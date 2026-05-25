---
title: 术语表
status: candidate
normative: true
stability: v1
updated: 2026-05-25
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

## 2. 核心术语

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 去中心化协作对象协议族，定义 identity、写入、同步、授权、显示与审计规则。 |
| Principal | 主体 | 协议中的稳定行为者身份；通常由 DID 标识，包含个人主体、组织、agent、Applet 等。 |
| Actor | 参与身份 | Principal 在 Realm 内的行为身份：执行动作、产生 Event、持有 profile 与 membership；可在不同 Realm 表现为 pairwise pseudonym。 |
| Organization | 组织 | 可治理主体的一类 Principal，通常由组织 DID 标识。 |
| Organization Governance | 组织治理 | 组织成员资格、控制策略、密钥、恢复与授权委派规则。 |
| Handle | 可路由人类地址 | 面向用户的可读入口，统一 canonical URI `contrix://<domain>/users/<localpart>`，显示形态 `@<localpart>:<domain>` 或 `<localpart>@<domain>`。可由 holder 自托管签发或 Organization / Principal Server / Directory 签发；解析结果含 `subject` DID，并 MAY 携带 `member_delivery_binding.recipient_service_did`，但只有物化为 Realm `delivery_binding` 后才成为投递路径。不可作为协议主体或授权主键。 |
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
| Space | 结构性分组对象 | 用户可理解的结构容器与导航节点（project、folder、board、list、泳道、calendar bucket、page group 等），ID 形如 `cx:space:`。永远没有自己的 membership / policy / E2EE group / federation policy；metadata 由 `realm_id` 指向的 home Realm 授权，子资源默认 Realm 由 `default_realm_ref` 解析。 |
| Space Hierarchy | Space 层级 | Space 之间通过 `parent_ref` + `cx.space.parent` 表达父子关系；可跨 Realm 做导航，但不传播 Realm membership、capability、history 或 E2EE key。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、邀请、组织页或精确链接发现。 |
| Flow | 协作主对象 | Realm 内承载协作议题、任务、正式表达与讨论轨道的标准对象。 |
| Flow primary track | Flow 默认入口 | 按 track primary 解析规则得到的默认 track；显式 `is_primary=true` 优先，未显式时标准 `synthesis` 优先。 |
| ~~Room~~ | _deprecated_ | 历史用语；v1 core model 不使用 `Room` 名词，请使用 `Flow discussion track` / `discussion track view`。`Room` 仅在 MIMI / Matrix interop 模块的明确互操作上下文中允许出现（参见 [`forbidden-model-terms.json`](../../artifacts/registry/forbidden-model-terms.json) `Room` 条目的 `allowed_contexts`）。 |
| synthesis track | 正式表达轨道 | Flow 的"synthesis"轨道，承载正式状态、结构化字段与决策正文。完整字段、profile、适用场景以 [`../models/flow-and-message.md` §4.2](../models/flow-and-message.md) 为准。 |
| discussion track | 讨论轨道 | Flow 的"discussion"轨道，承载消息与讨论时间线；成员、历史可见性和 E2EE 由 Flow 整体的 `scope_ref` 决定（`null`=Realm-default scope，否则=该 [Circle](../models/circle.md) scope）。Flow 单一 scope，不存在 per-track 安全边界。完整 profile 集合与适用场景以 [`../models/flow-and-message.md` §4.3](../models/flow-and-message.md) 为准。 |
| Circle | 信任圈 / 密码学子边界 | `cx:circle:` 对象，Realm 内的独立 MLS group + 子集成员 + 独立 history visibility 边界。**不**持有 federation identity 或 policy server（这些仍在父 Realm）。对象通过 `scope_ref` 引用 Circle 表达"窄于 Realm 的加密可见性圈"。详见 [`../models/circle.md`](../models/circle.md)。 |
| Circle scope / `scope_ref` | 对象加密 scope 引用 | 对象（Flow / Message / Morph / Space）的 `scope_ref` 字段；`null` = Realm-default encryption scope，否则指向同 Realm 的 Circle。Reducer 把它物化为 immutable tagged `effective_scope`，进入 Event envelope / E2EE AAD / Anchor leaf。 |
| effective_scope | 事件 immutable scope tag | Reducer 在每个 Event 接受时固化的 tagged scope（`{kind:"realm",realm_id}` 或 `{kind:"circle",realm_id,circle_id}`）。进入 envelope / AAD / sub-anchor leaf；后续 `scope_ref` 改绑不得重解释旧 event。 |
| Board | 看板 | `cx:space: kind=board`，组织一组 List Space 与其他 Space 的工作流容器。 |
| List | 列 / 泳道 | `cx:space: kind=list`，挂到 Board Space 下、承载 Flow 位置关系的列容器。 |
| Message | 消息对象 | 发生在 Flow discussion 轨道中的即时沟通与补充记录。 |
| Morph | 开放对象 | 标准对象扩展框架，承载非固定业务类型的可声明对象。 |
| Facet | 能力标签 | Morph/Profile 的能力提示（如 container/schedulable/renderable）。 |
| Relation | 关系边 | 对象间有向关系定义，如 `contains`、`mentions`、`depends_on`。 |
| Event | 协议事件 | 协议传播和验证的基础事实单元（Envelope 的内容承载形式）。 |
| Event Envelope | 事件外壳 | `event_id`、`actor_id`、`kind`、`payload`、`proofs` 等字段的签名封包。 |
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
| Inception Key | 起源密钥 | DID 创建时的初始控制密钥，锚定在 DID 的 method history 中。 |
| Plaintext Visible Service | 明文可见服务 | Realm policy 显式声明可接收非加密私有内容或可逆派生摘要的服务。 |
| Audit Agent | 审计代理 | 在 auditable E2EE profile 中被 Realm policy 明确声明的服务/主体，按 `cx.audit.accessed` 等审计规则接收必要 key material 或明文访问证明；不得因持有 MLS key 而绕过 capability、plaintext-visible service disclosure 或用户可见提示。详见 [`../crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md)。 |
| History Visibility | 历史可见性 | 控制加入 Realm 后能看到多少历史事件的范围规则。 |
| Join Rule | 加入规则 | 控制 Actor 如何加入 Realm 的策略（public、invite、knock、restricted 等）。 |
