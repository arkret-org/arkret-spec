# contrix-spec — Release-Readiness Tasks

> Parent plan: [`../_todos_all.md`](../_todos_all.md)
> Project role: protocol source of truth; gates all downstream wire changes.
> Phase: **1 (blocking)**.

## State at start (2026-05-24)

- Body (zh/) is **locked**: 73 files, 12 sections, 0 unresolved TBD.
- Artifacts clean: 152 event kinds, 53 schemas, 87 ops, 58 profiles. Drift detection (`renames.json` + 5 forbidden-* lists) active.
- en/ is a placeholder — only `index.md`, marked non-normative.
- 6 CXP proposals all DRAFT, no merge/deferral notice.
- CI: artifact-lint.yml + site.yml. Missing markdown-lint, external-link check, fixture-digest CI validator.
- Teabay §7-§9 baseline passed 2026-05-10 (6/7 checks).

## Phase 1 tasks (must close before SDK local rc1 freeze)

### Spec body & artifacts
- [x] §1 Re-run `python tools/artifact_pipeline.py check` and confirm `registry diff: clean` on `main` HEAD.
- [x] §2 Sweep `spec/v1/zh/` once more for legacy terms (`chadex`, `Place`/`Space` outside the inversion notes). Expect zero hits beyond `guides/migrating-from-matrix.md`.
- [x] §3 Decide and apply policy for `spec/v1/en/`: either commit to translation timeline or add a banner + frontmatter in `en/index.md` that explicitly says "Non-normative placeholder. Authority is `zh/`. Translation tracked in CXP-EN-MIRROR." (Q1 in master plan.)
- [x] §4 Mark all 6 CXP proposals: open each `spec/v1/proposals/CXP-000{1..6}.md` and add `status: deferred-to-v1.1` in frontmatter (or `accepted` if intended for 1.0).

### CI hygiene (master plan §5 baseline)
- [x] §5 Add `markdownlint-cli2` to `.github/workflows/artifact-lint.yml` (or a separate `docs-lint.yml`); fail on errors but warn on style.
- [x] §6 Add `lychee` (or `markdown-link-check`) external-link checker on a weekly schedule, allowlist `localhost`, `did:example`, `https://example.org/*`.
- [x] §7 Wire fixture-digest CI: add a job that downloads the latest cotest reference output and asserts the fixtures under `spec/v1/artifacts/fixtures/` match.
- [x] §8 Add `typos` workflow (crate-ci/typos) gated on `spec/v1/**/*.md`. Reuse `typos.toml` allowlist from sibling projects.

### Release
- [x] §9 Add `release-readiness-2026-Q3.md` next to existing teabay baseline in `spec/v1/artifacts/reports/` summarizing all artifact counts for the local rc1 freeze.
- [x] §10 Produce local `v1.0.0-rc1` artifact evidence once §1-§9 are green. Do not create GitHub releases or push release tags.

### Stretch (phase 5 nice-to-have)
- [x] §11 Stage `spec/v1/artifacts/contract-catalog.json` in local versioned artifact evidence so SDK consumers can pin without any remote publish step.

## Exit gate (phase 1)

All of:
1. `python tools/artifact_pipeline.py check` returns clean.
2. `lint_artifacts.py` succeeds on CI.
3. New CI jobs (markdown-lint, link-check, typos, fixture-digest) green.
4. Local `v1.0.0-rc1` artifact evidence exists; release notes link to `_todos_all.md`.

## Notes

- `tools/check-publish-order.py` (in `contrix-rust-sdk`) consumes our artifact bundle; do not change file layout without coordinating.
- The CHANGELOG ([Unreleased] section) currently has 4 entries from 2026-05-24; leave them — they are the rc1 release notes seed.
