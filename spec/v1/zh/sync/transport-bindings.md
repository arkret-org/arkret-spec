---
title: Transport Bindings
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 协议核心定义的是：

- canonical object / event schema
- DID identity and service discovery
- capability authorization
- Realm policy and reducer semantics
- sync / federation / applet / agent session semantics
- error, pagination, idempotency and stream message envelopes

**v1 core 互操作 transport 锁定为 HTTP/JSON**：默认 binding 由 [`service-http-binding.md`](./service-http-binding.md) 与
[`arkret-service-api.openapi.yaml`](../../artifacts/openapi/arkret-service-api.openapi.yaml) 规定。声称
`ak.profile.principal_server.v1` / `ak.profile.full_client.v1` 等 v1 core profile 的实现
**MUST** 提供 HTTP/JSON binding；其他 transport（gRPC、WebSocket-frame、SSE、message queue、
libp2p）属于 **binding extension profile**，core 实现 **不要求** 提供。

> Rationale: HTTP/JSON 是 core normative surface（`arkret-service-api.openapi.yaml` ~70 KB
> 完整描述）。gRPC / WebSocket / MQ / libp2p 由独立 binding extension profile 单独 normative
> 化，避免在 core 中只给几行说明就声称 transport-agnostic。Sync stream / events feed 的事件
> 驱动语义可由独立 AsyncAPI 描述补充，但不改变 core 锁定。

### 1.1 Stream frame 序列约束的机读锚点（normative）

`ak.self.account.stream.subscribe` 与 `ak.self.events.stream.subscribe` 的 NDJSON 多帧 stream 当前只有散文级的帧序列约束（见 [`client-sync.md` §2 / §2.2](./client-sync.md)、[`service-http-binding.md` §3.4](./service-http-binding.md)），缺独立的机读 normative 锚点。为关闭该缺口：

- **frame 序列约束 MUST 由 conformance vector 固化**：上述两类 stream 的帧先后序与必带字段组合 MUST 被登记的 conformance vector（`vector-registry.json`）机读固化，作为 wire conformance 的判定基准，而非仅靠散文。实现的 stream 输出必须能通过该 vector。
- 至少应被固化为可测试条目的 frame 序列约束（散文真相源见 client-sync.md，本节集中列举其 testable 形式）：
  1. `catchup=true` 时，`catchup_complete` 之前 MUST 至少出现一个 `delta` frame（baseline / catch-up delta）；`catchup=false` 时 MUST NOT 出现 `catchup_complete`。
  2. `dropped` frame MUST 携带 `cursor`；服务端无可用补齐 cursor 时 MUST 改发 `resync_required`（不带 cursor），MUST NOT 发送无 cursor 的 `dropped`。
  3. `delta` / `frontier` / `catchup_complete` frame MUST 携带 `cursor`；`heartbeat` / `resync_required` / `unauthorized` MUST NOT 依赖 cursor 推进位置。
  4. 客户端用作下一次 `after=` 的位置只来自 cursor-bearing frame 的 `cursor`；不带 cursor 的控制帧不推进重连位置。
- **AsyncAPI 交付（计划）**：在上述 vector 固化之外，stream 帧的事件驱动 schema MAY 由独立 AsyncAPI 文档补充描述；该 AsyncAPI 描述是 informative 补充，不改变本节"frame 序列约束 MUST 由 conformance vector 固化"的 normative 要求，也不改变 §1 的 core transport 锁定。

> 注：若上述 frame 序列约束需要在 `vector-registry.json` 新增条目，属 registry / artifact 改动，留协调者处理（见本提交报告说明）；本节只确立"MUST 由 conformance vector 固化 + AsyncAPI 计划"的 normative 要求与可测试条目清单。

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

Transport binding MUST 映射到 `artifacts/registry/contract-catalog.json#operation_registry` 中定义的 canonical `operation_id`。`artifacts/registry/operation-registry.json` 是实现可直接消费的生成视图。取值使用 `ak.<namespace>.<lower_snake_case>`。下表只是核心示例；完整集合以 generated registry 为准，OpenAPI、gRPC、MQ、SSE、WebSocket 和 libp2p binding 均不得声明 catalog 中不存在的 operation。

| Operation | 语义 |
| --- | --- |
| `ak.server.query.describe` | 返回服务 DID、service type、profile、feature、binding 与限制。 |
| `ak.root.identity.query.resolve` | 解析 DID，返回 DID document 与 normalized principal view。 |
| `ak.root.identity.log.query.list` | 获取 DID key log。 |
| `ak.root.identity.command.submit_did_operation` | 提交 DID 更新操作。 |
| `ak.self.events.command.submit` | 提交 signed Event Envelope。 |
| `ak.self.events.resource.get` | 按 ID 读取单个 Event。 |
| `ak.self.events.query.resolve` | 批量读取 Event。 |
| `ak.self.events.query.scan` | 按 actor / Realm / cursor 双向查询 Event。 |
| `ak.self.events.stream.subscribe` | 订阅 Realm / actor 增量流，可选 bounded catch-up replay。 |
| `ak.self.events.query.frontier` | 获取 actor 或 Realm 的可见 Event frontier。 |
| `ak.peer.events.command.submit` | federation peer 推送 signed Event Envelope 批次。 |
| `ak.peer.events.query.resolve` | federation peer 按 event id / digest 补洞解析 Event。 |
| `ak.peer.events.query.scan` | federation peer 按 Realm / actor / cursor 拉取或回填 Event。 |
| `ak.peer.events.query.scan_body` | `ak.peer.events.query.scan` 的 HTTP POST/body binding variant。 |
| `ak.peer.events.query.frontier` | federation peer 查询 Realm frontier 以检测 fork / stale peer。 |
| `ak.peer.snapshot.query.manifest_head` | federation peer 获取 snapshot-assisted bootstrap 的 manifest head。 |
| `ak.self.account.query.viewer` | 当前 holder 的账号主体自读；响应使用 signed handle claim / ref / digest。 |
| `ak.self.account.command.update_profile` | 当前账号 profile 更新；`bio` 映射到 `profile_fields.bio`。 |
| `ak.self.account.stream.subscribe` | 客户端账号视角聚合同步入口；HTTP/JSON binding 可用单次 `SyncOutcome` 长轮询，NDJSON / WebSocket-style binding 可用 account-aggregate frame stream。 |
| `ak.gate.account.command.register` | 注册 / account binding；request 使用 `principal_id`，不接受旧 `did` 或裸 `handle` 字段。 |
| `ak.gate.account.command.revoke_session` | 撤销 session grant；不撤销 device authorization。 |
| `ak.find.directory.query.search_realms` / `ak.find.directory.query.search_organizations` / `ak.find.directory.query.search_actors` / `ak.find.directory.query.search_users` | 授权搜索 Realm / Organization / Actor，以及用户目录条目（actor profile / handle 视图）。 |
| `ak.find.directory.query.resolve_realm` / `ak.find.directory.query.resolve_organization` / `ak.find.directory.query.resolve_handle` / `ak.find.directory.query.resolve_agent_selector` / `ak.find.directory.query.list_handles_for_subject` | 精确解析 Realm / Organization / handle / controller-scoped agent selector，以及列出已知 subject 的当前可见 handle claims。 |
| `ak.find.directory.command.announce` / `ak.find.directory.command.withdraw` / `ak.find.directory.push.command.register` | Discovery ingest：资源向 Directory 推送签名 discovery state、撤销 opt-in、或注册 pull-mode webhook 通知。详见 [`discovery/discovery-directory.md`](../discovery/discovery-directory.md) §8。 |
| `ak.self.blob.upload.create` | 上传 blob。 |
| `ak.self.blob.resource.get` | 获取 blob 或下载授权。 |
| `ak.edge.push.command.register_device` | 注册推送设备和推送网关。 |
| `ak.edge.push.command.notify` | 投递脱敏唤醒。 |
| `ak.self.authz.query.check` | 检查 capability / policy 是否允许动作。 |
| `ak.self.policy.query.check` | 调用 Policy Server 获取签名决策。 |
| `ak.self.moderation.command.report` | 提交内容或行为举报。 |
| `ak.edge.applet.command.transaction` | 向 Applet 推送事件批次。 |
| `ak.edge.applet.query.describe` | 查询 Applet profile、namespace 与限制。 |
| `ak.self.device_messages.command.send` | 将 to-device message 批次放入目标设备短期队列；HTTP binding 是 `POST /_arkret/self/device_messages`，因其语义是 send/fanout command，而不是 URI 资源替换。 |
| `ak.self.keys.upload.create` / `ak.self.keys.query.lookup` / `ak.self.keys.command.claim` | E2EE 设备密钥发布、查询与领取。 |
| `ak.self.keys.backups.resource.replace` / `ak.self.keys.backups.query.list` / `ak.self.keys.backups.command.unlock` / `ak.self.keys.backups.resource.delete` | 加密密钥备份对象存储、枚举、解锁取回与删除。 |

> **Federation peer surface（规范性）**：跨服务器互通必须使用 `/_arkret/peer/*` HTTP trust surface 和 `ak.peer.*` operation_id。`/_arkret/self/*` 只承接当前 principal / 已授权自服务会话的攻击面，不承接 federation server-to-server wire。**联邦接收收敛为单轨**：`POST /_arkret/peer/events`（`ak.peer.events.command.submit`）是唯一的 federation Event 接收轨，DataEvent / Control Move（含 Move / Anchor）统一走该 sealed Event Envelope 通道；实现私有 peer 入站轨 MUST NOT 作为跨 deployment 互通入口（详见 [`federation.md`](./federation.md) §4.0）。详见 [`federation.md`](./federation.md) §4。

HTTP binding MAY 把 `operation_id` 映射成路径；gRPC binding MAY 把它映射成 service method；message queue binding MAY 把它映射成 topic + message type。

Agent protocol handoff 状态通过 durable Event kind（例如 `ak.agent.interop_session.start`、`ak.agent.interop_session.status`）表达，不注册为 service `operation_id`。

## 5. HTTP/JSON Binding

HTTP/JSON 是默认 profile：

- JSON request / response 使用 UTF-8。
- 生产环境使用 HTTPS。
- 写操作使用 `Idempotency-Key` header 或 body 内 `idempotency_key`。

> **PQ-hybrid TLS 传输层姿态（canonical 表述）**：本节是 TLS PQ-hybrid 义务的真相源。生产 v1 部署的 service-to-service（federation peer）与 client-service TLS 1.3 连接 SHOULD 支持并优先协商混合后量子 group `X25519MLKEM768`（TLS 1.3 hybrid named group，经典 X25519 + ML-KEM-768 / NIST FIPS 203；draft-ietf-tls-ecdhe-mlkem）。`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1` 及继承它们的 profile 下，service-to-service 与 client-service 连接 MUST 协商 `X25519MLKEM768`；对端不提供该 group 时 MUST fail closed，MUST NOT 静默降级到纯经典 key exchange。default profile MAY 在对端不支持该 group 时回落到经典 TLS 1.3 key exchange，但 MUST 把该连接记录为 `transport_pq=not_negotiated`（或等价部署探针证据），并且 MUST NOT 宣称该连接具备 Harvest-Now-Decrypt-Later resistant transport posture。该姿态把 HNDL 缓解扩到仅靠 TLS 保护、不进 MLS / E2EE 的传输面（联邦 transaction 元数据、public plaintext Realm 内容、directory / sync 流量），不改任何 canonical `operation_id`、binding、Arkret wire envelope / schema / object model，也不触碰 envelope `scheme` / `version`，与请求级 RFC 9421 签名正交。高安全 / sovereign conformance 验证为 deployment-profile 握手探针：握手完成后检查协商出的 TLS named group 是否等于 `X25519MLKEM768`，并验证对端不提供时 fail closed，而非 object-model conformance vector。完整威胁论据见 [`../security/server-threat-model.md` §2.4](../security/server-threat-model.md)；联邦链路呼应见 [`federation.md` §3.2](./federation.md)；sovereign / 高安全部署的探针落地见 [`sovereign-deployment.md` §3 / §11](./sovereign-deployment.md)。
- 流式结果 MAY 使用 SSE、WebSocket 或 newline-delimited JSON。
- 错误使用统一 JSON error object，并映射到 HTTP status。

HTTP binding 的 canonical 路径和请求/响应 shape SHOULD 遵循 `service-http-binding.md`、OpenAPI 以及生成的 `artifacts/reports/operation-schema-index.json`；`service-api-schema.mdx` 只提供 operation 分组与治理说明视图。实现不得把未注册路径宣称为 Arkret canonical binding，不得在 `/_arkret` namespace 中表达版本，也不得包含 `/v1/`、`/api/v1`、`/arkret/v1` 等版本 path 段。v1 core conformance 测试始终以 canonical HTTP/JSON path 与字段为基准。

## 6. Non-HTTP Binding Extensions

gRPC、WebSocket / SSE、Message Queue (Kafka / NATS / Pulsar / AMQP) 与 P2P / libp2p binding **不是 v1 core
互操作 surface**。本规范不为它们定义 normative wire format、operation mapping、stream framing
或 discovery 字段；这些 transport 名称仅作为 extension profile slot 保留。

任何声明此类 binding 的部署 MUST 自行发布独立 binding profile 文档（profile id 形如
`ak.profile.binding.<transport>.v1`），并在该文档中至少明确：

- canonical `operation_id` → transport-specific 调用形态的映射；
- envelope / frame schema、签名绑定、idempotency key 与 cursor 处理；
- 错误码到 transport native status 的映射；
- 服务发现如何在 `supported_bindings` 中声明该 binding 与其能力。

未声明对应 binding profile 的实现 MUST NOT 接受非 HTTP/JSON 流量，也不得要求对端支持。
v1.0 conformance suite 不测试任何非 HTTP binding；gRPC / WS / MQ / libp2p 等
transport MUST 各自通过 binding profile 单独 normative 化。

### 6.1 Per-operation HTTP 伴生 binding（normative）

与上述 service-wide 替代 transport 不同，**per-operation HTTP 伴生 binding** 指仍运行在 HTTPS 之上、只覆盖单个 canonical `operation_id` 的替代 HTTP 交互形态（例如 `ak.self.blob.upload.create` 的 tus 可续传上传 binding，见 [`../crypto-media/media-and-blob.md` §2.1](../crypto-media/media-and-blob.md)）。这类 binding：

- MUST 由 core 规范文档直接 normative 化（含 operation 映射、认证/capability 复用、错误语义与 discovery 声明），不要求独立 `ak.profile.binding.<transport>.v1` profile；
- MUST 以对应 `ak.feature.*` id 在 `describe.supported_features` 声明，并在 `supported_bindings` 条目中通过 `operations` 限定其覆盖的 operation 集合，`extension_profile_required` 为 `null`；
- MUST NOT 改变所覆盖 operation 的语义结果（响应对象、receipt、内容寻址等与 canonical HTTP/JSON binding 一致）；
- 不改变本节对 service-wide 非 HTTP transport 的 binding profile 要求。

## 7. Binding Discovery

服务描述 SHOULD 返回：

```json
{
  "service_type": "principal_server",
  "service_did": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example",
  "supported_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://server.example",
      "operations": ["ak.self.account.query.viewer", "ak.self.account.command.update_profile", "ak.self.account.stream.subscribe", "ak.self.snapshot.query.manifest_head"],
      "extension_profile_required": null
    }
  ]
}
```

其他 binding（gRPC / WebSocket / SSE / MQ / libp2p）是 extension profile，需声明对应 binding profile id 后才可出现在此处；v1 core 仅要求 `http_json`。§6.1 的 per-operation HTTP 伴生 binding（如 `kind="tus"`）以 `extension_profile_required: null` + 对应 `ak.feature.*` 声明出现，不需要 binding profile id。

客户端 MUST 根据 `supported_bindings` 选择 transport，不得假设所有服务都有 REST path。

## 8. Normative Wording

当其他文档写 `GET /api/...`、`POST /api/...` 或 "endpoint" 时，**v1 core 互操作以 HTTP/JSON binding 为
normative 形态**。其他 transport 是 extension，需要显式声明对应 binding profile。

v1 core conformance 测试 MUST 包含：

- semantic operation test
- HTTP binding test

声明非 HTTP binding profile 的实现额外提供该 binding 的 mapping test。
