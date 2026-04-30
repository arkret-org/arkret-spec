# Query JSON Schema

Standard query shape:

```json
{
  "space_ids": [],
  "entity_types": [],
  "anchor_entity_id": null,
  "filters": [],
  "relation": null,
  "context": {
    "event_kinds": ["cx.entity.update", "cx.message.create", "cx.relation.create"],
    "relation_kinds": ["contains", "assigned_to", "depends_on", "replies_to"],
    "event_tiebreak": "event_id"
  },
  "order_by": [],
  "projection": [],
  "cursor": null,
  "limit": 50,
  "consistency": null
}
```

Filters support `eq`, `neq`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `contains`, `exists`, `prefix`, and `full_text`.

Index nodes MUST apply authorization filtering and must not leak invisible resource existence.

Optional `context` is used by `timeline` / `renderer="timeline"` views to request stable event ordering and relation-aware expansion across multiple object kinds around one anchor object.

