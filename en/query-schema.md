# Query JSON Schema

Standard query shape:

```json
{
  "space_ids": [],
  "entity_types": [],
  "filters": [],
  "relation": null,
  "order_by": [],
  "projection": [],
  "cursor": null,
  "limit": 50,
  "consistency": null
}
```

Filters support `eq`, `neq`, `in`, `not_in`, `lt`, `lte`, `gt`, `gte`, `contains`, `exists`, `prefix`, and `full_text`.

Index nodes MUST apply authorization filtering and must not leak invisible resource existence.
