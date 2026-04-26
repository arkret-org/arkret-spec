# Service HTTP/JSON Binding Draft

## 1. 目标

本文定义 Contrix 默认 HTTP/JSON binding 的路径、请求形状和错误响应。

协议核心不强绑定 REST。其他 transport binding MAY 使用 gRPC、WebSocket、SSE、message queue、libp2p 或 IPC，但必须映射到 `service-surface.md` 中定义的等价语义。

## 2. 通用要求

- 请求和响应默认使用 `Content-Type: application/json`。
- 写请求 MUST 支持幂等键或内容 ID 幂等。
- 认证 MAY 使用 bearer token、HTTP Message Signature、DID proof 或 transport-specific binding。
- 服务 MUST 通过 describe / feature discovery 暴露实际支持路径、profile 和限制。
- 错误响应 MUST 使用统一 error schema。

## 3. Repo API

### 3.1 提交操作

```text
POST /api/v1/repo/submit-op
```

请求：

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "op": {}
}
```

响应：

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE...",
  "sync_token": "opaque"
}
```

若 CAS (`expected_state_hash`) 校验失败，返回 `409 cas_conflict`。

### 3.2 同步增量

```text
POST /api/v1/repo/sync
```

请求：

```json
{
  "repo_id": "did:uuid:alice-or-cx-space",
  "since": "cursor-or-op-id",
  "limit": 500
}
```

响应：

```json
{
  "ops": [],
  "next_cursor": "opaque",
  "has_more": true
}
```

## 4. Identity API

```text
POST /api/v1/identity/resolve
```

请求：

```json
{
  "did": "did:web:alice.example"
}
```

响应：

```json
{
  "did_document": {
    "id": "did:web:alice.example",
    "verification_method": [],
    "service": []
  },
  "key_log_head": "cx:keyevt:01JS...",
  "seq": 5
}
```

Resolver MUST return enough method-specific evidence for clients to verify control history.

## 5. Relay API

```text
GET /api/v1/relay/firehose?space_id=<space_id>&cursor=<cursor>
```

Frame:

```json
{
  "type": "event",
  "seq": 106,
  "payload": {}
}
```

The same semantic stream MAY be exposed through WebSocket, SSE or long polling.

## 6. Directory API

```text
POST /api/v1/directory/search-spaces
POST /api/v1/directory/resolve-space
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/resolve-handle
```

Directory endpoints MUST apply resource discoverability, requester proof, moderation policy and authorization filtering per result.

For hidden or unauthorized resources, `resolve-*` SHOULD return an indistinguishable `not_found`.

## 7. Blob API

### 7.1 上传

```text
POST /api/v1/blob/upload
```

Content type MAY be `application/octet-stream` or `multipart/form-data`.

响应：

```json
{
  "blob_ref": "cx:blob:sha256:e3b0...",
  "size": 102450,
  "mimetype": "image/png"
}
```

### 7.2 下载

```text
HEAD /api/v1/blob/get?blob_ref=<blob_ref>
GET /api/v1/blob/get?blob_ref=<blob_ref>
```

客户端 MUST 重新计算内容哈希并与 `blob_ref` 比对。

## 8. 标准错误响应

```json
{
  "ok": false,
  "error": {
    "code": "cas_conflict",
    "message": "expected_state_hash mismatch",
    "retry_after_ms": 2000
  }
}
```

## 9. 标准错误码

| 错误码 | HTTP Status | 含义 |
| --- | --- | --- |
| `invalid_signature` | 401 | 签名校验失败。 |
| `auth_expired` | 401 | 认证令牌或 grant 已过期。 |
| `capability_denied` | 403 | 当前 actor 无所需权限。 |
| `space_frozen` | 403 | Space 冻结或归档。 |
| `not_found` | 404 | 目标不存在或对请求方不可见。 |
| `cas_conflict` | 409 | `expected_state_hash` 不匹配。 |
| `epoch_mismatch` | 409 | MLS epoch 版本过期。 |
| `quota_exceeded` | 413 | 配额超限。 |
| `rate_limited` | 429 | 请求频率超限。 |
| `unknown_did` | 422 | DID 无法解析。 |
| `schema_violation` | 422 | payload 不符合 schema。 |
| `internal_error` | 500 | 节点内部错误。 |

客户端收到 `429` MUST 遵守 `retry_after_ms`。收到 `409` SHOULD 拉取最新状态后退避重试。
