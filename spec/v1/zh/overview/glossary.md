---
title: 术语表
status: candidate
normative: true
stability: v1
updated: 2026-06-01
see_also:
  - index.md
  - overview/architecture.md
  - conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Contrix 规范中的核心术语。若其他文档使用同一术语，除非所在章节另有说明，以下定义优先于扩展实现约定。

本文中的英文术语保留为规范关键字；中文解释用于阅读，不能替代字段名、对象名或事件名。

术语表维护规则：

- 同一个 canonical 术语只定义一次；不要再添加“见上文”式重复行。
- 非规范别名可以保留为单独条目，但必须明确写出 canonical 术语，并说明新增 normative 文本应使用哪个术语。
- 禁用词、历史词和互操作上下文词应标注适用范围；不能把迁移期词汇重新引入 v1 core model。
- 局部上下文词（例如 SFU `participant_id`、Mermaid sequence `participant`）只在对应章节内有效，不升级为全局主体术语。

## 2. 核心术语

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 去中心化协作对象协议族，定义 identity、写入、同步、授权、显示与审计规则。 |
| Principal | 主体 | 协议中的稳定行为者身份；通常由 DID 标识，包含个人主体、组织、agent、Applet 等。 |
| Actor | 参与身份 | Principal 在 Realm 内的行为身份：执行动作、产生 Event、持有 profile 与 membership；可在不同 Realm 表现为 pairwise pseudonym。 |
| Organization | 组织 | 可治理主体的一类 Principal，通常由组织 DID 标识。 |
| Organization Governance | 组织治理 | 组织成员资格、控制策略、密钥、恢复与授权委派规则。 |
| Handle | 可路由人类地址 | 面向用户的可读入口，统一 canonical handle `user:domain`，显示形态 `@<localpart>:<domain>` 或 `<localpart>@<domain>`。可由 holder 自托管签发或 Organization / Principal Server / Directory 签发；解析结果含 `subject` DID，并 MAY 携带 `member_delivery_binding.recipient_service_did`，但只有物化为 Realm `delivery_binding` 后才成为投递路径。不可作为协议主体或授权主键。 |
| Connection Identifier | 连接标识角色 | 外部体系字符串（邮箱、手机号、通讯录用户名、外部账号 ID 等）在**发现 / 邀请 / consent 阶段**所扮演的角色；可见性默认关系私有，不得自动写入 DID Document、Realm history 或 grant subject。同一字符串经 holder 显式 disclosure 后可升格为 Handle。区分点是 holder 意图与可见性，不在字符串形态。 |
| Administrative Identifier | 管理标识角色 | 外部体系字符串（组织账号、计费账号、员工编号等）作为**组织本地管理标识**所扮演的角色；不出协议线，不得作为协议主体、grant subject 或 Event actor。 |
| Display Name | 显示名 | UI 展示用名称，可变且不可用于 ACL、grant、审计归因或发送者验证。 |
| Realm | 协作边界 | security/sync/auth/E2EE 边界。授权、policy、membership、history visibility、同步、加密、federation 都以 Realm 为根。`cx:realm:` 永远是边界，不承担产品导航树职责。底层只有一个 schema `cx.schema.realm.v1`；按用途分为 Principal Control Realm 与 Collaboration Realm 两类（见 [`models/realm-and-space.md` §2.7](../models/realm-and-space.md)）。 |
| Collaboration Realm | 协作 Realm（角色） | Realm 的一种用途，承载多方业务协作状态（Flow / Message / Space / Morph / Relation 等）。与 Principal Control Realm 互补。按是否含跨信任域成员再分 Internal / External 两类。 |
| Internal Collaboration Realm | 域内协作 Realm | Collaboration Realm 的一种：`federation_policy ∈ {closed, restricted}` 且成员仅来自本部署 trust domain。组织主网络上的普通项目 / 团队 Realm 默认属于此类。 |
| External Collaboration Realm | 跨域协作 Realm | Collaboration Realm 的一种：含跨信任域成员（external Organization DID / external principal）。Sovereign deployment 中其 policy 受 `cx.profile.sovereign_deployment.v1` 进一步约束（allowlist federation、独立 enclave、E2EE、deny-default applet/agent；见 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)）。 |
| Principal Control Realm | 主体控制 Realm（PCR） | Realm 的另一用途：与某 principal DID 1:1 绑定，承载该 principal 的身份基础设施事件（device / session / KeyPackage / recovery / profile / consent）。schema 层仍是 `cx.schema.realm.v1`，通过 `fields.purpose="principal_control"` + `schema_refs` 含 `cx.profile.principal_control_realm.v1` 标记 + 事件类型 allowlist 与一般 Collaboration Realm 区分。详见 [`identity/key-management.md` §4.1](../identity/key-management.md)。 |
| Trust Domain | 信任域 | deployment / sovereign replay boundary，wire 形态为 `cx:trust_domain:<scope>`。它在 service describe、Realm create 和跨域 proof transcript 中绑定接收上下文；定义见 [`../identity/identity-did.md` §3.6](../identity/identity-did.md#36-trust-domain)。 |
| Official Realm | 官方边界 | 由组织或 policy 明确确认的 Realm；它是治理 / 安全声明，不等同于用户可见的 Space。 |
| Realm Link | Realm 关系边 | Realm 之间通过 `cx.realm.link` 表达的显式治理、发现、mirror、confidential extension、迁移等关系；不是 hierarchy，不默认级联权限或历史。 |
| Space | 结构性分组对象 | 用户可理解的结构容器与导航节点（project、folder、board、list、泳道、calendar bucket、page group 等），ID 形如 `cx:space:`。永远没有自己的 membership / policy / E2EE group / federation policy；metadata 由 `realm_id` 指向的 home Realm 授权，子资源默认 Realm 由 `default_realm_id` 解析。 |
| Space Hierarchy | Space 层级 | Space 之间通过 `parent_space_id` + `cx.space.parent` 表达父子关系；可跨 Realm 做导航，但不传播 Realm membership、capability、history 或 E2EE key。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、邀请、组织页或精确链接发现。 |
| Flow | 协作主对象 | Realm 内承载协作议题、任务、正式表达与讨论轨道的标准对象。 |
| Flow primary track | Flow 默认入口 | 按 track primary 解析规则得到的默认 track；显式 `is_primary=true` 优先，未显式时标准 `synthesis` 优先。 |
| ~~Room~~ | _deprecated_ | 历史用语；v1 core model 不使用 `Room` 名词，请使用 `Flow discussion track` / `discussion track view`。`Room` 仅在 MIMI / Matrix interop 模块的明确互操作上下文中允许出现（参见 [`forbidden-model-terms.json`](../../artifacts/registry/forbidden-model-terms.json) `Room` 条目的 `allowed_contexts`）。 |
| synthesis track | 正式表达轨道 | Flow 的"synthesis"轨道，承载正式状态、结构化字段与决策正文。完整字段、profile、适用场景以 [`../models/flow-and-message.md` §4.2](../models/flow-and-message.md) 为准。 |
| discussion track | 讨论轨道 | Flow 的"discussion"轨道，承载消息与讨论时间线；成员、历史可见性和 E2EE 由 Flow 整体的 `scope_circle_id` 决定（`null`=Realm-default scope，否则=该 [Circle](../models/circle.md) scope）。Flow 单一 scope，不存在 per-track 安全边界。完整 profile 集合与适用场景以 [`../models/flow-and-message.md` §4.3](../models/flow-and-message.md) 为准。 |
| Circle | 子事件边界 / scoped 协作圈 | `cx:circle:` 对象，Realm 内的子集成员 + 独立 history visibility + 投递 / 查询 / projection 裁剪边界。**译名注意**：不要叫"信任圈"——Circle 不构成信任域，避免与 Trust Domain 混淆。**不**持有 federation identity 或 policy server（这些仍在父 Realm）。对象通过 `scope_circle_id` 引用 Circle 表达"窄于 Realm 的协作圈"；可按父 Realm floor 启用独立 MLS group。详见 [`../models/circle.md`](../models/circle.md)。 |
| Circle scope / `scope_circle_id` | 对象 effective scope 引用 | 对象（Flow / Message / Morph / Space）的 `scope_circle_id` 字段；`null` = Realm-default scope，否则指向同 Realm 的 Circle。Reducer 把它物化为 immutable tagged `effective_scope`，进入 Event envelope / Anchor leaf；MLS-backed scope 中也进入 E2EE AAD。 |
| effective_scope | 事件 immutable scope tag | Reducer 在每个 Event 接受时固化的 tagged scope（`{kind:"realm",realm_id}` 或 `{kind:"circle",realm_id,circle_id}`）。进入 envelope / sub-anchor leaf；在 MLS-backed scope 中也进入 AAD；后续 `scope_circle_id` 改绑不得重解释旧 event。 |
| Board | 看板 | `cx:space: kind=board`，组织一组 List Space 与其他 Space 的工作流容器。 |
| List | 列 / 泳道 | `cx:space: kind=list`，挂到 Board Space 下、承载 Flow 位置关系的列容器。 |
| Message | 消息对象 | 发生在 Flow discussion 轨道中的即时沟通与补充记录。 |
| Morph | 开放对象 | 标准对象扩展框架，承载非固定业务类型的可声明对象。 |
| Facet | 能力标签 | Morph/Profile 的能力提示（如 container/schedulable/renderable）。 |
| Relation | 关系边 | 对象间有向关系定义，如 `contains`、`mentions`、`depends_on`。 |
| Event | 协议事件 | 协议传播和验证的基础事实单元（Envelope 的内容承载形式）。 |
| Event Envelope | 事件外壳 | `event_id`、`actor_id`、`kind`、`payload`、`proofs` 等字段的签名封包。 |
| Wire Event | 线路事件 | 在协议 wire format 上实际传输、存储、同步、联邦并进入 reducer / 审计验证的 signed Event Envelope（schema `cx.schema.event.v1`，artifact [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）。它是 v1 共享状态的唯一 wire fact；字段语义见 [`../models/event-and-patch.md` §2](../models/event-and-patch.md)。 |
| Wire fact | 线路事实 | 在协议线上以 canonical bytes + proof 承诺、可被接收方验证并作为 reducer / audit truth source 的规范事实。v1 不定义独立的 `wire_fact` 对象；除 Wire Event / Event Envelope 外，Operation、SDK builder / draft、receipt object 与 projection 都不是共享 wire fact，除非它们以 registered Event kind 的 payload 进入 Event Envelope。 |
| Event Store | 事件存储 | 保存 Event Envelope 的服务能力，不是协议真相源本身。 |
| Event Batch Receipt | 事件批次回执 | 可选审计/同步加速对象（payload schema `cx.schema.event_batch_receipt.v1`），**不是 canonical history**，也**不是 reducer input**；只对 issuer *选择* 承诺的事件集合提供 *integrity*，不提供 *completeness*。详见 [`../models/event-and-patch.md` §5](../models/event-and-patch.md) 与 [`../sync/operations-sync.md` §4.1](../sync/operations-sync.md)。 |
| Integrity (data) | 数据完整性 | 给定数据未被中间人或第三方篡改。集合上的 Merkle / set commitment 提供 integrity，但不保证集合本身已覆盖给定范围。 |
| Completeness (range) | 范围完整性 | 给定范围内（per-actor seq interval、frontier 上下界、actor / realm scope）**没有漏给**任何属于该范围的成员。Completeness 必须依赖 *range-bound* attestation（带显式 from/to 边界）+ witness quorum 或独立 anchor 背书；set-bound commitment 单独不足以证明 completeness。 |
| Range-bound Attestation | 范围完整性证明 | 携带 explicit range scope（per-actor seq interval、frontier 上下界）的签名证明，是 completeness 证明的载体。v1 已注册 active event kind `cx.attestation.range_completeness`（payload schema `cx.schema.range_completeness_attestation.v1`），详见 [`../sync/operations-sync.md` §4.2](../sync/operations-sync.md)。 |
| Snapshot | 快照 | 恢复/同步起点对象，包含某时刻 Materialized State 与 frontier。 |
| HLC | 混合逻辑时钟 | `HLC` 为 `clock` 排序标签，固定格式 `<unix_ms_hex(12)>-<logical_hex(4)>-<node_id_hash(8)>`（hex 字段宽度依次 12 / 4 / 8）；canonical 规则见 [`../conformance/encoding.md` §7](../conformance/encoding.md)。 |
| Cursor | 同步游标 | 指定 frontier 的 `scope:realm\|actor\|query` 编码，用于增量同步与重放。 |
| Canonical JSON | 规范 JSON | 确定性 JSON 序列化格式，所有签名/哈希/对账输入必须使用；要求 UTF-8、key 排序、无空白、唯一 number 表示。 |
| View | 投影定义 | 查询 + kind + renderer + config 的共享可签名对象，定义“怎么看”。 |
| View.kind | 投影族类 | `collection / timeline / graph / document / composite`。 |
| Capability | 能力 | 授权语义与对象的绑定关系，授予 subject 执行特定 action。 |
| Capability Grant | 能力授权对象 | `capability` 标准对象；记录谁在什么条件下可执行何动作。 |
| Policy | 策略 | 运行期约束对象，用于授权、密钥、留存、治理与安全边界。 |
| Invite | 邀请 | 邀请主体加入 Realm 或授予特定能力的标准对象/事件 payload。 |
| Principal Server | 主体服务 | 主体控制或委托入口服务，承载 events / account aggregate / snapshot / discovery 等核心 API。Realm 内实际投递目标由成员 `delivery_binding.recipient_service_did` 决定；DID Document 默认 Principal Server 只可作为 join / rebind 时被 policy 允许的 binding 来源，不是 Realm delivery fallback。 |
| Sync Service | 同步服务 | 公开/订阅事件与 frontier 的受控同步能力，通常由 Principal Server 提供。 |
| Event Store Service | 事件存储服务 | 与 Sync Service 关联的持久化与检索服务角色。 |
| Blob Store | 二进制对象存储 | 附件、媒体、文件对象的存储与引用服务。 |
| Directory Server | 目录服务 | 提供可发现的 Realm、组织、actor、Applet 信息。 |
| Identity Resolution Infrastructure | 身份解析基础设施 | DID 文档、method resolver、密钥材料与验证链路。 |
| Redaction | 清理/隐私裁剪 | 合法授权下对已发布事实做最小化可见性处理。 |
| Erasure | 物理擦除 | 在某个存储边界内对原始 payload、blob、派生内容的不可恢复删除；不同于 Redaction，它不保留正文。 |
| Causal Depth | 因果深度 | 事件在已知 DAG / prev_refs 中的深度值；只可用于 timeline 诊断或兼容投影，不参与协议状态 winner。 |
| Pending Move | 待锚定动作 | Move 已通过本地格式/签名初检，但尚未被 Anchor frontier 覆盖；不影响 effective state。 |
| Effective | 已生效 | Move 被有效 Anchor frontier 覆盖，并已进入对应 Anchor view 的 state_root。 |
| Rejected | 已拒绝 | Move / Anchor 在格式、签名、schema、precondition、授权或 state_root 校验上确定失败。 |
| Move | 动作 | 多 cell 原子条件写；包含 `preconditions[]`、`effects[]`、`anchor_ref`、`refs[]` 与 issuer 签名。 |
| Anchor | 锚点 | Ordering authority 对 Move frontier 的签名承诺；包含 predecessors、frontier、state_root 与 anchorer signature。 |
| Genesis Anchor | 创世锚点 | 某个 Realm 的 Anchor DAG 根 Anchor；它是唯一允许 `predecessor_refs=[]` 的 Anchor，且 v1 要求 `frontier=[]`。它给该 Realm 的首个 reducer-input Event（通常是 `cx.realm.create`）提供 `anchor_ref` 基线，本身不是 Event，也不写入 cell。详见 [`../authz/event-auth-state-resolution.md` §4](../authz/event-auth-state-resolution.md)。 |
| Anchor DAG | 锚点图 | 某个 Realm 内已接受 Anchor 形成的 DAG；多个 leaf 通过 deterministic effective anchor view 查询。 |
| Cell | 状态单元 | Lattice 维护的最小协议状态键，形如 `cx:cell:<component>:<subject>`。 |
| Lattice | 状态代数 | 每个 cell family 的确定性 join 规则；核心类型包括 `or_set`、`mv_register`、`cas_register`、`fsm`、`counter`、`ordered_log`、`lww_register`（仅可用于 profile 明确标记 `client_projection_only=true` 的 UI affordance，不得作为授权或 Anchor 关键路径）、`rga`（协作文本与有序列表）。 |
| Bottom | 底值 | Lattice join 无法给出合法 value 时返回的 `⊥`；`bottom=reject` 时依赖它的 Move fail closed，`bottom=expose` 时可投影为冲突诊断。 |
| Reset | 重置语义 | 规范中“reset”不是单一 wire 动作：capability reset 通常是 revoke + reissue；cross-signing reset 是 `cx.cross_signing.reset`；cas_register / fsm 进入 `⊥` 后的恢复是 conflict-recovery Move（带 `state_witness` / `inclusion_proof` / recovery capability），不是普通 CAS 覆盖。正文使用 reset 时必须说明对应 event kind 或 recovery path。 |
| Component / Cell Family | 组件 / Cell 族 | 跨协议版本稳定的 cell family 标识符，URI 形式 `cx.component.<facet-path>.v<n>`；registry 为 reducer-input kind 声明 `cell_family`、`lattice` 与 `bottom`。 |
| MLS Governance Binding | MLS 治理绑定 | E2EE Realm 中把 MLS epoch 与 governance state（membership / policy / capability / Anchor frontier）强绑定的机制（profile `cx.profile.mls_governance_binding.full.v1`，定义见 `crypto-media/encryption-and-audit.md §2.5`）。由两层 artifact 组成：commit 侧的 *Governance Binding Payload* (`governance_binding`) 提供证据，lattice 侧的 *Covered Frontier Cell* (`covered_frontier_cell`) 沉淀状态。 |
| Governance Binding Payload | 治理绑定 payload | MLS Governance Binding 的 **commit-side proof**：每个 `cx.mls.commit` 携带的 `governance_binding` payload（MLS GroupContext extension `cx_governance_binding`，codepoint `0xF1C0`），哈希进 MLS transcript，覆盖 `membership_frontier`、`policy_root`、`capability_root`、`discussion_metadata_digest`。 |
| Covered Frontier | 已覆盖前沿 | MLS Governance Binding 的 **lattice-side accumulator**：`covered_frontier_cell`（cell family `cx.component.covered_frontier.v1`，or_set，bottom=expose）当前值，累积已被 commit attest 的 governance Anchor frontier；E2EE message Move 用 `contains` precondition gate 自身依赖的 governance frontier。 |
| Anchor Profile | 锚点 Profile | Realm create 时固定的 Anchor finality profile：`single_did`、`threshold`、`open_set` 或 `mixed`。 |
| Anchorer Cell | 锚定者 Cell | 定义下一批 Anchor 由谁授权的 `cas_register + bottom=reject` cell；冲突时产生 Realm-wide Anchor pause。 |
| Consent | 同意 | Holder-private 决策："我同意接收来自 X 的某种联系"。表达为 consent cell 上的 Move effect，是 invite / contact 路径的前置 gate。 |
| Consent Scope | 同意范围 | Consent grant 适用的联系类型枚举：`invite` / `direct_message` / `voice_call` / `video_call` / `presence` / `any`。 |
| Reducer | 归约器 | 确定性纯函数，将 Anchor frontier 中的 Move effects 归约为 cell values、state_root、bottom diagnostics 与产品 projection。 |
| Materialized State | 物化状态 | Reducer 输出的当前态对象，如 Flow、Relation、View。 |
| Frontier | 前沿 | Move / Anchor / Actor / Realm 已验证的最远同步边界。 |
| Causal Barrier | 因果一致性屏障 | 客户端或可选受托 projection 服务在返回查询结果前，依据本地 sync frontier 等待特定写入前沿到达的机制；用于保障 read-your-writes 体验。定义见 [`overview/architecture.md` §3.4](./architecture.md)。 |
| read-your-writes barrier | 读己之所写屏障 | Causal Barrier 在"读到自己刚提交的写入"这一场景下的别名；由 barrier `cursor` 表达，绑定 causal frontier。语义同 Causal Barrier，见 [`overview/architecture.md` §3.4 / §6.3](./architecture.md) 与 [`sync/client-sync.md`](../sync/client-sync.md)。 |
| Lazy Link | 惰性链接 | 节点处理深度 Graph/Tree 查询遇到跨 Realm 引用时，截断返回的不解引用占位链接；跨域级联展示必须由有多域权限的客户端主动多次请求合成，节点 MUST NOT 越权自动化拼接外部图谱。定义见 [`overview/architecture.md` §6.5](./architecture.md)。 |
| Inception Key | 起源密钥 | DID 创建时的初始控制密钥，锚定在 DID 的 method history 中。 |
| Plaintext Visible Service | 明文可见服务 | Realm policy 显式声明可接收非加密私有内容或可逆派生摘要的服务。 |
| Audit Agent | 审计代理 | 在 auditable E2EE profile 中被 Realm policy 明确声明的服务/主体，按 `cx.audit.accessed` 等审计规则接收必要 key material 或明文访问证明；不得因持有 MLS key 而绕过 capability、plaintext-visible service disclosure 或用户可见提示。详见 [`../crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md)。 |
| History Visibility | 历史可见性 | 控制加入 Realm 后能看到多少历史事件的范围规则。 |
| Join Rule | 加入规则 | 控制 Actor 如何加入 Realm 的策略（public、invite、knock、restricted 等）。 |
| Native Personal Agent | 原生个人代理（canonical） | Controller 主动 provision 的 personal AI agent。wire 上使用 `actor_kind=agent`，持有独立 DID，作为一等 principal 参与协议；其 native 身份由 `cx.agent.provision` / `cx.identity.accountability_grant` / `cx.agent.key.authorize` 等 provisioning state 判定，而不是新增 `actor_kind` 枚举；详见 [`actor.md` §3.3](../models/actor.md)。`Personal Agent` 是 informative alias，prose 中遇到时应理解为 Native Personal Agent。 |
| Personal Agent | _informative alias_ | 非规范别名；canonical 术语为 **Native Personal Agent**。新增 normative 文本 MUST 使用 canonical 术语。 |
| Agent Runtime | Agent 运行时 | 执行 agent 业务逻辑的进程或容器；通过 `cx.account.agent_key_pair` pairing 持有 agent key。Agent Runtime 是部署单元，不是 protocol principal——principal 身份由 Native Personal Agent 或 Ghost Actor 承担。 |
| Ghost Actor | 幽灵 actor | Applet-managed actor，通常是外部网络用户、账号或 automation 在 Contrix 中的镜像。Ghost Actor 必须使用可审计的独立 Actor DID（`actor_id` 不带 DID URL fragment）；wire `actor_kind` 仍取 `user / org / team / agent / service / device / integration` 之一，外部人类/账号镜像 SHOULD 使用 `integration`，Applet 托管 AI/automation MAY 使用 `agent`。Ghost/native 差异由 Applet provenance、`accountable_principal_ids` / `accountability` 与 profile/capability 约束表达，不新增 `agent_ghost` 或 `ghost` enum。 |
| Member | 成员 | 已加入某 Realm 或 Circle 的 actor；具体由 membership cell `cx.component.member.state.v1` 中 `state=active` 的条目定义。Member 是 actor 在某个 security boundary 内的 membership 状态，不是独立主体类型。 |
| Subject | 授权对象 | Capability grant 的授予对象；`subject` 字段值是 DID（具体 principal）或 condition selector（如 role / actor_kind / federated trust scope）。具体使用约束见 [`common-fields.md` §4.1](../models/common-fields.md#41-did-适用边界)。 |
| participant | _local-context only_ | 不是通用术语。仅允许在 SFU stream binding、Mermaid sequence 图、call participant_id 等明确局部上下文出现；prose normative 段落 MUST 使用 actor / member / subject 视语义选用，不得用 `participant` 表达通用主体语义。 |
| Operation | 操作（canonical operation_id） | API wire-binding 抽象单元，由 canonical `operation_id` 标识；定义见 [`api-conventions.md` §2.4](../sync/api-conventions.md)。Operation 不等同于 wire event kind——前者是 RPC / sync 单元，后者是 reducer-input event family；MUST NOT 互换。 |
| Patch | 字段增量（`cx.patch.v1`） | `cx.patch.v1` field 增量 payload 格式，统一表达 canonical object 字段级更新；路径与 op 规则见 [`event-and-patch.md` §4](../models/event-and-patch.md)。新对象的字段更新槽 SHOULD 通过 Patch 表达，不再造单字段 update event。 |
| Push terminology layering | push / notification / notify / wakeup 词汇分层 | 四个词在 v1 严格分层，不互换：**Push** = transport 层（push gateway 投递）；**Notification** = projection object（`cx.notification` cell value，inbox 派生对象）；**Notify** = push rule action（`cx.push_rules` 的 action enum 值）；**Wakeup** = payload disclosure class（`cx.profile.push_gateway.blind_wakeup.v1` 等 wakeup 信封）。Normative prose MUST 按上述分层选词。 |
| Display naming | display_name / title 命名规则 | `display_name` 用于 actor / user-facing identity profile 以及 device record 的用户可读设备名（可变、UI-only，无唯一性约束）；`title` 用于结构对象 Realm / Space / Circle 的人类可读名（可变、无唯一性约束）。v1 内两个字段不互改；新增 wire 字段按对象类别选用，不得用 `name`、`device_label` 等别名替代（见 [`common-fields.md` §3](../models/common-fields.md)）。 |
| Home Realm | 主 Realm | 对象 `realm_id` 字段指向的 Realm；每个 object 有 exactly one home Realm，是该对象 metadata 授权、policy、capability、E2EE key 的根。Space、Flow、Message、Morph 等 canonical object 均通过 `realm_id` 解析 home Realm。 |
| Effective Default Realm | 有效默认 Realm | Space 在不同 hierarchy 层级 fallback 解析后得到的 default Realm，用于决定该 Space 下新建子资源（Flow / 子 Space 等）的默认 home Realm；解析规则见 [`space-hierarchy.md` §4](../models/space-hierarchy.md)。Wire 字段 `default_realm_id` 不动；Effective Default Realm 是 fallback 解析后的派生概念。 |
| Group (capability subject) | 大写 Group（授权主体集合） | 大写 **Group** 表示作为 capability grant subject 的 principal / actor 集合（即"一组主体被授予同一 capability"），与 **MLS group**（小写，MLS 加密会话）无关。当两者并列出现时，prose MUST 加限定词：`capability subject Group` vs `MLS group`，不得仅写裸 `group`。 |
| Provision vs Register vs Install | provision / register / install 用词分工 | 三者不互换：**provision** = principal 主体一等创建（如 `cx.agent.provision`），主体身份进入协议线；**registration** = service / applet 描述符接入（如 `cx.applet.registration`），描述符进入 directory / registry；**install** = client-side 软件安装（应用商店安装、桌面安装），**不**进入 wire。Normative prose 描述 protocol 主体生命周期时 MUST 使用 provision，不得写 "install agent"。 |
| backup_class | 密钥备份分类 | `cx.schema.key_backup.v1` envelope 的 class enum，v1 仅三类：`did_recovery`（DID inception key 恢复）、`secret_storage`（用户密钥 / passphrase 保护的备份）、`mls_history`（MLS group history secret 备份）。详见 [`key-management.md` §7](../identity/key-management.md)。注意：**`external` / `escrow` 不在 v1 backup_class enum 中**，MUST NOT 在 normative prose 中用作 backup_class 同义词或第四类标签。 |
| MLS KeyPackage | MLS 密钥包（durable event payload） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生对象：actor 预先公布、供他人将其加入 MLS group 的单次使用公钥材料。在 Contrix 中作为可声明 / 领取 / 消费 / 撤销的 durable event payload（`cx.mls.keypackage` 等）落地，并被 Realm-scoped claim 生命周期约束。prose 用 `KeyPackage`（PascalCase），wire 字段用 `keypackage_` 前缀（如 `keypackage_id` / `keypackage_digest`）。详见 [`encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md)。 |
| MLS Welcome | MLS 欢迎消息（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生消息，把新成员带入当前 epoch。Contrix 扩展：MUST 通过 durable `cx.mls.welcome` Event、durable encrypted pointer 或等价可 backfill 记录交付（Ephemeral Channel 不得是唯一路径）。prose 用 `Welcome`，wire 字段（如 `welcome_digest`）保持小写。详见 [`encryption-and-audit.md` §2.1](../crypto-media/encryption-and-audit.md)。 |
| MLS Commit | MLS 提交（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生 epoch 推进消息。Contrix 扩展：作为 `cx.mls.commit` durable Event 进入 Realm history，并 MUST 携带 `governance_binding`（GroupContext extension `cx_governance_binding`）把 governance frontier 哈希进 MLS transcript（见 MLS Governance Binding 行）。详见 [`encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md)。 |
| MLS Proposal | MLS 提案（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生提案消息（add / remove / update 等），由后续 Commit 落实。Contrix 中作为 `cx.mls.proposal` durable Event 传输；发送者 MUST 在事件自身 causal auth state 下满足对应 admin set 或成员 self-update 规则。详见 [`encryption-and-audit.md` §2.1](../crypto-media/encryption-and-audit.md)。 |
| ServiceDescribe | 服务描述响应（discovery / operation-response 契约） | 各 `/describe` 端点（`server/describe`、`directory/describe`、`applet/describe` 等）统一的 canonical 响应 shape（schema `cx.schema.service_describe.v1`，artifact [`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)）。它是 operation-response / discovery 契约，含 `service_did`、`trust_domain`、`service_type`、claim-level profile 分区、`plaintext_visibility` 等。详见 [`service-surface.md` §2.6](../sync/service-surface.md)。 |
| Policy Server | 策略服务（service role） | 对授权决策做集中评估并回签 bound decision 的服务角色；运行时 `service_type=policy_server`。它评估 Realm policy / capability 并签发绑定到 `realm_id` / `actor` / `action` / `request_canonical_digest` 的 decision。详见 [`policy-server.md`](../authz/policy-server.md)。 |
| Applet Server | Applet 服务（service role） | 承载受注册、受授权集成（applet describe / transaction / Ghost Actor / portal Realm / third-party lookup）的服务角色；运行时 `service_type=applet_service`，端点前缀 `/applet`、`/server`。属 extension profile，非 v1 core 互操作必需。详见 [`applet-integration.md` §3.1](../extensions/applet-integration.md)。 |
| MIMI Provider Facade | MIMI 提供方门面（service role / 扩展 profile） | 与外部 MIMI provider 互通时的可选服务角色；运行时 `service_type=mimi_provider_facade`，端点前缀 `/mimi`、`/.well-known/mimi-protocol-directory`。它是 **EXTENSION profile，不是 v1 core service surface**，可由 Principal Server、anchorer service 或 Applet Bridge 承载。详见 [`mimi-interop.md`](../extensions/mimi-interop.md)。 |
| Read Receipt | 已读回执（projection / 隐私信号） | 用户读取位置 / 隐私信号，用于 Flow timeline UI 提示（schema `cx.schema.read_receipt.v1`，artifact [`read-receipt.schema.json`](../../artifacts/schemas/read-receipt.schema.json)）。**不是** canonical truth、**不是** 多设备 cursor、MUST NOT 触发 push；可见性由 Realm policy 约束。与 Event Batch Receipt（投递 / commit ack）、Audit RYW Receipt（审计一致性证明）相区分。详见 [`read-receipts.md`](../discovery/read-receipts.md)。 |
| Audit RYW Receipt | 审计读己之所写回执（审计 / 一致性证明） | 由 Events API node、witness 或 peer Principal Server 签发，证明某 `cx.audit.accessed` envelope 已达 accepted 状态的 read-your-writes 回执（schema `cx.schema.audit_ryw_receipt.v1`，artifact [`audit-ryw-receipt.schema.json`](../../artifacts/schemas/audit-ryw-receipt.schema.json)）。它是审计 / 一致性证明（在 Audit Agent 释放明文前要求），区别于 Read Receipt（用户读位置信号）与 Event Batch Receipt（投递 / commit ack）。详见 [`audited-e2ee.md` §4.1](../crypto-media/audited-e2ee.md)。 |
| Applet | 集成单元（service role / 扩展） | 受注册、受授权、可审计的集成服务抽象（bot / bridge / automation）；EXTENSION，非 v1 core 互操作必需。每个写入仍需签名与 capability，namespace 只表示可声明 / 接收范围而非权限通过。详见 [`applet-integration.md`](../extensions/applet-integration.md)。 |
| Applet Bridge | Applet 桥接（部署形态） | Applet 承载外部网络互通（如 MIMI Provider Facade）时的桥接部署形态；属 extension，不是新增 protocol principal 类型。详见 [`applet-integration.md`](../extensions/applet-integration.md)。 |
| SFU | Selective Forwarding Unit（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：多人会议默认选择性转发后端（转发包不混流）。后端类型属 media plane，MUST 有 service DID 且由 Realm policy 显式允许；它不解密 E2EE 媒体、不获得 Realm 权限、不进入 MLS governance binding 信任路径。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| TURN | Traversal Using Relays around NAT（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：NAT 穿透中继。仅转发包、不获得 Realm 权限，对 E2EE 媒体明文不可见。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| ICE | Interactive Connectivity Establishment（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：候选连接建立框架（含 candidate / config 发现）。属信令 / 连接层，不影响 MLS governance binding，也不暴露 E2EE 媒体明文。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| MCU | Multipoint Control Unit（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：服务端混流后端。因混流通常需要明文媒体，故 **不可用于 E2EE 媒体**；若使用必须按 plaintext-visible service 在 Realm policy / profile 中披露，且不进入 MLS governance binding。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| MemberIdentity | 成员身份段（durable event payload） | Realm-scoped、actor-scoped 的完整 `member_identity` 段，由 `cx.member.identity.update` 以明文或加密封装携带（schema `cx.schema.member_identity.v1`，artifact [`member-identity.schema.json`](../../artifacts/schemas/member-identity.schema.json)）。wire scope = durable event payload；披露 `subject_id` 与 `display_profile` 供 Realm UI projection，handle 生命周期刻意排除。 |
| MemberDeliveryBindingCandidate | 成员投递绑定候选（builder-side 候选对象） | builder-side 候选对象，把 Handle resolution 输出或可信签发等价物送入 Realm member_add / invite 流水线（schema `cx.schema.member_delivery_binding_candidate.v1`，artifact [`member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json)）。它本身不是 wire fact；只有 reducer 依 Join Policy 独立复核后才物化为 Realm-scoped `member_delivery_binding`。详见 [`identity-handles.md` §3.7](../identity/identity-handles.md)。 |
| DeviceMessageEnvelope | 设备消息信封（to-device 队列消息） | 私有点对点设备消息封装（schema artifact [`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json)，title "Contrix Device Message Envelope"）。wire scope = to-device 队列消息（经 `cx.device_messages.put` / `.get`，account subscribe `to_device`），**不是** durable shared Realm Event，不进入 reducer / Anchor history。prose 用 `to-device`，类型用 `DeviceMessageEnvelope`。 |
| Account Data | 账户数据（actor-private account data） | actor-private 的个人偏好 / 状态类别（read marker、saved view personalization、通知偏好、个人 blocklist、agent draft / sidecar projection 等）。wire scope = account data（`wire_scope=actor_private_event`，encrypted account data 或 actor-private stream），MUST NOT 进入 shared Realm Move / Anchor history。详见 [`client-preferences.md`](../discovery/client-preferences.md)。 |
| to-device | 设备直投通道（ephemeral / to-device 队列） | prose 术语：发往特定设备的私有点对点消息通道；类型为 DeviceMessageEnvelope，wire path / 字段为 `device_messages` / `to_device`。wire scope = to-device 队列（非 durable shared event）。详见 [`transport-bindings.md`](../sync/transport-bindings.md)。 |
| Franking Proof | franking 证明（审核证据对象） | 服务在接收 E2EE 密文事件时生成的不可伪造收讫证明（`cx.moderation.franking_proof`），目标是：证明被举报密文确实对应某条已投递消息、保护举报者、并让审核方在无完整明文下也能验证。MUST 在 routing metadata、ciphertext digest、AAD digest、sender claim、接收服务 DID、接收时间与 `replay_nonce` 之上生成；MUST NOT 包含 plaintext body。详见 [`content-moderation.md` §3.4](../governance/content-moderation.md)。 |

## 3. 大小写与 wire 形态约定

本节给出术语在 prose 与 wire 形态间的 canonical 大小写规则。这些规则与 §1 的术语表维护规则叠加适用，不取代后者；§1 维护规则（canonical 唯一定义、别名标注、禁用词范围等）仍然有效。

通用规则（CC-04 / SA-05）：缩写在 prose 中 MUST 全大写（如 `E2EE`、`MLS`、`SFU`、`TURN`、`ICE`、`MCU`），在 wire 字段名 / profile ID / enum / schema key 中 MUST 保持 snake_case 小写。Contrix 服务角色专名（CC-05）在 prose 中 MUST 使用 PascalCase 专名（`Policy Server`、`Principal Server`、`Directory Server`、`Applet Server`）；泛指"某个 policy 服务"时小写普通名词可接受。

- **KeyPackage（CC-01）**：prose 引用 MLS KeyPackage 时 MUST 写 `KeyPackage`（PascalCase）；wire 字段保留 `keypackage_` snake_case 前缀（如 `keypackage_id` / `keypackage_digest`）。prose 中 MUST NOT 写 `key package`（带空格）或 `keypackage`（全小写）。
- **Welcome（CC-02）**：prose 引用 MLS Welcome 消息时 MUST 写 `Welcome`；字段名（如 `welcome_digest`）MUST 保持小写。
- **fail closed vs fail-closed（CC-03）**：动词短语用 `fail closed`（如 "Implementations MUST fail closed"）；形容词用连字符 `fail-closed`（如 "fail-closed default"）。
- **E2EE vs e2ee（CC-04）**：prose MUST 用 `E2EE`；profile ID / enum / schema key 保留小写 `e2ee`（如 `cx.profile.e2ee_client.v1`、`encryption_profile` 取值）。
- **服务角色专名（CC-05）**：见上方通用规则；命名 Contrix 服务角色用 PascalCase 专名。
- **to-device（CC-06）**：prose 术语写 `to-device`；schema / 类型名用 `DeviceMessageEnvelope`；wire path / 字段用 `device_messages` / `to_device`。
