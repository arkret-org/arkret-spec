# Event Authorization and State Resolution

## 1. 目标

本文件定义 Contrix Space 内事件是否有效、状态如何收敛、冲突如何确定性解决、redaction 如何保留最小字段，以及 Space 版本如何升级。

任何支持联邦写入、多设备写入或离线写入的实现，MUST 实现本文件的 `space_version=1` 规则。

## 2. Space Version

每个 Space 的 create event MUST 包含：

```json
{
  "kind": "cx.space.create",
  "space_version": "1",
  "content": {
    "space_kind": "collaboration",
    "initial_creators": ["did:uuid:..."],
    "created_by_principal": "did:uuid:...",
    "owning_organizations": [],
    "default_discoverability": "invite_only",
    "default_join_rule": "invite",
    "history_visibility": "joined"
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
- upgrade compatibility rules

实现 MUST reject 未知 `space_version` 的写事件。实现 MAY 以只读方式展示未知版本事件，但 MUST NOT 将其作为本地 accepted state。

## 3. Event Validation Pipeline

收到事件后，节点 MUST 按以下顺序验证：

1. Parse canonical JSON，不接受重复 key、非规范 number、无效 UTF-8 或超过 profile 限制的对象。
2. 验证 `event_id` 等于事件 redaction 前 canonical bytes 的 multihash 派生值。
3. 验证 `proofs` 中 actor/device/service 签名。
4. 验证 `space_id`、`space_version`、`kind`、`created_at`、`hlc` 与 schema。
5. 拉取并验证 `prev_refs` 和 `auth_refs` 指向事件的 hash。
6. 对 `auth_refs` 运行授权算法。
7. 对 `content` 运行类型级 schema validation。
8. 对策略服务、capability constraint、rate limit 和 abuse policy 运行本地检查。
9. 输出 `accepted`、`soft_failed`、`rejected` 或 `quarantined`。

节点 MUST NOT 因为事件来自可信 Sync Service 就跳过任何步骤。

## 4. Auth Refs

每个写事件 MUST 包含 `auth_refs`。`auth_refs` 是授权当前事件所需的最小状态事件集合，不是完整状态快照。

`space_version=1` 的 auth refs 选择规则：

| 当前事件类型 | 必需 auth refs |
| --- | --- |
| `cx.space.create` | 无 |
| `cx.member.*` | `cx.space.create`、目标 actor 当前 membership、发送者 membership、相关 join rule、相关 capability grant |
| `cx.capability.grant` | `cx.space.create`、grantor membership、grantor 当前 grant/role/admin capability |
| `cx.capability.revoke` | 被撤销 grant、revoker membership、revoker revoke/admin capability |
| `cx.policy.*` | `cx.space.create`、actor membership、policy/admin capability、上一版同 key policy |
| `cx.space.discovery` | `cx.space.create`、actor membership、discovery/policy/admin capability、上一版 discovery state |
| `cx.space.moderation_policy` | `cx.space.create`、actor membership、moderation/policy/admin capability、上一版 moderation policy |
| `cx.space.policy_components` | `cx.space.create`、actor membership、policy/admin capability、上一版 policy component state |
| `cx.space.history_sharing_policy` | `cx.space.create`、actor membership、policy/admin capability、上一版 history sharing state、当前 encryption policy |
| `cx.space.child` | parent Space 的 `cx.space.create`、发送者 parent membership、`space.hierarchy.manage` capability、目标 child Space stripped create 或可验证引用 |
| `cx.space.parent` | child Space 的 `cx.space.create`、发送者 child membership、`space.hierarchy.manage` capability、目标 parent Space stripped create 或可验证引用 |
| `cx.space.inheritance_policy` | child Space 的 `cx.space.create`、child policy/admin capability、confirmed parent edge |
| `cx.space.organization` | `cx.space.create`、组织 DID 当前控制状态、组织签发或撤销该声明的 capability / service binding |
| `cx.entity.*` | actor membership、对应 create/update/delete capability、目标 entity 当前状态 |
| `cx.relation.*` | actor membership、relation type schema、source/target 可见状态、对应 relation capability |
| `cx.message.*` | actor membership、channel/topic 可见状态、send/edit/redact capability |
| `cx.mls.*` | actor membership、encryption policy、当前 epoch state、device trust state |
| `cx.redaction` | actor membership、被 redaction 事件、redact_own 或 redact_any capability |
| `cx.space.upgrade` | `cx.space.create`、当前 upgrade policy、creator/admin capability |

如果事件缺少必需 auth ref，节点 MUST soft fail 并尝试 backfill。若 backfill 后仍缺失，MUST reject。

## 5. Membership

Contrix 使用 `cx.member.state` 表达 actor 在 Space 中的成员状态：

```json
{
  "kind": "cx.member.state",
  "state_key": "did:uuid:actor",
  "content": {
    "membership": "join",
    "via": ["did:web:example.com"],
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

`cx.space.join_rule`:

- `private`：只允许 invite。
- `public`：任何 actor 可 join，但仍需通过 policy server 和 rate limit。
- `knock`：外部 actor 可 knock，不可直接 join。
- `restricted`：actor 必须满足 `allowed_selectors` 中至少一个可验证条件。
- `knock_restricted`：不满足 restricted 条件者可 knock。

`cx.space.history_visibility`:

- `world_readable`：任何 actor 可读取明文或已授权公开内容。
- `shared`：当前和历史成员可读取加入前历史。
- `invited`：被邀请 actor 可读取 stripped preview state。
- `joined`：仅加入后历史默认可见。

E2EE Space 中，history visibility 只授权索引和密钥共享资格，不保证服务端能解密历史。

`cx.space.history_sharing_policy`:

`history_visibility` 只描述默认读取边界。E2EE Space 若允许新成员获取加入前的解密材料，MUST 额外声明 history sharing policy：

```json
{
  "kind": "cx.space.history_sharing_policy",
  "state_key": "",
  "content": {
    "enabled": true,
    "roles_that_can_share": ["admin", "history_curator"],
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
- policy 变更只影响变更后发起的共享动作，不追溯授权已经发送给旧成员的历史解密材料。

`cx.space.policy_components`:

复杂 Space SHOULD 将策略拆成可独立演进的组件，而不是把所有布尔开关塞进单个 policy 对象：

```json
{
  "kind": "cx.space.policy_components",
  "state_key": "",
  "content": {
    "components": {
      "roles": "cx:event:roles_policy",
      "preauth": "cx:event:preauth_policy",
      "asset": "cx:event:asset_privacy_policy",
      "logging": "cx:event:logging_policy",
      "bot": "cx:event:bot_policy",
      "message_expiration": "cx:event:expiration_policy",
      "operational": "cx:event:operational_policy",
      "history_sharing": "cx:event:history_sharing_policy"
    },
    "component_root": "sha256:canonical_component_set"
  }
}
```

组件语义：

- `roles`：把 UI role 或 compatibility role 映射到 capability bundle；role 不能替代 capability 检查。
- `preauth`：预授权加入、邀请链接、knock 审批和一次性 join token。
- `asset`：附件上传域、下载隐私、proxy/OHTTP 要求和媒体大小/类型限制。
- `logging`：消息保留、导出、审计、合规可见性和删除边界。
- `bot`：bot / Applet / bridge / agent 是否允许加入，是否必须标识为 automated actor。
- `message_expiration`：消息过期、tombstone、legal hold 和本地清理提示。
- `operational`：限流、fanout、最大成员数、最大附件数、服务故障处理。
- `history_sharing`：加入前历史和 MLS epoch key material 的共享规则。

`component_root` SHOULD 被 `cx.mls.commit.application_state_ref.policy_root` 覆盖。客户端如果支持 E2EE 且无法验证组件根，MUST fail closed，至少不得接受依赖未知组件的新写入或 MLS epoch。

`cx.space.plaintext_visible_services`:

非 E2EE / 非内容加密的私有 Space 若允许服务端处理正文或可逆派生内容，必须显式声明可见服务：

```json
{
  "kind": "cx.space.plaintext_visible_services",
  "state_key": "",
  "content": {
    "services": [
      {
        "service_did": "did:web:server.acme.example",
        "service_type": "principal_server",
        "purposes": ["repo", "sync", "backfill"],
        "visibility": "private_plaintext"
      },
      {
        "service_did": "did:web:index.acme.example",
        "service_type": "index_node",
        "purposes": ["search", "notification", "preview"],
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
- 该 state event 的撤销或覆盖按普通 state resolution 生效；生效点之后不得继续向旧服务发送非加密私有内容。

### 6.1 Organization Ownership and Endorsement

组织所有权不是服务器本地配置，也不是 Space 名称、域名、图标或 UI 文案。组织所有权 MUST 由组织 principal 的可验证声明表达。

`cx.space.create` MAY 包含：

- `created_by_principal`：实际创建 Space 的 principal DID，可能是组织 DID、员工 DID、agent DID 或托管服务 DID。
- `owning_organizations`：创建时已由组织 DID 背书的 organization DID 列表。该字段为空时，Space 不得被展示为任何组织的 official Space。

若 Space 创建后才获得组织认可，组织 MUST 发布或共同签名 `cx.space.organization` state event：

```json
{
  "kind": "cx.space.organization",
  "state_key": "did:web:acme.example",
  "content": {
    "organization_did": "did:web:acme.example",
    "relationship": "owner",
    "status": "active",
    "endorsed_by": "did:web:acme.example#governance-key-1",
    "scope": {
      "official": true,
      "allowed_labels": ["official", "support"],
      "service_dids": [
        "did:web:server.acme.example",
        "did:web:index.acme.example"
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
- `host`：组织托管 Sync Service / Index / Blob / Media 等服务，但不声明内容所有权。
- `issuer`：组织只作为 trusted issuer / policy issuer。

客户端判断一个 Space 是否为某 Organization 官方创建或官方认可时，MUST 同时验证：

1. Organization DID 可解析，且 DID Document / key log 在事件时间有效。
2. `cx.space.create.created_by_principal` 是该 organization DID，或存在 active 的 `cx.space.organization` event。
3. `cx.space.organization` 的签名 key 属于 organization DID 的当前或事件时点有效控制链，或属于 organization DID 明确绑定的 governance service DID。
4. `relationship` 为 `owner` 或 `sponsor`，且 `scope.official=true`。
5. 该声明未过期、未被 `status=revoked` 或后续同 `state_key` state event 覆盖。
6. Space id、Space create event hash 和 organization DID 都被签名覆盖，防止把同一声明移植到另一个 Space。

客户端 MUST NOT 因以下信号把 Space 展示为 official：

- Space 名称、头像、主题或简介包含组织名。
- `space_id`、alias、handle、域名或邮箱后缀看起来属于组织。
- Sync Service / Index 由组织托管。
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

授权计算 MUST 使用事件 `created_at` 对应的 auth state，而不是接收时间的最新状态。撤销事件只影响其 causal frontier 之后的事件。

## 8. State Events

State event 是具有 `state_key` 的事件。其当前状态由 `(kind, state_key)` 最新 accepted 事件决定。

以下事件类型是 `space_version=1` 标准 state event：

- `cx.space.create`
- `cx.space.discovery`
- `cx.space.moderation_policy`
- `cx.space.join_rule`
- `cx.space.history_visibility`
- `cx.space.policy_server`
- `cx.space.schema`
- `cx.space.child`
- `cx.space.parent`
- `cx.space.inheritance_policy`
- `cx.space.organization`
- `cx.space.upgrade`
- `cx.member.state`
- `cx.capability.grant`
- `cx.capability.revoke`
- `cx.policy.rule`
- `cx.mls.epoch`
- `cx.view.definition`

非 state event 仍可影响物化 projection，但不进入 auth state map，除非具体类型声明其为 auth dependency。

## 9. State Resolution

当多个分支对同一 `(kind, state_key)` 给出不同 accepted state event 时，节点 MUST 运行 deterministic state resolution。

### 9.1 输入

- `base_state`: 最近共同祖先 state map。
- `state_sets`: 各分支 state map。
- `auth_chain`: 所有候选 state event 的 auth dependency 闭包。

### 9.2 输出

- `resolved_state`: 单一 state map。
- `conflict_records`: 被压制候选及原因。

### 9.3 算法

1. 将所有 state set 中相同 `(kind, state_key)` 且 event id 相同的项放入 unconflicted state。
2. 将不同 event id 的项放入 conflicted set。
3. 计算 auth difference：所有 conflicted event 的 auth chain 差集。
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
   - `auth_weight`：creator/admin capability 优先于普通 grant。
   - `causal_depth`：因果上更新者优先。
   - `hlc`：更大 HLC 优先。
   - `event_id`：字节序更小者作为最终 tie-breaker。
7. 依次尝试候选事件；能在 provisional auth state 下通过授权者进入 resolved state。
8. 如果同 key 所有候选均不通过授权，回退到 base_state；若无 base，则该 key unset。
9. 输出 conflict record，索引器 SHOULD 暴露给审计视图。

该算法 MUST deterministic。任何实现不得使用本地接收顺序、数据库自增 ID 或 Sync Service 顺序作为 tie-breaker。

## 10. Redaction

`cx.redaction` 是 state-independent event，但其效果由 reducer 应用到目标事件。

被 redaction 后，事件只保留：

- `event_id`
- `space_id`
- `space_version`
- `kind`
- `state_key`
- `sender`
- `sender_device`
- `created_at`
- `hlc`
- `prev_refs`
- `auth_refs`
- `hashes`
- `proofs`
- `redacted_by`
- `redaction_reason_code`

以下字段 MUST 清除：

- `content`
- `unsigned`
- `attachments`
- `mentions`
- `relations`
- `client_generated`

Redaction 不保证物理删除。Blob 删除、密钥销毁和法律擦除由 `media-and-blob.md` 与 `account-lifecycle.md` 定义。

## 11. Soft Fail, Reject, Quarantine

- `soft_failed`：格式和签名有效，但缺上下文或暂时无法授权。可参与 backfill，不进入用户可见状态。
- `rejected`：格式、hash、签名、schema 或授权确定失败。不得进入 reducer。
- `quarantined`：基础授权可过，但被本地/联邦策略标记为高风险。不得自动展示，可供管理员审查。

Soft failed state event MAY 在后续上下文补齐后重新评估。Rejected event MUST NOT 自动复活，除非重新提交为新 event。

## 12. Space Upgrade

在 Contrix v1 中，Space 升级通过 `cx.space.upgrade` 在同一 `space_id` 上执行，不启用新 `space_version`：

```json
{
  "kind": "cx.space.upgrade",
  "state_key": "",
  "content": {
    "target_schema_profile": "cx.schema.v1",
    "target_reducer_profile": "cx.reducer.v1",
    "migration_policy": "copy_state_and_continue",
    "compatibility_mode": "legacy_ignore_unknown_fields",
    "replacement_ref": "event:..."
  }
}
```

升级 MUST 保持 `space_id` 不变。升级事件必须包含兼容声明，便于未升级节点做 fail-closed。

升级规则：

- `cx.space.upgrade` MUST 由拥有 `space.upgrade` 或等价 admin capability 的 actor 发起。
- `target_schema_profile`、`target_reducer_profile`、`migration_policy`、`compatibility_mode` 和 `replacement_ref` 必须被事件签名覆盖。
- `replacement_ref` MAY 指向迁移计划、snapshot manifest 或新 profile 描述，但不能指向未签名的外部说明。
- 未支持目标 profile 的节点 MUST 停止接受依赖新语义的写入；MAY 继续只读展示升级前的 accepted history。
- 升级不得重写历史 event hash；任何 state 迁移都必须表现为新的 signed event、snapshot 或 reducer profile 输出。

### 12.1 Tombstone / Replacement

当一个 Space 被关闭、替换或迁移到新 Space 时，必须使用显式 tombstone：

```json
{
  "kind": "cx.space.tombstone",
  "state_key": "",
  "content": {
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
- Tombstone 不自动授予新 Space 读取旧 Space 历史的权限；历史访问仍受旧 Space 的 history visibility、capability、E2EE epoch 和 retention policy 约束。
