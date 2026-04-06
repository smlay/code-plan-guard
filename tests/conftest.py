"""Shared fixtures."""

from pathlib import Path

import pytest


@pytest.fixture
def tmp_repo(tmp_path: Path) -> Path:
    (tmp_path / "src" / "pkg").mkdir(parents=True)
    (tmp_path / "src" / "pkg" / "__init__.py").write_text("", encoding="utf-8")
    (tmp_path / "src" / "pkg" / "a.py").write_text(
        "from pkg import b\n",
        encoding="utf-8",
    )
    (tmp_path / "src" / "pkg" / "b.py").write_text("X = 1\n", encoding="utf-8")
    return tmp_path
