---
title: Policy Server
---

## 1. 目标

Policy Server 是可插拔的风险判断与治理服务，用于邀请、加入、媒体、消息、Applet、跨域联邦、目录发现、通话邀请等场景的预检查和审计。它类似 Matrix policy server / moderation policy 的思想，但在 Contrix 中不替代 capability authorization。

## 2. Policy Server Declaration

Space 可通过 state event 声明策略服务：

```json
{
  "kind": "cx.space.policy_server",
  "payload": {
    "server_id": "did:web:policy.example.com",
    "endpoint": "https://policy.example.com/contrix/v1/check",
    "public_keys": [
      "did:web:policy.example.com#key-1"
    ],
    "applies_to": [
      "join",
      "invite",
      "message",
      "media",
      "applet",
      "directory",
      "call",
      "federation"
    ],
    "policy_sources": [
      {"kind": "cx.space.moderation_policy"},
      "cx.organization.moderation_policy"
    ],
    "abuse_profile_ref": "cx.policy:abuse-v1",
    "fail_mode": "soft_deny",
    "cache_ttl_seconds": 300
  }
}
```

声明该事件需要 `cx.policy.manage` capability。

## 3. Check Request

```http
POST /contrix/v1/check
Authorization: Bearer <service_token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `service_signature` | required | Policy Server 授权凭证；MUST 绑定调用服务 DID。 |
| `request_id` | body | `string` | required | 请求 ID，用于日志和幂等追踪。 |
| `space_id` | body | `id` | optional | 相关 Space；Space 相关检查 SHOULD 提供。 |
| `request_canonical_hash` | body | `sha256:<hash>` | required | 被检查请求或事件 preview 的 canonical hash。 |
| `action` | body | `string` | required | 待检查动作，例如 `cx.message.create`。 |
| `actor` | body | `did` | required | 发起动作的 Actor DID。 |
| `device_id` | body | `id` | optional | 发起设备。 |
| `source` | body | `object` | required | 调用来源摘要。 |
| `source.service_did` | body | `did` | required | 调用服务 DID。 |
| `source.service_type` | body | `string` | required | 调用服务类型。 |
| `source.source_ip_hash` | body | `sha256:<hash>` | optional | 来源 IP 的不可逆 hash。 |
| `source.signed_transport` | body | `boolean` | required | 请求是否由签名 transport 保护。 |
| `event_preview` | body | `object` | optional | 最小披露事件预览。 |
| `auth_context` | body | `object` | optional | membership、capability、origin service 等授权上下文。 |

请求示例（非完整 schema）：

```json
{
  "request_id": "polreq_01",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "request_canonical_hash": "sha256:...",
  "action": "cx.message.create",
  "actor": "did:webvh:...",
  "device_id": "cx:device:01js0ke0000000000000000000",
  "source": {
    "service_did": "did:web:server.example",
    "service_type": "principal_server",
    "source_ip_hash": "sha256:...",
    "signed_transport": true
  },
  "event_preview": {
    "kind": "cx.message.create",
    "content_hash": "sha256:...",
    "redacted_content": {
      "mentions": ["did:web:bob.example.com"],
      "media": [{"blob_id": "blob:...", "mime": "image/png"}]
    }
  },
  "auth_context": {
    "membership": "join",
    "capability_ids": ["grant:..."],
    "origin_service": "did:web:server.example"
  }
}
```

请求 MUST 使用最小披露。E2EE 内容不得为策略检查强制明文上传；客户端 MAY 提供本地分类标签、hash、媒体 metadata 或用户确认的 report snippet。

## 4. Decision

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 回显请求 ID。 |
| `decision` | `enum(allow,soft_deny,hard_deny,quarantine,require_review)` | required | 策略决策。 |
| `reason_code` | `string` | required | 稳定原因码。 |
| `expires_at` | `datetime` | required | 决策缓存过期时间。 |
| `next_retry_at` | `datetime` | optional | 可重试时间，仅限限流/退避场景。 |
| `obligations` | `object[]` | optional | 调用方必须执行的附加动作。 |
| `signature` | `signature` | required | Policy Server 对决策的签名。 |
| `signature.kid` | `did-url` | required | 签名 key id。 |
| `signature.sig` | `base64url string` | required | detached signature。 |

响应示例（非完整 schema）：

```json
{
  "request_id": "polreq_01",
  "decision": "allow",
  "reason_code": "ok",
  "expires_at": "2026-04-26T00:05:00Z",
  "next_retry_at": "2026-04-26T00:05:30Z",
  "obligations": [
    {"type": "rate_limit", "bucket": "message", "remaining": 20}
  ],
  "signature": {
    "kid": "did:web:policy.example.com#key-1",
    "sig": "base64url..."
  }
}
```

`decision` 取值：

- `allow`
- `soft_deny`
- `hard_deny`
- `quarantine`
- `require_review`

`hard_deny` MAY 使事件被 reject；`quarantine` MUST 使事件进入 quarantine；`soft_deny` SHOULD 阻止默认客户端提交，但 Sync Service MAY 接收并标记 soft failed；`require_review` 生成 proposal/review flow。

`reason_code` SHOULD 至少覆盖：

- `ok`
- `spam_flood`
- `invite_token_risk`
- `session_token_risk`
- `auth_threat`
- `spoof_like`
- `malware_media`
- `replay_suspect`
- `policy_violation`
- `fork_risk`
- `resolver_risk`
- `topology_risk`
- `snapshot_risk`

`obligations` 可用于返回风控动作（例如 `rate_limit`、`challenge`、`review_hold`、`drop_attachment`）。  
`next_retry_at` SHOULD 仅在限流/退避路径返回。

## 5. Signature and Replay Protection

Policy decision 签名输入 MUST 包含：

- `request_id`
- `request_canonical_hash`
- decision
- reason_code
- expires_at
- policy server id
- key id

节点 MUST 拒绝过期 decision。缓存 decision 时 MUST 以 request canonical hash 为 key，不得把一个 actor/action 的 allow 泛化给不同内容。

## 6. Failure Mode

`fail_mode`：

- `open`：策略服务不可用时继续基础授权。
- `soft_deny`：默认客户端阻止提交，但允许 proposal 或稍后重试。
- `quarantine`：可提交但进入 quarantine。
- `closed`：不可用时拒绝提交。

公共开放 Space SHOULD NOT 使用 `open`。关键安全 Space MAY 使用 `closed`，但必须提供人工 break-glass capability。

## 7. Relationship to Capability Authorization

Policy server 不创建权限。事件必须先通过 capability authorization，再考虑 policy decision。即：

- 无 capability + policy allow = reject。
- 有 capability + policy hard_deny = reject 或 quarantine。
- 有 capability + policy unavailable = 按 fail_mode。

Policy server MAY 执行 Space 级与组织级的 blocklist、allowlist、rate limit、滥用声誉与内容风险标签。除非 holder 明确使用其自控的私有 policy 服务，Policy server MUST NOT 检查个人 blocklist。

### 7.1 Moderation State 必须进入 Anchor Frontier

Policy server decision 是 out-of-band 的签名决策，本身不进入 Space anchor frontier。只有 `allow` 与 `soft_deny`（仅阻止 default client 提交）可以仅在本地或 fast path 上生效；任何会改变其他 peer 对事件可见性、可写性、可分发性判断的 decision——`hard_deny`、`quarantine`、`require_review`——MUST 通过 anchored Move 写入协议状态。否则不同 Principal Server 在同一 Space 上对同一事件作出不一致决策，会形成跨 peer 的 split-brain：A 把消息 quarantine 隐藏，B 直接 allow，两边客户端看到的 Space 状态从此分叉。

为此 v1 引入 `cx.component.moderation_state.v1` cell family：

- `cell_family = cx.component.moderation_state.v1`
- `cell_subject` = `target_event_id` 或 `target_object_id` 的 canonical 字符串。
- `lattice = or-set`，`bottom = expose`。每个 add tag 形如 `<decision_kind>:<issuer_did>:<request_canonical_hash>`，确保不同 issuer 的同类决策可以并存且幂等。

对应 wire event：

- `cx.moderation.decision` — 由持有 `cx.space.moderate` 或 `cx.policy.manage` 的 actor 签发的 Move，在 `cx.component.moderation_state.v1:<target>` cell 上写一个 `or-set add` effect。
- `cx.moderation.decision.lift` — 在同一 cell 上写 `or-set remove` effect，针对此前 add 的 tag。
- 两者的 `refs[role=authorized_by]` SHOULD 引用对应 policy server signed decision（role=`policy_decision`）作为风险决策证据；该 ref 不参与签名校验等价性，仅用于审计和回放。policy server signed decision 本身不是 capability 来源——签发 Move 的 actor 必须独立持有 `cx.space.moderate` 或 `cx.policy.manage`。

Reducer 与所有读路径 MUST：

- 在 reducer 的 `apply_anchor` 阶段把 moderation state cell 的当前 value 暴露给后续 Move 的 precondition 与 query / projection executor。
- 对包含 `quarantine` / `hard_deny` 决策的目标，禁止派生层（search、inbox、notification、view）按未 quarantine 处理；命中时返回 `moderated_hidden` 占位符或省略，并保留 audit trail。
- 对包含 `require_review` 决策的目标，按 review proposal 状态机展示，不允许默认渲染。
- `cx.moderation.decision.lift` 解除决策时，受影响的 search / projection cache MUST 立即重算。

Policy server fast path 与 anchored decision 的关系：

- Fast path 上，policy server 返回 `quarantine` / `hard_deny` 后，origin Principal Server SHOULD **同步** 提交 `cx.moderation.decision` Move 到该 Space 的 anchor pipeline。Move 提交前 origin 节点 MAY 本地隐藏目标作为优化，但**不得**以 fast-path 决策永久代替 anchored decision。
- 若 origin 节点 24 小时内（或 Space policy 声明的更短窗口）未能把 fast-path quarantine 提升为 anchored decision——例如 anchorer paused、origin actor 失去 `cx.space.moderate` capability、Move 被 `failed_precondition` 拒绝——MUST 解除本地隐藏并退回到 anchored decision frontier 实际值。这避免单一 origin 在 anchorer 故障期间无限期隔离他人内容。
- Receiver 节点收到 fast-path quarantine signaling（policy server 签名）但无对应 anchored Move 时，MAY 临时隐藏目标作为风险缓解，但 MUST 在 UI 中标记 `moderation_pending_anchor` 并在 anchored decision 抵达后切换显示。

**Fast-path 退回的 UX 规则**：当 fast-path quarantine 因 24h 升级失败而被解除时，receiver MUST：

- 通过 ephemeral signal（client_sync extension）通知所有当前 viewing 该 Space 的客户端，附带 `reason_code=moderation_anchor_lifted` 与 `affected_event_id` 列表。
- 客户端 UI MUST 显式提示用户内容重新可见（避免用户误以为自己看错），不得静默切换显示。形态可以是:
  - 该 Space 顶部 banner: "X 条内容因审核未达成共识已恢复显示"
  - 在 audit log / moderation history view 中保留 `quarantine_attempted_at` + `lifted_at` + `reason` 三段 trail（不是普通 message redaction history，而是独立的 moderation history）。
- 已发出的 push notification SHOULD 由 push gateway 通过 silent update 收回（Apple/Google 平台的 silent push），但**不得**重新发送通知（避免双倍打扰）。
- audit / search / projection 应从那一刻起按 anchored frontier 重建受影响 view；缓存中曾被 fast-path 隐藏的 entry MUST 立即失效。

### 7.2 错误码与 reason_code 扩展

引入 anchored moderation state 后，`reason_code` 集合扩展：

- `moderation_anchor_pending` — fast-path quarantine 已记录，但 anchored Move 未到达。
- `moderation_anchor_lifted` — 此前 anchored quarantine 已被 `cx.moderation.decision.lift` 解除。
- `moderation_anchor_split` — moderation cell 在当前 anchor view 下出现 ⊥（或 expose 多 head）；UI 应显式提示而不是默默选 winner。

## 8. Antifraud Mapping from Server Abuse Practice

服务端中对“开放联邦入口”“垃圾泛滥”“地址枚举”“内容扫描”“重放放大”的常见防护可直接映射到策略服务：

- **反开放联邦入口**：来自未声明 `source.service_did` 的联邦请求先降级到 `rate_limited` 或 `soft_deny`，只有在策略显式 allowlist 后才恢复 normal allow。
- **反爆发**：策略决策返回中可携带 `rate_limit` `obligation`，要求源服务在 `next_retry_at` 之前退避。
- **反假源**：`source.signed_transport=true` 且 service key 可校验时可放行；未签名来源只能走更严格决策分支并写入审计。
- **反重放**：`request_id` 与 `request_canonical_hash` 一起构成 decision 缓存键；不同 payload 使用同一 `request_id` MUST 触发 `duplicate_conflict` 语义。
- **反钓鱼/内容滥发**：对媒体只传递 `content_hash`、`content_type`、扫描标签；需要二次确认的内容转为 `quarantine` 而非直接拒收。
- **反枚举**：对未授权目录查询与 join 探测使用统一错误码，不暴露存在性差异；这条规则同时应写入 directory/filter 层。

策略服务实现 SHOULD 引用 [server-threat-model.md](../security/server-threat-model.md) 中“3. 对照：协议内映射与处理”作为联邦威胁基线，并确保本地 policy decision 与本地 `capability/auth` 顺序一致。

## 9. Federation

跨域事件的 origin service MAY 附带 policy decision。接收方：

- MUST 验证 decision 签名。
- MAY 运行本地 policy server 再次检查。
- MUST 保留所有 hard_deny/quarantine decision 的 audit record。
- MUST NOT 因 origin policy allow 而跳过本地 capability/auth 验证。

## 10. Privacy

Policy server 默认不是内容接收者。实现 MUST：

- 对 E2EE Space 默认只发送 metadata。
- 对媒体默认发送 hash、MIME、尺寸、扫描标签，不发送原始 bytes。
- 对 handle、email、phone 等标识符使用 blinded token，除非用户或管理员明确授权。
- 在 audit log 中记录向 policy server 披露了哪些字段。
