import { defineCollection } from "astro:content";
import { glob } from "astro/loaders";
import { docsSchema } from "@astrojs/starlight/schema";

/**
 * The Starlight `docs` collection points at ../spec rather than the default
 * src/content/docs. Starlight's bundled docsLoader() is parameterless in the
 * 0.30 line, so we reach for Astro's glob() loader directly. Starlight then
 * consumes whatever the `docs` collection contains.
 *
 * Path translation: a file at spec/v1/zh/sync/client-sync.md becomes the
 * collection entry `zh/v1/sync/client-sync`, which under Starlight i18n
 * routes to `/zh/v1/sync/client-sync/`.
 */
export const collections = {
  docs: defineCollection({
    loader: glob({
      base: "../spec",
      pattern: "v*/{zh,en}/**/*.{md,mdx}",
      generateId: ({ entry }) => {
        const noExt = entry.replace(/\.(md|mdx)$/, "");
        const segments = noExt.split("/");
        if (segments.length < 2) return noExt;
        const [version, locale, ...rest] = segments;
        const tail = rest.length ? rest.join("/") : "index";
        return `${locale}/${version}/${tail}`;
      },
    }),
    schema: docsSchema(),
  }),
};
