# Reference Implementation Guide

本指南描述实现方如何消费本仓库的 canonical 输出。

## 1. 推荐接入顺序

1. 读取根目录 [`artifacts/registry/schema-registry.json`](../../artifacts/registry/schema-registry.json)、[`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 与 [`operation-registry.json`](../../artifacts/registry/operation-registry.json)。
   若需要判断 canonical source、surface tier 和 generated view 的关系，先读 [`artifacts/registry/contract-catalog.json`](../../artifacts/registry/contract-catalog.json)。
2. 用 `artifacts/schemas/` 或镜像到 `zh/en/conformance/schemas/` 的 JSON Schema 做结构校验。
3. 用 [`artifacts/openapi/contrix-service-api.openapi.yaml`](../../artifacts/openapi/contrix-service-api.openapi.yaml) 生成服务 stub、client 或 contract tests。
4. 用 `artifacts/fixtures/` 运行一致性向量。
5. 依据 `conformance-profiles.md` 与 `artifacts/profiles/conformance-profiles.json` 声明实现 profile。
6. 若实现从旧 `subject/room/card` contract 迁移，必须同时阅读 [`legacy-subject-room-card-to-flow-migration.md`](./legacy-subject-room-card-to-flow-migration.md) 与 [`implementation-compatibility-matrix.md`](./implementation-compatibility-matrix.md)。

## 2. 实现要求

- 所有写路径 MUST 支持幂等键。
- 结构校验通过后，仍 MUST 独立执行 signature、hash、capability、policy 与 MLS 验证。
- `operation_id`、`Event.kind`、schema id、profile id MUST 视为稳定兼容锚点。
- query string MUST NOT 承载长期认证材料。
- 对 removed legacy contract 的离线导入、拒绝基线和 rewrite 顺序，MUST 以 `legacy-compatibility-policy.json` 与 `legacy-contract-negative-fixture.json` 为准，而不是以仓库外口头约定为准。

## 3. 产出建议

- SDK：typed builders + validators。
- 服务端：OpenAPI contract test + fixture runner。
- 客户端：schema decode + sync/profile regression。
- `cotest`：以 profile 为单位输出 pass/fail 与 coverage。

## 4. 迁移交接入口

- 迁移规则：[`legacy-subject-room-card-to-flow-migration.md`](./legacy-subject-room-card-to-flow-migration.md)
- 下游兼容矩阵：[`implementation-compatibility-matrix.md`](./implementation-compatibility-matrix.md)
- 黑盒拒绝基线：[`artifacts/fixtures/legacy-contract-negative-fixture.json`](../../artifacts/fixtures/legacy-contract-negative-fixture.json)
