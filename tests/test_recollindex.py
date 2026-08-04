"""Smoke tests for recollindex module."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the wrapper package is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def test_module_imports() -> None:
    """Module imports without error."""
    from recoll_wrapper import recollindex  # noqa: F401
    assert True


def test_pretty_duration() -> None:
    """pretty_duration formats seconds correctly."""
    from recoll_wrapper.recollindex import pretty_duration

    assert pretty_duration(0) == "00h 00m 00s"
    assert pretty_duration(60) == "00h 01m 00s"
    assert pretty_duration(3600) == "01h 00m 00s"
    assert pretty_duration(3661) == "01h 01m 01s"
    assert pretty_duration(3723) == "01h 02m 03s"


def test_datasets_of_interest() -> None:
    """DATASETS_OF_INTEREST contains expected datasets."""
    from recoll_wrapper.recollindex import DATASETS_OF_INTEREST

    assert "lambo/share" in DATASETS_OF_INTEREST
    assert "shuttle/share" in DATASETS_OF_INTEREST
