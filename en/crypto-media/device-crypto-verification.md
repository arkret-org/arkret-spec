# Device Crypto and Verification

This file is the English placeholder for the detailed Chinese draft in `../zh/device-crypto-verification.md`.

It defines device identity, cross-signing, to-device messages, verification flows, secret storage, key backup, and delegated Applet devices.

## MLS KeyPackage Claim API

MLS KeyPackages use a single-use claim lifecycle separate from one-time prekeys.

Recommended operations:

```http
POST /api/v1/keys/keypackages/upload
POST /api/v1/keys/keypackages/claim
POST /api/v1/keys/keypackages/consume
POST /api/v1/keys/keypackages/revoke
```

`claim` MUST atomically move a KeyPackage from `published` to `claimed` and bind requester, intended Space, required capabilities, claim nonce, expiry, target device, and Welcome routing context. The same `keypackage_ref` MUST NOT have multiple active claims. `consume` binds `claim_id`, `welcome_ref`, `space_id`, and device proof after Welcome succeeds. Expired, revoked, removed-device, or invalid-principal packages MUST NOT be returned.

Failure responses MUST avoid enumerating invisible users, unavailable devices, or policy-denied targets.

