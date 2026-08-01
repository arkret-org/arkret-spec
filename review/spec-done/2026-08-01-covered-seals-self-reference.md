# `M` 包含消息自身的 `seal_ref` 使 E2EE DataEvent 恒不可发送

Status: closed (2026-08-01, same day)
Resolution: 问题成立，且比原报告更强——恒假性不只来自「Move 只能断言已存在的
Seal」这一惯例，还来自 Seal id 的内容寻址：`S.id = H(seal_canonical_bytes)` 覆盖
`delta[]` 与 `predecessor_refs[]`，`covered_set(S)` 中每个 Move 的 digest 都被
`S.id` 传递承诺，因此断言 `S.id` 的 Move 需要 hash 自指。原报告的 `max(...) < S`
写法预设 Seal 有全序，而 Seal 由 `predecessor_refs[]` 构成 DAG，正文改用祖先关系
表述。§2.5.2 已删除两处无条件加入 `S` 的措辞并补上 MUST NOT 条与构造性理由；
§2.5.1 新增 `covered_seal_refs` 可见性约束（每个元素 MUST 落在该 commit
`seal_basis` 的 predecessor closure 内，越界以 `governance_binding_mismatch`
拒绝），把「不可自指」从构造惯例升级为可机械检查的 normative 规则，同时堵住
producer 声称覆盖自己从未验证过的并发分支治理状态这条伪造路径；§2.5.2 另补
send-pause 解除路径，说明 gate 是有限等待而非死锁。mermaid、glossary、
migrating-from-matrix 与 conformance-profiles 中会被读成「seal_ref 指向自身已被
覆盖的 Seal」的措辞同步更正；新增 conformance vector
`ak.vector.mls.covered_seals_no_self_reference.v1`（vector-registry +
final-conformance-closure-fixture + AK-NC-011 evidence），其中一条断言直接禁止
fixture 用 `covered_seals ∋ S.id` 铺路。`artifact_pipeline check`、
`lint_spec`、`release_gate` 全绿。
遗留（实现侧，不是 spec gap）：`soland` 的 `validate_data_event_covered_seals`
已按新语义改为 `required_governance_seals_at`，但
`crates/server/tests/http_api/common.rs` 的测试 basis 仍把 grant cell 与
`covered_seals ∋ S.id` 写进同一个 Seal `S`。新语义下这些 grant cell 的
last-changing Move 由 `S` 收纳，故 `S ∈ M`，该 basis 依然只能靠那条不可构造的
自指 op 通过 gate。正确形态是两个 Seal：`S0` 承载治理写入，`S1` 收纳以
`covered_seal_refs=[S0]` 的 `ak.mls.genesis`，DataEvent 用 `seal_ref=S1`。
Detected by: S9 kanban/discussion E2EE 写入 live 修复（inkson → soland 全链路）
Affected surfaces: `encryption-and-audit.md` §2.5.2 的 `M` 定义与重建算法、
所有实现 E2EE application DataEvent `seal_ref` coverage gate 的 receiver、
`ak.mls.genesis` / `ak.mls.commit` 的 `covered_seal_refs` 语义

## 问题

§2.5.2「E2EE DataEvent 的 seal_ref 求值规则（normative）」把 `M` 定义为

> 包括消息 `seal_ref` 指向的 Seal、该 scope 最新 accepted membership / … frontier 所属的 Seal …

并在「`M` 的确定性重建算法（normative）」里再次要求

> 再加入消息自身的 `S` 与由这些 cell 触发、在 `S` 可见的最新 Realm/Circle cascade Seal。

覆盖判定是「`M` 中每一个元素都在**该 Seal view 下**的 `covered_seals_cell` 内」。
于是任何 E2EE application DataEvent 都要求 `S ∈ covered_seals_cell@J(S)`。

**该条件对任意 `S` 恒假。** 证明：

1. `covered_seals_cell` 的元素只来自 accepted `ak.mls.genesis` / `ak.mls.commit` 的
   `covered_seal_refs`（registry `or_set_batch_add`，§2.5.2 也只列这一个写入源）。
2. 一个 Control Move 只能断言它 authoring 时**已存在**的 Seal，因此对任一 commit `C`，
   `max(C.covered_seal_refs) < seal_of(C)`，其中 `seal_of(C)` 是首次把 `C` 纳入 accepted
   control state 的 Seal。
3. `J(S)` 由 `covered_set(S)` 决定，而 `covered_set(S)` 只含 `S` 及其祖先的 delta。
   任何 `C ∈ covered_set(S)` 满足 `seal_of(C) ≤ S`，结合 (2) 得
   `max(C.covered_seal_refs) < S`。
4. 故 `max(covered_seals_cell@J(S)) < S`，即 `S ∉ covered_seals_cell@J(S)`。∎

不存在「等一等再发」「换更新的 Seal 作 seal_ref」「先发一条 self-update commit 推进 epoch」
能绕开该结论：commit 自己也会生成新的 Seal，把 head 推到 `S+1`，下一条消息面对同样的不等式。
这是一个无限追赶，不是活性缺口。

## 实测

`soland` 的 `validate_data_event_covered_seals` 逐字实现了
`required_governance_seals = [seal_ref]`，live 环境下每条合规 MLS 密文稳定得到
`409 failed_precondition: mls_governance_binding_stale: covered_seals_cell does not
contain DataEvent seal_ref …`。

测试史上全绿是因为四份 fixture（`test-support/src/cba_basis.rs`、
`services/src/conformance_basis.rs`、`crates/server/tests/http_api/common.rs`、
`event_log_proof_strictness_tests.rs`）都在同一个 Seal `S` 的 sealed ops 里写入
`covered_seals ∋ S.id`，即上面 (2) 断言不可能出现的自指状态；`state_root` 还是在追加该 op
**之前**算的，所以连 fixture 自身都不自洽。

## `S ∈ M` 是多余的，不是必要的

`M` 的其余三组输入 (a) membership/device/lifecycle cell、(b) `policy_root` leaf 过滤集、
(c) `capability_root` leaf 过滤集，已经表达了 ban / revoke / policy 收紧的 send-pause 语义：

- `S` 上确实发生了治理变更时，该 cell 的 last-changing Move 的首次覆盖 Seal **就是 `S`**，
  `S` 由 (a)/(b)/(c) 自然进入 `M`，coverage 立即为假 → 暂停发送。这正是期望行为。
- `S` 上没有治理变更时（例如 `S` 只收纳了一条 `ak.mls.commit`，其写入的
  `mls.epoch` / `key_schedule` / `covered_seals` 三个 cell 都不在 (a)/(b)/(c) 中），
  无条件加入 `S` 只会产生上面证明的恒假条件。

因此「无条件加入 `S`」在**有**治理变更时是冗余的，在**无**治理变更时是致命的。

## 建议修正

1. §2.5.2 `M` 定义删除「包括消息 `seal_ref` 指向的 Seal」。
2. §2.5.2 重建算法删除「再加入消息自身的 `S`」。
3. 补一条 normative 说明：`S` MUST NOT 被无条件加入 `M`，并给出 `max(covered@S) < S`
   的构造性理由，避免实现者再按字面把 `S` 放回去。
4. §2.5 mermaid 中 `seal_ref: covered_seals_cell contains 自身 governance Seal`
   的措辞同步更正（"自身" 会被读成 `S` 自己）。

`M` 的其余部分、全称量化、单调增长、`contains` 只在 sealed control state 上求值、
producer 不得传入或删减 `M` 等规定全部保持不变。
