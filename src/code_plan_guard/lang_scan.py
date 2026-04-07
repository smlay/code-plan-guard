"""v0.3 experimental language scan (warning-only, heuristic)."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from code_plan_guard.paths import normalize_under_repo


_JS_IMPORT = re.compile(r"""import\s+.*?\s+from\s+['"](.+?)['"]""")
_JS_SIDE_EFFECT_IMPORT = re.compile(r"""^\s*import\s+['"](.+?)['"]\s*;?\s*$""")
_JS_REQUIRE = re.compile(r"""require\(\s*['"](.+?)['"]\s*\)""")


def scan_js_ts_imports(repo: Path, changed_files: list[str]) -> list[dict[str, Any]]:
    """
    Scan .js/.ts/.tsx/.jsx changed files for import/require targets.
    Only records relative paths ('./' or '../') as evidence.
    """
    out: list[dict[str, Any]] = []
    for rel in changed_files:
        if not rel.endswith((".js", ".jsx", ".ts", ".tsx")):
            continue
        p = repo / rel
        try:
            text = p.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            target = ""
            m = _JS_SIDE_EFFECT_IMPORT.match(line)
            if m:
                target = m.group(1)
            else:
                m2 = _JS_IMPORT.search(line)
                if m2:
                    target = m2.group(1)
                else:
                    rm = _JS_REQUIRE.search(line)
                    target = rm.group(1) if rm else ""
            if not target or not (target.startswith("./") or target.startswith("../")):
                continue
            # Resolve best-effort to a repo-relative path (existence not required)
            cand = str((Path(rel).parent / target).as_posix())
            norm, _ = normalize_under_repo(repo, cand, must_be_file=False)
            out.append(
                {
                    "source": "lang_scan",
                    "language": "js/ts",
                    "code": "W_LANG_IMPORT",
                    "path": rel,
                    "import_target": target,
                    "resolved_candidate": norm or cand,
                }
            )
    return out

