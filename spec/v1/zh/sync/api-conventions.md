---
title: HTTP/JSON Binding 通用约定
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 默认 HTTP/JSON binding 的线级约定。  
Cokret 协议核心不强绑定 REST API；核心操作、消息 envelope 与 transport binding 的关系见 `transport-bindings.md`。

各服务面可以扩展自己的 HTTP endpoint，但 MUST 遵守本文的基础规则，除非对应文档明确说明例外。非 HTTP binding（例如 gRPC、WebSocket、SSE、libp2p、message queue）MUST 提供语义等价的认证、授权、幂等、分页、错误和流控语义。

本文作为默认 HTTP binding 适用于：

- identity registry
- events
- Sync Service
- blob
- authz
- push gateway
- federation endpoint

## 2. HTTP 传输与编码

### 2.1 HTTPS

生产环境 API endpoint MUST 使用 HTTPS。  
明文 HTTP 只允许用于本地开发、测试网络或受控内网模拟环境。

### 2.2 JSON 编码

所有 JSON request / response MUST 使用 UTF-8。

Cokret canonical JSON 字段名 MUST 使用小写字母与下划线连接，例如：

- `realm_id`
- `event_id`
- `service_endpoint`
- `verification_method`
- `retry_after_ms`
- `reconnect_after_ms`

Raw 外部标准文档 MUST 保留外部标准字段名，例如 W3C DID Core 的 `verificationMethod` / `alsoKnownAs` / `serviceEndpoint` 和 VC 的 `credentialSubject`。Cokret normalized view、索引、policy input 和 reducer input MAY 使用 snake_case 派生字段，但这些派生字段不得作为 raw DID / VC 文档重新输出。

### 2.3 Content-Type

含 JSON body 的请求 SHOULD 设置：

```text
Content-Type: application/json
```

JSON response MUST 设置：

```text
Content-Type: application/json
```

Blob 上传、媒体下载和二进制 stream MAY 使用其他 content type，但 metadata response 仍应使用 JSON。

注意：OpenAPI `content:` map 与 HTTP `Content-Type` 只表示 media type / body 编码，不是 Cokret Content Block 字段。协议正文内容仍按对象或 Event payload schema 使用 `content` / `encrypted_content`。

### 2.4 Operation ID 动词 taxonomy

标准 `operation_id` 的最后一个动词段 MUST 与以下 taxonomy 对齐；新增 operation 若不匹配，必须在 `contract-catalog.json` 的 operation notes 中说明理由。

| 动词 | 语义边界 |
| --- | --- |
| `get` | 单个已知资源的直接读取，通常由 path / query 中的单一 id 定位。 |
| `resolve` | 将 event id / hash、handle、invite token、alias、DID 或外部标识解析为 canonical object、proof 或可验证 projection。 |
| `query` | selector、filter、cursor 或 range scan；结果通常按时间、因果或索引顺序分页。 |
| `search` | 目录型关键词 / discovery 查询；结果受 discoverability、隐私和排名策略控制。 |
| `subscribe` | streaming delta、live tail 或长连接增量流。 |

HTTP method 不是 operation 动词来源：同一 `query` 语义可以有 GET query string 与 POST/body 两种 binding；这种情况必须标记为 binding variant，而不是发明新的抽象语义。

## 3. 认证

API 调用 SHOULD 使用以下方式之一：

- `Authorization: Bearer <session_token>`
- detached JWS request signature
- HTTP message signature
- mTLS，用于受控企业或服务间通信

无论采用哪种传输认证方式，协议层权限判断最终 MUST 回到：

- actor DID
- device / session / agent delegation
- capability grant
- Realm policy
- verified claim / attestation

服务端 MUST NOT 仅因 bearer token 存在就跳过 capability 检查。

认证材料 MUST 放在 header、HTTP Message Signature、mTLS 握手或明确的 signed proof body 中。服务端 MUST NOT 接受 query string、path segment 或 fragment 中的 session token、access token、API key、签名密钥、长期 capability 或等价长期认证材料。

规则：

- 带有 `access_token`、`session_token`、`api_key`、`auth`、`signature` 等 query 参数的受保护 endpoint 请求 MUST 被拒绝，除非对应 endpoint 明确把该字段定义为非认证业务参数。
- 拒绝时 SHOULD 返回 `unauthenticated` 或 `invalid_param`，并且不得把 query 中的敏感值写入普通访问日志。
- `cx.blob.presign` 是唯一标准 URL bearer 例外：它只能是单 blob、单用途、短时效、只读、可撤销的派生 token，不得等同于用户 session、API key 或长期 capability；完整约束见 [`../crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。
- 第三方邀请的 `#token=` fragment 是客户端 handoff，不是服务端认证入口。服务端不会收到 fragment；客户端读取后 MUST 通过 body / signed proof 提交 claim，并按 [`third-party-invites.md` §3.2](./third-party-invites.md) 清理 URL 与本地状态。

### 3.1 认证服务发现

认证与授权服务器可以分离。服务 describe / discovery 响应 SHOULD 公布认证 metadata，但不得把 OAuth/OIDC subject 当作 Cokret principal：

```json
{
  "auth_metadata": {
    "oauth_issuer": "https://auth.example.com",
    "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
    "supported_auth_methods": ["passkey", "oidc", "device_pairing", "recovery_challenge"],
    "token_endpoint_auth_methods": ["private_key_jwt", "client_secret_basic"],
    "supported_grant_types": ["authorization_code", "refresh_token"],
    "did_binding_methods": ["session_grant", "did_http_signature"],
    "required_audience": "https://server.example/api/v1"
  }
}
```

规则：

- `sub`、email、username 或 OAuth client id MUST NOT 直接作为 `actor_id`、grant subject 或 event sender。
- 登录成功后，客户端或认证网关 MUST 产生可验证的 session grant、device binding 或 DID proof，把 OAuth/OIDC session 绑定到 DID principal / device。
- Resource server MUST 校验 token audience、issuer、expiry、nonce / replay 防护和 session grant 状态。
- `supported_auth_methods` 只描述 service account 登录或恢复入口；它不改变 DID 控制权规则。密码、邮箱验证码和 OIDC session 必须通过 `did_binding_methods` 绑定到 DID / device 后才能用于协议写入。
- 当认证 metadata 变化时，服务 SHOULD 通过 feature discovery 版本或 DID service metadata hash 暴露变更，客户端不得静默沿用过期 issuer。

## 4. 标准响应 envelope

**v1 现状（normative）**：成功响应 MUST 直接返回 endpoint-specific JSON 对象（字段集由对应 endpoint 在 `service-http-binding.md` §2.3 / §2.4 与 `contract-catalog.json` 定义）；每个 operation MUST 在 `contract-catalog.json#operation_registry.operations[].success_shape_kind` 声明机器可读成功形态，供 SDK / conformance 工具判定。**不存在跨 endpoint 强制的统一 success envelope**。错误响应 MUST 使用 §5 的统一错误 envelope (`{"ok": false, "error": {...}}`)，但成功响应没有等价的"包裹后再返回"模式。

各 endpoint 当前实际使用的成功标记形态可分为三类，调用方应直接按 endpoint 文档判定：

- **`{ok: true, ...payload}`** — 简单 mutation (push / device_messages.put / applet.transactions / 等)；
- **`{status: enum, ...payload}`** — 批量提交语义复杂时 (events.submit `status ∈ {accepted, duplicate, partial}`、keys.backups.put `status ∈ {accepted, duplicate}`)；
- **裸字段直接返回** — 创建 / 解析类 (blob.upload `{blob_ref, size_bytes, ...}`、directory.announce `{announce_id, indexed_at, ...}`、account session grant 等)。

新增 endpoint 设计时建议:
- 简单 idempotent mutation 默认走 `{ok: true, ...payload}`；
- 批量 / 多结果路径走 `{status, accepted[], rejected[], ...}`；
- 创建 / 解析类直接返回构造好的对象，不另加包裹。

`{ok: true}` 与 `{deleted: true}` / `{accepted: true}` 等单 boolean 标记**等价**（历史命名差异），新设计统一使用 `ok`。

流式 endpoint MAY 使用 newline-delimited JSON、SSE 或 WebSocket frame，但每个 frame 仍 SHOULD 是独立 JSON 对象。`request_id` 字段（若返回）SHOULD 与请求侧的 idempotency / tracing id 对齐，但不作为 success/failure discriminator。成功建立的 subscribe stream 若需要指示客户端延迟重连，MUST 使用 control frame 上的 `reconnect_after_ms`；`retry_after_ms` 保留给错误响应、非 HTTP binding 的失败诊断或显式 retry 语义。

## 5. 标准错误响应

错误响应 MUST 使用统一 JSON 格式：

```json
{
  "ok": false,
  "error": {
    "code": "capability_denied",
    "message": "actor does not have cx.flow.update on this flow",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "ck:request:01964137-0000-7000-8000-000000000000"
}
```

`message` 用于开发者诊断，不应用于稳定程序逻辑。  
客户端 MUST 以 `code` 作为主要错误分类。

### 5.1 标准错误码

标准 `error.code` 与批处理/联邦响应中的逐项 `reason_code` 共享同一字符串命名空间。**Canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)：所有标准 code、HTTP 状态、scope (`response` / `endpoint` / `both`) 与简短描述均以该 registry 为准。新增、修改或废弃代码 MUST 先更新 registry；本文与 `service-http-binding.md` §9 不再维护并行表格。

实现使用要点（registry 之外的语义协议）：

- 错误语义必须使用单一标准 code。若请求体过大使用 `payload_too_large` / 413；若配额策略拒绝使用 `quota_exceeded` / 403。
- `stale_frontier` / 409 表示服务可用但本地因果前沿落后，客户端可等待或 backfill；服务故障、维护或无法追赶 frontier 时使用 `temporarily_unavailable` / 503 并 SHOULD 返回 `Retry-After`。
- 格式错误的 cursor 使用 `invalid_param` / 400；格式正确但已过期的 cursor 使用 `cursor_expired` / 410。
- `unsupported_feature` 用于 `Event.requirements.features[]` 与 `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `cx.*` Event kind。二者不得互相替代。
- `conflict` / 409 是抽象 base code；实现 SHOULD 返回 registry 中更精确的 409 子 code（`cas_conflict` / `causal_conflict` / `dependency_missing` / `discussion_track_disabled` / `duplicate_conflict` / `epoch_mismatch` / `key_unavailable` / `rank_exhausted` / `stale_frontier` / `state_mismatch` / `audit_receipt_invalidated`）。
- 加密 envelope 相关 422 子 code（`aad_digest_mismatch` / `payload_digest_mismatch`）见 `crypto-media/encryption-and-audit.md` §2.3.4。

CI（`tools/artifact_pipeline.py check`）MUST 校验仓库内所有出现的字面 error code 字符串都登记在 registry 中，并 MUST 校验 `operations-error-mapping.json` 的 `universal_codes` 与 `operation_specific[]` 不引用 registry 外的 code。

### 5.2 未知路径与错误方法

对 `/api/v1/*` 与 `/cokret/v1/*` 之下的请求，服务端 MUST 使用统一错误响应，不得返回 HTML、纯文本框架错误或实现栈信息。

规则：

- 未声明或未实现的路径 MUST 返回 HTTP `404` 与错误码 `unrecognized_endpoint`。
- 已知路径但 HTTP method 不受支持时 MUST 返回 HTTP `405` 与错误码 `method_not_allowed`，并 SHOULD 设置 `Allow` header。
- 这两类请求 MUST 在路由层终止，不得进入业务逻辑、写入队列、触发昂贵解析或产生可观察副作用。
- 客户端和联邦对端 MUST 使用 `describe.supported_operations`、OpenAPI 文档和 feature discovery 判断 endpoint 是否可用，不得根据非标准 404 body 做能力推断。

## 6. 幂等

所有写接口 MUST 支持幂等重试。

写入请求 SHOULD 携带以下之一：

- `event_id`
- `request_id`
- endpoint-specific `idempotency_key`

规则：

- 相同幂等键 + 相同 canonical request body MUST 返回与首次请求语义等价的结果。
- 相同幂等键 + 不同 canonical request body MUST 返回 `duplicate_conflict`。
- 服务端 SHOULD 记录幂等键与 canonical request hash；联邦与服务间写入 MUST 将该 hash 纳入签名 transcript 或 transaction replay cache。
- 服务端 SHOULD 记录幂等结果至少到相关 Event 被最终同步或过期。

## 7. Cursor（统一不透明 token）

Cokret v1 在所有需要不透明 token 的位置使用**单一** `cursor` 类型，wire 形态固定为 `ck:cursor:<base64url(canonical_json)>`，schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)。它统一承担增量同步、列表分页和写后读屏障所有用途。

cursor 内部包含一个 `purpose` 字段（客户端不解析；仅供 issuing 服务自检）：

| `purpose` | 用途 | 出现位置 |
| --- | --- | --- |
| `stream` | 增量同步 / 列表分页的位置承诺。可作为 `after` / `before` / `prev_cursor` / `next_cursor` 回传。 | `/account/subscribe` frame 的 `cursor` 与重连 `after=` 参数、`timeline.prev_cursor` / `next_cursor`、列表分页 `next_cursor`、`cx.events.query`（含联邦 pull 复用形态 `GET /api/v1/events?before=<cursor>`）的 `before` / `after` 请求参数与 `prev_cursor` / `next_cursor` 响应字段。 |
| `barrier` | 读己之所写（RYW）：要求 reader 在 frontier 覆盖某个具体 event 之前不返回结果。 | 写接口响应中的 `cursor` 字段、`X-Cokret-Wait-For` header。 |

### 7.0 `prev_cursor` / `next_cursor` 含义（绝对方向）

任何返回 cursor 对的响应（`cx.events.query`、列表分页等）使用统一的**绝对方向**约定；`/account/subscribe` frame 只返回单个 account stream cursor,用于下一次 `after=` 重连：

| 响应字段 | 含义 | 回传给下一次请求 |
| --- | --- | --- |
| `prev_cursor` | 朝**更旧事件 / 更早历史**方向的延续位置 | `cx.events.query` 的 `before=` 参数；分页 `before=<prev_cursor>` 取更旧一批 |
| `next_cursor` | 朝**更新事件 / 更晚未来**方向的延续位置 | `cx.events.query` 的 `after=` 参数；分页 `after=<next_cursor>` 取更新一批；或作为 catch-up subscribe 起点 |

绝对方向与请求时所用的参数（`before` / `after` / `order`）和 selector 无关；服务端 MUST 始终按上述含义填充。客户端因此**不**需要记录"上一次请求的 direction"才能正确解释响应 cursor。

规则：

- 客户端 MUST 把 cursor 当作不透明字符串，禁止解析以推断排序、权限或服务身份。
- 任何接受 cursor 的接口 MUST 把无效 cursor 返回 `invalid_param`，把已过期 cursor 返回 `cursor_expired`。
- 同一字符串 cursor 在不同 issuing 服务间不可移植；跨服务复用 MUST `invalid_param`。
- TTL 硬上限：barrier cursor `expires_at - issued_at` MUST ≤ 1 小时；stream cursor MUST ≤ 7 天。详见 [`encoding.md` §8.3 规则 12](../conformance/encoding.md)。
- 声明 `cursor_revoke_high_assurance` feature 的服务必须实现 [`client-sync.md` §12.2.1](./client-sync.md) 的 revocation set。已撤销但仍在 TTL 内的 cursor MUST 返回 `cursor_revoked`；完整性失败仍返回 `cursor_integrity_invalid`，不得泄露 revocation set。

### 7.1 列表分页（normative）

所有列表接口 MUST 返回三个字段：

```json
{
  "<items_field>": [],
  "next_cursor": "ck:cursor:...",
  "has_more": false
}
```

**`<items_field>` 命名约定** (normative)：
- 优先使用资源复数名（`realms[]` / `flows[]` / `morphs[]` / `spaces[]` / `backups[]` / `notifications[]` / `messages[]` 等）；
- 没有自然资源复数名时（mixed entity 搜索、private contact discovery 等），使用 `results[]`；
- **MUST NOT** 使用通用占位 `items[]`，也不得使用 `events[]` 作为非 Event 数组的字段名（device_messages 与 account subscribe `to_device` 的 `messages[]` 例外见 `cx.device_messages.get` 与 `cx.account.subscribe`）。

**`next_cursor` / `has_more`** (normative)：
- `next_cursor` 是 optional：缺省表示当前批次已经是末尾。
- `has_more: boolean` MUST 出现：客户端 MUST 仅按 `has_more` 决定是否继续翻页；不得仅靠 `next_cursor` 是否存在做判断（实现可能在末尾仍返回 `next_cursor` 用作 long-poll resume token）。

**`prev_cursor`**（可选, 双向分页）：仅当接口支持向"更旧"方向翻页时返回。详见 §7.0；不支持双向翻页的接口 MUST NOT 返回 `prev_cursor`。

**Cursor 方向参数** (`before` / `after`)：见 §3.3 与 §7.0。`before` / `after` 是绝对时间方向（朝更旧 / 朝更新），与响应 `prev_cursor` / `next_cursor` 形成一一对应；不应再引入 `from=` / `start_at=` 等同义别名。已有的 `cx.device_messages.get` `from?: cursor` 是历史例外，新增接口 MUST 用 `before` / `after`。

服务端 MAY 对 `limit` 设置上限。超过上限时 SHOULD 使用最大允许值或返回 `invalid_param`。

## 8. 读己之所写

写接口成功后 SHOULD 在响应中返回一个 barrier cursor：

```json
{
  "status": "accepted",
  "event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
  "cursor": "ck:cursor:..."
}
```

该 cursor 内部 `purpose=barrier`、`target.event_id` 与 `target.event_digest` 绑定到刚提交事件。后续读接口 SHOULD 接受：

```text
X-Cokret-Wait-For: <cursor>
```

如果服务在超时前到达该 cursor 描述的 causal frontier，则返回正常结果；否则 SHOULD 返回 `temporarily_unavailable` 或 `timeout`，并附带当前 frontier。stream cursor 不得用于 wait-for header；服务端遇到 `purpose=stream` 的 cursor 出现在 wait-for 上下文 MUST 返回 `invalid_param`。

**Wait-for canonical 与投影（normative）**：`X-Cokret-Wait-For` HTTP header 是 wait-for barrier 的 wire canonical 形态；[`../conformance/query-schema.md §2`](../conformance/query-schema.md) 嵌套形态 `consistency: { wait_for, timeout_ms }` 与 [`../../artifacts/openapi/cokret-service-api.openapi.yaml`](../../artifacts/openapi/cokret-service-api.openapi.yaml) request body 扁平字段 `wait_for: string` 是同义投影，三者等价绑定到同一 RYW (read-your-writes) barrier 语义。服务端 MUST 接受任一形态并解析为相同 cursor；客户端 MAY 选择任一形态。当同一请求同时出现多种形态且取值不一致时，服务端 MUST 按下列优先级解析：(1) `X-Cokret-Wait-For` header；(2) request body `wait_for`；(3) `consistency.wait_for`。

## 9. Rate Limit

服务 MAY 按以下维度限流：

- actor DID
- device id
- session id
- source IP
- Realm id
- endpoint
- blob byte quota

核心协议不定义全网统一的固定请求数下限；不同 sovereign、public federation、high-assurance 或离线 profile 可以有不同容量与滥用模型。但任何可被客户端或联邦对端调用的服务，MUST 通过 describe endpoint 暴露当前有效的限流配置，使对端能做自适应重试。

限流配置 MUST 使用 `rate_limit_policy` 内联对象，或使用 `rate_limit_policy_id` 指向可缓存、可验证的同等策略对象。策略至少包含：

- `policy_version` 或等价版本/hash。
- `entries[]`，每项绑定 `endpoint` 或 `operation_id`。
- 适用范围：`scope`，例如 actor DID、service DID、device id、source IP、Realm id 或 blob quota。
- 窗口与额度：`window_seconds`、`max_requests`、`burst`；若是字节或批量限制，使用 `max_bytes`、`max_events_per_batch`、`max_body_bytes`。
- 重试提示：`retry_after_ms`、`backoff_hint` 或 `next_retry_at` 的语义。
- `effective_at` / `expires_at` 或缓存 TTL；未知时客户端 MUST 按保守策略重试。

公开 describe MAY 只返回 coarse policy，避免暴露内部防滥用细节；认证后的 describe SHOULD 返回调用方当前可见的精确有效策略。ServiceDescribe MUST 携带 `rate_limit_policy` 或 `rate_limit_policy_id`；若服务除了通用滥用防护外没有可预期的端点级限流，也必须返回显式空策略（例如 `rate_limit_policy.entries=[]`），不得同时省略二者。一旦可能返回 `rate_limited`，就 MUST 暴露足够的策略信息供对端调度。

触发限流时 MUST 返回 `rate_limited`，并 SHOULD 附带：

```json
{
  "retry_after_ms": 2000
}
```

HTTP response MUST 同时设置 `Retry-After` header。`Retry-After` 的值按 HTTP 标准使用秒数或 HTTP date；若同时存在 `Retry-After` 与 `retry_after_ms`，客户端 MUST 优先使用 `Retry-After`。

规则：

- `429 rate_limited` MUST 设置 `Retry-After`。
- `503 temporarily_unavailable` SHOULD 在可预估恢复时间时设置 `Retry-After`。
- body 中的 `retry_after_ms` 用于非 HTTP binding 和精细诊断；其值 SHOULD 与 header 表达的时间一致。
- 客户端和对端服务 MUST 对同一 actor / service DID / endpoint 组合执行指数退避，避免重试放大。

## 10. CORS 与浏览器客户端

面向浏览器的服务 SHOULD 支持 CORS preflight。

推荐响应头：

```text
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Content-Digest, Digest, Idempotency-Key, X-Cokret-Wait-For, X-Cokret-Request-Id
Access-Control-Expose-Headers: Retry-After, Content-Digest, Digest, Content-Disposition, Content-Range, Location, X-Cokret-Request-Id
```

服务端 MUST NOT 在 `OPTIONS` preflight 请求中执行写入逻辑。

规则：

- `Access-Control-Allow-Methods` SHOULD 反映该服务实际支持的 method 集合；支持 `HEAD` 或 `PATCH` 的服务必须把它们列入 CORS。
- 服务端 MUST NOT 在 CORS 中允许 `CONNECT` 或 `TRACE`。
- 浏览器可访问的私有 endpoint 不得依赖 cookie 作为唯一认证方式；推荐使用 `Authorization` header 或 device-bound proof。
- 若响应使用 `Access-Control-Allow-Origin: *`，服务端 MUST NOT 同时设置 `Access-Control-Allow-Credentials: true`。需要 credentialed CORS 的部署 MUST 回显明确 allowlisted origin，并继续按 §3 要求校验 header / proof / capability，不得把 cookie 当作协议层 principal。
- Preflight、CORS error、redirect 与 4xx/5xx body 都不得泄露不可见 Realm、actor、member 或 blob 是否存在。

## 11. 版本与 feature discovery

每个服务 SHOULD 暴露 describe endpoint，返回：

- `protocol_version`
- `service_type`
- `service_did`
- `supported_features`
- `supported_profiles`
- `auth_metadata`
- `max_body_bytes`
- `limits`
- `rate_limit_policy`
- `rate_limit_policy_id`

客户端 MUST 根据 feature discovery 决定是否启用可选能力，不得假设所有节点都支持完整协议。

### 11.1 服务发现缓存与委托

服务 DID Document 中的 service endpoint 是服务身份与 endpoint 绑定的权威来源。域名级 bootstrap MAY 通过 `/.well-known/cokret/server` 或等价 signed metadata 暴露 endpoint 摘要，但接收方仍 MUST 校验：

- HTTPS/TLS 名称与返回的 endpoint 一致；
- service DID、DID Document service entry、describe 响应和 HTTP Message Signature 绑定一致；
- Realm policy 或 actor / organization service delegation 允许该服务角色；
- metadata hash / version 未被本地策略标记为撤销或过期。

服务发现结果 SHOULD 按 HTTP cache header 缓存。未提供显式缓存时间时，客户端 MAY 使用不超过 24 小时的默认 TTL；实现 SHOULD 对正缓存设置上限（建议不超过 48 小时），对失败缓存使用更短 TTL 或指数退避，避免一次临时故障长期破坏联邦。

### 11.2 出站网络目标策略与 SSRF 防护

任何服务在访问由用户、远端 peer、DID Document、Directory、Policy Server、Blob/Media metadata、Snapshot manifest、Applet/Agent endpoint、Webhook 或 service discovery 返回的 URL 之前，MUST 执行出站网络目标策略。该规则覆盖 DID resolution、联邦 push/pull/frontier probe、媒体抓取、thumbnail 生成、policy check、snapshot/chunk fetch、webhook、agent/applet handoff 以及等价的非 HTTP binding。

默认策略 MUST fail closed，并至少拒绝下列地址类别：

- IPv4 loopback、unspecified、private、link-local、carrier-grade NAT、benchmark、protocol-assignment、TEST-NET、multicast、reserved 与 broadcast 地址段，包括 `0.0.0.0/8`、`10.0.0.0/8`、`100.64.0.0/10`、`127.0.0.0/8`、`169.254.0.0/16`、`172.16.0.0/12`、`192.0.0.0/24`、`192.0.2.0/24`（TEST-NET-1）、`192.168.0.0/16`、`198.18.0.0/15`、`198.51.100.0/24`（TEST-NET-2）、`203.0.113.0/24`（TEST-NET-3）、`224.0.0.0/4`、`240.0.0.0/4` 和 `255.255.255.255/32`。
- IPv6 unspecified、loopback、IPv4-mapped private/loopback、unique-local、link-local、multicast 与 reserved 地址段，包括 `::/128`、`::1/128`、`::ffff:0:0/96` 中映射到上述禁止 IPv4 段的地址、`fc00::/7`、`fe80::/10` 和 `ff00::/8`。
- 用于承载 IPv4 的 IPv6 转换 / 隧道地址段，包括 `64:ff9b::/96`（NAT64 well-known prefix）、`2002::/16`（6to4）和 `2001::/32`（Teredo）。这些地址段内嵌 IPv4 目标，MUST 先解封内嵌的 IPv4 地址再按上述 IPv4 分类重新判定：NAT64 取低 32 bit、6to4 取 `2002:` 之后的 32 bit、Teredo 取末 32 bit（按位取反）作为映射的 IPv4 server/client 地址；解封后若命中任一禁止 IPv4 段（含 metadata endpoint）MUST fail-closed 拒绝，不得仅因外层 IPv6 前缀未在简单 denylist 中而放行。部署 policy 登记的其它 NAT64 prefix（非 well-known）MUST 同等解封并重新分类。
- 云厂商或容器环境 metadata endpoint，包括 `169.254.169.254`、`169.254.170.2` 以及部署 policy 登记的等价 IPv6 / DNS metadata 名称。

执行规则：

- 服务 MUST 在连接前解析目标 host 的所有候选 A/AAAA 记录，并对实际选用的 IP 执行上述分类；不得只检查原始 URL 字符串或裸域名。
- DNS 解析结果 MUST 与连接目标绑定。连接建立、重试、HTTP redirect、Alt-Svc、proxy CONNECT 或协议升级改变目标 host/IP 时，MUST 重新执行策略检查。
- 对返回多个地址的域名，只要某次连接候选命中禁止地址类别，该候选 MUST 被拒绝；实现不得在策略命中后静默切换到另一个地址并把失败隐藏为普通网络波动。
- HTTP redirect 默认不得跨 trust domain 放宽策略。redirect 目标 MUST 重新校验 scheme、host、port、DID/service binding 和出站网络策略。
- 明文 HTTP 到公网目标默认 SHOULD 拒绝；仅本地开发、测试网络或 Realm / deployment policy 明确授权的受控内网例外可放行。
- 允许访问私网或 link-local 的例外 MUST 是显式 policy：绑定用途、service DID、trust domain、CIDR、端口、过期时间和审计要求。`development_mode=true` 的 loopback 例外不得出现在生产 ServiceDescribe 或 verified profile claim 中。
- 拒绝时 SHOULD 返回 `policy_denied`，并在仅对 operator 可见的审计细节中记录被拦截的地址类别、规范化 URL digest、解析 IP、调用用途和 policy version。公开错误不得泄露内网拓扑。

服务 MAY 在 `ServiceDescribe.egress_network_policy` 暴露粗粒度出站策略，供 peer 和客户端理解是否支持安全的外部 URL 解析。公开 describe 不应暴露敏感私网 allowlist；认证后的 operator describe MAY 返回完整策略。

## 12. 安全要求

服务实现 MUST：

- 对所有输入做 schema validation
- 对签名和 capability 做独立验证
- 对 blob / snapshot / chunk 做内容哈希校验
- 防止错误信息泄露不可见资源存在性
- 对高成本查询执行配额控制
- 对公开 endpoint 做滥用防护
- 拒绝 URL query / path 中的认证材料
- 对未知路径、错误 method、不可见资源和权限失败使用一致的最小披露错误语义
- 对下载、跳转、服务发现和联邦请求中的外部 URL 做 §11.2 的出站网络目标策略检查

服务实现 SHOULD：

- 记录可审计但不泄露明文的安全日志
- 对管理操作要求更强认证
- 对联邦写入执行 reputation / quarantine 策略
