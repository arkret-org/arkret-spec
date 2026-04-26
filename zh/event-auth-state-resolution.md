# Event Authorization and State Resolution

## 1. 目标

本文件定义 Contrix Space 内事件是否有效、状态如何收敛、冲突如何确定性解决、redaction 如何保留最小字段，以及 Space 版本如何升级。

任何支持联邦写入、多设备写入或离线写入的实现，MUST 实现本文件的 `cx.space.v1` 规则。

## 2. Space Version

每个 Space 的 create event MUST 包含：

```json
{
  "type": "cx.space.create",
  "space_version": "cx.space.v1",
  "content": {
    "space_kind": "collaboration",
    "initial_creators": ["did:uuid:..."],
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
4. 验证 `space_id`、`space_version`、`type`、`created_at`、`hlc` 与 schema。
5. 拉取并验证 `prev_refs` 和 `auth_refs` 指向事件的 hash。
6. 对 `auth_refs` 运行授权算法。
7. 对 `content` 运行类型级 schema validation。
8. 对策略服务、capability constraint、rate limit 和 abuse policy 运行本地检查。
9. 输出 `accepted`、`soft_failed`、`rejected` 或 `quarantined`。

节点 MUST NOT 因为事件来自可信 relay 就跳过任何步骤。

## 4. Auth Refs

每个写事件 MUST 包含 `auth_refs`。`auth_refs` 是授权当前事件所需的最小状态事件集合，不是完整状态快照。

`cx.space.v1` 的 auth refs 选择规则：

| 当前事件类型 | 必需 auth refs |
| --- | --- |
| `cx.space.create` | 无 |
| `cx.member.*` | `cx.space.create`、目标 actor 当前 membership、发送者 membership、相关 join rule、相关 capability grant |
| `cx.capability.grant` | `cx.space.create`、grantor membership、grantor 当前 grant/role/admin capability |
| `cx.capability.revoke` | 被撤销 grant、revoker membership、revoker revoke/admin capability |
| `cx.policy.*` | `cx.space.create`、actor membership、policy/admin capability、上一版同 key policy |
| `cx.space.child` | parent Space 的 `cx.space.create`、发送者 parent membership、`space.hierarchy.manage` capability、目标 child Space stripped create 或可验证引用 |
| `cx.space.parent` | child Space 的 `cx.space.create`、发送者 child membership、`space.hierarchy.manage` capability、目标 parent Space stripped create 或可验证引用 |
| `cx.space.inheritance_policy` | child Space 的 `cx.space.create`、child policy/admin capability、confirmed parent edge |
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
  "type": "cx.member.state",
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

## 6. Join Rule and History Visibility

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

## 7. Authorization Algorithm

对事件 `E`，节点 MUST：

1. 构造 auth state map：以 `(type, state_key)` 为 key，从 `auth_refs` 解析授权状态。
2. 验证所有 auth event 本身为 accepted，或在当前 state resolution 中被接受。
3. 验证 sender 的当前 membership。
4. 验证 sender 的 device 是否在事件时间有效，且未在 `created_at` 前撤销。
5. 验证 sender 持有 action 对应 capability；capability subject MUST 匹配 DID 或满足 selector。
6. 验证 capability constraint：时间、空间、对象、字段、速率、审批、设备、Applet 范围。
7. 验证 event type 的专用规则。
8. 验证 policy server hard deny、server ACL、ban list 与本地 quarantine list。

授权计算 MUST 使用事件 `created_at` 对应的 auth state，而不是接收时间的最新状态。撤销事件只影响其 causal frontier 之后的事件。

## 8. State Events

State event 是具有 `state_key` 的事件。其当前状态由 `(type, state_key)` 最新 accepted 事件决定。

以下事件类型是 `cx.space.v1` 标准 state event：

- `cx.space.create`
- `cx.space.join_rule`
- `cx.space.history_visibility`
- `cx.space.policy_server`
- `cx.space.schema`
- `cx.space.child`
- `cx.space.parent`
- `cx.space.inheritance_policy`
- `cx.space.upgrade`
- `cx.member.state`
- `cx.capability.grant`
- `cx.capability.revoke`
- `cx.policy.rule`
- `cx.mls.epoch`
- `cx.view.definition`

非 state event 仍可影响物化 projection，但不进入 auth state map，除非具体类型声明其为 auth dependency。

## 9. State Resolution

当多个分支对同一 `(type, state_key)` 给出不同 accepted state event 时，节点 MUST 运行 deterministic state resolution。

### 9.1 输入

- `base_state`: 最近共同祖先 state map。
- `state_sets`: 各分支 state map。
- `auth_chain`: 所有候选 state event 的 auth dependency 闭包。

### 9.2 输出

- `resolved_state`: 单一 state map。
- `conflict_records`: 被压制候选及原因。

### 9.3 算法

1. 将所有 state set 中相同 `(type, state_key)` 且 event id 相同的项放入 unconflicted state。
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

该算法 MUST deterministic。任何实现不得使用本地接收顺序、数据库自增 ID 或 relay 顺序作为 tie-breaker。

## 10. Redaction

`cx.redaction` 是 state-independent event，但其效果由 reducer 应用到目标事件。

被 redaction 后，事件只保留：

- `event_id`
- `space_id`
- `space_version`
- `type`
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

Space 升级通过 `cx.space.upgrade`：

```json
{
  "type": "cx.space.upgrade",
  "state_key": "",
  "content": {
    "from_space_id": "space:...",
    "to_space_id": "space:...",
    "to_space_version": "cx.space.v2",
    "migration_policy": "copy_state_and_continue",
    "replacement_ref": "event:..."
  }
}
```

升级 MUST 创建新 `space_id`。旧 Space 进入 tombstone 状态后 SHOULD 只允许 read、redaction、export 和 migration proof。客户端 SHOULD 将旧 Space 视为历史归档，并在 UI 中跳转到新 Space。
