# 实现兼容矩阵

本文给实现方一个最小、稳定、可执行的兼容矩阵，避免每个下游仓库重复人工摘录 active contract。

## 1. Canonical 输入

所有下游实现至少应消费：

- `artifacts/registry/contract-catalog.json`
- `artifacts/registry/event-kind-registry.json`
- `artifacts/registry/schema-registry.json`
- `artifacts/registry/id-kind-registry.json`
- `artifacts/registry/operation-registry.json`
- `artifacts/registry/legacy-compatibility-policy.json`
- `artifacts/profiles/conformance-profiles.json`
- `artifacts/openapi/contrix-service-api.openapi.yaml`
- `artifacts/fixtures/legacy-contract-negative-fixture.json`

## 2. 下游矩阵

| 下游仓库 / 组件 | 必须对齐的 canonical 输入 | 当前第一 blocker | 完成信号 |
| --- | --- | --- | --- |
| `contrix-rust-sdk` | schema / id-kind / event-kind / operation registry；legacy policy；negative fixture | 删除 `subject` / `room` / `card` typed builder、schema enum 和 event builder，统一到 `flow` / `flow.branch.*` | builder 和 validator 只输出 `cx:flow:*`；通过 `core_event_store` fixture 与 `legacy-contract-negative-fixture.json` |
| `soland` | operation registry；OpenAPI；schema；legacy policy；migration guide | 存储导出层、sync DTO、federation DTO 不再输出 legacy ID / schema / event kind | API surface 与 `supported_operations` 一致；active wire 输出不含 removed contract；通过 OpenAPI + fixture gate |
| `yougen` | operation registry；OpenAPI；service-api inventory；compatibility matrix | 代码生成模板不再手写旧 operation / DTO alias；生成结果直接消费 registry 和 OpenAPI | 生成物不再引用 removed contract；`supported_operations` 与 registry 无差集 |
| `cotest` | conformance profiles；全部 fixtures；legacy negative fixture；legacy policy | 增加黑盒 mutation runner，把 removed contract 当 reject set，而不是当 optional backward-compat path | 按 profile 输出 pass/fail/coverage；对 legacy reject set 返回拒绝且错误码命中允许集合 |
| 通用客户端 | schema / event-kind / sync fixture / compatibility matrix | UI 可保留 card/room 视图名，但 object identity、sync key、permission key 统一改成 `flow_id` | timeline / projection 不再依赖 `room_id` / `card_id` typed ID |
| 通用服务端 | operation registry；OpenAPI；schema；legacy policy；negative fixture | validator 和 importer 分层：active wire reject，offline import rewrite-before-validation | active wire reject removed contract；历史导入只走 rewrite 流程 |

## 3. 统一验收口径

所有下游仓库至少要满足：

- active wire 输出不包含 `cx:subject:`、`cx:room:`、`cx:card:`。
- active wire 输出不包含 `cx.schema.subject.v1`、`cx.schema.room.v1`、`cx.schema.card.v1`。
- active wire 输出不包含 `cx.subject.*`、`cx.room.*`、`cx.card.*`。
- 目录、projection、discussion 入口若仍保留旧 UI 名词，只能是 view label，不得回流为 typed ID、schema id 或 event kind。
- 历史导入若接受 legacy 数据，必须在 active validation、hash、签名、snapshot、sync、federation 之前先 rewrite。

## 4. 推荐验收顺序

1. 先清空 typed ID / schema ID / event kind 的 legacy 输出面。
2. 再清空 API DTO、OpenAPI、codegen 模板和 `supported_operations` 的 legacy 派生面。
3. 再把历史导入器和 migration tool 收敛到 `legacy-compatibility-policy.json`。
4. 最后用 `legacy-contract-negative-fixture.json` 做黑盒拒绝回归。
