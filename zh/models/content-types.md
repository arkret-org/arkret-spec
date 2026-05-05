# Content Types

## 1. 目标

Contrix 的 `message` 标准对象、Flow synthesis / discussion 和可讨论的 Morph 需要承载远比纯文本丰富的内容，包括图片、视频、文件、代码块、地理位置等。本规范定义了结构化的**内容类型系统 (Content Type System)**，使得：

- 所有客户端能够以一致的方式渲染各种消息类型
- 不支持某种内容类型的客户端能通过 `fallback_text` 优雅降级
- E2EE 场景下加密信封只包裹 `content` / `body` / `attachments` 等业务内容，不影响路由元数据

## 2. 设计原则

### 2.1 Content 是结构化的，不是裸字符串

Message 的 `content` 字段、`cx.message.create` / `cx.message.revise` Event Envelope 的 `payload.content` 或 `payload.encrypted_payload` 字段、Flow 的 `body` / `encrypted_payload` 字段、Flow discussion 摘要以及 Morph 的 `content` / `encrypted_payload` 字段 MUST 使用本规范定义的结构化 JSON 格式或其 canonical encrypted envelope，而非依赖客户端猜测渲染方式。

### 2.2 单一 Content Block 架构

每条消息的 `content` 字段是一个 **Content Block** 对象，包含：
- `type`：内容类型标识
- `body`：人类可读的纯文本摘要 / fallback
- 类型相关的专有字段

`cx.message.create` / `cx.message.revise` 的未加密 Event payload MUST 将这个对象放在 `payload.content` 字段中；E2EE payload MUST 将同一对象加密后放在 `payload.encrypted_payload`。`flow_id`、`message_id`、`reply_to`、`blob_refs` 等字段是 envelope / reducer metadata，不能把消息正文直接写成 payload 顶层 `body`。

### 2.3 复合消息使用 `composite` 类型

当一条消息需要同时包含文本和图片（例如带说明文字的截图），使用 `composite` 类型将多个 Content Block 组合。

## 3. Content Block 通用结构

```json
{
  "type": "cx.content.<type_name>",
  "body": "纯文本 fallback，用于通知、搜索索引和不支持该类型的客户端",
  // ... 类型专有字段
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `type` | string | MUST | 内容类型标识符 |
| `body` | string | MUST | 纯文本 fallback |

## 4. 标准内容类型

### 4.1 文本消息 `cx.content.text`

最基础的消息类型。

```json
{
  "type": "cx.content.text",
  "body": "@bob 请确认这个 item 的 legal 风险。",
  "format": "markdown",
  "formatted_body": "<mention did=\"did:web:bob.example.com\">@bob</mention> 请确认这个 item 的 legal 风险。"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `format` | string | SHOULD | 格式化类型：`plain`, `markdown`, `prosemirror_json` |
| `formatted_body` | string/object | 可选 | 结构化的富文本内容（当 format 不为 plain 时使用） |

### 4.2 图片消息 `cx.content.image`

```json
{
  "type": "cx.content.image",
  "body": "screenshot.png",
  "blob_ref": "cx:blob:sha256:a1b2c3...",
  "mime_type": "image/png",
  "width": 1920,
  "height": 1080,
  "size": 204800,
  "thumbnail": {
    "blob_ref": "cx:blob:sha256:d4e5f6...",
    "mime_type": "image/webp",
    "width": 320,
    "height": 180,
    "size": 12400
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
| `size` | integer | SHOULD | 字节数 |
| `thumbnail` | object | SHOULD | 缩略图信息 |
| `alt_text` | string | SHOULD | 无障碍访问文本描述 |

### 4.3 视频消息 `cx.content.video`

```json
{
  "type": "cx.content.video",
  "body": "demo-recording.mp4",
  "blob_ref": "cx:blob:sha256:b2c3d4...",
  "mime_type": "video/mp4",
  "width": 1280,
  "height": 720,
  "duration_ms": 45000,
  "size": 10485760,
  "thumbnail": {
    "blob_ref": "cx:blob:sha256:e5f6a7...",
    "mime_type": "image/jpeg",
    "width": 320,
    "height": 180
  }
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `duration_ms` | integer | SHOULD | 视频时长（毫秒） |

### 4.4 音频消息 `cx.content.audio`

```json
{
  "type": "cx.content.audio",
  "body": "voice-memo.ogg",
  "blob_ref": "cx:blob:sha256:c3d4e5...",
  "mime_type": "audio/ogg",
  "duration_ms": 12000,
  "size": 96000,
  "waveform": [10, 25, 48, 62, 55, 30, 15, 8]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `waveform` | integer[] | 可选 | 波形预览数据（0-100 的整数数组，用于 UI 渲染） |

### 4.5 文件消息 `cx.content.file`

```json
{
  "type": "cx.content.file",
  "body": "Q2-financial-report.pdf",
  "blob_ref": "cx:blob:sha256:d4e5f6...",
  "mime_type": "application/pdf",
  "size": 2097152,
  "filename": "Q2-financial-report.pdf"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `filename` | string | MUST | 原始文件名 |

### 4.6 位置消息 `cx.content.location`

```json
{
  "type": "cx.content.location",
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
| `description` | string | 可选 | 地点补充描述 |

### 4.7 代码块消息 `cx.content.code`

用于分享代码片段：

```json
{
  "type": "cx.content.code",
  "body": "fn main() { println!(\"hello\"); }",
  "language": "rust",
  "code": "fn main() {\n    println!(\"hello\");\n}"
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `language` | string | SHOULD | 编程语言标识（用于语法高亮） |
| `code` | string | MUST | 代码文本内容 |

### 4.8 通知消息 `cx.content.notice`

由系统或 Bot/Agent 生成的通知性消息，客户端 SHOULD 以视觉上区别于用户消息的样式渲染：

```json
{
  "type": "cx.content.notice",
  "body": "Agent completed task: Review legal docs",
  "format": "markdown",
  "formatted_body": "Agent completed task: **Review legal docs** ✅"
}
```

### 4.9 投票消息 `cx.content.poll`

根据去中心化协作需求（参考 MSC3381），投票也是一种标准内容块：

```json
{
  "type": "cx.content.poll",
  "body": "What should we order for the party?",
  "poll": {
    "kind": "disclosed",
    "max_selections": 1,
    "question": {
      "type": "cx.content.text",
      "body": "What should we order for the party?"
    },
    "answers": [
      { "id": "pizza", "text": { "type": "cx.content.text", "body": "Pizza 🍕" } },
      { "id": "poutine", "text": { "type": "cx.content.text", "body": "Poutine 🍟" } }
    ]
  }
}
```

响应投票时，客户端发送 `cx.content.poll.response`，包含所选 `id`。

### 4.10 复合消息 `cx.content.composite`

当一条消息包含多种内容（如文字说明 + 图片 + 文件附件）时使用：

```json
{
  "type": "cx.content.composite",
  "body": "Here's the updated design with the spec PDF attached.",
  "parts": [
    {
      "type": "cx.content.text",
      "body": "Here's the updated design with the spec PDF attached.",
      "format": "markdown"
    },
    {
      "type": "cx.content.image",
      "body": "design-v3.png",
      "blob_ref": "cx:blob:sha256:aaa...",
      "mime_type": "image/png",
      "width": 1920,
      "height": 1080
    },
    {
      "type": "cx.content.file",
      "body": "spec-v3.pdf",
      "blob_ref": "cx:blob:sha256:bbb...",
      "mime_type": "application/pdf",
      "size": 1048576,
      "filename": "spec-v3.pdf"
    }
  ]
}
```

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `parts` | ContentBlock[] | MUST | 按展示顺序排列的 Content Block 数组 |

## 5. Mixin 机制 (附加属性)

参考 Matrix 的 Extensible Events (MSC1767) 理念，某些修饰性状态（Mixins）可以附加到任何 `Content Block` 上，改变其渲染或处理行为，但不改变其核心类型。

例如：`automated` 标志表明该消息是由 Bot 自动生成的，`spoiler` 标志表明内容包含剧透。

```json
{
  "type": "cx.content.text",
  "body": "Daily build succeeded.",
  "mixins": {
    "cx.automated": true
  }
}
```

## 6. 引用与回复 (Reply)

### 6.1 回复关联

回复通过 Relation 表达（`message --replies_to--> message`），但为了渲染方便，消息的 `content` 中 MAY 内嵌引用上下文：

```json
{
  "type": "cx.content.text",
  "body": "> Alice: 这个方案可行吗？\n\n我觉得需要再评估一下风险。",
  "format": "markdown",
  "reply_context": {
    "ref": "cx:message:01js1000000000000000000099",
    "sender": "did:web:alice.example.com",
    "excerpt": "这个方案可行吗？"
  }
}
```

### 6.2 Fallback 规则

- `reply_context` 是**渲染提示 (Rendering Hint)**，不是真相源。真正的回复关系由 `replies_to` Relation 决定。
- 若客户端在本地缓存/搜索索引中已有原消息，SHOULD 优先使用本地数据渲染引用块，忽略 `reply_context.excerpt`。
- 若客户端无法获取原消息（例如跨 Space 引用或权限限制），则使用 `reply_context.excerpt` 做降级展示。

## 7. 自定义与扩展类型

### 7.1 命名空间约定

- 标准类型使用 `cx.content.*` 前缀
- 第三方扩展使用反向域名前缀，例如 `com.acme.content.poll`

### 7.2 未知类型的处理

客户端遇到不认识的 `type` 时：
1. MUST NOT 丢弃该消息
2. SHOULD 使用 `body` 字段做纯文本降级展示
3. MAY 显示"不支持的消息类型"提示

## 8. 与 E2EE 的交互

在端到端加密场景下：
- `content` 字段的完整 JSON 对象被加密为 `encrypted_payload`
- `encrypted_payload` MUST 符合 `artifacts/schemas/encrypted-envelope.schema.json`；`cx.message.create` / `cx.message.revise`、Flow synthesis `body` 和 Morph `content` 使用同一 canonical envelope
- `body` 字段在密文信封中**不保留明文副本**（防止元数据泄露）
- 用于推送通知的脱敏摘要由发送者的客户端单独生成并附在明文元数据中（参见 `push-notifications.md`）

## 9. v1 扩展规则

- Emoji / Sticker MUST 作为 `cx.content.image`、`cx.content.file` 或注册的 `cx.content.sticker` block 表达，并引用 content-addressed blob；客户端不得从未授权 URL 热加载私有表情资源。
- 投票 / 表单等交互式消息 SHOULD 使用 `poll` Morph、Relation 和 event reducer 表达；消息中的 content block 只能作为入口或摘要，不能成为唯一计票真相源。
- URL 预览 MUST 作为可丢弃的 rendering hint 或受控 preview blob 表达。服务端抓取私有链接前必须有用户或 Space policy 授权，预览服务若接触正文或页面内容，MUST 列入 `plaintext_visible_services`。
- E2EE 场景下缩略图 SHOULD 由客户端生成并加密上传；服务端生成缩略图前必须被声明为 plaintext-visible service，并遵守 `media-and-blob.md` 的 MIME、缓存和授权规则。
