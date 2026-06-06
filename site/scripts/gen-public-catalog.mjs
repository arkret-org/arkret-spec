// Build/deploy-time generator for the published, version-pinned contract catalog
// snapshot served at /v1/contract-catalog-<version>.json.
//
// The snapshot is a byte-for-byte copy of the canonical source
// spec/v1/artifacts/registry/contract-catalog.json. It is generated here (and
// copied into dist/ by astro build) rather than committed to git, so there is a
// single source of truth. Run automatically via the `prebuild` / `predev`
// package.json hooks.

import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const siteRoot = resolve(here, "..");
const repoRoot = resolve(siteRoot, "..");

const metaText = readFileSync(resolve(siteRoot, "src/lib/site-meta.ts"), "utf8");
const match = metaText.match(/export const specReleaseTag\s*=\s*"([^"]+)";/);
if (!match) {
  throw new Error("site-meta.ts missing specReleaseTag");
}
const tag = match[1];
if (!tag.startsWith("v")) {
  throw new Error(`specReleaseTag must start with 'v': ${tag}`);
}
const version = tag.slice(1);

const source = resolve(repoRoot, "spec/v1/artifacts/registry/contract-catalog.json");
const outDir = resolve(siteRoot, "public/v1");
const outFile = resolve(outDir, `contract-catalog-${version}.json`);

mkdirSync(outDir, { recursive: true });
writeFileSync(outFile, readFileSync(source));
console.log(`gen-public-catalog: wrote ${outFile} (byte-copy of ${source})`);
