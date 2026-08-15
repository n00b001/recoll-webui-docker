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
from rich.panel import Panel
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
# Logging setup — console + file with Rich formatting
# ---------------------------------------------------------------------------

def _setup_logging() -> Console:
    """Configure root logger with Rich handlers for console and file."""
    Path(LOG_FILE).parent.mkdir(parents=True, exist_ok=True)

    # Console handler (stderr) — rich formatting, colours, traceback support
    console = Console(stderr=True)
    console_handler = RichHandler(
        console=console,
        rich_tracebacks=True,
        tracebacks_show_locals=True,
        markup=True,
        log_time_format="[%X]",
    )
    console_handler.setLevel(logging.INFO)

    # File handler (plain text for grep-ability, no markup)
    file_handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
    )
    file_handler.setFormatter(file_formatter)

    # Root logger
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    # Return console for Progress/Progress rendering
    return console


console: Console = _setup_logging()
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
    _label: str, result: subprocess.CompletedProcess[str], c: Console
) -> None:
    """Print command output, handling failures gracefully.

    On TrueNAS, some host utilities are missing or return
    ``Function not implemented``. This helper prints stdout on success
    and a generic (unavailable) placeholder on failure instead of
    dumping stderr as data.
    """
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            c.print(f"  {line}")
    elif result.returncode != 0:
        c.print("  [dim](unavailable)[/]")


def _print_section(title: str) -> None:
    console.print(Panel.fit(title, border_style="bold yellow", padding=(0, 1)))


def _print_subsection(title: str) -> None:
    console.rule(f"[bold cyan]{title}[/]")


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
    c = console
    c.print("Container status:")
    result = run_cmd(
        "docker",
        "ps",
        "--filter",
        f"name={CONTAINER}",
        "--format",
        "table {{.Names}}\t{{.Status}}\t{{.Image}}",
    )
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")

    # Container image
    result = run_cmd(
        "docker",
        "inspect",
        CONTAINER,
        "--format",
        "{{.Config.Image}}",
    )
    c.print(f"Container image: [cyan]{result.stdout.strip()}[/]")

    # Recoll version
    result = run_cmd("docker", "exec", CONTAINER,
                     "sh", "-c", "recollindex -h 2>&1 | head -3")
    c.print("Recoll version:")
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")
    if result.stderr.strip():
        c.print(f"  [dim]{result.stderr.strip()}[/]")

    # Index size
    result = run_cmd("docker", "exec", CONTAINER,
                     "sh", "-c", f"du -sh {INDEX_PATH} 2>/dev/null")
    for line in result.stdout.strip().splitlines():
        c.print(f"Index size: [cyan]{line.strip()}[/]")

    # Container resources (CPU, memory, network, I/O)
    c.print("Container resources:")
    result = run_cmd("docker", "stats", CONTAINER, "--no-stream")
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")

    # Recoll processes inside container
    c.print("Existing Recoll processes:")
    result = run_cmd(
        "docker", "exec", CONTAINER, "sh", "-c",
        "ps -eo pid,comm,args | grep -E 'recoll(index)?|rcl' "
        "| grep -v grep",
    )
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            c.print(f"  {line}")
    else:
        c.print("  [dim](none)[/]")


def storage_diagnostics(label: str) -> None:  # noqa: PLR0915
    """Print ZFS, disk, and kernel-level storage information.

    Runs on the TrueNAS host (not inside the container).

    Args:
        label: Prefix for the diagnostic section.
    """
    _print_subsection(f"{label}: Storage diagnostics")

    c = console
    c.print(
        "[dim]NOTE: zpool/zfs diagnostics run on the TrueNAS host,[/]"
        " not inside the Recoll container."
    )

    # ZFS pools ----------------------------------------------------------
    c.print("ZFS pools:")
    _print_cmd_output("zpool status", run_cmd("zpool", "status"), c)

    # Selected ZFS datasets (only the ones we care about) ----------------
    c.print("Selected ZFS datasets:")
    result = run_cmd(
        "zfs",
        "list",
        "-H",
        "-o",
        "name,used,available,referenced,mountpoint",
    )
    if result.returncode == 0:
        c.print("  NAME                          USED    AVAIL   REFER   MOUNTPOINT")
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 5 and parts[0] in DATASETS_OF_INTEREST:
                c.print(f"  {' '.join(f'{p:<16}' for p in parts[:4])} {parts[4]}")
    else:
        c.print("  [dim](unavailable)[/]")

    # ZFS ARC cache stats ------------------------------------------------
    c.print("ZFS ARC:")
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
                    c.print(f"  {parts[1]:<12} {parts[2]}")
        except OSError:
            c.print("  [red]Could not read ARC stats[/]")
    else:
        c.print("  [yellow]ARC stats unavailable[/]")

    # Filesystem usage ---------------------------------------------------
    c.print("Filesystem usage:")
    dataset_mounts = {f"/mnt/{ds.split('/')[0]}/share" for ds in DATASETS_OF_INTEREST}
    _print_cmd_output("df", run_cmd("df", "-h", *dataset_mounts), c)

    # Block devices ------------------------------------------------------
    c.print("Block devices:")
    result = run_cmd(
        "lsblk",
        "-o",
        "NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT",
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            c.print(f"  {line}")
    else:
        c.print("  [dim](unavailable)[/]")

    # PCI storage adapters -----------------------------------------------
    c.print("PCI storage adapters:")
    result = run_cmd("lspci")
    if result.returncode == 0:
        for line in result.stdout.strip().splitlines():
            if re.search(
                r"sata|ahci|raid|sas|lsi|marvell|asm|asmedia|usb",
                line,
                re.IGNORECASE,
            ):
                c.print(f"  {line}")
    else:
        c.print("  [dim]lspci not available[/]")

    # SMART devices ------------------------------------------------------
    c.print("SMART devices:")
    _print_cmd_output("smartctl", run_cmd("smartctl", "--scan-open"), c)

    # Recent kernel storage messages -------------------------------------
    c.print("Recent kernel storage messages:")
    result = run_cmd(
        "sh",
        "-c",
        'dmesg | grep -Ei "ata|ahci|sas|scsi|usb|reset|timeout|error|failed|link|crc" '
        "| tail -100",
    )
    if result.returncode == 0 and result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            c.print(f"  [dim]{line}[/]")
    else:
        c.print("  [dim](unavailable)[/]")


def print_configuration() -> None:
    """Print relevant Recoll configuration values."""
    _print_subsection("Configuration")

    c = console
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        c.print(f"[red]Missing config file: {CONFIG_FILE}[/]")
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
                    c.print(f"  {stripped}")
    except OSError as exc:
        c.print(f"[red]Could not read config: {exc}[/]")


def check_existing_indexers() -> bool:
    """Check whether recollindex is already running inside the container.

    Returns:
        True if an indexer is already running (i.e., we should abort).
    """
    result = run_cmd(
        "docker", "exec", CONTAINER,
        "sh", "-c", "pgrep -x recollindex | wc -l",
    )
    count_text = result.stdout.strip()
    count = int(count_text) if count_text.isdigit() else 0

    c = console
    c.print("Checking existing Recoll indexers...")
    c.print(f"Existing recollindex processes: [bold]{count}[/]")

    if count > 0:
        c.print("[red]ERROR: recollindex is already running.[/]")
        c.print("[red]Refusing to start another indexer.[/]")
        return True
    return False


# ---------------------------------------------------------------------------
# Full rebuild confirmation
# ---------------------------------------------------------------------------


def confirm_rebuild() -> bool:
    """Ask the user for y/N confirmation before a full rebuild."""
    c = console
    c.print(
        "\n[bold red]WARNING:[/] This will completely rebuild the Recoll index."
    )
    c.print("[yellow]This may take a long time.[/]\n")

    answer = c.input("Continue? [y/N] ").strip().lower()
    if answer in ("y", "yes"):
        c.print("[green]Starting full rebuild...\n[/]")
        return True
    c.print("[yellow]Cancelled.\n[/]")
    return False


# ---------------------------------------------------------------------------
# Run recollindex with live progress
# ---------------------------------------------------------------------------


def run_indexing(mode: str, command: list[str]) -> int:
    """Run recollindex inside the container with a live progress spinner."""
    c = console
    _print_subsection("Indexing")
    c.print(f"Mode: [bold magenta]{mode}[/]")
    c.print(f"Command: [cyan]{' '.join(command)}[/]\n")

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
        console=c,
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

    for label, stream, style in [
        ("stdout", proc.stdout, "green"),
        ("stderr", proc.stderr, "red"),
    ]:
        assert stream is not None
        text = stream.read().strip()
        if not text:
            continue
        lines = text.splitlines()
        c.print(f"\n[bold {style}]recollindex {label}:[/]")
        prefix = "[red]" if style == "red" else ""
        suffix = "[/]" if style == "red" else ""
        for line in lines[:50]:
            c.print(f"  {prefix}{line}{suffix}")
        if len(lines) > 50:
            c.print(f"  [dim]... ({len(lines)} lines total)[/]")

    status = "SUCCESS" if exit_code == 0 else f"FAILED (exit {exit_code})"
    style = "green" if exit_code == 0 else "red"
    elapsed = pretty_duration(duration)
    c.print()
    c.print(f"Indexing complete: [bold {style}]{status}[/] in [cyan]{elapsed}[/]")

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
    c = console
    hostname_result = run_cmd("hostname")
    c.print(f"PID       : [cyan]{my_pid}[/]")
    hostname = (
        hostname_result.stdout.strip() if hostname_result.returncode == 0 else "unknown"
    )
    c.print(f"Hostname  : [cyan]{hostname}[/]")
    c.print(f"User      : [cyan]{os.environ.get('USER', 'unknown')}[/]")
    c.print(f"Arguments : [cyan]{' '.join(sys.argv[1:])}[/]")
    c.print(f"Time      : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]")
    c.print(f"Container : [cyan]{CONTAINER}[/]\n")

    # Pre-index diagnostics
    container_diagnostics("Initial")
    storage_diagnostics("Initial")
    print_configuration()

    # Guard: don't start a second indexer
    if check_existing_indexers():
        c.print("\n[red]Aborting because Recoll is already indexing.[/]\n")

        duration = time.monotonic() - start_wall
        c.rule()
        c.print("Exit code : [red]2[/]")
        c.print(f"Duration  : [cyan]{pretty_duration(duration)}[/]")
        c.print(f"Finished  : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]\n")

        _print_section("END")
        c.print(f"PID       : [cyan]{my_pid}[/]")
        c.print("Exit code : [red]2[/]")
        c.print(f"Time      : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]")

        return 2

    # Full rebuild confirmation
    if rebuild and not confirm_rebuild():
        c.print("[yellow]Cancelled.[/]\n")
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

    c.rule()

    exit_style = "green" if exit_code == 0 else "red"
    c.print(f"Exit code : [bold {exit_style}]{exit_code}[/]")
    c.print(f"Duration  : [bold cyan]{pretty_duration(duration)}[/]")
    c.print(f"Finished  : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]\n")

    _print_section("END")
    c.print(f"PID       : [cyan]{my_pid}[/]")
    c.print(f"Exit code : [bold {exit_style}]{exit_code}[/]")
    c.print(f"Time      : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]")

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
