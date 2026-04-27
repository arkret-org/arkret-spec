# Encryption and Auditability

Contrix uses MLS (RFC 9420) for group E2EE.

Auditable E2EE is explicit and transparent: compliance actors must be visible group members, and access must produce signed audit events before plaintext is released.

Bridge boundaries and Applets must not silently downgrade encrypted content into non-E2EE networks.

