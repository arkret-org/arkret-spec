# Account Lifecycle

This file is the English placeholder for the detailed Chinese draft in `../zh/account-lifecycle.md`.

It defines service account states, soft logout, lock, suspension, deactivation, erasure, and session revocation.

## Service Account Login And Recovery

Service accounts MAY use username/password, passkeys, WebAuthn, OAuth/OIDC, enterprise SSO, or a centralized auth service. These mechanisms prove authentication to an account service; they do not directly prove DID principal ownership.

After login, the account/auth service MUST bind the session to a DID principal and device, for example by issuing a short-lived `cx.session.grant`, recording a device binding, or requiring DID proof. Resource servers then verify grant, device, capability, Space policy, and revocation state.

## Account-First Onboarding

Implementations MAY provide an account-first experience: the user registers or logs in through `@alice:example.org`, email, phone, enterprise SSO, OIDC, or an invitation link without needing to understand or manually enter a DID.

In this mode, the account/auth service MUST complete one of the following before allowing durable writes:

- Bind the service account to a user-controlled principal DID and verify DID proof, device binding, or an equivalent session grant.
- Create a supported managed DID for the service account and record the controller, recovery policy, trust domain, service-account binding, and audit evidence.

A session that is not yet bound to a DID MAY perform pre-registration actions such as signup, risk checks, invite preview, email verification, or device initialization. It MUST NOT submit a Space Event, repo commit, capability grant, MLS membership, service delegation, or federation transaction as the final actor.

If the user later switches to a self-controlled DID, pairwise DID, or organization-private DID, the service MAY migrate handles, service-account bindings, credentials, or future write identity according to policy. Historical Event `actor_id`, repo `author`, and grant `subject` values MUST NOT be rewritten; migrations should be represented by explicit claims, attestations, profile updates, or account binding records.

When a service account is already bound to a `principal_id`, DID proof MAY be used as strong evidence to recover access to that service account. The recovery service SHOULD verify a one-time challenge proving current control of that `principal_id` before allowing a password reset, passkey / WebAuthn rebinding, `soft_logged_out` recovery, or a short-lived session grant. The DID proof MUST verify the DID Document, key log / method history, current authentication key or authorized device key, challenge audience, origin, expiry, and replay status according to the DID method and local trust policy.

Password reset or email-code recovery only restores service-account access. Unless the DID recovery policy is also satisfied, the service MUST NOT rotate DID control keys, authorize a long-lived new device, read or rewrap E2EE secret storage, issue broad capabilities, or revoke existing user devices except as required by explicit recovery policy or risk response.

DID-proof-based service-account recovery likewise does not recover, reset, or change the DID itself. If the user has lost DID control keys, the user must follow the DID recovery policy; the organization account recovery flow only restores the organization service account and cannot replace DID recovery.

When service-account recovery conflicts with current DID control state, the service SHOULD enter `locked` or `soft_logged_out` and require an authorized device, recovery key, threshold recovery, enterprise multi-party approval, or DID proof before rebinding.

`soft_logged_out` responses use `401 soft_logged_out`; clients MUST NOT delete local E2EE device keys only because of this response.

