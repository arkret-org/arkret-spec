---
title: 协议演进与向后兼容
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - conformance/encoding.md
  - conformance/conformance-profiles.md
  - sync/service-http-binding.md
  - conformance/normative-language.md
sidebar:
  label: 演进与兼容
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文是 Cokret 协议演进与向后兼容的**导航入口**：当一处改动需要判断"是否破坏兼容、历史数据是否仍可读、未升级对端是否仍可互通"时，从这里出发。

本文不发明新机制，只汇总并交叉引用既有规范（`encoding.md`、`conformance-profiles.md`、`renames.json`、`service-http-binding.md`）。规范关键字以被引用的源文档为准；本文与源文档冲突时，以源文档为准。

## 2. 两个硬约束

Cokret 是联邦化、端到端加密（MLS）、事件溯源协议。客户端与服务端各自独立升级，因此"普通项目停机迁移数据库"不适用，根因是两个硬约束：

1. **历史数据是不可变签名字节。** Event Envelope 的签名与 hash 输入是去除 `proofs` 与 `unsigned` 后的 canonical JSON bytes（见 [conformance/encoding.md](../conformance/encoding.md) §2）。改写其中任一字节即破坏签名；而事件可能由**他方**用**其私钥**签署，本方既无密钥也无权改写。
2. **对端版本不可控。** 联邦中其他 server / client 是异构版本共存，无法强制全网同步升级。

由此得出 Cokret 的演进基本定位：

> 演进 MUST 是"新代码永远能读旧字节、能与旧对端协商"，而 MUST NOT 是"把旧数据迁到新版本"。

## 3. 不可变签名字节 → 用重放/投影代替数据迁移

历史事件是 append-only 的不可变日志。升级 MUST NOT 改写历史签名字节。允许变化的是**可重建的物化视图**：reducer / projection 在新代码下重新解释同一份历史事件，产出新的派生读模型（如 Space / Flow / Morph lifecycle projection、Collection、inbox、搜索索引）。

因此在 Cokret 中，"数据迁移"被**重放（replay）/ 投影（projection）** 取代：

- 不可变的签名事件是真相；派生视图是可丢弃、可重算的缓存。
- 升级一个 reducer/projection 的语义时，重放历史即可得到新视图，无需也不得触碰历史字节。

## 4. 只有 v1，演进靠 v1 内部的加性升级

实现 MUST NOT 在正式代码与协议中定义除 v1 以外的版本 profile 或存储键。演进发生在 v1 **内部**，以加性方式进行：

- 新增 event kind / schema / profile 是加性的；已部署 reader 遇到未声明的能力按 §5 的 fail-closed 规则处理。
- **永不原地改变已签名字段的语义。**
- 遗留字段经 schema profile 升级迁移。例如非整数 number 字段：v1 wire MUST 用 integer 表示数值，遗留字段"MUST 在下一个 schema profile 升级时迁移到整数 + scale"（见 [conformance/encoding.md](../conformance/encoding.md) §2）。

Profile 命名采用 `ck.profile.<name>.v<major>`，`<major>` 是 profile 自身的演进轴，**不是**新增的协议版本 profile（见 [conformance/conformance-profiles.md](../conformance/conformance-profiles.md) §2）。

## 5. Profile / capability 协商 + fail-closed（应对"对端未升级"）

每个实现 MUST 声明自己支持的 profile、协议版本与 feature 集合（见 [conformance/conformance-profiles.md](../conformance/conformance-profiles.md) §1–§2.1）。互通是**协商**出来的，不是假设出来的：

- 兼容性 = 双方声明能力的**交集**。
- Extension（v1 lattice / interop）能力**只在显式 opt-in 时启用；未声明的实现遇到这些能力 MUST fail closed**。
- 能力广告通过 `*.describe` / feature discovery 暴露（见 §6）。

这条规则让"新客户端打旧服务器、旧客户端打新服务器"都能先握手、再按交集工作，而不会因单方假设对端是新版而误判。

## 6. 传输层 versionless，版本协商在协议内

默认 HTTP/JSON binding 的所有 path 都在 negative-space 根 `/_cokret/` 之下且**不含版本段**；版本不进 path，由 `*.describe` / `supported_operations` 协商（可选 `Cokret-Protocol-Version` header）。见 [sync/service-http-binding.md](../sync/service-http-binding.md) §2.1。

pre-auth 的根级能力广告位于根 meta 位 `GET /_cokret/describe`（`ck.server.describe`）。因此版本/能力发现是协议内的一等公民，新旧实现据此协商，而不依赖 URL 版本号或部署假设。

## 7. 破坏性改名走 `renames.json` + 离线 migration tool

并非所有演进都是纯加性。标识符改名、命名空间重组等破坏性改动 MUST 经由唯一真相源 [artifacts/migration/renames.json](../../artifacts/migration/renames.json) 登记，并遵守其双层 parser 语义：

- **current_parser**（sync / federation / snapshot consumer / reducer / 一致性 runner 等处理实时或持久 v1 wire bytes 的一切）：对登记的旧标识符 **hard_reject**，且 **MUST NOT 做 payload-shape 消歧**；按 schema 标准错误（`unknown_kind` / `unknown_field` / `schema_violation`）拒绝。
- **migration_tool**（离线批处理）：才允许读非当前 v1 字节并重写为 canonical v1 形态；MUST NOT 内嵌进实时 parser 面（不得内联转换、不得"自动接受旧形态并悄悄改写"）。

关键约束：**不存在 in-band 兼容容忍窗口**，也不存在任何形式的 mechanical replacement window；拒绝层级与允许上下文以 `renames.json` 的 `rejection_levels` 为唯一真相源。破坏性改动的兼容性是显式、有边界、可测试的（cotest drift fixtures），而非在实时路径堆隐式兼容分支。

## 8. 签名 / `unsigned` 位面分离作为安全扩展位面

`unsigned` 是传输/本地附加信息，MUST NOT 影响 event digest 或 proof `event_digest`（见 [conformance/encoding.md](../conformance/encoding.md) §2）。这给出一个安全的扩展位面：可以往 `unsigned` 增补本地/传输元信息而**不触碰任何签名字节**，旧 reader 直接忽略未知 `unsigned` 内容。注意这只适用于非规范、可丢弃的附加信息；任何进入签名语义的内容仍走 §4 的加性 schema 演进。

## 9. 可操作演进规则清单

落地时按以下规则判断一处改动：

1. **加性优先**：新增 optional 字段 / 新 event kind / 新 schema / 新 profile；MUST NOT 原地改变已签名字段语义。
2. **破坏性改动新旧并存**：引入新 event kind 或新 schema profile，旧的保留为只读历史，而非原地替换。
3. **改名必登记**：任何标识符迁移写进 `renames.json`；current parser hard_reject 旧标识符；历史数据靠离线 replay / projection 处理。
4. **reader 在其声明 profile 范围内 MUST 能解析历史签名字节**；超出声明范围按 fail-closed，而非崩溃或误读。
5. **协商而非假设**：握手时声明 profile + feature，按交集工作。
6. **不破坏不可变性**：升级改的是可重建的派生视图（重放/投影），不是历史字节。
7. **不引入新版本概念**：MUST NOT 定义 v1 以外的版本 profile 或存储键；MUST NOT 发明新的 in-band 兼容容忍窗口。

## 10. 兼容性原则摘要

签名事件不可变 → 用重放/投影代替数据迁移；对端不可控 → 用 profile 协商 + 加性演进 + fail-closed 代替"强制全网升级"。
