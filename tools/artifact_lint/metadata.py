"""Expose the canonical artifact metadata contract to direct lint invocations."""

from tools.check_artifact_metadata import check

from .core import Lint, ROOT


def check_artifact_metadata(lint: Lint) -> None:
    for error in check(ROOT):
        lint.fail(ROOT, error)
