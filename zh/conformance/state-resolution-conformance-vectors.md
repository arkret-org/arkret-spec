# State Resolution Conformance Vectors

## 1. 目标

本文件把 `event-auth-state-resolution.md` 的 state resolution 与冲突裁决规则转成可复现向量。  
实现必须对每个向量输出：

- `vector_id`
- `input`（事件集）
- `resolved_state`
- `conflict_records`
- `transcript_order`

除另有说明，测试均在 `space_version = "1"` 下执行。

## 2. 通用向量元数据

向量命名：

```text
cx.vector.state_resolution.<scenario>.v1
```

每个向量均要求：

- 解析输入事件前先通过 canonical validation / schema / signature / auth refs。
- 将并发分支写入 reducer，再按 `event-auth-state-resolution.md` 的优先级与 tie-breaker 得到 resolved state。
- 输出必须在不同节点（repo/index）保持一致的 event ordering 与 conflict 记录。

## 3. Vector: 并发 Membership 冲突

向量名称：

```text
cx.vector.state_resolution.conflict_membership.v1
```

输入：

- Space: `cx:space:01js0ms000000000000000000`
- 并发 membership 事件（都指向同一 state key）：

```json
{
  "base_state": {
    "event_id": "cx:event:01js0base000000000000000000",
    "kind": "cx.member.state",
    "state_key": "did:uuid:alice",
    "content": {
      "membership": "join",
      "via": ["did:web:admin.example"],
      "membership_epoch": "m_9"
    }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0m1b000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_a",
      "hlc": "01970e589d21-0004-a13f9c2e",
      "causal_depth": 10,
      "content": { "membership": "ban", "reason": "policy" },
      "auth_refs": ["cx:event:01js0auth101", "cx:event:01js0mem01"],
      "prev_refs": ["cx:event:01js0p01"]
    },
    {
      "event_id": "cx:event:01js0m1a000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_b",
      "hlc": "01970e589d21-0004-a13f9d2e",
      "causal_depth": 10,
      "content": { "membership": "leave", "reason": "requested" },
      "auth_refs": ["cx:event:01js0auth102", "cx:event:01js0mem01"],
      "prev_refs": ["cx:event:01js0p01"]
    },
    {
      "event_id": "cx:event:01js0m1c000000000000000000",
      "kind": "cx.member.state",
      "state_key": "did:uuid:alice",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:admin_c",
      "hlc": "01970e589d21-0004-a13f9f2e",
      "causal_depth": 10,
      "content": { "membership": "invite", "reason": "recovery" },
      "auth_refs": ["cx:event:01js0auth103", "cx:event:01js0mem01"],
      "prev_refs": ["cx:event:01js0p01"]
    }
  ],
  "auth_state": {
    "admin_a": "creator",
    "admin_b": "admin",
    "admin_c": "member"
  }
}
```

期望输出：

- resolved membership state winner：

```json
{
  "membership": "ban",
  "membership_epoch": "m_10",
  "source_event_id": "cx:event:01js0m1b000000000000000000"
}
```

- conflict_records（不完整示例）：

```json
[
  {
    "state_key": "did:uuid:alice",
    "state_candidates": [
      "cx:event:01js0m1b000000000000000000",
      "cx:event:01js0m1a000000000000000000",
      "cx:event:01js0m1c000000000000000000"
    ],
    "winner": "cx:event:01js0m1b000000000000000000",
    "reason": "higher priority class + tie break (causal_depth/hlc/event_id)"
  }
]
```

判定要点：

- 退回 base state 的条件是：winner 及所有候选都未通过 auth。
- 同级候选必须保持 deterministic tie-break。
- `event_id` 只在同一 auth class、causal_depth、hlc 完全一致时参与最终排序。

## 4. Vector: capability 依赖的 capability rebind 冲突

向量名称：

```text
cx.vector.state_resolution.capability_rebind.v1
```

输入：同一 `(kind,state_key)` 的能力重绑并发流。

```json
{
  "base_state": {
    "kind": "cx.capability.grant",
    "state_key": "cap-chan-post",
    "content": {
      "subject": "did:uuid:alice",
      "actions": ["message.send"],
      "capability_id": "cap-chan-post",
      "state": "active"
    }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0g1e000000000000000000",
      "kind": "cx.capability.grant",
      "state_key": "cap-chan-post",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:moderator_1",
      "hlc": "01970e589d22-0001-11111111",
      "causal_depth": 8,
      "content": {
        "subject": "did:uuid:alice",
        "scope": "space:01js0ms000000000000000000",
        "actions": ["message.send"]
      },
      "auth_refs": ["cx:event:01js0grant_admin", "cx:event:01js0capbase"],
      "prev_refs": ["cx:event:01js0capbase"]
    },
    {
      "event_id": "cx:event:01js0r1e000000000000000000",
      "kind": "cx.capability.revoke",
      "state_key": "cap-chan-post",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:member_x",
      "hlc": "01970e589d22-0001-22222222",
      "causal_depth": 9,
      "content": {
        "target_capability_id": "cap-chan-post"
      },
      "auth_refs": ["cx:event:01js0revoke_admin"],
      "prev_refs": ["cx:event:01js0g1e000000000000000000"]
    },
    {
      "event_id": "cx:event:01js0g1f000000000000000000",
      "kind": "cx.capability.grant",
      "state_key": "cap-chan-post",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:moderator_2",
      "hlc": "01970e589d22-0001-33333333",
      "causal_depth": 9,
      "content": {
        "subject": "did:uuid:alice",
        "scope": "space:01js0ms000000000000000000",
        "actions": ["message.send", "message.react"]
      },
      "auth_refs": ["cx:event:01js0grant_admin", "cx:event:01js0capbase"],
      "prev_refs": ["cx:event:01js0r1e000000000000000000"]
    }
  ]
}
```

期望输出：

```json
{
  "resolved_state": {
    "kind": "cx.capability.grant",
    "state_key": "cap-chan-post",
    "content": {
      "subject": "did:uuid:alice",
      "actions": ["message.send", "message.react"]
    },
    "source_event_id": "cx:event:01js0g1f000000000000000000"
  },
  "conflict_records": [
    {
      "state_key": "cap-chan-post",
      "state_candidates": [
        "cx:event:01js0g1e000000000000000000",
        "cx:event:01js0r1e000000000000000000",
        "cx:event:01js0g1f000000000000000000"
      ],
      "winner": "cx:event:01js0g1f000000000000000000",
      "reason": "capability grant/revoke in same family: revoke loses to causally newer valid re-grant"
    }
  ]
}
```

判定要点：

- 若候选 revoke 缺少有效 `revoke` 授权，不能阻断随后 re-grant。
- 即便 revoke 和 re-grant 并发，较新且 auth 合法的 re-grant 可覆盖 revoke。

## 5. Vector: 空间治理 state（schema）并发冲突

向量名称：

```text
cx.vector.state_resolution.schema_update.v1
```

输入：

```json
{
  "base_state": {
    "kind": "cx.space.policy",
    "state_key": "space_policy",
    "content": {
      "max_message_length": 4096,
      "allow_file_types": ["jpg", "png"]
    }
  },
  "candidates": [
    {
      "event_id": "cx:event:01js0s1a000000000000000000",
      "kind": "cx.space.policy",
      "state_key": "space_policy",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:web:adminspace.example",
      "hlc": "01970e589d23-0010-11111111",
      "causal_depth": 12,
      "content": {
        "max_message_length": 1024,
        "allow_file_types": ["jpg"]
      },
      "auth_refs": ["cx:event:01js0policy_admin"],
      "prev_refs": ["cx:event:01js0polbase"]
    },
    {
      "event_id": "cx:event:01js0s1b000000000000000000",
      "kind": "cx.space.policy",
      "state_key": "space_policy",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:web:adminspace.example",
      "hlc": "01970e589d23-0010-22222222",
      "causal_depth": 12,
      "content": {
        "max_message_length": 2048,
        "allow_file_types": ["jpg", "png", "pdf"]
      },
      "auth_refs": ["cx:event:01js0policy_admin"],
      "prev_refs": ["cx:event:01js0polbase"]
    }
  ]
}
```

期望：

- `causal_depth` 相同、同一优先级类时按 `hlc` 较大者胜出。
- expected winner：

```json
{
  "kind": "cx.space.policy",
  "state_key": "space_policy",
  "content": {
    "max_message_length": 2048,
    "allow_file_types": ["jpg", "png", "pdf"]
  },
  "source_event_id": "cx:event:01js0s1b000000000000000000"
}
```

失败判定：

- 直接用 `event_seq`（本地接收顺序）进行并发决断。
- 忽略 conflict record 的返回（审计不可复现）。

## 6. Vector: Board 并发项目移动冲突

向量名称：

```text
cx.vector.state_resolution.board_concurrent_item_move.v1
```

输入：

```json
{
  "base_state": {
    "scope_container_id": "cx:entity:01js0bd000000000000000000",
    "relation_kind": "contains",
    "entity_id": "cx:entity:01js0tk000000000000000000",
    "container_id": "cx:entity:01js0c1000000000000000000",
    "rank": "h0",
    "relation_id": "cx:relation:01js0r1000000000000000000"
  },
  "candidates": [
    {
      "operation_id": "cx:operation:01js0mv1000000000000000000",
      "kind": "cx.container.move_item",
      "actor_id": "did:web:alice.example",
      "hlc": "01970e589d24-0001-11111111",
      "auth_weight": 10,
      "content": {
        "scope_container_id": "cx:entity:01js0bd000000000000000000",
        "relation_kind": "contains",
        "entity_id": "cx:entity:01js0tk000000000000000000",
        "from_container_id": "cx:entity:01js0c1000000000000000000",
        "to_container_id": "cx:entity:01js0c2000000000000000000",
        "rank": "mV"
      }
    },
    {
      "operation_id": "cx:operation:01js0mv2000000000000000000",
      "kind": "cx.container.move_item",
      "actor_id": "did:web:bob.example",
      "hlc": "01970e589d24-0002-22222222",
      "auth_weight": 10,
      "content": {
        "scope_container_id": "cx:entity:01js0bd000000000000000000",
        "relation_kind": "contains",
        "entity_id": "cx:entity:01js0tk000000000000000000",
        "from_container_id": "cx:entity:01js0c1000000000000000000",
        "to_container_id": "cx:entity:01js0c3000000000000000000",
        "rank": "p0"
      }
    }
  ]
}
```

期望输出：

```json
{
  "resolved_position": {
    "scope_container_id": "cx:entity:01js0bd000000000000000000",
    "relation_kind": "contains",
    "entity_id": "cx:entity:01js0tk000000000000000000",
    "container_id": "cx:entity:01js0c3000000000000000000",
    "rank": "p0",
    "source_operation_id": "cx:operation:01js0mv2000000000000000000"
  },
  "conflict_records": [
    {
      "conflict_type": "exclusive_position",
      "state_key": "cx:entity:01js0bd000000000000000000|contains|cx:entity:01js0tk000000000000000000",
      "winner": "cx:operation:01js0mv2000000000000000000",
      "losers": ["cx:operation:01js0mv1000000000000000000"],
      "reason": "same auth weight; later HLC wins by deterministic operation order"
    }
  ]
}
```

判定要点：

- 最终 reduced state MUST 只有一个 active position edge。
- loser 不得继续作为 active containment 出现在普通 board projection 中。
- 审计输出 MUST 保留 loser operation 和冲突原因。

## 7. Vector: 字段位置原子移动

向量名称：

```text
cx.vector.state_resolution.board_atomic_field_position_move.v1
```

输入：

```json
{
  "base_state": {
    "view_id": "cx:view:01js0vw000000000000000000",
    "entity_id": "cx:entity:01js0tk000000000000000000",
    "group_by": "fields.status",
    "value": "todo",
    "rank": "h0",
    "source_operation_id": "cx:operation:01js0base00000000000000000"
  },
  "candidates": [
    {
      "operation_id": "cx:operation:01js0tm1000000000000000000",
      "kind": "cx.field_position.move",
      "actor_id": "did:web:alice.example",
      "hlc": "01970e589d25-0001-11111111",
      "auth_weight": 10,
      "content": {
        "entity_id": "cx:entity:01js0tk000000000000000000",
        "view_id": "cx:view:01js0vw000000000000000000",
        "group_by": "fields.status",
        "to_value": "review",
        "rank": "mV"
      }
    },
    {
      "operation_id": "cx:operation:01js0tm2000000000000000000",
      "kind": "cx.field_position.move",
      "actor_id": "did:web:bob.example",
      "hlc": "01970e589d25-0002-22222222",
      "auth_weight": 10,
      "content": {
        "entity_id": "cx:entity:01js0tk000000000000000000",
        "view_id": "cx:view:01js0vw000000000000000000",
        "group_by": "fields.status",
        "to_value": "done",
        "rank": "p0"
      }
    }
  ]
}
```

期望输出：

```json
{
  "resolved_position": {
    "view_id": "cx:view:01js0vw000000000000000000",
    "entity_id": "cx:entity:01js0tk000000000000000000",
    "group_by": "fields.status",
    "value": "done",
    "rank": "p0",
    "source_operation_id": "cx:operation:01js0tm2000000000000000000"
  },
  "conflict_records": [
    {
      "conflict_type": "atomic_position_register",
      "state_key": "cx:view:01js0vw000000000000000000|cx:entity:01js0tk000000000000000000|fields.status",
      "winner": "cx:operation:01js0tm2000000000000000000",
      "losers": ["cx:operation:01js0tm1000000000000000000"],
      "reason": "same auth weight; later HLC wins by deterministic operation order"
    }
  ]
}
```

判定要点：

- 两个并发 `cx.field_position.move` 写入同一 `(view_id, entity_id, group_by)` 时，`to_value` 和 `rank` MUST 来自同一个 winner。
- 实现不得输出 `status` 来自 operation A、`rank` 来自 operation B 的混合位置。
- 若客户端用裸 `cx.entity.update` 同时写 `fields.status` 与 `fields.rank` 且未声明 `atomic_position`，实现 MAY 按普通 scalar LWW 处理，但不得声称通过本向量。

## 8. Vector: Container Rebalance Assignment

向量名称：

```text
cx.vector.state_resolution.container_rebalance_assignment.v1
```

输入：

```json
{
  "base_state": {
    "scope_container_id": "cx:entity:01js0bd0000000000000000000",
    "container_id": "cx:entity:01js0c2000000000000000000",
    "relation_kind": "contains",
    "state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "active_edges": [
      {
        "relation_id": "cx:relation:01js0r1000000000000000000",
        "entity_id": "cx:entity:01js0tk1000000000000000000",
        "rank": "a0",
        "rank_source_operation_id": "cx:operation:01js0aa1000000000000000000"
      },
      {
        "relation_id": "cx:relation:01js0r2000000000000000000",
        "entity_id": "cx:entity:01js0tk2000000000000000000",
        "rank": "a00",
        "rank_source_operation_id": "cx:operation:01js0aa2000000000000000000"
      },
      {
        "relation_id": "cx:relation:01js0r3000000000000000000",
        "entity_id": "cx:entity:01js0tk3000000000000000000",
        "rank": "a000",
        "rank_source_operation_id": "cx:operation:01js0aa3000000000000000000"
      }
    ]
  },
  "operation": {
    "operation_id": "cx:operation:01js0rb1000000000000000000",
    "kind": "cx.container.rebalance",
    "actor_id": "did:web:alice.example",
    "hlc": "01970e589d26-0001-11111111",
    "auth_weight": 10,
    "content": {
      "scope_container_id": "cx:entity:01js0bd0000000000000000000",
      "container_id": "cx:entity:01js0c2000000000000000000",
      "relation_kind": "contains",
      "expected_state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
      "assignments": [
        {
          "relation_id": "cx:relation:01js0r1000000000000000000",
          "entity_id": "cx:entity:01js0tk1000000000000000000",
          "rank": "F"
        },
        {
          "relation_id": "cx:relation:01js0r2000000000000000000",
          "entity_id": "cx:entity:01js0tk2000000000000000000",
          "rank": "V"
        },
        {
          "relation_id": "cx:relation:01js0r3000000000000000000",
          "entity_id": "cx:entity:01js0tk3000000000000000000",
          "rank": "k"
        }
      ]
    }
  }
}
```

期望输出：

```json
{
  "resolved_ordered_set": [
    {
      "relation_id": "cx:relation:01js0r1000000000000000000",
      "entity_id": "cx:entity:01js0tk1000000000000000000",
      "rank": "F",
      "rank_source_operation_id": "cx:operation:01js0rb1000000000000000000"
    },
    {
      "relation_id": "cx:relation:01js0r2000000000000000000",
      "entity_id": "cx:entity:01js0tk2000000000000000000",
      "rank": "V",
      "rank_source_operation_id": "cx:operation:01js0rb1000000000000000000"
    },
    {
      "relation_id": "cx:relation:01js0r3000000000000000000",
      "entity_id": "cx:entity:01js0tk3000000000000000000",
      "rank": "k",
      "rank_source_operation_id": "cx:operation:01js0rb1000000000000000000"
    }
  ],
  "conflict_records": []
}
```

判定要点：

- Assignment rank MUST 与 `encoding.md` 的 `cx.rank.lexofractional.v1` rebalance 公式一致。
- Rebalance 不得改变三个 active edge 的相对顺序，不得新增、删除或移动 membership。
- assignments MUST 覆盖目标 container 的全部 active edges；遗漏任一 active edge MUST 使 operation 失败。

## 9. Vector: Container Rebalance CAS Conflict

向量名称：

```text
cx.vector.state_resolution.container_rebalance_cas_conflict.v1
```

输入：

```json
{
  "base_state": {
    "scope_container_id": "cx:entity:01js0bd0000000000000000000",
    "container_id": "cx:entity:01js0c2000000000000000000",
    "relation_kind": "contains",
    "state_hash": "sha256:2222222222222222222222222222222222222222222222222222222222222222",
    "active_edges": [
      {
        "relation_id": "cx:relation:01js0r1000000000000000000",
        "entity_id": "cx:entity:01js0tk1000000000000000000",
        "rank": "a0"
      },
      {
        "relation_id": "cx:relation:01js0r2000000000000000000",
        "entity_id": "cx:entity:01js0tk2000000000000000000",
        "rank": "a00"
      }
    ]
  },
  "operation": {
    "operation_id": "cx:operation:01js0rb2000000000000000000",
    "kind": "cx.container.rebalance",
    "content": {
      "scope_container_id": "cx:entity:01js0bd0000000000000000000",
      "container_id": "cx:entity:01js0c2000000000000000000",
      "relation_kind": "contains",
      "expected_state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
      "assignments": [
        {
          "relation_id": "cx:relation:01js0r1000000000000000000",
          "entity_id": "cx:entity:01js0tk1000000000000000000",
          "rank": "F"
        },
        {
          "relation_id": "cx:relation:01js0r2000000000000000000",
          "entity_id": "cx:entity:01js0tk2000000000000000000",
          "rank": "V"
        }
      ]
    }
  }
}
```

期望输出：

```json
{
  "rejected_operation_id": "cx:operation:01js0rb2000000000000000000",
  "reason": "cas_conflict",
  "resolved_ordered_set": [
    {
      "relation_id": "cx:relation:01js0r1000000000000000000",
      "entity_id": "cx:entity:01js0tk1000000000000000000",
      "rank": "a0"
    },
    {
      "relation_id": "cx:relation:01js0r2000000000000000000",
      "entity_id": "cx:entity:01js0tk2000000000000000000",
      "rank": "a00"
    }
  ]
}
```

判定要点：

- `expected_state_hash` 与当前 canonical ordered set hash 不一致时 MUST fail closed。
- Reducer 不得部分应用 `assignments`。
- projection 层不得把 CAS 失败解释为卡片删除或权限裁剪。
