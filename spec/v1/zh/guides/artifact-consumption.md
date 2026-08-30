---
title: Artifact Consumption Guide
status: candidate
normative: false
stability: v1
updated: 2026-07-13
---

# Arkret v1 Artifact Consumption Guide

本指南定义实现侧消费 `spec/v1/artifacts/` 的边界，避免各项目继续手抄协议事实表。

> 本文件是 informative 实施指南，不是协议真相源；其中复述的 MUST / MUST NOT / SHOULD 规则，其权威来源为被引用的规范正文、schema 与 registry。找不到权威来源的实施建议不得作为 wire conformance 规则引用。

> **另见** [`reference-implementation-guide.md`](./reference-implementation-guide.md)：本指南聚焦"哪些 artifact 是 source of truth 及其消费边界"；参考实现指南聚焦"按何种顺序接入这些 artifact 生成 stub / 跑一致性向量"。二者配合阅读。

## Source Of Truth

实现侧应把以下 artifact 作为 v1 协议事实来源:

- `registry/event-kind-registry.json`: event kind 是否 active、wire scope、cell family、lattice、bottom、payload schema。
- `registry/operation-registry.json`: service operation ID、transport binding（`http` / `grpc` / `mq`）、`body_class`、`success_shape_kind` 与 `response_schema_ref`。profile 归属不在本文件，见 `profiles/conformance-profiles.json`。
- `registry/schema-registry.json`: registered schema ID 到 schema artifact 的映射；consumer 递归解析同目录 `$ref` 指向的 raw schema artifact（例如 `event-envelope.schema.json` 引用 `event-payload.schema.json`、`common-ids.schema.json` 与 `read-cursor.schema.json`），避免假设 registry 直接列出的文件就是全部需要发布或缓存的 schema 文件。该要求的权威来源是 [`../overview/release-readiness.md`](../overview/release-readiness.md)。
- `registry/track-name-registry.json`: `Strand.tracks` active key 的闭集、状态与 schema/profile owner；未登记名称不得仅凭正则匹配进入 reducer。
- `registry/id-kind-registry.json`: typed ID kind 与 wire form。
- `profiles/conformance-profiles.json`: profile inheritance、required operations、event kinds、schemas、fixtures、features、capability actions、cell namespaces、rejected event kinds。

> 上述 `registry/{event-kind,operation,schema,track-name,id-kind}-registry.json` 是从 canonical `registry/contract-registry.json` 生成的机器视图；contract-registry 是它们的 single source of truth。新增或修改 contract 时，实施流程先修改 catalog 再重生成；权威规则见 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。

手写常量只能作为 ergonomics alias；admission、profile claim、conformance gate 应避免以手写常量作为唯一事实来源。

## JSON Schema `$id` 与发布形态

仓库内 validator 可使用本地 resolver，把 `$id` 映射到 `spec/v1/artifacts/schemas/<file>.json`，避免测试依赖网络。发布站点在相同路径提供 raw JSON Schema artifact、而不是 HTML catalog 页面的要求，权威来源为 [`../overview/release-readiness.md`](../overview/release-readiness.md)；`$id` URL 返回的 body 需要能被标准 JSON Schema validator 直接解析。

推荐响应头：

- `Content-Type: application/schema+json`（至少 `application/json`）
- `Cache-Control` 可按发布版本长期缓存；breaking schema 更新通过版本化 schema id 表达（规范见 [`../overview/release-readiness.md`](../overview/release-readiness.md)）

Markdown catalog 页面可以继续存在于 `/catalog/schemas/`；它是人类阅读视图，不应替代 `$id` URL 的机器消费形态。

## Rust SDK

`arkret-rust-sdk` 是 artifact 消费的第一层。

- `arkret_schema::SpecArtifactBundle` 负责读取 artifact bundle 并提供 drift report。
- `arkret_schema::event_payload_validator_catalog()` 负责从 event kind registry 和 schema registry 构建 payload validator。
- `arkret_wire::ProfileId`（含 `ProfileId::role`）和 `arkret_wire::ReducerProfileId` 负责发布 generated conformance / reducer profile 标识与角色划分；`arkret_wire::generated::profile_requirements` 负责发布 profile requirement 表（与其余 generated registry 同处 `arkret-wire`，消费者一律直接引用该路径）。
- 新增协议字段时，先更新 artifact，再重新生成 SDK generated module，最后让服务端/客户端消费 SDK API。

服务端或客户端不应复制 generated profile requirement 表；需要本地别名时，应能追溯到 SDK/generated artifact。

## Soland

Soland 是 Station，不是协议 registry 的来源。

- Event kind admission 先查 `event-kind-registry.json` 的 active durable event kind。
- 已有强语义 validator 可以继续留在 `crates/http/src/routing/events/operations/`，用于 strand、message、redaction 等需要 server policy 的路径。
- 对没有手写强语义 validator 的 active event kind，Soland 应 fallback 到 SDK artifact payload validator。
- server-local event-kind 常量应逐步缩为 alias 和 readable match arms；新增 standard event kind 不应要求先修改这些常量才能被识别。

## Inkson

Inkson 是客户端，不应重新解释协议安全事实。

- Agent audit binding、authz delegation、lattice pre-check、account data shape 应优先消费 SDK helper。
- UI 可以持有 view-model 和 local cache；`client.ui`、`client.blocklist`、profile gate 结果应能 roundtrip 到 server account data 或 server describe。
- 附件/blob 展示应消费 SDK media/blob 类型和服务端 authenticated URL，避免长期使用 placeholder URL。

## Cotest

Cotest 应测实现对 artifact 的遵循，而不是维护另一份手写协议事实。

- Profile gate tests 使用 generated `profile_requirements` 比较实现 surface。
- Event payload negative tests 使用 SDK validator 构造已知 invalid vector。
- 跨服务 scenario 可以 soft-gate 外部依赖；一旦服务启动成功，断言应是真实协议断言。

## Migration Rule

迁移顺序:

1. Spec artifact 新增或修改协议事实。
2. SDK generated/artifact reader 更新并有 drift test。
3. 各下游实现（Station、客户端、bridge、媒体服务等）通过 SDK 或 embedded artifact 消费。
4. Cotest 增加默认或 soft-gated 断言。
5. 删除项目内重复事实表或把它降级为 alias。
