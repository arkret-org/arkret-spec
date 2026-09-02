"""Require every schema definition to be reachable from a machine root."""

from __future__ import annotations

from pathlib import PurePosixPath
from urllib.parse import unquote

from .core import ARTIFACTS, Any, Lint, json, load_json, re


ROOT_REGISTRY = ARTIFACTS.parents[2] / "tools" / "schema-root-registry.json"
SCHEMAS = ARTIFACTS / "schemas"
SCHEMA_REF_RE = re.compile(r"(?:\.\./)?schemas/([^#\s\"']+\.json)(?:#([^\s\"']+))?")


def _resolve_pointer(document: Any, fragment: str) -> Any:
    current = document
    if fragment.startswith("/"):
        for token in fragment[1:].split("/"):
            token = token.replace("~1", "/").replace("~0", "~")
            current = current[token]
    elif fragment:
        raise KeyError(fragment)
    return current


def _schema_ref_key(value: str) -> tuple[str, str]:
    match = SCHEMA_REF_RE.fullmatch(value)
    if match is None:
        raise ValueError(value)
    return match.group(1), unquote(match.group(2) or "")


def _machine_roots(documents: dict[str, Any]) -> list[tuple[str, str]]:
    # A schema document's catalog-style root oneOf is an index, not a protocol
    # owner.  Ownership starts at an explicit operation/profile/binding/OpenAPI
    # reference (plus the separately registered formal roots below), and the
    # reference graph is then followed transitively.
    roots: list[tuple[str, str]] = []
    for directory in ("registry", "profiles", "bindings", "openapi"):
        for path in sorted((ARTIFACTS / directory).rglob("*")):
            if not path.is_file() or path.suffix.lower() not in {".json", ".yaml", ".yml"}:
                continue
            text = path.read_text(encoding="utf-8")
            for match in SCHEMA_REF_RE.finditer(text):
                if match.group(1) in documents:
                    roots.append((match.group(1), unquote(match.group(2) or "")))
    return roots


def _reachable(
    documents: dict[str, Any], roots: list[tuple[str, str]]
) -> set[tuple[str, str]]:
    seen: set[tuple[str, str]] = set()
    pending = list(roots)
    while pending:
        file_name, fragment = pending.pop()
        key = (file_name, fragment)
        if key in seen or file_name not in documents:
            continue
        seen.add(key)
        try:
            node = _resolve_pointer(documents[file_name], fragment)
        except (KeyError, TypeError):
            continue
        stack = [node]
        while stack:
            value = stack.pop()
            if isinstance(value, dict):
                reference = value.get("$ref")
                if isinstance(reference, str):
                    path, _, target_fragment = reference.partition("#")
                    target_file = (
                        PurePosixPath(file_name).parent.joinpath(path).name if path else file_name
                    )
                    if target_file in documents:
                        pending.append((target_file, unquote(target_fragment)))
                stack.extend(
                    child
                    for name, child in value.items()
                    if name not in {"$defs", "$ref"}
                )
            elif isinstance(value, list):
                stack.extend(value)
    return seen


def _registry_value(path: str) -> Any:
    file_part, _, fragment = path.partition("#")
    document = json.loads((ARTIFACTS / file_part).read_text(encoding="utf-8"))
    return _resolve_pointer(document, fragment)


def check_schema_root_reachability(lint: Lint) -> None:
    registry = load_json(lint, ROOT_REGISTRY)
    if not isinstance(registry, dict) or registry.get("source_of_truth") is not True:
        lint.fail(ROOT_REGISTRY, "schema root registry must be a source_of_truth object")
        return
    documents = {
        path.name: load_json(lint, path)
        for path in sorted(SCHEMAS.glob("*.json"))
    }
    documents = {name: value for name, value in documents.items() if isinstance(value, dict)}
    all_defs = {
        (file_name, f"/$defs/{def_name}")
        for file_name, document in documents.items()
        for def_name in document.get("$defs", {})
    }

    formal_refs: list[str] = []
    for index, root in enumerate(registry.get("formal_roots", [])):
        if not isinstance(root, dict):
            lint.fail(ROOT_REGISTRY, f"formal_roots[{index}] must be an object")
            continue
        schema_ref = root.get("schema_ref")
        kind = root.get("kind")
        if kind not in {"canonical_preimage", "decoded_artifact", "conformance_only"}:
            lint.fail(ROOT_REGISTRY, f"formal_roots[{index}].kind is not registered")
        try:
            key = _schema_ref_key(schema_ref)
            _resolve_pointer(documents[key[0]], key[1])
        except (ValueError, KeyError, TypeError):
            lint.fail(ROOT_REGISTRY, f"formal_roots[{index}].schema_ref does not resolve: {schema_ref!r}")
            continue
        formal_refs.append(schema_ref)
        registry_path = root.get("registry_path")
        try:
            registered_ref = _registry_value(registry_path)
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            registered_ref = None
        if registered_ref != schema_ref:
            lint.fail(ROOT_REGISTRY, f"formal_roots[{index}] is not registered at {registry_path!r}")
        implementation = root.get("implementation_path")
        symbol = root.get("implementation_symbol")
        implementation_path = ARTIFACTS.parents[2] / implementation if isinstance(implementation, str) else None
        if (
            implementation_path is None
            or not implementation_path.is_file()
            or not isinstance(symbol, str)
            or symbol not in implementation_path.read_text(encoding="utf-8")
        ):
            lint.fail(ROOT_REGISTRY, f"formal_roots[{index}] has no live implementation dispatch")

    compatibility = registry.get("compatibility_review")
    compatibility_refs = compatibility.get("schema_refs") if isinstance(compatibility, dict) else None
    if (
        not isinstance(compatibility, dict)
        or not isinstance(compatibility.get("owner"), str)
        or not isinstance(compatibility.get("reason"), str)
        or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(compatibility.get("review_by", "")))
        or not isinstance(compatibility_refs, list)
        or not all(isinstance(item, str) for item in compatibility_refs)
    ):
        lint.fail(ROOT_REGISTRY, "compatibility_review must declare owner, reason, review_by and schema_refs")
        return
    if len(compatibility_refs) != len(set(compatibility_refs)):
        lint.fail(ROOT_REGISTRY, "compatibility schema roots must be unique")

    base_roots = _machine_roots(documents)
    base_roots.extend(_schema_ref_key(value) for value in formal_refs)
    reached = _reachable(documents, base_roots)
    unreachable = all_defs - reached
    expected_compatibility: set[tuple[str, str]] = set()
    for schema_ref in compatibility_refs:
        try:
            key = _schema_ref_key(schema_ref)
            _resolve_pointer(documents[key[0]], key[1])
            expected_compatibility.add(key)
        except (ValueError, KeyError, TypeError):
            lint.fail(ROOT_REGISTRY, f"stale compatibility schema root: {schema_ref}")

    for file_name, fragment in sorted(unreachable - expected_compatibility):
        lint.fail(
            SCHEMAS / file_name,
            f"orphan schema definition {fragment} is unreachable from every protocol owner; connect it to an operation, Event kind, owned schema or registered dated root",
        )
    for file_name, fragment in sorted(expected_compatibility - unreachable):
        lint.fail(
            ROOT_REGISTRY,
            f"compatibility root schemas/{file_name}#{fragment} is now reachable and must be removed from the review list",
        )
