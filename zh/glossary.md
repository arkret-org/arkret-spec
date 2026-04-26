# 术语表

## 1. 目标

本文集中定义 Contrix New 规范中的核心术语。若其他文档使用同一术语，除非所在章节明确覆盖，否则应以本文定义为准。

本文中的英文术语保留为规范关键字；中文解释用于帮助阅读，不改变字段名、事件名或协议对象名。

## 2. 核心对象

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 面向去中心化协作对象、会话、任务、看板、知识记忆和 agent 协作的协议族。 |
| Principal | 主体 | 协议中的稳定身份主体，通常由 DID 表示。人、组织、agent、Applet 都可以是 principal。 |
| Actor | 行为者 | 在 Space 中执行动作、产生 Event、拥有 profile 和 membership 的主体视图。Actor 通常映射到 principal，但可包含 ghost actor、bot actor 或 accountable actor。 |
| Space | 协作空间 | 复制、授权、schema、policy、membership 和 history visibility 的边界。它替代 Matrix room 作为 Contrix 的协作边界，但不是唯一数据模型。 |
| Space Hierarchy | 空间层级 | Space 之间的 parent/child 组织关系，用于导航、发现和受控继承；不默认级联权限、成员、历史或加密。 |
| Entity | 实体 | 所有协作对象的统一载体，例如 task、message、topic、board、memory、run、file、profile。 |
| Relation | 关系 | Entity / Actor / Space 之间的一等连接对象，用于表达包含、回复、依赖、引用、分配、提及、父子、附件等语义。 |
| Event | 事件 | 协作事实和审计根。Event 由 actor/device/service 签名，进入 repo、relay、index 和 reducer。 |
| State Event | 状态事件 | 带 `state_key` 的 Event，当前状态由 `(type, state_key)` 归约得到，例如 membership、policy、schema、view definition。 |
| View | 视图 | 对 Entity / Relation / Event 的投影定义，例如 kanban、table、calendar、chat、thread、graph、review queue。View 不拥有真相数据。 |
| Projection | 投影 | Index 或客户端根据 View / query / reducer 从 canonical Event 集合派生出的展示或查询结果。 |
| Schema | 模式 | 对 Entity、Relation、Event、View 或 service payload 的结构约束。 |
| Policy | 策略 | Space 或服务级治理规则，例如加入规则、历史可见性、媒体规则、审核策略、policy server 配置。 |

## 3. 标准语义类型

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Board | 看板 | 由 Entity、Relation 和 kanban View 投影出的工作管理界面，不是协议根对象。 |
| Task | 任务 | 标准 Entity 类型，用于表达待办、状态、负责人、截止时间、依赖和讨论关系。 |
| Channel | 频道 | 标准 Entity 类型，用于承载长期消息流或话题集合。 |
| Topic | 话题 | 标准 Entity 类型，用于论坛式或线程式讨论，可挂接到 task、memory、run 等对象。 |
| Message | 消息 | 标准 Entity 类型，用于会话内容。消息仍是 Entity，不是协议唯一事实根。 |
| Memory | 记忆 | 标准 Entity 类型，用于 agent 或人类确认的长期知识、事实、偏好或上下文。 |
| Run | 运行记录 | 标准 Entity 类型，用于记录 agent、自动化或工具执行过程。 |
| Agent Protocol Session | Agent 协议会话 | Contrix 任务显式切换到 A2A、ACP legacy 或其他外部 agent protocol 执行时登记的受控会话。 |
| Mention | 提及 | 对 Actor 或 Entity 的结构化引用，协议层必须落成 ref / relation，不依赖正文扫描。 |
| Reaction | 反应 | 对目标 Entity/Event 的轻量语义反馈，通常通过 Relation 或标准 reaction event 表达。 |

## 4. 身份与可发现性

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| DID | 去中心化标识符 | Principal 的稳定标识。Contrix 默认 DID 方法为 `did:uuid`，同时支持 `did:web` 等外部方法适配。 |
| DID Document | DID 文档 | DID 解析得到的控制密钥、服务端点、验证方法等文档。外部 DID 文档保留原始字段，进入 Contrix normalized view 前映射为 snake_case。 |
| DID Method | DID 方法 | DID 的解析与更新规则，例如 `did:uuid`、`did:web`、`did:plc`。 |
| DID Key Log | DID 密钥日志 | 记录 DID 控制密钥演化、轮换、恢复和见证的追加式日志。 |
| Handle | 人类可读标识 | 例如 `alice.example.com` 或 `alice@service`。Handle 用于发现和显示，不作为权限主键。 |
| Claim | 声明 | 对某个主体属性、绑定或资格的可验证声明，例如 handle binding、组织成员资格。 |
| Attestation | 证明/背书 | 由可信 issuer 对 Claim 签名背书。 |
| VC | 可验证凭证 | Verifiable Credential，用于最小披露地证明属性、成员资格或 handle 绑定。 |
| Presentation | 凭证呈示 | 主体向验证方出示一个或多个 VC 的证明，可包含选择性披露或零知识证明。 |
| Pairwise DID | 成对 DID | 面向特定关系或组织使用的私有 DID，用于降低跨域关联风险。 |
| Public Persona DID | 公开人格 DID | 主动公开用于发现、社交或品牌展示的 DID。 |
| Normalized Principal View | 规范化主体视图 | 将不同 DID 方法、外部文档和 sidecar 数据映射为 Contrix 内部可验证主体视图。 |

## 5. 授权与责任

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Capability | 能力授权 | 明确授予某主体在某范围执行某动作的可验证授权。Contrix 使用 capability 替代 power level 作为核心权限模型。 |
| Grant | 授权记录 | 表达 capability 的签名对象，包含 issuer、subject、actions、scope、constraints、expiry 等。 |
| Delegation | 委托 | 一个主体把有限 capability 委托给另一个主体、设备、agent 或 Applet。 |
| Revocation | 撤销 | 使 grant、device、session 或 delegation 在其因果后继中失效的事件或状态。 |
| Constraint | 约束 | capability 的使用条件，例如时间、Space、Entity、字段、设备、速率、审批、Applet namespace。 |
| Condition Selector | 条件选择器 | 以可验证属性匹配主体的授权 subject，例如“某组织当前成员”。 |
| Accountable Actor | 可追责行为者 | 有直接身份但需要 responsible、guardian 或 controller 的 Actor，例如 agent、未成年人、托管账号。 |
| Responsible Party | 责任主体 | 对 accountable actor 行为承担责任的 principal。 |
| Approval | 审批 | 高风险动作的授权条件，可在提交前或 proposal 后发生。 |
| Proposal | 提案 | 受限主体不能直接提交高风险 Event 时创建的待审批意图。 |
| Authz | 授权判定 | Authorization 的缩写，指 capability、policy、membership、device trust 等规则的综合判定。 |

## 6. Repo、同步与状态

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Repo | 仓库 | Principal 或 Space 发布 signed commit / operation 的追加式存储。Repo 是审计真相源之一。 |
| Commit | 提交 | Actor 侧发布单元，包含一个或多个 operation/event 引用和签名。 |
| Operation / Op | 操作 | 对协作图的原子变更意图或事实，通常封装为 Event 或被 Event 引用。 |
| Operation Log | 操作日志 | 追加式审计记录，用于归约、同步、回放和冲突分析。 |
| Reducer | 归约器 | 将 accepted Event / Op 集合归约为当前状态和 projection 的确定性规则。 |
| State Resolution | 状态解析 | 对同一 state key 的并发冲突进行确定性合并的算法。 |
| Auth Refs | 授权引用 | 当前 Event 授权所需的最小状态事件集合。 |
| Prev Refs | 前序引用 | 当前 Event 的因果前序引用。 |
| Causal Frontier | 因果前沿 | 一个节点当前已知的最新因果边界，用于授权缓存、同步和冲突判断。 |
| Snapshot | 快照 | 某个状态或 projection 的签名物化结果，可用于快速恢复或迁移。 |
| Backfill | 回填 | 从远端拉取缺失历史 Event / state / operation 的过程。 |
| Fork | 分叉 | 同一主体、Space 或 state key 出现多个并发或冲突历史分支。 |
| Equivocation | 双签/作恶分叉 | 同一主体对同一逻辑位置发布不可兼容的多个签名事实。 |
| Redaction | 撤回/裁剪 | 通过 `cx.redaction` 清除目标事件内容字段并保留最小审计字段的机制，不等于全球物理删除。 |
| Tombstone | 墓碑 | 表示对象、Space 或旧版本被替代/废止的状态。 |
| Lazy Link | 惰性链接 | 跨 Space 查询或层级展开时返回的最小引用，避免无权限展开目标 Space 内容。 |
| Soft Fail | 软失败 | 事件格式和签名有效，但缺上下文或暂时无法授权，不进入用户可见状态，可后续重评估。 |
| Reject | 拒绝 | 事件确定不合法，不得进入 reducer。 |
| Quarantine | 隔离 | 事件基础授权可过，但被策略或风控标记，需要审查后展示或处理。 |

## 7. 服务角色

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Identity Registry | 身份注册表 | 保存、复制和见证 DID 文档、DID key log、handle binding 的服务角色。 |
| Witness | 见证节点 | 对 DID log、key rotation、重要状态变更进行外部见证的服务或主体。 |
| Relay | 中继 | 聚合、去重、转发、订阅与推送 Event / Op 的传播层，不是真相源。 |
| Index | 索引 | 将授权事件物化为查询结果、当前态、搜索结果和视图投影的派生层。 |
| AppView | 应用视图服务 | 面向特定产品或 UI 的 Index / projection 服务。 |
| Blob Store | 大对象存储 | 存储附件、媒体、snapshot chunk 或大对象的服务，地址可多源，校验基于内容哈希。 |
| Authz Service | 授权服务 | 预检查、解释或缓存 capability / policy 判定的服务，不应替代可验证协议规则。 |
| Policy Server | 策略服务 | 对邀请、加入、消息、媒体、Applet、联邦等行为给出签名风险决策的服务。 |
| Push Gateway | 推送网关 | 将脱敏通知投递到移动或桌面平台推送系统的服务。 |

## 8. 联邦与互操作

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Federation | 联邦 | 不同域、组织或服务节点之间交换 Event、Op、state、backfill、join/invite 的协议层。 |
| Service DID | 服务 DID | Relay、Index、Applet、Policy Server 等服务使用的 DID。 |
| Federation Transaction | 联邦交易 | 跨服务批量交换 PDU/EDU 等消息的传输单元；Contrix 中对应 signed transaction envelope。 |
| Cross-domain Join | 跨域加入 | Actor 通过一个服务加入另一个服务或组织托管的 Space。 |
| Server ACL | 服务级访问控制 | 对联邦服务、域、IP、service DID 或 relay 的接入限制。 |
| Applet | 小应用/集成服务 | 类似 Matrix appservice 的扩展机制，用于机器人、桥接、外部 SaaS 集成和自动化。 |
| Applet Registration | Applet 注册 | 描述 Applet service DID、endpoint、namespace、protocol、认证方式和能力范围的签名声明。 |
| Namespace | 命名空间 | Applet 声明自己负责处理的 actor、space、handle 或外部 protocol 标识范围。Namespace 不等于 capability。 |
| Bot Actor | 机器人行为者 | Applet 的可见自动化 Actor，可加入 Space、被 mention、发送消息或执行任务。 |
| Ghost Actor | 幽灵行为者 | 外部网络用户在 Contrix 中的镜像 Actor，必须可审计且不能静默冒充原生 human actor。 |
| Portal Space | 门户空间 | 外部系统 location 在 Contrix 中的镜像 Space，例如 Slack channel、GitHub issue discussion。 |
| Bridge | 桥接 | 在 Contrix 与外部系统之间转换 identity、message、event、file、membership 和 permission 的机制。 |
| Protocol Adapter | 协议适配器 | 将 Contrix task/session 映射到 A2A、ACP legacy、MCP bridge 或企业私有 agent API 的组件。 |

## 9. 设备、会话与加密

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Device | 设备 | Principal 下具有独立密钥、session、trust state 和 sync token 的客户端实例。 |
| Device ID | 设备标识 | Principal 范围内稳定标识某个设备的 ID。 |
| Device Record | 设备记录 | 设备公钥、算法、显示名、创建时间、撤销状态和签名链。 |
| Device List | 设备列表 | 某 principal 当前有效和已撤销设备的可同步状态。 |
| Session | 会话 | Access token / refresh token / device token 代表的登录状态。 |
| Soft Logout | 软登出 | token 失效但本地 E2EE 密钥不应被强制删除的状态。 |
| Cross-signing | 交叉签名 | Principal 使用 self-signing/user-signing key 建立设备和其他主体的信任链。 |
| Self-signing Key | 自签设备密钥 | 用于签名本 principal 设备的账户级密钥。 |
| User-signing Key | 用户签名密钥 | 用于签名其他 principal identity key 的密钥，表达人工验证后的信任。 |
| To-device Message | 设备间消息 | 发给具体 principal/device 的非 Space 持久消息，用于验证、secret sharing、key request 等。 |
| One-time Key | 一次性密钥 | 建立加密会话时被原子消费的预密钥。 |
| Fallback Key | 后备密钥 | one-time key 不足时使用的可重复预密钥，应尽快轮换。 |
| Secret Storage | 秘密存储 | 服务端保存密文、客户端持有解锁材料的密钥备份机制。 |
| Key Backup | 密钥备份 | 保存加密后的历史群组/session 密钥材料，用于设备恢复。 |
| MLS | Messaging Layer Security | RFC 9420 群组端到端加密协议，Contrix E2EE Space 的推荐加密基础。 |
| MLS Epoch | MLS 轮次 | MLS group state 的版本。成员变更、密钥更新会推进 epoch。 |
| KeyPackage | MLS 加入材料 | 设备发布的 MLS 加入包，必须绑定 DID 和 device identity。 |
| E2EE | 端到端加密 | 服务端和 relay/index 默认无法解密内容的加密模式。 |
| HPKE | 混合公钥加密 | 用于设备间加密、secret wrapping 或引导加密会话的机制。 |

## 10. 媒体、通知与临时事件

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Blob | 大对象 | 附件、图片、视频、snapshot chunk 等二进制或大体积内容。 |
| Blob Metadata | 大对象元数据 | Blob 的 hash、MIME、大小、加密 envelope、缩略图、扫描状态和 retention 信息。 |
| Authenticated Media | 认证媒体 | 下载需要授权或签名 URL 的媒体访问模式。 |
| Thumbnail | 缩略图 | Blob 派生物，必须可追溯到原 blob 和生成参数。 |
| Read Receipt | 已读回执 | 可公开或按 Space policy 可见的阅读确认。 |
| Read Marker | 已读游标 | Principal/device 私有的阅读位置或未读状态，不必公开给其他成员。 |
| Notification | 通知 | 由事件、mention、规则和 read marker 派生出的提醒，不是 canonical truth。 |
| Push Rule | 推送规则 | 用户私有或 Space 级的通知匹配规则。 |
| Presence | 在线状态 | Actor/device 当前在线、离开、忙碌等短暂状态。 |
| Typing | 输入中 | 短暂的正在输入指示。 |
| Ephemeral Event | 临时事件 | 不进入长期 repo 审计图的短期事件，例如 typing、presence、WebRTC ICE candidate。 |
| Durable Event | 持久事件 | 进入 repo / reducer / audit 的长期事件。 |

## 11. API、编码与一致性

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Canonical JSON | 规范 JSON | 用于 hash 和 signature 的确定性 JSON 编码规则。 |
| Multihash | 多哈希 | 携带哈希算法标识的内容哈希编码。 |
| Signature | 签名 | Actor、device 或 service 对 canonical payload 的密码学证明。 |
| Detached Signature | 分离签名 | 签名与 payload 分开传输或存储的签名形式。 |
| Cursor | 游标 | 分页或同步进度 token，不应被客户端解析内部结构。 |
| HLC | Hybrid Logical Clock | 混合逻辑时钟，用于并发排序、游标和冲突 tie-break。 |
| Rank | 排序秩 | 用于看板列、列表、树节点等可重排对象的稳定排序值。 |
| Idempotency Key | 幂等键 | 客户端重试提交时用于去重的事务标识。 |
| Sync Token | 同步令牌 | 客户端增量同步的 opaque resume token。 |
| State After | 后置状态 | sync timeline 应用完毕后的状态 delta，供客户端正确渲染当前 UI。 |
| Feature Discovery | 能力发现 | 客户端查询服务支持的 version、profile、endpoint、限制和扩展。 |
| Conformance Profile | 一致性画像 | 定义某类实现必须支持的能力集合和测试范围。 |
| Test Vector | 测试向量 | 跨实现验证 canonicalization、hash、签名、reducer、state resolution 等行为的固定输入输出。 |

## 12. 账户生命周期

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Service Account | 服务账户 | 用户在某服务上的登录入口或账户记录，不等同于 DID principal。 |
| Active | 活跃 | 账户可正常登录和写入。 |
| Locked | 锁定 | 安全风险导致临时禁止登录或写入，但不删除数据。 |
| Suspended | 暂停 | 治理或合规原因导致写入、公开展示或联邦行为受限。 |
| Deactivated | 已停用 | 账户被用户或管理员停用，session 和 device delegation 被撤销。 |
| Erasure Pending | 擦除中 | 正在执行数据最小化、Blob 删除、index 删除或合规保留处理。 |
| Session Revocation | 会话撤销 | 撤销 access token、refresh token、device session 或 Applet delegated session。 |
| Legal Hold | 法律保留 | 因合规或法律要求暂缓物理删除某些审计或媒体数据。 |

## 13. 易混术语

| 不要混淆 | 区别 |
| --- | --- |
| DID 与 Handle | DID 是稳定权限主体；Handle 是可迁移的人类入口。 |
| Actor 与 Principal | Principal 是身份根；Actor 是在 Space / 协作图里的行为者视图。 |
| Space Hierarchy 与权限继承 | 层级关系只表达组织和发现；权限、成员、历史、加密默认不继承，必须由 child Space 显式 opt-in。 |
| Entity 与 Event | Entity 是协作对象；Event 是事实和变更记录。 |
| Relation 与 View | Relation 是一等语义边；View 是投影定义。 |
| Repo 与 Index | Repo 保存可审计事实；Index 保存派生查询结果。 |
| Relay 与 Authority | Relay 传播事件；授权仍由签名、capability、policy 和 reducer 验证。 |
| Capability 与 Namespace | Capability 授权动作；Namespace 只说明 Applet 负责哪个名称范围。 |
| Redaction 与 Erasure | Redaction 裁剪协议内容并保留审计；Erasure 是服务侧物理删除/最小化流程。 |
| Read Receipt 与 Read Marker | Receipt 可公开或共享；Marker 默认私有，用于未读状态。 |
| Policy Server 与 Authz | Policy server 给风险决策；authz 是本地可验证授权判定。 |
| E2EE 与 Authenticated Media | E2EE 保护内容不可被服务端解密；authenticated media 只控制下载访问。 |
