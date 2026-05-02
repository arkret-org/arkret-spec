# Hybrid Logical Clock (HLC) Specification

## 1. Overview

Contrix v1 uses Hybrid Logical Clocks (HLC) for distributed event ordering. This specification defines the exact format, encoding, and comparison rules for HLC values in Contrix.

## 2. Motivation

Pure physical clocks suffer from clock skew, while pure logical clocks don't correlate with wall time. HLC combines both:
- Monotonically increasing across the distributed system
- Closely tracks physical time
- Allows ordering without global coordination

## 3. HLC Format

### 3.1 Structure

HLC is a tuple of (physical_time, logical_counter, node_id):

- **physical_time**: 48-bit Unix timestamp in milliseconds (~8,925 years before overflow)
- **logical_counter**: 16-bit monotonic counter (up to 65,535 events per ms)
- **node_id**: 32-bit hash of node identifier (for tiebreaking)

### 3.2 Textual Encoding

HLC values are encoded as strings with the following format:

```
<physical_hex>-<logical_hex>-<node_hex>
```

Where:
- `physical_hex`: 12-character lowercase hexadecimal (zero-padded to 12 chars)
- `logical_hex`: 4-character lowercase hexadecimal (zero-padded to 4 chars)
- `node_hex`: 8-character lowercase hexadecimal (first 32 bits of SHA256(node_id))

### 3.3 Examples

Valid HLC values:
- `01970e589d21-0004-a13f9c2e`
- `000000000001-ffff-12345678`
- `ffffffffffff-0000-abcdef12`

Invalid HLC values:
- `1970e589d21-1-a13f9c2e` (not zero-padded)
- `01970e589d21-0004` (missing node part)
- `xyz-0004-a13f9c2e` (invalid hex)

## 4. HLC Operations

### 4.1 Initialization

When a node starts, initialize its HLC:
```
hlc = max(current_physical_ms, 0)
```

### 4.2 Send Event

When sending an event:
```
hlc = max(current_hlc, current_physical_ms)
if hlc.physical == current_physical_ms:
    hlc.logical += 1
else:
    hlc.physical = current_physical_ms
    hlc.logical = 0
```

### 4.3 Receive Event

When receiving an event with HLC `hlc_remote`:
```
hlc = max(current_hlc, current_physical_ms, hlc_remote)
if hlc.physical == current_physical_ms or hlc.physical == hlc_remote.physical:
    hlc.logical += 1
else:
    hlc.logical = 0
```

### 4.4 Node ID Calculation

```
node_hex = SHA256(node_identifier)[0:8]
```

Where `node_identifier` is the principal DID or service DID.

## 5. Comparison Rules

HLC comparison is lexicographic on the encoded string:

1. First compare physical_hex (numerically)
2. If equal, compare logical_hex (numerically)
3. If equal, compare node_hex (lexicographically)

This works because the fixed-width hex encoding ensures correct ordering.

### 5.1 Pseudocode

```
function compare_hlc(hlc1, hlc2):
    p1 = parse_hex(hlc1.physical_hex)
    p2 = parse_hex(hlc2.physical_hex)
    if p1 != p2:
        return p1 - p2

    l1 = parse_hex(hlc1.logical_hex)
    l2 = parse_hex(hlc2.logical_hex)
    if l1 != l2:
        return l1 - l2

    return strcmp(hlc1.node_hex, hlc2.node_hex)
```

## 6. Use in Contrix

### 6.1 Event Ordering

Events are ordered by:
```
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

HLC provides the secondary ordering after causal dependencies.

### 6.2 Conflict Resolution

When two concurrent operations conflict (no causal relationship):
1. Compare by HLC (higher wins)
2. If HLC equal (very rare), compare by actor_id (lexicographic)
3. If still equal, compare by event_id (lexicographic)

### 6.3 Cursor Positions

Sync cursors include HLC to track timeline position:
```json
{
  "s": {
    "cx:space:...": {
      "o": "01970e589d21-0004-a13f9c2e"
    }
  }
}
```

## 7. Validation Rules

Implementations MUST:
- Validate HLC format with regex: `^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$`
- Reject or quarantine HLC values whose physical time exceeds the hard future-skew ceiling; the v1 default hard ceiling is 5 minutes
- Use a smaller profile-declared or locally configured expected drift window for high-risk state events; 5 minutes is not an ordering trust window
- Maintain monotonicity locally
- Use consistent node_id calculation

This exact textual format is normative for Event envelopes, cursors, snapshot frontiers, sync tokens that expose HLC positions, and conformance fixtures. Profiles MUST NOT substitute an 8-character logical counter or a variable-width encoding without declaring a new HLC version and schema profile.

## 8. Security Considerations

1. **Clock Skew Attacks**: Validate physical time against the hard ceiling and apply tighter expected / observed drift checks for high-risk state events
2. **Node ID Collisions**: Use full SHA256 space makes collisions negligible
3. **Replay Detection**: Combine HLC with other causal tracking

## 9. Implementation Guidelines

### 9.1 Clock Skew Handling

Nodes should track maximum drift seen:
- If local clock is behind remote, advance to remote
- If local clock is ahead, cap advance rate
- Log when skew exceeds 1 second
- If skew exceeds profile expected drift but remains under the hard ceiling, ordinary events may soft-fail / backfill; high-risk capability, membership, policy, MLS epoch, service binding, and Space upgrade events should enter quarantine or review

### 9.2 Overflow Handling

Physical time overflow won't occur for millennia, but implementations should:
- Reject HLC values with `physical_hex > ffffffffffff`
- Gracefully handle transition to version 2 if needed

### 9.3 Testing

Test suites should include:
- Monotonicity under high concurrency
- Hard future-skew boundaries plus expected-drift and observed-drift soft-fail / quarantine behavior
- Lexicographic ordering matches numeric comparison
- Node id calculation consistency

## 10. Conformance

Implementations claiming Contrix v1 support MUST:
- Accept HLC values in the specified format
- Generate HLC values in the specified format
- Implement correct comparison and ordering
- Maintain local monotonicity
- Validate incoming HLC values

## 11. Migration from Timestamps

Implementations transitioning from pure timestamps should:
- Map existing timestamps to HLC: `physical = timestamp_ms, logical = 0`
- Use consistent node_id for all migrated events
- Document migration cutoff in snapshot metadata
