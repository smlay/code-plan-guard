"""v0.3 helpers: GitHub PR plan/override discovery and richer audits."""

from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from code_plan_guard.result import WarningItem


_OVERRIDE_RE = re.compile(
    r"code-plan-guard:\s*override\s+(B\d{2})\s+reason=(.+?)(?:\s+sha=([0-9a-f]{7,40}))?\s*$",
    re.IGNORECASE,
)

_OVERRIDE_BLOCK = re.compile(
    r"```(?:override|code-plan-guard)\s*\n(.*?)\n```", re.IGNORECASE | re.DOTALL
)


@dataclass(frozen=True)
class OverrideDirective:
    blocker_id: str
    reason: str
    sha: str | None
    raw: str
    source_type: str  # file|pr_body|issue_comment|review_comment|unknown
    source_ref: str   # path or url/id
    author: str | None = None
    created_at: str | None = None


def parse_overrides_from_text(
    text: str,
    *,
    source_type: str,
    source_ref: str,
    author: str | None = None,
    created_at: str | None = None,
) -> list[OverrideDirective]:
    def _parse_lines(blob: str) -> list[OverrideDirective]:
        rows: list[OverrideDirective] = []
        for raw in (blob or "").splitlines():
            m = _OVERRIDE_RE.search(raw.strip())
            if not m:
                continue
            rows.append(
                OverrideDirective(
                    blocker_id=m.group(1).upper(),
                    reason=m.group(2).strip(),
                    sha=(m.group(3) or None),
                    raw=raw.strip(),
                    source_type=source_type,
                    source_ref=source_ref,
                    author=author,
                    created_at=created_at,
                )
            )
        return rows

    blocks = list(_OVERRIDE_BLOCK.finditer(text or ""))
    if blocks:
        out: list[OverrideDirective] = []
        for m in blocks:
            out.extend(_parse_lines(m.group(1)))
        return out
    return _parse_lines(text)


def overrides_from_file(path: Path | None) -> list[OverrideDirective]:
    if path is None or not path.is_file():
        return []
    text = path.read_text(encoding="utf-8", errors="ignore")
    return parse_overrides_from_text(text, source_type="file", source_ref=str(path))


def plan_path_from_pr_body(body: str) -> str | None:
    """
    Parse plan reference from PR body.
    Supported:
      - 'plan: path/to/plan.yaml'
      - markdown link: [plan](path/to/plan.yaml)
    """
    if not body:
        return None
    for line in body.splitlines():
        s = line.strip()
        if s.lower().startswith("plan:"):
            return s.split(":", 1)[1].strip()
    m = re.search(r"\[plan\]\(([^)]+)\)", body, flags=re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def _gh_api(repo: Path, args: list[str]) -> tuple[dict[str, Any] | list[Any] | None, str | None]:
    """Best-effort `gh api` wrapper. Returns (json, error_message)."""
    try:
        proc = subprocess.run(
            ["gh", "api", *args],
            cwd=repo,
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired) as e:
        return None, f"gh 调用失败：{e}"
    if proc.returncode != 0:
        msg = (proc.stderr or proc.stdout or "").strip()
        return None, f"gh api 返回非 0：{msg}"
    try:
        return json.loads(proc.stdout), None
    except json.JSONDecodeError as e:
        return None, f"gh 输出非 JSON：{e}"


def overrides_from_github_pr(repo: Path) -> tuple[list[OverrideDirective], list[WarningItem]]:
    """
    Read PR body + issue comments via `gh api`.
    Requires GITHUB_TOKEN and a PR context. Failure is warning-only.
    """
    warns: list[WarningItem] = []
    pr = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if not pr or not repo_full:
        return [], []

    pr_json, err = _gh_api(repo, [f"repos/{repo_full}/pulls/{pr}"])
    if pr_json is None or not isinstance(pr_json, dict):
        if err:
            warns.append(WarningItem(code="W_GITHUB_OVERRIDE_FETCH", message=err, details={}))
        return [], warns

    out: list[OverrideDirective] = []
    body = str(pr_json.get("body") or "")
    actor = os.environ.get("GITHUB_ACTOR") or None
    out.extend(
        parse_overrides_from_text(
            body, source_type="pr_body", source_ref=f"pr:{pr}", author=actor, created_at=None
        )
    )

    comments_json, err2 = _gh_api(repo, [f"repos/{repo_full}/issues/{pr}/comments"])
    if comments_json is None:
        if err2:
            warns.append(WarningItem(code="W_GITHUB_OVERRIDE_FETCH", message=err2, details={}))
        return out, warns

    if isinstance(comments_json, list):
        for c in comments_json:
            if not isinstance(c, dict):
                continue
            txt = str(c.get("body") or "")
            author = None
            u = c.get("user")
            if isinstance(u, dict):
                author = str(u.get("login") or "")
            created_at = str(c.get("created_at") or "")
            cid = str(c.get("id") or "")
            out.extend(
                parse_overrides_from_text(
                    txt,
                    source_type="issue_comment",
                    source_ref=f"comment:{cid}",
                    author=author,
                    created_at=created_at,
                )
            )

    return out, warns


def overrides_from_github_review_comments(repo: Path) -> tuple[list[OverrideDirective], list[WarningItem]]:
    """
    Fetch PR review comments via GitHub API:
      GET /repos/{owner}/{repo}/pulls/{pull_number}/comments
    """
    warns: list[WarningItem] = []
    pr = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if not pr or not repo_full:
        return [], []
    data, err = _gh_api(repo, [f"repos/{repo_full}/pulls/{pr}/comments"])
    if data is None:
        if err:
            warns.append(WarningItem(code="W_GITHUB_OVERRIDE_FETCH", message=err, details={}))
        return [], warns
    out: list[OverrideDirective] = []
    if isinstance(data, list):
        for c in data:
            if not isinstance(c, dict):
                continue
            txt = str(c.get("body") or "")
            author = None
            u = c.get("user")
            if isinstance(u, dict):
                author = str(u.get("login") or "")
            created_at = str(c.get("created_at") or "")
            cid = str(c.get("id") or "")
            out.extend(
                parse_overrides_from_text(
                    txt,
                    source_type="review_comment",
                    source_ref=f"review_comment:{cid}",
                    author=author,
                    created_at=created_at,
                )
            )
    return out, warns


def labels_from_github_pr(repo: Path) -> tuple[list[str], list[WarningItem]]:
    warns: list[WarningItem] = []
    pr = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if not pr or not repo_full:
        return [], []
    data, err = _gh_api(repo, [f"repos/{repo_full}/issues/{pr}/labels"])
    if data is None:
        if err:
            warns.append(WarningItem(code="W_GITHUB_LABEL_FETCH", message=err, details={}))
        return [], warns
    out: list[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("name"):
                out.append(str(item["name"]))
    return out, warns


def members_of_team(repo: Path, org_team: str) -> tuple[set[str], list[WarningItem]]:
    """
    Best-effort resolve 'org:team' members via gh api.
    Failure => warning-only and returns empty set.
    """
    warns: list[WarningItem] = []
    if ":" not in org_team:
        return set(), []
    org, team = org_team.split(":", 1)
    data, err = _gh_api(repo, [f"orgs/{org}/teams/{team}/members"])
    if data is None:
        if err:
            warns.append(WarningItem(code="W_GITHUB_TEAM_FETCH", message=err, details={"team": org_team}))
        return set(), warns
    out: set[str] = set()
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and item.get("login"):
                out.add(str(item["login"]))
    return out, warns


def fetch_pr_body(repo: Path) -> tuple[str | None, list[WarningItem]]:
    warns: list[WarningItem] = []
    pr = os.environ.get("GITHUB_PR_NUMBER") or os.environ.get("PR_NUMBER")
    repo_full = os.environ.get("GITHUB_REPOSITORY")
    if not pr or not repo_full:
        return None, []
    pr_json, err = _gh_api(repo, [f"repos/{repo_full}/pulls/{pr}"])
    if pr_json is None or not isinstance(pr_json, dict):
        if err:
            warns.append(WarningItem(code="W_GITHUB_PLAN_FETCH", message=err, details={}))
        return None, warns
    return str(pr_json.get("body") or ""), warns


def build_override_audit_payload(
    *,
    overrides_applied: list[dict[str, Any]],
    directives: list[OverrideDirective],
    plan_hash: str,
    commit_sha: str,
    blockers_before: list[str],
    blockers_after: list[str],
) -> dict[str, Any]:
    actor = os.environ.get("GITHUB_ACTOR", "local")
    return {
        "schema_version": "0.3",
        "actor": actor,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "commit_sha": commit_sha,
        "plan_hash": plan_hash,
        "blockers_before": blockers_before,
        "blockers_after": blockers_after,
        "directives": [
            {
                "blocker_id": d.blocker_id,
                "reason": d.reason,
                "sha": d.sha,
                "raw": (d.raw[:200] if d.raw else ""),
                "source_type": d.source_type,
                "source_ref": d.source_ref,
                "author": d.author,
                "created_at": d.created_at,
            }
            for d in directives
        ],
        "overrides": overrides_applied,
    }

