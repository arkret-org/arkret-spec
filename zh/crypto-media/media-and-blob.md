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

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `blob_ref` | query | `string` | required | 内容寻址 blob 引用。 |
| `Authorization` | header | `bearer token` 或 `device proof` | 私有 blob required | 调用者认证。 |
| `Range` | header | `string` | optional | Range 下载范围。 |
| `X-Contrix-Wait-For` | header | `token` | optional | 等待授权物化到指定 sync token。 |

响应字段 / header：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| body | response | `bytes` | GET required | blob 字节内容。 |
| `Content-Length` | header | `int` | optional | 可见时返回内容长度。 |
| `Digest` | header | `string` | optional | 内容摘要。 |
| `Cache-Control` | header | `string` | required | 缓存策略；私有内容必须保守。 |
| `Content-Type` | header | `string` | optional | MIME 类型；不得泄露不可见资源。 |

服务 MUST check:

- actor authorization
- Space visibility
- retention / legal hold
- unsafe media policy

受保护内容默认必须走 authenticated download。公开 blob MAY 允许匿名读取，但私有 Space、受控组织、E2EE 附件和任何带访问策略的媒体 MUST 要求认证。

下载请求 SHOULD 支持：

```text
Authorization: Bearer <session_token>
X-Contrix-Wait-For: <sync_token>
Range: bytes=<start>-<end>
```

规则：

- `X-Contrix-Wait-For` 用于避免客户端刚收到引用但 Blob 服务尚未完成授权物化。Blob 服务 SHOULD 等待本地授权 frontier 覆盖该 token，超时返回 `stale_frontier` 或 `temporarily_unavailable`。
- 下载授权 MUST 绑定 actor DID、device/session、Space id、blob ref、purpose 和过期时间。服务端不得只凭 URL 随机串放行私有媒体。
- Blob 服务 MAY 返回短期 signed download URL 或 `307/308` redirect 到对象存储，但 redirect token MUST 短时效、单 blob、单 purpose、可撤销，并不得扩大可见性。
- 客户端跟随 redirect 后仍 MUST 重新计算内容 hash，并与 `blob_ref` / `sha256` 比对。
- Range download MUST 绑定同一授权上下文；服务端不得让 Range probe 泄露不可见 blob 的大小、MIME 或存在性。

### 5.1 缓存

私有或受控 blob response MUST 设置保守缓存头：

```text
Cache-Control: private, no-store
```

如果服务明确允许客户端缓存，MAY 使用 `private, max-age=<n>`，但 MUST 绑定用户 / device 授权，不得被共享代理缓存。

公开不可变 blob MAY 使用长缓存：

```text
Cache-Control: public, immutable, max-age=31536000
```

前提是内容地址包含强 hash，且 metadata 不泄露私有 Space 信息。

### 5.2 缩略图与预览

缩略图、OCR 文本、转码副本、媒体探测 metadata 都是派生内容：

- E2EE 附件的缩略图 SHOULD 由客户端生成并加密上传，或只在本地生成。
- 服务端生成私有明文缩略图前，该服务 MUST 列入 `plaintext_visible_services`。
- 预览 URL、尺寸、MIME、文件名和 unsafe 标记都必须服从 Space policy 与 capability，不能绕过正文授权。

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
