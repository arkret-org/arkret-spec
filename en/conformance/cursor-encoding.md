# Cursor Encoding Specification

## 1. Overview

This specification defines the encoding format for sync cursors in Contrix v1. Cursors are opaque tokens used for incremental synchronization and must support reliable resumption across client sessions.

## 2. Cursor Structure

Contrix v1 uses a structured JSON encoding with Base64URL representation for transport.

### 2.1 Schema

```json
{
  "v": "1",
  "t": "2026-04-26T00:00:00.000Z",
  "s": {
    "cx:space:01JS0SP000000000000000000": {
      "p": ["cx:evt:01JS0EV000000000000000000"],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:abc123..."
    }
  },
  "d": {
    "device-1": "cx:devmsg:01JS0DM000000000000000000"
  },
  "x": 1714080000000
}
```

### 2.2 Field Definitions

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `v` | string | yes | Cursor version, must be "1" |
| `t` | timestamp | yes | Cursor generation timestamp |
| `s` | object | yes | Space positions map |
| `s.<space_id>` | object | yes | Per-space position |
| `s.<space_id>.p` | array | yes | Causal frontier (event IDs) |
| `s.<space_id>.o` | string | yes | Timeline order HLC |
| `s.<space_id>.h` | hash | yes | State hash at this position |
| `d` | object | no | Device positions map |
| `d.<device_id>` | string | yes | Last processed message ID |
| `x` | integer | yes | Expiration timestamp (Unix ms) |

## 3. Transport Encoding

The JSON object is serialized to canonical JSON (no extra whitespace, keys sorted) and encoded using Base64URL without padding.

### 3.1 Example

Input:
```json
{"v":"1","s":{}}
```

Encoded:
`eyJ2IjoiMSIsInM6e30ifQ` (Note: padding removed)

## 4. Validation Rules

Servers MUST validate cursors on receipt:

1. **Version Check**: `v` must be supported
2. **Expiration**: `x` must be in the future (allow 5 min clock skew)
3. **Structure**: Must be valid JSON after decoding
4. **Space IDs**: All space IDs must be valid `cx:space:*` format
5. **Event IDs**: All event IDs in causal frontiers must be valid
6. **HLC Format**: Timeline order must be valid HLC format

Invalid cursors MUST be rejected with `invalid_cursor` error.

## 5. Cursor Evolution

### 5.1 Version 1

Initial version with space positions, causal frontiers, and device positions.

### 5.2 Future Versions

New cursor versions:
- MUST use different `v` values
- MUST be backwards compatible or provide migration
- SHOULD support graceful degradation

## 6. Security Considerations

1. **Tamper Detection**: Clients SHOULD verify cursor content matches sync state
2. **Expiration**: Cursors MUST expire to prevent stale state replay
3. **Privacy**: Cursors may reveal space access patterns; encrypt in sensitive contexts
4. **Size Limits**: Servers MAY reject cursors exceeding 4KB after encoding

## 7. Implementation Notes

### 7.1 Client Behavior

- Always use the most recent `next_batch` cursor
- Store cursor locally for resume capability
- Handle `cursor_expired` by starting fresh sync
- Don't modify cursor content

### 7.2 Server Behavior

- Generate new cursor after each sync response
- Include all necessary state positions
- Set appropriate expiration (recommended: 7 days)
- Validate cursors on resume requests

### 7.3 Compression

For large accounts with many spaces, servers MAY use compression:
- Apply gzip before Base64URL encoding
- Add `c=gz` flag to indicate compression
- Clients must support decompression

## 8. Conformance

Implementations claiming Contrix v1 sync support MUST:
- Accept and generate version 1 cursors
- Validate all cursor fields
- Support at least 50 spaces per cursor
- Support expiration times up to 7 days
- Reject invalid cursors with appropriate errors

## 9. Examples

### 9.1 Initial Sync

Request without `since`:
```json
{}
```

Response with first cursor:
```json
{
  "next_batch": "eyJ2IjoiMSIsInMiOnt9fQ",
  "spaces": {...}
}
```

### 9.2 Resume Sync

Request with cursor:
```json
{
  "since": "eyJ2IjoiMSIsInMiOnt9fQ"
}
```

### 9.3 Expired Cursor Error

Response:
```json
{
  "error": "cursor_expired",
  "error_description": "The provided cursor has expired. Please perform initial sync.",
  "retry_after_ms": 0
}
```
