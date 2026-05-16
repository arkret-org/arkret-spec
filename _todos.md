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

- [ ] AW-1.1 Schema types：`AgentTask` / `ContextAnchor` / `ExecutionState` / `TransparencyState` / `SourceAuthorityState` / `MentionRedirectContent` / `ImportAttestationContent` / `SourceExportPolicyAttestation`
- [ ] AW-1.2 `agent_task` typed ID（`crates/identifiers`）+ `TypedId<AgentTask>`
- [ ] AW-1.3 Event payload helpers：`AgentTaskCreatePayload` / `AgentTaskTransitionPayload` / `AgentTaskCancelPayload` + `to_event_envelope()`；mention_redirect 注入 `requirements.critical_extensions[]`
- [ ] AW-1.4 FSM 校验：`legal_transition` 3 cell 各一个 + `agent_runtime_may_execute` gate + 单元测试覆盖合法/非法 transition
- [ ] AW-1.5 Reservation / recovery helpers：`compute_reservation_move`（`head_eq:"__unset__"`）/ `compute_recovery_move`（lex-min + §8 refs）/ `compute_orphan_cleanup_move`（含 anchor-based `ttl_evidence`）
- [ ] AW-1.6 import_attestation signing：`compute_canonical_signing_input` / `sign_import_attestation` / `verify_import_attestation` / `compute_content_hash`（JCS+SHA-256）/ `compute_export_policy_canonical_input`（domain separator）/ `sign_export_policy_attestation` / `verify_export_policy_attestation`
- [ ] AW-1.7 `attached_authority` 字段加到 `CapabilityGrant`（`crates/sdk/src/authz/capability.rs`）；`AttachedAuthority` enum（`anchored_event_ref` / `state_witness`）
- [ ] AW-1.8 HTTP client：`agent_workspace_resolve_mirror_flow` + `agent_workspace_list_pending_tasks`（`crates/http-client`）；401/403 不暴露存在性
- [ ] AW-1.9 Conformance hooks placeholder：`crates/testing::agent_workspace::vectors()` 返回 §15 的 43 vector enum
- [ ] AW-1.10 Module doc + CHANGELOG entry

Acceptance：`cargo test -p contrix` 全绿；新增 module 有 ≥80% line coverage。

### AW-2 `soland`（reducer + service ops）

- [ ] AW-2.1 Event kinds：`src/kinds.rs` 加 5 个 const；`src/reducer/registry.rs` 注册（profile_gate=`cx.profile.agent_workspace.v1`）
- [ ] AW-2.2 Reducer 实现 `src/reducer/agent_task.rs`：`reduce_agent_task_create` / 3 个 `_transition` / `_cancel`；含 schema validation、authz check、singleton enforcement、idempotent on illegal from
- [ ] AW-2.3 mention_redirect 拦截：critical_extension check（未支持 server reject）+ `authority_grant_ref` 校验（grant active + subject 匹配 + attached_authority.controller == sender_principal）
- [ ] AW-2.4 Reservation cell schema：2 个 reservation namespace（cas-register + bottom=reject + initial_value `"__unset__"`）+ 3 个 agent_task FSM namespace
- [ ] AW-2.5 HTTP service ops：`src/routing/agent_workspace/mod.rs`，2 个 GET endpoint；auth = DID-signed 或 session token；非 owner/未鉴权 返回 401/403
- [ ] AW-2.6 Notification 推送：源 Space `cx.member.state` / `cx.capability.grant` / `cx.capability.revoke` 后置 hook → 推 `agent_membership_change` 到 controller workspace
- [ ] AW-2.7 集成测试 `tests/agent_workspace/`：reservation_singleton / reservation_concurrent_bottom / recovery_move / fsm_transition / mention_redirect_validation / orphan_cleanup / resolve_api_filtering
- [ ] AW-2.8 OpenAPI contract 测试同步

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
- [ ] AW-3.1 `src/routes.rs` 加 `Agents` / `AgentTask { task_id }` / `AgentSettings { section }`；原 `Agents` 改名 `AgentProtocol`

**Views**：
- [ ] AW-3.2 `src/views/agent_workspace_dashboard.rs`
- [ ] AW-3.3 `src/views/agent_task_detail.rs`（含 publish-to-source modal + read-then-write）
- [ ] AW-3.4 `src/views/agent_workspace_settings.rs`

**Components**：
- [ ] AW-3.5 `src/components/agent_task_card.rs`
- [ ] AW-3.6 `src/components/fsm_state_chip.rs`（3 cell 状态 chip + transition history popover）
- [ ] AW-3.7 `src/components/publish_to_source_modal.rs`
- [ ] AW-3.8 `src/components/add_agent_modal.rs`
- [ ] AW-3.9 `src/components/private_compose_indicator.rs`

**Chat / Discussion compose 改造**：
- [ ] AW-3.10 `src/views/chat.rs` + `src/views/timeline.rs` mention 候选加 "我的 agent" 分组 + private routing 模式 + send 路径调用 SDK `compose_mention_redirect_pair`

**Watcher**：
- [ ] AW-3.11 `src/agent_workspace_watcher.rs`：监听本地 source Space 事件流 → 探测 `cx.redaction(target=mention_redirect)` / `cx.capability.revoke` / `cx.member.state(removed)` → read-then-write 写 transparency/source_authority transition

**Notification**：
- [ ] AW-3.12 `src/views/notifications.rs` 加 `agent_membership_change` renderer，click 跳 Agents Dashboard 或 task detail

**i18n**：
- [ ] AW-3.13 所有新文案进 `src/i18n.rs`（agents.dashboard / agents.pending / agents.task.transparency_lost_banner / agents.compose.private_routing_notice 等）

**测试**：
- [ ] AW-3.14 `tests/agent_workspace_dashboard.rs`（Playwright，mock soland）
- [ ] AW-3.15 `tests/private_compose.rs`（@my-agent 切换 + send 触发双侧）
- [ ] AW-3.16 `tests/publish_to_source.rs`（read-then-write，cancelled task abort modal）

**UX checklist**：
- [ ] AW-3.17 顶部 nav `Agents` 图标 + 红点（有 pending 时）
- [ ] AW-3.18 dashboard 待处理项 sticky on top
- [ ] AW-3.19 task 详情页 3 cell chip 用一致 palette；dark mode 兼容
- [ ] AW-3.20 publish modal 默认 = 我 + 仅文字（最小披露）
- [ ] AW-3.21 empty state：无 agent / 无 task 各引导
- [ ] AW-3.22 移动端 single column；3 cell chip 横向 scroll
- [ ] AW-3.23 keyboard shortcut Cmd/Ctrl+K agent task quick switcher

Acceptance：`cargo test -p yougen` 全绿；Playwright 3 个新 test 通过；浏览器开发者实际跑一次手动 smoke 包含 dashboard + compose + publish flow。

### AW-4 协议补完（执行中发现）

执行中如发现下列任一回 contrix-spec 提 PR：
- Cell schema `initial_value` 字段（已知，`_agent_workspace_artifact_todos.md §1.1`）
- `attached_authority` 加到 capability-grant schema（已知，§1.2）
- 跨 deployment watcher 投递 SLA（federation.md 章节）
- `cx.agent_task.cancel` 便捷事件 reducer 等价语义注

发现其他原地在该任务下加 ⚠ note，最终汇总。
