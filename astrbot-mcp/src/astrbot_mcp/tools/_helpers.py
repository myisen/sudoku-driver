"""Shared helpers for AstrBot MCP tools."""

from __future__ import annotations

import json
from typing import Any

# Cap the text returned by a single tool call so huge payloads
# (e.g. log buffers or market listings) don't blow up the context.
MAX_OUTPUT_CHARS = 20_000


def json_out(data: Any, max_chars: int = MAX_OUTPUT_CHARS) -> str:
    """Serialize ``data`` to compact JSON, truncating with a notice if too long."""
    text = json.dumps(data, ensure_ascii=False, default=str)
    if len(text) <= max_chars:
        return text
    suffix = f'\n\n...[输出已截断：原始 {len(text)} 字符，仅显示前 {max_chars} 字符]'
    return text[: max_chars - len(suffix)] + suffix


def err(exc: Exception) -> str:
    """Format an AstrBotError (or any exception) as tool error text."""
    return f"错误：{exc}"


def unsupported_on_legacy(feature: str) -> str:
    """Message for features that only exist on the new (v5+) API surface."""
    return (
        f"当前 AstrBot 版本（4.x 旧版）不支持「{feature}」。"
        "该功能需要 AstrBot v5+（master 分支）。"
    )
