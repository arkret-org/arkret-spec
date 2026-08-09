---
title: 术语表
status: candidate
normative: true
stability: v1
updated: 2026-07-30
see_also:
  - ../index.md
  - architecture.md
  - ../conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文集中定义 Arkret 规范中的核心术语。若其他文档使用同一术语，除非所在章节另有说明，以下定义优先于扩展实现约定。

本文中的英文术语保留为规范关键字；中文解释用于阅读，不能替代字段名、对象名或事件名。

术语表维护规则：

- 同一个 canonical 术语只定义一次；不要再添加“见上文”式重复行。
- 非规范别名可以保留为单独条目，但必须明确写出 canonical 术语，并说明新增 normative 文本应使用哪个术语。
- 禁用词、历史词和互操作上下文词应标注适用范围；不能把迁移期词汇重新引入 v1 core model。
- 局部上下文词（例如 SFU `participant_id`、Mermaid sequence `participant`）只在对应章节内有效，不升级为全局主体术语。
- **指针型条目（normative）**：若某术语条目显式声明其 canonical normative 定义下放到某专题文档（用"权威定义见 X §Y"、"单源 normative 定义在 X" 等措辞），则该条目本身只作术语指针，**不**承载该术语的 normative 约束，以被指向的专题文档为权威源。§1 第一段"以下定义优先于扩展实现约定"针对的是 glossary 自身给出完整定义的条目，不把指针型条目升格为权威定义源。
- crypto / governance 角色名词（`issuer` / `inviter` / `invitee` / `holder` / `notary` / `witness` / `controller` / `subject` 等）的总索引在 [`../models/common-fields.md` §4.3](../models/common-fields.md#43-角色名词登记索引)；本表条目仍是各角色的权威定义源，新增同类角色名词时应同步登记进该索引。

## 2. 核心术语

> **排序说明**：本表按术语**主题分组**排列（身份 / 边界对象 / 事件与同步 / 授权 / 服务角色等），便于按语义聚类阅读，**不是** canonical 对象序。canonical 对象清单及其权威顺序（Realm / Circle / Space（含 Board/List）/ Strand / Message / Relation / Morph / Event / View / Capability）以 [`index.md` §1](../index.md) 为准；§6 等引用对象集合时以该清单为锚点。

*Table 1. 术语表（normative）。本表行内的大写规范关键字（MUST / MUST NOT 等）具规范约束力；声明"以本条为单一锚点"的条目即为该约束的 canonical 权威位置。这是 [normative-language.md §4](../conformance/normative-language.md) 容器表默认 informative 规则的已登记例外。*

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Arkret | 协议名称 | 去中心化协作对象协议族，定义 identity、写入、同步、授权、显示与审计规则。 |
| kind 轴 | 协议自有分类轴 | Arkret 自有 discriminator、routing、registry family 与 reducer/lattice 分派字段；使用 `kind` / `*_kind(s)`。与外部 `type`、闭集 `class`、有序 `tier` 正交；权威判据见 [`common-fields.md` §2](../models/common-fields.md#2-类型记法)。 |
| type 轴 | 外部标准分类轴 | 只允许直接继承外部标准字段和值集并要求原样往返的分类；每个路径必须登记在 `classification-field-registry.json`，不得作为 Arkret 自有分派。与 `kind` / `class` / `tier` 交叉参照同上。 |
| class 轴 | 无序闭集分类轴 | 有限、无序、闭合且不选择互斥对象 shape 的分类；使用 `*_class(es)` 并必须解析到 finite value set。自由标签和开放 taxonomy 不属于 class。 |
| tier 轴 | 严格有序等级轴 | 有限且具有严格全序及比较语义的等级；使用 `*_tier`。v1 当前唯一协议字段是 `risk_tier`，顺序为 `low < medium < high`。 |
| protocol_version | 协议大版本字段 | wire-level 协议代际标识，canonical 字段值固定为字符串 `"1.0"`；它是 describe / 协商响应承载的 wire 版本。MUST NOT 写成 `1.0.0` 或 `v1.0.0`，也 MUST NOT 与发布 release tag（`v1.0.0`）互换填入对方位置。引用其格式与互换约束以本条为单一锚点，见 [`index.md` §5](../index.md)。 |
| release tag (`v1.0.0`) | 仓库发布线标签 | 规范仓库的发布 / release tag（语义化版本 `v1.0.0`），是文档 / artifact 发布维度的标识，**不**进入 wire。与 `protocol_version`（`"1.0"`）是两个不同维度，两者 MUST NOT 互换。详见 [`release-readiness.md` §2](./release-readiness.md)。 |
| Principal | 主体 | 协议中的稳定行为者身份；通常由 DID 标识，包含个人主体、组织、agent、Applet 等。 |
| Actor | 参与身份 | Principal 在 Realm 内的行为身份：执行动作、产生 Event、持有 profile 与 membership；可在不同 Realm 表现为 pairwise pseudonym。 |
| pairwise pseudonym / pairwise DID | 成对假名 / 成对 DID | 为降低跨 Realm 或跨服务关联性而按 scope 派生或选择的 DID 形态。它在给定 Realm、Strand track、service audience 或 profile 声明的 privacy scope 内作为 `actor_id` / routing identity 使用，但不自动披露 holder 的 principal DID；映射必须通过加密的 identity_link、claim disclosure、policy evidence 或 holder presentation 验证。Pairwise DID 仍是 DID，不能是非 DID 字符串；跨 scope 复用、与 principal DID 的可逆映射披露、以及授权归因规则由 minimal-metadata / identity profile 明确约束。 |
| Organization | 组织 | 可治理主体的一类 Principal，通常由组织 DID 标识。 |
| Organization Governance | 组织治理 | 组织成员资格、控制策略、密钥、恢复与授权委派规则。 |
| Handle | 可路由人类地址 | 面向用户的可读入口，统一 canonical handle `user:domain`，显示形态 `@<localpart>:<domain>` 或 `<localpart>@<domain>`。可由 holder 自托管签发或 Organization / Principal Server / Directory 签发；解析结果含 `subject` DID，并 MAY 携带 `member_delivery_binding.recipient_service_id`，但只有物化为 Realm `delivery_binding` 后才成为投递路径。Handle 不再是 base invite delivery 的安全关键路径；invite 使用 `invite_address + introduction_evidence`。不可作为协议主体或授权主键。 |
| Delivery Binding | 投递绑定 | Realm-scoped、actor-scoped 的投递路径权威来源：`delivery_binding.recipient_service_id` 决定该成员的明文 / 事件实际发往哪个服务，是安全相关的一等机制。由 reducer 依 Join Policy 复核 invite address / principal locator / 可选 `MemberDeliveryBindingCandidate` 等 evidence 后物化；`did_document_default`（DID Document 默认 Principal Server）只可在 join / rebind 时作为 Realm policy 允许的物化来源，binding accepted 之后 MUST NOT 再作为投递 fallback。字段、物化窗口与 fallback 约束的权威定义见 [`member-delivery-binding.md`](../governance/member-delivery-binding.md)。 |
| Connection Identifier | 连接标识角色 | 外部体系字符串（邮箱、手机号、通讯录用户名、外部账号 ID 等）在**发现 / 邀请 / consent 阶段**所扮演的角色；可见性默认关系私有，不得自动写入 DID Document、Realm history 或 grant subject。同一字符串经 holder 显式 disclosure 后可升格为 Handle。区分点是 holder 意图与可见性，不在字符串形态。 |
| Administrative Identifier | 管理标识角色 | 外部体系字符串（组织账号、计费账号、员工编号等）作为**组织本地管理标识**所扮演的角色；不出协议线，不得作为协议主体、grant subject 或 Event actor。 |
| Display Name | 显示名 | UI 展示用名称，可变且不可用于 ACL、grant、审计归因或发送者验证。 |
| Realm | 协作边界 | security/sync/auth/E2EE 边界。授权、policy、membership、history visibility、同步、加密、federation 都以 Realm 为根。`ak:realm:` 永远是边界，不承担产品导航树职责。底层只有一个 schema `ak.schema.realm.v1`；按用途分为 Principal Control Realm 与 Collaboration Realm 两类（见 [`models/realm-and-space.md` §2.8](../models/realm-and-space.md)）。 |
| Collaboration Realm | 协作 Realm（角色） | Realm 的一种用途，承载多方业务协作状态（Strand / Message / Space / Morph / Relation 等）。与 Principal Control Realm 互补。按是否含跨信任域成员再分 Internal / External 两类。 |
| Internal Collaboration Realm | 域内协作 Realm | Collaboration Realm 的一种：`federation_policy ∈ {closed, restricted}` 且成员仅来自本部署 trust domain。组织主网络上的普通项目 / 团队 Realm 默认属于此类。 |
| External Collaboration Realm | 跨域协作 Realm | Collaboration Realm 的一种：含跨信任域成员（external Organization DID / external principal）。Sovereign deployment 中其 policy 受 `ak.profile.sovereign_deployment.v1` 进一步约束（allowlist federation、独立 enclave、E2EE、deny-default applet/agent；见 [`sync/sovereign-deployment.md` §4](../sync/sovereign-deployment.md)）。 |
| Principal Control Realm | 主体控制 Realm（PCR） | Realm 的另一用途：与某 principal DID 1:1 绑定，承载该 principal 的身份基础设施事件（device / session / KeyPackage / recovery / profile / consent）。schema 层仍是 `ak.schema.realm.v1`：human / organization PCR 使用 `fields.purpose="principal_control"`，managed Agent PCR 使用 `fields.purpose="managed_agent_control"`；二者都以 `schema_refs` 含 `ak.profile.principal_control_realm.v1` 和事件类型 allowlist 与一般 Collaboration Realm 区分。详见 [`identity/key-management.md` §4.1](../identity/key-management.md)。 |
| Trust Domain | 信任域 | deployment / sovereign replay boundary，wire 形态为 `ak:trust_domain:<scope>`。它在 service describe、Realm create 和跨域 proof transcript 中绑定接收上下文；定义见 [`../identity/identity-did.md` §3.6](../identity/identity-did.md#36-trust-domain)。 |
| Official Realm | 官方边界 | 由组织或 policy 明确确认的 Realm；它是治理 / 安全声明，不等同于用户可见的 Space。 |
| Realm Link | Realm 关系边 | Realm 之间通过 `ak.realm.link` 表达的显式治理、发现、mirror、confidential extension、迁移等关系；不是 hierarchy，不默认级联权限或历史。 |
| Space | 结构性分组对象 | 用户可理解的结构容器与导航节点（project、folder、board、list、泳道、calendar bucket、page group 等），ID 形如 `ak:space:`。永远没有自己的 membership / policy / E2EE group / federation policy；metadata 由 `realm_id` 指向的 home Realm 授权，子资源默认 Realm 由 `default_realm_id` 解析。 |
| Space Hierarchy | Space 层级 | Space 之间通过 `parent_space_id` + `ak.space.parent` 表达父子关系；可跨 Realm 做导航，但不传播 Realm membership、capability、history 或 E2EE key。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、邀请、组织页或精确链接发现。 |
| Strand | 协作主对象 | Realm 内承载协作议题、任务、正式表达与讨论轨道的标准对象。 |
| Track | Strand 轨道 | Strand 内的**纯展示 / 时间线分段标识**：`Strand.tracks` map 的 key。TrackName 以 [`track-name-registry.json`](../../artifacts/registry/track-name-registry.json) 为 canonical 集合；`^[a-z][a-z0-9_]{0,63}$` 只是登记语法，未登记名称 fail closed。当前 active 名称为 `discussion` 与 `synthesis`。Track 不携带独立的 membership / 权限 / history visibility / E2EE——整个 Strand 共享单一 effective scope（由 `scope_circle_id` 决定）。默认入口按 track primary 解析规则得到（见 Strand primary track 条目）。详见 [`../models/strand-and-message.md` §4.4](../models/strand-and-message.md) 与 [`spec-map.md` §3.2](../spec-map.md)。 |
| Strand primary track | Strand 默认入口 | 按 track primary 解析规则得到的默认 track；显式 `is_primary=true` 优先，未显式时标准 `synthesis` 优先。 |
| synthesis track | 正式表达轨道 | Strand 的"synthesis"轨道，承载正式状态、结构化字段与决策正文。完整字段、profile、适用场景以 [`../models/strand-and-message.md` §4.2](../models/strand-and-message.md) 为准。 |
| discussion track | 讨论轨道 | Strand 的"discussion"轨道，承载消息与讨论时间线；成员、历史可见性和 E2EE 由 Strand 整体的 `scope_circle_id` 决定（`null`=Realm-default scope，否则=该 [Circle](../models/circle.md) scope）。Strand 单一 scope，不存在 per-track 安全边界。完整 profile 集合与适用场景以 [`../models/strand-and-message.md` §4.3](../models/strand-and-message.md) 为准。 |
| Circle | 子事件边界 / scoped 协作圈 | `ak:circle:` 对象，Realm 内的子集成员 + 独立 history visibility + 投递 / 查询 / projection 裁剪边界。**译名注意**：不要叫"信任圈"——Circle 不构成信任域，避免与 Trust Domain 混淆。**不**持有 federation identity 或 Policy Server（这些仍在父 Realm）。对象通过 `scope_circle_id` 引用 Circle 表达"窄于 Realm 的协作圈"；可按父 Realm floor 启用独立 MLS group。详见 [`../models/circle.md`](../models/circle.md)。 |
| Circle scope / `scope_circle_id` | 对象 effective scope 引用 | 对象（Strand / Space / Morph / Relation）的 `scope_circle_id` 字段；`null` = Realm-default scope，否则指向同 Realm 的 Circle。Message 不携带该字段，其 effective scope 从所属 Strand 派生。producer 将解析结果写入签名 `Event.scope_ref`，receiver 对冻结前态复核；MLS-backed scope 中同一值进入 E2EE AAD。 |
| `scope_ref` / effective scope | 签名 scope 与只读投影 | `Event.scope_ref` 是 producer 必填、proof 覆盖并由 receiver 验证的 immutable tagged scope。对象或 read projection MAY 暴露名为 `effective_scope` 的派生字段，但它不得替代、改写或晚于签名 scope 决定 Event 授权。 |
| Board | 看板 | `ak:space: kind=board`，组织一组 List Space 与其他 Space 的工作流容器。 |
| List | 列 / 泳道 | `ak:space: kind=list`，挂到 Board Space 下、承载 Strand 位置关系的列容器。 |
| Message | 消息对象 | 发生在 Strand discussion 轨道中的即时沟通与补充记录。 |
| Morph | 开放对象 | 标准对象扩展框架，承载非固定业务类型的可声明对象。 |
| Facet | 能力标签 | Morph/Profile 的能力提示（如 container/schedulable/renderable）。 |
| Relation | 关系边 | 对象间有向关系定义，如 `contains`、`mentions`、`depends_on`。 |
| Event | 协议事件 | 协议传播和验证的基础事实单元（Envelope 的内容承载形式）。 |
| Event Envelope | 事件外壳 | `event_id`、`actor_id`、`kind`、`payload`、`proofs` 等字段的签名封包。 |
| Wire Event | 线路事件 | 在协议 wire format 上实际传输、存储、同步、联邦并进入 reducer / 审计验证的 signed Event Envelope（schema `ak.schema.event.v1`，artifact [`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）。它是 v1 共享状态的唯一 wire fact；字段语义见 [`../models/event-and-patch.md` §2](../models/event-and-patch.md)。 |
| Wire fact | 线路事实 | 在协议线上以 canonical bytes + proof 承诺、可被接收方验证并作为 reducer / audit truth source 的规范事实。v1 不定义独立的 `wire_fact` 对象；除 Wire Event / Event Envelope 外，Operation、SDK builder / draft、receipt object 与 projection 都不是共享 wire fact，除非它们以 registered Event kind 的 payload 进入 Event Envelope。 |
| Signal Extension | 信号扩展 | 可选 encrypted-only live rail。presence、typing、read receipt 与 call signaling 的精确 kind、target 和内容位于 `SignalEnvelope.encrypted_payload`，外层只暴露 scope、sender、Seal basis 与三值 `signal_class`。它不进入 Event history、cell、Seal coverage、state_root 或 backfill。 |
| Signal（消歧） | 信号（消歧） | 本规范中未加限定的 “Signal” 一律指本协议的 Signal 平面（`SignalEnvelope` / `signal_class` / `ak.self.signal.*`）。引用同名即时通讯产品的设计时 MUST 使用全称并带产品限定，例如 “Signal SVR”、“Signal SealedSession”，不得写作裸 “Signal”。 |
| Kernel | 协议内核 | Arkret v1 的安全与收敛原语层，只包含 identity proof、scope/lifecycle、CBA、授权、MLS/key delivery、审计承诺、邀请与设备/账号安全。Kernel 不依赖 Collaboration Base 或任何 Extension。 |
| Collaboration Base | 协作基础包 | 官方基础协作层，包含 Strand、Message/Content、Relation、View 与 long text 等通用协作对象；依赖 Kernel，但不属于 Kernel。不得缩写为 CBA。 |
| Extension | 协议扩展 | 通过 Extension Manifest 声明 schema、reducer、action、transport rail、资源上限和 conformance vectors 的可选协议层。裸 “Extension” 仅表示本分层概念；产品扩展必须使用限定名称。 |
| Extension Manifest | 扩展清单 | 扩展装载、依赖闭包、隔离、资源约束与 conformance 绑定的唯一机器入口；它是签名声明性数据，不是可执行代码或 reducer DSL。 |
| Device Message | 设备消息 | 可靠的点对点设备队列消息，用于 key verification、secret 分发和 Realm key 请求。它使用 `DeviceMessageEnvelope`，既不是 Event 也不是 Signal。 |
| Event Store | 事件存储 | 保存 Event Envelope 的服务能力，不是协议真相源本身。 |
| Event Batch Receipt | 事件批次回执 | 可选审计/同步加速对象（payload schema `ak.schema.event_batch_receipt.v1`），**不是 canonical history**，也**不是 reducer input**；只对 issuer *选择* 承诺的事件集合提供 *integrity*，不提供 *completeness*。**wire-scope：仅为 receipt object 名称（`ak.event_batch_receipt`），不是 Event `kind`、不进入 `event-kind-registry.json`、不进 reducer**——与 Audit RYW Receipt 的"object + durable-kind 双形态"形成对照，命名分层的 normative 定义见 [`../models/event-and-patch.md` §5.1 概念分层](../models/event-and-patch.md)。数据面单事件"已看见"确认是其 `events[]` 单元素用法；只有具体 operation / profile 显式登记承载字段时，才能把该 receipt 作为响应证据。详见同文件 §5 与 [`../sync/operations-sync.md` §6.1](../sync/operations-sync.md)。 |
| Integrity (data) | 数据完整性 | 给定数据未被中间人或第三方篡改。集合上的 Merkle / set commitment 提供 integrity，但不保证集合本身已覆盖给定范围。 |
| Completeness (range) | 范围完整性 | 给定范围内（per-actor seq interval、frontier 上下界、actor / realm scope）**没有漏给**任何属于该范围的成员。Completeness 必须依赖 *range-bound* attestation（带显式 from/to 边界）+ witness quorum 或独立 seal 背书；set-bound commitment 单独不足以证明 completeness。 |
| Seal completeness_root | Seal 列集包络根 | 对已列控制面 digest 集合及其 actor-seq 包络作非缩 Merkle 承诺；混合 data/control actor 链中的未列 seq 不声明 plane，因此该 root 单独不构成 range completeness proof。扣发检测依赖 receipt obligation / inclusion list 与 range-bound attestation。 |
| Witness | 见证方 | 可对 frontier、range completeness、DID key-log 头部或 handover frontier 签发 attestation / receipt 的受信背书主体；可由 Principal Server、registry node 或独立 witness / receipt service 承担。Witness 不是 canonical truth 来源，不替代 Event 自身签名、Seal finality 或 reducer 验证；其签名只证明被见证的范围、头部或 frontier 在该 witness 视图中可验证。机制示例见 [`../sync/federation.md`](../sync/federation.md)、[`../sync/operations-sync.md`](../sync/operations-sync.md) 与 [`../identity/identity-did.md`](../identity/identity-did.md)。 |
| Range-bound Attestation | 范围完整性证明 | 携带 explicit range scope（per-actor seq interval、frontier 上下界）的签名证明，是 completeness 证明的载体。v1 已注册 active event kind `ak.attestation.range_completeness`（payload schema `ak.schema.range_completeness_attestation.v1`），详见 [`../sync/operations-sync.md` §6.4](../sync/operations-sync.md)。 |
| Snapshot | 快照 | 恢复/同步起点对象，包含某时刻 Materialized State 与 frontier。 |
| HLC | 混合逻辑时钟 | `HLC` 为 `clock` 排序标签，固定格式 `<unix_ms_hex(12)>-<logical_hex(4)>-<node_id_hash(8)>`（hex 字段宽度依次 12 / 4 / 8）；canonical 规则见 [`../conformance/encoding.md` §7](../conformance/encoding.md)。 |
| Cursor | 同步游标 | `ak:cursor:<base64url>` 形态的不透明 token，`purpose ∈ {stream, barrier}`；内部结构与验证规则的单一真相源见 [`../conformance/encoding.md` §8](../conformance/encoding.md)。 |
| Canonical JSON | 规范 JSON | 确定性 JSON 序列化格式，所有签名/哈希/对账输入必须使用；要求 UTF-8、key 排序、无空白、唯一 number 表示。 |
| View | 投影定义 | 查询 + kind + renderer + config 的共享可签名对象，定义“怎么看”。 |
| View.kind | 投影族类 | `collection / timeline / graph / document / composite`。 |
| Capability | 能力 | 授权语义与对象的绑定关系，授予 subject 执行特定 action。 |
| Capability Grant | 能力授权对象 | `ak:grant:` 标准对象（schema `ak.schema.capability.v1`）；记录谁在什么条件下可执行何动作。它与 `ak:capability:` 抽象 capability definition 引用不同。 |
| Policy | 策略 | 运行期约束对象，用于授权、密钥、留存、治理与安全边界。 |
| Invite | 邀请 | 邀请主体加入 Realm 或授予特定能力的标准对象/事件 payload。 |
| Principal Server | 主体服务 | 主体控制或委托入口服务，承载 events / account aggregate / snapshot / discovery 等核心 API。Realm 内实际投递目标由成员 `delivery_binding.recipient_service_id` 决定；DID Document 默认 Principal Server 只可作为 join / rebind 时被 policy 允许的 binding 来源，不是 Realm delivery fallback。 |
| Account Aggregate | 账号聚合 | Principal Server 对某 principal 的 actor-private 数据面聚合视图，聚合该账号跨 Realm 的 frontier 摘要、`to_device`、`account_data`、`device_lists` 与 notification / unread counts；通过 `ak.self.account.stream.subscribe`（`GET /_arkret/self/account/subscribe`）以 delta frame 推送。presence 是有界 TTL 的 encrypted Signal，走 Signal live rail，不进入账号聚合。它与「裸 Realm Event 查询面」（`ak.self.events.read.scan` / `ak.self.events.stream.subscribe`，逐 Realm 事件流）是不同的 selector / auth / freshness 边界，实现 MUST NOT 把二者合并为语义不明的单一 stream。中文统一译「账号聚合」。详见 [`sync/client-sync.md`](../sync/client-sync.md)。 |
| Sync Service | 同步服务 | 公开/订阅事件与 frontier 的受控同步能力，通常由 Principal Server 提供。 |
| Event Store Service | 事件存储服务 | 与 Sync Service 关联的持久化与检索服务角色。 |
| Blob Store | 二进制对象存储 | 附件、媒体、文件对象的存储与引用服务。 |
| Directory Server | 目录服务 | 提供可发现的 Realm、组织、actor、Applet 信息。 |
| Identity Resolution Infrastructure | 身份解析基础设施 | DID 文档、method resolver、密钥材料与验证链路。 |
| Auth Server | 认证服务（canonical, service role） | 负责登录因子验证（password / passkey / OIDC / SSO / recovery factor）、短期 `ak.session.grant` 签发与 session 生命周期管理的服务角色；profile `ak.profile.auth_server.v1`，运行时 `service_kind=auth_server`。它**不是协议身份根**，验证结果只证明某登录会话可绑定到某 DID principal / device，MUST NOT 替代 DID 控制证明或直接定义主体所有权。认证服务角色全规范 canonical 专名即 **`Auth Server`**（中文「认证服务」）；`Auth Service` / `认证服务器` 等写法 prose normative 段落 MUST NOT 用作另一术语，均应理解为 Auth Server 的别称。例外：`Auth Gateway` 及其中文 `认证网关` 专指 Auth Server 的**企业 SSO 部署形态**（见下行 Auth Gateway 条目），仅在描述该企业 SSO 形态时 MAY 使用；泛指认证服务角色时 MUST 用 canonical `Auth Server`，MUST NOT 用 `Auth Gateway` / `认证网关` 指代普通 Auth Server。详见 [`conformance/conformance-profiles.md` §9a](../conformance/conformance-profiles.md) 与 [`crypto-media/device-lifecycle.md` §1](../crypto-media/device-lifecycle.md)。 |
| Account Authority | 账号准入权威（canonical, service role） | 登录与账号准入的客户端可见服务角色：承载客户端可见的 `/_arkret/gate/account/*`（注册、`ak.session.grant` 签发 / 刷新 / 撤销 / 登出、device pairing、passkey/OIDC/SSO 结果换 grant、hard logout 内部编排）。客户端从 Principal Server 的 `/_arkret/describe`（`auth_metadata.account_authority`）发现它，之后所有客户端可见 gate/account 请求只发往该单一 `gate_account_base`。它与 **Auth Server** 的边界：Auth Server 只做登录因子验证与短期 grant 签发；Account Authority 是账号准入编排面，内部 MAY 委托 Auth Server 完成认证仪式，并在 split Auth-side hard logout 时通过标准 S2S `ak.gate.account.command.logout_auth_session` 终结 Auth-side session / grant chain（Auth Server 整体承载 Account Authority 时二者同 origin）。它与 **Principal Server** 的边界：个人部署通常二者同 origin，组织可由统一网关或独立前置承载。详见 [`sync/service-surface.md` §2.5](../sync/service-surface.md) Table 2-1 与 [`sync/api-conventions.md`](../sync/api-conventions.md)。 |
| Auth Gateway | 认证网关（Auth Server 的企业 SSO 部署形态） | Auth Server 的一种**部署形态**，不是独立服务角色：部署在企业内网 / 受控云端、把企业 IdP（Okta、Google Workspace 等 OAuth2 / OIDC）作为登录因子并由组织 DID 声明为 session grant issuer 的高安全网关。它继承 Auth Server 的全部约束（不是协议身份根、只签发短期受众绑定 `ak.session.grant`、不替代 `ak.device.authorize` / DID 控制）；对普通个人 DID SHOULD 只签发短期 session grant，不托管 principal signing key 或 recovery key。prose 提到该企业 SSO 形态时 MAY 使用 `Auth Gateway`；泛指认证服务时 MUST 用 canonical `Auth Server`。详见 [`crypto-media/device-lifecycle.md` §3](../crypto-media/device-lifecycle.md)。 |
| Device / Key Server | 设备 / 密钥服务（service role） | 承载 to-device 消息、one-time key、fallback key、MLS KeyPackage claim、device list 与 encrypted key backup metadata / ciphertext 的服务角色；E2EE profile 需要，个人部署通常内置于 Principal Server。服务角色一览（informative）见 [`sync/service-surface.md` §2.5](../sync/service-surface.md)；`service_kind` 机读真源见 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json)、namespace canonical 见 [`service-http-binding.md` §2.1](../sync/service-http-binding.md)；密钥备份语义见 [`identity/key-management.md` §7](../identity/key-management.md)。 |
| Push Gateway | 推送网关（canonical, service role） | 承载 push notification 分发的服务角色（`service_kind=push_gateway`）：把 Realm 事件唤醒转换为平台推送（APNs / FCM 等），profile 覆盖 blind wakeup（`ak.profile.push_gateway.blind_wakeup.v1`，不泄露内容）与 visible notification（`ak.profile.push_gateway.visible_notification.v1`）。作为 `plaintext_visible_services` 之一时其可见明文范围受披露义务约束。服务角色一览（informative）见 [`sync/service-surface.md` §2.5](../sync/service-surface.md)；`service_kind` 机读真源见 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json)；推送语义见 [`discovery/push-notifications.md`](../discovery/push-notifications.md)。 |
| Realtime Media Server | 实时媒体服务（canonical, service role） | 通话 / 会议的可选服务角色，提供 ICE config、TURN/STUN、SFU/MCU、录制策略与短期媒体凭证。它属 media plane，MUST 有 service DID 且由 Realm policy 显式允许；SFU 不解密 E2EE 媒体、不获得 Realm 权限、不进入 MLS governance binding，MCU 混流形态若用于 E2EE 必须按 plaintext-visible service 披露。媒体后端 canonical 专名即 **`Realtime Media Server`**。详见 [`sync/service-surface.md` §2.5](../sync/service-surface.md) Table 2-1 与 [`crypto-media/media-service-binding.md`](../crypto-media/media-service-binding.md)。 |
| Moderation Server | 审核 / 合规服务（canonical, service role） | 承载 report、审核队列、server ACL、policy list、appeal、legal hold / erasure workflow 的服务角色。canonical 专名为 **`Moderation Server`**；service-surface Table 2-1 表内别名为 "Moderation / Compliance Server"，仅在该表语境内使用，prose normative 段落 MUST 用 canonical 专名。公共或组织部署建议独立。服务角色一览（informative）见 [`sync/service-surface.md` §2.5](../sync/service-surface.md)；`service_kind` 机读真源见 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json)、namespace canonical 见 [`service-http-binding.md` §2.1](../sync/service-http-binding.md)；审核证据与流程见 [`governance/content-moderation.md`](../governance/content-moderation.md)。 |
| Archive / Recovery Service | 归档 / 恢复服务（service role） | history sharing、late key recovery 或组织恢复场景的可选服务角色（含 Archive Node、Key Recovery Service、Recovery Service）；高安全部署 MUST 显式声明。只能按 Realm policy、history visibility、T0 membership 与 capability 返回最小必要 epoch material / backup envelope / recovery proof，MUST NOT 因持有归档副本自动获得明文读取权。服务角色一览（informative）见 [`sync/service-surface.md` §2.5](../sync/service-surface.md)；`service_kind` 机读真源见 [`service-kind-registry.json`](../../artifacts/registry/service-kind-registry.json)、namespace canonical 见 [`service-http-binding.md` §2.1](../sync/service-http-binding.md)。 |
| Redaction | 清理/隐私裁剪 | 合法授权下对已发布事实做最小化可见性处理。 |
| Erasure | 物理擦除 | 在某个存储边界内对原始 payload、blob、派生内容的不可恢复删除；不同于 Redaction，它不保留正文。 |
| Causal Depth | 因果深度 | 事件在已知 DAG / prev_refs 中的深度值；只可用于 timeline 诊断或兼容投影，不参与协议状态 winner。 |
| Data Plane | 数据面 | 普通协作写入所在平面：消息、reaction、对象字段、排序、协作文本、计数等。DataEvent 签名与授权验证通过后按 Lattice / CRDT 本地接受；Seal 只可对其作观测承诺。 |
| Control Plane | 控制面 | 治理写入所在平面：membership、capability、policy、notary、lifecycle、MLS epoch、密钥治理，以及 schema 声明 `sealed=true` 的对象。Control Move 只有被 Seal 覆盖并进入控制面 `state_root` 后才 `sealed`。 |
| CBA | 控制面基线承诺封存 | `Control-plane Basis-committed Sealing` 的唯一缩写。DataEvent 按自身 `seal_ref` 验证，Control Move 按自身 `seal_basis` 验证并由 Seal 取得 finality。CBA 不表示 Collaboration Base。 |
| Authority Set | 权威集合 | 在某个 CBA basis 下决定 signer、quorum、delegation 与 revocation authority 的已接受 policy。wire 引用统一为 `{authority_set_id, authority_set_digest}`，不得只按可变名称解析。 |
| DataEvent | 数据事件 | 数据面 reducer-input Event；携带签名 `scope_ref`、`seal_ref` 与 `auth_context`，writes 由 kind + payload 派生。 |
| Control Move | 控制动作 | 控制面 reducer-input Event；携带签名 `scope_ref` 与 `seal_basis`，可携带 `preconditions[]`，writes 由 kind + payload 派生。 |
| CbaProofBundle | CBA 依赖证明包 | 不签名、不创建身份的 receiver-relative dependency bundle；携带目标 Seal、Control Move、inclusion proof 与 availability proof 的有界可验证超集。receiver 必须独立验签、重算 root 与 reducer 输出。 |
| AuthorizationLease | 授权租约 | 绑定 accepted CBA basis、主体、设备、scope、action、risk tier 与短期有效期的签名发布许可；它只能收窄既有授权，不能创建 capability。 |
| IngressReceipt | 入口签收回执 | ingress 对某个 Event digest 在 AuthorizationLease 有效期内到达的签名确认；不证明 reducer acceptance、投影可见性或 Seal finality。 |
| Control Proposal Ack | 控制提案签收 | 当前 authority set 对某个 exact Control Move proposal digest 的带签名签收（schema [`control-proposal-decision.schema.json`](../../artifacts/schemas/control-proposal-decision.schema.json) `$defs/control_proposal_ack`，wire `kind="signed_ack"`）。它固定首轮决议期限 `decision_due_at`、绝对期限 `absolute_due_at` 与 `authority_set_ref`，由 quorum 内每个真实 signer 的 Control Proposal Authority Ack（`authority_acks[]`）组装。**Ack 存在不等于 proposal 已被接受**：proposal 仍为 pending，只有 digest 被 accepted Seal 覆盖才获得控制面 finality；后续可能是 `signed_reject` 或 `signed_defer`。任何实现不得把它呈现为 accepted / approved / committed / sealed / finalized。它不是 IngressReceipt（网络到达）、不是 Event Batch Receipt（投递 / commit ack）、不是 Read Receipt（用户读位置信号），也不是任何 finality proof。详见 [`../authz/event-auth-state-resolution.md` §7.2](../authz/event-auth-state-resolution.md)。 |
| SecurityTransaction | 安全事务资源 | 可查询、可幂等续跑的闭合跨服务安全过程；v1 仅允许 RecoveryTransaction 与 SecurityRotationTransaction，不是通用 Saga/Plan DSL。 |
| RecoveryTransaction | 恢复事务 | 固定绑定 recovery session、DID entry、replacement device、authorize/reanchor Event 与 terminal receipt 的 SecurityTransaction。 |
| SecurityRotationTransaction | 安全轮换事务 | 固定绑定 revoke Event、新 secret commitment、backup series/envelope、active-series Event、erase confirmation 与 local commit 的 SecurityTransaction。 |
| Pending Control Move | 待确认控制动作 | Control Move 已通过格式、签名、basis、授权与 precondition 初检，但尚未被有效 Seal 覆盖。 |
| Rejected | 已拒绝 | Event / Seal 在格式、签名、schema、basis、precondition、授权、Lattice 或 `state_root` 校验上确定失败。 |
| Seal | 检查点锚点 | Ordering authority 对控制面的签名承诺；wire 组件以 `seal.schema.json` 为准，包括 `predecessor_refs`、`covered_control_event_ids`、`covered_control_event_digests`、`control_event_set_root`、`state_root`、`seal_policy_ref`、`sealed_at` 与 `proof`。它只 finalizes 控制面；数据面 root 是观测承诺。 |
| Genesis Seal | 创世检查点 | 某个 Realm 的 Seal DAG 根；它是唯一允许 `predecessor_refs=[]` 的 Seal，但 covered control set MUST 非空并原子覆盖完整 bootstrap unit。`ak.realm.create` 的五条 registered write 是 genesis intent、create 审计日志、founding notary、reducer profile 与 founding authority root cell（`ak.component.realm.authority_root.v1`）；profile、policy 与 creator membership 是同 unit 的独立签名 facet。v1 不含 founding `ak.capability.grant`。先接受空 Seal 再补 founding state 非法。它本身不是 Event，也不写入 cell。详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 与 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)。 |
| Seal DAG | 检查点图 | 某个 Realm 内已接受 Seal 形成的 DAG；多个 leaf 通过确定性 control view 合成。 |
| Cell | 状态单元 | Lattice 维护的最小协议状态键，形如 `ak:cell:<component>:<subject>`；其中 `<component>` 是原样嵌入的完整 `ak.component.<facet-path>.v<n>` Cell Family 标识符，因此 canonical 实例具有 `ak:cell:ak.component...` 双层 Arkret 限定。 |
| Lattice | 状态代数 | 每个 cell family 的确定性 join 规则；v1 active 类型为 `or_set`、`mv_register`、`cas_register`、`fsm`、`counter`、`ordered_log`。各类型的 join 语义与 bottom 行为以权威源 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 为准；未同时具备 join、op schema、profile gate 与 conformance vectors 的实现私有 CRDT 不属于 v1 wire lattice。 |
| Bottom | 底值 | Lattice join 无法给出合法 value 时返回的 `⊥`；`bottom=reject` 时依赖它的后续写入 fail closed，`bottom=expose` 时可投影为冲突诊断。 |
| Reset | 重置语义 | capability reset 使用 revoke + reissue；device identity recovery 使用 root re-anchor；cas_register / fsm 进入 `⊥` 后使用 conflict-recovery Control Move。正文使用 reset 时必须说明具体路径。 |
| Component / Cell Family | 组件 / Cell 族 | 跨协议版本稳定的 cell family 标识符，URI 形式 `ak.component.<facet-path>.v<n>`；registry 为 reducer-input kind 声明 `cell_family`、`lattice` 与 `bottom`。 |
| MLS Security Frontier Binding | MLS 密钥安全前沿绑定 | E2EE Realm 中把 MLS epoch 与会改变当前或历史密钥访问资格的 accepted state 强绑定的机制（兼容 profile id `ak.profile.mls_governance_binding.full.v1`，定义见 `crypto-media/encryption-and-audit.md §2.5`）。Commit 的 `governance_binding.security_frontier_digest` 进入 MLS transcript；active generation projection 记录 group、epoch、digest 与 Commit ref。 |
| Governance Binding Payload | 治理绑定 payload | 每个 `ak.mls.commit` 携带的闭合 payload（MLS GroupContext extension `mls_governance_binding`，codepoint `0xF1C0`），把唯一 `security_frontier_digest`、group/epoch 与 reducer profile 哈希进 MLS transcript。该 digest 只覆盖 membership、实际 MLS leaf key、MLS membership 和 encryption/history key-access policy，不覆盖普通 capability、metadata 或消息自身 `seal_ref`。 |
| MLS KeyPackage | MLS 密钥包（durable event payload） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生对象：actor 预先公布、供他人将其加入 MLS group 的单次使用公钥材料。在 Arkret 中作为可声明 / 领取 / 消费 / 撤销的 durable event payload（`ak.mls.keypackage` 等）落地，并被 Realm-scoped claim 生命周期约束。prose 用 `KeyPackage`（PascalCase）；单个 KeyPackage 的 identity/content 属性使用 `keypackage_` 前缀（如 `keypackage_id` / `keypackage_ref` / `keypackage_digest`），集合容器与批量引用使用 `key_packages` / `key_package_refs`。详见 [`encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md)。 |
| MLS Welcome | MLS 欢迎消息（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生消息，把新成员带入当前 epoch。Arkret 扩展：MUST 通过 durable `ak.mls.welcome` Event、durable encrypted pointer 或等价可 backfill 记录交付（Signal Extension 不得是唯一路径）。prose 用 `Welcome`，wire 字段（如 `welcome_digest`）保持小写。详见 [`encryption-and-audit.md` §2.1](../crypto-media/encryption-and-audit.md)。 |
| MLS Commit | MLS 提交（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生 epoch 推进消息。Arkret 扩展：作为 `ak.mls.commit` durable Event 进入 Realm history，并 MUST 携带 `governance_binding`（GroupContext extension `mls_governance_binding`）把 governance frontier 哈希进 MLS transcript（见 MLS Governance Binding 行）。详见 [`encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md)。 |
| MLS Proposal | MLS 提案（durable event） | [RFC 9420](https://datatracker.ietf.org/doc/html/rfc9420) 原生提案消息（add / remove / update 等），由后续 Commit 落实。Arkret 中作为 `ak.mls.proposal` durable Event 传输；发送者 MUST 在事件自身 causal auth state 下满足对应 admin set 或成员 self-update 规则。详见 [`encryption-and-audit.md` §2.1](../crypto-media/encryption-and-audit.md)。 |
| Notary Profile | 锚点 Profile | Realm create 时固定的 Seal finality profile：`single_did`、`threshold`、`open_set` 或 `mixed`。它只决定控制面 Seal 的签发与问责方式。 |
| Notary Cell | 锚定者 Cell | 定义下一批 Seal 由谁授权的 `cas_register + bottom=reject` cell；冲突时产生 Realm-wide Seal pause。 |
| Consent | 同意 | Holder-private 决策：“我同意接收来自 X 的某种非 Contact basis 动作”。表达为 consent Event 的签名 `kind + payload`，并由 registered reducer projection 写入 consent cell。Consent 可服务 invite 等非 Contact 路径，但不得参与 Contact-based create/send或Personal DM；后二者只读取双方 holder-signed directional Contact heads。 |
| Consent Scope | 同意范围 | Consent grant 适用的联系类型枚举：`invite` / `direct_message` / `voice_call` / `video_call` / `presence` / `any`。 |
| Contact Relation | 联系人关系 | Principal-scoped双边关系投影；request receipt(s)机械派生normal/glare basis，双方各自holder-signed directional lineage以scope replacement/tombstone演进。它不是`ak.contacts.*` account-data、`ak.relation.*`或consent cell，也不存在跨双方pair CAS。详见[`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md)。 |
| Direct Conversation | 1:1 私聊入口 | stable unordered participant pair的canonical DM入口，由唯一immutable `ak.direct_conversation.bound` fact绑定永久pair key、DM Realm与main Strand。leave/block/tombstone使其suspended但不创建successor；repair与new MLS generation始终复用原坐标。 |
| Reducer | 归约器 | 确定性纯函数，从 schema-validated `Event.kind + payload` 和 registry `cell_writes[].effect_projection` 派生 lattice writes，将 DataEvent 与已 sealed Control Move 归约为 cell values、控制面 `state_root`、bottom diagnostics 与产品 projection。 |
| Materialized State | 物化状态 | Reducer 输出的当前态对象，如 Strand、Relation、View。 |
| Frontier | 前沿 | Event、Actor、Seal 或查询范围已验证的最远同步边界。 |
| state_root | 状态根 | Seal 承诺的治理状态 authenticated root：Reducer 把已 sealed Control Move 的 registry-derived writes 归约为控制面 cell values 的可验证 root，由 Seal 的签名 transcript 承载。Event 的 `seal_basis` 只含 `leaves[]` 并通过所引 Seal 间接绑定该 root；不得把 root 复制进 basis。它是 capability / membership / policy inclusion proof 的锚点。单源 normative 定义在 [`../authz/event-auth-state-resolution.md` §6.2](../authz/event-auth-state-resolution.md)。 |
| epoch | 代际 | 单调递增的"代际"计数，按上下文落在三个语义簇，各有专题文档承载权威定义：(1) **MLS key epoch**——MLS group 每次 commit 推进的密钥代际，见 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)；(2) **授权 epoch pinning**——DataEvent `auth_context` 对 `key_epoch` / `credential_epoch` 的 pinning，见 [`../authz/event-auth-state-resolution.md` §4.1](../authz/event-auth-state-resolution.md)；(3) **history visibility epoch 边界**，见 [`../governance/history-visibility.md`](../governance/history-visibility.md)。本条仅作术语指针，不重复承载各簇规则；具体语义以对应专题文档为准。 |
| Causal Barrier | 因果一致性屏障 | 客户端或可选受托 projection 服务在返回查询结果前，依据本地 sync frontier 等待特定写入前沿到达的机制；用于保障 read-your-writes 体验。定义见 [`overview/architecture.md` §3.4](./architecture.md)。 |
| read-your-writes barrier | 读己之所写屏障 | Causal Barrier 在"读到自己刚提交的写入"这一场景下的别名；由 barrier `cursor` 表达，绑定 causal frontier。语义同 Causal Barrier，见 [`overview/architecture.md` §3.4 / §6.3](./architecture.md) 与 [`sync/client-sync.md`](../sync/client-sync.md)。 |
| Lazy Link | 惰性链接 | 节点处理深度 Graph / Space-hierarchy 查询遇到跨 Realm 引用时，截断返回的不解引用占位链接。其 normative 规则（截断行为、MUST NOT 越权自动化拼接外部图谱、跨域级联展示由有多域权限的客户端主动合成）单源定义在 [`overview/architecture.md` §6.5](./architecture.md)；本条仅作术语指针，不重复承载该规则。 |
| ReferenceProjectionState | 跨 Realm 引用投影状态 | Relation / View / Space hierarchy / Graph 查询展示跨 Realm 引用时使用的三值投影状态：`accessible`、`lazy_link`、`locked`。该状态只存在于 projection / response metadata，不写入 canonical Relation 对象；`locked` 与目标不存在、不可发现或 policy 拒绝必须不可区分。字段形态与安全约束见 [`relation.md` §4.2.1](../models/relation.md)。 |
| Identity Root | 身份根密钥 | DID method history 中逐代演进的冷控制密钥 `root_i`。它不进入 DID Document `verificationMethod`，不与任何设备、会话或业务密钥复用，只签 DID controller proof 与 PCR genesis / device re-anchor 两类锚事件。 |
| Plaintext Visible Service | 明文可见服务 | Realm policy 显式声明可接收非加密私有内容或可逆派生摘要的服务。 |
| Audit Applet | 审计 Applet | 在 auditable E2EE profile 中被 Realm / Circle 明确绑定的 applet / release service。它只作为控制面主体存在，不是 MLS 成员，不接收实时消息；若要访问历史材料，必须走 active `ak.audit.applet_binding.create/state` 投影、`ak.audit.session.*`、`ak.audit.release` 与 RYW receipt。详见 [`../crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md)。 |
| History Visibility | 历史可见性 | 控制加入 Realm 后能看到多少历史事件的范围规则。 |
| Join Rule | 加入规则 | 控制 Actor 如何加入 Realm 的策略（public、invite、knock、restricted 等）。 |
| Native Personal Agent | 原生个人代理（canonical） | Controller 主动 provision 的 personal AI agent。wire 上使用 `actor_kind=agent`，持有独立 DID，作为一等 principal 参与协议；其 native 身份由 `ak.self.agent.command.provision` / `ak.identity.accountability_grant` / `ak.agent.key.authorize` 等 provisioning state 判定，而不是新增 `actor_kind` 枚举；详见 [`actor.md` §3.3](../models/actor.md)。`Personal Agent` 是 informative alias，prose 中遇到时应理解为 Native Personal Agent。 |
| Personal Agent | _informative alias_ | 非规范别名；canonical 术语为 **Native Personal Agent**。新增 normative 文本 MUST 使用 canonical 术语。 |
| Agent Runtime | Agent 运行时 | 执行 agent 业务逻辑的进程或容器；通过 `ak.gate.account.command.pair_agent_key` pairing 持有 agent key。Agent Runtime 是部署单元，不是 protocol principal——principal 身份由 Native Personal Agent 或 Ghost Actor 承担。 |
| Ghost Actor | 幽灵 actor | Applet-managed actor，通常是外部网络用户、账号或 automation 在 Arkret 中的镜像。Ghost Actor 必须使用可审计的独立 Actor DID（`actor_id` 不带 DID URL fragment）；wire `actor_kind` 仍取 `user / org / team / agent / service / integration` 之一（不含 `device`），外部人类/账号镜像 SHOULD 使用 `integration`，Applet 托管 AI/automation MAY 使用 `agent`。Ghost/native 差异由 Applet provenance、`accountable_principal_ids` 与 profile/capability 约束表达，不新增 `agent_ghost` 或 `ghost` enum。 |
| Member | 成员 | 已加入某 Realm 或 Circle 的 actor；具体由 membership cell `ak.component.member.state.v1` 中 `state=active` 的条目定义。Member 是 actor 在某个 security boundary 内的 membership 状态，不是独立主体类型。 |
| Subject | 授权对象 | Capability grant 的授予对象；`subject` 字段值是 DID（具体 principal）或 condition selector（如 role / actor_kind / federated trust scope）。具体使用约束见 [`common-fields.md` §4.1](../models/common-fields.md#41-did-适用边界)。 |
| participant | _local-context only_ | 不是通用术语。仅允许在 SFU stream binding、Mermaid sequence 图、call participant_id 等明确局部上下文出现；prose normative 段落 MUST 使用 actor / member / subject 视语义选用，不得用 `participant` 表达通用主体语义。 |
| 3PID | 第三方标识符 | 邮箱、手机号等外部体系标识符在第三方邀请和认领流程中的具体形态。3PID 是 Connection Identifier 在邀请阶段的专门用法；公开 Event 中不得写入明文 3PID 或可枚举摘要。完整流程见 [`../sync/third-party-invites.md`](../sync/third-party-invites.md)。 |
| Operation | 操作（canonical operation_id） | API wire-binding 抽象单元，由 canonical `operation_id` 标识；定义见 [`api-conventions.md` §2.4](../sync/api-conventions.md)。Operation 不等同于 wire event kind——前者是 RPC / sync 单元，后者是 reducer-input event family；MUST NOT 互换。 |
| Patch | 字段增量（`ak.schema.patch.v1`） | `ak.schema.patch.v1` field 增量 payload 格式，统一表达 canonical object 字段级更新；路径与 op 规则见 [`event-and-patch.md` §4](../models/event-and-patch.md)。新对象的字段更新槽 SHOULD 通过 Patch 表达，不再造单字段 update event。 |
| Push terminology layering | push / notification / notify / wakeup 词汇分层 | 四个词在 v1 严格分层，不互换：**Push** = transport 层（push gateway 投递）；**Notification** = projection object（`ak.notification` cell value，inbox 派生对象）；**Notify** = push rule action（`ak.push_rules` 的 action enum 值）；**Wakeup** = payload disclosure class（`ak.profile.push_gateway.blind_wakeup.v1` 等 wakeup 信封）。Normative prose MUST 按上述分层选词。 |
| Display naming | display_name / title 命名规则 | `display_name` 用于 actor / user-facing identity profile 以及 device record 的用户可读设备名（可变、UI-only，无唯一性约束）；`title` 用于结构对象 Realm / Space / Circle 的人类可读名（可变、无唯一性约束）。v1 内两个字段不互改；新增 wire 字段按对象类别选用，不得用 `name`、`device_label` 等别名替代（见 [`common-fields.md` §3](../models/common-fields.md)）。 |
| Home Realm | 主 Realm | 对象 `realm_id` 字段指向的 Realm；每个 object 有 exactly one home Realm，是该对象 metadata 授权、policy、capability、E2EE key 的根。Space、Strand、Message、Morph 等 canonical object 均通过 `realm_id` 解析 home Realm。 |
| Effective Default Realm | 有效默认 Realm | Space 在不同 hierarchy 层级 fallback 解析后得到的 default Realm，用于决定该 Space 下新建子资源（Strand / 子 Space 等）的默认 home Realm；解析规则见 [`space-hierarchy.md` §4](../models/space-hierarchy.md)。Wire 字段 `default_realm_id` 不动；Effective Default Realm 是 fallback 解析后的派生概念。 |
| Group (capability subject) | 大写 Group（授权主体集合） | 大写 **Group** 表示作为 capability grant subject 的 principal / actor 集合（即"一组主体被授予同一 capability"），与 **MLS group**（小写，MLS 加密会话）无关。当两者并列出现时，prose MUST 加限定词：`capability subject Group` vs `MLS group`，不得仅写裸 `group`。 |
| Provision vs Register vs Install | provision / register / install 用词分工 | 三者不互换：**provision** = principal 主体一等创建（如 `ak.self.agent.command.provision`），主体身份进入协议线；**registration** = service / applet 描述符接入（如 `ak.applet.registration`），描述符进入 directory / registry；**install** = client-side 软件安装（应用商店安装、桌面安装），**不**进入 wire。Normative prose 描述 protocol 主体生命周期时 MUST 使用 provision，不得写 "install agent"。 |
| InstallPlan | Applet 安装计划 | `ak.self.applet.install.command.preview` 返回、`ak.self.applet.command.install` 重新计算并用 `plan_digest` 绑定的 canonical plan。机器契约为 `ak.schema.applet_install_plan.v1`（[`schemas/applet-install-plan.schema.json`](../../artifacts/schemas/applet-install-plan.schema.json)）；`plan_digest` 按 [`applet-schema.md` §1b](../extensions/applet-schema.md) 对省略自身后的 InstallPlan canonical JSON 计算。 |
| backup_kind | 密钥备份分类 | `ak.schema.key_backup.v1` envelope 的 class enum，v1 仅三类：`did_recovery`（root-generation metadata、guardian share metadata 或恢复服务证明；不含 recovery secret/root seed）、`secret_storage`（用户签名与账户密钥备份；新写入 SHOULD 优先 `recipient_method="recovery_public_key"`，`passphrase_kdf` 为合法但非首选路径，见 [`key-management.md` §7.5.1](../identity/key-management.md)）、`mls_history`（MLS group history secret 备份）。详见 [`key-management.md` §7](../identity/key-management.md)。注意：**`external` / `escrow` 不在 v1 backup_kind enum 中**，MUST NOT 在 normative prose 中用作 backup_kind 同义词或第四类标签。 |
| ServiceDescribe | 服务描述响应（discovery / operation-response 契约） | 各 `/describe` 端点（`server/describe`、`directory/describe`、`applet/describe` 等）统一的 canonical 响应 shape（schema `ak.schema.service_describe.v1`，artifact [`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json)）。它是 operation-response / discovery 契约，含 `service_id`、`trust_domain`、`service_kind`、claim-level profile 分区、`plaintext_visibility` 等。详见 [`service-surface.md` §3.0](../sync/service-surface.md)。 |
| Policy Server | 策略服务（service role） | 对授权决策做集中评估并回签 bound decision 的服务角色；运行时 `service_kind=policy_server`。它评估 Realm policy / capability 并签发绑定到 `realm_id` / `actor_id` / `action` / `request_canonical_digest` 的 decision。详见 [`policy-server.md`](../authz/policy-server.md)。 |
| Applet Server | Applet 服务（service role） | 承载受注册、受授权集成（applet describe / transaction / Ghost Actor / portal Realm / third-party lookup）的服务角色；运行时 `service_kind=applet_service`，端点前缀 `/applet`、`/server`。属 extension profile，非 v1 core 互操作必需。详见 [`applet-integration.md` §3.1](../extensions/applet-integration.md)。 |
| MIMI Provider Facade | MIMI 提供方门面（service role / 扩展 profile） | 与外部 MIMI provider 互通时的可选服务角色；运行时 `service_kind=mimi_provider_facade`，端点前缀 `/mimi`、`/.well-known/mimi-protocol-directory`。它是 **EXTENSION profile，不是 v1 core service surface**，可由 Principal Server、notary service 或 Applet Bridge 承载。详见 [`mimi-interop.md`](../extensions/mimi-interop.md)。 |
| Read Receipt | 已读回执（projection / 隐私信号） | 用户读取位置 / 隐私信号，用于 Strand timeline UI 提示（schema `ak.schema.read_receipt.v1`，artifact [`read-receipt.schema.json`](../../artifacts/schemas/read-receipt.schema.json)）。**不是** canonical truth、**不是** 多设备 cursor、MUST NOT 触发 push；可见性由 Realm policy 约束。与 Event Batch Receipt（投递 / commit ack）、Audit RYW Receipt（审计一致性证明）、Control Proposal Ack（控制面待决签收）相区分，也不是 IngressReceipt 或任何 finality proof。详见 [`read-receipts.md`](../discovery/read-receipts.md)。 |
| Audit RYW Receipt | 审计读己之所写回执（审计 / 一致性证明） | 由 Events API node、witness 或 peer Principal Server 签发，证明某 `ak.audit.release` 或其它 audit envelope 已达 accepted 状态的 read-your-writes 回执（schema `ak.schema.audit_ryw_receipt.v1`，artifact [`audit-ryw-receipt.schema.json`](../../artifacts/schemas/audit-ryw-receipt.schema.json)）。它是审计 / 一致性证明（在 attested release service 输出材料前要求），区别于 Read Receipt（用户读位置信号）与 Event Batch Receipt（投递 / commit ack）。**wire-scope：`ak.audit.ryw_receipt` 既是 receipt object 名，又是 `event-kind-registry.json` 中 `status="active"` 的 durable Event `kind`（object + durable-kind 双形态）**——与 Event Batch Receipt 的"仅 object"分层对照，见 [`../models/event-and-patch.md` §5.1](../models/event-and-patch.md)。详见 [`audited-e2ee.md` §6](../crypto-media/audited-e2ee.md)。 |
| Identity Receipt | 身份回执（identity registry / witness 证明） | DID identity registry node 或 witness 对某 DID key-log 头部状态（`head_event_digest` / `seq`）的签名回执（schema `ak.schema.identity_receipt.v1`，artifact [`identity-receipt.schema.json`](../../artifacts/schemas/identity-receipt.schema.json)，含 `did` / `seq` / `head_event_digest` / `registry_service_id` / `witness_role` 等字段）。用于让验证方确认 DID 文档 / key-log 的某一头部状态已被 registry / witness 见证；首次接受新 registry / witness key 或 binding 变化时按 [`did-usage-and-verification.md`](../identity/did-usage-and-verification.md) 验证，普通 receipt 验签复用 accepted key binding。区别于 Event Batch Receipt（投递 / commit ack）、Read Receipt（用户读位置信号）、Audit RYW Receipt（审计一致性证明）。详见 [`identity/identity-did.md`](../identity/identity-did.md)。 |
| Applet | 集成单元（service role / 扩展） | 受注册、受授权、可审计的集成服务抽象（bot / bridge / automation）；EXTENSION，非 v1 core 互操作必需。每个写入仍需签名与 capability，namespace 只表示可声明 / 接收范围而非权限通过。详见 [`applet-integration.md`](../extensions/applet-integration.md)。 |
| Applet Bridge | Applet 桥接（部署形态） | Applet 承载外部网络互通（如 MIMI Provider Facade）时的桥接部署形态；属 extension，不是新增 protocol principal 类型。详见 [`applet-integration.md`](../extensions/applet-integration.md)。 |
| SFU | Selective Forwarding Unit（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：多人会议默认选择性转发后端（转发包不混流）。后端类型属 media plane，MUST 有 service DID 且由 Realm policy 显式允许；它不解密 E2EE 媒体、不获得 Realm 权限、不进入 MLS governance binding 信任路径。详见 [`media-service-binding.md`](../crypto-media/media-service-binding.md)。 |
| TURN | Traversal Using Relays around NAT（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：NAT 穿透中继。仅转发包、不获得 Realm 权限，对 E2EE 媒体明文不可见。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| ICE | Interactive Connectivity Establishment（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：候选连接建立框架（含 candidate / config 发现）。属信令 / 连接层，不影响 MLS governance binding，也不暴露 E2EE 媒体明文。详见 [`webrtc-signaling.md`](../crypto-media/webrtc-signaling.md)。 |
| MCU | Multipoint Control Unit（external WebRTC 标准缩写） | 外部 WebRTC 标准缩写：服务端混流后端。因混流通常需要明文媒体，故 **不可用于 E2EE 媒体**；若使用必须按 plaintext-visible service 在 Realm policy / profile 中披露，且不进入 MLS governance binding。详见 [`media-service-binding.md`](../crypto-media/media-service-binding.md)。 |
| MemberIdentity | 成员身份段（durable event payload） | Realm-scoped、actor-scoped 的完整 `member_identity` 段，由 `ak.member.identity.update` 以明文或加密封装携带（schema `ak.schema.member_identity.v1`，artifact [`member-identity.schema.json`](../../artifacts/schemas/member-identity.schema.json)）。wire scope = durable event payload；披露 `subject_id` 与 `display_profile` 供 Realm UI projection，handle 生命周期刻意排除。 |
| MemberDeliveryBindingCandidate | 成员投递绑定候选（builder-side 候选对象） | builder-side 候选对象，把 Handle resolution 输出或可信签发等价物送入 Realm member_add / invite 流水线（schema `ak.schema.member_delivery_binding_candidate.v1`，artifact [`member-delivery-binding-candidate.schema.json`](../../artifacts/schemas/member-delivery-binding-candidate.schema.json)）。它本身不是 wire fact；只有 reducer 依 Join Policy 独立复核后才物化为 Realm-scoped `member_delivery_binding`。详见 [`identity-handles.md` §3.7](../identity/identity-handles.md)。 |
| Agent Sidecar | 个人 AI 私有工作区 | 独立 `ak:sidecar:` 对象与 native Sidecar scope，每个 `(realm_id, controller_id)` 至多一个；参与者恒为 controller + owned Agents，无 backing Circle、membership 或 private Strand 对象。详见 [`sidecar.md`](../models/sidecar.md)。 |
| eligible_sidecar_agent | Agent Sidecar 资格 predicate | `eligible_sidecar_agent(realm, controller, agent)` 派生 Sidecar desired access：controller 必须是目标 Realm active member；Agent 必须是 active Native Personal Agent、owned/accountable to controller，且 pairing / agent key / accountability grant / lifecycle / readiness / policy freshness 均有效；pause、deactivate、key revoke、`runtime_key_missing` / `pairing_open` readiness blocker 或 accountability grant 失效 MUST 使 predicate 立即为 false。详见 [`sidecar.md` §4](../models/sidecar.md)。 |
| DeviceMessageEnvelope | 设备消息信封（to-device 队列消息） | 私有点对点设备消息封装（schema artifact [`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json)，title "Arkret Device Message Envelope"）。wire scope = to-device 队列消息（经 `ak.self.device_messages.command.send` / `.get`，account subscribe `to_device`），**不是** durable shared Realm Event，不进入 reducer / Seal history。prose 用 `to-device`，类型用 `DeviceMessageEnvelope`。 |
| Account Data | 账户数据（actor-private account data） | actor-private 的个人偏好 / 状态类别（read marker、saved view personalization、通知偏好、个人 blocklist、agent draft / sidecar projection 等）。wire scope = account data（`wire_scope=actor_private_event`，encrypted account data 或 actor-private stream），MUST NOT 进入 shared Realm data/control history 或 Seal coverage。详见 [`client-preferences.md`](../discovery/client-preferences.md)。 |
| to-device | 设备直投通道（ephemeral / to-device 队列） | prose 术语：发往特定设备的私有点对点消息通道（正文写小写 `to-device`，章节标题 / title-case 写 `To-Device`，见 CC-06）；类型为 DeviceMessageEnvelope，wire path / 字段为 `device_messages` / `to_device`。wire scope = to-device 队列（非 durable shared event）。详见 [`transport-bindings.md`](../sync/transport-bindings.md)。 |
| Franking Proof | franking 证明（审核证据对象） | 服务在接收 E2EE 密文事件时生成的不可伪造收讫证明（`ak.moderation.franking_proof`），目标是：证明被举报密文确实对应某条已投递消息、保护举报者、并让审核方在无完整明文下也能验证。MUST 在 routing metadata、ciphertext digest、AAD digest、sender claim、接收服务 DID、接收时间与 `replay_nonce` 之上生成；MUST NOT 包含 plaintext body。详见 [`content-moderation.md` §3.4](../governance/content-moderation.md)。 |
| Degraded State / Error Code | 退化状态与标准错误码 | 跨实现必须一致解释的标准退化状态 / 错误标识（如 `decryption_pending`、`state_mismatch`、`projection_incomplete`、`unsupported_feature`、`unsupported_event_kind` 等）。其 canonical 取值、语义与逐项 `reason_code` 以 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 为单一权威来源；本术语表不重复枚举具体码值。 |
| soft_fail vs soft_deny | 临时失败与策略软拒绝 | `soft_fail` 是 authz / dependency / freshness 评估未能完成或需要重试的临时状态，不应被长期缓存为 policy decision；`soft_deny` 是 Policy Server 已评估后的软拒绝，通常表示 default client 不应提交或应降级，但不写入持久 moderation state。二者的 retry、cache 和 UI 处理 MUST 分离。 |

## 3. 大小写与 wire 形态约定

本节给出术语在 prose 与 wire 形态间的 canonical 大小写规则。这些规则与 §1 的术语表维护规则叠加适用，不取代后者；§1 维护规则（canonical 唯一定义、别名标注、禁用词范围等）仍然有效。

通用规则（本节 §3）：缩写在 prose 中 MUST 全大写（如 `E2EE`、`MLS`、`SFU`、`TURN`、`ICE`、`MCU`），在 wire 字段名 / profile ID / enum / schema key 中 MUST 保持 snake_case 小写。Arkret 服务角色专名（CC-05）在 prose 中 MUST 使用 PascalCase 专名；canonical 专名清单见下方 CC-05；泛指"某个 policy 服务"时小写普通名词可接受。

- **KeyPackage（CC-01）**：prose 引用 MLS KeyPackage 时 MUST 写 `KeyPackage`（PascalCase）。wire 命名是封闭的双层规则：单个 KeyPackage 的 identity/content 属性 MUST 使用 `keypackage_` 前缀（`keypackage_id` / `keypackage_ref` / `keypackage_digest`）；集合容器与批量引用 MUST 使用 `key_packages` / `key_package_refs`。不得创建其它 `keypackage_*` / `key_package_*` 变体。prose 中 MUST NOT 写 `key package`（带空格）或 `keypackage`（全小写）。
- **Welcome（CC-02）**：prose 引用 MLS Welcome 消息时 MUST 写 `Welcome`；字段名（如 `welcome_digest`）MUST 保持小写。
- **fail closed vs fail-closed（CC-03）**：动词短语用 `fail closed`（如 "Implementations MUST fail closed"）；形容词用连字符 `fail-closed`（如 "fail-closed default"）。
- **E2EE vs e2ee（CC-04）**：prose MUST 用 `E2EE`；profile ID / enum / schema key 保留小写 `e2ee`（如 `ak.profile.e2ee_client.v1`、`encryption_profile` 取值）。
- **服务角色专名（CC-05）**：命名 Arkret 服务角色用 PascalCase 专名。canonical 专名清单（prose normative 段落 MUST 使用左列；service-surface 表内别名仅在该表语境内允许）：

  | canonical 专名 | service-surface 表 / 别名形态 |
  | --- | --- |
  | `Principal Server` | — |
  | `Sync Service` | — |
  | `Event Store Service` | — |
  | `Blob Store` | — |
  | `Directory Server` | — |
  | `Auth Server` | `Auth Gateway`（企业 SSO 部署形态，见 Auth Gateway 条目） |
  | `Policy Server` | — |
  | `Applet Server` | — |
  | `Device / Key Server` | — |
  | `Realtime Media Server` | — |
  | `Push Gateway` | — |
  | `Moderation Server` | `Moderation / Compliance Server`（service-surface Table 2-1 表内别名） |
  | `Archive / Recovery Service` | Archive Node / Key Recovery Service / Recovery Service（同角色子形态） |
  | `MIMI Provider Facade` | — |
- **to-device（CC-06）**：正文 prose 写小写 `to-device`；**章节标题 / title-case 语境写 `To-Device`（连字符两侧首字母大写），句首可作 `To-device`**；schema / 类型名用 `DeviceMessageEnvelope`；wire path / 字段用 `device_messages` / `to_device`。
