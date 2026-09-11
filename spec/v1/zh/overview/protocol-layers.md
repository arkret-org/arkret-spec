---
title: 协议分层与信任边界
status: candidate
normative: true
stability: v1
updated: 2026-07-28
---

# 协议分层与信任边界

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本章是 Arkret v1 分层、扩展依赖方向与字段信任层归属的唯一规范来源。

## 1. 三层模型

Arkret v1 只有三个协议层，依赖方向只能由上向下：

```text
Extension → Collaboration Base → Kernel
Extension ─────────────────────→ Kernel
```

不得出现 Kernel 依赖 Collaboration Base/Extension，或 Collaboration Base 依赖某个可选
Extension。一个实现通过 Kernel conformance，不表示它实现了完整协作客户端。

### 1.1 Kernel

Kernel 仅包含下列安全原语：

1. Principal、Device、Service identity 与 proof；
2. Realm 与 `realm | circle | sidecar` `scope_ref` 原生安全作用域，以及 create-only `realm_genesis` 例外；
3. CBS Control Move、Seal、notary、state root 与闭集 lattice 词表；
4. signed durable DataEvent；
5. MLS scope/epoch binding；
6. core to-device queue；
7. self sync、peer federation 与 dependency fetch；
8. Blob descriptor、上传/下载与内容 digest；
9. Extension Manifest 的装载、隔离和资源约束；
10. `RecoveryTransaction` 与 `SecurityRotationTransaction`。

Kernel Event Envelope 不登记普通产品对象的寻址规则。新增应用 payload type MUST NOT 修改
Kernel Event、CBS 或 federation schema。

### 1.2 Collaboration Base

Collaboration Base 是官方协作基础包，包含 Strand、Message/Content、Relation、View 与
Blob-backed long text。**分层不是 conformance 声明单位**：v1 没有、也不会注册 `kernel` /
`collaboration_base` 对应的 profile id，实现的 conformance 声明一律通过
[`conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json) 的 implementation
profile 作出（协作对象由 `ak.profile.full_client.v1` 一类 profile 覆盖）。分层的规范作用只有两条：
[`protocol-layer-registry.json`](../../artifacts/registry/protocol-layer-registry.json) 对每个 active
Event.kind 的唯一归属，以及本节开头的依赖方向约束。只覆盖 Kernel 层 kind 的实现 MAY 完全不理解上述
协作 payload。

### 1.3 Extension

Signal、Calendar、Call/Media、Moderation、Directory/Push、Agent/Applet/Sidecar、
Organization/MIMI 与 identity hardening/witness 均为 Extension。扩展通过
[`extension-manifest.md`](../extensions/extension-manifest.md) 声明自己的 schema、reducer、
transport、资源上限与 vectors，不得把领域特例写回 Kernel gate。

### 1.4 Event.kind 的机器归属

[`protocol-layer-registry.json`](../../artifacts/registry/protocol-layer-registry.json) 是全部
active `Event.kind` 的穷尽分类真源。每个 kind 必须且只能出现在 `kernel`、
`collaboration_base`、`extension` 之一。新增或移动 kind 时，相关 conformance profile、
Extension Manifest 与 vectors MUST 在同一变更中更新；仅修改正文描述不构成有效分层。

## 2. 单一事实源

对 durable Event：

```text
signed_fact = envelope + kind + payload
state       = reduce(profile, prior_state, signed_fact)
```

producer MUST NOT 携带 `effects[]`、`conflict_keys_digest`，也 MUST NOT 任意选择可从
accepted governance basis 求出的 capability 引用。cell family、subject derivation、lattice、
bottom 与 state projection 是 reducer contract 的内部声明，不是 wire 上的第二份事实。

每个 reducer contract MUST 是由 schema-validated `kind + payload`、签名 envelope 字段、
已验证 basis 和前态决定的纯函数；不得读取本地到达顺序、未签名数据库字段或本地墙钟来决定
规范终态。每个写目标 MUST 声明输入、前态、输出、失败码及正负向量。

## 3. Security Scope

普通已存在 scope 中的 durable Event，其 producer 签名输入 MUST 包含以下三种 closed shape 之一：

```json
{"kind":"realm","realm_id":"ak:realm:..."}
```

或：

```json
{"kind":"circle","realm_id":"ak:realm:...","circle_id":"ak:circle:..."}
```

或：

```json
{"kind":"sidecar","realm_id":"ak:realm:...","sidecar_id":"ak:sidecar:..."}
```

`{"kind":"realm_genesis","realm_genesis_nonce":"..."}` 是 create-only 封闭例外，只允许对应的
Realm genesis Event；它不是普通 durable scope，也不得用于后续 Realm、Circle 或 Sidecar Event。
上述 closed union 以 `event-envelope.schema.json#/$defs/scope_ref` 为穷尽真源，正文集合必须由 lint 与其对齐。
Sidecar 的领域 Event kinds 仍归 Extension；Kernel 只认识签名 Event Envelope、CBS/Seal、MLS/AAD、
delivery/query 所需的原生安全 scope 形状，不解释 Sidecar 领域 reducer，也不得把 Sidecar 实现为 Circle。

字段名固定为 `scope_ref`。它是 signed producer fact，不是 reducer 盖章字段。reducer MUST
从 schema-validated payload、已接受的对象引用及治理状态独立派生 Realm、Circle 或 Sidecar 安全作用域，并逐字段比较；
无法派生、引用未补齐或不相等时 MUST fail closed。Event Envelope 不包含 reducer 盖章字段；
除 `event_id`、`proofs` 与 `unsigned` 外，所有实际存在的顶层字段都进入 producer event digest。

服务端只能用 `scope_ref` 做 ingress authorization、MLS/security policy 选择、eligible-device
fanout 与 federation routing。Strand、Message、Track、Call、read position 等精确产品目标
MUST 留在 recipient-visible ciphertext 内。Track 不是 v1 安全边界，也不存在 Track 级
server-visible ephemeral policy。

Event projection MAY 物化名为 `effective_scope` 的只读字段，但它 MUST 逐字段等于签名
`scope_ref`；不得成为第二个可写来源。

## 4. 字段信任层

每个 wire 字段必须属于且只属于以下一层：

| 层 | 含义 |
| --- | --- |
| `external_standard` | 外部标准原生对象；Arkret 不向其参数结构注入 overlay 字段。 |
| `transport` | 路由、重试、分帧等传输信息；不得参与业务授权或 reducer。 |
| `server_visible` | 服务端执行 scope/action/资源限制所需的最小元数据。 |
| `recipient_visible` | 只在 E2EE 解密后解释的产品目标与内容。 |
| `device_attested` | 设备签名声明；服务端只能验证签名、引用和 digest，不能把声明内容描述成自身观测事实。 |

一个结构不得跨层承载。其它位置对同一事实的表示必须是可机械重算的只读投影。

## 5. 最小正反例

正例：sender 签名 `scope_ref=circle`，server 仅验证 Circle membership 后转发密文；recipient
解密得到 `strand_id` 并运行 Collaboration Base reducer。

反例：sender 签名 Realm scope，却在密文中引用 Circle-only Strand。recipient 从 accepted
Strand projection 派生 Circle scope 后发现不等，必须拒绝；server 不需要也不得解密
`strand_id` 来替 sender 修正 scope。

反例：扩展 manifest 声明任意 JSON path 并让 producer 选择 cell。该 manifest 必须被拒绝，
因为它重新引入 producer reducer DSL。
