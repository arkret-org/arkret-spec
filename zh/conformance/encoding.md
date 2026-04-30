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
  "schema": "cx.schema.commit.v1",
  "commit_id": "cx:commit:01JS0KE000000000000000000",
  "type": "commit",
  "repo_id": "did:web:alice.example",
  "author": "did:web:alice.example",
  "author_seq": 1,
  "prev_commit": "sha256:...",
  "operations": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`commit_hash = sha256(canonical_json(commit_without_proofs))`。`repo_id`、`author_seq`、`schema` 和 `type` 必须进入 hash，防止 Commit 被跨 repo 或跨序列重放。

## 6. Signature

默认 proof:

```json
{
  "kind": "detached_jws",
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

列表排序 rank MUST 使用 `cx.rank.lexofractional.v1` profile，除非 Space schema 显式声明其他 rank profile。

规则：

- 字符集固定为 ASCII `0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz`，按该字符集顺序比较。
- Rank MUST 是 1..128 字符的字符串，且每个字符 MUST 来自上述字符集。
- 排序 MUST 使用逐字符字典序；若一个字符串是另一个字符串的前缀，较短者排在较前。
- `rank_between(left, right)` MUST 返回一个严格满足 `left < rank < right` 的 rank；`left` 或 `right` MAY 为空，表示容器开头或结尾的哨兵边界。
- 标准 midpoint 算法：从左到右比较字符值；缺失的 left 字符视为 `-1`，缺失的 right 字符视为 `alphabet_length`。若 `right_value - left_value > 1`，输出当前前缀加中间字符 `floor((left_value + right_value) / 2)`；否则复制 left 当前字符并继续下一位。若 left 当前字符缺失且无间隙，复制 alphabet 第一个字符并继续。
- 当 rank 长度超过 128，或连续插入导致实现无法生成短 rank，客户端 SHOULD 请求或提交 `cx.container.rebalance`。Reducer 不得接受超过 128 字符的 rank。
- 同一 container 内 rank 完全相同的对象 MUST 按 `rank_source_hlc`、`rank_source_actor_id`、`rank_source_operation_id`、`entity_id` 继续排序；如果 rank source 元数据缺失，MUST 使用 `entity_id` 作为最终稳定 tie-break，并在 conformance report 中声明降级。
- `cx.container.rebalance` 的 assignment 生成 MUST 基于权限裁剪前的 canonical ordered set。先按 reducer 已确定的稳定顺序排列 active edges，再选择最小宽度 `w`，使 `alphabet_length^w >= 2 * (item_count + 1)`；第 `i` 个对象（1-based）的 rank number 为 `floor(i * alphabet_length^w / (item_count + 1))`，以固定宽度 base62 编码并用 alphabet 第一个字符左填充。若所需 `w > 128`，实现 MUST 拒绝该 rebalance。
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且不得新增、删除或跨 container 移动 edge。CAS 的 `expected_state_hash` 不匹配时，MUST 拒绝整个 operation，不得部分应用。

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
payload_digest = sha256(canonical_json(cleartext_metadata) || ciphertext_bytes)
```

`cleartext_metadata` 至少包含 `encryption`、`epoch` 与 `content_type`；当 envelope 带 `aad` 时，`aad` MUST 进入 `cleartext_metadata` 后一起参与 digest。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入。
