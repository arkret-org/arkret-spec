/**
 * Single source of truth for site-level metadata that is referenced from
 * multiple pages but isn't derivable from `spec/v1/artifacts/`.
 *
 * Specifically:
 * - The canonical GitHub repo URL — used by every catalog detail page that
 *   wants to deep-link to the registry row that backs it.
 * - The current spec release tag shown in the homepage hero eyebrow and
 *   marketing footer. `tools/artifact_pipeline.py check` requires the
 *   matching public catalog snapshot to be byte-identical to the canonical
 *   registry catalog.
 *
 * Anything that lives inside `contract-catalog.json` (catalog version,
 * registry counts, ...) stays in `lib/artifacts.ts`; this file is for
 * meta that no machine artifact owns.
 */

export const repoUrl = "https://github.com/arkret-org/arkret-spec";
export const repoMain = `${repoUrl}/blob/main`;

/** Returns a URL to a file under spec/v1/ on the canonical repo. */
export function specFileUrl(relPath: string): string {
  const trimmed = relPath.replace(/^\.\//, "").replace(/^\/+/, "");
  return `${repoMain}/${trimmed}`;
}

/**
 * The current v1 publication state shown by the site.
 *
 * Keep the pre-release suffix until the stable promotion gate passes. The published
 * `site/public/v1/contract-catalog-<version>.json` snapshot is generated from
 * this tag at build time (scripts/gen-public-catalog.mjs) and is not committed.
 */
export const specReleaseTag = "v1.0.0-candidate";
export const specReleaseLabel = "v1";
