---
title: 协议演进
status: candidate
normative: true
stability: v1
updated: 2026-08-03
see_also:
  - ../authz/event-auth-state-resolution.md
  - ../conformance/conformance-profiles.md
  - ../sync/service-http-binding.md
  - ../conformance/normative-language.md
sidebar:
  label: 协议演进
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 四个版本维度

Arkret/1 分别管理四个版本维度，任何实现不得用其中一个替代另一个：

| 维度 | Wire 表达 | 作用 |
| --- | --- | --- |
| 协议族 | `protocol_version="1.0"` | 标识 Arkret/1 的身份、签名域、Event 因果模型与核心认证规则。 |
| Wire schema | `schema_id`、带 `.vN` 的 event kind / operation schema | 定义单个 Event、DTO、证明或持久对象的 closed shape。 |
| Realm reducer profile | Realm 的 `ak.component.realm.reducer_profile.v1` singleton control cell | 定义 Event admission、cell projection、lattice join、state root 与 security frontier 的共识语义。 |
| Capability | `ServiceDescribe` 的 operation、feature、schema/profile 能力集合 | 决定可选功能是否可用。 |

Spec、SDK 与服务实现的 SemVer 只管理发布制品，不参与联邦请求判定。实现不得用构建 SHA、发布版本或整包内容摘要代替上述机器可读合同。

## 2. Realm reducer profile

Reducer profile ID 使用 `ak.reducer.*.vN` 命名空间。当前注册的基线是 `ak.reducer.core.v1`。`ak.profile.*` 只表示实现、部署、产品或 conformance profile，不得写入 Realm reducer-profile cell。

每个 Realm 恰有一个 reducer-profile singleton control cell：

```text
ak:cell:ak.component.realm.reducer_profile.v1:null
```

其规则如下：

1. `ak.realm.create.payload.object.reducer_profile` 提供 genesis 值。
2. `ak.realm.upgrade.payload.target_reducer_profile` 是唯一后继写入口；该 Control Move 必须用标准 `head_eq` precondition 绑定 source profile。
3. profile cell 使用 `cas_register`、`bottom=reject`、`plane=control`，并完全复用 CBA join、Bottom 与 conflict recovery。
4. profile ID 的已发布语义不可原地修改；语义变化必须注册新的 ID 和从 source 到 target 的确定性 upgrade edge。
5. upgrade Event 本身由 source profile 解释；治理 basis 已包含该 upgrade 的后继才由 target profile 解释。

普通 Event 不声明 reducer profile。DataEvent 从其 `seal_ref` 认证的 joined control state 读取 cell；Control Move 从 `seal_basis` 的 frozen predecessor `J(L)` 读取。实现不得从本地 latest state、软件默认值、接收顺序或调用方字段推断。

## 3. Profile carrier 边界

Reducer profile 只出现在以下 canonical 位置：

- Realm create 的 `payload.object.reducer_profile`；
- Realm upgrade 的 `payload.target_reducer_profile`；
- Snapshot、MLS governance proof / binding 等必须脱离 Realm 状态独立验证的 reducer-derived artifact；
- `ServiceDescribe.supported_reducer_profiles[]`，用于广告本进程实际可执行的集合。

普通 Event、Event submit/query/subscribe/resolve/pull、普通 Realm operation 和 federation service binding 均不携带 reducer profile。调用方不得增加私有 header、query 或 JSON 字段来选择 reducer。

## 4. 能力发现与失败边界

节点只根据明确能力集合决定可用功能：

- `supported_operations[]`：可调用 operation；
- `supported_reducer_profiles[]`：可执行 Realm reducer；
- `supported_profiles[]`：实现、部署或产品 conformance profile；
- `supported_features[]`：可选功能。

目标 Realm 的 active reducer profile 不在本地实现集合时，该 Realm 操作返回 `unsupported_profile`；其它 Realm 不受影响。缺少计算 profile cell 所需的 CBA 依赖返回 `dependency_missing`；cell 为 Bottom 返回 `failed_bottom`、reason=`cell_in_bottom_state`。

Reducer upgrade target 的词法形状不合法时返回 `schema_violation`；target 未注册时返回 `unsupported_profile`；registry 中不存在 source→target edge 时返回 `failed_precondition`。

## 5. Schema 与功能演进

- closed schema 的新形状使用新的 schema ID、event kind 或 operation carrier；
- 已声明 extensible map 内的 namespaced 非 critical 字段可以按 schema 规则保留或忽略；
- critical extension 不受支持时只拒绝相关 Event；
- 不改变共识结果的功能使用 capability 协商；
- 改变 Event admission、cell、state root 或 security frontier 的功能使用新 reducer profile 和显式 Realm upgrade；
- 文档、fixture、实现重构与无语义 registry 整理不改变联邦判定。

任何进入签名语义的 canonical bytes 与已发布语义都不得原地重定义。每项影响 wire、状态、授权、安全、同步或互操作的变化必须进入对应 schema / registry，并有 conformance vector、fixture 或明确测试计划。

## 6. 传输与 `unsigned`

HTTP path 不承担协议版本语义；能力由 `GET /_arkret/describe` 和各 surface describe 返回。`open`、`edge`、`self`、`root`、`peer`、`gate`、`find` 只区分调用者和信任边界。

`unsigned` 仅承载可丢弃的本地或传输元数据，MUST NOT 影响 event digest、授权、reducer 或 canonical state。任何状态真相输入必须位于签名覆盖的 canonical schema 中。
