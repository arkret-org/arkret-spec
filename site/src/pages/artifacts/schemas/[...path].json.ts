import type { APIRoute } from "astro";
import { listAllSchemaDocuments, loadSchemaDocument } from "../../../lib/artifacts";

export const prerender = true;

export function getStaticPaths() {
  return listAllSchemaDocuments().map(({ file }) => {
    const tail = file.replace(/^schemas\//, "").replace(/\.json$/, "");
    return { params: { path: tail } };
  });
}

export const GET: APIRoute = ({ params }) => {
  const path = params.path;
  if (!path) return new Response("not found", { status: 404 });

  const file = `schemas/${path}.json`;
  const schema = loadSchemaDocument(file);

  return new Response(JSON.stringify(schema, null, 2) + "\n", {
    headers: {
      "Content-Type": "application/schema+json; charset=utf-8",
    },
  });
};
