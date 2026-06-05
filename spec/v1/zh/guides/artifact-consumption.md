---
title: Artifact Consumption Guide
status: candidate
normative: false
stability: v1
updated: 2026-05-25
---

# Cokret v1 Artifact Consumption Guide

本指南定义实现侧消费 `spec/v1/artifacts/` 的边界，避免各项目继续手抄协议事实表。

> **另见** [`reference-implementation-guide.md`](./reference-implementation-guide.md)：本指南聚焦"哪些 artifact 是 source of truth 及其消费边界"；参考实现指南聚焦"按何种顺序接入这些 artifact 生成 stub / 跑一致性向量"。二者配合阅读。

## Source Of Truth

实现侧必须把以下 artifact 作为 v1 协议事实来源:

- `registry/event-kind-registry.json`: event kind 是否 active、wire scope、cell family、lattice、bottom、payload schema。
- `registry/operation-registry.json`: service operation ID、surface group、profile tier。
- `registry/schema-registry.json`: registered schema ID 到 schema artifact 的映射；consumer MUST 递归解析同目录 `$ref` 指向的 raw schema artifact（例如 `event-envelope.schema.json` 引用的 `event-schema.json`），不得假设 registry 直接列出的文件就是全部需要发布或缓存的 schema 文件。
- `registry/id-kind-registry.json`: typed ID kind 与 wire form。
- `profiles/conformance-profiles.json`: profile inheritance、required operations、event kinds、schemas、fixtures、features、capability actions、cell namespaces、rejected event kinds。

手写常量只能作为 ergonomics alias；admission、profile claim、conformance gate 不得以手写常量作为唯一事实来源。

## JSON Schema `$id` 与发布形态

仓库内 validator SHOULD 使用本地 resolver，把 `$id` 映射到 `spec/v1/artifacts/schemas/<file>.json`，避免测试依赖网络。发布站点则 MUST 在相同路径提供 raw JSON Schema artifact，而不是 HTML catalog 页面；`$id` URL 返回的 body 必须能被标准 JSON Schema validator 直接解析。

推荐响应头：

- `Content-Type: application/schema+json`（至少 `application/json`）
- `Cache-Control` 可按发布版本长期缓存，但 breaking schema 更新必须通过版本化 schema id 表达

Markdown catalog 页面可以继续存在于 `/catalog/schemas/`；它是人类阅读视图，不得替代 `$id` URL 的机器消费形态。

## Rust SDK

`cokret-rust-sdk` 是 artifact 消费的第一层。

- `cokret_core::schema::SpecArtifactBundle` 负责读取 artifact bundle 并提供 drift report。
- `cokret_core::schema::event_payload_validator_catalog()` 负责从 event kind registry 和 schema registry 构建 payload validator。
- `cokret_core::generated::profiles` 和 `cokret_core::generated::profile_requirements` 负责发布 generated profile/profile requirement 常量。
- 新增协议字段时，先更新 artifact，再重新生成 SDK generated module，最后让服务端/客户端消费 SDK API。

禁止在服务端或客户端复制 generated profile requirement 表。

## Soland

Soland 是 principal server，不是协议 registry 的来源。

- Event kind admission 先查 `event-kind-registry.json` 的 active durable event kind。
- 已有强语义 validator 可以继续留在 `routing/events/operations.rs`，用于 flow、message、redaction 等需要 server policy 的路径。
- 对没有手写强语义 validator 的 active event kind，Soland 应 fallback 到 SDK artifact payload validator。
- `src/kinds.rs` 中的常量应逐步缩为 server-local alias 和 readable match arms；新增 standard event kind 不应要求先修改 `kinds.rs` 才能被识别。

## Yougen

Yougen 是客户端，不应重新解释协议安全事实。

- Agent audit binding、authz delegation、lattice pre-check、account data shape 应优先消费 SDK helper。
- UI 可以持有 view-model 和 local cache，但 `client.ui`、`client.blocklist`、profile gate 结果必须能 roundtrip 到 server account data 或 server describe。
- 附件/blob 展示应消费 SDK media/blob 类型和服务端 authenticated URL，不得长期使用 placeholder URL。

## Cotest

Cotest 应测实现对 artifact 的遵循，而不是维护另一份手写协议事实。

- Profile gate tests 使用 generated `profile_requirements` 比较实现 surface。
- Event payload negative tests 使用 SDK validator 构造已知 invalid vector。
- 跨服务 scenario 可以 soft-gate 外部依赖，但一旦服务启动成功，断言必须是真实协议断言。

## Migration Rule

迁移顺序:

1. Spec artifact 新增或修改协议事实。
2. SDK generated/artifact reader 更新并有 drift test。
3. 各下游实现（principal server、客户端、bridge、媒体服务等）通过 SDK 或 embedded artifact 消费。
4. Cotest 增加默认或 soft-gated 断言。
5. 删除项目内重复事实表或把它降级为 alias。
