from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from tools.release_tool_manifest import MANIFEST_PATH, load_manifest, registered_runners


class ReleaseToolManifestTest(unittest.TestCase):
    def test_live_manifest_is_closed_and_every_owner_exists(self) -> None:
        body = load_manifest()

        self.assertRegex(body["version"], r"^\d{4}-\d{2}-\d{2}(?:\.\d+)?$")
        self.assertEqual(body["pipelines"]["release_default"], ["artifact_pipeline", "crossref"])
        self.assertEqual(
            body["pipelines"]["release_strict"],
            ["artifact_pipeline", "crossref", "strict_spec_lint"],
        )
        self.assertEqual(len(body["pipelines"]["artifact_check"]), 31)

    def test_missing_owner_script_is_rejected(self) -> None:
        body = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
        body["checks"][0]["owner_script"] = "tools/missing.py"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "tools/release-tool-manifest.json"
            path.parent.mkdir(parents=True)
            path.write_text(json.dumps(body), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "owner script does not exist"):
                load_manifest(path, root)

    def test_runner_not_registered_by_the_manifest_is_rejected(self) -> None:
        body = load_manifest()
        runners = {check_id: (lambda: 0) for check_id in body["pipelines"]["artifact_check"]}
        runners["hidden_check"] = lambda: 0

        with self.assertRaisesRegex(ValueError, r"unregistered=\['hidden_check'\]"):
            registered_runners("artifact_check", runners, manifest=body)

    def test_registered_check_without_a_runner_is_rejected(self) -> None:
        body = load_manifest()
        runners = {check_id: (lambda: 0) for check_id in body["pipelines"]["artifact_check"]}
        runners.pop("artifact_lint")

        with self.assertRaisesRegex(ValueError, r"missing=\['artifact_lint'\]"):
            registered_runners("artifact_check", runners, manifest=body)


if __name__ == "__main__":
    unittest.main()
