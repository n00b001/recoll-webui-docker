"""Deliberately INVALID examples for the type-policy guard test.

This file is excluded from the package-wide policy scan (fixtures/ is not
scanned) and exists so test_type_policy proves the checker actually detects
ambiguous union annotations. Keep it in sync with the expectations there.
"""

from __future__ import annotations


def allowed_optional(value: int | None) -> str | None:
    """Optional style (one concrete type + None) is allowed."""
    return str(value) if value is not None else None


def bad_two_concrete(field: int | str, flag: bool | float) -> None:
    """Two concrete types in one annotation are ambiguous (2 violations)."""
    del field, flag


def bad_nested_and_generic(data: dict[str, int | float]) -> list[int | bytes]:
    """Unions inside subscripts are checked too (2 violations)."""
    return [0] * len(data) if data else []


class BadAnnotated:
    """Class-level annotations are checked as well."""

    attr: int | str = 1
