"""Type-policy guard: ban ambiguous union annotations in this package.

Policy (see AGENTS.md, "Logging & typing rules"): a parameter, return or
variable annotation must not combine TWO OR MORE concrete types in one
union (``int | str``, ``str | int | bytes``, also inside subscripts such as
``dict[str, int | float]``). If a value can be more than one concrete type,
model the shape explicitly (subclasses with isinstance/TypeGuard narrowing,
a Protocol, or Literal) instead of leaving the ambiguity in the signature.

Optional style — exactly one concrete member plus None (``int | None``) —
stays allowed; that is a documented "may be absent", not an ambiguous type.

Neither ruff nor ty has a rule for this, so it is enforced here by walking
the AST of every Python file in the package (tests/fixtures excluded).
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
FIXTURE_FILE = PACKAGE_ROOT / "tests" / "fixtures" / "ambiguous_types.py"
EXCLUDED_DIRS = {".venv", "__pycache__", "fixtures"}


def _iter_python_files() -> list[Path]:
    """All package Python files subject to the policy scan."""
    return sorted(
        p
        for p in PACKAGE_ROOT.rglob("*.py")
        if not any(part in EXCLUDED_DIRS for part in p.relative_to(PACKAGE_ROOT).parts)
    )


def _is_none_type(node: ast.expr) -> bool:
    """True for the None/NoneType leaf of a union.

    PEP 604 parses ``X | None`` as Name('int') | Constant(None) on modern
    CPython, so both spellings are recognised.
    """
    if isinstance(node, ast.Name):
        return node.id in ("None", "NoneType")
    return isinstance(node, ast.Constant) and node.value is None


def _flatten_union_leaves(node: ast.expr) -> list[ast.expr]:
    """Flatten nested ``a | b | c`` chains into their member expressions."""
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.BitOr):
        return _flatten_union_leaves(node.left) + _flatten_union_leaves(node.right)
    return [node]


def _annotation_nodes(tree: ast.Module) -> Iterator[ast.expr]:
    """Yield every annotation expression in the tree."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            all_args: list[ast.arg] = [*node.args.args, *node.args.kwonlyargs]
            vararg = node.args.vararg
            if vararg is not None:
                all_args.append(vararg)
            for arg in all_args:
                if arg.annotation is not None:
                    yield arg.annotation
            kwarg = node.args.kwarg
            if kwarg is not None and kwarg.annotation is not None:
                yield kwarg.annotation
            if node.returns is not None:
                yield node.returns
        elif isinstance(node, ast.AnnAssign) and node.annotation is not None:
            yield node.annotation


def find_violations(path: Path) -> list[tuple[int, str]]:
    """Return ``(line_number, source_line)`` pairs that break the policy."""
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(path))
    lines = source.splitlines()

    parents: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node

    violations: list[tuple[int, str]] = []
    for annotation in _annotation_nodes(tree):
        # Only top-level union chains (a union whose parent is another union
        # is part of a larger chain and reported once at the outermost level).
        top_unions: list[ast.BinOp] = []
        for candidate in ast.walk(annotation):
            if not isinstance(candidate, ast.BinOp) or not isinstance(
                candidate.op, ast.BitOr
            ):
                continue
            parent = parents.get(candidate)
            if isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.BitOr):
                continue
            top_unions.append(candidate)
        for union in top_unions:
            members = _flatten_union_leaves(union)
            concrete = [m for m in members if not _is_none_type(m)]
            if len(concrete) >= 2:
                violations.append((union.lineno, lines[union.lineno - 1].strip()))

    return sorted(violations, key=lambda item: item[0])


def test_no_ambiguous_unions_in_package() -> None:
    """No production or test file may annotate two concrete types in a union."""
    all_violations: dict[str, list[tuple[int, str]]] = {}
    for file_path in _iter_python_files():
        found = find_violations(file_path)
        if found:
            all_violations[str(file_path.relative_to(PACKAGE_ROOT))] = found

    assert not all_violations, (
        "Ambiguous union types found (two or more concrete members; model the "
        "type explicitly instead — see AGENTS.md):\n"
        + "\n".join(
            f"  {rel_path}:{line} -> {text}"
            for rel_path, items in all_violations.items()
            for line, text in items
        )
    )


def test_checker_detects_fixture_violations() -> None:
    """The checker must catch the known-bad fixture (exactly 5 violations)."""
    found = find_violations(FIXTURE_FILE)
    flagged_lines = {line for line, _ in found}

    assert len(found) == 5

    source_lines = FIXTURE_FILE.read_text(encoding="utf-8").splitlines()

    def line_of(marker: str) -> int:
        return next(i + 1 for i, ln in enumerate(source_lines) if marker in ln)

    # The allowed optional annotation must NOT be flagged.
    assert line_of("def allowed_optional") not in flagged_lines
    # Both unions in the two-concrete signature are reported (same line).
    assert line_of("def bad_two_concrete") in flagged_lines
    # Subscript and return-annotation unions are reported too.
    assert line_of("def bad_nested_and_generic") in flagged_lines
    # Class-level annotation is reported.
    assert line_of("attr: int | str") in flagged_lines
