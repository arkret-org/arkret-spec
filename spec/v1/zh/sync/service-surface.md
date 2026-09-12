---
title: Service Surface And Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-09-12
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
- Station 如何提供 account aggregate stream、snapshot 与 backfill 协调
- search / View projection 的语义边界如何在客户端或显式受托服务中保持一致
- directory 如何做 Realm / Organization / Actor 的授权搜索与精确解析
- blob 如何上传与校验
- invite / grant 如何参与首次加入工作区

本文给出 **最小可互操作服务面**。
默认调用风格采用 HTTP/JSON binding。Operation 语义可以映射到 gRPC、GraphQL、WebSocket、SSE、message queue、libp2p 或本地 IPC，但 **v1 core wire conformance 必须提供 HTTP/JSON binding**；非 HTTP binding 只能作为 extension profile 声明，并且必须提供语义等价的操作、认证、授权、幂等、分页、错误和流控语义。详细规则见 `transport-bindings.md`。

本文件按服务角色说明接口语义。所有 REST endpoint 的字段级请求 / 响应 schema、认证模式、访问限制和幂等规则以 [service-http-binding.md](service-http-binding.md#24-字段级-schema-索引) 为准；本文件中的 JSON 或字段列表仅用于解释服务面，不构成完整 schema。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

这里的 DID Document 是 `did` 的 method-native 解析结果，不是 Arkret 业务主键。Arkret Event、policy、member binding 和服务准入持久引用使用稳定 `did_core_id`；只有初次注册、解析刷新和方法原生验证才必须出示 `did`。注册的 method adapter MUST 验证 `did` 及其控制历史，并确认 `project(did) = did_core_id`；服务不得从域名或 URL 反推 `did_core_id`。

DID Document SHOULD 只负责：

- 声明 Station、identity registry、events、Station sync surface、blob、capability 服务入口
- 声明服务 DID 或服务 endpoint

它不应直接塞入：

- 当前 grant 全量状态
- 当前 realm 当前态
- 大量通知或 inbox 数据

### 2.2 没有任何单一服务是唯一真相源

- signed Event 是 actor 发布和协作事实真相源
- Station sync surface 是 Station 上的受控同步入口
- search、inbox、notification 和 View projection 是派生体验，可以由客户端本地计算，也可以由显式受托服务计算
- blob 是内容层

客户端应能在这些层之间交叉验证 frontier、hash 与 reducer profile。

### 2.3 接口必须天然支持幂等重试

网络重试、离线回放、多 Station 同步在去中心化系统中是常态。

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

### 2.5 核心角色、Station capability 与可选服务

`service_kind` 只回答“远端正在信任、授权或向谁披露数据”。候选实体只有在远端必须验证其独立 service DID / 签名、显式委托或 allowlist、识别独立明文 / 密钥 / 恢复 / 合规边界、直接发现其 base URL，或由它执行会产生不同 normative authority/state result 时，才可登记独立 `service_kind`。进程、数据库、团队、内部域名、私有 RPC、扩容单元、计算成本或未来部署设想均不足以产生 wire role。operation bundle 表达操作集合，feature / limit / transport binding 表达可选行为，本地进程拓扑不进入 wire contract。

每个独立服务的 `ServiceDescribe` MUST 只描述一个已登记角色，并明确 `service_kind`、`supported_operation_bundles`、认证方式、限制、plaintext visibility 和 profile。多个独立角色共享 public binding 时，部署 MUST 为每个角色支持 `GET /_arkret/describe?service_kind=<registered-id>`；查询值、响应角色与 DID/service binding 必须一致。Station 内部组件不得借此发布 role-scoped Describe。查询省略规则和错误语义见 [`service-http-binding.md` §2.3](./service-http-binding.md)。

*Table 2-A. 核心 account flow 概念（normative）。*

| 概念 | 规范职责 |
| --- | --- |
| **Station** | 为一组明确 principal account 保存并处理实际业务数据、执行本地账号与 Event 准入，并作为这些账号参与 Arkret 网络、接收外部投递和发起对外通信的权威服务站点。Station 是 `service_kind=station` 的 wire role。 |
| **Account Authority** | Station 对客户端发布的唯一账号准入逻辑入口，承载注册、session grant、恢复、配对与登出。它由 Station 的 `auth_metadata.account_authority` 发现，不是独立 `service_kind`、service DID 或公开 role profile。 |
| **Authentication Method Provider** | Passkey、OIDC、SSO 等认证方法或标准 issuer。它 MAY 是外部 IdP，但认证结果只作为 Account Authority 的输入，不取得 Station、账号或 Event authority。 |

Station 同时是业务数据所在地、`AccountId {principal_id, station_id}` 的账号归属边界和 inter-Station 通信主体。一个 Station MAY 服务多个不属于同一 Realm、组织、家庭或社群的 principal。它不是 relay、全网中心、DID 注册机构或可替换路由 anchor；运维层可迁移进程、数据库或副本，但不得把协议账号、权威历史或数据所有权改写到另一 `station_id`。账号与数据谱系的集中规则见 [`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md)。

*Table 2-B. Station 内置 capability / surface（normative）。这些项目均不产生额外 `service_kind`。*

| capability / surface | Station 职责 |
| --- | --- |
| Account / Event | account aggregate、viewer/profile、自服务、Event ingest/read、准入与投影。 |
| Client sync / federation / invite | subscription、cursor、snapshot、backfill、inter-Station transaction、invite locator / delivery、destination 与 replay gate。 |
| Authorization | effective grant、invite 与 capability 判定；内部 PDP / Policy Engine 可拆进程，但不能成为 wire role。 |
| Device / key | device authorization/revocation、active generation、OTK/fallback key、MLS KeyPackage claim、to-device queue 与 encrypted backup；所有裁决绑定 Station-local `AccountId`、PCR 与 durable gate。 |
| Blob authority | account / Realm 对象 authorization、metadata、retention policy 与引用关系；默认 bytes surface MAY 与 Station 同部署。 |
| Search | 私有 account / Realm 搜索；公共或授权发现属于 Directory Service。 |
| Moderation | report intake、local queue、Station ACL 与 decision/lift projection。 |

*Table 2-C. 按需出现的独立服务（informative）。只有满足本节保留判据且实际启用时才进入 discovery。*

| 服务 / 基础设施 | 独立边界 |
| --- | --- |
| Identity Resolution Infrastructure / Identity Registry | DID document、method-native log、receipt、witness、watcher、OOBI 与 service endpoint discovery；只有独立可寻址或签名实现才登记角色。 |
| Directory Service | 公共或组织目录、授权发现、anti-enumeration、takedown 与可见性边界。 |
| Blob Service | 仅按 Station 绑定的 contract 执行 bytes storage/delivery，不取得账号、Realm、Event、metadata 或 retention authority。 |
| Media Service / TURN / SFU | transform、delivery、ICE relay 或 selective forwarding；各自按实际 service DID、密钥、可见性与委托边界登记，不使用复合媒体角色。 |
| Push Gateway | 外部投递与 APNs/FCM/厂商适配边界，不持有 Station 业务数据 authority。 |
| Applet Service / Agent Runtime | 受注册授权的扩展服务或执行环境；按 capability 写回，不取得账号业务数据 authority。 |
| Moderation Service | 仅限 Realm/组织显式委托的独立审核实体；按实际 service DID/签名、plaintext visibility 或特定对象的保留/删除约束区分职责。legal hold 的阻止删除、授权解除与审计按 [device-lifecycle §12.2](../crypto-media/device-lifecycle.md#122-retention-and-erasure) 和 [call-state §5.2](../crypto-media/call-state.md#52-录制--转写-retention-policynormative) 执行，不因 hold 获得明文读取、解密或额外签署权。 |
| Archive Node / Key Recovery Service / Recovery Service | 按实际历史可见性、密钥持有和恢复 authority 分别授权，不得用含混总称赋予全部权限。 |
| Notary / MIMI Provider Facade | 分别为独立密码学角色和互操作 facade；只在相应 Realm/profile 实际委托时出现。 |

REST namespace 第一段路径（`self` / `gate` / `root` / `find` / `peer` / `open` / `edge`，见 [service-http-binding.md §2.1](./service-http-binding.md)）是 **trust-surface classifier（信任面分类器）**，编码"调用方↔服务"的攻击面类别，**不是授权结论**；实现 MUST NOT 把信任面段本身解释为授权通过、安全级别达标或明文可见许可。每个 operation 仍按自身契约执行 session / capability / DID proof / Realm policy / history visibility / rate limit 校验。

#### 2.5.1 Account Authority 与认证方法发现

Station 的根级 `/_arkret/describe` 是客户端登录 / account flow 的启动入口；普通客户端先按 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative) 建立并持久核对 Station 与认证绑定。`auth_metadata.account_authority` MUST 给出一个绝对 `gate_account_base_url`，客户端发起的 Arkret `/_arkret/gate/account/*` 请求都 MUST 从该 base 派生。客户端不得按 operation 猜测内部进程。部署 MAY 在认证 TCB 内使用网关、反代或独立 Auth Server 进程处理这些操作，但该组件是 deployment-private：不得拥有公开 `service_kind`、role profile、service registration、role-local Describe、federation identity 或 peer-discoverable endpoint。`ak.gate.account.command.logout_auth_session.v1` 是 Account Authority 内部终结认证 session 的 typed 子操作，普通客户端 MUST NOT 调用或从 `gate_account_base_url` 派生。

`auth_metadata.methods[]` 只描述认证方法（例如 `oidc`、`passkey`、`device_pairing`、未来 `gnap`）及其 provider / issuer / discovery，不决定 `gate/account` 的路由。OIDC method MUST 使用标准 discovery 与标准 `authorization_endpoint` / `token_endpoint`；Arkret 不定义 `/_arkret/gate/auth/oauth/*` 这类私有 OAuth endpoint family。标准认证结果进入 Arkret 的桥是 Account Authority 的 `POST {gate_account_base_url}/session-grants`，响应为 `SessionGrantOutcome`；Principal 本地 session provisioning 属 Account Authority 内部编排，不得暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

Account Authority 内部分派不得改变 operation 的协议身份。尤其 `ak.gate.account.command.pair_agent_key.v1` 依赖 Station 的 pairing record、Agent PCR Event acceptance 与 activation projection 时，split deployment MUST 将原始 typed request 委托到权威 Station 的同一 `/_arkret/gate/account/agent-key-pair` binding，并保留 Event ID 幂等身份；不得把该职责改造成产品私有 `fanout` URL 或只入本地队列后向客户端报告成功。具体 commit 规则见 [`../identity/key-management.md` §3.6.1 / §3.6.2](../identity/key-management.md)。

本登录 / account flow 最多并存三类 origin：Station（发现启动与 wire role）、Station 发布的 Account Authority base（全部 `gate/account` Arkret 操作）和 Authentication Method Provider / issuer（标准认证协议）。前两者即使分 origin 也仍属于同一 Station wire role。完整客户端仍可按其它 spec 访问 Directory、Blob、Media、Push 等独立 service origin；这些不改变 account flow 路由。

Deployment profile 的 canonical 机器真源是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `deployment_profiles` 集合；本文不得另注册 profile id。下列形态仅是服务角色组合说明，实际部署 MUST 声明 canonical id（如 `ak.profile.personal_node.v1`、`ak.profile.organization.v1`、`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1`）并按 profile registry 校验能力面：

- 个人节点通常部署一个 Station，并按需使用公共 Directory、Push 或 TURN/Media 服务。
- 组织节点 MAY 把 Station 的认证、policy、sync/federation、device/key、Blob bytes 与 moderation worker 拆成内部进程；这些边界不进入 discovery。只有满足独立信任判据的 Directory、Blob、Media、Push 或 Moderation Service 才发布独立角色。
- 高安全或主权部署把 Station 与 Identity Resolution、Directory、外部 Blob/Media、Push、Notary、Archive/Recovery 等已委托服务保持在受控 trust domain；公共服务或 federation ingress 只能作为显式授权的互联入口。
- Applet、MIMI facade、Agent runtime、Moderation、Archive/Recovery 等角色是 service role / capability 组合，不是 deployment profile id；它们只能在已声明 profile 允许的 namespace、capability、Realm policy 与 service describe 范围内工作。

### 2.6 Service DID 权威入口与路由解析（normative）

本节规定服务器、registry、联邦接收方与独立审计者的服务身份验证，以及末段所述独立消费；普通客户端自己 Station 的接入按 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative)。上述独立验证角色使用的服务身份、控制密钥与业务入口 MUST 来自同一经 DID method adapter 独立验证的状态。业务绑定持久 service_id（did_core_id）和预期 service_kind；解析时 MUST 验证 project(did) == service_id，并从该 DID Document 选择唯一对应的 ArkretService entry。entry.id MUST 是该文档 DID 的非空 fragment 标识，type MUST 为 ArkretService，serviceKind MUST 等于预期 service_kind，serviceEndpoint MUST 为 canonical absolute HTTPS base URL。不得在同一 kind 下选择多个 entry，也不得按数组顺序挑选入口。规范化要求 scheme / host 小写、去默认端口、消解 dot segment、无 userinfo / query / fragment、path 恰有一个 trailing slash。入口不规范、歧义、错误 service/core/type 均 MUST 拒绝。

公开 ak.open.service.read.resolution.v1（GET /_arkret/open/services/{service_id}/resolution）向成员与非成员返回 AuthenticatedServiceResolution：service_id、service_kind、method_history_evidence、normalized_did_document。它是可独立验证的原生证据载体，不是 resolver 的可信声明，也不签发独立地址记录。服务入口、当前 DID、method head / version 和 service control reference 只允许从该证据派生；不得另签地址声明覆盖文档。邀请、配置 URL、inline carrier、镜像和缓存均只提供发现线索，不能单独授予路由或业务权限。

`normalized_did_document` 采用 did-binding-contracts 的闭合规范化投影；原生 entry 的 type、serviceKind 和 serviceEndpoint 分别映射为 services 的 protocol_names、extensions 中对应属性和 endpoint，不能转发另一套原生文档 wire 形状。派生 `ServiceResolutionProjection` 的字段顺序固定为 service_id、service_kind、did、method_history_head、version_id、resolution_event_ref、base_url。resolution_event_ref 使用 adapter 坐标：WebVH 为 did-webvh-entry-sha256:<head hex>，did:web 为 did-web-document-sha256:<document digest hex>，did:key 历史用途为 did-key-did-sha256:<DID digest hex>。历史响应 capability 的 release_service_resolution_digest 固定摘要完整规范化 AuthenticatedServiceResolution；release_service_route_digest 固定为 SHA-256(RFC8785-JCS(ServiceResolutionProjection))。

did:webvh MUST 验证从 inception 至目标状态的完整原生日志、SCID、每个适用 update key / nextKeyHashes、控制轮换及 witness policy 所需证据，并比对 exact normalized document。不能只验末条签名。接收方 MUST 持久保存已接受的 method head / version / DID；后续材料必须包含该已接受状态及其连续原生后继。相同版本异 head 是 fork；旧状态回放、缺失已接受状态或无效原生后继 MUST fail closed，并保留 fork 证据。重启和 TTL 淘汰不得降低已接受 method 状态；并发更新须原子比较已接受 method 状态，旧请求不能覆盖新状态。离线节点补齐的是 DID 原生历史，刷新缓存不产生新 DID 版本。

完整旧历史并不证明当前状态。普通路由在首次使用、缓存到期、授权变化或安全敏感操作前，MUST 通过受信任 method resolver 的当前状态查询重新验证当前 head 和 exact document；仅随 resolution 携带的历史、发送者签名、镜像多数或 TLS 可达都不足以证明 freshness。查询失败时不得创建或延长路由缓存；无仍有效缓存时 MUST 拒绝业务投递。缓存最长 300 秒，且不得超过 method evidence、控制授权或绑定的有效边界；本地 verified_at / cache_expires_at 不是可转发的新鲜度凭证。相同 DID 状态的刷新只更新本地验证时间，不能创建额外地址历史。

did:web 仅在明确启用 no-history 信任配置及角色 policy 允许时可用。adapter MUST 通过 DNS/WebPKI 从 DID 的标准文档位置验证当前文档；携带或缓存的文档不能代替当前查询。相同 DID 下合法的业务 endpoint 更新或机器/IP 调整按该信任模型处理，不伪造历史能力；改变 DID 域名/路径产生另一身份，不能继承原 service core。要求历史证据的 signer / notary 用途 MUST 拒绝仅有当前 did:web 文档。did:key 不提供可变的服务入口。

获取与跟随所有发现线索时继续执行 canonical HTTPS、SSRF/DNS rebinding 防护、redirect policy、大小及超时限制：resolution 和 describe 各不超过 1 MiB，获取操作不超过 5 秒；原生日志与 witness 各不超过 4096 条，既有更严格 egress policy 继续适用。验证 DID 入口后，MUST 从该入口读取对应 service_kind 的标准 describe，并核对 service_id、service_kind、service_resolution 的 DID / method head / version 和唯一 http_json base URL。describe 不成为 resolver，动态能力、limits 与 rate policy 不需要制造 DID 更新。

WebVH DID 托管位置迁移须满足原生 portability 前置条件并保持 SCID，验证连续日志和适用 alsoKnownAs；新建不同 SCID 属于身份重绑定。业务 endpoint 更新也必须进入经验证的 DID Document。迁移提示即使已签名，也只能协调预检时间，不授权目标入口；业务流量切换必须重新完成当前 DID 状态与 describe 验证。

服务路由只保留 DID 方法原生状态，不创建额外的地址历史或签名发布状态机。DID method 原生历史及冻结历史 signer evidence 继续保留；可路由不代表 Realm 授权，历史签名必须验证签发位置的密钥与业务权威，不能用当前文档替代。

本节的 method-native 验证职责属于接纳外部材料的角色：服务器、联邦接收方、identity registry 与独立审计者。已建立账号会话的普通客户端在已登记用途上改为消费自己 Station 的已验证结果：Realm genesis notary 用 [server-trusted-results.md §5.8](./server-trusted-results.md)，已加入 Realm 的媒体服务绑定用同文件 §5.9；两者都返回派生 `ServiceResolutionProjection` 或冻结 signer descriptor，不返回 method evidence，客户端只核对请求/会话/route 与结果内的确定性绑定。普通客户端尚未建立账号会话时，自己 Station 的接入专用合同见 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative)，不执行本节的 method-native 历史验证。匿名 Directory 等独立消费仍需明确承担本节的验证者；未验证候选不能变成自己的 Station 或自报 verified。该接入合同不改变服务器、registry、联邦接收方及独立审计者的原生验证与 freshness 义务。

## 3. 通用服务描述接口

所有网络可发现服务 MUST 提供：

```text
GET /_arkret/describe
```

*Example (informative). `/_arkret/describe` 响应示例，字段权威定义以 schema 为准。*

```json schema=schemas/service-describe.schema.json
{
  "service_id": "ak:did_core:webvh:zCm2ZfnfjnNcgaUrSkWyf5UtD",
  "service_resolution": {
    "did": "did:webvh:zCm2ZfnfjnNcgaUrSkWyf5UtD:alice.example.net",
    "method_history_head": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "version_id": "3"
  },
  "trust_domain": "ak:trust_domain:did.webvh.alice.example",
  "service_kind": "station",
  "protocol_version": "1.0",
  "supported_profiles": [
    "ak.profile.station.v1"
  ],
  "supported_operation_bundles": [
    "ak.operation_bundle.station.describe.v1",
    "ak.operation_bundle.station.http_core.v1",
    "ak.operation_bundle.station.tus_upload.v1",
    "ak.operation_bundle.station.websocket.v1"
  ],
  "transport_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://alice.example.net/",
      "extension_profile_required": null
    },
    {
      "kind": "tus",
      "base_url": "https://alice.example.net/_arkret/self/blob/resumable",
      "extension_profile_required": null,
      "tus_version": ["1.0.0"],
      "tus_extensions": ["creation", "creation-with-upload", "checksum", "expiration", "termination"]
    }
  ],
  "supported_features": [
    "ak.feature.invite_addressing.v1",
    "ak.feature.notifications.v1",
    "ak.feature.realm_state_snapshot.v1",
    "ak.feature.sync_stream.v1",
    "ak.feature.blob.resumable_upload.tus.v1",
    "ak.feature.history_key_recovery.v1",
    "ak.feature.mls_exporter_aead.v1"
  ],
  "invite_addressing": {
    "supported_introduction_kinds": [
      "locator_ref",
      "consent_grant",
      "shared_realm",
      "handle_claim",
      "same_station",
      "explicit_address"
    ],
    "handle_claim_max_behavior": "quarantine",
    "explicit_address_max_behavior": "drop"
  },
  "receive_policy_constraints": {
    "policy_version": "2026-06-21",
    "applies_to": ["invite_delivery", "contact_request"],
    "deployment_allowed_introduction_kinds": [
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
      "gate_account_base_url": "https://alice.example.net/_arkret/gate/account"
    },
    "methods": [
      {
        "method": "oidc",
        "issuer_uri": "https://auth.example.com",
        "openid_configuration_url": "https://auth.example.com/.well-known/openid-configuration",
        "client_id": "ak.example-client",
        "scopes": ["openid", "profile"],
        "grant_exchange": {"kind": "account_handoff"}
      },
      {
        "method": "passkey",
        "grant_exchange": {"kind": "account_handoff"}
      }
    ],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  },
  "limits": {
    "mls_governance_proof": {
      "max_exact_response_bytes": 1048576
    },
    "max_body_bytes": 1048576,
    "max_events_per_batch": 100,
    "device_message_max_ttl_seconds": 86400,
    "read_cursor_debounce_ms": 1000,
    "dangling_redaction_min_retention_days": 30,
    "realm_state_snapshot_retention_heads": 2,
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
        "operation_id": "ak.self.events.command.submit.v1",
        "rate_limit_scope": ["service_id", "realm_id"],
        "window_seconds": 60,
        "max_requests": 120,
        "burst": 20
      }
    ]
  },
  "claimed_profiles": [
    {
      "profile_id": "ak.profile.station.v1",
      "claim_kind": "self_claimed",
      "claimed_at": "2026-05-02T00:00:00.000Z"
    }
  ],
  "verified_profiles": [
    {
      "profile_id": "ak.profile.core_event_store.v1",
      "claim_kind": "conformance_verified",
      "verification_run_id": "verify-2026-05-02T000000Z",
      "artifact_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
      "artifact_ref": "https://verifier.example/log/verify-2026-05-02T000000Z",
      "verifier_id": "ak:did_core:webvh:zC72cg8H1bJUTB6ZngzxP68BJ",
      "signature": "base64url:...",
      "timestamp": "2026-05-02T00:00:00.000Z"
    }
  ],
  "interop_surfaces": [],
  "development_mode": false
}
```

能力发现示例（normative 指引）：客户端判断服务端是否支持某项**可选传输能力**时，MUST 先从 `supported_operation_bundles` 展开精确 operation/binding pair，再按 `transport_bindings` 的数组顺序选择可用 endpoint，并检查对应 `supported_features` / `limits`，不得探测猜测 endpoint。以可续传 Blob 上传为例，服务端支持时 MUST 同时声明 `ak.operation_bundle.station.tus_upload.v1`、`ak.feature.blob.resumable_upload.tus.v1` 与一条 `kind="tus"` 的 transport binding；客户端据此发现后再用 tus `OPTIONS`（`Tus-Resumable` / `Tus-Version` / `Tus-Extension`）做 endpoint 级线上确认。完整 binding 语义、内容寻址不变式与隐私约束见 [`crypto-media/media-and-blob.md` §2.1](../crypto-media/media-and-blob.md)。

本规范登记的标准 `supported_features` 还包括：`ak.feature.history_key_recovery.v1`（唯一 private exporter-history
request/response-stream/S2S relay/RHRK archive 合同）、`ak.feature.mls_exporter_aead.v1`（接受并同步
`content_scheme=mls_exporter_aead_v1` Realm/Circle；见 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)
§2.10）与 `ak.feature.agent_runtime_approval_notifications.v1`。声明 `history_key_recovery` 的服务 MUST 同时暴露
`ak.self.seals.read.frontier.v1`、`ak.self.seals.read.resolve.v1`、
`ak.self.seals.read.mls_governance_proof.v1`、`ak.self.seals.read.governance_dependencies.v1`、
`ak.self.history_key_requests.command.create.v1`、`ak.self.history_key_requests.read.list.v1`、
`ak.self.history_key_responses.command.send.v1`、`ak.self.history_key_responses.read.list.v1`、
`ak.self.history_key_responses.command.ack.v1`、
`ak.self.organization_recovery_archives.read.list.v1`、
`ak.peer.seals.read.mls_governance_proof.v1`、`ak.peer.seals.read.governance_dependencies.v1`、
`ak.peer.history_key_requests.command.replicate.v1`、`ak.peer.history_key_responses.command.relay.v1` 与
`ak.peer.organization_recovery_archives.command.replicate.v1`，并支持 `history-key.schema.json`、near-current frontier proof schema 与
receipt-bound direct Seal traversal 及 typed dependency resolve；
不能只声明其中一个旧 relay/backup/archive 子能力。创建或处理 `mls_exporter_aead_v1 +
history_access=all_history_for_current_members` scope 的 client/server MUST 声明该 feature；任一端缺失时 fail closed，不能回退到
to-device request、foreign active MLS state 或公开 Event。其它客户端依赖能力时仍以 describe 声明为准。

服务类型命名规则：

- service identity bootstrap 的 DID Document entry 唯一使用 `type="ArkretService"`，并以必填 `serviceKind` 取 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json) 中 `valid_in` 含 `service_registration_key` 的值。`ArkretStation` / `ArkretDirectory` 不是 alias，必须拒绝。Organization 与 Agent 的 specialized DID service type 仅使用 [`did-document-contract-registry.json`](../../artifacts/registry/did-document-contract-registry.json) 登记的独立 endpoint shape，不得替代 service bootstrap。
- describe 响应的 `service_kind` 使用 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json) 中 `status=active` 且 `valid_in` 包含 `service_describe` 的小写注册值；正文不复制该闭集。其它 context 的值不得进入 Describe：例如 `mimi_provider_facade` 只用于 `mimi_provider_directory` descriptor，不是 `ServiceDescribe.service_kind`。Realm join candidate 的 `service_kind` 仅允许 `station`，其路由来源只允许 signed invite 或当前 joined-joined-member ActorId routing projection（见 [`realm-join-candidate.schema.json`](../../artifacts/schemas/realm-join-candidate.schema.json)）。
- conformance profile 使用 `ak.profile.*` 标识，例如 `ak.profile.station.v1`。
- 实现 MUST 区分这三层名称，不得把 DID service type、运行时 service_kind 与 conformance profile 混用。

### 3.0 Describe response claim levels

`server/describe`（以及结构等价的 `identity/describe` / `events/describe` / `sync/describe` /
`directory/describe` / `applet/describe`）响应 MUST 使用同一个 canonical `ServiceDescribe` shape。除 `service_id`、`service_resolution`、`trust_domain`、`service_kind`、`protocol_version`、`supported_profiles`、`supported_operation_bundles`、`transport_bindings`、`supported_features`、`auth_metadata`、`limits`、`plaintext_visibility` 和 `rate_limit_policy` / `rate_limit_policy_id` 之外，响应还 MUST 按 **claim level** 区分以下字段；schema 见
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)（`ak.schema.service_describe.v1`）：

完整 role-scoped `ServiceDescribe` 的 canonical response body MUST 不超过 1 MiB（1,048,576 bytes），且 MUST 省略 `Content-Encoding`、禁止 redirect。该上限覆盖完整 `supported_operation_bundles[]` 与 `transport_bindings[]` 闭包；实现不得沿用只适用于旧精简 describe 的 64 KiB 本地限制。超过上限的服务 MUST 收窄其 role surface 或拆分为独立 role-scoped endpoint，不得静默截断 binding rows。

`service_id` MUST 是该逻辑角色的 `did_core_id`，`service_resolution` MUST 投影当前 `did` 与 method history position。这个投影只用于将已选定 endpoint 与首跳 DID 方法验证结果 交叉确认，不能让 describe 变成 resolver，也不能单独创建 service 授权。

`ServiceDescribe` 顶层以及 schema 明示允许扩展的嵌套对象（当前包括 `auth_metadata`、其
`account_authority` / `methods[]` / `grant_exchange` 子树以及 `plaintext_visibility`）中的 `x_*`，只允许承载
可安全忽略的展示、日志或厂商 metadata。对任意合法 Describe 递归删除这些槽位中的全部 `x_*` 后，
operation/transport 可用集合、feature 可用集合、profile claim、认证、授权、route、payload/contract 选择与错误分类 MUST
完全不变；因此 `x_*` MUST NOT 承载 endpoint、operation、transport、schema selector、认证要求、授权约束、协议 limit 或
跨实现行为选择。需要影响这些结果的第一方字段必须先登记为 closed schema 字段；`invite_addressing` 即按此规则登记，且与
`ak.feature.invite_addressing.v1` 双向共现，不保留扩展别名。

软件源码树、SDK/服务构建、生成 registry 文件或整个发布制品的 exact hash / fingerprint 不是协议兼容性载体，MUST NOT
出现在 `ServiceDescribe`（包括 `x_*`）中，也 MUST NOT 作为连接、operation 可用性、Event authoring、admission、route
缓存或 fallback 的前置条件。实现只可按 `protocol_version`、本地 exact versioned registry/schema 与本节规定的
operation bundle、transport、feature、profile、limit 交集判断互操作能力；这些交集成立时，源码或制品字节不同不得使
整个服务不可用。开发工具 MAY 在单进程本地 UI、日志或 DOM 中暴露当前 bundle/build id 以诊断 stale cache，但该信号
MUST 保持在协议外、不得随 Describe 或业务请求传输，也不得改变任何协议结果。

当 `service_kind=directory_service` 时，`ak.find.directory.read.describe.v1` 还 MUST 按 [`discovery-directory.md` §8.9](../discovery/discovery-directory.md#89-akfinddirectoryreaddescribev1-扩展) 暴露已登记在 `ServiceDescribe` schema 中的 directory-specific 裸字段（例如 `resource_kinds[]`、`ingest_modes`、`accept_policy_kind`、TTL 与 `rate_limits` 字段）；这些字段不是 vendor-specific `x_*` 扩展。
`service_kind` 只选择 role overlay，不自动产生任何 conformance profile claim；尤其
`directory_service` 不要求 `supported_profiles` 含 `ak.profile.directory_service.v1`。实现只有在满足该 profile 的完整 typed
operation/schema/fixture closure 时才可独立声明它，缺少其中任一 operation 时应只公告真实 bundle，不得虚假 claim。

- `supported_operation_bundles: operation_bundle_id[]` — 当前 role endpoint 可实际调用的已登记 bundle ID 集合。
  每个 ID 必须在 `operation-registry.json#operation_bundles` 登记且 `service_kind` 与本响应逐字相同；展开后的
  `(operation_id,binding_kind)` union 是唯一 wire 可达性真源。该集合只表示 wire 可达，不构成 profile claim。
  每个可返回 role-scoped Describe 的角色都 MUST 至少公告本角色的
  `ak.operation_bundle.<service_kind>.describe.v1`；该 bundle 唯一成员为
  `(ak.server.read.describe.v1,http_json)`，所以本字段不得为空。
- `trust_domain: ak:trust_domain:<scope>` — 部署级 replay boundary。客户端 / 接收方 MUST 要求它与 Realm create-locked trust domain、federation header 和本地 receive context 一致；不一致时不得接受 replay-sensitive proof。
- `supported_features: feature_id[]` — 服务有实现代码、但 **不一定** 通过 conformance verification 的 feature。
  构建 conformance matrix 的工具 MUST 把它视为严格弱于 `claimed_profiles`。
- `claimed_profiles: [{profile_id, claim_kind: "self_claimed", ...}]` — 服务自声明加入的 profile。
  `claim_kind` 当前固定为 `self_claimed`；Conformance Verifier 验证结果 MUST 改写到 `verified_profiles`，不得复制到本字段。
- `verified_profiles: [{profile_id, claim_kind: "conformance_verified", verification_run_id, artifact_digest, artifact_ref, verifier_id, signature, timestamp, expires_at?}]` —
  附带 verification run 标识、artifact hash、artifact 获取位置或 transparency-log 引用、verifier identity、签名与验证时间戳的已验证 profile。`verifier_id` 承载稳定 verifier `did_core_id`；artifact proof 的 verification-method DID URL 必须取 bare `did`，经已登记 adapter 验证并投影到该值，不得把DID 填入此字段。签发主体是中立角色 **Conformance Verifier**（定义见
  [`conformance-suite.md`](../conformance/conformance-suite.md) §6.2）。**约束**：当 `development_mode=true`
  时，本数组 MUST 为空——dev / placeholder proof 路径不得用来宣告生产 conformance（见本节 §3.0）。
- `interop_surfaces: [{name, kind, since?, notes?}]` — Arkret v1 conformance 之外的 surface：
  被桥接的第三方协议，以及代他方承载的 resolver 姿态
  （`kind` ∈ {`matrix_passthrough`, `mimi_passthrough`, `delegated_resolver`, `external_interop`}，
  该枚举是封闭的；`delegated_resolver` 用于本服务并不自称 canonical 权威、
  但代其暴露的 DID document / key-log 表面，见
  [`../conformance/conformance-profiles.md` §9](../conformance/conformance-profiles.md)）。
  这些 surface **不构成** Arkret v1 conformance 的一部分。
  服务 **MUST NOT** 用 `interop_surfaces[]` 声明自身的产品私有 route root——
  产品私有 API 既不是被桥接的外部协议，也不是委托解析，枚举中没有它的成员；
  该声明会让私有前缀获得它并不具备的"贴近 conformance"地位，
  并在 discovery 面上把它暗示为 canonical path 的 fallback。
  item 对象是封闭的（`additionalProperties: false`），扩展键不能用作绕过路径。
- `development_mode: boolean` — 必填；为 `true` 时 `verified_profiles` MUST 为空。省略不是 false，SDK / conformance tooling MUST 把缺失视为 invalid describe。
- `egress_network_policy` — 可选的出站网络策略摘要。会解析 DID、联邦 peer、媒体、snapshot、Webhook、Applet 或 Agent endpoint 的服务 SHOULD 暴露粗粒度策略；完整 SSRF 防护语义见 [`api-conventions.md`](./api-conventions.md) §11.2。
- `receive_policy_constraints` — Station 可选的部署 / 管理员级接收策略上限。它约束 `ak.peer.invites.command.submit.v1` 与 `ak.peer.contacts.command.submit.v1` 对 `locator_ref`、`handle_claim`、`explicit_address` 等 introduction evidence 的处理；客户端 MUST 把它渲染为“服务器约束”，不得把它当作 subject 自愿公开。语义见 [`invite-addressing.md`](./invite-addressing.md) §5.2。

实现 MUST 明确区分 endpoint 可达性、feature 实现、profile claim 与 conformance verification：

1. 在 describe 响应中同时输出上述 claim-level 字段。
2. dev / placeholder posture 下，自检 `verified_profiles == []` 并在初始化时 fail closed。
3. conformance 报告工具与 admin 等下游 MUST 按 claim level 渲染不同 badge：`self_claimed`、`conformance_verified`、
   `experimental`、`compat`、`not_claimed`。
4. `verified_profiles` 是给 Conformance Verifier、管理员与独立审计方使用的 portable claim，不是普通产品客户端的运行时准入输入。上述角色在使用生产 conformance 结论前 MUST 通过 `artifact_ref` 或等价 transparency log 取得 verification artifact，校验 `artifact_digest`、`verifier_id`、`signature`、时间戳和可选 `expires_at`。普通 authenticated self 客户端既不得只信任服务自报，也不得自行下载该 artifact 或验证发行者历史：没有某个具体 operation 已登记的自己 Station 结果时，只能把该 profile 显示为未验证/不可用，不能据它启用能力。v1 不登记通用 conformance-result 查询。

`plaintext_visibility.data_classes` 是机器可判定的明文类别白名单。`event_kinds`、`payload_paths`、`blob_purposes` 和 `projection_outputs` 只是进一步缩小或解释范围，不能替代 `data_classes`；`notes` 只供人读。Realm policy 的 `plaintext_visible_services[].data_classes` MUST 是目标 `ServiceDescribe.plaintext_visibility.data_classes` 的子集，且 `visibility` 不得高于 `max_visibility`。若 describe 缺失 `data_classes` 或只给出自由文本 `purposes`，客户端 / reducer MUST 把它视为不能接收私有明文。

#### 3.0.1 Bundle 展开与 transport 求交

消费方 MUST 按下列固定顺序处理能力：

1. 要求 `supported_operation_bundles[]` canonical 升序、无重复，并逐项查本地 registry。未知
   `ak.operation_bundle.*`、非 `ak.operation_bundle.*.v1` ID、或 bundle 的 `service_kind` 与响应不符时，整个能力决策
   fail closed；不得解析 bundle 名称或从 profile/surface 猜成员。
2. 展开每个 bundle 冻结的 `(operation_id,binding_kind)`，取 role-local union；同一 pair 重叠表示无效 Describe。
3. union 中每种 `binding_kind` 都 MUST 至少有一条同 kind 的 `transport_bindings[]`；没有 endpoint 覆盖的 pair 不得公告。
   `transport_bindings[]` 的数组顺序就是 endpoint 偏好，首个本地可用且满足 profile/limit 的 endpoint 获选，不另设
   额外排序字段。
4. operation 的 request/response/error schema、success shape、retry/idempotency 与 effect 从该 exact
   `operation_id` 的本地 versioned registry closure 取得，Describe 不再复制这些静态字段。没有本地 exact version 就不调用，
   不按 payload shape 或相邻版本推导。
5. `supported_features[]` 只能在其 feature-registry 前置 operation pair、profile 与 limit 全部满足时启用；feature 不能增加
   bundle union 中不存在的 operation。profile 同样不能推导实时 route。

`ak.operation_bundle.*.v1` 是 current-v1 唯一可上 wire 且必须登记的 operation bundle 命名空间。current-v1 不定义
vendor bundle wire namespace；厂商私有集合不得进入 `supported_operation_bundles[]`，只能作为不影响任何协议决策的可忽略
`x_*` metadata。current-v1 也不接受旧扁平 operation 广告、transport 内嵌成员清单、无版本 operation alias、双读或 fallback。

### 3.1 Identity Resolution Surface

Identity Resolution Surface 是 DID method resolver、registry、witness、watcher 或 method-specific verifier 的统一抽象。`did:plc` 可以由 PLC directory、mirror 或 audit source 实现；`did:web` 可以由 HTTPS / DNS resolver 实现；`did:webvh` 可以由 DID log、watcher 和 witness 实现；`did:key` 可以只由本地 resolver 实现，不需要网络 API；`did:keri` 可以由 KERI log、witness、watcher 和 OOBI discovery 实现。

网络型 identity registry 至少应提供以下语义：

#### 3.1.1 描述 registry

```text
GET /_arkret/root/identity/describe
```

本 operation 是 `ak.root.identity.registry.read.describe.v1`，响应 MUST 是 §3.0 的
canonical role-scoped `ServiceDescribe`（`service_kind=identity_registry`），schema 为
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)。它与
`server/describe` 共用同一个封闭 shape，本节不定义额外顶层字段。

因此 registry 的部署形态 MUST 通过既有 canonical 字段表达，不得新增顶层裸字段：

- 可调用面：`supported_operation_bundles`。按 §3.0，该角色 MUST 至少公告
  `ak.operation_bundle.identity_registry.describe.v1`；本 operation 自身属于
  `ak.operation_bundle.identity_registry.http_core.v1`，因此能返回本响应的部署也 MUST 公告它；
- 已实现能力与 conformance 立场：`supported_features` / `claimed_profiles` /
  `verified_profiles`；
- 协议版本与配额：`protocol_version`、`limits`。

写者 / 见证者 / 副本这类运行姿态与 receipt 承载形式都不是 v1 协议决策输入：它们 MAY 作为顶层
`x_*` 展示 metadata 出现，且按 §3.0 的 `x_*` 规则，删除全部 `x_*` 后
operation / transport / feature / profile / 认证 / 授权 / route / 错误分类 MUST 完全不变。
需要影响上述结果的第一方字段 MUST 先登记为 closed schema 字段，不得以本节摘要为由绕过。

#### 3.1.2 获取当前 DID Document

```text
GET /_arkret/root/identity/document?did=<did>
```

返回 SHOULD 包含：

- 当前 materialized DID Document
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

**返回 method-native 形态，Arkret 不定义自有的日志信封（normative）**。响应是
`IdentityLogListOutcome`：`method` 声明该日志属于哪个 DID method，`entries[]` 是**逐字原样**的
method-native 条目。对 `did:webvh`，每条就是其 `did.jsonl` 条目，携带原生 `versionId`、
entryHash 链与 Data Integrity proof；验证完全按 `did:webvh` method specification 进行。

服务端 MUST NOT 重新编号、重新链接、重新签名或以任何方式重解释这些条目，也 MUST NOT 定义
平行的 digest / hash chain / proof transcript —— 对同一份历史存在第二套各自签名的表示时，
两者可能不一致而规范无法裁决谁为准。规范性说明见
[`../identity/identity-did.md` §4.4](../identity/identity-did.md)。

**没有原生历史的 method MUST 如实报告**：`did:web` 的响应 `native_history=false` 且 `entries` 为空。
服务端 MUST NOT 合成它并不具备的条目、序号或链。


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

Events API 是 Station 提供的 signed Event 提交、读取、回填和前沿查询接口。普通部署 SHOULD 由 Station 直接暴露 `/_arkret/self/events/*`。

Arkret v1 不规定 Event 在服务端的物化形态——不要求集中式 record 仓库、提交日志或仓库命名接口。Station 可以托管、复制或索引 Event,但接收方仍必须验证 Event 签名、DID 控制链、canonical hash、`actor_seq` 路径递增、`prev_refs` Event 因果依赖、`refs[role=authorized_by]` 所指不可变 grant record 及 `event_id` 幂等性。

Events API 至少应提供以下语义：

### 4.1 描述 Events API

```text
QUERY /_arkret/self/events/describe
Content-Type: application/json

{}
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

请求体是一个 `EventInitialSubmission {event, authorization_lease?, cbs_proof_bundles[]?}`，
或 `{events: EventInitialSubmission[]}`。发布证据不进入 Event digest-preimage canonical bytes。

要求：

- 同一个 `event_id` 重复提交相同 digest-preimage canonical bytes MUST 幂等成功；仅
  `proofs` / `unsigned` 等 excluded 字段不同不构成 hash collision，仍须按各自字段合同验证。
- 同一个 `event_id` 若 digest-preimage canonical bytes 不同 MUST 整组 quarantine，并以
  `witness_disagreement` 记录完整 hash collision evidence。
- 服务 MUST 验证 Event 签名、actor DID、device/session、AuthorizationLease、CBS basis、
  capability、Realm policy、`actor_seq` 和因果依赖，并在 lease 到期前持久化签发 IngressReceipt。
- 服务 SHOULD 返回 accepted event、当前 actor frontier、Realm frontier 以及 read-your-writes barrier `cursor`（schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)，purpose=`barrier`）。

批量提交的处理顺序、依赖可见性、frozen authorization basis 与 partial-accept 原子边界统一以 [`operations-sync.md` §5](./operations-sync.md) 为准；本 surface 只声明该 operation 属于 Events Surface。

### 4.3 获取单个 Event

```text
GET /_arkret/self/events/{event_id}
```

不可见或不存在的 Event MUST 使用统一 `not_found` 语义，除非调用方有审计/管理权限。

### 4.4 批量获取 Event

```text
QUERY /_arkret/self/events/resolve
```

请求体可携带一组 `event_ids` 或 `event_digests`。响应按 Realm policy、history visibility、E2EE envelope policy 和 redaction policy 过滤 payload。

### 4.5 列出 / 回填 Event

```text
QUERY /_arkret/self/events
Content-Type: application/json

{"actors":["ak:did_core:web:alice.example"],"realms":["ak:realm:..."],"before":"ak:cursor:...","limit":100}
```

参数完整定义与"近邻先返回"默认顺序规则见 [`service-http-binding.md` §3.3](./service-http-binding.md)。

用于：

- actor 历史恢复
- Realm 审计回放
- 补齐缺失 Event
- 从 snapshot frontier 后继续 reducer replay

### 4.6 获取 Event frontier

```text
QUERY /_arkret/self/events/frontier
Content-Type: application/json

{"actor_id":"ak:did_core:web:alice.example"}
```

返回调用方可见范围内的 actor frontier、Realm frontier、latest HLC、可选 witness receipt / event batch receipt。frontier 只用于同步和强一致读取，不能替代 Event 集合本身。

## 5. Account Aggregate / Snapshot Surface

Account Aggregate / Snapshot Surface 是 Station 提供的 **账号视角聚合** 能力 + snapshot 入口。逐 Realm 的事件查询和实时订阅走 Events Surface（`ak.self.events.read.scan.v1` / `ak.self.events.stream.subscribe.v1`，见 `service-http-binding.md` §3.3 / §3.4）。该 surface 不是独立第三方服务器角色，本质是 Station 上聚合多 Realm frontier、to_device、account_data、device_lists 与 unread / notification counts 的视图；presence 是有界 TTL 的 encrypted Signal，走 Signal live rail，不进入该聚合。客户端只应使用本 principal 控制/委托的 Station、对方 principal 控制/委托的 Station，或 Realm policy 明确列出的 shared notary / Station sync surface。

本节定义 account 与 snapshot 两类操作（事件流读取请到 Events Surface）：

- `GET /_arkret/self/account/viewer`：当前 holder 的账号主体自读（`ak.self.account.read.viewer.v1`）。响应使用 signed handle claim / ref / digest，不把未签名裸 `handle` 作为账号权威字段；请求无 authority selector，跨 PCR lineage 只有唯一 accepted Profile 时才返回 `profile`，歧义时省略而不隐式选择 current PCR。
- `POST /_arkret/self/account/profile`：当前账号 holder-signed Profile Event 提交（`ak.self.account.command.update_profile.v1`）。closed body 只携 `profile_event: EventInitialSubmission`；Event `realm_id` 选择该账号的本地 PCR lineage，`actor_id` 必须是与 session exact `AccountId` 逐字段相等的 account ActorId。无 accepted Profile 时接受 ID 从 Event 派生的 `ak.profile.create`，已有 Profile 时接受 target_ref 命中的 `ak.profile.update`。update patch 路径仅限 `display_name`、`avatar_blob_ref`、`profile_fields.<key>`；Event `preconditions` 为空，并发只使用 update payload 可选 `expected_state_digest`。
- `GET /_arkret/self/account/subscribe`：客户端账号视角聚合同步（`ak.self.account.stream.subscribe.v1`），见 `client-sync.md`。
- `GET /_arkret/self/account/describe`：account aggregate service describe（`ak.self.account.read.describe.v1`）。
- `POST /_arkret/self/account/cursor/revoke`：撤销账号聚合订阅 cursor（`ak.self.account.command.revoke_cursor.v1`）。
- `GET /_arkret/self/realm-state-snapshot/head`：snapshot manifest 入口。

`ak.self.account.command.update_profile.v1` 的 accepted Profile effect 恰好一次推进该 account pair 的 account-aggregate projection/cursor，使同一 pair 的其它绑定设备在 PCR Realm delta 中观察 canonical Event / Profile；exact replay 不产生第二条 delta，account-scoped wakeup 也不是真相源。

事件流读取统一在：

- `QUERY /_arkret/self/events` + JSON content（`ak.self.events.read.scan.v1`，双向 cursor；`before` 取历史方向，`after` 取未来方向。详见 [`service-http-binding.md` §3.3](./service-http-binding.md)）
- `GET /_arkret/self/events/subscribe?realm_ids=...&catchup=...`（`ak.self.events.stream.subscribe.v1`，可从 `after=` 追赶到当前 frontier，并支持重复 `realm_ids` / `actor_ids` selector）

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
GET /_arkret/self/realm-state-snapshot/head?realm_id=<id>
```

用于拿到当前推荐 snapshot manifest：响应即完整 `ak.schema.realm_state_snapshot.v1` manifest（不含 chunk bytes），chunk bytes 经 manifest `chunks[].chunk_ref` 走 blob surface 获取。v1 的 `snapshot` namespace 仅 `ak.self.realm_state_snapshot.read.manifest_head.v1` 一个 canonical operation；snapshot manifest 与 chunk 的防投毒校验流程见 §11。无法产出真实签名 manifest 的部署 MUST NOT 宣告本操作并 MUST 返回 `not_implemented`，不得伪造证明字段。

### 5.3 Event / Seal 状态与 Bottom 暴露

Sync 响应 SHOULD 在每条 reducer-input Event 上携带其当前协议状态字段（`event_state`），取值与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §13 失败状态表一致：`data_local` / `data_observed` / `control_pending` / `control_sealed` / `failed_precondition` / `failed_plane` / `failed_bottom` / `rejected_seal` / `fork_quarantine`。

普通 `causal_register` 的多头 MUST 完整保留；通用 current result 返回 `status=heads`，需要单值却不能确定结果的消费面返回 `unavailable` 并附冲突诊断。不得把多头当成权限或到达顺序赢家。

诊断的唯一 closed shape 见 [`bottom.schema.json`](../../artifacts/schemas/bottom.schema.json)：固定 `kind="conflict"`、ordinary `cell_ids`、按 Event id 排序的 typed `heads[{event_id,value}]` 与可选 `escalated_at`。它不是 Cell 状态、命令 outcome 或安全恢复载体；不得使用额外的 `cells`、`basis`、平行 `event_ids`、free-form details 或 Seal 镜像。安全 Cell 只有唯一已确认 revision；缺依赖保持 unavailable，已证明的安全确认分叉停止争议后继的授权消费，不能通过通用 recovery 生成另一条合法 lineage。

`event_state="fork_quarantine"` 表示争议 Event 被隔离，按 [Actor 分叉规则](../authz/event-auth-state-resolution.md) §15 处理；它不允许重写已经确认的安全历史。`bottom_escalation_after_ms` 只控制普通冲突的带外提示；超时不选赢家、不扩权。

`/_arkret/self/account/subscribe` / `/_arkret/self/events` 只在各自 schema 已登记的位置携带诊断，精确字段由 OpenAPI 与对应响应类型决定。

### 5.4 明文与服务信任

如果 Realm 未启用 E2EE 或内容层加密：

- 客户端 MUST NOT 将 message body、comment body、附件明文或可逆派生摘要提交给未授权第三方服务。
- `events`、`sync`、`sync/subscribe`、`sync/backfill` 的服务端必须是 principal DID、Organization DID 或 Realm policy 明确委托的 Station。
- Directory、Push Gateway、Blob preview、Policy preview，以及任何协议外 search / projection 服务，若会接收正文、正文摘要、附件预览、全文索引或可逆派生内容，MUST 在 Realm policy 中声明为 `plaintext_visible_services`。
- shared notary / Station sync surface 若可见明文，必须在 Realm policy 中作为明文可见方列出。
- `encryption_profile="none"` 只说明 content 未使用 E2EE；它不自动授权任意服务保存、索引、导出或生成可逆派生内容。只有 Realm 同时把内容声明为 public content（例如 `history_access=all_history_for_current_members` 且 preview / export policy 允许 public processing）时，服务才 MAY 按公开内容处理；否则仍按私有明文执行 `plaintext_visible_services` 检查。
- 接收方 Station 可以看到投递给该接收方的非加密内容；客户端和 Realm policy MUST 把这视为内容可见边界，而不是透明中继。
- 非受信服务只能接收公开内容、密文 envelope 或不可解析 payload。

## 6. Search / Projection Semantics

Arkret v1 不定义必需的远端索引或应用视图服务面。当前态查询、View projection、inbox、notification 和全文搜索默认属于客户端或 SDK 的本地派生能力；客户端可以根据已同步且已授权、已解密的 Event 集合自行维护本地索引，也可以完全不提供搜索功能。

实现 MAY 提供协议外或扩展 profile 的受托 search / projection 服务，但该服务不是核心协议角色。任何此类服务都不得成为真相源；其输出必须能追溯到 signed Event、reducer profile、View definition 和 causal frontier。

### 6.1 结构化查询形状

若客户端、SDK 或可选受托服务对外暴露可互操作查询语义，SHOULD 复用 `query-schema.md` 中的 Query 形状：

- `object_kinds`：标准对象类型，例如 `realm`、`space`、`strand`、`message`、`morph`（Space 通过 `space.kind` 区分 board/list/...；Strand 默认入口通过 track primary 解析规则得到）
- `morph_kinds`：当 `object_kinds` 包含 `morph` 时，可进一步限定开放对象类型
- `facets`：schema-declared capability hint 选择器，只用于 Morph 或声明支持 facets 的标准对象；不得作为授权、状态机、排序或 reducer 语义的唯一来源
- `relation`
- 过滤条件
- 排序
- cursor
- limit
- `view_id`、`projection` 与 `renderer`：非 raw projection SHOULD 使用核心原语 `collection` / `timeline` / `graph` / `document` / `composite`；例如看板展示使用 `projection="collection", renderer="board"`。
- barrier `cursor`：可选。若实现支持读己之所写等待，则必须把等待条件绑定到本地已知的因果前沿，例如特定 `event_id` / event hash / Realm frontier。Wire 形态与 stream cursor 共享 `ak:cursor:<base64url>`，由内部 `purpose` 字段区分（见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 与 [`api-conventions.md` §7](./api-conventions.md)）。

barrier cursor 在 Query / Projection 语义中是读己之所写 barrier，不是 Client Sync 的 stream cursor / `after=` resume token。实现 MAY 把它编码为 opaque token，但内部 MUST 绑定调用方、`realm_id`、目标 `event_id`、event hash、filter / query hash、服务 DID 和过期时间。Projection 服务收到该 cursor 时，应等待本地可验证 frontier 覆盖目标事件；若等待超时返回 `timeout`，若服务本地 frontier 明确落后返回 `frontier_stale`，若服务暂时无法追赶或不可用返回 `temporarily_unavailable`。Client Sync 仍必须只使用 [`client-sync.md`](./client-sync.md) 定义的 stream cursor 作为 `/_arkret/self/account/subscribe after=`。

### 6.2 Strand Discussion / Context Projection

Strand context timeline、Strand discussion timeline 和 Strand context projection 是客户端展示形态，不要求远端 endpoint。无论在客户端本地还是受托服务中执行，Strand 的所有 track 都按 Strand 的 effective scope 执行 membership / history visibility 检查：`Strand.scope_circle_id=null` 时按父 Realm；`scope_circle_id` 指向 [Circle](../models/circle.md) 时按该 Circle 自身 policy 与 membership 独立裁剪。Synthesis 与 discussion 同 scope，可见性同源。不得因为 Strand 在某 scope 可见就授予其他 scope 或 Board/List 或其他 Realm 对象权限。

### 6.3 Inbox / Notification Projection

Inbox 和 notification 可以由客户端从本地 Event、read cursor、mention Relation、assignment Relation 和 actor-private account data 派生。若受托服务生成 inbox preview、通知摘要或可逆派生内容，必须满足本节明文边界。

### 6.4 全文搜索

全文搜索是可选功能。请求形状 MAY 使用：

```json
{
  "query": "legal review",
  "realm_ids": ["ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"],
  "object_kinds": ["message", "strand", "morph"],
  "morph_kinds": ["comment"],
  "sender_actor_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
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
  "next_cursor": "ak:cursor:eyJleHBpcmVzX2F0IjoiMjA5OS0xMi0zMVQyMzo1OTo1OS4wMDBaIiwiaCI6ImFiY2RlZmdoaWprbG1ub3BxcnN0dXYiLCJpc3N1ZWRfYXQiOiIyMDk5LTEyLTMwVDIzOjU5OjU5LjAwMFoiLCJwdXJwb3NlIjoic3RyZWFtIiwidiI6IjEifQ",
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
- `organization_id`
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

Actor / handle directory MUST NOT return pairwise DID、private DID、private handle、未披露组织账号或仅因共同 Realm 推断出的关系。`search-users` 只做候选发现；`resolve-handle` 在 claim、audience、requester policy 与 intent 验证通过后 MAY 返回 exact `account_id: AccountId` 与 signed claims。`resolve-agent-selector` 只做精确 agent compose-time 解析。`list-handles-for-subject` 列出当前 context 可见 claims。Directory 结果是寻址证据，不是 membership、Contact consent 或 delivery authorization；目标服务只从 AccountId/ActorId 内的 Station identity 做标准 service resolution。语义边界回指 [`invite-addressing.md` §9](./invite-addressing.md)。

### 8.6 私密联系人发现

```text
POST /_arkret/find/directory/private-contact-discovery
```

该操作用于 `ak.private_contact_discovery.v1`。Directory advertise 本操作时 MUST 同时提供闭合的 `ServiceDescribe.private_contact_discovery`（RFC 9497 modeVOPRF、公钥 / epoch、固定 batch、proof shape、response buckets、completion TTL、quota 与 delay distribution）。客户端在发送前把 blinded batch 填充到精确 `batch_item_count`；blind / match / outcome 数组保持等长同序。响应只返回 PSI 命中位图与按 describe 固定为 always / never 的最小 invite/consent handoff stub；MUST NOT 返回 contact request token、reachability proof、原始 identifier、完整 profile、成员列表、Realm membership 或关系图谱。PSI quota 只在首次 blind 准入时执行；超额返回 padded 429 `psi_quota_exhausted` + 量化 `Retry-After`，不得伪装成 200 no-match。完全相同的 blind / match 重试不重复计数并返回缓存 outcome；同 batch_id 不同 canonical body 返回 `duplicate_conflict`，未知 / wrong-device / expired batch 统一返回 `psi_batch_unavailable`，pinned epoch 必须保留完整 completion TTL。逐目标失败一律编码为固定 cardinality 位图中的未命中位；精确 entity-body bucket 与 delay 规则见 [`../discovery/discovery-directory.md` §6.4](../discovery/discovery-directory.md)。联系人请求与 direct conversation resolver 的正式语义见 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。

## 9. MIMI Provider Facade Surface（extension profile）

MIMI Provider Facade 不属于 v1 core service surface。完整定义见 [`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)（标记为 interop extension profile）。声称 v1 core 的实现 **不要求** 提供 `/_arkret/open/mimi/*` 路径；只有显式声明 `ak.profile.mimi_interop.v1` 的部署才暴露该子面。

## 10. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 Event，但服务层仍需要可查询面。

至少建议提供：

```text
GET /_arkret/self/authz/effective-grants?realm_id=<id>&subject_actor_id=<percent-encoded-JCS-ActorId>&at=<timestamp?>
```

`subject_actor_id` 保留完整 Actor 分支与 Station，包括 Account 与 Service；省略时仅取已认证 credential 的完整 Actor。旧 `subject`、`subject_station_id`、`subject_account_id` query 参数 MUST 拒绝，不得重建或猜测远端 Actor。

```text
GET /_arkret/self/authz/invites?realm_id=<id>&subject=<did_core_id>&subject_station_id=<did_core_id>
```

Invite 查询的 `subject` 与 `subject_station_id` 共同定位完整 `AccountId`，显式指定时 MUST 成对出现。二者均省略仅查询已认证 credential 的精确 Account；不得用 handle、裸 principal、URL 或当前服务猜补 Station，也不得把同 DID 的另一 Station Account 视为本人。

```text
POST /_arkret/self/authz/check
```

`check` 接口适合：

- Events API 接收写入前预检查
- Station sync surface 分发前快速过滤
- client 发送前本地 UX 提示

## 10.1 Agent Surface

Agent 的 management、pairing、session grant 与 Sidecar operations 属于 self / gate trust surface 上的语义操作；canonical HTTP path、request/response schema 与 binding completeness index 由 [`service-http-binding.md` §2.4.1](./service-http-binding.md) 维护，本文只声明语义边界。实现 MUST 使用 operation catalog 中登记的 `ak.self.agent.*`、`ak.gate.account.*` 与 `ak.self.agent.sidecar.*` 操作名，不得从本节散文推导额外路径、profile id 或快捷授权。

约束:

- 本 surface 不引入 custom URI scheme(`arkret://` 等);所有 deep-link 由客户端用 deployment 已知的 `arkret_base_url` 拼接标准 HTTPS URL,移动端依赖 OS Universal Links / App Links。
- `pairing_request_id` 与 `approval_request_id` 都是 account/auth profile-local opaque UUIDv7 短期 artifact,不是 `ak:<kind>:<uuid>` 协议对象 id;agent runtime 收到 `approval_request_id` MUST NOT 解释成 URL 或尝试打开 UI,只能由 controller 的人类 session 带外查询。
- `{agent_id}` 是 DID,在 URL path 中 MUST 按 RFC 3986 percent-encoding。
- `ak.self.agent.command.provision.v1` MUST 接收非空 `slug`；`slug` 是 Agent 自身的固有字段，因此 provision request 与 list/get projection 均使用裸名 `slug`。controller 签署的唯一 `ak.agent.provision` Event 在一次 reducer transaction 中派生当前 selector projection，其中引用 Agent selector 的字段使用 `agent_slug=slug`；服务端不得另造 `ak.agent.selector_claim` Event。controller E2EE client MAY 在随后由其本地生成并加密提交的 Agent Actor Profile 中写入 `agent_slug` 作为投影 hint；服务端不得代写该 Agent PCR Profile。`agent_slug` 只用于 `@<controller-handle>/<agent_slug>` 输入别名到 agent principal DID 的 compose-time 解析；服务端 MUST 拒绝或 fail closed 处理同一 verified controller 下 active Agent 的 selector claim 冲突。
- participation replace/get 都是 controller-only。replace body 固定为 `{target_scope,selection,expected_version}`，GET 与 replace outcome 的 entry 固定为 `{target_scope,selection,version,next_replace_input:{expected_version}}`，且 `next_replace_input.expected_version=version`。Account Authority 只校验 controller、closed scope/五位 shape 与 CAS version；selection 可以表达希望开启但当前 policy/capability 尚不允许的位，因为它本身不产生权限。
- `ak.gate.account.command.issue_session_grant.v1` 为 agent runtime 签发 session 时，若 scope request 覆盖 participation-aware scope，签名 SessionGrant claims 的 `scope_details.participation[]` MUST 使用与 `agent_participation_entry` 同构的 `{target_scope,selection,version,next_replace_input:{expected_version}}` 条目，且 `next_replace_input.expected_version=version`。HTTP `SessionGrantOutcome` 不复制 `scope_details`。runtime 可据此避免无效动作；target 的授权只来自已验 JWT/introspection，并且必须在动作时读取当前 deployment/Realm/Circle/Strand policy，独立校验 capability、session scope、membership 与 lifecycle，不得信任客户端复制的预计算 ceiling/effective。

详细 wire 规则见 [`service-http-binding.md` §2.4](./service-http-binding.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)、[`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md)、[`../models/circle.md` §11.1](../models/circle.md)、[`../models/private-objects.md` §4.1](../models/private-objects.md) 与 [`../authz/capabilities.md` §5](../authz/capabilities.md)。

## 11. Realm Bootstrap Strand

Arkret v1 的首次加入流程：

1. 用户输入 handle、DID 或 Realm link。
2. 客户端向自己 Account Station 解析输入；服务器验证公开 handle 双向绑定、外部 DID/service authority、Directory/invite 元数据与 Realm 加入依据。
3. 客户端核对服务器准备结果的 canonical Realm、自己的 actor、请求动作及披露信息，签署确切准备字节并提交自己 Station；联邦 forwarding 由服务器完成。
4. 服务器按当前请求权限提供 Realm metadata、当前治理/安全状态及必要内容。未取得依据时返回适用 pending/unavailable，不得伪装为空的成功基线。
5. 需要 Snapshot 时从自己 Station 获取 manifest，并按请求范围下载 chunks。服务器验证外部 manifest 的 issuer、authority、witness quorum、state/event commitments 和治理历史；客户端核对来源、Realm/basis、下载内容 hash 与端到端认证，不执行 witness/DID/history 重放。
6. 使用服务器返回的合法 cursor 接续内容增量；不得把 frontier Event IDs 填入 cursor，或因 snapshot 不可用回退客户端全历史验证。
7. 运行内容显示/解密所需的本地归约，建立 read cursor、notification cursor 等个人状态。首屏与其它 Realm 不等待该 Realm 的完整内容历史。

## 12. 新鲜度与多服务并存

当多个 Station 或受托 search / projection 扩展并存时，相关服务 SHOULD 公开：

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

- Events / Station sync surface MAY 不解密正文
- 但仍 SHOULD 保留 hash、cursor、causal 与目标引用

## 14. 防滥用与配额机制 (Anti-Spam & Quota)

在去中心化网络中，计算、存储与带宽都是稀缺资源。协议要求所有提供写入或传播服务的节点实现必须具备防御恶意滥用的能力：

### 14.1 存储责任与 Blob Quota
- **成本归属**：Realm 的整体数据大小、历史 Event 数量及附属的 Blob 存储成本，逻辑上必须绑定到 Realm 的 `owner` 或负责托管的 `responsible_actor_id`。
- **拒绝写入**：当 Blob 服务或 Station 评估该 Realm 占用的资源已超出预设的 Policy 配额 (Quota) 时，MUST 返回明确的协议错误语义（例如 `quota_exceeded`、`payload_too_large` 或 profile 注册的付费/资源门槛错误），并拒收新写入的 Event 或大文件 Blob。HTTP status 映射属于 binding 层，见 [`api-conventions.md` §5.1](./api-conventions.md) 与 [`service-http-binding.md`](./service-http-binding.md)。

### 14.2 写频率控制 (Rate Limiting)
- Events API 和 Station sync surface 节点 SHOULD 基于 `actor_id` 与 `realm_id` 实施严格的并发和频率限制。
- 对于来自未验证或低信誉 DID 的恶意刷写（例如短时间内进行海量无效的 `message.create` 或反复触发高并发图重组），节点有权暂时熔断该 DID 的请求。

## 15. 设计决定

Arkret v1 固定：

- 定义最小 Station / identity registry / events / account / snapshot / blob / authz 服务面
- v1 core 互操作 transport 锁定为 HTTP/JSON（见 [`transport-bindings.md` §1](./transport-bindings.md)）；gRPC / WebSocket / SSE / MQ / libp2p 等其他 binding 仅为 extension profile，本节列出的 operation 形态与字段以 HTTP/JSON 为唯一权威。其他 binding 必须语义等价但不构成 v1 core 一致性。
- 写接口必须幂等
- principal 与 service 的业务引用都使用 `did_core_id`；注册 / resolution 出示 `did`，service 首跳 URL 来自方法验证后的 DID Document 服务入口，describe 只做二跳确认
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
- Service describe MUST 声明 `service_id: did_core_id`、`service_resolution`、`trust_domain`、`service_kind`、`protocol_version="1.0"`、`supported_profiles`、`supported_operation_bundles`、`transport_bindings[]`、`supported_features[]`、`auth_metadata`、`limits`、`rate_limit_policy` 或 `rate_limit_policy_id`、`plaintext_visibility` 与 `development_mode`。其中 `transport_bindings[]` 是数组(每项描述一个 transport binding,例如 `{kind: "http_json", ...}`);单数字段名 `binding` 不出现在 describe response 顶层。客户端 MUST 在使用任何其它 describe 字段前先比较 `protocol_version`；其形状合法但不等于 `"1.0"` 时 MUST 以 `unsupported_protocol_version` 将整个服务标记为不可用，MUST NOT 缓存其路由、对其做 capability 交集或发起业务请求。缺失或非字符串的 `protocol_version` 仍是 `schema_violation`。客户端还 MUST 拒绝 service `did_core_id` / `did` projection、trust_domain、Realm policy 或 profile 不匹配的服务。`plaintext_visibility` 缺失视为该服务**不可信**用作 `plaintext_visible_services` 成员(见 OpenAPI ServiceDescribe schema description)。
- Service describe 响应 MUST 同时给出 `supported_operation_bundles`，并按 §3.0 区分 `supported_features` / `claimed_profiles` / `verified_profiles` / `interop_surfaces` 四个 claim level 字段，schema 见 `ak.schema.service_describe.v1`。当 `development_mode=true` 时 `verified_profiles` MUST 为空；当 `development_mode=false` 且声明 `verified_profiles` 时，客户端仍 MUST 通过 `artifact_ref` / transparency log 获取并校验对应 verification artifact、verifier 签名和 hash 后才把它作为生产 conformance 依据。
- Sync cursor recovery MUST 按 `conformance-vectors.md` 执行：cursor 是 opaque token；过期或缺口时返回可恢复错误，并提供 backfill 起点或 snapshot frontier。
- Event source consistency MUST 按 `conformance-vectors.md` 执行：重复 Event 幂等，冲突 Event 拒绝，event order、hash、签名和 `actor_seq` 必须可复现验证。
