"""Rename Cokret-defined legacy cx- / cx_ brand identifiers to ck- / ck_.
Dev-phase brand cleanup (no installed base). Excludes the registries that
intentionally record the legacy names (handled manually) and meta refs."""
import os

# prefix -> replacement; distinctive enough for plain substring replace
PREFIXES = [
    ("cx-rtc-", "ck-rtc-"),
    ("cx-identity-link", "ck-identity-link"),
    ("cx-cross-signing-", "ck-cross-signing-"),
    ("cx-did-continuity-", "ck-did-continuity-"),
    ("cx-device-trust-", "ck-device-trust-"),
    ("cx-aad-event-ref", "ck-aad-event-ref"),
    ("cx-challenge-", "ck-challenge-"),
    ("cx_rtc_", "ck_rtc_"),
    ("cx_principal_signing", "ck_principal_signing"),
    ("cx_self_signing", "ck_self_signing"),
    ("cx_user_signing", "ck_user_signing"),
    ("cx_device_", "ck_device_"),
    ("cx_pseudonym_call_", "ck_pseudonym_call_"),
    ("cx_push_pseudo_", "ck_push_pseudo_"),
    ("cx_chal_", "ck_chal_"),
]
EXCLUDE = {
    os.path.normpath("spec/v1/artifacts/registry/legacy-cx-name-allowlist.json"),
    os.path.normpath("spec/v1/artifacts/registry/exporter-label-registry.json"),
    os.path.normpath("spec/v1/artifacts/registry/renames.json"),
    os.path.normpath("spec/v1/artifacts/registry/forbidden-model-terms.json"),
}
EXTS = (".json", ".md", ".mdx", ".yaml", ".yml")
ROOTS = ["spec/v1/zh", "spec/v1/artifacts"]

total = 0
touched = {}
for root_dir in ROOTS:
    for root, _, fs in os.walk(root_dir):
        for f in fs:
            if not f.endswith(EXTS):
                continue
            p = os.path.join(root, f)
            if os.path.normpath(p) in EXCLUDE:
                continue
            txt = open(p, encoding="utf-8", newline="").read()
            orig = txt
            c = 0
            for old, new in PREFIXES:
                n = txt.count(old)
                if n:
                    txt = txt.replace(old, new); c += n
            if txt != orig:
                open(p, "w", encoding="utf-8", newline="").write(txt)
                touched[p] = c; total += c

print(f"renamed {total} occurrences across {len(touched)} files")
for p, c in sorted(touched.items(), key=lambda kv: -kv[1]):
    print(f"   {c:4d}  {p}")
