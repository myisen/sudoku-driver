# 深入探究 Trae 远程沙箱架构：模型在云上，工具在容器里

> 本文以一个真实的 AI 编码智能体（Trae Remote Agent）为样本，从容器内部视角实测拆解"云端 Agent + 远程沙箱"的架构：模型推理发生在哪里、工具调用如何被执行、网络出口如何约束一切能力，以及如何在这个沙箱里把自己的 SSH 服务映射到 VPS 上实现远程接入。所有结论均来自容器内的实测证据（进程树、文件系统、网络行为），而非官方文档。

## TL;DR

- **模型不在沙箱里**。GLM 系列模型的推理运行在 Trae 平台云端，沙箱内没有任何程序调用模型 API，环境变量里也找不到模型网关地址。
- **沙箱只是"工具执行环境"**。核心进程是一个叫 `agent-tool-host` 的工具宿主：它接收平台下发的工具调用指令，在容器内拉起 `zsh`/文件操作/MCP 子进程执行，再把结果回传。
- **一切网络能力受出口代理约束**。HTTP(S) 自动走容器内 `127.0.0.1:18080` 代理；SSH 这类非 HTTP 协议需要 `nc -X connect` 手动穿透；部分构建工具（如 Clojure CLI 的 aether）完全不读代理，只能本地起镜像服务绕过。
- **沙箱生命周期决定一切持久化**。平台重置沙箱后，sshd、隧道进程、apt 索引全部丢失，只有工作区 `/workspace` 保留。隧道这类长连接本质上是"会话级"的。

---

## 1. 背景：远程沙箱形态的 AI Agent

传统本地运行形态下，AI 编码助手直接跑在用户的机器上：模型 API 返回工具调用，助手进程在本地磁盘执行读写、跑命令。而"远程沙箱"形态把**工具执行**搬到了云端容器里：

```
用户的 IDE / 浏览器
        │  对话
        ▼
Trae 平台后端（编排层）
        │  ① 对话上下文 + 工具结果
        ▼
模型 API（GLM 系列，云端推理）
        │  ② 返回:下一步工具调用
        ▼
远程沙箱容器（Linux）── 实际执行命令/读写文件/访问网络
```

这个形态带来几个直接的好处：用户本机零污染、执行环境可快照可重置、危险操作被容器隔离。但同时也引入了本文要回答的问题——**容器里面到底跑了什么？模型怎么"知道"容器里发生了什么？**

## 2. 容器内实测：进程树与目录结构

在沙箱里执行 `ps -eo pid,ppid,comm` 可以看到完整的进程树（此处省略参数，只保留进程名）：

```
    PID    PPID COMMAND
      1       0 tini              ← 容器 init
    834       1 supervisord      ← 进程守护
    835     834 agent-tool-host  ← ★ 工具宿主（核心）
   2264     835 npm exec @micro… ← MCP server 管理子进程
   2265     835 uv               ← Python 系 MCP server 管理
   2381    2373 postgres-mcp     ← 本地 MCP server 实例
   2419     835 MainThread       ← agent-tool-host 的工作线程
   3610       1 sshd             ← 我们后来装上的（见第 6 节）
   5455     835 zsh              ← 当前正在执行的 shell 命令
   5457    5455 ps
```

配套的文件系统证据在 `/var/log/tool/`：

```
/var/log/tool/
├── agent-tool-host.stdout.log / stderr.log   ← 工具宿主自身日志
├── command-execution/<id>/cwd.txt            ← 每次命令执行的记录目录
├── jobs/                                     ← 后台任务
└── mcp/                                      ← MCP 相关
```

两个关键观察：

1. **`agent-tool-host` 由 `supervisord` 守护**，是平台与容器之间的唯一桥梁——我（模型）发出的每一个工具调用，底层都是它代为执行。
2. **每次 Shell 调用都是一个全新的 `zsh --login` 进程**，执行完毕即退出。这意味着 shell 状态（`export` 的变量、`cd` 的目录）默认不跨调用保留，工作目录通过 `cwd.txt` 在调用之间传递。

## 3. 一次工具调用的完整旅程

把一次"让 Agent 跑条命令"的经历拆开看：

```
用户消息 → 平台编排层 → [① 对话上下文发往模型 API]
模型推理 → 返回工具调用（如 Shell: "git status"）
平台编排层 → [② 指令转发进沙箱]
agent-tool-host → 拉起 zsh --login 执行 → 捕获 stdout/stderr
agent-tool-host → [③ 结果回传平台]
平台编排层 → [④ 工具结果拼入上下文，回到①]
```

几个有趣的细节（实测发现）：

- 每次工具调用注入的环境变量由平台动态下发，包括沙箱标识、平台令牌等（完整列表不在此展示，涉密）。**唯独没有模型 API 的网关地址**——`env | grep -iE "model|api_base|base_url"` 一无所获。模型调用对沙箱是完全封闭的。
- 命令执行的 sandbox 机制：部分命令会落入一个受控沙箱（文件系统/网络白名单），越界访问会被拦截并要求显式声明。
- 我能"看到"的工具清单（Shell、Read、Grep、Agent 子代理、browser_*、几十个 `mcp_trae-remote-official_plugin_*`）都是 agent-tool-host 的能力面，而不是我直接触碰操作系统。

## 4. MCP 的组织方式：本地实例 + 远程网关

进程树里能看到两条 MCP 相关的支线：

- **本地 MCP server**：`npm exec @...` 和 `uv ...` 拉起的具体实例（如 `postgres-mcp`），负责数据库类工具；
- **远程 MCP**：工具名带 `mcp_trae-remote-official_plugin_` 前缀的（gitee、github、tavily、redis 等），实际请求发往 Trae 的远程 MCP 网关。

也就是说 MCP 在这个架构里是"平台统一代理、按插件分发"的模式：沙箱内只保留轻量的本地 server 或纯转发通道，凭据管理收在平台侧。

## 5. 网络层：出口代理决定你能做什么

这是整个架构里最影响实际体验的一层。沙箱没有直连公网的自由，所有出站流量都要过容器内的 HTTP 代理（实测地址 `127.0.0.1:18080`）。

### 5.1 HTTP(S)：透明但有限

`curl`、`git`（https）等会自动读取 `http_proxy/https_proxy` 环境变量，行为基本透明。但有两类例外：

### 5.2 非 HTTP 协议：需要手动穿透

SSH 不认 HTTP 代理环境变量。好在 OpenBSD netcat 支持 `-X connect`，可以用 ProxyCommand 穿透：

```sh
ssh -p 32622 \
  -o ProxyCommand="nc -X connect -x 127.0.0.1:18080 %h %p" \
  root@your-vps-ip 'echo CONNECT_OK'
```

实测这条路是通的——沙箱可以免密登录外部 VPS 并执行命令。

### 5.3 构建工具链的坑：aether 不读代理

给 Metabase 编译达梦驱动时遇到一个经典问题：Clojure CLI 的依赖解析器 aether **既不读 `settings.xml` 的 proxies，也不读 `-D` 系统属性**，导致 Maven 依赖全部直连超时。解法是在沙箱内起一个本地镜像服务，再让 `settings.xml` 把所有仓库镜像到 `127.0.0.1`：

```python
# /tmp/maven-mirror.py（节选）
# ThreadingHTTPServer 监听 127.0.0.1:8897
# GET/HEAD 依次尝试多个上游仓库（aliyun → clojars → repo1 → shibboleth → S3）
# 每个请求经 127.0.0.1:18080 出站代理转发，成功产物落盘缓存
```

```xml
<!-- ~/.m2/settings.xml -->
<mirror>
  <id>local-mirror</id>
  <mirrorOf>*</mirrorOf>
  <url>http://127.0.0.1:8897</url>
</mirror>
```

这个"本地镜像 + 多上游回退 + 代理转发"的组合拳，能覆盖绝大多数企业内网/受限网络下的构建场景，值得收藏。

## 6. 实战：把沙箱的 SSH 映射到自己的 VPS

有了第 5 节的基础，可以做一件好玩的事：**从外部 SSH 进这个云端沙箱**。思路是反向隧道——沙箱主动连出 VPS，并在 VPS 上开一个端口映射回沙箱 sshd：

```
你的任意机器 ──SSH──→ VPS:2222 ──ssh 隧道──→ 沙箱 sshd:2222
```

### 6.1 准备工作

沙箱内（默认没有 sshd）：

```sh
apt-get update && apt-get install -y openssh-server
mkdir -p /run/sshd
cat > /etc/ssh/sshd_config.d/99-sandbox.conf << 'EOF'
Port 2222
PermitRootLogin prohibit-password
PubkeyAuthentication yes
PasswordAuthentication yes
EOF
/usr/sbin/sshd
```

密钥双向配置：

- 沙箱生成 ed25519/RSA 密钥对，**公钥交给 VPS** 的 `authorized_keys`（沙箱 → VPS 方向）；
- VPS 的公钥写入沙箱 `/root/.ssh/authorized_keys`（VPS → 沙箱方向）。

### 6.2 建立反向隧道

```sh
ssh -p 32622 \
  -o ProxyCommand="nc -X connect -x 127.0.0.1:18080 %h %p" \
  -N -R 2222:localhost:2222 \
  -o ServerAliveInterval=30 -o ServerAliveCountMax=3 \
  -o ExitOnForwardFailure=yes \
  root@your-vps-ip
```

之后在 VPS 上 `ssh -p 2222 root@127.0.0.1` 即进入沙箱，端到端验证通过（注意默认只绑定 VPS 的 `127.0.0.1`；要公网可达需在 VPS sshd 开 `GatewayPorts yes` 并改绑 `0.0.0.0`）。

### 6.3 踩过的坑

1. **僵尸端口占用**：沙箱被平台重置导致隧道进程异常死亡后，VPS 侧 sshd 仍持有 `127.0.0.1:2222` 的监听（TCP 半开连接未清理）。重连隧道会报 `remote port forwarding failed`。解法是在 VPS 上 `fuser -k 2222/tcp` 清掉残留会话再重连。
2. **沙箱重置的破坏面**：实测一次平台重置后，openssh-server 本体、`/etc/ssh/sshd_config`、后台进程、apt 索引全部丢失，但 `/root/.ssh` 密钥和 `/workspace` 工作区保留。恢复全套只需约一分钟：重装 sshd → 重建用户 → 重开隧道。

### 6.4 能力的边界

这个隧道能存在，完全依赖沙箱会话存活。平台侧（沙箱外）**没有**通用 SSH/隧道能力——编排层只做模型调用和工具分发，MCP 工具集里也没有网络隧道类工具。所以：

- 沙箱活着 → 隧道可用（心跳保活解决普通断线）；
- 沙箱销毁 → 隧道必然失效，需要 Agent 在新会话里重建。

这也是"远程沙箱"形态的固有代价：**你得到的隔离与可重置，对应的就是长连接与持久服务的脆弱**。

## 7. 小结

| 维度 | 实测结论 |
|---|---|
| 模型推理位置 | 平台云端，沙箱内零痕迹（无网关地址、无相关进程） |
| 工具执行 | `agent-tool-host` 统一代理，每次 Shell 调用独立 zsh 进程 |
| MCP | 本地实例 + 远程网关混合，凭据收在平台侧 |
| 网络出口 | HTTP 透明代理，SSH 用 `nc -X connect` 穿透，构建工具链需本地镜像 |
| 持久性 | 仅 `/workspace` 可靠，进程级状态（sshd/隧道）随会话生灭 |

对使用者的启示：把远程沙箱 Agent 当作"**一个有生命周期限制的远程 Linux 盒子 + 一个藏在云端的模型**"来理解，很多行为就变得可预期了——为什么状态不保留、为什么隧道会断、为什么构建要自己搭镜像，都能从架构上找到原因。

对架构设计者的启示：工具宿主进程（agent-tool-host）这种"单桥梁"设计简洁可控，但代价是沙箱内一切长驻服务都依赖会话存活。如果未来要支持用户自建持久服务（如内网穿透、数据库代理），可能需要平台提供会话无关的托管通道。

---

*环境信息：Trae Remote Agent（远程沙箱形态），模型 GLM-5.3-Flash，Ubuntu 24.04 容器。文中所有操作均在沙箱容器内实测完成。*
