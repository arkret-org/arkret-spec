---
ckp: CKP-0013
title: Contact & Direct Conversation Lifecycle — 把"加联系人 → 找他聊天"端到端定义在既有 consent / discovery / realm / flow 原语之上
normative: false
stability: v1
updated: 2026-06-04
status: draft
created: 2026-06-04
authors:
  - chris@acroidea.com
depends_on: []
merged_into: null
---

> **Status: draft.** 本提案尚未合入 normative spec。合入前 operation 注册以 `contract-catalog.json#operation_registry` 为准。
>
> 从 **[CKP-0012](./0012-account-and-contact-self-operations.md)** 分拆而来:0012 处理无歧义的 account self-service;联系人因横跨多个 normative spec、且与既有 consent 模型语义重叠,单列于此。

## 1. Summary

定义"**联系人**"这一产品概念在协议层的完整生命周期,**从加联系人(关系建立)一直到找他聊天(发起 1:1 直接会话)**,并把它**编排在既有协议原语之上**,而不是另起一套并行模型。

关键判断:Cokret 协议里"联系人 + 私聊"所需的零件**大部分已经存在**,但**没有一个端到端的 source of truth** 把它们串起来:

- **联系同意**:`consent-model.md` §5/§6(`consent_scope = direct_message / voice_call / video_call / presence / invite` + 发起前 gate);
- **可达发现**:`ck.directory.private_contact_discovery`(PSI 命中 + invite handoff stub);
- **会话承载**:1:1 DM Realm(目前靠"普通 Realm + 成员数=2 + `mls_dm` 加密 + `is_direct_message` metadata"拼出,无专门创建编排,见 push-notifications.md §、identity-handles.md §);
- **消息载体**:聊天没有独立"消息表"——Cokret 用 **Flow 的 `discussion` track** 统一承载会话(`Room` 已 deprecated,见 glossary;Message 必须挂在某 Flow 的 discussion 时间线,见 [`flow-and-message.md`](../zh/models/flow-and-message.md) §1)。私聊 = DM Realm 内一个 **discussion-primary 的 Flow**。

soland 的 `/_soland/self/contacts/*`(request / respond / list)是把这几块封装成产品化"联系人 API",yougen 硬编码调用之(见 [`yougen/src/api/account.rs`](../../../../yougen/src/api/account.rs))。本提案把这层编排提升为协议面,定义清楚"联系人"映射到哪些既有原语、谁是关系状态的 source of truth。

## 2. Motivation

### 2.1 现状是碎片,不是空白

"加联系人之后找他聊天"今天能跑,但它分散在四份 normative spec 里,没有任何一处定义这条端到端流程:

1. Bob 发现 Alice 可达 → `ck.directory.private_contact_discovery`。
2. Bob 想联系 Alice → 受 `consent-model.md` §6.1 gate:`require_explicit_consent` profile 下 invite 被 reject 直到 Alice 显式同意;default profile 下进 Alice 的"陌生人邀请" quarantine inbox(**这已经是 request/respond 双边握手**)。
3. Alice 同意 → consent cell 记 `(peer=Bob, consent_scope=direct_message|invite)` active dot。
4. Bob 发起私聊 → 创建 1:1 DM Realm(成员数 2 + `mls_dm` + `is_direct_message`),走通用 MLS 建群 + KeyPackage claim。
5. 聊天 → 普通 `ck.message.create` Flow。

问题:**第 2–4 步之间没有 canonical 编排**。"Bob 和 Alice 是不是联系人"这个状态既能从 consent cell 推、又能从是否存在共享 DM Realm 推、还能从 soland 私有 `contacts` 表推——**三个来源,无权威**。通用客户端无法回答"列出我的联系人"而不绑定某实现。

### 2.2 与既有 `ck.contacts.*` / `ck.relation.*` 撞名、撞概念

协议中已有两个名字/语义相近的结构,联系人关系是**第三层**,三者 MUST 不混用(见 §3.1)。不澄清三层边界,实现必然误用。

## 3. Specification

### 3.1 三层关系模型(先钉死边界)

| 层 | 标识 | 作用域 | 语义 | 状态机 |
| --- | --- | --- | --- | --- |
| L1 holder-private 备注 | `ck.contacts.actor.<did>` account-data(**已存在**) | holder 本地私有(encrypted account-data) | 对某 DID 的 remark / tag / pin,**单边、不通知对方** | 无;`ck.account_data.set` 覆写 |
| L2 协作图关系 | `ck.relation.*`(**已存在**) | **Realm 内**(`realm_id` 必填) | Flow/Space/Message/Actor 间协作图边 | `active` / `tombstoned`,无双边握手 |
| **L3 联系人关系(本提案)** | `ck.contact.*` | **principal 级、跨 Realm**(不归属任何 Realm) | actor↔actor 社交关系,**双边握手** | `pending → accepted / rejected → tombstoned` |

不复用 L2:relation `realm_id` 必填、`relation_kind` 闭合注册表无 `contact`、状态机无 pending→accepted;联系人无自然归属 Realm 且需双边同意(见 [`relation.md`](../zh/models/relation.md) §2、§4)。不复用 L1:account-data 是单边私有偏好,无法表达"对方已接受"。

> **命名消歧**:operation id `ck.contact.*`(单数)与 account-data key `ck.contacts.*`(复数)字面极近,catalog `description` MUST 显著标注区别。

### 3.2 联系人关系生命周期 operation

| operation | HTTP | Body | 说明 |
| --- | --- | --- | --- |
| `ck.contact.request` | `POST /_cokret/self/contacts/request` | `{ target: did, scope?: string }` | 发起 pending 关系;`scope` 对齐 consent_scope |
| `ck.contact.respond` | `POST /_cokret/self/contacts/respond` | `{ requester: did, action: "accept"\|"reject" }` | 应答 |
| `ck.contact.list` | `GET /_cokret/self/contacts` | — | 列举当前 actor 的联系人及关系状态 |
| `ck.contact.tombstone` | `POST /_cokret/self/contacts/tombstone` | `{ contact: did }` | 终止关系 |

全部 `user_session`,落 `/_cokret/self/contacts/*`。

**与 consent 模型的关系(本提案最核心的设计决策,见 §6 Q1)**:`ck.contact.request/respond` 在语义上**几乎等同**于 `consent-model.md` §6.1 的 invite/consent 双边握手。本提案的立场是:**contact 是 consent 之上的一个具名、可列举的关系视图**,而非平行机制——`ck.contact.request` SHOULD 编译为既有 consent grant Move,`ck.contact.list` SHOULD 是对 holder consent cell + 既有关系事实的投影。是否需要独立的 contact 状态存储(而非纯投影)取决于 Q2。

### 3.3 Direct conversation(找他聊天)编排

定义 contact accepted 之后发起 1:1 会话的 canonical 步骤,**全部复用既有原语**,本提案只补"编排契约 + DM Realm 的 well-known 形态":

1. **前置 gate**:发起方 MUST 满足目标 `consent_scope=direct_message`(consent-model §6.2)。
2. **DM Realm 解析或创建**:1:1 DM Realm 是 well-known 形态——`member_count=2`、`encryption_profile=mls_dm`、metadata `is_direct_message=true`。**同一对 (A,B) 至多一个 active DM Realm**(去重 key `unordered_pair(A_did, B_did)`),避免重复建群。
3. **MLS 建群**:走既有 `ck.self.keys.keypackages.claim` + MLS group create(无新原语)。
4. **DM 主 Flow 解析或创建**:聊天消息必须挂在 Flow 的 discussion track(`flow-and-message.md` §1),因此 DM Realm 内 MUST 有一个 **well-known 的 discussion-primary Flow** 承载主聊天时间线。**同一 DM Realm 至多一个 active 主 Flow**(避免"一个私聊出现两条时间线");DM Realm 内 MAY 另有普通 Flow(把某个话题升级成独立议题),但默认聊天落主 Flow。
5. **消息**:`ck.message.create` 落该主 Flow 的 discussion track。

> 现状缺口:第 2 步的"well-known DM Realm 形态 + 去重不变量"、第 4 步的"DM 主 Flow well-known 约定"今天都只在 push-notifications.md / identity-handles.md / flow-and-message.md 被**间接**支撑,无 canonical 定义把它们串成"私聊"。本提案把这两层钉死(见 §6 Q3)。

### 3.4 对话 Flow 的 `stage`:允许为空

Flow 的 `stage`(`draft / proposed / planned / in_progress / blocked / done / cancelled / superseded`)是**工作项进度**语义,对两人私聊不适用——对话不是一件"有进度、会完成"的事。

**决定:对话类 Flow(DM 主 Flow 及一般 conversation-profile Flow)的 `stage` 允许为空(省略)。**

代价(必须在 §4 标明):`stage` 在 [`flow-and-message.md`](../zh/models/flow-and-message.md) §3 当前是**硬必填、无默认值**。本决定要求 normative 为对话类 Flow 开一个 **profile-gated 例外**——在 conversation profile 下 `stage` 可省略,reducer 不再对该类 Flow 强制 `stage` 必填;非对话 Flow 维持原必填约束不变。**不**改成全局可空(会松动所有工作项 Flow 的不变量)。空 `stage` 在投影 / UI 上表示"无进度语义",不参与 stage bucket 聚合。

## 4. Interactions with normative spec

- `zh/identity/consent-model.md`:§5 consent_scope、§6 invite/contact gate — contact operation 与之的 source-of-truth 关系(Q1)。
- `zh/discovery/discovery-directory.md`:`private_contact_discovery` 作为发现入口。
- `zh/models/realm-and-space.md`:DM Realm well-known 形态与去重不变量(新增小节)。
- `zh/models/flow-and-message.md`:§1 Message 必挂 Flow discussion track(私聊载体);§3 **`stage` 必填约束需为 conversation profile 开 stage-optional 例外**(§3.4),DM 主 Flow well-known 约定。
- `zh/models/relation.md` / `account-data-type-registry.json`:三层边界澄清,避免与 L1/L2 混用。
- `zh/crypto-media/encryption-and-audit.md` / `identity-handles.md`:`mls_dm` 加密形态。
- artifacts:`contract-catalog.json` operation_registry(+`operation-registry.json`)、OpenAPI、`operations-error-mapping.json`(contact 状态机错误)。
- 是否需要新 event_kind / 新 forbidden-wire 守卫:取决于 Q2。

## 5. Rationale & alternatives

- **备选 A:纯产品面,不进协议**(维持 soland `/_soland/self/contacts/*`)。否决理由:通用客户端无法跨实现回答"我的联系人",正是 0012/0013 要消除的耦合债。
- **备选 B:做成 L2 `ck.relation.*` 的一个 relation_kind**。否决理由:破坏 relation 的 Realm-scoped 不变量(§3.1)。
- **备选 C:完全等同 consent,不要 contact 这层**。部分采纳——contact 确实应建在 consent 之上(§3.2),但 consent cell 不提供"具名、可列举、带 DM 入口的关系视图",故仍需 contact 投影/编排层。

## 6. Open questions

- [ ] **Q1(核心)** contact 关系的 source of truth:是既有 **consent cell 的投影**(contact.request == consent grant Move),还是**独立的 contact 状态**?倾向"consent 之上的投影 + DM 编排",但需确认 consent cell 能否承载 pending/rejected/tombstoned 全状态机。
- [ ] **Q2** contact 关系事实是否进 **principal 级 signed log**(可被对端 / 多设备验证的双边事实、可移植),还是纯 server-side projection?进 signed log 需定义新的 principal-scoped fact kind 与其 reducer/可见性。明确排除 Realm `ck.relation.*`。
- [ ] **Q3** 1:1 私聊的两层 well-known 形态是否钉死、落哪:(a) DM Realm 形态 + `unordered_pair` 去重(§3.3 第 2 步);(b) DM 主 Flow 的 well-known 约定 + 单一主时间线不变量(§3.3 第 4 步,因 Message 必挂 Flow discussion track)。落 `realm-and-space.md` + `flow-and-message.md` 还是单独 binding?
- [ ] **Q4** `ck.contact.*`(单数)与 `ck.contacts.*`(复数 account-data)命名消歧:是否改名以彻底避免混淆?

## 7. Migration plan

> draft 阶段 placeholder。accepted 后再展开迁入 normative 的 PR 顺序(预计:先定 Q1/Q2 → consent-model 增补 → realm-and-space 增补 DM 形态 → catalog 注册 contact operation → soland/yougen/cotest 迁移)。

## 8. References

- 姊妹提案:[CKP-0012 Account Self-Service Operations](./0012-account-and-contact-self-operations.md)(分拆来源)。
- `zh/identity/consent-model.md`、`zh/discovery/discovery-directory.md`、`zh/models/relation.md`、`zh/models/realm-and-space.md`。
- 下游:[`yougen/src/api/account.rs`](../../../../yougen/src/api/account.rs)(`_soland/self/contacts/*` 硬编码现状)。
