---
akp: AKP-0005
title: Workflow State Machine (per-Realm status)
normative: false
stability: v1
updated: 2026-05-25
status: deferred-to-v1.1
created: 2026-05-23
authors:
  - did:webvh:z8kSru9qAfd1G7AvcVjggdEKy:arkret.example
depends_on: [AKP-0002]
---

## 1. Summary

引入 per-Realm workflow profile 对象,声明 Realm 内某类 Strand 的精细业务状态机(Open → In Progress → In Review → Done 等),包含状态集合、合法转换边、转换所需 capability / Relation 前置条件。每个 workflow state 映射到协议级 stage bucket(common-fields §5.3.2 的 8 值),保持跨 Realm dashboard 可聚合。

## 2. Motivation

Jira 左栏有"Workflows"页;Linear 有 "Status";GitHub Projects 有 "Status field"。这些都是**用户可定义状态机**,业务上常常是:

```
Open → In Progress → In Review → QA → Done
                  ↘   Blocked   ↗
```

当前协议:Strand 顶层 `state`(active/archived/redacted)是物理生命周期;`stage`(common-fields §5.3,8 值固定)是**协议级粗粒度**业务进度;**没有 reducer-enforced 的精细 transition 矩阵**,业务状态硬塞进 `fields.status: string`,缺乏:

- 谁可以从哪个状态转到哪个状态
- 转换是否需要 entry hook(如必须有 reviewer)
- 业务 stage(`in_progress`)与具体 status(`In Code Review` vs `In QA`)的映射

## 3. Specification

### 3.1 Workflow profile 对象

Schema id: `ak.schema.workflow.v1`

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `workflow_key` | yes | `string` | `^[a-z][a-z0-9_]{0,63}$` | Realm 内稳定 workflow profile key。 |
| `realm_id` | yes | `id:realm` | — | 归属 Realm。 |
| `name` | yes | `string` | 1..128 chars。 | Workflow 显示名。 |
| `description` | no | `string` | ≤512 chars。 | 描述。 |
| `target_strand_type_ref` | no | `id:strand_type` | 见 [AKP-0002](./0002-strand-type.md)。 | 本 workflow 绑定的 strand_type。一个 strand_type 可有多个 workflow,但 strand_type profile 的 `allowed_workflow_key` 声明默认 / 唯一允许的那个。 |
| `states` | yes | `array<WorkflowState>` | 至少 2 个;包含恰好 1 个 `is_initial=true`。 | 见 §3.2。 |
| `transitions` | yes | `array<Transition>` | 至少 1 条。 | 见 §3.3。 |
| `state` | yes | `enum(active, archived, tombstoned)` | 同 common-fields §5。 | workflow 自身的物理生命周期。 |
| 公共字段 | — | — | created_by / created_at / updated_by / updated_at / state_changed_at | — |

### 3.2 `WorkflowState` 子结构

```json
{
  "key": "in_review",
  "label": "In Review",
  "description": "Awaiting reviewer approval",
  "color": { "palette": "purple" },
  "icon": { "emoji": "👀" },
  "stage_category": "in_progress",
  "is_initial": false,
  "is_terminal": false,
  "rank": "a020"
}
```

- `key` create-locked,workflow 内唯一
- `stage_category` ∈ common-fields §5.3.2 的 8 值之一;reducer 在 workflow transition 后**自动派生** Strand.stage 写入(单 transition 完成两件事:fine-grained 状态推进 + 协议级 stage 同步)
- `is_initial=true` 的状态恰好一个;`ak.strand.create` 引用了本 workflow 时,Strand 起始状态为该 state
- `is_terminal=true` 表示该状态是该 workflow 的"完结"(可有多个,如 `done` / `wont_fix` / `duplicate`)
- `rank` 用于 picker 显示顺序

### 3.3 `Transition` 子结构

```json
{
  "key": "submit_for_review",
  "label": "Submit for Review",
  "from_state_keys": ["in_progress"],
  "to_state_key": "in_review",
  "required_capability": "ak.workflow.transition",
  "preconditions": [
    {
      "kind": "relation_exists",
      "relation_kind": "assigned_to",
      "from_ref": "$strand",
      "min_count": 1
    },
    {
      "kind": "field_filled",
      "field_def_ref": "ak:field_def:<reviewer-field>"
    }
  ],
  "on_enter_event": null
}
```

- `from_state_keys[]` 允许从多个源状态进入同一目标
- `preconditions` 是 reducer-evaluated 的事实条件:
  - `relation_exists`:对象上有某种 Relation(如必须有 assignee)
  - `field_filled`:某个 field_def(AKP-0003)有非空值
  - `child_workflow_state`:所有 sub-task 都处于某状态(用于 parent 必须等子任务完成)
- `required_capability`:除了 base `ak.strand.workflow.transition` 之外的额外 capability action(可空)
- `on_enter_event`:profile-declared 副作用 event(可空;v1 不强制定义可触发集合,留作 profile 扩展)

### 3.4 Strand 顶层新增字段

| 字段 | 必填 | 类型 | 约束 |
| --- | --- | --- | --- |
| `workflow_state_ref` | conditional | `{ workflow_key, state_key }` | 当 Strand 关联的 strand_type 声明 `allowed_workflow_key` 时必填;reducer 写入只能通过 `ak.strand.workflow.transition`。 |

### 3.5 Event 家族

| event kind | reducer_input | 说明 |
| --- | --- | --- |
| `ak.workflow.create` | yes | 创建 workflow |
| `ak.workflow.update` | yes | patch states / transitions(限制:不可删除已被 Strand 引用的 state;改 transition 走 §3.6 规则) |
| `ak.workflow.archive` | yes | active → archived |
| `ak.workflow.restore` | yes | archived → active |
| `ak.workflow.tombstone` | yes | terminal |
| `ak.strand.workflow.transition` | yes | **核心**:推进 Strand 的 workflow_state_ref;reducer 校验合法 transition + preconditions;成功后自动派生 Strand.stage |

### 3.6 Reducer 校验流程(`ak.strand.workflow.transition`)

1. 解析 payload: `{strand_id, transition_key, expected_state_key?}`
2. 取 Strand.workflow_state_ref → 找当前 state
3. 找 transition where `transition.key == payload.transition_key && current_state ∈ transition.from_state_keys`;否则 `failed_precondition`,`reason="workflow_transition_not_allowed"`
4. 若 `expected_state_key` 提供 → 与当前 state CAS 比较,不匹配 `failed_precondition`,`reason="workflow_state_cas_mismatch"`
5. 校验 `transition.preconditions[]` 全部满足;否则 `failed_precondition`,`reason="workflow_precondition_unmet"` + 具体哪条
6. 校验 actor 持有 `ak.strand.workflow.transition` 基础 capability **AND** `transition.required_capability`(若有)
7. 校验 Strand.state=active(共用 `ak.strand.update` 的 non-active 拒写规则)
8. 写入 cell:`ak.component.strand.workflow_state.v1` cas_register,head_eq precondition
9. 自动派生 `Strand.stage = target_state.stage_category`,通过同一 reducer transaction 触发"内部" stage 更新(**不**对外暴露为单独的 `ak.strand.stage.set` event;那个仍是 actor 直接推进 stage 的路径)
10. 写入 `Strand.workflow_state_ref.state_key = target_state.key`

### 3.7 与 stage 轴的关系

- **未启用本提案的 Realm**:actor 直接 `ak.strand.stage.set` 推进 8 值 stage(common-fields §5.3)
- **启用本提案的 Realm 且 Strand 关联了 workflow**:
  - 客户端 SHOULD 走 `ak.strand.workflow.transition`;此 event 推进 fine-grained state 并自动同步 stage
  - 直接调用 `ak.strand.stage.set` 仍合法(protocol 不阻止),但 profile MAY 收紧拒绝(`ak.profile.workflow.strict_stage_routing.v1`),只允许 stage 通过 workflow transition 派生
- stage 8 值始终是 workflow_state 的**协议级粗投影**,跨 Realm 聚合不依赖业务命名

### 3.8 Capability

| action | risk_tier | target event kinds |
| --- | --- | --- |
| `ak.workflow.manage` | medium | create / update / archive / restore / tombstone |
| `ak.strand.workflow.transition` | low | `ak.strand.workflow.transition`(基础推进权限,profile 可叠加 transition-specific capability) |

## 4. Interactions with normative spec

- 新增文件:`spec/v1/zh/models/workflow.md`。
- 新增 schema:`workflow.schema.json`、`strand-workflow-transition-payload`。
- 新增 id-kind:`workflow`。
- 新增 event_kinds(6 条)+ capability actions(2 条 + profile 扩展位)。
- 新增 profile:`ak.profile.workflow.v1`,strict variant `ak.profile.workflow.strict_stage_routing.v1`。
- `strand.schema.json` 增加 `workflow_state_ref` optional property。
- common-fields §5.3.4 已经预留了"启用 workflow 后 stage 派生"的描述,本提案落地时补充具体引用。
- forbidden-wire:`strand.fields.status`(可选;启用 workflow 后该字段保留为 free-form 元数据,reducer 仍允许,但 profile 可声明 strict reject)。

## 5. Rationale & alternatives

### 5.1 为什么不直接用协议级 stage 做精细化?

候选 A:把 stage enum 从 8 值扩展到 ~20 个细粒度状态。

否决理由:
- stage 是跨 Realm dashboard 聚合的固定 vocabulary;每加一个值都是 wire-breaking change
- 不同 Realm 的"In Review" 语义差别极大(Code Review vs Legal Review vs UX Review),协议级 enum 无法表达
- Linear 的 status / Jira 的 status / GitHub Projects 的 status 都是 per-project 可定义的

### 5.2 为什么不用 `fields.status: string` 完成?

- 没有 reducer-enforced 转换矩阵(任意覆写)
- 没有 capability 切分(每个 transition 不同权限)
- 没有 precondition 校验(assignee 必须存在才能 in_progress 等)
- 没有 audit 区分"改字段" vs "推进状态"
- 不能与协议级 stage 自动派生关联

### 5.3 为什么 transition 是 first-class event 而不是 `ak.strand.update`?

清洁 audit、capability 切分、reducer 校验流程分离。与 stage.set / tracks.update 同模式:状态机推进有自己的 event kind,patch 路径 forbidden。

## 6. Open questions

- [ ] precondition 类型集合具体多大?草案给出 3 种(relation_exists / field_filled / child_workflow_state),还需要"sub-strands all in terminal"、"depends_on resolved" 等。建议 v1 给最小集合,profile 可扩。
- [ ] `on_enter_event` 是否在 v1 范围?有 side-effect / loop 风险,建议 v1 不提供,留给 profile。
- [ ] workflow update 时如何处理已有 Strand 上的状态?例如改 state 的 stage_category 是否反向 backfill?默认不 backfill(只影响新 transition),audit log 留底。
- [ ] 一个 strand_type 是否可以绑定多个 workflow(让不同 Space 用不同 workflow)?目前设计是 strand_type 声明默认 / 唯一,但 Realm 内多 workflow 共存 + Strand 显式指定也合理。
- [ ] 跨 Realm workflow 复用(template marketplace)?postpone。

## 7. Migration plan

(accepted 阶段填)

## 8. References

- Jira Workflows: <https://support.atlassian.com/jira-cloud-administration/docs/work-with-issue-workflows/>
- Linear Workflows: <https://linear.app/docs/configuring-workflows>
- GitHub Projects status field
- AKP-0002 Strand Type(workflow 的 type 锚点)
- common-fields.md §5.3 stage 轴(workflow 的协议级 stage 派生目标)
