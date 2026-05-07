---
title: Event Authorization and State Resolution
---

## 1. 目标

本文件定义 Contrix Space 内事件是否有效、状态如何收敛、冲突如何确定性解决、redaction 如何保留最小字段，以及 Space 如何升级 reducer 与 schema profile。

任何支持联邦写入、多设备写入或离线写入的实现 MUST 实现本文件的规则。

## 2. 版本与 Profile

Contrix v1 通过以下三个机器约束表达版本演进，**不**使用顶层 `space_version` wire 字段：

- `Space.schema_refs`：声明 Space 启用的 schema id 集合（例如 `cx.schema.space.v1`、`cx.schema.flow.v1`）。
- `Event.requirements.{schema[], reducer, features[], critical_extensions[]}`：每个 Event 显式声明它依赖的 schema profile / reducer profile / feature / critical extension；整个 `requirements` 对象进入 event digest，参与签名绑定。
- `cx.space.upgrade` state event：把 Space 当前态从一个 reducer/schema profile 切换到另一个（见 §11）。

实现 MUST reject 自己未支持的 `requirements.reducer` 或 `requirements.schema[]` 中的 critical profile id（按 `requirements.features` / `requirements.critical_extensions` 规则 fail closed）。实现 MAY 以只读方式展示未支持 profile 下的事件，但 MUST NOT 将其作为本地 accepted state。

## 3. Event Validation Pipeline

收到事件后，节点 MUST 按以下顺序验证：

1. Parse canonical JSON，不接受重复 key、非规范 number、无效 UTF-8 或超过 profile 限制的对象。
2. 验证 `event_id` 是合法 `cx:event:*` typed ID，并验证事件 redaction 前、去除 `proofs` 与 `unsigned` 后 canonical bytes 的 digest 与 proof `payload_hash` / event digest 一致。
3. 验证 `proofs` 中 actor/device/service 签名。
4. 验证 `space_id`、`kind`、`created_at`、`hlc` 与 schema（含 `requirements.schema[]` 与 `requirements.reducer`）。
5. 拉取并验证 `prev_refs` 和 `auth_refs` 指向事件的 hash。
6. 对 `auth_refs` 运行授权算法。
7. 对 `payload` 运行类型级 schema validation。
8. 对策略服务、capability constraint、rate limit 和 abuse policy 运行本地检查。
9. 输出 `accepted`、`soft_failed`、`rejected` 或 `quarantined`。

节点 MUST NOT 因为事件来自可信 Sync Service 就跳过任何步骤。

接收方在进入授权和 state resolution 前 MUST 验证 HLC 格式和时钟窗口。Contrix v1 的 HLC drift 模型只有两个语义层级，外加 profile 覆盖：

| 字段 | 默认值 | 语义 |
| --- | ---: | --- |
| `hard_future_skew_ms` | 300_000（5 分钟） | 物理时间超出该窗口的 HLC MUST reject 或 quarantine。被 quarantine 的事件不得参与 winner 选择。 |
| `expected_future_skew_ms` | 30_000（30 秒） | 物理时间超出该窗口但在 hard 窗口内的 HLC SHOULD soft-fail / quarantine 并请求 backfill / policy check。 |

实现 / Space / reducer profile MAY 在 `server/describe.limits` 或 reducer profile 中显式声明更紧或更宽的 `hard_future_skew_ms` 与 `expected_future_skew_ms`。**v1 不再隐式区分"普通事件"与"高风险事件"的不同 expected drift**；如果某 reducer profile 想对 state event（capability、membership、policy、service binding、reducer profile 升级、MLS commit 等）施加更严的窗口，MUST 在 profile 中显式声明 `state_event_expected_future_skew_ms`，否则一律按 `expected_future_skew_ms` 执行。

无论窗口配置如何，HLC 不得单独覆盖缺失的 causal dependency、`actor_seq` 回退或 revoke freshness 检查；高风险 state event 即使 HLC 更大，也必须先满足签名、授权、`prev_refs`、`auth_refs`、`actor_seq` 和 revoke freshness。

## 4. Auth Refs

每个写事件 MUST 包含 `auth_refs`。`auth_refs` 是授权当前事件所需的最小状态事件集合，不是完整状态快照。

v1 reducer 的 auth refs 选择规则：

| 当前事件类型 | 必需 auth refs |
| --- | --- |
| `cx.space.create` | 无 |
| `cx.member.state` | `cx.space.create`、目标 actor 当前 membership、发送者 membership、相关 join rule、相关 capability grant |
| `cx.capability.grant` | `cx.space.create`、grantor membership、grantor 当前 grant/role/admin capability |
| `cx.capability.revoke` | 被撤销 grant、revoker membership、revoker revoke/admin capability |
| `cx.policy.*` | `cx.space.create`、actor membership、policy/admin capability、上一版同 key policy |
| `cx.space.<facet>`（per-facet policy state event，见 §4.1） | `cx.space.create`、actor membership、该 facet 对应 capability tier、上一版同 facet 的 state 事件，及该 facet 声明的额外依赖 |
| `cx.space.child` | parent Space 的 `cx.space.create`、发送者 parent membership、`cx.space.hierarchy.manage` capability、目标 child Space stripped create 或可验证引用 |
| `cx.space.parent` | child Space 的 `cx.space.create`、发送者 child membership、`cx.space.hierarchy.manage` capability、目标 parent Space stripped create 或可验证引用 |
| `cx.space.organization` | `cx.space.create`、组织 DID 当前控制状态、组织签发或撤销该声明的 capability / service binding |
| `cx.flow.branch.*` | actor Space membership、目标 Flow 当前状态、目标 discussion branch 当前状态、对应 flow branch capability |
| `cx.flow.branch.member` | actor Space membership、目标 actor 当前 discussion membership、discussion join / invite / moderation policy、对应 branch membership capability |
| `cx.flow.*` | actor Space membership、所属 Space (kind=board) / Space (kind=list) 当前状态（若适用）、目标 Flow 当前状态、对应 flow capability |
| `cx.morph.*` | actor Space membership、目标 Morph 当前状态、morph schema / facet policy、对应 morph capability |
| `cx.relation.*` | actor Space membership、relation type schema、source/target 可见状态、对应 relation capability |
| `cx.message.*` | actor Space membership、目标 Flow discussion membership / visibility、目标 Message 当前状态、send/edit/redact capability |
| `cx.mls.*` | actor membership、encryption policy、当前 epoch state、device trust state |
| `cx.redaction` | actor membership、被 redaction 事件、redact_own 或 redact_any capability |
| `cx.space.upgrade` | `cx.space.create`、当前 upgrade policy、creator/admin capability |
| `cx.space.archive` / `cx.space.freeze` / `cx.space.tombstone` / `cx.space.destroy` | `cx.space.create`、当前 lifecycle state、对应 lifecycle/admin capability tier，及该 transition 声明的额外 guard（见 §4.2） |
| `cx.device.authorized` / `cx.device.revoked` / `cx.device.list_update` | principal control Space 的 `cx.space.create`、目标 principal 当前 DID/key-log state、授权设备或 recovery policy、上一版 device state |
| `cx.session.grant` | principal control Space 的 `cx.space.create`、目标 principal 当前 DID/device state、issuer service binding 或组织 policy、上一版同 session / subject grant state |
| `cx.account.status` | principal control Space 的 `cx.space.create`、actor lifecycle / admin / governance capability、上一版 `cx.account.status` state、retention / legal-hold / erasure policy（如适用） |
| `cx.moderation.report` | actor membership、reporter capability（基础举报 capability 默认对成员开放）、被举报对象的可见性证明、上一版同 `(reporter, target)` report state（用于去重）|
| `cx.moderation.frank` | actor membership、E2EE Space 的 encryption / audit policy、对应 `cx.moderation.report` 引用、moderation server / audit agent service binding |
| `cx.policy.action` | actor membership、moderation / policy / admin capability、`cx.space.moderation_policy` 当前状态、政策列表 hash |

如果事件缺少必需 auth ref，节点 MUST soft fail 并尝试 backfill。Backfill MUST 受 `../conformance/scalability-constraints.md` 的 `auth_chain` 深度、`auth_refs` 数量、page size、retry 和本地资源上限约束；实现不得为了验证单个事件无限递归拉取历史。若在上限内仍缺失，或只能通过未验证 snapshot / 未授权服务获得依赖，节点 MUST reject、保持 soft-failed 或 quarantine，具体取决于错误是否可恢复。

长期 Space 中的 `cx.space.create` MAY 通过已验证 snapshot manifest、checkpoint、witness receipt 或 stripped create event 满足 bootstrap 依赖，但接收方仍必须能验证 create event digest、space id、creator authority 和 snapshot signer authority。任何 snapshot-assisted auth ref 都不得替代事件本身的签名责任，也不得允许服务端伪造 Space 起源。

### 4.1 Space-level Policy 状态事件

每个 Space-level 策略 facet 是一个独立 event kind。Reducer state slot 主键是 `(space_id, kind)`，per-subject facet 还要加上 schema registry 声明的 `state_subject_field`（见 [`artifacts/registry/event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json)）。

| Kind | cardinality | capability tier | 额外 auth refs | 说明 |
| --- | --- | --- | --- | --- |
| `cx.space.policy` | singleton | policy/admin | 上一版 state | Space 通用 access policy。 |
| `cx.space.join_rule` | singleton | join_policy/admin | 上一版 state | Space join rule。 |
| `cx.space.history_visibility` | singleton | history/policy/admin | 上一版 state、当前 encryption / `cx.space.history_sharing_policy` | Space history visibility。 |
| `cx.space.discovery` | singleton | discovery/policy/admin | 上一版 state | Space discoverability；MUST NOT 授予读取/加入/解密权限。 |
| `cx.space.policy_server` | singleton | policy/admin | service DID delegation、上一版 state | 绑定 Policy Server。 |
| `cx.space.policy_components` | singleton | policy/admin | 上一版 state | 启用的 policy component 集合。 |
| `cx.space.history_sharing_policy` | singleton | policy/admin | 上一版 state、当前 encryption policy | E2EE 历史共享策略；详见 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md)。 |
| `cx.space.asset_privacy_policy` | singleton | asset_privacy/policy/admin | 上一版 state | 资产隐私策略。 |
| `cx.space.moderation_policy` | singleton | moderation/policy/admin | 上一版 state | Space 审核策略。 |
| `cx.space.plaintext_visible_services` | singleton | privacy/policy/admin | service DID delegation、上一版 state | E2EE 边界外可见服务白名单。 |
| `cx.space.media_service` | singleton | media_service/policy/admin | service DID delegation、上一版 state | 媒体服务绑定。 |
| `cx.space.schema` | singleton | schema/policy/admin | 上一版 state、upgrade policy（如适用） | Space `schema_refs`。 |
| `cx.space.inheritance_policy` | per_subject (`payload.parent_space_id`) | child policy/admin | child Space 的 `cx.space.create`、confirmed parent edge | 父子 Space 继承策略；每个 parent 独立 slot；只在 child Space 写入。 |

未识别的 kind MUST fail closed（标准错误 `schema_violation`），不得静默 accepted。每个 kind 的 payload schema 通过 `event-schema.json` 的 kind 条件分支选择，并引用 `event-payload.schema.json` 中对应 payload 定义。

### 4.2 Space Lifecycle 状态事件

Space lifecycle FSM 的每个 transition 也是独立 event kind。`archive` / `freeze` 可逆，`tombstone` / `destroy` 终态。

| Kind | cardinality | capability tier | 额外 auth refs / guard | 说明 |
| --- | --- | --- | --- | --- |
| `cx.space.archive` | singleton | lifecycle/admin | 当前 lifecycle state、archive policy、未完成 child security-boundary Space / legal-hold / export gate | payload `archived: bool`，可逆。 |
| `cx.space.freeze` | singleton | lifecycle/admin | 当前 lifecycle state、freeze policy、maintenance / incident response constraint | payload `frozen: bool`，可逆。 |
| `cx.space.tombstone` | singleton | owner/governance/admin lifecycle | 当前 lifecycle state、replacement / migration / retention policy | 终态；payload 携带 `replacement_space` / `replacement_event`。 |
| `cx.space.destroy` | singleton | owner/governance/admin lifecycle | 当前 lifecycle state、tombstone / export / retention / legal-hold constraint、无活跃 child Space 和无未决 grant | 终态；不可恢复的 decommission marker。 |

未识别的 lifecycle kind MUST fail closed。同一 kind 的最新 accepted event 决定该 facet 当前状态；终态 kind（`cx.space.tombstone` / `cx.space.destroy`）一旦写入即拒绝后续普通业务写入。

### 4.3 State Slot 主键与 Subject Field

Reducer state slot 主键由 schema registry 中每个 kind 声明的 `state_cardinality` 决定，envelope 不携带 `state_key` 字段：

- `state_cardinality: singleton`：slot 主键为 `(space_id, kind)`，每个 Space 至多一份。
- `state_cardinality: per_subject`：slot 主键为 `(space_id, kind, value-of-state_subject_field)`，subject 由 schema 声明的 payload 字段路径派生（例如 `cx.space.inheritance_policy` 用 `payload.parent_space_id`，`cx.member.state` 用 `payload.actor_id`，`cx.capability.grant` 用 `payload.grant_id`）。
- `state_cardinality: none`（或省略）：非 state event，不参与 state resolution。

新增 facet 时 MUST 在 contract-catalog 中注册新 kind 并声明 cardinality；不得引入"在某 kind 内部用字符串字段再分桶"的二级机制。Subject 类型由 `state_subject_type` 声明（`id:space` / `did` / `string` / `mimi_uri` / `composite` 等）；reducer 在主键派生时 MUST 按声明类型解析，类型不符 MUST `schema_violation` reject。

### 4.4 Component 元信息与 Criticality

每个 state event kind 在 contract-catalog 中显式声明三项 **component 元信息**，使受方能在不识别具体 kind 时仍按声明的策略处理（吸收自 [`draft-ietf-mimi-room-policy`](https://datatracker.ietf.org/doc/draft-ietf-mimi-room-policy/) 的 policy component model）：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `component_type` | URI（`cx.component.<facet-path>.v<n>`） | 稳定标识"这个 state slot 维护的是哪个逻辑状态机"。多个 kind 操作同一逻辑 slot 时 MAY 共享 component_type（例如 `cx.capability.grant` 与 `cx.capability.revoke` 共享同一 grant slot；`cx.profile.create` 与 `cx.profile.update` 共享同一 profile slot）；共享关系 MUST 在 registry 文档中明确。 |
| `component_version` | int | 同一 `component_type` 内部的版本号；语义变化 MUST 升版本。版本不同的 event 不共享 reducer slot；reducer MUST 按 `(component_type, component_version)` 完整匹配。 |
| `criticality` | enum(`required`, `optional`, `ignore`) | 受方在不识别 `component_type` 或 `component_version` 时的默认行为。 |

**Criticality 处理规则**：

- `required`（v1 所有 canonical kind 默认）：受方不识别时 MUST fail closed。具体表现按上下文：直接业务事件 → `schema_violation` reject；historical backfill / state resolution → `quarantine` 直到收到能解析该 component 的实现或显式管理动作；frontier 推进 → `soft_failed`，要求 backfill。
- `optional`：受方不识别时记录 warning 并跳过该 event；事件不参与 state map，但允许 frontier 继续推进。
- `ignore`：受方不识别时静默丢弃；不进入 reducer、state map、审计 projection；本地诊断 MAY 记录 telemetry。

**与 `requirements.critical_extensions` 的优先级**：

每个 Event 的 `requirements.critical_extensions[]` 是 wire-level 显式覆盖。当 event 在该字段声明了 `component_type` 与 `fail_closed=true` 时，无论 registry 默认 criticality 为何，受方 MUST 按 `required` 处理。该机制用于 event 作者声明"即使你的 registry 标 optional，本事件依赖该 component 的语义生效"。

**新增 component_type 的注册流程**：

1. 在 contract-catalog 中注册 kind 与 component metadata（type / version / criticality）。
2. 若 component 横跨多个 kind（共享 slot），在 registry note 字段或 spec 文档中显式声明共享关系。
3. 若 component 引入 wire-breaking 或 reducer 语义变化，MUST 升 `component_version` 并发布过渡 profile。

**Component 升级**：

- 同 `component_type` 内升 `component_version` MUST 通过 `cx.space.upgrade` 显式过渡（参见 §12.1）。受方在 enforcement frontier 之前用旧 component_version 解释，frontier 之后用新 version。
- 跨 `component_type` 替换（罕见，例如重新设计的 facet）按完全独立的 kind 处理，旧 component_type 保留 readable readonly。

### 4.5 离线写入与 frontier 重新校验

v1 不再要求实现支持长期 `partial_auth_state` 与 `soft_failed` 复活机制。设备或 actor 长时间离线后回归时，规则简化为：

- 设备离线超过 reducer profile 声明的 `max_offline_backlog_ms`（v1 默认 30 天）后，提交新 Event 前 MUST 先重新拉取目标 Space 的 frontier、auth state 与最近 grant/revoke 事件。
- 缺少 auth chain、grant 已被撤销、device authorization 已过期、或 actor frontier 已分叉时，新 Event MUST soft-fail 或 quarantine，不得作为 accepted。
- 客户端 MAY 在不能验证完整 auth state 的本地视图上以 `read_only` / `auth_incomplete` 标记展示历史；不得提交依赖未经验证 auth state 的新写入。
- 离线提交的事件本身仍按 §7 规则校验 `created_at` 是否落入 grant/session/device 有效窗口；窗口外的事件 MUST 被 reject 或要求基于最新 frontier 重新提交。
- 服务端 SHOULD 在 frontier 落后导致 backfill 不完整时返回 `dependency_missing` / `temporarily_unavailable`，由客户端按退避重试。

实现 MAY 通过受授权 snapshot manifest、witness receipt 或合规审计 service 加速 frontier 重建；这些机制必须经过 §4 的 snapshot-assisted auth ref 验证流程，不得替代签名责任。

## 5. Membership

Contrix 使用 `cx.member.state` 表达 actor 在 Space 中的成员状态。reducer 按 schema registry 声明的 `state_subject_field=payload.actor_id` 派生 state slot 主键 `(space_id, "cx.member.state", actor_id)`：

```json
{
  "kind": "cx.member.state",
  "payload": {
    "actor_id": "did:web:actor.example.com",
    "membership": "join",
    "via": [
      "did:web:example.com"
    ],
    "reason": "invited",
    "invite_ref": "event:..."
  }
}
```

`membership` 取值：

- `join`
- `invite`
- `knock`
- `leave`
- `ban`

合法状态迁移：

| From | To | 条件 |
| --- | --- | --- |
| none | join | `join_rule=public`，或 actor 持有可验证 invite/restricted join proof |
| none | invite | inviter 持有 invite capability |
| none | knock | `join_rule=knock` 或 `knock_restricted` |
| invite | join | 被邀请 actor 接受，且未被 ban |
| invite | leave | 被邀请 actor 拒绝，或 inviter/admin 撤销 |
| knock | invite | 有 invite capability 的成员接受 knock |
| knock | leave | knocking actor 撤回，或 admin 拒绝 |
| join | leave | actor 自己离开，或有 kick capability 的成员移除 |
| join | ban | 有 ban capability |
| leave | invite | inviter 持有 invite capability |
| ban | leave | 有 unban capability |

被 ban 的 actor MUST NOT 发送除 appeal/profile-level 之外的 Space 写事件。

### 5.1 Flow Discussion Membership

Flow discussion branch membership 是 branch `access` 的显式 override 形态。默认情况下，discussion branch 继承 Flow / Space 的有效访问规则；只有 `branches[]` 中 `name="discussion"` 的 branch 声明 `access.membership="branch_scoped"` 或等价 policy state 生效时，`cx.flow.branch.member` 才作为 Space membership 之下的局部参与状态，用于控制某个 Flow discussion 的发言、阅读、通知和历史访问。它不授予 Space-wide 可见性，也不自动授予 Flow synthesis、Space (kind=board)/Space (kind=list) 或 Morph 的权限。

Contrix 使用 `cx.flow.branch.member` 表达 actor 在 Flow discussion branch 中的成员状态。reducer 用复合 subject `(flow_id, branch, actor_id)` 派生 state slot 主键 `(space_id, "cx.flow.branch.member", flow_id, branch, actor_id)`：

```json
{
  "kind": "cx.flow.branch.member",
  "payload": {
    "flow_id": "cx:flow:01js0r00m00000000000000000",
    "branch": "discussion",
    "actor_id": "did:web:actor.example.com",
    "membership": "join"
  }
}
```

规则：

- 默认情况下，discussion member MUST 同时是所在 Space 的 member。
- Space policy MAY 允许 discussion-scoped external admission。此时外部 actor 只获得该 discussion 的受限访问，不获得 Space directory、Space (kind=board)/Space (kind=list)、Flow synthesis 或其他 discussion 的可见性。
- `cx.flow.branch.member` 只授予 branch-scoped discussion membership；它不复制 `cx.flow.update`、`cx.flow.move`、`cx.space.*` 或 grant 管理权限。
- Flow synthesis 可见只有在有效 access policy 继承或授予 discussion 读取时，才代表 discussion timeline 可读；discussion 可读也不代表 synthesis 可写。
- `promoted_from_discussion` 等 relation 只表达沉淀来源，不传播 membership、E2EE epoch 或 history visibility。

## 6. Discovery, Join Rule and History Visibility

`cx.space.discovery` 控制 Space 是否能被目录、搜索、父 Space 或组织页发现。完整规则见 `discovery-directory.md`。

`discoverability` 取值：

- `public`：可被公共目录索引和搜索。
- `listed`：可在指定目录、组织页或父 Space 中列出。
- `restricted`：只有满足可验证条件的请求方可发现。
- `unlisted`：不进入搜索，但可凭精确 id、alias、邀请或允许的 parent edge 解析。
- `invite_only`：未被邀请或未持有 invite proof 的主体不得得知其存在。
- `secret`：仅本地或端到端加密上下文中可见。

`cx.space.discovery` 不授予读取、加入、写入或解密权限。节点和目录服务 MUST NOT 用 `join_rule` 或 `history_visibility` 推断 discoverability。

### 6.1 Discoverability × Join Rule 兼容性矩阵

`discoverability` 与 `join_rule` 是正交决策（"能否被发现"独立于"如何加入"），但不是任意组合都有意义。Reducer 接受 Space create / `cx.space.discovery` / `cx.space.join_rule` 时 MUST 在两者收敛后按下表校验有效组合；对 `forbidden` 组合 MUST `schema_violation` reject，不得静默规范化或暗中提升 join_rule。

`✓` = 允许；`-` = 不允许（reject）；`!` = 允许但语义低效（reducer 只警告，profile MAY 收紧为 reject）。

| ↓ discoverability \ join_rule → | `public` | `invite` | `knock` | `restricted` | `knock_restricted` | `closed` |
| --- | :---: | :---: | :---: | :---: | :---: | :---: |
| `public` | ✓ | ! | ✓ | ✓ | ✓ | - |
| `listed` | ✓ | ✓ | ✓ | ✓ | ✓ | ! |
| `restricted` | ! | ✓ | ✓ | ✓ | ✓ | ! |
| `unlisted` | ! | ✓ | ✓ | ✓ | ✓ | ✓ |
| `invite_only` | - | ✓ | - | - | - | ✓ |
| `secret` | - | ✓ | - | - | - | ✓ |

规则解释：

- `public` join_rule + 非 `public/listed` discoverability：`public` join 意味着任何 actor 可 join，与"主体不可被发现"自相矛盾；只有 `restricted/unlisted` 在 reducer 警告语义下允许（用于过渡迁移），`invite_only/secret` 必须 reject。
- `invite_only` / `secret` discoverability + `public/knock/restricted/knock_restricted` join_rule：被邀请前不能得知 Space 存在，因此不能允许 knock 或 selector-based 加入；只允许 `invite` 或 `closed`。
- `closed` join_rule：不接受任何普通加入。配合 `public` discoverability 矛盾（"能搜索到但永远进不去"），MUST reject；配合 `listed` 是低效（warning）；其他组合允许（用于归档、维护或迁移已结束的 Space）。
- `restricted` / `knock_restricted` join_rule 需要 selector 证明，前提是 actor 知道 Space 存在；因此与 `invite_only/secret` 不兼容。

实现 SHOULD 在 Space create 与每次 `cx.space.discovery` 或 `cx.space.join_rule` 收敛后立即校验，避免在后续操作中才发现非法组合；reducer 在历史 backfill 中遇到 `forbidden` 组合 MUST 把对应 policy event 标记为 `rejected` 而非静默接受。

### 6.2 Join Rule

`cx.space.join_rule`:

- `invite`：只允许 invite。
- `public`：任何 actor 可 join，但仍需通过 policy server 和 rate limit。
- `knock`：外部 actor 可 knock，不可直接 join。
- `restricted`：actor 必须满足 `allowed_selectors` 中至少一个可验证条件。
- `knock_restricted`：不满足 restricted 条件者可 knock。
- `closed`：不接受普通加入、knock 或 invite accept；只允许迁移、维护或管理员明确声明的例外流程。

Canonical event、Space object 和 JSON Schema MUST 使用 `invite` 表示邀请加入。任何不在该 enum 内的取值都是无效输入，接收方 MUST 按 `schema_violation` reject，不得静默映射为合法 enum 值，否则会掩盖签名 payload 与 policy intent 的差异。Matrix-style import 或 bridge 必须在写入前显式映射到本枚举值，并以新签名事件提交。

### 6.3 History Visibility

`cx.space.history_visibility`:

- `world_readable`：任何 actor 可读取明文或已授权公开内容。
- `shared`：当前和历史成员可读取加入前历史。
- `invited`：被邀请 actor 可读取 stripped preview state。
- `restricted`：只有满足 Space policy 中 `allowed_selectors`、claim、capability 或等价 history access proof 的 actor 可读取加入前历史或 stripped state；无法验证时 MUST 按 `joined` 或更严格规则 fail closed。
- `joined`：仅加入后历史默认可见。

E2EE Space 或通过 branch-scoped access override 启用 E2EE 的 Flow discussion branch 中，history visibility 只授权索引和密钥共享资格，不保证服务端能解密历史。`restricted` 不授予 discoverability、join 权限或自动密钥下发；它只让满足证明的 actor 进入 pre-join history 和 E2EE key share eligibility 的候选集合。

`cx.space.history_sharing_policy` 控制 E2EE Space 或 branch-scoped E2EE discussion 是否允许新成员获取加入前的解密材料。完整 schema、共享路径与审计要求见 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §3 及 minimal-metadata profile 规则。本节只重申 auth state 边界：

- 历史 key share MUST 绑定接收 principal、接收 device、epoch / range、policy hash、审计事件和发送设备签名。
- `requires_audit_event=true` 时，发送设备必须先写入 `cx.space_key.share_audit` 或等价审计事件，并等待因果确认后再发送历史 key material。
- policy 变更只影响变更后发起的共享动作，不追溯授权已经发送给既有成员的历史解密材料。

### 6.4 Policy Components

`cx.space.policy_components` 把复杂 Space 策略拆成可独立演进的组件，避免把所有布尔开关塞进单个 policy 对象：

```json
{
  "kind": "cx.space.policy_components",
  "payload": {
    "components": {
      "roles": "cx:event:01js0r01es0000000000000000",
      "preauth": "cx:event:01js0preav0000000000000000",
      "asset": "cx:event:01js0asset0000000000000000",
      "logging": "cx:event:01js010gg10000000000000000",
      "bot": "cx:event:01js0b0tag0000000000000000",
      "message_expiration": "cx:event:01js0expry0000000000000000",
      "operational": "cx:event:01js0perat0000000000000000",
      "history_sharing": "cx:event:01js0hstry0000000000000000"
    },
    "component_root": "sha256:canonical_component_set"
  }
}
```

组件语义：

- `roles`：把 UI role 或 profile role 映射到 capability bundle；role 不能替代 capability 检查。
- `preauth`：预授权加入、邀请链接、knock 审批和一次性 join token。
- `asset`：附件上传域、下载隐私、proxy/OHTTP 要求和媒体大小/类型限制。
- `logging`：消息保留、导出、审计、合规可见性和删除边界。
- `bot`：bot / Applet / bridge / agent 是否允许加入，是否必须标识为 automated actor。
- `message_expiration`：消息过期、tombstone、legal hold 和本地清理提示。
- `operational`：限流、fanout、最大成员数、最大附件数、服务故障处理。
- `history_sharing`：加入前历史和 MLS epoch key material 的共享规则。

`component_root` SHOULD 被 `cx.mls.commit.application_state_ref.policy_root` 覆盖。客户端如果支持 E2EE 且无法验证组件根，MUST fail closed，至少不得接受依赖未知组件的新写入或 MLS epoch。

### 6.5 Plaintext-Visible Services

`cx.space.plaintext_visible_services`：非 E2EE / 非内容加密的私有 Space 若允许服务端处理正文或可逆派生内容，必须显式声明可见服务。完整 schema、撤销语义与透明度要求见 [`sync/service-surface.md`](../sync/service-surface.md)。本节只列 auth state 行为：

- `service_did` 必须可解析，并通过 DID service、组织背书或 Space policy 委托绑定到对应 `service_type`。
- 未列入该 state event 的服务只能接收公开内容、密文 envelope、不可逆 hash、最小 routing metadata 或 policy 明确允许的 stripped preview。
- 该 state event 的撤销或覆盖按普通 state resolution 生效；生效点之后不得继续向已撤销服务发送非加密私有内容。
- 该 state event 是成员可验证的透明度机制；高安全 Space SHOULD 使用 E2EE、minimal-metadata profile 或本地客户端索引，而不是 admin-only 隐藏明文服务清单。

### 6.6 Organization Ownership and Endorsement

组织所有权由组织 principal 的可验证声明表达。`cx.space.create.payload.object` 提供 `created_by_principal` 与 `owning_organizations`；后续认可通过 `cx.space.organization` state event 发布或撤销（`relationship` ∈ `owner / sponsor / host / issuer`，`status` ∈ `active / revoked / suspended / transferred`）。

客户端将 Space 展示为某 Organization 官方认可时 MUST 同时验证：

1. Organization DID 可解析，且 DID Document / key log 在事件时间有效。
2. `cx.space.create.payload.object.created_by_principal` 是该 organization DID，或存在 active 的 `cx.space.organization` event。
3. `cx.space.organization` 的签名 key 属于 organization DID 的当前或事件时点有效控制链，或属于 organization DID 明确绑定的 governance service DID。
4. `relationship` 为 `owner` 或 `sponsor`，且 `scope.official=true`。
5. 该声明未过期、未被 `status=revoked` 或后续同 state slot 的 state event 覆盖。
6. Space id、Space create event hash 和 organization DID 都被签名覆盖，防止把同一声明移植到另一个 Space。

客户端 MUST NOT 仅凭 Space 名称、域名、handle、托管服务或成员组成把 Space 展示为 official。完整背书 schema、`scope.allowed_labels` 和撤销过渡规则见 [`identity/identity-did.md`](../identity/identity-did.md) Organization 章节。

## 7. Authorization Algorithm

对事件 `E`，节点 MUST：

1. 构造 auth state map：以 `(kind, subject?)` 为 key（subject 由 schema registry 的 `state_subject_field` 派生；singleton kind 仅 `(kind)`），从 `auth_refs` 解析授权状态。
2. 验证所有 auth event 本身为 accepted，或在当前 state resolution 中被接受。
3. 验证 sender 的当前 membership。
4. 验证 sender 的 device 是否在事件时间有效，且未在 `created_at` 前撤销。
5. 验证 sender 持有 action 对应 capability；capability subject MUST 匹配 DID 或满足 selector。
6. 验证 capability constraint：时间、空间、对象、字段、速率、审批、设备、Applet 范围。
7. 验证 event kind 的专用规则。
8. 验证 policy server hard deny、server ACL、ban list 与本地 quarantine list。

授权计算 MUST 使用事件被接受时的因果 auth state，而不是接收时间的最新状态。`created_at` 只用于校验签名 key、claim、grant 有效期和时钟窗口，不得让缺少因果前序或 actor_seq 回退的事件绕过 revoke。撤销事件只影响其 causal frontier 之后的事件；若业务事件与相关 revoke 的顺序无法通过 `prev_refs`、`actor_seq` 和 HLC 确定，节点 MUST fail closed、soft fail 或进入 review。

离线写入重新上线时，节点必须同时验证事件自身 `created_at` 位于 grant / session / device 的有效窗口内，以及 `auth_refs` 所声明的 grant frontier 未被该事件因果已知的 revoke 覆盖。若设备离线期间 grant 已过期，但事件 `created_at` 早于 `expires_at` 且 actor chain、HLC drift、device validity 和 revoke freshness 都可验证，事件 MAY 被接受；若无法证明该事件早于 revoke / expiry 的有效 frontier，MUST soft-fail、quarantine 或要求用户基于最新状态重新提交。实现 SHOULD 对离线队列声明最大积压窗口（默认 30 天，见 §4.5）。

## 8. State Events

State event 是 schema registry 中声明 `state_cardinality` 的事件。其当前状态由 reducer 按 cardinality 派生主键后取最新 accepted 事件决定（singleton: `(space_id, kind)`；per_subject: `(space_id, kind, subject)`，subject 取自 `state_subject_field`）。

v1 标准 state event：

| Kind | cardinality | subject 来源 |
| --- | --- | --- |
| `cx.space.create` | singleton | — |
| `cx.space.policy` / `cx.space.join_rule` / `cx.space.history_visibility` / `cx.space.discovery` / `cx.space.policy_server` / `cx.space.policy_components` / `cx.space.history_sharing_policy` / `cx.space.asset_privacy_policy` / `cx.space.moderation_policy` / `cx.space.plaintext_visible_services` / `cx.space.media_service` / `cx.space.schema` | singleton | — |
| `cx.space.inheritance_policy` | per_subject | `payload.parent_space_id` |
| `cx.space.child` | per_subject | `payload.child_space_id` |
| `cx.space.parent` | per_subject | `payload.parent_space_id` |
| `cx.space.organization` | singleton | — |
| `cx.space.upgrade` | per_subject | `payload.target_reducer_profile` |
| `cx.space.archive` / `cx.space.freeze` / `cx.space.tombstone` / `cx.space.destroy` | singleton | — |
| `cx.member.state` | per_subject | `payload.actor_id` |
| `cx.flow.branch.member` | per_subject | `(flow_id, branch, actor_id)` 复合 |
| `cx.flow.branch.history_visibility` / `cx.flow.branch.policy_components` | per_subject | `(flow_id, branch)` |
| `cx.capability.grant` / `cx.capability.delegate` / `cx.capability.revoke` / `cx.capability.derived` | per_subject | `payload.grant_id`（revoke 与 grant 共用同一 slot） |
| `cx.policy.rule` | per_subject | `payload.rule_id` |
| `cx.device.authorized` / `cx.device.revoked` | per_subject | `(principal_id, device_id)` |
| `cx.device.list_update` | per_subject | `payload.principal_id` |
| `cx.session.grant` | per_subject | `payload.grant_id` |
| `cx.account.status` | per_subject | `payload.principal_id` |
| `cx.profile.create` / `cx.profile.update` | per_subject | `payload.object.id` |
| `cx.view.create` / `cx.view.update` / `cx.view.reconcile` | per_subject | `payload.view_id` |

非 state 但参与 reducer / 审计的 moderation event（cardinality=none，按事件 id 收敛）：

- `cx.moderation.report`：举报事件，参与 moderation 队列与 quarantine projection。
- `cx.moderation.frank`：franking proof，参与 E2EE 滥用举报审计；不进入 capability state map。
- `cx.policy.action`：policy / governance action proposal or execution，可用于解除 state conflict quarantine；不默认进入 capability state map，除非具体 Space policy 把它声明为某业务事件的 auth dependency。
- `cx.audit.accessed`：auditable E2EE 解密承诺事件；详见 `crypto-media/encryption-and-audit.md` §3。
- `cx.audit.ryw_receipt`：Read-Your-Writes receipt（可选 ephemeral 或 durable）。

`cx.device.*` 和 `cx.session.grant` 是 principal-scoped state event。它们只在 principal control Space 的 state map 中解析；普通协作 Space MAY 通过 `auth_refs`、snapshot reference 或 policy server proof 引用该 state，但不得把另一个 principal 的设备/会话事件写入任意协作 Space history 来改变其身份状态。

principal control state 的 subject 由 schema registry 声明的 `state_subject_field` 从 payload 派生：

- `cx.device.authorized` / `cx.device.revoked`：subject 是 `(payload.principal_id, payload.device_id)` 复合。两 kind 共享 slot，revoke 表达为对该 slot 的 supersede。
- `cx.device.list_update`：subject 是 `payload.principal_id`。
- `cx.session.grant`：subject 是 `payload.grant_id`。

capability 相关 state event 的 subject 同样由 payload 派生：

- `cx.capability.grant`：subject 是 `payload.grant_id`（`cx:grant:<ulid>`）。后续 grant lifecycle 事件（含 condition refresh、approval recording 等）若 reuse 同一 `grant_id`，会按 §9 state resolution 与该 slot 收敛。
- `cx.capability.revoke`：subject 是 `payload.grant_id`，与对应 grant **共用同一 slot**，从而把 revoke 表达为对 grant slot 的 supersede（payload `revoked: true` / `revoked_at`）。reducer 在解析 `(kind=cx.capability.grant, grant_id)` 这个 slot 时，MUST 取最新 accepted 事件，无论其 kind 是 grant 还是 revoke。注意 reducer 把 `cx.capability.grant` 与 `cx.capability.revoke` 视作同一逻辑 slot 的两种 supersede 写入；contract-catalog 把这种关系标记为 slot 别名（参见 `state_subject_field` 与说明）。
- `cx.capability.derived`：subject 是 `payload.grant_id`（derived grant 自身的 `cx:grant:<ulid>`，与 source grant 不同的独立 ID）。derived event 是物化继承授权的协议事件，详见 `models/space-hierarchy.md` §7。auth_refs MUST 包含：source grant 的 accepted `cx.capability.grant` 事件、target child Space 的 confirmed parent 边、child 的 `cx.space.inheritance_policy`（subject=该 parent space id）。

委托链 / 派生链 revocation 传播规则：

- 撤销某 grant `G_parent`（即在 `["cx.capability.grant", G_parent.grant_id]` 上写入 `cx.capability.revoke`）后，所有 `parent_grant_id == G_parent.grant_id` 的子 grant **自动失效**，无需逐条额外写入 `cx.capability.revoke`。reducer 在评估子 grant 时 MUST 沿 `parent_grant_id` 反向追溯，若链上任一祖先的 grant slot 当前为 revoked 状态，则该子 grant 视为不可用。
- 同样，被任一 `cx.capability.derived` 事件引用的 source grant 一旦 revoke，在 source grant 的 revoke 事件因果后继中，所有引用它的 derived state slot MUST 视为失效；reducer MAY 通过显式发布带 `revoked: true` 的 `cx.capability.derived` 事件把该失效物化进 child 历史，但即使没有显式事件，cache 与评估器 MUST 把它视作不可用。
- 子 / derived grant 的 cache entry MUST 同步标记 stale。若某子 grant 需要在父被撤销后继续生效，签发方 MUST 重新发布一条不依赖该父 grant 的 grant，而不是依赖派生计算保持兼容。

实现不得使用 pipe 字符串、数据库自增 ID、HTTP receive order 或其它非确定性来源参与 state resolution。

State event 不等于 auth state dependency。`cx.view.*` 等投影定义事件可以使用 state resolution 形成当前 View 定义，但默认不进入 capability / membership / policy / MLS 的 auth state map；只有当某个 View 被 policy 明确声明为授权依赖、审计依赖或 materialized query contract 时，相关 View state event 才能作为对应业务事件的 `auth_refs`。非 state event 仍可影响物化 projection，但不进入 auth state map，除非具体类型声明其为 auth dependency。

每个 MLS group 的当前 epoch 由 winner `cx.mls.commit` 的 `next_epoch` 字段直接表达；v1 不再注册独立的 `cx.mls.epoch` event 或单独 epoch state key。具体推导规则见 `../crypto-media/encryption-and-audit.md` 第 2.4 / 2.5 节。

### 8.1 E2EE Space 的 State Binding

声明 `encryption_profile="mls_rfc9420"` 的 Space MUST 实施 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.5 定义的 MLS state binding。该 binding 把 `cx.profile.mls_state_binding.full.v1` 从可选 hardening 提升为 E2EE 必需，规则要点：

- 每个 `cx.mls.commit` MUST 携带 GroupContext extension 形态的 `application_state_ref`，覆盖 `policy_root` / `membership_frontier` / `capability_root` / `discussion_metadata_hash`。具体覆盖的 `component_type` 列表由 `cx.profile.mls_state_binding.full.v1` 的 `policy_root_required_components` / `membership_frontier_required_components` / `capability_root_required_components` 字段声明。
- E2EE Space 中的 state event 在协议层 accepted 后处于 `pending_mls_binding`（见 §11），直到被某个 winning `cx.mls.commit` 的 `application_state_ref` 覆盖才进入 **covered frontier**。
- Covered frontier 才是 E2EE Space 中"权威 state"的真正边界：撤销 / ban / policy 收紧只在 covered frontier 上才阻止后续 application messages 解密；`pending_mls_binding` 期间的旧 epoch 消息仍可能被持有 epoch key 的 actor 解密。
- 当 accepted frontier 与 covered frontier 之间的滞后超过 `max_mls_commit_delay_ms`（默认 30,000 ms）时，该 E2EE scope MUST 进入 `epoch_update_required`：暂停发送新 application messages（`security_class=high_assurance` 是 MUST，其他是 SHOULD），直到补齐 commit。
- 并发的 state event 与 §9 state resolution 的关系不变：state resolution 仍按 deterministic 算法选 winner / quarantine 候选；只是 winner 还需要进入 covered frontier 才能影响 E2EE 加密路径。
- 非 E2EE Space 不受本节约束；其 state event 在协议层 accepted 即生效。

## 9. State Resolution

当多个分支对同一 state slot 给出不同 accepted state event 时，节点 MUST 运行 deterministic state resolution。

Contrix 的 state resolution 设计前提与 Matrix 不同：

- 所有 Event 都由 actor / device / service DID 签名；服务端无法伪造签名。
- 因果由 `prev_refs` + `actor_seq` 显式表达；HLC 提供物理时间约束。
- 撤销与失效由 `cx.capability.revoke` / `cx.member.state` 等显式状态事件表达。

因此 v1 state resolution 不需要 Matrix 风格的 lattice authority + governance layer scoring + conflict winner reconstruction。一个真正"分叉"对同一 state slot 写入两个互斥事件，是协议异常，应交给管理员或自动 quarantine，而不是用一个权重表自动选边。

### 9.1 输入

- `base_state`：最近共同祖先 state map。
- `state_sets`：各分支 state map。
- `auth_chain`：所有候选 state event 的 auth dependency 闭包。

### 9.2 输出

- `resolved_state`：单一 state map。
- `conflict_records`：被压制候选及原因。

### 9.2.1 规模上限与 Snapshot Fallback

State resolution MUST 受 `../conformance/scalability-constraints.md` 的上限约束。默认 v1 限制包括：

- 单个 state key 的 conflict candidate 数最多 256。
- `auth_chain` 闭包深度最多 64。
- `auth_difference` 事件数最多 4,096。
- 单个事件 `auth_refs` 数最多 64。

超过上述限制时，节点 MUST 使用最近可验证 snapshot 作为 `base_state` 执行 snapshot-assisted resolution，或将依赖事件保持 `soft_failed` / `quarantined`，不得继续无界展开 auth chain。fallback snapshot 必须验证 signer authority、frontier、state hash 和 chunk digest。没有可验证 snapshot 时，节点 MUST fail closed；不得使用本地接收顺序、数据库自增 ID 或 Sync Service 到达顺序裁决 winner。

### 9.3 算法（quarantine-on-fork）

1. 将所有 state set 中相同 state slot 且 event id 相同的项放入 unconflicted state。
2. 将不同 event id 的候选放入 conflicted set。
3. 计算 auth difference：见 §9.4。
4. 对 auth difference 先排序并授权，得到 provisional auth state。
5. 对每个冲突 state slot：
   - **仅一个候选** 通过签名、schema、causal dependency、`auth_refs` 与 policy hard deny：该候选直接进入 resolved state，其余候选作为 `rejected` 记入 conflict_records。
   - **多个候选** 同时通过授权检查：
     - 若候选之间存在严格因果先后关系（一个候选的 `auth_chain` 完整覆盖另一个 + HLC > 对方），causal-后者作为 winner，前者作为 superseded 记入 conflict_records。
     - 若候选并发（无因果先后），reducer MUST 使用 `(causal_depth desc, HLC desc, actor_id asc, event_id asc)` 作为确定性 tie-break 选择 winner，但**同时** MUST 把所有非 winner 候选标记为 `quarantined`，并要求 admin / governance / policy server 在 quarantine 解除前不得让该 state key 进入普通 projection。换言之，并发 fork 不会被自动消化为安静的 winner-loser，而是产生显式 admin review item。
     - quarantine winner 的展示必须附带 conflict 诊断和被压制候选 id；客户端 UI MUST 显示 "state conflict pending review" 或等价标记。
   - **零候选** 通过授权：回退到 `base_state`，若无 base 则该 key unset；候选作为 `rejected` 记入 conflict_records。
6. 输出 conflict_records。索引器 SHOULD 暴露给审计视图。
7. quarantine 状态由后续 admin 写入的 `cx.policy.action`（`payload.action="state_conflict_resolution"`，并绑定目标 state slot 与被采纳 `event_id`）或等价管理事件解除；解除后被选中的 winner 进入 normal projection，其余候选保留为审计记录。

该算法 MUST deterministic。任何实现不得使用本地接收顺序、数据库自增 ID 或 Sync Service 顺序作为 tie-breaker。

HLC 只能在候选事件已通过格式、签名、授权、时钟窗口和 causal dependency 检查后参与排序。`created_at`、HTTP receive time、provider timestamp 或外部桥接时间戳不得替代 HLC，也不得单独作为授权或 winner 依据。

> Rationale: v1 之前曾使用一个二维 lattice (governance_layer × authority_kind) 选择 winner，并引入 `auth_weight` scalar 派生表。这是 Matrix room state v2/v11 风格的复杂性继承。Contrix 已经通过 capability + revoke + actor signature 表达了授权权威；在同一 state slot 同时被多份合法签名的并发 fork 上自动选边并不能正确反映组织治理意图（admin 应当显式介入），还增加了所有实现的测试矩阵。v1 选择 quarantine-on-concurrent-fork 替代该 lattice：审计透明、决定性、便于实现、保留 admin 治理 hook。需要更复杂决策权重的部署 MAY 在未来通过 hardening profile 单独引入加权 lattice；它不再属于 core 互操作。

### 9.4 Auth Difference

`auth difference` MUST 使用集合算法计算，不得依赖遍历顺序：

```text
auth_chain(e):
  result = {}
  stack = e.auth_refs
  while stack not empty:
    a = pop(stack)
    if a not in result:
      result.add(a)
      stack.extend(a.auth_refs)
  return result

auth_difference(conflicted_events):
  chains = [auth_chain(e) for e in conflicted_events]
  common = intersection(chains)
  diff = union(chains) - common
  return diff
```

实现 MUST 对 `diff` 中的事件按 state resolution 的 deterministic ordering 排序后再验证授权。若某个 auth event 缺失、hash 不匹配或自身不能 accepted，依赖它的候选事件 MUST soft-fail 或 fail closed，不能把缺失 auth 当作允许。

Policy hard deny、ban、quarantine、unknown critical feature、缺失必要 approval、未知 critical constraint、claim revocation 无法确认且该 claim 为必要条件时，候选事件 MUST 在 §9.3 的授权检查阶段 fail closed、soft fail 或 quarantine。它们不得通过任何"权重"或"优先级"被覆盖。

## 10. Redaction

`cx.redaction` 是 state-independent event，但其效果由 reducer 应用到目标事件。

`cx.message.redact` 与 `cx.redaction` 的边界如下：

- `cx.message.redact` 是 Message 专用 redaction。生产者在撤回 Flow discussion Message、Message revision 或 Message reaction projection 时 SHOULD 使用它；payload MUST 指向 `message_id`、`target_ref` 或目标 `event_id`，并携带可审计原因。
- `cx.redaction` 是通用 redaction envelope，用于非 Message 对象、任意 Event payload、附件引用或 profile 声明的内容裁剪。
- 两者不是互相扩大权限的别名。授权仍按目标对象、目标 Event、actor 和 capability 独立判定；拥有 `cx.message.redact.own` 不等于拥有通用 `cx.redaction`。
- 若两类 redaction 指向同一目标，reducer MUST 幂等地应用同一 redaction effect，并在审计视图保留多个 redaction event 的 event id、actor 和 reason。

被 redaction 后，事件只保留以下 envelope 顶层字段（**验证性 redaction stub** 的默认集合）：

- `event_id`
- `space_id`
- `kind`
- `state_subject`（仅 per_subject state event；redaction 前由 reducer 从 `state_subject_field` 派生并提升到 stub 顶层，使 redaction 后仍能定位 state slot）
- `actor_id`
- `actor_seq`
- `created_at`
- `hlc`
- `prev_refs`
- `auth_refs`
- `redacts`（若本身就是 redaction event）
- `proofs`
- `redacted_by`
- `redaction_reason_code`

`actor_seq` 与 `prev_refs` 必须保留，否则后继事件无法验证 actor chain 因果连续性。`proofs[].payload_hash` 也必须保留，否则后续节点无法在不重新生成 canonical bytes 的情况下验证签名绑定。

实现 MUST 在签名时刻保存原 envelope 的 canonical digest（`event_digest`），存储位置由实现决定，但在以下场景必须可重新提供：（a）通过 `auth_refs` 引用该事件时；（b）联邦 backfill 返回 redacted stub 时；（c）审计审查链验证时。`event_digest` 不出现在 redacted stub 顶层，因为它已等价于 `proofs[].payload_hash`。

上述保留字段是验证性 redaction stub 的默认集合。Space / reducer profile MAY 声明 `redaction_policy="anonymous"`，但该策略只影响普通 timeline、search、export preview 等用户可见 projection：这些 projection MUST 隐藏或替换原事件 `actor_id` / 物化对象 `created_by`。它不得从 canonical verification stub 中删除 `actor_id`、`proofs`、`actor_seq`、`prev_refs` 或 `auth_refs`，否则接收方将无法验证原始 Event chain、redaction 授权和审计责任。需要更强发送者隐私的 Space SHOULD 使用 pairwise DID / minimal-metadata E2EE；需要物理删除身份 metadata 时必须走 hard erasure receipt 和 legal-hold 边界，而不是重写已签名 Event。

以下 envelope 顶层字段 MUST 整体清除：

- `payload`（其中包括 `attachments`、`mentions`、`relations`、`client_generated`、对象正文等所有内容）
- `unsigned`
- `requirements`（仅在 redaction policy 声明 minimal-metadata 时清除；普通 redaction 保留整个 `requirements` 对象）

普通 redaction 默认保留 `requirements`，使下游能继续判断该 event 是否依赖未知 critical 语义。Minimal-metadata profile 的 redaction 才完全清除该字段。

Redaction 不保证物理删除。Blob 删除、密钥销毁和法律擦除由 `media-and-blob.md` 与 `account-lifecycle.md` 定义。

### 10.1 Redaction 与 Erasure

Redaction 是协议层可验证内容裁剪；Erasure 是某个存储边界内的物理删除或数据最小化流程。实现和 UI MUST 区分二者，不能把 redaction 描述为全网物理删除。

当 Space policy、account lifecycle、legal request 或 retention policy 要求 hard erasure 时，服务 MAY 在本地删除原始 payload bytes、blob bytes、缩略图、全文索引、embedding、preview 和可逆派生内容，但必须满足：

1. 已存在 accepted 的 `cx.redaction`、`cx.account.status{status="erasure_pending"}`、signed erasure receipt、retention expiry 或等价可审计授权依据。
2. 没有 active legal hold、审计保全或组织保留策略阻止删除。
3. 保留最小 verification stub：`event_id`、验证事件图所需的原始 Event envelope digest / proof `payload_hash`、redaction event id、erasure reason code、执行服务 DID、执行时间和签名 receipt。
4. 不得重写原事件 hash、签名或 causal refs；backfill 返回 redacted / erased stub，而不是伪造一个新事件或静默缺失。
5. 派生服务（Search、Embedding、Thumbnail、Notification preview 和其他受托 projection）必须按同一 erasure receipt 重新判定并删除或最小化派生内容。

Hard erasure stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest、未加盐搜索 fingerprint 或其他可对低熵内容离线枚举的验证物。若审计场景必须在擦除前承诺某段明文内容，必须使用每事件随机 salt 的 commitment 或服务持有的 HMAC/pepper commitment；salt / pepper 不得随普通 stub 分发，且在 erasure policy 要求不可恢复时必须销毁或转入 legal-hold 边界。

原始 Event envelope digest / proof `payload_hash` 可能已经被复制到其他节点、receipt 或审计日志中，因此 hard erasure 不能承诺从全网移除所有哈希痕迹。对短小、可预测的私密明文，Space SHOULD 使用 E2EE 或内容加密 payload profile，使持久 verifier 只暴露密文 digest 或不可逆路由 hash，而不是明文内容 digest。

对于 E2EE 内容，密钥销毁或停止共享只能阻止后续访问；已经被成员解密、导出或复制的明文不受协议保证。客户端和合规文档 MUST 明确这一点。

## 11. Soft Fail, Reject, Quarantine, Pending MLS Binding

- `soft_failed`：格式和签名有效，但缺上下文或暂时无法授权。可参与 backfill，不进入用户可见状态。
- `rejected`：格式、hash、签名、schema 或授权确定失败。不得进入 reducer。
- `quarantined`：基础授权可过，但被本地/联邦策略标记为高风险，或为 §9.3 并发 fork 的非 winner 候选。不得自动展示，可供管理员审查。
- `pending_mls_binding`（仅 E2EE Space）：协议层 accepted，但尚未被任一 winning `cx.mls.commit` 的 `application_state_ref` 覆盖。详见 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.5.1。该 state event 进入 reducer accepted set 推进 frontier，但 MUST NOT 影响 E2EE 解密 / key share / 新 application message 加密 epoch；也 MUST NOT 作为权威 state 展示给最终用户，直到对应 commit 把它纳入 covered frontier。

Soft failed state event MAY 在后续上下文补齐后重新评估。Rejected event MUST NOT 自动复活，除非重新提交为新 event。Quarantined event 由管理员显式释放或最终拒绝。

Frontier 与存储语义：

- `accepted` Event 才能推进 actor accepted frontier、Space reducer frontier、state hash 和 materialized projection。
- `soft_failed` Event MAY 进入 pending store、backfill 队列和诊断 API，但 MUST NOT 推进 accepted frontier、state hash 或用户可见 projection。上下文补齐后重新评估通过时，才以原 `event_id` 进入 accepted set。
- `rejected` Event MUST NOT 推进 accepted frontier，也不占据 accepted actor chain 中的 `actor_seq`。实现 MAY 保存 rejected envelope 的最小诊断记录或 abuse evidence，但不得把它返回为 accepted history；客户端展示时 MUST 标注为 rejected diagnostic，而不是普通事件。
- `quarantined` Event MUST NOT 自动进入 reducer 或普通 sync。管理员、policy server 或异步验证将其释放后，必须重新执行完整 validation，并以原 `event_id` 进入 accepted set；若最终拒绝，按 rejected 处理。
- 如果 actor 后续提交的 Event 以 soft-failed / quarantined / rejected Event 作为 `prev_refs`，接收方 MUST soft-fail 或 quarantine 后续 Event，直到该前序进入 accepted set；不得因为后续事件签名有效而跳过缺失或无效前序。
- 对同一 `event_id` 的相同 canonical bytes 重试保持幂等。对同一 `event_id` 的不同 canonical bytes，节点 MUST quarantine `duplicate_conflict`，并且不得让任一冲突版本推进 accepted frontier，除非本地已经有一个 accepted 版本；此时新冲突版本仍保持 quarantined/rejected diagnostic。

## 12. Space Upgrade and Lifecycle

### 12.1 Profile Upgrade

Contrix v1 通过 `cx.space.upgrade` 在同一 `space_id` 上切换 reducer / schema profile。Profile id 本身就是版本（v1 不使用顶层 `space_version` wire 字段）。只增加 optional 字段、且不改变 auth / reducer 语义的升级 MAY 直接发布 enforcement 事件；引入新 critical feature、auth 规则、reducer 规则或加密语义的升级 MUST 使用多阶段流程：

```json
{
  "kind": "cx.space.upgrade",
  "payload": {
    "phase": "announcement",
    "target_schema_profile": "cx.schema.v1",
    "target_reducer_profile": "cx.reducer.v1_1",
    "migration_policy": "copy_state_and_continue",
    "transition_mode": "ignore_unknown_fields",
    "replacement_ref": "cx:event:01js0sp0000000000000000000",
    "earliest_enforcement_hlc": "01970e589d21-0000-a13f9c2e",
    "readiness_deadline": "2026-05-16T00:00:00Z",
    "min_readiness": {
      "mode": "service_receipts",
      "required_services": [
        "principal_server",
        "sync_service"
      ]
    }
  }
}
```

升级规则：

- `cx.space.upgrade` MUST 由拥有 `cx.space.upgrade`、`cx.space.admin` 或 Space policy 明确声明的等价 admin capability 的 actor 发起。
- `phase`、`target_schema_profile`、`target_reducer_profile`、`migration_policy`、`transition_mode`、`replacement_ref`、activation frontier / HLC 和 readiness 条件必须被事件签名覆盖。
- `replacement_ref` MAY 指向迁移计划、snapshot manifest 或新 profile 描述，但不能指向未签名的外部说明。
- `phase=announcement` 只发布目标 profile、transition 模式、最早 enforcement 时间 / frontier 和迁移说明；它不得让节点开始接受依赖新语义的写入。
- `phase=readiness_check` MAY 汇总 service / bridge / client family 的 signed readiness receipts 或缺席清单；receipt 只能说明能力，不替代本地 schema、auth 和 reducer 校验。
- `phase=enforcement` 才切换 accepted target profile。它 MUST 引用 announcement，满足 readiness 条件或明确记录 admin override，并绑定 activation causal frontier；未到达该 frontier 的普通历史仍按先前 profile 解释。
- `readiness_deadline` 到达且 `min_readiness` 未满足时，升级不得自动进入 enforcement。管理员必须发布新的 `cx.space.upgrade` 事件，选择 extend deadline、cancel/rollback announcement，或带 explicit admin override 的 enforcement；这些选择都必须被签名并进入 state resolution。
- 未支持目标 profile 的节点在 enforcement 生效后 MUST 停止接受依赖新语义的写入；MAY 继续只读展示升级前的 accepted history，并可通过只读 projection 或代理提供降级视图。
- 降级代理不得把新 auth / reducer 语义翻译成先前语义后重新签发为普通写入；只能提供只读 projection、迁移提示或明确标记的 transition write path。
- 升级不得重写历史 event hash；任何 state 迁移都必须表现为新的 signed event、snapshot 或 reducer profile 输出。

### 12.2 Tombstone / Replacement

当一个 Space 被关闭、替换或迁移到新 Space 时，必须使用显式 tombstone：

```json
{
  "kind": "cx.space.tombstone",
  "payload": {
    "reason": "migrated",
    "replacement_space": "cx:space:01NEW...",
    "replacement_event": "cx:event:...",
    "effective_at": "2026-04-26T00:00:00Z"
  }
}
```

规则：

- Tombstone 只改变后续写入和默认展示，不删除历史。
- Tombstoned Space MUST reject 新普通写入，只允许 redaction、export、legal hold、account lifecycle、migration proof 等维护类事件。
- `replacement_space` 若存在，客户端 MUST 独立验证其 create event、owner / organization endorsement、Space policy 和历史导入证明。
- Tombstone 不自动授予新 Space 读取原 Space 历史的权限；历史访问仍受原 Space 的 history visibility、capability、E2EE epoch 和 retention policy 约束。

### 12.3 Space Lifecycle State Machine

Space lifecycle 是 reducer state，不是本地服务开关。每个 transition 是独立 kind：

| 当前状态 | Event | 下一状态 | 是否可恢复 | 主要效果 |
| --- | --- | --- | --- | --- |
| `active` | `cx.space.archive` (payload `archived=true`) | `archived` | yes | 从默认 active 列表和普通 discovery 中隐藏；普通业务写入默认 SHOULD reject，除非 policy 允许 archive maintenance。 |
| `archived` | `cx.space.archive` (payload `archived=false`) | `active` | yes | 恢复普通展示和写入。 |
| `active` / `archived` | `cx.space.freeze` (payload `frozen=true`) | `frozen` | yes | 临时写入冻结；只允许 redaction、export、legal hold、policy/account lifecycle、unfreeze 和管理员维护事件。 |
| `frozen` | `cx.space.freeze` (payload `frozen=false`) | `active` 或 `archived` | yes | 解除冻结，回到冻结前基础状态。 |
| `active` / `archived` / `frozen` | `cx.space.tombstone` | `tombstoned` | no | 关闭或迁移 Space；拒绝新普通写入，只保留维护、审计和迁移证明。 |
| `active` / `archived` / `frozen` | `cx.space.destroy` | `destroyed` | no | 不可恢复的 decommission marker；服务可按 retention / erasure policy 释放本地 payload，但仍不得伪造历史缺失。 |
| `tombstoned` | `cx.space.destroy` | `destroyed` | no | tombstone 后的最终销毁或资源回收声明。 |

规则：

- `cx.space.archive` / `cx.space.freeze` 是可逆 singleton state event；各自最新 accepted event 决定对应布尔状态。v1 不新增 `restore` / `unfreeze` kind。
- `frozen` 可以叠加在 `archived` 上；解除冻结后 MUST 回到冻结前的 archived/active 基础状态。
- `tombstoned` 和 `destroyed` 是 terminal state。后续普通业务 Event MUST reject；只允许 redaction、export、legal hold、account lifecycle、migration proof、snapshot/witness proof 和 policy 明确列出的维护类 Event。
- `destroy` 不等于全网物理删除。它只声明该 Space 已不可恢复地 decommission；已签名 Event、verification stub、legal hold 和外部副本仍按各自 policy 处理。
- 这些转换均需要 Space admin / owner / governance root 或 policy 声明的 lifecycle capability；policy hard deny 优先于其它授权来源。
