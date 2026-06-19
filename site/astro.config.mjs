// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readdirSync } from "node:fs";
import remarkMermaid from "./plugins/remark-mermaid.mjs";
import remarkRelMdLinks from "./plugins/remark-rel-md-links.mjs";

const here = dirname(fileURLToPath(import.meta.url));
const specRoot = resolve(here, "../spec/v1");

/**
 * Build explicit `items` array for a plane directory at spec/v1/zh/<plane>/.
 *
 * Starlight's autogenerate option matches against `entry.filePath` relative
 * to the collection base, then prepends the active locale. Our spec layout
 * is `spec/v1/<locale>/<plane>/<file>.md` (version first, then locale),
 * which doesn't fit Starlight's locale-first expectation, so autogenerate
 * silently produces empty groups. To work around it, we list each file
 * explicitly via `{ slug }` references — Starlight's slug lookup handles
 * locale prefixing correctly for explicit slugs.
 *
 * The reference locale (zh) is the source of truth for which entries exist.
 * Starlight auto-localizes the slug to the active locale at render time.
 *
 * Ordering: pass `order` — an array of basenames (no extension) — to pin the
 * reading order of a group. Listed files appear in that exact order; any file
 * not in `order` falls back after them, entry-page-first then alphabetical, so
 * a newly-added doc degrades gracefully instead of being dropped. The intended
 * order mirrors the document grouping in `spec/v1/zh/spec-map.md` §4 (the
 * authoritative reading-path reference) rather than raw filename alphabetical,
 * which would otherwise float optional/advanced docs above the foundations.
 */
function planeItems(plane, order = []) {
  const dir = resolve(specRoot, "zh", plane);
  const rank = (slug) => {
    const name = slug.split("/").pop();
    const i = order.indexOf(name);
    // Unlisted files sort after every explicitly-ordered one.
    return i === -1 ? order.length : i;
  };
  // Convention: a file named `overview` (or `index`) is the plane's entry
  // page and SHOULD appear at the top of the sidebar group. Avoid `index.md`
  // though — Starlight routes it as the directory landing page, which
  // conflicts with explicit slug items.
  const isEntry = (s) => /\/(overview|index)$/.test(s);
  return readdirSync(dir, { withFileTypes: true })
    .filter(
      (e) =>
        e.isFile() &&
        /\.(md|mdx)$/.test(e.name) &&
        e.name.toLowerCase() !== "readme.md",
    )
    .map((e) => ({
      slug: `v1/${plane}/${e.name.replace(/\.(md|mdx)$/, "")}`,
    }))
    .sort((a, b) => {
      const ra = rank(a.slug);
      const rb = rank(b.slug);
      if (ra !== rb) return ra - rb;
      const aEntry = isEntry(a.slug);
      const bEntry = isEntry(b.slug);
      if (aEntry && !bEntry) return -1;
      if (!aEntry && bEntry) return 1;
      return a.slug.localeCompare(b.slug);
    });
}

/**
 * Cokret protocol site.
 *
 * Routing model:
 *   /<locale>/v<version>/<spec-path>          — normative prose (Markdown under spec/<v>/<locale>/)
 *   /<locale>/catalog/<artifact-kind>/[id]    — auto-generated machine-artifact pages
 *   /<locale>/openapi                         — Scalar viewer for the OpenAPI document
 *
 * Locales mirror spec/v1/{zh,en}. Versions mirror spec/<vN>/. Adding a new
 * version is a directory drop + sidebar entry; nothing else changes.
 */
export default defineConfig({
  site: "https://cokret.io",
  trailingSlash: "always",
  redirects: {
    // Locale roots have no normative prose entry; send visitors to the
    // current spec version. /zh/ and /en/ would otherwise 404 because
    // our content collection only exposes v1 docs (slug `<locale>/v1/...`).
    "/zh/": "/zh/v1/",
    "/en/": "/en/v1/",
    // Starlight 0.39+ auto-prepends the active locale to any non-absolute
    // sidebar link, so the Catalog/OpenAPI sidebar entries resolve to
    // `/zh/catalog/…` and `/en/catalog/…` even though the underlying pages
    // live at `/catalog/…` (locale-agnostic, generated from the artifact
    // registry). Redirect the localized variants of the index pages
    // (the only catalog URLs the sidebar emits) back to the canonical
    // un-localized path. Detail pages like `/catalog/schemas/<id>/` are
    // reached by clicking from the index and are not locale-prefixed.
    "/zh/catalog/event-kinds/": "/catalog/event-kinds/",
    "/zh/catalog/errors/": "/catalog/errors/",
    "/zh/catalog/operations/": "/catalog/operations/",
    "/zh/catalog/profiles/": "/catalog/profiles/",
    "/zh/catalog/schemas/": "/catalog/schemas/",
    "/zh/openapi/": "/openapi/",
    "/en/catalog/event-kinds/": "/catalog/event-kinds/",
    "/en/catalog/errors/": "/catalog/errors/",
    "/en/catalog/operations/": "/catalog/operations/",
    "/en/catalog/profiles/": "/catalog/profiles/",
    "/en/catalog/schemas/": "/catalog/schemas/",
    "/en/openapi/": "/openapi/",
  },
  vite: {
    server: {
      fs: {
        // allow content collection loaders to read ../spec/v1/{zh,en}
        allow: [here, specRoot],
      },
    },
  },
  markdown: {
    // ```mermaid blocks → <pre class="mermaid">; client-side mermaid.js
    // (loaded via the starlight head injection below) renders them on page
    // load. Keeps the build pipeline pure-JS — no playwright/puppeteer.
    remarkPlugins: [remarkMermaid, remarkRelMdLinks],
  },
  integrations: [
    starlight({
      title: "Cokret Spec",
      description:
        "Cokret v1 — decentralized collaboration protocol specification.",
      defaultLocale: "zh",
      // Suppress Starlight's auto-injected /404 route: it issues a
      // `getEntry('docs','404')` lookup at build time to find a user override,
      // and our docs collection's id schema (`<locale>/<version>/<path>`)
      // means there is intentionally no id "404" — every build prints
      // `Entry docs → 404 was not found.` We provide our own thin 404 page
      // at src/pages/404.astro instead, which renders without that lookup.
      disable404Route: true,
      head: [
        {
          tag: "link",
          attrs: { rel: "icon", href: "/favicon.svg", type: "image/svg+xml" },
        },
        {
          tag: "link",
          attrs: {
            rel: "icon",
            href: "/favicon-32x32.png",
            sizes: "32x32",
            type: "image/png",
          },
        },
        {
          tag: "link",
          attrs: {
            rel: "apple-touch-icon",
            href: "/apple-touch-icon.png",
            sizes: "180x180",
          },
        },
        {
          tag: "link",
          attrs: { rel: "manifest", href: "/site.webmanifest" },
        },
        {
          tag: "script",
          attrs: { type: "module" },
          content: `
import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";

const pickTheme = () =>
  document.documentElement.dataset.theme === "dark" ? "dark" : "default";

let initialised = false;
async function render() {
  const nodes = Array.from(
    document.querySelectorAll("pre.mermaid:not([data-processed])"),
  );
  if (!nodes.length) return;
  if (!initialised) {
    mermaid.initialize({ startOnLoad: false, theme: pickTheme() });
    initialised = true;
  }
  await mermaid.run({ nodes });
}

// Re-theme on Starlight light/dark toggle. Mermaid v11 has no live retheme,
// so we wipe processed nodes back to their source and re-run.
const sources = new WeakMap();
function captureSources() {
  for (const el of document.querySelectorAll("pre.mermaid")) {
    if (!sources.has(el)) sources.set(el, el.textContent);
  }
}
async function rerenderForTheme() {
  const theme = pickTheme();
  for (const el of document.querySelectorAll("pre.mermaid")) {
    const src = sources.get(el);
    if (!src) continue;
    el.removeAttribute("data-processed");
    el.innerHTML = "";
    el.textContent = src;
  }
  mermaid.initialize({ startOnLoad: false, theme });
  initialised = true;
  await render();
}

const themeObserver = new MutationObserver((records) => {
  for (const r of records) {
    if (r.attributeName === "data-theme") {
      void rerenderForTheme();
      break;
    }
  }
});
themeObserver.observe(document.documentElement, { attributes: true });

// Run on first load, after Astro view-transition swaps, and after
// Starlight client-side nav.
const boot = () => { captureSources(); void render(); };
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", boot, { once: true });
} else {
  boot();
}
document.addEventListener("astro:page-load", boot);
document.addEventListener("astro:after-swap", boot);
`.trim(),
        },
      ],
      locales: {
        zh: { label: "简体中文", lang: "zh" },
        en: { label: "English", lang: "en" },
      },
      sidebar: [
        {
          label: "v1",
          collapsed: false,
          items: [
            // Reading order follows spec-map.md §4 document grouping, not raw
            // filename alphabetical. See planeItems() for the fallback rule.
            {
              label: "概览",
              items: planeItems("overview", [
                "architecture",
                "glossary",
                "current-model",
                "release-readiness",
                "evolution-and-compatibility",
              ]),
            },
            {
              label: "身份与组织",
              items: planeItems("identity", [
                "identity-did",
                "identity-handles",
                "key-management",
                "consent-model",
                "contact-and-direct-conversation",
                "account-lifecycle",
                "tsp-integration",
              ]),
            },
            {
              label: "对象模型",
              items: planeItems("models", [
                "overview",
                "common-fields",
                "realm-and-space",
                "strand-and-message",
                "circle",
                "morph",
                "relation",
                "actor",
                "governance-objects",
                "private-objects",
                "event-and-patch",
                "extension-objects",
                "views",
                "content-types",
                "realm-links",
                "space-hierarchy",
              ]),
            },
            {
              label: "授权与状态",
              items: planeItems("authz", [
                "capabilities",
                "constraint-schema",
                "resource-selector-grammar",
                "event-auth-state-resolution",
                "policy-server",
              ]),
            },
            {
              label: "同步与服务",
              items: planeItems("sync", [
                "operations-sync",
                "client-sync",
                "service-surface",
                "service-http-binding",
                "service-api-schema",
                "api-conventions",
                "transport-bindings",
                "federation",
                "sovereign-deployment",
                "third-party-invites",
              ]),
            },
            {
              label: "发现与目录",
              items: planeItems("discovery", [
                "discovery-directory",
                "object-addressing",
                "profiles-presence",
                "client-preferences",
                "push-notifications",
                "read-receipts",
              ]),
            },
            {
              label: "加密与媒体",
              items: planeItems("crypto-media", [
                "device-lifecycle",
                "encryption-and-audit",
                "media-and-blob",
                "webrtc-signaling",
                "media-service-binding",
                "call-state",
                "audited-e2ee",
              ]),
            },
            {
              label: "扩展",
              items: planeItems("extensions", [
                "applet-integration",
                "applet-schema",
                "agent-protocol-interop",
                "mimi-interop",
              ]),
            },
            {
              label: "治理",
              items: planeItems("governance", [
                "join-policy",
                "history-visibility",
                "content-moderation",
              ]),
            },
            { label: "安全", items: planeItems("security") },
            {
              label: "一致性",
              items: planeItems("conformance", [
                "normative-language",
                "encoding",
                "schema-registry",
                "query-schema",
                "snapshot-schema",
                "conformance-vectors",
                "scalability-constraints",
                "conformance-suite",
                "conformance-profiles",
              ]),
            },
            {
              label: "实施指南",
              items: planeItems("guides", [
                "artifact-consumption",
                "reference-implementation-guide",
                "migrating-from-matrix",
              ]),
            },
          ],
        },
        {
          label: "Catalog",
          collapsed: false,
          items: [
            { label: "Event kinds", link: "/catalog/event-kinds/" },
            { label: "Error codes", link: "/catalog/errors/" },
            { label: "Operations", link: "/catalog/operations/" },
            { label: "Profiles", link: "/catalog/profiles/" },
            { label: "Schemas", link: "/catalog/schemas/" },
            { label: "OpenAPI", link: "/openapi/" },
          ],
        },
      ],
      components: {
        // Site-level nav (brand + Docs/Catalog/OpenAPI/Ecosystem/Blog) above
        // Starlight's default header chrome, so docs pages share the same
        // top nav as the marketing landing page.
        Header: "./src/components/Header.astro",
      },
      customCss: ["./src/styles/spec.css"],
    }),
    mdx(),
  ],
});
