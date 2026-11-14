import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

const artifacts = new URL('../../spec/v1/artifacts/', import.meta.url);
const read = path => JSON.parse(readFileSync(fileURLToPath(new URL(path, artifacts)), 'utf8'));

// Route aliases are generated from the same canonical rows as the rendered pages.
export function catalogRedirects() {
  const errors = read('registry/error-code-registry.json');
  const profiles = read('profiles/conformance-profiles.json');
  const groups = {
    'event-kinds': read('registry/event-kind-registry.json').event_kinds.map(row => row.event_kind),
    errors: [...errors.codes, ...(errors.reason_codes ?? [])].map(row => row.code),
    operations: read('registry/operation-registry.json').operations.map(row => row.operation_id),
    schemas: read('registry/schema-registry.json').schemas.map(row => row.schema_id),
    profiles: ['implementation_profiles', 'deployment_profiles', 'vector_groups', 'hardening_profiles'].flatMap(key => profiles[key] ?? []),
  };
  const redirects = { '/openapi/': '/zh/openapi/', '/en/openapi/': '/zh/openapi/', '/en/guide/': '/zh/guide/' };
  for (const [kind, ids] of Object.entries(groups)) {
    for (const prefix of ['', '/en']) {
      redirects[`${prefix}/catalog/${kind}/`] = `/zh/catalog/${kind}/`;
      for (const id of new Set(ids)) {
        const tail = `${kind}/${encodeURIComponent(id)}/`;
        redirects[`${prefix}/catalog/${tail}`] = `/zh/catalog/${tail}`;
      }
    }
  }
  return redirects;
}
