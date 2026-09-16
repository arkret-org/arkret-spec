---
title: File Transfer
status: candidate
normative: true
stability: v1
updated: 2026-07-29
see_also:
  - private-objects.md
  - personal-productivity.md
  - ../crypto-media/media-and-blob.md
  - ../sync/client-sync.md
  - ../../artifacts/schemas/file-transfer.schema.json
  - ../../artifacts/registry/account-data-key-registry.json
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具有规范约束力。

## 1. 范围

本文定义 principal-private 的跨设备文件传输收件箱，用于“把本地文件发送到自己的其它授权设备”这一类体验。它不是共享聊天消息、不是 Realm timeline 项，也不是 Blob service 的新上传接口。

实现声明 `ak.profile.file_transfer.v1` 时，MUST 支持：

- 用 `ak.self.blob.upload.create.v1` / `ak.self.blob.resource.get.v1` / `ak.self.blob.resource.head.v1` 承载文件密文字节。
- 用 `ak.account_data.set` 写入 `ak.file_transfer.v1:<transfer_key>` 加密 account-data 记录。
- 用 `ak.self.events.command.submit.v1` 承载 `ak.account_data.set` 的实际写入路径。
- 用 `ak.self.account.stream.subscribe.v1` 把 account-data 更新同步到 holder 的其它授权设备。
- 用 `ak.self.device_messages.command.send.v1` / `ak.self.device_messages.read.list.v1` 承载 device-bound key delivery（见 §4.2）。

文件传输记录 MUST NOT 写入共享 Realm history。用户之后若选择把该文件发送到某个聊天、Strand 或共享对象，客户端 MUST 重新执行目标 Event.kind 的授权检查，并生成新的共享 Event；不得把 file-transfer account-data key、file-transfer 密文 value、私有 `content_key` 或本地传输历史复制到 shared payload。

## 2. 存储与 key 派生

文件传输由两个对象组成：

1. **Blob ciphertext**：文件明文先在客户端本地加密，密文字节上传为 Blob。普通实现 SHOULD 把该 Blob 的 `realm_id` 绑定到 holder 的 Principal Control Realm 或其它 holder-owned private Realm，以便沿用 Blob quota、retention、legal hold 与 GC 规则。加密文件 Blob metadata 的 `media_type` SHOULD 是 `application/octet-stream`，`filename` SHOULD 省略；原始文件名、原始 MIME 与明文字节数只出现在加密 account-data 明文中。
2. **Account-data transfer record**：写入 `ak.file_transfer.v1:<transfer_key>`。value MUST 先验证为 `ak.schema.file_transfer.v1`，再作为 encrypted account-data 写入 `ak.account_data.set`。

`transfer_id` 由发送设备生成，MUST 至少包含 128 bit 随机熵，wire 形态见 `file-transfer.schema.json#/$defs/transfer_id`。`transfer_key` MUST 按下式派生：

```text
transfer_key = derive_account_data_key(transfer_id)
```

`derive_account_data_key` 与 `account_data_namespace_key` 的密钥归属见 [`account-data.md` §2](./account-data.md)；服务端不得获得该 namespace key。

`transfer_key` 只用于 account-data key。原始 `transfer_id`、`blob_ref`、文件名、MIME、目标设备 id 和任何明文 hash MUST NOT 出现在 account-data key 中。

## 3. Transfer Record

`ak.file_transfer.v1:<transfer_key>` 的 plaintext value 字段顺序与 `ak.schema.file_transfer.v1` 对齐：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `kind` | yes | 固定 `file_transfer`。 |
| `transfer_id` | yes | 发送设备生成的不透明 id；不进入 account-data key。 |
| `blob_ref` | yes | 存储的密文 Blob 引用。 |
| `blob_size_bytes` | yes | Blob 字节数，通常是 ciphertext + AEAD overhead。 |
| `media_type` | yes | 原始文件 MIME；只在 encrypted account-data 明文中出现。 |
| `filename` | no | 清理后的原始文件名；只在 encrypted account-data 明文中出现。 |
| `plaintext_size_bytes` | yes | 加密前文件字节数。 |
| `access` | yes | 封闭对象；`access.visibility` 取 `actor_private` 或 `device_bound`，`device_bound` 时必须携带互异的 `recipient_device_ids[]`，条目数 MUST 为 1–1,000。 |
| `encryption` | yes | 文件密文 AEAD、AAD 与 key-delivery descriptor。 |
| `origin_device_id` | yes | 发起上传的 `ak:device:<uuidv7>`。 |
| `created_at` | yes | 传输创建时间，RFC3339 UTC。 |
| `updated_hlc` | yes | LWW 状态合并用 HLC。 |
| `retention_expires_at` | yes | transfer record 最晚保留时间。 |
| `status` | yes | `available` / `downloaded` / `dismissed` / `deleted`。 |

Producer MUST NOT 写入任何明文文件 digest / hash 字段（例如 `plaintext_digest`、`plaintext_sha256`、`cleartext_sha256` 或任何同义明文字段）、裸 `sha256`、裸 `size` 或任何可枚举本地路径字段。Receiver 遇到这些字段 MUST fail closed；schema 的 `additionalProperties:false` 同样会拒绝未列入 `ak.schema.file_transfer.v1` 的同义字段，且 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 对这些字段名提供机器可检索的 hard reject 约束。

## 4. 加密与 key delivery

文件传输默认是服务端不可读内容。Producer MUST 对每个 transfer 生成 fresh content key，并使用 `ak.aead.xchacha20_poly1305.v1` 加密文件明文。除非 profile 后续显式定义可证明安全的 key-reuse 形态，content key MUST NOT 在多个 transfer 间复用。

大文件 SHOULD 使用分块流式 AEAD 形态（`ak.blob.stream_aead.v1`，见 [media-and-blob.md](../crypto-media/media-and-blob.md) §3.3），使接收设备能边下边验、内存有界，并在收到合法末段且重算 digest 与 content-addressed `blob_ref` 内嵌值一致前不把文件视为完整。选用该形态时，transfer record 的 `encryption` descriptor 只携带 `nonce_prefix` / `segment_bytes`（而非整文件形态的单 `nonce`），MUST NOT 携带 `segment_count`。双方 MUST 从已认证 record 令 `S=plaintext_size_bytes`、`B=encryption.segment_bytes`，唯一派生 `N=max(1,ceil(S/B))`；`1024 <= B <= 8388608` 且 `1 <= N <= 1048576`，必须在分配下载计划、派生密钥或处理密文前校验。空文件恰有一个携末段 flag 的空明文段，不得从 `blob_size_bytes` 或收到的密文长度反推段数。`ak.file_transfer.key.v1` 只投递 content-key envelope，不回声这些 record 字段。小文件与缩略图 MAY 继续使用整文件形态（`ak.blob.whole_file_aead.v1`）。无论形态如何，`blob_ref` 都是 Blob 密文字节摘要的唯一 wire carrier。

AEAD AAD MUST 至少绑定：

- `schema="ak.schema.file_transfer.v1"`
- `purpose="file_transfer"`
- `transfer_id`
- `origin_device_id`
- `created_at`

整文件 AAD 是 `encryption.aad` 的 RFC 8785 JCS bytes。stream 文件传输使用同一个 nonce/段序/末段算法，但密钥来自本节的 fresh content key，而不是 MLS `key_ref`。其逐段 AAD MUST 恰为 RFC 8785 JCS 对象 `{schema,purpose,transfer_id,origin_device_id,created_at,scheme,nonce_prefix,segment_index,last_segment_flag,segment_count,media_type,size_bytes}`：前五项取经本 record 逐字段相等校验的 `encryption.aad`，`scheme` 固定为 `ak.blob.stream_aead.v1`，`nonce_prefix` 取 descriptor，`segment_index` 为当前段的零基序号，`last_segment_flag` 为整数 `0` 或 `1`，`segment_count=N`，`size_bytes=S`，`media_type` 取 record。`segment_count` 只存在于本地重建的 AAD；MUST NOT 给 record 或 key message 增加该字段，也不得虚构 MLS `key_ref` 或 `epoch`。XChaCha20-Poly1305 的 `nonce_prefix` 解码后恰为 19 bytes，单 nonce 为 24 bytes；两者均为 canonical Base64URL-no-pad。密文为按序拼接的 N 段（每段包含 16-byte tag），接收方 MUST 校验每段 tag、精确末段、总明文长度和完整密文 digest，截断、额外字节及重排均拒绝。

AAD MUST NOT 绑定 content-addressed `blob_ref`，因为这会让 `blob_ref = digest(ciphertext)` 与 `ciphertext = AEAD(plaintext, aad(blob_ref))` 形成循环定义。Receiver MUST 在解密前从 `blob_ref` 恢复 suite/digest 并与实际下载字节的重算结果比较；不一致 MUST 拒绝、丢弃已下载字节、不得渲染或写入持久缓存。record 不携 `content_digest` 或任何第二个 ciphertext digest 副本。

### 4.1 `account_data_wrapped_key`

`access.visibility="actor_private"` 时，`encryption.key_delivery.method` MUST 是 `account_data_wrapped_key`。此时 `content_key` 存在于 encrypted account-data plaintext 中，所有能解开 holder encrypted account-data 的授权设备都可以解密该文件。

`content_key` MUST NOT 出现在 Blob metadata、shared Event、push payload、URL、日志、未加密 device message 或任何服务端明文可见字段中。

### 4.2 `to_device_wrapped_key`

当 `access.visibility="device_bound"` 时，`access.recipient_device_ids` 是目标设备集合的唯一真相源，且 `encryption.key_delivery.method` MUST 是 `to_device_wrapped_key`。Producer MUST 为 `access.recipient_device_ids` 中的每个目标设备发送一条 `kind="ak.file_transfer.key.v1"` 的 to-device message；message `content` MUST validate as `ak.schema.file_transfer.v1#/$defs/file_transfer_key_message`。

`ak.file_transfer.key.v1` 的 `key_envelope` MUST 使用接收设备的 HPKE / device key 加密 content key。服务端只可转发该 envelope，不得看到 content key 明文。该 message 的权威内容只有 `transfer_id`、`key_envelope` 与 `expires_at`；Receiver MUST 以 `transfer_id` 选择已认证、已解密的 exact account-data transfer record，并只从该 record 取得 `blob_ref`（其内嵌 digest 即 ciphertext commitment）、AEAD profile、nonce/nonce_prefix 与 segment 参数。`expires_at` 过期、record 不存在/未认证、envelope 无法在该 record 的 recipient/device context 下解开时 MUST 拒绝；不得接受 message 对这些 record 字段的回声或用回声替代 record 校验。

`key_envelope` 是 RFC 9180 base-mode 单发 authority commit（`SetupBaseS` / `SetupBaseR`），suite 由 `scheme` 选定。其 HPKE `info` 与 AEAD `aad` MUST 是同一份 bytes，即下列对象的 RFC 8785 JCS：

```text
file_transfer_key_aad = {
  device_message_id, kind: "ak.file_transfer.key.v1",
  <DeviceMessageEnvelope 实际存在的 closed sender branch 字段，逐字>,
  recipient_account_id, recipient_device_id, expires_at,
  transfer_id
}
info = aad = RFC8785_JCS(file_transfer_key_aad)
```

envelope 成员取承载该 message 的 `DeviceMessageEnvelope` 原始 canonical value：sender branch 是 `sender_account_id` + `sender_device_id`，或完整 `sender_agent_*` 三元组，缺席的 key 整体省略、不写 `null`；`expires_at` 逐字取 envelope 已验证的 `.sssZ` string；`transfer_id` 取 message content。该集合满足 [`../crypto-media/device-lifecycle.md` §7](../crypto-media/device-lifecycle.md) 的通用 AAD 最小集，且不含队列服务物化的 `sent_at`。Receiver 从已认证 envelope 与 content 确定性重建同一 bytes 后执行 `Open`；AAD 由该投影重算、不上 wire，`key_envelope` MUST NOT 携带 `aad_digest`、算法名或任何 record 字段回声（[`../conformance/encoding.md` §10](../conformance/encoding.md)），AAD 错误只表现为 HPKE open 失败并按上一段拒绝。

未列入 `recipient_device_ids` 的设备即使收到了 account-data record，也 MUST 把该 transfer 视为不可解密，不得尝试从其它本地缓存或历史消息中恢复 key。

## 5. 同步、冲突与状态

每个 file-transfer item 是独立 account-data 值，MUST NOT 使用一个不断增长的大列表作为唯一真相源。

状态更新（例如 `downloaded`、`dismissed`、`deleted`）写回同一个 `ak.file_transfer.v1:<transfer_key>`。v1 对该 key 固定采用 `current-value projection` 合并语义，registry row 只登记 `deletion_mode=value_tombstone`，不再复制 merge-strategy 常量：所有写入 MUST 走 [`account-data.md` §5](./account-data.md) 的 compare-and-set 循环，服务端只做 `expected_revision` 比较，下述状态规则 MUST 由客户端在解密明文上执行。

三个非 terminal 状态 `available`、`downloaded`、`dismissed` 之间允许双向迁移：重新下载可写 `downloaded`，从 UI 收起可写 `dismissed`，重新发送到同一授权设备集合前可写回 `available`；它们之间的冲突按 `(actor, transfer_key)` 做 last-writer-wins，比较源为 `updated_hlc`。`deleted` 是该 `transfer_key` 的不可逆 terminal tombstone，且 MUST 作为 value 永久保留在同一 key（而不是通过 `ak.self.account_data.resource.delete.v1` 物理删除），使任何长期离线设备重连后仍能观察删除事实：任一副本一旦观察到 `status="deleted"`，同一 `transfer_key` 后续或并发的非 deleted 状态 MUST NOT 复活该 transfer；需要重新发送时必须生成新的 `transfer_id` 与新的 `transfer_key`。多个 deleted tombstone 之间 MAY 用较新的 `updated_hlc` 更新保留元数据。

CAS 冲突（`cas_conflict`）时客户端 MUST 重新解密 `current_entry`、按上述规则合并后以新的 `expected_revision` 重写一次；离线设备的旧字节级 retry 因此必然失败，不会把已被覆盖的状态整体写回。如果设备本地时钟或 HLC 来源不可信，客户端 SHOULD 保留本地冲突副本供用户恢复，但 shared reducer 不参与 file-transfer 合并。

客户端断线恢复 MUST 使用 `ak.self.account.stream.subscribe.v1?after=<cursor>&catchup=true` 重放账号聚合 delta；不得用 `ak.self.events.read.scan.v1` 代替，因为 file-transfer account-data 和 to-device key messages 不属于裸 Realm Event 查询面。

## 6. 下载与访问控制

File-transfer Blob 下载 MUST 使用 authenticated download (`ak.self.blob.resource.get.v1`)。请求 `purpose` SHOULD 使用 `file_transfer`。私有或加密 file-transfer Blob MUST NOT 使用 `ak.self.blob.command.presign.v1`；presign 是可转发 bearer URL，不满足 private/E2EE 文件传输的审计与泄露边界。

Blob 服务对不可见或已删除 Blob SHOULD 返回与不存在一致的 `not_found`，不得通过 HEAD / Range probe 泄露文件名、MIME、精确大小或存在性。客户端下载后 MUST 重新计算 digest，并在解密成功前不得把原始文件名或预览暴露给非 holder 授权的服务。

## 7. Retention 与 GC

`retention_expires_at` 是 live transfer record 的最晚保留时间。到期后客户端 SHOULD 写回同一 key 的 terminal tombstone（`status="deleted"`，更新 `updated_hlc`），而不是写入未定义的独立 tombstone 结构；仅本地 UI 投影可以物理删除。服务端只见不透明 account-data 密文，既不得推断某 value 是否为 tombstone，也不得物理清理该 key；terminal value 的永久保留是防止长期离线设备复活旧 transfer 的协议条件。

Blob GC 仍按 [media-and-blob.md](../crypto-media/media-and-blob.md) §8 执行：只有没有 live reference、grace period 已过、未处于 legal hold 且 policy 允许时，Blob MAY 被清理。删除 file-transfer account-data record 不自动证明 Blob 可硬删除；实现需要保留最小 receipt 或执行部署 policy 要求的引用扫描。

## 8. 与共享附件的关系

File transfer 是 holder-private inbox，不是可共享附件对象。把文件转发到 Realm / Strand / Message 时，客户端 MUST 选择下列路径之一：

- 为目标 Realm / Circle 重新加密并上传新的 Realm-bound Blob，然后在新的 `ak.message.create` 或其它共享 Event 中引用该 Blob。
- 若 policy 明确允许复用同一 ciphertext Blob，生成新的共享 Event 只引用目标授权所需的 Blob descriptor，并重新包装目标 recipient 能解开的内容 key；不得复用 file-transfer account-data 的 `content_key` 字段。

任何情况下，共享 Event MUST NOT 引用 `ak.file_transfer.v1:<transfer_key>`，也不得泄露 file-transfer `transfer_id`、origin local path、私有 state 或 account-data ciphertext。
