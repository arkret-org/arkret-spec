"""RFC 8785 encoding for reference vectors without floating-point numbers."""

from __future__ import annotations

import json
from typing import Any


def jcs_text(value: Any) -> str:
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        if abs(value) > 9_007_199_254_740_991:
            raise ValueError("JCS integer is outside the interoperable IEEE-754 range")
        return str(value)
    if isinstance(value, float):
        raise ValueError("floating-point values are not supported by reference vectors")
    if isinstance(value, str):
        encoded = json.dumps(value, ensure_ascii=False, allow_nan=False)
        encoded.encode("utf-8", errors="strict")
        return encoded
    if isinstance(value, list):
        return "[" + ",".join(jcs_text(item) for item in value) + "]"
    if isinstance(value, dict):
        if any(not isinstance(key, str) for key in value):
            raise ValueError("JCS object property names must be strings")
        return "{" + ",".join(
            jcs_text(key) + ":" + jcs_text(value[key])
            for key in sorted(value, key=lambda key: key.encode("utf-16-be", errors="strict"))
        ) + "}"
    raise ValueError(f"unsupported JCS value type: {type(value).__name__}")
