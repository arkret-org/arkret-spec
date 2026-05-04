# Optimization Round — Auditable E2EE Renaming + Capability/Constraint Simplification

源自上下文中两轮设计评审：

1. **Auditable E2EE 命名钢丝绳**：当前 `cx.profile.auditable_e2ee.{tee_required,software_only}.v1` 共享 `auditable_e2ee` 前缀，让"硬件强制"与"流程承诺"两种保证看起来等价。
2. **Capability + Constraint 复杂度**：14 种 constraint type 共用平面 enum；`condition.when` 是个未明确的字符串字段；求值算法的 deny/quarantine/review 优先级混合阶让缓存键设计困难；evaluation 依赖图没有显式契约。

本轮做 **PR 1 范围**（按之前推荐的优先级）。`auth_weight` lattice 重构与 4 个 state-resolution conformance vector 留 v1.x。

## A. Auditable E2EE 命名 + 字段重构

| # | 任务 | 文件 |
| --- | --- | --- |
| A1 | 重命名 profile id：`cx.profile.auditable_e2ee.tee_required.v1` → `cx.profile.attested_audit.e2ee.v1`；`cx.profile.auditable_e2ee.software_only.v1` → `cx.profile.disclosed_audit.e2ee.v1` | [`artifacts/profiles/conformance-profiles.json`](artifacts/profiles/conformance-profiles.json) |
| A2 | 同步更新 profile_groups (`e2ee_hardening`, `hardening_profiles`) 中的引用 | 同上 |
| A3 | `audit-ryw-receipt.schema.json` 加必填 `audit_assurance_class: enum("attested_hardware","disclosed_policy")` | [artifacts](artifacts/schemas/audit-ryw-receipt.schema.json) + [zh mirror](zh/conformance/schemas/audit-ryw-receipt.schema.json) |
| A4 | 更新 receipt schema description 引用新 profile id | 同上 |
| A5 | 重写 `encryption-and-audit.md §3.1` policy：删 `auditable_e2ee` bool 旗标 + 把 `auditable_e2ee_profile`/`audit_enforcement_level` 拆成 `audit_disclosure` 对象 + `audit_assurance` enum | [encryption-and-audit.md](zh/crypto-media/encryption-and-audit.md) |
| A6 | 更新 §3.2-§3.4 全部 profile id 引用 | 同上 |
| A7 | 加禁用措辞 normative 段（`disclosed_audit` 不得在产品材料中使用 "cryptographically enforced"/"attested"/"TEE-equivalent" 等措辞） | 同上 |
| A8 | 拆 §3.1 join warning 为 attested / disclosed 两套 MUST 文案 | 同上 |
| A9 | 更新 [`conformance-profiles.md`](zh/conformance/conformance-profiles.md) 中 auditable_e2ee 段对应文字 | conformance-profiles.md |
| A10 | 注册 `cx.audit.ryw_receipt` event kind（解决 _report.md B-13；attested mode 下 receipt 可作 durable Event 进入 audit log） | [`contract-catalog.json`](artifacts/registry/contract-catalog.json) |

## B. Capability + Constraint 简化

| # | 任务 | 文件 |
| --- | --- | --- |
| B1 | `condition.when` 改名为 `condition.kind`（typed object key 与 constraint 系统其他部分对齐） | [grant-constraint schema](artifacts/schemas/grant-constraint.schema.json) + [zh mirror](zh/conformance/schemas/grant-constraint.schema.json) |
| B2 | 更新 [constraint-schema.md §4.1 example](zh/authz/constraint-schema.md) 使用新字段名 | constraint-schema.md |
| B3 | 求值算法压扁：deny/quarantine/require_review 一律 "任一命中即生效"；priority 仅用于 allow 诊断；改写 §15.1 / §15.2 / §15.3 | constraint-schema.md |
| B4 | grant-constraint schema 加 `evaluation_class: enum("stateless","grant_local","space_state","external")` | grant-constraint schema (mirror 同步) |
| B5 | constraint-schema.md §2.1 加 `evaluation_class` 字段说明；新增 §2.3 表格列出 14 种 constraint type 各自的 evaluation_class | constraint-schema.md |

## C. 收尾

| # | 任务 |
| --- | --- |
| C1 | 跑 `python tools/artifact_pipeline.py sync` + `check`，确保 catalog ↔ generated registries ↔ mirror 一致 |
| C2 | 在 `CHANGELOG.md` 写入本轮变更条目（含 profile id rename 的 breaking note） |

## 不在本轮的范围

- `auth_weight` 11 档刻度重构为 (governance_layer, authority_kind) lattice — v1.x
- 补 4 个 state-resolution conformance vector — v1.x（_report.md M-09/M-10）
- core / extension constraint set 拆分（profile-gated）— 等 conformance suite 重构一并做
- _report.md 中其他 22 个 BLOCKING 项 — 后续 PR
