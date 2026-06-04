#!/usr/bin/env python3
"""Apply P-D6 per-operation security buckets to the OpenAPI document.

For each operationId in the YAML, this script:
  1. Determines the HTTP method (post / get / put / delete / head) that wraps the operation.
  2. Looks up the operation's auth bucket from the table below.
  3. Builds the appropriate security YAML block (with contentDigest included only
     when the method carries a request body).
  4. Inserts or replaces the security block directly under the operationId line.

The script operates on raw text to preserve formatting. After running, the
caller MUST run `python tools/artifact_pipeline.py check` + lint to validate.

This is a one-shot migration. After P-D6 lands, future operation additions
should declare their `security:` block by hand using the same buckets.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

YAML_PATH = Path("spec/v1/artifacts/openapi/cokret-service-api.openapi.yaml")

# Method names that carry a body for which Content-Digest is required.
METHODS_WITH_BODY = {"post", "put", "patch", "delete"}
# Method names that do not carry a body.
METHODS_NO_BODY = {"get", "head", "options"}

# Bucket assignment for every operation_id in the registry.
#   public_no_auth          — security: [] explicit; describe / public DID
#   user_bearer             — bearer only (user-facing; no S2S)
#   user_or_service         — bearer OR (signature + did headers [+ digest if body])
#   service_only            — signature + did headers [+ digest] only
#   admin_bearer            — bearer only; reducer/policy enforces admin claim
#   presign_or_bearer       — bearer OR S2S OR presign query (blob.get / blob.head)
OPERATIONS: dict[str, str] = {
    # service_discovery
    "ck.server.describe": "public_no_auth",

    # identity_registry
    "ck.identity.describe_registry": "public_no_auth",
    "ck.identity.resolve": "user_or_service",          # conservative: private DID needs auth
    "ck.identity.get_document": "user_or_service",     # conservative: same
    "ck.identity.get_log": "user_or_service",
    "ck.identity.get_receipts": "user_or_service",
    "ck.identity.submit_did_operation": "service_only",  # witness / registry submission

    # events_sync
    "ck.events.describe": "public_no_auth",
    "ck.events.submit": "user_or_service",
    "ck.events.get": "user_or_service",
    "ck.events.resolve": "user_or_service",
    "ck.events.query": "user_or_service",
    "ck.events.query_post": "user_or_service",
    "ck.events.subscribe": "user_or_service",
    "ck.events.frontier": "user_or_service",
    "ck.ephemeral.send": "user_or_service",
    "ck.account.describe": "public_no_auth",
    "ck.account.subscribe": "user_bearer",              # account-aggregate streaming; user only
    "ck.account.cursor_revoke": "user_bearer",
    "ck.snapshot.head": "user_or_service",
    "ck.projection.spaces": "user_or_service",
    "ck.projection.flows": "user_or_service",
    "ck.projection.morphs": "user_or_service",

    # directory_discovery
    "ck.directory.describe": "public_no_auth",
    "ck.directory.search_realms": "user_or_service",
    "ck.directory.resolve_realm": "user_or_service",
    "ck.directory.search_organizations": "user_or_service",
    "ck.directory.resolve_organization": "user_or_service",
    "ck.directory.search_actors": "user_or_service",
    "ck.directory.search_users": "user_or_service",
    "ck.directory.resolve_handle": "user_or_service",
    "ck.directory.private_contact_discovery": "user_bearer",  # PSI privacy
    "ck.directory.announce": "user_or_service",
    "ck.directory.withdraw": "user_or_service",
    "ck.directory.push.register": "user_or_service",

    # blob_storage
    "ck.blob.upload": "user_bearer",                   # conservative: no S2S upload
    "ck.blob.head": "presign_or_bearer",
    "ck.blob.get": "presign_or_bearer",
    "ck.blob.presign": "user_bearer",                  # issuing presign needs full auth

    # realtime_media
    "ck.media.ice_config": "user_bearer",

    # authz_policy
    "ck.authz.check": "user_or_service",
    "ck.authz.get_effective_grants": "user_or_service",
    "ck.authz.get_invites": "user_bearer",
    "ck.policy.check": "user_or_service",

    # moderation_reports
    "ck.moderation.report": "user_bearer",             # conservative: no S2S report

    # device_and_keys
    "ck.device_messages.put": "user_or_service",       # S2S device routing
    "ck.device_messages.get": "user_bearer",
    "ck.keys.upload": "user_bearer",
    "ck.keys.query": "user_or_service",
    "ck.keys.claim": "user_or_service",
    "ck.keys.keypackages.upload": "user_bearer",
    "ck.keys.keypackages.claim": "user_or_service",
    "ck.keys.keypackages.consume": "user_or_service",
    "ck.keys.keypackages.revoke": "user_bearer",
    "ck.keys.backups.put": "user_bearer",
    "ck.keys.backups.list": "user_bearer",
    "ck.keys.backups.get": "user_bearer",
    "ck.keys.backups.delete": "user_bearer",

    # push
    "ck.push.register_device": "user_bearer",
    "ck.push.unregister_device": "user_bearer",
    "ck.push.notify": "service_only",                  # principal server → push gateway

    # applet (interop_bridge)
    "ck.applet.ping": "service_only",
    "ck.applet.describe": "public_no_auth",            # public service metadata
    "ck.applet.transaction": "service_only",
    "ck.applet.resolve_actor": "service_only",
    "ck.applet.resolve_realm": "service_only",
    "ck.applet.protocol_metadata": "public_no_auth",
    "ck.applet.third_party_users": "service_only",
    "ck.applet.third_party_locations": "service_only",

    # mimi_interop (interop_bridge)
    "ck.mimi.provider_directory": "public_no_auth",
    "ck.mimi.group_info": "service_only",
    "ck.mimi.key_material": "service_only",
    "ck.mimi.submit_message": "service_only",
    "ck.mimi.room_update": "service_only",
    "ck.mimi.request_consent": "service_only",
    "ck.mimi.update_consent": "service_only",
    "ck.mimi.identifier_query": "service_only",
    "ck.mimi.notify": "service_only",
    "ck.mimi.report_abuse": "service_only",
    "ck.mimi.proxy_download": "service_only",

    # account_auth (deployment_local)
    "ck.account.device_pair": "user_bearer",
    "ck.account.issue_session_grant": "public_no_auth",   # callback-style; body carries proof
    "ck.account.oidc_callback": "public_no_auth",         # OIDC redirect with `code`
}


def render_security(bucket: str, has_body: bool, indent: str) -> list[str]:
    """Return the YAML lines for the security block at the given indent."""
    pad = indent
    if bucket == "public_no_auth":
        return [f"{pad}security: []"]
    if bucket in ("user_bearer", "admin_bearer"):
        return [
            f"{pad}security:",
            f"{pad}- bearerAuth: []",
        ]
    if bucket == "user_or_service":
        lines = [
            f"{pad}security:",
            f"{pad}- bearerAuth: []",
            f"{pad}- httpMessageSignature: []",
            f"{pad}  sourceServiceDid: []",
            f"{pad}  destinationServiceDid: []",
        ]
        if has_body:
            lines.append(f"{pad}  contentDigest: []")
        return lines
    if bucket == "service_only":
        lines = [
            f"{pad}security:",
            f"{pad}- httpMessageSignature: []",
            f"{pad}  sourceServiceDid: []",
            f"{pad}  destinationServiceDid: []",
        ]
        if has_body:
            lines.append(f"{pad}  contentDigest: []")
        return lines
    if bucket == "presign_or_bearer":
        lines = [
            f"{pad}security:",
            f"{pad}- bearerAuth: []",
            f"{pad}- httpMessageSignature: []",
            f"{pad}  sourceServiceDid: []",
            f"{pad}  destinationServiceDid: []",
        ]
        if has_body:
            lines.append(f"{pad}  contentDigest: []")
        lines.append(f"{pad}- presignParam: []")
        return lines
    raise ValueError(f"unknown bucket: {bucket}")


def main() -> int:
    text = YAML_PATH.read_text(encoding="utf-8")
    lines = text.splitlines()
    out: list[str] = []
    method_re = re.compile(r"^(\s+)(get|post|put|delete|head|patch|options):\s*$")
    operation_re = re.compile(r"^(\s+)operationId:\s*(\S+)\s*$")
    security_re = re.compile(r"^(\s+)security\s*:\s*(\S.*)?$")

    i = 0
    last_method: str | None = None
    last_method_indent: str | None = None
    seen: set[str] = set()
    while i < len(lines):
        line = lines[i]
        # Track the most recent HTTP method so we know body-presence by the
        # time we encounter the operationId. Method is the parent of operationId
        # so it always appears first.
        m_method = method_re.match(line)
        if m_method:
            indent, method = m_method.groups()
            last_method = method.lower()
            last_method_indent = indent
        m_op = operation_re.match(line)
        if m_op and last_method:
            op_indent, op_id = m_op.groups()
            if op_id in OPERATIONS:
                if op_id in seen:
                    # Should not happen — operationId is unique. Bail out for safety.
                    print(f"ERROR: duplicate operationId {op_id}", file=sys.stderr)
                    return 2
                seen.add(op_id)
                bucket = OPERATIONS[op_id]
                has_body = last_method in METHODS_WITH_BODY
                # Look ahead to see if there's an existing security block
                # at the same indent as operationId; replace it if so.
                # YAML array items use "- " at the SAME indent as their parent
                # field — we must NOT treat those as siblings of operationId.
                j = i + 1
                existing_security_start = None
                existing_security_end = None
                op_indent_len = len(op_indent)
                while j < len(lines):
                    nxt = lines[j]
                    stripped = nxt.lstrip()
                    if not stripped:
                        j += 1
                        continue
                    cur_indent = len(nxt) - len(stripped)
                    is_array_item = stripped.startswith("- ")
                    # End of operation block if we hit a lower-indent line.
                    if cur_indent < op_indent_len:
                        break
                    # Sibling field of operationId (parameters/responses/etc)
                    # — same indent as op, NOT an array item.
                    if cur_indent == op_indent_len and not is_array_item:
                        if stripped.startswith("security:"):
                            existing_security_start = j
                            # Find end of security block: first line whose
                            # indent is < op_indent_len, or a same-indent
                            # non-array-item sibling.
                            k = j + 1
                            while k < len(lines):
                                sub_line = lines[k]
                                sub = sub_line.lstrip()
                                if not sub:
                                    k += 1
                                    continue
                                sub_indent = len(sub_line) - len(sub)
                                sub_is_array_item = sub.startswith("- ")
                                if sub_indent < op_indent_len:
                                    break
                                if sub_indent == op_indent_len and not sub_is_array_item:
                                    break
                                k += 1
                            existing_security_end = k
                            break
                        # different sibling key — keep scanning past it
                        j += 1
                        continue
                    # Deeper-indented content (operation body) or array items —
                    # not a sibling, keep scanning.
                    j += 1
                # Emit current operationId line
                out.append(line)
                sec_lines = render_security(bucket, has_body, op_indent)
                out.extend(sec_lines)
                if existing_security_start is not None:
                    # Skip old security block on emit
                    i += 1
                    while i < existing_security_end:
                        i += 1
                    continue
                i += 1
                continue
        out.append(line)
        i += 1

    # Unhandled operations sanity check
    listed = set(OPERATIONS.keys())
    missing = listed - seen
    if missing:
        print(
            f"WARNING: {len(missing)} operationIds in OPERATIONS but not found in YAML:",
            file=sys.stderr,
        )
        for m in sorted(missing):
            print(f"  - {m}", file=sys.stderr)

    YAML_PATH.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"applied security to {len(seen)} operations")
    return 0


if __name__ == "__main__":
    sys.exit(main())
