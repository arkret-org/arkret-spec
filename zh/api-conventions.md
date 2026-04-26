# API 通用约定

## 1. 目标

本文定义 Contrix HTTP API 的通用线级约定。  
各服务面可以扩展自己的 endpoint，但 MUST 遵守本文的基础规则，除非对应文档明确说明例外。

本文适用于：

- identity registry
- repo
- relay
- index
- blob
- authz
- push gateway
- federation endpoint

## 2. 传输与编码

### 2.1 HTTPS

生产环境 API endpoint MUST 使用 HTTPS。  
明文 HTTP 只允许用于本地开发、测试网络或受控内网模拟环境。

### 2.2 JSON 编码

所有 JSON request / response MUST 使用 UTF-8。

Contrix canonical JSON 字段名 MUST 使用小写字母与下划线连接，例如：

- `space_id`
- `commit_id`
- `service_endpoint`
- `verification_method`
- `retry_after_ms`

Raw 外部标准文档 MAY 保留外部字段名，例如 W3C DID Core 的 `verificationMethod`，但进入 Contrix normalized view、索引、policy input 和 reducer input 前 MUST 映射为 snake_case。

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

## 4. 标准响应 envelope

成功响应 SHOULD 使用具体 endpoint 定义的 JSON 对象。  
如果 endpoint 需要通用 envelope，建议格式如下：

```json
{
  "ok": true,
  "request_id": "cx:req:01JS0KE000000000000000000",
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
    "message": "actor does not have entity.update on this task",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "cx:req:01JS0KE000000000000000000"
}
```

`message` 用于开发者诊断，不应用于稳定程序逻辑。  
客户端 MUST 以 `code` 作为主要错误分类。

### 5.1 标准错误码

| code | HTTP status | 含义 |
| --- | ---: | --- |
| `bad_json` | 400 | JSON 无法解析 |
| `schema_violation` | 400 / 422 | 请求不符合 schema |
| `missing_param` | 400 | 缺少必填参数 |
| `invalid_param` | 400 | 参数值非法 |
| `unauthenticated` | 401 | 缺少或无法验证认证材料 |
| `auth_expired` | 401 | session / grant 已过期 |
| `invalid_signature` | 401 | 签名不成立 |
| `capability_denied` | 403 | capability 或 policy 不允许 |
| `claim_required` | 403 | 缺少必要 claim / presentation |
| `not_found` | 404 | 目标不存在或对请求方不可见 |
| `method_not_allowed` | 405 | HTTP method 不支持 |
| `conflict` | 409 | 通用状态冲突 |
| `cas_conflict` | 409 | `expected_state_hash` 不匹配 |
| `epoch_mismatch` | 409 | 加密 epoch 过期 |
| `duplicate_conflict` | 409 | 相同幂等键对应不同内容 |
| `payload_too_large` | 413 | 请求体或 blob 超限 |
| `quota_exceeded` | 413 / 402 | 存储、带宽或计算配额超限 |
| `rate_limited` | 429 | 请求频率超限 |
| `unsupported_feature` | 501 | 服务不支持该 feature |
| `internal_error` | 500 | 服务内部错误 |
| `temporarily_unavailable` | 503 | 服务暂不可用 |

## 6. 幂等

所有写接口 MUST 支持幂等重试。

写入请求 SHOULD 携带以下之一：

- `op_id`
- `commit_id`
- `request_id`
- endpoint-specific `idempotency_key`

规则：

- 相同幂等键 + 相同 canonical request body MUST 返回与首次请求语义等价的结果。
- 相同幂等键 + 不同 canonical request body MUST 返回 `duplicate_conflict`。
- 服务端 SHOULD 记录幂等结果至少到相关 op 被最终同步或过期。

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
  "commit_id": "cx:commit:01JS0KE000000000000000000",
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

触发限流时 MUST 返回 `rate_limited`，并 SHOULD 附带：

```json
{
  "retry_after_ms": 2000
}
```

HTTP response SHOULD 同时设置 `Retry-After` header。

## 10. CORS 与浏览器客户端

面向浏览器的服务 SHOULD 支持 CORS preflight。

推荐响应头：

```text
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, X-Contrix-Wait-For, X-Contrix-Request-Id
```

服务端 MUST NOT 在 `OPTIONS` preflight 请求中执行写入逻辑。

## 11. 版本与 feature discovery

每个服务 SHOULD 暴露 describe endpoint，返回：

- `protocol_version`
- `service_type`
- `service_did`
- `supported_features`
- `supported_profiles`
- `max_body_bytes`
- `rate_limit_policy_ref`

客户端 MUST 根据 feature discovery 决定是否启用可选能力，不得假设所有节点都支持完整协议。

## 12. 安全要求

服务实现 MUST：

- 对所有输入做 schema validation
- 对签名和 capability 做独立验证
- 对 blob / snapshot / chunk 做内容哈希校验
- 防止错误信息泄露不可见资源存在性
- 对高成本查询执行配额控制
- 对公开 endpoint 做滥用防护

服务实现 SHOULD：

- 记录可审计但不泄露明文的安全日志
- 对管理操作要求更强认证
- 对联邦写入执行 reputation / quarantine 策略
