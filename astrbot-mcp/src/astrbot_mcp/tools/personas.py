"""Persona (system prompt) management tools."""

from __future__ import annotations

from mcp.types import ToolAnnotations

from ..client import AstrBotClient
from ._helpers import err, json_out


def register(mcp, client: AstrBotClient) -> None:
    @mcp.tool(
        description="列出所有人格（Persona，即系统提示词预设）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_list_personas() -> str:
        try:
            return json_out(await client.api("/personas", "/api/persona/list"))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="获取单个人格的完整内容（系统提示词、开场对话等）。",
        annotations=ToolAnnotations(readOnlyHint=True),
    )
    async def astrbot_get_persona(persona_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/persona/detail", json_body={"persona_id": persona_id}
                    )
                )
            return json_out(
                await client.get(
                    "/api/v1/personas/by-id", params={"persona_id": persona_id}
                )
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="创建新人格（系统提示词预设）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_create_persona(
        persona_id: str,
        system_prompt: str,
        begin_dialogs: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> str:
        """创建人格。

        Args:
            persona_id: 人格唯一 ID（同时作为显示名）。
            system_prompt: 系统提示词内容。
            begin_dialogs: 可选开场对话列表（交替 user/assistant 内容）。
            tools: 可选，允许该人格使用的函数工具名列表。
        """
        try:
            body: dict = {
                "persona_id": persona_id,
                "system_prompt": system_prompt,
            }
            if begin_dialogs:
                body["begin_dialogs"] = begin_dialogs
            if tools:
                body["tools"] = tools
            if await client.get_mode() == "legacy":
                return json_out(await client.post("/api/persona/create", json_body=body))
            return json_out(await client.post("/api/v1/personas", json_body=body))
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="更新人格内容（系统提示词、开场对话等，传入要修改的字段）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_update_persona(
        persona_id: str,
        system_prompt: str | None = None,
        begin_dialogs: list[str] | None = None,
        tools: list[str] | None = None,
    ) -> str:
        try:
            body: dict = {"persona_id": persona_id}
            if system_prompt is not None:
                body["system_prompt"] = system_prompt
            if begin_dialogs is not None:
                body["begin_dialogs"] = begin_dialogs
            if tools is not None:
                body["tools"] = tools
            if await client.get_mode() == "legacy":
                return json_out(await client.post("/api/persona/update", json_body=body))
            return json_out(
                await client.put("/api/v1/personas/by-id", json_body=body)
            )
        except Exception as exc:
            return err(exc)

    @mcp.tool(
        description="删除人格（不可恢复）。",
        annotations=ToolAnnotations(destructiveHint=True),
    )
    async def astrbot_delete_persona(persona_id: str) -> str:
        try:
            if await client.get_mode() == "legacy":
                return json_out(
                    await client.post(
                        "/api/persona/delete", json_body={"persona_id": persona_id}
                    )
                )
            return json_out(
                await client.delete(
                    "/api/v1/personas/by-id", params={"persona_id": persona_id}
                )
            )
        except Exception as exc:
            return err(exc)
