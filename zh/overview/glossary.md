# 术语表

## 1. 目标

本文集中定义 Contrix 规范中的核心术语。若其他文档使用同一术语，除非所在章节明确覆盖，否则应以本文定义为准。

本文中的英文术语保留为规范关键字；中文解释用于帮助阅读，不改变字段名、事件名或协议对象名。

## 2. 核心对象

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 面向去中心化协作对象、会话、任务、看板、知识记忆和 agent 协作的协议族。 |
| Principal | 主体 | 协议中的稳定身份主体，通常由 DID 表示。人、组织、agent、Applet 都可以是 principal。 |
| Organization | 组织 | 一类 principal，通常由组织 DID 表示，可签发成员资格/角色 credential、控制服务 DID、托管 Principal Server / Index / Applet、发布 policy 或拥有 Space。Organization 不是 Space；它是治理与身份主体。 |
| Organization Governance | 组织治理 | Organization DID 的控制策略，包括治理密钥、阈值、多签、服务委派、恢复和所有权转移规则。 |
| Actor | 行为者 | 在 Space 中执行动作、产生 Event、拥有 profile 和 membership 的主体视图。Actor 通常映射到 principal，但可包含 ghost actor、bot actor 或 accountable actor。 |
| Space | 协作空间 | 复制、授权、schema、policy、membership 和 history visibility 的边界。它替代 Matrix room 作为 Contrix 的协作边界，但不是唯一数据模型。 |
| Official Space | 官方空间 | 由 Organization DID 直接创建，或被 active `cx.space.organization` state event 背书且 `scope.official=true` 的 Space。名称、域名、服务器托管方或成员列表不能单独证明官方性。 |
| Space Hierarchy | 空间层级 | Space 之间的 parent/child 组织关系，用于导航、发现和受控继承；不默认级联权限、成员、历史或加密。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、父 Space、组织页、精确链接或邀请发现的策略；不等于 join rule、read permission 或 history visibility。 |
| Room | 房间 | Space 内的一等会话容器，用于承载 Message、成员状态、历史可见性、通知和 E2EE epoch。Room 可以被 Card 链接，但权限和成员独立。 |
| Board | 看板 | Space 内的一等工作组织对象，包含多个 List；Board 是协议对象，不只是 View 投影。 |
| List | 列表 | Board 下的一等有序分组对象，通常包含多个 Card，并维护局部排序与归档状态。 |
| Card | 卡片 | Board/List 下的一等工作项、主题项或可推进对象。Card 可链接零到多个 Room，但不继承或控制这些 Room 的成员。 |
| Message | 消息 | Room 内的一等会话内容对象。Message 归属某个 Room，不是 Space 的唯一事实根。 |
| Morph | 开放对象 | 可由 `facets` 扩展字段和能力的开放对象。Morph 用于 task 之外的新类型、实验类型、集成对象和领域对象，不替代 Room/Board/List/Card/Message 的主语义。 |
| Facet | 能力切面 | Morph 或支持扩展的标准对象上声明的能力 mixin，例如 assignable、schedulable、replyable、documentable。Facet 不是对象身份。 |
| Relation | 关系 | Room / Board / List / Card / Message / Morph / Actor / Space 之间的一等连接对象，用于表达包含、回复、依赖、引用、分配、提及、父子、附件、Card linked Room 等语义。 |
| Event | 事件 | 协作事实和审计根。Event 由 actor/device/service 签名，进入 repo、sync、index 和 reducer。 |
| State Event | 状态事件 | 带 `state_key` 的 Event，当前状态由 `(type, state_key)` 归约得到，例如 membership、policy、schema、view definition。 |
| View | 视图 | 对标准对象 / Morph / Relation / Event 的投影定义，例如 kanban、table、calendar、chat、thread、graph、review queue。View 拥有自己的定义真相（query、filter、sort、renderer、layout、visible fields），但不拥有被投影对象的协作事实。 |
| Projection | 投影 | Index 或客户端根据 View / query / reducer 从 canonical Event 集合派生出的展示或查询结果。 |
| Schema | 模式 | 对标准对象、Morph、Relation、Event、View 或 service payload 的结构约束。 |
| Policy | 策略 | Space 或服务级治理规则，例如加入规则、历史可见性、媒体规则、审核策略、policy server 配置。 |
| Moderation Policy | 审核策略 | Space 或 Organization 发布的黑名单、允许列表、过滤、隔离、审核队列和上诉规则。它是 deny/quarantine 层，不创建 capability。 |
| Personal Blocklist | 个人屏蔽列表 | Actor 私有的屏蔽与过滤规则，存储在本地或加密 Account Repo 中，只影响个人客户端体验和通知/联系请求处理。 |

## 3. 标准对象与语义类型

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Standard Object | 标准对象 | 协议直接定义主语义、授权和 reducer 的对象类型，包括 Space、Actor Profile、Room、Board、List、Card、Message、Relation、Event、View、Policy 等。 |
| Open Object | 开放对象 | `Morph` 的语义别名，强调对象类型可由 schema、facets 和应用 profile 扩展。 |
| Task | 任务 | 常见 Card 语义或 Morph 类型，用于表达待办、状态、负责人、截止时间、依赖和讨论关系。若需要看板拖拽，应建模为 Card；若只是领域对象，可建模为 Morph。 |
| Topic | 主题 | 常见 Card 语义或 Room 组织方式。需要推进、状态和列表位置时用 Card；需要持续会话时用 Room。 |
| Thread | 线程 | Message 的回复链或 Room 内局部会话投影，不是独立权限边界。 |
| Document | 文档 | 标准对象或 Morph 类型，用于结构化长文、页面、规范、笔记。是否可评论、可审阅、可版本化由对象类型和 facets 决定。 |
| File | 文件 | Blob metadata 与可见性策略的对象化表示，可作为 Morph 或标准 file profile 实现。 |
| Memory | 记忆 | Morph 类型或扩展 profile，用于 agent 或人类确认的长期知识、事实、偏好或上下文。 |
| Run | 运行记录 | Morph 类型或扩展 profile，用于记录 agent、自动化或工具执行过程。 |
| Agent Protocol Session | Agent 协议会话 | Card、Morph 或 Run 显式切换到 A2A、ACP 或其他外部 agent protocol 执行时登记的受控会话。 |
| Mention | 提及 | 对 Actor、Room、Board、List、Card、Message、Morph 或 Space 的结构化引用，协议层必须落成 ref / relation，不依赖正文扫描。 |
| Reaction | 反应 | 对目标 Message、Card、Morph、Event 或其他对象的轻量语义反馈，通常通过 Relation 或标准 reaction event 表达。 |
| Social Post | 社交发布 | Morph 类型或扩展 profile，用于个人、组织或社区 feed 中的发布内容；可公开、受众受限或私有。 |
| Social Feed | 社交时间线 | 个人主页、组织公告、项目动态或关注流的发布入口/投影源；本身不替代 Repo 或 Space。 |
| Social Circle | 社交圈 | 发布者维护的受众集合，例如朋友圈、亲友圈、内部成员圈；成员列表默认私有或受限可见。 |
| Audience Policy | 受众策略 | 定义 post/feed 的可读、可回复、可转发、可索引和受众快照规则。 |

## 4. 身份与可发现性

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| DID | 去中心化标识符 | Principal 的稳定标识。Contrix 默认 DID 方法为 `did:uuid`，同时支持 `did:web`、`did:keri`、`did:key` 等外部或 method-specific 适配。 |
| DID Document | DID 文档 | DID 解析得到的控制密钥、服务端点、验证方法等文档。外部 DID 文档保留原始字段，进入 Contrix normalized view 前映射为 snake_case。 |
| DID Method | DID 方法 | DID 的解析与更新规则，例如 `did:uuid`、`did:web`、`did:keri`、`did:key`、`did:plc`。不同方法可能使用公共 registry、私有 registry、KERI witness / watcher、域名解析或纯本地 resolver。 |
| DID Key Log | DID 密钥日志 | 记录 DID 控制密钥演化、轮换、恢复和见证的追加式日志。 |
| Handle | 人类可读标识 | 例如 `alice.example.com` 或 `alice@service`。Handle 用于发现和显示，不作为权限主键。 |
| Claim | 声明 | 对某个主体属性、绑定或资格的可验证声明，例如 handle binding、组织成员资格。 |
| Attestation | 证明/背书 | 由可信 issuer 对 Claim 签名背书。 |
| VC | 可验证凭证 | Verifiable Credential，用于最小披露地证明属性、成员资格或 handle 绑定。 |
| Presentation | 凭证呈示 | 主体向验证方出示一个或多个 VC 的证明，可包含选择性披露或零知识证明。 |
| Disclosure Policy | 披露策略 | Holder 私有规则，定义可向哪些 verifier / organization 披露哪些 claim、handle 或 derived proof。 |
| Disclosure Receipt | 披露回执 | Holder 私有审计记录，记录一次 presentation 披露了哪些字段、发给谁、使用何种 proof profile，不包含未披露字段值。 |
| Pairwise DID | 成对 DID | 面向特定关系或组织使用的私有 DID，用于降低跨域关联风险。 |
| Public Persona DID | 公开人格 DID | 主动公开用于发现、社交或品牌展示的 DID。 |
| Normalized Principal View | 规范化主体视图 | 将不同 DID 方法、外部文档和 sidecar 数据映射为 Contrix 内部可验证主体视图。 |

## 5. 授权与责任

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Capability | 能力授权 | 明确授予某主体在某范围执行某动作的可验证授权。Contrix 使用 capability 替代 power level 作为核心权限模型。 |
| Grant | 授权记录 | 表达 capability 的签名对象，包含 issuer、subject、actions、scope、constraints、expiry 等。 |
| Delegation | 委托 | 一个主体把有限 capability 委托给另一个主体、设备、agent 或 Applet。 |
| Derived Grant | 派生授权 | 由 Space 层级继承机制自动从父 Space grant 派生出的子 Space grant，受 `inherited_depth` 和继承策略约束。 |
| Revocation | 撤销 | 使 grant、device、session 或 delegation 在其因果后继中失效的事件或状态。 |
| Constraint | 约束 | capability 的使用条件，例如时间、Space、Room、Board、Card、Morph、字段、设备、速率、审批、Applet namespace。 |
| Condition Selector | 条件选择器 | 以可验证属性匹配主体的授权 subject，例如“某组织当前成员”。 |
| Accountable Actor | 可追责行为者 | 有直接身份但需要 responsible、guardian 或 controller 的 Actor，例如 agent、未成年人、托管账号。 |
| Responsible Party | 责任主体 | 对 accountable actor 行为承担责任的 principal。 |
| Approval | 审批 | 高风险动作的授权条件，可在提交前或 proposal 后发生。 |
| Proposal | 提案 | 受限主体不能直接提交高风险 Event 时创建的待审批意图。 |
| Authz | 授权判定 | Authorization 的缩写，指 capability、policy、membership、device trust 等规则的综合判定。 |

## 6. Repo、同步与状态

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Repo | 仓库 | Principal 或 Space 发布 signed commit / operation 的追加式可验证日志。Repo 是协议逻辑对象，不等同于服务器。 |
| Commit | 提交 | Actor 侧发布单元，包含一个或多个 operation/event 引用和签名。 |
| Operation | 操作 | 对协作图的原子变更意图或事实，通常封装为 Event 或被 Event 引用。其 wire 字段名为 `operation` / `operations`。 |
| Operation Envelope | 操作信封 | sync / federation 写路径的签名承载信封，字段名与 Event Envelope 一致（`actor_id`、`kind`、`content`、`proofs`），通过 `causal`、`target_ref`、`authz_ref` 绑定写入语义。 |
| Operation Log | 操作日志 | 追加式审计记录，用于归约、同步、回放和冲突分析。 |
| Reducer | 归约器 | 将 accepted Event / Operation 集合归约为当前状态和 projection 的确定性规则。 |
| Reducer Profile | 归约器画像 | 定义 reducer 版本和行为规范的标识符，例如 `cx.reducer.v1`。 |
| OR-Set | 观察-移除集合 | 冲突解决中用于集合字段的 CRDT 策略，支持并发 add/remove 收敛。 |
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
| Identity Resolution Infrastructure | 身份解析基础设施 | DID method resolver、registry、witness、watcher、OOBI discovery 或 method-specific verifier 的统称。它证明 DID 控制历史、key state 和服务委托，不决定某个 DID 是否能登录组织或访问组织数据。`did:key` 可以只需要本地 resolver；`did:keri` 通常需要 KERI log、witness、watcher 或 OOBI。 |
| Witness | 见证节点 | 对 DID log、key rotation、重要状态变更进行外部见证的服务或主体。 |
| Principal Server | 主体服务器 | 由 principal 控制或通过 DID / Space policy 明确委托的服务边界，可承载 repo、sync、index、blob、push、policy 等能力；`service_type` 应声明为 `principal_server`。 |
| Auth / Account Server | 认证/账户服务器 | 处理 passkey、OIDC、SSO、设备配对、session grant、账户恢复和 soft logout 的服务。它证明服务账户登录并绑定到 DID / device，不直接证明 DID 控制权，也不必须与 DID resolver 同源部署。 |
| Sync Service | 同步服务 | Principal Server 上的 Space 增量同步能力，负责订阅、回补、去重、临时信令和受控分发；它不是独立第三方服务器角色，也不是真相源。 |
| Index | 索引 | 将授权事件物化为查询结果、当前态、搜索结果和视图投影的派生层。 |
| AppView | 应用视图服务 | 面向特定产品或 UI 的 Index / projection 服务。 |
| Plaintext-visible Service | 明文可见服务 | 被 Space policy、principal DID 或组织 DID 明确委托，允许接收或保存非 E2EE 私有正文、附件预览、全文索引、通知摘要、embedding 或可逆派生摘要的服务。 |
| Blob Store | 大对象存储 | 存储附件、媒体、snapshot chunk 或大对象的服务，地址可多源，校验基于内容哈希。 |
| Device / Key Server | 设备与密钥服务器 | 提供 to-device message、one-time key、fallback key、device list 和 key backup metadata 的服务；设备信任仍来自签名链。 |
| Authz Service | 授权服务 | 预检查、解释或缓存 capability / policy 判定的服务，不应替代可验证协议规则。 |
| Policy Server | 策略服务 | 对邀请、加入、消息、媒体、Applet、联邦等行为给出签名风险决策的服务。 |
| Push Gateway | 推送网关 | 将脱敏通知投递到移动或桌面平台推送系统的服务。 |
| Directory Service | 目录服务 | 对 Space、Organization、Actor、Applet 等资源提供授权过滤后的搜索、列举和精确解析的派生服务；不是真相源。 |
| Applet Server | Applet 服务器 | 承载 Applet / bridge / bot / portal / ghost actor 逻辑的服务，写入仍需 capability、namespace 和签名。 |
| Agent Runtime Server | Agent 运行服务器 | 执行 agent run、tool call、memory promotion 和外部 agent protocol handoff 的服务；输出写回 Repo / Space 后才成为协议事实。 |
| Realtime Media Server | 实时媒体服务器 | 提供 ICE config、TURN/STUN、SFU/MCU、录制或会议辅助能力的服务。 |
| Moderation / Compliance Server | 审核/合规服务器 | 提供 report、审核队列、server ACL、policy list、appeal、legal hold 和 erasure workflow 的服务。 |

## 8. 联邦与互操作

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Federation | 联邦 | 不同域、组织或服务节点之间交换 Event、Operation、state、backfill、join/invite 的协议层。 |
| Service DID | 服务 DID | Principal Server、Index、Applet、Policy Server 等服务使用的 DID。 |
| Federation Transaction | 联邦交易 | 跨服务批量交换 PDU/EDU 等消息的传输单元；Contrix 中对应 signed transaction envelope。 |
| Cross-domain Join | 跨域加入 | Actor 通过一个服务加入另一个服务或组织托管的 Space。 |
| Server ACL | 服务级访问控制 | 对联邦服务、域、IP、service DID 或 Principal Server 的接入限制。 |
| Applet | 小应用/集成服务 | 类似 Matrix appservice 的扩展机制，用于机器人、桥接、外部 SaaS 集成和自动化。 |
| Applet Registration | Applet 注册 | 描述 Applet service DID、endpoint、namespace、protocol、认证方式和能力范围的签名声明。 |
| Namespace | 命名空间 | Applet 声明自己负责处理的 actor、space、handle 或外部 protocol 标识范围。Namespace 不等于 capability。 |
| Bot Actor | 机器人行为者 | Applet 的可见自动化 Actor，可加入 Space、被 mention、发送消息或执行任务。 |
| Ghost Actor | 幽灵行为者 | 外部网络用户在 Contrix 中的镜像 Actor，必须可审计且不能静默冒充原生 human actor。 |
| Portal Space | 门户空间 | 外部系统 location 在 Contrix 中的镜像 Space，例如 Slack channel、GitHub issue discussion。 |
| Bridge | 桥接 | 在 Contrix 与外部系统之间转换 identity、message、event、file、membership 和 permission 的机制。 |
| Protocol Adapter | 协议适配器 | 将 Contrix task/session 映射到 A2A、ACP、MCP bridge 或企业私有 agent API 的组件。 |

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
| Space Key | 空间密钥 | MLS group 的 epoch 密钥材料，用于加密/解密 Space 内消息。通过 `cx.space_key.share` / `cx.space_key.withheld` 在设备间分发。 |
| E2EE | 端到端加密 | 非授权服务器和 index 默认无法解密内容的加密模式。 |
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
| STUN | NAT 探测服务 | WebRTC 用于发现公网反射地址的服务。 |
| TURN | 中继媒体服务 | WebRTC 无法直连或要求隐藏 IP 时使用的媒体中继服务，凭证必须短期有效。 |
| ICE | 连接候选协商 | WebRTC 用于选择 P2P、STUN 或 TURN 路径的连接协商机制。 |
| SFU | 选择性转发单元 | 多方会议中转发媒体流的服务，通常不应解密 E2EE 媒体。 |
| MCU | 混流单元 | 多方会议中混合音视频的服务，通常会接触明文媒体，必须由 policy 显式允许。 |

## 11. API、编码与一致性

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Canonical JSON | 规范 JSON | 用于 hash 和 signature 的确定性 JSON 编码规则。 |
| Canonical Object | 规范对象 | 持久化、可签名、可审计的协议对象（如 Room、Board、Card、Message、Morph、Relation、Event、View、Policy），区别于传输信封或投影结果。 |
| ULID | 通用排序唯一标识符 | Universally Unique Lexicographically Sortable Identifier，Crockford Base32 编码，用于 Contrix ID 的排序部分。 |
| 3PID | 第三方标识 | Third-party Identifier，如邮箱、手机号，用于邀请和身份关联。 |
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
| Transport Binding | 传输绑定 | 将 Contrix canonical operation 映射到 HTTP/JSON、gRPC、WebSocket、SSE、message queue、libp2p 或 IPC 的规则。 |
| TSP | Trust Spanning Protocol | Trust over IP 的可信消息协议，用于跨 Verifiable Identifier 建立方向性可信消息关系；在 Contrix 中是可选 transport/trust binding。 |
| VID | Verifiable Identifier | TSP 使用的可验证标识符抽象，可映射到 Contrix principal DID、service DID、pairwise DID 或受支持的外部标识体系。 |
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
| Organization 与 Space | Organization 是可验证身份和治理主体；Space 是协作数据、授权和复制边界。一个组织可以拥有或托管多个 Space，一个 Space 也可以由多个组织共同治理。 |
| Space Hierarchy 与权限继承 | 层级关系只表达组织和发现；权限、成员、历史、加密默认不继承，必须由 child Space 显式 opt-in。 |
| Discoverability 与 Join Rule | Discoverability 决定能否发现资源存在；Join Rule 决定如何加入。公开可发现的 Space 仍可要求 invite、knock 或 restricted join。 |
| Discoverability 与 History Visibility | Discoverability 不授予历史读取；公开可搜索的 Space 不等于 `world_readable`。 |
| Follow 与 Contact/Circle | Follow 是订阅关系，通常单向；Contact 是联系人关系；Circle 是发布者私有或受限的受众集合，不能互相等同。 |
| Public Feed 与 Circle Feed | Public Feed 面向公开索引和广播；Circle Feed 必须按 Audience Policy 授权，不能只靠 UI 隐藏。 |
| 标准对象 / Morph 与 Event | 标准对象和 Morph 是协作对象；Event 是事实和变更记录。 |
| Relation 与 View | Relation 是一等语义边；View 是投影定义。对象之间的包含、依赖、回复、关联等事实必须由 Relation 表达，不能只存在于 View cache 或 layout 中。 |
| Repo 与 Index | Repo 保存可审计事实；Index 保存派生查询结果。 |
| Repo 与 Principal Server | Repo 是可验证日志；Principal Server 提供 `/repo/*` API 来访问、托管或复制该日志。 |
| Sync Service 与 Authority | Sync Service 只提供受控同步；授权仍由签名、capability、policy 和 reducer 验证。 |
| Capability 与 Namespace | Capability 授权动作；Namespace 只说明 Applet 负责哪个名称范围。 |
| Redaction 与 Erasure | Redaction 裁剪协议内容并保留审计；Erasure 是服务侧物理删除/最小化流程。 |
| Read Receipt 与 Read Marker | Receipt 可公开或共享；Marker 默认私有，用于未读状态。 |
| Policy Server 与 Authz | Policy server 给风险决策；authz 是本地可验证授权判定。 |
| Moderation Policy 与 Capability | Capability 决定是否具备基础动作权限；Moderation Policy 可以 deny、quarantine 或 require review，但不能凭空授予权限。 |
| Personal Blocklist 与 Space Ban | Personal Blocklist 是个人私有渲染/通知/联系过滤；Space Ban 是 Space 共享成员状态，会影响加入和写入。 |
| E2EE 与 Authenticated Media | E2EE 保护内容不可被服务端解密；authenticated media 只控制下载访问。 |

## 14. 规范性边界规则

以下规则用于消除实现中的概念合并和权限混淆。除非具体 profile 明确收紧，本节为 Contrix v1 的规范性边界。

1. Principal 是身份根；Actor 是 Space 内行为者视图。任何授权、签名验证和责任追溯 MUST 能回到 Principal DID 或受验证的 condition selector。Actor Profile、display name、handle、头像和组织目录结果都不得成为权限主键。
2. Organization 是治理 Principal；Space 是协作边界。组织可以拥有、托管或背书多个 Space，但 Organization DID、Space owner、Principal Server 运营方和成员列表是四个独立概念。实现 MUST NOT 仅凭域名、服务器托管方或 Space membership 推断组织归属。
3. 标准对象和 Morph 是当前协作对象；Event / Operation 是事实与审计输入；View 是投影定义，Projection 是派生展示。View 的定义本身可以是 canonical state，但被投影对象的状态、位置、关系和权限必须回到对象、Relation、Policy 和 Event。实现 MUST NOT 只保存当前对象而丢弃可验证事件链，也 MUST NOT 把 View 的可见字段当作权限裁剪。
4. Relation 是协议内的一等语义边；正文中的链接、mention、引用和回复若影响授权、通知、检索或审计，MUST 落成结构化 Relation 或 Event 字段。客户端正文扫描只能作为输入辅助。
5. Repo 是可验证发布日志；Principal Server 是服务边界；Index 是派生查询层。三者可以同机部署，但 service DID、`service_type`、capability、plaintext visibility 和 conformance profile MUST 可区分。
6. Capability 授予动作；Policy 限制、隔离或要求审查；Moderation Policy 不授予能力。任何 `allow` 结果都必须先满足 capability，再满足 policy、membership、device trust 和 schema 约束。
7. Invite 是加入引导，不自动授予完整权限。接受邀请后，只有被引用并满足约束的 grant 才进入有效授权集合；过期、撤销或认领失败的 invite MUST fail closed。
8. Handle、Claim、Attestation 和 VC 只能证明属性或绑定。权限判定若依赖这些属性，MUST 验证 issuer、audience、有效期、撤销状态和选择性披露范围。
9. E2EE、authenticated media 和 plaintext-visible service 是三种不同边界。下载需要授权不代表服务端不可见内容；端到端加密也不自动允许把 metadata、缩略图、embedding 或通知摘要交给未授权服务。
10. Redaction 是协议层内容裁剪；Erasure 是服务侧物理删除或最小化流程。实现 MUST 在 UI、审计和合规流程中区分二者，不能承诺已传播副本的全球物理删除。
