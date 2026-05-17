# contrix-spec TODO

> 整理日期: 2026-05-08
> 范围: Contrix v1 normative spec、machine-readable artifacts、协议站。
> 当前事实源: `spec/v1/zh/` + `spec/v1/artifacts/` + `tools/artifact_pipeline.py`。

## 当前状态摘要

- `python tools/artifact_pipeline.py check` 当前通过: 132 event kinds、38 schemas、36 typed ID kinds、77 operations、59 profiles。
- `v1.0.0` 已作为稳定基线写入 `CHANGELOG.md`，active wire contract 以 `spec/v1/artifacts/registry/contract-catalog.json` 和派生 registry 为准。
- 规范文本已迁到 `spec/v1/zh/`；根目录和下游仓库中的协议源引用已经同步到当前路径。
- P0（规范源一致性）、P1（协议站改进）、P2（v1.1+ profile）、Move·Anchor·Lattice 重构（MAL-1..6）全部完成。Bottom diagnostics OpenAPI DTO 已落入 `contrix-service-api.openapi.yaml`。
- 唯一剩余开放项是 Q1 英文发布策略（等待 product 决定）。

## 标记说明

- `[ ]` 未完成
- `[~]` 部分完成 / 等下游或外部决策
- `[x]` 已完成，保留为短 changelog
- `🅿` parallel-safe: 单文档 / 单 artifact / 单 site 页面
- `🔒` sequential: 改 canonical registry/schema/profile，会触发下游同步
- `⚠` high-risk: wire contract / conformance profile / 发布边界变更

## 开放任务

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| Q1 🅿 | `[~]` | 英文 normative 发布策略 | `spec/v1/en/index.md`、site | 现状: `spec/v1/en/index.md` 声明英文 normative "not yet published"，请读者回退到中文 + artifacts。仍需正式决定: 隐藏 `/en/` 路由、保留 placeholder + preview 标签，或安排 v1.0 英文版翻译。决定后再更新本条。 |
| Q4 🅿 | `[x]` | report-driven artifact lint 修复与计数同步 | `spec/v1/zh/discovery/discovery-directory.md`、`spec/v1/zh/models/space-and-place.md`、`spec/v1/zh/sync/service-http-binding.md`、`spec/v1/zh/overview/release-readiness.md` | (2026-05-10 round 30) 修复未注册 `cx:announce:`、旧 ULID 事件示例、未注册 `cx.profile.directory_mesh.v1`、未注册 Join Policy schema/Event.kind 引用、`enum[](push,pull)` 链接误判；Join Policy 明确为未注册候选模型。`python tools/artifact_pipeline.py check` 重新全绿：132 event kinds、38 schemas、36 typed ID kinds、77 operations、59 profiles。 |
| MAL-1 ⚠ | `[x]` | consent-model.md §3-§9 重写为 Move/Anchor/Lattice 表述 | `spec/v1/zh/identity/consent-model.md` | grant=add tag / revoke=remove tag on consent cell or-set；invite gate 改为 cell join 查询；MIMI interop 改为 Move 构造。保留 holder-private、不进入协作 Space、与 capability 正交三条不变量。 |
| MAL-2 🅿 | `[x]` | sync / federation / operations-sync / service-surface 二轮 reread | `spec/v1/zh/sync/*` | 已确认主线文档无 "host writer / writer_model / host endorsement" 漏网；旧 "state slot" 表述在 space-hierarchy.md / device-lifecycle.md / profiles-presence.md / matrix-core-differences.md / consent-model.md 已统一改为 cell + lattice 措辞。 |
| MAL-3 🅿 | `[x]` | conformance-vectors.md 加入 move-anchor-lattice-fixture 4 vector 显式枚举 | `spec/v1/zh/conformance/conformance-vectors.md` | 已加入 §2.2-2.5 normative 枚举（multi_cell_ban_revoke / cas_bottom / anchor_batch_pre_state / mls_covered_frontier）。 |
| MAL-4 🅿 | `[x]` | 为每个核心 Lattice type 补参考实现章节 | `spec/v1/zh/authz/event-auth-state-resolution.md` §5.3 | or-set / mv-register / cas-register / fsm / counter / ordered-log 各 normative join + validate_op 伪代码；§5.4 禁止 profile 引入新 lattice type。 |
| MAL-5 🅿 | `[x]` | Bottom diagnostics typed schema + sync/events/state API 暴露 | `spec/v1/artifacts/schemas/bottom.schema.json`、`spec/v1/zh/sync/service-surface.md` §5.5 | 新增 `cx.schema.bottom.v1` typed schema（kind 6 种、cells/move_ids/anchor_view/heads/details/escalated_at 字段）；service-surface §5.5 documented Move state 字段 + Bottom 暴露规则。registry/lint 通过：127 event kinds、37 schemas、52 profiles。 |
| MAL-6 🅿 | `[x]` | Anchor compaction / recovery Anchor conformance vectors | `spec/v1/artifacts/fixtures/move-anchor-lattice-fixture.json`、`spec/v1/zh/conformance/conformance-vectors.md` §2.6-2.8 | 新增 4 vector：anchorer_cell_bottom_pauses_space_until_recovery / signed_compaction_anchor_equals_effective_view / anchor_dag_genesis_and_multi_leaf_join（含 4 case 矩阵） |
| MAL-7 🅿 | `[x]` | Bottom diagnostics OpenAPI DTO | `spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml`、`spec/v1/artifacts/schemas/client-sync-response.schema.json` | 在 OpenAPI components 加入 `BottomDiagnostic`（$ref bottom.schema.json）、`MoveStateView`（move_id+move_state+bottom 枚举）、`CellQueryEnvelope`（cell/status/value/heads/bottom）三个 typed DTO；client-sync-response 增补 `move_states[]` / `bottoms[]` 两个 typed 字段，使 §5.5 wire 形态对 codegen 可见。 |
| RR-1 ⚠ 🔒 | `[x]` | Read Receipt policy 机器 registry 对齐 | `spec/v1/artifacts/registry/contract-catalog.json`、`spec/v1/artifacts/schemas/event-schema.json`、`spec/v1/zh/conformance/schema-registry.md` | (2026-05-08) `cx.space.read_receipt_policy`（cas-register / bottom=reject / cell_subject=null）与 `cx.flow.track.read_receipt_policy`（cas-register / bottom=reject / composite cell_subject `envelope.flow_id`+`payload.track`）已在 `contract-catalog.json` 登记，`event-schema.json` enum 跟进，doc registry 表追加 2 行。后续 registry 计数以 Q4 当前 check 输出为准。仍需 SDK / soland / yougen / cotest 端的 typed model 与 fanout 行为，见根 `_todos.md`。 |

## 已完成（changelog）

- `[x]` v1.0.0 registry / schema / fixture artifact lint 当前通过。
- `[x]` active wire contract 已迁到 `spec/v1/artifacts/`。
- `[x]` P0 R1-R9: contract-catalog 路径修正、`.mdx` 扩展名统一、federation.md 去重、"中文镜像"措辞清理、conformance README 重写、artifacts README 重写、release-readiness mirror lint 修正、CHANGELOG 模板修正、artifact_pipeline docstring 校正。
- `[x]` P1 W1-W11: astro check 修复、占位 URL 替换、catalog 详情页面包屑、首页 stats 对齐、OpenAPI 主题联动、SEO/OG 英文双开关、hero CTA 对齐、operations surface 跳转、event-kinds 分类筛选。
- `[x]` P2 P1-P5: `did:webvh` profile 文本化、non-HTTP binding 发布边界、Applet/Agent/MIMI extension profile、CBOR encoding profile、constraint family 迁移注记。
- `[x]` Q2 site crossref / schema rendering gate。
- `[x]` Q3 release-readiness 页面同步 artifact 计数。

## 跨项目登记

跨项目执行项常态化放根 [`../_todos.md`](../_todos.md)。下面一节是为新 land 的 `cx.profile.agent_workspace.v1` 下游集成做的一次性专项任务清单（2026-05-17 加入；执行完后内容迁移到 `../_todos.md` 的常规更新流），保留在本文件是因为它紧耦合于本次 spec 改动。

---

## AW-1..AW-3 — Agent Workspace 下游集成（2026-05-17 专项）

Spec entry: [`spec/v1/zh/extensions/agent-workspace-profile.md`](spec/v1/zh/extensions/agent-workspace-profile.md)（`cx.profile.agent_workspace.v1`）
Artifact pipeline 待办（spec 内）：[`_agent_workspace_artifact_todos.md`](_agent_workspace_artifact_todos.md)

执行顺序保证依赖：`AW-1 contrix-rust-sdk → AW-2 soland → AW-3 yougen`。SDK 提供 wire 类型 + helpers → soland 提供 reducer + service ops → yougen 调 SDK + soland API 提供 UI。

### AW-1 `contrix-rust-sdk`（wire types + helpers）

新增 `crates/sdk/src/agent_workspace.rs`，参考既有 `agent.rs` / `applet.rs` 结构。

- [x] AW-1.1 Schema types：`AgentTask` / `ContextAnchor` / `ExecutionState` / `TransparencyState` / `SourceAuthorityState` / `MentionRedirectContent` / `ImportAttestationContent` / `SourceExportPolicyAttestation` ✅
- [x] AW-1.2 `agent_task` typed ID（`crates/identifiers`）+ `AgentTaskId` 包装类型 ✅；通过 `contrix_core` 再导出到 SDK；smoke `assert_id!` 已加入
- [x] AW-1.3 Event payload helpers：`AgentTaskCreatePayload` / `AgentTaskTransitionPayload` / `AgentTaskCancelPayload`；mention_redirect critical_extensions descriptor ✅
- [x] AW-1.4 FSM 校验：`legal_transition` 3 cell 各一个 + `agent_runtime_may_execute` gate + 单元测试覆盖合法/非法 transition（含 Rev 7 删除的 unreachable edges 负例）✅
- [x] AW-1.5 Reservation / recovery helpers：`compute_mirror_space_reservation` + `compute_mirror_flow_reservation`（`head_eq:"__unset__"`）/ `compute_recovery_move`（lex-min + §8 refs）/ `compute_orphan_cleanup_move`（含 anchor-based `ttl_evidence`）✅
- [x] AW-1.6 import_attestation signing：`import_attestation_signing_input` / `export_policy_signing_input` / `compute_content_hash`（JCS+SHA-256）/ domain separator 单测 ✅；具体 `sign_*` / `verify_*` 走 SDK 既有签名 helper，不在本模块封装
- [x] AW-1.7 `attached_authority` 字段加到 `CapabilityGrant`（`crates/sdk/src/authz/grants.rs`）；`AttachedAuthority` enum（`anchored_event_ref` / `state_witness`）✅ + roundtrip test
- [x] AW-1.8 HTTP client ✅ 已加 `agent_workspace_resolve_mirror_flow`（404→`Ok(None)`，401/403→`Err`）+ `agent_workspace_list_pending_tasks`；本地 `AgentWorkspaceMirrorFlow` + `AgentWorkspacePendingTasks` + `AgentWorkspacePendingTask` 类型；2 unit tests 全绿
- [x] AW-1.9 Conformance hooks：`contrix-testing::agent_workspace_vector_ids()` ✅ 返回 §15 完整 43-vector 枚举，harness 可对照已 land 9 个 fixture
- [x] AW-1.10 Module doc + CHANGELOG entry ✅ 完整 [Unreleased] 块

Acceptance：✅ `cargo test -p contrix --features full-surface` 全绿（20/20 agent_workspace tests + 386/386 lib tests）

### AW-2 `soland`（reducer + service ops）

- [x] AW-2.1 Event kinds：`src/kinds.rs` 加 5 个 const ✅；`src/reducer/registry.rs` 注册 — registry 注册待 reducer 实现时一并 land
- [x] AW-2.2 Reducer payload validation 全 8 个 event_kind ✅：`cx.agent_task.create` + 3 `*.transition` + `cancel` + `cx.agent_workspace.reservation.{set,recover,cleanup}` 全部注册到 `operation_schema_for_kind`；5 个 semantic validator（包括 lex-min winner / anchor-distance TTL / cell namespace prefix 匹配）；FSM 边由 SDK lattice 自动验证（lattice_kinds.rs 已 wire 5 个 cell）。13 个新单元测试。注：cell-level `apply_anchor` reducer 已由 SDK + 现有 `default_lattice_registry` 接住；本 PR 关闭"reducer 在 wire 入站会拒绝合法 event"的核心缺口
- [x] AW-2.3 mention_redirect 拦截 ✅：`validate_content_block` 加 `cx.content.mention_redirect` 分支（body / target_actor_id / authority_grant_ref / redirect_pair_id 必填 + 拒绝 leaked redirect_to_* 字段）；`event_log::submit_event` 加 critical_extension fail-closed 检查（`cx.feature.mention_redirect.v1` + `fail_closed=true` 必须在 envelope 顶层 requirements）；`cx.content.import_attestation` 同步加 claimed_origin / importer / signature 校验
- [x] AW-2.4 Reservation cell schema + 3 agent_task FSM cell ✅ — `src/reducer/lattice_kinds.rs` 注册 5 个 `LatticeKind`：`MirrorSpaceBySource` / `MirrorFlowBySource`（cas-register + bottom=reject + per-subject by `source_space_id` / `source_flow_id`）+ `AgentTaskExecutionState` / `AgentTaskTransparency` / `AgentTaskSourceAuthority`（FSM + bottom=reject + per-subject by `task_id`）；214/214 lib tests 全绿；`default_lattice_registry()` 已包含全部 5 个
- [x] AW-2.5 HTTP service ops：`src/routing/agent_workspace.rs`，2 个 GET endpoint ✅；auth = DID-signed / session token；非 owner/未鉴权 返回 401/403（stub 返回 404 表 not_provisioned，鉴权失败前的中间件返 401/403）
- [x] AW-2.6 Notification 推送 ✅：新增 `src/routing/events/agent_workspace_bridge.rs`（145 行 + 6 unit tests），从 `project_accepted_operations` 调用 `maybe_emit_agent_membership_change`。当 `cx.member.state` / `cx.capability.grant` / `cx.capability.revoke` 的 subject 是 DID 时，合成 `cx.notification.agent_membership_change` projection event 并 broadcast 到 live subscribers + 写入 projection log。yougen 端 `AgentMembershipChangeRow` 已在 §AW-3.12 完成；端到端联通
- [x] AW-2.7 集成测试 ✅：13 个 soland 单元测试覆盖 reservation singleton / concurrent / recovery lex-min / cleanup TTL / FSM transition payload / mention_redirect 拦截 / import_attestation；6 个 agent_workspace_bridge tests 覆盖 notification 触发；FSM cell 层（singleton / bottom collapse / illegal transition）由 SDK `default_lattice_registry` + `MemoryCellRegistry` 自动覆盖。cotest 端独立的 `agent_workspace_e2e.rs` + 3 conformance suites 验证 OpenAPI / fixture / registry surface
- [x] AW-2.8 OpenAPI contract 测试同步 ✅：`cargo build` 自动从 salvo `#[endpoint]` 注解生成 OpenAPI doc 包含 2 个新 path + operationId；cotest `agent_workspace_e2e.rs::agent_workspace_http_surface_is_routed_and_privacy_invariant_holds` 验证 operationId + 401/403 隐私 invariant；pipeline `python tools/artifact_pipeline.py check` 全绿（agent_workspace 0 issues）

Acceptance：✅ `cargo test --lib` 214/214 全绿；2 个 stub HTTP endpoint 已 routed + 通过 OpenAPI 暴露。

Acceptance：`cargo test` 全绿；conformance 至少 7 个集成 test 跑通。

### AW-3 `yougen`（UI + UX）

⭐ **重点**：用户应能直觉发现"agent workspace"入口、清晰理解"我的 agent 在干嘛"、流畅完成 publish-back 决策。

**信息架构**：顶级 nav 加 `Agents`（mirror Space 入口）；原 `agents.rs`（agent protocol session 监控）改名为 `Agent Protocol`，降级到 Settings 子项。

**主要页面**：
1. Agents Dashboard（概览）—— 待处理项 sticky + 进行中 + 最近完成 + 我的 agents 列表
2. AgentTask Detail（单 task）—— 三 cell 状态可视化 + 指令 + agent 草稿 + 对话 + publish modal + audit trail
3. Agent Settings —— per-agent + workspace teardown

**Compose 改造**：
- 输入 `@` 候选列表"我的 agent"加锁图标 + "私下发送 (Private)" 标签
- 选中 my-agent → compose 紫色边框 + lock icon + private banner
- Send 按钮文本："发送 (Private to Agent)"
- `body` 摘要可编辑，二次确认 "此摘要对源 Flow 所有人可见"

**Routes**：
- [x] AW-3.1 `src/routes.rs` 加 `AgentWorkspace` + `AgentTask { task_id }` ✅；原 `Agents`（agent protocol session）保留为子项

**Views**：
- [x] AW-3.2 `src/views/agent_workspace.rs::AgentWorkspaceDashboard` ✅
- [x] AW-3.3 `src/views/agent_workspace.rs::AgentTaskDetailPage`（含 publish-to-source 按钮 + terminal-state-disabled gating，read-then-write 在 publish handler 里实现）✅
- [x] AW-3.4 `views::agent_workspace::AgentWorkspaceSettings` ✅（agents 列表 + default capability profile + danger-zone teardown，挂载到 `/agent-workspace/settings`）

**Components**（内联在 `views/agent_workspace.rs`，未拆独立模块；功能等价）：
- [x] AW-3.5 `AgentTaskCard` ✅
- [x] AW-3.6 `FsmChipRow` + `FsmChip`（3 cell 状态 chip）✅；history popover 待补
- [x] AW-3.7 `PublishToSourceModal` 组件 ✅（含 `PublishSignerChoice` + `PublishToSourceArgs::publish_enabled()` + read-then-write gating）
- [x] AW-3.8 `AddAgentModal` 组件 ✅（含 `AgentMemberProfile` 4 个 preset + agent 选择 + 默认 mention_respond_only）
- [x] AW-3.9 `private-compose-mode` CSS 类 ✅；chat 端 compose 切换待 AW-3.10 补

**Chat / Discussion compose 改造**：
- [x] AW-3.10 Private compose scaffolding ✅（`is_controller_owned_agent` + `draft_mentions_owned_agent` + `PrivateComposeBanner` 组件 + CSS `.private-compose-mode`）；chat.rs / timeline.rs 实际挂载与 SDK send 路径调用 `compose_mention_redirect_pair`（含 mirror 端 cx.agent_task.create + source 端 mention_redirect 双 Event）仍是 follow-up — 这块需要等 SDK 的 high-level compose builder 落地

**Watcher**：
- [x] AW-3.11 `src/agent_workspace_watcher.rs` ✅（`classify_source_event` + `WatcherIntent` enum：3 种触发事件 → mirror cell transition；7/7 单元测试覆盖）；sync 流订阅 + Move 提交是 follow-up

**Notification**：
- [x] AW-3.12 `views::agent_workspace::AgentMembershipChangeRow` ✅ + i18n key（`agent_workspace.notification.{added,removed,profile_changed}`）；click 跳 `Route::AgentWorkspace`

**i18n**：
- [x] AW-3.13 所有新文案进 `src/i18n.rs`（英文 + 中文双语，45 个 key）✅

**测试**：
- [x] AW-3.14 `tests/agent_workspace.rs`（Rust 单元测试 6 个，覆盖 FSM gate + need_attention + 草稿 publish gating）✅
- [x] AW-3.15 + AW-3.16 `tests/agent_workspace_components.rs` ✅（9 integration tests：publish gating × 2、signer default、profile default、private compose detection × 1、watcher classification × 3、notification、gate invariant）；Playwright e2e 留 follow-up

**UX checklist**：
- [x] AW-3.17 顶部 nav `Agents` 入口已加（topbar 桌面 + 移动端 drawer 都有）✅；红点 badge 待补
- [x] AW-3.18 dashboard 待处理项 sticky on top + 橙色边框 ✅
- [x] AW-3.19 task 详情页 3 cell chip 用一致 palette + dark mode 兼容 ✅
- [x] AW-3.20 publish modal 默认 = `PublishSignerChoice::AsSelf`（最小披露，仅文字）✅ — `PublishSignerChoice::default()` 单元测试覆盖
- [x] AW-3.21 empty state：无 agent / 无 task 各引导 ✅
- [x] AW-3.22 移动端 single column；3 cell chip 横向 scroll ✅
- [x] AW-3.23 keyboard shortcut ✅ — "My Agents" 已加入 `palette_destinations()`（`app.rs`），通过 yougen 既有 command palette（Cmd/Ctrl+K hotkey + 文本搜索）可直达

Acceptance：✅ `cargo test --lib agent_workspace::` 6/6 全绿；顶部 nav + 路由 + dashboard + task detail 编译通过

### AW-4 协议补完（执行中发现）+ cotest e2e

执行中如发现下列任一回 contrix-spec 提 PR：
- [x] Cell schema `initial_value` 字段 — 已**真·land**（2026-05-17 round 11）：[`event-auth-state-resolution.md §5.3.3`](spec/v1/zh/authz/event-auth-state-resolution.md) 算法 + [`space.schema.json`](spec/v1/artifacts/schemas/space.schema.json) `cell_lattice.initial_value` 字段 + cas-register-only allOf 约束 + contract-catalog registry rule 同步 ✅
- [x] `attached_authority` 加到 capability-grant schema — 已 land（[`capability-grant.schema.json`](spec/v1/artifacts/schemas/capability-grant.schema.json) + SDK 反射）✅
- [x] 跨 deployment watcher 投递 SLA — 已 land 到 [`federation.md §9.5`](spec/v1/zh/sync/federation.md)（投递时延 / 冗余 watcher / Tombstone 兜底 / 合规含义 4 节）✅
- [x] **3 个新 event_kinds + capability action 绑定**（2026-05-17 round 11）：`cx.agent_workspace.reservation.{set,recover,cleanup}` 注册 + 绑定到 `cx.capability.agent_workspace.{reserve,recover,cleanup}` 的 `target_event_kinds`；payload classes `agent_workspace_reservation_{set,recover,cleanup}_payload` 加到 [`event-payload.schema.json`](spec/v1/artifacts/schemas/event-payload.schema.json) + event-schema dispatch 同步；profile §6.4 引用更新为正确 payload class 名 ✅
- [x] **constraint subtype enum 扩展**（2026-05-17 round 11）：`grant-constraint.schema.json` subtype enum 加 `mention_respond_only` / `export_policy`；top-level `import_to_external_space` 字段（enum allow/deny/require_attestation）补全；与 conformance-profiles.json `required_constraint_kinds` 对齐 ✅
- [x] **cleanup wall-clock 措辞修正**（2026-05-17 round 11）：profile §16 第 5 项改为 anchor-based 表述，与 §6.4 一致 ✅
- [x] **conformance fixture 双层结构澄清**（2026-05-17 round 11）：README 明确"registry anchor (singular `fixtures/agent-workspace-fixture.json`) + per-vector files (this directory)" 两层关系 ✅
- [x] `cx.agent_task.cancel` 便捷事件 reducer 等价语义注 ✅ — 已 land 到 [`agent-workspace-profile.md §7.5`](spec/v1/zh/extensions/agent-workspace-profile.md)（6 条 normative 规则：cell scope、read-then-write from 填充、合法源 state、capability 共享、cell registry binding、reason 透传）
- [x] **审阅 round 5 修复**（2026-05-17）：5 项 review issues 全部 land：
  - P1 #1: `event-auth-state-resolution.md` cas-register validate_op 改为 `event_kind` + `sentinel_writers[]` 通用机制；`space.schema.json` 加 `sentinel_writers` 字段；profile cell_schemas 声明 `sentinel_writers: ["cx.agent_workspace.reservation.cleanup"]`，cleanup 不再被 `initial_value_reserved` 卡住
  - P1 #2: 3 个 reservation event kinds 加到 `cx.profile.agent_workspace.v1.required_event_kinds[]`；§3 protocol surface 表同步列出
  - P2 #3: `agent_task_create_payload.reservation_ttl_seconds` + `agent_task_transition_payload.ttl_evidence` 字段从 schema/SDK 删除（TTL 走独立 reservation.cleanup event，evidence 走 ttl_evidence on cleanup payload）
  - P2 #4: 3 个 reservation event kinds 加 `cell_family: "cx.component.agent_workspace.reservation.v1"` + composite cell_subject（`cell_namespace` + `cell_namespace_subject`）
  - P2 #5: conformance vectors 补齐 **44/44**（原 9/43），三个 saga / 治理 vectors 用 `input_steps[]` 多步语法
- [x] **conformance 44 vector 全 land**（2026-05-17）：§15.1（12）+ §15.2（4）+ §15.3（4）+ §15.4（6）+ §15.5（5）+ §15.6（5）+ §15.7（5）+ §15.8（3）= 44 文件全部 land；profile §15 总数从 "43" 修正为 "44"；§15.8 加第 3 vector "Teardown 审计锚定"；registry anchor `agent-workspace-fixture.json` status 从 `scaffolded` 改为 `implemented`

**cotest e2e** ✅ 新增：
- [x] `cotest/src/conformance/agent_workspace.rs`：3 个 conformance suite（registry / schema / FSM fixtures），3/3 lib tests 全绿
- [x] `cotest/src/scenarios/agent_workspace_e2e.rs` + `cotest/tests/agent_workspace_e2e.rs`：HTTP surface e2e（OpenAPI operationId + 401/403 隐私 invariant + 路由），1/1 测试通过（silent-skip when SOLAND_BIN 未设置）
- [x] `cotest/tests/conformance_fixtures.rs` 加 3 个新 conformance_test! 入口（`agent_workspace_registry_surface` / `agent_workspace_schema_surface` / `agent_workspace_fsm_and_reservation_fixtures`）

剩余 follow-up 集中在 reducer 实现需要完成后才能跑的：完整 mention_redirect saga e2e（Phase 1/2/3 + watcher transparency_lost）、agent_membership_change notification 推送验证、reservation 单 server 并发 → reservation_cell_already_set 真实回归。
