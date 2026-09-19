---
title: Client Sync
status: candidate
normative: true
stability: v1
updated: 2026-09-16
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

## 2. Endpoint

`ak.self.account.stream.subscribe.v1` 是账号聚合主入口。`ak.self.events.read.scan.v1` 与 `ak.self.events.stream.subscribe.v1` 用于读取一个或多个**明确获准的独立 stream**。字段、分页参数（subscribe 用 cursor，scan 用 `stream_position`）与 frame schema 见 [service-http-binding.md](./service-http-binding.md)。

### 2.1 多账号上下文 UX 指引（SHOULD）

客户端必须以完整 AccountId/ActorId 区分账号和成员身份。相同 principal 在不同 Station 的账号不能合并；UI 应明确显示当前提交账号和当前 own Station。

### 2.2 连接管理与重连

断线重连复用最后耐久保存的 account cursor。cursor 失效时重做 baseline；某条 Realm stream tail 缺失时只恢复该获准 stream，不重置其它 stream 或 to-device ACK。

### 2.3 按需列表、详情与分段 baseline（normative）

Initial sync 可以分段返回，但只有在某 section 的 baseline 完成标志到达后，客户端才能把该 section 作为完整集合替换。增量到达早于 baseline 完成时必须按 revision/stream position合并，不能被较旧 baseline 覆盖。

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

## 4. Realm Buckets

每个 Realm bucket 包含 Realm stream 和 caller 可见的 Circle/Sidecar stream 子项。子项是 `realm_sync_entry.streams[]`，每条各自携带 `{head_commit_ref, next_position}` 与自己的窗口标量（`limited` / `window_limit` / `complete` / `preview_only` / `e2ee_epoch`）；不得存在一个覆盖全部 scope 的 `realm_position`，也不得存在 bucket 级的窗口边界布尔——bucket 跨 N 条流时它没有指称对象，且会让一条流的窗口边界成为另一条流活动的函数。投递行在 bucket 级的扁平 `commits[]` 里，每行自带 `stream_ref` 与 `stream_position`；批次不需要跨流序（§6）。

看不到某 private stream 时，客户端不能从 position gap推断其存在或活动。**这条同时是 account 聚合 cursor 保持不透明的理由**：明文位置向量会把 caller 可见流集合的形状暴露出去，而单条 stream 的扫描因为位置本身不跨越可见性边界，才可以位置化（[`api-conventions.md` §7.2](./api-conventions.md)）。

`streams[]` 有条目上限。caller 获准可见的流超过上限时，服务端 MUST 置 `streams_limited=true`，且截断规则只依赖 caller 自己的可见流集合：Realm stream 只要可见就必须保留，其余按 `JCS(stream_ref)` 的 unsigned 字节序升序填满剩余名额。客户端 MUST 用 per-stream surface 补齐其余流，MUST NOT 把未出现在 `streams[]` 里的流判定为不存在。服务端不得静默丢流。

### 4.1 流的发现与选择（normative）

条目上限不得使一条流不可发现或永久饥饿。`ak.self.events.read.scan.v1` 要求调用方**已经知道** `stream_ref`，因此它补不齐发现面；发现面是 `ak.self.realm.read.streams.v1`（`GET /_arkret/self/realms/{realm_id}/streams`）：ACL 过滤、可分页，返回该 caller 获准知道其存在且**已建立 Commit 链**的 `stream_ref`，以及每条流的可读 floor 与 head anchor。

订阅侧可显式选择流集合：subscribe filter 的 `stream_refs` 至多 64 条，必须去重、每条属于 `realm_ids` 中的 exact Realm 且为该 caller 获准可见；分组包含 Realm stream 时它占一个名额，不含 Realm stream 的分组同样合法。缺省（不带 `stream_refs`）保持现有的有界首屏与 `streams_limited`。

带 `stream_refs` 时窗口就是该选择集合：服务端只推进该集合的 tail，**未选中的流记作未投递而不是已投递且为空**；cursor handle 把 `filter_digest` 绑定到该选择集合，换组必须用新 filter 与新 cursor，而各组已到达的位置分别保留可续传（§12.1）。因此客户端 MAY 分批订阅全部流，服务端 MUST NOT 静默丢尾，也 MUST NOT 让固定的前 64 条永久占满名额。选择集合建立之后新增或移除的流，通过重新枚举或可见 discovery delta 发现，该发现 MUST NOT 被 event kind filter 屏蔽。

只有已经建立 Commit 链的 stream 才作为 `streams[]` 条目出现：尚未产生 position 0 的容器没有 `head_commit_ref` 可携带，服务端 MUST NOT 构造空 head 的窗口；它在首个 Commit 落地后由枚举面或后续帧发现。

## 5. 当前结果与历史展示上下文

### 5.0 current 与 timeline 的载体边界（normative）

Timeline 是 committed Event 的展示序列；current 是 own Station返回的 typed result。Timeline 不能替代 current，current 也不能证明客户端已下载全部历史。

### 5.1 服务器当前结果

Typed current result至少绑定 selector、value/status、领域 revision，以及来源 `{commit_id, stream_ref, stream_position}`。客户端核对 request/account/Realm/selector 后安装结果，不执行 authority-commit projection/typed current result reducer。

### 5.2 State At Window Start (limited timeline 边界状态)

窗口上下文分为两类，不可互相冒充：`realm_sync_entry.state_at_window_start` 是 **Realm 级显示预览**（actor 显示行与 Realm metadata），`streams[].window_start_basis` 是**逐流的可验证重建材料**。显示预览 MUST NOT 被当作安全快照，它的存在 MUST NOT 清除任何一条流的 `preview_only`——一个 Realm 显示对象存在，不能把该 bucket 全部 Circle / Sidecar 的窗口都标成可重建。

`window_start_basis` 绑定 exact Realm、exact `stream_ref`、状态所在的 exact 边界（`anchor_kind` + `anchor_position` + `anchor_commit_ref`）、承载该逐流 slice 的 authority-signed `realm-state-snapshot`（`snapshot_ref`）与其 `governance_generation`，以及重建该前缀所依赖的跨流授权依赖的 exact accepted references（`accepted_dependency_refs`，closed 四坐标 `committed_event_ref`）。列出这些引用不引入跨流总序，也不比较跨流位置。空前缀必须显式声明其 genesis 边界（`anchor_kind=stream_genesis`）；窗口起点落在 caller 可读 floor 上时用 `anchor_kind=before_readable_floor`，受限成员**不必**拿到 position 0。

有限历史窗口 MAY 返回该逐流 slice，或明确 `preview_only=true`。两条路径都是**逐流**判定：某条流 `limited=true` 而帧不携带足以验证该流窗口起点的 `window_start_basis` 时，该流的 `streams[].preview_only` MUST 为 true。窗口起点状态来自 authority-signed snapshot slice 与对应 stream 的边界 anchor，不从首个可见 Event 的前驱或 producer 时间推导。只有在完成**该条流**所需上下文验证之后，其窗口起点行才能进入普通展示、reducer 输入或 MLS 安装流程。

**客户端不重放治理历史（normative）**：共享授权与对象重建由 own Station 负责，客户端只验证输出绑定、producer 输入与所需 MLS bytes / epoch。上一段所说的「重建」在服务端指获准前缀的重建，在客户端只指它本地已有的展示与密码学状态；它 MUST NOT 被理解为授权客户端重放私有治理闭包，也 MUST NOT 把历史窗口当作当前权限。

窗口起点之上的历史回填走 [`ak.self.events.read.scan.v1`](./service-http-binding.md) 的 `before_position`，逐流进行。subscribe 面不保留第二套分页机制。

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

DeviceMessage 与 `MlsWelcomeDelivery` 是 recipient-scoped delivery，不是共享 Event。它们按 delivery ID 去重
并由接收设备显式 ACK。

**恰好一次的 durable handler 副作用（normative）**：重投递是正常路径——新建订阅、补拉、cursor 重置或
服务端重试都会把未确认的 delivery 再次交给客户端，并**原样保留** `device_message_id`。客户端 MUST 在执行
handler 副作用**之前**查询 durable 去重记录，去重键是**封闭的发送端点加 `device_message_id`**：human device
用 `(sender_account_id, sender_device_id, device_message_id)`，Agent 用 `(sender_agent_id, device_message_id)`，
Station service 用 `(sender_id, device_message_id)`。命中且已成功持久化的 delivery 只恢复完成位点，MUST NOT
再次执行 handler。kind 专属的 `transaction_id` / `request_id` 只关联该业务 transcript，MUST NOT 充当通用去重键。
`device_message_id` 相同而 envelope canonical 内容不同视为协议冲突，MUST fail closed，MUST NOT 覆盖既有去重记录。

### 10.0 主接收路径与补拉路径 (normative)

主路径是 account stream 的 delivery delta；补拉路径与其共享同一 recipient queue 和 ACK token，不创建第二份消息。

### 10.1 显式投递确认 (normative)

只有 durable processing 后才能 ACK。队列删除**只**由显式 ACK 驱动：account stream cursor 推进 MUST NOT 删除
任何 delivery，补拉路径的 `after=` 读取位置同样只读。ACK 是累计且单调的——服务端删除该 token 覆盖位置（含）
之前的全部已投递 delivery；ACK 一个早于当前确认位置的 token 是合法 no-op，MUST NOT 回退确认位置。并行
dispatcher MUST 维护"最高已连续持久化位点"，MUST NOT ACK 覆盖位置晚于任何尚未持久化的 delivery。cursor
失效、`dropped` 或 resync 都不使已签发的 ACK token 失效；服务端 MUST 仍按其 `(account_id, device_id)` 绑定
校验并执行累计删除。

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

客户端验证每条可见 stream 的 Commit连续性、snapshot head和tail衔接。Retention/history floor之前的数据不可得不构成 gap；floor之后无法解释的 position跳跃必须停止该 stream并重取 snapshot/bundle。受限历史的下边界必须可验证而不是只能推断：`ak.self.events.read.scan.v1` 的 `stream_scan_outcome.readable_floor` 给出 `oldest_position` 与该位置的 `floor_commit_id`，`window_start_basis.anchor_kind=before_readable_floor` 给出同一边界在窗口侧的 anchor，两者都把允许区间的下端绑定到已接受的链上，且都不要求 caller 持有 position 0。该 anchor 只证明获准前缀从哪里开始，不证明 Station 没有更早历史或更新的更新。

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

### 14.1 解密缓存与历史密钥的本地静态加密 (normative)

本地 MLS private state、解密缓存和同主体备份必须静态加密并绑定账号/设备。新 member/endpoint 从其有效 Add/Welcome 起获得后续 epoch state。

### 14.2 History-only multi-candidate store（normative）

实现 MAY 本地保留多个已验证历史 MLS states 以解密自己本来有权读取的旧消息，但不得通过网络候选合并或治理 Station 扩大访问范围。

## 15. E2EE and MLS Sync Performance

`ak.mls.commit` 与所有新增 recipient 的 `MlsWelcomeDelivery` 在 authority submission 中原子持久化。Commit accepted 后发送方立即安装 staged post-state，不等待 Welcome ACK。Welcome 重试按 `welcome_id` 幂等。

每个 MLS scope维护单调 `key_access_revision`。Encrypted application Event只有在 epoch、group state ref、covered revision都等于 current public state时才能 commit；membership/device authorization变化推进 revision并阻塞 stale epoch新消息。

### 15.1 `decryption_pending` timeout and recovery

缺 epoch材料时先补拉该 scope 的 committed Genesis/Commit和 recipient delivery。超时仅驱动本地诊断，不改变 Event committed状态。若合法 private state永久丢失，治理 Station不能从 public tree恢复 secret；客户端必须显示不可解密或由获权成员通过后续标准 MLS transition修复。
