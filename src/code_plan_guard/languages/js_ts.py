from __future__ import annotations

from pathlib import Path

from code_plan_guard.lang_scan import scan_js_ts_imports
from code_plan_guard.languages.base import LangEdge, LangWarning


class JsTsPlugin:
    name = "js_ts"

    def analyze(self, repo: Path, changed_files: list[str]) -> tuple[list[LangEdge], list[LangWarning]]:
        edges: list[LangEdge] = []
        warns: list[LangWarning] = []
        try:
            rows = scan_js_ts_imports(repo, changed_files)
        except Exception as e:
            warns.append(
                LangWarning(
                    code="W_LANG_PLUGIN_FAILED",
                    message=f"js/ts 插件执行失败：{e}",
                    details={},
                    language="js/ts",
                    source="lang_scan",
                )
            )
            return edges, warns
        for r in rows:
            frm = str(r.get("path", ""))
            to = str(r.get("resolved_candidate", ""))
            if frm and to:
                edges.append(LangEdge(from_file=frm, to_file=to, language="js/ts", source="lang_scan"))
        # Promote scan issues as warnings only (truth already contains them).
        for r in rows[:200]:
            warns.append(
                LangWarning(
                    code=str(r.get("code", "W_LANG_IMPORT")),
                    message=f"{r.get('path')} imports {r.get('import_target')}",
                    details=r,
                    language="js/ts",
                    source="lang_scan",
                )
            )
        return edges, warns

