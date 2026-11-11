"""Reference Signal endpoint domains; native authorization is supplied verified input."""

from functools import lru_cache

from .artifact_lint.core import ARTIFACTS, schema_validator
from .content_history import jcs, unb64

FIELDS = ["actor_id", "endpoint", "authorization_event_ref", "signature_key_base64url"]
CONTEXT_SCHEMA = "schemas/content-encryption.schema.json#/$defs/endpoint"
CONTEXT_ENCODING = "UTF8(RFC8785_JCS(SignalSenderDomain)); direct closed endpoint object bytes, without prehashing or JSON string wrapping"
MAX_COUNTER = (1 << 64) - 1


@lru_cache(maxsize=1)
def endpoint_validator():
    return schema_validator(ARTIFACTS / "schemas/content-encryption.schema.json", "#/$defs/endpoint")


def sender_domain(endpoint):
    endpoint_validator().validate(endpoint)
    if endpoint["actor_id"]["kind"] != "account":
        raise ValueError("Signal requires a verified Account Device or Agent endpoint")
    if len(unb64(endpoint["signature_key_base64url"])) != 32:
        raise ValueError("Signal leaf key must be canonical raw Ed25519")
    return jcs(endpoint)


def verified_sender_domain(candidate, accepted_endpoint, *, active=True, matching_leaves=1):
    # This compares against independently verified facts; it cannot establish
    # native authority, current classification or a real accepted MLS roster.
    if not active or matching_leaves != 1:
        raise ValueError("current authority and exactly one active leaf are required")
    actual, accepted = sender_domain(candidate), sender_domain(accepted_endpoint)
    if actual != accepted:
        raise ValueError("Signal sender differs from the verified endpoint instance")
    return actual


def nonce_scope(group_id, epoch, endpoint):
    if not group_id or type(epoch) is not int or not 0 <= epoch <= MAX_COUNTER:
        raise ValueError("invalid Signal group or epoch")
    return group_id, epoch, sender_domain(endpoint)


def reserve_nonce(next_unreserved, count=1):
    # Models a committed atomic reservation, not a storage implementation.
    if (type(next_unreserved) is not int or type(count) is not int or count <= 0
            or next_unreserved < 0 or next_unreserved + count > MAX_COUNTER):
        raise ValueError("missing, rolled-back or exhausted Signal allocator")
    return next_unreserved, next_unreserved + count


def resume_nonce(snapshot_next, durable_next):
    # durable_next denotes the existing allocator's independently preserved
    # high-water, not a new protocol ledger or proof of physical durability.
    if (type(snapshot_next) is not int or type(durable_next) is not int
            or not 0 <= snapshot_next <= durable_next <= MAX_COUNTER):
        raise ValueError("Signal allocator continuity is not established")
    return durable_next


def accept_nonce(seen, scope, counter):
    if type(counter) is not int or not 0 <= counter <= MAX_COUNTER:
        raise ValueError("invalid Signal nonce counter")
    item = scope, counter
    if item in seen:
        raise ValueError("Signal nonce replay")
    seen.add(item)
