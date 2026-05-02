# Matrix And Contrix Core Differences

## 1. Goal

This document aims to explain the core design differences between Contrix and Matrix, clarifying why Contrix is not a direct Matrix variant, nor a simple rename or rewrite of its room / homeserver / appservice concepts.

## 2. Summary

Matrix is rooted in **rooms, event graphs, and homeserver federation**, primarily serving real-time communication, group chat, VoIP signaling, and bridges.

Contrix is rooted in **principal repos, Spaces, Entity / Relation / Event / View, and capabilities**, serving auditable collaboration objects, tasks, boards, knowledge, agent runs, and multi-view projections.

The protocols can interoperate through bridges, but their roots are different.

## 3. Core Differences

| Area | Matrix | Contrix |
| --- | --- | --- |
| Data root | Room event streams and room state. | Authorized Event / operation sets in a Space, reduced into Entities, Relations, and Views. |
| Main use | Instant messaging, group chat, VoIP signaling, bridges. | Collaboration objects, tasks/boards, chat/topics, knowledge memory, agent runs, audit workflows. |
| Server model | Homeservers are central to accounts, room participation, and federation. | Principal Servers are controlled or explicitly delegated service boundaries; Repo, Sync, Blob, and Policy remain layered. |
| Truth source | Room event graph and state resolution. | Principal-signed repo commits / operations plus Space reducers; search and View projection are derived layers. |
| Identity | Matrix user IDs are tied to homeserver domains, e.g. `@alice:example.org`. | Principals use DIDs as protocol primary keys; identifiers like `@alice:example.org` can be handles, login entry points, or bridge aliases, but not authorization subjects. |
| Authorization | Room auth rules, membership, and power levels. | Capability grants, constraints, claims, policy, and deterministic authorization. |
| Integrations | Application Services are mostly homeserver-registered namespace integrations. | Applets are signed, authorized, auditable service DIDs scoped by Space, Actor, object range, user grant, and capability. |
| AI agents | Bots can join through users or appservices, but agents are not protocol-root objects. | Agents are first-class principals / Actors with repos, capabilities, runs, memories, and protocol sessions. |
| Agent protocols | No native A2A / ACP handoff semantics. | A2A / ACP / MCP bridge / custom agent APIs can be controlled protocol sessions. |
| E2EE | Matrix E2EE is based on Olm / Megolm. | Contrix recommends MLS RFC 9420 for group E2EE. |
| Views and query | Client experience is reconstructed from sync, state, relations, and aggregation APIs. | View is first-class; search and projection are client-local by default and cannot be truth sources. |
| Plaintext boundary | Depends on deployment, encryption, appservice, and bridge configuration. | Private plaintext may only enter principal- or Space-policy-delegated services; `plaintext_visible_services` declares visibility. |

## 4. Deep Dive on Core Concepts

### 4.1 Applets vs Application Services

Matrix Application Services are mature bridge mechanisms built around homeserver registration, namespaces, transactions, queries, and ping.

Contrix Applets differ in their granularity and authorization model:

- Applet registration is signed and can be accepted by a Space owner, Organization, registry, or authz service.
- Namespace does not grant permission; each write still requires capability authorization.
- The same Applet can be enabled in different Spaces with different capabilities, visibility, and object scopes.
- Different users or organizations can enable different Applets in Spaces they control, subject to Space policy.
- Applets can act as bots, bridges, ghost actor controllers, portal Space managers, delegated agents, or delegated devices while remaining auditable.

### 4.2 AI and Agent Support

In Matrix, AI can be integrated via bots, appservices, or bridges, but it is not a protocol-native entity.

Contrix incorporates agents deeply into its object model: it treats agents as principals, Actors, and capability subjects; agent outputs can become `run`, `memory`, `message`, or `task` Entities; and agent-to-agent work can explicitly upgrade to A2A / ACP / MCP bridge / private agent APIs while writing session state, status, artifacts, and results back to Contrix.

### 4.3 Evolution of the Identity System

Contrix adopts a DID-rooted approach to identity and verifiable repositories, similar to certain principles in atprotocol, but with fundamental differences.

This does not require ordinary users to see or manage DIDs directly. Clients and services MAY offer a Matrix-like `@user:domain` experience for contact search, login, organization handles, or bridge aliases; before submitting durable operations, grants, repo commits, or MLS membership, that identifier must resolve or bind to a principal DID.

While Contrix leverages DID-rooted identity, bidirectional handle validation, service discovery through DID Documents, and per-principal verifiable repos, it focuses on enterprise environments and secure collaboration. atprotocol is primarily a public-record and PDS architecture, whereas Contrix targets multi-party collaboration, private Spaces, deterministic authorization state, integrated E2EE, and complex enterprise governance.

### 4.4 E2EE Architecture Choice

While Matrix's Olm / Megolm ecosystem is mature, widely deployed, and highly capable, Contrix integrates the modern, IETF standard MLS (RFC 9420) as its foundation for group E2EE. 

MLS maps naturally to group state, epochs, commits, proposals, member add/remove, history visibility, device authorization, and auditable E2EE. This better suits dynamic governance of collaborative Spaces and enterprise objects over channel-first structures.

## 5. Other Important Differences

Matrix is room-first; Contrix is object-first.

Matrix power levels are useful for room governance; Contrix capabilities are designed for fine-grained actions over Spaces, Entities, Relations, fields, time, devices, approval constraints, agents, and Applets.

Matrix homeservers are core federation participants. Contrix Principal Servers are controlled service boundaries and are not identities or truth sources.

Matrix is strongest as a real-time communication network. Contrix aims to model a larger collaboration graph: tasks, dependencies, references, mentions, runs, memories, agent actions, approvals, audits, and views.

## 6. Where Matrix Remains Stronger

Contrix should continue learning from Matrix:

- Matrix has a mature real-time communication ecosystem.
- Matrix room federation, state resolution, E2EE clients, and bridges have years of production experience.
- Matrix remains a strong reference for chat, public rooms, and bridges to existing IM networks.

Contrix should adopt stable lessons from Matrix without inheriting Matrix's room-first abstraction root.

## 7. Related Documents

- `extensions/applet-integration.md`
- `extensions/agent-protocol-interop.md`
- `extensions/agent-memory.md`
- `identity/identity-did.md`
- `crypto-media/encryption-and-audit.md`
- `authz/capabilities.md`
- `sync/service-surface.md`

## 8. External References

- Matrix Specification: https://spec.matrix.org/latest/
- Matrix Application Service API: https://spec.matrix.org/unstable/application-service-api/
- Matrix E2EE guide: https://matrix.org/docs/matrix-concepts/end-to-end-encryption/
- Matrix Megolm specification: https://spec.matrix.org/unstable/olm-megolm/megolm/
- AT Protocol DID specification: https://atproto.com/specs/did
- AT Protocol repository specification: https://atproto.com/specs/repository
- MLS RFC 9420: https://www.ietf.org/rfc/rfc9420
