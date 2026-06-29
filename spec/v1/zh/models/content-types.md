---
title: Content Types
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

> 体例说明：本文件字段表的「必填 / 必需」列采用 RFC 关键字（MUST / SHOULD / MAY）表达，区别于其余 models 对象表使用的 `yes / no / conditional` 体例；二者语义对应关系为 MUST↔yes、MAY↔no、SHOULD/条件性↔conditional。

## 1. 目标

Cokret 的 `message` 标准对象、Strand synthesis / discussion 和可讨论的 Morph 需要承载远比纯文本丰富的内容，包括图片、视频、文件、代码块、地理位置等。本规范定义了结构化的**内容类型系统 (Content Type System)**，使得：

- 所有客户端能够以一致的方式渲染各种消息类型
- 不支持某种内容类型的客户端能通过 `fallback_text` 优雅降级
- E2EE 场景下加密信封 (`encrypted_content`) 只包裹 Message 顶层的 `content`（即整个 Content Block 对象，包括其内部的 `body` 字段）和 `attachments` 等业务字段，`strand_id` / `created_by` 等路由与归因 metadata 保持明文

## 2. 设计原则

### 2.1 Content 是结构化的，不是裸字符串

Message 的 `content` 字段、`ck.message.create` / `ck.message.revise` Event Envelope 的 `payload.content` 或 `payload.encrypted_content` 字段、Strand 的 `content` / `encrypted_content` 字段、Strand discussion 摘要以及 Morph 的 `content` / `encrypted_content` 字段 MUST 使用本规范定义的结构化 JSON 格式或其 canonical encrypted envelope，而非依赖客户端猜测渲染方式。

### 2.2 单一 Content Block 架构

每条消息的 `content` 字段是一个 **Content Block** 对象，包含：
- `kind`：内容类型标识
- `body`：人类可读的纯文本摘要 / fallback
- 类型相关的专有字段

Message envelope 与 Content Block 的层级关系大致如下（Message 顶层完整 schema 见 [`strand-and-message.md` §9.2](./strand-and-message.md#92-schema-与字段)，本文件后续章节只讨论 `content` 内部结构）：

```json
{
  "id": "ck:message:...",
  "realm_id": "ck:realm:...",
  "strand_id": "ck:strand:...",
  "track_name": "discussion",
  "state": "active",
  "created_by": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z",

  "content": {
    "kind": "ck.content.text",
    "body": "纯文本 fallback",
    "format": "markdown",
    "formatted_body": "..."
  }
}
```

因此本文档示例里的 `kind` / `body` / `format` 等字段都是 **Content Block 内部字段**，位于 Message `content` 之下；不要与 Message 顶层字段混在一层理解。

`ck.message.create` / `ck.message.revise` 的未加密 Event payload MUST 将这个 Content Block 对象放在 `payload.content` 字段中；E2EE payload MUST 将同一对象加密后放在 `payload.encrypted_content`。`strand_id`、`blob_refs` 等字段是 envelope / reducer metadata（Message 主键是顶层 `id`，不是 `message_id`；回复关系由 `replies_to` Relation 表达，物化 Message 对象无 `reply_to` 标量字段——`ck.message.create` payload 可携带 `reply_to` 作为创建便利，reducer 据此记录该消息的回复指向并投影为 `replies_to` 关系，不要求单独的 canonical `ck.relation` 事件），不能把消息正文直接写成 payload 顶层 `body`。

这里的 `payload` 指 Event Envelope 的 kind-specific 业务载荷容器；`content` 指该 payload 内部写入 Message / Strand / Morph 正文字段的 Content Block，不是 `payload` 的同义词。

### 2.3 复合消息使用 `composite` 类型

当一条消息需要同时包含文本和图片（例如带说明文字的截图），使用 `composite` 类型将多个 Content Block 组合。

## 3. Content Block 通用结构

```json
{
  "kind": "ck.content.<kind_name>",
  "body": "纯文本 fallback，用于通知、搜索索引和不支持该类型的客户端"
}
```

类型专有字段以同级 key 形式追加到该对象上（例如 `format` / `formatted_body` 见 §4.1 文本消息示例）。

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `kind` | string | MUST | 内容类型标识符 |
| `body` | string | MUST | 纯文本 fallback |

## 4. 标准内容类型

### 4.1 文本消息 `ck.content.text`

最基础的消息类型。

```json
{
  "kind": "ck.content.text",
  "body": "@bob 请确认这个 item 的 legal 风险。",
  "format": "markdown",
  "formatted_body": "<mention did=\"did:web:bob.example\">@bob</mention> 请确认这个 item 的 legal 风险。"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `format` | string | SHOULD | 格式化类型：`plain`, `markdown`, `prosemirror_json` |
| `formatted_body` | string/object | MAY | 结构化的富文本内容（当 format 不为 plain 时使用） |

### 4.2 图片消息 `ck.content.image`

```json
{
  "kind": "ck.content.image",
  "body": "screenshot.png",
  "blob_ref": "ck:blob:sha256:a1b2c3...",
  "mime_type": "image/png",
  "width": 1920,
  "height": 1080,
  "size_bytes": 204800,
  "thumbnail": {
    "blob_ref": "ck:blob:sha256:d4e5f6...",
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

### 4.3 视频消息 `ck.content.video`

```json
{
  "kind": "ck.content.video",
  "body": "demo-recording.mp4",
  "blob_ref": "ck:blob:sha256:b2c3d4...",
  "mime_type": "video/mp4",
  "width": 1280,
  "height": 720,
  "duration_ms": 45000,
  "size_bytes": 10485760,
  "thumbnail": {
    "blob_ref": "ck:blob:sha256:e5f6a7...",
    "mime_type": "image/jpeg",
    "width": 320,
    "height": 180
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `duration_ms` | integer | SHOULD | 视频时长（毫秒） |

### 4.4 音频消息 `ck.content.audio`

```json
{
  "kind": "ck.content.audio",
  "body": "voice-memo.ogg",
  "blob_ref": "ck:blob:sha256:c3d4e5...",
  "mime_type": "audio/ogg",
  "duration_ms": 12000,
  "size_bytes": 96000,
  "waveform": [10, 25, 48, 62, 55, 30, 15, 8]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `waveform` | integer[] | MAY | 波形预览数据（0-100 的整数数组，用于 UI 渲染） |

### 4.5 文件消息 `ck.content.file`

```json
{
  "kind": "ck.content.file",
  "body": "Q2-financial-report.pdf",
  "blob_ref": "ck:blob:sha256:d4e5f6...",
  "mime_type": "application/pdf",
  "size_bytes": 2097152,
  "filename": "Q2-financial-report.pdf"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `filename` | string | MUST | 原始文件名 |

### 4.6 位置消息 `ck.content.location`

```json
{
  "kind": "ck.content.location",
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

### 4.7 代码块消息 `ck.content.code`

用于分享代码片段：

```json
{
  "kind": "ck.content.code",
  "body": "fn main() { println!(\"hello\"); }",
  "language": "rust",
  "code": "fn main() {\n    println!(\"hello\");\n}"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `language` | string | SHOULD | 编程语言标识（用于语法高亮） |
| `code` | string | MUST | 代码文本内容 |

### 4.8 通知消息 `ck.content.notice`

由系统或 Bot/Agent 生成的通知性消息，客户端 SHOULD 以视觉上区别于用户消息的样式渲染：

```json
{
  "kind": "ck.content.notice",
  "body": "Agent completed task: Review legal docs",
  "format": "markdown",
  "formatted_body": "Agent completed task: **Review legal docs** [done]"
}
```

### 4.9 投票消息 `ck.content.poll`

根据去中心化协作需求，投票也是一种标准内容块：

```json
{
  "kind": "ck.content.poll",
  "body": "What should we order for the party?",
  "poll": {
    "kind": "disclosed",
    "max_selections": 1,
    "question": {
      "kind": "ck.content.text",
      "body": "What should we order for the party?"
    },
    "answers": [
      { "id": "pizza", "text": { "kind": "ck.content.text", "body": "Pizza 🍕" } },
      { "id": "poutine", "text": { "kind": "ck.content.text", "body": "Poutine 🍟" } }
    ]
  }
}
```

`poll` block 字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `kind` | const `ck.content.poll` | MUST | content block 判别。 |
| `body` | `string` | MUST | fallback 文本，用于不支持 poll 渲染的客户端。 |
| `poll.kind` | `string` | MUST | 计票披露模式；封闭枚举，v1 仅 `disclosed` 一个取值（schema 为 `const`），以 `ck.content.poll` content-block schema 为权威源，客户端 MUST NOT 自行扩展。 |
| `poll.max_selections` | `integer`（≥ 1） | MUST | 单次响应最多可选 answer 数。 |
| `poll.question` | content block | MAY | 题干富文本；省略时以 `body` 为题。 |
| `poll.answers[]` | `array` | MUST | 候选项数组，每项 `{ id: string, text: content block }`；`id` 在同一 poll 内 MUST 唯一。 |

`ck.content.poll.response` block 字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `kind` | const `ck.content.poll.response` | MUST | content block 判别。 |
| `body` | `string` | MUST | fallback 文本。 |
| `poll_response.poll_ref` | `id:message` | MUST | 指向承载该 poll 的 Message。 |
| `poll_response.selections` | `array<string>` | MUST | 所选 answer `id` 列表；数量 MUST ≤ 对应 poll 的 `max_selections`。 |

响应投票时，客户端发送 `ck.content.poll.response` Content Block，最小形态为 `{ "kind": "ck.content.poll.response", "body": <fallback>, "poll_response": { "poll_ref": id:message, "selections": array<string> } }`，其中 `poll_ref` 指向承载该 poll 的 Message，`selections` 列出所选 answer `id`（数量 MUST ≤ 对应 poll 的 `max_selections`）。该 block 的 canonical schema 与 `poll` block 一同定义在 `ck.content.poll` 的 content-block schema（见 [`../conformance/schema-registry.md`](../conformance/schema-registry.md) 与 `artifacts/schemas/` 下的 content-block schema）。投票的权威计票仍按 §9 v1 扩展规则由 `poll` Morph / Relation / event reducer 承担，content block 只作为入口或摘要。

### 4.10 复合消息 `ck.content.composite`

当一条消息包含多种内容（如文字说明 + 图片 + 文件附件）时使用：

```json
{
  "kind": "ck.content.composite",
  "body": "Here's the updated design with the spec PDF attached.",
  "parts": [
    {
      "kind": "ck.content.text",
      "body": "Here's the updated design with the spec PDF attached.",
      "format": "markdown"
    },
    {
      "kind": "ck.content.image",
      "body": "design-v3.png",
      "blob_ref": "ck:blob:sha256:aaa...",
      "mime_type": "image/png",
      "width": 1920,
      "height": 1080
    },
    {
      "kind": "ck.content.file",
      "body": "spec-v3.pdf",
      "blob_ref": "ck:blob:sha256:bbb...",
      "mime_type": "application/pdf",
      "size_bytes": 1048576,
      "filename": "spec-v3.pdf"
    }
  ]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `parts` | ContentBlock[] | MUST | 按展示顺序排列的 Content Block 数组。`parts` 是 `ck.content.composite` 的 canonical wire 字段名；旧拼写 `blocks` MUST 被 schema 以 `schema_violation` 拒绝（见 [`spec/v1/artifacts/registry/forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json)）。 |

## 5. Mixin 机制 (附加属性)

参考 Matrix 的 Extensible Events (MSC1767) 理念，某些修饰性状态（Mixins）可以附加到任何 `Content Block` 上，改变其渲染或处理行为，但不改变其核心类型。

例如：`automated` 标志表明该消息是由 Bot 自动生成的，`spoiler` 标志表明内容包含剧透。

```json
{
  "kind": "ck.content.text",
  "body": "Daily build succeeded.",
  "mixins": {
    "ck.automated": true
  }
}
```

## 6. 引用与回复 (Reply)

### 6.1 回复关联

回复通过 Relation 表达（`message --replies_to--> message`），但为了渲染方便，消息的 `content` 中 MAY 内嵌引用上下文：

```json
{
  "kind": "ck.content.text",
  "body": "> Alice: 这个方案可行吗？\n\n我觉得需要再评估一下风险。",
  "format": "markdown",
  "reply_context": {
    "ref": "ck:message:01964200-0000-7000-8000-000000000129",
    "sender_actor_id": "did:web:alice.example",
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

- 标准类型使用 `ck.content.*` 前缀
- 第三方扩展使用反向域名前缀，例如 `com.acme.content.poll`

### 7.2 未知类型的处理

客户端遇到不认识的 `kind` 时：
1. MUST NOT 丢弃该消息
2. SHOULD 使用 `body` 字段做纯文本降级展示
3. MAY 显示"不支持的消息类型"提示

## 8. 与 E2EE 的交互

在端到端加密场景下：
- `content` 字段的完整 JSON 对象被加密为 `encrypted_content`
- `encrypted_content` MUST 符合 `artifacts/schemas/encrypted-envelope.schema.json`；`ck.message.create` / `ck.message.revise` 和 Strand synthesis `content` 使用同一 canonical envelope；没有 `content` 明文对偶的 payload surface MAY 继续使用通用 `encrypted_payload`
- `body` 字段在密文信封中**不保留明文副本**（防止元数据泄露）
- 用于推送通知的脱敏摘要由发送者的客户端单独生成并附在明文元数据中（参见 `push-notifications.md`）

## 9. v1 扩展规则

- Emoji / Sticker MUST 作为 `ck.content.image`、`ck.content.file` 或注册的 `ck.content.sticker` block 表达，并引用 content-addressed blob；客户端不得从未授权 URL 热加载私有表情资源。
- 投票 / 表单等交互式消息 SHOULD 使用 `poll` Morph、Relation 和 event reducer 表达；消息中的 content block 只能作为入口或摘要，不能成为唯一计票真相源。
- URL 预览 MUST 作为可丢弃的 rendering hint 或受控 preview blob 表达。服务端抓取私有链接前必须有用户或 Realm policy 授权，预览服务若接触正文或页面内容，MUST 列入 `plaintext_visible_services`。
- E2EE 场景下缩略图 SHOULD 由客户端生成并加密上传；服务端生成缩略图前必须被声明为 plaintext-visible service，并遵守 `media-and-blob.md` 的 MIME、缓存和授权规则。
