# Devices and Auth

Contrix uses private-key based identity with device authorization, OIDC/SSO gateway sessions, encrypted backups, and privacy-preserving push wakeups.

Device pairing adds a new device key through a signed authorization event. Device revocation invalidates future writes and should trigger MLS removal in encrypted Spaces.
