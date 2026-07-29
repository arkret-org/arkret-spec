---
title: Account Data
status: candidate
normative: true
stability: v1
updated: 2026-07-29
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 范围与存储模型

本文是 principal/actor-private Account Data 的存储、寻址、加密与 key 派生单一真相源。标准 data type 与产品语义仍由消费方文档定义，并登记在 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)。

账户私有数据 SHOULD 作为 encrypted account data 或 actor-private Event 保存。只有 holder 的受信任设备有权读写；Sync / Principal Server 只存储闭合加密 envelope 或不透明 bytes，不解析明文。每次 `ak.account_data.set` 是对一个 data type + key 的全量覆盖。跨设备并发写入契约见 §5：每个 key 都是 **server-versioned compare-and-set whole-value register**，merge primitive 由 registry row 的 `merge_strategy` 显式声明，没有隐式默认，也不得猜测字段级 merge。

## 2. Namespace key 与不透明寻址（normative）

需要从私有对象引用、集合名、搜索索引 shard 或其它敏感输入派生 account-data key 片段时，producer MUST 使用同一 principal 的 `account_data_namespace_key`。该密钥属于 client-local `secret_storage/account_data_namespace/v1` 子域，并按 [`../identity/key-management.md` §7.1 / §7.10](../identity/key-management.md) 进入备份与轮换；server、Directory、Search 与 relay MUST NOT 获得。

标准 primitive：

```text
derive_account_data_key(input) = base64url(HMAC-SHA256(account_data_namespace_key, input))
```

`input` MUST 是 canonical JSON、typed id 或消费方逐项定义的规范化 bytes。不同 principal 的 namespace key MUST 独立。轮换后，客户端 MUST 用新 key 重写相应 encrypted value，并在同一更新事务中 tombstone 旧 key，或保留有界只读迁移索引；不得把同一私有对象长期映射到两个可链接 key。

## 3. Value encryption（normative）

registry 中 `storage="encrypted_account_data"` 的 value MUST 使用 `ak.schema.account_data_encrypted_value.v1`，不得以摘要或固定字符串冒充 ciphertext。Envelope 使用 `ak.aead.xchacha20_poly1305.v1`，每次写入 MUST 生成新的 24-byte 随机 nonce。AEAD key 由同一 principal 的 32-byte account secret 通过 HKDF-SHA256 派生：

- salt = `arkret-account-data-value-hkdf-v1`
- info = `canonical_json({schema:"ak.schema.account_data_encrypted_value.v1",actor_id,account_data_key})`

account secret 属于 `secret_storage`，MUST 进入 key-backup / recovery lifecycle；不同 principal 与不同 `account_data_key` 的派生 key MUST 域隔离。

AEAD AAD 是 envelope `aad` 的 canonical JSON，且 MUST 精确包含 `actor_id`、`account_data_key`、`schema`、`version`。该对象即本 domain 在 [`../conformance/encoding.md` §10.2](../conformance/encoding.md) 意义上的 **pre-encryption immutable header**：四个字段全部在 AEAD seal 前确定。`aad_digest` 是该 canonical JSON 的 `sha256:` digest；`ciphertext_digest` 是解码后 ciphertext bytes 的 `sha256:` digest。两者都是 header 之外的字段，MUST NOT 进入 AAD——`ciphertext_digest` 覆盖含 AEAD tag 的完整密文，把它放回 AAD 会形成不可构造循环。Consumer MUST 在解密前验证闭合 schema、AAD actor/path/data-type 绑定与两个 digest（`aad_digest` 由 consumer 从 envelope 重建 `aad` 后重算比对，MUST NOT 采信调用方自报值代替 AAD）；任一不匹配 MUST fail closed，且不得以失败结果覆盖本地已验证状态。Server MAY 重算 digest 与验证 envelope 结构，但 MUST NOT 获得 account secret、派生 key 或明文。

## 4. 文档放置规则

新的 principal/actor-private data type：基础存储、namespace derivation、value encryption 与 merge primitive 归本文；字段语义放在最接近功能域的消费方文档；机器索引统一写 `account-data-key-registry.json`。消费方 MUST 引用本文，不得重新定义 namespace key、HKDF/AAD transcript、默认存储边界或 §5 的并发写入契约。

## 5. 并发写入与收敛契约（normative）

服务端只看到不透明密文，因此它 MUST NOT 执行任何领域 merge。跨设备收敛由**服务端强制的 compare-and-set**加上**客户端在明文上的领域规则**共同完成。

### 5.1 Revision register

每个 `(actor_id, account_data_key)` 是一个 whole-value register，带一个无符号整数 `revision`：

- `revision = 0` 表示该 key 从未被写入。
- 每次被接受的写入（包括 tombstone 写入）存储 `expected_revision + 1`。
- `revision` 是**高水位**：MUST NOT 回退。即使 tombstone 已被 GC，服务端仍 MUST 保留该 key 的最后 `revision`。

`ak.account_data.set` payload 与 `ak.self.account_data.resource.replace` request body MUST 携带 `expected_revision`；`ak.self.account_data.resource.delete` MUST 以同名 query 参数携带。创建一个从未写入的 key 使用 `expected_revision=0`。

服务端 MUST 在同一 key 上原子地比较并写入：`expected_revision` 不等于当前 `revision` 时 MUST 以 `cas_conflict` 拒绝，MUST NOT 存储任何内容、MUST NOT 推进 `revision`，也 MUST NOT 向其它设备 fanout。因此设备 A 的旧字节级 retry 在设备 B 的新写之后必然失败，而不是把 key 整体退回旧值。

### 5.2 冲突响应与客户端重试

`cas_conflict` 与 `resource.get` 的 `not_found` MUST 使用闭合 details 形态
[`account-data-operations.schema.json#/$defs/account_data_cas_conflict_details`](../../artifacts/schemas/account-data-operations.schema.json)：至少包含 `account_data_key` 与 `current_revision`；当前持有 live value 时 MUST 附带 `current_entry`，使客户端无需第二次往返即可解密、合并并发出**恰好一次**新的 CAS 写。key 未设置或处于 tombstone 时 MUST 省略 `current_entry`，`current_revision` 仍然权威。

客户端重试循环 MUST 是：读取当前 `(revision, content)` → 解密 → 按该 data type 的领域规则（例如 HLC last-writer-wins、delete-wins、集合并）在明文上合并 → 用 `expected_revision = current_revision` 重新加密写回。领域规则因此运行在客户端，而不是被伪装成服务端能力。

### 5.3 删除与不可复活终态

`deletion_mode` 由 registry row 声明：

- `physical_delete`：`ak.self.account_data.resource.delete` 写入一个有版本的 tombstone，`revision` 推进；`resource.get` 返回 `not_found` 并在 details 中给出 `current_revision`。服务端 MAY 在不短于 `account_data_tombstone_retention_ms`（见 [`../conformance/scalability-constraints.md` §7](../conformance/scalability-constraints.md)）后 GC tombstone 元数据，但 MUST 永久保留 `revision` 高水位。该 key 之后 MAY 被重新创建：调用方以 `expected_revision = current_revision` 写入即可。
- `value_tombstone`：删除态本身是一个通过 `ak.account_data.set` 写入的 value（例如 `status="deleted"`）。这类 key MUST NOT 使用 `resource.delete`，因为其领域要求删除是**不可复活的终态**，必须在 tombstone GC 之后仍然可被任何设备观察到。

### 5.4 登记要求

`account-data-key-registry.json` 的每一行 MUST 声明 `merge_strategy` 与 `deletion_mode`，不存在隐式默认。v1 的 `merge_strategy` 闭集只有 `cas_register`。引入任何无协调 merge primitive MUST 在同一行同时登记比较 transcript、tombstone 规则与 active conformance vector；MUST NOT 使用"CAS/LWW"一类不指定比较键与冲突返回的模糊表述。

可执行覆盖见 [`../conformance/conformance-vectors.md` §5.10](../conformance/conformance-vectors.md) 的 `ak.vector.account_data.cas_convergence.v1`。
