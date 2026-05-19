---
title: Media and Blob
---

## 1. 目标

Blob service 提供内容寻址存储。Media profile 在 Blob 之上定义 MIME、缩略图、认证下载、加密附件和保留策略。

## 2. Blob Metadata

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
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
| `realm_id` | `id:realm` | conditional | Owning Realm。普通用户/组织上传 MUST 设置，用于授权、asset privacy policy enforcement、retention 与 GC。仅当 deployment policy 显式声明的全局/跨 Realm 服务 blob（例如 avatar 公共预览）才可省略。 |
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

加密附件的 `key_ref` MUST 使用与 [`encryption-and-audit.md` §2.3.1](./encryption-and-audit.md) 相同的对象形态：`{algorithm, group_state_ref}`（MLS 场景）或 `{algorithm, key_id}`（其他 profile）。

```json
{
  "blob_ref": "cx:blob:sha256:...",
  "encrypted": true,
  "alg": "xchacha20_poly1305",
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "cx:event:01964148-0000-7000-8000-000000000000"
  },
  "epoch": 42,
  "nonce": "base64url...",
  "ciphertext_digest": "sha256:...",
  "size": 1234,
  "media_type": "image/png"
}
```

### 3.1 AEAD nonce uniqueness（normative）

AEAD nonce 在同一 `key_ref` 下复用 = 该 key 在所有曾用 nonce 上的明文被同时解密 = **整个 key catastrophic compromise**。Contrix MLS application key 在同一 epoch 内被所有群成员设备共享,如果多设备并发加密大量 attachment / blob,**naive random 96-bit nonce** 在 ~2^48 次操作后(birthday bound)有显著碰撞概率,且任何单次碰撞都击穿整个 epoch。因此 v1 wire **MUST** 满足下列 nonce 构造规则:

1. **派生 schema (normative)**:`nonce = MLS-Exporter(label, context, length=N_AEAD)` 派生的子密钥 `nonce_key`,与 `device_nonce_counter` 拼接组成。具体形态:

    ```text
    nonce_key = MLS-Exporter(
        label   = "contrix-aead-nonce-derivation-v1",
        context = canonical-bytes(
            { "key_ref": <key_ref-canonical>, "epoch": <mls-epoch>, "purpose": "blob-attachment" }
        ),
        length  = 32
    )

    nonce = HMAC-SHA256(
        key   = nonce_key,
        data  = canonical-bytes(
            { "device_id":            <sender-device-id>,
              "device_nonce_counter": <u64, big-endian, monotonic per-device> }
        )
    )[ 0 : N_AEAD ]
    ```

    `device_nonce_counter` MUST 单调递增,**每设备**单独维护;同一设备同一 epoch 内 MUST NOT 重用同一 counter 值。设备 MUST 在持久化存储中保留 counter,以防进程重启回退;若无法恢复该 epoch 的本地 counter,设备 MUST 先发起 MLS Commit 推进到新 epoch,并在新 epoch 从 0 初始化 counter 后再发送新的 AEAD payload。不得在未知历史的同一 epoch 内用 jump counter 继续发送。

2. **跨设备保证**:不同 device_id 派生出的 nonce 跨设备必然不同(HMAC 输入不同),不需要全局 counter 协调;同一设备内的递增 counter 保证设备内 nonce 不同。

3. **Wire encoding**: `nonce` 字段 base64url 编码 N_AEAD 字节(XChaCha20-Poly1305 → 24 bytes;AES-GCM → 12 bytes);接收方 MUST 在解密前校验 nonce 长度匹配 AEAD algorithm 声明。

4. **AAD binding**: AEAD AAD MUST 至少绑定 `(key_ref, ciphertext_digest, nonce)` 三元组的 canonical 形态;这阻止把同一 (key, nonce) 下的 ciphertext 与另一 AAD 配对解密。

5. **禁止形态**: 实现 **MUST NOT** 使用以下 nonce 来源:
   - 纯随机 96-bit nonce(birthday bound 不够);
   - 全局共享 counter(协调成本 / 同步攻击面);
   - 用户输入派生(可控 = 可碰撞);
   - 任何不绑定 device_id + counter 的形态。

6. **接收方 replay 防护**:接收方 MUST 维护 per-(key_ref, epoch, device_id) 已见 counter 集合或等价无误判结构;重复 counter MUST 触发 `failed_precondition` reason=`aead_nonce_counter_replay`。

`cleartext_sha256` 字段 v1 不再作为附件 metadata 标准字段：在 E2EE Realm 中泄露明文 hash 会破坏内容机密性（短/可预测明文可被离线枚举）。如果 deployment 出于审计需要保留 cleartext commitment，必须使用每事件随机 salt 的 commitment 或服务持有的 HMAC/pepper commitment（见 `event-auth-state-resolution.md` §10.1）。普通 E2EE 附件 metadata 只暴露 `ciphertext_digest`。

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
| `X-Contrix-Wait-For` | header | `cursor` | optional | barrier cursor（`purpose=barrier`）；服务端在 frontier 覆盖该 cursor 描述的 target event 前阻塞响应。 |

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
- Realm visibility
- retention / legal hold
- unsafe media policy

Retention 与 erasure 规则：

- Blob 删除 MUST 由 Realm policy、对象所有权、account lifecycle、retention expiry 或签名 compliance decision 授权。
- 处于 legal hold 的 blob MUST NOT 被物理删除；服务可以通过 redaction 或 policy 在普通视图中隐藏。
- Blob 被擦除后，服务 SHOULD 只保留最小 receipt：`blob_ref`、digest、策略允许时的 size class、erasure reason、执行服务 DID、执行时间和签名。
- 缩略图、preview、转码、搜索文本、embedding 和通知摘要等派生内容 MUST 在源 blob 或源 event 被 redacted / erased 后删除或重新最小化。
- E2EE 附件密钥销毁只能阻止后续访问，不能撤回已被授权接收方下载或解密的明文。

受保护内容默认必须走 authenticated download。公开 blob MAY 允许匿名读取，但私有 Realm、受控组织、E2EE 附件和任何带访问策略的媒体 MUST 要求认证。

下载请求 SHOULD 支持：

```text
Authorization: Bearer <session_token>
X-Contrix-Wait-For: <cursor>
Range: bytes=<start>-<end>
```

规则：

- `X-Contrix-Wait-For` 接受 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 的 `purpose=barrier` cursor，用于避免客户端刚收到引用但 Blob 服务尚未完成授权物化。Blob 服务 SHOULD 等待本地授权 frontier 覆盖该 cursor 描述的 target event，超时返回 `stale_frontier` 或 `temporarily_unavailable`。
- 下载授权 MUST 绑定 actor DID、device/session、Realm id、blob ref、purpose 和过期时间。服务端不得只凭 URL 随机串放行私有媒体。
- 受保护下载 MUST NOT 接受 query string 中的 session、access token 或长期 capability。浏览器客户端应通过 `Authorization` header、service worker 代理或 device-bound proof 获取媒体。
- Blob 服务 MAY 返回短期 signed download URL 或 `307/308` redirect 到对象存储，但 redirect token MUST 短时效、单 blob、单 purpose、可撤销，并不得扩大可见性。
- `Location` 值不得被服务端或客户端长期缓存；未立即下载时 SHOULD 重新请求 `/api/v1/blob/get` 获取新的授权上下文。
- 客户端跟随 redirect 后仍 MUST 重新计算内容 hash，并与 `blob_ref` / `sha256` 比对。
- 如果内容 hash、`Digest` header、`blob_ref` 或 encrypted attachment `ciphertext_digest` 不匹配，客户端 MUST 拒绝该响应、丢弃已下载字节、不得渲染、不得写入持久缓存，并 SHOULD 记录安全审计事件。服务端在上传、镜像或代理时发现 digest mismatch MUST 返回 `digest_mismatch`，并不得生成可用 blob metadata。
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

前提是内容地址包含强 hash，且 metadata 不泄露私有 Realm 信息。

### 5.3 缩略图与预览

缩略图、OCR 文本、转码副本、媒体探测 metadata 都是派生内容：

- E2EE 附件的缩略图 SHOULD 由客户端生成并加密上传，或只在本地生成。
- 服务端生成私有明文缩略图前，该服务 MUST 列入 `plaintext_visible_services`。
- 预览 URL、尺寸、MIME、文件名和 unsafe 标记都必须服从 Realm policy 与 capability，不能绕过正文授权。
- 缩略图必须重新绑定源 blob、生成参数、生成服务 DID 和可见性；删除、撤回、保留策略或 legal hold 改变时，派生内容必须随源内容重新判定。

### 5.4 Pre-Signed URL（浏览器原生标签兼容性例外）

§5 与 [`server-threat-model.md` §S21](../security/server-threat-model.md) 规定受保护下载 MUST NOT 接受 query string 中的认证材料。该规则的存在原因是 query string 会被 HTTP access log、代理、CDN、浏览器历史、复制链接和 `Referer` 头无差别记录，长期 capability 一旦落入 URL 即等价于失控。

然而浏览器原生媒体标签（`<img src>`、`<video src>`、`<audio src>`、`<link href>`、CSS `background-image: url(...)` 等）**无法附加 `Authorization` header**——浏览器在解析这些属性时直接对目标 URL 发起未带认证 header 的 GET。`fetch()` API 本身可以附加 `Authorization`，但其返回的 `Response` 仅能转换为 Blob URL 后由 JS 注入 DOM 才能让原生标签消费，无法直接代替原生 src 的同源加载语义。若严格执行"无 URL 认证"规则，受保护媒体只能通过 service worker 代理或 JS Blob URL 间接渲染——这在很多原生体验、邮件预览、跨页面共享场景中是死路。

为此 v1 定义 **`cx.blob.presign`** 作为该规则的**狭窄定制例外**：发出短 TTL、单对象、只读、可撤销的 pre-signed URL，让浏览器原生标签直接使用，同时通过严格 scope 限制把 URL 泄露的最大损失收敛在一个具体 blob 的短时间访问。

#### 5.4.1 流程

```text
1. 客户端 → POST /api/v1/blob/presign
   body: { blob_ref, max_age_seconds?, purpose? }
   auth: Authorization (standard bearer / service signature)

2. 服务端 (cx.blob.presign capability 通过后):
   - 生成 presign envelope (见 §5.4.2)
   - 用 blob service DID 签名
   - 返回 url、expires_at

3. 浏览器 / 客户端:
   <img src="<url with embedded presign=...>" />
   → GET /api/v1/blob/get?blob_ref=...&presign=...
   → 服务端验证 presign envelope 后吐 bytes
```

#### 5.4.2 Presign envelope wire 形态

`presign` query 参数的值是 base64url 编码的 detached-JWS envelope，覆盖 canonical JSON：

```json
{
  "scheme": "cx.blob.presign.v1",
  "blob_ref": "cx:blob:sha256:0123456789abcdef...",
  "issuer_service_did": "did:web:blob.acme.example",
  "issued_at": "2026-05-18T10:00:00Z",
  "expires_at": "2026-05-18T10:05:00Z",
  "purpose": "media_inline",
  "audience_hint": "did:webvh:Qm...:alice.example",
  "nonce": "base64url:random_16_bytes",
  "scope": {
    "method": ["GET", "HEAD"],
    "byte_range": null
  }
}
```

字段约束：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `scheme` | yes | 固定 `cx.blob.presign.v1`；未来版本 MUST 用新 scheme id（不接受 in-space 升级） |
| `blob_ref` | yes | 单一 blob 引用；与请求 `?blob_ref=` 必须完全匹配 |
| `issuer_service_did` | yes | 签发该 presign 的 blob service DID；MUST 是被部署 trust 的 service DID |
| `issued_at` / `expires_at` | yes | TTL 硬上限 1h；deployment SHOULD 默认 ≤ 5 min |
| `purpose` | yes | `media_inline` / `thumbnail` / `download`；服务端按 purpose 决定 `Content-Disposition`、限流强度等 |
| `audience_hint` | optional | 期望使用者 DID（**仅诊断 hint，不构成访问控制**；浏览器原生标签无法证明调用者身份，详见 §5.4.4.1）。 |
| `nonce` | yes | 16+ bytes 随机；服务端 SHOULD 记录已消费 nonce 以阻止 replay 直至 `expires_at` |
| `scope.method` | yes | 仅允许 `GET` / `HEAD` 中的子集；MUST NOT 包含写方法 |
| `scope.byte_range` | optional | 可限制可访问字节区间（如 `[0, 65536]` 仅头部） |

#### 5.4.3 接收方校验

`GET /api/v1/blob/get?blob_ref=X&presign=<envelope>` 处理时：

1. **互斥检查**：`Authorization` header 与 `?presign=` 同时出现 MUST 拒绝 `invalid_param`，避免混合 auth 模式
2. **签名校验**：用 envelope 内 `issuer_service_did` 当前 verification method 验证签名
3. **scheme 校验**：仅识别注册 scheme id（v1 = `cx.blob.presign.v1`）；未知 scheme MUST 拒绝
4. **blob_ref 一致性**：envelope `blob_ref` 与 query `blob_ref` 必须完全相同
5. **method 校验**：本次请求方法在 envelope `scope.method` 列表内
6. **TTL 校验**：`now() ∈ (issued_at, expires_at)`；含合理 clock skew tolerance（如 ±30s）
7. **nonce 校验**：未在已消费列表 / 撤销列表内（实现 SHOULD 用 bloom filter / 短 TTL set 防 replay）
8. **撤销校验**：blob 已被 redaction / erasure 处理时即便 envelope 仍有效也 MUST 拒绝
9. **可见性校验**：blob 在签发 presign 时刻可见，且在响应时刻仍**对签发 issuer 控制的 audience 可见**；以本次请求时刻为准（防止 presign 持续可用而源 blob 被 ban）

任何校验失败 MUST 返回 `not_found`（不区分 envelope 无效 vs blob 不可见，避免暴露存在性）；服务端 MAY 在 audit log 中记录具体 `reason_code` 如 `presign_invalid` / `presign_expired` / `presign_scope_mismatch`。

#### 5.4.4 安全约束

**MUST**：

- TTL ≤ 1h（硬上限）；deployment policy MAY 收紧到更短
- 单 blob，不接受通配
- 仅读（GET / HEAD），不接受 PUT / POST / DELETE
- envelope 不得包含可重用 credential（refresh token、session token、long-lived capability 等）
- envelope 由 blob service DID 签发，**不能**由 user device key 签发——这是 server-issued capability，不是 user delegation
- 已 revoked / redacted / erased blob 即使 envelope 仍有效 MUST 拒绝
- presign URL 不得通过普通 redirect / 反向代理透传到第三方 origin

**MUST NOT**：

- 用于 E2EE 附件 ciphertext fetch — E2EE 附件的 `blob_ref` + decryption key 都不应出现在服务端可记录的 URL；E2EE 客户端坚持 header auth 路径，由 client-side `fetch()` 配合 `Authorization` 完成
- 用于 `cx.blob.upload`、`cx.blob.head` 之外的任何写或副作用操作
- 由 user device 凭 capability 自签自用（必须经过 `cx.blob.presign` operation 走一次服务端签发，进 audit log 与 capability check）

**SHOULD**：

- deployment 对 presign 签发频率限流（按 issuer service DID + 请求方 actor），防止滥用作为隐蔽 oracle
- audit log 记录每次签发（actor、blob_ref、purpose、TTL、issuer）以便事后追溯
- 客户端 SHOULD 优先用 header auth；仅在浏览器原生标签场景使用 presign

#### 5.4.4.1 `audience_hint` 与 bearer-token 边界（normative）

`audience_hint` 是 **诊断 hint**，**不是访问控制**。原因：浏览器原生标签（`<img>` / `<video>`）在加载 presign URL 时不会附加任何调用者凭据；服务端无法在响应阶段验证当前请求确实来自 `audience_hint` 指向的 actor。任何把 `audience_hint` 当作 audience 强制的实现都会形成假阳性安全感。本节固定如下规则：

- **实现 MUST NOT** 把 `audience_hint` 当成访问控制 — 它只能进入 audit log 用于事后排查"presign 给谁发的"。
- presign 是一个**短 TTL bearer URL**：任何持有该 URL 的人在 TTL 内都可拉取 `blob_ref` 对应字节。最大损失窗口由 (a) TTL、(b) `scope.method`/`scope.byte_range`、(c) revocation（redaction / erasure 触发即时拒绝）三者共同收敛。
- **下列 blob 类别 MUST 走 fail-closed 规则，不得发 presign**：
  - **E2EE ciphertext** — 已经在 §5.4.4 MUST NOT 列出。E2EE 附件 fetch 走 client-side `fetch()` + `Authorization` header 路径。
  - **legal hold blob** — 处于 legal hold 状态的 blob MUST 拒绝 `cx.blob.presign`（`legal_hold_active`），即便申请方持有 `cx.blob.presign` capability。原因：legal hold 要求 access 留痕可追溯，bearer URL 让第三方无凭据拉取破坏审计链。
  - **redacted blob** — `cx.redaction` 已生效 / `cx.audit.erasure_receipt` 已发布的 blob MUST 立即拒绝 presign 请求与已签发但 TTL 未到的 presign 请求（`blob_redacted`）。
  - **private attachment 私有附件**（`visibility=actor_private` 或附 `cx.actor_private` policy 标签）— MUST NOT 走 presign 路径。该类 blob 只允许 issuing actor 本人通过 header auth fetch。
- **future audience-bound 机制**（v2 评估）：若未来需要真正绑定 audience，方案有 (a) 把 presign 升级为 cookie-bound URL（依赖 `__Host-` cookie + SameSite=Strict + presign 校验 cookie binding），(b) 通过 session-bound token 把 presign 换给 client 后只在该 session 内可用。两条都需要客户端配合，不属于 v1 范围。

#### 5.4.4.2 Bearer URL 泄漏面控制（normative）

为限制 bearer URL 泄漏后的最大损失：

- 服务端 MUST 在响应 header 中加：
  - `Cache-Control: private, no-store, max-age=0`
  - `Referrer-Policy: no-referrer`
  - `X-Content-Type-Options: nosniff`
- 服务端 MUST NOT 在 access log / metrics / tracing 中记录 `?presign=` query 参数原文；记录 audit log 时 SHOULD 把 envelope hash 而不是原文写入。
- 服务端 MUST 限制 presign URL 在反向代理 / CDN 层不被缓存（`Cache-Control: private` 不够时还要 set `Vary: Authorization` 或显式 surrogate-control）。
- 客户端 SHOULD 仅在最终消费节点（`<img src=...>` 注入或 fetch）处构造 presign URL；不要在中间 routing / page state / browser history 中长期保留。

#### 5.4.5 与 capability 的衔接

`cx.blob.presign` capability action（risk_tier=medium）控制谁可以**为某 blob 签发 presign**。grant 上的两个 constraint 收紧使用范围：

- `blob_presign_max_ttl_seconds`：grant 允许的最大 TTL 上限（硬上限不超过 3600）
- `blob_presign_scope`：grant 允许的 purpose 集合（`media_inline` / `thumbnail` / `download`）与可选 blob_ref pattern（按 Realm / purpose 细分）

服务端在 `cx.blob.presign` 调用时按 grant constraint 收窄请求的 `max_age_seconds` / `purpose`；超过 constraint 返回 `capability_denied`。

#### 5.4.6 与 §5.2 / §5.3 的关系

- §5 仍是 **认证下载默认路径**；pre-signed 仅作为 §5 的 narrow 例外
- §5.2 redirect / `Location` 头的"短期 signed download URL"语义可以由 `cx.blob.presign` 实现，但 redirect URL MUST 同样满足 §5.4 全部约束
- §5.3 缩略图通常通过 `purpose=thumbnail` presign 让 `<img>` 直接渲染；服务端 SHOULD 设更短 TTL（默认 ≤ 60s）

## 6. Asset Privacy Policy

私有附件下载本身会暴露元数据，例如调用方 IP、在线时间、服务域名关系、blob 大小和下载频率。Realm SHOULD 使用 `cx.realm.asset_privacy_policy` 声明媒体上传、下载和代理隐私要求：

```json
{
  "kind": "cx.realm.asset_privacy_policy",
  "payload": {
    "download_mode": "provider_proxy",
    "allowed_modes": [
      "provider_proxy",
      "ohttp_relay"
    ],
    "direct_download_allowed": false,
    "upload_services": [
      "did:web:blob.acme.example"
    ],
    "download_proxy_services": [
      "did:web:media-proxy.acme.example"
    ],
    "ohttp_gateway_services": [
      "did:web:ohttp-gateway.example"
    ],
    "max_plaintext_metadata": [
      "size_bucket",
      "media_type_family"
    ],
    "requires_client_hash_check": true
  }
}
```

`download_mode` 取值：

| 值 | 含义 |
| --- | --- |
| `direct` | 客户端直接从 Blob / 对象存储下载。只适合公开内容、同一信任域或明确接受 IP 暴露的 Realm。 |
| `provider_proxy` | 通过调用方或 Realm policy 指定的受信 media proxy 下载，隐藏源 Blob 服务或对象存储细节。 |
| `ohttp_relay` | 通过 OHTTP 或等价 oblivious relay 取回内容，降低 Blob 服务同时观察调用方身份和目标 blob 的能力。 |
| `client_mirror` | 客户端从多个 authorized mirror 选择，按内容 hash 验证，适合高可用或隔离网络。 |

规则：

- 私有 Realm、E2EE 附件和高隐私 minimal-metadata Realm 默认 SHOULD 使用 `provider_proxy` 或 `ohttp_relay`，不得默认 direct download。
- `direct_download_allowed=false` 时，客户端 MUST NOT 绕过代理直接访问 `Location` 或外部 URL；服务端也不得返回强制 direct 的 redirect。
- Proxy 服务不因参与下载而获得正文解密权。E2EE 附件必须保持密文，proxy 只能处理密文字节、size bucket、content hash 和授权 envelope。
- `max_plaintext_metadata` 控制服务可见 metadata。高隐私 Realm SHOULD 使用 bucketed size、MIME family，而不是精确文件名、精确字节数或完整 MIME。
- 无论采用哪种下载路径，客户端 MUST 校验内容 hash、ciphertext digest 和 E2EE attachment metadata；proxy 成功不等于内容可信。
- `cx.realm.asset_privacy_policy` SHOULD 被 `cx.realm.policy_components` payload 中的 `components.asset` 引用，并纳入 MLS-bound `policy_root`。

## 7. Safety

Blob service SHOULD:

- validate declared size
- compute digest server-side
- reject digest mismatch
- store MIME metadata as untrusted
- support malware scanning metadata
- support unsafe flag
- support GC grace period

## 8. Lifecycle

Blob MAY be GC'ed if:

- no live object references it
- grace period elapsed
- not under legal hold
- policy permits deletion
