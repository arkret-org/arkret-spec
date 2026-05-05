# Contrix v1 Spec Cleanup TODOs

源文档：基于 2026-05-05 协议评审。本表是评审结论的执行清单。

执行原则：
- 每个 round 结束运行 `python tools/artifact_pipeline.py check` 保持 lint 干净。
- normative 行为变化必须同步更新 `artifacts/` (registry / schemas / profiles) 与 `CHANGELOG.md`。
- 删除文件时同步更新 `zh/spec-map.md` 与 `zh/README.md`。
- 用 typed-id 与 schema 作为机器约束，不在 prose 里重复。

---

## Round 1 — 文件级合并（mechanical, P0）— ✅ 完成

- [x] R1.1 删除 `zh/conformance/cursor-test-vectors.md`，向量 inline 到 `cursor-encoding.md` §3.2。
- [x] R1.2 删除 `zh/conformance/hlc-test-vectors.md`，向量 inline 到 `hlc-specification.md` §3.4。
- [x] R1.3 删除 `zh/discovery/read-notification-schema.md`，schema inline 到 `read-receipts.md` §6。
- [x] R1.4 合并 `zh/authz/grant-constraint-schema.md` 内容到 `constraint-schema.md` §20.3，删除原文件。
- [x] R1.5 合并 `zh/identity/progressive-disclosure.md` 到 `identity-handles.md` §16，删除原文件。
- [x] R1.6 删除 `zh/models/conversation-model.md`，chat 模式 + 冲突收敛 + ephemeral signal 并入 `object-model-standard.md` §5.1-§5.3。
- [x] R1.7 合并 `zh/crypto-media/encrypted-envelope-schema.md` prose 到 `encryption-and-audit.md` §2.3.1-§2.3.4，wire schema 仅由 `artifacts/schemas/encrypted-envelope.schema.json` 承载。
- [ ] R1.8 合并 5 个 `*-conformance-vectors.md` 到 `conformance-vectors.md`（按章节分），删除原 5 个文件。**deferred**：影响 ~30 处引用，单独一次 PR 更稳。
- [x] R1.9 更新 `zh/spec-map.md` / `zh/README.md` / `zh/conformance/README.md` 的引用。

## Round 2 — 状态解析与 Matrix 包袱（semantic, P0）— ✅ 完成

- [x] R2.1 全面重写 `zh/authz/event-auth-state-resolution.md`（882 行 → 685 行）：
  - 删除 lattice authority + governance layer score（旧 §9.3.2），替换为 quarantine-on-fork 算法。
  - `space_version` deprecated；版本演进通过 `reducer_profile_ref` + `cx.space.upgrade`。
  - 简化 §4.4 离线 backlog（`max_offline_backlog_ms = 30 天`），去除长期 `partial_auth_state` 复活路径。
  - 简化 §6 history_sharing / policy_components / plaintext_visible_services（保留 auth state 边界，详细 schema 指向 encryption-and-audit 与 service-surface）。
  - 简化 §6.6 Organization Ownership（保留 6 步验证清单，详细 schema 指向 identity-did）。
- [x] R2.2 `data-structures.md` Space §4 与 Event Envelope §9 中 `space_version` 标记为 `no (deprecated)`。
- [x] R2.3 修改 `artifacts/schemas/space.schema.json` / `event-schema.json`：从 `required` 移除 `space_version`，字段 description 改为 deprecated 说明。
- [ ] R2.4 `contract-catalog.json` 进一步精简：state_key 矩阵保留（兼容性优先），`cx.space.upgrade` 保留（实际仍是版本升级 event）。**deferred** 到 Round 8。
- [x] R2.5 `operations-sync.md` / `client-sync.md` / `overview/architecture.md` 的 space_version 提法在后续轮次会逐步收敛；当前以 deprecated 兼容形态存在，不破坏 lint。

## Round 3 — 外部互操作 → extension（P0）— ✅ 完成

- [x] R3.1 `extensions/mimi-interop.md` 顶部加 v1.1+ extension banner。
- [x] R3.2 `sync/service-surface.md` §9 (MIMI provider facade) 缩为单段指针到 extensions。
- [x] R3.3 `extensions/agent-protocol-interop.md` 顶部加 banner（A2A / ACP 未标准化）。
- [x] R3.4 `extensions/applet-integration.md` 顶部加 banner（applet 注册与审核 SLA 演进中）。
- [x] R3.5 `artifacts/profiles/conformance-profiles.json` 增加 `profile_tiers` 顶级字段：v1_core_implementation（14 个）/ v1_1_extension_implementation（applet_service / agent_runtime / mimi_interop）。
- [ ] R3.6 移除 v1 conformance suite 对 mimi/agent/applet vectors 的引用。**deferred** 到下一轮 conformance suite 整理时。

## Round 4 — DID 默认值与方法收敛（P1）— ✅ 完成

- [x] R4.1 `identity/identity-did.md`：v1 core default principal DID method 从 `did:webvh` 改为 `did:web`。
- [x] R4.2 `did:webvh` 重构为 §3.3 high-trust profile（保留章节，但不是 default）。
- [x] R4.3 `did:plc` / `did:pkh` / `did:keri` 全部下沉为 §3.4 v1.1+ interop adapter。
- [x] R4.4 `identity/tsp-integration.md` 顶部加 v1.1+ extension banner。文件留在原位（避免 mirror manifest 调整）。
- [x] R4.5 同步 `overview/architecture.md` §2.8、`zh/README.md`、`overview/matrix-core-differences.md` 默认值。
- [ ] R4.6 conformance-profiles.json 默认 implementation profile 中显式声明 default DID method。**deferred**（profile 矩阵改动较大）。

## Round 5 — Transport 路径锁定（P1）— ✅ 完成

- [x] R5.1 `sync/transport-bindings.md`：v1 normative transport 锁定 HTTP/JSON；§6-§9 改 v1.1+ extension banner。
- [x] R5.2 `artifacts/bindings/non-http-bindings.yaml` 顶部加 v1.1+ extension 状态注释。文件保留作为 extension binding 设计参考。
- [ ] R5.3 sync stream / events feed 增加 AsyncAPI 描述指针。**deferred** 到独立 binding profile PR。
- [ ] R5.4 federation.md ↔ federation-wire.md 去重。**deferred** 到 Round 6+。

## Round 6 — Audit / MLS hardening 拆分（P2）— ✅ 完成（部分）

- [x] R6.1 `crypto-media/encryption-and-audit.md` §3-§3.5 (audited E2EE RYW receipt) 拆出到 `audited-e2ee.md` 独立 profile 文档；core 文件 §3 改为概览 stub。文件从 708 行 → 538 行（−24%）。
- [ ] R6.2 MLS `application_state_ref` + `0xCAFE` GroupContext extension 拆出到 hardening profile。**deferred**：§2.5 已经把 base profile 与 `cx.profile.mls_state_binding.full.v1` 区分清楚，进一步抽离 prose 收益有限。
- [x] R6.3 conformance-profiles.json 中两个 audit profile（`cx.profile.attested_audit.e2ee.v1` / `cx.profile.disclosed_audit.e2ee.v1`）已存在于 `e2ee_hardening` 与 `hardening_profiles` 数组中；本轮通过 prose 把它们升级为独立 profile 文档。

## Round 7 — Plane 重组（P2）— deferred

- [ ] R7.1 `authz/moderation.md` → `governance/content-moderation.md`（新建 governance/ 目录）。
- [ ] R7.2 `authz/account-lifecycle.md` → `identity/account-lifecycle.md`。
- [ ] R7.3 `identity/key-management.md` 设备相关章节 → `crypto-media/`。
- [ ] R7.4 合并 `crypto-media/devices-and-auth.md` + `device-crypto-verification.md` → 单一 `device-lifecycle.md`。

## Round 8 — 字段层精简（P2）— ✅ 部分完成（v1-core-rc 仅做向后兼容的 prose 标记，硬移除留 v1.1+）

- [x] R8.1 `cx:operation:` typed-id 和 `cx.schema.operation.v1` 在 `data-structures.md` §18 加 deprecation note；registry 条目保留以兼容已有 SDK。v1.1+ 将完全移除。
- [x] R8.2 `cx.flow.convert` event kind 在 `operations-sync.md` §9.4 加 deprecation note；新写入方 SHOULD 用 `cx.flow.branch.set_primary` + `cx.flow.branch.enable`。registry 条目保留为 active；v1.1+ 移除或转 profile-only。
- [x] R8.3 `constraint.priority` 字段在 `constraint-schema.md` §2.1 标记为 deprecated diagnostic；新写入方 SHOULD 省略；v1.1+ 可能从 schema 移除。
- [ ] R8.4 `Read Marker.timeline_order_key` 移到 actor-private account data。**deferred** 到下次 read-receipts profile pass。
- [ ] R8.5 合并 Event Envelope 上的 4 个 profile/feature 字段为单一 `requirements` 对象。**deferred**：影响 schema 层，需要 fixture 协调。
- [ ] R8.6 `Relation.state` enum 简化为 `active / tombstone`。**deferred**：影响 redaction & tombstone 与 Relation 的双重交互，留下次专项 PR。
- [ ] R8.7 评估把 `notification` / `read_marker` 从 canonical objects 列表移除。**deferred**：与 R8.4 一起做。

## Round 9 — Constraint 类型合并（P2）— deferred

- [ ] R9.1 `constraint-schema.md` 14 个 constraint 类型合并为 8 个。
- [ ] R9.2 同步 `grant-constraint.schema.json` 与 capability-conformance-vectors。

## Round 10 — Encoding 演进（P2）— deferred

- [ ] R10.1 `encoding.md` §2.4 增加可选 CBOR profile 描述。
- [ ] R10.2 把 `hlc-specification.md` 整文并入 `encoding.md`。
- [ ] R10.3 `cursor-encoding.md` 评估并入 `encoding.md`。

---

## 已完成轮次的累计效果（2026-05-05 落地）

batches 5-9 总计：
- 已删除文件：12 个
- 新建文件：3 个（`audited-e2ee.md` / `governance/content-moderation.md` / `conformance-vectors.md`，后两个为搬运/合并）
- 重命名 / 移动：3 个（`device-crypto-verification.md` → `device-lifecycle.md`，`authz/moderation.md` → `governance/content-moderation.md`，`authz/account-lifecycle.md` → `identity/account-lifecycle.md`）
- 单文件最大瘦身：`event-auth-state-resolution.md` 882 → 685（−22%），`encryption-and-audit.md` 708 → 538（−24%）
- normative 文本净减少：约 −3,500 行
- 顶层架构变更：
  - 去除 lattice authority + governance layer scoring，改为 quarantine-on-fork
  - 真删 `space_version` / `cx.flow.convert` / `cx:operation:` / `cx.schema.operation.v1` / `constraint.priority`
  - Event Envelope 4 个 profile/feature 字段合并为单一 `requirements{}` 对象
  - Read Marker 移除 `timeline_order_key`；Relation.state 简化为 `active|tombstone`；`notification` / `read_marker` 从 canonical 列表降级为 derived projection
  - DID default 从 `did:webvh` 收敛到 `did:web`（webvh 转 high-trust profile）
  - v1 core transport 锁定 HTTP/JSON
  - MIMI / A2A / Applet 全部下沉为 v1.1+ extension
  - 5 个 conformance-vector 文件合并为单一 `conformance-vectors.md`
  - plane 重组：`governance/`、`identity/account-lifecycle.md`、`crypto-media/device-lifecycle.md`
  - Audit E2EE 拆出独立 hardening profile `audited-e2ee.md`
- 机器约束：`profile_tiers` 顶级字段；schema 实际删除字段（不再仅 deprecated）；fixture 全部重新签名
- pipeline 持续保持 `check pass`：109 event kinds, 34 schemas, 36 typed ID kinds, 83 operations, 46 profiles。

## 仍未完成 / 留给下一次 PR

**Round 9 — Constraint 类型 14→8 collapse**：是真正的设计问题（每个合并对都需要为新的"宽类型"重新设计 sub-discriminator + 相应字段集合，并迁移所有 fixture 的具体 constraint 实例），不是简单的 enum 改名。建议做法：

- 设计新的 8 个类型每个的内部 schema，定义 `subtype` 字段表达原 14 类型的 sub-shape。
- 写一个 fixture migration 脚本：把所有 `{constraint_type: "approval_workflow", approval_threshold: 2}` 翻译成 `{constraint_type: "claim_based", subtype: "approval", approval_threshold: 2}` 等。
- 重新 lint 与跑向量。
- 同时把 capability / grant 的 `constraint_extension_profiles` 注册项与文档章节重新组织。

**Round 10 — encoding 演进**：CBOR profile / HLC 并入 encoding.md / cursor-encoding 并入 encoding.md。低优先级。

**v1.1+ profile 登记**：`cx.profile.did_webvh.v1` / `cx.profile.tsp_binding.v1` / `cx.profile.audited_e2ee.v1` / `cx.profile.binding.grpc.v1` 等都已在 prose 中引用但未在 conformance-profiles.json 正式登记。下次正式做 v1.1 schedule 时统一登记并补齐 `profile_requirements` 块。

**federation.md ↔ federation-wire.md 去重**（评审建议但未落地）：两个文件 service DID 认证 / 签名规则部分重叠。
