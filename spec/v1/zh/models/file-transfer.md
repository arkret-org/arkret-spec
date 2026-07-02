---
title: File Transfer
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - private-objects.md
  - personal-productivity.md
  - ../crypto-media/media-and-blob.md
  - ../sync/client-sync.md
  - ../../artifacts/schemas/file-transfer.schema.json
  - ../../artifacts/registry/account-data-type-registry.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

本文定义 principal-private 的跨设备文件传输收件箱，用于“把本地文件发送到自己的其它授权设备”这一类体验。它不是共享聊天消息、不是 Realm timeline 项，也不是 Blob service 的新上传接口。

实现声明 `ck.profile.file_transfer.v1` 时，MUST 支持：

- 用 `ck.self.blob.upload.create` / `ck.self.blob.resource.get` / `ck.self.blob.resource.head` 承载文件密文字节。
- 用 `ck.account_data.set` 写入 `ck.file_transfer.v1:<transfer_key>` 加密 account-data 记录。
- 用 `ck.self.events.command.submit` 承载 `ck.account_data.set` 的实际写入路径。
- 用 `ck.self.account.stream.subscribe` 把 account-data 更新同步到 holder 的其它授权设备。
- 用 `ck.self.device_messages.command.send` / `ck.self.device_messages.query.list` 承载 device-bound key delivery（见 §4.2）。

文件传输记录 MUST NOT 写入共享 Realm history。用户之后若选择把该文件发送到某个聊天、Strand 或共享对象，客户端 MUST 重新执行目标 Event.kind 的授权检查，并生成新的共享 Event；不得把 file-transfer account-data key、file-transfer 密文 value、私有 `content_key` 或本地传输历史复制到 shared payload。

## 2. 存储与 key 派生

文件传输由两个对象组成：

1. **Blob ciphertext**：文件明文先在客户端本地加密，密文字节上传为 Blob。普通实现 SHOULD 把该 Blob 的 `realm_id` 绑定到 holder 的 Principal Control Realm 或其它 holder-owned private Realm，以便沿用 Blob quota、retention、legal hold 与 GC 规则。加密文件 Blob metadata 的 `media_type` SHOULD 是 `application/octet-stream`，`filename` SHOULD 省略；原始文件名、原始 MIME 与明文字节数只出现在加密 account-data 明文中。
2. **Account-data transfer record**：写入 `ck.file_transfer.v1:<transfer_key>`。value MUST 先验证为 `ck.schema.file_transfer.v1`，再作为 encrypted account-data 写入 `ck.account_data.set`。

`transfer_id` 由发送设备生成，MUST 至少包含 128 bit 随机熵，wire 形态见 `file-transfer.schema.json#/$defs/transfer_id`。`transfer_key` MUST 按下式派生：

```text
transfer_key = derive_account_data_key(transfer_id)
```

`derive_account_data_key` 与 `account_data_namespace_key` 的密钥归属见 [`client-preferences.md` §2.2](../discovery/client-preferences.md)；服务端不得获得该 namespace key。

`transfer_key` 只用于 account-data key。原始 `transfer_id`、`blob_ref`、文件名、MIME、目标设备 id 和任何明文 hash MUST NOT 出现在 account-data key 中。

## 3. Transfer Record

`ck.file_transfer.v1:<transfer_key>` 的 plaintext value 字段顺序与 `ck.schema.file_transfer.v1` 对齐：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `kind` | yes | 固定 `file_transfer`。 |
| `transfer_id` | yes | 发送设备生成的不透明 id；不进入 account-data key。 |
| `blob_ref` | yes | 存储的密文 Blob 引用。 |
| `content_digest` | yes | Blob 字节 digest；对加密文件传输而言是 ciphertext digest，MUST NOT 是明文文件 hash。 |
| `blob_size_bytes` | yes | Blob 字节数，通常是 ciphertext + AEAD overhead。 |
| `media_type` | yes | 原始文件 MIME；只在 encrypted account-data 明文中出现。 |
| `filename` | no | 清理后的原始文件名；只在 encrypted account-data 明文中出现。 |
| `plaintext_size_bytes` | yes | 加密前文件字节数。 |
| `access` | yes | 封闭对象；`access.visibility` 取 `actor_private` 或 `device_bound`，`device_bound` 时必须携带 `recipient_device_ids[]`。 |
| `encryption` | yes | 文件密文 AEAD、AAD 与 key-delivery descriptor。 |
| `origin_device_id` | yes | 发起上传的 `ck:device:<uuid>`。 |
| `created_at` | yes | 传输创建时间，RFC3339 UTC。 |
| `updated_hlc` | yes | LWW 状态合并用 HLC。 |
| `retention_expires_at` | yes | transfer record 最晚保留时间。 |
| `state` | yes | `available` / `downloaded` / `dismissed` / `deleted`。 |

Producer MUST NOT 写入任何明文文件 digest / hash 字段（例如 `plaintext_digest`、`plaintext_sha256`、`cleartext_sha256` 或任何同义明文字段）、裸 `sha256`、裸 `size` 或任何可枚举本地路径字段。Receiver 遇到这些字段 MUST fail closed；schema 的 `additionalProperties:false` 同样会拒绝未列入 `ck.schema.file_transfer.v1` 的同义字段，且 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 对这些字段名提供机器可检索的 hard reject 约束。

## 4. 加密与 key delivery

文件传输默认是服务端不可读内容。Producer MUST 对每个 transfer 生成 fresh content key，并使用 `ck.aead.xchacha20_poly1305.v1` 加密文件明文。除非 profile 后续显式定义可证明安全的 key-reuse 形态，content key MUST NOT 在多个 transfer 间复用。

大文件 SHOULD 使用分块流式 AEAD 形态（`ck.blob.stream_aead.v1`，见 [media-and-blob.md](../crypto-media/media-and-blob.md) §3.3），使接收设备能边下边验、内存有界，并在收到合法末段并通过整体 `ciphertext_digest` 校验前不把文件视为完整。选用该形态时，transfer record 的 `encryption` descriptor 与 `ck.file_transfer.key.v1` 的 key envelope MUST 按该 scheme 携带 `nonce_prefix` / `segment_size` / `segment_count`（而非整文件形态的单 `nonce`）；§4.2 的字段一致性校验相应比对 `key_message.nonce_prefix == record.encryption.nonce_prefix`、segment 参数一致。小文件与缩略图 MAY 继续使用整文件形态（`ck.blob.whole_file_aead.v1`）。无论形态如何，`content_digest` 仍是 Blob 密文字节摘要的唯一字段。

AEAD AAD MUST 至少绑定：

- `schema="ck.schema.file_transfer.v1"`
- `purpose="file_transfer"`
- `transfer_id`
- `origin_device_id`
- `created_at`

AAD MUST NOT 绑定 content-addressed `blob_ref`，因为这会让 `blob_ref = digest(ciphertext)` 与 `ciphertext = AEAD(plaintext, aad(blob_ref))` 形成循环定义。Receiver MUST 在解密前校验 `blob_ref` 与 `content_digest` 均和实际下载字节一致；不一致 MUST 拒绝、丢弃已下载字节、不得渲染或写入持久缓存。`content_digest` 是 Blob 密文字节摘要的唯一字段，record 不得再嵌套第二个 ciphertext digest 副本。

### 4.1 `account_data_wrapped_key`

`access.visibility="actor_private"` 时，`encryption.key_delivery.method` MUST 是 `account_data_wrapped_key`。此时 `content_key` 存在于 encrypted account-data plaintext 中，所有能解开 holder encrypted account-data 的授权设备都可以解密该文件。

`content_key` MUST NOT 出现在 Blob metadata、shared Event、push payload、URL、日志、未加密 device message 或任何服务端明文可见字段中。

### 4.2 `to_device_wrapped_key`

当 `access.visibility="device_bound"` 时，`access.recipient_device_ids` 是目标设备集合的唯一真相源，且 `encryption.key_delivery.method` MUST 是 `to_device_wrapped_key`。Producer MUST 为 `access.recipient_device_ids` 中的每个目标设备发送一条 `kind="ck.file_transfer.key.v1"` 的 to-device message；message `content` MUST validate as `ck.schema.file_transfer.v1#/$defs/file_transfer_key_message`。

`ck.file_transfer.key.v1` 的 `key_envelope` MUST 使用接收设备的 HPKE / device key 加密 content key。服务端只可转发该 envelope，不得看到 content key 明文。Receiver MUST 校验 to-device message 中的字段与 account-data transfer record 的对应字段完全一致：`key_message.transfer_id == record.transfer_id`、`key_message.blob_ref == record.blob_ref`、`key_message.aead_profile == record.encryption.aead_profile`、`key_message.content_digest == record.content_digest`。若 `record.encryption.scheme == "ck.blob.whole_file_aead.v1"`，还 MUST 校验 `key_message.nonce == record.encryption.nonce`，且两侧均不得携带 stream 字段；若 `record.encryption.scheme == "ck.blob.stream_aead.v1"`，则 MUST 校验 `key_message.nonce_prefix == record.encryption.nonce_prefix`、`key_message.segment_size == record.encryption.segment_size`、`key_message.segment_count == record.encryption.segment_count`，且两侧均不得携带 whole-file `nonce`。不一致 MUST 拒绝该 key envelope。

未列入 `recipient_device_ids` 的设备即使收到了 account-data record，也 MUST 把该 transfer 视为不可解密，不得尝试从其它本地缓存或历史消息中恢复 key。

## 5. 同步、冲突与状态

每个 file-transfer item 是独立 account-data 值，MUST NOT 使用一个不断增长的大列表作为唯一真相源。

状态更新（例如 `downloaded`、`dismissed`、`deleted`）写回同一个 `ck.file_transfer.v1:<transfer_key>`。`deleted` 是该 `transfer_key` 的不可逆 terminal tombstone：任一副本一旦观察到 `state="deleted"`，同一 `transfer_key` 后续或并发的非 deleted 状态 MUST NOT 复活该 transfer；需要重新发送时必须生成新的 `transfer_id` 与新的 `transfer_key`。非 terminal 状态之间的冲突按 `(actor, transfer_key)` 做 last-writer-wins，比较源为 `updated_hlc`；多个 deleted tombstone 之间 MAY 用较新的 `updated_hlc` 更新保留元数据。如果设备本地时钟或 HLC 来源不可信，客户端 SHOULD 保留本地冲突副本供用户恢复，但 shared reducer 不参与 file-transfer 合并。

客户端断线恢复 MUST 使用 `ck.self.account.stream.subscribe?after=<cursor>&catchup=true` 重放账号聚合 delta；不得用 `ck.self.events.query.scan` 代替，因为 file-transfer account-data 和 to-device key messages 不属于裸 Realm Event 查询面。

## 6. 下载与访问控制

File-transfer Blob 下载 MUST 使用 authenticated download (`ck.self.blob.resource.get`)。请求 `purpose` SHOULD 使用 `file_transfer`。私有或加密 file-transfer Blob MUST NOT 使用 `ck.self.blob.command.presign`；presign 是可转发 bearer URL，不满足 private/E2EE 文件传输的审计与泄露边界。

Blob 服务对不可见或已删除 Blob SHOULD 返回与不存在一致的 `not_found`，不得通过 HEAD / Range probe 泄露文件名、MIME、精确大小或存在性。客户端下载后 MUST 重新计算 digest，并在解密成功前不得把原始文件名或预览暴露给非 holder 授权的服务。

## 7. Retention 与 GC

`retention_expires_at` 是 transfer record 的最晚保留时间。到期后客户端 SHOULD 写回同一 key 的 terminal tombstone（`state="deleted"`，更新 `updated_hlc`），而不是写入未定义的独立 tombstone 结构；仅本地 UI 投影可以物理删除。服务端 MAY 根据 encrypted account-data retention policy 在 tombstone 已同步并超过保留窗口后清理该 key。

Blob GC 仍按 [media-and-blob.md](../crypto-media/media-and-blob.md) §8 执行：只有没有 live reference、grace period 已过、未处于 legal hold 且 policy 允许时，Blob MAY 被清理。删除 file-transfer account-data record 不自动证明 Blob 可硬删除；实现需要保留最小 receipt 或执行部署 policy 要求的引用扫描。

## 8. 与共享附件的关系

File transfer 是 holder-private inbox，不是可共享附件对象。把文件转发到 Realm / Strand / Message 时，客户端 MUST 选择下列路径之一：

- 为目标 Realm / Circle 重新加密并上传新的 Realm-bound Blob，然后在新的 `ck.message.create` 或其它共享 Event 中引用该 Blob。
- 若 policy 明确允许复用同一 ciphertext Blob，生成新的共享 Event 只引用目标授权所需的 Blob descriptor，并重新包装目标 recipient 能解开的内容 key；不得复用 file-transfer account-data 的 `content_key` 字段。

任何情况下，共享 Event MUST NOT 引用 `ck.file_transfer.v1:<transfer_key>`，也不得泄露 file-transfer `transfer_id`、origin local path、私有 state 或 account-data ciphertext。
