---
title: Arkret Protocol (English entry)
status: candidate
stability: v1
updated: 2026-10-02
normative: false
---

> Informative entry page. This is **not** a normative English translation.

Arkret is a self-hostable, federated collaboration protocol for people,
organizations, and AI agents. Participants connect independently operated
Stations and use an open object model for conversations, tasks, documents,
calendars, and calls. Each Realm has one governance Station at a time: it
admits shared writes, assigns order within each visibility stream, and signs
RealmCommits. Other Stations forward submissions and replicate authorized
records; federation does not imply multi-writer consensus.

MLS end-to-end encryption protects content in enabled Realm, Circle, and
Agent Sidecar scopes. Routing and activity metadata remain visible to
carrying services. Clients check producer proofs, user intent, and content
cryptography while relying on their Account Station and the Realm's current
governance authority for the corresponding server results. Signatures do not
guarantee censorship resistance, correct admission by a compromised authority,
or service availability.

Personal conversations with an owned Agent use a separate Direct Conversation
Realm. Sidecars provide private Agent context within an existing project Realm;
publishing a result into shared collaboration requires an explicit new Event.

“Decentralized” can describe independent deployment and service choice only
with those qualifications. The current v1 model has an explicit authority per
Realm. Planned governance handoff requires the old authority to be online;
permanent loss without handoff leaves verifiable caches read-only and requires
an explicit successor Realm for continued collaboration. Accounts remain bound
to their Station and do not automatically carry over to another Station.
See [authority and handoff](../zh/sync/authority-commit-log.md) and
[server trust boundaries](../zh/sync/server-trusted-results.md).

## Language policy

The authoritative Arkret v1 specification is maintained **in Chinese**, under
[`spec/v1/zh/`](../zh/). Arkret v1 follows a **single authoritative language**
policy: the Chinese text under `zh/` is the only normative, human-readable
source of protocol truth. There is **no complete English specification**, and
none is promised.

English readers should refer directly to the Chinese sources:

- Specification map and reading order: [`spec/v1/zh/spec-map.md`](../zh/spec-map.md)
- Top-level index and scope: [`spec/v1/zh/index.md`](../zh/index.md)
- Glossary (canonical term names): [`spec/v1/zh/overview/glossary.md`](../zh/overview/glossary.md)

Machine-readable contracts under [`spec/v1/artifacts/`](../artifacts/)
(registries, schemas, conformance vectors) are language-neutral and are shared
across locales; they may be consumed directly regardless of reading language.

This page exists only to orient English readers. Do not cite it, or any
`/en/...` route, as an English normative contract — the normative text lives in
`zh/` and `artifacts/`.
