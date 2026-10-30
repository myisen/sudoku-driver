"""Async HTTP client for the AstrBot dashboard API.

Supports both AstrBot architectures:

- **v1 mode** (AstrBot master / v5+, FastAPI): everything under ``/api/v1``;
  auth via API Key or JWT login.
- **legacy mode** (AstrBot <= 4.x releases, Quart): management endpoints under
  ``/api/*`` require JWT login; only the small open-API surface ``/api/v1/*``
  accepts an API key.

The mode is auto-detected by probing both surfaces, and tool modules call
:meth:`AstrBotClient.api` with both path variants so the same tool works on
either version.
"""

from __future__ import annotations

import asyncio
import hashlib
import time
from typing import Any

import httpx

from .config import Settings

JWT_REFRESH_MARGIN = 6 * 24 * 3600  # tokens are valid for 7 days; refresh early


class AstrBotError(RuntimeError):
    """An error that MCP clients can act on."""


class AstrBotClient:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._http = httpx.AsyncClient(
            base_url=settings.base_url,
            timeout=httpx.Timeout(settings.timeout),
        )
        self._jwt_token: str | None = None
        self._jwt_expires_at: float = 0.0
        self._login_lock = asyncio.Lock()
        self._mode: str | None = None  # "v1" | "legacy"
        self._mode_lock = asyncio.Lock()

    @property
    def mode(self) -> str | None:
        return self._mode

    async def get_mode(self) -> str:
        """Async accessor: detect (or return) the API mode.

        Tools must use this instead of the sync ``mode`` property — the mode
        is unknown until the first login/probe has happened.
        """
        return await self._ensure_mode()

    async def aclose(self) -> None:
        await self._http.aclose()

    # ------------------------------------------------------------------ auth

    def _auth_headers(self) -> dict[str, str]:
        if self._settings.api_key:
            return {"Authorization": f"ApiKey {self._settings.api_key}"}
        if self._jwt_token and time.time() < self._jwt_expires_at:
            return {"Authorization": f"Bearer {self._jwt_token}"}
        return {}

    @staticmethod
    def _md5(text: str) -> str:
        return hashlib.md5(text.encode("utf-8")).hexdigest()

    async def _login(self) -> None:
        """Exchange username/password for a dashboard JWT.

        Tries, in order:
          1. POST /api/v1/auth/login with plaintext (new FastAPI dashboard)
          2. POST /api/auth/login with md5(password) (legacy WebUI behaviour)
          3. POST /api/auth/login with plaintext (fallback)
        """
        if not (self._settings.username and self._settings.password):
            raise AstrBotError(
                "AstrBot 认证失败：未配置凭据。请在环境变量中设置 ASTRBOT_API_KEY"
                "（推荐，在 AstrBot 后台「API Key」页面生成），"
                "或设置 ASTRBOT_USERNAME / ASTRBOT_PASSWORD。"
            )
        username = self._settings.username
        password = self._settings.password
        attempts: list[tuple[str, dict[str, str], str]] = [
            ("/api/v1/auth/login", {"username": username, "password": password}, "v1"),
            ("/api/auth/login", {"username": username, "password": self._md5(password)}, "legacy"),
            ("/api/auth/login", {"username": username, "password": password}, "legacy"),
        ]
        errors: list[str] = []
        async with self._login_lock:
            if self._jwt_token and time.time() < self._jwt_expires_at:
                return
            for path, payload, hint in attempts:
                try:
                    resp = await self._http.post(path, json=payload)
                except httpx.HTTPError as exc:
                    raise _transport_error(self._settings.base_url, exc) from exc
                if resp.status_code == 200:
                    try:
                        token = (resp.json().get("data") or {}).get("token")
                    except ValueError as exc:
                        raise AstrBotError(f"AstrBot 登录响应解析失败：{exc}") from exc
                    if token:
                        self._jwt_token = token
                        self._jwt_expires_at = time.time() + JWT_REFRESH_MARGIN
                        if self._mode is None:
                            self._mode = hint
                        return
                errors.append(f"{path} -> HTTP {resp.status_code}")
        raise AstrBotError(
            "AstrBot 登录失败：用户名或密码错误。请检查 ASTRBOT_USERNAME / "
            "ASTRBOT_PASSWORD（尝试过 "
            + "; ".join(errors)
            + "），或在 AstrBot 后台改用 API Key 认证。"
        )

    # ------------------------------------------------------------------ mode

    async def _ensure_mode(self) -> str:
        """Detect the AstrBot architecture by probing both API surfaces."""
        if self._mode:
            return self._mode
        async with self._mode_lock:
            if self._mode:
                return self._mode
            headers = self._auth_headers()
            if not headers:
                await self._login()
                headers = self._auth_headers()
            # Probe the v1 surface.
            try:
                resp = await self._http.get("/api/v1/stats", headers=headers)
            except httpx.HTTPError as exc:
                raise _transport_error(self._settings.base_url, exc) from exc
            if resp.status_code == 200:
                self._mode = "v1"
                return self._mode
            # 404 => the v1 surface exists (auth passed) but /stats is absent
            # (legacy release). 401 with JWT => legacy /api/v1 rejects JWT.
            if resp.status_code in (401, 404) and not self._settings.api_key:
                await self._login()
                headers = self._auth_headers()
                try:
                    resp = await self._http.get("/api/v1/stats", headers=headers)
                except httpx.HTTPError as exc:
                    raise _transport_error(self._settings.base_url, exc) from exc
                if resp.status_code == 200:
                    self._mode = "v1"
                    return self._mode
            # Probe the legacy surface.
            try:
                resp2 = await self._http.get("/api/stat/get", headers=headers)
            except httpx.HTTPError as exc:
                raise _transport_error(self._settings.base_url, exc) from exc
            if resp2.status_code == 200:
                self._mode = "legacy"
                return self._mode
            if resp.status_code == 401 or resp2.status_code == 401:
                raise AstrBotError(
                    "AstrBot 认证失败（401）。API Key 无效或已过期："
                    "请在 AstrBot 后台重新生成；旧版（4.x）AstrBot 的管理接口"
                    "不支持 API Key，请改用 ASTRBOT_USERNAME / ASTRBOT_PASSWORD 登录。"
                )
            raise AstrBotError(
                "无法识别 AstrBot API 版本（/api/v1/stats 与 /api/stat/get 均不可用）。"
                f"响应状态：v1={resp.status_code}, legacy={resp2.status_code}。"
                "请确认 ASTRBOT_BASE_URL 指向 AstrBot Dashboard 地址。"
            )

    # --------------------------------------------------------------- request

    async def _do_request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        clean_params = {k: v for k, v in (params or {}).items() if v is not None}
        headers = self._auth_headers()
        if not headers:
            await self._login()
            headers = self._auth_headers()
        try:
            resp = await self._http.request(
                method, path, params=clean_params, json=json_body, headers=headers
            )
        except httpx.HTTPError as exc:
            raise _transport_error(self._settings.base_url, exc) from exc

        # Re-login once when the JWT expired mid-flight.
        if resp.status_code == 401 and self._jwt_token:
            self._jwt_token = None
            await self._login()
            headers = self._auth_headers()
            try:
                resp = await self._http.request(
                    method, path, params=clean_params, json=json_body, headers=headers
                )
            except httpx.HTTPError as exc:
                raise _transport_error(self._settings.base_url, exc) from exc

        if resp.status_code == 401:
            raise AstrBotError(
                "AstrBot 认证失败（401）。"
                + (
                    "API Key 无效或已过期：请在 AstrBot 后台重新生成。"
                    if self._settings.api_key
                    else "登录态失效：请检查用户名密码。"
                )
                + "旧版（4.x）AstrBot 的管理接口不支持 API Key，"
                "如持续失败请改用 ASTRBOT_USERNAME / ASTRBOT_PASSWORD。"
            )
        if resp.status_code == 403:
            raise AstrBotError(
                "AstrBot 权限不足（403）。当前凭据缺少该操作所需权限，"
                "请在后台调整 API Key 的 scope 或使用管理员账号。"
            )
        if resp.status_code == 404:
            raise AstrBotError(
                f"AstrBot 接口不存在（404）：{method} {path}。"
                "请确认 ASTRBOT_BASE_URL 指向正确的 Dashboard 地址，"
                "且 AstrBot 版本支持该接口。"
            )
        if resp.status_code >= 400:
            raise AstrBotError(
                f"AstrBot 请求失败（HTTP {resp.status_code}）{method} {path}："
                f"{_extract_detail(resp)}"
            )
        try:
            envelope = resp.json()
        except ValueError as exc:
            raise AstrBotError(
                f"AstrBot 响应不是合法 JSON（{method} {path}）：{resp.text[:200]}"
            ) from exc
        if isinstance(envelope, dict) and envelope.get("status") == "error":
            raise AstrBotError(f"AstrBot 返回错误：{envelope.get('message') or envelope}")
        return envelope

    async def api(
        self,
        v1_path: str,
        legacy_path: str,
        *,
        method: str = "GET",
        params: dict[str, Any] | None = None,
        json_body: Any = None,
    ) -> Any:
        """Call a version-aware endpoint and unwrap the response envelope."""
        mode = await self._ensure_mode()
        path = v1_path if mode == "v1" else legacy_path
        envelope = await self._do_request(method, path, params=params, json_body=json_body)
        if isinstance(envelope, dict) and "data" in envelope:
            return envelope["data"]
        return envelope

    # Convenience verbs on a single, explicit path -----------------------

    async def get(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._unwrap(self._do_request("GET", path, params=params))

    async def post(self, path: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        return await self._unwrap(self._do_request("POST", path, params=params, json_body=json_body))

    async def put(self, path: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        return await self._unwrap(self._do_request("PUT", path, params=params, json_body=json_body))

    async def patch(self, path: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        return await self._unwrap(self._do_request("PATCH", path, params=params, json_body=json_body))

    async def delete(self, path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self._unwrap(self._do_request("DELETE", path, params=params))

    async def _unwrap(self, coro: Any) -> Any:
        envelope = await coro
        if isinstance(envelope, dict) and "data" in envelope:
            return envelope["data"]
        return envelope

    async def api_post(self, v1_path: str, legacy_path: str, *, params: dict[str, Any] | None = None, json_body: Any = None) -> Any:
        return await self.api(v1_path, legacy_path, method="POST", params=params, json_body=json_body)

    async def api_put(self, v1_path: str, legacy_path: str, *, json_body: Any = None) -> Any:
        return await self.api(v1_path, legacy_path, method="PUT", json_body=json_body)

    async def api_patch(self, v1_path: str, legacy_path: str, *, json_body: Any = None) -> Any:
        return await self.api(v1_path, legacy_path, method="PATCH", json_body=json_body)

    async def api_delete(self, v1_path: str, legacy_path: str, *, params: dict[str, Any] | None = None) -> Any:
        return await self.api(v1_path, legacy_path, method="DELETE", params=params)


def _extract_detail(resp: httpx.Response) -> str:
    try:
        body = resp.json()
    except ValueError:
        return resp.text[:300]
    if isinstance(body, dict):
        return str(body.get("message") or body.get("detail") or body)[:300]
    return str(body)[:300]


def _transport_error(base_url: str, exc: httpx.HTTPError) -> AstrBotError:
    if isinstance(exc, httpx.TimeoutException):
        return AstrBotError(
            f"连接 AstrBot 超时（{base_url}）。请确认 AstrBot 正在运行、"
            "地址正确且网络可达；也可通过 ASTRBOT_TIMEOUT 增大超时。"
        )
    return AstrBotError(
        f"无法连接 AstrBot（{base_url}）：{exc.__class__.__name__}。"
        "请检查 ASTRBOT_BASE_URL 是否正确、AstrBot 是否已启动。"
    )
