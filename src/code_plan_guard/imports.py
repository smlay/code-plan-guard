"""§8 static import analysis and expected_impact."""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from code_plan_guard.config import GuardConfig


def is_protected_if_test(node: ast.If, cfg: GuardConfig) -> tuple[bool, bool]:
    """
    Returns (is_false_branch, is_type_checking) which are independent flags
    for skip config (both use same body-skipping behavior when enabled).
    """
    t = node.test
    is_false = isinstance(t, ast.Constant) and t.value is False
    is_tc = (
        cfg.skip_imports_in_type_checking_if
        and isinstance(t, ast.Name)
        and t.id == "TYPE_CHECKING"
    )
    is_false_cfg = cfg.skip_imports_in_false_branch and is_false
    return is_false_cfg, is_tc and cfg.skip_imports_in_type_checking_if


def should_skip_direct_imports(node: ast.If, cfg: GuardConfig) -> bool:
    f, tc = is_protected_if_test(node, cfg)
    return f or tc


def _resolve_absolute_module(module: str, repo: Path, src_root_paths: list[Path]) -> str | None:
    """§8.2.1 — return posix rel path or None."""
    parts = module.split(".")
    rel_dir = Path(*parts) if parts else Path()
    for root in src_root_paths:
        candidate_py = root / rel_dir.with_suffix(".py")
        if candidate_py.is_file():
            try:
                return candidate_py.resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                continue
        candidate_pkg = root / rel_dir / "__init__.py"
        if candidate_pkg.is_file():
            try:
                return candidate_pkg.resolve().relative_to(repo.resolve()).as_posix()
            except ValueError:
                continue
    return None


def _resolve_under_anchor(anchor: Path, parts: list[str], repo: Path) -> str | None:
    if not parts:
        return None
    rel_dir = Path(*parts)
    cur = anchor / rel_dir
    py = cur.with_suffix(".py")
    if py.is_file():
        try:
            return py.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return None
    init_f = cur / "__init__.py"
    if init_f.is_file():
        try:
            return init_f.resolve().relative_to(repo.resolve()).as_posix()
        except ValueError:
            return None
    return None


def _src_roots(repo: Path, cfg: GuardConfig) -> list[Path]:
    roots: list[Path] = []
    for s in cfg.src_roots:
        p = (repo / s).resolve()
        if p.is_dir():
            roots.append(p)
    if not roots:
        roots.append(repo.resolve())
    return roots


def analyze_py_file(
    repo: Path,
    file_rel: str,
    cfg: GuardConfig,
) -> tuple[list[tuple[str, str]], list[str], list[dict[str, Any]]]:
    """
    Returns:
      edges: (from_file, to_file) posix
      unresolved: module strings
      warnings: {code, message, details}
    """
    path = repo / file_rel
    warnings: list[dict[str, Any]] = []
    edges: list[tuple[str, str]] = []
    unresolved: list[str] = []

    try:
        source = path.read_text(encoding="utf-8")
    except OSError:
        return edges, unresolved, warnings

    try:
        tree = ast.parse(source, filename=str(path))
    except SyntaxError as e:
        warnings.append(
            {
                "code": "SYNTAX_ERROR",
                "message": f"AST 解析失败：{e}",
                "details": {"file": file_rel, "lineno": e.lineno},
            }
        )
        return edges, unresolved, warnings

    src_roots = _src_roots(repo, cfg)

    def handle_import(node: ast.Import) -> None:
        for alias in node.names:
            name = alias.name
            resolved = _resolve_absolute_module(name, repo, src_roots)
            if resolved:
                edges.append((file_rel, resolved))
            else:
                unresolved.append(name)

    def handle_import_from(node: ast.ImportFrom) -> None:
        if node.module == "*" or (node.names and any(n.name == "*" for n in node.names)):
            warnings.append(
                {
                    "code": "W_STAR_IMPORT",
                    "message": "import * 未展开",
                    "details": {"file": file_rel, "lineno": getattr(node, "lineno", None)},
                }
            )
            return
        if node.level == 0:
            assert node.module is not None
            base_mod = node.module
            for alias in node.names:
                sub = f"{base_mod}.{alias.name}"
                resolved = _resolve_absolute_module(sub, repo, src_roots)
                if resolved:
                    edges.append((file_rel, resolved))
                else:
                    if not _resolve_absolute_module(base_mod, repo, src_roots):
                        unresolved.append(sub)
        else:
            cur_file = (repo / file_rel).resolve()
            anchor = cur_file.parent
            for _ in range(node.level - 1):
                anchor = anchor.parent
            base_parts = node.module.split(".") if node.module else []
            for alias in node.names:
                parts = base_parts + [alias.name]
                r = _resolve_under_anchor(anchor, parts, repo)
                if r:
                    edges.append((file_rel, r))
                else:
                    unresolved.append(".".join(parts) if parts else alias.name)

    def visit_stmt_list(stmts: list[ast.stmt], skip_direct_imports: bool) -> None:
        for st in stmts:
            if skip_direct_imports and isinstance(st, (ast.Import, ast.ImportFrom)):
                continue
            if isinstance(st, ast.Import):
                handle_import(st)
            elif isinstance(st, ast.ImportFrom):
                handle_import_from(st)
            elif isinstance(st, ast.If):
                prot = should_skip_direct_imports(st, cfg)
                visit_stmt_list(st.body, skip_direct_imports=prot)
                visit_stmt_list(st.orelse, skip_direct_imports=False)
            elif isinstance(st, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                visit_stmt_list(st.body, skip_direct_imports=False)
                for dec in getattr(st, "decorator_list", []) or []:
                    pass
            elif isinstance(st, ast.Try):
                visit_stmt_list(st.body, skip_direct_imports=False)
                for h in st.handlers:
                    visit_stmt_list(h.body, skip_direct_imports=False)
                visit_stmt_list(st.orelse, skip_direct_imports=False)
                visit_stmt_list(st.finalbody, skip_direct_imports=False)
            elif isinstance(st, (ast.For, ast.AsyncFor, ast.While, ast.With)):
                visit_stmt_list(getattr(st, "body", []), skip_direct_imports=False)
                visit_stmt_list(getattr(st, "orelse", []), skip_direct_imports=False)
            elif isinstance(st, ast.Match):
                for case in st.cases:
                    visit_stmt_list(case.body, skip_direct_imports=False)

    visit_stmt_list(tree.body, skip_direct_imports=False)

    for mod in sorted(set(unresolved)):
        warnings.append(
            {
                "code": "W_UNRESOLVED_IMPORT",
                "message": f"未解析模块：{mod}",
                "details": {"module": mod, "from_file": file_rel},
            }
        )

    return edges, unresolved, warnings


def build_expected_impact(
    repo: Path,
    changed_py_files: list[str],
    cfg: GuardConfig,
) -> tuple[dict[str, Any], list[dict[str, Any]], list[tuple[str, str]]]:
    """§8.3 JSON-shaped dict + warnings + all edges for reconciliation."""
    per_file: dict[str, Any] = {}
    all_edges: list[tuple[str, str]] = []
    all_warn: list[dict[str, Any]] = []
    aggregated: set[str] = set()

    for rel in sorted(changed_py_files):
        edges, unres, w = analyze_py_file(repo, rel, cfg)
        all_warn.extend(w)
        targets = sorted({t for _f, t in edges})
        per_file[rel] = {"one_hop_targets": targets, "unresolved_imports": sorted(set(unres))}
        all_edges.extend(edges)
        aggregated.update(targets)

    edge_count = len(all_edges)
    unresolved_count = sum(len(per_file[f]["unresolved_imports"]) for f in per_file)
    out = {
        "schema_version": "0.1",
        "changed_files": sorted(changed_py_files),
        "normalization": "posix_relative_under_repo",
        "per_file": per_file,
        "aggregated_one_hop": sorted(aggregated),
        "stats": {
            "edge_count": edge_count,
            "unresolved_count": unresolved_count,
            "changed_py_count": len(changed_py_files),
        },
    }
    return out, all_warn, all_edges
