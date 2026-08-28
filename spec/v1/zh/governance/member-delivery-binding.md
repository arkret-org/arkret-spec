---
title: Member Delivery Binding
status: candidate
normative: true
stability: v1
updated: 2026-07-07
see_also:
  - join-policy.md
  - ../sync/federation.md
  - ../identity/identity-handles.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`../conformance/normative-language.md`](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> **成员投递绑定（delivery binding）与 join gate 正交**：join gate（见 [`join-policy.md`](join-policy.md)）决定"能否加入"，delivery binding 决定"加入后 events / sync / to-device / push / key-package 投递到哪个 Principal Server"。两者方向、生命周期、授权来源均不同，MUST NOT 互相推导。

## 1. 成员投递绑定

`ak.member.state{membership="join"}` 表达的是某个 principal `did_core_id` 在该 Realm 中成为成员；它**不等价于**"按该 principal 当前 `did` 的全局 home Principal Server 投递"。Realm-scoped events / account aggregate / to-device / push / key-package 的实际投递目标由该成员的 **effective delivery binding** 决定。本文是 v1 normative。

## 2. 接受准则（normative）

任一 `ak.member.state{membership="join"}` Control Move 被 reducer 接受前 MUST 满足：

1. `payload.delivery_status ∈ {routable, unroutable}` 显式声明。
2. `delivery_status="routable"` 时 `payload.delivery_binding` 必填，且其 `binding_source` 在 Realm `ak.component.realm.delivery_binding_policy.v1`（§4）的 `allowed_binding_sources` 集合内。
3. `delivery_status="unroutable"` 仅当 Realm policy 显式允许（`unroutable_membership_allowed=true`）。
4. `delivery_binding.recipient_id` MUST 是稳定 service `did_core_id`。服务准入 MUST 满足：该 `did_core_id` 出现在 Realm policy 的 `allowed_recipient_services` 集合内，或该 policy 显式声明哨兵 `["*"]`（unrestricted），或该 `did_core_id` 被 `required_endorsers` 中至少一个治理 `did_core_id` 通过 `service_acceptance_ref` 引用的 acceptance Event 背书。`required_endorsers` 非空时，该背书要求独立生效：即使命中 allowlist 或 `["*"]` 哨兵，`service_acceptance_ref` 仍 MUST 被其中至少一个治理主体背书。**`allowed_recipient_services` 为空集 `[]` 时 = 拒绝（fail-closed，见 §4 字段表）**：既未命中 allowlist、又未声明 `["*"]` 哨兵、又无 `required_endorsers` 背书时，reducer MUST 拒绝该 routable join（`delivery_binding_policy_mismatch`），不得把空集解释为"不限"放行。
5. `delivery_binding.service_resolution` MUST 携带 inline `ServiceResolutionRecord`，或携带 `{current_record_url, pinned_record_digest?}`。`current_record_url` 指向 `ak.open.service.read.resolution.v1`（`GET /_arkret/open/services/{service_id}/resolution`）；可选 digest 只钉住首次看到的那一版完整 `{record,proof}`，后续新版本必须独立验签。物化前 MUST 验证 record 签名和 `issued_at <= refresh_after < expires_at`、method-native history、`record.service_id == recipient_id`、`project(record.did) == recipient_id`、`record.service_kind == recipient_kind`、canonical `base_url` endpoint 绑定与 route-binding digest。引用未取得、被 pinned 的初始版 digest 不匹配或记录已过期时不得将该 binding 物化为 routable。
6. `delivery_binding` 的 `binding_source`-conditional required 字段满足 [`event-payload.schema.json#/$defs/member_delivery_binding`](../../artifacts/schemas/event-payload.schema.json)（例如 `did_document_default` MUST 含 `did_document_digest`；`explicit` / `invite` / `organization_policy` MUST 含 `service_acceptance_ref`；policy-driven source MUST 含 `policy_event_ref`）。
7. `delivery_binding.delivery_modes` 是该 binding 的**显式**模式集合；空集合或缺失等价于 schema violation。普通"全功能"成员 SHOULD 列出 `["events", "sync", "to_device", "push", "keypackages"]`。

上述准则同样适用于把 member cell 从 `invite` 原子推进到 `join` 的
`ak.invite.accept`。该 event 的 `invite_accept_payload` MUST 携带 `delivery_status`，routable 时
MUST 同时携带 `delivery_binding`；reducer 在同一 Control Move 内验证并物化它们。invite
原先的 `invite_delivery_target` 只可作为候选提示，不得自动充当 member binding 或绕过
本节 evidence / policy 校验。

接收方 MUST 先执行 [`event-payload.schema.json#/$defs/membership_payload`](../../artifacts/schemas/event-payload.schema.json) 与 `member_delivery_binding` schema 校验。`delivery_status` 非法、`delivery_status="routable"` 但缺少 `payload.delivery_binding`、routable binding 缺少 `service_resolution`、`delivery_binding` 字段结构或 conditional required 字段不满足 schema、`delivery_modes` 缺失或为空时，返回 `schema_violation`，reducer 不进入 policy validation。schema 合法后，reducer 校验上述准则失败时 MUST 拒绝该 Control Move，**不得**降级为部分接受：签名无效、subject / service `did_core_id` 不匹配、`did` projection 不匹配、resolution record 候选过期、issuer 未解析、`service_acceptance_ref` / `policy_event_ref` 引用的 evidence 不存在或语义无效时，返回 `delivery_binding_invalid`；Realm policy 对 `unroutable_membership_allowed`、`allowed_binding_sources`、`allowed_recipient_services`、`required_endorsers` 或来源优先级的校验失败时，返回 `delivery_binding_policy_mismatch`。

声明可加入 unroutable member Realm 的客户端 profile SHOULD 在 join / accept UI 中披露："该 Realm 仅向本地可见，不接收服务端推送、同步、to-device、push 或 KeyPackage 投递"。该披露是客户端 profile 义务，不参与 reducer 接受条件；reducer 的可验证判据仅为上述 policy 和 payload 条件。

注意：`payload.delivery_binding` / `member_delivery_binding.recipient_id` 描述成员加入后接收 events、sync、to-device、push、KeyPackage 的目标 Principal Server。`join_candidates[]` 则是 invitee Principal Server 从 signed invite / 当前 joined-member delivery binding 裁剪出的 federation forwarding 提示；客户端不得直投 candidate。Join builder 和 reducer MUST NOT 把 candidate 复制为 invitee 加入后的 `delivery_binding`，该 binding 必须由 invitee 自签。`service_resolution` 只解决该 service DID 如何到达当前 URL，不产生 admission authority。

同一个 accepted binding 也是 availability holder eligibility 的唯一 predecessor carrier：对每个 effective
`membership="join"` 且 `delivery_status="routable"` 的成员，replay 在完整验证 binding 后把
`recipient_id` 加入 eligible holder set，并按 DID core id 去重。不得从 Membership payload 增加
`principal_authority`，也不得从 actor id、`via_ids`、DID Document、当前 route cache 或 notary 身份
推导第二套 holder。binding 过期或被 accepted rebind/leave 取代后只影响后继 Seal；已经 accepted Seal 继续
按其冻结 predecessor view 验证。

## 3. `binding_source` 与责任方

> **默认 allowlist 警示（normative）**：下表列出 6 类 `binding_source`，但**并非默认全部可用**。未配置 `ak.realm.delivery_binding_policy`（§4）时，`allowed_binding_sources` 默认仅含最弱来源 `did_document_default`（见 §4 字段表）。组织 / 合规 Realm MUST 显式收窄 `allowed_binding_sources` 并把 `did_document_default_allowed` 设为 `false`，否则成员可凭 DID Document 默认条目自行决定投递目标，绕过治理背书。

| `binding_source` | 谁负责填 | 何时使用 | 补充必填 |
| --- | --- | --- | --- |
| `explicit` | 邀请方 / 管理员客户端 | 用户显式选择目标服务 | `service_acceptance_ref` |
| `did_document_default` | 客户端 DID resolver | Realm policy 允许 fallback，未匹配其它来源 | `did_document_digest` |
| `invite` | 邀请方 builder | 邀请 token 已携带 binding | `service_acceptance_ref` |
| `join_policy` | reducer 由 Join Policy 推导 | Join Policy 的 gate / role 决定目标服务 | `policy_event_ref` |
| `organization_policy` | 组织治理目录 | invitee 是 Org 员工，组织 policy 指定目标 | `service_acceptance_ref` + `policy_event_ref` |
| `realm_policy` | Realm policy 默认值 | Realm 声明 default recipient | `policy_event_ref` |

所有六类来源都要求 `resolved_at`；任何 `binding_source` 进入 canonical Event 时，**结果 MUST 已在客户端 / 提交服务侧解析完成**，并携带已验证的 `service_resolution`，不得留"运行时再 resolve"的隐含状态。

### 3.1 邀请 / 成员添加输入

客户端 MAY 提供两类成员添加输入：

1. **基础路径**：显式 `invite_address`、online `principal_locator` 或其它 [`invite-addressing.md`](../sync/invite-addressing.md) 定义的 `introduction_evidence`。该路径不依赖 handle resolve。
2. **可选辅助路径**：邀请方输入 `@alice:acme.example`、`alice@acme.example`、`alice:acme.example` 或 `acct:alice@acme.example`。该字符串只是 builder 输入，不是 membership 主键，也不是 invite delivery 授权。

构造 `ak.member.state{membership="join"}` 前，客户端 / 提交服务 MUST：

1. 以 `subject_id` / `payload.actor_id` 作为成员主语；不得把 handle 字符串写作 actor、grant subject 或 cell subject。
2. 对基础路径，验证 `invite_address.subject_id`、`invite_address.recipient_id`、`principal_locator` proof、`introduction_evidence_digest` 和 Realm Join Policy；`invite_address.recipient_id` 只能作为 join-time `delivery_binding` 的候选输入，仍需按本文件 §2 和 §4 物化。
3. 对可选 handle 辅助路径，先按 [`identity/identity-handles.md` §3.1](../identity/identity-handles.md) 规范化为 canonical `handle`，再仅在 Directory / Organization 明确支持时调用 `ak.find.directory.read.resolve_handle.v1(intent="member_add" | "invite")`。不支持、无权或解析失败时，客户端 MUST 回到基础路径，要求提供 locator 或显式 address；不得本地合成 remote `recipient_id`。
4. 若可选解析结果携带 `MemberDeliveryBindingCandidate` 或 `member_delivery_binding`，验证其 handle claim / presentation 绑定 `handle`、`subject_id`、`member_delivery_binding.recipient_id`、`service_resolution`、issuer、`issued_at`、`expires_at`、撤销状态与 `audience`。claim `audience` MUST 等于目标 `realm_id` 或邀请方 service `did_core_id` 之一；不一致 MUST 视作未授权 claim。
5. 将有效 delivery evidence 物化为 `payload.delivery_binding` 时，按 Realm `ak.realm.delivery_binding_policy` 选择 `binding_source`：
   - 多个来源同时可用时，reducer MUST 按固定优先级选择唯一 binding：`explicit` > `organization_policy` > `invite` > `join_policy` > `realm_policy` > `did_document_default`。
   - schema MUST 先校验该 `binding_source` 的 conditional required evidence 字段；缺少 `service_acceptance_ref` / `policy_event_ref` / `did_document_digest` 等 source-specific 必填字段时，接收方 MUST 以 `schema_violation` 拒绝，reducer 不进入来源选择或 policy validation。字段齐备后，若 evidence 引用不可解析、签名无效、scope 不覆盖目标 Realm，reducer MUST 拒绝并返回 `delivery_binding_invalid`；若该来源不在 `allowed_binding_sources` 内；或 `recipient_id` 既不在 `allowed_recipient_services` 内、也未被 `["*"]` 哨兵覆盖、且无 `required_endorsers` 背书；或 `required_endorsers` 非空但 `service_acceptance_ref` 未被其中任一治理 DID 背书，reducer MUST 拒绝并返回 `delivery_binding_policy_mismatch`。上述失败均 MUST NOT 降级尝试较低优先级来源。
   - invite locator / invite delivery 已携带并通过接收服务背书的 binding 使用 `invite`，并携带 `service_acceptance_ref`；
   - Realm join policy 推导的 binding 使用 `join_policy`，并携带 `policy_event_ref`；
   - 组织目录 / 员工名录背书的地址使用 `organization_policy`，并携带 `service_acceptance_ref` + `policy_event_ref`；
   - Realm / linked Realm policy 继承使用 `realm_policy`，并携带 `policy_event_ref`；
   - 用户 / 管理员显式选择服务时使用 `explicit`，并携带 `service_acceptance_ref`；
   - 最后才考虑 `did_document_default`，且仅当 Realm `delivery_binding_policy.did_document_default_allowed=true` 并已在 join 时物化 DID document hash。
   - 可选 handle candidate 的 `member_delivery_binding.binding_source` 不得是 `did_document_default`；handle resolution 与 DID Document fallback 是两条独立的物化路径。
6. 若输入只证明 actor DID、没有可接受的 `recipient_id` 或服务背书，除非 Realm policy 允许 `did_document_default` fallback 并在 join 时完成物化，否则 reducer MUST 拒绝 routable join。

Reducer MUST 在 gate proof 通过前先校验 applicant 是否具备提交 `ak.member.state{join}` 的 capability 或等价 invite / join-authorized grant；gate 只能增加限制，不能创造权限。最终 `binding_source` 不在 `allowed_binding_sources` 中、或优先级决策得到的 binding 与 policy allowlist 冲突时，reducer MUST 返回 `delivery_binding_policy_mismatch`，不得降级到下一个来源。

Realm history SHOULD NOT 写入受限组织 handle 明文。需要审计时，Control Move 可引用 handle claim / service acceptance Event 的 `event_id`，或在私有 review / invite 流程中保存最小披露记录；公开成员状态只需要 DID 与 `delivery_binding`。

#### 3.1.1 Realm bootstrap 与初始成员（normative）

creator membership 是 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative) bootstrap registry 的最后一个 required slot：由 creator 提交唯一的 `ak.member.state{membership="join"}` Event，执行 `leave -> join` 并同时物化 delivery binding。`ak.realm.create` reducer 不隐式写 membership，也不存在随后 `join -> join` 的第二种 wire 形态。该 binding MUST 使用本节已有来源之一，并携带对应真实证据：

- `did_document_default`：必须携带 `did_document_digest`，且 Realm policy 显式允许 DID Document fallback；
- `explicit` / `organization_policy`：必须携带真实 `service_acceptance_ref`（以及 `organization_policy` 的 `policy_event_ref`）；
- `join_policy` / `realm_policy`：必须携带真实 `policy_event_ref`。

上述任一 routable 分支还 MUST 携带与 `recipient_id` 一致的 verified `service_resolution`；source-specific evidence 只解决准入来源，不解决当前 endpoint 映射。

初始批次中为其他 actor 写入 `ak.member.state{membership="join"}` 时也适用 §3.1 的普通规则。Handle 字符串本身、Directory `resolve_handle` 失败结果、或仅由客户端本地拼造的 DID / service DID 都不得作为 routable delivery binding；没有真实 `recipient_id` 证据时，producer 只能提交 `delivery_status="unroutable"`（若 Realm policy 允许），或改走后续 invite / rebind 流程。`binding_source="invite"` 只在存在真实 invite delivery / service-acceptance evidence 时使用；它不是 realm bootstrap 的兜底来源。

## 4. Policy 事件：`ak.realm.delivery_binding_policy`

Realm 通过独立的 `ak.realm.delivery_binding_policy` event 声明对成员投递绑定的强约束。该事件写入 `ak.component.realm.delivery_binding_policy.v1` cell（cas_register, cell_subject=null, bottom=reject），与 `ak.realm.join_rule` / `ak.realm.history_access` 等其它 realm policy 事件并列。该 cell 在当前 Seal basis 下有非 `⊥` 值后 reducer 即强制其约束；它**不**在 `ak.realm.policy_bundle` payload 内重复声明，也不存在额外的 bundle-side "active set" 开关。

```json
{
  "kind": "ak.realm.delivery_binding_policy",
  "payload": {
    "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
    "allowed_binding_sources": [
      "explicit",
      "invite",
      "organization_policy"
    ],
    "did_document_default_allowed": false,
    "allowed_recipient_services": [
      "ak:did_core:webvh:z3omZGak5a5es84Ph2kfPs4UP"
    ],
    "required_endorsers": [
      "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv"
    ],
    "unroutable_membership_allowed": false,
    "rebind_authorization": "member_and_admin",
    "expires_after_seconds": 7776000
  }
}
```

字段语义：

| 字段 | 类型 | 默认 | 语义 |
| --- | --- | --- | --- |
| `allowed_binding_sources` | `enum[]` | **policy event 缺席**时个人 / 公开 Realm 视为 `["did_document_default"]`，组织 Realm 必须显式收窄；policy event 存在时以写入值为准 | 允许出现在被接受 binding 中的 `binding_source` 子集。 |
| `did_document_default_allowed` | `boolean` | `true` for 个人 / 公开 Realm；组织 / 合规 Realm 必须显式设为 `false` | 是否允许 binding_source=did_document_default。 |
| `allowed_recipient_services` | `did_core_id[] \| ["*"]` | 三种情形分开：**policy event 缺席** → 个人 / 公开 Realm 视为 `["*"]`，组织 / 合规 Realm MUST 先显式写入本 policy；**policy event 存在但省略本字段** → `[]`（fail-closed）；**显式 `[]`** → 同样 fail-closed | 允许出现在 `recipient_id` 的稳定 service `did_core_id` 集合。`[]` = 拒绝任意 recipient service，MUST NOT 被解释为 unrestricted；unrestricted 只能由显式哨兵 `["*"]` 表达。普通成员 binding 仍必须满足 `binding_source` / 背书等其余 §2 准则；`["*"]` 只解除 recipient service allowlist 这一维度的限制，不豁免 `required_endorsers` 等其它校验。 |
| `required_endorsers` | `did_core_id[]` | `[]` | 非空时，`recipient_id` 的 `service_acceptance_ref` MUST 由其中一个治理 `did_core_id` 背书；该要求独立于 `allowed_recipient_services` 与 `["*"]` 哨兵。空数组表示无强制背书要求。 |
| `unroutable_membership_allowed` | `boolean` | `false` | 是否允许 `delivery_status="unroutable"` 成员。 |
| `rebind_authorization` | `enum(member, member_and_admin, admin_only, service_only, any)` | `member_and_admin` | rebind Control Move 的合法签名 / 背书集合（见 §6）。 |
| `handover_grace_seconds` | `int?` | 86400（省略时） | 更换 service core 后，旧 `recipient_id` 继续接受迟到 / 并发 event 的窗口；上限 604800。语义见 §6。 |
| `expires_after_seconds` | `int?` | unset = 不过期 | 该 Realm 中所有 binding 的最大有效期；reducer MUST 在物化时把 `delivery_binding.expires_at = resolved_at + expires_after_seconds`，除非 binding 显式声明更短的 `expires_at`。 |

`ak.component.realm.delivery_binding_policy.v1` 是 cas_register cell（`cell_subject=null`，每 Realm 一个）。变更走本节的 `ak.realm.delivery_binding_policy` facet event，与 [`models/realm-and-space.md` §2.3](../models/realm-and-space.md) 其它 per-facet Realm policy 事件同一路径；`ak.realm.policy_bundle` 只承载没有独立 facet event kind 的组件。

## 5. 路由不可降级（normative）

`delivery_binding` 一旦进入 accepted member cell，**任何 sender** 在向该 Realm 投递面向该成员的事件 / sync delta / to-device 消息 / push 唤醒 / MLS KeyPackage 请求时：

- MUST 解析当前 effective `delivery_binding.recipient_id` 作为唯一投递目标。
- MUST 把该字段当作 `did_core_id`，并只能通过 binding 携带的 inline record / `current_record_url` 及其后刷新的 verified `ServiceResolutionRecord` 映射到 `did` / `base_url`。`GET /_arkret/describe` 是到达 URL 后的二跳确认，不是首跳 resolver。
- MUST NOT 退路到该 actor 的 DID Document `type="ArkretService", serviceKind="principal_server"` entry，即便 DID Document 当前可解析、`recipient_id` 临时不可达、binding 已 `expires_at` 过期或被撤销。失败时 MUST 进入 quarantine + retry（重试策略：quarantine + 指数退避，见 [`sync/federation.md`](../sync/federation.md) §4.1）；只有本节固定的同-core route recovery 序列耗尽后，才向 sender 上游暴露 `delivery_binding_unresolvable` 诊断。
- MUST NOT 把"recipient_id 在本地登记了该 DID 的内部账号 / OIDC subject / 员工目录条目"视为投递授权——所有授权 MUST 通过 binding 的 `service_acceptance_ref` / `policy_event_ref` 显式建立。

`delivery_binding.expires_at` 到期：sender MUST 停止向该 binding 投递、quarantine pending events，并以已登记的 `delivery_binding_stale` 回执，提示该成员客户端通过 §6 rebind 流程提交新 binding。route notice / mirror 只能恢复仍有效 binding 所指向的同一 service core，不能延长 binding 有效期；这里**未提供授权 fallback path**——这是设计约束。

sender MAY 为高频投递保存 TTL `ServiceRouteCache`，key 必须是 `recipient_id: did_core_id`，value 至少包含已验证 `service_kind`、`did`、`method_history_head`、record sequence/digest、canonical `base_url`、route-binding digest、`current_record_url`、`verified_at`、`refresh_after`、signed record `expires_at` 与本地 `cache_expires_at`。`cache_expires_at` MUST `<= expires_at`；任一到期都使 cache miss，且本地 TTL 不得延长或覆盖 signed expiry。cache 是实现层优化，不是 Realm 授权状态，MUST NOT 写回 member cell 或改写 `binding_source`。`refresh_after` 可触发对 `current_record_url` 的异步刷新；任一 expiry 到达、收到 stale/handover 信号、method head / route-binding digest 改变或执行安全敏感操作时 MUST 取得最新 record 并重新验证。同一 `recipient_id` 下的 `did` / URL / method head 刷新不改变 member cell，不需要 rebind；`recipient_id` 改变才按 §6 rebind。刷新失败按本节 quarantine 规则处理，不得回退到域名推导、旧 `did` 或 actor DID Document。

TTL route cache 与 durable anti-rollback floor 必须分离。sender MUST 为每个 effective `recipient_id` 按 [`../sync/service-surface.md` §2.6](../sync/service-surface.md) durable 保存最后接受的 record sequence/digest；cache 丢失或进程重启不得允许回退到更旧 record。该 floor 是本地验证安全状态，不是新的 Realm 授权，也不得写回 member cell。

当 current route 过期或不可达、但 member binding 本身仍有效时，恢复顺序固定为：

1. 使用未过期且不低于 durable floor 的本地 verified route；
2. 从 binding 保存的 `current_record_url` 获取并验证正式 current record；
3. 若已 durable 保存与 floor basis 匹配、未取消且未过期的 `ServiceRouteHandoverNotice`，按其时间窗向 candidate 读取正式连续 successor；
4. 向 requester 与 target 都可见的 Realm peer/mirror 调用 `ak.peer.service_resolution.read.resolve.v1`，只接受从 durable floor 连续的 target-signed record/notice；
5. MAY 查询部署显式配置、且执行同等 requester/target 授权、反枚举与 target-proof 验证的外部 mirror；不得把任意公开 `did_core_id -> URL` 服务当 fallback；
6. 全部失败则保持 quarantine，并要求重新分享 signed locator/carrier 或执行显式带外修复。

每一条恢复路径最终都必须取得 target service 自签的正式 `ServiceResolutionRecord`、验证其 chain/freshness/method history，并完成 describe 二跳反向确认后才能恢复业务投递。notice、mirror ack、mirror 自身身份、HTTP redirect、candidate 可达或多个 mirror 一致均不能替代该验证。相同 sequence 异 digest、chain gap、wrong core/kind 或 describe mismatch 必须进入 route-fork quarantine。上述顺序只恢复**同一** `recipient_id` 的 route state；任何返回不同 service core 的 notice、record 或 mirror response 都必须拒绝，并按 §6 提交新的 delivery binding / rebind Control Move。

抓取 `current_record_url` MUST 使用 [`../sync/service-surface.md` §2.6](../sync/service-surface.md) 的 SSRF 防护、DNS 前后地址分类、无 redirect / 无 `Content-Encoding`、1 MiB（1,048,576 bytes）完整 `AuthenticatedServiceResolution` canonical 响应上限与 5 秒总 deadline。该上限包含 method-history evidence 与 normalized DID Document，不得沿用 64 KiB 的旧 record-only 上限。TLS 成功、URL 可达或 HTTP 200 均不替代 record 验签。

**权威划分（normative）**：路由不可降级原则与同-core route recovery（本节）、rebind 接受集合全分类与 `handover_grace_seconds`（§6）的**语义**权威是本文；[`sync/service-surface.md`](../sync/service-surface.md) §2.6 定义 current record、future route notice 与 durable floor；[`sync/federation.md`](../sync/federation.md) §4.1 定义 member rebind 的联邦 wire，§6.4 定义 route publish/resolve wire。route notice 的 `grace_until` 是同一 service core 的旧入口可用窗口，与 §6 更换 service core 的 `handover_grace_seconds` 不得混用。

## 6. Rebind 过渡（normative）

成员保持 `membership="join"` 但把 `recipient_id` 改为另一个 service `did_core_id`（个人 PS → 组织 PS 等）时，通过同一 `ak.member.state{membership="join"}` 的同状态 self-transition 完成。同一 `did_core_id` 的集群、域名、`did` 或 method head 更新是 resolution refresh，不是 rebind：

1. **签名 / 背书**：rebind Control Move 的可签名主体由 `rebind_authorization` 决定：
   - `member`：仅成员 DID 自签即可。
   - `member_and_admin`：成员 DID 自签 + Realm `ak.realm.admin` capability 持有者背书（双签）。
   - `admin_only`：仅 Realm admin 可发起（用于离职 / 强制迁移）。
   - `service_only`：仅当前 / 目标 recipient service DID 可发起（用于服务运维迁移）。
   - `any`：上述任一即可。
   新 binding 的 `recipient_id` 必须是 `did_core_id`，并携带已验证、未过期且与该 `did_core_id` 一致的 `service_resolution`；旧路由 cache 不能替代新 binding 材料。
2. **Precondition**：Control Move 的 `prev_refs` MUST 引用前一 sealed member cell 的 head；reducer 用 cas_register 校验前态。
3. **Handover frontier `F`**：该 Control Move 被 accepted Seal 覆盖时的 control point 是 rebind 切换点。事件因果图是偏序，切分 MUST 按下表**全分类**（任何 Realm event 恰好落入一类，不存在实现自由）：
   - causal 上 `prec(F)`（严格先于 F，不含 F）的 Realm events MUST 仍投递到旧 `recipient_id`（grace 内；grace 外见第 4 条）。
   - causal 上 `succ(F)`（含 F 及其后继）的 Realm events MUST 投递到新 `recipient_id`。
   - **与 F 并发**（既非 `prec(F)` 也非 `succ(F)`）的 Realm events：grace 内 sender MUST 双投（旧 + 新两个 `recipient_id`），接收方按 `event_id` + canonical hash 去重（与 [`operations-sync.md` §2.1](../sync/operations-sync.md) 的 `duplicate_conflict` 配对规则一致）；grace 外 MUST 只投新服务。
   - **sender frontier 判定**：sender 的本地 `service_binding_ref.delivery_binding_frontier` 与 F 的比较同样是偏序——frontier `≥ F`（F 在 sender 已观察 closure 内）时 MUST 切换到上述全分类规则；frontier `< F` 或**与 F 不可比**（含并发分支但缺 F 的部分前驱）时一律归入"落后"分支：仍按旧 binding 投递，并 MUST 触发 backfill 以推进本地 frontier（接收方负责回执并通知 sender 升级）。
4. **Grace period**：旧 `recipient_id` MUST 在 `handover_grace_seconds`（默认 86400）内继续接受迟到的 `prec(F)` 与 ∥F（与 F 并发）event；超过 grace 后旧服务 MUST reject 并返回 `delivery_binding_handed_over` + `new_recipient_id`。
5. **In-flight 事件**：sender 收到旧目标的 reject（无论 grace 内的临时失败还是 grace 外的 `delivery_binding_handed_over`）MUST 按新 binding 重新投递；不得回退到 DID Document，不得因 grace 已过而丢弃事件。
6. 旧服务在 grace 结束后 MUST NOT 保留可逆映射到该 Realm membership 的 sync state / to-device queue / push registration。新服务从 handover frontier 起重建 sync state，但 MUST 接受 `prec(F)` ∪ ∥F 的迟到 / 重投事件写入 Realm 历史（重建基线只约束 sync state 起点，不构成对迟到事件的拒收理由）。

未满足 rebind 授权或 precondition 的 Control Move **MUST fail closed**；服务不得仅因 DID Document 更新、本地 service account 切换、SSO subject 变更或员工目录调整自动迁移既有 Realm membership 的投递路径。

## 7. 单 binding 约束 + 多设备策略

同一 `(realm_id, actor_id)` 在任一时刻**有且仅有**一个 active `membership="join"` cell；该 cell 持有唯一 effective `delivery_binding`。**不允许**同一 DID 通过两个不同 `recipient_id` 同时持有两条 join membership——这种诉求应通过下列正确机制表达：

- **同一 binding 下多设备**：member 的多台设备各自向 `recipient_id` 上传 KeyPackage、注册 push、维护 to-device 队列。同一 binding 下的设备共享 sync state。
- **需要持有 Realm Event 的 bot/service/notary**：必须成为显式 joined Realm member/service actor，并使用该成员的 `delivery_binding.recipient_id`；部署级 HA、镜像或“已知 peer”本身不取得 Realm 内容。
- **同一物理用户的多个上下文** (e.g. Alice 既参与 personal Realm P 也参与 work Realm S)：每个 Realm 各自有独立 membership 与独立 binding；同一 DID 在 P 中 `recipient_id = personal PS`，在 S 中 `recipient_id = organization PS`。这就是本文整套机制要解决的核心场景。

## 8. 关联性与隐私边界

`delivery_binding` 解决的是**投递路由 / 设备隔离 / push 隔离 / 合规审计边界**，**不解决跨上下文 unlinkability**：外部观察者仍能看到同一 `actor_id` 在不同 Realm 的 membership。需要 unlinkability 的部署应使用 pairwise / private DID（[`../identity/identity-did.md` §3](../identity/identity-did.md)），与 `delivery_binding` 正交。
