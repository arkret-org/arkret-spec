# Operations And Sync

## 1. 目标

Contrix 是面向协作对象的分布式发布、传播、查询与收敛协议。

同步层必须支持：

- actor 侧可验证发布
- append-only 审计日志
- Flow identity 与 branch 能力
- Flow `discussion` branch / Message 时间线
- Board-Space / List-Space / Flow 工作流
- Morph 开放对象
- 离线写入
- 最终一致收敛

## 2. 核心角色

Contrix v1 区分：

- `client`
- `agent`
- `event_store`
- `principal_server`
- `sync_service`
- `blob store`

### 2.1 Event Store

Contrix v1 不把用户数据仓库作为协议一等概念。协议的唯一 canonical fact 是 **signed Event Envelope**。

Event Store 是 Principal Server、客户端、本地节点或授权副本保存 Event 的服务/存储能力。它不是独立权威对象，也不要求实现 atprotocol/Git 式数据仓库。实现可以用数据库、append-only file、Merkle log、object store、content-addressed block store 或其他存储引擎保存 Event；协议只要求下列语义可验证：

- event store：保存 signed Event Envelope。
- per-actor event chain：由 `actor_id`、`actor_seq` 和 `prev_refs` 表达 actor 自己的发布顺序。
- frontier / cursor：按 actor、Space 或查询范围暴露调用方可见的同步前沿。
- proof material：签名、hash、DID key 状态引用和可选 witness receipt。

网络上的 `/events/*` 是 Event 提交、读取、回填和前沿查询 API surface。接收方验证 Event 时 MUST 校验 Event 签名、DID 控制链、canonical hash、`actor_seq` 路径递增约束、`prev_refs` 因果约束、`auth_refs` 授权依赖和 `event_id` 幂等性。

实现 MAY 发布 Event batch receipt、checkpoint、snapshot 或 witness receipt 加速恢复和审计，但这些对象不得成为 canonical history 的必经层，也不得替代 Event Envelope 本身的签名责任。

### 2.2 Principal Server / Sync Service

Principal Server 是 principal 控制或明确委托的服务边界；Sync Service 是该服务器上的 Space 增量同步能力。

Sync Service 聚合本服务器授权可见的 Space Event，并提供订阅、fanout、backfill、ephemeral signaling 和初级过滤。它不是独立第三方服务器，也不应由未被 principal 或 Space policy 委托的第三方接触非加密私有内容。

Principal Server / Sync Service MUST NOT：

- 伪造 principal 的 Event。
- 把自己托管的 Space 自动标记为组织 official Space。
- 用本地数据库状态替代 Space reducer、capability 和 policy 判定。
- 阻止客户端从源 Event、witness receipt、snapshot frontier 或其他受信 Principal Server 交叉验证历史。
- 将非加密私有正文转发给未被发送方、接收方或 Space policy 明确委托的服务。

## 3. Event-first 发布模型

Contrix 采用 Event-first 模型：

1. actor/device/service 生成 signed Event Envelope。
2. `/events/*` 或等价 transport 接收、校验、幂等保存 Event。
3. Principal Server / Sync Service 同步调用方授权可见的 Space Event。
4. client reducer 将 accepted Event 集合归约为当前态；客户端可选择生成本地搜索索引和 View projection。

这套模型同时适用于：

- Flow / Message
- Board-Space / List-Space / Flow
- Morph

## 4. Event Batch Receipt / Checkpoint

Event 是 canonical history。Event batch receipt、checkpoint 和 snapshot 只是加速层或审计证明，不是 reducer 输入的替代物。

实现 MAY 为一批已接受 Event 生成签名 receipt：

```json
{
  "receipt_id": "cx:receipt:01js0rcp000000000000000000",
  "issuer": "did:web:alice.example.net",
  "scope": {
    "actor_id": "did:web:alice.example.com",
    "space_id": "cx:space:01js0sp0000000000000000000"
  },
  "frontier": {
    "actor_seq": 144,
    "event_hash": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
  },
  "events": [
    "cx:event:01js0ev0000000000000000000",
    "cx:event:01js0ew0000000000000000000"
  ],
  "created_at": "2026-04-22T08:30:00Z",
  "proofs": []
}
```

Receipt 可用于 read-your-writes、回放完整性检查、witness 证明或跨服务 backfill 对账。接收方 MUST 能在没有 receipt 的情况下验证单个 Event；也 MUST NOT 因缺少 batch receipt 而拒绝格式、签名、授权和因果均有效的 Event，除非某个高安全 deployment profile 明确要求额外 witness。

## 5. Wire Event Envelope

v1 的规范性 wire fact 只有 **Event Envelope**。Events API、Sync、Federation、Client write 和 reducer 都 MUST 以 `data-structures.md` 中的 `cx.schema.event.v1` Event Envelope 作为共享状态事实输入。

Service operation 名称可以描述提交、同步或联邦动作，但共享 wire fact 仍然只有 Event Envelope。`data-structures.md` 中的 Canonical Operation Object 只允许作为 SDK 内部 builder、离线草稿或内容寻址中间对象；它进入网络、联邦、sync 或 reducer 前 MUST 被封装成 Event Envelope。互操作 profile 不得要求对端同时理解 Canonical Operation Object 和 Event Envelope。

Event Envelope 的 `kind` 是标准事件类型，`content` 是事件负载，`prev_refs` 表示 actor event chain 前序，`auth_refs` 表示授权依赖。标准 `cx.*` Event kind 不得写入顶层 `type` 或 `content.type`；`type` 只用于物化对象、外部标准对象或 payload schema 明确声明的 discriminator。`target_ref`、`idempotency_key`、客户端事务 ID 等可放入 `content` 或 `unsigned`，但不得替代 `event_id`、`prev_refs`、`auth_refs`、`actor_seq` 和签名绑定。

如果事件依赖接收方可能不理解的新语义，发送方 MUST 在 Event Envelope 顶层声明 `required_features` 或 `critical_extensions`。这些字段和 `schema_profile_refs`、`reducer_profile_ref` MUST 进入 canonical event bytes、event digest 和 proof `payload_hash`。接收方不支持任何 critical feature 时 MUST fail closed，返回 `unsupported_feature`、`schema_violation`、`soft_fail` 或 `quarantine`，不得把事件当作普通已知语义接受。

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "space_version": "1",
  "actor_id": "did:web:alice.example.com",
  "actor_seq": 42,
  "kind": "cx.flow.update",
  "created_at": "2026-04-22T08:30:00Z",
  "hlc": "01970e589d21-0007-a13f9c2e",
  "prev_refs": [
    "cx:event:01js0et0000000000000000000"
  ],
  "auth_refs": [
    "cx:event:01js0gr0000000000000000000"
  ],
  "content": {
    "flow_id": "cx:flow:01js0cd0000000000000000000",
    "patch": {
      "fields.status": "review"
    }
  },
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#device-laptop",
      "payload_hash": "sha256:...",
      "created_at": "2026-04-22T08:30:00Z",
      "jws": "base64url..."
    }
  ]
}
```

`operation_id` 这个名称只保留给服务 API 的 canonical operation id（例如 `cx.sync.client_sync`）。Event Envelope、Canonical Operation Object、reducer input 和 typed ID 字段不得使用 `operation_id` 表达本地对象 ID；SDK 内部草稿对象使用普通 `id` 和可选 `idempotency_key`，且不得进入另一套排序、去重或签名规则。

## 6. 为什么需要 `prev_refs + hlc + actor_seq`

单一时间戳不足以支撑协作收敛。

Contrix v1 要求：

- `prev_refs` 表示 actor event chain 的直接前序
- `hlc` 表示近实时逻辑时间
- `actor_seq` 表示 actor 因果路径高度和防回退索引

三者的职责边界固定如下：

- `prev_refs` / `auth_refs` 是因果事实。HLC 更大不得覆盖缺失或相反的因果依赖。
- `actor_seq` 在同一 actor 的任一因果路径上 MUST 严格递增；它不是 device-local sequence，也不是全局 total order。生产者 SHOULD 令新事件的 `actor_seq` 大于其同 actor 直接 `prev_refs` 的最大 `actor_seq`。
- 同一 actor 的多个设备或离线写入 MAY 产生同一高度的 sibling fork。接收方若已接受同 actor 更高 `actor_seq`，不得仅因新事件的 `actor_seq` 较低或相同而拒绝；只有当该事件不能从任何已知 frontier 回填为有效历史分支、违反直接前序递增规则、或与同一 `event_id` 的 canonical hash 冲突时，才 MUST reject 或 quarantine。
- 同一高度的 sibling fork 只允许出现在互不因果依赖的分支上。若事件 B 的 `prev_refs` 包含同 actor 事件 A，B 的 `actor_seq` MUST 大于 A；两个同 actor、同 `actor_seq` 的事件 MUST NOT 把对方作为直接或间接前序。
- 同一 actor 发布的新 durable Event SHOULD 以其上一个 accepted durable Event 为唯一直接 `prev_refs`。多设备或离线分叉导致多个 actor frontier head 时，生产者 MAY 使用多个同 actor `prev_refs` 合并分支，并 SHOULD 设置 `actor_seq = max(prev_actor_seq) + 1`；接收方 MUST 把 actor frontier 表达为 head set，而不是单个最大序号，并保留 fork / merge 证据按 reducer 规则收敛。
- `prev_refs` 或 `auth_refs` MUST NOT 包含当前 `event_id`。任何自引用事件 MUST 以 `causal_conflict` reject。
- 当 `prev_refs` 表示 A 因果先于 B，但 `hlc(A) > hlc(B)` 时，因果顺序仍为 A -> B；实现 MAY 记录 clock skew warning，但不得用 HLC 反转因果。
- 当两个事件之间没有因果路径时，reducer 才可使用 deterministic ordering 中的 HLC / actor / event hash 作为 tie-breaker。

实现 MUST NOT 把 Sync Service 到达顺序、数据库自增 ID 或 HTTP 接收顺序当作协议顺序。

### 6.1 跨 Actor 依赖与确定性排序

Contrix v1 将依赖关系和 winner tie-breaker 分开处理：

- `prev_refs`、`auth_refs` 和具体 event kind 声明的 content-level causal refs 共同形成 accepted dependency graph。
- 若事件 B 的 dependency closure 包含事件 A，任何 canonical replay、timeline recovery 或 reducer input normalization 都 MUST 在拓扑上令 A 先于 B；即使 `hlc(A) > hlc(B)` 也不得反转。
- `auth_refs` 表示“B 的授权判定必须能看到 A”，不表示 A 的业务 payload 自动覆盖 B，也不额外提高 A 的 state resolution 权重。它只影响 B 是否可进入 accepted set、B 的 auth state map 和 deterministic dependency depth。
- 只有当两个 accepted Event 在 dependency graph 中互不可达时，才使用 HLC、Actor ID、`actor_seq`、`event_id` / hash 作为 deterministic total-order tie-breaker。
- Reducer 的 state conflict winner 仍按 `event-auth-state-resolution.md` 的 priority class、`auth_weight`、`causal_depth`、HLC 和 event id 规则执行；timeline 展示顺序不得被反向用于授权。

因此，跨 actor 的 `auth_refs` 会创建可验证依赖边界，但不会引入全局共识时钟或服务端接收顺序。

参考验证算法：

```
function validate_actor_seq(event, known_frontiers):
    actor = event.actor_id
    seq = event.actor_seq

    // 规则 1: 直接前序递增
    prev_seqs = [e.actor_seq for e in event.prev_refs if e.actor_id == actor]
    if prev_seqs:
        if seq <= max(prev_seqs):
            reject("actor_seq must exceed direct prev_refs max")

    // 规则 2: 防回退 — 低于所有已知 frontier heads 时先回补上下文
    if actor in known_frontiers:
        frontier_heads = known_frontiers[actor]  // head set, not single max
        if all(seq < h for h in frontier_heads):
            soft_fail("actor_seq below known heads; backfill required")

    // 规则 3: 无自引用
    if event.event_id in event.prev_refs or event.event_id in event.auth_refs:
        reject("self-referential event")

    accept()
```

低于所有已知 frontier head 的事件不应被立即永久拒绝，因为它可能是稍后回补到达的合法历史分支。接收方 MUST 先尝试 backfill 或用可验证 snapshot 证明该事件能连接到某个有效分支；只有在确认无法连接、直接前序递增规则被破坏、或同 `event_id` hash 冲突时，才 reject / quarantine。

该算法只验证 `actor_seq` 语义。完整的 Event 验证还必须包括签名、schema、capability、Space policy、因果依赖（`prev_refs` / `auth_refs` 存在性）和 HLC 合理性检查。

## 7. 标准 Event Kind

标准 `Event.kind` 的机器可读 source of truth 是 `artifacts/registry/event-kind-registry.json`；`schema-registry.md` 只是文档视图。实现必须拒绝未注册、未带 `cx.` 前缀或未在服务端能力清单中声明的标准事件类型。自定义事件不得使用 `cx.` 前缀，除非已纳入标准 registry。

registry 的 `wire_scope` 决定 kind 能进入哪条 wire path：只有 active 且 `wire_scope=durable_event` 的 kind 可以进入共享 Event Envelope 历史、参与 actor chain、推进 reducer frontier 或 state hash；`wire_scope=actor_private_event` 只能用于加密 account data 或 actor-private stream；`wire_scope=ephemeral_event` 只能走 ephemeral channel，MUST NOT 增加 `actor_seq`、`prev_refs`、state hash 或 reducer frontier。生产者不得发出未声明的 wire_scope。

本节列出 Event-first 写路径中的核心 durable Event kind，不替代 registry。

### 7.1 Space / Schema / Policy / Discovery

- `cx.space.create`
- `cx.space.update`
- `cx.space.archive`
- `cx.space.freeze`
- `cx.space.destroy`
- `cx.space.schema`
- `cx.space.policy`
- `cx.space.policy_server`
- `cx.space.policy_components`
- `cx.space.plaintext_visible_services`
- `cx.space.history_visibility`
- `cx.space.join_rule`
- `cx.space.discovery`
- `cx.organization.discovery`
- `cx.schema.define`
- `cx.schema.update`
- `cx.policy.set`

### 7.2 Flow

- `cx.flow.create`
- `cx.flow.update`
- `cx.flow.archive`
- `cx.flow.restore`
- `cx.flow.convert`
- `cx.flow.branch.enable`
- `cx.flow.branch.disable`
- `cx.flow.branch.update`
- `cx.flow.branch.set_primary`
- `cx.flow.branch.member`
- `cx.flow.branch.history_visibility`
- `cx.flow.branch.policy_components`
- `cx.flow.move`
- `cx.flow.reorder`

`cx.flow.*` 只修改 Flow 自身、branch 配置、branch access override 或 Flow 在 Board/List 中的位置。它们不得直接写入 Message 正文或 Morph 正文内容。`cx.flow.branch.*` 的 reducer 产物是 Flow `branches[]` 的当前态，而不是新的独立对象。

### 7.3 Message

- `cx.message.create`
- `cx.message.revise`
- `cx.message.redact`
- `cx.reaction.add`
- `cx.reaction.remove`

### 7.4 Morph / Relation / View

- `cx.morph.create`
- `cx.morph.update`
- `cx.morph.archive`
- `cx.morph.restore`
- `cx.relation.create`
- `cx.relation.update`
- `cx.relation.delete`
- `cx.container.move_item`
- `cx.container.rebalance`
- `cx.view.create`
- `cx.view.update`
- `cx.view.reconcile`

`cx.view.*` 只修改 View definition，例如 query、projection kind、renderer、visible fields、layout、grouping 或 shared saved view 配置。它不得用于保存 Flow 所属 List-Space、Flow rank、List-Space rank、discussion membership、Message timeline、Relation active state 或对象字段的唯一真相。

### 7.5 Membership / Invite / Capability

- `cx.member.state`
- `cx.invite.create`
- `cx.invite.cancel`
- `cx.invite.accept`
- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.6 Profile / Device / Space Key

- `cx.profile.update`
- `cx.profile.space_override`
- `cx.device.authorized`
- `cx.device.revoked`
- `cx.device.list_update`
- `cx.mls.epoch`（由 winning `cx.mls.commit` 派生的 epoch checkpoint）
- `cx.mls.keypackage`
- `cx.space_key.share`
- `cx.space_key.withheld`
- `cx.mls.proposal`
- `cx.mls.commit`
- `cx.mls.commit_failed`
- `cx.mls.welcome`
- `cx.audit.accessed`
- `cx.redaction`

`cx.profile.update`、`cx.device.*` 与 `cx.session.grant` 是 durable Event Envelope kind，但其规范作用域是 principal control Space。生产者 MUST 使用目标 principal 的 `principal_control_space_id` 作为 `space_id`；普通协作 Space 只能通过 `auth_refs`、verified snapshot 或 policy proof 引用这些身份状态，不得把全局 profile、device 或 session 控制事件混入协作 Space history。`cx.profile.space_override` 若作为共享 Space history 传播，MUST 使用目标 Space 的 `space_id` 并通过该 Space policy；若作为 principal control profile state 传播，MUST 在 content 中显式绑定目标 Space。

以下标准 kind 不属于共享 durable Space history，不能列入本节 durable 写路径：

- `cx.read.marker`：`actor_private_event`，只能进入 encrypted account data 或 actor-private stream。
- `cx.receipt.read`：`ephemeral_event`，只能走 ephemeral / receipt stream，不推进 `actor_seq`、Space reducer frontier 或 state hash。

## 8. 操作体原则

非 create 类操作 SHOULD 只携带 delta，而不是完整对象快照。对象字段更新的标准 delta 格式是 `cx.patch.v1`，定义见 `../models/data-structures.md#19-field-patch-cxpatchv1`；实现不得用私有 dot-path 解析规则替代该格式。Event Envelope 中，patch 永远嵌入 `content.patch`，目标对象用 `content.flow_id`、`content.morph_id`、`content.relation_id`、`content.view_id` 或该 kind schema 声明的等价字段表达。

对于 `branches` 这类具名集合数组，patch path MUST 使用 schema 允许的 selector 段，例如 `branches[name=discussion].access.permissions`；不得使用数字下标，因为不同副本上的数组物理顺序不是授权或 reducer 语义。

例如：

- `cx.flow.update` 只带字段变更
- `cx.flow.move` 只带目标 List 和新 rank
- `cx.message.revise` 只带新正文
- `cx.message.redact` 只带目标消息与原因
- `cx.morph.update` 只带 Morph 字段 patch
- `cx.view.update` 只带投影定义 patch；通过 View 触发的对象变更仍使用对应对象 Event kind

### 8.1 Flow Branch Enable

`cx.flow.branch.enable` 为 Flow 开启一个 branch。v1 标准 branch name 为 `synthesis` 和 `discussion`；profile MAY 声明更多 branch name。

```json
{
  "kind": "cx.flow.branch.enable",
  "target_ref": "cx:flow:01js0sb0000000000000000000",
  "content": {
    "flow_id": "cx:flow:01js0sb0000000000000000000",
    "branch": "discussion",
    "config": {
      "profile": "discussion",
      "access": {
        "membership": "branch_scoped",
        "permissions": "branch_scoped",
        "history_visibility": "joined"
      }
    }
  }
}
```

规则：

- enable/disable 不改变 Flow identity。
- enable `discussion` branch 使用 Flow / Space 默认 access；只有 config 或后续 policy state 明确声明 `branch_scoped` 时，才创建独立 membership/history/E2EE 边界。
- Flow synthesis 可见只有在有效 access policy 继承或授予 discussion 读取时，才代表 discussion 内容可读；projection 必须按有效 branch access 裁剪。
- 切换默认入口时应通过 `cx.flow.branch.set_primary`，Reducer MUST 保证同一 Flow 至多一个 active branch 设置 `is_primary=true`。若没有显式 primary，且 `synthesis` 与 `discussion` 同时存在，默认入口 MUST 派生为 `synthesis`。
- 发送 `cx.message.*` 到未启用的 discussion branch MUST 返回 `discussion_branch_disabled` 或等价 fail-closed 结果。

## 9. Flow 有序操作

### 9.1 `cx.flow.move`

`cx.flow.move` 用于跨 List-Space 移动 Flow。它移动的是 Flow 在一个 Board-Space 内的主位置，而不是修改 branch 定义。

```json
{
  "kind": "cx.flow.move",
  "target_ref": "cx:flow:01js0tk0000000000000000000",
  "content": {
    "board_id": "cx:space:01js0bd0000000000000000000",
    "flow_id": "cx:flow:01js0tk0000000000000000000",
    "from_list_id": "cx:space:01t0d000000000000000000000",
    "to_list_id": "cx:space:01rev1ew000000000000000000",
    "rank": "mV",
    "expected_position": {
      "list_id": "cx:space:01t0d000000000000000000000",
      "rank": "h0",
      "relation_id": "cx:relation:0101d000000000000000000000"
    }
  }
}
```

Reducer 语义：

1. 验证 actor 对 `board_id`、`flow_id`、`from_list_id` 和 `to_list_id` 的 move/reorder 权限。
2. 验证 `to_list_id` 是 `board_id` 下的 active List-Space（`kind="list"` 且为其 child space）。
3. 验证目标 Flow 所属 Space schema/profile 允许它进入该 Board。
4. 在 reduced state 中关闭同一 `(board_id, flow_id)` 下其他 active position edge。
5. 创建或更新 `to_list_id --contains--> flow_id` 的 active Relation，并把 rank 设置为 `rank`。
6. 对相同 Event 保持幂等。

`cx.flow.move` 不得把 `board_id`、`list_id` 或 `rank` 写入 Flow canonical object 作为唯一真相源。View projection MAY 返回这些派生字段，但必须能追溯到 active position edge 和 reducer frontier。

CAS 语义：`expected_position` 描述的是移动前源 List 中 Flow 的当前位置。Reducer MUST 验证 `expected_position.list_id`、`expected_position.rank` 和 `expected_position.relation_id` 与当前 reduced state 一致；不一致时 SHOULD 返回 `cas_conflict`，除非 policy 明确允许 non-CAS move。目标 List 的 rank 不要求 CAS（由 reducer 按目标 List 当前内容计算或接受客户端提供的 rank）。`cx.flow.move` 不要求源侧 CAS 的场景：若 `expected_position` 缺失或为空，reducer SHOULD 接受移动但 MUST 在目标侧执行 `(board_id, flow_id)` 去重（关闭旧 position edge）。

### 9.2 `cx.flow.reorder`

`cx.flow.reorder` 只改变同一 List-Space 内的 rank，不改变 List-Space membership。

```json
{
  "kind": "cx.flow.reorder",
  "target_ref": "cx:flow:01js0tk0000000000000000000",
  "content": {
    "board_id": "cx:space:01js0bd0000000000000000000",
    "list_id": "cx:space:01rev1ew000000000000000000",
    "flow_id": "cx:flow:01js0tk0000000000000000000",
    "rank": "mV",
    "expected_position": {
      "rank": "h0",
      "relation_id": "cx:relation:01p0s000000000000000000000"
    }
  }
}
```

`cx.flow.reorder` 不得改变 List-Space。若当前 List-Space 与 `expected_position` 不一致，除非 policy 明确允许 non-CAS reorder，否则实现 SHOULD 返回 `cas_conflict` 或标记为 stale reorder。

### 9.3 List-Space 排序

List-Space 在 Board-Space 内的顺序通过 `cx.space.update` 更新 List-Space 的 `rank` 字段来改变。它不得移动 Flow。

### 9.4 `cx.flow.convert`

`cx.flow.convert` 将同一个 Flow 的目标 branch 标记为唯一 primary，并可确保目标 branch 存在。

```json
{
  "kind": "cx.flow.convert",
  "target_ref": "cx:flow:01js0tk0000000000000000000",
  "content": {
    "flow_id": "cx:flow:01js0tk0000000000000000000",
    "branch": "discussion",
    "ensure_branches": ["discussion"]
  }
}
```

规则：

- convert 要求独立 capability action `cx.flow.convert`。
- convert 不改变 `flow_id`。
- convert 不自动删除已有 discussion 历史或 synthesis 字段。
- 设置 `branch="discussion"` 时，Reducer MUST 保证 `discussion` branch 存在；若当前不存在，则 MUST 自动创建它，或在 policy 禁止时 reject。
- 切换到其他 branch 时不得自动 archive discussion branch；若要关闭讨论，必须显式写入 `cx.flow.branch.disable` 或等价 policy 动作。
- Reducer MUST 把目标 branch 的 `is_primary` 设为 true，并清除同一 Flow 其他 active branch 的 primary 标记。
- convert 不自动移除 Board/List 位置；是否移除由后续 `cx.flow.move` / profile policy 决定。

## 10. 验证流程

任何接收 Event Envelope 的 Events API 或 sync service，至少应校验：

1. 签名有效。
2. actor DID 可解析。
3. key 在操作时点有效。
4. `space_id` 与 target object 所属 Space 一致。
5. capability 在操作时点有效。
6. `prev_refs` / `auth_refs` 因果依赖不违反基本约束。
7. 对 Flow / Message / Morph 执行对象类型 schema validation；Board-Space 和 List-Space 按 Space schema 验证。

## 11. Snapshot

Snapshot 是加速层，不是真相源。

Snapshot manifest MUST 包含：

- `snapshot_ref`
- `space_id`
- `reducer_profile`
- `schema_profile_refs`
- `chunks[]`（每项包含 `chunk_ref`、`sha256`、`size_bytes`）
- `state_hash`
- `frontier`
- `event_set_commitment`
- `verification_hints`（可选，但 high-assurance profile 必须包含 inclusion proof 入口或 witness quorum）
- `signature`

客户端在采用 Snapshot 前 MUST 验证：

1. `signature` 是标准 detached proof，覆盖 `snapshot_ref`、`space_id`、`state_hash`、`frontier`、`event_set_commitment`、`chunks`、`reducer_profile`、`schema_profile_refs` 和 `verification_hints` 的 canonical manifest hash。
2. `signature.verification_method` 对应的 DID 必须是 Space creator、Space owner、当前有效 Space admin、Space policy 授权的 snapshot issuer 或 witness quorum 成员；该权限 MUST 按 manifest `created_at` 的 as-of auth state 验证，且该 auth state 必须覆盖 snapshot frontier 以及截至 `created_at` 可解析的相关 grant/revoke。若 signer 在 `created_at` 前已被撤销，或 revoke freshness 无法确认，客户端 MUST quarantine / reject snapshot。
3. 每个 chunk 的实际 SHA-256 与 manifest 中声明的 digest 一致。
4. `event_set_commitment` 的 root 必须与 manifest 声称覆盖的 Event frontier、actor sequence range 和 canonical event hash 集合一致。
5. high-assurance profile 中，客户端 MUST 能对抽样 Event ID、actor sequence range、soft-failed / quarantined 摘要发起 inclusion / omission challenge；issuer 无法提供证明时，客户端 MUST quarantine snapshot 或回退到原始 Event 回放。
6. 后续 admin / snapshot issuer revoke 不会自动否定此前在有效权限下签名的 snapshot，但客户端在用 snapshot 恢复后 MUST 继续回放 snapshot frontier 之后的 Event，再用当前 auth state 判断新写入。
7. 若任何校验失败，客户端 MUST 丢弃快照并回退到 `/events/*` / `/sync/backfill` 进行原始 Event 历史回放。

## 12. 同步面

### 12.1 Event Source Sync

用于 actor 历史恢复与审计重放。

### 12.2 Space Sync

用于 Space 级当前态与增量同步。

### 12.3 Flow Sync

用于 Flow 当前态、branch 状态、可见性裁剪后的 discussion preview 和 Flow activity projection。

Flow Sync MUST NOT 因为 actor 可读 Flow synthesis 就自动展开不可读 discussion timeline 或 Morph 内容。

### 12.4 Discussion Sync

用于 Flow `discussion` branch 的消息时间线、membership 和通知。

### 12.5 Board Sync

用于 Board/List/Flow 当前态、Flow position 和拖拽增量。

### 12.6 Query Surface

用于 view、搜索与 context timeline 查询。

### 12.7 Authz / Invite Surface

用于：

- 拉取 invite
- 拉取有效 grant 集
- 判断某个 Event 在当前 frontier 下是否可写

## 13. 首次加入 Space

推荐流程：

1. 获取 Space metadata。
2. 获取与自己相关的 invite / grant 视图。
3. 拉取最近 snapshot manifest。
4. 下载 snapshot chunk。
5. 从 snapshot frontier 之后拉取增量 event。
6. 本地执行 reducer。
7. 进入 cursor 增量订阅。

若客户端没有现成 DID，但只有 handle，则在步骤 1 之前 MUST 先完成 handle -> DID 解析与双向校验。

## 14. 选择性同步

选择性同步至少支持以下过滤维度：

- space
- flow
- flow branch
- board
- list
- object type
- morph type
- relation kind
- watched refs
- changed since cursor

## 15. 幂等、去重与重放

在去中心化同步里，重复提交与重复投递是常态。

因此：

- `event_id` MUST 全局稳定。
- 同一个 `event_id` 的完全相同内容 MAY 被重复接收。
- 若同一个 ID 对应不同内容，节点 MUST 拒绝并记为冲突。
- sync service SHOULD 以 `event_id` 去重，而不是按到达次数计数。

## 16. 冲突与收敛

Contrix 初版不引入全网共识链。

它要求：

- 对同一 Space
- 在同一有效 event 集下
- 所有正确实现的 reducer

最终收敛到相同当前态。

并发操作 tie-breaker 依次为：

1. 授权权重。
2. HLC（作为 winner 选择时取较大的已验证 HLC）。
3. Actor ID 字典序。
4. Event hash / `event_id` 字典序。

该 winner 顺序不同于客户端 timeline 的展示顺序；timeline 通常先按 `prev_refs` / `auth_refs` / content causal refs 的 dependency graph 做稳定拓扑排序，再对互不可达事件按 `causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC` 递增展示。实现不得使用本地接收顺序、数据库自增 ID 或 Sync Service 顺序作为 tie-breaker。

### 16.1 Reducer Contract

Reducer 是确定性纯函数，不是服务端当前数据库状态。对同一 `space_id`、同一 accepted Event 集合、同一 `space_version` 和同一 reducer profile，正确实现 MUST 产生相同的 `state_hash`、materialized object state、conflict records 和 reducer frontier。

Reducer 输入：

- accepted Event Envelope 集合及其 canonical bytes / digest。
- 每个 Event 的 `prev_refs`、`auth_refs`、`actor_seq`、HLC、kind、content、proof validation result 和 authorization result。
- `space_version`、schema profile refs、reducer profile ref、Space policy state 和必要 snapshot base。

Reducer 输出：

- materialized object state / state map。
- reducer frontier，表示已纳入当前结果的 Event head set。
- conflict records、redaction records、soft-fail dependency records 和 state hash。

规则：

- Reducer MUST 幂等：重复输入同一 Event 不得改变输出。
- Reducer MUST 对输入集合顺序不敏感；排序只能使用本规范声明的 deterministic ordering。
- Reducer profile MUST 明确声明它处理的 Event kind、state key 规则、字段 merge operator、redaction preserved fields、rank/order profile、schema interpretation profile 和 critical extension 行为。
- 两个 reducer profile 只有在 profile id、space_version、critical feature 集合、state resolution 规则和字段 merge operator 均匹配时，才可比较 state hash。否则必须声明为不同 projection，不得声称同一 canonical state。
- Partial reducer MAY 用于客户端视图、搜索、通知或只读 projection，但它输出的是 scoped projection frontier，不是 Space accepted reducer frontier。Partial reducer 遇到不支持但会影响其输出语义的 standard Event kind、critical extension 或 required feature 时 MUST fail closed、返回 `projection_incomplete` / `unsupported_feature`，或降级为明确标注的不完整视图；不得静默忽略后继续声称完整。

## 17. 字段级 merge 与对象级收敛

### 17.1 标量字段

例如：

- `flow.title`
- `flow.fields.status`
- `flow.summary`
- `morph.fields.severity`

建议使用基于 deterministic event order 的 LWW。

### 17.2 集合字段

例如：

- labels
- watchers
- linked refs

建议使用 OR-Set。

### 17.3 Board position

同一个 Flow 在同一 Board 内的唯一主位置 key 是 `(board_id, flow_id)`。同一 key 下出现多个 active position edge 时，Reducer MUST 按 deterministic event order 选择唯一 winner，并在 `conflict_records` 中记录 losers。

### 17.4 Graph cycle

对象在依赖图、引用图或容器图中产生循环时，Reducer MUST 按 deterministic event order 从高到低尝试保留候选；任何会形成非法循环的 candidate MUST 被标记为 `rejected_cycle`。

## 18. Message

- `cx.message.create` 是 append-only。
- `cx.message.revise` 形成 revision chain。
- 默认视图显示最新可见 revision。
- `cx.message.redact` 保留最小审计字段。

## 19. 授权时序收敛

授权不能只看墙上时钟，否则 revoke、迟到 Event、离线写入都会失真。

Contrix v1 要求：

- grant / delegate / revoke 本身也是 event。
- 某个业务 event 是否有效，由同一 reducer 顺序下的有效授权集合决定。
- 若某个写入在 reducer 顺序上已经晚于相关 revoke，则 MUST 视为无效。
- 若顺序无法确定，实现 SHOULD fail closed。

## 20. 可见性、密文负载与 E2EE 索引

ACL 不等于密文保护，Sync Service 也不应被迫看懂所有正文。

字段可见性分级：

- 可路由元数据：`space_id`、`target_ref`、`type`、`causal`。
- 明文业务元数据：轻量状态、rank、due date 等；若足以暴露敏感内容，接收它们的受托 search / projection 服务必须列入 `plaintext_visible_services`。
- 不透明加密负载：message body、附件内容等。

## 21. 本地存储建议

客户端 SHOULD 维护三层本地数据：

- raw events
- reduced snapshots
- materialized local indexes

## 22. 设计决定

Contrix v1 固定：

- signed Event Envelope 是 actor 发布单元。
- Event Envelope 是共享状态归约单元。
- Flow / Message、Board / List 工作流、Morph 共享同一同步协议。
- `flow` 是统一协作主对象；默认 branch 由 branch primary 解析规则表达。
- `synthesis` branch 承载整理后的正式表达与推进字段。
- branch 默认继承 Flow / Space access；discussion branch 的 membership、history visibility 和 E2EE 只有在显式 branch-scoped override 时独立收敛。
- invite / grant / snapshot 组成 Space bootstrap 主流程。
- event 重试必须幂等。
- 授权有效性由同一 reducer 顺序收敛。
- 密文负载可以被不解密的 sync service 转发。
- 撤回采用 redaction/tombstone 语义。
- hard erasure 只能删除本地 payload / blob / 派生内容，并保留事件图验证所需的最小 verification stub；不得重写 event hash、额外保留已擦除明文的未加盐 digest，或伪装事件从未存在。
- 冲突通过固定 reducer 规则收敛。

## 23. 规范性引用

- Cursor 编码与 opaque 语义见 `encoding.md`、`data-structures.md` 和 `encoding-conformance-vectors.md`。
- HLC 文本格式固定为 `<unix_ms_hex_12>-<logical_hex_4>-<node_id_hash_8>`，排序向量见 `encoding-conformance-vectors.md`。
- Snapshot manifest、chunk digest、`state_hash` 和签名规则见 `snapshot-schema.md`。
- Flow discussion branch / Message 语义见 `../models/conversation-model.md`。
- Flow / Board / List / Morph 语义见 `../models/object-model-standard.md` 和 `../models/views.md`。
