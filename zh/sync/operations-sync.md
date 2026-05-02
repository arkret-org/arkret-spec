# Operations And Sync

## 1. 目标

Contrix 是面向协作对象的分布式发布、传播、查询与收敛协议。

同步层必须支持：

- actor 侧可验证发布
- append-only 审计日志
- Room / Message 时间线
- Board / List / Card 工作流
- Morph 开放对象
- 离线写入
- 最终一致收敛

## 2. 核心角色

Contrix v1 区分：

- `client`
- `agent`
- `repo`
- `principal_server`
- `sync_service`
- `index`
- `blob store`

### 2.1 Repo

Repo 是某个 principal 的发布源。

Repo 是协议逻辑对象，不必等同于服务器进程。它至少包含：

- commit log：principal 签名的提交链。
- operation / event store：commit 引用的协作操作。
- head / cursor：当前已发布前沿。
- proof material：签名、hash、DID key 状态引用和可选 witness receipt。

Repo MAY 由客户端本地维护，也 MAY 由 Principal Server 托管，或被多个只读副本复制。网络上的 `/repo/*` 是 Principal Server 访问 Repo 的 API surface；它不是 Repo 权威本身。接收方验证 Repo 数据时 MUST 校验 commit 签名、DID 控制链、hash 链、序列单调性和 operation 幂等性。

Repo 分为常见两类：

- Principal Repo：人、组织、agent、Applet 等 principal 的发布日志，是 actor 写入的默认源。
- Space Repo：可选的 Space 级聚合或治理日志，用于保存 Space bootstrap、snapshot、policy checkpoint 或共同治理记录；它不得替代各 principal 对自身写入的签名责任。

### 2.2 Principal Server / Sync Service

Principal Server 是 principal 控制或明确委托的服务边界；Sync Service 是该服务器上的 Space 增量同步能力。

Sync Service 聚合本服务器授权可见的 Space operation，并提供订阅、fanout、backfill、ephemeral signaling 和初级过滤。它不是独立第三方服务器，也不应由未被 principal 或 Space policy 委托的第三方接触非加密私有内容。

Principal Server / Sync Service MUST NOT：

- 伪造 principal 的 commit 或 operation。
- 把自己托管的 Space 自动标记为组织 official Space。
- 用本地数据库状态替代 Space reducer、capability 和 policy 判定。
- 阻止客户端从源 Repo 或其他受信 Principal Server 交叉验证历史。
- 将非加密私有正文转发给未被发送方、接收方或 Space policy 明确委托的服务。

## 3. Repo-first 发布模型

Contrix 采用 repo-first 模型：

1. actor 先写自己的 repo
2. repo 发布 commit
3. Principal Server / Sync Service 同步 Space 相关授权 operation
4. index 归约为当前态

这套模型同时适用于：

- Room / Message
- Board / List / Card
- Morph
- Run / Memory

## 4. Repo Commit

Contrix v1 repo 以 commit 为发布单元。

```json
{
  "commit_id": "cx:commit:01JS0CMT000000000000000000",
  "repo_id": "did:web:alice.example.com",
  "prev_commit": "cx:commit:01JS0CMP000000000000000000",
  "seq": 144,
  "created_at": "2026-04-22T08:30:00Z",
  "operations": [
    "cx:operation:01JS0OP000000000000000000",
    "cx:operation:01JS0OQ000000000000000000"
  ],
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 5. Operation Envelope

每个 operation MUST 具备统一 envelope。Envelope 的 `kind` 是事件 kind，并通过 `causal`、`target_ref`、`authz_ref` 和 `proofs` 绑定写入语义。

本文中的 Operation Envelope 是 v1 默认 wire format，也是 reducer 接收的事实输入。`data-structures.md` 中的 Canonical Operation Object 是 repo / SDK 内部可内容寻址对象；实现 MAY 用它生成 Envelope，但不得在 federation 或 sync 中要求对端同时理解两个不同的 wire object。若一个 profile 直接传输 Canonical Operation Object，必须声明映射到本节 Envelope 的规则，并通过同一套 signature、hash、auth_refs 和 reducer conformance。

```json
{
  "operation_id": "cx:operation:01JS0OP000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "kind": "cx.card.update",
  "target_ref": "cx:card:01JS0CD000000000000000000",
  "causal": {
    "deps": [
      "cx:operation:01JS0OO000000000000000000"
    ],
    "hlc": "01970e589d21-0007-a13f9c2e",
    "actor_seq": 42
  },
  "content": {},
  "authz_ref": "cx:grant:01JS0GR000000000000000000",
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:alice.example.com#device-laptop",
      "payload_hash": "sha256:...",
      "jws": "base64url..."
    }
  ]
}
```

## 6. 为什么需要 `deps + hlc + actor_seq`

单一时间戳不足以支撑协作收敛。

Contrix v1 要求：

- `deps` 表示直接因果依赖
- `hlc` 表示近实时逻辑时间
- `actor_seq` 表示 actor 本地单调序列

实现 MUST NOT 把 Sync Service 到达顺序、数据库自增 ID 或 HTTP 接收顺序当作协议顺序。

## 7. 标准 Operation Kind

所有 `kind` 都是可见事件类型。实现必须拒绝未注册、未带 `cx.` 前缀或未在服务端能力清单中声明的事件类型。

### 7.1 Space / Schema / Policy / Discovery

- `cx.space.create`
- `cx.space.update`
- `cx.space.archive`
- `cx.space.freeze`
- `cx.space.destroy`
- `cx.space.discovery`
- `cx.organization.discovery`
- `cx.schema.define`
- `cx.schema.update`
- `cx.policy.set`

### 7.2 Room / Message

- `cx.room.create`
- `cx.room.update`
- `cx.room.archive`
- `cx.room.member`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.redact`
- `cx.reaction.add`
- `cx.reaction.remove`

### 7.3 Board / List / Card

- `cx.board.create`
- `cx.board.update`
- `cx.board.archive`
- `cx.list.create`
- `cx.list.update`
- `cx.list.archive`
- `cx.list.reorder`
- `cx.card.create`
- `cx.card.update`
- `cx.card.archive`
- `cx.card.restore`
- `cx.card.move`
- `cx.card.reorder`
- `cx.card.link_room`
- `cx.card.unlink_room`
- `cx.card.set_primary_room`

### 7.4 Morph / Relation / View

- `cx.morph.create`
- `cx.morph.update`
- `cx.morph.delete`
- `cx.morph.restore`
- `cx.relation.create`
- `cx.relation.update`
- `cx.relation.delete`
- `cx.view.create`
- `cx.view.update`

`cx.view.*` 只修改 View definition，例如 query、projection kind、renderer、visible fields、layout、grouping 或 shared saved view 配置。它不得用于保存 Card 所属 List、Card rank、List rank、Room membership、Message timeline、Relation active state 或对象字段的唯一真相。

Card 与 Room 的关联只使用 Card 视角事件：`cx.card.link_room`、`cx.card.unlink_room` 和 `cx.card.set_primary_room`。`cx.room.link_card` / `cx.room.unlink_card` 不是 v1 标准事件，接收方 MUST 拒绝它们，避免同一语义出现双写路径。

### 7.5 Run / Memory / Extensions

- `cx.run.create`
- `cx.run.update`
- `cx.run.complete`
- `cx.run.fail`
- `cx.memory.create`
- `cx.memory.update`
- `cx.memory.confirm`
- `cx.memory.reject`
- `cx.memory.invalidate`
- `cx.memory.supersede`

这些事件在 v1 Core 中作用于 `morph_type=run` / `morph_type=memory` 的 Morph。若未来 profile 将 Run / Memory 提升为标准对象，必须声明新的 schema/profile 版本和迁移规则。

### 7.6 Membership / Invite / Capability

- `cx.membership.join`
- `cx.membership.leave`
- `cx.membership.kick`
- `cx.membership.ban`
- `cx.membership.unban`
- `cx.membership.knock`
- `cx.invite.create`
- `cx.invite.cancel`
- `cx.invite.accept`
- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.7 Profile / Device / Space Key

- `cx.profile.update`
- `cx.profile.space_override`
- `cx.device.authorized`
- `cx.device.revoked`
- `cx.device.list_update`
- `cx.space_key.share`
- `cx.space_key.withheld`

## 8. 操作体原则

非 create 类操作 SHOULD 只携带 delta，而不是完整对象快照。

例如：

- `cx.card.update` 只带字段变更
- `cx.card.move` 只带目标 List 和新 rank
- `cx.message.revise` 只带新正文
- `cx.message.redact` 只带目标消息与原因
- `cx.morph.update` 只带 Morph 字段 patch
- `cx.view.update` 只带投影定义 patch；通过 View 触发的对象变更仍使用对象 operation

## 9. Board / Card 有序操作

### 9.1 `cx.card.move`

`cx.card.move` 用于跨 List 移动 Card。它移动的是 Card 在一个 Board 内的主位置，而不是修改 Room 或 Card linked Room。

```json
{
  "kind": "cx.card.move",
  "target_ref": "cx:card:01js0tk000000000000000000",
  "content": {
    "board_id": "cx:board:01js0bd000000000000000000",
    "card_id": "cx:card:01js0tk000000000000000000",
    "from_list_id": "cx:list:01todo",
    "to_list_id": "cx:list:01review",
    "rank": "mV",
    "expected_position": {
      "list_id": "cx:list:01todo",
      "rank": "h0",
      "relation_id": "cx:relation:01old"
    }
  }
}
```

Reducer 语义：

1. 验证 actor 对 `board_id`、`card_id`、`from_list_id` 和 `to_list_id` 的 move/reorder 权限。
2. 验证 `to_list_id` 在 `board_id` 下是 active List。
3. 在 reduced state 中关闭同一 `(board_id, card_id)` 下其他 active position edge。
4. 创建或更新 `to_list_id --contains--> card_id` 的 active Relation，并把 rank 设置为 `rank`。
5. 对相同 Operation 保持幂等。

`cx.card.move` 不得把 `board_id`、`list_id` 或 `rank` 写入 Card canonical object 作为唯一真相源。Index / View projection MAY 返回这些派生字段，但必须能追溯到 active position edge 和 reducer frontier。

### 9.2 `cx.card.reorder`

`cx.card.reorder` 只改变同一 List 内的 rank，不改变 List membership。

```json
{
  "kind": "cx.card.reorder",
  "target_ref": "cx:card:01js0tk000000000000000000",
  "content": {
    "board_id": "cx:board:01js0bd000000000000000000",
    "list_id": "cx:list:01review",
    "card_id": "cx:card:01js0tk000000000000000000",
    "rank": "mV",
    "expected_position": {
      "rank": "h0",
      "relation_id": "cx:relation:01pos"
    }
  }
}
```

`cx.card.reorder` 不得改变 List。若当前 List 与 `expected_position` 不一致，除非 policy 明确允许 non-CAS reorder，否则实现 SHOULD 返回 `cas_conflict` 或标记为 stale reorder。

### 9.3 `cx.list.reorder`

`cx.list.reorder` 改变 List 在 Board 内的顺序。它不得移动 Card。

### 9.4 `cx.card.link_room`

`cx.card.link_room` 为 Card 关联一个 Room。

```json
{
  "kind": "cx.card.link_room",
  "target_ref": "cx:card:01js0tk000000000000000000",
  "content": {
    "card_id": "cx:card:01js0tk000000000000000000",
    "room_id": "cx:room:01js0rm000000000000000000",
    "purpose": "implementation_discussion",
    "primary": false
  }
}
```

规则：

- link 不传递权限。
- link 不改变 Room membership。
- link 不改变 Card visibility。
- 设置 `primary=true` 时，Reducer MUST 保证同一 Card 最多一个 active `primary_room`。

## 10. 验证流程

任何接收 operation 的 repo、sync service 或 index，至少应校验：

1. 签名有效。
2. actor DID 可解析。
3. key 在操作时点有效。
4. `space_id` 与 target object 所属 Space 一致。
5. capability 在操作时点有效。
6. causal 依赖不违反基本约束。
7. 对 Room / Card / Board / Morph 执行对象类型 schema validation。

## 11. Snapshot

Snapshot 是加速层，不是真相源。

Snapshot manifest MUST 包含：

- `snapshot_ref`
- `space_id`
- `schema_profile_refs`
- `chunk_digests`
- `state_hash`
- `frontier`
- `signature`

客户端在采用 Snapshot 前 MUST 验证：

1. `signature` 是标准 detached proof，覆盖 `snapshot_ref`、`space_id`、`state_hash`、`frontier`、`chunk_digests`、`reducer_profile` 和 `schema_profile_refs` 的 canonical manifest hash。
2. `signature.verification_method` 对应的 DID 必须是 Space owner、Space policy 授权的 snapshot issuer、可信 Index service DID 或 witness quorum 成员。
3. 每个 chunk 的实际 SHA-256 与 manifest 中声明的 digest 一致。
4. 若任何校验失败，客户端 MUST 丢弃快照并回退到 Repo 进行原始历史回放。

## 12. 同步面

### 12.1 Repo Sync

用于 actor 历史恢复与审计重放。

### 12.2 Space Sync

用于 Space 级当前态与增量同步。

### 12.3 Room Sync

用于 Room 消息时间线、Room membership 和通知。

### 12.4 Board Sync

用于 Board/List/Card 当前态、Card position 和拖拽增量。

### 12.5 Query Surface

用于 view、搜索、memory 检索与 context timeline 查询。

### 12.6 Authz / Invite Surface

用于：

- 拉取 invite
- 拉取有效 grant 集
- 判断某个 operation 在当前 frontier 下是否可写

## 13. 首次加入 Space

推荐流程：

1. 获取 Space metadata。
2. 获取与自己相关的 invite / grant 视图。
3. 拉取最近 snapshot manifest。
4. 下载 snapshot chunk。
5. 从 snapshot frontier 之后拉取增量 operation。
6. 本地执行 reducer。
7. 进入 cursor 增量订阅。

若客户端没有现成 DID，但只有 handle，则在步骤 1 之前 MUST 先完成 handle -> DID 解析与双向校验。

## 14. 选择性同步

选择性同步至少支持以下过滤维度：

- space
- room
- board
- list
- card
- object type
- morph type
- relation kind
- watched refs
- changed since cursor

## 15. 幂等、去重与重放

在去中心化同步里，重复提交与重复投递是常态。

因此：

- `commit_id` 与 `operation_id` MUST 全局稳定。
- 同一个 `commit_id` / `operation_id` 的完全相同内容 MAY 被重复接收。
- 若同一个 ID 对应不同内容，节点 MUST 拒绝并记为冲突。
- sync service 与 index SHOULD 以 `operation_id` 去重，而不是按到达次数计数。

## 16. 冲突与收敛

Contrix 初版不引入全网共识链。

它要求：

- 对同一 Space
- 在同一有效 operation 集下
- 所有正确实现的 reducer

最终收敛到相同当前态。

并发操作 tie-breaker 依次为：

1. 授权权重。
2. HLC。
3. Actor ID 字典序。
4. Operation hash 字典序。

实现不得使用本地接收顺序、数据库自增 ID 或 Sync Service 顺序作为 tie-breaker。

## 17. 字段级 merge 与对象级收敛

### 17.1 标量字段

例如：

- `card.title`
- `card.fields.status`
- `room.summary`
- `morph.fields.severity`

建议使用基于 deterministic operation order 的 LWW。

### 17.2 集合字段

例如：

- labels
- watchers
- linked refs

建议使用 OR-Set。

### 17.3 Board position

同一张 Card 在同一 Board 内的唯一主位置 key 是 `(board_id, card_id)`。同一 key 下出现多个 active position edge 时，Reducer MUST 按 deterministic operation order 选择唯一 winner，并在 `conflict_records` 中记录 losers。

### 17.4 Graph cycle

对象在依赖图、引用图或容器图中产生循环时，Reducer MUST 按 deterministic operation order 从高到低尝试保留候选；任何会形成非法循环的 candidate MUST 被标记为 `rejected_cycle`。

## 18. Message

- `cx.message.create` 是 append-only。
- `cx.message.revise` 形成 revision chain。
- 默认视图显示最新可见 revision。
- `cx.message.redact` 保留最小审计字段。

## 19. 授权时序收敛

授权不能只看墙上时钟，否则 revoke、迟到 operation、离线写入都会失真。

Contrix v1 要求：

- grant / delegate / revoke 本身也是 operation。
- 某个业务 operation 是否有效，由同一 reducer 顺序下的有效授权集合决定。
- 若某个写入在 reducer 顺序上已经晚于相关 revoke，则 MUST 视为无效。
- 若顺序无法确定，实现 SHOULD fail closed。

## 20. 可见性、密文负载与 E2EE 索引

ACL 不等于密文保护，Sync Service 也不应被迫看懂所有正文。

字段可见性分级：

- 可路由元数据：`space_id`、`target_ref`、`type`、`causal`。
- 明文业务元数据：轻量状态、rank、due date 等；若足以暴露敏感内容，相关 Index 必须列入 `plaintext_visible_services`。
- 不透明加密负载：message body、附件内容、敏感 memory 细节等。

## 21. 本地存储建议

客户端 SHOULD 维护三层本地数据：

- raw commits / raw operations
- reduced snapshots
- materialized indexes

## 22. 设计决定

Contrix v1 固定：

- repo commit 是 actor 发布单元。
- operation 是共享状态归约单元。
- Room / Message、Board / List / Card、Morph 共享同一同步协议。
- Card 和 Room 通过 relation 关联，权限不继承。
- invite / grant / snapshot 组成 Space bootstrap 主流程。
- commit/operation 重试必须幂等。
- 授权有效性由同一 reducer 顺序收敛。
- 密文负载可以被不解密的 sync service / index 转发。
- 撤回采用 redaction/tombstone 语义。
- hard erasure 只能删除本地 payload / blob / 派生内容，并保留 verification stub；不得重写 event hash 或伪装事件从未存在。
- 冲突通过固定 reducer 规则收敛。

## 23. 规范性引用

- Cursor 编码与 opaque 语义见 `encoding.md`、`data-structures.md` 和 `encoding-conformance-vectors.md`。
- HLC 文本格式固定为 `<unix_ms_hex_12>-<logical_hex_4>-<node_id_hash_8>`，排序向量见 `encoding-conformance-vectors.md`。
- Snapshot manifest、chunk digest、`state_hash` 和签名规则见 `snapshot-schema.md`。
- Room / Message 语义见 `../models/conversation-model.md`。
- Board / List / Card / Morph 语义见 `../models/object-model-standard.md` 和 `../models/views.md`。
