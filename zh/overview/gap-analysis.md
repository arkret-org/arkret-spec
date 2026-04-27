# 实现缺口分析

## 1. 目标

本文记录 Contrix 进入稳定可落地阶段前仍需补齐或持续验证的实现缺口。

本分析不以任何历史版本为参照，也不要求兼容既有数据模型；它只回答当前协议自身还需要哪些可测试、可互操作、可审计的工件。

## 2. 当前已覆盖的能力

| 能力主题 | 规范位置 | 当前状态 |
| --- | --- | --- |
| DID / Handle / 服务发现 | `identity-did.md`, `identity-handles.md`, `service-surface.md` | 已覆盖，需要持续补测试向量 |
| Space / Entity / Relation | `object-model-core.md`, `object-model-standard.md`, `data-structures.md`, `space-hierarchy.md` | 已覆盖核心模型、字段级结构和 Space 层级规则 |
| 消息 / 话题 / 线程 | `conversation-model.md`, `content-types.md` | 已覆盖主要语义 |
| 事件替换 / 撤回 / reaction | `conversation-model.md`, `operations-sync.md`, `event-auth-state-resolution.md` | 已覆盖基础语义和 redaction 规则 |
| 同步 / backfill / snapshot | `operations-sync.md`, `client-sync.md`, `snapshot-schema.md`, `sync-conformance-vectors.md`, `service-surface.md` | 已覆盖原则、schema、客户端同步面和首批一致性向量 |
| 权限 / capability | `capabilities.md`, `grant-constraint-schema.md` | 已覆盖，需要更多 conformance vectors |
| E2EE / 设备 / 密钥 | `encryption-and-audit.md`, `device-crypto-verification.md`, `key-management.md` | 已覆盖主要流程 |
| 推送 | `push-notifications.md` | 已覆盖隐私保护推送模型 |
| 已读 / 未读 | `read-receipts.md`, `read-notification-schema.md` | 已覆盖 |
| profile / presence / typing | `profiles-presence.md` | 已覆盖 |
| 3PID 邀请 | `third-party-invites.md` | 已覆盖草案 |
| WebRTC / 会议 | `webrtc-signaling.md` | 已覆盖 P2P、SFU、TURN/STUN/ICE、录制和屏幕共享 |
| Applet / Bridge | `applet-integration.md`, `applet-schema.md` | 已覆盖注册、命名空间和交易推送 |
| Agent 协议互操作 | `agent-protocol-interop.md` | 已覆盖 A2A / ACP legacy 等外部 agent transport handoff |
| Transport binding | `transport-bindings.md`, `api-conventions.md` | 已明确 HTTP/JSON 是默认 binding，不是协议核心唯一绑定 |

## 3. 关键缺口

### 3.1 Conformance Suite

需要补：

- canonical JSON 测试向量（首批见 `encoding-conformance-vectors.md`，仍需机器可执行 fixture）
- event id / hash / signature 测试向量（首批见 `encoding-conformance-vectors.md`，仍需真实 crypto fixture）
- state resolution 冲突测试向量
- redaction preserved fields 测试向量
- capability grant / revoke / derived grant 测试向量
- sync token / pagination / cursor 测试向量（首批见 `sync-conformance-vectors.md`，仍需机器可执行 fixture）
- E2EE device verification / key backup / to-device 测试向量
- Applet namespace / transaction 幂等测试向量
- Space hierarchy / Lazy Link / inheritance 测试向量

优先级：**P0**。

### 3.2 OpenAPI 与非 HTTP Binding 映射

当前已有默认 HTTP/JSON binding 草案，但仍需将核心 operation 同时落成：

- OpenAPI for HTTP/JSON binding
- gRPC service mapping
- WebSocket/SSE frame schema
- message queue envelope schema
- libp2p / P2P message envelope

优先级：**P0/P1**。

### 3.3 Schema Registry 完整化

当前 `data-structures.md` 已补核心对象字段级定义，但仍需要把以下内容从文档草案落成机器可验证 JSON Schema / OpenAPI components：

- `cx.space.*`
- `cx.entity.*`
- `cx.relation.*`
- `cx.message.*`
- `cx.task.*`
- `cx.view.*`
- `cx.capability.*`
- `cx.mls.*`
- `cx.audit.*`
- `cx.notification.*`
- `cx.receipt.*`
- `cx.call.*`
- `cx.agent.*`

优先级：**P0**。

### 3.4 Federation Hardening

需要继续细化：

- service DID authentication
- federation transaction replay protection
- relay-to-relay op exchange
- cross-domain Space join
- remote capability verification
- fork / equivocation detection
- abuse handling and quarantine
- policy server decision exchange

优先级：**P1**。

### 3.5 Directory, Search and Preview

需要补：

- Space directory
- Actor directory
- discoverability policy
- encrypted Space 的本地搜索与服务器搜索边界
- search result authorization filtering
- preview / summary 的最小披露规则
- hierarchy query 与 directory 的结合规则

优先级：**P1**。

### 3.6 Moderation and Abuse Operations

需要补：

- report object schema
- moderation queue schema
- policy list subscription
- block / mute / hide / quarantine semantics
- server-level ACL for service operators
- appeal / audit trail
- spam scoring 和 reputation 输入边界

优先级：**P1**。

### 3.7 Production Profiles

需要为以下部署形态定义推荐参数：

- personal node
- small team node
- enterprise node
- public relay
- E2EE client
- Applet bridge
- policy server
- media/SFU service
- agent runtime

优先级：**P1**。

## 4. 建议补文档顺序

1. Conformance test vectors（已开始补 `sync-conformance-vectors.md` 与 `encoding-conformance-vectors.md`，下一步应补 state resolution / redaction / capability 等机器 fixture）。
2. 完整 OpenAPI 与非 HTTP binding 映射。
3. 机器可验证 schema registry。
4. Federation hardening。
5. Directory / search / preview。
6. Moderation / abuse operation schema。
7. Production deployment profiles。

## 5. 当前结论

当前规范的主要方向已经清晰：身份、对象图、授权、同步、加密、Applet、Agent、会议和 transport binding 都已有独立章节。

接下来最关键的工作不是继续扩大概念范围，而是把协议收敛成可测试工件：

- schema
- endpoint / operation mapping
- encoding
- proof / signature profile
- conformance suite
- feature profile

这些完成后，Contrix 才能从设计草案进入可互操作实现阶段。
