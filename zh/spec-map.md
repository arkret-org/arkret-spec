# Spec Map

## 1. 目标

本文是 Contrix 规范的阅读入口。它按协议平面组织文档，避免读者在大量单文件中迷失。

若本文与具体规范冲突，以具体规范中的 MUST / SHOULD 规则为准。

### 1.1 规范权威层级

- `artifacts/registry/contract-catalog.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `artifacts/registry/*.json` 是从 canonical catalog 生成的机器视图；实现、SDK 和 lint 应消费这些生成物，而不是手抄 Markdown 表。
- `zh/sync/contrix-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape；它描述 HTTP 形状，不替代抽象 `operation_id`、Event kind、typed ID 或 reducer 语义。
- `zh/*/*.md` 文档主要承担解释、边界说明和阅读路径；除明确标注“生成视图”外，不应再手工维护穷尽清单。
- `artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵；`conformance/conformance-profiles.md` 是其说明视图。

## 2. 推荐阅读顺序

初次理解协议时，建议按以下顺序阅读：

1. `overview/architecture.md`：先理解分层、实际服务器角色和信任边界。
2. `overview/glossary.md`：确认术语含义，尤其是 Principal / Actor / Organization / Space / Event / Principal Server。
3. `models/object-model-core.md` 与 `models/object-model-standard.md`：理解协作图和标准对象。
4. `identity/identity-did.md`、`identity/identity-handles.md`、`identity/progressive-disclosure.md`：理解身份、handle 和隐私披露。
5. `authz/capabilities.md`、`authz/event-auth-state-resolution.md`：理解权限和 Space 状态机。
6. `sync/operations-sync.md`、`sync/client-sync.md`、`sync/service-surface.md`：理解写入、同步和服务面。
7. 按业务需要阅读扩展 profile，例如 Applet、Agent、WebRTC、Directory。

## 3. 核心概念边界

### 3.1 Principal / Actor / Organization

- Principal 是身份根，通常由 DID 表示。
- Actor 是 Principal 在 Space 或协作图中的行为者视图。
- Organization 是一种 Principal，负责治理、签发、服务委派和官方背书。
- Organization 不是 Space；Space 是协作数据边界。

### 3.2 Space / Standard Objects / Morph / View

- Space 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- Flow、Board、List、Message 是协议标准对象，拥有明确主语义和 reducer。
- Morph 是开放对象，用于 schema / profile 扩展类型；facets 是 schema/profile 声明后的能力提示和查询标签，不是对象身份，也不是授权、状态机、排序或 reducer 语义的唯一来源。
- `room` / `card` 退化为 `kind`；Flow 的 `synthesis` / `discussion` branch 分别承载正式表达与讨论能力，discussion branch 独立承载 membership、历史与 E2EE 权限。
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
| `overview/design-questions.md` | 早期关键设计问题与决策记录。 |
| `overview/gap-analysis.md` | 当前闭环状态、已收敛工件和剩余工程化事项。 |
| `overview/glossary.md` | 全局术语表。 |

### 4.2 身份、组织与隐私

| 文档 | 内容 |
| --- | --- |
| `identity/identity-did.md` | DID、默认 `did:plc`、DID Document、method adapter、Organization ownership。 |
| `identity/identity-handles.md` | Handle 解析、connection identifier、双向绑定、claim / attestation。 |
| `identity/progressive-disclosure.md` | 渐进披露、presentation request、disclosure policy、私有存储。 |
| `identity/tsp-integration.md` | TSP 作为可选 transport / trust binding。 |
| `identity/key-management.md` | 密钥、恢复、Accountable Actor。 |

### 4.3 对象模型与交互

| 文档 | 内容 |
| --- | --- |
| `models/object-model-core.md` | Space、Actor、Flow、Board、List、Message、Morph、Relation、Event、View 核心对象。 |
| `models/object-model-standard.md` | 标准对象、Morph 类型、标准 facets 与 schema evolution。 |
| `models/data-structures.md` | 核心对象字段级定义：必填性、类型、枚举、约束和说明。 |
| `models/conversation-model.md` | Flow discussion branch、Message、Mention、Reaction。 |
| `models/views.md` | Board/List/Flow、Table、Timeline、Graph 等投影。 |
| `models/content-types.md` | 富文本、媒体、投票、内容 block。 |

### 4.4 授权、治理与状态

| 文档 | 内容 |
| --- | --- |
| `authz/capabilities.md` | Capability、delegation、revocation、claim 条件。 |
| `authz/grant-constraint-schema.md` | Grant constraint schema。 |
| `authz/event-auth-state-resolution.md` | Space version、auth refs、membership、policy components、history sharing、state resolution。 |
| `authz/policy-server.md` | Policy Server 风险判断与签名决策。 |
| `authz/moderation.md` | 举报、E2EE franking、Space/Organization 审核策略、个人屏蔽入口。 |
| `security/server-threat-model.md` | 服务端攻击模型与反滥用规则。 |
| `authz/account-lifecycle.md` | 账号停用、锁定、擦除、session revocation。 |

### 4.5 同步、服务与联邦

| 文档 | 内容 |
| --- | --- |
| `sync/operations-sync.md` | Event-first 发布、Event Envelope、snapshot、冲突收敛。 |
| `sync/client-sync.md` | 客户端增量同步、timeline、state_after、to_device。 |
| `sync/service-surface.md` | 最小服务面与实际服务组合：principal server、identity、events、sync、directory、blob、authz、device/key、push、applet、agent、media、moderation。 |
| `sync/service-http-binding.md` | 默认 HTTP/JSON binding 路径、请求/响应和标准错误码。 |
| `sync/service-api-schema.md` | 核心 request / response schema。 |
| `sync/api-conventions.md` | 错误、分页、幂等、feature discovery。 |
| `sync/transport-bindings.md` | HTTP/REST、gRPC、WebSocket、SSE、MQ、libp2p 等 binding。 |
| `sync/federation.md` | 跨域联邦模型。 |
| `sync/federation-wire.md` | 联邦交易与线级格式。 |
| `sync/sovereign-deployment.md` | 高安全自建网络、sovereign client、DID resolver policy、受控外部协作 Space、enclave、导入导出和撤销规则。 |

### 4.6 发现、目录与用户状态

| 文档 | 内容 |
| --- | --- |
| `discovery/discovery-directory.md` | Space / Organization / Actor / Applet discoverability、私密联系人发现与目录服务。 |
| `discovery/profiles-presence.md` | Actor profile、presence、typing、用户目录。 |
| `discovery/client-preferences.md` | Account data、私有标签、通知偏好、个人 blocklist。 |
| `discovery/push-notifications.md` | 推送规则、推送网关、E2EE 脱敏推送。 |
| `discovery/read-receipts.md` | Read receipt 与 read marker。 |
| `discovery/read-notification-schema.md` | read / notification schema。 |

### 4.7 加密、设备与媒体

| 文档 | 内容 |
| --- | --- |
| `crypto-media/device-crypto-verification.md` | 设备身份、cross-signing、to-device、secret storage、key backup。 |
| `crypto-media/devices-and-auth.md` | 多设备、登录、认证、SSO。 |
| `crypto-media/encryption-and-audit.md` | MLS E2EE、MLS-bound state、KeyPackage lifecycle、minimal metadata Space 与可审查留痕。 |
| `crypto-media/media-and-blob.md` | Blob metadata、thumbnail、authenticated media、asset privacy policy。 |
| `crypto-media/webrtc-signaling.md` | 音视频通话、会议、TURN/STUN/ICE、SFU/MCU。 |

### 4.8 扩展、Agent 与集成

| 文档 | 内容 |
| --- | --- |
| `extensions/applet-integration.md` | Applet / bridge / bot / ghost actor / portal Space。 |
| `extensions/applet-schema.md` | Applet schema 与 OpenAPI binding。 |
| `extensions/agent-protocol-interop.md` | A2A / ACP / external agent protocol handoff。 |
| `extensions/mimi-interop.md` | MIMI Provider Facade、room binding、content/policy/identity mapping。 |
| `sync/third-party-invites.md` | 3PID 邀请与认领。 |
| `models/space-hierarchy.md` | Space parent/child、继承、lazy link、循环处理。 |

### 4.9 Schema、编码与一致性

| 文档 | 内容 |
| --- | --- |
| `conformance/encoding.md` | Canonical JSON、ID、hash、signature、cursor、HLC、rank。 |
| `conformance/encoding-conformance-vectors.md` | Canonical JSON、hash、event digest、event-batch receipt digest、signature binding、HLC、cursor 的一致性测试向量。 |
| `conformance/schema-registry.md` | 标准 schema / event type registry。 |
| `conformance/state-resolution-conformance-vectors.md` | 并发 membership/capability/governance state resolution向量。 |
| `conformance/redaction-conformance-vectors.md` | redaction 约束与可见性向量。 |
| `conformance/capability-conformance-vectors.md` | delegated capability、revoke 回滚、approval 约束向量。 |
| `conformance/query-schema.md` | View / Search / Inbox 可复用查询形状。 |
| `conformance/snapshot-schema.md` | Snapshot manifest、chunk、signature、encrypted envelope。 |
| `conformance/scalability-constraints.md` | v1 wire、授权、state resolution、Board/Relation/View 和 E2EE 的规模上限。 |
| `conformance/conformance-suite.md` | 自动化互操作 suite、向量优先级、组件测试矩阵。 |
| `conformance/conformance-profiles.md` | 实现 profile 与一致性测试范围。 |
| `conformance/sync-conformance-vectors.md` | Client Sync、pagination、snapshot、MLS epoch backfill 的一致性测试向量。 |

## 5. 拆分原则

后续新增能力应按以下规则放置：

- 改变身份、DID、handle、claim 的内容，放入身份与隐私组。
- 改变共享状态有效性的内容，放入授权、治理与状态组。
- 改变服务 API 或 transport 的内容，放入同步、服务与联邦组。
- 新业务能力优先做 profile，例如 agent、applet、webrtc。
- 不要把服务部署角色写成身份主体；不要把 UI 投影写成真相源。



## Legacy contract removal entry（2026-05-03）

实现方如需确认 `subject` / `room` / `card` 到 `flow` 的迁移边界，应同时阅读：

- `artifacts/registry/legacy-compatibility-policy.json`
- `zh/guides/legacy-subject-room-card-to-flow-migration.md`

仓库 CI 已通过 `python tools/artifact_pipeline.py check` 阻止旧 typed ID、旧 schema ID 和旧 event kind 重新进入 active contract，并统一执行 machine-artifact mirror drift 与 registry lint。
