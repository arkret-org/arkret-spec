---
title: Contrix Protocol
---

## 1. 一句话理解

`contrix-spec` 是 **Contrix v1 去中心化协作协议规范**。其核心不是界面，而是“可验证协作事实 + 可投影的对象语义”：

- 身份主键：DID principal
- 数据主语：Realm / Space（含 Board/List）/ Flow / Message / Relation / Event / View / Capability
- 审计主语：signed Event + per-actor event chain
- 权限主语：capability
- 呈现主语：views / projection
- 扩展承载：Morph + schema / profile-defined facets

## 2. 不做什么

Contrix v1 明确不把以下内容作为基础互操作必需项：

- 聊天消息作为唯一协议对象根
- 房间状态机作为全协议统一底座
- 全网共识链
- 强绑定某个 SaaS UI 外壳
- 以 embedding、向量库替代协议真相源
- 以高复杂字段级/字节级 ACL 作为第一阶段互操作要求

## 3. 规范地图

[spec-map.md](./spec-map.md) 是总目录。README 仅保留顶层入口与实施路径，避免因 profile 增长变成长清单。

### 3.1 一分钟实施链路（实现导向）

1. 完成 DID 与服务发现，建立 principal/service 绑定。
2. Realm 创建后锁定 schema 与策略基线。
3. Event-first 写入并做初始 auth state 校验。
4. 客户端执行 `event-auth-state-resolution` 收敛。
5. 使用 snapshot / frontier 建立快速重建路径。
6. 讨论类空间先验 MLS state，再决定是否解密展示。
7. reducer 产出 canonical projection，UI 只消费 projection。
8. 失败场景进入可恢复退化状态（如 `decryption_pending`、`state_mismatch`）。

### 3.2 先读路径

- `overview/architecture.md`：架构、服务角色、部署与信任边界。
- `overview/glossary.md`：Principal / Actor / Organization / Realm / Event / Principal Server 等术语。
- `models/overview.md`：对象总览、typed-id 一览、设计原则。
- `models/common-fields.md`、`models/realm-and-space.md`、`models/flow-and-message.md`：公共字段、Realm/Space、Flow/Message 等核心对象。
- `models/relation.md`、`models/morph.md`、`models/event-and-patch.md`：关系、Morph 扩展、事件与字段增量。
- `identity/identity-did.md`、`identity/identity-handles.md`：身份、handle、渐进披露（progressive disclosure 在 `identity-handles.md` §16）。
- `authz/capabilities.md`、`authz/event-auth-state-resolution.md`：授权与状态。
- `sync/operations-sync.md`、`sync/client-sync.md`、`sync/service-surface.md`、`sync/service-http-binding.md`：同步与服务。
- `security/server-threat-model.md`：安全边界与抗滥用。
- 场景扩展：Applet、Agent、WebRTC、Directory、Moderation、Federation、Sovereign Deployment。

### 3.3 目录结构分层

- 总览与决策
- 身份、组织与隐私
- 对象模型与交互
- 授权、治理与状态
- 同步、服务与联邦
- 发现、目录与用户状态
- 加密、设备与媒体
- 扩展、Agent 与集成
- Schema、编码与一致性

## 4. 关键设计决策

### 4.1 身份

- `principal_id = DID URI`，Handle 只作为可迁移的人类可读入口。
- Resolver policy 必须声明可用 DID method、默认 method、信任根与 fail-closed 规则。
- **v1 core 默认 principal DID method 为 `did:webvh`**：在 `did:web` 之上叠加 `did.jsonl` 历史链 + SCID + witness evidence，提供可审计的 DID 控制历史，抵御 DNS / TLS 单点失陷。
- `did:web` 仅作为 **service DID 默认 method** 与 **`personal_node` deployment profile 的可选 principal method**；`did:webvh` hosting 暂时不可达时只允许 §3.4 定义的 cache-only degraded mode，不得 live fallback 到 `did:web`。
- 临时、测试、设备、邀请、bootstrap 使用 `did:key`；不得作为默认长期主身份。
- 钱包绑定（`did:pkh`）、AT Protocol 互通（`did:plc` adapter）、KERI 系列等是 interop extension profile，不属于 v1 core 互操作必需。
- DID 文档、history chain 与 method evidence 需按各自 method 的 verifier 校验。

### 4.2 对象模型

- 所有持久协作修改必须是 signed Event。
- 所有共享状态由授权 Event 集合 reducer 收敛后生成。
- Realm 是权限、成员、schema、policy 的边界。
- Flow 为统一协作对象，默认入口由 track primary 解析规则表达，同一 `flow_id` 下可切换默认 track。
- Morph 是扩展载体，不单独定义核心能力和排序语义。
- `notification` 是投影用途，不是 canonical truth。

### 4.3 看板与会话

- 看板定义：`Board Space -> List Space -> Flow`。
- 会话定义：`Flow(discussion track) -> Message`。
- `cx.flow.tracks.update` 是 track 配置（启用 / 关闭 / 切换 primary / 修改 profile）的唯一写入路径，不复制对象、不迁移历史。
- Track 不携带独立 access；discussion 完全继承源 Realm。需要独立成员、历史或 E2EE 边界时，必须升级为 linked Realm 并通过 `Flow.discussion_realm_ref` 引用。

### 4.4 同步与真相模型

- signed Event Envelope 是发布最小单位，actor event chain 是重放和可验证基础。
- Principal Server / Sync Service 是同步基础设施，不是唯一真相源。
- 搜索、inbox、notification、projection 默认由客户端或 SDK 派生。
- 未加密私有正文不得发送到未授权第三方服务。
- Event 写入具备幂等性；撤回通过 redaction 收敛，不等于全局物理删除。

### 4.5 授权

- 权限采用 capability 模型，授权与能力必须显式、可验证、可撤销。
- accountable actor 需追溯 `responsible / guardian / controller`。
- 高风险动作支持 approval constraint 与治理式审批约束。
- `handle` 不承担权限主键作用，授权主体以 DID 或 selector 条件表述。
- 消息、撤回、Flow 管理、排序等动作均有独立动作语义。

## 5. 规范语言与实现声明

本规范的强制关键字为 RFC 2119 语义：

- `MUST`
- `SHOULD`
- `MAY`

各实现声明支持范围时需同时给出：

- `protocol_version`（v1 使用 `1.0`）
- conformance profile（如 `cx.profile.full_client.v1`）
- schema / reducer profile（如 `cx.schema.event.v1` 与 `cx.profile.core_event_store.v1`）
- 尺度与分页边界（默认见 `conformance/scalability-constraints.md`）

新增能力优先通过 profile / 扩展章节 / registry 条目引入。

## 6. 当前覆盖范围

- 身份、handle、组织主体、服务 DID 与进阶披露
- Realm / Flow / Message / Morph / Relation / Event / View / Capability
- 字段级结构、必填性、枚举与约束
- capability、delegation、claim 条件、policy 与 moderation policy
- Event-first 发布、Principal Server 同步、客户端查询与投影
- MLS E2EE、设备验证、WebRTC、blob 与媒体
- Applet、Agent 互通、Directory、Federation、Sovereign deployment

## 7. 一句话总结

Contrix 的目标是统一协作对象语义，建立“可验证审计 + 长期可恢复”的协作基础设施，而不是绑定聊天协议外壳。
