# Encoding, IDs, Hashes, Signatures

Contrix canonical JSON uses UTF-8, sorted object keys, no insignificant whitespace, valid JSON numbers, RFC 3339 UTC timestamps, and snake_case fields.

Default digest:

```text
sha256:<lowercase_hex_digest>
```

Default ID:

```text
cx:<kind>:<ulid>
```

Default proof is detached JWS bound to payload hash, actor DID, verification method, audience/domain where applicable, and creation time.

