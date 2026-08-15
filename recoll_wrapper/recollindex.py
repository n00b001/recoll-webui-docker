"""TrueNAS Recoll indexing wrapper.

Runs recollindex inside a Docker container with full diagnostics,
concurrency locking, and coloured logging to both console and file.

Usage:
    uv run python recollindex.py          # incremental (file-diff) index
    uv run python recollindex.py --rebuild  # full rebuild (removes existing index)
"""

from __future__ import annotations

import fcntl
import logging
import os
import re
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONTAINER = "recoll-engine"
BASE_PATH = os.environ.get("RECOLL_BASE_PATH", "/mnt/shuttle/share")
LOG_FILE = os.path.join(BASE_PATH, "app-data/recoll/.recoll/recollindex.log")
CONFIG_FILE = os.path.join(BASE_PATH, "app-data/recoll/.recoll/recoll.conf")
INDEX_PATH = "/root/.recoll/xapiandb"
LOCK_FILE = "/tmp/recollindex-wrapper.lock"
DATASETS_OF_INTEREST = ("lambo/share", "shuttle/share")

# ---------------------------------------------------------------------------
# Logging setup — Rich handler to both stderr and log file
# ---------------------------------------------------------------------------

try:
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)
    log_file = open(LOG_FILE, "a")  # noqa: SIM115
except (OSError, PermissionError):
    log_file = None

console = Console(file=log_file, stderr=True)
logging.basicConfig(
    level=logging.DEBUG,
    format="%(message)s",
    datefmt="[%X]",
    handlers=[
        RichHandler(
            console=console,
            rich_tracebacks=True,
            tracebacks_show_locals=True,
            markup=True,
            log_time_format="[%X]",
        )
    ],
)
log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cmd(*args: str, timeout: int | None = None) -> subprocess.CompletedProcess[str]:
    """Run a command. Diagnostics never abort the script."""
    try:
        return subprocess.run(
            args, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess[str](
            args, -1, "", f"Timed out after {timeout}s"
        )


def pretty_duration(seconds: float) -> str:
    """Format seconds as ``HHh MMm SSs``."""
    t = timedelta(seconds=int(seconds))
    h, m, s = (
        int(t.total_seconds()) // 3600,
        (int(t.total_seconds()) % 3600) // 60,
        int(t.total_seconds()) % 60,
    )
    return f"{h:02d}h {m:02d}m {s:02d}s"


def _print_cmd_output(
    _label: str, result: subprocess.CompletedProcess[str], logger: logging.Logger
) -> None:
    """Print command output, handling failures gracefully.

    On TrueNAS, some host utilities are missing or return
    ``Function not implemented``. This helper logs stdout on success
    and a generic (unavailable) placeholder on failure instead of
    dumping stderr as data.
    """
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            logger.info("  %s", line)
    elif result.returncode != 0:
        logger.debug("(unavailable)")


def _print_section(title: str) -> None:
    log.info("═══ %s ═══", title)


def _print_subsection(title: str) -> None:
    log.info("─── %s ───", title)


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def container_diagnostics(label: str) -> None:
    """Print Docker / container health information.

    Args:
        label: Prefix for the diagnostic section (e.g., "Initial", "Post-index").
    """
    _print_subsection(f"{label}: Container diagnostics")

    # Container status table
    log.info("Container status:")
    result = run_cmd(
        "docker",
        "ps",
        "--filter",
        f"name={CONTAINER}",
        "--format",
        "table {{.Names}}\t{{.Status}}\t{{.Image}}",
    )
    for line in result.stdout.strip().splitlines():
        log.info("  %s", line)

    # Container image
    result = run_cmd(
        "docker",
        "inspect",
        CONTAINER,
        "--format",
        "{{.Config.Image}}",
    )
    log.info("Container image: %s", result.stdout.strip())

    # Recoll version
    result = run_cmd(
        "docker", "exec", CONTAINER, "sh", "-c", "recollindex -h 2>&1 | head -3"
    )
    log.info("Recoll version:")
    for line in result.stdout.strip().splitlines():
        log.info("  %s", line)
    if result.stderr.strip():
        log.debug("%s", result.stderr.strip())

    # Index size
    result = run_cmd(
        "docker", "exec", CONTAINER, "sh", "-c", f"du -sh {INDEX_PATH} 2>/dev/null"
    )
    for line in result.stdout.strip().splitlines():
        log.info("Index size: %s", line.strip())

    # Container resources (CPU, memory, network, I/O)
    log.info("Container resources:")
    result = run_cmd("docker", "stats", CONTAINER, "--no-stream")
    for line in result.stdout.strip().splitlines():
        log.info("  %s", line)

    # Recoll processes inside container
    log.info("Existing Recoll processes:")
    result = run_cmd(
        "docker",
        "exec",
        CONTAINER,
        "sh",
        "-c",
        "ps -eo pid,comm,args | grep -E 'recoll(index)?|rcl' " "| grep -v grep",
    )
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log.info("  %s", line)
    else:
        log.debug("(none)")


def storage_diagnostics(label: str) -> None:
    """Print ZFS, disk, and kernel-level storage information.

    Runs on the TrueNAS host (not inside the container).

    Args:
        label: Prefix for the diagnostic section.
    """
    _print_subsection(f"{label}: Storage diagnostics")

    log.info(
        "NOTE: zpool/zfs diagnostics run on the TrueNAS host, "
        "not inside the Recoll container."
    )

    # ZFS pools ----------------------------------------------------------
    log.info("ZFS pools:")
    _print_cmd_output("zpool status", run_cmd("zpool", "status"), log)

    # Selected ZFS datasets (only the ones we care about) ----------------
    log.info("Selected ZFS datasets:")
    result = run_cmd(
        "zfs",
        "list",
        "-H",
        "-o",
        "name,used,available,referenced,mountpoint",
    )
    if result.returncode == 0:
        log.info("  NAME                          USED    AVAIL   REFER   MOUNTPOINT")
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 5 and parts[0] in DATASETS_OF_INTEREST:
                log.info("  %s %s", " ".join(f"{p:<16}" for p in parts[:4]), parts[4])
    else:
        log.warning("ZFS datasets unavailable")

    # ZFS ARC cache stats ------------------------------------------------
    log.info("ZFS ARC:")
    arc_path = Path("/proc/spl/kstat/zfs/arcstats")
    if arc_path.exists():
        try:
            text = arc_path.read_text()
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] in (
                    "size",
                    "c_min",
                    "c_max",
                    "hits",
                    "misses",
                ):
                    log.info("  %s %s", parts[1], parts[2])
        except OSError:
            log.error("Could not read ARC stats")
    else:
        log.warning("ARC stats unavailable")

    # Filesystem usage ---------------------------------------------------
    log.info("Filesystem usage:")
    dataset_mounts = {f"/mnt/{ds.split('/')[0]}/share" for ds in DATASETS_OF_INTEREST}
    _print_cmd_output("df", run_cmd("df", "-h", *dataset_mounts), log)

    # Block devices ------------------------------------------------------
    log.info("Block devices:")
    result = run_cmd(
        "lsblk",
        "-o",
        "NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT",
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log.info("  %s", line)
    else:
        log.debug("Block devices unavailable")

    # PCI storage adapters -----------------------------------------------
    log.info("PCI storage adapters:")
    result = run_cmd("lspci")
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if re.search(
                r"sata|ahci|raid|sas|lsi|marvell|asm|asmedia|usb",
                line,
                re.IGNORECASE,
            ):
                log.info("  %s", line)
    else:
        log.debug("lspci not available")

    # SMART devices ------------------------------------------------------
    log.info("SMART devices:")
    _print_cmd_output("smartctl", run_cmd("smartctl", "--scan-open"), log)

    # Recent kernel storage messages -------------------------------------
    log.info("Recent kernel storage messages:")
    result = run_cmd(
        "sh",
        "-c",
        'dmesg | grep -Ei "ata|ahci|sas|scsi|usb|reset|timeout|error|failed|link|crc" '
        "| tail -100",
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            log.debug("%s", line)
    else:
        log.debug("Kernel storage messages unavailable")


def print_configuration() -> None:
    """Print relevant Recoll configuration values."""
    _print_subsection("Configuration")

    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        log.error("Missing config file: %s", CONFIG_FILE)
        return

    keys_of_interest: set[str] = {
        "topdirs",
        "dbdir",
        "indexstemminglanguages",
        "indexallfilenames",
        "loglevel",
        "maxfsmbexp",
        "storeAllExtraDbFields",
        "usesystemhacks",
    }
    try:
        for line in config_path.read_text().splitlines():
            stripped = line.strip()
            if "=" in stripped and not stripped.startswith("#"):
                key = stripped.split("=")[0].strip()
                if key in keys_of_interest:
                    log.info("  %s", stripped)
    except OSError as exc:
        log.error("Could not read config: %s", exc)


def check_existing_indexers() -> bool:
    """Check whether recollindex is already running inside the container.

    Returns:
        True if an indexer is already running (i.e., we should abort).
    """
    result = run_cmd(
        "docker",
        "exec",
        CONTAINER,
        "sh",
        "-c",
        "pgrep -x recollindex | wc -l",
    )
    count_text = result.stdout.strip()
    count = int(count_text) if count_text.isdigit() else 0

    log.info("Checking existing Recoll indexers...")
    log.info("Existing recollindex processes: %d", count)

    if count > 0:
        log.error("recollindex is already running.")
        log.error("Refusing to start another indexer.")
        return True
    return False


# ---------------------------------------------------------------------------
# Full rebuild confirmation
# ---------------------------------------------------------------------------


def confirm_rebuild() -> bool:
    """Ask the user for y/N confirmation before a full rebuild."""
    log.warning("WARNING: This will completely rebuild the Recoll index.")
    log.warning("This may take a long time.")

    # console.input() is needed for interactive prompt
    answer = console.input("Continue? [y/N] ").strip().lower()
    if answer in ("y", "yes"):
        log.info("Starting full rebuild...")
        return True
    log.warning("Cancelled.")
    return False


# ---------------------------------------------------------------------------
# Run recollindex with live progress
# ---------------------------------------------------------------------------


def run_indexing(mode: str, command: list[str]) -> int:
    """Run recollindex inside the container with a live progress spinner."""
    _print_subsection("Indexing")
    log.info("Mode: %s", mode)
    log.info("Command: %s", " ".join(command))

    full_cmd = [
        "docker",
        "exec",
        CONTAINER,
        "sh",
        "-c",
        f"ionice -c 3 nice -n 19 {' '.join(command)}",
    ]

    start = time.monotonic()

    with Progress(
        SpinnerColumn(spinner_name="arrow"),
        TextColumn("[bold cyan]{task.description}[/]"),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        task = progress.add_task("Indexing in progress...", start=True)

        proc = subprocess.Popen(
            full_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
        )

        while proc.poll() is None:
            elapsed = time.monotonic() - start
            progress.update(
                task, description=f"Indexing... ({pretty_duration(elapsed)})"
            )
            time.sleep(1)

        exit_code = proc.returncode

    duration = time.monotonic() - start

    for label, stream, level in [
        ("stdout", proc.stdout, logging.INFO),
        ("stderr", proc.stderr, logging.WARNING),
    ]:
        assert stream is not None
        text = stream.read().strip()
        if not text:
            continue
        lines = text.splitlines()
        log.log(level, "recollindex %s:", label)
        for line in lines[:50]:
            log.log(level, "  %s", line)
        if len(lines) > 50:
            log.log(level, "  ... (%d lines total)", len(lines))

    status = "SUCCESS" if exit_code == 0 else f"FAILED (exit {exit_code})"
    elapsed = pretty_duration(duration)
    log.info("")
    log.info("Indexing complete: %s in %s", status, elapsed)

    return exit_code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point."""
    rebuild = "--rebuild" in sys.argv[1:]

    start_wall = time.monotonic()
    my_pid = os.getpid()

    # Header
    _print_section("START")
    hostname_result = run_cmd("hostname")
    log.info("PID       : %s", my_pid)
    hostname = (
        hostname_result.stdout.strip() if hostname_result.returncode == 0 else "unknown"
    )
    log.info("Hostname  : %s", hostname)
    log.info("User      : %s", os.environ.get("USER", "unknown"))
    log.info("Arguments : %s", " ".join(sys.argv[1:]))
    log.info("Time      : %s", time.strftime("%a %b %d %X %Z %Y"))
    log.info("Container : %s", CONTAINER)

    # Pre-index diagnostics
    container_diagnostics("Initial")
    storage_diagnostics("Initial")
    print_configuration()

    # Guard: don't start a second indexer
    if check_existing_indexers():
        log.error("Aborting because Recoll is already indexing.")

        duration = time.monotonic() - start_wall
        log.info("Exit code : 2")
        log.info("Duration  : %s", pretty_duration(duration))
        log.info("Finished  : %s", time.strftime("%a %b %d %X %Z %Y"))

        _print_section("END")
        log.info("PID       : %s", my_pid)
        log.info("Exit code : 2")
        log.info("Time      : %s", time.strftime("%a %b %d %X %Z %Y"))

        return 2

    # Full rebuild confirmation
    if rebuild and not confirm_rebuild():
        log.warning("Cancelled.")
        return 0

    # Run indexing --------------------------------------------------------
    if rebuild:
        exit_code = run_indexing("FULL REBUILD", ["recollindex", "-z"])
    else:
        exit_code = run_indexing("INCREMENTAL", ["recollindex"])

    # Post-index diagnostics
    container_diagnostics("Post-index")
    storage_diagnostics("Post-index")

    # Final summary -------------------------------------------------------
    duration = time.monotonic() - start_wall

    log.info("-" * 40)

    log.info("Exit code : %s", exit_code)
    log.info("Duration  : %s", pretty_duration(duration))
    log.info("Finished  : %s", time.strftime("%a %b %d %X %Z %Y"))

    _print_section("END")
    log.info("PID       : %s", my_pid)
    log.info("Exit code : %s", exit_code)
    log.info("Time      : %s", time.strftime("%a %b %d %X %Z %Y"))

    return exit_code


# ---------------------------------------------------------------------------
# Entry point with file lock
# ---------------------------------------------------------------------------


def _locked_main() -> int:
    """Run main() inside a non-blocking file lock."""
    try:
        lock_fd = open(LOCK_FILE, "w", encoding="utf-8")  # noqa: SIM115
    except OSError as exc:
        log.error("Cannot create lock file %s: %s", LOCK_FILE, exc)
        return 1

    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        return main()
    except BaseException:
        log.exception("Unhandled exception:")
        return 1
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    sys.exit(_locked_main())
