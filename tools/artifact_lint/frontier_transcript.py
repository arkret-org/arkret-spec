"""Keep the federation frontier transcript and envelope anchors in agreement."""

from .core import ARTIFACTS, Lint, load_json

FIELDS = ["domain", "frontier_root", "auth_state_root", "policy_frontier_root",
          "membership_frontier_root", "realm_id", "issuer_id", "max_hlc", "observed_at"]
DOMAIN = "ak.events.frontier.signature.v1"


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
    envelope = ["typ", "scheme", "verification_method", "payload_digest", "created_at", "jws", "signed_payload"]
    if signature.get("required") != envelope or set(signature.get("properties", {})) != set(envelope) or signature.get("additionalProperties") is not False:
        lint.fail(schema_path, "frontier signature envelope must be closed and complete")
    if signature.get("properties", {}).get("typ", {}).get("const") != DOMAIN:
        lint.fail(schema_path, "frontier signature typ must match its registered domain")
    prose_path = ARTIFACTS.parent / "zh/sync/federation.md"
    prose = prose_path.read_text(encoding="utf-8")
    if ", ".join(FIELDS) not in prose or DOMAIN not in prose:
        lint.fail(prose_path, "frontier normative transcript must match the registry field list")
    section = prose.split("#### 4.5.1", 1)[-1].split("#### 4.5.2", 1)[0]
    if '"heads"' in section or '"issuer"' in section or "JSON null" not in section:
        lint.fail(prose_path, "frontier probe must use canonical field names and explicit optional nulls")
