"""Realm claim handoff signature KAT; synthetic ledger digests, not SUT admission."""
import base64
import copy
import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from tools.artifact_lint.mls_roster_client_roles import signing_bytes

ART = Path(__file__).resolve().parents[1] / "spec/v1/artifacts"
CLAIM_DOMAIN = "ak.peer-keypackage-claim-receipt-v1\n"
ADD_DOMAIN = "ak.mls_add_authority_attestation.v1\n"

def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")

def sign(value, seed, kid, domain):
    key = Ed25519PrivateKey.from_private_bytes(bytes([seed]) * 32)
    value["signature"] = {"kid": kid, "signature_algorithm": "Ed25519", "signature": ""}
    value["signature"]["signature"] = b64(key.sign(signing_bytes(value, domain)))
    return {"verification_method": kid, "public_key_base64url": b64(key.public_key().public_bytes_raw())}

def handoff_fixture():
    template = json.loads((ART / "fixtures/mls-roster-client-roles-fixture.json").read_text(encoding="utf-8"))["signature_binding_kat"]
    claim = copy.deepcopy(template["claim_receipt"])
    add = copy.deepcopy(template["attestation"])
    actor = {"kind": "realm", "realm_actor_id": {"realm_id": add["realm_id"], "principal_id": "ak:did_core:webvh:zRealmActorFixture"}}
    del claim["request"]["target_account_id"]
    claim["request"]["target_actor_id"] = actor
    claim["source_id"] = claim["destination_id"] = "ak:did_core:web:old-governor.example"
    claim["claim_authority_ref"] = add["genesis_event_ref"]
    claim_key = sign(claim, 71, "did:web:old-governor.example#claim", CLAIM_DOMAIN)
    add.update(actor_id=actor, attestor_station_id="ak:did_core:web:new-governor.example", claim_receipt=claim,
               claim_authority_ref=claim["claim_authority_ref"])
    add_key = sign(add, 72, "did:web:new-governor.example#add", ADD_DOMAIN)
    return {"description": "Independent real Ed25519 signatures over closed claim and Add hosts. Ledger digests and governance refs are synthetic; no native method history, live handoff, actual claim or RFC MLS admission is asserted.",
            "claim_receipt": claim, "attestation": add,
            "claim_receipt_signing_key": claim_key, "attestation_signing_key": add_key,
            "required_scenarios": ["RA-CLAIM-1"] + [f"RA-HANDOFF-{i}" for i in range(1, 7)]}

class ClaimContinuationModel:
    """Ledger-only model with externally verified governance cuts as input.

    This deliberately does not claim to verify method history or handoff signatures.
    Production must obtain these cuts from its real authority verifier and imports.
    """
    def __init__(self, actor, issuer, authority_ref, expires_at):
        self.actor = copy.deepcopy(actor)
        self.issuer = issuer
        self.authority_ref = authority_ref
        self.governor = issuer
        self.expires_at = expires_at
        self.generation = 1
        self.frozen = False
        self.inventory = {"claim": {"actor": actor, "issuer": issuer, "authority_ref": authority_ref},
                          "method_history": {"issuer": issuer}, "welcome": None, "outcome": None}

    def transfer(self, next_governor, verified_predecessor, imported):
        if not self.frozen or verified_predecessor != self.governor or imported != self.inventory:
            return False
        self.governor = next_governor
        self.frozen = False
        return True

    def consume(self, destination, actor, generation, historical_recipient, now, request, receipt,
                authenticated=True, authorized=True):
        if self.frozen or destination != self.governor or not authenticated or not authorized or actor != self.actor:
            return False
        if self.inventory["outcome"] is not None:
            previous = self.inventory["outcome"]
            return previous["receipt"] if request == previous["request"] else False
        if generation != self.generation or historical_recipient != self.issuer or now >= self.expires_at or self.inventory["welcome"] is None:
            return False
        self.inventory["outcome"] = {"request": request, "receipt": receipt}
        return receipt
