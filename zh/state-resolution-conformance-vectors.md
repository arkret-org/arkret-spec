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
