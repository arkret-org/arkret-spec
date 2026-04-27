# Contrix Protocol

## 1. 项目定位

`contrix-spec` 是 **全新的去中心化协作协议** 草案。Contrix 明确采用：

- 以 **DID principal** 为身份根
- 以 **Space / Entity / Relation 协作图** 为数据根
- 以 **append-only repo + ops** 为审计根
- 以 **capability** 为权限根
- 以 **views/projections** 为人类展示根
- 以 **Event** 为协作事实根
- 以 **memory/run/message/task** 等标准 Entity 类型承载业务语义

它的目标不是“把聊天协议包装成看板”，而是定义一套能投影为看板、聊天/话题、表格、日历、树、图谱、甘特图和 agent 记忆的统一协作协议。

## 2. 设计目标

Contrix 第一阶段聚焦以下目标：

1. 稳定身份  
   所有主体使用 DID 作为稳定 ID，Handle 只是可迁移的人类可读入口。
2. 面向对象协作  
   协议根抽象固定为 Space、Actor、Entity、Relation、Event、View；board、task、message、memory、run 等是标准 Entity 类型。
3. 去中心化同步  
   真相基底是签名操作和 repo commit，而不是单一中心数据库。
4. 多交互模式  
   同一协议同时支持 kanban、list、table、calendar、gantt、chat、thread、forum、tree、graph 等模式。
5. 人类友好  
   数据必须天然能投影成看板、时间线、话题流、消息流、审阅队列。
6. AI 友好  
   协议天然支持 agent principal、delegation、run log、memory extraction。
7. 审计与恢复  
   编辑、撤回、授权变化、冲突收敛都必须可解释、可审计。

## 3. 非目标

当前阶段明确不把以下内容当作首版必需项：

- 让聊天消息重新变成唯一数据根
- 房间状态机作为全协议统一底座
- 全网共识链
- 强绑定某个 SaaS 产品 UI
- 把 embedding 或向量库当作协议真相源
- 一开始就做极度复杂的字段级/字节级 ACL

## 4. 规范地图

完整分组阅读入口见 [spec-map.md](./spec-map.md)。README 只保留顶层入口，避免随着扩展 profile 增多而变成长清单。

核心阅读路径：

1. [architecture.md](./architecture.md)：架构平面、部署拓扑和信任边界。
2. [glossary.md](./glossary.md)：术语边界，尤其是 Principal / Actor / Organization / Space / Repo / Relay。
3. [object-model-core.md](./object-model-core.md) 与 [object-model-standard.md](./object-model-standard.md)：核心对象和标准类型。
   字段级定义见 [data-structures.md](./data-structures.md)。
4. [identity-did.md](./identity-did.md)、[identity-handles.md](./identity-handles.md)、[progressive-disclosure.md](./progressive-disclosure.md)：身份、handle、隐私披露。
5. [capabilities.md](./capabilities.md) 与 [event-auth-state-resolution.md](./event-auth-state-resolution.md)：授权、membership、state resolution。
6. [operations-sync.md](./operations-sync.md)、[client-sync.md](./client-sync.md)、[service-surface.md](./service-surface.md)、[service-http-binding.md](./service-http-binding.md)：写入、同步、服务面和默认 HTTP binding。
7. 按场景阅读扩展：Applet、Agent、WebRTC、Directory、Social、Moderation、Federation、Sovereign Deployment。

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

- `principal_id = DID URI`
- Handle 与 DID 分离
- 默认 DID 方法为 `did:uuid`
- `did:uuid` 基于自定义 UUID v8：44 位毫秒时间戳 + 4 位哈希算法标识 + 74 位初始锚点公钥哈希片段
- DID 哈希填充与验证 MUST 使用大端序
- 普通密钥轮换 MUST NOT 改变 DID
- 当前控制密钥通过 `key_log` 从 `inception_key` 继承，不要求始终与 DID 哈希直接匹配
- DID 文档由多 `identity registry / witness / replica` 节点保存与复制，而不是单中心目录
- 解析模式参考 atprotocol 的 handle 双向验证，但更偏向协作与多服务发现
- 初版 SHOULD 支持 `did:web` 作为组织/服务互操作方法
- 对 `did:plc`、`did:web` 等外部 DID，采用 `method adapter + normalized principal view + sidecar` 兼容层；保留原始文档与历史，不强行改写成 `did:uuid`

### 5.2 数据

- 每个 principal 拥有自己的 repo
- 所有共享状态来自 **授权 Event / operation 集合的归约结果**
- `space` 是复制、权限、schema 与 policy 边界
- `entity` 是所有协作对象的统一载体
- `relation` 是一等对象，用于表达包含、依赖、回复、引用、分配、提及等关系
- `event` 是协作事实和审计根
- `view` 是投影，不拥有核心数据
- `board/task/message/channel/topic/memory/run` 是标准 Entity 类型，不是协议根
- `schema/policy` 是正式对象，不再只是引用占位符
- `invite/read_marker/notification` 补齐人类协作的加入、已读、提醒链路；notification 是派生投影，不是 canonical truth

### 5.3 看板与会话

- 看板是 `Entity + Relation + View` 的投影，常用语义类型为 `board/collection/task`
- 聊天是 `Entity + Relation + View` 的投影，常用语义类型为 `channel/topic/message`
- 话题模式是 `topic/message` Entity 与 `belongs_to/replies_to` Relation 的投影
- 同一个 `task`、`run`、`memory` 都可以通过 Relation 挂接默认讨论话题
- `@user`、`@object` 在 UI 层可写成文本，在协议层必须落成结构化 Entity/Actor 引用与 `mentions` Relation

### 5.4 同步

- repo commit 是 actor 侧发布单元
- operation log 是审计真相源
- relay 是传播与订阅层，不是唯一真相源
- index/appview 是查询与物化层，不是唯一真相源
- 服务面要求最小可互操作 identity registry / repo / relay / index / blob / authz 接口
- board/chat/topic/tree/graph 只是不同同步配置和 View 投影，不是不同协议
- commit/op 提交必须天然幂等
- 授权有效性也必须由同一 reducer 顺序收敛
- 撤回通过 redaction 收敛，不等于保证全球物理删除
- relay / index 可以转发不解密的密文 payload
- DID 里的哈希锚定 `inception_key`；普通密钥轮换不换 DID，只有不可恢复时才考虑例外性身份重建

### 5.5 权限

- 权限采用 capability 模型
- delegation 必须显式、可验证、可撤销
- agent 必须使用窄权限、短时效、可审计授权
- agent、未成年人、托管账号等 accountable Actor 必须能追溯 responsible / guardian / controller
- accountability 不等于 capability，权限仍必须由 grant 显式授予
- 高风险动作支持 approval constraint 与 proposal 模式
- 权限主体使用 DID 或 condition selector，handle 不作为权限主键
- 组织成员、角色、handle 绑定等动态条件由可验证 claim / attestation 表达
- DID Document 不作为跨组织身份画像；公开 persona DID 可以声明 handle，pairwise/private DID 默认不公开 handle，并通过最小披露 VC / presentation 证明属性
- 消息发送、编辑、撤回、频道管理、话题管理都应有独立动作语义

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

若某段明显以“建议”“草案”“后续可扩展”描述，则视为非强制设计方向。

## 8. 当前覆盖范围

当前规范已经覆盖：

- DID、handle、组织主体、服务 DID 与渐进披露。
- Space、Entity、Relation、Event、View 和标准业务类型。
- 核心数据结构字段级类型、必填性、枚举和约束。
- Capability、delegation、claim 条件、policy server、moderation policy。
- Repo-first 发布、Relay 传播、Index 查询、Directory 发现、HTTP binding。
- MLS E2EE、设备验证、WebRTC 会议、Blob 与媒体。
- Applet、Agent protocol interop、Social feed、Space hierarchy。
- Sovereign deployment 与 controlled collaboration Space。

后续新增能力应优先作为 profile 或独立章节进入 [spec-map.md](./spec-map.md) 对应分组，避免继续堆进单个超大文件。

## 9. 一句话总结

Contrix 要解决的是：

- 去中心化协作对象
- 看板、聊天/话题、树、图谱与任务依赖的统一数据模型
- 稳定身份和授权
- AI agent 可写入、可检索、可审计的长期记忆

而不是再造一个改名后的聊天协议。
