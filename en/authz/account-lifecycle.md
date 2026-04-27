# Account Lifecycle

This file is the English placeholder for the detailed Chinese draft in `../zh/account-lifecycle.md`.

It defines service account states, soft logout, lock, suspension, deactivation, erasure, and session revocation.

## Service Account Login And Recovery

Service accounts MAY use username/password, passkeys, WebAuthn, OAuth/OIDC, enterprise SSO, or a centralized auth service. These mechanisms prove authentication to an account service; they do not directly prove DID principal ownership.

After login, the account/auth service MUST bind the session to a DID principal and device, for example by issuing a short-lived `cx.session.grant`, recording a device binding, or requiring DID proof. Resource servers then verify grant, device, capability, Space policy, and revocation state.

Password reset or email-code recovery only restores service-account access. Unless the DID recovery policy is also satisfied, the service MUST NOT rotate DID control keys, authorize a long-lived new device, read or rewrap E2EE secret storage, issue broad capabilities, or revoke existing user devices except as required by explicit recovery policy or risk response.

When service-account recovery conflicts with current DID control state, the service SHOULD enter `locked` or `soft_logged_out` and require an authorized device, recovery key, threshold recovery, enterprise multi-party approval, or DID proof before rebinding.

`soft_logged_out` responses use `401 soft_logged_out`; clients MUST NOT delete local E2EE device keys only because of this response.

