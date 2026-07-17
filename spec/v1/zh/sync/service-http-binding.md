---
title: Service HTTP/JSON Binding
status: candidate
normative: true
stability: v1
updated: 2026-07-16
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

Operation 语义本身可映射到不同 transport；但 **v1 core wire conformance 必须提供本文定义的 HTTP/JSON binding**。其他 transport binding（gRPC、WebSocket、SSE、message queue、libp2p 或 IPC）只能作为 extension profile 出现，并且必须映射到 `service-surface.md` 中定义的等价语义。

## 2. 通用要求

- 请求和响应默认使用 `Content-Type: application/json`。
- 写请求 MUST 支持幂等键或内容 ID 幂等。
- 认证 MUST 使用 DPoP、HTTP Message Signature、DID proof、mTLS 或等价 sender-constrained binding。会话出示按 [`api-conventions.md` §3](./api-conventions.md) 推荐序选择：`/_arkret/self/*` 的默认会话凭据是直接出示 `ak.session.grant` + `DPoP`（[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449)，[`api-conventions.md` §3.3](./api-conventions.md)），Principal Server 经 session-grant 内省（缓存 ≤120s）+ DPoP 校验放行，**不**铸独立本地 bearer、**不**暴露第二个客户端可见的 Principal 本地凭据签发 endpoint；带 body 写与敏感读 MUST 使用 `session_public_key` 的 RFC 9421 HTTP Message Signature 或等价 sender-constrained proof。裸 `Authorization: Bearer` 只能作为 DPoP / PoP 绑定中的 grant 载体；生产 current-v1 受保护 endpoint MUST NOT 接受裸 bearer 作为认证成功（§2.5）。
- 服务 MUST 通过 describe / feature discovery 暴露实际支持路径、profile 和限制。
- 错误响应 MUST 使用统一 error schema。
- 认证材料 MUST 放在 header、HTTP Message Signature、mTLS 或 signed proof body 中；受保护 endpoint MUST NOT 接受 query string 认证。
- 未知路径、错误 method、限流、临时不可用和不可见资源 MUST 使用 `api-conventions.md` 中定义的标准错误语义。

### 2.1 REST API 命名空间组织

Arkret 的 HTTP/JSON binding 按 **服务角色与 canonical operation** 组织，而不是按某个产品形态拆成固定的 Client API / Server API / Push API 包。客户端、Principal Server、Events API、Directory、Applet、Push Gateway 等都可以暴露自己的服务面；服务发现决定某个节点实际支持哪些命名空间。

所有 path 都在 negative-space 根 `/_arkret/` 之下，且**不含版本段**。`/_arkret/` 之后的第一段是 **trust-surface classifier（信任面分类器）**：它编码"调用方↔服务"的信任关系和攻击面类别。本文保留"信任同心圆"作为解释隐喻，但正式规则是"第一段 = 信任面分类"，不是授权结论。

| 信任面段 | 信任关系 | 承接命名空间 |
| --- | --- | --- |
| `self` | 本人已认证会话 | events·account·contacts·direct_conversations·rtc·blob·keys·authz·policy·projection·agents·device_messages·moderation·snapshot·ephemeral·applets |
| `gate` | 认证入口 | account（auth / session-grant） |
| `root` | 身份信任根：DID / key log / receipt；不是 Unix/root 管理员权限 | identity |
| `find` | 目录发现 | directory |
| `peer` | 对等 Arkret 服务器 | federation server↔server wire：`peer.events`、`peer.snapshot`、`peer.invites`、`peer.contacts` |
| `open` | 外部协议互通 / 外部 handoff 面；不表示 public / no-auth access | mimi、invite_locator |
| `edge` | 推送 / 桥接网关 | push·applet |

读 URL 即读攻击面：`/_arkret/self/...` 是调用方本人的会话面，`/_arkret/open/...` 一眼就是在跟外部协议或外部 provider 打交道。但信任面段本身 **MUST NOT** 被实现解释为授权通过、安全级别达标或明文可见许可。每个 operation 仍必须按自身契约执行 session、capability、DID proof、Realm policy、history visibility、service delegation、rate limit 和最小披露校验；路径段只帮助路由、审计、中间件和读者快速识别攻击面。pre-auth 的根级能力广告位于根 meta 位 `GET /_arkret/describe`（`ak.server.query.describe`）；其余 `*.describe` 各自跟随所在段。版本不进 path，由 `*.describe` / `supported_operations` 协商（可选 `Arkret-Protocol-Version` header）。versionless + 协议内协商如何支撑新旧实现互通，见 [overview/evolution-and-compatibility.md](../overview/evolution-and-compatibility.md) §6。

默认 REST 命名空间如下：

| 命名空间 | 主要调用方 | 语义 | 规范文件 |
| --- | --- | --- | --- |
| `/_arkret/describe` | 客户端与服务 | 根级服务描述、feature discovery、auth metadata（pre-auth）。 | `service-surface.md`、`api-conventions.md` |
| `/_arkret/gate/account/*` | 客户端、Account Authority；部署内部可委托 Auth Server / Principal Server | 账户认证 / 准入入口：注册 / account binding、session-grant 签发、刷新、撤销、登出、设备配对授权落地、OIDC 回调、agent key pairing。客户端 MUST 只从 `ServiceDescribe.auth_metadata.account_authority.gate_account_base` 派生此 namespace。 | `service-surface.md`、`api-conventions.md` |
| `/_arkret/root/identity/*` | 客户端、服务、registry | 身份信任根：DID 文档、key log、DID operation、receipt；`root` 不是管理员权限面。 | `service-surface.md`、`identity-did.md` |
| `/_arkret/self/events/*` | 客户端、Principal Server、授权 Event 副本 | signed Event 提交、按 ID 读取、批量读取、actor/Realm 双向历史查询(query)、流式订阅(subscribe，含 bounded catch-up replay)、frontier 查询。 | `operations-sync.md`、`service-surface.md` |
| `/_arkret/peer/events/*` | 对等 Principal Server / Federation Server | federation peer 推送、拉取 / backfill、按 ID 补洞、frontier probe。所有请求 MUST 使用 service-to-service 签名、Source/Destination service DID 与 trust-domain header，并通过 Realm `federation_peer` 授权。 | `federation.md`、`operations-sync.md` |
| `/_arkret/peer/invites` | 对等 Principal Server | 私有 invite delivery：邀请方 Principal Server 将 `ak.invite.create`、显式 invite address 与 introduction evidence 投递给被邀请方 Principal Server。所有请求 MUST 使用 service-to-service 签名并绑定 Destination service DID。 | `invite-addressing.md` |
| `/_arkret/peer/contacts` | 对等 Principal Server | 私有 contact fact delivery：一方 Principal Server 将 `ak.contact.requested` / `accepted` / `rejected` / `tombstoned` 原签名 envelope 投递给对端 holder 的 Principal Server。它不接收共享 Realm Event，不推进 Realm reducer / Seal。所有请求 MUST 使用 service-to-service 签名并绑定 Destination service DID。 | `identity/contact-and-direct-conversation.md`、`federation.md` |
| `/_arkret/self/account/*` | 客户端、Principal Server | account viewer 自读、profile 更新、account 聚合 streaming 订阅(`GET /_arkret/self/account/subscribe`)、describe 与 cursor revoke。逐 Realm 的事件流读取走 `/_arkret/self/events/*`。 | `client-sync.md`、`service-surface.md`、`profiles-presence.md` |
| `/_arkret/self/snapshot/*` | 客户端、Principal Server | Realm snapshot manifest 入口(`GET /_arkret/self/snapshot/head`)。 | `client-sync.md`、`service-surface.md` |
| `/_arkret/peer/snapshot/*` | 对等 Principal Server / Federation Server | federation snapshot-assisted bootstrap manifest 入口(`GET /_arkret/peer/snapshot/head`)。 | `federation.md`、`snapshot.schema.json` |
| `/_arkret/self/realms/*`、`/_arkret/self/views/*` | 客户端、Principal Server | Realm lifecycle 读取与治理（get / archive / freeze / tombstone / destroy / moderation-policy / export / links），以及 Realm 作用域内 reducer 派生对象读取：Space / Strand / Morph lifecycle 列表与 document Morph 单对象读模型；collection View 物化在 `/_arkret/self/views/*`。 | `realm-and-space.md`、`strand-and-message.md`、`morph.md`、`views.md` |
| `/_arkret/self/applets/*` | 客户端、Realm admin、已安装 Applet service | self/admin 信任面的 Applet 安装聚合操作：install 预览、install、revoke（`ak.self.applet.install.command.preview` / `ak.self.applet.command.install` / `ak.self.applet.command.revoke`），以及 bridge Applet 的 Ghost Actor provisioning（`ak.self.applet.ghost.command.provision`）。Applet 运行时桥接面在 `/_arkret/edge/applet/*`。 | `applet-integration.md` |
| `/_arkret/find/directory/*` | 客户端、服务 | Realm / Organization / Actor / handle 的授权发现与解析。 | `discovery-directory.md` |
| `/_arkret/self/blob/*` | 客户端、服务 | Blob 上传、HEAD、authenticated download。 | `media-and-blob.md` |
| `/_arkret/edge/push/*` | 客户端、Sync、Push Gateway | 推送设备注册、注销、脱敏唤醒投递。 | `push-notifications.md` |
| `/_arkret/self/device_messages/*`、`/_arkret/self/keys/*` | E2EE 客户端、Principal Server | 当前已认证 principal/device 的 to-device 队列、设备 key 发布/查询、KeyPackage 与 key backup 运行态操作。 | `device-lifecycle.md` |
| `/_arkret/self/authz/*`、`/_arkret/self/policy/check` | 客户端、Events API、Sync、Policy Server | capability 预检查、Policy Server 签名决策。Canonical path 是 `/_arkret/self/policy/check`(`ak.self.policy.query.check`)。 | `capabilities.md`、`policy-server.md` |
| `/_arkret/self/rtc/ice-config` | 通话客户端、Realtime Media Server | TURN/STUN/ICE 短期凭证。 | `webrtc-signaling.md` |
| `/_arkret/self/moderation/*` | 客户端、审核服务 | 举报、审核队列或扩展审核入口。 | `governance/content-moderation.md` |
| `/_arkret/edge/applet/*` | Arkret 服务调用 Applet | applet ping / describe、transaction push、Ghost Actor / portal 查询。 | `applet-integration.md` |
| `/_arkret/open/invite-locators/resolve` | 扫码客户端、Principal Server | 外部 handoff：把 URL fragment / OOB 中取得的 locator token 通过 JSON body 换成签名 `principal_locator`。token MUST NOT 出现在 URL path 或 query。 | `invite-addressing.md` |
| `/_arkret/open/agent-pairing/resolve`、`/_arkret/open/agent-pairing/runtime-key-requests`、`/_arkret/open/agent-pairing/runtime-key-requests/status` | Agent runtime、Principal Server | 外部 handoff：把 URL fragment / OOB 中取得的 pairing token 通过 JSON body 换成 6 字段 `agent_pairing_bootstrap`；随后 runtime 用 bootstrap 中至少 128-bit CSPRNG 的一次性 `pairing_code` + local key PoP 提交待 controller 审批的 runtime key request，并轮询 status 端点获知 controller 审批结果。token / pairing 秘密 MUST NOT 出现在 URL path 或 query。服务端 MUST 按 `(agent_id, pairing_request_id, source_ip_bucket)` 限速；同一 handle 连续 10 次失败后 MUST 永久失效，所有 miss / mismatch / exhausted 响应保持不可枚举。 | `../identity/key-management.md` |
| `/_arkret/open/mimi/*` | Arkret 服务、MIMI provider facade | 外部协议互通；`open` 表示 interop / handoff surface，不表示公开免认证访问。 | `mimi-interop.md` |

客户端视角的常用 API 集合通常包括 `/_arkret/describe`、`/_arkret/root/identity/*`、`/_arkret/self/events/*`、`/_arkret/self/account/*`、`/_arkret/self/snapshot/*`、`/_arkret/self/realms/*`、`/_arkret/self/views/*`、`/_arkret/find/directory/*`、`/_arkret/self/blob/*`、`/_arkret/edge/push/*`、`/_arkret/self/device_messages/*`、`/_arkret/self/keys/*`、`/_arkret/self/authz/*`。federation / Principal Server 服务间 API 集合包括 `/_arkret/peer/events/*`、`/_arkret/peer/snapshot/*`、`/_arkret/peer/invites` 与 `/_arkret/peer/contacts`；locator 二维码 / 链接 handoff 使用 `/_arkret/open/invite-locators/resolve`，agent pairing 短链接 handoff 使用 `/_arkret/open/agent-pairing/resolve`。policy、applet、push 等非 federation 服务间调用按各自 trust surface 暴露。搜索、inbox、notification 和 View projection 默认是客户端本地派生；Realm 作用域对象读取（`/_arkret/self/realms/{realm_id}/spaces|strands|morphs`、`/_arkret/self/realms/{realm_id}/morphs/{morph_id}`）与 `/_arkret/self/views/*` projection 绑定属于 extension surface，必须由服务显式声明支持，且不得成为 canonical truth source。

#### 2.1.1 账号/设备接口归属判据

设备相关接口不能只按资源名放入 `gate` 或 `self`；规范 MUST 按动作跨越的信任边界分类：

- `/_arkret/gate/account/*` 是认证与准入边界。凡是签发、刷新或撤销 `ak.session.grant`，消费 OIDC / passkey / recovery proof / pairing code，或把一次短期配对证明落成新的 durable device authorization 的操作，MUST 放在 `gate`。`ak.gate.account.command.pair_device` 属于此类：它消费短期 pairing proof 和已授权设备的 fresh proof，返回 `ak.device.authorize` / `ak.device.list_update` 相关引用或等价结果；它不得成为普通 to-device 消息队列。
- `/_arkret/self/*` 是当前 authenticated principal/device 的运行态。凡是读取账号投影、维护 account subscribe、读写当前设备 to-device 队列、发布/查询 E2EE key、KeyPackage 或 key backup 的操作，属于 `self`。`ak.self.device_messages.command.send` / `ak.self.device_messages.query.list` / `ak.self.device_messages.command.ack` 属于此类：它是已认证会话下的 per-device 私有投递队列，即使载荷是 `ak.key.verification.*`，也不承担设备准入授权本身。
- 新设备尚未被 `ak.device.authorize` 接受时，若 gate 已签发 fresh-device restricted `ak.session.grant`，该 grant MAY 只允许向同 principal 的已授权设备发送/接收 `ak.key.verification.*` bootstrap 消息；它 MUST NOT 允许 `ak.secret.*`、key backup unlock、KeyPackage 发布或 Realm E2EE history 读取。`ak.secret.request/send` 只能在目标新设备已经被 durable device list 接受并完成验证绑定后使用。
- `/_arkret/root/identity/*` 承载 DID、key log、recovery policy/session 等身份根状态；这些操作可能发生在完整 grant-binding self session 之前，不能为了“设备相关”而移动到 `self`。
- `/_arkret/edge/push/*` 只注册/注销唤醒路由和投递盲通知。push MAY 提醒旧设备打开同步，但 push payload 不是验证请求真相源，也不得携带可替代 to-device transcript 的授权材料。

#### 2.1.2 Account Authority 路由规则

客户端登录 / account flow MUST 先读取 Principal Server 的 `GET /_arkret/describe`，再从 `auth_metadata.account_authority.gate_account_base` 得到唯一的客户端可见 Account Authority base。所有客户端可见的 Arkret `/_arkret/gate/account/*` 请求（包括 `session-grants`、`session-grants/refresh`、`session-grants/revoke`、`logout`、`device-pair`、`device-enroll`、`agent-key-pair`、`oidc/callback`）都 MUST 发往该 base。客户端 MUST NOT 按 operation 名称自行把一部分请求发往 Principal Server、一部分发往 Auth Server。`ak.gate.account.command.introspect_session_grant` 与 `ak.gate.account.command.logout_auth_session` 是部署内部 S2S 操作，不是客户端 account flow；普通客户端 MUST NOT 从 `gate_account_base` 派生或调用它们。

若 Auth Server 与 Principal Server 分进程或分 origin，部署 MUST 提供一个位于认证 TCB 内的 Account Authority 前置，完整承载 `gate_account_base` 并在内部按 operation 路由。该内部路由是实现细节；`auth_metadata.methods[].issuer` / OIDC discovery 只用于标准认证协议 endpoint，不得被客户端用来推导 Arkret `gate/account` endpoint。

`auth_metadata.methods[]` 中的 OIDC method 使用标准 OIDC discovery。客户端打开 `authorization_endpoint` 取得 authorization code 后，MUST 把 `code`、`code_verifier`、`state`、`nonce`、`redirect_uri`、`issuer`、`client_id` 与设备 proof 绑定到 `SessionGrantRequestBody.proof` 的 `proof_kind="oidc_code_exchange"` 分支并提交给 Account Authority 的 `session-grants`。v1 规定由 Account Authority 代客户端调用 issuer `token_endpoint`，校验 discovery、`id_token` / userinfo、`state`、`nonce`、`redirect_uri`、principal binding、device binding、audience 与 request canonical digest 后签发 `SessionGrantOutcome`。`/_arkret/gate/account/oidc/callback` 若由部署启用，只是浏览器 redirect landing / handoff endpoint，MUST NOT 返回 `SessionGrantOutcome`、`ak.session.grant` 或 Principal 本地 session material。

因此，同一 principal 的新设备加入流程 MUST 拆为两层：新设备的验证请求经 `ak.self.device_messages.command.send` 投递给旧设备，旧设备主要通过 `ak.self.account.stream.subscribe` 的 `delta.to_device.messages[]` 接收；用户确认和 SAS/QR transcript 成功后，授权落地经 `ak.gate.account.command.pair_device` 或等价 gate 操作完成。v1 core 不定义 `/_arkret/self/devices/pairing-requests*` 作为 canonical approval surface；部署私有审批面必须放在实现自己的 negative-space root 下，不得列入 v1 core conformance，也不得要求通用客户端依赖。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

路径风格约束：新增 HTTP path SHOULD 使用 kebab-case 资源名和清晰的资源/动作边界。现有 `/_arkret/self/device_messages`、`/_arkret/self/blob/get`、`/_arkret/self/agent-sidecar-threads:ensure` 是已注册 v1 binding 的命名例外；它们不构成新路径的命名模板。新增例外必须先进入 canonical operation catalog，并在本文件说明为什么不能使用常规资源路径。

新增顶层 REST 命名空间前，规范必须同步更新 `contract-catalog.json#operation_registry`、OpenAPI path、必要的 request/response schema refs、feature discovery 返回值和对应 conformance profile；`artifacts/reports/operation-schema-index.json` 由 pipeline 生成并用于复核 DTO 字段集合。实现不得用未声明路径绕过 canonical operation、capability、幂等、分页或错误语义。

#### 2.1.3 Conformance / Debug 命名空间（test-only，profile-gated，normative）

测试 harness、conformance runner、活体调试需要一些**非生产**观测 / 注入能力（例如直接读取内部 reducer cell 状态、强制推进 HLC、清空幂等缓存、dump seal DAG、回放固定 fixture）。这些能力 **MUST NOT** 伪装成协议生产面 operation，也 **MUST NOT** 复用 §2.1 表中任何生产 trust-surface 段（`self` / `gate` / `root` / `find` / `peer` / `open` / `edge`）。规范为它们保留**单一专用命名空间**：

```text
/_arkret/_conformance/*
```

- `_conformance` 段首字符 `_` 表明它**不是** §2.1 的生产 trust-surface classifier，而是 test-only 保留段。所有测试 / 调试 / fixture-replay / 内部状态注入 / 内部状态 dump 端点 MUST 落在该段下；实现 MUST NOT 在生产 trust-surface 段下新增此类端点。
- **暴露门（development-mode-gated，MUST）**：`/_arkret/_conformance/*` **仅在** 实现以 `development_mode=true`（canonical test-build 姿态标记，`GET /_arkret/describe` 顶层字段，见 [`service-surface.md` §3.0](./service-surface.md)）运行时暴露。**生产部署（`development_mode=false`）MUST NOT 路由该命名空间**：路由层 MUST 对 `/_arkret/_conformance/*` 返回与未知路径相同的 `404 unrecognized_endpoint`，不得进入业务逻辑，也不得在 `GET /_arkret/describe` 的 `supported_operations` / `supported_features` 中宣告。该命名空间下的 operation MUST NOT 进入 `contract-catalog.json#operation_registry` 的生产 operation 集，也 MUST NOT 出现在 OpenAPI 生产 binding 中。
- **生命周期（MUST）**：`_conformance` 端点是 ephemeral test affordance，不是稳定互操作契约。它们 MUST NOT 被任何对端实现作为协议依赖消费——通用客户端、Principal Server、Sync Service、federation peer、Applet、Push Gateway 等任何生产组件（含实现自身的产品 / 运维面）MUST NOT 调用、探测或依赖另一实现的 `_conformance` 端点。test build 之外的代码路径 MUST NOT 引用该命名空间。任一组件把 `_conformance` 端点当作生产能力消费即视为 profile violation。
- **test-only 能力集（normative 边界）**：以下类别属于 `_conformance` test-only 集——(a) 内部状态读出（reducer cell / seal DAG / bottom diagnostics / 幂等缓存内容的非授权裸读）；(b) 状态注入 / 强制推进（直接写 cell、强制 HLC、伪造 frontier、跳过 seal 覆盖）；(c) fixture replay / 确定性种子；(d) 时间 / 时钟 / 限流旁路；(e) 任何绕过 capability / Realm policy / history visibility / 签名校验的 inspection。生产面**永不**提供以上能力；需要协议级可观测性的生产场景（如 [`service-surface.md` §5.3](./service-surface.md) 的 `event_state` / `bottom` 暴露）走已注册的生产 operation，不走 `_conformance`。
- **conformance 验证自身**：test-build 姿态的 canonical 标记是 `development_mode=true`（[`service-surface.md` §3.0](./service-surface.md)），**不再**有独立的 `ak.profile.*` test-build profile——test build 不是对端可协商能力，不进入 `claimed_profiles` / `verified_profiles`、不构成 v1 core 互操作 profile、也不进入对端 fast-path 能力命中判断。`development_mode=true` 的部署 MUST NOT 同时对外宣告生产 `verified_profiles`（与 [`service-surface.md` §3.0](./service-surface.md) 的 `development_mode=true ⇒ verified_profiles=[]` 约束一致）。

§2.1.1 的"部署私有审批面必须放在实现自己的 negative-space root 下"是同一原则的另一面：私有**产品**面放实现自己的 root；test-only **调试 / conformance** 面放 `/_arkret/_conformance/*` 并受 `development_mode=true` gate。二者都不得污染生产 trust-surface 段，也都不得列入 v1 core conformance 的生产 operation 集。

#### 2.1.4 非 spec `/_arkret/*` 路径群边界（catalog completeness，normative）

§2.2 末条"实现不得用未声明路径绕过 canonical operation"是**强制**的 catalog-completeness 不变量。本节把它写实为可判定规则，并对未登记 `/_arkret/*` 路径群逐簇裁决归位，作为 conformance 判定基准。

**规则（MUST）**：任何在 §2.1 生产 trust-surface 段（`self` / `gate` / `root` / `find` / `peer` / `open` / `edge`）下被实现暴露、或被任一对端消费的 `/_arkret/*` path，MUST 解析到 `contract-catalog.json#operation_registry` 中已登记的 canonical operation（并具备对应 OpenAPI binding 与 request/response schema ref）。一项能力若不在 catalog 中，只有三条互斥的合规归属：

- **(a) 真协议能力** → MUST 先补 canonical operation（catalog + OpenAPI + §2.1 命名空间 + 对应 conformance profile）再暴露；在补齐前 MUST NOT 以未登记 `/_arkret/*` 路径作为事实协议面。
- **(b) 产品 / 运维 / 部署私有能力** → MUST NOT 占用任何 `/_arkret/*` 生产段，而是放实现自己的 negative-space root（实现私有，例如 `/_<impl>/*`），且 MUST NOT 列入 v1 core conformance 的生产 operation 集。
- **(c) test-only 调试 / conformance / fixture-replay** → 走 §2.1.3 的 `/_arkret/_conformance/*`，受 `development_mode=true` gate。

三者互斥；任一对端实现（含 conformance 测试面）MUST NOT 把未登记 `/_arkret/*` 路径当作协议依赖消费，而应改查已注册 operation 或对应实现私有面。本节与 §2.1.3 正交：(c) 处理 test-only 观测，(a)/(b) 处理生产能力的归属。

**路径群裁决（normative resolution）**。下表把未登记 `/_arkret/*` 路径形态逐簇归位；标注的 canonical operation / event 即该能力的唯一合规协议入口，其余形态按 (b) 归实现私有面。

A 类——真协议能力，**已由既有 canonical operation / event 覆盖，无需新增 operation**：

| 未登记路径形态 | canonical 归属 |
| --- | --- |
| session-grant 刷新 / 续期（`gate/auth/refresh` 等） | `ak.gate.account.command.refresh_session_grant`（`POST /_arkret/gate/account/session-grants/refresh`，§2.1.2） |
| self account-secret / 设备恢复运行态（`self/keys/recovery`） | `ak.self.keys.backups.command.unlock`（key backup 解锁）+ `ak.root.identity.recovery_session.{create,resource.get,submit_proof,complete}`（恢复挑战应答，[account-lifecycle.md](../identity/account-lifecycle.md)）；无独立 `self/keys/recovery` operation |
| holder 发起第三方邀请（`self/invites/third-party`） | `ak.invite.third_party` Event 经 `ak.self.events.command.submit` 摄取（[third-party-invites.md §3.1](./third-party-invites.md)）；invite token 铸造是 holder ↔ 验证服务的私有交互，**不**构成独立 `/_arkret/*` operation |

B 类——产品 / 运维能力，被实现误放进协议段，按 (b) 归位（治理归属原则同 §2.1.1：服务器 / 运维级能力走实现私有 negative-space root（例如 `/_<impl>/*`），日常治理走协议事件 + capability 闸门，不占用 `/_arkret/*` 命名空间）：

| 误址簇 | canonical 协议归属（若该能力本就是协议能力） | 误址形态归位 |
| --- | --- | --- |
| WebRTC / calls 信令面 | call 信令 `ak.call.signal` 走 ephemeral envelope（`ak.self.ephemeral.command.send`）；媒体凭证 `ak.self.call.media.exchange.issue_token`（`/_arkret/self/rtc/token`）+ `/_arkret/self/rtc/ice-config`；持久 call 状态 `ak.call.{state,recording.start,summary}` 走 self/events | 其余 call-setup / 私有信令旁路 → 媒体服务私有面 `/_<impl>/*`，不进 v1 core |
| moderation 审查者工作台运行态 | `ak.moderation.{decision,decision.lift,appeal.submit,appeal.review,appeal.decision,appeal.close}` 事件经 self/events，realm authz capability 闸门；report 经 `ak.self.moderation.command.report` | 残留实现私有 admin 路径（如 `/_<impl>/admin`）+ OAuth admin scope 入口下线 |
| relations / views / moves 直读 | Realm 作用域对象读（`/_arkret/self/realms/{realm_id}/spaces|strands|morphs`、`/_arkret/self/realms/{realm_id}/morphs/{morph_id}`）、`/_arkret/self/views/*`（extension surface，非 canonical truth source，须服务显式声明） | 越出已声明 read binding 的 relation/view/move 直读路径 → 实现私有面 |
| authz / grants compat 路由 | capability 经 `ak.capability.{grant,revoke,delegate}` 事件 + `ak.self.policy.query.check` 预检 | 任何 `/_arkret/*` authz 直写 compat 路径 MUST NOT 存在；capability 一律走主 reducer 事件，相关运维只读视图归 `/_<impl>/*` |
| blob 直写形态（`blob/put`） | `ak.self.blob.upload.create`（`POST /_arkret/self/blob/upload`）+ tus 续传 binding | `blob/put` 直写归并到 upload operation，或声明为 per-operation HTTP 伴生 binding（[transport-bindings.md §6.1](./transport-bindings.md)），不得作未注册 canonical 路径 |
| 主权部署只读 realm/account 运维视图 | （无协议 operation——属运维级） | server info / stats 类只读运维视图 → 实现私有运维 / 产品面（例如 `/_<impl>/*`） |

### 2.2 端点契约规则

每个 REST endpoint 的规范定义必须至少包含：

- `operation_id` / canonical operation。
- Path 参数、query 参数和 request body 字段类型。
- 成功响应字段类型。
- 认证方式：`public_metadata`、`user_session`、`device_proof`、`service_signature`、`policy_token`、`applet_signature` 等。
- 访问限制：Realm membership、history visibility、capability、service delegation、namespace、plaintext visibility、rate limit、quota。
- 幂等键：写接口使用 `Idempotency-Key` header、`event_id`、`request_id` 或 canonical request hash。
- 失败时使用标准 error envelope。

JSON 示例只用于说明，不构成完整 schema。正式接口定义 MUST 以 `contract-catalog.json#operation_registry`、OpenAPI binding 和被 `request_schema_ref` / `response_schema_ref` 指向的 JSON Schema 为准；字段表只提供人类阅读索引，字段集合快照由 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json) 生成。

默认规则：

- 除明确标记为 `public_metadata` 的 describe / discovery 外，所有 endpoint MUST 认证。
- 认证只证明调用方身份；服务仍 MUST 执行 capability、Realm policy、history visibility、service delegation 和 revocation 检查。
- 服务间调用 MUST 使用 HTTP Message Signature 或等价 service DID proof，并绑定 method、target URI、content digest、origin service DID 和 destination service DID；shared ingress / 多租户 / allowlist endpoint 场景还 MUST 绑定 destination service endpoint digest。
- 服务间调用的 `origin` / `destination` 必须是 service DID，且必须与 DID Document service endpoint、目标 URL、Realm policy / service delegation 和签名 transcript 一致。
- 受保护 endpoint 不得接受 query string 中的 token、API key 或签名材料；临时下载 URL 只能使用短时效、单用途、可撤销的派生 token。
- 返回 `not_found` 的 endpoint MUST 对“不存在”和“存在但不可见”保持一致失败语义，除非调用方已有管理权限。
- 所有批量读取 MUST 支持 `limit` 上限，分页 cursor 必须是不透明 token。
- 路由层 MUST 对 `/_arkret/*` 下的未知路径返回 `404 unrecognized_endpoint`，对已知路径的错误 method 返回 `405 method_not_allowed`，且不得进入业务逻辑。

### 2.3 端点契约清单

类型简写：`did` 为 DID URI，`id` 为协议对象 ID，`cursor` / `token` 为 opaque string，`signature` 为 `{kid, alg?, sig}`，`proof` 为 DID / HTTP message / detached JWS proof。`events` 为 Event Envelope 数组。

| Endpoint | Request 类型 | Auth / 访问限制 | Success 类型 |
| --- | --- | --- | --- |
| `GET /_arkret/describe` | query: none 或 `service_type?`（必须是 `service-type-registry.json` 中 active 且 `valid_in` 含 `service_describe` 的值）。一个 public binding 只暴露一个角色时 MAY 省略；共享 binding 暴露多个角色时调用方 MUST 指定，省略返回 `missing_param`；指定未暴露/非法值返回 `invalid_param`。 | `public_metadata`；不得返回私有 topology、secret 或未授权 internal endpoint。 | role-scoped `ServiceDescribe`（`ak.schema.service_describe.v1`；`service_type` MUST 与 query 一致，`supported_operations` / profile / auth / limits / plaintext visibility 只描述该角色；必须含 `service_id`、`trust_domain`、claim-level 字段、`auth_metadata`、`plaintext_visibility`、`development_mode`，且 `development_mode=true` 时 `verified_profiles=[]`；Principal Server MUST 在 `auth_metadata.account_authority` 发布 Account Authority） |
| `GET /_arkret/root/identity/describe` | query: none | `public_metadata`；可限流。 | `ServiceDescribe`；identity-specific 能力通过 `supported_features` / `limits` / 扩展字段表达。 |
| `POST /_arkret/root/identity/resolve` | body `{did: did, requested_evidence_kinds?: string[]}` | `public_metadata`；private DID MAY require `user_session` 或 presentation proof。 | `{did_document, key_log_head?, seq?, receipts?, method_evidence?}` |
| `GET /_arkret/root/identity/document` | query `{did: did, version?: string}` | 同 `root.identity.query.resolve`。 | `{did_document, head_event_digest?, seq?, receipts?}` |
| `GET /_arkret/root/identity/log` | query `{did: did, cursor?: cursor, limit?: int}` | public DID 可公开；private / pairwise DID MUST require holder-approved proof。 | `{events[], next_cursor?, has_more}` |
| `POST /_arkret/root/identity/submit-did-operation` | body `{did: did, did_method: string, seq?: int, prev_event_digest?: string, operation: object}` | transport auth 只负责准入；控制授权完全由 `operation` 内 DID-method-native proof 决定。MUST 校验 `did_method` 与 DID method component 相等、完整 method history、原生 proof 与 head/sequence CAS；不支持的 method、通用 replace/patch/document fallback、stale head 与 sibling fork 均 fail closed。 | `{status, did, seq?, head_event_digest?, operation_ref?, receipts?}` |
| `POST /_arkret/root/identity/service-registrations:ensure` | body `ServiceRegistrationEnsureRequestBody {service_type, public_base, inception_operation, idempotency_key, previous_receipt?}` | `service_signature` 或部署受信 registration bearer；Provider MUST 验证 client-signed WebVH inception、registration key 与签名内 endpoint 一致性；transport credential 不替代 control proof。 | `ServiceRegistrationOutcome {service_id, did_document, version_id, registration_receipt, created}` |
| `GET /_arkret/root/identity/service-registrations` | query `{service_type: enum(principal_server,auth_server,identity_registry), public_base: canonical-url}` | `service_signature` 或部署受信 registration bearer；只读，不得创建或变更 identity。 | `ServiceRegistrationOutcome`；不存在返回 `did_not_found`。 |
| `GET /_arkret/root/identity/receipts` | query `{did: did, head: string}` | 同 DID 可见性；witness 可公开最小 receipt。 | `{receipts[], threshold_met?: boolean}` |
| `POST /_arkret/root/identity/recovery-policy` | body `ak.schema.recovery_policy.v1` | `user_session` bound to the principal/current device, or authorized recovery coordinator/service proof for that principal；MUST verify `auth_data.signed_fields`、签名权限、`version` 单调递增和 `supersedes` 链接。 | `schemas/recovery-policy.schema.json#/$defs/recovery_policy_publish_outcome` |
| `GET /_arkret/root/identity/recovery-policy` | query `{principal_id?: did}` | `user_session` bound to the principal/current device, or authorized recovery coordinator/service proof for that principal；不得枚举他人 recovery policy。 | `schemas/recovery-policy.schema.json#/$defs/recovery_policy_active_outcome`；`active_policy=null` 表示当前没有 accepted recovery policy。 |
| `GET /_arkret/self/events/describe` | query none 或 `{actor_id?: did, realm_id?: id}` | `public_metadata` 或 `user_session`；私有 frontier 需认证。 | `ServiceDescribe`；event schema / reducer / signature 能力通过 `supported_features`、`supported_profiles`、`limits` 或扩展字段表达。 |
| `POST /_arkret/self/events` | body 是 `EventSubmitEnvelope`（单事件）或 `{events: EventSubmitEnvelope[]}`（批量）；submit 输入 MUST NOT 携带 reducer-managed accepted-output 字段（如 `actor_kind` / `effective_scope`）。MUST NOT 使用 `{event: ...}` wrapper。 | `user_session` / `device_proof` / 当前 principal 授权的 delegated service signature；MUST 验证 actor DID、签名、capability、Realm policy、`actor_seq`、`prev_refs`、`refs[role=authorized_by]`。不得接受 federation peer wire。 | `{status, accepted[], duplicate[]?, rejected[]?, quarantine[]?, actor_frontier?, realm_frontier?, cursor?}` |
| `POST /_arkret/self/events/seals` | body `seal.schema.json` | `user_session` bound to the Seal signer device；调用方必须可见该 Realm，且 signer principal MUST 满足 predecessor governance state 的 `ak.component.notary.v1` 成员 / 门限规则；可见性与“设备属于调用方”都只是附加前置，不构成 notary 授权。Managed Agent PCR 仅在唯一 signed genesis 与 accepted Agent DID delegation 精确绑定 `(Agent DID, controller DID, realm_id, authorization_ref)` 且 purpose 覆盖 `principal_control_realm_recovery` 时，允许 controller 当前 active device 作为 delegated notary signer；service 不得代签。服务端 MUST 重算 Seal ID、完整 predecessor coverage、`delta`、`covered_event_digests`、`control_event_set_root`、`completeness_root`、`state_root` 与签名；B 模型 PCR bootstrap 的首个 Seal MUST 由 bootstrap device #1 签名并完整覆盖 `[ak.realm.create, ak.device.authorize]` 原子 unit；managed Agent PCR 首个 Seal MUST 由 controller device 签名并覆盖 create，后继 Seal MUST 覆盖 effectless `ak.mls.genesis`。该职责只能由 canonical operation 承载，MUST NOT 通过非注册端点或自定义 queue envelope 承载。 | `EventSealSubmitOutcome {seal_id, accepted_event_digests[], post_state_root}` |
| `GET /_arkret/self/events/{event_id}` | path `{event_id: id}` query `{include_payload?: boolean}` | Event 可见性按 Realm policy / history visibility / E2EE envelope 判断；不可见时返回 `not_found`。 | `{event, visibility?, receipts?}` |
| `POST /_arkret/self/events/resolve` | body `{event_ids?: id[], event_digests?: string[], include_payload?: boolean}` | 同 Event read；payload 可见性按 Realm policy / E2EE envelope 判断。 | `{events[], missing[], unauthorized[]?}` |
| `GET /_arkret/self/events` | query `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object, include_completeness?: boolean}` | 调用方必须对每个 selector 元素满足读取约束：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy。`realms[]` ∪ 内部、`actors[]` ∪ 内部、二者组合为交集。批次内顺序规则见 §3.3。`limit` 缺省为 100；服务端 MUST clamp 到本部署 self events query 上限（v1 参考实现上限 100）。`include_completeness=true` 仅在服务声明 `events_query_range_completeness` feature 时生效。 | `{events[], next_cursor?, prev_cursor?, has_more, range_completeness?}` |
| `POST /_arkret/self/events/query` | body `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object, include_completeness?: boolean}` | 同 `GET /_arkret/self/events`（`ak.self.events.query.scan` 的 HTTP POST/body binding variant，registry `binding_variant_of="ak.self.events.query.scan"`）。 | `{events[], next_cursor?, prev_cursor?, has_more, range_completeness?}`；语义与 GET 形态完全一致，仅 wire 形态从 query string 变为 JSON body。 |
| `GET /_arkret/self/events/subscribe` | query `{realms?: id[], actors?: did[], after?: cursor, catchup?: boolean}` | 同 `GET /_arkret/self/events` 的逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性边界。授权丢失通过 per-realm `unauthorized` 帧通知，不中断整条流。 | event stream frames `{kind: event\|frontier\|heartbeat\|catchup_complete\|epoch_rotation\|dropped\|resync_required\|unauthorized, realm_id?: id, cursor?: cursor, payload?: object, reconnect_after_ms?: int}` |
| `GET /_arkret/self/events/frontier` | query `{actor_id?: did, realm_id?: id}` | 返回调用方可见范围内 frontier；不得泄露不可见 Realm 或 private DID。`actor_id` 形响应为 `{actor_id, actor_seq, event_id?}`；没有可见 Event（包括未知或不可见 actor）时 MUST 返回同形的空 frontier `{actor_id, actor_seq: 0}`，不得用 `not_found` 作为正常 genesis 探测，也不得据此披露 actor 是否存在。非空 frontier 的 `actor_seq >= 1` 且 `event_id` MUST 存在。`realm_id` 形响应 `frontier` 为 Realm Seal view `{realm_id, seal_id, control_event_set_root, state_root, hlc?}`：这是 account client 铸造单 leaf Control Move `seal_basis`（`leaves=[seal_id]`）与 DataEvent `seal_ref` 的注册来源；对调用方自己的 principal control realm，Principal Server MUST 返回（已初始化 Realm 至少有 genesis Seal）。该来源不可用时客户端 MUST fail closed，不得伪造 basis。 | `{frontier, receipts?}` |
| `POST /_arkret/self/events/mls-governance-proof` | body `mls-governance-proof-bundle.schema.json#/$defs/proof_request`，必含 caller 本地已信任的 `trusted_anchor_seal_id` 与 `chunk_index`；chunk 0 禁止 `expected_bundle_digest`，后续 chunk 必须携带 | 只对已认证且可见的 Realm/scope 返回 `complete_control_state_v1` 的一个 manifest-committed chunk。服务端 MUST 从请求的精确 anchor 构造逻辑 `seal_path`，不得静默替换；无法桥接返回 409 `mls_governance_anchor_unreachable`。每响应 ≤4 MiB，逻辑 item bytes ≤256 MiB、chunks ≤1024，四类总项/单块项上限按 `scalability-constraints.md` §6；任一总界超限返回 422 `mls_governance_proof_bounds_exceeded`，不得部分返回。服务端 MUST 从同一 accepted Seal view 派生 `membership_frontier` 和全部治理根，调用方不得提交 root/frontier；任一 chunk commitment、covered Event、控制状态、Seal 路径、签名权限或 reducer profile 无法重建时 MUST fail closed。 | `mls-governance-proof-bundle.schema.json`，含 `proof_request_digest`、完整逻辑内容地址 `bundle_digest`、`chunk_manifest` 与一个 `chunk`；client 收齐全部块、重算 `chunks_root` / Seal roots 前不得接受。`accepted_seal_id` 不得单独作为 Bundle cache key。 |
| `GET /_arkret/peer/events/describe` | query none 或 `{realm_id?: id}` | `public_metadata` 可返回通用能力；Realm-specific 限制和 peer policy 细节需 service signature。 | `ServiceDescribe`；MUST 声明 `ak.peer.events.*` supported_operations、peer auth metadata 与 federation limits。 |
| `POST /_arkret/peer/events` | body `EventsSubmitFederationRequestBody {service_binding_ref, events[], idempotency_key?}` | `service_signature`；MUST 绑定 Source/Destination service DID、Source/Destination trust domain、Request-Canonical-Digest、Content-Digest 与 Idempotency-Key（若有），并验证 Realm policy / service binding 中的 `federation_peer` 角色。 | `EventsSubmitOutcome {status, accepted[], duplicate[]?, rejected[]?, quarantine[]?, actor_frontier?, realm_frontier?, cursor?, original_outcome?}` |
| `GET /_arkret/peer/events` | query `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object}` | `service_signature`；调用方必须是每个 selector 所属 Realm 的授权 federation peer。服务端按 Realm policy、history visibility、reference disclosure 与 E2EE epoch policy 裁剪。 | `EventsQueryOutcome {events[], next_cursor?, prev_cursor?, has_more, snapshot_bootstrap?}` |
| `POST /_arkret/peer/events/query` | body `{realms?: id[], actors?: did[], before?: cursor, after?: cursor, order?: enum(default, ascending, descending), limit?: int, filters?: object}` | 同 `GET /_arkret/peer/events`（`ak.peer.events.query.scan` 的 HTTP POST/body binding variant，registry `binding_variant_of="ak.peer.events.query.scan"`）。 | 同 `EventsQueryOutcome`。 |
| `POST /_arkret/peer/events/resolve` | body `{event_ids?: id[], event_digests?: string[], include_payload?: boolean, realms?: id[]}` | `service_signature`；调用方必须是目标 Event 所属 Realm 的授权 federation peer；不可见或禁止 disclosure 的 Event 返回 missing / unauthorized，不得泄露 payload。 | `EventsResolveOutcome {events[], missing[], unauthorized[]?}` |
| `GET /_arkret/peer/events/frontier` | query `{realm_id: id}` | `service_signature`；调用方必须是该 Realm 的授权 federation peer；响应 MUST 由目标 service DID 签名并绑定 observed frontier。 | `EventsFrontierFederationPeerState {realm_id, heads[], max_hlc?, frontier_root, actor_seq_upper_bounds?, witness_receipts?, observed_at, issuer, signature}` |
| `POST /_arkret/peer/invites` | body `schemas/invite-delivery-request.schema.json` | `service_signature`；`Destination-Service-ID` MUST 等于 `invite_address.recipient_service_id`；接收方必须验证 `invite_event.kind=ak.invite.create`、`payload.invitee == invite_address.subject_id`、`introduction_evidence` 与 subject 私有 `invite_receive_policy`。 | `schemas/invite-delivery-request.schema.json#/$defs/invite_delivery_outcome`；响应只给 generic receive status，不泄露 subject 是否存在。 |
| `POST /_arkret/self/ephemeral` | body `ak.schema.ephemeral_envelope.v1` (`kind` ∈ `ak.presence` / `ak.typing` / `ak.receipt.read` / `ak.call.signal`) | `user_session` 或 service signature；actor 必须可在 `realm_id` 的 ephemeral channel 中广播该 kind，并持有对应 `ak.presence.broadcast` / `ak.typing.broadcast` / `ak.receipt.broadcast` / `ak.call.signal.send` action。 | `{accepted: true, kind, realm_id, dispatched_to?, server_received_at?}`；不生成 Event ID、不推进 actor_seq / Realm frontier。 |
| `POST /_arkret/self/rtc/token` | body `{realm_id: id, call_id: id, actor_id: did, device_id: id, focus_id: string, capability_refs?: id[], desired_media?: object}` | `user_session` 或 device proof；调用方 MUST 持 `ak.call.join`，并根据 `desired_media` 持 `ak.call.screen_share` 等子 capability；token issuer DID MUST 出现在 `ak.realm.media_service.service_id` 锚定列表；当 `ak.call.state.session_focus` 已存在，请求的 `focus_id` MUST 等于该值（否则 `focus_mismatch`）。 | `{focus_id, type, connect_url, backend_token, participant_identity, participant_binding, expires_at, service_signature}`；`expires_at - now ≤ 600s`（SHOULD ≤ 300s）。`participant_binding.scheme="ak.media.participant_binding.v1"`，覆盖 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)`。媒体服务 token exchange；详见 [`../crypto-media/media-service-binding.md` §3](../crypto-media/media-service-binding.md)。 |
| `GET /_arkret/self/account/viewer` | query none | `user_session` bound to principal/device。返回当前 holder 的账号主体投影，不是服务能力 describe。 | `AccountView {principal_id, primary_handle_claim?, primary_handle_claim_ref?, handle_claim_digests?, state, devices[], profile?}`；不得返回未签名裸 `handle` 作为权威身份。 |
| `GET /_arkret/self/account/subscribe` | query `{after?: cursor, catchup?: boolean, filter?: object}` | `user_session` bound to principal/device。聚合账号视角 delta(跨 Realm frontier、to_device、device_lists、account_data、presence、unread / notification counts)，不是裸事件读；presence 广播必须走 `POST /_arkret/self/ephemeral`。 | `application/x-ndjson` 返回 `AccountSubscribeFrame` 流，frame kinds: `delta` / `catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`;`dropped` / `resync_required` 可带 `reconnect_after_ms`。 |
| `POST /_arkret/self/account/profile` | body `AccountUpdateProfileRequestBody {patch}`；`patch` 为 `ak.patch.v1`，路径仅限 `display_name` / `avatar_blob_ref` / `profile_fields.<key>` | `user_session` bound to principal/device。Actor Profile 字段语义以 [`profiles-presence.md` §2.2](../discovery/profiles-presence.md) 为准；协议路径不接受 `avatar_url`、`handle`、lifecycle、principal、actor_kind、accountability 或 auth 字段。 | `AccountUpdateProfileOutcome {profile: ActorProfile}`；服务端 MUST 写入或等价产生 `ak.profile.update` / Actor Profile projection。 |
| `POST /_arkret/self/account/cursor/revoke` | body `{cursor: cursor, reason_code: string, revoke_scope?: enum(this_cursor,same_device,same_session)}` | `user_session` bound to principal/device；high-assurance optional profile。 | `{revoked: boolean, expires_at: datetime}`；撤销命中后的 cursor 使用返回 `cursor_revoked`，不得推进任何 server-side state。 |
| `GET /_arkret/self/account/describe` | query none | `public_metadata` 或 `user_session`；私有 limits 可认证后返回。 | `ServiceDescribe`；私有 frontier 只能作为认证后扩展字段返回。 |
| `POST /_arkret/self/contacts/request` | body `schemas/contact-operations.schema.json#/$defs/contact_request_request_body` | `user_session` bound to requester principal；requester 只能写自己的 contact request fact 与 requester-side consent grant。 | `schemas/contact-operations.schema.json#/$defs/contact_request_outcome`；投递签名 request envelope 给 target，不能替 target 写 consent 或 accepted fact。 |
| `POST /_arkret/self/contacts/respond` | body `schemas/contact-operations.schema.json#/$defs/contact_respond_request_body` | `user_session` bound to request target；accept 同步写 target-controlled consent grants。 | `schemas/contact-operations.schema.json#/$defs/contact_respond_outcome`；reject 不写 consent。 |
| `GET /_arkret/self/contacts` | query `{state?: enum, cursor?: cursor, limit?: int}` | `user_session` bound to holder principal；只返回 holder 可验证 contact projection 与本地备注合并视图。 | `schemas/contact-operations.schema.json#/$defs/contact_list`；`effective_scopes[]` 若出现必须等价于 `bidirectional_scopes[]`。每个 human contact 的 `agents[]` 是 viewer-specific、fail-closed 的可直聊 native personal agent 投影：agent 必须 accountable to 该 contact、lifecycle active，且与 viewer 的 accepted contact / `direct_message` consent 当前有效；其 `avatar_blob_ref?` 来自该 agent 的 Actor Profile；不得从公开 selector、共同 Realm 或历史 membership 推断。 |
| `POST /_arkret/self/contacts/tombstone` | body `schemas/contact-operations.schema.json#/$defs/contact_tombstone_request_body` | `user_session` bound to holder principal；默认只撤销 contact-managed active consent dots。 | `schemas/contact-operations.schema.json#/$defs/contact_tombstone`；不得默认撤销同 peer 的独立组织 invite 授权。 |
| `POST /_arkret/self/circles` | body `schemas/circle-operations.schema.json#/$defs/circle_create_request_body` | `user_session`；调用方必须对 `realm_id` 持创建 Circle 的能力；`encryption_profile=none` 仅当父 Realm policy floor 允许明文。 | `schemas/circle-operations.schema.json#/$defs/circle_view`；构造 `ak.circle.create` 走本地 accept 管线；reducer-locked 字段(`mls_group_ref` / `state`)由 reducer 产生，不接受 actor 提交。 |
| `GET /_arkret/self/circles` | query `{realm_id: id}` | `user_session`；按 Circle directory visibility 逐条裁剪；`members` 可见性 Circle 的非成员 MUST NOT 见到该 Circle。 | `schemas/circle-operations.schema.json#/$defs/circle_list`。 |
| `GET /_arkret/self/circles/{circle_id}` | path `{circle_id: id}` | `user_session`；Circle 不可见时返回 `not_found`,不泄露存在性。 | `schemas/circle-operations.schema.json#/$defs/circle_view`。 |
| `POST /_arkret/self/circles/{circle_id}/members` | path `{circle_id: id}` body `schemas/circle-operations.schema.json#/$defs/circle_member_request_body` | `user_session`；激活他人需 `ak.circle.member.manage`(narrowed 到该 Circle)且目标已是父 Realm joined 成员(strict-subset 不变量);自助 join 由 `join_rule` 决定。 | `schemas/circle-operations.schema.json#/$defs/circle_membership_outcome`;构造 `ak.circle.member.state`。 |
| `DELETE /_arkret/self/circles/{circle_id}/members/{actor_id}` | path `{circle_id: id, actor_id: did}` | `user_session`；移除自己或(持 `ak.circle.member.manage` 时)他人。 | `schemas/circle-operations.schema.json#/$defs/circle_membership_outcome`;构造 `ak.circle.member.state`(`membership=leave`)。 |
| `POST /_arkret/self/circles/{circle_id}/scope-rotate` | path `{circle_id: id}` body none | `user_session` + Circle scope 管理能力。 | `schemas/circle-operations.schema.json#/$defs/circle_scope_rotate_outcome`;不得在未真正更换密钥学 scope 时确认轮转;MLS 级联未端到端打通前返回 `unsupported_feature`(501)。 |
| `POST /_arkret/self/circles/{circle_id}/archive` | path `{circle_id: id}` body `schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body`(可选) | `user_session` + Circle 管理能力。 | `schemas/circle-operations.schema.json#/$defs/circle_view`;构造 `ak.circle.archive`,非法转换由 reducer 以 `circle_not_active` 拒绝。 |
| `POST /_arkret/self/circles/{circle_id}/restore` | path `{circle_id: id}` body `schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body`(可选) | `user_session` + Circle 管理能力。 | `schemas/circle-operations.schema.json#/$defs/circle_view`;构造 `ak.circle.restore`,非法转换由 reducer 以 `circle_not_archived` 拒绝；若存在 pending MLS remove proposal，恢复写入前必须先完成对应 rotate。 |
| `POST /_arkret/self/circles/{circle_id}/tombstone` | path `{circle_id: id}` body `schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body`(可选) | `user_session` + Circle 管理能力。 | `schemas/circle-operations.schema.json#/$defs/circle_view`;构造 `ak.circle.tombstone`(terminal),响应回显终态且 `members` 为空。 |
| `POST /_arkret/self/direct-conversations/resolve` | body `schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_request_body` | `user_session`；MUST 同时验证 accepted contact 与 target holder 的 active `direct_message` / `any` consent。 | `schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_outcome`；create=true 时幂等创建 canonical DM Realm + main Strand + binding。 |
| `GET /_arkret/self/snapshot/head` | query `{realm_id: id}` | Realm read；响应是完整 Snapshot manifest（schema_ref [`schemas/snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json)，不含 chunk bytes），manifest 必须签名且签名 transcript 可由响应自身完整重建。high-assurance profile MUST 校验 `authority_binding` 证明 `created_by` 在 `created_at` 时被 Realm policy / witness quorum 授权。无法产出真实签名 manifest 的部署 MUST NOT 宣告本操作并 MUST 返回 `not_implemented`，不得伪造证明字段。 | `ak.schema.snapshot.v1`（manifest，含 `chunks[]` 下载描述符） |
| `GET /_arkret/peer/snapshot/head` | query `{realm_id: id}` | `service_signature`；调用方必须是该 Realm 的授权 federation peer；响应、签名、frontier、authority_binding 与 not_implemented 规则同 `ak.self.snapshot.query.manifest_head`（schema_ref schemas/snapshot.schema.json）。 | `ak.schema.snapshot.v1`（manifest，含 `chunks[]` 下载描述符） |
| `GET /_arkret/self/realms/{realm_id}/spaces` | path `{realm_id: id}`; query `{include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | `user_session` 或服务签名；调用方必须满足该 Realm 的 metadata/read 可见性。 | `{realm_id, spaces[], total, next_cursor?, has_more}`；`spaces[]` 行含 `space_id, realm_id, kind, title, parent_space_id?, rank?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `GET /_arkret/self/realms/{realm_id}/strands` | path `{realm_id: id}`; query `{include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `ak.self.space.query.list`。 | `{realm_id, strands[], total, next_cursor?, has_more}`；`strands[]` 行可含从 plaintext-visible `metadata.title` / `metadata.summary` 派生的 `title?` / `summary?`，以及 `strand_id, realm_id, state, state_changed_at?, title?, summary?, board_space_id?, list_space_id?, rank?, assigned_actor_ids?, assigned_to_relations?, created_by?, created_at?, updated_at?`。`board_space_id/list_space_id/rank` 是从 `ak.component.strand.position.v1` cell 派生的只读 view 字段，不是 Strand object 的 canonical truth；`assigned_actor_ids` 是从当前可见 active `assigned_to` Relation 派生的只读 view 字段，`assigned_to_relations[]` 带 `{relation_id, actor_id}` 供客户端 tombstone 旧 assignment edge；空或省略表示对当前 caller 的投影为 unassigned；当 metadata 加密且服务端不可见时 `title` / `summary` MUST 省略或为 `null`。 |
| `GET /_arkret/self/realms/{realm_id}/morphs` | path `{realm_id: id}`; query `{include_terminal?: boolean=false, cursor?: cursor, limit?: int}` | 同 `ak.self.space.query.list`。 | `{realm_id, morphs[], total, next_cursor?, has_more}`；`morphs[]` 行含 `morph_id, realm_id, morph_type, title?, state, created_by?, created_at?, updated_at?, state_changed_at?`。 |
| `POST /_arkret/self/views/{view_id}/projection` | path `{view_id}` body `schemas/view.schema.json#/$defs/view_projection_request_body`（可为空对象） | `user_session` 或服务签名；调用方必须可读取目标 View 及其投影对象。 | `schemas/view.schema.json#/$defs/collection_projection_view`；只注册 `View{kind="collection"}` 的物化读取面。响应是派生结果，MUST 绑定 `frontier`，不得扩大底层对象可见性。 |
| `GET /_arkret/self/realms/{realm_id}/morphs/{morph_id}` | path `{realm_id: id, morph_id: id}` | `user_session` 或服务签名；调用方必须可读取该 document Morph 及返回的 relation/comment/cursor 子投影。 | `schemas/view.schema.json#/$defs/document_morph_projection_outcome`；单 document Morph 的派生读模型，不是真相源。 |
| `GET /_arkret/find/directory/describe` | query none | `public_metadata`；可限流。 | `ServiceDescribe`；directory resource / discovery capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /_arkret/find/directory/search-realms` | body `schemas/directory-operations.schema.json#/$defs/directory_search_realms_request_body` | discoverability + requester proof + policy filtering；隐藏资源不泄露存在性。 | `schemas/directory-operations.schema.json#/$defs/directory_realm_search_outcome` |
| `POST /_arkret/find/directory/resolve-realm` | body `schemas/directory-operations.schema.json#/$defs/directory_resolve_realm_request_body` | invite / restricted / secret Realm 按统一 `not_found` 失败。 | `schemas/directory-operations.schema.json#/$defs/directory_realm_resolution_outcome` |
| `POST /_arkret/find/directory/resolve-target` | body `schemas/directory-operations.schema.json#/$defs/directory_resolve_target_request_body` | 对象级地址解析（`resolve_realm` 泛化）；`invite` / `preview` token 必须按 target descriptor 与 effective link type 校验；未授权统一 `not_found`。详见 [`../discovery/object-addressing.md` §6](../discovery/object-addressing.md)。 | `schemas/directory-operations.schema.json#/$defs/directory_target_resolution_outcome`；preview token 成功时只返回 `ak.realm.preview_policy` 允许字段，除非另有 join routing 权限否则省略 `join_candidates[]`。 |
| `POST /_arkret/find/directory/search-organizations` | body `schemas/directory-operations.schema.json#/$defs/directory_search_organizations_request_body` | 仅返回公开或授权可发现组织。 | `schemas/directory-operations.schema.json#/$defs/directory_organization_search_outcome` |
| `POST /_arkret/find/directory/resolve-organization` | body `schemas/directory-operations.schema.json#/$defs/directory_resolve_organization_request_body` | 公开组织 DID 可解析不表示成员或拓扑公开。 | `schemas/directory-operations.schema.json#/$defs/directory_organization_resolution_outcome` |
| `POST /_arkret/find/directory/search-actors` | body `schemas/directory-operations.schema.json#/$defs/directory_search_actors_request_body` | 不得泄露 pairwise/private DID 或未披露组织账号。 | `schemas/directory-operations.schema.json#/$defs/directory_actor_search_outcome` |
| `POST /_arkret/find/directory/search-users` | body `schemas/directory-operations.schema.json#/$defs/directory_search_users_request_body` | `user_session`; 用于 mention autocomplete / contact request / 成员添加候选，必须受共同 Realm / directory policy 限制。请求词不得进入 URL、Referer 或明文 access log。 | `schemas/directory-operations.schema.json#/$defs/directory_user_search_outcome`；每项 MAY 含 `{handle, display_name?, verified?, subject?}`，但受限 handle 未授权时不得披露 DID / delivery binding。 |
| `POST /_arkret/find/directory/resolve-handle` | body `schemas/directory-operations.schema.json#/$defs/directory_resolve_handle_request_body` | 按 handle 双向验证规则；受限 / 组织 handle 需 presentation；返回 `member_delivery_binding` 时必须有 issuer claim / policy 证明。 | `schemas/directory-operations.schema.json#/$defs/directory_handle_resolution_outcome` |
| `POST /_arkret/find/directory/resolve-agent-selector` | body `schemas/directory-operations.schema.json#/$defs/directory_resolve_agent_selector_request_body` | 精确解析 `@<controller-handle>/<agent_slug>`；只在 requester / intent / audience / scope 可见时披露 agent DID 和 selector claim。失败必须与不存在不可区分。 | `schemas/directory-operations.schema.json#/$defs/directory_agent_selector_resolution_outcome` |
| `POST /_arkret/find/directory/list-handles-for-subject` | body `schemas/directory-operations.schema.json#/$defs/directory_list_handles_for_subject_request_body` | 按 subject visibility、issuer trust、audience、requester policy 和 intent 过滤；不得因为共同 Realm membership 单独披露受限组织 handle。 | `ak.schema.list_handles_for_subject_response.v1`：`{subject, claims[], primary_handle?, as_of, next_cursor?, has_more}`；`claims[]` 是当前 context 可见 signed handle claims，且 `claims[].subject` MUST 等于响应 `subject`。 |
| `POST /_arkret/self/blob/upload` | `multipart/form-data` body `schemas/blob-operations.schema.json#/$defs/blob_upload_request_body`，其中 `content` 是二进制 part。 | `user_session`; upload capability、quota、media policy；私有 blob 绑定 Realm / actor。 | `schemas/blob-operations.schema.json#/$defs/blob_upload_outcome` |
| `HEAD/GET /_arkret/self/blob/get` | query `{blob_ref: string}` headers `Authorization?`, `Range?`, `X-Arkret-Wait-For?` | 公开 blob 可匿名；header auth 路径必须验证 actor/device/Realm/purpose/expiry；除 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md) `ak.self.blob.command.presign` 的短 TTL bearer URL 例外外，不得 query string 认证。 | bytes 或 headers `{Content-Length?, Digest?, Cache-Control, Content-Type?, Content-Disposition?, Content-Range?}` |
| `POST /_arkret/self/blob/presign` | body `{blob_ref: string, max_age_seconds?: int (<=3600), purpose?: enum(media_inline, thumbnail, download)}` | `user_session`; 受 `ak.self.blob.command.presign` capability 控制；为单个 blob 签发短 TTL（默认 ≤ 5 min，硬上限 ≤ 1h）、单对象、只读、可撤销 pre-signed URL。仅供浏览器 `<img src>` / `<video src>` 等原生标签渲染受保护媒体；E2EE 附件 ciphertext MUST NOT 经此下发。 | `{url, expires_at, purpose}`；详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `POST /_arkret/edge/push/register-device` | body `{device_id: id, push_gateway: url, push_key: string, platform?: string, app_id?: string, display_name?: string, recipient_service_id?: did}` | `user_session` for same principal/device；registration 作用域绑定当前 Principal Server service DID；push_key 必须被加密或最小披露存储。 | `{ok: true, registration_id?, expires_at?}` |
| `POST /_arkret/edge/push/unregister-device` | body `{device_id: id, push_key?: string, app_id?: string}` | `user_session` for same device/principal 或 device revocation path。 | `{ok: true}` |
| `POST /_arkret/edge/push/notify` | header `Idempotency-Key?`（幂等键走 header，不入 body）；body `schemas/push-operations.schema.json#/$defs/push_notify_request_body`，顶层 `{notification, event_kind?, reason_code?, audit_envelope?}`；默认 `notification` 为 blind 形态 `{push_target_id, wakeup_kind, timing_profile_hint, push_hint?, counts?, route_tokens?, devices[]}`，可见通知必须使用互斥的 profile-gated visible 形态（必带 `event_id` / `realm_id` / `sender_actor_id`，可携带 `strand_id` / `message_id` / `sender_actor_display_name` / `strand_title` / `realm_title` / `user_is_target` / `priority` / `membership`）。`notification.content`、`body`、`preview`、`summary` 或任意 `content_*` 不属于 notify body。`timing_profile_hint`、`route_tokens` 与 `devices[].target_route_token` 是 gateway-internal 字段，MUST 在出 provider 前 strip；不得承载 raw Realm id、Circle id、`effective_scope` 或 actor DID allow-list。来源 / 目标服务 DID 走 `Source-Service-ID` / `Destination-Service-ID` header（`recipient_service_id` 复用 `Destination-Service-ID`）；`operation_id` 由 path 唯一确定，不入 body。 | 来自被授权 Sync 或通知服务的 `service_signature`；默认 MUST 遵守 `ak.profile.push_gateway.blind_wakeup.v1`，不得携带 event / realm / sender 识别字段；独立第三方 Push Gateway 的路由输入只能是 opaque route token。`visible_notification` 只在 profile、Realm policy、设备 opt-in 和 UI disclosure 同时满足时允许，且不放宽路由 token 边界。 | `schemas/push-operations.schema.json#/$defs/push_notify_outcome` |
| `POST /_arkret/self/device_messages` | header `Idempotency-Key` body `DeviceMessagesSendRequestBody {messages: {principal_id: {device_id: DeviceMessageTarget {kind, content, expires_at}}}}` | sender `user_session` / device key；目标必须是授权 device；fresh-device restricted session grant 仅可向同 principal 已授权设备发送 `ak.key.verification.*` bootstrap，不得发送 `ak.secret.*`。服务端入队前 MUST materialize `DeviceMessageEnvelope` 并绑定 `recipient_principal_id` / `recipient_device_id` / `expires_at`；按 `(sender, Idempotency-Key)` 幂等。验证消息不得作为持久 Event history；缺失、已过期或超过 TTL 上限的消息 MUST reject。 | `{ok: true, delivered?, unknown_devices?}` |
| `GET /_arkret/self/device_messages` | query `{after?: cursor, limit?: int}` | `user_session` bound to current device；只返回该 device 队列；`after=` 是只读位置，MUST NOT 触发队列删除。 | `{messages: DeviceMessageEnvelope[], ack_token?, next_cursor?, has_more, limited?, lost?}`；`messages` 非空时 MUST 返回 `ack_token`。 |
| `POST /_arkret/self/device_messages/ack` | body `{ack_token: string}` | `user_session` bound to current device；`ack_token` 绑定必须匹配当前 `(principal_id, device_id)`，unknown / 过期 / cross-binding 令牌返回 `invalid_param`（reason `invalid_ack_token`）且不得删除任何消息。 | `{ok: true, pruned_count?}`；累计单调确认，重复 / 旧令牌为 no-op；语义见 [`client-sync.md` §10.1](./client-sync.md)。 |
| `POST /_arkret/self/keys/upload` | body `{device_id: id, one_time_keys?: object, fallback_keys?: object, device_signature: signature}` | current device proof；key 必须链接 self-signing / principal key。 | `{one_time_key_counts, fallback_keys?}` |
| `POST /_arkret/self/keys/query` | body `{device_keys: {principal_id: string[]}, timeout_ms?: int}` | `user_session`; 查询范围可按关系 / Realm 限制。 | `{device_keys, failures?}` |
| `POST /_arkret/self/keys/claim` | body `{one_time_keys: {principal_id: {device_id: algorithm}}}` | `user_session`; one-time key MUST 原子消费。 | `{one_time_keys, failures?}` |
| `PUT /_arkret/self/keys/backups/{backup_id}` | path `{backup_id}` body `ak.schema.key_backup.v1` | current device proof / DID proof / recovery proof；path 与 body backup id 必须一致。 | `{status, backup_id, ciphertext_digest}` |
| `GET /_arkret/self/keys/backups` | query `{series_id?: id, backup_class?: string, cursor?: cursor, limit?: int}` | `user_session` bound to current principal/device 或 recovery proof。 | `{backups[], next_cursor?, has_more}` |
| `POST /_arkret/self/keys/backups/{backup_id}/unlock` | path `{backup_id}` body `{proof: ak.schema.key_backup_unlock_proof.v1}` | 同 principal 当前授权 device、recovery policy 或授权组织恢复服务；MUST 附 fresh device proof，bearer token 单独到达 MUST 拒绝；unlock proof 校验见 `identity/key-management.md` §7.7.1。 | `ak.schema.key_backup.v1` |
| `DELETE /_arkret/self/keys/backups/{backup_id}` | path `{backup_id}` body `{proof, reason?}` | 高风险 device proof、DID proof 或 recovery policy proof。 | `{deleted: true, backup_id?}` |
| `POST /_arkret/root/identity/recovery-sessions` | body `ak.schema.recovery_session.v1#/$defs/recovery_session_create_request_body` | 创建 device recovery session；server 从已接受的 DID/delegation 状态推导并锁定 `identity_model`，MUST snapshot active recovery policy，以及 A 模型 accepted `ssk_generation` 或 B 模型 `current_device_generation_ref`、`device_generation_status`、canonical DID head 与完整 accepted Seal frontier；不得信任请求方自报 model/generation。签发 256-bit one-time challenge，TTL <= 900s。 | `ak.schema.recovery_session.v1` |
| `GET /_arkret/root/identity/recovery-sessions/{recovery_session_id}` | path `{recovery_session_id}` | 仅 session principal / requesting device / authorized recovery coordinator 可见；不得枚举他人 session。 | `ak.schema.recovery_session.v1` |
| `POST /_arkret/root/identity/recovery-sessions/{recovery_session_id}/proofs` | path `{recovery_session_id}` body `ak.schema.recovery_session.v1#/$defs/recovery_session_proof_submit_request_body` | proof MUST verify against the server-reconstructed canonical transcript and echo the session challenge. | `ak.schema.recovery_session.v1#/$defs/recovery_session_proof_submit_outcome` |
| `POST /_arkret/root/identity/recovery-sessions/{recovery_session_id}/complete` | path `{recovery_session_id}` body `ak.schema.recovery_session.v1#/$defs/recovery_session_complete_request_body` | 要求 `state=verified`，并严格按 server-locked model 分流：A 模型只接受已经 accepted 的 `ak.device.authorize` + `ak.device.list_update`；B 模型只接受已经原子 accepted 的 `[ak.device.reanchor, replacement ak.device.authorize]` 及其 Event Batch Receipt，复核 session snapshot 的 DID head/frontier、event id/digest 与 resulting generation。complete 不得自行补写、重签或部分提交这些 Event。 | `ak.schema.recovery_session.v1#/$defs/recovery_session_complete_outcome` |
| `GET /_arkret/self/authz/effective-grants` | query `{realm_id: id, subject: did, at?: string}` | subject 本人、Realm admin、authorized service；不得枚举无关 subject。 | `{grants[], state_digest?, evaluated_at}` |
| `GET /_arkret/self/authz/invites` | query `{realm_id?: id, subject: did 或 string, cursor?: cursor}` | subject 本人或 inviter/admin；secret invites 不可枚举。 | `schemas/authz-operations.schema.json#/$defs/authz_invite_list` |
| `POST /_arkret/self/authz/check` | body `{actor_id: did, action: string, resource?: object, context?: object}` | caller 必须是相关 actor、Events/Sync 预检查服务或 policy-authorized service。`authz/check` 是本地 capability projection / preflight / 诊断入口；其结果不得作为 Event `auth_context`、Policy Server obligation proof、reducer accept 依据或跨服务签名授权事实。需要动态 claim、approval、challenge、外部状态、签名 replay 防护或可写入审计链的策略判定时，调用方 MUST 使用 `ak.self.policy.query.check` (`/_arkret/self/policy/check`)。 | `{decision, matched_grants?, applied_constraints?, policy_results?, missing_proofs?, frontier?, freshness_state?, last_known_frontier_age_ms?, notary_status?, cache_expires_at?, reason_code?, retry_after_ms?, obligations?}` |
| `POST /_arkret/self/policy/check` | body `PolicyCheckRequestBody {request_id, realm_id, request_canonical_digest, action, actor_id, source, event_preview?, auth_context?}` | `policy_token` / `service_signature`; 只接收最小披露字段。 | `PolicyCheckOutcome {request_id, bound_to, decision, reason_code, expires_at, auth_state_digest, policy_frontier_digest, membership_frontier_digest, obligations?, signature}`。 |
| `GET /_arkret/self/realms/{realm_id}/links` | path `{realm_id: id}` query `{direction?: enum(outbound,inbound,both), link_kind_allow?: string}` | `user_session`。 | `schemas/realm-link-operations.schema.json#/$defs/realm_link_list`;从 `ak.realm.link` 投影;`link_kind_allow` 是逗号分隔的 canonical link kind 白名单。 |
| `POST /_arkret/self/realms/{realm_id}/links` | path `{realm_id: id}` body `schemas/realm-link-operations.schema.json#/$defs/realm_link_create_request_body` | `user_session`。 | `schemas/realm-link-operations.schema.json#/$defs/realm_link_mutation_outcome`;构造 `ak.realm.link`；一般有向环合法且遍历时以 visited-set 截断。self-reference / kind / payload 校验失败返回 422；self-reference 使用 `schema_violation` + `realm_link_self_reference`，非法 FSM 迁移使用 `failed_precondition` + `realm_link_invalid_transition`。 |
| `DELETE /_arkret/self/realms/{realm_id}/links/{target_realm_id}` | path `{realm_id: id, target_realm_id: id}` query `{link_kind?: string}` | `user_session`。 | `schemas/realm-link-operations.schema.json#/$defs/realm_link_mutation_outcome`;写 status=tombstoned 的 `ak.realm.link`;`link_kind` 缺省 `governed_by`。 |
| `POST /_arkret/self/realms/{realm_id}/archive` | path `{realm_id: id}` body `schemas/event-payload.schema.json#/$defs/realm_archive_payload` | `user_session` + `ak.realm.archive`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view`;构造 `ak.realm.archive`;`archived=false` 解除 archived facet。 |
| `POST /_arkret/self/realms/{realm_id}/freeze` | path `{realm_id: id}` body `schemas/event-payload.schema.json#/$defs/realm_freeze_payload` | `user_session` + `ak.realm.freeze`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view`;构造 `ak.realm.freeze`;`frozen=true` 使普通写入返回 `realm_frozen`,`frozen=false` 解除冻结。 |
| `POST /_arkret/self/realms/{realm_id}/tombstone` | path `{realm_id: id}` body `schemas/event-payload.schema.json#/$defs/realm_tombstone_payload` | `user_session` + `ak.realm.tombstone`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view`;构造 `ak.realm.tombstone`;MUST 携带 `successor_realm_id`，仅用于 successor 接续，不得用于无 successor 解散。 |
| `POST /_arkret/self/realms/{realm_id}/destroy` | path `{realm_id: id}` body `schemas/event-payload.schema.json#/$defs/realm_destroy_payload` | `user_session` + `ak.realm.destroy`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view`;构造 `ak.realm.destroy`;无 successor 的永久关闭 / 产品"解散 Realm"入口；后续普通写入返回 `realm_terminal_state`。 |

Realm lifecycle 操作以对应 lifecycle Event 被 Realm event log 接受为唯一生效点；`archive` / `freeze` 的解除由显式 `archived=false` / `frozen=false` Event 表达，不存在定时生效、自动解冻或 wall-clock 到期语义。
| `GET /_arkret/self/realms/{realm_id}/effective-policy` | path `{realm_id: id}` | `user_session`。 | `schemas/realm-link-operations.schema.json#/$defs/realm_effective_policy_outcome`;沿 `governed_by` / `inherits_policy_from` 祖先按 `ak.realm.inheritance_policy` 合并；无继承声明时 `inheritance_mode=none`(禁止隐式继承)。 |
| `GET /_arkret/self/realms/{realm_id}/policy-server` | path `{realm_id: id}` | `user_session`。 | `schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_view`;Realm 与 `governed_by` 祖先链都未声明时返回 `not_found`;`from_org_fallback=true` 表示继承所得。 |
| `PUT /_arkret/self/realms/{realm_id}/policy-server` | path `{realm_id: id}` body `schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_replace_request_body` | `user_session` + `ak.policy.manage`。 | `schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_view`;构造 `ak.realm.policy_server`;该 admin DTO 是 canonical payload(server_id/endpoint/public_keys/applies_to/fail_mode)的简化投影。 |
| `DELETE /_arkret/self/realms/{realm_id}/policy-server` | path `{realm_id: id}` | `user_session` + `ak.policy.manage`。 | 无响应体;tombstone per-Realm `ak.realm.policy_server` cell,调用方回退到 `governed_by` 链或本地能力检查。 |
| `GET /_arkret/self/realms/{realm_id}` | path `{realm_id: id}` | `user_session`;不可见返回 `not_found`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view`。 |
| `GET /_arkret/self/realms/{realm_id}/export` | path `{realm_id: id}` | `user_session`;调用方须有读取该 Realm 的授权。 | `schemas/realm-read-operations.schema.json#/$defs/realm_export`;`ak.export.realm.v1` 全量 event-log + operation dump;payload 可见性仍按 Realm policy。 |
| `GET /_arkret/self/realms/{realm_id}/moderation-policy/effective` | path `{realm_id: id}` | `user_session`。 | `schemas/realm-read-operations.schema.json#/$defs/realm_effective_moderation_policy`;组织继承的合并审核策略视图。 |
| `PUT /_arkret/self/realms/{realm_id}/moderation-policy` | path `{realm_id: id}` body `schemas/realm-read-operations.schema.json#/$defs/realm_moderation_policy_replace_request_body` | `user_session`;仅 Realm owner 可写。 | `schemas/realm-read-operations.schema.json#/$defs/realm_moderation_policy_document`;构造 `ak.realm.moderation_policy`;若 override 放宽了组织策略禁止的动作，需文档内嵌组织 approval，否则返回 `failed_precondition` 且 `reason_code=requires_organization_approval`。 |
| `GET /_arkret/self/consent/cells` | query none | `user_session`;只返回调用方作为 holder（或显式 holder controller）可读的私有 consent cell，peer 禁止读取。 | `schemas/consent-operations.schema.json#/$defs/consent_cell_list`。 |
| `GET /_arkret/self/consent/cells/{holder_did}` | path `{holder_did: did}` query `{peer: did, consent_scope?: enum}` | `user_session`;调用方 MUST 为 holder 或显式 holder controller，peer 禁止读取 dots / expiry / state。 | `schemas/consent-operations.schema.json#/$defs/consent_cell_view`;holder 视图中无 cell 返回 `not_found`。 |
| `POST /_arkret/self/consent/cells/{holder_did}/grant` | path `{holder_did: did}` body `schemas/consent-operations.schema.json#/$defs/consent_update_request_body` | `user_session`;调用方 MUST 有权写 holder consent(holder 或显式授权的 controller / agent)。 | `schemas/consent-operations.schema.json#/$defs/consent_cell_view`;构造 `ak.consent.grant` Control Move。 |
| `POST /_arkret/self/consent/cells/{holder_did}/revoke` | path `{holder_did: did}` body `schemas/consent-operations.schema.json#/$defs/consent_update_request_body` | `user_session`;同 grant 授权约束。 | `schemas/consent-operations.schema.json#/$defs/consent_cell_view`;构造 `ak.consent.revoke`;`consent_scope=any` 撤销级联所有具体 scope。 |
| `POST /_arkret/self/consent/request` | body `schemas/consent-operations.schema.json#/$defs/consent_request_request_body` | `user_session`;`peer_did` 缺省并 MUST 等于认证 actor；holder 不存在、policy deny、限速、静默丢弃与进入 quarantine MUST 不可区分。 | `schemas/consent-operations.schema.json#/$defs/consent_request_outcome`;只返回 opaque accepted-for-processing，不创建或返回 consent cell。 |
| `GET /_arkret/self/account_data` | query none | `user_session`。 | `schemas/account-data-operations.schema.json#/$defs/account_data_list`;`content` 服务端原样存储，对服务不透明。 |
| `GET /_arkret/self/account_data/{data_type}` | path `{data_type: string}` | `user_session`。 | `schemas/account-data-operations.schema.json#/$defs/account_data_entry`;未设置返回 `not_found`。 |
| `PUT /_arkret/self/account_data/{data_type}` | path `{data_type: string}` body `schemas/account-data-operations.schema.json#/$defs/account_data_replace_request_body` | `user_session`;controller-private registered type 拒绝 agent / applet / service principal。 | `schemas/account-data-operations.schema.json#/$defs/account_data_entry`;构造 `ak.account_data.set` actor-private 写;`content` 原样存储,canonical 编码与敏感键加密由 client 负责。 |
| `DELETE /_arkret/self/account_data/{data_type}` | path `{data_type: string}` | `user_session`。 | `schemas/account-data-operations.schema.json#/$defs/account_data_delete_outcome`;删除并向 holder 其他设备 fanout actor-private update。 |
| `GET /_arkret/self/read-cursors` | query `{realm_id?: id}` | `user_session`。 | `schemas/read-cursor-operations.schema.json#/$defs/read_cursor_list`。 |
| `POST /_arkret/self/read-cursors` | body `schemas/read-cursor-operations.schema.json#/$defs/read_cursor_advance_request_body` | `user_session`。 | `schemas/read-cursor-operations.schema.json#/$defs/read_marker_outcome`；构造 `ak.read_cursor.advance` actor-private 写；多设备按 HLC max + device_id tiebreak 收敛，不写入共享 Realm history。 |
| `POST /_arkret/self/moderation/report` | body `{realm_id: id, target_ref: id, report_reason_code: enum, description?: string, reporter: did, evidence_refs?: id[]}` | `user_session`; reporter 必须可见 target；report 仅对 moderators 可见。 | `{report_id, status, routed_to?}` |
| `POST /_arkret/self/applets/install/preview` | body `schemas/applet-install-operations.schema.json#/$defs/applet_install_preview_request_body` `{applet_package, effective_scope, approval_request}` | `user_session`; self/admin aggregate operation；只读预览，不写 Realm history。 | `InstallPlan`（`schemas/applet-install-plan.schema.json`）；返回 canonical `plan_digest`。 |
| `POST /_arkret/self/applets/install` | header `Idempotency-Key` body `schemas/applet-install-operations.schema.json#/$defs/applet_install_request_body` `{plan_digest, applet_package, effective_scope, approved_scopes, ...}` | `user_session`; self/admin aggregate operation；MUST 重算 plan，`plan_digest` 不匹配返回 `applet_install_plan_mismatch`；不创建 install 专用 durable Event。 | `schemas/applet-install-operations.schema.json#/$defs/applet_install_outcome` |
| `POST /_arkret/self/applets/{applet_id}/revoke` | path `{applet_id}` body `schemas/applet-install-operations.schema.json#/$defs/applet_revoke_request_body` `{effective_scope, reason_code, revoke_mode, proof?}` | `user_session`; self/admin aggregate operation；撤销 bound grants / widget tokens / delegated sessions；当 `revoke_mode` 包含 delegated sessions 时，`proof` MUST 签署由 active install 重建的 `ak.gate.account.command.revoke_session` applet selector。 | `schemas/applet-install-operations.schema.json#/$defs/applet_revoke_outcome` |
| `GET /_arkret/edge/applet/ping` | query none | `public_metadata` 或 `service_signature`；不得泄露 private namespace。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_ping_outcome` |
| `GET /_arkret/edge/applet/describe` | query none | `service_signature` SHOULD；public mode 只返回公开 capabilities。 | `ServiceDescribe`；applet protocols / namespaces / auth capability 放入 `supported_features` / `limits` / 扩展字段。 |
| `POST /_arkret/edge/applet/transactions` | header `Idempotency-Key` body `schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_request_body` | `service_signature`; Applet 必须验证每个 event signature、namespace 和 capability；按 `(source_service_id, Idempotency-Key)` 幂等。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_outcome` |
| `GET /_arkret/edge/applet/actors/{actor_id}` | path `{actor_id}` | `service_signature`; actor_id 必须命中 Applet actor namespace。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_actor_view` 或 `not_found` |
| `GET /_arkret/edge/applet/realms/{realm_id_or_alias}` | path `{realm_id_or_alias}` | `service_signature`; 必须命中 portal namespace 或授权查询。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_realm_view` |
| `GET /_arkret/edge/applet/protocols/{protocol}` | path `{protocol}` | 可 public_metadata；实例列表可要求授权。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_protocol_metadata` |
| `GET /_arkret/edge/applet/third_party/users` | query `{protocol, external_id, instance_id?}` | `service_signature`; 查询字段必须在 registration namespace 内。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_user_list` |
| `GET /_arkret/edge/applet/third_party/locations` | query `{protocol, external_id, instance_id?}` | `service_signature`; 查询字段必须在 portal namespace 内。 | `schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_location_list` |
| `POST /_arkret/self/rtc/ice-config` | body `schemas/media-operations.schema.json#/$defs/media_ice_config_request_body` | `user_session`; actor 必须有 call/media capability，Realtime Media Server 必须被 Realm policy 委托。 | `schemas/ice-config-response.schema.json` |
| `POST /_arkret/self/keys/keypackages/upload` | body `{principal_id, device_id, key_packages[], device_signature, expires_at?, strand_id?, mls_group_id?}` | `user_session` + 当前 device proof;每条 KeyPackage 必须 self-signed 并通过当前 device 签发。 | `{accepted, rejected?, key_package_refs?, available_count?}` |
| `POST /_arkret/self/keys/keypackages/claim` | body `{target_principal_id, intended_realm_id, requester, required_capabilities[], claim_nonce, expires_at, target_device_ids?, minimal_metadata_allowed?, timeout_ms?, strand_id?, mls_group_id?, proofs?}` | `user_session`;一次性 KeyPackage MUST 原子 claim(同 `ak.self.keys.command.claim`)。 | `{claims[], failures?, available_count?}` |
| `POST /_arkret/self/keys/keypackages/consume` | body `{key_package_refs[], consumer_device_id, signature, strand_id?, epoch?}` | `service_signature`(MLS group creator 通常是 service-side 调用) 或 `user_session`。 | `{consumed[], failures?}` |
| `POST /_arkret/self/keys/keypackages/revoke` | body `{key_package_refs[], device_id, signature, reason?}` | `user_session` + 当前 device proof;不可撤销已消费的 KeyPackage。 | `{revoked[], failures?}` |
| `POST /_arkret/find/directory/announce` | body `{resource_kind, resource_id, discovery_state, source_refs, as_of, principal_server_did, ttl_seconds?, supersedes_announce_id?}` | `user_session` 或 `service_signature` 视 resource_kind；principal/server MUST 签发 discovery state 与 ingest request。 | `{announce_id, indexed_at, effective_ttl_seconds, next_revalidation_after, warnings?}` |
| `POST /_arkret/find/directory/withdraw` | body `{resource_id, governance_proof, reason?, effective_at?}` | `user_session` 或 `service_signature`；必须由 resource governance key 证明撤销权。 | `{withdrawal_ref, acked_at}` |
| `POST /_arkret/find/directory/push/register` | body `schemas/directory-operations.schema.json#/$defs/directory_push_register_request_body` `{subscriber_did, resource_filter, webhook_endpoint, secret?, expires_at?}` | `user_session` 或 `service_signature`；directory 变更 push webhook 注册，仅作为 pull 模式优化，不替代 freshness 协议。 | `schemas/directory-operations.schema.json#/$defs/directory_push_register_outcome` |
| `POST /_arkret/gate/account/authentication-handoffs` | body `AccountHandoffRequestBody {request_id, proof}` + `DPoP` header | `proof_kind="oidc_code_exchange"`；Account Authority 代客户端换码并验证 issuer / client / redirect / state / nonce / PKCE，body holder signature 必须与 DPoP JWK 相同。按 `request_id` 幂等。 | `AccountHandoffOutcome {request_id, account_handle, account_handoff_grant, expires_at, allowed_operations, binding}`。`account_handle` 仅供 UI 显示和本地文件命名，不是 principal 身份或授权证据；`account_handoff_grant` 为 DPoP-bound opaque credential，不是 `ak.session.grant`；`binding.state` 为 `identity_creation_active | identity_creation_busy | bound`，active 分支携带 lease，bound 分支携带 `principal_id`。 |
| `POST /_arkret/gate/account/identity-binding-challenges` | body `IdentityBindingChallengeRequestBody {request_id, lease_id, lease_fence, did_operation}` | `Authorization: DPoP <account_handoff_grant>` + `DPoP`；必须是当前 lease holder / fence。Account Authority 验证完整未发布 operation、导出 principal/digest、持久化公开 checkpoint，并续租同一 holder。 | `IdentityBindingChallengeOutcome`；服务端生成、共享 durable store 持久化、单次使用且 ≤300 秒，绑定 account、holder jkt、lease/fence、principal、operation digest、audience、origin、trust domain 与 purpose。 |
| `POST /_arkret/gate/account/register` | body `AccountRegisterRequestBody {principal_id, display_name?, device_id?, proof?, identity_creation?, policy_evidence?}` | DID-first 分支使用 bootstrap / DID-bound / paired-device proof。account-first `identity_creation` 分支 MUST 使用 `DPoP <account_handoff_grant>` + matching DPoP，携带当前 lease/fence、原样 unpublished DID operation 与 fresh root control proof。对 `did:webvh`，proof key 必须从 entry 0 `parameters.updateKeys[0]` 取得，不能用 DID Document VM 或请求任意 key。 | `AccountRegisterOutcome {..., binding_receipt?}`。Account Authority 内部提交 operation，只在 `accepted` 或 byte-identical `duplicate` + verified head 后绑定；按 account/principal/operation digest 幂等。恢复秘密与 root private key 禁止进入请求。 |
| `POST /_arkret/gate/account/session-grants` | body `SessionGrantRequestBody {principal_id, device_id?, requested_scope?, proof}` | Account Authority。DID-bound / paired-device / passkey / OIDC / agent proof；另支持 `proof_kind="pre_registration_handoff"`，此分支必须用 `Authorization: DPoP <account_handoff_grant>` + matching DPoP。`principal_id` 对所有 proof kind 均必填并且必须已有 verified account binding；handoff 所属 service account 必须正好绑定该 principal。未知或尚未绑定时 MUST 返回 `principal_unknown`（404）。Account Authority MUST NOT 从 OIDC subject 派生或铸出 principal DID；首次 OIDC 最多建立 account handoff，客户端先按 [`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 完成 custody、entry 0 与 register。 | `SessionGrantOutcome {principal_id, device_id?, session_grant, expires_at, granted_scope?, scope_details?}`。这是客户端可见的单次登录结果；`session_grant` 随后以 `Bearer <ak.session.grant>` + `DPoP` 访问 `/_arkret/self/*`。Principal 本地 session provisioning 属 Account Authority 内部步骤，不存在第二个客户端可见的 Principal 本地凭据签发 endpoint。 |
| `POST /_arkret/gate/account/session-grants/refresh` | body `{grant_jwt, audience?, device_id, proof}` + `DPoP` header | DPoP holder proof MUST 证明持有 `grant_jwt.cnf.jkt` 所绑定的密钥（`ath` = 旧 grant、`htm`/`htu` 绑定本端点）；同时 `proof` MUST 是 fresh DID/device proof，覆盖 `principal_id`、`device_id`、`audience`、`request_canonical_digest`、`challenge`、`issued_at`、`expires_at`，且 `expires_at - issued_at <= 300s`;`device_id` MUST 匹配旧 grant 的持久绑定与 JWT claim。 | `SessionGrantRefreshOutcome {grant_id, grant_jwt, session_public_key, expires_at, audience, scopes, dpop_jkt, previous_grant_id}`。轮换出新 grant（同 subject/scope/audience、`cnf.jkt` 不变、新 minutes-to-hours expiry），旧 grant **single-use 立即吊销**。语义：grant 是会话续期凭证，但 soft logout 恢复不能只凭 holder proof 静默续期；必须叠加 fresh DID/device proof 才能恢复 active session。轮换 grant 的 `session_public_key` 绑定到证明所用的设备密钥，因此其会话私钥即设备私钥（服务端不另发会话私钥）。 |
| `POST /_arkret/gate/account/session-grants/revoke` | body 可省略，或 `SessionRevokeRequestBody {target_grant_id?, target_device_id?, all_sessions?, proof?}` | `user_session` 撤当前 session；跨 grant / device / all_sessions 需要 fresh DID/device proof 或显式 capability。三个 selector 互斥，target 必须属于当前 principal。 | `SessionRevokeOutcome {revoked_count, revoked_grant_ids?}`。撤目标 session grant（针对性吊销某个会话凭证）；不撤 device authorization、不终结 Auth Server `browser_session`、不隐式写 `ak.account.status`。整设备 hard logout 用下面的 `account/logout`。 |
| `POST /_arkret/gate/account/session-grants/introspect` (S2S) | body `SessionGrantIntrospectRequestBody {id? 或 grant_jwt?, audience?, proof?{challenge, proof_jwt}}` | `session_grant_introspection_bearer`(部署本地静态 bearer)或 admin scope。**read-only**:MUST NOT 消费 / 吊销 grant(消费 / 轮换是 `refresh` 的职责)。`proof` 是 S2S 可选附加确认；Principal Server 校验 `/_arkret/self/*` 时 MUST NOT 要求普通客户端发送额外 introspection proof header，持钥证明由同一请求的 `DPoP` 校验完成。 | `SessionGrantIntrospectOutcome {active, status, proof_required, one_time_use_consumed, grant?}`。RFC 7662 式 server-to-server 内省,Principal Server 校验所持 grant 时调用;`status` ∈ {active, revoked, expired, locked, suspended, audience_mismatch, proof_required, invalid_proof, not_found}(not_found / audience_mismatch 以 status 返回而非错误回包);`grant` 元数据 MUST 含 `cnf_jkt`(供 Principal Server 校验 `/_arkret/self/*` 每请求 DPoP,见 [`api-conventions.md` §3.3](./api-conventions.md)),并含 `session_public_key`(供 RFC 9421 PoP 校验),绝不含 grant JWT / refresh token / 会话私钥。`browser_session` finished 后 MUST 返回 inactive。见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md)。 |
| `POST /_arkret/gate/account/auth-sessions/logout` (S2S) | body `AuthSessionLogoutRequestBody {grant_jwt, logout_request_digest?, validated_at?, reason_code?}` | `session_grant_introspection_bearer` 认证族的部署内 S2S bearer；普通客户端 MUST NOT 调用；MUST NOT 复用客户端给 `account/logout` URL 铸造的 DPoP proof。 | `AuthSessionLogoutOutcome {ok, grant_chain_terminated, auth_session_logged_out}`。hard logout 的 Auth-side 子步骤:登出该 grant 所属 Auth-side session / `browser_session`，并终结其整条 grant 轮换链；此后 refresh MUST `session_logged_out`，introspection MUST inactive。不清 Principal-side 本地设备会话 / to-device / push。 |
| `POST /_arkret/gate/account/logout` (Account Authority) | body 可省略；`Authorization: Bearer <ak.session.grant>` + `DPoP` header | DPoP holder proof MUST 证明持有当前 `ak.session.grant.cnf.jkt` 绑定的密钥；`ath` 绑定该 grant，`htm`/`htu` 绑定本端点。Account Authority MUST 能定位 grant chain 与 principal device session。 | `{ok, revoked}`。普通 hard logout 的唯一客户端规范入口(`ak.gate.account.command.logout`):Account Authority MUST 内部终结 Auth-side session / grant 轮换链（split 部署使用上面的 `auth-sessions/logout` S2S 子操作），同时终结或持久化重试 Principal Server 本地 account session / 设备会话记录、drop 该设备待投递 to-device、移除 push registration。不发 `ak.device.revoke`、不擦 durable device authorization(重新登录即恢复),与仅撤会话令牌的 `revoke_session` 不同。见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md)。 |
| `POST /_arkret/gate/account/device-pair` | body `AccountDevicePairRequestBody {pairing_code, new_device_pubkey, challenge_signature, display_name?, device_metadata?}` | `user_session` + existing device proof + freshly minted 8-character pairing code(短 TTL, one-time, audience-bound to this Account Authority `gate_account_base` / origin); endpoint 与 session-grants 同一 Account Authority namespace；服务端 MUST 对 `(principal_id, source_device_id, target_origin)` 限速并防重放，同一 pairing transcript 累计 10 次失败后 MUST 锁定并永久失效。该操作是用户在旧设备完成 SAS/QR 验证后的准入落地，不是旧设备收取请求的轮询面。 | `AccountDevicePairOutcome {device_id, authorized_event_ref, device_grant?, key_backup_hint?}` |
| `POST /_arkret/gate/account/device-enroll` | body `AccountDeviceEnrollRequestBody {device_id, device_public_key, hpke_key, algorithms, actor_seq, bootstrap_create_event_id?, not_before?}` | `user_session`。托管（account-authority）设备入册：已认证 session 请求其 DID 文档指派的入册权威为**本 session 自己的设备**铸一条 `service_attested` `ak.device.authorize`；权威用其持久入册密钥签发（MUST NOT 使用 principal SSK 或 identity root），返回完整 Event，调用方原样提交 `POST /_arkret/self/events`。权威 DID 与 `authorization_ref` MUST 由 principal DID Document 按 accepted-at 时点解析指派，否则 `device_enrollment_authority_not_designated`。与 §2.1 的 `device-pair` 互斥：本端点 MUST 仅接受 `actor_seq=1`、同一 principal/account 的 verified identity-creation binding receipt 且不存在任何 active device；裸 session grant 或 `actor_seq>1` 不得增设第二台长期设备。后续设备必须走 `device-pair` 或 B 模型 recovery re-anchor。首设备由 [`../identity/key-management.md` §5.0.1](../identity/key-management.md) 的原子 bootstrap unit 绑定。 | `AccountDeviceEnrollOutcome {principal_id, device_id, authority_did, authorized_event}` |
| `POST /_arkret/gate/account/agent-key-pair` | body `{agent_id, verification_method, public_key, proof_of_possession, requested_scope_disclosure, runtime_attestation?, authorize_event}` + `Idempotency-Key=authorize_event.event_id` | `user_session` + pairing request。`requested_scope_disclosure` MUST 符合 `agent-requested-scope-disclosure.schema.json`，绑定当前 verifier/audience/单次 challenge，且完整 scope 重算 digest 必须匹配 authorize Event accepted-at Agent DID 中的公开 commitment；披露不得复制进 Event/通知/公开 history。commit 前 MUST 验证 controller-owned managed-PCR backup 对 pre-commit frontier 的 `pcr_recovery.status=ready`；否则返回 `agent_pcr_recovery_not_ready`，不消费 pairing handle，也不改动既有 key / grant。`verification_method` 的 DID 部分 MUST 与 `agent_id` bit-identical，不匹配 `failed_precondition` / `verification_method_principal_mismatch`。服务端必须从当前持久化 runtime request 重算 stable binding 与 controller-signed request digest，stale prompt fail closed；只有 `ak.agent.key.authorize` durable accepted 后才消费 handle 并终止 account notification。该 Event 推进 Agent PCR frontier 后，恢复投影 MUST 转为 `stale`，直至 post-commit backup accepted；不回滚本次成功 pairing，但阻断下一次 commit。runtime replacement 时，该 controller-signed Event 的 `payload.supersedes[]` MUST 精确列出全部既有 active authorization；reducer 接受该单一 Event 时原子 observe-remove 并记录 reason=`superseded_by_repairing`，不得由服务端合成独立 revoke Event。见 [`../identity/key-management.md` §3.6.1-§3.6.2](../identity/key-management.md)。 | `{ok: true, authorized_event_ref}` |
| `GET /_arkret/self/agents` | query `{cursor?, limit?, state?}` | `user_session` bound to controller principal；只列出调用方可管理的 native personal agent。 | `{agents[], next_cursor?, has_more}` |
| `POST /_arkret/self/agents` | body `{display_name?, slug, avatar_blob_ref?, requested_scope, accountability?, pairing_ttl_ms?}` | controller `user_session`，且 controller 必须已有 accepted recovery policy；服务端分配 Agent DID/PCR binding，在 Agent DID accepted inception history 的唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 只固定域分离 `requested_scope_digest`，完整 `requested_scope` 保持 controller-private，禁止写入公开 DID/history；在 controller PCR 仅写入 controller-owned accountability / selector facts，并创建 runtime pairing request，返回 `pcr_recovery.status=pending`。`requested_scope` 必填、创建后 immutable，是 Agent key/session 的全局硬上限而不是授权：内容 `actions[]` 只声明以后可由 Realm grant 的最大 action 集，operation/service resource 约束服务面，显式内容 resource selector 只可进一步收窄未来 grant 的资源范围。该 operation 不得从 `requested_scope` 物化任何 `ak.capability.grant`；后续 Agent key scope、Realm grant、participation 与 session request 可更窄但必须满足 actions/resources/constraints 子集规则并与 membership / Realm policy 按 AND 收窄。controller MUST 以 authenticated controller DID、返回的 Agent DID 和原始 scope 重算 digest；不匹配时不得继续 bootstrap，并在后续 pairing/grant admission 时通过私有 controller-signed disclosure 出示 scope。controller E2EE client 随后本地生成 Agent PCR MLS/genesis/Profile state（含请求中的 `display_name` / `avatar_blob_ref`，后者仍须满足 Blob media authorization）并上传 controller-owned recovery backup；服务端不得生成或暂存 MLS private state，不得代写 Agent PCR Profile，也不得在首次 pairing 前预写 `ak.agent.key.authorize`。`slug` 映射为 controller selector claim 的 `agent_slug`；同一 controller 下 active native agent selector 冲突必须 fail closed。 | `{agent_id, principal_control_realm_id, controller_authorization_ref, requested_scope_digest, pcr_recovery:{status:"pending"}, pairing_request_id, pairing_code?, expires_at}` |
| `GET /_arkret/self/agents/{agent_id}` | path `{agent_id}` | controller `user_session` 或 policy-authorized admin。 | `{agent, status, grants?, key_state?}`；`key_state.pcr_recovery` 投影 `pending` / `ready` / `stale` 与 accepted backup/frontier reference。 |
| `POST /_arkret/self/agents/{agent_id}/pause` | path `{agent_id}` body `{reason?}` | controller-only；暂停 agent 并拒绝新 agent session grant。 | `{ok: true, status: "paused"}` |
| `POST /_arkret/self/agents/{agent_id}/resume` | path `{agent_id}` body `{sidecar_exposure_ack?}` | controller-only；必须重新校验 controller/agent/key/grant freshness，并在 pause 期间新增 sidecar exposure 时要求显式确认。 | `{ok: true, status: "active"}` |
| `POST /_arkret/self/agents/{agent_id}/deactivate` | path `{agent_id}` body `{reason?}` | controller-only terminal transition；fan-out agent key revoke、capability revoke 与 runtime endpoint revoke。URL 路径与 op id `ak.self.agent.command.deactivate` 保持一致。 | `{ok: true, status: "deactivated"}` |
| `POST /_arkret/self/agents/{agent_id}/renew-pairing` | path `{agent_id}` body `{pairing_ttl_ms?}` | controller-only；对任何非 terminal agent 重开一次性 pairing handle，旧 handle 永久不可解析；`pending_runtime_key` / `pairing_expired` 走 bootstrap 重开，`active` / `paused` 走 runtime replacement（status / 既有 key / grant 在新配对完成前不变，完成时由单一 authorize Event 的精确 `supersedes[]` 原子替换）；两种分支都不得创建、撤销或重发 Realm grant；`deactivated` MUST 拒绝；slug 被同 controller 其他 active / open agent 占用时 MUST `failed_precondition`。响应以 `pairing_mode=bootstrap|replacement` 固化所选分支，并返回 immutable DID binding 的同一 `requested_scope_digest` 与当前 `pcr_recovery`（可能是 `pending` / `ready` / `stale`），但后续 pair commit 仅接受 `ready`。见 [`../identity/key-management.md` §3.6.1](../identity/key-management.md)。 | `{agent_id, principal_control_realm_id, controller_authorization_ref, requested_scope_digest, pcr_recovery, pairing_mode, pairing_request_id, pairing_code?, expires_at}` |
| `POST /_arkret/self/agents/{agent_id}/grants` | path `{agent_id}` body `{grant, requested_scope_disclosure}` | controller grant authority；grant subject 必须是该 agent principal，且不得超过 controller 可委托范围。admission verifier MUST 验证 controller-signed 私有 disclosure 与 accepted-at DID commitment，并禁止把完整 scope 写入 grant/Realm history。 | `{ok: true, grant_id}` |
| `DELETE /_arkret/self/agents/{agent_id}/grants/{grant_id}` | path `{agent_id, grant_id}` | controller grant authority；撤销或解绑 agent grant，后续 agent action proof fail closed。 | `{ok: true, revoked_at}` |
| `POST /_arkret/self/agent-sidecar-threads:ensure` | body `{controller_id, addressed_agent_ids?, context_ref}`；`context_ref={realm_id, strand_id, track_name?, message_id?}` 或 `{realm_id, relation_id}` | controller `user_session` + `ak.self.agent.sidecar_thread.command.ensure`；只允许创建 / 复用 `ak.profile.agent_sidecar_thread.v1` 的受限 Circle / Strand / Relation；`addressed_agent_ids[]` 仅影响本次通知 fanout，不是持久成员边界；在 eligibility、Circle membership active，且若 Circle 为 MLS-backed 则 MLS membership active 后，才 fanout notification/context。 | `{ok: true, private_circle_id, private_strand_id, private_relation_id, pending_member_reconciliations?}` |
| `PUT /_arkret/self/agents/{agent_id}/participation` | path `{agent_id}` body `AgentParticipationReplaceRequestBody {scope, selection}` | controller-only；设置 native personal agent 在指定 deployment / Realm / Circle / Strand scope 内的参与 selection；selection 不得超过 effective ceiling。 | `AgentParticipationReplaceOutcome {ok, effective_participation}` |
| `GET /_arkret/self/agents/{agent_id}/participation` | path `{agent_id}` query `{scope}` | controller 或该 agent 自身；读取 selection、ceiling 与 effective participation，用于 runtime 主动遵守 mention / act-on-behalf gate。 | `AgentParticipationGetOutcome {selection, ceiling, effective_participation}` |
| `POST /_arkret/gate/account/oidc/callback` | body `AccountOidcCallbackRequestBody {state, code, nonce?, redirect_uri?}` | 部署可选的 OIDC browser redirect landing / handoff endpoint；服务端 MUST 校验 `state` / `nonce` / `redirect_uri` 与配置的 issuer binding。该 endpoint MUST NOT 签发或返回 `SessionGrantOutcome`、`ak.session.grant` 或 Principal 本地 session material；客户端可见 grant 签发仍只走 `session-grants`。 | `AccountOidcCallbackOutcome {redirect_url}` |
| `POST /_arkret/open/invite-locators/resolve` | body `schemas/principal-locator.schema.json#/$defs/principal_locator_resolve_request_body` | locator token 从二维码 / 链接 URL fragment 或等价 OOB handoff 取得后放入 JSON body；服务端 MUST 对不存在、过期、撤销、策略拒绝返回不可枚举形态。 | `schemas/principal-locator.schema.json`；签名 `principal_locator`，不是 membership grant。 |
| `POST /_arkret/open/agent-pairing/resolve` | body `schemas/agent-operations.schema.json#/$defs/agent_pairing_resolve_request_body` | pairing token 从二维码 / 链接 URL fragment 或等价 OOB handoff 取得后放入 JSON body；服务端 MUST 对不存在、过期、撤销、策略拒绝返回不可枚举形态。 | `schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap`；只返回 6 字段 pairing bootstrap，不返回 scope payload。 |
| `POST /_arkret/open/agent-pairing/runtime-key-requests` | body `schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_request_body` | runtime 用 resolved bootstrap 中的 `pairing_code`、`pairing_request_id` 和本地 key proof-of-possession 提交待 controller 审批的 runtime key request；服务端 MUST 校验 pairing code、pairing 未过期、verification_method DID 与 `agent_id` 一致、PoP 绑定 request canonical digest。每个 open handle 最多一个 stable `ak.agent.runtime_key_binding.v1`：同 binding 重试保留 approval/notification id并更新请求；不同 binding MUST HTTP 409 `agent_runtime_request_conflict`，不得覆盖。 | `schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_outcome`；请求只创建/更新短期 approval 与 account notification，不激活 key。声明 `ak.feature.agent_runtime_approval_notifications.v1` 后 controller 由 account subscribe 发现，再读取 authenticated `agent_get` 并签 `ak.agent.key.authorize`。 |
| `POST /_arkret/open/agent-pairing/runtime-key-requests/status` | body `schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_request_body` | runtime 轮询 controller 审批结果；`pairing_request_id` + `pairing_code` + `agent_id` 三元组即查询凭证，MUST 全部放 JSON body；服务端 MUST 让「记录不存在」与「pairing_code / agent_id 不匹配」不可区分（同为 not_found）；pending 且已过期的 pairing MUST 报告为 `agent_status=pairing_expired`（懒过期）。每次 HTTP response MUST 携带 `Retry-After`；客户端至少等待该值，按 1s/2s/5s/10s 后最大 30s 退避并在 pairing 过期后停止。 | `schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_outcome`；审批通过后返回 `authorized_event_ref` 与授权 key 绑定（`authorized_verification_method` / `authorized_public_key_digest`）；runtime MUST 本地比对 digest，不一致按「已被其它 runtime 配对」处理，不得据此保存授权结果。 |
| `GET /_arkret/open/mimi/provider-directory` | query `{provider_did?, capabilities?: string[]}` | `public_metadata`;provider 列表本身公开。 | `{providers[]}` |
| `POST /_arkret/open/mimi/key-material` | body `schemas/mimi-operations.schema.json#/$defs/mimi_key_material_request_body` | `service_signature`(MIMI provider-to-provider) 或 `user_or_service`。 | `schemas/mimi-operations.schema.json#/$defs/mimi_key_material_outcome` |
| `POST /_arkret/open/mimi/strands/{strand_id}/update` | path `{strand_id}` body `schemas/mimi-operations.schema.json#/$defs/mimi_room_update_request_body` | `service_signature`。 | `schemas/mimi-operations.schema.json#/$defs/mimi_room_update_outcome` |
| `POST /_arkret/open/mimi/strands/{strand_id}/notify` | path `{strand_id}` body `schemas/mimi-operations.schema.json#/$defs/mimi_notify_request_body` | `service_signature`。 | `schemas/mimi-operations.schema.json#/$defs/mimi_notify_outcome` |
| `POST /_arkret/open/mimi/strands/{strand_id}/messages` | path `{strand_id}` body `schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_request_body` | `service_signature`;MIMI 跨 provider message。 | `schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_outcome` |
| `GET /_arkret/open/mimi/strands/{strand_id}/group-info` | path `{strand_id}` query `{epoch?, include_proof?}` | `service_signature` 或 `user_session` (member proof)。 | `schemas/mimi-operations.schema.json#/$defs/mimi_group_info_outcome` |
| `POST /_arkret/open/mimi/consent/request` | body `schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_request_body` | `service_signature` 或 `user_session`。 | `schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_outcome` |
| `POST /_arkret/open/mimi/consent/update` | body `schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_request_body` | `service_signature` 或 `user_session`。 | `schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_outcome` |
| `POST /_arkret/open/mimi/identifiers/query` | body `schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_request_body` | `service_signature` 或 `user_session`;不得用于枚举攻击,query MUST 限速。 | `schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_outcome` |
| `POST /_arkret/open/mimi/report-abuse` | body `schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_request_body` | `user_session` 或 `service_signature`;同 `ak.self.moderation.command.report` 互补。 | `schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_outcome` |
| `POST /_arkret/open/mimi/proxy-download` | body `schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_request_body` | `service_signature`;MIMI 桥接 blob 时使用；不接受 user_session。 | `schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_outcome` |

> **§2.3 表格作用域**: 上表是 v1 core 服务面的主要 HTTP operation endpoint 契约阅读视图(operation_id 的权威全集由 generated registry 视图 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 维护，本文不硬编码数字；一个 operation_id 对应多个 HTTP 别名时合并展示)。OpenAPI 是 **HTTP/JSON binding** 的机器可消费最终来源；operation id、event kind、schema id 与 profile id 的全局 canonical source 仍是 `contract-catalog.json` / 对应 registry；operation DTO 字段集合的生成索引为 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json)。未在本表展开的已注册 operation 仍以这些机读来源为准。

> **错误码映射**: 每个 operation_id 的 operation-specific 错误码集合（在通用 `unauthenticated` / `auth_expired` / `schema_violation` / `rate_limited` / `internal_error` / `service_unavailable` 等通用失败面之外）由 [`artifacts/registry/operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 给出。错误码语义见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。

#### 2.3.1 Wire-level JSON 示例

以下三段示例展示 §2.3 表中三类典型 binding。所有 fence 标 `schema=schemas/event-envelope.schema.json expect=valid`(canonical `ak.schema.event.v1` artifact),与 [`event-and-patch.md` §2.3](../models/event-and-patch.md) 的 canonical Event Envelope shape 一致。示例均为 DataEvent，因此携带顶层 `effects[]`、`seal_ref` 与 `auth_context`；Control Move 示例见 [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)。

**示例 A — `POST /_arkret/self/events`(单事件提交,`ak.message.create`)**:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "actor_seq": 4,
  "kind": "ak.message.create",
  "created_at": "2026-04-26T00:00:00Z",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["ak:event:019640ed-0000-7000-8000-000000000000"],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "causal_refs": ["sha256:3333333333333333333333333333333333333333333333333333333333333333"],
  "effects": [
    {
      "cell": "ak:cell:ak.component.strand.discussion.timeline.v1:ak:strand:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "append", "issuer_seq": 0, "value": { "message_id": "ak:message:019640ed-8000-7000-8000-000000000000" } }
    }
  ],
  "seal_ref": "ak:seal:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "auth_context": {
    "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "key_id": "device-1",
    "key_epoch": 1,
    "capability_refs": ["ak:grant:0196410c-0000-7000-8000-000000000000"]
  },
  "payload": {
    "strand_id": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "track_name": "discussion",
    "content": { "kind": "ak.content.text", "body": "Sample message" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:00:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

**示例 B — `GET /_arkret/self/events?realms=...&after=...&limit=2`(分页响应,`events[]` 中的一条 `ak.message.create`)**:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ak:event:019640ed-9000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zHuXvTbhiRsj2KEPE64TLhzG4:bob.example",
  "actor_seq": 7,
  "kind": "ak.message.create",
  "created_at": "2026-04-26T00:01:00Z",
  "hlc": "01970e589d34-0001-c00ff00f",
  "prev_refs": ["ak:event:019640ed-8500-7000-8000-000000000000"],
  "refs": [
    { "id": "ak:grant:0196410c-1000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "causal_refs": ["sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"],
  "effects": [
    {
      "cell": "ak:cell:ak.component.strand.discussion.timeline.v1:ak:strand:019640c6-8000-7000-8000-000000000000",
      "op": { "kind": "append", "issuer_seq": 1, "value": { "message_id": "ak:message:019640ed-9000-7000-8000-000000000000" } }
    }
  ],
  "seal_ref": "ak:seal:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "auth_context": {
    "did": "did:webvh:zHuXvTbhiRsj2KEPE64TLhzG4:bob.example",
    "key_id": "device-1",
    "key_epoch": 1,
    "capability_refs": ["ak:grant:0196410c-1000-7000-8000-000000000000"]
  },
  "payload": {
    "strand_id": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "track_name": "discussion",
    "content": { "kind": "ak.content.text", "body": "Reply" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:zHuXvTbhiRsj2KEPE64TLhzG4:bob.example#device-1",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:01:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

外层分页响应形如 `{events: [<示例 A>, <示例 B>], next_cursor: "<opaque>", has_more: true}`(`events[]` 顺序见 §3.3,`next_cursor` 永远朝更新方向)。

**示例 C — `GET /_arkret/self/events/subscribe`(NDJSON stream frame 的 `ak.reaction.add` payload)**:

每一帧为一行 JSON;`event` kind frame 携带完整 envelope:

```json schema=schemas/event-envelope.schema.json expect=valid
{
  "event_id": "ak:event:019640ee-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zCELkEydSckveKumo1eHsfN2G:carol.example",
  "actor_seq": 12,
  "kind": "ak.reaction.add",
  "created_at": "2026-04-26T00:02:00Z",
  "hlc": "01970e589d40-0002-c00fbeef",
  "prev_refs": ["ak:event:019640ed-9000-7000-8000-000000000000"],
  "refs": [
    { "id": "ak:grant:0196410c-2000-7000-8000-000000000000", "role": "authorized_by", "critical": true },
    { "id": "ak:event:019640ed-8000-7000-8000-000000000000", "role": "parent_event", "critical": false }
  ],
  "causal_refs": ["sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"],
  "effects": [
    {
      "cell": "ak:cell:ak.component.message.reactions.v1:ak:message:019640ed-8000-7000-8000-000000000000",
      "op": { "kind": "add", "value": { "actor_id": "did:webvh:zCELkEydSckveKumo1eHsfN2G:carol.example", "key": "+1" } }
    }
  ],
  "seal_ref": "ak:seal:sha256:0000000000000000000000000000000000000000000000000000000000000000",
  "auth_context": {
    "did": "did:webvh:zCELkEydSckveKumo1eHsfN2G:carol.example",
    "key_id": "device-2",
    "key_epoch": 1,
    "capability_refs": ["ak:grant:0196410c-2000-7000-8000-000000000000"]
  },
  "payload": {
    "target_ref": "ak:message:019640ed-8000-7000-8000-000000000000",
    "key": "+1"
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:zCELkEydSckveKumo1eHsfN2G:carol.example#device-2",
      "event_digest": "sha256:0000000000000000000000000000000000000000000000000000000000000000",
      "created_at": "2026-04-26T00:02:00Z",
      "jws": "eyJhbGciOiJFZERTQSJ9..signature"
    }
  ]
}
```

订阅外层帧形如 `{"kind":"event","realm_id":"ak:realm:...","cursor":"<opaque>","payload":<上面 envelope>}`,详见 §2.3 `ak.self.events.stream.subscribe` 行与 [`client-sync.md`](./client-sync.md) §12。

跨域 actor 验证响应（通过 `/_arkret/root/identity/resolve` 与 holder-approved presentation challenge 获得）只能作为缓存加速或辅助诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Realm policy；不得把对端"验证通过"当成最终授权依据。

### 2.4 字段级 Schema 索引

本节是 REST 端点的字段级人类索引。字段写法为 `name: type - 说明`。出现在“必填字段”列的字段为该索引中的 required 摘要；出现在“可选字段”列的字段为 optional 摘要。位置若非 body，会显式标注为 `path.`、`query.` 或 `header.`。机器契约已存在时，“约束”列必须指向 `request_schema_ref` / `response_schema_ref`；完整字段集合、required 性、closed/open 状态以 JSON Schema 和 pipeline 生成的 [`operation-schema-index.json`](../../artifacts/reports/operation-schema-index.json) 为准。字段顺序按 operation DTO 顺序：target / identity 字段、scope 字段、auth/proof 字段、option 字段、body/content 字段、result 字段、audit/time 字段。

规范性 operation contract 以 `artifacts/registry/contract-catalog.json#operation_registry` 为 canonical source；`artifacts/registry/operation-registry.json` 与 `artifacts/reports/operation-schema-index.json` 是其生成视图。本表、OpenAPI 与非 HTTP binding 均 MUST 从 canonical source 生成或通过 CI 校验；不得新增 catalog 中不存在的 `operation_id`，也不得在声明支持某 operation 时遗漏对应 catalog 条目。

#### 2.4.1 Binding completeness index

`binding_completeness` 由 operation registry 派生：声明 `request_schema_ref` / `response_schema_ref` 且 OpenAPI 指向同一 schema fragment 的 operation 为 `typed_schema`；绑定通用 `OperationRequest` / `OperationResult` body 的 operation MUST 声明 `generic_binding`，且 core-tier operation MUST NOT 使用 generic binding。

所有 v1 operation 均为 `typed_schema`。未列出的 operation 在 registry 中已经是 `typed_schema`、无 body 的 status response，或不使用 generic operation envelope。

| `operation_id` | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `ak.server.query.describe` | 无 | `query.service_type: string - 过滤服务类型` | `ServiceDescribe` | `public_metadata`; 不得返回私有拓扑或 secret。`trust_domain` 与 `plaintext_visibility` 必填；缺失时 callers MUST fail closed。 |
| `ak.root.identity.registry.query.describe` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流；identity-specific 字段只能作为扩展字段追加。 |
| `ak.root.identity.query.resolve` | `did: did - 待解析 DID` | `requested_evidence_kinds: string[] - 请求附加证据类型，如 key_log/receipts` | `did_document: object`; `key_log_head: id?`; `seq: int?`; `receipts: object[]?`; `method_evidence: object?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveOutcome。private / pairwise DID 可要求 presentation proof。 |
| `ak.root.identity.document.resource.get` | `query.did: did` | `query.version: string - 指定版本或 head` | `did_document: object`; `head_event_digest: string?`; `seq: int?`; `receipts: object[]?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityDocumentView。可见性同 `ak.root.identity.query.resolve`。 |
| `ak.root.identity.log.query.list` | `query.did: did` | `query.cursor: cursor`; `query.limit: int` | `events: object[]`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityLogListOutcome。private / pairwise DID MUST 要求 holder-approved proof。 |
| `ak.root.identity.command.submit_did_operation` | `did: did`; `did_method: string`; `operation: object` | `seq: int`; `prev_event_digest: string` | `status: enum(accepted,duplicate,pending)`; `did: did`; `head_event_digest: string?`; `seq: int?`; `operation_ref: string?`; `receipts: object[]?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitOutcome。`did_method` 不含 `did:` 前缀且必须匹配 DID；`operation` 必须携带完整 method-native control proof，统一 wrapper 不得另造授权 proof 或降格为通用 `patch`；transport auth 不替代控制权。幂等键由 native operation id / seq / canonical bytes 决定；相同标识不同内容、stale head 或 sibling fork 必须 fail closed。 |
| `ak.root.identity.service_registration.command.ensure` | `service_type: enum(principal_server,auth_server,identity_registry)`; `public_base: canonical-url`; `inception_operation: ServiceWebvhInceptionOperation`; `idempotency_key: string` | `previous_receipt: ServiceRegistrationReceipt or null` | `service_id: did`; `did_document: ServiceDidDocument`; `version_id: string`; `registration_receipt: ServiceRegistrationReceipt`; `created: boolean` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationEnsureRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationOutcome。幂等对象是 canonical `(service_type, public_base)`；Provider MUST 以数据库唯一约束和同事务先查后建保证并发安全，且必须扫描现存托管 document 阻止 mapping 丢失后的第二 DID。 |
| `ak.root.identity.service_registration.resource.get` | `query.service_type: enum(principal_server,auth_server,identity_registry)`; `query.public_base: canonical-url` | 无 | 同 `ServiceRegistrationOutcome`，`created=false` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationOutcome。只读诊断；不得隐式 ensure。 |
| `ak.root.identity.receipts.query.list` | `query.did: did`; `query.head: string` | 无 | `receipts: object[]`; `threshold_met: boolean?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityReceiptListOutcome。只公开最小 witness receipt。 |
| `ak.root.identity.recovery_policy.command.publish` | body `ak.schema.recovery_policy.v1` | 无 | `ok: true`; `policy_id: id`; `principal_id: did`; `version: int`; `accepted_at: datetime` | request_schema_ref=schemas/recovery-policy.schema.json; response_schema_ref=schemas/recovery-policy.schema.json#/$defs/recovery_policy_publish_outcome。发布 genesis 或 rotate recovery policy；server MUST verify `auth_data.signed_fields`、签名权限、`version` 单调递增和 `supersedes` 链接。 |
| `ak.root.identity.recovery_policy.resource.get` | 无 | `query.principal_id: did - 省略时解析认证主体` | `active_policy: object or null`; `principal_id: did?`; `recovery_policy_ref: object?`; `as_of: datetime?`; `control_frontier: object?` | response_schema_ref=schemas/recovery-policy.schema.json#/$defs/recovery_policy_active_outcome。读取当前 accepted recovery policy 投影；`active_policy=null` 是成功响应，表示尚无 accepted policy。 |
| `ak.root.identity.recovery_session.command.create` | body `create_request` | 无 | `session` | request_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_create_request_body; response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_state。server 从 accepted DID/delegation state 推导并锁定 `identity_model`；创建时 snapshot active recovery policy，以及 A 模型 accepted `ssk_generation` 或 B 模型 `current_device_generation_ref`、generation status、canonical DID head 与完整 accepted Seal frontier。请求方不得自报 model/generation。签发 256-bit one-time challenge，TTL <= 900s。 |
| `ak.root.identity.recovery_session.resource.get` | path `{recovery_session_id}` | 无 | `session` | response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_state。仅 session principal / requesting device / authorized recovery coordinator 可见；不得枚举他人 session。 |
| `ak.root.identity.recovery_session.command.submit_proof` | path `{recovery_session_id}`; body `proof_submit_request` | 无 | `proof_submit_response` | request_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_proof_submit_request_body; response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_proof_submit_outcome。proof MUST 对 server-reconstructed canonical transcript 校验并回显 session challenge。 |
| `ak.root.identity.recovery_session.command.complete` | path `{recovery_session_id}`; body `complete_request` | 无 | `complete_response` | request_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_complete_request_body; response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_complete_outcome。要求 `state=verified` 并按 server-locked model 分流：A 只引用 accepted authorize + list-update；B 只引用原子 accepted reanchor + replacement authorize unit 及 Event Batch Receipt，并复核 snapshot/head/frontier/id/digest/result generation。complete 不得自行合成、重签或部分提交 Event。 |
| `ak.self.events.query.describe` | 无 | `query.actor_id: did`; `query.realm_id: id` | `ServiceDescribe` | public metadata 可公开；私有 frontier 需认证后作为扩展字段返回。 |
| `ak.self.events.command.submit` | 单事件提交 body 是 `EventSubmitEnvelope` 对象（顶层 `event_id`/`actor_id`/`payload`/`proofs[]` ...，但不含 reducer-managed accepted-output 字段）；批量提交 body 是 `{events: EventSubmitEnvelope[]}`。MUST NOT 使用 `{event: ...}` wrapper。 | `expected_frontier: object`; `idempotency_key: string` | `status: enum(accepted,duplicate,partial)`; `accepted: id[]`; `duplicate: id[]?`; `rejected: object[]?`; `quarantine: object[]?`; `actor_frontier: object?`; `realm_frontier: object?`; `cursor: cursor?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitOutcome。MUST 验证 Event signature、DID、capability、Realm policy、`actor_seq`、`prev_refs` 和 `refs[role=authorized_by]`。同一 `event_id` 对应不同 canonical 内容时 MUST 以 `duplicate_conflict`（409）拒绝（见 [operations-sync.md](./operations-sync.md) §12），不得退化为 `causal_conflict` / `state_mismatch`。`cursor` 是 barrier purpose（read-your-writes）。 |
| `ak.self.events.command.submit_seal` | body `Seal` | 无 | `seal_id: seal-id`; `accepted_event_digests: string[]`; `post_state_root: string` | request_schema_ref=schemas/seal.schema.json; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventSealSubmitOutcome。认证 session 只能对可见 Realm 提交 Seal，且 signer MUST 满足 predecessor `ak.component.notary.v1` authority；managed Agent PCR 可按 `key-management.md` §4.1 的闭合 delegation 由 controller 当前设备签署，service 不得代签。receiver MUST 重算全部 signed body、coverage、completeness 与 state。B 模型 principal-control Realm 的首个 Seal必须由 bootstrap device #1 签名并完整覆盖 bootstrap unit；managed Agent PCR 首个/后继 Seal分别完整覆盖 create 与 effectless MLS genesis。 |
| `ak.self.events.resource.get` | `path.event_id: id` | `query.include_payload: boolean` | `event: object`; `visibility: object?`; `receipts: object[]?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventView。不可见时返回 `not_found`。 |
| `ak.self.events.query.resolve` | 至少一个：`event_ids: id[]` 或 `event_digests: string[]` | `include_payload: boolean` | `events: object[]`; `missing: id[]`; `unauthorized: id[]?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsResolveRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsResolveOutcome。payload 可见性按 Realm policy / E2EE envelope 判断。 |
| `ak.self.events.query.scan` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.before: cursor`; `query.after: cursor`; `query.order: enum(default,ascending,descending)=default`; `query.limit: int`; `query.filters: object`; `query.include_completeness: boolean=false` | `events: object[]`; `next_cursor: cursor?`; `prev_cursor: cursor?`; `has_more: boolean`; `range_completeness: object?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryOutcome。`realms[]` 内部 union、`actors[]` 内部 union、二者组合为 intersection。每个 selector 元素都按对应可见性约束逐项检查：actor scope 走 actor history visibility；realm scope 走 membership frontier + history visibility + E2EE epoch policy；accepted Agent DID delegation 精确绑定的 controller MAY 回读该 managed Agent PCR 的控制历史，但该例外不得扩大到其他 Agent 或 Realm。`before` / `after` 均为开区间（排除 cursor 自身），可单独或同时给出形成 `(after, before)` 区间。默认顺序：仅 `before` → descending，仅 `after` → ascending，两者皆给 → descending；`order=ascending\|descending` 显式覆盖。响应 `prev_cursor` 永远朝更旧方向、`next_cursor` 永远朝更新方向。`include_completeness=true` 请求 `range_completeness`，详见 §3.3.6。 |
| `ak.self.events.query.scan_body` | body 至少一个：`realms: id[]` 或 `actors: did[]` | `before: cursor`; `after: cursor`; `order: enum(default,ascending,descending)=default`; `limit: int`; `filters: object`; `include_completeness: boolean=false` | 与 `ak.self.events.query.scan` 同 | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryPostRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryOutcome。`ak.self.events.query.scan` 的 HTTP POST/body binding variant（registry `binding_variant_of="ak.self.events.query.scan"`）。语义、selector 规则、默认顺序、响应 cursor 含义、错误码、`include_completeness` 与 GET 形态完全一致；仅 wire 形态从 query string 变为 JSON body。**何时使用**：`realms[]` / `actors[]` 较大、`filters` 较复杂、或部署侧记录 access log 时担心 query string 泄露 filter 内容。gRPC / MQ 不需要单独绑定（统一走 `SelfEvents/Query`）。 |
| `ak.self.events.stream.subscribe` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.after: cursor`; `query.catchup: boolean=false` | stream frame: `kind: enum(event,frontier,heartbeat,catchup_complete,epoch_rotation,dropped,resync_required,unauthorized)`; `realm_id: id?`; `cursor: cursor?`; `payload: object?`;`reconnect_after_ms: int?` | 同 `ak.self.events.query.scan` 逐 selector 授权检查；非 principal recipient（service delegation）必须满足明文可见性。`after=<cursor>` 是订阅起点（不含 cursor 本身），与 `ak.self.events.query.scan` 的 `after=` 同义；subscribe 天然只走未来方向，不接受 `before=` / `order=`。`catchup=true` 只表示从 `after=` 到当前 frontier 的追赶 replay，不表示全量历史；缺省或无 `after` 时只进入 live tail。某 realm 中途授权丢失 MUST 发出 `unauthorized` 帧并继续其他 realm；该帧 payload 至少包含 `reason_code`、`selector`、`retry_after_ms?`，不得包含不可见 Realm 标题、成员或 actor 集合。服务端因容量丢弃发出 `dropped` 帧，客户端必须 reconcile；`dropped` / `resync_required` MAY 携带 `reconnect_after_ms`，约束下一次同 scope 订阅重连。 |
| `ak.self.events.query.frontier` | 至少一个：`query.actor_id: did` 或 `query.realm_id: id` | 无 | `frontier: object`; `receipts: object[]?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsFrontierState。只承载 self Events API 的当前 caller 可见 frontier；不得接受 federation peer wire，不得泄露不可见 Realm 或 private DID。 |
| `ak.self.events.query.mls_governance_proof` | body `realm_id`; `effective_scope`; `mls_group_id`; `previous_epoch`; `next_epoch`; `binding_profile`; `reducer_profile`; `trusted_anchor_seal_id`; `chunk_index` | `expected_bundle_digest`（`chunk_index>0` 时 MUST，0 时 MUST NOT） | `MlsGovernanceProofBundle` bounded chunk（必含 `proof_request_digest`, `bundle_digest`, `trusted_anchor_seal_id`, `accepted_seal_id`, `chunk_manifest`, `chunk`） | request_schema_ref=schemas/mls-governance-proof-bundle.schema.json#/$defs/proof_request；response_schema_ref=schemas/mls-governance-proof-bundle.schema.json。仅限已认证且可见的 Realm/scope；response anchor MUST 与请求精确相等，服务端从同一 accepted Seal view 派生 frontier 与全部 root。无法桥接返回 `mls_governance_anchor_unreachable`；总 byte/count/chunk 上限超出返回 `mls_governance_proof_bounds_exceeded`，不得截断。Chunk 0 建 manifest，后续必须 pin 同一 digest；manifest 丢失返回 `frontier_unavailable` 并从 0 重启。Cache acquisition index 使用 `(proof_request_digest, accepted_seal_id)`，manifest 以 `bundle_digest`、chunk 以 `chunk_digest` 存储，不得只按 accepted Seal 缓存。 |
| `ak.peer.events.query.describe` | 无 | `query.realm_id: id` | `ServiceDescribe` | `public_metadata` 可返回通用 peer surface 能力；Realm-specific peer policy 细节需 service signature。响应 MUST 声明实际可调用的 `ak.peer.events.*` supported_operations、auth metadata 与 federation limits。 |
| `ak.peer.events.command.submit` | `service_binding_ref: object`; `events: EventEnvelope[]` | `idempotency_key: string` | `status: enum(accepted,duplicate,partial,historical_only)`; `accepted: id[]`; `duplicate: id[]?`; `rejected: object[]?`; `quarantine: object[]?`; `actor_frontier: object?`; `realm_frontier: object?`; `cursor: cursor?`; `original_outcome: object?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitFederationRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsSubmitOutcome。MUST 使用 §3 service-to-service authentication，绑定 Source/Destination service DID、Source/Destination trust domain、Request-Canonical-Digest、Content-Digest 与 Idempotency-Key（若有），并校验 Realm policy / service binding 的 `federation_peer` 角色。`status=historical_only` 仅出现在 idempotency cache 撤销后重放路径（[`federation.md` §8.5.1](./federation.md)）：原 cache outcome 经 `original_outcome` 原样带回，顶层 `accepted[]` MUST 为 empty。 |
| `ak.peer.events.query.resolve` | 至少一个：`event_ids: id[]` 或 `event_digests: string[]` | `include_payload: boolean`; `realms: id[]` | `events: object[]`; `missing: id[]`; `unauthorized: id[]?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsResolveRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsResolveOutcome。用于 federation peer 补洞解析 missing `prev_refs` / causal references；payload 可见性按 Realm policy、history visibility、reference disclosure 与 E2EE envelope 判断。 |
| `ak.peer.events.query.scan` | 至少一个：`query.realms: id[]` 或 `query.actors: did[]` | `query.before: cursor`; `query.after: cursor`; `query.order: enum(default,ascending,descending)=default`; `query.limit: int`; `query.filters: object` | `events: object[]`; `next_cursor: cursor?`; `prev_cursor: cursor?`; `has_more: boolean`; `snapshot_bootstrap: object?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryOutcome。用于 federation pull / backfill；调用方必须是 selector 所属 Realm 的授权 federation peer。分页、排序与 cursor 语义同 `ak.self.events.query.scan`，但 HTTP trust surface 是 `peer`。 |
| `ak.peer.events.query.scan_body` | body 至少一个：`realms: id[]` 或 `actors: did[]` | `before: cursor`; `after: cursor`; `order: enum(default,ascending,descending)=default`; `limit: int`; `filters: object` | 与 `ak.peer.events.query.scan` 同 | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryPostRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsQueryOutcome。`ak.peer.events.query.scan` 的 HTTP POST/body binding variant（registry `binding_variant_of="ak.peer.events.query.scan"`）。 |
| `ak.peer.events.query.frontier` | `query.realm_id: id` | 无 | `realm_id: id`; `heads: id[]`; `max_hlc: string?`; `frontier_root: hash`; `actor_seq_upper_bounds: object?`; `witness_receipts: object[]?`; `observed_at: datetime`; `issuer: did`; `signature: object` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventsFrontierFederationPeerState。用于 federation frontier probe；MUST 由响应方 service DID 签名并绑定 observed frontier，调用方必须是该 Realm 的授权 federation peer。 |
| `ak.peer.invites.command.submit` | `schema: ak.schema.invite_delivery_request.v1`; `invite_event: EventEnvelope`; `invite_address: object`; `introduction_evidence: object`; `idempotency_key: string` | 无 | `status: enum(accepted,duplicate,deferred)`; `received_at: datetime?`; `retry_after_ms: int?` | request_schema_ref=schemas/invite-delivery-request.schema.json; response_schema_ref=schemas/invite-delivery-request.schema.json#/$defs/invite_delivery_outcome。Principal Server 间私有 invite delivery；MUST 绑定 Source/Destination service DID、Request-Canonical-Digest 与 Content-Digest，且 `Destination-Service-ID == invite_address.recipient_service_id`。接收方内部可 quarantine/drop，但 wire 响应不得泄露 subject 是否存在。 |
| `ak.peer.contacts.command.submit` | `schema: ak.schema.peer_contact_delivery_request.v1`; `contact_event: EventEnvelope`; `contact_address: object`; `fact_kind: enum(ak.contact.requested,ak.contact.accepted,ak.contact.rejected,ak.contact.tombstoned)`; `introduction_evidence: object?`; `idempotency_key: string` | 无 | `status: enum(accepted,duplicate,deferred)`; `disclosed_outcome: enum(delivered,blocked,quarantined)?`; `received_at: datetime?`; `retry_after_ms: int?` | request_schema_ref=schemas/peer-contact-delivery-request.schema.json; response_schema_ref=schemas/peer-contact-delivery-request.schema.json#/$defs/peer_contact_delivery_outcome。Principal Server 间私有 contact fact delivery；`fact_kind=ak.contact.requested` 时 `introduction_evidence` MUST 出现并按 recipient receive policy + `receive_policy_constraints` 判定。MUST 绑定 Source/Destination service DID、Request-Canonical-Digest 与 Content-Digest,且 `Destination-Service-ID == contact_address.recipient_service_id`。接收方投影原始签名 envelope，不得 re-sign;wire 响应默认 opaque。 |
| `ak.peer.snapshot.query.manifest_head` | `query.realm_id: id` | 无 | `ak.schema.snapshot.v1` manifest（`id`、`realm_id`、`state_digest`、`frontier`、`event_set_commitment`、`chunks[]`、`created_by`、`created_at`、`authority_binding`、`signature` 等） | response_schema_ref=schemas/snapshot.schema.json。用于 snapshot-assisted bootstrap；调用方必须是该 Realm 的授权 federation peer，manifest 校验与 not_implemented 规则同 `ak.self.snapshot.query.manifest_head`。 |
| `ak.self.account.query.viewer` | 无 | 无 | `principal_id: did`; `primary_handle_claim?: HandleClaim`; `primary_handle_claim_ref?: string`; `handle_claim_digests?: hash[]`; `state: enum(active,soft_logged_out,locked,suspended,deactivated,erasure_pending)`; `devices: object[]`; `profile?: ActorProfile` | response_schema_ref=schemas/account-operations.schema.json#/$defs/account_view。`user_session` 必须绑定 principal/device；`primary_handle_claim` 与 `primary_handle_claim_ref` 互斥；不得返回 unsigned bare handle。 |
| `ak.self.account.stream.subscribe` | 无 | `query.after: cursor`; `query.catchup: boolean=false`; `query.filter: object` | `application/x-ndjson` 每行一个 `AccountSubscribeFrame`(`kind: delta / catchup_complete / frontier / heartbeat / dropped / resync_required / unauthorized`,`delta` 含 `cursor` + `realms?` + `to_device?` + `device_lists?` + `account_data?` + `presence?` + `notifications?`;`notifications={items: NotificationDelta[]}`，不是 Event container；`dropped` / `resync_required` 可含 `reconnect_after_ms`)。 | `user_session` 必须绑定 account context、principal、device 与 recipient service。聚合账号视角 delta；裸事件读用 `ak.self.events.query.scan` / `ak.self.events.stream.subscribe`。`cursor` 是 stream purpose并内部覆盖 notification monotonic position。Initial sync 使用 `catchup=true` 且省略 `after`，必须返回 open agent approval 的完整 add baseline；projection 与 cursor 是 durable authority，account-scoped broadcast 只负责低延迟 wakeup。 |
| `ak.self.account.command.update_profile` | `patch: ak.patch.v1` | 无 | `profile: ActorProfile` | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_update_profile_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_update_profile_outcome。允许 path 仅 `display_name` / `avatar_blob_ref` / `profile_fields.<key>`；个人简介使用 `profile_fields.bio`；`avatar_url` MUST NOT 进入协议 body，头像引用使用 `avatar_blob_ref`。 |
| `ak.self.account.command.revoke_cursor` | `cursor: cursor` | `reason_code: string`; `revoke_scope: enum(this_cursor,same_device,same_session)=this_cursor` | `revoked: boolean`; `expires_at: datetime` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeOutcome。High-assurance optional profile；撤销 cursor authority，详见 [`client-sync.md` §12.2.1](./client-sync.md)。 |
| `ak.self.account.query.describe` | 无 | 无 | `ServiceDescribe` | 私有 frontier 可认证后作为扩展字段返回。 |
| `ak.self.contact.command.request` | `target: did`; `requested_scopes: consent_scope[]`; `message: string?`; `recipient_service_id: did?`; `introduction_evidence: object?`; `idempotency_key: string?` | 无 | `request_event_ref: id`; `requester_consent_refs: id[]`; `state: string` | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_request_request_body; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_request_outcome。requester 只能写自己的 request fact；若请求 scope，必须同步写 requester-side consent grant。跨 Principal Server 首次接触使用 `recipient_service_id` 定址；`introduction_evidence` 可携带 `locator_ref`、`handle_claim` 或 `explicit_address` 等来源证据，issuer 侧 PS 无法构造合规 evidence 时按 `explicit_address` 低信任处理。 |
| `ak.self.contact.command.respond` | `request_id: id`; `requester: did`; `action: enum(accept,reject)` | `granted_scopes: consent_scope[]` | `response_event_ref: id`; `consent_grant_refs: id[]?`; `state: string` | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_request_body; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_outcome。只有 target 可 accept/reject；accept 写 target-controlled consent grants，reject 不写 consent。 |
| `ak.self.contact.query.list` | 无 | `state: enum?`; `cursor: cursor`; `limit: int` | `contacts: object[]`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_list。从 contact facts 投影；方向化 scopes 必须区分 `granted_by_me[]`、`granted_to_me[]`、`bidirectional_scopes[]`；`agents[]` 只包含当前 viewer 可直聊的 active native personal agents。 |
| `ak.self.contact.command.tombstone` | `contact: did` | `revoke_scopes: consent_scope[]`; `full_peer_revoke: boolean=false` | `tombstone_event_ref: id`; `consent_revoke_refs: id[]`; `state: string` | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone_request_body; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone。默认 revoke holder 给 peer 的 contact-managed active dots，不误删同 peer 的独立 consent。 |
| `ak.self.invite_receive_policy.resource.get` | 无 | 无 | `schema: const`; `subject_id: did`; `allowed_introduction_kinds: enum[]`; `handle_claim_behavior?: enum`; `explicit_address_behavior: enum`; `unknown_invites: enum`; `allowed_handle_domains?: string[]`; `blocked_handle_domains?: string[]`; `trusted_handle_issuers?: did[]`; `trusted_directory_services?: did[]`; `disclosure?: object`; `blocked_subjects?: did[]` | response_schema_ref=schemas/invite-receive-policy.schema.json。读取 subject 私有 invite/contact receive policy；无显式 override 时返回推荐默认值；该 policy 不写入目标 Realm durable event log 或公开 contact fact log。 |
| `ak.self.invite_receive_policy.resource.replace` | `schema: ak.schema.invite_receive_policy.v1`; `subject_id: did`; `allowed_introduction_kinds: enum[]`; `explicit_address_behavior: enum`; `unknown_invites: enum` | `handle_claim_behavior: enum`; `allowed_handle_domains: string[]`; `blocked_handle_domains: string[]`; `trusted_handle_issuers: did[]`; `trusted_directory_services: did[]`; `disclosure: object`; `blocked_subjects: did[]`; `trusted_realm_ids: id[]`; `trusted_principal_services: did[]`; `blocked_principal_services: did[]` | 同请求体（回显存储后的 policy） | request_schema_ref=schemas/invite-receive-policy.schema.json; response_schema_ref=schemas/invite-receive-policy.schema.json。`subject_id` MUST 等于 session actor；override 与 `ak.self.contact.command.tombstone(block_peer)` 写入的 `blocked_subjects` 共享同一存储；最终可达性仍由 Principal Server `receive_policy_constraints` 收紧。 |
| `ak.self.direct_conversation.command.resolve` | `peer: did` | `create: boolean=false`; `idempotency_key: string?` | `realm_id: id?`; `main_strand_id: id?`; `binding_event_ref: id?`; `state: string`; `created: boolean?` | request_schema_ref=schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_request_body; response_schema_ref=schemas/contact-operations.schema.json#/$defs/direct_conversation_resolve_outcome。accepted contact + `direct_message` consent 双 gate；orphan Realm 不得作为默认入口返回。 |
| `ak.self.circle.command.create` | `realm_id: id`; `title: string` | `summary: string`; `directory_visibility: enum(members,realm_members)=members`; `join_rule: enum(invite,request,open)=invite`; `history_visibility: enum=joined`; `content_encryption_floor: enum`; `metadata_encryption_floor: enum`; `encryption_profile: enum(none,mls_rfc9420)=mls_rfc9420` | `circle_id: id`; `realm_id: id`; `title: string`; `directory_visibility: enum`; `join_rule: enum`; `history_visibility: enum`; `encryption_profile: enum`; `mls_group_ref: string?`; `state: enum`; `members: did[]`; `created_by: did`; `created_at: datetime` | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_create_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view。构造 `ak.circle.create`;reducer-locked 字段(`mls_group_ref` / `state`)不接受 actor 提交;`encryption_profile=none` 仅当父 Realm policy floor 允许明文。 |
| `ak.self.circle.query.list` | `query.realm_id: id` | 无 | `realm_id: id`; `circles: object[]` | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_list。按 Circle directory visibility 逐条裁剪。 |
| `ak.self.circle.resource.get` | `path.circle_id: id` | 无 | 同 `ak.self.circle.command.create` 响应字段 | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view。不可见时返回 `not_found`。 |
| `ak.self.circle.member.command.add` | `path.circle_id: id`; `actor_id: did` | `membership: enum(invite,join,knock,leave,ban)=join` | `circle_id: id`; `actor_id: did`; `membership: enum` | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_member_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_membership_outcome。构造 `ak.circle.member.state`;加入他人需 `ak.circle.member.manage` 且目标已是父 Realm joined 成员；`knock` 仅在 `join_rule=request` 下有效。 |
| `ak.self.circle.member.resource.delete` | `path.circle_id: id`; `path.actor_id: did` | 无 | `circle_id: id`; `actor_id: did`; `membership: enum` | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_membership_outcome。构造 `ak.circle.member.state`(`membership=leave`)。 |
| `ak.self.circle.command.rotate_scope` | `path.circle_id: id` | 无 | `circle_id: id`; `mls_group_ref: string?`; `note: string?` | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_scope_rotate_outcome。不得在未真正更换密钥学 scope 时确认轮转;MLS 级联未端到端打通前返回 `unsupported_feature`(501)。 |
| `ak.self.circle.command.archive` | `path.circle_id: id` | `reason_code: string` | 同 `ak.self.circle.command.create` 响应字段 | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view。构造 `ak.circle.archive`;非法转换由 reducer 以 `circle_not_active` 拒绝。 |
| `ak.self.circle.command.restore` | `path.circle_id: id` | `reason_code: string` | 同 `ak.self.circle.command.create` 响应字段 | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view。构造 `ak.circle.restore`;非法转换由 reducer 以 `circle_not_archived` 拒绝；若存在 pending MLS remove proposal，恢复写入前必须先完成对应 rotate。 |
| `ak.self.circle.command.tombstone` | `path.circle_id: id` | `reason_code: string` | 同 `ak.self.circle.command.create` 响应字段 | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_lifecycle_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view。构造 `ak.circle.tombstone`(terminal);响应回显终态且 `members` 为空。 |
| `ak.self.ephemeral.command.send` | body `ak.schema.ephemeral_envelope.v1` | `proof: object`（按 kind 需要）；payload 内 kind-specific 字段 | `accepted: boolean`; `kind: string`; `realm_id: id`; `dispatched_to: int?`; `server_received_at: datetime?` | request_schema_ref=schemas/ephemeral-envelope.schema.json; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EphemeralSubmitOutcome。broadcast ephemeral channel；只承载 `ak.presence` / `ak.typing` / `ak.receipt.read` / `ak.call.signal`，并分别要求 `ak.presence.broadcast` / `ak.typing.broadcast` / `ak.receipt.broadcast` / `ak.call.signal.send`。MUST NOT 写入 durable Event history，MUST NOT 推进 actor_seq / Realm frontier。拒绝码包括 `ephemeral_kind_not_permitted`、`ephemeral_ttl_out_of_range`、`ephemeral_channel_unavailable`。 |
| `ak.self.call.media.exchange.issue_token` | body `realm_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `focus_id: string` | `capability_refs: id[]`; `desired_media: object` | `focus_id: string`; `type: string`; `connect_url: string`; `backend_token: string`; `participant_identity: string`; `participant_binding: object`; `expires_at: datetime`; `service_signature: object` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeOutcome。Media service token exchange，等价于 MSC4195 `lk-jwt-service`。TTL `expires_at ≤ 600s`；token issuer DID MUST 出现在 `ak.realm.media_service.service_id` 锚定列表。拒绝码：`focus_mismatch`、`unknown_focus_type`、`token_issuer_unauthorised`、`mls_governance_binding_stale`、`media_plaintext_service_not_authorised`、`capability_denied`、`media_service_foci_required`。详见 [`../crypto-media/media-service-binding.md` §3](../crypto-media/media-service-binding.md)。 |
| `ak.self.snapshot.query.manifest_head` | `query.realm_id: id` | 无 | `ak.schema.snapshot.v1` manifest（`id`、`realm_id`、`state_digest`、`frontier`、`event_set_commitment`、`chunks[]`、`created_by`、`created_at`、`authority_binding`、`signature` 等） | response_schema_ref=schemas/snapshot.schema.json。响应是完整 Snapshot manifest（不含 chunk bytes），客户端经 `chunks[].chunk_ref` 走 blob surface 取数；manifest MUST 签名，signer 必须是 Realm owner、Realm policy 授权的 snapshot issuer 或 witness quorum 成员，签名 transcript 见 [`../conformance/snapshot-schema.md`](../conformance/snapshot-schema.md) §5；无法产出真实签名 manifest 的部署 MUST NOT 宣告本操作并 MUST 返回 `not_implemented`，不得伪造证明字段；high-assurance profile MUST 支持 inclusion / omission challenge hints。 |
| `ak.self.space.query.list` | `path.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `spaces: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionSpaceList。extension surface；返回 reducer 派生的 Space lifecycle read model，不是真相源；默认不得返回 tombstoned terminal rows。 |
| `ak.self.strand.query.list` | `path.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `strands: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionStrandList。extension surface；返回 reducer 派生的 Strand lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `ak.self.morph.query.list` | `path.realm_id: id` | `query.include_terminal: boolean=false`; `query.cursor: cursor`; `query.limit: int` | `realm_id: id`; `morphs: object[]`; `total: int`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionMorphList。extension surface；返回 reducer 派生的 Morph lifecycle read model，不是真相源；默认不得返回 redacted terminal rows。 |
| `ak.self.views.collection_projection.command.materialize` | `path.view_id: id` | `body.cursor: cursor`; `body.limit: int` | `projection: collection`; `view_id: id`; `frontier: object`; `groups: object[]?`; `items: object[]?` | request_schema_ref=schemas/view.schema.json#/$defs/view_projection_request_body; response_schema_ref=schemas/view.schema.json#/$defs/collection_projection_view。extension surface；只物化 collection View，输出必须可追溯到 signed Event、View definition 与 reducer profile。 |
| `ak.self.morph.resource.get` | `path.realm_id: id`; `path.morph_id: id` | 无 | `document: object`; `versions: object[]`; `relations: object[]`; `comments: object[]`; `cursor_presence: object[]` | response_schema_ref=schemas/view.schema.json#/$defs/document_morph_projection_outcome。extension surface；单 document Morph 派生读模型，不是真相源。 |
| `ak.find.directory.query.describe` | 无 | 无 | `ServiceDescribe` | `public_metadata`; 可限流。Directory-specific 字段可作为扩展字段返回；详见 `../discovery/discovery-directory.md` §8.9。 |
| `ak.find.directory.query.search_realms` | 无 | `query: string`; `organization_did: did`; `source_realm_id: id`; `requester: did`; `proof_challenge: string`; `claim_presentations: DirectoryRestrictedClaimPresentation[]`; `cursor: cursor`; `limit: int` | `realms: object[]`; `next_cursor: cursor?`; `has_more: boolean` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_realms_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_realm_search_outcome。hidden resource 不泄露存在性；restricted claim presentation 形态见 discovery-directory.md §2；每条 `realms[]` item MUST 含 `as_of`/`source_refs`/`policy_revision`/`stale?`/`divergent?`（discovery-directory.md §9.1）；`join_candidates[]` MAY 省略以避免在搜索结果泄露服务拓扑，客户端 join 前必须 resolve。 |
| `ak.find.directory.query.resolve_realm` | 至少一个：`realm_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proof_challenge: string`; `claim_presentations: DirectoryRestrictedClaimPresentation[]` | `realm_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `join_candidates?: object[]` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_realm_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_realm_resolution_outcome。secret/restricted Realm 使用统一 `not_found`；`join_candidates[]` 是规范 join ingress 列表，元素符合 `ak.schema.realm_join_candidate.v1`。支持结构化 candidate 且可披露 join 路由时 MUST 返回；没有 `join_candidates[]` 的响应不能直接用于提交 join material。 |
| `ak.find.directory.query.resolve_target` | `address: string` | `requester: did`; `proofs: proof[]`; `token: string` | `target_kind: enum(realm,strand,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; `as_of`/`source_refs`/`join_candidates?` 等 discovery-directory.md §9.1 通用字段 | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_target_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_target_resolution_outcome。`resolve_realm` 的对象级泛化，realm 解析委托 `resolve_realm` 并继承 candidate routing 语义；`invite` / `preview` token 按 target descriptor + effective link type 校验（[`../discovery/object-addressing.md` §4.2](../discovery/object-addressing.md)）；preview token 只授权 preview policy 允许字段；未授权统一 `not_found`。 |
| `ak.find.directory.query.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `organizations: object[]`; `next_cursor: cursor?`; `has_more: boolean` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_organizations_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_organization_search_outcome。仅公开或授权可发现组织。 |
| `ak.find.directory.query.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_organization_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_organization_resolution_outcome。解析组织不等于公开成员或拓扑。 |
| `ak.find.directory.query.search_actors` | 无 | `query: string`; `realm_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `actors: object[]`; `next_cursor: cursor?`; `has_more: boolean` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_actors_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_actor_search_outcome。不得泄露 pairwise/private DID。 |
| `ak.find.directory.query.search_users` | `body.query: string` | `body.realm_id: id`; `body.limit: int`; `body.intent: enum(mention,contact_request,invite,member_add)` | `users: object[]`; `next_cursor: cursor?`; `has_more: boolean` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_users_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_user_search_outcome。mention autocomplete / 联系人请求 / 成员添加候选；受共同 Realm / directory policy 限制；请求词不得进入 URL、Referer 或未脱敏 access log。结果 MAY 包含 handle preview，但未授权时不得披露 `subject` DID 或 `member_delivery_binding`。 |
| `ak.find.directory.query.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `realm_id: id`; `requester: did`; `proofs: proof[]` | `did: did`; `subject: did`; `handle: string`; `verified: boolean`; `claims: object[]?`; `member_delivery_binding: object?`; `source_refs: id[]?`; `expires_at: timestamp?` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_handle_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_handle_resolution_outcome。受限 / 组织 handle 需要 presentation；响应 `handle` 是 canonical `user:domain`；投递服务 DID 只通过 `member_delivery_binding.recipient_service_id` 返回。 |
| `ak.find.directory.query.resolve_agent_selector` | `controller_handle: string`; `agent_slug: string`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `requester: did` | `expected_agent_did: did`; `proof_challenge: string`; `realm_id: id`; `proofs: proof[]` | `controller_subject: did`; `subject: did`; `agent_slug: string`; `verified: true`; `selector_claim: object`; `source_refs: id[]?`; `expires_at: timestamp?` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_agent_selector_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_agent_selector_resolution_outcome。精确解析 `@<controller-handle>/<agent_slug>`；成功响应中的 `subject` 是 agent DID，`selector_claim` MUST 是当前可见 `ak.schema.agent_selector_claim.v1`。未授权、不可见、不存在、revoked / expired / ambiguous MUST 返回与不存在不可区分的失败。 |
| `ak.find.directory.query.list_handles_for_subject` | `subject: did` | `realm_id: id`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `requester: did`; `proof_challenge: string`; `proofs: proof[]`; `as_of: datetime`; `cursor: cursor`; `limit: int` | `subject: did`; `claims: object[]`; `primary_handle: string?`; `as_of: datetime`; `next_cursor: cursor?`; `has_more: boolean` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_list_handles_for_subject_request_body; response_schema_ref=schemas/list-handles-for-subject-response.schema.json。holder/principal DID + context → current visible claims；`subject` 不是 Realm `actor_id`。必须按 disclosure policy、issuer trust、audience 和 intent 过滤；不能因共同 Realm 单独披露受限 handle。 |
| `ak.find.directory.query.private_contact_discovery` | `requester: did`; `contacts: object[]` | `proofs: proof[]`; `privacy_profile: string`; `padding: object` | `matches: object[]`; `proofs: object[]?`; `retry_after_ms: int?` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_private_contact_discovery_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_private_contact_discovery_outcome。MUST 使用 blinded / padded identifier batch；响应 MAY 含最小 invite/consent handoff stub，但不得返回 contact request handoff token、原始 connection identifier、完整 profile、成员列表、Realm membership 或关系图谱。 |
| `ak.find.directory.command.announce` | `resource_kind: enum(realm,organization,actor,applet,handle)`; `resource_id: id\|did\|handle`; `discovery_state: object`; `source_refs: id[]`; `as_of: timestamp`; `principal_server_did: did` | `ttl_seconds: int`; `supersedes_announce_id: ak:announce:<uuidv7>` | `announce_id: ak:announce:<uuidv7>`; `indexed_at: timestamp`; `effective_ttl_seconds: int`; `next_revalidation_after: timestamp`; `warnings: string[]?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceOutcome。资源 → Directory 的签名 ingest；`announce_id` 是 Directory-local typed ID，不是跨 Directory 全局对象权威；MUST 验签 + 双向 opt-in；详见 `../discovery/discovery-directory.md` §8.3 / §8.5 / §8.10。 |
| `ak.find.directory.command.withdraw` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdrawal_ref: string`; `acked_at: timestamp` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawOutcome。资源主动撤销 opt-in；`withdrawal_ref` 是 Directory-local audit reference，不是注册 typed ID。Directory MUST 在 ≤ 1h 内停止披露；详见 `../discovery/discovery-directory.md` §8.7。 |
| `ak.find.directory.command.takedown_appeal` | `takedown_id: string`; `resource_id: id\|did\|handle`; `appellant_did: did`; `argument_digest: hash`; `requested_outcome: enum(overturn,reduce_scope,reinstate)`; `created_at: timestamp`; `governance_proof: object` | （无可选字段） | `appeal_id: string`; `received_at: timestamp`; `decision_receipt: object` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryTakedownAppealRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryTakedownAppealOutcome。资源端对 operator takedown 的申诉；appeal packet MUST 绑定 `takedown_id` / resource id / `appellant_did` / argument digest / `requested_outcome` / `created_at` 并由资源 governance key 或授权 advocate 签名，Directory 返回 signed decision receipt；详见 `../discovery/discovery-directory.md` §8.7。 |
| `ak.find.directory.push.command.register` | `subscriber_did: did`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_push_register_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_push_register_outcome。push webhook 注册；仅作为 pull 模式优化，不替代 freshness 协议（§8.6）。 |
| `ak.self.blob.upload.create` | `content: binary`; `size_bytes: int` | `realm_id: id`; `content_digest: string`; `media_type: string`; `filename: string`; `purpose: string` | `blob_ref: string`; `size_bytes: int`; `media_type: string?`; `content_digest: string`; `upload_receipt: object?` | request_schema_ref=schemas/blob-operations.schema.json#/$defs/blob_upload_request_body; response_schema_ref=schemas/blob-operations.schema.json#/$defs/blob_upload_outcome。upload capability、quota、media policy；`content` part Content-Type 缺省为 `application/octet-stream`。`size_bytes` 可由客户端声明，也可由服务端在响应中按实际接收字节计算后返回；二者不一致时 MUST `digest_mismatch` 或 `invalid_param`。 |
| `ak.self.blob.resource.head` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.X-Arkret-Wait-For: cursor` | headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID，但不能验证当前请求者 audience。不得通过 header 泄露不可见资源。`presign` 形态见 `ak.self.blob.command.presign`。 |
| `ak.self.blob.resource.get` | `query.blob_ref: string` | `header.Authorization: token` 或 `query.presign: token`（与 `Authorization` 互斥）；`header.Range: string`; `header.X-Arkret-Wait-For: cursor` | bytes；headers 包含 `Content-Length?`, `Digest?`, `Cache-Control`, `Content-Type?`, `Content-Disposition?`, `Content-Range?`, `Location?` | Header auth 路径必须验证 actor/device/Realm/purpose/expiry；presign 路径只接受 `ak.self.blob.command.presign` 发出的短 TTL 单对象 bearer token，验证 envelope、TTL、scope、Realm/blob 状态和 issuer service DID。Range 和 redirect 不得泄露不可见资源。两者同时出现 MUST 拒绝。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `ak.self.blob.command.presign` | `blob_ref: string` | `max_age_seconds: int (<=3600)`; `purpose: enum(media_inline, thumbnail, download)` | `url: uri`; `expires_at: timestamp`; `purpose: string` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/BlobPresignRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/BlobPresignOutcome。为单个 blob 签发短 TTL（默认 ≤ 5 min，硬上限 ≤ 1h）、单对象、只读、可撤销的 pre-signed URL。**仅用于让浏览器 `<img src>` / `<video src>` 等无法附 Authorization header 的原生标签渲染受保护媒体**。E2EE 附件 ciphertext MUST NOT 通过此机制下发。受 `ak.self.blob.command.presign` capability 控制；TTL / scope / purpose 由 grant constraint 收紧。详见 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。 |
| `ak.edge.push.command.register_device` | `device_id: id`; `push_gateway: url`; `push_key: string` | `platform: string`; `app_id: string`; `display_name: string`; `recipient_service_id: did` | `ok: boolean`; `registration_id: id?`; `expires_at: datetime?` | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_register_device_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_register_device_outcome。只能注册当前 principal/device，且 registration 作用域绑定当前 Principal Server service DID；如显式携带 `recipient_service_id`，MUST 等于目标服务 DID。 |
| `ak.edge.push.command.unregister_device` | `device_id: id` | `push_key: string`; `app_id: string` | `ok: boolean` | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_unregister_device_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_unregister_device_outcome。same device/principal 或 device revocation path。 |
| `ak.edge.push.command.notify` | `notification.push_target_id: string`; `notification.wakeup_kind: enum(message,mention,assignment,schedule,reaction,call_invite,reminder,scheduled_send,expiry_invalidation)`; `notification.timing_profile_hint: enum(default,traffic_metadata_hardened)`; `notification.devices: object[]` | `header.Idempotency-Key: string`; `notification.push_hint: string`; `notification.counts: object`; routing-stripped（gateway-internal，出 provider 前 strip）: `notification.timing_profile_hint: string`, `notification.route_tokens: object {realm_route_token?, scope_route_token?, mention_redirect_target_route_tokens?: string[], delivery_binding_frontier_token?}`, `notification.devices[].target_route_token: string`; 顶层: `event_kind: string`, `reason_code: string`, `audit_envelope: object {access_kind, late_recovery_original_event_id?}`; visible profile only: `notification.event_id: id`, `notification.realm_id: id`, `notification.sender_actor_id: did`, `notification.strand_id: id`, `notification.message_id: id`, `notification.sender_actor_display_name: string`, `notification.strand_title: string`, `notification.realm_title: string`, `notification.user_is_target: boolean`, `notification.priority: string`, `notification.membership: string` | `rejected: object[]` | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_notify_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_notify_outcome。来自授权 Sync 或 notification service；`idempotency_key` / `origin_service_id` / `destination_service_id` / `recipient_service_id` 走 transport header（`Idempotency-Key` / `Source-Service-ID` / `Destination-Service-ID`，后者由 `recipient_service_id` 复用），`operation_id` 由 path 唯一确定，均不入 body。默认 blind wakeup 请求 MUST NOT 携带 event / realm / sender 字段；独立第三方 Push Gateway 的路由输入只能是 opaque token，且不得承载 raw Realm id、Circle id、`effective_scope` 或 actor DID allow-list。`notification.timing_profile_hint=traffic_metadata_hardened` 声明源 Realm / route 使用 `ak.profile.traffic_metadata_hardened.v1`，只用于 gateway provider-visible timing bucket，不进入 provider payload。visible 字段只在 `ak.profile.push_gateway.visible_notification.v1` 且 Realm policy + device opt-in + UI disclosure 通过时允许；`notification.content`、`body`、`preview`、`summary` 或任意 `content_*` 仍然禁止。`service_signature` 的 transcript MUST 绑定 `push_target_id` 所对应 registration 的 registration service DID（即 `ak.edge.push.command.register_device` 注册作用域绑定的 Principal Server service DID）；且发起 notify 的来源服务 DID MUST 出现在该设备 registration 的 `recipient_service_id` 投递链内。push gateway MUST 拒绝来源服务不在目标设备投递链内、或 transcript 未绑定该 registration service DID 的请求（`capability_denied`），以阻止跨 Realm / 跨 Principal Server 的 push 注入。 |
| `ak.self.device_messages.command.send` | `header.Idempotency-Key: string`; `messages: object` | 每个 target 必须含 `kind`、`content`、`expires_at` | `ok: boolean`; `delivered: object?`; `unknown_devices: object?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesSendRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesSendOutcome。`(sender, Idempotency-Key)` 幂等；目标必须是授权 device；fresh-device restricted session grant 仅可向同 principal 已授权设备发送 `ak.key.verification.*` bootstrap；过期或超过 TTL 上限的消息必须拒绝或逐项 reject。 |
| `ak.self.device_messages.query.list` | 无 | `query.after: cursor`; `query.limit: int` | `messages: object[]`; `ack_token: string?`; `next_cursor: cursor?`; `has_more: boolean`; `limited: boolean?`; `lost: boolean?` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesGetOutcome。响应字段 `messages[]` 含 `DeviceMessageEnvelope` 对象, 不是 Event Envelope; 只返回当前 device 队列；`after=` 是只读位置，不触发队列删除；`messages` 非空时 MUST 返回 `ack_token`。 |
| `ak.self.device_messages.command.ack` | `ack_token: string` | 无 | `ok: boolean`; `pruned_count: int?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesAckRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesAckOutcome。显式 to-device 投递确认（[`client-sync.md` §10.1](./client-sync.md)）：累计单调、天然幂等；unknown / 过期 / cross-binding 令牌返回 `invalid_param`（reason `invalid_ack_token`）且不得删除任何消息。 |
| `ak.self.keys.upload.create` | `device_id: id`; `device_signature: signature` | `one_time_keys: object`; `fallback_keys: object` | `one_time_key_counts: object`; `fallback_keys: object?` | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_upload_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_upload_outcome。key 必须链接 self-signing / principal key。 |
| `ak.self.keys.query.lookup` | `device_keys: object` | `timeout_ms: int` | `device_keys: object`; `failures: object[]?` | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_query_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_query_outcome。查询范围可按关系 / Realm 限制。 |
| `ak.self.keys.command.claim` | `one_time_keys: object` | 无 | `one_time_keys: object`; `failures: object[]?` | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_claim_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_claim_outcome。one-time key MUST 原子消费。 |
| `ak.self.keys.keypackages.upload.create` | `principal_id: did`; `device_id: id`; `key_packages: object[]`; `device_signature: signature` | `expires_at: datetime`; `strand_id: id`; `mls_group_id: string` | `accepted: int`; `rejected: object[]?`; `key_package_refs: id[]?`; `available_count: int?` | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_upload_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_upload_outcome。MLS KeyPackage MUST 绑定 device key、credential 和 supported cipher suites；服务 SHOULD 返回该 device 当前可见 `available_count` 以支持低水位补充。 |
| `ak.self.keys.keypackages.command.claim` | `target_principal_id: did`; `intended_realm_id: id`; `requester: did`; `required_capabilities: string[]`; `claim_nonce: string`; `expires_at: datetime` | `target_device_ids: id[]`; `minimal_metadata_allowed: boolean`; `timeout_ms: int`; `strand_id: id`; `mls_group_id: string`; `proofs: proof[]` | `claims: object[]`; `failures: object[]?`; `available_count: int?` | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_claim_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_claim_outcome。KeyPackage claim MUST 原子保留，重复 claim 不得返回同一 one-time package；claimed 过期不得回到 published，claim path 按 `(requester_service_id, target_principal_id)` 限速并做反枚举。 |
| `ak.self.keys.keypackages.command.consume` | `key_package_refs: id[]`; `consumer_device_id: id`; `signature: signature` | `claim_ids: string[]`; `welcome_ref: ref`; `realm_id: id`; `strand_id: id`; `mls_group_id: string`; `epoch: int` | `consumed: id[]`; `failures: object[]?` | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_consume_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_consume_outcome。consume MUST 校验 claim holder、epoch 和 package freshness。 |
| `ak.self.keys.keypackages.command.revoke` | `key_package_refs: id[]`; `device_id: id`; `signature: signature` | `reason: string` | `revoked: id[]`; `failures: object[]?` | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_revoke_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/key_packages_revoke_outcome。只能由 owning device、principal 或授权 admin 撤销。 |
| `ak.self.keys.backups.resource.replace` | `path.backup_id: id`; `backup: object` | `idempotency_key: string` | `status: enum(accepted,duplicate)`; `backup_id: id`; `ciphertext_digest: string` | request_schema_ref=schemas/key-backup.schema.json; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_replace_outcome。path/body backup id 必须一致；服务端不得解密。 |
| `ak.self.keys.backups.query.list` | 无 | `query.series_id: id?`; `query.backup_class: enum(ak.schema.key_backup.v1.backup_class)`; `query.cursor: cursor`; `query.limit: int` | `backups: object[]`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_list。仅返回调用方可见的最小 metadata；不得泄露无关 Realm / group membership。 |
| `ak.self.keys.backups.command.unlock` | `path.backup_id: id`; `proof: ak.schema.key_backup_unlock_proof.v1` | 无 | `backup: object` | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_unlock_request_body; response_schema_ref=schemas/key-backup.schema.json。只返回同 principal 授权 device、recovery policy 或授权恢复服务可见的 encrypted backup object；path/proof backup id 必须一致，unlock proof 校验 MUST 先于 ciphertext 返回（`identity/key-management.md` §7.7.1 / §7.8）。 |
| `ak.self.keys.backups.resource.delete` | `path.backup_id: id`; `proof: proof` | `reason: string` | `deleted: boolean`; `backup_id: id?` | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_delete_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_delete_outcome。高风险删除；不等于 device revoke、DID recovery 或 MLS epoch rotation。 |
| `ak.self.authz.grants.query.effective` | `query.realm_id: id`; `query.subject: did` | `query.at: string` | `grants: object[]`; `state_digest: string?`; `evaluated_at: datetime` | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/GrantList。subject 本人、Realm admin 或授权服务。 |
| `ak.self.authz.invites.query.list` | `query.subject: did 或 string` | `query.realm_id: id`; `query.cursor: cursor` | `invites: object[]`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/authz-operations.schema.json#/$defs/authz_invite_list。secret invite 不可枚举。 |
| `ak.self.authz.query.check` | `actor_id: did`; `action: string` | `resource: object`; `context: object` | `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `matched_grants: object[]?`; `applied_constraints: object[]?`; `policy_results: object[]?`; `missing_proofs: object[]?`; `frontier: object?`; `freshness_state: enum(fresh,stale,unknown)?`; `last_known_frontier_age_ms: int?`; `notary_status: enum(fresh,lagging,unreachable,unknown)?`; `cache_expires_at: datetime?`; `reason_code: string?`; `retry_after_ms: int?`; `obligations: object[]?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckOutcome。Policy allow 不创建 capability；客户端不得把非标准 `allowed` 字段作为规范字段；`freshness_state=stale/unknown` 且高风险动作时 MUST fail closed，reason_code 使用 `revocation_freshness_unknown`。 |
| `ak.self.policy.query.check` | `request_id: string`; `realm_id: id`; `request_canonical_digest: string`; `action: string`; `actor_id: did`; `source: object` | `device_id: id`; `event_preview: object`; `auth_context: object` | `request_id: string`; `bound_to: object`; `decision: enum(allow,soft_deny,hard_deny,quarantine,require_review)`; `reason_code: string`; `expires_at: datetime`; `auth_state_digest: string`; `policy_frontier_digest: string`; `membership_frontier_digest: string`; `obligations: object[]?`; `signature: signature` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/PolicyCheckRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/PolicyCheckOutcome。只接收最小披露字段；decision 按 hash/cache frontier 绑定。Canonical HTTP 路径 `POST /_arkret/self/policy/check`。 |
| `ak.self.realm_link.query.list` | `path.realm_id: id` | `query.direction: enum(outbound,inbound,both)=both`; `query.link_kind_allow: string` | `realm_id: id`; `direction: enum`; `links: object[]` | response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_link_list。从 `ak.realm.link` 投影。 |
| `ak.self.realm_link.command.create` | `path.realm_id: id`; `target_realm_id: id`; `link_kind: enum` | `status: enum(active,rejected,tombstoned)=active`; `label: string`; `commitment: string` | `realm_id: id`; `target_realm_id: id`; `link_kind: enum`; `status: enum` | request_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_link_create_request_body; response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_link_mutation_outcome。构造 `ak.realm.link`；一般有向环合法；self-reference / kind / payload 校验失败返回 422，非法 FSM 迁移使用 `failed_precondition + realm_link_invalid_transition`。 |
| `ak.self.realm_link.resource.delete` | `path.realm_id: id`; `path.target_realm_id: id` | `query.link_kind: string=governed_by` | `realm_id: id`; `target_realm_id: id`; `link_kind: enum`; `status: enum` | response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_link_mutation_outcome。写 status=tombstoned 的 `ak.realm.link`。 |
| `ak.self.realm.command.archive` | `path.realm_id: id`; `archived: boolean` | `reason: string` | `ok: boolean`; `realm_id: id`; `deleted: boolean`; `archived: boolean`; `frozen: boolean` | request_schema_ref=schemas/event-payload.schema.json#/$defs/realm_archive_payload; response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view。构造 `ak.realm.archive`;`archived=false` 复原。 |
| `ak.self.realm.command.freeze` | `path.realm_id: id`; `frozen: boolean` | `reason: string` | 同 `ak.self.realm.command.archive` 响应字段 | request_schema_ref=schemas/event-payload.schema.json#/$defs/realm_freeze_payload; response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view。构造 `ak.realm.freeze`;非豁免普通写入返回 `realm_frozen`。 |
| `ak.self.realm.command.tombstone` | `path.realm_id: id`; `reason: string`; `successor_realm_id: id` | `replacement_event: ref` | `ok: boolean`; `realm_id: id`; `deleted: true`; `terminal_state: tombstoned`; `successor_realm_id: id` | request_schema_ref=schemas/event-payload.schema.json#/$defs/realm_tombstone_payload; response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view。构造 `ak.realm.tombstone`;只用于 successor 接续。 |
| `ak.self.realm.command.destroy` | `path.realm_id: id`; `reason: string` | `retention_policy_id: ref`; `verification_stub_required: boolean` | `ok: boolean`; `realm_id: id`; `deleted: true`; `terminal_state: destroyed` | request_schema_ref=schemas/event-payload.schema.json#/$defs/realm_destroy_payload; response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view。构造 `ak.realm.destroy`;产品"解散 Realm"的无 successor 关闭入口。 |
| `ak.self.realm_link.query.effective_policy` | `path.realm_id: id` | 无 | `realm_id: id`; `effective_policy: object`; `inheritance_chain: id[]`; `inheritance_mode: enum(explicit,none)` | response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_effective_policy_outcome。沿 `governed_by` / `inherits_policy_from` 祖先合并；无继承声明时 `inheritance_mode=none`。 |
| `ak.self.realm_organization.query.list` | `path.realm_id: id` | 无 | `realm_id: id`; `relationships: object[]`(每行 `statement_id: string`; `organization_id: did`; `relationship: enum(owner,governance,sponsor,directory_certifier)`; `status: enum(active,revoked)`; `control_scopes: string[]`; `issued_at: datetime`; `not_before: datetime?`; `expires_at: datetime?`; `issuer_role: enum`; `delegation_ref: string?`; `lifecycle_phase: enum(verified_active,revoked_or_expired)`); `declared_organization_hints: did[]` | response_schema_ref=schemas/realm-organization-operations.schema.json#/$defs/realm_organization_relationship_list。从 `ak.realm.organization` 投影(latest-per-(organization_id, relationship))。`declared_organization_hints` 是无验证语句的 `owning_organizations` 声明,MUST NOT 渲染为官方/治理/背书(见 [`../models/realm-and-space.md` §2.3.0](../models/realm-and-space.md))。 |
| `ak.self.realm_policy_server.resource.get` | `path.realm_id: id` | 无 | `realm_id: id`; `policy_server_did: did`; `policy_server_url: string`; `cache_ttl_seconds: int`; `timeout_ms: int`; `on_timeout: enum(fail_closed,deny)`; `updated_at: datetime`; `from_org_fallback: boolean` | response_schema_ref=schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_view。Realm 与 `governed_by` 祖先链都未声明时返回 `not_found`。 |
| `ak.self.realm_policy_server.resource.replace` | `path.realm_id: id`; `policy_server_did: did`; `policy_server_url: string` | `cache_ttl_seconds: int`; `timeout_ms: int`; `on_timeout: enum(fail_closed,deny)=fail_closed` | 同 `ak.self.realm_policy_server.resource.get` 响应字段 | request_schema_ref=schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_replace_request_body; response_schema_ref=schemas/realm-policy-server-operations.schema.json#/$defs/realm_policy_server_view。构造 `ak.realm.policy_server`(admission capability `ak.policy.manage`)。 |
| `ak.self.realm_policy_server.resource.delete` | `path.realm_id: id` | 无 | 无响应体 | tombstone per-Realm `ak.realm.policy_server` cell;`ak.policy.manage`；调用方回退 `governed_by` 链或本地能力检查。 |
| `ak.self.realm.resource.get` | `path.realm_id: id` | 无 | `ok: boolean`; `realm_id: id`; `owner: did`; `members: did[]`; `deleted: boolean` | response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view。不可见返回 `not_found`。 |
| `ak.self.realm.query.export` | `path.realm_id: id` | 无 | `schema: const(ak.export.realm.v1)`; `realm_id: id`; `generated_at: datetime`; `operations: object[]`; `events: object[]` | response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_export。全量 event-log + operation dump；payload 可见性按 Realm policy。 |
| `ak.self.realm.moderation_policy.query.effective` | `path.realm_id: id` | 无 | `realm_id: id`; `inheritance_mode: enum(none,organization)`; `inheritance_chain: did[]`; `organization_policy_layers: object[]`; `effective_rules: object[]`; `realm_policy: object?` | response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_effective_moderation_policy。组织继承的合并审核策略视图。 |
| `ak.self.realm.moderation_policy.resource.replace` | `policy: object`(自由 `ak.realm.moderation_policy` 文档) | 无 | `kind: const`; `realm_id: id`; `policy: object`; `updated_by: did`; `updated_at: datetime` | request_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_moderation_policy_replace_request_body; response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_moderation_policy_document。仅 Realm owner 可写；放宽组织策略禁止动作的 override 需文档内嵌组织 approval，否则返回 `failed_precondition` 且 `reason_code=requires_organization_approval`。 |
| `ak.self.consent.query.list` | 无 | 无 | `ok: boolean`; `cells: object[]` | response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_cell_list。仅 authenticated holder（或显式 holder controller）可读；peer 不得获得 cell/dot/expiry。 |
| `ak.self.consent.resource.get` | `path.holder_did: did`; `query.peer: did` | `query.consent_scope: enum` | `ok: boolean`; `cell_id: string`; `holder_did: did`; `peer_did: did`; `consent_scope: enum`; `state: enum(active,no_consent)`; `active_grant_dots: string[]`; `grant_dots: string[]`; `revoked_dots: string[]`; `expires_at: datetime?`; `requested_at: datetime?`; `updated_at: datetime` | response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_cell_view。调用方 MUST 为 holder 或显式 holder controller；peer 禁止读取。 |
| `ak.self.consent.command.grant` | `path.holder_did: did`; `peer_did: did` | `consent_scope: enum=direct_message`; `expires_at: datetime` | 同 `ak.self.consent.resource.get` 响应字段 | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_update_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_cell_view。构造 `ak.consent.grant`;调用方 MUST 有权写 holder consent。 |
| `ak.self.consent.command.revoke` | `path.holder_did: did`; `peer_did: did` | `consent_scope: enum=direct_message`; `expires_at: datetime` | 同 `ak.self.consent.resource.get` 响应字段 | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_update_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_cell_view。构造 `ak.consent.revoke`;`consent_scope=any` 撤销级联所有具体 scope。 |
| `ak.self.consent.command.request` | `holder_did: did` | `peer_did: did`; `consent_scope: enum=direct_message` | `ok: const(true)`; `accepted_for_processing: const(true)` | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_request_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_request_outcome。`peer_did` 缺省并 MUST 等于认证 actor；holder 不存在、policy deny、限速、静默丢弃与进入 quarantine 的响应/时序 MUST 不可区分，且不得返回 consent cell。 |
| `ak.self.account_data.query.list` | 无 | 无 | `entries: object[]` | response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_list。`content` 对服务不透明。 |
| `ak.self.account_data.resource.get` | `path.data_type: string` | 无 | `data_type: string`; `content: any`; `updated_at: datetime` | response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_entry。未设置返回 `not_found`。 |
| `ak.self.account_data.resource.replace` | `path.data_type: string`; `content: any` | 无 | 同 `ak.self.account_data.resource.get` 响应字段 | request_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_replace_request_body; response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_entry。构造 `ak.account_data.set`;controller-private registered type 拒绝 agent / applet / service principal。 |
| `ak.self.account_data.resource.delete` | `path.data_type: string` | 无 | `ok: boolean`; `data_type: string` | response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_delete_outcome。删除并向其他设备 fanout actor-private update。 |
| `ak.self.read_cursor.command.advance` | `realm_id: id`; `read_scope: object`; `position: object` | 无 | `realm_id: id`; `actor_id: did`; `device_id: id`; `read_scope: object`; `position: object`; `updated_at: datetime` | request_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_cursor_advance_request_body; response_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_marker_outcome。构造 `ak.read_cursor.advance`;`read_scope` / `position` 形态见 read-cursor.schema.json;多设备按 HLC max 收敛。 |
| `ak.self.read_cursor.query.list` | 无 | `query.realm_id: id` | `markers: object[]` | response_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_cursor_list。 |
| `ak.self.moderation.command.report` | `realm_id: id`; `target_ref: id`; `report_reason_code: enum`; `reporter: did` | `description: string`; `evidence_refs: id[]` | `report_id: id`; `status: string`; `routed_to: did[]?` | request_schema_ref=schemas/moderation-report.schema.json; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ModerationReportOutcome。reporter 必须可见 target；只对 moderators 可见。 |
| `ak.edge.applet.query.ping` | 无 | 无 | `ok: boolean`; `applet_id: id`; `service_id: did`; `protocol_version: string` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_ping_outcome。不得泄露 private namespace。 |
| `ak.edge.applet.query.describe` | 无 | 无 | `ServiceDescribe` | public mode 只返回公开 capabilities；applet-specific 字段作为扩展字段返回。 |
| `ak.self.applet.install.command.preview` | `applet_package: object`; `effective_scope: object`; `approval_request: object` | 无 | `InstallPlan` | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_preview_request_body; response_schema_ref=schemas/applet-install-plan.schema.json。self/admin aggregate operation；只读预览，不写 Realm history；返回 canonical `plan_digest`。 |
| `ak.self.applet.command.install` | `header.Idempotency-Key: string`; `plan_digest: hash`; `applet_package: object`; `effective_scope: object`; `approved_scopes: object[]` | `actor_policy: object`; `e2ee_policy: object`; `widget_policy: object` | `ok: boolean`; `install_id: string`; `registration_event_ref: ref?`; `registration_epoch: hash`; `bot_actor_id: did`; `capability_grant_refs: ref[]`; `membership_event_refs: ref[]`; `e2ee_authorization_refs: ref[]`; `widget_policy_ref: ref?`; `effective_status: enum(installed,partially_installed,rejected)`; `rejected: object[]` | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_request_body; response_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_outcome。self/admin aggregate operation；MUST 重新计算 plan，`plan_digest` 不匹配返回 `applet_install_plan_mismatch`；不创建 install 专用 durable Event。 |
| `ak.self.applet.command.revoke` | `header.Idempotency-Key: string`; `path.applet_id: id`; `effective_scope: object`; `reason_code: string`; `revoke_mode: enum(revoke_all,revoke_runtime_only,revoke_widget_only,revoke_delegated_sessions)` | `proof?: AccountLifecycleProof` | `ok: boolean`; `revoked_refs: ref[]?`; `rejected: object[]?` | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_request_body; response_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_outcome。self/admin aggregate operation；撤销 bound grants / widget tokens / delegated sessions；delegated session revoke 的 `proof` MUST 签署 Account Authority session revoke applet selector；revoke 后未来写入返回 `applet_revoked` 或更细 reason。 |
| `ak.self.applet.ghost.command.provision` | `header.Idempotency-Key: string`; `path.applet_id: id`; `schema: const(ak.applet.ghost_actor.provision_request.v1)`; `applet_id: id`; `service_id: did`; `ghost_actor_id: did`; `protocol: string`; `tenant: string`; `external_user_id: string`; `realm_id: id`; `external_ref: object` | `display_name: string` | `ghost_actor_id: did`; `profile_event_ref: ref`; `accountability_grant_ref: ref`; `authorization_ref: ref`; `display_name: string?` | request_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_actor_provision_request_body; response_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_actor_provision_outcome。调用方是已安装 bridge Applet 的 service DID；服务端 MUST 校验 active registration 覆盖 caller service DID、`ghost_actor_id` 命中 registration actor namespace、`realm_id` 在 effective scope 内；同一 `(applet_id, protocol, tenant, external_user_id)` 重复 provision MUST 幂等返回既有 refs。见 `applet-integration.md` §9.1。 |
| `ak.edge.applet.command.transaction` | `header.Idempotency-Key: string`; `source_service_id: did`; `events: EventEnvelope[]` | `ephemeral: EphemeralEnvelope[]` | `ok: boolean`; `rejected: object[]?`; `retry_after_ms: int?` | request_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_request_body; response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_outcome。Applet 必须验证 event signature、namespace、capability；按 `(source_service_id, Idempotency-Key)` 幂等。 |
| `ak.edge.applet.actor.query.resolve` | `path.actor_id: did` | 无 | `exists: boolean`; `actor_id: did?`; `display_name: string?`; `external_ref: object?` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_actor_view。actor_id 必须命中 namespace。 |
| `ak.edge.applet.realm.query.resolve` | `path.realm_id_or_alias: string` | 无 | `exists: boolean`; `realm_id: id?`; `title: string?`; `external_ref: object?` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_realm_view。必须命中 portal namespace 或授权查询。 |
| `ak.edge.applet.query.protocol_metadata` | `path.protocol: string` | 无 | `protocol: string`; `display_name: string`; `icon_blob_ref: string?`; `field_types: object`; `instances: object[]?` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_protocol_metadata。instance list 可要求授权。 |
| `ak.edge.applet.third_party_users.query.list` | `query.protocol: string`; `query.external_id: string` | `query.instance_id: string` | `actor_id: did?`; `exists: boolean`; `external_ref: object?` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_user_list。查询字段必须在 registration namespace 内。 |
| `ak.edge.applet.third_party_locations.query.list` | `query.protocol: string`; `query.external_id: string` | `query.instance_id: string` | `realm_id: id?`; `exists: boolean`; `external_ref: object?` | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_location_list。查询字段必须在 portal namespace 内。 |
| `ak.open.invite_locator.query.resolve` | `locator_token: string` | 无 | `principal_locator` object | request_schema_ref=schemas/principal-locator.schema.json#/$defs/principal_locator_resolve_request_body; response_schema_ref=schemas/principal-locator.schema.json。locator token MUST 只在 JSON body 中提交；二维码 / 链接 SHOULD 把 token 放在 URL fragment。返回值是签名 `principal_locator`，不是 membership grant、不是 `member_delivery_binding`。 |
| `ak.open.agent_pairing.query.resolve` | `pairing_token: string` | 无 | `agent_pairing_bootstrap` object | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pairing_resolve_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap。pairing token MUST 只在 JSON body 中提交；二维码 / 链接 SHOULD 把 token 放在 URL fragment。返回值只含 pairing bootstrap 6 字段。 |
| `ak.open.mimi.query.provider_directory` | 无 | `query.provider_id: string`; `query.features: string[]` | `providers: object[]`; `features: object`; `expires_at: datetime?` | response_schema_ref=schemas/mimi-interop.schema.json。只返回公开 provider capability，不泄露 Realm membership。 |
| `ak.open.mimi.exchange.request_key_material` | `requester: did`; `strand_id: id`; `device_id: id` | `mimi_room_uri: string`; `realm_id: id`; `mls_group_id: string`; `epoch: int`; `proofs: proof[]` | `key_packages: object[]?`; `group_info: object?`; `failures: object[]?`; `signature: signature?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_key_material_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_key_material_outcome。必须存在 accepted `ak.mimi.room_binding` 且 requester 有对应 room / device 权限。 |
| `ak.open.agent_pairing.command.submit_runtime_key_request` | `pairing_code: string`; `pairing_request_id: string`; `agent_id: did`; `verification_method: did_url`; `public_key`; `proof_of_possession: proof` | 无 | `agent_runtime_approval_outcome` object | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_outcome。runtime 用 pairing bootstrap 中的 `pairing_code` + local key PoP 提交待 controller 审批的 runtime key request;pairing code 与 PoP MUST 只在 JSON body 中提交，不得出现在 URL path 或 query;controller 仍须签署 `ak.agent.key.authorize` 才最终授权。 |
| `ak.open.agent_pairing.query.runtime_key_request_status` | `pairing_request_id: string`; `pairing_code: string`; `agent_id: did` | 无 | `agent_runtime_approval_status_outcome` object | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_outcome。runtime 轮询 controller 审批结果；三元组查询凭证 MUST 只在 JSON body 中提交；记录不存在与 `pairing_code` / `agent_id` 不匹配 MUST 不可区分；pending 已过期 MUST 报告为 `agent_status=pairing_expired`（懒过期）；审批通过后带 `authorized_event_ref` 与授权 key 绑定字段，runtime MUST 本地比对 `authorized_public_key_digest`。 |
| `ak.open.mimi.command.update_room` | `path.strand_id: id`; `mls_group_id: string`; `update: object` | `epoch: int`; `confirmed_transcript_hash: string`; `sender_actor_id: did` | `accepted: boolean`; `room_state_ref: id?`; `rejected: object[]?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_room_update_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_room_update_outcome。更新必须映射到 Arkret Strand discussion track / Realm policy 授权范围内；`confirmed_transcript_hash` 沿用 MLS/MIMI 外部标准字段名。 |
| `ak.open.mimi.command.notify` | `path.strand_id: id`; `notification: object` | `origin_provider: did`; `routing: object` | `accepted: boolean`; `retry_after_ms: int?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_notify_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_notify_outcome。只可传递最小 fanout / delivery signal，不得携带未授权明文。 |
| `ak.open.mimi.command.submit_message` | `path.strand_id: id`; `sender_actor_id: did`; `device_id: id`; `ciphertext: object` | `mls_group_id: string`; `epoch: int`; `associated_data: object` | `event_ref: id?`; `delivery: object`; `rejected: object[]?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_outcome。必须校验 MLS epoch、有效 discussion access、capability 和 `ak.mimi.room_binding`。 |
| `ak.open.mimi.query.group_info` | `path.strand_id: id` | `query.epoch: int`; `query.include_proof: boolean` | `group_info: object`; `room_binding_ref: id?`; `proofs: proof[]?` | response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_group_info_outcome。只能返回 requester 授权可见的 MLS groupInfo / room projection。 |
| `ak.open.mimi.command.request_consent` | `requester: did`; `target: object`; `purpose: enum(invite,direct_message,voice_call,video_call,presence,any)` | `strand_id: id`; `expires_at: datetime`; `proofs: proof[]` | `consent_id: id`; `status: string`; `challenge: string?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_outcome。consent 只表达联系 / invite 意图，不授予 Realm read/write。 |
| `ak.open.mimi.command.update_consent` | `consent_id: id`; `decision: enum(accept,deny,revoke)`; `actor_id: did`; `signature: signature` | `reason: string`; `expires_at: datetime` | `status: string`; `updated_at: datetime`; `event_ref: id?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_outcome。必须绑定原 request、target identity proof 和 replay protection。 |
| `ak.open.mimi.query.identifiers` | `identifiers: object[]` | `requester: did`; `privacy_profile: string`; `proofs: proof[]` | `matches: object[]`; `proofs: proof[]?`; `has_more: boolean` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_outcome。SHOULD 使用 private contact discovery；不得返回原始通讯录或完整关系图谱。 |
| `ak.open.mimi.command.report_abuse` | `strand_id: id`; `target_ref: string`; `reporter: did`; `abuse_reason_code: string` | `evidence_package: object`; `franking_proof: object`; `description: string` | `report_id: id`; `status: string`; `routed_to: did[]?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_outcome。E2EE report 只能向授权 moderation recipient 解密 evidence。 |
| `ak.open.mimi.command.proxy_download` | `asset_ref: string`; `requester: did` | `strand_id: id`; `ohttp_context: object`; `range: string` | `download_ref: string`; `headers: object?`; `expires_at: datetime?` | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_outcome。当 Realm asset privacy policy 要求 proxy/OHTTP 时不得返回 direct object-store URL。 |
| `ak.gate.account.exchange.create_handoff` | `request_id: id`; `proof: AccountHandoffAuthenticationProof` | 无 | `request_id: id`; `account_handle: handle`; `account_handoff_grant: string`; `expires_at: datetime`; `allowed_operations: const[]`; `binding: AccountHandoffBinding` | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_handoff_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_handoff_outcome。DPoP holder-bound OIDC handoff；`account_handle` 仅供 UI / 本地文件命名，不是身份或授权证据；闭合权限集，不是普通 OAuth bearer 或 session grant。 |
| `ak.gate.account.command.issue_identity_binding_challenge` | `request_id: id`; `lease_id: string`; `lease_fence: int`; `did_operation: DidOperationSubmitRequestBody` | 无 | `request_id: id`; `challenge_id: string`; `challenge: string`; `purpose: const(account_binding)`; `principal_id: did`; `operation_digest: hash`; `lease_id: string`; `lease_fence: int`; `dpop_jkt: string`; `audience: did`; `origin: uri`; `trust_domain: id`; `issued_at: datetime`; `expires_at: datetime` | request_schema_ref=schemas/account-operations.schema.json#/$defs/identity_binding_challenge_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/identity_binding_challenge_outcome。完整 operation 进入公开 checkpoint；challenge 必须服务端生成、共享持久化、单次使用、≤300 秒。 |
| `ak.gate.account.command.register` | `principal_id: did` | `display_name: string`; `device_id: id`; `proof: AccountRegistrationControlProof`; `identity_creation: IdentityCreationRegistration`; `policy_evidence: AccountRegistrationPolicyEvidence` | `principal_id: did`; `state: enum(active,soft_logged_out,locked,suspended,deactivated,erasure_pending)`; `devices: object[]`; `primary_handle_claim?: HandleClaim`; `primary_handle_claim_ref?: string`; `handle_claim_digests?: hash[]`; `profile?: ActorProfile`; `registration_audit?: AccountRegistrationAudit`; `binding_receipt?: AccountBindingReceipt` | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_register_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_register_outcome。已发布 DID 分支的 `proof` 仅允许 DID-bound / paired-device control proof；OIDC、passkey 或 agent authentication 单独不足以绑定 DID。account-first 分支由 Account Authority 内部发布 entry 0 并可恢复地绑定；`proof` 与 `identity_creation` 互斥；不得包含裸 `handle`、恢复秘密或 root private key。 |
| `ak.gate.account.command.issue_session_grant` | `principal_id: did`; `proof: SessionGrantRequestBodyProof` | `device_id: id`; `requested_scope: string[]`; agent branch: `agent_key_authorization_ref`, `agent_scope_request`, `dpop_binding_proof`, `requested_scope_disclosure?` | `principal_id: did`; `device_id: id?`; `session_grant: string`; `expires_at: datetime`; `granted_scope: string[]?`; `scope_details: object?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantOutcome。Account Authority 单次返回客户端可见登录结果；`principal_id` 必须已有 verified binding。`oidc_code_exchange` 由 Authority 换码；`pre_registration_handoff` 使用 DPoP-bound account handoff，且其 account 必须绑定请求 principal；`agent_key_proof` 仍使用 verifier-private scope evidence。 |
| `ak.gate.account.command.revoke_session` | 无 | `target_grant_id: id`; `target_device_id: id`; `all_sessions: true`; `applet_id: id`; `effective_scope: object`; `registration_epoch: hash`; `service_id: did`; `capability_grant_refs: ref[]`; `proof: AccountLifecycleProof` | `revoked_count: int`; `revoked_grant_ids?: id[]` | request_schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_outcome。空 body 撤当前 session；grant/device/all_sessions/applet selector 互斥；跨 grant/device/all_sessions/applet 需要 fresh proof；不撤 device authorization。 |
| `ak.gate.account.command.refresh_session_grant` | `grant_jwt: string`; `device_id: id`; `proof: SessionGrantRefreshProof` | `audience: string` | `grant_id: string`; `grant_jwt: string`; `session_public_key: string`; `expires_at: datetime`; `audience: string`; `scopes: string[]`; `dpop_jkt: string`; `previous_grant_id: string` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRefreshRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRefreshOutcome。DPoP holder proof 证明持有 grant 的 `cnf.jkt` 密钥；fresh DID/device proof 必须绑定 principal、device、audience、request digest、challenge 与 <=300s 窗口；轮换出新 grant（`cnf.jkt` 不变、新 minutes-to-hours expiry），旧 grant single-use 吊销；`audience` 不得跨轮换变更（否则 `audience_mismatch`）。 |
| `ak.gate.account.command.logout_auth_session` | `grant_jwt: string` | `logout_request_digest: string`; `validated_at: timestamp`; `reason_code: enum(account_logout)` | `ok: bool`; `grant_chain_terminated: bool`; `auth_session_logged_out: bool` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthSessionLogoutRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthSessionLogoutOutcome。Account Authority → Auth Server 的 S2S Auth-side logout 子操作；使用与 session-grant introspection 同族的部署内 S2S bearer；登出该 grant 所属 Auth-side session / `browser_session` 并终结 grant 轮换链。该操作幂等；已登出、已吊销、未知或已剪枝 grant/session 均按成功处理。普通客户端 MUST NOT 调用。 |
| `ak.gate.account.command.logout` | `header.Authorization: bearer`; `header.DPoP: proof` | 无 | `ok: bool`; `revoked: bool` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountLogoutRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountLogoutOutcome。Account Authority 普通 hard logout 单入口：Authorization 出示当前 `ak.session.grant`，DPoP holder proof 绑定 grant 与 `/logout` endpoint；内部终结 Auth-side session / grant 轮换链与 Principal 本地 account session / 设备会话记录，并清该设备待投递 to-device / push registration；不同于 `revoke_session`（仅撤会话令牌）。 |
| `ak.gate.account.command.introspect_session_grant` | 无 | `id: string`; `grant_jwt: string`; `audience: string`; `proof?: object` | `active: bool`; `status: string`; `proof_required: bool`; `one_time_use_consumed: bool`; `grant: object?` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantIntrospectRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantIntrospectOutcome。RFC 7662 式 server-to-server 内省；`id` 与 `grant_jwt` 二选一；`session_grant_introspection_bearer` 或 admin scope 认证；**read-only**，MUST NOT 消费/吊销 grant；`proof` 为 S2S 可选附加确认，不是普通客户端 self-path header；`grant.cnf_jkt` MUST 返回（供 Principal Server 校验 `/_arkret/self/*` 每请求 DPoP，见 [`api-conventions.md` §3.3](./api-conventions.md)）；`grant.session_public_key` 供 RFC 9421 PoP 校验；`browser_session` finished 后 MUST 返回 inactive。 |
| `ak.gate.account.command.pair_device` | `pairing_code: string`; `new_device_pubkey: object`; `challenge_signature: signature` | `display_name: string`; `device_metadata: object` | `device_id: id`; `authorized_event_ref: ref`; `device_grant: object?`; `key_backup_hint: object?` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_pair_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_pair_outcome。pairing code / proof 必须短期有效、一次性使用，并绑定目标 Account Authority `gate_account_base` / origin / request canonical hash；服务端 MUST 按 principal、授权源设备和目标 origin 限速。 |
| `ak.gate.account.command.pair_agent_key` | `agent_id: did`; `verification_method: did_url`; `public_key: object`; `proof_of_possession: proof`; `requested_scope_disclosure: AgentRequestedScopeDisclosure`; `authorize_event: EventEnvelope`; `header.Idempotency-Key=authorize_event.event_id` | `runtime_attestation: object` | `ok: boolean`; `authorized_event_ref: ref` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_outcome。commit 前 MUST 验证 controller-owned managed-PCR backup 覆盖 pre-commit frontier 且 `pcr_recovery.status=ready`，否则 `agent_pcr_recovery_not_ready` 且 pairing handle 不消费。`requested_scope_disclosure` 是 verifier/audience/challenge-bound 私有 sidecar；MUST 验证 controller proof、单次 challenge、接收窗口与 accepted-at DID digest，且不得写入 `authorize_event` 或公开 history。`authorize_event` MUST 是 Agent PCR 中 `actor_id=agent_id`、`executed_by=controller`、带可验证 controller delegation 的完整签名 Event。`verification_method` 的 DID 部分 MUST 与 `agent_id` bit-identical。相同 Event / pairing 重试幂等；同 Event ID 不同 bytes 返回 conflict。split Account Authority MUST 把完全相同的 typed request 委托到权威 Principal Server 的同一 canonical operation，MUST NOT 改用产品私有 fan-out endpoint；只有 downstream durable acceptance + activation 后才能返回成功。accepted authorize Event 推进 frontier 后，恢复投影转 `stale` 直至 post-commit backup accepted；这不回滚本次 pairing。replacement re-pairing 时，controller-signed `authorize_event.payload.supersedes[]` MUST 精确列出全部既有 active authorization，reducer 接受该单一 Event 时原子替换并记录 reason=`superseded_by_repairing`。 |
| `ak.gate.account.command.enroll_device` | `device_id: id`; `device_public_key: string`; `hpke_key: string`; `algorithms: string[]`; `actor_seq: int` | `bootstrap_create_event_id: id`; `not_before: datetime` | `principal_id: did`; `device_id: id`; `authority_did: did`; `authorized_event: object` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_enroll_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_enroll_outcome。托管 DID（account-authority）设备入册，见 [`crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md) 与 [`identity/key-management.md` §5.0.6](../identity/key-management.md)。`Authorization` 出示当前 `ak.session.grant`，`DPoP` holder proof 绑定 grant `cnf.jkt` 与本 endpoint。入册权威用其**持久**签名密钥铸造 `service_attested` `ak.device.authorize`（`executed_by`/`authorization_ref`/`enrollment_authority_binding`），**MUST NOT** 持有或伪造本 principal 的 SSK；返回完整签名 Event，调用方原样提交到 `POST /_arkret/self/events`。首设备原子 bootstrap 时 `actor_seq` MUST 为 `1`，请求 MUST 携带同一提交批次内 root-signed `ak.realm.create` 的 `bootstrap_create_event_id`；权威 MUST 把该 ID 写为 authorize Event 唯一的 `prev_refs`。非首设备入册 MUST 省略该字段，权威不得接受任意调用方指定的其它 predecessor。区别于 `pair_device`（§2.1 已授权设备 SAS/QR 审批，携 `pairing_code`）：本操作是无兄弟设备可审批的 bootstrap / 首台设备路径。服务端 MUST 按 principal 与目标 origin 限速。 |
| `ak.self.agent.command.provision` | 无 | `display_name: string?`; `slug: string`; `requested_scope: object`; `accountability: object?`; `pairing_ttl_ms: int?` | `agent_id: did`; `principal_control_realm_id: id`; `controller_authorization_ref: did_url`; `requested_scope_digest: hash`; `pcr_recovery: {status: pending}`; `pairing_request_id: string`; `pairing_code: string?`; `expires_at: datetime` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_provision_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_provision_outcome。controller 无 accepted recovery policy 时在任何副作用前 fail closed。operation 分配 Agent DID/PCR binding，在 accepted Agent DID service entry 只固定 scope digest commitment，完整 scope 保持 controller-private；在 controller PCR 仅写 accountability/selector facts，并创建 runtime pairing request。`requested_scope` 必填且 immutable，只建立全局 Agent key/session 上限，不得生成任何内容 grant。后续 Agent key scope、Realm grant、participation 与 session request可收窄但不得超过其 action/resource/constraint 上限。controller 必须重算返回 digest 后再继续，并为需要判定的 verifier 生成短时、单次 challenge-bound 私有 disclosure；controller E2EE client 随后本地生成并提交 Agent PCR MLS/genesis/Profile state 及 controller-owned recovery backup。服务端不得生成 MLS private state，不创建 provision 专用 Event，也不得在首次 pairing 前预写 `ak.agent.key.authorize`。Agent 自身字段使用必填 `slug`，selector claim 外部引用使用 `agent_slug`。 |
| `ak.self.agent.command.renew_pairing` | `path.agent_id: did` | `pairing_ttl_ms: int?` | `agent_id: did`; `principal_control_realm_id: id`; `controller_authorization_ref: did_url`; `requested_scope_digest: hash`; `pcr_recovery: object`; `pairing_mode: enum(bootstrap,replacement)`; `pairing_request_id: string`; `pairing_code: string?`; `expires_at: datetime` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_renew_pairing_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_renew_pairing_outcome。对任何非 terminal agent 原地重开 pairing：签发全新一次性 pairing handle，旧 handle 永久不可解析，并返回 immutable DID binding 的同一 `requested_scope_digest`、当前 `pcr_recovery`（`pending` / `ready` / `stale`）与固定分支 `pairing_mode`。`pending_runtime_key` / `pairing_expired` 走 `bootstrap`；`active` / `paused` 走 `replacement`（status / 既有 key / grant 在新配对完成前不变，完成时由 controller-signed authorize Event 的精确 `supersedes[]` 原子替换）；两种分支都不得创建、撤销或重发 Realm grant；`deactivated` MUST 拒绝。pair commit 仍仅接受 `pcr_recovery.status=ready`。见 [`identity/key-management.md` §3.6.1](../identity/key-management.md)。 |
| `ak.self.agent.query.list` | 无 | `query.cursor: cursor`; `query.limit: int`; `query.state: string` | `agents: object[]`; `next_cursor: cursor?`; `has_more: boolean` | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_list。只列出调用方可管理的 native personal agent。 |
| `ak.self.agent.resource.get` | `path.agent_id: did` | 无 | `agent: object`; `status: enum(pending_runtime_key,active,pairing_expired,paused,deactivated)`; `grants: object[]?`; `key_state: object?` | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_view。只返回 controller 或 policy-authorized admin 可见的 agent projection；`key_state.pcr_recovery` 必须按 active controller backup series 与 Agent PCR current frontier 投影 `pending` / `ready` / `stale`。 |
| `ak.self.agent.command.pause` | `path.agent_id: did` | `reason: string` | `ok: boolean`; `status: enum(paused)` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pause_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state。暂停 agent 并拒绝新 agent session grant。 |
| `ak.self.agent.command.resume` | `path.agent_id: did` | `sidecar_exposure_ack: object` | `ok: boolean`; `status: enum(active)` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_resume_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state。必须重新校验 controller/agent/key/grant freshness；新增 sidecar exposure 时要求显式确认。 |
| `ak.self.agent.command.deactivate` | `path.agent_id: did` | `reason: string` | `ok: boolean`; `status: enum(deactivated)` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_deactivate_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state。terminal transition；fan-out agent key revoke、capability revoke 与 runtime endpoint revoke。 |
| `ak.self.agent.grant.command.attach` | `path.agent_id: did`; `grant: CapabilityGrant`; `requested_scope_disclosure: AgentRequestedScopeDisclosure` | 无 | `ok: boolean`; `grant_id: id` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_grant_attach_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_grant_attach_outcome。`grant` 是完整、已签名的 `capability-grant.schema.json` 对象；`grant.subject` 必须是 path Agent principal，`grant.issuer` 必须是 authenticated controller，`grant.realm_id` 必填且 Event 必须写入该受治理 Realm。admission verifier MUST 私下验证 disclosure 的 controller/verifier/audience/challenge/freshness/proof，重算 accepted-at DID commitment；`grant.actions` 必须是披露 `requested_scope.actions` 的子集，显式内容 resource ceiling 存在时 `grant.resources` 还必须在该 ceiling 内，且 actions/resources 不得超过 controller 可委托范围。完整 scope/disclosure 不得复制进 grant 或 Realm Event。服务端不得补默认 `ak.event.read`、改写 resource selector 或返回成功却只写 audit log。 |
| `ak.self.agent.grant.resource.delete` | `path.agent_id: did`; `path.grant_id: id` | 无 | `ok: boolean`; `revoked_at: datetime` | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_grant_detach_outcome。撤销或解绑 agent grant，后续 agent action proof fail closed。 |
| `ak.self.agent.sidecar_thread.command.ensure` | `controller_id: did`; `context_ref: object` | `addressed_agent_ids: did[]` | `ok: boolean`; `private_circle_id: id`; `private_strand_id: id`; `private_relation_id: id`; `pending_member_reconciliations: object[]?` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_sidecar_thread_ensure_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_sidecar_thread_ensure_outcome。idempotent ensure；Sidecar Circle 按 `(context_ref.realm_id, controller_id)` 复用，Sidecar private Strand 按 `(controller_id, normalized_context_ref)` 复用；普通 `ak.circle.create` 能力不会被隐式授予；在 eligibility、Circle membership active，且 MLS-backed Circle 的 MLS membership active 后才 fanout。 |
| `ak.self.agent.participation.resource.replace` | `path.agent_id: did`; `scope: AgentParticipationScope`; `selection: AgentParticipation` | 无 | `ok: boolean`; `effective_participation: AgentParticipationEntry`; `entries?: AgentParticipationEntry[]` | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_participation_replace_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_participation_outcome。controller-only；服务端必须把 provisioned `requested_scope` 作为最外层全局 ceiling，再校验 `selection ⊆ effective_ceiling(scope)`，并物化 reply / act_on_behalf grant 与第三方 mention gate；Realm / Circle / Strand ceiling 不得补回全局 scope 未允许的能力。 |
| `ak.self.agent.participation.resource.get` | `path.agent_id: did` | `query.scope?: AgentParticipationScope` | `ok: boolean`; `entries: AgentParticipationEntry[]` | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_participation_outcome。controller 或该 agent runtime 可读取 selection、ceiling 与 effective participation；未知或 stale ceiling 必须 fail closed。 |
| `ak.gate.account.exchange.complete_oidc` | `state: string`; `code: string` | `nonce: string`; `redirect_uri: url` | `redirect_url: url` | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountOidcCallbackRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountOidcCallbackOutcome。部署可选的 browser redirect landing / handoff；MUST 校验 state、nonce、服务端配置的 issuer binding，并且 MUST NOT 返回 `SessionGrantOutcome` 或 `ak.session.grant`。 |
| `ak.self.media.query.ice_config` | `realm_id: id`; `call_id: id`; `actor_id: did`; `device_id: id`; `mode: enum(p2p,sfu,turn)` | 无 | `ttl_seconds: int`; `refresh_lead_seconds: int`; `issued_at: datetime`; `issued_at_bucket: datetime`; `bucket_seconds: int`; `ice_servers: object[]`; `constraints: object?`; `signature: signature` | request_schema_ref=schemas/media-operations.schema.json#/$defs/media_ice_config_request_body; response_schema_ref=schemas/ice-config-response.schema.json。actor 必须有 call/media capability；Realtime Media Server 必须被委托；TURN pseudonym bucket 固定 300s。 |

### 2.5 Sender-constrained 会话出示（RFC 9421 PoP）

会话出示的推荐序、SHOULD 默认规则与高安全 profile MUST 升级见 [`api-conventions.md` §3 / §3.2](./api-conventions.md)。`/_arkret/self/*` 的默认会话凭据是 `ak.session.grant` + `DPoP`（[`api-conventions.md` §3.3](./api-conventions.md)）；本节固定的 RFC 9421 PoP header 形状用于在该默认之上为带 body 写与敏感读叠加 HTTP Message Signature。

客户端做 PoP 出示时，用 `ak.session.grant` 委托的 `session_public_key` 对应私钥对请求做 RFC 9421 HTTP Message Signature，header 形状与联邦 service-to-service 出示（§3 与 `federation.md` §3.2）同栈：

```http
POST /_arkret/self/events
Authorization: Bearer <ak.session.grant>
Content-Digest: sha256=:<base64>:
Idempotency-Key: <opaque-key>
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest" "idempotency-key");created=...;expires=...;keyid="<session_public_key kid>"
Signature: sig1=:base64...:
```

header 规则：

- `Signature-Input` 的 covered components MUST 至少包含 `@method`、`@target-uri`、`@authority`；带 body 的请求 MUST 包含 `content-digest`（编码遵循 RFC 9530，覆盖 canonical request body，接收方 MUST 在验签前先校验 body 实际 hash 与 header 一致）。
- 参与幂等 / replay key 的 `Idempotency-Key` MUST 进入签名 transcript；出现 `X-Arkret-Wait-For` 时 SHOULD 一并覆盖，避免被替换。
- 签名 parameters MUST 包含 `created` 与 `expires`；`keyid` MUST 指向当前会话 `ak.session.grant` 委托的 `session_public_key` kid。
- 接收方 MUST 校验签名密钥与 grant 绑定的 principal / device / audience / origin 一致，并按既有 replay window（签名时效窗口，量级见 `federation.md` §3.2 / `encoding.md` §6）拒绝过窗或重放出示；时效窗口外的逐字节重放即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝。
- `Authorization: Bearer` header MAY 与 DPoP / PoP 签名并存（携带 `ak.session.grant` 供服务端定位会话与 grant），但出示是否被接受由 sender-constrained proof transcript 而非裸凭据决定；纯 bearer（无 DPoP / `Signature` / mTLS 绑定）在生产 current-v1 受保护 endpoint 上 MUST 被拒绝。

## 3. Events API

### 3.1 提交 Event

```text
POST /_arkret/self/events
```

单事件提交 request body 直接是 `EventSubmitEnvelope` 对象（**不**用任何 `{event: ...}` wrapper）。批量提交 request body 是 `{events: EventSubmitEnvelope[]}`。服务接受后返回的 get/query/subscribe 路径暴露 accepted `EventEnvelope`；submit input 与 accepted/read envelope 不得混用。

单事件请求示例（非完整 schema）：

```json
{
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
  "actor_seq": 42,
  "kind": "ak.strand.update",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0007-a13f9c2e",
  "prev_refs": [
    "ak:event:019640ed-0000-7000-8000-000000000000"
  ],
  "refs": [
    { "id": "ak:grant:0196410c-0000-7000-8000-000000000000", "role": "authorized_by", "critical": true }
  ],
  "causal_refs": [],
  "effects": [
    {
      "cell": "ak:cell:ak.component.strand.metadata.v1:ak:strand:019640c6-8000-7000-8000-000000000000",
      "op": {
        "kind": "set",
        "value": {
          "metadata": {
            "fields": {
              "review_status": "approved"
            }
          }
        }
      }
    }
  ],
  "seal_ref": "ak:seal:sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "auth_context": {
    "did": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
    "key_id": "device-1",
    "key_epoch": 3,
    "capability_refs": ["ak:grant:0196410c-0000-7000-8000-000000000000"]
  },
  "payload": {
    "target_ref": "ak:strand:019640c6-8000-7000-8000-000000000000",
    "patch": { "metadata.fields.review_status": "approved" }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com#device-1",
      "event_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "created_at": "2026-04-22T08:30:00Z",
      "jws": "..."
    }
  ]
}
```

批量请求示例（非完整 schema）：

```json
{
  "events": [
    { "event_id": "ak:event:...", "realm_id": "ak:realm:...", "actor_id": "did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:...", "actor_seq": 42, "kind": "ak.strand.update", "...": "..." },
    { "event_id": "ak:event:...", "realm_id": "ak:realm:...", "actor_id": "did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:...", "actor_seq": 43, "kind": "ak.message.create", "...": "..." }
  ]
}
```

响应示例（非完整 schema）：

```json
{
  "status": "accepted",
  "accepted": ["ak:event:019640ed-8000-7000-8000-000000000000"],
  "actor_frontier": {
    "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
    "actor_seq": 42,
    "event_id": "ak:event:019640ed-8000-7000-8000-000000000000"
  },
  "cursor": "ak:cursor:<opaque-valid-barrier-cursor>"
}
```

若非 reducer 写入的乐观 `expected_frontier` 校验失败，返回 `409 cas_conflict`。DataEvent 的 data-plane guard / Lattice join 失败或 Control Move 的 precondition 失败，按对应 reducer 语义返回 `failed_precondition`、`failed_plane` 或 `failed_bottom`，不得把这类失败旁路成 `cas_conflict`。协议级写入单元是 signed Event Envelope；实现 MAY 在 SDK 或本地接口中接受 operation builder，但在进入网络传播、同步或审计前 MUST 转换为 Event Envelope。接收方不得要求 Event 先归属某个 batch receipt、seal 或 predecessor commit 才承认其 canonical history 地位。

`events[]` 的处理顺序、依赖可见性、frozen authorization basis 与 partial-accept 原子边界统一以 [`operations-sync.md` §5](./operations-sync.md) 为准。本 binding 只定义下列响应 `status` 映射。

**`status` 判别规则（normative）**：响应顶层 `status` 字段 MUST 按下述规则唯一确定，便于客户端不需要逐项扫描即可判断处理结果：

- `status=accepted` **仅当** `rejected[]` 与 `quarantine[]` 均为 empty 且 `accepted[]` 非 empty（至少一项首次接受；可与 `duplicate[]` 中的幂等重复项并存）。
- `status=duplicate` **仅当** 本批所有项均为内容完全相同的幂等重复——全部列入 `duplicate[]` 且 `accepted[]` 为 empty——且 `rejected[]` / `quarantine[]` 均为 empty。
- 调用方重试求差时 MUST 以 `accepted[] ∪ duplicate[]` 为已投递集合（联邦路径同 [`federation.md` §4.1](./federation.md)）。
- 其他所有已通过请求 schema 校验的场景（包括部分成功 + 部分拒绝、部分成功 + 部分隔离、全部拒绝等）一律 `status=partial`，此时响应中 `rejected[]` 与 `quarantine[]` 至少之一 MUST 非 empty，且不得把 `partial` 上报为 `accepted`。空 `events[]` 违反请求 schema 的 `minItems: 1`，MUST 以 `schema_violation` 拒绝且不进入本状态判定。
- 上述规则覆盖 self submit 路径（`ak.self.events.command.submit`，enum `accepted` / `duplicate` / `partial`）。`status=historical_only` **不**在 self 路径出现，仅由 federation peer submit（`ak.peer.events.command.submit`）在 idempotency cache 撤销后重放路径产生，语义见本表 `ak.peer.events.command.submit` 行与 [`federation.md` §8.5.1](./federation.md)；故"其他一律 partial"不含该值。

实现 MUST NOT 把 `status=partial` 简化为 `accepted` 以便利客户端处理；客户端 MUST 在 `partial` 时根据 `rejected[]` / `quarantine[]` 决定是否重试或上报。

### 3.2 批量获取 Event

```text
POST /_arkret/self/events/resolve
```

请求示例（非完整 schema）：

```json
{
  "event_ids": ["ak:event:019640ed-8000-7000-8000-000000000000"],
  "include_payload": true
}
```

响应示例（非完整 schema）：

```json
{
  "events": [],
  "missing": [],
  "unauthorized": []
}
```

### 3.3 查询 / 回填 Event（`ak.self.events.query.scan`）

```text
GET /_arkret/self/events?realms=<id>&before=<cursor>&limit=500          # 历史 backfill（cursor 之前最近的一批历史事件，向更旧方向取一页）
GET /_arkret/self/events?actors=<did>&after=<cursor>&limit=500           # 从已知 frontier 追上（catch-up）
GET /_arkret/self/events?realms=<id>&actors=<did>&after=<Y>&before=<X>   # 区间查询（Y, X）开区间
```

#### 3.3.1 Selector

`realms` / `actors` 都是数组（`realms=A&realms=B`）；同一参数的多个值之间是 union，跨参数（realms × actors）是 intersection。

#### 3.3.2 边界参数 `before` / `after`（v1 wire 形态）

| 参数 | 类型 | 必填 | 语义 |
| --- | --- | --- | --- |
| `before` | `cursor` | optional | 返回此 cursor *之前*（**不含**该 cursor 指向的位置）的最近一批 Event。"之前" = 比此 cursor 更旧的事件方向。 |
| `after` | `cursor` | optional | 返回此 cursor *之后*（**不含**）的最近一批 Event。"之后" = 比此 cursor 更新的事件方向。 |
| `order` | `enum(default, ascending, descending)` | optional | 默认 `default` 按下方"近邻先返回"规则；`ascending` / `descending` 显式强制顺序。 |
| `limit` | `int` | optional | 服务端 enforce 上限（见 [`scalability-constraints.md`](../conformance/scalability-constraints.md)）。 |
| `include_completeness` | `boolean` | optional | 默认 `false`。`true` 时请求服务端在响应中附带覆盖本批次范围的 `ak.attestation.range_completeness` 引用（§3.3.6）。仅在服务端 `supported_features[]` 声明 `events_query_range_completeness` 时有效；未声明的服务 MUST 忽略该参数（不报错、不返回字段）。 |

规则：

- `before` 与 `after` 都是 **排除** 语义 — Arkret cursor 是位置 token 而不是 event 引用，"位置之前/之后"不包含 cursor 标记的边界本身。这与 Stripe `starting_after`/`ending_before`、Relay GraphQL `after`/`before` 等业界惯例一致。
- 两参数都可省略；都不给时服务端按隐式 `before=<server_head>` 处理（即"最新首屏 + 可继续历史 backfill"）。
- 两参数都给即为开区间 `(after, before)` 查询。
- v1 wire 只接受 `before` / `after` / `order`；任何其他游标方向参数 MUST 返回 `invalid_param`。

#### 3.3.3 默认顺序规则："近邻先返回"

`order=default` 时，批次内事件按**距离 seal cursor 的远近**排序，离 seal 最近的事件排第一位：

| 给定参数 | 默认 `order` | 物理意义 |
| --- | --- | --- |
| 仅 `before=X` | **descending**（newest first） | 离 X 最近的 = 比 X 略旧的事件，即"X 之前最近发生的事"。UI 友好。 |
| 仅 `after=Y` | **ascending**（oldest first） | 离 Y 最近的 = 比 Y 略新的事件，即"Y 之后最早发生的事"。reducer / catch-up 友好。 |
| 都给（区间） | **descending** | 区间内 UI-导向默认；想按 causal 顺序应用时显式 `order=ascending`。 |
| 都不给 | **descending** | 等价于 `before=<server_head>`，最新事件首屏。 |

`order=ascending` / `order=descending` 显式覆盖上述默认；批次内的事件顺序在所有情况下都按 `(causal_depth, hlc, actor_id, actor_seq, event_id)` 的字典序解决 ties，详见 [`client-sync.md` §6](./client-sync.md)。

#### 3.3.4 响应

```json
{
  "events": [],
  "prev_cursor": "opaque",
  "next_cursor": "opaque",
  "has_more": true
}
```

响应 cursor 含义在 v1 中是**绝对**的，与请求是 `before` 还是 `after`、`order` 取何值无关：

| 响应字段 | 含义 | 下一次调用 |
| --- | --- | --- |
| `prev_cursor` | 朝**更旧事件**方向的延续位置（位于本批次较旧端之外） | 传给下次请求的 `before=` 取更旧一批 |
| `next_cursor` | 朝**更新事件**方向的延续位置（位于本批次较新端之外） | 传给下次请求的 `after=` 取更新一批 |
| `has_more` | 等价于 `has_more_before`：是否在 `prev_cursor` 指向的**更旧事件**方向上仍有可拉取 Event。客户端到达 oldest accessible event 时 `has_more=false`。`has_more` 不反映 `next_cursor` 方向是否有事件——`next_cursor` 永远有效（朝未来推进），但其指向的事件可能尚未发生。 |  |

边界场景：

- **客户端已经追到最新 head**（`after=` 调用暂时无新事件）：响应 `events=[]`、`prev_cursor` 仍可指向当前可见 head 之前的位置（可继续 `before=prev_cursor` 翻历史）、`next_cursor` 指向未来推进点、`has_more=true` 当更旧方向仍有可读历史时。
- **客户端到达 oldest accessible event**（不允许再往更旧拉）：`prev_cursor=null`、`has_more=false`。
- **超过 visibility 边界**：返回 `not_found` 而不是空批次，避免泄露不可见 Realm 的存在性。

#### 3.3.5 POST/body 形态（`ak.self.events.query.scan_body`）

```text
POST /_arkret/self/events/query
Content-Type: application/json

{
  "realms": ["ak:realm:..."],
  "actors": ["did:webvh:..."],
  "before": "ak:cursor:...",
  "after": "ak:cursor:...",
  "order": "default",
  "limit": 200,
  "filters": { "kind": ["ak.message.create"] }
}
```

POST 形态与 GET 形态**完全等价**：参数集（`realms` / `actors` / `before` / `after` / `order` / `limit` / `filters` / `include_completeness`）、默认顺序规则（§3.3.3）、响应 cursor 绝对方向（§3.3.4）一律相同；只是 wire 形态从 query string 变为 JSON body。

**何时使用 POST**：
- URL 长度风险：`realms[]` 或 `actors[]` 列表较大、`filters` 是嵌套 object 时，URL 容易超过代理 / CDN / 负载均衡器的实际上限（常见 4–8 KiB）
- 隐私 / 日志风险：部署侧的 HTTP access log 通常会完整记录 URL；query string 中的 filter 字段（含可能的敏感 keyword、`actor_id` 列表）会被无差别采集
- 兼容受限客户端：某些 HTTP 中间层会规范化或丢失复杂的 `style: deepObject` 参数

`ak.self.events.query.scan_body` 是 `ak.self.events.query.scan` 的 **HTTP-专属 binding variant**，不是独立语义 operation。gRPC 与 MQ 的 wire 形态本就是 body-based，统一使用 `ak.self.events.query.scan` / `SelfEvents/Query` / `self.events.query.scan` 即可，不需要单独的 `_post` 命名。

**选择规则**：
- 简单查询（仅 `before` / `after` / `limit`，少量 realms/actors）→ `GET /_arkret/self/events`，cacheable、可被代理优化
- 复杂查询（大型 selector / 复杂 filters）→ `POST /_arkret/self/events/query`

**可测试的 GET / POST 边界**：客户端在满足以下任一条件时 **SHOULD** 使用 `ak.self.events.query.scan_body` 而非 GET 形态，而不是依赖主观判断：

- (a) 请求含 `filters` object；
- (b) `realms[]` / `actors[]` 及其它 selector 项合计超过实现声明的 GET selector 上限（默认阈值 8）；
- (c) selector / filter 含敏感主体关系（如可暴露联系人图谱的 `actor_id` 列表或敏感 keyword）。

当部署侧在 `ServiceDescribe` / feature discovery 标记 query-logging 风险（如反向代理会完整记录 query string）时，客户端 **MUST** 使用 POST。GET query 仅适用于无 `filters`、selector 项少且不敏感的简单查询。

上述"GET selector 上限"由 `ServiceDescribe.limits.max_get_query_selectors` 机器声明；缺省值为 8。客户端在 selector 总数（`realms[]` + `actors[]`）超过该值，或 `filters` 包含不应进入 URL / Referer / access log 的敏感条件时，SHOULD 使用 `POST /_arkret/self/events/query`。

服务端 SHOULD 同时实现两个 endpoint；客户端可以按场景自由选择，**不需要协商**。`ak.self.events.query.scan_body` 在注册表（`operation-registry.json`）中通过 `binding_variant_of="ak.self.events.query.scan"` 标记，以保证 SDK 生成器、conformance 测试与 server.query.describe 能机器可读地枚举该 alternate binding，同时授权、审计和指标归并到 `ak.self.events.query.scan`。

**`binding_variant_of` conformance 矩阵规则**：当 operation B 声明 `binding_variant_of=A` 时，B 与 A 共享 selector / cursor / cursor-direction / projection 测试集合，只独立测试 wire encoding（query string vs JSON body）。conformance suite 不需要为 variant 重复跑业务逻辑测试。

#### 3.3.6 Range completeness（optional feature：`events_query_range_completeness`）

cursor + `has_more` 只告诉客户端"拿到了一页"，不告诉客户端"该范围内没有事件被静默扣下"。`prev_refs` DAG 能把**被引用**的缺失依赖暴露为 backfill 目标，但不在已见事件因果过去中的整条 sibling 分支（如被扣下的 ban / 撤销 / moderation 事件）无法被 DAG 发现——这正是 [`operations-sync.md` §6.4](./operations-sync.md) `ak.attestation.range_completeness` 针对的 silent fork 形态。本节把该原语接到客户端读取面。

在 `ServiceDescribe.supported_features[]` 声明 `events_query_range_completeness` 的服务 MUST 支持：

1. **请求**：`include_completeness=true`（GET query 参数或 POST body 字段）。
2. **响应**：附带可选字段 `range_completeness`（见 [`EventsQueryOutcome`](../../artifacts/schemas/service-operation-dtos.schema.json)）：`attestation_refs[]` 是覆盖本批次事件范围的 `ak.attestation.range_completeness` event id 集合；服务端 MAY 经 `attestations[]` 内联这些引用对应的**完整 EventEnvelope**（`kind="ak.attestation.range_completeness"`）。每个内联 Event 的 `event_id` MUST 出现在 `attestation_refs[]` 中；客户端 MUST 先验证 EventEnvelope 签名、`event_digest` 与 `payload.schema="ak.schema.range_completeness_attestation.v1"`，再按 payload 执行 range completeness 验证。服务端 SHOULD 按固定 frontier bucket 预计算 attestation（与 [`federation.md` §4.5.3](./federation.md) 的 probe bucket 对齐），返回覆盖集而不是按页边界现算；over-coverage 合法，客户端按 scope 取交集验证。
3. **无覆盖时**：省略 `range_completeness` 字段。客户端 MUST 把缺失视为"该范围未被 attest"，不得视为错误，也不得视为完整性确认。

客户端验证 MUST 遵循 [`operations-sync.md` §6.4.4](./operations-sync.md) verifier 协议：backfill 完成后客户端持有 scope 全集，适用其第 4 步（重算 Merkle root 并比较，不一致 `range_completeness_root_mismatch`）与第 6 步（`actor_seq_ranges[]` 与本地视图比对，本地有缺口而 attestation 声称完整时 `range_completeness_actor_seq_gap`）；`witness_disagreement` 按其第 7 步 fail closed。`single_source` attestation 只是 issuer 自报（§6.4.3），不构成 sovereign-grade 证明；声明 `security_class=high_assurance` 或 `ak.profile.federation.high_assurance.v1` 的 Realm，客户端 MUST 只接受 `federation_witness_attested` quorum 解除 completeness 关注。

适用范围与边界：

- 只覆盖 reducer-input event；ephemeral、account_data、to-device 不在 scope（to-device 投递安全由 [`client-sync.md` §10.1](./client-sync.md) 显式 ack 承担）。
- E2EE 无障碍：attestation leaf 只含 `(actor_id, actor_seq, event_id, event_digest)`，服务端无需明文。
- 只接 query / backfill / 恢复路径（[`client-sync.md` §12.3](./client-sync.md)），不接 subscribe 实时尾部；attestation 事件本身会作为普通事件随流到达。
- 已声明 `ak.profile.federation.high_assurance.v1` 的部署因联邦面已在生产这些 attestation，SHOULD 同时声明 `events_query_range_completeness` 把它们暴露给客户端。

### 3.4 流式订阅 Event（`ak.self.events.stream.subscribe`）

```text
GET /_arkret/self/events/subscribe?realms=<id>&after=<cursor>&catchup=true
```

`after=<cursor>` 表示订阅起点：从该 cursor *之后*（排除）开始接收事件，与 [`ak.self.events.query.scan`](#33-查询--回填-eventakselfeventsqueryscan) 的 `after=` 同义。Subscribe 天然只有"朝未来推进"一个方向，不接受 `before=` / `order=`；想要历史回填请用 `ak.self.events.query.scan`。

支持多 realm / actor 一次订阅；`catchup=true` 时服务端只回放 `after=` 到当前 frontier 的追赶区间，再发出 `catchup_complete` 帧切到实时尾部。完整历史必须通过 `GET /_arkret/self/events` 的 `before` / `after` 分页或区间查询读取。


HTTP 200 response `Content-Type` MUST be `application/x-ndjson`。Frame 每行一个独立 JSON 对象：

```text
{ "kind": "event", "realm_id": "ak:realm:01...", "cursor": "opaque", "payload": {} }
{ "kind": "catchup_complete", "realm_id": "ak:realm:01...", "cursor": "opaque" }
{ "kind": "frontier", "realm_id": "ak:realm:01...", "cursor": "opaque" }
{ "kind": "heartbeat" }
{ "kind": "epoch_rotation", "realm_id": "ak:realm:01...", "payload": {"new_epoch": 17} }
{ "kind": "dropped", "realm_id": "ak:realm:01...", "cursor": "opaque", "reconnect_after_ms": 5000 }
{ "kind": "unauthorized", "realm_id": "ak:realm:01..." }
{ "kind": "resync_required", "realm_id": "ak:realm:01...", "reconnect_after_ms": 10000 }
```

Frame 字段约束（normative，与 OpenAPI `EventsSubscribeFrame` 的机器约束一致；严格度对齐 [`account-subscribe-frame.schema.json`](../../artifacts/schemas/account-subscribe-frame.schema.json)）：

| `kind` | `realm_id` | `cursor` | `payload` | 语义 |
| --- | --- | --- | --- | --- |
| `event` | REQUIRED | REQUIRED | REQUIRED | selector 范围内的一条 Event；cursor 是该事件之后的续传位置。 |
| `epoch_rotation` | REQUIRED | 禁止 | REQUIRED | Realm-scoped MLS epoch 边界提示帧，不推进 cursor。 |
| `frontier` | optional | REQUIRED | 禁止 | 仅推进 cursor。`realm_id` 存在 = 该 Realm 的 frontier；缺省 = 整个订阅。 |
| `catchup_complete` | optional | REQUIRED | 禁止 | 追赶回放完成。`realm_id` 存在 = 该 Realm 完成；缺省 = 整个订阅完成。 |
| `dropped` | REQUIRED | REQUIRED | 禁止 | Realm-scoped 缺口信号；客户端按 cursor 用 `ak.self.events.query.scan` 补齐该 Realm。MAY 携带 `reconnect_after_ms`。 |
| `resync_required` | optional | 禁止 | 禁止 | `realm_id` 存在 = 仅该 Realm 需要重建本地状态；缺省 = 整个订阅重建。MAY 携带 `reconnect_after_ms`。 |
| `unauthorized` | optional | 禁止 | 禁止 | `realm_id` 存在 = 对该 Realm 失权，该 Realm 从流中移除，其余 Realm 继续；缺省 = 整个 session 失权，客户端 MUST 重新认证。 |
| `heartbeat` | 禁止 | 禁止 | 禁止 | keepalive，不携带任何数据。 |

客户端必须把 `dropped` 与 `resync_required` 当作硬信号——前者要求按 cursor 重新 `ak.self.events.query.scan` 补齐，后者要求重建本地状态。`kind="dropped"` frame 的 `cursor` 为 REQUIRED；服务端没有可用补齐 cursor 时 MUST 发送 `resync_required`，不得发送无 cursor 的 `dropped`。

**流内 frame.kind 与 endpoint error code 的分层（normative）**：上表的 `kind="dropped"` / `kind="resync_required"` 是**已建立流内**的 in-band NDJSON frame.kind 信号。它们各有一个对应的 **endpoint error code**——`stream_dropped` / `stream_resync_required`（[`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)，`scope=endpoint`，HTTP 409）——用于**建流前 / 建流瞬间**在 HTTP 响应层早拒：当客户端提交的 cursor 在订阅建立时点已不可安全续传（例如 cursor 太旧、超出服务端可补齐范围），服务端 MUST 以 `stream_resync_required` 拒绝建流（客户端从新 cursor / snapshot 重新订阅）；若订阅建立过程中已确知发生不可补齐的事件丢弃，MUST 以 `stream_dropped` 早拒。二者与同名 frame.kind 的恢复语义一致（resync = 重建本地状态、dropped = 按 server-directed 路径补齐），区别仅在**发生层**：endpoint code 是 HTTP 响应早拒（流尚未/未能建立），frame.kind 是已建立流的 in-band 信号。客户端 MUST 对两层用同一恢复路径处理。

本端点（与 `ak.self.events.query.scan`）cursor 绑定中的 `filter_digest` 是 **query-scope digest**：覆盖完整 selector（`realms` / `actors`）、`filters` 与 `order`，canonical 计算见 [`client-sync.md` §11.1](./client-sync.md)。在不同 scope 下回传 cursor MUST 返回 `cursor_integrity_invalid`，不得按新 scope 续读。

Dropped / resync-required control frame MAY 携带顶层 `reconnect_after_ms`，表示客户端在打开下一条 `ak.self.events.stream.subscribe` 连接前必须等待的最小毫秒数。cooldown scope MUST 至少按 `(principal_id, device_id, operation_id, filter_digest)` 四元组维度强制执行（与 [`client-sync.md` §2.2](./client-sync.md) 对 `ak.self.account.stream.subscribe` 的 cooldown 维度定义一致；`operation_id` 进入该四元组确保 `ak.self.account.stream.subscribe` 与 `ak.self.events.stream.subscribe` 的 cooldown 互不串扰）。该字段不是错误响应的 `retry_after_ms`，不约束无关 API 调用；服务端一旦发送该字段，MUST 在对应 cooldown scope 内强制执行，过早重连 MUST 返回 `429 rate_limited` 并设置 `Retry-After`，且不得推进 cursor、ack 或其它不可逆订阅状态。客户端 SHOULD 在该延迟上加入 jitter。

## 4. Identity API

```text
POST /_arkret/root/identity/resolve
```

请求示例（非完整 schema）：

```json
{
  "did": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example"
}
```

响应示例（非完整 schema）：

```json
{
  "did_document": {
    "id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "verificationMethod": [],
    "service": []
  },
  "key_log_head": "ak:key_event:019642b0-0000-7000-8000-000000000005",
  "seq": 5
}
```

Resolver MUST 返回下列方法相关证据字段，供客户端验证 control history：`did_document`（normalized view）、`did_document_digest`、`verification_method`、`key_log_head` 或该 DID method 等价的 history head、`seq` / `version_id`、method-specific raw evidence 引用，以及 resolver 自身的 `resolver_service_id`、`resolved_at` 和覆盖上述字段的 `resolver_signature`。不具备可验证历史的 DID method MUST 显式返回 `history_evidence_kind="none"`，客户端按 [`identity-did.md`](../identity/identity-did.md) 的 method policy 决定是否接受。

## 5. Account API

`/_arkret/self/account/*` 承载当前 authenticated principal/device 的账号视角能力：一次性 viewer 自读、Actor Profile 自服务更新、account 聚合 streaming（跨 Realm frontier、to_device、account_data、device_lists、presence、unread / notification counts）、account describe 与 cursor revoke。snapshot manifest 入口独立放在 `/_arkret/self/snapshot/*`。逐 Realm 的事件读取与流式订阅走 `/_arkret/self/events/*`（`ak.self.events.query.scan`、`ak.self.events.stream.subscribe`），见 §3.3 / §3.4。

注册与 session revoke 属认证生命周期，落 `/_arkret/gate/account/*`，与 `ak.gate.account.command.issue_session_grant` 共认证面。Handle 申请、审批、预分配、重签、撤销和管理员分配仍属于 issuer / Auth Server / 部署治理流程；Arkret account self-service endpoint 不得接受裸 `handle` 字段，也不得把未签名 handle 字符串返回为权威身份。实现如需管理面 MUST 使用自己的 negative-space root（例如 `/_<impl>/admin/*`），不得放在 `/_arkret/` 协议命名空间下。组织登记行 CRUD、owner-scoped policy document 存储 CRUD、后台策略编辑 UI 等部署本地管理能力不属于 v1 core operation surface；协议层只规定 signed Organization / Realm policy Event、`ak.self.policy.query.check` 的决策 envelope 以及相关 capability / reducer 语义。

### 5.1 账号 viewer 与 profile 自服务

```text
GET  /_arkret/self/account/viewer
POST /_arkret/self/account/profile
```

`ak.self.account.query.viewer` 返回当前 holder-bound account projection。响应中的 `state` 必须使用 account lifecycle 闭合枚举；`primary_handle_claim` 若存在必须是完整可验证的 `ak.schema.handle_claim.v1`，否则只能返回 `primary_handle_claim_ref` / `handle_claim_digests[]` 供客户端刷新本地 claim cache。viewer 与 `ak.self.account.query.describe` 不同：前者返回主体身份投影，后者返回服务能力。

`ak.self.account.command.update_profile` 的协议 body 是 `AccountUpdateProfileRequestBody {patch}`，其中 `patch` 是 `ak.patch.v1`，允许路径仅 `display_name`、`avatar_blob_ref`、`profile_fields.<key>`。`bio` 不是 Actor Profile 顶层 canonical 字段，必须写入 `profile_fields.bio`；`avatar_url` 不是协议字段，只能在实现层上传 / 解析为 Blob 后写入 `avatar_blob_ref`。`handle`、`status`、`principal_id`、`actor_kind`、`accountable_principal_ids` 与任何 authorization / lifecycle / handle-claim 字段 MUST reject。

`ak.self.account.command.update_profile` 是 holder-bound service wrapper，不是新的 profile 真相源。服务端接受后 MUST 写入或等价产生 `ak.profile.update` / Actor Profile projection。它**不隐式**触发 `ak.find.directory.command.announce` 或 `ak.account_data.set`；需要可发现 profile 或跨设备 UI/avatar 状态同步的客户端 / 服务，MUST 继续显式走对应 Directory / Account Data 路径，直到部署 profile 另行声明更强 fan-out 契约。

### 5.2 账号聚合订阅（`ak.self.account.stream.subscribe`）

```text
GET /_arkret/self/account/subscribe?catchup=true                         # initial account sync baseline
GET /_arkret/self/account/subscribe?after=<cursor>                        # live tail after external reconciliation
GET /_arkret/self/account/subscribe?after=<cursor>&catchup=true           # reconnect / dropped catch-up
```

该端点对应 `ak.self.account.stream.subscribe`。HTTP binding 使用 `Accept: application/x-ndjson` 的 frame stream（服务端按 account / Realm filter 推送 `delta` frame 与 `catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized` 控制 frame）。请求参数、frame schema 与重连规则见 [`client-sync.md`](./client-sync.md) §2。

它与 `ak.self.events.stream.subscribe` 是对称的两类 streaming 订阅(account-aggregate vs per-Realm event log),共享 cursor / `dropped` / `resync_required` 控制模型，但恢复面不同:`self.account.stream.subscribe` 的 `dropped` 用 `GET /_arkret/self/account/subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta;裸 Event 缺口才使用 `ak.self.events.query.scan`。`catchup=true` 不表示全量历史；完整历史读取必须走 `ak.self.events.query.scan`。它不是裸事件读取——裸事件读取请使用 `ak.self.events.query.scan` / `ak.self.events.stream.subscribe`。

Dropped / resync-required control frame MAY 携带 `reconnect_after_ms`。客户端在同一 principal/device/filter scope 重新建立 `/_arkret/self/account/subscribe` 之前 MUST 至少等待该时长；服务端 MUST 对过早重连返回 `429 rate_limited` + `Retry-After`，并且不得推进 account subscribe position 或 dropped recovery state。

客户端回传的 `after=<cursor>` 只决定续传读取位置，MUST 先通过 [`client-sync.md` §12.2](./client-sync.md) 的 cursor 完整性校验（handle 查表 / 绑定匹配）；校验失败 MUST 返回 `cursor_integrity_invalid` 且 MUST NOT 推进任何 server-side state。to-device 队列删除与 cursor 解耦，只由 `ak.self.device_messages.command.ack` 显式确认驱动（[`client-sync.md` §10.1](./client-sync.md)）。

## 6. Snapshot API

`/_arkret/self/snapshot/*` 提供 Realm snapshot manifest 入口；snapshot 是派生的当前态缓存，客户端使用前 MUST 校验签名、签名者授权、`state_digest` 和每个 chunk digest（见 [`service-surface.md` §11](./service-surface.md)）。

### 6.1 当前 snapshot manifest（`ak.self.snapshot.query.manifest_head`）

```text
GET /_arkret/self/snapshot/head?realm_id=<id>
```

该端点对应 `ak.self.snapshot.query.manifest_head`，返回当前推荐的完整 Snapshot manifest（`ak.schema.snapshot.v1`，不含 chunk bytes）；manifest 自带签名 transcript 的全部被签字段与 `chunks[]` 下载描述符。客户端先验证 manifest 签名与签名者授权，再通过 `chunks[].chunk_ref` 走 blob surface 取实际数据。无法产出真实签名 manifest 的部署 MUST NOT 在 `describe.supported_operations` 宣告本操作，对该端点 MUST 返回 `not_implemented`；MUST NOT 用结构合法、语义为假的 `signature` / `authority_binding` / `event_set_commitment` 填充响应。若部署支持并宣告本操作、Realm 对调用方可见、但当前尚无可用 snapshot manifest，则 MUST 返回 `snapshot_unavailable`(503)；Realm 不存在或对调用方不可见时仍返回不可区分的 `not_found`。snapshot 不是真相源，校验失败时客户端 MUST 回退到 Event history replay。

## 7. Directory API

```text
POST /_arkret/find/directory/search-realms
POST /_arkret/find/directory/resolve-realm
POST /_arkret/find/directory/resolve-target
POST /_arkret/find/directory/search-organizations
POST /_arkret/find/directory/resolve-organization
POST /_arkret/find/directory/search-actors
POST /_arkret/find/directory/search-users
POST /_arkret/find/directory/resolve-handle
POST /_arkret/find/directory/resolve-agent-selector
POST /_arkret/find/directory/list-handles-for-subject
```

Directory 端点 MUST 在每个结果上分别应用资源可发现性、请求方证明、审核策略与授权过滤。

对于隐藏或未授权访问的资源，`resolve-*` SHOULD 返回与"不存在"不可区分的 `not_found`。

## 8. Blob API

### 8.1 上传

```text
POST /_arkret/self/blob/upload
```

Content type MUST 取 `multipart/form-data`。请求体 MUST 含唯一的 `content` 二进制 part 与唯一的 `size_bytes` 字段；`content` part 未声明 `Content-Type` 时按 `application/octet-stream` 处理。

响应示例（非完整 schema）：

```json
{
  "blob_ref": "ak:blob:sha256:e3b0...",
  "content_digest": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "size_bytes": 102450,
  "media_type": "image/png"
}
```

### 8.2 下载

```text
HEAD /_arkret/self/blob/get?blob_ref=<blob_ref>
GET /_arkret/self/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。
若哈希不匹配，客户端 MUST 拒绝响应并丢弃内容；服务端在上传、代理或镜像校验时发现不匹配 MUST 返回 `422 digest_mismatch`。

## 9. 标准错误响应

```json
{
  "ok": false,
  "error": {
    "code": "cas_conflict",
    "message": "expected_state_digest mismatch",
    "retry_after_ms": 2000
  }
}
```

## 10. 标准错误码

标准错误码、HTTP 状态码与逐项 reason_code 的 **canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。本节只引用该 registry，不在 Markdown 中维护并行表格；任何新增 / 修改 / 删除错误码 MUST 先更新 registry。

`api-conventions.md` §5.1 是该 registry 的解释性 narrative 视图（解释每个 code 的使用场景）；它本身也以 registry 为准，发现差异时以 registry 为准。

实现使用规则：

- 客户端收到 `429` MUST 优先遵守 `Retry-After` header；若缺失再使用 body 中的 `retry_after_ms`。`503` 在带有 `Retry-After` 时也必须按该时间退避。收到 `409` SHOULD 拉取最新状态后退避重试。
- `unsupported_feature` 用于 `Event.requirements.features[]` / `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `ak.*` Event kind；二者不得互相替代。
- 通用 `conflict` 仅作为抽象 base code 出现在 narrative；实现 SHOULD 返回 registry 中更精确的 409 子 code（`cas_conflict` / `causal_conflict` / `dependency_missing` / `duplicate_conflict` / `epoch_mismatch` / `rank_exhausted` / `stale_frontier` / `state_mismatch` / `discussion_track_disabled` / `key_unavailable` / `audit_receipt_invalidated`；完整集合以 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 为准）。

## 11. 安全与抗滥用

服务端 SHOULD 在高风险入口实施一致性失败语义：

- 对目录/resolve 查询、join 探测、公开元数据接口，未授权请求不应返回可区分 `not_found` 与 `forbidden` 的信息差异。
- 联邦入口与 policy check 入口应记录来源 service DID + 来源域名哈希，结合 `rate_limited` 与 `temporarily_unavailable` 作回压。
- 对来源签名缺失/验证失败的入口请求，应优先走 reject + audit，不得影响已认证正常来源的可用性。
- 对 URL 中携带认证材料的请求，应 reject + redact log，不得进入正常认证 fallback。
