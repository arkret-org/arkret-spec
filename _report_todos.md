# Report-Derived Protocol TODOs

日期: 2026-05-23

来源说明: 根目录未找到独立 `_claude_report.md`；当前 `_codex_report.md` 已包含第一轮评审与“第二轮深度评审追加”，本清单按这两部分内容合并筛选。筛选原则是：证据能在当前仓库中复核、可用小修闭环、尽量不改变既有核心概念。需要新增大块 schema/registry 体系或当前证据不足的条目先放入“后续评估”。

## 本轮采纳并修复

- [x] 修正 `cx.vector.encoding.event_digest.v1` 与 `encoding-fixture.json` 中 `cx.message.create` digest 向量缺少 `track`、`preconditions`、`effects`、`anchor_ref` 的问题，并更新 expected canonical bytes / digest。
- [x] 修正 `crypto-signature-fixture.json` 中签名正向 Event 缺少 reducer-input Move 字段和 `track` 的问题，并重新生成 `payload_hash`、binding hash、detached payload、JWS signing input 与签名。
- [x] 在 `event-and-patch.md`、`encoding.md` 与 `event-schema.json` 中统一 detached JWS transcript：`payload_hash` 绑定完整 canonical Event，JWS 签 canonical proof binding object。
- [x] 修正 `service-http-binding.md` 的单 Event 示例，补齐 reducer-input Event 必需的 `preconditions`、`effects`、`anchor_ref`。
- [x] 收紧 `events[]` 同批提交语义：同批前序 Event 可用于解析，但新 grant / authority 不得在同一 Anchor pre-state 内立即授权后续 Event。
- [x] 将 `/api/v1/push/notify` 默认请求形状改为 blind wakeup，并把 visible notification 字段限定到 profile / Realm policy / device opt-in / UI disclosure 同时满足的路径。
- [x] 在 discovery push 文档中补充 Sync / notification service 转发前必须执行 push metadata 白名单校验，超出字段 strip + audit 或拒绝。
- [x] 为站点增加 `/artifacts/schemas/*.json` raw JSON Schema endpoint，并在 Artifact Consumption Guide 与 Release Readiness 中要求 `$id` URL 返回 raw JSON。
- [x] 修正 blob presign 文案：`cx.blob.head` 是允许的只读路径，不应出现在写/副作用禁止项中。
- [x] 修正 Morph 文档中的幻象 event kind `cx.morph.transition`，改为已注册的 `cx.morph.schema_migrate`。
- [x] 修正 Realm lifecycle 错误域措辞，避免与 `cx.realm.lifecycle.*` capability 命名混用。
- [x] 对 revocation freshness 增加 `freshness_required_ms > 2 * clock_skew_tolerance_ms` 约束，并把高风险默认窗口调为 120s。
- [x] 为 Space parent / `default_realm_ref` 递归解析补充 acyclic 检测和 fail-closed 规则。
- [x] 为 snapshot manifest 补充 `snapshot_issuer_did` / `witness_attestations[]` 信任锚要求，并在 HTTP binding 与 service surface 中对齐。
- [x] 为 Applet registration / transaction 明确 Realm owner/admin/policy 授权 grant 要求，缺失时 `applet_registration_unauthorized`。
- [x] 为 MIMI facade 补充缺失 Contrix governance binding 时 fail-closed quarantine，reason=`mimi_governance_binding_missing`。
- [x] 将 Agent 写入 Event 的 `agent_context` 从建议提升为 MUST，避免 agent-signed write 伪装成人类直接写入。
- [x] 在服务端威胁模型中补充 federation traffic-pattern observer 与 OHTTP / padding / decoy traffic 等缓解建议。

## 已核对但本轮不直接改动

- [x] `policy-server.md` 的 decision cache 已经按 `(realm_id, actor, action, request_canonical_hash, auth_state_hash)` 或等价 `auth_state_hash` 命中校验绑定；报告中的缓存三元组问题在当前文本中已覆盖。
- [x] Capability delegation cycle detection 已经明确禁止 ancestor cycle，并按 parent chain DFS fail closed；报告中的自环 delegation 建议在当前文本中已覆盖。
- [x] `encryption-and-audit.md` 当前已包含 governance binding 的 `realm_id`、固定 `0xF1C0` GroupContext extension、`previous_epoch` / `next_epoch`、KeyPackage claim envelope 和 `covered_frontier_cell` gate；本轮只保留后续 schema/vector 深化项，不重复改动概念层。

## 本轮验证

- [x] `python tools\artifact_pipeline.py check`
- [x] `npm run crossref`
- [x] `npm run check`
- [x] `npm run build`
- [x] `crypto-signature-fixture.json` schema / canonical hash / Ed25519 signature 校验。
- [x] `encoding-fixture.json` canonical JSON / digest 校验。
- [x] `site/dist/artifacts/schemas/event-schema.json` 已生成 raw JSON 文件，覆盖 `$id` URL 对应路径。

## 后续评估 / 未在本轮闭环

- [ ] 为所有 Markdown wire JSON 示例建立自动抽取 + JSON Schema local resolver 校验。当前仅修复了报告点名的高风险示例/fixture；完整 CI 需要新增示例标注约定和负向 fixture `first_expected_error` 元数据。
- [ ] 为 `cx.account.*` Account Data 标准类型建立机器 registry，或引入 `cx.schema.account_data_type.v1`。这需要设计新的 registry 形态，且当前 registry 文件已有未归属脏改动，本轮不混入。
- [ ] 建立 `vector-registry.json` 机器索引，机械列举 `cx.vector.*`。这属于 conformance runner 结构增强，本轮未展开。
- [ ] 评估 `state_root` leaf 是否确实需要加入 `batch_index`。当前 state_root 定义是状态快照 root，不直接承诺历史顺序；报告建议可能会改变 root 兼容性，需要独立设计和向量迁移。
- [ ] 对 MLS / device lifecycle 的更深 schema 级建议（例如新增 `expected_previous_epoch` 字段、device revoke Anchor frontier schema、Welcome `keypackage_canonical_hash` 双绑）做独立 schema/vector 迁移评审；当前 prose 已覆盖主要安全意图，但机器 schema 是否完全表达仍需单独工作。
