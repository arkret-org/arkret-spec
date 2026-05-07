// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";
import { readdirSync } from "node:fs";

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
 */
function planeItems(plane) {
  const dir = resolve(specRoot, "zh", plane);
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
    .sort((a, b) => a.slug.localeCompare(b.slug));
}

/**
 * Contrix protocol site.
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
  site: "https://contrix.io",
  trailingSlash: "always",
  vite: {
    server: {
      fs: {
        // allow content collection loaders to read ../spec/v1/{zh,en}
        allow: [here, specRoot],
      },
    },
  },
  integrations: [
    starlight({
      title: "Contrix Spec",
      description:
        "Contrix v1 — decentralized collaboration protocol specification.",
      defaultLocale: "zh",
      locales: {
        zh: { label: "简体中文", lang: "zh" },
        en: { label: "English", lang: "en" },
      },
      sidebar: [
        {
          label: "v1",
          collapsed: false,
          items: [
            { label: "概览", items: planeItems("overview") },
            { label: "身份与组织", items: planeItems("identity") },
            { label: "对象模型", items: planeItems("models") },
            { label: "授权与状态", items: planeItems("authz") },
            { label: "同步与服务", items: planeItems("sync") },
            { label: "发现与目录", items: planeItems("discovery") },
            { label: "加密与媒体", items: planeItems("crypto-media") },
            { label: "扩展", items: planeItems("extensions") },
            { label: "治理", items: planeItems("governance") },
            { label: "安全", items: planeItems("security") },
            { label: "一致性", items: planeItems("conformance") },
            { label: "实施指南", items: planeItems("guides") },
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
        // future: PageTitle override to render artifact badges
      },
      customCss: ["./src/styles/spec.css"],
    }),
    mdx(),
  ],
});
