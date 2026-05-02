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

协议 wire / canonical object 层的 typed ID 格式：

```text
cx:<kind>:<ulid>
```

标准 `kind` 的机器可读 source of truth 是 `artifacts/registry/id-kind-registry.json`。本文只定义通用规则。

`cx:` 前缀表示 Contrix 协议命名空间；`<kind>` 表示对象或引用类型；`<ulid>` 是该类型下的稳定 ID。完整 typed ID 是 wire value 的一部分，MUST 出现在：

- Event Envelope、canonical object、receipt、snapshot、fixture 和 OpenAPI / non-HTTP DTO。
- canonical JSON、签名 payload、`payload_hash`、event digest、cursor 内部 state、federation payload、audit log。
- 跨服务引用、日志和错误响应中需要自描述对象类型的字段。

数据库或本地索引实现 MAY 不把 `cx:<kind>:` 前缀作为主键的一部分存储。例如 `receipts` 表可以只存 `d1sc01j0000000000000000000`，因为表名或显式 `kind` 列已经提供类型上下文。实现若这样存储，MUST 在进入 canonical JSON、签名、hash、联邦转发、sync cursor、audit replay 或 API response 前恢复完整 typed ID。接收方验证签名、hash、backfill 或 replay 时，MUST 按完整 typed ID 比较，不得用数据库 row id、自增 id、表名推断或隐式转换替代 wire value。

`<kind>` 是 canonical bytes 的一部分。实现不得把 `cx:receipt:<id>` 改写成 `cx:event:<id>`，也不得因为字段名叫 `receipt_id` 就在验证时补前缀。字段名可以辅助 schema 校验，但不能替代 signed wire ID。

v1 wire、JSON Schema、registry、fixture 和所有签名 canonical object 中的 ULID 部分 MUST 使用小写 Crockford Base32 字符集 `[0-9a-hjkmnp-z]`，并且不得包含 `i`、`l`、`o`、`u`。旧草案或外部导入数据 MAY 使用大写 ULID；实现必须在生成 v1 Event Envelope、object id、cursor payload 或 proof `payload_hash` 前把它规范化为小写。已经进入签名 canonical bytes 的 ID 不得在验证、转发、backfill 或审计回放时重写大小写。

特殊 ID/ref 形式：

- `cx:cursor:<base64url>` 是 opaque token，不是 typed ULID object ID。
- `cx:blob:sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` 是内容寻址 Blob ref；`cx:blob:01js0bm0000000000000000000` 是 Blob metadata ID。二者不得混用。
- `cx:mls:<profile>:<profile_id>`、`cx:pseudonym:<scope_id>:<random>` 等 profile-scoped form 必须由对应 profile 注册和校验。

自定义 profile 若新增 `cx:<kind>:` 前缀，MUST 在 profile registry 或扩展 registry 中声明 kind、wire form、存储边界和校验规则。未注册的 `cx:<kind>:` typed ID MUST 被视为未知 critical wire type，除非所在字段明确允许 opaque string。

## 5. Event Batch Receipt Hash

```json
{
  "schema": "cx.schema.event_batch_receipt.v1",
  "receipt_id": "cx:receipt:01js0rc0000000000000000000",
  "type": "event_batch_receipt",
  "issuer": "did:web:alice.example",
  "scope": {
    "actor_id": "did:web:alice.example"
  },
  "frontier": {
    "actor_seq": 1,
    "event_hash": "sha256:..."
  },
  "events": ["sha256:..."],
  "created_at": "2026-04-26T00:00:00Z"
}
```

`receipt_hash = sha256(canonical_json(receipt_without_proofs))`。`issuer`、`scope`、`frontier`、`events`、`schema` 和 `type` 必须进入 hash，防止 receipt 被跨 actor、跨 Space 或跨前沿重放。

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
- `rank_between(left, right)` MUST 返回一个严格满足 `left < rank < right` 的 rank，或返回规范错误 `rank_exhausted`。`left` 或 `right` MAY 为空，表示容器开头或结尾的哨兵边界。
- 标准 midpoint 算法 MUST 是有界算法，不能在无间隙边界无限循环。参考伪代码：

```text
alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
base = len(alphabet)
min = -1
max = base

rank_between(left, right):
  assert left == "" or all chars in alphabet
  assert right == "" or all chars in alphabet
  assert right == "" or left == "" or left < right
  prefix = ""
  i = 0
  while len(prefix) < 128:
    l = value(left[i]) if i < len(left) else min
    r = value(right[i]) if right != "" and i < len(right) else max
    if r - l > 1:
      return prefix + alphabet[floor((l + r) / 2)]
    if i < len(left):
      prefix += left[i]
    else:
      prefix += alphabet[0]
      if right != "" and prefix == right:
        return rank_exhausted
      return prefix
    i += 1
  return rank_exhausted
```

例如 `rank_between("", "0")` MUST 返回 `rank_exhausted`，因为在 start sentinel 与最小 rank `"0"` 之间不存在合法 rank。客户端或 reducer 遇到 `rank_exhausted` MUST 触发 rebalance 或要求调用方提交 `cx.container.rebalance`，不得生成非法 rank。
- 当 rank 长度超过 128，或连续插入导致实现无法生成短 rank，客户端 SHOULD 请求或提交 `cx.container.rebalance`。Reducer 不得接受超过 128 字符的 rank。
- 同一 container 内 rank 完全相同的对象 MUST 按 `rank_source_hlc`、`rank_source_actor_id`、`rank_source_event_id`、`object_id` 继续排序；如果 rank source 元数据缺失，MUST 使用 `object_id` 作为最终稳定 tie-break，并在 conformance report 中声明降级。
- `cx.container.rebalance` 的 assignment 生成 MUST 基于权限裁剪前的 canonical ordered set。先按 reducer 已确定的稳定顺序排列 active edges，再选择最小宽度 `w`，使 `alphabet_length^w >= 2 * (item_count + 1)`；第 `i` 个对象（1-based）的 rank number 为 `floor(i * alphabet_length^w / (item_count + 1))`，以固定宽度 base62 编码并用 alphabet 第一个字符左填充。若所需 `w > 128`，实现 MUST 拒绝该 rebalance。
- Rebalance assignments MUST 覆盖 container 内全部 active edges，且不得新增、删除或跨 container 移动 edge。CAS 的 `expected_state_hash` 不匹配时，MUST 拒绝整个 operation，不得部分应用。

## 10. Encrypted Envelope Digest

加密 payload 的 digest MUST 覆盖密文和明文路由元数据：

```text
payload_digest = sha256(canonical_json(cleartext_metadata) || ciphertext_bytes)
```

`cleartext_metadata` 至少包含 `encryption`、`epoch` 与 `content_type`；当 envelope 带 `aad` 时，`aad` MUST 进入 `cleartext_metadata` 后一起参与 digest。实现 MUST NOT 使用明文 payload 作为 `payload_digest` 输入。
