# Policy Server

## 1. 目标

Policy Server 是可插拔的风险判断与治理服务，用于邀请、加入、媒体、消息、Applet、跨域联邦、目录发现、通话邀请等场景的预检查和审计。它类似 Matrix policy server / moderation policy 的思想，但在 Contrix 中不替代 capability authorization。

## 2. Policy Server Declaration

Space 可通过 state event 声明策略服务：

```json
{
  "kind": "cx.space.policy_server",
  "state_key": "primary",
  "content": {
    "server_id": "did:web:policy.example.com",
    "endpoint": "https://policy.example.com/contrix/v1/check",
    "public_keys": ["did:web:policy.example.com#key-1"],
    "applies_to": ["join", "invite", "message", "media", "applet", "directory", "call", "federation"],
    "policy_sources": [
      "cx.space.moderation_policy",
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
  "actor": "did:plc:...",
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

Policy server MAY enforce Space-level and Organization-level blocklists, allowlists, rate limits, abuse reputation and content risk labels. It MUST NOT inspect personal blocklists unless the holder explicitly uses a private policy service under their control.

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
