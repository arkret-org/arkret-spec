---
title: Extension Manifest
status: candidate
normative: true
stability: v1
updated: 2026-07-28
---

# Extension Manifest

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

Extension Manifest 是扩展装载、隔离与 conformance 绑定的唯一机器入口。manifest 是声明性数据，
不是可执行代码、selector 语言或 reducer DSL。

## 1. 必填声明

每个 manifest MUST 声明：

```text
manifest_id
extension_id
namespace
layer
manifest_digest
publisher
published_at
dependencies[]
payload_schemas[]
reducer_contracts[]
required_actions[]
confidentiality
transport_profiles[]
recovery_profile
federation_profile
conformance_vectors[]
resource_limits
signatures[]
```

`layer` 只能是 `collaboration_base` 或 `extension`。Kernel 不通过 manifest 自我声明。
namespace 必须与 extension id 绑定且无冲突。每个 schema/reducer/vector 引用必须使用
content digest；网络 URL 只能是获取 hint，不能替代 digest identity。
不需要跨设备恢复或 federation 的扩展分别把 `recovery_profile` /
`federation_profile` 显式设为 `null`；不得为满足必填字段而引用无语义的占位 profile。

`manifest_digest = sha256(canonical_json(manifest_without_manifest_digest_and_signatures))`。
publisher proof 必须签
`canonical_json({context:"ak.extension-manifest-proof-v1", payload_digest:manifest_digest,
extension_id, publisher, verification_method, created_at, domain?, audience?})`，其中
`created_at` 必须逐字等于 `published_at`。`manifest_digest` 不得递归包含自身或 signatures。

## 2. 封闭词表

manifest 只允许以下 reducer/lattice 引用：Kernel 已登记的闭集 lattice，或 manifest 明确引用的
独立代数 profile 和跨实现 vectors。confidentiality 只能是
`plaintext_allowed | recipient_encrypted | e2ee_required`。transport profile 只能引用 active
operation/rail id。resource limits 只能使用 Kernel schema 定义的 byte/item/depth/rate 维度。

manifest 不得包含：

- 任意 JSON path/cell subject 表达式；
- producer 选择的 cell write / state projection；
- 可执行条件、脚本、Wasm 或通用 policy DSL；
- server-visible 的业务 target selector；
- 修改 Kernel Event、Seal、CBA 或 federation schema 的指令；
- 与 reducer contract 并列的第二份状态映射。

## 3. 装载算法

Kernel loader MUST：

1. 验证 manifest canonical digest、publisher signature 与 active schema；
2. 检查 namespace 唯一性；
3. 构造 dependency DAG，拒绝环、缺失依赖或层级逆向依赖；
4. 验证所有 action、schema、reducer、transport 和 vector 引用存在且 digest 匹配；
5. 检查声明资源上限不超过 Kernel 硬上限；
6. 只广告已完整装载且 vectors 通过的 extension/profile。

未知 extension payload 可按 Event requirements 的 criticality 保留或 fail closed，但不得运行未知
reducer。依赖 closure 任一节点失效时，loader 必须撤下整个受影响 profile 的能力广告。

## 4. Conformance 边界

Kernel conformance 不启用任何 manifest。Collaboration Base 由一个标准 manifest 聚合 Strand、
Message/Content、Relation、View 与 long text；Calendar、Call、Agent、Applet 等各自独立。
新增普通 payload type 只修改其所属 manifest/schema/reducer/vector，不得修改 Kernel release
gate 的领域特例表。

正例：Calendar manifest 引用 Kernel Event 与 Blob，声明 calendar payload schema 和 reducer
vectors；Kernel 无需理解 RSVP 字段。

反例：manifest 用 `payload.calendar_id` 作为 server routing selector。精确产品目标应在密文内，
该 manifest 必须拒绝。
