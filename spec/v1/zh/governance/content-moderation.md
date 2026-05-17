---
title: Moderation
---

## 1. 目标

去中心化协作协议不能仅依赖"好人不会来捣乱"的假设。协议必须提供标准化的**内容审核与用户管理**机制，包括：

- 用户举报不当内容
- 忽略/屏蔽其他用户
- Space 级别的审核策略
- 组织级别的准入黑名单、允许列表和风险策略
- 服务器级别的访问控制

## 2. 设计原则

### 2.1 审核权由 Space Owner 行使

去中心化环境中没有"全网管理员"。内容审核的权限由 Space 的 Capability 体系决定。只有拥有 `cx.space.moderate` 权限的 Actor 才能执行审核操作。

### 2.2 屏蔽是本地行为

用户屏蔽另一个用户是纯本地的客户端行为，不需要广播到网络。协议不应强制"告诉全世界我屏蔽了谁"。

### 2.3 举报留痕但不公开

举报记录应被安全送达 Space 管理员，但不应暴露给被举报人或其他普通成员。

### 2.4 黑名单不是 capability grant

Contrix 的授权核心仍然是 allow-grant + explicit revoke。黑名单、过滤器和风险策略是额外的 deny/quarantine 层：

- 没有 capability 时，黑名单不能创建权限。
- 有 capability 时，Space / Organization / Service policy MAY deny、quarantine 或 require review。
- 个人 block 只影响个人客户端体验，不能替 Space 删除其他成员可见的事实。

### 2.5.0 Capability / Moderation / Personal Blocklist 三层判定

下图把动作从提交到呈现要穿过的三层 gate 画在一起。**Capability 是唯一的"能不能做"判定**，Moderation 只能在 capability 之上叠加 deny / quarantine / require_review，Personal Blocklist 完全是接收方本地行为。

```mermaid
flowchart TB
    Action["actor 提交动作<br>(写消息 / Move / grant / ...)"]

    Cap{"1. Capability<br>有 grant 且未 revoke<br>且 constraint 满足?"}
    Cap -- "否" --> DenyCap["拒绝 (missing_capability)<br>没有任何 deny 层能补救"]
    Cap -- "是" --> Mod{"2. Moderation Policy<br>(Space / Organization / Service)"}

    Mod -- "deny / hard_deny" --> DenyMod["拒绝并写入<br>cx.component.moderation_state.v1<br>(anchored Move，跨 peer 一致)"]
    Mod -- "quarantine" --> Quar["事件进 quarantine 队列<br>不进 effective state<br>(anchored)"]
    Mod -- "require_review" --> Rev["进 review 队列<br>等待 moderator 决策"]
    Mod -- "allow" --> Stored["写入 Space 历史<br>(canonical fact)"]

    Stored --> View{"3. 接收方个人 blocklist / mute"}
    View -- "命中" --> Hidden["本地 UI 隐藏 / 折叠<br>纯客户端，不影响其他成员视图"]
    View -- "未命中" --> Show["正常展示"]
```

读图要点：

- **Capability 是唯一 allow 来源**：黑名单 / moderation policy / personal blocklist 都不能凭空创造权限。
- **Moderation 决策 MUST anchored**（见 §2.5）：`hard_deny` / `quarantine` / `require_review` 必须通过 anchored Move 写入 `cx.component.moderation_state.v1` cell，避免不同 Principal Server 给出不一致判定导致跨 peer 视图分叉。
- **Personal Blocklist 不进 cell**：它只是接收方本地客户端 view 过滤，不广播、不共享、不替 Space 删除其他人可见的事实。

### 2.5 Moderation 决策 MUST Anchored

任何会改变其他 peer 对事件可见性、可写性或可分发性判断的 moderation decision——即 `hard_deny`、`quarantine`、`require_review`——MUST 通过 anchored Move 写入 `cx.component.moderation_state.v1` cell，详细规则见 [`authz/policy-server.md` §7.1](../authz/policy-server.md)。Policy server signed decision 与个人 blocklist 仍是 out-of-band，不进入该 cell。这避免不同 Principal Server 对同一事件做出不一致 quarantine / allow 决策导致跨 peer 视图分叉。

## 3. 内容举报 (Report)

### 3.1 举报操作

用户可以举报 Space 中的任何可见对象（Message、Flow、Morph、Relation 等）：

```
POST /api/v1/moderation/report
```

请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
|------|------|------|------|
| `space_id` | id | required | 被举报对象所在 Space。 |
| `target_ref` | id | required | 被举报 Object / Event 引用；若提交 Operation 引用，服务必须先映射到对应 `event_id`。 |
| `reason` | enum | required | 举报原因，取值见 3.2。 |
| `description` | string | optional；`reason=other` 时 required | 举报说明；服务端 MAY 限制长度。 |
| `reporter` | did | required | 举报人 DID，MUST 与认证 session / device proof 一致。 |
| `evidence_refs` | id[] | optional | 可见证据引用。 |

响应字段：

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `report_id` | id | required | 举报记录 ID。 |
| `status` | string | required | 初始处理状态，例如 `submitted`。 |
| `routed_to` | did[] | optional | 被路由到的审核服务或 moderator DID。 |

请求示例（非完整 schema）：

```json
{
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "target_ref": "cx:message:01964200-0000-7000-8000-000000000002",
  "reason": "harassment",
  "description": "This message contains targeted personal attacks.",
  "reporter": "did:web:alice.example.com"
}
```

### 3.2 举报原因枚举

| Reason | 说明 |
|--------|------|
| `spam` | 垃圾信息 / 广告 |
| `harassment` | 骚扰 / 人身攻击 |
| `hate_speech` | 仇恨言论 |
| `nsfw` | 不适当的成人内容 |
| `illegal` | 违法内容 |
| `misinformation` | 虚假信息 |
| `other` | 其他原因（需要 `description` 补充说明） |

### 3.3 举报的处理

- 举报会生成一个 `cx.moderation.report` 事件，写入 Space Event history
- 该事件仅对拥有 `cx.space.moderate` 权限的 Actor 可见
- 被举报人不会收到通知
- 管理员可以基于举报决定后续行动（警告、删除内容、封禁用户等）

### 3.4 E2EE 举报 Franking

在 E2EE Space 中，服务端无法读取正文，但审核方仍需要验证“被举报明文确实对应某条已投递消息”。实现 SHOULD 支持 message franking：服务在接收密文事件时生成不可伪造的收讫证明，而不保存明文。

推荐 frank 结构：

```json
{
  "kind": "cx.moderation.frank",
  "frank_id": "cx:frank:0196425b-0000-7000-8000-000000000000",
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
  "ciphertext_digest": "sha256:...",
  "aad_digest": "sha256:...",
  "sender_claim": {
    "actor_id": "did:web:alice.example.com",
    "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
    "mls_group_id": "base64url...",
    "epoch": 42
  },
  "received_by": "did:web:server.acme.example",
  "received_at": "2026-04-30T00:00:00Z",
  "signature": "base64url..."
}
```

规则：

- Frank MUST 在 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID 与接收时间之上生成。
- Frank MUST NOT 包含 plaintext body、attachment filename、reply excerpt、mention 列表、private handle 或解密后内容 hash，除非 Space policy 明确允许该字段。
- 接收方客户端在解密消息后 SHOULD 保存 frank 与明文的本地绑定证明；该绑定默认只在本地或 E2EE 私有报告中保存。
- 举报 E2EE 内容时，`cx.moderation.report` MAY 携带 `plaintext_evidence` 的加密副本、原始 encrypted envelope、frank 和 reporter 对明文/evidence package 的签名。
- 审核方验证时 MUST 检查：frank 服务签名、event/ciphertext/AAD digest、reporter 提交明文重新加密或解密验证结果、目标消息的 accepted state、sender identity / pseudonym link 和 reporter 可见性。
- Frank 只证明服务接收过对应密文事件，不单独证明明文含义。审核决定仍必须落成 signed moderation decision，并受 Space policy、capability 和 appeal 规则约束。

Franking 信任链：

1. 从 frank 的 `received_by` 取得 receiving service DID。
2. 解析该 DID Document，并验证 frank `signature` 使用的 verification method 在 `received_at` 时有效且未撤销。
3. 验证该 service DID 在目标 Space 的 policy / service binding 中被授权为 Sync、Federation、MIMI facade 或 moderation ingestion 服务。
4. 验证 DID service endpoint、HTTP Message Signature / federation binding 与实际接收服务一致，防止把其他服务签名重放到本 Space。
5. 验证 frank payload hash 覆盖 canonical event routing metadata、ciphertext digest、AAD digest、sender claim、receiving service DID、received time 和 replay nonce。
6. 若任一环节缺失，审核方 MAY 接收举报材料作人工线索，但 MUST NOT 将 frank 视为可验证投递证明。

## 4. 用户屏蔽 (Ignore/Block)

### 4.1 屏蔽是 Actor-Private 状态

用户可以屏蔽任意 Actor，屏蔽列表存储在本地或用户的私有 account data 中：

```json
{
  "kind": "cx.account.blocklist",
  "owner": "did:web:alice.example.com",
  "entries": [
    {
      "target": {
        "kind": "actor",
        "did": "did:web:spammer.example.com"
      },
      "mode": "block",
      "created_at": "2026-04-26T10:00:00Z",
      "reason_code": "harassment",
      "expires_at": null
    }
  ]
}
```

### 4.2 屏蔽行为

客户端在渲染时：

- SHOULD 隐藏被屏蔽用户的消息
- SHOULD 不显示被屏蔽用户的 Typing 和 Presence 状态
- SHOULD 不为被屏蔽用户的消息生成通知
- SHOULD 默认拒绝被屏蔽用户发起的 DM、call invite、contact request 和 applet-mediated request
- MAY 在共同 Space 中显示折叠占位符，避免破坏上下文
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

个人 blocklist 是 holder-private account data。实现 MUST NOT 默认上传明文 blocklist 到公共 Sync Service、Space、Directory 或被屏蔽方可见的位置。

跨设备同步 SHOULD 使用加密 account data。服务端只应看到不透明密文。

## 5. Space 审核工具

### 5.1 内容删除

管理员可以通过 `cx.message.redact` 操作撤回任意成员的消息：
- 需要 `cx.space.moderate` 权限
- 撤回会产生 tombstone，不可逆
- 审计视图中仍可看到撤回记录

### 5.2 用户封禁

管理员通过 `cx.member.state{membership="ban"}` Event 封禁用户（成员状态机详见 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)，policy 对象详见 [`../models/governance-objects.md` §3](../models/governance-objects.md)）。封禁后：

- 被封禁用户无法重新加入该 Space
- 其未来的 Operation 提交将被 Sync Service 拒绝
- 是否隐藏其历史内容由 Space Policy 决定

### 5.3 Space Blocklist / Filter Policy

Space MAY 使用 `cx.space.moderation_policy` state event 声明黑名单、允许列表、内容过滤和风险处理策略。

```json
{
  "kind": "cx.space.moderation_policy",
  "payload": {
    "version": 1,
    "targets": [
      {
        "target": {
          "kind": "actor",
          "did": "did:web:spammer.example.com"
        },
        "action": "deny_join",
        "reason_code": "spam",
        "created_by": "did:web:acme.example#mod",
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
        "filter_id": "cx:filter:3655021a-cf20-7000-8000-000000000000",
        "match": {
          "kind": "url_domain",
          "pattern_hash": "sha256:..."
        },
        "action": "require_review"
      }
    ],
    "appeal": {
      "enabled": true,
      "endpoint": "cx:flow:56b39410-0000-7000-8000-000000000000"
    }
  }
}
```

`action` 取值：

- `deny_join`
- `deny_invite`
- `deny_write`
- `quarantine_message`
- `require_review`
- `redact_on_accept`
- `shadow_collapse`

规则：

- 修改 `cx.space.moderation_policy` MUST 持有 `cx.space.moderate` 或 `cx.policy.manage` capability。
- Space blocklist MUST 在 signature / DID 基础校验之后、事件进入用户可见 reducer 状态之前进行评估。
- `deny_join` / `deny_write` SHOULD 产出已签名的 moderation decision 或 audit record。
- `quarantine_message` MUST 在审核通过前阻止事件进入普通用户可见视图。
- 内容过滤 SHOULD 优先使用 hash、label 或本地分类；E2EE Space MUST NOT 要求向服务端过滤器上传明文。
- Space blocklist MUST NOT 静默覆盖密码学历史。要改变已 accepted 事件的呈现，需通过 redaction / tombstone / quarantine 事件实现。

### 5.4 消息审核队列

Space SHOULD 支持审核队列 (Moderation Queue) 视图，汇集所有举报记录。建议使用标准 View 机制：

```json
{
  "kind": "collection",
  "renderer": "list",
  "query": {
    "facets": ["reviewable"],
    "filters": [
      { "field": "fields.status", "op": "eq", "value": "pending" }
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
        { "key": "pending", "title": "Pending" }
      ],
      "hidden_count_policy": "omit"
    }
  }
}
```

## 6. 服务器级访问控制

### 6.1 Server ACL

Principal Server 可以配置服务器级别的 ACL，控制哪些域的联邦请求被接受或拒绝：

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

规则评估顺序：先检查 `deny` 列表，再检查 `allow` 列表。支持 glob 通配符。

### 6.2 与联邦协议的关系

Server ACL 在联邦层（参见 `federation.md`）起作用。当 Principal Server 收到来自被 deny 的域的 `push-operations` 请求时，SHOULD 立即返回 `403 capability_denied`。

## 7. 组织级审核策略

Organization MAY 为其控制或背书的 Space 与服务发布组织级审核策略。该策略仅通过显式引用生效，不会通过任何全局魔法自动适用。

推荐对象：

```json
{
  "kind": "cx.organization.moderation_policy",
  "organization_did": "did:web:acme.example",
  "policy_id": "cx:org-policy:abuse-v1",
  "scope": {
    "space_ids": ["cx:space:01964280-0000-7000-8000-000000000000"],
    "service_dids": [
      "did:web:server.acme.example",
      "did:web:policy.acme.example"
    ],
    "applies_to_official_spaces": true
  },
  "rules": [
    {
      "target": {
        "kind": "organization",
        "did": "did:web:known-abuse.example"
      },
      "action": "deny_federation",
      "reason_code": "abuse_network"
    },
    {
      "target": {
        "kind": "claim_selector",
        "claim_type": "org_membership",
        "issuer": "did:web:untrusted.example"
      },
      "action": "deny_restricted_join"
    }
  ],
  "valid_from": "2026-04-26T00:00:00Z",
  "valid_until": null,
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:web:acme.example#governance-key-1",
    "jws": "..."
  }
}
```

规则：

- 组织策略只对显式引用它的 Space / 服务有权威；对官方 Space 也仅当其 `cx.space.organization` 背书声明组织策略适用时才生效。
- 仅当组织策略允许覆盖时，Space MAY 覆盖组织默认值。
- 组织级 deny SHOULD 由 Policy Server、Principal Server ACL、Directory 过滤与 Space moderation policy 共同执行。
- 组织策略 MUST 由 Organization DID 或受授权的 governance service DID 签名。
- 组织策略 MUST NOT 暴露用户私有 blocklist、私有 handle 或未披露的组织成员关系。

## 8. Policy Server 集成

Space 与 Organization 的审核策略 SHOULD 通过 Policy Server 进行动态评估，覆盖以下场景：

- invite / join request
- knock request
- message create / edit
- media upload
- Applet transaction
- federation transaction
- directory listing
- call invite

Policy Server MAY 返回 `hard_deny`、`quarantine`、`require_review` 或 `soft_deny`，但 MUST NOT 自行授予 capability。

## 9. 服务端威胁借鉴

在“去中心化服务治理”场景中，服务端常见风险的抗滥用经验如下：

- **入口源身份强制**：任何外部服务联邦请求都先验 `service DID`。未签名或未被 allowlist 的源服务不得参与写路径（至少转入 `soft_deny` / `quarantine`）。
- **多级限速**：Sync Service / Policy Server 和受托 search / projection 服务应至少按以下维度限速：`source DID`、`source IP`（或其哈希）、`service token`、`space id`、`endpoint`。超阈值 MUST 返回 `rate_limited`。
- **批量事件反滥用**：对短周期内的 `invite`、`join`、`message`、`media.upload` 进行突发抑制；出现异常突发可触发 `quarantine`。
- **最小可观察性差异**：对未通过鉴权的目录/加入枚举请求，返回统一错误，不泄露对象可见性差异。
- **可疑媒体隔离**：媒体 hash、MIME、扫描标签先入审计与审核，不应默认解密给 Sync Service 或受托 projection；必要时按 `snapshot`/`preview` 再二次放行。
- **可追溯审计**：每次风控拦截、隔离、降级决策都要记录结构化审计事件，且不得仅依赖联邦来源的本地口头说明。

上述规则至少部分对应 `server-threat-model.md` 中的映射结果。  
`policy-server.md` 与 `federation.md` 也应同步落地。

## 10. v1 流程要求

- 自动化审核只能产生 risk signal、`quarantine` 或 `require_review` 建议；除非 Space policy 明确授权，AI 分类器不得直接 hard delete、ban 或扩大可见性。
- 上诉流程 MUST 形成可审计事件，至少包含 target、moderation action、appeal actor、reviewer、decision、reason code 和时间；上诉材料的明文可见范围必须受 policy 控制。
- 跨 Space 共享封禁列表必须由 Organization DID、联盟治理 DID 或受信 issuer 签名，并声明 scope、reason code、evidence hash、过期时间和误伤申诉入口。默认不得把个人 blocklist 发布为共享封禁。
- 审核操作 MUST 使用不可抵赖日志：moderator DID、device/service proof、policy version、target event hash、action、reason code 和 audit timestamp 都必须进入签名记录。
