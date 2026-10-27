"""Erasure target references retain canonical principal identity in both carriers."""
import json
import unittest
from pathlib import Path
from jsonschema import Draft202012Validator
from referencing import Registry, Resource

ROOT=Path(__file__).resolve().parents[1]

class ErasureReferenceSchemaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        documents=[json.loads(p.read_text(encoding="utf-8")) for p in (ROOT/"spec/v1/artifacts/schemas").glob("*.json")]
        cls.registry=Registry().with_resources((x["$id"],Resource.from_contents(x)) for x in documents)

    def validator(self,fragment):
        return Draft202012Validator({"$ref":"https://arkret.org/v1/schemas/erasure-verification-stub.schema.json#/$defs/"+fragment},registry=self.registry)

    def test_principal_subject_and_target_reuse_the_same_core_identity(self):
        for principal in ["ak:did_core:web:alice.example","ak:did_core:webvh:QmTnpRaadxso9gmuqCaoT54ib4kWKNt1F5UuqXN6i5hwey"]:
            self.validator("subject").validate({"kind":"principal","subject_ref":principal})
            self.validator("scope").validate({"storage_boundary":"account_private_store","target_refs":[principal]})
            self.validator("subject_ref").validate(principal)


    def test_digest_subject_and_target_share_both_registered_algorithms(self):
        for algorithm in ["sha256", "blake3"]:
            reference=algorithm+":"+"09"*32
            self.validator("subject").validate({"kind":"account_private_state","subject_ref":reference})
            self.validator("subject_ref").validate(reference)
            self.validator("scope").validate({"storage_boundary":"account_private_store","target_refs":[reference]})
        self.assertFalse(self.validator("subject_ref").is_valid("sha512:"+"09"*64))

    def test_blocked_legal_hold_requires_a_non_null_reference(self):
        # Closed conditional shape only; this is not evidence of a legal hold.
        schema=json.loads((ROOT/"spec/v1/artifacts/schemas/erasure-receipt.schema.json").read_text(encoding="utf-8"))
        conditional=Draft202012Validator(schema["allOf"][0],registry=self.registry)
        for document in [{"outcome":"blocked_by_legal_hold"},{"outcome":"blocked_by_legal_hold","legal_hold_ref":None}]:
            self.assertFalse(conditional.is_valid(document))
        conditional.validate({"outcome":"blocked_by_legal_hold","legal_hold_ref":"ak:policy:01964137-0000-7000-8000-000000000001"})

    def test_invalid_and_duplicate_targets_remain_closed(self):
        for target in ["", "ak:did_core:", "arbitrary-private-string", "ak:realm:invalid"]:
            self.assertFalse(self.validator("subject_ref").is_valid(target),target)
        self.assertFalse(self.validator("scope").is_valid({"storage_boundary":"account_private_store","target_refs":["ak:did_core:web:alice.example"]*2}))
        self.assertFalse(self.validator("subject").is_valid({"kind":"principal","subject_ref":"did:web:alice.example"}))

    def test_event_commit_reference_has_one_closed_canonical_shape(self):
        import base64
        token=base64.urlsafe_b64encode(bytes([1])+bytes([9])*32).decode().rstrip("=")
        event="ak:event:"+token
        document={"stub_schema":"ak.schema.erasure_verification_stub.v1",
                  "subject":{"kind":"event","subject_ref":event},
                  "scope":{"storage_boundary":"canonical_log_minimization"},
                  "receipt_id":"ak:receipt:01964137-0000-7000-8000-000000000001",
                  "trigger":{"kind":"event","event_id":event},
                  "completed_at":"2026-10-26T00:00:00.000Z",
                  "committed_event_ref":{"event_id":event,"commit_id":"ak:realm_commit:"+token,
                    "stream_ref":{"kind":"realm","realm_id":"ak:realm:"+token},"stream_position":0}}
        validator=Draft202012Validator({"$ref":"https://arkret.org/v1/schemas/erasure-verification-stub.schema.json"},registry=self.registry)
        validator.validate(document)
        from copy import deepcopy
        for key in ["commit_inclusion","commit_ref"]:
            bad=deepcopy(document)
            bad[key]=bad.pop("committed_event_ref")
            self.assertFalse(validator.is_valid(bad),key)
        for incomplete in [{},{"commit_id":"ak:realm_commit:"+token}]:
            bad=deepcopy(document)
            bad["committed_event_ref"]=incomplete
            self.assertFalse(validator.is_valid(bad))
        bad=deepcopy(document)
        bad["subject"]={"kind":"principal","subject_ref":"ak:did_core:web:alice.example"}
        self.assertFalse(validator.is_valid(bad))

if __name__=="__main__":unittest.main()
