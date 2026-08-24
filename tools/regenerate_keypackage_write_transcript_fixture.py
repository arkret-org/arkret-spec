"""Recompute the signed KeyPackage write-transcript fixture from its test key.

The fixture's signing input is ``domain || JCS(unsigned_request)``, so any rename
that touches a field name inside ``unsigned_request`` changes the canonical bytes
and invalidates every stored signature. That is not fixture rot to be patched by
hand: the transcript must be re-derived from the published conformance seed so the
stored ``canonical_jcs``, ``signing_input_base64url`` and ``signature`` stay
mutually consistent and independently verifiable.

Usage::

    python tools/regenerate_keypackage_write_transcript_fixture.py
    python tools/regenerate_keypackage_write_transcript_fixture.py --check
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey  # noqa: E402

from tools.artifact_lint.core import canonical_json  # noqa: E402

FIXTURE = ROOT / "spec" / "v1" / "artifacts" / "fixtures" / "keypackage-write-transcript-fixture.json"


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def rebuild(document: dict) -> tuple[dict, list[str]]:
    seed = b64u_decode(document["test_key"]["private_key_seed"])
    signing_key = Ed25519PrivateKey.from_private_bytes(seed)
    changed: list[str] = []
    consume_request_digest: str | None = None

    for group in ("cases", "negative_cases"):
        for case in document.get(group, []):
            if not isinstance(case, dict) or "unsigned_request" not in case:
                continue
            # Intentionally invalid cases still need current canonical bytes and
            # signing input after a field rename. Preserve only their broken
            # signature so regeneration cannot erase the negative condition.
            preserve_invalid_signature = (
                group == "negative_cases" and case.get("expect_invalid_signature")
            )
            canonical = canonical_json(case["unsigned_request"])
            if case.get("name") == "consume_single_claim":
                consume_request_digest = "sha256:" + hashlib.sha256(
                    canonical.encode("utf-8")
                ).hexdigest()
            signing_input = case["domain"].encode("utf-8") + canonical.encode("utf-8")
            signature = b64u(signing_key.sign(signing_input))
            before = (
                case.get("canonical_jcs"),
                case.get("signing_input_base64url"),
                case.get("signature"),
            )
            after = (
                canonical,
                b64u(signing_input),
                case.get("signature") if preserve_invalid_signature else signature,
            )
            if before != after:
                changed.append(case.get("name", "<unnamed>"))
            if "canonical_jcs" in case:
                case["canonical_jcs"] = canonical
            if "signing_input_base64url" in case:
                case["signing_input_base64url"] = b64u(signing_input)
            if "signature" in case and not preserve_invalid_signature:
                case["signature"] = signature

    for case in document.get("cases", []):
        if not isinstance(case, dict) or "signed_receipt" not in case:
            continue
        receipt = case["signed_receipt"]
        if consume_request_digest is not None:
            receipt["request_digest"] = consume_request_digest
        unsigned_receipt = dict(receipt)
        unsigned_receipt.pop("signature", None)
        canonical = canonical_json(unsigned_receipt)
        signing_input = case["domain"].encode("utf-8") + canonical.encode("utf-8")
        signature = b64u(signing_key.sign(signing_input))
        before = (
            case.get("canonical_jcs"),
            case.get("signing_input_base64url"),
            case.get("signature"),
            receipt.get("signature", {}).get("sig"),
        )
        after = (canonical, b64u(signing_input), signature, signature)
        if before != after:
            changed.append(case.get("name", "<unnamed>"))
        case["canonical_jcs"] = canonical
        case["signing_input_base64url"] = b64u(signing_input)
        case["signature"] = signature
        receipt["signature"]["sig"] = signature
    return document, changed


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="fail instead of writing")
    args = parser.parse_args(argv)

    document = json.loads(FIXTURE.read_text(encoding="utf-8"))
    document, changed = rebuild(document)

    if args.check:
        if changed:
            print(f"transcript fixture is stale: {changed}", file=sys.stderr)
            return 1
        print("transcript fixture is current")
        return 0

    FIXTURE.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(f"regenerated {len(changed)} case(s): {changed}" if changed else "no change")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
