#!/usr/bin/env python3
"""Refresh the exact inventory of explicitly normative prose headings."""
import json
from artifact_lint.section_identity import NORMATIVE_TITLE_INVENTORY_PATH, collect_normative_title_inventory

def main() -> int:
    document = {
        "description": "Closed inventory of current spec/v1/zh headings carrying the normative marker. Heading additions, removals, renames and moves require protocol review.",
        "titles": collect_normative_title_inventory(),
    }
    NORMATIVE_TITLE_INVENTORY_PATH.write_text(json.dumps(document, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
