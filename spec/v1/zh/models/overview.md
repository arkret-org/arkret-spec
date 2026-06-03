---
title: Overview
sidebar:
  order: 0
status: candidate
normative: true
stability: v1
updated: 2026-05-25
see_also:
  - models/common-fields.md
  - models/realm-and-space.md
  - models/flow-and-message.md
  - conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Contrix 的核心数据模型是一张以 Realm 为边界、以标准对象和开放 Morph 共同组成的可审计协作图。本目录定义协作图中所有标准对象的语义、字段、行为与互相之间的关系。

阅读建议：

- 第一次接触请按本文 §3 设计原则与 §2 typed-id 一览建立总览。
- 字段细节、必填性、枚举值集中在 [`common-fields.md`](./common-fields.md)（公共字段）与各对象自己的"字段"小节。
- 每个对象在 `models/` 下都有唯一权威文件；文件之间不重复 normative 规则，只在必要处交叉引用。

## 2. Typed ID 一览

每个 Contrix 对象的种类由 `id` 的 typed-id 前缀（`cx:<kind>:`）唯一决定，canonical object 上不再单独写 `type` 字段。下表是对象到详细文档的索引。

DID 的使用边界见 [common-fields.md §4.1](./common-fields.md#41-did-适用边界)：DID 标识 actor / principal / issuer / service / device 等主体，不替代 `cx:<kind>:` 对象 ID。

### 2.1 协作图核心对象

| Typed ID | 对象 | 说明 | 详情 |
| --- | --- | --- | --- |
| `cx:realm:` | Realm | security / sync / auth / E2EE 边界 | [realm-and-space.md](./realm-and-space.md) |
| `cx:circle:` | Circle | Realm 内子事件 / 子消息边界（子集成员 / 独立 history / 投递裁剪；可选独立 MLS group），对象通过 `scope_circle_id` 引用 | [circle.md](./circle.md) |
| `cx:space:` | Space | 产品结构容器与导航节点（project / folder / board / list / section ...），通过 `realm_id` / `default_realm_id` 解析安全边界 | [realm-and-space.md](./realm-and-space.md) |
| `cx:flow:` | Flow | 统一协作主对象（task / decision / incident / channel ...） | [flow-and-message.md](./flow-and-message.md) |
| `cx:message:` | Message | Flow `discussion` track 时间线消息 | [flow-and-message.md](./flow-and-message.md) |
| `cx:morph:` | Morph | 开放形态对象，承载扩展业务类型 | [morph.md](./morph.md) |
| `cx:relation:` | Relation | 一等关系对象（contains / replies_to / depends_on ...） | [relation.md](./relation.md) |
| `cx:actor_profile:` | Actor Profile | Actor 在协作图中的展示镜像 | [actor.md](./actor.md) |
| `cx:view:` | View | 投影定义（看板 / 列表 / 时间线 / graph / document ...） | [views.md](./views.md) |
| `cx:event:` | Event | 签名事件，reducer 输入与审计事实 | [event-and-patch.md](./event-and-patch.md) |

### 2.2 治理对象

| Typed ID | 对象 | 说明 | 详情 |
| --- | --- | --- | --- |
| `cx:policy:` | Policy | access / encryption / retention / federation / moderation 等策略 | [governance-objects.md](./governance-objects.md) |
| `cx:capability:` | Capability Definition | abstract capability definition reference（非签名 grant；签名 grant 用 `cx:grant:`）。真源见 [`id-kind-registry.json` `capability` 条目](../../artifacts/registry/id-kind-registry.json)。 | [governance-objects.md](./governance-objects.md) |
| `cx:grant:` | Capability Grant | 授权委派 | [governance-objects.md](./governance-objects.md) |
| `cx:invite:` | Invite | Realm 加入引导 | [governance-objects.md](./governance-objects.md) |
| `cx.schema.*` | Schema | 标准对象 / Morph type / facet / event 的结构与约束 | [governance-objects.md](./governance-objects.md) |

### 2.3 派生 / 私有对象

> 派生对象不是 canonical truth，由 client / SDK 从 Event 集合本地计算；schema 仅用于 wire 表示。

| Typed ID | 对象 | 说明 | 详情 |
| --- | --- | --- | --- |
| `cx:read_cursor:` | Read Cursor | actor-private 已读位置 | [private-objects.md](./private-objects.md) |
| `cx:notification:` | Notification | inbox projection | [private-objects.md](./private-objects.md) |

### 2.4 内容 / 媒体 / 扩展对象

| Typed ID | 对象 | 说明 | 详情 |
| --- | --- | --- | --- |
| `cx:blob:` | Blob | 由 Blob Store 管理的内容寻址数据，不参与协作图归约 | [extension-objects.md](./extension-objects.md) |
| `cx:applet:` | Applet | bot / bridge / portal / 集成服务（extension profile） | [extension-objects.md](./extension-objects.md) |
| Agent runtime | Agent | A2A / ACP 互通运行时 | [extension-objects.md](./extension-objects.md) |

### 2.5 辅助标识符

| Typed ID | 对象 | 说明 |
| --- | --- | --- |
| `cx:receipt:` | Event Batch Receipt | 可选审计 / 同步加速对象，不是 reducer 输入 |
| `cx:cell:`、`cx:cursor:`、`cx:anchor:` | 状态 / 同步原语 | 不是协作图对象；语义见 `authz/event-auth-state-resolution.md`、`sync/operations-sync.md` 与 `conformance/encoding.md` |

字段级、必填性、枚举值与 wire 约束统一以 [`common-fields.md`](./common-fields.md) 与各对象文件中的字段表为准。Schema 引用见 `artifacts/schemas/`，event/operation registry 见 `artifacts/registry/`。

### 2.6 对象关系总览

下图把核心 typed-id 之间的归属、容纳、引用、投影关系画成一张图。`cx:event:` 是事实根，所有共享对象都是 Event 集合在某个 reducer profile 下的物化结果。

```mermaid
flowchart TB
    Event["cx:event:<br/>签名事件（事实根）"]

    subgraph SP ["cx:realm: — security / sync / auth / E2EE 边界"]
        direction TB
        Space["cx:space:<br/>kind=board / list / ..."]
        Flow["cx:flow:"]
        Morph["cx:morph:"]
        Msg["cx:message:<br/>(discussion 时间线)"]
        Rel["cx:relation:"]

        Space -- "contains" --> Flow
        Space -- "parent_space_id（导航，可跨 Realm）" --> Space
        Flow -- "tracks.discussion" --> Msg
        Rel -. "from_ref / to_ref" .-> Flow
        Rel -. "from_ref / to_ref" .-> Morph
        Rel -. "from_ref / to_ref" .-> Space
    end

    Circle["cx:circle:<br/>(Realm 内子事件边界)"]
    Flow -. "scope_circle_id<br/>（窄化 effective scope）" .-> Circle

    View["cx:view:<br/>投影定义（不持有真相）"]
    View -. "投影" .-> Flow
    View -. "投影" .-> Space
    View -. "投影" .-> Msg

    Event ==> SP
    Event ==> Circle
```

读图要点：

- 实线箭头是结构归属或容纳关系；虚线是引用 / 投影 / scope 窄化。
- `cx:realm:` 是 federation/identity 硬边界——federation、policy、capability registry、Realm-default MLS 都以它为根。`cx:space:` 永远不是边界，Space metadata 由 `realm_id` 指向的 home Realm 授权。
- `cx:circle:` 是 Realm 内的子事件 / 子消息边界——子集成员 / 独立 history / 投递裁剪；在 E2EE Realm 或 policy 要求下还拥有独立 MLS group。`Flow.scope_circle_id` 指向 Circle 表示整个 Flow（所有 track）落在该 Circle scope。
- `cx:relation:` 是一等对象，跨对象语义 MUST 通过 Relation 表达，不藏在字段里。
- `cx:view:` 拥有投影定义的真相，但不持有被投影对象的协作事实。
- Discussion 想要独立 membership / history visibility / 投递裁剪或 E2EE 时，整个 Flow 通过 `scope_circle_id` 落在一个 [Circle](./circle.md)；不再有 per-track 安全边界。

## 3. 设计原则

### 3.1 Realm 边界与 Space 容器

每个 `cx:realm:` 都是 security/sync/auth/E2EE 硬边界——复制、权限、schema、policy、membership、history visibility、加密、federation policy 都以它为根。Realm 不承担产品导航树职责：结构性分组、项目、folder、看板、列、泳道、calendar bucket 等由独立的 **Space** 对象（`cx:space:`）承担，Space 永远不形成独立边界。

`security_class=high_assurance` 是 Realm 的可选标签，进一步收紧 federation policy 与默认审计/E2EE 选项。

Realm 之间 MAY 通过 `cx.realm.link` 形成显式 link graph（governance、discoverability、confidential_extension、mirror 等），但 v1 不定义通用 Realm hierarchy。membership、capability、history visibility、schema、policy 和 encryption key 不因 link 级联；任何继承都必须由目标 Realm 显式声明。详细规则见 [`realm-links.md`](./realm-links.md)。

Space 层级通过 Space 自己的 `parent_space_id` + `cx.space.parent` 表达，可跨 Realm 做导航，但不得传播 Realm membership、capability、history visibility 或 E2EE key。详细规则见 [`space-hierarchy.md`](./space-hierarchy.md)。

### 3.2 Flow 承载主语义

同一个协作主题由一个 Flow 表达；track primary 解析规则与 track 配置决定默认入口和能力面。

标准对象本身表达主语义：

- `flow`：统一协作主对象。它承载 `metadata.title` / `metadata.summary` / `content` 等基础字段，并通过 track primary 解析规则决定默认进入哪个 track。
- `message`：Flow `discussion` track 中的消息。
- `morph`：开放形态对象，用于业务扩展、未知类型和实验对象。
- `space`：Realm 内部的结构容器（`kind=board` / `kind=list` / 其他 profile 注册的形态）。

标准对象 MAY 暴露 schema/profile 已声明的 `facets` 来辅助展示或查询，但它的核心职责不依赖 facets 才成立。实现不得要求标准对象先声明 facet 才能承认其主语义。

### 3.3 Morph 是开放对象

`morph` 表示协议未固化为标准类型的协作对象，适合插件、未来标准类型实验、外部系统镜像、低频弱互操作扩展数据。

Morph 的可见能力可以由 Realm schema / Morph profile 声明，并通过 `facets` 暴露给 View、UI、本地搜索或插件。实现遇到未知标准类型 SHOULD fail closed；遇到未知 Morph facet SHOULD 保留数据，但不得让未知 facet 绕过 schema、capability、policy 或 encryption 约束。

Facet 字符串本身不是规范性 reducer 或授权来源。任何会改变写入权限、状态转换、排序、包含关系、事件有效性或跨实现 wire 行为的能力，MUST 由明确 schema/profile/event kind/capability action 定义。详情见 [morph.md](./morph.md)。

### 3.4 Relation 是一等对象

跨对象语义 MUST 使用 `relation` 表达，而不是藏在对象字段里。Relation 连接的是对象引用：标准字段 `from_ref` / `to_ref` 可以指向 `flow`、`message`、`morph`、`space`、`realm` 或 `blob` 的 `cx:<kind>:` typed ID。Actor 端点没有对应的 actor typed-ID 对象（actor 的身份根是 DID，协作图展示镜像是 `cx:actor_profile:`）；因此当端点是 Actor 时，`from_ref` / `to_ref` 直接使用该 actor 的 DID（principal），而不是某个 actor typed-ID（见 [common-fields.md §4.1](./common-fields.md#41-did-适用边界)）。

跨 Realm 引用规则、结构性 Relation 的本地约束（如 `contains` / `belongs_to` 不可跨 Realm）见 [relation.md](./relation.md)。

### 3.5 Event 是事实

所有协作变化最终都落为签名 `event`。Event 是审计根和 reducer 输入。当前态只是 Event 集合在某个 reducer profile 下的物化结果。详情见 [event-and-patch.md](./event-and-patch.md)。

### 3.6 View 是投影定义

`view` 是一等协议对象，但它拥有的是投影定义的真相，而不是被投影对象的协作事实。它定义查询、过滤、排序、分组、renderer、布局、可见字段和共享 saved view 配置。

View 不得发明对象能力，也不得持有对象状态的唯一副本；对象能力来自对象类型、schema/profile 和 capability，facets 只作为已声明能力的查询与投影 hint。详情见 [views.md](./views.md)。

### 3.7 Schema 演进

标准类型演进 MUST 遵守：

- 新字段优先 optional。
- 既有字段不得静默改变语义。
- reducer 和客户端 MUST 保留未知字段，但 MUST NOT 让未知字段绕过 capability、schema、policy 或加密约束。
- UI 遇到未知 Morph type SHOULD 降级为 generic Morph card。
- 标准对象不得阻止 Realm 定义自定义 Morph type。

## 4. 阅读路径（Reading Paths）

按目标层面索引：

| 关注层面 | 起点 |
| --- | --- |
| 协作图整体结构 / 标准对象一览 | 本文 §2-§3 |
| 公共字段、lifecycle、reducer 总则 | [common-fields.md](./common-fields.md) |
| Realm 边界、看板 / 列 / 容器、位置语义 | [realm-and-space.md](./realm-and-space.md) |
| Flow / track / discussion / Message | [flow-and-message.md](./flow-and-message.md) |
| Morph 类型、facets、扩展 | [morph.md](./morph.md) |
| Relation 基数、跨 Realm、冲突 | [relation.md](./relation.md) |
| Actor、Actor Profile | [actor.md](./actor.md) |
| Schema / Policy / Capability Grant / Invite | [governance-objects.md](./governance-objects.md) |
| Read Cursor / Notification | [private-objects.md](./private-objects.md) |
| Event Envelope / Proof / Patch / Receipt / reducer | [event-and-patch.md](./event-and-patch.md) |
| Applet / Agent / Blob | [extension-objects.md](./extension-objects.md) |
| Content Block（消息正文 / 富文本 / 媒体） | [content-types.md](./content-types.md) |
| 投影 / 看板 / 时间线 / graph / document View | [views.md](./views.md) |
| Realm link graph、显式继承、治理关系 | [realm-links.md](./realm-links.md) |
| Space 产品结构层级、跨 Realm 导航 | [space-hierarchy.md](./space-hierarchy.md) |

## 5. 规范性引用

- 标准 event type 注册表见 `../conformance/schema-registry.md`。
- Reducer conformance vector 见 `../conformance/conformance-vectors.md`。
- Schema evolution 测试见 `../conformance/conformance-profiles.md`。
- Move / Anchor / Lattice / capability 校验规则见 `../authz/event-auth-state-resolution.md`。
