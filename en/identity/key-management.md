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

## Ownership Proof And Decryption Proof

DID control proof SHOULD use a signed fresh challenge rather than proof that the user can decrypt historical ciphertext.

Valid ownership or recovery proof includes:

- a current control key, authorized device key, or recovery key signing a fresh server challenge
- a new device key authorized by an existing device or by the recovery policy
- a recovery service explicitly declared in the DID document, organization policy, or recovery policy signing a verifiable recovery event

Being able to decrypt data encrypted to a public key MAY be one recovery factor, but it is not sufficient account ownership by itself. If used, the service should encrypt a short-lived random challenge to the current recovery public key and require the client to sign or prove the full transcript. The proof MUST bind challenge, audience/origin, service DID, principal DID, key id, expiry, and replay nonce.

Implementations MUST NOT treat the following as standalone recovery proof:

- decrypting an old message, old blob, old MLS epoch, or old backup
- presenting historical plaintext
- passing service-account password or email-code recovery without DID / recovery proof
- holding a revoked, expired, or no-longer-authorized device key

The main risks are key-purpose confusion, stale-key resurrection, offline attack against weak backup passphrases, decryption-oracle abuse, phishing / relay attacks, and privacy leakage from proving ownership with historical content. Decryption capability can be a recovery factor; changing DID control state must still become a signed `recover`, `rotate`, `cx.device.authorized`, or equivalent key-log event.

