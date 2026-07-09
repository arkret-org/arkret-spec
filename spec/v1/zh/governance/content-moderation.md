---
title: Moderation
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

去中心化协作协议不能仅依赖"好人不会来捣乱"的假设。协议必须提供标准化的**内容审核与用户管理**机制，包括：

- 用户举报不当内容
- 忽略/屏蔽其他用户
- Realm 级别的审核策略
- 组织级别的准入黑名单、允许列表和风险策略
- 服务器级别的访问控制

## 2. 设计原则

### 2.1 审核权由 Realm / Circle 管理员行使

去中心化环境中没有"全网管理员"。内容审核的权限由 Realm / Circle 的 Capability 体系决定：

- Realm-default 内容由持有 `ck.realm.moderation_policy` 或等价 Realm-scoped moderation grant 的 Actor 处理。
- Circle-scoped 内容由该 Circle 的管理员 / moderator 处理；Realm 管理员只有在 grant 明确覆盖目标 Circle 时才可以处理该 Circle 的举报。
- 普通用户举报不会触发合规审计、历史 key release 或外部审查方密钥访问。

### 2.2 屏蔽是本地行为

用户屏蔽另一个用户是纯本地的客户端行为，不需要广播到网络。协议不应强制"告诉全世界我屏蔽了谁"。

### 2.3 举报留痕但不公开

举报记录应被安全送达目标 `effective_scope` 的管理员 / moderator，但不应暴露给被举报人或其他普通成员。Circle 举报不得泄露给无权知道该 Circle 内容的 Realm 普通成员。

### 2.4 黑名单不是 capability grant

Arkret 的授权核心仍然是 allow-grant + explicit revoke。黑名单、过滤器和风险策略是额外的 deny/quarantine 层：

- 没有 capability 时，黑名单不能创建权限。
- 有 capability 时，Realm / Organization / Service policy MAY deny、quarantine 或 require review。
- 个人 block 只影响个人客户端体验，不能替 Realm 删除其他成员可见的事实。

### 2.5 Capability / Moderation / Personal Blocklist 三层判定

下图把动作从提交到呈现要穿过的三层 gate 画在一起。**Capability 是唯一的"能不能做"判定**，Moderation 只能在 capability 之上叠加 deny / quarantine / require_review，Personal Blocklist 完全是接收方本地行为。

```mermaid
flowchart TB
    Action["actor 提交动作<br>(写消息 / Move / grant / ...)"]

    Cap{"1. Capability<br>有 grant 且未 revoke<br>且 constraint 满足?"}
    Cap -- "否" --> DenyCap["拒绝 (missing_capability)<br>没有任何 deny 层能补救"]
    Cap -- "是" --> Mod{"2. Moderation Policy<br>(Realm / Organization / Service)"}

    Mod -- "deny / hard_deny" --> DenyMod["拒绝并写入<br>ck.component.moderation_state.v1<br>(sealed Move，跨 peer 一致)"]
    Mod -- "quarantine" --> Quar["事件进 quarantine 队列<br>不进 effective state<br>(sealed)"]
    Mod -- "require_review" --> Rev["进 review 队列<br>等待 moderator 决策"]
    Mod -- "allow" --> Stored["写入 Realm 历史<br>(canonical fact)"]

    Stored --> View{"3. 接收方个人 blocklist / mute"}
    View -- "命中" --> Hidden["本地 UI 隐藏 / 折叠<br>纯客户端，不影响其他成员视图"]
    View -- "未命中" --> Show["正常展示"]
```

读图要点：

- **Capability 是唯一 allow 来源**：黑名单 / moderation policy / personal blocklist 都不能凭空创造权限。
- **Moderation 决策 MUST sealed**（见 §2.6）：`hard_deny` / `quarantine` / `require_review` 必须通过 sealed Move 写入 `ck.component.moderation_state.v1` cell，避免不同 Principal Server 给出不一致判定导致跨 peer 视图分叉。
- **Personal Blocklist 不进 cell**：它只是接收方本地客户端 view 过滤，不广播、不共享、不替 Realm 删除其他人可见的事实。
- **Blocklist 不可枚举**：个人 block 命中不得向被屏蔽方或 federation peer 暴露为独立错误码、receipt 差异、presence / typing 差异或 directory 结果差异；对外表现必须与普通不可见、不可达或不存在一致。

### 2.6 Moderation 决策 MUST Sealed

任何会改变其他 peer 对事件可见性、可写性或可分发性判断的 moderation decision——即 `hard_deny`、`quarantine`、`require_review`——MUST 通过 sealed Move 写入 `ck.component.moderation_state.v1` cell，详细规则见 [`authz/policy-server.md` §7.1](../authz/policy-server.md)。Policy Server signed decision 与个人 blocklist 仍是 out-of-band，不进入该 cell。这避免不同 Principal Server 对同一事件做出不一致 quarantine / allow 决策导致跨 peer 视图分叉。

**确定性收敛与提交路径（normative）**：`ck.component.moderation_state.v1` 与 `ck.component.moderation.appeal.v1` 两类 cell 的确定性收敛由 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 注册的 lattice 定义，与 capability cell（[`authz/capabilities.md` §12.1](../authz/capabilities.md)）同型：`ck.moderation.decision` = 对 moderation_state cell 的 `or_set` **add**；`ck.moderation.decision.lift` = 对同一 cell 的 observed-remove / supersede（撤销被 lift 的 decision）；`ck.moderation.appeal.*` = appeal cell 上的 `fsm` 状态机（submitted → under_review → decided → closed）。裁决（`ck.moderation.decision[.lift]`）与申诉（`ck.moderation.appeal.*`）一律经 `POST /_cokret/self/events` 作为 self-authored Move 提交，**不经任何实现私有运维 / admin 写路径**；治理状态完全由数据/控制面 reducer 收敛，运维管理面不持有 moderation 真相。

## 3. 内容举报 (Report)

### 3.1 举报操作

用户可以举报自己可见的 Realm / Circle 对象（Message、Strand、Morph、Relation 等）：

```
POST /_cokret/self/moderation/report
```

请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `realm_id` | id | required | 被举报对象所在 Realm。 |
| `effective_scope` | object | optional | 举报目标的实际治理边界；缺省为 `{kind:"realm", realm_id}`。Circle 内容 MUST 填 `{kind:"circle", realm_id, circle_id}` 或由服务端从 target 解析得到。 |
| `target_ref` | id | required | 被举报 Object / Event 引用；若提交 Operation 引用，服务必须先映射到对应 `event_id`。 |
| `report_reason_code` | enum | required | 举报原因码，取值见 §3.2。 |
| `description` | string | optional；`report_reason_code=other` 时 required | 举报说明；服务端 MAY 限制长度。 |
| `reporter` | did | required | 举报人 DID，MUST 与认证 session / device proof 一致。 |
| `evidence_refs` | id[] | optional | 可见证据引用。 |
| `evidence_package` | object | optional | E2EE 或私有证据包；见 §3.4。 |
| `franking_proof` | object | optional | 密文投递证明；见 §3.4。 |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_id` | id | required | 举报记录 ID。 |
| `status` | enum | required | 举报处理状态；`moderation-queue-item` 的**权威生命周期枚举** `{ submitted, resolved }`（语义、转换与终态见 §3.3）。提交后为 `submitted`；实现 MUST NOT 返回该枚举之外的值。 |
| `routed_to` | did[] | optional | 该举报被路由 / 分诊到的 scoped moderator / 管理员 DID（若服务执行了路由则填充）。**治理拓扑保护（normative）**：实现 MUST NOT 向不持有 moderation / governance capability 的普通 reporter 暴露具体 moderator / 管理员 DID——否则反复对不同 scope 举报即可枚举 Circle / Realm 的完整 moderator/admin DID 集合。对普通 reporter，响应 MUST 省略 `routed_to` 或仅返回布尔"已路由"指示（如 `routed: true`），不得回退到 `SHOULD`——前句的 MUST NOT 暴露与本句的披露收口口径一致；完整 `routed_to` DID 列表 MUST 仅对本身持有 moderation / governance capability 的 caller 返回。 |

请求示例（非完整 schema）：

```json
{
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "effective_scope": {
    "kind": "circle",
    "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
    "circle_id": "ak:circle:01964200-0000-7000-8000-000000000001"
  },
  "target_ref": "ak:message:01964200-0000-7000-8000-000000000002",
  "report_reason_code": "harassment",
  "description": "This message contains targeted personal attacks.",
  "reporter": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com"
}
```

#### 3.1.1 举报入口反滥用约束（normative）

举报入口本身是可被滥用的写路径（举报洪水、超大 evidence_package 充塞、franking_proof 重放）。实现 MUST：

- 对 `/_cokret/self/moderation/report` 按 [`../security/server-threat-model.md` §4.1](../security/server-threat-model.md) 的入口与服务面规则施加**分层限速**（至少按 `reporter` DID、source service、`realm_id`、source IP hash、endpoint 维度），超阈值 MUST 返回 `rate_limited`；单 reporter 在单位时间窗口内对同一 `target_ref` 的重复举报 MUST 去重或抑制。
- 对 `evidence_package` 施加大小上界：其总字节数 MUST 受一个 `max_total_blob_bytes` 等价上界约束（命名遵循 [`../models/common-fields.md` §3.0.1](../models/common-fields.md)），超限 MUST 拒绝而非静默截断。
- 对 `franking_proof.replay_nonce` 的去重存储 MUST 有界：去重窗口 MUST 有限（时间或计数），过期 nonce MAY 被驱逐；实现 MUST NOT 假定无限去重存储，超出窗口的 nonce 复用按不可验证投递证明处理（见 §3.4）。
- **target scope 绑定（normative）**：服务端 MUST 从 `target_ref` 解析其真实治理边界 `(realm_id, effective_scope)`，并校验它等于请求声明的 `realm_id` / `effective_scope`；不一致时 MUST 拒绝。reporter 对 `target_ref` 在该 scope 内不可见时同样 MUST 拒绝(对齐 §3.3 "举报自己可见的对象")。为避免对象存在性 / Circle 隔离边界枚举，上述拒绝与"目标不存在"MUST 使用统一不透明失败形态(对齐 §2.5)。本校验与 §5.5.2 appeal 链的同 Realm 绑定校验同口径，防止以有权 Realm 的 `realm_id` 举报无权 Realm / Circle 内对象。

### 3.2 举报原因枚举

| Report reason code | 说明 |
|--------|------|
| `spam` | 垃圾信息 / 广告 |
| `harassment` | 骚扰 / 人身攻击 |
| `hate_speech` | 仇恨言论 |
| `nsfw` | 不适当的成人内容 |
| `illegal` | 违法内容 |
| `misinformation` | 虚假信息 |
| `other` | 其他原因（需要 `description` 补充说明） |

### 3.3 举报的处理

- 举报 service operation（`ck.self.moderation.command.report`）会物化 `ck.self.moderation.report` 事件，写入 Realm Event history；Circle 举报的 plaintext metadata 和 evidence audience MUST 按 `effective_scope.kind="circle"` 加密 / 限制。
- 该事件仅对目标 scope 的管理员 / moderator 可见；Realm-default 内容是 Realm moderator，Circle 内容是 Circle moderator 或显式覆盖该 Circle 的 Realm grant 持有者。
- 被举报人不会收到通知。
- 管理员可以基于举报决定后续行动（警告、删除内容、封禁用户等）。
- 举报不会授予 moderator 历史 key、epoch key、审计 applet release 权限或外部 verifier 权限。

**queue-item 生命周期(normative,`moderation-queue-item.schema.json` 与响应 `status` 的权威源)**:v1 刻意最小化为两态——

| 状态 | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `submitted` | 举报已受理，待处理 | `resolved` | 否 |
| `resolved` | 处理完成 | —(终态) | **是** |

- **处置结果**(是否违规、采取何种处置)**不进** `status`,由独立的 `ck.moderation.decision` 事件承载。
- **申诉**不改 queue-item,由独立的 `ck.moderation.appeal.*` 子系统(§5.5)按 `decision_ref` 维护。
- 如后续工作流需要中间相(如 triage / review 分阶段),MAY 在新修订中增补状态值;v1 实现 MUST NOT 产生这两值之外的 `status`。

### 3.4 E2EE 举报 Evidence Package 与 Franking

在 E2EE Realm / Circle 中，服务端无法读取正文。举报 E2EE 内容时，reporter MAY 提交一个加密 evidence package 给目标 scope 的 moderator；实现 SHOULD 支持 `franking_proof`，用于证明某条密文 envelope 曾被接收服务投递，而不保存明文。

Evidence package SHOULD 包含 reporter 自己可见并愿意提交的最小证据，例如：

- 被举报消息明文或必要 excerpt；
- 原始 encrypted envelope；
- plaintext / ciphertext / AAD digest；
- reporter 对 evidence package 的签名；
- 可选 `franking_proof`。

Evidence package MUST 加密给 `effective_scope` 对应 moderator audience。它 MUST NOT 包含 Realm / Circle 历史 key、MLS epoch secret、exporter secret 或允许 moderator 解密未举报消息的材料。

该最小披露闭包由 `ck.vector.moderation.evidence_package_minimal_disclosure.v1` 固化；实现 MUST 把 evidence package 的目标、加密 audience、reporter signature evidence 与禁止披露的 MLS epoch/history secrets 一并纳入校验。

推荐 franking proof 结构：

```json
{
  "kind": "ck.moderation.franking_proof",
  "franking_proof_id": "ak:franking_proof:0196425b-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:0196419b-0000-7000-8000-000000000000",
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "routing_metadata_digest": "sha256:...",
  "ciphertext_digest": "sha256:...",
  "aad_digest": "sha256:...",
  "sender_claim": {
    "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
    "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
    "mls_group_id_digest": "sha256:..."
  },
  "received_by": "did:webvh:z5a3yeFnKQFn6ZqPY1Qgv3RrZ:server.acme.example",
  "received_at": "2026-04-30T00:00:00Z",
  "replay_nonce": "base64url...",
  "signature": "base64url..."
}
```

规则：

- `franking_proof` MUST 在 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID、接收时间与 `replay_nonce` 之上生成。其中 canonical event routing metadata 的覆盖在 wire 上由必填字段 `routing_metadata_digest` 承载（见 [`moderation-report.schema.json`](../../artifacts/schemas/moderation-report.schema.json) `franking_proof.required`），验证方 MUST 据此核验该覆盖。
- 对 `encrypted-envelope.schema.json` 承载的 v1 消息，`franking_proof.ciphertext_digest` 的取值 MUST 等于被举报 `encrypted_content.payload_digest`：即 `sha256(canonical_json(payload_metadata) || base64url_decode(ciphertext))`（见 [`encryption-and-audit.md` §2.3.3](../crypto-media/encryption-and-audit.md#233-payload_digest-计算)）。实现 MUST NOT 接受或生成旧式嵌套 `digests.ciphertext` / `ciphertext_digest` envelope 字段。
- `franking_proof` MUST NOT 包含 plaintext body、attachment filename、reply excerpt、mention 列表、private handle 或解密后内容 hash。
- **群拓扑 / 时序元数据最小披露（normative）**：`sender_claim` MUST NOT 携带 raw `mls_group_id` 或明文 `epoch`。前者是群组身份、后者是 epoch 进度，均为元数据侧信道，向可能非该 E2EE 群成员的 moderator 披露会泄露群存在性与活跃 epoch 进度。需要把 sender claim 绑定到具体群上下文时，`mls_group_id` MUST 以不可逆 digest 形式（`mls_group_id_digest`，与 `routing_metadata_digest` 一致的 keyed/salted 或 plain digest 约定）出现；`epoch` MUST NOT 以明文整数出现于 `franking_proof`。
- **`received_by` / `received_at` 向非群成员 moderator 最小化（normative）**：franking 的 `received_by`（接收服务 DID）与 `received_at`（精确接收时间）以明文加密给 moderator，而 moderator 不必是该 E2EE 群成员。明文 `received_by` 暴露消息归属的 Principal Server（服务拓扑 / 可把用户关联回 home server），明文 `received_at` 暴露秒级活动 timing。因此当接收 moderator 不是该消息所在群 / Circle 成员时，`received_by` SHOULD 降级为接收服务 DID 的 digest 或仅证明"某授权投递服务接收过"（不暴露具体 service DID），`received_at` SHOULD bucket 化（与 discovery / presence 的 last_active bucket 同口径）而非秒级精确值。§3.4.1 不存在治理密钥释放所需的精确 `received_by` / `received_at` 校验仅在持有对应治理 capability 的验证路径内进行，不向普通 reporter / 非群 moderator 暴露精确值。
- `franking_proof` 只证明服务接收过对应密文事件；它不证明 reporter 提交的明文与密文一致，也不证明 sender 在群外不可抵赖地 authored 该明文。
- Moderator 验证时 MUST 检查 reporter 可见性、目标消息 accepted state、encrypted envelope digest、franking service signature、AAD / ciphertext digest 和 evidence package 签名。
- 若任一环节缺失，moderator MAY 把材料作为人工线索，但 MUST NOT 将 `franking_proof` 视为可验证投递证明。

#### 3.4.1 不存在治理密钥释放

Realm / Circle 治理举报没有独立审查方，也没有“为了举报给 moderator 获取 MLS key / exporter secret”的流程。实现 MUST NOT 把 `ck.self.moderation.command.report` 自动升级为 `ck.audit.session.request`，MUST NOT 因举报向 moderator、Policy Server、Sync Service 或外部 verifier release 历史 key / epoch key。

需要政府 / 企业合规审计时，必须走 [`../crypto-media/audited-e2ee.md`](../crypto-media/audited-e2ee.md) 定义的 Audit Applet Binding + sealed release session；这与用户举报是不同协议流程。

Franking 信任链：

1. 从 `franking_proof` 的 `received_by` 取得 receiving service DID。
2. 解析该 DID Document，并验证 `franking_proof.signature` 使用的 verification method 在 `received_at` 时有效且未撤销。
3. 验证该 service DID 在目标 Realm 的 policy / service binding 中被授权为 Sync、Federation、MIMI facade 或 moderation ingestion 服务。
4. 验证 DID service endpoint、HTTP Message Signature / federation binding 与实际接收服务一致，防止把其他服务签名重放到本 Realm。
5. 验证 `franking_proof` payload hash 覆盖 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID、received time 和 replay nonce。
6. **`received_at` 时序新鲜度（normative）**：本步使用的是验证路径内的**精确** `received_at`（即持有治理 capability 的释放/验证路径所见的精确值，见 §3.4 末段），**不是**向非群 moderator 展示的 bucket 化值；§3.4 的 bucket 化只面向展示层最小化，不削弱此处的时序校验精度。`received_at` 由 receiving service 自填，本身无外部时间锚；被攻陷服务可回填一个 key 仍有效的 `received_at`，让已撤销 key 的旧签名"看似有效"。因此验证方 MUST 执行下列其一：(a) 用一个可独立校验的时间锚（如 seal frontier / HLC，或绑定该 proof 的外部时间见证）约束 `received_at`；或 (b) 若 `received_at` 早于第 2 步 verification method 最近一次 rotation / 撤销且无独立时间见证，MUST 把该 franking proof 视为**不可验证投递证明**（与 §3.1.1 去重窗口外 nonce 复用按"不可验证"降级一致），不得仅凭 `received_at` 落在 key 有效期内即采信。

## 4. 用户屏蔽 (Ignore/Block)

### 4.1 屏蔽是 Actor-Private 状态

用户可以屏蔽任意 Actor，屏蔽列表存储在本地或用户的私有 account data 中。`ck.account.blocklist` 的**权威结构定义（entry 字段集、`version`、`entry_id`、`applies_to`、`target.kind` 取值与同步 / 隐私约束）在 [`../discovery/client-preferences.md` §3.5`](../discovery/client-preferences.md)**；本节不重复定义，仅引用，避免字段漂移。下例为最小说明性片段（完整必填字段与约束以 client-preferences §3.5 为准）：

```json
{
  "version": 1,
  "entries": [
    {
      "entry_id": "ak:block:019640b3-cc00-7000-8000-000000000000",
      "target": {
        "kind": "actor",
        "did": "did:webvh:zGMfBAbnRTYqW4943CVr9Dcii:spammer.example.com"
      },
      "mode": "block",
      "applies_to": ["messages", "mentions", "dm"],
      "reason_code": "harassment",
      "created_at": "2026-04-26T10:00:00Z",
      "expires_at": null
    }
  ]
}
```

### 4.2 屏蔽行为

客户端在渲染时：

- SHOULD 隐藏被屏蔽用户的消息
- SHOULD NOT 显示被屏蔽用户的 Typing 和 Presence 状态
- SHOULD NOT 为被屏蔽用户的消息生成通知
- SHOULD 默认拒绝被屏蔽用户发起的 DM、call invite、contact request 和 applet-mediated request
- MAY 在共同 Realm 中显示折叠占位符，避免破坏上下文
- MUST NOT 从网络层面丢弃被屏蔽用户的 Operation（这些 Operation 对其他成员仍然有效）

### 4.3 个人过滤对象

个人 blocklist MAY 包含：

- actor DID
- device DID / device id
- service DID
- handle
- domain
- organization DID
- Applet id
- keyword / mention pattern

对 handle、domain、organization DID 的屏蔽 MUST 在本地解析成可验证 DID / claim 后应用。客户端 MUST NOT 因裸字符串后缀误伤无关主体。

### 4.4 隐私要求

个人 blocklist 是 holder-private account data。实现 MUST NOT 默认上传明文 blocklist 到公共 Sync Service、Realm、Directory 或被屏蔽方可见的位置。

跨设备同步 SHOULD 使用加密 account data。服务端只应看到不透明密文。

## 5. Realm 审核工具

### 5.1 内容删除

管理员可以通过 `ck.message.redact` 操作撤回任意成员的消息：
- 需要 `ck.message.redact` capability（撤回他人消息的非 `.own` 形态；`ck.realm.moderation_policy` 仅管理审核策略事件本身，**不**隐含该撤回权，若要并入审核员 bundle 须在 grant 的 `actions[]` 中显式并列 `ck.message.redact`）
- 撤回会产生 tombstone，不可逆
- 审计视图中仍可看到撤回记录

### 5.2 用户封禁

管理员通过 `ck.member.state{membership="ban"}` Event 封禁用户（成员状态机详见 [`../models/realm-and-space.md` §2.7](../models/realm-and-space.md)，policy 对象详见 [`../models/governance-objects.md` §3](../models/governance-objects.md)）。封禁后：

- 被封禁用户无法重新加入该 Realm
- 其未来的 Operation 提交将被 Sync Service 拒绝
- 是否对其隐藏**已可见**历史内容由 Realm Policy 决定；但 ban 后的 **key share 与 server-mediated backfill MUST fail closed**，其 fail-closed 真相源为 [`history-visibility.md` §6](./history-visibility.md) 与 [`../crypto-media/device-lifecycle.md` §13.1](../crypto-media/device-lifecycle.md)（把"接收 principal / device 已处于 ban / leave / removed"列为主体级拒绝终态）。Realm policy 只能在此基础上**更严**，MUST NOT 放宽该 fail-closed 边界向被封禁主体继续交付 key / 历史。

### 5.3 Realm Blocklist / Filter Policy

Realm MAY 使用 `ck.realm.moderation_policy` state event 声明黑名单、允许列表、内容过滤和风险处理策略。

```json
{
  "kind": "ck.realm.moderation_policy",
  "payload": {
    "version": 1,
    "targets": [
      {
        "target": {
          "kind": "actor",
          "did": "did:webvh:zGMfBAbnRTYqW4943CVr9Dcii:spammer.example.com"
        },
        "action": "deny_join",
        "reason_code": "spam",
        "created_by": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example#mod",
        "created_at": "2026-04-26T00:00:00Z",
        "expires_at": null
      },
      {
        "target": {
          "kind": "domain",
          "domain": "malicious.example"
        },
        "action": "quarantine_message",
        "reason_code": "abuse_cluster"
      }
    ],
    "content_filters": [
      {
        "filter_id": "ak:filter:3655021a-cf20-7000-8000-000000000000",
        "match": {
          "kind": "url_domain",
          "pattern_digest": "sha256:..."
        },
        "action": "require_review"
      }
    ],
    "appeal": {
      "enabled": true,
      "endpoint": "ak:strand:56b39410-0000-7000-8000-000000000000"
    }
  }
}
```

`action` 取值：

- `deny_join`
- `deny_restricted_join`
- `deny_invite`
- `deny_write`
- `deny_federation`
- `quarantine_message`
- `require_review`
- `redact_on_accept`
- `shadow_collapse`

`target.kind` 取值至少包括：

| kind | 标识字段 | 语义 |
| --- | --- | --- |
| `actor` | `did` | 单个 Actor / Principal。 |
| `device` | `device_id` 或 `did` | 单个设备身份。 |
| `service_did` | `did` | 单个 Principal Server、Sync Service、Federation peer 或其他 service DID。 |
| `domain` | `domain`，可选 `match_subdomains` | 规范化 DNS A-label domain；只按 label 边界匹配。 |
| `trust_domain` | `trust_domain` | 部署级 trust domain。 |
| `organization` | `did` | Organization DID 或其签发的治理链。 |
| `claim_selector` | `claim_type` / `issuer` | 由声明、VC 或组织关系选择一组主体。 |
| `media_digest` | `digest` | 媒体或 blob 内容 digest。 |
| `content_label` | `label` | 分类器或审核标签。 |

Realm 级 server ACL 等价规则 MUST 使用 `service_did`、`domain` 或 `trust_domain` target 表达。`deny_write` / `deny_federation` 命中这些 target 时，接收方 MUST 拒绝该 peer 后续 service-to-service 写入、backfill push、完整 frontier probe 和默认 fanout；`quarantine_message` 命中时，事件不得进入普通用户可见视图，直到 sealed moderation decision 解除。`deny_join` 命中 server target 时，MUST 拒绝通过该 service DID 或 domain 发起的新 join / invite acceptance，但不会自动清扫已经 accepted 的成员；`deny_restricted_join` 只作用于 `default_join_rule=restricted` / `default_join_rule=knock_restricted` / `history_visibility=restricted` 或等价 restricted admission profile 的申请、knock、invite acceptance（术语以 [`join-policy.md` §4](./join-policy.md) 的 `default_join_rule` 枚举为准，`restricted` 与 `knock_restricted` 两值均落入本作用域），命中时 MUST fail closed，不得回退到普通 `deny_join` 之外的宽松路径。清扫既有成员必须通过 `ck.member.state{membership="ban"}`、grant revoke、MLS epoch rotation 或明确的 moderation decision 完成。

Domain target 的匹配必须基于已验证 service DID / DID Document endpoint / member delivery binding 的规范化结果。实现 MUST NOT 对未经验证的裸字符串、display name、handle 后缀或用户输入 URL 做后缀封禁推断。

规则：

- 修改 `ck.realm.moderation_policy` MUST 持有 `ck.realm.moderation_policy` 或 `ck.policy.manage` capability。
- Realm blocklist MUST 在 signature / DID 基础校验之后、事件进入用户可见 reducer 状态之前进行评估。
- `deny_join` / `deny_write` SHOULD 产出已签名的 moderation decision 或 audit record。
- `quarantine_message` MUST 在审核通过前阻止事件进入普通用户可见视图。
- 内容过滤 SHOULD 优先使用 hash、label 或本地分类；E2EE Realm MUST NOT 要求向服务端过滤器上传明文。
- Realm blocklist MUST NOT 静默覆盖密码学历史。要改变已 accepted 事件的呈现，需通过 redaction / tombstone / quarantine 事件实现。
- **`redact_on_accept` 的 redact capability 前提（normative）**：`redact_on_accept` 在 review / accept 阶段自动产生对目标消息的 redaction，等价于代表 policy 作者行使 `ck.message.redact`。与 §5.1 "`ck.realm.moderation_policy` 不隐含撤回他人消息的 `ck.message.redact` 权"口径一致：声明含 `redact_on_accept` action 的 `ck.realm.moderation_policy` 的 policy 作者 MUST 同时持有 `ck.message.redact` capability（撤回他人消息的非 `.own` 形态）。reducer 在接受携带 `redact_on_accept` 的 policy 写入、以及在 accept 阶段执行该自动 redaction 时 MUST 校验该 capability；policy 作者不持有时 MUST 拒绝该 action（`capability_denied`），不得仅凭 `ck.realm.moderation_policy` 隐式获得 redact 权。

### 5.4 消息审核队列

Realm SHOULD 支持审核队列 (Moderation Queue) 视图，汇集所有举报记录。建议使用标准 View 机制：

```json
{
  "kind": "collection",
  "renderer": "list",
  "query": {
    "facets": ["reviewable"],
    "filters": [
      { "field": "fields.status", "op": "eq", "value": "submitted" }
    ]
  },
  "collection": {
    "item_facets": ["reviewable"],
    "item_render": "row",
    "item_order_by": [
      { "field": "fields.priority", "direction": "desc" },
      { "field": "created_at", "direction": "asc" }
    ],
    "grouping": {
      "mode": "field",
      "field": "fields.status",
      "lanes": [
        { "key": "submitted", "title": "Submitted" }
      ],
      "hidden_count_policy": "omit"
    }
  }
}
```

### 5.5 上诉流程 (Appeal Strand, normative)

上诉是审核闭环的反向通道。被 `ck.moderation.decision` 影响的 target（成员被 ban、消息被 remove、Strand 被锁等）可以走标准 `ck.moderation.appeal.*` 事件链请求复核，无需脱离 Arkret wire。本节定义事件链、状态机与 reducer 强制约束。

#### 5.5.1 事件链

四个 active event kind（见 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json)）：

| Event kind | 触发者 | 目标 cell 状态转换 | capability |
| --- | --- | --- | --- |
| `ck.moderation.appeal.submit` | appellant（被影响 target 的控制者或 policy 列出的 advocate） | (none) → `submitted` | `ck.moderation.appeal.submit`（risk_tier=low） |
| `ck.moderation.appeal.review` | reviewer（不得是原 decision 的 issuer） | `submitted` → `under_review` | `ck.moderation.appeal.review`（risk_tier=medium） |
| `ck.moderation.appeal.decision` | reviewer（同上） | `under_review` → `decided` | （复用 `ck.moderation.appeal.review`，见表注） |
| `ck.moderation.appeal.close` | reviewer（手动）、appellant（撤回）或部署的授权关闭服务（见 §5.5.2 close 是手动 / 授权动作） | `decided` → `closed`；`submitted` / `under_review` → `closed` 仅限 appellant withdraw | （复用 `ck.moderation.appeal.review`，appellant withdraw 例外见 §5.5.2） |

> 表注（capability 复用）：`.decision` 与 `.close` 是 `ck.moderation.appeal.review` capability action 的目标 event kind，**有意复用同一 review capability**——见 [`capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中 `ck.moderation.appeal.review`（`event_mapping_kind=aggregate_admin`，`target_event_kinds` 含 `review` / `decision` / `close` 三者）。因此 `.decision` / `.close` 行不另列独立 capability，其 `risk_tier` **继承自 `ck.moderation.appeal.review` 的 `medium`**；它们不是独立 capability action，registry 也不为其登记单独 action。`separation of duties`（reviewer ≠ 原 decision issuer）由 §5.5.2 reducer 约束兜底，弥补共用 capability 带来的影响差。
> 表注（submit 授权）：Realm member 作为被影响 target 的 appellant 提交 `ck.moderation.appeal.submit` 属于 baseline membership 权限；非成员 advocate 只有在 Realm policy / `ck.moderation.appeal.submit` capability 授权时 MAY 代表 appellant 提交。

Payload schema 在 [`moderation-appeal.schema.json`](../../artifacts/schemas/moderation-appeal.schema.json)（schema id `ck.schema.moderation_appeal.v1`，四种 payload 通过 `oneOf` 分支）。

##### 5.5.1.1 `verdict` 封闭枚举（normative）

`ck.moderation.appeal.decision` 的 `verdict` 字段是**封闭枚举**，权威取值集合为 `{ uphold, overturn, modify }`（与 [`moderation-appeal.schema.json`](../../artifacts/schemas/moderation-appeal.schema.json) `decision_payload.verdict.enum` 完全一致）。取未列值时 reducer MUST 用 `schema_violation` 拒绝。各值语义与后续动作如下：

| `verdict` | 含义 | 后续动作（normative） |
| --- | --- | --- |
| `uphold` | **驳回上诉**：原 `ck.moderation.decision` 维持生效，无进一步动作。这是最常见结局。 | 不得携带 `modify_decision_ref`（schema `if/then` 强制）；不产生 lift / 新 decision；cell 转入 `decided`。 |
| `overturn` | **撤销原 decision**：上诉胜诉，原处置被完全反转。 | MUST 与一条 `ck.moderation.decision.lift`（target 等于 `decision_ref`）在同一 ordered submit batch 或等价控制事务中出现，否则 reducer 用 `appeal_overturn_missing_lift` 拒绝（见 §5.5.2）。 |
| `modify` | **调整原 decision**：处置参数被修订（如缩短 ban 时长、降级处置）。 | MUST 与一条新的 `ck.moderation.decision` 在同一 batch 出现，并由 `modify_decision_ref` 指向它（见 §5.5.2）。 |

#### 5.5.2 Reducer 强制约束

- **Realm 绑定**：所有 `ck.moderation.appeal.*` payload MUST 携带 `realm_id`，且该值 MUST 等于 enclosing Event 的 `realm_id`。Reducer 还 MUST 解析 `decision_ref`，确认它引用同一 Realm 的 `ck.moderation.decision`；若 target / decision 属于另一 Realm，除非显式 cross-Realm moderation profile 授权，否则 MUST `schema_violation` 或 `capability_denied`。
- **separation of duties**：`ck.moderation.appeal.review` / `ck.moderation.appeal.decision` 的 `reviewer` MUST NOT 等于被上诉 `decision_ref` 对应 `ck.moderation.decision` event 的 issuer。违反时 reducer 用 `appeal_self_review_forbidden` 拒绝。
- **overturn 与 lift 原子**：`ck.moderation.appeal.decision` `verdict=overturn` MUST 与一条 `ck.moderation.decision.lift`（target 等于 `decision_ref`）在同一 ordered submit batch 或等价控制事务中出现；否则 reducer 用 `appeal_overturn_missing_lift` 拒绝。这关闭"上诉胜诉但原 decision 仍生效"的窗口。
- **modify 与新 decision 原子**：`verdict=modify` MUST 与一条新的 `ck.moderation.decision`（其 `target_ref` 等于原 target）在同一 batch 中出现。`modify_decision_ref` 是 `ck.moderation.appeal.decision` payload 上的字段（不是新 decision 上的字段），其值 MUST 指向同 batch 内该新 decision event 的 id；reducer 校验 `modify_decision_ref` 与同 batch 新 decision 的 event id 一致。
- **重复 submit 幂等约束**：同一 `(decision_ref, appellant)` 在其 appeal cell 处于**非 `closed`** 状态时不得再次 submit；违反时 `failed_precondition`。这是与时长无关的幂等约束（同一 appellant 对同一 decision 不得并存多个未结上诉）。cell 进入 `closed` 后允许新 `appeal_id`。重复 submit 的**时长级限流**（冷静期）不在协议层规定，由部署 / Realm policy 自行决定，协议不规定任何具体时长。
- **appellant withdraw**：cell 处于 `submitted` 或 `under_review` 时，`appellant` 本人 MAY emit `ck.moderation.appeal.close`，并把 payload 字段 `close_reason` 设为 enum 值 `appellant_withdrawn`，从而把 appeal 直接转为 `closed`。Reducer MUST 校验 `closer == appellant`，且不得要求 reviewer capability；该路径不得隐式改变原 moderation decision。
- **close 是手动 / 授权动作**：`ck.moderation.appeal.close` 由 reviewer / 部署授权关闭服务在 appeal 已 `decided` 后主动关闭，或由 appellant withdraw 提前触发(见上一条)。协议层不规定任何自动关闭定时器、超时时长或 timer-service DID。部署若需要"非活跃自动关闭"，自行实现产品服务，在 appeal 已 `decided` 后经正常授权通道(reviewer / 部署的授权关闭服务的 capability)提交 `ck.moderation.appeal.close`；未 `decided` 的提前 close 只允许 appellant withdrawal。该 close payload MUST 携带 `closer`，reducer 按常规 capability gate 校验 `closer` 是否有权关闭。

#### 5.5.3 审计与可见性

- 全部四个 event 进入 moderation audit log（durable_event），同时受 moderation / appeal policy 的 evidence visibility 控制可见范围；它们不触发 Audit Applet release。
- `evidence_visibility`（submit payload 字段）控制 reason text / evidence_refs 的明文可见范围（`appellant_only` / `reviewers_only` / `realm_admins` / `realm_members`），默认 `reviewers_only`。这只影响明文 audience，不改变 wire envelope 加密。
- 与 §10 v1 流程要求一致：appeal 流程"形成可审计事件"现在由这四个事件原生承担，不再需要平台外通道。

#### 5.5.4 与 `moderation_policy.appeal.endpoint` 的关系

§5.3 `moderation_policy` 中 `appeal.endpoint` 字段保留用于 UI 引导（用户在哪个 Strand 提交上诉），不替代 wire 事件。endpoint Strand 内的消息只是 narrative，约束性 verdict / lift 仍走本节 normative 事件链。

## 6. 服务器级访问控制

### 6.1 本地部署 ACL 与 Realm ACL 的边界

Principal Server 可以配置本地服务器级 ACL，控制哪些 peer 的联邦请求被接受、拒绝或停止 fanout：

```json
{
  "server_acl": {
    "allow": ["*"],
    "deny": [
      "spam-node.example.com",
      "*.malicious.example.net"
    ]
  }
}
```

该 `server_acl` 是部署本地 policy 名称，不是标准 Event kind，不进入 `event-kind-registry.json`，也不是可复制的 Realm 状态。实现 MUST NOT 接受 `ck.realm.server_acl`、`ck.server.acl` 或等价未注册 kind 作为 Realm 权威状态。

规则评估顺序：先检查 `deny` 列表，再检查 `allow` 列表。支持 glob 通配符时，通配符只允许覆盖完整 DNS label；`*.example.com` 不得匹配 `example.com` 或 `badexample.com`。推荐实现同时支持 exact `service_did`、`trust_domain` 与 DNS domain 规则，并优先使用已验证 service DID。

### 6.2 Realm 级 server ACL 的权威路径

需要让参与该 Realm 的 peer 以可验证、可复制方式看到 server ACL 时，MUST 使用已注册的 `ck.realm.moderation_policy`：

```json
{
  "kind": "ck.realm.moderation_policy",
  "payload": {
    "value": {
      "version": 1,
      "targets": [
        {
          "target": {
            "kind": "service_did",
            "did": "did:webvh:z5GPnjxXzWM85J3Kw6iMV4Tj2:spam-node.example"
          },
          "action": "deny_federation",
          "reason_code": "abuse_network"
        },
        {
          "target": {
            "kind": "domain",
            "domain": "malicious.example.net",
            "match_subdomains": true
          },
          "action": "deny_write",
          "reason_code": "abuse_network"
        }
      ]
    }
  }
}
```

> `targets[]` 条目的 `target` / `action` / `reason_code` 为核心字段，`created_by` / `created_at` / `expires_at` 为可选 audit 字段（取值与 §5.3 一致）；本节示例为聚焦 server ACL 而省略可选 audit 字段，并非表示其不可携带。完整字段集合与必填性以 [`moderation-report.schema.json`](../../artifacts/schemas/moderation-report.schema.json) 对应定义为准。

`ck.realm.moderation_policy` server target 的生效规则：

- 接收方在完成请求签名、DID、trust domain 和 endpoint digest 识别后，MUST 在接受 Event 进入普通 reducer 前评估 Realm policy。
- 命中 `deny_federation` 或 `deny_write` 的入站 service-to-service 写入 MUST fail closed；批量请求中可逐项拒绝，也可在请求级拒绝，取决于被拒绝规则是否影响整批认证上下文。
- 命中出站 deny 的 peer MUST 从该 Realm 的 fanout 目标集中移除；该抑制不是临时网络失败，不应进入无限重试队列。
- 命中 `quarantine_message` 的 Event MUST 进入 quarantine，不得作为 accepted state 推进普通用户可见 frontier。
- 这些规则只影响未来接收、投递和呈现。它们 MUST NOT 静默改写、删除或重新解释已经 accepted 的密码学历史。

### 6.3 与联邦协议的关系

Server ACL 在联邦层（参见 [`../sync/federation.md`](../sync/federation.md) §3.4）起作用。当 Principal Server 收到来自被 deny 的 peer 的 `ck.peer.events.command.submit`（`/_cokret/peer/events`，`Source-Service-DID`、source trust domain 或已验证 endpoint domain 命中 deny list）请求时，MUST fail closed，SHOULD 返回 `403 policy_denied` 或 `403 capability_denied`，并保持错误最小披露。

整机级 defederation 需要入站与出站同时配置：拒收该 peer 的 push / pull / frontier probe，并停止向其 fanout 新 Event、push、to-device、key-package、backfill 和媒体 / snapshot fetch。

## 7. 组织级审核策略

Organization MAY 为其控制或背书的 Realm 与服务发布组织级审核策略。该策略仅通过显式引用生效，不会隐式继承、自动级联或作为全局默认策略适用。

推荐对象：

```json
{
  "kind": "ck.organization.moderation_policy",
  "organization_did": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example",
  "policy_id": "ak:org-policy:abuse-v1",
  "policy_scope": {
    "realm_ids": ["ak:realm:01964280-0000-7000-8000-000000000000"],
    "service_dids": [
      "did:webvh:z5a3yeFnKQFn6ZqPY1Qgv3RrZ:server.acme.example",
      "did:webvh:z9hEFwrg1A6sjcDxhuzWJGKhe:policy.acme.example"
    ],
    "applies_to_owned_realms": true
  },
  "rules": [
    {
      "target": {
        "kind": "organization",
        "did": "did:webvh:z6zPnbtvkN7vxa9zUyCgGyX52:known-abuse.example"
      },
      "action": "deny_federation",
      "reason_code": "abuse_network"
    },
    {
      "target": {
        "kind": "claim_selector",
        "claim_type": "org_membership",
        "issuer": "did:webvh:zCJLLNnZDTQJWQp7tztodmPUc:untrusted.example"
      },
      "action": "deny_restricted_join"
    }
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example#governance-key-1",
    "jws": "..."
  }
}
```

规则：

- 组织策略只对显式引用它的 Realm / 服务有权威；对官方 Realm 也仅当其 `ck.realm.organization` 背书声明组织策略适用时才生效。
- 仅当组织策略允许覆盖时，Realm MAY 覆盖组织默认值。
- 组织级 deny SHOULD 由 Policy Server、Principal Server ACL、Directory 过滤与 Realm moderation policy 共同执行。
- 组织策略 MUST 由 Organization DID 或受授权的 governance service DID 签名。
- 组织策略 MUST NOT 暴露用户私有 blocklist、私有 handle 或未披露的组织成员关系。

## 8. Policy Server 集成

Realm 与 Organization 的审核策略 SHOULD 通过 Policy Server 进行动态评估，覆盖以下场景：

- invite / join request
- knock request
- message create / edit
- media upload
- Applet transaction
- federation transaction
- directory listing
- call invite

Policy Server MAY 返回 `hard_deny`、`quarantine`、`require_review` 或 `soft_deny`，但 MUST NOT 自行授予 capability。

### 8.1 Decision verb 与 §5.3 policy action 家族映射

本文存在两套相关但不同前缀 / 粒度的词汇，易混淆，这里统一登记其关系。**Decision verb**（§2.5 判定流程图与 §8 Policy Server 返回值）是 *runtime 判定结果*，集合为 `allow` / `soft_deny` / `hard_deny` / `quarantine` / `require_review`（全小写、无 `deny_` 前缀）。**§5.3 `moderation_policy` action 家族**是 *持久化 Realm policy 规则的 effect*，集合为 `deny_join` / `deny_restricted_join` / `deny_invite` / `deny_write` / `deny_federation` / `quarantine_message` / `require_review` / `redact_on_accept` / `shadow_collapse`（`deny_*` 前缀 + 作用对象后缀）。二者映射：

| Decision verb（runtime） | 对应 §5.3 policy action 家族 | 说明 |
| --- | --- | --- |
| `allow` | （无对应 deny action） | 放行，写入 canonical 历史。 |
| `hard_deny` | `deny_join` / `deny_restricted_join` / `deny_invite` / `deny_write` / `deny_federation` 中按动作类型取一 | `deny_*` 是 hard_deny 按被拒动作维度的细分；命中即 fail closed。 |
| `soft_deny` | （无持久化 action；仅 runtime 降级 / 限流上下文，常与 `rate_limit` obligation 同用） | 不写入 `moderation_state` cell。 |
| `quarantine` | `quarantine_message` | 事件进 quarantine，不进 effective state。 |
| `require_review` | `require_review` | 同名；进 review 队列。 |

`redact_on_accept` / `shadow_collapse` 是 §5.3 特有的后处理 effect，不由 decision verb 直接表达；它们在 review / accept 阶段叠加，不属于上表的一对一 runtime verb。大小写约定：decision verb 与 policy action **均为全小写 snake_case**，实现 MUST NOT 引入大写或驼峰变体。

## 9. 服务端威胁借鉴

在“去中心化服务治理”场景中，服务端常见风险的抗滥用经验如下：

- **入口源身份强制**：任何外部服务联邦请求都先验 `service DID`。未签名或未被 allowlist 的源服务不得参与写路径（至少转入 `soft_deny` / `quarantine`）。
- **多级限速**：Sync Service / Policy Server 和受托 search / projection 服务应至少按以下维度限速：`source DID`、`source IP`（或其哈希）、`service token`、`realm id`、`endpoint`。超阈值 MUST 返回 `rate_limited`。
- **批量事件反滥用**：对短周期内的 `invite`、`join`、`message`、`media.upload` 进行突发抑制；出现异常突发可触发 `quarantine`。
- **最小可观察性差异**：对未通过鉴权的目录/加入枚举请求，返回统一错误，不泄露对象可见性差异。
- **可疑媒体隔离**：媒体 hash、MIME、扫描标签先入审计与审核，不应默认解密给 Sync Service 或受托 projection；必要时按 `snapshot`/`preview` 再二次放行。
- **可追溯审计**：每次风控拦截、隔离、降级决策都要记录结构化审计事件，且不得仅依赖联邦来源的本地口头说明。

上述抗滥用规则的威胁映射见 [`../security/server-threat-model.md`](../security/server-threat-model.md)；其在授权与联邦层的 normative enforcement 分别见 [`../authz/policy-server.md`](../authz/policy-server.md) 与 [`../sync/federation.md`](../sync/federation.md)。本节为借鉴性概览，约束力以上述文件的 normative 条款为准。

## 10. v1 流程要求

- 自动化审核只能产生 risk signal、`quarantine` 或 `require_review` 建议；除非 Realm policy 明确授权，AI 分类器不得直接 hard delete、ban 或扩大可见性。
- 上诉流程 MUST 形成可审计事件，至少包含 target、moderation action、appeal actor、reviewer、decision、reason code 和时间；上诉材料的明文可见范围必须受 policy 控制。v1 中该要求由 §5.5 的 normative 事件链原生承担：appeal MUST 走 `ck.moderation.appeal.submit` / `.review` / `.decision` / `.close` 四个 active event kind（见 §5.5.1），不再需要平台外通道。
- 跨 Realm 共享封禁列表必须由 Organization DID、联盟治理 DID 或受信 issuer 签名，并声明 scope、reason code、evidence hash、过期时间和误伤申诉入口。默认不得把个人 blocklist 发布为共享封禁。
- 审核操作 MUST 使用不可抵赖日志：moderator DID、device/service proof、policy version、target event hash、action、reason code 和 audit timestamp 都必须进入签名记录。
