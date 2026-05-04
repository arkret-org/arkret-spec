# Service Surface And Bootstrap

## 1. 目标

如果只有对象模型、同步原则和 capability，而没有最小线级服务面，协议仍然很难真正互操作。

因此 Contrix v1 定义：

- identity registry 如何收发 DID 操作与 receipt
- Events API 如何提交、读取、回填 signed Event
- Principal Server 如何提供 space sync stream 与 backfill
- search / View projection 的语义边界如何在客户端或显式受托服务中保持一致
- directory 如何做 Space / Organization / Actor 的授权搜索与精确解析
- blob 如何上传与校验
- invite / grant 如何参与首次加入工作区

本文给出 **最小可互操作服务面**。
默认调用风格采用 HTTP/JSON binding，但协议核心不强绑定 REST API。实现也可以支持 gRPC、GraphQL、WebSocket、SSE、message queue、libp2p 或本地 IPC，只要提供语义等价的操作、认证、授权、幂等、分页、错误和流控语义即可。详细规则见 `transport-bindings.md`。

本文件按服务角色说明接口语义。所有 REST endpoint 的字段级请求 / 响应 schema、认证模式、访问限制和幂等规则以 [service-http-binding.md](service-http-binding.md#24-字段级-schema-索引) 为准；本文件中的 JSON 或字段列表仅用于解释服务面，不构成完整 schema。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

DID Document SHOULD 只负责：

- 声明 principal server、identity registry、events、sync service、blob、capability 服务入口
- 声明服务 DID 或服务 endpoint

它不应直接塞入：

- 当前 grant 全量状态
- 当前 space 当前态
- 大量通知或 inbox 数据

### 2.2 没有任何单一服务是唯一真相源

- signed Event 是 actor 发布和协作事实真相源
- sync service 是 Principal Server 上的受控同步入口
- search、inbox、notification 和 View projection 是派生体验，可以由客户端本地计算，也可以由显式受托服务计算
- blob 是内容层

客户端应能在这些层之间交叉验证 frontier、hash 与 reducer profile。

### 2.3 接口必须天然支持幂等重试

网络重试、离线回放、多 Principal Server 同步在去中心化系统中是常态。

因此写接口 MUST 支持：

- `event_id` 幂等
- `Idempotency-Key` 或客户端事务 ID 幂等
- 重复提交不重复生效

### 2.4 服务必须公布自己的实现 profile

每个服务 SHOULD 能公开：

- `protocol_version`
- `supported_features`
- `supported_reducer_profiles`
- `supported_schema_profiles`

否则客户端无法判断自己能否安全使用该服务。

### 2.5 实际服务器与服务面组合

实际部署中的“服务器”是一个或多个服务面的组合，不是协议真相源。实现可以合并服务器，但必须在 `server/describe` 中明确 `service_type`、`supported_operations`、认证方式、限制和 profile。

协议层统一使用 **Principal Server** 表示 principal 控制或委托的受控入口。不同部署形态的差异由 deployment profile、支持的 operation、是否内置 Auth / Account、Policy、Events API、Blob、Identity Resolution 等能力表达。

常见组合如下。这里的“需要”表示协议交互需要该能力存在，不表示每个用户都必须自建；个人和小团队通常只自建一个 Principal Server，其余基础设施可使用公共或托管服务。

| 实际服务器 | 普通部署建议 | 通常暴露的 REST namespace | 主要能力 |
| --- | --- | --- | --- |
| Principal Server | 普通用户或组织自建的核心入口 | `/server`, `/events`, `/sync`, `/federation`, 可代理 `/blob`, `/authz`, `/device_messages`, `/keys` | 用户/组织的受控入口、Event 提交/读取、client sync、联邦 transaction、服务发现聚合、明文可见边界执行。 |
| Identity Resolution Infrastructure | 普通用户默认使用公共服务或本地 method resolver；高安全或隔离网络才自建完整基础设施 | `/identity`, `/server` 或 method-specific resolver | DID document、DID / KERI log、handle binding、receipt、witness、watcher、OOBI、service endpoint discovery。 |
| Auth / Account Server | 个人部署可内置；组织通常独立或接入 SSO | 通过 `auth_metadata` 暴露，具体登录路径 MAY 由部署定义 | 登录、passkey/OIDC/SSO、session grant、device pairing、账户恢复；不得直接替代 DID 控制权。 |
| Sync / Federation Server | 普通用户通常内置在 Principal Server | `/sync`, `/federation`, `/server` | client sync、subscription、backfill、snapshot head、跨域 transaction、重放和 destination 绑定校验。 |
| Directory Server | 普通用户默认使用公共目录；组织发现或隔离网络才自建 | `/directory`, `/server` | Space/Organization/Actor/handle/Applet 的授权搜索和解析，私密联系人发现，最小披露发现。 |
| Blob / Media Server | 个人通常内置；文件量大或高安全组织可独立 | `/blob`, `/server` | blob upload、authenticated download、HEAD、Range、thumbnail、preview、retention、media safety。 |
| Device / Key Server | E2EE profile 需要；个人通常内置在 Principal Server | `/device_messages`, `/keys`, `/keys/keypackages`, `/keys/backups`, `/server` | to-device message、one-time key、fallback key、MLS KeyPackage claim、device list、encrypted key backup metadata / ciphertext。 |
| Authz / Policy Server | 个人可内置；共享 Space 和组织治理建议独立 | `/authz`, `/contrix/v1/check`, `/server` | effective grants、invite 查询、capability precheck、签名 policy decision、risk / quarantine。 |
| Push Gateway | 普通用户默认使用公共或托管推送；内网或高安全组织可自建 | `/push`, `/server` | push device register/unregister、脱敏通知投递、APNs/FCM/厂商推送适配。 |
| Applet Server | 集成/桥接/自动化可选 | `/applet`, `/server` | applet describe、transaction、ghost actor、portal Space、third-party lookup。 |
| MIMI Provider Facade | 与外部 MIMI provider 互通时可选；可由 Principal Server、Space Host 或 Applet Bridge 承载 | `/mimi`, `/.well-known/mimi-protocol-directory`, `/server` | MIMI provider discovery、room binding、key material、submit message、groupInfo、consent、identifier query、abuse report、proxy download。 |
| Agent Runtime Server | agent 场景可选但推荐 | `extensions/agent-*` 定义的 service surface，通常通过 `/events` 写回结果 | agent 执行、tool 调用、A2A/ACP/MCP handoff。 |
| Realtime Media Server | 通话/会议可选 | `/contrix/v1/ice-config`，以及 WebRTC signaling / TURN / SFU profile | ICE config、TURN/STUN、SFU/MCU、录制策略、短期媒体凭证。 |
| Moderation / Compliance Server | 公共或组织部署建议独立 | `/moderation`, `/server` | report、审核队列、server ACL、policy list、appeal、legal hold / erasure workflow。 |

推荐 deployment profile：

- `principal_server_personal`：一个 Principal Server；内部合并 Events API + Sync/Federation + Blob + Device/Key + Authz；客户端可自行维护本地 search / projection；Identity Resolver、Directory、Push 和 TURN/Media 默认可用公共服务。
- `principal_server_organization`：一个组织委托的 Principal Server；通常搭配 Auth / Account Server；需要统一授权和审计时增加 Policy Server；Blob、Directory、Push 可按规模和合规要求拆分。
- `principal_server_secure_organization`：一个或多个组织委托的 Principal Server，搭配 Auth / Account Server、Identity Resolution Infrastructure、Policy/Authz、Blob/Media；公共 Directory、Push 或外部 federation ingress 只作为可选互联入口。
- `isolated_enclave`：Principal + Identity Resolution Infrastructure + Auth + Directory + Policy/Authz + Events/Blob + Sync/Federation + Audit/Compliance 全部在信任域内部署。
- `public_federation_ingress`：Principal/Federation + Policy + Moderation + Directory 的受限组合，不默认可见明文。
- `applet_service`：Applet Server + Event writer + Authz precheck，只在授权 namespace 和 capability 内工作。
- `mimi_provider_facade`：MIMI facade + Device/Key + Federation/Authz integration，只投影被 `cx.mimi.room_binding` 授权的 Space / Flow discussion branch。
- `agent_runtime`：Agent Runtime + Event writer，所有写入仍通过 principal / agent DID 签名。

客户端选择服务时 MUST 先解析 DID Document 与 Space policy，再校验 `server/describe`。不得因为多个服务位于同一域名，就默认它们拥有相同权限或相同明文可见范围。

## 3. 通用服务描述接口

所有网络可发现服务 MUST 提供：

```text
GET /api/v1/server/describe
```

示例：

```json
{
  "service_did": "did:web:alice.example.net",
  "service_type": "principal_server",
  "protocol_version": "1.0",
  "supported_features": [
    "sync_stream",
    "snapshot",
    "notifications"
  ],
  "supported_reducer_profiles": [
    "cx.reducer.v1"
  ],
  "supported_schema_profiles": [
    "cx.schema.v1"
  ],
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "supported_auth_methods": ["passkey", "oidc", "device_pairing"],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  },
  "max_body_bytes": 1048576,
  "limits": {
    "max_body_bytes": 1048576,
    "max_events_per_batch": 100,
    "device_message_max_ttl_seconds": 86400,
    "read_marker_debounce_ms": 1000,
    "dangling_redaction_min_retention_days": 30,
    "snapshot_retention_heads": 2
  },
  "rate_limit_policy": {
    "policy_version": "2026-05-02",
    "entries": [
      {
        "operation_id": "cx.federation.push_operations",
        "scope": ["service_did", "space_id"],
        "window_seconds": 60,
        "max_requests": 120,
        "burst": 20
      }
    ]
  }
}
```

服务类型命名规则：

- DID Document `service.type` 使用协议注册名，例如 `ContrixPrincipalServer`、`ContrixDirectory`。
- describe 响应的 `service_type` 使用小写注册值，例如 `principal_server`、`sync_node`、`identity_registry`、`auth_server`、`blob_node`、`directory_service`、`device_key_service`、`authz_service`、`policy_server`、`push_gateway`、`applet_service`、`mimi_provider_facade`、`agent_runtime`、`media_service`、`sfu_service`、`turn_service`、`moderation_service`。
- conformance profile 使用 `cx.profile.*` 标识，例如 `cx.profile.principal_server.v1`。
- 实现 MUST 区分这三层名称，不得把 DID service type、运行时 service_type 与 conformance profile 混用。

### 3.1 Identity Resolution Surface

Identity Resolution Surface 是 DID method resolver、registry、witness、watcher 或 method-specific verifier 的统一抽象。`did:plc` 可以由 PLC directory、mirror 或 audit source 实现；`did:web` 可以由 HTTPS / DNS resolver 实现；`did:webvh` 可以由 DID log、watcher 和 witness 实现；`did:key` 可以只由本地 resolver 实现，不需要网络 API；`did:keri` 可以由 KERI log、witness、watcher 和 OOBI discovery 实现。

网络型 identity registry 至少应提供以下语义：

#### 3.1.1 描述 registry

```text
GET /api/v1/identity/describe
```

返回：

- `service_did`
- `registry_mode = writer | witness | replica`
- 支持的 receipt 类型
- 当前软件版本与实现 profile

#### 3.1.2 获取当前 DID Document

```text
GET /api/v1/identity/document?did=<did>
```

返回 SHOULD 包含：

- 当前 materialized DID Document
- 当前 `head_event_hash`
- 当前 `seq`
- 可选 witness receipts

#### 3.1.3 获取 DID 日志

```text
GET /api/v1/identity/log?did=<did>&cursor=<cursor>&limit=<n>
```

用于：

- 审计
- 重建 DID Document
- 验证 `key_log` 与 registry head 一致

#### 3.1.4 提交 DID 更新

```text
POST /api/v1/identity/submit-did-operation
```

请求体 SHOULD 包含：

- `did`
- `seq`
- `prev_event_hash`
- `patch`
- `proofs`

要求：

- 相同 `did + seq` + 相同内容的重复提交 MUST 幂等成功
- 相同 `did + seq` 但内容不同 MUST 拒绝
- registry MUST 验证从 `inception_key` 出发的授权链

#### 3.1.5 获取 receipt / witness 证明

```text
GET /api/v1/identity/receipts?did=<did>&head=<event-hash>
```

#### 3.1.6 写入确认建议

Contrix v1 要求：

- writer 客户端同时向多个 registry / witness 提交 `did_operation`
- 至少拿到 `k-of-n` receipt 才视为提交成功
- 读取时可附带 `expected_head` 或 `min_seq`

这让 DID 写入仍然是普通网络请求，而不是全网区块共识。

## 4. Events API

Events API 是 Principal Server 提供的 signed Event 提交、读取、回填和前沿查询接口。普通部署 SHOULD 由 Principal Server 直接暴露 `/events/*`。

Contrix v1 不要求实现 atprotocol/Git 式数据仓库、提交日志或仓库命名接口。Principal Server 可以托管、复制或索引 Event，但接收方仍必须验证 Event 签名、DID 控制链、canonical hash、`actor_seq` 路径递增、`prev_refs` / `auth_refs` 因果依赖和 `event_id` 幂等性。

Events API 至少应提供以下语义：

### 4.1 描述 Events API

```text
GET /api/v1/events/describe
```

返回：

- `service_did`
- 支持的签名算法
- 支持的 Event schema / reducer profile
- 支持的 actor frontier、Space frontier、batch-get 和 stream/backfill 能力

### 4.2 提交 Event

```text
POST /api/v1/events
```

请求体是一个 Event Envelope，或 profile 明确允许的 Event Envelope 数组。

要求：

- 同一个 `event_id` 重复提交相同 canonical bytes MUST 幂等成功。
- 同一个 `event_id` 若内容不同 MUST 拒绝并记录冲突。
- 服务 MUST 验证 Event 签名、actor DID、device/session、capability、Space policy、`actor_seq` 和因果依赖。
- 服务 SHOULD 返回 accepted event、当前 actor frontier、Space frontier 以及 read-your-writes `sync_token`。

当请求体包含 `events[]` 时，服务 MUST 按数组顺序逐项处理。前一项已接受的 Event 可以满足后一项的 `prev_refs` / `auth_refs` / payload-level causal reference；同批中尚未处理、已拒绝或进入 quarantine 的 Event 不能作为已解析依赖。批处理中单项失败不得回滚已接受项：成功项进入 `accepted[]`，重复幂等项进入 `duplicate[]`，失败项进入 `rejected[]` 或 `quarantine[]`。若后续 Event 依赖同批失败或缺失 Event，服务 MUST 以 `dependency_missing`、`causal_conflict`、`soft_fail` 或等价原因拒绝/隔离该后续 Event，而不是隐式接受。

### 4.3 获取单个 Event

```text
GET /api/v1/events/{event_id}
```

不可见或不存在的 Event MUST 使用统一 `not_found` 语义，除非调用方有审计/管理权限。

### 4.4 批量获取 Event

```text
POST /api/v1/events/batch-get
```

请求体可携带一组 `event_ids` 或 `event_hashes`。响应按 Space policy、history visibility、E2EE envelope policy 和 redaction policy 过滤 payload。

### 4.5 列出 / 回填 Event

```text
GET /api/v1/events?actor_id=<did>&space_id=<id>&cursor=<cursor>&limit=<n>
```

用于：

- actor 历史恢复
- Space 审计回放
- 补齐缺失 Event
- 从 snapshot frontier 后继续 reducer replay

### 4.6 获取 Event frontier

```text
GET /api/v1/events/frontier?actor_id=<did>
GET /api/v1/events/frontier?space_id=<id>
```

返回调用方可见范围内的 actor frontier、Space frontier、latest HLC、可选 witness receipt / event batch receipt。frontier 只用于同步和强一致读取，不能替代 Event 集合本身。

## 5. Sync Surface

Sync Surface 是 Principal Server 提供的 Space 增量同步能力。它不是独立第三方服务器角色。客户端只应使用本 principal 控制/委托的 Principal Server、对方 principal 控制/委托的 Principal Server，或 Space policy 明确列出的 shared Space Host。

本节定义三个不同操作：

- `POST /api/v1/sync`：客户端聚合增量同步，见 `client-sync.md`。
- `GET /api/v1/sync/subscribe`：Space Event 增量流订阅。
- `GET /api/v1/sync/backfill`：按 cursor 回补历史 Event。

实现不得把这三个操作合并成语义不明的单一“stream”接口。其他 transport MAY 使用不同帧名，但必须映射到上述 canonical operation。

### 5.1 描述 sync service

```text
GET /api/v1/sync/describe
```

### 5.2 Space sync stream 订阅

```text
GET /api/v1/sync/subscribe?space_id=<id>&cursor=<cursor>
```

实现可用：

- SSE
- WebSocket
- 长轮询

但必须提供稳定 cursor 语义。

### 5.3 增量回补

```text
GET /api/v1/sync/backfill?space_id=<id>&cursor=<cursor>&limit=<n>
```

### 5.4 snapshot 入口

```text
GET /api/v1/sync/snapshot-head?space_id=<id>
```

用于拿到当前推荐 snapshot manifest。

### 5.5 明文与服务信任

如果 Space 未启用 E2EE 或内容层加密：

- 客户端 MUST NOT 将 message body、comment body、附件明文或可逆派生摘要提交给未授权第三方服务。
- `events`、`sync`、`sync/subscribe`、`sync/backfill` 的服务端必须是 principal DID、Organization DID 或 Space policy 明确委托的 Principal Server。
- Directory、Push Gateway、Blob preview、Policy preview，以及任何协议外 search / projection 服务，若会接收正文、正文摘要、附件预览、全文索引或可逆派生内容，MUST 在 Space policy 中声明为 `plaintext_visible_services`。
- shared Space Host 若可见明文，必须在 Space policy 中作为明文可见方列出。
- 接收方 Principal Server 可以看到投递给该接收方的非加密内容；客户端和 Space policy MUST 把这视为内容可见边界，而不是透明中继。
- 非受信服务只能接收公开内容、密文 envelope 或不可解析 payload。

## 6. Search / Projection Semantics

Contrix v1 不定义必需的远端索引或应用视图服务面。当前态查询、View projection、inbox、notification 和全文搜索默认属于客户端或 SDK 的本地派生能力；客户端可以根据已同步且已授权、已解密的 Event 集合自行维护本地索引，也可以完全不提供搜索功能。

实现 MAY 提供协议外或扩展 profile 的受托 search / projection 服务，但该服务不是核心协议角色。任何此类服务都不得成为真相源；其输出必须能追溯到 signed Event、reducer profile、View definition 和 causal frontier。

### 6.1 结构化查询形状

若客户端、SDK 或可选受托服务对外暴露可互操作查询语义，SHOULD 复用 `query-schema.md` 中的 Query 形状：

- `object_types`：标准对象类型，例如 `space`、`flow`、`message`、`morph`（Space(kind=board/list) 通过 `space.kind` 标识；Flow 默认入口通过 branch primary 解析规则得到）
- `morph_types`：当 `object_types` 包含 `morph` 时，可进一步限定开放对象类型
- `facets`：schema-declared capability hint 选择器，只用于 Morph 或声明支持 facets 的标准对象；不得作为授权、状态机、排序或 reducer 语义的唯一来源
- `relation`
- 过滤条件
- 排序
- cursor
- limit
- `view_id`、`projection` 与 `renderer`：非 raw projection SHOULD 使用核心原语 `collection` / `timeline` / `graph` / `document` / `composite`；例如看板展示使用 `projection="collection", renderer="board"`。
- `sync_token`：可选。若实现支持读己之所写等待，则必须把等待条件绑定到本地已知的因果前沿，例如特定 `event_id` / event hash / Space frontier。

`sync_token` 在 Query / Projection 语义中是读己之所写 barrier，不是 Client Sync 的 `next_batch` / `since` resume token。实现 MAY 把它编码为 opaque token，但内部 MUST 绑定调用方、`space_id`、目标 `event_id`、event hash、filter / query hash、服务 DID 和过期时间。Projection 服务收到该 token 时，应等待本地可验证 frontier 覆盖目标事件；若等待超时返回 `timeout`，若服务本地 frontier 明确落后返回 `stale_frontier`，若服务暂时无法追赶或不可用返回 `temporarily_unavailable`。Client Sync 仍必须只使用 `client-sync.md` 定义的 `next_batch` 作为 `since`。

### 6.2 Flow Discussion / Context Projection

Flow context timeline、Flow discussion timeline 和 Flow context projection 是客户端展示形态，不要求远端 endpoint。无论在客户端本地还是受托服务中执行，Flow `discussion` branch 都必须按有效 access policy 执行 membership / history visibility 检查：默认可继承 Flow / Space，显式 branch-scoped override 则按该 override 独立裁剪。不得因为 Flow synthesis 可见就展开未授权的 discussion 内容，也不得因为 discussion 可见就授予 Flow synthesis、Board/List 或其他 Space 对象权限。

### 6.3 Inbox / Notification Projection

Inbox 和 notification 可以由客户端从本地 Event、read marker、mention Relation、assignment Relation 和 actor-private account data 派生。若受托服务生成 inbox preview、通知摘要或可逆派生内容，必须满足本节明文边界。

### 6.4 全文搜索

全文搜索是可选功能。请求形状 MAY 使用：

```json
{
  "query": "legal review",
  "space_ids": ["cx:space:01js0sp0000000000000000000"],
  "object_types": ["message", "flow", "morph"],
  "morph_types": ["comment"],
  "sender": "did:web:alice.example.com",
  "time_range": {
    "after": "2026-04-01T00:00:00Z",
    "before": "2026-04-26T00:00:00Z"
  },
  "order_by": "relevance",
  "cursor": null,
  "limit": 20
}
```

响应形状 MAY 使用：

```json
{
  "results": [
    {
      "rank": 0.95,
      "object": { /* Object 当前态 */ },
      "highlights": [
        { "field": "content.body", "snippet": "Please complete the <em>legal review</em> by Friday." }
      ]
    }
  ],
  "next_cursor": "search_cursor_abc",
  "total_estimate": 42
}
```

**E2EE 场景说明**：在加密 Space 中，远端服务无法对密文执行全文搜索。默认搜索发生在客户端本地：客户端同步 Event、解密可见内容，并自行维护本地全文索引。受控网络中的 TEE 或组织搜索服务属于可选扩展，不是核心协议能力。

### 6.5 明文搜索边界

Search / projection 派生结果可能比 Sync Surface 更容易查询，也可能包含正文摘要、命中片段、embedding 或通知摘要。因此：

- 非 E2EE 私有 Space 的全文搜索、embedding、通知摘要、inbox preview 和报表投影只能由 `plaintext_visible_services` 中列出的服务生成或保存。
- 未列入 `plaintext_visible_services` 的受托 search / projection 服务 MUST 只接收公开内容、密文 envelope、不可逆 hash、最小 routing metadata 或 policy 明确允许的 stripped preview。
- 客户端在选择受托 search / projection 服务前 MUST 校验 service DID、supported profile、Space policy 委托和 plaintext-visible 声明。
- Search / projection 输出不得扩大可见性；查询结果、通知、搜索命中和 preview 都必须受底层 Space policy 与 capability 约束。

服务端强制边界：

- Events / Sync / Federation / Push / Blob preview，以及任何受托 search / projection 服务在接收包含明文或可逆派生摘要的请求时，MUST 检查自身 service DID 是否在当前 Space policy 的 `plaintext_visible_services` 中，且 visibility 等级覆盖该内容类型。
- 未授权服务 MUST 拒绝明文请求并返回 `capability_denied` 或 `schema_violation`，不得静默索引、转发、缓存或降级保存。
- 恶意客户端把明文发送到协议外服务不属于协议可强制阻止的范围；但任何声称支持 Contrix profile 的服务若接收或处理未授权明文，均视为 profile violation。

## 7. Blob Surface

blob 服务至少应提供：

### 7.1 上传 blob

```text
POST /api/v1/blob/upload
```

返回：

- `blob_ref`
- `sha256`
- `size`

### 7.2 查询 blob 头信息

```text
HEAD /api/v1/blob/get?blob_ref=<ref>
```

### 7.3 下载 blob

```text
GET /api/v1/blob/get?blob_ref=<ref>
```

blob 校验 MUST 基于内容哈希，而不是单一 URL。

## 8. Directory Surface

directory 是授权过滤后的发现与搜索服务面。它是派生索引，不是真相源。

### 8.1 描述 directory

```text
GET /api/v1/directory/describe
```

返回：

- `service_did`
- 支持的 discovery profile
- 支持的资源类型：space / organization / actor / applet
- 是否支持 restricted query proof

### 8.2 搜索 Space

```text
POST /api/v1/directory/search-spaces
```

请求 MAY 包含：

- `query`
- `organization_did`
- `parent_space_id`
- `requester`
- `proofs`
- `limit`
- `cursor`

Directory MUST 对每个结果应用 `cx.space.discovery`、Space policy、organization endorsement 和 requester proof 过滤。

### 8.3 精确解析 Space

```text
POST /api/v1/directory/resolve-space
```

用于通过 `space_id`、alias、invite token 或 signed link 获取 stripped preview state。对 `invite_only` / `secret` Space，未授权请求 MUST 返回与不存在相同的错误形态。

### 8.4 搜索与解析 Organization

```text
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
```

Organization directory MUST respect organization discovery policy。公开组织 DID 可解析不表示成员列表、官方 Space 列表、服务拓扑或治理策略全文可公开。

### 8.5 搜索 Actor / Handle

```text
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Actor / handle directory MUST NOT return pairwise DID、private DID、private handle、未披露的组织账号或仅因共同 Space 推断出的关系。

### 8.6 私密联系人发现

```text
POST /api/v1/directory/private-contact-discovery
```

该操作用于 `cx.private_contact_discovery.v1`。请求 MUST 使用 blinded / padded connection identifier batch，响应只返回 time-bound reachability proof 或 invite/consent 引导，不得返回原始 connection identifier、完整 profile、成员列表或关系图谱。

## 9. MIMI Provider Facade Surface

MIMI Provider Facade 是面向 MIMI 草案的互操作服务面。它不替代 Principal Server / Federation / Device Key Server；它只把被授权的 Contrix Space 或 Flow discussion branch 投影为 MIMI room。

推荐操作：

```text
GET /api/v1/mimi/provider-directory
POST /api/v1/mimi/key-material
PUT /api/v1/mimi/rooms/{flow_id}/update
POST /api/v1/mimi/rooms/{flow_id}/notify
POST /api/v1/mimi/rooms/{flow_id}/messages
GET /api/v1/mimi/rooms/{flow_id}/group-info
POST /api/v1/mimi/consent/request
POST /api/v1/mimi/consent/update
POST /api/v1/mimi/identifiers/query
POST /api/v1/mimi/report-abuse
POST /api/v1/mimi/proxy-download
```

规则：

- 只有存在 accepted `cx.mimi.room_binding` 的 Space 或 Flow discussion branch 可以通过该 surface 暴露为 MIMI room。
- MIMI 写请求 MUST 使用 provider service DID 的 HTTP Message Signature，并绑定 source / destination / room id / request hash。
- Facade MUST 将 MIMI 写入转换为 Contrix Event，并执行 DID、device、MLS、capability、auth refs 和 Space policy 校验。
- MIMI provider timestamp、room id、user id 和 role 只能作为互操作 metadata，不得替代 Contrix event id、HLC、DID 或 capability。

完整语义见 `../extensions/mimi-interop.md`。

## 10. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 Event，但服务层仍需要可查询面。

至少建议提供：

```text
GET /api/v1/authz/effective-grants?space_id=<id>&subject=<did>
```

```text
GET /api/v1/authz/invites?space_id=<id>&subject=<did-or-handle>
```

```text
POST /api/v1/authz/check
```

`check` 接口适合：

- Events API 接收写入前预检查
- sync service 分发前快速过滤
- client 发送前本地 UX 提示

## 11. Space Bootstrap Flow

Contrix v1 的首次加入流程：

1. 用户输入 handle、DID 或 Space link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 DID Document 和 Space policy 发现 Principal Server / identity registry / events / sync / blob / authz 服务
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 Space metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk。**防投毒要求 (Snapshot Validation)**：由于 Sync Service 仍是服务节点，快照可能被恶意篡改。客户端 MUST 验证快照 manifest 的规范字段 `signature`、签名者授权、`state_hash` (Merkle Root)、frontier 和每个 chunk digest。`signature` 的 signer 必须是 Space owner、Space policy 授权的 snapshot issuer 或 witness quorum 成员。若校验失败，客户端 MUST 丢弃快照并回退到 `/events/*` 或 `/sync/backfill` 进行原始 Event 历史回放。
7. 从 frontier 之后拉取 backfill / sync stream 增量
8. 本地执行 reducer
9. 建立 read marker、notification cursor 等个人状态

## 12. 新鲜度与多服务并存

当多个 Principal Server 或受托 search / projection 扩展并存时，相关服务 SHOULD 公开：

- 当前 frontier
- snapshot frontier
- reducer profile
- 最后物化时间（如适用）

客户端 MAY 比较这些值来判断：

- 哪个服务更新
- 是否需要回退到 Event 重放
- 某个受托 projection 是否只是暂时落后，而不是数据冲突

对于 identity registry，同样 SHOULD 公开：

- DID 当前 head
- `seq`
- receipt 集合摘要

客户端可据此判断某个 registry 是：

- 最新 head
- 落后副本
- 还是可能发生了分叉或作恶

## 13. 传输安全与密文

服务面 SHOULD 区分：

- 路由所需元数据
- 可选端到端密文内容

如果 payload 已按 `policy.encryption_profile` 加密，则：

- Events / sync service MAY 不解密正文
- 但仍 SHOULD 保留 hash、cursor、causal 与目标引用

## 14. 防滥用与配额机制 (Anti-Spam & Quota)

在去中心化网络中，计算、存储与带宽都是稀缺资源。协议要求所有提供写入或传播服务的节点实现必须具备防御恶意滥用的能力：

### 14.1 存储责任与 Blob Quota
- **成本归属**：Space 的整体数据大小、历史 Event 数量及附属的 Blob 存储成本，逻辑上必须绑定到 Space 的 `owner` 或负责托管的 `responsible_actor_id`。
- **拒绝写入**：当 Blob 服务或 Principal Server 评估该 Space 占用的资源已超出预设的 Policy 配额 (Quota) 时，MUST 返回明确的资源超限错误 (如 HTTP 413 或 402)，并拒收新写入的 Event 或大文件 Blob。

### 14.2 写频率控制 (Rate Limiting)
- Events API 和 Sync Service 节点 SHOULD 基于 `actor_id` 与 `space_id` 实施严格的并发和频率限制。
- 对于来自未验证或低信誉 DID 的恶意刷写（例如短时间内进行海量无效的 `message.create` 或反复触发高并发图重组），节点有权暂时熔断该 DID 的请求。

## 15. 设计决定

Contrix v1 固定：

- 定义最小 principal server / identity registry / events / sync / blob / authz 服务面
- HTTP/JSON 路径是默认推荐 binding，但语义等价最重要，可支持其他调用风格
- 写接口必须幂等
- DID 写入采用多 registry / witness receipt，而不是区块链
- bootstrap 必须覆盖 invite / grant / snapshot / backfill
- 服务必须公开 reducer / schema / feature profile
- 明确 Space Owner 的资源记账责任与防滥用熔断标准

## 16. HTTP/JSON Binding

默认 HTTP/JSON binding 的具体路径、请求/响应形状、Blob 上传下载和标准错误码移至 `service-http-binding.md`。

`service-surface.md` 只定义服务角色和语义面。任何 HTTP、gRPC、WebSocket、SSE、message queue、libp2p 或 IPC 实现都必须映射到本文定义的等价语义。

## 17. 线级互操作要求

以下事项是 v1 的落地要求：

- Directory search result MUST 使用 `query-schema.md` 的分页、过滤和 `visibility_explanation` 约束；对不可见或不可枚举资源，错误形态 MUST 与不存在一致。
- Authz check response MUST 返回 `decision`、`matched_grants`、`applied_constraints`、`policy_results`、`missing_proofs`、`frontier` 和 `cache_valid_until`；`decision` 只能是 `allow`、`deny`、`quarantine`、`require_review` 或 `soft_fail`。
- Service describe MUST 声明 `service_did`、`service_type`、`protocol_version=1.0`、`supported_profiles`、`supported_operations`、`auth_metadata`、`limits`、`rate_limit_policy` 或 `rate_limit_policy_ref`、`plaintext_visibility` 和 `binding`。客户端 MUST 拒绝 service DID、Space policy 或 profile 不匹配的服务。
- Sync cursor recovery MUST 按 `sync-conformance-vectors.md` 执行：cursor 是 opaque token；过期或缺口时返回可恢复错误，并提供 backfill 起点或 snapshot frontier。
- Event source consistency MUST 按 `encoding-conformance-vectors.md` 和 `sync-conformance-vectors.md` 执行：重复 Event 幂等，冲突 Event 拒绝，event order、hash、签名和 `actor_seq` 必须可复现验证。


