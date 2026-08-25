"""
G-3 fix (Phase 4B): structural tenant-isolation check.

Audit finding: tenant isolation depended entirely on convention (`tenant_select()`
in this same package) plus code review -- nothing stopped a future PR from writing
`select(SomeTenantScopedModel)` directly, with no `organization_id` filter
anywhere in the statement, and having it compile, type-check, and pass ruff/mypy
cleanly while leaking cross-tenant data.

This module is a static (AST-based) checker, not a runtime guard -- a runtime
guard (e.g. Postgres row-level security, or wrapping every Session) would be a
much larger structural change to a codebase this size, and the audit explicitly
said not to rewrite large working modules unnecessarily. This is Option B from
the remediation brief: a check that fails CI/tests the moment an unscoped query
against a tenant-scoped model is introduced, exercised by
tests/unit/test_tenant_isolation_lint.py.

How it works:
  1. Collect every ORM model class name that has an `organization_id` column
     (from every app/modules/*/models.py file) -- these are "tenant-scoped".
  2. Walk every .py file under app/modules (excluding this file, tenant_query.py,
     and test files) looking for `select(<ModelName>)` calls where ModelName is
     tenant-scoped.
  3. For each match, look at the *entire statement* the call belongs to (using
     end_lineno so multi-line `.where(...)` chains are included) and require one
     of:
       - the literal text `organization_id` appears somewhere in that statement
         (covers the extremely common `select(Model).where(Model.organization_id
         == ...)` pattern used throughout this codebase), or
       - the statement calls `tenant_select(` instead of raw `select(`, or
       - the line the `select(` call starts on carries an explicit
         `# tenant-scope: safe - <reason>` marker, for the legitimate cases where
         a tenant-scoped model is deliberately queried without an org filter
         (e.g. "list every org a user belongs to", keyed by user_id instead).

This does not replace code review, and it does not catch every possible bypass
(e.g. a helper function that swallows the org_id argument entirely). It closes
the specific gap the audit named: a raw, entirely-unscoped query landing with
no signal at all.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path

APP_MODULES_DIR = Path(__file__).resolve().parent.parent / "modules"

_EXEMPT_FILES = {"tenant_query.py"}
_EXEMPT_MARKER = "tenant-scope: safe"


@dataclass(frozen=True)
class Violation:
    path: Path
    lineno: int
    model_name: str
    statement_snippet: str

    def __str__(self) -> str:
        return f"{self.path}:{self.lineno}: raw select({self.model_name}) with no organization_id filter and no exemption marker"


def _collect_tenant_scoped_model_names() -> set[str]:
    names: set[str] = set()
    for models_file in APP_MODULES_DIR.glob("*/models.py"):
        tree = ast.parse(models_file.read_text(), filename=str(models_file))
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                # Matches both `organization_id: Mapped[uuid.UUID] = mapped_column(...)`
                # and legacy `organization_id = Column(...)` styles.
                if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name) and item.target.id == "organization_id":
                    names.add(node.name)
                elif isinstance(item, ast.Assign):
                    for target in item.targets:
                        if isinstance(target, ast.Name) and target.id == "organization_id":
                            names.add(node.name)
    return names


def _statement_source(source_lines: list[str], node: ast.stmt) -> str:
    start = node.lineno - 1
    end = node.end_lineno if node.end_lineno is not None else node.lineno
    return "\n".join(source_lines[start:end])


def find_violations() -> list[Violation]:
    tenant_models = _collect_tenant_scoped_model_names()
    violations: list[Violation] = []

    for py_file in APP_MODULES_DIR.rglob("*.py"):
        if py_file.name in _EXEMPT_FILES or py_file.name.startswith("test_"):
            continue
        source = py_file.read_text()
        source_lines = source.splitlines()
        tree = ast.parse(source, filename=str(py_file))

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "select"):
                continue
            if len(node.args) != 1 or not isinstance(node.args[0], ast.Name):
                continue
            model_name = node.args[0].id
            if model_name not in tenant_models:
                continue

            call_line = source_lines[node.lineno - 1]

            # Walk up to the enclosing statement (Assign/Return/Expr/...) so a
            # `.where(Model.organization_id == ...)` chained on later lines is
            # still seen as part of "this statement". The exemption marker may sit
            # on the call line itself or on a comment line immediately preceding
            # the statement (the natural place for a short justifying comment).
            statement = _enclosing_statement(tree, node)
            stmt_start = statement.lineno if statement else node.lineno
            statement_text = _statement_source(source_lines, statement) if statement else call_line
            # The marker may also sit on a comment line immediately above the
            # statement (rather than inside it), e.g. a short justifying comment
            # placed right before a multi-line `await db.execute(...)` call.
            preceding_comment_lines: list[str] = []
            idx = stmt_start - 2
            while idx >= 0 and source_lines[idx].strip().startswith("#"):
                preceding_comment_lines.append(source_lines[idx])
                idx -= 1

            if _EXEMPT_MARKER in statement_text or any(_EXEMPT_MARKER in line for line in preceding_comment_lines):
                continue
            if "organization_id" in statement_text or "tenant_select(" in statement_text:
                continue

            violations.append(
                Violation(
                    path=py_file.relative_to(APP_MODULES_DIR.parent.parent),
                    lineno=node.lineno,
                    model_name=model_name,
                    statement_snippet=statement_text.strip()[:200],
                )
            )

    return violations


def _enclosing_statement(tree: ast.AST, target: ast.Call) -> ast.stmt | None:
    """Finds the top-level statement (module-body-of-a-function-level statement)
    that contains `target`, by walking every statement in every function/module
    body and checking whether `target` is nested inside it."""
    best: ast.stmt | None = None
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for stmt in body:
            if not isinstance(stmt, ast.stmt):
                continue
            if _contains(stmt, target):
                # Prefer the innermost (smallest span) enclosing statement.
                if best is None or (stmt.end_lineno or stmt.lineno) - stmt.lineno <= (best.end_lineno or best.lineno) - best.lineno:
                    best = stmt
    return best


def _contains(stmt: ast.stmt, target: ast.Call) -> bool:
    for node in ast.walk(stmt):
        if node is target:
            return True
    return False
