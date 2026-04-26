# Agent Memory Draft

## 1. Goal

Contrix New is not only a collaboration protocol. It is also intended to become a long-term memory substrate for AI agents.

But "memory" here does not mean:

- the current LLM context window
- model parameters
- one vendor's private vector database

In Contrix, memory means knowledge objects that are:

- signable
- authorized
- auditable
- retrievable
- inspectable and editable by humans

## 2. Design Principles

### 2.1 Protocol Truth Must Be Structured Objects and Operations

The canonical source of memory SHOULD be:

- items
- comments
- relations
- runs
- memories
- attachments

not embeddings or cached summaries.

### 2.2 Memory Must Carry Provenance

Any high-value memory SHOULD record:

- source objects
- source runs
- the author or extractor
- confidence
- status

### 2.3 Memory Must Be Reviewable

If an agent can write memory, humans MUST be able to:

- inspect it
- review it
- reject it
- mark it expired
- supersede it with a newer memory

## 3. Memory Layers

Contrix recommends splitting agent memory into four layers.

### 3.1 Working Memory

Working memory is temporary in-run context.

It is usually:

- local
- short-lived
- unstable
- not required to enter the protocol

Examples:

- prompt assembly outputs
- transient tool-call caches
- temporary plan drafts

### 3.2 Episodic Memory

Episodic memory records "what happened."

In Contrix this is usually carried by:

- `run`
- `comment`
- activity projections

### 3.3 Semantic Memory

Semantic memory records "what is known."

In Contrix this is carried by `memory` objects, especially for:

- facts
- decisions
- summaries
- procedures
- preferences

### 3.4 Task Memory

Task memory records "what still needs to happen."

In Contrix this is usually carried by:

- `item`
- checklist entries
- relations
- due dates and assignees

## 4. Why Memory Must Not Collapse into a Vector Store

Using only a vector store creates four problems:

1. provenance and authorization become weak
2. auditability is poor
3. humans cannot easily inspect and edit the knowledge
4. portability across implementations is poor

Therefore the Contrix rule is:

- vector indexes may exist
- but they may only be derived retrieval layers for `memory`

## 5. Memory Lifecycle

A suggested lifecycle is:

1. an agent or human produces runs, comments, or item updates
2. an agent or rule engine extracts candidate knowledge
3. `memory(status=candidate)` is created
4. a human or high-authority agent reviews it
5. it becomes `memory(status=confirmed)`
6. if reality changes, it is invalidated or superseded

## 6. Memory Status

The initial `memory.status` set should include:

- `candidate`
- `confirmed`
- `rejected`
- `invalidated`
- `superseded`

### 6.1 `candidate`

Candidate memory that has not yet been formally accepted.

### 6.2 `confirmed`

Valid knowledge that may be retrieved and referenced.

### 6.3 `rejected`

Candidate memory that should not become long-term knowledge.

### 6.4 `invalidated`

Memory that used to be valid but is no longer true.

### 6.5 `superseded`

Memory replaced by a newer version.

## 7. Suggested Memory Fields

See the concrete example in [object-model.md](./object-model.md).

Important fields include:

- `memory_kind`
- `subject_ref`
- `source_refs`
- `confidence`
- `status`
- `valid_from`
- `valid_until`
- `supersedes`

## 8. Relationship Between Memory and Run

`run` expresses:

- who executed what
- how the process unfolded
- which objects were produced

`memory` expresses:

- what knowledge was distilled from those processes

A reasonable structure is:

- `run` points to `output_refs`
- `memory.source_refs` points back to the `run`

That lets humans trace knowledge back to its source.

## 9. Memory and Human Interfaces

Contrix treats memory as a human-reviewable object. Implementations SHOULD therefore support at least:

- a memory review table
- a subject timeline
- a knowledge graph
- an item-side memory list

This lets humans manage knowledge the same way they manage work.

## 10. Memory Query Patterns

The first version should support at least:

- by `subject_ref`
- by `memory_kind`
- by `status`
- by `source_refs`
- by `created_by`
- by `valid_from / valid_until`
- relation-graph expansion

## 11. Retrieval Enhancements

Embeddings, rerankers, and full-text indexes may all exist as enhancements.

Implementations should still follow:

- derived indexes must be rebuildable
- derived indexes are not the sole truth
- derived indexes must obey the same ACL rules

## 12. Forgetting and Retention

Contrix does not require remembering everything forever.

Memory should support:

- archiving
- invalidation
- supersession
- retention policy

But knowledge objects already in the audit chain should not silently disappear.

## 13. Privacy and Minimum Exposure

Agent memory is often more sensitive than ordinary tasks. Implementations SHOULD support:

- space-scoped isolation
- object-scoped isolation
- memory-kind restrictions
- stricter read rules for candidate memories

## 14. Initial Design Decisions

The current draft recommends fixing:

- runs and memories as first-class objects
- coexistence of episodic, semantic, and task memory
- embeddings as derived layers only
- provenance as mandatory for meaningful memory
- memories as reviewable, invalidatable, and supersedable

## 15. Further Work

The next round still needs:

- a standard memory-extraction flow
- a concrete candidate-to-confirmed approval state machine
- a vector-retrieval compatibility surface
- retention / legal-hold / export semantics
