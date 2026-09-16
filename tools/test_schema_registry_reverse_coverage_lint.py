"""Reverse closure between artifacts/schemas and the schema registry (ruling 2026-09-05-0245).

The forward check proves every registry row points at an existing file. A
renamed or newly added schema file that no row names still has a `$id` and a
`$ref` audience, but no `schema_id`, so registry-walking consumers never see
it; three such files shipped before this gate existed. The test pins that an
unregistered file fails and that the shipped tree is clean.
"""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import foundation
from tools.artifact_lint.core import Lint

SCHEMAS = ROOT / "spec" / "v1" / "artifacts" / "schemas"
SCHEMA_REGISTRY = ROOT / "spec" / "v1" / "artifacts" / "registry" / "schema-registry.json"


def _registered_files() -> set[str]:
    registry = json.loads(SCHEMA_REGISTRY.read_text(encoding="utf-8"))
    return {row["file"] for row in registry["schemas"]}


class SchemaRegistryReverseCoverageTest(unittest.TestCase):
    def test_every_schema_file_has_a_registry_row(self) -> None:
        registered = _registered_files()
        missing = sorted(
            f"schemas/{path.name}"
            for path in SCHEMAS.glob("*.schema.json")
            if f"schemas/{path.name}" not in registered
        )
        self.assertEqual(missing, [])

    def test_previously_unregistered_files_now_have_rows(self) -> None:
        registered = _registered_files()
        for name in (
            "schemas/presence-preference.schema.json",
            "schemas/presence-visibility.schema.json",
        ):
            self.assertIn(name, registered)

    def test_unregistered_schema_file_fails_the_gate(self) -> None:
        stray = SCHEMAS / "zz-reverse-coverage-probe.schema.json"
        self.assertFalse(stray.exists())
        stray.write_text('{"$schema": "https://json-schema.org/draft/2020-12/schema", "type": "object"}\n', encoding="utf-8")
        try:
            lint = Lint()
            foundation.check_registries(lint)
            errors = [str(error) for error in lint.errors]
        finally:
            stray.unlink()
        self.assertTrue(
            any("zz-reverse-coverage-probe.schema.json" in error and "no schema-registry row" in error for error in errors),
            errors,
        )

    def test_shipped_registry_passes_the_gate(self) -> None:
        lint = Lint()
        foundation.check_registries(lint)
        errors = [str(error) for error in lint.errors if "no schema-registry row" in str(error)]
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
