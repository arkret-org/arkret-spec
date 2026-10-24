"""Derive and freeze the complete public schema/member and registry contract."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
REFERENCE = "tools/protocol-member-contract.json"
ANNOTATIONS = {"title", "$comment", "examples"}


def contract_shape(node):
    if isinstance(node,dict):
        return {key:contract_shape(value) for key,value in node.items() if key not in ANNOTATIONS}
    if isinstance(node,list):
        return [contract_shape(value) for value in node]
    return node


def registry_contract_shape(node):
    if isinstance(node, dict):
        metadata_owner = node.get("source_of_truth") is True or "metadata_authority" in node
        ignored = ANNOTATIONS | ({"version", "generated_at"} if metadata_owner else set())
        return {key: registry_contract_shape(value) for key, value in node.items() if key not in ignored}
    if isinstance(node, list):
        return [registry_contract_shape(value) for value in node]
    return node


def digest(node) -> str:
    raw = json.dumps(node,ensure_ascii=False,sort_keys=True,separators=(",", ":")).encode()
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def derive(root: Path = ROOT) -> dict:
    artifacts = root / "spec/v1/artifacts"
    schemas = []
    for path in sorted((artifacts / "schemas").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        # Keeping the complete assertion tree also freezes conditional required,
        # null/absent, open slots, branch order and signature-binding annotations.
        schemas.append({"file":path.name,"contract":contract_shape(document)})
    registries = []
    for path in sorted((artifacts / "registry").glob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("source_of_truth") is True:
            registries.append({"file":path.name,"digest":digest(registry_contract_shape(document))})
    import yaml
    openapi = yaml.safe_load((artifacts/"openapi/arkret-service-api.openapi.yaml").read_text(encoding="utf-8"))
    payload = {"encoding_profile_digest":digest((root / "spec/v1/zh/conformance/encoding.md").read_text(encoding="utf-8")),"schemas":schemas,"canonical_registries":registries,"openapi":contract_shape(openapi)}
    return {"format_version":1,"kind":"protocol_member_contract","source_of_truth":False,
            "generated_from":["spec/v1/artifacts/schemas", "spec/v1/artifacts/registry", "spec/v1/artifacts/openapi"],
            "generated_by":"tools/protocol_member_contract.py --refresh-candidate",
            "description":"Derived release contract: names, members, constraints, presence, enum ownership, encoding, units, ordering, open slots and canonical/signature bindings.",
            "contract_digest":digest(payload),**payload}


def compare(expected: dict, actual: dict) -> list[str]:
    if expected == actual:
        return []
    errors = []
    before={row['file']:row['contract'] for row in expected.get('schemas',[])}
    after={row['file']:row['contract'] for row in actual.get('schemas',[])}
    for name in sorted(before.keys() | after.keys()):
        if before.get(name) != after.get(name):
            errors.append(f"schema/member contract changed: {name}")
    if expected.get('canonical_registries') != actual.get('canonical_registries'):
        errors.append('canonical registry contract changed')
    if expected.get('openapi') != actual.get('openapi'):
        errors.append('HTTP path/query/header/status/body contract changed')
    return errors or ['member-contract provenance or aggregate digest changed']


def published_v1_tags(root: Path) -> list[str]:
    result = subprocess.run(['git', 'tag', '--list', 'v1.*'], cwd=root,
                            capture_output=True, text=True, encoding='utf-8', check=True)
    return sorted(tag for tag in result.stdout.splitlines()
                  if re.fullmatch(r'v1\.\d+\.\d+(?:\+[A-Za-z0-9.-]+)?', tag))


def check(root: Path = ROOT) -> list[str]:
    path=root/REFERENCE
    if not path.is_file():
        return ['public member contract is missing']
    expected=json.loads(path.read_text(encoding='utf-8'))
    errors=compare(expected,derive(root))
    for tag in published_v1_tags(root):
        result = subprocess.run(['git', 'show', tag + ':' + REFERENCE], cwd=root,
                                capture_output=True, text=True, encoding='utf-8')
        if result.returncode:
            errors.append(f'published v1 release {tag} lacks its frozen member contract')
        else:
            errors.extend(f'published v1 identity {tag} is immutable: ' + error
                          for error in compare(json.loads(result.stdout), expected))
    return errors


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--refresh-candidate',action='store_true')
    args=parser.parse_args()
    if args.refresh_candidate:
        from release_metadata import current_release_tag
        if '-candidate' not in current_release_tag() or published_v1_tags(ROOT):
            parser.error('a published v1 member contract cannot be refreshed in place')
        (ROOT/REFERENCE).write_text(json.dumps(derive(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    errors=check()
    for error in errors:print(error)
    if not errors:print('Public member contract: exact; published v1 identities remain immutable')
    return bool(errors)


if __name__=='__main__':
    raise SystemExit(main())
