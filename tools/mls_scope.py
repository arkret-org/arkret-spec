"""Exact MLS scope locators for signed claim intents, not native authority."""
from __future__ import annotations

import base64
import hashlib


def canonical_mls_group_id(scope: dict) -> str:
    kind = scope.get("kind")
    fields = {"kind", "realm_id"}
    if kind == "realm":
        key = scope.get("realm_id")
    elif kind == "circle":
        fields.add("circle_id")
        key = scope.get("circle_id")
    elif kind == "sidecar":
        fields.add("sidecar_id")
        realm, sidecar = scope.get("realm_id"), scope.get("sidecar_id")
        key = realm + "\x1f" + sidecar if isinstance(realm, str) and isinstance(sidecar, str) else None
    else:
        raise ValueError("claim requires an executable MLS scope")
    if set(scope) != fields or not isinstance(key, str) or not isinstance(scope.get("realm_id"), str):
        raise ValueError("claim scope is not closed")
    return base64.urlsafe_b64encode(hashlib.sha256(b"ak.mls.group_id.v1\0" + key.encode("utf-8")).digest()).decode("ascii").rstrip("=")


def verify_claim_scope(request: dict) -> None:
    """Check the original target binding without granting membership or disclosure."""
    scope = request.get("effective_scope")
    if not isinstance(scope, dict):
        raise ValueError("claim requires its complete target scope")
    if scope.get("realm_id") != request.get("intended_realm_id"):
        raise ValueError("claim scope differs from intended Realm")
    if canonical_mls_group_id(scope) != request.get("mls_group_id"):
        raise ValueError("claim scope differs from signed MLS group ID")
    if request.get("claim_purpose") == "direct_conversation" and scope["kind"] != "realm":
        raise ValueError("Direct claim requires its own Realm scope")
