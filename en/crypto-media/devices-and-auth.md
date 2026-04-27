# Devices and Auth

Contrix uses private-key based identity with device authorization, OIDC/SSO gateway sessions, encrypted backups, and privacy-preserving push wakeups.

Device pairing adds a new device key through a signed authorization event. Device revocation invalidates future writes and should trigger MLS removal in encrypted Spaces.

## What Auth Services Verify

An Auth Service / Auth Gateway is not the protocol identity root. It verifies that a login session can be bound to a DID principal / device; it does not define ownership from username, password, email, or OIDC subject alone.

Implementations MAY support username/password, passkey/WebAuthn, OIDC/SSO, authorized-device pairing, recovery keys, threshold recovery, or trusted recovery services. After authentication, the service MUST produce a verifiable binding such as:

- `cx.session.grant` delegating a short-lived `session_public_key` to a DID principal / device
- `cx.device.authorized` authorizing a new device key
- a `recover` / key-log event satisfying the principal recovery policy

Resource servers verify session grants, device authorization, DID proof, capability, and Space policy. They MUST NOT treat a successful password check, SSO session, or service account id as `actor_id`, event sender, or capability subject.

A service-account password reset only changes service login credentials. It MUST NOT grant DID control, issue a long-lived device grant, or expose E2EE key backup unless a valid DID control proof or recovery-policy event is also present.

For enterprise SSO, an Auth Gateway is usually a session-grant issuer or device authorization service declared by the organization DID. It MAY hold high-privilege signing material only for enterprise-managed accounts; for personal DIDs it SHOULD issue short-lived session grants and SHOULD NOT custody the user's principal signing key or recovery key.

