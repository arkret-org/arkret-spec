# Policy Server

## 1. 目标

Policy Server 是可插拔的风险判断与治理服务，用于邀请、加入、媒体、消息、Applet、跨域联邦等场景的预检查和审计。它类似 Matrix policy server / moderation policy 的思想，但在 Contrix 中不替代 capability authorization。

## 2. Policy Server Declaration

Space 可通过 state event 声明策略服务：

```json
{
  "type": "cx.space.policy_server",
  "state_key": "primary",
  "content": {
    "server_id": "did:web:policy.example.com",
    "endpoint": "https://policy.example.com/contrix/v1/check",
    "public_keys": ["did:web:policy.example.com#key-1"],
    "applies_to": ["join", "invite", "message", "media", "applet"],
    "fail_mode": "soft_deny",
    "cache_ttl_seconds": 300
  }
}
```

声明该事件需要 `space.policy.manage` capability。

## 3. Check Request

```http
POST /contrix/v1/check
Authorization: Bearer <service_token>
Content-Type: application/json
```

```json
{
  "request_id": "polreq_01",
  "space_id": "space:...",
  "action": "message.send",
  "actor": "did:uuid:...",
  "device_id": "dev_a",
  "event_preview": {
    "type": "cx.message.create",
    "content_hash": "sha256:...",
    "redacted_content": {
      "mentions": ["did:uuid:bob"],
      "media": [{"blob_id": "blob:...", "mime": "image/png"}]
    }
  },
  "auth_context": {
    "membership": "join",
    "capability_ids": ["grant:..."],
    "origin_service": "did:web:relay.example"
  }
}
```

请求 MUST 使用最小披露。E2EE 内容不得为策略检查强制明文上传；客户端 MAY 提供本地分类标签、hash、媒体 metadata 或用户确认的 report snippet。

## 4. Decision

```json
{
  "request_id": "polreq_01",
  "decision": "allow",
  "reason_code": "ok",
  "expires_at": "2026-04-26T00:05:00Z",
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

`hard_deny` MAY 使事件被 reject；`quarantine` MUST 使事件进入 quarantine；`soft_deny` SHOULD 阻止默认客户端提交，但 relay MAY 接收并标记 soft failed；`require_review` 生成 proposal/review flow。

## 5. Signature and Replay Protection

Policy decision 签名输入 MUST 包含：

- `request_id`
- request canonical hash
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

## 8. Federation

跨域事件的 origin service MAY 附带 policy decision。接收方：

- MUST 验证 decision 签名。
- MAY 运行本地 policy server 再次检查。
- MUST 保留所有 hard_deny/quarantine decision 的 audit record。
- MUST NOT 因 origin policy allow 而跳过本地 capability/auth 验证。

## 9. Privacy

Policy server 默认不是内容接收者。实现 MUST：

- 对 E2EE Space 默认只发送 metadata。
- 对媒体默认发送 hash、MIME、尺寸、扫描标签，不发送原始 bytes。
- 对 handle、email、phone 等标识符使用 blinded token，除非用户或管理员明确授权。
- 在 audit log 中记录向 policy server 披露了哪些字段。

