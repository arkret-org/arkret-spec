# teabay Directory Service Baseline

- Report ID: `teabay-directory-service-baseline-2026-05-10`
- Profile: `cx.profile.directory_service.v1`
- Implementation: `teabay 0.1.0`
- Generated: `2026-05-10T18:10:58+08:00`
- Status: baseline passed, with pull/divergence coverage still partial.

## Verified Commands

| Check | Command | Result |
| --- | --- | --- |
| teabay unit + local integration | `cargo test` | passed |
| Docker-backed conformance | `TEABAY_RUN_DOCKER_TESTS=1 cargo test --test it -- --nocapture` | passed |
| Admin wasm compile | `cargo check --manifest-path teabay-admin/Cargo.toml --target wasm32-unknown-unknown` | passed |
| Shared fixtures crate | `cargo check --manifest-path teabay-testing/Cargo.toml` | passed |
| cotest compile | `cargo test --test directory_service --no-run` | passed |
| cotest skip path | `cargo test --test directory_service -- --nocapture` | passed with skip when no Directory service is attached |

## Coverage

| Area | Status | Evidence |
| --- | --- | --- |
| Directory describe / profile discovery | implemented | `tests/it/conformance.rs`, `../cotest/src/scenarios/directory_service.rs` |
| Query face | implemented | search / resolve realms, organizations, actors, users, handles |
| Anti-enumeration visibility | implemented | secret and unauthorized restricted realms collapse to `not_found`; authorized restricted resolution succeeds |
| Realm pagination | implemented | keyset cursor survives hidden restricted candidates |
| Push ingest verify chain | implemented | signed discovery proof, directory authorization, source-ref fetch against mock Principal Server, open accept policy, persistence |
| Private Contact Discovery | implemented | RFC 9497 blind/match smoke over seeded contact fixture |
| Operator admin surface | implemented | allowlist CRUD, audit feed, resource browser, operator takedown |
| Pull revalidation worker | partial | worker exists; no mock Principal Server pull scenario in this report |
| Divergence worker | partial | HTTPS polling exists; DID service-resolution hardening remains tracked in teabay M6 notes |

## Notes

The cotest hook now includes `cx.profile.directory_service.v1` and a `teabay_directory_service_profile_is_discoverable` scenario. The scenario can attach to a running Directory with `TEABAY_BASE_URL` or spawn `../teabay/target/debug/teabay` when `DATABASE_URL` is supplied.

Shared Directory SQL fixtures live in `../teabay/teabay-testing` so cotest can reuse seeded resource rows without copying them.
