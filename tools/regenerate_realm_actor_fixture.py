"""Generate or check Realm actor signing-byte KATs."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.realm_actor_contract import ART, signature_fixture

path = ART / "fixtures/realm-actor-signature-kat-fixture.json"
expected = json.dumps(signature_fixture(), ensure_ascii=False, indent=2) + "\n"
if "--check" in sys.argv:
    if not path.exists() or path.read_text(encoding="utf-8") != expected:
        raise SystemExit("Realm actor KAT drift")
else:
    path.write_text(expected, encoding="utf-8", newline="\n")
