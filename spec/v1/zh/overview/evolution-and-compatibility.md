---
title: 协议演进
status: candidate
normative: true
stability: v1
updated: 2026-08-26
see_also:
  - ../authz/event-auth-state-resolution.md
  - ../conformance/conformance-profiles.md
  - ../conformance/schema-registry.md
  - ../conformance/encoding.md
  - ../crypto-media/encryption-and-audit.md
  - ../sync/service-http-binding.md
  - ../sync/service-surface.md
  - ../conformance/normative-language.md
sidebar:
  label: 协议演进
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 四个版本维度

Arkret/1 分别管理四个版本维度，任何实现不得用其中一个替代另一个（本模型的设计动机与混合版本网络的运转方式见 §9，informative）：

| 维度 | Wire 表达 | 作用 |
| --- | --- | --- |
| 协议族 | `protocol_version="1.0"` | 标识 Arkret/1 的身份、签名域、Event 因果模型与核心认证规则。接收方在使用 describe 中任何其它声明前 MUST 先执行精确版本比较；不等于 `"1.0"` 时将整个服务判定为不可用并产生 `unsupported_protocol_version`，不得继续能力交集、缓存路由或发起业务请求。 |
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

当前 v1 registry 没有 active upgrade edge，因此任何 `ak.realm.upgrade` 都按 §4 以 `failed_precondition` 拒绝；这是已裁决的 v1 边界，不是隐式成功或实现缺省。首个后继 reducer profile 只能在同一发布中同时登记 source→target edge，并满足 `reducer-profile-registry.json#upgrade_release_gate` 要求的成功 transition、source `head_eq` precondition、未注册 target、未声明 edge 与并发 upgrade 冲突五类向量后发布。

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

- `supported_operation_bundles[]`：可调用 operation 的精确 carrier/request/response/error schema 组合；
- `supported_reducer_profiles[]`：可执行 Realm reducer；
- `supported_profiles[]`：实现、部署或产品 conformance profile；
- `supported_features[]`：可选功能。

目标 Realm 的 active reducer profile 不在本地实现集合时，该 Realm 操作返回 `unsupported_profile`；其它 Realm 不受影响。缺少计算 profile cell 所需的 CBA 依赖返回 `dependency_missing`；cell 为 Bottom 返回 `failed_bottom`、reason=`cell_in_bottom_state`。

Reducer upgrade target 的词法形状不合法时返回 `schema_violation`；target 未注册时返回 `unsupported_profile`；registry 中不存在 source→target edge 时返回 `failed_precondition`。

`protocol_version` 是一个 bootstrap 判别字段，不是可选 capability。对携带该字段的 describe / ping 响应，接收方 MUST 在依赖 v1-specific schema 解释其它字段之前先取出它：缺失、非字符串或非 canonical 字面形式是 `schema_violation`；形状合法但与本地唯一支持值 `"1.0"` 不同是 `unsupported_protocol_version`。后一种结果是对端代际不受支持，不表示对端响应属于 v1 内的损坏对象。

## 5. Schema 与功能演进

- closed schema 的新形状使用新的 schema ID、event kind 或 operation carrier；
- 已声明 extensible map 内的 namespaced 非 critical 字段可以按 schema 规则保留或忽略；
- critical extension 不受支持时只拒绝相关 Event；
- 不改变共识结果的功能使用 capability 协商；
- 改变 Event admission、cell、state root 或 security frontier 的功能使用新 reducer profile 和显式 Realm upgrade；
- 文档、fixture、实现重构与无语义 registry 整理不改变联邦判定。

任何进入签名语义的 canonical bytes 与已发布语义都不得原地重定义。每项影响 wire、状态、授权、安全、同步或互操作的变化必须进入对应 schema / registry，并有 conformance vector、fixture 或明确测试计划。

pre-GA 的 current-v1 直接修订只持续到 `v1.0.0` promotion。promotion 后的冻结面、兼容新增、两阶段退役、最短观测窗口、历史解释保留、安全例外与 catalog diff 门禁，唯一规则见 [`release-readiness.md` §5.1.1](./release-readiness.md)。本文的 schema / capability / reducer 演进规则在 post-GA 不得被解释为删除或原地替换已发布 active 行的许可。

## 6. 传输与 `unsigned`

HTTP path 不承担协议版本语义；能力由 `GET /_arkret/describe` 和各 surface describe 返回。`open`、`edge`、`self`、`root`、`peer`、`gate`、`find` 只区分调用者和信任边界。

`unsigned` 仅承载可丢弃的本地或传输元数据，MUST NOT 影响 event digest、授权、reducer 或 canonical state。任何状态真相输入必须位于签名覆盖的 canonical schema 中。

## 7. 协商面清单（路由视图）

异构版本互通不依赖单一版本号，而是由下列相互独立的协商面共同判定。本节是**路由视图**：每一行的规范内容只在「规范位置」列所指文件中定义，本表不重复承载规则，也不得被当作第二份真相源。

| 协商面 | 载体 | 判定时机 | 未命中时的处置 | 规范位置 |
| --- | --- | --- | --- | --- |
| 传输代际 | WebSocket subprotocol `arkret.v1`；HTTP binding 不含 path 版本段，必要时用 `Arkret-Protocol-Version` 请求/响应 header 或 media-type 参数 | 连接建立 | 服务端未选择该 subprotocol 时客户端不建立该连接并回落 HTTP | [`../sync/websocket-binding.md`](../sync/websocket-binding.md)、[`../sync/api-conventions.md` §11](../sync/api-conventions.md) |
| 协议族 | describe / ping 中的 `protocol_version` | bootstrap JSON 解析后、使用任何 v1-specific 声明前 | 不等于 `"1.0"` 时以 `unsupported_protocol_version` 将整个服务判定为不可用；不进入 capability 协商 | 本文 §1、§4，[`../sync/service-surface.md` §17](../sync/service-surface.md) |
| 服务能力 | `*.describe` 的 `supported_operation_bundles` / `supported_features` / `claimed_profiles` / `verified_profiles` / `supported_features` / `interop_surfaces` | 首次接触与缓存失效 | 没有 exact operation carrier/schema 交集时只禁用该 operation，调用方不得据非标准 404 body 推断能力 | [`../sync/service-surface.md` §3.0](../sync/service-surface.md) |
| describe 完整性 | 签名 `ServiceResolutionRecord` 的 `describe_digest` 反向绑定 | route 解析的二跳确认 | digest 不一致时不切换业务流量 | [`../sync/service-surface.md` §2.6](../sync/service-surface.md) |
| 对象 shape | schema id 与带 `.vN` 的 event kind / operation carrier；schema 内闭集枚举按版本冻结 | schema validation | `schema_violation`，或算法 selector 对应的稳定 `unsupported_*` 码 | [`../conformance/schema-registry.md` §6、§6.1](../conformance/schema-registry.md) |
| 开放注册集取值 | event kind、error code、relation kind、typed id kind、feature id 等 registry 字符串集合 | 反序列化与语义处置两段分离 | 未知值原样保留、不使整体解码失败；语义处置仍按各消费面 fail-closed 规则 | [`../conformance/schema-registry.md` §6.1(a)](../conformance/schema-registry.md) |
| 共识语义 | Realm 的 reducer-profile singleton control cell | 每条 Event 从其 CBA governance basis 读取 | `unsupported_profile` | 本文 §2、§4 |
| 逐 Event 硬要求 | `requirements.schema[]` / `features[]` / `critical_extensions[]` | Event admission | 未知 critical 标识 MUST fail closed | [`../conformance/schema-registry.md` §6](../conformance/schema-registry.md)、[`../conformance/conformance-profiles.md` §3](../conformance/conformance-profiles.md) |
| 算法 agility（四面） | signature / digest / HPKE / MLS ciphersuite 四个 registry 的 schema 内 selector | 验签、摘要、应用层封装、MLS 群组协商 | `unsupported_signature_alg` / `unsupported_digest_algorithm` / `unsupported_hpke_suite` / `unsupported_ciphersuite` | [`../conformance/encoding.md` §3.2、§6.1](../conformance/encoding.md)、[`../crypto-media/encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md)、[`../conformance/schema-registry.md` §6.1(b.1)](../conformance/schema-registry.md) |
| 端到端对端能力 | KeyPackage `capabilities` 与 claim `required_capabilities`（`required_capabilities ⊆ capabilities`） | KeyPackage claim | `claim_failed` | [`../crypto-media/device-lifecycle.md` §9](../crypto-media/device-lifecycle.md)、[`../crypto-media/encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md) |

表中 KeyPackage 行之前的对端都是**服务**，其声明面经签名 route record 与 describe digest 绑定；KeyPackage 行的对端是**设备端点**，它是 v1 唯一的客户端↔客户端能力协商载体。两类协商面不得互相替代：服务 describe 不表达群成员设备的能力，KeyPackage capability 也不表达服务 operation 可用性。

## 8. 密文可解性不变量

本节不新增 wire MUST，它把已经分散生效的规则组织成唯一判定链，回答“新旧实现共存时密文会不会因为版本差异而产生歧义”。

1. **选择器不上 wire**：`ak.schema.encrypted_envelope.v1` 的 `version` 是 const，加密上下文的分支由结构（`counter` 是否存在）决定，内容方案由 `group_state_ref` 指向的 exact winning group state 冻结；不存在调用方提供的 scheme selector。
2. **认证输入由接收方重建**：HKDF info 与 AEAD / HPKE AAD 按注册的唯一派生公式从已签 outer Event、exact group state 与 envelope 自身重算，接收方不采信 wire 上的派生镜像。
3. **算法集合按 schema 版本冻结**：四个算法 registry 是算法 token 的机器词表，但具体 canonical object 的 selector 是按 schema 版本冻结的闭集；registry 把 reserved 行转为 active 不回改已发布 schema 的 enum。
4. **未识别一律 fail closed**：未登记或未被该 schema 版本接受的 suite MUST 拒绝，即使本地密码学库支持；不得猜测、不得回退到旧算法、不得把 Unknown 变体交给密码学库。
5. **历史字节永不重写**：已发布的 proof 与密文永远按其发布时的算法重验；新算法只能走新 proof 与新 schema 版本。

由 (1)(2) 得同一段密文对任意合规接收方只有一个原像重建路径；由 (3)(4)(5) 得算法演进不会让旧接收方对同一字节产生第二种解释。因此在同一协议代际内，接收方“解不开”只可能来自缺少 key material（[`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) 的 `decryption_pending`）或授权不足，不可能来自版本歧义。

密文层之外的向前兼容是另一条独立路径：解密成功后遇到未知 Content Block `kind` 时按 [`../models/content-types.md` §7.2](../models/content-types.md) 以已认证的 `body` 降级展示，MUST NOT 丢弃该消息。该路径不依赖密钥层协商，也不得被用来解释密钥层的 fail-closed 义务。

## 9. 设计原理与混合版本互通（informative）

本节是解说性文字，不新增任何规范义务；术语与规则以 §1–§8 及各被引用文件为准。它回答三个问题：为什么 Arkret 不用单一版本号协商，fail-closed 交集为什么是默认姿态，以及新旧实现混跑的网络在典型场景下如何实际运转。

### 9.1 为什么不是单一版本号

集中式服务可以让所有客户端跟随服务端一起升级，所以"一个版本号 + 服务端灰度"就够了。去中心化网络没有这个前提：没有任何一方能强制他人升级，网络的常态是不同年代的客户端、服务端与联邦对端长期共存。这时单一版本号会制造两难——要么把任何功能差异都变成"版本不同、拒绝通讯"（网络按最慢实现分裂），要么让版本号退化成没有判定力的装饰。

Arkret 的取舍是：`protocol_version` 只保留**代际判定**这一件事（签名域、Event 因果模型与核心认证规则的整体身份，见 §1、§4），几乎永不改变；其余全部差异按关注点拆到 §7 列出的相互正交的协商面上，各自独立演进、独立失败。一个功能、一个算法、一种共识语义的可用性各有自己的判定载体与稳定错误码，任何一面不匹配都只使**那一面**不可用，不传染到整个连接。

HTTP path 不承载版本（§6）出于同一逻辑的传输面推论：URL 里的 `/v2/` 是未认证的、一次性对整个 API 面分叉的粗粒度开关，还会诱导实现长期维护双栈路由。Arkret 的能力声明经签名 `ServiceResolutionRecord` 与 `describe_digest` 绑定（§7 第四行），是可验证、逐能力的，而 path 版本两者都做不到。

### 9.2 fail-closed 交集为什么是默认

互通性 = 双方声明能力的交集，未声明即不可用（[`../conformance/conformance-profiles.md` §1](../conformance/conformance-profiles.md)）。选择这个默认，是因为在开放联邦里"宽容接受不认识的东西"的每一种形态都对应一类真实故障：静默忽略未知语义会让不同实现对同一 Event 序列收敛出不同状态（共识分裂）；按猜测降级会成为降级攻击的入口；"尽力执行"会让声明面与实际行为脱钩，把 fail-closed 协商变成 fail-open。交集原则把最坏结果钉在"该功能对这对端不可用"，而不是"状态分叉"或"安全边界被静默放宽"。

它的代价——新功能在对端升级前不可用——由两层解码纪律缓解（[`../conformance/schema-registry.md` §6.1](../conformance/schema-registry.md)）：**反序列化层**对开放注册集的未知值原样保留，旧实现不会因为网络上出现新 event kind 就整体解码失败、掉出网络；**语义层**对未声明支持的能力照常拒绝或隔离。也就是说，旧节点"看得见、存得住、转发得了"新数据，只是不假装执行它。未知值保留 ≠ 语义接受，这条边界是整个演进模型的支点。

### 9.3 为什么共识语义单独走 reducer profile

describe 协商是**成对**的：A 与 B 各自声明，交集只约束这一对连接。但 Realm 的共识语义（Event admission、cell projection、lattice join、state root、security frontier）必须对**所有成员、所有时间点**的验证者给出同一答案，否则同一 Realm 会在不同实现上分叉。所以它不走 describe，而是写进 Realm 自身的 governance 状态（reducer-profile singleton cell，§2），每条 Event 从**它自己的** CBA basis 读取该 cell——任何时候重放历史，每条 Event 都由它当时生效的语义解释，与验证者本地软件的新旧无关。升级共识语义因此不是"发布新软件"，而是 Realm 内一次可审计的显式治理动作（`ak.realm.upgrade`），带 `head_eq` 前置条件、由 source profile 解释、经 registry 声明的 upgrade edge 门禁（`reducer-profile-registry.json#upgrade_release_gate`）。

### 9.4 典型混合版本场景

以下场景全部由既有规则推出，作为阅读校验：

1. **旧客户端 × 新服务端**：新服务端多声明的 operation / feature 对旧客户端不可见也无影响；旧客户端只调用自己认识且对端声明的面。反向（新客户端 × 旧服务端）由交集原则对称处理——新客户端在 describe 缺少声明时不发送新面的请求。
2. **新 event kind 到达旧节点**：反序列化保留（§6.1(a)）；若旧节点是该 Realm accepted history 的责任方则按 [`../conformance/conformance-profiles.md` §2.1](../conformance/conformance-profiles.md) 拒绝或隔离，若只是只读投影方则保留 raw event 并标记 projection incomplete。发送方本应先确认对端声明（交集原则），所以该场景出现即说明发送方违规或声明面漂移。
3. **新算法上线**：registry 先登记 reserved 行（不可上 wire）→ KAT / 协商负例 / activation requirements 就绪 → 新 schema 版本携带扩展后的 selector 闭集发布 → producer 仅对已声明新 schema 版本与相应 profile 的对端使用新算法。旧接收方拒绝新 selector 是**合规的协商结果**，不是缺陷（§6.1(b.1)）。已发布的历史字节永不按新算法重验（§8）。
4. **新共识语义**：按 §9.3 走新 reducer profile 与显式 Realm upgrade；不支持 target profile 的成员对该 Realm 后继 Event 得到 `unsupported_profile`，其它 Realm 不受影响。当前 v1 没有 active upgrade edge（§2），首个后继 profile 的发布门禁已在 registry 中钉定。
5. **E2EE 群里的新内容能力**：能力下界是 MLS 认证的 GroupContext 状态（`required_keypackage_capabilities`，[`../crypto-media/encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md)）；不满足下界的设备进不了群，发送方只能使用下界内的能力，提高下界必须经 GroupContextExtensions proposal 并在 Commit 前验证全体成员。因此"群里有人解不出新格式"被结构性排除在合法状态之外；密文本身的无歧义性由 §8 保证。
6. **GA 之后退役旧能力**：pre-GA 的直接修订姿态止于 `v1.0.0` promotion；此后 active 行只能按 [`release-readiness.md` §5.1.1](./release-readiness.md) 的两阶段退役（`active → deprecated → retired`、最短观测窗口、混合版本互通证据）推进，`retired` 也不删除历史解释所需的 row 与 schema bytes。

### 9.5 模型概括

Arkret 的兼容性模型是"**一个几乎不变的代际判别值 + 多个正交的、fail-closed 的协商面 + 永不重写的历史字节**"。新旧实现互通不靠猜测对方版本，靠的是每个差异维度都有自己的声明载体、判定时机与稳定失败语义；密文不因版本差异不可解，靠的是解密所需的全部输入都被签名引用钉死、不给任何一方留下第二种解释路径。
