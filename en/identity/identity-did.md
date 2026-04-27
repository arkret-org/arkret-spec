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

The detailed Chinese draft is currently normative for bit layout and registry semantics.

