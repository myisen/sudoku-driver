# astrbot-mcp

管理 [AstrBot](https://github.com/AstrBotDevs/AstrBot) 实例的 MCP（Model Context Protocol）服务器。让 Claude / Trae / Cursor 等支持 MCP 的 AI 客户端直接管理你的 AstrBot：查看运行状态、管理平台接入、LLM 供应商、插件、人格与会话路由。

## 功能（P0 核心集，44 个工具）

| 域 | 工具 |
|---|---|
| 监控诊断 | `astrbot_get_stats` / `astrbot_get_version` / `astrbot_get_start_time` / `astrbot_get_logs` / `astrbot_get_storage_stats` |
| 存储与系统 | `astrbot_cleanup_storage` / `astrbot_system_restart` / `astrbot_get_system_config` / `astrbot_update_system_config` |
| 平台接入 | `astrbot_list_bot_types` / `astrbot_list_bots` / `astrbot_get_bot` / `astrbot_create_bot` / `astrbot_update_bot` / `astrbot_delete_bot` / `astrbot_toggle_bot` / `astrbot_get_bot_stats` |
| LLM 供应商 | `astrbot_list_providers` / `astrbot_get_provider_schema` / `astrbot_get_provider` / `astrbot_create_provider` / `astrbot_update_provider` / `astrbot_delete_provider` / `astrbot_toggle_provider` / `astrbot_test_provider` |
| 插件管理 | `astrbot_list_plugins` / `astrbot_search_plugin_market` / `astrbot_get_plugin` / `astrbot_install_plugin` / `astrbot_update_plugin` / `astrbot_reload_plugin` / `astrbot_toggle_plugin` / `astrbot_uninstall_plugin` / `astrbot_get_plugin_config` / `astrbot_set_plugin_config` |
| 人格 | `astrbot_list_personas` / `astrbot_get_persona` / `astrbot_create_persona` / `astrbot_update_persona` / `astrbot_delete_persona` |
| 会话路由 | `astrbot_list_sessions` / `astrbot_get_active_umos` / `astrbot_set_session_provider` / `astrbot_set_session_service` |

## 安装

```bash
pip install .
# 或开发模式
pip install -e .
```

## 版本兼容

本服务器会自动探测 AstrBot 的 API 架构，同一套工具在两个大版本上都能工作：

| | AstrBot v5+（master 分支，FastAPI） | AstrBot 4.x 及更早正式版（Quart） |
|---|---|---|
| 管理接口 | `/api/v1/*` | `/api/*` |
| 认证方式 | API Key（`ApiKey <key>`）或账号密码（JWT） | 仅账号密码（JWT），密码以 md5 提交 |
| 探测方式 | `GET /api/v1/stats` 返回 200 | `GET /api/stat/get` 返回 200 |

**注意事项：**

- **AstrBot 4.x 必须使用 `ASTRBOT_USERNAME` / `ASTRBOT_PASSWORD` 登录**。4.x 的 API Key 只能访问少量 `/api/v1` 开放接口，无法调用本服务器的管理工具（会得到 401）。
- v5+ 推荐使用 API Key；账号密码同样可用。
- 少量功能在 4.x 上不存在（如存储统计/清理），对应工具会返回 `unsupported_on_legacy` 提示而不是报错。
- 默认账号为 `astrbot` / `astrbot`，首次登录后建议在 WebUI 中修改。

## 配置

若使用 AstrBot v5+，推荐在后台 **设置 → API Key** 页面生成一个 API Key，并按需勾选权限 scope（建议：`system`、`bot`、`provider`、`plugin`、`persona`、`config`、`data`）。AstrBot 4.x 请直接使用账号密码。

| 环境变量 | 说明 | 默认值 |
|---|---|---|
| `ASTRBOT_BASE_URL` | AstrBot Dashboard 地址 | `http://127.0.0.1:6185` |
| `ASTRBOT_API_KEY` | API Key（推荐） | - |
| `ASTRBOT_USERNAME` / `ASTRBOT_PASSWORD` | 备选：账号密码登录（自动换 JWT） | - |
| `ASTRBOT_TIMEOUT` | 请求超时（秒） | `30` |

## 在 MCP 客户端中使用

Claude Desktop / Trae 等（`claude_desktop_config.json`）：

```json
{
  "mcpServers": {
    "astrbot": {
      "command": "python",
      "args": ["-m", "astrbot_mcp"],
      "env": {
        "ASTRBOT_BASE_URL": "http://127.0.0.1:6185",
        "ASTRBOT_API_KEY": "你的APIKey"
      }
    }
  }
}
```

调试：

```bash
ASTRBOT_API_KEY=xxx npx @modelcontextprotocol/inspector python -m astrbot_mcp
```

## 权限与安全

- 写入类工具（删除、重启、安装插件等）均标注 `destructiveHint`，客户端会请求确认。
- API Key 支持最小权限：只勾选需要的 scope 即可限制 MCP 可执行的操作。
- 错误信息均带修复指引（如 401 → 提示重新生成 API Key）。

## 许可

MIT
