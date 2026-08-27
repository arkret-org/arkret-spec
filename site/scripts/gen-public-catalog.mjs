// Build/deploy-time generator for the published, version-pinned contract registry
// snapshot served at /v1/contract-registry-<version>.json.
//
// The snapshot is a byte-for-byte copy of the canonical source
// spec/v1/artifacts/registry/contract-registry.json. It is generated here (and
// copied into dist/ by astro build) rather than committed to git, so there is a
// single source of truth. Run automatically via the `prebuild` / `predev`
// package.json hooks.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, "..");
const repoRoot = resolve(siteRoot, "..");

const releaseMetadataPath = resolve(repoRoot, "spec/v1/release-metadata.json");
const releaseMetadata = JSON.parse(readFileSync(releaseMetadataPath, "utf8"));
if (releaseMetadata.format_version !== 1) {
  throw new Error("unsupported release metadata format_version");
}
const tag = releaseMetadata.release_tag;
const releaseTagPattern =
  /^v(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)\.(?:0|[1-9]\d*)(?:-candidate(?:\.[0-9A-Za-z-]+)*)?$/;
if (!releaseTagPattern.test(tag)) {
  throw new Error(`invalid release_tag in ${releaseMetadataPath}`);
}
const version = tag.slice(1);

const source = resolve(repoRoot, "spec/v1/artifacts/registry/contract-registry.json");
const outDir = resolve(siteRoot, "public/v1");
const outFile = resolve(outDir, `contract-registry-${version}.json`);

mkdirSync(outDir, { recursive: true });
writeFileSync(outFile, readFileSync(source));
console.log(`gen-public-catalog: wrote ${outFile} (byte-copy of ${source})`);
