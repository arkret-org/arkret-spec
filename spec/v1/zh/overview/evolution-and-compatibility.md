---
title: 协议演进与 current-wire 边界
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - ../conformance/encoding.md
  - ../conformance/conformance-profiles.md
  - ../sync/service-http-binding.md
  - ../conformance/normative-language.md
sidebar:
  label: 协议演进
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与边界

本文定义 Arkret v1 的协议演进边界：实现如何在不破坏已接受 v1 签名字节、不引入隐式双语义、不让未声明能力跨越信任边界的前提下新增能力。

本文只约束 **current v1 wire**。current parser、reducer、federation peer、snapshot consumer、conformance runner 与生产 SDK 只处理当前 registry、schema、profile 与 OpenAPI binding 所定义的 v1 形态。任何不在当前真相源中的 operation、event kind、schema、字段、profile 或 critical extension 都按对应源文档定义的 `unsupported_feature`、`unknown_kind`、`unknown_field`、`schema_violation`、`quarantine` 等结果 fail closed；实现不得在实时协议路径中做隐式形态转换、字段猜测或按 payload shape 选择另一套语义。

## 2. 两个硬约束

Arkret 是联邦化、端到端加密（MLS）、事件溯源协议。客户端、服务端与 federation peer 独立部署，因此协议演进受两个硬约束支配：

1. **已接受事件是不可变签名字节。** Event Envelope 的签名与 hash 输入是去除 `proofs` 与 `unsigned` 后的 canonical JSON bytes（见 [conformance/encoding.md](../conformance/encoding.md) §2）。改写其中任一字节即破坏签名。
2. **对端能力必须显式声明。** federation peer、client、service 与 gateway 不能假设对方支持本地新增能力；互通只能基于 describe/profile/feature/operation 交集。

由此得出 v1 演进基本规则：

> 演进 MUST 是加性的、可协商的、可测试的；实现 MUST 持续验证其已接受且仍在声明 profile 范围内的 v1 签名字节；未声明或未登记能力 MUST fail closed，而不是被实时路径容忍、猜测或重写。

## 3. 加性演进

v1 内部演进采用以下加性方式：

- 新增 event kind、schema id、operation、profile、feature 或已预先声明的 extension point；closed schema / payload 上新增 optional 字段仍是 wire-breaking，不属于可独立部署的加性变更；
- 新增能力必须登记到相应单一真相源：contract registry、schema registry、profile matrix、operation registry、error-code registry、OpenAPI binding 或对应 domain registry；
- 任何进入签名语义的字段，一旦被当前 v1 接受，其 canonical bytes 与语义不得原地改变；
- 需要改变对象模型或状态机语义时，必须新增可协商的 schema/profile/kind，并明确与既有 current-v1 语义的边界；
- 新增 critical extension、required feature 或高风险 profile 时，未声明实现按 [conformance/conformance-profiles.md](../conformance/conformance-profiles.md) 与 `conformance-profiles.json` 的 unknown/unsupported 规则 fail closed。

Profile 命名采用 `ak.profile.<name>.v1`。current-v1 树不得预注册其它 major；需要调整的 profile 在稳定发布前直接原子更新其 canonical v1 定义。

### 3.1 破坏性变更的承载（normative）

当前规范尚未稳定发布，因此破坏性修订 MUST 在一个原子变更中直接更新 canonical event kind、schema、field、profile、OpenAPI、fixture 与 vector，并删除被替代形态。current-v1 树不得保留 rename alias、migration manifest、旧 parser 分支、新旧双写或未来 major profile。修订完成后，只有更新后的 canonical 形态存在；任何缺席于当前 registry/schema 的输入都按 `unknown_kind`、`unknown_field`、`schema_violation` 或对应稳定错误 fail closed。

stable v1 发布包一旦冻结，其 registry/schema/reducer release 即为不可变 lockstep 单元。closed schema、既有 kind payload 或 reducer contract 的任何修订必须通过新的 schema id / event kind / 显式 profile 发布；不得原地给 stable closed schema 增加 optional 字段。联邦双方 release digest 不同期间，`reducer_profile_mismatch` 整批 fail closed 是预期行为；self surface 对未知 kind / field 逐事件 fail closed。Producer 只能在双方已声明的 schema/kind/profile 交集内发送，不存在“已知加性超集”自动降级。混版本部署必须先升级所有参与节点的声明能力，再启用新 profile；旧 profile 的 wire bytes 与语义保持不变。

## 4. Profile / capability 协商

每个实现 MUST 声明自己支持的 profile、operation、feature、schema 与 binding（见 [conformance/conformance-profiles.md](../conformance/conformance-profiles.md) §1-§2.1）。互通集合由双方声明能力的交集确定：

- 未声明的 optional extension 可以省略交互；若调用方仍尝试该交互，receiver 返回已登记的 wire code `unsupported_feature`。`feature_not_advertised` 只是在能力发现面描述“未广告”的状态标签，不是 wire 错误码；
- 未声明的 required feature、critical extension、高风险 action 或影响授权 / 安全 / 密钥材料的能力 MUST fail closed；
- federation peer 在接受跨域事件、snapshot、KeyPackage、directory claim、capability decision 或 applet transaction 前，必须验证本地 profile 与对端 profile 的交集覆盖该对象的全部 required semantics；
- client 与 SDK 不得把本地 UI/配置开关当成协议能力声明；协议能力以 ServiceDescribe、profile matrix、event/schema registry 与签名对象内的 profile 绑定为准。

## 5. 传输层 versionless

默认 HTTP/JSON binding 的 path 都在 negative-space 根 `/_arkret/` 之下且不含版本段；版本与能力发现由 `*.describe` / `supported_operations` / `supported_profiles` / `supported_features` 承载。见 [sync/service-http-binding.md](../sync/service-http-binding.md) §2.1。

pre-auth 的根级能力广告位于 `GET /_arkret/describe`（`ak.server.query.describe`）。实现不得通过 URL path 后缀、私有 header 或部署约定绕开 ServiceDescribe 的能力声明。

## 6. 签名位面与 `unsigned` 位面

`unsigned` 是传输或本地附加信息，MUST NOT 影响 event digest 或 proof `event_digest`（见 [conformance/encoding.md](../conformance/encoding.md) §2）。因此 `unsigned` 可以承载可丢弃的本地/传输元信息；任何影响授权、状态机、密钥材料、审计，或任何进入 reducer / canonical projection 计算的真相输入（projection 本身是派生层、非真相源，此处指"被 reducer 消费以派生 canonical 状态的签名输入"，而非派生出的投影结果）的内容，不得只放在 `unsigned` 中。

## 7. 可操作清单

落地一项协议改动时，按以下清单判断：

1. **单一真相源**：新增或改变的对象、字段、operation、error、profile、vector 必须进入对应 registry/schema/artifact；Markdown 表只做说明视图。
2. **加性优先**：新增能力通过 optional/required feature、profile、schema 或 event kind 表达；不得原地改变已接受签名字节语义。
3. **显式协商**：跨 client/service/federation 的新能力必须能从 describe/profile 交集中判断可用性。
4. **fail closed**：未知 required feature、critical extension、高风险 action、未登记 operation/kind/field 与不匹配 profile 均按源文档定义的稳定错误或 quarantine 处理。
5. **可测试**：每个影响 wire、状态机、授权、安全、同步或互操作的新增义务都应配套 conformance vector、fixture 或明确测试计划。
6. **不泄漏产品面**：`/_arkret/` 只承载协议语义；部署私有管理、运营或产品 API 不得注册进 Arkret operation namespace。
