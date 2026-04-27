# Transport Bindings

## 1. 目标

Contrix 协议核心不绑定 REST API。协议核心定义的是：

- canonical object / event / operation schema
- DID identity and service discovery
- capability authorization
- Space policy and reducer semantics
- sync / federation / applet / agent session semantics
- error, pagination, idempotency and stream message envelopes

HTTP/JSON REST 是默认互操作 binding，用于浏览器、普通服务端和调试工具。实现 MAY 使用 gRPC、WebSocket、SSE、GraphQL、QUIC、libp2p、message queue 或本地 IPC，只要它们提供语义等价的操作，并满足同样的签名、授权、幂等、分页、流控和错误语义。

## 2. 分层

| 层 | 是否协议核心 | 例子 |
| --- | --- | --- |
| Semantic operation | 是 | `submit_commit`, `sync`, `query`, `backfill`, `authz_check`, `applet_transaction` |
| Message envelope | 是 | request id、actor、device、capability refs、idempotency key、cursor、error code |
| Encoding profile | 是 | canonical JSON、hash、signature、CBOR profile 可选 |
| Transport binding | 否，除非实现声明 | HTTP/REST、gRPC、WebSocket、SSE、GraphQL、libp2p |
| Product SDK | 否 | TypeScript SDK、Python SDK、CLI |

规范中的 `/api/v1/...` 路径是 HTTP binding 示例和默认 profile，不是唯一合法接口形态。

## 3. Binding Requirements

任何 transport binding MUST 支持：

- 服务发现：声明 service type、service DID、supported features、supported transports。
- 认证：能携带 session token、request signature、mTLS identity 或 DID-based service signature。
- 授权上下文：能传递 actor DID、device id、capability refs、Space id、resource/action。
- 幂等：写操作能携带 idempotency key，并返回重复提交的一致结果。
- 分页：列表和历史读取能携带 opaque cursor。
- 流式：订阅、sync、agent status、applet transaction ack 可表达多帧结果。
- 错误：能表达稳定 `code`、message、retry hint 和 details。
- 内容协商：能声明 JSON、binary blob、encrypted envelope、event stream 格式。
- 背压与限流：能表达 retry-after、quota、max frame/body size。

## 4. Canonical Operation Names

Transport binding SHOULD 映射到以下 canonical operation names：

| Operation | 语义 |
| --- | --- |
| `identity.resolve` | 解析 DID，返回 DID document 与 normalized principal view。 |
| `identity.get_log` | 获取 DID key log。 |
| `repo.submit_commit` | 提交签名 commit。 |
| `repo.get_ops` | 批量读取 operation / event。 |
| `sync.subscribe` | 订阅 Space 增量流。 |
| `sync.backfill` | 回填历史事件。 |
| `sync.run` | 客户端增量同步。 |
| `index.query` | 查询 Entity / Relation / View projection。 |
| `index.space_hierarchy` | 查询 Space 层级。 |
| `blob.upload` | 上传 blob。 |
| `blob.get` | 获取 blob 或下载授权。 |
| `authz.check` | 检查 capability / policy 是否允许动作。 |
| `policy.check` | 调用 policy server 获取签名决策。 |
| `applet.transaction` | 向 Applet 推送事件批次。 |
| `device.send_message` | 发送 to-device message。 |
| `agent.protocol_session.start` | 启动外部 agent protocol handoff。 |
| `agent.protocol_session.status` | 回写 agent session 状态。 |

HTTP binding MAY 把 operation name 映射成路径；gRPC binding MAY 把它映射成 service method；message queue binding MAY 把它映射成 topic + message type。

## 5. HTTP/JSON Binding

HTTP/JSON 是默认 profile：

- JSON request / response 使用 UTF-8。
- 生产环境使用 HTTPS。
- 写操作使用 `Idempotency-Key` header 或 body 内 `idempotency_key`。
- 流式结果 MAY 使用 SSE、WebSocket 或 newline-delimited JSON。
- 错误使用统一 JSON error object，并映射到 HTTP status。

HTTP binding 的路径 SHOULD 遵循 `service-api-schema.md`，但实现 MAY 使用 XRPC、RPC style 或版本化路径，只要 feature discovery 暴露实际 binding。

## 6. gRPC Binding

gRPC binding SHOULD：

- 使用 protobuf message 表达 request / response。
- 保留 canonical operation name。
- 对写操作携带 `idempotency_key`。
- 对 streaming sync 使用 server streaming。
- 在 metadata 中携带 authentication 和 request id。
- 将 Contrix error code 映射到 gRPC status details，而不是只使用 generic status。

## 7. WebSocket / SSE Binding

WebSocket / SSE 适合：

- sync subscription
- sync streaming
- typing / presence / ephemeral signals
- agent protocol session status
- applet transaction ack

每个 frame SHOULD 是独立 envelope：

```json
{
  "frame_id": "cx:frame:01J...",
  "operation": "sync.subscribe",
  "cursor": "cx:cursor:...",
  "payload": {},
  "error": null
}
```

Frame MUST 可独立验证其 stream context，且不得依赖不受保护的连接状态绕过 capability 检查。

## 8. Message Queue Binding

企业或高吞吐部署 MAY 使用 Kafka、NATS、Pulsar、AMQP 等消息队列。要求：

- topic 命名不得成为授权依据。
- message body MUST 包含 signed envelope。
- consumer MUST 对每条消息独立做 schema、signature、capability 和 replay 检查。
- offset 不得作为 canonical cursor；必须映射为 Contrix opaque cursor。

## 9. P2P / libp2p Binding

P2P binding MAY 用于离线、边缘或本地优先场景。要求：

- peer identity MUST 绑定 service DID 或 device DID。
- gossip 只传播 signed events / commits / transactions。
- 接收方 MUST 独立验证，不得信任 peer routing。
- backfill 和 snapshot MUST 通过 hash 校验。

## 10. Binding Discovery

服务描述 SHOULD 返回：

```json
{
  "service_type": "principal_server",
  "service_did": "did:web:server.example",
  "supported_bindings": [
    {
      "binding": "http_json",
      "base_url": "https://server.example/api/v1",
      "operations": ["sync.subscribe", "sync.backfill"]
    },
    {
      "binding": "grpc",
      "endpoint": "server.example:443",
      "operations": ["sync.subscribe"]
    }
  ]
}
```

客户端 MUST 根据 `supported_bindings` 选择 transport，不得假设所有服务都有 REST path。

## 11. Normative Wording

当其他文档写 `GET /api/...`、`POST /api/...` 或 “endpoint” 时，除非明确说“HTTP binding MUST”，都应理解为 HTTP/JSON binding 的示例或默认 profile。

协议一致性测试 SHOULD 同时包含：

- semantic operation test
- HTTP binding test
- 至少一个非 HTTP binding mapping test
