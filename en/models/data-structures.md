# Data Structures

This file is the English companion for the detailed Chinese draft in `../../zh/models/data-structures.md`.

It defines field-level structures for core Contrix objects, including Space, Actor Profile, Entity, Relation, Event, View, Policy, Capability, Invite, Read Marker, Notification, Repo Commit, Operation, Blob metadata, encrypted payload envelopes, and Client Sync responses.

The Chinese draft is currently normative for field names, requiredness, types, constraints, and descriptions.

The current policy type registry includes `plaintext_visibility` for `cx.space.plaintext_visible_services`.

Canonical Operation objects use `operation_type` plus optional `semantic_kind`. For ordered Kanban operations, `move`, `reorder`, and `rebalance` MUST declare a known `semantic_kind` and validate the corresponding payload schema:

- `cx.task.move` maps to `operation_type="move"` and `object_type="entity"`.
- `cx.relation.move` maps to `operation_type="move"` and `object_type="relation"`.
- `cx.task.reorder` maps to `operation_type="reorder"` and `object_type="entity"`.
- `cx.relation.rebalance` maps to `operation_type="rebalance"` and `object_type="relation"`.

For collection-backed Kanban preset views, `collection.grouping.item_relation_kind` is required and must not be inferred from local defaults. It is the relation kind used by relation-backed item positions and by `cx.relation.move` exclusive position keys.

The canonical View kind registry is the enum in `artifacts/schemas/view.schema.json`: `collection`, `timeline`, `graph`, `document`, and `composite`. Product shapes such as `kanban`, `list`, `table`, `calendar`, `gantt`, `chat`, `thread`, `forum`, `tree`, `review_queue`, `matrix`, `dashboard`, `activity`, `inbox`, `notifications`, `memory_review`, `agent_runs`, `context_timeline`, and `moderation_queue` are `preset` values mapped to those five primitives. `collection` views use `CollectionConfig`; `timeline`, `graph`, `document`, and `composite` use their matching typed configs. Legacy `kanban`, `tabular`, `time_window`, `queue`, and `matrix` configs are compatibility fields and are not new top-level View kinds.

