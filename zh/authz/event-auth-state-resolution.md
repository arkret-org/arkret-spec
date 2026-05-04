# Event Authorization and State Resolution

## 1. 目标

本文件定义 Contrix Space 内事件是否有效、状态如何收敛、冲突如何确定性解决、redaction 如何保留最小字段，以及 Space 版本如何升级。

任何支持联邦写入、多设备写入或离线写入的实现，MUST 实现本文件的 `space_version=1` 规则。

## 2. Space Version

每个 Space 的 create event MUST 包含：

```json
{
  "kind": "cx.space.create",
  "state_key": "",
  "space_version": "1",
  "payload": {
    "object": {
      "id": "cx:space:01js0sp0000000000000000000",
      "kind": "collaboration",
      "space_version": "1",
      "title": "Launch Plan",
      "initial_creators": [
        "did:plc:..."
      ],
      "created_by_principal": "did:plc:...",
      "owning_organizations": [],
      "schema_refs": [
        "cx.schema.space.v1"
      ],
      "default_discoverability": "invite_only",
      "default_join_rule": "invite",
      "history_visibility": "joined",
      "encryption_profile": "none",
      "created_at": "2026-04-26T00:00:00Z"
    }
  }
}
```

`space_version` 决定：

- event envelope schema
- canonical JSON profile
- event id / hash input
- auth event selection
- authorization algorithm
- reducer conflict ordering
- redaction preserved fields
- membership transition rules
- profile transition rules

实现 MUST reject 未知 `space_version` 的写事件。实现 MAY 以只读方式展示未知版本事件，但 MUST NOT 将其作为本地 accepted state。

## 3. Event Validation Pipeline

收到事件后，节点 MUST 按以下顺序验证：

1. Parse canonical JSON，不接受重复 key、非规范 number、无效 UTF-8 或超过 profile 限制的对象。
2. 验证 `event_id` 是合法 `cx:event:*` typed ID，并验证事件 redaction 前、去除 `proofs` 与 `unsigned` 后 canonical bytes 的 digest 与 proof `payload_hash` / event digest 一致。
3. 验证 `proofs` 中 actor/device/service 签名。
4. 验证 `space_id`、`space_version`、`kind`、`created_at`、`hlc` 与 schema。
5. 拉取并验证 `prev_refs` 和 `auth_refs` 指向事件的 hash。
6. 对 `auth_refs` 运行授权算法。
7. 对 `payload` 运行类型级 schema validation。
8. 对策略服务、capability constraint、rate limit 和 abuse policy 运行本地检查。
9. 输出 `accepted`、`soft_failed`、`rejected` 或 `quarantined`。

节点 MUST NOT 因为事件来自可信 Sync Service 就跳过任何步骤。

接收方在进入授权和 state resolution 前 MUST 验证 HLC 格式和时钟窗口。Contrix v1 的 `5 分钟` 是默认 hard future-skew 上限，用于识别明显错误或伪造的未来时间；它不是高风险 state event 的默认排序信任窗口。HLC 物理时间超过 hard future-skew 的事件 MUST reject 或 quarantine；被 quarantine 的事件不得参与 winner 选择。

实现和 Space / reducer profile SHOULD 声明更小的 `expected_future_skew_ms`。未声明时，普通服务端写入 SHOULD 以 30 秒作为 expected drift，高风险 state event（`cx.capability.*`、membership、policy、MLS epoch、service binding、Space upgrade）SHOULD 以 10 秒或本地运维可证明的更小窗口作为 expected drift。移动端、离线端或弱同步环境 MAY 使用更宽 expected drift，但必须在 profile / policy 中声明，并且不得让 HLC 单独覆盖缺失的 causal dependency、`actor_seq` 回退或 revoke freshness。

若候选事件的 HLC 未超过 hard future-skew 但明显超出该 actor / service 最近观测 drift 或 profile expected drift，节点 SHOULD soft-fail 或 quarantine 并请求 backfill / policy check。对于高风险 state event，节点不得仅因更大的 HLC 让其胜出；必须先满足签名、授权、`prev_refs`、`auth_refs`、`actor_seq` 和 revoke freshness 检查。

## 4. Auth Refs

每个写事件 MUST 包含 `auth_refs`。`auth_refs` 是授权当前事件所需的最小状态事件集合，不是完整状态快照。

`space_version=1` 的 auth refs 选择规则：

| 当前事件类型 | 必需 auth refs |
| --- | --- |
| `cx.space.create` | 无 |
| `cx.member.state` | `cx.space.create`、目标 actor 当前 membership、发送者 membership、相关 join rule、相关 capability grant |
| `cx.capability.grant` | `cx.space.create`、grantor membership、grantor 当前 grant/role/admin capability |
| `cx.capability.revoke` | 被撤销 grant、revoker membership、revoker revoke/admin capability |
| `cx.policy.*` | `cx.space.create`、actor membership、policy/admin capability、上一版同 key policy |
| `cx.space.policy.set` | `cx.space.create`、actor membership、按 `state_key` 选择对应 capability tier（见下方 state_key 表）、上一版同 `state_key` 的 state 事件，及该 `state_key` 声明的额外依赖 |
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
| `cx.space.lifecycle.set` | `cx.space.create`、当前 lifecycle state、按 `state_key` 选择对应 lifecycle/admin capability tier，及该 transition 声明的额外 guard（见下方 lifecycle 矩阵） |
| `cx.device.authorized` / `cx.device.revoked` / `cx.device.list_update` | principal control Space 的 `cx.space.create`、目标 principal 当前 DID/key-log state、授权设备或 recovery policy、上一版 device state |
| `cx.session.grant` | principal control Space 的 `cx.space.create`、目标 principal 当前 DID/device state、issuer service binding 或组织 policy、上一版同 session / subject grant state |
| `cx.account.status` | principal control Space 的 `cx.space.create`、actor lifecycle / admin / governance capability、上一版 `cx.account.status` state、retention / legal-hold / erasure policy（如适用） |
| `cx.moderation.report` | actor membership、reporter capability（基础举报 capability 默认对成员开放）、被举报对象的可见性证明、上一版同 `(reporter, target)` report state（用于去重）|
| `cx.moderation.frank` | actor membership、E2EE Space 的 encryption / audit policy、对应 `cx.moderation.report` 引用、moderation server / audit agent service binding |
| `cx.moderation.policy_action` | actor membership、moderation / policy / admin capability、`cx.space.policy.set` (state_key=`moderation`) 当前状态、政策列表 hash |

### 4.0.1 `cx.space.policy.set` state_key 矩阵

`cx.space.policy.set` 把所有 Space 级策略 / 配置赋值合并为一个 event kind，按 `state_key` 派发不同 capability tier 与额外 auth ref。State resolution key 形如 `cx:space:<id>|<state_key>`。

| `state_key` | capability tier | 额外 auth refs | 说明 |
| --- | --- | --- | --- |
| `access` | policy/admin | 上一版 `access` state | Space 通用 access policy（替代旧 `cx.space.policy`）。 |
| `join_rule` | join_policy/admin | 上一版 `join_rule` state | Space `join_rule`。 |
| `history_visibility` | history/policy/admin | 上一版 `history_visibility` state、当前 encryption / `history_sharing` policy | Space history visibility。 |
| `discovery` | discovery/policy/admin | 上一版 `discovery` state | Space discoverability；MUST NOT 授予读取/加入/解密权限。 |
| `policy_server` | policy/admin | service DID delegation、上一版 `policy_server` state | 绑定 Policy Server。 |
| `policy_components` | policy/admin | 上一版 `policy_components` state | 启用的 policy component 集合。 |
| `history_sharing` | policy/admin | 上一版 `history_sharing` state、当前 encryption policy | E2EE 历史共享策略。 |
| `asset_privacy` | asset_privacy/policy/admin | 上一版 `asset_privacy` state | 资产隐私策略。 |
| `moderation` | moderation/policy/admin | 上一版 `moderation` state | Space 审核策略。 |
| `plaintext_visible_services` | privacy/policy/admin | service DID delegation、上一版 `plaintext_visible_services` state | E2EE 边界外可见服务白名单。 |
| `media_service` | media_service/policy/admin | service DID delegation、上一版 `media_service` state | 媒体服务绑定。 |
| `schema_refs` | schema/policy/admin | 上一版 `schema_refs` state、upgrade policy（如适用） | Space `schema_refs`。 |
| `inheritance:<parent_space_id>` | child policy/admin | child Space 的 `cx.space.create`、confirmed parent edge | 父子 Space 继承策略；`state_key` 必须是 `inheritance:` 前缀加目标 parent space id；每个 parent 一份；只在 child Space 写入。 |

未识别的 `state_key` MUST fail closed（`unsupported_state_key`），不得静默 accepted。每个 `state_key` 的 payload schema 通过 `event-payload.schema.json` 中的 `cx.space.policy.set` allOf 分支按 `state_key` 选择。

### 4.0.2 `cx.space.lifecycle.set` state_key 矩阵

`cx.space.lifecycle.set` 把 Space 生命周期 FSM 的全部 transition 收敛到一个 event kind，按 `state_key` 选择 facet。`archive` 与 `freeze` 是可逆布尔状态，`tombstone` 与 `destroy` 是终态。

| `state_key` | capability tier | 额外 auth refs / guard | 说明 |
| --- | --- | --- | --- |
| `archive` | lifecycle/admin | 当前 lifecycle state、archive policy、未完成 child security-boundary Space / legal-hold / export gate | payload `archived: bool`，可逆。 |
| `freeze` | lifecycle/admin | 当前 lifecycle state、freeze policy、maintenance / incident response constraint | payload `frozen: bool`，可逆。 |
| `tombstone` | owner/governance/admin lifecycle | 当前 lifecycle state、replacement / migration / retention policy | 终态；payload 携带 `replacement_space` / `replacement_event`。 |
| `destroy` | owner/governance/admin lifecycle | 当前 lifecycle state、tombstone / export / retention / legal-hold constraint、无活跃 child Space 和无未决 grant | 终态；不可恢复的 decommission marker。 |

未识别的 lifecycle `state_key` MUST fail closed。同一 facet 的最新 accepted event 决定该 facet 当前状态；终态 facet（`tombstone` / `destroy`）一旦写入即拒绝后续普通业务写入。

如果事件缺少必需 auth ref，节点 MUST soft fail 并尝试 backfill。Backfill MUST 受 `../conformance/scalability-constraints.md` 的 `auth_chain` 深度、`auth_refs` 数量、page size、retry 和本地资源上限约束；实现不得为了验证单个事件无限递归拉取历史。若在上限内仍缺失，或只能通过未验证 snapshot / 未授权服务获得依赖，节点 MUST reject、保持 soft-failed 或 quarantine，具体取决于错误是否可恢复。

长期 Space 中的 `cx.space.create` MAY 通过已验证 snapshot manifest、checkpoint、witness receipt 或 stripped create event 满足 bootstrap 依赖，但接收方仍必须能验证 create event digest、space id、space_version、creator authority 和 snapshot signer authority。任何 snapshot-assisted auth ref 都不得替代事件本身的签名责任，也不得允许服务端伪造 Space 起源。

### 4.1 Partial Auth State 与渐进恢复

当缺失 auth chain、Principal Control Event Stream 或远端 snapshot 时，节点 MAY 构造 `partial_auth_state`，但它只是本地只读恢复视图，不是 accepted state：

- `partial_auth_state` MUST 只由本地已 accepted Event、已验证 snapshot / checkpoint、以及明确标记为缺口的 dependency record 组成。
- 任何仍处于 `soft_failed` 的 Event MUST NOT 推进 accepted frontier、state hash、capability cache、membership state、MLS epoch 或普通可写 projection。
- 客户端 MAY 在 `partial_auth_state` 下展示已经 accepted 且当前可见性已验证的历史内容，并 MUST 标记 `auth_incomplete` / `read_only` 或等价状态。
- 客户端 MUST NOT 在 `partial_auth_state` 下提交依赖缺失 auth state 的新写入；需要写入时必须先 backfill 到可验证 frontier，或让服务端返回 `dependency_missing` / `temporarily_unavailable`。
- 对高风险 state event（membership、capability grant/revoke、policy、MLS epoch、Space lifecycle、device/session control），缺少 auth chain 时 MUST fail closed 或保持 pending；不得用 partial view 推断允许。
- `partial_auth_state` 的诊断输出 SHOULD 暴露缺失 event id、缺失 state key、已尝试 source、retry cursor、snapshot candidate 和本地预算耗尽原因，便于渐进 backfill。

该机制的目标是让长期离线设备能够先只读打开已验证历史，再后台补齐数千个 auth events；它不得降低任何写入、授权或 state resolution 的验证要求。

## 5. Membership

Contrix 使用 `cx.member.state` 表达 actor 在 Space 中的成员状态：

```json
{
  "kind": "cx.member.state",
  "state_key": "did:web:actor.example.com",
  "payload": {
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

Contrix 使用 `cx.flow.branch.member` 表达 actor 在 Flow discussion branch 中的成员状态：

```json
{
  "kind": "cx.flow.branch.member",
  "state_key": "<base64url_nopad(sha256(canonical_json([\"cx.flow.branch.member\",\"cx:flow:01js0r00m00000000000000000\",\"discussion\",\"did:web:actor.example.com\"])))>",
  "payload": {
    "flow_id": "cx:flow:01js0r00m00000000000000000",
    "branch": "discussion",
    "actor_id": "did:web:actor.example.com",
    "state_key_components": [
      "cx.flow.branch.member",
      "cx:flow:01js0r00m00000000000000000",
      "discussion",
      "did:web:actor.example.com"
    ],
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

`cx.space.policy.set` (state_key=`discovery`) 控制 Space 是否能被目录、搜索、父 Space 或组织页发现。完整规则见 `discovery-directory.md`。

`discoverability` 取值：

- `public`：可被公共目录索引和搜索。
- `listed`：可在指定目录、组织页或父 Space 中列出。
- `restricted`：只有满足可验证条件的请求方可发现。
- `unlisted`：不进入搜索，但可凭精确 id、alias、邀请或允许的 parent edge 解析。
- `invite_only`：未被邀请或未持有 invite proof 的主体不得得知其存在。
- `secret`：仅本地或端到端加密上下文中可见。

`cx.space.policy.set` (state_key=`discovery`) 不授予读取、加入、写入或解密权限。节点和目录服务 MUST NOT 用 `join_rule` 或 `history_visibility` 推断 discoverability。

`cx.space.policy.set` (state_key=`join_rule`):

- `invite`：只允许 invite。
- `public`：任何 actor 可 join，但仍需通过 policy server 和 rate limit。
- `knock`：外部 actor 可 knock，不可直接 join。
- `restricted`：actor 必须满足 `allowed_selectors` 中至少一个可验证条件。
- `knock_restricted`：不满足 restricted 条件者可 knock。
- `closed`：不接受普通加入、knock 或 invite accept；只允许迁移、维护或管理员明确声明的例外流程。

Canonical event、Space object 和 JSON Schema MUST 使用 `invite` 表示邀请加入。任何不在该 enum 内的取值都是无效输入，接收方 MUST 按 `schema_violation` reject，不得静默映射为合法 enum 值，否则会掩盖签名 payload 与 policy intent 的差异。Matrix-style import 或 bridge 必须在写入前显式映射到本枚举值，并以新签名事件提交。

`cx.space.policy.set` (state_key=`history_visibility`):

- `world_readable`：任何 actor 可读取明文或已授权公开内容。
- `shared`：当前和历史成员可读取加入前历史。
- `invited`：被邀请 actor 可读取 stripped preview state。
- `restricted`：只有满足 Space policy 中 `allowed_selectors`、claim、capability 或等价 history access proof 的 actor 可读取加入前历史或 stripped state；无法验证时 MUST 按 `joined` 或更严格规则 fail closed。
- `joined`：仅加入后历史默认可见。

E2EE Space 或通过 branch-scoped access override 启用 E2EE 的 Flow discussion branch 中，history visibility 只授权索引和密钥共享资格，不保证服务端能解密历史。`restricted` 不授予 discoverability、join 权限或自动密钥下发；它只让满足证明的 actor 进入 pre-join history 和 E2EE key share eligibility 的候选集合。

`cx.space.policy.set` (state_key=`history_sharing`):

`history_visibility` 只描述默认读取边界。E2EE Space 或通过 branch-scoped access override 启用 E2EE 的 discussion branch 若允许新成员获取加入前的解密材料，MUST 额外声明 history sharing policy：

```json
{
  "kind": "cx.space.policy.set",
  "state_key": "history_sharing",
  "payload": {
    "enabled": true,
    "roles_that_can_share": [
      "admin",
      "history_curator"
    ],
    "shareable_range": {
      "mode": "duration",
      "max_before_join_ms": 2592000000
    },
    "automatic_share": false,
    "requires_audit_event": true,
    "withholding_allowed_reasons": [
      "unverified_device",
      "history_not_visible",
      "policy_denied"
    ]
  }
}
```

规则：

- E2EE 历史共享会削弱 forward secrecy；客户端在加入前 MUST 向用户或管理员可见地展示该 policy。
- `automatic_share=true` 只可用于 Space policy 明确允许、且接收设备已通过 device trust chain 验证的场景。
- 共享历史密钥材料前，发送设备 MUST 检查接收 principal 的 membership、device trust、history visibility、capability 和本 state event。
- `requires_audit_event=true` 时，发送设备必须先写入 `cx.space_key.share_audit` 或等价审计事件，并等待因果确认后再发送历史 key material。
- 历史 key share MUST 绑定接收 principal、接收 device、epoch / range、policy hash、审计事件和发送设备签名；不得作为未限定范围的“给新成员全部先前密钥”隐式流程。
- 普通客户端 MUST NOT 为未来可能的历史共享而无限期保留先前 epoch 明文 secret。需要本地恢复或合规保留时，先前 key material MUST 以设备受保护密钥或明确授权的 key backup 加密保存，受 retention / legal hold / erasure policy 约束，并在不再需要时销毁。
- 若 Space 使用 Archive Node / Audit Node 保存历史解密能力，该节点 MUST 是显式成员、受托 service 或 capability subject，且其保留范围、访问目的、审计义务和撤销流程必须写入 Space policy；不得把普通成员客户端伪装成隐式长期密钥仓库。
- policy 变更只影响变更后发起的共享动作，不追溯授权已经发送给既有成员的历史解密材料。

`cx.space.policy.set` (state_key=`policy_components`):

复杂 Space SHOULD 将策略拆成可独立演进的组件，而不是把所有布尔开关塞进单个 policy 对象：

```json
{
  "kind": "cx.space.policy.set",
  "state_key": "policy_components",
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

> 注：`components` 中的值为占位 event_id，实际部署 MUST 替换为真实 event_id。

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

`cx.space.policy.set` (state_key=`plaintext_visible_services`):

非 E2EE / 非内容加密的私有 Space 若允许服务端处理正文或可逆派生内容，必须显式声明可见服务：

```json
{
  "kind": "cx.space.policy.set",
  "state_key": "plaintext_visible_services",
  "payload": {
    "services": [
      {
        "service_did": "did:web:server.acme.example",
        "service_type": "principal_server",
        "purposes": [
          "events",
          "sync",
          "backfill"
        ],
        "visibility": "private_plaintext"
      },
      {
        "service_did": "did:web:search.acme.example",
        "service_type": "delegated_search",
        "purposes": [
          "search",
          "notification",
          "preview"
        ],
        "visibility": "derived_plaintext"
      }
    ]
  }
}
```

规则：

- `service_did` 必须可解析，并通过 DID service、组织背书或 Space policy 委托绑定到对应 `service_type`。
- `visibility=private_plaintext` 表示可接收正文或附件预览；`visibility=derived_plaintext` 表示只可接收通知摘要、全文索引、embedding、报表等派生内容。
- 未列入该 state event 的服务只能接收公开内容、密文 envelope、不可逆 hash、最小 routing metadata 或 policy 明确允许的 stripped preview。
- 该 state event 的撤销或覆盖按普通 state resolution 生效；生效点之后不得继续向已撤销服务发送非加密私有内容。
- 该 state event 是成员可验证的透明度机制。允许某服务看见明文但对受影响成员隐藏该事实是不合规的；高安全 Space SHOULD 使用 E2EE、minimal-metadata profile 或本地客户端索引，而不是 admin-only 隐藏明文服务清单。

### 6.1 Organization Ownership and Endorsement

组织所有权不是服务器本地配置，也不是 Space 名称、域名、图标或 UI 文案。组织所有权 MUST 由组织 principal 的可验证声明表达。

`cx.space.create.payload.object` MAY 包含：

- `created_by_principal`：实际创建 Space 的 principal DID，可能是组织 DID、员工 DID、agent DID 或托管服务 DID。
- `owning_organizations`：创建时已由组织 DID 背书的 organization DID 列表。该字段为空时，Space 不得被展示为任何组织的 official Space。

若 Space 创建后才获得组织认可，组织 MUST 发布或共同签名 `cx.space.organization` state event：

```json
{
  "kind": "cx.space.organization",
  "state_key": "did:web:acme.example",
  "payload": {
    "organization_did": "did:web:acme.example",
    "relationship": "owner",
    "status": "active",
    "endorsed_by": "did:web:acme.example#governance-key-1",
    "scope": {
      "official": true,
      "allowed_labels": [
        "official",
        "support"
      ],
      "service_dids": [
        "did:web:server.acme.example",
        "did:web:search.acme.example"
      ]
    },
    "valid_from": "2026-04-26T00:00:00Z",
    "valid_until": null,
    "revocation_ref": null
  }
}
```

`relationship` 取值：

- `owner`：组织是 Space 的所有者或共同所有者。
- `sponsor`：组织认可该 Space，但不单独拥有全部治理权。
- `host`：组织托管 Sync Service / Blob / Media / delegated search 等服务，但不声明内容所有权。
- `issuer`：组织只作为 trusted issuer / policy issuer。

客户端判断一个 Space 是否为某 Organization 官方创建或官方认可时，MUST 同时验证：

1. Organization DID 可解析，且 DID Document / key log 在事件时间有效。
2. `cx.space.create.payload.object.created_by_principal` 是该 organization DID，或存在 active 的 `cx.space.organization` event。
3. `cx.space.organization` 的签名 key 属于 organization DID 的当前或事件时点有效控制链，或属于 organization DID 明确绑定的 governance service DID。
4. `relationship` 为 `owner` 或 `sponsor`，且 `scope.official=true`。
5. 该声明未过期、未被 `status=revoked` 或后续同 `state_key` state event 覆盖。
6. Space id、Space create event hash 和 organization DID 都被签名覆盖，防止把同一声明移植到另一个 Space。

客户端 MUST NOT 因以下信号把 Space 展示为 official：

- Space 名称、头像、主题或简介包含组织名。
- `space_id`、alias、handle、域名或邮箱后缀看起来属于组织。
- Sync Service 或受托 search / projection 服务由组织托管。
- Space 中有组织成员加入。

组织可通过后续 `cx.space.organization` 将 `status` 改为 `revoked`、`suspended` 或 `transferred`。撤销只影响官方背书和后续治理判断，不应自动删除历史数据；历史展示 SHOULD 保留“曾经由该组织背书，已于某时间撤销”的审计状态。

## 7. Authorization Algorithm

对事件 `E`，节点 MUST：

1. 构造 auth state map：以 `(kind, state_key)` 为 key，从 `auth_refs` 解析授权状态。
2. 验证所有 auth event 本身为 accepted，或在当前 state resolution 中被接受。
3. 验证 sender 的当前 membership。
4. 验证 sender 的 device 是否在事件时间有效，且未在 `created_at` 前撤销。
5. 验证 sender 持有 action 对应 capability；capability subject MUST 匹配 DID 或满足 selector。
6. 验证 capability constraint：时间、空间、对象、字段、速率、审批、设备、Applet 范围。
7. 验证 event kind 的专用规则。
8. 验证 policy server hard deny、server ACL、ban list 与本地 quarantine list。

授权计算 MUST 使用事件被接受时的因果 auth state，而不是接收时间的最新状态。`created_at` 只用于校验签名 key、claim、grant 有效期和时钟窗口，不得让缺少因果前序或 actor_seq 回退的事件绕过 revoke。撤销事件只影响其 causal frontier 之后的事件；若业务事件与相关 revoke 的顺序无法通过 `prev_refs`、`actor_seq` 和 HLC 确定，节点 MUST fail closed、soft fail 或进入 review。

离线写入重新上线时，节点必须同时验证事件自身 `created_at` 位于 grant / session / device 的有效窗口内，以及 `auth_refs` 所声明的 grant frontier 未被该事件因果已知的 revoke 覆盖。若设备离线期间 grant 已过期，但事件 `created_at` 早于 `expires_at` 且 actor chain、HLC drift、device validity 和 revoke freshness 都可验证，事件 MAY 被接受；若无法证明该事件早于 revoke / expiry 的有效 frontier，MUST soft-fail、quarantine 或要求用户基于最新状态重新提交。实现 SHOULD 对离线队列声明最大积压窗口；public profile 默认不得超过 30 天，超过后新写入必须重新签名并重新授权。

## 8. State Events

State event 是具有 `state_key` 的事件。其当前状态由 `(kind, state_key)` 最新 accepted 事件决定。

以下事件类型是 `space_version=1` 标准 state event：

- `cx.space.create`
- `cx.space.policy.set`（按 `state_key` 区分：`access` / `join_rule` / `history_visibility` / `discovery` / `policy_server` / `policy_components` / `history_sharing` / `asset_privacy` / `moderation` / `plaintext_visible_services` / `media_service` / `schema_refs` / `inheritance`）
- `cx.space.child`
- `cx.space.parent`
- `cx.space.organization`
- `cx.space.upgrade`
- `cx.space.lifecycle.set`（按 `state_key` 区分：`archive` / `freeze` / `tombstone` / `destroy`）
- `cx.member.state`
- `cx.flow.branch.member`
- `cx.flow.branch.history_visibility`
- `cx.flow.branch.policy_components`
- `cx.capability.grant`
- `cx.capability.derived`
- `cx.capability.revoke`
- `cx.policy.rule`
- `cx.mls.epoch`
- `cx.device.authorized`
- `cx.device.revoked`
- `cx.device.list_update`
- `cx.session.grant`
- `cx.account.status`
- `cx.moderation.policy_action`
- `cx.view.create`
- `cx.view.update`
- `cx.view.reconcile`

非 state 但参与 reducer / 审计的 moderation event 列表（state_key 缺省，按事件 id 收敛）：

- `cx.moderation.report`：举报事件，参与 moderation 队列与 quarantine projection。
- `cx.moderation.frank`：franking proof，参与 E2EE 滥用举报审计；不进入 capability state map。
- `cx.audit.accessed`：auditable E2EE 解密承诺事件；详见 `crypto-media/encryption-and-audit.md` §3。
- `cx.audit.ryw_receipt`：Read-Your-Writes receipt（可选 ephemeral 或 durable，见 §6.3 受控 deployment）。

`cx.device.*` 和 `cx.session.grant` 是 principal-scoped state event。它们只在 principal control Space 的 state map 中解析；普通协作 Space MAY 通过 `auth_refs`、snapshot reference 或 policy server proof 引用该 state，但不得把另一个 principal 的设备/会话事件写入任意协作 Space history 来改变其身份状态。

principal control state 的 `state_key` MUST 可从事件内容确定性导出。实际 wire 形态使用 `../conformance/encoding.md` §9.5 定义的 canonical hash 编码，`payload.state_key_components` 提供反向可解释信息：

- `cx.device.authorized` / `cx.device.revoked`：`["cx.device.authorized" 或 "cx.device.revoked", principal_id, device_id]`
- `cx.device.list_update`：`["cx.device.list_update", principal_id]`
- `cx.session.grant`：`["cx.session.grant", grant_id]`

实现不得使用 pipe 字符串、数据库自增 ID、HTTP receive order 或其它非确定性来源参与 state resolution。

State event 不等于 auth state dependency。`cx.view.*` 等投影定义事件可以使用 state resolution 形成当前 View 定义，但默认不进入 capability / membership / policy / MLS 的 auth state map；只有当某个 View 被 policy 明确声明为授权依赖、审计依赖或 materialized query contract 时，相关 View state event 才能作为对应业务事件的 `auth_refs`。非 state event 仍可影响物化 projection，但不进入 auth state map，除非具体类型声明其为 auth dependency。

`cx.mls.epoch` 在 state map 中表示当前 MLS epoch checkpoint，但它不得作为独立授权事实推进 epoch。验证规则见 `../crypto-media/encryption-and-audit.md` 第 5.3 节：checkpoint 必须能从同一 conflict set 的 winning `cx.mls.commit` 机械验证，无法验证时 MUST reject 或 soft-fail。

## 9. State Resolution

当多个分支对同一 `(kind, state_key)` 给出不同 accepted state event 时，节点 MUST 运行 deterministic state resolution。

### 9.1 输入

- `base_state`: 最近共同祖先 state map。
- `state_sets`: 各分支 state map。
- `auth_chain`: 所有候选 state event 的 auth dependency 闭包。

### 9.2 输出

- `resolved_state`: 单一 state map。
- `conflict_records`: 被压制候选及原因。

### 9.2.1 规模上限与 Snapshot Fallback

State resolution MUST 受 `../conformance/scalability-constraints.md` 的上限约束。默认 v1 限制包括：

- 单个 state key 的 conflict candidate 数最多 256。
- `auth_chain` 闭包深度最多 64。
- `auth_difference` 事件数最多 4,096。
- 单个事件 `auth_refs` 数最多 64。

超过上述限制时，节点 MUST 使用最近可验证 snapshot 作为 `base_state` 执行 snapshot-assisted resolution，或将依赖事件保持 `soft_failed` / `quarantined`，不得继续无界展开 auth chain。fallback snapshot 必须验证 signer authority、frontier、state hash 和 chunk digest。没有可验证 snapshot 时，节点 MUST fail closed；不得使用本地接收顺序、数据库自增 ID 或 Sync Service 到达顺序裁决 winner。

### 9.3 算法

1. 将所有 state set 中相同 `(kind, state_key)` 且 event id 相同的项放入 unconflicted state。
2. 将不同 event id 的项放入 conflicted set。
3. 计算 auth difference：见 9.3.1。
4. 对 auth difference 先排序并授权，得到 provisional auth state。
5. 对 conflicted set 按 priority class 分组：
   - `space.create`
   - membership ban/leave/join/invite/knock
   - capability revoke
   - capability grant
   - policy / schema / join_rule / history_visibility
   - encryption epoch
   - view definition
   - other state
6. 组内排序键：
   - `authority_class`：按 9.3.2 的 lattice 偏序计算（高者优先）。
   - `causal_depth`：因果上更新者优先。
   - `hlc`：更大 HLC 优先。
   - `event_id`：字节序更小者作为最终 tie-breaker。
7. 依次尝试候选事件；能在 provisional auth state 下通过授权者进入 resolved state。
8. 如果同 key 所有候选均不通过授权，回退到 base_state；若无 base，则该 key unset。
9. 输出 conflict record，索引器 SHOULD 暴露给审计视图。

该算法 MUST deterministic。任何实现不得使用本地接收顺序、数据库自增 ID 或 Sync Service 顺序作为 tie-breaker。

HLC 只能在候选事件已通过格式、签名、授权、时钟窗口和 causal dependency 检查后参与排序。`created_at`、HTTP receive time、provider timestamp 或外部桥接时间戳不得替代 HLC，也不得单独作为授权或 winner 依据。

### 9.3.1 Auth Difference

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

### 9.3.2 Authority Class

候选事件的授权来源在 state resolution 中表达为一个 **authority class**——两维 lattice 的一个点：

```
authority_class = (governance_layer, authority_kind)
```

- `governance_layer` ∈ `{ root, organization, space_admin, policy_membership, object, none }`
  - `root`：Space create / recovery root（`cx.space.create.payload.object.initial_creators`、Space root recovery key 或治理根明确授权）
  - `organization`：active `cx.space.organization{relationship=owner|sponsor, scope.official=true}` 绑定的 governance DID / service DID 直接签发，且 action 在声明 scope 内
  - `space_admin`：active Space admin / creator capability，resource 精确覆盖目标 Space
  - `policy_membership`：policy / membership / capability 管理 grant，resource 精确覆盖目标 state key
  - `object`：Flow / Space / Morph / Relation 管理或操作 grant，resource 精确覆盖目标对象
  - `none`：无具名治理来源；仅由基础 membership / 入场规则允许
- `authority_kind` ∈ `{ direct, delegated, self }`
  - `direct`：grant subject 是 actor 本人，未经过委派
  - `delegated`：通过有效 delegation chain（未过期、未被 revoke、depth 在 profile 限制内）
  - `self`：actor 对自身 state 的动作（leave、knock、invite accept、read marker），由 join rule / invite / history policy 允许

`authority_class` 是 state resolution 的排序键，不是额外授权来源。候选事件必须先通过签名、schema、causal dependency、`auth_refs` 和 policy hard deny 检查；未通过者没有 `authority_class`，不得进入 winner 选择。

实现 MUST 在候选事件自己的 causal auth state 上计算 `authority_class`，不得使用接收节点的当前最新状态、HTTP 到达顺序、数据库行号或尚未通过授权的竞争候选。若同一候选事件可由多个 grant / role / issuer 授权，取 lattice 上最高的一个；同 class 时按 `delegation_depth` 较小、`grant_event_id` 字节序较小、`issuer_did` 字节序较小继续比较。

#### 偏序定义

A `≻` B（A 严格优于 B）当且仅当：

1. `governance_layer(A)` 严格高于 `governance_layer(B)`（按上面顺序，`root > organization > space_admin > policy_membership > object > none`），或
2. `governance_layer(A) == governance_layer(B)` 且 `authority_kind(A)` 在同 layer 内严格优于 `authority_kind(B)`（`direct > delegated > self`，`none` 视作最低）。

`authority_kind=self` 仅在该 event kind 明确允许的 self/admission 范围内有意义；其他 layer 上的 `self` 视作 `none`。

#### 派生 scalar `auth_weight`

为方便 fixture、审计视图与诊断输出，可从 lattice 派生稳定 scalar：

| `governance_layer` | `direct` | `delegated` | `self` |
| --- | --- | --- | --- |
| `root` | 700 | — | — |
| `organization` | 650 | 640 | — |
| `space_admin` | 600 | 590 | — |
| `policy_membership` | 550 | 540 | — |
| `object` | 500 | 490 | — |
| `none` (action surface) | 200 | 190 | 100 |
| `none` (no grant) | — | — | 0 |

注意事项：

- `auth_weight` 是 lattice 的派生展示，**不是规范决策依据**。实现 MUST 用 lattice 偏序排序；当两份实现的 lattice 偏序结果一致而 scalar 不一致时，以 lattice 为准。
- `auth_weight` 间距（10）保留给将来同 layer 的细粒度授权来源（profile-specific authority、emergency override 等），新增条目 MUST 落入既有 layer，不得跨越上级 layer。
- 实现不得用本地权重表覆盖 lattice 偏序定义。

Policy hard deny、ban、quarantine、unknown critical feature、缺失必要 approval、未知 critical constraint、claim revocation 无法确认且该 claim 为必要条件时，MUST 在计算 `authority_class` 前使候选事件 fail closed、soft fail 或 quarantine。它们不得通过高 `authority_class` 被覆盖。

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
- `space_version`
- `kind`
- `state_key`（仅 state event）
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

上述保留字段是验证性 redaction stub 的默认集合。Space / reducer profile MAY 声明 `redaction_policy="anonymous"`，但该策略只影响普通 timeline、search、export preview 等用户可见 projection：这些 projection MUST 隐藏或替换原事件 `actor_id` / 物化对象 `created_by`，例如显示为 anonymous redacted sender。它不得从 canonical verification stub 中删除 `actor_id`、`proofs`、`actor_seq`、`prev_refs` 或 `auth_refs`，否则接收方将无法验证原始 Event chain、redaction 授权和审计责任。需要更强发送者隐私的 Space SHOULD 使用 pairwise DID / minimal-metadata E2EE；需要物理删除身份 metadata 时必须走 hard erasure receipt 和 legal-hold 边界，而不是重写已签名 Event。

以下 envelope 顶层字段 MUST 整体清除：

- `payload`（其中包括 `attachments`、`mentions`、`relations`、`client_generated`、对象正文等所有内容）
- `unsigned`
- `schema_profile_refs`（仅在 redaction policy 声明 minimal-metadata 时清除；普通 redaction 保留）
- `reducer_profile_ref`（同上）
- `required_features`（同上）
- `critical_extensions`（同上）

普通 redaction 默认保留 `schema_profile_refs` / `reducer_profile_ref` / `required_features` / `critical_extensions`，使下游能继续判断该 event 是否依赖未知 critical 语义。Minimal-metadata profile 的 redaction 才完全清除这些字段。

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

## 11. Soft Fail, Reject, Quarantine

- `soft_failed`：格式和签名有效，但缺上下文或暂时无法授权。可参与 backfill，不进入用户可见状态。
- `rejected`：格式、hash、签名、schema 或授权确定失败。不得进入 reducer。
- `quarantined`：基础授权可过，但被本地/联邦策略标记为高风险。不得自动展示，可供管理员审查。

Soft failed state event MAY 在后续上下文补齐后重新评估。Rejected event MUST NOT 自动复活，除非重新提交为新 event。

Frontier 与存储语义：

- `accepted` Event 才能推进 actor accepted frontier、Space reducer frontier、state hash 和 materialized projection。
- `soft_failed` Event MAY 进入 pending store、backfill 队列和诊断 API，但 MUST NOT 推进 accepted frontier、state hash 或用户可见 projection。上下文补齐后重新评估通过时，才以原 `event_id` 进入 accepted set。
- `rejected` Event MUST NOT 推进 accepted frontier，也不占据 accepted actor chain 中的 `actor_seq`。实现 MAY 保存 rejected envelope 的最小诊断记录或 abuse evidence，但不得把它返回为 accepted history；客户端展示时 MUST 标注为 rejected diagnostic，而不是普通事件。
- `quarantined` Event MUST NOT 自动进入 reducer 或普通 sync。管理员、policy server 或异步验证将其释放后，必须重新执行完整 validation，并以原 `event_id` 进入 accepted set；若最终拒绝，按 rejected 处理。
- 如果 actor 后续提交的 Event 以 soft-failed / quarantined / rejected Event 作为 `prev_refs`，接收方 MUST soft-fail 或 quarantine 后续 Event，直到该前序进入 accepted set；不得因为后续事件签名有效而跳过缺失或无效前序。
- 对同一 `event_id` 的相同 canonical bytes 重试保持幂等。对同一 `event_id` 的不同 canonical bytes，节点 MUST quarantine `duplicate_conflict`，并且不得让任一冲突版本推进 accepted frontier，除非本地已经有一个 accepted 版本；此时新冲突版本仍保持 quarantined/rejected diagnostic。

## 12. Space Upgrade

在 Contrix v1 中，Space 升级通过 `cx.space.upgrade` 在同一 `space_id` 上执行，不启用新 `space_version`。只增加 optional 字段、且不改变 auth / reducer 语义的升级 MAY 直接发布 enforcement 事件；引入新 critical feature、auth 规则、reducer 规则或加密语义的升级 MUST 使用多阶段流程：

```json
{
  "kind": "cx.space.upgrade",
  "state_key": "upgrade:cx.reducer.v1_1",
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

升级 MUST 保持 `space_id` 不变。升级事件必须包含 transition 声明，便于未支持目标 profile 的节点做 fail-closed。

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

### 12.1 Tombstone / Replacement

当一个 Space 被关闭、替换或迁移到新 Space 时，必须使用显式 tombstone：

```json
{
  "kind": "cx.space.lifecycle.set",
  "state_key": "tombstone",
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

### 12.2 Space Lifecycle State Machine

Space lifecycle 是 reducer state，不是本地服务开关。v1 使用以下状态：

所有 transition 通过单一 kind `cx.space.lifecycle.set` 写入，按 `state_key` 选择 facet：

| 当前状态 | Event | 下一状态 | 是否可恢复 | 主要效果 |
| --- | --- | --- | --- | --- |
| `active` | `cx.space.lifecycle.set` (state_key=`archive`, payload `archived=true`) | `archived` | yes | 从默认 active 列表和普通 discovery 中隐藏；普通业务写入默认 SHOULD reject，除非 policy 允许 archive maintenance。 |
| `archived` | `cx.space.lifecycle.set` (state_key=`archive`, payload `archived=false`) | `active` | yes | 恢复普通展示和写入。 |
| `active` / `archived` | `cx.space.lifecycle.set` (state_key=`freeze`, payload `frozen=true`) | `frozen` | yes | 临时写入冻结；只允许 redaction、export、legal hold、policy/account lifecycle、unfreeze 和管理员维护事件。 |
| `frozen` | `cx.space.lifecycle.set` (state_key=`freeze`, payload `frozen=false`) | `active` 或 `archived` | yes | 解除冻结，回到冻结前基础状态。 |
| `active` / `archived` / `frozen` | `cx.space.lifecycle.set` (state_key=`tombstone`) | `tombstoned` | no | 关闭或迁移 Space；拒绝新普通写入，只保留维护、审计和迁移证明。 |
| `active` / `archived` / `frozen` | `cx.space.lifecycle.set` (state_key=`destroy`) | `destroyed` | no | 不可恢复的 decommission marker；服务可按 retention / erasure policy 释放本地 payload，但仍不得伪造历史缺失。 |
| `tombstoned` | `cx.space.lifecycle.set` (state_key=`destroy`) | `destroyed` | no | tombstone 后的最终销毁或资源回收声明。 |

规则：

- `state_key=archive` / `state_key=freeze` 是可逆 state event；各自最新 accepted event 决定对应布尔状态。v1 不新增 `restore` / `unfreeze` kind 或单独 state_key。
- `frozen` 可以叠加在 `archived` 上；解除冻结后 MUST 回到冻结前的 archived/active 基础状态。
- `tombstoned` 和 `destroyed` 是 terminal state。后续普通业务 Event MUST reject；只允许 redaction、export、legal hold、account lifecycle、migration proof、snapshot/witness proof 和 policy 明确列出的维护类 Event。
- `destroy` 不等于全网物理删除。它只声明该 Space 已不可恢复地 decommission；已签名 Event、verification stub、legal hold 和外部副本仍按各自 policy 处理。
- 这些转换均需要 Space admin / owner / governance root 或 policy 声明的 lifecycle capability；policy hard deny 优先于 auth weight。
