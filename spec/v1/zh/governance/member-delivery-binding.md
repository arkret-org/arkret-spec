---
title: Member Delivery Binding
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - join-policy.md
  - ../sync/federation.md
  - ../identity/identity-handles.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> 本文从 `join-policy.md` 拆出。**成员投递绑定（delivery binding）与 join gate 正交**：join gate（见 [`join-policy.md`](join-policy.md)）决定"能否加入"，delivery binding 决定"加入后 events / sync / to-device / push / key-package 投递到哪个 Principal Server"。两者方向、生命周期、授权来源均不同，MUST NOT 互相推导。

## 1. 成员投递绑定

`ck.member.state{membership="join"}` 表达的是某个 DID 在该 Realm 中成为成员；它**不等价于**"按该 DID 的全局 home Principal Server 投递"。Realm-scoped events / account aggregate / to-device / push / key-package 的实际投递目标由该成员的 **effective delivery binding** 决定。本文是 v1 normative。

## 2. 接受准则（normative）

任一 `ck.member.state{membership="join"}` Control Move 被 reducer 接受前 MUST 满足：

1. `payload.delivery_status ∈ {routable, unroutable}` 显式声明。
2. `delivery_status="routable"` 时 `payload.delivery_binding` 必填，且其 `binding_source` 在 Realm `ck.component.realm.delivery_binding_policy.v1`（§4）的 `allow_binding_sources` 集合内。
3. `delivery_status="unroutable"` 仅当 Realm policy 显式允许（`allow_unroutable_membership=true`）。
4. `delivery_binding.recipient_service_did` 出现在 Realm policy 的 `allowed_recipient_services` 集合内，或该 policy 显式声明哨兵 `["*"]`（unrestricted）；否则 MUST 被 `required_endorsers` 中至少一个治理 DID 通过 `service_acceptance_ref` 引用的 acceptance Event 背书。**`allowed_recipient_services` 为空集 `[]` 时 = 拒绝（fail-closed，见 §4 字段表）**：既未命中 allowlist、又未声明 `["*"]` 哨兵、又无 `required_endorsers` 背书时，reducer MUST 拒绝该 routable join（`delivery_binding_policy_mismatch`），不得把空集解释为"不限"放行。
5. `delivery_binding` 的 `binding_source`-conditional required 字段满足 [`event-payload.schema.json#/$defs/member_delivery_binding`](../../artifacts/schemas/event-payload.schema.json)（例如 `did_document_default` MUST 含 `did_document_digest`；`explicit` / `invite` / `organization_policy` MUST 含 `service_acceptance_ref`；policy-driven source MUST 含 `policy_event_ref`）。
6. `delivery_binding.delivery_modes` 是该 binding 的**显式**模式集合；空集合或缺失等价于 schema violation。普通"全功能"成员 SHOULD 列出 `["events", "sync", "to_device", "push", "key_packages"]`。

reducer 校验上述任一条失败 MUST 拒绝该 Control Move 并返回 `delivery_binding_invalid`，**不得**降级为部分接受。

声明可加入 unroutable member Realm 的客户端 profile SHOULD 在 join / accept UI 中披露："该 Realm 仅向本地可见，不接收服务端推送、同步、to-device、push 或 KeyPackage 投递"。该披露是客户端 profile 义务，不参与 reducer 接受条件；reducer 的可验证判据仅为上述 policy 和 payload 条件。

注意：`payload.delivery_binding` / `member_delivery_binding.recipient_service_did` 描述的是成员加入后接收 events、sync、to-device、push、KeyPackage 的目标 Principal Server；`join_candidates[]` 描述的是本次 join / invite-accept / knock material 可提交到哪些 Realm ingress service。两者方向不同、生命周期不同、授权来源不同。Join builder 和 reducer MUST NOT 从 `join_candidates[].service_did` 推导成员 `delivery_binding`，也 MUST NOT 从成员 `delivery_binding.recipient_service_did` 推导 Realm ingress candidate。

## 3. `binding_source` 与责任方

> **默认 allowlist 警示（normative）**：下表列出 6 类 `binding_source`，但**并非默认全部可用**。未配置 `ck.realm.delivery_binding_policy`（§4）时，`allow_binding_sources` 默认仅含最弱来源 `did_document_default`（见 §4 字段表）。组织 / 合规 Realm MUST 显式收窄 `allow_binding_sources` 并把 `allow_did_document_default` 设为 `false`，否则成员可凭 DID Document 默认条目自行决定投递目标，绕过治理背书。

| `binding_source` | 谁负责填 | 何时使用 | 补充必填 |
| --- | --- | --- | --- |
| `explicit` | 邀请方 / 管理员客户端 | 用户显式选择目标服务 | `service_acceptance_ref` |
| `did_document_default` | 客户端 DID resolver | Realm policy 允许 fallback，未匹配其它来源 | `did_document_digest` |
| `invite` | 邀请方 builder | 邀请 token 已携带 binding | `service_acceptance_ref` |
| `join_policy` | reducer 由 Join Policy 推导 | Join Policy 的 gate / role 决定目标服务 | `policy_event_ref` |
| `organization_policy` | 组织治理目录 | invitee 是 Org 员工，组织 policy 指定目标 | `service_acceptance_ref` + `policy_event_ref` |
| `realm_policy` | Realm policy 默认值 | Realm 声明 default recipient | `policy_event_ref` |

所有六类来源都要求 `resolved_at`；任何 `binding_source` 进入 canonical Event 时，**结果 MUST 已在客户端 / 提交服务侧解析完成**，不得留"运行时再 resolve"的隐含状态。

### 3.1 邀请 / 成员添加输入

客户端 MAY 提供两类成员添加输入：

1. **基础路径**：显式 `invite_address`、online `principal_locator` 或其它 [`invite-addressing.md`](../sync/invite-addressing.md) 定义的 `introduction_evidence`。该路径不依赖 handle resolve。
2. **可选辅助路径**：邀请方输入 `@alice:acme.example`、`alice@acme.example`、`alice:acme.example` 或 `acct:alice@acme.example`。该字符串只是 builder 输入，不是 membership 主键，也不是 invite delivery 授权。

构造 `ck.member.state{membership="join"}` 前，客户端 / 提交服务 MUST：

1. 以 `subject_id` / `payload.actor_id` 作为成员主语；不得把 handle 字符串写作 actor、grant subject 或 cell subject。
2. 对基础路径，验证 `invite_address.subject_id`、`invite_address.recipient_service_did`、`principal_locator` proof、`introduction_evidence_digest` 和 Realm Join Policy；`invite_address.recipient_service_did` 只能作为 join-time `delivery_binding` 的候选输入，仍需按本文件 §2 和 §4 物化。
3. 对可选 handle 辅助路径，先按 [`identity/identity-handles.md` §3.1](../identity/identity-handles.md) 规范化为 canonical `handle`，再仅在 Directory / Organization 明确支持时调用 `ck.find.directory.query.resolve_handle(intent="member_add" | "invite")`。不支持、无权或解析失败时，客户端 MUST 回到基础路径，要求提供 locator 或显式 address；不得本地合成 remote `recipient_service_did`。
4. 若可选解析结果携带 `MemberDeliveryBindingCandidate` 或 `member_delivery_binding`，验证其 handle claim / presentation 绑定 `handle`、`subject_id`、`member_delivery_binding.recipient_service_did`、issuer、`issued_at`、`expires_at`、撤销状态与 `audience`。claim `audience` MUST 等于目标 `realm_id` 或邀请方 service DID 之一；不一致 MUST 视作未授权 claim。
5. 将有效 delivery evidence 物化为 `payload.delivery_binding` 时，按 Realm `ck.realm.delivery_binding_policy` 选择 `binding_source`：
   - 多个来源同时可用时，reducer MUST 按固定优先级选择唯一 binding：`explicit` > `organization_policy` > `invite` > `join_policy` > `realm_policy` > `did_document_default`。
   - 选择最高优先级来源后，若该来源不在 `allow_binding_sources` 内、`recipient_service_did` 不在 `allowed_recipient_services` 内，或缺少该来源的条件性 evidence，reducer MUST 拒绝并返回 `delivery_binding_policy_mismatch`；MUST NOT 降级尝试较低优先级来源。
   - invite locator / invite delivery 已携带并通过接收服务背书的 binding 使用 `invite`，并携带 `service_acceptance_ref`；
   - Realm join policy 推导的 binding 使用 `join_policy`，并携带 `policy_event_ref`；
   - 组织目录 / 员工名录背书的地址使用 `organization_policy`，并携带 `service_acceptance_ref` + `policy_event_ref`；
   - Realm / linked Realm policy 继承使用 `realm_policy`，并携带 `policy_event_ref`；
   - 用户 / 管理员显式选择服务时使用 `explicit`，并携带 `service_acceptance_ref`；
   - 最后才考虑 `did_document_default`，且仅当 Realm `delivery_binding_policy.allow_did_document_default=true` 并已在 join 时物化 DID document hash。
   - 可选 handle candidate 的 `member_delivery_binding.binding_source` 不得是 `did_document_default`；handle resolution 与 DID Document fallback 是两条独立的物化路径。
6. 若输入只证明 actor DID、没有可接受的 `recipient_service_did` 或服务背书，除非 Realm policy 允许 `did_document_default` fallback 并在 join 时完成物化，否则 reducer MUST 拒绝 routable join。

Reducer MUST 在 gate proof 通过前先校验 applicant 是否具备提交 `ck.member.state{join}` 的 capability 或等价 invite / join-authorized grant；gate 只能增加限制，不能创造权限。最终 `binding_source` 不在 `allow_binding_sources` 中、或优先级决策得到的 binding 与 policy allowlist 冲突时，reducer MUST 返回 `delivery_binding_policy_mismatch`，不得降级到下一个来源。

Realm history SHOULD NOT 写入受限组织 handle 明文。需要审计时，Control Move 可引用 handle claim / service acceptance Event 的 `event_id`，或在私有 review / invite 流程中保存最小披露记录；公开成员状态只需要 DID 与 `delivery_binding`。

#### 3.1.1 Realm bootstrap 与初始成员（normative）

`ck.realm.create` 的 creator membership 是 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-ckrealmcreate-reducer-bootstrapnormative) 定义的 reducer 派生状态，不是客户端显式提交的 `ck.member.state{membership="join"}` Event。实现 MUST NOT 为这条隐式 creator membership 伪造 `binding_source="invite"`、`service_acceptance_ref` 或其它不存在的 join evidence。若 creator 需要在创建批次内立即成为 routable member，同一 `ck.self.events.command.submit` 批次 MAY 在 `ck.realm.create` 之后、由同一 `actor_id` 提交一条 `ck.member.state{membership="join"}` 同状态 self-transition（前态为 reducer 已派生的 `join`），专门物化 `delivery_binding`；该 binding MUST 使用本节已有来源之一，并携带对应真实证据：

- `did_document_default`：必须携带 `did_document_digest`，且 Realm policy 显式允许 DID Document fallback；
- `explicit` / `organization_policy`：必须携带真实 `service_acceptance_ref`（以及 `organization_policy` 的 `policy_event_ref`）；
- `join_policy` / `realm_policy`：必须携带真实 `policy_event_ref`。

初始批次中为其他 actor 写入 `ck.member.state{membership="join"}` 时也适用 §3.1 的普通规则。Handle 字符串本身、Directory `resolve_handle` 失败结果、或仅由客户端本地拼造的 DID / service DID 都不得作为 routable delivery binding；没有真实 `recipient_service_did` 证据时，producer 只能提交 `delivery_status="unroutable"`（若 Realm policy 允许），或改走后续 invite / rebind 流程。`binding_source="invite"` 只在存在真实 invite delivery / service-acceptance evidence 时使用；它不是 realm bootstrap 的兜底来源。

## 4. Policy 事件：`ck.realm.delivery_binding_policy`

Realm 通过独立的 `ck.realm.delivery_binding_policy` event 声明对成员投递绑定的强约束。该事件写入 `ck.component.realm.delivery_binding_policy.v1` cell（cas_register, cell_subject=null, bottom=reject），与 `ck.realm.join_rule` / `ck.realm.history_visibility` 等其它 realm policy 事件并列。Realm 在 `ck.realm.policy_components` 中将该 component 列入 active set 后，reducer 强制其约束。

```json
{
  "kind": "ck.realm.delivery_binding_policy",
  "payload": {
    "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
    "allow_binding_sources": [
      "explicit",
      "invite",
      "organization_policy"
    ],
    "allow_did_document_default": false,
    "allowed_recipient_services": [
      "did:webvh:z3omZGak5a5es84Ph2kfPs4UP:principal.acme.example"
    ],
    "required_endorsers": [
      "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example"
    ],
    "allow_unroutable_membership": false,
    "rebind_authorization": "member_and_admin",
    "expires_after_seconds": 7776000
  }
}
```

字段语义：

| 字段 | 类型 | 默认 | 语义 |
| --- | --- | --- | --- |
| `allow_binding_sources` | `enum[]` | `["did_document_default"]` for 个人 / 公开 Realm；组织 Realm 必须显式收窄 | 允许出现在被接受 binding 中的 `binding_source` 子集。 |
| `allow_did_document_default` | `boolean` | `false` | 是否允许 binding_source=did_document_default。组织 / 合规 Realm MUST 设为 `false`。 |
| `allowed_recipient_services` | `did[] \| ["*"]` | `[]`（**拒绝 / fail-closed**） | 允许出现在 `recipient_service_did` 的封闭集合。**默认空集 `[]` = 拒绝任意 recipient service（fail-closed）**，不再是"不限"——与本文整体 fail-closed 取向（§2 / §5 / §6）一致；漏配空集时 reducer MUST 拒绝 routable join（`delivery_binding_policy_mismatch`），不得放开任意 recipient service。需要"不限"语义时 MUST **显式声明哨兵** `["*"]`（unrestricted 标记），而非依赖空集。普通成员 binding 仍必须满足 `binding_source` / 背书等其余 §2 准则；`["*"]` 只解除 recipient service allowlist 这一维度的限制，不豁免 `required_endorsers` 等其它校验。 |
| `required_endorsers` | `did[]` | `[]` | 当 `allowed_recipient_services` 非空时，`recipient_service_did` 的 `service_acceptance_ref` MUST 由其中一个治理 DID 背书；否则空数组表示无强制背书要求。 |
| `allow_unroutable_membership` | `boolean` | `false` | 是否允许 `delivery_status="unroutable"` 成员。 |
| `rebind_authorization` | `enum(member, member_and_admin, admin_only, service_only, any)` | `member_and_admin` | rebind Control Move 的合法签名 / 背书集合（见 §6）。 |
| `expires_after_seconds` | `int?` | unset = 不过期 | 该 Realm 中所有 binding 的最大有效期；reducer MUST 在物化时把 `delivery_binding.expires_at = resolved_at + expires_after_seconds`，除非 binding 显式声明更短的 `expires_at`。 |

`ck.component.realm.delivery_binding_policy.v1` 是 cas_register cell（`cell_subject=null`，每 Realm 一个）。变更走 [`models/realm-and-space.md`](../models/realm-and-space.md) 的 `ck.realm.policy_components` 通用路径。

## 5. 路由不可降级（normative）

`delivery_binding` 一旦进入 accepted member cell，**任何 sender** 在向该 Realm 投递面向该成员的事件 / sync delta / to-device 消息 / push 唤醒 / MLS KeyPackage 请求时：

- MUST 解析当前 effective `delivery_binding.recipient_service_did` 作为唯一投递目标。
- MUST NOT 退路到该 actor 的 DID Document `CokretPrincipalServer` service entry，即便 DID Document 当前可解析、`recipient_service_did` 临时不可达、binding 已 `expires_at` 过期或被撤销。失败时 MUST 进入 quarantine + retry（重试策略：quarantine + 指数退避，见 [`sync/federation.md`](../sync/federation.md) §4.1），并在第二次失败后向 sender 上游暴露 `delivery_binding_unresolvable` 诊断。
- MUST NOT 把"recipient_service_did 在本地登记了该 DID 的内部账号 / OIDC subject / 员工目录条目"视为投递授权——所有授权 MUST 通过 binding 的 `service_acceptance_ref` / `policy_event_ref` 显式建立。

`expires_at` 到期：sender MUST 停止向该 binding 投递、quarantine pending events，并提示该成员客户端通过 §6 rebind 流程提交新 binding。**未提供 fallback path**——这是设计约束。

**权威划分（normative）**：路由不可降级原则（本节）、rebind 接受集合全分类与 `handover_grace_seconds`（§6）的**语义**权威是本文；[`sync/federation.md`](../sync/federation.md) §4.1 只承载对应的联邦 **wire 形态**（`delivery_binding_stale` 响应体与 `handover_proof` 校验、handover 限速与重定向边界）。两处表述如有分歧，语义以本文为准，wire 形态以 federation.md §4.1 为准。

## 6. Rebind 过渡（normative）

成员保持 `membership="join"` 但迁移 `recipient_service_did`（个人 PS → 组织 PS、组织换集群、灾备切换等）通过同一 `ck.member.state{membership="join"}` 的同状态 self-transition 完成：

1. **签名 / 背书**：rebind Control Move 的可签名主体由 `rebind_authorization` 决定：
   - `member`：仅成员 DID 自签即可。
   - `member_and_admin`：成员 DID 自签 + Realm `ck.realm.admin` capability 持有者背书（双签）。
   - `admin_only`：仅 Realm admin 可发起（用于离职 / 强制迁移）。
   - `service_only`：仅当前 / 目标 recipient service DID 可发起（用于服务运维迁移）。
   - `any`：上述任一即可。
2. **Precondition**：Control Move 的 `prev_refs` MUST 引用前一 sealed member cell 的 head；reducer 用 cas_register 校验前态。
3. **Handover frontier `F`**：该 Control Move 被 accepted Seal 覆盖时的 control point 是 rebind 切换点。事件因果图是偏序，切分 MUST 按下表**全分类**（任何 Realm event 恰好落入一类，不存在实现自由）：
   - causal 上 `prec(F)`（严格先于 F，不含 F）的 Realm events MUST 仍投递到旧 `recipient_service_did`（grace 内；grace 外见第 4 条）。
   - causal 上 `succ(F)`（含 F 及其后继）的 Realm events MUST 投递到新 `recipient_service_did`。
   - **与 F 并发**（既非 `prec(F)` 也非 `succ(F)`）的 Realm events：grace 内 sender MUST 双投（旧 + 新两个 `recipient_service_did`），接收方按 `event_id` + canonical hash 去重（与 [`operations-sync.md` §2.1](../sync/operations-sync.md) 的 `duplicate_conflict` 配对规则一致）；grace 外 MUST 只投新服务。
   - **sender frontier 判定**：sender 的本地 `service_binding_ref.delivery_binding_frontier` 与 F 的比较同样是偏序——frontier `≥ F`（F 在 sender 已观察 closure 内）时 MUST 切换到上述全分类规则；frontier `< F` 或**与 F 不可比**（含并发分支但缺 F 的部分前驱）时一律归入"落后"分支：仍按旧 binding 投递，并 MUST 触发 backfill 以推进本地 frontier（接收方负责回执并通知 sender 升级）。
4. **Grace period**：旧 `recipient_service_did` MUST 在 `handover_grace_seconds`（默认 86400）内继续接受迟到的 `prec(F)` 与 ∥F（与 F 并发）event；超过 grace 后旧服务 MUST reject 并返回 `delivery_binding_handed_over` + `new_recipient_service_did`。
5. **In-flight 事件**：sender 收到旧目标的 reject（无论 grace 内的临时失败还是 grace 外的 `delivery_binding_handed_over`）MUST 按新 binding 重新投递；不得回退到 DID Document，不得因 grace 已过而丢弃事件。
6. 旧服务在 grace 结束后 MUST NOT 保留可逆映射到该 Realm membership 的 sync state / to-device queue / push registration。新服务从 handover frontier 起重建 sync state，但 MUST 接受 `prec(F)` ∪ ∥F 的迟到 / 重投事件写入 Realm 历史（重建基线只约束 sync state 起点，不构成对迟到事件的拒收理由）。

未满足 rebind 授权或 precondition 的 Control Move **MUST fail closed**；服务不得仅因 DID Document 更新、本地 service account 切换、SSO subject 变更或员工目录调整自动迁移既有 Realm membership 的投递路径。

## 7. 单 binding 约束 + 多设备策略

同一 `(realm_id, actor_id)` 在任一时刻**有且仅有**一个 active `membership="join"` cell；该 cell 持有唯一 effective `delivery_binding`。**不允许**同一 DID 通过两个不同 `recipient_service_did` 同时持有两条 join membership——这种诉求应通过下列正确机制表达：

- **同一 binding 下多设备**：member 的多台设备各自向 `recipient_service_did` 上传 KeyPackage、注册 push、维护 to-device 队列。同一 binding 下的设备共享 sync state。
- **Realm-level mirror / shared sync**：Realm 自身需要多服务承载（HA / 灾备 / 跨区域）时，使用 Realm metadata 的 [`sync_endpoints`](../sync/federation.md) 表达 Realm-level service binding，与 member-level `delivery_binding` 正交。
- **同一物理用户的多个上下文** (e.g. Alice 既参与 personal Realm P 也参与 work Realm S)：每个 Realm 各自有独立 membership 与独立 binding；同一 DID 在 P 中 `recipient_service_did = personal PS`，在 S 中 `recipient_service_did = org PS`。这就是本文整套机制要解决的核心场景。

## 8. 关联性与隐私边界

`delivery_binding` 解决的是**投递路由 / 设备隔离 / push 隔离 / 合规审计边界**，**不解决跨上下文 unlinkability**：外部观察者仍能看到同一 `actor_id` 在不同 Realm 的 membership。需要 unlinkability 的部署应使用 pairwise / private DID（[`../identity/identity-did.md` §3](../identity/identity-did.md)），与 `delivery_binding` 正交。
