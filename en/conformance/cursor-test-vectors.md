# Cursor Encoding Conformance Test Vectors

## 1. Cursor Encoding Tests

### 1.1 Valid Cursor Examples

#### Minimal Cursor

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z",
    "s": {},
    "x": 1714080000000
  },
  "encoded": "eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoiLCJzIjp7fSwieCI6MTcxNDA4MDAwMDAwMH0",
  "decoded_matches": true
}
```

#### Cursor with Space Position

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T12:34:56.789Z",
    "s": {
      "cx:space:01JS0SP000000000000000000": {
        "p": ["cx:evt:01JS0EV000000000000000000"],
        "o": "01970e589d21-0004-a13f9c2e",
        "h": "sha256:abc123def4567890123456789012345678901234567890123456789012345678"
      }
    },
    "x": 1714125296789
  },
  "encoded": "eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDEyOjM0OjU2Ljc4OVoiLCJzIjp7ImN4OnNwYWNlOjAxSlMwU1AwMDAwMDAwMDAwMDAwMDAwMDAwIjp7InAiOlsiY3g6ZXZ0OjAxSlMwRVYwMDAwMDAwMDAwMDAwMDAwMDAwMCJdLCJvIjoiMDE5NzBlNTh5ZDIxLTAwMDQtYTEzZjljMmUiLCJoIjoic2hhMjU2OmFiYzEyM2RlZjQ1Njc4OTAxMjM0NTY3ODkwMTIzNDU2Nzg5MDEyMzQ1Njc4OTAxMjM0NTY3OCJ9fSwieCI6MTcxNDEyNTI5Njc4OX0",
  "decoded_matches": true
}
```

#### Cursor with Device Positions

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z",
    "s": {
      "cx:space:01JS0SP000000000000000000": {
        "p": [],
        "o": "01970e589d21-0000-a13f9c2e",
        "h": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    },
    "d": {
      "device-laptop": "cx:devmsg:01JS0DM000000000000000000",
      "device-phone": "cx:devmsg:01JS0DM000000000000000001"
    },
    "x": 1714080000000
  },
  "encoded": "eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoiLCJzIjp7ImN4OnNwYWNlOjAxSlMwU1AwMDAwMDAwMDAwMDAwMDAwMDAwIjp7InAiOltdLCJvIjoiMDE5NzBlNTh5ZDIxLTAwMDAtYTEzZjljMmUiLCJoIjoic2hhMjU2OjAxMjM0NTY3ODlhYmNkZWYwMTIzNDU2Nzg5YWJjZGVmMDEyMzQ1Njc4OWFiY2RlZjAxMjM0NTY3ODlhYmNkZWYifX0sImQiOnsiZGV2aWNlLWxhcHRvcCI6ImN4OmRldm1zZzowMUpTMERNMDAwMDAwMDAwMDAwMDAwMDAwMCIsImRldmljZS1waG9uZSI6ImN4OmRldm1zZzowMUpTMERNMDAwMDAwMDAwMDAwMDAwMDAwMSJ9LCJ4IjoxNzE0MDgwMDAwMDAwfQ",
  "decoded_matches": true
}
```

### 1.2 Invalid Cursor Examples

#### Missing Required Field

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z"
    // Missing "s" and "x"
  },
  "encoded": "eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoifQ",
  "expected_error": "invalid_cursor: missing_required_field"
}
```

#### Invalid Version

```json
{
  "cursor_json": {
    "v": "2",  // Unsupported version
    "t": "2026-04-26T00:00:00.000Z",
    "s": {},
    "x": 1714080000000
  },
  "encoded": "eyJ2IjoiMiIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoiLCJzIjp7fSwieCI6MTcxNDA4MDAwMDAwMH0",
  "expected_error": "invalid_cursor: unsupported_version"
}
```

#### Invalid Space ID Format

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z",
    "s": {
      "invalid-space-id": {
        "p": [],
        "o": "01970e589d21-0000-a13f9c2e",
        "h": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    },
    "x": 1714080000000
  },
  "expected_error": "invalid_cursor: invalid_space_id_format"
}
```

#### Invalid HLC Format

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z",
    "s": {
      "cx:space:01JS0SP000000000000000000": {
        "p": [],
        "o": "not-a-valid-hlc",
        "h": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
      }
    },
    "x": 1714080000000
  },
  "expected_error": "invalid_cursor: invalid_hlc_format"
}
```

#### Expired Cursor

```json
{
  "cursor_json": {
    "v": "1",
    "t": "2026-04-26T00:00:00.000Z",
    "s": {},
    "x": 1614080000000  // More than 7 days ago
  },
  "encoded": "eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoiLCJzIjp7fSwieCI6MTYxNDA4MDAwMDAwMH0",
  "current_time": "2026-04-26T00:00:00.000Z",
  "expected_error": "cursor_expired"
}
```

## 2. Cursor Validation Tests

### 2.1 Structure Validation

```
Test: Verify cursor structure integrity

Input cursor:
{
  "v": "1",
  "t": "2026-04-26T12:00:00.000Z",
  "s": {},
  "x": 1714104000000
}

Checks:
  1. ✓ "v" is present and equals "1"
  2. ✓ "t" is valid RFC 3339 timestamp
  3. ✓ "s" is object (can be empty)
  4. ✓ "x" is positive integer
  5. ✓ "x" is not in the past (within 7 days)
  6. ✓ No extra fields beyond specification

Result: PASS
```

### 2.2 Space Position Validation

```
Test: Validate space position structure

Input cursor:
{
  "v": "1",
  "t": "2026-04-26T12:00:00.000Z",
  "s": {
    "cx:space:01JS0SP000000000000000000": {
      "p": ["cx:evt:01JS0EV000000000000000000"],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:abc123..."
    }
  },
  "x": 1714104000000
}

Checks:
  1. ✓ Space ID matches format ^cx:space:[ULID]$
  2. ✓ "p" is array of valid event IDs
  3. ✓ "o" matches HLC format
  4. ✓ "h" matches SHA256 format
  5. ✓ No extra fields in space position

Result: PASS
```

### 2.3 Causal Frontier Validation

```
Test: Validate causal frontier event IDs

Input cursor with causal frontier:
{
  "s": {
    "cx:space:...": {
      "p": [
        "cx:evt:01JS0EV000000000000000000",
        "cx:evt:01JS0EV000000000000000001",
        "cx:evt:01JS0EV000000000000000002"
      ],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:..."
    }
  }
}

Checks:
  1. ✓ All event IDs match format
  2. ✓ All event IDs are unique
  3. ✓ Array is not empty for active spaces
  4. ✓ Order represents causal dependencies

Result: PASS
```

## 3. Cursor Encoding/Decoding Tests

### 3.1 Canonical JSON Serialization

```
Test: Verify canonical JSON encoding

Input:
{
  "v": "1",
  "t": "2026-04-26T00:00:00.000Z",
  "s": {},
  "x": 1714080000000
}

Canonical JSON (keys sorted):
{"v":"1","t":"2026-04-26T00:00:00.000Z","s":{},"x":1714080000000}

Base64URL (no padding):
eyJ2IjoiMSIsInQiOiIyMDI2LTA0LTI2VDAwOjAwOjAwLjAwMFoiLCJzIjp7fSwieCI6MTcxNDA4MDAwMDAwMH0

Verification:
  ✓ Keys are sorted alphabetically
  ✓ No extra whitespace
  ✓ No trailing commas
  ✓ Base64URL encoding without "=" padding
```

### 3.2 Round-trip Encoding

```
Test: Encode and decode cursor

Original:
{
  "v": "1",
  "t": "2026-04-26T12:34:56.789Z",
  "s": {
    "cx:space:01JS0SP000000000000000000": {
      "p": ["cx:evt:01JS0EV000000000000000000"],
      "o": "01970e589d21-0004-a13f9c2e",
      "h": "sha256:abc123..."
    }
  },
  "x": 1714125296789
}

Process:
  1. Serialize to canonical JSON
  2. Encode to Base64URL
  3. Decode from Base64URL
  4. Parse JSON

Expected: Decoded cursor matches original
Result: PASS
```

## 4. Cursor Expiration Tests

### 4.1 Expiration Calculation

```
Test: Calculate cursor expiration

Input:
{
  "x": 1714080000000  // 2026-04-26T00:00:00.000Z
}

Current time: 2026-05-01T00:00:00.000Z

Check:
  - Cursor expires at: 2026-04-26T00:00:00.000Z
  - Current time > Expiration time
  - Time difference: 5 days (more than 7 days ago)

Expected: cursor_expired error
Result: PASS
```

### 4.2 Valid Cursor Time Window

```
Test: Accept cursor within valid time window

Input:
{
  "x": 1714684800000  // 2026-05-02T00:00:00.000Z
}

Current time: 2026-05-03T00:00:00.000Z

Check:
  - Cursor expires at: 2026-05-02T00:00:00.000Z
  - Current time: 2026-05-03T00:00:00.000Z
  - Time difference: 1 day (within 7 days)

Expected: cursor is valid
Result: PASS
```

## 5. Integration Tests

### 5.1 Cursor Resume Flow

```
Scenario: Resume sync from cursor

Step 1 - Initial sync:
  Request: {} (no cursor)
  Response:
  {
    "next_batch": "eyJ2IjoiMSIsInMiOnt9fQ",
    "spaces": {...}
  }

Step 2 - Resume sync:
  Request: {"since": "eyJ2IjoiMSIsInMiOnt9fQ"}
  Response:
  {
    "next_batch": "eyJ2IjoiMSIsInMiOnsiY3g6c3BhY2U6Li4uIjp7fX19",
    "spaces": {...}
  }

Expected: Incremental events since previous cursor
Result: PASS
```

### 5.2 Cursor Advancement

```
Scenario: Cursor advances with events

Initial cursor:
{
  "s": {
    "cx:space:A": {
      "p": ["evt:1"],
      "o": "000001-000001-aaaa"
    }
  }
}

After processing events:
{
  "s": {
    "cx:space:A": {
      "p": ["evt:1", "evt:2", "evt:3"],
      "o": "000001-000004-aaaa"
    }
  }
}

Expected: Cursor reflects new frontier
Result: PASS
```

## 6. Error Handling Tests

### 6.1 Invalid Base64URL

```
Input: "not-base64"

Expected error: invalid_cursor: invalid_encoding
```

### 6.2 Invalid JSON

```
Input: "eyJ2IjoiMSIsInQiOiJpbnZhbGlk"

Expected error: invalid_cursor: invalid_json
```

### 6.3 Malformed JSON

```
Input: "eyJ2IjoiMSIsIn0=" (with padding)

Expected error: invalid_cursor: invalid_encoding (padding not allowed)
```

## 7. Performance Tests

### 7.1 Encoding Performance

```
Target: Encode 10,000 cursors

Expected:
  - < 100ms total
  - < 10μs per cursor average
```

### 7.2 Decoding Performance

```
Target: Decode 10,000 cursors

Expected:
  - < 100ms total
  - < 10μs per cursor average
```

### 7.3 Validation Performance

```
Target: Validate 10,000 cursors

Expected:
  - < 150ms total
  - < 15μs per cursor average
  - Includes structure validation and expiration check
```

## 8. Security Tests

### 8.1 Tampering Detection

```
Scenario: Detect tampered cursor

Original: eyJ2IjoiMSIsInMiOnt9fQ
Tampered: eyJ2IjoiMiIsInMiOnt9fQ (version changed)

Expected:
  1. Decode succeeds
  2. Validation fails (unsupported version)
  3. Error returned

Result: PASS
```

### 8.2 Injection Prevention

```
Scenario: Prevent cursor injection attacks

Input cursor with extra fields:
{
  "v": "1",
  "t": "2026-04-26T00:00:00.000Z",
  "s": {},
  "x": 1714080000000,
  "admin": true  // Malicious extra field
}

Expected:
  1. Strict validation rejects extra fields
  2. Error returned or extra fields stripped

Result: PASS
```

## 9. Conformance Requirements

Implementations MUST:

1. Accept cursor version "1"
2. Generate cursor version "1"
3. Validate all required fields
4. Check cursor expiration (max 7 days)
5. Reject invalid HLC format
6. Reject invalid Space/Event ID format
7. Support at least 50 spaces per cursor
8. Use canonical JSON for encoding
9. Use Base64URL without padding

Implementations SHOULD:

1. Cache parsed cursors for performance
2. Log validation failures
3. Support compressed cursors
4. Provide cursor debugging tools
5. Monitor cursor expiration rates
