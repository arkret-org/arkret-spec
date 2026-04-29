# Grant Constraint Schema

## 1. Overview

This specification defines the formal schema for constraints in Contrix v1 capability grants. Constraints refine when and how a capability can be exercised.

## 2. Constraint Structure

### 2.1 Base Schema

All constraints follow this structure:

```json
{
  "constraint_id": "string",
  "constraint_type": "enum",
  "effect": "allow|deny|quarantine|require_review",
  "parameters": {},
  "priority": "integer"
}
```

### 2.2 Constraint Types

| Constraint Type | Description | Version |
|-----------------|-------------|---------|
| `temporal` | Time-based constraints | v1 |
| `field_access` | Field-level read/write control | v1 |
| `type_restriction` | Entity type restrictions | v1 |
| `scope_limitation` | Space/channel/view scope | v1 |
| `delegation_control` | Delegation depth and path | v1 |
| `rate_limiting` | Operation frequency limits | v1 |
| `approval_workflow` | Approval requirements | v1 |
| `claim_based` | Claim/attestation requirements | v1 |
| `accountability` | Responsible party tracking | v1 |
| `encryption_requirement` | Mandatory encryption | v1 |

## 3. Temporal Constraints

### 3.1 Time Window

```json
{
  "constraint_type": "temporal",
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-05-26T00:00:00Z",
  "recurrence": {
    "frequency": "daily|weekly|monthly",
    "days": ["monday", "tuesday", "wednesday"],
    "window_start": "09:00:00",
    "window_end": "17:00:00",
    "timezone": "UTC"
  }
}
```

### 3.2 Duration Limits

```json
{
  "constraint_type": "temporal",
  "max_duration": "8h",
  "max_session_duration": "1h",
  "inactivity_timeout": "30m"
}
```

## 4. Field Access Constraints

### 4.1 Field Write Allow

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "scope": "write",
  "fields": ["title", "body", "fields.status"],
  "condition": {
    "when": "entity_is_owned_by_actor"
  }
}
```

### 4.2 Field Write Deny

```json
{
  "constraint_type": "field_access",
  "effect": "deny",
  "scope": "write",
  "fields": ["id", "created_by", "created_at"]
}
```

### 4.3 Field Read Visibility

```json
{
  "constraint_type": "field_access",
  "effect": "allow",
  "scope": "read",
  "fields": ["title", "fields.status"],
  "sensitive_fields": ["fields.ssn", "fields.salary"],
  "sensitive_handling": "redact|hash|omit"
}
```

## 5. Type Restrictions

### 5.1 Entity Type Allow List

```json
{
  "constraint_type": "type_restriction",
  "effect": "allow",
  "entity_type_allow": ["task", "message", "document"],
  "entity_type_deny": ["run", "memory"]
}
```

### 5.2 Memory Kind Restrictions

```json
{
  "constraint_type": "type_restriction",
  "memory_kind_allow": ["episodic", "semantic"],
  "memory_kind_deny": ["sensitive", "credentials"]
}
```

## 6. Scope Limitations

### 6.1 Channel Restrictions

```json
{
  "constraint_type": "scope_limitation",
  "allowed_channel_refs": [
    "cx:channel:01JS0CH000000000000000000"
  ],
  "denied_channel_refs": [
    "cx:channel:01JS0CH999999999999999999"
  ]
}
```

### 6.2 View Restrictions

```json
{
  "constraint_type": "scope_limitation",
  "allowed_view_kinds": ["collection"],
  "allowed_view_presets": ["kanban", "list"],
  "denied_view_kinds": ["graph"],
  "denied_view_presets": ["admin"]
}
```

## 7. Delegation Control

### 7.1 Delegation Depth

```json
{
  "constraint_type": "delegation_control",
  "max_delegation_depth": 2,
  "delegation_path": ["did:web:org.example.com"],
  "prohibit_subdelegation": false
}
```

### 7.2 Delegation Scope

```json
{
  "constraint_type": "delegation_control",
  "delegation_scope": "narrowing_only",
  "allow_scope_expansion": false,
  "require_parent_reference": true
}
```

## 8. Rate Limiting

### 8.1 Operation Rate

```json
{
  "constraint_type": "rate_limiting",
  "max_operations": 100,
  "period": "1h",
  "burst": 10,
  "scope": "per_space|global"
}
```

### 8.2 Resource Rate

```json
{
  "constraint_type": "rate_limiting",
  "max_resources": 1000,
  "resource_type": "entity",
  "period": "24h",
  "scope": "per_space"
}
```

## 9. Approval Workflow

### 9.1 Pre-Approval

```json
{
  "constraint_type": "approval_workflow",
  "approval_required": true,
  "approval_mode": "before_commit",
  "approval_actor_refs": [
    "did:web:manager.example.com"
  ],
  "approval_relation": "controller",
  "timeout": "72h",
  "auto_reject_on_timeout": true
}
```

### 9.2 Proposal Mode

```json
{
  "constraint_type": "approval_workflow",
  "approval_mode": "proposal_then_approve",
  "proposal_entity_type": "proposal",
  "approval_threshold": "majority|unanimous|quorum",
  "approvers": [
    "did:web:approver1.example.com",
    "did:web:approver2.example.com"
  ]
}
```

## 10. Claim-Based Constraints

### 10.1 Claim Requirements

```json
{
  "constraint_type": "claim_based",
  "requires_claims": [
    {
      "claim_type": "org_membership",
      "issuer": "did:web:acme.com",
      "organization": "did:web:acme.com",
      "status": "active",
      "roles": ["employee", "contractor"]
    }
  ],
  "trusted_claim_issuers": [
    "did:web:acme.com"
  ],
  "claim_refresh_required": true,
  "claim_max_age": "24h"
}
```

### 10.2 Claim Validation

```json
{
  "constraint_type": "claim_based",
  "validation_mode": "strict|lenient",
  "allow_expired_claims": false,
  "allow_revoked_claims": false,
  "minimum_trust_level": "high"
}
```

## 11. Accountability Constraints

### 11.1 Responsible Party

```json
{
  "constraint_type": "accountability",
  "accountability_required": true,
  "responsible_actor": "did:web:guardian.example.com",
  "accountability_relation": "guardian",
  "log_all_operations": true,
  "require_signature": true
}
```

### 11.2 Guardian Approval

```json
{
  "constraint_type": "accountability",
  "guardian_approval_required": true,
  "guardian_actor_refs": [
    "did:web:parent1.example.com",
    "did:web:parent2.example.com"
  ],
  "approval_threshold": "any|all"
}
```

## 12. Encryption Requirements

### 12.1 Mandatory Encryption

```json
{
  "constraint_type": "encryption_requirement",
  "encryption_required": true,
  "min_encryption_level": "mls_rfc9420",
  "allow_plaintext_fallback": false,
  "require_audit_trail": true
}
```

### 12.2 Key Management

```json
{
  "constraint_type": "encryption_requirement",
  "key_rotation_period": "7d",
  "max_key_age": "30d",
  "require_key_backup": true,
  "approved_key_issuers": [
    "did:web:keys.example.com"
  ]
}
```

## 13. Constraint Evaluation

### 13.1 Evaluation Order

Constraints are evaluated in priority order:

```
1. All deny constraints (highest priority first)
2. All quarantine constraints
3. All allow constraints (lowest priority first)
4. All require_review constraints
```

Within each category, higher `priority` value wins.

### 13.2 Constraint Combination

When multiple constraints apply:
- All must be satisfied (AND logic)
- Conflict resolution: deny > quarantine > require_review > allow
- Exceptions defined per constraint type

### 13.3 Evaluation Algorithm

```
function evaluate_constraints(operation, grant_constraints):
    # Check deny constraints first
    for constraint in grant_constraints:
        if constraint.effect == "deny":
            if matches(operation, constraint):
                return DENIED

    # Check quarantine constraints
    for constraint in grant_constraints:
        if constraint.effect == "quarantine":
            if matches(operation, constraint):
                return QUARANTINED

    # Check require_review constraints
    for constraint in grant_constraints:
        if constraint.effect == "require_review":
            if matches(operation, constraint):
                return REQUIRES_REVIEW

    # All allow constraints must pass
    for constraint in grant_constraints:
        if constraint.effect == "allow":
            if not matches(operation, constraint):
                return DENIED

    return ALLOWED
```

## 14. Constraint Matching

### 14.1 Temporal Matching

```javascript
function matches_temporal(operation, constraint):
    now = current_timestamp()

    if constraint.not_before and now < constraint.not_before:
        return false
    if constraint.expires_at and now > constraint.expires_at:
        return false
    if constraint.recurrence:
        return matches_recurrence(now, constraint.recurrence)

    return true
```

### 14.2 Field Access Matching

```javascript
function matches_field_access(operation, constraint):
    if constraint.scope == "read":
        fields = operation.read_fields
    else:
        fields = operation.write_fields

    for field in fields:
        if field in constraint.fields:
            if constraint.effect == "deny":
                return false
            if constraint.condition:
                if not meets_condition(operation, constraint.condition):
                    return false

    return true
```

## 15. Security Considerations

### 15.1 Constraint Evasion

Prevent evasion through:
- Strict constraint validation
- No implicit constraint relaxation
- Audit logging of constraint violations
- Rate limiting constraint evaluation

### 15.2 Time-Based Attacks

Mitigations:
- Use server time for validation
- Allow reasonable clock skew (±5 minutes)
- Log time validation failures
- Monitor for time manipulation attempts

### 15.3 Claim Spoofing

Prevent spoofing by:
- Validating claim issuer signatures
- Checking claim revocation status
- Verifying claim freshness
- Using trusted claim issuers only

## 16. Performance Considerations

### 16.1 Constraint Caching

Cache constraint evaluation results:
- Key: (grant_id, operation_type, resource_type)
- TTL: Based on constraint temporal bounds
- Invalidation: On constraint change

### 16.2 Optimization Strategies

- Index constraints by type
- Pre-compute constraint combinations
- Use fast path for simple constraints
- Batch constraint evaluation

## 17. Conformance

Implementations MUST:
- Support all v1 constraint types
- Evaluate constraints in correct order
- Return correct denial reasons
- Log constraint violations
- Validate constraint parameters

Implementations SHOULD:
- Cache constraint evaluations
- Optimize common constraint patterns
- Provide constraint debugging tools
- Support constraint templates
- Monitor constraint performance

## 18. Examples

### 18.1 Agent Grant with Constraints

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:agent.example.com",
  "actions": ["read", "create_entity", "write_memory"],
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_type": "task"
    }
  ],
  "constraints": [
    {
      "constraint_type": "temporal",
      "expires_at": "2026-05-01T00:00:00Z"
    },
    {
      "constraint_type": "field_access",
      "effect": "allow",
      "scope": "write",
      "fields": ["title", "fields.status", "fields.priority"]
    },
    {
      "constraint_type": "accountability",
      "accountability_required": true,
      "responsible_actor": "did:web:owner.example.com"
    },
    {
      "constraint_type": "approval_workflow",
      "approval_required": true,
      "approval_mode": "after_commit_review"
    }
  ]
}
```

### 18.2 Temporary Elevated Access

```json
{
  "constraints": [
    {
      "constraint_type": "temporal",
      "not_before": "2026-04-26T09:00:00Z",
      "expires_at": "2026-04-26T17:00:00Z",
      "recurrence": {
        "frequency": "weekly",
        "days": ["saturday", "sunday"],
        "timezone": "America/New_York"
      }
    },
    {
      "constraint_type": "claim_based",
      "requires_claims": [{
        "claim_type": "org_role",
        "roles": ["on_call"]
      }]
    }
  ]
}
```
