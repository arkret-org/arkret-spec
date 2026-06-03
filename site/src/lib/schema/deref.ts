import type { JsonSchema } from "./types";

/**
 * Resolve a JSON Pointer against a root schema document. Supports the
 * subset Cokret actually uses: same-doc fragments (`#/$defs/Foo`) and
 * sibling-file fragments (`./event-envelope.schema.json`, `./event-envelope.schema.json#/...`).
 *
 * Cross-file resolution requires the caller to provide a `loadFile` callback
 * because the loader differs between build-time (artifacts.ts) and any future
 * dev-time tooling.
 */
export interface DerefContext {
  /** The current schema document, used for in-doc `$ref: "#/..."`. */
  doc: JsonSchema;
  /** Identity of the current document (e.g. "schemas/space.schema.json"). */
  docId: string;
  /** Resolves a sibling file path into another schema document. */
  loadFile?: (relativeRef: string) => JsonSchema | undefined;
  /** Tracks visited refs to break cycles. */
  visited?: Set<string>;
}

const POINTER_DECODE = (token: string) => token.replace(/~1/g, "/").replace(/~0/g, "~");

function resolvePointer(doc: JsonSchema, pointer: string): JsonSchema | undefined {
  if (pointer === "" || pointer === "/") return doc;
  const parts = pointer.replace(/^\//, "").split("/").map(POINTER_DECODE);
  let cur: unknown = doc;
  for (const part of parts) {
    if (cur && typeof cur === "object" && part in (cur as Record<string, unknown>)) {
      cur = (cur as Record<string, unknown>)[part];
    } else {
      return undefined;
    }
  }
  return cur as JsonSchema;
}

export function deref(node: JsonSchema, ctx: DerefContext): JsonSchema {
  if (!node || typeof node !== "object" || !node.$ref) return node;
  const ref = node.$ref;
  const visited = ctx.visited ?? new Set<string>();
  const cycleKey = `${ctx.docId}::${ref}`;
  if (visited.has(cycleKey)) return { ...node, description: node.description ?? `cycle: ${ref}` };
  visited.add(cycleKey);

  // same-doc fragment
  if (ref.startsWith("#")) {
    const target = resolvePointer(ctx.doc, ref.slice(1));
    if (!target) return node;
    return deref(target, { ...ctx, visited });
  }

  // cross-file: optional fragment
  const [filePart, fragment] = ref.split("#");
  const next = ctx.loadFile?.(filePart);
  if (!next) return node;
  const target = fragment ? resolvePointer(next, fragment) : next;
  if (!target) return node;
  return deref(target, { doc: next, docId: filePart, loadFile: ctx.loadFile, visited });
}
