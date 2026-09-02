"""Keep the federation frontier transcript and envelope anchors in agreement."""

from .core import ARTIFACTS, Lint, load_json

FIELDS = ["domain", "frontier_root", "auth_state_root", "policy_frontier_root",
          "membership_frontier_root", "realm_id", "issuer_id", "max_hlc", "observed_at"]
DOMAIN = "ak.events.frontier.signature.v1"
# The wire envelope carries only the two members the verifier cannot rebuild
# from the outer response. Everything the transcript already fixes (its typ,
# scheme, digest, an observed_at mirror and the transcript echo itself) is a
# second copy the verifier would have to distrust anyway.
ENVELOPE = ["verification_method", "jws"]
TRANSCRIPT_MIRRORS = frozenset({"typ", "scheme", "payload_digest", "created_at", "signed_payload"})


def check_frontier_transcript(lint: Lint) -> None:
    registry_path = ARTIFACTS / "registry/proof-context-registry.json"
    schema_path = ARTIFACTS / "schemas/service-operation-dtos.schema.json"
    registry = load_json(lint, registry_path)
    schema = load_json(lint, schema_path)
    if not isinstance(registry, dict) or not isinstance(schema, dict):
        return
    rows = [row for row in registry.get("domain_separations", []) if row.get("domain") == DOMAIN]
    anchor = "schemas/service-operation-dtos.schema.json#/$defs/EventsFrontierFederationPeerState/properties/signature"
    if len(rows) != 1 or any(rows[0].get(key) != value for key, value in {
        "binding_fields": FIELDS, "defined_in": "zh/sync/federation.md",
        "schema_ref": anchor, "primitive": "detached_signature",
    }.items()):
        lint.fail(registry_path, "frontier signature transcript or owning anchor drifted")
    response = schema.get("$defs", {}).get("EventsFrontierFederationPeerState", {})
    properties = response.get("properties", {})
    if response.get("x-arkret-signature-transcript") != FIELDS or any(field not in properties for field in FIELDS[1:]):
        lint.fail(schema_path, "frontier transcript must bind the exact nine fields and existing response members")
    signature = properties.get("signature", {})
    if signature.get("required") != ENVELOPE or set(signature.get("properties", {})) != set(ENVELOPE) or signature.get("additionalProperties") is not False:
        lint.fail(schema_path, "frontier signature envelope must be closed to verification_method and jws")
    mirrors = sorted(TRANSCRIPT_MIRRORS & set(signature.get("properties", {})))
    if mirrors:
        lint.fail(schema_path, f"frontier signature envelope must not mirror the rebuilt transcript: {mirrors}")
    if signature.get("x-arkret-signature-domain") != DOMAIN:
        lint.fail(schema_path, "frontier signature envelope must declare its registered domain")
    prose_path = ARTIFACTS.parent / "zh/sync/federation.md"
    prose = prose_path.read_text(encoding="utf-8")
    if ", ".join(FIELDS) not in prose or DOMAIN not in prose:
        lint.fail(prose_path, "frontier normative transcript must match the registry field list")
    section = prose.split("#### 4.5.1", 1)[-1].split("#### 4.5.2", 1)[0]
    if '"heads"' in section or '"issuer"' in section or "JSON null" not in section:
        lint.fail(prose_path, "frontier probe must use canonical field names and explicit optional nulls")
    prose_mirrors = sorted(name for name in TRANSCRIPT_MIRRORS if f"`{name}`" in section)
    if prose_mirrors or "`verification_method, jws`" not in section or "`observed_at` 必须在接收时间前后 300 秒内" not in section:
        lint.fail(prose_path, f"frontier signature prose must keep the two-member envelope and judge freshness on observed_at: {prose_mirrors}")
