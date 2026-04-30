# Moderation

Moderation covers reporting, blocking, hiding, quarantine, policy lists, server-level service controls, and audit trails.

Moderation actions must be modeled as signed events and checked through policy/capability rules.

## E2EE Report Franking

E2EE Spaces SHOULD support message franking. When a service receives an encrypted event, it can sign a frank over canonical routing metadata, ciphertext digest, AAD digest, sender claim, receiving service DID, and receipt time without seeing plaintext.

Franks MUST NOT contain plaintext body, filenames, reply excerpts, mentions, private handles, or decrypted content hashes unless Space policy explicitly allows those fields.

An E2EE report MAY include encrypted plaintext evidence for moderators, the original encrypted envelope, the frank, and the reporter signature over the evidence package. Moderators verify the service signature, event/ciphertext/AAD digests, reporter visibility, accepted state, sender identity or pseudonym link, and the supplied plaintext evidence. A frank proves service receipt of the encrypted event; it does not by itself prove the semantic meaning of the plaintext.

