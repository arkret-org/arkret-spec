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

YAML_PATH = Path("spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml")

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
#   presign_or_bearer       — bearer OR S2S OR presign query (self.blob.resource.get / self.blob.resource.head)
OPERATIONS: dict[str, str] = {
    # service_discovery
    "ak.server.query.describe": "public_no_auth",

    # identity_registry
    "ak.root.identity.registry.query.describe": "public_no_auth",
    "ak.root.identity.query.resolve": "user_or_service",          # conservative: private DID needs auth
    "ak.root.identity.document.resource.get": "user_or_service",     # conservative: same
    "ak.root.identity.log.query.list": "user_or_service",
    "ak.root.identity.receipts.query.list": "user_or_service",
    "ak.root.identity.command.submit_did_operation": "service_only",  # witness / registry submission

    # events_sync
    "ak.self.events.query.describe": "public_no_auth",
    "ak.self.events.command.submit": "user_or_service",
    "ak.self.events.resource.get": "user_or_service",
    "ak.self.events.query.resolve": "user_or_service",
    "ak.self.events.query.scan": "user_or_service",
    "ak.self.events.query.scan_body": "user_or_service",
    "ak.self.events.stream.subscribe": "user_or_service",
    "ak.self.events.query.frontier": "user_or_service",
    "ak.self.ephemeral.command.send": "user_or_service",
    "ak.self.account.query.describe": "public_no_auth",
    "ak.self.account.stream.subscribe": "user_bearer",              # account-aggregate streaming; user only
    "ak.self.account.command.revoke_cursor": "user_bearer",
    "ak.self.snapshot.query.manifest_head": "user_or_service",
    "ak.self.space.query.list": "user_or_service",
    "ak.self.strand.query.list": "user_or_service",
    "ak.self.morph.query.list": "user_or_service",
    "ak.self.morph.resource.get": "user_or_service",

    # directory_discovery
    "ak.find.directory.query.describe": "public_no_auth",
    "ak.find.directory.query.search_realms": "user_or_service",
    "ak.find.directory.query.resolve_realm": "user_or_service",
    "ak.find.directory.query.search_organizations": "user_or_service",
    "ak.find.directory.query.resolve_organization": "user_or_service",
    "ak.find.directory.query.search_actors": "user_or_service",
    "ak.find.directory.query.search_users": "user_or_service",
    "ak.find.directory.query.resolve_handle": "user_or_service",
    "ak.find.directory.query.private_contact_discovery": "user_bearer",  # PSI privacy
    "ak.find.directory.command.announce": "user_or_service",
    "ak.find.directory.command.withdraw": "user_or_service",
    "ak.find.directory.push.command.register": "user_or_service",

    # blob_storage
    "ak.self.blob.upload.create": "user_bearer",                   # conservative: no S2S upload
    "ak.self.blob.resource.head": "presign_or_bearer",
    "ak.self.blob.resource.get": "presign_or_bearer",
    "ak.self.blob.command.presign": "user_bearer",                  # issuing presign needs full auth

    # realtime_media
    "ak.self.media.query.ice_config": "user_bearer",

    # authz_policy
    "ak.self.authz.query.check": "user_or_service",
    "ak.self.authz.grants.query.effective": "user_or_service",
    "ak.self.authz.invites.query.list": "user_bearer",
    "ak.self.policy.query.check": "user_or_service",

    # moderation_reports
    "ak.self.moderation.command.report": "user_bearer",             # conservative: no S2S report

    # device_and_keys
    "ak.self.device_messages.command.send": "user_or_service",       # S2S device routing
    "ak.self.device_messages.query.list": "user_bearer",
    "ak.self.keys.upload.create": "user_bearer",
    "ak.self.keys.query.lookup": "user_or_service",
    "ak.self.keys.command.claim": "user_or_service",
    "ak.self.keys.keypackages.upload.create": "user_bearer",
    "ak.self.keys.keypackages.command.claim": "user_or_service",
    "ak.self.keys.keypackages.command.consume": "user_or_service",
    "ak.self.keys.keypackages.command.revoke": "user_bearer",
    "ak.self.keys.backups.resource.replace": "user_bearer",
    "ak.self.keys.backups.query.list": "user_bearer",
    "ak.self.keys.backups.command.unlock": "user_bearer",
    "ak.self.keys.backups.resource.delete": "user_bearer",

    # push
    "ak.edge.push.command.register_device": "user_bearer",
    "ak.edge.push.command.unregister_device": "user_bearer",
    "ak.edge.push.command.notify": "service_only",                  # principal server → push gateway

    # applet (interop_bridge)
    "ak.edge.applet.query.ping": "service_only",
    "ak.edge.applet.query.describe": "public_no_auth",            # public service metadata
    "ak.edge.applet.command.transaction": "service_only",
    "ak.edge.applet.actor.query.resolve": "service_only",
    "ak.edge.applet.realm.query.resolve": "service_only",
    "ak.edge.applet.query.protocol_metadata": "public_no_auth",
    "ak.edge.applet.third_party_users.query.list": "service_only",
    "ak.edge.applet.third_party_locations.query.list": "service_only",

    # mimi_interop (interop_bridge)
    "ak.open.mimi.query.provider_directory": "public_no_auth",
    "ak.open.mimi.query.group_info": "service_only",
    "ak.open.mimi.exchange.request_key_material": "service_only",
    "ak.open.mimi.command.submit_message": "service_only",
    "ak.open.mimi.command.update_room": "service_only",
    "ak.open.mimi.command.request_consent": "service_only",
    "ak.open.mimi.command.update_consent": "service_only",
    "ak.open.mimi.query.identifiers": "service_only",
    "ak.open.mimi.command.notify": "service_only",
    "ak.open.mimi.command.report_abuse": "service_only",
    "ak.open.mimi.command.proxy_download": "service_only",

    # account_auth (deployment_local)
    "ak.gate.account.command.pair_device": "user_bearer",
    "ak.gate.account.command.issue_session_grant": "public_no_auth",   # callback-style; body carries proof
    "ak.gate.account.exchange.complete_oidc": "public_no_auth",         # OIDC redirect with `code`
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
            f"{pad}  sourceServiceId: []",
            f"{pad}  destinationServiceId: []",
        ]
        if has_body:
            lines.append(f"{pad}  contentDigest: []")
        return lines
    if bucket == "service_only":
        lines = [
            f"{pad}security:",
            f"{pad}- httpMessageSignature: []",
            f"{pad}  sourceServiceId: []",
            f"{pad}  destinationServiceId: []",
        ]
        if has_body:
            lines.append(f"{pad}  contentDigest: []")
        return lines
    if bucket == "presign_or_bearer":
        lines = [
            f"{pad}security:",
            f"{pad}- bearerAuth: []",
            f"{pad}- httpMessageSignature: []",
            f"{pad}  sourceServiceId: []",
            f"{pad}  destinationServiceId: []",
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
