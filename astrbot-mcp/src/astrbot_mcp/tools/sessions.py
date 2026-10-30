"""Session (conversation route) management tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="分页列出活跃会话（UMO：平台:消息类型:会话ID），含当前使用的 provider 与服务开关状态。可搜索、按平台过滤。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_sessions(
        page: int = 1,
        page_size: int = 20,
        search: str = "",
        platform: str = "",
        message_type: str = "all",
    ) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.get("/api/session/list-all-with-status")
                )
            return json_out(
                await client.get(
                    "/api/v1/sessions",
                    params={
                        "page": page,
                        "page_size": page_size,
                        "search": search,
                        "platform": platform,
                        "message_type": message_type,
                    },
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取有消息往来的活跃 UMO 列表（用于批量操作时确定 umo 标识）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_active_umos(platform: str = "") -> str:
        try:
            return json_out(
                await client.api(
                    "/sessions/active-umos",
                    "/api/session/active-umos",
                    params={"platform_id": platform} if platform else None,
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="批量为会话设置 LLM provider（切换会话使用的模型）。umos 来自 astrbot_list_sessions / astrbot_get_active_umos。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_set_session_provider(
        umos: list[str],
        provider_id: str,
        provider_type: str = "chat_completion",
    ) -> str:
        """批量设置会话 provider。

        Args:
            umos: 会话 UMO 列表。
            provider_id: 目标 provider ID（来自 astrbot_list_providers）。
            provider_type: chat_completion / text_to_speech / speech_to_text。
        """
        if provider_type not in {"chat_completion", "text_to_speech", "speech_to_text"}:
            return "错误：provider_type 必须是 chat_completion / text_to_speech / speech_to_text 之一"
        body = {
            "umos": umos,
            "provider_id": provider_id,
            "provider_type": provider_type,
        }
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/session/batch-update-provider", json_body=body
                    )
                )
            return json_out(
                await client.patch("/api/v1/sessions/provider", json_body=body)
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="批量开关会话服务（是否响应消息 / 是否启用 LLM / 是否启用 TTS）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_set_session_service(
        umos: list[str],
        session_enabled: bool | None = None,
        llm_enabled: bool | None = None,
        tts_enabled: bool | None = None,
    ) -> str:
        try:
            body: dict = {"umos": umos}
            if session_enabled is not None:
                body["session_enabled"] = session_enabled
            if llm_enabled is not None:
                body["llm_enabled"] = llm_enabled
            if tts_enabled is not None:
                body["tts_enabled"] = tts_enabled
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/session/batch-update-service", json_body=body
                    )
                )
            return json_out(
                await client.patch("/api/v1/sessions/service", json_body=body)
            )
        except Exception as exc:
            return err(exc)
