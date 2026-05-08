---
title: Transport Bindings
---

## 1. 目标

Contrix 协议核心定义的是：

- canonical object / event schema
- DID identity and service discovery
- capability authorization
- Space policy and reducer semantics
- sync / federation / applet / agent session semantics
- error, pagination, idempotency and stream message envelopes

**v1 core 互操作 transport 锁定为 HTTP/JSON**：默认 binding 由 [`service-http-binding.md`](./service-http-binding.md) 与
[`contrix-service-api.openapi.yaml`](../../artifacts/openapi/contrix-service-api.openapi.yaml) 规定。声称
`cx.profile.principal_server.v1` / `cx.profile.full_client.v1` 等 v1 core profile 的实现
**MUST** 提供 HTTP/JSON binding；其他 transport（gRPC、WebSocket-frame、SSE、message queue、
libp2p）属于 **v1.1+ extension binding profile**，core 实现 **不要求** 提供。

> Rationale: 早期文档把"transport-agnostic"作为 normative claim，但仓库里 `contrix-service-api.openapi.yaml`
> 已展开 ~70 KB HTTP/JSON 细节，而 gRPC / WebSocket / MQ / libp2p 各自只有几行说明。这种状况
> 下声称对等 transport 会误导实现者。v1 直接承认 HTTP/JSON 是 core，把其他 transport
> 留作 extension。Sync stream / events feed 的事件驱动语义可由后续 AsyncAPI 描述补充，但不
> 改变 core 锁定。

## 2. 分层

| 层 | 是否协议核心 | 例子 |
| --- | --- | --- |
| Semantic operation | 是 | `submit_event`, `get_events`, `sync`, `backfill`, `authz_check`, `applet_transaction` |
| Message envelope | 是 | request id、actor、device、capability refs、idempotency key、cursor、error code |
| Encoding profile | 是 | canonical JSON、hash、signature、CBOR profile 可选 |
| Transport binding (HTTP/JSON) | 是（v1 core） | `/api/v1/...` 路径、Idempotency-Key header、错误 JSON。 |
| Transport binding (gRPC / WS / SSE / MQ / libp2p) | 否（v1.1+ extension） | 仅在显式声明 binding profile 时启用。 |
| Product SDK | 否 | TypeScript SDK、Python SDK、CLI |

规范中的 `/api/v1/...` 路径是 v1 core HTTP binding 的 normative 形态；非 HTTP binding 是 extension。

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

## 4. Canonical Operation IDs

Transport binding MUST 映射到 `artifacts/registry/contract-catalog.json#operation_registry` 中定义的 canonical `operation_id`。`artifacts/registry/operation-registry.json` 是实现可直接消费的生成视图。取值使用 `cx.<namespace>.<lower_snake_case>`。下表只是核心示例；完整集合以 generated registry 为准，OpenAPI、gRPC、MQ、SSE、WebSocket 和 libp2p binding 均不得声明 catalog 中不存在的 operation。

| Operation | 语义 |
| --- | --- |
| `cx.server.describe` | 返回服务 DID、service type、profile、feature、binding 与限制。 |
| `cx.identity.resolve` | 解析 DID，返回 DID document 与 normalized principal view。 |
| `cx.identity.get_log` | 获取 DID key log。 |
| `cx.identity.submit_did_operation` | 提交 DID 更新操作。 |
| `cx.events.submit` | 提交 signed Event Envelope。 |
| `cx.events.get` | 按 ID 读取单个 Event。 |
| `cx.events.batch_get` | 批量读取 Event。 |
| `cx.events.list` | 按 actor / Space / cursor 列出 Event。 |
| `cx.events.frontier` | 获取 actor 或 Space 的可见 Event frontier。 |
| `cx.sync.subscribe` | 订阅 Space 增量流。 |
| `cx.sync.backfill` | 回填历史事件。 |
| `cx.sync.client_sync` | 客户端增量同步。 |
| Federation push（复用 `cx.events.submit` + service_signature） | v1 已移除 `/federation/*` 独立 API surface；联邦推送复用 `/events/submit`，认证从 user_session 切换为 HTTP Message Signature + Source/Destination service DID header。详见 [`federation.md`](./federation.md)。 |
| Federation pull / backfill（复用 `cx.sync.backfill` + service_signature） | 同上，跨域历史回补复用 `/sync/backfill`。 |
| `cx.directory.search_spaces` / `cx.directory.search_organizations` / `cx.directory.search_actors` / `cx.directory.search_users` | 授权搜索 Space / Organization / Actor / User。 |
| `cx.directory.resolve_space` / `cx.directory.resolve_organization` / `cx.directory.resolve_handle` | 精确解析 Space / Organization / handle。 |
| `cx.blob.upload` | 上传 blob。 |
| `cx.blob.get` | 获取 blob 或下载授权。 |
| `cx.push.register_device` | 注册推送设备和推送网关。 |
| `cx.push.notify` | 投递脱敏唤醒。 |
| `cx.authz.check` | 检查 capability / policy 是否允许动作。 |
| `cx.policy.check` | 调用 policy server 获取签名决策。 |
| `cx.moderation.report` | 提交内容或行为举报。 |
| `cx.applet.transaction` | 向 Applet 推送事件批次。 |
| `cx.applet.describe` | 查询 Applet profile、namespace 与限制。 |
| `cx.device_messages.put` | 发送 to-device message。 |
| `cx.keys.upload` / `cx.keys.query` / `cx.keys.claim` | E2EE 设备密钥发布、查询与领取。 |
| `cx.keys.backups.put` / `cx.keys.backups.list` / `cx.keys.backups.get` / `cx.keys.backups.delete` | 加密密钥备份对象存储、枚举、读取与删除。 |

HTTP binding MAY 把 `operation_id` 映射成路径；gRPC binding MAY 把它映射成 service method；message queue binding MAY 把它映射成 topic + message type。

Agent protocol handoff 状态通过 durable Event kind（例如 `cx.agent.protocol_session.start`、`cx.agent.protocol_session.status`）表达，不注册为 service `operation_id`。

## 5. HTTP/JSON Binding

HTTP/JSON 是默认 profile：

- JSON request / response 使用 UTF-8。
- 生产环境使用 HTTPS。
- 写操作使用 `Idempotency-Key` header 或 body 内 `idempotency_key`。
- 流式结果 MAY 使用 SSE、WebSocket 或 newline-delimited JSON。
- 错误使用统一 JSON error object，并映射到 HTTP status。

HTTP binding 的路径 SHOULD 遵循 `service-api-schema.mdx`，但实现 MAY 使用 XRPC、RPC style 或版本化路径，只要 feature discovery 暴露实际 binding。

## 6. gRPC Binding（v1.1+ extension）

> 以下章节描述的 gRPC / WebSocket / SSE / MQ / libp2p binding 都是 **v1.1+ extension**。
> v1 core 实现 **不要求** 提供这些 binding；只有显式声明对应 binding profile 的部署才需要
> 实现。这些章节保留为部署设计参考，不构成 v1 core 互操作要求。


gRPC binding SHOULD：

- 使用 protobuf message 表达 request / response。
- 保留 canonical `operation_id`。
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
- gossip 只传播 signed events、event batch receipts、snapshots 或 transactions。
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

当其他文档写 `GET /api/...`、`POST /api/...` 或 "endpoint" 时，**v1 core 互操作以 HTTP/JSON binding 为
normative 形态**。其他 transport 是 extension，需要显式声明对应 binding profile。

v1 core conformance 测试 MUST 包含：

- semantic operation test
- HTTP binding test

声明非 HTTP binding profile 的实现额外提供该 binding 的 mapping test。

