# HLC Conformance Test Vectors

## 1. HLC Format Validation

### 1.1 Valid HLC Values

| HLC Value | Physical Time | Logical Counter | Node ID | Description |
|-----------|---------------|-----------------|---------|-------------|
| `000000000001-00000001-a13f9c2e` | 1 ms | 1 | `a13f9c2e` | Minimum valid HLC |
| `01970e589d21-00000004-a13f9c2e` | 2026-04-26T00:00:00.000Z | 4 | `a13f9c2e` | Typical HLC |
| `ffffffffffff-ffffffff-12345678` | ~285616 years | 4294967295 | `12345678` | Maximum values |

### 1.2 Invalid HLC Values

| HLC Value | Reason | Expected Error |
|-----------|--------|----------------|
| `1970e589d21-00000001-a13f9c2e` | Physical not zero-padded | `invalid_hlc_format` |
| `01970e589d21-1-a13f9c2e` | Logical not zero-padded | `invalid_hlc_format` |
| `01970e589d21-00000001-a13f` | Node ID too short | `invalid_hlc_format` |
| `xyz-00000001-a13f9c2e` | Invalid hex in physical | `invalid_hlc_format` |
| `01970e589d21-0000000g-a13f9c2e` | Invalid hex in logical | `invalid_hlc_format` |
| `01970e589d21-00000001-` | Missing node part | `invalid_hlc_format` |

## 2. HLC Comparison Tests

### 2.1 Lexicographic Ordering

```
Test: HLC string comparison should match numeric comparison

Input:
  hlc1 = "01970e589d21-00000001-a13f9c2e"
  hlc2 = "01970e589d21-00000002-a13f9c2e"

Expected: hlc1 < hlc2 (lexicographically and numerically)
Result: PASS
```

```
Test: Physical time takes precedence

Input:
  hlc1 = "01970e589d21-00000001-a13f9c2e"
  hlc2 = "01970e589d22-00000000-a13f9c2e"

Expected: hlc1 < hlc2 (physical time differs)
Result: PASS
```

```
Test: Logical counter breaks ties

Input:
  hlc1 = "01970e589d21-00000001-a13f9c2e"
  hlc2 = "01970e589d21-00000002-a13f9c2e"

Expected: hlc1 < hlc2 (logical counter wins)
Result: PASS
```

```
Test: Node ID breaks ties

Input:
  hlc1 = "01970e589d21-00000001-a13f9c2e"
  hlc2 = "01970e589d21-00000001-b13f9c2e"

Expected: hlc1 < hlc2 (node ID wins)
Result: PASS
```

### 2.2 Clock Skew Handling

```
Test: Handle clock rollback

Scenario:
  Current HLC: "01970e589d21-00000001-a13f9c2e" (T1)
  Physical time: T0 < T1
  Incoming event with HLC at T0

Expected: Advance local HLC to max(current, incoming) + 1
Result: PASS - Local HLC becomes "01970e589d21-00000002-a13f9c2e"
```

## 3. HLC Generation Tests

### 3.1 Sequential Events

```
Scenario: Generate 5 sequential events

Initial state:
  current_hlc = "01970e589d21-00000000-a13f9c2e"
  physical_time = "01970e589d21"

Event 1: hlc = "01970e589d21-00000001-a13f9c2e"
Event 2: hlc = "01970e589d21-00000002-a13f9c2e"
Event 3: hlc = "01970e589d21-00000003-a13f9c2e"
Event 4: hlc = "01970e589d21-00000004-a13f9c2e"
Event 5: hlc = "01970e589d21-00000005-a13f9c2e"
```

### 3.2 Physical Time Advancement

```
Scenario: Physical time advances

Event 1: time = "01970e589d21", hlc = "01970e589d21-00000001-a13f9c2e"
Event 2: time = "01970e589d22", hlc = "01970e589d22-00000000-a13f9c2e"
Event 3: time = "01970e589d22", hlc = "01970e589d22-00000001-a13f9c2e"
```

## 4. Node ID Calculation

### 4.1 SHA256 Truncation

```
Test: Node ID from DID

Input:
  node_identifier = "did:web:alice.example.com"
  hash_algorithm = "SHA256"
  truncation = "first 32 bits (8 hex chars)"

Process:
  1. Compute SHA256("did:web:alice.example.com")
  2. Take first 8 hex characters

Expected: Valid 8-character hex string
Example: "a13f9c2e" (actual value depends on SHA256 output)
```

## 5. Edge Cases

### 5.1 Logical Counter Overflow

```
Scenario: Logical counter reaches maximum

Input:
  current_hlc = "01970e589d21-ffffffff-a13f9c2e"
  next_event_time = same physical time

Expected: Advance physical time, reset logical counter
Result: HLC becomes "01970e589d22-00000000-a13f9c2e"
Note: Physical time should advance by at least 1 ms
```

### 5.2 Maximum Physical Time

```
Scenario: Physical time near maximum

Input:
  hlc = "fffffffffffe-00000001-a13f9c2e"
  next_physical = "ffffffffffff"

Expected: Continue working until overflow
Note: In practice, physical time overflow won't occur for millennia
```

## 6. Integration Tests

### 6.1 Event Ordering with HLC

```
Scenario: Order events by HLC

Events:
  A: "01970e589d21-00000001-alice"
  B: "01970e589d21-00000002-bob"
  C: "01970e589d21-00000001-bob"
  D: "01970e589d22-00000000-alice"

Expected order: C < B < A < D
Explanation:
  - C and A: Same physical time, C has lower logical
  - B > C: B has higher logical
  - A and B: Same physical time, A has lower logical
  - D > A: D has higher physical time
```

### 6.2 Concurrent Event Resolution

```
Scenario: Resolve concurrent updates

Context: Two actors update same entity concurrently

Event from Alice:
  hlc = "01970e589d21-00000001-a13f9c2e"
  content: {"status": "done"}

Event from Bob:
  hlc = "01970e589d21-00000002-b13f9c2e"
  content: {"status": "in_progress"}

Expected: Bob's update wins (higher logical counter)
Result: Entity status = "in_progress"
```

## 7. Error Recovery

### 7.1 Invalid HLC Recovery

```
Scenario: Receive event with invalid HLC

Input:
  event_hlc = "invalid-hlc-value"

Expected behavior:
  1. Reject event with `invalid_hlc_format` error
  2. Do not process event
  3. Log error for debugging
```

### 7.2 Clock Skew Beyond Threshold

```
Scenario: Remote clock skewed by more than 5 minutes

Input:
  local_time = "01970e589d21" (2026-04-26T00:00:00Z)
  remote_hlc = "0197237f2400-00000001-a13f9c2e" (2026-05-01T00:00:00Z)

Expected behavior:
  1. Reject event with `clock_skew_exceeded` error
  2. Log warning for monitoring
  3. Optionally notify operator
```

## 8. Performance Tests

### 8.1 HLC Generation Rate

```
Scenario: Generate HLCs at maximum rate

Target: 10,000 events per second

Expected:
  - No logical counter overflow within 1 ms window
  - Physical time advances when logical counter would overflow
  - All generated HLCs are valid and unique
```

### 8.2 HLC Parsing Performance

```
Scenario: Parse 100,000 HLC values

Expected:
  - Parse time < 100ms total
  - < 1μs per HLC average
  - No memory leaks
```

## 9. Security Tests

### 9.1 HLC Forgery Detection

```
Scenario: Detect forged HLC with impossible future time

Input:
  current_time = "01970e589d21"
  event_hlc = "999999999999-00000001-a13f9c2e"

Expected:
  1. Detect physical time is > 5 minutes in future
  2. Reject with `hlc_future_timestamp` error
  3. Log potential time manipulation attempt
```

### 9.2 HLC Replay Prevention

```
Scenario: Detect replayed old HLC

Input:
  current_hlc = "01970e589d21-00000100-a13f9c2e"
  replayed_hlc = "01970e589d20-00000001-a13f9c2e"

Expected:
  1. Accept if causal refs are valid
  2. Reject if event_id was already processed
  3. Use event_id deduplication, not HLC comparison
```

## 10. Conformance Requirements

Implementations MUST:

1. Accept all valid HLC values in the specified format
2. Generate HLC values in the specified format
3. Implement correct comparison ordering
4. Maintain local monotonicity
5. Validate incoming HLC format
6. Handle clock skew up to ±5 minutes
7. Reject HLC values with timestamps > 5 minutes in future

Implementations SHOULD:

1. Log clock skew warnings
2. Track maximum drift observed
3. Support multiple nodes with different node IDs
4. Optimize HLC generation for high throughput
