---
title: Transport Bindings
status: candidate
normative: true
stability: v1
updated: 2026-05-25
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 协议核心定义的是：

- canonical object / event schema
- DID identity and service discovery
- capability authorization
- Realm policy and reducer semantics
- sync / federation / applet / agent session semantics
- error, pagination, idempotency and stream message envelopes

**v1 core 互操作 transport 锁定为 HTTP/JSON**：默认 binding 由 [`service-http-binding.md`](./service-http-binding.md) 与
[`cokret-service-api.openapi.yaml`](../../artifacts/openapi/cokret-service-api.openapi.yaml) 规定。声称
`ck.profile.principal_server.v1` / `ck.profile.full_client.v1` 等 v1 core profile 的实现
**MUST** 提供 HTTP/JSON binding；其他 transport（gRPC、WebSocket-frame、SSE、message queue、
libp2p）属于 **binding extension profile**，core 实现 **不要求** 提供。

> Rationale: HTTP/JSON 是 core normative surface（`cokret-service-api.openapi.yaml` ~70 KB
> 完整描述）。gRPC / WebSocket / MQ / libp2p 由独立 binding extension profile 单独 normative
> 化，避免在 core 中只给几行说明就声称 transport-agnostic。Sync stream / events feed 的事件
> 驱动语义可由独立 AsyncAPI 描述补充，但不改变 core 锁定。

## 2. 分层

| 层 | 是否协议核心 | 例子 |
| --- | --- | --- |
| Semantic operation | 是 | `submit_event`, `get_events`, `sync`, `backfill`, `authz_check`, `applet_transaction` |
| Message envelope | 是 | request id、actor、device、capability refs、idempotency key、cursor、error code |
| Encoding profile | 是 | canonical JSON、hash、signature、CBOR profile 可选 |
| Transport binding (HTTP/JSON) | 是（v1 core） | `/...` 路径、Idempotency-Key header、错误 JSON。 |
| Transport binding (gRPC / WS / SSE / MQ / libp2p) | 否（binding extension profile） | 仅在显式声明 binding profile 时启用。 |
| Product SDK | 否 | TypeScript SDK、Python SDK、CLI |

规范中的 `/...` 路径是 v1 core HTTP binding 的 normative 形态；非 HTTP binding 是 extension。

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

Transport binding MUST 映射到 `artifacts/registry/contract-catalog.json#operation_registry` 中定义的 canonical `operation_id`。`artifacts/registry/operation-registry.json` 是实现可直接消费的生成视图。取值使用 `ck.<namespace>.<lower_snake_case>`。下表只是核心示例；完整集合以 generated registry 为准，OpenAPI、gRPC、MQ、SSE、WebSocket 和 libp2p binding 均不得声明 catalog 中不存在的 operation。

| Operation | 语义 |
| --- | --- |
| `ck.server.describe` | 返回服务 DID、service type、profile、feature、binding 与限制。 |
| `ck.identity.resolve` | 解析 DID，返回 DID document 与 normalized principal view。 |
| `ck.identity.get_log` | 获取 DID key log。 |
| `ck.identity.submit_did_operation` | 提交 DID 更新操作。 |
| `ck.events.submit` | 提交 signed Event Envelope。 |
| `ck.events.get` | 按 ID 读取单个 Event。 |
| `ck.events.resolve` | 批量读取 Event。 |
| `ck.events.query` | 按 actor / Realm / cursor 双向查询 Event。 |
| `ck.events.subscribe` | 订阅 Realm / actor 增量流，可选 bounded catch-up replay。 |
| `ck.events.frontier` | 获取 actor 或 Realm 的可见 Event frontier。 |
| `ck.account.viewer` | 当前 holder 的账号主体自读；响应使用 signed handle claim / ref / digest。 |
| `ck.account.update_profile` | 当前账号 profile 更新；`bio` 映射到 `profile_fields.bio`。 |
| `ck.account.subscribe` | 客户端账号视角聚合 streaming 订阅(NDJSON frame 流；与 `ck.events.subscribe` 对称)。 |
| `ck.account.register` | 注册 / account binding；request 使用 `principal_id`，不接受旧 `did` 或裸 `handle` 字段。 |
| `ck.account.session_revoke` | 撤销 session grant / access token；不撤销 device authorization。 |
| `ck.directory.search_realms` / `ck.directory.search_organizations` / `ck.directory.search_actors` / `ck.directory.search_users` | 授权搜索 Realm / Organization / Actor，以及用户目录条目（actor profile / handle 视图）。 |
| `ck.directory.resolve_realm` / `ck.directory.resolve_organization` / `ck.directory.resolve_handle` / `ck.directory.list_handles_for_subject` | 精确解析 Realm / Organization / handle，以及列出已知 subject 的当前可见 handle claims。 |
| `ck.directory.announce` / `ck.directory.withdraw` / `ck.directory.push.register` | Discovery ingest：资源向 Directory 推送签名 discovery state、撤销 opt-in、或注册 pull-mode webhook 通知。详见 [`discovery/discovery-directory.md`](../discovery/discovery-directory.md) §8。 |
| `ck.blob.upload` | 上传 blob。 |
| `ck.blob.get` | 获取 blob 或下载授权。 |
| `ck.push.register_device` | 注册推送设备和推送网关。 |
| `ck.push.notify` | 投递脱敏唤醒。 |
| `ck.authz.check` | 检查 capability / policy 是否允许动作。 |
| `ck.policy.check` | 调用 policy server 获取签名决策。 |
| `ck.moderation.report` | 提交内容或行为举报。 |
| `ck.applet.transaction` | 向 Applet 推送事件批次。 |
| `ck.applet.describe` | 查询 Applet profile、namespace 与限制。 |
| `ck.device_messages.put` | 发送 to-device message。 |
| `ck.keys.upload` / `ck.keys.query` / `ck.keys.claim` | E2EE 设备密钥发布、查询与领取。 |
| `ck.keys.backups.put` / `ck.keys.backups.list` / `ck.keys.backups.get` / `ck.keys.backups.delete` | 加密密钥备份对象存储、枚举、读取与删除。 |

> **Federation 复用说明（非独立 operation）**：v1 联邦不再注册独立的 federation operation_id，而是**复用**上表已有的 operation，并在认证层切换形态：
>
> - **Federation push**：复用 `ck.events.submit`（`POST /_cokret/self/events`）；认证从 user_session 切换为 HTTP Message Signature + `Source-Service-DID` / `Destination-Service-DID` header，请求体携带 `service_binding_ref`。详见 [`federation.md`](./federation.md) §4.1。
> - **Federation pull / backfill**：复用 `ck.events.query`（`GET /_cokret/self/events?before=<cursor>`，取该 cursor 之前最近一批，默认 descending）；认证同 push；可选返回 `snapshot_bootstrap`。详见 [`federation.md`](./federation.md) §4.2。
>
> 这两项是同一 canonical operation 的 federation auth-class 使用形态，不是新的 `operation_id`，因此不出现在上表的 operation 列中。

HTTP binding MAY 把 `operation_id` 映射成路径；gRPC binding MAY 把它映射成 service method；message queue binding MAY 把它映射成 topic + message type。

Agent protocol handoff 状态通过 durable Event kind（例如 `ck.agent.protocol_session.start`、`ck.agent.protocol_session.status`）表达，不注册为 service `operation_id`。

## 5. HTTP/JSON Binding

HTTP/JSON 是默认 profile：

- JSON request / response 使用 UTF-8。
- 生产环境使用 HTTPS。
- 写操作使用 `Idempotency-Key` header 或 body 内 `idempotency_key`。
- 流式结果 MAY 使用 SSE、WebSocket 或 newline-delimited JSON。
- 错误使用统一 JSON error object，并映射到 HTTP status。

HTTP binding 的 canonical 路径和请求/响应 shape SHOULD 遵循 `service-http-binding.md`、OpenAPI 以及生成的 `artifacts/reports/operation-schema-index.json`；`service-api-schema.mdx` 只提供 operation 分组与治理说明视图。实现 MAY 额外暴露 XRPC、RPC style 或部署本地 legacy alias，但这些 alias MUST NOT 宣称为 Cokret canonical binding，MUST NOT 出现在 `*.describe` 的 canonical operation binding 中，MUST NOT 使用 `/_cokret` namespace 表达版本，也不得包含 `/v1/`、`/api/v1`、`/cokret/v1` 等版本 path 段。v1 core conformance 测试始终以 canonical HTTP/JSON path 与字段为基准，路径别名不得替代 canonical binding。

## 6. Non-HTTP Binding Extensions

gRPC、WebSocket / SSE、Message Queue (Kafka / NATS / Pulsar / AMQP) 与 P2P / libp2p binding **不是 v1 core
互操作 surface**。本规范不为它们定义 normative wire format、operation mapping、stream framing
或 discovery 字段；这些 transport 名称仅作为 extension profile slot 保留。

任何声明此类 binding 的部署 MUST 自行发布独立 binding profile 文档（profile id 形如
`ck.profile.binding.<transport>.v1`），并在该文档中至少明确：

- canonical `operation_id` → transport-specific 调用形态的映射；
- envelope / frame schema、签名绑定、idempotency key 与 cursor 处理；
- 错误码到 transport native status 的映射；
- 服务发现如何在 `supported_bindings` 中声明该 binding 与其能力。

未声明对应 binding profile 的实现 MUST NOT 接受非 HTTP/JSON 流量，也不得要求对端支持。
v1.0 conformance suite 不测试任何非 HTTP binding；gRPC / WS / MQ / libp2p 等
transport MUST 各自通过 binding profile 单独 normative 化。

## 7. Binding Discovery

服务描述 SHOULD 返回：

```json
{
  "service_type": "principal_server",
  "service_did": "did:web:server.example",
  "supported_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://server.example",
      "operations": ["ck.account.viewer", "ck.account.update_profile", "ck.account.subscribe", "ck.snapshot.head"],
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
