"""System monitoring, logs, storage and global config tools."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out, unsupported_on_legacy


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="获取 AstrBot 运行统计：消息量、平台数量、内存占用、活跃会话等总体运行状况。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_stats() -> str:
        try:
            return json_out(await client.api("/stats", "/api/stat/get"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取 AstrBot 版本信息（当前版本与最新可用版本）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_version() -> str:
        try:
            version = await client.api("/stats/version", "/api/stat/version")
            try:
                versions = await client.api("/stats/versions", "/api/stat/version")
            except Exception:
                versions = None
            return json_out({"current": version, "available": versions})
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取 AstrBot 进程启动时间。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_start_time() -> str:
        try:
            return json_out(
                await client.api("/stats/start-time", "/api/stat/start-time")
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="读取 AstrBot 运行日志（环形缓冲区最近日志），用于排查问题。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_logs() -> str:
        try:
            data = await client.api("/logs/history", "/api/log-history")
            if isinstance(data, dict) and "logs" in data:
                return json_out(data)
            return json_out({"logs": data})
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取 AstrBot 数据目录存储占用统计（日志、缓存、数据库等大小）。仅新版 AstrBot (v5+) 支持。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_storage_stats() -> str:
        try:
            if await client.get_mode() == "legacy":
                return unsupported_on_legacy("存储占用统计")
            return json_out(await client.get("/api/v1/stats/storage"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="清理 AstrBot 存储空间。target 可选 logs（日志）/ cache（缓存）/ traces（链路追踪）/ all（全部）。仅新版 AstrBot (v5+) 支持。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_cleanup_storage(target: str = "all") -> str:
        """清理存储。

        Args:
            target: 要清理的类别：logs、cache、traces 或 all。
        """
        if target not in {"logs", "cache", "traces", "all"}:
            return "错误：target 必须是 logs / cache / traces / all 之一"
        try:
            if await client.get_mode() == "legacy":
                return unsupported_on_legacy("存储清理")
            return json_out(
                await client.post(
                    "/api/v1/stats/storage/cleanup", json_body={"target": target}
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="重启 AstrBot 主进程。重启期间机器人短暂离线，请谨慎使用。",
        annotations=ToolAnnotations(destructiveHint=True, readOnlyHint=False),
    )
    async def astrbot_system_restart() -> str:
        try:
            return json_out(
                await client.api_post("/system/restart", "/api/stat/restart-core")
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="读取 AstrBot 全局系统配置（dashboard、默认 provider、插件市场源等）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_system_config() -> str:
        try:
            return json_out(await client.api("/system-config", "/api/config/get"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新 AstrBot 全局系统配置。传入要修改的配置片段，会与现有配置合并保存。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_update_system_config(config: dict[str, Any]) -> str:
        try:
            current = await client.api("/system-config", "/api/config/get")
            merged = {**(current if isinstance(current, dict) else {}), **config}
            if await client.get_mode() == "legacy":
                result = await client.post(
                    "/api/config/astrbot/update",
                    json_body={"config": merged, "conf_id": "default"},
                )
            else:
                result = await client.put("/api/v1/system-config", json_body=merged)
            return json_out(result)
        except Exception as exc:
            return err(exc)
