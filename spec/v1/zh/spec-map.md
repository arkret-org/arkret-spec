---
title: Spec Map
status: candidate
normative: false
stability: v1
updated: 2026-06-01
see_also:
  - index.md
  - conformance/normative-language.md
---

## 1. 目标

本文是 Cokret 规范的阅读入口。它按协议平面组织文档，避免读者在大量单文件中迷失。

若本文与具体规范冲突，以具体规范中的 MUST / SHOULD 规则为准。

> **`v1/` 不是 URL 版本号**：本规范树的 `v1/` 目录与 `ck.*.v1` 标识符表示协议代际（`protocol_version="1.0"`），HTTP path 不含任何版本段。消歧说明见 [`index.md` §1](./index.md)，path 规则见 [`sync/api-conventions.md` §11](./sync/api-conventions.md)。

### 1.1 规范权威层级

- `artifacts/registry/contract-catalog.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `artifacts/registry/event-kind-registry.json`、`schema-registry.json`、`id-kind-registry.json` 和 `operation-registry.json` 是从 canonical catalog 生成的机器视图；实现、SDK 和 lint 应消费这些生成物，而不是手抄 Markdown 表。
- `artifacts/registry/error-code-registry.json` 是标准 service error 与逐项 `reason_code` 的 canonical registry。
- `artifacts/openapi/cokret-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape；它描述 HTTP 形状，不替代抽象 `operation_id`、Event kind、typed ID 或 reducer 语义。
- `zh/*/*.md` 文档主要承担解释、边界说明和阅读路径；除明确标注“生成视图”外，不应再手工维护穷尽清单。
- `artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵；`conformance/conformance-profiles.md` 是其说明视图。
- 语言权威：本规范权威文本为 `zh/` 下中文；`en/` 仅提供说明性入口，非规范源。`artifacts/` 下机读契约语言中立、跨语言共享。

### 1.2 漂移检测 artifacts

为了让下游实现（SDK、yougen、soland、cotest 等）能够机器化地发现已经从协议中移除或被弃用的概念，
`artifacts/registry/` 下提供一组 drift detection artifacts。它们是 canonical source of truth，由
`registry-manifest.json` 索引，cotest scanner 直接消费这些文件来识别旧 id / 旧字段 / 旧术语的残留：

- `artifacts/registry/removed-event-kinds.json`：已移除的 Event.kind 列表（例如 `ck.field.position.*`、
  `ck.flow.track.*`、`ck.realm.lifecycle.set`、`ck.realm.policy.set`）。
- `artifacts/registry/removed-operation-ids.json`：已移除的 operation id（与上述 event kind 对齐的 binding 端点）。
- `artifacts/registry/deprecated-profile-ids.json`：已弃用或从未 canonical 化的 profile id
  （例如 `chat_only_client`、`kanban_only_client`）。
- `artifacts/registry/forbidden-wire-fields.json`：在 current-wire 中禁止出现的字段（带上下文，例如
  timeline event 顶层不得出现 `branch`、payload 中不得出现 `room_kind` 或 `kind=room`）。
- `artifacts/registry/forbidden-model-terms.json`：在 current-model prose / code identifier / UI 文案中
  禁止使用的术语（例如 `Room`、`Realm(kind=list)`、`flow_branch`、`track members`、`Room visibility`）及其替代物。
- `artifacts/registry/renames.json`：从旧 id / 旧字段名到 v1 替代物的重命名映射（`replacement=null` 表示概念被删除、
  无机械替代）。

每条 entry 公共字段：`id`、`since_revision`（生效起始的 spec revision）、`rejection_level`
（`hard_reject` / `migration_only` / `compat_only` / `docs_only`）、`replacement`、`allowed_contexts`
（`changelog` / `legacy_migration` / `interop_module` / `negative_test`）、`notes`；
可选字段：`migration_group`（同一设计决策的批量条目归并标签，见 `renames.json.migration_group_definitions`）、
`migration_tool_only: true`（仅离线 migration / replay 工具可消费的 disambiguation entry）。

新增、移除或重命名标准 ck.* 概念时 MUST 同步更新这组 artifacts；CHANGELOG 条目和这些 artifacts 是
"机器可发现的协议演化记录"的两面。

#### 1.2.1 Parser 分层（normative）

`renames.json` 的条目按消费方分两层，分别由 `renames.json.parser_tier_definitions` 定义：

- **Current parser**：sync service、federation peer、snapshot consumer、reducer、conformance test runner —— 任何处理 live 或已持久化 v1 wire bytes 的组件。MUST 把 `renames.json` 中所有 `hard_reject` / `migration_only` 条目都视作输入禁止；**MUST NOT 做 payload-shape disambiguation**；遇到旧 id MUST 直接返回 `unknown_kind` / `unknown_field` / `schema_violation` 等标准错误，**不得在线静默重写**。
- **Migration tool**：离线批处理工具，读取 pre-v1 / pre-inversion bytes 并改写成 canonical v1 形态。MAY 消费带 `migration_tool_only: true` 的 entry（例如 `ck.space.create#pre_inversion_security_boundary`），按 `disambiguation_payload_shape` 规则鉴别。MUST NOT 嵌入实时 parser 表面（无 inline transform；无 "auto-accept legacy and quietly rewrite"）。

这条规则把 Realm/Space inversion 时引入的"payload-shape 鉴别"复杂度严格限制在迁移工具内：当前 v1 sync / federation / snapshot 路径不需要也不允许实现这条 fallback。新增的 `migration_tool_only` 标志使该约束机器可检测，CI / lint 可据此拒绝在 reducer/service 代码里引用对应 entry。

## 2. 推荐阅读顺序

初次理解协议时，建议按以下顺序阅读：

1. `overview/architecture.md`：先理解分层、实际服务器角色和信任边界。
2. `overview/glossary.md`：确认术语含义，尤其是 Principal / Actor / Organization / Realm / Event / Principal Server。
3. `overview/current-model.md`：理解 v1 统一对象模型的关键设计决定（Flow 统一、Board/List 容器化、track 模型、E2EE 边界、agent 落点）。
4. `models/overview.md` 起步，按需进入 `models/realm-and-space.md`、`models/flow-and-message.md` 等专项文件，理解协作图和标准对象。
5. `identity/identity-did.md`、`identity/identity-handles.md`、`identity/key-management.md`：理解身份、handle、设备/备份密钥和隐私披露（progressive disclosure 在 `identity-handles.md` §16）。
6. `authz/capabilities.md`、`authz/event-auth-state-resolution.md`：理解权限和 Realm 状态机。
7. `sync/operations-sync.md`、`sync/client-sync.md`、`sync/service-surface.md`：理解写入、同步和服务面。
8. `governance/history-visibility.md`：理解历史可见性、preview / peek、public plaintext Realm 和 E2EE history key share 的共同边界。
9. 按业务需要阅读扩展 profile，例如 Applet、Agent、WebRTC、Directory。

### 2.1 快速收敛链路（先读）

1. `overview/glossary.md`
2. `models/overview.md` + `models/realm-and-space.md` + `models/flow-and-message.md`
3. `authz/event-auth-state-resolution.md` + `crypto-media/encryption-and-audit.md`
4. `sync/client-sync.md` + `sync/operations-sync.md`（含 snapshot、fork、decryption_pending）

### 2.2 从产品概念找章节

| 产品概念 | Cokret 读法 | 先读 |
| --- | --- | --- |
| 群聊 / 频道 / Matrix Room | Realm 负责成员和历史边界；Flow + Message 负责话题和消息；View 负责 timeline / thread 展示。 | `overview/current-model.md`、`models/flow-and-message.md`、`governance/history-visibility.md` |
| Trello 看板 / 列 / 卡片 | Board/List 是 Space.kind；卡片是 Flow；拖拽位置是 `ck.flow.move` / Relation 派生投影。 | `models/realm-and-space.md`、`models/views.md` |
| Jira issue / workflow / issue links | Issue 对应 Flow；粗粒度进度是 `stage`；细粒度 workflow 由 Realm profile 声明；依赖、阻塞、指派是 Relation。 | `models/flow-and-message.md`、`models/relation.md`、`models/common-fields.md` |
| Watchers / 通知规则 / 勿扰 | Watch cell 决定是否关注；push rule 决定如何投递；DND 和 blocklist 属于 actor-private account data。 | `models/flow-and-message.md` §8、`discovery/push-notifications.md`、`discovery/client-preferences.md` |
| 小程序 / Bot / Agent / 外部集成 | Applet/Agent 是扩展主体或服务；共享结果仍要落为 Event、Flow、Message、Morph 或 Relation。 | `extensions/applet-integration.md`、`extensions/agent-protocol-interop.md`、`models/extension-objects.md` |

## 3. 核心概念边界

### 3.1 Principal / Actor / Organization

- Principal 是身份根，通常由 DID 表示。
- Actor 是 Principal 在 Realm 或协作图中的参与身份——拥有独立的 event chain、profile 与 membership，并以该 Principal 的 key 签名行为；不是只读派生投影。
- Organization 是一种 Principal，负责治理、签发、服务委派和官方背书。
- Organization 不是 Realm；Realm 是协作数据边界。

### 3.2 Realm / Standard Objects / Morph / View

- Realm 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- Flow、Message 和 Realm workflow 容器是协议标准对象，拥有明确主语义和 reducer。
- Morph 是开放对象，用于 schema / profile 扩展类型；facets 是 schema/profile 声明后的能力提示和查询标签，不是对象身份，也不是授权、状态机、排序或 reducer 语义的唯一来源。
- Flow 通过 track primary 解析规则选择默认入口；`synthesis` / `discussion` track 分别承载正式表达与讨论能力。Track 是纯展示 / 时间线分段标识，**不携带独立 access**——整个 Flow 共享单一 effective scope（由 `Flow.scope_circle_id` 决定，null = Realm-default，否则指向同 Realm 的 [Circle](./models/circle.md)）。需要独立 membership、历史可见性或 E2EE 边界时，把整 Flow 落在 Circle，或按 [`models/circle.md` §7.2](./models/circle.md) 拆为两个 Flow + Relation。
- View 是投影定义，不拥有真相数据。

### 3.3 Principal Server / Events / Sync / Projection

- signed Event Envelope 是唯一 canonical fact。
- Principal Server 通过 `/_cokret/self/events/*` API 提交、读取、回填和验证 Event frontier。
- Principal Server 是主体控制或委托的服务边界；Sync Service 是其 Realm 同步能力。
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
| `index.md` | 项目定位、设计目标、规范入口。 |
| `spec-map.md` | 本文，按协议平面组织阅读路径。 |
| `overview/architecture.md` | 顶层架构、Principal Server 部署形态、部署拓扑、信任边界。 |
| `overview/current-model.md` | Flow / track / board / list / view 的统一模型说明。 |
| `overview/release-readiness.md` | `v1` 发布基线、工件矩阵与稳定发布门槛。 |
| `overview/glossary.md` | 全局术语表。 |
| `guides/migrating-from-matrix.md` | 与 Matrix 的核心区别、边界和取舍（informative 对照，非真相源，详见 §4.10 实现指南组说明；面向 Matrix 实现者的迁移视角；旧路径 `overview/matrix-core-differences.md`）。 |

### 4.2 身份、组织与隐私

| 文档 | 内容 |
| --- | --- |
| `identity/identity-did.md` | DID、v1 core 默认 principal method `did:webvh`、`did:web` 仅作为 service DID 默认 / `personal_node` profile 可选、`did:webvh` outage 的 cache-only degraded mode、DID Document、Organization ownership。 |
| `identity/identity-handles.md` | Handle 解析、connection identifier、双向绑定、claim / attestation、`MemberDeliveryBindingCandidate`（§3.7）。 |
| `identity/consent-model.md` | 用户同意、披露边界、撤回语义和跨服务 consent proof。 |
| `identity/tsp-integration.md` | TSP 作为可选 transport / trust binding。 |
| `identity/key-management.md` | 密钥、恢复、Accountable Actor。 |

### 4.3 对象模型与交互

`models/` 目录按对象类别组织，每个对象只在一个文件里讲完语义、字段、行为和示例；index.md 是入口与 typed-id 索引。

| 文档 | 内容 |
| --- | --- |
| `models/overview.md` | 对象总览、typed-id 一览、设计原则、阅读路径。 |
| `models/common-fields.md` | 公共字段、lifecycle / state 对齐、主体引用对照、reducer 总则、类型记法。 |
| `models/realm-and-space.md` | Realm（security boundary）、Space（看板 / 列 / 容器；`kind=board` / `kind=list` / 其他 profile 注册形态）、位置语义、Space lifecycle / cas_register / cascade。 |
| `models/flow-and-message.md` | Flow（统一协作主对象）、tracks（synthesis / discussion）、`scope_circle_id`（Flow effective scope）、Watch / 通知订阅模型（`watches` Relation + cas_register cell + 投影脱敏）、Message、chat 模式、冲突收敛、ephemeral 信号。 |
| `models/circle.md` | Circle（intra-Realm 子事件 / 子消息边界）、`scope_circle_id` / `effective_scope`、Circle encryption profile 与父 Realm floor、`Circle.members ⊆ Realm.members`、Realm-default vs Circle scope、Space `child_scope_policy`、跨 scope Relation、`confidential_discussion_of` 模式、MLS-backed Circle rotate amplification 缓解、Circle UX 视觉一致性要求。 |
| `models/morph.md` | Morph 开放对象、`morph_type` 合并优先级、标准 facets、schema evolution。 |
| `models/relation.md` | Relation 一等关系、标准 `relation_kind` 与基数、跨 Realm 规则、RelationProfile、冲突处理。 |
| `models/actor.md` | Actor 与 Actor Profile、`actor_kind`、accountability。 |
| `models/governance-objects.md` | Schema、Policy、Capability Grant、Invite 治理对象。 |
| `models/private-objects.md` | Read Cursor、Notification、actor-private account data 引导。 |
| `models/event-and-patch.md` | Event Envelope、Proof、Field Patch (`ck.patch.v1`)、Event Batch Receipt、reducer 总则。 |
| `models/extension-objects.md` | Applet、Agent、Blob 等通过 extension profile 接入的对象（指向 `extensions/` 与 `crypto-media/`）。 |
| `models/views.md` | View kind / renderer、Query、Board / Timeline / Graph / Document projection。 |
| `models/content-types.md` | 富文本、媒体、投票、内容 block。 |
| `models/realm-links.md` | Realm link graph、显式继承、治理 / 发现 / mirror / confidential-extension 关系。 |
| `models/space-hierarchy.md` | Space 产品结构层级、跨 Realm 导航、effective default Realm 解析。 |

### 4.4 授权、治理与状态

| 文档 | 内容 |
| --- | --- |
| `authz/capabilities.md` | Capability、delegation、revocation、claim 条件。 |
| `authz/constraint-schema.md` | Capability / policy 约束表达式、条件字段和组合语义。 |
| `authz/resource-selector-grammar.md` | Resource selector 的语法、匹配范围和解析规则。 |
| `authz/event-auth-state-resolution.md` | Move、Anchor、Lattice、bottom diagnostics、auth refs、membership、policy cells、history sharing 与 E2EE covered frontier。 |
| `authz/policy-server.md` | Policy Server 风险判断与签名决策。 |
| `governance/join-policy.md` | Join Rule、邀请、knock / restricted / approval 流程和 history visibility 联动。 |
| `governance/history-visibility.md` | `world_readable` / `shared` / `invited` / `joined` / `restricted` 的精确定义、preview / peek policy、public plaintext Realm 与 E2EE history key share。 |
| `governance/content-moderation.md` | 举报、E2EE franking、Realm/Organization 审核策略、个人屏蔽入口。 |
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
| `sync/sovereign-deployment.md` | 高安全自建网络、sovereign client、DID resolver policy、sovereign deployment 下 External Collaboration Realm 的强制 policy、enclave、导入导出和撤销规则。 |

### 4.6 发现、目录与用户状态

| 文档 | 内容 |
| --- | --- |
| `discovery/discovery-directory.md` | Realm / Organization / Actor / Applet discoverability、私密联系人发现与目录服务。 |
| `discovery/object-addressing.md` | 客户端无关可分享对象地址：`web+cokret:` URI scheme、HTTPS 落地、link 类型与 `resolve_target`。 |
| `discovery/profiles-presence.md` | Actor profile、presence、typing、用户目录。 |
| `discovery/client-preferences.md` | Account data、私有标签、通知偏好、个人 blocklist、联系人 / Realm 本地备注。 |
| `discovery/push-notifications.md` | 推送规则、推送网关、E2EE 脱敏推送。 |
| `discovery/read-receipts.md` | Read receipt 与 read cursor。 |

### 4.7 加密、设备与媒体

| 文档 | 内容 |
| --- | --- |
| `crypto-media/device-lifecycle.md` | 设备身份、登录与授权边界、SSO/OIDC gateway、多设备配对、to-device 消息、cross-signing、secret storage、key backup。 |
| `crypto-media/encryption-and-audit.md` | MLS E2EE、MLS Governance Binding（`governance_binding` payload + `covered_frontier_cell`）、KeyPackage lifecycle、minimal-metadata Realm 与 master-agent control 边界（核心机制）。 |
| `crypto-media/audited-e2ee.md` | 可选 hardening profile：`ck.profile.attested_audit.e2ee.v1` / `ck.profile.disclosed_audit.e2ee.v1` 的 audit policy、join warning、强制留痕、RYW receipt、forbidden marketing terms。 |
| `crypto-media/media-and-blob.md` | Blob metadata、thumbnail、authenticated media、asset privacy policy。 |
| `crypto-media/webrtc-signaling.md` | 音视频通话、会议、TURN/STUN/ICE、SFU/MCU。 |

### 4.8 扩展、Agent 与集成

| 文档 | 内容 |
| --- | --- |
| `extensions/applet-integration.md` | Applet / bridge / bot / Ghost Actor / portal Realm。 |
| `extensions/applet-schema.md` | Applet schema 与 OpenAPI binding。 |
| `extensions/agent-protocol-interop.md` | A2A / ACP / external agent protocol handoff。 |
| `extensions/mimi-interop.md` | MIMI Provider Facade、room binding、content/policy/identity mapping。 |
| `sync/third-party-invites.md` | 3PID 邀请与认领。 |

> `models/realm-links.md`、`models/space-hierarchy.md` 与 `models/extension-objects.md` 的权威登记在 [§4.3 对象模型与交互](#43-对象模型与交互)；扩展场景从那里跳转，本组不重复整行登记。

### 4.9 Schema、编码与一致性

| 文档 | 内容 |
| --- | --- |
| `conformance/README.md` | conformance 目录入口、阅读顺序和 artifact/向量使用说明。 |
| `conformance/encoding.md` | Canonical JSON、ID、hash、signature、cursor、HLC、rank。 |
| `conformance/conformance-vectors.md` | 合并的一致性测试向量：§1 Encoding & crypto（canonical JSON / digest / signature binding / HLC / cursor / encrypted envelope）、§2 State resolution（并发 membership / capability / governance）、§3 Redaction（约束与可见性）、§4 Capability（delegation / revoke / approval）、§5 Sync（client sync / pagination / snapshot / MLS epoch backfill）。 |
| `conformance/schema-registry.md` | 标准 schema / event type registry。 |
| `conformance/query-schema.md` | View / Search / Inbox 可复用查询形状。 |
| `conformance/snapshot-schema.md` | Snapshot manifest、chunk、signature、encrypted envelope。 |
| `conformance/scalability-constraints.md` | v1 wire、授权、Move/Anchor/Lattice、Board/Relation/View 和 E2EE 的规模上限。 |
| `conformance/conformance-suite.md` | 自动化互操作 suite、向量优先级、组件测试矩阵。 |
| `conformance/conformance-profiles.md` | 实现 profile 与一致性测试范围。 |

### 4.10 实现指南

这些文档不是新的协议真相源，而是把 artifact 消费、参考实现和发布集成路径串起来：

| 文档 | 内容 |
| --- | --- |
| `guides/artifact-consumption.md` | SDK、cotest、yougen、soland 等下游如何消费 registry、OpenAPI、profiles 与 drift artifacts。 |
| `guides/reference-implementation-guide.md` | 参考实现的模块边界、生成链路、测试入口和发布前检查顺序。 |
| `guides/migrating-from-matrix.md` | 面向 Matrix 实现者的 informative 设计取舍对照（非真相源）；§4.1 同步列出便于概览读者定位。 |

## 5. 拆分原则

后续新增能力应按以下规则放置：

- 改变身份、DID、handle、claim 的内容，放入身份与隐私组。
- 改变共享状态有效性的内容，放入授权、治理与状态组。
- 改变服务 API 或 transport 的内容，放入同步、服务与联邦组。
- 新业务能力优先做 profile，例如 Agent、Applet、WebRTC。
- 不要把服务部署角色写成身份主体；不要把 UI 投影写成真相源。
