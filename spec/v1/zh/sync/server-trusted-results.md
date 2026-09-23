---
title: Authority-Attested Results
status: candidate
normative: true
stability: v1
updated: 2026-09-20
see_also:
  - ../conformance/normative-language.md
  - authority-commit-log.md
  - service-http-binding.md
---

# Authority-attested 结果

规范关键字按[规范语言](../conformance/normative-language.md)解释。

用户已经信任自己的 Account Station 进行会话、账号和本地可见性处理，但 Realm 共享事实的 finality
只能来自 current governance Station 的 RealmCommit 或绑定该 authority generation 的 typed snapshot。

## 1. 信任方与角色

v1 保留三类可被 Account Station 转达的权威结果：

- `RealmCommit`：证明 exact Event 已在某一 Realm/Circle/Sidecar stream 的唯一 position 被接纳；
- `RealmStateSnapshot`：由当前治理 Station 签名确认指定 authority generation 下的内联 `current_state_entries[]` typed current rows、调用者获准 stream heads 与 history floors；
- `TypedCurrentResult`：返回封闭 selector 的 current value 及最后影响它的 Commit revision。

服务不得返回一个既无 RealmCommit 又无 typed snapshot/current signature 绑定的 `accepted=true`。

## 2. 消费方验证

消费 Station 必须：

1. 从 Realm genesis 开始验证连续 handoff chain；
2. 确认签名者是该 generation 的 current governance Station；
3. 验证 object ID、detached signature 投影和 nonce/audience；
4. 对 Commit 验证同 stream 的 position/predecessor 连续性；
5. 对 snapshot/current 验证 selector 和可见性没有扩张到其它 Circle/Sidecar。

客户端仍独立验证 Event producer proof、MLS/attachment 密码学和用户意图。Authority signature 不能替代 producer signature。

## 3. 转发与缓存

Account Station 可以缓存已验证结果并对自己账号开放，但必须保留 exact authority bytes 和验证状态。
它不得改变 revision、合并多个 stream 为一个伪全局序，或用本地接收时间作为 finality。

Authority handoff 后，旧 generation 的历史 Commit 仍可验，但旧 Station 签发的新 position 无效。缓存在每次写入前
必须刷新 authority bundle。

## 4. 服务器验证复用

MLS current 只包含 public group state、epoch、group-state ref、`current_key_access_revision` 和
`covered_key_access_revision`。两个 revision 不等时，治理 Station 拒绝新 encrypted application Event 和 Welcome admission，
直到有效 MLS Commit 覆盖 current revision。

Welcome 是 producer-signed recipient delivery object，与 Add Commit 原子入队。它不是 Realm Event，不产生独立
RealmCommit。接收者按 `welcome_id` 幂等 ACK；ACK 不改变已接纳 Commit 的 finality。

## 5. MLS 绑定结果

单 authority 模型不证明治理 Station 没有审查、扣留或错误接纳一个真实 producer Event。它只提供统一顺序、
即时 current authorization 判断和获准 stream 的连续性。需要 Byzantine transparency 的部署必须使用未来的独立 witness
profile，不得恢复 authority-commit/RealmCommit/typed current result 双平面。

## 6. 信任边界细则

### 1.1 攻击者与责任矩阵

Account Station 只对 session、本地可见性与缓存负责，不产生 Realm finality。

### 1.2 普通客户端的 Station 接入（normative）

Realm finality 的信任锚是 genesis + handoff chain 确定的 current governance Station。本节是普通客户端首次
登录、恢复连接与重新接入自己 Station 的唯一合同：它**不要求**客户端实现 DID method-native 的历史 verifier，
也**不授权**客户端把任意外部服务当作自己的 Station。

1. **独立起点**：客户端 MUST 从用户明确选择的 Station HTTPS base URL，或部署独立预配的 base URL 与预期
   身份/认证绑定开始。搜索结果、邀请、二维码与 redirect 只提供候选，MUST NOT 自动替换该选择。TLS MUST
   验证被选择 origin 的证书；已预配的 `service_id`、`trust_domain` 或认证绑定存在时，服务自报 MUST 与之
   逐字匹配，MUST NOT 覆盖它。
2. **公开发现**：在发送任何既有账号凭据**之前**，从该 base 读取 `GET /_arkret/describe`。该请求 MUST 不带
   凭据、MUST 不跟随自动 redirect，并执行
   [`service-http-binding.md` §2.3](./service-http-binding.md) 的大小、压缩与超时限制。客户端 MUST 检查
   `protocol_version`、`service_kind="station"`、唯一 canonical HTTP JSON base 与实际选择一致，以及合法的
   `service_id`、`trust_domain` 与 `auth_metadata`。describe 自洽不证明该 origin 是某个人或组织的真实服务。
3. **认证绑定**：全部 account 操作 MUST 从 `auth_metadata.account_authority.gate_account_base_url` 派生，并
   校验其 origin 与 `account_authority.origin` 一致；MUST NOT 按 operation 猜地址，也 MUST NOT 在 base 缺失时
   回退。Station、Authority 与 IdP 可以分处不同 origin。
4. **持久接纳**：客户端 MUST 在开始认证或重用凭据**之前**，耐久保存并逐项比较所选 base URL、`service_id`、
   `trust_domain`、Authority origin/base 与认证方法配置。集合顺序、可忽略的 `x_*`、动态 limits/features 以及
   未改变上述绑定的常规签名 key rotation 都**不**构成认证权威替换。该持久状态 MUST NOT 随登出、进程重启、
   账号切换或缓存淘汰自动丢弃；并发首次安装 MUST 比较既有绑定，MUST NOT 后写覆盖。保存或读取失败 MUST
   阻止后续凭据发送，MUST NOT 降级为"首次接入"。
5. **变更与重新接入**：恢复连接 MUST 先重新取得公开 describe 并与持久绑定比较。失配时 MUST 停止认证、
   refresh 与既有凭据发送，并保留旧绑定与账号材料；只有用户显式重新选择并确认新绑定，或独立受信的部署
   管理渠道授权更新之后，才可安装新绑定并**重新认证**。MUST NOT 向新权威转交旧 handoff、authorization
   code、refresh token 或 SessionGrant，MUST NOT 以"重试""重新连接"或清缓存代替重新接入。
6. **独立验证不被替代**：客户端不重放 DID 历史，并不免除服务端的独立验证义务——Station、registry、联邦
   接收方与独立审计者各自的原生验证职责不变。不能验证的候选 MUST NOT 被标记 verified，也 MUST NOT 作为
   隐式账号接入依据。

首次 origin 选错、独立预配渠道失陷或受信 WebPKI/origin 失陷属于残余暴露；持久绑定只能延续已经作出的选择，
不能追溯证明首次选择正确。

### 5.2 已知 MLS artifact 的接纳结果

MLS public state 由 accepted Genesis/Commit Event 及其 RealmCommit 投影。

#### 5.2.1 认证收件人的 Welcome 引用发现

调用方通过 Commit Event ref 与 typed MLS current 判断 winning transition，不通过独立 RealmCommit proof。

### 5.6 按次 current 与精确历史签名公钥

授权结果绑定 exact selector、authority generation、current revision 与 caller audience。机读合同是
[`signer-key-operations.schema.json`](../../artifacts/schemas/signer-key-operations.schema.json)。

**结果不镜像身份（normative）**：current 与 historical 结果的 key 统一使用封闭 `query_signing_key`，只含
`public_key_b64u`、完整 `authorization_ref: committed_event_ref`、`revision{commit_id,stream_position}` 与
`governance_generation`。`actor` 与 `verification_method` **只从 enclosing selector 取得**，key MUST NOT 重复
携带这两个字段。`revision` 是该 authorization stream 在解析时已验证的 current revision，MUST 与
`authorization_ref.stream_ref` 属于同一 stream、位置不得早于 authorization Event，并由其 RealmCommit 验证
`governance_generation`；缺任一坐标或绑定时必须返回 `unavailable`，不得只返回缓存 key bytes。SDK MAY 在本地
由 selector 与 key 组装完整缓存类型，但 MUST NOT 把该身份镜像写回 self wire result。

**关联只靠完整 selector（normative）**：每个请求 selector 恰好对应一个结果，不省略、不重复、不额外添加。
结果关联 MUST 使用**完整 selector 的相等性**——`verification_mode`、`sender_kind`、完整 AccountId、
`device_id`（适用时）、`verification_method` 与历史 `committed_event_ref`（适用时）——MUST NOT 使用数组下标。乱序不影响
关联；重复、缺失或多余的 selector MUST 拒绝整份结果。

**历史坐标来源与双引用分离（normative）**：两个 `historical_event` selector 都 MUST 携 required
`committed_event_ref{event_id,commit_id,stream_ref,stream_position}`，且 `stream_ref.realm_id` 必须等于请求
`realm_id`。该引用是“待验 producer 签名的 historical Event”；结果 key 的 `authorization_ref` 是“使该 key
在该历史点有效的 accepted authorization Event”。两者 MAY 相同但 MUST 独立验证，协议不得强制相等、互相替代
或因 key bytes 相同而合并授权代次。唯一构造来源是已验证
`realm_sync_entry.commits[]` 或 `stream_scan_outcome.committed_events[]` 的 `stream_row{commit,event}`：客户端先验证
RealmCommit signature／generation／stream／position／predecessor，并核对 `commit.event_ref == event.event_id`，
再逐字复制四坐标。current projection 中嵌套的 Event、`event_states[]`、account cursor、arrival order、
`created_at`、SignerEvidenceRef 或本地曾见同 EventId 都不能补出坐标；current entry 的 source coordinate 只证明
该 entry 自身来源，不外推给 value 内嵌 Event。

redacted／reference-locked row 即使暴露 EventId 或 Commit coordinate，也没有 producer envelope 可验，历史 signer
状态仍为 unresolved。缺 exact target coordinate 时 MAY 在已知 stream 上用正式 per-stream scan 回填；只有裸
EventId 时不得全 Realm 探测、按时间／cursor 猜 position，也不得降级成 `current_admission` query。缓存与耐久索引
必须以完整 target `committed_event_ref` 为键并保留独立 authorization ref/revision；重启、乱序 response 与迟到
的另一账号 response 都必须重新核对完整 selector 与 recipient context。

**调用语境不可丢（normative）**：`recipient_account_id` MUST 逐字等于已认证 SessionGrant 的完整账号，其
Station MUST 是服务本请求的自己 Station；结果 context MUST 逐字回显请求。current 结果只供**本次冻结的操作**
消费：同批或完全相同且已在途的查询 MAY 合并，但已完成的结果 MUST NOT 供未来操作或重连使用。稳定公钥
bytes MAY 缓存，但 `(actor, method, key)` MUST NOT 替代 exact authorization Event 实例——同一 key 的重新授权
必须按独立授权实例核对。

**`authorization_ref` 是必填（normative）**：所有 resolved 分支的 `query_signing_key` MUST 携带真实适用的
accepted 授权 Event 完整坐标、current revision 与 governance generation；历史 Agent 与普通设备没有例外。
缺失或无法取得时 MUST 返回同形且逐字回显完整 selector 的 `unavailable`，MUST NOT 把裸缓存公钥当作成功，
也 MUST NOT 用细分 reason 泄漏隐藏状态。

**不改动的两条边界（normative）**：Signal frame 没有 enclosing selector，继续使用完整
`station_signing_key {actor, verification_method, public_key_b64u, authorization_ref}` 的独立身份形态；
peer portable evidence 保持自己的独立来源合同，MUST 绑定本地接收方，其独立接纳时间 MUST NOT 混同原
producer 的 admission 时间。本节的收窄只作用于 self 查询结果，MUST NOT 被读作对这两者的放宽。

### 5.8 DID result

DID 解析证据可以作为 producer/service proof 验证输入，但不代表 Event 已提交。

### 5.9 Media result

Media 内容完整性由 blob ref 和 producer-signed 引用证明；可见性和接纳位置由 RealmCommit/current result 证明。
