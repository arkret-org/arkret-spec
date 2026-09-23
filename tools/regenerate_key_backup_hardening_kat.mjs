#!/usr/bin/env node
// Rebuild the key-backup AEAD and unlock-proof cryptographic KAT from §7.2.
import { readFileSync, writeFileSync } from 'node:fs';
import { createCipheriv, createDecipheriv, createHash, createPrivateKey, createPublicKey, sign, verify } from 'node:crypto';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';

const root = resolve(fileURLToPath(new URL('..', import.meta.url)));
const path = resolve(root, 'spec/v1/artifacts/fixtures/key-backup-hardening-fixture.json');
const original = readFileSync(path, 'utf8');
const fixture = JSON.parse(original);
const vector = fixture.cases.find(c => c.name === 'unlock_proof');
const seed = Buffer.from([...Array(32).keys()]); // registered conformance_ed25519_fixture_key
const privateKey = createPrivateKey({ key: Buffer.concat([Buffer.from('302e020100300506032b657004220420', 'hex'), seed]), format: 'der', type: 'pkcs8' });
const publicKey = createPublicKey(privateKey);
const publicBytes = publicKey.export({ format: 'der', type: 'spki' }).subarray(-32);
const material = JSON.parse(readFileSync(resolve(root, 'spec/v1/artifacts/registry/test-material-registry.json'), 'utf8'));
const registered = material.published_signing_material.find(row => row.id === 'conformance_ed25519_fixture_key');
if (!registered || registered.fingerprint !== 'sha256:' + createHash('sha256').update(publicBytes).digest('hex')
    || !registered.source_fixtures.includes('spec/v1/artifacts/fixtures/key-backup-hardening-fixture.json')) {
  throw Error('offline Ed25519 key is not bound to the formal test-material registry');
}
const b64u = bytes => Buffer.from(bytes).toString('base64url');
const canonical = value => JSON.stringify(value, (_key, item) => item && !Array.isArray(item) && typeof item === 'object'
  ? Object.fromEntries(Object.entries(item).sort(([a], [b]) => a < b ? -1 : a > b ? 1 : 0)) : item);
function base58(bytes) {
  const alphabet = '123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz';
  let n = BigInt('0x' + Buffer.from(bytes).toString('hex'));
  let s = '';
  while (n) { s = alphabet[Number(n % 58n)] + s; n /= 58n; }
  return '1'.repeat([...bytes].findIndex(b => b !== 0)) + s;
}
const multikey = 'z' + base58(Buffer.concat([Buffer.from([0xed, 0x01]), publicBytes]));
const did = 'did:key:' + multikey;
const old = vector.envelope;
// The fixed vector is a genesis envelope: plaintext metadata must agree with it.
vector.plaintext.series_seq = 0;
const item = vector.plaintext.items[0];
const contents = [{ item_kind: item.item_kind, secret_id: item.secret_id }];
const encryption = { recipient_method: 'secret_storage_key', recipient_key_ref: 'ak.secret_storage.v1', aead: { name: 'chacha20_poly1305', nonce: vector.crypto_transcript.nonce_b64u } };
const envelope = {
  backup_id: old.backup_id, actor_id: old.actor_id, backup_kind: old.backup_kind,
  backup_version: 'kb_hardening_kat', series_id: old.series_id, series_seq: 0,
  created_at: old.created_at, encryption, domain_separation: { subdomain: 'key_backup' },
  contents, ciphertext: '', ciphertext_digest: '',
  auth_data: {
    device_id: vector.session.requesting_device_id,
    verification_method: did + '#' + multikey,
    signature_algorithm: 'Ed25519', signature: '',
    device_authorize_event_id: 'ak:event:AQJmSg1s9QyzppFeJL40dN92YVHZeLdBBt3UWHa9XNOD'
  }
};
const aad = canonical({
  schema: 'ak.schema.key_backup.v1', actor_id: envelope.actor_id, device_id: null,
  backup_kind: envelope.backup_kind, backup_version: envelope.backup_version,
  created_at: envelope.created_at, item_kinds: [...new Set(contents.map(c => c.item_kind))].sort(),
  recipient_method: encryption.recipient_method, recipient_key_ref: encryption.recipient_key_ref
});
const plaintext = canonical(vector.plaintext);
const key = Buffer.from(vector.crypto_transcript.key_b64u, 'base64url');
const nonce = Buffer.from(encryption.aead.nonce, 'base64url');
const cipher = createCipheriv('chacha20-poly1305', key, nonce, { authTagLength: 16 });
cipher.setAAD(Buffer.from(aad));
const encrypted = Buffer.concat([cipher.update(plaintext), cipher.final()]);
const tag = cipher.getAuthTag();
const combined = Buffer.concat([encrypted, tag]);
const digest = 'sha256:' + createHash('sha256').update(combined).digest('hex');
envelope.ciphertext = b64u(combined);
envelope.ciphertext_digest = digest;
for (const field of ['backup_id', 'backup_kind', 'series_id', 'series_seq']) {
  if (envelope[field] !== vector.plaintext[field]) throw Error(`plaintext/envelope ${field} mismatch`);
}
if (canonical(contents) !== canonical(vector.plaintext.items.map(({ item_kind, secret_id }) => ({ item_kind, secret_id })))) {
  throw Error('plaintext/public contents mismatch');
}
const envelopeUnsigned = structuredClone(envelope);
delete envelopeUnsigned.auth_data.signature;
envelope.auth_data.signature = b64u(sign(null, Buffer.from(canonical(envelopeUnsigned)), privateKey));
vector.envelope = envelope;
vector.session.requesting_device_public_key_did = did;
vector.proof.ciphertext_digest = digest;
vector.proof.auth_data.verification_method = did + '#' + multikey;
const proofUnsigned = structuredClone(vector.proof);
delete proofUnsigned.auth_data.signature;
vector.proof.auth_data.signature = b64u(sign(null, Buffer.from(canonical(proofUnsigned)), privateKey));
vector.test_key = {
  algorithm: 'Ed25519', private_key_seed: b64u(seed), public_key: b64u(publicBytes),
  note: 'Public offline conformance key registered in test-material-registry.json; live authorization MUST reject it as test_material_denied.'
};
vector.crypto_transcript = {
  fixture_kind: 'cryptographic_transcript', aead: 'chacha20_poly1305',
  key_b64u: b64u(key), nonce_b64u: b64u(nonce), aad_canonical_json: aad,
  plaintext_canonical_json: plaintext, ciphertext_b64u: b64u(encrypted), tag_b64u: b64u(tag),
  ciphertext_and_tag_b64u: b64u(combined), ciphertext_digest: digest, tag_length_bytes: 16,
  envelope_signing_jcs: canonical(envelopeUnsigned), proof_signing_jcs: canonical(proofUnsigned)
};
vector.expected.valid_unlock = 'test_material_denied';
vector.expected.cryptographic_envelope_signature = 'valid';
vector.expected.cryptographic_proof_signature = 'valid';
vector.expected.cryptographic_aead_open = 'valid';
vector.assertions = vector.assertions.map(a => a.includes('the real Ed25519 signature')
  ? 'The published Ed25519 key proves offline transcript validity; live authorization rejects this key as test_material_denied.' : a);
fixture.generated_by = 'tools/regenerate_key_backup_hardening_kat.mjs';

// Independent cryptographic checks, including negative mutation controls.
const open = (aadBytes, encryptedBytes) => {
  const decipher = createDecipheriv('chacha20-poly1305', key, nonce, { authTagLength: 16 });
  decipher.setAAD(Buffer.from(aadBytes));
  decipher.setAuthTag(encryptedBytes.subarray(-16));
  return Buffer.concat([decipher.update(encryptedBytes.subarray(0, -16)), decipher.final()]).toString();
};
if (open(aad, combined) !== plaintext) throw Error('AEAD positive control failed');
for (const [changedAad, changedBytes] of [[aad + ' ', combined], [aad, Buffer.concat([Buffer.from([combined[0] ^ 1]), combined.subarray(1)])]]) {
  try { open(changedAad, changedBytes); throw Error('AEAD mutation accepted'); } catch (e) { if (e.message === 'AEAD mutation accepted') throw e; }
}
for (const [payload, signature] of [[canonical(envelopeUnsigned), envelope.auth_data.signature], [canonical(proofUnsigned), vector.proof.auth_data.signature]]) {
  if (!verify(null, Buffer.from(payload), publicKey, Buffer.from(signature, 'base64url'))) throw Error('Ed25519 positive control failed');
  if (verify(null, Buffer.from(payload + ' '), publicKey, Buffer.from(signature, 'base64url'))) throw Error('Ed25519 mutation accepted');
}
const generated = JSON.stringify(fixture, null, 2) + '\n';
if (process.argv.includes('--check')) {
  if (original !== generated) { console.error('key-backup hardening KAT drift; regenerate with node tools/regenerate_key_backup_hardening_kat.mjs'); process.exit(1); }
  console.log('key-backup hardening KAT: exact §7.2 AEAD, signatures, and negative mutations OK');
} else {
  writeFileSync(path, generated);
  console.log('regenerated key-backup hardening KAT');
}
