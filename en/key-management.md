# Key Management

This document defines the lifecycle for Contrix keys:

- inception key
- principal signing key
- recovery key
- device key
- session key
- agent key
- MLS KeyPackage key
- backup / restore key

Principles:

- A principal is not a device.
- Long-term identity keys and daily operation keys are separated.
- Devices, sessions, agents, and applets require explicit revocable authority.
- Recovery keys do not automatically grant content access.
- Device revocation should trigger write rejection and MLS epoch update where relevant.

The Chinese draft contains the detailed device record, authorization event, session grant, backup envelope, recovery policy, and compromise-response rules.
