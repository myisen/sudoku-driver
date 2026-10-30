"""Tool registration for the AstrBot MCP server."""

from __future__ import annotations

from ..client import AstrBotClient
from . import bots, personas, plugins, providers, sessions, system

MODULES = (system, bots, providers, plugins, personas, sessions)


def register_all(mcp, client: AstrBotClient) -> None:
    for module in MODULES:
        module.register(mcp, client)
