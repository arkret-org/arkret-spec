"""Every `check_*` in `artifact_lint` must be reachable from a real lint phase.

`c473e3c4` deleted two lines from the phase call table in `runner.py` and left
both `check_*` functions sitting in `fixtures.py`. Python does not diagnose an
unused top-level function, the files still existed, and no test asserted that a
check is actually scheduled, so two gates disappeared while the suite stayed
green.

The entry point modelled here is the phase call table that `runner.main()` hands
to `run_lint_phase` — not the import list. Only call edges count: importing a
name, mentioning it in a string, or binding it without calling it does not wire
a check up, and a pair of checks that only call each other stays unreachable.
The analysis therefore proves reachability over the supported call forms; it
does not claim that every Python branch executes, nor that a reached check is
correct.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent / "artifact_lint"
CHECK_PREFIX = "check_"


def _called_names(node: ast.AST) -> set[str]:
    """Every function name invoked in a call position under `node`.

    Helpers count as edges — a registered check may reach another check through
    one — but only in a call position: a bare reference is not an edge.
    """
    names: set[str] = set()
    for child in ast.walk(node):
        if not isinstance(child, ast.Call):
            continue
        func = child.func
        if isinstance(func, ast.Name):
            names.add(func.id)
        elif isinstance(func, ast.Attribute):
            names.add(func.attr)
    return names


def _phase_roots(runner_source: str) -> set[str]:
    """Checks the phase call table actually schedules."""
    tree = ast.parse(runner_source)
    roots: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "run_lint_phase":
            continue
        for argument in list(node.args) + [keyword.value for keyword in node.keywords]:
            roots |= _called_names(argument)
    return roots


def _defined_and_edges(sources: dict[str, str]) -> tuple[set[str], dict[str, set[str]]]:
    defined: set[str] = set()
    edges: dict[str, set[str]] = {}
    for source in sources.values():
        tree = ast.parse(source)
        for node in tree.body:
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            called = _called_names(node)
            called.discard(node.name)
            edges.setdefault(node.name, set()).update(called)
            if node.name.startswith(CHECK_PREFIX):
                defined.add(node.name)
    for name, called in edges.items():
        edges[name] = called & set(edges)
    return defined, edges


def unreachable_checks(sources: dict[str, str], runner_source: str) -> set[str]:
    """`check_*` definitions no phase can reach over supported call edges."""
    defined, edges = _defined_and_edges(sources)
    reachable: set[str] = set()
    frontier = [name for name in _phase_roots(runner_source) if name in edges]
    while frontier:
        name = frontier.pop()
        if name in reachable:
            continue
        reachable.add(name)
        frontier.extend(edges.get(name, ()))
    return defined - reachable


def _package_sources() -> dict[str, str]:
    return {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(PACKAGE.glob("*.py"))
    }


class LintCheckReachabilityTest(unittest.TestCase):
    def test_every_check_is_reachable_from_a_real_phase(self) -> None:
        sources = _package_sources()
        orphans = unreachable_checks(sources, sources["runner.py"])
        self.assertEqual(
            sorted(orphans),
            [],
            "these check_* functions are defined but no lint phase can reach them; "
            "register them in runner.main()'s phase call table, call them from a "
            "registered check, or delete them together with the obligation they guarded",
        )

    def test_phase_roots_are_not_empty(self) -> None:
        sources = _package_sources()
        self.assertGreater(len(_phase_roots(sources["runner.py"])), 100)


RUNNER = """
def main():
    run_lint_phase(1, 1, "p", [("a", lambda: check_registered(lint))])
"""


class ReachabilityAnalysisTest(unittest.TestCase):
    """The gate must fail on each way a check loses its wiring."""

    def test_registered_check_is_reachable(self) -> None:
        sources = {"m.py": "def check_registered(lint):\n    pass\n", "runner.py": RUNNER}
        self.assertEqual(unreachable_checks(sources, RUNNER), set())

    def test_indirect_call_through_a_registered_check_is_reachable(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    helper(lint)\n"
                "def helper(lint):\n"
                "    check_indirect(lint)\n"
                "def check_indirect(lint):\n"
                "    pass\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), set())

    def test_deleting_the_last_call_fails_even_with_the_import_kept(self) -> None:
        sources = {
            "m.py": (
                "from .other import check_orphan\n"
                "def check_registered(lint):\n"
                "    pass\n"
            ),
            "other.py": "def check_orphan(lint):\n    pass\n",
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_orphan"})

    def test_name_bound_but_never_called_is_not_wiring(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    table = [check_orphan]\n"
                "    return table\n"
                "def check_orphan(lint):\n"
                "    pass\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_orphan"})

    def test_mention_in_a_string_is_not_wiring(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    return 'check_orphan'\n"
                "def check_orphan(lint):\n"
                "    pass\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_orphan"})

    def test_self_call_is_not_wiring(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    pass\n"
                "def check_orphan(lint):\n"
                "    check_orphan(lint)\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_orphan"})

    def test_isolated_mutual_calls_are_not_wiring(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    pass\n"
                "def check_left(lint):\n"
                "    check_right(lint)\n"
                "def check_right(lint):\n"
                "    check_left(lint)\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_left", "check_right"})

    def test_unwiring_a_helper_orphans_what_it_reached(self) -> None:
        sources = {
            "m.py": (
                "def check_registered(lint):\n"
                "    pass\n"
                "def helper(lint):\n"
                "    check_downstream(lint)\n"
                "def check_downstream(lint):\n"
                "    pass\n"
            ),
            "runner.py": RUNNER,
        }
        self.assertEqual(unreachable_checks(sources, RUNNER), {"check_downstream"})

    def test_import_list_alone_is_not_a_phase_root(self) -> None:
        runner = "from .m import check_orphan\n\ndef main():\n    run_lint_phase(1, 1, 'p', [])\n"
        sources = {"m.py": "def check_orphan(lint):\n    pass\n", "runner.py": runner}
        self.assertEqual(unreachable_checks(sources, runner), {"check_orphan"})


if __name__ == "__main__":
    unittest.main()
