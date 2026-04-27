# Spec Map

## 1. 目标

本文是 Contrix 规范的阅读入口。它按协议平面组织文档，避免读者在大量单文件中迷失。

若本文与具体规范冲突，以具体规范中的 MUST / SHOULD 规则为准。

## 2. 推荐阅读顺序

初次理解协议时，建议按以下顺序阅读：

1. `overview/architecture.md`：先理解分层、角色和信任边界。
2. `overview/glossary.md`：确认术语含义，尤其是 Principal / Actor / Organization / Space / Repo / Relay。
3. `models/object-model-core.md` 与 `models/object-model-standard.md`：理解协作图和标准对象。
4. `identity/identity-did.md`、`identity/identity-handles.md`、`identity/progressive-disclosure.md`：理解身份、handle 和隐私披露。
5. `authz/capabilities.md`、`authz/event-auth-state-resolution.md`：理解权限和 Space 状态机。
6. `sync/operations-sync.md`、`sync/client-sync.md`、`sync/service-surface.md`：理解写入、同步和服务面。
7. 按业务需要阅读扩展 profile，例如 Applet、Agent、WebRTC、Social、Directory。

## 3. 核心概念边界

### 3.1 Principal / Actor / Organization

- Principal 是身份根，通常由 DID 表示。
- Actor 是 Principal 在 Space 或协作图中的行为者视图。
- Organization 是一种 Principal，负责治理、签发、服务委派和官方背书。
- Organization 不是 Space；Space 是协作数据边界。

### 3.2 Space / Feed / View

- Space 是复制、授权、schema、policy、membership、history visibility 和 E2EE 的边界。
- Feed 是一种社交或活动时间线投影源，不替代 Space。
- View 是投影定义，不拥有真相数据。

### 3.3 Repo / Repo Service / Relay / Index

- Repo 是可验证发布日志，不等同于服务器。
- Repo Service 是访问或托管 Repo 的服务。
- Relay 是传播层，不是真相源。
- Index 是查询和投影层，不是真相源。

### 3.4 Discoverability / Join Rule / History Visibility

- Discoverability 决定资源能否被发现。
- Join Rule 决定如何加入。
- History Visibility 决定加入后能看到多少历史。
- 三者必须分开判断。

### 3.5 Capability / Moderation / Personal Blocklist

- Capability 决定基础动作权限。
- Moderation Policy 可以 deny、quarantine 或 require review，但不能授予权限。
- Personal Blocklist 是个人私有过滤，只影响自己的客户端体验。

### 3.6 Public Feed / Circle Feed

- Public Feed 适合公开索引、关注和广播。
- Circle Feed 必须使用 Audience Policy、受众快照和可选 E2EE。
- 朋友圈不能靠“公开发布后 UI 隐藏”实现。

## 4. 文档分组

### 4.1 总览与决策

| 文档 | 内容 |
| --- | --- |
| `README.md` | 项目定位、设计目标、规范入口。 |
| `spec-map.md` | 本文，按协议平面组织阅读路径。 |
| `overview/architecture.md` | 顶层架构、部署拓扑、信任边界。 |
| `overview/design-questions.md` | 早期关键设计问题与决策记录。 |
| `overview/gap-analysis.md` | 当前实现缺口和落地优先级。 |
| `overview/glossary.md` | 全局术语表。 |

### 4.2 身份、组织与隐私

| 文档 | 内容 |
| --- | --- |
| `identity/identity-did.md` | DID、did:uuid、DID Document、key log、Organization ownership。 |
| `identity/identity-handles.md` | Handle 解析、双向绑定、claim / attestation。 |
| `identity/progressive-disclosure.md` | 渐进披露、presentation request、disclosure policy、私有存储。 |
| `identity/tsp-integration.md` | TSP 作为可选 transport / trust binding。 |
| `identity/key-management.md` | 密钥、恢复、Accountable Actor。 |

### 4.3 对象模型与交互

| 文档 | 内容 |
| --- | --- |
| `models/object-model-core.md` | Space、Actor、Entity、Relation、Event、View 核心对象。 |
| `models/object-model-standard.md` | Task、Message、Run、Memory、Social Post 等标准类型。 |
| `models/data-structures.md` | 核心对象字段级定义：必填性、类型、枚举、约束和说明。 |
| `models/conversation-model.md` | Channel、Topic、Message、Thread、Mention、Reaction。 |
| `models/views.md` | Board、Table、Timeline、Graph 等投影。 |
| `models/content-types.md` | 富文本、媒体、投票、内容 block。 |
| `models/social-graph.md` | 社交 feed、朋友圈、follow/contact/circle、Audience Policy。 |

### 4.4 授权、治理与状态

| 文档 | 内容 |
| --- | --- |
| `authz/capabilities.md` | Capability、delegation、revocation、claim 条件。 |
| `authz/grant-constraint-schema.md` | Grant constraint schema。 |
| `authz/event-auth-state-resolution.md` | Space version、auth refs、membership、state resolution。 |
| `authz/policy-server.md` | Policy Server 风险判断与签名决策。 |
| `authz/moderation.md` | 举报、Space/Organization 审核策略、个人屏蔽入口。 |
| `security/server-threat-model.md` | 服务端攻击模型与反滥用规则。 |
| `authz/account-lifecycle.md` | 账号停用、锁定、擦除、session revocation。 |

### 4.5 同步、服务与联邦

| 文档 | 内容 |
| --- | --- |
| `sync/operations-sync.md` | Repo-first 发布、op、snapshot、冲突收敛。 |
| `sync/client-sync.md` | 客户端增量同步、timeline、state_after、to_device。 |
| `sync/service-surface.md` | 最小服务面：identity、repo、relay、index、directory、blob、authz。 |
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
| `discovery/discovery-directory.md` | Space / Organization / Actor / Applet discoverability 与目录服务。 |
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
| `crypto-media/encryption-and-audit.md` | MLS E2EE 与可审查留痕。 |
| `crypto-media/media-and-blob.md` | Blob metadata、thumbnail、authenticated media。 |
| `crypto-media/webrtc-signaling.md` | 音视频通话、会议、TURN/STUN/ICE、SFU/MCU。 |

### 4.8 扩展、Agent 与集成

| 文档 | 内容 |
| --- | --- |
| `extensions/applet-integration.md` | Applet / bridge / bot / ghost actor / portal Space。 |
| `extensions/applet-schema.md` | Applet schema 与 OpenAPI 草案。 |
| `extensions/agent-memory.md` | Agent memory、run、promotion、review。 |
| `extensions/agent-protocol-interop.md` | A2A / ACP legacy / external agent protocol handoff。 |
| `sync/third-party-invites.md` | 3PID 邀请与认领。 |
| `models/space-hierarchy.md` | Space parent/child、继承、lazy link、循环处理。 |

### 4.9 Schema、编码与一致性

| 文档 | 内容 |
| --- | --- |
| `conformance/encoding.md` | Canonical JSON、ID、hash、signature、cursor、HLC、rank。 |
| `conformance/encoding-conformance-vectors.md` | Canonical JSON、hash、event/commit digest、signature binding、HLC、cursor 的一致性测试向量。 |
| `conformance/schema-registry.md` | 标准 schema / event type registry。 |
| `conformance/state-resolution-conformance-vectors.md` | 并发 membership/capability/governance state resolution向量。 |
| `conformance/redaction-conformance-vectors.md` | redaction 约束与可见性向量。 |
| `conformance/capability-conformance-vectors.md` | delegated capability、revoke 回滚、approval 约束向量。 |
| `conformance/query-schema.md` | Index / View / Inbox 查询语法。 |
| `conformance/snapshot-schema.md` | Snapshot manifest、chunk、signature、encrypted envelope。 |
| `conformance/conformance-suite.md` | 自动化互操作 suite、向量优先级、组件测试矩阵。 |
| `conformance/conformance-profiles.md` | 实现 profile 与一致性测试范围。 |
| `conformance/sync-conformance-vectors.md` | Client Sync、pagination、snapshot、MLS epoch backfill 的一致性测试向量。 |
| `extensions/matrix-compat-gap.md` | Matrix 能力差距和取舍。 |

## 5. 拆分原则

后续新增能力应按以下规则放置：

- 改变身份、DID、handle、claim 的内容，放入身份与隐私组。
- 改变共享状态有效性的内容，放入授权、治理与状态组。
- 改变服务 API 或 transport 的内容，放入同步、服务与联邦组。
- 新业务能力优先做 profile，例如 social、agent、applet、webrtc。
- 不要把服务部署角色写成身份主体；不要把 UI 投影写成真相源。


