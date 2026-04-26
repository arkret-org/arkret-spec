# Contrix New Protocol

## 1. 项目定位

`contrix-spec-new` 是 **全新的去中心化协作协议** 草案。Contrix New 明确采用：

- 以 **DID principal** 为身份根
- 以 **Space / Entity / Relation 协作图** 为数据根
- 以 **append-only repo + ops** 为审计根
- 以 **capability** 为权限根
- 以 **views/projections** 为人类展示根
- 以 **Event** 为协作事实根
- 以 **memory/run/message/task** 等标准 Entity 类型承载业务语义

它的目标不是“把聊天协议包装成看板”，而是定义一套能投影为看板、聊天/话题、表格、日历、树、图谱、甘特图和 agent 记忆的统一协作协议。

## 2. 设计目标

Contrix New 第一阶段聚焦以下目标：

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

当前目录的文档按五十二个部分组织：

1. [gap-analysis.md](./gap-analysis.md)  
   列出当前协议进入稳定可落地阶段前仍需补齐的 schema、编码、联邦、媒体、设备、conformance 等能力。
2. [design-questions.md](./design-questions.md)  
   先把关键协议问题列出，再给出统一决策和收敛方案。
3. [architecture.md](./architecture.md)  
   定义协议的角色划分、拓扑、信任边界和核心架构平面。
4. [identity-did.md](./identity-did.md)  
   定义核心 DID 方法、UUID v8 生成、DID Document 解析与 Key Log。
5. [identity-handles.md](./identity-handles.md)  
   定义 Handle 解析、双向绑定与可验证凭证 Claim 证明。
6. [key-management.md](./key-management.md)  
   定义密钥与恢复模型、Accountable Actor 及受托代理。
7. [object-model-core.md](./object-model-core.md)  
   定义 Space、Actor、Entity、Relation、Event、View 等基础核心协议对象。
8. [object-model-standard.md](./object-model-standard.md)  
   定义 board/task/message/memory/run 等标准语义业务类型。
9. [conversation-model.md](./conversation-model.md)  
   定义 chat / topic / thread / mention / edit / recall / reaction 的统一交互模型。
10. [operations-sync.md](./operations-sync.md)  
   定义 repo commit、operation envelope、relay/index、snapshot、选择性同步、冲突收敛。
11. [capabilities.md](./capabilities.md)  
    定义 capability grant、delegation、revocation，以及消息/话题/看板相关动作权限。
12. [views.md](./views.md)  
    定义看板、列表、表格、聊天、线程、论坛、图谱、审阅队列等标准投影。
13. [agent-memory.md](./agent-memory.md)  
    定义如何把 Contrix 当作 AI agent 的长期记忆与协作外脑。
14. [service-surface.md](./service-surface.md)  
    定义最小 repo / relay / index / blob / authz 服务面，以及 Space bootstrap。
15. [api-conventions.md](./api-conventions.md)  
    定义默认 HTTP/JSON binding 的错误响应、幂等、分页、CORS、rate limit 与 feature discovery 约定。
16. [conformance-profiles.md](./conformance-profiles.md)  
    定义 minimal client、full client、repo、relay、index、identity registry、blob、E2EE、enterprise、agent runtime 等实现 profile。
17. [query-schema.md](./query-schema.md)  
    定义 Index / View / Inbox 查询语法。
18. [grant-constraint-schema.md](./grant-constraint-schema.md)  
    定义 capability grant constraint 正式语法。
19. [encoding.md](./encoding.md)  
    定义 canonical JSON、ID、hash、signature、cursor、HLC、rank 编码。
20. [snapshot-schema.md](./snapshot-schema.md)  
    定义 snapshot manifest、chunk、signature 与 encrypted envelope。
21. [service-api-schema.md](./service-api-schema.md)  
    定义 identity / repo / relay / index / blob / authz 核心 request / response。
22. [read-notification-schema.md](./read-notification-schema.md)  
    定义 read marker、receipt、notification、inbox 查询面。
23. [schema-registry.md](./schema-registry.md)  
    定义标准 object schema 与 event type 注册表。
24. [media-and-blob.md](./media-and-blob.md)  
    定义 blob metadata、thumbnail、authenticated download 与 encrypted attachment。
25. [federation-wire.md](./federation-wire.md)  
    定义 federation transaction、cross-domain join、backfill authorization 与 fork detection。
26. [applet-schema.md](./applet-schema.md)  
    定义 Applet registration、namespace、transaction、protocol metadata 与 bridge error schema。
27. [encryption-and-audit.md](./encryption-and-audit.md)  
    定义基于 MLS (RFC 9420) 的端到端加密标准与可审查的透明留痕机制。
28. [devices-and-auth.md](./devices-and-auth.md)  
    定义多设备管理、认证协议、密钥备份与单点登录。
29. [content-types.md](./content-types.md)  
    定义结构化的富文本与媒体消息类型系统（含 Polls 投票与 Mixins）。
30. [federation.md](./federation.md)  
    定义跨域联邦协议：节点间认证、Op 交换、跨域加入 Space、服务发现。
31. [push-notifications.md](./push-notifications.md)  
    定义推送规则引擎、推送网关接口与 E2EE 脱敏推送。
32. [moderation.md](./moderation.md)  
    定义内容举报、用户屏蔽、审核队列与服务器级 ACL。
33. [profiles-presence.md](./profiles-presence.md)  
    定义 Actor Profile 标准字段、在线状态广播、Typing 指示器与用户目录搜索。
34. [webrtc-signaling.md](./webrtc-signaling.md)  
    定义 WebRTC 音视频通话与会议，包括 P2P、SFU/MCU、TURN/STUN/ICE 发现、屏幕共享、录制转写、VoIP push 与 E2EE 边界。
35. [read-receipts.md](./read-receipts.md)  
    定义公开的 Read Receipt (已读回执) 与私有的 Read Marker (未读游标)。
36. [applet-integration.md](./applet-integration.md)  
    定义机器人、插件接入机制，融合 MSC3861 (OIDC) 与 MSC4326 (受托代理身份)。
37. [third-party-invites.md](./third-party-invites.md)  
    定义如何通过邮箱或手机号等 3PID 发起盲化邀请与认领流。
38. [client-preferences.md](./client-preferences.md)  
    定义用户私有的空间标签、UI 状态、自定义 Emoji 等 Account Data 存储。
39. [matrix-compat-gap.md](./matrix-compat-gap.md)  
    对比 `matrix-spec` 与 `matrix-spec-proposals`，列出 Contrix 必须吸收、改造或拒绝继承的协议能力。
40. [event-auth-state-resolution.md](./event-auth-state-resolution.md)  
    定义 Space version、事件授权、状态归约、membership、redaction、soft fail 与 Space upgrade。
41. [device-crypto-verification.md](./device-crypto-verification.md)  
    定义设备身份、cross-signing、to-device、验证流程、secret storage、key backup 与 Applet delegated device。
42. [sync-v2.md](./sync-v2.md)  
    定义客户端增量同步协议，包括 timeline、state_after、account_data、to_device、device_lists 与 E2EE 同步要求。
43. [policy-server.md](./policy-server.md)  
    定义策略服务声明、预检查请求、签名决策、失败模式、联邦处理与隐私边界。
44. [account-lifecycle.md](./account-lifecycle.md)  
    定义服务账户、DID principal、device session、注销、锁定、暂停、软登出、擦除与 session 撤销。
45. [glossary.md](./glossary.md)  
    集中定义协议术语，覆盖核心对象、身份授权、同步联邦、设备加密、Applet、媒体通知与账户生命周期。
46. [space-hierarchy.md](./space-hierarchy.md)  
    定义 Space 父子层级、双向确认、显式继承、层级查询、循环处理，以及权限/成员/历史/加密默认不级联的规则。
47. [agent-protocol-interop.md](./agent-protocol-interop.md)  
    定义 AI agent 在 Contrix 任务中升级/切换到 A2A、ACP legacy 或其他外部 agent protocol 的发现、授权、执行、状态回流和审计规则。
48. [transport-bindings.md](./transport-bindings.md)  
    定义协议核心与 HTTP/REST、gRPC、WebSocket、SSE、message queue、libp2p 等 transport binding 的关系，明确 REST 只是默认互操作 binding。
49. [tsp-integration.md](./tsp-integration.md)  
    定义 Trust Spanning Protocol (TSP) 与 Contrix 身份、联邦、服务间通信、pairwise 控制消息的可选结合方式，并说明 TSP 与 MLS 的边界。
50. [progressive-disclosure.md](./progressive-disclosure.md)  
    定义隐私信息渐进披露的端到端实现方案，包括 presentation request、disclosure policy、proof profile、私有存储、transport fallback 和安全要求。
51. [discovery-directory.md](./discovery-directory.md)  
    定义 Space、Organization、Actor、Applet 的可发现性策略、目录服务、公开/受限/不可列举资源、精确解析和防枚举要求。
52. [social-graph.md](./social-graph.md)  
    定义个人/组织社交发布、公开 feed、朋友圈式受众、follow/contact/circle 关系、Audience Policy 和社交层审核边界。

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
- `Space/Actor/Entity/Relation/Event/View` 的统一抽象
- board/chat/topic/tree/graph 的统一投影方式
- `@mention` 的结构化语义
- edit / recall / redaction 语义
- board/chat/topic 的同步模式
- 对不同对象类型的冲突收敛规则
- 最小服务接口与 Space bootstrap
- `schema/policy/invite/read_marker/notification` 缺失对象
- 幂等提交、授权时序与密文转发语义

## 9. 下一轮优先级

在当前框架稳定后，建议优先继续细化：

1. 测试向量  
   为 canonical JSON、event hash、signature、state resolution、redaction、sync token 编写跨实现测试向量。
2. OpenAPI 合并  
   将 `service-api-schema.md`、`sync-v2.md`、`device-crypto-verification.md`、`policy-server.md` 的默认 HTTP binding 落成统一 OpenAPI，同时保留 canonical operation 到其他 transport 的映射。
3. Conformance suite  
   为 repo、relay、index、E2EE client、Applet、policy server 定义自动化互操作测试。
4. Space version v2 候选  
   在 v1 实现反馈后冻结下一版 auth/state/redaction 变更，不在同一 Space version 中破坏兼容性。

## 10. 一句话总结

Contrix New 要解决的是：

- 去中心化协作对象
- 看板、聊天/话题、树、图谱与任务依赖的统一数据模型
- 稳定身份和授权
- AI agent 可写入、可检索、可审计的长期记忆

而不是再造一个改名后的聊天协议。
