# Contrix v1 Conformance Index

## Overview

This directory contains the complete conformance specification documents, test vectors, and implementation guides for the Contrix v1 protocol.

## Directory Structure

```
conformance/
├── schemas/                    # JSON Schema definitions
│   ├── cursor-schema.json     # Cursor structure validation
│   ├── event-schema.json      # Event envelope validation
│   ├── grant-schema.json      # Capability Grant validation
│   └── encrypted-envelope-schema.json  # Encrypted envelope validation
│
├── specifications
│   ├── cursor-encoding.md     # Cursor encoding specification
│   ├── hlc-specification.md   # HLC format specification
│   ├── hlc-test-vectors.md    # HLC test vectors
│   └── cursor-test-vectors.md # Cursor test vectors
│
├── implementation guides
│   └── reference-implementation-guide.md  # Reference implementation guide
│
└── existing documents
    ├── encoding.md                    # Encoding specification
    ├── encoding-conformance-vectors.md # Encoding test vectors
    ├── snapshot-schema.md             # Snapshot schema
    ├── state-resolution-conformance-vectors.md  # State resolution tests
    ├── redaction-conformance-vectors.md        # Redaction test vectors
    ├── conformance-profiles.md        # Conformance profiles
    ├── conformance-suite.md           # Test suite
    └── schema-registry.md             # Schema registry
```

## Specification Documents

### Core Specifications

| Document | Description | Status |
|----------|-------------|--------|
| cursor-encoding.md | Cursor encoding format, validation rules, security considerations | Complete |
| hlc-specification.md | HLC text format, comparison algorithm, clock handling | Complete |
| encoding.md | Canonical JSON encoding specification | Existing |
| snapshot-schema.md | Snapshot structure and validation specification | Existing |

### Authorization Specifications

| Document | Description | Status |
|----------|-------------|--------|
| resource-selector-grammar.md | Resource selector EBNF grammar, matching algorithm | Complete |
| constraint-schema.md | Constraint type definitions, evaluation order | Complete |
| grant-constraint-schema.md | Grant constraint specification (pre-existing) | Existing |

### Encryption Specifications

| Document | Description | Status |
|----------|-------------|--------|
| encrypted-envelope-schema.md | Encrypted envelope structure, AAD processing, MLS integration | Complete |

## Test Vectors

### New Test Vectors

| Document | Coverage | Test Count |
|----------|----------|------------|
| hlc-test-vectors.md | HLC format validation, comparison, generation | 30+ |
| cursor-test-vectors.md | Cursor encoding/decoding, validation, expiration | 25+ |

### Existing Test Vectors

| Document | Coverage |
|----------|----------|
| encoding-conformance-vectors.md | Canonical JSON encoding |
| state-resolution-conformance-vectors.md | State resolution and conflict resolution |
| redaction-conformance-vectors.md | Message editing and redaction |
| capability-conformance-vectors.md | Authorization matching |

## JSON Schema Files

All schema files use JSON Schema Draft 7 format:

| Schema | Purpose | Validates |
|--------|---------|-----------|
| cursor-schema.json | Cursor validation | Structure, field types, format constraints |
| event-schema.json | Event envelope validation | Signatures, references, content format |
| grant-schema.json | Grant validation | Authorization, constraints, proofs |
| encrypted-envelope-schema.json | Encrypted envelope validation | Encryption structure, AAD, digest |

## Implementation Guides

| Document | Target Audience | Content |
|----------|----------------|---------|
| reference-implementation-guide.md | Implementers | Architecture recommendations, code organization, key implementations |

## Conformance Requirements

### Required

Implementations claiming Contrix v1 support MUST:

1. **Core Protocol**
   - Support all v1 event types
   - Implement correct HLC generation and comparison
   - Implement correct cursor encoding
   - Support all v1 constraint types

2. **Sync Protocol**
   - Support incremental sync
   - Support selective sync
   - Implement correct state convergence
   - Support backfill mechanism

3. **Authorization Model**
   - Implement capability-based authorization
   - Support all v1 constraint types
   - Implement correct evaluation order
   - Support delegation limits

4. **Encryption** (optional)
   - Support MLS (RFC 9420)
   - Correctly implement encrypted envelope
   - Support E2EE scenarios

5. **Federation** (optional)
   - Support inter-service authentication
   - Implement replay protection
   - Support snapshot-assisted bootstrap

### Test Requirements

Implementations MUST pass the following tests:

1. **Encoding Tests**
   - Canonical JSON encoding
   - HLC generation and comparison
   - Cursor encoding and decoding

2. **State Resolution Tests**
   - Conflict resolution
   - State convergence
   - Causal relationship handling

3. **Authorization Tests**
   - Capability matching
   - Constraint evaluation
   - Delegation tracking

4. **Encryption Tests** (if supported)
   - Envelope encryption and decryption
   - AAD verification
   - MLS integration

## Usage Guide

### For Implementers

1. Start with `reference-implementation-guide.md`
2. Consult relevant specification documents for detailed requirements
3. Use JSON Schema files to validate data structures
4. Run test vectors to verify implementation correctness

### For Protocol Researchers

1. Read core specification documents to understand protocol design
2. Review test vectors to understand edge cases
3. Refer to JSON Schema for data structure details

### For Test Tool Developers

1. Use JSON Schema files for automated validation
2. Implement test vectors for automated testing
3. Reference conformance profiles

## Version History

### v1.0 (2026-04-28)

Initial complete specification version, including:
- All core technical specifications
- Complete JSON Schema definitions
- Comprehensive test vectors
- Reference implementation guide

## Contributing

### Submitting New Specifications

1. Follow existing document format
2. Provide complete JSON Schema
3. Include test vectors
4. Update this index file

### Submitting Test Vectors

1. Use standard format (reference existing test vectors)
2. Include expected results
3. Cover edge cases
4. Provide validation tools (where applicable)

## Related Resources

### Protocol Documents

- [Object Model Core](../models/object-model-core.md)
- [Operations and Sync](../sync/operations-sync.md)
- [Authorization Model](../authz/capabilities.md)
- [Encryption and Audit](../crypto-media/encryption-and-audit.md)

### Tools and Libraries

- JSON Schema validation: `ajv` (JavaScript), `jsonschema` (Python)
- Canonical JSON: `canonical-json` (npm)
- DID resolution: `did-resolver`

## Contact

- Specification issues: Submit GitHub Issue
- Implementation issues: Discuss in Discussions
- Security issues: Reference security reporting process
