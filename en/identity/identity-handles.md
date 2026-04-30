# Handles and Claim Proofs

Handles are human-readable entry points, not authorization subjects.

The protocol MUST NOT use handles, emails, domain usernames, or organization namespace strings directly as grant subjects or event actors. Correct authorization uses:

```text
grant subject = DID
authorization condition = verified claim / attestation
```

Matrix-style identifiers such as `@alice:example.org` MAY be accepted as user-facing handles, login names, contact search entries, or bridge aliases. Implementations MUST preserve their external system, localpart, domain / origin server, and normalization rules; they MUST NOT treat those identifiers directly as DIDs, grant subjects, Event actors, or unverified organization-membership proofs.

DNS / HTTPS well-known resolution applies to DNS-style handles. Non-DNS handles such as `@alice:example.org` or `alice@google.com` MAY resolve through an organization Directory, Auth / Account Server, bridge registry, or trusted issuer claim, but the result still MUST reduce to a DID plus verifiable binding evidence.

Implementations MUST distinguish:

| Layer | Examples | Use | Protocol subject |
| --- | --- | --- | --- |
| Connection Identifier | email, phone, contact username, external account id | contact discovery, consent, invite, initial relationship | no |
| Administrative Identifier | organization account, billing account, managed employee id | local administration, compliance, recovery | no |
| Handle | DNS handle, Matrix-style id | human entry point and alias | no |
| Display Name | `Alice Zhang` | UI display | no |
| Principal DID | `did:uuid:...`, `did:web:...` | signing, authorization, accountability | yes |

Connection identifiers are relationship-private discovery inputs. They MUST NOT automatically enter DID Documents, Space history, membership events, grants, or MLS credentials. A provider proof of reachability still reduces to a DID or pending invite proof with purpose, audience, expiry, and issuer proof.

Contrix separates:

- public persona handle binding through `also_known_as`
- pairwise/private DIDs for privacy-sensitive relationships
- verifiable credentials for organization membership, handle ownership, email control, and role claims
- selective-disclosure or unlinkable presentations for high-privacy proofs

For `alice@google.com` and `alice@facebook.com`, the recommended model is separate pairwise DIDs and separate credentials. A verifier for Google MUST NOT require disclosure of Facebook credentials, DIDs, or handles unless the holder explicitly provides a linking proof.

