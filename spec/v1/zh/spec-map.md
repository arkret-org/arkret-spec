---
title: Spec Map
---

## 1. 目标

本文是 Contrix 规范的阅读入口。它按协议平面组织文档，避免读者在大量单文件中迷失。

若本文与具体规范冲突，以具体规范中的 MUST / SHOULD 规则为准。

### 1.1 规范权威层级

- `artifacts/registry/contract-catalog.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `artifacts/registry/event-kind-registry.json`、`schema-registry.json`、`id-kind-registry.json` 和 `operation-registry.json` 是从 canonical catalog 生成的机器视图；实现、SDK 和 lint 应消费这些生成物，而不是手抄 Markdown 表。
- `artifacts/registry/error-code-registry.json` 是标准 service error 与逐项 `reason_code` 的 canonical registry。
- `artifacts/openapi/contrix-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape；它描述 HTTP 形状，不替代抽象 `operation_id`、Event kind、typed ID 或 reducer 语义。
- `zh/*/*.md` 文档主要承担解释、边界说明和阅读路径；除明确标注“生成视图”外，不应再手工维护穷尽清单。
- `artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵；`conformance/conformance-profiles.md` 是其说明视图。

## 2. 推荐阅读顺序

初次理解协议时，建议按以下顺序阅读：

1. `overview/architecture.md`：先理解分层、实际服务器角色和信任边界。
2. `overview/glossary.md`：确认术语含义，尤其是 Principal / Actor / Organization / Space / Event / Principal Server。
3. `overview/current-model.md`：理解 v1 统一对象模型的关键设计决定（Flow 统一、Board/List 容器化、track 模型、E2EE 边界、agent 落点）。
4. `models/overview.md` 起步，按需进入 `models/space-and-place.md`、`models/flow-and-message.md` 等专项文件，理解协作图和标准对象。
5. `identity/identity-did.md`、`identity/identity-handles.md`、`identity/key-management.md`：理解身份、handle、设备/备份密钥和隐私披露（progressive disclosure 在 `identity-handles.md` §16）。
6. `authz/capabilities.md`、`authz/event-auth-state-resolution.md`：理解权限和 Space 状态机。
7. `sync/operations-sync.md`、`sync/client-sync.md`、`sync/service-surface.md`：理解写入、同步和服务面。
8. 按业务需要阅读扩展 profile，例如 Applet、Agent、WebRTC、Directory。

### 2.1 快速收敛链路（先读）

1. `overview/glossary.md`
2. `models/overview.md` + `models/space-and-place.md` + `models/flow-and-message.md`
3. `authz/event-auth-state-resolution.md` + `crypto-media/encryption-and-audit.md`
4. `sync/client-sync.md` + `sync/operations-sync.md`（含 snapshot、fork、decryption_pending）

## 3. 核心概念边界

### 3.1 Principal / Actor / Organization

- Principal 是身份根，通常由 DID 表示。
- Actor 是 Principal 在 Space 或协作图中的参与身份——拥有独立的 event chain、profile 与 membership，并以该 Principal 的 key 签名行为；不是只读派生投影。
- Organization 是一种 Principal，负责治理、签发、服务委派和官方背书。
- Organization 不是 Space；Space 是协作数据边界。

### 3.2 Space / Standard Objects / Morph / View

- Space 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- Flow、Message 和 Space workflow 容器是协议标准对象，拥有明确主语义和 reducer。
- Morph 是开放对象，用于 schema / profile 扩展类型；facets 是 schema/profile 声明后的能力提示和查询标签，不是对象身份，也不是授权、状态机、排序或 reducer 语义的唯一来源。
- Flow 通过 track primary 解析规则选择默认入口；`synthesis` / `discussion` track 分别承载正式表达与讨论能力。Track 是纯展示 / 时间线分段标识，**不携带独立 access**——所有访问语义继承自 Flow 所属 Space；需要独立 membership、历史可见性或 E2EE 边界的 discussion 必须升级为 child Space 并通过 `Flow.discussion_space_ref` 引用。
- View 是投影定义，不拥有真相数据。

### 3.3 Principal Server / Events / Sync / Projection

- signed Event Envelope 是唯一 canonical fact。
- Principal Server 通过 `/events/*` API 提交、读取、回填和验证 Event frontier。
- Principal Server 是主体控制或委托的服务边界；Sync Service 是其 Space 同步能力。
- 搜索、inbox、notification 和 View projection 默认由客户端本地派生；可选受托服务也不得成为真相源。

### 3.4 Discoverability / Join Rule / History Visibility

- Discoverability 决定资源能否被发现。
- Join Rule 决定如何加入。
- History Visibility 决定加入后能看到多少历史。
- 三者必须分开判断。

### 3.5 Capability / Moderation / Personal Blocklist

- Capability 决定基础动作权限。
- Moderation Policy 可以 deny、quarantine 或 require review，但不能授予权限。
- Personal Blocklist 是个人私有过滤，只影响自己的客户端体验。

## 4. 文档分组

### 4.1 总览与决策

| 文档 | 内容 |
| --- | --- |
| `README.md` | 项目定位、设计目标、规范入口。 |
| `spec-map.md` | 本文，按协议平面组织阅读路径。 |
| `overview/architecture.md` | 顶层架构、Principal Server 部署形态、部署拓扑、信任边界。 |
| `overview/matrix-core-differences.md` | 与 Matrix 的核心区别、边界和取舍。 |
| `overview/current-model.md` | Flow / track / board / list / view 的统一模型说明。 |
| `overview/release-readiness.md` | `v1` 发布基线、工件矩阵与稳定发布门槛。 |
| `overview/glossary.md` | 全局术语表。 |

### 4.2 身份、组织与隐私

| 文档 | 内容 |
| --- | --- |
| `identity/identity-did.md` | DID、v1 core 默认 principal method `did:webvh`、`did:web` 仅作为 service DID 默认 / `personal_node` profile 可选 / `did:webvh` 不可达 fallback、DID Document、Organization ownership。 |
| `identity/identity-handles.md` | Handle 解析、connection identifier、双向绑定、claim / attestation。 |
| `identity/tsp-integration.md` | TSP 作为可选 transport / trust binding。 |
| `identity/key-management.md` | 密钥、恢复、Accountable Actor。 |

### 4.3 对象模型与交互

`models/` 目录按对象类别组织，每个对象只在一个文件里讲完语义、字段、行为和示例；index.md 是入口与 typed-id 索引。

| 文档 | 内容 |
| --- | --- |
| `models/overview.md` | 对象总览、typed-id 一览、设计原则、阅读路径。 |
| `models/common-fields.md` | 公共字段、lifecycle / state 对齐、主体引用对照、reducer 总则、类型记法。 |
| `models/space-and-place.md` | Space（security boundary）、Place（看板 / 列 / 容器；`kind=board` / `kind=list` / 其他 profile 注册形态）、位置语义、Place lifecycle / cas-register / cascade。 |
| `models/flow-and-message.md` | Flow（统一协作主对象）、tracks（synthesis / discussion）、`discussion_space_ref`、Watch / 通知订阅模型（`watches` Relation + cas-register cell + 投影脱敏）、Message、chat 模式、冲突收敛、ephemeral 信号。 |
| `models/morph.md` | Morph 开放对象、`morph_type` 合并优先级、标准 facets、schema evolution。 |
| `models/relation.md` | Relation 一等关系、标准 `relation_kind` 与基数、跨 Space 规则、RelationProfile、冲突处理。 |
| `models/actor.md` | Actor 与 Actor Profile、`actor_kind`、accountability。 |
| `models/governance-objects.md` | Schema、Policy、Capability Grant、Invite 治理对象。 |
| `models/private-objects.md` | Read Marker、Notification、actor-private account data 引导。 |
| `models/event-and-patch.md` | Event Envelope、Proof、Field Patch (`cx.patch.v1`)、Event Batch Receipt、reducer 总则。 |
| `models/extension-objects.md` | Applet、Agent、Blob 等通过 extension profile 接入的对象（指向 `extensions/` 与 `crypto-media/`）。 |
| `models/views.md` | View kind / renderer、Query、Board / Timeline / Graph / Document projection。 |
| `models/content-types.md` | 富文本、媒体、投票、内容 block。 |
| `models/space-hierarchy.md` | Space-Space 层级、继承、lazy link、循环处理（已不在本组主入口，但仍属 models 目录）。 |

### 4.4 授权、治理与状态

| 文档 | 内容 |
| --- | --- |
| `authz/capabilities.md` | Capability、delegation、revocation、claim 条件。 |
| `authz/event-auth-state-resolution.md` | Move、Anchor、Lattice、bottom diagnostics、auth refs、membership、policy cells、history sharing 与 E2EE covered frontier。 |
| `authz/policy-server.md` | Policy Server 风险判断与签名决策。 |
| `governance/content-moderation.md` | 举报、E2EE franking、Space/Organization 审核策略、个人屏蔽入口。 |
| `security/server-threat-model.md` | 服务端攻击模型与反滥用规则。 |
| `identity/account-lifecycle.md` | 账号停用、锁定、擦除、session revocation。 |

### 4.5 同步、服务与联邦

| 文档 | 内容 |
| --- | --- |
| `sync/operations-sync.md` | Event-first 发布、Event Envelope、snapshot、冲突收敛。 |
| `sync/client-sync.md` | 客户端增量同步、timeline、state_after、to_device。 |
| `sync/service-surface.md` | 最小服务面与实际服务组合：principal server、identity、events、sync、directory、blob、authz、device/key、push、applet、agent、media、moderation。 |
| `sync/service-http-binding.md` | 默认 HTTP/JSON binding 路径、请求/响应和标准错误码。 |
| `sync/service-api-schema.mdx` | 核心 request / response schema 与 canonical operation 说明视图（含 `<OperationTable />` 组件）。 |
| `sync/api-conventions.md` | 错误、分页、幂等、feature discovery。 |
| `sync/transport-bindings.md` | HTTP/REST、gRPC、WebSocket、SSE、MQ、libp2p 等 binding。 |
| `sync/federation.md` | 跨域联邦模型、节点认证、Event 交换协议、跨域加入、frontier exchange、wire transaction 形态（合并自原 federation-wire.md）。 |
| `sync/sovereign-deployment.md` | 高安全自建网络、sovereign client、DID resolver policy、受控外部协作 Space、enclave、导入导出和撤销规则。 |

### 4.6 发现、目录与用户状态

| 文档 | 内容 |
| --- | --- |
| `discovery/discovery-directory.md` | Space / Organization / Actor / Applet discoverability、私密联系人发现与目录服务。 |
| `discovery/profiles-presence.md` | Actor profile、presence、typing、用户目录。 |
| `discovery/client-preferences.md` | Account data、私有标签、通知偏好、个人 blocklist、联系人 / Space 本地备注。 |
| `discovery/push-notifications.md` | 推送规则、推送网关、E2EE 脱敏推送。 |
| `discovery/read-receipts.md` | Read receipt 与 read marker。 |

### 4.7 加密、设备与媒体

| 文档 | 内容 |
| --- | --- |
| `crypto-media/device-lifecycle.md` | 设备身份、登录与授权边界、SSO/OIDC gateway、多设备配对、to-device 消息、cross-signing、secret storage、key backup。 |
| `crypto-media/encryption-and-audit.md` | MLS E2EE、MLS Governance Binding（`governance_binding` payload + `covered_frontier_cell`）、KeyPackage lifecycle、minimal-metadata Space 与 master-agent control 边界（核心机制）。 |
| `crypto-media/audited-e2ee.md` | 可选 hardening profile：`cx.profile.attested_audit.e2ee.v1` / `cx.profile.disclosed_audit.e2ee.v1` 的 audit policy、join warning、强制留痕、RYW receipt、forbidden marketing terms。 |
| `crypto-media/media-and-blob.md` | Blob metadata、thumbnail、authenticated media、asset privacy policy。 |
| `crypto-media/webrtc-signaling.md` | 音视频通话、会议、TURN/STUN/ICE、SFU/MCU。 |

### 4.8 扩展、Agent 与集成

| 文档 | 内容 |
| --- | --- |
| `extensions/applet-integration.md` | Applet / bridge / bot / ghost actor / portal Space。 |
| `extensions/applet-schema.md` | Applet schema 与 OpenAPI binding。 |
| `extensions/agent-protocol-interop.md` | A2A / ACP / external agent protocol handoff。 |
| `extensions/agent-workspace-profile.md` | 用户私人 agent workspace（mirror Space + agent_task FSM + mention_redirect / import_attestation 跨 Space 协作模式）。 |
| `extensions/mimi-interop.md` | MIMI Provider Facade、room binding、content/policy/identity mapping。 |
| `sync/third-party-invites.md` | 3PID 邀请与认领。 |
| `models/space-hierarchy.md` | Space parent/child、继承、lazy link、循环处理。 |
| `models/extension-objects.md` | Applet / Agent / Blob 等扩展对象在 models 层的入口与跳转。 |

### 4.9 Schema、编码与一致性

| 文档 | 内容 |
| --- | --- |
| `conformance/encoding.md` | Canonical JSON、ID、hash、signature、cursor、HLC、rank。 |
| `conformance/conformance-vectors.md` | 合并的一致性测试向量：§1 Encoding & crypto（canonical JSON / digest / signature binding / HLC / cursor / encrypted envelope）、§2 State resolution（并发 membership / capability / governance）、§3 Redaction（约束与可见性）、§4 Capability（delegation / revoke / approval）、§5 Sync（client sync / pagination / snapshot / MLS epoch backfill）。 |
| `conformance/schema-registry.md` | 标准 schema / event type registry。 |
| `conformance/query-schema.md` | View / Search / Inbox 可复用查询形状。 |
| `conformance/snapshot-schema.md` | Snapshot manifest、chunk、signature、encrypted envelope。 |
| `conformance/scalability-constraints.md` | v1 wire、授权、Move/Anchor/Lattice、Board/Relation/View 和 E2EE 的规模上限。 |
| `conformance/conformance-suite.md` | 自动化互操作 suite、向量优先级、组件测试矩阵。 |
| `conformance/conformance-profiles.md` | 实现 profile 与一致性测试范围。 |

## 5. 拆分原则

后续新增能力应按以下规则放置：

- 改变身份、DID、handle、claim 的内容，放入身份与隐私组。
- 改变共享状态有效性的内容，放入授权、治理与状态组。
- 改变服务 API 或 transport 的内容，放入同步、服务与联邦组。
- 新业务能力优先做 profile，例如 agent、applet、webrtc。
- 不要把服务部署角色写成身份主体；不要把 UI 投影写成真相源。


