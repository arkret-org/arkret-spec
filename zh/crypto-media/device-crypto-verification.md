# Device Crypto and Verification

## 1. 目标

本文件定义 Contrix 多设备身份、设备信任、设备间消息、密钥验证、密钥备份和 E2EE 历史共享。它补足 `devices-and-auth.md` 与 `key-management.md` 的线级协议要求。

## 2. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `cx:device:<ulid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json
{
  "device_id": "cx:device:01js0dv0000000000000000000",
  "principal_id": "did:plc:...",
  "display_name": "Alice iPhone",
  "algorithms": ["cx.mls.v1", "cx.hpke_x25519_aead_xchacha20poly1305.v1"],
  "verify_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "kid": "did:plc:...#cx_device_01HV_verify"
  },
  "hpke_key": {
    "kty": "OKP",
    "crv": "X25519",
    "kid": "did:plc:...#cx_device_01HV_hpke"
  },
  "created_at": "2026-04-26T00:00:00Z"
}
```

设备记录 MUST 由 principal 当前控制密钥或已信任的 self-signing key 签名。服务端不得伪造 device identity。

## 3. Signing Hierarchy

Contrix 使用三层签名链：

- `principal_signing_key`：DID 控制层，负责发布和轮换账户级签名根。
- `self_signing_key`：签名本 principal 的设备。
- `user_signing_key`：签名其他 principal 的 identity key，表达人工验证后的信任。

`self_signing_key` 和 `user_signing_key` SHOULD 存入加密 secret storage，并通过新设备验证后共享。

## 4. Device List Sync

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `cx.device.list_update` event。该 event 是 principal control stream 中的 durable identity state；若使用 Event Envelope，顶层 `space_id` MUST 是目标 principal 的 `principal_control_space_id`：

```json
{
  "kind": "cx.device.list_update",
  "payload": {
    "principal_id": "did:plc:...",
    "changed": [
      "cx:device:01js0ke0000000000000000000"
    ],
    "left": [
      "cx:device:01js0kg0000000000000000000"
    ],
    "stream_id": "devstream_42"
  }
}
```

客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 5. To-Device Messages

To-device message 是面向具体 principal/device 的非 Space 持久消息，用于密钥交换、验证、secret sharing 和通知。

To-device wire object MUST 使用 `DeviceMessageEnvelope`，而不是持久 `EventEnvelope`。标准 `cx.key.verification.*` 名称在 to-device 通道中出现在 `kind` 字段；它们不得推进 `actor_seq`、`prev_refs`、Space reducer frontier 或持久 timeline。

`DeviceMessageEnvelope` 基本字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `kind` | `string` | required | 消息 kind，例如 `cx.key.verification.request`。标准 `cx.*` to-device kind MUST 在 registry 中登记为 `ephemeral_event` 或由扩展 profile 声明。 |
| `txn_id` | `id` | required | 发送方幂等 ID，MUST 与 PUT path `{txn_id}` 一致。 |
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
PUT /api/v1/device_messages/{txn_id}
Authorization: Bearer <token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `txn_id` | path | `id` | required | 发送方生成的幂等 ID；服务端 MUST 以 `(sender, txn_id)` 去重。 |
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
      "cx:device:01js0ke0000000000000000000": {
        "kind": "cx.key.verification.request",
        "expires_at": "2026-04-26T00:10:00Z",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "cx:device:01js0kf0000000000000000000",
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

服务端 MUST 以 `(sender, txn_id)` 幂等。设备收到 sync 响应并推进 `next_batch` 后，服务端 MAY 删除已投递消息。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

若 `content` 已端到端加密，加密 AAD MUST 至少覆盖 `kind`、`txn_id`、`sender_principal_id`、`sender_device_id`、`recipient_principal_id`、`recipient_device_id`、`sent_at` 和 `expires_at`。队列服务不得重写这些字段。

接收接口：

```http
GET /api/v1/device_messages?from=<token>&limit=<n>
Authorization: Bearer <token>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 必须绑定当前接收设备。 |
| `from` | query | `token` | optional | 上次同步位置。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `events` | `object[]` | required | 当前设备可见的 to-device 消息。 |
| `next_batch` | `token` | optional | 下一次读取 token。 |
| `limited` | `boolean` | optional | 是否因 limit 被截断。 |

## 6. One-Time and Fallback Keys

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

## 7. MLS KeyPackage Claim API

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
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备和 policy denied 做反枚举处理。对外错误码 SHOULD 合并为单一不透明错误码 `claim_failed`，不得返回可区分失败原因的 error message。服务端 SHOULD 使用统一状态码、最小响应体、限速和延迟填充降低时序侧信道；实现不得故意让不同失败原因产生稳定可测的响应差异。
- claim record SHOULD 被 Principal Server / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private room 的明文目标信息。

## 8. Verification Flows

设备密钥验证用于确认“这个 principal/device/key 是否是用户想信任的对象”。验证成功本身不授予登录态、Space 权限或长期设备权力：

- 同一 principal 的新设备登录，验证成功后仍 MUST 通过 `cx.device.authorized`、DID/key-log operation 或 recovery policy 把设备加入有效设备集合。
- 跨 principal 验证只表达人工信任；通常由本地 `user_signing_key` 签名对方 identity key 或设备 key，不得改变对方设备授权状态。
- `cx.session.grant` 只授予短期会话能力；不得因 SAS/QR 成功而自动升级为长期设备授权。

### 8.1 标准消息类型

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

### 8.2 状态机、超时与并发

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

### 8.3 SAS 验证

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

### 8.4 QR 验证

QR 验证 MUST 使用一次性 secret 或 public commitment，且 QR 内容 MUST 有过期时间和 intended verifier。

QR payload MUST 至少绑定：

- `transaction_id`
- 展示端 principal id 与 device id
- intended verifier principal id；若已知，还 SHOULD 绑定 intended verifier device id
- 一次性 secret 或 public commitment
- `expires_at`
- supported verification method

QR payload MUST NOT 包含长期私钥、secret storage key、recovery secret 或 MLS group secret。扫码后，客户端仍 MUST 通过 to-device transcript 完成 `mac` / `done`，不能只凭扫码动作直接信任设备。

### 8.5 成功后的动作

同一 principal 的新设备配对完成后，已授权设备 MAY：

1. 签发 `cx.device.authorized` 或符合 DID method 的 key-log operation。
2. 发布 `cx.device.list_update`。
3. 在用户或 policy 允许时，通过加密 to-device 消息共享 `self_signing_key`、secret storage bootstrap 或 MLS Welcome。

跨 principal 验证完成后，客户端 MAY 使用 `user_signing_key` 对对方 principal identity key 或 device key 生成信任签名。该签名只影响本 principal 的信任视图，不授予对方 Space capability。

### 8.6 Cancel Code Registry

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

## 9. Secret Storage（client-local cache form）

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

## 10. Key Backup

Key backup 保存已加密的 Space / MLS 历史密钥材料。它只覆盖当前 actor 已经通过 membership、history visibility 和 Space policy 获得的历史范围，不是给未来新成员预先保留历史 secret 的机制。

备份单元使用 `cx.schema.key_backup.v1`，并设置 `backup_class="mls_history"`。示例：

```json
{
  "backup_id": "cx:backup:01js0kh0000000000000000000",
  "actor_id": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "device_id": "cx:device:01js0ke0000000000000000000",
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
      "space_id": "cx:space:01js0sp0000000000000000000",
      "mls_group_id": "base64url",
      "epoch": 42,
      "first_event_id": "cx:event:01js0ev0000000000000000000",
      "last_event_id": "cx:event:01js0ew0000000000000000000"
    }
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
  "auth_data": {
    "device_id": "cx:device:01js0ke0000000000000000000",
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

### 10.1 Backup API

Device / Key Server 对 encrypted backup object 提供标准操作：

```http
PUT /api/v1/keys/backups/{backup_id}
GET /api/v1/keys/backups
GET /api/v1/keys/backups/{backup_id}
DELETE /api/v1/keys/backups/{backup_id}
```

`PUT` 请求体 MUST 是 `cx.schema.key_backup.v1`，且 path 中的 `backup_id` MUST 与 body 中的 `backup_id` 一致。`PUT` 按 `(actor_id, backup_id)` 幂等；同一 `backup_id` 若提交不同 canonical content MUST 返回冲突错误。

`list` 响应只返回调用方可见的 backup metadata、digest 和 retention hints。`get` 返回完整 encrypted backup object。`delete` MUST 要求当前设备证明、DID proof 或 recovery policy 允许的高风险证明。

## 11. Space / Branch Key Share and Withholding

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

## 12. Cross-Signing Reset

重置 `self_signing_key` 或 `user_signing_key` 是高风险操作。实现 MUST 要求以下至少一种证明：

- principal DID 控制密钥签名。
- recovery key 解锁 secret storage。
- 已验证设备 quorum 签名。
- 受信任账户恢复服务签名，且该服务在 DID document 中声明。

重置后，先前设备签名链不再自动可信。客户端 MUST 将所有既有信任标记为 `needs_reverification`。

## 13. Applet Device Delegation

Applet 如需代表 ghost actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Space、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
