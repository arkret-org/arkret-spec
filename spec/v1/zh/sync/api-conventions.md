---
title: HTTP/JSON Binding 通用约定
status: candidate
normative: true
stability: v1
updated: 2026-09-20
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 默认 HTTP/JSON binding 的线级约定。
Arkret 协议核心不强绑定 REST API；核心操作、消息 envelope 与 transport binding 的关系见 `transport-bindings.md`。

各服务面可以扩展自己的 HTTP endpoint，但 MUST 遵守本文的基础规则，除非对应文档明确说明例外。非 HTTP binding（例如 gRPC、WebSocket、SSE、libp2p、message queue）MUST 提供语义等价的认证、授权、幂等、分页、错误和流控语义。

本文作为默认 HTTP binding 适用于：

- identity registry
- events
- Station sync surface
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

Arkret canonical JSON 字段名 MUST 使用小写字母与下划线连接，例如：

- `realm_id`
- `event_id`
- `service_endpoint`
- `verification_method`
- `retry_after_ms`
- `reconnect_after_ms`

Raw 外部标准文档 MUST 保留外部标准字段名，例如 W3C DID Core 的 `verificationMethod` / `alsoKnownAs` / `serviceEndpoint` 和 VC 的 `credentialSubject`。Arkret normalized view、索引、policy input 和 reducer input MAY 使用 snake_case 派生字段，但这些派生字段不得作为 raw DID / VC 文档重新输出。

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

注意：OpenAPI `content:` map 与 HTTP `Content-Type` 只表示 media type / body 编码，不是 Arkret Content Block 字段。协议正文内容仍按对象或 Event payload schema 使用 `content` / `encrypted_content`。

### 2.3.1 Content-Encoding 与 pre-parse 大小边界（normative）

所有在 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 标注 `body_class=non_streaming_json` 的 operation：

- request 与 response 的 `Content-Encoding` **MUST be absent**。服务端 MUST 在读取或解压 body 之前以 HTTP 415、`error_code=unsupported_content_encoding` 拒绝携带该 header 的请求；MUST NOT 复用 `param_invalid`（它固定映射 400）。cache / proxy MUST 设置适当 `no-transform`，MUST NOT 在中途压缩 response。
- 三层大小边界（完整 canonical Event 1 MiB、canonical operation body 8 MiB、HTTP message content wire bytes 16 MiB）、二维 count+bytes batch/page 算法与统一 `payload_too_large` 语义的唯一真源是 [`../conformance/scalability-constraints.md` §2.1](../conformance/scalability-constraints.md)。
- 请求处理 MUST 按 scalability-constraints §2.1.8 的顺序执行：header 边界 → 不需 body 的认证 → 拒绝 `Content-Encoding` → `Content-Length` 预检 → 边读边计 wire bytes → JSON parse → JCS 计数 → schema/operation 校验 → body-dependent proof/auth → handler。实现 MUST NOT 先完整缓存或解析 body 再判大小。
- streaming binding（NDJSON / SSE、Blob upload/download、Range、media transport、federation streaming）不套用 8 / 16 MiB 整体 body 上限，各自按 scalability-constraints §2.1.7 定义 per-frame / per-chunk / pending 上限。

### 2.4 Operation ID kind/action taxonomy

标准 `operation_id` 是跨 transport 的语义操作名，不是 HTTP method 的派生名。Operation ID MUST 使用可变长度前缀加固定末两段：

```text
ak.<surface>.<domain-or-subject...>.<kind>.<action>.v1
```

`<kind>` MUST 取下表固定集合。`<action>` 是该 kind 内的业务动作，MUST 描述协议效果，不得为表达 transport binding 而采用只描述传输、不描述协议效果的纯 HTTP method 名称 `post` / `put` / `patch`。`get` / `delete` 作为 `resource` kind 下的 canonical action，描述的是读取 / 删除这一**协议效果**（其 HTTP method 由 `kind` 钉死，见下表），不在此限。

| kind | 语义边界 | HTTP/JSON binding 关系 |
| --- | --- | --- |
| `read` | 安全、幂等的只读计算：扫描、批量解析、checkpoint/head 投影、proof materialization。不得产生 server-side mutation。 | 简单 selector 可使用 `GET`，typed request content 优先使用 RFC 10008 `QUERY`，需要隐藏 selector 或承载复杂 body 时可使用 `POST`；唯一 binding 由 operation registry 固定。 |
| `stream` | 长连接、live tail、增量同步或 bounded catch-up stream。 | 通常 `GET`；响应可以是 NDJSON、SSE、WebSocket frame 或等价 stream。 |
| `resource` | URI 明确标识一个资源、binding 或 slot；请求语义围绕该 URI 的当前表示。 | `resource.get` 使用 `GET`/`HEAD`；`resource.replace` 使用 `PUT`；`resource.delete` 使用 `DELETE`。 |
| `command` | 触发协议动作、状态推进、发布、入队、fanout、ack、领取、消费、授权、撤销、注册或流程推进。 | 通常 `POST`。命令可通过 idempotency key、对象 id、序列号或签名 transcript 实现幂等，但不因此变成 `PUT`。 |
| `upload` | 上传 blob、KeyPackage、密钥材料或可续传 artifact。 | 通常 `POST`；若某 binding 定义客户端指定对象 URI 的完整内容替换，才可单独使用 `PUT`。 |
| `exchange` | token、OIDC callback、媒体凭证、MIMI key material 等握手或跨系统交换。 | 通常 `POST`，并由请求体或 HTTP Message Signature 绑定 proof / audience / digest。 |

下列 action 语义是规范性约束：

- `resource.replace` 表示请求体是目标 URI 当前表示或 slot 值的完整替换；HTTP/JSON binding MUST 使用 `PUT`。
- `command.publish` 表示发布调用方签名的 policy / identity state / 权威文档，由服务端按签名、版本和 `supersedes` 链验证后接受；除非目标 URI 本身就是可完整替换的 slot，否则 MUST 使用 `POST`。
- `command.send` / `command.notify` 表示投递、入队或 fanout；即使有幂等键，也不是 `resource.replace`。
- `command.ack` 表示对已投递数据做显式确认；天然幂等，但不得被 cursor 推进隐式替代。
HTTP method 不是 operation action 的来源。以 `ak.self.events.read.scan.v1` 为例，其 HTTP binding 唯一为 `POST /_arkret/self/streams/scan`（`/_arkret/self/events` 是 `ak.self.events.command.submit` 的 binding，不是 scan 的），OpenAPI Operation Object 使用稳定、无版本的 endpoint identity `ak.self.events.read.scan` 作为 `operationId`。实现不得为同一 operation 暴露未登记的 GET / POST 别名；gRPC / MQ 同样只暴露 registry 中的 canonical operation contract。

### 2.4.1 HTTP operation selector（normative）

OpenAPI `operationId` 标识稳定的 HTTP endpoint family，不是带版本的 `operation_id`：其值 MUST 等于 canonical
`operation_id` 去掉末尾 `.vN` 后的 endpoint identity。同一 method/path 的多个 `operation_id` 版本共享同一个
OpenAPI Operation Object 和同一个无版本 `operationId`。

每个 canonical Arkret HTTP 请求 MUST 在接收方读取或解析 body 之前携带**恰好一个**
`Arkret-Operation` header，值为 exact versioned `operation_id`。接收方 MUST 从当前 method/path route
family、已验证的服务能力交集与 binding kind 计算可接受候选集，并验证 selector 属于该候选集。

1. header 缺失时返回 HTTP 400 / `operation_selector_required`；endpoint 当前只有一个版本也不得隐式补全；
2. header 重复、值未注册、服务未支持该 exact 版本，或该 id 不属于当前 method/path route family，返回
   HTTP 422 / `unsupported_operation_version`；
3. 候选集为空时返回 `unsupported_operation_version`，不得回退到相邻版本或未广告 `operation_id`；
4. 不得按 endpoint 唯一性、body shape、字段相似度、无版本别名、客户端 SDK 版本或失败回退猜测版本。

强制 selector 保证同一 endpoint family 新增版本时，旧客户端仍继续明确选择原版本，不会因服务端候选集
变化而突然失败或被静默切换。成功响应 MUST 以 `Arkret-Operation` response header 回显最终选中的 exact
versioned id。需要 RFC 9421 HTTP Message Signature 时，签名基串 MUST 覆盖该 header；授权、幂等和审计
MUST 使用 exact `operation_id`，不能把无版本 OpenAPI `operationId` 当作带版本的协议 operation。

### 2.4.2 写操作的 durable Event authorship 闭包（normative）

每个带 `idempotency_mechanism` 的写 operation 都 MUST 在 canonical
`contract-registry.json` 的 operation 行声明一个 `durable_effect`，且只可使用：

- `event_log`：显式列出非 actor-private 的 active `event_kinds[]`；若请求本身承载任意
  Event，则改用 `event_kind_source="$request.<path>"`。当请求 schema 是多个合法 shape 的
  union、Event 在不同分支使用不同路径时，使用非空 `event_kind_sources[]` 列出每个分支
  的路径；receiver 只对实际命中的 schema 分支解析对应路径并取 kind。每条路径都必须
  能在 `request_schema_ref` 的至少一个合法分支中解析；
- `actor_private_event`：显式登记唯一 active actor-private `event_kind`；
- `none`：必须给出稳定、具体的 `rationale`，说明结果只改变 service-local material、
  identity log、队列、外部系统，或仅返回待签/待提交材料，不产生 Arkret durable Event。

一个 operation 不得同时声明静态 kind 与任一种动态 source，也不得同时声明
`event_kind_source` 与 `event_kind_sources`，不得把 actor-private kind 填进
`event_log`。HTTP / gRPC / MQ adapter 必须实现同一 mapping；成功响应不能绕过该声明产生
未登记 durable Event。该闭包由 `tools/artifact_lint` 与
`operation-registry-coverage-fixture.json` 机械校验。

**leaf effect 的成员集合是封闭的（normative）**：上述三种 `kind` 各自的成员集合逐字封闭，
未登记的 key MUST 使整条 registry 行失败。`branched` 是**组合节点**而不是 leaf effect：
顶层 `branched` object 只允许 `kind`、`discriminator` 与 `effect_branches`，
每个 `effect_branches[].effect` 递归使用同一套 leaf 定义。

**`cross_service_effects` / `irreversibility_note`（normative）**：这是 leaf effect 上与 `kind`
**正交**的一对 optional 成员。

- `kind` 只描述本 operation 在当前 Arkret 服务内**是否/如何 author durable Event**；
  `cross_service_effects` 描述同一 operation **越过本地事务边界后可能已经提交的外部持久副作用**。
  两者正交：`kind:"none"` 的 operation 同样可以有外部 durable effect
  （例：`ak.peer.account_status.command.submit.v1` 不 author Event，但 `erasure_pending` 分支要求
  接收端先落 durable 物理擦除意图才能 ack）。因此 MUST NOT 把这对成员绑死在 `event_log` 上。

本字段不描述、也不声称闭合服务内部的数据库表、事务拆分、outbox/queue 结构、single-use claim
ledger、缓存或补偿实现。上述内部实现只有在其可观察的 retry、幂等、ACK barrier、失败恢复或
响应语义形成跨实现互操作要求时，才必须通过该 operation 的 request/response schema、
`idempotency_mechanism`、`retry_safe`、reason code 与正文合同表达；不得为记录某个实现的内部 UoW
而扩展 `durable_effect` kind。因而审计与工具输出只能称其为 **durable Event authorship mapping**，
不得简称为覆盖一切持久副作用的 durable-effect 合同。
- 两个成员 MUST **同时出现或同时缺席**。出现时 `cross_service_effects` MUST 非空、逐字去重，
  每项是 operation-local 的稳定 slug；`irreversibility_note` MUST 非空。
- **presence 就是那条机器信号**：这对成员出现即表示该 operation 可能产生**不可安全盲重试**的持久效果。
  消费者 MUST 只按 pair 的 presence 判定，MUST NOT 从未注册 slug 推导任何额外协议行为
  （补偿策略、重试类别、副作用分类）。slug 是诊断 / 审计标签，不是封闭枚举；
  两个现有样本不足以支撑枚举语义。若将来确实需要按 effect kind 自动选择补偿策略，
  MUST 另建 registered effect-kind registry 与 typed retry class 并同批迁移现有行，
  MUST NOT 把自由 slug 偷偷当枚举使用。
- 这对成员 MUST 放在实际发生副作用的 leaf effect 上（含 `effect_branches[].effect`），
  顶层 `branched` object MUST NOT 携带它们——否则一个分支的不可逆性会被错误推广到全部请求。

**`viewer` action（术语定义）**：`ak.self.account.read.viewer.v1` 的含义钉死为：**当前已认证 holder 的主体自读投影**。目标不由 path / query 中的外部 id 定位，而由 holder-bound `user_session` 的会话绑定决定，故不建模为 `resource.get`；命名沿用 GraphQL 生态的 `viewer` 惯例（"viewer = 发起请求的已认证主体"）。它与 `query.describe`（服务能力元数据，可 pre-auth）的区分见 [`service-http-binding.md` §5.1](./service-http-binding.md)。注意区分本规范 prose 中 `viewer` 的另一用法：可见性 / 投影语境（pins、history visibility、conformance vector 的 `viewer_*` 字段）里的 "viewer" 指**正在读取内容、作为可见性评估视角的主体**，不是本 operation；`reviewer`（审核者）与两者均无关，全文检索 `viewer` 时勿混入。

### 2.5 HTTP method 语义

HTTP method 选择 MUST 服从资源语义，而不是简单照搬 `operation_id` 的最后一个词：

- `GET` / `HEAD`：只读、无 server-side mutation；可用 path/query 定位资源、projection 或分页读取位置。读取 cursor 不得触发队列删除或 ack。
- `POST`：提交 command、batch、proof、搜索/复杂查询 body、入队、fanout、创建服务端分配 id 的资源，或执行由签名/admission 决定效果的操作。每个写 operation MUST 在 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 声明 `idempotency_mechanism` / `retry_safe`；可自动重试的写入必须使用 `Idempotency-Key`、对象 id、request id、canonical hash 或 protocol sequence。确实无法提供稳定 identity 的 operation 只能声明 `none/false`，并 MUST 同时声明 §6 的机读 `uncertain_outcome`，不得让客户端猜测恢复路径。
- `PUT`：仅用于“客户端对一个已知 URI 表达完整目标表示或当前 slot 值”的创建/替换/设置。重复发送同一 URI 和同一表示 MUST 不产生额外副作用；同一 URI 上不同表示按该 slot 的覆盖、版本或 precondition 规则处理。
- `DELETE`：删除一个已知 URI 表示的资源、binding 或 slot；重复删除必须有定义良好的幂等结果。
- `PATCH`：仅在规范显式定义 patch document 语义、冲突检测和幂等边界时使用；否则 partial update 使用 `POST` command 或 `PUT` slot replacement。

因此，`ak.self.device_messages.command.send.v1` 表示“把 to-device message 批次放入目标设备短期队列”，HTTP binding 必须是 `POST /_arkret/self/device_messages`，并以 `(sender, Idempotency-Key)` 去重：该操作没有单个由 URI 标识、可完整替换的消息资源；队列删除只由 `ak.self.device_messages.command.ack.v1` 触发。相反，`ak.self.keys.backups.resource.replace.v1`、`ak.self.account_data.resource.replace.v1` 和 `ak.self.agent.participation.resource.replace.v1` 都有 path 标识的单一 backup/config/slot，HTTP binding MUST 使用 `PUT`。

## 3. 认证

受保护 endpoint 的请求 MUST 携带可验证且 sender-constrained 的认证材料。`ak.session.grant` 是 RFC 9449 DPoP-bound token，current-v1 的唯一 HTTP Authorization scheme 固定为 `DPoP`；`Bearer` 不属于该 credential 的合法出示形态，即使请求同时携带 `DPoP` proof header 也 MUST 拒绝。高安全 profile 可在此基础上叠加 RFC 9421 HTTP Message Signature，但不得改回或协商其它 SessionGrant scheme。

1. **默认会话出示**：`Authorization: DPoP <ak.session.grant>` 加匹配 RFC 9449 DPoP proof；认证、JKT、audience、method/URI、时间与重放检查全部执行。
2. **高安全追加层**：仅在已登记高安全 profile 中追加 RFC 9421 HTTP Message Signature 绑定 transcript/body；它不替代 DPoP，也不是第二种默认会话 scheme。detached JWS 不作为 SessionGrant fallback；其它独立登记的业务 proof 保持原合同。

无论采用哪种传输认证方式，协议层权限判断最终 MUST 回到：

- actor DID
- device / session / agent delegation
- capability grant
- Realm policy
- verified claim / attestation

服务端 MUST NOT 仅因 bearer token 存在就跳过 capability 检查。

认证材料 MUST 放在 header、HTTP Message Signature、mTLS 握手或明确的 signed proof body 中。服务端 MUST NOT 接受 query string、path segment 或 fragment 中的 session credential、API key、签名密钥、长期 capability 或等价长期认证材料。

规则：

- 带有 `access_token`、`session_credential`、`api_key`、`auth`、`signature` 等 query 参数的受保护 endpoint 请求 MUST 被拒绝，除非对应 endpoint 明确把该字段定义为非认证业务参数。
- 拒绝时 SHOULD 返回 `unauthenticated` 或 `param_invalid`，并且不得把 query 中的敏感值写入普通访问日志。
- `ak.self.blob.command.presign.v1` 是唯一标准 URL bearer 例外：它只能是单 blob、单用途、短时效、只读、可撤销的派生 token，不得等同于用户 session、API key 或长期 capability；完整约束见 [`../crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。
- 第三方邀请的 `#token=` fragment 是客户端 handoff，不是服务端认证入口。服务端不会收到 fragment；客户端读取后 MUST 通过 body / signed proof 提交 claim，并按 [`third-party-invites.md` §3.2](./third-party-invites.md) 清理 URL 与本地状态。
- online principal locator 的 `#token=` fragment 同样只是客户端 handoff。`locator_token` MUST 通过 `POST /_arkret/open/invite-locators/resolve` JSON body 提交；不得出现在 URL path 或 query string。详见 [`invite-addressing.md`](./invite-addressing.md)。

### 3.1 认证服务发现

认证与授权服务器可以分离。普通客户端 MUST 先按 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative) 建立或核对持久 Station/认证绑定，再发送账号凭据；独立 origin 的 Authority 不改变该要求。Station 的 `/_arkret/describe` MUST 公布 `auth_metadata.account_authority` 与 `auth_metadata.methods[]`。客户端先用 `account_authority.gate_account_base_url` 定位所有客户端可见的 Arkret `/_arkret/gate/account/*` 操作，再按 `methods[]` 中的标准 discovery 找认证 provider；规范明确标记为部署内部 S2S 的 account 子操作（例如 `ak.gate.account.command.logout_auth_session.v1`）只能由 Account Authority 按对应契约调用，不能由客户端派生。不得把 OAuth/OIDC subject 当作 Arkret principal：

```json fragment
{
  "auth_metadata": {
    "account_authority": {
      "origin": "https://account.example",
      "gate_account_base_url": "https://account.example/_arkret/gate/account"
    },
    "methods": [
      {
        "method": "oidc",
        "issuer": "https://auth.example.com",
        "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
        "client_id": "ak.example-client",
        "scopes": ["openid", "profile"],
        "grant_exchange": {"kind": "account_handoff"}
      },
      {
        "method": "passkey",
        "grant_exchange": {"kind": "account_handoff"}
      }
    ],
    "did_binding_methods": ["session_dpop", "session_http_signature"]
  }
}
```
规则：

- `sub`、email、username 或 OAuth client id MUST NOT 直接作为 `actor_id`、grant subject 或 event sender。
- 登录成功后，Account Authority MUST 产生可验证的 `SessionGrantOutcome`，把 OAuth/OIDC / passkey / device proof 绑定到 DID principal / device。客户端可见登录凭据是 `ak.session.grant`，Principal 本地 session provisioning 是 Account Authority 内部步骤。该 credential 的 durable authority 是 Account Authority 的 issuer ledger，不是 Principal Control Realm Event/typed current result；issuer MUST NOT 为 SessionGrant 代签 principal Event。
- Resource server MUST 按 §3.3 的 exact-token 内省权威合同判定 `ak.session.grant`：在预先绑定的部署内认证通道（[`service-http-binding.md` §2.2.3](./service-http-binding.md)）上提交**完整 token** 与目标 `audience_id`，由 Account Authority 从 issuer ledger 定位该 exact credential、判定状态并返回本次准入所需的全部权威元数据。该权威结果就是 resource server 对这枚 token 的唯一状态来源：resource server MUST NOT 把本地 JWT 验签、issuer DID 历史回放或从 signed claims 重算 issuance preimage / suite-tagged ID / `jti` 当作该 token 的授权依据，本地验签结果 MUST NOT 产生独立的 active 判定。resource server 仍 MUST 校验返回结果的 `issuer_id`、`audience_id`、完整 `account_id`、`credential_class`、`scopes`、`expires_at`、holder 绑定与本次业务 gate，并在依赖不可达或响应不完整时按 §3.3 fail closed。
- 客户端 MUST 把 `ak.session.grant` 当作不透明凭据：不解析其 claim、不依据本地解码结果判断有效性，也不据此跳过任何服务端判定。
- `methods[]` 只描述 service account 登录或恢复入口；它不改变 DID 控制权规则。密码、邮箱验证码、passkey 和 OIDC session 必须通过 `did_binding_methods` 绑定到 DID / device 后才能用于协议写入。
- Account-first registration 的首设备 authority 来自 identity-root control transcript 与 founding device proof；service discovery 不发布设备 authority pin。Account Authority 只能 relay exact signed genesis unit并验证 receipt。
- 当认证 metadata 变化时，服务 SHOULD 通过 feature discovery 版本或 DID service metadata hash 暴露变更；客户端 MUST 使相关发现缓存失效并按 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative) 比较持久绑定，不得静默沿用过期 issuer，也不得把已有凭据直接转交新 issuer/Authority。

### 3.2 Sender-constrained（proof-of-possession）会话出示

`ak.session.grant` 已把短期 `session_public_key` / `cnf.jkt` 绑定到 principal / device / audience（见 [`../crypto-media/device-lifecycle.md` §1 / §3](../crypto-media/device-lifecycle.md)）。按 RFC 9449 §7.1，DPoP-bound token 必须用 `Authorization: DPoP` 出示；把同一 token 放入 `Bearer` scheme 会绕开 token-type signal，不能因旁边另有 proof header 而合法化。

客户端用 grant-binding key 签 DPoP / request proof；Account Authority 用 issuer key 签 JWT 与
introspection/status。这两个签名域 MUST 分离：DPoP 证明当前 holder 持有会话 key，不签发 grant；issuer
签名证明自己的授权决定，不证明 principal/device 已签某个 Event，也不替代 governance Station 的 RealmCommit。S2S HTTP Message Signature
只认证 transport source/destination/body，MUST NOT 替代任一内层 proof。

**生产 current-v1 PoP 要求（normative）**：

- `/_arkret/self/*` 以及 Account Authority 的 refresh、revoke、logout 等直接出示 SessionGrant 的 endpoint MUST 使用 §3.3 的 `Authorization: DPoP <ak.session.grant>` + `DPoP` proof header；`Bearer` + DPoP、DPoP scheme 无 proof、错误 `ath` 均 MUST 拒绝。
- 高安全 profile 对所有受保护的 `ak.self.*` operation MUST 要求 RFC 9421 HTTP Message Signature 会话出示并绑定 transcript/body。`ak.self.` 前缀是机器可判定的默认保护面；同一 operation 若在 registry 明确列为匿名 public metadata projection，无有效 proof 时只能返回该公开 projection，MUST NOT 把 bare bearer 当作 session / capability 认证。新增或未知 `ak.self.*` operation 默认 fail closed，除非 operation registry 与其规范性 contract 同时明确声明匿名 public projection。
- 对其它受保护 current-v1 endpoint，实现仍 MUST 使用其合同指定的 sender-constrained proof；只要 credential 是 `ak.session.grant`，Authorization scheme 仍固定为 `DPoP`。
- 服务 SHOULD 通过 `auth_metadata.did_binding_methods` 公布支持的 sender-constrained 方法（如 `session_dpop`、`session_http_signature`），其中 session_dpop 表示唯一默认层，session_http_signature 表示可追加的高安全层，不能作为可互换选择；未公布任何 sender-constrained 方法的服务 MUST NOT 声明通过 current-v1 production protected-endpoint conformance。
- 在 §11.2 之外，PoP 出示不改变 §3 其余规则：协议层权限判断仍 MUST 回到 actor DID / capability / Realm policy；PoP 只把"持有 token"升级为"持有绑定密钥"。

**PoP 出示形态（RFC 9421）**：客户端用 `session_public_key` 对应私钥对请求签名。本场景是
[`service-http-binding.md` §8](./service-http-binding.md) 的
`ak.http_signature.scenario.client_session_pop.v1`，适用的必需覆盖项：

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.client_session_pop.v1 -->
- `@method`、`@target-uri`、`@authority`（绑定动词、目标 URI 与 host，防止跨 endpoint / 跨 host 复用）
- `arkret-operation`（header `Arkret-Operation`；按 §2.4.1，凡要求 RFC 9421 签名的 canonical 请求
  都 MUST 覆盖 operation selector。客户端面不例外：selector 参与业务解释、授权、幂等与审计，
  MUST 由发起签名的一方绑定。header 合法但未签入的请求 MUST 按 `http_signature_invalid` 拒绝；
  签入后被替换的请求 MUST 验签失败）
- `content-digest`（条件项：**带 body 的请求**必需；exact HTTP content bytes、canonical JSON 要求、
  RFC 9530 唯一 `sha-256` token 与验签前校验顺序遵循 [`service-http-binding.md` §8.2](./service-http-binding.md)）
- `idempotency-key`（条件项：**该请求参与幂等 / replay key 时**必需）
- `x-arkret-wait-for`（条件项：**该 header 出现时**必需）
<!-- END ak-http-signature-covered-set -->

签名 parameters MUST 包含 `created` 与 `expires`（不得用 `Date` 替代）。覆盖集是下界不是闭集，
实现 MAY 额外覆盖其它组件。上述判定由 `ak.vector.session.http_signature_operation_selector_binding.v1`
钉死。

与 session key 的绑定：签名 `kid` MUST 指向当前 `ak.session.grant` 委托的 `session_public_key`，且该 grant 的 principal / device / audience / origin 约束 MUST 与请求一致；grant 已撤销、过期或 audience / origin 不匹配时，服务端 MUST 拒绝（`unauthenticated`）。

Replay window：PoP 出示复用 [`service-http-binding.md` §8.3](./service-http-binding.md) 的共享签名时效窗口，本节不复制其数值。过窗签名即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝；幂等 / replay key 复用 §6 与 `Idempotency-Key` 机制。`encoding.md` §7.2 的 HLC 时钟漂移阈值是**另一个场景的独立阈值**，MUST NOT 被代入本窗口。

公开 metadata surface：若 endpoint 明确被定义为无需认证的 public surface（例如公开 describe 的 public metadata 子集），服务 MAY 在无认证材料或只有裸 bearer 的情况下返回公开响应；该响应 MUST 按未认证请求处理，不得授予 session / capability 语义，不得返回调用者私有 projection、自身 viewer 字段或任何依赖 session grant 的数据。若同一 endpoint 需要返回已认证视图，调用方 MUST 使用 DPoP / PoP / mTLS 绑定；裸 bearer 仍 MUST 被拒绝。

### 3.3 `/_arkret/self/*` 出示 grant + DPoP（normative，默认会话凭据路径）

Account Authority 以 `ak.session.grant` 作为客户端唯一可见的会话凭据；Station **不**为客户端铸发独立的本地 bearer，**不**存在第二个客户端可见的 Principal 本地凭据签发 endpoint。客户端对 `/_arkret/self/*` 的每次请求 MUST 直接出示该 grant，并叠加一份 sender-constrained 的 **DPoP（[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449)）** 持有证明：

```http
POST /_arkret/self/events
Authorization: DPoP <ak.session.grant>
DPoP: <DPoP proof JWT>
```

需要 fresh 高风险动作认证的操作（如用户自助擦除入口）不落在本面：它们 MUST 由 Account Authority 在 `/_arkret/gate/account/*` 直接受理。session grant introspection 刻意不投影 `auth_time` 或认证 proof kind，Station MUST NOT 依据 introspection 或本地会话状态自行判定或近似认证新鲜度（见 [`../identity/account-lifecycle.md` §8.1 与 §10](../identity/account-lifecycle.md) 的认证新鲜度归属原则）。

Station 对每次 `/_arkret/self/*` 请求 MUST 校验（任一项判定为不满足即 `unauthenticated`，fail closed；权威依赖本身不可达或响应不完整不属于本列表的失败项，按下文「依赖不可达」处理）：

- **DPoP 签名**:DPoP proof JWT MUST 用该 grant 的 grant-binding(DPoP)key 签名，其公钥 JWK thumbprint（[RFC 7638](https://www.rfc-editor.org/rfc/rfc7638)）MUST 等于 grant 的 `cnf.jkt`(Station 通过 session-grant 内省取得 `cnf_jkt`,见 §3.1 与下文)。
- **DPoP 绑定声明**:`htm` MUST 等于请求方法、`htu` MUST 等于请求 URL、`ath` MUST 等于所出示 grant 的 hash;这些把该 proof 钉死到「本方法 + 本 URL + 本 grant」,防跨 endpoint / 跨 grant 复用。`htu` 比对遵循 [RFC 9449](https://www.rfc-editor.org/rfc/rfc9449) §4.3,先剥离 query 与 fragment，再逐字比较经规范化的 scheme + authority + path。**外部 URI 重建**:`htu` 的 authority 是客户端看到的 gate origin。直连部署 MUST 使用请求自身的 scheme 与 authority；反向代理部署 MUST 使用静态配置的 public origin，或仅接受由受信最后一跳代理写入、并在入口清洗所有客户端同名 header 后得到的 `Forwarded` / `X-Forwarded-Host` / `X-Forwarded-Proto`。实现不得信任任意首跳转发值，也不得退化为 path-only 比对；无法可靠重建完整外部 URI 时 MUST 以 `unauthenticated` 拒绝 DPoP 出示。
- **grant active**:grant MUST 经 exact-token 内省判定 issuer ledger 当前为 active(`ak.gate.account.command.introspect_session_grant.v1`,提交本次出示的完整 token 与本 Station 的 `audience_id`)。本地 session/cache 只是有 freshness 上限的投影，MUST NOT 覆盖 issuer 返回的 revoked/superseded/expired 或成为第二真相源。内省的 `proof` 字段是部署内部 S2S 的可选附加确认；默认 self-path 客户端只发送本节的 `Authorization` + `DPoP`，Station MUST 依据内省返回的 `cnf_jkt` 在本地校验该请求的 DPoP，不得要求客户端再发送额外的 session-grant introspection proof header。
- **grant class/binding**：JWT 与内省必须使用
  `service-operation-dtos.schema.json#/$defs/SignedSessionGrantClaims` 的 typed
  `credential_class`，Arkret v1 固定为 `standard` 并必须携带 `holder_binding`。恢复完成入口在核验 replacement
  device 后直接签发同一种 Standard grant，不存在临时恢复凭据类。`standard.holder_binding` 在 JWT 与 introspection
  共用同一 closed discriminated XOR wire：human 分支恰为
  `{kind="human_device",device_binding}`，并禁止全部 Agent runtime字段；Agent分支恰为
  `{kind="agent_runtime",agent_id,device_id,agent_key_authorization_ref,verification_method}`，并禁止
  `device_binding`。
  `agent_key_authorization_ref`就是唯一 authorization代次，必须 resolve为 current accepted
  active authorization，不存在额外 `generation`字段或隐式数据库 generation轴。Station 在每个
  self-path admission 中必须依据本请求取得的权威内省结果同时重验 token subject、分支 binding ref、runtime device、current accepted Agent
  key authorization及 Agent/controller current lifecycle；仅匹配 kind、key digest、scope内 device字符串或
  service-private row均不得替代 signed binding。持 active authorized Agent key但尚无 session的 runtime可凭 PoP
  取得 standard Agent session，不能伪装 human device。
- **audience**:grant 的 audience MUST 等于本 Station 的 service DID。
- **scope**：grant scope MUST 含当前 endpoint 对应的 operation scope；scope 只表达服务操作授权，MUST NOT
  使用旧 `session.bind` 哨兵或 device scope 代替 typed holder binding。
- **principal / device 绑定**：grant 的 subject 与 typed `holder_binding` MUST 与请求 principal / device 一致；
  introspection 若同时返回顶层 device metadata，它也 MUST 与 signed holder binding 逐字一致。
- **未过期**:grant 与 DPoP proof 均 MUST 未过期。
- **DPoP 重放防护**:Station MUST 按 DPoP `jti` + `iat` 新鲜度窗口拒绝重放。DPoP proof 只有 `iat`、没有 `expires` parameter，因此该窗口是**独立合同** `ak.dpop.freshness.v1`，正文见 [`service-http-binding.md` §8.4](./service-http-binding.md)；它 MUST NOT 继承 RFC 9421 的 `created` / `expires` 算法，两者共用同一把 grant-binding key 也不合并合同。

**SessionGrant exact-token 内省权威（normative）**：`ak.session.grant` 的状态与权威元数据只有一个来源——签发它的 Account Authority 的 issuer ledger，经 [`service-http-binding.md` §2.2.3](./service-http-binding.md) 的部署内认证通道以 exact-token 内省取得。

- **权威判定分支**：用于请求准入的内省 MUST 使用 `grant_jwt` 分支提交本次出示的**完整 token 字节**，并携带本 Station 的 `audience_id`；Account Authority MUST 在 ledger 中定位该 exact credential 后判定状态，并在 `active` 时返回本次准入所需的全部权威元数据（`issuer_id`、完整 `account_id`、`audience_id`、`credential_class`、`holder_binding`、`scopes`、`expires_at`、`cnf_jkt`、`session_public_key`）。
- **`id` 分支边界**：`id` 分支只能用于其合同原本允许的管理 / 状态查询。它返回的 `active` MUST NOT 用来为另一份未逐字节核对的 JWT 授权；任何以 ID 为键的等价本地状态读取，MUST 先证明所出示 token 的 exact bytes（或等价的完整凭据绑定）与该 ledger record 相同。
- **不重建 issuer 事实**：Station MUST NOT 以本地 JWT 验签、issuer DID 历史回放或从 signed claims 重算 issuance preimage / suite-tagged ID / `jti` 作为授权依据。本地验签不产生 active ledger record，MUST NOT 成为独立的授权路径或撤销观测替代物。
- **一次请求一份权威结果**：Station MUST 先确定本请求所有消费步骤（DPoP 校验、scope、device / Agent gate、高安全 body proof）中**最严格**的 freshness 要求，按该要求取得一份权威结果，再把同一份结果传递给后续 gate；同一请求 MUST NOT 为同一枚 token 发起第二次独立内省。跨请求 MUST NOT 复用「DPoP 已验」布尔值，也 MUST NOT 把仍可变的会话 / 账号状态冻结成无限期有效。
- **缓存与最大陈旧度**：Station **MAY** 缓存权威结果，缓存键 MUST 至少隔离 exact token、预期 `audience_id` 与权威配置上下文（issuer / 通道身份），MUST NOT 只用 `jti` 或 grant id 作键。self-path 结果的最大陈旧度 **MUST ≤ 120s**，管理 / 状态查询面的最大陈旧度 **MUST ≤ 30s**，敏感 operation MUST 旁路缓存、强制取 fresh 结果（吊销生效上界即该最大陈旧度，见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md)）。共享 HTTP client、typed 解析与有界缓存设施时，各通道的认证方式、完整 `account_id` 绑定、scope 规则、错误语义与上述不同最大陈旧度 MUST 分别保留；实现复用 MUST NOT 把较严的一侧放宽到较松的一侧。主动失效是可选加强项，MUST NOT 被宣称为即时撤销，且 MUST NOT 让较旧的 in-flight `active` 响应覆盖更新的失效观察。
- **依赖不可达**：权威依赖不可达、超时或响应不完整时，Station MUST 按既有依赖错误 fail closed（`temporarily_unavailable`，SHOULD 带 `Retry-After`）。该情形 MUST NOT 被解释为 `active`，MUST NOT 由调用方自报的 metadata 兜底，也 MUST NOT 改写成 `unauthenticated` 等用户认证失败。仅当存在仍在最大陈旧度内、且该 operation 允许缓存时，才可使用已缓存的权威结果。

实现 MUST 通过 `ak.vector.session.dpop_target_uri_binding.v1`，证明跨 authority、跨 scheme、伪造转发头与 authority 不可重建场景均 fail closed，且不存在 path-only fallback。

**DPoP 与 RFC 9421 PoP 是两层正交保障**。DPoP（RFC 9449）提供 per-request 认证 + sender-constraint，但**不绑定请求 body**——默认 profile 下 body 完整性依赖 TLS(与 Matrix 同口径)。§3.2 的 RFC 9421 PoP 则额外提供 body 完整性(覆盖 `content-digest`)。两层用**同一把** Ed25519 grant-binding(DPoP)key:该 key 的 RFC 7638 thumbprint 即 grant 的 `cnf.jkt`(DPoP 绑定),其公钥即 grant 委托的 `session_public_key`(9421 绑定),客户端无需为 DPoP 与 9421 各管理一把密钥。此 grant-binding key 是短期会话认证凭据，必须独立生成、独立存储并随 session 轮换；其私钥字节、公钥字节、JWK thumbprint 与 `kid` 都 MUST NOT 等于或复用签事件 / KeyPackage / MLS 的长期设备身份 key(`device_public_key_did`)。违反分离要求的请求 MUST 以 `unauthenticated` fail closed(见 [`../crypto-media/device-lifecycle.md` §3.3/§5.2](../crypto-media/device-lifecycle.md))。

- **默认 profile**:self-path 的会话出示就是本节的 grant + DPoP;RFC 9421 PoP 可选叠加。
- **高安全 profile**(`sovereign_deployment` / `high_security_organization`，见 §3.2 末段):对所有受保护的 `ak.self.*` operation，Station **MUST** 在 grant + DPoP 之外**再要求** RFC 9421 PoP 出示；仅出示 grant + DPoP、缺 `Signature-Input` 的此类请求 MUST 被拒。此时 9421 校验的 `session_public_key` **MUST** 取自本请求上文已取得的**那一份**权威内省结果(grant + DPoP 会话为请求级、不落库为本地 bearer)，而非持久化 session 记录，也 MUST NOT 为此发起第二次独立内省。

该模型对齐 Matrix [MSC3861](https://github.com/matrix-org/matrix-spec-proposals/pull/3861)（Auth Server 签发凭据 + Resource Server 内省）的方向，并在其上叠加 DPoP sender-constraining(比 Matrix 的裸 bearer 更强)。

**其它仍合法的入站凭据**:除 grant + DPoP 外，Station MAY 在 development mode 保留本地开发凭据回退；生产客户端默认且规范化的 self-path 出示路径是 grant + DPoP。Auth Server 的 OIDC/OAuth 结果 MUST 先进入 Account Authority 的 `SessionGrantOutcome`，不得作为 Station 的 self-path 直接凭据。

**SessionGrant operation replay（normative）**：issue 与 refresh 使用 proof/operation-specific 稳定 request
identity 加 canonical intent digest。exact replay 在重新验证当前 holder/DPoP、method/target、issuer/audience
与 digest 后 MUST 返回首次 durable outcome；同 key 异 intent MUST `duplicate_conflict`。若记录的 outcome
已经 expired，返回 `session_grant_replay_expired`；若 revoked/superseded，返回
`session_grant_replay_terminal`；若 replay retention 后已无法判定，返回
`session_grant_replay_indeterminate`。三者都 MUST NOT 返回成功或静默生成新 grant，客户端必须用新的
one-shot proof 与 request identity 重新认证。account-first 恢复不得重做已经 accepted 的 DID operation
或 Recovery Key，见 [`../identity/account-lifecycle.md` §2.1.3](../identity/account-lifecycle.md)。

### 3.4 Account handoff + DPoP（normative，pre-registration 路径）

[`account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 的 `account_handoff_grant` 是 Account Authority 的临时 sender-constrained 凭据，不是 `ak.session.grant` 或 OAuth bearer。创建 handoff 时尚无 credential 可计算 `ath`：客户端对 `POST /_arkret/gate/account/authentication-handoffs` 发送不带 Authorization 的 DPoP proof，proof JWT header 中的 public JWK 建立候选 holder；该 JWK MUST 是 Ed25519，body `AccountHandoffAuthenticationProof.signature` MUST 由同一 key 按 canonical schema transcript 签名。Account Authority 必须验证两处 key 一致后，才把其 RFC 7638 thumbprint写入 handoff `cnf.jkt`。

后续 challenge、register 与 returning-device `HumanSessionGrantRequest` 使用：

```http
POST /_arkret/gate/account/identity-binding-challenges
Authorization: DPoP <account_handoff_grant>
DPoP: <DPoP proof JWT>
```

Account Authority MUST 验证 DPoP signature key thumbprint 等于 handoff `cnf.jkt`，`htm` / `htu` 精确绑定当前 method 与外部完整 endpoint URI，`ath` 等于所出示 handoff 的 hash，`jti` 未使用，`iat` 在新鲜度窗口内，handoff 未过期/撤销且当前 operation 位于其闭合 `allowed_operations`。外部 URI 重建与受信代理规则完全复用 §3.3；不得 path-only 比对。任一失败均 `unauthenticated` 或该 operation 登记的 `proof_invalid`，且不得进入 lease、challenge、DID publish、binding 或 grant 副作用。

DPoP 本身不覆盖 request body。`create_handoff` 的 body 完整性由上述 holder signature覆盖；`register(identity_creation)` 的身份关键字段由 root-signed control proof 与 reserved operation digest覆盖。高安全部署 MAY 额外要求 §3.2 RFC 9421 `content-digest`，但不得因此省略 DPoP holder 校验或 root control proof。

## 4. 标准 HTTP 成功响应

HTTP 成功响应没有跨 operation 的通用 envelope，也没有通用 `ok` discriminator。每个 operation 必须在 `contract-registry.json#operation_registry.operations[].success_shape_kind` 声明且只声明下列一种成功形态：

- `typed_response`：返回 endpoint-specific JSON 对象；其必填字段必须直接表达业务结果，例如资源标识、closed `status`、计数或逐项结果。响应对象及其递归子对象均 MUST NOT 使用名为 `ok` 的字段；
- `empty_response`：返回无 entity body 的成功状态；默认使用 HTTP 204，MUST NOT 发送 JSON `{}`、`null` 或 `{ "ok": true }` 作为占位。

请求级失败必须走 §5 的非 2xx Problem Details，MUST NOT 在 2xx body 中使用 `ok=false` 表达。多结果操作若允许部分成功，必须以 operation-specific closed `status` 和逐项结果完整表达；例如 Applet transaction 使用 `status ∈ {accepted, partial, rejected}`，而不是把任意布尔值与 `rejected[]` 拼接。

流式 endpoint MAY 使用 newline-delimited JSON、SSE 或 WebSocket frame，但 frame 合同由对应 transport binding 独立定义，不得把本节 HTTP body 规则机械套入 WebSocket、gRPC 或 MQ。成功建立的 subscribe stream 若需要指示客户端延迟重连，MUST 使用 control frame 上的 `reconnect_after_ms`。

## 5. RFC 9457 HTTP 错误响应

Arkret v1 HTTP endpoint 的所有非 2xx 响应 MUST 只使用 [RFC 9457 Problem Details](https://www.rfc-editor.org/rfc/rfc9457)，并设置 `Content-Type: application/problem+json`；该行为不依赖请求的 `Accept`，也不存在旧私有错误 envelope 的 content-negotiation 双轨。

```json illustrative
{
  "type": "https://arkret.org/problems/capability_denied",
  "title": "Capability denied",
  "status": 403,
  "detail": "actor does not have ak.strand.update on this strand",
  "instance": "ak:request:01964137-0000-7000-8000-000000000000"
}
```
核心成员规则如下：

- `type` 是稳定且唯一的机器判别字段，固定为 `https://arkret.org/problems/{code}`；`{code}` 必须来自 `error-code-registry.json`，客户端不得从 `title` 或 `detail` 推断错误类型；
- `title` 是该 problem type 的稳定短标题；`status` 必须与 HTTP status line 一致；`detail` 仅用于本次错误的开发者诊断，不得承载稳定程序逻辑；
- `instance` SHOULD 是本次请求的可追踪 URI-reference；含敏感上下文的内部日志定位信息不得直接放入 wire；
- `retry_after_ms`、`reason_code` 及其它扩展成员直接位于 problem 根对象。producer 只能发送该 `type` 在 registry 或对应 typed schema 登记的扩展；不得重新引入通用 `details` bag；
- consumer 必须容忍未知扩展成员，但必须校验核心成员类型，并以完整 `type` URI 进行分派；未知 `type` 仍按其 HTTP status 类别作为失败处理。

`Retry-After` header 是 HTTP 重试时序的权威来源；若同时存在注册的 `retry_after_ms` 扩展，两者必须语义一致。WebSocket、gRPC 与 MQ 的错误 frame/status 合同保持各自 transport 形态，不伪装为 `application/problem+json`。

### 5.1 标准错误码

Problem `type` URI 的 `{code}` 尾段与批处理/联邦响应中的逐项 `reason_code` 共享同一字符串命名空间。**Canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)：所有标准 code、`type_uri`、`title`、HTTP 状态、scope (`response` / `endpoint` / `both`) 与简短描述均以该 registry 为准。新增、修改或删除 problem type MUST 先更新 registry；本文与 [`service-http-binding.md` §6](./service-http-binding.md) 只引用该 registry，不维护并行表格。

实现使用要点（registry 之外的语义协议）：

- 错误语义必须使用单一标准 code。若请求体过大使用 `payload_too_large` / 413；若配额策略拒绝使用 `quota_exceeded` / 403。
- `revision_stale` / 409 表示服务可用但本地因果前沿落后，客户端可等待或 backfill；服务故障、维护或无法追赶 checkpoint 时使用 `temporarily_unavailable` / 503 并 SHOULD 返回 `Retry-After`。
- 格式错误的 cursor 使用 `param_invalid` / 400；格式正确但已过期的 cursor 使用 `cursor_expired` / 410。
- `unsupported_feature` 用于两类情形：`Event.requirements.features[]` 与 `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；以及 active 标准 kind 的 Event 结构合法、但其 wire 特性或 producer 类在 v1 支持矩阵中登记为 unsupported（例如 `rfc9420.proposal` 解码出的 RFC 9420 sender class 或 Proposal 类型，见 [`artifacts/registry/mls-proposal-admission-registry.json`](../sync/authority-commit-log.md)）。后一类 MUST NOT 报成 `schema_violation`。`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `ak.*` Event kind。三种情形不得互相替代。
- `conflict` / 409 是抽象 base code；实现 SHOULD 返回 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 中 `http_status=409` 的更精确 code。本文不维护并行穷尽清单；示例包括 `cas_conflict`、`causal_conflict`、`dependency_missing`、`duplicate_conflict`、`revision_stale`、`state_mismatch`。
- 加密 envelope 相关 422 子 code（`aad_digest_mismatch` / `payload_digest_mismatch`）的 canonical 定义在 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)；它们判定的 AAD 与 payload 绑定见 [`../crypto-media/encryption-and-audit.md` §2.3](../crypto-media/encryption-and-audit.md) 与 §2.8。

CI（`tools/artifact_pipeline.py check`）MUST 校验仓库内所有出现的字面 error code 字符串都登记在 registry 中，并 MUST 校验 `operations-error-mapping.json` 的 `rules.universal_codes` 与每个 `operations[].operation_specific[]` 不引用 registry 外的 code。

### 5.2 未知路径与错误方法

对 `/_arkret/*` 之下的请求，服务端 MUST 使用统一错误响应，不得返回 HTML、纯文本框架错误或实现栈信息。

规则：

- 未声明或未实现的路径 MUST 返回 HTTP `404` 与错误码 `unrecognized_endpoint`。
- 已知路径但 HTTP method 不受支持时 MUST 返回 HTTP `405` 与错误码 `method_not_allowed`，并 SHOULD 设置 `Allow` header。
- 这两类请求 MUST 在路由层终止，不得进入业务逻辑、写入队列、触发昂贵解析或产生可观察副作用。
- 客户端和联邦对端 MUST 使用 `describe.supported_operation_bundles` 的精确 carrier/schema 交集、OpenAPI 文档和 feature discovery 判断 endpoint 是否可用，不得根据非标准 404 body 做能力推断。

## 6. 幂等

请求级幂等行为的 active 认证入口是 `ak.vector.api.request_idempotency.v1`（`protocol-edge-cases-fixture.json`）；runner MUST 覆盖同键同 body、同键异 body、跨 principal/operation 复用、`canonical_hash_input` 指针和 24 小时保留临界点。

每个写接口 MUST 在 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 中声明幂等机制与重试安全性。只有 `retry_safe=true` 的 operation 承诺可对逐字节相同的完整请求执行自动幂等重试；`retry_safe=false` 的 operation 不作该承诺，客户端必须走 operation-specific outcome 查询、恢复流程或人工确认。

`retry_safe=true` 且 `idempotency_mechanism != "none"` 的写入请求 MUST 携带或内生由 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 同行声明的稳定 request identity；`retry_safe=false` 的 operation 仅在其 registry 行声明了对应机制时才使用该机制。少数使用 command binding 但语义为纯计算 / 只读判定的 operation MAY 声明 `none/true`，前提是任何重复执行都不持久化状态、不消费一次性材料且不产生外部副作用。

**机读真相源（normative）**：每个 operation 实际采用哪种幂等机制（§2.5 所列 `idempotency_key` / `object_id` / `request_id` / `canonical_hash` / `protocol_sequence`），以 operation registry 的 `idempotency_mechanism` 字段为准；配套 `retry_safe` 布尔字段声明"逐字节相同的全量重试是否不产生重复副作用"（`true` = 重试返回原 outcome、等价幂等 no-op 或确定性冲突；`false` = 盲目重试可能重复副作用或消费一次性材料）。客户端 MUST NOT 对 `retry_safe=false` 的 operation 在未带外确认首次请求效果的情况下自动重试。

`canonical_hash` 的默认 identity 是 `sha256:` 加 `canonical_json(完整请求体)` 的小写十六进制摘要，去重作用域是 `(authenticated principal, operation_id, canonical_hash)`。若 operation registry 同行声明 `canonical_hash_input`，其值 MUST 是 RFC 6901 JSON Pointer；接收方以该 pointer 选中的值计算 identity，同时仍须保存完整请求体的 canonical hash。同一 identity 对应不同完整请求体 MUST 返回 `duplicate_conflict`。因此 pointer 只能指向内容派生且协议定义为稳定身份的字段，不能把可碰撞的客户端标签当成内容摘要。

对请求级 identity 机制（`idempotency_key` / `request_id` / `canonical_hash`）适用以下规则。self 面的 `Idempotency-Key` 去重作用域 MUST 至少绑定 `(authenticated principal, operation_id, Idempotency-Key)`；不同 principal 或不同 operation 复用同一字符串不构成重复：

- 相同幂等键 + 相同 canonical request body MUST 返回与首次请求语义等价的结果。
- 相同幂等键 + 不同 canonical request body MUST 返回 `duplicate_conflict`。
- Contact self commit 的暂时未确认响应遵守 [Contact 写链 §2](../identity/contact-and-direct-conversation.md#2-contact-写链回执与-contact-round)：`503 temporarily_unavailable` 不表示未写入，也不是首次耐久终局 outcome。相同完整请求继续查询原 Event 的终局；不得永久缓存该临时错误、重建 Event 或在 RealmCommit 确认前返回可授权 receipt。prepare 的首次 draft 与 commit 的首次耐久终局分别固定；终局包括 typed accepted/领域 failed 与按真实拒绝原因登记映射的 Problem Details，后者固定原 HTTP status/body。
- 服务端 SHOULD 记录 request identity 与完整 canonical request hash；联邦与服务间写入 MUST 将完整 hash 纳入签名 transcript 或 transaction replay cache。
- `object_id` 与 `protocol_sequence` 通常是资源/协议状态 identity，不是请求级幂等键。逐字节相同的合法重放按 registry 的 `retry_safe` 承诺返回原 outcome 或等价 no-op；同一对象或序列上的不同 canonical body 通常是普通后继写，受 CAS、checkpoint、版本或状态机规则约束。
- **Event submit 的两层 identity**：`ak.self.events.command.submit.v1` 与 `ak.peer.events.command.submit.v1` 均登记为 `canonical_hash / full_body / retry_safe=true`，不得解释成 `protocol_sequence` 或把 `event_id` 当作 request identity。外层 request replay identity 是完整 `submit_request` canonical body 的 SHA-256；普通 Event 分支即完整 `EventAdmissionSubmission`，包括 Event 之外的 `approval_signatures`。它服从本节的 principal／operation 作用域、至少 24 小时记录下限与同 identity 异完整 body 的 `duplicate_conflict`。内层 `event_id` 只是不变 Event 内容身份：接收方仍 MUST 从当前 canonical Event bytes 重算 EventId；carried ID 不匹配是 `event_id_digest_mismatch` 且零副作用。只有不同 digest-preimage canonical bytes 各自重算为同一个完整 EventId 时，才 MUST 按 operations-sync §12／event-auth-state-resolution §15 整组 quarantine，并返回登记的 `witness_disagreement` reason。任何被外层 full-body hash 覆盖但不进入 EventId preimage 的字段变化都会形成不同外层请求；仅 excluded envelope 字段不同本身不构成 EventId 碰撞，也不得弱化内层重算与见证分歧规则。
- `idempotency_mechanism="none"` 与 `retry_safe=false` 同时出现时，该 operation MUST 在 binding 文档中给出超时后的 outcome 查询、一次性材料重新签发或人工确认路径；客户端 MUST NOT 把传输失败解释为“服务端未执行”并盲目重放。`none/true` 只表示重复执行纯计算等价，不产生需要去重的 write outcome。

上述恢复路径的机读真相源是 operation registry 同行 `uncertain_outcome`：`query_operation` 必须引用 outcome/read operation；`reissue_material` 必须引用重新签发入口并要求 fresh request identity；`revoke_then_reissue` 必须分别引用幂等 revoke 与 fresh-material issue operation，并要求 fresh request identity，客户端只有在 revoke 已达可确认终态后才可 issue；`manual_confirmation` 明确进入 uncertain 人工确认；`drop_unconfirmed` 仅允许不持久化、可安全丢弃的 ephemeral/fanout signal。`none/false` 缺该字段、引用未知 operation、或任何重新签发策略未要求 fresh identity 时，artifact lint MUST 失败。

### 6.1 幂等记录保留窗口（normative）

- 对请求级 identity 机制的 operation，接收方 MUST 自幂等记录创建时刻起保留该记录**至少 24 小时**。`object_id` / `protocol_sequence` 的状态保留由对象生命周期或协议状态机决定，不受本段请求去重记录窗口约束。
- 该保留窗口 MUST ≥ 对应请求面的签名寿命上限（见 §3.2 与 [`service-http-binding.md` §8.3](./service-http-binding.md) 的共享窗口）加最大允许时钟偏移。
- 保留窗口内，同一请求级幂等键 + 相同 canonical request body 的重放 MUST 返回与首次请求语义等价的原 outcome；同一请求级幂等键 + 不同 canonical request body 仍按本节上文规则返回 `duplicate_conflict`。
- 保留窗口过后的重放行为由实现自定（MAY 按新请求处理或拒绝），但实现 MUST NOT 对窗口外的重放声称幂等保证。
- 在 24 小时下限之上，服务端 SHOULD 记录幂等结果至少到相关 Event 被最终同步或过期。

Applet transaction push 的幂等记录（[`applet-integration.md` §7.3](../extensions/applet-integration.md)）与联邦幂等 / replay cache（[`federation.md` §8.5](./federation.md)）都遵循本节保留窗口，不另行定义更短窗口。

### 6.2 客户端重试义务（normative）

- **安全全量重试同 identity**：仅当 registry 声明 `retry_safe=true` 时，语义上同一请求的全量重试才允许自动执行。若 `idempotency_mechanism != "none"`，重试 MUST 复用 registry 所声明的同一稳定 request identity（`Idempotency-Key` / request id / object id / canonical hash / protocol sequence），且 canonical form 的 request body MUST 逐字节相同；若为纯计算 `none/true`，请求体仍 MUST 逐字节相同，但不虚构 idempotency key。`event_id` 仍只按上文承担 Event 内容身份，不因出现在请求内就成为未登记的第六种 request mechanism。
- **不安全 operation 禁止自动重放**：`retry_safe=false` 时，客户端 MUST NOT 自动全量重试；必须先执行该 operation 的 outcome 查询或恢复流程。若没有机器可调用的恢复路径，调用方只能把结果标为 uncertain 并请求人工确认，不能生成新的 key 盲目再发。
- **改内容必换 request key**：采用请求级 identity 的请求修改内容后重交 MUST 换新幂等键，MUST NOT 以旧幂等键携带新 canonical body 重交（服务端按上文规则返回 `duplicate_conflict`）。`object_id` / `protocol_sequence` 不适用本条。
- **Event submit 不采用 schema 外的批次求差规则**：两项 Event submit 的具体 request／outcome shape 只由 operation registry 同行的 `request_schema_ref`／`response_schema_ref` 决定。self union 的普通／MLS／DC founding／membership compensation 各自按 schema 返回单 outcome；peer union 的 `authority_forward` 与 `registered_atomic_unit` 同样没有 per-item partial。只有 peer `committed_replication` 明确登记同序 `replication_outcomes[]`，其状态是 `stored|duplicate|rejected`；数组位置唯一绑定 `replications[]` 的同位置输入，因此 outcome 不重复 `index` 或 source coordinates。这里不存在顶层 `accepted[]`／`duplicate[]`，调用方不得从完整 replay 中删去已经 stored 的 item 来构造 partial retry。由于两项 registry 行都是 `canonical_hash / full_body / retry_safe=true`，调用方对结果不确定的 transport retry MUST 重发逐字节相同的完整 request body，并由接收方返回原 branch outcome 或等价幂等结果；同一 24 小时保留窗口内，相同 full-body canonical hash 不能在依赖变化后被解释为一次新求值。依赖补齐后若协议允许构造内容不同的新提交，该完整 body 产生新的 canonical hash；不得用外层重试改写内层 Event bytes、`event_id`、source `RealmCommit` 或首次请求的 outcome。

## 7. Cursor（统一不透明 token）

> **Scope（normative）**：本节只定义 cursor 在 HTTP/JSON binding 上的**使用契约**——出现位置、`purpose` 语义、分页方向（`before` / `after` / `prev_cursor` / `next_cursor`）与不透明性约束;cursor 的内部 canonical 结构、字段 schema、编码与 TTL 硬上限数值见 [`encoding.md` §8](../conformance/encoding.md) 与 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)。
>
> **具名例外（normative）**：单条 stream 的扫描——`ak.self.events.read.scan.v1` 与 federation peer `ak.peer.events.read.scan.v1`——**不使用 cursor**，见 §7.2。本节的 cursor 出现位置、方向表与三字段合同都不覆盖这两个 operation；任何把它们读成"cursor 分页"的实现都是错的。

Arkret v1 在**仍然需要**不透明 token 的位置使用**单一** `cursor` 类型，wire 形态固定为 `ak:cursor:<base64url(canonical_json)>`，schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)。它承担 account 聚合流的增量同步、列表分页和写后读屏障三类用途；单 stream 扫描不在其中（§7.2）。

cursor 内部包含一个 `purpose` 字段（客户端不解析；仅供 issuing 服务自检）：

| `purpose` | 用途 | 出现位置 |
| --- | --- | --- |
| `stream` | 增量同步 / 列表分页的位置承诺。回传方向取决于出现位置（见右列），并非任意位置都支持全部四向。 | **account 聚合流**：`/_arkret/self/account/subscribe` frame 的 `cursor` **仅**作为重连 `after=` 参数回传，是单向 catch-up 起点，**不支持** `before` / `prev_cursor`（account stream 不可反向，见本文 §7.0 与 [`client-sync.md` §2](./client-sync.md)）。**列表分页**：列表接口的请求 cursor 与响应 `prev_cursor` / `next_cursor`——只有这些位置支持 `before` / `prev_cursor` 反向延续。单 stream 扫描不在此列（§7.2）。 |
| `barrier` | 读己之所写（RYW）：要求 reader 在 checkpoint 覆盖某个具体 event 之前不返回结果。 | 写接口响应中的 `cursor` 字段、`X-Arkret-Wait-For` header。 |

### 7.0 `prev_cursor` / `next_cursor` 含义（绝对方向）

任何返回 cursor 对的响应（列表分页等）使用统一的**绝对方向**约定；`/_arkret/self/account/subscribe` frame 只返回单个 account stream cursor,用于下一次 `after=` 重连：

| 响应字段 | 含义 | 回传给下一次请求 |
| --- | --- | --- |
| `prev_cursor` | 朝**更旧事件 / 更早历史**方向的延续位置 | 分页 `before=<prev_cursor>` 取更旧一批 |
| `next_cursor` | 朝**更新事件 / 更晚未来**方向的延续位置 | 分页 `after=<next_cursor>` 取更新一批 |

绝对方向与请求时所用的参数（`before` / `after` / `order`）和 selector 无关；服务端 MUST 始终按上述含义填充。客户端因此**不**需要记录"上一次请求的 direction"才能正确解释响应 cursor。

HTTP/JSON binding 的 cursor purpose 位置一致性如下：`purpose=stream` 的 cursor 只可出现在 stream / pagination context（例如 `/_arkret/self/account/subscribe` 的 `after=`、列表接口的分页参数、响应 `prev_cursor` / `next_cursor`）；`purpose=barrier` 的 cursor 只可出现在本文 §8 定义的 RYW barrier context（写接口响应中的 barrier `cursor` 字段、`X-Arkret-Wait-For` header 或等价投影）。任一 context 收到不匹配的 `purpose` 时，服务端 MUST 返回 `param_invalid`。

规则：

- 客户端 MUST 把 cursor 当作不透明字符串，禁止解析以推断排序、权限或服务身份。
- 任何接受 cursor 的接口 MUST 在 wire/schema 层先拒绝不满足注册 cursor 类型与词法约束的值并返回 `schema_violation`；对通过该层但令牌结构、完整性或请求绑定无效的 cursor 返回 `param_invalid`，对已过期 cursor 返回 `cursor_expired`。
- 同一字符串 cursor 在不同 issuing 服务间不可移植；跨服务复用 MUST `param_invalid`。
- TTL 硬上限：barrier cursor 与 stream cursor 的 `expires_at - issued_at` 硬上限的**唯一 canonical 数值定义点**是 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 的 `expires_at`；本节与 [`encoding.md` §8](../conformance/encoding.md) 都不重复字面毫秒数值。
- 声明 `ak.feature.cursor_revoke_high_assurance.v1` feature 的服务必须实现 [`client-sync.md` §12.2.1](./client-sync.md) 的 revocation set。已撤销但仍在 TTL 内的 cursor MUST 返回 `cursor_revoked`；完整性失败仍返回 `cursor_integrity_invalid`，不得泄露 revocation set。

### 7.1 列表分页（normative）

所有列表接口 MUST 返回三个字段：

```json fragment
{
  "<items_field>": [],
  "next_cursor": "ak:cursor:...",
  "has_more": false
}
```
**`<items_field>` 命名约定** (normative)：
- 优先使用资源复数名（`realms[]` / `strands[]` / `morphs[]` / `spaces[]` / `backups[]` / `notifications[]` / `messages[]` 等）；
- 没有自然资源复数名时使用语义名：全文/混合实体搜索命中使用 `matches[]`，原始查询行使用 `rows[]`，private contact discovery 仍使用 `matches[]`；
- **MUST NOT** 使用 `results[]` 作为返回字段名，避免与 Rust `Result` 语义和 SDK 类型命名冲突；
- **MUST NOT** 使用通用占位 `items[]`，也不得使用 `events[]` 作为非 Event 数组的字段名（device_messages 与 account subscribe `to_device` 的 `messages[]` 例外见 `ak.self.device_messages.read.list.v1` 与 `ak.self.account.stream.subscribe.v1`）。

**`next_cursor` / `has_more`** (normative)：
- `next_cursor` 是 optional：缺省表示当前批次已经是末尾。
- `has_more: boolean` MUST 出现：客户端 MUST 仅按 `has_more` 决定是否继续翻页；不得仅靠 `next_cursor` 是否存在做判断（实现可能在末尾仍返回 `next_cursor` 用作 long-poll resume token）。

本小节的三字段合同**不**适用于单 stream 扫描：`ak.self.events.read.scan.v1` / `ak.peer.events.read.scan.v1`
既不返回 `next_cursor` 也不返回 `has_more`，字段集是 `stream_scan_outcome` 的 `{commits, truncated}`
（[`authority-commit-operations.schema.json`](../../artifacts/schemas/authority-commit-operations.schema.json)），
语义见 [`service-http-binding.md` §3.1](./service-http-binding.md) 与本文 §7.2。

**`prev_cursor`**（可选, 双向分页）：仅当接口支持向"更旧"方向翻页时返回。详见 §7.0；不支持双向翻页的接口 MUST NOT 返回 `prev_cursor`。

**Cursor 方向参数** (`before` / `after`)：见本文 §7.0。`before` / `after` 是绝对时间方向（朝更旧 / 朝更新），与响应 `prev_cursor` / `next_cursor` 形成一一对应；所有 v1 列表接口（包括 `ak.self.device_messages.read.list.v1`）MUST 使用这两个方向名，不得引入 `from=` / `start_at=` 等同义别名。单 stream 扫描的方向名是 `after_position` / `before_position`（§7.2），它们是**位置参数**不是 cursor 参数，同样不得引入同义别名。

服务端 MAY 对 `limit` 设置上限。超过上限时 SHOULD 使用最大允许值或返回 `param_invalid`。

### 7.2 单 stream 扫描用位置，不用 cursor（normative）

治理 Station 在每条 stream 上给出严格 +1 的 `RealmCommit.stream_position`
（[`authority-commit-log.md`](./authority-commit-log.md)），因此**在单条 stream 内位置本身就是完整的续传凭据**，
不需要服务端签发的不透明 token。`ak.self.events.read.scan.v1` 与 `ak.peer.events.read.scan.v1` 因此使用
位置分页：

- 请求是 `stream_scan_request` = `{realm_id, stream_ref, after_position | before_position（恰一个）, limit}`。
  `after_position` 朝更新方向、`before_position` 朝更旧方向（历史回填）；两者的排他性由 request
  合同的 `oneOf` 结构给出，同时出现或都不出现是 schema 违规。取 `null` 分别表示从该 caller
  获准读取的最旧位置、最新位置起——**不是**物理流首与物理流头。
- 响应是 `stream_scan_outcome` = `{commits, truncated, readable_floor?}`。续页由客户端取本批的
  最大 / 最小 `stream_position` 自行得到；响应 MUST NOT 返回 `prev_cursor` / `next_cursor` / `has_more`。
- 边界一律按该 caller 的允许区间解释：`truncated` 只表示该方向上还有它获准读取的 Commit，
  `readable_floor` 给出允许区间下端的 `oldest_position` 与该位置的 `floor_commit_id`。
  语义与逐页示例见 [`service-http-binding.md` §3.1](./service-http-binding.md)。
- 服务端 MUST NOT 在这两个 operation 上接受 `ak:cursor:` 值，也 MUST NOT 为它们签发 cursor。

决定性理由：[`service-http-binding.md` §3.2](./service-http-binding.md) 的 snapshot + tail 是规范定义的
bootstrap 路径，它交给客户端的是**每条获准 stream 的 head position**——此时客户端手上没有任何 cursor。
scan 若只收 opaque cursor，规范自己的 bootstrap 起不了步。federation peer 复制验的同样是逐 stream 连续性，
判据也是位置。

反过来，account 聚合流的 `after=` 与列表分页**不能**照此位置化：前者横跨 N 条独立 stream，没有可以明文
表达的标量位置，且明文位置向量会让调用方从 gap 推断它看不见的 private stream 是否存在
（[`client-sync.md` §4](./client-sync.md)）；cursor 的服务端 handle 还绑定 `filter_digest` 与 device，
换了过滤条件复用位置会静默漏事件。两者的不透明性理由与"事件是否有确定顺序"无关，不随全序 commit 消失。

## 8. 读己之所写

写接口成功后 SHOULD 在响应中返回一个 barrier cursor：

```json fragment
{
  "status": "accepted",
  "event_id": "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-",
  "cursor": "ak:cursor:..."
}
```
该 cursor 的 server-side handle 绑定到刚提交事件：`purpose=barrier`，`target.event_id` 与 `target.event_digest` 由 issuing server 通过 handle 解析；`target` 不出现在 cursor wire body 中。后续读接口 SHOULD 接受：

```text
X-Arkret-Wait-For: <cursor>
```

如果服务在超时前到达该 cursor 描述的 authority stream position，则返回正常结果；否则 SHOULD 返回 `temporarily_unavailable` 或 `timeout`，并附带当前 stream head。stream cursor 不得用于 wait-for header；服务端遇到 `purpose=stream` 的 cursor 出现在 wait-for 上下文 MUST 返回 `param_invalid`。

**Wait-for canonical 与投影（normative）**：`X-Arkret-Wait-For` HTTP header 是 wait-for barrier 的 wire canonical 形态；[`../conformance/query-schema.md §2`](../conformance/query-schema.md) 嵌套形态 `consistency: { wait_for, timeout_ms }` 与 [`../../artifacts/openapi/arkret-service-api.openapi.yaml`](../../artifacts/openapi/arkret-service-api.openapi.yaml) request body 扁平字段 `wait_for: string` 是同义投影，三者等价绑定到同一 RYW (read-your-writes) barrier 语义。服务端 MUST 接受任一形态并解析为相同 cursor；客户端 MAY 选择任一形态。当同一请求同时出现多种形态且取值不一致时，服务端 MUST 按下列优先级解析：(1) `X-Arkret-Wait-For` header；(2) request body `wait_for`；(3) `consistency.wait_for`。

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
- 适用范围：`rate_limit_scope`，例如 actor DID、service DID、device id、source IP、Realm id 或 blob quota。
- 窗口与额度：`window_seconds`、`max_requests`、`burst`；若是字节或批量限制，使用 `max_bytes`、`max_events_per_batch`、`max_body_bytes`。
- 重试提示：`retry_after_ms`、`backoff_hint` 或 `next_retry_at` 的语义。
- `effective_at` / `expires_at` 或缓存 TTL。若这些时间界限未知，客户端 MUST 把该策略视为最多缓存 60 秒，并按默认退避重试：首次重试间隔 ≥ 1,000 ms，随后指数倍增（factor=2）到 ≥ 60,000 ms 上限，加入 0-20% jitter，且同一 `(endpoint, scope)` 在 5 分钟内最多重试 5 次。

公开 describe MAY 只返回 coarse policy，避免暴露内部防滥用细节；认证后的 describe SHOULD 返回调用方当前可见的精确有效策略。ServiceDescribe MUST 携带 `rate_limit_policy` 或 `rate_limit_policy_id`；若服务除了通用滥用防护外没有可预期的端点级限流，也必须返回显式空策略（例如 `rate_limit_policy.entries=[]`），不得同时省略二者。一旦可能返回 `rate_limited`，describe 中的策略信息至少 MUST 暴露：受影响的 `endpoint` 或 `operation_id`、`rate_limit_scope` 类别、窗口字段（`window_seconds` 与 `max_requests` / `max_bytes` / `max_events_per_batch` / `max_body_bytes` 之一）或明确的重试提示字段（`retry_after_ms` / `backoff_hint` / `next_retry_at` 之一）。若安全原因只能返回 coarse policy，服务端仍 MUST 在每次 `rate_limited` 响应中返回可执行的 `retry_after_ms` 或 HTTP `Retry-After`。

触发限流时 MUST 返回 `rate_limited`，并 SHOULD 附带：

```json fragment
{
  "retry_after_ms": 2000
}
```
HTTP response MUST 同时设置 `Retry-After` header。`Retry-After` 的值按 HTTP 标准使用秒数或 HTTP date；若同时存在 `Retry-After` 与 `retry_after_ms`，客户端 MUST 优先使用 `Retry-After`。

**服务端提示与本地退避的唯一组合（normative）**：服务端提示和客户端本地指数退避都是“不得早于”的独立
下界。客户端选择继续重试时 MUST 使用
`effective_delay = max(server_hint_delay, jitter(local_backoff_delay))`。0 秒提示或已经过去的 HTTP date 按
`server_hint_delay=0` 处理，不能把本地首次至少 1,000 ms 或已经增长的退避梯子缩短为立即重试。0–20% jitter
只施加于本地退避，先于 `max`；不得向服务端提示增加随机量。服务端提示超出本地重试预算 / 退避上限时，
客户端 MAY 放弃并向上层报告失败；但只要继续，就不得按本地上限截短后提前重试。收到提示仍 MUST 推进本地
退避 attempt，单个长提示不得永久抬高后续梯子的基数。

规则：

- `429 rate_limited` MUST 设置 `Retry-After`。
- `503 temporarily_unavailable` SHOULD 在可预估恢复时间时设置 `Retry-After`。
- body 中的 `retry_after_ms` 用于非 HTTP binding 和精细诊断；其值 SHOULD 与 header 表达的时间一致。
- 客户端和对端服务 MUST 对同一 actor / service DID / endpoint 组合执行指数退避，避免重试放大。

本地退避无论服务端提示是否存在都按以下默认梯子推进：首次等待至少 1,000 ms，factor=2，单次上限至少
60,000 ms，应用 0–20% jitter，且同一组合在连续 5 分钟内最多自动重试 5 次；提示缺失时它就是唯一时间
下界，提示存在时按上式取最大值。声明 `traffic_metadata_hardened` profile 时，实际发送时刻还 MUST 受该
profile 的 `retry_cadence_padding` 约束。

## 10. CORS 与浏览器客户端

面向浏览器的服务 SHOULD 支持 CORS preflight。

推荐默认做法是回显经过 allowlist 校验的明确 origin；只有完全公开、无 credential、无隐私可见性差异的 metadata endpoint 才 SHOULD 使用 `*`：

```text
Access-Control-Allow-Origin: https://app.example
Access-Control-Allow-Methods: GET, HEAD, POST, PUT, PATCH, DELETE, OPTIONS
Access-Control-Allow-Headers: Authorization, Content-Type, Content-Digest, Digest, Idempotency-Key, X-Arkret-Wait-For, X-Arkret-Request-Id
Access-Control-Expose-Headers: Retry-After, Content-Digest, Digest, Content-Disposition, Content-Range, Location, X-Arkret-Request-Id
```

服务端 MUST NOT 在 `OPTIONS` preflight 请求中执行写入逻辑。

规则：

- `Access-Control-Allow-Methods` SHOULD 反映该服务实际支持的 method 集合；支持 `HEAD` 或 `PATCH` 的服务必须把它们列入 CORS。
- 服务端 MUST NOT 在 CORS 中允许 `CONNECT` 或 `TRACE`。
- 浏览器可访问的私有 endpoint 不得依赖 cookie 作为唯一认证方式；推荐使用 `Authorization` header 或 device-bound proof。
- 需要 credentialed CORS 或任何带 Authorization / device proof / session 语义的 endpoint MUST 回显明确 allowlisted origin，并继续按 §3 要求校验 header / proof / capability，不得把 cookie 当作协议层 principal。
- 若公开 metadata endpoint 响应使用 `Access-Control-Allow-Origin: *`，服务端 MUST NOT 同时设置 `Access-Control-Allow-Credentials: true`，且该响应 MUST NOT 因 caller identity 暴露不同 Realm、actor、member 或 blob 存在性。
- Preflight、CORS error、redirect 与 4xx/5xx body 都不得泄露不可见 Realm、actor、member 或 blob 是否存在。

## 11. 版本与 feature discovery

**path 不含版本段。** 所有 HTTP path 都是 `/_arkret/<信任段>/...` 形态的绝对路径，URL 只编码信任拓扑，版本是元数据，绝不放进 path（不存在 `/v1/`、`/api/v1`、`/arkret/v1`）。契约版本的唯一真相源是 `contract-registry.json` 与 `protocol_version`（固定 `"1.0"`）；wire 级版本由 schema id（`ak.schema.*.v1`）和 event kind 版本后缀承载。

版本与能力发现走 **`*.describe` 协商**：调用方 MUST 先精确比较 `describe.protocol_version`；与本地支持的 `"1.0"` 不等时 MUST 以 `unsupported_protocol_version` fail closed，不得解释或缓存其它声明。版本匹配后，调用方再用 `describe.supported_operation_bundles` 的精确 carrier/schema 交集与 `supported_profiles`（而非 path 里写死的版本）判断对端支持什么。传输层版本使用请求/响应 header（`Arkret-Protocol-Version: 1.0`）或 media-type 参数做 content negotiation，**绝不放 path**。选择支持该请求 header 或等价 media-type 参数的 binding，对不支持的形状合法版本 MUST 返回 `unsupported_protocol_version`，不得猜测或回退。

每个服务 SHOULD 暴露 describe endpoint，返回：

- `protocol_version`
- `service_kind`
- `service_id`
- `supported_features`
- `supported_profiles`
- `auth_metadata`
- `max_body_bytes`
- `limits`
- `rate_limit_policy`
- `rate_limit_policy_id`

客户端 MUST 根据 feature discovery 决定是否启用可选能力，不得假设所有节点都支持完整协议。

### 11.1 服务发现缓存与委托

对 [service-surface §2.6](./service-surface.md) 的独立验证角色，服务入口唯一来自经 method adapter 验证的 DID Document；普通客户端自己 Station 的接入与认证绑定按 [server-trusted-results §1.2](./server-trusted-results.md#12-普通客户端的-station-接入normative)，不承担此处方法历史验证。独立验证路径的域名 bootstrap 仅暴露 resolution_url 等发现线索；接收方必须验证 service_id/kind、完整原生历史、已接受 method 状态、当前查询的新鲜度、唯一 ArkretService endpoint、describe 二跳一致性，以及业务 policy/delegation。缓存按 [service-surface.md §2.6](./service-surface.md) 有界使用，HTTP TTL 不能延长证据或授权有效性。失败不得推进 method 状态或续期路由；service core 改变必须重新授权业务绑定。

### 11.2 出站网络目标策略与 SSRF 防护

任何服务在访问由用户、远端 peer、DID Document、Directory、Blob/Media metadata、Snapshot manifest、Applet/Agent endpoint、Webhook 或 service discovery 返回的 URL 之前，MUST 执行出站网络目标策略。该规则覆盖 DID resolution、联邦 push/pull/checkpoint probe、媒体抓取、thumbnail 生成、snapshot/chunk fetch、webhook、agent/applet handoff 以及等价的非 HTTP binding。

**Scheme allowlist（normative）**：出站网络目标策略 MUST 先按 **scheme 白名单** fail-closed。默认允许集**只含** `https`（`http` 仅在 §2.1 允许明文的本地开发 / 测试 / 受控内网场景下 MAY 加入），任何其它 scheme（`file`、`gopher`、`ftp`、`data`、`blob`、`dict`、`ldap`、`ws`、`wss` 以及任意未登记 scheme）MUST 直接拒绝（`policy_denied`），不得进入后续 host / IP 分类。理由：IP 分类只对基于网络 host 的 scheme 有意义；非网络 scheme 会整体旁路下面的 host/IP 判定，把 URL 解析变成本地文件读取或协议走私向量。scheme 判定 MUST 在 host 解析之前执行，并在每次 redirect / Alt-Svc / 协议升级改变 scheme 时重新判定。

通过 scheme 白名单后，默认策略 MUST fail closed，并至少拒绝下列地址类别：

- IPv4 loopback、unspecified、private、link-local、carrier-grade NAT、benchmark、protocol-assignment、TEST-NET、multicast、reserved 与 broadcast 地址段，包括 `0.0.0.0/8`、`10.0.0.0/8`、`100.64.0.0/10`、`127.0.0.0/8`、`169.254.0.0/16`、`172.16.0.0/12`、`192.0.0.0/24`（IETF Protocol Assignments）、`192.0.2.0/24`（TEST-NET-1）、`192.168.0.0/16`、`198.18.0.0/15`（benchmark）、`198.51.100.0/24`（TEST-NET-2）、`203.0.113.0/24`（TEST-NET-3）、`224.0.0.0/4`、`240.0.0.0/4` 和 `255.255.255.255/32`。
- IPv6 unspecified、loopback、IPv4-mapped private/loopback、unique-local、link-local、multicast 与 reserved 地址段，包括 `::/128`、`::1/128`、`::ffff:0:0/96` 中映射到上述禁止 IPv4 段的地址、`fc00::/7`、`fe80::/10` 和 `ff00::/8`。
- 用于承载 IPv4 的 IPv6 转换 / 隧道地址段，包括 `64:ff9b::/96`（NAT64 well-known prefix）、`2002::/16`（6to4）和 `2001::/32`（Teredo）。这些地址段内嵌 IPv4 目标，MUST 先解封内嵌的 IPv4 地址再按上述 IPv4 分类重新判定：NAT64 取低 32 bit、6to4 取 `2002:` 之后的 32 bit、Teredo 取末 32 bit（按位取反）作为映射的 IPv4 server/client 地址；解封后若命中任一禁止 IPv4 段（含 metadata endpoint）MUST fail closed 拒绝，不得仅因外层 IPv6 前缀未在简单 denylist 中而放行。部署 policy 登记的其它 NAT64 prefix（非 well-known）MUST 同等解封并重新分类。
- 云厂商或容器环境 metadata endpoint，包括 `169.254.169.254`、`169.254.170.2` 以及部署 policy 登记的等价 IPv6 / DNS metadata 名称。

执行规则：

- 服务 MUST 在连接前解析目标 host 的所有候选 A/AAAA 记录，并对实际选用的 IP 执行上述分类；不得只检查原始 URL 字符串或裸域名。
- DNS 解析结果 MUST 与连接目标绑定。连接建立、重试、HTTP redirect、Alt-Svc、proxy CONNECT 或协议升级改变目标 host/IP 时，MUST 重新执行策略检查。
- 对返回多个地址的域名，只要某次连接候选命中禁止地址类别，该候选 MUST 被拒绝；实现不得在策略命中后静默切换到另一个地址并把失败隐藏为普通网络波动。
- HTTP redirect 默认不得跨 trust domain 放宽策略。redirect 目标 MUST 重新校验 scheme、host、port、DID/service binding 和出站网络策略。
- 明文 HTTP 到公网目标默认 SHOULD 拒绝；仅本地开发、测试网络或 Realm / deployment policy 明确授权的受控内网例外可放行。
- 允许访问私网或 link-local 的例外 MUST 是显式 policy：绑定用途、service DID、trust domain、CIDR、端口、过期时间和审计要求。`development_mode=true` 的 loopback 例外不得出现在生产 ServiceDescribe 或 verified profile claim 中。
- 拒绝时 SHOULD 返回 `policy_denied`，并在仅对 operator 可见的审计细节中记录被拦截的地址类别、规范化 URL digest、解析 IP、调用用途和 policy version。已登记 operation（例如 `ak.open.mimi.command.proxy_download.v1`）在 wire 上承载该拒绝时 reason code 为 `egress_policy_denied`。公开错误不得泄露内网拓扑。
- **出站联邦 / 媒体 / snapshot fetch 的两层校验为合取（normative）**：出站联邦 push / pull / checkpoint probe、媒体抓取、以及 snapshot manifest / chunk fetch，MUST **同时**满足 (a) 本节 §11.2 的地址分类 fail-closed 检查，与 (b) [`federation.md` §3.4`](./federation.md) 的 federation peer policy（`deny` 先于 `allow` 评估，且 peer policy 只能收紧不能放宽地址分类）。两层是**合取**：任一层拒绝即 fail closed，不存在"地址分类通过即放行而跳过 peer policy"或"peer policy allow 即跳过地址分类"的旁路。snapshot manifest / chunk fetch 的目标 host（含 `chunks[].chunk_ref` 指向的 blob host、`realm_state_snapshot_bootstrap` 内的 endpoint）MUST 同样纳入这两层校验——既按 §11.2 做地址分类，也按 §3.4 peer policy 判定该 host / service DID 是否在出站允许集中；任一层拒绝即拒绝该 chunk fetch，不得静默退回未校验地址。

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
