---
title: Account Data
status: candidate
normative: true
stability: v1
updated: 2026-07-17
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 范围与存储模型

本文是 principal/actor-private Account Data 的存储、寻址、加密与 key 派生单一真相源。标准 data type 与产品语义仍由消费方文档定义，并登记在 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)。

账户私有数据 SHOULD 作为 encrypted account data 或 actor-private Event 保存。只有 holder 的受信任设备有权读写；Sync / Principal Server 只存储闭合加密 envelope 或不透明 bytes，不解析明文。每次 `ak.account_data.set` 是对一个 data type + key 的全量覆盖；跨设备 merge 规则由该 data type 的 registry row 声明，未声明时为 CAS/LWW whole-value replacement，不得猜测字段级 merge。

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

新的 principal/actor-private data type：基础存储、namespace derivation、value encryption 与 merge primitive 归本文；字段语义放在最接近功能域的消费方文档；机器索引统一写 `account-data-key-registry.json`。消费方 MUST 引用本文，不得重新定义 namespace key、HKDF/AAD transcript 或默认存储边界。
