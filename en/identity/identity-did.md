# DID Identity

Contrix uses DIDs as stable principal identifiers. Handles, emails, organization usernames, and third-party accounts are verifiable attributes, not protocol primary keys.

Core decisions:

- Default native method: `did:uuid:<uuid-v8>`.
- `did:uuid` embeds a timestamp, hash algorithm id, and 74-bit inception public-key hash fragment.
- Implementations MAY support `did:keri`.
- Implementations MAY support `did:key` for temporary, test, device, invitation, or bootstrap subjects.
- Ordinary key rotation MUST NOT change the DID.
- Current control keys MUST be traceable from `inception_key` through `key_log`.
- Canonical Contrix fields use snake_case.
- Raw W3C DID/VC documents MAY be preserved as external evidence and mapped into Contrix normalized views.
- Public-persona DIDs MAY publish `also_known_as`; pairwise/private DIDs SHOULD NOT.

## User-Facing Identifiers Are Optional

Implementations MAY let users discover, log in, invite, or recover accounts through `@alice:example.org`, `alice@example.org`, organization usernames, OIDC subjects, invitation links, or other human-readable identifiers.

These identifiers are user-facing identifiers, service-account ids, handles, 3PIDs, or bridge aliases; they are not protocol primary keys. Before accepting any durable Event, repo commit, capability grant, federation transaction, MLS membership, or service delegation, the implementation MUST bind the current session to a principal DID and device, then verify that binding according to local trust policy.

If the user does not yet have an explicit DID, an Auth / Account Server MAY create a supported managed DID before registration completion, invite claiming, or first write, such as `did:uuid`, `did:web`, or an organization-private DID. The managed DID's controller, recovery policy, trust domain, and service-account binding MUST be auditable; subsequent protocol objects still use the DID as the root for `actor_id`, `repo_id`, `author`, grant `subject`, service DID, or `verification_method`.

Raw W3C field mappings:

| Raw field | Contrix canonical field |
| --- | --- |
| `alsoKnownAs` | `also_known_as` |
| `verificationMethod` | `verification_method` |
| `assertionMethod` | `assertion_method` |
| `publicKeyMultibase` | `public_key_multibase` |
| `serviceEndpoint` | `service_endpoint` |

## Identity Resolution Infrastructure

Contrix abstracts identity resolution as `Identity Resolution Infrastructure`; it does not require every DID method to use the same Identity Registry model.

| DID method | Requires public Identity Registry? | Required resolution / verification capability |
| --- | --- | --- |
| `did:key` | No. | Local method resolver expands the DID string into a DID Document. It fits temporary subjects, devices, tests, one-time invitations, or bootstrap keys, but not long-lived recoverable identity. |
| `did:web` | No public registry. | HTTPS / DNS / domain governance, TLS / PKI, and method-specific DID Document retrieval and verification. |
| `did:uuid` | Depends on trust policy. | Public or private registry / witness / resolver, key log, receipts, and service delegation. |
| `did:keri` | No traditional centralized registry. | KERI event log, key state resolution, witness receipts, watchers, and OOBI discovery. |
| `did:plc` or external methods | Depends on the method. | Preserve raw DID Documents and method-specific proofs, then map into the Contrix normalized principal view. |

Using `did:key` or `did:keri` therefore does not mean identity resolution disappears. It means a public writable registry is usually unnecessary. Clients, Auth Servers, Principal Servers, and Policy / Authz still need the corresponding DID method resolver / verifier to confirm DID control state, service delegation, and key rotation history.

## Resolver, Auth Server, And Organization Authorization

DID resolution, login authentication, and organization data authorization are separate responsibilities:

| Layer | Responsible for | Not responsible for |
| --- | --- | --- |
| Identity Resolution Infrastructure | Resolving a DID to a DID Document, key state, key log / KERI log, service delegation, witness evidence, or method-specific proof. | Deciding whether the user may log in to an organization or access Space / repo data. |
| Auth / Account Server | Passkeys, OIDC, SSO, device pairing, account recovery, session grants, and binding a service-account login to a DID / device. | Changing DID control, replacing DID key proof, or deciding every organization authorization rule. |
| Organization / Policy / Authz | Deciding whether a DID, device, credential, or capability may access organization data, Spaces, repos, Applets, or admin actions. | Maintaining public DID control history. |

An organization MAY run its own Auth / Account Server while continuing to use the public `did:uuid` resolver network. A typical flow is:

1. The user submits `did:uuid:...`, a handle, an invitation link, or an organization account.
2. The organization Auth Server selects a resolver according to local trust policy. Standard deployments may default to the public `did:uuid` resolver; high-security deployments may use an organization-private resolver; `did:web` resolves according to its DID method and domain.
3. The Auth Server or client resolves the DID Document and verifies the key log, witness evidence, service delegation, and acceptable trust domain.
4. The user proves login binding through a DID control key, device key, passkey / OIDC binding proof, or required VC presentation.
5. The Auth Server issues only a session grant / device binding. Organization Policy / Authz then decides data access from the DID, credentials, membership, invites, capabilities, and Space policy.

### DID Proof For Organization Account Binding

When a user registers, claims, or binds an organization service account with an existing DID, the Auth / Account Server MUST verify that the caller currently controls that DID. Submitting only a DID string, handle, email code, OIDC subject, or organization username is not sufficient to establish the binding.

The recommended DID proof is challenge-response:

1. The user submits the DID to bind.
2. The Auth Server resolves the DID Document and verifies the method, key log, witness evidence, deactivation state, and accepted trust domain according to local policy.
3. The Auth Server creates a one-time challenge bound to purpose, target service, origin / audience, expiry, and a random nonce.
4. The client signs the challenge with a currently valid DID `authentication` verification method, authorized device key, or temporary key covered by a valid session / device grant.
5. The Auth Server verifies the signature, the current validity of the verification method, and that the challenge is unexpired and unused.
6. After verification, the Auth Server MAY create or update the `service_account -> principal_id` binding and issue a short-lived `cx.session.grant` or record a device binding.

The service-account binding is local organization state. It does not transfer DID ownership to the organization and does not allow the organization to rotate, recover, or deactivate the user's DID unless the DID's own control state or recovery policy authorizes that action.

Therefore, a public `did:uuid` resolver is one form of public identity-control and service-discovery infrastructure; `did:key` may resolve locally, and `did:keri` may be verified through KERI witnesses, watchers, and resolvers. An enterprise Auth Server is that enterprise's login and session boundary. Using a public resolver does not let the resolver log in to the enterprise or access enterprise data. Allowing a DID to log in means the organization's policy accepts that DID, its control proof, and any required credential or invite.

For `did:web` and other method-specific DID methods, resolver selection is determined by the method rules plus local trust policy. An organization may require employees or service principals to use `did:web`, organization-private `did:uuid`, or public `did:uuid`; this is an admission policy, not a natural coupling between the Auth Server and Resolver.

The detailed Chinese draft is currently normative for bit layout and registry semantics.

