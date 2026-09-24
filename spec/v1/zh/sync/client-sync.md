---
title: Client Sync
status: candidate
normative: true
stability: v1
updated: 2026-09-20
see_also:
  - authority-commit-log.md
  - current-results.md
  - service-http-binding.md
  - federation.md
  - ../governance/history-visibility.md
---

## 0. 规范语言

本文关键字按 [normative-language.md](../conformance/normative-language.md) 解释。Wire shape 以 schema、OpenAPI 和 canonical operation registry 为准。

## 1. 目标

Client Sync 是 own Account Station 向客户端提供的受信账号聚合流。它传送：

- Realm/Circle/Sidecar 各自独立 authority stream 的 committed delta；
- typed current results 与签名 snapshot；
- Account-private 数据、to-device、device list 和 notification projection；
- MLS public transition 提示和 recipient-scoped Welcome delivery。

聚合流不是新的 Realm 总链。客户端不得把不同 scope 的 position 排成全局序，也不从 timeline 重放治理。

旧 `self/seals/frontier` 与 `self/events/frontier` 两条路径不属于 v1 读取面。客户端 MUST NOT
把 SealBasis、actor-only Event aggregate frontier 或跨 Realm 聚合位置当作 RealmCommit stream head、
readable floor、authoring authority 或同步完成证据。获准 stream 的发现使用
`ak.self.realm.read.streams.v1`，snapshot manifest head 使用
`ak.self.realm_state_snapshot.read.manifest_head.v1`；committed Event 读取按独立 stream 使用
`ak.self.committed_event.read.scan.v1`，并分别遵守该 stream 的 visibility 与 readable floor。

## 2. Endpoint

`ak.self.account.stream.subscribe.v1` 是账号聚合主入口。`ak.self.committed_event.read.scan.v1` 与 `ak.self.committed_event.stream.subscribe.v1` 用于读取一个或多个**明确获准的独立 stream**。字段、分页参数（subscribe 用 cursor，scan 用 `stream_position`）与 frame schema 见 [service-http-binding.md](./service-http-binding.md)。

### 2.1 多账号上下文 UX 指引（SHOULD）

客户端必须以完整 AccountId/ActorId 区分账号和成员身份。相同 principal 在不同 Station 的账号不能合并；UI 应明确显示当前提交账号和当前 own Station。

### 2.2 连接管理与重连

断线重连复用最后耐久保存的 account cursor。cursor 失效时重做 baseline；某条 Realm stream tail 缺失时只恢复该获准 stream，不重置其它 stream 或 to-device ACK。

### 2.3 按需列表、详情与分段 baseline（normative）

Initial sync 可以分段返回，但只有在某 section 的 baseline 完成标志到达后，客户端才能把该 section 作为完整集合替换。增量到达早于 baseline 完成时必须按 revision/stream position合并，不能被较旧 baseline 覆盖。

账号全局 baseline 的封闭 channel 集合是
`account_data_events / station_cas / device_lists / notifications / agent_draft_pending_intents` 五项。每个
`account_baseline_segment` MUST 携同一个冻结窗口的 `snapshot_cursor`。只有某 channel 的末页已经交付，
服务端才能把它列入
`completed_channels`；中间页缺少某 item 不是 removal，客户端不得据此清除本地行。

每个 NDJSON canonical frame 仍至多 8 MiB，每轮至多 16 MiB／16 帧。`agent_draft_pending_intents` 每帧的
`items[]` 合计至多 100 项；每项是封闭的 `action=upsert|remove` 联合，单个 upsert value 的 canonical JSON
至多 1 MiB。达到 count 或 bytes 任一上限都
必须分页，不得通过截短 `content_handoff`、丢 terminal metadata 或借用其它 channel 规避预算。

## 3. Stream Classes

账号聚合包含三类彼此不同的状态：

1. `authority_committed`：Realm、Circle、Sidecar 各自独立 Commit stream；
2. `account_private`：preference、notification state、local drafts 等 Station-local 状态；
3. `delivery`：to-device、Welcome 与 push hint，需要独立 ACK/去重。

第一类以 `{stream_ref, stream_position, commit_id}` 排序；后两类不得伪装成 RealmCommit。

### 3.1 Account notification delta（normative）

notification delta 的闭合形态是 `{id, action, data?}`；它只表示“可能有新 committed/current/delivery 状态”。客户端响应通知后从 own Station读取，不使用通知 payload 授权动作。

#### 3.1.1 Agent runtime approval 分支（`ak:notification:<uuidv7>`）

审批通知绑定 exact request/actor/account；批准行为仍生成 producer-signed Event并等待 current authority Commit。

#### 3.1.2 普通源 Event 当前行分支（`ak:notification_projection:*`）

投影行必须携带来源 committed ref；同一来源重复通知不得产生第二次业务 effect。

#### 3.1.3 通道位置、baseline 与增量（两分支共用）

notification channel 使用自己的 Station-local revision。它不与任何 Realm stream position比较。

### 3.2 Agent signer 按需结果（normative）

Agent signer material 按需返回并绑定 exact Agent、controller、account 与 current authorization revision。客户端不从历史 Event自行挑选 signer。

### 3.3 Agent draft pending-intent channel（normative）

`AccountSubscribeFrame.agent_draft_pending_intents` 是独立 controller-holder-private projection；SDK 必须将它
投影为 `AgentDraftPendingIntentContainer::{Baseline,Delta}`，并在 `AccountBaselineChannel` 增加唯一
`AgentDraftPendingIntents` 分支。它不得进入 `account_data.events`、`account_data.station_cas`、
`notifications` 或 `to_device`，也不得通过 storage-private API 冒充公开 handoff。

稳定 item key 是 exact `(controller_account_id, agent_id, draft_id)`。`Baseline` 的
`snapshot_cut_position + page_offset + next_page_offset` 与外层 `baseline.snapshot_cursor` 共同冻结分页；
offset 仅属于该 pending-intent container，换 snapshot 或 `resync_required` 后必须丢弃。只有
`next_page_offset=null` 的末页可把该 channel 加入 `completed_channels`。`Delta` 的
`projection_position` 是本 channel 单调位置，并由外层 opaque account cursor 覆盖。cursor 续传必须返回遗漏的
available upsert 或 terminal update/removal；两类变化都在同一有序 `items[]` 中，以
`action=upsert|remove` 区分。cursor 失效时重做本 channel baseline，不得回退到 notification、to-device 或
account-data register 推测状态。

upsert value 直接验证为 `ak.schema.agent_draft_pending_intent.v1` 的 closed union：

- `Live` 分支仅允许 `state=available` 且 MUST 携完整 `content_handoff`；
- `TerminalRedacted` 分支仅允许 `state=consumed|expired`，MUST NOT 携 `content_handoff`／ciphertext，并 MUST
  保留 controller/agent/draft create-once identity、`accepted_event_id`、`canonical_event_digest`、
  `content_digest`、`created_at`、`expires_at` 与对应 `consumption` 或 `expired_at`；
- removal 只发生在 terminal metadata retention 之后，仍携稳定 key、source Event id、canonical/content
  digest、expiry、最后 terminal state／metadata 与 `removed_at`。客户端按 projection position 应用，旧
  available upsert 不得复活 terminal-redacted 或 removed item，也不得被误作 account-data revision。

每一 baseline page 与 delta 在披露前都 MUST 重验 session 对应 exact `controller_account_id` 的 active device。
Agent session、其它 AccountId、目标 Realm member 与 federation peer 一律不可见；错误 audience 必须 withheld，
不得用空 ciphertext 或 redacted 行泄露该 key 的存在。

`ak.vector.agent.draft_pending_intent.v1` MUST 覆盖本 channel 的多页 baseline、cursor delta、live／terminal-redacted、
terminal removal、no-resurrection、active controller device allow、四类 audience deny 与四个既有 carrier 禁用分支。

## 4. Realm Buckets

每个 Realm bucket 包含 Realm stream 和 caller 可见的 Circle/Sidecar stream 子项。子项是 `realm_sync_entry.streams[]`，每条各自携带 `{head_commit_ref, next_position}` 与自己的窗口标量（`limited` / `window_limit` / `complete` / `preview_only` / `e2ee_epoch`）；不得存在一个覆盖全部 scope 的 `realm_position`，也不得存在 bucket 级的窗口边界布尔——bucket 跨 N 条流时它没有指称对象，且会让一条流的窗口边界成为另一条流活动的函数。投递行在 bucket 级的扁平 `commits[]` 里，每行自带 `stream_ref` 与 `stream_position`；批次不需要跨流序（§6）。

看不到某 private stream 时，客户端不能从 position gap推断其存在或活动。**这条同时是 account 聚合 cursor 保持不透明的理由**：明文位置向量会把 caller 可见流集合的形状暴露出去，而单条 stream 的扫描因为位置本身不跨越可见性边界，才可以位置化（[`api-conventions.md` §7.2](./api-conventions.md)）。

`streams[]` 有条目上限。caller 获准可见的流超过上限时，服务端 MUST 置 `streams_limited=true`，且截断规则只依赖 caller 自己的可见流集合：Realm stream 只要可见就必须保留，其余按 `JCS(stream_ref)` 的 unsigned 字节序升序填满剩余名额。客户端 MUST 用 per-stream surface 补齐其余流，MUST NOT 把未出现在 `streams[]` 里的流判定为不存在。服务端不得静默丢流。

### 4.1 流的发现与选择（normative）

条目上限不得使一条流不可发现或永久饥饿。`ak.self.committed_event.read.scan.v1` 要求调用方**已经知道** `stream_ref`，因此它补不齐发现面；发现面是 `ak.self.realm.read.streams.v1`（`GET /_arkret/self/realms/{realm_id}/streams`）：ACL 过滤、可分页，返回该 caller 获准知道其存在且**已建立 Commit 链**的 `stream_ref`，以及每条流的可读 floor 与 head anchor。

订阅侧可显式选择流集合：subscribe filter 的 `stream_refs` 至多 64 条，必须去重、每条属于 `realm_ids` 中的 exact Realm 且为该 caller 获准可见；分组包含 Realm stream 时它占一个名额，不含 Realm stream 的分组同样合法。缺省（不带 `stream_refs`）保持现有的有界首屏与 `streams_limited`。

带 `stream_refs` 时窗口就是该选择集合：服务端只推进该集合的 tail，**未选中的流记作未投递而不是已投递且为空**；cursor handle 把 `filter_digest` 绑定到该选择集合，换组必须用新 filter 与新 cursor，而各组已到达的位置分别保留可续传（§12.1）。因此客户端 MAY 分批订阅全部流，服务端 MUST NOT 静默丢尾，也 MUST NOT 让固定的前 64 条永久占满名额。选择集合建立之后新增或移除的流，通过重新枚举或可见 discovery delta 发现，该发现 MUST NOT 被 event kind filter 屏蔽。

只有已经建立 Commit 链的 stream 才作为 `streams[]` 条目出现：尚未产生 position 0 的容器没有 `head_commit_ref` 可携带，服务端 MUST NOT 构造空 head 的窗口；它在首个 Commit 落地后由枚举面或后续帧发现。

## 5. 当前结果与历史展示上下文

### 5.0 current 与 timeline 的载体边界（normative）

Timeline 是 committed Event 的展示序列；current 是 own Station返回的 typed result。Timeline 不能替代 current，current 也不能证明客户端已下载全部历史。

### 5.1 服务器当前结果

Typed current result至少绑定 selector、value/status、领域 revision，以及来源 `{commit_id, stream_ref, stream_position}`。客户端核对 request/account/Realm/selector 后安装结果，不执行 authority-commit projection/typed current result reducer。

该 source coordinate 只绑定写出 current entry 的 source Event，不绑定 entry value 中任意嵌套 Event。历史
signer-key selector 的 `committed_event_ref` 只能从已验证 `realm_sync_entry.commits[]` 的
`stream_row{commit,event}` 逐字构造；窗口外回填继续使用 §5.2 的 per-stream scan，其
`stream_scan_outcome.committed_events[]` 复用同一个 `stream_row`。两条面必须核对 Commit signature／generation、
Realm／stream／position／predecessor 与 `commit.event_ref == event.event_id` 后才可建本地耐久索引；不得新增
Event 字段、account sibling map 或 signer 专用 carrier，也不得从 current projection、cursor、producer time、
arrival order 或缓存拼坐标。redacted／reference-locked row 不提供可验 producer envelope，必须保持 unresolved。

### 5.2 State At Window Start (limited timeline 边界状态)

窗口上下文分为两类，不可互相冒充：`realm_sync_entry.state_at_window_start` 是 **Realm 级显示预览**（actor 显示行与 Realm metadata），`streams[].window_start_basis` 是**逐流的可验证重建材料**。显示预览 MUST NOT 被当作安全快照，它的存在 MUST NOT 清除任何一条流的 `preview_only`——一个 Realm 显示对象存在，不能把该 bucket 全部 Circle / Sidecar 的窗口都标成可重建。

`window_start_basis` 绑定 exact Realm、exact `stream_ref`、状态所在的 exact 边界（`anchor_kind` + `anchor_position` + `anchor_commit_ref`）、承载该逐流 slice 的 authority-signed `realm-state-snapshot`（`snapshot_ref`）与其 `governance_generation`，以及重建该前缀所依赖的跨流授权依赖的 exact accepted references（`accepted_dependency_refs`，closed 四坐标 `committed_event_ref`）。列出这些引用不引入跨流总序，也不比较跨流位置。空前缀必须显式声明其 genesis 边界（`anchor_kind=stream_genesis`）；窗口起点落在 caller 可读 floor 上时用 `anchor_kind=before_readable_floor`，受限成员**不必**拿到 position 0。

非 preview 窗口引用的 exact `snapshot_ref` 必须能由 [`ak.self.realm_state_snapshot.read.by_ref.v1`](./service-http-binding.md) 向同一认证账号取回原完整签名对象；当前 `/head` 即使来自同一 Realm 也不得替代旧 ref。own Station 若不能在该窗口可消费期间保留并向该账号披露原对象，必须对该逐流窗口改报 `preview_only=true`，且不得继续给出名义可验的 basis。客户端逐字核对请求 ref、Realm、snapshot 与 basis 的同一历史任期，并用 fresh current nonce-bound authority bundle 的历史链验证该任期当时的签名 Station；再按 [`realm-state-snapshot-schema.md` §4](../conformance/realm-state-snapshot-schema.md) 验证 current rows、heads、floors 和每流 tail。任一失败时该窗口不得进入普通投影或 MLS。`readable_floor` 仅说明可读下界，不能补造 snapshot slice。

有限历史窗口 MAY 返回该逐流 slice，或明确 `preview_only=true`。两条路径都是**逐流**判定：某条流 `limited=true` 而帧不携带足以验证该流窗口起点的 `window_start_basis` 时，该流的 `streams[].preview_only` MUST 为 true。窗口起点状态来自 authority-signed snapshot slice 与对应 stream 的边界 anchor，不从首个可见 Event 的前驱或 producer 时间推导。只有在完成**该条流**所需上下文验证之后，其窗口起点行才能进入普通展示、reducer 输入或 MLS 安装流程。

**客户端不重放治理历史（normative）**：共享授权与对象重建由 own Station 负责，客户端只验证输出绑定、producer 输入与所需 MLS bytes / epoch。上一段所说的「重建」在服务端指获准前缀的重建，在客户端只指它本地已有的展示与密码学状态；它 MUST NOT 被理解为授权客户端重放私有治理闭包，也 MUST NOT 把历史窗口当作当前权限。

窗口起点之上的历史回填走 [`ak.self.committed_event.read.scan.v1`](./service-http-binding.md) 的 `before_position`，逐流进行。subscribe 面不保留第二套分页机制。

## 6. Event Ordering

同一 stream 中只按 `stream_position` 升序；position 0 无 predecessor，后续 Commit 的 `previous_commit_ref` 必须等于该 stream上一 Commit。Event 本身不携 predecessor。

不同 Realm/Circle/Sidecar stream 之间没有 protocol total order。UI需要混排时 MAY 使用 `created_at`/arrival time 做展示排序，但该顺序不得进入授权、current、MLS epoch或审计完整性判断。

**本节是跨流展示序的唯一定义点（normative）**：同一 stream 按 `stream_position`，跨 stream 无 protocol 序，混排序只是展示选择。[`conformance/encoding.md` §3.4](../conformance/encoding.md) 的 canonical digest comparator 是 scope restriction（规定该序可以用在哪里），不是任何展示面的默认序；其它章节 MUST NOT 另行定义跨流展示序。

## 7. Large Account and Large Realm Sync

大账号按 Realm bucket分页；大 Realm**逐条 stream**分页，续传凭据按面区分：subscribe 聚合面用 cursor，单 stream 扫描用 `stream_position`（[`api-conventions.md` §7.2](./api-conventions.md)）。snapshot + tail 是推荐恢复方式；不得为了打开首屏默认下载全历史。每页必须有 byte/item上限，截断必须返回明确的续传依据——cursor 面返回 continuation cursor，scan 面置 `truncated=true` 并由调用方从本批位置推进。

## 8. Lazy Loading Members

成员列表按 current projection分页，详情按需加载。缺失成员详情不能被解释为 leave/ban。

### 8.1 Member Roster, Identity Projection, and Handle Claims

Roster 行绑定完整 ActorId、membership current revision和来源 committed ref。Handle/Profile 是独立投影；相同 principal、不同 Station account不合并。私有 Realm不得因 lazy roster暴露不可见成员或 Station拓扑。

`member_roster_entry` 的 wire 字段严格如下：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `actor_id` | yes | 完整 ActorId。 |
| `membership` | yes | `join` 或 `knock`。 |
| `subject_account_id` | no | 获准披露时的 exact AccountId。 |
| `identity_event_ids` | no | 当前 identity Event IDs。 |
| `member_display_state_digest` | no | 当前可见身份状态摘要。 |
| `identity_events` | no | 可选原始 committed identity Events。 |
| `handle_claim_digests` | no | 当前可见 handle claim digests。 |
| `handle_claims` | no | 可选 signed handle claim evidence。 |
| `handle_claims_limited` | no | claims被截断或仅摘要时为 true。 |

## 9. Account Data and Private State

Account-private 状态不进入 RealmCommit，包括 UI preference、DND、local blocklist、draft 与 notification read state。它们使用 Station-local CAS/revision；引用 Realm 事实时必须绑定 exact committed ref，但不能获得 Realm写权。

## 10. To-Device Delivery

DeviceMessage 与 `MlsWelcomeDelivery` 是 recipient-scoped delivery，不是共享 Event。两者进入同一个
recipient-private、有序耐久队列：account delta 的 `to_device.deliveries[]` 和
`ak.self.device_messages.read.list.v1` 的 `deliveries[]` 均使用闭合判别联合，
`delivery_kind="device_message"` 携原样 `device_message`，`delivery_kind="mls_welcome"` 携
原样且带 producer proof 的 `mls_welcome`。客户端先按判别分支验证完整对象，再持久化、处理并显式 ACK；
不得把 Welcome 转成 DeviceMessage、共享 Event，或从另一个 URL 补取 Welcome。human device 的主路径是
account delta，两个分支都可从同一队列的 list 补拉。Agent runtime 使用其自身已授权 session 调用同一 list/ACK，
按 `(recipient_actor_id, recipient_endpoint.verification_method, current agent_key_authorize_event_id)`
绑定队列与 token；不能借用 controller 的 account/device 队列、session 或 synthetic device_id。

**恰好一次的 durable handler 副作用（normative）**：重投递是正常路径——新建订阅、补拉、cursor 重置或
服务端重试都会把未确认的 delivery 再次交给客户端，并**原样保留** `device_message_id`。客户端 MUST 在执行
handler 副作用**之前**查询 durable 去重记录。DeviceMessage 的键是**封闭的发送端点加 `device_message_id`**：human device
用 `(sender_account_id, sender_device_id, device_message_id)`，Agent 用 `(sender_agent_id, device_message_id)`，
Station service 用 `(sender_id, device_message_id)`。命中且已成功持久化的 delivery 只恢复完成位点，MUST NOT
再次执行 handler。kind 专属的 `transaction_id` / `request_id` 只关联该业务 transcript，MUST NOT 充当通用去重键。
`device_message_id` 相同而 envelope canonical 内容不同视为协议冲突，MUST fail closed，MUST NOT 覆盖既有去重记录。
Welcome 的键是 `(recipient_actor_id, recipient_endpoint, welcome_id)`，并绑定完整 producer-signed
`MlsWelcomeDelivery` canonical bytes；同键不同 bytes MUST fail closed。Welcome 没有
`device_message_id` 或 DeviceMessage sender endpoint，不能从其 Commit Event id 推造去重键。
两类去重记录都必须先于 handler 副作用 durable；队列 ACK 不代替此去重。

### 10.0 主接收路径与补拉路径 (normative)

human device 的主路径是 account stream 的 delivery delta；补拉路径与其共享同一 recipient queue 和 ACK
token，不创建第二份消息。`deliveries[]` 按同一队列位置顺序返回，可交错出现两种分支；pagination
cursor 与累计 ACK 均按队列位置计算，不按分支分别推进。Agent runtime 的 Welcome 由同一 list/ACK
operation 读取其 Agent endpoint 队列；service MUST 以当前 Agent session 与 accepted key authorization
精确选择该队列，不可把 human device 的 account delta 暴露给 Agent。

### 10.1 显式投递确认 (normative)

只有 durable processing 后才能 ACK。队列删除**只**由显式 ACK 驱动：account stream cursor 推进 MUST NOT 删除
任何 delivery，补拉路径的 `after=` 读取位置同样只读。ACK 是累计且单调的——服务端删除该 token 覆盖位置（含）
之前的全部已投递 delivery；ACK 一个早于当前确认位置的 token 是合法 no-op，MUST NOT 回退确认位置。并行
dispatcher MUST 维护"最高已连续持久化位点"，MUST NOT ACK 覆盖位置晚于任何尚未持久化的 delivery。cursor
失效、`dropped` 或 resync 都不使已签发的 ACK token 失效；服务端 MUST 仍按签发时的 exact recipient
endpoint 绑定校验并执行累计删除。human device token 绑定完整 `(account_id, device_id)`；Agent token
绑定 `(agent_id, verification_method, accepted authorization Event id)`，current authorization 被替换或撤销后
旧 Agent token 不可被新 session 用于读、ACK 或清除新 endpoint 的队列。任一 token 覆盖的两类 delivery
只要尚有一项未 durable processing，客户端 MUST NOT ACK 到该位置。

未确认的 `DeviceMessageEnvelope` 与 `MlsWelcomeDelivery` MUST 持久保留，不得因入队后的
`expires_at`、默认 TTL 或队列容量而删除。`expires_at` 限制发送／业务处理有效性，不能充当
队列 ACK。配置的 endpoint 队列容量是**入队前置限制**：满额时服务端 MUST 在同一原子写入
边界拒绝新的投递，既不淘汰旧项，也不消费该请求的幂等 identity；DeviceMessage send 使用
通用 `quota_exceeded`，且同一批次零部分入队；MLS Commit 携 Welcome 时，容量拒绝必须使
Commit、公开 MLS state 与所有 Welcome 一起零写入。队列容量按同一 exact endpoint 下两种
未确认分支合计，已 ACK 项不占容量。`lost` 仅可表示有持久证据的历史缺口或故障，不得把
正常 TTL／容量淘汰当作它的生产来源；`lost` 为真时客户端 MUST 重建 MLS／密钥就绪状态。

### 10.2 队列分页

队列 cursor只用于 recipient delivery。它不能作为 Realm stream cursor或 authority proof。

## 11. Filters

过滤器只能缩小 caller 已获权的数据。过滤不能改变 Commit continuity；若中间 Commit因内容过滤不可见，服务必须提供不泄露内容的连续性元数据或从授权 snapshot head开启新窗口，不能伪造相邻 predecessor。

### 11.1 Events 面的 query-scope digest（normative）

cursor 的 filter digest绑定 account、operation、完整 stream selectors、visibility/history floor和过滤条件。任一项变化都要求新 cursor。

## 12. Cursor Semantics

cursor 是签发 Station可验证的 opaque resume token，不是 Event/Commit ID，也不是跨 Station可移植证明。

### 12.1 Cursor Integrity (normative)

cursor 必须绑定 issuer、account/device、purpose、query-scope digest、expiry和内部 positions。篡改、跨账号、跨 operation复用必须拒绝。

### 12.2 校验流程 (normative)

服务先验签/MAC与 expiry，再核对 session、purpose和 query scope，最后才读取 position。失败不得推进任何 server-side state。

### 12.2.1 Cursor Revoke（high-assurance optional）

高保证部署可撤销 cursor；撤销不影响已提交 RealmCommit、delivery ACK token或 Event ID幂等性。

### 12.3 过期或缺口恢复流程

恢复优先级为：account baseline、目标 typed snapshot、每条获准 stream tail、按需旧历史。不得回退到邀请人/旧 authority的任意日志。

#### 12.3.1 `cursor_expired` / `cursor_integrity_invalid` / `cursor_unrecognized`（旧 cursor MUST 废弃）

丢弃旧 cursor并重做对应 surface baseline；不删除本地已验证 Commit或MLS private state。

#### 12.3.2 `revision_stale`（旧 cursor 仍有效，可继续 backfill）

该历史错误名只表示服务仍能从已有 cursor补拉更早的获准内容；它不是 actor/RealmCommit checkpoint。客户端按响应 continuation继续。

#### 12.3.3 历史完整性边界（两分支共用）

客户端验证每条可见 stream 的 Commit连续性、snapshot head和tail衔接。Retention/history floor之前的数据不可得不构成 gap；floor之后无法解释的 position跳跃必须停止该 stream并重取 snapshot/bundle。受限历史的下边界必须可验证而不是只能推断：`ak.self.committed_event.read.scan.v1` 的 `stream_scan_outcome.readable_floor` 给出 `oldest_position` 与该位置的 `floor_commit_id`，`window_start_basis.anchor_kind=before_readable_floor` 给出同一边界在窗口侧的 anchor，两者都把允许区间的下端绑定到已接受的链上，且都不要求 caller 持有 position 0。该 anchor 只证明获准前缀从哪里开始，不证明 Station 没有更早历史或更新的更新。

## 13. Initial Sync

1. own Station验证或刷新 current `RealmAuthorityBundle`；
2. 从 current authority取得 nonce-bound bundle；
3. 拉取 authority-signed typed snapshot；
4. 按 Realm、每个可见 Circle、每个可见 Sidecar的独立 head补 tail；
5. 安装 current result、delivery和Account-private baseline。

Invite issuer、Directory、cache或 genesis Station都只能提供 locator。默认不拉全历史。

### 13.1 渐进加载与目标就绪

首屏只等待目标对象、必要 current policy/membership和目标 stream tail。其它 Realm、旧历史、完整 roster与不可见 scope不得成为全局 readiness barrier。

## 14. E2EE Requirements

治理 Station只跟踪 MLS public state，不持有 group secret。客户端完整验证 RFC 9420 Commit、GroupContext minimal binding、tree、confirmation和Welcome。

MLS Genesis 在某 scope首次 authority commit 后不可逆激活；此前内容只能使用允许的明文形态，此后新的应用内容必须使用该 MLS group。Realm与各 Circle独立激活。

### 14.1 MLS 私态与解密缓存的本地静态加密 (normative)

本地 MLS private state、解密缓存和同主体备份必须静态加密并绑定账号/设备。新 member/endpoint 从其有效 Add/Welcome 起获得后续 epoch state。

客户端提供“清除派生明文缓存”操作时，MUST 只删除派生明文、解密缓存及可重新取得的辅助链接，不得因此删除已验证的当前或合法历史 MLS private-state checkpoint。清理前 MUST 向用户明确说明：保留 checkpoint 不保证每条旧消息均可重新解密；缺失的合法 epoch 私态无法由治理 Station 的 public state 重建。不得为履行清理承诺复活独立 exporter-history secret 存储或声称所有旧内容可恢复。

### 14.2 History-only multi-candidate store（normative）

实现 MAY 本地保留多个已验证历史 MLS states 以解密自己本来有权读取的旧消息，但不得通过网络候选合并或治理 Station 扩大访问范围。

## 15. E2EE and MLS Sync Performance

`ak.mls.commit` 与所有新增 recipient 的 `MlsWelcomeDelivery` 在 authority submission 中原子持久化。Commit accepted 后发送方立即安装 staged post-state，不等待 Welcome ACK。Welcome 重试按 `welcome_id` 幂等。

旧 Seal closure 形式的 MLS accepted-artifact 与 Welcome-ref 独立读取端点不属于 v1，服务 MUST NOT 将其作为 Commit 接纳证明或 recipient delivery 的第二读取源。Commit 的公开接纳事实由已登记的 committed Event／RealmCommit 读取面取得；`MlsWelcomeDelivery` 仍必须留在同一事务写入的 recipient-private queue，作为 §10 的 `delivery_kind="mls_welcome"` 原样交付：human device 经 account delta 或同队列补拉，Agent runtime 经自身 endpoint 的同队列补拉，均在 durable processing 后显式 ACK。移除旧端点不得删除 Welcome ciphertext、重试队列、outbox 或扩大其它客户端的可读范围。

每个 MLS scope维护单调 `key_access_revision`。Encrypted application Event只有在 epoch、group state ref、covered revision都等于 current public state时才能 commit；membership/device authorization变化推进 revision并阻塞 stale epoch新消息。

### 15.1 `decryption_pending` timeout and recovery

缺 epoch材料时先补拉该 scope 的 committed Genesis/Commit和 recipient delivery。超时仅驱动本地诊断，不改变 Event committed状态。若合法 private state永久丢失，治理 Station不能从 public tree恢复 secret；客户端必须显示不可解密或由获权成员通过后续标准 MLS transition修复。
