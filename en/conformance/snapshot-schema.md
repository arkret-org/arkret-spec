# Snapshot and Encrypted Envelope Schema

Snapshots accelerate bootstrap but are not the truth source. Signed Operations and commits remain authoritative.

Snapshot manifest includes:

- `snapshot_id`
- `space_id`
- `reducer_profile`
- `schema_profile`
- `frontier`
- `state_hash`
- `chunks`
- `proof`

Clients MUST verify manifest signature and state hash before using a snapshot.

Encrypted envelopes include cleartext routing metadata plus ciphertext and ciphertext digest.

