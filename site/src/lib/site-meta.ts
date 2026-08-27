import releaseMetadata from "@spec/release-metadata.json";

/**
 * Site adapters for metadata referenced from multiple pages.
 *
 * Specifically:
 * - The canonical GitHub repo URL — used by every catalog detail page that
 *   wants to deep-link to the registry row that backs it.
 * - The current spec release tag shown in the homepage hero eyebrow and
 *   marketing footer. Its canonical machine source is
 *   `spec/v1/release-metadata.json`.
 *
 * Registry catalog data stays in `lib/artifacts.ts`; publication metadata is
 * adapted from its canonical JSON rather than copied into this module.
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
 * `site/public/v1/contract-registry-<version>.json` snapshot is generated from
 * this tag by `tools/artifact_pipeline.py generate`, committed, and verified by
 * `tools/artifact_pipeline.py check`.
 */
export const specReleaseTag = releaseMetadata.release_tag;
export const specReleaseLabel = "v1";
