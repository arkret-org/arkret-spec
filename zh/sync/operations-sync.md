# Operations And Sync

## 1. 目标

Contrix 是面向协作对象的分布式发布、传播、查询与收敛协议。

同步层必须同时支持：

- actor 侧可验证发布
- append-only 审计日志
- 当前态快速恢复
- 看板模式同步
- 聊天/话题模式同步
- 树/图谱/依赖图同步
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

Repo 的实现 MAY 使用数据库、对象存储、append-only 文件日志、Merkle log、content-addressed block store 或其他存储引擎。协议不要求某种数据库模型；协议要求的是可验证的 commit log、operation/event store、head / cursor 与 proof material。

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
- 将非加密私有正文、附件预览、全文索引、通知摘要、embedding 或可逆派生摘要写入未列入 `plaintext_visible_services` 的派生服务。

### 2.3 Index

Index 是物化与查询层。

### 2.4 Blob Store

Blob Store 负责附件与大对象内容。

## 3. Repo-first 发布模型

Contrix 采用 repo-first 模型：

1. actor 先写自己的 repo
2. repo 发布 commit
3. Principal Server / Sync Service 同步 Space 相关授权 operation
4. index 归约为当前态

这套模型同时适用于：

- board/task 更新
- topic/message 流
- run/memory 沉淀

## 4. Repo Commit

Contrix v1 repo 以 commit 为发布单元。

```json
{
  "commit_id": "cx:commit:01JS0CMT000000000000000000",
  "repo_did": "did:web:alice.example.com",
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

每个 operation MUST 具备统一 envelope。

Operation Envelope 是 sync / federation 写路径的签名承载信封。它不同于 `data-structures.md` 中的 canonical Operation object：Envelope 的 `type` 是事件 kind，且通过 `causal`、`target_ref`、`authz_ref` 和 `signature` 绑定写入语义；canonical Operation object 的 `type` 固定为 `"operation"`，并使用 `operation_type` 描述 create/update/delete 等对象级动作。

```json
{
  "operation_id": "cx:operation:01JS0OP000000000000000000",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor": "did:web:alice.example.com",
  "type": "cx.entity.update",
  "target_ref": "cx:entity:01JS0EN000000000000000000",
  "causal": {
    "deps": [
      "cx:operation:01JS0OO000000000000000000"
    ],
    "hlc": "01970e589d21-0007-a13f9c2e",
    "actor_seq": 42
  },
  "body": {},
  "authz_ref": "cx:grant:01JS0GR000000000000000000",
  "signature": {
    "key_id": "did:web:alice.example.com#device-laptop",
    "alg": "ES256",
    "sig": "base64url..."
  }
}
```

## 6. 为什么需要 `deps + hlc + actor_seq`

单一时间戳不足以支撑协作收敛。

Contrix v1 要求：

- `deps` 表示直接因果依赖
- `hlc` 表示近实时逻辑时间
- `actor_seq` 表示 actor 本地单调序列

事件顺序分为三层：

| 顺序 | 用途 | 规则 |
| --- | --- | --- |
| Causal order | 授权、缺口检测、backfill | `deps` / `prev_refs` / `auth_refs` |
| Reducer order | 状态收敛、冲突解决 | space version 指定的 deterministic reducer |
| Timeline order | 客户端展示、分页恢复 | `causal_depth + hlc + actor_id + actor_seq + event_id` |

实现 MUST NOT 把 Sync Service 到达顺序、数据库自增 ID 或 HTTP 接收顺序当作协议顺序。

## 7. 操作类型

所有 `type` 都是可见事件类型（`event.type`）；Operation 本身是 `event` 的承载信封。
因此以下规则必须成立：

- 处理层不再引入独立的 `operation_type` 命名空间；`operation.type == event.type`。
- 不应出现既无 schema 注册也未在服务端能力清单中注册的自定义 `type`。
- 旧实现若发送未带 `cx.` 前缀的事件，必须经过兼容适配后映射为注册表 `cx.*` 名称。

### 7.1 Space / Schema / Policy

- `cx.space.create`
- `cx.space.update`
- `cx.space.archive` (归档：Space 进入只读状态，所有写入 MUST 被拒绝，历史数据可查)
- `cx.space.freeze` (临时冻结，由具备 `space.admin` 权限的 Actor 触发，可解冻)
- `cx.space.destroy` (标记待回收，Sync Service 和 Index 按 retention policy 倒计时清理)
- `cx.schema.define`
- `cx.schema.update`
- `cx.policy.set`

### 7.2 Entity / Relation / View

- `cx.entity.create`
- `cx.entity.update`
- `cx.entity.delete`
- `cx.entity.restore`
- `cx.relation.create`
- `cx.relation.update`
- `cx.relation.delete`
- `cx.view.create`
- `cx.view.update`

### 7.3 标准语义操作

以下操作是语义糖，MUST 能还原为 `entity.*` 或 `relation.*`：

- `cx.task.create`
- `cx.task.update`
- `cx.task.move`
- `cx.task.reorder`
- `cx.comment.create`
- `cx.comment.update`
- `cx.comment.redact`
- `cx.attachment.add`
- `cx.attachment.remove`

### 7.4 Channel / Topic / Message

- `cx.channel.create`
- `cx.channel.update`
- `cx.channel.archive`
- `cx.topic.create`
- `cx.topic.update`
- `cx.topic.close`
- `cx.topic.reopen`
- `cx.message.create`
- `cx.message.revise`
- `cx.message.redact`
- `cx.reaction.add`
- `cx.reaction.remove`

### 7.5 Run / Memory

- `cx.run.create`
- `cx.run.update`
- `cx.run.complete`
- `cx.run.fail`
- `cx.memory.create`
- `cx.memory.update`
- `cx.memory.confirm`
- `cx.memory.invalidate`
- `cx.memory.supersede`

### 7.6 Membership

- `cx.membership.join` (加入 Space)
- `cx.membership.leave` (主动离开)
- `cx.membership.kick` (被管理员移除)
- `cx.membership.ban` (封禁，禁止再次加入)
- `cx.membership.unban` (解封)
- `cx.membership.knock` (请求加入，等待审批)

### 7.7 Invite / Read State

- `cx.invite.create`
- `cx.invite.cancel`
- `cx.invite.accept`
- `cx.read.marker`

### 7.8 Capability

- `cx.capability.grant`
- `cx.capability.delegate`
- `cx.capability.revoke`

### 7.9 私有与临时状态

以下状态不建议作为 durable shared operation：

- typing
- live presence
- 本地草稿

它们 MAY 通过 sync ephemeral channel 或 actor-private state 同步。

## 8. 操作体原则

非 create 类操作 SHOULD 只携带 delta，而不是完整对象快照。

例如：

- `cx.entity.update` 只带字段变更
- `cx.relation.move`（规范化 `cx.entity` reorder）只带目标容器和新 rank
- `cx.message.revise` 只带新正文
- `cx.message.redact` 只带目标消息与原因

## 9. 验证流程

任何接收 operation 的 repo、sync service 或 index，至少应校验：

1. 签名有效
2. actor DID 可解析
3. key 在操作时点有效
4. `space_id` 与 target Space 一致
5. capability 在操作时点有效
6. causal 依赖不违反基本约束

## 10. Snapshot

Snapshot 是加速层，不是真相源。

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "snapshot_id": "cx:snap:01JS0SN000000000000000000",
  "covers_frontier": [
    "cx:operation:01JS0OP000000000000000000",
    "cx:operation:01JS0OQ000000000000000000"
  ],
  "generated_at": "2026-04-22T08:40:00Z",
  "generator": "did:web:index.example.com",
  "reducer_version": "0.1.0",
  "chunks": [
    {
      "kind": "items",
      "url": "https://index.example.com/cx/snapshots/01/items.json"
    },
    {
      "kind": "messages",
      "url": "https://index.example.com/cx/snapshots/01/messages.json"
    }
  ]
}
```

Snapshot manifest MUST 包含以下信任链字段：

- `schema_profile_refs`
- `chunk_digests`（每个 chunk 的 SHA-256 摘要）
- `state_hash`（快照覆盖范围内全量状态的 Merkle Root）
- `signed_by`（签名者 DID，应为 Space Owner 或可信 Index 节点）
- `generator_signature`（对 `state_hash` + `chunk_digests` 的密码学签名）

客户端在采用 Snapshot 前 MUST 验证：

1. `generator_signature` 的签名有效性（签名者公钥通过 DID Document 解析）
2. 每个 chunk 的实际 SHA-256 与 `chunk_digests` 中声明的值一致
3. 若任何校验失败，客户端 MUST 丢弃快照并回退到 Repo 进行原始历史回放

## 11. 同步面

### 11.1 Repo Sync

用于 actor 历史恢复与审计重放。

### 11.2 Space Sync

用于 Space 级当前态与增量同步。

### 11.3 Sync Stream Subscription

用于实时事件传播。

### 11.4 Query Surface

用于 view、搜索、memory 检索与 thread 查询。

### 11.5 Authz / Invite Surface

用于：

- 拉取 invite
- 拉取有效 grant 集
- 判断某个 operation 在当前 frontier 下是否可写

## 12. View 同步 Profile

### 12.1 Board 模式

默认同步：

- board/collection/task Entity 当前态
- 当前打开 task 的 comment 摘要
- 当前打开 task 的默认 topic 摘要

### 12.2 Chat 模式

默认同步：

- channel metadata
- open topics
- 最近 N 条 messages
- live message/reaction/redaction 增量

### 12.3 Topic 模式

默认同步：

- topic metadata
- anchor object
- 最近 N 条 messages
- 反向 backfill cursor

### 12.4 Graph / Tree 模式

默认同步：

- root Entity 当前态
- 查询范围内的 Entity 当前态
- 相关 Relation 集合
- 最近影响这些 Entity/Relation 的 Event 摘要

## 13. 首次加入 Space

推荐流程：

1. 获取 Space metadata
2. 获取与自己相关的 invite / grant 视图
3. 拉取最近 snapshot manifest
4. 下载 snapshot chunk
5. 从 snapshot frontier 之后拉取增量 operation
6. 本地执行 reducer
7. 进入 cursor 增量订阅

若客户端没有现成 DID，但只有 handle，则在步骤 1 之前 MUST 先完成 handle -> DID 解析与双向校验。

## 14. 选择性同步

选择性同步是协议关键能力。

初版至少支持以下过滤维度：

- space
- view
- entity_type
- relation_kind
- target refs
- watched entities
- watched runs
- changed since cursor

## 15. 幂等、去重与重放

在去中心化同步里，重复提交与重复投递是常态，不是异常。

因此：

- `commit_id` 与 `operation_id` MUST 全局稳定
- 同一个 `commit_id` / `operation_id` 的完全相同内容 MAY 被重复接收
- 若同一个 ID 对应不同内容，节点 MUST 拒绝并记为冲突
- sync service 与 index SHOULD 以 `operation_id` 去重，而不是按到达次数计数

这能避免：

- 客户端重试导致重复写入
- 多 Principal Server 回流造成重复 fanout
- index 因重复投递而产生错误统计

## 16. 冲突与收敛

### 16.1 不追求全局共识

Contrix 初版不引入全网共识链。

它要求：

- 对同一 space
- 在同一有效 operation 集下
- 所有正确实现的 reducer

最终收敛到相同当前态。

### 16.2 脑裂与 DAG 分支合并

在去中心化网络中，离线编辑或网络分区（脑裂）是常态。当网络恢复时，不同的分支需要进行合并。Contrix 采用基于有向无环图 (DAG) 的拓扑排序结合混合逻辑时钟 (HLC) 来实现绝对确定性的状态收敛。

```mermaid
graph TD
    A[Operation A: HLC=10, Title='Doc'] --> B[Operation B: HLC=11, Title='Doc v1']
    A --> C[Operation C: HLC=12, Title='Doc (Draft)']
    B --> D[Operation D: Merge B & C]
    C --> D
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style B fill:#bbf,stroke:#333,stroke-width:2px
    style C fill:#bfb,stroke:#333,stroke-width:2px
    style D fill:#fbb,stroke:#333,stroke-width:4px
```

**合并过程说明：**
1. Alice 离线提交了 Operation B。Bob 在线提交了 Operation C。
2. 由于两人都没有看到对方的 Operation，B 和 C 的 `prev_operations` 都指向 A。
3. 网络恢复后，Bob 的客户端拉取到 B，发现此时 DAG 存在两个 Head (B 和 C)。
4. Bob 的客户端自动生成一条 Dummy Operation D（或者在下一次业务提交时包含多个 `prev_operations`），将 B 和 C 设为前驱，完成拓扑合并。

### 16.3 确定性状态收敛与 Tie-breaking (平局破除)

借鉴成熟的分布式状态解析算法（如 Matrix State Resolution v2 的 Kahn's 拓扑排序），当网络中出现并发的分叉操作（无明确的 `prev_ids` 覆盖关系）时，所有节点 MUST 采用绝对确定的排序来打破平局 (Tie-breaking)，保障全网视图强一致。

排序优先级算法 (Reverse Topological Authorization Ordering)：
比较两个并发操作 $O_A$ 和 $O_B$ 时，判定 $O_A < O_B$ ($O_B$ 胜出，成为最终态) 的依据严格依序如下：
1. **授权权重 (Auth Weight)**：检查生成该操作时，`actor` 持有的 capability / role / creator-admin 权重。权重大的操作胜出。
2. **混合逻辑时钟 (HLC)**：若权限相等，比较 `hlc` 时间戳。时间戳大的胜出。
3. **Actor ID 字典序**：若时间戳依然完全相等，比较发出的 `actor_id` 的纯字符串字典序。
4. **Operation Hash 字典序**：最后兜底，比较操作信封哈希 `operation_id` 的字典序。

这确保了整个图的拓扑排序具备绝对的唯一性。

## 17. 字段级 merge 与对象级收敛

### 17.1 标量字段

例如：

- `title`
- `body`
- `status`
- `priority`

建议：

- **LWW by Deterministic Order**：基于 16.3 节定义的 Tie-breaking 排序算法实现 Last-Write-Wins。无论这些修改在网络中到达节点的顺序如何，经过排序后最终生效的永远是“最大”的那个值。

### 17.2 集合字段

例如：

- `labels`
- `assignees`
- `watchers`

建议：

- OR-Set

### 17.3 树图结构与循环依赖处理

对象在 `collection` 或 `board` 间的转移通过 Relation 的增删或 `move` 操作实现。在离线并发操作中，极易产生循环包含 (Cycle) 或孤儿数据 (Orphaned items)。

建议收敛规则：
- **防循环 (Cycle Prevention)**：当发生并行移动导致图结构出现循环时（如 A 包含 B，同时 B 包含 A），Reducer 将基于 `hlc + actor_seq` 排序，较晚发生的移动操作将被判定无效并被退回，或者强制平铺到根容器。
- **防孤儿 (Orphan Resolution)**：当一个对象被移入的父节点被并行删除时，该对象将自动回落到 Space 的默认 Inbox 容器或其原始容器中。

### 17.4 排序字段与重平衡

例如：

- `rank`
- `container_id`

应通过 move/reorder 语义处理。`rank` 推荐使用 Fractional Indexing string。

**重平衡 (Rebalance) 与并发防乱序机制**：
当高频拖拽导致 Fractional Indexing 字符串长度膨胀或精度耗尽时，具备 `manage_board` 或对应管理权限的 Actor MAY 提交一条特殊的 `cx.relation.rebalance` 操作。该操作将在其所属分支上截断现有的长尾 rank，为容器内所有对象重新分配短且等距的 rank 字符串，以消除碎片和性能隐患。
为防止多端并发触发重平衡导致列表排序被彻底损毁（并发乱序风暴），`rebalance` 操作 MUST 携带一个 **`expected_state_hash` (CAS 并发锁)**。节点在处理 `rebalance` 时，如果当前列表状态哈希与预期不符，MUST 拒绝该次重平衡。客户端若遭遇 CAS 失败，应自动使用指数退避 (Exponential Backoff) 策略拉取最新状态后重试。

### 17.5 Message

- `cx.message.create` 是 append-only
- `cx.message.revise` 形成 revision chain
- 默认视图显示最新可见 revision

### 17.6 Reaction

reaction 以 `(message_id, actor, reaction_key)` 为 OR-Set key 收敛。

## 18. 排序模型

拖拽排序建议采用：

- `container_id`
- `rank`

其中 `rank` 建议采用 fractional indexing string。

消息时间线显示顺序建议采用：

- `hlc + actor + actor_seq + operation_id`

正式 timeline order 见 `client-sync.md`。当存在明确因果依赖时，因果前序 MUST 优先于纯时间排序。

## 18.1 大规模同步加速

大规模 Space 的同步性能不依赖单一机制，而是多层组合：

- Snapshot：用签名 snapshot 恢复当前态，避免从创世事件重放。
- Incremental cursor：通过 opaque cursor 只拉取增量。
- Selective sync：只同步当前视图、活跃 Space、关注对象和 mention。
- Lazy member loading：只同步渲染和授权需要的 member state。
- Backfill ranges：历史按区间分页拉取。
- Blob lazy loading：附件与大对象按需拉取。
- Local reducer cache：客户端缓存 reduced state 和 materialized view。
- Causal barrier：查询可等待指定 sync token，保证读己之所写。

这些加速层都不得成为真相源。客户端在采用 snapshot、index projection 或 sync backfill 前，仍需能追溯到 signed event / operation、hash、auth refs 和 reducer profile。

## 19. Tombstone、Redaction 与恢复

### 19.1 对象删除

对象删除 SHOULD 采用 tombstone。

### 19.2 消息撤回

消息撤回应采用 redaction，而不是物理消失。

语义要求：

- 默认视图显示“已撤回”
- 不应继续在普通视图泄露正文
- 不承诺全网物理擦除

### 19.3 先收到 redaction，后收到原消息

接收方 SHOULD 保留 dangling redaction，并在目标消息到达后应用。

## 20. 授权时序收敛

授权不能只看墙上时钟，否则 revoke、迟到 operation、离线写入都会失真。

Contrix v1 要求：

- grant / delegate / revoke 本身也是 operation
- 某个业务 operation 是否有效，由同一 reducer 顺序下的有效授权集合决定
- 若某个写入在 reducer 顺序上已经晚于相关 revoke，则 MUST 视为无效
- 若顺序无法确定，实现 SHOULD fail closed

这意味着授权语义也必须服从同一套因果与排序规则，而不是旁路逻辑。

## 21. 可见性、密文负载与 E2EE 索引

ACL 不等于密文保护，Sync Service 也不应被迫看懂所有正文。为解决端到端加密与视图检索的矛盾，协议采用“明暗双轨策略”。

### 21.1 字段可见性分级

- **可路由元数据 (Routing Metadata)**：`space_id`、`target_ref`、`type`、`causal`。此类数据必须明文，用于 Sync Service 路由与因果排序。
- **明文业务元数据 (Cleartext Indexable Metadata)**：`status`、`labels`、`priority`、`due_at` 等轻量级业务流转字段。此类字段 MAY 保持明文，供被授权且必要的 Index 层查询与生成无密钥依赖的统计视图；若字段足以暴露私密内容或组织敏感状态，则该 Index MUST 被列入 `plaintext_visible_services`，否则应改用密文、不可逆 hash 或 stripped preview。
- **不透明加密负载 (Opaque Encrypted Payload)**：`content`、`body`、附件内容、敏感 `memory` 细节。此类字段 MUST 被加密。实现 MAY 使用 `policy.encryption_profile` 指定的 envelope 格式加密。即使 sync service 或 index 无法解密，也 SHOULD 能转发、去重与保留因果结构。

### 21.2 端到端加密与合规审计

针对 `channel` 和 `board` 等涉及多参与方的加密需求，本协议官方推荐使用基于 IETF RFC 9420 的 MLS (Message Layer Security) 协议，以替代在大型群组中性能较差的 Double Ratchet，从而高效处理前向安全 (Forward Secrecy) 与后向安全 (Post-Compromise Security)。

同时，为了在满足组织合规性要求时不引入“暗网式监控后门”，本协议支持原生的**“可审查的端到端加密 (Auditable E2EE)”** 与透明留痕机制。

关于 MLS 的 KeyPackage 发布、加密信封格式以及强制合规审计留痕 (`cx.audit.accessed`) 的深入技术标准与交互流程，请参阅独立的协议拓展文件：
[加密与可审查性规范 (Encryption and Auditability)](../crypto-media/encryption-and-audit.md)。

### 21.3 密文上的检索索引

由于去中心化网络中不受信节点无法解密数据，如需实现全局密文检索功能，客户端 SHOULD 选择以下方案之一：
1. 依赖本地存储解密后维护的客户端全文索引（倒排索引）。
2. 在受控网络内，指定一个支持可信执行环境 (TEE) 或受组织高度信任的 Index 节点代理密文检索功能。

## 22. Blob 同步

Blob 不应强制与元数据同流同步。

建议：

- 元数据先同步
- 内容按需加载
- 通过 hash 校验完整性

## 23. 本地存储建议

客户端 SHOULD 维护三层本地数据：

- raw commits / raw operations
- reduced snapshots
- materialized indexes

## 24. 设计决定

Contrix v1 固定：

- repo commit 是 actor 发布单元
- operation 是共享状态归约单元
- board/chat/topic 共享同一同步协议
- invite / grant / snapshot 组成 Space bootstrap 主流程
- commit/operation 重试必须幂等
- 授权有效性由同一 reducer 顺序收敛
- 密文负载可以被不解密的 sync service / index 转发
- 撤回采用 redaction/tombstone 语义
- 冲突通过固定 reducer 规则收敛

## 25. 规范性引用

以下线级事项由 v1 相关文档固定，本文不再保留开放项：

- Cursor 编码与 opaque 语义见 `encoding.md`、`data-structures.md` 和 `encoding-conformance-vectors.md`。
- HLC 文本格式固定为 `<unix_ms_hex>-<logical_hex>-<node_id_hash>`，排序向量见 `encoding-conformance-vectors.md`。
- Snapshot manifest、chunk digest、`state_hash` 和签名规则见 `snapshot-schema.md`。
- Encrypted payload envelope schema 见 `data-structures.md`、`snapshot-schema.md`、`encryption-and-audit.md` 和 `encoding-conformance-vectors.md`。
- Read marker 的私有状态、同步面和 notification 派生规则见 `read-notification-schema.md`、`read-receipts.md` 和 `client-preferences.md`。
- Sync Service / Index 线级接口见 `service-surface.md`、`service-http-binding.md` 和 `query-schema.md`；transport 等价性见 `transport-bindings.md`。

实现若缺少上述任一规范性依赖，MUST 在 feature discovery 中声明不支持对应 profile，不能声称完整支持 Contrix v1 同步。

