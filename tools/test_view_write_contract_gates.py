"""Mutation probes for the View write contract and the member-source closure.

Three gates meet here, and each one exists because the shape it guards had
already gone wrong once.

``_reducer_managed_paths`` read ``reducer-managed-path-registry.json`` by
walking the whole document and collecting every ``path`` key it met into one
flat set. The registry's own ``registry_rules`` describe a *per object* solve:
the universal list restricted to the members that object declares, minus that
object's ``universal_exemptions``, plus its own bans. Reading it flat inverted
the one exemption in the file -- ``state``, carved out for ``ak.view.update``
because ``models/views.md`` section 3.1 gives a shared View no tombstone Event
kind -- into a prohibition, so the single write the spec cannot do without could
not be registered at all. It also merged every object's private bans, so a name
one family reserves was enforced against every other family that happened to
declare it.

``check_result_value_member_closure`` is the other direction. A schema
declaration is not a maintenance rule: ``view_value`` declared ``updated_by``
and ``updated_at``, nothing required any write to produce them, and the create
snapshot happily carried author-supplied values into the family while the update
path had no producer at all. The same hole at create was larger still --
``schema``, ``realm_id``, ``created_by`` and ``created_at`` were author input
that every later write retained verbatim, so a forged creator became the
permanent create-locked truth of the object.

Every probe reads as a delta against the live baseline: the mutation's *new*
errors are asserted, so an unrelated pre-existing failure cannot make a probe
look like it passed.
"""

from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tools.artifact_lint import fixtures as fixture_gate
from tools.artifact_lint import proof_context_schemas as gate

EVENT_KINDS = gate.EVENT_KIND_REGISTRY
REDUCER_PATHS = gate.REDUCER_MANAGED_PATH_REGISTRY

VIEW_UPDATE = "ak.view.update"
VIEW_CREATE = "ak.view.create"
VIEW_RECONCILE = "ak.view.reconcile"


def _row(registry: dict, kind: str) -> dict:
    for row in registry["event_kinds"]:
        if row["event_kind"] == kind:
            return row
    raise AssertionError(f"{kind} is not a registered Event kind")


def _write(registry: dict, kind: str, family: str = "view") -> dict:
    for write in _row(registry, kind).get("result_writes") or ():
        if write.get("result_family") == family:
            return write
    raise AssertionError(f"{kind} declares no write of {family}")


def _object_row(registry: dict, object_kind: str) -> dict:
    for row in registry["objects"]:
        if row["object_kind"] == object_kind:
            return row
    raise AssertionError(f"{object_kind} has no reducer-managed path row")


class _Harness(unittest.TestCase):
    """Run one gate with zero or more registries swapped for mutated copies."""

    check = None

    def _run(self, mutations: dict[Path, object] | None = None) -> list[str]:
        original = gate.load_json
        documents: dict[Path, object] = {}
        for path, mutate in (mutations or {}).items():
            document = copy.deepcopy(original(gate.Lint(), path))
            mutate(document)
            documents[path.resolve()] = document

        def load_json_with_mutation(lint, path):
            return documents.get(path.resolve(), original(lint, path))

        gate.load_json = load_json_with_mutation
        try:
            lint = gate.Lint()
            type(self).check(lint)
            return lint.errors
        finally:
            gate.load_json = original

    def _newly_reported(self, mutations: dict[Path, object]) -> list[str]:
        baseline = set(self._run())
        return sorted(set(self._run(mutations)) - baseline)

    def assertNewFailure(self, mutations: dict[Path, object], fragment: str) -> None:
        reported = self._newly_reported(mutations)
        self.assertTrue(reported, "the mutation reported nothing new")
        self.assertTrue(
            any(fragment in message for message in reported),
            f"no new error mentions {fragment!r}; got {reported}",
        )


class ReducerManagedPathSolveTest(_Harness):
    """The forbidden set is solved per object, from the registry's own rules."""

    check = staticmethod(gate.check_result_write_contracts)

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_removing_the_state_exemption_blocks_the_only_removal_path(self) -> None:
        """This is the flat read's failure mode, reproduced deliberately.

        ``state`` is in ``universal_forbidden_patch_paths`` and View declares it,
        so without the exemption it is forbidden -- and the patch that sets it to
        ``tombstoned`` is the whole protocol-level removal path for a shared
        View. A gate that stays quiet here is a gate that would have let the
        flattening survive.
        """

        def drop_exemption(document: dict) -> None:
            row = _object_row(document, "view")
            row["universal_exemptions"] = [
                item for item in row["universal_exemptions"] if item.get("path") != "state"
            ]

        self.assertNewFailure({REDUCER_PATHS: drop_exemption}, "'state'")

    def test_an_exemption_owned_by_another_kind_does_not_apply(self) -> None:
        """An exemption is a carve-out assigned to one owner, not a relaxation."""

        def reassign_owner(document: dict) -> None:
            for item in _object_row(document, "view")["universal_exemptions"]:
                if item.get("path") == "state":
                    item["owner"] = VIEW_RECONCILE

        self.assertNewFailure({REDUCER_PATHS: reassign_owner}, "'state'")

    def test_another_objects_private_ban_does_not_reach_view(self) -> None:
        """The pollution half of the same bug.

        Under the flat read every object's private bans applied to every family
        that happened to declare a member of the same name. View did not collide
        with any of them, which is the only reason exactly one write was blocked
        rather than several. Give another object a private ban on a name View
        does allow, and View must not notice.
        """

        def ban_title_elsewhere(document: dict) -> None:
            row = _object_row(document, "circle")
            row["forbidden_patch_paths"].append(
                {
                    "path": "title",
                    "basis": "probe",
                    "reason_code": "patch_path_reducer_managed",
                    "owner_kind": "event_kind",
                    "owner": "ak.circle.update",
                    "schema_enforced": False,
                    "description": "probe: a private ban of one object kind",
                }
            )

        self.assertEqual(self._newly_reported({REDUCER_PATHS: ban_title_elsewhere}), [])

    def test_reaching_under_a_banned_path_is_refused(self) -> None:
        """``created_by`` is reducer-managed, so ``created_by.account_id`` is not a way in.

        This projection's grammar is stricter still -- ``allowed_paths`` here are
        top-level member names -- so the dotted spelling is refused one layer
        earlier than the ownership solve. Both layers matter: the registry's own
        forbidden paths MAY be dotted, and the ownership solve is what has to
        cover those.
        """

        def reach_under_a_banned_path(document: dict) -> None:
            write = _write(document, VIEW_UPDATE)
            write["result_projection"]["allowed_paths"].append("created_by.account_id")

        self.assertNewFailure({EVENT_KINDS: reach_under_a_banned_path}, "allowed_paths")

    def test_a_banned_path_covers_its_descendants_and_not_its_namesakes(self) -> None:
        """The subtree test is a dotted-prefix test, not a substring test."""

        forbidden = {"created_by", "layout.columns"}
        self.assertTrue(gate._names_a_forbidden_path("created_by", forbidden))
        self.assertTrue(gate._names_a_forbidden_path("created_by.account_id", forbidden))
        self.assertTrue(
            gate._names_a_forbidden_path("layout.columns.width", forbidden)
        )
        self.assertFalse(gate._names_a_forbidden_path("created_byte", forbidden))
        self.assertFalse(gate._names_a_forbidden_path("layout", forbidden))

    def test_a_write_without_a_value_schema_cannot_resolve_its_target(self) -> None:
        """No fallback to a flat set, and no fallback to an empty one.

        Both fallbacks are silent in opposite directions: a flat set forbids
        names this object never reserved, an empty set forbids nothing at all.
        """

        def drop_the_value_schema(document: dict) -> None:
            _write(document, VIEW_UPDATE).pop("value_schema_ref")

        self.assertNewFailure({EVENT_KINDS: drop_the_value_schema}, "value_schema_ref")

    def test_the_family_and_the_value_schema_must_agree(self) -> None:
        def disagree(document: dict) -> None:
            _object_row(document, "view")["result_family"] = "realm_profile"

        self.assertNewFailure({REDUCER_PATHS: disagree}, "result_family")


class ValueMemberClosureTest(_Harness):
    """Every member of a covered value has a source on every write."""

    check = staticmethod(gate.check_result_value_member_closure)

    def test_the_live_registry_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_a_write_that_stops_maintaining_update_metadata_turns_red(self) -> None:
        """``always_maintained`` is what a required-members rule cannot say.

        ``updated_by`` is optional in the value schema, so a required-member
        accounting would never ask for it. Dropping its producer from one write
        leaves a family where the member is set once at create and then points
        at the wrong Actor after every later write -- while every other gate
        stays green.
        """

        def drop_the_producer(document: dict) -> None:
            write = _write(document, VIEW_RECONCILE)
            write["derived_members"] = [
                item for item in write["derived_members"] if item.get("name") != "updated_by"
            ]

        self.assertNewFailure({EVENT_KINDS: drop_the_producer}, "updated_by")

    def test_an_unregistered_kind_may_not_produce_the_transition_time(self) -> None:
        """``state_changed_at`` belongs to the one registered transition carrier."""

        def add_a_second_producer(document: dict) -> None:
            _write(document, VIEW_RECONCILE)["derived_members"].append(
                {"name": "state_changed_at", "derivation": "object_state_transition_time"}
            )

        self.assertNewFailure({EVENT_KINDS: add_a_second_producer}, "state_changed_at")

    def test_the_create_author_region_may_not_reach_a_create_locked_member(self) -> None:
        """The whole-value spelling of the forgery the patch surface refuses.

        The author region used to be the materialized View minus four banned
        members, which still declared ``created_by``. A prose sentence asked
        semantic validation to cross-check it against the envelope; a prose
        sentence is not a gate, and every later write retained whatever value
        arrived.
        """

        def hand_the_author_the_creator(document: dict) -> None:
            definition = document["$defs"]["view_definition"]
            definition["properties"]["created_by"] = {"$ref": "#/properties/created_by"}

        view_schema = gate.ARTIFACTS / "schemas" / "view.schema.json"
        self.assertNewFailure({view_schema: hand_the_author_the_creator}, "created_by")

    def test_a_later_write_may_not_re_derive_a_create_locked_member(self) -> None:
        def re_derive_at_update(document: dict) -> None:
            write = _write(document, VIEW_UPDATE)
            write["retained_members"] = [
                name for name in write["retained_members"] if name != "created_at"
            ]
            write["derived_members"].append(
                {"name": "created_at", "derivation": "object_create_time"}
            )

        self.assertNewFailure({EVENT_KINDS: re_derive_at_update}, "created_at")

    def test_a_later_write_must_carry_a_create_locked_member(self) -> None:
        """Dropping the retention is not "the member is optional here".

        The value schema requires ``created_at``, and the update projection is a
        patch that cannot reach it, so a write that neither retains nor derives
        it describes a result the reducer cannot produce.
        """

        def stop_retaining(document: dict) -> None:
            write = _write(document, VIEW_UPDATE)
            write["retained_members"] = [
                name for name in write["retained_members"] if name != "created_at"
            ]

        self.assertNewFailure({EVENT_KINDS: stop_retaining}, "created_at")

    def test_a_member_may_not_hold_two_roles_on_one_write(self) -> None:
        def derive_and_retain(document: dict) -> None:
            _write(document, VIEW_UPDATE)["retained_members"].append("updated_by")

        self.assertNewFailure({EVENT_KINDS: derive_and_retain}, "updated_by")

    def test_a_declared_maintenance_rule_needs_a_value_schema(self) -> None:
        """The coverage frontier is declared, so it cannot be widened silently."""

        def declare_maintenance_without_a_value(document: dict) -> None:
            row = _object_row(document, "view")
            row.pop("value_schema_ref")
            row["value_schema_open_gap_owner"] = "probe"

        self.assertNewFailure(
            {REDUCER_PATHS: declare_maintenance_without_a_value}, "value_schema_ref"
        )


class ViewWriteContractFixtureTest(unittest.TestCase):
    """The vector's two faces, and the trap between them.

    ``cases[]`` proves shapes, ``admission_cases[]`` proves outcomes. The trap
    is that a patch map's KEYS are its paths, so ``{"set": {"state":
    "tombstoned"}}`` validates against ``patch.schema.json`` -- as a patch
    setting a member literally named ``set``. A fixture written that way would
    report "the removal patch is accepted" while carrying a patch no reducer
    may apply, and every other gate would stay green.
    """

    FIXTURE = fixture_gate.ARTIFACTS / "fixtures" / "view-write-contract-fixture.json"

    def _run(self, mutate=None) -> list[str]:
        original = fixture_gate.load_json
        document = None
        if mutate is not None:
            document = copy.deepcopy(original(fixture_gate.Lint(), self.FIXTURE))
            mutate(document)

        def load_json_with_mutation(lint, path):
            if document is not None and Path(path).resolve() == self.FIXTURE.resolve():
                return document
            return original(lint, path)

        fixture_gate.load_json = load_json_with_mutation
        try:
            lint = fixture_gate.Lint()
            fixture_gate.check_view_write_contract_fixture(lint)
            return lint.errors
        finally:
            fixture_gate.load_json = original

    def assertNewFailure(self, mutate, fragment: str) -> None:
        baseline = set(self._run())
        reported = sorted(set(self._run(mutate)) - baseline)
        self.assertTrue(reported, "the mutation reported nothing new")
        self.assertTrue(
            any(fragment in message for message in reported),
            f"no new error mentions {fragment!r}; got {reported}",
        )

    def _case(self, document: dict, name: str, key: str = "cases") -> dict:
        for case in document[key]:
            if case.get("name") == name:
                return case
        raise AssertionError(f"{key} has no case named {name}")

    def test_the_live_fixture_is_clean(self) -> None:
        self.assertEqual(self._run(), [])

    def test_an_accepted_patch_may_not_address_a_non_member(self) -> None:
        """The ``{"set": {...}}`` wrapper, reproduced deliberately.

        It is schema-valid, which is the whole problem: only a check that reads
        the patch map's keys as paths can tell this apart from the real removal
        patch.
        """

        def wrap_the_patch(document: dict) -> None:
            case = self._case(document, "terminal_state_patch_is_accepted")
            case["instance"]["patch"] = {"set": {"state": "tombstoned"}}

        self.assertNewFailure(wrap_the_patch, "'set'")

    def test_an_admitted_case_may_not_patch_a_reducer_managed_member(self) -> None:
        def admit_a_forbidden_path(document: dict) -> None:
            case = self._case(document, "legal_active_to_tombstoned_is_admitted", "admission_cases")
            case["payload"]["patch"] = {"created_by": {"kind": "account"}}

        self.assertNewFailure(admit_a_forbidden_path, "created_by")

    def test_a_refusal_must_name_a_registered_error_code(self) -> None:
        """A refusal that invents its own spelling is a second error vocabulary."""

        def invent_a_code(document: dict) -> None:
            case = self._case(
                document, "an_update_after_the_terminal_transition_is_refused", "admission_cases"
            )
            case["expected"]["error"] = "view_is_gone"

        self.assertNewFailure(invent_a_code, "view_is_gone")

    def test_a_refusal_must_name_a_registered_reason_code(self) -> None:
        def invent_a_reason(document: dict) -> None:
            case = self._case(
                document, "an_update_after_the_terminal_transition_is_refused", "admission_cases"
            )
            case["expected"]["reason_code"] = "view_tombstoned_already"

        self.assertNewFailure(invent_a_reason, "view_tombstoned_already")

    def test_a_refusal_may_not_declare_a_stored_effect(self) -> None:
        """Fail closed is an assertion the fixture has to be able to state."""

        def store_something(document: dict) -> None:
            case = self._case(
                document, "a_patch_that_mixes_a_legal_and_an_illegal_path_stores_nothing",
                "admission_cases",
            )
            case["expected"]["stored_effect"] = "title"

        self.assertNewFailure(store_something, "stored effect")

    def test_an_admitted_case_may_not_carry_an_error(self) -> None:
        def admit_with_an_error(document: dict) -> None:
            case = self._case(document, "legal_active_to_tombstoned_is_admitted", "admission_cases")
            case["expected"]["error"] = "failed_precondition"

        self.assertNewFailure(admit_with_an_error, "MUST NOT carry an error")

    def test_a_transition_may_not_postdate_the_write_that_carried_it(self) -> None:
        """The one rule in this fixture that no schema keyword can state.

        ``state_changed_at`` and ``updated_at`` are produced by the SAME
        accepted Event, so one cannot run ahead of the other -- but JSON Schema
        has no ordering keyword, so every schema-shaped gate in the pipeline
        calls the inconsistent value valid.
        """

        def move_the_transition_forward(document: dict) -> None:
            case = self._case(document, "materialized_terminal_view_validates")
            case["instance"]["state_changed_at"] = "2026-09-19T02:00:00.000Z"

        self.assertNewFailure(move_the_transition_forward, "later than updated_at")

    def test_a_transition_may_not_predate_the_object(self) -> None:
        def move_the_transition_backward(document: dict) -> None:
            case = self._case(document, "materialized_terminal_view_validates")
            case["instance"]["state_changed_at"] = "2026-09-18T00:00:00.000Z"

        self.assertNewFailure(move_the_transition_backward, "earlier than created_at")

    def test_the_acceptance_items_of_the_vector_cannot_be_dropped(self) -> None:
        """Dropping the admitted transition is how this fixture would rot.

        Every rejection case can be written without ever proving the write the
        spec depends on is possible, and a rejection-only fixture looks fuller,
        not emptier.
        """

        def drop_the_admission(document: dict) -> None:
            document["admission_cases"] = [
                case
                for case in document["admission_cases"]
                if case.get("name") != "legal_active_to_tombstoned_is_admitted"
            ]

        self.assertNewFailure(drop_the_admission, "legal_active_to_tombstoned_is_admitted")

    def test_the_prestate_guard_case_cannot_be_dropped(self) -> None:
        def drop_the_guard(document: dict) -> None:
            document["admission_cases"] = [
                case
                for case in document["admission_cases"]
                if case.get("name")
                != "a_stale_prestate_guard_fails_without_selecting_a_historical_candidate"
            ]

        self.assertNewFailure(drop_the_guard, "a_stale_prestate_guard_fails")


if __name__ == "__main__":  # pragma: no cover
    unittest.main()
