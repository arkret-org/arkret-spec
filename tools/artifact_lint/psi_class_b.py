"""Private-contact-discovery Class B problem machine-artifact closure."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from .core import ARTIFACTS, Draft202012Validator, FormatChecker, Lint, load_json, yaml


SCHEMA_PATH = ARTIFACTS / "schemas" / "directory-operations.schema.json"
FIXTURE_PATH = ARTIFACTS / "fixtures" / "privacy-security-fixture.json"
SCHEMA_VALIDATION_FIXTURE_PATH = ARTIFACTS / "fixtures" / "schema-validation-fixture.json"
MAPPING_PATH = ARTIFACTS / "registry" / "operations-error-mapping.json"
ERROR_REGISTRY_PATH = ARTIFACTS / "registry" / "error-code-registry.json"
OPENAPI_PATH = ARTIFACTS / "openapi" / "arkret-service-api.openapi.yaml"

OPERATION_ID = "ak.find.directory.read.private_contact_discovery.v1"
SCHEMA_REF = "schemas/directory-operations.schema.json#/$defs/psi_padded_problem"
OPENAPI_SCHEMA_REF = "../schemas/directory-operations.schema.json#/$defs/psi_padded_problem"
BUCKETS = (4096, 16384, 65536, 262144)

ERROR_TRIPLES = {
    "psi_quota_exhausted": (
        "https://arkret.org/problems/psi_quota_exhausted",
        "Psi quota exhausted",
        429,
    ),
    "policy_denied": (
        "https://arkret.org/problems/policy_denied",
        "Policy denied",
        403,
    ),
    "duplicate_conflict": (
        "https://arkret.org/problems/duplicate_conflict",
        "Duplicate conflict",
        409,
    ),
    "psi_batch_unavailable": (
        "https://arkret.org/problems/psi_batch_unavailable",
        "Psi batch unavailable",
        410,
    ),
}

EXPECTED_PROJECTIONS = (
    ("blind", "psi_quota_exhausted", "blind_response_bucket_bytes", True),
    ("blind", "policy_denied", "blind_response_bucket_bytes", False),
    ("blind", "duplicate_conflict", "blind_response_bucket_bytes", False),
    ("match", "policy_denied", "match_response_bucket_bytes", False),
    ("match", "duplicate_conflict", "match_response_bucket_bytes", False),
    ("match", "psi_batch_unavailable", "match_response_bucket_bytes", False),
)

NEGATIVE_MUTATIONS = (
    "additional_extension",
    "missing_padding",
    "non_space_padding",
    "wrong_type_status_pair",
    "wrong_title",
    "overlong_detail",
    "overlong_instance",
)

SCHEMA_VALIDATION_CASES = {
    "psi_padded_problem_quota_exhausted_valid": True,
    "psi_padded_problem_policy_denied_valid": True,
    "psi_padded_problem_duplicate_conflict_valid": True,
    "psi_padded_problem_batch_unavailable_valid": True,
    "psi_padded_problem_old_envelope_rejected": False,
    "psi_padded_problem_extra_extension_rejected": False,
    "psi_padded_problem_type_status_mismatch_rejected": False,
    "psi_padded_problem_missing_padding_rejected": False,
    "psi_padded_problem_non_space_padding_rejected": False,
}


def _operation_row(mapping: object) -> dict[str, Any] | None:
    if not isinstance(mapping, dict):
        return None
    return next(
        (
            row
            for row in mapping.get("operations", [])
            if isinstance(row, dict) and row.get("operation_id") == OPERATION_ID
        ),
        None,
    )


def _fixture_vector(fixture: object) -> dict[str, Any] | None:
    if not isinstance(fixture, dict):
        return None
    return next(
        (
            row
            for row in fixture.get("cases", [])
            if isinstance(row, dict)
            and row.get("vector_id") == "ak.vector.psi.quota_blinded_denial.v1"
        ),
        None,
    )


def _mapping_projection_tuple(row: object) -> tuple[Any, ...] | None:
    if not isinstance(row, dict):
        return None
    return (
        row.get("phase"),
        row.get("error_code"),
        row.get("response_bucket_field"),
        row.get("retry_after_required"),
    )


def _problem_validator(schema: dict[str, Any]) -> Any:
    root = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "$defs": schema.get("$defs", {}),
        "$ref": "#/$defs/psi_padded_problem",
    }
    return Draft202012Validator(root, format_checker=FormatChecker())


def _maximal_problem(projection: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    prefix = policy.get("instance_prefix")
    fill = policy.get("instance_fill")
    instance_length = policy.get("instance_length")
    code_point = policy.get("detail_code_point")
    detail_length = policy.get("detail_length")
    if (
        not isinstance(prefix, str)
        or not isinstance(fill, str)
        or len(fill) != 1
        or not isinstance(instance_length, int)
        or not isinstance(code_point, str)
        or not code_point.startswith("U+")
        or not isinstance(detail_length, int)
    ):
        raise ValueError("invalid maximal string projection")
    instance = prefix + fill * (instance_length - len(prefix))
    return {
        "type": projection.get("type"),
        "title": projection.get("title"),
        "status": projection.get("status"),
        "detail": chr(int(code_point[2:], 16)) * detail_length,
        "instance": instance,
        "padding": policy.get("padding"),
    }


def _canonical_json_size(value: object) -> int:
    return len(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    )


def _negative_instances(problem: dict[str, Any]) -> dict[str, dict[str, Any]]:
    cases: dict[str, dict[str, Any]] = {}
    cases["additional_extension"] = copy.deepcopy(problem)
    cases["additional_extension"]["request_id"] = "ak:request:forbidden"
    cases["missing_padding"] = copy.deepcopy(problem)
    cases["missing_padding"].pop("padding")
    cases["non_space_padding"] = copy.deepcopy(problem)
    cases["non_space_padding"]["padding"] = "\t"
    cases["wrong_type_status_pair"] = copy.deepcopy(problem)
    cases["wrong_type_status_pair"]["status"] = 403
    cases["wrong_title"] = copy.deepcopy(problem)
    cases["wrong_title"]["title"] = "Rate limited"
    cases["overlong_detail"] = copy.deepcopy(problem)
    cases["overlong_detail"]["detail"] = "x" * 257
    cases["overlong_instance"] = copy.deepcopy(problem)
    cases["overlong_instance"]["instance"] = "ak:request:" + "a" * 118
    return cases


def _check_openapi(lint: Lint) -> None:
    if yaml is None:
        lint.fail(OPENAPI_PATH, "PyYAML is required for PSI Class B OpenAPI closure")
        return
    try:
        document = yaml.safe_load(OPENAPI_PATH.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as exc:
        lint.fail(OPENAPI_PATH, f"cannot parse OpenAPI for PSI Class B closure: {exc}")
        return
    components = document.get("components", {}) if isinstance(document, dict) else {}
    schemas = components.get("schemas", {}) if isinstance(components, dict) else {}
    if schemas.get("PsiPaddedProblem") != {"$ref": OPENAPI_SCHEMA_REF}:
        lint.fail(OPENAPI_PATH, "PsiPaddedProblem must reference the canonical directory schema")
    if "PsiResponsePadding" in schemas:
        lint.fail(OPENAPI_PATH, "PsiResponsePadding must not duplicate the canonical directory schema")

    response_expectations = {
        "PsiQuotaExhausted": ("psi_quota_exhausted", 429),
        "PsiPolicyDenied": ("policy_denied", 403),
        "PsiDuplicateConflict": ("duplicate_conflict", 409),
        "PsiBatchUnavailable": ("psi_batch_unavailable", 410),
    }
    responses = components.get("responses", {}) if isinstance(components, dict) else {}
    for name, (code, status) in response_expectations.items():
        response = responses.get(name, {}) if isinstance(responses, dict) else {}
        schema = (
            response.get("content", {})
            .get("application/problem+json", {})
            .get("schema", {})
        )
        all_of = schema.get("allOf", []) if isinstance(schema, dict) else []
        expected_overlay = {
            "properties": {
                "type": {"const": f"https://arkret.org/problems/{code}"},
                "status": {"const": status},
            }
        }
        if all_of != [{"$ref": "#/components/schemas/PsiPaddedProblem"}, expected_overlay]:
            lint.fail(OPENAPI_PATH, f"components.responses.{name} PSI problem projection drifted")


def check_psi_class_b_artifact_closure(lint: Lint) -> None:
    """Lock the schema, six phase/code projections, maximal bodies, and OpenAPI refs."""
    schema = load_json(lint, SCHEMA_PATH)
    fixture = load_json(lint, FIXTURE_PATH)
    schema_validation_fixture = load_json(lint, SCHEMA_VALIDATION_FIXTURE_PATH)
    mapping = load_json(lint, MAPPING_PATH)
    error_registry = load_json(lint, ERROR_REGISTRY_PATH)
    if not all(
        isinstance(value, dict)
        for value in (schema, fixture, schema_validation_fixture, mapping, error_registry)
    ):
        return
    if Draft202012Validator is None or FormatChecker is None:
        lint.fail(SCHEMA_PATH, "jsonschema is required for PSI Class B schema validation")
        return

    problem_schema = schema.get("$defs", {}).get("psi_padded_problem")
    if not isinstance(problem_schema, dict):
        lint.fail(SCHEMA_PATH, "missing canonical $defs.psi_padded_problem")
        return
    expected_required = ["type", "title", "status", "detail", "instance", "padding"]
    if problem_schema.get("required") != expected_required:
        lint.fail(SCHEMA_PATH, "psi_padded_problem required member order drifted")
    if problem_schema.get("additionalProperties") is not False:
        lint.fail(SCHEMA_PATH, "psi_padded_problem must remain closed")

    registry_rows = {
        row.get("code"): row
        for row in error_registry.get("codes", [])
        if isinstance(row, dict) and isinstance(row.get("code"), str)
    }
    for code, (type_uri, title, status) in ERROR_TRIPLES.items():
        row = registry_rows.get(code, {})
        if (row.get("type_uri"), row.get("title"), row.get("http_status")) != (
            type_uri,
            title,
            status,
        ):
            lint.fail(ERROR_REGISTRY_PATH, f"{code} canonical PSI problem triple drifted")

    operation = _operation_row(mapping)
    if operation is None:
        lint.fail(MAPPING_PATH, f"missing {OPERATION_ID}")
        return
    mapping_projections = operation.get("class_b_problem_projections")
    if not isinstance(mapping_projections, list):
        lint.fail(MAPPING_PATH, "PCD operation missing class_b_problem_projections machine map")
        return
    actual_mapping = tuple(_mapping_projection_tuple(row) for row in mapping_projections)
    if actual_mapping != EXPECTED_PROJECTIONS:
        lint.fail(MAPPING_PATH, "PCD Class B phase/code projection set or order drifted")
    for index, row in enumerate(mapping_projections):
        if not isinstance(row, dict):
            continue
        code = row.get("error_code")
        triple = ERROR_TRIPLES.get(code)
        if row.get("schema_ref") != SCHEMA_REF:
            lint.fail(MAPPING_PATH, f"class_b_problem_projections[{index}] schema_ref drifted")
        if triple is None or row.get("http_status") != triple[2]:
            lint.fail(MAPPING_PATH, f"class_b_problem_projections[{index}] status drifted")

    vector = _fixture_vector(fixture)
    if vector is None:
        lint.fail(FIXTURE_PATH, "missing PSI quota blinded denial vector")
        return
    expected = vector.get("expected")
    if not isinstance(expected, dict):
        lint.fail(FIXTURE_PATH, "PSI quota denial vector expected must be an object")
        return
    if expected.get("class_b_problem_schema_ref") != SCHEMA_REF:
        lint.fail(FIXTURE_PATH, "PSI fixture canonical Class B schema_ref drifted")
    fixture_projections = expected.get("class_b_problem_projections")
    policy = expected.get("class_b_problem_maximal_string_projection")
    if not isinstance(fixture_projections, list) or not isinstance(policy, dict):
        lint.fail(FIXTURE_PATH, "PSI fixture missing Class B projections or maximal string policy")
        return
    if tuple(_mapping_projection_tuple(row) for row in fixture_projections) != EXPECTED_PROJECTIONS:
        lint.fail(FIXTURE_PATH, "PSI fixture Class B phase/code projection set or order drifted")
    if expected.get("class_b_problem_negative_schema_mutations") != list(NEGATIVE_MUTATIONS):
        lint.fail(FIXTURE_PATH, "PSI Class B negative schema mutation matrix drifted")

    validator = _problem_validator(schema)
    first_problem: dict[str, Any] | None = None
    for index, projection in enumerate(fixture_projections):
        if not isinstance(projection, dict):
            lint.fail(FIXTURE_PATH, f"class_b_problem_projections[{index}] must be an object")
            continue
        code = projection.get("error_code")
        triple = ERROR_TRIPLES.get(code)
        if triple is None:
            lint.fail(FIXTURE_PATH, f"class_b_problem_projections[{index}] has unknown code")
            continue
        if (projection.get("type"), projection.get("title"), projection.get("status")) != triple:
            lint.fail(FIXTURE_PATH, f"class_b_problem_projections[{index}] canonical triple drifted")
        try:
            problem = _maximal_problem(projection, policy)
        except (TypeError, ValueError) as exc:
            lint.fail(FIXTURE_PATH, f"invalid maximal PSI problem projection: {exc}")
            return
        errors = sorted(validator.iter_errors(problem), key=lambda error: list(error.path))
        if errors:
            lint.fail(FIXTURE_PATH, f"class_b_problem_projections[{index}] schema-invalid: {errors[0].message}")
        if first_problem is None:
            first_problem = problem
        body_size = _canonical_json_size(problem)
        minimal_bucket = next((bucket for bucket in BUCKETS if body_size <= bucket), None)
        if projection.get("minimal_bucket_bytes") != minimal_bucket:
            lint.fail(
                FIXTURE_PATH,
                f"class_b_problem_projections[{index}] minimal bucket drifted: body={body_size}",
            )

    if first_problem is not None:
        for name, mutated in _negative_instances(first_problem).items():
            if not list(validator.iter_errors(mutated)):
                lint.fail(SCHEMA_PATH, f"psi_padded_problem accepted negative mutation {name}")

    validation_cases = {
        row.get("name"): row
        for row in schema_validation_fixture.get("schema_validation_cases", [])
        if isinstance(row, dict) and isinstance(row.get("name"), str)
    }
    for name, expect_valid in SCHEMA_VALIDATION_CASES.items():
        case = validation_cases.get(name)
        if not isinstance(case, dict):
            lint.fail(SCHEMA_VALIDATION_FIXTURE_PATH, f"missing canonical PSI case {name}")
            continue
        if case.get("schema_ref") != SCHEMA_REF or case.get("expect_valid") is not expect_valid:
            lint.fail(SCHEMA_VALIDATION_FIXTURE_PATH, f"canonical PSI case {name} drifted")

    _check_openapi(lint)
