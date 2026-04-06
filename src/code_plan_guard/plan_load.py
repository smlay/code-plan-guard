"""§5.2–5.3 plan file loading."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import yaml

from code_plan_guard import messages as msg


def load_plan_raw(plan_path: Path) -> tuple[dict[str, Any] | None, str | None, str | None]:
    """
    Returns (data, fatal_message, error_kind).
    On success: (dict, None, None).
    On failure: (None, message, kind).
    """
    suffix = plan_path.suffix.lower()
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError as e:
        return None, f"无法读取计划文件：{e}", "IO_ERROR"

    if suffix == ".md":
        return _parse_markdown_plan(text)

    if suffix in (".yaml", ".yml"):
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            return None, f"YAML 解析失败：{e}", "CONFIG_ERROR"
        if not isinstance(data, dict):
            return None, "YAML 根节点必须是对象", "CONFIG_ERROR"
        return data, None, None

    if suffix == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            return None, f"JSON 解析失败：{e}", "CONFIG_ERROR"
        if not isinstance(data, dict):
            return None, "JSON 根节点必须是对象", "CONFIG_ERROR"
        return data, None, None

    return None, f"不支持的计划扩展名：{suffix}", "CONFIG_ERROR"


_FENCE = re.compile(
    r"^```\s*(yaml|yml)\s*\n(.*?)^```\s*$",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


def _parse_markdown_plan(text: str) -> tuple[dict[str, Any] | None, str | None, str | None]:
    matches = list(_FENCE.finditer(text))
    if not matches:
        return None, msg.MD01, "MD_PARSE"
    if len(matches) >= 2:
        return None, msg.MD02, "MD_PARSE"
    body = matches[0].group(2)
    try:
        data = yaml.safe_load(body)
    except yaml.YAMLError as e:
        return None, f"Markdown 内 YAML 解析失败：{e}", "CONFIG_ERROR"
    if not isinstance(data, dict):
        return None, "Markdown 内 YAML 根节点必须是对象", "CONFIG_ERROR"
    return data, None, None
