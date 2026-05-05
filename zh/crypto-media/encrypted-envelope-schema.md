# 加密负载信封 Schema

## 1. 概述

本规范定义了 Contrix v1 中加密内容的信封格式。该信封支持 MLS (RFC 9420) 和未来的加密方案，同时保持协议互操作性。

## 2. 信封结构

### 2.1 Schema

```json
{
  "envelope": {
    "scheme": "mls-rfc9420",
    "version": "1.0",
    "group_id": "base64url",
    "epoch": "integer",
    "content_type": "string",
    "ciphertext": "base64url",
    "aad": {
      "space_id": "cx:space:...",
      "event_kind": "cx.message.create",
      "event_ref_hash": "sha256:...",
      "causal_refs": ["cx:event:..."]
    },
    "key_ref": {
      "algorithm": "MLS",
      "group_state_ref": "cx:event:01js0mg0000000000000000000"
    },
    "payload_digest": "sha256:...",
    "aad_digest": "sha256:..."
  }
}
```

### 2.2 字段定义

| 字段 | 类型 | 必需 | 说明 |
|------|------|------|------|
| `scheme` | string | 是 | 加密方案标识符 |
| `version` | string | 是 | 方案版本 |
| `group_id` | string | 是 | MLS 群组 ID (Base64URL) |
| `epoch` | integer | 是 | MLS epoch 编号 |
| `content_type` | string | 是 | 解密内容的 MIME 类型 |
| `ciphertext` | string | 是 | 加密负载 (Base64URL)。`mls-rfc9420` profile 中为 MLS PrivateMessage / application message 的序列化字节。 |
| `authentication_tag` | string | 条件 | 仅 raw AEAD / exporter-AEAD profile 使用。`mls-rfc9420` profile 的认证标签已在 MLS message 内，不应重复拆出。 |
| `aad` | object | 是 | 附加认证数据 |
| `aad.space_id` | id:space | 是 | 用于路由和授权的 Space |
| `aad.event_kind` | string | 是 | 用于路由的 Event kind；MUST 使用标准 `kind` 命名规则，允许多段 kind。 |
| `aad.event_id` | id:event | 条件 | `aad_visibility.event_id="opaque_id"` 时可见。 |
| `aad.event_ref_hash` | hash | 条件 | `aad_visibility.event_id="routing_hash"` 时使用，hash 输入必须由 profile 固定。 |
| `aad.causal_refs` | array | 条件 | 可见因果依赖；高隐私 profile 可用 `causal_ref_hashes` 替代。 |
| `aad.causal_ref_hashes` | array<hash> | 条件 | `aad_visibility.causal_refs="routing_hash"` 时使用。 |
| `key_ref` | object | 条件 | 密钥材料引用（对接收方可选） |
| `key_ref.algorithm` | string | 条件 | `mls-rfc9420` profile 中为 `MLS`；未来 profile 必须注册自己的值。 |
| `key_ref.group_state_ref` | id:event/hash | 否 | 可指向已 accepted 的 `cx.mls.genesis`、winner `cx.mls.commit` 或等价 group state proof，用于加速 lookup；不得替代 MLS transcript 验证。 |
| `payload_digest` | hash | 是 | `sha256(payload_metadata_bytes || encrypted_payload_bytes)`；输入定义见第 3.3 节。若 profile 拆出 `authentication_tag`，tag MUST 纳入 `encrypted_payload_bytes`。 |
| `aad_digest` | hash | 是 | 规范 AAD 的 SHA256 |
| `cleartext_commitment` | hash | 否（v1 预留） | `sha256` 覆盖明文规范字节（每个 scheme 由自己的 Cleartext Commitment Profile 定义；`mls-rfc9420` 的规则见 `encryption-and-audit.md` §4 的 commitment profile）。提供后允许接收方在不暴露明文的前提下检测 ciphertext malleability：发送方"承诺密文对应这一份明文"。v1 字段为可选，目的是预留 wire 兼容空间，避免 v2 引入 cleartext binding 时再做破坏性升级；v1 实现 MAY 忽略，v2 MAY 对新 scheme 设为必填。 |

Ratchet tree MUST 由 `cx.mls.genesis`、Welcome、Commit 或 group state proof 管理，不得在每条消息的 envelope 中重复传输。

## 3. 附加认证数据 (AAD)

### 3.1 用途

AAD 包含路由元数据，具有以下特性：

- 必须是明文，用于同步路由
- 被认证覆盖（完整性保护）
- 篡改必定被检测

AAD 字段集合受 Space 的 `aad_visibility` policy 约束。隐私优先 Space SHOULD 只保留路由所需的 `space_id`、event kind、epoch 和不可逆 routing hash；需要跨 provider 调试或投递确认的 Space MAY 暴露 opaque `event_id` / `message_id`，但该选择 MUST 在 Space policy 中声明并纳入 MLS-bound `policy_root`。

`aad.event_id` 与 `aad.event_ref_hash` 是互斥 profile 字段：

- `opaque_id`：AAD MAY 包含 `event_id`，用于跨 provider 投递确认和精确去重。
- `routing_hash`：AAD MUST 使用 `event_ref_hash`，不得暴露稳定 `event_id`。hash 输入 SHOULD 为 `sha256("cx-aad-event-ref-v1" || event_id || space_id || policy_nonce)`。
- `hidden`：AAD MUST 同时省略 `event_id` 与 `event_ref_hash`；去重只能依赖外层 Event Envelope、transport receipt 或 receiver-local cache。

`aad.causal_refs` 在高隐私 profile 中 MAY 替换为 `causal_ref_hashes`，但该 profile 必须声明 backfill 和 conflict diagnostic 如何工作。

### 3.2 规范 AAD 序列化

AAD 在计算 `aad_digest` 前必须序列化为规范 JSON：

```json
{
  "space_id": "cx:space:01js0sp0000000000000000000",
  "event_kind": "cx.message.create",
  "event_ref_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "causal_refs": ["cx:event:01js0et0000000000000000000"]
}
```

规则：

- 键按字典序排序
- 无多余空白
- 无尾随逗号
- 字符串使用 UTF-8 编码

### 3.3 `payload_digest` 输入

`payload_digest` 的输入必须完全确定，不得使用实现本地对象序列化结果。

1. `aad_bytes = canonical_json(aad)`，`aad_digest = sha256(aad_bytes)`。
2. `payload_metadata` 是以下对象的 canonical JSON，字段缺失时不得写入 null：

```json
{
  "scheme": "mls-rfc9420",
  "version": "1.0",
  "group_id": "base64url",
  "epoch": 12,
  "content_type": "application/json",
  "aad": {
    "space_id": "cx:space:01js0sp0000000000000000000",
    "event_kind": "cx.message.create",
    "event_ref_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
  },
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "cx:event:01js0mg0000000000000000000"
  }
}
```

4. `payload_metadata_bytes = canonical_json(payload_metadata)`。
5. `encrypted_payload_bytes = base64url_decode(ciphertext)`；若 envelope 含 `authentication_tag`，追加 `base64url_decode(authentication_tag)`。
6. `payload_digest = "sha256:" + sha256(payload_metadata_bytes || encrypted_payload_bytes)`。

`mls-rfc9420` profile 中，MLS PrivateMessage 本身还必须把 `aad_bytes` 作为 MLS authenticated data 或 profile 声明的等价 authenticated input；`payload_digest` 是 Contrix envelope 的外层完整性检查，不替代 MLS AEAD。

## 4. 加密方案

### 4.1 MLS (RFC 9420)

**标识符**：`mls-rfc9420`

**参数**：

- `group_id`：MLS 群组标识符
- `epoch`：当前 MLS epoch
- `ciphertext`：MLS 加密的应用消息，具体为 MLS PrivateMessage / application message 的序列化字节
- `authentication_tag`：不单独出现；认证标签、sender data、generation 和 nonce 由 MLS message framing 管理

**密钥材料**：

- 发送者使用 MLS secret tree 为每条 application message 派生的 key / nonce
- 接收者按 MLS epoch、sender 和 generation 从本地 group state 解密
- 密钥分发通过 MLS Welcome/Commit

### 4.2 未来方案

新方案 MUST：

- 使用唯一的 `scheme` 标识符
- 定义必需字段
- 指定密钥分发方式
- 保持 AAD 稳定性
- 在协议 schema 注册表中注册

## 5. 加密流程

### 5.1 发送方流程

```
1. 收集待加密内容
2. 序列化为字节（如 JSON UTF-8 字符串）
3. 从事件元数据生成 AAD
4. 调用 MLS library 构造 application PrivateMessage，并把规范 AAD 作为 MLS authenticated data 或 profile 声明的等价 authenticated input
5. 序列化 MLS PrivateMessage 为 `ciphertext`
6. 计算摘要
7. 组装信封
```

### 5.2 伪代码

```
function encrypt_content(content, aad, group_context):
    plaintext = serialize(content)
    aad_bytes = canonical_json(aad)
    private_message = mls_protect_application_message(group_context, plaintext, aad_bytes)
    ciphertext = serialize(private_message)
    payload_metadata = canonical_json({
        scheme: "mls-rfc9420",
        version: "1.0",
        group_id: group_context.id,
        epoch: group_context.epoch,
        content_type: "application/json",
        aad: aad
    })
    payload_digest = sha256(payload_metadata || ciphertext)
    aad_digest = sha256(aad_bytes)

    return {
        scheme: "mls-rfc9420",
        group_id: group_context.id,
        epoch: group_context.epoch,
        content_type: "application/json",
        ciphertext: base64url_encode(ciphertext),
        aad: aad,
        payload_digest: "sha256:" + payload_digest,
        aad_digest: "sha256:" + aad_digest
    }
```

## 6. 解密流程

### 6.1 接收方流程

```
1. 提取信封字段
2. 使用 aad_digest 验证 AAD 完整性
3. 使用 payload_digest 验证负载完整性
4. 获取 group_id/epoch 对应的 MLS group state
5. 使用 MLS library 和 AAD 解密 PrivateMessage
6. 将明文反序列化为内容
```

### 6.2 错误处理

| 错误 | 原因 | 响应 |
|------|------|------|
| `aad_digest_mismatch` | AAD 被篡改 | 拒绝整个事件 |
| `payload_digest_mismatch` | 密文损坏 | 拒绝整个事件 |
| `key_unavailable` | 缺少 epoch | 标记为 `decryption_pending`，按 `client-sync.md` 的 timeout / recovery 规则恢复 |
| `epoch_mismatch` | 错误的密钥 epoch | 回溯或获取 epoch；无法在 timeout 内恢复时标记 `decryption_failed` |
| `group_removed` | 不再是成员 | fail closed；不得向未授权成员请求密钥 |

`decryption_pending` 是有界恢复状态，不是永久展示状态。默认 timeout 为 7 天；超时后客户端 MUST 降级为 metadata-only `decryption_failed` 占位。连续 epoch 缺口过大时，客户端 SHOULD 使用 range-based recovery，从授权 peer、key backup、Archive Node 或 policy 声明的 Key Recovery Service 获取最小必要 epoch material。

## 7. 与事件的集成

### 7.1 带加密内容的事件

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "kind": "cx.message.create",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["cx:event:01js0et0000000000000000000"],
  "content": {
    "encrypted_envelope": {
      "scheme": "mls-rfc9420",
      ...
    }
  },
  "proofs": [...]
}
```

### 7.2 用于路由的明文 AAD

同步服务使用 AAD 字段进行路由：

- `space_id`：路由到正确的 Space
- `event_kind`：确定事件处理方式
- `causal_refs`：维护因果排序

以上操作均不需要解密。

## 8. 密钥分发

### 8.1 MLS KeyPackage

Actor 设备发布 KeyPackage 用于 MLS。Wire 形态以 [`device-crypto-verification.md` §7 KeyPackage Record](./device-crypto-verification.md) 为唯一规范来源；本节仅复述以方便阅读，发现差异时以 device-crypto-verification.md §7 为准。

```json
{
  "keypackage_id": "cx:mls:kp:01js0kp0000000000000000000",
  "principal_id": "did:web:alice.example.com",
  "device_id": "cx:device:01js0dv0000000000000000000",
  "public_key": "base64url...",
  "cipher_suites": ["MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519"],
  "extensions": {},
  "device_signature": "base64url...",
  "single_use": true,
  "expires_at": "2026-05-26T00:00:00Z"
}
```

字段语义：

- `principal_id`：拥有该 KeyPackage 的 principal DID。Server 不得仅根据 KeyPackage 的 `device_signature` 推导 principal；必须通过有效 `cx.device.authorized` state 校验该 device 当前归属 `principal_id`。
- `device_id`：发布 KeyPackage 的 device 的 typed ID。
- `device_signature`：由该 device 的当前签名 key 对 canonical KeyPackage bytes（不含 `device_signature` 自身）做的 detached 签名。
- `single_use=true` 时 KeyPackage 被消费后立即失效，不得用于第二个 Welcome。

### 8.2 Epoch 变更

当 MLS epoch 变更时：

1. 管理员发送 `cx.mls.commit` 事件
2. 包含新的 ratchet tree
3. 接收者更新 epoch 密钥
4. 新信封使用新 epoch

## 9. 安全考虑

### 9.1 前向安全

MLS 提供：

- 过去的消息无法用当前密钥解密
- Epoch 轮换更改群组秘密
- 被移除的成员无法解密新消息

### 9.2 后向安全

MLS 提供：

- 时间 T 的泄露不影响 T+1
- 使用新密钥材料的 epoch 轮换
- 推荐定期强制 epoch 轮换

### 9.3 重放防护

信封包含：

- AAD 中的 `event_id` 用于去重
- `epoch` 用于检测先前密钥重用
- 服务器强制事件 ID 唯一性

### 9.4 审计追踪

用于可审计 E2EE：

- 审计代理是 MLS 群组成员
- 解密访问通过 `cx.audit.accessed` 记录
- 所有成员可查看审计追踪

## 10. 性能考虑

### 10.1 信封大小

典型信封大小：

- AAD：约 100 字节
- 密文：内容长度 + 16 字节（标签）
- 元数据：约 50 字节
- 总计：内容 + 约 166 字节

### 10.2 密钥缓存

接收者应缓存：

- 按 `(group_id, epoch)` 索引的 epoch 密钥
- 定期刷新以保证后向安全
- 群组成员变更时失效

## 11. 测试

### 11.1 测试向量

实现必须通过：

- 加密/解密往返
- AAD 完整性验证
- 摘要计算
- MLS epoch 变更
- 多接收者场景

### 11.2 互操作性

测试矩阵：

- 不同 MLS 密码套件
- 不同内容类型
- 不同 AAD 配置
- 跨实现解密

## 12. 迁移路径

### 12.1 从明文迁移

将 Space 迁移到加密：

1. 在 Space policy 中添加 `encryption_profile`
2. 通过 `cx.mls.genesis` 创建 MLS 群组，并为新成员写入 durable `cx.mls.welcome`
3. 新内容加密
4. 既有内容保持明文

### 12.2 加密方案

添加新方案：

1. 注册方案标识符
2. 定义信封格式
3. 实现密钥分发
4. 保持 AAD 稳定性
5. 更新一致性测试

## 13. 一致性

实现 MUST：

- 接受本规范定义的 MLS 信封
- 解密前验证所有摘要
- 支持基于 AAD 的路由
- 优雅处理解密错误
- 对缺少密钥记录 `decryption_pending`

实现 SHOULD：

- 缓存 epoch 密钥以优化性能
- 支持多种密码套件
- 实现强制 epoch 轮换
- 提供密钥备份/恢复
- 在需要时支持审计模式

## 14. 示例

### 14.1 简单消息

```json
{
  "envelope": {
    "scheme": "mls-rfc9420",
    "group_id": "6yg7KVGVmA",
    "epoch": 42,
    "content_type": "application/json",
    "ciphertext": "SGVsbG8gV29ybGQ",
    "aad": {
      "space_id": "cx:space:01js0sp0000000000000000000",
      "event_kind": "cx.message.create",
      "event_ref_hash": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
      "causal_refs": []
    },
    "payload_digest": "sha256:abc123...",
    "aad_digest": "sha256:def456..."
  }
}
```

### 14.2 带附件引用

```json
{
  "content": {
    "body": {"encrypted_envelope": {...}},
    "attachments": [
      {
        "blob_ref": "cx:blob:...",
        "filename": "document.pdf",
        "encryption": {"encrypted_envelope": {...}}
      }
    ]
  }
}
```
