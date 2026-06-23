---
title: Device Lifecycle
status: candidate
normative: true
stability: v1
updated: 2026-06-12
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. Login & Authorization Boundaries

去中心化协议摒弃了传统的账号+密码中心化认证模式，身份的本质是持有私钥。Cokret 把以下三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `ck.session.grant`、触发恢复流程、请求已有设备授权，或（托管 DID 模型，§5.4）经 `ck.gate.account.command.enroll_device` 请求入册权威签发 `service_attested` 设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `ck.device.authorize`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Realm capability。

### 1.1 认证服务（Auth Server）验证什么

Cokret 可以部署 Auth Server（企业 SSO 场景下的部署形态为 Auth Gateway），但它不是协议身份根。它验证的是“某个登录会话是否可以被绑定到某个 DID principal / device”，而不是用用户名、密码、邮箱或 OIDC subject 直接定义主体所有权。

实现 MAY 支持以下登录因子：

- 用户名 + 密码，用于传统 service account 登录。
- Passkey / WebAuthn，用于强认证或无密码登录。
- OIDC / SSO，用于企业或组织管理账号。
- 已授权设备配对，用于普通多设备加入。
- Recovery key、门限恢复或受信恢复服务，用于全部设备丢失后的恢复。

认证成功后，Auth Server MUST 产出以下至少一种可验证绑定：

- `ck.session.grant`：把短期 `session_public_key` 委托给 DID principal / device。
- `ck.device.authorize`：把新设备公钥加入当前设备集合。
- 满足 `recovery_policy` 的 `recover` / key-log event。

`session_public_key` 不仅是会话身份标记，还是会话请求的 proof-of-possession 出示密钥：日常受保护请求 SHOULD 用该 key 对请求做 RFC 9421 HTTP Message Signature（sender-constrained 出示），使会话出示与该 key 绑定，仅截获 `ck.session.grant` 不足以重放。行使该 key 出示的具体形态、覆盖的 components 与 replay window 见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md) 与 [`../sync/service-http-binding.md` §2.5](../sync/service-http-binding.md)；高安全 deployment profile 下该 PoP 出示对常规写与敏感读升为 MUST。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Realm policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

### 1.2 登录、设备授权与设备验证的边界

Cokret v1 把三件事分开处理：

- **登录因子验证**：Auth Server 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `ck.session.grant`、触发恢复流程、请求已有设备授权，或（托管 DID 模型，§5.4）经 `ck.gate.account.command.enroll_device` 请求入册权威签发 `service_attested` 设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `ck.device.authorize`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Realm capability。

因此“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `ck.device.authorize` 或短期 `ck.session.grant`。短期 Web/OIDC 登录可以只使用 `ck.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须走设备授权和设备密钥验证。


## 2. 多设备配对 (Device Pairing)

在 Cokret 中，用户的每个物理/逻辑设备都应该拥有本地独立生成的设备级密钥对 (Device Key)。
多设备登录的过程，本质上是“已授权设备将新设备加入身份控制网”的密码学授权过程。

### 2.1 配对流程 (无密码登录)
1. **新设备初始化**：用户在新手机或新电脑上打开应用，本地生成一组全新的 ECDSA/Ed25519 密钥对。屏幕上显示包含公钥与临时连接信息的二维码 (QR Code)。
2. **主设备扫码**：用户使用已登录的主设备（如已通过面容 ID 解锁的手机）扫描该二维码。
3. **密码学授权**：
   - 主设备验证 pairing challenge 后，签发 `ck.device.authorize`、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `ck.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `ck.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Sync Service，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播 `ck.device.authorize` 事件；若封装为 Event Envelope，其 `realm_id` 是目标 principal 的 `principal_control_realm_id`。新设备获得的能力由该事件、session grant、Realm capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

### 2.2 设备吊销
当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `ck.device.revoke`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

`ck.device.revoke` 是 principal control stream 上的 Control Move：其 Event Envelope MUST 携带 `seal_basis`（撤销方签名时观察到的 accepted Seal view `{leaves[], control_event_set_root, state_root}`，进入 canonical event bytes 并被撤销证明签名覆盖，见 `../authz/event-auth-state-resolution.md` §5）；payload 不携带任何 frontier 字段。客户端铸造单 leaf basis 的注册来源是 `ck.self.events.query.frontier?realm_id=<principal_control_realm_id>`（Realm Seal view `{realm_id, seal_id, control_event_set_root, state_root, hlc?}`，取 `leaves=[seal_id]`）；该来源不可用时 MUST fail closed，不得伪造 basis。撤销自被 accepted Seal 覆盖（`control_sealed`）起生效；Principal Server / Sync Service 在拒绝该设备后续 session grant、KeyPackage、to-device write 或 Event write 时，MUST 以该 covering Seal 或其后继 Seal view 作为判定依据，不得用本地布尔缓存替代；撤销已提交但尚未 sealed 期间，受理服务 SHOULD 预先 fail closed。

共享 E2EE Realm 不能只看到“某设备已撤销”的服务端布尔值就推进新 epoch。对应 `ck.mls.commit` Remove 的 `governance_binding.membership_frontier` MUST 覆盖该 `ck.device.revoke` 事件本身，或覆盖一个已经把该撤销导入 Realm governance state 的显式 Control Move，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖；否则该 Remove 不满足 MLS Governance Binding，新的 `covered_seals_cell` 不得声称已覆盖该设备撤销。


## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 托管员工 DID 的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 principal signing key 或 recovery key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，签发短期、受众绑定、scope 受限的 `ck.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。其中绑定的设备 MUST 是客户端持有的稳定协议 `device_id`（`ck:device:<uuid>`，由客户端在认证时显式声明，例如 OAuth `urn:cokret:client:device:<id>` scope 透传到 introspection 的 `org.cokret.device_id` claim）。资源服务器 MUST NOT 从 token / session 标识（如 `jti` / `session_id`）派生或伪造一个 per-token 的 `device_id`——这违反 §4「服务端不得伪造 device identity」，且会让该值在每次 token 轮换时漂移，静默破坏所有按 `(principal, device)` 绑定的不变量（sync cursor 主体/设备匹配、key backup 写入设备授权）。携带认证材料但缺少稳定 device 绑定的会话 MUST 对 device-scoped 操作 fail-closed 拒绝，而非降级放行。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。常规写与敏感读 SHOULD 进一步用 `session_key`（即 grant 委托的 `session_public_key`）对每个请求做 RFC 9421 HTTP Message Signature 出示（sender-constrained / PoP，见 [`../sync/api-conventions.md` §3.2](../sync/api-conventions.md)），使会话请求与该 key 绑定，截获 token 不足以重放；高安全 deployment profile 下该出示升为 MUST。资源服务器仍 MUST 重新验证 DID control state、capability、Realm policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。

### 3.3 设备持有绑定与 grant 轮换（normative）

为在「会话凭据短期有效」与「设备会话可跨多日免重登」之间取得一致,session grant 采用**设备密钥持有绑定 + 滚动轮换**模型:

- **持有绑定(cnf.jkt)**:签发 `ck.session.grant` 时,Auth Server MUST 要求客户端出示一个由其稳定设备密钥(holder key,RFC 9449 DPoP 式持有证明)签名的 proof,并把该密钥的 RFC 7638 JWK 指纹写入 grant 的 `cnf.jkt`(RFC 7800 confirmation)。该设备密钥即设备的持有凭证;`cnf.jkt` 把 grant 绑定到「持有该私钥的设备」,而非仅记一个 `device_id` 字符串。
- **grant 直接出示、短期轮换**:Principal Server 不铸第二个本地会话凭据；客户端以 `ck.session.grant` + DPoP 直接访问 `/_cokret/self/*`。grant 自身为分钟到小时级 TTL，客户端在 grant 临期时用**仍有效的 grant** 与同一设备 holder key 轮换出新 grant。
- **轮换(rotation)**:grant 临近自身过期时，客户端用**同一设备 holder key** 签 DPoP 持有证明，向 Auth Server 的 session-grant 轮换端点(见 [`../sync/service-http-binding.md` §2.3](../sync/service-http-binding.md))换出一张新 grant。Auth Server MUST 校验 proof 的 JWK 指纹等于旧 grant 的 `cnf.jkt`(证明持有同一设备私钥)，新 grant 保持 `cnf.jkt` 不变、刷新过期、继承 subject/scope/audience；旧 grant MUST 单次使用吊销。如此滚动使设备会话存活到天级，**直到设备被吊销、grant 链被吊销、或底层 `browser_session` 被终结(登出)**——三者任一即拒绝继续轮换(见 [`../identity/account-lifecycle.md` §4.1](../identity/account-lifecycle.md))。
- **不引入长期离线续期凭据**:本协议以「设备 holder key 轮换 grant」承担续期职责,grant 自身保持分钟到小时级 TTL;不依赖、也不要求签发 OAuth `offline_access` 类长期续期凭据。
- **登出即终结**:轮换链挂靠在 Auth Server 的 `browser_session` 上；`browser_session` 被登出终结后，即便持有正确的设备私钥(指纹匹配 `cnf.jkt`)也 MUST NOT 再轮换出新 grant——续期必须重新走完整认证。

此模式只把 Web2 SSO 作为登录因子和会话授权输入。它不授予 E2EE 密钥访问权，不自动创建长期设备，不替代 `ck.device.authorize`、DID/key-log operation 或 recovery policy。


## 4. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `ck:device:<uuid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json
{
  "device_id": "ck:device:019640dd-8000-7000-8000-000000000000",
  "principal_id": "did:webvh:...",
  "display_name": "Alice iPhone",
  "algorithms": ["ck.mls.v1", "ck.hpke_x25519_aead_xchacha20poly1305.v1"],
  "verify_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "kid": "did:webvh:...#ck_device_01HV_verify"
  },
  "hpke_key": {
    "kty": "OKP",
    "crv": "X25519",
    "kid": "did:webvh:...#ck_device_01HV_hpke"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

`display_name` 是用户为该设备指定的人类可读名称（如 "Alice iPhone"），用于在设备列表 / 验证 / 撤销 UI 中区分同一 principal 名下的多台设备。它是 optional、可变、UI-only 字段，无唯一性约束，不参与任何 capability、reducer 或加密信任决策；设备的协议层唯一标识始终是 `device_id`。按 [`models/common-fields.md` §3](../models/common-fields.md) 与 [`overview/glossary.md`](../overview/glossary.md) 的命名约定，device record 的人类可读名称字段统一使用 `display_name`，不得用 `device_label`、`device_name` 或裸 `name` 等别名。

设备记录 MUST 由 principal 当前控制密钥或已信任的 self-signing key 签名。服务端不得伪造 device identity。

## 5. Signing Hierarchy

Cokret 使用三层签名链：

- `principal_signing_key`：DID 控制层，负责发布和轮换账户级签名根。
- `self_signing_key`：签名本 principal 的设备。
- `user_signing_key`：签名其他 principal 的 identity key，表达人工验证后的信任。

`self_signing_key` 和 `user_signing_key` SHOULD 存入加密 secret storage，并通过新设备验证后共享。

### 5.1 Cross-Signing Publish Envelope

`self_signing_key` (SSK) 与 `user_signing_key` (USK) 的公钥 MUST 通过 `ck.cross_signing.publish` 事件公布到 principal control stream。该事件确立"PSK → {SSK, USK}"绑定，是后续 device trust chain 与人工信任签名得以验证的根。

Schema id：`ck.schema.cross_signing_publish.v1`

```json
{
  "kind": "ck.cross_signing.publish",
  "realm_id": "<principal_control_realm_id>",
  "actor_id": "did:webvh:...",
  "payload": {
    "principal_id": "did:webvh:...",
    "trust_domain": "ck:trust_domain:did.webvh.example",
    "principal_signing_key": {
      "kid": "did:webvh:...#ck_principal_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase"
    },
    "self_signing_key": {
      "kid": "did:webvh:...#ck_self_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase",
      "binding": {
        "verification_method": "did:webvh:...#ck_principal_signing_v1",
        "alg": "EdDSA",
        "signature": "base64url..."
      }
    },
    "user_signing_key": {
      "kid": "did:webvh:...#ck_user_signing_v1",
      "alg": "EdDSA",
      "public_key": "z6Mk...",
      "key_format": "multibase",
      "binding": {
        "verification_method": "did:webvh:...#ck_principal_signing_v1",
        "alg": "EdDSA",
        "signature": "base64url..."
      }
    },
    "expected_previous_generation": 0,
    "generation": 1,
    "issued_at": "2026-04-26T00:00:00Z"
  }
}
```

Payload-only schema 示例（即 Event `payload` / 上例 `payload` 的规范形态）：

```json schema=schemas/cross-signing-publish.schema.json
{
  "principal_id": "did:web:alice.example",
  "trust_domain": "ck:trust_domain:did.webvh.example",
  "principal_signing_key": {
    "kid": "did:web:alice.example#ck_principal_signing_v1",
    "alg": "EdDSA",
    "public_key": "AA",
    "key_format": "raw_base64url"
  },
  "self_signing_key": {
    "kid": "did:web:alice.example#ck_self_signing_v1",
    "alg": "EdDSA",
    "public_key": "BB",
    "key_format": "raw_base64url",
    "binding": {
      "verification_method": "did:web:alice.example#ck_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "c2ln"
    }
  },
  "user_signing_key": {
    "kid": "did:web:alice.example#ck_user_signing_v1",
    "alg": "EdDSA",
    "public_key": "CC",
    "key_format": "raw_base64url",
    "binding": {
      "verification_method": "did:web:alice.example#ck_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "c2ln"
    }
  },
  "expected_previous_generation": 0,
  "generation": 1,
  "issued_at": "2026-04-26T00:00:00Z"
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `principal_signing_key` | required | PSK 当前公钥引用。`kid` MUST 出现在该 principal 当前 DID document 或 key-log head 的 verification methods 中；服务端不接受 `kid` 不在当前控制集中的 publish。 |
| `trust_domain` | required | 部署级 trust domain（`ck:trust_domain:<scope>`）。Receiver MUST 在验证任一 binding 签名前先检查该值与当前接收上下文一致；不一致 MUST `cross_domain_replay_rejected`。 |
| `self_signing_key` | required | SSK 公钥 + 由 PSK 对 canonical SSK record 的签名。`binding.verification_method` MUST 与 `principal_signing_key.kid` 相同 DID 控制集。 |
| `user_signing_key` | required | USK 公钥 + 由 PSK 对 canonical USK record 的签名；MUST 与 `self_signing_key` 不同 `public_key`。 |
| `expected_previous_generation` | required | CAS precondition。首次 publish 使用 `0`；后续 publish MUST 等于 receiver 当前 accepted generation。 |
| `generation` | required | 单调递增整数。每次 cross-signing reset（§14）MUST `generation += 1`。Receiver 见到 `generation` 比已 accepted 状态低的 publish MUST 拒绝。 |
| `issued_at` | required | 发布时间；MUST be no later than 接收方本地时钟 + protocol skew。 |

`binding` 的 canonical signing input：

```text
"ck-cross-signing-bind-v1\n"
+ canonical_json({
    "principal_id": <did>,
    "trust_domain": <trust_domain>,
    "subordinate_key_kind": "self_signing" | "user_signing",
    "subordinate_kid": <kid>,
    "subordinate_alg": <alg>,
    "subordinate_public_key": <public_key>,
    "generation": <generation>
  })
```

服务端 MUST 拒绝 `subordinate_alg` 不在协议算法 registry 中、或 `subordinate_public_key` 与 binding 输入声明不一致的 publish。Reducer 接受 publish 前还 MUST 校验 `payload.expected_previous_generation == current accepted generation` 且 `payload.generation == payload.expected_previous_generation + 1`；同一控制提交批次内若 reset 与 stale publish 并发，stale publish 因 head precondition 不成立而 fail closed，不得依赖本地到达顺序。

`trust_domain` 绑定（normative）：`ck.cross_signing.publish` 与 §14 的 reset 使用同一 deployment-scope replay boundary。Receiver MUST 在解析 publish 时先检查 `payload.trust_domain == current_receive_context.trust_domain`；不匹配时直接拒绝，不得把该 publish 纳入 accepted generation。由于 `trust_domain` 也进入 PSK 对 SSK / USK 的 binding transcript，同一 publish bytes 从 deployment A 搬到 deployment B 时签名 transcript 不同，验证必然失败。

### 5.2 Device Trust Chain

设备 trust state 由以下链推导，**不允许跳层**：

```text
DID-method history → principal_signing_key (PSK)
                       ├── self_signing_key (SSK)   ── signs ──► device.verify_key
                       └── user_signing_key (USK)   ── signs ──► other principal's verify_key
```

每条 `ck.device.authorize` 事件 MUST 在 `payload.cross_signing_binding` 字段携带 SSK 对该设备 `verify_key` 的签名：

```json
{
  "kind": "ck.device.authorize",
  "payload": {
    "principal_id": "did:webvh:...",
    "device_id": "ck:device:...",
    "device_public_key": "z6Mk...",
    "cross_signing_binding": {
      "verification_method": "did:webvh:...#ck_self_signing_v1",
      "alg": "EdDSA",
      "ssk_generation": 1,
      "signature": "base64url..."
    },
    "...": "..."
  }
}
```

`cross_signing_binding` 的 canonical signing input：

```text
"ck-device-trust-bind-v1\n"
+ canonical_json({
    "principal_id": <did>,
    "device_id": <id:device>,
    "device_public_key": <public_key>,
    "ssk_generation": <ssk_generation>
  })
```

#### 5.2.1 验证算法（normative）

接收方判定 `device` 是否 cross-signed 时 MUST 执行：

1. 解析 principal control stream 中 `accepted_generation = max(publish.generation)` 的 `ck.cross_signing.publish` 事件作为当前 PSK / SSK / USK。
2. 校验 `publish.principal_signing_key.kid` 出现在该 principal DID method 当前控制集中。
3. 校验 `publish.self_signing_key.binding.signature` 由 PSK 对 §5.1 canonical 输入签名。
4. 在该设备的最新 `ck.device.authorize` 事件中读取 `cross_signing_binding`；若缺失 MUST 视为 `unverified`，不得回退到"已授权 ⇒ cross-signed"。
5. 比较 `cross_signing_binding.ssk_generation` 与 `accepted_generation`：
   - 相等：用当前 SSK 公钥校验签名；通过则 `cross_signed`，失败则 `unverified`。
   - 小于：cross-signing 在该设备签发后已重置；设备 trust state MUST 强制降为 `needs_reverification`（见 §14）。
   - 大于：未来 generation；MUST 视为 `unverified` 并触发 stream re-sync。
6. 跨 principal 信任（USK 签对方 PSK / device key）按对称流程执行：本端 USK binding 必须签发对方 PSK 的 `(kid, generation)` 元组而不是裸公钥，避免对方静默轮换 PSK 后仍继承信任。

实现 MUST 把"未携带 `cross_signing_binding` 的 `ck.device.authorize`"与"binding 校验失败"区分上报，因为前者属于 bootstrap 例外（仅 [`identity/key-management.md` §5.0.1](../identity/key-management.md) inception 路径允许），后者属于密码学异常。

#### 5.2.2 设备 lifecycle × trust 正交状态机（normative）

设备状态由**两个正交维度**构成，二者独立演进、不可互相替代：

- **Lifecycle 维度**：`active`（`ck.device.authorize` 在效）↔ `revoked`（`ck.device.revoke` 已吊销）。`revoked` 是 **terminal**——一旦吊销，该 `device_id` MUST NOT 被复活；重新启用需新设备新 `device_id` 走新 `ck.device.authorize`。目录态投影见 §8.2 `device_status`。
- **Trust 维度**：`unverified` / `cross_signed` / `needs_reverification` / `verified`，由 §5.2.1 验证算法 + §14 reset 规则驱动。

两维度正交关系与合法转换如下：

| | trust=`unverified` | trust=`cross_signed` | trust=`needs_reverification` | trust=`verified` |
| --- | --- | --- | --- | --- |
| lifecycle=`active` | 初始态 / binding 缺失或校验失败（§5.2.1 步骤4） | §5.2.1 步骤5 binding 校验通过（generation 相等） | §5.2.1 步骤5 generation 小于（旧 binding）或 §14.2 reset 扩散 | SAS/QR 人工验证成功（§10.5）或入册权威背书路径 |
| lifecycle=`revoked` | （吊销后 trust 维度冻结，见下） | — | — | — |

正交转换规则：

- **trust 出边**：`unverified → cross_signed`（binding 校验通过）；`cross_signed → verified`（人工 SAS/QR 验证）；`cross_signed`/`verified → needs_reverification`（cross-signing reset，§14.2 或 binding generation 落后）；`needs_reverification → cross_signed`（被新 generation SSK 重新 cross-sign，即出现 `ssk_generation == accepted_generation` 的有效 binding）；`needs_reverification → verified`（重新 cross-sign 后再次人工验证）。`verified` 不直接降回 `cross_signed`（人工信任只被 reset 显式作废为 `needs_reverification`）。
- **lifecycle 出边**：`active → revoked`（`ck.device.revoke`），terminal，无逆边。
- **revoked 设备的 trust 取值**：设备进入 `revoked` 后其 trust 维度**冻结**为吊销时刻的值且不再用于任何信任判定——receiver MUST 把 revoked 设备一律当作不可用于验签 / 不可接收新密钥（§8.2 / §9：`device_status != active` 即 fail-closed），无论其冻结的 trust 值为何。trust 维度仅对 `active` 设备有协议意义。
- **非法迁移**：从 `revoked` 转出任何 lifecycle/trust 态 MUST 被拒绝（视为陈旧投影，按 control 流 frontier fail-closed）。

### 5.3 Bootstrap 例外

[`identity/key-management.md` §5.0.1](../identity/key-management.md) 中首台设备由 inception key 自授权时，`ck.device.authorize.payload.cross_signing_binding` MUST 省略 `verification_method` 引用，并改用 `bootstrap_binding`：

```json
{
  "bootstrap_binding": {
    "kind": "inception_self_authorized",
    "did_method_evidence_ref": "did:webvh:.../entry-0"
  }
}
```

receiver 接受 `bootstrap_binding` 当且仅当该 principal 的 control stream 中尚无任何 `ck.cross_signing.publish` 事件。首次 publish 写入后，所有后续 `ck.device.authorize` MUST 使用 §5.2 形式的 `cross_signing_binding`。本段（§5.2/§5.3 的 SSK / inception 信任根）适用于客户端自持控制密钥的 cross-signing 模型；使用托管 DID（account-authority）的 principal 改走 §5.4 的 `enrollment_authority_binding`，其 control stream 不产生 `ck.cross_signing.publish`，故本段"首次 publish 后必须用 §5.2"的前提对该模型恒不触发。

### 5.4 委派账号权威入册（`service_attested`）

当 principal 使用托管 DID（account authority 代铸，见 [`identity/account-lifecycle.md` §2.1.1](../identity/account-lifecycle.md) 与 [`identity/key-management.md` §5.0.6](../identity/key-management.md)）时，设备入册的信任根是 **DID 文档指派的入册权威**，而非客户端自持的 SSK（§5.2）或 DID inception key（§5.3）。该路径下 `ck.device.authorize` MUST 携带 `enrollment_authority_binding`，而非 `cross_signing_binding` 或 `bootstrap_binding`（三者互斥，schema `oneOf`）：

```json
{
  "enrollment_authority_binding": {
    "kind": "service_attested",
    "authority_did": "did:webvh:.../auth-server",
    "authorization_ref": "did:webvh:<principal>#device-enrollment"
  }
}
```

该 `ck.device.authorize` Event 的信封 MUST 采用 [`models/common-fields.md`](../models/common-fields.md) 的委派执行形态：`actor_id` = principal DID（记录主体），`executed_by` = 入册权威 DID（实际写入方，等于 `authority_did`），`authorization_ref` = principal DID 文档中指派该权威的委派条目（`did_delegation_ref`，即 [`identity/identity-did.md`](../identity/identity-did.md) 的 `CokretDeviceEnrollmentAuthority` service 条目，或一条 `capabilityDelegation` verification method）。Event `proofs[]` 由入册权威的签名密钥签发，其 `verification_method` MUST 映射到 `executed_by`（而非 `actor_id`）。入册权威的签名密钥是一把**持久服务密钥**，与 §5.0.1 step5 必须退场的 inception key 无关；Auth Server 等账号权威 **MUST NOT** 持有或伪造本 principal 的 SSK。

receiver 接受 `service_attested` 的 `ck.device.authorize` 时 MUST 校验：

1. `authority_did`（= `executed_by`）确为 principal DID 文档**在本 Event accepted-at 时点解析**所指派的入册权威（按时点解析见下），且 `authorization_ref` 委派覆盖设备授权动作；不满足则 `reject`，reason `device_enrollment_authority_not_designated`。
2. `proofs[]` 用入册权威 DID **按时点解析**得到的签名公钥验签通过。

`device_id` 是 principal 作用域内的 typed id（`ck:device:<uuid>`），由客户端在该会话内一致使用；入册产生的 `device_public_key` 投影写入设备行时即以该 `device_id` 为键，与会话/恢复查找口径一致。

被接受后，该 device 的 `device_public_key` 作为 principal DID 下的 verification method 进入**设备集投影**（device-set projection），它**不**写入 DID method 的 key log（如 `did:webvh` 的 `did.jsonl`）。在该 profile 下，设备的信任根即"入册权威背书"；E2EE 设备集成员资格由**入册背书的设备集**派生，§5.2 的 SSK cross-signing 为可选增强而非必需。

**两套验证 regime（normative）：**

- **入册时（低频）：** 如上，通过解析入册权威 DID 校验 `ck.device.authorize`。
- **普通事件热路径（高频）：** receiver **MUST NOT** 为校验普通业务事件而在线解析 principal DID。普通事件 `proofs[].verification_method` 形如 `{principal_did}#{device_id}`，fragment 即 `device_id`；receiver 从**当前 principal-control 流 frontier 的设备集投影**取该 device 的 `device_public_key` 验签，device 缺失或已吊销即 `reject`。吊销一致性由 control 流 frontier 保证，防止 stale 投影放行已撤销设备。

**按时点解析（normative）：** 历史 `ck.device.authorize` 的复验（审计 / 联邦 replay）MUST 按该 Event 的 server-sealed accepted-at，对入册权威 DID 做按时点解析（`did:webvh` 历史 `versionTime`），用当时有效的入册密钥验签；因此入册权威轮换其签名密钥**不会**使既有授权失效。设备集投影的历史复算同样按时点进行。

**inception 窗口不适用：** `service_attested` 的 `ck.device.authorize` 不携带 `did_inception` ref，[`identity/key-management.md` §5.0.1 step5](../identity/key-management.md) 的 inception key 24h 在线窗口门对其天然 inert。

**客户端请求入口（normative）：** 客户端经 canonical gate 操作 `ck.gate.account.command.enroll_device`（`POST /_cokret/gate/account/device-enroll`，request `account_device_enroll_request_body {device_id, device_public_key, actor_seq, not_before?}`、response `account_device_enroll_outcome {principal_id, device_id, authority_did, authorized_event}`）向其指派的入册权威请求该 `service_attested` 签名。请求 MUST 以当前 `ck.session.grant`（`Authorization: bearer`）+ holder DPoP proof（绑定 grant `cnf.jkt` 与本 endpoint）认证；入册权威校验该会话拥有目标 principal 后，用其持久 enrollment key 铸造 `ck.device.authorize` 并返回完整 Event，客户端原样提交到 `POST /_cokret/self/events`。该操作是 §2.1 `pair_device`（已授权设备 SAS/QR 审批，携 `pairing_code`）之外、用于无兄弟设备可审批的 bootstrap / 首台设备路径。入册权威 endpoint 与其它 `/_cokret/gate/account/*` 同处一个 Account Authority `gate_account_base`。

## 5a. Privacy-Preserving Push

Cokret 推送通道设计的目标是在不向 push gateway / vendor、上游 Sync Service、网络中间人或第三方 SaaS 控制面泄露身份与可链接信息的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。

### 5a.1 `push_target_id` 派生与作用域

- 作用域：`per (recipient_service_did, principal_id, device_id, push_route)`。`recipient_service_did` 是当前 Realm membership delivery binding 指向的 Principal Server service DID；同一 DID 在个人 Principal Server 与组织 Principal Server 上注册同一物理设备时，MUST 使用互相不可链接的 `push_target_id`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度：`push_target_id` MUST 至少 128 bit 熵，编码为 base64url（最少 22 字符）；推荐 256 bit。`high_security_organization`、`sovereign_deployment` / `isolated_sovereign_network` 等高安全 deployment profile MUST 使用 ≥ 256 bit 熵（不可链接性是这些场景的硬隐私属性，128 bit 仅为通用下限）。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。生成方式 SHOULD 是 device-local 随机；设备 MAY 用本地 secret 与 `push_route` 派生，前提是源 secret 不可被服务端取回。
- 标识形态：典型 wire 形态为 typed ID `ck:pseudonym:push:<base64url>`，由 `id-kind-registry.json` 中 `pseudonym` 项授权使用；也可作为 raw base64url 字符串出现在 `ck.device.push_route` 等 actor-private state event payload 中。

### 5a.2 注册与撤销

- 设备 MUST 通过 `ck.device.push_route` actor-private state Event 把 `(recipient_service_did, principal_id, device_id, push_route, push_target_id, push_gateway_did, encryption_key, capabilities)` 写入当前投递 Principal Server 可见的 principal control stream 或等价 actor-private state；该 Event 不携带 CBA reducer 字段，不进入 shared Realm Seal coverage。目标 actor-private cell 的 `cell_subject` 由 schema registry 声明的 composite `(payload.recipient_service_did, payload.principal_id, payload.device_id, payload.push_route)` 派生（cas_register, bottom=reject）。`recipient_service_did` MUST 与 [`governance/member-delivery-binding.md` §2](../governance/member-delivery-binding.md) 接受准则中该 device 所属 member 的 `delivery_binding.recipient_service_did` 一致；推送注册按 `(recipient_service_did, principal, device, push_route)` 维度隔离，同一 DID 在不同 Principal Server 上下文中的 push route 不共享、不可关联。
- 撤销：设备 MUST 在同一 actor-private cell 上写后继 `ck.device.push_route` event 设置 `revoked: true` 或重新写入新 `push_target_id`；service / gateway MUST 在 actor-private state 收敛后停止接受旧伪名。
- 轮换：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时轮换 `push_target_id`。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 `(recipient_service_did, principal, device)` 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。短暂保留期 MUST ≤ 24h，或与单条未投递消息 TTL 取较短者；超过该窗口 MUST 物理删除旧 `push_target_id` 与对应索引材料，不得保留任何能把新旧映射回同一 device 的信息。
- **条数与注册速率上限（normative）**：单一 `(recipient_service_did, principal_id, device_id)` 维度下并存的 active `push_route` 条数 MUST ≤ 16（v1 wire 上限；登记于 [`../conformance/scalability-constraints.md` §6.1](../conformance/scalability-constraints.md)），超过时服务端 MUST 拒绝新 `ck.device.push_route` 注册（`push_route_limit_exceeded`）。同一维度的 push-route 注册 / 轮换 MUST 限速，默认窗口 60s 内 ≤ 8 次写入；超额时返回限速响应并记内部审计 `push_route_registration_rate_limited`。该上限防止单设备通过无界 push_route 放大注册状态或制造可链接性面。

### 5a.3 不可链接性要求

- 同一 `principal_id` 在不同 `recipient_service_did`、不同设备或不同 push route 上的 `push_target_id` MUST NOT be linkable by push gateway / 第三方 transport（除非两侧自愿持有相同源 secret）。受托 Sync Service MAY 在自己的授权上下文内持有从成员 delivery binding 到本服务本地 push queue 的短期索引，但不得把该索引导出给 Push Gateway / vendor。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Realm 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Realm），但 push payload 内不得携带 plaintext `realm_id`/`strand_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

### 5a.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST NOT 包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Realm 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

### 5a.5 与其它子系统的边界

- Sync Service：以 `push_target_id` 作为 push fanout 索引。被 member delivery binding 授权的 Principal Server MAY 在运行时持有 `recipient_service_did + principal_id + device_id + push_route -> push_target_id` 映射以完成投递；该映射不得暴露给 Push Gateway / vendor，日志、导出、法定披露和跨服务复制 MUST 脱敏或失效化。未被该 Realm membership / service binding 授权的服务不得保留可逆映射。
- WebRTC 通话邀请（`webrtc-signaling.md` §9 incoming-call wakeup）通过同一 `push_target_id` 触发；payload 仍走 §5a.4 加密通道。
- 推送规则（`push-notifications.md` §4 keyword / member_count 等）以 `push_target_id` 为目标但 MUST 在不解密 payload 的前提下完成评估，或在 E2EE Realm 中由设备本地评估，详见对应文档。

## 6. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `ck.device.list_update` event。该 event 是 principal control stream 中的 actor-private durable identity state；若使用 Event Envelope，顶层 `realm_id` MUST 是目标 principal 的 `principal_control_realm_id`。它不进入任一共享 Realm 控制面 Seal coverage / state_root；共享 Realm 只能通过 MLS Welcome / Remove、device trust proof 或 explicit membership / KeyPackage event 感知其结果：

```json
{
  "kind": "ck.device.list_update",
  "payload": {
    "principal_id": "did:webvh:...",
    "changed": [
      "ck:device:01964137-0000-7000-8000-000000000000"
    ],
    "left": [
      "ck:device:01964138-0000-7000-8000-000000000000"
    ],
    "stream_id": "devstream_42"
  }
}
```

客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 7. To-Device Messages

To-device message 是面向具体 principal/device 的非 Realm 持久消息，用于密钥交换、验证、secret sharing 和通知。

To-device wire object MUST 使用 `DeviceMessageEnvelope`，而不是持久 `EventEnvelope`。标准 `ck.key.verification.*` 名称在 to-device 通道中出现在 `kind` 字段；它们不得推进 `actor_seq`、`prev_refs`、Realm reducer frontier 或持久 timeline。

`DeviceMessageEnvelope` 基本字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `kind` | `string` | required | 消息 kind，例如 `ck.key.verification.request`。标准 `ck.*` to-device kind MUST 在 registry 中登记为 `ephemeral_event` 或由扩展 profile 声明。 |
| `sender_principal_id` | `did` | required | 发送 principal。 |
| `sender_device_id` | `id:device` | required | 发送设备。 |
| `recipient_principal_id` | `did` | required | 接收 principal；MUST 等于投递路径中的目标 principal。 |
| `recipient_device_id` | `id:device` | required | 接收设备；MUST 等于投递路径中的目标设备。 |
| `sent_at` | `datetime` | required | 发送时间。 |
| `expires_at` | `datetime` | required | 队列过期时间；不得晚于该 kind/profile 声明的 TTL 上限。 |
| `content` | `object` | required | 类型相关内容；私密内容 SHOULD 端到端加密。 |
| `device_proof` | `proof` | optional | 传输认证不能覆盖的场景 MAY 带 detached device proof。 |

`recipient_principal_id` 和 `recipient_device_id` MUST 被签名、device proof 或加密 AAD 覆盖。发送接口使用 `messages.{principal_id}.{device_id}` 做批量路由时，服务端在入队前 MUST 把路径目标复制进 `DeviceMessageEnvelope`，且接收端 MUST 拒绝 envelope 目标与当前登录设备不一致的消息。

To-device 消息是短期队列对象，不是长期 Event history。发送方 MUST 设置 `expires_at`；服务端 MUST 拒绝缺失 `expires_at`、已经过期、早于 `sent_at` 或超过当前 service / Realm / profile TTL 上限的消息。默认最大队列 TTL 为 24 小时；高安全 profile SHOULD 使用更短值。标准验证请求仍受第 8.2 节约束，`request.expires_at` MUST be no later than `timestamp + 10m`。过期消息 MUST 从投递队列中清除，`GET /_cokret/self/device_messages` 不得返回；服务 MAY 仅保留最小幂等记录和脱敏审计摘要到 `expires_at` 后的短 grace period。

发送接口：

```http
POST /_cokret/self/device_messages
Authorization: Bearer <token>
Idempotency-Key: <opaque-string>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Idempotency-Key` | header | `string` | required | 发送方生成的幂等键，长度 1..128；服务端 MUST 以 `(sender, Idempotency-Key)` 去重，重复键但 body canonical hash 不同 MUST 拒绝。 |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前 principal 与发送设备。 |
| `messages` | body | `object` | required | 收件人 principal 到 device 消息的映射。 |
| `messages.{principal_id}` | body | `object` | required | 目标 principal DID。 |
| `messages.{principal_id}.{device_id}` | body | `object` | required | 目标设备消息；`{device_id}` MUST 是完整 `id:device` wire key。 |
| `messages.{principal_id}.{device_id}.kind` | body | `string` | required | to-device 消息 kind，例如 `ck.key.verification.request`。 |
| `messages.{principal_id}.{device_id}.expires_at` | body | `datetime` | required | 队列过期时间；服务端物化 envelope 后必须复制到 `DeviceMessageEnvelope.expires_at`。 |
| `messages.{principal_id}.{device_id}.content` | body | `object` | required | 消息内容；私密内容 SHOULD 端到端加密。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | 请求是否被**接受处理**（见下 partial-success 规则）。 |
| `delivered` | `object` | optional | 已入队或已投递设备摘要。 |
| `unknown_devices` | `object` | optional | 无法识别或不可投递的设备。 |

**Partial-success / 全局失败语义（normative）**：

- **整体拒绝**（请求级失败：认证 / 授权失败、`Idempotency-Key` 冲突、所有目标 envelope 缺 `expires_at` / 已过期 / 超 TTL 上限、body 非 canonical）MUST 走 HTTP 错误响应（4xx，按 [`../sync/api-conventions.md`](../sync/api-conventions.md) error envelope），**不**用 `ok=false` 表达；此时不入队任何消息。
- **部分成功**（请求被接受、至少一个目标被处理，但部分设备落入 `unknown_devices`）：`ok` MUST 为 `true`——`ok` 表达"请求已被接受并逐设备处理"，而非"全部设备均成功"。逐设备结果由 `delivered` / `unknown_devices` 表达。
- **覆盖关系**：`delivered` 与 `unknown_devices` 的设备集合 MUST 互不相交，且其并集 MUST 等于请求 `messages` 中的全部 `(principal_id, device_id)` 目标全集（每个目标恰好出现在二者之一）。consumer 据此可断言无目标被静默丢弃。
- 单设备因 TTL / `expires_at` 等可投递性原因不可入队时，该设备 MUST 计入 `unknown_devices`（携带可投递性失败语义），不使整请求失败。

请求示例（非完整 schema）。`messages.{principal_id}.{device_id}` 的 `{device_id}` 是**收件设备**地址,`content.from_device` 是**发送设备**(MUST 等于 envelope `sender_device_id`,见 §10.1),二者为不同设备，故 UUID 不同：

```json
{
  "messages": {
    "did:web:alice.example.com": {
      "ck:device:01964137-0000-7000-8000-000000000000": {
        "kind": "ck.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "ck:device:019641aa-0000-7000-8000-000000000001",
          "timestamp": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:10:00Z",
          "methods": [
            "ck.sas.v1",
            "ck.qr.v1"
          ]
        }
      }
    }
  }
}
```

同一 principal 的新设备请求旧设备验证/授权时，MUST 使用同一 `POST /_cokret/self/device_messages` wire shape 投递 `ck.key.verification.request`。发送方必须是 gate 签发的 holder-bound session，或受限 fresh-device session grant；后者只能发送 `ck.key.verification.*` bootstrap 消息给同 principal 的已授权设备。请求 content SHOULD 携带 `purpose="same_principal_device_authorization"` 和供 UI 比对/后续 gate finalize 使用的 pairing 材料：

```json
{
  "messages": {
    "did:web:alice.example.com": {
      "ck:device:01964136-8000-7000-8000-000000000000": {
        "kind": "ck.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_456",
          "from_device": "ck:device:01964137-0000-7000-8000-000000000000",
          "timestamp": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:10:00Z",
          "methods": ["ck.sas.v1", "ck.qr.v1"],
          "purpose": "same_principal_device_authorization",
          "pairing_code": "384921",
          "new_device_pubkey": {
            "kid": "ck:device:01964137-0000-7000-8000-000000000000",
            "alg": "Ed25519",
            "public_key": "base64url..."
          },
          "challenge_signature": "base64url...",
          "gate_audience": "https://auth.example.com",
          "request_canonical_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
          "device_metadata": {
            "display_name": "Alice's laptop",
            "platform": "desktop"
          }
        }
      }
    }
  }
}
```

接收旧设备 MUST 把 `purpose`、`pairing_code`、`new_device_pubkey.kid`、`challenge_signature`、`gate_audience` 和 `request_canonical_digest` 纳入用户确认与 SAS/QR transcript 绑定；不得只因收到该请求就把新设备标记为 trusted。用户确认后，旧设备通过 `ck.gate.account.command.pair_device` 完成授权落地；本规范不定义 `/_cokret/self/devices/pairing-requests*` 作为授权批准接口。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->

服务端 MUST 以 `(sender, Idempotency-Key)` 幂等。已投递消息的队列删除只由接收设备的显式确认（`ck.self.device_messages.command.ack`，见下文与 [`client-sync.md` §10.1](../sync/client-sync.md)）驱动；sync cursor 推进 MUST NOT 触发删除。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖 `kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、`sent_at` 和 `expires_at`。队列服务不得重写这些字段。`Idempotency-Key` 是 HTTP 层语义，不进入 envelope，也不参与 AAD。

接收接口：

```http
GET /_cokret/self/device_messages?from=<cursor>&limit=<n>
Authorization: Bearer <token>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `from` | query | `cursor` | optional | 上次同步位置（stream cursor）。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `messages` | `object[]` | required | 当前设备可见的 to-device 消息（`DeviceMessageEnvelope[]`，不是 Event Envelope）。 |
| `ack_token` | `string` | optional | `messages` 非空时 MUST 返回。覆盖本页及之前所有已投递消息的不透明确认令牌；客户端持久化处理完成后回传给 `ck.self.device_messages.command.ack`。语义见 [`client-sync.md` §10.1](../sync/client-sync.md)。 |
| `next_cursor` | `cursor` | optional | 下一次读取 stream cursor（只读位置，不触发删除）。 |
| `has_more` | `boolean` | required | 是否还有后续消息页。 |
| `limited` | `boolean` | optional | 是否因 limit 被截断。 |
| `lost` | `boolean` | optional | 自该设备上次确认位置以来，服务端因过期或容量约束丢弃过未确认消息时 SHOULD 置 `true`；客户端 SHOULD 触发密钥恢复路径。 |

确认接口：

```http
POST /_cokret/self/device_messages/ack
Authorization: Bearer <token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `ack_token` | body | `string` | required | 服务端先前签发给同一 `(principal_id, device_id)` 的确认令牌。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | 确认是否被接受（含旧令牌 no-op 的情况）。 |
| `pruned_count` | `int` | optional | 本次实际删除的消息数。 |

确认语义（normative，完整定义见 [`client-sync.md` §10.1](../sync/client-sync.md)）：确认是累计且单调的——服务端删除令牌覆盖位置（含）之前的全部已投递消息；重复 ack 或 ack 旧令牌返回 `{ok: true}` 且不得回退确认位置（天然幂等，无需 `Idempotency-Key`）。unknown / 过期 / cross-binding 令牌 MUST 返回 `invalid_param`（reason `invalid_ack_token`）且 MUST NOT 删除任何排队消息。客户端 MUST 在该批次密钥材料 / verification transcript / secret **持久化落盘之后**才 ack；未 ack 的消息在重连时由服务端重新投递，客户端按 `transaction_id` / `request_id` 幂等处理重复投递。

## 8. One-Time and Fallback Keys

设备支持非 MLS 加密或引导 MLS 时，MUST 发布 one-time / fallback prekey：

```http
POST /_cokret/self/keys/upload
POST /_cokret/self/keys/query
POST /_cokret/self/keys/claim
```

`POST /_cokret/self/keys/upload` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_id` | body | `id:device` | required | 当前上传设备。 |
| `one_time_keys` | body | `object` | optional | 算法名到 one-time key 的映射。 |
| `fallback_keys` | body | `object` | optional | 算法名到 fallback key 的映射。 |
| `device_signature` | body | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。canonical 签名输入见下方 §8.1。 |

响应字段：`one_time_key_counts: object` required；`fallback_keys: object` optional。

#### 8.1 `device_signature` canonical 签名输入（normative）

`keys/upload` 的 `device_signature` 由该设备的**设备身份 key**(event-signer 的 Ed25519 `did:key`，即 §5.2 `device_public_key` 对应私钥)对本次上传批次签名，绑定 `device_id` 与所上传的 OTK / fallback 批次。canonical 签名输入：

```text
"ck-keys-upload-v1\n"
+ canonical_json({
    "device_id": <id:device>,
    "one_time_keys": <one_time_keys or {}>,
    "fallback_keys": <fallback_keys or {}>
  })
```

- `canonical_json` 为 RFC 8785 JCS（见 [`../conformance/encoding.md`](../conformance/encoding.md)）；缺省的 `one_time_keys` / `fallback_keys` MUST 规范化为空对象 `{}` 后参与签名，不得省略键，保证发送方与验签方对同一批次得到逐字节一致的输入。
- 批次内每个 `key_record.signature` 仍按其各自语义独立链接到 self-signing / principal key；`device_signature` 额外对**整批**签名，防止服务端或中间人对批次做增删/重排。
- `device_signature.kid` MUST 指向该设备身份 key；服务端 MUST 用该设备权威 `device_public_key`(§5.2)验签，失败 MUST 拒绝上传（`invalid_param`）。

`POST /_cokret/self/keys/query` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_keys` | body | `object` | required | principal DID 到 device ID 列表的映射。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

服务端在处理 `keys/query` 时 MUST 先认证 requester，并且 MUST 仅在 requester 与被查询 `principal_id` 之间存在当前有效的授权关系时返回目录记录：至少同属一个 requester 可见且 requester 仍为 `join` 的 Realm，或存在当前 call/session/contact profile 明确定义的共享上下文。否则 MUST 使用与不存在不可区分的失败形态（省略该 `(principal_id, device_id)` 记录或写入 `failures` 的非枚举性失败），不得让任意已登录用户枚举其它 principal 的设备存在性 / 吊销状态。

响应字段：`device_keys: object` required；`failures: object` optional。`device_keys` 的每个 `(principal_id, device_id)` 记录为 `query_device_record`：prekey bundle 收在 `algorithms`(算法名 → key_record)子字段下，并在**与 `algorithms` 同级**携带设备验签公钥目录字段 `device_signing_key` 与 `device_status`(见下方 §8.2)。schema 见 [`keys-operations.schema.json`](../../artifacts/schemas/keys-operations.schema.json) 的 `$defs/query_device_record`。

#### 8.2 设备验签公钥目录（normative）

`keys/query` 响应在每个 `(principal_id, device_id)` 记录上附带便捷的**设备验签公钥目录**面，供任意 realm 成员把 `(actor, device)` 解析为权威验签公钥，据此 fail-closed 验证通话信令（[`webrtc-signaling.md` §5.1](./webrtc-signaling.md)）与持久消息的 proof：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `device_signing_key` | `did:key`(Ed25519 multibase) | optional | 该设备的**权威验签公钥**，来源 = 该设备权威 `ck.device.authorize.payload.device_public_key`(§5.2)。MUST **仅对 verified 且未吊销**的设备返回。 |
| `device_status` | `enum(active, revoked)` | optional | 目录态。`active` = 该设备 `device.authorize` 在效且未吊销；`revoked` = 已被 `ck.device.revoke` 吊销。 |
| `cross_signing_binding` | `object` | optional | **Tier-2**：该设备权威 `ck.device.authorize.payload.cross_signing_binding`（§5.2）原样回显，形态 `{verification_method, alg, ssk_generation, signature}`。供客户端独立验证 device key ← SSK 链路。inception bootstrap 设备无此字段（§5.0.1 例外）。 |

并在 `keys_query_outcome` 顶层附带**每 principal** 的交叉签名根材料：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `cross_signing` | `object` | optional | **Tier-2**：`{principal_id}` → 该 principal 当前 `accepted_generation` 的 `ck.cross_signing.publish` payload（§5.1，含 `principal_signing_key` / `self_signing_key`(+binding) / `generation`）。供客户端把 SSK 锚定到 DID 控制集再验 device binding。 |

规则：

- 服务端 MUST 仅对 verified 且未吊销设备返回 `device_signing_key`；对**吊销 / 未验**设备 MUST 省略 `device_signing_key`，并以 `device_status` 标注(吊销返 `revoked`)。即"省略 key" 与 "`device_status != active`" 等价表达设备不可用于验签。
- **Tier-1 便捷面（降级行为）**：`device_signing_key` 承载服务端在 session-grant / `device.authorize` ingest 时已校验过的 `device_public_key` 断言。仅信服务端断言而不独立验证交叉签名链的客户端，其设备身份信任根退化为"承载服务端诚实"，与 §4「device 身份不可由服务端伪造」相悖，故 **Tier-1 是显式降级行为，MUST NOT 作为 `e2ee_client` conformance profile 下 E2EE / 通话 proof 验签路径的默认行为**：
  - 凡声明 `ck.profile.e2ee_client.v1` 的客户端，在 E2EE 消息与通话信令 proof 验签路径上 MUST 执行 §8.3 的 Tier-2 链验证；仅服务端断言（Tier-1）不满足该 profile 的接受判据。
  - 不在该 profile 下、仅凭 Tier-1 接受 `device_signing_key` 的客户端，MUST 向用户披露"该设备身份未经密码学交叉签名链验证、信任根为承载服务端"（例如以 `unverified` / `device_unverified` 标识呈现），MUST NOT 把该设备呈现为已验证。
- **Tier-2 硬化面**：返回 `cross_signing_binding`（每设备）与 `cross_signing`（每 principal）的客户端 MUST 按 §8.3 独立验证完整交叉签名链，**不信服务端对 `device_signing_key` 的断言**，仅在链验证通过后才接受该 key。服务端对在效设备 SHOULD 同时返回 Tier-2 字段；缺失时客户端 MUST 视为 `unverified` 并 fail-closed。

接收方验 envelope / signal proof 时 MUST 按 `verification_method` = `` `{actor}#device` `` 经本目录解析 `device_signing_key` 得 verify_key；设备**吊销**(`device_status != active` 或目录省略 key)、目录**缺失**该 `(actor, device)`、Tier-2 链验证未通过、或验签失败者 MUST **fail-closed**：丢弃信号，MUST NOT 触发 UI、MUST NOT 入库。该规则同时适用于通话信令(详见 [`webrtc-signaling.md` §5.1](./webrtc-signaling.md))与持久消息接收路径。

#### 8.3 客户端交叉签名链验证（Tier-2，normative）

返回 Tier-2 字段时，客户端在接受 `device_signing_key` 为某 `(actor, device)` 的权威验签公钥前 MUST 执行 §5.2.1 链验证，且 **MUST NOT** 仅因服务端返回了 `device_signing_key` 就信任它：

1. **DID 锚定**：独立解析 `actor` 的 DID，校验 `cross_signing.{actor}.principal_signing_key`（`kid` + `public_key`）等于该 DID 当前控制集中对应 verification method 的密钥（逐字节）；不符 MUST 视为 `unverified`。
2. **PSK→SSK**：用上一步 DID 锚定的 PSK 校验 `self_signing_key.binding.signature` 覆盖 §5.1 self-signing canonical 输入；不通过 MUST `unverified`。
3. **SSK→device**：读该设备 `cross_signing_binding`；缺失 MUST `unverified`（除 §5.0.1 inception bootstrap 例外）。比较 `cross_signing_binding.ssk_generation` 与 `cross_signing.{actor}.generation`：相等则用 `self_signing_key.public_key` 校验 `cross_signing_binding.signature` 覆盖 §5.2 `"ck-device-trust-bind-v1\n" + canonical_json({principal_id, device_id, device_public_key, ssk_generation})`；小于 MUST `needs_reverification`（降级，不接受）；大于 MUST `unverified` 并触发 re-sync。
4. **接受判据**：仅当 1–3 全部得 `cross_signed` 时，客户端方接受 `device_signing_key` 用于 proof 验签；任一步失败 MUST fail-closed（按 `unverified` 处理：丢弃该 `(actor,device)` 的 proof，不触发 UI、不入库）。
5. `device_public_key` 取自 `device_signing_key`(did:key 内嵌的 Ed25519 公钥)，并 MUST 与第 3 步 binding 输入中的 `device_public_key` 为同一把 key——即客户端验证的正是它将用于 proof 验签的那把 key，闭合"目录给的 key ⇔ 被交叉签名背书的 key"。

`POST /_cokret/self/keys/claim` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `one_time_keys` | body | `object` | required | principal DID -> device ID -> algorithm 的映射。 |

响应字段：`one_time_keys: object` required；`failures: object` optional。

规则：

- `claim` MUST 原子消费 one-time key。
- fallback key MUST 标记 `fallback=true`；设备成功使用该 fallback key 建立首个会话后，MUST 在下一次 OTK 上传批次中同时上传新的 fallback key，并 MUST NOT 用旧 fallback key 建立第二个会话。
- 服务端返回 key 时 MUST 附带 device signature。
- 客户端 MUST 拒绝未被 self-signing key 或 principal key 链接的 device key，除非用户明确接受未验证设备。

## 9. MLS KeyPackage Claim API

MLS KeyPackage 使用独立的 single-use claim API，而不是复用 one-time prekey 语义。

本节四个 HTTP operation 的闭合 DTO schema 见 [`schemas/keypackage-operations.schema.json`](../../artifacts/schemas/keypackage-operations.schema.json)。OpenAPI 与 `sync/service-http-binding.md` 的字段表 MUST 引用同一 schema fragment；不得再以开放 `OperationRequest` / `OperationResult` 作为这些安全敏感路径的 generated-SDK 契约。

推荐操作：

```http
POST /_cokret/self/keys/keypackages/upload
POST /_cokret/self/keys/keypackages/claim
POST /_cokret/self/keys/keypackages/consume
POST /_cokret/self/keys/keypackages/revoke
```

`upload` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `principal_id` | `did` | required | KeyPackage 所属 principal。 |
| `device_id` | `id:device` | required | KeyPackage 所属设备。 |
| `key_packages` | `object[]` | required | MLS KeyPackage 与 metadata；每项 MUST 带 unique `keypackage_id` 和 `keypackage_ref`。 |
| `device_signature` | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。 |

`claim` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `target_principal_id` | `did` | required | 被邀请或加入的 principal。 |
| `target_device_ids` | `array<id:device>` | optional | 为空时由服务选择可用设备。 |
| `intended_realm_id` | `id` | required | 目标 Realm。 |
| `requester` | `did` | required | 发起 claim 的 actor 或 service DID。 |
| `required_capabilities` | `string[]` | required | 需要的 content / MLS / policy profile。 |
| `minimal_metadata_allowed` | `boolean` | optional | 是否允许 pseudonymous credential。 |
| `claim_nonce` | `string` | required | 防重放随机数。 |
| `expires_at` | `datetime` | required | claim 有效期。 |
| `proofs` | `proof[]` | required | requester / service / device proof。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、`keypackage_digest`、device binding、expiry、capabilities 和 `capabilities_digest = sha256(JCS(capabilities))`。 |
| `failures` | `object[]` | optional | 不可领取设备与原因；不得泄露不可见用户或设备。 |

`consume` request MUST validate `schemas/keypackage-operations.schema.json#/$defs/key_packages_consume_request_body`，并由 Welcome 接收方或授权发送方在 Welcome 成功处理后调用，绑定 `key_package_refs[]`、`consumer_device_id`、`signature`，以及可选 `claim_ids[]`、`welcome_ref`、`realm_id`、`strand_id`、`mls_group_id`、`epoch`。`revoke` request MUST validate `#/$defs/revoke_request`，可由设备、principal controller 或 policy 授权服务发起。

规则：

- `claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST NOT 返回该 KeyPackage。
- **`required_capabilities` ⊆ KeyPackage `capabilities`（normative subset rule）**：claim request 中的 `required_capabilities` 集合 MUST 是被领取 KeyPackage 上声明的 `capabilities`（见 [`encryption-and-audit.md` §2.6 KeyPackage payload](./encryption-and-audit.md)）的**子集**。任何 `required_capabilities ∖ capabilities ≠ ∅` 的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，但服务端 SHOULD 在内部审计日志中记录 `keypackage_capability_overreach` 以便滥用检测）。该规则避免了"客户端在 claim 时声明超过 KeyPackage 实际声明的能力，使后续 Welcome / Commit 在错误能力假设下进行"的隐性越权。
- Device / Key Server 在 claim 成功响应中返回的每条 claim MUST 包含 `keypackage_digest = canonical_digest(KeyPackage bytes)`、`capabilities_digest = sha256(JCS(capabilities))`，并携带 claimed 设备的 trust binding。cross-signing 设备携带当前 accepted `ssk_generation`；§5.4 service-attested / enrollment-authority 设备携带该设备 accepted `ck.device.authorize` 的 `device_authorize_event_id`。二者 MUST 精确二选一。`ck.mls.welcome` MUST 回填同一 KeyPackage hash 到顶层 `payload.keypackage_digest` 和 `payload.claim_ref.keypackage_digest`，回填同一 digest 到 `payload.claim_ref.capabilities_digest`，并把 claim record 的 trust binding 原样回填到 `payload.claim_ref`；Welcome 接收端在解密前必须比对这些值与本地 claim 记录，并确认该 trust binding 仍指向 claimed 设备当前 accepted state，防止 group manager 或中间服务在 Welcome 阶段替换 KeyPackage、扩大 KeyPackage 能力集合、复用旧 SSK generation 或旧设备授权事件的 claim。
- `payload.claim_envelope` 是 requester 对本次 Welcome 的独立签名 transcript，签名身份绑定 requester 而不是被 claim 的设备。cross-signing requester MUST 在 envelope 中携带 requester 当前 accepted `ssk_generation`，并用该 generation 的 SSK 签名；service-attested / enrollment-authority requester MUST 在 envelope 中携带 `requester_device_id`，并用该设备当前 accepted `ck.device.authorize.payload.device_public_key` 对 envelope canonical bytes 签名。二者 MUST 精确二选一。服务端和接收端 MUST 校验 envelope 的 `requester_did`、`requester_device_id`（若存在）、signature `kid` 与当前未撤销设备投影一致；不得把 claim/claim_ref 中属于 recipient KeyPackage 的 `device_authorize_event_id` 当作 requester 签名身份使用。
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备和 policy denied 做反枚举处理。对外错误码 SHOULD 合并为单一不透明错误码 `claim_failed`，不得返回可区分失败原因的 error message。服务端 SHOULD 使用统一状态码、最小响应体、限速和延迟填充降低时序侧信道；实现不得故意让不同失败原因产生稳定可测的响应差异。
- 设备 SHOULD 维持 `keypackage_min_available` 低水位，默认 8。Device / Key Server 的 claim / query 响应 SHOULD 返回调用方可见的 `available_count`；客户端发现可用 KeyPackage 低于低水位时，MUST 在下一次 sync / device maintenance 周期补充上传，避免邀请路径因耗尽而失败。
- claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转为 revoked / unusable 状态；服务不得把它自动放回 `published`，也不得接受迟到的 consume。设备需要重新发布新的 KeyPackage。
- Device / Key Server MUST 维护过期扫描或等价触发：KeyPackage `expires_at`、claim `expires_at`、device revoke、principal control state 失效、capability revoke 或 Realm policy 变更任一发生时，后续 `query` / `claim` MUST NOT 返回该 KeyPackage；后台清理不得是唯一防线。扫描周期 SHOULD ≤ 60s，且每次 `claim` 路径必须先做同步 freshness 判定。
- KeyPackage claim MUST 对 `(requester_service_did, target_principal_id)` 做限速，默认窗口为 60s 内最多 5 次 claim 尝试。超过限额时对外仍使用反枚举响应（`claim_failed` 或通用 rate-limited envelope，不泄露目标存在性）；服务端内部审计 reason 记录为 `keypackage_claim_rate_limited`。
- claim record SHOULD 被 Principal Server / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private Realm / MLS group 的明文目标信息。

### 9.1 KeyPackage 状态机（normative）

上述分散规则共同定义下列受控状态机，单段 KeyPackage（由 `keypackage_ref` 标识）的合法状态与转换为：

| 状态 | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `published` | 已 upload，可被 claim | `claimed`（原子 claim）、`revoked`（device revoke / principal 失效 / KeyPackage `expires_at` 到期）、`retired`（account deactivation，§7.1） | 否 |
| `claimed` | 已被某次 claim 原子占用 | `consumed`（Welcome 成功处理后 consume）、`revoked`（claim `expires_at` 到期 / device revoke / capability revoke） | 否 |
| `consumed` | 已被 Welcome 消费 | —（终态） | **是** |
| `revoked` | 因过期 / 吊销 / policy 失效不可用 | —（终态） | **是** |
| `retired` | account deactivation 标记的 unused KeyPackage | —（终态） | **是** |

转换约束：

- **`published → claimed` 原子**：`claim` MUST 原子转换；同一 `keypackage_ref` 不得被多个 active claim 占用。
- **`claimed` 不回 `published`**：claimed 但未 consume 的 KeyPackage 到达 claim `expires_at` 后 MUST 转 `revoked`，服务 MUST NOT 自动放回 `published`，也 MUST NOT 接受迟到的 consume。
- **终态集合**：`{ consumed, revoked, retired }` 均为 terminal，任何转出 MUST 被拒绝。`published` / `claimed` 的过期或吊销一律收敛到 `revoked`（claim 路径同步 freshness 判定，扫描周期 SHOULD ≤ 60s，见上）。
- **`retired`**：仅 account deactivation fanout（[`../identity/account-lifecycle.md` §7.1](../identity/account-lifecycle.md)）把 unused（`published`）KeyPackage 标 `retired`；已 `claimed` / `consumed` 的不改写。新邀请 MUST NOT 从 `retired` / `revoked` / `consumed` 的 KeyPackage 选取。

## 10. Verification Strands

设备密钥验证用于确认“这个 principal/device/key 是否是用户想信任的对象”。验证成功本身不授予登录态、Realm 权限或长期设备权力：

- 同一 principal 的新设备登录，验证成功后仍 MUST 通过 `ck.device.authorize`、DID/key-log operation 或 recovery policy 把设备加入有效设备集合。
- 跨 principal 验证只表达人工信任；通常由本地 `user_signing_key` 签名对方 identity key 或设备 key，不得改变对方设备授权状态。
- `ck.session.grant` 只授予短期会话能力；不得因 SAS/QR 成功而自动升级为长期设备授权。

### 10.1 标准消息类型

Cokret 标准验证消息通过 to-device 通道发送：

- `ck.key.verification.request`
- `ck.key.verification.ready`
- `ck.key.verification.start`
- `ck.key.verification.accept`
- `ck.key.verification.key`
- `ck.key.verification.mac`
- `ck.key.verification.done`
- `ck.key.verification.cancel`

所有验证消息 content MUST 包含：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `transaction_id` | `string` | required | 交易 ID；对参与 principal/device 组合唯一，长度 1..128，不能复用已完成或已取消交易。 |
| `from_device` | `id:device` | required | 发送设备；MUST 等于 envelope 的 `sender_device_id`。 |

各消息的额外字段：

| `kind` | 额外必填字段 | 说明 |
| --- | --- | --- |
| `ck.key.verification.request` | `methods`, `timestamp`, `expires_at` | 发起验证。`methods` 使用标准方法名，例如 `ck.sas.v1`、`ck.qr.v1`。同 principal 新设备授权请求 SHOULD 另带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`、`challenge_signature`、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`；这些字段必须进入 SAS/QR transcript 或等价 proof 绑定。 |
| `ck.key.verification.ready` | `methods` | 接受请求并回报本设备可用方法。 |
| `ck.key.verification.start` | `method` | 选择方法并开始。SAS 还 MUST 带 `key_agreement_protocols`、`hashes`、`message_authentication_codes`、`short_authentication_string`。 |
| `ck.key.verification.accept` | `commitment` | 接受 `start` 并提交本端 ephemeral key 承诺；还 MUST 固定选定算法。 |
| `ck.key.verification.key` | `key` | 发送本端 ephemeral public key。 |
| `ck.key.verification.mac` | `mac`, `keys` | 发送待验证 key 的 MAC 与 key-id MAC。 |
| `ck.key.verification.done` | none | 双方 MAC 验证通过后完成。MAY 带本地生成的签名摘要。 |
| `ck.key.verification.cancel` | `code` | 任意阶段取消；`reason` MAY 给出面向用户的短说明。 |

### 10.2 状态机、超时与并发

标准交互状态机为：

```text
request -> ready -> start -> accept -> key -> mac -> done
```

`cancel` MAY 在任意阶段发送。接收方 MUST 对重复的同一消息做幂等处理；对越序或状态不匹配的消息 MUST cancel，`code=unexpected_message`。

请求超时规则：

- `request.timestamp` 不能比接收设备本地时间晚 5 分钟以上。
- `request.expires_at` MUST be no later than `timestamp + 10m`。
- 用户在展示提示后 2 分钟内没有交互，客户端 SHOULD 本地取消或隐藏提示。
- 过期交易的后续消息 MUST 被忽略或以 `code=timeout` 取消。

并发规则：

- `request` 可以发送给同一 principal 的多个设备；`ready` 之后实际验证 MUST 收敛到两个具体设备。
- 一台接收设备接受后，发起方 SHOULD 向其他待处理设备发送 `cancel`，`code=accepted_by_other_device`。
- 交易完成或取消后，`transaction_id` MUST NOT 在相同 principal/device 组合中重用。

### 10.3 SAS 验证

SAS 验证 MUST 绑定：

- 双方 principal id
- 双方 device id
- 双方 device verify key
- transaction id
- chosen method and algorithms

`accept.commitment` MUST 是对本端 ephemeral public key 与 canonical `start` 消息的哈希承诺。收到 `key` 后，接收方 MUST 重算 commitment；不一致 MUST cancel，`code=mismatched_commitment`。

MAC 阶段 MUST 覆盖完整 transcript，包括双方 principal id、device id、device verify key、transaction id、method、算法选择、双方 ephemeral key 和待验证 key id。任何 transcript 不一致 MUST cancel，`code=mismatched_mac`。

Transcript 中的双方 principal/device MUST 与 `DeviceMessageEnvelope` 的 sender/recipient 字段一致；不一致时 MUST cancel，`code=mismatched_mac` 或 `unexpected_message`。

SAS 展示值 MUST 从同一 transcript 派生。用户确认前，客户端不得把对方 device key 标记为 verified。

### 10.4 QR 验证

QR 验证 MUST 使用一次性 secret 或 public commitment，且 QR 内容 MUST 有过期时间和 intended verifier。

QR payload MUST 至少绑定：

- `transaction_id`
- 展示端 principal id 与 device id
- intended verifier principal id；若已知，还 SHOULD 绑定 intended verifier device id
- 一次性 secret 或 public commitment
- `expires_at`
- supported verification method

QR payload MUST NOT 包含长期私钥、secret storage key、recovery secret 或 MLS group secret。扫码后，客户端仍 MUST 通过 to-device transcript 完成 `mac` / `done`，不能只凭扫码动作直接信任设备。

### 10.5 成功后的动作

同一 principal 的新设备配对完成后，已授权设备 MAY：

1. 签发 `ck.device.authorize` 或符合 DID method 的 key-log operation。
2. 发布 `ck.device.list_update`。
3. 在用户或 policy 允许时，通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome。

当验证目的为 `same_principal_device_authorization` 时，用户确认后的授权落地 MUST 发生在 `/_cokret/gate/account/*` 认证面，默认使用 `ck.gate.account.command.pair_device`。旧设备把验证 transcript 中绑定的 `pairing_code`、`new_device_pubkey`、`challenge_signature` 以及自身 fresh device proof 提交给 gate；gate 返回的 `authorized_event_ref` 只是 durable `ck.device.authorize` / `ck.device.list_update` 已被接受的引用或等价结果。新设备可通过同一 to-device transcript 的 `ck.key.verification.done` 中的 `authorized_event_ref` hint、后续 full `ck.self.account.stream.subscribe` device list baseline，或重新通过 `ck.gate.account.command.issue_session_grant` 升级会话来观察授权结果；它 MUST 验证 durable device list，而不得把 `done` 消息本身当成授权真相源。

跨 principal 验证完成后，客户端 MAY 使用 `user_signing_key` 对对方 principal identity key 或 device key 生成信任签名。该签名只影响本 principal 的信任视图，不授予对方 Realm capability。

### 10.6 Cancel Code Registry

标准 cancel code：

| code | 含义 |
| --- | --- |
| `user_cancelled` | 用户主动取消。 |
| `timeout` | 交易过期或交互超时。 |
| `unknown_transaction` | 本设备不存在该交易。 |
| `unexpected_message` | 消息与当前状态机不匹配。 |
| `unsupported_method` | 无共同验证方法。 |
| `unsupported_algorithm` | 无共同 key agreement、hash、MAC 或 SAS 表示算法。 |
| `mismatched_commitment` | ephemeral key commitment 校验失败。 |
| `mismatched_mac` | MAC 或 key-id MAC 校验失败。 |
| `device_revoked` | 任一参与设备已撤销。 |
| `untrusted_device` | policy 要求验证设备，但设备信任链不满足。 |
| `policy_denied` | Realm、组织或账号 policy 拒绝。 |
| `accepted_by_other_device` | 同一请求已被另一设备接受。 |
| `cross_signing_reset` | 验证过程中检测到 cross-signing reset，旧 SSK generation 已废止；详见 §14.3。 |

### 10.7 Secret Sharing（`ck.secret.*`）

§10.5(3) 允许已授权设备在验证成功后“通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome”。本节把该动作收敛为两个标准 to-device kind，用于把账户级 secret（如 MLS account secret / secret storage bootstrap key）从一台已授权设备直传给同一 principal 的另一台已通过 §10.3 SAS 验证的设备，无需用户重新输入恢复口令。它是 [`identity/key-management.md` §7](../identity/key-management.md) 无口令恢复路径的设备直传分支，服务端零知识。

标准 kind（均为 `wire_scope=ephemeral_event`，走 §7 to-device 通道，不进入任何持久 timeline）：

- `ck.secret.request`：请求设备（通常是新设备）向已授权设备索取某个 `secret_id`。
- `ck.secret.send`：被请求设备把 secret 以 HPKE 密封后回传给请求设备。

两者 content 闭合形态见 [`schemas/device-message.schema.json`](../../artifacts/schemas/device-message.schema.json) 的 `secret_request_content` / `secret_send_content`。

`ck.secret.request.content` 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 调用方生成的随机关联 id；MUST NOT 在被应答或取消后重用。 |
| `secret_id` | `string` | required | 被请求 secret 的不透明标识，例如 `org.example.mls_account_secret`。 |
| `from_device` | `id:device` | required | 请求（新）设备；MUST 等于 envelope 的 `sender_device_id`。 |
| `recipient_hpke_public_key` | `string` | required | 请求设备控制的 base64url X25519 HPKE 公钥，被请求设备据此密封。它 **MUST** 逐字节等于目标 `from_device` 在该 principal 设备集投影（§4 device record / §6 device list）中登记的权威 `hpke_key`；不等即 fail closed（见下方规则）。**MUST NOT** 仅因该公钥"看似格式合法"或与某条 SAS transcript 内某值相符就接受——SAS（§10.3）只验证双方 device verify key（Ed25519），不覆盖 HPKE（X25519）密封密钥，故密封目标公钥必须独立绑定到权威 `hpke_key`。 |

`ck.secret.send.content` 字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `request_id` | `string` | required | 关联到 pending 的 `ck.secret.request`；MUST 等于密封 plaintext 内被认证的 `request_id`。 |
| `secret_id` | `string` | required | 与请求一致的 secret 标识。 |
| `from_device` | `id:device` | required | 授权（已有）设备；MUST 等于 envelope 的 `sender_device_id`，且 MUST 是接收 principal 的未撤销设备。 |
| `scheme` | `string` | required | MUST 为 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active suite id；v1 default-MUST 为 `ck.hpke_x25519_aead_xchacha20poly1305.v1`。未登记 / 非 active suite MUST fail closed（`unsupported_hpke_suite`）。 |
| `enc` | `string` | required | base64url HPKE（RFC 9180）封装密钥（KEM 输出）。 |
| `ciphertext` | `string` | required | base64url HPKE AEAD 密文。HPKE AAD 见下方定义。 |

HPKE AAD（本 kind 的具体绑定）MUST 是对以下字段的 canonical JSON（RFC 8785 JCS）：`kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、content 中的 `request_id`、content 中的 `secret_id`，以及把 `expires_at` 归一化为整数 Unix 秒后的字段 `expires_at_unix`。principal / device 字段为字符串、`request_id` / `secret_id` 为 content 中的原始字符串、`expires_at_unix` 为整数，在收发两端都可从 `DeviceMessageEnvelope` 与 `ck.secret.send.content` 确定性重建（归一化为整数避免 RFC3339 字符串在 `DateTime` 往返序列化中重排——如 `Z` 与 `+00:00`、小数秒——导致 AAD 不一致；队列服务 MUST NOT 重写这些字段）。把 `request_id` / `secret_id` 同时放入 AAD 与 sealed plaintext 可防止中间层替换外层关联字段后诱导接收方把同一 ciphertext 解释为另一项 pending secret。§7 的通用 AAD 最小集还要求覆盖 `sent_at`；由于 to-device 队列在物化时由服务端赋 `sent_at`，发送方在密封时无法预知它，因此本 kind 改由密封 plaintext 内携带并被 AAD 绑定的一次性 `request_id` 提供等价的抗重放/新鲜性绑定。

`ck.secret.send` 的 plaintext（仅 HPKE 解封后可见，不出现在 wire 任何明文字段）MUST 至少携带被请求 secret 本体、其版本号、`request_id` 与 `secret_id`；接收方解封后 MUST 校验内层 `request_id` / `secret_id` 与外层 content 一致、且 `request_id` 命中本端某个 pending 请求，否则丢弃。

规则（normative）：

- 时序：`ck.secret.request` / `ck.secret.send` MUST 在两台设备完成 §10.3 SAS 验证之后发送。请求与发送绑定的设备 MUST 与该 SAS transcript 绑定的 device key 一致，防止“验证设备 A、把 secret 发给设备 B”。
- TTL：二者受 §7 队列 TTL 约束；`ck.secret.send` SHOULD 使用更短 `expires_at`（推荐 10–60 分钟）。
- 用户在环：被请求设备在发送 `ck.secret.send` 前 MUST 经用户显式授权，并 MUST 校验目标 device ∈ 本 principal 当前授权设备集合且未撤销。
- 密封密钥绑定（normative）：被请求设备在密封并发送 `ck.secret.send` 前，MUST 校验请求中的 `recipient_hpke_public_key` 逐字节等于目标 `from_device` 在设备集投影（§4 device record / §6 device list，经 §8.3 Tier-2 链验证后视为权威）中登记的 `hpke_key`；不等 MUST fail closed（不密封、不发送），并 SHOULD 提示用户该请求异常。该校验闭合"验证设备 A 的 verify key、却把账户级 secret 密封给攻击者控制的 X25519 公钥"这一密钥绑定缝隙——它独立于 §10.3 SAS（SAS 只绑 verify key）。注：device `hpke_key` 由签名的 `ck.device.authorize` 事件承载、有事件签名链完整性背书，但当前 §5.2 `cross_signing_binding` 只覆盖 `device_public_key`（verify key）；把 `hpke_key` 一并纳入 cross-signing transcript 覆盖是更强绑定的后续硬化方向。
- 反滥用：接收方 MUST 丢弃 unsolicited `ck.secret.send`（无本端 pending `request_id`）；`request_id` 用后即作废；对同一 `from_device` 的重复请求 SHOULD 限速；多次拒绝 SHOULD 提示用户考虑撤销该设备。
- 审计：被请求设备 SHOULD 记录一次 secret 共享审计（如 `ck.audit.accessed`，`access_kind=secret_share`）。
- 止损：误授权后，用户从任一已授权设备发起 §2.2 设备撤销并轮换对应 account secret、重新封装全部备份即可使被泄露设备失效。
- QR：与 §10.4 一致，QR payload 仍 MUST NOT 直接携带任何 secret 本体；secret 只经本节 HPKE 密封的 `ck.secret.send` 传输。

## 11. Secret Storage（client-local cache form）

Secret storage 用于保存：

- `self_signing_key`
- `user_signing_key`
- recovery secret
- MLS group secrets backup key
- applet delegated device secret

`ck.secret_storage.v1` 是 **client-local** envelope，仅用于设备本地或可信操作系统 keychain；**不得作为线级 (wire) 上传格式**。

Device / Key Server 的 `ck.keys.backups.*` endpoint MUST 只接受 `ck.schema.key_backup.v1` wire envelope。任何不符合 `ck.schema.key_backup.v1` 顶层 `required`（含 `series_id` / `series_seq`）的请求体 MUST 返回 `schema_violation`，原因码 `key_backup_wire_schema_required`。Client-local `ck.secret_storage.v1` 存储不受影响，但 MUST NOT 通过 `PUT /_cokret/self/keys/backups/{backup_id}` 同步。

任何同步到 Device / Key Server 或其它远端服务的 secret，MUST 使用 §12 的 `ck.schema.key_backup.v1` envelope，并设置对应 `backup_class`：

| Secret 类别 | `backup_class` |
| --- | --- |
| DID 恢复材料 | `did_recovery` |
| `self_signing_key`、`user_signing_key`、recovery secret 等账户级 secret | `secret_storage` |
| MLS epoch / Realm history secret | `mls_history` |
| 外部托管或 profile 自定义 account secret | `secret_storage` |

每个 `backup_class` MUST 使用独立 HKDF info 字符串派生 commitment / wrap key，禁止跨 class 共享密钥材料。规范权威表述见 [`../identity/key-management.md` §7.1](../identity/key-management.md)：HKDF info 形如 `cokret-key-backup/<backup_class>/<subdomain>/v1`（`/` 分隔，含 subdomain 维度）。任何 v1 wire 实现 MUST 跟随 `identity/key-management.md` 的 canonical 形式，本节描述只作为引导。

Client-local secret storage 的存储格式仍可使用本节的 `ck.secret_storage.v1` envelope，但其字段不进入任何 wire / hash / 签名输入；服务端不接受该 envelope。

## 12. Key Backup

Key backup 保存已加密的 Realm / MLS 历史密钥材料。它只覆盖当前 actor 已经通过 membership、history visibility 和 Realm policy 获得的历史范围，不是给未来新成员预先保留历史 secret 的机制。

备份单元使用 `ck.schema.key_backup.v1`，并设置 `backup_class="mls_history"`。示例：

```json
{
  "backup_id": "ck:backup:01964138-8000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "backup_class": "mls_history",
  "backup_version": "kb_1",
  "series_id": "ck:backup_series:01964138-1000-7000-8000-000000000000",
  "series_seq": 0,
  "supersedes": null,
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": {
    "recipient_method": "secret_storage_key",
    "recipient_key_ref": "mls_group_secrets_backup_key",
    "aead": {
      "name": "xchacha20_poly1305",
      "aead_profile": "ck.aead.xchacha20_poly1305.v1",
      "nonce": "base64url..."
    }
  },
  "domain_separation": {
    "hkdf_info": "cokret-key-backup/mls_history/mls_epoch/v1",
    "subdomain": "mls_epoch",
    "aead_aad": {
      "schema": "ck.schema.key_backup.v1",
      "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
      "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
      "backup_class": "mls_history",
      "backup_version": "kb_1",
      "created_at": "2026-04-26T00:00:00Z",
      "item_types": ["mls_epoch_secret"]
    }
  },
  "contents": [
    {
      "item_type": "mls_epoch_secret",
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "mls_group_id": "base64url",
      "epoch": 42,
      "first_event_id": "ck:event:019640ed-8000-7000-8000-000000000000",
      "last_event_id": "ck:event:019640ee-0000-7000-8000-000000000000"
    }
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "auth_data": {
    "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ck_device_01964137",
    "signature_algorithm": "Ed25519",
    "signature": "base64url...",
    "signed_fields": [
      "backup_id",
      "actor_id",
      "backup_class",
      "backup_version",
      "series_id",
      "series_seq",
      "supersedes",
      "encryption",
      "domain_separation",
      "contents",
      "ciphertext_digest"
    ]
  }
}
```

备份 MUST 加密给 recovery public key 或 secret storage key。服务端 MUST NOT 能解密。

> **Recipient method 与 fresh-device 恢复（normative）**：上例的 `recipient_method="secret_storage_key"` 仅适用于**已经持有 secret_storage root key 的现有设备**（见 `identity/key-management.md` §7.5.3）。**全新设备 / 新浏览器**在尚未解锁 secret_storage root 之前 MUST NOT 直接用 `secret_storage_key` envelope 恢复 `mls_history`；它 MUST 走以下两步之一：
> 1. **recovery_public_key（推荐，HPKE）**：`mls_history` envelope 直接加密给 actor 的 recovery public key（`recipient_method="recovery_public_key"`，HPKE base mode，参数见 `identity/key-management.md` §7.5.2）。新设备用经 recovery policy 解锁的 recovery 私钥即可 HPKE-open，无需先持有 secret_storage root。这是 fresh-browser same-account MLS 恢复的规范路径。
> 2. **先解 root，再用 secret_storage_key**：新设备先用 `passphrase_kdf`（`passphrase_kdf` envelope，见 `identity/key-management.md` §7.5.1），或经 recovery policy 释放 recovery private key 后用 `recovery_public_key` 解出 `secret_storage` 域的 root（取得 `mls_group_secrets_backup_key`），之后才能解 `secret_storage_key` 的 `mls_history` envelope。
>
> `recipient_method` 取值 MUST 来自 `ck.schema.key_backup.v1` 的枚举（`passphrase_kdf` / `recovery_public_key` / `secret_storage_key`）。实现 MUST NOT 发出枚举外的值（例如 `device_snapshot_secret`、`threshold_recovery`、`hardware_wrapped_key` 不是合法 wire 值，receiver/validator MUST fail closed）。threshold / hardware / trusted recovery service 是 recovery policy / proof 层的 unlock factor，不是 backup envelope recipient method。

规则：

- 备份 metadata MUST 绑定 actor DID、device id、backup id、backup class、created_at、ciphertext digest 和加密参数。
- `backup_class="did_recovery"` 的 wire envelope MUST 使用 `recipient_method="recovery_public_key"`，并携带顶层 `recovery_policy_ref{policy_id, policy_version}`，且与当前 accepted recovery policy 一致；不一致 MUST `recovery_policy_mismatch`。`mls_history` 与 `secret_storage` envelope MAY 携带 `recovery_policy_ref` 作为恢复流程 hint；若出现，receiver MUST 验证它与当前 accepted recovery policy 一致，但不得用它替代 active-series record、frontier_ref 或 Realm/MLS 授权校验。
- 上传设备 MUST 通过 `auth_data` 对 backup metadata 与 ciphertext digest 签名，并 SHOULD 携带 `auth_data.ssk_generation` 绑定当前 accepted `ck.cross_signing.publish.generation`（加固档 `ck.profile.*.e2ee.v1` 等 hardening profile 下 MUST 携带并纳入 `signed_fields`；core schema 不把 `ssk_generation` 列为 required，故核心档下缺失时不报 schema `schema_violation`。但对高敏 `backup_class ∈ {secret_storage, did_recovery}`，receiver 即便在 core 档下也 MUST 在缺失 `ssk_generation` 时 fail-closed，详见 [`identity/key-management.md` §7.4.1](../identity/key-management.md)；`mls_history` 类缺失时按 hardening profile 策略处置）。`auth_data.signed_fields` MUST 至少覆盖 `backup_id`、`actor_id`、`backup_class`、`backup_version`、`series_id`、`series_seq`、`supersedes`、`encryption`、`contents` 与 `ciphertext_digest`；非 genesis envelope 还 MUST 覆盖 `supersedes_digest`，携带 `frontier_ref` 时还 MUST 覆盖 `frontier_ref`，携带 `recovery_policy_ref` 时还 MUST 覆盖 `recovery_policy_ref`。签名链必须链接到当前 principal 的 self-signing / device trust chain。
- 服务端 MUST 只允许同一 actor 的当前授权设备、满足 recovery policy 的恢复流程，或 policy 明确授权的组织恢复服务读取备份密文。
- 服务端返回备份列表时 SHOULD 最小化 metadata；不得向无关 caller 暴露 Realm membership、MLS group id 或历史范围。
- 删除备份只删除服务端密文和 metadata；它不撤销 DID 控制权，也不改变 Realm membership。需要吊销设备或轮换 MLS epoch 时必须发布相应事件。
- 被撤销设备上传的新备份 MUST 被拒绝。撤销前上传的备份 MAY 继续保留，但恢复使用时必须重新验证当前 recovery policy、device revocation state 和 Realm history visibility。
- **Series & freshness**：所有 wire envelope MUST 满足 `identity/key-management.md` §7.6 的 series 链规则（`series_id` / `series_seq` / `supersedes` / `supersedes_digest`）。Receiver 在恢复或读取时 MUST 先用 `ck.key_backup.active_series` / `ck.schema.key_backup_active_series.v1` signed active-series record 确认 canonical `series_id`（当同一 `(actor_id, backup_class)` 存在多个 series 时），再重建链并仅使用尾部 envelope；服务端 MUST NOT 重写、改写或省略已上传 envelope 的链字段，除非按 §12.2 retention 流程整组迁移。

### 12.1 Backup API

Device / Key Server 对 encrypted backup object 提供标准操作：

```http
PUT /_cokret/self/keys/backups/{backup_id}
GET /_cokret/self/keys/backups
POST /_cokret/self/keys/backups/{backup_id}/unlock
DELETE /_cokret/self/keys/backups/{backup_id}
```

`PUT` 请求体 MUST 是 `ck.schema.key_backup.v1`，且 path 中的 `backup_id` MUST 与 body 中的 `backup_id` 一致。`PUT` 按 `(actor_id, backup_id)` 幂等；同一 `backup_id` 若提交不同 canonical content MUST 返回冲突错误。

`PUT` 还 MUST：(a) 校验 `series_seq` 严格大于该 series 已有的最大 sequence（首条 MUST `series_seq=0`）；(b) 校验 `supersedes` 引用的前一条 envelope 存在、`actor_id` / `series_id` 匹配，并由当前 caller 可见；(c) 校验 `supersedes_digest` 等于服务端持有的前一条 canonical_json digest（排除 `auth_data.signature`）；任一失败 MUST 返回 `409 Conflict`，reason 分别为 `series_seq_not_monotonic` / `series_predecessor_not_found` / `series_chain_broken`。

`GET /_cokret/self/keys/backups` 支持 `?series_id=<series_id>` 与 `?backup_class=<class>` 过滤；响应 MUST 按 `series_seq` 升序返回该 series 的全部 envelope metadata，便于 client 重建链。当仅按 `backup_class` 查询且返回多个 series 时，server / client MUST NOT 用返回顺序、最大 `series_seq` 或最新 `created_at` 推断 active series；恢复方 MUST 使用 `identity/key-management.md` §7.6 的 `ck.key_backup.active_series` / `ck.schema.key_backup_active_series.v1` signed active-series record。`list` 响应只返回调用方可见的 backup metadata、digest 和 retention hints；不得越过 `identity/key-management.md` §7.8 的限速。

`unlock` 返回完整 encrypted backup object：request body MUST 携带 `ck.schema.key_backup_unlock_proof.v1`（见 `identity/key-management.md` §7.7.1），并受 §7.8 的 fresh device proof 与 rate limit 约束。`delete` MUST 要求当前设备证明、DID proof 或 recovery policy 允许的高风险证明；active series 内的非尾部 envelope MUST NOT 被单独删除，删除链尾部 envelope MUST 同时附 §15 风格的 high-risk proof（principal_signing / device_quorum / trusted_recovery_service）并写入高风险审计。

### 12.2 Retention and Erasure

| Profile | `delete_after` 默认 | `legal_hold` 行为 |
| --- | --- | --- |
| `ck.profile.personal_node.v1` | `null`（无自动过期） | clients-only flag；服务端不强制 |
| `ck.profile.small_team.v1` | `null` | 仅在组织声明 `ck:policy:<id>` 允许时可置 `true` |
| `ck.profile.organization.v1` | 365d（可被 Realm policy 覆盖） | 服务端 MUST 在 `legal_hold=true` 时阻塞 user-initiated delete |
| `ck.profile.high_security_organization.v1` | 90d | 服务端 MUST 强制 `legal_hold` 与审计配对 |
| `ck.profile.sovereign_deployment.v1` | deployment-defined | 与本地法务合规框架对齐 |

要求：

- 服务端 MUST 在收到 user erasure 请求（参见 `ck.audit.erasure_receipt` / `ck.schema.erasure_receipt.v1`）时，按 erasure receipt 的 `scope` 与 `subject` 处理对应 backup envelope：若 `subject.kind="principal"` 且 `scope.storage_boundary` 涵盖 `device_secret_store`，相应 `did_recovery` / `secret_storage` envelope MUST 被删除并产出 `ck.schema.erasure_receipt.v1` 子条目。
- 用户主动删除自身备份与 erasure 流程区分清晰：常规 `DELETE` 不写 erasure receipt，但 `identity/key-management.md` §7.8 的高风险审计仍要求落地 `ck.audit.accessed` (`access_kind="key_backup_delete"`).
- `legal_hold=true` 的 envelope MUST 被服务端拒绝删除（即便提供 high-risk proof）；解除 hold MUST 由声明该 hold 的 Policy Server 通过 policy update 完成，并写入审计。
- 同一 series 内的 retention 必须保证链不被打破：服务端 MUST NOT 删除 active series 的非尾部 envelope；旧 series 只有在已经被 active-series record 移出 primary source 后，才 MAY 按 retention / erasure 策略整组删除或迁移。
- erasure 完成后保留的 `retained_stub_digest` MUST 仅含 metadata 哈希，不含密文与 KDF 参数，以避免间接成为离线爆破证据。

## 13. Realm Key Share and Withholding

Cokret 使用 `ck.realm_key.share` 共享历史解密材料。共享前发送设备 MUST 检查：

- 接收设备属于目标 principal。
- 设备未撤销。
- 设备通过 self-signing 或人工验证，或 Realm policy 允许未验证设备。
- history visibility 允许该 principal 获取目标历史范围，且判定时点使用目标 Event range 的 deterministic `T0`，不得使用本地到达顺序或 wall clock。
- effective `ck.realm.history_sharing_policy` 允许该 receiver class、scope、epoch range 和 key source；当 Realm / Circle history visibility 为 `restricted` 时，必须命中 `restricted_rules[]`，否则 MUST withhold。
- `key_scope.policy_digest` 绑定本次判定使用的 Realm policy / MLS governance policy root；如判定依赖 membership frontier，`key_scope.membership_frontier_digest` SHOULD 同时写入。
- `sender_device_signature` MUST 覆盖发送设备、接收 principal/device、`key_scope`、`aad_digest?`、`ciphertext` 或 `encrypted_key_ref` 与 `created_at`。接收方 MUST 验证该签名链接到当前有效 sender device key，且不得只依赖传输层认证。
- 对 `history_visibility=joined` 的 scope，join 前 epoch key MUST 被拒绝；对 `invited`，share range MUST be no earlier than receiver 的有效 invite frontier；对 `shared`，join 前 history key share 仍需要 policy 明确允许；对 `world_readable`，E2EE key 不因 public history 自动公开。
- Archive Node、Key Recovery Service、Recovery Service 或 peer 不能因为持有备份副本就绕过上述检查；服务端 operator 权限不是 key share 授权。

拒绝共享时发送 `ck.realm_key.withheld`，其 payload 使用 `withheld_reason_code` 承载原因码：

- `unverified_device`
- `blacklisted_device`
- `not_member`
- `history_not_visible`
- `policy_denied`
- `unknown_session`

## 14. Cross-Signing Reset

重置 `self_signing_key` 或 `user_signing_key` 是高风险操作。实现 MUST 要求以下至少一种证明：

- principal DID 控制密钥签名。
- recovery key 解锁 secret storage。
- 已验证设备 quorum 签名。
- 受信任账户恢复服务签名，且该服务在 DID document 中声明。

重置后，先前设备签名链不再自动可信。客户端 MUST 将所有既有信任标记为 `needs_reverification`。

### 14.1 Reset Envelope

Reset 操作 MUST 写入一条 `ck.cross_signing.reset` 事件到 principal control stream，并在其后**立即**发布新的 `ck.cross_signing.publish`（§5.1）以使协议状态可恢复。实现还 MUST 生成可审计记录：在同一 ordered submit batch 或在 reset accepted 后的 bounded audit window 内写入 `ck.audit.accessed`，`access_kind="cross_signing_reset"`，`target_ref` 指向 reset event 或 principal control Realm，`purpose` 说明 reset reason；声明 active Audit Applet Binding 或 `ck.profile.attested_audit.e2ee.v1` 的部署 MUST 通过 `refs[role="audit_pair"]` 把 reset 与 audit event 配对，其它高安全部署 SHOULD 配对。

Schema id：`ck.schema.cross_signing_reset.v1`

`proof.kind` MUST be one of `principal_signing` / `recovery_unlock` / `device_quorum` / `trusted_recovery_service`，且必须符合 [`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json) 的 kind-specific shape。下面示例选用 `principal_signing`：

```json
{
  "kind": "ck.cross_signing.reset",
  "realm_id": "<principal_control_realm_id>",
  "actor_id": "did:webvh:...",
  "payload": {
    "trust_domain": "ck:trust_domain:did.webvh.example",
    "reset_event_id": "ck:event:0196414c-5000-7000-8000-000000000000",
    "principal_id": "did:webvh:...",
    "previous_generation": 1,
    "new_generation": 2,
    "reset_reason_code": "rotation",
    "proof": {
      "kind": "principal_signing",
      "verification_method": "did:webvh:...#ck_principal_signing_v1",
      "alg": "EdDSA",
      "signature": "base64url..."
    },
    "issued_at": "2026-04-26T00:00:00Z"
  }
}
```

Payload-only schema 示例（即 Event `payload` / 上例 `payload` 的规范形态）：

```json schema=schemas/cross-signing-reset.schema.json
{
  "trust_domain": "ck:trust_domain:did.webvh.example",
  "reset_event_id": "ck:event:0196414c-5000-7000-8000-000000000000",
  "principal_id": "did:web:alice.example",
  "previous_generation": 1,
  "new_generation": 2,
  "reset_reason_code": "rotation",
  "proof": {
    "kind": "principal_signing",
    "verification_method": "did:web:alice.example#ck_principal_signing_v1",
    "alg": "EdDSA",
    "signature": "c2ln"
  },
  "issued_at": "2026-04-26T00:00:00Z"
}
```

字段规则：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `previous_generation` | required | 被重置前的 `generation`；MUST 等于当前 accepted publish 的 `generation`。 |
| `new_generation` | required | 后续 publish 将使用的 `generation`；MUST = `previous_generation + 1`。 |
| `reset_reason_code` | required | 机器可读枚举：`rotation` / `compromise` / `device_loss` / `policy_required`。 |
| `proof` | required | 四类高风险证明之一，详见 §14；接收方 MUST 拒绝缺失 / 无效的 proof。 |
| `proof.recovery_session_id` | `recovery_unlock` 时 required | 当 `proof.kind = recovery_unlock` 时，proof body MUST 携带 §15 device recovery state machine 的 `recovery_session_id`（§15 step 2）。它随 `proof_body` 进入下方 §14.1 canonical transcript，使 `recovery_unlock` proof 自身携带 freshness binding，不依赖外部 state machine；receiver MUST 拒绝 `recovery_session_id` 与 `principal_id` 在 `issued_at` 时无活跃 recovery session 匹配的 reset。其余三类 proof 不携带此字段。 |

所有 proof 签名的 canonical input MUST 是：

```text
utf8("ck-cross-signing-reset-v1\n") ||
canonical_json({
  "trust_domain": trust_domain,
  "reset_event_id": reset_event_id,
  "principal_id": principal_id,
  "previous_generation": previous_generation,
  "new_generation": new_generation,
  "reset_reason_code": reset_reason_code,
  "issued_at": issued_at,
  "proof_kind": proof.kind,
  "proof_body": proof without signature fields
})
```

**`trust_domain` 与 `reset_event_id` 绑定（normative）**：

- `trust_domain` 是部署级的 trust 域标识，typed string，形如 `ck:trust_domain:<scope>`。它在每个 deployment 的 `ServiceDescribe.trust_domain` 与 Realm create object 的 `trust_domain` 中声明（详见 [`identity-did.md` §3.6 Trust Domain](../identity/identity-did.md)）。canonical input MUST 把当前 receive context 的 `trust_domain` 嵌入 proof transcript，使同一 principal DID 在 deployment A 签发的 reset proof 无法被 deployment B 重放——B 的 `trust_domain` 字符串不同，proof signature transcript 校验立即失败 (`invalid_signature`)。
- `reset_event_id` 是承载该 reset 的 Event Envelope 的 `event_id`（typed `ck:event:<uuidv7>`），由 producer 在签名前分配。把它纳入 transcript 确保同一 reset proof 不能复用到另一个 Event shell（不同 `event_id` ⇒ 不同 transcript ⇒ 签名失败）。这关闭了"复制 reset proof bytes，包到新 Event 里重放"的攻击面。
- 这两个字段同时是 `ck.cross_signing.reset` payload 的必填字段（[`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json) `trust_domain` / `reset_event_id`）。
- 接收方验证顺序：(a) 检查 `trust_domain` 与本 receiver 当前 trust 域一致；不一致直接 `cross_domain_replay_rejected`，不进入签名校验。(b) 检查 `reset_event_id == enclosing Event.event_id`；不一致 `reset_event_id_mismatch`。(c) 按上面 canonical input 重算 transcript 并验证每个 proof 的签名；任一不匹配 `invalid_signature`。
- 多 deployment 部署、sovereign trust domain、recovery service 跨域复用、device quorum 跨 trust domain 都受这两个字段保护——任一变化都会让 transcript 失配。

`recovery_unlock.unlock_commitment` 的派生输入 MUST 避免自引用：其
`unlock_binding_input_bytes` 使用与上面相同的字段集合，但 `proof_body`
MUST 同时排除 `signature` 字段和 `unlock_commitment` 字段。随后
`recovery_unlock.signature` 仍然覆盖上面的完整 canonical input，也就是覆盖已经
计算出的 `unlock_commitment`。

`device_quorum.signatures[]` 的每个设备签名分别覆盖同一 canonical input。`trusted_recovery_service` 的 `service_did` MUST 出现在 principal DID Document 的恢复服务声明中；未声明的服务签名无效。

每类 proof 的接收方验证规则见 §14.4；schema（[`cross-signing-reset.schema.json`](../../artifacts/schemas/cross-signing-reset.schema.json)）只编码 wire 形态最低限，签名 / 门限 / commitment 验证均为本节 normative。

### 14.2 `needs_reverification` 扩散规则

Receiver 接受 reset 后 MUST 按以下顺序更新本地状态：

1. **本 principal 名下所有设备**的 trust state 强制从 `cross_signed` / `verified` 降为 `needs_reverification`。设备本身不被撤销，可以继续读写已经获得 capability 的 Realm；但 sender-side trust UI MUST 显示警告，且任何要求 cross-signed 的策略（例如 `ck.realm.policy.require_cross_signed`）MUST 重新计算。
2. **本 principal USK 签发的跨 principal 信任**全部进入 `needs_reverification`：对方在自己视图里看到的"由 X 验证过我"提示 MUST 消失，需要等待新一轮 USK publish 与人工再确认。
3. **MLS leaf credential** 不直接因 reset 失效——MLS credential 由 device key 与 KeyPackage 单独签名。但发送方 SHOULD 在 reset 后发送的第一个 outbound MLS handshake 中发起一次 Empty Commit，让 epoch transcript 在新 SSK generation 下重新被覆盖；接收方 MUST 允许该 commit 推进。
4. **in-flight verification transaction**（§10 状态机里仍在 `request` / `ready` / `start` / `accept` / `key` / `mac` 阶段的）MUST 以 `code=cross_signing_reset` cancel，禁止把基于旧 SSK 的 SAS / QR transcript 用旧 generation 完成。
5. **To-device 队列隔离**：reset accepted 后，服务端和客户端 MUST drop 或 quarantine 所有已排队但尚未处理的 `ck.key.verification.*` to-device 消息，以及任何未显式绑定 `new_generation` 的 cross-signing / trust bootstrap 消息。隔离窗口内仅允许 `ck.key.verification.cancel(code=cross_signing_reset)`、新的 `ck.cross_signing.publish` 可验证通知和重新发起的、显式绑定 `new_generation` 的验证事务通过；不得让旧 generation 的 `mac` / `done` 消息在 reset 后完成信任升级。
6. **新的 `ck.cross_signing.publish`** MUST 在 reset 接受后 `ck.profile.cross_signing.reset.v1` 的 `parameters.publish_recovery_window_seconds` 窗口内发布到 control stream（默认 24h）；超时未发布的 reset 会让该 principal 进入"无可用 SSK / USK"窗口，接收方在此窗口内 MUST 拒绝任何 `ck.device.authorize.cross_signing_binding.ssk_generation == new_generation` 的事件，避免静默接受未公布的 SSK。
7. **`secret_storage` backup 同步刷新（normative）**：reset accepted 后，所有引用旧 SSK 的 `secret_storage` 类 `ck.schema.key_backup.v1` envelope MUST 在同一 `publish_recovery_window_seconds` 窗口内被新设备签发的后继 envelope 取代——后继 envelope 的 `series_id` 保持不变、`series_seq` 严格递增、`supersedes` 指向旧 envelope；`contents` 中含 `self_signing_key` / `user_signing_key` 的条目 MUST 对应 `new_generation`。窗口过期后，receiver MUST 把任何引用 retired generation 的 `secret_storage` envelope 视为 `backup_post_reset_stale`，并在恢复流程（§15 step 4）中拒绝作为主解锁源；服务端 SHOULD 在 list 响应中通过 metadata flag 提示该 envelope 已 stale，但 MUST NOT 自行删除（删除属于 §12.2 retention 流程）。

### 14.3 Cancel Code

§10.6 的 cancel code registry 增补一项：

| code | 含义 |
| --- | --- |
| `cross_signing_reset` | 本端或对端在验证过程中检测到 cross-signing reset；transcript 已绑定的 SSK generation 已被废止，必须放弃当前 transaction 并以新 generation 重启。 |

### 14.4 Proof 验证规则（Normative）

`cross-signing-reset.schema.json` 只编码 wire 形态最低限。Receiver 接受任一 reset 前 MUST 按下表对所选 proof.kind 执行**全部**校验；任一失败 MUST 拒绝该 reset 并以下面的 reason_code 标记。canonical input 同 §14.1。

| proof.kind | Receiver MUST 校验 | 失败 reason_code |
| --- | --- | --- |
| `principal_signing` | (a) `verification_method` MUST 是该 principal 当前 DID Document 中具备**principal-grade 控制权**的 verification method（即 [`../identity/key-management.md` §3.2](../identity/key-management.md) 定义的 principal signing key 类，例如 `did:webvh:...#ck_principal_signing_v1` 或等价 DID method 控制密钥），且在 `issued_at` 时刻未撤销 / 未轮换；**MUST NOT** 是被本次 reset 重置对象的 `self_signing_key` / `user_signing_key`（让被废止的密钥自我授权废止自身会导致 trust circular）。(b) `signature` 在 `alg` 下覆盖 §14.1 canonical input 验证通过；(c) `previous_generation` 等于 receiver 持有的 accepted publish generation，`new_generation = previous_generation + 1`。 | `cross_signing_reset_proof_authority_invalid` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_generation_mismatch` |
| `recovery_unlock` | (a) `recovery_secret_ref` 解析到 principal **当前 DID Document recovery 区或 `recovery_policy`** 中声明的 recovery key entry（必须在 `issued_at` 时刻 authoritative，未撤销 / 未过期）；(b) `signature` 验证使用该 entry 绑定的 public key、`alg` 在 entry 的算法白名单内、覆盖 §14.1 canonical input（**密码学强度仅由本签名提供**——拥有 recovery 私钥即视作 unlock 通过）；(c) `unlock_commitment` 等于 `SHA-256(utf8("ck-cross-signing-reset-unlock-binding-v1\n") \|\| recovery_secret_ref \|\| unlock_binding_input_bytes)`；`unlock_binding_input_bytes` 按 §14.1 定义，使用同一组 reset 字段，但 `proof_body` 同时排除 `signature` 与 `unlock_commitment`，避免 commitment 对自身取 hash。这是一个**完全由公开材料派生**的 wire-integrity 哈希，receiver 用事件自身的 `recovery_secret_ref` 与 `unlock_binding_input_bytes` 重算后比对；它**不证明持有 recovery secret**（signature 已承担该证明），但绑定 proof 到具体 ref + reset 内容，阻止把同一 ref 的签名跨 reset 复用为另一组 (principal_id, generation) 的 proof shell。 | `cross_signing_reset_recovery_ref_unknown` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_unlock_commitment_mismatch` |
| `device_quorum` | (a) 每个 `signatures[i]` 的 `verification_method` 是当前 principal device set 中**已授权且未撤销**的 device key（按 `signatures[i].device_id` 查找其 `ck.device.authorize` 记录），并验证 `signature` 覆盖 §14.1 canonical input；(b) `signatures[]` 按 `device_id` 去重；(c) 去重后**有效**签名数 ≥ `threshold`；(d) `threshold` 等于 receiver 当前 `recovery_policy.device_quorum.k`（或等价已发布门限策略），小于该值 MUST 拒（`recovery_policy` 自身的发布 / 修改授权——含降低 `device_quorum.k`——受 [`../identity/key-management.md` §8.1](../identity/key-management.md) 的 ratchet 约束:MUST 由当前 principal signing key 或满足旧 policy 门限的 quorum 签名、`version` 严格递增，因此单设备无法单方面调低本门限）。 | `cross_signing_reset_signature_invalid` / `cross_signing_reset_quorum_insufficient` / `cross_signing_reset_quorum_below_policy` |
| `trusted_recovery_service` | (a) `service_did` 出现在 principal DID Document 的恢复服务声明（或 organization recovery_policy `trusted_services[]`）中、未撤销、`issued_at` 在其有效窗口内；(b) `verification_method` 是该服务**已公布**的 verification method；(c) `signature` 覆盖 §14.1 canonical input；(d) 若 service 声明要求 `attestation_ref`，则该 ref MUST 解析到一条 receiver 可校验的 attestation event，且 attestation 所属 trust domain MUST 等于 reset payload 的 `trust_domain`；跨 trust domain attestation 不得作为恢复服务授权依据。 | `cross_signing_reset_recovery_service_unknown` / `cross_signing_reset_signature_invalid` / `cross_signing_reset_attestation_missing` / `cross_signing_reset_recovery_service_attestation_domain_mismatch` |

通用规则：

- 所有 proof 的 `alg` MUST 在 [`conformance/encoding.md` §6.1](../conformance/encoding.md) 的 Signature Suite registered set（签名算法白名单）内；未列入算法 MUST `unsupported_signature_alg`。
- `issued_at` 与 receiver 本地时钟偏差超出 [`ck.profile.cross_signing.reset.v1`](../../artifacts/profiles/conformance-profiles.json) 声明的 `parameters.max_clock_skew_seconds`（默认 300s，允许范围 60–900s）MUST `cross_signing_reset_clock_skew_exceeded`。
- 同一 `(principal_id, previous_generation)` 已被某条 reset 消费后，新到达的 reset MUST 以 `cross_signing_reset_replayed` 拒绝；replay-rejection 缓存保留时间不得少于 profile `parameters.reset_replay_cache_min_retention_seconds`（默认 90000s，对应 24h + 1h slack），且必须覆盖 `parameters.publish_recovery_window_seconds`（默认 86400s）所定义的"reset → publish"窗口。
- Receiver MUST 在接受 reset 后 `parameters.publish_recovery_window_seconds` 之内观察到对应的 `ck.cross_signing.publish`；超时未观察到 MUST 进入 §14.2 第 5 项的 "无可用 SSK / USK" 状态，并拒绝任何引用 `new_generation` 的设备授权事件。

## 15. Device Recovery Lifecycle

设备恢复是一个端到端状态机，不能只靠单个 reset proof 或 key backup 下载完成。合规实现 MUST 按以下顺序闭环：

`ck.schema.recovery_session.v1`（[`recovery-session.schema.json`](../../artifacts/schemas/recovery-session.schema.json)）规范化 recovery-session wire contract。Create/get/proofs/complete 的请求响应 shape、`principal_signing` proof 形态和 transcript fixture 均由该 schema 的 `$defs` 固定。

状态机（normative）——状态值固定为 `pending` / `verified` / `completed` / `rejected` / `expired`，合法转换为下表的封闭集合；表外转换 MUST reject：

| 当前状态 | 允许的出边 |
| --- | --- |
| `pending` | `verified` / `rejected` / `expired` |
| `verified` | `completed` / `expired` / `rejected` |
| `completed` / `rejected` / `expired` | 终态，无出边 |

- **`expired` 语义**：`expires_at` 过后仍处于非终态（`pending` / `verified`）的 session MUST 视为 `expired`。实现 MAY 在读取时惰性求值，或 MAY 显式写入状态字段，但对外可观察状态 MUST 一致——同一时点对同一 session 的任何读取不得返回不同状态。`verified` 后未在 `expires_at` 前完成 `/complete` 的 session 同样按本条过期。
- **`rejected` 进入条件**：proof 校验失败次数达到服务端策略上限，或服务端风控 / 操作员显式拒绝。进入 `rejected` 时 MUST 写入 `rejection_reason_code`，取值为封闭枚举：`proof_failed`（proof 校验失败达到策略上限）、`operator_rejected`（操作员 / 管理面显式拒绝）、`risk_policy`（服务端风控策略拒绝）、`superseded`（被同 principal / device 的新 recovery session 取代）。
- **终态请求**：对处于终态（`completed` / `rejected` / `expired`）的 session 调用 `submit_proof` 或 `complete`，服务端 MUST 返回 `failed_precondition`，reason_code=`recovery_session_terminal`。

1. **Recovery policy 触发**：新设备声明恢复意图，引用 principal DID 当前 `recovery_policy`、目标 `principal_id`、新 `device_id`、当前 `ssk_generation` 和 trust domain。服务端 / coordinator MUST 在创建 session 时 snapshot 当前 accepted `(policy_id, policy_version, ssk_generation)`，签发 256-bit CSPRNG `challenge`（base64url no padding, exactly 43 chars），并设置 `expires_at`。默认 TTL 为 900s；deployment MAY 配置更短 TTL，MUST NOT 配置更长 TTL，除非后续 recovery policy 字段显式授权覆盖。challenge MUST 单 session 单次使用；proof 失败或成功消费后不得在其它 session 复用。
2. **新设备认证**：按 recovery policy 选择 `principal_signing`、`recovery_unlock`、`device_quorum` 或 `trusted_recovery_service` proof。`principal_signing` proof 的 canonical transcript MUST 是 `canonical_json` of exactly:

   ```json
   {
     "type": "ck.identity.recovery_proof.v1",
     "kind": "principal_signing",
     "principal_id": "<principal DID>",
     "requesting_device_id": "<new device id>",
     "trust_domain": "<current trust domain>",
     "policy_id": "<active recovery policy id snapshotted by the session>",
     "policy_version": 1,
     "recovery_session_id": "ck:recovery_session:<uuidv7>",
     "ssk_generation": 1,
     "challenge": "<256-bit base64url session challenge>",
     "created_at": "<session created_at>",
     "expires_at": "<session expires_at>"
   }
   ```

   `created_at` 是 recovery session 创建/签发时间，不是客户端 proof 创建时间。`expires_at` 是同一 session 的过期时间。Receiver MUST reconstruct this transcript from stored session state, not from client-supplied copies of policy/session metadata except the echoed `challenge`; any mismatch fails closed (`recovery_evidence_unbound`, `recovery_policy_mismatch`, `recovery_session_challenge_mismatch`, or `invalid_signature` as applicable). Other proof kinds MUST bind the same session tuple and add kind-specific material when their schemas are introduced.
3. **设备授权与列表更新**：proof 接受（session 进入 `verified`）后，授权材料 MUST 由**恢复客户端**产出，而不是服务端——服务端既无新设备私钥，也无 SSK，无法伪造合法 `cross_signing_binding`。客户端 MUST：
   1. 用已接受的 recovery proof 对应的 recovery 私钥（24 词助记词派生，或经门限 / 硬件按 recovery policy 释放的同一 recovery 私钥）HPKE-open 承载 SSK 的 envelope —— 即 `recipient_method="recovery_public_key"` 且 `contents[].item_type` 含 `self_signing_key` 的那条 envelope（按 [`../identity/key-management.md` §7.5.0](../identity/key-management.md) 矩阵它属于 `secret_storage` 域，但其解锁只依赖 recovery 因子、不依赖已授权设备 key），取出该 principal 的 self-signing key（SSK）；承载 DID 控制恢复材料的 `did_recovery` envelope 同样在此阶段由 recovery 私钥解锁（见 step 4 的 recovery-bootstrap unlock set）；
   2. 用 SSK 对新设备 `verify_key` 按 §5.2 canonical 输入签出 `cross_signing_binding`，其 `ssk_generation` MUST 等于 session snapshot 的 `ssk_generation`；
   3. 组装完整 `ck.device.authorize` payload（[`event-payload.schema.json#/$defs/device_authorize_payload`](../../artifacts/schemas/event-payload.schema.json)），其中 `recovery_session_id` MUST 等于本 session（供 step 7 receipt 审计对账）。客户端 MUST 用已解锁的 SSK 签发普通 Event Envelope，并先提交到 principal control stream。
   4. 提交 `ck.device.list_update` 普通 Event Envelope，引用新设备授权结果。两条 Event MUST 使用 principal control stream 的连续 `actor_seq` / `prev_refs`。

   服务端在 `/complete` 请求体中只接受 `authorization_event_id` 与 `device_list_update_event_id` 引用。服务端 MUST 从 event store 解析这两条 durable Event，校验 kind、签名、principal control stream 连续性、`device_id == session.requesting_device_id`、`principal_id == session.principal_id`、`recovery_session_id == 本 session`，以及 `cross_signing_binding.ssk_generation == session.ssk_generation`；任一不符 MUST 拒绝（generation 不符时 reason=`device_recovery_ssk_generation_mismatch`）。校验通过后，服务端把 session 置为 `completed` 并在 `complete_response` 回同一组 event id。服务端不得代 principal 签发 `ck.device.authorize` 或 `ck.device.list_update`。恢复不是 bootstrap-first-device 情形，MUST 用 `cross_signing_binding` 而非 `bootstrap_binding`。reducer 同样 MUST 在当前 accepted `ck.cross_signing.publish.generation` 与 `ssk_generation` 不一致时拒绝（`device_recovery_ssk_generation_mismatch`）。
4. **Key backup / Secret storage unlock**：新设备只能拉取 policy 允许的 backup class（`did_recovery` / `secret_storage` / `mls_history`）。每个 backup decrypt proof MUST validate as `ck.schema.key_backup_unlock_proof.v1`，并绑定 `recovery_session_id`、新设备 key、active-series record、`backup_id`、`backup_class`、`series_id` 与 `ciphertext_digest`；解密后的明文 keybag MUST validate as `ck.schema.key_backup_plaintext.v1`，且外层 envelope 字段必须与明文字段一致。

   **解锁次序是 normative 的**，且判据是「该 envelope 是否能仅凭本 session 的 recovery 因子（recovery 私钥 / 门限 / 硬件释放的同一私钥）解开、且其内容是完成 step 3 设备授权所必需的材料」，**而不是简单按 `backup_class`**（这一点修正了旧文「授权前只解 `did_recovery`」与「SSK 按 §7.1 属于 `secret_storage` 域」之间的矛盾——SSK 的恢复定向副本以 `recipient_method=recovery_public_key` 加密，域上仍是 `secret_storage`，但属于下述 bootstrap 集合）：

   - **授权前**可解锁且 MUST 解锁的是 **recovery-bootstrap unlock set**：(a) 全部 `did_recovery` envelope；(b) 承载 SSK 的 `recipient_method="recovery_public_key"` 的 `secret_storage` envelope。否则没有 SSK 去签 `cross_signing_binding`。该集合的解锁仅依赖 recovery 因子，不依赖已授权设备 key。
   - **授权 accepted 之后**才能解锁的是其余全部 `secret_storage`（如 `user_signing_key`、非 bootstrap account secret、`mls_group_secrets_backup_key` 等）与全部 `mls_history` envelope，MUST 用已授权的新设备 key（或经设备 key 释放的本地解锁能力）解锁；其中 `mls_history` 的释放仍受 [`../identity/key-management.md` §7.6](../identity/key-management.md) active-series + frontier 校验约束。

   服务端不得把恢复 proof 当作长期 bearer token。
5. **MLS Welcome replay**：对每个可恢复 Realm，授权 peer / key service 重新发 Welcome 或 history key share；Welcome 的 `claim_ref.ssk_generation` MUST 等于当前 accepted cross-signing generation。旧 generation 的 Welcome MUST `claim_generation_mismatch`。
6. **Secret storage ready**：客户端在本地 secret storage 解锁、device list 同步、关键 Realm Welcome 完成前，只能进入 `recovery_pending`；不得把设备显示为 fully verified。
7. **Finalize / audit**：`ck.device.authorize` accepted 之后，新设备 key 才成为 principal 控制下的签名者。恢复完成后 MUST 按 `ck.schema.recovery_receipt.v1`（[`recovery-receipt.schema.json`](../../artifacts/schemas/recovery-receipt.schema.json)）写入恢复 receipt（可为 actor-private 或 audit Event，取决于 profile），且 `auth_data.verification_method` MUST 解析到 `new_device_id` 对应的 accepted device key；服务端 key 或尚未授权的新设备 key MUST NOT 签正式 recovery receipt。receipt MUST 绑定 `recovery_session_id`、`policy_id`、`policy_version`、`trust_domain`、`new_device_id`、`proof_summary`（含 proof_digest）、`backup_classes_unlocked[]`（每条记录 `backup_class` / `backup_id` / `series_id` / `ciphertext_digest`）、`welcome_count` / `welcome_realm_summary?`、`outcome` 与 `started_at` / `completed_at`；`outcome != completed` 时 MUST 携带 `outcome_reason_code`。`auth_data.signed_fields` MUST 覆盖上述全部 normative 字段（schema 在 `signed_fields.allOf.contains` 中强制）。同一 `recovery_session_id` 上的重复 receipt MUST 被 receiver 拒绝。若流程在设备授权 accepted 前失败、中止或过期，实现 MUST 写服务端 outcome / audit evidence，并用 `recovery_session_id` 对账；不得让服务端或未授权设备伪造正式 `ck.schema.recovery_receipt.v1`。

KeyPackage low-water refresh：claim 失败后 KeyPackage 不得自动放回；服务端响应 SHOULD 返回 `available_count`、`low_watermark` 和 `suggested_publish_count`。当 `available_count < low_watermark` 时，设备 SHOULD 发布新的 KeyPackage；若低水位持续低于 Realm policy 的最小值，发送方 MAY 延迟新设备 Welcome 并返回 `keypackage_refresh_required`。同一 device 多个 KeyPackage 的选择 MUST 使用服务端返回的最早 unclaimed package 或 deterministic order，不得按本地随机重试导致重复 claim。

## 16. Applet Device Delegation

Applet 如需代表 Ghost Actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Realm、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
