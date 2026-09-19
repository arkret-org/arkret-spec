"""Shared structural check for closed, conjunctive evidence-reference sets."""

from __future__ import annotations

from collections.abc import Callable, Hashable
from typing import Any

from .core import Lint, Path


def check_closed_evidence_set(
    lint: Lint,
    path: Path,
    label: str,
    value: Any,
    *,
    empty_error: str,
    parse: Callable[[Any], tuple[Hashable | None, str | None]],
    resolve: Callable[[Any, Hashable], str | None],
) -> bool:
    """Require every member of a non-empty reference set to parse and resolve.

    Callers own their record shape and reference namespace. This helper owns the
    shared conjunctive rule: the set is non-empty, contains no duplicate exact
    reference, and every listed member resolves. It deliberately makes no claim
    about whether the resolved evidence has the right natural-language meaning.
    """
    if not isinstance(value, list) or not value:
        lint.fail(path, empty_error)
        return False

    ok = True
    seen: set[Hashable] = set()
    for index, reference in enumerate(value):
        item_label = f"{label}[{index}]"
        key, error = parse(reference)
        if error is not None or key is None:
            lint.fail(path, f"{item_label} {error or 'is malformed'}")
            ok = False
            continue
        if key in seen:
            lint.fail(path, f"{item_label} duplicates an earlier required reference")
            ok = False
            continue
        seen.add(key)
        error = resolve(reference, key)
        if error is not None:
            lint.fail(path, f"{item_label} {error}")
            ok = False
    return ok


__all__ = ["check_closed_evidence_set"]
