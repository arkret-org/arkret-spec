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

For collection-backed Kanban views, `kanban.card_relation_kind` is required and must not be inferred from local defaults. It is the relation kind used by relation-backed card positions and by `cx.relation.move` exclusive position keys.

The canonical View kind registry is the enum in `artifacts/schemas/view.schema.json`: `kanban`, `list`, `table`, `calendar`, `gantt`, `chat`, `thread`, `forum`, `tree`, `graph`, `timeline`, `review_queue`, `matrix`, `document`, `dashboard`, `activity`, `inbox`, `notifications`, `memory_review`, `agent_runs`, `context_timeline`, and `moderation_queue`. Non-Kanban views use typed configs (`tabular`, `time_window`, `timeline`, `conversation`, `graph`, `queue`, `matrix`, `document`, `dashboard`) as required by the schema.

