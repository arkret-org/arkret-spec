---
title: Cokret Protocol
status: candidate
normative: true
stability: v1
updated: 2026-06-10
see_also:
  - spec-map.md
  - overview/architecture.md
  - overview/glossary.md
  - conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](./conformance/normative-language.md) 解释；仅大写形式具规范约束力。

本规范权威文本为 `zh/` 下中文；`en/` 仅提供说明性入口，非规范源。`artifacts/` 下的机读契约为语言中立，跨语言共享。

## 1. 范围（Scope）

`cokret-spec` 是 **Cokret v1 去中心化协作协议规范**。其核心不是界面，而是"可验证协作事实 + 可投影的对象语义"：

- 身份主键：DID principal
- 数据主语（canonical 对象清单）：Realm / Circle / Space（含 Board/List）/ Strand / Message / Relation / Morph / Event / View / Capability
- 审计主语：signed Event + per-actor event chain
- 权限主语：capability
- 呈现主语：views / projection
- 扩展承载：Morph（同时是上面 canonical 对象清单中的开放对象）+ schema / profile-defined facets

> 上面"数据主语"是本规范的 canonical 对象清单；§6 与其他章节引用对象集合时以此为准。Morph 既是 canonical 对象清单中的开放对象，也充当 schema / profile 扩展承载，两处指的是同一对象，不是两类东西。

> **关于 “v1”（消歧）**：本规范树的 `v1/` 目录、`stability: v1` 以及 `ck.*.v1` 标识符中的 `v1`，指的是**协议代际**（对应 `protocol_version="1.0"` 与 schema id / event kind 后缀承载的 wire 级版本），**不是 URL 路径版本号**。HTTP path 不含任何版本段（不存在 `/v1/`、`/api/v1`），版本是元数据，通过 `*.describe` 协商；规则见 [`sync/api-conventions.md` §11](./sync/api-conventions.md)。破坏性变更通过新增 event kind / schema id 承载，**从不发生“整面切 v2”**，因此 `v1` 后缀是长期锚点，不应被移除。

### 1.1 5 分钟读法

先按下表理解对象边界，再进入字段和 event 细节：

| 问题 | Cokret 对象 | 一句话边界 |
| --- | --- | --- |
| 谁在做事？ | Principal / Actor | Principal 是 DID 身份根；Actor 是该 Principal 在 Realm 内产生 Event 的参与身份。 |
| 这批协作事实归谁管？ | Realm | 权限、成员、历史可见性、E2EE、同步和联邦都以 Realm 为根。 |
| Realm 内要给一部分人单独的成员、历史和加密边界？ | Circle | Circle 是 Realm 内的子事件边界；复用父 Realm 的 federation / policy / capability，只裁剪成员、history、投递与查询，必要时启独立 MLS group。 |
| 用户界面怎么组织项目、看板和列表？ | Space | Space 是导航 / 容器，不拥有成员、policy 或加密组。 |
| 一件事、一个任务、一个话题或一个决策放哪里？ | Strand | Strand 是统一协作主对象；正式内容在 synthesis，讨论在 discussion。 |
| 聊天消息是什么？ | Message | Message 只属于某个 Strand 的 discussion track。 |
| 对象之间如何表达包含、依赖、回复、指派？ | Relation | 跨对象语义用 Relation；不能把关系藏在自由字段里。 |
| 怎么看成看板、表格、聊天、时间线、图？ | View | View 只定义投影和交互入口，不持有被投影对象的真相。 |
| 非标准业务对象放哪里？ | Morph | Morph 是扩展缓冲层；schema/profile 决定字段与能力，facet 只做 UI / 查询提示。 |

## 2. 非目标（Non-Goals）

Cokret v1 明确不把以下内容作为基础互操作必需项：

- 聊天消息作为唯一协议对象根
- 房间状态机作为全协议统一底座
- 全网共识链
- 强绑定某个 SaaS UI 外壳
- 以 embedding、向量库替代协议真相源
- 以高复杂字段级/字节级 ACL 作为第一阶段互操作要求

> 上述非目标的肯定式表述（"房间不是唯一世界模型、消息也不是唯一原子单元"等架构取向）见 [`overview/architecture.md` §5](./overview/architecture.md)；两处指同一组取舍，一为否定式边界、一为肯定式取向。

## 3. 文档地图（Document Map）

[spec-map.md](./spec-map.md) 是总目录。README 仅保留顶层入口与实施路径，避免因 profile 增长变成长清单。

### 3.1 实施清单（Implementation Checklist, _informative_）

1. 完成 DID 与服务发现，建立 principal/service 绑定。
2. Realm 创建后锁定 schema 与策略基线。
3. Event-first 写入并做初始 auth state 校验。
4. 客户端执行 `event-auth-state-resolution` 收敛。
5. 使用 snapshot / frontier 建立快速重建路径。
6. 讨论类空间先验 MLS state，再决定是否解密展示。
7. reducer 产出 canonical projection，UI 只消费 projection。
8. 失败场景进入可恢复退化状态（如 `decryption_pending`、`state_mismatch`、`projection_incomplete`）；这些标准退化状态 / 错误标识的 canonical 语义详见 [`artifacts/registry/error-code-registry.json`](../artifacts/registry/error-code-registry.json)。

### 3.2 推荐阅读顺序（Suggested Reading Order, _informative_）

完整推荐阅读顺序由 [spec-map.md §2](./spec-map.md) 单点维护，避免双清单各自漂移。新读者先看以下核心入口即可起步：

- `overview/architecture.md`：架构、服务角色、部署与信任边界。
- `overview/glossary.md`：Principal / Actor / Organization / Realm / Event / Principal Server 等术语。
- `overview/current-model.md`：v1 统一对象模型的关键设计决定（Strand 统一、Board/List 容器化、track 模型、E2EE 边界、agent 落点）。
- `models/overview.md`：对象总览、typed-id 一览、设计原则。

其余身份、授权、同步、加密、扩展等专项文件的推荐顺序见 spec-map §2。

### 3.3 目录结构分层

- 总览与决策
- 身份、组织与隐私
- 对象模型与交互
- 授权、治理与状态
- 同步、服务与联邦
- 发现、目录与用户状态
- 加密、设备与媒体
- 扩展、Agent 与集成
- Schema、编码与一致性

## 4. 关键设计决策

### 4.1 身份

- `principal_id = DID URI`，Handle 只作为可迁移的人类可读入口。
- Resolver policy 必须声明可用 DID method、默认 method、信任根与 fail-closed 规则。
- **v1 core 默认 principal DID method 为 `did:webvh`**：在 `did:web` 之上叠加 `did.jsonl` 历史链 + SCID + witness evidence，提供可审计的 DID 控制历史，抵御 DNS / TLS 单点失陷。
- `did:webvh` 是 v1 core 默认 principal DID method 与默认 service DID method；`did:web` 仅作为显式 no-history service profile 与 **`personal_node` deployment profile 的可选 principal method**；`did:webvh` hosting 暂时不可达时只允许 [`identity/identity-did.md`](./identity/identity-did.md) 定义的 cache-only degraded mode，MUST NOT live fallback 到 `did:web`；缓存有效期 / TTL 耗尽后 MUST fail-closed（见 [`identity/identity-did.md` §3.4](./identity/identity-did.md)），不得无限期缓存信任旧 DID 文档。
- 临时、测试、设备、邀请、bootstrap 使用 `did:key`；MUST NOT 作为默认长期主身份。
- 钱包绑定（`did:pkh`）、AT Protocol 互通（`did:plc` adapter）、KERI 系列等是 interop extension profile，不属于 v1 core 互操作必需。
- DID 文档、history chain 与 method evidence 需按各自 method 的 verifier 校验。

### 4.2 对象模型

- 所有持久协作修改必须是 signed Event。
- 所有共享状态由授权 Event 集合 reducer 收敛后生成。
- Realm 是权限、成员、schema、policy 的边界。
- Strand 为统一协作对象，默认入口由 track primary 解析规则表达，同一 `strand_id` 下可切换默认 track。
- Morph 是扩展载体，不单独定义核心能力和排序语义。
- `notification` 是投影用途，不是 canonical truth。

### 4.3 看板与会话

- 看板定义：`Board Space -> List Space -> Strand`。
- 会话定义：`Strand(discussion track) -> Message`。
- `ck.strand.tracks.update` 是 track 配置（启用 / 关闭 / 切换 primary / 修改 profile）的唯一写入路径，不复制对象、不迁移历史。
- Track 不携带独立 access；整个 Strand 共享单一 effective scope（由 `Strand.scope_circle_id` 决定）。需要独立成员、历史或 E2EE 边界时，把整个 Strand 通过 `scope_circle_id` 落在一个 [Circle](./models/circle.md)，或拆为两个 Strand + `confidential_discussion_of` Relation（见 [`models/circle.md` §7.2](./models/circle.md)）。

### 4.4 同步与真相模型

- signed Event Envelope 是发布最小单位，actor event chain 是重放和可验证基础。
- Principal Server / Sync Service 是同步基础设施，不是唯一真相源。
- 搜索、inbox、notification、projection 默认由客户端或 SDK 派生。
- 未加密私有正文不得发送到未授权第三方服务。
- Event 写入具备幂等性；撤回通过 redaction 收敛，不等于全局物理删除。

### 4.5 授权

- 权限采用 capability 模型，授权与能力必须显式、可验证、可撤销。
- accountable actor 需追溯 `responsible / guardian / controller`。
- 高风险动作支持 approval constraint 与治理式审批约束。
- `handle` 不承担权限主键作用，授权主体以 DID 或 selector 条件表述。
- 消息、撤回、Strand 管理、排序等动作均有独立动作语义。

## 5. 规范语言与实现声明

本规范的强制关键字按 RFC 2119 / RFC 8174 语义解释，完整集合（含否定与可选形式）以 [conformance/normative-language.md](./conformance/normative-language.md) 为权威来源：

- `MUST` / `MUST NOT` / `REQUIRED`
- `SHOULD` / `SHOULD NOT` / `RECOMMENDED`
- `MAY` / `OPTIONAL`

仅大写形式具规范约束力；全文使用的 `MUST NOT` / `SHOULD NOT` 等均属上述集合。

各实现声明支持范围时需同时给出：

- `protocol_version`（canonical 字段值固定为字符串 `"1.0"`；wire / describe 响应 MUST NOT 写成 `1.0.0` 或 `v1.0.0`。术语主条目见 [`overview/glossary.md` §2](./overview/glossary.md)）
- conformance profile（如 `ck.profile.full_client.v1`）
- schema / reducer profile（如 `ck.schema.event.v1` 与 `ck.profile.core_event_store.v1`）
- 尺度与分页边界（默认见 `conformance/scalability-constraints.md`）

> `protocol_version` 字段值（`"1.0"`）与发布 / release tag（`v1.0.0`，见 [`overview/release-readiness.md`](./overview/release-readiness.md)）是两个不同维度：前者是 wire-level 协议大版本标识，后者是仓库发布线标签。两者 MUST NOT 互换填入对方位置。

新增能力优先通过 profile / 扩展章节 / registry 条目引入。

## 6. 当前覆盖范围

- 身份、handle、组织主体、服务 DID 与进阶披露
- 对象覆盖以 §1 的 canonical 对象清单为准：Realm / Circle / Space（含 Board/List）/ Strand / Message / Relation / Morph / Event / View / Capability
- 字段级结构、必填性、枚举与约束
- capability、delegation、claim 条件、policy 与 moderation policy
- Event-first 发布、Principal Server 同步、客户端查询与投影
- MLS E2EE、设备验证、WebRTC、blob 与媒体
- Applet、Agent 互通、Directory、Federation、Sovereign deployment

## 7. 摘要（Summary）

Cokret 的目标是统一协作对象语义，建立"可验证审计 + 长期可恢复"的协作基础设施，而不是绑定聊天协议外壳。
