/**
 * Rewrite relative `.md` / `.mdx` links to their Starlight route URLs.
 *
 * Astro 5's built-in relative-link resolution does not fire for the docs
 * collection here: the glob loader points at ../spec (outside src/content/docs)
 * and a custom generateId reorders <version>/<locale> into <locale>/<version>.
 * Without this plugin every `[…](../foo/bar.md)` cross-reference renders as a
 * literal `.md` href and 404s.
 *
 * Source layout: spec/<version>/<locale>/<rest>.md
 * Route layout:  /<locale>/<version>/<rest>/         (trailing slash, no .md)
 *
 * Links that resolve outside spec/<version>/<locale>/ (e.g. ../../artifacts/…)
 * or to non-md targets are left untouched.
 *
 * Anchors and query strings are preserved.
 */
import { dirname, resolve, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";

// specRoot is fixed by the project layout, so we resolve it here rather than
// threading it through plugin options. Keeping the plugin a zero-arg factory
// matches the shape of remark-mermaid and avoids confusing unified's plugin
// pipeline with a partially-applied transformer.
//
// Root is `spec/` (parent of `spec/v1/`) so that relativizing produces paths
// that include the `v1` segment — the route layout begins with the version.
const here = dirname(fileURLToPath(import.meta.url));
const specRoot = resolve(here, "../../spec");

export default function remarkRelMdLinks() {
  return (tree, file) => {
    const sourcePath = file?.history?.[0] || file?.path;
    if (!sourcePath) return;
    const sourceDir = dirname(sourcePath);
    walk(tree, sourceDir);
  };
}

function walk(node, sourceDir) {
  if (!node) return;
  if (node.type === "link" && typeof node.url === "string") {
    const rewritten = rewrite(node.url, sourceDir);
    if (rewritten !== null) node.url = rewritten;
  }
  if (Array.isArray(node.children)) {
    for (const child of node.children) walk(child, sourceDir);
  }
}

function rewrite(url, sourceDir) {
  // Skip absolute URLs (http:, https:, mailto:, etc.), root-absolute paths,
  // and pure anchors — only relative file paths are in scope.
  if (/^[a-z][a-z0-9+\-.]*:/i.test(url)) return null;
  if (url.startsWith("/")) return null;
  if (url.startsWith("#")) return null;

  // Split off optional ?query and #fragment so we operate on just the path.
  const hashIdx = url.indexOf("#");
  const queryIdx = url.indexOf("?");
  let cut = -1;
  if (hashIdx >= 0 && queryIdx >= 0) cut = Math.min(hashIdx, queryIdx);
  else cut = Math.max(hashIdx, queryIdx);
  const path = cut >= 0 ? url.slice(0, cut) : url;
  const tail = cut >= 0 ? url.slice(cut) : "";

  if (!/\.(md|mdx)$/i.test(path)) return null;

  const target = resolve(sourceDir, path);
  const rel = relative(specRoot, target).split(sep).join("/");
  // Expected shape after relativizing against spec root:
  //   <version>/<locale>/<rest>.md
  const m = /^(v\d+)\/(zh|en)\/(.+)\.(md|mdx)$/.exec(rel);
  if (!m) return null;
  const [, version, locale, rest] = m;
  return `/${locale}/${version}/${rest}/${tail}`;
}
