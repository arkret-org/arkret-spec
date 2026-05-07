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
| 1.E.4 | `[x]` | `matrix-core-differences.md` 新增 §6 "State Model 与 Writer Model 的明确偏离"，覆盖 6 大偏离：state_key 移除 / 聚合 kind 拆分 / 双轨 state resolution / component-typed state / E2EE MLS state binding / holder-private consent |

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

## Phase 4 ⚠ 🔒 — Hybrid Writer Model（决策：c — 混合 profile）✅

> **决策**：每个 Space 在 create 时锁定 `space_writer_model ∈ {hub, peer_mesh}`，与 `encryption_profile` 同等地位（create-locked，不可后续 PATCH）。默认按 `federation_policy` 派生：`closed` / `restricted` / `quarantine` → `hub`；`open` → `peer_mesh`。两套语义共存，由 Space-level 选择。

### 设计原则

- `hub` 模型：每个 Space 有唯一 `space_host`（service DID）；所有 durable state event MUST 携带 host endorsement proof；state resolution fork 在协议层不可能（host 是单一 ordering authority）。fork = host 故障或攻击，按异常处理。
- `peer_mesh` 模型：当前 v1 行为不变；任何持有 capability 的 actor 可写入任意 state slot；并发 fork 由 §9.3 quarantine-on-concurrent-fork 算法处理。
- `host` 转移有显式仪式：smooth transfer = 现任 host + 新 host 双签；emergency transfer = `owning_organizations` 多数签名 + cooldown。
- 两个 profile：`cx.profile.space.hub_writer.v1` 与 `cx.profile.space.peer_mesh.v1`，作为 Space-level 强制 profile。

### 4.A 数据结构 + 注册（核心 wire 改动）

| # | 状态 | 任务 |
|---|---|---|
| 4.A.1 | `[x]` | `space.schema.json` + `data-structures.md` Space 表新增 `space_writer_model: enum(hub, peer_mesh)`，create-locked |
| 4.A.2 | `[x]` | `space_create_payload` 新增可选字段 `space_writer_model` 与 `space_host`（hub 必填）；缺省时按 `federation_policy` 派生 |
| 4.A.3 | `[x]` | event-kind-registry 新增 `cx.space.host`（singleton state，subject=null，hub-only）和 `cx.space.host.transfer`（per_subject by `payload.transfer_id`，hub-only） |
| 4.A.4 | `[x]` | event-payload schema 新增 `space_host_payload`、`space_host_transfer_payload`；包含 host service DID、standby_hosts、activation_timeout、transfer 双签证据等字段 |

### 4.B Host Endorsement Proof（新 proof 类型）

| # | 状态 | 任务 |
|---|---|---|
| 4.B.1 | `[x]` | `event-envelope.schema.json` proof 数组允许多 proof；定义 `proof.kind=host_endorsement` 类型，覆盖与 actor proof 相同的 canonical bytes，但 verification_method 是 host service DID |
| 4.B.2 | `[x]` | `event-auth-state-resolution.md` 新增 §3.3「Hub Writer Endorsement」：列出哪些 event kind 必须有 host endorsement（所有 durable state event 在 hub Space 中必须；ephemeral 与 actor_private 不要求） |
| 4.B.3 | `[x]` | reducer 规则：hub Space 中缺 host endorsement 的 state event MUST `proof_missing` reject；endorsement 是 reducer 接受的硬条件 |

### 4.C State Resolution 行为

| # | 状态 | 任务 |
|---|---|---|
| 4.C.1 | `[x]` | `event-auth-state-resolution.md` §9 增加分支：hub Space 的 state resolution 期望 0 fork；fork 出现 = host 故障/分裂，整个 state slot quarantine 直到 host 状态澄清 |
| 4.C.2 | `[x]` | hub Space 的 §9.3 quarantine-on-fork 仍执行，但语义从"协议常态"转为"host 异常诊断" |
| 4.C.3 | `[x]` | peer_mesh Space 行为无变化 |

### 4.D Host 转移仪式

| # | 状态 | 任务 |
|---|---|---|
| 4.D.1 | `[x]` | `cx.space.host.transfer` 定义两种 mode：`smooth`（current host + new host 双签 + replacement_at frontier） |
| 4.D.2 | `[x]` | `emergency` mode：current host 失联超 `activation_timeout_ms`，由 `owning_organizations` ≥1/2 签名启动；附带 incident_ref |
| 4.D.3 | `[x]` | activation frontier 后所有新 endorsement 由 new host 签发；旧 host 的 endorsement 在 frontier 后无效 |
| 4.D.4 | `[x]` | `cx.space.host.transfer` 必须 ≥1 个 host endorsement（smooth：双方；emergency：governance quorum） |

### 4.E Profile + 默认派生

| # | 状态 | 任务 |
|---|---|---|
| 4.E.1 | `[x]` | `conformance-profiles.json` 新增 `cx.profile.space.hub_writer.v1` 与 `cx.profile.space.peer_mesh.v1`（Space-level profile，进 `Space.schema_refs`） |
| 4.E.2 | `[x]` | hub_writer profile：required `cx.space.host` 已 accepted；required host endorsement on state events |
| 4.E.3 | `[x]` | peer_mesh profile：禁止 host endorsement（防写错）；保持现有 peer-mesh 语义 |
| 4.E.4 | `[x]` | `data-structures.md` Space 表说明 federation_policy → space_writer_model 默认派生表 |

### 4.F 联邦语义

| # | 状态 | 任务 |
|---|---|---|
| 4.F.1 | `[x]` | `sync/federation.md`：hub Space 联邦传播变成 host fanout（host 是 source of truth；follower 接收并验证签名后写入本地 replica） |
| 4.F.2 | `[x]` | hub Space 的写入必须经 host：客户端通过 host 提交事件，host endorsement 后传播 |
| 4.F.3 | `[x]` | peer_mesh Space 联邦传播保持 peer-mesh + auth-chain bootstrap |
| 4.F.4 | `[x]` | `sync/sovereign-deployment.md`：sovereign 部署默认 hub_writer，并明确组织 server 担任 host 的语义 |

### 4.G Glossary + 交叉引用 + lint

| # | 状态 | 任务 |
|---|---|---|
| 4.G.1 | `[x]` | `glossary.md` 新增 Space Writer Model / Space Host / Host Endorsement / Hub Writer / Peer Mesh / Host Transfer 6 条 |
| 4.G.2 | `[x]` | `overview/architecture.md` 增加一段说明双轨 writer 模型 |
| 4.G.3 | `[x]` | `python tools/artifact_pipeline.py check` 通过 |

## Phase 5 🅿 — Consent state machine ✅

| # | 状态 | 任务 |
|---|---|---|
| 5.1 | `[x]` | 新增 `spec/v1/zh/identity/consent-model.md`：完整定义 holder-private consent 模型、设计原则、与 capability/invite 正交、scope 枚举、reducer 行为、invite/contact 前置 gate 整合、MIMI interop、隐私审计、未来 capability constraint 扩展点 |
| 5.2 | `[x]` | 新增 2 个 event kinds：`cx.consent.grant` 与 `cx.consent.revoke`（共享 state slot by `payload.consent_id`）。`cx.consent.query` 不作为 durable event 注册（属于 service operation）。Component_type=`cx.component.consent.grant.v1`，criticality=`required` |
| 5.3 | `[x]` | consent 作为 invite/contact 前置 gate 在 §6 文档化；与 `cx.space.policy_components` 中 `preauth` component 的 `require_consent` 互动写明 |
| 5.4 | `[x]` | `mimi-interop.md` §10 引用更新：MIMI `request_consent` / `update_consent` 显式映射到 `cx.consent.grant` / `cx.consent.revoke`，保留 `consent_id` 作为 inter-protocol correlation |
| 5.5 | `[x]` | `python tools/artifact_pipeline.py check` 通过：129 event kinds（+2）、34 schemas、50 profiles |

## 执行规则

1. 每个 Phase 完成后必须 `python tools/artifact_pipeline.py check` 通过，再开始下一个 Phase。
2. Phase 1 内部分 1.A → 1.B → 1.C → 1.D → 1.E 顺序执行；1.C 内部各文件可并行。
3. 不在 Phase 1 完成前开始 Phase 2/3。
4. Phase 4 阻塞，等显式决策。
5. 每完成一个 sub-task 标 `[x]`，并在末尾追加该 sub-task 简短说明（一行）。

## 审计发现与修补（2026-05-07）

完成 5 个 Phase 后做的一致性审计与设计 polish：

| # | 发现 | 修补 |
|---|---|---|
| A1 | `consent-model.md` 自身引用了已移除的 `cx.space.policy.set (state_key=policy_components)` | 改为 `cx.space.policy_components` |
| A2 | 共享 state slot 的 paired kinds（capability.grant/revoke、profile.create/update、device.authorized/revoked）有不同 `component_type`，与 consent.grant/revoke 共享模式不一致 | secondary kind `component_type` 对齐 primary，并新增 `component_slot_alias_of` registry 字段；§4.4 文本说明此关系 |
| A3 | `writer_model_constraint: hub` 仅在 registry 声明，spec 无明文 reject 规则 | §3.3 加 "Writer Model Kind Constraints" 段：peer_mesh Space 出现 `cx.space.host` / `cx.space.host.transfer` MUST `schema_violation` reject |
| A4 | hub Space 的 genesis host bootstrap 流程不明确 | §3.3 加 "Genesis Host 引导" 段：4 步明确 create event 的 space_host 充当 implicit cx.space.host genesis、初始事件 endorsement 来源、host_did 转移必须走 §13 |
| A5 | encryption-and-audit.md §2.5.1 没指向 event-auth-state-resolution.md §8.1 / §11 | 加交叉引用 |
| A6 | mimi-interop.md §9.1 表缺少 `cx.space.host` / `cx.space.host.transfer` | 加 2 行说明这是 Contrix 专属（MIMI hub provider 概念相邻但不等价） |
| A7 | `mls_state_binding.full.v1` 的 `capability_root_required_components` 包含已 alias 掉的 `cx.component.capability.revoke.v1` | 移除（grant slot 已覆盖 revoke） |
| A8 | `space.schema.json` 没强制 peer_mesh Space 不能有 `space_host` | 加 if/then 反向约束：`peer_mesh` MUST NOT 声明 `space_host` |
| A9 | `matrix-core-differences.md` 缺 v1 偏离声明（Phase 1.E.4 遗留） | 新增 §6 详细列 6 大偏离 + 理由 |

审计自动检查通过：

- 46 个 state kind 全部完整声明 cardinality / subject_field / component_type / criticality
- `mls_state_binding.full.v1` 的 3 个 component 列表（policy_root / membership_frontier / capability_root）全部引用 registry 中实际存在的 component_type
- `python tools/artifact_pipeline.py check` 通过：129 event kinds、34 schemas、50 profiles

**仍未做的可选改进**（不影响 wire 合约 / lint 通过；列在此处供后续追踪）：

- 新 kinds（`cx.space.host`、`cx.space.host.transfer`、`cx.consent.*`）的 conformance fixture 覆盖：state-resolution-fixture.json 应增加 hub fork diagnostic vector；新增 host-transfer-fixture.json / consent-fixture.json
- `cx.consent.query` 作为 service operation 的 OpenAPI binding（暂仅在 spec 文本提及）
- 把 `policy_root_required_components` 从 profile 元信息提升为机器可校验的 lint 规则（"E2EE Space 的 cx.mls.commit 必须列出全部 required components"）

## 完成 changelog

### 2026-05-07：Phase 5 完成（Consent state machine）

- 新文件 [`spec/v1/zh/identity/consent-model.md`](spec/v1/zh/identity/consent-model.md) 详细定义 holder-private consent 协议层：与 capability + invite 正交的"我同意接收来自 X 的某种联系"语义。
- 新增 2 个 event kinds：`cx.consent.grant` / `cx.consent.revoke`（共享 state slot by `payload.consent_id`，与 capability.grant/revoke 同一 supersede 模式）。
- 新增 2 个 payload schemas：`consent_grant_payload`（含 `peer`、`scope`、`not_before`/`valid_until`、`evidence_ref`），`consent_revoke_payload`。
- Scope 枚举：`invite` / `direct_message` / `voice_call` / `video_call` / `presence` / `any`（每种 scope 是独立 consent slot）。
- Consent 写入位置约束：MUST 在 holder 的 principal control Space，不暴露给协作 Space。
- Invite / contact 流程整合：consent 作为前置 gate；`cx.space.policy_components.preauth` 可声明 `require_consent: true` 强制走显式 consent 路径。
- MIMI 互译映射：`cx.mimi.request_consent` / `cx.mimi.update_consent` 显式映射到 Contrix consent event family，保留 `consent_id` 作为 inter-protocol correlation。
- glossary 新增 2 条：Consent / Consent Scope。
- event_kinds 127 → 129。
- `python tools/artifact_pipeline.py check` 通过。

### 2026-05-07：Phase 4 完成（Hybrid Writer Model：hub vs peer_mesh）

- **Space 层 wire-breaking**：`Space.space_writer_model: enum(hub, peer_mesh)` 与 `space_host: did` 加入 space.schema.json，create-locked。默认按 federation_policy 派生（closed/restricted/quarantine → hub；open → peer_mesh）。
- **2 个新 event kind**：
  - `cx.space.host`（singleton state，hub-only）—— 声明 host service DID、standby_hosts、activation_timeout_ms、host_endpoint
  - `cx.space.host.transfer`（per_subject by transfer_id，hub-only）—— smooth dual-sign / emergency governance-quorum 双 mode
- **新 proof type**：`proof.kind="host_endorsement"`（与 `detached_jws` 并列）。hub Space 的 durable state event 必须携带恰好一个 host endorsement proof，覆盖与 actor proof 相同的 canonical bytes。peer_mesh Space 出现 host_endorsement MUST schema_violation reject。
- **2 个新 conformance profile**：`cx.profile.space.hub_writer.v1`（required `cx.space.host` accepted + host endorsement on state events）、`cx.profile.space.peer_mesh.v1`（rejected_event_kinds: `cx.space.host`, `cx.space.host.transfer`）。
- **event-auth-state-resolution.md** 新增三大块：
  - §3.3 Hub Writer Endorsement：endorsement 验证规则、bootstrap 例外、与现有 §3 验证流程的关系
  - §9.5 Hub Writer 模型下的 Fork 诊断：hub Space 的 fork = host fault；整 state slot quarantine + host fault report；触发 emergency transfer 候选条件
  - §13 Space Host Transfer：smooth / emergency 两 mode 详细规则、activation_frontier 边界
- **federation.md §2.4**：双模型传播形态——peer_mesh 走 §4 mesh 协议；hub 走 actor → host → fanout 路径。跨域 Space 的 writer_model 由 create event 锁定，不存在 split-brain 状态。
- **sovereign-deployment.md**：sovereign 部署默认 hub-writer，组织自己的 Principal Server 担任 Space Host；可通过 §13 host transfer 仪式在组织间转移。
- **glossary.md** 新增 6 条：Space Writer Model / Space Host / Host Endorsement / Hub Writer Model / Peer Mesh Model / Host Transfer。
- **data-structures.md** Space 表增加 space_writer_model + space_host 两行。
- **event_kinds count**：125 → 127（+`cx.space.host` + `cx.space.host.transfer`）。
- **profiles count**：48 → 50（+ hub_writer + peer_mesh）。
- `python tools/artifact_pipeline.py check` 通过。
- 协议层得到："sovereign 部署用单 writer + MLS state binding，跨组织 federation 用 peer-mesh + state resolution"——每种工作流用最适合的形态，且选择是显式 wire-level 决策，不是隐式默认。

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
