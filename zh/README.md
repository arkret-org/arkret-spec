# Contrix Protocol

## 1. 项目定位

`contrix-spec` 是 **Contrix v1 去中心化协作协议规范**。Contrix 明确采用：

- 以 **DID principal** 为身份根
- 以 **Space（含 Board / List 形态）/ Flow / Message / Morph / Relation / Event / View / Capability 协作图** 为数据根
- 以 **signed Event + per-actor event chain** 为审计根
- 以 **capability** 为权限根
- 以 **views/projections** 为人类展示根
- 以 **Event** 为协作事实根
- 以 **Flow、Board、List、Message** 承载标准协作语义，以 **Morph + schema/profile-declared facets** 承载开放扩展对象

它的目标不是“把聊天协议包装成看板”，而是定义一套能投影为看板、Flow 讨论流、Flow synthesis 面、表格、日历、树、图谱、甘特图和 agent 记忆的统一协作协议。

## 2. 设计目标

Contrix v1 聚焦以下目标：

1. 稳定身份  
   所有主体使用 DID 作为稳定 ID，Handle 只是可迁移的人类可读入口。
2. 面向对象协作  
   协议根抽象固定为 Space（含 Board / List 形态）、Actor、Flow、Message、Morph、Relation、Event、View、Capability；Flow 承载统一 identity，并通过 `kind` 与 `synthesis` / `discussion` branch 表达整理推进与讨论语义；标准对象承载主语义，Morph 通过 Space schema / Morph profile 扩展领域对象，facets 只作为声明后的能力提示和查询标签。
3. 去中心化同步  
   真相基底是 signed Event Envelope 和可验证 actor event chain，而不是单一中心数据库或 atprotocol/Git 式数据仓库。
4. 多交互模式  
   同一协议同时支持 kanban、list、table、calendar、gantt、chat、thread、forum、tree、graph 等模式。
5. 人类友好  
   数据必须天然能投影成看板、时间线、Flow activity、synthesis/discussion 双分支、审阅队列。
6. AI 友好  
   协议天然支持 agent principal、delegation 和外部协议 handoff。
7. 审计与恢复  
   编辑、撤回、授权变化、冲突收敛都必须可解释、可审计。

## 3. 非目标

Contrix v1 明确不把以下内容作为基础互操作必需项：

- 让聊天消息重新变成唯一数据根
- 房间状态机作为全协议统一底座
- 全网共识链
- 强绑定某个 SaaS 产品 UI
- 把 embedding 或向量库当作协议真相源
- 一开始就做极度复杂的字段级/字节级 ACL

## 4. 规范地图

完整分组阅读入口见 [spec-map.md](./spec-map.md)。README 只保留顶层入口，避免随着扩展 profile 增多而变成长清单。

### 4.1 一分钟执行链路（实现导向）

建议按以下顺序实现：

1. DID 与服务发现，完成 principal/service 绑定。  
2. 空间创建后锁定 `space_version` 与策略基线。  
3. Event first 写入，经过 auth state 初检。  
4. 客户端做 `event-auth-state-resolution` 收敛。  
5. snapshot/frontier 用于快速重建状态。  
6. 讨论类空间先做 MLS application state 绑定校验，再决定是否解密显示。  
7. reducer 产出 canonical projection；UI 仅消费 projection。  
8. 所有失败退化写入 `decryption_pending` / `state_mismatch` 的可恢复状态。  


核心阅读路径：

1. [architecture.md](./overview/architecture.md)：架构平面、Principal Server 部署形态、部署拓扑和信任边界。
2. [glossary.md](./overview/glossary.md)：术语边界，尤其是 Principal / Actor / Organization / Space / Event / Principal Server。
3. [object-model-core.md](./models/object-model-core.md) 与 [object-model-standard.md](./models/object-model-standard.md)：核心对象和标准类型，重点将 `card`、`room` 作为 `flow.kind`（非独立 typed-id）理解。
   字段级定义见 [data-structures.md](./models/data-structures.md)。
4. [identity-did.md](./identity/identity-did.md)、[identity-handles.md](./identity/identity-handles.md)、[progressive-disclosure.md](./identity/progressive-disclosure.md)：身份、handle、隐私披露。
5. [capabilities.md](./authz/capabilities.md) 与 [event-auth-state-resolution.md](./authz/event-auth-state-resolution.md)：授权、membership、state resolution。
6. [operations-sync.md](./sync/operations-sync.md)、[client-sync.md](./sync/client-sync.md)、[service-surface.md](./sync/service-surface.md)、[service-http-binding.md](./sync/service-http-binding.md)：写入、同步、实际服务组合、服务面和默认 HTTP binding。
7. 按场景阅读扩展：Applet、Agent、WebRTC、Directory、Moderation、Federation、Sovereign Deployment。
8. 与 Matrix 的核心区别见 [matrix-core-differences.md](./overview/matrix-core-differences.md)。
9. 安全加固对照阅读：[server-threat-model.md](./security/server-threat-model.md)（服务端攻击模型与抗滥用规则）

当前规范按以下平面组织：

- 总览与决策
- 身份、组织与隐私
- 对象模型与交互
- 授权、治理与状态
- 同步、服务与联邦
- 发现、目录与用户状态
- 加密、设备与媒体
- 扩展、Agent 与集成
- Schema、编码与一致性

## 5. 核心设计决定

### 5.1 身份

> 详细设计决定与取舍分析见 [design-questions.md](./overview/design-questions.md)。

- `principal_id = DID URI`
- Handle 与 DID 分离
- 默认普通用户 DID 方法为 `did:plc`
- Contrix 不定义自有 DID method；新对象和规范示例 MUST 使用现有 DID method
- 长期 principal DID SHOULD 支持密钥轮换、恢复、停用或可验证历史
- Resolver policy MUST 声明 allowed methods、默认 method、trust roots、method capability 与 fail-closed 规则
- DID 文档、operation history 和 method evidence 由对应 DID method 的 resolver / verifier 校验
- 解析模式参考 atprotocol 的 handle 双向验证，但更偏向协作与多服务发现
- 组织 / service DID SHOULD 使用 `did:web`；高保证组织 SHOULD 使用 `did:webvh`
- `did:key` 仅用于临时、测试、设备、邀请或 bootstrap 场景；`did:pkh` 仅用于钱包身份绑定
- 对 `did:plc`、`did:web` 等 DID，采用 `method adapter + normalized principal view + sidecar` 兼容层；保留原始文档与历史，不强行改写成私有 DID
- DID 的哈希锚定 `inception_key`；普通密钥轮换不换 DID，只有不可恢复时才考虑例外性身份重建

### 5.2 数据

> 对象字段级定义见 [data-structures.md](./models/data-structures.md)，核心对象模型见 [object-model-core.md](./models/object-model-core.md)。

- 所有持久协作修改都是 signed Event
- 所有共享状态来自 **授权 Event 集合的归约结果**
- `space` 是复制、权限、schema 与 policy 边界
- `flow` 是统一协作对象；`kind="card"` 偏整理推进，`kind="room"` 偏讨论协作，二者可以在同一个 `flow_id` 上互转
- `space(kind=board)`、`space(kind=list)`、`message` 是协议一等标准对象
- `morph` 是开放对象载体，用于 schema / profile 扩展类型；facets 是 schema/profile 声明后的能力提示和查询标签，不单独定义授权、状态机、排序或 reducer 语义
- `relation` 是一等对象，用于表达包含、依赖、回复、引用、分配、提及等关系
- `event` 是协作事实和审计根
- `view` 是投影，不拥有核心数据
- `document` 等可作为 Morph 类型或扩展 profile，不自动授予能力
- `schema/policy` 是正式对象，不再只是引用占位符
- `invite/read_marker/notification` 补齐人类协作的加入、已读、提醒链路；notification 是派生投影，不是 canonical truth

### 5.3 看板与会话

> 会话模型细节见 [conversation-model.md](./models/conversation-model.md)，看板/层级见 [space-hierarchy.md](./models/space-hierarchy.md)。

- 看板由 `Space(kind=board) -> Space(kind=list) -> Flow(kind="card")` 表达；View 负责投影，不再把 Board 伪装成通用开放对象集合
- 会话由 `Flow(discussion branch) -> Message` 表达；discussion branch 是独立权限、成员、历史和 E2EE 边界
- `kind="card"` 默认走 `synthesis` branch，但可以开启 `discussion` branch
- `kind="room"` 默认走 `discussion` branch，但仍保留统一基础字段和可选 `synthesis` branch
- `cx.flow.convert` 只切换默认视角，不复制对象、不迁移消息历史
- `@user`、`@object` 在 UI 层可写成文本，在协议层必须落成结构化 Actor/Object 引用与 `mentions` Relation

### 5.4 同步

> 同步协议细节见 [operations-sync.md](./sync/operations-sync.md) 与 [client-sync.md](./sync/client-sync.md)。

- signed Event Envelope 是 actor 侧发布单元
- per-actor event chain 是审计和重放基础
- Principal Server / Sync Service 是受控同步与订阅层，不是唯一真相源
- 搜索、inbox、notification 和 View projection 默认由客户端或 SDK 本地派生，不是必需服务面
- 服务面要求最小可互操作 principal server / identity registry / events / sync / blob / authz 接口
- board/chat/thread/tree/graph 只是不同同步配置和 View 投影，不是不同协议
- Event 提交必须天然幂等
- 授权有效性也必须由同一 reducer 顺序收敛
- 撤回通过 redaction 收敛，不等于保证全球物理删除
- sync service 可以转发不解密的密文 payload；未加密私有正文不得提交给未委托第三方服务或受托搜索扩展

### 5.5 权限

> 授权模型见 [capabilities.md](./authz/capabilities.md)，状态解析见 [event-auth-state-resolution.md](./authz/event-auth-state-resolution.md)。

- 权限采用 capability 模型
- delegation 必须显式、可验证、可撤销
- agent 必须使用窄权限、短时效、可审计授权
- agent、未成年人、托管账号等 accountable Actor 必须能追溯 responsible / guardian / controller
- accountability 不等于 capability，权限仍必须由 grant 显式授予
- 高风险动作支持 approval constraint 与 proposal 模式
- 权限主体使用 DID 或 condition selector，handle 不作为权限主键
- 组织成员、角色、handle 绑定等动态条件由可验证 claim / attestation 表达
- DID Document 不作为跨组织身份画像；公开 persona DID 可以声明 handle，pairwise/private DID 默认不公开 handle，并通过最小披露 VC / presentation 证明属性
- 消息发送、编辑、撤回、Flow branch 管理、Flow 管理和 Space 排序都应有独立动作语义

## 6. 工程原则

协议实现应遵循以下工程原则：

- JSON/HTTP 友好性，但不把 REST 作为协议核心唯一绑定
- 签名与审计思路
- 去中心化服务发现
- 附件、同步、索引分层

协议不采用以下产品或架构假设：

- room-first 抽象
- “消息事件”统一承载所有业务对象
- 不依赖单一中心目录或单点控制入口
- UI 依赖聊天历史还原业务状态

## 7. 规范语言

本目录中的规范性表述使用 RFC 2119 风格关键字：

- `MUST`
- `SHOULD`
- `MAY`

本目录中的 `MUST`、`SHOULD`、`MAY` 均为规范性关键字。示例、说明性背景、迁移说明和明确标注为“非规范”的段落不改变强制要求。

各实现声明 Contrix 兼容性时 MUST 同时声明：

- 支持的 `protocol_version`，v1 使用 `1.0`。
- 支持的 conformance profile，例如 `cx.profile.full_client.v1`。
- 支持的 schema / reducer profile，例如 `cx.schema.event.v1` 与 `cx.profile.core_event_store.v1`。
- 支持的规模上限与分页边界；默认见 [conformance/scalability-constraints.md](./conformance/scalability-constraints.md)。
- 未支持的可选扩展，例如 WebRTC、Applet、Agent Runtime、Sovereign Deployment。

## 8. 当前覆盖范围

当前规范已经覆盖：

- DID、handle、组织主体、服务 DID 与渐进披露。
- Space（含 Board / List 形态）、Flow、Message、Morph、Relation、Event、View 和标准业务类型。
- 核心数据结构字段级类型、必填性、枚举和约束。
- Capability、delegation、claim 条件、policy server、moderation policy。
- Event-first 发布、Principal Server 同步、客户端本地查询/投影、Directory 发现、HTTP binding。
- MLS E2EE、设备验证、WebRTC 会议、Blob 与媒体。
- Applet、Agent protocol interop、Space hierarchy。
- Sovereign deployment 与 controlled collaboration Space。

新增能力应优先作为 profile、扩展章节或 schema registry 条目进入 [spec-map.md](./spec-map.md) 对应分组，避免继续堆进单个超大文件。

## 9. 一句话总结

Contrix 要解决的是：

- 去中心化协作对象
- 看板、Flow 讨论流、Flow synthesis 面、树、图谱与任务依赖的统一数据模型
- 稳定身份和授权
- AI agent 可写入、可检索、可审计的长期记忆

而不是再造一个改名后的聊天协议。


