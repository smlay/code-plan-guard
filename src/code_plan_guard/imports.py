"""§8 static import analysis and expected_impact."""

from __future__ import annotations

import ast
import hashlib
import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
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

    # File-level cache (best-effort). Key includes file content + config-relevant flags.
    cache_path: Path | None = None
    if cfg.cache_enabled:
        try:
            data = path.read_bytes()
            fp = hashlib.sha256(data).hexdigest()
            cblob = json.dumps(
                {
                    "file": file_rel,
                    "fp": fp,
                    "src_roots": cfg.src_roots,
                    "skip_false": cfg.skip_imports_in_false_branch,
                    "skip_tc": cfg.skip_imports_in_type_checking_if,
                },
                sort_keys=True,
            )
            key = hashlib.sha256(cblob.encode()).hexdigest()
            cache_path = cfg.resolved_cache_dir() / "file" / f"{key}.json"
            if cache_path.is_file():
                raw = json.loads(cache_path.read_text(encoding="utf-8"))
                e = [tuple(x) for x in raw.get("edges", [])]
                u = list(raw.get("unresolved", []))
                w = list(raw.get("warnings", []))
                return e, u, w
        except Exception:
            cache_path = None

    try:
        if path.is_file() and path.stat().st_size > cfg.perf_max_file_bytes:
            warnings.append(
                {
                    "code": "W_FILE_TOO_LARGE_SKIPPED",
                    "message": f"文件过大已跳过 AST 解析：{file_rel}",
                    "details": {
                        "file": file_rel,
                        "size_bytes": path.stat().st_size,
                        "max_file_bytes": cfg.perf_max_file_bytes,
                    },
                }
            )
            return edges, unresolved, warnings
    except OSError:
        pass

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

    if cache_path is not None:
        try:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(
                    {
                        "schema_version": "0.1",
                        "edges": [list(x) for x in edges],
                        "unresolved": sorted(set(unresolved)),
                        "warnings": warnings,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception:
            pass

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

    rels = sorted(changed_py_files)
    results: dict[str, tuple[list[tuple[str, str]], list[str], list[dict[str, Any]]]] = {}

    def _analyze_many(files: list[str]) -> None:
        if not files:
            return
        max_workers = min(32, (os.cpu_count() or 4) + 4)
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(analyze_py_file, repo, rel, cfg): rel for rel in files}
            for fut in as_completed(futs):
                rel = futs[fut]
                results[rel] = fut.result()

    _analyze_many(rels)

    # Deterministic aggregation + perf edge cap
    edge_cap = int(cfg.perf_max_edges)
    analyzed: list[str] = []
    for rel in rels:
        edges, unres, w = results.get(rel, ([], [], []))
        all_warn.extend(w)
        targets = sorted({t for _f, t in edges})
        per_file[rel] = {"one_hop_targets": targets, "unresolved_imports": sorted(set(unres))}
        if edge_cap > 0 and (len(all_edges) + len(edges)) > edge_cap:
            all_warn.append(
                {
                    "code": "W_TOO_MANY_EDGES",
                    "message": "边数量超过阈值，已截断后续边（确定性）。",
                    "details": {"max_edges": edge_cap},
                }
            )
            remain = max(0, edge_cap - len(all_edges))
            all_edges.extend(edges[:remain])
            aggregated.update({t for _f, t in edges[:remain]})
            break
        all_edges.extend(edges)
        aggregated.update(targets)
        analyzed.append(rel)

    # Optional hop expansion (>1): adds edges for additional analyzed files.
    hop_depth = max(1, int(getattr(cfg, "hop_depth", 1) or 1))
    if hop_depth > 1:
        # Only expand to python files under repo; deterministic frontier.
        seen_files = set(analyzed)
        frontier: list[str] = sorted({t for t in aggregated if t.endswith(".py") and t not in seen_files})
        max_files = int(cfg.perf_max_changed_files) if int(cfg.perf_max_changed_files) > 0 else 200

        cur_depth = 1
        aggregated_multi: set[str] = set(aggregated)
        while cur_depth < hop_depth and frontier:
            # bound analysis set deterministically
            remaining_budget = max(0, max_files - len(seen_files))
            if remaining_budget <= 0:
                all_warn.append(
                    {
                        "code": "W_HOP_DEPTH_DEGRADED",
                        "message": "hop_depth 扩展已降级：分析文件数量超过阈值。",
                        "details": {"hop_depth": hop_depth, "max_files": max_files},
                    }
                )
                break
            batch = frontier[:remaining_budget]
            _analyze_many(batch)

            next_frontier: set[str] = set()
            for rel in batch:
                seen_files.add(rel)
                edges, unres, w = results.get(rel, ([], [], []))
                all_warn.extend(w)
                targets = sorted({t for _f, t in edges})
                per_file.setdefault(rel, {"one_hop_targets": [], "unresolved_imports": []})
                per_file[rel]["one_hop_targets"] = sorted(set(per_file[rel]["one_hop_targets"]) | set(targets))
                per_file[rel]["unresolved_imports"] = sorted(
                    set(per_file[rel]["unresolved_imports"]) | set(unres)
                )

                # edge cap still applies
                if edge_cap > 0 and (len(all_edges) + len(edges)) > edge_cap:
                    all_warn.append(
                        {
                            "code": "W_TOO_MANY_EDGES",
                            "message": "边数量超过阈值，已截断后续边（确定性）。",
                            "details": {"max_edges": edge_cap},
                        }
                    )
                    remain = max(0, edge_cap - len(all_edges))
                    all_edges.extend(edges[:remain])
                    aggregated_multi.update({t for _f, t in edges[:remain]})
                    frontier = []
                    break
                all_edges.extend(edges)
                aggregated_multi.update(targets)
                for t in targets:
                    if t.endswith(".py") and t not in seen_files:
                        next_frontier.add(t)

            if not frontier:
                # may have been truncated by edge cap
                break
            frontier = sorted(next_frontier)
            cur_depth += 1

        aggregated = aggregated_multi

    edge_count = len(all_edges)
    unresolved_count = sum(len(per_file[f]["unresolved_imports"]) for f in per_file)
    out = {
        "schema_version": "0.1",
        "changed_files": sorted(changed_py_files),
        "normalization": "posix_relative_under_repo",
        "per_file": per_file,
        "aggregated_one_hop": sorted(aggregated),
        "analysis": {"hop_depth": hop_depth, "analyzed_files": sorted(set(per_file.keys()))},
        "stats": {
            "edge_count": edge_count,
            "unresolved_count": unresolved_count,
            "changed_py_count": len(changed_py_files),
        },
    }
    return out, all_warn, all_edges
