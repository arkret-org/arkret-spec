"""Mutation test for the accountability string-set descriptor lint boundary."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class AccountabilityScopeDescriptorLintTest(unittest.TestCase):
    def test_descriptor_and_schema_mutations_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            sandbox = Path(temporary_directory) / "arkret-spec"
            shutil.copytree(
                ROOT,
                sandbox,
                ignore=shutil.ignore_patterns(".git", "target", "__pycache__"),
            )

            schema_path = (
                sandbox
                / "spec"
                / "v1"
                / "artifacts"
                / "schemas"
                / "accountability-grant.schema.json"
            )
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            array_variant = schema["properties"]["accountability_scope"]["oneOf"][1]
            del array_variant["minItems"]
            del array_variant["uniqueItems"]
            array_variant["items"] = {"type": "string", "enum": ["employment"]}
            schema_path.write_text(
                json.dumps(schema, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            registry_path = (
                sandbox
                / "spec"
                / "v1"
                / "artifacts"
                / "registry"
                / "event-kind-registry.json"
            )
            registry = json.loads(registry_path.read_text(encoding="utf-8"))
            row = next(
                row
                for row in registry["event_kinds"]
                if row["event_kind"] == "ak.identity.accountability_grant"
            )
            components = row["cell_writes"][0]["cell_subject"]["components"]
            components[2]["unexpected"] = True
            components.append(
                {
                    "kind": "unknown_component",
                    "field": "payload.accountability_scope",
                }
            )
            registry_path.write_text(
                json.dumps(registry, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(sandbox / "tools" / "lint_artifacts.py")],
                cwd=sandbox,
                capture_output=True,
                check=False,
                text=True,
                encoding="utf-8",
            )
            diagnostics = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0)
            for expected in (
                "unknown member(s) ['unexpected']",
                ".kind must be 'select'",
                "array schema must declare minItems >= 1",
                "array schema must declare uniqueItems: true",
                "string and array item variants must share one element schema",
            ):
                self.assertIn(expected, diagnostics)

        lint_source = (ROOT / "tools" / "lint_artifacts.py").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("finding 09", lint_source.lower())


if __name__ == "__main__":
    unittest.main()
