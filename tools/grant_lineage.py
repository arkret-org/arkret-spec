"""Bounded grant-lineage reference functions for conformance, not admission."""

from __future__ import annotations

import copy
import json

MAX_TIME_MS = 253402300799999
MODERATION_ACTIONS = {"ak.moderation.decision", "ak.moderation.decision.lift"}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def window_covered(action, resource, child, sources, *, finite_required, committed_at,
                   max_lifetime_ms=86400000):
    """Sources are complete validated authority paths, never wire hints."""
    start, end = child
    lower = float("-inf") if start is None else start
    upper = float("inf") if end is None else end
    if lower >= upper or (finite_required and end is None):
        return False
    intervals = []
    for source in sources:
        if [action, resource] not in source["rights"]:
            continue
        if not source.get("current", True):
            continue
        for lo, hi in source["windows"]:
            lo = float("-inf") if lo is None else lo
            if hi is None and finite_required:
                if max_lifetime_ms <= 0 or committed_at > MAX_TIME_MS - max_lifetime_ms:
                    return False
                hi = committed_at + max_lifetime_ms
            hi = float("inf") if hi is None else hi
            if lo < hi:
                intervals.append((lo, hi))
    cursor = lower
    for lo, hi in sorted(intervals):
        if hi <= cursor:
            continue
        if lo > cursor:
            return False
        cursor = hi
        if cursor >= upper:
            return True
    return False


def derive_lineage(parents, *, realm_id, issuer, current_root, child_position,
                   root_controller=False, depth_limit=4):
    """Use authenticated accepted prestate and the actual child position."""
    if not 1 <= depth_limit <= 4:
        raise ValueError("depth limit")
    if current_root.get("kind") != "realm_root" or current_root.get("realm_id") != realm_id:
        raise ValueError("current root")
    if not parents:
        if not root_controller:
            raise ValueError("root controller")
        return {"authority_depth": 1, "authority_root_ref": copy.deepcopy(current_root)}
    roots, depths = [], []
    for parent in parents:
        if (not parent["current"] or parent["realm_id"] != realm_id
                or canonical(parent["subject"]) != canonical(issuer)):
            raise ValueError("current parent authority")
        if parent.get("terminal"):
            raise ValueError("terminal parent")
        if parent["created_position"] >= child_position:
            raise ValueError("parent must precede child")
        root = parent["authority_root_ref"]
        if canonical(root) != canonical(current_root):
            raise ValueError("single current root")
        if type(parent["authority_depth"]) is not int or not 1 <= parent["authority_depth"] <= depth_limit:
            raise ValueError("parent depth")
        roots.append(root)
        depths.append(parent["authority_depth"])
    depth = 1 + max(depths)
    if depth > depth_limit:
        raise ValueError("depth limit")
    return {"authority_depth": depth, "authority_root_ref": copy.deepcopy(roots[0])}


def moderation_dependency(actions, subject_dependencies=(), constraint_dependencies=(), *, known=True):
    """Dependency families come from registered, validated semantics."""
    if not known:
        raise ValueError("unsupported critical semantics")
    return bool(MODERATION_ACTIONS.intersection(actions)
                or "moderation_state" in subject_dependencies
                or "moderation_state" in constraint_dependencies)


def run_case(case):
    operation, value = case["operation"], copy.deepcopy(case["input"])
    try:
        if operation == "window":
            return {"allowed": window_covered(**value)}
        if operation == "lineage":
            return derive_lineage(**value)
        if operation == "dependency":
            return {"depends": moderation_dependency(**value)}
    except (KeyError, TypeError, ValueError):
        return {"decision": "reject"}
    raise ValueError("unregistered reference operation")
