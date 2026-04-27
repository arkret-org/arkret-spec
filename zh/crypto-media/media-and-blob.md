# Media and Blob Draft

## 1. 目标

Blob service 提供内容寻址存储。Media profile 在 Blob 之上定义 MIME、缩略图、认证下载、加密附件和保留策略。

## 2. Blob Metadata

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "sha256": "hex...",
  "size": 1234,
  "media_type": "image/png",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": null
}
```

## 3. Encrypted Attachment

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "encrypted": true,
  "alg": "xchacha20_poly1305",
  "key_ref": "mls_epoch:42",
  "nonce": "base64url...",
  "ciphertext_digest": "sha256:...",
  "cleartext_sha256": "hex...",
  "size": 1234,
  "media_type": "image/png"
}
```

## 4. Thumbnail

Thumbnail descriptor:

```json
{
  "source_blob_ref": "cx:blob:sha256:...",
  "thumbnail_blob_ref": "cx:blob:sha256:...",
  "width": 320,
  "height": 180,
  "media_type": "image/webp"
}
```

## 5. Authenticated Download

```text
GET /api/v1/blob/get?blob_ref=<ref>
```

服务 MUST check:

- actor authorization
- Space visibility
- retention / legal hold
- unsafe media policy

## 6. Safety

Blob service SHOULD:

- validate declared size
- compute digest server-side
- reject digest mismatch
- store MIME metadata as untrusted
- support malware scanning metadata
- support unsafe flag
- support GC grace period

## 7. Lifecycle

Blob MAY be GC'ed if:

- no live Entity references it
- grace period elapsed
- not under legal hold
- policy permits deletion
