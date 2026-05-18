---
title: Artifact Consumption Guide
---

# Contrix v1 Artifact Consumption Guide

本指南定义实现侧消费 `spec/v1/artifacts/` 的边界，避免各项目继续手抄协议事实表。

## Source Of Truth

实现侧必须把以下 artifact 作为 v1 协议事实来源:

- `registry/event-kind-registry.json`: event kind 是否 active、wire scope、cell family、lattice、bottom、payload schema。
- `registry/operation-registry.json`: service operation ID、surface group、profile tier。
- `registry/schema-registry.json`: schema ID 到 schema artifact 的映射。
- `registry/id-kind-registry.json`: typed ID kind 与 wire form。
- `profiles/conformance-profiles.json`: profile inheritance、required operations、event kinds、schemas、fixtures、features、capability actions、cell namespaces、rejected event kinds。

手写常量只能作为 ergonomics alias；admission、profile claim、conformance gate 不得以手写常量作为唯一事实来源。

## Rust SDK

`contrix-rust-sdk` 是 artifact 消费的第一层。

- `contrix_core::schema::SpecArtifactBundle` 负责读取 artifact bundle 并提供 drift report。
- `contrix_core::schema::event_payload_validator_catalog()` 负责从 event kind registry 和 schema registry 构建 payload validator。
- `contrix_core::generated::profiles` 和 `contrix_core::generated::profile_requirements` 负责发布 generated profile/profile requirement 常量。
- 新增协议字段时，先更新 artifact，再重新生成 SDK generated module，最后让服务端/客户端消费 SDK API。

禁止在服务端或客户端复制 generated profile requirement 表。

## Soland

Soland 是 principal server，不是协议 registry 的来源。

- Event kind admission 先查 `event-kind-registry.json` 的 active durable event kind。
- 已有强语义 validator 可以继续留在 `routing/events/operations.rs`，用于 flow、agent workspace、message、redaction 等需要 server policy 的路径。
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
3. Soland/Yougen/Teabay/Floria/Chime 通过 SDK 或 embedded artifact 消费。
4. Cotest 增加默认或 soft-gated 断言。
5. 删除项目内重复事实表或把它降级为 alias。
