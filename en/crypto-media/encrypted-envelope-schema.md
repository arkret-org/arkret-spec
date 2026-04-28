# Encrypted Payload Envelope Schema

## 1. Overview

This specification defines the envelope format for encrypted content in Contrix v1. The envelope supports both MLS (RFC 9420) and future encryption schemes while maintaining protocol compatibility.

## 2. Envelope Structure

### 2.1 Schema

```json
{
  "envelope": {
    "scheme": "mls-rfc9420",
    "version": "1.0",
    "group_id": "base64url",
    "epoch": "integer",
    "content_type": "string",
    "ciphertext": "base64url",
    "authentication_tag": "base64url",
    "aad": {
      "space_id": "cx:space:...",
      "event_type": "cx.message.create",
      "event_id": "cx:event:...",
      "causal_refs": ["cx:event:..."]
    },
    "key_ref": {
      "algorithm": "MLS",
      "ratchet_tree": "base64url"
    },
    "digests": {
      "payload_digest": "sha256:...",
      "aad_digest": "sha256:..."
    }
  }
}
```

### 2.2 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `scheme` | string | yes | Encryption scheme identifier |
| `version` | string | yes | Scheme version |
| `group_id` | string | yes | MLS group ID (Base64URL) |
| `epoch` | integer | yes | MLS epoch number |
| `content_type` | string | yes | MIME type of decrypted content |
| `ciphertext` | string | yes | Encrypted payload (Base64URL) |
| `authentication_tag` | string | yes | AEAD authentication tag (Base64URL) |
| `aad` | object | yes | Additional Authenticated Data |
| `aad.space_id` | id:space | yes | Space for routing and authorization |
| `aad.event_type` | string | yes | Event type for routing |
| `aad.event_id` | id:event | yes | Event ID for deduplication |
| `aad.causal_refs` | array | yes | Causal dependencies |
| `key_ref` | object | conditional | Key material reference (optional for recipients) |
| `digests` | object | yes | Cryptographic digests |
| `digests.payload_digest` | hash | yes | SHA256 of ciphertext+tag |
| `digests.aad_digest` | hash | yes | SHA256 of canonical AAD |

## 3. Additional Authenticated Data (AAD)

### 3.1 Purpose

AAD contains routing metadata that:
- Must be plaintext for sync routing
- Is covered by authentication (integrity protected)
- Cannot be tampered with without detection

### 3.2 Canonical AAD Serialization

AAD must be serialized to canonical JSON before computing `aad_digest`:

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "event_type": "cx.message.create",
  "event_id": "cx:event:01JS0EV000000000000000000",
  "causal_refs": ["cx:event:01JS0EU000000000000000000"]
}
```

Rules:
- Keys sorted lexicographically
- No extra whitespace
- No trailing commas
- Strings use UTF-8 encoding

## 4. Encryption Schemes

### 4.1 MLS (RFC 9420)

**Identifier**: `mls-rfc9420`

**Parameters**:
- `group_id`: MLS group identifier
- `epoch`: Current MLS epoch
- `ciphertext`: MLS encrypted application message
- `authentication_tag`: Included in MLS message

**Key Material**:
- Senders use current MLS epoch key
- Recipients derive from MLS ratchet tree
- Key distribution via MLS Welcome/Commit

### 4.2 Future Schemes

New schemes MUST:
- Use unique `scheme` identifier
- Define required fields
- Specify key distribution
- Maintain AAD compatibility
- Register in protocol schema registry

## 5. Encryption Process

### 5.1 Sender Flow

```
1. Collect content to encrypt
2. Serialize to bytes (e.g., JSON, UTF-8 string)
3. Generate AAD from event metadata
4. Fetch current MLS epoch key
5. Encrypt content using AEAD
6. Compute digests
7. Assemble envelope
```

### 5.2 Pseudocode

```
function encrypt_content(content, aad, group_context):
    plaintext = serialize(content)
    aad_bytes = canonical_json(aad)
    key = derive_epoch_key(group_context)
    (ciphertext, tag) = aead_encrypt(key, plaintext, aad_bytes)
    payload_digest = sha256(ciphertext || tag)
    aad_digest = sha256(aad_bytes)

    return {
        scheme: "mls-rfc9420",
        group_id: group_context.id,
        epoch: group_context.epoch,
        content_type: "application/json",
        ciphertext: base64url_encode(ciphertext),
        authentication_tag: base64url_encode(tag),
        aad: aad,
        digests: {
            payload_digest: "sha256:" + payload_digest,
            aad_digest: "sha256:" + aad_digest
        }
    }
```

## 6. Decryption Process

### 6.1 Recipient Flow

```
1. Extract envelope fields
2. Verify AAD integrity using aad_digest
3. Verify payload integrity using payload_digest
4. Fetch MLS epoch key for group_id/epoch
5. Decrypt ciphertext using AEAD with AAD
6. Deserialize plaintext to content
```

### 6.2 Error Handling

| Error | Cause | Response |
|-------|-------|----------|
| `aad_digest_mismatch` | AAD tampered | Reject entire event |
| `payload_digest_mismatch` | Ciphertext corrupted | Reject entire event |
| `key_unavailable` | Missing epoch | Mark as `decryption_pending` |
| `epoch_mismatch` | Wrong key epoch | Backtrack or fetch epoch |
| `group_removed` | No longer member | Fail closed |

## 7. Integration with Events

### 7.1 Event with Encrypted Content

```json
{
  "event_id": "cx:event:01JS0EV000000000000000000",
  "kind": "cx.message.create",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "actor_id": "did:web:alice.example.com",
  "hlc": "01970e589d21-0004-a13f9c2e",
  "prev_refs": ["cx:event:01JS0EU000000000000000000"],
  "content": {
    "encrypted_envelope": {
      "scheme": "mls-rfc9420",
      ...
    }
  },
  "proofs": [...]
}
```

### 7.2 Plaintext AAD for Routing

Sync services use AAD fields for routing:
- `space_id`: Route to correct Space
- `event_type`: Determine event handling
- `causal_refs`: Maintain causal ordering

None of this requires decryption.

## 8. Key Distribution

### 8.1 MLS KeyPackage

Actors publish KeyPackage for MLS:
```json
{
  "keypackage_id": "cx:mls:kp:...",
  "actor_id": "did:web:alice.example.com",
  "public_key": "base64url",
  "cipher_suites": ["MLS_128_DHKEMX25519_AES128GCM_SHA256_Ed25519"],
  "extensions": {...},
  "signature": "base64url",
  "expires_at": "2026-05-26T00:00:00Z"
}
```

### 8.2 Epoch Changes

When MLS epoch changes:
1. Admin sends `cx.mls.commit` event
2. Contains new ratchet tree
3. Recipients update epoch keys
4. New envelopes use new epoch

## 9. Security Considerations

### 9.1 Forward Secrecy

MLS provides:
- Past messages undecryptable with current keys
- Epoch rotation changes group secrets
- Removed members can't decrypt new messages

### 9.2 Post-Compromise Security

MLS provides:
- Compromise at time T doesn't compromise T+1
- Epoch rotation with new key material
- Regular forced epoch rotation recommended

### 9.3 Replay Prevention

Envelopes include:
- `event_id` in AAD for deduplication
- `epoch` to detect old key reuse
- Servers enforce event ID uniqueness

### 9.4 Audit Trail

For auditable E2EE:
- Audit agents are MLS group members
- Decryption access logged via `cx.audit.accessed`
- All members can see audit trail

## 10. Performance Considerations

### 10.1 Envelope Size

Typical envelope size:
- AAD: ~100 bytes
- Ciphertext: content length + 16 bytes (tag)
- Metadata: ~50 bytes
- Total: content + ~166 bytes

### 10.2 Key Caching

Recipients should cache:
- Epoch keys by `(group_id, epoch)`
- Periodic refresh for post-compromise security
- Invalidation on group membership change

## 11. Testing

### 11.1 Test Vectors

Implementations must pass:
- Encryption/decryption roundtrip
- AAD integrity verification
- Digest computation
- MLS epoch changes
- Multi-recipient scenarios

### 11.2 Interoperability

Test matrix:
- Different MLS cipher suites
- Different content types
- Different AAD configurations
- Cross-implementation decryption

## 12. Migration Path

### 12.1 From Plaintext

Migrating Space to encrypted:
1. Add `encryption_profile` to Space policy
2. Create MLS group via `cx.mls.create`
3. New content encrypted
4. Old content remains plaintext

### 12.2 Encryption Schemes

Adding new schemes:
1. Register scheme identifier
2. Define envelope format
3. Implement key distribution
4. Maintain AAD compatibility
5. Update conformance tests

## 13. Conformance

Implementations MUST:
- Accept MLS envelopes as defined
- Verify all digests before decryption
- Support AAD-based routing
- Handle decryption errors gracefully
- Log `decryption_pending` for missing keys

Implementations SHOULD:
- Cache epoch keys for performance
- Support multiple cipher suites
- Implement forced epoch rotation
- Provide key backup/recovery
- Support audit mode where required

## 14. Examples

### 14.1 Simple Message

```json
{
  "envelope": {
    "scheme": "mls-rfc9420",
    "group_id": "6yg7KVGVmA",
    "epoch": 42,
    "content_type": "application/json",
    "ciphertext": "SGVsbG8gV29ybGQ",
    "authentication_tag": "dGhpcyBpcyBhIHRhZw",
    "aad": {
      "space_id": "cx:space:01JS0SP000000000000000000",
      "event_type": "cx.message.create",
      "event_id": "cx:event:01JS0EV000000000000000000",
      "causal_refs": []
    },
    "digests": {
      "payload_digest": "sha256:abc123...",
      "aad_digest": "sha256:def456..."
    }
  }
}
```

### 14.2 With Attachment Reference

```json
{
  "content": {
    "body": {"encrypted_envelope": {...}},
    "attachments": [
      {
        "blob_ref": "cx:blob:...",
        "filename": "document.pdf",
        "encryption": {"encrypted_envelope": {...}}
      }
    ]
  }
}
```
