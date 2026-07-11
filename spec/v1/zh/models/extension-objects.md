---
title: Extension Objects
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文为 Arkret 协作图中**通过扩展 profile 接入的对象类型**提供模型层入口：

- **Applet**（`ak:applet:`）：bot / bridge / portal / 集成服务（extension profile，非 v1 core 互操作必需）。
- **Agent**：A2A / ACP / 外部 agent 协议互通运行时。
- **Blob**（`ak:blob:`）：由 Blob Store 管理的二进制数据，不参与协作图归约。两种 wire 形态：`ak:blob:<uuid>`（metadata row id）与内容寻址特殊形态 `ak:blob:<digest-suite>:<hex>`（v1 为 `sha256` 或 profile-gated `blake3`，见 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)）。

每个对象的完整规范由对应专项文档承担；本文只给出对象语义概述、字段索引与跳转。

公共字段、lifecycle、reducer 总则见 [`common-fields.md`](./common-fields.md)。

## 2. Applet

### 2.1 概念

Applet 是受注册、受授权、可审计的集成服务。它可以：

- 作为 bot 参与 Realm
- 桥接外部网络（IRC / Slack / Discord / GitHub 等）
- 创建和管理 Ghost Actor
- 管理 portal realm
- 接收 Arkret 事件交易
- 把外部事件转换为 Arkret event
- 在获得明确授权时以受托 agent / device 方式执行操作

> **状态：extension profile**。Arkret v1 core 互操作 **不要求** 实现 Applet profile；声称 v1 core 的实现可以完全不接 Applet，仅通过 capability + actor 模型表达 bot / bridge / agent。`ak.profile.applet_service.v1` 视为可选 extension（见 `artifacts/profiles/conformance-profiles.json` 的 `profile_tiers.extension_profile_implementation`）。

### 2.2 关键对象

- `ak:applet:<uuid>`：Applet 对象 typed ID。
- `ak.applet.registration`：Applet 注册 event；完整字段与校验规则的唯一真源是 [`../extensions/applet-schema.md`](../extensions/applet-schema.md)。
- **Applet Service**：运行集成逻辑的服务端进程（独立 service DID）。
- **Applet Controller**：管理该 Applet 的主体（组织、开发者、企业管理员）。
- **Bot Actor**：Applet 的主要可见 Actor，可以加入 Realm、被 mention、发送消息或执行自动化。
- **Ghost Actor**：外部网络用户在 Arkret 中的镜像 Actor；MUST 带有 `accountable_principal_ids` 指向 Applet controller，并用 `profile_fields.external_ref` 记录外部网络来源；MUST NOT 伪装成人类 DID。
- **Portal Realm**：外部网络 location 在 Arkret 中的镜像 Realm。

### 2.3 行为约束

- Applet **不**自动拥有全网权限。
- Applet 的每个写入仍需签名和 capability。
- Applet namespace 只表示"该 Applet 可声明或接收这些对象"，不等于权限通过。
- Ghost Actor 必须是可审计 Actor，MUST NOT 伪装成人类 DID。
- Applet 对 Portal Realm 写入仍需显式 Realm link、目标 Realm 的 explicit capability、目标 Realm 的 Policy Server / moderation 检查、E2EE 边界提示（如 bridge 到非 E2EE 外部系统）。详见 [`realm-links.md`](./realm-links.md)。

### 2.4 详细规范

- 整体架构、namespace 模型、事件交易、Ghost Actor / portal realm 设计：[`../extensions/applet-integration.md`](../extensions/applet-integration.md)。
- Applet schema 与 OpenAPI binding：[`../extensions/applet-schema.md`](../extensions/applet-schema.md)。
- MIMI Provider Facade（外部协议互通）：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)。
- Applet policy（`policy_type=applet`）：[governance-objects.md §3](./governance-objects.md)。

## 3. Agent

### 3.1 概念

Agent 是 Arkret 协作图中以 **A2A** / **ACP** 等外部 agent 协议进行任务编排的可委派运行时。它可以：

- 在 Realm 内以独立 Actor 身份执行受托动作。
- 接收外部 agent 协议事件并把结果落点到 Strand / Message / Morph。
- 通过 capability + accountability 链表达"哪个 principal 委派 / 谁负责"。

Agent 的对象身份与 Applet 类似（独立 DID 或受托 device DID），但运行时面向 agent 协议互通，而非外部网络桥接。

### 3.2 关键对象

- `actor_kind=agent` 的 Actor / Actor Profile（详见 [actor.md §3](./actor.md)）。
- `ak.profile.agent_runtime.v1` extension profile（详见 [`../conformance/conformance-profiles.md`](../conformance/conformance-profiles.md)）。
- Agent policy（`policy_type=agent`）：见 [governance-objects.md §3](./governance-objects.md)。
- `notification_type=agent`：见 [private-objects.md §3](./private-objects.md)。

### 3.3 详细规范

- A2A / ACP / external agent protocol handoff 已退出协议面；reserved 名字空间见 [`../extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)。
- Agent 落点（结果如何写回 Strand / Message / Morph）：[`../overview/current-model.md` §8](../overview/current-model.md)。

## 4. Blob

### 4.1 概念

Blob 是 Arkret 中由 **Blob Store** 管理的内容寻址数据：图片、视频、文件、音频、缩略图等。Blob 是协议中的**内容层对象**，**不参与协作图归约**——它的生命周期、加密、缩略图、权限、保留策略由 media / blob 子系统单独管理。

Blob 在协作图中通过 typed blob ref 引用——内容寻址引用使用 `ak:blob:<digest-suite>:<hex>`，其中 suite MUST 是 [`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json) 对当前 profile 为 active 的 `sha256` 或 `blake3`；metadata row 引用使用 `ak:blob:<uuid>`：

- Message `ak.content.image` / `ak.content.video` / `ak.content.audio` / `ak.content.file` 中的 `blob_ref`。
- Strand `content` Content Block 中的引用。
- `Realm.avatar_blob_ref` / `Space.avatar_blob_ref` / `actor_profile.avatar_blob_ref`。
- Relation `attached_to` 指向 blob 的边。

### 4.2 行为约束

- Blob 自身**没有协作图 reducer**：它的写入路径是 Blob Store API（authenticated media），不是 Event Envelope。
- 每个 blob 的引用都必须满足 Realm media policy 与 authenticated media 校验。
- E2EE Realm 中缩略图 SHOULD 由客户端生成并加密上传；服务端生成缩略图前必须被声明为 plaintext-visible service。
- URL 预览、外部资源热加载受 [`content-types.md` §9](./content-types.md) 与 [`../crypto-media/media-and-blob.md`](../crypto-media/media-and-blob.md) 约束。

### 4.3 详细规范

- Blob metadata、thumbnail、authenticated media、asset privacy policy：[`../crypto-media/media-and-blob.md`](../crypto-media/media-and-blob.md)。
- Content Block 中的 blob 引用：[content-types.md](./content-types.md)。
- Media policy（`policy_type=media`）：[governance-objects.md §3](./governance-objects.md)。

## 5. 规范性引用

- 公共字段：[common-fields.md](./common-fields.md)。
- Applet 完整规范：[`../extensions/applet-integration.md`](../extensions/applet-integration.md)、[`../extensions/applet-schema.md`](../extensions/applet-schema.md)。
- Agent 互通：当前 reserved，见 [`../extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)。
- MIMI Provider：[`../extensions/mimi-interop.md`](../extensions/mimi-interop.md)。
- Media / Blob：[`../crypto-media/media-and-blob.md`](../crypto-media/media-and-blob.md)。
- Conformance profiles：[`../conformance/conformance-profiles.md`](../conformance/conformance-profiles.md)。
