---
title: Service Surface And Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-08-28
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
| Moderation | report intake、local queue、Station ACL 与普通 appeal orchestration。 |

*Table 2-C. 按需出现的独立服务（informative）。只有满足本节保留判据且实际启用时才进入 discovery。*

| 服务 / 基础设施 | 独立边界 |
| --- | --- |
| Identity Resolution Infrastructure / Identity Registry | DID document、method-native log、receipt、witness、watcher、OOBI 与 service endpoint discovery；只有独立可寻址或签名实现才登记角色。 |
| Directory Service | 公共或组织目录、授权发现、anti-enumeration、takedown 与可见性边界。 |
| Blob Service | 仅按 Station 绑定的 contract 执行 bytes storage/delivery，不取得账号、Realm、Event、metadata 或 retention authority。 |
| Media Service / TURN / SFU | transform、delivery、ICE relay 或 selective forwarding；各自按实际 service DID、密钥、可见性与委托边界登记，不使用复合媒体角色。 |
| Push Gateway | 外部投递与 APNs/FCM/厂商适配边界，不持有 Station 业务数据 authority。 |
| Applet Service / Agent Runtime | 受注册授权的扩展服务或执行环境；按 capability 写回，不取得账号业务数据 authority。 |
| Moderation Service | 仅限 Realm/组织显式委托且拥有独立 service DID/签名、plaintext visibility 或 legal-hold authority 的外部审核实体。 |
| Archive Node / Key Recovery Service / Recovery Service | 按实际历史可见性、密钥持有和恢复 authority 分别授权，不得用含混总称赋予全部权限。 |
| Notary / MIMI Provider Facade | 分别为独立密码学角色和互操作 facade；只在相应 Realm/profile 实际委托时出现。 |

REST namespace 第一段路径（`self` / `gate` / `root` / `find` / `peer` / `open` / `edge`，见 [service-http-binding.md §2.1](./service-http-binding.md)）是 **trust-surface classifier（信任面分类器）**，编码"调用方↔服务"的攻击面类别，**不是授权结论**；实现 MUST NOT 把信任面段本身解释为授权通过、安全级别达标或明文可见许可。每个 operation 仍按自身契约执行 session / capability / DID proof / Realm policy / history visibility / rate limit 校验。

#### 2.5.1 Account Authority 与认证方法发现

Station 的根级 `/_arkret/describe` 是客户端登录 / account flow 的启动入口。`auth_metadata.account_authority` MUST 给出一个绝对 `gate_account_base_url`，客户端发起的 Arkret `/_arkret/gate/account/*` 请求都 MUST 从该 base 派生。客户端不得按 operation 猜测内部进程。部署 MAY 在认证 TCB 内使用网关、反代或独立 Auth Server 进程处理这些操作，但该组件是 deployment-private：不得拥有公开 `service_kind`、role profile、service registration、role-local Describe、federation identity 或 peer-discoverable endpoint。`ak.gate.account.command.logout_auth_session.v1` 是 Account Authority 内部终结认证 session 的 typed 子操作，普通客户端 MUST NOT 调用或从 `gate_account_base_url` 派生。

`auth_metadata.methods[]` 只描述认证方法（例如 `oidc`、`passkey`、`device_pairing`、未来 `gnap`）及其 provider / issuer / discovery，不决定 `gate/account` 的路由。OIDC method MUST 使用标准 discovery 与标准 `authorization_endpoint` / `token_endpoint`；Arkret 不定义 `/_arkret/gate/auth/oauth/*` 这类私有 OAuth endpoint family。标准认证结果进入 Arkret 的桥是 Account Authority 的 `POST {gate_account_base_url}/session-grants`，响应为 `SessionGrantOutcome`；Principal 本地 session provisioning 属 Account Authority 内部编排，不得暴露第二个客户端可见的 Principal 本地凭据签发 endpoint。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

Account Authority 内部分派不得改变 operation 的协议身份。尤其 `ak.gate.account.command.pair_agent_key.v1` 依赖 Station 的 pairing record、Agent PCR Event acceptance 与 activation projection 时，split deployment MUST 将原始 typed request 委托到权威 Station 的同一 `/_arkret/gate/account/agent-key-pair` binding，并保留 Event ID 幂等身份；不得把该职责改造成产品私有 `fanout` URL 或只入本地队列后向客户端报告成功。具体 commit 规则见 [`../identity/key-management.md` §3.6.1 / §3.6.2](../identity/key-management.md)。

本登录 / account flow 最多并存三类 origin：Station（发现启动与 wire role）、Station 发布的 Account Authority base（全部 `gate/account` Arkret 操作）和 Authentication Method Provider / issuer（标准认证协议）。前两者即使分 origin 也仍属于同一 Station wire role。完整客户端仍可按其它 spec 访问 Directory、Blob、Media、Push 等独立 service origin；这些不改变 account flow 路由。

Deployment profile 的 canonical 机器真源是 [`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 `deployment_profiles` 集合；本文不得另注册 profile id。下列形态仅是服务角色组合说明，实际部署 MUST 声明 canonical id（如 `ak.profile.personal_node.v1`、`ak.profile.organization.v1`、`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1`）并按 profile registry 校验能力面：

- 个人节点通常部署一个 Station，并按需使用公共 Directory、Push 或 TURN/Media 服务。
- 组织节点 MAY 把 Station 的认证、policy、sync/federation、device/key、Blob bytes 与 moderation worker 拆成内部进程；这些边界不进入 discovery。只有满足独立信任判据的 Directory、Blob、Media、Push 或 Moderation Service 才发布独立角色。
- 高安全或主权部署把 Station 与 Identity Resolution、Directory、外部 Blob/Media、Push、Notary、Archive/Recovery 等已委托服务保持在受控 trust domain；公共服务或 federation ingress 只能作为显式授权的互联入口。
- Applet、MIMI facade、Agent runtime、Moderation、Archive/Recovery 等角色是 service role / capability 组合，不是 deployment profile id；它们只能在已声明 profile 允许的 namespace、capability、Realm policy 与 service describe 范围内工作。

### 2.6 Service `did_core_id` 与首跳路由解析（normative）

服务身份与 principal 身份使用同一个二层模型：业务层持久 `service_id: did_core_id`，首次注册或绑定时必须同时提供可验证 `did`，并由 method adapter 验证 `project(did) = service_id`。因此服务端在业务表中只保存 `did_core_id` 不会失去可路由性；发送前通过已验证的 `ServiceResolutionRecord` 将它映射为当前 `did` 和真实 `base_url`。

从 remote peer、invite/contact carrier、mirror、DNS、DID Document、HTTP redirect 或本地配置取得的 URL/record bytes 一律只是不可信候选，不因传递者已通过 federation 认证而继承可信度。接受方 MUST 对 target-signed record 本身独立执行：canonical digest 与 proof context 校验；从 `verification_method` 取 bare controller DID；由 active method adapter 验证 inception、连续历史、签发时 control/assertion authorization，并确认 `project(did) == record.service_id`；再检查 record chain、freshness、SSRF policy 及下述 Describe reverse binding。传递者只能证明“谁送来了这些 bytes”，不能替 target service 证明“这个 URL 属于该 core”。TLS/WebPKI 只保护到已验证 record 所绑定 host 的连接，也不能单独建立 `did_core_id` 所有权。

`ServiceResolutionRecord` 是签名的首跳材料，至少绑定 service `did_core_id`、`service_kind`、当前 `did`、method history head / version、服务控制历史引用、`record_sequence` / `previous_record_digest`、`current_record_url`、`base_url`、`describe_digest` 以及 `issued_at` / `refresh_after` / `expires_at`。`resolution_event_ref` MUST 按 active adapter row 从同一个已验证状态确定性映射：`did:webvh` 为 `did-webvh-entry-sha256:<hex>`，`did:web` 为 `did-web-document-sha256:<hex>`，`did:key` 为 `did-key-did-sha256:<hex>`。首条 record 的 sequence 为 `0` 且 predecessor 为 `null`；同一 service `did_core_id` 的每个后继 MUST 恰好加一，并以前一份完整 record（包含 proof）的 `sha256(RFC8785_JCS(...))` 作为 predecessor，禁止跳号、复用或回滚。时间必须满足 `issued_at <= refresh_after < expires_at`。`base_url` MUST 是 canonical absolute HTTPS base：scheme / host 小写、去掉默认端口、消解 dot-segment、禁止 userinfo / query / fragment，规范化 path 并且恰有一个 trailing slash。

`describe_digest` 不是对整个动态 `ServiceDescribe` 的摘要，而是
`sha256(RFC8785_JCS(route_binding_projection))`；`route_binding_projection` 仅含
`{service_id, service_kind, service_resolution:{did,method_history_head,version_id}, http_json_base_url}`。
`http_json_base_url` 是对被选中 `transport_bindings[kind=http_json].base_url` 执行上述 canonical URL 规则后的值，不是原始字符串的另一个别名。
`limits`、rate policy、feature/profile claims、verified artifacts 与 `x_*` 扩展不进入该投影，它们的正常变化不应使路由失效。完整 record 的内容地址摘要固定为 `sha256(RFC8785_JCS(service_resolution_record))`，计算对象包含 `record` 和 `proof`。

首跳 carrier 可携带 inline signed record，也可携带
`current_record_url` 与可选 `pinned_record_digest`。该 URL 指向稳定的
`GET /_arkret/open/services/{service_id}/resolution`（`service_id` 按 RFC 3986 percent-encode）返回完整 `AuthenticatedServiceResolution`，canonical
operation 是 `ak.open.service.read.resolution.v1`。响应以当前完整签名 `ServiceResolutionRecord` 为核心，并携带验证该版本所需的 exact method-history evidence 与 normalized DID document。对于 `did:webvh`，evidence **MUST** 携带从 inception 到 record 所钉位置的完整无缺口 native log，以及该区间所有 witness policy 所要求的完整 witness records；resolver 生成的摘要、部分区间或仅当前 DID Document 均不构成历史验证材料。旧
`pinned_record_digest` 只锁定它所属的旧版本，不得用来拒绝在同一 `current_record_url`
上取得的新版本。新版本 MUST 重新验证完整 record digest、service proof、method history、
`project(did) == service_id`、`service_kind`、document digest、时间序和 endpoint 绑定后才能入 cache。
验证成功后，下一次刷新 URL MUST 从新 record 的 canonical `base_url` 加
`_arkret/open/services/{percent-encoded service_id}/resolution` 重新派生；只有响应中的新 record、完整 method-history evidence 与 normalized DID document 已联合验证时，才能用该派生值替换 cache 中的旧 `current_record_url`。这是服务换 URL 的过渡路径，不依赖 HTTP redirect。裸 record、history summary 或未独立验证的 current DID Document 均不足以冻结 notary signer 或验证历史签名。

调用 `GET /_arkret/describe` 已经需要候选 URL，因此 describe 是**二跳确认面**，不是从 `did_core_id` 得到 URL 的首跳 resolver。调用方 MUST 先验证 record，再以 canonical `base_url` 派生 role-scoped describe URL，并确认 describe 的 `route_binding_projection` 与 `describe_digest` 一致。resolution 和 describe 请求 MUST NOT 自动跟随 redirect；如果收到 redirect，调用方只能在另行取得的新签名 record 已绑定新 URL 后重新发起，不得依赖同域名、TLS 或 redirect 自身建立身份。

对 `current_record_url` 的自动抓取属于服务端网络输入，MUST 在 DNS 前后执行 SSRF 防护：默认拒绝 loopback、link-local、private / reserved address、userinfo、非 HTTPS 和 DNS rebinding；只有部署 policy 显式列入的 private service 可例外。解析后地址 MUST 钉住到当次请求，禁止 redirect 与 `Content-Encoding`，响应 canonical bytes MUST 不超过 1 MiB，从连接到读完的总 deadline MUST 不超过 5 秒。超限、超时或地址分类改变均 fail closed。

`ServiceResolutionRecord` 只表达**当前已经生效**的 route；`refresh_after` 只是刷新提示，MUST NOT 被解释为未来激活时间。计划迁移使用与 current record 分离的 closed、portable、由同一 service control identity 签名的 `ServiceRouteHandoverNotice`：

```text
ServiceRouteHandoverNotice {
  service_id, service_kind,
  handover_id, notice_revision,
  state,                         // scheduled | cancelled
  from_record_sequence, from_record_digest,
  candidate_base_url?, candidate_record_url?,
  not_before?, cutover_at?, grace_until?,
  previous_notice_digest?,
  issued_at, expires_at,
  proof
}
```

同一 `handover_id` 的首份 notice 必须使用 `notice_revision=0` 且 `previous_notice_digest=null`；后继 revision 必须恰好加一，并以前一份完整 notice（含 proof）的 `sha256(RFC8785_JCS(...))` 为 predecessor。`scheduled` 必须携带 candidate 与完整时间窗，并满足 `issued_at <= not_before <= cutover_at < grace_until <= expires_at`；`candidate_record_url` 必须从 canonical `candidate_base_url` 加固定的 percent-encoded service-resolution path 机械派生。`cancelled` 必须省略 candidate 与时间窗，并精确引用同一 handover 的前一 revision；它只能取消尚未被接受正式 successor record 的计划。notice revision 与 `ServiceResolutionRecord.record_sequence` 是两条独立序列，发布、修订或取消 notice 均不得消耗 record sequence。

完整 notice 的 content-addressed digest 固定为 `sha256(RFC8785_JCS(service_route_handover_notice))`，计算对象包含 proof。proof 使用独立 domain context `ak.service_route_handover_notice_proof.v1`；其 `payload_digest` 固定覆盖 proof 之外的全部 notice claims，签名 binding 另含 `verification_method`、proof creation time 及 registry 要求的 domain/audience。`verification_method` 的 bare controller `did` 必须经 adapter 投影为 `service_id`，并且该 key 在 `issued_at` 对应的 method/control state 中被授权用于 service assertion。实现不得复用 current record proof context、HTTP Message Signature 或 mirror 签名充当 notice proof。

接收方只有在 `from_record_sequence/from_record_digest` 已经命中本地 durable last-seen record 时，才能接受 notice。publish request 是 exact-one artifact，MUST NOT 在同一个 notice request 中夹带、隐含或原子接受 record chain。若 receiver 落后，publisher 必须先按 sequence 逐份 publish 缺失的 target-signed `ServiceResolutionRecord`，每一份都取得 durable ack 并推进 receiver floor 后，再用新的 request 单独 publish notice；没有最后一份 record ack 时不得声称 notice basis 已补齐或 preannouncement 原子完成。`not_before` 前只允许对 candidate 执行无 Realm、to-device、KeyPackage、repair 或其它业务 payload 的有界 resolution/describe preflight，且不得更新 effective route。自 `not_before` 起可以尝试读取 candidate；只有 candidate 返回相同 `service_id + service_kind`、`record_sequence=from_record_sequence+1`、`previous_record_digest=from_record_digest` 的正式 current `ServiceResolutionRecord`，并通过 method history、freshness、SSRF 与 describe reverse-binding 验证后，才能切换业务流量。`cutover_at` 是优先切换点，旧入口应继续服务至 `grace_until`；notice 本身、mirror ack、candidate 可达或 TLS 成功均不授权业务投递。正式 successor 已接受后，迟到 cancellation 不得回滚 route；要回到旧 URL 必须再发布连续的新 record。

对每个实际存在业务授权关系的 remote `service_id`，实现 MUST 在独立于 TTL cache 的 durable anti-rollback ledger 中保存至少 `{service_kind,last_seen_record_sequence,last_seen_record_digest}`，并在把新 route 用于业务流量前原子推进该 floor。较低 sequence、相同 sequence 不同 digest、跳号或 predecessor 不连续均 MUST fail closed；两个能通过 target proof 的同 sequence 异 digest 也属于 service-control fork，必须 quarantine，不能按到达时间、URL 可达性或 mirror 多数票选 winner。已接受 active notice 的 `{handover_id,notice_revision,notice_digest,state,expires_at}` 与对外签发/接收的 durable ack 同样必须在依赖它进行安全切换前落盘，并保留到取消、完成或过期。进程重启、cache eviction 或 DNS 变化不得降低 last-seen floor。

若迁移同时改变 `did:webvh` 的域名或路径，route handover 与 DID portability 是两条必须按顺序组合的证明链：初始 WebVH 日志必须已启用 portability；owner 在旧 DID/control state 仍有效时签发并分发 notice；candidate host 上必须发布保留同一 SCID、包含从 inception 起完整历史的合法 successor DID log，并按 WebVH 规则在新 DID Document 的 `alsoKnownAs` 引用旧 DID；随后才签发 `record_sequence + 1` 的正式 `ServiceResolutionRecord`，其中 `did`、`method_history_head`、`current_record_url` 与 `base_url` 全部绑定新位置，且 `previous_record_digest` 连续。WebVH `nextKeyHashes` 只预承诺未来更新 key，不表达切换时间、candidate endpoint 或 Arkret 通知范围，MUST NOT 替代 `ServiceRouteHandoverNotice`。same-SCID 迁移保持同一 service core，按本节刷新 route；新建不同 SCID/core 则是 service identity 变更，必须走 member/service rebind，不能伪装成 URL 刷新。

高频投递实现 MAY 另存 `ServiceRouteCache[service did_core_id] -> {service_kind, did, method_history_head, record_sequence, record_digest, base_url, describe_digest, current_record_url, verified_at, refresh_after, expires_at, cache_expires_at}` 的本地 TTL cache。这里 `expires_at` 是 target-signed record 的硬到期时间，`cache_expires_at` 是实现选择的本地缓存到期时间且 MUST `<= expires_at`；二者不得合并、互相延长或只保存本地 TTL 而丢弃 signed expiry。该 cache 是可丢失、可重建的性能优化；它的存储引擎、淘汰算法和后台刷新属于实现层，但绝不能代替前段 durable anti-rollback ledger。`refresh_after` 到达时 SHOULD 通过 `current_record_url` 异步刷新；`cache_expires_at` 或 signed `expires_at` 任一到达、binding / Realm policy 变化、method head 不一致、route-binding digest 改变、签名/授权失效或安全敏感操作时 MUST 取得并验证最新 record。同一 `did_core_id` 下的 resolution / URL 刷新只更新 durable route floor 与本地 cache，不改变 Realm 授权，不需要 member rebind；service `did_core_id` 改变才必须通过新 ActorId change 重新授权。同一未失效 binding 的普通请求 MAY 复用 cache，不得每次在线 resolve DID。

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
    "ak.feature.snapshot.v1",
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
request/response-stream/S2S relay/RRK archive 合同）、`ak.feature.mls_exporter_aead.v1`（接受并同步
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

- service identity bootstrap 的 DID Document entry 唯一使用 `type="ArkretService"`，并以必填 `serviceKind` 取 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json) 中 `valid_in` 含 `service_registration_key` 的值。`ArkretStation` / `ArkretDirectory` 不是 alias，必须拒绝。Organization 与 managed-Agent 的 specialized DID service type 仅使用 [`did-document-contract-registry.json`](../../artifacts/registry/did-document-contract-registry.json) 登记的独立 endpoint shape，不得替代 service bootstrap。
- describe 响应的 `service_kind` 使用 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json) 中 `status=active` 且 `valid_in` 包含 `service_describe` 的小写注册值；正文不复制该闭集。其它 context 的值不得进入 Describe：例如 `mimi_provider_facade` 只用于 `mimi_provider_directory` descriptor，不是 `ServiceDescribe.service_kind`。Realm join candidate 的 `service_kind` 仅允许 `station`，其路由来源只允许 signed invite 或当前 joined-joined-member ActorId routing projection（见 [`realm-join-candidate.schema.json`](../../artifacts/schemas/realm-join-candidate.schema.json)）。
- conformance profile 使用 `ak.profile.*` 标识，例如 `ak.profile.station.v1`。
- 实现 MUST 区分这三层名称，不得把 DID service type、运行时 service_kind 与 conformance profile 混用。

### 3.0 Describe response claim levels

`server/describe`（以及结构等价的 `identity/describe` / `events/describe` / `sync/describe` /
`directory/describe` / `applet/describe`）响应 MUST 使用同一个 canonical `ServiceDescribe` shape。除 `service_id`、`service_resolution`、`trust_domain`、`service_kind`、`protocol_version`、`supported_profiles`、`supported_operation_bundles`、`transport_bindings`、`supported_features`、`auth_metadata`、`limits`、`plaintext_visibility` 和 `rate_limit_policy` / `rate_limit_policy_id` 之外，响应还 MUST 按 **claim level** 区分以下字段；schema 见
[`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)（`ak.schema.service_describe.v1`）：

完整 role-scoped `ServiceDescribe` 的 canonical response body MUST 不超过 1 MiB（1,048,576 bytes），且 MUST 省略 `Content-Encoding`、禁止 redirect。该上限覆盖完整 `supported_operation_bundles[]` 与 `transport_bindings[]` 闭包；实现不得沿用只适用于旧精简 describe 的 64 KiB 本地限制。超过上限的服务 MUST 收窄其 role surface 或拆分为独立 role-scoped endpoint，不得静默截断 binding rows。

`service_id` MUST 是该逻辑角色的 `did_core_id`，`service_resolution` MUST 投影当前 `did` 与 method history position。这个投影只用于将已选定 endpoint 与首跳 `ServiceResolutionRecord` 交叉确认，不能让 describe 变成 resolver，也不能单独创建 service 授权。

顶层 `x_*` 只允许承载可安全忽略的展示、日志或厂商 metadata。对任意合法 Describe 删除全部顶层 `x_*` 后，
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
4. 客户端不得只信任服务自报的 `verified_profiles`；使用生产 conformance 结论前 MUST 通过 `artifact_ref` 或等价 transparency log 取得 verification artifact，校验 `artifact_digest`、`verifier_id`、`signature`、时间戳和可选 `expires_at`。

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

请求体是一个 `EventInitialSubmission {event, authorization_lease?, cba_proof_bundles[]?}`，
或 `{events: EventInitialSubmission[]}`。发布证据不进入 Event digest-preimage canonical bytes。

要求：

- 同一个 `event_id` 重复提交相同 digest-preimage canonical bytes MUST 幂等成功；仅
  `proofs` / `unsigned` 等 excluded 字段不同不构成 hash collision，仍须按各自字段合同验证。
- 同一个 `event_id` 若 digest-preimage canonical bytes 不同 MUST 整组 quarantine，并以
  `witness_disagreement` 记录完整 hash collision evidence。
- 服务 MUST 验证 Event 签名、actor DID、device/session、AuthorizationLease、CBA basis、
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
- `GET /_arkret/self/snapshot/head`：snapshot manifest 入口。

`ak.self.account.command.update_profile.v1` 的 accepted Profile effect 恰好一次推进该 account pair 的 account-aggregate projection/cursor，使同一 pair 的其它绑定设备在 PCR Realm delta 中观察 canonical Event / Profile；exact replay 不产生第二条 delta，account-scoped wakeup 也不是真相源。

事件流读取统一在：

- `QUERY /_arkret/self/events` + JSON content（`ak.self.events.read.scan.v1`，双向 cursor；`before` 取历史方向，`after` 取未来方向。详见 [`service-http-binding.md` §3.3](./service-http-binding.md)）
- `GET /_arkret/self/events/subscribe?realms=...&catchup=...`（`ak.self.events.stream.subscribe.v1`，可从 `after=` 追赶到当前 frontier，并支持多 realm 一次订阅）

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

用于拿到当前推荐 snapshot manifest：响应即完整 `ak.schema.snapshot.v1` manifest（不含 chunk bytes），chunk bytes 经 manifest `chunks[].chunk_ref` 走 blob surface 获取。v1 的 `snapshot` namespace 仅 `ak.self.snapshot.read.manifest_head.v1` 一个 canonical operation；snapshot manifest 与 chunk 的防投毒校验流程见 §11。无法产出真实签名 manifest 的部署 MUST NOT 宣告本操作并 MUST 返回 `not_implemented`，不得伪造证明字段。

### 5.3 Event / Seal 状态与 Bottom 暴露

Sync 响应 SHOULD 在每条 reducer-input Event 上携带其当前协议状态字段（`event_state`），取值与 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §13 失败状态表一致：`data_local` / `data_observed` / `control_pending` / `control_sealed` / `failed_precondition` / `failed_plane` / `failed_bottom` / `rejected_seal` / `fork_quarantine` / `seal_ref_stale`。

State query / projection 响应 MUST 在 cell 当前 join 值为 ⊥ 时返回结构化 Bottom 诊断，schema 参见 [`schemas/bottom.schema.json`](../../artifacts/schemas/bottom.schema.json) 与 `ak.schema.bottom.v1`：

```json
{
  "cell": "ak:cell:ak.component.realm.policy.v1:null",
  "status": "bottom",
  "bottom": {
    "kind": "conflict",
    "cells": ["ak:cell:ak.component.realm.policy.v1:null"],
    "event_ids": [
      "ak:event:AZX1GsdimKJVck-Bj3-kzDNnYkXrZ76QLZGeTiOWlbBR…",
      "ak:event:ARs--JcXpC9xvf_GqjOGJpBUzlc1X5_5KkF53AKeLGQF…"
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
- `organization_principal_id`
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

```text
GET /_arkret/self/authz/invites?realm_id=<id>&subject=<did-or-handle>
```

```text
POST /_arkret/self/authz/check
```

`check` 接口适合：

- Events API 接收写入前预检查
- Station sync surface 分发前快速过滤
- client 发送前本地 UX 提示

## 10.1 Personal Agent Surface

Native personal agent 的 management、pairing、session grant 与 Sidecar operations 属于 self / gate trust surface 上的语义操作；canonical HTTP path、request/response schema 与 binding completeness index 由 [`service-http-binding.md` §2.4.1](./service-http-binding.md) 维护，本文只声明语义边界。实现 MUST 使用 operation catalog 中登记的 `ak.self.agent.*`、`ak.gate.account.*` 与 `ak.self.agent.sidecar.*` 操作名，不得从本节散文推导额外路径、profile id 或快捷授权。

约束:

- 本 surface 不引入 custom URI scheme(`arkret://` 等);所有 deep-link 由客户端用 deployment 已知的 `arkret_base_url` 拼接标准 HTTPS URL,移动端依赖 OS Universal Links / App Links。
- `pairing_request_id` 与 `approval_request_id` 都是 account/auth profile-local opaque UUIDv7 短期 artifact,不是 `ak:<kind>:<uuid>` 协议对象 id;agent runtime 收到 `approval_request_id` MUST NOT 解释成 URL 或尝试打开 UI,只能由 controller 的人类 session 带外查询。
- `{agent_id}` 是 DID,在 URL path 中 MUST 按 RFC 3986 percent-encoding。
- `ak.self.agent.command.provision.v1` MUST 接收非空 `slug`；`slug` 是 Agent 自身的固有字段，因此 provision request 与 list/get projection 均使用裸名 `slug`。controller 签署的唯一 `ak.agent.provision` Event 在一次 reducer transaction 中派生当前 selector projection，其中引用 Agent selector 的字段使用 `agent_slug=slug`；服务端不得另造 `ak.agent.selector_claim` Event。controller E2EE client MAY 在随后由其本地生成并加密提交的 Agent Actor Profile 中写入 `agent_slug` 作为投影 hint；服务端不得代写该 Agent PCR Profile。`agent_slug` 只用于 `@<controller-handle>/<agent_slug>` 输入别名到 agent principal DID 的 compose-time 解析；服务端 MUST 拒绝或 fail closed 处理同一 verified controller 下 active native agent 的 selector claim 冲突。
- participation replace/get 都是 controller-only。replace body 固定为 `{target_scope,selection,expected_version}`，GET 与 replace outcome 的 entry 固定为 `{target_scope,selection,version,next_replace_input:{expected_version}}`，且 `next_replace_input.expected_version=version`。Account Authority 只校验 controller、closed scope/五位 shape 与 CAS version；selection 可以表达希望开启但当前 policy/capability 尚不允许的位，因为它本身不产生权限。
- `ak.gate.account.command.issue_session_grant.v1` 为 agent runtime 签发 session 时，若 scope request 覆盖 participation-aware scope，`scope_details.participation[]` MUST 使用与 `agent_participation_entry` 同构的 `{target_scope,selection,version,next_replace_input:{expected_version}}` 条目，且 `next_replace_input.expected_version=version`。runtime 可据此避免无效动作；target 仍必须在动作时读取当前 deployment/Realm/Circle/Strand policy，并独立校验 capability、session scope、membership 与 lifecycle，不得信任 session 中携带的预计算 ceiling/effective。

详细 wire 规则见 [`service-http-binding.md` §2.4](./service-http-binding.md)、[`../identity/key-management.md` §3.6.1](../identity/key-management.md)、[`../identity/account-lifecycle.md` §9.1](../identity/account-lifecycle.md)、[`../models/circle.md` §11.1](../models/circle.md)、[`../models/private-objects.md` §4.1](../models/private-objects.md) 与 [`../authz/capabilities.md` §5](../authz/capabilities.md)。

## 11. Realm Bootstrap Strand

Arkret v1 的首次加入流程：

1. 用户输入 handle、DID 或 Realm link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 Realm link / invite / ActorId routing projection / locator / peer evidence 携带的 inline record 或 `current_record_url` 得到 service `did_core_id` 的首跳 `did` / `base_url`，验证 method history、record 签名、freshness 与 Realm policy，再以 role-scoped describe 确认 Station / identity registry / events / account / snapshot / blob / authz 能力
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 Realm metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk。**防投毒要求 (Snapshot Validation)**：由于 Station sync surface 仍是服务节点，快照可能被恶意篡改。客户端 MUST 验证快照 manifest 的规范字段 `created_by`（即签发者 DID，与 [`snapshot.schema.json`](../../artifacts/schemas/snapshot.schema.json) 一致）、`created_at`、`authority_binding`、`signature`、`state_digest` (Merkle Root)、frontier 和每个 chunk digest。`signature` 的 signer 必须匹配 `created_by`，且 `authority_binding` 必须证明该 DID 在 `created_at` 时是 Realm owner、Realm policy 授权的 snapshot issuer 或 witness quorum 成员。`authority_kind="witness_quorum"` 时，`authority_binding.witness_attestations[]` 是 v1 唯一的 quorum 证据载体：客户端 MUST 按 [`snapshot-schema.md` §5.1](../conformance/snapshot-schema.md) 逐行重算 `ak.snapshot_witness_attestation_proof.v1` canonical projection 验签，并只以 `created_at` 时点的 accepted Realm auth/policy state 判定授权 witness set、key validity、撤销新鲜度与 threshold（按 `witness_id` 去重）。不存在"等价 quorum proof"：缺失、未达阈值或使用任何未登记的替代载体时 MUST 以 `snapshot_authority_unverified` 拒绝，不得作为高保证 snapshot 使用。若校验失败，客户端 MUST 丢弃快照并回退到 `QUERY /_arkret/self/events`（`ak.self.events.read.scan.v1`，JSON content 携带 `before`）进行原始 Event 历史回放。
7. 从 frontier 之后拉取 backfill / sync stream 增量
8. 本地执行 reducer
9. 建立 read cursor、notification cursor 等个人状态

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
- principal 与 service 的业务引用都使用 `did_core_id`；注册 / resolution 出示 `did`，service 首跳 URL 由签名 `ServiceResolutionRecord` 给出，describe 只做二跳确认
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
