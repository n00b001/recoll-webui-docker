"""Comprehensive tests for recollindex module."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

# Ensure the wrapper package is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


# ---------------------------------------------------------------------------
# Module-level smoke tests
# ---------------------------------------------------------------------------


def test_module_imports() -> None:
    """Module imports without error."""
    import recollindex  # noqa: F401
    assert True


def test_datasets_of_interest() -> None:
    """DATASETS_OF_INTEREST contains expected datasets."""
    from recollindex import DATASETS_OF_INTEREST

    assert "lambo/share" in DATASETS_OF_INTEREST
    assert "shuttle/share" in DATASETS_OF_INTEREST


# ---------------------------------------------------------------------------
# pretty_duration
# ---------------------------------------------------------------------------


def test_pretty_duration() -> None:
    """pretty_duration formats seconds correctly."""
    from recollindex import pretty_duration

    assert pretty_duration(0) == "00h 00m 00s"
    assert pretty_duration(60) == "00h 01m 00s"
    assert pretty_duration(3600) == "01h 00m 00s"
    assert pretty_duration(3661) == "01h 01m 01s"
    assert pretty_duration(3723) == "01h 02m 03s"


def test_pretty_duration_large() -> None:
    """pretty_duration handles large values."""
    from recollindex import pretty_duration

    assert pretty_duration(172800) == "48h 00m 00s"
    assert pretty_duration(99999) == "27h 46m 39s"


# ---------------------------------------------------------------------------
# run_cmd
# ---------------------------------------------------------------------------


def test_run_cmd_success() -> None:
    """run_cmd returns CompletedProcess on success."""
    from recollindex import run_cmd

    result = run_cmd("echo", "hello")
    assert result.returncode == 0
    assert "hello" in result.stdout


def test_run_cmd_failure() -> None:
    """run_cmd returns non-zero exit code without raising."""
    from recollindex import run_cmd

    result = run_cmd("sh", "-c", "exit 42")
    assert result.returncode == 42


def test_run_cmd_timeout() -> None:
    """run_cmd catches TimeoutExpired and returns CompletedProcess."""
    from recollindex import run_cmd

    result = run_cmd("sleep", "10", timeout=1)
    assert result.returncode == -1
    assert "Timed out after 1s" in result.stderr


# ---------------------------------------------------------------------------
# _setup_logging / console
# ---------------------------------------------------------------------------


def test_setup_logging_returns_console() -> None:
    """_setup_logging returns a Console instance."""
    from rich.console import Console

    from recollindex import _setup_logging

    c = _setup_logging()
    assert isinstance(c, Console)


def test_module_console_initialised() -> None:
    """Module-level console is a rich Console after import."""
    from rich.console import Console

    import recollindex

    assert isinstance(recollindex.console, Console)
    assert recollindex.log is not None


# ---------------------------------------------------------------------------
# _print_section, _print_subsection
# ---------------------------------------------------------------------------


def test_print_section() -> None:
    """_print_section prints a panel."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        recollindex._print_section("Test Section")
        fake_console.print.assert_called_once()
    finally:
        recollindex.console = orig


def test_print_subsection() -> None:
    """_print_subsection prints a rule."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        recollindex._print_subsection("Test Sub")
        fake_console.rule.assert_called_once()
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# container_diagnostics
# ---------------------------------------------------------------------------


def test_container_diagnostics() -> None:
    """container_diagnostics runs through all diagnostics."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        mock_result = subprocess.CompletedProcess(
            [], 0, "name\tstatus\timage\n", ""
        )
        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            recollindex.container_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_container_diagnostics_no_processes() -> None:
    """container_diagnostics handles empty process list."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            return subprocess.CompletedProcess(args, 0, "\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            recollindex.container_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_container_diagnostics_with_stderr() -> None:
    """container_diagnostics prints stderr when present."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            if "recollindex -h" in args:
                return subprocess.CompletedProcess(args, 0, "v1\n", "warning\n")
            return subprocess.CompletedProcess(args, 0, "\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            recollindex.container_diagnostics("Test")
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# storage_diagnostics
# ---------------------------------------------------------------------------


def test_storage_diagnostics() -> None:
    """storage_diagnostics runs through all checks."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            with patch.object(Path, "exists", return_value=False):
                recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_storage_diagnostics_arc_available() -> None:
    """storage_diagnostics parses ARC stats when available."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "data\n", "")
        arc_content = (
            "timestamp    1234567890\n"
            "size         12345678\n"
            "c_min        1111111\n"
            "c_max        2222222\n"
            "hits         333333\n"
            "misses       44444\n"
        )

        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", return_value=arc_content):
                    recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_storage_diagnostics_arc_read_error() -> None:
    """storage_diagnostics handles OSError reading ARC stats."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            with patch.object(Path, "exists", return_value=True):
                with patch.object(Path, "read_text", side_effect=OSError("perm")):
                    recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_storage_diagnostics_zfs_failed() -> None:
    """storage_diagnostics handles zfs list failure."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            if args[0] == "zfs":
                return subprocess.CompletedProcess(args, 1, "", "error\n")
            return subprocess.CompletedProcess(args, 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            with patch.object(Path, "exists", return_value=False):
                recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_storage_diagnostics_lspci_unavailable() -> None:
    """storage_diagnostics handles missing lspci."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            if args[0] == "lspci":
                return subprocess.CompletedProcess(args, 1, "", "")
            return subprocess.CompletedProcess(args, 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            with patch.object(Path, "exists", return_value=False):
                recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


def test_storage_diagnostics_pci_matching() -> None:
    """storage_diagnostics filters PCI storage adapters."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            if args[0] == "lspci":
                return subprocess.CompletedProcess(
                    args, 0,
                    "00:1f.2 SATA controller: Intel\n"
                    "01:00.0 VGA compatible device: NVIDIA\n",
                    ""
                )
            return subprocess.CompletedProcess(args, 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            with patch.object(Path, "exists", return_value=False):
                recollindex.storage_diagnostics("Test")
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# print_configuration
# ---------------------------------------------------------------------------


def test_print_configuration_missing() -> None:
    """print_configuration handles missing config file."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        with patch.object(Path, "exists", return_value=False):
            recollindex.print_configuration()
            calls = [str(c) for c in fake_console.print.call_args_list]
            assert any("Missing config" in c for c in calls)
    finally:
        recollindex.console = orig


def test_print_configuration_success() -> None:
    """print_configuration parses and prints config values."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        config_content = (
            "# comment\n"
            'topdirs = /path1\n'
            'loglevel = 3\n'
            'other = value\n'
        )
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", return_value=config_content):
                recollindex.print_configuration()
                calls = [str(c) for c in fake_console.print.call_args_list]
                assert any("topdirs" in c for c in calls)
                assert any("loglevel" in c for c in calls)
    finally:
        recollindex.console = orig


def test_print_configuration_os_error() -> None:
    """print_configuration handles OSError reading config."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        with patch.object(Path, "exists", return_value=True):
            with patch.object(Path, "read_text", side_effect=OSError("perm")):
                recollindex.print_configuration()
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# check_existing_indexers
# ---------------------------------------------------------------------------


def test_check_existing_indexers_none() -> None:
    """check_existing_indexers returns False when no processes."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "0\n", "")
        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            result = recollindex.check_existing_indexers()
            assert result is False
    finally:
        recollindex.console = orig


def test_check_existing_indexers_running() -> None:
    """check_existing_indexers returns True when processes exist."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "2\n", "")
        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            result = recollindex.check_existing_indexers()
            assert result is True
    finally:
        recollindex.console = orig


def test_check_existing_indexers_non_digit() -> None:
    """check_existing_indexers handles non-digit output."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_result = subprocess.CompletedProcess([], 0, "error\n", "")
        with patch.object(recollindex, "run_cmd", return_value=mock_result):
            result = recollindex.check_existing_indexers()
            assert result is False
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# confirm_rebuild
# ---------------------------------------------------------------------------


def test_confirm_rebuild_yes() -> None:
    """confirm_rebuild returns True on 'y'."""
    import recollindex

    fake_console = MagicMock()
    fake_console.input.return_value = "y"
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        result = recollindex.confirm_rebuild()
        assert result is True
    finally:
        recollindex.console = orig


def test_confirm_rebuild_yes_full() -> None:
    """confirm_rebuild returns True on 'yes'."""
    import recollindex

    fake_console = MagicMock()
    fake_console.input.return_value = "yes"
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        result = recollindex.confirm_rebuild()
        assert result is True
    finally:
        recollindex.console = orig


def test_confirm_rebuild_no() -> None:
    """confirm_rebuild returns False on 'n'."""
    import recollindex

    fake_console = MagicMock()
    fake_console.input.return_value = "n"
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        result = recollindex.confirm_rebuild()
        assert result is False
    finally:
        recollindex.console = orig


def test_confirm_rebuild_empty() -> None:
    """confirm_rebuild returns False on empty input."""
    import recollindex

    fake_console = MagicMock()
    fake_console.input.return_value = ""
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        result = recollindex.confirm_rebuild()
        assert result is False
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# run_indexing
# ---------------------------------------------------------------------------


def _make_mock_proc(returncode, stdout="ok\n", stderr=""):
    """Helper to build a mock Popen process."""
    mock_proc = MagicMock()
    mock_proc.returncode = returncode
    mock_proc.stdout = MagicMock()
    mock_proc.stdout.read.return_value = stdout
    mock_proc.stderr = MagicMock()
    mock_proc.stderr.read.return_value = stderr
    mock_proc.poll.side_effect = [None, returncode]
    return mock_proc


def test_run_indexing_success() -> None:
    """run_indexing completes successfully."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_proc = _make_mock_proc(0)

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("time.sleep"):
                result = recollindex.run_indexing("INCREMENTAL", ["recollindex"])
                assert result == 0
    finally:
        recollindex.console = orig


def test_run_indexing_failure() -> None:
    """run_indexing returns non-zero on failure."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_proc = _make_mock_proc(2, stdout="", stderr="error\n")

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("time.sleep"):
                result = recollindex.run_indexing("FULL REBUILD", ["recollindex", "-z"])
                assert result == 2
    finally:
        recollindex.console = orig


def test_run_indexing_many_lines() -> None:
    """run_indexing truncates output beyond 50 lines."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_proc = _make_mock_proc(3, stdout="\n".join(f"line{i}" for i in range(100)))

        with patch("subprocess.Popen", return_value=mock_proc):
            with patch("time.sleep"):
                recollindex.run_indexing("INCREMENTAL", ["recollindex"])
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------


def test_main_incremental_success() -> None:
    """Main runs incremental indexing and returns exit code."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_proc = _make_mock_proc(0)

        with patch.object(recollindex, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "hostname\n", "")):
            with patch.object(recollindex, "container_diagnostics"):
                with patch.object(recollindex, "storage_diagnostics"):
                    with patch.object(recollindex, "print_configuration"):
                        with patch.object(recollindex, "check_existing_indexers", return_value=False):
                            with patch("subprocess.Popen", return_value=mock_proc):
                                with patch("time.sleep"):
                                    result = recollindex.main()
                                    assert result == 0
    finally:
        recollindex.console = orig


def test_main_aborts_on_existing_indexer() -> None:
    """Main returns 2 when indexer already running."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        with patch.object(recollindex, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "hostname\n", "")):
            with patch.object(recollindex, "container_diagnostics"):
                with patch.object(recollindex, "storage_diagnostics"):
                    with patch.object(recollindex, "print_configuration"):
                        with patch.object(recollindex, "check_existing_indexers", return_value=True):
                            result = recollindex.main()
                            assert result == 2
    finally:
        recollindex.console = orig


def test_main_rebuild_cancelled() -> None:
    """Main returns 0 when rebuild is cancelled."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        with patch.object(recollindex, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "hostname\n", "")):
            with patch.object(recollindex, "container_diagnostics"):
                with patch.object(recollindex, "storage_diagnostics"):
                    with patch.object(recollindex, "print_configuration"):
                        with patch.object(recollindex, "check_existing_indexers", return_value=False):
                            with patch.object(recollindex, "confirm_rebuild", return_value=False):
                                with patch.object(sys, "argv", ["recollindex.py", "--rebuild"]):
                                    result = recollindex.main()
                                    assert result == 0
    finally:
        recollindex.console = orig


def test_main_rebuild_success() -> None:
    """Main runs full rebuild and returns exit code."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        mock_proc = _make_mock_proc(0)

        with patch.object(recollindex, "run_cmd", return_value=subprocess.CompletedProcess([], 0, "hostname\n", "")):
            with patch.object(recollindex, "container_diagnostics"):
                with patch.object(recollindex, "storage_diagnostics"):
                    with patch.object(recollindex, "print_configuration"):
                        with patch.object(recollindex, "check_existing_indexers", return_value=False):
                            with patch.object(recollindex, "confirm_rebuild", return_value=True):
                                with patch("subprocess.Popen", return_value=mock_proc):
                                    with patch("time.sleep"):
                                        with patch.object(sys, "argv", ["recollindex.py", "--rebuild"]):
                                            result = recollindex.main()
                                            assert result == 0
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# _locked_main
# ---------------------------------------------------------------------------


def test_locked_main_success() -> None:
    """_locked_main runs main with file lock."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            with patch.object(recollindex, "LOCK_FILE", tmp_path):
                with patch.object(recollindex, "main", return_value=0):
                    result = recollindex._locked_main()
                    assert result == 0
        finally:
            os.unlink(tmp_path)
    finally:
        recollindex.console = orig


def test_locked_main_lock_file_os_error() -> None:
    """_locked_main handles lock file creation failure."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        with patch("builtins.open", side_effect=OSError("no perm")):
            result = recollindex._locked_main()
            assert result == 1
    finally:
        recollindex.console = orig


def test_locked_main_exception_handling() -> None:
    """_locked_main catches and reports exceptions."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        with tempfile.NamedTemporaryFile(delete=False) as f:
            tmp_path = f.name

        try:
            with patch.object(recollindex, "LOCK_FILE", tmp_path):
                with patch.object(recollindex, "main", side_effect=RuntimeError("boom")):
                    result = recollindex._locked_main()
                    assert result == 1
        finally:
            os.unlink(tmp_path)
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# Constants and configuration
# ---------------------------------------------------------------------------


def test_constants() -> None:
    """Module constants are set correctly."""
    import recollindex

    assert recollindex.CONTAINER == "recoll-engine"
    assert "recoll" in recollindex.LOG_FILE
    assert "recoll.conf" in recollindex.CONFIG_FILE
    assert "xapiandb" in recollindex.INDEX_PATH
    assert recollindex.LOCK_FILE == "/tmp/recollindex-wrapper.lock"


def test_config_file_constant_uses_base_path() -> None:
    """CONFIG_FILE equals BASE_PATH + app-data/recoll/.recoll/recoll.conf."""
    import os

    import recollindex

    expected = os.path.join(
        recollindex.BASE_PATH, "app-data/recoll/.recoll/recoll.conf"
    )
    assert expected == recollindex.CONFIG_FILE


def test_log_file_constant_uses_base_path() -> None:
    """LOG_FILE equals BASE_PATH + app-data/recoll/.recoll/recollindex.log."""
    import os

    import recollindex

    expected = os.path.join(
        recollindex.BASE_PATH, "app-data/recoll/.recoll/recollindex.log"
    )
    assert expected == recollindex.LOG_FILE


def test_container_diagnostics_recoll_version_stderr() -> None:
    """container_diagnostics prints stderr when recoll version command has stderr."""
    import subprocess

    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console
        container = recollindex.CONTAINER

        def side_effect(*args, **_kwargs):
            if len(args) >= 4 and args[0] == "docker" and args[1] == "exec" and args[2] == container and args[3] == "sh":
                return subprocess.CompletedProcess(args, 0, "v1\n", "warning\n")
            return subprocess.CompletedProcess(args, 0, "data\n", "")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            recollindex.container_diagnostics("Test")
            calls = [str(c) for c in fake_console.print.call_args_list]
            assert any("warning" in c for c in calls)
    finally:
        recollindex.console = orig


# ---------------------------------------------------------------------------
# _print_cmd_output — graceful failure handling
# ---------------------------------------------------------------------------


def test_print_cmd_output_success() -> None:
    """_print_cmd_output prints stdout on success."""
    import recollindex

    fake_console = MagicMock()
    result = subprocess.CompletedProcess([], 0, "line1\nline2\n", "")
    recollindex._print_cmd_output("test", result, fake_console)
    assert fake_console.print.call_count == 2


def test_print_cmd_output_failure() -> None:
    """_print_cmd_output prints dim unavailable on failure."""
    import recollindex

    fake_console = MagicMock()
    result = subprocess.CompletedProcess([], 1, "", "Function not implemented")
    recollindex._print_cmd_output("test", result, fake_console)
    fake_console.print.assert_called_once()
    call = fake_console.print.call_args[0][0]
    assert "unavailable" in call
    # Should NOT leak the raw stderr message
    assert "Function not implemented" not in call


def test_print_cmd_output_empty_success() -> None:
    """_print_cmd_output prints nothing on success with empty output."""
    import recollindex

    fake_console = MagicMock()
    result = subprocess.CompletedProcess([], 0, "", "")
    recollindex._print_cmd_output("test", result, fake_console)
    fake_console.print.assert_not_called()


# ---------------------------------------------------------------------------
# storage_diagnostics — failing host utilities (TrueNAS)
# ---------------------------------------------------------------------------


def test_storage_diagnostics_all_commands_fail() -> None:
    """storage_diagnostics handles every command failing (TrueNAS BusyBox env)."""
    import recollindex

    fake_console = MagicMock()
    orig = recollindex.console
    try:
        recollindex.console = fake_console

        def side_effect(*args, **_kwargs):
            return subprocess.CompletedProcess(args, 1, "", "Function not implemented")

        with patch.object(recollindex, "run_cmd", side_effect=side_effect):
            with patch.object(Path, "exists", return_value=False):
                recollindex.storage_diagnostics("Test")
        # Should NOT have printed any "Function not implemented" lines
        calls = [str(c) for c in fake_console.print.call_args_list]
        assert not any("Function not implemented" in c for c in calls)
    finally:
        recollindex.console = orig
