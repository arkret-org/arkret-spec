---
title: Current-v1 合同
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../conformance/conformance-profiles.md
  - ../conformance/schema-registry.md
  - ../conformance/encoding.md
  - ../sync/service-http-binding.md
  - ../sync/service-surface.md
sidebar:
  label: Current-v1 合同
---

## 0. 规范语言

本文中的规范关键字按 [conformance/normative-language.md](../conformance/normative-language.md) 解释。

## 1. 唯一 current-v1 合同

Arkret/1 管理三个互相独立的维度：

| 维度 | Wire 表达 | 作用 |
| --- | --- | --- |
| 协议族 | `protocol_version="1.0"` | 标识 Arkret/1 的签名域、核心对象与认证规则。 |
| Wire schema | `schema_id`、带 `.vN` 的 Event kind 与 operation schema | 定义单个 Event、DTO、证明或持久对象的 closed shape。 |
| 服务能力 | `ServiceDescribe` 的 operation、feature 与 conformance profile 集合 | 决定可选功能是否可用。 |

current-v1 的 canonical schema、registry、正文与 conformance vectors 共同构成唯一合同。规范发布前的修订直接替换这些真源并同步 SDK 与实现；不得增加别名、双读路径、第二套解释器或由 Realm 选择的状态语义。

Realm、Circle 与 Sidecar 的共享状态使用 Arkret v1 固定的领域 reducer。Realm 对象、Event、snapshot、MLS binding 与 `ServiceDescribe` 均不携带可协商的 reducer 选择；实现也不得通过 header、query、私有字段或本地配置为同一组 canonical bytes 选择另一套状态解释。

Spec、SDK 与服务实现的 SemVer 只管理发布制品，不参与联邦请求判定。构建 SHA、源码树摘要和生成文件摘要不得进入协议协商。

## 2. 固定 reducer 与顺序边界

每个注册 Event kind 直接绑定其领域 payload、领域 reducer 与 typed current result。治理 Station只按 Event 所属 stream 的 `RealmCommit.stream_position` 顺序执行这些规则：

- Realm、每个 Circle、每个 Sidecar 各自拥有独立 stream；不同 stream 不定义总序。
- producer Event 不携带 predecessor、提交位置或治理方选择。
- `previous_commit_ref` 只属于 `RealmCommit`，并且只可引用同 stream 的前一笔 Commit。
- 需要排除陈旧意图的领域 Event 在 typed payload 中携带 `expected_revision`；新对象使用稳定领域 ID。
- 一个 current-v1 实现必须支持全部 core reducer 语义，不能只支持某个可选择子集。

协议语义变化必须修改 current candidate 的 canonical schema、registry、fixture 与 SDK；它不是 Realm 内的治理动作。

## 3. 能力发现与失败边界

节点只根据明确能力集合决定可用功能：

- `supported_operation_bundles[]` 表示可调用 operation 的精确 carrier/request/response/error schema 组合；
- `supported_features[]` 表示可选运行时功能；
- `supported_profiles[]` 表示实现、部署或产品 conformance profile；
- `verified_profiles[]` 只提供独立验证证据，不增加操作能力。

`protocol_version` 是 bootstrap 判别字段。缺失、非字符串或非 canonical 字面形式是 `schema_violation`；形状合法但不等于 `"1.0"` 是 `unsupported_protocol_version`。缺少某项可选 feature 时只禁用依赖该 feature 的 operation，不得改用另一套状态语义。

## 4. Schema 与功能修订

- closed schema 的新形状使用新的 schema ID、Event kind 或 operation carrier；
- extensible map 内的 namespaced 非 critical 字段按 schema 规则保留或忽略；
- critical extension 不受支持时只拒绝相关 Event；
- 不改变共享状态解释的功能使用 capability 协商；
- 任何改变 Event admission、typed current result、RealmCommit 验证或 key-access revision 的修订必须同步更新规范、机器工件、SDK 与 conformance vectors。

## 5. 协商面清单

| 协商面 | 载体 | 判定时机 | 未命中时的处置 |
| --- | --- | --- | --- |
| 传输代际 | WebSocket subprotocol `arkret.v1` | 连接建立 | 回落 HTTP 或终止连接。 |
| 协议族 | describe / ping 的 `protocol_version` | 使用其它 v1 声明前 | 整个服务不可用。 |
| 服务能力 | operation bundles / features / profiles | 首次接触与缓存失效 | 只禁用未匹配 operation。 |
| describe 完整性 | `AuthenticatedServiceResolution.describe_digest` | route 二跳确认 | 不切换业务流量。 |
| 对象 shape | schema ID 与 versioned kind | schema validation | fail closed。 |
| 算法 selector | signature / digest / HPKE / MLS ciphersuite registry | 验签、摘要或加密处理 | 稳定 `unsupported_*` 错误。 |
| 端点能力 | MLS KeyPackage capabilities | KeyPackage claim | `claim_failed`。 |

服务 describe 不表达成员设备能力，KeyPackage capability 也不表达服务 operation 可用性。

## 6. 密文可解性不变量

1. 加密上下文由 closed schema 与已提交 group state 唯一确定。
2. HKDF info 与 AAD 由接收方从已签 outer Event、exact group state 与 envelope 重建。
3. 未被当前 schema 接受的算法 selector 一律 fail closed。
4. proof 与密文始终按其 canonical bytes 验证，不得重写。

因此“无法解密”只能来自缺少 key material 或授权不足，不能来自对同一 bytes 选择不同解释。

## 7. 异构实现互通（informative）

Arkret 使用协议族判别加多个正交能力面。服务增加 operation 时，客户端只调用自己认识且对端声明的面；对端缺少声明时不发送该请求。未知开放注册值可以被保存和转发，但未声明支持的语义仍必须拒绝或隔离。共享 Realm 状态的解释不参与双方协商，所有 current-v1 实现对同一 stream 的 Commit 序列执行相同领域规则。
