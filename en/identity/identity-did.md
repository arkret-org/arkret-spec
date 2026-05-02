# DID Identity

Contrix uses DIDs as stable principal identifiers. Handles, emails, organization usernames, and third-party accounts are verifiable attributes, not protocol primary keys.

Contrix v1 does not define, register, or recommend a Contrix-specific DID method. Implementations and users MUST use existing DID methods, such as `did:plc`, `did:web`, `did:webvh`, `did:key`, `did:pkh`, or another public DID method explicitly allowed by local trust policy.

Core decisions:

- The default public principal DID method is `did:plc`.
- Organization and service DIDs SHOULD use `did:web`; high-assurance organization DIDs SHOULD use `did:webvh` or an equivalent history-bearing method.
- `did:key` is suitable for temporary, test, device, invitation, or bootstrap subjects.
- `did:pkh` is suitable only when a wallet or blockchain account is the intended identity root.
- New protocol objects, examples, fixtures, and conformance vectors MUST NOT use `did:uuid`.
- Raw W3C DID/VC documents and method-specific history MUST be preserved as external evidence and mapped into Contrix normalized views.
- Public-persona DIDs MAY publish `alsoKnownAs`; pairwise/private DIDs SHOULD NOT.

## User-Facing Identifiers Are Optional

Implementations MAY let users discover, log in, invite, or recover accounts through `@alice:example.org`, `alice@example.org`, organization usernames, OIDC subjects, invitation links, or other human-readable identifiers.

These identifiers are user-facing identifiers, service-account ids, handles, 3PIDs, or bridge aliases; they are not protocol primary keys. Before accepting any durable Event, repo commit, capability grant, federation transaction, MLS membership, or service delegation, the implementation MUST bind the current session to a principal DID and device, then verify that binding according to local trust policy.

If the user does not yet have an explicit DID, an Auth / Account Server MAY create a supported managed DID before registration completion, invite claiming, or first write. Public Contrix deployments default to `did:plc` for ordinary user principals. Organization or service principals SHOULD use `did:web`, and SHOULD use `did:webvh` when verifiable history is required. The managed DID's controller, recovery policy, trust domain, method-specific history, and service-account binding MUST be auditable; subsequent protocol objects still use the DID as the root for `actor_id`, `repo_id`, `author`, grant `subject`, service DID, or `verification_method`.

## Method Selection

| Scenario | Default / recommended DID method | Notes |
| --- | --- | --- |
| Ordinary user principal DID | `did:plc` | Default choice for users without domains; supports rotation and recovery. |
| User-owned domain identity | `did:web` or `did:webvh` | Optional when the user wants identity bound to a domain; `did:webvh` adds verifiable history. |
| Organization DID | `did:webvh` SHOULD, `did:web` MAY | Organizations usually control domains; high-assurance orgs should use history, watchers, or witnesses. |
| Service DID | `did:web` SHOULD, `did:webvh` MAY | Service discovery naturally maps to HTTPS endpoints. |
| Temporary subjects, devices, tests, one-time invitations | `did:key` | Local resolution and no network dependency; not the default long-lived identity. |
| Wallet or blockchain account binding | `did:pkh` | Use only when wallet control is the intended root. |
| High-security or sovereign deployment | Existing DID method selected by policy | Trust roots and resolver rules MUST be explicit. |

Core resolver / verifier implementations MUST support `did:plc` and `did:web`, SHOULD support `did:key`, SHOULD support `did:webvh` for organization / high-security profiles, and MAY support `did:pkh` for wallet interop.

## Identity Resolution Infrastructure

Contrix abstracts identity resolution as `Identity Resolution Infrastructure`; it does not require every DID method to use the same Identity Registry model.

| DID method | Requires public Identity Registry? | Required resolution / verification capability |
| --- | --- | --- |
| `did:plc` | Requires an accepted PLC directory, mirror, or audit source. | Verify the PLC operation chain, genesis / previous op hashes, rotation keys, recovery state, DID Document, service bindings, and directory transparency evidence. |
| `did:web` | No public registry. | HTTPS / DNS / domain governance, TLS / PKI, and method-specific DID Document retrieval and verification. |
| `did:webvh` | No traditional public registry. | `did.jsonl` history, SCID, entry hash chain, controller proofs, watcher / witness evidence, HTTPS / DNS verification. |
| `did:key` | No. | Local method resolver expands the DID string into a DID Document. It fits temporary subjects, devices, tests, one-time invitations, or bootstrap keys. |
| `did:pkh` | No Contrix registry. | CAIP-10 / chain-specific account validation, wallet proof, and chain namespace policy. |
| Other existing DID methods | Depends on the method. | Preserve raw DID Documents and method-specific proofs, then map into the Contrix normalized principal view. |

Using `did:key` or `did:pkh` does not mean identity resolution disappears. It means a public writable registry is usually unnecessary. Clients, Auth Servers, Principal Servers, and Policy / Authz still need the corresponding DID method resolver / verifier to confirm DID control state, service delegation, and method limitations.

## Resolver Policy

Resolver policy MUST define accepted methods, the default principal method, trust roots, method capability, privacy handling, cache rules, and fail-closed behavior.

Example:

```json
{
  "default_principal_method": "did:plc",
  "allowed_methods": ["did:plc", "did:web", "did:webvh", "did:key", "did:pkh"],
  "method_policy": {
    "did:plc": {
      "role": ["principal"],
      "directory": ["https://plc.directory"],
      "require_operation_history": true
    },
    "did:web": {
      "role": ["organization", "service", "principal"],
      "require_https": true
    },
    "did:key": {
      "role": ["device", "test", "bootstrap"],
      "long_lived_principal": "deny"
    }
  }
}
```

## Resolver, Auth Server, And Organization Authorization

DID resolution, login authentication, and organization data authorization are separate responsibilities:

| Layer | Responsible for | Not responsible for |
| --- | --- | --- |
| Identity Resolution Infrastructure | Resolving a DID to a DID Document, key state, method history, service delegation, witness evidence, or method-specific proof. | Deciding whether the user may log in to an organization or access Space / repo data. |
| Auth / Account Server | Passkeys, OIDC, SSO, device pairing, account recovery, session grants, and binding a service-account login to a DID / device. | Changing DID control, replacing DID key proof, or deciding every organization authorization rule. |
| Organization / Policy / Authz | Deciding whether a DID, device, credential, or capability may access organization data, Spaces, repos, Applets, or admin actions. | Maintaining public DID control history. |

When a user registers, claims, or binds an organization service account with an existing DID, the Auth / Account Server MUST verify that the caller currently controls that DID. Submitting only a DID string, handle, email code, OIDC subject, or organization username is not sufficient to establish the binding.

The recommended DID proof is challenge-response:

1. The user submits the DID to bind.
2. The Auth Server resolves the DID Document and verifies the method, history, witness / directory evidence, deactivation state, and accepted trust domain according to local policy.
3. The Auth Server creates a one-time challenge bound to purpose, target service, origin / audience, expiry, and a random nonce.
4. The client signs the challenge with a currently valid DID `authentication` verification method, authorized device key, or temporary key covered by a valid session / device grant.
5. The Auth Server verifies the signature, the current validity of the verification method, and that the challenge is unexpired and unused.
6. After verification, the Auth Server MAY create or update the `service_account -> principal_id` binding and issue a short-lived `cx.session.grant` or record a device binding.

Example payload:

```json
{
  "type": "cx.did.proof",
  "purpose": "account_binding",
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "audience": "did:web:auth.acme.example",
  "origin": "https://auth.acme.example",
  "challenge": "base64url-random",
  "issued_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:05:00Z"
}
```

The service-account binding is local organization state. It does not transfer DID ownership to the organization and does not allow the organization to rotate, recover, or deactivate the user's DID unless the DID's own control state or recovery policy authorizes that action.

## DID Documents And Normalized Principal View

Raw W3C DID Core / VC documents on the wire MUST retain their standard field names. Implementations MUST NOT rewrite DID Document fields such as `alsoKnownAs`, `verificationMethod`, `assertionMethod`, `publicKeyMultibase`, `publicKeyJwk`, `serviceEndpoint`, or VC fields such as `credentialSubject`, `validFrom`, `validUntil`, and `credentialStatus` into snake_case and then emit them as raw DID / VC documents.

Contrix-owned envelopes, API parameters, indexes, policy inputs, and reducer inputs still use snake_case. Implementations MAY construct an internal normalized principal view, but that view is a derived projection, not the DID Document itself. Re-publishing or forwarding DID / VC data MUST use the original standard field names.

Normalized principal view SHOULD include `did`, `did_method`, `support_profile`, `raw_document_hash`, `raw_history_ref`, `current_control_keys`, `authentication_methods`, `assertion_methods`, `service_bindings`, `contrix_bindings`, `method_evidence`, and `limitations`.

Contrix MUST NOT rewrite external DID documents into a private DID method, invent unsupported fields, discard method-specific history, or accept every service endpoint merely because the DID Document resolves.

## Method-Specific Operations

DID updates MUST use the selected DID method's operation format, authorization rules, and submission channel. Contrix does not define a generic private DID operation patch format.

Identity Resolution Surface MAY expose a uniform API for submitting or querying method-specific operations, but the request body MUST explicitly carry `did_method`, the raw operation, proofs, and resolver policy context.

## Legacy `did:uuid`

New implementations, test vectors, fixtures, normative examples, service DIDs, actor DIDs, capability subjects, federation transactions, and newly written Events MUST NOT use `did:uuid`.

Existing historical data that already contains `did:uuid` MAY be retained as read-only legacy data. Migration MUST create a new supported DID and bind the legacy identifier to it through verifiable link claims, old-key proof, new-DID proof, organization governance records, or manual audit records. Implementations MUST NOT pretend that legacy `did:uuid` is a conformant DID method for new writes.

## Conformance

Contrix v1 DID conformance requires:

- Default principal DID creation MUST use `did:plc` unless deployment policy explicitly selects another existing DID method.
- Method adapter conformance tests MUST cover `did:plc`, `did:web`, `did:key`, and SHOULD cover `did:webvh` or another history-bearing method.
- DID proof schemas MUST align with `data-structures.md` Proof and `encoding.md` canonical JSON rules.
- Normalized principal views MUST retain raw document hashes, method-specific proofs, current control keys, service bindings, Contrix bindings, and evidence.
- Adapters that cannot verify method history may only declare a limited trust profile and MUST NOT be used by default for high-risk organizations, service delegation, or long-lived principal creation.
