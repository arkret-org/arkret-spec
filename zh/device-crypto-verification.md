# Device Crypto and Verification

## 1. 目标

本文件定义 Contrix 多设备身份、设备信任、设备间消息、密钥验证、密钥备份和 E2EE 历史共享。它补足 `devices-and-auth.md` 与 `key-management.md` 的线级协议要求。

## 2. Device Identity

每个设备 MUST 有稳定 `device_id` 和设备签名密钥：

```json
{
  "device_id": "dev_01HV...",
  "principal_id": "did:uuid:...",
  "display_name": "Alice iPhone",
  "algorithms": ["cx.mls.v1", "cx.hpke_x25519_aead_xchacha20poly1305.v1"],
  "verify_key": {
    "kty": "OKP",
    "crv": "Ed25519",
    "kid": "did:uuid:...#dev_01HV_verify"
  },
  "hpke_key": {
    "kty": "OKP",
    "crv": "X25519",
    "kid": "did:uuid:...#dev_01HV_hpke"
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
    "principal_id": "did:uuid:...",
    "changed": ["dev_a"],
    "left": ["dev_old"],
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

```json
{
  "messages": {
    "did:uuid:alice": {
      "dev_a": {
        "type": "cx.key.verification.request",
        "content": {
          "transaction_id": "ver_123",
          "from_device": "dev_b",
          "methods": ["sas", "qr"]
        }
      }
    }
  }
}
```

服务端 MUST 以 `(sender, txn_id)` 幂等。设备收到 sync 响应并推进 `next_batch` 后，服务端 MAY 删除已投递消息。To-device 消息 SHOULD 端到端加密；未加密消息只能用于能力发现和验证引导。

## 6. One-Time and Fallback Keys

设备支持非 MLS 加密或引导 MLS 时，MUST 发布 one-time / fallback prekey：

```http
POST /api/v1/keys/upload
POST /api/v1/keys/query
POST /api/v1/keys/claim
```

规则：

- `claim` MUST 原子消费 one-time key。
- fallback key MUST 标记 `fallback=true`，并在成功建立会话后尽快轮换。
- 服务端返回 key 时 MUST 附带 device signature。
- 客户端 MUST 拒绝未被 self-signing key 或 principal key 链接的 device key，除非用户明确接受未验证设备。

## 7. Verification Flows

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

## 8. Secret Storage

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

## 9. Key Backup

Key backup 保存已加密的 Space / MLS 历史密钥材料。备份单元：

```json
{
  "backup_version": "kb_1",
  "space_id": "space:...",
  "epoch": 42,
  "session_id": "mls_epoch_42",
  "first_event_id": "event:...",
  "last_event_id": "event:...",
  "ciphertext": "base64url...",
  "auth_data": {
    "device_id": "dev_a",
    "signature": "base64url..."
  }
}
```

备份 MUST 加密给 recovery public key 或 secret storage key。服务端 MUST NOT 能解密。

## 10. Room-Key Equivalent and Withholding

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

## 11. Cross-Signing Reset

重置 `self_signing_key` 或 `user_signing_key` 是高风险操作。实现 MUST 要求以下至少一种证明：

- principal DID 控制密钥签名。
- recovery key 解锁 secret storage。
- 已验证设备 quorum 签名。
- 受信任账户恢复服务签名，且该服务在 DID document 中声明。

重置后，旧设备签名链不再自动可信。客户端 MUST 将所有旧信任标记为 `needs_reverification`。

## 12. Applet Device Delegation

Applet 如需代表 ghost actor 或桥接用户参与 E2EE，MUST 使用受限 delegated device：

- device id MUST 标记 `applet_id`。
- capability MUST 限制 Space、协议、动作和有效期。
- delegated device 不得签发新的 human device。
- delegated device 的 to-device 权限 MUST 只覆盖其 namespace 内 actor。

