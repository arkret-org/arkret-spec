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

把按 selector / cursor 取事件序列的三个旧 operation 收敛为按 delivery 形态拆分的两个新 operation，并把 client_sync 改名为 account 同步以澄清它"账号视角聚合"的真实定位。重构思路：selector（actor / space）、range（forward / backward / window）和 delivery（unary / stream）三个维度被旧 surface 切错了——`cx.events.list`（actor or space, 单向, unary）、`cx.sync.backfill`（space, 双向, unary）、`cx.sync.subscribe`（space, 实时, stream）的差别本质是 selector 和 cursor 方向，不是不同操作；只有 streaming 与 unary 才是真正的 delivery 差别。

- **变更类型**: modify（重命名 + 合并 — wire breaking）
- **影响 artifact**: `operation_registry`、`capability_action_registry`、
  `contrix-service-api.openapi.yaml`、`non-http-bindings.yaml`、
  `conformance-profiles.json`
- **canonical 变更**（`contract-catalog.json`）:
  - **新增** `cx.events.query`（HTTP `GET /events`、gRPC `Events/Query`、mq
    `events.query`）。selector 是 `spaces[]` ∪ `actors[]` ∩ 组合；range 是
    `from?` + `until?` + `direction: forward|backward`；返回 `events[]` +
    `next_cursor?` + `prev_cursor?`。合并旧 `cx.events.list` 与
    `cx.sync.backfill` 的双向语义。
  - **新增** `cx.events.subscribe`（HTTP `GET /events/subscribe`、gRPC
    `Events/Subscribe`、mq `events.subscribe`）。多 space / actor 一次订阅；
    `include_history: bool=true` 时先吐历史再以 `catchup_complete` 帧切到实时。
    新增 `dropped` / `epoch_rotation` / `unauthorized` / `resync_required` /
    `frontier` / `heartbeat` / `catchup_complete` 帧类型。
  - **新增** `cx.sync.account`（HTTP `POST /sync`、gRPC `Sync/Account`、mq
    `sync.account`）。语义不变，是旧 `cx.sync.client_sync` 的改名——这个 op
    的真实定位是 to_device / account_data / device_lists / presence / 跨
    Space delta 的 **账号视角聚合**，不是裸事件读。
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
    - 客户端 MUST 把 Space 流订阅切到 `GET /events/subscribe`，不再用
      `/sync/subscribe`；并按 `catchup_complete` / `dropped` /
      `resync_required` 帧调整恢复逻辑
    - 客户端 MUST 把 account 同步的 operation_id 改为 `cx.sync.account`；
      路径 `POST /sync` 不变
    - 服务实现 MUST 在 `events.query` 上对每个 selector 元素逐项做
      visibility 判定（actor scope 用 actor history visibility；space
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
  - query 参数：`actor_id` / `space_id` 改成 `actors[]` / `spaces[]`；
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

### 协议评审驱动的简化（2026-05-05，第四批：constraint 14→8 collapse + encoding 合并 + federation dedup）

#### Round 9 — Constraint 类型 14 → 8 family + subtype discriminator

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

#### Round 10 — Encoding 文档收敛

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
  exchange shape `{space_id, heads[], max_hlc, witness_receipts[]}` 与 duplicate_conflict 处理规则）。
- 4 处跨文件引用 (`security/server-threat-model`, `spec-map`, `service-http-binding`, `federation`
  本身) 重定向到 federation.md。spec-map 中重复行去重。

### 协议评审驱动的简化（2026-05-05，第三批：真删 + Event Envelope requirements 合并 + plane 重组 + conformance-vectors 合一）

#### 真删之前仅标 deprecated 的字段 / 注册表项

- `space_version`：从 `event-schema.json` / `space.schema.json` 完全删除（不仅是 required 列表）；
  `crypto-signature-fixture` 重新生成 canonical bytes / payload_hash / binding_hash / signed JWS（用
  test private key 重新签名并验证通过）；`event-envelope-negative-fixture` 11 个 event 全部清理；
  `encoding-conformance-vectors` 中的 canonical bytes vector + digest 重算。规范文本中的版本演进
  提法统一改写为 Event `requirements` 与 profile id / `cx.space.upgrade` 语义。
- `cx.flow.convert`：从 `contract-catalog.json` event_kind_registry 删除（本批 110 → 109 active kinds，
  之后 actor_profile 评审新增 `cx.profile.create` 把总数加回 110，参见下方 "actor_profile + gatekeeper
  收尾" 一节）；`event-schema.json` 移除对应 if/then 分支与 `flow_convert_payload` $def；prose 全部改为
  `cx.flow.track.set_primary` + `cx.flow.track.enable` 组合。
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

#### Round 7 plane 重组

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

#### Round 6 (audited E2EE) — 已在 batch 6 完成，本批不重做

#### R1.8 conformance-vectors 合并

- 5 个 `*-conformance-vectors.md`（encoding / state-resolution / redaction / capability / sync）合并为
  单一 `conformance-vectors.md`，按 §1-§5 分组。约 1,300 行整合。
- 所有跨文件引用全部更新（11 处 .md / .json）。
- 删除原 5 个文件。

#### actor_profile + gatekeeper 收尾（2026-05-06，v1.0.0 release 锁定前的最后批次）

- **actor_profile object & `cx.profile.create`**：新增 `cx:actor_profile:` typed-id 和 `cx.profile.create`
  / `cx.profile.update` / `cx.profile.space_override` 三个 event kind；event_kind_registry 由 109 回到
  110 active kinds（id_kind_registry 由 36 → 36 仍保持，因为同批未删除其他 typed id 但 actor_profile
  以独立 kind 进入）。create payload 不再共享 `object_create_payload`：`cx.space.create` /
  `cx.flow.create` / `cx.morph.create` 各自指向完整对象 schema，wire 校验直接走对象 schema。
- **state_key 形态**：`cx.space.policy.set` 的 `state_key=inheritance` 由常量改为
  `inheritance:cx:space:<ulid>` 模式（每个父 space 一条），并把 `plaintext_visible_services` 显式纳入
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

### 协议评审驱动的简化（2026-05-05，第二批：Round 6 + Round 8 子集）

#### Round 6 — Audited E2EE 拆出独立 hardening profile

- 新建 [`zh/crypto-media/audited-e2ee.md`](zh/crypto-media/audited-e2ee.md)：承载
  `cx.profile.attested_audit.e2ee.v1` 与 `cx.profile.disclosed_audit.e2ee.v1` 两类
  audited E2EE profile 的完整 normative：audit policy declaration、join warning canonical
  文案、audit agent entry、强制留痕 (`cx.audit.accessed`)、RYW receipt schema、transparency
  surface、forbidden marketing terms。
- `zh/crypto-media/encryption-and-audit.md` §3 缩为概览 stub 指向 audited-e2ee.md；文件从
  708 行 → 538 行（−24%）。Core E2EE / MLS 内容（§2 / §4-§7）完全保留，与 audit profile
  正交。
- `zh/spec-map.md` 增加 audited-e2ee.md 入口。

#### Round 8（历史中间态，已由第三批完成真删）

- `cx.flow.convert`、`cx.schema.operation.v1` / `cx:operation:`、`constraint.priority` 最初以
  deprecation-only 方式标记；第三批已经完成 wire contract 真删。
- 正式 v1.0.0 以当前 `artifacts/registry/contract-catalog.json`、schema 与对应中文规范为准，不再把
  这些字段或注册表项声明为 active 兼容项。

### 协议评审驱动的简化（2026-05-05）

基于全仓评审，本轮收敛掉了一批与 Matrix room state 风格继承的复杂性预算与对仍在演进外部
标准的 normative 绑定；已完成事项以本文和机器工件为准。

#### Round 1 — 文件级合并（删除冗余文件）

- 删除 `zh/conformance/cursor-test-vectors.md`，向量入口并入 `cursor-encoding.md` §3.2。
- 删除 `zh/conformance/hlc-test-vectors.md`，向量入口并入 `hlc-specification.md` §3.4。
- 删除 `zh/discovery/read-notification-schema.md`，schema 与 query 形状并入 `read-receipts.md` §6。
- 删除 `zh/authz/grant-constraint-schema.md`，grant context 示例并入 `constraint-schema.md` §20.3。
- 删除 `zh/identity/progressive-disclosure.md`，渐进披露语义并入 `identity-handles.md` §16。
- 删除 `zh/models/conversation-model.md`，chat 模式示例与冲突规则并入 `object-model-standard.md` §5.1-§5.3。
- 删除 `zh/crypto-media/encrypted-envelope-schema.md`，envelope wire 形态、AAD 序列化、
  payload_digest 计算与解密错误码并入 `encryption-and-audit.md` §2.3.1-§2.3.4；schema 仍由
  `artifacts/schemas/encrypted-envelope.schema.json` 承载。

#### Round 2 — 状态解析与 Matrix 包袱去除（核心语义变更）

- **重写 `zh/authz/event-auth-state-resolution.md`**（882 行 → 685 行，约 −22%）：
  - **Lattice authority 替换为 quarantine-on-fork**：去除 §9.3.2 的 `governance_layer × authority_kind`
    二维 lattice 与派生 `auth_weight` 表。并发 fork 同 `(kind, state_key)` 由 reducer
    quarantine 全部非 winner 候选并要求 admin 显式介入，winner 不再由权重表自动选边。
  - **`space_version` 标记为 deprecated wire 字段**：版本演进通过 `reducer_profile_ref` /
    `schema_profile_refs` / `cx.space.upgrade` 表达。读取方 MUST 容忍兼容字段；新写入方
    SHOULD 省略。
  - 简化 §4.1 partial_auth_state：v1 默认 `max_offline_backlog_ms = 30 天`；离线超过窗口
    后必须重新拉 frontier 才能写入，去除 `soft_failed` / `partial_auth_state` 长期复活
    路径作为 normative 要求。
  - 简化 §6 history_sharing / policy_components / plaintext_visible_services：保留 auth state
    边界条款，完整 schema 与撤销语义指向 `crypto-media/encryption-and-audit.md` 与
    `sync/service-surface.md`。
  - 简化 §6.6 Organization Ownership：保留 6 步验证清单，详细 schema 指向 `identity/identity-did.md`。
- 同步更新 `artifacts/schemas/event-schema.json` 与 `space.schema.json`：把 `space_version` 从
  `required` 数组移除，字段 description 改为 deprecated 说明。
- 同步更新 `zh/models/data-structures.md`：Space §4 与 Event Envelope §9 的 `space_version`
  改为 `no (deprecated)` 必填性。

#### Round 3 — 外部互操作下沉为 interop extension profile

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

#### Round 4 — DID method 默认值收敛

- v1 core 默认 principal DID method 从 `did:webvh` 改为 **`did:web`**。理由：`did:web`
  生态成熟、HTTPS + 域名部署门槛低；`did:webvh` 仍在 W3C CCG 演进中。需要可审计身份历史的部署
  SHOULD 升级为 `did:webvh`（high-trust profile）。
- `did:plc`（AT Protocol interop）、`did:pkh`（钱包绑定）、KERI 系列、TSP transport 全部下沉为
  **interop extension profile**；v1 core 实现不要求支持。
- 同步更新：`zh/identity/identity-did.md` §3-§3.4、`zh/identity/tsp-integration.md` 顶部 banner、
  `zh/README.md`、`zh/overview/architecture.md` §2.8、`zh/overview/matrix-core-differences.md`。

#### Round 5 — Transport 路径锁定

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
  [`zh/overview/release-readiness.md`](./zh/overview/release-readiness.md).
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
  Space policy 通过 `audit_disclosure` 对象 + `audit_assurance` enum 声明；UI
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
