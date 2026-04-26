# Service API Request / Response Schema Draft

## 1. 目标

本文给出 Contrix 核心服务的正式 request / response 形状。通用错误、分页、幂等规则见 `api-conventions.md`。

## 2. Identity

### 2.1 Resolve DID

```text
POST /api/v1/identity/resolve
```

Request:

```json
{ "did": "did:web:alice.example" }
```

Response:

```json
{
  "did": "did:web:alice.example",
  "did_document": {},
  "normalized_principal_view": {},
  "seq": 5,
  "head_event_hash": "sha256:...",
  "receipts": []
}
```

## 3. Repo

### 3.1 Submit Commit

```text
POST /api/v1/repo/submit_commit
```

Request:

```json
{
  "repo_id": "did:web:alice.example",
  "commit": {},
  "idempotency_key": "cx:req:01JS0RQ000000000000000000"
}
```

Response:

```json
{
  "status": "accepted",
  "commit_id": "cx:commit:01JS0KE000000000000000000",
  "commit_hash": "sha256:...",
  "sync_token": "cx:sync:..."
}
```

### 3.2 Fetch Ops

```text
POST /api/v1/repo/ops
```

Request:

```json
{ "op_ids": ["cx:op:01JS0OP000000000000000000"] }
```

Response:

```json
{ "ops": [], "missing": [] }
```

## 4. Relay

### 4.1 Subscribe

```text
GET /api/v1/relay/subscribe?space_id=<id>&cursor=<cursor>
```

Frame:

```json
{
  "type": "event",
  "cursor": "cx:cursor:...",
  "event": {}
}
```

## 5. Index

### 5.1 Query

```text
POST /api/v1/index/query
```

Request 使用 `query-schema.md`。

Response:

```json
{
  "items": [],
  "next_cursor": null,
  "has_more": false,
  "frontier": {}
}
```

## 6. Blob

### 6.1 Upload

```text
POST /api/v1/blob/upload
```

Response:

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "sha256": "hex...",
  "size": 1234,
  "media_type": "image/png"
}
```

## 7. Authz

### 7.1 Check

```text
POST /api/v1/authz/check
```

Request:

```json
{
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:...",
  "action": "entity.update",
  "resource": {}
}
```

Response:

```json
{
  "allowed": true,
  "grant_refs": ["cx:grant:..."],
  "requirements": []
}
```
