import type { JsonSchema, SchemaRow } from "./types";
import { deref, type DerefContext } from "./deref";

/**
 * Convert a JSON Schema into a flat tree of {@link SchemaRow}s suitable for
 * the SchemaViewer component. Handles:
 *
 *   - object properties with `required`
 *   - array items / prefixItems
 *   - oneOf / anyOf / allOf composition (rendered as composition rows)
 *   - `$ref` (resolved via deref)
 *   - `enum` and `const` (kept on the row as enumValues)
 *
 * Anything we cannot represent cleanly is surfaced as a textual type
 * (e.g. "object" or "?"). This keeps the renderer honest — we don't lie
 * about coverage by silently dropping shape.
 */
/** Hard cap on recursion depth. Recursive schemas (e.g. `content_block`
 *  containing nested `parts: [content_block]`) would otherwise blow the
 *  staak. Beyond this depth we render a placeholder row pointing the user
 *  back to the schema id for full inspection. */
const MAX_DEPTH = 8;

export function walkSchema(root: JsonSchema, ctx: DerefContext): SchemaRow {
  return buildRow("$", "$", root, true, ctx, 0);
}

function buildRow(
  path: string,
  name: string,
  node: JsonSchema,
  required: boolean,
  ctx: DerefContext,
  depth: number
): SchemaRow {
  if (depth > MAX_DEPTH) {
    return {
      path,
      name,
      required,
      type: "…",
      description: `recursion truncated at depth ${MAX_DEPTH}; see source schema for full shape`,
    };
  }
  // JSON Schema 2020-12 allows a boolean in any sub-schema slot:
  // `true` accepts anything, `false` rejects everything. They aren't
  // objects, so the rest of this function — `.$ref`, `'default' in node`,
  // composition keys — would crash on them.
  if (typeof node !== "object" || node === null) {
    return {
      path,
      name,
      required,
      type: node === false ? "never" : "any",
    };
  }
  const refTarget = node.$ref;
  const resolved = deref(node, ctx);
  const description = resolved.description ?? node.description;
  const example = pickExample(resolved);
  const enumValues = resolved.enum ?? (resolved.const !== undefined ? [resolved.const] : undefined);
  const row: SchemaRow = {
    path,
    name,
    required,
    type: typeLabel(resolved),
    description,
    enumValues,
    format: resolved.format,
    pattern: resolved.pattern,
    example,
    ref: refTarget,
  };

  // composition (oneOf / anyOf / allOf)
  for (const key of ["oneOf", "anyOf", "allOf"] as const) {
    const branches = resolved[key];
    if (Array.isArray(branches) && branches.length > 0) {
      row.children = (row.children ?? []).concat(
        branches.map((branch, i) => {
          const r = buildRow(`${path}.${key}[${i}]`, `${key}[${i}]`, branch, false, ctx, depth + 1);
          r.composition = key;
          return r;
        })
      );
    }
  }

  // object
  if (resolved.type === "object" || (!resolved.type && resolved.properties)) {
    const props = resolved.properties ?? {};
    const requiredSet = new Set(resolved.required ?? []);
    const childRows = Object.entries(props).map(([prop, sub]) =>
      buildRow(`${path}.${prop}`, prop, sub, requiredSet.has(prop), ctx, depth + 1)
    );
    if (resolved.patternProperties) {
      for (const [pattern, sub] of Object.entries(resolved.patternProperties)) {
        childRows.push(
          buildRow(`${path}./${pattern}/`, `(${pattern})`, sub, false, ctx, depth + 1)
        );
      }
    }
    if (childRows.length) row.children = (row.children ?? []).concat(childRows);
  }

  // array
  if (resolved.type === "array" && resolved.items && !Array.isArray(resolved.items)) {
    row.children = (row.children ?? []).concat([
      buildRow(`${path}[]`, "items", resolved.items, false, ctx, depth + 1),
    ]);
  }
  if (Array.isArray(resolved.prefixItems)) {
    row.children = (row.children ?? []).concat(
      resolved.prefixItems.map((sub, i) =>
        buildRow(`${path}[${i}]`, `[${i}]`, sub, false, ctx, depth + 1)
      )
    );
  }

  return row;
}

function typeLabel(node: JsonSchema): string {
  if (node.const !== undefined) return `const ${JSON.stringify(node.const)}`;
  if (node.enum) {
    const types = new Set(node.enum.map((v) => typeof v));
    if (types.size === 1 && types.has("string")) return "string (enum)";
    return `enum (${node.enum.length})`;
  }
  if (Array.isArray(node.type)) return node.type.join(" | ");
  if (typeof node.type === "string") {
    if (node.type === "array") {
      const items = node.items;
      if (items && !Array.isArray(items)) {
        return `array<${typeLabel(items)}>`;
      }
      return "array";
    }
    if (node.type === "string" && node.format) return `string (${node.format})`;
    return node.type;
  }
  if (node.oneOf) return `oneOf[${node.oneOf.length}]`;
  if (node.anyOf) return `anyOf[${node.anyOf.length}]`;
  if (node.allOf) return `allOf[${node.allOf.length}]`;
  if (node.$ref) return `$ref ${node.$ref}`;
  if (node.properties) return "object";
  return "?";
}

function pickExample(node: JsonSchema): unknown {
  if (Array.isArray(node.examples) && node.examples.length > 0) return node.examples[0];
  if ("default" in node) return node.default;
  return undefined;
}
