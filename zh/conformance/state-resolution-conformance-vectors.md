# State Resolution Conformance Vectors

## 1. 目标

本文件把 `event-auth-state-resolution.md` 的 state resolution 与冲突裁决规则转成可复现向量。当前向量按 Subject / Room / Board / List / Card / Message / Morph 模型定义，不包含旧 `Entity` 兼容性要求。

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
- State key: `did:uuid:bob`
- Candidate A: `cx.member.state` -> `join`
- Candidate B: `cx.member.state` -> `ban`

期望：

- 若 Candidate B 由有效 ban capability 授权，`ban` MUST win。
- 被压制候选进入 `conflict_records`。

## 3. Vector: 并发 Room Membership 冲突

向量名称：

```text
cx.vector.state_resolution.conflict_room_membership.v1
```

输入：

- Room: `cx:room:01js0r00000000000000000000`
- State key: `cx:room:01js0r00000000000000000000|did:uuid:bob`
- Candidate A: `cx.room.member` -> `join`
- Candidate B: `cx.room.member` -> `leave`

期望：

- Room membership 只影响该 Room。
- 结果不得改变 Space membership、Card visibility 或 Board visibility。
- 若 `leave` 是 actor 自己发起且授权有效，`leave` wins。

## 4. Vector: 并发 Card Move

向量名称：

```text
cx.vector.state_resolution.concurrent_card_move.v1
```

输入：

```json
{
  "base": {
    "card_id": "cx:card:01js0ca0000000000000000000",
    "list_id": "cx:list:01js0111000000000000000000",
    "rank": "U"
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0ev1000000000000000000",
      "kind": "cx.card.move",
      "content": {
        "board_id": "cx:board:01js0bd0000000000000000000",
        "card_id": "cx:card:01js0ca0000000000000000000",
        "to_list_id": "cx:list:01js0112000000000000000000",
        "rank": "U"
      },
      "hlc": "01970e589d21-0001-a13f9c2e"
    },
    {
      "event_id": "cx:event:01js0ev2000000000000000000",
      "kind": "cx.card.move",
      "content": {
        "board_id": "cx:board:01js0bd0000000000000000000",
        "card_id": "cx:card:01js0ca0000000000000000000",
        "to_list_id": "cx:list:01js0113000000000000000000",
        "rank": "U"
      },
      "hlc": "01970e589d21-0002-a13f9c2e"
    }
  ]
}
```

期望：

- 授权都有效时，reducer MUST 使用 deterministic tie-breaker 选择一个最终 Card position。
- 失败候选不应生成第二个 Card 副本。
- 最终位置 key 为 `(board_id, card_id)`，不是 `(list_id, card_id)`。

## 5. Vector: Card Linked Room 不继承权限

向量名称：

```text
cx.vector.state_resolution.card_linked_room_auth.v1
```

输入：

- Candidate A: `cx.card.link_room(card_id, room_id, primary=false)`
- Viewer has `cx.card.read` on Card.
- Viewer has no `cx.room.member` for linked Room.

期望：

- Relation is accepted if author has card link capability and can reference the target Room.
- Viewer can see only a lazy Room reference or locked state.
- Viewer cannot read linked Room Message events.

## 6. Vector: Subject Surface 不继承权限

向量名称：

```text
cx.vector.state_resolution.subject_surface_auth.v1
```

输入：

- Candidate A: `cx.subject.link_surface(subject_id, surface_ref=room_id, surface_role=primary_discussion, primary=true)`
- Viewer has `cx.subject.read` on Subject.
- Viewer has no `cx.room.member` for linked Room.

期望：

- Relation is accepted if author has subject surface capability and can reference the target Room.
- Viewer can see only a locked surface stub, authorized hidden count, or no surface entry depending on Room discoverability.
- Viewer cannot read linked Room Message events.
- Room membership, Card visibility, and Subject update rights are unchanged.
