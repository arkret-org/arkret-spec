---
title: Realm State Snapshot Schema
status: candidate
normative: true
stability: v1
updated: 2026-10-22
sidebar:
  label: Realm Snapshot
---

# Realm 状态快照

规范关键字按[规范语言](./normative-language.md)解释。机器契约为
[`realm-state-snapshot.schema.json`](../../artifacts/schemas/realm-state-snapshot.schema.json)，bootstrap 与治理
Station 更换规则见[治理提交日志](../sync/authority-commit-log.md)。

## 1. 目的与边界

Snapshot 是加速恢复的派生物，不是真相源。真相源是 producer-signed Event 与当前治理 Station 签发的
RealmCommit。Snapshot 必须绑定 Realm、authority generation、签发时各个可见 stream head、内联 typed
current rows、对应 history floor、创建时间和 Station proof。closed wire 成员是 `snapshot_id`、
`realm_id`、`governance_generation`、`purpose`、可选 `history_basis`、`visible_stream_heads[]`、`current_state_entries[]`、
`retention_and_history_floor`、`created_at` 与 `signature`。v1 没有额外的 sections、chunk/chunk digest、
state root 或 Blob 引用层；不得把旧 replay 容器作为此 schema 的兼容分支。

`purpose="full_recovery"` 的同 cut 基线用于 join、新设备、缓存修复、跨站副本 bootstrap 及 planned
handoff；历史窗口只使用 `purpose="stream_history"` 的独立原签 basis。受限成员不必下载 floor 之前的治理历史；分别读取多项 current 与 heads 不能替代这个
一致截面。Account current baseline 冻结账号发现和各 channel 的交付进度，不承诺同一 Realm 的完整 typed
rows、逐流 heads 与 floors，也不承载原治理签名，MUST NOT 替代 Snapshot 或历史窗口的 exact basis。
Snapshot 不授予写权限、不交付 MLS 私钥，也不替代当前授权、最终交付门或 handoff 的完整私有迁移。

v1 保留完整内联基线及其 Realm 硬容量预算，包含按 §3 获准披露的内容型 rows；完整 signed canonical body
不得超过 8 MiB，准入与恢复规则见 [scalability-constraints §4.1](./scalability-constraints.md#41-realm-snapshot-硬容量预算)。
这是一项有界 Realm 的容量选择，不能解释为无限消息存储保证；客户端职责简化不解除服务端的容量门。

## 2. 可见 stream heads

`visible_stream_heads[]` 对接收者获准读取的每条 Realm、Circle 或 Sidecar stream 分别记录 `stream_ref`、
`stream_position` 与 `realm_commit_id`。不同 stream 的 position 不能比较，也不能由数组顺序推导总序。

普通 joiner 的 snapshot 只列出其当前可见 stream；因此它只能验证这些 stream 的连续性，不能证明隐藏
Circle 或 Sidecar 不存在。planned authority handoff 使用单独的私有 full-stream-head manifest，不能从公开
authority bundle 或普通 join snapshot 获得隐藏 stream 列表。

## 3. Typed current rows

`current_state_entries[]` 的每个元素必须是 `typed-current-result.schema.json` 的 closed typed result；
其 selector、revision 和 value 由各 family 的 schema 决定，不额外包一层通用 row/chunk。当前治理 Station
必须从同一 durable cut 读取本用途覆盖范围内全部可向该请求者披露的 rows、`visible_stream_heads[]` 和 stream floors，
不得把无权 Circle/Sidecar 的 row、head 或 floor 混入；同一完整 typed subject 不得出现两个 current row。
接收方须以每条 row 必填的 `source_stream_ref` 定位可见 head 与 floor，验证其 Realm/stream 属于本次可见范围、
revision 的位置不晚于**该 stream** 的可见 head；不得从 selector 或同值 position 猜来源。可读取到
revision 所指 Commit 时还须逐字核对其 stream、commit id 与 position。落在获授权 history floor 之前的
row 由当前治理 Station 的这份签名 snapshot 承诺，不能要求受限接收者下载不可见前史来补证；
范围或坐标不一致时整份丢弃。

Relation 使用已登记的 `relation` result：selector 是完整 `primary_conflict_domain`，
value 是该 domain 唯一的完整当前 Relation（含 active 或 tombstoned 状态），不另造按 RelationId
选取的 current 身份或冲突集合。它的 `source_stream_ref` MUST 等于当前 value 的源作用域；
Circle scope 不进入 primary-domain 身份。除源 Realm/Circle 成员可见性外，完整 row 还 MUST
满足 [`../models/relation.md` §4](../models/relation.md#4-跨-realm-引用) 对两个 endpoint 的
reference-disclosure 要求。无权、未知或不可证明可披露的 endpoint 不得通过 Snapshot 泄露；
该完整 row MUST 省略，不能将 locked stub、部分 Relation 或未授权 target-side reverse edge
写入 canonical `current_state_entries[]`。重取旧 Snapshot 时也必须重新执行同一披露判定。

**内容型与状态型 family 的披露（normative）**：「可向该请求者披露」按 family 性质分两类。
`message_revision` 是 v1 唯一的内容型 family：它的 value 就是承载 Event 的 create／revise payload，即历史内容。
它的 row 只在同时满足下列两条时进入 snapshot：(1) row 的 covering Commit（`revision` 所指）位于请求者在
`source_stream_ref` 上的可读区间内，即不早于该 stream 的 caller readable floor（`since_join` 成员为其当前有效
join Commit，见 [`../governance/history-visibility.md` §3.1](../governance/history-visibility.md)）——不满足时
请求者本来也不能经 scan 读到承载该 value 的 Event；(2) 该 Message 没有 `ak:message:` 拼写的 `object_redaction`
row——已撤回 Message 只下发其 `object_redaction` row，原 payload 不得经 snapshot 恢复
（[`../models/strand-and-message.md` §9.5.1](../models/strand-and-message.md)）。其余 family 都是状态型，按
membership 与 scope 可见性披露，不受 history floor 限制：Realm 共享状态向全部 joined 成员可见，floor 只约束
内容历史。按 `snapshot_ref` 重取已签发 snapshot 时同样按请求者当前可读区间与当前撤回状态重验，已含不再可披露
`message_revision` row 的 snapshot 对该请求者不可用。接收方 MUST 接受「只有 `object_redaction`、没有
`message_revision` row」的 Message，也 MUST NOT 把 floor 以下 Message row 的缺席当作缺口。
从 snapshot 边界之后的逐 stream tail 继续运行同一 typed reducer，不得用 generic patch、
typed current result merge 或 wall-clock last-write-wins 修补差异。`current_state_entries: []` 仅在该 cut
确实没有可披露 current row 时合法；它不是要求另取 chunk 的占位符，也不能证明隐藏 row 不存在。

## 4. 创建与验证

Snapshot 的 `signature` 使用 `ak.realm_snapshot_signature.v1`。unsigned projection 是从完整 closed Snapshot 删除
`signature` 后保留的全部实际存在成员；验证方对其作 RFC 8785 JCS，重算
`sha256:lowercase_hex(SHA-256(unsigned_bytes))`，先与 envelope 的 `signed_digest` 逐字比较，再验证
`UTF8("ak.realm_snapshot_signature.v1\n") || RFC8785_JCS({context,signature_algorithm,verification_method,signed_digest,created_at})`
上的 64-byte Ed25519 签名。以下原治理证明由消费 Account Station 与独立审计者执行；普通客户端按
[server-trusted-results §2.1](../sync/server-trusted-results.md#21-普通客户端消费既有治理结果normative)
消费已持久接纳、绑定完整认证账号及本地会话的自己 Station 原件，不执行治理链、方法历史、治理签名或 nonce 验证。
当前 `/head` MUST 是 `purpose="full_recovery"` 且不携带 `history_basis`。历史窄对象 MUST NOT 进入 join/bootstrap/handoff 或 current 覆盖安装；其未覆盖项不表示缺失、删除或不可见。
当前 `/head` snapshot 的 `governance_generation` 必须等于 fresh current authority bundle 的当前任期，
其 `verification_method` 必须是当前 Station 的 service signing key。按已发出 `snapshot_ref` 读取的历史 exact snapshot 可属于更早任期；
消费 Account Station／独立审计者必须由同一 fresh current authority bundle 的完整 genesis-to-current 历史链定位该 generation 当时的治理 Station，
以该 Station 在 snapshot 签署时有效的 exact service signing key 验签。未知 generation、链外 Station、旧 key 代签新任期均必须拒绝；
不能拿当前 Station key 替旧任期签名，也不能把已被取代的 snapshot 冒充当前 `/head`。

当前治理 Station 在同一一致性快照中读取 visible stream heads、`current_state_entries[]` 与 history floors，构造 canonical body，
计算 snapshot ID 并签名。消费 Account Station／独立审计者必须验证：

1. fresh current authority bundle 证明签名 Station 是 snapshot 的 `governance_generation` 当时的治理 Station；当前 `/head` 还必须处于当前任期；
2. snapshot ID 与 canonical body 匹配；
3. Station proof 的 domain separation 与 payload digest 匹配；
4. 每个 visible head 可由随后下载的同 stream tail 连续承接；
5. tail 中每个 Commit 的 Event、producer proof、authority proof 与 typed reducer 均有效。

普通客户端仍 MUST 验证完整 closed shape 与 content ID、请求 ref、Realm／scope／完整 selector、revision／generation、
同 cut 的 rows／heads／floors、逐流 tail 衔接及既有 checkpoint，独立执行 producer proof 自身一致性、exact historical
signer selector、MLS 与附件验证。历史 exact by-ref 的任期 MUST 与窗口 basis 一致，可以早于当前任期；它仅供该历史
窗口使用，MUST NOT 安装为较新 current 的替代品、回退已保存 head 或冒充当前 `/head`。

### 4.1 Exact 历史原件与当前披露权限

v1 在窗口引用发布前签发独立 `purpose="stream_history"` 原件；签名与 content ID 覆盖用途和整个
`history_basis={account_id,stream_ref,anchor_position,anchor_commit_ref,accepted_dependency_refs}`。
完整 AccountId 同时绑定认证主体和 Station；Realm、generation、exact ref 与窗口逐字一致。by-ref 请求仍使用既有
认证账号、Realm 与 snapshot_ref 路由，不新增操作；结果的 signed coverage 必须匹配该窗口，`/head` 仅提供完整恢复。
跨站 Account Station 可经既有 `ak.peer.realm_join.read.bootstrap.v1` 的可选 `history_stream_ref` 请求源站当前 cut 的窄原件；省略时仍为完整恢复。请求必须绑定真实当前 membership Commit 与 member Account，响应的 signed Account／目标／任期须逐字匹配。接收站只归档原件及所需已接受依赖，不将此结果送入完整 bootstrap 安装；旧 cut 使用已保留原件，不能用此 fresh 请求替换已发窗口。

**selector 完备性（normative）**：取该已接受 cut 下所有 `source_stream_ref` 等于目标流的可披露 typed rows，但排除 `circle`／`sidecar` 定义 selector：这些定义虽来自父 Realm stream，实际属于各自 scope，不得让 Realm 历史顺带依赖它们；
Circle／Sidecar 目标还取该 cut 的父 Realm `member_state`（该 Account Actor）以及 exact `circle`／`sidecar`
定义 selector。这些是唯一额外 selector，source 必须是父 Realm；同一 selector 不得重复。跨流来源必须逐条解析为
原 accepted Event／Commit 四坐标，排序去重后逐字等于 `history_basis.accepted_dependency_refs` 与窗口的依赖引用。
heads／floors 恰覆盖目标与这些必要 selector 的 source streams，不得顺带包含其他 scope。target head 必须等于
anchor；所有 rows、heads、floors 来自原同一 cut，依赖不得跨 cut 更新替换。source 明确承担该 selector 集在该 cut
完整物化的责任；签名不额外提供 omission proof。原件未含真实依赖或不可证明可披露时只能在发窗口前报 preview。

完整恢复原件可以作为签发输入，但必须验证其来源和原 cut，从该 cut 得到上述完整 selector 集，然后由该 cut 的
治理权威签发新的原件和 ID；不得剪掉已发原件的组件沿用旧签名，也不得由接收 Account Station 冒充 foreign governor
重签。无法按该任期合法签发的历史 cut 只能使用此前已签发的窄原件或报 preview，不用当前 head 代替。

每次 exact by-ref 读取，Station MUST 在同一当前授权 cut 重验所有实际包含的 rows、heads、floors 及 exact
accepted dependencies，包括 membership、scope、history floor、retention 与 redaction。目标自身或真实依赖失权时
整份拒绝；未包含的无关 Circle／Sidecar 失权不影响目标 basis。值或 head 前进、新增可见流不要求改写历史原件。
MUST NOT 部分采用、删除失权组件沿用原 ID，或用另一 cut／Snapshot／裸 cursor 替换 basis。

未被窗口 reservation 引用的原件按完整恢复／逐流历史 coverage 分别有界保留，淘汰同一 coverage 的旧原件不得挤掉另一流正在使用的 basis；已引用原件仍受原 cursor 生命周期保护。

own Station 必须按 [client-sync §5.2](../sync/client-sync.md#52-state-at-window-start-limited-timeline-边界状态) 的 cursor 有效期保留原件；保留不覆盖
当前授权门。签发时已不能保证保留与披露的窗口 MUST 逐流标为 preview；签发后撤权导致 exact basis 不可得时，
读取使用既有不可用结果，客户端不得持久安装该 Account 帧或推进其聚合 cursor。重新同步须取得新的合法窗口；
不得将失败帧原地降级成成功。原件验证失败同样整份拒绝，不部分采用其 rows。

任一项失败时必须丢弃整个 snapshot，不能部分采用 rows。Snapshot 签名使签署时该任期的治理 Station 对
该 materialization 负责，但本身不提供独立 omission proof；随后 tail 的逐 stream 连续性只能
证明从各自已验证 head 起的后续 Commit 没有缺口，不能反证该 head 前被治理方隐去的 row。

## 5. Join bootstrap

邀请人服务器和 Directory 只提供候选 locator。Joiner 的 Account Station 向候选发送 fresh nonce，取得并验证
genesis-to-current 的 nonce-bound authority bundle，再从该 current governance Station 拉取 snapshot 与 joiner
可见的所有 stream tails。普通客户端经已持久接纳的自己 Station 按 §4 消费原件。邀请中缓存的“初始 Station”
或 genesis Station 不能覆盖已验证的 current authority；Station／独立审计者不因客户端职责简化而免除原治理验证。

## 6. Planned handoff

旧 Station 私下向新 Station 交付 snapshot、完整 stream-head manifest 及每条 stream 的缺口材料。公开
handoff certificate 只披露 Realm stream head 与 full manifest digest。新 generation 在每条既有 stream 上的
第一笔 Commit 必须以前一 generation 导入的该 stream head 为 `previous_commit_ref`，位置加一；它们彼此没有
统一的“handoff 后第一笔”顺序。

若旧 Station 丢失且未完成双签 handoff，v1 不自动选主，也不允许新 Station从成员投票或最长链自行接管。
恢复必须走 Realm 明确声明的外部恢复政策或创建新 Realm。
