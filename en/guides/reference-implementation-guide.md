# Contrix v1 Reference Implementation Guide

## 1. Overview

This guide provides implementation guidance for building Contrix v1 compatible clients and servers. It covers architecture decisions, code organization, and practical considerations.

## 2. Implementation Phases

### 2.1 Phase 1: Core Protocol (Required)

**Components to implement:**

1. **Event Processing**
   - Event envelope parsing and validation
   - Signature verification
   - HLC generation and comparison
   - Causal dependency tracking

2. **State Resolution**
   - Reducer implementation
   - Conflict resolution
   - State convergence
   - Tombstone handling

3. **Basic Authorization**
   - Capability matching
   - Grant validation
   - Constraint evaluation

**Deliverable:** Basic event processing and state management

### 2.2 Phase 2: Synchronization (Required)

**Components to implement:**

1. **Client Sync**
   - Cursor management
   - Incremental sync
   - Backfill handling
   - Resume capability

2. **Repo Management**
   - Commit creation
   - Operation signing
   - Local storage
   - Causal ordering

**Deliverable:** Full client sync with resume capability

### 2.3 Phase 3: Federation (Optional)

**Components to implement:**

1. **Federation Protocol**
   - Service-to-service authentication
   - Push/pull operations
   - Cross-domain sync
   - Snapshot assistance

2. **Directory Integration**
   - Space discovery
   - Actor resolution
   - Service discovery

**Deliverable:** Cross-domain collaboration support

### 2.4 Phase 4: Encryption (Optional for MVP)

**Components to implement:**

1. **MLS Integration**
   - KeyPackage management
   - Group creation
   - Message encryption/decryption
   - Epoch handling

2. **E2EE Workflows**
   - Key distribution
   - Member management
   - Audit mode (if required)

**Deliverable:** End-to-end encrypted messaging

## 3. Architecture Recommendations

### 3.1 Client Architecture

```
Contrix Client
├── Core Layer
│   ├── Event Processor (validation, signing)
│   ├── Reducer (state resolution)
│   ├── HLC Generator (time ordering)
│   └── Authz Engine (capability checks)
├── Storage Layer
│   ├── Event Store (append-only log)
│   ├── State Cache (current state)
│   ├── Cursor Store (sync positions)
│   └── Key Store (encryption keys)
├── Sync Layer
│   ├── Sync Client (incremental sync)
│   ├── Backfill Manager (history recovery)
│   └── Subscription Manager (real-time updates)
├── UI Layer
│   ├── State Projections (views)
│   ├── Event Handlers (user actions)
│   └── Notification Manager
└── Crypto Layer (optional)
    ├── MLS Client (group encryption)
    ├── Key Manager (key distribution)
    └── Audit Logger (compliance)
```

### 3.2 Server Architecture

```
Contrix Server
├── API Layer
│   ├── Sync Endpoint (client sync)
│   ├── Federation Endpoint (server-to-server)
│   ├── Auth Endpoint (authentication)
│   └── Admin Endpoint (management)
├── Core Layer
│   ├── Event Validator (signature checks)
│   ├── Authz Engine (capability evaluation)
│   ├── Reducer (state computation)
│   └── Policy Engine (rule enforcement)
├── Storage Layer
│   ├── Event Store (persistent storage)
│   ├── State Store (materialized state)
│   ├── Index Store (searchable data)
│   └── Cursor Store (sync positions)
├── Federation Layer
│   ├── Federation Client (outgoing)
│   ├── Federation Server (incoming)
│   └── Federation Auth (service auth)
└── Support Services
    ├── Push Service (notifications)
    ├── Blob Service (file storage)
    └── Audit Service (compliance logging)
```

## 4. Code Organization

### 4.1 Recommended Module Structure

```
src/
├── core/
│   ├── types.ts          # Type definitions
│   ├── event.ts          # Event processing
│   ├── reducer.ts        # State resolution
│   ├── hlc.ts            # HLC implementation
│   └── authz.ts          # Authorization engine
├── storage/
│   ├── event-store.ts    # Event storage
│   ├── state-store.ts    # State cache
│   └── cursor-store.ts   # Cursor management
├── sync/
│   ├── sync-client.ts    # Sync protocol
│   ├── backfill.ts       # Backfill logic
│   └── subscription.ts   # Real-time updates
├── crypto/
│   ├── mls-client.ts     # MLS integration
│   ├── key-manager.ts    # Key management
│   └── envelope.ts       # Encryption envelope
├── api/
│   ├── http-client.ts    # HTTP client
│   ├── http-server.ts    # HTTP server
│   └── middleware.ts     # API middleware
└── utils/
    ├── canonjson.ts      # Canonical JSON
    ├── digest.ts         # Hash computation
    └── encoding.ts       # Base64URL encoding
```

### 4.2 Type System

```typescript
// Core types
interface Event {
  event_id: string;
  kind: string;
  space_id: string;
  actor_id: string;
  hlc: string;
  prev_refs: string[];
  auth_refs: string[];
  content: unknown;
  proofs: Proof[];
}

interface State {
  entities: Map<string, Entity>;
  relations: Map<string, Relation>;
  events: Map<string, Event>;
  frontier: string[];
}

interface Grant {
  id: string;
  issuer: string;
  subject: string | Condition;
  actions: string[];
  resources: ResourceSelector[];
  constraints?: Constraint[];
  proofs: Proof[];
}

// HLC type
type HLC = string;  // Format: <physical_hex_12>-<logical_hex_8>-<node_hex_8>

// Cursor type
interface Cursor {
  v: "1";
  t: string;
  s: Record<string, SpacePosition>;
  d?: Record<string, string>;
  x: number;
}
```

## 5. Key Implementation Details

### 5.1 Event Validation

```typescript
async function validateEvent(event: Event): Promise<ValidationResult> {
  // 1. Validate signature
  const proofValid = await verifyProofs(event.proofs, event);
  if (!proofValid) {
    return { valid: false, error: "invalid_signature" };
  }

  // 2. Validate HLC format
  if (!isValidHLC(event.hlc)) {
    return { valid: false, error: "invalid_hlc" };
  }

  // 3. Validate space_id format
  if (!isValidSpaceId(event.space_id)) {
    return { valid: false, error: "invalid_space_id" };
  }

  // 4. Validate actor DID
  const actorDoc = await resolveDID(event.actor_id);
  if (!actorDoc) {
    return { valid: false, error: "unknown_actor" };
  }

  // 5. Check causal dependencies
  for (const prevRef of event.prev_refs) {
    if (!(await hasEvent(prevRef))) {
      return { valid: false, error: "missing_causal_dependency" };
    }
  }

  // 6. Validate authorization
  const authz = await checkAuthorization(event);
  if (!authz.allowed) {
    return { valid: false, error: "unauthorized", reason: authz.reason };
  }

  return { valid: true };
}
```

### 5.2 HLC Implementation

```typescript
class HLCGenerator {
  private physical: number;
  private logical: number;
  private nodeId: string;

  constructor(nodeId: string, initialTime?: number) {
    this.nodeId = nodeId;
    this.physical = initialTime || Date.now();
    this.logical = 0;
  }

  generate(): HLC {
    const now = Date.now();

    if (now > this.physical) {
      this.physical = now;
      this.logical = 0;
    } else if (now === this.physical) {
      this.logical++;
    } else {
      // Clock went backwards, advance logical
      this.logical++;
    }

    return this.format();
  }

  private format(): HLC {
    const physicalHex = this.physical.toString(16).padStart(12, '0');
    const logicalHex = this.logical.toString(16).padStart(4, '0');
    const nodeHash = sha256hex(this.nodeId).substring(0, 8);
    return `${physicalHex}-${logicalHex}-${nodeHash}`;
  }

  compare(other: HLC): number {
    const [p1, l1, n1] = this.parse(other);
    const [p2, l2, n2] = [this.physical, this.logical, this.nodeId];

    if (p1 !== p2) return p1 - p2;
    if (l1 !== l2) return l1 - l2;
    return n1.localeCompare(n2);
  }

  private parse(hlc: HLC): [number, number, string] {
    const [physical, logical, node] = hlc.split('-');
    return [
      parseInt(physical, 16),
      parseInt(logical, 16),
      node
    ];
  }
}
```

### 5.3 Cursor Management

```typescript
class CursorManager {
  async encodeCursor(positions: SyncPositions): Promise<string> {
    const cursor: Cursor = {
      v: "1",
      t: new Date().toISOString(),
      s: {},
      x: Date.now() + (7 * 24 * 60 * 60 * 1000)  // 7 days
    };

    for (const [spaceId, pos] of positions.spaces) {
      cursor.s[spaceId] = {
        p: pos.frontier,
        o: pos.timelineOrder,
        h: pos.stateHash
      };
    }

    if (positions.devices) {
      cursor.d = positions.devices;
    }

    const json = canonicalJSON(cursor);
    return base64urlEncode(json);
  }

  async decodeCursor(encoded: string): Promise<Cursor> {
    const json = base64urlDecode(encoded);
    const cursor = JSON.parse(json);

    // Validate
    if (cursor.v !== "1") {
      throw new Error("Unsupported cursor version");
    }

    if (cursor.x < Date.now()) {
      throw new Error("Cursor expired");
    }

    return cursor;
  }
}
```

### 5.4 Authorization Engine

```typescript
class AuthzEngine {
  async checkCapability(
    actor: string,
    action: string,
    resource: Resource
  ): Promise<AuthzResult> {
    // 1. Fetch relevant grants
    const grants = await this.fetchGrants(actor, resource.spaceId);

    // 2. Filter by resource match
    const matchingGrants = grants.filter(g =>
      this.matchesResource(g.resources, resource)
    );

    // 3. Check action
    const withAction = matchingGrants.filter(g =>
      g.actions.includes(action) || g.actions.includes('*')
    );

    // 4. Evaluate constraints
    for (const grant of withAction) {
      const result = await this.evaluateConstraints(grant, resource);
      if (result.allowed) {
        return { allowed: true, grantId: grant.id };
      }
    }

    return { allowed: false, reason: "no_matching_grant" };
  }

  private async evaluateConstraints(
    grant: Grant,
    resource: Resource
  ): Promise<ConstraintResult> {
    if (!grant.constraints) {
      return { allowed: true };
    }

    // Check deny constraints first
    const denies = grant.constraints.filter(c => c.effect === "deny");
    for (const constraint of denies) {
      if (await this.matchesConstraint(constraint, resource)) {
        return { allowed: false, constraint: constraint };
      }
    }

    // Check allow constraints
    const allows = grant.constraints.filter(c => c.effect === "allow");
    for (const constraint of allows) {
      if (!(await this.matchesConstraint(constraint, resource))) {
        return { allowed: false, constraint };
      }
    }

    return { allowed: true };
  }
}
```

## 6. Testing Strategy

### 6.1 Unit Tests

Test coverage targets:
- Event processing: 90%+
- State resolution: 90%+
- Authorization: 85%+
- HLC operations: 95%+

### 6.2 Integration Tests

Test scenarios:
- Sync flow with cursors
- Multi-space synchronization
- Conflict resolution
- Authorization paths

### 6.3 Conformance Tests

Use provided test vectors:
- HLC test vectors
- Cursor test vectors
- Encoding conformance vectors
- State resolution vectors

## 7. Performance Guidelines

### 7.1 Targets

- Event processing: < 1ms per event
- State resolution: < 10ms for 1000 events
- Authorization check: < 1ms for cached grants
- Cursor encoding/decoding: < 100μs

### 7.2 Optimizations

1. **Cache grant evaluations** by causal frontier
2. **Pre-compute state hashes** for common operations
3. **Use efficient data structures** for state storage
4. **Batch event processing** when possible

## 8. Security Considerations

### 8.1 Signature Verification

- Always verify event signatures
- Check proof validity (not expired, correct key)
- Verify DID control chain

### 8.2 Authorization

- Never trust client-side authorization claims
- Always re-evaluate on server
- Log authorization failures

### 8.3 Input Validation

- Validate all input formats
- Reject malformed data early
- Use strict parsing (fail closed)

## 9. Error Handling

### 9.1 Error Types

```typescript
enum ErrorCode {
  // Event errors
  INVALID_EVENT_FORMAT = "invalid_event_format",
  INVALID_SIGNATURE = "invalid_signature",
  INVALID_HLC = "invalid_hlc",

  // Authorization errors
  UNAUTHORIZED = "unauthorized",
  EXPIRED_GRANT = "expired_grant",
  REVOKED_GRANT = "revoked_grant",

  // Sync errors
  INVALID_CURSOR = "invalid_cursor",
  CURSOR_EXPIRED = "cursor_expired",
  MISSING_CAUSAL_DEPENDENCY = "missing_causal_dependency",

  // Network errors
  NETWORK_ERROR = "network_error",
  TIMEOUT = "timeout",
  RATE_LIMITED = "rate_limited"
}
```

### 9.2 Error Response Format

```typescript
interface ErrorResponse {
  error: string;
  error_code: string;
  error_description?: string;
  retry_after_ms?: number;
}
```

## 10. Deployment Considerations

### 10.1 Client Deployment

- Support offline mode
- Handle network failures gracefully
- Provide sync progress indicators
- Implement exponential backoff for retries

### 10.2 Server Deployment

- Use horizontal scaling for sync endpoints
- Implement rate limiting
- Monitor for abuse patterns
- Provide health check endpoints

## 11. Monitoring and Observability

### 11.1 Metrics to Track

- Event processing rate
- Sync success/failure rates
- Authorization cache hit rate
- Cursor expiration rate
- API latency percentiles

### 11.2 Logging

- Log all authorization failures
- Log sync errors with context
- Log suspicious patterns
- Use structured logging (JSON)

## 12. Resources

### 12.1 Reference Implementations

Look for reference implementations in:
- Official Contrix SDK repositories
- Community implementations
- Test suite implementations

### 12.2 Tools and Libraries

Recommended libraries:
- DID resolution: `did-resolver`
- JSON canonicalization: `canonical-json`
- MLS: `openmls` (when available)
- JSON Schema validation: `ajv` (JavaScript)

## 13. Getting Help

### 13.1 Community Resources

- Documentation: `https://contrix.org/spec`
- GitHub Discussions: `contrix/spec/discussions`
- Discord/Slack: (check README for links)

### 13.2 Contributing

See `CONTRIBUTING.md` for:
- Code style guidelines
- Pull request process
- Testing requirements
- Documentation standards
