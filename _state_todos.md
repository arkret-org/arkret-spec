# state_key 消灭与 MIMI 借鉴：任务计划

> 起草日期: 2026-05-07
> 范围: Contrix v1 spec（`spec/v1/zh/` + `spec/v1/artifacts/`）
> 决策: **彻底移除 envelope 上的 `state_key` 字段**；把所有 facet 拆成独立 kind；把 subject 移到 payload 具名字段；schema registry 声明每个 state kind 的 cardinality 与 subject_field。
> 借鉴 MIMI: component-typed policy（component_type / version / criticality）、MLS-bound state、显式 consent。

## 决策摘要

1. **消灭 `state_key`**：envelope 不再有此字段；reducer 主键为 `(space_id, kind, subject?)`，subject 由 schema 声明的 payload 字段派生。
2. **per-facet kind**：`cx.space.policy.set` → `cx.space.<facet>.set` × N；`cx.space.lifecycle.set` → `cx.space.<state>.set` × 4。`cx.mimi.room_binding`、`cx.space.upgrade` 等 subject 进 payload 具名字段。
3. **借鉴 MIMI**：每个 state kind 在 schema 声明 `component_type` (URI)、`component_version` (int)、`criticality` (required/optional/ignore)。未识别 component 不再一刀切 fail-closed，按 criticality 分级处理。
4. **E2EE Space 状态收紧**：state event 必须绑定 MLS GroupContextExtensions 中的 `cx_state_root`，由 MLS epoch 唯一定权威，不再做独立 state resolution。
5. **Space Host 模型**：**待决策**（peer-mesh / hub-writer / 混合 profile），未决前不动 federation/state-resolution 架构。
6. **Consent state machine**：新增 `cx.consent.*` event family，与 capability/invite 正交。

## 标记说明

- `[ ]` 未完成
- `[~]` 进行中 / 部分完成
- `[x]` 已完成
- `[!]` 阻塞 / 等决策
- 🅿 单文档 / 单 artifact 可并行
- 🔒 改 canonical schema/registry，触发下游同步
- ⚠ wire-breaking，必须在协议发布前完成

## 基线

- 起点：`python tools/artifact_pipeline.py check` 通过：110 event kinds、34 schemas、36 typed ID kinds、83 operations、48 profiles。
- 起点：`spec/v1/zh/` 下 20 个文件出现 `state_key`，`spec/v1/artifacts/` 下 8 个文件出现 `state_key`。
- 完成定义：所有 wire artifact / spec / fixture 中不再出现 envelope-level `state_key` 字段；artifact pipeline lint 通过；新 per-facet kinds 在 registry 注册并被 spec 引用。

## Phase 1 ⚠ 🔒 — 消灭 `state_key`，拆 per-facet kind

### 1.A 注册新 kinds + 弃用旧聚合 kind

| # | 状态 | 任务 |
|---|---|---|
| 1.A.1 | `[x]` | 在 contract-catalog.json 注册 12 个 policy facet kinds（采用 `state_key_replaces` 中已草拟的命名：`cx.space.policy`/`cx.space.join_rule`/`cx.space.history_visibility`/`cx.space.discovery`/`cx.space.policy_server`/`cx.space.policy_components`/`cx.space.history_sharing_policy`/`cx.space.asset_privacy_policy`/`cx.space.moderation_policy`/`cx.space.plaintext_visible_services`/`cx.space.media_service`/`cx.space.schema`） |
| 1.A.2 | `[x]` | 新增 `cx.space.inheritance_policy`（state_cardinality=per_subject, subject_field=`payload.parent_id`） |
| 1.A.3 | `[x]` | 新增 4 个 lifecycle kinds：`cx.space.archive`/`cx.space.freeze`/`cx.space.tombstone`/`cx.space.destroy` |
| 1.A.4 | `[x]` | 硬移除 `cx.space.policy.set`、`cx.space.lifecycle.set`（v1 未发布；`tools/artifact_pipeline.py generate` 已同步生成 registry） |
| 1.A.5 | `[x]` | `cx.mimi.room_binding`：state_subject_field=`payload.mimi_room_uri` 注册到 contract-catalog；schema 同步移除 state_key 必填 |
| 1.A.6 | `[x]` | `cx.profile.create/update`：state_subject_field=`payload.object.id` 注册；schema 同步 |
| 1.A.7 | `[x]` | `cx.space.inheritance_policy`：state_subject_field 修正为 `payload.parent_space_id`（与现有 payload schema 字段名一致） |

### 1.B schema 改动 ✅

| # | 状态 | 任务 |
|---|---|---|
| 1.B.1 | `[x]` | `event-schema.json`：移除 envelope 顶层 `state_key` 字段定义；移除所有 `(kind, state_key)` 条件分支；改为按 kind 路由 payload schema |
| 1.B.2 | `[x]` | 12 policy facet kind 的 payload 分发：`plaintext_visible_services` 走自己的 typed payload；其余 11 个走 generic `state_payload`（typed payload 进 Phase 2 单独做） |
| 1.B.3 | `[x]` | 4 个 lifecycle kind 已各自路由到 `space_archive_payload` / `space_freeze_payload` / `space_tombstone_payload` / `space_destroy_payload` |
| 1.B.4 | `[x]` | `cx.space.inheritance_policy` 路由到 `space_inheritance_policy_payload`（已有 `parent_space_id`）；registry subject_field 改名对齐 |
| 1.B.5 | `[x]` | `mimi-interop.schema.json` 移除 `state_key` 必填；spec 的 mimi_room_uri 已是 payload field |
| 1.B.6 | `[x]` | `event-envelope.schema.json` grep 后无 state_key 引用 |
| 1.B.7 | `[x]` | contract-catalog 加 `state_cardinality` / `state_subject_field` / `state_subject_type` 给所有原使用 state_key 的 kind（cx.space.create / member.state / flow.branch.member / capability.* / profile.* / mimi.room_binding / inheritance / child / parent / upgrade / organization） |

### 1.C spec markdown 更新 ✅

> 影响 20 个文件。所有改动完成；剩余 `state_key` 提及仅限"envelope 不携带 state_key"的描述性段落。

| # | 状态 | 文件 |
|---|---|---|
| 1.C.1 | `[x]` | `event-auth-state-resolution.md` — §4.1/§4.2 重写为 per-kind 表；§4.3 替换为 state slot 主键说明；§5/§5.1 示例去 state_key；§6 全部 `cx.space.policy.set (state_key=X)` 改为 `cx.space.<facet>`；§8 state event 列表重写为 cardinality 表；§10 redaction stub 增加 `state_subject` 字段；§12 例子去 state_key |
| 1.C.2 | `[x]` | `glossary.md` — State Resolution 条目改写；新增 State Slot / State Subject 条目 |
| 1.C.3 | `[x]` | `data-structures.md` — Event Envelope 表移除 `state_key` 行；改写 §405 state slot 派生描述 |
| 1.C.4 | `[x]` | `webrtc-signaling.md` — 全部转为 per-facet kind 引用 |
| 1.C.5 | `[x]` | `sovereign-deployment.md` — `cx.space.create` 例子去 state_key |
| 1.C.6 | `[x]` | `service-surface.md` — discovery 引用更新 |
| 1.C.7 | `[x]` | `operations-sync.md` — 24 处批量替换为 per-facet kind |
| 1.C.8 | `[x]` | `content-moderation.md` — 6 处转 per-facet kind |
| 1.C.9 | `[x]` | `mimi-interop.md` — `cx.mimi.room_binding` 例子去 state_key |
| 1.C.10 | `[x]` | `conformance-suite.md` — 4 处转 per-facet kind |
| 1.C.11 | `[x]` | `conformance-vectors.md` — 12 处 state_key 删除；`cx.member.state` payload 加 `actor_id`；`target_state_key` 改为 `target_event_id` |
| 1.C.12 | `[x]` | `encoding.md` — §9.5 重写为"复合 state subject"，移除"composite state_key"措辞 |
| 1.C.13 | `[x]` | `schema-registry.md` — `cx.space.policy.set inheritance:` 替换为 `cx.space.inheritance_policy` |
| 1.C.14 | `[x]` | `profiles-presence.md` — `cx.profile.create/update` 例子去 state_key |
| 1.C.15 | `[x]` | `discovery-directory.md` — discovery 引用更新 |
| 1.C.16 | `[x]` | `device-lifecycle.md` — push_route 改写为 composite subject 说明 |
| 1.C.17 | `[x]` | `media-and-blob.md` — 8 处转 per-facet kind |
| 1.C.18 | `[x]` | `policy-server.md` — 4 处转 per-facet kind |
| 1.C.19 | `[x]` | `object-model-standard.md` — `cx.flow.branch.member` 例子去 state_key |
| 1.C.20 | `[x]` | `space-hierarchy.md` — child/parent/inheritance/derived 全部改写 |

### 1.D fixtures + examples ✅

| # | 状态 | 任务 |
|---|---|---|
| 1.D.1 | `[x]` | `state-resolution-fixture.json` 重写：所有 candidate 改为 per-facet kind；引入 `state_slot` 描述字段；`cx.member.state` candidate 加 `payload.actor_id` |
| 1.D.2 | `[x]` | `mimi-interop-fixture.json` 移除 `state_key` |
| 1.D.3 | `[x]` | `conformance-profiles.json` — 5 个 profile 的 `required_event_kinds` 与 `required_state_keys` 合并为 per-facet kind |
| 1.D.4 | `[x]` | `contract-catalog.json` — 同步 generate（无残余 state_key） |

### 1.E 验证 ✅

| # | 状态 | 任务 |
|---|---|---|
| 1.E.1 | `[x]` | 全仓 grep 确认 `state_key` 仅在描述性 "envelope 不携带 state_key" 段落出现 |
| 1.E.2 | `[x]` | `python tools/artifact_pipeline.py check` 通过：125 event kinds (+15)、34 schemas、36 typed IDs、83 operations、48 profiles |
| 1.E.3 | `[x]` | event_kinds count 110 → 125 = +17 新 facet kinds − 2 旧聚合 kind |
| 1.E.4 | `[ ]` | `matrix-core-differences.md` 增加偏离说明（待办：留给 Phase 2 一起做） |

## Phase 2 🔒 — Component-typed policy + criticality（吸收 MIMI Room Policy Components）✅

| # | 状态 | 任务 |
|---|---|---|
| 2.1 | `[x]` | contract-catalog 中所有 42 个 state kind 添加 `component_type` (URI `cx.component.<facet-path>.v<n>`)、`component_version` (默认 1)、`criticality` (默认 `required`)。同时把 Phase 1 漏掉的 11 个 state kind 补足 `state_cardinality` + `state_subject_field`：`cx.flow.branch.history_visibility`、`cx.flow.branch.policy_components`、`cx.policy.rule`、`cx.device.authorized`、`cx.device.revoked`、`cx.device.list_update`、`cx.session.grant`、`cx.account.status`、`cx.view.create`、`cx.view.update`、`cx.view.reconcile` |
| 2.2 | `[x]` | `event-auth-state-resolution.md` 新增 §4.4 "Component 元信息与 Criticality"，解释 type/version/criticality、unknown-component 处理、`requirements.critical_extensions` 优先级、新增 component_type 注册流程、版本升级仪式 |
| 2.3 | `[x]` | `mimi-interop.md` §9 重写：拆为 §9.1 component_type 互译表（Contrix kind ↔ MIMI policy component URI）+ §9.2 criticality 互译；标注 Contrix-only / MIMI-only / 双向映射区别 |
| 2.4 | `[x]` | `glossary.md` 新增 Component / Component Type / Component Version / Criticality 4 条 |
| 2.5 | `[x]` | `python tools/artifact_pipeline.py check` 通过 |

## Phase 3 🔒 ⚠ — E2EE Space 状态绑定 MLS ✅

> **设计调整**：原计划提出新增 `cx_state_root` extension + 替换 state resolution。检视 `encryption-and-audit.md` §2.5 后发现 v1 已定义完整的 `application_state_ref` + `cx_app_state_ref` GroupContext extension（codepoint 0xCAFE）。Phase 3 改为收紧而非重写：把 MLS state binding 从 optional hardening 提升为 E2EE 必需，显式列出每个 frontier 必须覆盖的 component_types，并引入 "covered frontier" 与 "pending_mls_binding" 状态把 accepted state 与 MLS-bound state 拆开。

| # | 状态 | 任务 |
|---|---|---|
| 3.1 | `[x]` | `conformance-profiles.json`: `cx.profile.e2ee_client.v1` 直接 `inherits` `cx.profile.mls_state_binding.full.v1`（不再是 optional extension）；修复随之产生的循环继承；扩充 `cx.profile.mls_state_binding.full.v1` 增加 `policy_root_required_components` / `membership_frontier_required_components` / `capability_root_required_components` 三个 component_type 列表 |
| 3.2 | `[x]` | `crypto-media/encryption-and-audit.md` §2.5 重写：明确"E2EE Space MUST 声明 mls_state_binding.full"，每个 frontier 字段引用 profile 中声明的 component_type 列表；新增 §2.5.1 "Covered Frontier 与 Pending MLS Binding"；§2.5.1 旧"GroupContext Extension 定义"重编为 §2.5.2 |
| 3.3 | `[x]` | `event-auth-state-resolution.md` §11 加 `pending_mls_binding` 状态条目；新增 §8.1 "E2EE Space 的 State Binding" 章节做 cross-reference |
| 3.4 | `[x]` | `glossary.md` 新增 4 条：Application State Ref / Covered Frontier / Pending MLS Binding |
| 3.5 | `[x]` | `python tools/artifact_pipeline.py check` 通过 |

## Phase 4 [!] ⚠ — Space Host 单 writer 模型（**等决策**）

> **决策点**：(a) 保持 peer-mesh + state resolution；(b) 切到 hub-writer；(c) 混合 profile（sovereign 默认 hub，open federation 允许 mesh）。
> 决策前不开始本阶段任何子任务。

| # | 状态 | 任务（仅等待决策后启动） |
|---|---|---|
| 4.0 | `[!]` | **等待 (a)/(b)/(c) 选择** |
| 4.1 | `[ ]` | 视决策修改 `sync/federation.md`、`sync/sovereign-deployment.md` |
| 4.2 | `[ ]` | 视决策修改 state resolution 规则 |
| 4.3 | `[ ]` | 视决策定义 host migration 仪式 |

## Phase 5 🅿 — Consent state machine

| # | 状态 | 任务 |
|---|---|---|
| 5.1 | `[ ]` | 新增目录 `spec/v1/zh/consent/`，写一篇 `consent-model.md` |
| 5.2 | `[ ]` | 新增 event kinds：`cx.consent.grant`、`cx.consent.revoke`、`cx.consent.query` |
| 5.3 | `[ ]` | 在 invite / capability 流程中显式标注 consent 作为前置 gate |
| 5.4 | `[ ]` | 在 `mimi-interop.md` §10 把 MIMI consent 映射到这套 event family |
| 5.5 | `[ ]` | 验证 pipeline lint 通过 |

## 执行规则

1. 每个 Phase 完成后必须 `python tools/artifact_pipeline.py check` 通过，再开始下一个 Phase。
2. Phase 1 内部分 1.A → 1.B → 1.C → 1.D → 1.E 顺序执行；1.C 内部各文件可并行。
3. 不在 Phase 1 完成前开始 Phase 2/3。
4. Phase 4 阻塞，等显式决策。
5. 每完成一个 sub-task 标 `[x]`，并在末尾追加该 sub-task 简短说明（一行）。

## 完成 changelog

### 2026-05-07：Phase 3 完成（E2EE state 绑定 MLS GroupContextExtensions）

- 把 `cx.profile.mls_state_binding.full.v1` 从 `cx.profile.e2ee_client.v1` 的 optional_extensions 提升为 inherited 必需 profile。所有 E2EE 客户端默认实施 GroupContext extension binding；早期 base profile 实现废弃。
- 修复 profile 循环继承（mls_state_binding.full 原 inherits e2ee_client，现改为根 profile）。
- `cx.profile.mls_state_binding.full.v1` 增加三个 `*_required_components` 字段，显式列出每个 MLS frontier 字段必须覆盖的 component_type：
  - `policy_root_required_components`：13 个 Space-level policy/lifecycle facet
  - `membership_frontier_required_components`：cx.member.state、cx.flow.branch.member
  - `capability_root_required_components`：4 个 capability kind
- `crypto-media/encryption-and-audit.md` §2.5 重写：明确 binding profile 是 E2EE 必需而非 optional；frontier 字段从静态描述改为按 profile component 列表派生；§2.5.1 新增 "Covered Frontier 与 Pending MLS Binding"，区分协议层 accepted 与 MLS-bound accepted 两个状态。
- `event-auth-state-resolution.md` §11 加入第四种 event 状态 `pending_mls_binding`（仅 E2EE Space）；新增 §8.1 详述 E2EE state binding 的协议层规则与 covered frontier 语义。
- `glossary.md` 新增 4 条：Application State Ref / Covered Frontier / Pending MLS Binding。
- `python tools/artifact_pipeline.py check` 通过：125 event kinds、34 schemas、48 profiles。
- 关键语义变化：E2EE Space 中"撤销 / ban / policy 收紧"的实际生效点不再是协议层 accepted，而是 covered frontier；这把 MIMI Room Policy 的 MLS-bound state 模型完整融入 Contrix 的 E2EE 路径，同时保留非 E2EE Space 的普通 reducer + state resolution 路径。

### 2026-05-07：Phase 2 完成（Component-typed policy + Criticality）

- 所有 42 个 state event kind 添加三项 component 元信息：`component_type`（`cx.component.<facet-path>.v1`）、`component_version`（1）、`criticality`（`required`）。
- Phase 1 漏掉的 11 个 state kind（flow.branch.* / policy.rule / device.* / session.grant / account.status / view.*）补足 `state_cardinality` + `state_subject_field`。
- registry rules 增加一段说明 component 元信息和 criticality 语义。
- `event-auth-state-resolution.md` 新增 §4.4 详细解释 criticality 处理规则、`requirements.critical_extensions` 优先级、新 component 注册流程、版本升级仪式。
- `mimi-interop.md` §9 完全重写：Contrix component_type ↔ MIMI policy component IANA URI 显式互译表；criticality 三档（required/optional/ignore）双向映射到 MIMI must-understand/should-understand/silently-drop。
- `glossary.md` 新增 4 条术语：Component / Component Type / Component Version / Criticality。
- `python tools/artifact_pipeline.py check` 通过：125 event kinds、34 schemas、48 profiles。
- 现在 Contrix 的状态模型与 MIMI Room Policy 模型在概念层完全对齐（每个 state kind 是一个 typed component），同时保留 Contrix 自己的 capability + signature 授权根。

### 2026-05-07：Phase 1 完成（state_key 彻底消灭）

- **wire-breaking 变更**：envelope 顶层不再有 `state_key` 字段。
- **聚合 kind 移除**：`cx.space.policy.set`、`cx.space.lifecycle.set` 已硬移除（v1 未发布，无兼容包袱）。
- **新 per-facet kinds (17)**：
  - 12 policy facet：`cx.space.policy`、`cx.space.join_rule`、`cx.space.history_visibility`、`cx.space.discovery`、`cx.space.policy_server`、`cx.space.policy_components`、`cx.space.history_sharing_policy`、`cx.space.asset_privacy_policy`、`cx.space.moderation_policy`、`cx.space.plaintext_visible_services`、`cx.space.media_service`、`cx.space.schema`
  - 1 inheritance：`cx.space.inheritance_policy`（per_subject by `payload.parent_space_id`）
  - 4 lifecycle：`cx.space.archive`、`cx.space.freeze`、`cx.space.tombstone`、`cx.space.destroy`
- **registry 元信息**：每个 state event kind 添加 `state_cardinality`（singleton / per_subject）；per_subject 同时添加 `state_subject_field`（payload 字段路径）与 `state_subject_type`。覆盖 cx.space.* / cx.member.state / cx.flow.branch.member（复合 subject）/ cx.capability.* / cx.profile.* / cx.mimi.room_binding 等所有原使用 state_key 的 kind。
- **Reducer state slot 主键**：singleton 为 `(space_id, kind)`；per_subject 为 `(space_id, kind, value-of-state_subject_field)`。
- **Redaction stub**：增加 `state_subject` envelope-level 字段（reducer 在 redaction 前从 `state_subject_field` 派生），保证 stub 仍可定位 state slot。
- **schema 改动**：`event-schema.json` 移除顶层 state_key + 所有 (kind, state_key) 条件分支；按 kind 直接路由 payload schema。`event-payload.schema.json`、`mimi-interop.schema.json` 同步去 state_key。
- **20 个 zh markdown 全部更新**；2 个 fixture 重写；conformance profiles 重新组织为 per-facet kind。
- **Pipeline lint 通过**：125 event kinds (+15)、34 schemas、36 typed IDs、83 operations、48 profiles。
- **遗留**：`matrix-core-differences.md` 显式说明本次偏离的段落待补（计入 Phase 2）。
