"""Generate the non-authoritative DID representation review report."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"
OUTPUT = ROOT / "spec" / "v1" / "artifacts" / "reports" / "did-representation-report.json"

DID_NAMES = {
    "did": "did",
    "webvh_did": "did",
    "human_principal_did": "did",
    "agent_did": "did",
    "applet_managed_actor_did": "did",
    "ephemeral_pairwise_principal_did": "did",
    "did_key_did": "did",
    "did_core_id": "did_core_id",
    "did_url": "did_url",
}


def _escape(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


def _profiles(value: Any) -> tuple[set[str], set[str]]:
    profiles: set[str] = set()
    terminals: set[str] = set()
    if isinstance(value, dict):
        ref = value.get("$ref")
        if isinstance(ref, str):
            name = ref.rsplit("/", 1)[-1]
            profile = DID_NAMES.get(name)
            if profile:
                profiles.add(profile)
                terminals.add(f"ref:{name}")
                return profiles, terminals
        pattern = value.get("pattern")
        if isinstance(pattern, str):
            if pattern == r"^ak:did_core:[a-z0-9]+:[^\s/?#]+$":
                profiles.add("did_core_id")
                terminals.add(f"pattern:{pattern}")
            elif pattern.startswith("^did:"):
                profile = "did_url" if "+#[" in pattern or ")#" in pattern else "did"
                profiles.add(profile)
                terminals.add(f"pattern:{pattern}")
        for key in ("oneOf", "anyOf", "allOf"):
            children = value.get(key)
            if isinstance(children, list):
                for child in children:
                    child_profiles, child_terminals = _profiles(child)
                    profiles.update(child_profiles)
                    terminals.update(child_terminals)
        if value.get("type") == "array" and "items" in value:
            child_profiles, child_terminals = _profiles(value["items"])
            profiles.update(child_profiles)
            terminals.update(child_terminals)
    return profiles, terminals


def build_report() -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in sorted(SCHEMAS.glob("*.schema.json")):
        document = json.loads(path.read_text(encoding="utf-8"))

        def visit(value: Any, pointer: str, external_literal: bool) -> None:
            if isinstance(value, dict):
                external_annotation = value.get("x-arkret-external-literal-object")
                external = external_literal or external_annotation is True or isinstance(external_annotation, dict)
                properties = value.get("properties")
                if isinstance(properties, dict):
                    for name, schema in properties.items():
                        property_pointer = f"{pointer}/properties/{_escape(name)}"
                        profiles, terminals = _profiles(schema)
                        if profiles:
                            entries.append(
                                {
                                    "schema_path": f"{path.name}#{property_pointer}",
                                    "property_name": name,
                                    "semantic_category": (
                                        "external_system_identifier"
                                        if external or "/$defs/tsp_vid/" in property_pointer
                                        else "responsibility_identity_material"
                                    ),
                                    "representation_profile": (
                                        next(iter(profiles)) if len(profiles) == 1 else "ambiguous"
                                    ),
                                    "external_literal_owner": external,
                                    "terminal_signature": sorted(terminals),
                                }
                            )
                        visit(schema, property_pointer, external)
                for key, child in value.items():
                    if key != "properties":
                        visit(child, f"{pointer}/{_escape(key)}", external)
            elif isinstance(value, list):
                for index, child in enumerate(value):
                    visit(child, f"{pointer}/{index}", external_literal)

        visit(document, "", False)
    entries.sort(key=lambda row: row["schema_path"])
    return {
        "source_of_truth": False,
        "generated_by": "tools/generate_did_representation_report.py",
        "profiles": ["did_core_id", "did", "did_url"],
        "entries": entries,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    rendered = json.dumps(build_report(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not OUTPUT.exists() or OUTPUT.read_text(encoding="utf-8") != rendered:
            print(f"stale generated report: {OUTPUT.relative_to(ROOT).as_posix()}")
            return 1
        print("DID representation report is current")
        return 0
    OUTPUT.write_text(rendered, encoding="utf-8", newline="")
    print(f"generated {OUTPUT.relative_to(ROOT).as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
