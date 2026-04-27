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

字段规则：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `blob_ref` | `string` | required | 内容地址，通常包含强 hash。 |
| `sha256` | `string` | required | 服务端计算的内容 hash。 |
| `size` | `int` | required | 字节大小。 |
| `media_type` | `string` | optional | 上传声明或服务端校正后的 MIME。缺省为 `application/octet-stream`。 |
| `created_by` | `did` | required | 上传 Actor 或 service DID。 |
| `created_at` | `datetime` | required | 服务端接收时间。 |
| `filename` | `string` | optional | 用户提供或服务生成的文件名；不得用于路径拼接。 |
| `encryption` | `object/null` | required | 加密附件元数据或 `null`。 |

上传规则：

- 上传请求的 `Content-Type` header 是 optional；缺省值为 `application/octet-stream`。
- 客户端 SHOULD 提供准确 `Content-Type`，但服务端 MUST 把上传声明的 MIME 和文件名视为不可信 metadata。
- 如果服务端发现声明 MIME 与内容明显冲突，MAY 把 `media_type` 降级为 `application/octet-stream`，并记录安全标记。
- 文件名 MUST 做控制字符、路径分隔符和过长字段清理；不得影响 `blob_ref` 或存储路径。

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
| `Content-Type` | header | `string` | 可见时 required | MIME 类型；不得泄露不可见资源。 |
| `Content-Disposition` | header | `string` | 可见时 required | `inline` 或 `attachment`，并可携带安全清理后的 `filename`。 |
| `Content-Range` | header | `string` | Range 响应 required | 实际返回字节范围。 |
| `Accept-Ranges` | header | `string` | optional | 服务支持 Range 时 MAY 返回 `bytes`。 |
| `Location` | header | `url` | redirect 时 required | 短期下载 URL 或对象存储 URL。 |

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
- 受保护下载 MUST NOT 接受 query string 中的 session、access token 或长期 capability。浏览器客户端应通过 `Authorization` header、service worker 代理或 device-bound proof 获取媒体。
- Blob 服务 MAY 返回短期 signed download URL 或 `307/308` redirect 到对象存储，但 redirect token MUST 短时效、单 blob、单 purpose、可撤销，并不得扩大可见性。
- `Location` 值不得被服务端或客户端长期缓存；未立即下载时 SHOULD 重新请求 `/api/v1/blob/get` 获取新的授权上下文。
- 客户端跟随 redirect 后仍 MUST 重新计算内容 hash，并与 `blob_ref` / `sha256` 比对。
- Range / HEAD download MUST 绑定同一授权上下文；服务端不得让 Range probe 或 HEAD response 泄露不可见 blob 的大小、MIME、文件名或存在性。
- 对不可见 blob，服务端 SHOULD 返回与不存在资源一致的 `not_found`，并避免返回 `Content-Length`、`Content-Type`、`Content-Disposition`、`Accept-Ranges` 等可枚举 header。

### 5.1 Content-Type 与 Content-Disposition

下载或 HEAD 响应在资源对调用方可见时 MUST 返回 `Content-Type`。返回值 SHOULD 是上传 metadata 中的 `media_type`，但允许以下安全校正：

- 对 `text/*` 添加 charset。
- 对未知或未提供 MIME 返回 `application/octet-stream`。
- 当服务端判定声明 MIME 明显错误或危险时，返回 `application/octet-stream`。

下载或缩略图响应在资源可见时 MUST 返回 `Content-Disposition`：

- 原始下载 MUST 使用 `inline` 或 `attachment`。
- 缩略图 SHOULD 使用 `inline`，并 MAY 使用服务生成文件名。
- 如果存在安全清理后的 `filename`，`Content-Disposition` SHOULD 携带它；否则不携带文件名。
- 服务端 SHOULD 仅对安全类型使用 `inline`，其他类型使用 `attachment`。

建议允许 `inline` 的类型：

```text
text/css
text/plain
text/csv
application/json
application/ld+json
image/jpeg
image/gif
image/png
image/apng
image/webp
image/avif
video/mp4
video/webm
video/ogg
video/quicktime
audio/mp4
audio/webm
audio/aac
audio/mpeg
audio/ogg
audio/wave
audio/wav
audio/x-wav
audio/x-pn-wav
audio/flac
audio/x-flac
```

`text/html`、`text/javascript`、`image/svg+xml` 和未知脚本型内容不得默认 `inline`。

### 5.2 缓存

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

### 5.3 缩略图与预览

缩略图、OCR 文本、转码副本、媒体探测 metadata 都是派生内容：

- E2EE 附件的缩略图 SHOULD 由客户端生成并加密上传，或只在本地生成。
- 服务端生成私有明文缩略图前，该服务 MUST 列入 `plaintext_visible_services`。
- 预览 URL、尺寸、MIME、文件名和 unsafe 标记都必须服从 Space policy 与 capability，不能绕过正文授权。
- 缩略图必须重新绑定源 blob、生成参数、生成服务 DID 和可见性；删除、撤回、保留策略或 legal hold 改变时，派生内容必须随源内容重新判定。

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
