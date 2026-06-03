---
title: Service Surface And Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-05-26
see_also:
  - sync/service-http-binding.md
  - sync/operations-sync.md
  - sync/transport-bindings.md
  - sync/federation.md
  - conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标（Goals）

如果只有对象模型、同步原则和 capability，而没有最小线级服务面，协议仍然很难真正互操作。

因此 Cokret v1 定义：

- identity registry 如何收发 DID 操作与 receipt
- Events API 如何提交、读取、回填 signed Event
- Principal Server 如何提供 account aggregate stream、snapshot 与 backfill 协调
- search / View projection 的语义边界如何在客户端或显式受托服务中保持一致
- directory 如何做 Realm / Organization / Actor 的授权搜索与精确解析
- blob 如何上传与校验
- invite / grant 如何参与首次加入工作区

本文给出 **最小可互操作服务面**。
默认调用风格采用 HTTP/JSON binding。Operation 语义可以映射到 gRPC、GraphQL、WebSocket、SSE、message queue、libp2p 或本地 IPC，但 **v1 core wire conformance 必须提供 HTTP/JSON binding**；非 HTTP binding 只能作为 extension profile 声明，并且必须提供语义等价的操作、认证、授权、幂等、分页、错误和流控语义。详细规则见 `transport-bindings.md`。

本文件按服务角色说明接口语义。所有 REST endpoint 的字段级请求 / 响应 schema、认证模式、访问限制和幂等规则以 [service-http-binding.md](service-http-binding.md#24-字段级-schema-索引) 为准；本文件中的 JSON 或字段列表仅用于解释服务面，不构成完整 schema。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

DID Document SHOULD 只负责：

- 声明 principal server、identity registry、events、sync service、blob、capability 服务入口
- 声明服务 DID 或服务 endpoint

它不应直接塞入：

- 当前 grant 全量状态
- 当前 realm 当前态
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

常见组合如下。这里的"需要"表示协议交互需要该能力存在，不表示每个用户都必须自建；个人和小团队通常只自建一个 Principal Server，其余基础设施可使用公共或托管服务。

*Table 2-1. 服务角色与 REST namespace 对照（informative）。namespace 一栏与 service-http-binding.md §2.1 重合，本表是 informative 视图，canonical 单一来源是 [service-http-binding.md §2.1](./service-http-binding.md)。*

| 实际服务器 | 普通部署建议 | 通常暴露的 REST namespace | 主要能力 |
| --- | --- | --- | --- |
| Principal Server | 普通用户或组织自建的核心入口 | `/server`, `/_cokret/self/events`, `/account`, `/snapshot`, `/federation`, 可代理 `/blob`, `/authz`, `/_cokret/self/device_messages`, `/keys` | 用户/组织的受控入口、Event 提交/读取、client sync、联邦 transaction、服务发现聚合、明文可见边界执行。 |
| Identity Resolution Infrastructure | 普通用户默认使用公共服务或本地 method resolver；高安全或隔离网络才自建完整基础设施 | `/identity`, `/server` 或 method-specific resolver | DID document、DID / KERI log、handle binding、receipt、witness、watcher、OOBI、service endpoint discovery。 |
| Auth Server | 个人部署可内置；组织通常独立或接入 SSO | 通过 `auth_metadata` 暴露，具体登录路径 MAY 由部署定义 | 登录、passkey/OIDC/SSO、session grant、device pairing、账户恢复；不得直接替代 DID 控制权。 |
| Sync / Federation Server | 普通用户通常内置在 Principal Server | `/account`, `/snapshot`, `/federation`, `/server` | client sync、subscription、backfill、snapshot head、跨域 transaction、重放和 destination 绑定校验。 |
| Directory Server | 普通用户默认使用公共目录；组织发现或隔离网络才自建 | `/directory`, `/server` | Realm/Organization/Actor/handle/Applet 的授权搜索和解析，私密联系人发现，最小披露发现。 |
| Blob / Media Server | 个人通常内置；文件量大或高安全组织可独立 | `/blob`, `/server` | blob upload、authenticated download、HEAD、Range、thumbnail、preview、retention、media safety。 |
| Device / Key Server | E2EE profile 需要；个人通常内置在 Principal Server | `/_cokret/self/device_messages`, `/keys`, `/_cokret/self/keys/keypackages`, `/_cokret/self/keys/backups`, `/server` | to-device message、one-time key、fallback key、MLS KeyPackage claim、device list、encrypted key backup metadata / ciphertext。 |
| Authz / Policy Server | 个人可内置；共享 Realm 和组织治理建议独立 | `/authz`, `/_cokret/self/policy/check`, `/server` | effective grants、invite 查询、capability precheck、签名 policy decision、risk / quarantine。 |
| Push Gateway | 普通用户默认使用公共或托管推送；内网或高安全组织可自建 | `/push`, `/server` | push device register/unregister、脱敏通知投递、APNs/FCM/厂商推送适配。 |
| Applet Server | 集成/桥接/自动化可选 | `/applet`, `/server` | applet describe、transaction、Ghost Actor、portal Realm、third-party lookup。 |
| MIMI Provider Facade | 与外部 MIMI provider 互通时可选；可由 Principal Server、anchorer service 或 Applet Bridge 承载 | `/mimi`, `/.well-known/mimi-protocol-directory`, `/server` | MIMI provider discovery、room binding、key material、submit message、groupInfo、consent、identifier query、abuse report、proxy download。 |
| Agent Runtime Server | agent 场景可选但推荐 | `extensions/agent-*` 定义的 service surface，通常通过 `/_cokret/self/events` 写回结果 | agent 执行、tool 调用、A2A/ACP/MCP handoff。 |
| Realtime Media Server | 通话/会议可选 | `/_cokret/self/rtc/ice-config`，以及 WebRTC signaling / TURN / SFU profile | ICE config、TURN/STUN、SFU/MCU、录制策略、短期媒体凭证。 |
| Moderation / Compliance Server | 公共或组织部署建议独立 | `/moderation`, `/server` | report、审核队列、server ACL、policy list、appeal、legal hold / erasure workflow。 |
| Archive / Recovery Service | history sharing、late key recovery 或组织恢复场景可选；高安全部署必须显式声明 | `/server` + `supported_operations` 中的 keys / blob / events 子集 | Archive Node、Key Recovery Service 或 Recovery Service。只能按 Realm policy、history visibility、T0 membership 和 capability 返回最小必要 epoch material / backup envelope / recovery proof；不得因持有归档副本自动获得明文读取权。 |

推荐 deployment profile：

- `principal_server_personal`：一个 Principal Server；内部合并 Events API + Sync/Federation + Blob + Device/Key + Authz；客户端可自行维护本地 search / projection；Identity Resolution Infrastructure、Directory、Push 和 TURN/Media 默认可用公共服务。
- `principal_server_organization`：一个组织委托的 Principal Server；通常搭配 Auth Server；需要统一授权和审计时增加 Policy Server；Blob、Directory、Push 可按规模和合规要求拆分。
- `principal_server_secure_organization`：一个或多个组织委托的 Principal Server，搭配 Auth Server、Identity Resolution Infrastructure、Policy/Authz、Blob/Media；公共 Directory、Push 或外部 federation ingress 只作为可选互联入口。
- `isolated_enclave`：Principal + Identity Resolution Infrastructure + Auth + Directory + Policy/Authz + Events/Blob + Sync/Federation + Audit/Compliance 全部在信任域内部署。
- `public_federation_ingress`：Principal/Federation + Policy + Moderation + Directory 的受限组合，不默认可见明文。
- `applet_service`：Applet Server + Event writer + Authz precheck，只在授权 namespace 和 capability 内工作。
- `mimi_provider_facade`：MIMI facade + Device/Key + Federation/Authz integration，只投影被 `ck.mimi.room_binding` 授权的 Realm / Flow discussion track。
- `agent_runtime`：Agent Runtime + Event writer，所有写入仍通过 principal / agent DID 签名。

客户端选择服务时 MUST 先解析 DID Document 与 Realm policy，再校验 `server/describe`。不得因为多个服务位于同一域名，就默认它们拥有相同权限或相同明文可见范围。

## 3. 通用服务描述接口

所有网络可发现服务 MUST 提供：

```text
GET /_cokret/describe
```

*Example (informative). `/_cokret/describe` 响应示例，字段权威定义以 schema 为准。*

```json schema=schemas/service-describe.schema.json
{
  "service_did": "did:web:alice.example.net",
  "trust_domain": "ck:trust_domain:did.webvh.alice.example",
  "service_type": "principal_server",
  "protocol_version": "1.0",
  "supported_profiles": [
    "ck.profile.principal_server.v1"
  ],
  "supported_operations": [
    "ck.server.describe",
    "ck.events.submit",
    "ck.events.query",
    "ck.account.subscribe"
  ],
  "supported_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://alice.example.net"
    }
  ],
  "supported_features": [
    "sync_stream",
    "snapshot",
    "notifications"
  ],
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "supported_auth_methods": ["passkey", "oidc", "device_pairing"],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  },
  "limits": {
    "max_body_bytes": 1048576,
    "max_events_per_batch": 100,
    "device_message_max_ttl_seconds": 86400,
    "read_cursor_debounce_ms": 1000,
    "dangling_redaction_min_retention_days": 30,
    "snapshot_retention_heads": 2
  },
  "plaintext_visibility": {
    "data_classes": [],
    "max_visibility": "none",
    "event_kinds": [],
    "payload_paths": [],
    "blob_purposes": [],
    "projection_outputs": [],
    "notes": "content-only E2EE baseline"
  },
  "rate_limit_policy": {
    "policy_version": "2026-05-02",
    "entries": [
      {
        "operation_id": "ck.events.submit",
        "rate_limit_scope": ["service_did", "realm_id"],
        "window_seconds": 60,
        "max_requests": 120,
        "burst": 20
      }
    ]
  },
  "implemented_features": [
    "sync_stream",
    "snapshot"
  ],
  "claimed_profiles": [
    {
      "profile_id": "ck.profile.principal_server.v1",
      "claim_kind": "self_claimed",
      "claimed_at": "2026-05-02T00:00:00Z"
    }
  ],
  "verified_profiles": [
    {
      "profile_id": "ck.profile.core_event_store.v1",
      "claim_kind": "cotest_verified",
      "cotest_run_id": "cotest-2026-05-02T000000Z",
      "artifact_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "artifact_ref": "https://cotest.example/log/cotest-2026-05-02T000000Z",
      "cotest_issuer_did": "did:web:cotest.example",
      "signature": "base64url:...",
      "timestamp": "2026-05-02T00:00:00Z"
    }
  ],
  "experimental_features": [],
  "compat_surfaces": [],
  "development_mode": false
}
```

服务类型命名规则：

- DID Document `service.type` 使用协议注册名，例如 `CokretPrincipalServer`、`CokretDirectory`。
- describe 响应的 `service_type` 使用小写注册值，例如 `principal_server`、`sync_node`、`identity_registry`、`auth_server`、`blob_node`、`directory_service`、`device_key_service`、`authz_service`、`policy_server`、`push_gateway`、`applet_service`、`mimi_provider_facade`、`agent_runtime`、`media_service`、`sfu_service`、`turn_service`、`moderation_service`、`archive_node`、`key_recovery_service`、`recovery_service`。其中 `sync_node` 保留：它不是独立的 describe-only 角色，而是 `realm.schema.json` / `realm-join-candidate.schema.json` 的 service class 枚举值，仅当 Realm policy 授权其接收 join-side submission / delivery binding 时使用（见 [`realm-join-candidate.schema.json`](../../artifacts/schemas/realm-join-candidate.schema.json)）。
- conformance profile 使用 `ck.profile.*` 标识，例如 `ck.profile.principal_server.v1`。
- 实现 MUST 区分这三层名称，不得把 DID service type、运行时 service_type 与 conformance profile 混用。

### 3.0 Describe response claim levels

`server/describe`（以及结构等价的 `identity/describe` / `events/describe` / `sync/describe` /
`directory/describe` / `applet/describe`）响应 MUST 使用同一个 canonical `ServiceDescribe` shape。除 `service_did`、`trust_domain`、`service_type`、`protocol_version`、`supported_profiles`、`supported_operations`、`supported_bindings`、`supported_features`、`auth_metadata`、`limits`、`plaintext_visibility` 和 `rate_limit_policy` / `rate_limit_policy_id` 之外，响应还 MUST 按 **claim level** 区分以下字段；schema 见
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)（`ck.schema.service_describe.v1`）：

- `supported_operations: operation_id[]` — 该 endpoint 可被实际调用的 operation_id。仅表示 wire 可达，
  不构成 profile claim。元素 SHOULD 命中 `operation-registry.json` 注册项。
- `trust_domain: ck:trust_domain:<scope>` — 部署级 replay boundary。客户端 / 接收方 MUST 要求它与 Realm create-locked trust domain、federation header 和本地 receive context 一致；不一致时不得接受 replay-sensitive proof。
- `implemented_features: feature_id[]` — 服务有实现代码、但 **不一定** 通过 conformance verification 的 feature。
  构建 conformance matrix 的工具 MUST 把它视为严格弱于 `claimed_profiles`。
- `claimed_profiles: [{profile_id, claim_kind: "self_claimed", ...}]` — 服务自声明加入的 profile。
  `claim_kind` 当前固定为 `self_claimed`；cotest 验证结果 MUST 改写到 `verified_profiles`，不得复制到本字段。
- `verified_profiles: [{profile_id, claim_kind: "cotest_verified", cotest_run_id, artifact_digest, artifact_ref, cotest_issuer_did, signature, timestamp, expires_at?}]` —
  附带 cotest run 标识、artifact hash、artifact 获取位置或 transparency-log 引用、cotest issuer DID、签名与验证时间戳的已验证 profile。**约束**：当 `development_mode=true`
  时，本数组 MUST 为空——dev / placeholder proof 路径不得用来宣告生产 conformance（见本节 §3.0）。
- `experimental_features: feature_id[]` — 服务暴露但不承诺稳定互操作的 feature；客户端 MUST NOT
  把它当成协议级决策的依据，也不得继承到 `claimed_profiles`。
- `compat_surfaces: [{name, kind, ...}]` — 仅为兼容性而暴露的 legacy / external interop surface
  （`kind` ∈ {`matrix_passthrough`, `mimi_passthrough`, `legacy_alias`, `external_interop`, `deprecated_alias`}）。
  这些 surface **不构成** Cokret v1 conformance 的一部分。
- `development_mode: boolean` — 必填；为 `true` 时 `verified_profiles` MUST 为空。省略不是 false，SDK / conformance tooling MUST 把缺失视为 invalid describe。
- `egress_network_policy` — 可选的出站网络策略摘要。会解析 DID、联邦 peer、媒体、snapshot、Policy Server、Webhook、Applet 或 Agent endpoint 的服务 SHOULD 暴露粗粒度策略；完整 SSRF 防护语义见 [`api-conventions.md`](./api-conventions.md) §11.2。

旧版本只暴露 `supported_operations`，把 endpoint 可达性、feature 实现、profile claim 混在一起。
本次区分要求实现：

1. 在 describe 响应中同时输出上述六个字段（向后兼容地追加在原有字段之后）。
2. dev / placeholder posture 下，自检 `verified_profiles == []` 并在初始化时 fail closed。
3. cotest 与 admin 等下游 MUST 按 claim level 渲染不同 badge：`self_claimed`、`cotest_verified`、
   `experimental`、`compat`、`not_claimed`。
4. 客户端不得只信任服务自报的 `verified_profiles`；使用生产 conformance 结论前 MUST 通过 `artifact_ref` 或等价 transparency log 取得 cotest artifact，校验 `artifact_digest`、`cotest_issuer_did`、`signature`、时间戳和可选 `expires_at`。

`plaintext_visibility.data_classes` 是机器可判定的明文类别白名单。`event_kinds`、`payload_paths`、`blob_purposes` 和 `projection_outputs` 只是进一步缩小或解释范围，不能替代 `data_classes`；`notes` 只供人读。Realm policy 的 `plaintext_visible_services[].data_classes` MUST 是目标 `ServiceDescribe.plaintext_visibility.data_classes` 的子集，且 `visibility` 不得高于 `max_visibility`。若 describe 缺失 `data_classes` 或只给出自由文本 `purposes`，客户端 / reducer MUST 把它视为不能接收私有明文。

### 3.1 Identity Resolution Surface

Identity Resolution Surface 是 DID method resolver、registry、witness、watcher 或 method-specific verifier 的统一抽象。`did:plc` 可以由 PLC directory、mirror 或 audit source 实现；`did:web` 可以由 HTTPS / DNS resolver 实现；`did:webvh` 可以由 DID log、watcher 和 witness 实现；`did:key` 可以只由本地 resolver 实现，不需要网络 API；`did:keri` 可以由 KERI log、witness、watcher 和 OOBI discovery 实现。

网络型 identity registry 至少应提供以下语义：

#### 3.1.1 描述 registry

```text
GET /_cokret/root/identity/describe
```

返回：

- `service_did`
- `registry_mode = writer | witness | replica`
- 支持的 receipt 类型
- 当前软件版本与实现 profile

#### 3.1.2 获取当前 DID Document

```text
GET /_cokret/root/identity/document?did=<did>
```

返回 SHOULD 包含：

- 当前 materialized DID Document
- 当前 `head_event_digest`
- 当前 `seq`
- 可选 witness receipts

#### 3.1.3 获取 DID 日志

```text
GET /_cokret/root/identity/log?did=<did>&cursor=<cursor>&limit=<n>
```

用于：

- 审计
- 重建 DID Document
- 验证 `key_log` 与 registry head 一致

返回的每个 log entry MUST validate as `did-key-log-entry.schema.json`：`seq=0` 表示 inception 且不得携带 `prev_event_digest`；`seq>0` 必须携带 `prev_event_digest`，并且该值必须等于前一条 accepted entry 的 `head_event_digest`。`operation` 是规范化操作 kind；DID-method-specific 原始操作对象放在 `operation_body`，不得使用通用 JSON Patch 形态。

#### 3.1.4 提交 DID 更新

```text
POST /_cokret/root/identity/submit-did-operation
```

请求体 SHOULD 包含：

- `did`
- `did_method`
- `operation`
- `proofs`
- `seq` / `prev_event_digest`（当 DID method 暴露 key-log 序号或 head hash 时）
- `policy_context`（可选，绑定 resolver / registry policy）

要求：

- `operation` 是 DID-method-specific 原始操作对象；实现 MUST NOT 把 DID 更新降格为通用 JSON Patch。
- 相同 DID method operation id / seq / canonical hash 的重复提交 MUST 幂等成功。
- 相同 DID method operation id / seq 但内容不同 MUST 拒绝。
- registry MUST 验证从 `inception_key` 出发的授权链

#### 3.1.5 获取 receipt / witness 证明

```text
GET /_cokret/root/identity/receipts?did=<did>&head=<event-hash>
```

#### 3.1.6 写入确认建议

Cokret v1 要求：

- writer 客户端同时向多个 registry / witness 提交 `did_operation`
- 至少拿到 `k-of-n` receipt 才视为提交成功
- 读取时可附带 `expected_head` 或 `min_seq`

这让 DID 写入仍然是普通网络请求，而不是全网区块共识。

## 4. Events API

Events API 是 Principal Server 提供的 signed Event 提交、读取、回填和前沿查询接口。普通部署 SHOULD 由 Principal Server 直接暴露 `/_cokret/self/events/*`。

Cokret v1 不规定 Event 在服务端的物化形态——不要求集中式 record 仓库、提交日志或仓库命名接口。Principal Server 可以托管、复制或索引 Event,但接收方仍必须验证 Event 签名、DID 控制链、canonical hash、`actor_seq` 路径递增、`prev_refs` 与 `refs[role=authorized_by]` 因果依赖和 `event_id` 幂等性。

Events API 至少应提供以下语义：

### 4.1 描述 Events API

```text
GET /_cokret/self/events/describe
```

返回：

- `service_did`
- 支持的签名算法
- 支持的 Event schema / reducer profile
- 支持的 actor frontier、Realm frontier、resolve 和 stream/backfill 能力

### 4.2 提交 Event

```text
POST /_cokret/self/events
```

请求体是一个 Event Envelope，或 profile 明确允许的 Event Envelope 数组。

要求：

- 同一个 `event_id` 重复提交相同 canonical bytes MUST 幂等成功。
- 同一个 `event_id` 若内容不同 MUST 拒绝并记录冲突。
- 服务 MUST 验证 Event 签名、actor DID、device/session、capability、Realm policy、`actor_seq` 和因果依赖。
- 服务 SHOULD 返回 accepted event、当前 actor frontier、Realm frontier 以及 read-your-writes barrier `cursor`（schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)，purpose=`barrier`）。

当请求体包含 `events[]` 时，服务 MUST 按数组顺序逐项处理。前一项已接受的 Event 可以满足后一项的 bytes / Event ID / actor chain / `prev_refs` / payload-level causal reference 解析；同批中尚未处理、已拒绝或进入 quarantine 的 Event 不能作为已解析依赖。`refs[role=authorized_by]` 是授权状态引用，不是普通解析引用：被引用 grant / authority MUST 已存在于后一项 Event 的 `anchor_ref` pre-state 中，才可用于授权判定。同批前一项创建、delegate、恢复或扩权的 grant 不得在同一 Anchor batch 内立即授权后一项写入；依赖方必须等后续 Anchor 覆盖该 grant，或在当前批次被拒绝/隔离。`refs(role="after")` 只表达后续 Anchor 的排序约束，不允许读取同批 effect 来满足 precondition 或授权。批处理中单项失败不得回滚已接受项：成功项进入 `accepted[]`，重复幂等项进入 `duplicate[]`，失败项进入 `rejected[]` 或 `quarantine[]`。若后续 Event 依赖同批失败或缺失 Event，服务 MUST 以 `dependency_missing`、`causal_conflict`、`soft_fail` 或等价原因拒绝/隔离该后续 Event，而不是隐式接受。

### 4.3 获取单个 Event

```text
GET /_cokret/self/events/{event_id}
```

不可见或不存在的 Event MUST 使用统一 `not_found` 语义，除非调用方有审计/管理权限。

### 4.4 批量获取 Event

```text
POST /_cokret/self/events/resolve
```

请求体可携带一组 `event_ids` 或 `event_digests`。响应按 Realm policy、history visibility、E2EE envelope policy 和 redaction policy 过滤 payload。

### 4.5 列出 / 回填 Event

```text
GET /_cokret/self/events?actors=<did>&realms=<id>&before=<cursor>&limit=<n>    # 历史 backfill
GET /_cokret/self/events?actors=<did>&realms=<id>&after=<cursor>&limit=<n>     # catch-up
```

参数完整定义与"近邻先返回"默认顺序规则见 [`service-http-binding.md` §3.3](./service-http-binding.md)。

用于：

- actor 历史恢复
- Realm 审计回放
- 补齐缺失 Event
- 从 snapshot frontier 后继续 reducer replay

### 4.6 获取 Event frontier

```text
GET /_cokret/self/events/frontier?actor_id=<did>
GET /_cokret/self/events/frontier?realm_id=<id>
```

返回调用方可见范围内的 actor frontier、Realm frontier、latest HLC、可选 witness receipt / event batch receipt。frontier 只用于同步和强一致读取，不能替代 Event 集合本身。

## 5. Account Aggregate / Snapshot Surface

Account Aggregate / Snapshot Surface 是 Principal Server 提供的 **账号视角聚合** 能力 + snapshot 入口。逐 Realm 的事件查询和实时订阅走 Events Surface（`ck.events.query` / `ck.events.subscribe`，见 `service-http-binding.md` §3.3 / §3.4）。该 surface 不是独立第三方服务器角色，本质是 Principal Server 上聚合多 Realm frontier、to_device、account_data、device_lists 与 presence 的视图。客户端只应使用本 principal 控制/委托的 Principal Server、对方 principal 控制/委托的 Principal Server，或 Realm policy 明确列出的 shared anchorer / sync service。

> 历史命名 "Sync Surface" 容易让读者把它误解为"所有同步路径"，但事件流读取/订阅已迁移到 Events Surface。本节仅描述 account-aggregate 与 snapshot 入口。

本节定义 account 与 snapshot 两类操作（事件流读取请到 Events Surface）：

- `GET /_cokret/self/account/subscribe`：客户端账号视角聚合同步（`ck.account.subscribe`），见 `client-sync.md`。
- `GET /_cokret/self/snapshot/head`：snapshot manifest 入口。

事件流读取统一在：

- `GET /_cokret/self/events?realms=...&before=...` 或 `&after=...`（`ck.events.query`，双向 cursor；`before` 取历史方向，`after` 取未来方向。详见 [`service-http-binding.md` §3.3](./service-http-binding.md)）
- `GET /_cokret/self/events/subscribe?realms=...&catchup=...`（`ck.events.subscribe`，可从 `after=` 追赶到当前 frontier，并支持多 realm 一次订阅）

实现不得把账号聚合 (`/_cokret/self/account/subscribe`) 和裸事件读 (`/_cokret/self/events`) 合并成语义不明的单一“stream”接口；它们的 selector、auth、frame schema、freshness 行为都不同。其他 transport MAY 使用不同帧名，但必须映射到上述 canonical operation。

### 5.1 描述 account aggregate service

```text
GET /_cokret/self/account/describe
```

### 5.2 snapshot 入口

```text
GET /_cokret/self/snapshot/head?realm_id=<id>
```

用于拿到当前推荐 snapshot manifest。

### 5.3 Move / Anchor 状态与 Bottom 暴露

Sync 响应 MUST 在每条 Move 上携带其当前协议状态字段（`event_state`），取值与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §13 失败状态表一致：`pending_anchor` / `effective` / `failed_precondition` / `failed_bottom` / `rejected_anchor` / `anchorer_paused`。

State query / projection 响应 MUST 在 cell 当前 join 值为 ⊥ 时返回结构化 Bottom 诊断，schema 参见 [`schemas/bottom.schema.json`](../../artifacts/schemas/bottom.schema.json) 与 `ck.schema.bottom.v1`：

```json
{
  "cell": "ck:cell:ck.component.realm.policy.v1:ck.realm.01j…",
  "status": "bottom",
  "bottom": {
    "kind": "conflict",
    "cells": ["ck:cell:ck.component.realm.policy.v1:ck.realm.01j…"],
    "event_ids": [
      "ck:event:84210000-0000-7000-8000-000000000000…",
      "ck:event:a5294000-0000-7000-8000-000000000000…"
    ],
    "anchor_view": {
      "leaves": ["ck:anchor:sha256:dddd…"],
      "state_root": "sha256:eeee…"
    },
    "heads": [{"…": "candidate-A"}, {"…": "candidate-B"}],
    "details": {}
  }
}
```

规则：

- `bottom=reject` cell 的 query MUST 返回 `status:"bottom"` 与诊断；客户端 / 授权路径 MUST NOT 把 `heads` 当作 allow。
- `bottom=expose` cell 的 query MAY 返回 `status:"conflict"` 暴露多 head 给 projection / UI；同样不得用作授权 allow。
- `event_state="anchorer_paused"` 表达 anchorer cell 当前为 ⊥（spec §4.4）：除 recovery anchorer 签发的 Move 外，UI 应明显提示 Realm-wide pause。
- `bottom_escalation_after_ms` 超时后服务端 MUST 在 `bottom.escalated_at` 标记，并向 admin / recovery governance 渠道带外通知；超时本身不自动选 winner。

`/_cokret/self/account/subscribe` / `/_cokret/self/events` / `/state/query` 响应 MUST 在文档化字段位置嵌入上述 `bottom` 对象（位置与精确 wire 形态见 [`service-api-schema.mdx`](service-api-schema.mdx) `ck.schema.bottom.v1` 引用）。

### 5.4 明文与服务信任

如果 Realm 未启用 E2EE 或内容层加密：

- 客户端 MUST NOT 将 message body、comment body、附件明文或可逆派生摘要提交给未授权第三方服务。
- `events`、`sync`、`sync/subscribe`、`sync/backfill` 的服务端必须是 principal DID、Organization DID 或 Realm policy 明确委托的 Principal Server。
- Directory、Push Gateway、Blob preview、Policy preview，以及任何协议外 search / projection 服务，若会接收正文、正文摘要、附件预览、全文索引或可逆派生内容，MUST 在 Realm policy 中声明为 `plaintext_visible_services`。
- shared anchorer / sync service 若可见明文，必须在 Realm policy 中作为明文可见方列出。
- `encryption_profile="none"` 只说明 content 未使用 E2EE；它不自动授权任意服务保存、索引、导出或生成可逆派生内容。只有 Realm 同时把内容声明为 public content（例如 `history_visibility=world_readable` 且 preview / export policy 允许 public processing）时，服务才 MAY 按公开内容处理；否则仍按私有明文执行 `plaintext_visible_services` 检查。
- 接收方 Principal Server 可以看到投递给该接收方的非加密内容；客户端和 Realm policy MUST 把这视为内容可见边界，而不是透明中继。
- 非受信服务只能接收公开内容、密文 envelope 或不可解析 payload。

## 6. Search / Projection Semantics

Cokret v1 不定义必需的远端索引或应用视图服务面。当前态查询、View projection、inbox、notification 和全文搜索默认属于客户端或 SDK 的本地派生能力；客户端可以根据已同步且已授权、已解密的 Event 集合自行维护本地索引，也可以完全不提供搜索功能。

实现 MAY 提供协议外或扩展 profile 的受托 search / projection 服务，但该服务不是核心协议角色。任何此类服务都不得成为真相源；其输出必须能追溯到 signed Event、reducer profile、View definition 和 causal frontier。

### 6.1 结构化查询形状

若客户端、SDK 或可选受托服务对外暴露可互操作查询语义，SHOULD 复用 `query-schema.md` 中的 Query 形状：

- `object_types`：标准对象类型，例如 `realm`、`space`、`flow`、`message`、`morph`（Space 通过 `space.kind` 区分 board/list/...；Flow 默认入口通过 track primary 解析规则得到）
- `morph_types`：当 `object_types` 包含 `morph` 时，可进一步限定开放对象类型
- `facets`：schema-declared capability hint 选择器，只用于 Morph 或声明支持 facets 的标准对象；不得作为授权、状态机、排序或 reducer 语义的唯一来源
- `relation`
- 过滤条件
- 排序
- cursor
- limit
- `view_id`、`projection` 与 `renderer`：非 raw projection SHOULD 使用核心原语 `collection` / `timeline` / `graph` / `document` / `composite`；例如看板展示使用 `projection="collection", renderer="board"`。
- barrier `cursor`：可选。若实现支持读己之所写等待，则必须把等待条件绑定到本地已知的因果前沿，例如特定 `event_id` / event hash / Realm frontier。Wire 形态与 stream cursor 共享 `ck:cursor:<base64url>`，由内部 `purpose` 字段区分（见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 与 [`api-conventions.md` §7](./api-conventions.md)）。

barrier cursor 在 Query / Projection 语义中是读己之所写 barrier，不是 Client Sync 的 stream cursor / `after=` resume token。实现 MAY 把它编码为 opaque token，但内部 MUST 绑定调用方、`realm_id`、目标 `event_id`、event hash、filter / query hash、服务 DID 和过期时间。Projection 服务收到该 cursor 时，应等待本地可验证 frontier 覆盖目标事件；若等待超时返回 `timeout`，若服务本地 frontier 明确落后返回 `stale_frontier`，若服务暂时无法追赶或不可用返回 `temporarily_unavailable`。Client Sync 仍必须只使用 [`client-sync.md`](./client-sync.md) 定义的 stream cursor 作为 `/_cokret/self/account/subscribe after=`。

### 6.2 Flow Discussion / Context Projection

Flow context timeline、Flow discussion timeline 和 Flow context projection 是客户端展示形态，不要求远端 endpoint。无论在客户端本地还是受托服务中执行，Flow 的所有 track 都按 Flow 的 effective scope 执行 membership / history visibility 检查：`Flow.scope_circle_id=null` 时按父 Realm；`scope_circle_id` 指向 [Circle](../models/circle.md) 时按该 Circle 自身 policy 与 membership 独立裁剪。Synthesis 与 discussion 同 scope，可见性同源。不得因为 Flow 在某 scope 可见就授予其他 scope 或 Board/List 或其他 Realm 对象权限。

### 6.3 Inbox / Notification Projection

Inbox 和 notification 可以由客户端从本地 Event、read cursor、mention Relation、assignment Relation 和 actor-private account data 派生。若受托服务生成 inbox preview、通知摘要或可逆派生内容，必须满足本节明文边界。

### 6.4 全文搜索

全文搜索是可选功能。请求形状 MAY 使用：

```json
{
  "query": "legal review",
  "realm_ids": ["ck:realm:0196419b-0000-7000-8000-000000000000"],
  "object_types": ["message", "flow", "morph"],
  "morph_types": ["comment"],
  "sender_actor_id": "did:web:alice.example.com",
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
      "object": {"_comment": "<Object 当前态 — 与 ck.objects.* 返回形态相同>"},
      "highlights": [
        { "field": "content.body", "snippet": "Please complete the <em>legal review</em> by Friday." }
      ]
    }
  ],
  "next_cursor": "search_cursor_abc",
  "total_estimate": 42
}
```

**E2EE 场景说明**：在加密 Realm 中，远端服务无法对密文执行全文搜索。默认搜索发生在客户端本地：客户端同步 Event、解密可见内容，并自行维护本地全文索引。受控网络中的 TEE 或组织搜索服务属于可选扩展，不是核心协议能力。

### 6.5 明文搜索边界

Search / projection 派生结果可能比 account aggregate surface 更容易查询，也可能包含正文摘要、命中片段、embedding 或通知摘要。因此：

- 非 E2EE 私有 Realm 的全文搜索、embedding、通知摘要、inbox preview 和报表投影只能由 `plaintext_visible_services` 中列出的服务生成或保存。
- 未列入 `plaintext_visible_services` 的受托 search / projection 服务 MUST 只接收公开内容、密文 envelope、不可逆 hash、最小 routing metadata 或 policy 明确允许的 stripped preview。
- 客户端在选择受托 search / projection 服务前 MUST 校验 service DID、supported profile、Realm policy 委托和 plaintext-visible 声明。
- Public plaintext Realm 的搜索 / preview 服务仍 MUST 区分 `directory_card`、`stripped_state`、`history_stub` 和 `history_snippet`；history snippet 只能在 `ck.realm.preview_policy` 或等价 public export policy 允许时生成，不能从 `discoverability=public` 推导。
- Search / projection 输出不得扩大可见性；查询结果、通知、搜索命中和 preview 都必须受底层 Realm policy 与 capability 约束。

服务端强制边界：

- Events / Sync / Federation / Push / Blob preview，以及任何受托 search / projection 服务在接收包含明文或可逆派生摘要的请求时，MUST 检查自身 service DID 是否在当前 Realm policy 的 `plaintext_visible_services` 中，且 `visibility` 等级与 `data_classes[]` 均覆盖该内容类型。
- 未授权服务 MUST 拒绝明文请求并返回 `capability_denied` 或 `schema_violation`，不得静默索引、转发、缓存或降级保存。
- 恶意客户端把明文发送到协议外服务不属于协议可强制阻止的范围；但任何声称支持 Cokret profile 的服务若接收或处理未授权明文，均视为 profile violation。

## 7. Blob Surface

blob 服务至少应提供：

### 7.1 上传 blob

```text
POST /_cokret/self/blob/upload
```

返回：

- `blob_ref`
- `sha256`
- `size_bytes`

### 7.2 查询 blob 头信息

```text
HEAD /_cokret/self/blob/get?blob_ref=<ref>
```

### 7.3 下载 blob

```text
GET /_cokret/self/blob/get?blob_ref=<ref>
```

blob 校验 MUST 基于内容哈希，而不是单一 URL。

## 8. Directory Surface

directory 是授权过滤后的发现与搜索服务面。它是派生索引，不是真相源。

### 8.1 描述 directory

```text
GET /_cokret/find/directory/describe
```

返回：

- `service_did`
- 支持的 discovery profile
- 支持的资源类型：realm / organization / actor / applet
- 是否支持 restricted query proof

### 8.2 搜索 Realm

```text
POST /_cokret/find/directory/search-realms
```

请求 MAY 包含：

- `query`
- `organization_did`
- `source_realm_id`
- `requester`
- `proofs`
- `limit`
- `cursor`

Directory MUST 对每个结果应用 `ck.realm.discovery`、Realm policy、organization endorsement 和 requester proof 过滤。

### 8.3 精确解析 Realm

```text
POST /_cokret/find/directory/resolve-realm
```

用于通过 `realm_id`、alias、invite token 或 signed link 获取 stripped preview state。对 `invite_only` / `secret` Realm，未授权请求 MUST 返回与不存在相同的错误形态。

### 8.4 搜索与解析 Organization

```text
POST /_cokret/find/directory/search-organizations
POST /_cokret/find/directory/resolve-organization
```

Organization directory MUST respect organization discovery policy。公开组织 DID 可解析不表示成员列表、官方 Realm 列表、服务拓扑或治理策略全文可公开。

### 8.5 搜索 Actor / Handle

```text
POST /_cokret/find/directory/search-actors
POST /_cokret/find/directory/search-users
POST /_cokret/find/directory/resolve-handle
POST /_cokret/find/directory/list-handles-for-subject
```

Actor / handle directory MUST NOT return pairwise DID、private DID、private handle、未披露的组织账号或仅因共同 Realm 推断出的关系。`search-users` 可用于 mention autocomplete / 成员添加候选；`resolve-handle` MAY 解析 handle 为 `subject` DID 与 `member_delivery_binding`，但只在 claim、audience、requester policy 和 Realm intent 验证通过时披露。`list-handles-for-subject` 用于已知 subject DID 时列出当前 context 可见 signed handle claims；它必须执行同样的 disclosure、issuer trust、audience 和 requester policy 过滤。Directory 返回的 `member_delivery_binding.recipient_service_did` 只是 join builder 输入，不能替代 Realm `delivery_binding` 或 grant 校验。

### 8.6 私密联系人发现

```text
POST /_cokret/find/directory/private-contact-discovery
```

该操作用于 `ck.private_contact_discovery.v1`。请求 MUST 使用 blinded / padded connection identifier batch，响应只返回 PSI set-membership 命中位图与最小 invite/consent handoff stub；MUST NOT 返回 time-bound reachability proof、原始 connection identifier、完整 profile、成员列表或关系图谱。

## 9. MIMI Provider Facade Surface（extension profile）

MIMI Provider Facade 不属于 v1 core service surface。完整定义见 [`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)（标记为 interop extension profile）。声称 v1 core 的实现 **不要求** 提供 `/_cokret/open/mimi/*` 路径；只有显式声明 `ck.profile.mimi_interop.v1` 的部署才暴露该子面。

## 10. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 Event，但服务层仍需要可查询面。

至少建议提供：

```text
GET /_cokret/self/authz/effective-grants?realm_id=<id>&subject=<did>
```

```text
GET /_cokret/self/authz/invites?realm_id=<id>&subject=<did-or-handle>
```

```text
POST /_cokret/self/authz/check
```

`check` 接口适合：

- Events API 接收写入前预检查
- sync service 分发前快速过滤
- client 发送前本地 UX 提示

## 10.1 Personal Agent Surface(CXP-0008 / CXP-0009)

Native personal agent 的 management 与 sidecar operations 落在 `/_cokret/self/agents/*` 与 `/_cokret/self/agent-sidecar-threads*`,pairing 与 session grant 复用 `/_cokret/gate/account/*`:

| Operation | HTTP binding | Profile |
| --- | --- | --- |
| `ck.agent.provision` | `POST /_cokret/self/agents` | `ck.profile.personal_agent_provisioning.v1` |
| `ck.account.agent_key_pair` | `POST /_cokret/gate/account/agent-key-pair` | `ck.profile.personal_agent_provisioning.v1` |
| `ck.account.issue_session_grant`(扩展为 `proof.proof_kind="agent_key_proof"` 分支) | `POST /_cokret/gate/account/session-grants` | `ck.profile.agent_auth.v1` |
| `ck.agent.list` / `ck.agent.get` | `GET /_cokret/self/agents` / `GET /_cokret/self/agents/{agent_principal_id}` | `ck.profile.personal_agent_provisioning.v1` |
| `ck.agent.pause` / `resume` / `deactivate` / `rotate_key` | `POST /_cokret/self/agents/{agent_principal_id}/{pause,resume,deactivate,rotate-key}` | `ck.profile.personal_agent_provisioning.v1` |
| `ck.agent.grant.attach` / `ck.agent.grant.detach` | `POST /_cokret/self/agents/{agent_principal_id}/grants` / `DELETE /_cokret/self/agents/{agent_principal_id}/grants/{grant_id}` | `ck.profile.personal_agent_provisioning.v1` |
| `ck.agent.sidecar_thread.ensure` | `POST /_cokret/self/agent-sidecar-threads:ensure` | `ck.profile.agent_sidecar_thread.v1` |

约束:

- 本 CXP 不引入 custom URI scheme(`cokret://` 等);所有 deep-link 由客户端用 deployment 已知的 `cokret_base_url` 拼接标准 HTTPS URL,移动端依赖 OS Universal Links / App Links。
- `pairing_request_id` 与 `approval_request_id` 都是 account/auth profile-local opaque UUIDv7 短期 artifact,不是 `ck:<kind>:<uuid>` 协议对象 id;agent runtime 收到 `approval_request_id` MUST NOT 解释成 URL 或尝试打开 UI,只能由 controller 的人类 session 带外查询。
- `{agent_principal_id}` 是 DID,在 URL path 中 MUST 按 RFC 3986 percent-encoding。

详细 wire 规则见 CXP-0008 §4 / CXP-0009 §4。

## 11. Realm Bootstrap Flow

Cokret v1 的首次加入流程：

1. 用户输入 handle、DID 或 Realm link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 DID Document 和 Realm policy 发现 Principal Server / identity registry / events / account / snapshot / blob / authz 服务
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 Realm metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk。**防投毒要求 (Snapshot Validation)**：由于 Sync Service 仍是服务节点，快照可能被恶意篡改。客户端 MUST 验证快照 manifest 的规范字段 `created_by`（即签发者 DID，与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 一致）、`created_at`、`authority_binding`、`signature`、`state_digest` (Merkle Root)、frontier 和每个 chunk digest。`signature` 的 signer 必须匹配 `created_by`，且 `authority_binding` 必须证明该 DID 在 `created_at` 时是 Realm owner、Realm policy 授权的 snapshot issuer 或 witness quorum 成员。high-assurance profile 下，`authority_binding.witness_attestations[]` 或等价 quorum proof 必须可验证；缺失时不得作为高保证 snapshot 使用。若校验失败，客户端 MUST 丢弃快照并回退到 `GET /_cokret/self/events?before=<cursor>`（`ck.events.query`）进行原始 Event 历史回放。
7. 从 frontier 之后拉取 backfill / sync stream 增量
8. 本地执行 reducer
9. 建立 read cursor、notification cursor 等个人状态

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
- **成本归属**：Realm 的整体数据大小、历史 Event 数量及附属的 Blob 存储成本，逻辑上必须绑定到 Realm 的 `owner` 或负责托管的 `responsible_actor_id`。
- **拒绝写入**：当 Blob 服务或 Principal Server 评估该 Realm 占用的资源已超出预设的 Policy 配额 (Quota) 时，MUST 返回明确的资源超限错误 (如 HTTP 413 或 402)，并拒收新写入的 Event 或大文件 Blob。

### 14.2 写频率控制 (Rate Limiting)
- Events API 和 Sync Service 节点 SHOULD 基于 `actor_id` 与 `realm_id` 实施严格的并发和频率限制。
- 对于来自未验证或低信誉 DID 的恶意刷写（例如短时间内进行海量无效的 `message.create` 或反复触发高并发图重组），节点有权暂时熔断该 DID 的请求。

## 15. 设计决定

Cokret v1 固定：

- 定义最小 principal server / identity registry / events / account / snapshot / blob / authz 服务面
- v1 core 互操作 transport 锁定为 HTTP/JSON（见 [`transport-bindings.md` §1](./transport-bindings.md)）；gRPC / WebSocket / SSE / MQ / libp2p 等其他 binding 仅为 extension profile，本节列出的 operation 形态与字段以 HTTP/JSON 为唯一权威。其他 binding 必须语义等价但不构成 v1 core 一致性。
- 写接口必须幂等
- DID 写入采用多 registry / witness receipt，而不是区块链
- bootstrap 必须覆盖 invite / grant / snapshot / backfill
- 服务必须公开 reducer / schema / feature profile
- 明确 Realm Owner 的资源记账责任与防滥用熔断标准

## 16. HTTP/JSON Binding

默认 HTTP/JSON binding 的具体路径、请求/响应形状、Blob 上传下载和标准错误码移至 `service-http-binding.md`。

`service-surface.md` 只定义服务角色和语义面。任何 HTTP、gRPC、WebSocket、SSE、message queue、libp2p 或 IPC 实现都必须映射到本文定义的等价语义。

## 17. 线级互操作要求

以下事项是 v1 的落地要求：

- Directory search result MUST 使用 `query-schema.md` 的分页、过滤和 `visibility_explanation` 约束；对不可见或不可枚举资源，错误形态 MUST 与不存在一致。
- Authz check response MUST 返回 `decision`、`matched_grants`、`applied_constraints`、`policy_results`、`missing_proofs`、`frontier` 和 `cache_expires_at`；`decision` 只能是 `allow`、`deny`、`quarantine`、`require_review` 或 `soft_fail`。
- Service describe MUST 声明 `service_did`、`trust_domain`、`service_type`、`protocol_version=1.0`、`supported_profiles`、`supported_operations`、`supported_bindings[]`、`supported_features[]`、`auth_metadata`、`limits`、`rate_limit_policy` 或 `rate_limit_policy_id`、`plaintext_visibility` 与 `development_mode`。其中 `supported_bindings[]` 是数组(每项描述一个 transport binding,例如 `{kind: "http_json", ...}`);单数字段名 `binding` 不出现在 describe response 顶层。客户端 MUST 拒绝 service DID、trust_domain、Realm policy 或 profile 不匹配的服务。`plaintext_visibility` 缺失视为该服务**不可信**用作 `plaintext_visible_services` 成员(见 OpenAPI ServiceDescribe schema description)。
- Service describe 响应 MUST 同时按 §3.0 区分 `supported_operations` / `implemented_features` / `claimed_profiles` / `verified_profiles` / `experimental_features` / `compat_surfaces` 六个 claim level 字段，schema 见 `ck.schema.service_describe.v1`。当 `development_mode=true` 时 `verified_profiles` MUST 为空；当 `development_mode=false` 且声明 `verified_profiles` 时，客户端仍 MUST 通过 `artifact_ref` / transparency log 获取并校验对应 cotest artifact、issuer 签名和 hash 后才把它作为生产 conformance 依据。
- Sync cursor recovery MUST 按 `conformance-vectors.md` 执行：cursor 是 opaque token；过期或缺口时返回可恢复错误，并提供 backfill 起点或 snapshot frontier。
- Event source consistency MUST 按 `conformance-vectors.md` 执行：重复 Event 幂等，冲突 Event 拒绝，event order、hash、签名和 `actor_seq` 必须可复现验证。
