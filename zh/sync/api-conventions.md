# HTTP/JSON Binding 通用约定

## 1. 目标

本文定义 Contrix 默认 HTTP/JSON binding 的线级约定。  
Contrix 协议核心不强绑定 REST API；核心操作、消息 envelope 与 transport binding 的关系见 `transport-bindings.md`。

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

Contrix canonical JSON 字段名 MUST 使用小写字母与下划线连接，例如：

- `space_id`
- `event_id`
- `service_endpoint`
- `verification_method`
- `retry_after_ms`

Raw 外部标准文档 MUST 保留外部标准字段名，例如 W3C DID Core 的 `verificationMethod` / `alsoKnownAs` / `serviceEndpoint` 和 VC 的 `credentialSubject`。Contrix normalized view、索引、policy input 和 reducer input MAY 使用 snake_case 派生字段，但这些派生字段不得作为 raw DID / VC 文档重新输出。

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
- Space policy
- verified claim / attestation

服务端 MUST NOT 仅因 bearer token 存在就跳过 capability 检查。

认证材料 MUST 放在 header、HTTP Message Signature、mTLS 握手或明确的 signed proof body 中。服务端 MUST NOT 接受 query string、path segment 或 fragment 中的 session token、access token、API key、签名密钥或等价认证材料。

规则：

- 带有 `access_token`、`session_token`、`api_key`、`auth`、`signature` 等 query 参数的受保护 endpoint 请求 MUST 被拒绝，除非对应 endpoint 明确把该字段定义为非认证业务参数。
- 拒绝时 SHOULD 返回 `unauthenticated` 或 `invalid_param`，并且不得把 query 中的敏感值写入普通访问日志。
- 临时下载 URL 可以把短期能力 token 放入 URL，但它 MUST 是单 blob、单用途、短时效、可撤销的派生 token，不得等同于用户 session 或长期 capability。

### 3.1 认证服务发现

认证与授权服务器可以分离。服务 describe / discovery 响应 SHOULD 公布认证 metadata，但不得把 OAuth/OIDC subject 当作 Contrix principal：

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

成功响应 SHOULD 使用具体 endpoint 定义的 JSON 对象。  
如果 endpoint 需要通用 envelope，建议格式如下：

```json
{
  "ok": true,
  "request_id": "cx:req:01js0ke0000000000000000000",
  "result": {}
}
```

流式 endpoint MAY 使用 newline-delimited JSON、SSE 或 WebSocket frame，但每个 frame 仍 SHOULD 是独立 JSON 对象。

## 5. 标准错误响应

错误响应 MUST 使用统一 JSON 格式：

```json
{
  "ok": false,
  "error": {
    "code": "capability_denied",
    "message": "actor does not have card.update on this card",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "cx:req:01js0ke0000000000000000000"
}
```

`message` 用于开发者诊断，不应用于稳定程序逻辑。  
客户端 MUST 以 `code` 作为主要错误分类。

### 5.1 标准错误码
标准 `error.code` 与批处理/联邦响应中的逐项 `reason_code` 共享同一字符串命名空间。若某个接口返回 `accepted[]` / `rejected[]` / `quarantine[]`，其中逐项 `reason_code` SHOULD 复用下表中的标准代码；新增代码必须同时写入本文与 `artifacts/registry/error-code-registry.json`。

| code | HTTP status | 含义 |
| --- | ---: | --- |
| `bad_json` | 400 | JSON 无法解析 |
| `bad_query` | 400 | query 参数无法解析、重复冲突或不符合 endpoint schema |
| `schema_violation` | 422 | JSON 可解析但不符合 endpoint schema |
| `missing_param` | 400 | 缺少必填参数 |
| `invalid_param` | 400 | 参数值非法 |
| `unauthenticated` | 401 | 缺少或无法验证认证材料 |
| `auth_expired` | 401 | session / grant 已过期 |
| `soft_logged_out` | 401 | session 被软登出；客户端应重新认证但保留本地设备密钥 |
| `invalid_signature` | 401 | 签名不成立 |
| `capability_denied` | 403 | capability 或 policy 不允许 |
| `space_frozen` | 403 | Space 冻结、归档、tombstone 或关闭，拒绝普通写入 |
| `claim_required` | 403 | 缺少必要 claim / presentation |
| `not_found` | 404 | 目标不存在或对请求方不可见 |
| `unrecognized_endpoint` | 404 | 路径位于协议命名空间下但未被该服务实现或声明 |
| `method_not_allowed` | 405 | HTTP method 不支持 |
| `conflict` | 409 | 通用状态冲突 |
| `cas_conflict` | 409 | `expected_state_hash` 不匹配 |
| `causal_conflict` | 409 | `prev_refs` / `auth_refs`、actor chain 或同批依赖违反因果约束 |
| `dependency_missing` | 409 | 缺少必要依赖；可通过 backfill / snapshot / 重试恢复 |
| `discussion_branch_disabled` | 409 | 目标 Flow discussion branch 未启用，不能接收 `cx.message.*` |
| `epoch_mismatch` | 409 | 加密 epoch 过期 |
| `duplicate_conflict` | 409 | 相同幂等键对应不同内容 |
| `rank_exhausted` | 409 | fractional rank 区间耗尽，需要 rebalance 或选择其他位置 |
| `hlc_logical_overflow` | 503 | 生产者当前毫秒内无法继续生成单调 HLC，应稍后重试 |
| `payload_too_large` | 413 | 请求体或 blob 超限 |
| `digest_mismatch` | 422 | 上传、下载、代理或镜像内容摘要与声明不一致 |
| `unknown_did` | 422 | DID 无法按当前 resolver policy 解析或验证 |
| `quota_exceeded` | 403 | 存储、带宽或计算配额超限 |
| `rate_limited` | 429 | 请求频率超限 |
| `timeout` | 504 | 长轮询、等待 frontier 或上游请求超时 |
| `stale_frontier` | 409 | 服务本地授权或同步 frontier 尚未覆盖请求要求 |
| `sync_token_expired` | 410 | 客户端同步 token 已过期，需要回退到 initial sync 或 snapshot bootstrap |
| `unsupported_feature` | 501 | 服务不支持该 feature |
| `unsupported_event_kind` | 501 | 服务不接收该 active 标准 Event kind |
| `projection_incomplete` | 409 | 受限 reducer / projection 无法在当前依赖与 feature 集下声称完整结果 |
| `internal_error` | 500 | 服务内部错误 |
| `temporarily_unavailable` | 503 | 服务暂不可用 |

错误语义必须使用单一标准 code。若请求体过大使用 `payload_too_large` / 413；若配额策略拒绝使用 `quota_exceeded` / 403。`stale_frontier` 表示服务可用但本地因果前沿落后，客户端可等待或 backfill；服务故障、维护或无法追赶 frontier 时使用 `temporarily_unavailable` / 503 并 SHOULD 返回 `Retry-After`。Malformed sync token 使用 `invalid_param` / 400；格式正确但已过期的 sync token 使用 `sync_token_expired` / 410。

### 5.2 未知路径与错误方法

对 `/api/v1/*` 与 `/contrix/v1/*` 之下的请求，服务端 MUST 使用统一错误响应，不得返回 HTML、纯文本框架错误或实现栈信息。

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

## 7. 分页与 cursor

列表接口 SHOULD 使用 cursor 分页：

```json
{
  "items": [],
  "next_cursor": "cx:cursor:...",
  "has_more": false
}
```

`cursor` MUST 是不透明字符串。客户端 MUST NOT 解析 cursor 内容来推断排序或权限。

服务端 MAY 对 `limit` 设置上限。超过上限时 SHOULD 使用最大允许值或返回 `invalid_param`。

## 8. 读己之所写

写接口成功后 SHOULD 返回 `sync_token`：

```json
{
  "status": "accepted",
  "event_id": "cx:event:01js0ev0000000000000000000",
  "sync_token": "cx:sync:..."
}
```

查询接口 SHOULD 接受：

```text
X-Contrix-Wait-For: <sync_token>
```

如果服务在超时前达到该 causal frontier，则返回正常结果；否则 SHOULD 返回 `temporarily_unavailable` 或 `timeout`，并附带当前 frontier。

## 9. Rate Limit

服务 MAY 按以下维度限流：

- actor DID
- device id
- session id
- source IP
- Space id
- endpoint
- blob byte quota

核心协议不定义全网统一的固定请求数下限；不同 sovereign、public federation、high-assurance 或离线 profile 可以有不同容量与滥用模型。但任何可被客户端或联邦对端调用的服务，MUST 通过 describe endpoint 暴露当前有效的限流配置，使对端能做自适应重试。

限流配置 MUST 使用 `rate_limit_policy` 内联对象，或使用 `rate_limit_policy_ref` 指向可缓存、可验证的同等策略对象。策略至少包含：

- `policy_version` 或等价版本/hash。
- `entries[]`，每项绑定 `endpoint` 或 `operation_id`。
- 适用范围：`scope`，例如 actor DID、service DID、device id、source IP、Space id 或 blob quota。
- 窗口与额度：`window_seconds`、`max_requests`、`burst`；若是字节或批量限制，使用 `max_bytes`、`max_events_per_batch`、`max_body_bytes`。
- 重试提示：`retry_after_ms`、`backoff_hint` 或 `next_retry_at` 的语义。
- `effective_at` / `expires_at` 或缓存 TTL；未知时客户端 MUST 按保守策略重试。

公开 describe MAY 只返回 coarse policy，避免暴露内部防滥用细节；认证后的 describe SHOULD 返回调用方当前可见的精确有效策略。服务若省略 `rate_limit_policy` 和 `rate_limit_policy_ref`，表示除了通用滥用防护外没有可预期的端点级限流；一旦可能返回 `rate_limited`，就 MUST 暴露足够的策略信息供对端调度。

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
Access-Control-Allow-Headers: Authorization, Content-Type, Content-Digest, Digest, Idempotency-Key, X-Contrix-Wait-For, X-Contrix-Request-Id
Access-Control-Expose-Headers: Retry-After, Content-Digest, Digest, Content-Disposition, Content-Range, Location, X-Contrix-Request-Id
```

服务端 MUST NOT 在 `OPTIONS` preflight 请求中执行写入逻辑。

规则：

- `Access-Control-Allow-Methods` SHOULD 反映该服务实际支持的 method 集合；支持 `HEAD` 或 `PATCH` 的服务必须把它们列入 CORS。
- 服务端 MUST NOT 在 CORS 中允许 `CONNECT` 或 `TRACE`。
- 浏览器可访问的私有 endpoint 不得依赖 cookie 作为唯一认证方式；推荐使用 `Authorization` header 或 device-bound proof。

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
- `rate_limit_policy_ref`

客户端 MUST 根据 feature discovery 决定是否启用可选能力，不得假设所有节点都支持完整协议。

### 11.1 服务发现缓存与委托

服务 DID Document 中的 service endpoint 是服务身份与 endpoint 绑定的权威来源。域名级 bootstrap MAY 通过 `/.well-known/contrix/server` 或等价 signed metadata 暴露 endpoint 摘要，但接收方仍 MUST 校验：

- HTTPS/TLS 名称与返回的 endpoint 一致；
- service DID、DID Document service entry、describe 响应和 HTTP Message Signature 绑定一致；
- Space policy 或 actor / organization service delegation 允许该服务角色；
- metadata hash / version 未被本地策略标记为撤销或过期。

服务发现结果 SHOULD 按 HTTP cache header 缓存。未提供显式缓存时间时，客户端 MAY 使用不超过 24 小时的默认 TTL；实现 SHOULD 对正缓存设置上限（建议不超过 48 小时），对失败缓存使用更短 TTL 或指数退避，避免一次临时故障长期破坏联邦。

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
- 对下载、跳转、服务发现和联邦请求中的外部 URL 做 allowlist / policy 检查

服务实现 SHOULD：

- 记录可审计但不泄露明文的安全日志
- 对管理操作要求更强认证
- 对联邦写入执行 reputation / quarantine 策略


