/**
 * Lightweight JSON Schema types restricted to the subset used by the
 * Cokret artifact corpus. We do not aim to be a full JSON Schema 2020-12
 * implementation — only what we actually render.
 */
export interface JsonSchema {
  $schema?: string;
  $id?: string;
  $ref?: string;
  title?: string;
  description?: string;
  type?: string | string[];
  enum?: unknown[];
  const?: unknown;
  format?: string;
  pattern?: string;
  minimum?: number;
  maximum?: number;
  minLength?: number;
  maxLength?: number;
  examples?: unknown[];
  default?: unknown;
  required?: string[];
  properties?: Record<string, JsonSchema>;
  patternProperties?: Record<string, JsonSchema>;
  additionalProperties?: boolean | JsonSchema;
  items?: JsonSchema | JsonSchema[];
  prefixItems?: JsonSchema[];
  minItems?: number;
  maxItems?: number;
  uniqueItems?: boolean;
  oneOf?: JsonSchema[];
  anyOf?: JsonSchema[];
  allOf?: JsonSchema[];
  not?: JsonSchema;
  if?: JsonSchema;
  then?: JsonSchema;
  else?: JsonSchema;
  $defs?: Record<string, JsonSchema>;
  definitions?: Record<string, JsonSchema>;
  // pass-through for unknown keywords
  [key: string]: unknown;
}

/**
 * Flat row presented to the UI by walkSchema(). One row per "named child"
 * (a property, an enum value list, a oneOf branch, ...).
 */
export interface SchemaRow {
  path: string; // dotted path, e.g. "payload.strand_id"
  name: string; // last segment, displayed as field name
  required: boolean;
  type: string; // displayed type label (handles unions, arrays, etc.)
  description?: string;
  enumValues?: unknown[];
  format?: string;
  pattern?: string;
  example?: unknown;
  /** Children of object/array shapes; rendered as nested expandable rows. */
  children?: SchemaRow[];
  /** Composition kind, if this row represents a oneOf/anyOf/allOf branch. */
  composition?: "oneOf" | "anyOf" | "allOf";
  /** Reference target, if the source schema used $ref. */
  ref?: string;
}
