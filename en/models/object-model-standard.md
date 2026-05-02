# Standard Object Types

Standard Entity semantic type labels in the first profile:

- `board`
- `collection`
- `task`
- `message`
- `topic`
- `channel`
- `document`
- `file`
- `memory`
- `run`
- `actor_profile`
- `poll`

These are semantic conventions over the core Entity / Relation / Event model. They do not introduce separate protocol roots.

`entity_type` does not implicitly grant behavior. Standard profiles MAY inject default facets for common types, but conformance decisions use the actual `Entity.facets` / Space schema profile. Typical mappings:

- `board`: `container`, `replyable`, `renderable`
- `collection`: `container`, `rankable`, `renderable`
- `task`: `stateful`, `rankable`, `assignable`, `schedulable`, `replyable`, `renderable`
- `message`: `replyable`, `renderable`, `notifiable`
- `topic` / `channel`: `container`, `replyable`, `renderable`
- `document`: `documentable`, `container`, `replyable`, `renderable`
- `memory` / `run`: `reviewable`, `notifiable`, `renderable`
