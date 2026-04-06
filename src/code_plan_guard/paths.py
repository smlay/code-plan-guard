"""§7 path normalization and B02."""

from __future__ import annotations

import os
from pathlib import Path


def is_b01_empty_or_absolute(s: str) -> bool:
    """§7.1 — empty or absolute plan path string → B01."""
    if not s or not s.strip():
        return True
    return Path(s).is_absolute()


def normalize_under_repo(
    repo: Path, s: str, *, must_be_file: bool
) -> tuple[str | None, str | None]:
    """
    §7.1 — return (posix_rel, None) or (None, error_tag).
    must_be_file=True for changes[].file (B02 if not file).
    must_be_file=False for impacted_files / exception paths (existence not required).
    """
    s = s.strip()
    if not s:
        return None, "empty_path"
    if Path(s).is_absolute():
        return None, "absolute_path"
    joined = os.path.normpath(os.path.join(os.fspath(repo.resolve()), s))
    try:
        real = Path(os.path.realpath(joined))
    except OSError:
        return None, "resolve_failed"
    repo_real = Path(os.path.realpath(os.fspath(repo.resolve())))
    try:
        rel = real.relative_to(repo_real)
    except ValueError:
        return None, "outside_repo"
    posix = rel.as_posix()
    if must_be_file:
        if not real.is_file():
            return None, "not_a_file"
    return posix, None


def normalize_optional_plan_paths(repo: Path, paths: list[str] | None) -> set[str]:
    """Normalize impacted-like paths; skip invalid."""
    out: set[str] = set()
    if not paths:
        return out
    for p in paths:
        r, _err = normalize_under_repo(repo, p, must_be_file=False)
        if r is not None:
            out.add(r)
    return out
