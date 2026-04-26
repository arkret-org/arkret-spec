# Object Model Core

Contrix is based on an auditable collaboration graph, not rooms or messages as root abstractions.

Core objects:

- `space`
- `actor`
- `entity`
- `relation`
- `event`
- `view`
- `schema`
- `policy`
- `invite`
- `read_marker`
- `notification`

Core rules:

- Space is the replication, policy, schema, indexing, and encryption boundary.
- Entity is the common container for collaborative objects.
- Relation is a first-class object for cross-object semantics.
- Event is the signed fact and reducer input.
- View is a projection, not a truth source.
- Canonical fields use snake_case.

The Chinese draft contains the current schema examples and reducer rules.
