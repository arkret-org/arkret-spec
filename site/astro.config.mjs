// @ts-check
import { defineConfig } from "astro/config";
import starlight from "@astrojs/starlight";
import mdx from "@astrojs/mdx";
import { fileURLToPath } from "node:url";
import { dirname, resolve } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const specRoot = resolve(here, "../spec/v1");

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
            { label: "概览", autogenerate: { directory: "v1/overview" } },
            { label: "身份与组织", autogenerate: { directory: "v1/identity" } },
            { label: "对象模型", autogenerate: { directory: "v1/models" } },
            { label: "授权与状态", autogenerate: { directory: "v1/authz" } },
            { label: "同步与服务", autogenerate: { directory: "v1/sync" } },
            { label: "发现与目录", autogenerate: { directory: "v1/discovery" } },
            { label: "加密与媒体", autogenerate: { directory: "v1/crypto-media" } },
            { label: "扩展", autogenerate: { directory: "v1/extensions" } },
            { label: "治理", autogenerate: { directory: "v1/governance" } },
            { label: "安全", autogenerate: { directory: "v1/security" } },
            { label: "一致性", autogenerate: { directory: "v1/conformance" } },
            { label: "实施指南", autogenerate: { directory: "v1/guides" } },
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
