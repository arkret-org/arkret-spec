# Resource Selector Grammar

## 1. Overview

This specification defines the formal grammar for resource selectors in Contrix v1 capability grants. Resource selectors define which objects a capability applies to.

## 2. Grammar Definition

### 2.1 EBNF Grammar

```ebnf
selector            ::= space_selector
                     | entity_selector
                     | relation_selector
                     | view_selector
                     | wildcard_selector
                     | conjunction_selector
                     | disjunction_selector

space_selector      ::= "space" ":" space_id
                     | "space" ":" "*"

entity_selector     ::= "entity" ":" space_id ":" entity_type
                     | "entity" ":" space_id ":" entity_id
                     | "entity" ":" "*" ":" entity_type
                     | "entity" ":" space_id ":*"

relation_selector   ::= "relation" ":" space_id ":" relation_kind
                     | "relation" ":" "*" ":" relation_kind

view_selector       ::= "view" ":" space_id ":" view_id
                     | "view" ":" space_id ":*"

wildcard_selector   ::= "*"
                     | "space" ":" "*"

conjunction_selector ::= selector "+" selector

disjunction_selector ::= selector "," selector
```

### 2.2 Lexical Rules

- `space_id`: `cx:space:` followed by ULID
- `entity_id`: `cx:entity:` followed by ULID
- `entity_type`: String identifier (e.g., `task`, `message`, `board`)
- `relation_kind`: String identifier (e.g., `contains`, `assigned_to`)
- `view_id`: `cx:view:` followed by ULID
- Whitespace is ignored except within quoted strings

## 3. Selector Evaluation

### 3.1 Space Selector

`space:cx:space:01JS0SP000000000000000000`
- Matches: The specific Space
- Applies to: All entities, relations, events in the Space

`space:*`
- Matches: All Spaces
- Use with: `max_delegation_depth=0` to prevent unintended expansion

### 3.2 Entity Selector

`entity:cx:space:...:task`
- Matches: All entities with `entity_type=task` in the Space
- Does not match: Other entity types

`entity:cx:space:...:cx:entity:01JS0EN000000000000000000`
- Matches: The specific entity
- Highest specificity

`entity:*:task`
- Matches: All `task` entities across all accessible Spaces
- Requires: `space:*` or Space policy delegation

`entity:cx:space:...:*`
- Matches: All entities in the Space
- Equivalent to: `space:cx:space:...` for entity operations

### 3.3 Relation Selector

`relation:cx:space:...:assigned_to`
- Matches: All `assigned_to` relations in the Space
- Applies to: Both reading and creating these relations

`relation:*:assigned_to`
- Matches: All `assigned_to` relations across all accessible Spaces

### 3.4 View Selector

`view:cx:space:...:cx:view:01JS0VW000000000000000000`
- Matches: The specific View
- Permission: `read` allows reading the View definition

`view:cx:space:...:*`
- Matches: All Views in the Space

### 3.5 Wildcard Selector

`*`
- Matches: All resources in all accessible contexts
- Use with: Extreme caution and time limits
- Should: Always include `expires_at`

## 4. Selector Combination

### 4.1 Conjunction (+)

`space:cx:space:...+entity:cx:space:...:task`
- Matches: Task entities in the specific Space
- Redundant: Space is implied by entity selector
- Useful: When combining different resource types

### 4.2 Disjunction (,)

`space:cx:space:A,space:cx:space:B`
- Matches: Either Space A or Space B
- Applied: To all resources in both Spaces

`entity:cx:space:...:task,entity:cx:space:...:message`
- Matches: Tasks OR messages in the Space

## 5. JSON Representation

While the grammar defines string selectors, capability grants use JSON:

```json
{
  "resources": [
    {
      "kind": "space",
      "space_id": "cx:space:01JS0SP000000000000000000"
    },
    {
      "kind": "entity",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "entity_type": "task"
    },
    {
      "kind": "entity",
      "space_id": "cx:space:01JS0SP000000000000000000",
      "entity_id": "cx:entity:01JS0EN000000000000000000"
    }
  ]
}
```

## 6. Matching Algorithm

Given a target resource and a selector:

```
function matches(target, selector):
    if selector.kind == "space":
        return target.space_id == selector.space_id or selector.space_id == "*"

    if selector.kind == "entity":
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if selector.entity_id and target.entity_id != selector.entity_id:
            return false
        if selector.entity_type and target.entity_type != selector.entity_type:
            return false
        return true

    if selector.kind == "relation":
        if target.space_id != selector.space_id and selector.space_id != "*":
            return false
        if selector.relation_kind and target.relation_kind != selector.relation_kind:
            return false
        return true

    # Similar logic for other kinds...
```

## 7. Authorization Scope

Selectors define the **resource scope** of a grant. The complete authorization requires:

1. **Resource Match**: Target resource must match selector
2. **Action Match**: Operation action must be in grant's `actions` array
3. **Constraints**: All constraints in grant must be satisfied

## 8. Security Considerations

### 8.1 Wildcard Expansion

`*` selectors can match unintended resources. Mitigations:
- Always use with `expires_at`
- Combine with `entity_facet_allow` / `entity_type_allow` constraints; new profiles SHOULD prefer facet-scoped capability restrictions
- Require admin approval for wildcard grants
- Audit wildcard grant usage

### 8.2 Selector Injection

Validate selector input to prevent injection attacks:
- Strict parsing with defined grammar
- Reject malformed selectors
- Limit selector complexity depth

### 8.3 Privacy Leaks

Overly broad selectors can expose private information:
- `*` selector may expose unintended Spaces
- Avoid in multi-tenant environments
- Use Space-level isolation

## 9. Performance Considerations

### 9.1 Selector Indexing

For efficient matching:
- Index grants by `space_id` (most common filter)
- Index by `entity_type` (common constraint)
- Cache wildcard grants separately

### 9.2 Evaluation Order

Evaluate selectors in this order for performance:
1. Exact `space_id` matches (fastest)
2. Exact `entity_id` matches
3. Type-based matches
4. Wildcard matches (slowest)

## 10. Examples

### 10.1 Basic Task Grant

```json
{
  "grant_id": "cx:grant:...",
  "subject": "did:web:alice.example.com",
  "actions": ["read", "update"],
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_type": "task"
    }
  ],
  "constraints": {
    "fields_write_allow": ["title", "status"]
  }
}
```

### 10.2 Multi-Space Grant

```json
{
  "resources": [
    {"kind": "space", "space_id": "cx:space:A"},
    {"kind": "space", "space_id": "cx:space:B"}
  ]
}
```

### 10.3 Specific Entity Grant

```json
{
  "resources": [
    {
      "kind": "entity",
      "space_id": "cx:space:...",
      "entity_id": "cx:entity:01JS0EN000000000000000000"
    }
  ]
}
```

## 11. Migration Path

For implementations using simpler string-based selectors:

1. **Phase 1**: Support both string and JSON selectors
2. **Phase 2**: Emit JSON selectors in new grants
3. **Phase 3**: Deprecate string selector format

## 12. Conformance

Implementations MUST:
- Accept JSON resource selectors as defined
- Support exact ID matching
- Support type-based matching
- Support space-level wildcards
- Validate selector structure
- Return clear errors for invalid selectors

Implementations SHOULD:
- Optimize selector evaluation
- Cache selector match results
- Log wildcard selector usage
- Provide selector explain/debug tools
