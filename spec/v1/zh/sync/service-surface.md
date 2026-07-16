---
title: Service Surface And Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - service-http-binding.md
  - operations-sync.md
  - transport-bindings.md
  - federation.md
  - ../conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标（Goals）

如果只有对象模型、同步原则和 capability，而没有最小线级服务面，协议仍然很难真正互操作。

因此 Arkret v1 定义：

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

- 声明 Principal Server、identity registry、events、Sync Service、blob、capability 服务入口
- 声明服务 DID 或服务 endpoint

它不应直接塞入：

- 当前 grant 全量状态
- 当前 realm 当前态
- 大量通知或 inbox 数据

### 2.2 没有任何单一服务是唯一真相源

- signed Event 是 actor 发布和协作事实真相源
- Sync Service 是 Principal Server 上的受控同步入口
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

实际部署中的“服务器”是一个或多个服务面的组合，不是协议真相源。实现可以合并服务器，但每个 `ServiceDescribe` MUST 只描述一个逻辑角色，并明确该角色的 `service_type`、`supported_operations`、认证方式、限制、plaintext visibility 和 profile；不得把多角色聚合成一个 compound `service_type`，也不得把其它角色的 operation 或明文边界混入当前响应。多个角色共享同一 public binding 时，部署 MUST 为每个角色支持 `GET /_arkret/describe?service_type=<registered-id>` 的 role-scoped 响应；查询值、响应 `service_type` 和该角色的 DID/service binding 必须一致。查询省略规则和错误语义见 [`service-http-binding.md` §2.3](./service-http-binding.md)。

协议层统一使用 **Principal Server** 表示 principal 控制或委托的受控入口。登录与账号准入另有一个客户端可见的 **Account Authority** 角色：客户端从 Principal Server 的 `/_arkret/describe` 发现它，之后所有客户端可见的 `/_arkret/gate/account/*` 请求都只发往该 Account Authority。部署内部 S2S 子操作只可由 Account Authority 按对应 operation 契约调用，不能由客户端派生。不同部署形态的差异由 deployment profile、支持的 operation、是否内置 Auth / Account、Policy、Events API、Blob、Identity Resolution 等能力表达。

常见组合如下。这里的"需要"表示协议交互需要该能力存在，不表示每个用户都必须自建；个人和小团队通常只自建一个 Principal Server，其余基础设施可使用公共或托管服务。

*Table 2-1. 服务角色能力视图（informative）。REST namespace 的 canonical 单一来源是 [service-http-binding.md §2.1](./service-http-binding.md)；本表不重复 path 清单。*

| 实际服务器 | 普通部署建议 | 主要能力 |
| --- | --- | --- |
| Principal Server | 普通用户或组织自建的核心入口 | 用户/组织的受控入口、Event 提交/读取、account viewer / profile 自服务、client sync、联邦 transaction、invite locator / 私有 invite delivery、服务发现聚合、明文可见边界执行；其 describe MUST 发布 `auth_metadata.account_authority`。 |
| Identity Resolution Infrastructure | 普通用户默认使用公共服务或本地 method resolver；高安全或隔离网络才自建完整基础设施 | DID document、DID / KERI log、handle binding、receipt、witness、watcher、OOBI、service endpoint discovery。 |
| Account Authority | 个人部署通常与 Principal Server 同 origin；组织可由统一网关、Auth Server 或独立前置承载 | 账号准入、注册、session grant 签发 / 刷新 / 撤销 / 登出、device pairing、passkey/OIDC/SSO 结果换 grant、hard logout 内部编排。对客户端必须是单一 `gate_account_base`；内部 MAY 委托 Auth Server 与 Principal Server，并在 split Auth-side 时通过标准 `ak.gate.account.command.logout_auth_session` S2S 子操作终结 Auth-side session。 |
| Auth Server / method provider | 个人部署可内置；组织通常独立或接入 SSO / IdP | 认证仪式、浏览器登录上下文、passkey/OIDC/SSO、issuer / subject 校验；不得作为零散 `gate/account` operation 的客户端可见目标，除非它整体就是 Account Authority。 |
| Sync / Federation Server | 普通用户通常内置在 Principal Server | client sync、subscription、backfill、snapshot head、跨域 transaction、invite delivery、重放和 destination 绑定校验。 |
| Directory Server | 普通用户默认使用公共目录；组织发现或隔离网络才自建 | Realm/Organization/Actor/handle/Applet 的授权搜索和解析，私密联系人发现，最小披露发现。 |
| Blob / Media Server | 个人通常内置；文件量大或高安全组织可独立 | blob upload、authenticated download、HEAD、Range、thumbnail、preview、retention、media safety。 |
| Device / Key Server | E2EE profile 需要；个人通常内置在 Principal Server | to-device message、one-time key、fallback key、MLS KeyPackage claim、device list、encrypted key backup metadata / ciphertext。 |
| Authz / Policy Server | 个人可内置；共享 Realm 和组织治理建议独立 | effective grants、invite 查询、capability precheck、签名 policy decision、risk / quarantine。 |
| Push Gateway | 普通用户默认使用公共或托管推送；内网或高安全组织可自建 | push device register/unregister、脱敏通知投递、APNs/FCM/厂商推送适配。 |
| Applet Server | 集成/桥接/自动化可选 | applet describe、transaction、Ghost Actor、portal Realm、third-party lookup。 |
| MIMI Provider Facade | 与外部 MIMI provider 互通时可选；可由 Principal Server、notary service 或 Applet Bridge 承载 | MIMI provider discovery、room binding、key material、submit message、groupInfo、consent、identifier query、abuse report、proxy download。 |
| Agent Runtime Server | agent 场景可选但推荐 | agent 执行、tool 调用、A2A/ACP/MCP handoff；具体 service surface 由 `extensions/agent-*` 定义，通常通过 Events API 写回结果。 |
| Realtime Media Server | 通话/会议可选 | ICE config、TURN/STUN、SFU/MCU、录制策略、短期媒体凭证。 |
| Moderation / Compliance Server | 公共或组织部署建议独立 | report、审核队列或扩展审核入口、server ACL、policy list、appeal、legal hold / erasure workflow。 |
| Archive / Recovery Service | history sharing、late key recovery 或组织恢复场景可选；高安全部署必须显式声明 | Archive Node、Key Recovery Service 或 Recovery Service。只能按 Realm policy、history visibility、T0 membership 和 capability 返回最小必要 epoch material / backup envelope / recovery proof；不得因持有归档副本自动获得明文读取权。 |

REST namespace 第一段路径（`self` / `gate` / `root` / `find` / `peer` / `open` / `edge`，见 [service-http-binding.md §2.1](./service-http-binding.md)）是 **trust-surface classifier（信任面分类器）**，编码"调用方↔服务"的攻击面类别，**不是授权结论**；实现 MUST NOT 把信任面段本身解释为授权通过、安全级别达标或明文可见许可。每个 operation 仍按自身契约执行 session / capability / DID proof / Realm policy / history visibility / rate limit 校验。

#### 2.5.1 Account Authority 与认证方法发现

Principal Server 的根级 `/_arkret/describe` 是客户端登录 / account flow 的启动入口。`auth_metadata.account_authority` MUST 给出一个绝对 `gate_account_base`，客户端发起的 Arkret `/_arkret/gate/account/*` 请求都 MUST 从该 base 派生。客户端 MUST NOT 根据 operation 名称自行判断某个请求该打 Principal Server、某个请求该打 Auth Server；若 Auth Server 与 Principal Server 分进程或分 origin，部署 MUST 提供一个位于认证 TCB 内的 Account Authority 前置（网关、反代或同进程合并）完整承载该 base，并在内部按 operation 路由。`ak.gate.account.command.logout_auth_session` 是 Account Authority → Auth Server 的 S2S 子操作，普通客户端 MUST NOT 调用或从 `gate_account_base` 派生。

`auth_metadata.methods[]` 只描述认证方法（例如 `oidc`、`passkey`、`device_pairing`、未来 `gnap`）及其 provider / issuer / discovery，不决定 `gate/account` 的路由。OIDC method MUST 使用标准 discovery 与标准 `authorization_endpoint` / `token_endpoint`；Arkret 不定义 `/_arkret/gate/auth/oauth/*` 这类私有 OAuth endpoint family。标准认证结果进入 Arkret 的桥是 Account Authority 的 `POST {gate_account_base}/session-grants`，响应为 `SessionGrantOutcome`；Principal 本地 session provisioning 属 Account Authority 内部编排，不得暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

Account Authority 内部分派不得改变 operation 的协议身份。尤其 `ak.gate.account.command.pair_agent_key` 依赖 Principal Server 的 pairing record、Agent PCR Event acceptance 与 activation projection 时，split deployment MUST 将原始 typed request 委托到权威 Principal Server 的同一 `/_arkret/gate/account/agent-key-pair` binding，并保留 Event ID 幂等身份；不得把该职责改造成产品私有 `fanout` URL 或只入本地队列后向客户端报告成功。具体 commit 规则见 [`../identity/key-management.md` §3.6.1 / §3.6.2](../identity/key-management.md)。

本登录 / account flow 最多并存三类 origin：Principal Server（发现启动）、Account Authority（全部 `gate/account` Arkret 操作）和认证 method provider / issuer（标准认证协议）。完整 Arkret 客户端仍可按其它 spec 访问 Directory、Blob、Media、Push 等 service origin；这些不改变 account flow 的路由规则。

Deployment profile 的 canonical 机器真源是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `deployment_profiles` 集合；本文不得另注册 profile id。下列形态仅是服务角色组合说明，实际部署 MUST 声明 canonical id（如 `ak.profile.personal_node.v1`、`ak.profile.organization.v1`、`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1`）并按 profile registry 校验能力面：

- 个人节点可把 Principal Server、Events API、Sync/Federation、Blob、Device/Key 与 Authz 合并到同一 trust domain，并使用公共 Directory、Push 或 TURN/Media 服务。
- 组织节点通常把 Principal Server 与 Auth Server、Policy/Authz、Blob/Media、Directory、Push 等服务按规模和合规边界拆分。
- 高安全或主权部署把 Principal、Identity Resolution、Auth、Directory、Policy/Authz、Events/Blob、Sync/Federation 与 Audit/Compliance 保持在受控 trust domain 内；公共 Directory、Push 或外部 federation ingress 只能作为显式授权的互联入口。
- Applet、MIMI facade、Agent runtime、Moderation、Archive/Recovery 等角色是 service role / capability 组合，不是 deployment profile id；它们只能在已声明 profile 允许的 namespace、capability、Realm policy 与 service describe 范围内工作。

客户端选择服务时 MUST 先解析 DID Document 与 Realm policy，再校验 `server/describe`。不得因为多个服务位于同一域名，就默认它们拥有相同权限或相同明文可见范围。

## 3. 通用服务描述接口

所有网络可发现服务 MUST 提供：

```text
GET /_arkret/describe
```

*Example (informative). `/_arkret/describe` 响应示例，字段权威定义以 schema 为准。*

```json schema=schemas/service-describe.schema.json
{
  "service_id": "did:webvh:zCm2ZfnfjnNcgaUrSkWyf5UtD:alice.example.net",
  "trust_domain": "ak:trust_domain:did.webvh.alice.example",
  "service_type": "principal_server",
  "protocol_version": "1.0",
  "supported_profiles": [
    "ak.profile.principal_server.v1"
  ],
  "supported_operations": [
    "ak.server.query.describe",
    "ak.self.events.command.submit",
    "ak.self.events.query.scan",
    "ak.peer.events.command.submit",
    "ak.peer.events.query.scan",
    "ak.peer.events.query.resolve",
    "ak.peer.events.query.frontier",
    "ak.peer.invites.command.submit",
    "ak.peer.snapshot.query.manifest_head",
    "ak.open.invite_locator.query.resolve",
    "ak.self.account.query.viewer",
    "ak.self.account.command.update_profile",
    "ak.self.account.stream.subscribe"
  ],
  "supported_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://alice.example.net"
    },
    {
      "kind": "tus",
      "base_url": "https://alice.example.net/_arkret/self/blob/resumable",
      "operations": ["ak.self.blob.upload.create"],
      "extension_profile_required": null,
      "tus_version": ["1.0.0"],
      "tus_extensions": ["creation", "creation-with-upload", "checksum", "expiration", "termination"]
    }
  ],
  "supported_features": [
    "sync_stream",
    "snapshot",
    "invite_addressing",
    "notifications",
    "ak.feature.blob.resumable_upload.tus.v1",
    "ak.feature.realm_key.peer_relay.v1",
    "ak.feature.realm_key.backup_retrieval.v1",
    "ak.feature.realm_key.archive_retrieval.v1",
    "ak.feature.mls_exporter_aead.v1"
  ],
  "x_invite_addressing": {
    "supported_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim",
      "same_principal_server",
      "explicit_address"
    ],
    "recommended_introduction_kind": "locator_ref",
    "handle_claim_default_behavior": "quarantine",
    "explicit_address_default_behavior": "quarantine"
  },
  "receive_policy_constraints": {
    "policy_version": "2026-06-21",
    "applies_to": ["invite_delivery", "contact_request"],
    "permitted_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim"
    ],
    "handle_claim_max_behavior": "quarantine",
    "explicit_address_max_behavior": "drop",
    "allowed_handle_domains": ["alice.example.net"]
  },
  "auth_metadata": {
    "account_authority": {
      "origin": "https://alice.example.net",
      "gate_account_base": "https://alice.example.net/_arkret/gate/account",
      "enrollment_authority_did": "did:key:z6MkenrollmentAuthority"
    },
    "methods": [
      {
        "method": "oidc",
        "issuer": "https://auth.example.com",
        "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
        "client_id": "ak.example-client",
        "scopes": ["openid", "profile"],
        "grant_exchange": {"proof_kind": "oidc_code_exchange"}
      },
      {
        "method": "passkey",
        "grant_exchange": {"proof_kind": "passkey_assertion"}
      }
    ],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  },
  "limits": {
    "max_body_bytes": 1048576,
    "max_events_per_batch": 100,
    "device_message_max_ttl_seconds": 86400,
    "read_cursor_debounce_ms": 1000,
    "dangling_redaction_min_retention_days": 30,
    "snapshot_retention_heads": 2,
    "resumable_upload_incomplete_ttl_seconds": 86400
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
        "operation_id": "ak.self.events.command.submit",
        "rate_limit_scope": ["service_id", "realm_id"],
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
      "profile_id": "ak.profile.principal_server.v1",
      "claim_kind": "self_claimed",
      "claimed_at": "2026-05-02T00:00:00Z"
    }
  ],
  "verified_profiles": [
    {
      "profile_id": "ak.profile.core_event_store.v1",
      "claim_kind": "conformance_verified",
      "verification_run_id": "verify-2026-05-02T000000Z",
      "artifact_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "artifact_ref": "https://verifier.example/log/verify-2026-05-02T000000Z",
      "verifier_did": "did:webvh:zC72cg8H1bJUTB6ZngzxP68BJ:verifier.example",
      "signature": "base64url:...",
      "timestamp": "2026-05-02T00:00:00Z"
    }
  ],
  "experimental_features": [],
  "compat_surfaces": [],
  "development_mode": false
}
```

能力发现示例（normative 指引）：客户端判断服务端是否支持某项**可选传输能力**时，MUST 以 describe 的 `supported_features` / `supported_bindings` / `limits` 为权威发现面，而不是对猜测 endpoint 直接探测。以可续传 Blob 上传为例，服务端支持时 MUST 同时声明 `supported_features` 含 `ak.feature.blob.resumable_upload.tus.v1`、`supported_bindings` 含一条 `kind="tus"` 的 binding，并在 `limits` 暴露续传上限；客户端据此发现后再用 tus `OPTIONS`（`Tus-Resumable` / `Tus-Version` / `Tus-Extension`）做 endpoint 级线上确认。完整 binding 语义、内容寻址不变式与隐私约束见 [`crypto-media/media-and-blob.md` §2.1](../crypto-media/media-and-blob.md)。

本规范登记的标准 `supported_features` 还包括：`ak.feature.realm_key.peer_relay.v1`（中继 to-device `ak.realm_key.request`）、`ak.feature.realm_key.backup_retrieval.v1`（托管 `mls_history` key backup unlock）、`ak.feature.realm_key.archive_retrieval.v1`（archive node 历史 key 取回）、`ak.feature.mls_exporter_aead.v1`（接受并同步 `content_scheme=mls-exporter-aead-v1` Realm；见 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.10）与 `ak.feature.agent_runtime_approval_notifications.v1`（通过 account subscribe 的闭合 notification delta 投递 Agent runtime 审批；见 [`client-sync.md` §3.1](./client-sync.md)）。客户端依赖这些能力时 MUST 以 describe 声明为准，未声明时 fail closed 或选择规范明确允许的 fallback。

服务类型命名规则：

- DID Document `service.type` 使用协议注册名，例如 `ArkretPrincipalServer`、`ArkretDirectory`。
- describe 响应的 `service_type` 使用 [`service-type-registry.json`](../../artifacts/registry/service-type-registry.json) 中 `status=active` 且 `valid_in` 包含 `service_describe` 的小写注册值；正文不复制该闭集。其它 context 的值不得进入 Describe：例如 `mimi_provider_facade` 只用于 `mimi_provider_directory` descriptor，不是 `ServiceDescribe.service_type`。`sync_node` 同时被 registry 允许用于 Realm sync endpoint / join candidate，但只有当 Realm policy 授权对应 submission / delivery binding 时才能用于这些 Realm 字段（见 [`realm-join-candidate.schema.json`](../../artifacts/schemas/realm-join-candidate.schema.json)）。
- conformance profile 使用 `ak.profile.*` 标识，例如 `ak.profile.principal_server.v1`。
- 实现 MUST 区分这三层名称，不得把 DID service type、运行时 service_type 与 conformance profile 混用。

### 3.0 Describe response claim levels

`server/describe`（以及结构等价的 `identity/describe` / `events/describe` / `sync/describe` /
`directory/describe` / `applet/describe`）响应 MUST 使用同一个 canonical `ServiceDescribe` shape。除 `service_id`、`trust_domain`、`service_type`、`protocol_version`、`supported_profiles`、`supported_operations`、`supported_bindings`、`supported_features`、`auth_metadata`、`limits`、`plaintext_visibility` 和 `rate_limit_policy` / `rate_limit_policy_id` 之外，响应还 MUST 按 **claim level** 区分以下字段；schema 见
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)（`ak.schema.service_describe.v1`）：

当 `service_type=directory_service` 时，`ak.find.directory.query.describe` 还 MUST 按 [`discovery-directory.md` §8.9](../discovery/discovery-directory.md#89-akfinddirectoryquerydescribe-扩展) 暴露已登记在 `ServiceDescribe` schema 中的 directory-specific 裸字段（例如 `resource_types[]`、`discovery_profiles[]`、`ingest_modes`、`accept_policy_kind`、TTL 与 `rate_limits` 字段）；这些字段不是 vendor-specific `x_*` 扩展。

- `supported_operations: operation_id[]` — 该 endpoint 可被实际调用的 operation_id。仅表示 wire 可达，
  不构成 profile claim。元素 SHOULD 命中 `operation-registry.json` 注册项。
- `trust_domain: ak:trust_domain:<scope>` — 部署级 replay boundary。客户端 / 接收方 MUST 要求它与 Realm create-locked trust domain、federation header 和本地 receive context 一致；不一致时不得接受 replay-sensitive proof。
- `implemented_features: feature_id[]` — 服务有实现代码、但 **不一定** 通过 conformance verification 的 feature。
  构建 conformance matrix 的工具 MUST 把它视为严格弱于 `claimed_profiles`。
- `claimed_profiles: [{profile_id, claim_kind: "self_claimed", ...}]` — 服务自声明加入的 profile。
  `claim_kind` 当前固定为 `self_claimed`；Conformance Verifier 验证结果 MUST 改写到 `verified_profiles`，不得复制到本字段。
- `verified_profiles: [{profile_id, claim_kind: "conformance_verified", verification_run_id, artifact_digest, artifact_ref, verifier_did, signature, timestamp, expires_at?}]` —
  附带 verification run 标识、artifact hash、artifact 获取位置或 transparency-log 引用、verifier DID、签名与验证时间戳的已验证 profile。签发主体是中立角色 **Conformance Verifier**（定义见
  [`conformance-suite.md`](../conformance/conformance-suite.md) §6.2）。**约束**：当 `development_mode=true`
  时，本数组 MUST 为空——dev / placeholder proof 路径不得用来宣告生产 conformance（见本节 §3.0）。
- `experimental_features: feature_id[]` — 服务暴露但不承诺稳定互操作的 feature；客户端 MUST NOT
  把它当成协议级决策的依据，也不得继承到 `claimed_profiles`。
- `compat_surfaces: [{name, kind, ...}]` — Arkret v1 conformance 之外的 external interop surface
  （`kind` ∈ {`matrix_passthrough`, `mimi_passthrough`, `external_interop`}）。
  这些 surface **不构成** Arkret v1 conformance 的一部分。
- `development_mode: boolean` — 必填；为 `true` 时 `verified_profiles` MUST 为空。省略不是 false，SDK / conformance tooling MUST 把缺失视为 invalid describe。
- `egress_network_policy` — 可选的出站网络策略摘要。会解析 DID、联邦 peer、媒体、snapshot、Policy Server、Webhook、Applet 或 Agent endpoint 的服务 SHOULD 暴露粗粒度策略；完整 SSRF 防护语义见 [`api-conventions.md`](./api-conventions.md) §11.2。
- `receive_policy_constraints` — Principal Server 可选的部署 / 管理员级接收策略上限。它约束 `ak.peer.invites.command.submit` 与 `ak.peer.contacts.command.submit` 对 `locator_ref`、`handle_claim`、`explicit_address` 等 introduction evidence 的处理；客户端 MUST 把它渲染为“服务器约束”，不得把它当作 subject 自愿公开。语义见 [`invite-addressing.md`](./invite-addressing.md) §5.2。

实现 MUST 明确区分 endpoint 可达性、feature 实现、profile claim 与 conformance verification：

1. 在 describe 响应中同时输出上述 claim-level 字段。
2. dev / placeholder posture 下，自检 `verified_profiles == []` 并在初始化时 fail closed。
3. conformance 报告工具与 admin 等下游 MUST 按 claim level 渲染不同 badge：`self_claimed`、`conformance_verified`、
   `experimental`、`compat`、`not_claimed`。
4. 客户端不得只信任服务自报的 `verified_profiles`；使用生产 conformance 结论前 MUST 通过 `artifact_ref` 或等价 transparency log 取得 verification artifact，校验 `artifact_digest`、`verifier_did`、`signature`、时间戳和可选 `expires_at`。

`plaintext_visibility.data_classes` 是机器可判定的明文类别白名单。`event_kinds`、`payload_paths`、`blob_purposes` 和 `projection_outputs` 只是进一步缩小或解释范围，不能替代 `data_classes`；`notes` 只供人读。Realm policy 的 `plaintext_visible_services[].data_classes` MUST 是目标 `ServiceDescribe.plaintext_visibility.data_classes` 的子集，且 `visibility` 不得高于 `max_visibility`。若 describe 缺失 `data_classes` 或只给出自由文本 `purposes`，客户端 / reducer MUST 把它视为不能接收私有明文。

### 3.1 Identity Resolution Surface

Identity Resolution Surface 是 DID method resolver、registry、witness、watcher 或 method-specific verifier 的统一抽象。`did:plc` 可以由 PLC directory、mirror 或 audit source 实现；`did:web` 可以由 HTTPS / DNS resolver 实现；`did:webvh` 可以由 DID log、watcher 和 witness 实现；`did:key` 可以只由本地 resolver 实现，不需要网络 API；`did:keri` 可以由 KERI log、witness、watcher 和 OOBI discovery 实现。

网络型 identity registry 至少应提供以下语义：

#### 3.1.1 描述 registry

```text
GET /_arkret/root/identity/describe
```

返回：

- `service_id`
- `registry_mode = writer | witness | replica`
- 支持的 receipt 类型
- 当前软件版本与实现 profile

#### 3.1.2 获取当前 DID Document

```text
GET /_arkret/root/identity/document?did=<did>
```

返回 SHOULD 包含：

- 当前 materialized DID Document
- 当前 `head_event_digest`
- 当前 `seq`
- 可选 witness receipts

#### 3.1.3 获取 DID 日志

```text
GET /_arkret/root/identity/log?did=<did>&cursor=<cursor>&limit=<n>
```

用于：

- 审计
- 重建 DID Document
- 验证 `key_log` 与 registry head 一致

默认情况下，返回的每个 log entry MUST validate as `did-key-log-entry.schema.json`：`seq=0` 表示 inception 且不得携带 `prev_event_digest`；`seq>0` 必须携带 `prev_event_digest`，并且该值必须等于前一条 accepted entry 的 `head_event_digest`。`operation` 是规范化操作 kind；DID-method-specific 原始操作对象放在 `operation_body`，不得使用通用 JSON Patch 形态。

generic 形态的 digest、hash chain 与 proof transcript 的唯一规范定义在 [`../identity/identity-did.md` §4.4](../identity/identity-did.md)。本 transport surface MUST 原样返回符合该节与 `did-key-log-entry.schema.json` 的 entry，不得删除 proof binding 的 `context` / `seq`，也不得另定义 transport-specific transcript。

- Verifier 顺序固定：先重算并 constant-time 比对 `head_event_digest` 与 `proof.payload_digest`，再构造 binding object 并验证 detached JWS；任一步失败 MUST 拒绝该 entry 及其后续链段。实现 MUST NOT 用字段拼接字符串、裸 hex 或任何非 canonical JSON 形态替代上述 transcript。
- 签名者授权：`proofs[]` 的 `verification_method` MUST 按该 DID method 的原生控制规则验证；不得把“上一 entry 的 key 验下一 entry”当成通用规则。`seq=0` 由该 entry 声明的 cold identity root 自签。对启用 pre-rotation 的 did:webvh，entry N 的 proof 必须由 **entry N 当前显式 `updateKeys`** 验证，且当前 key 的 canonical multikey hash 必须命中 entry N-1 的 `nextKeyHashes`；省略当前 `updateKeys`、沿用 previous key、复用 spent key均拒绝。其它 method 依其注册 adapter 的 update/recovery 规则。registry host MUST NOT 以自身 key 代替 controller 签名；registry / witness 对 head 状态的背书走 identity receipt，不进入 entry `proofs[]`。

did method 原生日志有更强互操作格式时 MAY 直接返回该 method 的原生 accepted log entry，例如 `did:webvh` 的 Data Integrity proof 日志；这种服务 MUST 在 `describe.experimental_features[]` 中声明对应 feature id（例如 `ak.feature.identity.webvh_native_log.v1`），并且 `operation_body` / proof 语义 MUST 可按该 DID method 的规范重建同一 DID Document head。未声明该 experimental feature 的 `ak.root.identity.log.query.list` 响应仍 MUST 使用 `did-key-log-entry.schema.json`。

#### 3.1.4 提交 DID 更新

```text
POST /_arkret/root/identity/submit-did-operation
```

请求体 SHOULD 包含：

- `did`
- `did_method`
- `operation`
- `seq` / `prev_event_digest`（当 DID method 暴露 key-log 序号或 head hash 时）

要求：

- `did_method` 不含 `did:` 前缀，且 MUST 与 `did` 的 method component 逐字节相等；不支持该 method 的 registry MUST fail closed，不得把它转交给通用 JSON handler。
- `operation` 是完整、不可变的 DID-method-native 原始操作对象，并且包含该 method 要求的 controller / update / recovery proof；实现 MUST NOT 把 DID 更新降格为通用 JSON Patch，也不得在 wrapper 外另造一套 method-neutral 授权 proof。transport bearer、mTLS、session 或部署凭据只负责通道准入，不能替代 method-native control proof。
- `seq` / `prev_event_digest` 仅是调用方给出的乐观并发条件。若提供，adapter MUST 将其与从 native operation / accepted history 推导的 sequence 与 previous head 精确比对；不得用 wrapper 值覆盖或修补已签名 operation。
- registry policy、trust roots、witness threshold 与审计上下文 MUST 来自服务端配置和已验证状态，不得由 caller-supplied `policy_context` 决定授权。
- 相同 DID method operation id / seq / canonical operation bytes 的重复提交 MUST 返回 `duplicate` 且不追加第二条 history；相同 operation id / seq 但 canonical bytes 不同、previous head stale、或同一 previous head 产生 sibling candidate 时 MUST 以 conflict fail closed，并保留可审计分叉证据（若实现支持 quarantine），不得覆盖 accepted head。
- registry MUST 从已验证 genesis 开始验证完整 method-native 授权链。did:webvh adapter 必须逐 entry 验证当前显式 `updateKeys`、上一 entry `nextKeyHashes` commitment、SCID/hash chain、`state.id` 与 spent-key 永不复用；不得以 previous-key 签名或缺失字段继承替代。
- 所有 method-native proof 与 CAS 检查 MUST 在持久化 DID Document、log entry、receipt 或 cache 之前完成；失败不得产生部分写入。

#### 3.1.5 获取 receipt / witness 证明

```text
GET /_arkret/root/identity/receipts?did=<did>&head=<event-hash>
```

#### 3.1.6 写入确认建议

Arkret v1 要求：

- writer 客户端同时向多个 registry / witness 提交 `did_operation`
- 至少拿到 `k-of-n` receipt 才视为提交成功
- 读取时可附带 `expected_head` 或 `min_seq`

这让 DID 写入仍然是普通网络请求，而不是全网区块共识。

## 4. Events API

Events API 是 Principal Server 提供的 signed Event 提交、读取、回填和前沿查询接口。普通部署 SHOULD 由 Principal Server 直接暴露 `/_arkret/self/events/*`。

Arkret v1 不规定 Event 在服务端的物化形态——不要求集中式 record 仓库、提交日志或仓库命名接口。Principal Server 可以托管、复制或索引 Event,但接收方仍必须验证 Event 签名、DID 控制链、canonical hash、`actor_seq` 路径递增、`prev_refs` 与 `refs[role=authorized_by]` 因果依赖和 `event_id` 幂等性。

Events API 至少应提供以下语义：

### 4.1 描述 Events API

```text
GET /_arkret/self/events/describe
```

返回：

- `service_id`
- 支持的签名算法
- 支持的 Event schema / reducer profile
- 支持的 actor frontier、Realm frontier、resolve 和 stream/backfill 能力

### 4.2 提交 Event

```text
POST /_arkret/self/events
```

请求体是一个 Event Envelope，或 profile 明确允许的 Event Envelope 数组。

要求：

- 同一个 `event_id` 重复提交相同 canonical bytes MUST 幂等成功。
- 同一个 `event_id` 若内容不同 MUST 拒绝并记录冲突。
- 服务 MUST 验证 Event 签名、actor DID、device/session、capability、Realm policy、`actor_seq` 和因果依赖。
- 服务 SHOULD 返回 accepted event、当前 actor frontier、Realm frontier 以及 read-your-writes barrier `cursor`（schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)，purpose=`barrier`）。

批量提交的处理顺序、依赖可见性、frozen authorization basis 与 partial-accept 原子边界统一以 [`operations-sync.md` §5](./operations-sync.md) 为准；本 surface 只声明该 operation 属于 Events Surface。

### 4.3 获取单个 Event

```text
GET /_arkret/self/events/{event_id}
```

不可见或不存在的 Event MUST 使用统一 `not_found` 语义，除非调用方有审计/管理权限。

### 4.4 批量获取 Event

```text
POST /_arkret/self/events/resolve
```

请求体可携带一组 `event_ids` 或 `event_digests`。响应按 Realm policy、history visibility、E2EE envelope policy 和 redaction policy 过滤 payload。

### 4.5 列出 / 回填 Event

```text
GET /_arkret/self/events?actors=<did>&realms=<id>&before=<cursor>&limit=<n>    # 历史 backfill
GET /_arkret/self/events?actors=<did>&realms=<id>&after=<cursor>&limit=<n>     # catch-up
```

参数完整定义与"近邻先返回"默认顺序规则见 [`service-http-binding.md` §3.3](./service-http-binding.md)。

用于：

- actor 历史恢复
- Realm 审计回放
- 补齐缺失 Event
- 从 snapshot frontier 后继续 reducer replay

### 4.6 获取 Event frontier

```text
GET /_arkret/self/events/frontier?actor_id=<did>
GET /_arkret/self/events/frontier?realm_id=<id>
```

返回调用方可见范围内的 actor frontier、Realm frontier、latest HLC、可选 witness receipt / event batch receipt。frontier 只用于同步和强一致读取，不能替代 Event 集合本身。

## 5. Account Aggregate / Snapshot Surface

Account Aggregate / Snapshot Surface 是 Principal Server 提供的 **账号视角聚合** 能力 + snapshot 入口。逐 Realm 的事件查询和实时订阅走 Events Surface（`ak.self.events.query.scan` / `ak.self.events.stream.subscribe`，见 `service-http-binding.md` §3.3 / §3.4）。该 surface 不是独立第三方服务器角色，本质是 Principal Server 上聚合多 Realm frontier、to_device、account_data、device_lists 与 presence 的视图。客户端只应使用本 principal 控制/委托的 Principal Server、对方 principal 控制/委托的 Principal Server，或 Realm policy 明确列出的 shared notary / Sync Service。

本节定义 account 与 snapshot 两类操作（事件流读取请到 Events Surface）：

- `GET /_arkret/self/account/viewer`：当前 holder 的账号主体自读（`ak.self.account.query.viewer`）。响应使用 signed handle claim / ref / digest，不把未签名裸 `handle` 作为账号权威字段。
- `POST /_arkret/self/account/profile`：当前账号 profile 更新（`ak.self.account.command.update_profile`）。patch 路径仅限 `display_name`、`avatar_blob_ref`、`profile_fields.<key>`；字段语义以 [`profiles-presence.md` §2.2](../discovery/profiles-presence.md) 为准。
- `GET /_arkret/self/account/subscribe`：客户端账号视角聚合同步（`ak.self.account.stream.subscribe`），见 `client-sync.md`。
- `GET /_arkret/self/account/describe`：account aggregate service describe（`ak.self.account.query.describe`）。
- `POST /_arkret/self/account/cursor/revoke`：撤销账号聚合订阅 cursor（`ak.self.account.command.revoke_cursor`）。
- `GET /_arkret/self/snapshot/head`：snapshot manifest 入口。

`ak.self.account.command.update_profile` 不隐式替代 directory 或 cross-device account-data fan-out。实现若仍需维持可发现性或跨设备头像/简介同步，必须显式调用 `ak.find.directory.command.announce`、`ak.account_data.set` 或等价已声明 operation。

事件流读取统一在：

- `GET /_arkret/self/events?realms=...&before=...` 或 `&after=...`（`ak.self.events.query.scan`，双向 cursor；`before` 取历史方向，`after` 取未来方向。详见 [`service-http-binding.md` §3.3](./service-http-binding.md)）
- `GET /_arkret/self/events/subscribe?realms=...&catchup=...`（`ak.self.events.stream.subscribe`，可从 `after=` 追赶到当前 frontier，并支持多 realm 一次订阅）

实现不得把账号聚合 (`/_arkret/self/account/subscribe`) 和裸事件读 (`/_arkret/self/events`) 合并成语义不明的单一“stream”接口；它们的 selector、auth、frame schema、freshness 行为都不同。其他 transport MAY 使用不同帧名，但必须映射到上述 canonical operation。

### 5.1 Account 自服务与描述

```text
GET /_arkret/self/account/viewer
POST /_arkret/self/account/profile
GET /_arkret/self/account/describe
POST /_arkret/self/account/cursor/revoke
```

### 5.2 snapshot 入口

```text
GET /_arkret/self/snapshot/head?realm_id=<id>
```

用于拿到当前推荐 snapshot manifest：响应即完整 `ak.schema.snapshot.v1` manifest（不含 chunk bytes），chunk bytes 经 manifest `chunks[].chunk_ref` 走 blob surface 获取。v1 的 `snapshot` namespace 仅 `ak.self.snapshot.query.manifest_head` 一个 canonical operation；snapshot manifest 与 chunk 的防投毒校验流程见 §11。无法产出真实签名 manifest 的部署 MUST NOT 宣告本操作并 MUST 返回 `not_implemented`，不得伪造证明字段。

### 5.3 Event / Seal 状态与 Bottom 暴露

Sync 响应 SHOULD 在每条 reducer-input Event 上携带其当前协议状态字段（`event_state`），取值与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §13 失败状态表一致：`data_local` / `data_observed` / `control_pending` / `control_sealed` / `failed_precondition` / `failed_plane` / `failed_bottom` / `rejected_seal` / `fork_quarantine` / `stale_seal_ref`。

State query / projection 响应 MUST 在 cell 当前 join 值为 ⊥ 时返回结构化 Bottom 诊断，schema 参见 [`schemas/bottom.schema.json`](../../artifacts/schemas/bottom.schema.json) 与 `ak.schema.bottom.v1`：

```json
{
  "cell": "ak:cell:ak.component.realm.policy.v1:ak:realm:0196419b-0000-7000-8000-000000000000",
  "status": "bottom",
  "bottom": {
    "kind": "conflict",
    "cells": ["ak:cell:ak.component.realm.policy.v1:ak:realm:0196419b-0000-7000-8000-000000000000"],
    "event_ids": [
      "ak:event:84210000-0000-7000-8000-000000000000…",
      "ak:event:a5294000-0000-7000-8000-000000000000…"
    ],
    "basis": {
      "leaves": ["ak:seal:sha256:dddd…"],
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
- `event_state="fork_quarantine"` 表达控制面 Seal 分叉已被证明；UI 与自动化 MUST 停止基于该 fork 的普通治理 allow，直到 recovery path 给出新的 sealed basis。
- `bottom_escalation_after_ms` 超时后服务端 MUST 在 `bottom.escalated_at` 标记，并向 admin / recovery governance 渠道带外通知；超时本身不自动选 winner。

`/_arkret/self/account/subscribe` / `/_arkret/self/events` 响应 MUST 在文档化字段位置嵌入上述 `bottom` 对象（精确 wire 形态见 [`bottom.schema.json`](../../artifacts/schemas/bottom.schema.json)；HTTP 字段位置以 [`service-http-binding.md`](service-http-binding.md) 与 OpenAPI 为准）。

### 5.4 明文与服务信任

如果 Realm 未启用 E2EE 或内容层加密：

- 客户端 MUST NOT 将 message body、comment body、附件明文或可逆派生摘要提交给未授权第三方服务。
- `events`、`sync`、`sync/subscribe`、`sync/backfill` 的服务端必须是 principal DID、Organization DID 或 Realm policy 明确委托的 Principal Server。
- Directory、Push Gateway、Blob preview、Policy preview，以及任何协议外 search / projection 服务，若会接收正文、正文摘要、附件预览、全文索引或可逆派生内容，MUST 在 Realm policy 中声明为 `plaintext_visible_services`。
- shared notary / Sync Service 若可见明文，必须在 Realm policy 中作为明文可见方列出。
- `encryption_profile="none"` 只说明 content 未使用 E2EE；它不自动授权任意服务保存、索引、导出或生成可逆派生内容。只有 Realm 同时把内容声明为 public content（例如 `history_visibility=world_readable` 且 preview / export policy 允许 public processing）时，服务才 MAY 按公开内容处理；否则仍按私有明文执行 `plaintext_visible_services` 检查。
- 接收方 Principal Server 可以看到投递给该接收方的非加密内容；客户端和 Realm policy MUST 把这视为内容可见边界，而不是透明中继。
- 非受信服务只能接收公开内容、密文 envelope 或不可解析 payload。

## 6. Search / Projection Semantics

Arkret v1 不定义必需的远端索引或应用视图服务面。当前态查询、View projection、inbox、notification 和全文搜索默认属于客户端或 SDK 的本地派生能力；客户端可以根据已同步且已授权、已解密的 Event 集合自行维护本地索引，也可以完全不提供搜索功能。

实现 MAY 提供协议外或扩展 profile 的受托 search / projection 服务，但该服务不是核心协议角色。任何此类服务都不得成为真相源；其输出必须能追溯到 signed Event、reducer profile、View definition 和 causal frontier。

### 6.1 结构化查询形状

若客户端、SDK 或可选受托服务对外暴露可互操作查询语义，SHOULD 复用 `query-schema.md` 中的 Query 形状：

- `object_types`：标准对象类型，例如 `realm`、`space`、`strand`、`message`、`morph`（Space 通过 `space.kind` 区分 board/list/...；Strand 默认入口通过 track primary 解析规则得到）
- `morph_types`：当 `object_types` 包含 `morph` 时，可进一步限定开放对象类型
- `facets`：schema-declared capability hint 选择器，只用于 Morph 或声明支持 facets 的标准对象；不得作为授权、状态机、排序或 reducer 语义的唯一来源
- `relation`
- 过滤条件
- 排序
- cursor
- limit
- `view_id`、`projection` 与 `renderer`：非 raw projection SHOULD 使用核心原语 `collection` / `timeline` / `graph` / `document` / `composite`；例如看板展示使用 `projection="collection", renderer="board"`。
- barrier `cursor`：可选。若实现支持读己之所写等待，则必须把等待条件绑定到本地已知的因果前沿，例如特定 `event_id` / event hash / Realm frontier。Wire 形态与 stream cursor 共享 `ak:cursor:<base64url>`，由内部 `purpose` 字段区分（见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 与 [`api-conventions.md` §7](./api-conventions.md)）。

barrier cursor 在 Query / Projection 语义中是读己之所写 barrier，不是 Client Sync 的 stream cursor / `after=` resume token。实现 MAY 把它编码为 opaque token，但内部 MUST 绑定调用方、`realm_id`、目标 `event_id`、event hash、filter / query hash、服务 DID 和过期时间。Projection 服务收到该 cursor 时，应等待本地可验证 frontier 覆盖目标事件；若等待超时返回 `timeout`，若服务本地 frontier 明确落后返回 `stale_frontier`，若服务暂时无法追赶或不可用返回 `temporarily_unavailable`。Client Sync 仍必须只使用 [`client-sync.md`](./client-sync.md) 定义的 stream cursor 作为 `/_arkret/self/account/subscribe after=`。

### 6.2 Strand Discussion / Context Projection

Strand context timeline、Strand discussion timeline 和 Strand context projection 是客户端展示形态，不要求远端 endpoint。无论在客户端本地还是受托服务中执行，Strand 的所有 track 都按 Strand 的 effective scope 执行 membership / history visibility 检查：`Strand.scope_circle_id=null` 时按父 Realm；`scope_circle_id` 指向 [Circle](../models/circle.md) 时按该 Circle 自身 policy 与 membership 独立裁剪。Synthesis 与 discussion 同 scope，可见性同源。不得因为 Strand 在某 scope 可见就授予其他 scope 或 Board/List 或其他 Realm 对象权限。

### 6.3 Inbox / Notification Projection

Inbox 和 notification 可以由客户端从本地 Event、read cursor、mention Relation、assignment Relation 和 actor-private account data 派生。若受托服务生成 inbox preview、通知摘要或可逆派生内容，必须满足本节明文边界。

### 6.4 全文搜索

全文搜索是可选功能。请求形状 MAY 使用：

```json
{
  "query": "legal review",
  "realm_ids": ["ak:realm:0196419b-0000-7000-8000-000000000000"],
  "object_types": ["message", "strand", "morph"],
  "morph_types": ["comment"],
  "sender_actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
  "matches": [
    {
      "rank": 0.95,
      "object": {"_comment": "<Object 当前态 — 与 ak.objects.* 返回形态相同>"},
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
- Public plaintext Realm 的搜索 / preview 服务仍 MUST 区分 `directory_card`、`stripped_state`、`history_stub` 和 `history_snippet`；history snippet 只能在 `ak.realm.preview_policy` 或等价 public export policy 允许时生成，不能从 `discoverability=public` 推导。
- Search / projection 输出不得扩大可见性；查询结果、通知、搜索命中和 preview 都必须受底层 Realm policy 与 capability 约束。

服务端强制边界：

- Events / Sync / Federation / Push / Blob preview，以及任何受托 search / projection 服务在接收包含明文或可逆派生摘要的请求时，MUST 检查自身 service DID 是否在当前 Realm policy 的 `plaintext_visible_services` 中，且 `visibility` 等级与 `data_classes[]` 均覆盖该内容类型。
- 未授权服务 MUST 拒绝明文请求并返回 `capability_denied` 或 `schema_violation`，不得静默索引、转发、缓存或降级保存。
- 恶意客户端把明文发送到协议外服务不属于协议可强制阻止的范围；但任何声称支持 Arkret profile 的服务若接收或处理未授权明文，均视为 profile violation。

## 7. Blob Surface

blob 服务至少应提供：

### 7.1 上传 blob

```text
POST /_arkret/self/blob/upload
```

返回：

- `blob_ref`
- `sha256`
- `size_bytes`

### 7.2 查询 blob 头信息

```text
HEAD /_arkret/self/blob/get?blob_ref=<ref>
```

### 7.3 下载 blob

```text
GET /_arkret/self/blob/get?blob_ref=<ref>
```

blob 校验 MUST 基于内容哈希，而不是单一 URL。

## 8. Directory Surface

directory 是授权过滤后的发现与搜索服务面。它是派生索引，不是真相源。

> 本节各 `POST /_arkret/find/directory/...` 路径为 **informative 示意**；canonical operation_id 与 HTTP path 以 [`service-http-binding.md` §2.1](./service-http-binding.md) 与 `artifacts/registry/operation-registry.json`（`ak.find.directory.*`）为准。

### 8.1 描述 directory

```text
GET /_arkret/find/directory/describe
```

返回：

- `service_id`
- 支持的 discovery profile
- 支持的资源类型：realm / organization / actor / applet
- 是否支持 restricted query proof

### 8.2 搜索 Realm

```text
POST /_arkret/find/directory/search-realms
```

请求 MAY 包含：

- `query`
- `organization_did`
- `source_realm_id`
- `requester`
- `proofs`
- `limit`
- `cursor`

Directory MUST 对每个结果应用 `ak.realm.discovery`、Realm policy、organization endorsement 和 requester proof 过滤。

### 8.3 精确解析 Realm

```text
POST /_arkret/find/directory/resolve-realm
```

用于通过 `realm_id`、alias、invite token 或 signed link 获取 stripped preview state。对 `invite_only` / `secret` Realm，未授权请求 MUST 返回与不存在相同的错误形态。

### 8.4 搜索与解析 Organization

```text
POST /_arkret/find/directory/search-organizations
POST /_arkret/find/directory/resolve-organization
```

Organization directory MUST respect organization discovery policy。公开组织 DID 可解析不表示成员列表、官方 Realm 列表、服务拓扑或治理策略全文可公开。

### 8.5 搜索 Actor / Handle

```text
POST /_arkret/find/directory/search-actors
POST /_arkret/find/directory/search-users
POST /_arkret/find/directory/resolve-handle
POST /_arkret/find/directory/resolve-agent-selector
POST /_arkret/find/directory/list-handles-for-subject
```

Actor / handle directory MUST NOT return pairwise DID、private DID、private handle、未披露的组织账号或仅因共同 Realm 推断出的关系。`search-users` 可用于 mention autocomplete / contact request / 成员添加候选；`resolve-handle` MAY 解析 handle 为 `subject` DID 与 `member_delivery_binding`，但只在 claim、audience、requester policy 和 intent 验证通过时披露。`resolve-agent-selector` 只做精确 `@<controller-handle>/<agent_slug>` compose-time 解析；成功时返回 agent DID 与当前可见 `ak.schema.agent_selector_claim.v1`，未授权、不可见、不存在、revoked / expired / ambiguous 时 MUST 使用与不存在不可区分的失败。`list-handles-for-subject` 用于已知 subject DID 时列出当前 context 可见 signed handle claims；它必须执行同样的 disclosure、issuer trust、audience 和 requester policy 过滤。Directory 返回的 `member_delivery_binding.recipient_service_id` 只可作为 contact address / handle evidence / join builder 输入，不能替代 `receive_policy_constraints`、Realm `delivery_binding` 或 grant 校验。该字段是 **builder evidence，不是 delivery 授权**：它**不是** member-level delivery 的权威路由来源（权威来源是 effective `ak.member.state.delivery_binding`），reducer MUST 按 [`../governance/member-delivery-binding.md`](../governance/member-delivery-binding.md) 重新物化 effective delivery binding，不得把 Directory 披露的该字段直接当作投递目标授权。语义边界回指 [`invite-addressing.md` §9](./invite-addressing.md)。

### 8.6 私密联系人发现

```text
POST /_arkret/find/directory/private-contact-discovery
```

该操作用于 `ak.private_contact_discovery.v1`。请求 MUST 使用 blinded / padded connection identifier batch，响应只返回 PSI set-membership 命中位图与最小 invite/consent handoff stub；MUST NOT 返回 contact request handoff token、time-bound reachability proof、原始 connection identifier、完整 profile、成员列表、Realm membership 或关系图谱。联系人请求与 direct conversation resolver 的正式语义见 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。

## 9. MIMI Provider Facade Surface（extension profile）

MIMI Provider Facade 不属于 v1 core service surface。完整定义见 [`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)（标记为 interop extension profile）。声称 v1 core 的实现 **不要求** 提供 `/_arkret/open/mimi/*` 路径；只有显式声明 `ak.profile.mimi_interop.v1` 的部署才暴露该子面。

## 10. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 Event，但服务层仍需要可查询面。

至少建议提供：

```text
GET /_arkret/self/authz/effective-grants?realm_id=<id>&subject=<did>
```

```text
GET /_arkret/self/authz/invites?realm_id=<id>&subject=<did-or-handle>
```

```text
POST /_arkret/self/authz/check
```

`check` 接口适合：

- Events API 接收写入前预检查
- Sync Service 分发前快速过滤
- client 发送前本地 UX 提示

## 10.1 Personal Agent Surface

Native personal agent 的 management、pairing、session grant 与 sidecar operations 属于 self / gate trust surface 上的语义操作；canonical HTTP path、request/response schema 与 binding completeness index 由 [`service-http-binding.md` §2.4.1](./service-http-binding.md) 维护，本文只声明语义边界。实现 MUST 使用 operation catalog 中登记的 `ak.self.agent.*`、`ak.gate.account.*` 与 `ak.self.agent.sidecar_thread.*` 操作名，不得从本节散文推导额外路径、profile id 或快捷授权。

约束:

- 本 surface 不引入 custom URI scheme(`arkret://` 等);所有 deep-link 由客户端用 deployment 已知的 `arkret_base_url` 拼接标准 HTTPS URL,移动端依赖 OS Universal Links / App Links。
- `pairing_request_id` 与 `approval_request_id` 都是 account/auth profile-local opaque UUIDv7 短期 artifact,不是 `ak:<kind>:<uuid>` 协议对象 id;agent runtime 收到 `approval_request_id` MUST NOT 解释成 URL 或尝试打开 UI,只能由 controller 的人类 session 带外查询。
- `{agent_id}` 是 DID,在 URL path 中 MUST 按 RFC 3986 percent-encoding。
- `ak.self.agent.command.provision` MUST 接收非空 `slug`；`slug` 是 Agent 自身的固有字段，因此 provision request 与 list/get projection 均使用裸名 `slug`。服务端 MUST 在 controller PCR 生成或更新当前有效的 `ak.schema.agent_selector_claim.v1`（controller-scoped selector claim），其中引用 Agent selector 的字段使用 `agent_slug=slug`。controller E2EE client MAY 在随后由其本地生成并加密提交的 Agent Actor Profile 中写入 `agent_slug` 作为投影 hint；服务端不得代写该 Agent PCR Profile。`agent_slug` 只用于 `@<controller-handle>/<agent_slug>` 输入别名到 agent principal DID 的 compose-time 解析；服务端 MUST 拒绝或 fail closed 处理同一 verified controller 下 active native agent 的 selector claim 冲突。
- participation operation 使用 `agent-operations.schema.json#/$defs/agent_participation_entry` 形态返回 `selection`、`ceiling` 与 `effective`。`set` 只能由 controller 调用，服务端 MUST 校验 `selection ⊆ effective_ceiling(scope)`；`get` 可由 controller 或该 agent runtime 调用。
- `ak.gate.account.command.issue_session_grant` 为 agent runtime 签发 session 时，若 scope request 覆盖 participation-aware scope，`scope_details.participation[]` MUST 使用与 `agent_participation_entry` 同构的 `{scope, selection, ceiling, effective}` 条目。runtime MUST 把该数组视为行为契约；服务端仍以 capability grant、dispatcher gate 和 reducer 校验作为强制边界。

详细 wire 规则见 [`service-http-binding.md` §2.4](./service-http-binding.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)、[`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md)、[`../models/circle.md` §11.1](../models/circle.md)、[`../models/private-objects.md` §4.1](../models/private-objects.md) 与 [`../authz/capabilities.md` §5](../authz/capabilities.md)。

## 11. Realm Bootstrap Strand

Arkret v1 的首次加入流程：

1. 用户输入 handle、DID 或 Realm link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 DID Document 和 Realm policy 发现 Principal Server / identity registry / events / account / snapshot / blob / authz 服务
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 Realm metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk。**防投毒要求 (Snapshot Validation)**：由于 Sync Service 仍是服务节点，快照可能被恶意篡改。客户端 MUST 验证快照 manifest 的规范字段 `created_by`（即签发者 DID，与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 一致）、`created_at`、`authority_binding`、`signature`、`state_digest` (Merkle Root)、frontier 和每个 chunk digest。`signature` 的 signer 必须匹配 `created_by`，且 `authority_binding` 必须证明该 DID 在 `created_at` 时是 Realm owner、Realm policy 授权的 snapshot issuer 或 witness quorum 成员。high-assurance profile 下，`authority_binding.witness_attestations[]` 或等价 quorum proof 必须可验证；缺失时不得作为高保证 snapshot 使用。若校验失败，客户端 MUST 丢弃快照并回退到 `GET /_arkret/self/events?before=<cursor>`（`ak.self.events.query.scan`）进行原始 Event 历史回放。
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

- Events / Sync Service MAY 不解密正文
- 但仍 SHOULD 保留 hash、cursor、causal 与目标引用

## 14. 防滥用与配额机制 (Anti-Spam & Quota)

在去中心化网络中，计算、存储与带宽都是稀缺资源。协议要求所有提供写入或传播服务的节点实现必须具备防御恶意滥用的能力：

### 14.1 存储责任与 Blob Quota
- **成本归属**：Realm 的整体数据大小、历史 Event 数量及附属的 Blob 存储成本，逻辑上必须绑定到 Realm 的 `owner` 或负责托管的 `responsible_actor_id`。
- **拒绝写入**：当 Blob 服务或 Principal Server 评估该 Realm 占用的资源已超出预设的 Policy 配额 (Quota) 时，MUST 返回明确的协议错误语义（例如 `quota_exceeded`、`payload_too_large` 或 profile 注册的付费/资源门槛错误），并拒收新写入的 Event 或大文件 Blob。HTTP status 映射属于 binding 层，见 [`api-conventions.md` §4.1](./api-conventions.md) 与 [`service-http-binding.md`](./service-http-binding.md)。

### 14.2 写频率控制 (Rate Limiting)
- Events API 和 Sync Service 节点 SHOULD 基于 `actor_id` 与 `realm_id` 实施严格的并发和频率限制。
- 对于来自未验证或低信誉 DID 的恶意刷写（例如短时间内进行海量无效的 `message.create` 或反复触发高并发图重组），节点有权暂时熔断该 DID 的请求。

## 15. 设计决定

Arkret v1 固定：

- 定义最小 Principal Server / identity registry / events / account / snapshot / blob / authz 服务面
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
- Authz check response MUST 返回 `decision`、`matched_grants`、`applied_constraints`、`policy_results`、`missing_proofs`、`frontier` 和 `cache_expires_at`；`decision` 只能是 `allow`、`soft_deny`、`hard_deny`、`quarantine` 或 `require_review`。
- Service describe MUST 声明 `service_id`、`trust_domain`、`service_type`、`protocol_version=1.0`、`supported_profiles`、`supported_operations`、`supported_bindings[]`、`supported_features[]`、`auth_metadata`、`limits`、`rate_limit_policy` 或 `rate_limit_policy_id`、`plaintext_visibility` 与 `development_mode`。其中 `supported_bindings[]` 是数组(每项描述一个 transport binding,例如 `{kind: "http_json", ...}`);单数字段名 `binding` 不出现在 describe response 顶层。客户端 MUST 拒绝 service DID、trust_domain、Realm policy 或 profile 不匹配的服务。`plaintext_visibility` 缺失视为该服务**不可信**用作 `plaintext_visible_services` 成员(见 OpenAPI ServiceDescribe schema description)。
- Service describe 响应 MUST 同时按 §3.0 区分 `supported_operations` / `implemented_features` / `claimed_profiles` / `verified_profiles` / `experimental_features` / `compat_surfaces` 六个 claim level 字段，schema 见 `ak.schema.service_describe.v1`。当 `development_mode=true` 时 `verified_profiles` MUST 为空；当 `development_mode=false` 且声明 `verified_profiles` 时，客户端仍 MUST 通过 `artifact_ref` / transparency log 获取并校验对应 verification artifact、verifier 签名和 hash 后才把它作为生产 conformance 依据。
- Sync cursor recovery MUST 按 `conformance-vectors.md` 执行：cursor 是 opaque token；过期或缺口时返回可恢复错误，并提供 backfill 起点或 snapshot frontier。
- Event source consistency MUST 按 `conformance-vectors.md` 执行：重复 Event 幂等，冲突 Event 拒绝，event order、hash、签名和 `actor_seq` 必须可复现验证。
