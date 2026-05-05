# 术语表

## 1. 目标

本文集中定义 Contrix 规范中的核心术语。若其他文档使用同一术语，除非所在章节另有说明，以下定义优先于扩展实现约定。

本文中的英文术语保留为规范关键字；中文解释用于阅读，不能替代字段名、对象名或事件名。

## 2. 核心术语

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 去中心化协作对象协议族，定义 identity、写入、同步、授权、显示与审计规则。 |
| Principal | 主体 | 协议中的稳定行为者身份；通常由 DID 标识，包含个人主体、组织、agent、Applet 等。 |
| Actor | 主体视图 | 在 Space 中执行动作、产生 Event、持有 profile 与 membership 的可见身份表示。 |
| Organization | 组织 | 可治理主体的一类 Principal，通常由组织 DID 标识。 |
| Organization Governance | 组织治理 | 组织成员资格、控制策略、密钥、恢复与授权委派规则。 |
| Handle | 人类可读标识 | 可迁移的人类可读入口或别名；包括 DNS handle 和外部体系 alias，不可作为协议主体或授权主键。 |
| DNS Handle | DNS 风格标识 | `alice.example.com` 这类可通过 DNS / HTTPS well-known 双向验证到 DID 的 Handle 子类。 |
| Connection Identifier | 连接标识 | 邮箱、手机号、通讯录用户名、外部账号 ID 等用于发现、邀请或 consent 的标识；默认关系私有，不等于 Handle 或 DID。 |
| Administrative Identifier | 管理标识 | 组织账号、计费账号、员工编号等组织本地管理标识；不能作为协议主体。 |
| Display Name | 显示名 | UI 展示用名称，可变且不可用于 ACL、grant、审计归因或发送者验证。 |
| Space | 协作边界 | 授权、policy、membership、history visibility、同步与真相归约的作用域。 |
| Official Space | 官方空间 | 由组织或 policy 明确确认的 Space，不等于单纯“有官方 handle 的 Space”。 |
| Space Hierarchy | Space 层级 | Space 之间的 parent/child 组织关系，用于导航与受控继承；不默认级联权限或历史。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、邀请、组织页或精确链接发现。 |
| Flow | 协作主对象 | Space 内承载协作议题、任务、正式表达与讨论分支的标准对象。 |
| Flow primary branch | Flow 默认入口 | 按 branch primary 解析规则得到的默认 branch；显式 `is_primary=true` 优先，未显式时标准 `synthesis` 优先。 |
| Room | 讨论分支视图 | Flow 的 discussion branch 或以 discussion 为默认入口的会话视图简称。 |
| synthesis branch | 正式表达分支 | Flow 的“synthesis”分支，承载正式状态、结构化字段与决策正文。 |
| discussion branch | 讨论分支 | Flow 的“discussion”分支，承载消息与讨论时间线；成员、历史可见性和 E2EE 默认继承 Flow / Space access，显式 override 时才 branch-scoped。 |
| Space (kind=board) | 看板空间 | `type=space`，用于组织一组 Space (kind=list) 的工作容器空间。 |
| Space (kind=list) | 列/泳道空间 | `type=space`，表示一列或泳道容器，可挂到 Space (kind=board) 并承载 Flow 成员。 |
| Message | 消息对象 | 发生在 Flow discussion 分支中的即时沟通与补充记录。 |
| Morph | 开放对象 | 标准对象扩展框架，承载非固定业务类型的可声明对象。 |
| Facet | 能力标签 | Morph/Profile 的能力提示（如 container/schedulable/renderable）。 |
| Relation | 关系边 | 对象间有向关系定义，如 `contains`、`mentions`、`depends_on`。 |
| Event | 协议事件 | 协议传播和验证的基础事实单元（Envelope 的内容承载形式）。 |
| Event Envelope | 事件外壳 | `event_id`、`actor_id`、`kind`、`payload`、`proofs` 等字段的签名封包。 |
| Event Store | 事件存储 | 保存 Event Envelope 的服务能力，不是协议真相源本身。 |
| Snapshot | 快照 | 恢复/同步起点对象，包含某时刻 Materialized State 与 frontier。 |
| HLC | 混合逻辑时钟 | `HLC` 为 `clock` 排序标签，形如 `<unix_ms_hex>-<logical_hex>-<node_id_hash>`。 |
| Cursor | 同步游标 | 指定 frontier 的 `scope:space|actor|query` 编码，用于增量同步与重放。 |
| Canonical JSON | 规范 JSON | 确定性 JSON 序列化格式，所有签名/哈希/对账输入必须使用；要求 UTF-8、key 排序、无空白、唯一 number 表示。 |
| View | 投影定义 | 查询 + kind + renderer + config 的共享可签名对象，定义“怎么看”。 |
| View.kind | 投影族类 | `collection / timeline / graph / document / composite`。 |
| Capability | 能力 | 授权语义与对象的绑定关系，授予 subject 执行特定 action。 |
| Capability Grant | 能力授权对象 | `capability` 标准对象；记录谁在什么条件下可执行何动作。 |
| Policy | 策略 | 运行期约束对象，用于授权、密钥、留存、治理与安全边界。 |
| Invite | 邀请 | 邀请主体加入 Space 或授予特定能力的标准对象/事件 payload。 |
| Principal Server | 主体服务 | 主体控制或委托入口服务，承载 events / sync / discovery 等核心 API。 |
| Sync Service | 同步服务 | 公开/订阅事件与 frontier 的受控同步能力，通常由 Principal Server 提供。 |
| Event Store Service | 事件存储服务 | 与 Sync Service 关联的持久化与检索服务角色。 |
| Blob Store | 二进制对象存储 | 附件、媒体、文件对象的存储与引用服务。 |
| Directory Server | 目录服务 | 提供可发现的 Space、组织、actor、Applet 信息。 |
| Identity Resolution Infrastructure | 身份解析基础设施 | DID 文档、method resolver、密钥材料与验证链路。 |
| Redaction | 清理/隐私裁剪 | 合法授权下对已发布事实做最小化可见性处理。 |
| Erasure | 物理擦除 | 在某个存储边界内对原始 payload、blob、派生内容的不可恢复删除；不同于 Redaction，它不保留正文。 |
| Auth Weight | 授权权重 | **历史概念**（v1 之前的 lattice state-resolution 派生表）。v1 已用 quarantine-on-concurrent-fork 替代；详见 `authz/event-auth-state-resolution.md` §9.3。新实现 MUST NOT 依赖 `auth_weight`。 |
| Causal Depth | 因果深度 | 事件在已知 DAG / prev_refs 中的深度值，用于 deterministic timeline 排序。 |
| Soft Fail | 软失败 | 事件格式和签名有效但缺少上下文或暂时无法授权的中间状态；可在上下文补齐后重新评估。 |
| Quarantine | 隔离 | 基础授权可通过但被策略标记为高风险的事件状态；不自动展示，需管理员审查。 |
| Accepted | 已接受 | 事件通过全部校验后的最终状态；可推进 frontier 和 reducer。 |
| Rejected | 已拒绝 | 事件在格式、签名、schema 或授权上确定失败；不得进入 reducer。 |
| State Resolution | 状态收敛 | 多分支对同一 `(kind, state_key)` 给出不同 accepted state event 时，按确定性算法选择唯一 winner。 |
| Reducer | 归约器 | 确定性纯函数，将 accepted Event 集合归约为当前态、state hash 和 conflict records。 |
| Materialized State | 物化状态 | Reducer 输出的当前态对象，如 Flow、Relation、View。 |
| Frontier | 前沿 | Actor 或 Space 已接受事件的最远同步边界，用 event_id / HLC / actor_seq 表示。 |
| Inception Key | 起源密钥 | DID 创建时的初始控制密钥，锚定在 DID 的 method history 中。 |
| Plaintext Visible Service | 明文可见服务 | Space policy 显式声明可接收非加密私有内容或可逆派生摘要的服务。 |
| History Visibility | 历史可见性 | 控制加入 Space 后能看到多少历史事件的范围规则。 |
| Join Rule | 加入规则 | 控制 Actor 如何加入 Space 的策略（public、invite、knock、restricted 等）。 |
| MLS Bound State | MLS 绑定状态 | E2EE Space 中由 MLS application state root 覆盖的 membership、policy 等关键状态。 |
