"""LLM provider management tools."""

from __future__ import annotations

from typing import Any

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out


async def _legacy_provider_list(client: AstrBotClient, provider_type: str) -> Any:
    return await client.get(
        "/api/config/provider/list", params={"provider_type": provider_type}
    )


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="列出已配置的 LLM 服务提供商。capability 可选 chat_completion（对话）/ text_to_speech（语音合成）/ speech_to_text（语音识别）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_providers(capability: str = "chat_completion") -> str:
        try:
            if capability not in {"chat_completion", "text_to_speech", "speech_to_text"}:
                return "错误：capability 必须是 chat_completion / text_to_speech / speech_to_text 之一"
            if await client.get_mode() == "legacy":
                data = await _legacy_provider_list(client, capability)
            else:
                data = await client.get(
                    "/api/v1/providers", params={"capability": capability}
                )
            return json_out(data)
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取 provider 配置模板（各厂商类型的字段说明），用于构造 create/update 所需的 config。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_provider_schema() -> str:
        try:
            return json_out(
                await client.api(
                    "/providers/schema", "/api/config/provider/template"
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取单个 provider 的完整配置。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_provider(provider_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                for ptype in ("chat_completion", "text_to_speech", "speech_to_text"):
                    providers = await _legacy_provider_list(client, ptype)
                    for provider in providers or []:
                        if provider.get("id") == provider_id:
                            return json_out(provider)
                return f"错误：未找到 provider {provider_id}"
            return json_out(
                await client.get(
                    f"/api/v1/providers/{provider_id}", params={"merged": True}
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="新增 LLM 服务提供商。config 需包含 id、type（如 openai_chat_completion）、key、api_base 等完整配置。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_create_provider(config: dict[str, Any]) -> str:
        """新增 provider。

        Args:
            config: 完整 provider 配置，参考 astrbot_get_provider_schema。
        """
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post("/api/config/provider/new", json_body=config)
                )
            return json_out(
                await client.post("/api/v1/providers", json_body={"config": config})
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新 LLM 服务提供商配置（实时生效）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_update_provider(provider_id: str, config: dict[str, Any]) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/config/provider/update",
                        json_body={"id": provider_id, "config": config},
                    )
                )
            return json_out(
                await client.put(
                    f"/api/v1/providers/{provider_id}", json_body={"config": config}
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="删除 LLM 服务提供商配置（不可恢复）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_delete_provider(provider_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/config/provider/delete", json_body={"id": provider_id}
                    )
                )
            return json_out(await client.delete(f"/api/v1/providers/{provider_id}"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="启用或禁用 LLM 服务提供商。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_toggle_provider(provider_id: str, enabled: bool) -> str:
        try:
            if await client.get_mode() == "legacy":
                target = None
                for ptype in ("chat_completion", "text_to_speech", "speech_to_text"):
                    providers = await _legacy_provider_list(client, ptype)
                    for provider in providers or []:
                        if provider.get("id") == provider_id:
                            target = provider
                            break
                    if target:
                        break
                if target is None:
                    return f"错误：未找到 provider {provider_id}"
                target["enable"] = enabled
                return json_out(
                    await client.post(
                        "/api/config/provider/update",
                        json_body={"id": provider_id, "config": target},
                    )
                )
            return json_out(
                await client.patch(
                    f"/api/v1/providers/{provider_id}/enabled",
                    json_body={"enabled": enabled},
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="测试 provider 连通性（向模型发送测试请求，返回延迟与响应）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_test_provider(provider_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.get(
                        "/api/config/provider/check_one",
                        params={"id": provider_id},
                    )
                )
            return json_out(await client.post(f"/api/v1/providers/{provider_id}/test"))
        except Exception as exc:
            return err(exc)
