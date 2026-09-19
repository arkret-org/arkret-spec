#!/usr/bin/env python3
"""Refresh the closed inventory of explicitly normative prose headings."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime

from artifact_lint.section_identity import (
    NORMATIVE_TITLE_INVENTORY_PATH,
    collect_normative_title_inventory,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--generated-at", required=True)
    args = parser.parse_args()
    generated_at = datetime.fromisoformat(args.generated_at)
    if generated_at.utcoffset() is None:
        parser.error("--generated-at must include an offset")
    date_text = generated_at.date().isoformat()
    counter = 1
    if NORMATIVE_TITLE_INVENTORY_PATH.is_file():
        current = json.loads(
            NORMATIVE_TITLE_INVENTORY_PATH.read_text(encoding="utf-8")
        )
        match = re.fullmatch(r"(\d{4}-\d{2}-\d{2})\.(\d+)", str(current.get("version")))
        if match is None:
            parser.error("current inventory version must use YYYY-MM-DD.N")
        current_date, current_counter = match.groups()
        if current_date > date_text:
            parser.error("--generated-at date precedes the current inventory version")
        if current_date == date_text:
            counter = int(current_counter) + 1
    document = {
        "version": f"{date_text}.{counter}",
        "source_of_truth": True,
        "generated_at": args.generated_at,
        "description": (
            "Closed inventory of current spec/v1/zh headings that explicitly carry "
            "the （normative） marker. Any addition, removal, rename, or move is reviewed "
            "as a protocol change and refreshes this source-of-truth inventory."
        ),
        "titles": collect_normative_title_inventory(),
    }
    NORMATIVE_TITLE_INVENTORY_PATH.write_text(
        json.dumps(document, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
