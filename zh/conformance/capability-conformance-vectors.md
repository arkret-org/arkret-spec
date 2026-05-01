# Capability Conformance Vectors

## 1. 目标

本文件将 capability 的链式授权、撤销回滚与审批约束固定为跨实现向量。  
适配对象：`identity-registry`, `principal_server_repo_api`, `e2ee_client`, `enterprise_client`, `agent_runtime`.

向量命名：

```text
cx.vector.capability.<scenario>.v1
```

每个向量应检查：

- selector scope 是否正确绑定到 actor/device/space/action。
- 授权时间窗约束是否导致一致结果。
- 关键路径必须拒绝 `authorization-only` 假阳性。

## 2. Vector: 多级委托链

向量名称：

```text
cx.vector.capability.delegate_chain.v1
```

输入事件链：

```json
{
  "base": {
    "kind": "cx.capability.grant",
    "state_key": "space-admin",
    "subject": "did:uuid:root_admin",
    "actions": ["cx.space.admin"],
    "constraints": []
  },
  "delegations": [
    {
      "event_id": "cx:event:01js0d1g000000000000000000",
      "kind": "cx.capability.delegate",
      "state_key": "space-admin-delegate-a",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:root_admin",
      "content": {
        "source_capability": "space-admin",
        "subject": "did:uuid:ops",
        "scope": "space:01js0ms000000000000000000",
        "actions": ["cx.capability.*", "cx.invite.create"],
        "constraints": [
          {
            "constraint_type": "temporal",
            "effect": "allow",
            "not_before": "2026-04-20T00:00:00Z",
            "expires_at": "2026-05-20T00:00:00Z"
          },
          {
            "constraint_type": "rate_limiting",
            "effect": "allow",
            "rate_limit": "5/hour"
          }
        ]
      },
      "auth_refs": ["cx:event:01js0rootgrant"]
    },
    {
      "event_id": "cx:event:01js0d1h000000000000000000",
      "kind": "cx.capability.delegate",
      "state_key": "invite-ops",
      "space_id": "cx:space:01js0ms000000000000000000",
      "space_version": "1",
      "actor_id": "did:uuid:ops",
      "content": {
        "source_capability": "space-admin-delegate-a",
        "subject": "did:uuid:intern",
        "scope": "space:01js0ms000000000000000000",
        "actions": ["cx.invite.create"],
        "constraints": [
          {
            "constraint_type": "rate_limiting",
            "effect": "allow",
            "rate_limit": "2/day"
          },
          {
            "constraint_type": "scope_limitation",
            "effect": "allow",
            "allowed_audiences": ["did:web:partner.example", "did:web:vendor.example"]
          }
        ]
      },
      "auth_refs": ["cx:event:01js0d1g000000000000000000"]
    }
  ],
  "action_query": {
    "actor_id": "did:uuid:intern",
    "action": "cx.invite.create",
    "resource": "cx:space:01js0ms000000000000000000",
    "request_time": "2026-04-26T01:00:00Z",
    "request_audience": "did:web:vendor.example"
  }
}
```

期望输出：

```json
{
  "authorized": true,
  "valid_chain": [
    "cx:event:01js0rootgrant",
    "cx:event:01js0d1g000000000000000000",
    "cx:event:01js0d1h000000000000000000"
  ],
  "constraints_checked": {
    "time": true,
    "scope": true,
    "rate_limit": true,
    "audience": true
  }
}
```

失败判定：

- 忽略中间 delegate 层直接用 root 进行授权。
- 忽略 `audiences` 约束。
- 时间边界过期仍返回 true。

## 3. Vector: revoke 回滚

向量名称：

```text
cx.vector.capability.revoke_rollback.v1
```

输入：

```json
{
  "events": [
    {
      "event_id": "cx:event:01js0g2a000000000000000000",
      "kind": "cx.capability.grant",
      "state_key": "cap-post-001",
      "content": { "subject": "did:uuid:alice", "actions": ["cx.message.create"] },
      "created_at": "2026-04-26T00:00:00Z"
    },
    {
      "event_id": "cx:event:01js0r2a000000000000000000",
      "kind": "cx.capability.revoke",
      "state_key": "cap-post-001",
      "content": { "target_capability_id": "cx:capability:01js0g2a000000000000000000" },
      "created_at": "2026-04-26T00:00:01Z"
    },
    {
      "event_id": "cx:event:01js0x2a000000000000000000",
      "kind": "cx.member.*",
      "state_key": "did:uuid:alice",
      "created_at": "2026-04-26T00:00:02Z"
    },
    {
      "event_id": "cx:event:01js0msg2a000000000000000000",
      "kind": "cx.message.create",
      "actor_id": "did:uuid:alice",
      "created_at": "2026-04-26T00:00:03Z",
      "content": { "body": "should_fail_if_revoke_applies" },
      "prev_refs": ["cx:event:01js0x2a000000000000000000"]
    }
  ],
  "rollback": {
    "target_state_key": "cx.event:01js0r2a000000000000000000",
    "reason": "revoke_undo_invalid_signature"
  }
}
```

期望输出：

- 初始解析：`cx:event:01js0msg2a000000000000000000` 因 revoke 生效应拒绝或标记 soft-fail/rejected（取决于实现策略）。
- 回滚 revoke 后重算：同一事件在回滚前瞻分析中应变为 authorized。
- 回滚必须产生独立可审计结果，不可直接修改历史事件链的 event_id。

验证：

- `accepted` 集合必须对应当前 reducer frontier。
- 回滚后状态必须可复现，并有 `rollback_ref` 或等价证据。

## 4. Vector: 审批约束缺失

向量名称：

```text
cx.vector.capability.approval_constraint.v1
```

输入：

```json
{
  "event": {
    "event_id": "cx:event:01js0mha000000000000000000",
    "kind": "cx.policy.action",
    "actor_id": "did:web:contractor.example",
    "space_id": "cx:space:01js0ms000000000000000000",
    "space_version": "1",
    "hlc": "01970e589d26-0001-aaaaaaaa",
    "content": {
      "action": "cx.space.admin",
      "approval_required": true,
      "approval_quorum": 2,
      "scope": "space:01js0ms000000000000000000"
    },
    "auth_refs": ["cx:event:01js0space_admin"]
  },
  "capabilities": [
    {
      "kind": "cx.capability.grant",
      "state_key": "admin-delete",
      "subject": "did:web:contractor.example",
      "actions": ["cx.space.admin"]
    },
    {
      "kind": "cx.capability.grant",
      "state_key": "evidence",
      "subject": "did:uuid:approver_1",
      "actions": ["cx.approval.vote"]
    }
  ]
}
```

期望输出：

```json
{
  "authorized": false,
  "failure_code": "approval_required",
  "next_state": "proposal",
  "visible_to": ["initiator", "approvers"]
}
```

判定要求：

- 即便有高权限 grant，若 approval constraint 未满足，不得直接通过写入执行。
- 必须有可复现的 proposal / review 生命周期。
- 通过审核后应产生可验证的审批完成事件，再以独立 action event 执行。
