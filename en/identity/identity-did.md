# DID Identity

Contrix uses DIDs as stable principal identifiers. Handles, emails, organization usernames, and third-party accounts are verifiable attributes, not protocol primary keys.

Core decisions:

- Default native method: `did:uuid:<uuid-v8>`.
- `did:uuid` embeds a timestamp, hash algorithm id, and 74-bit inception public-key hash fragment.
- Ordinary key rotation MUST NOT change the DID.
- Current control keys MUST be traceable from `inception_key` through `key_log`.
- Canonical Contrix fields use snake_case.
- Raw W3C DID/VC documents MAY be preserved as external evidence and mapped into Contrix normalized views.
- Public-persona DIDs MAY publish `also_known_as`; pairwise/private DIDs SHOULD NOT.

Raw W3C field mappings:

| Raw field | Contrix canonical field |
| --- | --- |
| `alsoKnownAs` | `also_known_as` |
| `verificationMethod` | `verification_method` |
| `assertionMethod` | `assertion_method` |
| `publicKeyMultibase` | `public_key_multibase` |
| `serviceEndpoint` | `service_endpoint` |

## Resolver, Auth Server, And Organization Authorization

DID resolution, login authentication, and organization data authorization are separate responsibilities:

| Layer | Responsible for | Not responsible for |
| --- | --- | --- |
| Identity Registry / Resolver | Resolving a DID to a DID Document, key log, service delegation, and witness evidence. | Deciding whether the user may log in to an organization or access Space / repo data. |
| Auth / Account Server | Passkeys, OIDC, SSO, device pairing, account recovery, session grants, and binding a service-account login to a DID / device. | Changing DID control, replacing DID key proof, or deciding every organization authorization rule. |
| Organization / Policy / Authz | Deciding whether a DID, device, credential, or capability may access organization data, Spaces, repos, Applets, or admin actions. | Maintaining public DID control history. |

An organization MAY run its own Auth / Account Server while continuing to use the public `did:uuid` resolver network. A typical flow is:

1. The user submits `did:uuid:...`, a handle, an invitation link, or an organization account.
2. The organization Auth Server selects a resolver according to local trust policy. Standard deployments may default to the public `did:uuid` resolver; high-security deployments may use an organization-private resolver; `did:web` resolves according to its DID method and domain.
3. The Auth Server or client resolves the DID Document and verifies the key log, witness evidence, service delegation, and acceptable trust domain.
4. The user proves login binding through a DID control key, device key, passkey / OIDC binding proof, or required VC presentation.
5. The Auth Server issues only a session grant / device binding. Organization Policy / Authz then decides data access from the DID, credentials, membership, invites, capabilities, and Space policy.

Therefore, a public `did:uuid` resolver is public identity-control and service-discovery infrastructure; an enterprise Auth Server is that enterprise's login and session boundary. Using a public resolver does not let the resolver log in to the enterprise or access enterprise data. Allowing a `did:uuid` to log in means the organization's policy accepts that DID, its control proof, and any required credential or invite.

For `did:web` and other method-specific DID methods, resolver selection is determined by the method rules plus local trust policy. An organization may require employees or service principals to use `did:web`, organization-private `did:uuid`, or public `did:uuid`; this is an admission policy, not a natural coupling between the Auth Server and Resolver.

The detailed Chinese draft is currently normative for bit layout and registry semantics.

