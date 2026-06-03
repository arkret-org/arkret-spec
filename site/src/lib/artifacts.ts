/**
 * Single source-of-truth loader for spec/v1/artifacts/.
 *
 * Every component (EventKind, ErrorCodeTable, SchemaViewer, ...) and every
 * dynamic catalog route imports from here, so the JSON Schema / registry
 * files are read once at build time and cross-referenced via typed lookups.
 *
 * The registry / schema / fixture files are imported through Vite's
 * `import.meta.glob` with `eager: true`, which means everything is bundled
 * into the static build and there is no runtime fetch.
 */

// --- raw bundled data --------------------------------------------------------

const registryFiles = import.meta.glob<Record<string, unknown>>(
  "../../../spec/v1/artifacts/registry/*.json",
  { eager: true, import: "default" }
);

const profileFiles = import.meta.glob<Record<string, unknown>>(
  "../../../spec/v1/artifacts/profiles/*.json",
  { eager: true, import: "default" }
);

const schemaFiles = import.meta.glob<Record<string, unknown>>(
  "../../../spec/v1/artifacts/schemas/*.json",
  { eager: true, import: "default" }
);

const fixtureFiles = import.meta.glob<Record<string, unknown>>(
  "../../../spec/v1/artifacts/fixtures/*.json",
  { eager: true, import: "default" }
);

const openapiFiles = import.meta.glob<string>(
  "../../../spec/v1/artifacts/openapi/*.yaml",
  { eager: true, query: "?raw", import: "default" }
);

const bindingFiles = import.meta.glob<string>(
  "../../../spec/v1/artifacts/bindings/*.yaml",
  { eager: true, query: "?raw", import: "default" }
);

// --- typed shapes (only the fields we actually display) ----------------------

export interface EventKind {
  event_kind: string;
  category: string;
  status: "active" | "reserved" | string;
  wire_scope: "durable_event" | "actor_private_event" | "ephemeral_event" | string;
  reducer_input?: boolean;
  payload?: string;
}

export interface ErrorCode {
  code: string;
  kind?: "code" | "reason_code";
  http_status?: number;
  scope?: "service" | "item" | "both" | string;
  applies_to?: string[];
  description: string;
}

export interface IdKind {
  kind: string;
  category: string;
  status: string;
  wire_form: string;
  description?: string;
}

export interface Operation {
  operation_id: string;
  http: string;
  grpc: string;
  mq: string;
  /** For interop_bridge tier ops, the in-spec operation this bridge mirrors. */
  bridges_to?: string;
}

export interface SurfaceGroup {
  surface: string;
  tier: string;
  operations: string[];
}

export interface SchemaEntry {
  schema_id: string;
  file: string;
}

export interface ConformanceProfileMatrix {
  implementation_profiles: string[];
  deployment_profiles: string[];
  vector_profiles: string[];
  hardening_profiles: string[];
  encoding_extension_profiles?: string[];
  identity_extension_profiles?: string[];
  profile_requirements: Record<string, unknown>;
  default_unsupported_behavior?: Record<string, unknown>;
}

// --- typed accessors ---------------------------------------------------------

function fileEnd(path: string): string {
  const tail = path.split("/").pop();
  if (!tail) throw new Error(`unexpected path: ${path}`);
  return tail;
}

function pickRegistry<T = unknown>(name: string): T {
  const key = Object.keys(registryFiles).find((p) => fileEnd(p) === name);
  if (!key) throw new Error(`registry file missing: ${name}`);
  return registryFiles[key] as T;
}

function pickProfile<T = unknown>(name: string): T {
  const key = Object.keys(profileFiles).find((p) => fileEnd(p) === name);
  if (!key) throw new Error(`profile file missing: ${name}`);
  return profileFiles[key] as T;
}

function pickSchema<T = unknown>(name: string): T {
  const key = Object.keys(schemaFiles).find((p) => fileEnd(p) === name);
  if (!key) throw new Error(`schema file missing: ${name}`);
  return schemaFiles[key] as T;
}

const contractCatalog = pickRegistry<Record<string, unknown>>("contract-catalog.json");
const eventRegistry = pickRegistry<{ event_kinds: EventKind[] }>("event-kind-registry.json");
const errorRegistry = pickRegistry<{ codes: ErrorCode[]; reason_codes?: ErrorCode[] }>("error-code-registry.json");
const idRegistry = pickRegistry<{ id_kinds: IdKind[]; special_forms?: IdKind[] }>("id-kind-registry.json");
const operationRegistry = pickRegistry<{
  operations: Operation[];
  surface_groups: SurfaceGroup[];
  capability_tiers: Record<string, string>;
}>("operation-registry.json");
const schemaRegistry = pickRegistry<{ schemas: SchemaEntry[] }>("schema-registry.json");
const conformanceProfiles = pickProfile<ConformanceProfileMatrix>("conformance-profiles.json");

// --- exports -----------------------------------------------------------------

export const eventKinds: EventKind[] = eventRegistry.event_kinds.slice().sort((a, b) =>
  a.event_kind.localeCompare(b.event_kind)
);

const errorCodeMap = new Map<string, ErrorCode>();
for (const row of errorRegistry.codes) {
  errorCodeMap.set(row.code, { ...row, kind: "code" });
}
for (const row of errorRegistry.reason_codes ?? []) {
  if (!errorCodeMap.has(row.code)) {
    errorCodeMap.set(row.code, { ...row, kind: "reason_code" });
  }
}

export const errorCodes: ErrorCode[] = Array.from(errorCodeMap.values()).sort((a, b) =>
  a.code.localeCompare(b.code)
);

export const idKinds: IdKind[] = idRegistry.id_kinds.slice().sort((a, b) =>
  a.kind.localeCompare(b.kind)
);

export const operations: Operation[] = operationRegistry.operations.slice().sort((a, b) =>
  a.operation_id.localeCompare(b.operation_id)
);

export const surfaceGroups: SurfaceGroup[] = operationRegistry.surface_groups;
export const capabilityTiers: Record<string, string> = operationRegistry.capability_tiers;

export const schemaEntries: SchemaEntry[] = schemaRegistry.schemas.slice().sort((a, b) =>
  a.schema_id.localeCompare(b.schema_id)
);

export const profileMatrix = conformanceProfiles;

/**
 * Distinct `ck.profile.*` ids declared anywhere in conformance-profiles.json.
 * Mirrors what `tools/lint_artifacts.py` reports as "N profiles" so the
 * homepage stat and release-readiness numbers stay in sync.
 */
export const totalProfileCount: number = (() => {
  const seen = new Set<string>();
  const walk = (value: unknown): void => {
    if (typeof value === "string") {
      if (value.startsWith("ck.profile.")) seen.add(value);
      return;
    }
    if (Array.isArray(value)) {
      for (const item of value) walk(item);
      return;
    }
    if (value && typeof value === "object") {
      for (const item of Object.values(value as Record<string, unknown>)) {
        walk(item);
      }
    }
  };
  walk(conformanceProfiles as unknown);
  return seen.size;
})();

export const catalogVersion: string =
  (contractCatalog.version as string | undefined) ?? "unknown";

// --- lookup helpers ----------------------------------------------------------

const eventByKind = new Map(eventKinds.map((row) => [row.event_kind, row]));
const errorByCode = new Map(errorCodes.map((row) => [row.code, row]));
const idByKind = new Map(idKinds.map((row) => [row.kind, row]));
const operationById = new Map(operations.map((row) => [row.operation_id, row]));
const schemaById = new Map(schemaEntries.map((row) => [row.schema_id, row]));

const surfaceByOperation = new Map<string, SurfaceGroup>();
for (const group of surfaceGroups) {
  for (const id of group.operations) surfaceByOperation.set(id, group);
}

export function getEventKind(kind: string): EventKind | undefined {
  return eventByKind.get(kind);
}
export function getErrorCode(code: string): ErrorCode | undefined {
  return errorByCode.get(code);
}
export function getIdKind(kind: string): IdKind | undefined {
  return idByKind.get(kind);
}
export function getOperation(id: string): Operation | undefined {
  return operationById.get(id);
}
export function getOperationSurface(id: string): SurfaceGroup | undefined {
  return surfaceByOperation.get(id);
}
export function getSchemaEntry(id: string): SchemaEntry | undefined {
  return schemaById.get(id);
}

// --- schema document loading -------------------------------------------------

/**
 * Load a JSON Schema document by either its registered schema_id or its
 * artifact-relative file path (`schemas/<name>.schema.json`). Returns the
 * raw schema object — composition / $ref resolution is the caller's concern,
 * see lib/schema/deref.ts.
 */
export function loadSchemaDocument(idOrFile: string): Record<string, unknown> {
  const entry = schemaById.get(idOrFile);
  const file = entry ? entry.file : idOrFile;
  // file looks like "schemas/space.schema.json"
  const tail = file.replace(/^schemas\//, "");
  return pickSchema<Record<string, unknown>>(tail);
}

export function listSchemaDocuments(): { id: string; file: string; doc: Record<string, unknown> }[] {
  return schemaEntries.map((entry) => ({
    id: entry.schema_id,
    file: entry.file,
    doc: loadSchemaDocument(entry.schema_id),
  }));
}

export function listAllSchemaDocuments(): { file: string; doc: Record<string, unknown> }[] {
  return Object.entries(schemaFiles)
    .map(([path, doc]) => ({
      file: `schemas/${fileEnd(path)}`,
      doc,
    }))
    .sort((a, b) => a.file.localeCompare(b.file));
}

// --- fixture loading ---------------------------------------------------------

export interface FixtureEntry {
  name: string;
  data: Record<string, unknown>;
}

export const fixtures: FixtureEntry[] = Object.entries(fixtureFiles)
  .map(([path, data]) => ({ name: fileEnd(path).replace(/\.json$/, ""), data }))
  .sort((a, b) => a.name.localeCompare(b.name));

// --- OpenAPI -----------------------------------------------------------------

export function readOpenApiYaml(): string {
  const key = Object.keys(openapiFiles)[0];
  if (!key) throw new Error("no openapi yaml under spec/v1/artifacts/openapi/");
  return openapiFiles[key];
}

export function readBindingsYaml(): string {
  const key = Object.keys(bindingFiles).find((p) => /non-http-bindings/.test(p));
  if (!key) throw new Error("non-http-bindings.yaml missing");
  return bindingFiles[key];
}
