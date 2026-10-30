"""Plugin management tools (list, market search, install, config)."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="列出已安装的 AstrBot 插件（含版本、启用状态、作者、仓库地址）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_plugins() -> str:
        try:
            return json_out(await client.api("/plugins", "/api/plugin/get"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="从插件市场搜索插件。返回市场列表后按关键词过滤。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_search_plugin_market(
        keyword: str | None = None,
        force_refresh: bool = False,
    ) -> str:
        """搜索插件市场。

        Args:
            keyword: 过滤关键词（匹配插件名/描述，大小写不敏感）。
            force_refresh: 是否强制刷新市场缓存。
        """
        try:
            if await client.get_mode() == "legacy":
                data = await client.get("/api/plugin/market_list")
            else:
                data = await client.get(
                    "/api/v1/plugins/market",
                    params={"force_refresh": str(force_refresh).lower()},
                )
            if isinstance(data, dict):
                items = data.get("list") or data.get("plugins") or data
            else:
                items = data
            if keyword and isinstance(items, list):
                kw = keyword.lower()
                items = [p for p in items if kw in _search_text(p)]
            return json_out(items)
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取单个已安装插件的详情。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_plugin(plugin_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                plugins = await client.get(
                    "/api/plugin/get", params={"name": plugin_id}
                )
                if isinstance(plugins, list) and plugins:
                    return json_out(plugins[0])
                return f"错误：未找到插件 {plugin_id}"
            return json_out(await client.get(f"/api/v1/plugins/{plugin_id}"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="从 Git 仓库 URL 安装插件（如 https://github.com/user/astrbot_plugin_xxx）。安装后自动加载。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_install_plugin(url: str, proxy: str | None = None) -> str:
        try:
            body: dict[str, Any] = {"url": url}
            if proxy:
                body["proxy"] = proxy
            if await client.get_mode() == "legacy":
                return json_out(await client.post("/api/plugin/install", json_body=body))
            return json_out(
                await client.post("/api/v1/plugins/install/url", json_body=body)
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新指定插件到最新版本。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_update_plugin(plugin_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/plugin/update", json_body={"name": plugin_id}
                    )
                )
            return json_out(await client.post(f"/api/v1/plugins/{plugin_id}/update"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="重载指定插件（应用配置或代码变更）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_reload_plugin(plugin_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/plugin/reload", json_body={"name": plugin_id}
                    )
                )
            return json_out(await client.post(f"/api/v1/plugins/{plugin_id}/reload"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="启用或禁用插件。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_toggle_plugin(plugin_id: str, enabled: bool) -> str:
        try:
            if await client.get_mode() == "legacy":
                path = "/api/plugin/on" if enabled else "/api/plugin/off"
                return json_out(await client.post(path, json_body={"name": plugin_id}))
            return json_out(
                await client.patch(
                    f"/api/v1/plugins/{plugin_id}/enabled",
                    json_body={"enabled": enabled},
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="卸载插件（不可恢复）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_uninstall_plugin(plugin_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/plugin/uninstall", json_body={"name": plugin_id}
                    )
                )
            return json_out(await client.delete(f"/api/v1/plugins/{plugin_id}"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="读取插件当前配置。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_plugin_config(plugin_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.get(
                        "/api/config/get", params={"plugin_name": plugin_id}
                    )
                )
            return json_out(await client.get(f"/api/v1/plugins/{plugin_id}/config"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新插件配置（传入完整或部分配置字典，保存后自动热重载插件）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_set_plugin_config(plugin_id: str, config: dict[str, Any]) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/config/api/plugin/update",
                        params={"plugin_name": plugin_id},
                        json_body=config,
                    )
                )
            return json_out(
                await client.put(
                    f"/api/v1/plugins/{plugin_id}/config",
                    json_body={"config": config},
                )
            )
        except Exception as exc:
            return err(exc)


def _search_text(plugin: Any) -> str:
    parts = []
    if isinstance(plugin, dict):
        for key in ("name", "repo", "desc", "description", "author"):
            value = plugin.get(key)
            if isinstance(value, str):
                parts.append(value.lower())
    return " ".join(parts)
