"""§13.2 cache for expected_impact."""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from code_plan_guard.config import GuardConfig, config_for_cache_hash
from code_plan_guard.constants import __version__


def _file_fingerprint(path: Path) -> str:
    try:
        data = path.read_bytes()
        return hashlib.sha256(data).hexdigest()
    except OSError:
        st = path.stat()
        return f"mtime:{st.st_mtime_ns}:size:{st.st_size}"


def cache_key(
    repo: Path,
    cfg: GuardConfig,
    changed_py_rels: list[str],
) -> str:
    parts: list[str] = [
        f"tool={__version__}",
        f"py={sys.version_info[:3]}",
        f"cfg={hashlib.sha256(config_for_cache_hash(cfg).encode()).hexdigest()}",
        "hop_depth=1",
    ]
    for rel in sorted(changed_py_rels):
        p = repo / rel
        parts.append(f"{rel}\0{_file_fingerprint(p)}")
    blob = "|".join(parts)
    return hashlib.sha256(blob.encode()).hexdigest()


def cache_paths(cache_dir: Path, key: str) -> Path:
    return cache_dir / f"{key}.json"


def load_cache(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def save_cache(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")
