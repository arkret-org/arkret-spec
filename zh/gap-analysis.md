# 与旧 contrix-spec 的差距分析

## 1. 目标

旧 `contrix-spec` 覆盖面很宽：客户端 API、联邦 API、身份服务、推送网关、媒体仓库、事件 schema、加密、设备管理、第三方邀请、VoIP、审核与管理接口都有较细的 endpoint 和 schema。

Contrix New 的方向不同：它不再以 room / message / homeserver 为协议根，而是以 DID、repo、Space、Entity、Relation、Event、View 和 capability 为根。因此本差距分析不要求照搬旧模型，而是回答：

- 哪些旧规范能力在新架构中仍然必须保留
- 哪些能力已经被新抽象覆盖，但还缺线级 schema
- 哪些旧能力应降级为兼容层或应用 profile
- 哪些旧能力应明确不继承

## 2. 当前已覆盖的能力

当前新规范已经覆盖或替代了以下旧规范主题：

| 旧规范主题 | 新规范位置 | 当前状态 |
| --- | --- | --- |
| DID / Handle / 服务发现 | `identity-did.md`, `identity-handles.md`, `service-surface.md` | 已覆盖，需要正式 schema 和测试向量 |
| 房间 / 空间 | `object-model-core.md`, `object-model-standard.md` | 已替换为 Space / Entity / Relation |
| 消息 / 话题 / 线程 | `conversation-model.md`, `content-types.md` | 已覆盖主要语义 |
| 事件替换 / 撤回 / reaction | `conversation-model.md`, `operations-sync.md` | 已覆盖，需要更多标准 event type |
| 同步 / backfill / snapshot | `operations-sync.md`, `service-surface.md` | 已覆盖原则和最小接口 |
| 权限 / power levels | `capabilities.md` | 已替换为 capability / policy |
| E2EE | `encryption-and-audit.md` | 已选择 MLS，需要落 KeyPackage / envelope schema |
| 推送 | `push-notifications.md` | 已覆盖隐私保护推送模型 |
| 已读 / 未读 | `read-receipts.md` | 已覆盖 |
| profile / presence / typing | `profiles-presence.md` | 已覆盖 |
| 3PID 邀请 | `third-party-invites.md` | 已覆盖草案 |
| VoIP | `webrtc-signaling.md` | 已覆盖信令草案 |
| applet / bot / integration | `applet-integration.md`, `agent-memory.md` | 已定义 Applet registration / namespace / transaction 草案，仍需正式 schema |

## 3. 明显缺口

### 3.0 Matrix / MSC 对比后的 P0 缺口

进一步对比 `E:\Works\palpo-im\matrix-spec` 与 `E:\Works\palpo-im\matrix-spec-proposals` 后，确认旧 Contrix 差距之外还存在五个直接影响稳定落地的 P0/P1 缺口：

- Space version / event authorization / state resolution：Matrix room version 将事件格式、授权规则、状态解析、redaction 与升级绑定在一起。Contrix 已新增 `event-auth-state-resolution.md`，用 `cx.space.v1` 固定 Space 版本、auth refs、membership、状态冲突归约和 soft fail 语义。
- Device crypto / cross-signing / to-device：Matrix 的 cross-signing、device list、to-device、secret storage、key backup 是 E2EE 多端的必要协议面。Contrix 已新增 `device-crypto-verification.md`，定义设备身份、验证、密钥备份和 Applet delegated device。
- Client sync v2：repo 复制不能替代客户端增量同步。Contrix 已新增 `sync-v2.md`，定义 timeline、state_after、account_data、to_device、device_lists、ephemeral 与 E2EE 同步要求。
- Policy server：治理策略必须可签名、可缓存、可审计，但不能替代 capability 授权。Contrix 已新增 `policy-server.md`。
- Account lifecycle：DID principal、服务账户、device session、repo data 和 Space membership 的生命周期必须拆分。Contrix 已新增 `account-lifecycle.md`。

### 3.1 线级 API 与 OpenAPI schema

旧规范有大量 `data/api/**/*.yaml`，每个 endpoint 都有 request / response / error schema。当前新规范只有文档级接口草案。

需要补：

- repo / relay / index / blob / identity / authz 的正式 OpenAPI 或等价 JSON Schema
- 标准 request / response envelope
- cursor、pagination、filter、sort 的统一语法
- 标准错误码、重试语义、幂等键和 rate limit header
- CORS / browser client 行为

优先级：**P0**。没有这层，无法做互操作测试。

### 3.2 事件与对象 schema 注册表

旧规范有 `data/event-schemas/schema/*.yaml`。当前新规范定义了对象模型，但还缺标准事件/对象 schema 注册表。

需要补：

- `cx.space.*`
- `cx.entity.*`
- `cx.relation.*`
- `cx.message.*`
- `cx.task.*`
- `cx.view.*`
- `cx.capability.*`
- `cx.mls.*`
- `cx.audit.*`
- `cx.notification.*`
- `cx.receipt.*`

优先级：**P0**。这决定 reducer 和索引器能否一致实现。

### 3.3 编码与 canonicalization

旧规范有 server signature、event hash、transaction id 等规则。当前新规范还缺统一编码细则。

需要补：

- canonical JSON 编码规则
- hash input 与 hash id 格式
- `op_id`、`commit_id`、`entity_id`、`relation_id`、`space_id` 生成规则
- HLC、cursor、rank、pagination token 编码
- detached JWS / COSE / multibase 选择
- signature verification profile

优先级：**P0**。否则不同实现会签出不同 hash。

### 3.4 设备、密钥与跨设备消息

旧规范有 device management、cross-signing、to-device、secret sharing、key backup。当前新规范已有 `devices-and-auth.md`，但缺可实现的密钥生命周期规则。

需要补：

- device identity schema
- device authorization / revocation event
- device-scoped access token 或 session grant
- device-to-device ephemeral channel
- secret backup / restore envelope
- MLS KeyPackage publication 和 rotation
- lost device response

优先级：**P0/P1**。E2EE 和多端体验都依赖它。

### 3.5 内容仓库与媒体处理

旧规范的 content repo 包含 upload / download / thumbnail / authenticated media / metadata。当前 `service-surface.md` 只有 blob 基础接口。

需要补：

- blob metadata schema
- MIME sniffing 与禁止规则
- thumbnail / preview 派生物
- authenticated download
- retention / GC / legal hold
- encrypted attachment envelope
- virus scanning 与 unsafe media 标记

优先级：**P1**。

### 3.6 搜索、目录与发现

旧规范有 user directory、public room directory、search、room previews。新规范只有 index/search 草案。

需要补：

- Space directory
- Actor directory
- visibility / discoverability policy
- encrypted Space 的本地搜索与服务器搜索边界
- search result authorization filtering
- preview / summary 的最小披露规则

优先级：**P1**。

### 3.7 联邦协议细节

旧规范有 federation transaction、server key、event auth、join/invite/knock/backfill。新规范已有 `federation.md`，但还缺完整线级联邦协议。

需要补：

- server / service DID authentication
- inter-service transaction envelope
- relay-to-relay op exchange
- cross-domain Space join
- backfill authorization
- remote capability verification
- fork / equivocation detection
- abuse handling and quarantine

优先级：**P1**。

### 3.8 管理、审核与滥用治理

旧规范有 report content、moderation policy list、server ACL、admin。新规范已有 `moderation.md`，但仍缺可执行流程。

需要补：

- report object schema
- moderation queue schema
- policy list subscription
- block / mute / hide / quarantine semantics
- server-level ACL equivalent for service operators
- appeal / audit trail
- spam scoring 和 reputation 输入边界

优先级：**P1**。

### 3.9 通知、回执与账户私有状态

旧规范有 push rules、receipt、read marker、account data、recent emoji、tags。新规范已有拆分文档，但还缺正式私有状态存储模型。

需要补：

- private repo / private state namespace
- account data event type
- per-user tags / labels
- notification rules DSL
- read receipt privacy profile
- multi-device unread merge

优先级：**P1**。

### 3.10 互操作与 conformance profile

旧规范有 feature profile 表。当前新规范缺“最低可实现集”定义。

需要补：

- minimal repo node
- relay node
- index node
- full client
- E2EE client
- enterprise client
- agent runtime
- conformance test vector

优先级：**P0**。否则“实现了 Contrix”没有可验证含义。

### 3.11 Applet / Bridge 线级 schema

旧规范有 appservice 风格的 registration、transaction、query user、query room、third-party protocols。新规范已经采用 Applet 模型，但仍需把草案固化成 schema。

需要补：

- `applet_registration` JSON Schema
- namespace pattern grammar
- `/api/v1/applet/transactions/{txn_id}` OpenAPI
- query actor / query space OpenAPI
- protocol metadata schema
- third-party user / location lookup schema
- ghost actor / portal Space schema
- bridge error event schema

优先级：**P1**。这决定 Contrix 是否能可靠桥接 Slack、Discord、GitHub、Linear、邮件等系统。

## 4. 不建议继承的旧设计

以下旧设计不应直接搬入新规范：

- room 是唯一状态容器
- power level 是主要权限模型
- homeserver 是用户唯一权威入口
- event type 主要围绕 chat message 设计
- presence / typing 默认广泛广播
- 明文服务器索引默认可见
- 以用户 ID / handle 作为权限主键

这些能力可以以新模型重建，但不应保留原抽象作为协议根。

## 5. 建议补文档顺序

1. `api-conventions.md`：统一 HTTP、错误、幂等、分页、CORS、rate limit。
2. `conformance-profiles.md`：定义最小实现集和测试范围。
3. `schema-registry.md`：标准对象、事件与操作 schema 注册表。
4. `encoding.md`：canonical JSON、hash、id、signature、cursor。
5. `key-management.md`：设备密钥、恢复、备份、MLS KeyPackage。
6. `media-and-blob.md`：内容仓库、缩略图、附件加密。
7. `directory-search.md`：目录、搜索、preview、可见性。
8. `federation-wire.md`：联邦交易、跨域加入、backfill。
9. `applet-schema.md`：Applet registration、namespace、transaction、protocol metadata 的正式 schema。

## 6. 当前结论

当前新规范在架构方向上比旧规范更统一，但在“可实现细节”上仍少了很多。最关键的缺口不是再写更多概念，而是把以下内容落成可测试工件：

- schema
- endpoint
- encoding
- proof / signature profile
- conformance suite
- feature profile

这些内容补齐后，Contrix New 才能从“设计草案”进入“可互操作协议”阶段。
