---
title: HTTP/JSON Binding 通用约定
status: candidate
normative: true
stability: v1
updated: 2026-07-16
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

- request 与 response 的 `Content-Encoding` **MUST be absent**。服务端 MUST 在读取或解压 body 之前以 HTTP 415、`error_code=unsupported_content_encoding` 拒绝携带该 header 的请求；MUST NOT 复用 `invalid_param`（它固定映射 400）。cache / proxy MUST 设置适当 `no-transform`，MUST NOT 在中途压缩 response。
- 三层大小边界（完整 canonical Event 1 MiB、canonical operation body 8 MiB、HTTP message content wire bytes 16 MiB）、二维 count+bytes batch/page 算法与统一 `payload_too_large` 语义的唯一真源是 [`../conformance/scalability-constraints.md` §2.1](../conformance/scalability-constraints.md)。
- 请求处理 MUST 按 scalability-constraints §2.1.8 的顺序执行：header 边界 → 不需 body 的认证 → 拒绝 `Content-Encoding` → `Content-Length` 预检 → 边读边计 wire bytes → JSON parse → JCS 计数 → schema/operation 校验 → body-dependent proof/auth → handler。实现 MUST NOT 先完整缓存或解析 body 再判大小。
- streaming binding（NDJSON / SSE、Blob upload/download、Range、media transport、federation streaming）不套用 8 / 16 MiB 整体 body 上限，各自按 scalability-constraints §2.1.7 定义 per-frame / per-chunk / pending 上限。

### 2.4 Operation ID kind/action taxonomy

标准 `operation_id` 是跨 transport 的语义操作名，不是 HTTP method 的派生名。Operation ID MUST 使用可变长度前缀加固定末两段：

```text
ak.<surface>.<domain-or-subject...>.<kind>.<action>
```

`<kind>` MUST 取下表固定集合。`<action>` 是该 kind 内的业务动作，MUST 描述协议效果，不得为表达 transport binding 而采用只描述传输、不描述协议效果的纯 HTTP method 名称 `post` / `put` / `patch`。`get` / `delete` 作为 `resource` kind 下的 canonical action，描述的是读取 / 删除这一**协议效果**（其 HTTP method 由 `kind` 钉死，见下表），不在此限。

| kind | 语义边界 | HTTP/JSON binding 关系 |
| --- | --- | --- |
| `query` | 只读查询、解析、枚举、frontier/head/effective/viewer 投影、policy check。不得产生 server-side mutation。 | 通常 `GET`；复杂 selector、隐私敏感参数、批量解析或 proof body 可用 `POST`。 |
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
- `query.scan_body` 只允许作为 HTTP-only companion binding，MUST 声明 `binding_variant_of` 指向同语义的 canonical `query.scan` operation；非 HTTP transport MUST 使用 canonical operation，不得把 body variant 暴露为独立能力。

HTTP method 不是 operation action 的来源：同一 `query.scan` 语义可以有 GET query string 与 POST/body 两种 HTTP binding；这种情况必须标记为 binding variant，而不是发明新的协议操作。`ak.self.events.query.scan_body` 必须声明 `binding_variant_of="ak.self.events.query.scan"`，非 HTTP transport 仍使用 canonical `ak.self.events.query.scan`。

### 2.4.1 写操作的 durable effect 闭包（normative）

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
未登记 durable Event。该闭包由 `tools/lint_artifacts.py` 与
`operation-registry-coverage-fixture.json` 机械校验。

**`viewer` action（术语定义）**：`ak.self.account.query.viewer` 的含义钉死为：**当前已认证 holder 的主体自读投影**。目标不由 path / query 中的外部 id 定位，而由 holder-bound `user_session` 的会话绑定决定，故不建模为 `resource.get`；命名沿用 GraphQL 生态的 `viewer` 惯例（"viewer = 发起请求的已认证主体"）。它与 `query.describe`（服务能力元数据，可 pre-auth）的区分见 [`service-http-binding.md` §5.1](./service-http-binding.md)。注意区分本规范 prose 中 `viewer` 的另一用法：可见性 / 投影语境（pins、history visibility、conformance vector 的 `viewer_*` 字段）里的 "viewer" 指**正在读取内容、作为可见性评估视角的主体**，不是本 operation；`reviewer`（审核者）与两者均无关，全文检索 `viewer` 时勿混入。

### 2.5 HTTP method 语义

HTTP method 选择 MUST 服从资源语义，而不是简单照搬 `operation_id` 的最后一个词：

- `GET` / `HEAD`：只读、无 server-side mutation；可用 path/query 定位资源、projection 或分页读取位置。读取 cursor 不得触发队列删除或 ack。
- `POST`：提交 command、batch、proof、搜索/复杂查询 body、入队、fanout、创建服务端分配 id 的资源，或执行由签名/admission 决定效果的操作。每个写 operation MUST 在 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 声明 `idempotency_mechanism` / `retry_safe`；可自动重试的写入必须使用 `Idempotency-Key`、对象 id、request id、canonical hash 或 protocol sequence。确实无法提供稳定 identity 的 operation 只能声明 `none/false`，并 MUST 同时声明 §6 的机读 `uncertain_outcome`，不得让客户端猜测恢复路径。
- `PUT`：仅用于“客户端对一个已知 URI 表达完整目标表示或当前 slot 值”的创建/替换/设置。重复发送同一 URI 和同一表示 MUST 不产生额外副作用；同一 URI 上不同表示按该 slot 的覆盖、版本或 precondition 规则处理。
- `DELETE`：删除一个已知 URI 表示的资源、binding 或 slot；重复删除必须有定义良好的幂等结果。
- `PATCH`：仅在规范显式定义 patch document 语义、冲突检测和幂等边界时使用；否则 partial update 使用 `POST` command 或 `PUT` slot replacement。

因此，`ak.self.device_messages.command.send` 表示“把 to-device message 批次放入目标设备短期队列”，HTTP binding 必须是 `POST /_arkret/self/device_messages`，并以 `(sender, Idempotency-Key)` 去重：该操作没有单个由 URI 标识、可完整替换的消息资源；队列删除只由 `ak.self.device_messages.command.ack` 触发。相反，`ak.self.keys.backups.resource.replace`、`ak.self.realm_policy_server.resource.replace`、`ak.self.account_data.resource.replace` 和 `ak.self.agent.participation.resource.replace` 都有 path 标识的单一 backup/config/slot，HTTP binding MUST 使用 `PUT`。

## 3. 认证

受保护 endpoint 的请求 MUST 携带可验证且 sender-constrained 的认证材料。会话出示方式按下列**推荐序**选择（越靠前越优先）。生产 current-v1 受保护 endpoint MUST 要求 DPoP、RFC 9421 HTTP Message Signature、detached JWS、mTLS 或等价 proof-of-possession（PoP）绑定；裸 `Authorization: Bearer <ak.session.grant>` 只证明持有 token，不是合格的 current-v1 受保护 endpoint 会话出示。

1. **`session_public_key` PoP（RFC 9421 HTTP Message Signature）—— 推荐默认**：请求用 `ak.session.grant` 委托的短期 `session_public_key`（私钥仅持有方掌握）对请求做 HTTP Message Signature。会话凭据与签名密钥绑定，仅截获 `ak.session.grant` 不足以重放。详见 §3.2 与 [`service-http-binding.md` §2.5](./service-http-binding.md)。
2. **detached JWS request signature** 或等价 signed proof body：栈不便用 RFC 9421 时的等价 sender-constrained 出示。
3. **mTLS**：用于受控企业或服务间通信。
4. **`Authorization: Bearer <ak.session.grant>`（裸 bearer，仅可与 PoP 并存）**：可随 DPoP / RFC 9421 / JWS / mTLS 一起携带，用于让服务端定位 session grant；裸 bearer 本身不证明持有绑定密钥，凭据一旦泄露即可重放。生产 current-v1 受保护 endpoint MUST NOT 接受仅含裸 bearer 的请求作为认证成功。公开 metadata endpoint 若被定义为无需认证的 public surface，MAY 按未认证请求返回公开响应，但 MUST NOT 把裸 bearer 当作 session / capability 认证。

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
- 拒绝时 SHOULD 返回 `unauthenticated` 或 `invalid_param`，并且不得把 query 中的敏感值写入普通访问日志。
- `ak.self.blob.command.presign` 是唯一标准 URL bearer 例外：它只能是单 blob、单用途、短时效、只读、可撤销的派生 token，不得等同于用户 session、API key 或长期 capability；完整约束见 [`../crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)。
- 第三方邀请的 `#token=` fragment 是客户端 handoff，不是服务端认证入口。服务端不会收到 fragment；客户端读取后 MUST 通过 body / signed proof 提交 claim，并按 [`third-party-invites.md` §3.2](./third-party-invites.md) 清理 URL 与本地状态。
- online principal locator 的 `#token=` fragment 同样只是客户端 handoff。`locator_token` MUST 通过 `POST /_arkret/open/invite-locators/resolve` JSON body 提交；不得出现在 URL path 或 query string。详见 [`invite-addressing.md`](./invite-addressing.md)。

### 3.1 认证服务发现

认证与授权服务器可以分离。Principal Server 的 `/_arkret/describe` MUST 公布 `auth_metadata.account_authority` 与 `auth_metadata.methods[]`。客户端先用 `account_authority.gate_account_base` 定位所有客户端可见的 Arkret `/_arkret/gate/account/*` 操作，再按 `methods[]` 中的标准 discovery 找认证 provider；规范明确标记为部署内部 S2S 的 account 子操作（例如 `ak.gate.account.command.logout_auth_session`）只能由 Account Authority 按对应契约调用，不能由客户端派生。不得把 OAuth/OIDC subject 当作 Arkret principal：

```json
{
  "auth_metadata": {
    "account_authority": {
      "origin": "https://account.example",
      "gate_account_base": "https://account.example/_arkret/gate/account",
      "enrollment_authority_did": "did:key:z6MkenrollmentAuthority"
    },
    "methods": [
      {
        "method": "oidc",
        "issuer": "https://auth.example.com",
        "openid_configuration": "https://auth.example.com/.well-known/openid-configuration",
        "client_id": "ak.example-client",
        "scopes": ["openid", "profile"],
        "grant_exchange": {"proof_kind": "oidc_code_exchange"}
      },
      {
        "method": "passkey",
        "grant_exchange": {"proof_kind": "passkey_assertion"}
      }
    ],
    "did_binding_methods": ["session_grant", "did_http_signature"]
  }
}
```

规则：

- `sub`、email、username 或 OAuth client id MUST NOT 直接作为 `actor_id`、grant subject 或 event sender。
- 登录成功后，Account Authority MUST 产生可验证的 `SessionGrantOutcome`，把 OAuth/OIDC / passkey / device proof 绑定到 DID principal / device。客户端可见登录凭据是 `ak.session.grant`，Principal 本地 session provisioning 是 Account Authority 内部步骤。
- Resource server MUST 校验 token audience、issuer、expiry、nonce / replay 防护和 session grant 状态；Principal Server 校验 grant 时通过 Account Authority / Auth-side 内省或等价可信本地状态 fail closed。
- `methods[]` 只描述 service account 登录或恢复入口；它不改变 DID 控制权规则。密码、邮箱验证码、passkey 和 OIDC session 必须通过 `did_binding_methods` 绑定到 DID / device 后才能用于协议写入。
- 当 Account Authority 提供 [`../identity/account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 的 account-first 分支时，Principal Server 的部署配置 MUST 在 `account_authority.enrollment_authority_did` 公布 B 模型首设备入册权威 DID。客户端 MUST 把该值作为 entry 0 的部署 pin，并在调用 Account Authority `describe` 时校验其公布的同名值一致；不得直接采用待认证 Account Authority 响应中的 DID，也不得以 TOFU 替代部署声明。
- 当认证 metadata 变化时，服务 SHOULD 通过 feature discovery 版本或 DID service metadata hash 暴露变更，客户端不得静默沿用过期 issuer。

### 3.2 Sender-constrained（proof-of-possession）会话出示

`ak.session.grant` 已把短期 `session_public_key` 绑定到 principal / device / audience / origin（见 [`../crypto-media/device-lifecycle.md` §1 / §3](../crypto-media/device-lifecycle.md)）。若请求只用 `Authorization: Bearer <ak.session.grant>` 出示，凭据被窃即可在 audience 内重放，与 key 绑定设计脱节。按 [RFC 9700](https://www.rfc-editor.org/rfc/rfc9700)（OAuth 2.0 Security BCP, BCP 240）"优先使用 sender-constrained token" 的指导，Arkret v1 对生产受保护 endpoint 要求 PoP。

**生产 current-v1 PoP 要求（normative）**：

- `/_arkret/self/*` endpoint MUST 使用 §3.3 的 `Authorization: Bearer <ak.session.grant>` + DPoP 出示。该 bearer header 只是 DPoP 绑定的 grant 载体；缺少有效 DPoP proof 时 MUST 拒绝。
- 对常规写操作（任何推进 actor_seq / Realm frontier 或产生持久副作用的请求）与敏感读（成员列表、私有 projection、key backup、device list、moderation 队列等），实现 MUST 用 RFC 9421 HTTP Message Signature 或等价 sender-constrained proof 做会话出示；高安全 profile 进一步要求 RFC 9421 形态与 transcript/body 绑定。
- 对其它受保护 current-v1 endpoint，实现仍 MUST 要求 DPoP、RFC 9421 HTTP Message Signature、detached JWS、mTLS 或等价 sender-constrained proof。裸 `Authorization: Bearer <ak.session.grant>` MUST 以 `unauthenticated` 拒绝。
- 服务 SHOULD 通过 `auth_metadata.did_binding_methods` 公布支持的 sender-constrained 方法（如 `session_dpop`、`session_http_signature`），供客户端选择；未公布任何 sender-constrained 方法的服务 MUST NOT 声明通过 current-v1 production protected-endpoint conformance。
- 在 §11.2 之外，PoP 出示不改变 §3 其余规则：协议层权限判断仍 MUST 回到 actor DID / capability / Realm policy；PoP 只把"持有 token"升级为"持有绑定密钥"。

**PoP 出示形态（RFC 9421，与联邦面同栈）**：客户端用 `session_public_key` 对应私钥对请求签名，`Signature-Input` covered components 与联邦 service-to-service 出示对齐（见 [`federation.md` §3.2](./federation.md) 与 [`service-http-binding.md` §2.5](./service-http-binding.md)），至少覆盖：

- `@method`、`@target-uri`、`@authority`（绑定动词、目标 URI 与 host，防止跨 endpoint / 跨 host 复用）；
- `content-digest`（带 body 的请求必填；exact HTTP content bytes、canonical JSON 要求、RFC 9530 唯一 `sha-256` token 与验签前校验顺序遵循 [`service-http-binding.md` §2.5.1](./service-http-binding.md)）；
- 关键 header：`Idempotency-Key`（若参与幂等 / replay key）、`X-Arkret-Wait-For`（若出现）；
- 签名 parameters MUST 包含 `created` 与 `expires`（不得用 `Date` 替代）。

与 session key 的绑定：签名 `kid` MUST 指向当前 `ak.session.grant` 委托的 `session_public_key`，且该 grant 的 principal / device / audience / origin 约束 MUST 与请求一致；grant 已撤销、过期或 audience / origin 不匹配时，服务端 MUST 拒绝（`unauthenticated`）。

Replay window：PoP 出示**复用既有 replay window 机制**——签名时效窗口与联邦面同口径（`expires - created` 上限、`created` 与本地时钟偏差上限，量级见 [`encoding.md` §6](../conformance/encoding.md) 与 [`federation.md` §3.2](./federation.md) 签名时效窗口），过窗签名即使 replay cache 已 evict 也 MUST 因 `created` / `expires` 校验失败而拒绝；幂等 / replay key 复用 §6 与 `Idempotency-Key` 机制。

公开 metadata surface：若 endpoint 明确被定义为无需认证的 public surface（例如公开 describe 的 public metadata 子集），服务 MAY 在无认证材料或只有裸 bearer 的情况下返回公开响应；该响应 MUST 按未认证请求处理，不得授予 session / capability 语义，不得返回调用者私有 projection、自身 viewer 字段或任何依赖 session grant 的数据。若同一 endpoint 需要返回已认证视图，调用方 MUST 使用 DPoP / PoP / mTLS 绑定；裸 bearer 仍 MUST 被拒绝。

### 3.3 `/_arkret/self/*` 出示 grant + DPoP（normative，默认会话凭据路径）

Account Authority 以 `ak.session.grant` 作为客户端唯一可见的会话凭据；Principal Server **不**为客户端铸发独立的本地 bearer，**不**存在第二个客户端可见的 Principal 本地凭据签发 endpoint。客户端对 `/_arkret/self/*` 的每次请求 MUST 直接出示该 grant，并叠加一份 sender-constrained 的 **DPoP（[RFC 9449](https://www.rfc-editor.org/rfc/rfc9449)）** 持有证明：

```http
POST /_arkret/self/events
Authorization: Bearer <ak.session.grant>
DPoP: <DPoP proof JWT>
```

Principal Server 对每次 `/_arkret/self/*` 请求 MUST 校验（任一项失败即 `unauthenticated`，fail closed）：

- **DPoP 签名**:DPoP proof JWT MUST 用该 grant 的 grant-binding(DPoP)key 签名，其公钥 JWK thumbprint（[RFC 7638](https://www.rfc-editor.org/rfc/rfc7638)）MUST 等于 grant 的 `cnf.jkt`(Principal Server 通过 session-grant 内省取得 `cnf_jkt`,见 §3.1 与下文)。
- **DPoP 绑定声明**:`htm` MUST 等于请求方法、`htu` MUST 等于请求 URL、`ath` MUST 等于所出示 grant 的 hash;这些把该 proof 钉死到「本方法 + 本 URL + 本 grant」,防跨 endpoint / 跨 grant 复用。`htu` 比对遵循 [RFC 9449](https://www.rfc-editor.org/rfc/rfc9449) §4.3,先剥离 query 与 fragment，再逐字比较经规范化的 scheme + authority + path。**外部 URI 重建**:`htu` 的 authority 是客户端看到的 gate origin。直连部署 MUST 使用请求自身的 scheme 与 authority；反向代理部署 MUST 使用静态配置的 public origin，或仅接受由受信最后一跳代理写入、并在入口清洗所有客户端同名 header 后得到的 `Forwarded` / `X-Forwarded-Host` / `X-Forwarded-Proto`。实现不得信任任意首跳转发值，也不得退化为 path-only 比对；无法可靠重建完整外部 URI 时 MUST 以 `unauthenticated` 拒绝 DPoP 出示。
- **grant active**:grant MUST 经 session-grant 内省判定 active(`ak.gate.account.command.introspect_session_grant`)。Principal Server **MAY** 缓存内省结果，但 TTL **SHOULD ≤ 120s**；对敏感操作 MUST 旁路缓存、强制重新内省(吊销生效上界即缓存 TTL，见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md))。内省的 `proof` 字段是部署内部 S2S 的可选附加确认；默认 self-path 客户端只发送本节的 `Authorization` + `DPoP`，Principal Server MUST 依据内省返回的 `cnf_jkt` 在本地校验该请求的 DPoP，不得要求客户端再发送额外的 session-grant introspection proof header。
- **grant class/binding**：JWT 与内省必须使用
  `service-operation-dtos.schema.json#/$defs/SignedSessionGrantClaims` 的 typed
  `credential_class`。`recovery_restricted` 只允许 recovery bootstrap scope，必须携带
  `recovery_binding` 且不得携带 `standard.holder_binding`。`standard.holder_binding` 在 JWT 与 introspection
  共用同一 closed discriminated XOR wire：human 分支恰为
  `{kind="human_device",device_binding}`，并禁止全部 Agent runtime字段；Agent分支恰为
  `{kind="agent_runtime",agent_id,device_id,agent_key_authorization_ref,verification_method}`，并禁止
  `device_binding`。`agent_key_authorization_ref`就是唯一 authorization代次，必须 resolve为 current accepted
  active authorization，不存在额外 `generation`字段或隐式数据库 generation轴。Principal Server 在每个
  self-path admission 中必须同时重验 token subject、分支 binding ref、runtime device、current accepted Agent
  key authorization及 Agent/controller current lifecycle；仅匹配 kind、key digest、scope内 device字符串或
  service-private row均不得替代 signed binding。持 active authorized Agent key但尚无 session的 runtime可凭 PoP
  取得 standard Agent session，不能伪装 human device。
- **audience**:grant 的 audience MUST 等于本 Principal Server 的 service DID。
- **scope**:grant scope MUST 含 Principal Server 的 session.bind scope 与 device scope。
- **principal / device 绑定**:grant 绑定的 principal / device MUST 与请求一致。
- **未过期**:grant 与 DPoP proof 均 MUST 未过期。
- **DPoP 重放防护**:Principal Server MUST 按 DPoP `jti` + `iat` 新鲜度窗口拒绝重放(窗口量级与 §3.2 / `federation.md` §3.2 PoP 时效窗口同口径)。

实现 MUST 通过 `ak.vector.session.dpop_target_uri_binding.v1`，证明跨 authority、跨 scheme、伪造转发头与 authority 不可重建场景均 fail closed，且不存在 path-only fallback。

**DPoP 与 RFC 9421 PoP 是两层正交保障**。DPoP（RFC 9449）提供 per-request 认证 + sender-constraint,但**不绑定请求 body**——默认 profile 下 body 完整性依赖 TLS(与 Matrix 同口径)。§3.2 的 RFC 9421 PoP 则额外提供 body 完整性(覆盖 `content-digest`)。两层用**同一把** Ed25519 grant-binding(DPoP)key:该 key 的 RFC 7638 thumbprint 即 grant 的 `cnf.jkt`(DPoP 绑定),其公钥即 grant 委托的 `session_public_key`(9421 绑定),客户端无需为 DPoP 与 9421 各管理一把密钥。此 grant-binding key 是短期会话认证凭据，必须独立生成、独立存储并随 session 轮换；其私钥字节、公钥字节、JWK thumbprint 与 `kid` 都 MUST NOT 等于或复用签事件 / KeyPackage / MLS 的长期设备身份 key(`device_public_key`)。违反分离要求的请求 MUST 以 `unauthenticated` fail closed(见 [`../crypto-media/device-lifecycle.md` §3.3/§5.2](../crypto-media/device-lifecycle.md))。

- **默认 profile**:self-path 的会话出示就是本节的 grant + DPoP;RFC 9421 PoP 可选叠加。
- **高安全 profile**(`sovereign_deployment` / `high_security_organization`,见 §3.2 末段):对常规写与敏感读,Principal Server **MUST** 在 grant + DPoP 之外**再要求** RFC 9421 PoP 出示(获取 body 完整性);仅出示 grant + DPoP、缺 `Signature-Input` 的写 / 敏感读 MUST 被拒。此时 9421 校验的 `session_public_key` **MUST** 取自该 grant 的 session-grant 内省结果(grant + DPoP 会话为请求级、不落库为本地 bearer),而非持久化 session 记录。

该模型对齐 Matrix [MSC3861](https://github.com/matrix-org/matrix-spec-proposals/pull/3861)（Auth Server 签发凭据 + Resource Server 内省）的方向，并在其上叠加 DPoP sender-constraining(比 Matrix 的裸 bearer 更强)。

**其它仍合法的入站凭据**:除 grant + DPoP 外，Principal Server MAY 在 development mode 保留本地开发凭据回退；生产客户端默认且规范化的 self-path 出示路径是 grant + DPoP。Auth Server 的 OIDC/OAuth 结果 MUST 先进入 Account Authority 的 `SessionGrantOutcome`，不得作为 Principal Server 的 self-path 直接凭据。

### 3.4 Account handoff + DPoP（normative，pre-registration 路径）

[`account-lifecycle.md` §2.1.2](../identity/account-lifecycle.md) 的 `account_handoff_grant` 是 Account Authority 的临时 sender-constrained 凭据，不是 `ak.session.grant` 或 OAuth bearer。创建 handoff 时尚无 credential 可计算 `ath`：客户端对 `POST /_arkret/gate/account/authentication-handoffs` 发送不带 Authorization 的 DPoP proof，proof JWT header 中的 public JWK 建立候选 holder；该 JWK MUST 是 Ed25519，body `AccountHandoffAuthenticationProof.signature` MUST 由同一 key 按 canonical schema transcript 签名。Account Authority 必须验证两处 key 一致后，才把其 RFC 7638 thumbprint写入 handoff `cnf.jkt`。

后续 challenge、register 与 `proof_kind="pre_registration_handoff"` session-grant 请求使用：

```http
POST /_arkret/gate/account/identity-binding-challenges
Authorization: DPoP <account_handoff_grant>
DPoP: <DPoP proof JWT>
```

Account Authority MUST 验证 DPoP signature key thumbprint 等于 handoff `cnf.jkt`，`htm` / `htu` 精确绑定当前 method 与外部完整 endpoint URI，`ath` 等于所出示 handoff 的 hash，`jti` 未使用，`iat` 在新鲜度窗口内，handoff 未过期/撤销且当前 operation 位于其闭合 `allowed_operations`。外部 URI 重建与受信代理规则完全复用 §3.3；不得 path-only 比对。任一失败均 `unauthenticated` 或该 operation 登记的 `proof_invalid`，且不得进入 lease、challenge、DID publish、binding 或 grant 副作用。

DPoP 本身不覆盖 request body。`create_handoff` 的 body 完整性由上述 holder signature覆盖；`register(identity_creation)` 的身份关键字段由 root-signed control proof 与 reserved operation digest覆盖。高安全部署 MAY 额外要求 §3.2 RFC 9421 `content-digest`，但不得因此省略 DPoP holder 校验或 root control proof。

## 4. 标准响应 envelope

**v1 现状（normative）**：成功响应 MUST 直接返回 endpoint-specific JSON 对象（字段集由对应 endpoint 在 `service-http-binding.md` §2.3 / §2.4 与 `contract-registry.json` 定义）；每个 operation MUST 在 `contract-registry.json#operation_registry.operations[].success_shape_kind` 声明机器可读成功形态，供 SDK / conformance 工具判定。**不存在跨 endpoint 强制的统一 success envelope**。错误响应 MUST 使用 §5 的统一错误 envelope (`{"ok": false, "error": {...}}`)，但成功响应没有等价的"包裹后再返回"模式。

各 endpoint 当前实际使用的成功标记形态可分为三类，调用方应直接按 endpoint 文档判定：

- **`{ok: true, ...payload}`** — 简单 mutation (push / self.device_messages.command.send / applet.transactions / 等)；
- **`{status: enum, ...payload}`** — 批量提交语义复杂时 (self.events.command.submit `status ∈ {accepted, duplicate, partial}`、self.keys.backups.resource.replace `status ∈ {accepted, duplicate}`)；
- **裸字段直接返回** — 创建 / 解析类 (self.blob.upload.create `{blob_ref, size_bytes, ...}`、find.directory.command.announce `{announce_id, indexed_at, ...}`、account session grant 等)。

新增 endpoint SHOULD 按下列分类选择成功形态:
- 简单 idempotent mutation 默认走 `{ok: true, ...payload}`；
- 批量 / 多结果路径走 `{status, accepted[], rejected[], ...}`；
- 创建 / 解析类直接返回构造好的对象，不另加包裹。

`ok` 是简单 mutation 的唯一通用成功 discriminator。`deleted`、`accepted` 等字段只有在某个 operation 的 typed response schema 把它们定义为独立业务状态时才可出现，MUST NOT 与 `ok` 互换；客户端与服务端不得为同一 operation 实现双读或别名输出。

流式 endpoint MAY 使用 newline-delimited JSON、SSE 或 WebSocket frame，但每个 frame 仍 SHOULD 是独立 JSON 对象。`request_id` 字段（若返回）SHOULD 与请求侧的 idempotency / tracing id 对齐，但不作为 success/failure discriminator。成功建立的 subscribe stream 若需要指示客户端延迟重连，MUST 使用 control frame 上的 `reconnect_after_ms`；`retry_after_ms` 保留给错误响应、非 HTTP binding 的失败诊断或显式 retry 语义。

## 5. 标准错误响应

错误响应 MUST 使用统一 JSON 格式：

```json
{
  "ok": false,
  "error": {
    "code": "capability_denied",
    "message": "actor does not have ak.strand.update on this strand",
    "retry_after_ms": null,
    "details": {}
  },
  "request_id": "ak:request:01964137-0000-7000-8000-000000000000"
}
```

`message` 用于开发者诊断，不应用于稳定程序逻辑。
客户端 MUST 以 `code` 作为主要错误分类。

**RFC 9457 problem+json 可协商投影（normative）.** 默认错误 wire 仍是上文的 `{ok: false, error: {...}}` 形态，**不变**。在此之上，本规范定义一个与 [RFC 9457 problem+json](https://www.rfc-editor.org/rfc/rfc9457) 对齐的、可经 content negotiation 协商的标准错误投影：

- 支持 HTTP binding 的 server 在请求携带 `Accept: application/problem+json` 时 **MUST** 返回符合 RFC 9457 的 problem 对象，并 **MUST** 设置 `Content-Type: application/problem+json`。该 problem 对象的字段由默认错误形态确定性映射而来：`error.code → type`（`type` MAY 为 URN 或相对 URI 形式的 type 标识）、`error.message → detail`、HTTP status → `status`、`request_id → instance`；server MAY 额外附带 `title`。
- 不支持 HTTP binding，或客户端未通过 `Accept` 协商该 media type 时，server **MUST** 维持默认 `{ok: false, error: {...}}` 形态，不得改变默认 wire。
- 该投影是默认形态之上的确定性 content-negotiation 对齐，不引入新的错误码命名空间：`type` 承载的仍是 §5.1 标准 `error.code` 字符串，客户端 MUST 以其作为主要错误分类，`detail` 仅用于开发者诊断，不应用于稳定程序逻辑。

### 5.1 标准错误码

标准 `error.code` 与批处理/联邦响应中的逐项 `reason_code` 共享同一字符串命名空间。**Canonical 单一来源** 是 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)：所有标准 code、HTTP 状态、scope (`response` / `endpoint` / `both`) 与简短描述均以该 registry 为准。新增、修改或删除代码 MUST 先更新 registry；本文与 `service-http-binding.md` §9 只引用该 registry，不维护并行表格。

实现使用要点（registry 之外的语义协议）：

- 错误语义必须使用单一标准 code。若请求体过大使用 `payload_too_large` / 413；若配额策略拒绝使用 `quota_exceeded` / 403。
- `stale_frontier` / 409 表示服务可用但本地因果前沿落后，客户端可等待或 backfill；服务故障、维护或无法追赶 frontier 时使用 `temporarily_unavailable` / 503 并 SHOULD 返回 `Retry-After`。
- 格式错误的 cursor 使用 `invalid_param` / 400；格式正确但已过期的 cursor 使用 `cursor_expired` / 410。
- `unsupported_feature` 用于 `Event.requirements.features[]` 与 `requirements.critical_extensions[]` 中出现该实现未声明支持的 feature 标识；`unsupported_event_kind` 用于该实现声明 profile 不接收的 active 标准 `ak.*` Event kind。二者不得互相替代。
- `conflict` / 409 是抽象 base code；实现 SHOULD 返回 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 中 `http_status=409` 的更精确 code。本文不维护并行穷尽清单；示例包括 `cas_conflict`、`causal_conflict`、`dependency_missing`、`duplicate_conflict`、`stale_frontier`、`state_mismatch`。
- 加密 envelope 相关 422 子 code（`aad_digest_mismatch` / `payload_digest_mismatch`）见 `crypto-media/encryption-and-audit.md` §2.3.4。

CI（`tools/artifact_pipeline.py check`）MUST 校验仓库内所有出现的字面 error code 字符串都登记在 registry 中，并 MUST 校验 `operations-error-mapping.json` 的 `rules.universal_codes` 与每个 `operations[].operation_specific[]` 不引用 registry 外的 code。

### 5.2 未知路径与错误方法

对 `/_arkret/*` 之下的请求，服务端 MUST 使用统一错误响应，不得返回 HTML、纯文本框架错误或实现栈信息。

规则：

- 未声明或未实现的路径 MUST 返回 HTTP `404` 与错误码 `unrecognized_endpoint`。
- 已知路径但 HTTP method 不受支持时 MUST 返回 HTTP `405` 与错误码 `method_not_allowed`，并 SHOULD 设置 `Allow` header。
- 这两类请求 MUST 在路由层终止，不得进入业务逻辑、写入队列、触发昂贵解析或产生可观察副作用。
- 客户端和联邦对端 MUST 使用 `describe.supported_operations`、OpenAPI 文档和 feature discovery 判断 endpoint 是否可用，不得根据非标准 404 body 做能力推断。

## 6. 幂等

请求级幂等行为的 active 认证入口是 `ak.vector.api.request_idempotency.v1`（`protocol-edge-cases-fixture.json`）；runner MUST 覆盖同键同 body、同键异 body、跨 principal/operation 复用、`canonical_hash_input` 指针和 24 小时保留临界点。

每个写接口 MUST 在 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 中声明幂等机制与重试安全性。只有 `retry_safe=true` 的 operation 承诺可对逐字节相同的完整请求执行自动幂等重试；`retry_safe=false` 的 operation 不作该承诺，客户端必须走 operation-specific outcome 查询、恢复流程或人工确认。

`retry_safe=true` 且 `idempotency_mechanism != "none"` 的写入请求 MUST 携带或内生由 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 同行声明的稳定 request identity；`retry_safe=false` 的 operation 仅在其 registry 行声明了对应机制时才使用该机制。少数使用 command binding 但语义为纯计算 / 只读判定的 operation MAY 声明 `none/true`，前提是任何重复执行都不持久化状态、不消费一次性材料且不产生外部副作用。

**机读真相源（normative）**：每个 operation 实际采用哪种幂等机制（§2.5 所列 `idempotency_key` / `object_id` / `request_id` / `canonical_hash` / `protocol_sequence`），以 operation registry 的 `idempotency_mechanism` 字段为准；配套 `retry_safe` 布尔字段声明"逐字节相同的全量重试是否不产生重复副作用"（`true` = 重试返回原 outcome、等价幂等 no-op 或确定性冲突；`false` = 盲目重试可能重复副作用或消费一次性材料）。客户端 MUST NOT 对 `retry_safe=false` 的 operation 在未带外确认首次请求效果的情况下自动重试。

`canonical_hash` 的默认 identity 是 `sha256:` 加 `canonical_json(完整请求体)` 的小写十六进制摘要，去重作用域是 `(authenticated principal, operation_id, canonical_hash)`。若 operation registry 同行声明 `canonical_hash_input`，其值 MUST 是 RFC 6901 JSON Pointer；接收方以该 pointer 选中的值计算 identity，同时仍须保存完整请求体的 canonical hash。同一 identity 对应不同完整请求体 MUST 返回 `duplicate_conflict`。因此 pointer 只能指向内容派生且协议定义为稳定身份的字段，不能把可碰撞的客户端标签当成内容摘要。

对请求级 identity 机制（`idempotency_key` / `request_id` / `canonical_hash`，以及以 `event_id` 作为 request identity 的事件提交）适用以下规则。self 面的 `Idempotency-Key` 去重作用域 MUST 至少绑定 `(authenticated principal, operation_id, Idempotency-Key)`；不同 principal 或不同 operation 复用同一字符串不构成重复：

- 相同幂等键 + 相同 canonical request body MUST 返回与首次请求语义等价的结果。
- 相同幂等键 + 不同 canonical request body MUST 返回 `duplicate_conflict`。
- 服务端 SHOULD 记录 request identity 与完整 canonical request hash；联邦与服务间写入 MUST 将完整 hash 纳入签名 transcript 或 transaction replay cache。
- `object_id` 与 `protocol_sequence` 通常是资源/协议状态 identity，不是请求级幂等键。逐字节相同的合法重放按 registry 的 `retry_safe` 承诺返回原 outcome 或等价 no-op；同一对象或序列上的不同 canonical body 通常是普通后继写，受 CAS、frontier、版本或状态机规则约束。**Event identity 例外**：`ak.self.events.command.submit` 与 `ak.peer.events.command.submit` 虽登记为 `protocol_sequence`，但 `event_id` 是 immutable content identity；同一 `event_id` 对应不同 canonical Event bytes MUST 返回 `duplicate_conflict` 并按 operations-sync §12 / federation §4.3 处置，不得当作后继写。
- `idempotency_mechanism="none"` 与 `retry_safe=false` 同时出现时，该 operation MUST 在 binding 文档中给出超时后的 outcome 查询、一次性材料重新签发或人工确认路径；客户端 MUST NOT 把传输失败解释为“服务端未执行”并盲目重放。`none/true` 只表示重复执行纯计算等价，不产生需要去重的 write outcome。

上述恢复路径的机读真相源是 operation registry 同行 `uncertain_outcome`：`query_operation` 必须引用 outcome/read operation；`reissue_material` 必须引用重新签发入口并要求 fresh request identity；`revoke_then_reissue` 必须分别引用幂等 revoke 与 fresh-material issue operation，并要求 fresh request identity，客户端只有在 revoke 已达可确认终态后才可 issue；`manual_confirmation` 明确进入 uncertain 人工确认；`drop_unconfirmed` 仅允许不持久化、可安全丢弃的 ephemeral/fanout signal。`none/false` 缺该字段、引用未知 operation、或任何重新签发策略未要求 fresh identity 时，artifact lint MUST 失败。

### 6.1 幂等记录保留窗口（normative）

- 对请求级 identity 机制的 operation，接收方 MUST 自幂等记录创建时刻起保留该记录**至少 24 小时**。`object_id` / `protocol_sequence` 的状态保留由对象生命周期或协议状态机决定，不受本段请求去重记录窗口约束。
- 该保留窗口 MUST ≥ 对应请求面的签名时效 replay window（`expires - created` 上限，见 §3.2 与 [`federation.md` §3.2](./federation.md)）加最大允许时钟偏移。
- 保留窗口内，同一请求级幂等键 + 相同 canonical request body 的重放 MUST 返回与首次请求语义等价的原 outcome；同一请求级幂等键 + 不同 canonical request body 仍按本节上文规则返回 `duplicate_conflict`。
- 保留窗口过后的重放行为由实现自定（MAY 按新请求处理或拒绝），但实现 MUST NOT 对窗口外的重放声称幂等保证。
- 在 24 小时下限之上，服务端 SHOULD 记录幂等结果至少到相关 Event 被最终同步或过期。

Applet transaction push 的幂等记录（[`applet-integration.md` §7.3](../extensions/applet-integration.md)）与联邦幂等 / replay cache（[`federation.md` §8.5](./federation.md)）都遵循本节保留窗口，不另行定义更短窗口。

### 6.2 客户端重试义务（normative）

- **安全全量重试同 identity**：仅当 registry 声明 `retry_safe=true` 时，语义上同一请求的全量重试才允许自动执行。若 `idempotency_mechanism != "none"`，重试 MUST 复用同一稳定 request identity（`Idempotency-Key` / `event_id` / `request_id` / object id / canonical hash / protocol sequence），且 canonical form 的 request body MUST 逐字节相同；若为纯计算 `none/true`，请求体仍 MUST 逐字节相同，但不虚构 idempotency key。
- **不安全 operation 禁止自动重放**：`retry_safe=false` 时，客户端 MUST NOT 自动全量重试；必须先执行该 operation 的 outcome 查询或恢复流程。若没有机器可调用的恢复路径，调用方只能把结果标为 uncertain 并请求人工确认，不能生成新的 key 盲目再发。
- **改内容必换 request key**：采用请求级 identity 的请求修改内容后重交 MUST 换新幂等键，MUST NOT 以旧幂等键携带新 canonical body 重交（服务端按上文规则返回 `duplicate_conflict`）。`object_id` / `protocol_sequence` 不适用本条。
- **federation submit 收到响应后是新求值**：`ak.peer.events.command.submit` 的调用方只有在完全未收到响应、首次结果不确定时，才把逐字节相同的 transport retry 视为上文“安全全量重试”并复用原 `Idempotency-Key`。一旦收到任何 submit 响应，该 key 即终结；按 `accepted[] ∪ duplicate[]` 求差重组的 partial retry、依赖补齐后的同 body 重求值以及原子 `dependency_missing` 后的重交都 MUST 使用新的 `Idempotency-Key`（或省略），见 [`federation.md` §4.1](./federation.md)。接收方仍可按 [`federation.md` §8.5](./federation.md) 对旧 key + 相同 canonical hash 返回旧幂等 outcome，但调用方不得把该 cache hit 当作依赖补齐后的新求值。

## 7. Cursor（统一不透明 token）

> **Scope（normative）**：本节只定义 cursor 在 HTTP/JSON binding 上的**使用契约**——出现位置、`purpose` 语义、分页方向（`before` / `after` / `prev_cursor` / `next_cursor`）与不透明性约束;cursor 的内部 canonical 结构、字段 schema、编码与 TTL 硬上限数值见 [`encoding.md` §8](../conformance/encoding.md)。

Arkret v1 在所有需要不透明 token 的位置使用**单一** `cursor` 类型，wire 形态固定为 `ak:cursor:<base64url(canonical_json)>`，schema 见 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json)。它统一承担增量同步、列表分页和写后读屏障所有用途。

cursor 内部包含一个 `purpose` 字段（客户端不解析；仅供 issuing 服务自检）：

| `purpose` | 用途 | 出现位置 |
| --- | --- | --- |
| `stream` | 增量同步 / 列表分页的位置承诺。回传方向取决于出现位置（见右列），并非任意位置都支持全部四向。 | **account 聚合流**：`/_arkret/self/account/subscribe` frame 的 `cursor` **仅**作为重连 `after=` 参数回传，是单向 catch-up 起点，**不支持** `before` / `prev_cursor`（account stream 不可反向，见本文 §7.0 与 [`client-sync.md` §2](./client-sync.md)）。**Realm timeline / 列表分页 / 查询**：`timeline.prev_cursor` / `next_cursor`、列表分页 `prev_cursor` / `next_cursor`、`ak.self.events.query.scan` 与 federation peer `ak.peer.events.query.scan`（`GET /_arkret/peer/events?before=<cursor>`）的 `before` / `after` 请求参数与 `prev_cursor` / `next_cursor` 响应字段——这些位置才支持 `before` / `prev_cursor` 反向延续。 |
| `barrier` | 读己之所写（RYW）：要求 reader 在 frontier 覆盖某个具体 event 之前不返回结果。 | 写接口响应中的 `cursor` 字段、`X-Arkret-Wait-For` header。 |

### 7.0 `prev_cursor` / `next_cursor` 含义（绝对方向）

任何返回 cursor 对的响应（`ak.self.events.query.scan`、列表分页等）使用统一的**绝对方向**约定；`/_arkret/self/account/subscribe` frame 只返回单个 account stream cursor,用于下一次 `after=` 重连：

| 响应字段 | 含义 | 回传给下一次请求 |
| --- | --- | --- |
| `prev_cursor` | 朝**更旧事件 / 更早历史**方向的延续位置 | `ak.self.events.query.scan` 的 `before=` 参数；分页 `before=<prev_cursor>` 取更旧一批 |
| `next_cursor` | 朝**更新事件 / 更晚未来**方向的延续位置 | `ak.self.events.query.scan` 的 `after=` 参数；分页 `after=<next_cursor>` 取更新一批 |

绝对方向与请求时所用的参数（`before` / `after` / `order`）和 selector 无关；服务端 MUST 始终按上述含义填充。客户端因此**不**需要记录"上一次请求的 direction"才能正确解释响应 cursor。

HTTP/JSON binding 的 cursor purpose 位置一致性如下：`purpose=stream` 的 cursor 只可出现在 stream / pagination context（例如 `/_arkret/self/account/subscribe` 的 `after=`、`ak.self.events.query.scan` 的 `before` / `after`、响应 `prev_cursor` / `next_cursor`）；`purpose=barrier` 的 cursor 只可出现在本文 §8 定义的 RYW barrier context（写接口响应中的 barrier `cursor` 字段、`X-Arkret-Wait-For` header 或等价投影）。任一 context 收到不匹配的 `purpose` 时，服务端 MUST 返回 `invalid_param`。

规则：

- 客户端 MUST 把 cursor 当作不透明字符串，禁止解析以推断排序、权限或服务身份。
- 任何接受 cursor 的接口 MUST 把无效 cursor 返回 `invalid_param`，把已过期 cursor 返回 `cursor_expired`。
- 同一字符串 cursor 在不同 issuing 服务间不可移植；跨服务复用 MUST `invalid_param`。
- TTL 硬上限：barrier cursor 与 stream cursor 的 `expires_at - issued_at` 硬上限的**唯一 canonical 数值定义点**见 [`encoding.md` §8.3 规则 9](../conformance/encoding.md)；本节不重复字面毫秒数值。
- 声明 `cursor_revoke_high_assurance` feature 的服务必须实现 [`client-sync.md` §12.2.1](./client-sync.md) 的 revocation set。已撤销但仍在 TTL 内的 cursor MUST 返回 `cursor_revoked`；完整性失败仍返回 `cursor_integrity_invalid`，不得泄露 revocation set。
- 声明 `events_query_range_completeness` feature 的服务必须实现 [`service-http-binding.md` §3.3.6](./service-http-binding.md)：`ak.self.events.query.scan` 接受 `include_completeness=true` 并返回覆盖该页范围的 `ak.attestation.range_completeness` 引用。未声明该 feature 的服务 MUST 忽略 `include_completeness` 参数。

### 7.1 列表分页（normative）

所有列表接口 MUST 返回三个字段：

```json
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
- **MUST NOT** 使用通用占位 `items[]`，也不得使用 `events[]` 作为非 Event 数组的字段名（device_messages 与 account subscribe `to_device` 的 `messages[]` 例外见 `ak.self.device_messages.query.list` 与 `ak.self.account.stream.subscribe`）。

**`next_cursor` / `has_more`** (normative)：
- `next_cursor` 是 optional：缺省表示当前批次已经是末尾。
- `has_more: boolean` MUST 出现：客户端 MUST 仅按 `has_more` 决定是否继续翻页；不得仅靠 `next_cursor` 是否存在做判断（实现可能在末尾仍返回 `next_cursor` 用作 long-poll resume token）。

本小节的三字段合同适用于资源列表接口，不适用于双向 Event range scan。
`ak.self.events.query.scan` / `ak.peer.events.query.scan` 按绝对方向分别返回
`has_more_before` 与 `has_more_after`：沿 `before=<prev_cursor>` 补更旧历史时只看
`has_more_before`，沿 `after=<next_cursor>` 追更新事件时只看 `has_more_after`。scan client
不得把其中任一字段重命名为通用 `has_more`，也不得在向后补历史时用
`has_more_after` 作为终止判据。

**`prev_cursor`**（可选, 双向分页）：仅当接口支持向"更旧"方向翻页时返回。详见 §7.0；不支持双向翻页的接口 MUST NOT 返回 `prev_cursor`。

**Cursor 方向参数** (`before` / `after`)：见 [`service-http-binding.md` §3.3](./service-http-binding.md) 与本文 §7.0。`before` / `after` 是绝对时间方向（朝更旧 / 朝更新），与响应 `prev_cursor` / `next_cursor` 形成一一对应；所有 v1 接口（包括 `ak.self.device_messages.query.list`）MUST 使用这两个方向名，不得引入 `from=` / `start_at=` 等同义别名。

服务端 MAY 对 `limit` 设置上限。超过上限时 SHOULD 使用最大允许值或返回 `invalid_param`。

## 8. 读己之所写

写接口成功后 SHOULD 在响应中返回一个 barrier cursor：

```json
{
  "status": "accepted",
  "event_id": "ak:event:019640ed-8000-7000-8000-000000000000",
  "cursor": "ak:cursor:..."
}
```

该 cursor 的 server-side handle 绑定到刚提交事件：`purpose=barrier`，`target.event_id` 与 `target.event_digest` 由 issuing server 通过 handle 解析；`target` 不出现在 cursor wire body 中。后续读接口 SHOULD 接受：

```text
X-Arkret-Wait-For: <cursor>
```

如果服务在超时前到达该 cursor 描述的 causal frontier，则返回正常结果；否则 SHOULD 返回 `temporarily_unavailable` 或 `timeout`，并附带当前 frontier。stream cursor 不得用于 wait-for header；服务端遇到 `purpose=stream` 的 cursor 出现在 wait-for 上下文 MUST 返回 `invalid_param`。

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

```json
{
  "retry_after_ms": 2000
}
```

HTTP response MUST 同时设置 `Retry-After` header。`Retry-After` 的值按 HTTP 标准使用秒数或 HTTP date；若同时存在 `Retry-After` 与 `retry_after_ms`，客户端 MUST 优先使用 `Retry-After`。

**超长 `Retry-After` 与客户端重试预算（normative）**：当 `Retry-After` 指示的等待时长超出客户端自身的重试预算 / 退避上限时，客户端 MAY 放弃该请求并向上层报告失败；但只要选择继续重试，就 MUST NOT 早于 `Retry-After` 指示的时刻重试同一请求——不得把超长 `Retry-After` 按本地退避上限截断（clamp）后提前重试。

规则：

- `429 rate_limited` MUST 设置 `Retry-After`。
- `503 temporarily_unavailable` SHOULD 在可预估恢复时间时设置 `Retry-After`。
- body 中的 `retry_after_ms` 用于非 HTTP binding 和精细诊断；其值 SHOULD 与 header 表达的时间一致。
- 客户端和对端服务 MUST 对同一 actor / service DID / endpoint 组合执行指数退避，避免重试放大。

缺少 `Retry-After` / `retry_after_ms` 或其它 operation-specific 恢复提示的可恢复错误，统一使用以下默认退避：首次等待至少 1,000 ms，factor=2，单次上限至少 60,000 ms，应用 0–20% jitter，且同一组合在连续 5 分钟内最多自动重试 5 次。声明 `traffic_metadata_hardened` profile 时，实际发送时刻还 MUST 受该 profile 的 `retry_cadence_padding` 约束。

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

版本与能力发现走 **`*.describe` 协商**：调用方 MUST 用 `describe.supported_operations` / `supported_profiles`（而非 path 里写死的版本）判断对端支持什么。当前尚未发布，破坏性修订直接更新 current-v1 canonical event kind、schema、profile、fixture 与 `forbidden-wire-fields`，不保留 rename alias、迁移表或双读路径。如确需在传输层标注协议版本，用请求/响应 header（`Arkret-Protocol-Version: 1.0`）或 media-type 参数做 content negotiation，**绝不放 path**。

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

服务 DID Document 中的 service endpoint 是服务身份与 endpoint 绑定的权威来源。域名级 bootstrap MAY 通过 `/.well-known/arkret/server` 或等价 signed metadata 暴露 endpoint 摘要，但接收方仍 MUST 校验：

- HTTPS/TLS 名称与返回的 endpoint 一致；
- service DID、DID Document service entry、describe 响应和 HTTP Message Signature 绑定一致；
- Realm policy 或 actor / organization service delegation 允许该服务角色；
- metadata hash / version 未被本地策略标记为撤销或过期。

服务发现结果 SHOULD 按 HTTP cache header 缓存。未提供显式缓存时间时，客户端 MAY 使用不超过 24 小时的默认 TTL；实现 SHOULD 对正缓存设置上限（建议不超过 48 小时），对失败缓存使用更短 TTL 或指数退避，避免一次临时故障长期破坏联邦。

### 11.2 出站网络目标策略与 SSRF 防护

任何服务在访问由用户、远端 peer、DID Document、Directory、Policy Server、Blob/Media metadata、Snapshot manifest、Applet/Agent endpoint、Webhook 或 service discovery 返回的 URL 之前，MUST 执行出站网络目标策略。该规则覆盖 DID resolution、联邦 push/pull/frontier probe、媒体抓取、thumbnail 生成、policy check、snapshot/chunk fetch、webhook、agent/applet handoff 以及等价的非 HTTP binding。

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
- 拒绝时 SHOULD 返回 `policy_denied`，并在仅对 operator 可见的审计细节中记录被拦截的地址类别、规范化 URL digest、解析 IP、调用用途和 policy version。公开错误不得泄露内网拓扑。
- **出站联邦 / 媒体 / snapshot fetch 的两层校验为合取（normative）**：出站联邦 push / pull / frontier probe、媒体抓取、以及 snapshot manifest / chunk fetch，MUST **同时**满足 (a) 本节 §11.2 的地址分类 fail-closed 检查，与 (b) [`federation.md` §3.4`](./federation.md) 的 federation peer policy（`deny` 先于 `allow` 评估，且 peer policy 只能收紧不能放宽地址分类）。两层是**合取**：任一层拒绝即 fail closed，不存在"地址分类通过即放行而跳过 peer policy"或"peer policy allow 即跳过地址分类"的旁路。snapshot manifest / chunk fetch 的目标 host（含 `chunks[].chunk_ref` 指向的 blob host、`snapshot_bootstrap` 内的 endpoint）MUST 同样纳入这两层校验——既按 §11.2 做地址分类，也按 §3.4 peer policy 判定该 host / service DID 是否在出站允许集中；任一层拒绝即拒绝该 chunk fetch，不得静默退回未校验地址。

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
