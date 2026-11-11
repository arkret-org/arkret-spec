"""Inventory naming surfaces without deciding ownership or semantic correctness.

Schema keywords select schema positions. Ordinary JSON keys, example members,
dynamic map keys and Markdown candidates are deliberately separate surfaces.
The report is deterministic and makes no naming-compliance or semantic claim.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
from typing import Any

import yaml

SCHEMA_MAPS = {"$defs", "definitions", "properties", "patternProperties", "dependentSchemas"}
SCHEMA_SINGLE = {
    "additionalProperties", "unevaluatedProperties", "propertyNames", "contains",
    "not", "if", "then", "else", "additionalItems", "unevaluatedItems", "contentSchema",
}
SCHEMA_ARRAYS = {"allOf", "anyOf", "oneOf", "prefixItems"}
METHODS = {"get", "put", "post", "delete", "options", "head", "patch", "trace", "query"}
COMPONENTS = {
    "schemas", "responses", "parameters", "examples", "requestBodies", "headers",
    "securitySchemes", "links", "callbacks", "pathItems",
}
TOKEN = re.compile(r"(?:[A-Za-z_$][A-Za-z0-9_.$:/{}<>-]*)\Z")
INLINE_CODE = re.compile(r"(?<!`)(`+)([^`\n]+?)\1(?!`)")
FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})(.*)$")
TYPE_DECLARATION = re.compile(r"\b(?:interface|struct|enum|type|class)\s+([A-Za-z_][A-Za-z0-9_]*)")
PASCAL_CANDIDATE = re.compile(r"(?<![A-Za-z0-9_])([A-Z][A-Za-z0-9]*(?:_[A-Za-z0-9]+)*)(?![A-Za-z0-9_])")


def pointer(parent: str, token: str | int) -> str:
    return parent + "/" + str(token).replace("~", "~0").replace("/", "~1")


def scalar_name(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def json_document(text: str) -> Any:
    def mapping(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"duplicate JSON member prevents an unambiguous inventory: {key}")
            result[key] = value
        return result
    return json.loads(text, object_pairs_hook=mapping)


class Inventory:
    def __init__(self) -> None:
        self.records: list[dict[str, Any]] = []
        self.files: list[dict[str, str]] = []

    def add(self, file: str, path: str, name: str, category: str, context: str,
            source_role: str, **metadata: Any) -> None:
        self.records.append(dict(file=file, pointer=path, name=name, category=category,
                                 context=context, source_role=source_role, **metadata))

    def data(self, value: Any, file: str, path: str, context: str, role: str) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                here = pointer(path, key)
                self.add(file, here, key, "data.member", context, role)
                self.data(child, file, here, context, role)
        elif isinstance(value, list):
            for index, child in enumerate(value):
                self.data(child, file, pointer(path, index), context, role)
        elif isinstance(value, str):
            category = "data.token_candidate" if TOKEN.fullmatch(value) else "data.string_value_candidate"
            self.add(file, path, value, category, context, role)

    def schema(self, node: Any, file: str, path: str, context: str, role: str) -> None:
        if not isinstance(node, dict):
            return
        external = node.get("x-arkret-external-literal-object")
        for key, value in node.items():
            here = pointer(path, key)
            self.add(file, here, key, "schema.keyword", context, role)
            if key in SCHEMA_MAPS and isinstance(value, dict):
                for name, child in value.items():
                    child_path = pointer(here, name)
                    if key in {"$defs", "definitions"}:
                        category = "schema.type_declaration"
                    elif key == "properties":
                        category = "schema.property_name"
                    elif key == "patternProperties":
                        category = "schema.dynamic_key_pattern"
                    else:
                        category = "schema.dependent_property_name"
                    metadata = {}
                    if key == "properties":
                        metadata["ownership"] = "external_literal_object" if external else "arkret_or_undeclared"
                        if external:
                            metadata["external_owner"] = external
                    self.add(file, child_path, name, category, context, role, **metadata)
                    self.schema(child, file, child_path, context, role)
            elif key in SCHEMA_SINGLE or key == "items":
                if key in {"additionalProperties", "unevaluatedProperties"} and value is not False:
                    self.add(file, here, "*", "schema.dynamic_key_slot", context, role)
                if isinstance(value, list):
                    for index, child in enumerate(value):
                        self.schema(child, file, pointer(here, index), context, role)
                else:
                    self.schema(value, file, here, context, role)
            elif key in SCHEMA_ARRAYS and isinstance(value, list):
                for index, child in enumerate(value):
                    self.schema(child, file, pointer(here, index), context, role)
            elif key == "dependencies" and isinstance(value, dict):
                for name, child in value.items():
                    self.add(file, pointer(here, name), name, "schema.dependent_property_name", context, role)
                    if isinstance(child, dict):
                        self.schema(child, file, pointer(here, name), context, role)
                    else:
                        self.data(child, file, pointer(here, name), "schema.property_dependency", role)
            elif key == "enum" and isinstance(value, list):
                for index, literal in enumerate(value):
                    self.enum(node, literal, file, pointer(here, index), context, role)
            elif key == "const":
                self.enum(node, value, file, here, context, role)
            elif key == "$ref" and isinstance(value, str):
                self.add(file, here, value, "schema.reference", context, role)
            elif key in {"examples", "example", "default"}:
                self.data(value, file, here, "schema.instance_annotation", role)
            elif isinstance(value, (dict, list)):
                self.data(value, file, here, "schema.annotation_or_keyword_data", role)

    def enum(self, node: dict, value: Any, file: str, path: str, context: str, role: str) -> None:
        owner = node.get("x-arkret-value-ownership", {})
        owner = owner if isinstance(owner, dict) else {}
        self.add(file, path, scalar_name(value), "schema.enum_or_const", context, role,
                 literal=value, ownership=owner.get("class", "undeclared"),
                 declared_owner=owner.get("owner"), authority=owner.get("authority"))

    def openapi(self, node: Any, file: str, path: str, role: str, parent: str = "") -> None:
        if isinstance(node, list):
            for index, child in enumerate(node):
                self.openapi(child, file, pointer(path, index), role, parent)
            return
        if not isinstance(node, dict):
            return
        for key, value in node.items():
            here = pointer(path, key)
            self.add(file, here, key, "openapi.keyword_or_member", "openapi_document", role)
            if key == "schema":
                self.schema(value, file, here, "openapi_inline_schema", role)
            elif path == "/components" and key in COMPONENTS and isinstance(value, dict):
                for name, child in value.items():
                    declared = pointer(here, name)
                    category = "openapi.schema_component" if key == "schemas" else "openapi.component"
                    self.add(file, declared, name, category, "openapi_component_" + key, role)
                    if key == "schemas":
                        self.schema(child, file, declared, "openapi_component_schema", role)
                    else:
                        self.openapi(child, file, declared, role, key)
            elif key in {"paths", "webhooks"} and isinstance(value, dict):
                for name, child in value.items():
                    declared = pointer(here, name)
                    self.add(file, declared, name, "openapi.path_or_webhook", key, role)
                    self.openapi(child, file, declared, role, key)
            elif key == "operationId" and isinstance(value, str):
                self.add(file, here, value, "openapi.operation_id", "openapi_operation", role)
            elif key == "$ref" and isinstance(value, str):
                self.add(file, here, value, "openapi.reference", "openapi_reference", role)
            elif key == "name" and node.get("in") in {"path", "query", "header", "cookie"}:
                self.add(file, here, scalar_name(value), "openapi.parameter_name", "openapi_parameter_" + node["in"], role)
            elif key == "headers" and isinstance(value, dict):
                for name, child in value.items():
                    declared = pointer(here, name)
                    self.add(file, declared, name, "openapi.header_name", "openapi_header", role)
                    self.openapi(child, file, declared, role, "headers")
            elif key == "security" and isinstance(value, list):
                for index, requirement in enumerate(value):
                    if isinstance(requirement, dict):
                        for name, scopes in requirement.items():
                            declared = pointer(pointer(here, index), name)
                            self.add(file, declared, name, "openapi.security_requirement", "openapi_security", role)
                            self.data(scopes, file, declared, "openapi_security_scope", role)
            elif key in {"example", "examples", "default"} or key.startswith("x-"):
                self.data(value, file, here, "openapi_annotation_or_example", role)
            elif key in {"content", "responses"} and isinstance(value, dict):
                for name, child in value.items():
                    declared = pointer(here, name)
                    self.add(file, declared, name, "openapi.media_type" if key == "content" else "openapi.response_status", "openapi_" + key, role)
                    self.openapi(child, file, declared, role, key)
            else:
                self.openapi(value, file, here, role, key)

    def markdown(self, text: str, file: str) -> None:
        lines = text.splitlines()
        fence = None
        language = ""
        block: list[str] = []
        start = 0
        for index, line in enumerate(lines, 1):
            marker = FENCE.match(line)
            if marker and fence is None and (marker[1][0] != '`' or '`' not in marker[2]):
                information = marker[2].strip().split()
                fence, language, start, block = marker[1], information[0].lower() if information else '', index, []
                continue
            if fence is not None:
                if marker and marker[1][0] == fence[0] and len(marker[1]) >= len(fence) and not marker[2].strip():
                    if language == "json":
                        try:
                            value = json_document("\n".join(block))
                        except ValueError:
                            pass
                        else:
                            self.data(value, file, f"/markdown/code_blocks/{start}", "prose_json_instance_candidate", "normative_prose")
                    fence = None
                    continue
                block.append(line)
                declaration_spans = []
                for match in TYPE_DECLARATION.finditer(line):
                    declaration_spans.append(match.span(1))
                    self.add(file, f"/markdown/lines/{index}/declarations/{match.start()}", match[1],
                             "prose.type_declaration_candidate", "code_fence_" + language, "normative_prose")
                for match in PASCAL_CANDIDATE.finditer(line):
                    if match.span(1) not in declaration_spans:
                        self.add(file, f"/markdown/lines/{index}/code_tokens/{match.start()}", match[1],
                                 "prose.pascal_candidate", "code_fence_" + language, "normative_prose")
                continue
            inline_spans = []
            for match in INLINE_CODE.finditer(line):
                inline_spans.append(match.span())
                token = match[2]
                if TOKEN.fullmatch(token):
                    self.add(file, f"/markdown/lines/{index}/inline_code/{match.start()}", token,
                             "prose.identifier_candidate", "inline_code", "normative_prose")
            for match in PASCAL_CANDIDATE.finditer(line):
                if not any(start <= match.start() < end for start, end in inline_spans):
                    self.add(file, f"/markdown/lines/{index}/text_tokens/{match.start()}", match[1],
                             "prose.pascal_candidate", "prose_text", "normative_prose")

    def report(self) -> dict:
        records = sorted(self.records, key=lambda row: (row["file"], row["pointer"], row["category"], row["name"], row["context"]))
        identities = [(row["file"], row["pointer"], row["category"], row["name"], row["context"]) for row in records]
        if len(identities) != len(set(identities)):
            raise ValueError("inventory emitted a duplicate occurrence")
        return {
            "scope": "Declaration and candidate inventory only; not a semantic or naming-compliance verdict. Markdown line locations are synthetic RFC 6901 paths, not schema instance pointers.",
            "files": sorted(self.files, key=lambda row: row["file"]),
            "statistics": {
                "file_count": len(self.files), "occurrence_count": len(records),
                "by_category": dict(sorted(Counter(row["category"] for row in records).items())),
                "by_context": dict(sorted(Counter(row["context"] for row in records).items())),
                "by_source_role": dict(sorted(Counter(row["source_role"] for row in records).items())),
            },
            "occurrences": records,
        }


def build_inventory(root: Path) -> dict:
    root = root.resolve()
    artifacts = root / "spec/v1/artifacts"
    registry_roles = {}
    manifest = artifacts / "registry/registry-manifest.json"
    if manifest.exists():
        for row in json_document(manifest.read_text(encoding="utf-8")).get("registries", []):
            registry_roles[row["file"]] = row.get("source_role", "undeclared")
    result = Inventory()
    for path in sorted(artifacts.rglob("*")):
        if not path.is_file():
            continue
        file = path.relative_to(root).as_posix()
        local = path.relative_to(artifacts).as_posix()
        role = registry_roles.get(local, "schema_contract" if local.startswith("schemas/") else "unclassified_artifact")
        result.files.append(dict(file=file, source_role=role))
        result.add(file, "", path.name, "artifact.filename", "artifact_file", role)
        if path.suffix not in {".json", ".yaml", ".yml", ".md"}:
            continue
        text = path.read_text(encoding="utf-8")
        if path.suffix == ".md":
            result.markdown(text, file)
            continue
        document = json_document(text) if path.suffix == ".json" else yaml.safe_load(text)
        if local.startswith("schemas/"):
            result.add(file, "", path.name.removesuffix(".schema.json").replace("-", "_"), "schema.root_type_candidate", "schema_document", role)
            result.schema(document, file, "", "json_schema", role)
        elif isinstance(document, dict) and "openapi" in document:
            result.openapi(document, file, "", role)
        else:
            result.data(document, file, "", "registry_metadata" if local.startswith("registry/") else "artifact_data", role)
    for path in sorted((root / "spec/v1/zh").rglob("*")):
        if not path.is_file() or path.suffix not in {".md", ".mdx"}:
            continue
        file = path.relative_to(root).as_posix()
        result.files.append(dict(file=file, source_role="normative_prose"))
        result.markdown(path.read_text(encoding="utf-8"), file)
    for path in sorted((root / "tools").rglob("*.json")):
        file = path.relative_to(root).as_posix()
        result.files.append(dict(file=file, source_role="tool_metadata"))
        result.add(file, "", path.name, "tool.metadata_filename", "tool_metadata", "tool_metadata")
        result.data(json_document(path.read_text(encoding="utf-8")), file, "", "tool_metadata", "tool_metadata")
    return result.report()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    payload = json.dumps(build_inventory(args.root), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8", newline="\n")
    else:
        print(payload, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
