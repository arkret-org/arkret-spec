#!/usr/bin/env python3
"""Regenerate SHA-256 canonical-JSON digest expectations in fixture artifacts.

Only the input/digest pairs recognized by ``artifact_lint`` are updated.
The script is deterministic and intentionally does not handle signatures or
non-SHA-256 suites.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "spec" / "v1" / "artifacts" / "fixtures"
SHAPES = (
    ("input", "expected_digest"),
    ("input", "digest"),
    ("envelope", "event_digest"),
    ("envelope", "payload_hash"),
    ("canonical_input", "expected_digest"),
)


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def iter_dict_nodes(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dict_nodes(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dict_nodes(child)


def replace(node: dict[str, Any], key: str, value: Any) -> int:
    if node.get(key) == value:
        return 0
    node[key] = value
    return 1


def update_direct_conversation_vectors(data: dict[str, Any]) -> int:
    """Refresh dependent Direct Conversation digests as one closed KAT set."""

    vectors = {
        vector.get("vector_id"): vector
        for vector in data.get("vectors", [])
        if isinstance(vector, dict)
    }
    pair = vectors.get("ak.vector.direct_conversation.pair_key.v1")
    binding = vectors.get("ak.vector.direct_conversation.binding_digest.v1")
    if not isinstance(pair, dict) or not isinstance(binding, dict):
        return 0
    pair_digest = pair.get("expected_digest")
    binding_input = binding.get("input")
    domain = binding.get("domain_separator_utf8")
    if not isinstance(pair_digest, str) or not isinstance(binding_input, dict) or not isinstance(domain, str):
        return 0

    updates = replace(binding_input, "pair_key", pair_digest)
    canonical = canonical_json(binding_input)
    binding_digest = "sha256:" + hashlib.sha256((domain + canonical).encode("utf-8")).hexdigest()
    updates += replace(binding, "expected_canonical_bytes_utf8", canonical)
    updates += replace(binding, "digest_input_hex", (domain + canonical).encode("utf-8").hex())
    updates += replace(binding, "expected_digest", binding_digest)

    for case in binding.get("normalization_cases", []):
        if not isinstance(case, dict):
            continue
        payload = case.get("payload")
        if isinstance(payload, dict):
            updates += replace(payload, "pair_key", pair_digest)
        updates += replace(case, "expected_digest", binding_digest)

    for case in binding.get("mutation_cases", []):
        if not isinstance(case, dict):
            continue
        if case.get("name") == "omit_domain_separator":
            bare = canonical.encode("utf-8")
            updates += replace(case, "digest_input_hex", bare.hex())
            updates += replace(case, "expected_digest", "sha256:" + hashlib.sha256(bare).hexdigest())
            continue
        mutation_input = case.get("input")
        mutation_domain = case.get("domain_separator_utf8")
        if isinstance(mutation_input, dict) and isinstance(mutation_domain, str):
            updates += replace(mutation_input, "pair_key", pair_digest)
            mutation_canonical = canonical_json(mutation_input)
            updates += replace(case, "expected_canonical_bytes_utf8", mutation_canonical)
            if "digest_input_hex" in case:
                updates += replace(
                    case,
                    "digest_input_hex",
                    (mutation_domain + mutation_canonical).encode("utf-8").hex(),
                )
            updates += replace(
                case,
                "expected_digest",
                "sha256:" + hashlib.sha256((mutation_domain + mutation_canonical).encode("utf-8")).hexdigest(),
            )
    return updates


def update_file(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    updates = 0
    for node in iter_dict_nodes(data):
        for input_key, digest_key in SHAPES:
            digest = node.get(digest_key)
            if input_key not in node or not isinstance(digest, str) or not digest.startswith("sha256:"):
                continue
            canonical = canonical_json(node[input_key])
            domain_separator = node.get("domain_separator_utf8", "")
            if not isinstance(domain_separator, str):
                continue
            digest_input = domain_separator + canonical
            expected = "sha256:" + hashlib.sha256(digest_input.encode("utf-8")).hexdigest()
            if node[digest_key] != expected:
                node[digest_key] = expected
                updates += 1
            if isinstance(node.get("expected_canonical_bytes_utf8"), str):
                if node["expected_canonical_bytes_utf8"] != canonical:
                    node["expected_canonical_bytes_utf8"] = canonical
                    updates += 1
            if isinstance(node.get("digest_input_hex"), str):
                expected_hex = digest_input.encode("utf-8").hex()
                if node["digest_input_hex"] != expected_hex:
                    node["digest_input_hex"] = expected_hex
                    updates += 1
    if path.name == "encoding-fixture.json" and isinstance(data, dict):
        updates += update_direct_conversation_vectors(data)
    if updates:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return updates


def main() -> int:
    changed_files = 0
    changed_values = 0
    for path in sorted(FIXTURES.glob("*.json")):
        updates = update_file(path)
        if updates:
            changed_files += 1
            changed_values += updates
    print(f"updated {changed_values} value(s) in {changed_files} fixture file(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
