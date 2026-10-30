"""MCP server entry point for AstrBot management.

Run with: python -m astrbot_mcp
Requires: ASTRBOT_API_KEY (or ASTRBOT_USERNAME/ASTRBOT_PASSWORD) env vars.
"""

from __future__ import annotations

import argparse
import sys

from mcp.server.fastmcp import FastMCP

from . import __version__
from .client import AstrBotClient
from .config import load_settings
from .tools import register_all


def build_server() -> tuple[FastMCP, AstrBotClient]:
    settings = load_settings()
    client = AstrBotClient(settings)
    mcp: FastMCP = FastMCP(
        name="astrbot-mcp",
        instructions=(
            "AstrBot 管理 MCP 服务器。可用于管理 AstrBot 实例：查看运行状态与日志、"
            "管理平台接入(bots)、LLM 服务提供商(providers)、插件、人格(personas)、"
            "会话路由与系统配置。写入类操作会实时影响机器人运行，执行删除/重启等"
            "操作前请先与用户确认。"
        ),
    )
    register_all(mcp, client)
    return mcp, client


def main() -> None:
    parser = argparse.ArgumentParser(description="AstrBot management MCP server")
    parser.add_argument(
        "--version", action="version", version=f"astrbot-mcp {__version__}"
    )
    parser.parse_args()

    mcp, client = build_server()

    import anyio

    async def _run() -> None:
        try:
            await mcp.run_stdio_async()
        finally:
            await client.aclose()

    try:
        anyio.run(_run)
    except KeyboardInterrupt:
        pass
    finally:
        sys.exit(0)


if __name__ == "__main__":
    main()
