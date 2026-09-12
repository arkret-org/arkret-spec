#!/usr/bin/env python3
"""Generate snapshot serialization vectors; these are not restore proofs."""
from __future__ import annotations
import copy
import hashlib
import json
import sys
from pathlib import Path
from blake3 import blake3

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.artifact_lint.core import canonical_json


def hash_bytes(data, suite):
    return hashlib.sha256(data).digest() if suite == "sha256" else blake3(data).digest()


def tree(leaves, suite):
    if not leaves:
        return hash_bytes(b"", suite)
    if len(leaves) == 1:
        return hash_bytes(b"\x00" + leaves[0], suite)
    split = 1 << ((len(leaves) - 1).bit_length() - 1)
    return hash_bytes(b"\x01" + tree(leaves[:split], suite) + tree(leaves[split:], suite), suite)


def main():
    path = ROOT / "spec/v1/artifacts/fixtures/sync-fixture.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    old = data["snapshot_state_digest"]
    catalog = json.loads((ROOT / "spec/v1/artifacts/registry/contract-registry.json").read_text(encoding="utf-8"))
    models = {w["cell_family"]: w["state_model"] for c in catalog["event_kind_registry"]["cell_contracts"].values() for w in c["cell_writes"]}
    items = copy.deepcopy(old["cases"][0]["chunks"][0]["items"])
    event_id = "ak:event:AQsHmGu_9sPOyJ4aG8VlWQBp8wGGhdC-BjfAaXqrIbk-"
    for item in items:
        model = models[item["id"].split(":", 3)[2]]
        item["state_model"] = model
        state = item["state"]
        if model == "sequenced_state" and "revision_event_id" not in state:
            head = state.get("heads", [{"event_id": event_id, "value": state.get("value")}])[0]
            item["state"] = {"revision_event_id": head["event_id"], "value": head["value"]}
        elif model == "causal_register":
            heads = state.get("heads", [{"event_id": event_id, "value": state.get("value")}])
            item["state"] = {"covered_event_ids": sorted(h["event_id"] for h in heads), "heads": heads}
        elif model == "or_set" and isinstance(state["value"], list):
            item["state"] = {"value": {"adds": state["value"], "removed_tag_ids": []}}
        elif model == "ordered_log":
            for entry in state["value"]:
                if isinstance(entry["issuer_id"], str):
                    entry["issuer_id"] = {"kind": "service", "service_id": entry["issuer_id"]}
    items.sort(key=lambda x: x["id"])
    preimages = [canonical_json({"cell": x["id"], "state_model": x["state_model"], "state": x["state"]}).encode() for x in items]
    root = "sha256:" + tree(preimages, "sha256").hex()
    template = copy.deepcopy(old["cases"][0]["chunks"][0])
    template.update(items=items, eligibility_context_digest="sha256:" + "e" * 64, replay_events=[], replay_authority_refs=[])
    cases = [{"name": "canonical_chunk_recomputes_state_digest", "expected": "accept_digest_only", "digest_algorithm": "sha256", "chunks": [template], "declared_state_digest": root}]
    split_chunks = []
    for index, part in enumerate([items[:2], items[2:4], items[4:]]):
        chunk = copy.deepcopy(template)
        chunk.update(index=index, items=part)
        split_chunks.append(chunk)
    cases.append({"name": "chunk_boundaries_do_not_change_state_digest", "expected": "accept_digest_only", "digest_algorithm": "sha256", "chunks": split_chunks, "declared_state_digest": root})
    cases.append({"name": "blake3_digest", "expected": "accept_digest_only", "digest_algorithm": "blake3", "chunks": [copy.deepcopy(template)], "declared_state_digest": "blake3:" + tree(preimages, "blake3").hex()})
    for name, mutation in [
        ("wrong_digest", "declared_digest"), ("wrong_family_model", "state_model"),
        ("missing_coverage", "covered_event_ids"), ("duplicate_cell", "duplicate_item"),
        ("wrong_eligibility_context", "eligibility_context_digest"),
        ("missing_replay_evidence_blocks_restore", "replay_events"),
    ]:
        cases.append({"name": name, "mutation": mutation, "expected": "reject_or_pending_restore" if mutation == "replay_events" else "reject", "source_case": "canonical_chunk_recomputes_state_digest"})
    data["snapshot_state_digest"] = {
        "vector_id": old["vector_id"], "manifest": old["manifest"],
        "scope": "Digest serialization only. Empty replay evidence is deliberately not a complete authenticated restore proof.",
        "assertions": ["snapshot_root_is_distinct_from_seal_security_root", "full_model_state_is_hashed", "rfc6962_recursive_split", "fixed_eligibility_context_required_for_restore"],
        "leaves": [{"id": item["id"], "leaf_preimage": preimage.decode(), "leaf": "sha256:" + hash_bytes(b"\x00" + preimage, "sha256").hex()} for item, preimage in zip(items, preimages)],
        "state_digest": root, "cases": cases,
    }
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    if "--check" in sys.argv:
        if path.read_text(encoding="utf-8") != text:
            raise SystemExit("Snapshot state fixture drift")
    else:
        path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
