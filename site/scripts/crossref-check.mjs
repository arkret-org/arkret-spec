#!/usr/bin/env node
/**
 * Cross-reference check.
 *
 * Greps every Markdown / MDX file under spec/v1/{zh,en} for occurrences of
 *   <EventKind name="...">, <ErrorCode code="...">,
 *   <OperationRef id="...">, <SchemaViewer schema="...">
 * and verifies each referenced id exists in the corresponding registry.
 *
 * The MDX components themselves throw at build-time on missing ids, so this
 * script is a pre-build fast fail (and it also runs in environments without
 * a JS toolchain installed — pure node + json reads).
 *
 * Run from repo root: `node site/scripts/crossref-check.mjs`
 */
import { readFileSync, readdirSync, statSync } from "node:fs";
import { join, dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const repoRoot = resolve(here, "../..");
const specRoot = resolve(repoRoot, "spec/v1");
const artifactsRoot = resolve(specRoot, "artifacts");

const eventKinds = new Set(
  loadJson("registry/event-kind-registry.json").event_kinds.map((r) => r.event_kind)
);
const errorRegistry = loadJson("registry/error-code-registry.json");
const errorCodes = new Set([
  ...errorRegistry.codes.map((r) => r.code),
  ...(errorRegistry.reason_codes ?? []).map((r) => r.code),
]);
const operations = new Set(
  loadJson("registry/operation-registry.json").operations.map((r) => r.operation_id)
);
const schemaIds = new Set(
  loadJson("registry/schema-registry.json").schemas.map((r) => r.schema_id)
);
const profiles = (() => {
  const data = loadJson("profiles/conformance-profiles.json");
  return new Set(
    [
      ...(data.implementation_profiles ?? []),
      ...(data.deployment_profiles ?? []),
      ...(data.vector_profiles ?? []),
      ...(data.hardening_profiles ?? []),
    ]
  );
})();

const checks = [
  { tag: "EventKind", attr: "name", set: eventKinds },
  { tag: "ErrorCode", attr: "code", set: errorCodes },
  { tag: "OperationRef", attr: "id", set: operations },
  { tag: "SchemaViewer", attr: "schema", set: schemaIds },
];

const errors = [];
for (const file of walk(specRoot)) {
  if (!/\.(md|mdx)$/i.test(file)) continue;
  const text = readFileSync(file, "utf8");
  for (const check of checks) {
    const re = new RegExp(`<${check.tag}\\b[^>]*\\b${check.attr}=["']([^"']+)["']`, "g");
    for (const m of text.matchAll(re)) {
      const id = m[1];
      if (check.set.has(id)) continue;
      // SchemaViewer also accepts file paths starting with `schemas/`
      if (check.tag === "SchemaViewer" && id.startsWith("schemas/")) continue;
      errors.push(`${file}: <${check.tag} ${check.attr}="${id}"> not in registry`);
    }
  }
}

if (errors.length) {
  console.error("crossref check failed:");
  for (const e of errors) console.error(`  ${e}`);
  process.exit(1);
}
console.log(
  `crossref ok (${eventKinds.size} event kinds, ${errorCodes.size} errors, ${operations.size} operations, ${schemaIds.size} schemas, ${profiles.size} profiles)`
);

// helpers ---------------------------------------------------------------------
function loadJson(rel) {
  return JSON.parse(readFileSync(resolve(artifactsRoot, rel), "utf8"));
}

function* walk(dir) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    const s = statSync(p);
    if (s.isDirectory()) yield* walk(p);
    else yield p;
  }
}
