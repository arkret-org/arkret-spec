# Encoding, IDs, Hashes, Signatures

## 1. 目标

本文定义 Contrix 的 canonical encoding、ID、hash、signature、cursor、HLC 与 rank 编码规则，确保不同实现能得到相同 digest 和验证结果。

## 2. Canonical JSON

Contrix canonical JSON MUST 使用：

- UTF-8
- object key 按 Unicode code point 升序排序
- 无 insignificant whitespace
- number 不得使用 NaN / Infinity
- timestamp 使用 RFC 3339 UTC，尾部 `Z`
- 字段名使用 snake_case

签名和 hash 输入 MUST 是 canonical JSON bytes。

## 3. Hash

默认 hash:

```text
sha256:<lowercase_hex_digest>
```

未来 MAY 支持 multihash，但初版 conformance MUST 支持 SHA-256。

## 4. ID

ID 格式：

```text
cx:<kind>:<ulid>
```

常见 kind：

- `space`
- `entity`
- `relation`
- `event`
- `commit`
- `operation`
- `grant`
- `view`
- `blob`
- `txn`

ULID MUST 使用 Crockford Base32 大写或规范小写之一；同一 profile MUST 固定大小写。Contrix canonical 文本推荐小写。

## 5. Commit Hash

```json
{
  "commit_id": "cx:commit:01JS0KE000000000000000000",
  "prev_commit": "sha256:...",
  "operations": ["sha256:..."],
  "author": "did:web:alice.example",
  "created_at": "2026-04-26T00:00:00Z"
}
```

`commit_hash = sha256(canonical_json(commit_without_proof))`。

## 6. Signature

默认 proof:

```json
{
  "type": "detached_jws",
  "alg": "EdDSA",
  "verification_method": "did:web:alice.example#device-1",
  "payload_hash": "sha256:...",
  "jws": "..."
}
```

Proof MUST bind:

- payload hash
- actor DID
- verification method
- domain / audience where applicable
- created_at

## 7. HLC

Hybrid Logical Clock 编码：

```text
<unix_ms_hex>-<logical_hex>-<node_id_hash>
```

示例：

```text
01970e589d21-0004-a13f9c2e
```

排序按 `(unix_ms, logical, node_id_hash)` 字典序。

## 8. Cursor

Cursor 是不透明字符串：

```text
cx:cursor:<base64url>
```

Cursor 内容 MAY 包含：

- query hash
- last sort key
- last event id
- frontier
- expiry

客户端 MUST NOT 解析 cursor。

## 9. Rank

列表排序 rank SHOULD 使用可插入的 lexicographic rank 字符串。

规则：

- rank MUST 稳定排序
- rank SHOULD 支持在两个 rank 之间生成新 rank
- rank conflict 用 HLC + actor_id tie-break

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
payload_digest = sha256(canonical_json(cleartext_metadata) || ciphertext_bytes)
```
