# Grant Constraint Schema

Capability grants use explicit scope and constraints.

Scope:

```json
{
  "space_ids": [],
  "entity_types": [],
  "actions": []
}
```

Constraints may include time windows, writable field allow/deny lists, required claims, approval requirements, audience binding, device binding, max blob bytes, and delegation depth.

Evaluation requires signature, issuer authority, subject match, action/resource scope, time validity, revocation, field constraints, claim constraints, approval constraints, and delegation chain validation.

