# State Resolution Conformance Vectors

## 1. 目标

本文件把 `event-auth-state-resolution.md` 的 state resolution 与冲突裁决规则转成可复现向量。当前向量按 Space、Flow（含 branch primary 标记）、Space(kind=board/list) 容器、Message、Morph、Relation 和 View 模型定义。

实现必须对每个向量输出：

- `vector_id`
- `input`
- `resolved_state`
- `conflict_records`
- `transcript_order`

除另有说明，测试均在 `space_version = "1"` 下执行。

## 2. Vector: 并发 Space Membership 冲突

向量名称：

```text
cx.vector.state_resolution.conflict_space_membership.v1
```

输入：

- Space: `cx:space:01js0ms0000000000000000000`
- State key: `did:web:bob.example.com`
- Candidate A: `cx.member.state` -> `join`
- Candidate B: `cx.member.state` -> `ban`

期望：

- 若 Candidate B 由有效 ban capability 授权，`ban` MUST win。
- 被压制候选进入 `conflict_records`。

## 3. Vector: 并发 Branch-Scoped Discussion Membership 冲突

向量名称：

```text
cx.vector.state_resolution.conflict_flow_discussion_membership.v1
```

输入：

- Flow discussion: `cx:flow:01js0r00000000000000000000`
- State key: `cx:flow:01js0r00000000000000000000|discussion|did:web:bob.example.com`
- Candidate A: `cx.flow.branch.member` -> `join`
- Candidate B: `cx.flow.branch.member` -> `leave`

期望：

- Branch-scoped discussion membership 只影响该 Flow discussion。
- 结果不得改变 Space membership、Flow synthesis visibility 或 Space(kind=board) visibility。
- 若 `leave` 是 actor 自己发起且授权有效，`leave` wins。

## 4. Vector: 并发 Flow Card Move

向量名称：

```text
cx.vector.state_resolution.concurrent_flow_card_move.v1
```

输入：

```json
{
  "base": {
    "flow_id": "cx:flow:01js0ca0000000000000000000",
    "list_id": "cx:space:01js0111000000000000000000",
    "rank": "U"
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0ev1000000000000000000",
      "kind": "cx.flow.move",
      "content": {
        "board_id": "cx:space:01js0bd0000000000000000000",
        "flow_id": "cx:flow:01js0ca0000000000000000000",
        "to_list_id": "cx:space:01js0112000000000000000000",
        "rank": "U"
      },
      "hlc": "01970e589d21-0001-a13f9c2e"
    },
    {
      "event_id": "cx:event:01js0ev2000000000000000000",
      "kind": "cx.flow.move",
      "content": {
        "board_id": "cx:space:01js0bd0000000000000000000",
        "flow_id": "cx:flow:01js0ca0000000000000000000",
        "to_list_id": "cx:space:01js0113000000000000000000",
        "rank": "U"
      },
      "hlc": "01970e589d21-0002-a13f9c2e"
    }
  ]
}
```

期望：

- 授权都有效时，reducer MUST 使用 deterministic tie-breaker 选择一个最终 Flow item position。
- 失败候选不应生成第二个 Flow 副本。
- 最终位置 key 为 `(board_id, flow_id)`，不是 `(list_id, flow_id)`。

## 5. Vector: Flow Discussion Branch-Scoped Override 不继承权限

向量名称：

```text
cx.vector.state_resolution.flow_discussion_visibility.v1
```

输入：

- Candidate A: `cx.flow.branch.enable(flow_id, branch_kind=discussion, primary=true)`
- Viewer has `cx.flow.read` on Flow.
- Discussion access override sets `membership=branch_scoped`.
- Viewer has no `cx.flow.branch.member` for the discussion branch.

期望：

- Branch is accepted if author has the required flow branch capability.
- Viewer can see only a lazy discussion reference or locked state.
- Viewer cannot read discussion Message events.

## 6. Vector: Flow Discussion Surface Branch-Scoped Override 不继承权限

向量名称：

```text
cx.vector.state_resolution.flow_discussion_surface_auth.v1
```

输入：

- Candidate A: `cx.flow.branch.enable(flow_id, branch_kind=discussion, primary=true)`
- Viewer has `cx.flow.read` on Flow.
- Discussion access override sets `membership=branch_scoped`.
- Viewer has no `cx.flow.branch.member` for the discussion branch.

期望：

- Branch is accepted if author has the required flow branch capability.
- Viewer can see only a locked discussion stub, authorized hidden count, or no surface entry depending on discussion discoverability.
- Viewer cannot read discussion Message events.
- Branch-scoped discussion membership, Flow synthesis visibility, and Flow update rights are unchanged.
