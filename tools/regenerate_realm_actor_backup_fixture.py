"""Regenerate the fixed-root native content-backup primitive KAT."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.realm_actor_backup_contract import fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    path = ROOT / "spec/v1/artifacts/fixtures/realm-actor-content-backup-fixture.json"
    expected = json.dumps(fixture(), ensure_ascii=False, indent=2) + "\n"
    if args.check:
        if not path.exists() or path.read_text(encoding="utf-8") != expected:
            raise SystemExit("native content-backup KAT drift")
    else:
        path.write_text(expected, encoding="utf-8", newline="\n")


if __name__ == "__main__":
    main()
