from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "artifacts" / "registry" / "mirror-manifest.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Sync canonical artifacts/* outputs into zh/ mirror locations.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit non-zero if any zh mirror differs from canonical artifacts, without writing changes.",
    )
    return parser.parse_args()


def iter_tree_files(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file()
    }


def load_manifest() -> list[dict[str, str]]:
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    mirrors = data.get("mirrors")
    if not isinstance(mirrors, list):
        raise ValueError("mirror manifest must contain a mirrors list")
    normalized: list[dict[str, str]] = []
    for row in mirrors:
        if not isinstance(row, dict):
            raise ValueError("mirror manifest entries must be objects")
        label = row.get("label")
        mode = row.get("mode")
        canonical = row.get("canonical")
        mirror = row.get("mirror")
        if not all(isinstance(value, str) and value for value in (label, mode, canonical, mirror)):
            raise ValueError("mirror manifest entries require non-empty label/mode/canonical/mirror strings")
        normalized.append(
            {
                "label": label,
                "mode": mode,
                "canonical": str(ROOT / canonical),
                "mirror": str(ROOT / mirror),
            }
        )
    return normalized


def sync_file(label: str, canonical: Path, mirror: Path, check: bool, changes: list[str]) -> None:
    if not canonical.exists():
        raise FileNotFoundError(f"canonical {label} file is missing: {canonical}")
    if not mirror.exists() or canonical.read_bytes() != mirror.read_bytes():
        rel = mirror.relative_to(ROOT).as_posix()
        changes.append(f"{label}: {rel}")
        if not check:
            mirror.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical, mirror)


def sync_tree(label: str, canonical: Path, mirror: Path, check: bool, changes: list[str]) -> None:
    if not canonical.exists():
        raise FileNotFoundError(f"canonical {label} tree is missing: {canonical}")

    canonical_files = iter_tree_files(canonical)
    mirror_files = iter_tree_files(mirror) if mirror.exists() else {}

    for rel_path in sorted(canonical_files.keys() - mirror_files.keys()):
        changes.append(f"{label}: add {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            target = mirror / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical_files[rel_path], target)

    for rel_path in sorted(mirror_files.keys() - canonical_files.keys()):
        changes.append(f"{label}: remove {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            (mirror / rel_path).unlink()

    for rel_path in sorted(canonical_files.keys() & mirror_files.keys()):
        if canonical_files[rel_path].read_bytes() == mirror_files[rel_path].read_bytes():
            continue
        changes.append(f"{label}: update {mirror.relative_to(ROOT).as_posix()}/{rel_path}")
        if not check:
            target = mirror / rel_path
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(canonical_files[rel_path], target)

    if not check and mirror.exists():
        for path in sorted(mirror.rglob("*"), reverse=True):
            if path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass


def main() -> int:
    args = parse_args()
    changes: list[str] = []
    mirror_groups = load_manifest()

    for group in mirror_groups:
        label = group["label"]
        canonical = Path(group["canonical"])
        mirror = Path(group["mirror"])
        mode = group["mode"]
        if mode == "file":
            sync_file(label, canonical, mirror, args.check, changes)
        elif mode == "tree":
            sync_tree(label, canonical, mirror, args.check, changes)
        else:
            raise ValueError(f"unsupported mirror mode {mode!r}")

    if args.check:
        if changes:
            print("zh mirror drift detected:")
            for change in changes:
                print(f"  {change}")
            return 1
        print("zh mirrors are in sync with canonical artifacts.")
        return 0

    if changes:
        print("Synced zh mirrors from canonical artifacts:")
        for change in changes:
            print(f"  {change}")
    else:
        print("zh mirrors were already in sync with canonical artifacts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
