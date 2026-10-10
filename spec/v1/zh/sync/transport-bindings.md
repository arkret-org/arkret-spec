---
title: Transport Bindings
status: candidate
normative: true
stability: v1
updated: 2026-07-16
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
`ak.profile.station.v1` / `ak.profile.full_client.v1` 等 v1 core profile 的实现
**MUST** 提供 HTTP/JSON binding；其他 transport（gRPC、WebSocket-frame、SSE、message queue、
libp2p）属于 **binding extension profile**，core 实现 **不要求** 提供。本规范当前定义的
第一个可选 profile 是 [`ak.profile.binding.websocket.v1`](./websocket-binding.md)。

> Rationale: HTTP/JSON 是 core normative surface（完整契约见 `arkret-service-api.openapi.yaml`
> 完整描述）。gRPC / WebSocket / MQ / libp2p 由独立 binding extension profile 单独 normative
> 化，避免在 core 中只给几行说明就声称 transport-agnostic。Sync stream / events feed 的事件
> 驱动语义可由独立 AsyncAPI 描述补充，但不改变 core 锁定。

### 1.1 Stream frame 序列约束的机读锚点（normative）

`ak.self.account.stream.subscribe.v1` 与 `ak.self.committed_event.stream.subscribe.v1` 的 NDJSON 多帧序列必须按各自 frame schema 与下列完整 trace 断言测试；逐帧 JSON Schema validation 不能替代序列测试：

- 必须固化并执行的 frame 序列约束（散文真相源见 client-sync.md，本节集中列举其 testable 形式）：
  1. `catchup=true` 时，`catchup_complete` 之前 MUST 至少出现一个 `delta` frame（baseline / catch-up delta）；`catchup=false` 时 MUST NOT 出现 `catchup_complete`。
  2. `dropped` frame MUST 携带 `cursor`；服务端无可用补齐 cursor 时 MUST 改发 `resync_required`（不带 cursor），MUST NOT 发送无 cursor 的 `dropped`。
  3. `delta` / `checkpoint` / `catchup_complete` frame MUST 携带 `cursor`；`heartbeat` / `resync_required` / `unauthorized` MUST NOT 依赖 cursor 推进位置。
  4. 客户端用作下一次 `after=` 的位置只来自 cursor-bearing frame 的 `cursor`；不带 cursor 的控制帧不推进重连位置。
- Stream 帧的事件驱动 schema MAY 另由 AsyncAPI 文档作 informative 补充；AsyncAPI 不改变本节 vector 的 normative 判定，也不改变 §1 的 core transport 锁定。

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

Transport binding MUST 映射到 `artifacts/registry/contract-registry.json#operation_registry` 中定义的 canonical `operation_id`。`artifacts/registry/operation-registry.json` 是实现可直接消费的生成视图。取值使用 `ak.<namespace>.<lower_snake_case>`。下表只是核心示例；完整集合以 generated registry 为准，OpenAPI、gRPC、MQ、SSE、WebSocket 和 libp2p binding 均不得声明 catalog 中不存在的 operation。

| Operation | 语义 |
| --- | --- |
| `ak.server.read.describe.v1` | 返回服务 DID、service type、profile、feature、binding 与限制。 |
| `ak.root.identity.read.resolve.v1` | 解析 DID，返回 DID document 与 normalized principal view。 |
| `ak.root.identity.log.read.list.v1` | 获取 DID key log。 |
| `ak.root.identity.command.submit_did_operation.v1` | 提交 DID 更新操作。 |
| `ak.self.events.command.submit.v1` | endpoint-specific closed union：普通 Event、MLS Commit、四 Event DC founding 原子 unit 或 membership compensation 原子 unit。 |
| `ak.self.committed_event.resource.get.v1` | 按 ID 读取单个 Event。 |
| `ak.self.committed_event.read.scan.v1` | 按获准的单个 authority stream 与 `stream_position` 连续查询 Event；不使用 cursor。 |
| `ak.self.committed_event.stream.subscribe.v1` | 订阅获准 stream 的增量流，可选 bounded catch-up replay。 |
| `ak.peer.events.command.submit.v1` | 唯一 peer Event ingress；closed union 严分 `authority_forward` 单提交、bounded `committed_replication` 与 `registered_atomic_unit`。 |
| `ak.peer.committed_event.read.scan.v1` | federation peer 按获准的单个 authority stream 与 `stream_position` 拉取或回填 Event；不使用 cursor。 |
| `ak.peer.contacts.command.submit.v1` | federation peer以closed XOR投递原签名`ak.contact.*` fact、对应source-signed acceptance receipt与可刷新current proof；不得承载`ak.direct_conversation.bound`、共享Realm Event或unsigned service row。 |
| `ak.self.contact.command.scope_update.v1` | Contact issuer-local signed full-set scope replacement，固定`phase=prepare\|commit`。 |
| `ak.self.agent.participation.resource.replace.v1` | controller 通过 bearer+DPoP 在自己的 Account Authority 原子替换一个 versioned per-scope selection；不产生 Realm Event、不走 peer relay。 |
| `ak.self.account.read.viewer.v1` | 当前 holder 的账号主体自读；响应使用 signed handle claim / ref / digest。 |
| `ak.self.account.command.update_profile.v1` | closed `{profile_event}` 提交 holder-signed `ak.profile.create` 或 `ak.profile.update`；Event 的 `actor_id` 必须是 `kind="account"` 且其 `account_id` 逐字段等于 authenticated session 的 exact `AccountId`，`realm_id` 必须等于该账号的本地唯一 PCR lineage，服务端只走 ordinary admission。create ID 由 Event 派生；Event preconditions 为空，update 并发只使用可选 signed `payload.expected_state_digest`，patch 仍只允许 display/avatar/profile_fields；exact replay 不重复 account-aggregate delta。 |
| `ak.self.account.stream.subscribe.v1` | 客户端账号视角聚合同步入口；HTTP binding 使用 `AccountSubscribeFrame` NDJSON account-aggregate frame stream。 |
| `ak.gate.account.exchange.create_handoff.v1` | OIDC code 换 DPoP-bound account handoff，并返回 binding / identity-creation lease 状态；不是 session grant。 |
| `ak.gate.account.command.issue_identity_binding_challenge.v1` | 为当前 handoff lease 保留DID operation，并签发服务端持久化的一次性 root-control challenge。 |
| `ak.gate.account.command.register.v1` | 注册 / account binding；account-first 分支内部发布客户端签名的 DID inception 并按 account/principal/operation digest 幂等绑定；不接受裸 `handle` 或 root secret。 |
| `ak.gate.account.command.revoke_session.v1` | 撤销 session grant；不撤销 device authorization。 |
| `ak.self.blob.upload.create.v1` | 上传 blob。 |
| `ak.self.blob.resource.get.v1` | 获取 blob 或下载授权。 |
| `ak.edge.push.command.register_device.v1` | 注册推送设备和推送网关。 |
| `ak.edge.push.command.notify.v1` | 投递脱敏唤醒。 |
| `ak.self.authz.read.check.v1` | 检查 capability / policy 是否允许动作。 |
| `ak.self.moderation.command.report.v1` | 提交 direct-holder signed `ak.self.moderation.report` Event；服务端只做 exact validate-and-forward，不代签或重建举报。 |
| `ak.edge.applet.command.transaction.v1` | 向 Applet 推送事件批次。 |
| `ak.edge.applet.read.describe.v1` | 查询 Applet profile、namespace 与限制。 |
| `ak.self.device_messages.command.send.v1` | 将 to-device message 批次放入目标设备短期队列；HTTP binding 是 `POST /_arkret/self/device_messages`，因其语义是 send/fanout command，而不是 URI 资源替换。 |
| `ak.self.keys.upload.create.v1` / `ak.self.keys.read.lookup.v1` / `ak.self.keys.command.claim.v1` | E2EE 设备密钥发布、查询与领取。 |
| `ak.self.keys.backups.resource.replace.v1` / `ak.self.keys.backups.read.list.v1` / `ak.self.keys.backups.command.unlock.v1` / `ak.self.keys.backups.resource.delete.v1` | 加密密钥备份对象存储、枚举、解锁取回与删除。 |

> **Federation peer surface（规范性）**：跨服务器互通必须使用 `/_arkret/peer/*` HTTP trust surface 和 `ak.peer.*` operation_id。`/_arkret/self/*` 只承接当前 principal / 已授权自服务会话的攻击面，不承接 federation server-to-server wire。**联邦接收收敛为单轨**：`POST /_arkret/peer/events`（`ak.peer.events.command.submit.v1`）是唯一的 federation Event 接收轨，但 wire 必须命中闭合的 `authority_forward | committed_replication | registered_atomic_unit` 分支之一。forward 只由 current authority 首次接纳；replication 必须携 source Event+RealmCommit 并且只持久化副本；atomic unit 只能使用 registry 已登记 unit kind 并整组成功或零写。实现私有 peer 入站轨、schema 外 batch 或跨分支字段 MUST NOT 作为跨 deployment 互通入口（详见 [`federation.md` §4.1](./federation.md)）。

HTTP binding MAY 把 `operation_id` 映射成路径；gRPC binding MAY 把它映射成 service method；message queue binding MAY 把它映射成 topic + message type。

Agent/Applet runtime 的外部协议配置、handoff 进度、私有 session id 与实现状态不属于 Arkret transport binding，也不得回流为共享 Realm history；只有跨实现有 canonical 语义的结果对象才能通过已注册 Arkret Event 或 operation response/stream 传递。

## 5. HTTP/JSON Binding

HTTP/JSON 是默认 profile：

- JSON request / response 使用 UTF-8。
- 生产环境使用 HTTPS。
- 写操作使用 `Idempotency-Key` header 或 body 内 `idempotency_key`。

> **PQ-hybrid TLS 传输层姿态（canonical 表述）**：本节是 TLS PQ-hybrid 义务的真相源。生产 v1 部署的 service-to-service（federation peer）与 client-service TLS 1.3 连接 SHOULD 支持并优先协商混合后量子 group `X25519MLKEM768`（TLS 1.3 hybrid named group，经典 X25519 + ML-KEM-768 / NIST FIPS 203；`draft-ietf-tls-ecdhe-mlkem-05`）。`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1` 及继承它们的 profile 下，service-to-service 与 client-service 连接 MUST 协商 `X25519MLKEM768`；对端不提供该 group 时 MUST fail closed，MUST NOT 静默降级到纯经典 key exchange。default profile MAY 在对端不支持该 group 时回落到经典 TLS 1.3 key exchange，但 MUST 把该连接记录为 `transport_pq=not_negotiated`（或等价部署探针证据），并且 MUST NOT 宣称该连接具备 Harvest-Now-Decrypt-Later resistant transport posture。该姿态把 HNDL 缓解扩到仅靠 TLS 保护、不进 MLS / E2EE 的传输面（联邦 transaction 元数据、public plaintext Realm 内容、directory / sync 流量），不改任何 canonical `operation_id`、binding、Arkret wire envelope / schema / object model，也不触碰 envelope `scheme` / `version`，与请求级 RFC 9421 签名正交。高安全 / sovereign conformance 验证为 deployment-profile 握手探针：握手完成后检查协商出的 TLS named group 是否等于 `X25519MLKEM768`，并验证对端不提供时 fail closed，而非 object-model conformance vector。完整威胁论据见 [`../security/server-threat-model.md` §2.4](../security/server-threat-model.md)；联邦链路呼应见 [`federation.md` §3.2](./federation.md)；sovereign / 高安全部署的探针落地见 [`sovereign-deployment.md` §3 / §11](./sovereign-deployment.md)。
- 流式结果 MAY 使用 SSE、WebSocket 或 newline-delimited JSON。
- 错误使用统一 JSON error object，并映射到 HTTP status。

HTTP binding 的 canonical 路径和请求/响应 shape SHOULD 遵循 `service-http-binding.md`、OpenAPI 以及生成的 `artifacts/reports/operation-schema-index.json`；`service-api-schema.mdx` 只提供 operation 分组与治理说明视图。实现不得把未注册路径宣称为 Arkret canonical binding，不得在 `/_arkret` namespace 中表达版本，也不得包含 `/v1/`、`/api/v1`、`/arkret/v1` 等版本 path 段。v1 core conformance 测试始终以 canonical HTTP/JSON path 与字段为基准。

## 6. Non-HTTP Binding Extensions

gRPC、WebSocket / SSE、WebTransport over HTTP/3、Message Queue (Kafka / NATS / Pulsar / AMQP)
与 P2P / libp2p binding **不是 v1 core 互操作 surface**。其中 WebSocket 的可选 normative
profile 见 [`websocket-binding.md`](./websocket-binding.md)；其它 transport 当前只保留
extension profile slot，不具有可互操作的 wire format、operation mapping 或 stream framing。

任何声明此类 binding 的部署 MUST 自行发布独立 binding profile 文档（profile id 形如
`ak.profile.binding.<transport>.v1`），并在该文档中至少明确：

- canonical `operation_id` → transport-specific 调用形态的映射；
- envelope / frame schema、签名绑定、idempotency key 与 cursor 处理；
- 错误码到 transport native status 的映射；
- 服务发现如何在 `transport_bindings` 中声明该 binding 与其能力。

未声明对应 binding profile 的实现 MUST NOT 接受非 HTTP/JSON 流量，也不得要求对端支持。
v1.0 conformance suite 不测试任何非 HTTP binding；gRPC / WS / WebTransport / MQ / libp2p 等
transport MUST 各自通过 binding profile 单独 normative 化。

### 6.1 Per-operation HTTP 伴生 binding（normative）

与上述 service-wide 替代 transport 不同，**per-operation HTTP 伴生 binding** 指仍运行在 HTTPS 之上、只覆盖单个 canonical `operation_id` 的替代 HTTP 交互形态（例如 `ak.self.blob.upload.create.v1` 的 tus 可续传上传 binding，见 [`../crypto-media/media-and-blob.md` §2.1](../crypto-media/media-and-blob.md)）。这类 binding：

- MUST 由 core 规范文档直接 normative 化（含 operation 映射、认证/capability 复用、错误语义与 discovery 声明），不要求独立 `ak.profile.binding.<transport>.v1` profile；
- MUST 以对应 exact `ak.feature.*.v1` id 在 `describe.supported_features` 声明，并通过已登记
  `supported_operation_bundles[]` 展开其覆盖的 operation pair；`transport_bindings` 条目只声明 endpoint 与 transport
  参数，不复制成员清单，`extension_profile_required` 为 `null`；
- MUST NOT 改变所覆盖 operation 的语义结果（响应对象、receipt、内容寻址等与 canonical HTTP/JSON binding 一致）；
- 不改变本节对 service-wide 非 HTTP transport 的 binding profile 要求。

## 7. Binding Discovery

服务描述 SHOULD 返回：

```json fragment
{
  "service_kind": "station",
  "service_id": "ak:did_core:webvh:z5CVGhWHEfRe1HhKLRueCrxfD",
  "service_resolution": {
    "did": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example",
    "method_history_head": "sha256:bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb",
    "version_id": "3"
  },
  "transport_bindings": [
    {
      "kind": "http_json",
      "base_url": "https://server.example",
      "extension_profile_required": null
    }
  ],
  "supported_operation_bundles": [
    "ak.operation_bundle.station.describe.v1",
    "ak.operation_bundle.station.http_core_current.v1"
  ]
}
```
`transport_bindings[]` 必须通过
[`transport-binding.schema.json`](../../artifacts/schemas/transport-binding.schema.json)
验证。当前注册 kind 为 `http_json`、`tus` 与 `websocket`；未知 kind 不能覆盖任何 bundle pair，
若它是公告能力所需的唯一 carrier，客户端必须 fail closed。WebSocket 条目的 `kind` 通过 registry/schema identity
固定 `ak.profile.binding.websocket.v1`、所需 subprotocol 与认证；条目只声明连接坐标和 limit 字段，
不得回显这些固定参数。

其它 binding（gRPC / SSE / WebTransport / MQ / libp2p）需先发布对应 binding profile 和
machine registry/schema，才可出现在此处；v1 core 仅要求 `http_json`。WebTransport profile
必须精确钉定所用 revision、stream/datagram 对 canonical operation 与 stream-frame 的映射、
Origin 校验、session authentication 与 reconnect/cursor 语义，不得仅因底层运行在 HTTP/3
就当作 `http_json`。§6.1 的 per-operation HTTP 伴生 binding（如 `kind="tus"`）以
`extension_profile_required: null` + 对应 exact feature 与 operation bundle 声明出现，不需要 binding profile id。

客户端 MUST 根据 `transport_bindings` 选择 transport，不得假设所有服务都有 REST path。

## 8. Normative Wording

当其他文档写 `GET /api/...`、`POST /api/...` 或 "endpoint" 时，**v1 core 互操作以 HTTP/JSON binding 为
normative 形态**。其他 transport 是 extension，需要显式声明对应 binding profile。

v1 core conformance 测试 MUST 包含：

- semantic operation test
- HTTP binding test

声明非 HTTP binding profile 的实现额外提供该 binding 的 mapping test。
