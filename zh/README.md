# Contrix New Protocol

## 1. 项目定位

`contrix-spec-new` 是 **全新的去中心化协作协议** 草案，不是旧 `contrix-spec` 的小修小补版本。

旧 `contrix-spec` 本质上仍然沿用了 Matrix 式的“房间 + 事件 + 消息”中心抽象；  
新的 Contrix 则明确转向：

- 以 **DID principal** 为身份根
- 以 **workspace/object graph** 为数据根
- 以 **append-only repo + ops** 为审计根
- 以 **capability** 为权限根
- 以 **views/projections** 为人类展示根
- 以 **memory + run** 为 AI agent 协作与记忆根
- 以 **channel/topic/message** 为标准会话交互根

它的目标不是“把聊天协议包装成看板”，而是直接定义一个既能做看板，也能做聊天/话题，还能做 agent 记忆的统一协作协议。

## 2. 设计目标

Contrix New 第一阶段聚焦以下目标：

1. 稳定身份  
   所有主体使用 DID 作为稳定 ID，Handle 只是可迁移的人类可读入口。
2. 面向对象协作  
   协议直接表达 workspace、board、item、topic、message、view、memory、run 等协作对象。
3. 去中心化同步  
   真相基底是签名操作和 repo commit，而不是单一中心数据库。
4. 多交互模式  
   同一协议同时支持 kanban、list、table、chat、thread、forum、graph 等模式。
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

当前目录的文档按十个部分组织：

1. [design-questions.md](./design-questions.md)  
   先把关键协议问题列出，再给出统一决策和收敛方案。
2. [architecture.md](./architecture.md)  
   定义协议的角色划分、拓扑、信任边界，以及与旧协议的核心分歧。
3. [identity.md](./identity.md)  
   定义 DID、Handle、服务发现、设备与 agent 委托、恢复与迁移。
4. [object-model.md](./object-model.md)  
   定义 workspace、board、item、channel、topic、message、memory、run 等核心对象。
5. [conversation-model.md](./conversation-model.md)  
   定义 chat / topic / thread / mention / edit / recall / reaction 的统一交互模型。
6. [operations-sync.md](./operations-sync.md)  
   定义 repo commit、operation envelope、relay/index、snapshot、选择性同步、冲突收敛。
7. [capabilities.md](./capabilities.md)  
   定义 capability grant、delegation、revocation，以及消息/话题/看板相关动作权限。
8. [views.md](./views.md)  
   定义看板、列表、表格、聊天、线程、论坛、图谱、审阅队列等标准投影。
9. [agent-memory.md](./agent-memory.md)  
   定义如何把 Contrix 当作 AI agent 的长期记忆与协作外脑。
10. [service-surface.md](./service-surface.md)  
   定义最小 repo / relay / index / blob / authz 服务面，以及 workspace bootstrap。

当前轮的任务清单与后续 backlog 记录在 [_tasks.md](./_tasks.md)。

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

### 5.2 数据

- 每个 principal 拥有自己的 repo
- 所有共享状态来自 **授权操作集合的归约结果**
- `workspace` 是复制与权限边界
- `item` 是主业务对象，不等于 UI card
- `board` 是工作上下文，`view` 是投影
- `channel/topic/message` 是会话对象，不是协议根
- `memory` 是持久知识对象，不等于 embedding chunk
- `run` 是 agent 或自动化执行轨迹对象
- `schema/policy` 是正式对象，不再只是引用占位符
- `invite/read_marker/notification` 补齐人类协作的加入、已读、提醒链路

### 5.3 看板与会话

- 看板是 `item + collection + board + view` 的投影
- 聊天是 `channel + topic + message` 的投影
- 话题模式是 `topic + message` 的投影
- 同一个 `item`、`run`、`memory` 都可以挂接默认讨论话题
- `@user`、`@object` 在 UI 层可写成文本，在协议层必须落成结构化引用

### 5.4 同步

- repo commit 是 actor 侧发布单元
- operation log 是审计真相源
- relay 是传播与订阅层，不是唯一真相源
- index/appview 是查询与物化层，不是唯一真相源
- 服务面要求最小可互操作 identity registry / repo / relay / index / blob / authz 接口
- board/chat/topic 只是不同同步配置，不是不同协议
- commit/op 提交必须天然幂等
- 授权有效性也必须由同一 reducer 顺序收敛
- 撤回通过 redaction 收敛，不等于保证全球物理删除
- relay / index 可以转发不解密的密文 payload
- DID 里的哈希锚定 `inception_key`；普通密钥轮换不换 DID，只有不可恢复时才考虑例外性身份重建

### 5.5 权限

- 权限采用 capability 模型
- delegation 必须显式、可验证、可撤销
- agent 必须使用窄权限、短时效、可审计授权
- 消息发送、编辑、撤回、频道管理、话题管理都应有独立动作语义

## 6. 与旧 contrix-spec 的关系

旧规范可作为经验参考，但新规范默认 **不追求数据模型兼容**。

可以继承的经验：

- JSON/HTTP 友好性
- 签名与审计思路
- 去中心化服务发现
- 附件、同步、索引分层

应该抛弃或弱化的旧假设：

- room-first 抽象
- “消息事件”统一承载所有业务对象
- homeserver 作为唯一中心入口
- UI 依赖聊天历史还原业务状态

## 7. 规范语言

本目录中的规范性表述使用 RFC 2119 风格关键字：

- `MUST`
- `SHOULD`
- `MAY`

若某段明显以“建议”“草案”“后续可扩展”描述，则视为非强制设计方向。

## 8. 当前轮产出

本轮将协议从“方向性草图”推进到“问题清单 + 统一交互模型 + 自洽框架”，重点补齐：

- 关键设计问题清单
- board/chat/topic 的统一抽象
- `@mention` 的结构化语义
- edit / recall / redaction 语义
- board/chat/topic 的同步模式
- 对不同对象类型的冲突收敛规则
- 最小服务接口与 workspace bootstrap
- `schema/policy/invite/read_marker/notification` 缺失对象
- 幂等提交、授权时序与密文转发语义

## 9. 下一轮优先级

在当前框架稳定后，建议优先继续细化：

1. 线级协议  
   每个服务接口的正式 request/response schema。
2. 模式定义  
   query JSON schema、grant constraint schema、snapshot chunk schema。
3. 编码规则  
   cursor、HLC、rank、commit hash、签名封装格式。
4. 互操作性  
   最小兼容实现、测试向量、conformance profile、加密 envelope。

## 10. 一句话总结

Contrix New 要解决的是：

- 去中心化协作对象
- 看板与聊天/话题的统一数据模型
- 稳定身份和授权
- AI agent 可写入、可检索、可审计的长期记忆

而不是再造一个改名后的聊天协议。
