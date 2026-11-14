"""Executable grant-lineage and active Reaction state conformance."""

from __future__ import annotations

import copy
import json

from tools.generate_reaction_current_fixture import (
    ANCHOR, REALM, STREAM, TARGET, VECTOR, apply, build_fixture, jcs, revision,
    sign_snapshot, typed_id,
)
from tools.grant_lineage import run_case as run_grant_case
from tools.regenerate_detached_object_signature_kat import KEY_A_SEED, OLD_VM, make_signature
from .call_current import schema_validator, verify_detached, verify_producer
from .core import ARTIFACTS, Lint, load_contract_json, load_json

GRANT_FIXTURE = ARTIFACTS / "fixtures/grant-lineage-lifetime-fixture.json"
REACTION_FIXTURE = ARTIFACTS / "fixtures/reaction-authority-order-fixture.json"
PROJECTION = {"kind": "set", "value_projection": {"kind": "object", "members": [
    {"name": "entries", "derivation": "reaction_effective_entries"}]}}


def verified_row(row, keys):
    """Cryptographic checks complement the caller's native authority gates."""
    event, commit = row["event"], row["commit"]
    verify_producer(event, keys["producer_public_key_b64u"])
    verify_detached(commit, "signature", keys["governance_public_key_b64u"], "ak.realm_commit_signature.v1")
    core = {key: value for key, value in commit.items() if key not in {"commit_id", "signature"}}
    if typed_id("realm_commit", core) != commit["commit_id"]:
        raise ValueError("Commit content identity")
    if (commit["event_ref"] != event["event_id"] or commit["stream_ref"] != STREAM
            or event["scope_ref"] != STREAM or event["realm_id"] != REALM
            or commit["realm_id"] != REALM or event["payload"]["target_ref"] != TARGET
            or event["kind"] not in {"ak.reaction.add", "ak.reaction.remove"}):
        raise ValueError("exact source and target")


class ReactionReference:
    """Station-side ordered current; this is not a client history reducer."""

    def __init__(self, keys, *, complete=True):
        self.keys = keys
        self.complete = complete
        self.checkpoint, self.head = 0, ANCHOR
        self.entries, self.current_revision, self.pending = [], None, {}
        self.known = {0: ANCHOR}

    def receive(self, row):
        verified_row(row, self.keys)
        commit = row["commit"]
        position = commit["stream_position"]
        if position in self.known and self.known[position] != commit["commit_id"]:
            raise ValueError("known position equivocation")
        if position <= self.checkpoint:
            return "ignore"
        if not self.complete:
            raise ValueError("partial baseline")
        if position > self.checkpoint + 1:
            if position in self.pending and self.pending[position] != row:
                raise ValueError("buffered equivocation")
            self.pending[position] = copy.deepcopy(row)
            return "buffer"
        self._next(row)
        while self.checkpoint + 1 in self.pending:
            self._next(self.pending.pop(self.checkpoint + 1))
        return "accept"

    def _next(self, row):
        commit = row["commit"]
        if commit["stream_position"] != self.checkpoint + 1 or commit["previous_commit_ref"] != self.head:
            raise ValueError("stream continuity")
        self.entries = apply(self.entries, row)
        self.current_revision = revision(commit)
        self.checkpoint, self.head = commit["stream_position"], commit["commit_id"]
        self.known[self.checkpoint] = self.head

    def historical_read(self, row, readable_floor):
        verified_row(row, self.keys)
        if row["commit"]["stream_position"] < readable_floor:
            raise ValueError("history floor")
        return copy.deepcopy(row)

    def install(self, snapshot):
        verify_detached(snapshot, "signature", self.keys["governance_public_key_b64u"], "ak.realm_snapshot_signature.v1")
        unsigned = {key: value for key, value in snapshot.items() if key not in {"snapshot_id", "signature"}}
        if typed_id("realm_snapshot", unsigned) != snapshot["snapshot_id"]:
            raise ValueError("Snapshot content identity")
        if snapshot["purpose"] != "full_recovery" or snapshot["realm_id"] != REALM:
            raise ValueError("complete scoped baseline required")
        heads = [head for head in snapshot["visible_stream_heads"] if head["stream_ref"] == STREAM]
        rows = [row for row in snapshot["current_state_entries"]
                if row["selector"] == {"kind": "message_reactions", "target_ref": TARGET}]
        if len(heads) != 1 or len(rows) != 1:
            raise ValueError("complete exact target current")
        head, current = heads[0], rows[0]
        if head["stream_position"] < self.checkpoint:
            raise ValueError("checkpoint rollback")
        if head["stream_position"] == self.checkpoint and head["commit_id"] != self.head:
            raise ValueError("checkpoint equivocation")
        if current["source_stream_ref"] != STREAM or current["revision"]["stream_position"] > head["stream_position"]:
            raise ValueError("row source bounds")
        entries = current["value"]["entries"]
        if set(current["value"]) != {"entries"}:
            raise ValueError("closed active value")
        seen, order = set(), []
        for entry in entries:
            if set(entry) != {"actor_id", "key", "source"}:
                raise ValueError("closed active entry")
            key = (jcs(entry["actor_id"]), entry["key"].encode("utf-8"))
            source = entry["source"]
            if key in seen or source["stream_ref"] != STREAM or source["stream_position"] > current["revision"]["stream_position"]:
                raise ValueError("unique actor/key and qualified source")
            seen.add(key)
            order.append(key)
        if order != sorted(order):
            raise ValueError("canonical entry order")
        if self.current_revision is not None:
            prior, incoming = self.current_revision, current["revision"]
            if incoming["stream_position"] < prior["stream_position"]:
                raise ValueError("current revision rollback")
            if ((incoming["stream_position"] == prior["stream_position"])
                    != (incoming["commit_id"] == prior["commit_id"])):
                raise ValueError("current revision equivocation")
            if incoming == prior and self.entries != entries:
                raise ValueError("same revision different value")
        self.entries = copy.deepcopy(entries)
        self.current_revision = copy.deepcopy(current["revision"])
        self.checkpoint, self.head = head["stream_position"], head["commit_id"]
        self.known[self.checkpoint] = self.head
        self.complete, self.pending = True, {}


def run_reaction_case(fixture, name):
    rows = copy.deepcopy(fixture["original_rows"])
    keys = fixture["test_keys"]
    model = ReactionReference(keys)
    snapshot = copy.deepcopy(fixture["checkpoints"][-1])
    try:
        if name == "complete_ordered_tail":
            for row in rows:
                model.receive(row)
            return "accept" if model.entries == [] and model.checkpoint == 6 else "reject"
        if name == "remove_keeps_empty_row":
            model.install(snapshot)
            return "accept" if not model.entries and model.current_revision == revision(rows[-1]["commit"]) else "reject"
        if name == "snapshot_then_tail":
            model.install(fixture["checkpoints"][3])
            for row in rows[4:]:
                model.receive(row)
            return "accept" if not model.entries else "reject"
        if name == "old_add_after_empty_cut":
            model.install(snapshot)
            return model.receive(rows[3])
        if name == "gap_before_remove":
            model.install(fixture["checkpoints"][3])
            outcome = model.receive(rows[5])
            if model.checkpoint != 4 or len(model.entries) != 2:
                return "reject"
            model.receive(rows[4])
            return outcome if model.checkpoint == 6 and not model.entries else "reject"
        if name == "same_position_equivocation":
            model.install(snapshot)
            core = {key: value for key, value in rows[-1]["commit"].items() if key not in {"commit_id", "signature"}}
            core["committed_at"] = "2026-11-14T00:00:01.000Z"
            commit = {"commit_id": typed_id("realm_commit", core), **core}
            commit["signature"], _ = make_signature("ak.realm_commit_signature.v1", commit, OLD_VM, KEY_A_SEED)
            return model.receive({"event": rows[-1]["event"], "commit": commit})
        if name == "producer_signature_tampered":
            rows[0]["event"]["payload"]["key"] = "wrong"
            return model.receive(rows[0])
        if name == "commit_signature_tampered":
            rows[0]["commit"]["committed_at"] = "2026-11-14T00:00:01.000Z"
            return model.receive(rows[0])
        if name == "snapshot_value_tampered":
            snapshot["current_state_entries"][0]["value"]["entries"] = fixture["checkpoints"][0]["current_state_entries"][0]["value"]["entries"]
            model.install(snapshot)
        elif name in {"duplicate_actor_key", "source_from_other_stream", "source_after_row_revision"}:
            snapshot = copy.deepcopy(fixture["checkpoints"][3])
            entries = snapshot["current_state_entries"][0]["value"]["entries"]
            if name == "duplicate_actor_key":
                entries[1]["actor_id"] = copy.deepcopy(entries[0]["actor_id"])
            elif name == "source_from_other_stream":
                entries[0]["source"]["stream_ref"]["realm_id"] = typed_id("realm", {"fixture": "wrong"})
            else:
                entries[0]["source"]["stream_position"] = 99
            model.install(sign_snapshot(snapshot))
        elif name == "partial_snapshot_not_installed":
            snapshot["purpose"] = "stream_history"
            model.install(sign_snapshot(snapshot))
        elif name == "history_scan_read_only":
            model.install(snapshot)
            before = copy.deepcopy(model.__dict__)
            model.historical_read(rows[3], 4)
            return "accept" if model.__dict__ == before else "reject"
        elif name == "same_principal_other_station":
            model.install(fixture["checkpoints"][3])
            return "accept" if len(model.entries) == 2 else "reject"
        elif name == "no_tombstone_or_payload_in_current":
            for current in fixture["checkpoints"]:
                model.install(current)
            return "accept" if model.entries == [] else "reject"
        elif name in {"floor_does_not_require_old_event", "nested_source_is_not_read_permission"}:
            model.install(fixture["checkpoints"][3])
            sources = [entry["source"]["stream_position"] for entry in model.entries]
            return "accept" if min(sources) < 4 and all(set(entry) == {"actor_id", "key", "source"} for entry in model.entries) else "reject"
        else:
            raise ValueError("unknown reference case")
    except Exception as exc:
        from cryptography.exceptions import InvalidSignature
        if isinstance(exc, (ValueError, KeyError, TypeError, InvalidSignature)):
            return "reject"
        raise
    return "reject"


def check_grant_reaction(lint: Lint):
    try:
        grant = load_json(lint, GRANT_FIXTURE)
        for case in grant["cases"]:
            actual = run_grant_case(case)
            if actual != case["expected"]:
                lint.fail(GRANT_FIXTURE, f"{case['name']}: expected {case['expected']}, got {actual}")
        fixture = load_json(lint, REACTION_FIXTURE)
        if fixture != build_fixture():
            raise ValueError("Reaction fixture differs from deterministic crypto output")
        for row in fixture["original_rows"]:
            schema_validator(ARTIFACTS / "schemas/event-envelope.schema.json", "").validate(row["event"])
            schema_validator(ARTIFACTS / "schemas/event-payload.schema.json", "#/$defs/reaction_payload").validate(row["event"]["payload"])
            schema_validator(ARTIFACTS / "schemas/realm-commit.schema.json", "").validate(row["commit"])
            verified_row(row, fixture["test_keys"])
        for snapshot in fixture["checkpoints"]:
            schema_validator(ARTIFACTS / "schemas/realm-state-snapshot.schema.json", "").validate(snapshot)
            ReactionReference(fixture["test_keys"]).install(snapshot)
        for case in fixture["cases"]:
            actual = run_reaction_case(fixture, case["name"])
            if actual != case["expected"]:
                lint.fail(REACTION_FIXTURE, f"{case['name']}: expected {case['expected']}, got {actual}")
        contract = load_contract_json(lint, ARTIFACTS / "registry/contract-registry.json")
        writers = []
        for event in contract["event_kind_registry"]["event_kinds"]:
            for write in event.get("state_writes", []):
                if write["state_family"] == "message_reactions":
                    writers.append(event["event_kind"])
                    if write["state_projection"] != PROJECTION:
                        raise ValueError("Reaction writer is not the registered complete active receiver derivation")
        if sorted(writers) != ["ak.reaction.add", "ak.reaction.remove"]:
            raise ValueError("Reaction writer set")
        if fixture["covers_vectors"] != [VECTOR]:
            raise ValueError("Reaction vector owner")
    except Exception as exc:
        lint.fail(REACTION_FIXTURE, f"grant/Reaction conformance: {getattr(exc, 'message', str(exc))}")
