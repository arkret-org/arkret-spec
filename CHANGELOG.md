# Changelog

本文件记录 Cokret 协议规范在主要发布之间的变化。

格式参考 [Keep a Changelog](https://keepachangelog.com/) 与
[Semantic Versioning](https://semver.org/)。

本仓库当前维护单一 `v1.0.0` 规范线；下方条目描述的是 v1 相对内部草案的收敛内容，
而不是相对任何先前公开稳定版本的差异。任何更新都落在 `spec/v1/` 与对应的唯一 public v1 catalog snapshot 上。

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

### 拆分 webrtc-signaling.md 为三文件(STR-001,2026-06-04)

把承载过多协议面的 `crypto-media/webrtc-signaling.md` 物理拆分为三个单一职责文件,消除 schema / profile / vector / anchor 漂移的结构性根因。详见 `_delay_todos.md`。

- **变更类型**: modify(纯结构/文档重组,无 wire / 语义变更)
- **影响 artifact**: prose(新增 `crypto-media/call-state.md`、`crypto-media/media-service-binding.md`;trim 并重编号 `webrtc-signaling.md`)/ registry 描述(error-code / operation / vector source_refs / conformance-profiles / exporter-label / operations-error-mapping 中的章节引用)/ schema 描述(event-payload / ice-config-response / ephemeral-envelope)/ openapi 描述。
- **canonical 变更**:
  - `call-state.md` = durable `ck.call.state` payload、状态机、录制 / 转写生命周期(原 §3/§4/§11/§11.1/§13)。
  - `media-service-binding.md` = `ck.realm.media_service` foci、token / participant binding、focus 选举、SFU 权限、媒体 E2EE 帧密钥注入与治理绑定(原 §6.1/§6.2/§10.x)。
  - `webrtc-signaling.md` = 仅保留 ephemeral 信令 + ICE/TURN + WebRTC binding,重编号为 §1–§12。
  - 所有入站章节引用按内容主题重定向到新文件;`vector-registry.json` 的 media_binding 向量 `source_refs` 改指 `media-service-binding.md`。
- **派生 artifact 同步**: `contract-catalog.json` 中 token-exchange notes 章节引用更新,已 `python tools/artifact_pipeline.py generate` 重生成 operation-registry 与 public catalog snapshot;`release_gate.py` 5/5 全绿。
- **conformance impact**:
  - 受影响 profile: `ck.profile.media_service_binding.v1`(及 livekit / cokret-native sub-profile)、`ck.profile.webrtc_media.v1` —— 仅文档定位变化,要求不变。
  - wire 兼容性: backward-compatible(无 token / schema / vector id 变化)。
  - reader / writer 行为要求: 无新增 MUST;仅规范文档位置变更。下游 soland / yougen / cokret-rust-sdk / cotest 的 spec 锚点注释已同步。

### 品牌命名空间 cx→ck 与 API 信任同心圆改名(2026-06-03)

把半迁移的 `contrix`→`cokret` 品牌收尾，并把 HTTP API 命名空间从扁平功能模块改为去版本的"信任同心圆"。详见 `_rename.md`。

- **变更类型**: modify
- **影响 artifact**: registry（contract-catalog / 全部派生视图 / operations-error-mapping / error-code / renames / forbidden-model-terms）/ schema / fixture / openapi / non-http binding / prose / site metadata / tooling
- **canonical 变更**:
  - 全部 wire token 前缀 `cx.`→`ck.`、typed-id 前缀 `ck:`→`ck:`、品牌串 `contrix`/`Contrix`→`cokret`/`Cokret`（含实体文件 `cokret-service-api.openapi.yaml`、`cokret-native.md`）。
  - 每个 operation 的 `http` binding 重写为 `/_cokret/<信任段>/...`（段：`self`/`gate`/`root`/`find`/`peer`/`open`/`edge`/`local`），顶层 `ck.server.describe` 落根 meta 位 `GET /_cokret/describe`。
  - **去 path 版本**：删除所有 `/v1/`、`/api/v1`、`/cokret/v1` 片段；`servers` 仅 `https://{host}`；版本改由 `*.describe` / `supported_operations` 协商（可选 `Cokret-Protocol-Version` header）。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 重生成全部派生 registry 视图与 public catalog snapshot；OpenAPI path、`operations-error-mapping.http_alias`、prose 路径表已同步；fixture 内嵌 digest 经 `tools/fix_crypto_signature_fixture.py` 与 digest 重算更新，`tools/check_fixture_digests.py --write-reference` 刷新引用。
- **conformance impact**:
  - 受影响 profile: 全部（operation id 与 wire token 全变）。
  - wire 兼容性: **breaking**（协议尚未公开发布，单一 v1 线，允许 pre-release breaking）。
  - reader / writer 行为要求: 旧 `cx.*` / `contrix` token 与旧扁平 / 版本化 path MUST 被拒绝；登记于 `renames.json` 迁移组 `brand_namespace_cx_to_ck`（hard_reject）与 `forbidden-model-terms.json`。
- **fixture / vector 变化**: 全部 fixture 的 token 与内嵌 digest 已重算；`reports/fixture-digests.json` 引用已刷新。
- **prose 同步**: `sync/service-http-binding.md`(§2.1 信任段图例)、`sync/api-conventions.md`(§11 path 无版本 + 版本协商)、`sync/service-surface.md`、`sync/service-api-schema.mdx` 及全部引用 HTTP path 的 zh 文档。
- **迁移指南**: 下游实现把所有 `cx.`→`ck.`、`ck:`→`ck:`、`contrix`→`cokret`；调用 path 从扁平 `/events` 等改为 `/_cokret/<段>/...`，去掉 `/api/v1`、`/cokret/v1` 前缀；用 `*.describe` 协商版本，不要在 path 写版本。

### MLS effective scope and public catalog gate(2026-05-31)

收紧 MLS Realm/Circle key scope 的机器契约，并把当前候选站点元数据与 public catalog 快照对齐。

- **变更类型**: modify
- **影响 artifact**: event payload schema / prose / site metadata / artifact pipeline
- **canonical 变更**: `realm_key_scope` 与 `mls_genesis_payload` 改用 tagged `effective_scope`；`mls_governance_binding` 封闭字段集并显式绑定 `effective_scope`、`realm_id` 与可选 `circle_id`；旧草案 `flow_id` / `track` 不再是 MLS key scope 形状。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 会刷新当前唯一 `site/public/v1/contract-catalog-1.0.0.json`；`check` 比较 public snapshot 与 canonical catalog 的 hash/bytes/counts/Circle presence。
- **conformance impact**:
  - 受影响 profile: `cx.profile.mls_governance_binding.full.v1`、E2EE client、Circle MLS。
  - profile tier 变化: 无。
  - wire 兼容性: breaking；实现必须写 `effective_scope`，不得继续把 Flow `track` 或 `flow_id` 当 key scope。
  - reader / writer 行为要求: Commit / Welcome / Genesis 的 governance binding scope mismatch MUST fail closed。
- **fixture / vector 变化**: 无新增 fixture；现有 Circle effective-scope vectors 继续覆盖 accepted-event / anchor binding，不再允许 MLS scope 使用旧字段。
- **prose 同步**: `crypto-media/encryption-and-audit.md`、`models/circle.md`、`overview/release-readiness.md`。
- **迁移指南**: 迁移写入端先由 `scope_circle_id` 派生 reducer-stamped `effective_scope`，再把同一 tagged value 放入 MLS genesis/governance binding；历史 key share 使用 `key_scope.effective_scope`。

### Grant constraint identifier suffix cleanup(2026-05-31)

把 grant constraint 中单一 kind 的 identifier 字段统一从 `_refs` 改为 `_ids`，关闭 schema 与命名规范之间的漂移。

- **变更类型**: modify
- **影响 artifact**: grant constraint schema / capability registry / forbidden wire field registry / rename registry / prose
- **canonical 变更**: `allowed_view_refs`、`allowed_flow_refs`、`allowed_circle_refs`、`denied_flow_refs`、`allowed_space_refs`、`denied_space_refs`、`realm_refs`、`approval_actor_refs` 改名为对应 `_ids`；`allowed_from_container_refs` / `allowed_to_container_refs` 保持 `_refs`，因为它们是 Space/Flow/Morph polymorphic container reference。
- **派生 artifact 同步**: `contract-catalog.json#capability_action_registry` 及 generated capability action registry 通过 pipeline 刷新；旧名进入 `forbidden-wire-fields.json` 与 `renames.json`。
- **conformance impact**:
  - 受影响 profile: capability / policy / agent auth / Circle management。
  - profile tier 变化: 无。
  - wire 兼容性: breaking；current parser MUST hard reject 旧 `_refs` 字段。
  - reader / writer 行为要求: Writer MUST emit `_ids`；reader MUST NOT treat old names as aliases on live wire。
- **fixture / vector 变化**: 无新增；drift lint 会拒绝旧字段在当前 schema/prose 示例中重新出现。
- **prose 同步**: `authz/capabilities.md`、`authz/constraint-schema.md`、`authz/resource-selector-grammar.md`、`models/circle.md`、`identity/key-management.md`。
- **迁移指南**: 离线迁移工具可机械替换旧字段名；实时 sync/federation/reducer parser 不得内联 rewrite。

### Media participant typed ID prefix cleanup(2026-05-31)

将 WebRTC/SFU participant handle 的 typed ID 前缀从缩写 `ck:rtcpart:` 收敛为 `ck:rtc_participant:`。

- **变更类型**: modify
- **影响 artifact**: id kind registry / OpenAPI / forbidden wire field registry / rename registry / prose
- **canonical 变更**: `contract-catalog.json#id_kind_registry` 中 `kind=rtcpart` 改为 `kind=rtc_participant`，wire form 改为 `ck:rtc_participant:<uuid>`。
- **派生 artifact 同步**: `id-kind-registry.json` 与 public catalog 由 pipeline 刷新。
- **conformance impact**:
  - 受影响 profile: realtime media / WebRTC signaling。
  - profile tier 变化: 无。
  - wire 兼容性: breaking；current parser MUST hard reject `ck:rtcpart:<uuid>`。
  - reader / writer 行为要求: Writer MUST emit `ck:rtc_participant:<uuid>` in `participant_identity` and participant binding surfaces。
- **fixture / vector 变化**: WebRTC conformance vector prose updated; no signed fixture digest changed.
- **prose 同步**: `crypto-media/webrtc-signaling.md`、`crypto-media/bindings/cokret-native.md`、`conformance/conformance-vectors.md`。
- **迁移指南**: 离线迁移工具可机械替换 prefix；实时 media token / signaling validator 不得接受旧缩写。

### Directory anti-enumeration vector closure(2026-05-31)

把 Directory / PSI 的反枚举要求纳入 machine-readable conformance vector 闭包。

- **变更类型**: add
- **影响 artifact**: vector registry / privacy-security fixture / prose
- **canonical 变更**: `vector-registry.json` 新增 `cx.vector.directory.*` 与 `cx.vector.psi.*` cluster，覆盖 public/listed/restricted/unlisted 查询、resolve blinding、ingest 双向 opt-in、withdraw/takedown、PSI OPRF 两轮、padding/cardinality 和 quota blinded denial。
- **派生 artifact 同步**: 无派生 registry；`python tools/artifact_pipeline.py check` 校验 vector id source_refs 闭包。
- **conformance impact**:
  - 受影响 profile: directory discovery、private contact discovery、privacy hardening。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible；测试闭包增强。
  - reader / writer 行为要求: Directory-capable implementations MUST run these vectors before claiming profile support。
- **fixture / vector 变化**: `privacy-security-fixture.json` 增加 vector cluster 与 closure case。
- **prose 同步**: `discovery/discovery-directory.md` §12。
- **迁移指南**: 无 wire migration；实现应把未授权/不存在/策略拒绝路径统一到 blinded response class。

### Relation tombstoned state spelling(2026-05-31)

将 Relation 物化对象的终态拼写从 `tombstone` 收敛为 `tombstoned`，与 Realm / Space / Circle 等对象 state 命名一致。

- **变更类型**: modify
- **影响 artifact**: relation schema / prose
- **canonical 变更**: `relation.schema.json#/properties/state` enum 改为 `active | tombstoned`；`cx.relation.tombstone` event kind 不改名。
- **派生 artifact 同步**: 无派生 registry。
- **conformance impact**:
  - 受影响 profile: core object model / relation projection。
  - profile tier 变化: 无。
  - wire 兼容性: breaking；materialized Relation state MUST NOT emit `tombstone`。
  - reader / writer 行为要求: Reducer stamps `tombstoned`; readers reject old materialized state in current v1 snapshots。
- **fixture / vector 变化**: 无新增。
- **prose 同步**: `models/relation.md`、`models/common-fields.md`。
- **迁移指南**: 离线 snapshot/materialized-state migration 可机械替换 state value；event kind 与 audit reason 保持原样。

### Release candidate closure hardening(2026-05-31)

关闭 v1 候选复审中仍带 TBD 或命名歧义的安全 surface。

- **变更类型**: modify + add
- **影响 artifact**: key backup schema / vector registry / conformance profiles / forbidden wire field registry / rename registry / prose
- **canonical 变更**: `key_backup.encryption.kdf.params.hash` 改为 `digest_algorithm`；LiveKit recording key 固定 MLS exporter label `"cx-rtc-recording-key/v1"` 与 recording transcript Context；新增 `cx.vector.identity.did_proof_replay_window.v1`、`cx.vector.media_binding.recording_exporter_label.v1`；新增 `cx.profile.circle_anchor_cadence.fixed_5m.v1`。
- **派生 artifact 同步**: public contract catalog 由 `python tools/artifact_pipeline.py generate` 刷新；`check` 校验 schema/vector/profile reference closure。
- **conformance impact**:
  - 受影响 profile: key backup memory-hard、media service binding、LiveKit binding、auth server / identity proof、Circle conformance。
  - profile tier 变化: 新增 hardening profile `cx.profile.circle_anchor_cadence.fixed_5m.v1`。
  - wire 兼容性: breaking for key-backup PBKDF2 params；current parser MUST reject old `params.hash`。
  - reader / writer 行为要求: Recording exporter label/context mismatch、DID proof replay/freshness violation、event-count Circle anchor cadence all MUST fail closed or omit the profile claim。
- **fixture / vector 变化**: 更新 `key-backup-fixture.json`；新增 DID proof replay 与 recording exporter label vectors。
- **prose 同步**: `identity/key-management.md`、`identity/identity-did.md`、`crypto-media/webrtc-signaling.md`、`crypto-media/bindings/livekit.md`、`models/circle.md`、`proposals/0007-circle-primitive.md`、`proposals/0010-media-service-binding-framework.md`。
- **迁移指南**: 离线迁移工具可把 key-backup PBKDF2 `params.hash` 改为 `params.digest_algorithm`；实时 key-backup validator、media adapter、Auth Server 与 Circle anchor scheduler 不得接受旧形态或活动触发 cadence。

### History visibility / preview policy hardening(2026-05-30)

补齐 Realm 历史可见性、加入前 preview / peek、public plaintext Realm 与 E2EE history key share 的规范边界，并把关键 policy surface 机器化。

- **变更类型**: add + modify
- **影响 artifact**: event registry / capability registry / event payload schema / event envelope schema / realm schema / error-code registry / vector registry / conformance profiles / prose
- **canonical 变更**:
  - `contract-catalog.json#event_kind_registry`: 新增 active reducer-input event kind `cx.realm.preview_policy`，cell family 为 `cx.component.realm.preview_policy.v1`。
  - `contract-catalog.json#capability_action_registry`: 新增 high-risk action `cx.realm.preview_policy`，并把 `cx.realm.preview_policy` 纳入 policy management surface。
  - `event-payload.schema.json`: 新增 `history_visibility_payload`、`history_sharing_policy_payload`、`preview_policy_payload`、`history_visibility_value` 与 `history_sharing_restricted_rule`；`realm_key_scope.history_visibility` 改为封闭枚举；`plaintext_data_class` 增加 `history_preview` / `public_history_export`。
  - `event-envelope.schema.json`: 为 `cx.realm.preview_policy`、`cx.realm.history_visibility`、`cx.realm.history_sharing_policy` 增加具体 payload dispatch。
  - `realm.schema.json`: 增加 materialized `preview_policy_id` 指针。
  - `error-code-registry.json`: 新增 `history_sharing_policy_missing`、`history_not_visible`、`preview_policy_denied`。
  - `vector-registry.json`: 新增 `cx.vector.history_visibility.joined_prejoin_denied.v1`、`cx.vector.preview.token_scoped_stripped_state.v1`、`cx.vector.history_sharing.e2ee_prejoin_key_share_policy.v1`。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`；`event-kind-registry.json` / `capability-action-registry.json` 等派生视图同步；`python tools/artifact_pipeline.py check` 通过，registry diff clean。
- **conformance impact**:
  - 受影响 profile: Directory / resolve_target preview、E2EE client history key share、core event payload validation、privacy hardening。
  - profile tier 变化: 无；`privacy_hardening` 列表增加 `preview_policy`。
  - wire 兼容性: backward-compatible for readers that already fail closed on unsupported event kinds；writers that emit `history_visibility=restricted` MUST also provide effective `cx.realm.history_sharing_policy`。
  - reader / writer 行为要求: `history_visibility` MUST use T0 semantics；`preview` token MUST bind target descriptor + link type + preview policy digest；E2EE old epoch key share MUST require both history visibility and history sharing policy.
- **fixture / vector 变化**: `conformance-vectors.md` 增加三条 history / preview / history sharing 向量，并注册到 `vector-registry.json`。
- **prose 同步**: 新增 `zh/governance/history-visibility.md`；同步 `discovery-directory.md`、`object-addressing.md`、`realm-and-space.md`、`circle.md`、`encryption-and-audit.md`、`device-lifecycle.md`、`service-surface.md`、`capabilities.md`、`spec-map.md`、`release-readiness.md`、`schema-registry.md`、`operations-sync.md`、`architecture.md`。
- **迁移指南**: 实现不得再把 `history_visibility` enum 当作粗略 UI hint；必须按 T0 + current safety policy + key-share policy 评估。支持加入前 preview 的实现必须写 `cx.realm.preview_policy`，旧的裸 `lt=preview` 或未绑定 token 一律按 `reference` / `not_found` fail closed。

### Subscribe stream reconnect backoff(2026-05-30)

为 `cx.events.subscribe` / `cx.account.subscribe` 的 200 NDJSON control frame 增加 `reconnect_after_ms`，用于服务端在 `dropped` / `resync_required` 后显式约束下一次订阅重连时间，避免故障或负载压力下的重连放大。

- **变更类型**: add
- **影响 artifact**: schema / openapi / registry notes / fixtures / prose
- **canonical 变更**:
  - `schemas/account-subscribe-frame.schema.json`: `dropped` / `resync_required` frame 可携带 `reconnect_after_ms`；其它 account subscribe frame kind 不得携带该字段。
  - `contract-catalog.json#operation_registry`: `cx.events.subscribe` / `cx.account.subscribe` notes 记录 server-directed reconnect holdoff 语义。
  - `openapi/cokret-service-api.openapi.yaml`: `EventsSubscribeFrame` 增加 `reconnect_after_ms`，并限制为 `dropped` / `resync_required` 使用；account subscribe 通过 schema `$ref` 同步。
- **派生 artifact 同步**: `operation-registry.json` 由 `contract-catalog.json` 重新生成；`python tools/artifact_pipeline.py check` 验证。
- **conformance impact**:
  - 受影响 profile: `principal_server.v1` / `core_event_store.v1` / full client 与 E2EE client 的 subscribe 恢复行为。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible；reader MUST tolerate absent `reconnect_after_ms`，收到时 MUST 延迟同 scope 重连；server 发送后 MUST 对过早重连返回 `429 rate_limited` + `Retry-After`。
  - reader / writer 行为要求: `reconnect_after_ms` 只约束同一 subscribe operation + principal/device/filter 或 caller/selector scope 的重连，不约束无关 API；不得推进 cursor、ack 或 dropped recovery state。
- **fixture / vector 变化**: `schema-validation-fixture.json` 新增 account subscribe control frame 正例。
- **prose 同步**: `zh/sync/client-sync.md`、`zh/sync/service-http-binding.md`、`zh/sync/api-conventions.md`、`zh/sync/service-api-schema.mdx`。
- **迁移指南**: 服务端在过载、buffer pressure 或无法立即恢复时优先在 stream control frame 下发 `reconnect_after_ms`；客户端把该字段作为订阅重连前的最小等待时间，并在等待窗口内避免重复建立同 scope stream。

### Event envelope schema filename normalization(2026-05-30)

统一 Event Envelope schema 文件命名，移除 pre-release 草案中的 `event-schema.json` / `event-envelope.schema.json` 双名状态。

- **变更类型**: modify
- **影响 artifact**: schema / registry / prose / tooling / fixtures
- **canonical 变更**:
  - `contract-catalog.json#schema_registry`: `cx.schema.event.v1` 的 canonical file 从 `schemas/event-schema.json` 改为 `schemas/event-envelope.schema.json`。
  - `event-envelope.schema.json` 变为完整 schema body；删除旧 `event-schema.json` 文件与 `$ref` alias 形态。
  - 全部 sibling `$ref`、Markdown schema fence、fixture schema ref 与 lint 工具硬编码路径同步到 `event-envelope.schema.json`。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`；`schema-registry.json` 同步新路径；`python tools/artifact_pipeline.py check` 验证 registry diff clean。
- **conformance impact**:
  - 受影响 profile: 使用 `cx.schema.event.v1` 的全部 Event writer / reader；无新 profile。
  - profile tier 变化: 无。
  - wire 兼容性: pre-release cleanup；schema id 与 wire object shape 不变，仅 canonical artifact 文件名变化。
  - reader / writer 行为要求: schema consumers MUST 继续通过 `schema-registry.json` 查 `{schema_id,file}`，不得机械推导文件名。
- **fixture / vector 变化**: schema-validation fixture 的 Event schema ref 同步改名；无新增 vector。
- **prose 同步**: `zh/conformance/schema-registry.md`、`zh/overview/release-readiness.md`、`zh/sync/operations-sync.md`、`zh/models/event-and-patch.md` 等文档链接同步。
- **迁移指南**: pre-release consumers 删除本地 `event-schema.json` 路径假设，改读 `cx.schema.event.v1 -> schemas/event-envelope.schema.json`。

### Realm join candidate routing(2026-05-30)

为跨 Principal Server 加入 Realm 增加结构化 candidate ingress service 列表，避免 join / invite-accept / knock 隐式绑定到邀请者 Principal Server 或任何 URL 路由 hint。

- **变更类型**: add
- **影响 artifact**: schema / registry / prose
- **canonical 变更**:
  - `contract-catalog.json#schema_registry`: 注册新 schema `cx.schema.realm_join_candidate.v1`，文件为 `schemas/realm-join-candidate.schema.json`。
  - 新增 `realm-join-candidate.schema.json`，定义 `realm_id`、`service_did`、`service_type`、`role`、`operations`、`join_methods`、`source`、`as_of`、`expires_at` 等字段；candidate 是 time-bounded routing hint，不是授权 grant，也不是 `member_delivery_binding`。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`；`schema-registry.json` 已同步新增 schema；`python tools/artifact_pipeline.py check` 通过，registry diff clean。
- **conformance impact**:
  - 受影响 profile: directory discovery / federation join 行为；无新 profile。
  - profile tier 变化: 无。
  - wire 兼容性: pre-release cleanup；协议尚未发布，不保留 `via_services` 兼容字段，Realm join routing 只使用 `join_candidates[]`。
  - reader / writer 行为要求: `resolve_realm` / realm-target `resolve_target` 在调用方有权取得 join 路由时 MUST 返回 `join_candidates[]`；客户端 MAY 通过任一未过期 candidate 提交 join-side material，但最终授权仍由 Realm policy / invite / review / reducer 校验决定。
- **fixture / vector 变化**: 无新增 fixture；本次仅新增 schema 与 prose contract。
- **prose 同步**:
  - `zh/discovery/discovery-directory.md` §7 / §9.1 / §9.1.1：定义 `join_candidates[]`、candidate 选择和 retry 规则。
  - `zh/sync/federation.md` §5：跨域 invite / knock / restricted join 流程改为通过 candidate ingress service。
  - `zh/sync/service-http-binding.md`、`zh/discovery/object-addressing.md`：同步 directory response 字段。
  - `zh/governance/join-policy.md`：明确 join candidate 与 member delivery binding 不得互相推导。
- **迁移指南**: Directory / Principal Server 在 `resolve_realm` 输出 `join_candidates[]`；客户端在提交 join material 前必须先取得未过期 candidate，不从 URL、邀请者服务 DID 或成员投递绑定推导 ingress。

### Shareable object addressing & `resolve_target`(CXP-0011)(2026-05-28)

引入客户端无关的可分享对象地址(Flow / Message / Realm 深链):一套 path-表身份 / query-表提示的 grammar、三种 envelope(逻辑 ID / `web+cokret:` URI scheme / HTTPS fragment 落地),以及对象级解析 operation `cx.directory.resolve_target`。地址层纯寻址,授权由绑定 canonical target 的签名 token 承载,分 `reference` / `invite` 两型(`preview` 保留不实现)。

- **变更类型**: add
- **影响 artifact**: registry / openapi / non-http binding / prose
- **canonical 变更**:
  - `contract-catalog.json#operation_registry`: 注册 1 个新 operation `cx.directory.resolve_target`(`POST /directory/resolve-target` / `Directory/ResolveTarget` / `directory.resolve_target`),加入 `directory_discovery` surface group。
  - `operations-error-mapping.json`: 为 `cx.directory.resolve_target` 注册 operation-specific `not_found`(镜像 `resolve_realm`)。
  - 无新 event kind / schema / capability / id kind;不改任何 wire / reducer 行为。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 重新生成 `operation-registry.json` 等视图;`check` 验证 drift clean。`cokret-service-api.openapi.yaml` 增 `/directory/resolve-target` path(通用 `OperationRequest`/`OperationResult`);`non-http-bindings.yaml` gRPC Directory 段增 `ResolveTarget`。
- **conformance impact**:
  - 受影响 profile: 无新 profile;`resolve_target` 属 directory discovery extension surface,实现按既有 directory profile 声明。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible(纯新增 operation;`resolve_realm` 保留共存,未 deprecate)。
  - reader / writer 行为要求: `resolve_target` MUST 在 realm 解析上委托 `resolve_realm`;携带 token 时 MUST 按 target descriptor 逐级校验再走 join-policy;未授权统一 `not_found`;web protocol handler 模板 MUST fragment-only。
- **fixture / vector 变化**: 无(本次未新增 conformance vector)。
- **prose 同步**:
  - `zh/discovery/object-addressing.md`: 新增 normative 文件(grammar / 三 envelope / link 类型 / token target 绑定 / 隐私 / `resolve_target` 契约)。
  - `zh/discovery/discovery-directory.md` §9: 新增 `resolve_target` operation 行 + 交叉引用。
  - `zh/sync/service-http-binding.md` §2.3: HTTP endpoint 表 + field-level 表 + POST 列表增 `resolve-target`;operation 计数 100 → 101。
  - `zh/overview/release-readiness.md`: Service operation 计数 100 → 101。
  - `zh/spec-map.md`: 新增 `discovery/object-addressing.md` 索引行。
- **迁移指南**: backward-compatible add;实现按以下顺序采纳即可——
  1. 升级 `contract-catalog.json` 并 `artifact_pipeline.py generate`。
  2. Directory 服务实现 `resolve_target`,realm 分支委托既有 `resolve_realm`。
  3. 客户端实现 `web+cokret:` 注册(web handler 模板 fragment-only)与 HTTPS fragment 落地解析。
  4. invite token 复用 join-policy `invite_token` / `signed_link` 生命周期,签发时绑定 target descriptor digest。

### Personal AI Agent provisioning & sidecar threads(CXP-0008 / CXP-0009)(2026-05-26)

引入 native personal AI agent 的端到端创建、运行时认证、capability 委托、生命周期管理路径,以及 controller 与其 native agents 之间的私聊上下文线程(sidecar thread)。Native agent 与 Applet-managed Ghost AI agent 是两类不同 actor,Realm policy 必须能分别控制。

- **变更类型**: add
- **影响 artifact**: schema / registry / profile / prose / conformance
- **canonical 变更**:
  - `event-schema.json`: Event Envelope 增加 `executed_by`(signed, conditional)、`authorization_ref`(signed, conditional)、`actor_kind`(reducer-stamped projection, immutable);加入新 reducer-input event kinds `cx.agent.pause` / `cx.agent.resume` / `cx.agent.deactivate` 与 actor_private event kinds `cx.agent.draft.propose` / `cx.agent.action_request` / `cx.agent.action_approve` / `cx.agent.action_reject`。
  - `event-payload.schema.json`: `agent_key_authorize_payload` 增加可选 `runtime_attestation`(v1 baseline `kind="self_asserted"`,未知 kind fail closed)。
  - `event-kind-registry.json`: 注册上述 7 个新 event kinds(3 lifecycle + 4 draft/action)。
  - `operation-registry.json`: 注册 `cx.account.agent_key_pair`、`cx.agent.provision` / `list` / `get` / `pause` / `resume` / `deactivate` / `rotate_key` / `grant.attach` / `grant.detach`、`cx.agent.sidecar_thread.ensure`(共 11 个)。
  - `capability-action-registry.json`: 注册 14 个新 actions(`cx.agent.provision` / `pause` / `resume` / `deactivate` / `draft.propose` / `action_request` / `action_approve` / `action_reject` / `sidecar_thread.ensure` / `sidecar_thread.write` / `sidecar_thread.publish`);aggregate action 显式声明 `target_event_kinds` 并标 migration_group。
  - `account-data-type-registry.json`: 注册 `cx.agent.draft.v1` (controller-private, encrypted_at_rest) 与 `cx.agent.sidecar_projection.v1` (controller-private)。
  - `relation.md`: 标准 relation kinds 加入 `agent_sidecar_of`(weak-semantic, non-structural, non-cascading)。
  - `conformance-profiles.json`: 注册 4 个 profile `cx.profile.personal_agent_provisioning.v1` / `cx.profile.agent_auth.v1` / `cx.profile.agent_delegation_policy.v1` / `cx.profile.agent_sidecar_thread.v1`。
- **conformance impact**:
  - 受影响 profile: 4 个新 profile;`cx.profile.full_client.v1` / `cx.profile.e2ee_client.v1` / `cx.profile.principal_server.v1` 在支持 personal agent 时 SHOULD 声明上述新 profile。
  - profile tier 变化: 4 个新 profile 列入 v1 profile catalog。
  - wire 兼容性: backward-compatible(新字段 `executed_by` / `authorization_ref` / `actor_kind` 都是 conditional 或 reducer-stamped;旧 event 无须改写)。
  - reader / writer 行为要求: receiver MUST 拒绝未知 critical extension;reducer MUST 拒绝 actor-supplied `actor_kind`;`executed_by` 出现时 MUST 校验 proof.verification_method 对应该 DID。
- **fixture / vector 变化**: `conformance-vectors.md` 新增 §11 共 9 个 vectors,覆盖 provisioning + pairing + grant 生效顺序、pairing 过期自动撤销、session grant replay 防护、controller deactivate cascade、act-on-behalf attribution、sidecar Circle 幂等 ensure、existence privacy、eligibility 三态 + revocation 闭环、multi-agent publish attribution。
- **prose 同步**:
  - `zh/models/event-and-patch.md` §2.2 / §2.4:`executed_by` / `authorization_ref` / `actor_kind` 字段与 normative 规则。
  - `zh/models/actor.md` §3.3:native personal agent vs Ghost Actor 边界、reducer-stamped `actor_kind` projection。
  - `zh/identity/key-management.md` §3.6.1:personal agent runtime pairing 与 session normative 规则。
  - `zh/identity/account-lifecycle.md` §9.1:agent pause/resume/deactivate 语义与 controller lifecycle 传播。
  - `zh/authz/capabilities.md` §5.4:14 个新 actions。
  - `zh/models/relation.md` §3:`agent_sidecar_of` relation kind。
  - `zh/models/circle.md` §11.1:agent sidecar Circle 形态约束。
  - `zh/models/private-objects.md` §4.1 / §4.2:draft 与 sidecar projection account-data 与隐私边界。
  - `zh/sync/service-surface.md` §10.1:Personal Agent surface 与 operations。
  - `zh/conformance/conformance-profiles.md` §18.1–18.4:4 个新 profile 详情。
  - `zh/extensions/applet-integration.md` §3.4.1:Ghost Actor vs Native Personal Agent 边界。
  - `zh/extensions/agent-protocol-interop.md` §7.1:外部 agent protocol session 与 personal agent runtime session 边界。
- **迁移指南**: backward-compatible add;实现按以下顺序采纳即可——
  1. 升级 `event-schema.json` / `event-payload.schema.json`,扩展 reducer 处理 `executed_by` / `authorization_ref` / `actor_kind`。
  2. 实现 `cx.account.agent_key_pair` 与 `SessionGrantRequest` 的 `agent_key_proof` 分支,独立 schema branch + 独立 proof validator。
  3. 实现 `cx.agent.provision` orchestration 与 lifecycle operations。
  4. 实现 sidecar `cx.agent.sidecar_thread.ensure` 与 controller_agent_circle_key 派生。
  5. UI 实现 sidecar exposure 披露(CXP-0009 §3 invariant 10 / CXP-0008 §4.5)。
- **CXP**: [`spec/v1/proposals/0008-personal-agent-provisioning.md`](spec/v1/proposals/0008-personal-agent-provisioning.md) / [`spec/v1/proposals/0009-agent-sidecar-thread.md`](spec/v1/proposals/0009-agent-sidecar-thread.md)。

### Naming consistency pass for id/ref/content/size fields（2026-05-26）

按 `common-fields.md` 的严格语义规则统一字段前后缀：对象自身主标识用 `id`，单一具体 kind 外引用用
`<kind>_id`，reference material 用 `_ref`，序号用 `_seq`，字节数用 `_bytes`，顶层内容块用
`content`。

- **变更类型**: modify
- **影响 artifact**: schema / fixture / openapi / profile / registry / prose / lint
- **canonical 变更**:
  - `snapshot.schema.json`: manifest 自身字段 `snapshot_ref` → `id`；外部指向 snapshot 的
    `snapshot_ref` 保持不变。
  - `event-schema.json` 与 `event-batch-receipt.schema.json`: `$defs` 内部定义名
    `profileRef` / `featureRef` / `eventRef` / `criticalExtension` →
    `profile_ref` / `feature_ref` / `event_ref` / `critical_extension`。
  - `key-backup.schema.json`: `series_sequence` → `series_seq`，错误码同步为
    `series_seq_not_monotonic`。
  - `blob.schema.json` / `media-metadata.schema.json`: 字节数 `size` → `size_bytes`。
  - `realm.schema.json`: `created_by_principal` → `created_by`。
  - `flow.schema.json`: 顶层 `body` → `content`；content block 内部 `body` 字段保持不变。
  - privacy / service feature 枚举：`flow_body` / `message_body` / `body_only` →
    `flow_content` / `message_content` / `content_only`。
- **派生 artifact 同步**: OpenAPI、fixtures、fixture digest reference、profile/registry 描述与 prose
  已同步；`tools/lint_artifacts.py` 新增 legacy alias guard。
- **conformance impact**:
  - 受影响 profile: 任何读写 Snapshot / Realm / Flow / Blob / MediaMetadata / KeyBackup 或
    service feature/privacy profile 的实现。
  - profile tier 变化: 无。
  - wire 兼容性: **breaking**（候选稿命名收敛）。
  - reader / writer 行为要求: Writer MUST emit canonical names；reader MAY 在迁移层识别旧名，
    但 schema validation MUST reject canonical object 中的旧字段。
- **fixture / vector 变化**: key-backup、privacy-security、schema-validation fixtures 与
  `fixture-digests.json` 已更新。
- **prose 同步**: `zh/models/common-fields.md`、Snapshot / sync / Realm / Flow / Blob / KeyBackup /
  E2EE 相关章节已同步。
- **迁移指南**: 下游实现需替换上述字段名与枚举值；Snapshot manifest 的 `id` 与 API/chunk/challenge
  中的 `snapshot_ref` 必须按“自身标识 vs 外部引用”区分处理。

### Key-backup hardening: series chain, recovery policy / receipt schemas, first-backup gate（2026-05-26）

闭合 v1 候选稿中"用户密钥备份"复审发现的多处缺口：(a) recovery policy 只有内联示例无 schema 与 lifecycle；(b) 备份 envelope 无法防止服务端静默 rollback；(c) recipient method 中只有 `passphrase_kdf` 完整；(d) recovery receipt 无 schema；(e) cross-signing reset 与 `secret_storage` backup refresh 无窗口耦合；(f) inception key 退场无 first-backup 硬前置；(g) `cx.secret_storage.v1` wire deprecation 与 retention/erasure 交互未规范。

- **变更类型**: add（recovery_policy / recovery_receipt schema、backup series 链字段、first-backup gate、recipient method profiles、server-side rate limiting、recovery UI MUSTs、retention/erasure 表）+ modify（`cx.schema.key_backup.v1` 字段与 signed_fields；`cx.profile.key_backup.memory_hard.v1` 必需 endpoints / schemas / fixtures / feature_discovery；openapi `cx.keys.backups.list` 查询参数）。
- **影响 artifact**:
  - 新增 `schemas/recovery-policy.schema.json`（`cx.schema.recovery_policy.v1`）、`schemas/recovery-receipt.schema.json`（`cx.schema.recovery_receipt.v1`）。
  - 修改 `schemas/key-backup.schema.json`：required 集合追加 `series_id` / `series_seq`；新增 `supersedes` / `supersedes_digest` / `frontier_ref` 字段；signed_fields 必须覆盖 series & supersedes，并在 `series_seq >= 1` 与 `frontier_ref` 存在时按条件分支扩展；新增 genesis vs successor 的 `allOf` 互斥约束。
  - 修改 `openapi/cokret-service-api.openapi.yaml`：`cx.keys.backups.list` 新增 `?series_id=` 与 `?backup_class=` 查询参数。
  - 修改 `profiles/conformance-profiles.json#cx.profile.key_backup.memory_hard.v1`：endpoints 扩展至 put/list/get/delete；required_schemas 增加两个新 schema；required_fixtures 加 `key-backup-fixture.json`；feature_discovery 增加 series chain / freshness anchor / recipient method profiles / server rate limit / recovery policy & receipt 6 项。
  - 新增 `fixtures/key-backup-fixture.json`：9 个 `schema_validation_cases`（正/负向）。
  - 修改 registries：
    - `id-kind-registry.json`: 新增 `backup_series`、`recovery_session`。
    - `schema-registry.json`: 新增 `cx.schema.recovery_policy.v1`、`cx.schema.recovery_receipt.v1`。
    - `error-code-registry.json`: 新增 11 条 reason codes（`series_chain_broken` / `series_seq_not_monotonic` / `series_predecessor_not_found` / `recovery_policy_mismatch` / `share_commitment_mismatch` / `backup_frontier_stale` / `backup_post_reset_stale` / `legacy_secret_storage_wire_form` / `recovery_evidence_unbound` / `unsupported_aead_profile` / `attestation_missing`）。
  - 修改 prose：
    - `zh/identity/key-management.md` §5.0.1 step 6（first-backup gate）；新增 §7.5 Recipient Method Profiles、§7.6 Backup Series & Freshness、§7.7 Recovery UI Requirements、§7.8 Server-Side Hardening、§7.9 Algorithm Agility；§8 替换 recovery_policy 内联示例为 `cx.schema.recovery_policy.v1` 形态并新增 §8.1 policy lifecycle / §8.2 holder retrieval；§10 / §11 conformance 行补强。
    - `zh/crypto-media/device-lifecycle.md` §11 新增 wire deprecation 段；§12 example 与 prose 同步 series 字段；§12.1 PUT 三类 409 reason / GET filter / DELETE high-risk proof；新增 §12.2 Retention and Erasure；§14.2 新增 step 7（reset → secret_storage backup refresh 同步窗口）；§14.5 step 7 收紧到 `cx.schema.recovery_receipt.v1` 校验。
    - `zh/overview/release-readiness.md`: schema 54→56、typed ID 41→43、raw schema file 54→57。
- **canonical 变更**: `cx.schema.key_backup.v1` wire 要求扩展（新 required 字段、条件分支签名覆盖、新 typed-id kind）；新增两类 wire payload schema。`cx.keys.backups.list` 操作扩展查询参数。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 已重新生成 schema-registry / id-kind-registry / 其它派生视图；`python tools/artifact_pipeline.py check` clean（`159 event kinds, 56 schemas, 43 typed ID kinds, 87 operations, 58 claimable profiles, 79 profile id references`）；`python tools/lint_artifacts.py`、`python tools/lint_spec.py`、`python tools/check_fixture_digests.py` 全部通过。`fixture-digests.json` 已更新。
- **conformance impact**:
  - 受影响 profile: `cx.profile.key_backup.memory_hard.v1`（feature_discovery 与 required_fixtures 扩张）；`cx.profile.cross_signing.reset.v1`（reset accepted 后新增 `secret_storage` backup refresh 同步窗口要求）。
  - profile tier 变化: 无新增 profile 层级；既有 hardening profile 收紧。
  - wire 兼容性: **breaking** 对仍处于 candidate 状态的 `cx.schema.key_backup.v1`（required 集合扩展、signed_fields 条件覆盖）；候选稿期内引入，未影响已发布 v1.0 稳定基线。
  - reader / writer 行为要求:
    - Writer MUST emit `series_id` / `series_seq` on every backup envelope, set `supersedes`+`supersedes_digest` on successors, and cover them in `auth_data.signed_fields`.
    - Reader MUST `LIST` per series_id, verify the `supersedes`/`supersedes_digest` chain, and decrypt only from the tail. On stale frontier or post-reset stale envelope MUST emit `backup_frontier_stale` / `backup_post_reset_stale`.
    - Server MUST enforce series monotonicity & predecessor existence on `PUT`, return the three 409 reasons listed in `zh/crypto-media/device-lifecycle.md §12.1`, and rate-limit `GET` per §7.8 defaults.
    - Server MUST reject legacy `cx.secret_storage.v1` wire envelopes with `schema_violation reason=legacy_secret_storage_wire_form`.
- **fixture / vector 变化**: 新增 `fixtures/key-backup-fixture.json`（series chain / passphrase_kdf nonce_salt / Argon2id 下限 / PBKDF2 degraded reason / mixed_secret_storage strict KDF / successor digest 强制）。后续 release 应补 KAT-级别正向 fixture（passphrase → KDF → nonce → AEAD KAT）。
- **prose 同步**: `zh/identity/key-management.md` §5.0.1 / §7 / §8 / §10 / §11；`zh/crypto-media/device-lifecycle.md` §11 / §12 / §14.2 / §14.5；`zh/overview/release-readiness.md`。
- **迁移指南**: 实现侧最小变更清单：
  1. 在产生新备份 envelope 时分配 `series_id`、把 `series_seq` 设为 0（genesis）或现有最大 +1（successor）。
  2. successor 在签名前先 canonicalize 前一条 envelope（排除 `auth_data.signature`）并计算 `supersedes_digest`；把 `supersedes` / `supersedes_digest` / `frontier_ref?` 加入 `auth_data.signed_fields`。
  3. 备份恢复路径切到 `LIST?series_id=` 路径，按 sequence 顺序重建链并仅使用尾部。
  4. inception bootstrap 完成首台 `cx.device.authorize` 后，**先**发布 `backup_class=did_recovery` envelope（或离线封存 receipt）再让 inception key 退场。
  5. cross-signing reset 接收后 24h 内为现存 `secret_storage` series 发布后继 envelope，否则恢复流程将拒绝旧 envelope。
  6. 旧 `cx.secret_storage.v1` 远端对象一次性迁移到 `cx.schema.key_backup.v1`；wire endpoint 升级后不再接受旧形态。

### Clarify `alsoKnownAs` narrow scope and verification authority/cache split（2026-05-26）

`identity-handles.md` 长期把 `alsoKnownAs` 与 "客户端 / verifier 双向验证" 写成笼统规则，导致两类常见误读：(a) 实现者把 `alsoKnownAs` 当作 mention 索引 / Directory 主键 / 投递路径的候选字段；(b) 不清楚 Principal Server / Directory 对 `binding_state=verified` 的代验是 hint 还是权威背书。本次新增 §4.1 与 §6.0 两节，把"`alsoKnownAs` 只服务公开 handle 的 holder-side 反向背书"与"first-party 客户端验证才是 authority，server-side 预验只是 cache hint"两条边界写进规范。

- **变更类型**: edit（description / prose only）
- **影响 artifact**: `zh/identity/identity-handles.md`
- **canonical 变更**: 无（无 schema / registry / wire field 变化）。新增 §4.1 列出 `alsoKnownAs` 不参与的机制（投递路由、Realm 加成员、actor 归因、Principal Server 搬迁、受限 handle、pairwise / 设备 / agent DID、跨上下文 unlinkability、handle 重分配历史归因）及其对应权威字段；改写 §6 顶层把"客户端 MUST 解析 DID Document"一般化为"verifier MUST 取得 DID Document 当前内容"，并显式枚举两条达成路径（live parse 或 verifier 自有 / co-trusted 缓存按 §6.1.1 / §6.1.2 命中）；新增 §6.0 把 verifier 分为 Authority（first-party MUST：wallet 披露 / accept invite / join official Realm / 跨组织 federation 信任决策 / audit-trail 记录）与 Pre-verification & Cache（SHOULD first-party；MAY use bounded cache：verified 徽章 / mention autocomplete / 联系人卡片展示）两层，并规定缓存失效或 §6.1.2 信号触发时 UI MUST 降级为 unverified。Server-attested hint 的可选附加字段（DID Document digest 副本、`alsoKnownAs` proof 副本）显式声明为实现层，v1 不为此层定义规范 wire schema；互操作性由"verifier MUST 保留独立 re-verify 能力"保证。
- **派生 artifact 同步**: 无（无 catalog / registry 改动；不触发 `tools/artifact_pipeline.py` 重生成）。
- **conformance impact**:
  - 受影响 profile: 无（既有 MUST 不变，新增的 §6.0 把"verifier 自验"的隐含期望显式化）。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible（description-only）。
  - reader / writer 行为要求: 无新增 wire MUST；新增 prose MUST 是"做信任决策的一方 MUST first-party 验证、MUST NOT 把 server-attested `binding_state` 当作权威背书"，与既有 §6 / §6.1 缓存规则一致。
- **fixture / vector 变化**: 无。
- **prose 同步**: 仅 `zh/identity/identity-handles.md` §4.1（新增）/ §6 顶层（改写）/ §6.0（新增）；其它章节通过既有引用链自然受益。
- **迁移指南**: 实现侧无 wire / API 变更。若实现把 `alsoKnownAs` 用作 mention 索引、Directory 主键、缓存键、投递路径或 actor 归因依据，应按 §4.1 表格迁回对应权威字段（`delivery_binding.recipient_service_did` / `MemberDeliveryBindingCandidate` / issuer claim / event `actor_id`）。

### CXP-0007: introduce Circle primitive; remove Flow.discussion_realm_ref（2026-05-25）

引入 **Circle**（`ck:circle:`）作为 Realm 内的密码学子边界（独立 MLS group / 子集成员 / 独立 history visibility），同时**彻底删除** `Flow.discussion_realm_ref` 字段及其全部补丁规则（§5.0.1 跨 Realm lifecycle 级联表、§8.9 watch 跨 Realm 投影、改绑禁令等）。Flow 永远只有一个 effective encryption scope —— "一对象一安全边界"成为协议级硬不变量。

- **变更类型**: add（Circle 原语 + `Flow.scope_ref` / `Space.scope_ref` / `Space.default_scope_ref` / `Space.child_scope_policy` / `Morph.scope_ref`）+ remove（`Flow.discussion_realm_ref` 与 §5 整节 / §5.0.1 / §5.1 / §8.9 旧形态）。
- **影响 artifact**:
  - 新增 `schemas/circle.schema.json`（`cx.schema.circle.v1`）。
  - 修改 `schemas/flow.schema.json`：删除 `discussion_realm_ref` 字段；追加 `scope_ref`；更新 `tracks` / `flow_track` description（消除 per-track 安全边界假设）。
  - 新增 normative 文档 `zh/models/circle.md`。
  - 重写 `zh/models/flow-and-message.md` §1 / §3 schema 表 / §4.3 / §4.4 / §4.6 / §5（整节）/ §8.3 / §8.5 / §8.9 / §9.4；删除 §5.0.1 lifecycle 表、§5.1 mermaid 图。
  - 修改 `zh/overview/architecture.md` §2.0 容器选型表（追加 Circle 行，删除 `discussion_realm_ref` 行）。
  - 修改 `zh/overview/glossary.md`：删除 `Linked Discussion Realm` 条目，修订 `discussion track` 条目，新增 `Circle` / `Circle scope` / `effective_scope` 条目。
  - 修改 `zh/overview/current-model.md` §6 / §7（MLS 边界改为 Realm-default + Circle 双层）。
  - 修改 `zh/models/realm-and-space.md` §2.2（Circle 替代"辅助 MLS group"）、§2.6 cascade 表（Circle scope cascade 替代 Discussion Realm edge cascade）。
  - 修改 `zh/models/realm-links.md` §1 序言；`zh/models/overview.md` 关系图；`zh/models/private-objects.md` §2.3；`zh/models/views.md` §6.1。
  - 修改 `zh/authz/capabilities.md` §1 / §3 / §6.x；`zh/authz/resource-selector-grammar.md` §4.4。
  - 修改 `zh/sync/operations-sync.md` §7.2 / §7.4 / §11；`zh/sync/service-surface.md` §6.2。
  - 修改 `zh/discovery/push-notifications.md` §4.3；`zh/discovery/read-receipts.md` §2.5 / 字段表。
  - 修改 `zh/crypto-media/encryption-and-audit.md`：MLS admin set / epoch_update_required / cache invalidation / `scope` 字段定义全部改为 `(realm_id, circle_id?)` 复合 scope。
  - 修改 `zh/extensions/mimi-interop.md` §9.1（MIMI room policy 投影规则）。
  - 修改 `zh/conformance/conformance-vectors.md`（Flow discussion 可见性条件改为 effective scope）、`zh/conformance/encoding.md`（`<noun>_ref` 例子换为 `scope_ref`）、`zh/conformance/query-schema.md` §5（查询授权检查改为 effective scope）。
  - 修改 `zh/index.md` §4.3；`zh/spec-map.md`（新增 `circle.md` 行，修订 `flow-and-message.md` 描述）。
  - 修改 registries:
    - `id-kind-registry.json`: 新增 `circle`。
    - `schema-registry.json`: 新增 `cx.schema.circle.v1`。
    - `event-kind-registry.json`: 新增 7 条 `cx.circle.*` event kinds（`cx.circle.create` / `update` / `archive` / `restore` / `tombstone` / `member.state` / `anchor_commit`）。
    - `capability-action-registry.json`: 新增 6 条 capability actions（`cx.circle.create` / `cx.circle.manage` / `cx.circle.member.add` / `cx.circle.member.manage` / `cx.circle.member.add.others` / `cx.circle.audit`）。
    - `forbidden-wire-fields.json`: 新增 `discussion_realm_ref` 进入 reserved-name guard（`hard_reject`，reason=`discussion_realm_ref_removed`）；更新既有 `discussion_space_ref` 条目的 replacement 指向 `scope_ref`。
    - `error-code-registry.json`: 新增 6 条 reason codes（`circle_realm_mismatch` / `circle_not_active` / `circle_member_must_be_realm_member` / `scope_rebind_forbidden` / `metadata_encryption_floor_violation` / `discussion_realm_ref_removed`）。
    - `renames.json`: 新增 `discussion_realm_ref`（object_field, replacement=null）与 `Linked Discussion Realm`（glossary_term, replacement=Circle），migration_group=`cxp_0007_circle_introduction`。
    - `forbidden-model-terms.json`: 修订 `Room` / `track members` 条目，从"linked discussion Realm" 改为 "Circle (intra-Realm cryptographic sub-boundary)"。
    - `removed-event-kinds.json`: 修订 `cx.flow.track.member` / `cx.flow.track.history_visibility` / `cx.flow.track.policy_components` 三条 notes。
- **canonical 变更**: Flow 顶层字段 `discussion_realm_ref` 删除；Flow 顶层字段 `scope_ref`（id:circle, optional, null = Realm-default scope）新增。Event envelope / payload / AAD / Anchor leaf 新增 reducer-stamped immutable tagged `effective_scope`（`{kind:"realm"|"circle", realm_id, circle_id?}`）。
- **派生 artifact 同步**: canonical registry 已重新生成并通过 `python tools/artifact_pipeline.py check`：`159 event kinds, 54 schemas, 41 typed ID kinds, 87 operations, 58 claimable profiles, 79 profile id references`，`registry diff: clean`。Circle schema / event kind / typed ID / capability action / error code / rename / forbidden-field artifacts 已落地。v1.0 stable promotion 前仍必须关闭 CXP-0007 §8.1 机器契约缺口：`effective_scope` submit-input 与 reducer-output schema 角色需显式区分，Message / Anchor output shape 与 Anchor leaf canonical bytes 需绑定 `effective_scope`，`content_encryption_floor` 需机器化，`confidential_discussion_of` Relation 需注册并验证，Circle sub-anchor + `cx.circle.anchor_commit` 固定节拍 profile 与 completion conformance vector cluster 需落地或被正式 de-scope。
- **conformance impact**:
  - 受影响 profile: `core_event_store`（新增 Circle event kinds 与 effective_scope canonical bytes）、`chat_mvp`（讨论可见性改按 effective scope 判断）、`e2ee_v1`（Realm-default 与 Circle 独立 MLS group；Realm-member-removal 触发 N+1 rotate amplification，详见 [`zh/models/circle.md` §10.3](spec/v1/zh/models/circle.md)）。
  - profile tier 变化: 尚未同步 Circle/effective-scope vector/profile 要求；除非在 freeze 前明确 de-scope，否则属于 stable release blocker。
  - wire 兼容性: **breaking**（删除字段 + 新增字段 + 新增 immutable envelope tag）。本变更必须在 v1 freeze 前 ship；freeze 后将升级为 v2 breaking change。
  - reader / writer 行为要求:
    - Writer MUST NOT emit `discussion_realm_ref` on the v1 wire.
    - Reader MUST reject `discussion_realm_ref` with `schema_violation reason=discussion_realm_ref_removed`.
    - Reader MUST stamp / verify `effective_scope` on every Event envelope (cryptographically bound; subsequent rebinds MUST NOT reinterpret prior events).
    - Sync Service MUST filter Circle-scoped events at delivery time per `effective_scope` membership (zh/models/circle.md §9.3).
- **fixture / vector 变化**: 尚未同步 Circle/effective-scope fixture / vector cluster；当前 `vector-registry.json`、`fixtures/` 与 `conformance-profiles.json` 未形成可执行的 Circle coverage。CXP-0007 §8.1 第 8 步必须在 v1.0 stable 前落地，或在 release notes 中明确降级为 post-freeze 非 v1.0 contract。
- **迁移指南**: 见 [CXP-0007 §8](spec/v1/proposals/0007-circle-primitive.md) Migration plan 与 [renames.json](spec/v1/artifacts/registry/renames.json) `cxp_0007_circle_introduction` migration group。对"宽 synthesis + 窄 discussion" 业务诉求，改用两个 Flow + `confidential_discussion_of` Relation（见 [`zh/models/circle.md` §7.2](spec/v1/zh/models/circle.md)）。

### Description-only doc enhancements from `_simple_report_claude.md` review（2026-05-24）

`_simple_report_claude.md` review 后接受的 4 项低风险文档增强；无 wire / canonical 变更，纯 description / prose 改动。

- **变更类型**: edit（description / prose only）
- **影响 artifact**: `contract-catalog.json` id_kind_registry + 派生 `id-kind-registry.json`; `schemas/device-message.schema.json`（字段 description）; `zh/identity/tsp-integration.md`; `zh/overview/glossary.md`
- **canonical 变更**: 无（catalog 中 `agent_session` id_kind 的 `kind` / `wire_form` 不变，仅扩写 description 说明 typed-id / event kind / capability action 三 surface 的双名映射，指向 `capabilities.md §5.0` 与 `renames.json` `wire_compat_grandfather` migration_group）；`device-message.schema.json` 的 `sender_principal_id` / `recipient_principal_id` 仅追加 description 解释为何 device messages 不沿用 `*_actor_id`；`tsp-integration.md` 把 TSP 首次出现处统一为 "Trust over IP 框架的 Trust Spanning Protocol（TSP）"；`glossary.md` 的 `synthesis track` / `discussion track` 末尾各追加 "详见 `../models/flow-and-message.md` §4.2 / §4.3" 链接（与 `MLS Governance Binding` entry 同款模式）。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 重生成派生 registry；`check` 输出 `Artifact registry lint passed (152 event kinds, 53 schemas, 40 typed ID kinds, 87 operations, 58 claimable profiles, 79 profile id references)` 与 `registry diff: clean`。
- **conformance impact**:
  - 受影响 profile: 无。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible（description-only）。
  - reader / writer 行为要求: 无新增 MUST；description 旨在防止 SDK 团队再次提"把 device-message 字段对齐成 *_actor_id"或"把 agent_session ↔ protocol_session 解释成机械推导"类 PR。
- **fixture / vector 变化**: 无。
- **prose 同步**: TSP 与 glossary 改动如上；`flow-and-message.md` 不变（glossary 主动引用 §4.2 / §4.3）。
- **迁移指南**: 无 wire 改动；下游无需迁移。

### Collapse `read_scope.kind` track variants（2026-05-24）

`read-cursor.schema.json` 的 `read_scope.kind` enum 内联了 `flow_discussion` / `flow_synthesis` 两个 track 专用变体，把 v1 标准 track 名硬编码进了 schema enum，与 "track set is profile-extensible" 的设计相互矛盾。本次折叠到 `kind: "flow"` + 已有的 `track` 字段表达。

- **变更类型**: remove（enum 值移除，breaking for any stored data that used the two collapsed values）
- **影响 artifact**: `schemas/read-cursor.schema.json`; `fixtures/schema-validation-fixture.json`; `zh/discovery/read-receipts.md`; `zh/sync/operations-sync.md`
- **canonical 变更**: `read_scope.kind` enum 从 8 项减为 6 项（移除 `flow_discussion` / `flow_synthesis`）；track-scoped read cursor 必须改用 `{kind: "flow", ref: ck:flow:…, track: "discussion" | "synthesis" | <profile-registered>}`。`kind` / `track` 字段 description 同步更新，阐明 track 名集合可由 profile 扩展。
- **派生 artifact 同步**: 无 catalog 派生影响；`python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 53 schemas, 40 typed ID kinds, 87 operations, 58 claimable profiles, 79 profile id references)` 与 `registry diff: clean`.
- **conformance impact**:
  - 受影响 profile: read receipt / read cursor 实现。
  - profile tier 变化: 无。
  - wire 兼容性: **breaking** for stored read cursors that used `flow_discussion` / `flow_synthesis`；reader / writer MUST 用 `kind: "flow"` + explicit `track`.
  - reader / writer 行为要求: writers MUST emit only the new shape; readers MUST reject the two removed enum values with `schema_violation`.
- **fixture / vector 变化**: `schema-validation-fixture.json` 已迁移到新 shape；无需新增 vector.
- **prose 同步**: `read-receipts.md` §3.2 / §6.1 与 `operations-sync.md` `cx.read_cursor.advance` 示例已同步。
- **迁移指南**: 旧 actor-private read cursor 存储在加密 account data 中，迁移由 client 端在首次升级时一次性重写：`flow_discussion` → `{kind: "flow", track: "discussion"}`；`flow_synthesis` → `{kind: "flow", track: "synthesis"}`. Reducer 对旧 enum 值 fail closed.

### Naming normalization closure pass（2026-05-24）

补齐 `_name_report.md` / `_name_report_codex.md` 中命名归一化项的 wire、schema、registry 与 prose 闭环。

- **变更类型**: rename + remove（breaking for old wire names）
- **影响 artifact**: `renames.json`; `forbidden-wire-fields.json`; `removed-event-kinds.json`; `event-kind-registry.json`; `id-kind-registry.json`; `schema-registry.json`; `capability-action-registry.json`; `contract-catalog.json`; schemas (`capability-grant`, `policy`, `attestation-evidence`, `event-schema`, `event-payload`, `realm`, `read-cursor`, `handle-claim`, moderation / delivery / receipt schemas); fixtures (`encoding`, `crypto-signature`, validation fixtures); OpenAPI; `zh/**` prose.
- **canonical 变更**: ID prefix 缩写全部展开（`ck:notif:` / `ck:devmsg:` / `ck:keyevt:` / `ck:modq:` / `ck:req:` / `ck:txn:` / `ck:frank:` → full snake_case）；agent/device event kind 改为 imperative（`authorize` / `revoke` / `rotate`）；`cx.relation.delete` → `cx.relation.tombstone`; `read-marker` → `read-cursor`; 时间字段统一为 `not_before` / `expires_at`; `signed_by` → `verification_method`; `sender` → `sender_actor_id`; Event proof 使用 `event_digest`; CRDT lattice 字段 / enum 统一为 `lattice` + snake_case; Directory / projection alias 回归 canonical 字段名; `_did` 主体别名改为 `_id`; handle claim delivery routing single-source 到 `member_delivery_binding.recipient_service_did`.
- **派生 artifact 同步**: registry、schema、fixture、OpenAPI 与 prose 已同步；本条要求 `python tools\lint_artifacts.py` 通过，并要求旧 wire alias 由 `renames.json` / `forbidden-wire-fields.json` / `removed-event-kinds.json` 提供 fail-closed 依据。
- **conformance impact**:
  - 受影响 profile: core event envelope validation、identity handles、directory discovery、read receipts/cursors、device lifecycle、agent key authorization、moderation/franking、capability authorization。
  - profile tier 变化: 无。
  - wire 兼容性: **breaking** — 旧字段名、旧 Event.kind、旧 typed ID prefix 和旧 schema id 不再合法；只允许在 changelog、legacy migration helper 或 negative test 中出现。
  - reader / writer 行为要求: writers MUST emit only canonical names; readers / reducers MUST hard-reject old forms with `schema_violation` except where explicitly marked legacy migration.
- **fixture / vector 变化**: `encoding-fixture.json` 的 Event Batch Receipt canonical bytes / digest 更新为 `receipt_scope`; crypto detached JWS fixture 重算 `event_digest` / binding hash / signature；schema validation fixtures 与 negative fixtures 同步旧名拒绝面。
- **prose 同步**: `common-fields.md` 新增 naming convention；identity handles、directory、read receipts、device lifecycle、content moderation、sync surface、conformance vectors 等章节同步。
- **迁移指南**: 下游 SDK / validator 需要重新生成 typed ID、event kind、schema id 与 field-name 常量；旧 wire form 应根据 `renames.json` 做一次性迁移，运行时 parser / reducer 对旧 form fail closed。

### Report consolidation closure pass（2026-05-24）

合并 `_codex_report.md` 与 `_claude_report.md` 中经复核成立、且不需要重塑现有概念的闭环修订。

- **变更类型**: add + edit（reason code closure、typed ID registry、authz freshness diagnostics、normative prose hardening）
- **影响 artifact**: `error-code-registry.json`; `contract-catalog.json` id_kind_registry + 派生 `id-kind-registry.json`; `event-payload.schema.json`; `resource-selector.schema.json`; `openapi/cokret-service-api.openapi.yaml`; `tools/lint_artifacts.py`; `zh/{authz,crypto-media,discovery,extensions,guides,identity,overview,sync}`；`proposals/0002..0006` 外部参考链接。
- **canonical 变更**: 新增 `ck:announce:<uuid>` typed ID kind；新增 `revocation_freshness_unknown`、`realm_already_exists`、`out_of_order_bootstrap`、`policy_revision_gap`、`moderation_anchor_lifted`、`e2ee_relaxed_federation_policy_unsupported`、`deactivation_federation_incomplete`、`selector_actor_wildcard_forbidden` reason codes；清理 `reason_codes` 内部重复的 `audit_agent_attestation_mismatch`；`AuthzCheckResponse` 增补 freshness 诊断字段；`actor:*` selector 明确禁止。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`；`python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 53 schemas, 40 typed ID kinds, 87 operations, 57 claimable profiles, 78 profile id references)` 与 `registry diff: clean`; `node site/scripts/crossref-check.mjs` 输出 `crossref ok (152 event kinds, 253 errors, 87 operations, 53 schemas, 57 profiles)`。
- **conformance impact**:
  - 受影响 profile: core authz/federation freshness、account deactivation federation、Directory ingest、E2EE relaxed profile guard、resource selector validation。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible add + breaking for invalid inputs only（`actor:*`、未登记的 announce id 形态、缺 freshness fail-closed reason 的响应）。
  - reader / writer 行为要求: writers MUST use `ck:announce:<uuidv7>` for Directory announce records; authz/federation receivers MUST use `revocation_freshness_unknown` for high-risk unknown/stale revocation freshness; resource selector parsers MUST reject `actor:*`.
- **fixture / vector 变化**: 本轮不新增 vector fixture；新增 lint 覆盖 `_unknown` / `_incomplete` reason-code closure、error registry section 内重复 code，以及旧 `ann_*` Directory announce id 形态回归。
- **prose 同步**: 已更新 authz selector grammar、capability freshness diagnostics、federation probe/deactivation fanout、service HTTP binding、release readiness/schema consumption、operations sync、Directory announce、MIMI candidate join-policy guard 与 cross-signing reset audit pairing。
- **迁移指南**: 下游 SDK / validator 需要重新生成 typed ID 常量并接受 `ck:announce:<uuidv7>`；若旧实现返回 `revoke_freshness_unknown` 或 `ann_*`，应迁移到本条 canonical 名称和 typed ID 形态。若旧 grant 或 fixture 中存在 `actor:*`，writer MUST 改为具体 DID 集合或 claim-based subject condition；reducer / importer 在加载既有 `actor:*` grant 时 MUST fail closed（`schema_violation` + `selector_actor_wildcard_forbidden`）并使相关授权缓存失效。

### Review closure pass for `_claude_report.md`（2026-05-24）

对 `_claude_report.md` 中经核验成立的 schema / registry / normative prose 缺口做最小闭环修订。

- **变更类型**: edit + add（schema capacity constraints、reason codes、drift registry disambiguation、normative prose hardening）
- **影响 artifact**: `event-schema.json`; `error-code-registry.json`; `removed-event-kinds.json`; `renames.json`; `forbidden-wire-fields.json`; `zh/{authz,conformance,crypto-media,discovery,extensions,governance,identity,models,overview,sync}` 多个 normative 文档。
- **canonical 变更**: `prev_refs` / `refs[]` 增加 schema-level `maxItems`（128）与 `prev_refs.uniqueItems=true`; `cx.space.create/update` 的 removed/rename registry 改为 payload-shape disambiguation，避免与 active container-shape event kind 同名冲突；新增 Space payload 上 Realm-level 字段的 forbidden-wire-field guard；新增 reason codes 覆盖容量、principal-control Realm 归属、bottom-state、DID upgrade stale evidence、MIMI fail-closed taxonomy、agent endpoint retire/malformed response、join gate 不可枚举失败、Realm default 解析不可用等。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py check` 输出 `Artifact registry lint passed (152 event kinds, 53 schemas, 39 typed ID kinds, 87 operations, 57 claimable profiles, 78 profile id references)` 与 `registry diff: clean`; `node site/scripts/crossref-check.mjs` 输出 `crossref ok (152 event kinds, 245 errors, 87 operations, 53 schemas, 57 profiles)`。
- **conformance impact**:
  - 受影响 profile: core Event Envelope validation、principal_control_realm、MIMI interop、agent runtime、push gateway、join policy、MLS/E2EE hardening。
  - profile tier 变化: 无。
  - wire 兼容性: breaking for invalid inputs only（超长 refs、pre-inversion Space-as-boundary payload、stale DID transfer evidence、未绑定 control Realm 的 device authorization 等均必须 fail closed）。
  - reader / writer 行为要求: writer MUST respect refs capacity and current Space payload shape; reducers MUST enforce newly clarified fail-closed reason paths; readers MUST not use HLC as final timeline order before causal closure is known.
- **fixture / vector 变化**: 本轮不新增 vector fixture；已有 lint 与 registry closure 覆盖 reason-code / artifact 引用。
- **prose 同步**: 已更新 scalability、event auth/state resolution、key management、federation、encoding、MIMI interop、push notifications、read receipts、join policy、space hierarchy、agent interop、glossary 等章节。
- **迁移指南**: 下游 cotest / SDK generator 需要把 `removed-event-kinds.json` 的 `wire_id + disambiguation_payload_shape` 作为判定旧 `cx.space.*` 的输入；不能再只用 Event.kind 字符串 hard reject 当前 active `cx.space.create/update`。

### Register canonical ephemeral send operation（2026-05-22）

把 `cx.schema.ephemeral_envelope.v1` 的广播发送入口从 prose-only "ephemeral channel" 落到规范 HTTP / gRPC / MQ operation。

- **变更类型**: add
- **影响 artifact**: `contract-catalog.json` operation_registry;派生 `operation-registry.json`;`openapi/cokret-service-api.openapi.yaml`;`bindings/non-http-bindings.yaml`;`zh/sync/{operations-sync,service-http-binding,service-api-schema.mdx}`;`zh/discovery/read-receipts.md`;`zh/overview/release-readiness.md`。
- **canonical 变更**: 在 `events_sync` surface group 注册 `cx.ephemeral.send`，HTTP binding 为 `POST /ephemeral`（部署路径 `/api/v1/ephemeral`），gRPC `Ephemeral/Send`，MQ `ephemeral.send`。请求体为 `cx.schema.ephemeral_envelope.v1`，只承载 `cx.presence` / `cx.typing` / `cx.receipt.read` / `cx.call.signal`，不得写入 durable Event history 或推进 actor_seq / Realm frontier。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`；operation 计数更新为 86。
- **conformance impact**:
  - 受影响 profile: `events_sync` core surface 增加可发现 operation；实现必须在 `supported_operations` 中声明实际支持。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible add。
  - reader / writer 行为要求: writer MUST send broadcast ephemeral signals through `cx.ephemeral.send` or an advertised equivalent binding，MUST NOT fall back to `cx.events.submit`；reader MUST drop expired signals and treat them as non-durable UI hints。
- **fixture / vector 变化**: 暂无新增 conformance vector；server/client implementation tests 覆盖 canonical endpoint。
- **prose 同步**: 已更新 wire-scope 表、HTTP endpoint/field 表、transport mapping 与 read receipt 发送说明。
- **迁移指南**: 下游实现若此前使用部署本地 `/sync/typing`、`/typing`、`/receipts` 或 `/receipts/read`，SHOULD 迁移到 `POST /api/v1/ephemeral`；旧路径只能作为实现本地兼容 shim。

### Register lifecycle projection read surface（2026-05-22）

把 Space / Flow / Morph lifecycle projection 读端从实现私有路径提升为规范 extension surface。

- **变更类型**: add
- **影响 artifact**: `contract-catalog.json` operation_registry;派生 `operation-registry.json`;`openapi/cokret-service-api.openapi.yaml`;`bindings/non-http-bindings.yaml`;`zh/sync/{service-http-binding,service-api-schema.mdx}`;`zh/overview/release-readiness.md`。
- **canonical 变更**: 新增 `projection_lifecycle` surface group，注册 `cx.projection.spaces` / `cx.projection.flows` / `cx.projection.morphs`，HTTP binding 分别为 `GET /projection/spaces` / `GET /projection/flows` / `GET /projection/morphs`。该 surface 是 extension tier，返回 reducer 派生 read model，不是真相源。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`，并通过 `python tools/artifact_pipeline.py check`；operation 计数更新为 85。
- **conformance impact**:
  - 受影响 profile: 无 core profile 强制新增；实现必须通过 `supported_operations` 显式声明支持。
  - profile tier 变化: 无。
  - wire 兼容性: backward-compatible add。
  - reader / writer 行为要求: reader MUST treat projection rows as derived state only；writer MUST continue to write canonical Event history and not mutate projection rows directly。
- **fixture / vector 变化**: 暂无新增 conformance vector；现有 server implementation tests 覆盖路径和 terminal filtering。
- **prose 同步**: 已更新 `service-http-binding.md` REST namespace / endpoint / field 表，`service-api-schema.mdx` transport mapping，`release-readiness.md` registry 计数。
- **迁移指南**: 下游实现若此前暴露实现私有 `/projection/space-containers` 或 `space_containers` wire 名，SHOULD 迁移到 canonical `/projection/spaces` 与 `spaces[]/space_id` 响应；旧名只能作为部署本地兼容 alias。

### Split `/sync` namespace; convert account aggregate to streaming subscribe; rename `cx.events.batch_get` → `cx.events.resolve`（2026-05-21）

三件事原子合并:

1. 拆 `/api/v1/sync` 命名空间:`/account/*` 承载 account 聚合,`/snapshot/*` 承载 snapshot manifest 入口。
2. **account 聚合从 long-poll 转为 streaming push**: 旧 Matrix-derived `cx.account.sync` / `POST /account/sync` 一次性切成 `cx.account.subscribe` / `GET /account/subscribe`,响应 wire 形态从单 JSON object 改为 `application/x-ndjson` frame 流。`cx.account.subscribe` 与 `cx.events.subscribe` 因此成为对称的两类 streaming 订阅(account-aggregate vs per-Realm event log),共享 cursor / `dropped` / `resync_required` 恢复语义。
3. `cx.events.batch_get` / `POST /events/batch-get` 重命名为 `cx.events.resolve` / `POST /events/resolve`(reference → object 解引用,与 `cx.identity.resolve` / `cx.directory.resolve_*` 同族)。

`POST /events`(submit) 与 `GET /events?…`(query) 路径形态保持不变。

- **变更类型**: rename + delivery-model change (both breaking)
- **影响 artifact**: `contract-catalog.json` operation_registry + capability_action_registry + schema_registry;派生 `operation-registry.json` + `capability-action-registry.json` + `schema-registry.json`;`openapi/cokret-service-api.openapi.yaml`(路径、operationId、method、schema 名、Content-Type、frame description);`bindings/non-http-bindings.yaml`(gRPC service + mq topic);`profiles/conformance-profiles.json`(operation_id + schema_id 引用,matrix_compat 描述);`registry/error-code-registry.json`(error description 中的路径文本);`schemas/{cursor,bottom,account-subscribe-frame}.schema.json`(新建 account-subscribe-frame,删除 client-sync-response);`fixtures/sync-fixture.json`(recovery `call` 字段);`tools/{apply_pd6_security.py,lint_artifacts.py}`(operation_id 映射 + describe path 列表)。
- **canonical 变更**: `contract-catalog.json` 中 5 个 operation 重命名(`cx.sync.account` → `cx.account.subscribe`(同时 wire 形态从 POST 改为 GET streaming)、`cx.sync.describe` → `cx.account.describe`、`cx.sync.get_snapshot_head` → `cx.snapshot.head`、`cx.events.batch_get` → `cx.events.resolve`),以及对应 http / grpc / mq 绑定路径全部更新;schema_registry 中 `cx.schema.client_sync_response.v1` 重命名为 `cx.schema.account_subscribe_frame.v1`,对应 schema 文件从 `client-sync-response.schema.json` 重写为 `account-subscribe-frame.schema.json`(新增 `kind` 字段及 7 种 frame 变体: `delta` / `catchup_complete` / `frontier` / `heartbeat` / `dropped` / `resync_required` / `unauthorized`,delta 变体的 body 字段与旧 schema 一致);surface_groups[`events_sync`].operations 同步更新;`cx.events.query_post` HTTP wire alias 维持现状不变。
- **派生 artifact 同步**: 已运行 `python tools/artifact_pipeline.py generate`;registry 视图、OpenAPI、non-http bindings、conformance profiles 已与 catalog 对齐。
- **conformance impact**:
  - 受影响 profile: 所有 require `cx.sync.*` operation_id 的 profile (principal_server.v1、core_event_store.v1、chat_mvp.v1 等十余个) 已迁移到新名字;`cx.profile.matrix_compat.v1` 描述更新——不再声明 `/account/sync` wire-shape parity(streaming push 与 Matrix long-poll `/sync` 不再兼容,其他 Matrix-derived surfaces 如 to-device / keys / push gateway 的 parity 保持)。
  - profile tier 变化: 无。
  - wire 兼容性: **breaking** — 旧路径 `POST /sync`、`GET /sync/describe`、`GET /sync/snapshot-head`、`POST /events/batch-get`、`POST /account/sync` 全部不再合法;旧 operation_id `cx.sync.*` / `cx.events.batch_get` / `cx.account.sync` 不再注册;account-aggregate 消费循环从 `POST` long-poll 改为 NDJSON streaming GET。
  - reader / writer 行为要求: 客户端 MUST 把上述路径 / operation_id / wire delivery model 一次性切到新形态;不保留旧 alias。客户端 MUST 维护长连接 + frame-driven 重连(规则见 `client-sync.md` §2.0)。
- **fixture / vector 变化**: `sync-fixture.json` recovery 字段 `cx.sync.get_snapshot_head` → `cx.snapshot.head`;现有 conformance vectors 自身路径文本中的 `/sync*` / batch_get / account.sync 已通过 prose 文档传播性更新覆盖。
- **prose 同步**: 已更新 `zh/sync/{service-surface,service-http-binding,client-sync,federation,operations-sync,transport-bindings,service-api-schema.mdx}`(其中 `client-sync.md` §2 整段重写为 streaming 连接管理 + frame kind 表 + 重连规则,新增 §2.0 连接管理章节;`service-http-binding.md` §5 拆为 §5 Account API + §6 Snapshot API,后续 sections 顺延)、`zh/authz/capabilities.md` §5.* 操作清单、`zh/conformance/{conformance-profiles,schema-registry,encoding}.md`、`zh/identity/key-management.md`。
- **迁移指南**: 客户端实施侧 (1) **账号聚合**: `POST /account/sync` (单次响应) → `GET /account/subscribe` (长连接 NDJSON);消费循环改为 frame loop,delta frame 推数据,`dropped` frame 用 `cx.events.query` 补齐,`resync_required` 全量重建。(2) `GET /sync/describe` → `GET /account/describe`。(3) `GET /sync/snapshot-head?realm_id=…` → `GET /snapshot/head?realm_id=…`。(4) `POST /events/batch-get` → `POST /events/resolve`(请求 / 响应 body 形状不变,仅路径与 operation_id 变)。(5) operation_id 引用同步更新。`POST /events`(submit) 与 `GET /events?…`(query) 路径不变;`cx.events.query_post` (POST /events/query) 仍为同一逻辑查询的 HTTP body 形式 wire alias,操作语义保持原貌。客户端 HTTP/2+ 部署对两条 streaming 长连接(`events.subscribe` + `account.subscribe`)是多路复用的,无额外 TCP 槽消耗;HTTP/1.1 部署多占 1 个 TCP 槽,仍在 per-origin 6-connection 上限内。

### Withdraw `cx.profile.agent_workspace.v1`（2026-05-20）

撤销 agent workspace extension profile 及其所有派生工件。"用户本地 agent 协作上下文"被重新归位为部署本地关切，不再属于协议层。一般性的 agent 参与（agent 加入 Realm、capability、A2A/ACP 协议会话）通过既有的 `cx.member.state` / `cx.capability.grant` / `cx.agent.*` 表面继续支持。

- **变更类型**: remove
- **影响 artifact**: 整体删除 `spec/v1/zh/extensions/agent-workspace-profile.md`、`spec/v1/artifacts/fixtures/agent-workspace-fixture.json`、`spec/v1/artifacts/conformance/agent-workspace/`（44 个向量）、`spec/v1/artifacts/schemas/agent-task.schema.json`、`spec/v1/artifacts/schemas/agent-authority.schema.json`、`spec/v1/artifacts/schemas/content-mention-redirect.schema.json`、`spec/v1/artifacts/schemas/content-import-attestation.schema.json`、`spec/v1/artifacts/schemas/content-source-export-policy-attestation.schema.json`。从 `contract-catalog.json` 及派生的 event-kind / schema / id-kind / capability-action / operation 视图中删除全部 `cx.agent_task.*`、`cx.agent_workspace.*`、`cx.capability.agent_workspace.*`、`cx.schema.agent_task.v1`、`cx.schema.agent_authority.v1`、`cx.schema.content.{mention_redirect,import_attestation,source_export_policy_attestation}.v1`、`ck:agent_task:` typed ID、`cx.feature.{mention_redirect,import_attestation,governed_import,agent_workspace_lite}.v1`、`cx.capability.agent_workspace.{reserve,recover,cleanup}`、`mention_respond_only` / `import_to_external_space` 约束、`agent_membership_change` 通知类型、`mirror_of` realm link kind、`CokretAgentWorkspaceService` DID service 类型以及与之绑定的全部 error code（`source_export_*`、`reservation_cell_already_set`、`conflicting_agent_workspace_profiles`、`lite_profile_writes_disallowed_event_kind`、`invalid_task_fsm_transition`）。OpenAPI / non-http bindings / `tools/apply_pd6_security.py` 中的相关 endpoint 与绑定一并删除。
- **canonical 变更**: `contract-catalog.json` 删除 ~120 条 entry；`profiles/conformance-profiles.json` 删除 4 个 profile id（`cx.profile.agent_workspace.v1` / `.lite.v1` / `.governed.v1` / `.strict.v1`）。
- **派生 artifact 同步**: registry 视图、OpenAPI、non-http bindings 已与 catalog 同步；conformance 目录在本次提交后为空。
- **conformance impact**:
  - 受影响 profile: `cx.profile.agent_workspace.v1` 系列全部移除；`cx.profile.agent_runtime.v1` 不再 require `cx.schema.agent_authority.v1`。
  - profile tier 变化: `extension_profile_implementation` 列表中移除 4 个 id。
  - wire 兼容性: breaking（声明该 profile 或发出对应事件 / 操作的实现 MUST 停止）；尚未存在已发布的 wire 用户，所以实际迁移面狭窄。
  - reader / writer 行为要求: writer MUST NOT emit 已删除事件；reader MUST `schema_violation` 拒绝（由 `removed-event-kinds.json` 与 `removed-operation-ids.json` 强制）。
- **fixture / vector 变化**: 44 个 `conformance/agent-workspace/*` 向量删除；`agent-workspace-fixture.json` registry anchor 删除。
- **prose 同步**: 已更新 `zh/spec-map.md`、`zh/authz/capabilities.md` §5.7 / §5.8 / §6、`zh/authz/constraint-schema.md` §2.2、`zh/authz/event-auth-state-resolution.md` §5.3.3、`zh/models/content-types.md` §2 / §4.11 / §4.12、`zh/models/realm-links.md`、`zh/models/private-objects.md`、`zh/identity/identity-did.md`、`zh/sync/federation.md` §9.5、`zh/sync/service-http-binding.md` §2.3、`zh/conformance/conformance-profiles.md`、`zh/conformance/schema-registry.md`、`zh/extensions/agent-protocol-interop.md` §3.1、`zh/crypto-media/encryption-and-audit.md`、`zh/overview/architecture.md`。
- **迁移指南**: 需要"私人 agent 工作上下文"的部署应在自家 profile 中声明等价语义并使用私有的事件 / schema id，不得复用任何已收录到 removed-event-kinds.json / removed-operation-ids.json / deprecated-profile-ids.json 的标识符。

### Round 3 cleanup pass on `_todos.md`（2026-05-20）

承接 round 1 + 2，本轮 close 10 项最重的 P0/P1 任务（T02、T06、T07、T10、T11、T12、T14、T15、T16、T17）。三轮累计 close 29 项 spec-body 任务；剩余 3 项（T29 tooling / T31 / T32 design）标 `evaluate_only` 留给后续独立 session。这一批新增了 4 个 event kind、3 个新 schema、1 个新 typed ID kind、9 个新 error code、4 个新 conformance vector reference，是迄今最接近"协议体内新增"的一轮。

- **变更类型**: add（4 event kinds / 3 schemas / 1 typed ID kind / 9 error codes / 多条 prose 新增 section）+ edit（schema 收紧、prose 加 normative 段）
- **影响 artifact**: schemas (`event-schema`, `cursor`, `anchor`, `flow`, `ephemeral-envelope` [新增], `moderation-appeal` [新增], `attestation-evidence` [新增])、registries (`contract-catalog` → 派生 event-kind / schema / id-kind / capability-action / operation registries、`error-code-registry` 新增 9 条)；`profiles/conformance-profiles.json`；以及 `spec/v1/zh/**` 多个 prose 文件（`identity/account-lifecycle.md`、`identity/consent-model.md`、`models/realm-and-space.md`、`models/event-and-patch.md`、`sync/operations-sync.md`、`sync/federation.md`、`sync/third-party-invites.md`、`governance/content-moderation.md`、`crypto-media/encryption-and-audit.md`、`crypto-media/audited-e2ee.md`、`crypto-media/media-and-blob.md`、`crypto-media/webrtc-signaling.md`、`overview/release-readiness.md`）。
- **canonical 变更**:
  - **T02 (Durable/ephemeral envelope 拆分)**：`event-schema.json` 加 `not` allOf 分支显式拒绝 12 个 `wire_scope=ephemeral_event` kind 出现在 durable Event Envelope（cx.call.signal / cx.presence / cx.typing / cx.receipt.read / cx.key.verification.*）；从 if/then 非 reducer 枚举中移除 ephemeral 项，保留 actor_private 项。新增 `ephemeral-envelope.schema.json` (schema id `cx.schema.ephemeral_envelope.v1`) 定义广播 ephemeral 信号的独立 envelope（kind + realm_id + actor_id + sent_at + expires_at + payload + optional proof，expires_at 硬上限 5 分钟）；点对点 to-device 仍用 `device-message.schema.json`。`operations-sync.md` 加 §3.6 wire-scope 边界规范表 + 5 条 reject 规则。
  - **T06 (Moderation appeal wire 闭环)**：新增 4 个 active event kind：`cx.moderation.appeal.submit` / `.review` / `.decision` / `.close`，统一指向 schema `cx.schema.moderation_appeal.v1`（[`moderation-appeal.schema.json`](spec/v1/artifacts/schemas/moderation-appeal.schema.json) 单 schema oneOf 出四种 payload）。新增 typed ID kind `ck:appeal:<uuid>`。新增 2 个 capability action：`cx.moderation.appeal.submit`（low risk, 任何成员）+ `cx.moderation.appeal.review`（medium risk, moderator）。`content-moderation.md` 新增 §5.5 完整描述事件链、cell state machine (none → submitted → under_review → decided → closed)、separation of duties (reviewer ≠ original decision issuer)、overturn 与 lift 原子绑定、modify 与新 decision 原子绑定、cool-off / auto close、evidence_visibility 4 档枚举。新增 2 个错误码 `appeal_overturn_missing_lift` / `appeal_self_review_forbidden`。
  - **T07 (Lifecycle 级联)**：`account-lifecycle.md` 新增 §7.1 Deactivation Fanout 7 域表（session / device / applet / KeyPackage / push / to-device queue / capability cache）+ MLS deactivation grace window + partial fanout 状态。`realm-and-space.md` 新增 §2.5 Realm 终态：明确 `cx.realm.tombstone`（successor）vs `cx.realm.destroy`（永久退役）区分；§2.5.1 destroy 后 5 条 normative 规则（拒后续普通写、snapshot/backfill/GC、no successor、erasure receipt 与 legal hold 优先级、federation fanout 30 天）；§2.5.2 跨 Principal Server erasure receipt fanout（issuing → receiving、partial 状态 → `outcome=partially_completed`、未回执 7 天后 fanout_status=incomplete、hash chain stub 保留 + projection 显示 `[erased]`）。新增错误码 `realm_terminal_state`。
  - **T10 (Attested audit evidence schema)**：新增 `attestation-evidence.schema.json` (schema id `cx.schema.attestation_evidence.v1`) 把 attestation 证据结构化：platform (family/vendor/model/firmware) + measurement (code_hash/policy_version/report_data) + attestation_chain (多种 quote format) + attestation_key (与 epoch_key_destruction 共享 root of trust) + verification_method + validity 窗口 ≤90 天 + revocation 检查 + operator_did + audit_purpose + audit_policy_version_hash + proofs (operator 与 enclave 双密钥分离)。`audited-e2ee.md` §2 表把 `attested_hardware` 描述对接到此 schema，去掉"prose 自报"形态。新增 2 个错误码 `audit_agent_attestation_mismatch` / `audit_purpose_mismatch`。
  - **T11 (Presign blob audience 边界)**：`media-and-blob.md` `audience_hint` 字段说明从 "仅 hint" 升级为 "**诊断 hint，不构成访问控制**"；新增 §5.4.4.1 normative：实现 MUST NOT 把 audience_hint 当访问控制；E2EE ciphertext / legal hold / redacted / actor_private blob MUST 走 fail-closed (拒绝发 presign)；future audience-bound 机制（cookie-bound / session-bound）超出 v1 范围。新增 §5.4.4.2 bearer URL 泄漏面控制（Cache-Control private no-store / Referrer-Policy no-referrer / 不记录 presign query 原文）。新增 2 个错误码 `legal_hold_active` / `blob_redacted`。
  - **T12 (SFU/MCU 治理绑定)**：`webrtc-signaling.md` 新增 §10.3.1：`media_service_decrypts=true` MUST (a) 由 `cx.realm.policy_components` 写入并受 policy_root 覆盖；(b) SFU service DID 进 `plaintext_visible_services[]` 标 `purpose=media_plaintext`；(c) MLS governance binding policy_root 覆盖；(d) downgrade 拒绝 OOB；(e) negative vector 覆盖 3 种 attack path。新增 2 个错误码 `media_plaintext_service_not_authorised` / `mls_governance_binding_stale`。
  - **T14 (Federation idempotency cache 绑定 service key)**：`federation.md` 新增 §8.5.1：idempotency cache entry MUST 携带 `Source-Service-DID` / `verification_method` / `service_binding_ref` / `origin_key_state_hash`；撤销后重放 MUST 返回 `historical_only`，不触发新副作用；cache hit MUST 重做 capability check；negative vector 覆盖 3 种 revoke-after-cache 路径。
  - **T15 (3PID OOB code 熵 + 失败清理)**：`third-party-invites.md` 把 OOB code 例从 `XYZ-123-ABC` 升级为 `XYZ7-K9MP-...`（22+ chars base32 排除易混字符），并加 normative 段定义 OOB code 仅 2 种合法形态：(1) 离线可校验 ≥128-bit 熵；(2) 服务端 lookup 短码 + pepper/HMAC + 限速 + `oob_code_kind="lookup"` 字段 + 3 次错误 invalidate。新增 §6.1 失败 / 异常清理状态机覆盖 7 种触发（expired / send_failed / capability loss / inviter left / revoked / claim success / rate_limit invalidated），统一不可枚举响应（byte-identical + timing ≤50ms）。新增错误码 `expired_invite_token`。
  - **T16 (Late key recovery 状态机)**：`encryption-and-audit.md` 新增 §2.6.1 Late Key Recovery 状态机：明确 `decryption_pending → decryption_failed → late_recovered`（4 个 transition + 4 条 accept 条件 a/b/c/d：membership 时点 + policy 时点 + key share 来源授权 + audit profile 强制 emit `cx.audit.accessed` late_recovery=true）；revoked/removed actor 收到迟到 key MUST 不解密（vector `cx.vector.late_key_recovery.removed_actor.v1`）；§2.6.2 late_recovered 与 redaction/erasure 的关系（`redacted_after_recovery`，audit marker 保留）。新增错误码 `late_recovery_rejected_membership`。
  - **T17 (Consent revoke scope + 缓存失效)**：`consent-model.md` 新增 §4.1：(4.1.1) Scope cascade — `scope=any` revoke MUST cascade 到全部子 scope（`superseded_by_any_revoke` 标记），反向不成立；(4.1.2) 缓存失效表覆盖 5 类缓存（directory reachability、MIMI consent check、push/contact discovery PSI、invite gate cache、in-flight invite 不追溯），`any` revoke MUST cascade 失效所有 scope entry。新增 vector reference `cx.vector.consent.scope_cascade.v1` + `cx.vector.consent.cache_invalidation.v1`。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 更新 `event-kind-registry`、`schema-registry`、`id-kind-registry`、`operation-registry`、`capability-action-registry`；`check` 输出 `Artifact registry lint passed (155 event kinds, 57 schemas, 40 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`；`npm run crossref` 输出 `crossref ok (155 event kinds, 54 errors, 84 operations, 57 schemas, 59 profiles)`；`cd site && npm run build` 562 pages 0 warning（较 round 2 的 555 增加 7 页：4 个新 event kind + 3 个新 schema + 2 个新 capability action - 重复入口）。
- **conformance impact**:
  - 受影响 profile: 无新增 profile；现有 moderation / audit / e2ee profile 描述同步细化。
  - profile tier 变化: 无。
  - wire 兼容性: **wire-breaking**（增量）— (a) `cx.events.submit` 现在 MUST 拒绝任何 ephemeral_event kind（cx.call.signal / cx.presence / cx.typing / cx.receipt.read / cx.key.verification.*），早期实现若误把这些当 durable Event 提交 MUST 更新 routing；(b) Realm `media_service_decrypts=true` 现在 MUST 经过 policy_components + policy_root + plaintext_visible_services 三处绑定，没有走完整路径的 SFU 会被拒绝媒体；(c) federation idempotency cache 实现需要把 `Source-Service-DID` / `origin_key_state_hash` 纳入 cache key；(d) 3PID OOB code 短随机串（旧 `XYZ-123-ABC` 等）MUST 满足新 (1) 或 (2) 两种合法形态之一。
  - reader / writer 行为要求: SDK MUST 更新 (i) ephemeral signal 路由到 ephemeral-envelope 或 device-message channel，不再走 cx.events.submit；(ii) moderation appeal 写入路径完整 4 events + 2 capability + cell state machine；(iii) deactivation fanout 涵盖 7 域（session/device/applet/KeyPackage/push/to-device queue/capability cache）；(iv) Realm destroy 后只接受 audit-class event；(v) Audit Agent 入群 attestation evidence 走 `cx.schema.attestation_evidence.v1`；(vi) presign URL 严格 fail-closed for E2EE/legal hold/redacted/private；(vii) federation idempotency cache 重做 capability check on hit；(viii) OOB code 满足熵或 lookup 形态约束；(ix) late_recovered transition emit audit marker + 4 条 accept 条件全部 pass。
- **fixture / vector 变化**: 新增 6 个 conformance vector references（待补可执行 fixture）：`cx.vector.webrtc.media_plaintext_downgrade.v1`、`cx.vector.federation.idempotency_after_key_revoke.v1`、`cx.vector.invite.oob_code_entropy.v1`、`cx.vector.invite.failure_indistinguishable.v1`、`cx.vector.late_key_recovery.removed_actor.v1`、`cx.vector.consent.scope_cascade.v1`、`cx.vector.consent.cache_invalidation.v1`。
- **prose 同步**: 每项都同步修改对应中文 normative prose；`overview/release-readiness.md` 计数表更新 (151→155 / 54→57 / 39→40)。
- **不在本轮范围**: T29（markdown/fixture schema lint 工具化 — 是 tools/ Python 改动，标 `evaluate_only`）；T31（Directory member count side-channel 降噪 — 设计决策，需团队评估 k-anonymity / bucket rounding）；T32（MLS governance binding codepoint IANA 申请 / 迁移策略 — 公开联邦发布前的设计决策）。三项均在 `_todos.md` 标 `evaluate_only`。
- **迁移指南**:
  - SDK / yougen / soland：(i) ephemeral signal 路由切换到 `cx.schema.ephemeral_envelope.v1` 或 `cx.schema.device_message.v1`，不再走 `cx.events.submit`；(ii) 实现 `cx.moderation.appeal.*` 4 events + capability gate + separation of duties；(iii) deactivation fanout 7 域；(iv) Realm destroy → only audit-class accept；(v) Audit Agent join 走 attestation-evidence；(vi) presign blob 4 类必拒；(vii) federation idempotency cache 加 `Source-Service-DID` / `origin_key_state_hash`；(viii) OOB code 满足熵约束；(ix) late_recovered 4 条 accept 条件 + audit marker；(x) consent revoke 缓存失效 5 类。
  - cotest / drift validator：把 9 个新增错误码（`realm_terminal_state`、`audit_agent_attestation_mismatch`、`audit_purpose_mismatch`、`legal_hold_active`、`blob_redacted`、`media_plaintext_service_not_authorised`、`mls_governance_binding_stale`、`expired_invite_token`、`late_recovery_rejected_membership`、`appeal_overturn_missing_lift`、`appeal_self_review_forbidden`）纳入错误码白名单；4 个新 event kind（`cx.moderation.appeal.{submit,review,decision,close}`）纳入 active event kind 白名单；3 个新 schema（`cx.schema.moderation_appeal.v1`、`cx.schema.ephemeral_envelope.v1`、`cx.schema.attestation_evidence.v1`）纳入 schema 白名单；1 个新 typed ID kind `ck:appeal:<uuid>` 纳入 id kind 白名单。
  - 文档作者：检索 `cx.realm.destroy` / `cx.moderation.appeal` / `late_recovered` / `attestation_evidence` / `audience_hint` / `idempotency cache` / OOB code，引用更新到新 normative 段。

### Round 2 cleanup pass on `_todos.md`（2026-05-20）

承接 round 1，继续 close `_codex_report.md` / `_claude_report.md` P0/P1/P2 待办：本轮 close 7 项（T01、T03、T04、T08、T09、T13、T23）。这一批以 schema / canonical-transcript / 跨域 replay 防御 / receiver fail-close hard ceiling 为主，比 round 1 改动更接近协议语义层。

- **变更类型**: edit + add（schema 新字段、registry 新 typed ID kind、error-code-registry 新条目、新 conformance vector 段落）
- **影响 artifact**: schemas (`anchor`, `cursor`, `cross-signing-reset`)、fixtures (`move-anchor-lattice-fixture`, `encoding-fixture`)、registries (`contract-catalog` → `id-kind-registry` 派生、`error-code-registry`)、`profiles/conformance-profiles.json`；以及 `spec/v1/zh/**` 多个 prose 文件（`authz/event-auth-state-resolution.md`、`conformance/conformance-vectors.md`、`crypto-media/audited-e2ee.md`、`crypto-media/device-lifecycle.md`、`crypto-media/encryption-and-audit.md`、`identity/identity-did.md`、`models/event-and-patch.md`）。
- **canonical 变更**:
  - **T01 (Anchor 内容寻址去自引用)**：`event-auth-state-resolution.md` §4 明确列出 Anchor canonical bytes transcript fields 表（`id` 与 `anchorer_sig` 显式排除）；`anchor.schema.json` 的 schema description、`id`、`anchorer_sig` 字段加 description 描述 `id = "ck:anchor:" || H(anchor_canonical_bytes)` 不自引用、signature 不签自己；新增 receiver verification 三步流程 (a) recompute H 校验 `id`；(b) 验证 `anchorer_sig` 覆盖 canonical bytes；(c) attack 必然在 (b) 或 (c) 失败。`conformance-vectors.md` 新增 §2.8.1 `cx.vector.move_anchor_lattice.anchor_canonical_no_self_reference.v1`，覆盖 6 种 case：base + id-in-canonical-bytes attack + sig-in-canonical-bytes attack + key reorder + proof injection + non-digest frontier value。
  - **T03 (Cursor fixture/schema)**：`encoding-fixture.json` cursor vector 修正 (a) `ck:space:` → `ck:realm:`（同时 base64url 与解码后 canonical bytes）；(b) `t/x` 时间戳搬到 2099-12-30 ~ 2099-12-31（24h TTL，远早于 stream cursor 7 天上限），加 `fixture_freshness_note` 提醒"不要把固定 fixture 时间戳搬到 wire"。`cursor.schema.json` (a) `h.minLength: 16 → 22` 把 ≥128-bit base64url entropy 强制成 schema 检查（128/6 ≈ 21.33）；(b) 新增 `_mac` 类型属性（pattern `^hmac-(?:sha256|sha384|sha512):[0-9a-f]{64,128}$`）与 `_sig` 类型属性（pattern compact-JWS `<protected>.<payload?>.<signature>`），各自约束 wire 形态；(c) `patternProperties` 中辅助 `_*` 字段的 regex 改为 `^_(?!mac$|sig$)[A-Za-z0-9_]*$`——禁止用 `_mac_foo` / `_sig_bar` 冒充 integrity 字段，只有精确字段名 `_mac` / `_sig` 被典型化为整性字段。
  - **T04 (Anchor frontier event_digest)**：`move-anchor-lattice-fixture.json` 的 frontier entries 与 anchor schema `frontier[]` items 对齐为 `sha256:<hex>` 形态；fixture notes 明确 frontier 直接引用 content-addressed `event_digest`。
  - **T08 (Cross-signing reset 跨域 replay 防御)**：`device-lifecycle.md` §14.1 canonical input 在 transcript 顶部新增 `trust_domain` + `reset_event_id`（紧接 `cx-cross-signing-reset-v1\n` magic header）；新增 normative 段说明 deployment A 签发的 proof bytes 无法被 deployment B 重放（trust_domain mismatch ⇒ transcript fail）、新 Event shell 重放也会失败（reset_event_id mismatch ⇒ transcript fail）。`cross-signing-reset.schema.json` payload required 字段加 `trust_domain` (`ck:trust_domain:<scope>`) 与 `reset_event_id` (`ck:event:<uuidv7>`)；receiver 验证顺序 (a) `cross_domain_replay_rejected` (b) `reset_event_id_mismatch` (c) `invalid_signature`。`identity-did.md` 新增 §3.6 Trust Domain 节正式定义 `ck:trust_domain:` 字段与三处暴露位置（server describe / Realm policy / proof transcript），并把 trust_domain 注册进 `contract-catalog.json` → `id-kind-registry.json` 派生（新增 1 个 typed ID kind `ck:trust_domain:`）。`error-code-registry.json` 新增 `cross_domain_replay_rejected` + `reset_event_id_mismatch` 两条错误码。
  - **T09 (e2ee_relaxed 硬上限 + receiver fail-close)**：`conformance-profiles.json` 的 `cx.profile.e2ee_relaxed.v1.downgrade_window_constraint` 加 `absolute_hard_ceiling_ms: 300000`、`receiver_enforcement`（receiver MUST 独立 enforce 硬上限，不得静默 clamp；reducer reject policy write `> 300000 ms` 用 `relaxed_window_exceeds_ceiling`）与 `compliance_profile_disabled`（声明 `cx.profile.attested_audit.e2ee.v1` / `disclosed_audit.e2ee.v1` 或 `audit_assurance >= disclosed_policy` 时 MUST 拒绝 relaxed profile，用 `e2ee_relaxed_disallowed_in_compliance_profile`）。`error-code-registry.json` 新增对应两条错误码。`encryption-and-audit.md` §2.4.1 prose 同步说明硬上限与合规互斥；新增 negative vector 引用 `cx.vector.e2ee_relaxed.window_exceeds_ceiling.v1`。
  - **T13 (Identity Link 缓存 policy tightening)**：`encryption-and-audit.md` §2.7 把缓存 value 增加 `policy_frontier_hash`（推荐 `sha256(canonical_json({policy_revision, disclosure_policy, history_visibility, identity_disclosure_profile, metadata_encryption_profile, minimal_metadata_mode}))`），并新增 policy tightening eager invalidation 规则覆盖 (a) `cx.identity.disclosure_policy` strictness 升级；(b) `cx.realm.policy_components` 中 `metadata_encryption_profile` / `minimal_metadata_mode` / `identity_disclosure_profile` 变化；(c) `cx.realm.history_visibility` 收紧；(d) linked Realm (`Flow.discussion_realm_ref` / `Realm.linked_realms[]`) membership / history visibility 收紧。比较时用 constant-time 比 `policy_frontier_hash`；任一不一致即失效。新增 conformance vector reference `cx.vector.identity_link.policy_tightening_invalidation.v1`。
  - **T23 (`cx.event_batch_receipt` / `cx.audit.ryw_receipt` 概念分层)**：`event-and-patch.md` §5.1 加 normative 段：`cx.event_batch_receipt` 是 receipt object（schema id prefix），不出现在 event-kind-registry，不会作为 `Event.kind` 提交；任何把它当 event kind 提交的实现 MUST `schema_violation`。同段对照说明 `cx.audit.ryw_receipt` 既是 receipt object 也是 active durable event kind（仅在 `cx.profile.attested_audit.e2ee.v1` 下作 durable Event）。`audited-e2ee.md` §4.1 加 normative 段说明 `cx.audit.ryw_receipt` 的 object 与 durable Event 两种形态触发条件。
- **派生 artifact 同步**: `python tools/artifact_pipeline.py generate` 更新 `event-kind-registry.json`、`schema-registry.json`、`id-kind-registry.json`（含新 `ck:trust_domain:`）、`operation-registry.json`、`capability-action-registry.json`；`check` 输出 `Artifact registry lint passed (151 event kinds, 54 schemas, 39 typed ID kinds, 84 operations, 80 profiles)` 与 `registry diff: clean`；`npm run crossref` clean；`cd site && npm run build` 555 pages 0 warning。
- **conformance impact**:
  - 受影响 profile: `cx.profile.e2ee_relaxed.v1` 新增 `absolute_hard_ceiling_ms` / `receiver_enforcement` / `compliance_profile_disabled` 字段；其余 profile 无变化。
  - profile tier 变化: 无。
  - wire 兼容性: **wire-breaking** — (a) `cx.cross_signing.reset` payload 新增 required `trust_domain` + `reset_event_id` 字段；既有 reset payload 缺这两字段时 MUST `schema_violation`。 (b) cursor `h` 字段 minLength 由 16 升到 22；旧实现若发出 16~21 chars 的 handle MUST 失效。(c) `relaxed_window_max_ms > 300000` 的 Realm policy MUST 被 reducer 拒；合规 profile 同时启用 relaxed profile 也 MUST 被拒。(d) Anchor frontier 必须是 `event_digest` 形态；本轮把 fixture 对齐到 schema。
  - reader / writer 行为要求: SDK MUST 更新 (i) cursor handle 生成长度 ≥22 chars；(ii) cross-signing reset payload 写入 / 校验路径加 `trust_domain` / `reset_event_id`；(iii) e2ee_relaxed policy 不允许写超过 300000 ms，receiver 路径独立 enforce 该硬上限；(iv) identity_link 缓存 value 增加 `policy_frontier_hash` 字段并在每次 disclosure policy / history visibility / linked Realm 收紧时 eager 失效；(v) cotest scanner / drift validator 把 `cx.event_batch_receipt` 当 receipt object（不在 event kind allowlist）、`cx.audit.ryw_receipt` 按当前 profile 判定。
- **fixture / vector 变化**: `move-anchor-lattice-fixture.json` frontier 改 event_digest；`encoding-fixture.json` cursor vector 改 `ck:realm:` + 2099 timestamps；新增 `cx.vector.move_anchor_lattice.anchor_canonical_no_self_reference.v1`（6 case）；prose 引用 `cx.vector.e2ee_relaxed.window_exceeds_ceiling.v1`、`cx.vector.identity_link.policy_tightening_invalidation.v1`（待补可执行 fixture）。
- **prose 同步**: 每项都同步修改对应中文 normative prose；`identity-did.md` 新增 §3.6 Trust Domain。
- **迁移指南**:
  - SDK：必填字段 `trust_domain` / `reset_event_id` 必须先填到 reset payload 才能写入；cursor handle 生成至少 22 chars base64url；relaxed_window_max_ms 写入前先按硬上限校验。
  - 部署：deployment 初始化时声明 `ck:trust_domain:<scope>`；server describe / Realm policy 同步暴露。
  - cotest / drift validator：`cx.event_batch_receipt` 排除出 active event-kind allowlist；`cx.audit.ryw_receipt` 按 profile 判定 object vs durable Event；新增的 5 个错误码（`cross_domain_replay_rejected`、`reset_event_id_mismatch`、`relaxed_window_exceeds_ceiling`、`e2ee_relaxed_disallowed_in_compliance_profile`）纳入错误码白名单。

### Round 1 cleanup pass on `_todos.md`（2026-05-20）

承接 `_codex_report.md` / `_claude_report.md` 的 P0–P2 待办，本轮一次性 close 12 项（T05、T18、T19、T20、T21、T22、T24、T25、T26、T27、T28、T30）。全部为 spec-internal 一致性、命名、cross-reference、drift artifact 与构建产物清理，不引入新协议语义。

- **变更类型**: edit + add（drift artifact / schema 字段）
- **影响 artifact**: schemas (`range-completeness-attestation`, `audit-ryw-receipt`, `event-payload`, `event-schema`, `flow`, `identity-link`, `client-sync-response`)、registries (`removed-event-kinds`, `forbidden-wire-fields`, `renames`, `operation-registry`, `contract-catalog`, `id-kind-registry`, `error-code-registry`)、`profiles/conformance-profiles.json`、`fixtures/privacy-security-fixture.json`、`bindings/non-http-bindings.yaml`、`openapi/cokret-service-api.openapi.yaml`、以及 `spec/v1/zh/**` 多个 prose 文件；site 侧 `astro.config.mjs` 与新增 `src/pages/404.astro`。
- **canonical 变更**:
  - **T05 (did:webvh outage)**：`zh/identity/identity-did.md` resolver policy 示例字段 `fallback_to_did_web` 改为 `outage_mode` + `outage_max_duration_ms`；增加 rationale 段落，明确 `fallback_to_did_web` 这种字段名 MUST `schema_violation`，避免与 §3.4 cache-only outage 语义矛盾。
  - **T18 (OR-Set dot event_id 规范化)**：`zh/authz/event-auth-state-resolution.md` OR-Set dot 语义统一使用 `event_id`（dot 形态 `<event_id>:<effect_index>`）；dot / lattice / hash 引用均以 `event_id` + `event_digest` 表达。
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
  - wire 兼容性: **wire-breaking** — `space_frontier` 字段名、`cx.directory.search_spaces` / `cx.directory.resolve_space` operation id、`policy_sources` 字符串简写、非 canonical OR-Set dot 形态在当前 wire 上 MUST 被拒绝。新 drift entries 在 `forbidden-wire-fields.json` / `renames.json` 中标 hard_reject。
  - reader / writer 行为要求: 实现 MUST 更新 client SDK、bindings、test fixtures；不能再发送或接受旧名。OpenAPI 与 gRPC binding 中 operation method 名也变更（`Directory/SearchRealms` / `Directory/ResolveRealm`）。
- **fixture / vector 变化**: `privacy-security-fixture.json` 中 `cx.directory.resolve_space` → `cx.directory.resolve_realm`、test case `hidden_space_resolve_indistinguishable` → `hidden_realm_resolve_indistinguishable`；无新增 fixture。
- **prose 同步**: 上述每项都同步修改对应中文 normative prose。
- **迁移指南**:
  - SDK / yougen / soland / cotest：把 `space_frontier` → `realm_frontier`、`cx.directory.search_spaces|resolve_space` → `cx.directory.search_realms|resolve_realm`、`cx.message.send` 加入 hard_reject 集合；OR-Set dot 由 wire `event_id` 派生。
  - 文档实现者：检索 `space_frontier` / `cx.directory.search_spaces` / `cx.directory.resolve_space` / `cx.message.send` / `fallback_to_did_web` / `Room-scoped DID`，全部替换为对应新名。
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
  - 新增 schema id `cx.schema.member_delivery_binding_candidate.v1`，绑定 `schemas/member-delivery-binding-candidate.schema.json`；MUST 字段 `subject_did` / `handle_uri` / `recipient_service_did` / `delivery_binding_hint` / `issuer_service_did` / `audience` / `expires_at` / `source_refs` / `proofs` / `intent`；`additionalProperties: false`；`handle_uri` 复用 handle-claim canonical 形态约束（`cokret://<domain>/users/<localpart>`，lowercase localpart）；`delivery_binding_hint.binding_source` 排除 `did_document_default`。
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

Handle 是统一概念：协议层只有一种 handle canonical URI（`cokret://<domain>/users/<localpart>`，lowercase localpart）、一套解析与验证规则。`acct:<localpart>@<domain>` 只能作为 `handle_aliases[]` 互通别名。Holder 自托管个人 handle（自有域名）与组织内部账号地址在结构上是同一类——区别只在 issuer（domain owner 自己 vs Organization / Principal Server / Directory），不在 URI 形态。显示形态 `@<localpart>:<domain>` 或 `<localpart>@<domain>`；其它字面形态在 schema 层被拒绝。

- **新增 Event.kind**：
  - `cx.realm.delivery_binding_policy`（state event；`cell_family=cx.component.realm.delivery_binding_policy.v1`, `cas-register`, `bottom=reject`, `cell_subject=null`）。
  - `cx.device.push_route`（actor-private event；`cell_family=cx.component.device.push_route.v1`, `cas-register`, composite `cell_subject=(recipient_service_did, principal_id, device_id, push_route)`, `bottom=reject`）。
- **Schema**：
  - `event-payload.schema.json#/$defs/member_delivery_binding`：严格 schema。`recipient_service_type=const "principal_server"`、`binding_scope=const "realm"`；`delivery_modes` / `resolved_at` 必填；按 `binding_source` 的 conditional required（`did_document_default` → `did_document_hash`；`explicit` / `invite` / `organization_policy` → `service_acceptance_ref`；`join_policy` / `space_policy` / `organization_policy` → `policy_ref`）。
  - `event-payload.schema.json#/$defs/membership_payload`：`membership=join` 时 `actor_id` / `delivery_status` 必填；`delivery_status=routable` 时 `delivery_binding` 必填。
  - `event-schema.json`：`cx.realm.delivery_binding_policy` 进入 wire-level `kind` enum 与 state_payload 分支。
  - `handle-claim.schema.json`：`handle_uri` 仅允许 `cokret://<host>(:<port>)?/users/<lowercase-localpart>`；`acct:<localpart>@<host>(:<port>)?` 移入 `handle_aliases[]`，不得作为 canonical；裸 `cokret://<host>`、`user:domain`、bare host 一律拒绝。`binding_state=verified` 必填 `handle_uri` / `expires_at`；出现 `recipient_service_did` 或 `delivery_binding_hint` 时必填 `handle_uri` / `audience` / `expires_at`，且 `delivery_binding_hint.binding_source` 不允许 `did_document_default`。
- **Prose normative**：
  - `identity/identity-handles.md`：Handle 单一模型，§3.1 显示形态与 canonical URI、§3.2 解析结果必含字段、§3.3 `delivery_binding_hint` 约束、§3.4 Issuer 类型（holder self-issued / Organization / Principal Server / Directory）与 holder 自托管路径、§3.5 公开 vs 受限、§3.6 与 pairwise DID 正交；§5 解析 issuer 优先级；§6 双向验证按公开 / 受限分流；§6.1.2 撤销路径（TTL + Directory withdrawal + DID Document 变化）；§6.1.3 重分配与历史归因。
  - `governance/join-policy.md` §5.1：接受准则、`binding_source` 与责任方表、`cx.realm.delivery_binding_policy` 字段、路由不可降级、rebind handover via causal frontier、单 binding 约束、unlinkability 边界；§5.1.2.1 Handle 作为 member_add 输入的 6 步构造法（含 `audience` 校验）。
  - `sync/federation.md` §4.1：接收方服务绑定规则切分 member-level vs Realm-level 两条互不重叠路径；fail-closed 解析算法；handover stale 协议；`service_binding_ref.delivery_binding_frontier` 必填；`delivery_binding_diagnostics` 仅作诊断。§6.2 Actor Event Source 发现用途表。
  - `identity/identity-did.md` §3.2：DID Document `CokretPrincipalServer` service entry 是默认服务发现入口，不作为 Realm-scoped delivery 路径；Handle 属 Handle 层，不属 DID method。
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
  - Handle 字符串仅是 builder 输入；canonical URI 比对、`alsoKnownAs` 一致性校验、Directory 缓存键一律 MUST 使用 `cokret://` 形态，`acct:` 仅为互通别名。
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

把 `operation_registry.capability_tiers` 从三档（core / extension / deployment_local）扩到四档,新增 `interop_bridge` tier 用来标记"对外部协议（MIMI、Applet 等）的 adapter surface",并修复几处 surface 错位分组。动机:此前 `mimi_interop`、`applet` 与 `directory_discovery`、`blob_media` 等同被打上 `extension`,把"协议内可选 surface"与"对外部协议的桥接"压成同一类,导致 30% 操作看着像 extension —— 实际上前者属于 Cokret 规范本体的可选项,后者是独立外部规范的 adapter,生命周期/治理/profile 语义都不一样。本次只动 metadata,无 wire 变化、无 op 增删。

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
  `cokret-service-api.openapi.yaml`、`non-http-bindings.yaml`、
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

把 Flow 的能力面字段从 `branch` 改名为 `track`。原命名暗含 git 风格的"版本派生"心智模型，与 Cokret
中 Flow 多面共同推进的语义不符；`track`（多轨录音 / PM workstream tracks）更准确地表达"同一议题
沿多条并行轨道演进"的设计意图。Synthesis 与 discussion 仍是 v1 标准 track name，profile 仍可声明
更多 track name；只是承载它们的字段、event kind、schema $defs、constraint key 全部统一改名。

- **变更类型**: modify（重命名 — wire breaking）
- **影响 artifact**: `event_kind_registry`、`capability_action_registry`、`schema_registry`、
  `error_code_registry`、`flow.schema.json`、`message.schema.json`、`event-schema.json`、
  `event-payload.schema.json`、`grant-constraint.schema.json`、`notification.schema.json`、
  `read-receipt.schema.json`、`read-marker.schema.json`、`cokret-service-api.openapi.yaml`、
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
- `ck:operation:` typed-id：从 `id_kind_registry` 删除（37 → 36）；`cx.schema.operation.v1` 从 schema_registry
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

- **actor_profile object & `cx.profile.create`**：新增 `ck:actor_profile:` typed-id 和 `cx.profile.create`
  / `cx.profile.update` / `cx.profile.space_override` 三个 event kind；event_kind_registry 由 109 回到
  110 active kinds（id_kind_registry 仍保持 36，因为这次未删除其他 typed id，而 actor_profile 以独立
  kind 进入）。create payload 不再共享 `object_create_payload`：`cx.realm.create` / `cx.flow.create`
  / `cx.morph.create` 各自指向完整对象 schema，wire 校验直接走对象 schema。
- **state_key 形态**：`cx.realm.policy.set` 的 `state_key=inheritance` 由常量改为
  `inheritance:ck:realm:<ulid>` 模式（每个父 realm 一条），并把 `plaintext_visible_services` 显式纳入
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

- `cx.flow.convert`、`cx.schema.operation.v1` / `ck:operation:`、`constraint.priority` 最初以
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
