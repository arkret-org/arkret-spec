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

`ak.self.account.stream.subscribe.v1` 是账号聚合主入口。`ak.self.events.read.scan.v1` 与 `ak.self.events.stream.subscribe.v1` 用于读取一个或多个**明确获准的独立 stream**。字段、cursor 与 frame schema 见 [service-http-binding.md](./service-http-binding.md)。

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

每个 Realm bucket 包含 Realm stream 和 caller 可见的 Circle/Sidecar stream 子项。每个子项分别携带 head/cursor；不得存在一个覆盖全部 scope 的 `realm_position`。看不到某 private stream 时，客户端不能从 position gap推断其存在或活动。

## 5. 当前结果与历史展示上下文

### 5.0 current 与 timeline 的载体边界（normative）

Timeline 是 committed Event 的展示序列；current 是 own Station返回的 typed result。Timeline 不能替代 current，current 也不能证明客户端已下载全部历史。

### 5.1 服务器当前结果

Typed current result至少绑定 selector、value/status、领域 revision，以及来源 `{commit_id, stream_ref, stream_position}`。客户端核对 request/account/Realm/selector 后安装结果，不执行 authority-commit projection/typed current result reducer。

### 5.2 State At Window Start (limited timeline 边界状态)

有限历史窗口 MAY 返回签名 snapshot slice 或明确 `preview_only=true`。窗口起点状态来自 authority-signed typed snapshot和对应 stream head，不从首个可见 Event的前驱或 producer 时间推导。

## 6. Event Ordering

同一 stream 中只按 `stream_position` 升序；position 0 无 predecessor，后续 Commit 的 `previous_commit_ref` 必须等于该 stream上一 Commit。Event 本身不携 predecessor。

不同 Realm/Circle/Sidecar stream 之间没有 protocol total order。UI需要混排时 MAY 使用 `created_at`/arrival time 做展示排序，但该顺序不得进入授权、current、MLS epoch或审计完整性判断。

## 7. Large Account and Large Realm Sync

大账号按 Realm bucket分页，大 Realm按单 stream cursor分页。snapshot + tail 是推荐恢复方式；不得为了打开首屏默认下载全历史。每页必须有 byte/item上限，截断必须返回明确 continuation cursor。

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

DeviceMessage 与 `MlsWelcomeDelivery` 是 recipient-scoped delivery，不是共享 Event。它们按 delivery ID去重并由接收设备显式 ACK。

### 10.0 主接收路径与补拉路径 (normative)

主路径是 account stream 的 delivery delta；补拉路径与其共享同一 recipient queue 和 ACK token，不创建第二份消息。

### 10.1 显式投递确认 (normative)

只有 durable processing 后才能 ACK。Account stream cursor推进不删除 delivery；cursor失效也不使已签发 ACK token失效。

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

客户端验证每条可见 stream 的 Commit连续性、snapshot head和tail衔接。Retention/history floor之前的数据不可得不构成 gap；floor之后无法解释的 position跳跃必须停止该 stream并重取 snapshot/bundle。

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
