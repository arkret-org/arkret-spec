---
title: Content Types
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> 体例说明：本文件字段表的「必填 / 必需」列采用 RFC 关键字（MUST / SHOULD / MAY）表达，区别于其余 models 对象表使用的 `yes / no / conditional` 体例；二者语义对应关系为 MUST↔yes、MAY↔no、SHOULD/条件性↔conditional。

## 1. 目标

Arkret 的 `message` 标准对象、Strand synthesis / discussion 和可讨论的 Morph 需要承载远比纯文本丰富的内容，包括图片、视频、文件、代码块、地理位置等。本规范定义了结构化的**内容类型系统 (Content Type System)**，使得：

- 所有客户端能够以一致的方式渲染各种消息类型
- 不支持某种内容类型的客户端能通过 `fallback_text` 优雅降级
- E2EE 场景下加密信封 (`encrypted_content`) 只包裹 Message 顶层的 `content`（即整个 Content Block 对象，包括其内部的 `body` 字段）和 `attachments` 等业务字段，`strand_id` / `created_by` 等路由与归因 metadata 保持明文

## 2. 设计原则

### 2.1 Content 是结构化的，不是裸字符串

Message 的 `content` 字段、`ak.message.create` / `ak.message.revise` Event Envelope 的 `payload.content` 或 `payload.encrypted_content` 字段、Strand 的 `content` / `encrypted_content` 字段、Strand discussion 摘要以及 Morph 的 `content` / `encrypted_content` 字段 MUST 使用本规范定义的结构化 JSON 格式或其 canonical encrypted envelope，而非依赖客户端猜测渲染方式。

### 2.2 单一 Content Block 架构

每条消息的 `content` 字段是一个 **Content Block** 对象，包含：
- `kind`：内容类型标识
- `body`：人类可读的纯文本摘要 / fallback
- 类型相关的专有字段

Message envelope 与 Content Block 的层级关系大致如下（Message 顶层完整 schema 见 [`strand-and-message.md` §9.2](./strand-and-message.md#92-schema-与字段)，本文件后续章节只讨论 `content` 内部结构）：

```json
{
  "id": "ak:message:...",
  "realm_id": "ak:realm:...",
  "strand_id": "ak:strand:...",
  "track_name": "discussion",
  "state": "active",
  "created_by": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
  "created_at": "2026-04-26T00:00:00Z",

  "content": {
    "kind": "ak.content.text",
    "body": "纯文本 fallback",
    "format": "markdown",
    "formatted_body": "..."
  }
}
```

因此本文档示例里的 `kind` / `body` / `format` 等字段都是 **Content Block 内部字段**，位于 Message `content` 之下；不要与 Message 顶层字段混在一层理解。

`ak.message.create` / `ak.message.revise` 的未加密 Event payload MUST 将这个 Content Block 对象放在 `payload.content` 字段中；E2EE payload MUST 将同一对象加密后放在 `payload.encrypted_content`。`strand_id`、`blob_refs` 等字段是 envelope / reducer metadata（Message 主键是顶层 `id`，不是 `message_id`；回复关系由 `replies_to` Relation 表达，物化 Message 对象无 `reply_to` 标量字段——`ak.message.create` payload 可携带 `reply_to` 作为创建便利，reducer 据此记录该消息的回复指向并投影为 `replies_to` 关系，不要求单独的 canonical `ak.relation` 事件），不能把消息正文直接写成 payload 顶层 `body`。

这里的 `payload` 指 Event Envelope 的 kind-specific 业务载荷容器；`content` 指该 payload 内部写入 Message / Strand / Morph 正文字段的 Content Block，不是 `payload` 的同义词。

### 2.3 复合消息使用 `composite` 类型

当一条消息需要同时包含文本和图片（例如带说明文字的截图），使用 `composite` 类型将多个 Content Block 组合。

## 3. Content Block 通用结构

```json
{
  "kind": "ak.content.<kind_name>",
  "body": "纯文本 fallback，用于通知、搜索索引和不支持该类型的客户端"
}
```

类型专有字段以同级 key 形式追加到该对象上（例如 `format` / `formatted_body` 见 §4.1 文本消息示例）。

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `kind` | string | MUST | 内容类型标识符 |
| `body` | string | MUST | 纯文本 fallback |

## 4. 标准内容类型

### 4.1 文本消息 `ak.content.text`

最基础的消息类型。

```json
{
  "kind": "ak.content.text",
  "body": "@bob 请确认这个 item 的 legal 风险。",
  "format": "markdown",
  "formatted_body": "<mention did=\"did:webvh:zHuXvTbhiRsj2KEPE64TLhzG4:bob.example\">@bob</mention> 请确认这个 item 的 legal 风险。"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `format` | string | SHOULD | 格式化类型：`plain`, `markdown`, `prosemirror_json` |
| `formatted_body` | string/object | MAY | 结构化的富文本内容（当 format 不为 plain 时使用） |

**inline 正文上限（normative）**：`ak.content.text.body` MUST NOT 超过 **256 KiB UTF-8 bytes（262,144）**。超过该分界的纯文本正文 MUST 使用 §4.1.1 的 `ak.content.long_text`。JSON Schema 的 `maxLength` 只表达不宽于该值的 code-point 快速上限；权威检查 MUST 由 UTF-8 byte validator 执行。

### 4.1.1 长文本消息 `ak.content.long_text`

超过 inline 分界的纯文本正文使用本 Content Block：一个小型 inline fallback 加一个 Blob-backed 完整正文。它是 **v1 core Content Block**，不使用 requirements feature，服务端 MUST NOT 广告“支持 `ak.content.text` 但不支持 `ak.content.long_text`”——长正文是同一个 Message 基础模型的边界形态，把它设为可选会使合法 Message 在不同 core 实现间不可读。

#### plaintext 形态

```json
{
  "kind": "ak.content.long_text",
  "format": "markdown",
  "body": "前 4 KiB 内的可独立展示前缀……",
  "body_kind": "prefix",
  "blob_ref": "ak:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "size_bytes": 700000,
  "line_count": 12000,
  "media_type": "text/markdown"
}
```

| 字段 | 类型 | 必需 | 规则 |
|------|------|------|------|
| `kind` | const | MUST | `ak.content.long_text` |
| `format` | enum | MUST | 闭集 `plain` \| `markdown`；本 kind MUST NOT 使用 `prosemirror_json`（结构化富文本应有独立 Content Block/schema） |
| `body` | string | MUST | fallback，≤ **4 KiB UTF-8 bytes（4,096）** |
| `body_kind` | enum | MUST | 闭集 `prefix` \| `summary` |
| `blob_ref` | hash blob ref | MUST | 完整 UTF-8 正文字节的内容地址，形如 `ak:blob:(sha256\|blake3):<64 hex>` |
| `size_bytes` | uint64 | MUST | §4.1.2 规范化后完整 UTF-8 正文字节数 |
| `line_count` | uint64 | MAY | 按 §4.1.2 计算 |
| `media_type` | enum | MUST | `text/plain` 对应 `format=plain`，`text/markdown` 对应 `format=markdown` |

shape MUST 是 `additionalProperties=false` 的闭合对象。

`blob_ref` 本身就是完整 plaintext 字节的 digest commitment，因此本 kind **不**再增加重复的 `content_digest`。接收端 MUST 把 `blob_ref=ak:blob:<suite>:<hex>` 拆成 `<suite>:<hex>`，要求它与 Blob metadata 的 `content_digest` 相等，并对下载的规范化正文重算；三者任一不等即 `digest_mismatch`。UUID 形态 Blob ref 不具备该性质，故在本 Content Block 中 MUST NOT 使用；`media_type` MUST NOT 携带 `; charset=utf-8` 等参数（charset 由本 kind 固定为 UTF-8）。

#### E2EE 形态

E2EE Message 的 long-text descriptor 位于已认证的 `encrypted_content` plaintext 中，完整正文 Blob 使用现有 `encrypted_attachment` descriptor：

```json
{
  "kind": "ak.content.long_text",
  "format": "plain",
  "body": "已认证 fallback",
  "body_kind": "summary",
  "line_count": 12000,
  "attachment": {
    "blob_ref": "ak:blob:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "encrypted": true,
    "scheme": "ak.blob.stream_aead.v1",
    "alg": "mls_exporter_aead_xchacha20poly1305_stream",
    "key_ref": {
      "algorithm": "MLS",
      "group_state_ref": "ak:event:01900000-0000-7000-8000-000000000000"
    },
    "epoch": 42,
    "ciphertext_digest": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "size_bytes": 700000,
    "media_type": "text/plain",
    "nonce_prefix": "AAAAAAAAAAAAAAAAAAAAAAAAAA",
    "segment_bytes": 262144,
    "segment_count": 3
  }
}
```

规则：

- 完整正文的明文字节数由 `attachment.size_bytes` 承载（[`../crypto-media/media-and-blob.md` §3.1](../crypto-media/media-and-blob.md)：`encrypted_attachment.size_bytes` 是**明文**字节数，与 `segment_count == ceil(size_bytes / segment_bytes)` 同源）。本 kind MUST NOT 再定义 `plaintext_size_bytes` 之类的第二个明文尺寸字段；
- `attachment.scheme` MUST 是 `ak.blob.stream_aead.v1`，`attachment.alg` MUST 是对应的 `_stream` 算法。E2EE long text MUST NOT 使用 whole-file AEAD——强制 streaming 是为了让超过分界的正文能边下边验且内存有界，不作为同一语义的第二种可选形态；
- `attachment.blob_ref` MUST 是 hash-addressed，且其中的 `<suite>:<hex>` MUST 同时等于 `attachment.ciphertext_digest` 与 Blob metadata `content_digest`；三者都承诺按 `segment_index` 顺序拼接、每段包含 AEAD tag 的完整 stored ciphertext bytes；
- `attachment.media_type` MUST 与 `format` 一致；
- `segment_count` MUST 等于 `ceil(attachment.size_bytes / attachment.segment_bytes)`，并与实际收到的 segment 数一致（[`../crypto-media/media-and-blob.md` §3.3.1](../crypto-media/media-and-blob.md)）；接收端 MUST NOT 从 stored ciphertext 长度反推明文长度；
- 完整 `ciphertext_digest`、逐段 AEAD、末段与顺序全部验证通过前，接收端 MUST NOT 把正文标成完整；
- fallback `body` 已在 Message encrypted payload 内认证，Blob 服务 MUST NOT 改写。

### 4.1.2 文本规范化与计数（normative）

Blob 解码后的正文 MUST：

- 是有效 UTF-8，不带 BOM；
- 保留原始 Unicode scalar sequence，MUST NOT 做 NFC/NFKC 改写；
- 行结束统一使用 LF（U+000A）；producer MUST 在计算 digest、size 与 line count **之前**把 CRLF/CR 规范化为 LF；
- 除 LF、TAB 外 MUST NOT 含 C0 控制字符与 DEL；
- `format=markdown` 按不可信输入消毒，MUST NOT 执行 raw HTML/script。

`size_bytes`（plaintext 形态）与 `attachment.size_bytes`（E2EE 形态）都是上述规范化后完整 UTF-8 字节长度。fallback `body` 自身 MUST 满足相同的 UTF-8、LF、BOM、控制字符与 markdown 消毒规则；producer MUST 先规范化完整正文，再从该结果生成 prefix 或 summary，MUST NOT 对两者采用不同的换行 / Unicode 处理。

`line_count` 若存在，定义为：

```text
empty text     => 0
non-empty text => count(U+000A) + (last scalar is U+000A ? 0 : 1)
```

接收端 MUST 校验声明计数。计数不一致时正文无效，但 Message 的小 fallback 仍可显示。

### 4.1.3 Fallback 规则（normative）

`body` 是 timeline、通知可访问性、Blob 尚未到达和未知实现的安全 fallback。

- `body_kind=prefix`：`body` MUST 是完整正文从 byte 0 开始、在 Unicode scalar 边界截断的前缀，MUST NOT 超过 4,096 UTF-8 bytes；接收端下载 Blob 后 MUST 验证前缀相等。前缀可在 code point 边界截断，不要求落在单词或段落边界。
- `body_kind=summary`：`body` 是作者提供的摘要，不要求是正文前缀，MUST NOT 超过 4,096 UTF-8 bytes；UI MUST 标注为摘要，MUST NOT 拼接到完整正文前面。协议不尝试机器验证摘要忠实性。

4 KiB 是 UTF-8 **字节**限制，不是 JSON Schema `maxLength` 的 code point 数。schema MAY 给不宽于 4,096 的 `maxLength` 作为快速上限，但权威检查 MUST 由 UTF-8 byte validator 完成。

### 4.1.4 选择边界（normative）

选择基于**最终规范化源正文**，不是 gzip、ciphertext、JSON escaped 或上传 chunk 大小：

```text
0..262144 bytes        => ak.content.text
262145 bytes and above => ak.content.long_text
```

边界无重叠。`ak.content.long_text` MUST NOT 用来把 10 字节正文强行 Blob 化；普通文件另用 `ak.content.file`。

此外，最终 Event 仍 MUST 满足 [`../conformance/scalability-constraints.md` §2.1.1](../conformance/scalability-constraints.md) 的完整 Event Envelope 上限。这是一条**更早的 transport 必要条件**，不改变上述 content-kind 的强制分界：

- `ak.content.text` 只在正文 ≤256 KiB **且**完整 Event 合法时可用；
- `ak.content.long_text` 在正文 >256 KiB 时强制；在较小正文上**仅当**完整 Event 否则无法满足 1 MiB 硬上限时允许，且该例外 MUST 由完整 Event size validator 证明，MUST NOT 由实现任意选择。

因此 `size_bytes` / `attachment.size_bytes` 的 schema 下界不能写成 262,145——那会使上述例外不可表达。schema 只校验类型与非负性，">256 KiB 或 Event-overflow 例外"由 normative validator 判定。

### 4.1.5 下游行为（normative）

- **Timeline**：先显示 `body`，下载 / 验证成功后替换为完整正文。
- **Search**：只能索引已解密且完整验证的 Blob 正文；fallback 可单独标记为 partial。
- **Mentions**：提交通知所需的 canonical mentions MUST 仍在 Message metadata / encrypted metadata 中，MUST NOT 要求服务端扫描 Blob。
- **Reply/quote**：引用 Message ID，不复制完整长正文。
- **Push**：MUST NOT 把 Blob 正文发送给 push provider；沿用 blind/visible profile 边界。
- **Redaction / expiry**：Message 不可见后 MUST 同步使 fallback、搜索索引、缓存和 Blob 访问失效；Blob GC 沿用现有引用追踪。
- **Range**：E2EE 按 AEAD segment 边界请求并验证。
- **Offline**：实现 MAY 只缓存 fallback；缓存完整正文 MUST 受 Realm / Message 生命周期清理。

未知 `ak.content.long_text` 的客户端按 §7.2 的 unknown-kind fallback：展示已认证 `body`，MUST NOT 把未知字段解释成 executable content，也 MUST NOT 假装正文完整。

客户端在提交 Message 前 MUST 完成 Blob 上传并取得稳定 hash ref；引用不存在、digest 不符、无权访问或 E2EE descriptor 不完整时按现有 Blob / Content 校验错误拒绝。

### 4.1.6 明确否决

1. 给 `ak.content.text` 加可选 `body_ref`，形成两种语义；
2. 提高 Event 1 MiB 上限来容纳正文；
3. 多个 Message chunk 拼成一条逻辑 Message；
4. 复用 `ak.content.file` 表达消息正文；
5. 用 `ak.content.composite` 切段，破坏搜索 / quote / redaction 身份；
6. 允许 UUID `blob_ref` 并另猜内容是否被承诺；
7. `text/plain; charset=utf-8` 形态的 media type；
8. long text 支持 `prosemirror_json`；
9. E2EE long text 任意选择 whole-file 或 streaming AEAD；
10. 只用 JSON Schema `maxLength` 声称执行了 UTF-8 byte limit。

### 4.2 图片消息 `ak.content.image`

```json
{
  "kind": "ak.content.image",
  "body": "screenshot.png",
  "blob_ref": "ak:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "mime_type": "image/png",
  "width": 1920,
  "height": 1080,
  "size_bytes": 204800,
  "thumbnail": {
    "blob_ref": "ak:blob:sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "mime_type": "image/webp",
    "width": 320,
    "height": 180,
    "size_bytes": 12400
  },
  "alt_text": "Release dashboard showing 3 critical issues"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `blob_ref` | string | MUST | Blob 内容地址 |
| `mime_type` | string | MUST | MIME 类型 |
| `width` | integer | SHOULD | 像素宽度 |
| `height` | integer | SHOULD | 像素高度 |
| `size_bytes` | integer | SHOULD | 字节数 |
| `thumbnail` | object | SHOULD | 缩略图信息 |
| `alt_text` | string | SHOULD | 无障碍访问文本描述 |

### 4.3 视频消息 `ak.content.video`

```json
{
  "kind": "ak.content.video",
  "body": "demo-recording.mp4",
  "blob_ref": "ak:blob:sha256:cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc",
  "mime_type": "video/mp4",
  "width": 1280,
  "height": 720,
  "duration_ms": 45000,
  "size_bytes": 10485760,
  "thumbnail": {
    "blob_ref": "ak:blob:sha256:dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd",
    "mime_type": "image/jpeg",
    "width": 320,
    "height": 180
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `duration_ms` | integer | SHOULD | 视频时长（毫秒） |

### 4.4 音频消息 `ak.content.audio`

```json
{
  "kind": "ak.content.audio",
  "body": "voice-memo.ogg",
  "blob_ref": "ak:blob:sha256:eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee",
  "mime_type": "audio/ogg",
  "duration_ms": 12000,
  "size_bytes": 96000,
  "waveform": [10, 25, 48, 62, 55, 30, 15, 8]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `waveform` | integer[] | MAY | 波形预览数据（0-100 的整数数组，用于 UI 渲染） |

### 4.5 文件消息 `ak.content.file`

```json
{
  "kind": "ak.content.file",
  "body": "Q2-financial-report.pdf",
  "blob_ref": "ak:blob:sha256:ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff",
  "mime_type": "application/pdf",
  "size_bytes": 2097152,
  "filename": "Q2-financial-report.pdf"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `filename` | string | MUST | 原始文件名 |

### 4.6 位置消息 `ak.content.location`

```json
{
  "kind": "ak.content.location",
  "body": "Meeting point: 37.7749° N, 122.4194° W",
  "geo_uri": "geo:37.7749,-122.4194",
  "label": "San Francisco Office",
  "description": "Main entrance, 2nd floor lobby"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `geo_uri` | string | MUST | RFC 5870 Geo URI |
| `label` | string | SHOULD | 地点名称 |
| `description` | string | MAY | 地点补充描述 |

### 4.7 代码块消息 `ak.content.code`

用于分享代码片段：

```json
{
  "kind": "ak.content.code",
  "body": "fn main() { println!(\"hello\"); }",
  "language": "rust",
  "code": "fn main() {\n    println!(\"hello\");\n}"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `language` | string | SHOULD | 编程语言标识（用于语法高亮） |
| `code` | string | MUST | 代码文本内容 |

### 4.8 通知消息 `ak.content.notice`

由系统或 Bot/Agent 生成的通知性消息，客户端 SHOULD 通过可感知的 presentation invariant 与用户撰写消息区分；具体样式、控件和文案属于实现自由：

```json
{
  "kind": "ak.content.notice",
  "body": "Agent completed task: Review legal docs",
  "format": "markdown",
  "formatted_body": "Agent completed task: **Review legal docs** [done]"
}
```

### 4.9 投票消息 `ak.content.poll`

根据去中心化协作需求，投票也是一种标准内容块：

```json
{
  "kind": "ak.content.poll",
  "body": "What should we order for the party?",
  "poll": {
    "kind": "disclosed",
    "max_selections": 1,
    "question": {
      "kind": "ak.content.text",
      "body": "What should we order for the party?"
    },
    "answers": [
      { "id": "pizza", "text": { "kind": "ak.content.text", "body": "Pizza 🍕" } },
      { "id": "poutine", "text": { "kind": "ak.content.text", "body": "Poutine 🍟" } }
    ]
  }
}
```

`poll` block 字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `kind` | const `ak.content.poll` | MUST | content block 判别。 |
| `body` | `string` | MUST | fallback 文本，用于不支持 poll 渲染的客户端。 |
| `poll.kind` | `string` | MUST | 计票披露模式；封闭枚举，v1 仅 `disclosed` 一个取值（schema 为 `const`），以 `ak.content.poll` content-block schema 为权威源，客户端 MUST NOT 自行扩展。 |
| `poll.max_selections` | `integer`（≥ 1） | MUST | 单次响应最多可选 answer 数。 |
| `poll.question` | content block | MAY | 题干富文本；省略时以 `body` 为题。 |
| `poll.answers[]` | `array` | MUST | 候选项数组，每项 `{ id: string, text: content block }`；`id` 在同一 poll 内 MUST 唯一。 |

`ak.content.poll.response` block 字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `kind` | const `ak.content.poll.response` | MUST | content block 判别。 |
| `body` | `string` | MUST | fallback 文本。 |
| `poll_response.poll_ref` | `id:message` | MUST | 指向承载该 poll 的 Message。 |
| `poll_response.selections` | `array<string>` | MUST | 所选 answer `id` 列表；数量 MUST ≤ 对应 poll 的 `max_selections`。 |

响应投票时，客户端发送 `ak.content.poll.response` Content Block，最小形态为 `{ "kind": "ak.content.poll.response", "body": <fallback>, "poll_response": { "poll_ref": id:message, "selections": array<string> } }`，其中 `poll_ref` 指向承载该 poll 的 Message，`selections` 列出所选 answer `id`（数量 MUST ≤ 对应 poll 的 `max_selections`）。该 block 的 canonical schema 与 `poll` block 一同定义在 `ak.content.poll` 的 content-block schema（见 [`../conformance/schema-registry.md`](../conformance/schema-registry.md) 与 `artifacts/schemas/` 下的 content-block schema）。投票的权威计票仍按 §9 v1 扩展规则由 `poll` Morph / Relation / event reducer 承担，content block 只作为入口或摘要。

### 4.10 复合消息 `ak.content.composite`

当一条消息包含多种内容（如文字说明 + 图片 + 文件附件）时使用：

```json
{
  "kind": "ak.content.composite",
  "body": "Here's the updated design with the spec PDF attached.",
  "parts": [
    {
      "kind": "ak.content.text",
      "body": "Here's the updated design with the spec PDF attached.",
      "format": "markdown"
    },
    {
      "kind": "ak.content.image",
      "body": "design-v3.png",
      "blob_ref": "ak:blob:sha256:1111111111111111111111111111111111111111111111111111111111111111",
      "mime_type": "image/png",
      "width": 1920,
      "height": 1080
    },
    {
      "kind": "ak.content.file",
      "body": "spec-v3.pdf",
      "blob_ref": "ak:blob:sha256:2222222222222222222222222222222222222222222222222222222222222222",
      "mime_type": "application/pdf",
      "size_bytes": 1048576,
      "filename": "spec-v3.pdf"
    }
  ]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `parts` | ContentBlock[] | MUST | 按展示顺序排列的 Content Block 数组。`parts` 是 `ak.content.composite` 的 canonical wire 字段名；旧拼写 `blocks` MUST 被 schema 以 `schema_violation` 拒绝（见 [`spec/v1/artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。 |

## 5. Mixin 机制 (附加属性)

参考 Matrix 的 Extensible Events (MSC1767) 理念，某些修饰性状态（Mixins）可以附加到任何 `Content Block` 上，改变其渲染或处理行为，但不改变其核心类型。

例如：`automated` 标志表明该消息是由 Bot 自动生成的，`spoiler` 标志表明内容包含剧透。

```json
{
  "kind": "ak.content.text",
  "body": "Daily build succeeded.",
  "mixins": {
    "ak.automated": true
  }
}
```

## 6. 引用与回复 (Reply)

### 6.1 回复关联

回复通过 Relation 表达（`message --replies_to--> message`），但为了渲染方便，消息的 `content` 中 MAY 内嵌引用上下文：

```json
{
  "kind": "ak.content.text",
  "body": "> Alice: 这个方案可行吗？\n\n我觉得需要再评估一下风险。",
  "format": "markdown",
  "reply_context": {
    "message_ref": "ak:message:01964200-0000-7000-8000-000000000129",
    "sender_actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
    "excerpt": "这个方案可行吗？"
  }
}
```

### 6.2 Fallback 规则

- `reply_context` 是**渲染提示 (Rendering Hint)**，不是真相源。真正的回复关系由 `replies_to` Relation 决定。
- 若客户端在本地缓存/搜索索引中已有原消息，SHOULD 优先使用本地数据渲染引用块，忽略 `reply_context.excerpt`。
- 若客户端无法获取原消息（例如跨 Realm 引用或权限限制），则使用 `reply_context.excerpt` 做降级展示。

## 7. 自定义与扩展类型

### 7.1 命名空间约定

- 标准类型使用 `ak.content.*` 前缀
- 第三方扩展使用反向域名前缀，例如 `com.acme.content.poll`

### 7.2 未知类型的处理

客户端遇到不认识的 `kind` 时：
1. MUST NOT 丢弃该消息
2. SHOULD 使用 `body` 字段做纯文本降级展示
3. MAY 显示"不支持的消息类型"提示

## 8. 与 E2EE 的交互

在端到端加密场景下：
- `content` 字段的完整 JSON 对象被加密为 `encrypted_content`
- `encrypted_content` MUST 符合 `artifacts/schemas/encrypted-envelope.schema.json`；`ak.message.create` / `ak.message.revise` 和 Strand synthesis `content` 使用同一 canonical envelope；没有 `content` 明文对偶的 payload surface MAY 继续使用通用 `encrypted_payload`
- `body` 字段在密文信封中**不保留明文副本**（防止元数据泄露）
- 用于推送通知的脱敏摘要由发送者的客户端单独生成并附在明文元数据中（参见 `push-notifications.md`）

## 9. v1 扩展规则

- Emoji / Sticker MUST 作为 `ak.content.image`、`ak.content.file` 或注册的 `ak.content.sticker` block 表达，并引用 content-addressed blob；客户端不得从未授权 URL 热加载私有表情资源。
- 投票 / 表单等交互式消息 SHOULD 使用 `poll` Morph、Relation 和 event reducer 表达；消息中的 content block 只能作为入口或摘要，不能成为唯一计票真相源。
- URL 预览 MUST 作为可丢弃的 rendering hint 或受控 preview blob 表达。服务端抓取私有链接前必须有用户或 Realm policy 授权，预览服务若接触正文或页面内容，MUST 列入 `plaintext_visible_services`。
- E2EE 场景下缩略图 SHOULD 由客户端生成并加密上传；服务端生成缩略图前必须被声明为 plaintext-visible service，并遵守 `media-and-blob.md` 的 MIME、缓存和授权规则。
