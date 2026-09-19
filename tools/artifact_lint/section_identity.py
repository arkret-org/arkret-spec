"""Section identity: numbered headings, slugs, fragments and pointer aliases.

A section number is an address other pages cite. Three things were never
checked, and all three were broken at once in `sync/service-http-binding.md`:

* the same number named two different sections (2.1, 2.2, 2.4, 2.4.1), so a
  bare section citation had two candidate targets and no reader or tool could
  tell which one carried the obligation;
* `#fragment` links were only checked as far as the *file* -- `check_markdown_links`
  drops the fragment -- so a link could point at a heading that does not exist,
  and several did;
* three pages ended in a "stable reference anchor" layer whose sections claimed
  to be mere signposts while actually carrying the only statement of live
  obligations. Citing such a layer as a normative source is citing a signpost.

These checks close all three. They deliberately do not judge whether a section
is "substantial enough" to be normative: the obligation is decided by what the
text says, not by its length. What is checked is that every number resolves to
exactly one section, every fragment resolves to a heading that exists, and a
section that declares itself a pure pointer really does nothing but point, at a
single reachable target that is not itself a pointer.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .core import (
    ARTIFACTS,
    Lint,
    ROOT,
    SPEC_ROOT,
    markdown_files,
    markdown_heading_slug,
    read_text,
)

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
NUMBER_RE = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")
FENCE_RE = re.compile(r"^\s*(```|~~~)")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)\s]+)\)")
SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")

HTML_ANCHOR_RE = re.compile(
    r"<a\s[^>]*?\b(?:id|name)\s*=\s*[\"']([^\"']+)[\"']", re.IGNORECASE
)

POINTER_MARKER = "引用别名（normative pointer）"

LEDGER_PATH = ROOT / "tools" / "prose-section-identity-ledger.json"


def _headings(text: str) -> list[tuple[int, str]]:
    """Return (level, heading text) pairs, skipping fenced code blocks."""
    out: list[tuple[int, str]] = []
    fence: str | None = None
    for line in text.split("\n"):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            token = fence_match.group(1)
            if fence is None:
                fence = token
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        match = HEADING_RE.match(line)
        if match:
            out.append((len(match.group(1)), match.group(2)))
    return out


def _anchor_ids(text: str) -> set[str]:
    """Explicit HTML anchor ids, the third convention the spec really uses.

    A clause table cannot carry an ATX heading per row, so the SDK clause table
    gives each row an `<a id="...">`. Those fragments resolve in every renderer,
    so a check that only reads headings would call every one of them broken and
    no repair could ever clear it. Anchors inside fenced code blocks are samples,
    not targets, and are skipped like headings are.
    """
    out: set[str] = set()
    fence: str | None = None
    for line in text.split("\n"):
        fence_match = FENCE_RE.match(line)
        if fence_match:
            token = fence_match.group(1)
            if fence is None:
                fence = token
            elif line.strip().startswith(fence):
                fence = None
            continue
        if fence is not None:
            continue
        out.update(HTML_ANCHOR_RE.findall(line))
    return out


def _slugs(text: str) -> set[str]:
    """Every fragment the page really offers: heading slugs and HTML anchors."""
    return {
        markdown_heading_slug(heading) for _, heading in _headings(text)
    } | _anchor_ids(text)


def check_numbered_heading_identity(lint: Lint) -> None:
    """One number, one section; one slug, one section -- per page.

    A duplicate number makes every bare section citation of that page
    ambiguous, and a duplicate slug makes the second heading unaddressable by
    fragment because renderers resolve the first.
    """
    for path in markdown_files():
        numbers: dict[str, str] = {}
        slugs: dict[str, str] = {}
        for _, heading in _headings(read_text(path)):
            match = NUMBER_RE.match(heading)
            if match:
                number = match.group(1)
                if number in numbers:
                    lint.fail(
                        path,
                        f"section number {number} names two sections: "
                        f"{numbers[number]!r} and {heading!r}; a bare {number} "
                        "citation cannot resolve to one identity",
                    )
                else:
                    numbers[number] = heading
            slug = markdown_heading_slug(heading)
            if slug in slugs:
                lint.fail(
                    path,
                    f"heading slug #{slug} is produced by two headings: "
                    f"{slugs[slug]!r} and {heading!r}; the second is unreachable "
                    "by fragment",
                )
            else:
                slugs[slug] = heading


def _resolve_fragment(
    lint: Lint,
    source: Path,
    target: str,
    where: str,
    slug_cache: dict[Path, set[str]],
    report_path: Path | None = None,
) -> bool:
    """Resolve `target`'s fragment relative to `source`; report under `report_path`.

    Returns False when the fragment could not be resolved to a heading. The
    reporting path is separate because artifact rows and ledger rows name a
    prose anchor from somewhere else in the tree.
    """
    if SCHEME_RE.match(target) or "#" not in target:
        return True
    file_part, fragment = target.split("#", 1)
    if not fragment:
        return True
    resolved = (source.parent / file_part).resolve() if file_part else source.resolve()
    if resolved.suffix != ".md":
        return True
    if not resolved.is_file():
        lint.fail(
            report_path or source,
            f"{where} names {target!r}, whose file does not exist",
        )
        return False
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return True
    if resolved not in slug_cache:
        slug_cache[resolved] = _slugs(resolved.read_text(encoding="utf-8"))
    if fragment not in slug_cache[resolved]:
        rel = resolved.relative_to(ROOT.resolve()).as_posix()
        lint.fail(
            report_path or source,
            f"{where} points at #{fragment} in {rel}, which has no such heading; "
            "a section number existing is not proof its fragment resolves",
        )
        return False
    return True


def check_markdown_fragment_targets(lint: Lint) -> None:
    """Every `#fragment` in a prose link must be a heading that exists.

    `check_markdown_links` stops at the file, so a link could name a heading
    that was renumbered or deleted and stay green forever.
    """
    slug_cache: dict[Path, set[str]] = {}
    for path in markdown_files():
        for target in LINK_RE.findall(read_text(path)):
            _resolve_fragment(lint, path, target, "markdown link", slug_cache)


LINKED_PAGE_SECTION_RE = re.compile(
    r"\[`(?P<label>[^`]+\.md)`\]\((?P<href>[^)\s]+)\)\s*§(?P<section>\d+(?:\.\d+)*)"
)


def check_linked_page_section_refs(lint: Lint) -> None:
    """`[`page.md`](page.md) §N` must name a section that page really has.

    `check_prose_plain_text_section_refs` strips markdown links before it looks
    for citations, so in this very common shape the page name disappears with
    the link and the section number that follows is attributed to nothing. Fifty
    citations across the spec use it and none of them were ever resolved.
    """
    number_cache: dict[Path, set[str]] = {}
    for path in markdown_files():
        for match in LINKED_PAGE_SECTION_RE.finditer(read_text(path)):
            href = match.group("href").split("#", 1)[0]
            if SCHEME_RE.match(href):
                continue
            target = (path.parent / href).resolve()
            if target.suffix != ".md" or not target.is_file():
                continue
            if target not in number_cache:
                number_cache[target] = _numbers(target.read_text(encoding="utf-8"))
            section = match.group("section")
            if section not in number_cache[target]:
                lint.fail(
                    path,
                    f"cites {match.group('label')} section {section}, which that "
                    "page does not have",
                )


ARTIFACT_ANCHOR_RE = re.compile(r"zh/[^\s\"'`),]*?\.md#[^\s\"'`),]+")
BARE_NUMBER_RE = re.compile(r"^\d+(?:\.\d+)*\.?$")

ARTIFACT_ANCHOR_RATCHET_PATH = (
    ROOT / "tools" / "artifact-anchor-fragment-exemptions.json"
)


def _numbers(text: str) -> set[str]:
    out: set[str] = set()
    for _, heading in _headings(text):
        match = NUMBER_RE.match(heading)
        if match:
            out.add(match.group(1))
    return out


def _load_artifact_anchor_ratchet(lint: Lint) -> dict[tuple[str, str], dict]:
    """Rows this gate is allowed to skip, each owned by an open spec report."""
    if not ARTIFACT_ANCHOR_RATCHET_PATH.is_file():
        lint.fail(ARTIFACT_ANCHOR_RATCHET_PATH, "artifact anchor ratchet is missing")
        return {}
    try:
        document = json.loads(
            ARTIFACT_ANCHOR_RATCHET_PATH.read_text(encoding="utf-8")
        )
    except Exception as exc:
        lint.fail(ARTIFACT_ANCHOR_RATCHET_PATH, f"unable to parse ratchet: {exc}")
        return {}
    rows: dict[tuple[str, str], dict] = {}
    for row in document.get("anchors", []):
        if not isinstance(row, dict):
            lint.fail(ARTIFACT_ANCHOR_RATCHET_PATH, f"row is not an object: {row!r}")
            continue
        artifact = row.get("artifact")
        anchor = row.get("anchor")
        owner = row.get("owner_report")
        if not isinstance(artifact, str) or not isinstance(anchor, str):
            lint.fail(ARTIFACT_ANCHOR_RATCHET_PATH, f"row lacks artifact/anchor: {row!r}")
            continue
        if not isinstance(owner, str) or not owner.strip():
            lint.fail(
                ARTIFACT_ANCHOR_RATCHET_PATH,
                f"{artifact} {anchor}: no owner_report; an unowned exemption is a "
                "permanent hole, not a tracked gap",
            )
            continue
        rows[(artifact, anchor)] = row
    return rows


def check_artifact_fragment_targets(lint: Lint) -> None:
    """The same rule for prose anchors carried inside canonical artifacts.

    Registry rows pin obligations to prose anchors (`source_anchor`, the
    `normative:` refs on operations, schemas and contracts). Those were never
    resolved against real headings, so a row could name a section that no
    longer exists -- or never did.

    Artifact anchors carry exactly one convention: a markdown fragment that a
    renderer can resolve -- a heading slug or an explicit `<a id>`. The bare
    dotted number form (`...md#4.1`) is retired: it named a section *number*,
    which no renderer resolves, so such an anchor was never a working link and
    could not be clicked through to the obligation it claimed to cite. Anchors
    written that way are reported here rather than silently resolved against the
    numbering table.

    Rows already broken when this gate landed are listed in a shrink-only
    ratchet, each owned by the spec report that must close it. A ratchet row
    that now resolves is an error too: a repaired anchor MUST leave the list
    rather than sit there licensing the next break.
    """
    ratchet = _load_artifact_anchor_ratchet(lint)
    slug_cache: dict[Path, set[str]] = {}
    probe = SPEC_ROOT / "artifacts" / "_probe_"
    resolved_rows: set[tuple[str, str]] = set()
    seen_rows: set[tuple[str, str]] = set()
    for path in sorted(ARTIFACTS.rglob("*.json")):
        try:
            text = path.read_text(encoding="utf-8")
        except Exception as exc:  # pragma: no cover - unreadable artifact
            lint.fail(path, f"unable to read artifact: {exc}")
            continue
        rel = lint.rel(path)
        for raw in sorted(set(ARTIFACT_ANCHOR_RE.findall(text))):
            anchor = raw.split("zh/", 1)[1]
            page, fragment = anchor.split("#", 1)
            target_path = (SPEC_ROOT / "zh" / page).resolve()
            exempt = (rel, raw) in ratchet
            seen_rows.add((rel, raw))
            if BARE_NUMBER_RE.match(fragment):
                if not exempt:
                    lint.fail(
                        path,
                        f"artifact anchor {raw!r} uses the retired section-number "
                        "form; write the heading fragment the page really offers "
                        "so the citation resolves in a renderer",
                    )
                continue
            errors_before = len(lint.errors)
            _resolve_fragment(
                lint,
                probe,
                "../zh/" + anchor,
                f"artifact anchor {raw!r}",
                slug_cache,
                report_path=path,
            )
            broke = len(lint.errors) > errors_before
            if exempt:
                if broke:
                    del lint.errors[errors_before:]
                else:
                    resolved_rows.add((rel, raw))
    for key in sorted(ratchet):
        if key in resolved_rows:
            lint.fail(
                ARTIFACT_ANCHOR_RATCHET_PATH,
                f"{key[0]} {key[1]}: the anchor resolves now, so its ratchet row "
                "MUST be removed",
            )
        elif key not in seen_rows:
            lint.fail(
                ARTIFACT_ANCHOR_RATCHET_PATH,
                f"{key[0]} {key[1]}: no artifact carries this anchor any more, so "
                "its ratchet row MUST be removed",
            )


def _own_body(text: str, heading: str) -> str:
    """The section's own lines, stopping at the next heading of any level.

    A pointer block belongs to the section that declares it, not to its
    ancestors: `_section_body` includes subsections, so every parent of a
    pointer section would otherwise look like a pointer that "carries prose".
    """
    lines = text.split("\n")
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and match.group(2) == heading:
            body: list[str] = []
            for rest in lines[index + 1:]:
                if HEADING_RE.match(rest):
                    break
                body.append(rest)
            return "\n".join(body).strip()
    return ""


def _section_body(text: str, heading: str) -> str:
    lines = text.split("\n")
    for index, line in enumerate(lines):
        match = HEADING_RE.match(line)
        if match and match.group(2) == heading:
            level = len(match.group(1))
            body: list[str] = []
            for rest in lines[index + 1:]:
                nxt = HEADING_RE.match(rest)
                if nxt and len(nxt.group(1)) <= level:
                    break
                body.append(rest)
            return "\n".join(body).strip()
    return ""


def check_normative_pointer_aliases(lint: Lint) -> None:
    """A section that declares itself a pure pointer must only point.

    The shape is constrained on purpose. A pointer section that also carries a
    free-standing clause is exactly the "signpost with a rule nailed to it" that
    made the old anchor layers citable as normative sources: readers cite the
    number, the obligation lives half here and half there, and neither copy is
    authoritative.
    """
    slug_cache: dict[Path, set[str]] = {}
    for path in markdown_files():
        text = read_text(path)
        for _, heading in _headings(text):
            body = _own_body(text, heading)
            if POINTER_MARKER not in body:
                continue
            stray = [
                line
                for line in body.split("\n")
                if line.strip() and not line.lstrip().startswith(">")
            ]
            if stray:
                lint.fail(
                    path,
                    f"section {heading!r} declares itself a normative pointer but "
                    f"also carries prose outside the pointer block: {stray[0].strip()!r}",
                )
                continue
            links = LINK_RE.findall(body)
            if len(links) != 1:
                lint.fail(
                    path,
                    f"section {heading!r} is a normative pointer with {len(links)} "
                    "link targets; it MUST name exactly one",
                )
                continue
            target = links[0]
            if "#" not in target:
                lint.fail(
                    path,
                    f"section {heading!r} points at {target!r} without a section "
                    "fragment; a pointer MUST name the exact section that carries "
                    "the obligation",
                )
                continue
            if not _resolve_fragment(
                lint, path, target, f"pointer {heading!r}", slug_cache
            ):
                continue
            file_part, fragment = target.split("#", 1)
            resolved = (
                (path.parent / file_part).resolve() if file_part else path.resolve()
            )
            target_text = resolved.read_text(encoding="utf-8")
            for _, target_heading in _headings(target_text):
                if markdown_heading_slug(target_heading) != fragment:
                    continue
                if POINTER_MARKER in _own_body(target_text, target_heading):
                    lint.fail(
                        path,
                        f"section {heading!r} points at {target_heading!r}, which "
                        "is itself a pointer; a pointer chain has no authoritative end",
                    )
                break


LEDGER_DISPOSITIONS = ("promoted", "pointer", "moved")


def check_prose_section_identity_ledger(lint: Lint) -> None:
    """Every retired anchor section is registered with a resolvable disposition.

    Zero inbound citations found by a search is not proof that nothing cites a
    section, so an anchor is never simply deleted: its identity, what it meant
    and where that meaning now lives are recorded here, and the recorded target
    is resolved on every run.
    """
    if not LEDGER_PATH.is_file():
        lint.fail(LEDGER_PATH, "prose section identity ledger is missing")
        return
    try:
        document = json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except Exception as exc:
        lint.fail(LEDGER_PATH, f"unable to parse ledger: {exc}")
        return
    rows = document.get("sections")
    if not isinstance(rows, list) or not rows:
        lint.fail(LEDGER_PATH, "ledger carries no sections")
        return
    seen: set[tuple[str, str]] = set()
    slug_cache: dict[Path, set[str]] = {}
    probe = SPEC_ROOT / "zh" / "_probe_"
    for row in rows:
        if not isinstance(row, dict):
            lint.fail(LEDGER_PATH, f"ledger row is not an object: {row!r}")
            continue
        page = row.get("page")
        section = row.get("section")
        disposition = row.get("disposition")
        target = row.get("target")
        if not isinstance(page, str) or not isinstance(section, str):
            lint.fail(LEDGER_PATH, f"ledger row lacks page/section: {row!r}")
            continue
        key = (page, section)
        if key in seen:
            lint.fail(LEDGER_PATH, f"duplicate ledger row for {page} {section}")
            continue
        seen.add(key)
        if disposition not in LEDGER_DISPOSITIONS:
            lint.fail(
                LEDGER_PATH,
                f"{page} {section}: disposition {disposition!r} is not one of "
                + ", ".join(LEDGER_DISPOSITIONS),
            )
            continue
        meaning = row.get("meaning")
        if not isinstance(meaning, str) or not meaning.strip():
            lint.fail(LEDGER_PATH, f"{page} {section}: no recorded meaning")
        if not isinstance(target, str) or "#" not in target:
            lint.fail(
                LEDGER_PATH,
                f"{page} {section}: target {target!r} must name a page and a fragment",
            )
            continue
        _resolve_fragment(
            lint,
            probe,
            target,
            f"ledger row {page} {section}",
            slug_cache,
            report_path=LEDGER_PATH,
        )
