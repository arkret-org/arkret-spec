# Contrix v1 Spec 改进报告

生成日期：2026-05-31
评审范围：`spec/v1/zh/` normative 文本、`spec/v1/artifacts/` 下的 JSON Schema / registry / OpenAPI，以及 proposal 状态文件。
基础校验结果：初始 `python tools/artifact_pipeline.py check`、`python tools/lint_artifacts.py`、`python tools/lint_spec.py` 均通过；本轮已补充部分缺失 lint，并在修复后再次通过同一组自检。

## 处理状态

- [x] 1. OpenAPI ErrorEnvelope enum 已改为按 error registry endpoint/both scope 同步，并加 lint 防漂移。
- [x] 2. `policy_denied` / `cursor_unrecognized` 已提升为顶层错误码，并同步 OpenAPI。
- [x] 3. DID-as-id 与 DID URL 边界已收紧；签名 `verification_method` 改为要求 key fragment，并加 lint。
- [x] 4. OpenAPI 关键认证路径 `device_id` 已按 `cx:device:<uuid7>` 约束，并加 lint。
- [x] 5. wire schema 裸 `scope` 已改名，并加 lint 禁止 schema property 回归。
- [x] 6. 标准 reducer-input payload 顶层未知字段已关闭；`generic_standard_payload` 作为显式开放扩展/桥接容器保留，并加 lint。
- [x] 7. 泛型 `OperationRequest` / `OperationResult` 已纳入 operation registry 的 `generic_binding` 机器化治理；core tier 禁止泛型绑定，剩余 extension / interop / deployment-local 泛型面带迁移计划。
- [x] 8. ServiceDescribe rate limit 省略语义已收敛为显式空策略。
- [x] 9. Capability action 偏离类别已机器化为 `event_mapping_kind`，并加 lint 校验允许类别与 grandfather 规则。
- [x] 10. 成功响应形态已 registry 化为 `success_shape_kind`，并加 OpenAPI 一致性 lint。
- [x] 11. Proposal frontmatter 状态规则已支持 `merged_into` / `merged_to`，并接入 `lint_spec.py`。

## 摘要

当前 spec 的主线设计已经比较完整，但仍有几类会影响实现互操作和安全边界的问题：

- OpenAPI 与 canonical registry 存在错误码枚举漂移，SDK 生成物会拒绝合法错误。
- DID / DID URL / typed ID 的 schema 约束不够精确，可能导致身份主体与签名 key 混淆。
- 部分 wire schema 违反自身命名规则，例如裸 `scope` 字段。
- 大量 reducer-input payload 允许任意未知字段，和 `critical_extensions` 的 fail-closed 机制存在张力。
- OpenAPI 仍有大量 `OperationRequest` / `OperationResult` 泛型面，降低了“canonical HTTP binding”的可机读性。
- ServiceDescribe、rate limit、cursor error 等章节之间存在若干语义不一致。

## P0 / P1 问题

### [x] 1. OpenAPI ErrorEnvelope 枚举与 error registry 漂移

**证据**

- `spec/v1/zh/sync/api-conventions.md:177` 声明 `error-code-registry.json` 是标准 error code 的 canonical 单一来源。
- `spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml:236-241` 声称 `ErrorEnvelope.error.code.enum` 由该 registry 生成。
- 实际比对：`error-code-registry.json` 的 `codes[]` 有 117 个；其中 `scope in {both, endpoint}` 的 102 个应该能出现在 HTTP ErrorEnvelope 中，但 OpenAPI enum 只有 45 个，缺 57 个 response/endpoint code。
- 缺失样例：`cursor_integrity_invalid`、`cursor_revoked`、`failed_precondition`、`did_proof_required`、`policy_violation`、`profile_unsupported`、`delivery_binding_unresolvable`。

**风险**

使用 OpenAPI 生成的 SDK / 客户端会把 registry 中合法的错误响应当成未知或 schema invalid。尤其是 cursor、recovery、blob、policy 相关错误会影响恢复流程和安全诊断。

**建议**

- 在 artifact pipeline 中加入 `ErrorEnvelope.error.code.enum == error-code-registry.codes[scope in {both, endpoint}]` 的硬校验。
- 若 `service_call` scope 不应进入 HTTP ErrorEnvelope，应在 registry schema 中明确这个分层，并生成独立枚举。
- 不要手工维护 OpenAPI enum；由 registry 生成。

### [x] 2. `policy_denied` / `cursor_unrecognized` 在 prose 中像顶层错误码，但 registry 只把它们放在 reason_codes

**证据**

- `api-conventions.md:408` 说 SSRF / egress policy 拒绝时 SHOULD 返回 `policy_denied`。
- `error-code-registry.json:1933` 的 `policy_denied` 位于 `reason_codes[]`，不是 `codes[]`，没有 HTTP status / scope。
- `encoding.md:443-444` 要求跨服务 stateful cursor portability miss 返回 `cursor_unrecognized`。
- `error-code-registry.json:931` 的 `cursor_unrecognized` 同样是 `reason_codes[]`。

**风险**

实现者会在顶层 `error.code` 和逐项 `reason_code` 之间做出不同选择。客户端无法稳定判断 HTTP status、重试语义和恢复路径。

**建议**

- 二选一收敛：
  - 将 `policy_denied`、`cursor_unrecognized` 提升为 `codes[]`，补 HTTP status / scope，并同步 OpenAPI。
  - 或修改 prose，明确返回顶层 `policy_violation` / `invalid_param` / `cursor_integrity_invalid`，并把 `policy_denied` / `cursor_unrecognized` 作为 `error.details.reason_code` 或批处理 item `reason_code`。

### [x] 3. DID 与 DID URL 的 schema 边界过宽，可能导致主体身份混淆

**证据**

- `common-fields.md:30` 定义 `did` 是 DID URI string；`common-fields.md:55` 又明确 `verification_method` 承载 DID URL。
- 多个 schema 的 `$defs.did` 使用 `^did:[a-z0-9]+:[^\s]+$`，例如 `event-envelope.schema.json:1522-1525`、`actor-profile.schema.json:88-90`。
- 该 pattern 会接受带 fragment / query 的 DID URL，例如 `did:example:alice#key-1`，从而可被填入 `actor_id`、`principal_id`、`created_by` 等 DID-as-id 字段。
- `event-envelope.schema.json:1833-1836` 对 `verification_method` 也使用同一宽松 pattern，并说明“DID or DID URL”，进一步模糊主体 DID 与 key DID URL。
- OpenAPI 中还有更宽的 `pattern: '^did:'`，例如 session grant 的 `principal_id`（`contrix-service-api.openapi.yaml:2760-2764`、`2895-2899`）。

**风险**

授权、capability matching、accountability、DID Document lookup 可能在“裸 DID”和“DID URL”之间出现规范化差异。一个组件把 `did:x:y#k` 当 actor DID，另一个组件 stripping fragment 后当 `did:x:y`，会造成签名归属、grant subject、审计主体不一致。

**建议**

- 全局拆分 `$defs.did` 与 `$defs.did_url`：
  - DID-as-id 字段禁止 `#`、`?`、fragment 和 DID URL service/query 形态。
  - `verification_method`、`kid` 等签名 key 字段必须使用 DID URL，通常要求 fragment。
- 在 OpenAPI 里复用同一 DID / DID URL component schema，不再使用 `^did:`。
- 加 conformance negative vectors：`actor_id = did:...#key`、`principal_id = did:...?service=...` 必须拒绝。

### [x] 4. `device_id` 在 OpenAPI 关键认证路径未按 typed ID 约束

**证据**

- `common-fields.md:37` 明确 `device_id` wire form MUST 为 `cx:device:<uuid>`，并强调不是例外字段。
- `PolicyCheckRequest.device_id` 只有 `type: string`（`contrix-service-api.openapi.yaml:2637-2638`）。
- `SessionGrantRequest.device_id` / `SessionGrantResponse.device_id` 也只有 `type: string`（`contrix-service-api.openapi.yaml:2763-2764`、`2898-2899`）。

**风险**

认证、policy check、session grant 这类安全敏感路径可能接受 raw UUID、设备别名或外部 device handle。不同实现如果在内部再补前缀，会造成签名 transcript、session binding、cursor binding 和 policy decision 不一致。

**建议**

- 定义 OpenAPI component `DeviceId`，pattern 与 schema registry 一致。
- 所有 `device_id` 字段和 path/query/body 参数统一 `$ref` 该 component。
- 对历史 raw device id 提供 migration-only parser，live HTTP path fail closed。

## P1 / P2 问题

### [x] 5. Wire schema 中仍存在裸 `scope` 字段，违反 common-fields 命名规则

**证据**

- `common-fields.md:57` 规定 wire schema 不得新增裸 `scope`，必须使用领域前缀，如 `read_scope`、`claim_scope`、`policy_scope`。
- `event-payload.schema.json:1367-1382` 的 `history_sharing_restricted_rule.scope` 是裸 `scope`。
- `recovery-policy.schema.json:164-175` 的 `trusted_recovery_services[].scope` 也是裸 `scope`。

**风险**

`scope` 在本协议里已经被用于 Circle/effective scope、capability selector scope、agent scope、consent scope、recovery service scope 等多个不同语义。裸名会让 schema author 和实现者把不同轴混用。

**建议**

- `history_sharing_restricted_rule.scope` 改为 `history_scope` 或 `sharing_scope`。
- `trusted_recovery_services[].scope` 改为 `recovery_action_scope` / `authorized_action_scope`。
- 将旧字段加入 `renames.json` / `forbidden-wire-fields.json`，并补 lint：非 registry metadata 中出现裸 `scope` 时失败。

### [x] 6. 已知 reducer-input payload 大量 `additionalProperties: true`，与 critical extension fail-closed 机制冲突

**证据**

- `event-and-patch.md:56` / `:65` 要求关键扩展通过 `requirements.critical_extensions[]` 声明并 fail closed；顶层扩展不得随意加。
- `event-payload.schema.json` 中 61 个 `$defs` object 使用 `additionalProperties: true`。
- 例：`message_create_payload` 只要求 `flow_id`、`track` 和 `content/encrypted_payload` 之一，但 `additionalProperties: true`（`event-payload.schema.json:2303-2369`）。
- 例：`object_stage_set_payload` 明确拒绝 `reason/note`，但仍允许其他任意未知字段（`event-payload.schema.json:674-685`）。

**风险**

未知字段进入已签名 payload 后，旧实现会保留并接受，新实现可能赋予语义，造成 downgrade / split-brain。攻击者也可以在安全敏感 payload 中携带“看似有效”的扩展字段，诱导部分客户端或桥接服务解释。

**建议**

- reducer-input 标准 payload 默认 `additionalProperties: false`。
- 非关键扩展统一放入 `x_*` 命名空间，并要求 Realm schema/profile 明确声明。
- 关键扩展必须出现在 `requirements.critical_extensions[]`，不支持则 fail closed。
- 对保留未知字段的规则限定到 materialized object projection 或 explicit extension container，不适用于标准 reducer-input payload。

### [x] 7. OpenAPI 仍大量使用泛型 `OperationRequest` / `OperationResult`

**证据**

- OpenAPI 自称是 canonical HTTP binding，并说明稳定核心操作应使用 typed schema（`contrix-service-api.openapi.yaml:48-61`）。
- `OperationRequest` / `OperationResult` 均为 `additionalProperties: true`（`contrix-service-api.openapi.yaml:3324-3334`）。
- 当前 OpenAPI 中仍有 45 个 request 使用 `OperationRequest`，57 个 response 使用 `OperationResult`。样例包括 push、keys、directory、blob、agent、MIMI、applet 等多个受保护面。

**风险**

SDK、WAF、合规扫描、测试向量无法从 OpenAPI 得到必填字段、字段类型、敏感字段位置和错误映射。越是扩展面和 service-to-service 面，越容易出现“prose-only contract”导致的实现分叉。

**建议**

- 给每个 active operation 增加 typed request/response schema，至少覆盖身份、key、push、blob、agent、directory 这些安全敏感面。
- 对尚未稳定的 extension 操作，在 registry 中标注 `generic_binding: true`、profile gate 和升级计划，避免误以为已经是完整可生成 SDK 的 surface。
- CI 增加阈值：active / required profile operation 不得引用 `OperationRequest` / `OperationResult`。

### [x] 8. ServiceDescribe 的 rate limit 字段要求前后不一致

**证据**

- `api-conventions.md:320` 说若省略 `rate_limit_policy` 和 `rate_limit_policy_id`，表示除通用滥用防护外没有可预期的端点级限流。
- `service-surface.md:233-235` 把 `rate_limit_policy` / `rate_limit_policy_id` 放入 Describe 必备字段组。
- `service-describe.schema.json:519-525` 使用 `anyOf` 强制要求二者至少一个。
- OpenAPI `ServiceDescribe` 同样用 `anyOf` 强制要求二者之一（`contrix-service-api.openapi.yaml:323-325`）。

**风险**

实现者不知道“没有端点级限流”的服务 describe 是否合法。严格 schema validator 会拒绝 prose 允许的省略形态。

**建议**

- 若 v1 要求所有服务都声明限流策略，则删除 `api-conventions.md:320` 的省略语义，改为要求返回 `rate_limit_policy: {entries: []}`。
- 若允许省略，则移除 schema / OpenAPI 的 `anyOf`，并明确 `rate_limit_policy` 与 `rate_limit_policy_id` 是 conditional required。

### [x] 9. Capability action 的偏离类别没有机器化字段

**证据**

- `capabilities.md:153-166` 规定 action 与 event kind 的偏离只允许四类，且禁止新增其它偏离。
- `capability-action-registry.json` / `contract-catalog.json` 的 action 条目只有 `action`、`category`、`risk_tier`、`required_constraints`、`target_event_kinds`、`profile`，没有 `deviation_category` 或 `migration_group` 字段。
- 当前 registry 已有多处 action != target event kind，例如 `cx.circle.manage`、`cx.object.archive`、`cx.agent.sidecar_thread.ensure`、`cx.policy.manage` 等。它们可能合理，但不可被 lint 证明属于四类之一。

**风险**

未来新增 action 时，规范只能靠人工 review 判断是否属于允许偏离。IAM / audit 工具也无法解释“为什么这个 action 可以覆盖这些 event kind”。

**建议**

- 给 action registry 增加 `event_mapping_kind`：`same_name | aggregate_admin | polymorphic_object | scope_suffix_variant | wire_compat_grandfather`。
- 对 `wire_compat_grandfather` 增加 `grandfathered_since`，并在 CI 中禁止新增。
- lint：`action != target_event_kind` 时必须有合法 `event_mapping_kind`。

## P2 / 维护性问题

### [x] 10. 成功响应形态分裂，SDK 需要 endpoint-specific 分支

**证据**

- `api-conventions.md:138-151` 明确没有统一 success envelope，成功响应可能是 `{ok:true}`、`{status:...}` 或裸字段。

**风险**

这不是直接 bug，但会放大 SDK 和测试矩阵复杂度。特别是批量提交、创建、解析、mutation 混用时，调用方需要为每个 endpoint 单独判断成功。

**建议**

- 保留现状也可，但应在 operation registry 中为每个 operation 增加 `success_shape_kind`，例如 `ok_envelope | status_envelope | bare_object | stream_frame`。
- SDK generator 从 registry 生成成功判定逻辑，而不是硬编码 endpoint 名称。

### [x] 11. Proposal frontmatter 与状态 lint 规则不一致

**证据**

- `STATUS_METRICS.md:67-72` 计划：accepted proposal 必须有 `merged_into:`，否则 lint warning `CXP002`。
- `proposals/0010-media-service-binding-framework.md:4-13` 是 `status: accepted`，但使用 `merged_to:`，没有 `merged_into:`。
- 当前 `python tools/lint_spec.py` 仍返回 0 warning，说明该规则尚未落地。

**风险**

proposal 迁入 normative 的追踪字段不稳定，后续审计“哪些草案已经成为 wire contract”会依赖人工判断。

**建议**

- 统一 frontmatter 字段名：要么把规则改成支持 `merged_to[]`，要么把 CXP-0010 改为 `merged_into:`。
- 将 CXP001/CXP002/CXP003 真正加入 `lint_spec.py`。

## 建议新增的自动化检查

1. [x] **Error registry ↔ OpenAPI enum drift check**：按 `scope` 生成 ErrorEnvelope enum。
2. [x] **DID kind check**：禁止旧的 `^did:` / greedy DID pattern；`verification_method` 必须匹配 DID URL。
3. [x] **Typed ID component check**：本轮覆盖 OpenAPI `device_id` 字段 / path 参数的 canonical pattern。
4. [x] **Bare scope field check**：wire schema 不得出现字段名 `scope`。
5. [x] **Reducer payload closure check**：active reducer-input payload 默认 `additionalProperties=false`；显式开放的 `generic_standard_payload` 作为例外。
6. [x] **Generic OpenAPI binding budget**：profile / extension operation 引用泛型 `OperationRequest` / `OperationResult` 时必须带 profile gate、原因和迁移计划；core tier 禁止。
7. [x] **Capability action deviation check**：`action != target_event_kind` 必须有机器化偏离类别。

## 本轮落地

- 更新 `spec/v1/artifacts/registry/error-code-registry.json`：新增顶层 `policy_denied`、`cursor_unrecognized`。
- 更新 `spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml`：ErrorEnvelope enum 重新按 registry 同步；DID / DID URL / `device_id` 约束收紧。
- 更新 `spec/v1/artifacts/schemas/*.schema.json`：DID-as-id pattern 禁止 fragment/query；签名 `verification_method` 改为 DID URL；裸 `scope` 改为 `history_scope` / `recovery_action_scope`。
- 更新 `spec/v1/zh/sync/api-conventions.md`：ServiceDescribe 不再允许同时省略 `rate_limit_policy` 与 `rate_limit_policy_id`，无端点级限流时使用显式空策略。
- 更新 `spec/v1/proposals/README.md`、`spec/v1/proposals/STATUS_METRICS.md`、`tools/lint_spec.py`：accepted CXP 支持单目标 `merged_into` 与多目标 `merged_to`。
- 更新 `tools/lint_artifacts.py`：新增 ErrorEnvelope enum、裸 `scope`、DID/DID URL、OpenAPI `device_id` 防回归检查。
- 更新 `spec/v1/artifacts/schemas/event-payload.schema.json`：关闭标准 reducer-input payload 顶层未知字段，降低 critical extension 绕过风险。
- 更新 `spec/v1/artifacts/registry/contract-catalog.json` 及派生 registry / public catalog 快照：新增 capability action `event_mapping_kind`、operation `success_shape_kind`、泛型绑定 `generic_binding` 迁移预算。
- 更新 `spec/v1/zh/authz/capabilities.md`、`spec/v1/zh/sync/api-conventions.md` 与 OpenAPI 说明：把 action 偏离类别、成功响应形态、泛型绑定治理写回规范正文。
- 更新 `tools/lint_artifacts.py`：新增 reducer payload closure、capability action event mapping、operation binding metadata 一致性检查。

## 自检结果

- [x] `python tools/artifact_pipeline.py check`
- [x] `python tools/lint_artifacts.py`
- [x] `python tools/lint_spec.py`
