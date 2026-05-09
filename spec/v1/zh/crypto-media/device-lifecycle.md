---
title: Device Lifecycle
---

## 1. Login & Authorization Boundaries

去中心化协议摒弃了传统的账号+密码中心化认证模式，身份的本质是持有私钥。Contrix 把以下三件事分开处理：

- **登录因子验证**：Auth Service 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `cx.session.grant`、触发恢复流程，或请求已有设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `cx.device.authorized`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Space capability。

### 1.1 认证服务器验证什么

Contrix 可以部署 Auth Service / Auth Gateway，但它不是协议身份根。它验证的是“某个登录会话是否可以被绑定到某个 DID principal / device”，而不是用用户名、密码、邮箱或 OIDC subject 直接定义主体所有权。

实现 MAY 支持以下登录因子：

- 用户名 + 密码，用于传统 service account 登录。
- Passkey / WebAuthn，用于强认证或无密码登录。
- OIDC / SSO，用于企业或组织管理账号。
- 已授权设备配对，用于普通多设备加入。
- Recovery key、门限恢复或受信恢复服务，用于全部设备丢失后的恢复。

认证成功后，Auth Service MUST 产出以下至少一种可验证绑定：

- `cx.session.grant`：把短期 `session_public_key` 委托给 DID principal / device。
- `cx.device.authorized`：把新设备公钥加入当前设备集合。
- 满足 `recovery_policy` 的 `recover` / key-log event。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Space policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

### 1.2 登录、设备授权与设备验证的边界

Contrix v1 把三件事分开处理：

- **登录因子验证**：Auth Service 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `cx.session.grant`、触发恢复流程，或请求已有设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `cx.device.authorized`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Space capability。

因此“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `cx.device.authorized` 或短期 `cx.session.grant`。短期 Web/OIDC 登录可以只使用 `cx.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须走设备授权和设备密钥验证。


## 2. 多设备配对 (Device Pairing)

在 Contrix 中，用户的每个物理/逻辑设备都应该拥有本地独立生成的设备级密钥对 (Device Key)。
多设备登录的过程，本质上是“已授权设备将新设备加入身份控制网”的密码学授权过程。

### 2.1 配对流程 (无密码登录)
1. **新设备初始化**：用户在新手机或新电脑上打开应用，本地生成一组全新的 ECDSA/Ed25519 密钥对。屏幕上显示包含公钥与临时连接信息的二维码 (QR Code)。
2. **主设备扫码**：用户使用已登录的主设备（如已通过面容 ID 解锁的手机）扫描该二维码。
3. **密码学授权**：
   - 主设备验证 pairing challenge 后，签发 `cx.device.authorized`、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `cx.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `cx.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Sync Service，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播 `cx.device.authorized` 事件；若封装为 Event Envelope，其 `space_id` 是目标 principal 的 `principal_control_space_id`。新设备获得的能力由该事件、session grant、Space capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

### 2.2 设备吊销
当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `cx.device.revoked`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。


## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 托管员工 DID 的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 principal signing key 或 recovery key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，签发短期、受众绑定、scope 受限的 `cx.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。资源服务器仍 MUST 重新验证 DID control state、capability、Space policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。续期需要重新验证 OIDC session，并重新检查组织 policy、设备状态和风险信号。

此模式只把 Web2 SSO 作为登录因子和会话授权输入。它不授予 E2EE 密钥访问权，不自动创建长期设备，不替代 `cx.device.authorized`、DID/key-log operation 或 recovery policy。


## 4. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `cx:device:<uuid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json
{
  "device_id": "cx:device:019640dd-8000-7000-8000-000000000000",
  "principal_id": "did:webvh:...",
  "display_name": "Alice iPhone",
  "algorithms": ["cx.mls.v1", "cx.hpke_x25519_aead_xchacha20poly1305.v1"],
  "verify_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "kid": "did:webvh:...#cx_device_01HV_verify"
  },
  "hpke_key": {
    "kty": "OKP",
    "crv": "X25519",
    "kid": "did:webvh:...#cx_device_01HV_hpke"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

设备记录 MUST 由 principal 当前控制密钥或已信任的 self-signing key 签名。服务端不得伪造 device identity。

## 5. Signing Hierarchy

Contrix 使用三层签名链：

- `principal_signing_key`：DID 控制层，负责发布和轮换账户级签名根。
- `self_signing_key`：签名本 principal 的设备。
- `user_signing_key`：签名其他 principal 的 identity key，表达人工验证后的信任。

`self_signing_key` 和 `user_signing_key` SHOULD 存入加密 secret storage，并通过新设备验证后共享。

## 5a. Privacy-Preserving Push

Contrix 推送通道设计的目标是在不向 push gateway / vendor、上游 Sync Service、网络中间人或第三方 SaaS 控制面泄露身份与可链接信息的前提下，把"有事可投递"的最小信号送达终端。这是 [`discovery/push-notifications.md`](../discovery/push-notifications.md) 与 [`crypto-media/webrtc-signaling.md`](./webrtc-signaling.md) 中"pairwise pseudonym `push_target_id`"语义的协议层定义。

### 5a.1 `push_target_id` 派生与作用域

- 作用域：`per (principal_id, device_id, push_route)`。`push_route` 标识同一设备上不同 push 通道（如 `apns_main`, `fcm_voip`, `webpush_default`），允许同一设备针对不同通道发布相互不可链接的伪名。
- 长度：`push_target_id` MUST 至少 128 bit 熵，编码为 base64url（最少 22 字符）；推荐 256 bit。
- 不可推导性：`push_target_id` MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码可推导。生成方式 SHOULD 是 device-local 随机；设备 MAY 用本地 secret 与 `push_route` 派生，前提是源 secret 不可被服务端取回。
- 标识形态：典型 wire 形态为 typed ID `cx:pseudonym:push:<base64url>`，由 `id-kind-registry.json` 中 `pseudonym` 项授权使用；也可作为 raw base64url 字符串出现在 `cx.device.push_route` 等 actor-private state event payload 中。

### 5a.2 注册与撤销

- 设备 MUST 通过 `cx.device.push_route` actor-private Move 把 `(push_route, push_target_id, push_gateway_did, encryption_key, capabilities)` 写入 principal control stream；目标 cell 的 `cell_subject` 由 schema registry 声明的 composite `(payload.principal_id, payload.device_id, payload.push_route)` 派生（cas-register, bottom=reject）。
- 撤销：设备 MUST 在同一 cell 上写后继 Move 设置 `revoked: true` 或重新写入新 `push_target_id`；service / gateway MUST 在 Anchor frontier 收敛后停止接受旧伪名。
- 轮换：客户端 SHOULD 在 push token 变化、设备恢复、Out-of-band 重新登录、或自定义 rotation 周期（默认 ≤ 90 天）时轮换 `push_target_id`。
- 长期不可恢复性：服务方在丢弃旧 `push_target_id` 后 MUST NOT 保留可把旧 / 新伪名链接回同一 (principal, device) 的索引；只允许在 rotation 时短暂保留以便迁移未投递消息。

### 5a.3 不可链接性要求

- 同一 `principal_id` 在两台设备上的 `push_target_id` MUST 不可由 push gateway / Sync Service / 第三方 transport 关联（除非两侧自愿持有相同源 secret）。
- 同一设备的两条 `push_route` 的伪名 MUST 互相独立；其中一条被泄露不得让攻击者推导另一条。
- 跨 Space 投递 MUST 使用同一 `push_target_id`（按 device 而非按 Space），但 push payload 内不得携带 plaintext `space_id`/`flow_id`/`message_id`；目标拆分由 device 端解 envelope 后完成。

### 5a.4 Push Payload 形态

- 协议层 push payload MUST 视作 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob。AAD MUST 不包含可链接 wire 字段，仅可携带 routing-only `wakeup_kind`（参见 `discovery/push-notifications.md`）。
- gateway / vendor MUST NOT 解密 payload。任何"丰富推送"扩展（如显示发件人）都属于 vendor-side 行为，需要 Space 与 device 双方明确 opt-in，并对应单独的 plaintext-visible service profile，不在 v1 默认互操作范围。

### 5a.5 与其它子系统的边界

- Sync Service：以 `push_target_id` 作为 push fanout 索引，但不得保留 `push_target_id ↔ principal/device` 的可逆映射；服务重启 / 数据导出 / 法定披露场景 MUST 失效化导出该索引。
- WebRTC 通话邀请（`webrtc-signaling.md` §13 incoming-call wakeup）通过同一 `push_target_id` 触发；payload 仍走 §5a.4 加密通道。
- 推送规则（`push-notifications.md` §4 keyword / member_count 等）以 `push_target_id` 为目标但 MUST 在不解密 payload 的前提下完成评估，或在 E2EE Space 中由设备本地评估，详见对应文档。

## 6. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `cx.device.list_update` event。该 event 是 principal control stream 中的 durable identity state；若使用 Event Envelope，顶层 `space_id` MUST 是目标 principal 的 `principal_control_space_id`：

```json
{
  "kind": "cx.device.list_update",
  "payload": {
    "principal_id": "did:webvh:...",
    "changed": [
      "cx:device:01964137-0000-7000-8000-000000000000"
    ],
    "left": [
      "cx:device:01964138-0000-7000-8000-000000000000"
    ],
    "stream_id": "devstream_42"
  }
}
```

客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 7. To-Device Messages

To-device message 是面向具体 principal/device 的非 Space 持久消息，用于密钥交换、验证、secret sharing 和通知。

To-device wire object MUST 使用 `DeviceMessageEnvelope`，而不是持久 `EventEnvelope`。标准 `cx.key.verification.*` 名称在 to-device 通道中出现在 `kind` 字段；它们不得推进 `actor_seq`、`prev_refs`、Space reducer frontier 或持久 timeline。

`DeviceMessageEnvelope` 基本字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `kind` | `string` | required | 消息 kind，例如 `cx.key.verification.request`。标准 `cx.*` to-device kind MUST 在 registry 中登记为 `ephemeral_event` 或由扩展 profile 声明。 |
| `sender_principal_id` | `did` | required | 发送 principal。 |
| `sender_device_id` | `id:device` | required | 发送设备。 |
| `recipient_principal_id` | `did` | required | 接收 principal；MUST 等于投递路径中的目标 principal。 |
| `recipient_device_id` | `id:device` | required | 接收设备；MUST 等于投递路径中的目标设备。 |
| `sent_at` | `datetime` | required | 发送时间。 |
| `expires_at` | `datetime` | required | 队列过期时间；不得晚于该 kind/profile 声明的 TTL 上限。 |
| `content` | `object` | required | 类型相关内容；私密内容 SHOULD 端到端加密。 |
| `device_proof` | `proof` | optional | 传输认证不能覆盖的场景 MAY 带 detached device proof。 |

`recipient_principal_id` 和 `recipient_device_id` MUST 被签名、device proof 或加密 AAD 覆盖。发送接口使用 `messages.{principal_id}.{device_id}` 做批量路由时，服务端在入队前 MUST 把路径目标复制进 `DeviceMessageEnvelope`，且接收端 MUST 拒绝 envelope 目标与当前登录设备不一致的消息。

To-device 消息是短期队列对象，不是长期 Event history。发送方 MUST 设置 `expires_at`；服务端 MUST 拒绝缺失 `expires_at`、已经过期、早于 `sent_at` 或超过当前 service / Space / profile TTL 上限的消息。默认最大队列 TTL 为 24 小时；高安全 profile SHOULD 使用更短值。标准验证请求仍受第 8.2 节约束，`request.expires_at` MUST 不晚于 `timestamp + 10m`。过期消息 MUST 从投递队列中清除，`GET /device_messages` 不得返回；服务 MAY 仅保留最小幂等记录和脱敏审计摘要到 `expires_at` 后的短 grace period。

发送接口：

```http
POST /api/v1/device_messages
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
| `messages.{principal_id}.{device_id}.kind` | body | `string` | required | to-device 消息 kind，例如 `cx.key.verification.request`。 |
| `messages.{principal_id}.{device_id}.expires_at` | body | `datetime` | required | 队列过期时间；服务端物化 envelope 后必须复制到 `DeviceMessageEnvelope.expires_at`。 |
| `messages.{principal_id}.{device_id}.content` | body | `object` | required | 消息内容；私密内容 SHOULD 端到端加密。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ok` | `boolean` | required | 请求是否被处理。 |
| `delivered` | `object` | optional | 已入队或已投递设备摘要。 |
| `unknown_devices` | `object` | optional | 无法识别或不可投递的设备。 |

请求示例（非完整 schema）：

```json
{
  "messages": {
    "did:web:alice.example.com": {
      "cx:device:01964137-0000-7000-8000-000000000000": {
        "kind": "cx.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "cx:device:01964137-8000-7000-8000-000000000000",
          "timestamp": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:10:00Z",
          "methods": [
            "cx.sas.v1",
            "cx.qr.v1"
          ]
        }
      }
    }
  }
}
```

服务端 MUST 以 `(sender, Idempotency-Key)` 幂等。设备收到 sync 响应并推进 `cursor` 后，服务端 MAY 删除已投递消息。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖 `kind`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、`sent_at` 和 `expires_at`。队列服务不得重写这些字段。`Idempotency-Key` 是 HTTP 层语义，不进入 envelope，也不参与 AAD。

接收接口：

```http
GET /api/v1/device_messages?from=<cursor>&limit=<n>
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
| `events` | `object[]` | required | 当前设备可见的 to-device 消息。 |
| `next_cursor` | `cursor` | optional | 下一次读取 stream cursor。 |
| `limited` | `boolean` | optional | 是否因 limit 被截断。 |

## 8. One-Time and Fallback Keys

设备支持非 MLS 加密或引导 MLS 时，MUST 发布 one-time / fallback prekey：

```http
POST /api/v1/keys/upload
POST /api/v1/keys/query
POST /api/v1/keys/claim
```

`POST /api/v1/keys/upload` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_id` | body | `id:device` | required | 当前上传设备。 |
| `one_time_keys` | body | `object` | optional | 算法名到 one-time key 的映射。 |
| `fallback_keys` | body | `object` | optional | 算法名到 fallback key 的映射。 |
| `device_signature` | body | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。 |

响应字段：`one_time_key_counts: object` required；`fallback_keys: object` optional。

`POST /api/v1/keys/query` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `device_keys` | body | `object` | required | principal DID 到 device ID 列表的映射。 |
| `timeout_ms` | body | `int` | optional | 查询等待上限。 |

响应字段：`device_keys: object` required；`failures: object` optional。

`POST /api/v1/keys/claim` 请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `one_time_keys` | body | `object` | required | principal DID -> device ID -> algorithm 的映射。 |

响应字段：`one_time_keys: object` required；`failures: object` optional。

规则：

- `claim` MUST 原子消费 one-time key。
- fallback key MUST 标记 `fallback=true`，并在成功建立会话后尽快轮换。
- 服务端返回 key 时 MUST 附带 device signature。
- 客户端 MUST 拒绝未被 self-signing key 或 principal key 链接的 device key，除非用户明确接受未验证设备。

## 9. MLS KeyPackage Claim API

MLS KeyPackage 使用独立的 single-use claim API，而不是复用 one-time prekey 语义。

推荐操作：

```http
POST /api/v1/keys/keypackages/upload
POST /api/v1/keys/keypackages/claim
POST /api/v1/keys/keypackages/consume
POST /api/v1/keys/keypackages/revoke
```

`upload` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `principal_id` | `did` | required | KeyPackage 所属 principal。 |
| `device_id` | `id:device` | required | KeyPackage 所属设备。 |
| `keypackages` | `object[]` | required | MLS KeyPackage 与 metadata；每项 MUST 带 unique `keypackage_id` 和 `keypackage_ref`。 |
| `device_signature` | `signature` | required | 当前设备签名，MUST 链接到 self-signing / principal key。 |

`claim` 请求字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `target_principal_id` | `did` | required | 被邀请或加入的 principal。 |
| `target_device_ids` | `array<id:device>` | optional | 为空时由服务选择可用设备。 |
| `intended_space_id` | `id` | required | 目标 Space。 |
| `requester` | `did` | required | 发起 claim 的 actor 或 service DID。 |
| `required_capabilities` | `string[]` | required | 需要的 content / MLS / policy profile。 |
| `minimal_metadata_allowed` | `boolean` | optional | 是否允许 pseudonymous credential。 |
| `claim_nonce` | `string` | required | 防重放随机数。 |
| `expires_at` | `datetime` | required | claim 有效期。 |
| `proofs` | `proof[]` | required | requester / service / device proof。 |

`claim` 响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `claims` | `object[]` | required | 每个 claimed KeyPackage 的 `claim_id`、`keypackage_ref`、device binding、expiry 和 capabilities。 |
| `failures` | `object[]` | optional | 不可领取设备与原因；不得泄露不可见用户或设备。 |

`consume` MUST 由 Welcome 接收方或授权发送方在 Welcome 成功处理后调用，绑定 `claim_id`、`welcome_ref`、`space_id` 和 device proof。`revoke` 可由设备、principal controller 或 policy 授权服务发起。

规则：

- `claim` MUST 原子地把 KeyPackage 从 `published` 转为 `claimed`。
- 同一 `keypackage_ref` 不得被多个 active claim 使用。
- 过期、撤销、设备被移除或 principal control state 失效时，服务 MUST 不再返回该 KeyPackage。
- **`required_capabilities` ⊆ KeyPackage `capabilities`（normative subset rule）**：claim request 中的 `required_capabilities` 集合 MUST 是被领取 KeyPackage 上声明的 `capabilities`（见 [`encryption-and-audit.md` §2.6 keypackage payload](./encryption-and-audit.md)）的**子集**。任何 `required_capabilities ∖ capabilities ≠ ∅` 的 claim MUST 被服务端拒绝（与其它 claim 失败一致使用统一不透明错误码 `claim_failed`，但服务端 SHOULD 在内部审计日志中记录 `keypackage_capability_overreach` 以便滥用检测）。该规则避免了"客户端在 claim 时声明超过 KeyPackage 实际声明的能力，使后续 Welcome / Commit 在错误能力假设下进行"的隐性越权。
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备和 policy denied 做反枚举处理。对外错误码 SHOULD 合并为单一不透明错误码 `claim_failed`，不得返回可区分失败原因的 error message。服务端 SHOULD 使用统一状态码、最小响应体、限速和延迟填充降低时序侧信道；实现不得故意让不同失败原因产生稳定可测的响应差异。
- claim record SHOULD 被 Principal Server / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private room 的明文目标信息。

## 10. Verification Flows

设备密钥验证用于确认“这个 principal/device/key 是否是用户想信任的对象”。验证成功本身不授予登录态、Space 权限或长期设备权力：

- 同一 principal 的新设备登录，验证成功后仍 MUST 通过 `cx.device.authorized`、DID/key-log operation 或 recovery policy 把设备加入有效设备集合。
- 跨 principal 验证只表达人工信任；通常由本地 `user_signing_key` 签名对方 identity key 或设备 key，不得改变对方设备授权状态。
- `cx.session.grant` 只授予短期会话能力；不得因 SAS/QR 成功而自动升级为长期设备授权。

### 10.1 标准消息类型

Contrix 标准验证消息通过 to-device 通道发送：

- `cx.key.verification.request`
- `cx.key.verification.ready`
- `cx.key.verification.start`
- `cx.key.verification.accept`
- `cx.key.verification.key`
- `cx.key.verification.mac`
- `cx.key.verification.done`
- `cx.key.verification.cancel`

所有验证消息 content MUST 包含：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `transaction_id` | `string` | required | 交易 ID；对参与 principal/device 组合唯一，长度 1..128，不能复用已完成或已取消交易。 |
| `from_device` | `id:device` | required | 发送设备；MUST 等于 envelope 的 `sender_device_id`。 |

各消息的额外字段：

| `kind` | 额外必填字段 | 说明 |
| --- | --- | --- |
| `cx.key.verification.request` | `methods`, `timestamp`, `expires_at` | 发起验证。`methods` 使用标准方法名，例如 `cx.sas.v1`、`cx.qr.v1`。 |
| `cx.key.verification.ready` | `methods` | 接受请求并回报本设备可用方法。 |
| `cx.key.verification.start` | `method` | 选择方法并开始。SAS 还 MUST 带 `key_agreement_protocols`、`hashes`、`message_authentication_codes`、`short_authentication_string`。 |
| `cx.key.verification.accept` | `commitment` | 接受 `start` 并提交本端 ephemeral key 承诺；还 MUST 固定选定算法。 |
| `cx.key.verification.key` | `key` | 发送本端 ephemeral public key。 |
| `cx.key.verification.mac` | `mac`, `keys` | 发送待验证 key 的 MAC 与 key-id MAC。 |
| `cx.key.verification.done` | none | 双方 MAC 验证通过后完成。MAY 带本地生成的签名摘要。 |
| `cx.key.verification.cancel` | `code` | 任意阶段取消；`reason` MAY 给出面向用户的短说明。 |

### 10.2 状态机、超时与并发

标准交互状态机为：

```text
request -> ready -> start -> accept -> key -> mac -> done
```

`cancel` MAY 在任意阶段发送。接收方 MUST 对重复的同一消息做幂等处理；对越序或状态不匹配的消息 MUST cancel，`code=unexpected_message`。

请求超时规则：

- `request.timestamp` 不能比接收设备本地时间晚 5 分钟以上。
- `request.expires_at` MUST 不晚于 `timestamp + 10m`。
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

1. 签发 `cx.device.authorized` 或符合 DID method 的 key-log operation。
2. 发布 `cx.device.list_update`。
3. 在用户或 policy 允许时，通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome。

跨 principal 验证完成后，客户端 MAY 使用 `user_signing_key` 对对方 principal identity key 或 device key 生成信任签名。该签名只影响本 principal 的信任视图，不授予对方 Space capability。

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
| `policy_denied` | Space、组织或账号 policy 拒绝。 |
| `accepted_by_other_device` | 同一请求已被另一设备接受。 |

## 11. Secret Storage（client-local cache form）

Secret storage 用于保存：

- `self_signing_key`
- `user_signing_key`
- recovery secret
- MLS group secrets backup key
- applet delegated device secret

`cx.secret_storage.v1` 是 **client-local** envelope，仅用于设备本地或可信操作系统 keychain；**不再作为线级 (wire) 上传格式**。任何同步到 Device / Key Server 或其它远端服务的 secret，MUST 使用 §10 的 `cx.schema.key_backup.v1` envelope，并设置对应 `backup_class`：

| Secret 类别 | `backup_class` |
| --- | --- |
| DID 恢复材料 | `did_recovery` |
| `self_signing_key`、`user_signing_key`、recovery secret 等账户级 secret | `secret_storage` |
| MLS epoch / Space history secret | `mls_history` |
| 外部托管或 profile 自定义 secret | `external` |

每个 `backup_class` MUST 使用独立 HKDF info 字符串（`contrix-key-backup-{backup_class}-v1`）派生 commitment / wrap key，禁止跨 class 共享密钥材料。

Client-local secret storage 的存储格式仍可使用本节的 `cx.secret_storage.v1` envelope，但其字段不进入任何 wire / hash / 签名输入；服务端不接受该 envelope。

## 12. Key Backup

Key backup 保存已加密的 Space / MLS 历史密钥材料。它只覆盖当前 actor 已经通过 membership、history visibility 和 Space policy 获得的历史范围，不是给未来新成员预先保留历史 secret 的机制。

备份单元使用 `cx.schema.key_backup.v1`，并设置 `backup_class="mls_history"`。示例：

```json
{
  "backup_id": "cx:backup:01964138-8000-7000-8000-000000000000",
  "actor_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
  "backup_class": "mls_history",
  "backup_version": "kb_1",
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": {
    "recipient_method": "secret_storage_key",
    "recipient_key_ref": "mls_group_secrets_backup_key",
    "aead": {
      "name": "xchacha20_poly1305",
      "nonce": "base64url..."
    }
  },
  "contents": [
    {
      "item_type": "mls_epoch_secret",
      "space_id": "cx:space:0196419b-0000-7000-8000-000000000000",
      "mls_group_id": "base64url",
      "epoch": 42,
      "first_event_id": "cx:event:019640ed-8000-7000-8000-000000000000",
      "last_event_id": "cx:event:019640ee-0000-7000-8000-000000000000"
    }
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:42108421-0842-7084-a108-42108421084242108421-0842-7084-a108-421084210842222222222222",
  "auth_data": {
    "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
    "signature": "base64url..."
  }
}
```

备份 MUST 加密给 recovery public key 或 secret storage key。服务端 MUST NOT 能解密。

规则：

- 备份 metadata MUST 绑定 actor DID、device id、backup id、backup class、created_at、ciphertext digest 和加密参数。
- 上传设备 MUST 对 backup metadata 与 ciphertext digest 签名，签名链必须链接到当前 principal 的 self-signing / device trust chain。
- 服务端 MUST 只允许同一 actor 的当前授权设备、满足 recovery policy 的恢复流程，或 policy 明确授权的组织恢复服务读取备份密文。
- 服务端返回备份列表时 SHOULD 最小化 metadata；不得向无关 caller 暴露 Space membership、MLS group id 或历史范围。
- 删除备份只删除服务端密文和 metadata；它不撤销 DID 控制权，也不改变 Space membership。需要吊销设备或轮换 MLS epoch 时必须发布相应事件。
- 被撤销设备上传的新备份 MUST 被拒绝。撤销前上传的备份 MAY 继续保留，但恢复使用时必须重新验证当前 recovery policy、device revocation state 和 Space history visibility。

### 12.1 Backup API

Device / Key Server 对 encrypted backup object 提供标准操作：

```http
PUT /api/v1/keys/backups/{backup_id}
GET /api/v1/keys/backups
GET /api/v1/keys/backups/{backup_id}
DELETE /api/v1/keys/backups/{backup_id}
```

`PUT` 请求体 MUST 是 `cx.schema.key_backup.v1`，且 path 中的 `backup_id` MUST 与 body 中的 `backup_id` 一致。`PUT` 按 `(actor_id, backup_id)` 幂等；同一 `backup_id` 若提交不同 canonical content MUST 返回冲突错误。

`list` 响应只返回调用方可见的 backup metadata、digest 和 retention hints。`get` 返回完整 encrypted backup object。`delete` MUST 要求当前设备证明、DID proof 或 recovery policy 允许的高风险证明。

## 13. Space / Branch Key Share and Withholding

Contrix 使用 `cx.space_key.share` 共享历史解密材料。共享前发送设备 MUST 检查：

- 接收设备属于目标 principal。
- 设备未撤销。
- 设备通过 self-signing 或人工验证，或 Space policy 允许未验证设备。
- history visibility 允许该 principal 获取目标历史范围。

拒绝共享时发送 `cx.space_key.withheld`，原因码：

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

## 15. Applet Device Delegation

Applet 如需代表 ghost actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Space、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
