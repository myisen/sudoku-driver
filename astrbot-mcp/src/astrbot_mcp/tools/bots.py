"""Platform adapter (bot) management tools."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out, unsupported_on_legacy

COMMON_BOT_TYPES = (
    "aiocqhttp(QQ/NapCat/Lagrange)、qq_official(QQ官方)、telegram、discord、"
    "wecom(企业微信)、lark(飞书)、dingtalk、webchat"
)


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="列出 AstrBot 支持的平台适配器类型及配置模板（qq_official、aiocqhttp、telegram、discord、wecom 等）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_bot_types() -> str:
        try:
            if await client.get_mode() == "legacy":
                return (
                    "当前为旧版 AstrBot，无独立的平台类型模板接口。常见类型：\n"
                    f"{COMMON_BOT_TYPES}\n"
                    "具体配置字段请参考官方文档 https://docs.astrbot.app 的平台接入章节。"
                )
            return json_out(await client.get("/api/v1/bot-types"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="列出已配置的平台接入实例（机器人）。可按 enabled / type 过滤。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_bots(enabled: bool | None = None, type: str | None = None) -> str:
        try:
            data = await client.api("/bots", "/api/config/platform/list")
            if isinstance(data, dict) and "platforms" in data:
                data = data["platforms"]
            if isinstance(data, list):
                if enabled is not None:
                    data = [b for b in data if bool(b.get("enable", b.get("enabled"))) == enabled]
                if type:
                    data = [b for b in data if b.get("type") == type]
            return json_out(data)
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取单个平台接入实例的完整配置详情。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_bot(bot_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                bots = await client.get("/api/config/platform/list")
                platforms = bots.get("platforms", []) if isinstance(bots, dict) else bots
                for bot in platforms or []:
                    if bot.get("id") == bot_id:
                        return json_out(bot)
                return f"错误：未找到平台实例 {bot_id}"
            return json_out(await client.get(f"/api/v1/bots/{bot_id}"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="新增平台接入实例。新版建议先调用 astrbot_list_bot_types 获取配置模板；config 需包含该平台所需凭据。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_create_bot(
        name: str,
        type: str,
        config: dict[str, Any],
        enabled: bool = True,
    ) -> str:
        """新增平台接入。

        Args:
            name: 实例显示名称。
            type: 平台适配器类型（如 aiocqhttp、telegram）。
            config: 该类型的完整配置（含凭据等）。
            enabled: 创建后是否立即启用。
        """
        try:
            if await client.get_mode() == "legacy":
                # 旧版直接提交完整配置字典，id 为必填主键
                body = dict(config)
                body.setdefault("id", name)
                body["type"] = type
                body["enable"] = enabled
                return json_out(await client.post("/api/config/platform/new", json_body=body))
            body = {"name": name, "type": type, "config": config, "enable": enabled}
            return json_out(await client.post("/api/v1/bots", json_body=body))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新平台接入实例配置。config 传入完整配置（基于 astrbot_get_bot 返回值修改）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_update_bot(
        bot_id: str,
        config: dict[str, Any],
        name: str | None = None,
        type: str | None = None,
    ) -> str:
        try:
            if await client.get_mode() == "legacy":
                body = dict(config)
                body.setdefault("id", bot_id)
                return json_out(
                    await client.post(
                        "/api/config/platform/update",
                        json_body={"id": bot_id, "config": body},
                    )
                )
            body: dict[str, Any] = {"config": config}
            if name:
                body["name"] = name
            if type:
                body["type"] = type
            return json_out(await client.put(f"/api/v1/bots/{bot_id}", json_body=body))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="删除平台接入实例（不可恢复）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_delete_bot(bot_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/config/platform/delete", json_body={"id": bot_id}
                    )
                )
            return json_out(await client.delete(f"/api/v1/bots/{bot_id}"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="启用或禁用平台接入实例。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_toggle_bot(bot_id: str, enabled: bool) -> str:
        try:
            if await client.get_mode() == "legacy":
                bots = await client.get("/api/config/platform/list")
                platforms = bots.get("platforms", []) if isinstance(bots, dict) else bots
                target = next((b for b in platforms or [] if b.get("id") == bot_id), None)
                if target is None:
                    return f"错误：未找到平台实例 {bot_id}"
                target["enable"] = enabled
                return json_out(
                    await client.post(
                        "/api/config/platform/update",
                        json_body={"id": bot_id, "config": target},
                    )
                )
            return json_out(
                await client.patch(
                    f"/api/v1/bots/{bot_id}/enabled", json_body={"enabled": enabled}
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取各平台接入实例的连接状态统计。仅新版 AstrBot (v5+) 支持。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_bot_stats() -> str:
        try:
            if await client.get_mode() == "legacy":
                return unsupported_on_legacy("平台连接状态统计")
            return json_out(await client.get("/api/v1/bots/stats"))
        except Exception as exc:
            return err(exc)
