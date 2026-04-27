# Handles and Claim Proofs

Handles are human-readable entry points, not authorization subjects.

The protocol MUST NOT use handles, emails, domain usernames, or organization namespace strings directly as grant subjects or event actors. Correct authorization uses:

```text
grant subject = DID
authorization condition = verified claim / attestation
```

Contrix separates:

- public persona handle binding through `also_known_as`
- pairwise/private DIDs for privacy-sensitive relationships
- verifiable credentials for organization membership, handle ownership, email control, and role claims
- selective-disclosure or unlinkable presentations for high-privacy proofs

For `alice@google.com` and `alice@facebook.com`, the recommended model is separate pairwise DIDs and separate credentials. A verifier for Google MUST NOT require disclosure of Facebook credentials, DIDs, or handles unless the holder explicitly provides a linking proof.

