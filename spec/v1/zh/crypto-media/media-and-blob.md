---
title: Media and Blob
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Blob service 提供内容寻址存储。Media profile 在 Blob 之上定义 MIME、缩略图、认证下载、加密附件和保留策略。

## 2. Blob Metadata

```json fragment
{
  "blob_id": "ak:blob:019a7360-0000-7000-8000-000000000004",
  "schema": "ak.schema.blob.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "content_digest": "sha256:...",
  "size_bytes": 1234,
  "media_type": "image/png",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": null
}
```
字段规则：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `blob_id` | `string` | required | Blob metadata 资源的 producer-allocated UUIDv7 身份；不承诺内容字节。 |
| `schema` | `ak.schema.blob.v1` | required | Blob metadata schema discriminator。 |
| `realm_id` | `id:realm` | conditional | Owning Realm。普通用户/组织上传 MUST 设置，用于授权、asset privacy policy enforcement、retention 与 GC。仅当 deployment policy 显式声明的全局/跨 Realm 服务 blob（例如 avatar 公共预览）才可省略。 |
| `content_digest` | `digest` | required | 服务端计算的内容 digest，wire 形态为 `<algo>:<lowercase_hex>`。 |
| `size_bytes` | `int` | required | 字节大小。 |
| `media_type` | `string` | optional | 上传声明或服务端校正后的 MIME。缺省为 `application/octet-stream`。 |
| `created_by` | `ActorId` | required | 上传 Actor 或 service 的完整 Arkret 身份。 |
| `created_at` | `datetime` | required | 服务端接收时间。 |
| `updated_by` | `ActorId` | optional | 最近更新 Blob metadata 的 Actor 或 service 的完整 Arkret 身份。 |
| `updated_at` | `datetime` | optional | 最近更新时间。 |
| `filename` | `string` | optional | 用户提供或服务生成的文件名；不得用于路径拼接。 |
| `encryption` | `object/null` | required | 加密附件元数据或 `null`。 |

命名说明：`blob_id=ak:blob:<uuidv7>` 只标识 Blob metadata 资源，`blob_ref=ak:blob:<suite>:<hex>` 只标识并承诺 exact content bytes；两者的 schema 形态互斥，consumer 不得按值猜测一种字段的含义。Blob metadata、Media metadata 和 Content Block descriptor 中的字节数统一使用 `size_bytes`；不得使用裸 `size` 表示字节数（见 [`models/common-fields.md` §3.0.1](../models/common-fields.md#301-size-字段命名)）。Blob metadata 以 `content_digest` 承诺其 metadata id 对应的内容；任何携带 content-addressed `blob_ref` 的 carrier 不得再携同原像 `content_digest` / `ciphertext_digest` 镜像。

上传请求 schema 见 [`blob-operations.schema.json#/$defs/upload_request`](../../artifacts/schemas/blob-operations.schema.json)，响应 schema 见 [`blob-operations.schema.json#/$defs/upload_response`](../../artifacts/schemas/blob-operations.schema.json)。

上传规则：

- Canonical HTTP upload body MUST be `multipart/form-data` with a required `content` binary part and required `size_bytes` metadata field. The `content` part `Content-Type` is optional; its default value is `application/octet-stream`.
- 客户端 SHOULD 提供准确 `Content-Type`，但服务端 MUST 把上传声明的 MIME 和文件名视为不可信 metadata。
- 如果服务端发现声明 MIME 与内容明显冲突，MAY 把 `media_type` 降级为 `application/octet-stream`，并记录安全标记。
- 文件名 MUST 做控制字符、路径分隔符和过长字段清理；不得影响 `blob_ref` 或存储路径。
- `upload_receipt` 若返回，MUST 绑定 content-addressed `blob_ref`、`size_bytes`、`received_at` 与 `issuer_id`，并由 Blob Service DID 对 receipt canonical bytes 签名；digest 从 `blob_ref` 唯一恢复，不得作为 sibling 字段重复；receipt 不得作为开放实现私有对象返回。
- 大文件 / 弱网场景 MAY 通过 §2.1 的可续传上传 binding 完成同一次上传；该 binding 是可选扩展，是否支持以及如何发现见 §2.1 与 [`sync/service-surface.md` §3](../sync/service-surface.md)。

### 2.1 可续传上传（Resumable Upload binding，optional extension）

可续传上传是 `ak.self.blob.upload.create.v1` 操作的**可选替代传输 binding**，面向大文件与弱网下的断点续传。它不是新的 operation_id，也不改变 Blob 的内容寻址与 receipt 语义；§2 的上传规则（声明 metadata 不可信、文件名清理、receipt 签名）对该 binding 同样适用。普通实现 MAY 暴露该 binding；当服务端未在 `/_arkret/describe` 声明该能力时，客户端 MUST 回退到 §2 的 canonical `multipart/form-data` 上传，不得对猜测的 endpoint 直接发起续传。

TUS 创建请求的 `POST` MUST 携带
`Arkret-Operation: ak.self.blob.upload.create.v1`；即使当前 advertised candidate 只有该版本也不得省略。
服务端 MUST 在读取 upload metadata/body 之前验证 selector。缺失返回 `operation_selector_required`；未知、
未广告或与 route family 不匹配时返回 `unsupported_operation_version`。后续 `PATCH` / `HEAD` / `DELETE`
同样 MUST 携带创建资源时绑定的 exact `Arkret-Operation`，不得另行选择或从 payload 推导其他 schema 版本。

**协议绑定（normative）**

- 该 binding MUST 采用 tus resumable upload 协议，当前 baseline 为 `tus 1.0.0`。服务端 MUST 支持 `creation` 扩展；SHOULD 支持 `creation-with-upload`、`checksum`、`expiration` 与 `termination`。
- 创建续传资源（tus `POST`）所需的认证、capability（`ak.self.blob.upload.create.v1`）与 quota（`blob_max_bytes`）与 canonical 上传完全一致。后续 `PATCH`（写入 segment）、`HEAD`（查询 `Upload-Offset` 续传点）、`DELETE`（终止）作用于服务端返回的 upload URL，是 tus 原生 verb，不注册为独立 arkret operation。

**内容寻址不变式（normative）**

- 续传只是字节传输方式。所有 segment 组装完成后，服务端 MUST 对完整字节计算 Realm-selected digest 并编码为最终 `blob_ref`；同一字节序列走 §2 canonical multipart 上传必须得到 byte-identical `blob_ref`，并按 §2 规则签发不含 sibling digest 的 `upload_receipt`。独立 Blob metadata 资源仍以 `blob_id` + `content_digest` 表达其身份与内容承诺。
- tus 的 offset 分块（`Upload-Offset` / 每个 `PATCH` chunk）是**传输层切分**，与加密附件 `ak.blob.stream_aead.v1`（§3.3）的 **AEAD segment** 是两个独立维度：实现 MUST NOT 把 tus chunk 边界与 AEAD segment 边界互相约束或混为一谈。续传承载的始终是（可能已在客户端 AEAD 加密的）Blob 字节，加密形态由客户端在上传前决定。

**能力发现（normative）**

- 该 binding 按 [`sync/transport-bindings.md` §6.1](../sync/transport-bindings.md) 分类为 **per-operation HTTP 伴生 binding**：本节即其 normative binding 文档，不需要独立 `ak.profile.binding.*` profile。
- 支持该 binding 的服务端 MUST 在 `/_arkret/describe` 同时声明：
  - `supported_features` 含 `ak.feature.blob.resumable_upload.tus.v1`；
  - `transport_bindings` 含一条 `kind="tus"` 的 binding，携带 tus endpoint 的 `base_url`、`operations: ["ak.self.blob.upload.create.v1"]`、`extension_profile_required: null`、`tus_version`（支持的协议版本列表）与 `tus_extensions`（支持的扩展列表）；
  - `limits` 携带下文的续传相关上限。
- 该 binding 只伴随 authenticated `ak.self.blob.upload.create.v1`，目标固定为当前账号会话已经绑定的自己 Station；v1 不允许客户端从任意 `blob_node` describe 选择一个写入目标。客户端首次接受 binding、binding / policy 变化或会话/route freshness 失效时，MUST 核对当前会话的 exact Station/HTTPS origin 与 describe 中该 operation 的声明；不得为此下载 DID 历史或信任陌生 endpoint 自报。`/_arkret/describe` 是**服务级**能力声明面；tus `OPTIONS` 响应（`Tus-Resumable`、`Tus-Version`、`Tus-Extension`、`Tus-Max-Size`）是 **endpoint 级**的线上确认。二者 MUST 一致；冲突时客户端以已绑定自己 Station 的 describe 与服务端实际拒绝为准，不得仅凭对猜测 endpoint 的裸 `OPTIONS` 探测作为发现手段。跨 Station/独立 Blob 服务若未来需要该 binding，必须先登记具体代理/结果合同；本节不提供该能力。

**隐私（normative）**

- tus `Upload-Metadata` header MUST NOT 携带私有或 E2EE Blob 的明文文件名、MIME 或任何可枚举本地路径；此类 Blob 的 `Upload-Metadata` SHOULD 省略，至多携带字节数。原始文件名 / MIME 的归属与 [`models/file-transfer.md` §2](../models/file-transfer.md) 的 file-transfer 规则一致。
- upload URL MUST 按 authenticated 资源处理：每个 tus 请求（`POST`/`PATCH`/`HEAD`/`DELETE`）MUST 独立认证；upload URL MUST NOT 作为可转发 bearer 凭证对待——这与 §5.4 presign 的只读 bearer URL 边界相反：presign 仅授权只读 `get`/`head`，续传是写路径。

**过期与 GC**

- 未完成的续传资源 MUST 有有限生命周期。服务端 SHOULD 支持 tus `expiration` 扩展并通过 `Upload-Expires` 暴露过期时间。未完成上传 MUST NOT 产生可被 Event / account-data 引用的 `blob_ref`；到期后服务端 MAY 直接回收已接收的部分字节。

**`limits` 键**

- `resumable_upload_incomplete_ttl_seconds`：未完成续传 part 的最长保留秒数。
- `resumable_upload_max_bytes`（optional）：单次续传上传上限；省略时回退到 canonical `blob_max_bytes` / `max_body_bytes` 语义。
- `resumable_upload_min_chunk_bytes`（optional）：服务端要求的最小非末段 `PATCH` chunk 字节数。

**版本与前向兼容**

- 当前 baseline 是 tus 1.0.0。IETF httpbis 的 *Resumable Uploads*（`draft-ietf-httpbis-resumable-upload`）标准化后，其 binding MUST 通过单独登记的 feature id 与新的 `transport_bindings.kind` 增量声明，不改写本节 tus 1.0.0 语义；客户端按 describe 声明的 feature / binding 选择具体协议，对两者均可同时声明的服务端 SHOULD 优先选用其支持的最新标准化形态。

## 3. Encrypted Attachment

加密附件的 `key_ref` MUST 是 closed MLS group-binding 对象 `{algorithm:"MLS",group_state_ref}`；current v1
不存在 `{algorithm,key_id}` 或其他 profile 分支。MLS 附件 epoch 不在 wire 上重复声明；其唯一派生式为
`attachment_epoch = resolve_exact_winning_group_state(key_ref.group_state_ref).epoch`。Event ref 必须解析到
accepted genesis 或 winning commit，proof hash 必须解析到等价的 exact winning group state；无法解析、非
winning state、hash/ref 歧义或缺少该 state 时 MUST 在密钥派生和解密前 fail closed。

```json fragment
{
  "blob_ref": "ak:blob:sha256:...",
  "encrypted": true,
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "ak:event:Af-qizSfVETcKiliXG093VVneO4nQF194ZXGkMWJijix"
  },
  "nonce": "base64url...",
  "size_bytes": 1234,
  "media_type": "image/png",
  "encryption_algorithm": "xchacha20_poly1305"
}
```
### 3.1 AEAD nonce uniqueness（normative）

AEAD nonce 在同一 `key_ref` 下复用会使该 key 下使用相关 nonce 的密文同时失去机密性与完整性。整文件形态使用与 [`../conformance/encoding.md` §10.1](../conformance/encoding.md) 相同的 full-width counter 编码：`nonce = I2OSP(durable_sender_counter, AEAD.Nn)`；`N_AEAD`、counter 持久化、replay 防护与 AAD binding 的唯一规范源是 encoding §10.1 / §10.2。Blob / attachment envelope 的 `purpose` 取值固定为 `"blob-attachment"`。

1. **Wire encoding**: `nonce` 字段 base64url 编码 N_AEAD 字节(XChaCha20-Poly1305 → 24 bytes;AES-GCM → 12 bytes);接收方 MUST 在解密前校验 nonce 长度匹配 AEAD algorithm 声明。

2. **AAD binding（normative）**: Blob / attachment envelope 的 AEAD AAD MUST 是 encoding [§10.2](../conformance/encoding.md) 的 **pre-encryption immutable header** 的 canonical bytes。该 header 对整文件形态 (`ak.blob.whole_file_aead.v1`) 至少绑定：

   - `scheme`、`alg`、`key_ref`（canonical 形态）、按本节唯一规则派生的 `epoch`；
   - `nonce`；
   - `purpose = "blob-attachment"`、`aead_profile`；
   - `media_type`；
   - `size_bytes`——在 `encrypted_attachment` descriptor 中它是**明文**字节数（§3.3.1 的段数只从它与 `segment_bytes` 派生），在 authority commit 之前即已确定，因此进入 AAD 不产生任何循环。它与 Blob metadata 顶层的 `size_bytes`（存储的密文字节数）是两个不同对象上的不同量，实现 MUST NOT 互相替代；descriptor 中 MUST NOT 再增加第二个明文尺寸字段；
   - 任何 profile 声明的 content policy digest（该 digest 必须在加密前已确定）。

   分块形态的逐段 AAD 见 §3.3.3。**content-addressed `blob_ref` MUST NOT 进入 AAD**：其内嵌 digest 覆盖含 AEAD tag 的完整密文，进入生成同一 tag 的 AAD 会形成不可构造循环（encoding §10.2）。它是 post-encryption commitment，MUST 由引用该附件的已签名 Event / encrypted descriptor / upload receipt 覆盖；若某条 Blob 路径没有任何外层认证，MUST 补齐该认证，MUST NOT 把 ref 或其 digest 塞回 AEAD AAD。

3. **禁止形态**: 实现 **MUST NOT** 使用以下 nonce 来源:
   - 纯随机 96-bit nonce(birthday bound 不够);
   - 全局共享 counter(协调成本 / 同步攻击面);
   - 用户输入派生(可控 = 可碰撞);
   - HMAC/Hash 输出截断后直接作为完整 nonce 的形态；
   - 任何不是 `I2OSP(durable_sender_counter, AEAD.Nn)` 的整文件 nonce 形态。

4. **整文件形态（`ak.blob.whole_file_aead.v1`）接收方校验（normative）**：整文件 envelope 只携单 `nonce` 字段。Producer MUST 以原子 CAS 耐久预留严格递增的 `durable_sender_counter`，并把整个 `AEAD.Nn` 字节 nonce 编码为 `I2OSP(counter, AEAD.Nn)`；不得为 sender domain、device 或其它信息保留高位 prefix。Receiver MUST 解码恰好 `AEAD.Nn` 字节的 nonce，以 `OS2IP(nonce)` 取得 counter，并把 `(key_ref, purpose, aead_profile, counter)` 绑定到 exact ciphertext digest。相同 tuple 的相同密文折叠；相同 tuple 的不同密文 MUST 以 `failed_precondition`（`aead_nonce_counter_replay`）fail closed。高位字节不是任意 padding：任何不等于该 counter 的 canonical full-width `I2OSP` 编码、counter 回退／复用、counter 耗尽后的继续发送或 random fallback 都 MUST 拒绝（reason `aead_nonce_derivation_invalid`）。

E2EE 附件 metadata MUST 使用 [`blob.schema.json#/$defs/encrypted_attachment`](../../artifacts/schemas/blob.schema.json) 的 wire 形态。Producer 必须提供由 stored ciphertext bytes 派生的 content-addressed `blob_ref`，不得再提供 sibling `ciphertext_digest` 或明文 hash；若 deployment 出于审计需要保留 plaintext commitment，必须使用每事件随机 salt 的 commitment 或服务持有的 HMAC / pepper commitment，边界见 [`encryption-and-audit.md` §2.3](./encryption-and-audit.md)。

### 3.2 形态选择：整文件 AEAD 与分块流式 AEAD

加密附件 envelope 通过 `scheme` 字段声明密文构造形态，v1 定义两种**并存**的合法形态：

| `scheme` | 形态 | 适用 |
| --- | --- | --- |
| `ak.blob.whole_file_aead.v1` | 整文件单次 AEAD：单 `nonce`；整体密文 digest 由 content-addressed `blob_ref` 内嵌承诺，校验通过后才释放明文。 | 默认形态；小文件、缩略图。 |
| `ak.blob.stream_aead.v1` | 分块流式 AEAD（STREAM / OAE2）：明文切成固定大小 segment，每段独立 AEAD 加密，可边下边验、内存有界。 | 大文件、流式播放、跨设备传输。见 §3.3。 |

- envelope **MUST** 携带 `scheme` 字段。未携带 `scheme` 字段时的 missing-field default 为 `ak.blob.whole_file_aead.v1`（整文件形态）。
- 发送方 **MAY** 对任意附件选用 `ak.blob.stream_aead.v1`；大文件 **SHOULD** 选用分块形态（见 [`models/file-transfer.md`](../models/file-transfer.md)）。
- 接收方 **MUST** 按 envelope 的 `scheme` 字段分派解密路径；遇到未知 `scheme` MUST fail closed（`unsupported_attachment_scheme`），不得回退到任何其它形态尝试解密。
- **`ak.content.long_text` 例外（normative）**：[`../models/content-types.md` §4.1.1](../models/content-types.md) 的 E2EE 长文本正文 **MUST** 使用 `ak.blob.stream_aead.v1` 与对应的 `_stream` 算法，MUST NOT 使用整文件形态；其 `blob_ref` MUST 是 content-addressed（`ak:blob:(sha256|blake3):<64 hex>`），且内嵌 digest MUST 等于完整 stored ciphertext bytes 的 digest。attachment 不再携 sibling `ciphertext_digest`；独立 Blob metadata 的 `content_digest` 必须与 ref 内嵌值一致。plaintext 长文本的 `blob_ref` 同样承诺完整规范化正文字节；`blob_id` 不得用于该 Content Block。强制 streaming 是为了让超过 256 KiB 的正文能边下边验且内存有界，不是同一语义的第二种可选形态。
- 两种形态的 envelope 都 MUST 满足 §3.1 的 AEAD nonce 纪律；分块形态的 nonce 兼容关系见 §3.3.2。

### 3.3 Streaming Chunked AEAD（`ak.blob.stream_aead.v1`，normative）

本节的 `key_ref`、MLS epoch 派生与 §3.3.3 AAD 字段表属于 `encrypted_attachment` 合同。holder-private
file-transfer 复用本节的段长、段数、nonce、末段与密文拼接算法；它不携 MLS `key_ref`，fresh content key 与
逐段 AAD 的唯一合同在 [file-transfer.md §4](../models/file-transfer.md#4-加密与-key-delivery)。两种上下文不得
混用 AAD，也不得为了套用 attachment 模型给 file-transfer record 添加未登记字段。

本节定义分块流式 AEAD scheme。其构造采用业界已生产化的 STREAM（OAE2，online authenticated encryption）形态，使接收方能在收到每个 segment 时增量验证并安全释放对应明文段，同时保留顶层单值整体完整性语义。

#### 3.3.1 Segment 切分

- 明文按 `segment_bytes` 字节切成有序 segment 序列；除最后一段外每段长度 MUST 恰为 `segment_bytes`，最后一段长度 MUST 在 `1 .. segment_bytes` 区间（空明文按单个长度为 0 的末段处理，且该段仍携带末段 flag）。
- `segment_bytes` MUST 在 envelope 中显式声明，单位为字节。v1 默认值为 `262144`（256 KiB）。取值范围与派生段数上限见 [`conformance/scalability-constraints.md`](../conformance/scalability-constraints.md) §6。
- verifier MUST 令 `N = max(1, ceil(size_bytes / segment_bytes))`。`N` 是本地派生值，envelope MUST NOT 携带 `segment_count` 镜像字段。
- segment_index 从 `0` 开始连续单调递增，无空洞；第 `N - 1` 段是末段。

#### 3.3.2 Segment nonce 构造与 §3.1 兼容关系（normative）

每个 segment 独立用同一 content key 做 AEAD 加密，但使用各自的 nonce。segment nonce 构造为：

```text
nonce = nonce_prefix || u32_be(segment_index) || last_segment_flag

其中：
  nonce_prefix       长度 = N_AEAD - 5 字节（per-object 随机，单调性由后缀保证）
  u32_be(segment_index)  4 字节 unsigned big-endian segment 序号
  last_segment_flag  1 字节：0x00 普通段 / 0x01 末段
```

`N_AEAD` 取值见 [`../conformance/encoding.md` §10.1](../conformance/encoding.md)（XChaCha20-Poly1305 → 24，因此 `nonce_prefix` 为 19 字节；AES-GCM → 12，`nonce_prefix` 为 7 字节）。

- `nonce_prefix` MUST per-object 随机生成（至少 `N_AEAD - 5` 字节 CSPRNG 输出），并在 envelope 中以 base64url 编码携带（字段 `nonce_prefix`）。同一 content key 下不同 object MUST 使用不同 `nonce_prefix`。
- 与 §3.1 整文件形态的兼容关系：§3.1 的 nonce 是整个 `AEAD.Nn` 字节宽度上的 `I2OSP(durable_sender_counter, AEAD.Nn)`，没有 sender prefix。本 scheme 使用 per-object 随机 `nonce_prefix` 加单调 segment 后缀；每个 transfer 又使用 fresh content key（content key MUST NOT 跨 transfer 复用，见 §3.3.4），因此 `(content key, nonce)` 对在全局唯一。两种 scheme 的 nonce 构造由 `scheme` 封闭分派，接收方不得把 stream prefix 规则套用到 whole-file nonce，也不得把 whole-file full-width counter 规则套用到 stream segment nonce。
- 因 `segment_index` 为 `u32`，单 object 的 segment 数硬上界为 `2^32`；v1 实际派生段数上限远低于此（见 scalability-constraints §6），二者 MUST 同时满足。

#### 3.3.3 AAD binding（normative）

每个 segment 的 AEAD AAD MUST 绑定以下 canonical 形态，使任一 segment 密文不能被挪用到其它 object、其它位置或另一末段判定：

- `scheme = "ak.blob.stream_aead.v1"`
- `key_ref`（canonical 形态，见 §3）
- `nonce_prefix`（本 object 的随机前缀）
- `segment_index`
- `last_segment_flag`
- `segment_count = N`（从已认证的 `size_bytes` 与 `segment_bytes` 重算，只存在于 AAD，不是 envelope 字段）
- §3.1 第 2 条要求的 envelope 绑定项：`media_type`、`size_bytes` 与任何 profile 声明的 content policy digest

`segment_index`、`last_segment_flag` 已进入 nonce，本节要求其同时进入 AAD，使重排、截断与末段伪造在 AEAD 层即被拒绝（tag 校验失败）。

上述字段全部在 AEAD authority commit 前确定，构成 encoding [§10.2](../conformance/encoding.md) 意义上的 pre-encryption immutable header。**逐段 AAD MUST NOT 包含 `blob_ref` 或其内嵌 digest**（§3.3.5 的整体 digest 覆盖每段的 tag，进入 AAD 会形成循环）、也 MUST NOT 包含任何其它 post-encryption 值。整体 commitment 的认证归属见 §3.1 第 2 条与 §3.3.5。

#### 3.3.4 Content key 与 thumbnail

- 每个附件 object MUST 使用 fresh content key；content key MUST NOT 跨 object / 跨 transfer 复用。key 派生与 key_ref 形态沿用 §3 与 [`encryption-and-audit.md` §2.3](./encryption-and-audit.md)。
- thumbnail 在分块形态下仍走 §4 / §5.3 的**整文件形态**：缩略图通常远小于 `segment_bytes`，无需分块；其独立 AEAD key / nonce context（`purpose="thumbnail"`、独立 key derivation / AAD，不复用正文 key+nonce）规则不变（见 §5.3）。即正文密文使用 `ak.blob.stream_aead.v1` 时，其缩略图附件 envelope 仍 SHOULD 使用 `ak.blob.whole_file_aead.v1`。

#### 3.3.5 `blob_ref` 内嵌 digest（分块形态语义，normative）

为保持与整文件形态一致的**单值整体完整性**语义：

- `blob_ref=ak:blob:<suite>:<hex>` 的 `<suite>:<hex>` = 对全部 segment 密文（每段含其各自 AEAD tag）按 segment_index 升序拼接后的完整字节流，用 Realm digest suite（见 [`../conformance/encoding.md` §3.2](../conformance/encoding.md)）求得。
- 拼接顺序 MUST 严格按 segment_index 升序，且覆盖恰好派生的 `N` 段、不含其它字节。
- 语义分层：per-segment AEAD tag 提供**增量**校验（边下边验），content-addressed `blob_ref` 提供**整体**完整性（防止整体替换 / 段集合层面的攻击）。两者都 MUST 校验通过。
- **认证归属（normative）**：`blob_ref` 是 post-encryption commitment，MUST NOT 出现在任何 segment 的 AEAD AAD 中（encoding [§10.2](../conformance/encoding.md)）。它自身的真实性由引用该附件的已签名 Event / encrypted descriptor（例如 `ak.content.file` / `ak.content.long_text` 的 attachment、file-transfer record）或 upload receipt 承担；接收方 MUST 以外层已认证值为准，MUST NOT 采信仅由传输层提供的 digest。

#### 3.3.6 解密 MUST（normative）

接收方解密 `ak.blob.stream_aead.v1` 附件时：

1. **按序处理**：MUST 按 segment_index 从 `0` 起严格升序处理 segment；segment_index 跳变、乱序、出现空洞 MUST 拒绝（`segment_sequence_invalid`），并丢弃已缓冲明文。
2. **逐段 AEAD 校验**：每段 MUST 用 §3.3.2 的 nonce 与 §3.3.3 的 AAD 做 AEAD 解密；tag 校验失败 MUST 拒绝（`segment_aead_failed`）。在第 N 段 AEAD 校验通过前，MUST NOT 释放第 N 段明文。
3. **末段判定**：MUST 仅在见到 `last_segment_flag = 0x01` 的合法末段（且其 `segment_index == N - 1`）并通过 AEAD 校验后，才认为附件完整。在见到合法末段前，接收方 MUST NOT 把附件视为已完整接收。
4. **缺末段拒绝**：流在未出现合法末段时即终止（连接中断，或派生的 `N` 段已耗尽但末段 flag 仍为 `0x00`）MUST 拒绝（`segment_stream_truncated`），并丢弃已释放/缓冲明文，不得把已得明文当作完整文件。
5. **重复拒绝**：同一 segment_index 出现多次 MUST 拒绝（`segment_replay`）。
6. **越界拒绝**：`segment_index >= N`、或非末段长度不等于 `segment_bytes`、或末段长度超出 `1 .. segment_bytes`（空明文 0 例外）MUST 拒绝（`segment_bounds_invalid`）。
7. **整体 digest 校验**：全部 segment 接收完毕后，MUST 按 §3.3.5 重算拼接密文 digest 并与 `blob_ref` 内嵌值比对；不匹配 MUST 拒绝、丢弃全部明文、不得渲染或写入持久缓存（与 §5 digest mismatch 规则一致）。Range / 分段流式播放场景下允许在整体 digest 完成前消费已通过 per-segment 校验的明文段，但**最终持久化或标记完整**前 MUST 完成整体 digest 校验。

任一上述校验失败 MUST fail closed，按 §5 规则丢弃已下载字节、不得渲染、不得写入持久缓存，并 SHOULD 记录安全审计事件。

#### 3.3.7 JSON 示例

```json fragment
{
  "blob_ref": "ak:blob:sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "encrypted": true,
  "scheme": "ak.blob.stream_aead.v1",
  "key_ref": {
    "algorithm": "MLS",
    "group_state_ref": "ak:event:Af-qizSfVETcKiliXG093VVneO4nQF194ZXGkMWJijix"
  },
  "nonce_prefix": "base64url-N_AEAD-minus-5-bytes",
  "segment_bytes": 262144,
  "size_bytes": 3211264,
  "media_type": "video/mp4",
  "encryption_algorithm": "mls_exporter_aead_xchacha20poly1305_stream"
}
```
整文件形态（`ak.blob.whole_file_aead.v1`）的 envelope 仍按 §3 示例（携带单 `nonce` 而非 `nonce_prefix` / `segment_*`）。

## 4. Thumbnail

Thumbnail descriptor:

```json fragment
{
  "source_blob_ref": "ak:blob:sha256:...",
  "thumbnail_blob_ref": "ak:blob:sha256:...",
  "width": 320,
  "height": 180,
  "media_type": "image/webp"
}
```
## 5. Authenticated Download

```text
GET /_arkret/self/blob/get?blob_ref=<ref>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `blob_ref` | query | `string` | required | 内容寻址 blob 引用。 |
| `Authorization` | header | `bearer token` 或 `device proof` | 私有 blob required | 调用者认证。 |
| `Range` | header | `string` | optional | Range 下载范围。 |
| `X-Arkret-Wait-For` | header | `cursor` | optional | barrier cursor（`purpose=barrier`）；服务端在 checkpoint 覆盖该 cursor 描述的 target event 前阻塞响应。 |

响应字段 / header：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| body | response | `bytes` | GET required | blob 字节内容。 |
| `Content-Length` | header | `int` | optional | 可见时返回内容长度。 |
| `Digest` | header | `string` | optional | 内容摘要。 |
| `Cache-Control` | header | `string` | required | 缓存策略；私有内容必须保守。 |
| `Content-Type` | header | `string` | 可见时 required | MIME 类型；不得泄露不可见资源。 |
| `Content-Disposition` | header | `string` | 可见时 required | `inline` 或 `attachment`，并可携带安全清理后的 `filename`。 |
| `Content-Range` | header | `string` | Range 响应 required | 实际返回字节范围。 |
| `Accept-Ranges` | header | `string` | optional | 服务支持 Range 时 MAY 返回 `bytes`。 |
| `Location` | header | `url` | redirect 时 required | 短期下载 URL 或对象存储 URL。 |

服务 MUST check:

- actor authorization
- Realm / Circle scope visibility
- retention / legal hold
- unsafe media policy

Retention 与 erasure 规则：

- Blob 删除 MUST 由 Realm policy、对象所有权、account lifecycle、retention expiry 或签名 compliance decision 授权。
- 处于 legal hold 的 blob MUST NOT 被物理删除；服务可以通过 redaction 或 policy 在普通视图中隐藏。
- Blob 被擦除后，服务 SHOULD 只保留最小 receipt：content-addressed `blob_ref`（包含唯一 digest commitment）、策略允许时的 size class、erasure reason、执行服务 DID、执行时间和签名；不得再携同原像 sibling digest。
- 缩略图、preview、转码、搜索文本、embedding 和通知摘要等派生内容 MUST 在源 blob 或源 event 被 redacted / erased 后删除或重新最小化。
- E2EE 附件密钥销毁只能阻止后续访问，不能撤回已被授权接收方下载或解密的明文。

受保护内容默认必须走 authenticated download。公开 blob MAY 允许匿名读取，但私有 Realm、受控组织、E2EE 附件和任何带访问策略的媒体 MUST 要求认证。

下载请求 SHOULD 支持：

```text
Authorization: DPoP <ak.session.grant>
X-Arkret-Wait-For: <cursor>
Range: bytes=<start>-<end>
```

规则：

- `X-Arkret-Wait-For` 接受 [`cursor.schema.json`](../../artifacts/schemas/cursor.schema.json) 的 `purpose=barrier` cursor，用于避免客户端刚收到引用但 Blob 服务尚未完成授权物化。Blob 服务 SHOULD 等待本地授权 checkpoint 覆盖该 cursor 描述的 target event，超时返回 `revision_stale` 或 `temporarily_unavailable`。
- 下载授权 MUST 绑定 actor DID、device/session、Realm id、blob ref、purpose 和过期时间。服务端不得只凭 URL 随机串放行私有媒体。
- 受保护下载 MUST NOT 接受 query string 中的 session credential 或长期 capability。浏览器客户端应通过 `Authorization` header、service worker 代理或 device-bound proof 获取媒体。
- Blob 服务 MAY 返回短期 signed download URL 或 `307/308` redirect 到对象存储，但 redirect token MUST 短时效、单 blob、单 purpose、可撤销，并不得扩大可见性。
- `Location` 值不得被服务端或客户端长期缓存；未立即下载时 SHOULD 重新请求 `/_arkret/self/blob/get` 获取新的授权上下文。
- 客户端跟随 redirect 后仍 MUST 重新计算内容 digest，并与 content-addressed `blob_ref` 内嵌值比对；若同时读取独立 Blob metadata，其 `content_digest` 也必须相等。
- 如果内容 hash、`Digest` header 或 `blob_ref` 不匹配，客户端 MUST 拒绝该响应、丢弃已下载字节、不得渲染、不得写入持久缓存，并 SHOULD 记录安全审计事件。服务端在上传、镜像或代理时发现 digest mismatch MUST 返回 `digest_mismatch`，并不得生成可用 blob metadata。
- Range / HEAD download MUST 绑定同一授权上下文；服务端不得让 Range probe 或 HEAD response 泄露不可见 blob 的大小、MIME、文件名或存在性。
- 对采用 `ak.blob.stream_aead.v1`（§3.3）的加密附件，Range 下载的语义从"密文任意字节分片"升级为"可独立验证的明文分段"：客户端 SHOULD 按 segment 边界（`segment_bytes` 的整数倍偏移）请求 Range，使每个取回的 segment 能立即用 per-segment AEAD tag 增量校验并安全释放对应明文，无需先下完整文件。客户端仍 MUST 按 §3.3.6 完成按序、末段与 `blob_ref` 内嵌整体 digest 校验后才认为附件完整；服务端对密文字节本身的 Range 语义不变（仍以 `Content-Range` 描述密文字节区间）。
- 对不可见 blob，服务端 SHOULD 返回与不存在资源一致的 `not_found`，并避免返回 `Content-Length`、`Content-Type`、`Content-Disposition`、`Accept-Ranges` 等可枚举 header。

### 5.1 Content-Type 与 Content-Disposition

下载或 HEAD 响应在资源对调用方可见时 MUST 返回 `Content-Type`。返回值 SHOULD 是上传 metadata 中的 `media_type`，但允许以下安全校正：

- 对 `text/*` 添加 charset。
- 对未知或未提供 MIME 返回 `application/octet-stream`。
- 当服务端判定声明 MIME 明显错误或危险时，返回 `application/octet-stream`。

下载或缩略图响应在资源可见时 MUST 返回 `Content-Disposition`：

- 原始下载 MUST 使用 `inline` 或 `attachment`。
- 缩略图 SHOULD 使用 `inline`，并 MAY 使用服务生成文件名。
- 如果存在安全清理后的 `filename`，`Content-Disposition` SHOULD 携带它；否则不携带文件名。
- 服务端 SHOULD 仅对安全类型使用 `inline`，其他类型使用 `attachment`。

建议允许 `inline` 的类型：

```text
text/css
text/plain
text/csv
application/json
application/ld+json
image/jpeg
image/gif
image/png
image/apng
image/webp
image/avif
video/mp4
video/webm
video/ogg
video/quicktime
audio/mp4
audio/webm
audio/aac
audio/mpeg
audio/ogg
audio/wave
audio/wav
audio/x-wav
audio/x-pn-wav
audio/flac
audio/x-flac
```

`text/html`、`text/javascript`、`image/svg+xml` 和未知脚本型内容不得默认 `inline`。

### 5.2 缓存

私有或受控 blob response MUST 设置保守缓存头：

```text
Cache-Control: private, no-store
```

如果服务明确允许客户端缓存，MAY 使用 `private, max-age=<n>`，但 MUST 绑定用户 / device 授权，不得被共享代理缓存。

公开不可变 blob MAY 使用长缓存：

```text
Cache-Control: public, immutable, max-age=31536000
```

前提是内容地址包含强 hash，且 metadata 不泄露私有 Realm 信息。

### 5.3 缩略图与预览

缩略图、OCR 文本、转码副本、媒体探测 metadata 都是派生内容：

- E2EE 附件的缩略图 SHOULD 由客户端生成并加密上传，或只在本地生成。
- 服务端生成私有明文缩略图前，该服务 MUST 列入 `plaintext_visible_services`，且 `data_classes[]` 覆盖 `thumbnail` / `attachment_preview`。
- 预览 URL、尺寸、MIME、文件名和 unsafe 标记都必须服从 Realm policy 与 capability，不能绕过正文授权。
- 缩略图必须重新绑定源 blob、生成参数、生成服务 DID 和可见性；删除、撤回、保留策略或 legal hold 改变时，派生内容必须随源内容重新判定。
- 缩略图 descriptor MUST 至少绑定 content-addressed `source_blob_ref`、`thumbnail_blob_ref`、`width`、`height`、`media_type`、`generated_by?`、`visibility` 和 `derivation_profile`；两项 ref 的内嵌 digest 分别是 exact stored bytes 的唯一承诺，descriptor 不携 `source_ciphertext_digest` / `thumbnail_ciphertext_digest`。若源附件是 E2EE，缩略图必须使用独立 AEAD key / nonce context，推荐 `purpose="thumbnail"` 并把两项 ref、尺寸和生成参数纳入 key derivation / AAD；不得复用原附件正文 key+nonce，也不得把明文缩略图 hash 暴露给未获授权服务。
- producer SHOULD 使用 `thumbnails[]` 数组表达上述绑定。Consumer 收到只含 `media-metadata.schema.json` 的 `preview_blob_ref`、缺少 `thumbnails[]` descriptor 的 metadata 时，必须按源 blob 的最严格可见性处理，不得因缺少 descriptor 而放宽访问或缓存。

`media-metadata.visibility` 的标准取值是 `public` / `realm_bound` / `actor_private` / `device_bound`。`realm_bound` 表示访问受 owning Realm、Circle scope 与 capability 共同约束；它不是 Space 边界。`actor_private` 表示仅 issuing actor 的授权会话可通过 header auth 获取，MUST NOT 被转换为 bearer presign URL。`presign` 是 §5.4 定义的**下载通道机制**（发放短 TTL bearer URL），不是 visibility 维度上的取值；blob 的 visibility 仍按上述四值之一判定，是否允许 presign 由 §5.4.4.1 的 fail-closed 规则按 visibility 与 Realm policy 决定（例如 `actor_private` MUST NOT 走 presign）。`presigned` 不是合法 visibility 枚举值。

### 5.4 Pre-Signed URL（浏览器原生标签认证例外）

§5 与 [`server-threat-model.md` §2.1 #21 URL 凭证泄露](../security/server-threat-model.md) 规定受保护下载 MUST NOT 接受 query string 中的认证材料。该规则的存在原因是 query string 会被 HTTP access log、代理、CDN、浏览器历史、复制链接和 `Referer` 头无差别记录，长期 capability 一旦落入 URL 即等价于失控。

然而浏览器原生媒体标签（`<img src>`、`<video src>`、`<audio src>`、`<link href>`、CSS `background-image: url(...)` 等）**无法附加 `Authorization` header**——浏览器在解析这些属性时直接对目标 URL 发起未带认证 header 的 GET。`fetch()` API 本身可以附加 `Authorization`，但其返回的 `Response` 仅能转换为 Blob URL 后由 JS 注入 DOM 才能让原生标签消费，无法直接代替原生 src 的同源加载语义。若严格执行"无 URL 认证"规则，受保护媒体只能通过 service worker 代理或 JS Blob URL 间接渲染——这在很多原生体验、邮件预览、跨页面共享场景中是死路。

为此 v1 定义 **`ak.self.blob.command.presign.v1`** 作为该规则的**狭窄定制例外**：发出短 TTL、单对象、只读、可撤销的 pre-signed URL，让浏览器原生标签直接使用，同时通过严格 access_scope 限制把 URL 泄露的最大损失收敛在一个具体 blob 的短时间访问。

#### 5.4.1 流程

```text
1. 客户端 → POST /_arkret/self/blob/presign
   body: { blob_ref, max_age_seconds?, purpose? }
   auth: Authorization (standard bearer / service signature)

2. 服务端 (ak.self.blob.command.presign.v1 capability 通过后):
   - 生成 presign envelope (见 §5.4.2)
   - 用 blob service DID 签名
   - 返回 url、expires_at

3. 浏览器 / 客户端:
   <img src="<url with embedded presign=...>" />
   → GET /_arkret/self/blob/get?blob_ref=...&presign=...
   → 服务端验证 presign envelope 后吐 bytes
```

#### 5.4.2 Presign envelope wire 形态

`presign` query 参数的值是 base64url 编码的 detached-JWS envelope，覆盖 canonical JSON：

```json fragment
{
  "scheme": "ak.blob.presign.v1",
  "blob_ref": "ak:blob:sha256:0123456789abcdef...",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "issuer_id": "ak:did_core:webvh:z9L9sKcFqigzdgN2ucF1V6ztq",
  "issued_at": "2026-05-18T10:00:00Z",
  "expires_at": "2026-05-18T10:05:00Z",
  "purpose": "media_inline",
  "audience_hint": "did:webvh:z2dmj...:alice.example",
  "nonce": "base64url:random_16_bytes",
  "access_scope": {
    "method": ["GET", "HEAD"],
    "byte_range": null
  }
}
```
字段约束：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `scheme` | yes | 固定 `ak.blob.presign.v1`；未来版本 MUST 用新 scheme id（不接受 in-space 升级） |
| `blob_ref` | yes | 单一 blob 引用；与请求 `?blob_ref=` 必须完全匹配 |
| `realm_id` | conditional | 该 presign 授权的 Realm。普通 Realm-owned blob MUST 设置，且必须与 blob metadata 的 `realm_id`、签发时 capability scope 和响应时可见性检查一致。仅 deployment policy 明确声明的 public/global blob MAY 省略。 |
| `issuer_id` | yes | 签发该 presign 的 blob service DID；MUST 是被部署 trust 的 service DID |
| `issued_at` / `expires_at` | yes | TTL 硬上限 1h；deployment SHOULD 默认 ≤ 5 min |
| `purpose` | yes | `media_inline` / `thumbnail` / `download`；服务端按 purpose 决定 `Content-Disposition`、限流强度等 |
| `audience_hint` | optional | 期望使用者 DID（**仅诊断 hint，不构成访问控制**；浏览器原生标签无法证明调用者身份，详见 §5.4.4.1）。（注意：`audience_hint` 仅为路由/下载体验提示，**不构成授权，也不是密码学意义上的 audience 绑定**。） |
| `nonce` | yes | 16+ bytes 随机；作为 presign envelope id、audit key 与撤销列表 key。除非显式声明 single-use profile，服务端不得因同一 nonce 被浏览器重复 GET / HEAD / Range 拉取而拒绝正常媒体加载。 |
| `access_scope.method` | yes | 仅允许 `GET` / `HEAD` 中的子集；MUST NOT 包含写方法 |
| `access_scope.byte_range` | optional | 可限制可访问字节区间（如 `[0, 65536]` 仅头部） |

#### 5.4.3 接收方校验

`GET /_arkret/self/blob/get?blob_ref=X&presign=<envelope>` 处理时：

1. **互斥检查**：`Authorization` header 与 `?presign=` 同时出现 MUST 拒绝 `param_invalid`，避免混合 auth 模式
2. **签名校验**：用 envelope 内 `issuer_id` 当前 verification method 验证签名
3. **scheme 校验**：仅识别注册 scheme id（v1 = `ak.blob.presign.v1`）；未知 scheme MUST 拒绝
4. **blob_ref 一致性**：envelope `blob_ref` 与 query `blob_ref` 必须完全相同
5. **Realm 绑定校验**：若 blob metadata 有 `realm_id`，envelope `realm_id` MUST 存在且完全相同；若 envelope 省略 `realm_id`，该 blob **MUST** 是 deployment public/global 白名单中**显式登记**的 blob。服务端 **MUST NOT** 仅因 blob metadata 缺 `realm_id` 即推断其为 public/global——"缺失 `realm_id`"与"已授权公开"必须解耦：未显式登记在白名单的 realm-less blob（例如因上传 bug 漏设 `realm_id` 的 Realm-owned blob）MUST fail closed（`not_found`），不得为其签发无 Realm 绑定的 bearer URL。为 Realm A 签发的 presign 不能作为 Realm B 的授权使用。
6. **method 校验**：本次请求方法在 envelope `access_scope.method` 列表内
7. **TTL 校验**：接收方 MUST 按 [`contract-registry.json#protocol_time_tolerance_registry`](../../artifacts/registry/contract-registry.json) 的 `ak.time_tolerance.blob_presign_ttl.v1` 校验 `issued_at` 与 `expires_at`：未来 `issued_at` 和过去 `expires_at` 各自只获得该场景登记的短窗口宽限，边界包含在可接受区间内。实现 MUST NOT 换用 approval／temporal 场景的容差或方向，也 MUST NOT 自定义更宽容差使过期 presign 在无界时间内被接受。
8. **nonce / 撤销校验**：`nonce` 未在撤销列表内；普通 `media_inline` / `thumbnail` presign 是短 TTL 多次可用 bearer URL，服务端 MUST NOT 把浏览器正常的重复 GET / HEAD / Range 请求当作 replay 拒绝。只有 profile 显式声明 single-use presign 时，才可维护 consumed set。
9. **撤销 / 状态实时回查（normative）**：服务端在每次 presign GET / HEAD / Range 响应阶段 MUST 同步回查该 `blob_ref` 的**当前** redaction / erasure / ban / legal-hold 状态,**不得仅凭 envelope 自校验(签名 + TTL + scope)就放行**。只要当前状态命中 redaction / erasure / ban / legal hold,即便 envelope 仍在 TTL 内且签名有效，也 MUST 拒绝(`not_found`,audit `blob_redacted` / `legal_hold_active`)。该回查 MUST 在响应 bytes 之前完成，以闭合"签发后被 redact 的内容在 TTL 窗口内仍被已泄露 URL 拉取"的竞态(见 §5.4.4 撤销索引保留下界与 §5.4.4.1 fail-closed 规则)。

   **一致性边界（normative）**：本回查**不要求**每次都向远端撤销权威发起网络往返。参考实现 MAY 命中 §5.4.4 保留到 `expires_at` 的**本地撤销 / 失效索引**做 O(1) 查询，因此本步骤的常态成本是本地命中而非每次远程查。允许的 staleness 上界按状态类别分级：

   - 普通 redaction / erasure / ban 命中：MAY 采用**有界 staleness**——本地撤销索引相对撤销权威的滞后 MUST ≤ 部署显式声明的 `revocation_index_propagation_max_ms`；该部署参数不是协议时钟容差，不得从 `ak.time_tolerance.blob_presign_ttl.v1` 或其它场景隐式继承。在该窗口内本地索引尚未收到的撤销可短暂未命中，但 presign TTL（≤ 1h）与撤销索引保留下界共同把暴露面收敛在有界窗口内。
   - **legal-hold / erasure（强一致 MUST）**：legal hold 与硬擦除命中 MUST 强一致——服务端 MUST NOT 用可能滞后的缓存放行：本地索引未能确认"无 legal hold / 未 erased"时 MUST fail closed（`not_found` / `legal_hold_active`），不得在 staleness 窗口内放行受 legal hold 约束的内容。

   实现不得以"性能"为由把 legal-hold / erasure 降级为有界 staleness，也不得对普通 redaction 引入无界 staleness 使已 redact 内容在 presign 整个 TTL 内持续可取。
10. **blob 状态与签发者校验**：签发时服务端 MUST 已确认请求方有权为该 `blob_ref` mint presign；响应时只能重新确认 envelope 绑定的 Realm / blob 仍一致、blob 未被 redacted / erased / banned / legal hold、issuer service DID 仍被部署信任。v1 bearer presign 无法在响应阶段证明当前请求者属于某个 audience。
11. **Realm presign 资格实时重判（normative）**：服务端在响应阶段 MUST 重判该 `blob_ref` 所属 Realm 当前是否已收紧为 routing-unlinkable（Realm asset policy 声明 `routing_unlinkability_required=true`），并重判 `ak.realm.asset_privacy_policy`（§6）是否仍**显式**声明 `direct_download_allowed=true`。routing unlinkability 命中，或 asset policy 缺失、不可验证、未进入 effective policy bundle 的 `components`、字段缺失、字段为 false 时，MUST 拒绝（`not_found`，audit `routing_unlinkability_presign_forbidden` / `direct_download_disallowed_presign_forbidden`），不得仅凭签发时该 Realm 尚未收紧或曾允许 direct download 就放行。这闭合"签发时允许、签发后 policy 收紧/移除、已发 presign 仍在 TTL 内被拉取"的竞态，与 §5.4.4.1 签发侧的同名禁令构成两侧闭合。

任何校验失败 MUST 返回 `not_found`（不区分 envelope 无效 vs blob 不可见，避免暴露存在性）；服务端 MAY 在 audit log 中记录具体 `reason_code` 如 `presign_invalid` / `presign_expired` / `presign_scope_mismatch`。

#### 5.4.4 安全约束

**MUST**：

- TTL ≤ 1h（硬上限）；deployment policy MAY 收紧到更短
- 单 blob，不接受通配
- 仅读（GET / HEAD），不接受 PUT / POST / DELETE
- envelope 不得包含可重用 credential（refresh token、session token、long-lived capability 等）
- envelope 由 blob service DID 签发，**不能**由 user device key 签发——这是 server-issued capability，不是 user delegation
- 已 revoked / redacted / erased blob 即使 envelope 仍有效 MUST 拒绝
- presign nonce 撤销 / 失效索引 MUST 至少保留到该 envelope 的 `expires_at`。普通 `media_inline` / `thumbnail` presign 在短 TTL 内多次可用（§5.4.3 步骤 8），其撤销条目若在 `expires_at` 前被清理，§5.4.4.1 对已签发但 TTL 未到的 presign 的即时拒绝（如 redacted blob）就会失效；因此撤销索引的保留下界 MUST 覆盖 envelope 的整个有效期。
- presign URL 不得通过普通 redirect / 反向代理透传到第三方 origin

**MUST NOT**：

- 用于 E2EE 附件 ciphertext fetch — E2EE 附件的 `blob_ref` + decryption key 都 MUST NOT 出现在服务端可记录的 URL；E2EE 客户端坚持 header auth 路径，由 client-side `fetch()` 配合 `Authorization` 完成
- 用于 `ak.self.blob.upload.create.v1`、删除、mutation 或任何写/副作用操作；presign 只对 envelope 明确授权的 `ak.self.blob.resource.get.v1` / `ak.self.blob.resource.head.v1` 只读路径有效
- 由 user device 凭 capability 自签自用（必须经过 `ak.self.blob.command.presign.v1` operation 走一次服务端签发，进 audit log 与 capability check）

**SHOULD**：

- deployment 对 presign 签发频率限流（按 issuer service DID + 请求方 actor），防止滥用作为隐蔽 oracle
- audit log 记录每次签发（actor、blob_ref、purpose、TTL、issuer）以便事后追溯
- 客户端 SHOULD 优先用 header auth；仅在浏览器原生标签场景使用 presign

#### 5.4.4.1 `audience_hint` 与 bearer-token 边界（normative）

`audience_hint` 是 **诊断 hint**，**不是访问控制**。原因：浏览器原生标签（`<img>` / `<video>`）在加载 presign URL 时不会附加任何调用者凭据；服务端无法在响应阶段验证当前请求确实来自 `audience_hint` 指向的 actor。任何把 `audience_hint` 当作 audience 强制的实现都会形成假阳性安全感。本节固定如下规则：

- **实现 MUST NOT** 把 `audience_hint` 当成访问控制 — 它只能进入 audit log 用于事后排查"presign 给谁发的"。
- presign 是一个**短 TTL bearer URL**：任何持有该 URL 的人在 TTL 内都可拉取 `blob_ref` 对应字节。最大损失窗口由 (a) TTL、(b) `access_scope.method`/`access_scope.byte_range`、(c) revocation（redaction / erasure 触发即时拒绝）三者共同收敛。
- `nonce` 不提供普通媒体 presign 的单次消费语义。浏览器原生标签可能对同一 URL 执行 `HEAD` + `GET`、Range、retry 或解码器重复拉取；v1 `media_inline` / `thumbnail` presign MUST 允许这些重复请求。需要单次下载时必须声明独立 profile（例如 `single_use=true` 或专用 purpose），且不得用于原生媒体标签。
- **下列 blob 类别 MUST 走 fail-closed 规则，不得发 presign**：
  - **E2EE ciphertext** — 已经在 §5.4.4 MUST NOT 列出。E2EE 附件 fetch 走 client-side `fetch()` + `Authorization` header 路径。
  - **legal hold blob** — 处于 legal hold 状态的 blob MUST 拒绝 `ak.self.blob.command.presign.v1`（`legal_hold_active`），即便申请方持有 `ak.self.blob.command.presign.v1` capability。原因：legal hold 要求 access 留痕可追溯，bearer URL 让第三方无凭据拉取破坏审计链。
  - **redacted blob** — `ak.redaction` 已生效 / `ak.audit.erasure_receipt` 已发布的 blob MUST 立即拒绝 presign 请求与已签发但 TTL 未到的 presign 请求（`blob_redacted`）。
  - **private attachment 私有附件**（`visibility=actor_private` 或附 `ak.actor_private` policy 标签）— MUST NOT 走 presign 路径（`private_attachment`）。该类 blob 只允许 issuing actor 本人通过 header auth fetch。
  - **routing-unlinkable Realm-owned blob** — blob metadata 绑定的 Realm 的 asset policy 声明 `routing_unlinkability_required=true` 时，服务端 MUST NOT 签发 bearer presign URL（`routing_unlinkability_presign_forbidden`）。该类 Realm 的下载必须走 header auth、`provider_proxy`、`ohttp_relay` 或等价的不把 `blob_ref` / bearer envelope 暴露到可转发 URL 的路径。只有 deployment-public/global blob（无 Realm 绑定，且 policy 明确允许 public direct download）可继续使用 presign。
  - **未显式允许 direct download 的 Realm-owned blob** — blob metadata 绑定的 Realm 只有在当前 effective `ak.realm.asset_privacy_policy`（§6）中显式声明 `direct_download_allowed=true` 时，服务端才 MAY 继续评估 bearer presign；policy 缺失、不可验证、未进入 effective policy bundle 的 `components`、字段缺失或字段为 false，一律按 `direct_download_allowed=false` fail closed，MUST NOT 签发 bearer presign URL（`direct_download_disallowed_presign_forbidden`），即便该 Realm 未声明 `routing_unlinkability_required`、即便申请方持有 `ak.self.blob.command.presign.v1` capability。presign 产出的就是一个可转发的 bearer download URL；缺省放行会把成员限定读取权降格为“持链接即可读取”。该类 Realm 的媒体必须走 authenticated header fetch 或 `download_mode` 声明的 `provider_proxy` / `ohttp_relay` / `client_mirror` 路径。只有 effective policy 显式 `direct_download_allowed=true` 的 Realm-owned blob，以及 deployment-public/global 白名单中的 realm-less blob，才可继续评估 presign 的其余 gate。
- **最小 conformance matrix（normative）**：实现 MUST 覆盖四个 case：(a) Realm-owned blob 无 asset policy → 拒绝；(b) `direct_download_allowed=false` → 拒绝；(c) policy 已进入 effective policy bundle 的 `components` 且显式为 true → 仅在本节其它 gate 全部通过时允许；(d) URL 签发后 policy 被移除、失去 effective 引用或改为 false → 后续 GET / HEAD / Range 立即按步骤 11 拒绝。测试不得把 deployment-public/global realm-less 白名单分支当作 Realm-owned blob 的缺省回退。
- **future audience-bound 机制**（未来评估方向，不属于 v1）：若未来需要真正绑定 audience，方案有 (a) 把 presign 升级为 cookie-bound URL（依赖 `__Host-` cookie + SameSite=Strict + presign 校验 cookie binding），(b) 通过 session-bound token 把 presign 换给 client 后只在该 session 内可用。两条都需要客户端配合，不属于 v1 范围。

#### 5.4.4.2 Bearer URL 泄漏面控制（normative）

为限制 bearer URL 泄漏后的最大损失：

- 服务端 MUST 在响应 header 中加：
  - `Cache-Control: private, no-store, max-age=0`
  - `Referrer-Policy: no-referrer`
  - `X-Content-Type-Options: nosniff`
- 服务端 MUST NOT 在 access log / metrics / tracing 中记录 `?presign=` query 参数原文；记录 audit log 时 SHOULD 把 envelope hash 而不是原文写入。
- 服务端 MUST 限制 presign URL 在反向代理 / CDN 层不被缓存（`Cache-Control: private` 不够时还要 set `Vary: Authorization` 或显式 surrogate-control）。
- 客户端 MUST NOT 把 presign URL 持久化到 app state、route state、analytics、crash report、local storage、普通日志或浏览器历史中；SHOULD 仅在最终消费节点（`<img src=...>` 注入或 fetch）处构造 presign URL。

#### 5.4.5 与 capability 的衔接

`ak.self.blob.command.presign.v1` capability action（risk_tier=medium）控制谁可以**为某 blob 签发 presign**。grant 上的两个 constraint 收紧使用范围：

- `blob_presign_max_ttl_seconds`：grant 允许的最大 TTL 上限（硬上限不超过 3600）
- `blob_presign_scope`：grant 允许的 purpose 集合（`media_inline` / `thumbnail` / `download`）与可选 blob_ref pattern（按 Realm / purpose 细分）

服务端在 `ak.self.blob.command.presign.v1` 调用时按 grant constraint 收窄请求的 `max_age_seconds` / `purpose`；超过 constraint 返回 `capability_denied`。

#### 5.4.6 与 §5.2 / §5.3 的关系

- §5 仍是 **认证下载默认路径**；pre-signed 仅作为 §5 的 narrow 例外
- §5.2 redirect / `Location` 头的"短期 signed download URL"语义可以由 `ak.self.blob.command.presign.v1` 实现，但 redirect URL MUST 同样满足 §5.4 全部约束
- §5.3 缩略图通常通过 `purpose=thumbnail` presign 让 `<img>` 直接渲染；服务端 SHOULD 设更短 TTL（默认 ≤ 60s）

## 6. Asset Privacy Policy

私有附件下载本身会暴露元数据，例如调用方 IP、在线时间、服务域名关系、blob 大小和下载频率。Realm SHOULD 使用 `ak.realm.asset_privacy_policy` 声明媒体上传、下载和代理隐私要求；无论 Realm 的 discoverability、join rule、history visibility 或 encryption profile 如何，Realm-owned blob 的 bearer presign 资格都采用 fail-closed 缺省：只有 effective policy 显式 `direct_download_allowed=true` 才可签发，缺失 policy 不等于允许。

```json fragment
{
  "kind": "ak.realm.asset_privacy_policy",
  "payload": {
    "value": {
      "download_mode": "provider_proxy",
      "allowed_modes": [
        "provider_proxy",
        "ohttp_relay"
      ],
      "direct_download_allowed": false,
      "upload_services": [
        "ak:did_core:webvh:z9L9sKcFqigzdgN2ucF1V6ztq"
      ],
      "download_proxy_services": [
        "ak:did_core:webvh:zGKqLZm5euMAfKUjGMsFkXR9E"
      ],
      "ohttp_gateway_services": [
        "ak:did_core:webvh:zAQ5daUZibU8q3K1aaxD9vMRg"
      ],
      "max_plaintext_metadata": [
        "size_bucket",
        "media_type_family"
      ],
      "client_digest_check_required": true
    }
  }
}
```
该 Event 使用 closed `realm_asset_privacy_policy_payload`；策略字段只能位于 whole-value `payload.value`，未知字段以 `schema_violation` 拒绝。

`download_mode` 取值：

| 值 | 含义 |
| --- | --- |
| `direct` | 客户端直接从 Blob / 对象存储下载。只适合公开内容、同一信任域或明确接受 IP 暴露的 Realm。 |
| `provider_proxy` | 通过调用方或 Realm policy 指定的受信 media proxy 下载，隐藏源 Blob 服务或对象存储细节。 |
| `ohttp_relay` | 通过 OHTTP 或等价 oblivious relay 取回内容，降低 Blob 服务同时观察调用方身份和目标 blob 的能力。 |
| `client_mirror` | 客户端从多个 authorized mirror 选择，按内容 hash 验证，适合高可用或隔离网络。 |

规则：

- 私有 Realm、E2EE 附件和高隐私 Realm 默认 SHOULD 使用 `provider_proxy` 或 `ohttp_relay`，不得默认 direct download。对声明 `routing_unlinkability_required=true` 的 Realm-owned blob，§5.4.4.1 的 presign hard reject 优先于本节的 `download_mode=direct`；deployment 不得用 direct download policy 绕过该 bearer URL 禁令。
- `direct_download_allowed` 的 presign 缺省值是 false：只有本 policy 的 `realm_asset_privacy_policy` 安全 typed current result 在当前已确认状态中已设置且字段逐字为 true，才允许继续评估 presign。policy 缺失、未确认、不可验证或字段省略都 MUST 按 false 处理；deployment-wide “允许 direct”不得覆盖 Realm-owned blob 的该缺省。
- `direct_download_allowed=false` 时，客户端 MUST NOT 绕过代理直接访问 `Location` 或外部 URL；服务端也不得返回强制 direct 的 redirect。该约束同样禁止 bearer presign：服务端 MUST NOT 为 `direct_download_allowed=false` Realm-owned blob 签发 `ak.self.blob.command.presign.v1` URL（§5.4.4.1 `direct_download_disallowed_presign_forbidden`），因为 presign 就是一个可转发的 direct bearer URL。
- Proxy 服务不因参与下载而获得正文解密权。E2EE 附件必须保持密文，proxy 只能处理密文字节、size bucket、content hash 和授权 envelope。
- `max_plaintext_metadata` 控制服务可见 metadata。高隐私 Realm SHOULD 使用 bucketed size、MIME family，而不是精确文件名、精确字节数或完整 MIME。
- 无论采用哪种下载路径，客户端 MUST 校验内容 hash、ciphertext digest 和 E2EE attachment metadata；proxy 成功不等于内容可信。
- `ak.realm.asset_privacy_policy` 由它自己的 Event kind 写入 `realm_asset_privacy_policy` typed current result，**不**在 `ak.realm.policy_bundle` payload 内重复声明。该 metadata/下载策略由普通 Event/authority-commit/RealmCommit admission 保护；它本身不改变 MLS key 持有人，必须排除在 `key_access_revision` 外。

## 7. Safety

Blob service SHOULD:

- validate declared `size_bytes`
- compute digest server-side
- reject digest mismatch
- store MIME metadata as untrusted
- support malware scanning metadata
- support unsafe flag
- support GC grace period

## 8. Lifecycle

Blob MAY be GC'ed if:

- no live object references it
- grace period elapsed
- not under legal hold
- policy permits deletion
