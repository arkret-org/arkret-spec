---
title: Transport Bindings
---

## 1. 目标

Contrix 协议核心定义的是：

- canonical object / event schema
- DID identity and service discovery
- capability authorization
- Realm policy and reducer semantics
- sync / federation / applet / agent session semantics
- error, pagination, idempotency and stream message envelopes

**v1 core 互操作 transport 锁定为 HTTP/JSON**：默认 binding 由 [`service-http-binding.md`](./service-http-binding.md) 与
[`contrix-service-api.openapi.yaml`](../../artifacts/openapi/contrix-service-api.openapi.yaml) 规定。声称
`cx.profile.principal_server.v1` / `cx.profile.full_client.v1` 等 v1 core profile 的实现
**MUST** 提供 HTTP/JSON binding；其他 transport（gRPC、WebSocket-frame、SSE、message queue、
libp2p）属于 **binding extension profile**，core 实现 **不要求** 提供。

> Rationale: HTTP/JSON 是 core normative surface（`contrix-service-api.openapi.yaml` ~70 KB
> 完整描述）。gRPC / WebSocket / MQ / libp2p 由独立 binding extension profile 单独 normative
> 化，避免在 core 中只给几行说明就声称 transport-agnostic。Sync stream / events feed 的事件
> 驱动语义可由独立 AsyncAPI 描述补充，但不改变 core 锁定。

## 2. 分层

| 层 | 是否协议核心 | 例子 |
| --- | --- | --- |
| Semantic operation | 是 | `submit_event`, `get_events`, `sync`, `backfill`, `authz_check`, `applet_transaction` |
| Message envelope | 是 | request id、actor、device、capability refs、idempotency key、cursor、error code |
| Encoding profile | 是 | canonical JSON、hash、signature、CBOR profile 可选 |
| Transport binding (HTTP/JSON) | 是（v1 core） | `/api/v1/...` 路径、Idempotency-Key header、错误 JSON。 |
| Transport binding (gRPC / WS / SSE / MQ / libp2p) | 否（binding extension profile） | 仅在显式声明 binding profile 时启用。 |
| Product SDK | 否 | TypeScript SDK、Python SDK、CLI |

规范中的 `/api/v1/...` 路径是 v1 core HTTP binding 的 normative 形态；非 HTTP binding 是 extension。

## 3. Binding Requirements

任何 transport binding MUST 支持：

- 服务发现：声明 service type、service DID、supported features、supported transports。
- 认证：能携带 session token、request signature、mTLS identity 或 DID-based service signature。
- 授权上下文：能传递 actor DID、device id、capability refs、Realm id、resource/action。
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
| `cx.events.resolve` | 批量读取 Event。 |
| `cx.events.query` | 按 actor / Realm / cursor 双向查询 Event（替代旧 `cx.events.list` + `cx.sync.backfill`）。 |
| `cx.events.subscribe` | 订阅 Realm / actor 增量流，可选 bounded catch-up replay（替代旧 `cx.sync.subscribe`）。 |
| `cx.events.frontier` | 获取 actor 或 Realm 的可见 Event frontier。 |
| `cx.account.subscribe` | 客户端账号视角聚合 streaming 订阅(NDJSON frame 流;与 `cx.events.subscribe` 对称)。 |
| Federation push（复用 `cx.events.submit` + service_signature） | 联邦推送复用 `POST /api/v1/events`；认证从 user_session 切换为 HTTP Message Signature + `Source-Service-DID` / `Destination-Service-DID` header，请求体携带 `service_binding_ref`。详见 [`federation.md`](./federation.md) §4.1。 |
| Federation pull / backfill（复用 `cx.events.query` + service_signature） | 跨域历史回补复用 `GET /api/v1/events?before=<cursor>`（取该 cursor 之前最近一批，默认 descending），认证同 push；可选返回 `snapshot_bootstrap`。详见 [`federation.md`](./federation.md) §4.2。 |
| `cx.directory.search_realms` / `cx.directory.search_organizations` / `cx.directory.search_actors` / `cx.directory.search_users` | 授权搜索 Realm / Organization / Actor / User。 |
| `cx.directory.resolve_realm` / `cx.directory.resolve_organization` / `cx.directory.resolve_handle` | 精确解析 Realm / Organization / handle。 |
| `cx.directory.announce` / `cx.directory.withdraw` / `cx.directory.subscribe` | Discovery ingest：资源向 Directory 推送签名 discovery state、撤销 opt-in、或注册 pull-mode 通知。详见 [`discovery/discovery-directory.md`](../discovery/discovery-directory.md) §8。 |
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

## 6. Non-HTTP Binding Extensions

gRPC、WebSocket / SSE、Message Queue (Kafka / NATS / Pulsar / AMQP) 与 P2P / libp2p binding **不是 v1 core
互操作 surface**。本规范不为它们定义 normative wire format、operation mapping、stream framing
或 discovery 字段；这些 transport 名称仅作为 extension profile slot 保留。

任何声明此类 binding 的部署 MUST 自行发布独立 binding profile 文档（profile id 形如
`cx.profile.binding.<transport>.v1`），并在该文档中至少明确：

- canonical `operation_id` → transport-specific 调用形态的映射；
- envelope / frame schema、签名绑定、idempotency key 与 cursor 处理；
- 错误码到 transport native status 的映射；
- 服务发现如何在 `supported_bindings` 中声明该 binding 与其能力。

未声明对应 binding profile 的实现 MUST NOT 接受非 HTTP/JSON 流量，也不得要求对端支持。
v1.0 conformance suite 不测试任何非 HTTP binding；gRPC / WS / MQ / libp2p 等
transport 必须各自通过 binding profile 单独 normative 化。

## 7. Binding Discovery

服务描述 SHOULD 返回：

```json
{
  "service_type": "principal_server",
  "service_did": "did:web:server.example",
  "supported_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://server.example/api/v1",
      "operations": ["cx.account.subscribe", "cx.snapshot.head"],
      "extension_profile_required": null
    }
  ]
}
```

其他 binding（gRPC / WebSocket / SSE / MQ / libp2p）是 extension profile，需声明对应 binding profile id 后才可出现在此处；v1 core 仅要求 `http_json`。

客户端 MUST 根据 `supported_bindings` 选择 transport，不得假设所有服务都有 REST path。

## 8. Normative Wording

当其他文档写 `GET /api/...`、`POST /api/...` 或 "endpoint" 时，**v1 core 互操作以 HTTP/JSON binding 为
normative 形态**。其他 transport 是 extension，需要显式声明对应 binding profile。

v1 core conformance 测试 MUST 包含：

- semantic operation test
- HTTP binding test

声明非 HTTP binding profile 的实现额外提供该 binding 的 mapping test。
