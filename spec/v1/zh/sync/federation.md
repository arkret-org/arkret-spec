---
title: Federation
---

## 1. 目标

Contrix 是去中心化协议，不同用户或组织各自运行受控 Principal Server。当来自不同域的 Actor 需要在同一个 Space 中协作时，Principal Server 之间需要一套**跨域联邦协议 (Federation Protocol)**，定义：

- 节点之间如何互相发现与认证
- 如何安全交换签名 Event Envelope
- 如何处理跨域加入 Space 的请求
- 如何在异构网络中维持因果一致性

## 2. 设计原则

### 2.1 Event Chain 是信任锚点

跨域协作的信任不来自"服务器管理员彼此认识"，而来自**每个 Actor 的 signed Event chain 都是密码学可验证的**。任何节点在接收到来自外部域的 Event Envelope 时，可以独立验证签名、DID、`actor_seq`、`prev_refs` 和授权因果链，不需要信任对方服务器。

### 2.2 Principal Server 是受控同步边界，不是全局权威

联邦场景中没有独立第三方分发服务器角色。Space 范围传播由参与方 Principal Server 之间的 federation transaction 完成。Principal Server 不能伪造、篡改或选择性隐藏已签名的 Event Envelope；任何参与者都可以通过直接查询源 Events API、witness receipt、snapshot frontier 或其他受信 Principal Server 交叉验证历史。

### 2.3 Anchor Finality 优于全局同步共识

跨域网络延迟不可预测。联邦协议不要求所有 Principal Server 同步参与一个全局共识组；每个 Space 通过 Anchor DAG 表达 ordering commitment。`single_did`（中心化 hub）、`threshold`（k-of-n 委员会）、`open_set`（开放对等）和 `mixed`（含 sovereign fallback）只是 `anchorer` cell value 与 Anchor profile 的不同配置；详见 §2.4。

### 2.4 Anchor Profile 决定传播形态

联邦传播按目标 Space 的 `anchor_profile`（参见 [`../models/space-and-place.md` §2.2](../models/space-and-place.md)）走几种形态：

- **`single_did`**：单一 service DID 签发持久 Anchor。Actor 可以向自己的 Principal Server 提交 Move，但 Move 只有被该 DID 签发的 Anchor frontier 覆盖后才 effective。传播形态是 actor/server → anchorer → fanout。
- **`threshold`**：k-of-n committee 签发 Anchor。提交路径与 `single_did` 类似，但 Anchor 验证 threshold signature。
- **`open_set`**：多个 federation peer / admin DID 可以签发 leaf Anchor。Principal Server 之间 push / pull pending Move 与 Anchor leaf；查询时使用 deterministic effective anchor view join。
- **`mixed`**：正常由主 anchorer 签发 Anchor；主 anchorer 故障、签发矛盾 Anchor 或 anchorer cell 变成 `⊥` 时，fallback recovery anchorer 可以签发恢复 Anchor。

跨域 Space 跨过两个 deployment（A 与 B）时，`anchor_profile` 与 genesis anchorer 由 Space create 固定，所有参与 deployment 都按同一 Anchor 验证规则处理；不存在 "A 当 hub、B 当 peer mesh" 的分裂状态。

## 3. 节点间认证

### 3.1 基于 DID 的服务器身份

每个 Principal Server / Events API 节点 MUST 拥有自己的 DID（通常是 `did:web`），并在其 DID Document 中声明 Service Endpoints：

```json
{
  "id": "did:web:server.acme.example.com",
  "service": [
    {
      "id": "#contrix-principal-server",
      "type": "ContrixPrincipalServer",
      "serviceEndpoint": "https://server.acme.example.com/api/v1"
    }
  ],
  "verificationMethod": [
    {
      "id": "#server-key-1",
      "type": "Ed25519VerificationKey2020",
      "publicKeyMultibase": "z6Mkf..."
    }
  ]
}
```

其中 DID Document 的 `service.type` 使用协议注册名（如 `ContrixPrincipalServer`），服务 describe 响应中的 `service_type` 使用运行时注册值（如 `principal_server`）。联邦鉴权 MUST 校验两者的绑定关系，不得只凭域名或 URL 接受请求。

### 3.2 请求签名

节点间的 HTTP 请求 MUST 使用 [HTTP Message Signatures (RFC 9421)](https://datatracker.ietf.org/doc/html/rfc9421) 进行签名。接收方通过发送方 DID Document 中的公钥验证请求的真实性。

签名 transcript MUST 覆盖以下 RFC 9421 derived components 与 header 字段：
- `@method`
- `@target-uri`
- `@authority`
- `content-digest`（针对有 body 的请求；编码遵循 RFC 9530）
- `source-service-did`（自定义 header `Source-Service-DID`）
- `destination-service-did`（自定义 header `Destination-Service-DID`）
- `request-canonical-hash`（自定义 header `Request-Canonical-Hash`）
- 签名 parameters MUST 包含 `created` 与 `expires`（不得用 `Date` header 替代）

签名验证规则：

- body 中的 `origin` / `destination` MUST 与签名 transcript 中的来源 / 目标 service DID 一致。
- `destination` MUST 是接收方 service DID；反向代理、多租户 host 或 shared ingress 不能只凭 `Host` 判断目的地。
- 请求带 body 时 MUST 携带 `Content-Digest`，且 digest 必须覆盖 canonical request body。
- 受保护联邦 endpoint MUST NOT 接受 query string 认证。
- 签名失败、destination 不匹配、digest 不匹配或时间窗口失效 MUST 返回标准 error envelope，并尽量不泄露 Space、Actor 或 Event 是否存在。

### 3.3 域信任模型

Contrix 不要求全局信任列表。每个节点维护自己的**联邦许可列表 (Federation Allow List)**：

- **开放联邦 (Open)**：接受来自任何域的合法签名请求。适合公共协作场景。
- **受限联邦 (Restricted)**：仅接受来自预配置域列表的请求。适合企业内部或联盟场景。
- **封闭 (Closed)**：不接受任何外部联邦请求。适合纯内部部署。

## 4. Event 交换协议

### 4.1 推送模式 (Push)

> **v1 联邦不再使用独立 HTTP API surface**。跨域 Event 推送复用普通 events API（`POST /api/v1/events` 对应 `cx.events.submit`），把"联邦"与"客户端写入"的区别下沉到认证层：service-to-service 调用 MUST 使用 HTTP Message Signature + `Source-Service-DID` / `Destination-Service-DID` header；普通用户写入使用 user session / device proof。本节描述的所有规则适用于带 service signature 的 `cx.events.submit` 调用。

本文件中的联邦载荷项是 v1 规范性 Event Envelope。请求与响应体中的共享事实字段使用 `events[]`，不引入第二套 Operation wire object。

当 Actor A（托管在 `server-alpha.com`）向 Space S 提交了新 Event，而 Space S 的另一参与方 Principal Server `server-beta.com` 也服务同一个 Space 时：

1. `server-alpha.com` 检测到新 Event 属于跨域 Space
2. `server-alpha.com` 从 Space policy / membership / service delegation 中解析应接收该 Event 的对端 Principal Server，并生成接收方服务绑定快照
3. `server-alpha.com` 向 `server-beta.com` 发送推送请求：

```
POST /api/v1/events
Host: server-beta.com
Source-Service-DID: did:web:server-alpha.com
Destination-Service-DID: did:web:server-beta.com
Content-Digest: sha256=:<base64>:
Signature-Input: sig1=("@method" "@target-uri" "@authority" "content-digest" "source-service-did" "destination-service-did");created=...;expires=...
Signature: sig1=:base64...:
```

请求字段（service-to-service 形态）：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Source-Service-DID` | header | `did` | required | 来源 service DID；与签名 transcript 绑定。 |
| `Destination-Service-DID` | header | `did` | required | 目标 service DID；MUST 与目标 URL、DID service endpoint 和 Space policy 委托一致。 |
| `Signature-Input` | header | `string` | required | HTTP Message Signature 输入；MUST 至少绑定 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-did`、`destination-service-did`，以及 `created` / `expires` 参数。 |
| `Signature` | header | `string` | required | 来源 service DID 的 HTTP Message Signature。 |
| `Content-Digest` | header | `string` | required | 请求体摘要，MUST 覆盖 canonical request body；接收方 MUST 在验签前先校验 body 实际 hash 与 header 一致，再走签名 transcript 校验。 |
| `events` | body | `object[]` | required | Event Envelope 数组；每项 MUST 是完整签名 `cx.schema.event.v1`。复用 §3 client write 同一 schema，不引入第二套形态。 |
| `service_binding_ref` | body | `object` | required | 接收方服务绑定快照（v1 联邦特有的请求级元数据；client write 时省略）。 |
| `service_binding_ref.space_id` | body | `id` | required | 受影响的 Space。在多 Space 批量推送中，发送方 SHOULD 把不同 Space 的 events 拆成独立请求；单请求 MUST 至少携带一个 `space_id`。 |
| `service_binding_ref.space_policy_hash` | body | `sha256:<hash>` | required | 发送方用于判定接收方委托关系的 Space policy hash。 |
| `service_binding_ref.membership_frontier` | body | `id[]` | required | membership / policy 因果前沿。 |
| `service_binding_ref.destination_service_type` | body | `string` | required | 目标服务类型，例如 `principal_server`。 |
| `service_binding_ref.reducer_profile_hash` | body | `sha256:<hash>` | required | 发送方在此 Space 使用的 reducer profile canonical hash（覆盖 `cx.reducer.<id>.v<n>` 的完整规则定义）。接收方 MUST 与自己的 reducer profile 比对；不一致 MUST 拒绝整批请求并返回 `reducer_profile_mismatch`。这避免了同一 Event 在两端 reducer 下产生不同 cell 状态、state_root 或 covered_frontier，进而被 idempotent 接受却不可重放的隐性失败。 |

> **关于旧字段 `origin` / `destination` / `space_id`**：v1 之前的草案曾把这三项放在 body 顶层。v1 已合并联邦 surface 后，`origin` / `destination` 已由 header `Source-Service-DID` / `Destination-Service-DID` 承担（避免 body 与 header 双源真相）；`space_id` 移入 `service_binding_ref` 内部，与其它服务绑定快照字段一起验证。发送方与接收方 MUST 使用新形态。

请求示例（非完整 schema；`Source-Service-DID` / `Destination-Service-DID` 由 header 承载，不重复在 body 中）：

```json
{
  "service_binding_ref": {
    "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:event:..."],
    "destination_service_type": "principal_server",
    "reducer_profile_hash": "sha256:..."
  },
  "events": [
    {"_comment": "<完整签名 Event Envelope，符合 cx.schema.event.v1>"}
  ]
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `accepted` | `id[]` | required | 已接受 Event ID。 |
| `rejected` | `object[]` | required | 被拒绝项；每项 SHOULD 包含 `id`、`reason_code` 和可审计说明。 |
| `quarantine` | `id[]` | optional | 进入隔离队列等待人工或异步验证的 Event ID。 |

4. `server-beta.com` 独立验证每个 Event 的 Actor 签名、Space policy、服务委托、接收方服务绑定和因果链，然后决定是否接受

错误响应 MUST 使用 `api-conventions.md` 中的标准 JSON error envelope。批量请求中，单条 Event 的拒绝 SHOULD 进入 `rejected[]`；整个请求无法认证、目的地不匹配、schema 解析失败或被限流时 SHOULD 返回对应 HTTP 错误。`rate_limited` 和可预期恢复的 `temporarily_unavailable` SHOULD 携带 `Retry-After`。

Contrix v1 的联邦批量传播采用依赖感知的 partial accept：最小原子单元是单个 Event 及其已接受依赖，而不是整个请求数组。接收方已经 accepted 的 Event 不因后续 Event 失败而回滚；后续 Event 若依赖同批失败项，必须拒绝或隔离并暴露依赖诊断。需要 all-or-nothing 批处理的部署必须通过 profile / critical extension 显式协商。

`events[]` MUST 按数组顺序处理。同批中已接受的 Event 可以满足后续 Event 的 `prev_refs`、`refs[role=authorized_by]` 或 payload-level causal reference；同批中尚未处理、已拒绝或隔离的 Event 不能被视为已接受依赖。单条 Event 失败不得回滚同批已接受 Event；响应 MUST 将成功项放入 `accepted[]`，失败项放入 `rejected[]`，需要异步校验的项放入 `quarantine[]`。依赖同批失败或缺失 Event 的后续项 MUST 以 `dependency_missing`、`causal_conflict` 或等价原因拒绝/隔离。

接收方服务绑定规则：

- Actor DID 的当前 DID Document MAY 声明其受控或委托的 `ContrixPrincipalServer` endpoint。
- Organization DID 或 Space policy MAY 为组织成员、受管设备或特定 Space 指定 Principal Server。
- Space metadata 的 `sync_endpoints` 只表示 Space policy 明确委托的 shared anchorer / sync service 或组织 Principal Server，不自动授权任意第三方接收私有内容。
- 联邦 transaction MUST 绑定 `destination` service DID、Space policy hash / version、membership frontier 和目标 endpoint；接收方 MUST 校验自己在该快照下有权接收该 Space 的事件。
- 当服务委托被撤销或成员被移除后，生效因果点之后不得继续向已撤销 service DID 推送非加密私有内容；历史 backfill 也必须按撤销后的 visibility 与 history policy 重新判定。

### 4.1.0 推送时序

下图把 push transaction 的握手画成时序图。**信任根是签名 Event 本身 + RFC 9421 HTTP Message Signature + 接收方服务绑定快照，不是任何一方服务器的本地数据库。**

```mermaid
sequenceDiagram
    autonumber
    participant Cli as Actor 客户端
    participant Alpha as server-alpha 发送方
    participant Pol as Space S policy
    participant Beta as server-beta 接收方

    Cli->>Alpha: 提交 signed Event 到 Space S
    Alpha->>Pol: 解析应接收的 Principal Server
    Pol-->>Alpha: 接收方列表 + service_binding_ref<br>(space_policy_hash / membership_frontier / reducer_profile_hash)
    Alpha->>Beta: POST /api/v1/events (cx.events.submit)<br>HTTP Message Sig (RFC 9421)<br>Source-Service-DID / Destination-Service-DID<br>Content-Digest / service_binding_ref / events 数组
    note over Beta: 校验:<br>1. 签名 transcript + destination DID 匹配<br>2. content-digest 覆盖 body<br>3. allow list / federation_policy<br>4. service_binding_ref 与本地一致<br>5. 逐 Event verify_event + actor chain<br>6. anchor_ref / Lattice precondition
    Beta-->>Alpha: 200 + accepted / rejected / quarantine
    note over Alpha: 失败项<br>重试 / quarantine / 暴露给上游 actor
```

读图要点：

- 接收方独立验证每个 Event 的签名与因果链，不信任发送方服务器；服务器之间的握手只是传输面认证。
- `service_binding_ref.reducer_profile_hash` 不一致时整批拒绝（`reducer_profile_mismatch`），避免同 Event 在两端 reducer 下产生不同 cell 状态的隐性失败。
- 批内单 Event 失败 **不**回滚同批已接受 Event；依赖同批失败项的后续 Event 必须 `dependency_missing` / `causal_conflict` 拒绝或 quarantine。

### 4.1.1 批量推送与幂等

Contrix v1 联邦推送 **复用** `POST /api/v1/events`（`cx.events.submit`）一个 endpoint，认证侧由 service signature header 区分；不再定义独立 `/federation/*` path：

- 幂等以 `(Source-Service-DID, Destination-Service-DID, event_id)` 逐事件去重；接收方对重复 `event_id` 且内容一致 MUST 返回 `accepted[]` 而非报错，内容不一致 MUST 拒绝（参见 §4.3）。
- 批次级重放检测使用签名 transcript 中的 `Request-Canonical-Hash` 与 `Idempotency-Key` header（详见 §8.5），不引入额外的 path 事务 ID。
- `quarantine[]` 项 SHOULD 放入 `rejected[]` 并附 `reason_code=quarantined`，或由实现扩展响应 schema。
- 持续同步、批量重试和 frontier 交换通过组合 `cx.events.submit`（推送，本节）、`cx.events.query`（拉取 / backfill，§4.2）与 frontier exchange（§4.5）完成；无需额外的有状态事务 endpoint。

### 4.2 拉取模式 (Pull / Backfill)

当节点发现自己的因果图中存在缺失（`prev_refs` 或 `refs[role=authorized_by]` 引用了本地没有的 Event）时，可以主动向源 Principal Server 或源 Events API 拉取。**v1 联邦 pull 复用 `cx.events.query`**（`GET /api/v1/events`），通过 `before=<cursor>` 表示历史回填（取该 cursor 之前最近一批），认证使用与 §4.1 同一套 service signature header：

```
GET /api/v1/events?spaces=cx:space:...&before=<cursor>&limit=100
Host: server-alpha.com
Source-Service-DID: did:web:server-beta.com
Destination-Service-DID: did:web:server-alpha.com
Signature-Input: ...
Signature: ...
```

请求字段（query；完整参数集与默认顺序规则见 [`service-http-binding.md` §3.3](./service-http-binding.md)）：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `spaces` | query | `id[]` | required | 请求回补的 Space。 |
| `before` | query | `cursor` | conditional | 取该 cursor *之前*（排除）的最近一批；历史 backfill 主用例。`before` 与 `after` 至少给其一，否则服务端按隐式 `before=<server_head>` 处理。 |
| `after` | query | `cursor` | conditional | 取该 cursor *之后*（排除）的最近一批；catch-up 场景使用。 |
| `order` | query | `enum(default, ascending, descending)` | optional | 联邦 pull 默认沿用 §3.3 "近邻先返回" 规则——仅 `before` 时 descending，仅 `after` 时 ascending；reducer-导向场景显式 `order=ascending`。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值（见 [`scalability-constraints.md`](../conformance/scalability-constraints.md)）。 |

响应字段（与单域 `cx.events.query` 响应同源；联邦特化的 `snapshot_bootstrap` 是 optional 加速返回）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `events` | `object[]` | required | Event Envelope 数组；每项 MUST 保持原始签名信封。批次内顺序按 `order` 规则与"近邻先返回"默认（[`service-http-binding.md` §3.3.3](./service-http-binding.md)）。 |
| `snapshot_bootstrap` | `object` | optional | 可选的快照加速返回；如有则接收方 MUST 校验签名并验证 frontier 一致性后才可使用。详见 §9.1。 |
| `prev_cursor` | `cursor` | optional | 朝**更旧事件**方向的延续位置；下次请求传入 `before=<prev_cursor>` 继续历史 backfill。 |
| `next_cursor` | `cursor` | optional | 朝**更新事件**方向的延续位置；下次请求传入 `after=<next_cursor>` 继续 catch-up。 |
| `has_more` | `boolean` | required | 是否仍有可拉取的 Event；客户端到达 oldest accessible event 时 `false`。 |

> **关于旧 endpoint `GET /api/v1/federation/pull-operations`**：v1 之前的草案曾定义独立 federation pull endpoint。v1 已合并到 `cx.events.query`；旧 endpoint 不应再被实现或文档。`snapshot_bootstrap` 字段仍以 optional 形式出现在 `cx.events.query` 响应中（仅 service-to-service 调用、Space policy 显式允许时）。

`snapshot_bootstrap` 字段（存在时）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `snapshot_ref` | `id` | optional | 快照标识。 |
| `state_hash` | `string` | optional | 快照状态根，必须与快照 frontier 对应。 |
| `snapshot_frontier` | `id[]` | optional | 需要从该 frontier 之后开始增量回放。 |
| `signature` | `object` | optional | 标准 Snapshot detached proof，覆盖 `snapshot_ref`、`state_hash`、`snapshot_frontier` 和 reducer/schema profile。 |
| `signature.verification_method` | `string` | optional | 用于信任锚点的 DID verification method。 |
| `signature.alg` | `string` | optional | 签名算法。 |
| `signature.jws` | `string` | optional | detached JWS。 |

### 4.3 重复与幂等

- 同一个 `event_id` 的 Event MAY 被多个 Principal Server 推送多次
- 接收方 MUST 以 `event_id` 去重
- 内容相同的重复推送 MUST 幂等接受
- `event_id` 相同但内容不同的推送 MUST 拒绝

### 4.4 Capability Revoke Fanout

`cx.capability.revoke`、superseding grant、membership removal、ban、device/session revoke 和会使既有 allow cache 失效的 policy change 是高优先级 auth state。源 Principal Server 在接受这类 Event 后，MUST 主动推送给所有当前已知的相关 Principal Server，而不是只等待对端下一次 pull：

- fanout 目标包括 Space policy / membership / service delegation 中声明的 shared anchorer / sync service、受影响 subject 的 Principal Server、grant issuer / delegatee 所在 Principal Server，以及正在服务该 Space 的 federation peer。
- 推送 payload MUST 包含原始 Event Envelope、必要 auth refs、当前 auth frontier 或可验证 snapshot reference，便于接收方立即失效 capability cache。
- 接收方即使暂时无法完整验证该 revoke，也 MUST 将匹配 scope 的 allow cache 标记为 stale / `revoke_freshness_unknown`，直到 backfill 完成。
- fanout 失败时，源服务器 MUST 保留重试队列并在后续 federation transaction、frontier probe 或 pull 响应中暴露缺失诊断；不得因单个 peer 不可达而回滚已 accepted revoke。

该主动推送只加速缓存一致性，不替代接收方对签名、Move refs、Anchor frontier、Lattice state_root 和 policy 的独立验证。

### 4.5 Fork Detection / Frontier Exchange

参与同一 Space 的 federation peer 通过 frontier 交换检测 silent fork。本节定义三层职责：peer **MUST** 实现 frontier probe **能力**（响应已授权 peer 的查询），baseline 部署 **SHOULD** 周期性主动交换，high-assurance / sovereign / regulated profile **MUST** 周期性主动交换并具备失败降级语义。

#### 4.5.1 Frontier Probe 能力 (MUST)

每个参与 Space S 的 federation peer **MUST** 暴露 frontier probe endpoint，使被 Space S policy 授权的对端 peer 可以按需查询当前 frontier。Probe 是 `cx.events.frontier` 服务 operation（见 [`./service-http-binding.md` §3.2](./service-http-binding.md) 与 OpenAPI `cx.events.frontier`）的 federation auth-class 使用形态——v1 不再为 federation 单独引入新 operation；同一 operation_id 通过下表的 auth / response profile 区分调用面：

| 调用面 | 调用方 | 鉴权 | 响应形态 |
| --- | --- | --- | --- |
| Public Events API | account holder / SDK client | 用户/服务 access token | 通常仅 `space_frontier` 或 `actor_seq` 简要视图 |
| Federation peer probe (本节) | 被 Space `service_binding` 授权的 federation peer 服务 DID | §3 节点间认证 + Space policy 列出的 `federation_peer` 角色 | 完整 `(heads, max_hlc, frontier_root, actor_seq_upper_bounds, witness_receipts, signature)` |
| Anonymous / unauth health check | optional | 无 / 限速 token | 仅 `frontier_root` 摘要；MUST NOT 暴露 actor 集合或 seq upper bounds |

Probe **MUST** 是 capability-gated：

- 被 Space `service_binding` 授权为 federation peer 的服务方可读取该 Space 的 frontier 完整形态；
- anonymous 或未授权 reader **MUST NOT** 通过该 endpoint 取得 frontier 完整形态（防止 actor 集合枚举）。如部署允许低权限健康检查，**MUST** 只暴露非敏感摘要（如 `frontier_root` 哈希），不暴露 `actor_seq_upper_bounds` 等可还原 actor 集合的字段。
- Probe 请求与响应都 **MUST** 走 §3 节点间认证。

Probe 响应 payload：

```json
{
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "heads": ["sha256:..."],
  "max_hlc": "01970e589d21-0004-a13f9c2e",
  "frontier_root": "sha256:...",
  "actor_seq_upper_bounds": {
    "did:web:alice.example.com": 144,
    "did:web:bob.example.org": 87
  },
  "witness_receipts": [],
  "observed_at": "2026-05-18T08:30:00Z",
  "issuer": "did:web:server-alpha.com",
  "signature": {}
}
```

字段规则：

- `heads[]` 是当前 accepted frontier 的稳定 event hash；接收方比较两端 heads 集合发现差异。
- `max_hlc` 是 issuer 在 frontier 处观察到的最大 HLC；用于检测时钟严重偏移。
- `frontier_root` 是 canonical Merkle root over `(heads[] ∪ sorted(actor_seq_upper_bounds))`；签名仅覆盖该 root 与 `(space_id, issuer, observed_at)`，便于轻量比对而无需重传全部字段。
- `actor_seq_upper_bounds` 是 issuer 视角每个 federation-visible actor 的 `actor_seq` 上界，用于检测 *per-actor* 缺口（silent fork 常表现为某 actor 的某段 seq 在对端不可见而全局 frontier 仍单调推进）。
- `witness_receipts[]` 可选，包含 witness / receipt service 对 frontier 的 attestation。
- `signature` 是 issuing service 对 canonical probe payload 的签名，按 §3.2 规则。

冲突检测规则：

- 若两端历史包含相同 `event_id` 但不同 hash，接收方 MUST quarantine 并以 `duplicate_conflict` 报告。
- 若冲突来自同一 actor 的不同签名 frontier，接收方 SHOULD 保留最小证据集：冲突 event id、hash、签名 key id、source service DID、收到时间和相关 frontier。证据集不得包含未授权明文 payload。
- 可疑 remote 输入 MAY 在 quarantine 队列中暂存，直到签名、schema、capability、fork resolution 与 operator policy 全部通过。
- `actor_seq_upper_bounds` 差异本身不是冲突证据（合法 partial replication 也会出现差异），但 SHOULD 触发 `cx.events.query` per-actor backfill，并在 backfill 后仍存在差异时升级为 fork suspect。

#### 4.5.2 Baseline 主动交换 (SHOULD)

普通 federation 部署 **SHOULD** 周期性主动交换 frontier；默认建议每个 federation-visible Space 与每个 peer 的间隔不超过 6 小时，超大 Space 或低活跃 Space 可放宽到 24 小时。Baseline 不强制 fail-state，但实现 SHOULD 在 probe 失败时进入指数退避并向运营暴露 diagnostics。

#### 4.5.3 High-Assurance Profile 主动交换 (MUST)

启用 `cx.profile.federation.high_assurance.v1`（high-assurance / sovereign / regulated / multi-writer federation 部署，详见 [`sovereign-deployment.md`](./sovereign-deployment.md)）的服务 **MUST**：

- 每个 federation-visible Space 与每个授权 peer 的 frontier probe 间隔 ≤ **1 小时**；
- 维护 per-peer / per-Space frontier exchange 状态机，跟踪 `last_success_at` 与连续失败计数；
- 连续 3 次 probe 失败（peer 不可达、签名失败、`frontier_root` 不一致超过 fork-resolution 阈值）**MUST** 把该 peer 在该 Space 的状态标记为 `stale_peer`；
- `stale_peer` 状态期间：
  - **MUST** 拒绝以来自该 peer 的 push payload 在本地推进 Space frontier（继续 quarantine，不让 silent fork 永久化），直到 fork resolution 或重新对齐；
  - **MUST** 通过 §8.6 威胁映射要求的 alarm 通道（operator dashboard / audit log / pager hook）暴露该状态；
  - **MAY** 拒绝向该 peer fanout 新 Event。
- fork resolution 成功（heads 重合或 quorum witness attestation 一致）后 **MUST** 解除 `stale_peer` 标记。

启用 high-assurance profile 但实现未实现上述 fail-state 等同于不满足 profile 声明，**MUST NOT** 在 `cx.service_binding` 中声明 `cx.profile.federation.high_assurance.v1`。

## 5. 跨域加入 Space

### 5.1 邀请流程

当 Space S 的管理员邀请外部用户 Bob（Principal Server 在 `server-beta.com`）时：

1. 管理员提交 `cx.invite.create` Event，`subject_did` 指向 Bob 的 DID
2. 该 Event 通过联邦推送到达 Bob 的 Principal Server
3. Bob 的客户端发现 Invite，决定接受
4. Bob 的客户端提交 `cx.invite.accept` Event 到自己的 Events API
5. Bob 的 Principal Server 将该 Event 推送给 Space S 的其他参与方 Principal Server
6. 各参与方按 reducer 验证 Invite 有效性并收敛成员状态
7. 若 Space 启用了 E2EE，管理员的客户端构造 MLS `Welcome` 消息发给 Bob

### 5.2 Knock / Restricted 跨域加入流程

Bob 也可以主动申请加入。具体流程取决于 Space 的 `cx.space.join_rule` 与 `cx.space.join_policy`（见 [`../governance/join-policy.md`](../governance/join-policy.md)）。

**自动解析路径**（`join_rule ∈ {restricted, knock_restricted}`，且 Bob 拟使用的 gate 子集均 `auto_resolve=true`）：

1. Bob 发现 Space S 的元数据（通过公开的 Space Directory、链接或 `directory_hint`）
2. Bob 直接提交 `cx.member.state{membership="join", gate_proofs=[...]}` Move，附带 claim presentation / challenge proof
3. Bob 的 Principal Server 推送至 Space S 的 shared anchorer 或参与方 Principal Server
4. 各参与方 reducer 加载当前 `cx.component.space.join_policy.v1` cell value，按 `combinator` 校验 `gate_proofs[]`；通过则收敛 `membership=join`
5. 若 Space 启用了 E2EE，Bob join 后由现有成员通过 MLS commit + welcome 引入

**申请-审核路径**（`join_rule ∈ {knock, knock_restricted}`，且至少一个 gate `auto_resolve=false`）：

1. Bob 发现 Space S 的元数据
2. Bob 提交 `cx.member.state{membership="knock"}` Move（不携带正文）以及 `cx.member.application` Move（携带 answers / claim presentation / challenge proof，E2EE Space 中 application 正文必须通过 reviewer sub-group MLS 或 envelope encryption 加密给 reviewer set）
3. 两条 Move 推送到 Space S 的 shared anchorer 或管理员 Principal Server；接收方验证签名后扇出至 reviewer 的设备列表
4. 持有 `cx.space.join.review` capability 的 reviewer 评估申请，提交 `cx.member.application.review{decision=accept|reject|request_changes}` Move；`reviewer_quorum != "any"` 时 reducer 收集足够 accept 后视为 accepted
5. 任一 reviewer 提交 `cx.invite.create`，`refs[role="join_authorised_by"]` 引用对应 review accept Move
6. Bob 提交 `cx.invite.accept`；reducer 校验 join_authorisation 链有效后收敛 `membership=join`
7. 若 Space 启用了 E2EE，inviter 客户端构造 MLS `Welcome` 消息发给 Bob

> 申请正文 MUST NOT 出现在公开可见的 `cx.member.state{knock}` payload 中（参见 [`../governance/join-policy.md` §7](../governance/join-policy.md)）；只能进入受加密保护的 `cx.member.application`。这避免 Matrix `m.room.member{knock}.reason` 因默认可见而成为外部 spam 通道的设计缺陷。

## 6. 联邦级服务发现

### 6.1 Anchorer / Sync Endpoint 列表

每个 Space 的 metadata MAY 包含一个 `sync_endpoints` 列表，用于列出被 Space policy 明确委托的 shared anchorer、sync service 或组织 Principal Server。该列表不是公开分发节点列表；列表中的每个 endpoint 都必须有 service DID、角色、可见性范围和是否可见明文的声明：

```json
{
  "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
  "sync_endpoints": [
    {
      "did": "did:web:server-alpha.com",
      "endpoint": "https://server-alpha.com/api/v1",
      "role": "primary",
      "service_type": "principal_server",
      "plaintext_visible": true
    },
    {
      "did": "did:web:server-beta.com",
      "endpoint": "https://server-beta.com/api/v1",
      "role": "mirror",
      "service_type": "principal_server",
      "plaintext_visible": false
    }
  ]
}
```

若 `plaintext_visible` 为 true，该 service DID 还 MUST 出现在 Space policy 的 `plaintext_visible_services` 中。若为 false，服务只能接收公开内容、密文 envelope、不可逆 hash 或 policy 允许的 stripped preview。

### 6.2 Actor Event Source 发现

给定一个 Actor 的 DID，其他节点通过解析 DID Document 中的 `#contrix-principal-server` 或等价服务端点来定位其 Events API：

```
DID Document -> service[type=ContrixPrincipalServer] -> serviceEndpoint
```

### 6.3 域名级服务发现缓存

DID Document 的 service entry 是联邦服务发现的权威来源。域名级 bootstrap MAY 暴露：

```text
GET https://<domain>/.well-known/contrix/server
```

该响应只用于找到候选服务 endpoint，不直接授权联邦请求。接收方仍 MUST 校验 service DID、DID Document、describe 响应、TLS 名称、HTTP Message Signature、Space policy / service delegation 和 `destination` 绑定一致。

缓存规则：

- 按 HTTP cache header 缓存服务发现响应。
- 未提供显式缓存时间时 MAY 使用不超过 24 小时的默认 TTL。
- 正缓存 SHOULD 设置本地上限（建议不超过 48 小时）。
- 失败缓存必须短 TTL 或指数退避，避免一次临时故障长期破坏跨域同步。
- service delegation 被撤销、DID Document key log 更新或 Space policy 变更时，本地缓存必须按版本 / hash 失效。

## 7. 联邦请求 vs 单域 client 请求

v1 联邦与单域 client 请求共享同一组 events / sync / identity 端点；区别仅在认证层（service signature + DID header vs user session / device proof）。本节给出对照速查表；wire 细节见 §4.1 / §4.2 与 [`service-http-binding.md`](./service-http-binding.md)。

| 联邦行为 | 复用端点 | 认证模式差异 |
| --- | --- | --- |
| 跨域推送 Event（含批处理） | `POST /api/v1/events`（`cx.events.submit`） | service_signature（HTTP Message Signature）+ `Source-Service-DID` / `Destination-Service-DID` header；Space policy 必须列出 source service DID 为合法 federation peer。 |
| 跨域 backfill / 拉取缺失历史 | `GET /api/v1/events?before=<cursor>`（`cx.events.query`） | 同上。 |
| 跨域 Space 成员视图 | `GET /api/v1/events`（`cx.events.query`） + `cx.member.state` 过滤 | 同上；服务端按 Space policy 决定哪些成员对该 service DID 可见。 |
| 跨域 actor / DID 验证 | `POST /api/v1/identity/resolve`（`cx.identity.resolve`） | 该端点本就是公共服务面；联邦请求按调用方信任策略缓存。 |

### 7.1 跨域 Event 推送

```
POST /api/v1/events
Authorization: <service_signature>
Source-Service-DID: did:web:server.acme.example
Destination-Service-DID: did:web:server.beta.example
Request-Canonical-Hash: sha256:...
```

字段、签名 transcript、绑定与重放保护按 §3.2、§4.1 与 [`api-conventions.md` §3](./api-conventions.md) 与 [`service-http-binding.md` §3](./service-http-binding.md) 执行。事件以普通 reducer-input event 提交（preconditions / effects / anchor_ref 在顶层），与单域 client write 共享同一 schema（`cx.schema.event.v1`）。

### 7.2 跨域 Backfill

```
GET /api/v1/events?spaces=<id>&before=<cursor>&limit=<n>
Authorization: <service_signature>
```

字段定义见 §4.2；service operation id 为 `cx.events.query`，`before=<cursor>` 用于回填历史（取 cursor 之前最近一批，默认 descending）。空间历史按 Space policy 与 history visibility 过滤；snapshot bootstrap 通过 `/api/v1/sync/snapshot-head` 单独获取。

### 7.3 查询 Space 成员

跨域参与方查询某 Space 成员视图时，使用 `cx.events.query` 并过滤 `kind=cx.member.state`：

```
GET /api/v1/events?spaces=<id>&kinds=cx.member.state&before=<cursor>&limit=<n>
Authorization: <service_signature>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `spaces` | query | `id[]` | required | 要查询成员的 Space。 |
| `kinds` | query | `string[]` | optional | 事件类型过滤；此处固定 `cx.member.state`。 |
| `from` | query | `cursor` | optional | 分页 cursor。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `members` | `object[]` | required | 成员摘要数组；内容受 requester 可见性和 Space policy 限制。 |
| `membership_frontier` | `object` | required | 用于判断成员视图新鲜度的因果前沿。 |
| `next_cursor` | `cursor` | optional | 下一页 cursor。 |

### 7.4 验证 Actor

跨域 actor 验证复用 `POST /api/v1/identity/resolve` 公共服务面（`cx.identity.resolve`）。该端点本就是公共 DID 解析入口，但 Contrix 实现 MUST 按调用方信任策略限速、缓存、并对私有 / pairwise DID 拒绝匿名公开。

下面保留的是 v1 之前定义的 `verify-actor` 单独端点的字段集——它现在是 `/api/v1/identity/resolve` 的高级 query 形态（"holder-approved proof challenge"），不是独立 operation。

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `actor_id` | body | `did` | required | 待验证 Actor DID。 |
| `purpose` | body | `enum(event_source,federation_join,device_binding)` | required | 验证目的；服务端 MUST 将目的纳入授权与限流策略。 |
| `space_id` | body | `id` | optional；Space 相关目的为 required | 相关 Space ID；用于绑定 Space policy、membership 和 plaintext visibility。 |
| `challenge` | body | `base64url string` | optional；challenge 验证为 required | 请求方生成的短期随机挑战；服务端 MUST 拒绝过期或重复 challenge。 |
| `signed_payload_hash` | body | `sha256:<base64url-or-hex>` | optional；验证具体事件/设备绑定时为 required | 被验证 payload 的 canonical hash，MUST 与签名 transcript 绑定。 |
| `signature` | body | `object` | required | Actor 设备键或授权签名。 |
| `signature.kid` | body | `did-url` | required | 签名键 ID，MUST 属于 `actor_id` 的当前或可验证历史 key log。 |
| `signature.alg` | body | `string` | optional | 签名算法；出现时 MUST 与 DID Document/key log 中的 key 类型一致。 |
| `signature.sig` | body | `base64url string` | required | 对 canonical verification payload 的 detached signature。 |

`signature.sig` 覆盖的 canonical verification payload MUST 至少绑定 `actor_id`、`purpose`、`space_id`（若存在）、`challenge`（若存在）、`signed_payload_hash`（若存在）、请求方 service DID、目标 service DID 和请求时间窗口，防止跨目的、跨 Space 或跨服务重放。

请求示例（非完整 schema）：

```json
{
  "actor_id": "did:webvh:...",
  "purpose": "event_source",
  "space_id": "cx:space:...",
  "challenge": "base64url...",
  "signed_payload_hash": "sha256:...",
  "signature": {
    "kid": "did:webvh:...#device-a",
    "alg": "Ed25519",
    "sig": "base64url..."
  }
}
```

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `valid` | `boolean` | required | 是否完成签名、DID/key-log 和目的约束校验；不得表示最终授权。 |
| `actor_id` | `did` | required | 回显被验证 Actor DID，MUST 与请求一致。 |
| `verified_key_id` | `did-url` | `valid=true` 时 required | 实际通过校验的 key id。 |
| `key_log_head` | `id` | optional | 服务端用于校验的 key-log head；接收方可据此刷新本地缓存。 |
| `did_document_ref` | `sha256:<hash>` | optional | DID Document canonical hash 或等价引用。 |
| `expires_at` | `datetime` | `valid=true` 时 required | 该辅助验证结果的最晚缓存时间；不得长于本地策略 TTL。 |
| `warnings` | `string[]` | required | 非致命提示；无提示时为空数组。 |

响应示例（非完整 schema）：

```json
{
  "valid": true,
  "actor_id": "did:webvh:...",
  "verified_key_id": "did:webvh:...#device-a",
  "key_log_head": "cx:keyevt:...",
  "did_document_ref": "sha256:...",
  "expires_at": "2026-04-26T00:05:00Z",
  "warnings": []
}
```

访问限制：

- 请求 MUST 使用来源 service DID 的 HTTP Message Signature。
- `purpose` MUST 是 `event_source`、`federation_join`、`device_binding` 或 Space policy 明确允许的等价目的。
- 请求方 MUST 是该 Space 的参与方 Principal Server、被委托 anchorer / sync service，或拥有相关 federation / join 处理权限的服务。
- 服务端 MUST 限流，并对不可见 actor 返回统一 `not_found` / `capability_denied` 语义，避免批量枚举 DID。
- 响应只能作为缓存加速或诊断。接收方在接受事件、成员变更或设备绑定前，仍 MUST 独立验证 DID Document、key log、签名 transcript、capability 和 Space policy。

## 8. 安全考量

### 8.1 反洪泛 (Anti-Flooding)

联邦端点 MUST 实施严格的速率限制。恶意节点可能通过大量推送无效 Event 来消耗对端资源。建议：
- 按 `origin` DID、来源 IP hash、endpoint 和 Space id 做独立限速
- 对来自未知域的首次请求做降级处理（先验证后全速）
- 限制单次请求体积和批次大小，超阈值先进入 `rate_limited`
- 先执行低成本 envelope / size / signature transcript 校验，再进入昂贵的 DID resolution、auth chain 展开和 reducer 预演
- 对连续失败来源使用有界队列和 `Retry-After`，不得让失败请求触发无限 backfill 或 retry fanout

### 8.2 选择性拒绝

节点有权选择性拒绝来自特定域的联邦请求（参见 3.3 节的域信任模型），这不违反协议。被拒绝的域可以通过其他途径（如用户直接下载可见 Event 历史）获取信息。

### 8.3 元数据与身份校验

联邦请求在鉴权前应执行签名与服务源一致性检查：

- `origin`/`destination` service DID 必须与请求签名与 `target-uri` 一致；
- 对签名失败、签名域缺失、`origin` 不在可接受集合的来源进入 `quarantine` 或 `hard_deny`；
- 未通过身份校验的错误响应 MUST 不泄露可验证/不可验证来源的差异。

### 8.4 元数据泄露防护

在联邦推送 E2EE Space 的 Event 时，密文信封 `encrypted_payload` 对联邦中间节点同样不可见。联邦协议传输的只有明文路由元数据和不透明的密文块。

### 8.5 重放与异常模式防护

节点 MUST 将 `Idempotency-Key` 与请求 canonical hash 绑定后执行幂等和重放检查：

- 相同 `(origin, destination, Idempotency-Key)` 但 canonical hash 不同 MUST 拒绝；
- 相同 `(origin, destination, Idempotency-Key)` 且 canonical hash 相同 MAY 幂等接受；
- 单事件级别仍以 `event_id` 去重，规则见 4.3 节；
- 同源短时重复失败、失败率异常上升时 MUST 暂停该源并返回 `rate_limited`/`temporarily_unavailable`。

### 8.6 威胁映射落地

本协议在服务器端应默认支持 [server-threat-model.md](../security/server-threat-model.md) 中“可借鉴项”，特别是：

- 开放联邦入口阻断；
- 攻击来源限流与排队；
- 重放检测与 quarantine；
- 统一回执和拒绝语义避免枚举泄漏。

## 9. 未来实现边界与优化优先级

这类方向并非都属于第一版互操作要求。按“安全完整性 → 可交付性 → 优化性”分层如下。

### 9.1 联邦级 Snapshot 同步与校验（必须项）

联邦场景下，Principal Server 之间应支持基于快照的快速恢复（snapshot-assisted bootstrap），否则首次加入或大范围缺失时会退化为全量历史回放，影响可用性。实现层面：

在 `GET /api/v1/events?before=<cursor>`（`cx.events.query` 联邦 pull 形态）响应中，服务端 SHOULD 在可用时提供 `snapshot_bootstrap`（可选字段）：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `snapshot_bootstrap` | `object` | optional | 可选，携带可验证的快照入口，不改变操作集合语义。 |
| `snapshot_bootstrap.snapshot_ref` | `id` | optional | 触发本次增量前可选的 snapshot id。 |
| `snapshot_bootstrap.state_hash` | `string` | optional | snapshot 的状态摘要。 |
| `snapshot_bootstrap.snapshot_frontier` | `id[]` | optional | snapshot 覆盖的 frontier。 |
| `snapshot_bootstrap.signature` | `object` | optional | 标准 Snapshot detached proof；接收方必须验证签名、state_hash 与 `snapshot_frontier` 一致性。 |

校验规则：

- 客户端在接收到 `snapshot_bootstrap` 时，先执行 `signature`、签名者授权、`state_hash` 和 chunk digest 校验。
- 接受快照后，增量回放起点必须以 `snapshot_frontier` 为锚点，不得把 snapshot 当成无因果前沿的新 genesis。
- 快照校验失败时，必须退回到纯 Event 增量回放，并将该来源记入 `quarantine` 或 `rate_limited` 分支进行观察。

### 9.2 多 Principal Server 的 Gossip / 批量同步（增强项）

该方向用于性能和可靠性提升，不是签名真实性的前提条件。最小实现可直接使用本文件 4/7 节的 push + pull。实现支持时应遵循：

- 批次内必须保持 `events` 的原始签名 Envelope 顺序与 `event_id` 可去重性。
- Gossip 转发不得改变单条 Event 的语义、签名或时间线排序前置假设。
- 不得以批处理成功作为 Event 被最终可验证的充要条件；最终仍以 `event_id`、签名、因果前沿验证判定是否可见。
- 每个 batch 应带可核验的批次摘要（例如请求级 hash）以便对端做重试/重放检测。
- 若实现启用多跳 gossip 而不是直接 push / pull，每个 federation transaction MUST 携带由 service-to-service 签名覆盖的 transport-level path metadata，例如 `relay_path`、`hop_count` 和 `max_hops`。接收方发现自己的 service DID 已在路径中、`origin`/`destination` 与签名 transcript 不一致，或超过 `max_hops` 时，MUST reject 或 quarantine。path metadata 不能替代单条 Event 的 Actor 签名，也不是 Actor canonical event 的一部分。
- 转发方 MUST 在 fanout 前按 `event_id` 与 canonical event hash 去重。实现 SHOULD 维护有界的 `(space_id, event_id, peer_service_did)` replay cache，并对 `origin`、Space 和 peer 维度设置 in-flight 上限。队列超过本地策略时返回 `rate_limited` 或 `temporarily_unavailable` 并带 `Retry-After`，不得制造无界重试风暴。

### 9.3 跨域权限委托与级联（明确边界项）

方向“跨域 Space 的权限委托与级联”是必要但必须收敛到显式规则：

- 默认不跨域、不中继地隐式级联。任何权限在跨域传递前都必须有明确 `cx.capability.grant` / `cx.capability.delegate` Event 表达，并绑定目标 `space_id`、目标服务/主体、可见范围、时效和可撤销性。
- 受权链必须可审计、可传递上限（如 depth / scope）并支持回收（revoke）。在未满足上限或超出范围时应 fail-closed。
- 委托不得扩大被委托方可见范围；只能收窄或保持不变。`principal_server` 不能仅凭受托委托获得不在其角色定义内的明文访问。
- 对级联场景，只允许显式 opt-in，且每一跳必须重复检查 policy 与签名。无法验明权利链的来源时必须视为 unauthorized。

### 9.4 联邦节点声誉系统（可选项）

声誉系统可作为 anti-abuse 组件是可选的，不得影响协议的最终一致性安全边界：

- 声誉只能用于流量调度、排队优先级和临时降级，不得替代签名验证、DID 校验和 Space policy 授权判断。
- 声誉决策不得造成可审计事件的不可达性（例如把合法请求静默降权为拒绝）。
- 即使在高声誉策略触发下，仍应返回可区分的标准错误码（`temporarily_unavailable`、`rate_limited`、`quarantine`）供重试/恢复。

### 9.5 跨 deployment Watcher 投递 SLA（`cx.profile.agent_workspace.v1`）

`cx.profile.agent_workspace.v1`（详见 [`extensions/agent-workspace-profile.md`](../extensions/agent-workspace-profile.md)）依赖客户端 / agent-runtime watcher 观察源 Space 的 `cx.redaction(target=mention_redirect)` / `cx.capability.revoke` / `cx.member.state(removed)` 事件，再在镜像 Space 写 transparency / source_authority transition。这是"observe-then-write"模式：mirror reducer 不消费源 Space 事件。

当源 Space 与 mirror Space 跨 deployment 部署时（典型：源 Space 在组织 deployment A，controller 的 workspace root 在 deployment B），watcher 的可靠投递依赖 federation 通道。本节给出 SLA 边界：

**投递时延**：
- watcher 在源 Space sync frontier 推进后 SHOULD 在 `federation_sync_interval + 30s` 内观察到触发事件并写出 transition
- 默认 `federation_sync_interval=60s`；高频部署 MAY 设为 `15s`，最大不超过 `300s`

**冗余 watcher**：
- 同一 mirror Space MAY 有多个并发 watcher（controller 的多个 client + agent runtime + sync node housekeeping）；FSM `from` precondition 保证只有第一个 transition 成功，后续 idempotent no-op
- 跨 deployment 多 watcher MUST 用同一套 `evidence_refs` schema（事件 ID + 可独立验证的 anchor inclusion proof）

**Tombstone 兜底**：
- 若 watcher 长时间不可达（`watcher_silence_window`，默认 `24h`），mirror Space 的 sync node housekeeping MAY 写 `cx.agent_task.execution.transition(to=cancelled_orphan, reason=ttl_expired)` 以避免任务永久卡死
- Housekeeping Move 携带 anchor-based ttl_evidence（见 [`agent-workspace-profile.md §6.4`](../extensions/agent-workspace-profile.md)）

**未投递的合规含义**：
- 当源 Space 的撤销事件因联邦不可达而未及时投递到 mirror，controller 仍可能基于过期上下文继续指挥 agent。这是设计上承认的失效模式（agent runtime gate 是 best-effort 透明度保证，不是密码学强制）
- 合规部署 MAY 在源端要求 sync ack-back（federation `push-anchors` 收到 mirror ack 后才允许 agent 继续工作），但这会显著增加时延且超出本 profile v1 范围
