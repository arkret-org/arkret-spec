"""Byte-exact reference primitives for the recoverable application contract."""
import base64
import hashlib
import hmac
import json
import unicodedata
from datetime import datetime

from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.ciphers.aead import ChaCha20Poly1305
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

ROOT_LABEL = "ak.epoch-content-root-v1"
CONTENT_LABEL = "ak.content-v1"
SCHEME = "ak.encryption.epoch_content_aead.v1"
STRATEGY = "ak.encryption_backup.epoch_content_roots.v1"


def jcs(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()


def b64(value):
    return base64.urlsafe_b64encode(value).decode().rstrip("=")


def did_key(public, codec):
    raw = codec + public
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
    number, encoded = int.from_bytes(raw, "big"), ""
    while number:
        number, digit = divmod(number, 58)
        encoded = alphabet[digit] + encoded
    multikey = "z" + encoded
    return "did:key:" + multikey + "#" + multikey


def unb64(value):
    raw = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))
    if b64(raw) != value:
        raise ValueError("noncanonical binary encoding")
    return raw


def vector_prefix(length):
    if length < 64:
        return bytes([length])
    if length < 16384:
        return (length | 0x4000).to_bytes(2, "big")
    if length < 1 << 30:
        return (length | 0x80000000).to_bytes(4, "big")
    raise ValueError("MLS vector too long")


def expand(secret, label, context, length):
    full_label = b"MLS 1.0 " + label.encode("ascii")
    info = length.to_bytes(2, "big") + vector_prefix(len(full_label)) + full_label + vector_prefix(len(context)) + context
    previous = b""
    output = b""
    for counter in range(1, 256):
        previous = hmac.new(secret, previous + info + bytes([counter]), "sha256").digest()
        output += previous
        if len(output) >= length:
            return output[:length]
    raise ValueError("HKDF length")


def content_root(exporter_secret, root_context):
    derived = expand(exporter_secret, ROOT_LABEL, b"", 32)
    return expand(derived, "exported", hashlib.sha256(jcs(root_context)).digest(), 32)


def root_ref(root, context):
    return "sha256:" + hashlib.sha256(b"ak.content.root_ref.v1\n" + jcs(context) + root).hexdigest()


def content_key(root, context, length=16):
    return expand(root, CONTENT_LABEL, hashlib.sha256(jcs(context)).digest(), length)


def key_commitment(key, context):
    return "sha256:" + hashlib.sha256(b"ak.content.key_commitment.v1\n" + jcs(context) + key).hexdigest()


def content_outer_event(event):
    return {k: v for k, v in event.items() if k not in {"event_id", "payload", "producer_proof", "unsigned"}}


def content_outer_event_digest(event):
    return "sha256:" + hashlib.sha256(jcs(content_outer_event(event))).hexdigest()


def verify_local_message_binding(intent, original_event, actual_producer):
    """Byte binding only; actual producer qualification is a native caller obligation."""
    content = intent["content"]
    context = content["encryption_context"]
    expected_actor = original_event.get("executed_by", original_event["actor_id"])
    if (content["kind"] != "mls" or context["scheme"] != SCHEME
            or context["effective_scope"] != original_event["scope_ref"]
            or context["producer"] != actual_producer
            or actual_producer["actor_id"] != expected_actor
            or context["sender_domain"] != jcs(actual_producer["actor_id"]).decode()
            or context["outer_event_digest"] != content_outer_event_digest(original_event)):
        raise ValueError("local encrypted context differs from its frozen Event or actual producer")
    body = content["encrypted_content"]
    envelopes = [body]
    if "encrypted_metadata" in content:
        envelopes.append(content["encrypted_metadata"])
    for envelope in envelopes:
        if (envelope["encryption_scheme"] != context["scheme"]
                or any(envelope["encryption_context"][field] != body["encryption_context"][field]
                       for field in ["epoch", "group_state_ref", "root_ref"])):
            raise ValueError("local encrypted message mixes construction or original group state")
    if len({e["encryption_context"]["content_key_salt"] for e in envelopes}) != len(envelopes):
        raise ValueError("local encrypted content slots reuse the same key derivation domain")


def aad(outer_event, envelope, context):
    frozen = content_outer_event(outer_event)
    metadata = {k: v for k, v in envelope.items() if k != "ciphertext"}
    return jcs({"outer_event": frozen, "envelope": metadata, "content_context": context})


def _hkdf_expand(prk, info, length):
    output = previous = b""
    for counter in range(1, 256):
        previous = hmac.new(prk, previous + info + bytes([counter]), "sha256").digest()
        output += previous
        if len(output) >= length:
            return output[:length]
    raise ValueError("HKDF length")


def _extract(suite, salt, label, ikm):
    return hmac.new(salt, b"HPKE-v1" + suite + label + ikm, "sha256").digest()


def _labeled_expand(suite, prk, label, info, length):
    return _hkdf_expand(prk, length.to_bytes(2, "big") + b"HPKE-v1" + suite + label + info, length)


def hpke_context(dh, enc, pk_r, info):
    """RFC 9180 base mode, KEM=0x20, KDF=1, AEAD=3, sequence zero."""
    kem_suite = b"KEM\x00\x20"
    shared = _labeled_expand(kem_suite, _extract(kem_suite, b"", b"eae_prk", dh), b"shared_secret", enc + pk_r, 32)
    suite = b"HPKE\x00\x20\x00\x01\x00\x03"
    context = b"\x00" + _extract(suite, b"", b"psk_id_hash", b"") + _extract(suite, b"", b"info_hash", info)
    secret = _extract(suite, shared, b"secret", b"")
    return _labeled_expand(suite, secret, b"key", context, 32), _labeled_expand(suite, secret, b"base_nonce", context, 12)


def hpke_seal(sk_e, pk_r, info, plaintext, associated=None):
    ephemeral = X25519PrivateKey.from_private_bytes(sk_e)
    enc = ephemeral.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    key, nonce = hpke_context(ephemeral.exchange(X25519PublicKey.from_public_bytes(pk_r)), enc, pk_r, info)
    return enc + ChaCha20Poly1305(key).encrypt(nonce, plaintext, info if associated is None else associated)


def hpke_open(sk_r, sealed, info, associated=None):
    if len(sealed) < 48:
        raise ValueError("truncated HPKE encapsulation")
    recipient = X25519PrivateKey.from_private_bytes(sk_r)
    pk_r = recipient.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    enc, ciphertext = sealed[:32], sealed[32:]
    key, nonce = hpke_context(recipient.exchange(X25519PublicKey.from_public_bytes(enc)), enc, pk_r, info)
    return ChaCha20Poly1305(key).decrypt(nonce, ciphertext, info if associated is None else associated)


def mnemonic_backup_key(mnemonic, passphrase=""):
    """Reference derivation after BIP39 checksum/word validation by the caller."""
    text = unicodedata.normalize("NFKD", mnemonic).encode()
    salt = b"mnemonic" + unicodedata.normalize("NFKD", passphrase).encode()
    seed = hashlib.pbkdf2_hmac("sha512", text, salt, 2048, 64)
    prk = hmac.new(b"arkret-identity-recovery-kdf-v1", seed, "sha256").digest()
    ikm = _hkdf_expand(prk, b"arkret/backup-hpke/v1", 32)
    suite = b"KEM\x00\x20"
    raw = bytearray(_labeled_expand(suite, _extract(suite, b"", b"dkp_prk", ikm), b"sk", b"", 32))
    raw[0] &= 248
    raw[31] = (raw[31] & 127) | 64
    private = bytes(raw)
    public = X25519PrivateKey.from_private_bytes(private).public_key().public_bytes(Encoding.Raw, PublicFormat.Raw)
    return private, public


def grant_header(grant, selector):
    fields = ("recipient", "recipient_hpke_key_base64url", "recipient_key_event_ref", "history_cut", "expires_at")
    return jcs({**{k: grant[k] for k in fields}, "selector": selector})


def qualify_history_request(request, signer_actor, signer_endpoint, signer_authorization,
                            current_leaf, current_read, created_at, now):
    """Compose independently native-verified signer, leaf and read facts.

    These inputs are not caller claims or a native provenance verifier. The
    Event signature key was verified independently; it need not be the MLS key.
    """
    fields = {"recipient", "recipient_hpke_key_base64url", "history_cut", "expires_at"}
    if set(request) != fields or not current_read or request["recipient"] != current_leaf:
        raise ValueError("not the exact current readable endpoint")
    recipient = request["recipient"]
    if (recipient["actor_id"], recipient["endpoint"], recipient["authorization_event_ref"]) != (
            signer_actor, signer_endpoint, signer_authorization):
        raise ValueError("request signer differs from native leaf ownership")
    moment = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    created, current, expiry = map(moment, (created_at, now, request["expires_at"]))
    if not created <= current < expiry or not 0 < (expiry - created).total_seconds() <= 900:
        raise ValueError("request is outside its validity window")
    public = unb64(request["recipient_hpke_key_base64url"])
    if len(public) != 32 or b64(public) != request["recipient_hpke_key_base64url"]:
        raise ValueError("invalid canonical recipient key")
    # A fresh local validation scalar rejects low-order/zero DH inputs. It
    # neither issues a grant nor replaces native caller authorization.
    X25519PrivateKey.generate().exchange(X25519PublicKey.from_public_bytes(public))
    return recipient


def qualify_history_grant(grant, accepted_request_ref, accepted_request,
                          signer_actor, signer_endpoint, signer_authorization,
                          current_leaf, recipient_read, issuer_disclose,
                          selection_authorized, request_created_at, now):
    """New issuance/delivery only, using independently native-qualified facts.

    This is not the current-holder archival scan of historical PCR originals.
    """
    fields = {"recipient", "recipient_hpke_key_base64url", "recipient_key_event_ref",
              "history_cut", "expires_at", "entries"}
    if set(grant) != fields or not issuer_disclose or not selection_authorized:
        raise ValueError("no current disclosure authority for this selection")
    if grant["recipient_key_event_ref"] != accepted_request_ref or any(
            grant[key] != accepted_request[key] for key in
            ("recipient", "recipient_hpke_key_base64url", "history_cut", "expires_at")):
        raise ValueError("grant differs from its original accepted request")
    return qualify_history_request(accepted_request, signer_actor, signer_endpoint,
                                   signer_authorization, current_leaf, recipient_read,
                                   request_created_at, now)


def coverage_pages(scope, genesis, cut, entries, backup_refs):
    positions = [row["source"]["stream_position"] for row in entries]
    if positions != list(range(cut["stream_position"] + 1)):
        raise ValueError("coverage is not the exact genesis-to-cut prefix")
    if any(row["source"]["stream_ref"] != scope for row in entries) or entries[-1]["source"] != cut:
        raise ValueError("coverage scope/cut mismatch")
    if entries[0]["source"]["event_id"] != genesis:
        raise ValueError("coverage genesis mismatch")
    if len({row["source"]["event_id"] for row in entries}) != len(entries):
        raise ValueError("duplicate original")
    pages = []
    previous = None
    for offset in range(0, len(entries), 256):
        selected = []
        for row in entries[offset:offset + 256]:
            selected.append({"source": row["source"], "root_refs": sorted(set(row["root_refs"])), "blob_refs": sorted(set(row["blob_refs"]))})
        refs = sorted({ref for row in selected for ref in backup_refs[row["source"]["event_id"]]})
        page = {"effective_scope": scope, "genesis_event_ref": genesis, "cut": cut, "entries": selected,
                "backup_refs": refs, "previous_page_digest": previous}
        page["page_digest"] = "sha256:" + hashlib.sha256(jcs(page)).hexdigest()
        pages.append(page)
        previous = page["page_digest"]
    return pages


def inventory_digest(inventory):
    entries = inventory["entries"]
    keys = [jcs({"effective_scope": row["effective_scope"], "genesis_event_ref": row["genesis_event_ref"]}) for row in entries]
    if keys != sorted(set(keys)):
        raise ValueError("inventory must be unique and canonically ordered")
    for entry in entries:
        indices = [leaf["leaf_index"] for leaf in entry["old_leaves"]]
        if indices != sorted(set(indices)):
            raise ValueError("old leaves must be unique and ordered")
        if any(leaf["endpoint"]["signature_key_base64url"] == inventory["replacement"]["signature_key_base64url"] for leaf in entry["old_leaves"]):
            raise ValueError("replacement reused an old endpoint signer")
    return "sha256:" + hashlib.sha256(b"ak.content.recovery_inventory.v1\n" + jcs(inventory)).hexdigest()


def cleanup_digest(inventory, results):
    expected = [(x["effective_scope"], x["genesis_event_ref"]) for x in inventory["entries"]]
    actual = [(x["effective_scope"], x["genesis_event_ref"]) for x in results]
    if actual != expected:
        raise ValueError("missing, reordered or unfinished cleanup")
    for entry, result in zip(inventory['entries'], results):
        if result.get('state') == 'rekeyed':
            if (result.get('remaining_old_leaf_count') != 0 or not result.get('root_refs')
                    or not result.get('backup_refs') or 'winning_commit' not in result
                    or 'retirement_proof' in result):
                raise ValueError('unfinished rekeyed cleanup')
        elif result.get('state') in {'removed', 'terminated'}:
            from tools.recovery_scope_cleanup import digest
            proof = result.get('retirement_proof', {})
            if (set(result) != {'state', 'effective_scope', 'genesis_event_ref', 'retirement_proof'}
                    or proof.get('state') != result['state']
                    or proof.get('replacement') != inventory['replacement']
                    or proof.get('inventory_digest') != inventory_digest(inventory)
                    or proof.get('inventory_entry_digest') != digest(entry)
                    or any(proof.get(k) != entry[k] for k in ('effective_scope', 'genesis_event_ref'))
                    or 'signature' not in proof):
                raise ValueError('retirement does not bind the exact inventory entry')
        else:
            raise ValueError('unknown cleanup state')
    # This structural digest does not verify native facts or signatures.
    value = {"inventory_digest": inventory_digest(inventory), "scope_cleanups": results}
    return "sha256:" + hashlib.sha256(b"ak.content.cleanup_inventory.v1\n" + jcs(value)).hexdigest()


def verify_preparation_resource(resource, authorization, replacement, pcr_cut, previous=None):
    """Bind wire progress to independently qualified native source inputs.

    This checks episode continuity only. It does not qualify a holder, prove
    native census completeness, fetch/verify a Blob or attest plaintext ready.
    """
    expected = {"state", "replacement", "pcr_cut"}
    state = resource.get("state")
    if state == "prepared":
        expected.add("inventory_blob_ref")
    elif state != "pending":
        raise ValueError("unknown preparation state")
    if set(resource) != expected:
        raise ValueError("missing or extra preparation fields")
    if replacement["actor_id"].get("kind") != "account" or replacement["authorization_event_ref"] != authorization:
        raise ValueError("wrong native replacement source")
    if resource["replacement"] != replacement or resource["pcr_cut"] != pcr_cut:
        raise ValueError("preparation differs from original episode")
    if previous is not None:
        verify_preparation_resource(previous, authorization, replacement, pcr_cut)
        if previous["state"] == "prepared" and (state != "prepared" or resource["inventory_blob_ref"] != previous["inventory_blob_ref"]):
            raise ValueError("prepared inventory cannot roll back or rebind")


def verify_root_index(envelope, plaintext):
    for field in ("backup_id", "backup_kind", "series_id", "series_sequence"):
        if envelope[field] != plaintext[field]:
            raise ValueError("backup identity mismatch")
    items = plaintext["items"]
    if len({x["secret_id"] for x in items}) != len(items):
        raise ValueError("duplicate secret id")
    projection = []
    for item in items:
        if item["item_kind"] != "content_epoch_root":
            raise ValueError("history block contains another secret class")
        if root_ref(unb64(item["root_base64url"]), item["root_context"]) != item["root_ref"]:
            raise ValueError("root commitment mismatch")
        projection.append({k: v for k, v in item.items() if k != "root_base64url"})
    if projection != envelope["contents"]:
        raise ValueError("public root index mismatch")


def authorize_history_read(proof, challenge, current, source, envelope):
    """Reference decision over independently native-verified source/current facts.

    This verifies the real intent signature, not native DID/ledger provenance.
    """
    if "nonce" in proof or "nonce" in challenge:
        raise ValueError("backup challenges have one random value")
    if proof["kind"] != "current_device" or proof["account_id"] != current["actor_id"]["account_id"]:
        raise ValueError("not the current holder")
    if proof["requesting_device_id"] != current["device_id"] or current["authorized_generation"] != current["generation"]:
        raise ValueError("old or different device")
    if current["lifecycle"] != "active":
        raise ValueError("revoked current authority")
    moment = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    now = moment(current["now"])
    if not moment(challenge["issued_at"]) <= moment(proof["issued_at"]) <= now <= moment(proof["expires_at"]) <= moment(challenge["expires_at"]):
        raise ValueError("expired challenge or intent")
    if (moment(challenge["expires_at"]) - moment(challenge["issued_at"])).total_seconds() > 300:
        raise ValueError("challenge window too long")
    if proof["signature_proof"]["verification_method"] != current["verification_method"]:
        raise ValueError("wrong current signer")
    for field in ("account_id", "requesting_device_id", "backup_id", "series_id", "ciphertext_digest", "challenge_id", "challenge", "audience", "service_id", "content_history"):
        if proof.get(field) != challenge.get(field):
            raise ValueError("challenge intent mismatch")
    for field in ("subject_actor_id", "custody_authorization_ref"):
        if proof.get(field) != challenge.get(field):
            raise ValueError("challenge custody mismatch")
    target = proof.get("subject_actor_id", current["actor_id"])
    if target != source["subject_actor_id"] or target != envelope["actor_id"]:
        raise ValueError("wrong subject")
    if target != current["actor_id"]:
        if envelope.get("custodian_actor_id") != current["actor_id"] or proof.get("custody_authorization_ref") != current.get("custody_authorization_ref") or envelope.get("custody_authorization_ref") != proof.get("custody_authorization_ref") or current.get("custody_subject_actor_id") != target or not proof.get("custody_authorization_ref"):
            raise ValueError("no current custody")
        if any(row["root_context"]["effective_scope"] != source["reference"]["stream_ref"] for row in envelope["contents"]):
            raise ValueError("custody block includes a foreign scope")
    for field in ("backup_id", "series_id", "ciphertext_digest"):
        if proof[field] != envelope[field]:
            raise ValueError("wrong immutable object")
    history = proof["content_history"]
    if history["source"] != source["reference"]:
        raise ValueError("wrong original source")
    requested = set(history["root_refs"])
    available = {row.get("root_ref") for row in envelope["contents"] if row["item_kind"] == "content_epoch_root"}
    if not requested or not requested <= set(source["protection"]["root_refs"]) or not requested <= available:
        raise ValueError("unprotected or missing root")
    if envelope["backup_id"] not in source["protection"]["backup_refs"] and envelope["backup_id"] not in source.get("retained_replacement_backup_refs", []):
        raise ValueError("unverified substitute block")
    signed = {**proof, "signature_proof": {k: v for k, v in proof["signature_proof"].items() if k != "signature"}}
    Ed25519PublicKey.from_public_bytes(unb64(current["public_key_base64url"])).verify(unb64(proof["signature_proof"]["signature"]), jcs(signed))
    return requested


def ordered_roster(records):
    """Canonical ordering after independent native record/RFC validation."""
    genesis = [x for x in records if x["kind"] == "genesis"]
    if len(genesis) != 1:
        raise ValueError("one genesis required")
    tail = [x for x in records if x["kind"] != "genesis"]
    def key(row):
        if row["kind"] not in ("add", "recovery"):
            raise ValueError("unknown roster source")
        return row["covering_commit"]["stream_position"], -1 if row["kind"] == "recovery" else row["consumed_proposal_ordinal"]
    keys = [key(x) for x in tail]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate roster record")
    recovery_positions = {key(x)[0] for x in tail if x["kind"] == "recovery"}
    if any(key(x)[0] in recovery_positions for x in tail if x["kind"] == "add"):
        raise ValueError("recovery Commit cannot mix ordinary Adds")
    return genesis + sorted(tail, key=key)


def verify_roster_keys(records, add_rows, recovery_rows):
    """Verify original key bindings; native participation/control is separate."""
    if records != ordered_roster(records):
        raise ValueError("noncanonical roster ordering")
    for kind, rows in (("add", add_rows), ("recovery", recovery_rows)):
        selected = [x for x in records if x["kind"] == kind]
        if len(selected) != len(rows):
            raise ValueError("missing or extra signing key")
        for original, row in zip(selected, rows):
            digest = "sha256:" + hashlib.sha256(jcs(original)).hexdigest()
            if row["record_digest"] != digest:
                raise ValueError("wrong original record binding")
            if kind == "recovery" and row["public_key_base64url"] != original["producer_signer_fact"]["public_key_base64url"]:
                raise ValueError("wrong recovery key")
            if kind == "recovery":
                event = original["commit_event"]
                leaf = recovery_path_leaf(unb64(event["payload"]["commit_base64url"]))
                replacement = event["payload"]["recovery_binding"]["replacement"]
                if leaf["actor_id"] != event.get("executed_by", event["actor_id"]) or leaf["actor_id"] != replacement["actor_id"] or leaf["signature_key_base64url"] != row["public_key_base64url"] or leaf["signature_key_base64url"] != replacement["signature_key_base64url"]:
                    raise ValueError("original recovery fact differs from RFC path leaf")
                scope = event["scope_ref"]
                name = scope["kind"]
                scope_key = scope["realm_id"] if name == "realm" else scope["circle_id"] if name == "circle" else scope["realm_id"] + "\x1f" + scope["sidecar_id"]
                expected = hashlib.sha256(b"ak.mls.group_id.v1\x00" + scope_key.encode()).hexdigest()
                if leaf["group_id_hex"] != expected:
                    raise ValueError("wrong recovery group scope")


def verify_recovery_source(record, origin_key):
    """Check source crypto after native role and method-native qualification.

    Executed-by identifies the actual producer; this function does not authorize
    delegation or decide that a resource is an accepted controlled Agent PCR.
    """
    source = record["recovery_source"]["attestation"]
    event = record["commit_event"]
    payload, binding = event["payload"], event["payload"]["recovery_binding"]
    if source["replacement"]["actor_id"] != event.get("executed_by", event["actor_id"]):
        raise ValueError("wrong original producer actor")
    if source["replacement"]["actor_id"].get("kind") != "account" or origin_key["station_id"] != source["replacement"]["actor_id"]["account_id"]["station_id"]:
        raise ValueError("origin is not the original owning Account Station")
    if source["signature"]["kid"] != origin_key["verification_method"]:
        raise ValueError("wrong original origin method")
    Ed25519PublicKey.from_public_bytes(unb64(origin_key["public_key_base64url"])).verify(
        unb64(source["signature"]["signature"]), b"ak.mls.recovery_source.v1\n" + jcs({k: v for k, v in source.items() if k != "signature"}))
    checks = {"event_ref": event["event_id"], "replacement": binding["replacement"], "effective_scope": event["scope_ref"],
              "base_group_state_ref": payload["base_group_state_ref"], "previous_epoch": payload["previous_epoch"], "inventory_digest": binding["inventory_digest"]}
    if any(source[k] != value for k, value in checks.items()):
        raise ValueError("recovery source differs from original submission")
    if binding["authorization_event_ref"] != binding["replacement"]["authorization_event_ref"] or binding["base_group_state_ref"] != payload["base_group_state_ref"] or binding["expected_epoch"] != payload["previous_epoch"]:
        raise ValueError("inconsistent original recovery binding")
    parse_time = lambda value: datetime.fromisoformat(value.replace("Z", "+00:00"))
    issued, expiry, accepted = map(parse_time, (source["attested_at"], source["expires_at"], record["covering_commit"]["committed_at"]))
    if not issued <= accepted < expiry or not 0 < (expiry - issued).total_seconds() <= 300:
        raise ValueError("source was not valid at original acceptance")
    fact_digest = "sha256:" + hashlib.sha256(jcs(record["producer_signer_fact"])).hexdigest()
    if record["covering_commit"]["producer_signer_fact_digest"] != fact_digest:
        raise ValueError("wrong original producer fact commitment")
    fact = record["producer_signer_fact"]
    if fact.get("kind") == "agent_runtime":
        actor, public, authorization, event_ref = fact["actor_id"], fact["public_key_base64url"], fact["authorization_event_ref"], fact["event_ref"]
        if source["replacement"]["endpoint"] != {"kind": "agent_runtime", "verification_method": fact["verification_method"]}:
            raise ValueError("Agent recovery cannot use a Device endpoint")
    elif "device_id" in fact:
        actor, public, authorization, event_ref = fact["actor"], fact["key"]["public_key_base64url"], fact["key"]["authorization_ref"]["event_id"], fact["event_id"]
        if source["replacement"]["endpoint"] != {"kind": "device", "device_id": fact["device_id"]}:
            raise ValueError("wrong original device endpoint")
    else:
        raise ValueError("unsupported recovery producer")
    if actor != source["replacement"]["actor_id"] or public != source["replacement"]["signature_key_base64url"] or authorization != source["replacement"]["authorization_event_ref"] or event_ref != source["event_ref"] or fact["verification_method"] != source["verification_method"] or fact["accepted_at"] != record["covering_commit"]["committed_at"]:
        raise ValueError("original signer fact differs from origin endpoint proof")


def roster_pages(records, wrap, maximum=2 * 1024 * 1024):
    """Freeze longest-prefix pages including final signed wrapper/key budgets."""
    count = 1
    seen = set()
    while count not in seen:
        seen.add(count)
        pages, offset = [], 0
        while offset < len(records):
            fitting = None
            for size in range(1, min(8, len(records) - offset) + 1):
                peer, own = wrap(records[offset:offset + size], len(pages), count)
                if max(len(jcs(peer)), len(jcs(own))) <= maximum:
                    fitting = (size, peer, own)
            if fitting is None:
                raise ValueError("complete roster record exceeds budget")
            size, peer, own = fitting
            pages.append((peer, own)); offset += size
        if len(pages) == count:
            return pages
        count = len(pages)
    raise ValueError("unstable final manifest pagination")


def verify_external_recovery_binding(binding, authenticated_data, inherited_extensions, accepted_base_extensions):
    """Reference byte binding only; native authority and RFC signatures remain mandatory."""
    from tools.regenerate_mls_governance_binding_fixture import encode
    numeric = dict(binding)
    for field in ("previous_epoch", "next_epoch", "key_access_revision"):
        value = numeric[field]
        if not isinstance(value, str) or not value.isascii() or not value.isdecimal() or str(int(value)) != value:
            raise ValueError("noncanonical binding counter")
        numeric[field] = int(value)
    if numeric["next_epoch"] != numeric["previous_epoch"] + 1:
        raise ValueError("recovery epoch differs from exact base")
    if authenticated_data != encode(numeric) or inherited_extensions != accepted_base_extensions:
        raise ValueError("External Commit binding or inherited extensions differ")


def recovery_path_leaf(wire):
    """Strict public-wire fixture reader for the v1 ExternalInit-only branch.

    Does not replace a native RFC transition, signature or authority verifier.
    """
    class Reader:
        def __init__(self, data): self.data, self.pos = data, 0
        def take(self, length):
            end = self.pos + length
            if end > len(self.data): raise ValueError("truncated MLS wire")
            value, self.pos = self.data[self.pos:end], end
            return value
        def number(self, length): return int.from_bytes(self.take(length), "big")
        def vector(self):
            first = self.number(1); width = 1 << (first >> 6)
            if width == 8: raise ValueError("reserved MLS vector width")
            length = ((first & 63) << (8 * (width - 1))) | self.number(width - 1)
            if len(vector_prefix(length)) != width: raise ValueError("nonminimal MLS vector")
            return self.take(length)
    stream = Reader(wire)
    if (stream.number(2), stream.number(2)) != (1, 1): raise ValueError("not MLS PublicMessage")
    group_id, epoch, sender = stream.vector(), stream.number(8), stream.number(1)
    if sender != 4: raise ValueError("not NewMemberCommit")
    stream.vector()
    if stream.number(1) != 3: raise ValueError("not Commit")
    proposals = Reader(stream.vector())
    if (proposals.number(1), proposals.number(2)) != (1, 6): raise ValueError("expected inline ExternalInit")
    proposals.vector()
    if proposals.pos != len(proposals.data) or stream.number(1) != 1: raise ValueError("unexpected proposal or missing path")
    encryption_key, signature_key = stream.vector(), stream.vector()
    if stream.number(2) != 1: raise ValueError("not BasicCredential")
    actor = json.loads(stream.vector())
    for _ in range(5): stream.vector()
    if stream.number(1) != 3: raise ValueError("not Commit leaf")
    stream.vector(); stream.vector(); leaf_signature = stream.vector()
    stream.vector()
    signature, confirmation = stream.vector(), stream.vector()
    if stream.pos != len(wire) or len(signature_key) != 32 or len(signature) != 64 or len(leaf_signature) != 64:
        raise ValueError("invalid public Commit framing")
    return {"group_id_hex": group_id.hex(), "epoch": str(epoch), "actor_id": actor,
            "signature_key_base64url": b64(signature_key), "encryption_key_base64url": b64(encryption_key),
            "confirmation_tag_base64url": b64(confirmation)}
