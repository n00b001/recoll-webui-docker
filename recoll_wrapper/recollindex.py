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
from pathlib import Path
from typing import IO

from rich.console import Console
from rich.logging import RichHandler
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

CONTAINER: str = "recoll-engine"
LOG_FILE: str = "/mnt/shuttle/share/app-data/recoll/.recoll/recollindex.log"
CONFIG_FILE: str = "/mnt/shuttle/share/app-data/recoll/.recoll/recoll.conf"
INDEX_PATH: str = "/root/.recoll/xapiandb"
LOCK_FILE: str = "/tmp/recollindex-wrapper.lock"
DATASETS_OF_INTEREST: tuple[str, ...] = ("lambo/share", "shuttle/share")

# ---------------------------------------------------------------------------
# Console / logging setup
# ---------------------------------------------------------------------------

class _LogState:
    """Mutable holder for the active logger and console.

    Avoids the ``global`` keyword by storing references on an instance.
    """

    def __init__(self) -> None:
        # Temporary console writing only to stderr until log file is ready.
        self.console: Console = Console()
        self.logger: logging.Logger = logging.getLogger("recoll")

    def configure(self, log_path: Path) -> None:
        """Set up coloured console output + log-file tee.

        Uses Python's standard ``logging`` module with two handlers:
        - A ``RichHandler`` that feeds back into the Rich Console (which
          writes to a ``_TeeStream`` so colour goes to both terminal and file).
        - A plain ``FileHandler`` for machine-parsable log lines.

        Args:
            log_path: Absolute path to the log file.
        """
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Tee stream: writes to both the terminal and the log file.
        log_fd = open(log_path, "a", encoding="utf-8")  # noqa: SIM115
        tee = _TeeStream(sys.stdout, log_fd)

        # Replace the console with one that targets the tee.
        self.console = Console(
            file=tee,
            force_terminal=True,
            no_color=False,
        )

        # Reconfigure logging to use the new console.
        self.logger.handlers.clear()
        rich_handler = RichHandler(console=self.console, rich_tracebacks=True)
        rich_handler.setFormatter(logging.Formatter("%(message)s", datefmt="[%X]"))
        self.logger.addHandler(rich_handler)

        # Plain file handler for machine-parsable output.
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        )
        self.logger.addHandler(file_handler)


# Module-level singleton avoiding ``global`` inside functions.
_log = _LogState()


def console() -> Console:
    """Return the active Rich console.

    Returns:
        The configured ``Console`` instance.
    """
    return _log.console


def logger() -> logging.Logger:
    """Return the active Python logger.

    Returns:
        The configured ``logging.Logger`` instance.
    """
    return _log.logger


def _setup_logging(log_path: Path) -> None:
    """Initialise logging to write to both console and file.

    Args:
        log_path: Path to the log file.
    """
    _log.configure(log_path)


class _TeeStream(IO[str]):
    """Write to both the terminal (original stdout) and a log file.

    Implements ``IO[str]`` so it can be passed directly to Rich Console.
    """

    def __init__(self, original: IO[str], log: IO[str]) -> None:
        self._original = original
        self._log = log

    def write(self, data: str) -> int:
        """Write to both streams.

        Args:
            data: Text to write.

        Returns:
            Number of characters written to the original stream.
        """
        self._log.write(data)
        self._log.flush()
        return self._original.write(data)

    def flush(self) -> None:
        """Flush both underlying streams."""
        self._original.flush()
        self._log.flush()

    def isatty(self) -> bool:
        """Delegate ``isatty`` to the original stream.

        Returns:
            Whether the original stream is a TTY.
        """
        return self._original.isatty()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def run_cmd(
    *args: str,
    timeout: int | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run a command and return the CompletedProcess.

    Diagnostics never abort the script even when they fail.

    Args:
        *args: Command and arguments to execute.
        timeout: Optional timeout in seconds.

    Returns:
        A ``CompletedProcess`` containing stdout, stderr, and return code.
    """
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return result
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess[str](
            args, -1, "", f"Timed out after {timeout}s"
        )


def docker_exec(*cmd: str) -> subprocess.CompletedProcess[str]:
    """Shortcut for ``docker exec <CONTAINER> <cmd>``.

    Args:
        *cmd: Command to execute inside the container.

    Returns:
        A ``CompletedProcess`` containing stdout, stderr, and return code.
    """
    return run_cmd("docker", "exec", CONTAINER, *cmd)


def pretty_duration(seconds: float) -> str:
    """Format seconds as ``HHh MMm SSs``.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted duration string.
    """
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = int(seconds % 60)
    return f"{h:02d}h {m:02d}m {s:02d}s"


def print_section(title: str) -> None:
    """Print a visually separated section header.

    Args:
        title: Section title to display.
    """
    console().print(
        Panel.fit(title, border_style="bold yellow", padding=(0, 1))
    )


def print_subsection(title: str) -> None:
    """Print a subsection rule line.

    Args:
        title: Subsection title to display.
    """
    console().rule(f"[bold cyan]{title}[/]")


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def container_diagnostics(label: str) -> None:
    """Print Docker / container health information.

    Args:
        label: Prefix for the diagnostic section (e.g., "Initial", "Post-index").
    """
    print_subsection(f"{label}: Container diagnostics")

    # Container status table
    c = console()
    c.print("Container status:")
    result = run_cmd(
        "docker", "ps",
        "--filter", f"name={CONTAINER}",
        "--format", "table {{.Names}}\t{{.Status}}\t{{.Image}}",
    )
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")

    # Container image
    result = run_cmd(
        "docker", "inspect", CONTAINER,
        "--format", "{{.Config.Image}}",
    )
    c.print(f"Container image: [cyan]{result.stdout.strip()}[/]")

    # Recoll version
    result = docker_exec("sh", "-c", "recollindex -h 2>&1 | head -3")
    c.print("Recoll version:")
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")
    if result.stderr.strip():
        c.print(f"  [dim]{result.stderr.strip()}[/]")

    # Index size
    result = docker_exec("sh", "-c", f"du -sh {INDEX_PATH} 2>/dev/null")
    for line in result.stdout.strip().splitlines():
        c.print(f"Index size: [cyan]{line.strip()}[/]")

    # Container resources (CPU, memory, network, I/O)
    c.print("Container resources:")
    result = run_cmd("docker", "stats", CONTAINER, "--no-stream")
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")

    # Recoll processes inside container
    c.print("Existing Recoll processes:")
    result = docker_exec(
        "sh", "-c",
        "ps -eo pid,comm,args | grep -E 'recoll(index)?|rcl' | grep -v grep",
    )
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            c.print(f"  {line}")
    else:
        c.print("  [dim](none)[/]")


def storage_diagnostics(label: str) -> None:
    """Print ZFS, disk, and kernel-level storage information.

    Runs on the TrueNAS host (not inside the container).

    Args:
        label: Prefix for the diagnostic section.
    """
    print_subsection(f"{label}: Storage diagnostics")

    c = console()
    c.print(
        "[dim]NOTE: zpool/zfs diagnostics run on the TrueNAS host,[/]"
        " not inside the Recoll container."
    )

    # ZFS pools ----------------------------------------------------------
    c.print("ZFS pools:")
    result = run_cmd("zpool", "status")
    output = result.stdout or result.stderr
    for line in output.strip().splitlines():
        c.print(f"  {line}")

    # Selected ZFS datasets (only the ones we care about) ----------------
    c.print("Selected ZFS datasets:")
    result = run_cmd(
        "zfs", "list",
        "-H", "-o", "name,used,available,referenced,mountpoint",
    )
    if result.returncode == 0:
        c.print(
            "  NAME                          USED    AVAIL   REFER   MOUNTPOINT"
        )
        for line in result.stdout.strip().splitlines():
            parts = line.split("\t")
            if len(parts) >= 5 and parts[0] in DATASETS_OF_INTEREST:
                c.print(
                    f"  {' '.join(f'{p:<16}' for p in parts[:4])} {parts[4]}"
                )
    else:
        c.print(f"  [red]zfs list failed: {result.stderr.strip()}[/]")

    # ZFS ARC cache stats ------------------------------------------------
    c.print("ZFS ARC:")
    arc_path = Path("/proc/spl/kstat/zfs/arcstats")
    if arc_path.exists():
        try:
            text = arc_path.read_text()
            for line in text.splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1] in (
                    "size", "c_min", "c_max", "hits", "misses"
                ):
                    c.print(f"  {parts[1]:<12} {parts[2]}")
        except OSError:
            c.print("  [red]Could not read ARC stats[/]")
    else:
        c.print("  [yellow]ARC stats unavailable[/]")

    # Filesystem usage ---------------------------------------------------
    c.print("Filesystem usage:")
    dataset_mounts = {f"/mnt/{ds.split('/')[0]}/share" for ds in DATASETS_OF_INTEREST}
    result = run_cmd("df", "-h", *dataset_mounts)
    for line in (result.stdout or result.stderr).strip().splitlines():
        c.print(f"  {line}")

    # Block devices ------------------------------------------------------
    c.print("Block devices:")
    result = run_cmd(
        "lsblk", "-o", "NAME,SIZE,MODEL,SERIAL,FSTYPE,MOUNTPOINT",
    )
    for line in result.stdout.strip().splitlines():
        c.print(f"  {line}")

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
    result = run_cmd("smartctl", "--scan-open")
    for line in (result.stdout or result.stderr).strip().splitlines():
        c.print(f"  {line}")

    # Recent kernel storage messages -------------------------------------
    c.print("Recent kernel storage messages:")
    result = run_cmd(
        "sh", "-c",
        'dmesg | grep -Ei "ata|ahci|sas|scsi|usb|reset|timeout|error|failed|link|crc" '
        "| tail -100",
    )
    for line in (result.stdout or result.stderr).strip().splitlines():
        c.print(f"  [dim]{line}[/]")


def print_configuration() -> None:
    """Print relevant Recoll configuration values."""
    print_subsection("Configuration")

    c = console()
    config_path = Path(CONFIG_FILE)
    if not config_path.exists():
        c.print(f"[red]Missing config file: {CONFIG_FILE}[/]")
        return

    keys_of_interest: set[str] = {
        "topdirs", "dbdir", "indexstemminglanguages",
        "indexallfilenames", "loglevel", "maxfsmbexp",
        "storeAllExtraDbFields", "usesystemhacks",
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
    result = docker_exec(
        "sh", "-c", "pgrep -x recollindex | wc -l",
    )
    count_text = result.stdout.strip()
    count = int(count_text) if count_text.isdigit() else 0

    c = console()
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
    """Ask the user for y/N confirmation before a full rebuild.

    Returns:
        True if confirmed, False if cancelled.
    """
    c = console()
    c.print("\n[bold red]WARNING:[/] This will completely rebuild the Recoll index.")
    c.print("[yellow]This may take a long time.[/]\n")

    answer = input("Continue? [y/N] ").strip().lower()
    if answer in ("y", "yes"):
        c.print("[green]Starting full rebuild...\n[/]")
        return True
    c.print("[yellow]Cancelled.\n[/]")
    return False


# ---------------------------------------------------------------------------
# Run recollindex with live progress
# ---------------------------------------------------------------------------


def run_indexing(mode: str, command: list[str]) -> int:
    """Execute the indexing command inside the container.

    Shows a live progress spinner with elapsed time while waiting.

    Args:
        mode: Display label (e.g., "FULL REBUILD", "INCREMENTAL").
        command: The recollindex command and flags to run.

    Returns:
        The exit code of the indexing process.
    """
    print_subsection("Indexing")
    c = console()
    c.print(f"Mode: [bold magenta]{mode}[/]")
    c.print("Command:")
    c.print(f"  [cyan]{' '.join(command)}[/]\n")

    # Build the full docker exec command with ionice + nice
    full_cmd = [
        "docker", "exec", CONTAINER,
        "sh", "-c",
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
            full_cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Poll until the process finishes
        while proc.poll() is None:
            elapsed = time.monotonic() - start
            progress.update(
                task,
                description=f"Indexing in progress... ({pretty_duration(elapsed)})",
            )
            time.sleep(1)

        exit_code = proc.returncode if proc.returncode is not None else 1

    duration = time.monotonic() - start

    # Surface any output from recollindex
    assert proc.stdout is not None
    assert proc.stderr is not None

    stdout_text = proc.stdout.read().strip()
    stderr_text = proc.stderr.read().strip()

    if stdout_text:
        c.print("\n[bold green]recollindex stdout:[/]")
        lines = stdout_text.splitlines()
        for line in lines[:50]:
            c.print(f"  {line}")
        if len(lines) > 50:
            c.print(f"  [dim]... ({len(lines)} lines total)[/]")

    if stderr_text:
        c.print("\n[bold red]recollindex stderr:[/]")
        lines = stderr_text.splitlines()
        for line in lines[:100]:
            c.print(f"  [red]{line}[/]")
        if len(lines) > 100:
            c.print(f"  [dim]... ({len(lines)} lines total)[/]")

    # Summary
    status = "SUCCESS" if exit_code == 0 else f"FAILED (exit {exit_code})"
    status_style = "green" if exit_code == 0 else "red"
    c.print(
        f"\nIndexing complete: [bold {status_style}]{status}[/] "
        f"in [cyan]{pretty_duration(duration)}[/]"
    )

    return exit_code


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> int:
    """Entry point."""
    rebuild = "--rebuild" in sys.argv[1:]

    log_path = Path(LOG_FILE)
    _setup_logging(log_path)

    start_wall = time.monotonic()
    my_pid = os.getpid()

    # Header
    print_section("START")
    c = console()
    hostname_result = run_cmd("hostname")
    c.print(f"PID       : [cyan]{my_pid}[/]")
    hostname = (
        hostname_result.stdout.strip()
        if hostname_result.returncode == 0
        else "unknown"
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

        print_section("END")
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

    print_section("END")
    c.print(f"PID       : [cyan]{my_pid}[/]")
    c.print(f"Exit code : [bold {exit_style}]{exit_code}[/]")
    c.print(f"Time      : [cyan]{time.strftime('%a %b %d %X %Z %Y')}[/]")

    return exit_code


# ---------------------------------------------------------------------------
# Entry point with file lock
# ---------------------------------------------------------------------------


def _locked_main() -> int:
    """Run main() inside a file lock.

    Returns:
        The exit code from ``main()``, or 1 on unhandled exception.
    """
    try:
        lock_fd = open(LOCK_FILE, "w", encoding="utf-8")  # noqa: SIM115
    except OSError as exc:
        console().print(f"[red]Cannot create lock file {LOCK_FILE}: {exc}[/]")
        return 1

    fcntl.flock(lock_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        return main()
    except BaseException:  # catch SystemExit, KeyboardInterrupt too
        console().print("[bold red]Unhandled exception:[/]")
        console().print_exception()
        return 1
    finally:
        fcntl.flock(lock_fd, fcntl.LOCK_UN)
        lock_fd.close()


if __name__ == "__main__":
    sys.exit(_locked_main())
