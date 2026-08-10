---
title: Spec Map
status: candidate
normative: false
stability: v1
updated: 2026-07-13
see_also:
  - index.md
  - conformance/normative-language.md
---

## 1. 目标

本文是 Arkret 规范的阅读入口。它按协议平面组织文档，避免读者在大量单文件中迷失。

若本文与具体规范冲突，以具体规范中的 `MUST` / `SHOULD` 规则为准。

> **`v1/` 不是 URL 版本号**：本规范树的 `v1/` 目录与 `ak.*.v1` 标识符表示协议代际（`protocol_version="1.0"`），HTTP path 不含任何版本段。消歧说明见 [`index.md` §1](./index.md)，path 规则见 [`sync/api-conventions.md` §11](./sync/api-conventions.md)。

### 1.1 规范权威层级

- `artifacts/registry/contract-registry.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `artifacts/registry/event-kind-registry.json`、`schema-registry.json`、`track-name-registry.json`、`id-kind-registry.json`、`operation-registry.json`、`capability-action-registry.json` 和 `calendar-timezone-registry.json` 是从 canonical catalog 生成的机器视图；实现、SDK 和 lint 应消费这些生成物，而不是手抄 Markdown 表。
- `artifacts/registry/error-code-registry.json` 是标准 service error 与逐项 `reason_code` 的 canonical registry。
- `artifacts/openapi/arkret-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape；它描述 HTTP 形状，不替代抽象 `operation_id`、Event kind、typed ID 或 reducer 语义。
- `zh/*/*.md` 文档主要承担解释、边界说明和阅读路径；除明确标注“生成视图”外，不应再手工维护穷尽清单。
- `artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵；`conformance/conformance-profiles.md` 是其说明视图。
- 语言权威：本规范权威文本为 `zh/` 下中文；`en/` 仅提供说明性入口，非规范源。`artifacts/` 下机读契约语言中立、跨语言共享。

**ak.\* 命名空间的机读登记边界（导航摘要）**：本段是**导航摘要，非规范源**（与本文 frontmatter `normative: false` 一致）。并非所有 `ak.*` 标识符都要求进入机读 registry；算法 / 编码 profile id、设备验证方法名、client-local scheme id、信封 scheme 常量、hash / transcript 域分隔标签、feature id、DID Document / 外部生态 profile 值、E2EE application message kind 与标准 account-data tag 词表等类别豁免机读登记，其权威定义由各自的定义文档承载。豁免类别全表与配套约束的权威定义见 [`conformance/schema-registry.md` §1.2](./conformance/schema-registry.md)；如本摘要与该权威源有出入，以 schema-registry.md §1.2 为权威。

### 1.2 Current-wire artifact map

`artifacts/registry/registry-manifest.json` 索引 current v1 的机器可读源。实现、SDK、Conformance Verifier 与 transport adapter 应优先消费这些 artifact，而不是从 Markdown 表格手抄定义：

- `artifacts/registry/contract-registry.json`：event、schema、typed id、operation contract 的 canonical catalog。
- `artifacts/registry/operation-registry.json`、`event-kind-registry.json`、`schema-registry.json`、`track-name-registry.json`、`id-kind-registry.json`、`capability-action-registry.json`、`calendar-timezone-registry.json`：从 canonical catalog 生成的 current-wire 视图。`track-name-registry.json` 固定 `Strand.tracks` 的 active key 与 owner；`calendar-timezone-registry.json` 额外锁定 calendar schedule 可 pin 的 IANA TZDB release 与 zone canonicalization 规则。
- `artifacts/registry/error-code-registry.json`：标准 service error 与 `reason_code` 的 canonical registry。
- `artifacts/profiles/conformance-profiles.json`：profile、feature、unknown/unsupported 行为和 profile role 的机器矩阵。
- `artifacts/schemas/*.schema.json`：wire object、DTO、event payload、proof、capability、cursor、seal 与 extension object 的 JSON Schema。
- `artifacts/openapi/arkret-service-api.openapi.yaml`：HTTP/JSON binding shape；它约束 HTTP 形状，不替代抽象 operation、event kind、typed id 或 reducer 语义。
- `artifacts/fixtures/*.json` 与 `artifacts/registry/vector-registry.json`：conformance vector 的机器索引与可执行样例。
- `artifacts/registry/forbidden-wire-fields.json` 与 `artifacts/registry/forbidden-model-terms.json`：current-wire/current-model 的禁止字段和禁止术语检测源。

本文仅给出阅读地图；上述 artifact 的生成、校验和 drift 检测规则由各自 schema、registry 与 conformance 文档承载。

## 2. 推荐阅读顺序

初次理解协议时，建议按以下顺序阅读：

1. `overview/protocol-layers.md` 与 `overview/architecture.md`：先理解 Kernel / Collaboration Base / Extension 分层、实际服务器角色和信任边界。
2. `overview/glossary.md`：确认术语含义，尤其是 Principal / Actor / Organization / Realm / Event / Principal Server。
3. `overview/current-model.md`：理解 v1 统一对象模型的关键设计决定（Strand 统一、Board/List 容器化、track 模型、E2EE 边界、agent 落点）。
4. `models/overview.md` 起步，按需进入 `models/realm-and-space.md`、`models/strand-and-message.md` 等专项文件，理解协作图和标准对象。
5. `identity/identity-did.md`、`identity/identity-handles.md`、`identity/key-management.md`、`identity/security-transactions.md`、`identity/consent-model.md`、`identity/contact-and-direct-conversation.md`：理解身份、handle、设备/备份密钥、安全事务、consent gate、联系人关系和 1:1 私聊入口。
6. `authz/capabilities.md`、`authz/cba-profiles.md`、`authz/event-auth-state-resolution.md`、`authz/offline-publication.md`：理解权限、CBA 授权形态、Realm 状态机和离线发布。
7. `sync/operations-sync.md`、`sync/client-sync.md`、`sync/signal.md`、`sync/service-surface.md`、`sync/service-http-binding.md`：理解 durable 写入、同步、加密实时 rail 和服务面。
8. `governance/history-visibility.md`：理解历史可见性、preview / peek、public plaintext Realm 和 E2EE history key share 的共同边界。
9. 按业务需要阅读扩展 profile，例如 Applet、Agent、WebRTC、Directory。

### 2.1 快速收敛链路（先读）

1. `overview/glossary.md`
2. `models/overview.md` + `models/realm-and-space.md` + `models/strand-and-message.md`
3. `authz/event-auth-state-resolution.md` + `crypto-media/encryption-and-audit.md`
4. `sync/client-sync.md` + `sync/operations-sync.md`（含 snapshot、fork、decryption_pending）

### 2.2 从产品概念找章节

| 产品概念 | Arkret 读法 | 先读 |
| --- | --- | --- |
| 群聊 / 频道类场景 | Realm 负责成员和历史边界；Strand + Message 负责话题和消息；View 负责 timeline / thread 展示。 | `overview/current-model.md`、`models/strand-and-message.md`、`governance/history-visibility.md` |
| Trello 看板 / 列 / 卡片 | Board/List 是 Space.kind；卡片是 Strand；拖拽位置是 `ak.strand.move` / Relation 派生投影。 | `models/realm-and-space.md`、`models/views.md` |
| Jira issue / workflow / issue links | Issue 对应 Strand；粗粒度进度是 `stage`；细粒度 workflow 由 Realm profile 声明；依赖、阻塞、指派是 Relation。 | `models/strand-and-message.md`、`models/relation.md`、`models/common-fields.md` |
| Watchers / 通知规则 / 勿扰 | Watch cell 决定是否关注；push rule 决定如何投递；DND 和 blocklist 属于 actor-private account data。 | `models/strand-and-message.md` §8、`discovery/push-notifications.md`、`discovery/client-preferences.md` |
| 小程序 / Bot / Agent / 外部集成 | Applet/Agent 是扩展主体或服务；共享结果仍要落为 Event、Strand、Message、Morph 或 Relation。外部 runtime 的私有协议 session 不进入 Arkret 共享 history。 | `extensions/applet-integration.md`、`models/extension-objects.md` |

## 3. 核心概念边界

### 3.1 Principal / Actor / Organization

- Principal 是身份根，通常由 DID 表示。
- Actor 是 Principal 在 Realm 或协作图中的参与身份——拥有独立的 event chain、profile 与 membership，并以该 Principal 的 key 签名行为；不是只读派生投影。
- Organization 是一种 Principal，负责治理、签发、服务委派和官方背书。
- Organization 不是 Realm；Realm 是协作数据边界。

### 3.2 Realm / Standard Objects / Morph / View

- Realm 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- Strand、Message 和 Realm workflow 容器是协议标准对象，拥有明确主语义和 reducer。
- Morph 是开放对象，用于 schema / profile 扩展类型；facets 是 schema/profile 声明后的能力提示和查询标签，不是对象身份，也不是授权、状态机、排序或 reducer 语义的唯一来源。
- Strand 通过 track primary 解析规则选择默认入口；`synthesis` / `discussion` track 分别承载正式表达与讨论能力。Track 是纯展示 / 时间线分段标识，**不携带独立 access**——整个 Strand 共享单一 effective scope（由 `Strand.scope_circle_id` 决定，null = Realm-default，否则指向同 Realm 的 [Circle](./models/circle.md)）。需要独立 membership、历史可见性或 E2EE 边界时，把整 Strand 落在 Circle，或按 [`models/circle.md` §7.2](./models/circle.md) 拆为两个 Strand + Relation。
- View 是投影定义，不拥有真相数据。

### 3.3 Principal Server / Events / Sync / Projection

- signed Event Envelope 是唯一 canonical fact。
- Principal Server 通过 `/_arkret/self/events/*` API 提交、读取、回填和验证 Event frontier。
- Principal Server 是主体控制或委托的服务边界；Sync Service 是其 Realm 同步能力。
- 搜索、inbox、notification 和 View projection 默认由客户端本地派生；可选受托服务也不充当真相源（规范约束见 [`conformance/query-schema.md`](./conformance/query-schema.md) §8–§9）。

### 3.4 Discoverability / Join Rule / History Visibility

- Discoverability 决定资源能否被发现。
- Join Rule 决定如何加入。
- History Visibility 决定加入后能看到多少历史。
- 三者分开判断（规范约束见 [`governance/join-policy.md`](./governance/join-policy.md) 与 [`governance/history-visibility.md`](./governance/history-visibility.md)）。

### 3.5 Capability / Moderation / Personal Blocklist

- Capability 决定基础动作权限。
- Moderation Policy 可以 deny、quarantine 或 require review，但不能授予权限。
- Personal Blocklist 是个人私有过滤，只影响自己的客户端体验。

## 4. 文档分组

### 4.1 总览与决策

| 文档 | 内容 |
| --- | --- |
| `index.md` | 项目定位、设计目标、规范入口。 |
| `spec-map.md` | 本文，按协议平面组织阅读路径。 |
| `overview/architecture.md` | 顶层架构、Principal Server 部署形态、部署拓扑、信任边界。 |
| `overview/protocol-layers.md` | Kernel、Collaboration Base 与 Extension 的协议边界、依赖方向和演进规则。 |
| `overview/current-model.md` | Strand / track / Board / List / View 的统一模型说明。 |
| `overview/release-readiness.md` | `v1` 发布基线、工件矩阵与稳定发布门槛。 |
| `overview/glossary.md` | 全局术语表。 |
| `overview/evolution-and-compatibility.md` | 协议演进与 current-wire 边界：版本承载、加性演进、profile / capability 协商和 fail-closed 的整体入口（被 `conformance/conformance-profiles.md`、`conformance/encoding.md`、`sync/service-http-binding.md` 引用为演进导航入口）。 |
| `guides/migrating-from-matrix.md` | 与 Matrix 的核心区别、边界和取舍（informative 对照，非真相源，详见 §4.10 实现指南组说明）。 |

### 4.2 身份、组织与隐私

| 文档 | 内容 |
| --- | --- |
| `identity/identity-did.md` | DID、v1 唯一长期 principal method `did:webvh`、`did:key` 仅显式 ephemeral pairwise principal、service 默认 `did:webvh` 且 `did:web` 仅显式 no-history service、`did:webvh` outage 的 cache-only degraded mode、DID Document、Organization ownership。 |
| `identity/did-usage-and-verification.md` | DID / DID URL 字段总表、非 DID identifier 对照、普通身份锚点使用与少量 DID 权威验证触发条件、verified binding 缓存和失效边界。 |
| `identity/identity-handles.md` | Handle 解析、connection identifier、双向绑定、claim / attestation、`MemberDeliveryBindingCandidate`（§3.7）。 |
| `identity/consent-model.md` | 用户同意、披露边界、撤回语义和跨服务 consent proof。 |
| `identity/contact-and-direct-conversation.md` | 联系人请求 / 接受 / 拒绝 / tombstone、双方方向性 Contact authority、private contact discovery 边界、direct conversation resolver、DM Realm 与 DM 主 Strand 形态。 |
| `identity/tsp-integration.md` | TSP 作为可选 transport / trust binding。 |
| `identity/key-management.md` | 密钥、恢复、Accountable Actor。 |
| `identity/security-transactions.md` | RecoveryTransaction / SecurityRotationTransaction 的幂等、恢复与终态合同。 |
| `identity/account-lifecycle.md` | 账号停用、锁定、擦除、session revocation。 |
| `sync/third-party-invites.md` | 3PID 邀请、认领与第三方标识符 claim 流程；物理位于 `sync/`，因为其 wire strand 与服务提交路径由 Sync / Federation 章节承载。 |

### 4.3 对象模型与交互

`models/` 目录按对象类别组织，每个对象只在一个文件里讲完语义、字段、行为和示例；`models/overview.md` 是入口与 typed-id 索引。

| 文档 | 内容 |
| --- | --- |
| `models/overview.md` | 对象总览、typed-id 一览、设计原则、阅读路径。 |
| `models/common-fields.md` | 公共字段、lifecycle / state 对齐、主体引用对照、reducer 总则、类型记法。 |
| `models/realm-and-space.md` | Realm（security boundary）、Space（看板 / 列 / 容器；`kind=board` / `kind=list` / 其他 profile 注册形态）、位置语义、Space lifecycle / cas_register / cascade。 |
| `models/strand-and-message.md` | Strand（统一协作主对象）、tracks（synthesis / discussion）、`scope_circle_id`（Strand effective scope）、Watch / 通知订阅模型（`watches` Relation + cas_register cell + 投影脱敏）、Message、chat 模式、冲突收敛、ephemeral 信号。 |
| `models/calendar-event.md` | Calendar Strand 的 `schema_refs` 激活、schedule fields、LocalDateTime 半开区间、RFC 8984 recurrence v1 子集、TZDB 版本绑定、schedule revision frontier、attendees 与 `ak.rsvp.set` 完整 entry 收敛。 |
| `models/circle.md` | Circle（intra-Realm 子事件 / 子消息边界）、`scope_circle_id` / `effective_scope`、Circle encryption profile 与父 Realm floor、`Circle.members ⊆ Realm.members`、Realm-default vs Circle scope、Space `child_scope_policy`、跨 scope Relation、`confidential_discussion_of` 模式、MLS-backed Circle rotate amplification 缓解、Circle UX 视觉一致性要求。 |
| `models/sidecar.md` | Agent Sidecar 独立对象、Event-derived 身份、native scope、ownership-derived owned/effective access、独立 MLS、context view 映射、存在性隐私与专用 UI 不变量。 |
| `models/morph.md` | Morph 开放对象、`morph_kind` 合并优先级、标准 facets、schema evolution。 |
| `models/relation.md` | Relation 一等关系、标准 `relation_kind` 与基数、跨 Realm 规则、RelationProfile、冲突处理。 |
| `models/actor.md` | Actor 与 Actor Profile、`actor_kind`、accountability。 |
| `models/governance-objects.md` | Schema、Policy、Capability Grant、Invite 治理对象。 |
| `models/private-objects.md` | Read Cursor、Notification、actor-private account data 引导。 |
| `models/account-data.md` | principal/actor-private Account Data 的存储、namespace key、value encryption、HKDF/AAD transcript 与文档放置规则单一真相源。 |
| `models/crdt-text-extension.md` | 实时协同文本 CRDT 的 reserved profile、默认 revision 关系与激活门槛。 |
| `models/personal-productivity.md` | principal-private reminders、scheduled send、snooze、saved items 与 draft sync account-data key 规则。 |
| `models/file-transfer.md` | principal-private 跨设备文件传输：encrypted account-data transfer record、Blob ciphertext、to-device key delivery、retention 与共享附件边界。 |
| `models/event-and-patch.md` | Event Envelope、Proof、Field Patch (`ak.schema.patch.v1`)、Event Batch Receipt、reducer 总则。 |
| `models/extension-objects.md` | Applet、Agent、Blob 等通过 extension profile 接入的对象（指向 `extensions/` 与 `crypto-media/`）。 |
| `models/pins.md` | Shared pin events、`pin_scope` 解析、Space effective scope 安全边界与 pin projection stub。 |
| `models/views.md` | View kind / renderer、Query、Board / Timeline / Graph / Document projection。 |
| `models/content-types.md` | 富文本、媒体、投票、内容 block。 |
| `models/realm-links.md` | Realm link graph、显式继承、治理 / 发现 / mirror / confidential-extension 关系。 |
| `models/space-hierarchy.md` | Space 产品结构层级、跨 Realm 导航、effective default Realm 解析。 |

### 4.4 授权、治理与状态

| 文档 | 内容 |
| --- | --- |
| `authz/capabilities.md` | Capability、delegation、revocation、claim 条件。 |
| `authz/cba-profiles.md` | CBA 授权集合 profile、并发类别、proof bundle 与提案终态。 |
| `authz/offline-publication.md` | AuthorizationLease、IngressReceipt 与离线发布窗口。 |
| `authz/constraint-schema.md` | Capability / policy 约束表达式、条件字段和组合语义。 |
| `authz/resource-selector-grammar.md` | Resource selector 的语法、匹配范围和解析规则。 |
| `authz/event-auth-state-resolution.md` | Move、Seal、Lattice、bottom diagnostics、auth refs、membership、policy cells、history sharing 与 E2EE covered Seals。 |
| `authz/policy-server.md` | Policy Server 风险判断与签名决策。 |
| `governance/join-policy.md` | Join Rule、邀请、knock / restricted / approval 流程和 history visibility 联动。 |
| `governance/member-delivery-binding.md` | 成员 effective delivery binding：接受准则、`binding_source`、`ak.realm.delivery_binding_policy`、路由不可降级、rebind 过渡、单 binding + 多设备策略与隐私边界（与 join gate 正交）。 |
| `governance/history-visibility.md` | `world_readable` / `shared` / `invited` / `joined` / `restricted` 的精确定义、preview / peek policy、public plaintext Realm 与 E2EE history key share。 |
| `governance/content-moderation.md` | 举报、E2EE franking、Realm/Organization 审核策略、个人屏蔽入口。 |
| `security/server-threat-model.md` | 服务端攻击模型与反滥用规则；物理位于 `security/` 安全分析专项目录。 |

### 4.5 同步、服务与联邦

| 文档 | 内容 |
| --- | --- |
| `sync/operations-sync.md` | Event-first 发布、Event Envelope、snapshot、冲突收敛。 |
| `sync/client-sync.md` | 客户端增量同步、timeline、state_after、to_device。 |
| `sync/signal.md` | encrypted-only Signal Extension send / subscribe rail、可见分类与 TTL。 |
| `sync/service-surface.md` | 最小服务面与实际服务组合：Principal Server、identity、events、sync、directory、blob、authz、device/key、push、applet、agent、media、moderation。 |
| `sync/privacy-preserving-search.md` | 客户端加密索引托管、blind-index token、`ak.realm.search_policy` 与 search result fail-closed 语义。 |
| `sync/service-http-binding.md` | 默认 HTTP/JSON binding 路径、请求/响应和标准错误码。 |
| `sync/invite-addressing.md` | Realm invite 的显式 invite address、online principal locator、introduction evidence、private invite delivery 与 handle/mention 边界。 |
| `sync/service-api-schema.mdx` | canonical operation 分组与治理说明视图（含 `<OperationTable />` 组件）；request / response shape 以 OpenAPI、JSON Schema 和 `artifacts/reports/operation-schema-index.json` 为准。 |
| `sync/api-conventions.md` | 错误、分页、幂等、feature discovery。 |
| `sync/transport-bindings.md` | HTTP/REST、gRPC、WebSocket、SSE、MQ、libp2p 等 binding。 |
| `sync/websocket-binding.md` | （optional profile）`ak.profile.binding.websocket.v1`：三条 stream operation 的 WebSocket 承载、帧 schema、DPoP 绑定、重连与 flow control。 |
| `sync/federation.md` | 跨域联邦模型、节点认证、Event 交换协议、跨域加入、frontier exchange、wire transaction 形态。 |
| `sync/sovereign-deployment.md` | 高安全自建网络、sovereign client、DID resolver policy、sovereign deployment 下 External Collaboration Realm 的强制 policy、enclave、导入导出和撤销规则。 |
| `sync/third-party-invites.md` | 3PID 邀请与认领的 wire strand、token handoff、claim submit 与不可枚举响应；身份语义同时在 §4.2 交叉登记。 |

### 4.6 发现、目录与用户状态

| 文档 | 内容 |
| --- | --- |
| `discovery/discovery-directory.md` | Realm / Organization / Actor / Applet discoverability、私密联系人发现与目录服务。 |
| `discovery/object-addressing.md` | 客户端无关可分享对象地址：`web+arkret:` URI scheme、HTTPS 落地、link 类型与 `resolve_target`。 |
| `discovery/profiles-presence.md` | Actor profile、presence、typing、用户目录。 |
| `discovery/client-preferences.md` | Account data、私有标签、通知偏好、个人 blocklist、联系人 / Realm 本地备注。 |
| `discovery/push-notifications.md` | 推送规则、推送网关、E2EE 脱敏推送。 |
| `discovery/read-receipts.md` | Read receipt 与 read cursor。 |

### 4.7 加密、设备与媒体

| 文档 | 内容 |
| --- | --- |
| `crypto-media/device-lifecycle.md` | 设备身份、登录与授权边界、SSO/OIDC gateway、多设备配对、to-device 消息、PCR 设备授权、secret storage、key backup。 |
| `crypto-media/encryption-and-audit.md` | MLS E2EE、MLS Security Frontier Binding（`governance_binding.security_frontier_digest` + active generation projection）、KeyPackage lifecycle、minimal-metadata Realm 与 master-agent control 边界（核心机制）。 |
| `crypto-media/disappearing-messages.md` | Message expiry、`ak.realm.disappearing_policy`、expiry stub、crypto-shredding 与 redaction 区分。 |
| `crypto-media/audited-e2ee.md` | 可选 hardening profile：Audit Applet Binding、阶段性 release session、sealed historical release、RYW receipt、`ak.profile.attested_audit.e2ee.v1` / `ak.profile.disclosed_audit.e2ee.v1` 保证类别与 forbidden marketing terms。 |
| `crypto-media/media-and-blob.md` | Blob metadata、thumbnail、authenticated media、asset privacy policy。 |
| `crypto-media/webrtc-signaling.md` | 音视频通话 ephemeral 信令、ICE/TURN/STUN、一对一通话、多设备冲突、屏幕共享、推送集成。 |
| `crypto-media/media-service-binding.md` | 媒体服务发现（`ak.realm.media_service` foci）、token / participant binding 兑换、focus 选举、SFU 权限、媒体 E2EE 帧密钥注入与治理绑定。 |
| `crypto-media/call-state.md` | 通话模型与状态机、durable `ak.call.state` 字段语义、录制 / 转写生命周期。 |
| `crypto-media/bindings/arkret-native.md` | （optional sub-profile）Arkret 原生媒体后端 binding，定义 `ak.profile.media_service_binding.arkret_native.v1`，由 `media-service-binding.md` 引用。 |
| `crypto-media/bindings/livekit.md` | （optional sub-profile）LiveKit 媒体后端 binding，定义 `ak.profile.media_service_binding.livekit.v1`，由 `media-service-binding.md` 引用。 |

### 4.8 扩展、Agent 与集成

| 文档 | 内容 |
| --- | --- |
| `extensions/applet-integration.md` | Applet / bridge / bot / Ghost Actor / portal Realm。 |
| `extensions/extension-manifest.md` | Extension Manifest 的声明式边界、依赖与禁止可执行 DSL 规则。 |
| `extensions/applet-schema.md` | Applet schema 与 OpenAPI binding。 |
| `extensions/mimi-interop.md` | MIMI Provider Facade、room binding、content/policy/identity mapping。 |

> `models/realm-links.md`、`models/space-hierarchy.md` 与 `models/extension-objects.md` 的权威登记在 [§4.3 对象模型与交互](#43-对象模型与交互)；扩展场景从那里跳转，本组不重复整行登记。

### 4.9 Schema、编码与一致性

| 文档 | 内容 |
| --- | --- |
| `conformance/README.md` | conformance 目录入口、阅读顺序和 artifact/向量使用说明。 |
| `conformance/normative-language.md` | RFC 2119 / 8174 规范关键字（`MUST` / `SHOULD` / `MAY` 等）的 canonical 定义与中英对照；几乎所有文档在 §0 引用，若干总览类文档亦在 frontmatter `see_also` 登记。 |
| `conformance/encoding.md` | Canonical JSON、ID、hash、signature、cursor、HLC、rank。 |
| `conformance/conformance-vectors.md` | 一致性测试向量的人类阅读入口；完整 active vector 集合以 `artifacts/registry/vector-registry.json` 及其 `source_refs` 为准。 |
| `conformance/schema-registry.md` | 标准 schema / event type registry。 |
| `conformance/query-schema.md` | View / Search / Inbox 可复用查询形状。 |
| `conformance/snapshot-schema.md` | Snapshot manifest、chunk、signature、encrypted envelope。 |
| `conformance/scalability-constraints.md` | v1 wire、授权、CBA/Lattice、Board/Relation/View 和 E2EE 的规模上限。 |
| `conformance/conformance-suite.md` | 自动化互操作 suite、向量优先级、组件测试矩阵。 |
| `conformance/conformance-profiles.md` | 实现 profile 与一致性测试范围。 |

### 4.10 实现指南

这些文档不是新的协议真相源，而是把 artifact 消费、参考实现和发布集成路径串起来：

| 文档 | 内容 |
| --- | --- |
| `guides/artifact-consumption.md` | SDK、conformance runner 与 transport adapter 如何消费 registry、OpenAPI、profiles 与 fixtures。 |
| `guides/reference-implementation-guide.md` | 参考实现的模块边界、生成链路、测试入口和发布前检查顺序。 |
| `guides/migrating-from-matrix.md` | Matrix interop 的 informative 设计取舍对照（非真相源）；§4.1 同步列出便于概览读者定位。 |

## 5. 拆分原则

后续新增能力应按以下规则放置：

- 改变身份、DID、handle、claim 的内容，放入身份与隐私组。
- 改变共享状态有效性的内容，放入授权、治理与状态组。
- 改变服务 API 或 transport 的内容，放入同步、服务与联邦组。
- principal/actor-private data type 的基础存储、寻址、加密与 merge primitive 放入 `models/account-data.md`；具体字段语义留在功能域消费方文档，并统一登记 `account-data-key-registry.json`。
- 新业务能力优先做 profile，例如 Agent、Applet、WebRTC。
- 不要把服务部署角色写成身份主体；不要把 UI 投影写成真相源。
