# Device Crypto and Verification

## 1. 目标

本文件定义 Contrix 多设备身份、设备信任、设备间消息、密钥验证、密钥备份和 E2EE 历史共享。它补足 `devices-and-auth.md` 与 `key-management.md` 的线级协议要求。

## 2. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥。`device_id` 的类型是 `id:device`，wire form MUST 为完整 `cx:device:<ulid>`；当它出现在 JSON object key 中时也同样适用，不得改写成局部别名：

```json
{
  "device_id": "cx:device:01HV...",
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

任何设备新增、撤销、签名更新或算法更新，MUST 产生 `cx.device.list_update` event：

```json
{
  "type": "cx.device.list_update",
  "content": {
    "principal_id": "did:plc:...",
    "changed": ["cx:device:01js0ke0000000000000000000"],
    "left": ["cx:device:01js0kg0000000000000000000"],
    "stream_id": "devstream_42"
  }
}
```

客户端 sync MUST 暴露 device list delta。E2EE 客户端在向 principal 发送新加密内容前，MUST 查询或同步其最新 device list。

## 5. To-Device Messages

To-device message 是面向具体 principal/device 的非 Space 持久消息，用于密钥交换、验证、secret sharing 和通知。

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
| `messages.{principal_id}.{device_id}.type` | body | `string` | required | to-device 消息类型，例如 `cx.key.verification.request`。 |
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
        "type": "cx.key.verification.request",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "cx:device:01js0kf0000000000000000000",
          "methods": ["sas", "qr"]
        }
      }
    }
  }
}
```

服务端 MUST 以 `(sender, txn_id)` 幂等。设备收到 sync 响应并推进 `next_batch` 后，服务端 MAY 删除已投递消息。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

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
- `claim` 失败响应 MUST 对不存在、不可见、无可用设备和 policy denied 做反枚举处理。
- claim record SHOULD 被 Principal Server / Device Key Server 保留到 Welcome 过期后的一段短 TTL，用于重试、诊断和滥用审计；不得长期保留可关联 private room 的明文目标信息。

## 8. Verification Flows

Contrix 标准验证消息：

- `cx.key.verification.request`
- `cx.key.verification.ready`
- `cx.key.verification.start`
- `cx.key.verification.accept`
- `cx.key.verification.key`
- `cx.key.verification.mac`
- `cx.key.verification.done`
- `cx.key.verification.cancel`

SAS 验证 MUST 绑定：

- 双方 principal id
- 双方 device id
- 双方 device verify key
- transaction id
- chosen method and algorithms

MAC 阶段 MUST 覆盖以上 transcript。任何 transcript 不一致 MUST cancel，原因码为 `mismatched_commitment` 或 `mismatched_mac`。

QR 验证 MUST 使用一次性 secret 或 public commitment，且 QR 内容 MUST 有过期时间和 intended verifier。

## 9. Secret Storage

Secret storage 用于保存：

- `self_signing_key`
- `user_signing_key`
- recovery secret
- MLS group secrets backup key
- applet delegated device secret

Secret storage envelope：

```json
{
  "type": "cx.secret_storage.v1",
  "secret_id": "self_signing_key",
  "kdf": {
    "name": "argon2id",
    "memory_kib": 65536,
    "iterations": 3,
    "salt": "base64url..."
  },
  "aead": "xchacha20poly1305",
  "ciphertext": "base64url...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

服务端只存密文。恢复口令、recovery key 或硬件密钥不得上传。

## 10. Key Backup

Key backup 保存已加密的 Space / MLS 历史密钥材料。备份单元：

```json
{
  "backup_version": "kb_1",
  "space_id": "cx:space:...",
  "epoch": 42,
  "session_id": "mls_epoch_42",
  "first_event_id": "cx:event:...",
  "last_event_id": "cx:event:...",
  "ciphertext": "base64url...",
  "auth_data": {
    "device_id": "cx:device:01js0ke0000000000000000000",
    "signature": "base64url..."
  }
}
```

备份 MUST 加密给 recovery public key 或 secret storage key。服务端 MUST NOT 能解密。

## 11. Room-Key Equivalent and Withholding

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

重置后，旧设备签名链不再自动可信。客户端 MUST 将所有旧信任标记为 `needs_reverification`。

## 13. Applet Device Delegation

Applet 如需代表 ghost actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Space、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。
