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

