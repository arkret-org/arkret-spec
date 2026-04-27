# Grant Constraint Schema Draft

## 1. 目标

Capability grant 通过 constraint 限定 subject 能做什么、在哪里做、何时做、以什么身份或设备做。本文定义标准 constraint 语法。

## 2. Grant Envelope

```json
{
  "type": "capability_grant",
  "grant_id": "cx:grant:01JS0GR000000000000000000",
  "issuer": "did:web:acme.example",
  "subject": "did:web:alice.example",
  "scope": {},
  "constraints": {},
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-07-26T00:00:00Z",
  "revocation_ref": "cx:revocation-list:default",
  "proof": {}
}
```

## 3. Scope

```json
{
  "space_ids": ["cx:space:01JS0SP000000000000000000"],
  "entity_types": ["task", "message"],
  "actions": ["cx.entity.create", "cx.entity.update", "cx.message.create"]
}
```

Scope MUST be allow-list based。未列出的动作默认拒绝。

## 4. Constraint

```json
{
  "time": {
    "not_before": "2026-04-26T00:00:00Z",
    "expires_at": "2026-07-26T00:00:00Z"
  },
  "fields_write_allow": ["title", "fields.status"],
  "fields_write_deny": ["policy", "encryption_profile"],
  "max_blob_bytes": 10485760,
  "requires_claims": [],
  "requires_approval": null,
  "device_bound": true,
  "audience": ["did:web:repo.example"]
}
```

## 5. Claim Constraint

```json
{
  "type": "contrix_org_membership_credential",
  "issuer": ["did:web:google.example"],
  "subject_matches_actor": true,
  "claims": {
    "org": "did:web:google.example",
    "member": true
  }
}
```

## 6. Approval Constraint

```json
{
  "mode": "required",
  "approvers": ["did:web:manager.example"],
  "threshold": 1,
  "expires_after_ms": 86400000,
  "reason_required": true
}
```

## 7. Delegation

Grant MAY allow delegation:

```json
{
  "delegation": {
    "allowed": true,
    "max_depth": 1,
    "subset_only": true
  }
}
```

Delegated grant MUST be equal or narrower than parent grant.

## 8. Evaluation

节点判断动作是否允许时 MUST 检查：

1. grant signature
2. issuer authority
3. subject match
4. action in scope
5. resource in scope
6. time validity
7. revocation status
8. field constraints
9. claim constraints
10. approval constraints
11. delegation chain

任何一步失败 MUST 拒绝。
