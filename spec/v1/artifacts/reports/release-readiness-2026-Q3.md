# Cokret Spec Release Readiness 2026 Q3

- Report ID: `release-readiness-2026-Q3`
- Generated: `2026-05-25`
- Spec head checked: local `b7d35be` on `main`; `origin/main` was 5 commits behind at audit time.
- Target: `v1.0.0` stable promotion candidate. No release tag, GitHub release, or remote release artifact is created by this workflow.
- Status: blocked for stable promotion. Local artifact, fixture, docs, and site checks have current passing evidence, but CKP-0007 machine-contract gaps, versioned public catalog policy, and dependency audit findings must be closed or explicitly de-scoped before release.

## Artifact Counts

| Artifact | Count | Source |
| --- | ---: | --- |
| Event kinds | 159 | `tools/artifact_pipeline.py check` |
| Schemas | 54 | `tools/artifact_pipeline.py check` |
| Typed ID kinds | 41 | `tools/artifact_pipeline.py check` |
| Operations | 87 | `tools/artifact_pipeline.py check` |
| Claimable profiles | 58 | `tools/artifact_pipeline.py check` |
| Profile ID references | 79 | `tools/artifact_pipeline.py check` |

## Checks

| Check | Result |
| --- | --- |
| Artifact registry lint | passed: `python tools/artifact_pipeline.py check` |
| Registry diff | clean |
| Cross-artifact lint | passed: `python tools/lint_artifacts.py` |
| Site crossref | passed: `node site/scripts/crossref-check.mjs` |
| Fixture digest reference | passed: `python tools/check_fixture_digests.py --reference spec/v1/artifacts/reports/fixture-digests.json` |
| Markdown lint | passed: `npx markdownlint-cli2@0.18.1` |
| Site typecheck / build | passed: `cd site && npm run check`; `cd site && npm run build` |
| Dependency audit | failed: `npm audit --omit=dev --audit-level=moderate` reported 1 high, 6 moderate, and 3 low vulnerabilities in the site production dependency tree |
| External link check | pending local evidence; lychee was not installed locally, CI link-check remains the required evidence path |
| Contract policy | active-contract checks only |
| English mirror policy | non-normative placeholder; only `spec/v1/en/index.md` is an English page. Any generated `/en/v1/...` fallback page is not an English normative translation. |
| CKP-0001..0006 | deferred to v1.1; not v1.0 wire contracts |
| CKP-0007 | accepted in prose/registry surface, but not ready for stable promotion until the blockers below close |

## Stable-promotion Blockers

1. Close CKP-0007 machine-contract gaps:
   - split or normativize submit input vs accepted/reducer-output event shapes for `effective_scope`;
   - define Message and Anchor output shapes that bind `effective_scope`, including anchor canonical bytes;
   - make `content_encryption_floor` a machine-checkable contract, not only prose;
   - register and validate the standard `confidential_discussion_of` Relation shape if it remains the migration path;
   - add Circle/effective-scope conformance vectors, fixtures, and profile matrix requirements.
2. Resolve or explicitly exception the site dependency audit findings before public stable publication.
3. Push the candidate branch/PR and retain GitHub Actions evidence for artifact lint, docs lint, fixture digest, link-check, and site build.

## Versioned Public Artifact Policy

The canonical live source remains `spec/v1/artifacts/registry/contract-catalog.json`. Files under `site/public/v1/contract-catalog-<version>.json` are public release snapshots and must have an explicit lifecycle:

- Frozen-baseline route: leave old snapshots unchanged and publish the current contract under a new versioned filename.
- Current-release route: regenerate the existing versioned snapshot only as an intentional replacement, and gate it with count/hash checks against the canonical catalog.

Current HEAD uses a single current-v1 public snapshot: `site/src/lib/site-meta.ts#specReleaseTag` points at `v1.0.0`, and `site/public/v1/contract-catalog-1.0.0.json` MUST be byte-identical to the canonical catalog. The repository does not maintain separate rc/stable catalog snapshots. `python tools/artifact_pipeline.py check` enforces hash/count/Circle-presence gates for the current v1 snapshot.

## Release Notes Seed

Do not promote the current HEAD directly to stable. Once the blockers above are closed, the v1.0.0 release notes should state the exact canonical artifact counts, the public catalog snapshot filename, and the CKP-0007 conformance/vector coverage included in the release. The English mirror remains explicitly non-normative until the CKP-EN-MIRROR translation track lands. CKP-0001 through CKP-0006 remain design proposals and are not v1.0 wire contracts.
