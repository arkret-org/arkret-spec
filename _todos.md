# contrix-spec Active TODO

更新时间: 2026-05-02

本文只跟踪规范和机器工件本身的剩余工作。实现项目的落地任务分别在各项目 `_todos.md` 中跟踪。

状态: 本仓库规范/机器工件范围已闭环；外部 SDK、`cotest` 和 reference Principal Server 的实际实现验收仍以对应项目清单为准。

## 0. 当前规范边界

- [x] 中文 `zh/` 是 Contrix v1 当前规范源；英文 `en/` 已标记为 stale。
- [x] v1 wire canonical fact 已收敛为 signed `Event Envelope`；`Canonical Operation Object` 只作为 SDK builder / 离线草稿 / 本地内容寻址中间对象。
- [x] 核心对象边界为 `Space / Room / Board / List / Card / Message / Morph / Relation / Event / View`。
- [x] `artifacts/` 承载 JSON Schema、OpenAPI、registry、fixtures、profiles 和 non-HTTP bindings。
- [x] Markdown 示例、OpenAPI、registry、fixtures、profiles 和 schema 的一致性已纳入自动化 lint。

## P0: 规范源与机器工件闭环

这些任务可以由 spec/artifacts 维护者与 SDK 维护者并行推进，但合并前必须互相校验。

- [x] 建立 registry-first 校验流程:
  - 以 `artifacts/registry/event-kind-registry.json` 作为标准 `Event.kind` 唯一来源。
  - 以 `artifacts/registry/schema-registry.json` 作为 `cx.schema.*` 唯一来源。
  - 以 `artifacts/registry/id-kind-registry.json` 固定 `cx:<kind>:` typed ID 前缀。
  - 以 `artifacts/registry/operation-registry.json` 固定服务 operation id。
  - Markdown 中出现的标准 kind、schema id、operation id、typed ID 示例必须能被脚本抽取并校验。
- [x] 补齐 artifact drift CI:
  - 校验 `zh/conformance/schemas/*` 与 `artifacts/schemas/*` 一致。
  - 校验 `zh/sync/contrix-service-api.openapi.yaml` 与 `artifacts/openapi/contrix-service-api.openapi.yaml` 一致。
  - 校验 fixtures 中的 event/schema/kind/profile 引用均存在于 registry。
  - 校验 deprecated alias 只能出现在 registry 的兼容声明中，不能出现在新示例写路径中。
- [x] 冻结 v1 event envelope 字段:
  - 顶层字段必须覆盖 `event_id`、`space_id`、`actor_id`、`actor_seq`、`kind`、`created_at`、`hlc`、`prev_refs`、`auth_refs`、`content`、`proofs`。
  - `required_features`、`critical_extensions`、`schema_profile_refs`、`reducer_profile_ref` 必须进入 digest 规则和 fixture。
  - 明确 `operation_id` 只能作为服务 operation id 或旧 SDK 本地幂等别名。
- [x] 补齐 `Event Envelope` 负向样例:
  - 裸名事件、未知 critical feature、签名 payload hash 不匹配、`actor_seq` 回退、`prev_refs` 超限、`auth_refs` 缺失。
  - 同一 `event_id` 不同 canonical bytes 的 duplicate conflict。
  - `wire_scope=actor_private_event` 或 `ephemeral_event` 被错误提交到 durable history。

## P0: 最小互操作 Profile 收敛

这些闭环应优先服务 `contrix-rust-sdk`、`soland`、`yougen` 和 `cotest`。

- [x] 固化 `cx.profile.core_event_store.v1`:
  - DID / service discovery。
  - Event Envelope validation。
  - event submit/fetch/batch-get/backfill/frontier。
  - per-actor event chain validation。
  - idempotent duplicate handling。
  - standard error envelope。
- [x] 固化 `cx.profile.chat_mvp.v1`:
  - Space、`cx.member.state`、Room、`cx.room.member`、Message、Reaction、Redaction。
  - Client Sync timeline、`state_after`、history visibility、lazy member loading。
  - E2EE 可选时的 encrypted event preservation 和 key-missing 状态。
- [x] 固化 `cx.profile.kanban_mvp.v1`:
  - Board/List/Card。
  - `contains` position Relation。
  - `cx.card.move`、`cx.card.reorder`、`cx.list.reorder`、`cx.container.rebalance`。
  - Collection projection、rank tie-break、wait-for query。
- [x] 为 `principal_server`、`index_node`、`identity_registry`、`push_gateway`、`full_client`、`e2ee_client` 建立 profile-to-test matrix。
- [x] 在 `artifacts/profiles/conformance-profiles.json` 中给每个 profile 明确:
  - 必须实现的 endpoint。
  - 必须接受/拒绝的 event kind。
  - 必须加载的 schema。
  - 必须通过的 fixture 文件。
  - 可选扩展和未实现时的 feature discovery 返回。

## P0: Reducer、Authz 与状态收敛

可由 spec 作者定义算法，SDK/cotest 同步实现测试。

- [x] 把 deterministic event order 写成可执行算法:
  - causal dependency first。
  - `actor_seq` 单调。
  - HLC 排序。
  - `event_id` final tie-break。
  - 禁止使用数据库自增 ID、HTTP 到达顺序或 sync service 接收顺序。
- [x] 形式化 state resolution:
  - state key 提取规则。
  - `auth_weight` priority class 完整枚举。
  - membership、join rule、history visibility、policy component、capability conflict 的 winner/loser 规则。
  - `conflict_records`、`soft_failed`、`quarantined` 的输出形态。
- [x] 形式化 capability engine:
  - resource selector AST。
  - grant/delegation 展开顺序与 cycle detection。
  - claim/attestation 验证顺序。
  - approval/proposal constraint 的生效点。
  - Authz Snapshot Bitmap cache key、失效条件和最大重建延迟。
- [x] 明确 revocation freshness:
  - 高风险动作必须绑定最新可验证 grant/revoke frontier。
  - backdated `created_at` 和 HLC future drift 必须 fail closed 或 soft fail。
  - 离线写入需要 pre-revocation lease / snapshot proof 或可验证 causal frontier。

## P1: 服务面与 OpenAPI

这些任务可由服务端实现者和 SDK API crate 并行执行。

- [x] 让 `service-http-binding.md`、`service-api-schema.md` 与 OpenAPI 完全一致。
- [x] 为所有 endpoint 标注:
  - service operation id。
  - authn/authz 要求。
  - idempotency key 规则。
  - cursor/page 上限。
  - error envelope。
  - plaintext visibility class。
- [x] 明确 `/events/*` 与兼容 `/repo/*` 的边界:
  - 新互操作实现必须支持 `/events/*`。
  - `/repo/operations`、`/repo/submit-commit` 只能作为 compatibility 或 local adapter，不是 v1 主写路径。
- [x] 为 Index/AppView 输出定义稳定 DTO:
  - Board projection。
  - Timeline projection。
  - Graph/tree lazy link。
  - Inbox/notification。
  - Access explanation。
  - Pending/conflict/retry state。

## P1: 身份、隐私与账号关联

- [x] 补齐 `did:uuid` fixture:
  - UUID v8 bit layout。
  - 44-bit ms timestamp。
  - 4-bit hash algorithm id。
  - 74-bit inception key hash fragment。
  - 大端填充。
  - private/pairwise DID timestamp privacy variant。
- [x] 补齐 DID resolver policy 示例:
  - 公共 `did:uuid` registry。
  - 组织私有 registry。
  - sovereign pinned resolver。
  - `did:web` adapter。
  - `did:key` local adapter。
  - `did:keri` future adapter boundary。
- [x] 补齐 account-first onboarding 规范示例:
  - OIDC/passkey 登录只绑定 service account。
  - 持久 Event 写入前必须完成 DID proof 或托管 DID 创建。
  - service account recovery 不等于 DID recovery。
- [x] 补齐 progressive disclosure 测试向量:
  - overbroad request rejection。
  - represented organization proof。
  - pairwise DID response。
  - disclosure receipt 不包含 withheld values。

## P1: 安全与隐私 Conformance

- [x] Directory 隐私向量:
  - nonexistent / hidden / invite-only 同形态响应。
  - actor search 不因共同 Space 或 presence 泄露未授权关系。
  - private contact discovery 的 batch cardinality 和 timing class。
- [x] Snapshot 安全向量:
  - manifest signature。
  - `event_set_commitment`。
  - inclusion / omission challenge。
  - witness quorum。
  - soft-failed/quarantined 摘要。
- [x] Plaintext-visible service 向量:
  - 未列入服务拒绝明文 message body、attachment preview、notification summary。
  - E2EE Space 的 index/search/push 只允许密文 envelope、不可逆 hash 或 policy 允许的 stripped preview。
- [x] Agent escalation 向量:
  - owner 有权限不代表 agent 自动有权限。
  - owner presence 默认不可见。
  - agent 加入 Space/Room 需要显式 grant。
  - confirmed memory 写入需要独立 action 和 review policy。

## P2: 英文规范刷新

- [x] 在 v1 Core 冻结后固定 `en/` 边界:
  - 根 README、`zh/overview/gap-analysis.md` 与 lint 范围均声明 `zh/` + `artifacts/` 是当前 source of truth。
  - 保留 stale 标记直到英文目录通过 registry lint。
  - 避免英文目录产生新的术语源。

## Definition of Done

- [x] 新增或修改的标准 kind/schema/operation/profile 都先进入 `artifacts/registry/*`。
- [x] Markdown 示例、OpenAPI、schema、fixtures 全部通过一致性 lint。
- [x] `artifacts/profiles/conformance-profiles.json` 已提供 `cotest` 可读取的 profile-to-fixture 覆盖矩阵。
- [x] SDK 和 reference Principal Server 所需的 `core_event_store` 声明、endpoint、schema、fixture 输入已固定；实际通过由对应项目跟踪。
- [x] 英文目录继续标记为 stale，根 README 明确不得作为实现 source of truth，避免被实现者误用。

