# Changelog

本文件记录 Contrix 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

本仓库当前发布 `v1.0.0` 规范稳定基线。下方条目描述的是该基线相对内部候选稿的收敛内容，
而不是相对任何先前公开稳定版本的差异。

## 变更登记模板

`v1.0.0` 之后，对 `event_kind_registry` / `schema_registry` / `id_kind_registry` /
`operation_registry` / `error_code_registry` / `conformance-profiles.json` 中任意一项的
有意变更都 MUST 在本 changelog 增加条目。每条条目按下方模板填写：

```
### [<version>] — <YYYY-MM-DD>

#### <一句话主题>

- **变更类型**: add | modify | deprecate | remove
- **影响 artifact**: <registry / schema / profile / fixture / openapi / non-http binding>
- **canonical 变更**: <在 `contract-catalog.json` 等 canonical 源中实际改了什么>
- **派生 artifact 同步**: <生成视图、fixture、OpenAPI 是否已通过 `python tools/artifact_pipeline.py generate` 重新生成；drift 由 `python tools/artifact_pipeline.py check` 在 CI 中验证>
- **conformance impact**:
  - 受影响 profile: <e.g. `core_event_store`, `chat_mvp`, ...>
  - profile tier 变化: <在 `conformance-profiles.json#profile_tiers` 中加入 / 移出 / 改 tier>
  - wire 兼容性: backward-compatible | breaking | deprecation-only
  - reader / writer 行为要求: <MUST tolerate / MUST emit / MAY ignore 等>
- **fixture / vector 变化**: <`event-envelope-negative-fixture`、`crypto-signature-fixture`、
  `*-conformance-vectors` 等是否需要重生成>
- **prose 同步**: <列出与该 artifact 对齐的 `spec/v1/zh/**/*.md` 段落>
- **迁移指南**: <对下游实现的最小变更清单；deprecation-only 时必须给出弃用窗口>
```

如果一次变更跨多个 artifact（例如同时新增 event kind + payload schema + profile gating），
单一条目中 MUST 把每个 artifact 列在 "影响 artifact" 字段中并保持原子。

只有在 changelog、profile tier 与 conformance 影响三项同时落定后，相应 PR 才被认为
满足发布门槛 — 这与 `spec/v1/zh/overview/release-readiness.md` §5.1 保持一致。

## [Unreleased]

### Round 1 cleanup pass on `_todos.md`（2026-05-20）

承接 `_codex_report.md` / `_claude_report.md` 的 P0–P2 待办，本轮一次性 close 12 项（T05、T18、T19、T20、T21、T22、T24、T25、T26、T27、T28、T30）。全部为 spec-internal 一致性、命名、cross-reference、drift artifact 与构建产物清理，不引入新协议语义。

- **变更类型**: edit + add（drift artifact / schema 字段）
- **影响 artifact**: schemas (`range-completeness-attestation`, `audit-ryw-receipt`, `event-payload`, `event-schema`, `flow`, `identity-link`, `client-sync-response`)、registries (`removed-event-kinds`, `forbidden-wire-fields`, `renames`, `operation-registry`, `contract-catalog`, `id-kind-registry`, `error-code-registry`)、`profiles/conformance-profiles.json`、`fixtures/privacy-security-fixture.json`、`bindings/non-http-bindings.yaml`、`openapi/contrix-service-api.openapi.yaml`、以及 `spec/v1/zh/**` 多个 prose 文件；site 侧 `astro.config.mjs` 与新增 `src/pages/404.astro`。
- **canonical 变更**:
  - **T05 (did:webvh outage)**：`zh/identity/identity-did.md` resolver policy 示例字段 `fallback_to_did_web` 改为 `outage_mode` + `outage_max_duration_ms`；增加 rationale 段落，明确 `fallback_to_did_web` 这种字段名 MUST `schema_violation`，避免与 §3.4 cache-only outage 语义矛盾。
  - **T18 (Move id 残留)**：`zh/authz/event-auth-state-resolution.md` OR-Set dot 语义中的 `move.id` 全部改为 `event_id`（dot 形态 `<event_id>:<effect_index>`）；prose 同步说明 v1 不存在独立 Move-typed id，dot/lattice/hash 均以 `event_id`+`event_digest` 表达。
  - **T19 (range completeness 命名)**：event kind 统一为 `cx.attestation.range_completeness`（无 `.v1`，与 `event-kind-registry.json` active 注册一致）；payload schema 仍为 `cx.schema.range_completeness_attestation.v1`。`operations-sync.md` §4.1 / §4.2 / §4.2.5、`event-and-patch.md` §5.1、`overview/glossary.md`、`error-code-registry.json` 全部对齐。
  - **T20 (`space_frontier` → `realm_frontier`)**：`schemas/range-completeness-attestation.schema.json`、`schemas/audit-ryw-receipt.schema.json`、`openapi` `EventSubmitResponse`、`zh/sync/{service-http-binding,operations-sync,federation}.md`、`zh/crypto-media/audited-e2ee.md` 全部改名；`forbidden-wire-fields.json` + `renames.json` 新增 entry 把 `space_frontier` 列为 hard-reject（context = frontier object property）。
  - **T21 (Directory operation Space → Realm)**：`cx.directory.search_spaces` → `cx.directory.search_realms`、`cx.directory.resolve_space` → `cx.directory.resolve_realm`（HTTP path 早已是 `/directory/search-realms` / `/directory/resolve-realm`，本轮把 operation_id / gRPC / MQ 全部对齐）。涉及 `operation-registry.json`、`contract-catalog.json`、`conformance-profiles.json`、`openapi`、`non-http-bindings.yaml`、`service-api-schema.mdx`、`service-http-binding.md`、`discovery-directory.md`、`transport-bindings.md`、`privacy-security-fixture.json`（含 test case 名 `hidden_space_resolve_indistinguishable` → `hidden_realm_resolve_indistinguishable`）；`renames.json` 加 hard-reject entry。
  - **T22 (章节号/链接修正)**：`relation.md` 把 5 处指向 `realm-and-space.md` 旧 §4.x 的链接改为新 §3.5 / §3.6（含锚点）；`federation.md` `anchor_profile` 引用改指 `realm-and-space.md §2.3` (Schema 字段表所在节)，且把 `[§4.4 Capability Revoke Fanout](#)` 占位改为真实锚点；`service-surface.md` §5 跳号修复 (§5.5 → §5.3, §5.6 → §5.4)，同步更新 `client-sync-response.schema.json`、`openapi`、`event-auth-state-resolution.md` 中所有 §5.5 引用。
  - **T24 (`FlowTrack.enabled`)**：`flow.schema.json` `$defs/flow_track` 增加 `enabled` (boolean, default true) 字段；`flow-and-message.md` §4.1 字段表补 `enabled` 行；prose 明确 `enabled=false` 时新写入 MUST 被 reducer 用 `track_disabled` 拒绝，不删除历史。
  - **T25 (Flow move 字段)**：`event-payload.schema.json` 与 `event-schema.json` `flow_move_payload` 中 `target_space_id` 描述补充"是 cx.flow.move payload 上唯一的目的地输入字段；`list_space_id` 是 cell value 字段名，不可在 payload 上直接出现（`additionalProperties=false` 已经会拒）"；`operations-sync.md` §9.1 prose 同步说明。
  - **T26 (`policy_sources`)**：`policy-server.md` 示例里 `policy_sources` 字符串简写改为 `{"kind": "..."}` object 形态；新增段落明确 canonical transcript 仅接受 object form。
  - **T27 (`Room` 术语)**：`overview/glossary.md` 把 `Room` 行改为 deprecated/interop-only 说明；`identity-link.schema.json` `pairwise_did` description 由 "Room-scoped DID" 改为 "Realm-scoped pairwise DID"；`id-kind-registry.json` 与 `contract-catalog.json` 对应 description 由 "Room/Realm-scoped" 改为 "Realm-scoped"（并显式提醒 'Room' 在 v1 core 已 deprecated）。
  - **T28 (`cx.message.send`)**：`removed-event-kinds.json` 新增 `cx.message.send` (hard_reject, replacement = `cx.message.create`)，使 cotest scanner / 下游 literal scanner 能把它识别为 historical draft 而非 unknown extension。
  - **T30 (site build warning)**：`site/astro.config.mjs` 加 `disable404Route: true`，新增 `site/src/pages/404.astro` 作为自定义 404 页面；消除 Starlight `getEntry('docs','404')` 在 build 时发出的 `Entry docs → 404 was not found.` 警告。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (151 event kinds, 54 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`；`python tools/lint_artifacts.py` clean；`npm run crossref` 输出 `crossref ok (151 event kinds, 54 errors, 84 operations, 54 schemas, 59 profiles)`；`cd site && npm run build` 555 pages 0 warning。
- **conformance impact**:
  - 受影响 profile: `cx.profile.directory_service.v1`、`cx.profile.privacy_security_vectors.v1`（仅 endpoint id rename，required_endpoints 列表已同步更新）；其余 profile 无变化。
  - profile tier 变化: 无。
  - wire 兼容性: **wire-breaking** — `space_frontier` 字段名、`cx.directory.search_spaces` / `cx.directory.resolve_space` operation id、`policy_sources` 字符串简写、Move dot 的 `move.id` 形态在当前 wire 上 MUST 被拒绝。新 drift entries 在 `forbidden-wire-fields.json` / `renames.json` 中标 hard_reject。
  - reader / writer 行为要求: 实现 MUST 更新 client SDK、bindings、test fixtures；不能再发送或接受旧名。OpenAPI 与 gRPC binding 中 operation method 名也变更（`Directory/SearchRealms` / `Directory/ResolveRealm`）。
- **fixture / vector 变化**: `privacy-security-fixture.json` 中 `cx.directory.resolve_space` → `cx.directory.resolve_realm`、test case `hidden_space_resolve_indistinguishable` → `hidden_realm_resolve_indistinguishable`；无新增 fixture。
- **prose 同步**: 上述每项都同步修改对应中文 normative prose。
- **迁移指南**:
  - SDK / yougen / soland / cotest：把 `space_frontier` → `realm_frontier`、`cx.directory.search_spaces|resolve_space` → `cx.directory.search_realms|resolve_realm`、`cx.message.send` 加入 hard_reject 集合；OR-Set dot 仍由 wire `event_id` 派生，旧 `move.id` 字符串生成路径 MUST 删除。
  - 文档实现者：检索 `space_frontier` / `cx.directory.search_spaces` / `cx.directory.resolve_space` / `move.id` / `cx.message.send` / `fallback_to_did_web` / `Room-scoped DID`，全部替换为对应新名。
  - site 部署：若 fork 了 `astro.config.mjs`，请同步 `disable404Route: true` + `src/pages/404.astro` 以避免 build warning。

### Realm/Space terminology inversion (wire-breaking, Round R1.x)

- Old `Space` (security boundary) → **Realm**, old `Place` (container) →
  **Space**. Affects schemas, contract-catalog, event-kind-registry,
  forbidden-* / renames drift artifacts; downstream artefacts and SDK
  bindings track the same names.

### Realm/Space 反转的 drift artifact 补录（2026-05-20）

R4.1 任务。`59ac1d4 Rework Realm and Space boundaries` 已在 spec 内把 Space (security boundary) 翻转为 Realm，把 Place (container) 翻转为 Space，并相应改了 schemas / contract-catalog / event-kind-registry / 现有 forbidden-* / renames notes。但 drift artifact 的 entries 没有补充由这次反转直接产生的废弃符号（仅改了 notes 与 replacement 文案），导致 cotest scanner 与下游 SDK 在跑 literal_scanner / drift validator 时无法识别 `cx.space.policy` (旧 security 语义) / `cx.place.*` (旧 container 语义) / `discussion_space_ref` / `Place` 这些遗留 token。本轮把它们补进 drift 三表 + renames。

- **变更类型**: add
- **影响 artifact**: `registry/removed-event-kinds.json`、`registry/forbidden-wire-fields.json`、`registry/forbidden-model-terms.json`、`registry/renames.json`
- **canonical 变更**:
  - `removed-event-kinds.json` 新增 13 条 entries，覆盖 (a) 旧 security-boundary 形态 `cx.space.{create,update,organization,policy,join_rule,history_visibility,discovery,policy_server,delivery_binding_policy}`（replacement 对应 `cx.realm.*`），以及 (b) 旧 container 形态 `cx.place.{create,update,parent,archive,restore,tombstone}`（replacement 对应 `cx.space.*`）。`cx.space.create` / `cx.space.update` 的 entry 在 notes 中显式声明：当前 `cx.space.create` 是合法的 container 事件，本条仅禁止 pre-inversion 的 security-boundary 语义形态（须通过 payload shape 区分）。
  - `forbidden-wire-fields.json` 新增 `discussion_space_ref` (context = `flow_payload`, replacement = `discussion_realm_ref`)，对应 `schemas/flow.schema.json` 当前字段。
  - `forbidden-model-terms.json` 新增 `Place` (context = `core_model_name`, replacement = `Space (container)`)，并保留既有的 `Realm(kind=list)` → `Space(kind=list)` entry（仍合规）。
  - `renames.json` 新增 17 条 entries 与上述 removed / forbidden 一一对应；其中 `cx.space.create` / `cx.space.update` 标 `migration_only` (因为同名 token 在新旧语义间复用，纯机械重命名不安全)，其余标 `hard_reject`。`cx.space.notification.audit` 也补为 `capability_action` 级别 rename，与 capability-action-registry 中现存 `cx.realm.notification.audit` 对齐。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (151 event kinds, 54 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`。drift artifact 不参与 generate 派生，本轮仅扩列 canonical entries。
- **conformance impact**:
  - 受影响 profile: 无；drift artifact 仅供 cotest scanner / 下游迁移工具消费，不进 profile machinery。
  - profile tier 变化: 无。
  - wire 兼容性: 兼容 — 反转后的当前 wire 已使用 `cx.realm.*` / `cx.space.*` (container) / `discussion_realm_ref`，本轮仅把"不应再出现"的旧名机器可读化。
  - reader / writer 行为要求: cotest scanner MUST 把新 entries 纳入 drift 报告；下游 SDK MUST 在编码前拒绝构造任何 pre-inversion token；reducer MUST 已经在 schema 校验阶段就 reject (这些字段 / kind 在当前 schema / registry 中根本不存在)。
- **fixture / vector 变化**: 无新增 fixture；既有 `event-envelope-negative-fixture.json` 在 `59ac1d4` 已对齐反转后的命名，可在后续 task 中扩 negative case 引用本轮新增 entries。
- **prose 同步**: 无 prose 改动；drift artifact 是机器可读的 source of truth，prose 部分由 `59ac1d4` 已经完成。
- **迁移指南**:
  - cotest / SDK / yougen / soland / sodmin / teabay 等下游：在 literal scanner / drift validator 中把本轮新增的 13 个 removed event kinds、1 个 forbidden wire field、1 个 forbidden model term、17 条 rename 纳入 hard-reject 集合。
  - 任何仍持有 pre-inversion 存量数据的实现：写入 forward migration 把 `cx.place.*` / `discussion_space_ref` / 旧语义 `cx.space.*` 翻译为反转后的形态后再回放，不要在 wire 上直接 emit 旧 token。

### 新增 service describe claim 等级 schema（2026-05-20）

T6.1 的协议侧落地。此前 `server/describe` / `identity/describe` / `events/describe` / `sync/describe` /
`directory/describe` / `push/describe` 仅暴露 `supported_operations`，把 endpoint 可达性、feature 实现、profile claim
混在一起。客户端无法区分某个 profile 是服务自声明的还是经过 cotest 验证的，dev / placeholder proof
posture 也容易被误标为生产 conformance。本轮在规范层把 describe response 切分为 claim level，并为
`development_mode=true` 添加 hard constraint 禁止 `verified_profiles`。

- **变更类型**: add
- **影响 artifact**: `schemas/service-describe.schema.json`、`registry/contract-catalog.json`、`registry/schema-registry.json`、`zh/sync/service-surface.md`、`zh/sync/service-http-binding.md`、`zh/overview/release-readiness.md`
- **canonical 变更**:
  - 新增 schema id `cx.schema.service_describe.v1`，绑定 `schemas/service-describe.schema.json`；required 字段 `supported_operations` / `implemented_features` / `claimed_profiles` / `verified_profiles` / `experimental_features` / `compat_surfaces`；`claimed_profiles[].claim_kind` 枚举为 `self_claimed`；`verified_profiles[].claim_kind` 枚举为 `cotest_verified` 且 required `cotest_run_id` / `artifact_hash`（`sha256:<hex>`）/ `timestamp`；`compat_surfaces[].kind` 枚举为 `matrix_passthrough` / `mimi_passthrough` / `legacy_alias` / `external_interop` / `deprecated_alias`；JSON Schema `allOf.if/then` 强制 `development_mode=true => verified_profiles=[]`。
  - `service-surface.md` 新增 §3.0 章节，定义六个 claim level 字段、约束与下游 badge 规则；§17 wire 互操作要求条目补充 claim level MUST。
  - `service-http-binding.md` §2.3 `GET /api/v1/server/describe` 响应字段集合扩充。
  - `release-readiness.md` Registry 表 `Schema` 计数 53 → 54。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 54 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`。
- **conformance impact**:
  - 受影响 profile: 无 profile-level 改动；本轮仅扩展 describe wire envelope。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible — 旧 caller 看到追加字段直接忽略；新 caller MUST 按 claim level 解读，且任何 dev / placeholder 部署 MUST 自检 `verified_profiles == []`。
  - reader / writer 行为要求: 服务 MUST 同时输出六个 claim level 字段，且 dev mode 下 `verified_profiles` 强制为空；客户端 / sodmin / cotest validator MUST 按 claim level 渲染 badge 与 conformance 判断，不得把 `supported_operations` / `implemented_features` 当成 profile claim。
- **fixture / vector 变化**: 后续 cotest profile validator fixture（T6.1 验收）将基于本 schema 派生 negative case（dev_mode=true 但 verified_profiles 非空 / claimed_profiles 用 cotest_verified claim_kind 等）。
- **prose 同步**: `spec/v1/zh/sync/service-surface.md` §3.0（新增）+ §17；`spec/v1/zh/sync/service-http-binding.md` §2.3 表格；`spec/v1/zh/overview/release-readiness.md` Registry 表。
- **迁移指南**:
  - 服务实现：在 describe handler 中追加六个字段；把旧 `supported_profiles` / 自声明 profile 重命名为 `claimed_profiles[{profile_id, claim_kind:"self_claimed"}]`；cotest run 结果 MUST 经由独立 verifier 写入 `verified_profiles`；dev mode posture 下编译期或运行期 assert `verified_profiles.is_empty()`。
  - 下游：sodmin / yougen / cotest validator MUST 区分 self_claimed 与 cotest_verified；旧 `supported_profiles` 字段保留作向后兼容别名，但不再表达 claim level。

### 新增 `MemberDeliveryBindingCandidate` 规范级对象（2026-05-19）

Handle → `delivery_binding_hint` → member delivery binding → Space-scoped delivery 端到端链路此前在 coauth / soland / teabay 等下游各自拼字符串组装；本轮把 "用 handle 加成员" 链路上需要传递的最小字段集合凝固为一个 schema-defined builder 对象 `MemberDeliveryBindingCandidate`，让 SDK `member_add` builder 只接受 candidate 或已物化 binding，停止跨实现 ad-hoc shape 漂移。

- **变更类型**: add
- **影响 artifact**: `schemas/member-delivery-binding-candidate.schema.json`、`registry/contract-catalog.json`、`registry/schema-registry.json`、`zh/identity/identity-handles.md`、`zh/spec-map.md`、`zh/overview/release-readiness.md`
- **canonical 变更**:
  - 新增 schema id `cx.schema.member_delivery_binding_candidate.v1`，绑定 `schemas/member-delivery-binding-candidate.schema.json`；MUST 字段 `subject_did` / `handle_uri` / `recipient_service_did` / `delivery_binding_hint` / `issuer_service_did` / `audience` / `expires_at` / `source_refs` / `proofs` / `intent`；`additionalProperties: false`；`handle_uri` 复用 handle-claim canonical 形态约束（`contrix://<domain>/users/<localpart>`，lowercase localpart）；`delivery_binding_hint.binding_source` 排除 `did_document_default`。
  - `zh/identity/identity-handles.md` 新增 §3.7 章节，定义字段、来源（Directory `intent="member_add"` / 受信 issuer 直接签发）、validator MUST 规则（schema 合规 / canonical handle_uri / audience match / expiry / proof binding transcript / subject 一致性 / `binding_source` 合法值 / `recipient_service_did` 内外一致），以及 display / mention / member_add 三种 intent 解析返回字段的差异。
  - `spec-map.md` §4.2 在 `identity-handles.md` 条目补注 §3.7 入口。
  - `release-readiness.md` Registry 表 `Schema` 计数 52 → 53。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 已重跑；`python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 53 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`。
- **conformance impact**:
  - 受影响 profile: 无 profile-level 变更；candidate 是 `cx.directory.resolve_handle` 响应与 SDK `member_add` builder 之间的 typed payload。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible — 旧 caller 仍可继续构造拼字符串 payload，但 SDK 已标 deprecation；新 caller MUST 走 candidate 路径。
  - reader / writer 行为要求: Directory MUST 在 `intent ∈ {member_add, invite}` 响应中以 candidate shape 重新打包 §9.0 normative 字段；SDK builder MUST 在落 `cx.member.state{join}.delivery_binding` 前对 candidate 跑 validator；reducer 仍 MUST 按 Join Policy 独立再验证（candidate 不取代 Join Policy 检查）。
- **fixture / vector 变化**: 沿用既有 `handle-claim` fixture；后续可基于 candidate schema 派生 negative payload（subject mismatch / expired / audience mismatch / non-canonical handle_uri）。
- **prose 同步**: `spec/v1/zh/identity/identity-handles.md` §3.7（新增）；`spec/v1/zh/spec-map.md` §4.2；`spec/v1/zh/overview/release-readiness.md` Registry 表。
- **迁移指南**:
  - Directory 实现：把 `cx.directory.resolve_handle(intent="member_add" \| "invite")` 响应聚合为 candidate shape，并附 `source_refs[]` 与 `proofs[]`。
  - SDK / 客户端：把任何 "用 handle 加成员" 入口改成只接 `MemberDeliveryBindingCandidate` 或已物化 `MemberDeliveryBinding`；旧拼字符串 API 打 deprecation，至少保留一个 minor 版本。
  - coauth / soland / teabay 等下游：在 T3.2 / T3.3 / T3.4 任务中迁移到 candidate；本轮 spec + SDK 不直接改这些项目。

### Push gateway profile 拆分 + profile role 注解（2026-05-19）

`cx.profile.push_gateway.v1` 此前把 `blind_wakeup` 列为 optional extension，下游可声明"支持 push gateway 但不支持 blind wakeup"，与 spec 正文要求的"默认互操作安全基线"矛盾。本轮把 push gateway profile 按隐私语义拆分为三个独立 profile，并为所有 profile 增加 `role` 注解，让 SDK / yougen / soland 之类的 client 无法把 gateway profile 误用为本地 client profile。

- **变更类型**: add + modify
- **影响 artifact**: `profiles/conformance-profiles.json`、`zh/discovery/push-notifications.md`、`zh/conformance/conformance-profiles.md`、`zh/overview/release-readiness.md`
- **canonical 变更**:
  - 在 `conformance-profiles.json` 新增三个 profile id：`cx.profile.push_gateway.blind_wakeup.v1`（default，所有 push gateway 实现 MUST 支持）、`cx.profile.push_gateway.visible_notification.v1`（opt-in，Realm policy + device opt-in + UI 明示三重前置）、`cx.profile.push_gateway.matrix_passthrough.v1`（interop only，MUST NOT 与 blind wakeup 在同一 `(recipient_service_did, device)` 上混用）。
  - `cx.profile.push_gateway.v1` 的 `optional_extensions` 移除 `blind_wakeup`；新增 `depends_on` / `required_profiles` 数组引用 `cx.profile.push_gateway.blind_wakeup.v1`，并在 `description` 中明示默认基线身份。
  - 新增 top-level `profile_roles` 表（spec 层 metadata，与 `profile_tiers` 平级），覆盖全部 80 个声明 profile，role 取值限定为 `client` / `server` / `gateway` / `directory` / `admin` / `interop`；附加 `profile_roles_rule` 说明 SDK 与 conformance loader MUST 在声明前查表。
  - `implementation_profiles` 与 `profile_tiers.v1_profile_catalog` 列表均新增三个 push gateway 子 profile。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 已重跑；`python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 52 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`。
- **conformance impact**:
  - 受影响 profile: `cx.profile.push_gateway.v1`（语义收紧：blind wakeup 从 optional 升为 required dependency）、新增三个 push gateway 子 profile、`cx.profile.matrix_compat.v1`（作为 matrix_passthrough profile 的 depends_on 引用方）。
  - profile tier 变化: 三个新 profile 全部进入 `v1_profile_catalog` 与 `implementation_profiles`。
  - wire 兼容性: behavioural-breaking — 已声明 `cx.profile.push_gateway.v1` 但未实现 blind wakeup 的实现 MUST 在该 changelog 生效后补齐 blind wakeup 强制约束，或撤销 profile 声明。
  - reader / writer 行为要求: Push gateway 实现 MUST 拒绝任何携带稳定识别字段（principal/sender DID、Realm/Flow/Message id 等）的 provider payload；client SDK MUST 在声明 push gateway profile 前同步声明 blind_wakeup profile；bridge 实现 MUST 在 (recipient_service_did, device) 粒度上分区 matrix_passthrough 与 blind_wakeup 流量。
- **fixture / vector 变化**: 沿用既有 `privacy-security-fixture.json`；后续 T0.x 任务可基于本轮三个新 profile 派生 negative payload fixture（携带 sender DID / Realm id 的 push payload 应被 reject）。
- **prose 同步**: `spec/v1/zh/discovery/push-notifications.md` §2.2 + §5.1 改述 blind wakeup 为默认基线并指向新拆分的 profile；`spec/v1/zh/conformance/conformance-profiles.md` §11 新增三 profile 描述表（profile id / role / 强制能力 / fixture）；`spec/v1/zh/overview/release-readiness.md` 更新 profile id 计数（77 → 80）与 `profile_requirements` 计数（65 → 68）。
- **迁移指南**:
  - Push gateway 实现：把 blind wakeup 从 optional extension 升级为编译期 / 运行期常态行为，移除任何"关闭 blind wakeup"的 feature flag；如部署确需可见通知，新增 `cx.profile.push_gateway.visible_notification.v1` 声明并实现 Realm policy / device opt-in / UI 明示三重前置。
  - yougen / soland / SDK：在 profile loader / capability manifest 里按 `profile_roles` 表过滤；client 角色 SDK MUST NOT 把 `gateway` / `directory` / `admin` / `interop` 角色 profile 误装为本地客户端 profile。
  - Matrix bridge：把 matrix_passthrough profile 声明从隐式归并到默认 push gateway 声明中拆出来，按 (recipient_service_did, device) 粒度分区流量。

### 新增机器可读 drift detection artifacts（2026-05-19）

下游实现（SDK、yougen、soland、cotest 等）此前只能靠人工阅读 CHANGELOG 来发现协议已移除的概念（branch、Room core model、`cx.flow.track.*`、`cx.field.position.*` 等），cotest scanner 无法自动检测漂移。本轮在 `artifacts/registry/` 下新增六份 canonical drift detection artifacts，并在 `registry-manifest.json` 中注册、在 `spec-map.md §1.2` 中索引。

- **变更类型**: add
- **影响 artifact**: `registry/removed-event-kinds.json`、`registry/removed-operation-ids.json`、`registry/deprecated-profile-ids.json`、`registry/forbidden-wire-fields.json`、`registry/forbidden-model-terms.json`、`registry/renames.json`、`registry/registry-manifest.json`
- **canonical 变更**:
  - 新增 6 份 `artifacts/registry/*.json`，统一 schema：`{$schema, version, kind, source_of_truth, rejection_levels, allowed_context_definitions, entries[]}`；每条 entry 字段 `id` / `since_revision` / `rejection_level` (`hard_reject` | `migration_only` | `compat_only` | `docs_only`) / `replacement` / `allowed_contexts` / `notes`。
  - `registry-manifest.json` 新增六个条目（`removed_event_kinds` / `deprecated_profile_ids` / `removed_operation_ids` / `forbidden_wire_fields` / `forbidden_model_terms` / `renames`），全部标记 `source_role=canonical` / `source_of_truth=true`。
  - 首批 entry：8 条 removed event kinds（`cx.field.position.move`/`reorder`、`cx.flow.track.member`/`history_visibility`/`read_receipt_policy`/`policy_components`、`cx.realm.lifecycle.set`、`cx.realm.policy.set`）；9 条 removed operation ids（与上述 event kind 对齐）；2 条 deprecated profile ids（`chat_only_client`、`kanban_only_client`）；3 条 forbidden wire fields（top-level `branch`、`room_kind`、Flow payload `kind=room`）；5 条 forbidden model terms（`Room`、`Realm(kind=list)`、`flow_branch`、`track members`、`Room visibility`）；6 条 renames。`since_revision` 统一指向 `0a5ab85`。
- **派生 artifact 同步**: 不影响 `event_kind_registry` / `schema_registry` / `id_kind_registry` / `operation_registry` / `capability_action_registry` 生成视图，无需 `python tools/artifact_pipeline.py generate`。`registry-manifest` 是 canonical 索引，已手工同步。
- **conformance impact**:
  - 受影响 profile: 无；这组 artifacts 不参与 wire conformance，而是 drift detection 输入。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible — 仅新增机器可读 metadata 文件。
  - reader / writer 行为要求: cotest scanner MUST 消费这六份 artifacts 来标记下游实现中的旧 id / 旧字段 / 旧术语；新增、移除或重命名标准 cx.* 概念时 MUST 同步更新这组 artifacts。
- **fixture / vector 变化**: 无；后续 T0.x 任务可基于这组 artifacts 生成 negative drift fixture。
- **prose 同步**: `spec/v1/zh/spec-map.md` 新增 §1.2「漂移检测 artifacts」段落，列出六份文件、entry schema 字段与维护约束。
- **迁移指南**:
  - cotest：scanner 增加 drift detection pass，按 `rejection_level=hard_reject` 对下游仓库 grep 旧 id / 字段 / 术语，命中即报错；`allowed_contexts` 用于豁免 changelog / migration / interop 注释。
  - SDK / yougen / soland 等下游：把这组 artifacts 作为单一权威来源对照自身代码，旧 id / 旧字段 / 旧术语清理任务以 entry 粒度跟踪。
  - 后续移除任何标准 cx.* 概念时，必须在同一 PR 中同时新增对应 entry，否则 cotest drift scanner 无法发现漂移。

### Realm-scoped member delivery binding + 统一 Handle 模型（2026-05-19）

Realm membership 显式承载成员的投递服务绑定，DID 是协议主键、签名与审计归因的根；Realm-scoped 投递的唯一权威路由源是该成员 `cx.member.state{join}.delivery_binding` 中固化的 `recipient_service_did`。

Handle 是统一概念：协议层只有一种 handle canonical URI（`contrix://<domain>/users/<localpart>`，lowercase localpart）、一套解析与验证规则。`acct:<localpart>@<domain>` 只能作为 `handle_aliases[]` 互通别名。Holder 自托管个人 handle（自有域名）与组织内部账号地址在结构上是同一类——区别只在 issuer（domain owner 自己 vs Organization / Principal Server / Directory），不在 URI 形态。显示形态 `@<localpart>:<domain>` 或 `<localpart>@<domain>`；其它字面形态在 schema 层被拒绝。

- **新增 Event.kind**：
  - `cx.realm.delivery_binding_policy`（state event；`cell_family=cx.component.realm.delivery_binding_policy.v1`, `cas-register`, `bottom=reject`, `cell_subject=null`）。
  - `cx.device.push_route`（actor-private event；`cell_family=cx.component.device.push_route.v1`, `cas-register`, composite `cell_subject=(recipient_service_did, principal_id, device_id, push_route)`, `bottom=reject`）。
- **Schema**：
  - `event-payload.schema.json#/$defs/member_delivery_binding`：严格 schema。`recipient_service_type=const "principal_server"`、`binding_scope=const "realm"`；`delivery_modes` / `resolved_at` 必填；按 `binding_source` 的 conditional required（`did_document_default` → `did_document_hash`；`explicit` / `invite` / `organization_policy` → `service_acceptance_ref`；`join_policy` / `space_policy` / `organization_policy` → `policy_ref`）。
  - `event-payload.schema.json#/$defs/membership_payload`：`membership=join` 时 `actor_id` / `delivery_status` 必填；`delivery_status=routable` 时 `delivery_binding` 必填。
  - `event-schema.json`：`cx.realm.delivery_binding_policy` 进入 wire-level `kind` enum 与 state_payload 分支。
  - `handle-claim.schema.json`：`handle_uri` 仅允许 `contrix://<host>(:<port>)?/users/<lowercase-localpart>`；`acct:<localpart>@<host>(:<port>)?` 移入 `handle_aliases[]`，不得作为 canonical；裸 `contrix://<host>`、`user:domain`、bare host 一律拒绝。`binding_state=verified` 必填 `handle_uri` / `expires_at`；出现 `recipient_service_did` 或 `delivery_binding_hint` 时必填 `handle_uri` / `audience` / `expires_at`，且 `delivery_binding_hint.binding_source` 不允许 `did_document_default`。
- **Prose normative**：
  - `identity/identity-handles.md`：Handle 单一模型，§3.1 显示形态与 canonical URI、§3.2 解析结果必含字段、§3.3 `delivery_binding_hint` 约束、§3.4 Issuer 类型（holder self-issued / Organization / Principal Server / Directory）与 holder 自托管路径、§3.5 公开 vs 受限、§3.6 与 pairwise DID 正交；§5 解析 issuer 优先级；§6 双向验证按公开 / 受限分流；§6.1.2 撤销路径（TTL + Directory withdrawal + DID Document 变化）；§6.1.3 重分配与历史归因。
  - `governance/join-policy.md` §5.1：接受准则、`binding_source` 与责任方表、`cx.realm.delivery_binding_policy` 字段、路由不可降级、rebind handover via causal frontier、单 binding 约束、unlinkability 边界；§5.1.2.1 Handle 作为 member_add 输入的 6 步构造法（含 `audience` 校验）。
  - `sync/federation.md` §4.1：接收方服务绑定规则切分 member-level vs Realm-level 两条互不重叠路径；fail-closed 解析算法；handover stale 协议；`service_binding_ref.delivery_binding_frontier` 必填；`delivery_binding_diagnostics` 仅作诊断。§6.2 Actor Event Source 发现用途表。
  - `identity/identity-did.md` §3.2：DID Document `ContrixPrincipalServer` service entry 是默认服务发现入口，不作为 Realm-scoped delivery 路径；Handle 属 Handle 层，不属 DID method。
  - `discovery/discovery-directory.md` §9.0：Handle 解析 normative 准则（6 条），含 audience 与 invocation 上下文一致性校验。
  - `sync/client-sync.md` §2.x：Delivery Binding UX 指引（4 条 SHOULD）。
  - `crypto-media/device-lifecycle.md` §5a：`push_target_id` 作用域 `(recipient_service_did, principal, device, push_route)`；`cx.device.push_route` cell_subject 与 binding 一致性。
  - `discovery/push-notifications.md` / `sync/service-http-binding.md`：push registration 作用域绑定当前 Principal Server service DID；`cx.directory.resolve_handle` 增 `intent` / `requester` / `audience`-bearing claim 响应；`cx.directory.search_users` 增 `intent`。
  - `models/flow-and-message.md` §9.4：mention 节点结构（`subject` / `handle_uri` / `display_snapshot` / `resolved_at`）；handle 重分配时 UI 显式标注。
  - `overview/glossary.md`：单一 Handle 术语；`overview/architecture.md`、`overview/matrix-core-differences.md`、`sync/operations-sync.md`、`conformance/encoding.md`：术语与叙述对齐。
- **Conformance vectors**（`conformance/conformance-vectors.md`）：
  - §7：4 个 Member Delivery Binding vector — `explicit` / `did_document_default` / `unroutable` / rebind + revoke。
  - §8：Handle → Join vector（含 negative cases：`verified=false`、`subject != did`、`recipient_service_did` 不在 Realm `allowed_recipient_services`、无 `recipient_service_did`）。
- **路由 normative 硬约束**：
  - sender 在 Realm-scoped 投递时 MUST 解析当前 effective member `delivery_binding.recipient_service_did`；解析失败、过期、撤销时 MUST quarantine + retry，MUST NOT 退回 DID Document。
  - `delivery_binding_frontier` 落后于接收方接受的 handover frontier 时，接收方 MUST 返回 `delivery_binding_stale` + 新目标；sender MUST 重定向，不得退回 DID Document。
  - "actor DID 在某 Principal Server 上有本地账号 / OIDC subject / 员工记录 / 设备 session" 不构成 Realm-scoped 投递授权；授权 MUST 通过 binding 的 `service_acceptance_ref` / `policy_ref` 链建立。
  - Handle 字符串仅是 builder 输入；canonical URI 比对、`alsoKnownAs` 一致性校验、Directory 缓存键一律 MUST 使用 `contrix://` 形态，`acct:` 仅为互通别名。
- **隐私边界**：本机制解决路由 / 设备 / push / 审计边界。跨上下文 unlinkability 通过 pairwise / private DID（`identity-did.md` §3）实现，与本机制正交：同一 DID 在不同 Realm 的 membership 仍可被外部观察者关联。
- **Registry 计数**：active event kind 152，schema 52，typed ID kind 39，operation 84，profile 77。

### Watch / 通知订阅模型作为专用 `cx.flow.watch.set` event + 派生 `watches` Relation（2026-05-18）

Flow 通知订阅长期通过实现私有的 `fields.participants` / `fields.watchers` 数组表达，结构上和 ACL 易混；早期 prose 在 [flow-and-message.md §4.3](spec/v1/zh/models/flow-and-message.md) 提到 "watchers" 但未给出 wire 形态。本轮把 watch 模型正式登记为：
- 专用 durable event `cx.flow.watch.set`（writes cas-register cell `cx.component.flow.watch.v1`）—— 完全机器可发现；
- `watches` Relation（`actor --watches--> flow`）作为该 cell 的**派生投影**，直接 `cx.relation.create` 写入 MUST schema_violation（与派生 `contains` Relation 同模式）；
- 明确"watch 决定通知是否发生，push rule 决定通知如何投递"的两层职责，并把 `muted` 强约束实现自由度（pre-engine short-circuit / 内置 deny rule / 用户显式 rule 三种等价）写清楚。

- **变更类型**: add（standard event_kind + cell family + payload schema + capability actions + push-rule condition）
- **影响 artifact**: `contract-catalog.json`（canonical 源）、`event-kind-registry.json`、`capability-action-registry.json`、`event-schema.json`（新增 `flow_watch_set_payload`）、`relation.md`、`flow-and-message.md`、`push-notifications.md`、`private-objects.md`、`spec-map.md`、`capabilities.md` §5.3/§5.4 capability 列表、`conformance/schema-registry.md` event 表、`sync/operations-sync.md` §7.2 Flow event 分类
- **canonical 变更**:
  - `contract-catalog.json` 新增 event_kind `cx.flow.watch.set`（category=discussion, lattice=cas-register, bottom=reject, cell_family=`cx.component.flow.watch.v1`, cell_subject=tuple(flow_id, actor_did)）。
  - `event-schema.json` 新增 `flow_watch_set_payload` $def（字段：`flow_id`、`actor_did`、`level ∈ {mentions_only, participating, all, muted, null}`（**required**，`null` 表示清空 cell）、`level_public`（conditional：仅在 `level` 非 null 时允许出现）、`expected_value` 用作 cas `head_eq`，**whole-value compare**——形如 `null | {level, level_public?}`，与 cell value 完全同形）并接入 `kind=cx.flow.watch.set` 分支。Schema 用 `allOf` if/then 强制 `level=null ⇒ level_public 省略`，消除 `{level_public: true}` 单独出现的歧义。
  - `contract-catalog.json` capability actions 新增 `cx.flow.watch.set`（discussion, low risk_tier，普通成员默认 bundle）、`cx.flow.watch.manage_others`（discussion, medium risk_tier，target_event_kinds=[cx.flow.watch.set]）、`cx.realm.notification.audit`（governance, high risk_tier，纯 read，target_event_kinds 为空）。
  - `models/flow-and-message.md` 新增 §8（Watch 与通知订阅）9 个子节：概念边界 / 级别枚举 / cell basis + 写入事件 / 写入授权 / 投影脱敏（含 audit 闭环要求 `cx.realm.notification.audit` + `cx.audit.accessed` 双 capability）/ Agent 例外 / 隐含订阅 / push rule 引擎关系 / `discussion_realm_ref` 场景。原 §8（Message）顺移为 §9，原 §9（规范性引用）顺移为 §10。
  - §4.3 / §4.4 中既有 `watchers` 措辞替换为 `watches` 并指向 §8。
  - `models/relation.md` §3.1 标准 kind 列表加入 `watches`；§3.2 cardinality 表新增 `actor (did) -> flow` 行，明确标注**派生投影 / not directly writable**，truth source 是 `cx.flow.watch.set` + cell。
  - `discovery/push-notifications.md §4.3` condition table 新增 `watch_state` kind（server-side, supports glob and multi-value）；§4.3.2 增补"两层职责"叙述、`muted` 强约束三种等价实现路径（pre-engine short-circuit / 内置 deny rule / 用户显式 override rule）。
  - `models/relation.md` 与 `models/private-objects.md` 中既有 `[flow-and-message.md §8.7]` / `§8.6` 引用同步重定向到 `§9.7` / `§9.6`。
  - 人类可读 registry 同步：`authz/capabilities.md` §5.3 / §5.4 把 `cx.flow.watch.set`、`cx.flow.watch.manage_others`、`cx.realm.notification.audit` 加入对应分类列表；`conformance/schema-registry.md` event 表加入 `cx.flow.watch.set`；`sync/operations-sync.md` §7.2 Flow event 分类列表加入 `cx.flow.watch.set` 并补叙述指向 §8 truth source 规则。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 重新生成 `capability-action-registry.json` / `event-kind-registry.json`；`event-schema.json` enum 覆盖完整（事件计数 146 → 147）。`relation.schema.json` 的 `relation_kind` 是开放 string，不需要新增 enum 值。
- **conformance impact**:
  - 受影响 profile: `cx.profile.chat_mvp.v1`、`cx.profile.kanban_mvp.v1`（任何承载 Flow + Message 的实现都可声明该 relation 的支持）。
  - profile tier 变化: 无；watch 模型在 v1 保持 opt-in，不强制为 chat_mvp 必需。
  - wire 兼容性: backward-compatible —— 新增 event kind / capability action 不影响既有 wire；不识别 `cx.flow.watch.set` 的实现按 unknown event 处理。但若声明支持，MUST 遵守投影脱敏、`muted` 短路、audit capability 双持有规则。
  - reader / writer 行为要求:
    - Writer: 通知订阅 MUST 通过 `cx.flow.watch.set` durable event 写入，不得通过 Flow `fields.participants` / `fields.watchers` 双写、也不得通过 `cx.relation.create relation_kind=watches`；后两者 wire 上 MUST 被 reducer 拒绝（与既有 `fields.rank` 与派生 `contains` Relation 同模式）。`level` 取四值枚举之一或 `null`；其它值 MUST schema_violation。
    - Reducer: `payload.actor_did == envelope.actor_id` 默认强制；除非 actor 持有 `cx.flow.watch.manage_others`。`muted` 在 projection / push 派发上 MUST 与"无记录"对外不可区分。审计读取必须同时校验读取方持有 `cx.realm.notification.audit` **与** `cx.audit.accessed`；缺其一时 `failed_precondition`（`reason="audit_capability_incomplete"`）。
    - Sync Service: notification dispatch 顺序 = (1) 解析 receiver effective watch level + 隐含订阅 → (2) 应用 `muted` 短路（pre-engine 或 built-in deny rule 二选一，dispatch 输出等价）→ (3) 评估用户 push rule。
- **fixture / vector 变化**: 暂未生成专用 conformance vector；下一轮 spec round 计划补 `flow-watch-level-projection-fixture.json` 覆盖四象限投影脱敏、muted 短路三种等价路径、audit capability 双持有校验。
- **prose 同步**: 见 "canonical 变更" 段列出的五份 prose 文档。
- **迁移指南**:
  - 客户端实现（如 yougen）需要把"新建 discussion 时添加用户"的 UI 从写 Flow `fields.participants` 改为提交 `cx.flow.watch.set` event；label 从 "Add users" 改为 "Add watchers" 并增加"不影响访问控制"提示。
  - 服务端实现：projection layer 在响应 Flow watcher 列表 / "我的订阅" 查询时 MUST 按 §8.5 表脱敏；`muted` 永远不可见给非自己 / 非 audit 持有方。audit 读取路径 MUST 校验 `cx.realm.notification.audit` + `cx.audit.accessed` 双持有；缺一律 fail-closed 并产生 `cx.audit.accessed` 写入（先写后读模型）。
  - notification dispatcher：实现 §8.7 "隐含订阅 union 显式 watch cell, muted 显式覆盖" 的求值顺序；`muted` 短路具体走 pre-engine 或 built-in deny rule 由实现自行选择，wire 上等价。
  - 外部文档若引用 `flow-and-message.md` §8 / §9：§8 现指向 Watch 章节、原 Message 章节顺移为 §9、原 规范性引用 顺移为 §10。本仓库内的引用（relation.md / private-objects.md）已同步。

### Conformance profile matrix 覆盖 cotest registry/vector gates（2026-05-17）

- **变更类型**: add
- **影响 artifact**: `conformance-profiles.json`、`release-readiness.md`、`conformance-profiles.md`
- **canonical 变更**: `vector_profiles` 新增 `discovery_vectors`、`event_kind_lattice_dispatch_vectors`、`event_kind_payload_coverage_vectors`、`operation_registry_coverage_vectors`、`error_code_registry_coverage_vectors`，并为这些 profile 增加 `profile_requirements` 与 `required_cotest_suites`。
- **派生 artifact 同步**: 无 generated registry 改动；`python tools/artifact_pipeline.py check` 负责验证 profile matrix 引用。
- **conformance impact**:
  - 受影响 profile: vector profile matrix。
  - profile tier 变化: 无；这些 profile 仍属于 vector gate，不是实现 bundle。
  - wire 兼容性: backward-compatible。
  - reader / writer 行为要求: 无 wire 行为变化；实现声明 profile 时必须通过对应 cotest suite。
- **fixture / vector 变化**: 现有 cotest discovery / event-kind lattice / payload / operation / error-code vectors 被纳入机器 profile matrix。
- **prose 同步**: `spec/v1/zh/overview/release-readiness.md` 与 `spec/v1/zh/conformance/conformance-profiles.md` 的 profile 计数同步为 66 profile / 54 requirement blocks / 21 implementation profiles / 16 vector profiles。
- **迁移指南**: conformance runner 必须以 `conformance-profiles.json` 生成 must-test matrix；server describe 声明的 profile 与必需 operation 不一致时 hard fail。

### Lifecycle state machine — 显式补齐 archive / update / tombstone 源状态 MUST（2026-05-15）

把 `common-fields.md §5` 从只规定 `*.restore` 来源升级到完整的 archive / restore / tombstone / update 状态机表。原来只有 restore 一条显式 MUST(spec round 之前补的),archive / tombstone / update 的源状态校验在 prose 里隐含但没有 wire-级 MUST,导致 SDK / 服务端实现各异。本轮把所有 lifecycle transition 的允许源状态 + reason_code 列成统一表,并下推到 Flow / Space / Morph 三套对象 schema 与 prose;新增 3 条 conformance vector 验 wire 行为。

- **变更类型**: add(状态机 MUST + reason_code 注册)
- **影响 artifact**: `common-fields.md`、`flow.schema.json`、`space.schema.json`、`morph.schema.json`、对应 zh prose、`conformance-vectors.md`
- **canonical 变更**:
  - `common-fields.md §5.1` 新增"Canonical state-transition table",列出 `cx.<kind>.archive` / `.restore` / `.tombstone` / `.update` 的允许源、目标、`failed_precondition` reason_code,以及"未知对象容忍 / 终态等价 / 不允许 same-state self-transition / update on non-active MUST fail" 四条附加规则。
  - reason_code 命名:`<kind>_not_active`(archive / update 错源)、`<kind>_not_archived`(restore 错源)、`<kind>_already_terminal`(tombstone / redaction 进入已终态);`<kind>` 取 `flow` / `space` / `morph` / `message`,所有实现 MUST 用相同 reason_code 串。
  - 三套对象 schema(`flow.schema.json` / `space.schema.json` / `morph.schema.json`)的 `state` 字段 description 加 reducer 强制契约,引用 common-fields §5.1。
  - 三套对象 prose(`flow-and-message.md` / `realm-and-space.md §4.4` Archive Space + Tombstone Space / `morph.md`)的 `state` 行 / archive 子节 / tombstone 子节同步补齐 MUST 文字。
- **派生 artifact 同步**: 无 generated artifact 需重新生成(本次只动 normative prose + schema description + 新 fixture)。`registry diff: clean`。
- **schema 变更**:
  - 三套 `state` 字段 description 加详细 transition 规则;`state_changed_at` description 把 `cx.<kind>.restore` 加进"由何 event 写入"列表。
- **conformance impact**:
  - 受影响 profile: `cx.profile.kanban_mvp.v1`、`cx.profile.chat_mvp.v1`(因覆盖 Flow lifecycle)、所有支持 Morph 的 profile。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible —— 新规则只收紧 reject 路径,well-behaved 客户端(emit archive 前确认 state=active 等)不受影响。pre-existing 在错源状态发 lifecycle event 的实现需要修(SDK 已在 round 9 收紧 restore,archive/tombstone 还在 follow-up)。
  - reader / writer 行为要求:
    - Writer: emit lifecycle event 前 MUST 确认 pre-state 满足表;失败时 reducer 会用 `failed_precondition` 拒绝。
    - Reducer: 按 §5.1 表实现源状态校验;未知对象(create 尚未到达)不报错。错源 MUST 用表里 reason_code,不允许自创。
- **fixture / vector 变化**: `conformance-vectors.md §6.5-6.7` 新增三条向量(archive-on-archived rejected / tombstone-on-tombstoned rejected / update-on-archived rejected),都用 Space 举例并明示"Flow / Morph 等价同形"。
- **prose 同步**: `common-fields.md §5` 段加 §5.1 子节、`realm-and-space.md §4.4` Archive Space + Tombstone Space 子节加 MUST 文字、`flow-and-message.md §3` table state 行扩、`morph.md §2.2` table state 行扩。
- **迁移指南**:
  - SDK 实现:需要把 archive / update / tombstone 的源状态校验加上(类似 SDK round 9 给 restore 加 guard 的模式);失败时返 `Error::Protocol("<kind>_not_active" | "<kind>_already_terminal")`。SDK round 10 任务。
  - 服务端实现:envelope 形态不变;若服务端做了 projection state 追踪(soland Space 待做),lifecycle event 提交前可做 state-machine 预校验,直接返 HTTP 412 而不是先存后被 reducer reject。
  - 客户端 UI:archive / restore 按钮做 capability gate 时也应 disable 当前 state 不满足前提的按钮(例如已 archived 的 list 不显示 "Archive" 而显示 "Restore")。

### 新增 `cx.space.restore` 修正 Space 生命周期对称性（2026-05-15）

补齐 Space 的 `archived -> active` 反向转换。此前 Space schema 的 `state` 枚举包含 `archived`（[`common-fields.md` §5](spec/v1/zh/models/common-fields.md) 也明示其为"可撤销"软隐藏），但 event_kind_registry 中只有 `cx.space.archive` 与 `cx.space.tombstone`——既没有 `cx.space.restore`，common-fields §5 又禁止直接 PATCH 顶层 `state`。这把"unarchive 一个看板/列"变成 wire-level 无解的操作：与 Flow / Morph 的 `*.restore` 形成不对称。本变更对齐到 `cx.flow.restore` / `cx.morph.restore` 的现有模式，不改 Space schema 形状。

- **变更类型**: add
- **影响 artifact**: `event_kind_registry`、`capability_action_registry`、`event-schema.json`、`space.schema.json`
- **canonical 变更**（`contract-catalog.json`）:
  - `event_kind_registry.event_kinds[]` 新增 `cx.space.restore`（`wire_scope=durable_event`、`reducer_input=true`、`category=space`、payload 与 `cx.space.archive` 同属 generic_standard_payload 组）。
  - `capability_action_registry.actions[]` 新增 `cx.space.restore`（category=`flow`、`risk_tier=medium`、`required_constraints=[]`、`target_event_kinds=["cx.space.restore"]`），与 `cx.space.archive` 对称。
  - 现有 bundle action `cx.object.restore` 的 `target_event_kinds` 追加 `cx.space.restore`（此前只覆盖 `cx.flow.restore` 与 `cx.morph.restore`）；持有该 bundle 的 admin grant 自动覆盖 Space restore，无需重新签发。
- **派生 artifact 同步**: 已通过 `python tools/artifact_pipeline.py generate` 重新生成 `event-kind-registry.json` 与 `capability-action-registry.json`；diff 干净。
- **schema 变更**:
  - `event-schema.json` 在 Space generic_standard_payload 分支的 `if.enum` 中加入 `cx.space.restore`，与现有 `cx.space.archive` / `cx.space.tombstone` 共享同一 payload 校验。
  - `space.schema.json#/properties/state` description 补充：`archived` 由 `cx.space.restore` 还原到 `active`，仅当当前 `state == "archived"` 时合法；`tombstoned` MUST NOT 被 restore。
- **conformance impact**:
  - 受影响 profile: `cx.profile.kanban_mvp.v1`（Space lifecycle 是 kanban_mvp 已覆盖的能力路径）；`minimal_client` / `full_client` 等通过 kanban_mvp 间接受影响。`chat_mvp` 不涉及 Space。
  - profile tier 变化: 无。
  - wire 兼容性: **backward-compatible**。新增 event kind 与 capability action，旧 writer 不发送即可；旧 reader 收到未知 kind 时按既有未知-kind 处理规则（reject 或 ignore by profile 声明）即可，没有现有 wire 被收紧。
  - reader / writer 行为要求:
    - Writer：从 `archived` 还原 Space MUST 发送 `cx.space.restore`；MUST NOT 通过 `cx.space.update` PATCH 顶层 `state`。
    - Reducer：MUST 校验当前 `state == "archived"`；其他状态 MUST `failed_precondition`（`reason="space_not_archived"`）。Tombstoned Space MUST NOT 被 restore。校验通过后 set `state="active"` 并写入 `state_changed_at`。
    - Restore **不**级联：archive 时同时隐藏的 child Space / 内部 Flow 仍处于自身 `archived` 状态时，restore parent 不会改变 children；UI 需独立 restore（与 archive 不级联对称）。
- **fixture / vector 变化**: `spec/v1/zh/conformance/conformance-vectors.md` 新增 §6 "Space Lifecycle Vectors"，覆盖三条向量：§6.2 archive→restore happy path（验证 `state` 与 `state_changed_at` 转换、默认 projection 隐藏 / 还原、不级联到 children）、§6.3 在 `state == active` 时 restore 被拒（`failed_precondition` / `space_not_archived`）、§6.4 在 `state == tombstoned` 时 restore 被拒（同 reason；明确 tombstoned 不可复活，正确路径是新建 Space）。
- **prose 同步**: `spec/v1/zh/models/realm-and-space.md`（§4.2 state 行、§4.3 授权列表、§4.4 新增 "Restore Space" 子节）、`spec/v1/zh/models/common-fields.md`（§5 约定第一条加入 `*.restore` 命名）、`spec/v1/zh/conformance/schema-registry.md`（§4.1 新增 Space 行块，同时补齐此前缺失的 `cx.space.create/update/parent/archive/tombstone` 行——pre-existing 文档视图 gap）、`spec/v1/zh/sync/operations-sync.md`（§7 新增 7.3 Space 段，其后段落自然顺延为 7.4/7.5/7.6/7.7）、`spec/v1/zh/authz/capabilities.md`（§5.2 加入 `cx.space.restore`）、`spec/v1/zh/conformance/conformance-vectors.md`（新增 §6）。
- **迁移指南**:
  1. 客户端 unarchive Space 的代码若此前通过 `cx.space.update` 设 `state="active"` 绕开 archive/restore 对称缺口，应迁移到 `cx.space.restore`；reducer 收紧后该绕路 PATCH 已不合法。
  2. Reducer 实现新增 `cx.space.restore` 入口；状态机分支沿用 archive 的 capability 校验路径，只是写入 `state="active"` 而非 `"archived"`。
  3. Capability 评估器对 `cx.object.restore` bundle 的 `target_event_kinds` 重新加载即可——bundle 已在 source-of-truth 中追加 `cx.space.restore`。
  4. 不需要 fixture 迁移；既有 archive-then-tombstone 路径不变。

### Flow `tracks` 由数组改为 map（2026-05-09）

把 Flow `tracks` 从 `array<{ name, ... }>` 改为 `map<TrackName, FlowTrackConfig>`，key 即 track 稳定名。动机：track 名是封闭词汇表（`synthesis` / `discussion` 及 profile 声明的扩展名），不是用户自由 ID；map 形态把"同一 Flow 内 name 唯一"从一条显式约束变成结构本身保证，并且去掉 `name` 字段冗余、消除 patch path stable-key selector 段（`tracks[name=discussion].profile` → `tracks.discussion.profile`）。`is_primary=true` 仍然在每个 track entry 上；"至多一个" 由 reducer 校验，schema 不再单独表达此约束（map 形态下需逐 key 检查）。

- **变更类型**: modify（schema 形状变化 — wire breaking）
- **影响 artifact**: `flow.schema.json`、`event-payload.schema.json`（patch_path 描述）、`conformance-vectors`
- **canonical 变更**:
  - `flow.schema.json#/properties/tracks`：`type=array, items=$ref flow_track, minItems=1, contains/maxContains=1, uniqueItems=true` → `type=object, minProperties=1, propertyNames=$ref track_name, additionalProperties=$ref flow_track`。
  - `flow.schema.json#/$defs/flow_track`：移除 `required: ["name"]` 与 `properties.name`；其余字段（`is_primary` / `profile` / `template` / `fields`）不变。
  - `event-payload.schema.json#/$defs/patch_path`：regex 不变，描述更新——v1 标准 schema 不再使用 stable-key selector 段，`tracks` 走普通对象段。Profile / 扩展若引入具名集合数组仍可用 selector 段。
- **派生 artifact 同步**: 无 generated artifact 改动；`conformance-vectors.md` 中 Flow create 例子已改为 map 形态。
- **conformance impact**:
  - 受影响 profile: 任何接受/产生 Flow object 的实现（即所有 `core_event_store` / `chat_mvp` 及以上 profile）。
  - profile tier 变化: 无。
  - wire 兼容性: **breaking**。旧 array 形态 MUST 被 reducer 拒绝（schema validation 即触发）。
  - reader / writer 行为要求: writer MUST emit map；reader MUST reject array 形态为 `schema_violation`。`cx.flow.track.enable` / `disable` / `set_primary` 三个 event payload 不变（它们一直按 track name 字符串寻址）。
- **fixture / vector 变化**: `conformance-vectors.md` Flow create 向量已更新；其他 fixture 不含 Flow tracks 例子。
- **prose 同步**: `spec/v1/zh/models/object-model-core.md`（§6 / §7）、`object-model-standard.md`（§2.1 / §2.4 / §5.1）、`data-structures.md`（§6.1 / §19 patch path 说明）、`overview/current-model.md`（§2 / §3）、`models/views.md`（§6.1 概念映射）、`sync/operations-sync.md`（§7.2 / §8 patch path）、`conformance/encoding.md`（§9.5.2）、`authz/capabilities.md`（§7）、`authz/constraint-schema.md`（§6.1）。
- **迁移指南**:
  1. Writer：把 `tracks: [{ name: "synthesis", is_primary: true }, { name: "discussion" }]` 重写为 `tracks: { synthesis: { is_primary: true }, discussion: {} }`；从 entry 中删除 `name` 字段。
  2. Reducer：把 `tracks[].name` 唯一性从显式校验改为依赖 map 结构；保留"至多一个 `is_primary=true`"的 reducer-level 校验。
  3. Patch path：把 `tracks[name=<x>].<field>` 改写为 `tracks.<x>.<field>`。
  4. SDK / projection：所有按 `tracks.find(t => t.name === ...)` 的查找改为 `tracks[name]` 直接索引；按 `Object.entries(tracks)` 迭代时记得 entry 已不含 `name`。

### Operation registry tier 分类与 surface 错位整理（2026-05-08）

把 `operation_registry.capability_tiers` 从三档（core / extension / deployment_local）扩到四档,新增 `interop_bridge` tier 用来标记"对外部协议（MIMI、Applet 等）的 adapter surface",并修复几处 surface 错位分组。动机:此前 `mimi_interop`、`applet` 与 `directory_discovery`、`blob_media` 等同被打上 `extension`,把"协议内可选 surface"与"对外部协议的桥接"压成同一类,导致 30% 操作看着像 extension —— 实际上前者属于 Contrix 规范本体的可选项,后者是独立外部规范的 adapter,生命周期/治理/profile 语义都不一样。本次只动 metadata,无 wire 变化、无 op 增删。

- **变更类型**: modify(metadata-only:tier rename + surface split + 新字段 `bridges_to`)
- **影响 artifact**: `contract_catalog`(operation_registry 段)、`operation_registry`(generated view)
- **canonical 变更**(`contract-catalog.json#operation_registry`):
  - **新增 tier** `interop_bridge`,定义为"对外部协议的 adapter surface,advertise 仅当桥接的外部协议被支持;不属于任何 core 或 extension profile;通常通过 `bridges_to` 镜像一个本规范内的 op"。
  - **retier**:`applet`、`mimi_interop` 两个 surface 从 `extension` 改为 `interop_bridge`。
  - **surface 拆分**:
    - 旧 `blob_media`(blob.upload/head/get + media.ice_config)→ 拆为 `blob_storage`(三个 blob op,`extension`)+ `realtime_media`(`cx.media.ice_config`,`extension`)。ICE config 是 WebRTC 控制面,与 blob 存储正交,不应同 surface。
    - 旧 `admin_operator` 中混入的 `cx.moderation.report`(用户面 abuse 上报)拆出为 `moderation_reports`(`extension`),`admin_operator` 只保留运营/管理操作并维持 `deployment_local`。
  - **operations[] 新增字段** `bridges_to`(可选,字符串,引用本仓库一个 operation_id):
    - `cx.mimi.report_abuse` → `cx.moderation.report`
    - `cx.mimi.proxy_download` → `cx.blob.get`
  - **registry_rules 简化**:删掉枚举式句子("Account, admin, applet, MIMI, media, moderation, directory, push, and key-management surfaces are optional..."),改为引用 `capability_tiers` 语义。
- **派生 artifact 同步**:`operation-registry.json`(generated view)已镜像同样的 tier、surface、bridges_to 字段;`registry-manifest.json` 版本号 bump 至 `2026-05-08`;`contract-catalog.json` 与 `operation-registry.json` 版本号同步 bump。lint(`tools/lint_artifacts.py`)对未知 tier 已自动校验,无 hardcode 列表需要更新。
- **conformance impact**:
  - 受影响 profile: 无。`conformance-profiles.json` 中 `profile_tiers` 与本次 surface 的 `capability_tiers` 是两个独立维度;profile 矩阵不引用 surface tier 字符串。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible(operation_id、HTTP 路径、gRPC、mq 名都未变)。
  - reader / writer 行为要求: 无新行为要求。Discovery 实现 SHOULD 在按 tier 过滤时把 `interop_bridge` 当作"非默认 advertise"来处理(此前归在 `extension`,语义上 advertise 默认即可,这次起需要外部协议显式支持才 advertise)。
- **fixture / vector 变化**: 无。
- **prose 同步**: 本次未改 zh 文档(本仓库 zh 文档不硬编码 surface tier 字符串)。后续若新增 tier 介绍段落可在 `spec/v1/zh/sync/service-api-schema.mdx` 与 `spec/v1/zh/conformance/conformance-profiles.md` 增补。
- **迁移指南**:
  - SDK / discovery 实现:消费 `operation-registry.json#surface_groups[].tier` 的代码,如果用枚举/switch 处理 tier,需要新增 `interop_bridge` 分支(否则该 tier 的 surface 会落入 default 分支)。
  - 消费 surface 名称(`blob_media` / `admin_operator` 包含 `cx.moderation.report`)的代码:`blob_media` 已拆为 `blob_storage` + `realtime_media`;`cx.moderation.report` 已迁出 `admin_operator`。这是 surface 字符串变化,不是 op 变化,但下游若按 surface 过滤需要更新。

### Sync / Events 读取 surface 重构（2026-05-08）

把按 selector / cursor 取事件序列的三个旧 operation 收敛为按 delivery 形态拆分的两个新 operation，并把 client_sync 改名为 account 同步以澄清它"账号视角聚合"的真实定位。重构思路：selector（actor / realm）、range（forward / backward / window）和 delivery（unary / stream）三个维度被旧 surface 切错了——`cx.events.list`（actor or realm, 单向, unary）、`cx.sync.backfill`（realm, 双向, unary）、`cx.sync.subscribe`（realm, 实时, stream）的差别本质是 selector 和 cursor 方向，不是不同操作；只有 streaming 与 unary 才是真正的 delivery 差别。

- **变更类型**: modify（重命名 + 合并 — wire breaking）
- **影响 artifact**: `operation_registry`、`capability_action_registry`、
  `contrix-service-api.openapi.yaml`、`non-http-bindings.yaml`、
  `conformance-profiles.json`
- **canonical 变更**（`contract-catalog.json`）:
  - **新增** `cx.events.query`（HTTP `GET /events`、gRPC `Events/Query`、mq
    `events.query`）。selector 是 `realms[]` ∪ `actors[]` ∩ 组合；range 是
    `from?` + `until?` + `direction: forward|backward`；返回 `events[]` +
    `next_cursor?` + `prev_cursor?`。合并旧 `cx.events.list` 与
    `cx.sync.backfill` 的双向语义。
  - **新增** `cx.events.subscribe`（HTTP `GET /events/subscribe`、gRPC
    `Events/Subscribe`、mq `events.subscribe`）。多 realm / actor 一次订阅；
    `include_history: bool=true` 时先吐历史再以 `catchup_complete` 帧切到实时。
    新增 `dropped` / `epoch_rotation` / `unauthorized` / `resync_required` /
    `frontier` / `heartbeat` / `catchup_complete` 帧类型。
  - **新增** `cx.sync.account`（HTTP `POST /sync`、gRPC `Sync/Account`、mq
    `sync.account`）。语义不变，是旧 `cx.sync.client_sync` 的改名——这个 op
    的真实定位是 to_device / account_data / device_lists / presence / 跨
    Realm delta 的 **账号视角聚合**，不是裸事件读。
  - **移除** `cx.events.list`、`cx.sync.backfill`、`cx.sync.subscribe`、
    `cx.sync.client_sync`。
  - capability_action_registry 同步：移除三条旧 sync 服务动作，新增
    `cx.events.query` / `cx.events.subscribe` / `cx.sync.account`，三者均
    `service` 类别、`low` risk_tier。
- **派生 artifact 同步**: 已直接同步 `operation-registry.json`、
  `capability-action-registry.json`；OpenAPI、non-http binding、conformance
  profile 都已手工对齐。如运行 `python tools/artifact_pipeline.py generate`
  应得到等价结果。
- **conformance impact**:
  - 受影响 profile: `core_event_store`, `chat_mvp`, `kanban_mvp`,
    `minimal_client`, `full_client`, `principal_server_events_api`,
    `principal_server`, `agent_runtime`, `franking`, `personal_node`,
    `small_team`, `mls_governance_binding.full`, `attested_audit.e2ee`,
    `disclosed_audit.e2ee`, `reaction_vectors`, `redaction_vectors`,
    `sync_vectors`, `matrix_compat`
  - profile tier 变化: 无（profile 仍在原 tier，只是 required_endpoints
    重命名）
  - wire 兼容性: **breaking**（HTTP 路径与 operation_id 同步变更）
  - reader / writer 行为要求:
    - 客户端 MUST 把双向历史读切到 `GET /events?direction=...`，不再用
      `/sync/backfill`
    - 客户端 MUST 把 Realm 流订阅切到 `GET /events/subscribe`，不再用
      `/sync/subscribe`；并按 `catchup_complete` / `dropped` /
      `resync_required` 帧调整恢复逻辑
    - 客户端 MUST 把 account 同步的 operation_id 改为 `cx.sync.account`；
      路径 `POST /sync` 不变
    - 服务实现 MUST 在 `events.query` 上对每个 selector 元素逐项做
      visibility 判定（actor scope 用 actor history visibility；realm
      scope 用 membership frontier + history visibility + E2EE epoch
      policy）
- **fixture / vector 变化**: `sync-fixture.json` 现在覆盖
  `cx.events.query` / `cx.events.subscribe` / `cx.sync.account`；旧名称
  应被替换。
- **prose 同步**: `service-http-binding.md` §2.1/§2.3/§2.4/§3.3/§3.4/§5、
  `service-api-schema.mdx`、`transport-bindings.md` §4、`client-sync.md`
  §1/§2、`federation.md` §7、`authz/capabilities.md` §5.5、
  `identity/key-management.md` §device.authorized.content.scopes。
- **迁移指南**:
  - rename `operation_id` 引用：`cx.events.list` → `cx.events.query`；
    `cx.sync.backfill` → `cx.events.query`（带 `direction=backward`）；
    `cx.sync.subscribe` → `cx.events.subscribe`；
    `cx.sync.client_sync` → `cx.sync.account`
  - rename HTTP 路径：`GET /sync/subscribe` → `GET /events/subscribe`；
    `GET /sync/backfill` → `GET /events?direction=backward`；
    `POST /sync` 路径不变但 operation_id 改名
  - query 参数：`actor_id` / `realm_id` 改成 `actors[]` / `realms[]`；
    `cursor` 改成 `from`（再叠 `until?` + `direction`）
  - `events.subscribe` 帧 schema 改名：`type` → `kind`，新增多种
    `kind` 值；客户端 MUST 处理新帧类型而不是把未知 kind 当 `event`

### `branches[]` → `tracks[]`（2026-05-08，Flow 能力面命名重构）

把 Flow 的能力面字段从 `branch` 改名为 `track`。原命名暗含 git 风格的"版本派生"心智模型，与 Contrix
中 Flow 多面共同推进的语义不符；`track`（多轨录音 / PM workstream tracks）更准确地表达"同一议题
沿多条并行轨道演进"的设计意图。Synthesis 与 discussion 仍是 v1 标准 track name，profile 仍可声明
更多 track name；只是承载它们的字段、event kind、schema $defs、constraint key 全部统一改名。

- **变更类型**: modify（重命名 — wire breaking）
- **影响 artifact**: `event_kind_registry`、`capability_action_registry`、`schema_registry`、
  `error_code_registry`、`flow.schema.json`、`message.schema.json`、`event-schema.json`、
  `event-payload.schema.json`、`grant-constraint.schema.json`、`notification.schema.json`、
  `read-receipt.schema.json`、`read-marker.schema.json`、`contrix-service-api.openapi.yaml`、
  `conformance-profiles.json`、`capability-fixture.json`
- **canonical 变更**:
  - 字段重命名：`branches` → `tracks`、`branch` → `track`（在 Flow / Message / ReadReceipt /
    ReadMarker / Notification / event payload 中各自对应字段）。
  - Event kind 重命名：`cx.flow.branch.{enable,disable,update,set_primary,read,admin,member,
    history_visibility,policy_components}` → `cx.flow.track.*`。
  - Cell family 重命名：`cx.component.flow.branch.{member,history_visibility,policy_components}.v1`
    → `cx.component.flow.track.*`。
  - Constraint key 重命名：`allowed_branches` / `denied_branches` → `allowed_tracks` /
    `denied_tracks`。
  - Schema `$defs` 重命名：`branch_name` → `track_name`、`flow_branch` → `flow_track`、
    `flow_branch_{enable,disable,set_primary}_payload` → `flow_track_*_payload`、event-payload
    `$defs/branch` → `$defs/track`。
  - Error code 重命名：`discussion_branch_disabled` → `discussion_track_disabled`、
    `no_flow_branch_message_grant` → `no_flow_track_message_grant`。
  - Conformance optional extension 重命名：`discussion_branch` → `discussion_track`。
  - Patch path stable-key 选择段重命名：`branches[name=...]` → `tracks[name=...]`。
  - Legacy hybrid 名重命名：`branch_scoped` → `track_scoped`（仅出现在 schema description /
    historical note，已在 v1 之前移除）。
- **派生 artifact 同步**: 已通过 `python tools/artifact_pipeline.py generate` 重生成派生 registry 视图；
  `python tools/artifact_pipeline.py check` 全绿（132 event kinds、38 schemas、36 typed ID kinds、
  78 operations、59 profiles）。
- **conformance impact**:
  - 受影响 profile: `cx.profile.core_event_store.v1`、`cx.profile.chat_mvp.v1`、
    `cx.profile.kanban_mvp.v1`、`cx.profile.full_client.v1`、`cx.profile.e2ee_client.v1`、
    `cx.profile.mimi_interop.v1`、`cx.profile.principal_server.v1`。所有承载 Flow 能力面 / message
    track / track-scoped capability constraint 的 profile 都受影响。
  - profile tier 变化: 无；profile 集合不变，只更换内部引用的字段 / event kind 名。
  - wire 兼容性: **breaking**。所有 Flow / Message / event payload / capability constraint /
    notification / read-receipt / read-marker 上原本写 `branch` / `branches` / `cx.flow.branch.*`
    的 wire 数据需要换成新名。
  - reader / writer 行为要求: 升级后的实现 MUST emit 新名；MUST 拒绝（schema validation 阶段）
    带旧字段名的 wire 数据，不得执行同义解释。同时维护两套命名的实现 MAY 在迁移窗口期内 tolerate
    旧名，但 SHOULD 同时写出新名并在描述里标记 deprecation。
- **fixture / vector 变化**: `capability-fixture.json` 中 `no_flow_branch_message_grant` 已改名；
  `event-envelope-negative-fixture` / `crypto-signature-fixture` / `move-anchor-lattice-fixture` 不
  涉及 branch 字段，无需重新签名。`conformance-vectors.md` §5.5 / §5.5.1 / §5.6 已同步使用 track 字段。
- **prose 同步**: 已更新 33 个 `spec/v1/zh/**/*.md` 文件，包括 overview / models / sync / authz /
  conformance / discovery / crypto-media / extensions / identity 全部 plane。中文 prose 中"分支"
  在 Flow 能力面语境一律改为"轨道"；保留场景：Merkle 分支、sibling fork 历史分支、JSON Schema
  if/then 分支、状态机 quarantine/rate_limited 分支、policy 决策分支、"容器形态"变体义。
- **迁移指南**:
  1. 所有发出 `cx.flow.branch.*` event 的客户端 / 服务端 MUST 改用 `cx.flow.track.*`，并把 payload
     字段 `branch` 改为 `track`。
  2. Capability grant 中 `allowed_branches` / `denied_branches` MUST 改为 `allowed_tracks` /
     `denied_tracks`。
  3. Read receipt / read marker / notification 写入 MUST 把 `branch` 字段改为 `track`。
  4. 所有 wire-emitting code path 跑一遍重新签名（detached JWS over canonical bytes）；payload 字段
     改名属于 canonical bytes 变更，原签名失效。
  5. 错误码消费者把 `discussion_branch_disabled` / `no_flow_branch_message_grant` 替换为
     `_track_` 形式。
  6. SDK / 服务实现可在 transition 期内 tolerate 旧名 wire（推荐 reject 但允许警告），同时
     `server/describe.profiles_supported` 中只声明新 profile id；不得为旧名重新登记 event kind。

## [1.0.0] — 2026-05-05

### 协议评审驱动的简化（2026-05-05：constraint 14→8 collapse + encoding 合并 + federation dedup）

#### Constraint 类型 14 → 8 family + subtype discriminator

- `grant-constraint.schema.json` `constraint_type` enum 从 15 收敛为 8（`temporal`, `field_access`,
  `type_restriction`, `scope_limitation`, `delegation_control`, `quota`, `claim_based`,
  `confidentiality`），新增 `subtype` 字段保留原 14 类型的子语义。
- 新增 `applies_to_actions[]` 让 `temporal` 吸收 v0 的 `edit_window` / `redact_window`。
- `constraint-schema.md` §2.2 表从 14 行 + 2 例外行重构为 8 family + subtype 表；§2.3 evaluation_class
  表从 19 行简化为 17 行（按 `(family, subtype)` 索引）；新增 v0→v1 family 命名映射 table 用于翻译既有
  grant；§6.3、§8、§9、§10、§11、§12、§13、§14 章节标题更新以反映 family/subtype 归属。
- 16 处 JSON 示例迁移到新形态：`approval_workflow` → `claim_based{subtype=approval}`；
  `accountability` → `claim_based{subtype=accountability}`；`encryption_requirement` →
  `confidentiality{subtype=encryption}`；`visibility_control` → `confidentiality{subtype=visibility}`；
  `container_move` → `scope_limitation`；`rate_limiting` → `quota{subtype=rate}`；`resource_limit` →
  `quota{subtype=resource}`；`edit_window` → `temporal{subtype=edit_window}`。
- conformance-profiles.json 增加 `cx.profile.constraint.device_session.v1`。

#### Encoding 文档收敛

- 删除 `zh/conformance/hlc-specification.md`：操作伪代码（send / receive / compare）与验证规则
  并入 `encoding.md` §7.1-§7.3。
- 删除 `zh/conformance/cursor-encoding.md`：客户端契约 / canonical 内部结构 / 验证规则 /
  cursor 可迁移性 (服务器之间 reparse) / 一致性要求 并入 `encoding.md` §8.1-§8.6。
- `encoding.md` §2.1 新增 "备用 canonical encoding (profile-gated)"：注册 `cx.profile.encoding.cbor.v1`
  作为未来 CBOR (RFC 8949) deterministic encoding 的扩展点；引入 `encoding_extension_profiles`
  顶级字段到 conformance-profiles.json。
- conformance/README.md 更新文件清单。

#### federation.md ⇌ federation-wire.md 去重

- 删除 `zh/sync/federation-wire.md`（原 170 行）。federation.md §3.2 删除自指 `federation-wire.md §2`
  的注释，新增 §4.5 Fork Detection / Frontier Exchange（来自原 federation-wire.md §6 的 frontier
  exchange shape `{realm_id, heads[], max_hlc, witness_receipts[]}` 与 duplicate_conflict 处理规则）。
- 4 处跨文件引用 (`security/server-threat-model`, `spec-map`, `service-http-binding`, `federation`
  本身) 重定向到 federation.md。spec-map 中重复行去重。

### 协议评审驱动的简化（2026-05-05：真删 + Event Envelope requirements 合并 + plane 重组 + conformance-vectors 合一）

#### 真删之前仅标 deprecated 的字段 / 注册表项

- `space_version`：从 `event-schema.json` / `realm.schema.json` 完全删除（不仅是 required 列表）；
  `crypto-signature-fixture` 重新生成 canonical bytes / payload_hash / binding_hash / signed JWS（用
  test private key 重新签名并验证通过）；`event-envelope-negative-fixture` 11 个 event 全部清理；
  `encoding-conformance-vectors` 中的 canonical bytes vector + digest 重算。规范文本中的版本演进
  提法统一改写为 Event `requirements` 与 profile id / `cx.realm.upgrade` 语义。
- `cx.flow.convert`：从 `contract-catalog.json` event_kind_registry 删除（删除后 110 → 109 active
  kinds，之后 actor_profile 评审新增 `cx.profile.create` 把总数加回 110，参见下方 "actor_profile +
  gatekeeper 收尾" 一节）；`event-schema.json` 移除对应 if/then 分支与 `flow_convert_payload` $def；
  prose 全部改为 `cx.flow.track.set_primary` + `cx.flow.track.enable` 组合。
- `cx:operation:` typed-id：从 `id_kind_registry` 删除（37 → 36）；`cx.schema.operation.v1` 从 schema_registry
  删除（35 → 34）；`operation.schema.json` 与 zh 镜像完全删除；data-structures.md §18（Canonical
  Operation Object）删除，§19 Field Patch 重新编号为 §18。
- `constraint.priority`：从 `grant-constraint.schema.json` properties 删除；§2.1 base schema 不再列
  priority；§15 求值伪代码不再使用 priority；§6.3 container_move 示例移除 priority。

#### Event Envelope 4 个 profile/feature 字段 → 单一 requirements{} 对象

- `schema_profile_refs[]` / `reducer_profile_ref` / `required_features[]` / `critical_extensions[]`
  四个顶级字段从 wire schema 移除，合并为单一 `requirements: {schema[], reducer, features[],
  critical_extensions[]}`。
- `crypto-signature-fixture` 重新生成（canonical bytes、digest、签名全部更新；用 test private key
  重新签名并 Ed25519 公钥验证通过）。`event-envelope-negative-fixture` 11 个 event 收敛。所有 prose
  reference 更新（data-structures, operations-sync, api-conventions, service-http-binding,
  schema-registry, conformance-profiles, conformance-suite, event-auth-state-resolution,
  contract-catalog 描述文本）。

#### Read Marker / Relation.state / Notification

- Read Marker：删除 `timeline_order_key`（"may speed up comparison" — 不是 wire 必要，比较顺序
  应由客户端按 HLC 实现）。schema + prose 同步。
- `Relation.state` enum：`active|deleted|redacted` → `active|tombstone`；删除/撤回原因仅记录在
  `cx.relation.delete` / `cx.redaction` 事件上。
- `object-model-core.md` 核心对象列表：`notification` / `read_marker` 从 canonical 列表降级为
  "派生对象（不是 canonical truth，由 client / SDK 从 Event 集合本地计算）"。

#### plane 重组

- 新 `zh/governance/` 目录，`authz/moderation.md` → `governance/content-moderation.md`。
- `authz/account-lifecycle.md` → `identity/account-lifecycle.md`（账号生命周期是 identity 概念，不是
  capability authorization）。
- 合并 `crypto-media/devices-and-auth.md` + `device-crypto-verification.md` → 单一 `device-lifecycle.md`
  （13 + 26 KB → 26 KB merged，重复内容被消除；§1-§3 来自 devices-and-auth 的 login/auth boundaries +
  pairing + SSO，§4-§15 来自 device-crypto-verification 的 device identity / signing / list sync /
  to-device / OTKs / KeyPackage claim / verification / secret storage / key backup / cross-signing /
  applet device delegation）。
- 全部跨文件引用更新。spec-map 中两条 device-lifecycle.md 重复条目去重；过期描述（identity-did
  默认值、event-auth-state-resolution scope）刷新。

#### Audited E2EE 相关改动已在更早条目完成，此处不重复登记

#### R1.8 conformance-vectors 合并

- 5 个 `*-conformance-vectors.md`（encoding / state-resolution / redaction / capability / sync）合并为
  单一 `conformance-vectors.md`，按 §1-§5 分组。约 1,300 行整合。
- 所有跨文件引用全部更新（11 处 .md / .json）。
- 删除原 5 个文件。

#### actor_profile + gatekeeper 收尾（2026-05-06，v1.0.0 release 锁定前）

- **actor_profile object & `cx.profile.create`**：新增 `cx:actor_profile:` typed-id 和 `cx.profile.create`
  / `cx.profile.update` / `cx.profile.space_override` 三个 event kind；event_kind_registry 由 109 回到
  110 active kinds（id_kind_registry 仍保持 36，因为这次未删除其他 typed id，而 actor_profile 以独立
  kind 进入）。create payload 不再共享 `object_create_payload`：`cx.realm.create` / `cx.flow.create`
  / `cx.morph.create` 各自指向完整对象 schema，wire 校验直接走对象 schema。
- **state_key 形态**：`cx.realm.policy.set` 的 `state_key=inheritance` 由常量改为
  `inheritance:cx:realm:<ulid>` 模式（每个父 realm 一条），并把 `plaintext_visible_services` 显式纳入
  state_payload enum 以保留 schema 强校验。
- **encrypted_payload mutual exclusion**：message / flow / morph schemas 增加 `encrypted_payload` 字段，
  与 `content` / `body` 互斥；`message_create_payload` / `message_redact_payload` 由 anyOf 收紧到
  oneOf+not。
- **18 BLOCKER 修复（"Final gatekeeper review"）**：encrypted-envelope schema (`ratchet_tree` →
  `group_state_ref`、强制 `version` + `aad_digest`、`key_ref` 锁 `additionalProperties:false`)；
  read-receipt (`reader` → `actor_id`，新增 `flow_id`、`track`、`hlc`、`schema`)；read-marker
  (`scope` 改为 `{kind, ref, track?}`，新增 `device_id` 与 `position{event_id, hlc}` 满足多设备汇聚)；
  notification (新增 `source_ref` / `flow_id` / `track`)；resource-selector (移除 `board_id` /
  `list_id`)；capability-grant (`actions[]` pattern 强制 `cx.<segment>...` canonical 词表)；event-payload
  (`message_create` 必须带 `track`，新增共享 `$defs/track`)；以及对应的 `cx.capability.{grant,revoke,
  derived}` state_key 推导规则、derive/revoke supersede 语义、push privacy `push_target_id` 推导
  (`device-lifecycle.md` §5a) 与跨文件引用修复。

#### v1.0.0 发布边界

本发布包不依赖仓库外待办文档作为 normative 输入。constraint collapse、encoding/HLC 合并、profile
登记和 federation wire 去重均已纳入当前 v1.0.0 文本、schema、registry、fixture 或 profile catalog；
后续工作必须以新的 changelog 条目和 profile/registry 变更单独登记。

### 协议评审驱动的简化（2026-05-05：Audited E2EE hardening profile + 已废弃条目收尾）

#### Audited E2EE 拆出独立 hardening profile

- 新建 [`spec/v1/zh/crypto-media/audited-e2ee.md`](./spec/v1/zh/crypto-media/audited-e2ee.md)：承载
  `cx.profile.attested_audit.e2ee.v1` 与 `cx.profile.disclosed_audit.e2ee.v1` 两类
  audited E2EE profile 的完整 normative：audit policy declaration、join warning canonical
  文案、audit agent entry、强制留痕 (`cx.audit.accessed`)、RYW receipt schema、transparency
  surface、forbidden marketing terms。
- `zh/crypto-media/encryption-and-audit.md` §3 缩为概览 stub 指向 audited-e2ee.md；文件从
  708 行 → 538 行（−24%）。Core E2EE / MLS 内容（§2 / §4-§7）完全保留，与 audit profile
  正交。
- `zh/spec-map.md` 增加 audited-e2ee.md 入口。

#### 已废弃条目的 deprecation-only 过渡说明

- `cx.flow.convert`、`cx.schema.operation.v1` / `cx:operation:`、`constraint.priority` 最初以
  deprecation-only 方式标记；后续条目已经完成 wire contract 真删。
- 正式 v1.0.0 以当前 `artifacts/registry/contract-catalog.json`、schema 与对应中文规范为准，不再把
  这些字段或注册表项声明为 active 兼容项。

### 协议评审驱动的简化（2026-05-05）

基于全仓评审，此条目收敛掉与 Matrix room state 风格继承相关的复杂性预算，以及对仍在演进外部
标准的 normative 绑定；已完成事项以本文和机器工件为准。

#### 文件级合并（删除冗余文件）

- 删除 `zh/conformance/cursor-test-vectors.md`，向量入口并入 `cursor-encoding.md` §3.2。
- 删除 `zh/conformance/hlc-test-vectors.md`，向量入口并入 `hlc-specification.md` §3.4。
- 删除 `zh/discovery/read-notification-schema.md`，schema 与 query 形状并入 `read-receipts.md` §6。
- 删除 `zh/authz/grant-constraint-schema.md`，grant context 示例并入 `constraint-schema.md` §20.3。
- 删除 `zh/identity/progressive-disclosure.md`，渐进披露语义并入 `identity-handles.md` §16。
- 删除 `zh/models/conversation-model.md`，chat 模式示例与冲突规则并入 `object-model-standard.md` §5.1-§5.3。
- 删除 `zh/crypto-media/encrypted-envelope-schema.md`，envelope wire 形态、AAD 序列化、
  payload_digest 计算与解密错误码并入 `encryption-and-audit.md` §2.3.1-§2.3.4；schema 仍由
  `artifacts/schemas/encrypted-envelope.schema.json` 承载。

#### 状态解析与 Matrix 包袱去除（核心语义变更）

- **重写 `zh/authz/event-auth-state-resolution.md`**（882 行 → 685 行，约 −22%）：
  - **Lattice authority 替换为 quarantine-on-fork**：去除 §9.3.2 的 `governance_layer × authority_kind`
    二维 lattice 与派生 `auth_weight` 表。并发 fork 同 `(kind, state_key)` 由 reducer
    quarantine 全部非 winner 候选并要求 admin 显式介入，winner 不再由权重表自动选边。
  - **`space_version` 标记为 deprecated wire 字段**：版本演进通过 `reducer_profile_ref` /
    `schema_profile_refs` / `cx.realm.upgrade` 表达。读取方 MUST 容忍兼容字段；新写入方
    SHOULD 省略。
  - 简化 §4.1 partial_auth_state：v1 默认 `max_offline_backlog_ms = 30 天`；离线超过窗口
    后必须重新拉 frontier 才能写入，去除 `soft_failed` / `partial_auth_state` 长期复活
    路径作为 normative 要求。
  - 简化 §6 history_sharing / policy_components / plaintext_visible_services：保留 auth state
    边界条款，完整 schema 与撤销语义指向 `crypto-media/encryption-and-audit.md` 与
    `sync/service-surface.md`。
  - 简化 §6.6 Organization Ownership：保留 6 步验证清单，详细 schema 指向 `identity/identity-did.md`。
- 同步更新 `artifacts/schemas/event-schema.json` 与 `realm.schema.json`：把 `space_version` 从
  `required` 数组移除，字段 description 改为 deprecated 说明。
- 同步更新 `zh/models/data-structures.md`：Realm §4 与 Event Envelope §9 的 `space_version`
  改为 `no (deprecated)` 必填性。

#### 外部互操作下沉为 interop extension profile

- `zh/extensions/mimi-interop.md` 顶部增加 extension profile banner：MIMI 仍是 IETF
  Internet-Draft；v1 core 不要求实现 MIMI provider facade。
- `zh/extensions/agent-protocol-interop.md` banner：A2A / ACP / MCP bridge 都未标准化（IBM
  Research 已宣布 ACP 并入 A2A）；v1 core 不要求实现 agent-protocol upgrade。
- `zh/extensions/applet-integration.md` banner：Applet registry 与审核 SLA 仍在演进；v1
  core 不要求实现。
- `zh/sync/service-surface.md` §9 (MIMI Provider Facade) 缩为单段指针，详细路径下沉到 extension。
- `artifacts/profiles/conformance-profiles.json` 增加 `profile_tiers` 顶级字段：
  - `v1_profile_catalog` 列出 v1 stable catalog 中可独立声明的 implementation profile。
  - `v1_minimal_interop_floor` 列出声称 v1 Event Store interop 的最小 profile。
  - `extension_profile_implementation` 列出 `applet_service` / `agent_runtime` / `mimi_interop`
    三个 extension profile。
  - `tier_rules` 解释 profile catalog、最小互操作地板与 extension 的 conformance 边界。

#### DID method 默认值收敛

- v1 core 默认 principal DID method 从 `did:webvh` 改为 **`did:web`**。理由：`did:web`
  生态成熟、HTTPS + 域名部署门槛低；`did:webvh` 仍在 W3C CCG 演进中。需要可审计身份历史的部署
  SHOULD 升级为 `did:webvh`（high-trust profile）。
- `did:plc`（AT Protocol interop）、`did:pkh`（钱包绑定）、KERI 系列、TSP transport 全部下沉为
  **interop extension profile**；v1 core 实现不要求支持。
- 同步更新：`zh/identity/identity-did.md` §3-§3.4、`zh/identity/tsp-integration.md` 顶部 banner、
  `zh/README.md`、`zh/overview/architecture.md` §2.8、`zh/overview/matrix-core-differences.md`。

#### Transport 路径锁定

- v1 core 互操作 transport **锁定为 HTTP/JSON**。`zh/sync/transport-bindings.md` 顶部声明
  HTTP/JSON 是 normative，gRPC / WebSocket / SSE / message queue / libp2p binding 全部
  下沉为 binding extension profile。
- `artifacts/bindings/non-http-bindings.yaml` 顶部增加 binding extension profile 状态注释；
  文件保留作为 extension binding 设计参考。

#### 仓库结构变更

- 删除文件：8 个（cursor-test-vectors / hlc-test-vectors / read-notification-schema /
  grant-constraint-schema / progressive-disclosure / conversation-model /
  encrypted-envelope-schema；以及一批 zh/spec-map.md 入口）。
- normative `zh/` 文本累计减少约 2,500 行（含 event-auth-state-resolution.md 的 197 行）。
- 机器约束（`artifacts/registry/`、`artifacts/schemas/`、`artifacts/profiles/`）保持向前
  兼容：v1 readers 必须容忍 deprecated 字段；既有 fixture 不要求重写。

### 发布状态

- 仓库当前发布状态为 `v1.0.0` 规范稳定基线。详见
  [`spec/v1/zh/overview/release-readiness.md`](./spec/v1/zh/overview/release-readiness.md).
- 实现若要宣称 `v1-conformance-certified`，仍必须通过 reference validator /
  reference reducer / reference authz evaluator / conformance runner 及对应核心 vectors；
  未认证实现只能声明自己支持的具体 profile。

### 当前基线内容

- 中文规范与机器可读 artifacts 同时锁定；中文文本是人类可读 normative
  来源，artifacts 是机器可验证 wire 真相源。
- Event Envelope、reducer、frontier、snapshot、sync、federation 的 wire fact
  以 `event_id` / actor frontier 为语义单位。
- `core_event_store` / `chat_mvp` / `kanban_mvp` 三个最小实现闭环。
- MLS RFC 9420 群组 E2EE、device verification、authenticated media、
  federation、sovereign deployment、Applet、Agent、MIMI interop、Directory、
  Moderation、Push 等扩展 profile。
- Audited E2EE 双 profile：`cx.profile.attested_audit.e2ee.v1`（硬件 attestation
  强制）与 `cx.profile.disclosed_audit.e2ee.v1`（流程性披露，无密码学强制）。
  Realm policy 通过 `audit_disclosure` 对象 + `audit_assurance` enum 声明；UI
  join warning 与对外材料按 `encryption-and-audit.md` §3.1.1 / §3.5 normative
  分类与禁用措辞执行。
- Capability + constraint 求值规则：`deny` / `quarantine` / `require_review`
  一律"任一命中即生效"；`priority` 仅对 `effect=allow` 有诊断意义；每个
  constraint type 在 `constraint-schema.md` §2.3 有 canonical
  `evaluation_class`，授权评估器据此分 fast / slow path。
- `artifacts/registry/` 下的 contract catalog、event-kind / schema /
  id-kind / operation registry、error code registry、mirror manifest、
  conformance profile registry。
- `tools/artifact_pipeline.py` 流水线作为 registry / mirror 的唯一权威入口。

[1.0.0]: ./
