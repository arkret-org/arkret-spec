# Reference Implementation Guide

本指南描述实现方如何消费本仓库的 canonical 输出。

## 1. 推荐接入顺序

1. 读取根目录 [`artifacts/registry/schema-registry.json`](../../artifacts/registry/schema-registry.json) 与 [`operation-registry.json`](../../artifacts/registry/operation-registry.json)。
2. 用 `artifacts/schemas/` 或镜像到 `zh/en/conformance/schemas/` 的 JSON Schema 做结构校验。
3. 用 [`artifacts/openapi/contrix-service-api.openapi.yaml`](../../artifacts/openapi/contrix-service-api.openapi.yaml) 生成服务 stub、client 或 contract tests。
4. 用 `artifacts/fixtures/` 运行一致性向量。
5. 依据 `conformance-profiles.md` 与 `artifacts/profiles/conformance-profiles.json` 声明实现 profile。

## 2. 实现要求

- 所有写路径 MUST 支持幂等键。
- 结构校验通过后，仍 MUST 独立执行 signature、hash、capability、policy 与 MLS 验证。
- `operation_id`、schema id、profile id MUST 视为稳定兼容锚点。
- query string MUST NOT 承载长期认证材料。

## 3. 产出建议

- SDK：typed builders + validators。
- 服务端：OpenAPI contract test + fixture runner。
- 客户端：schema decode + sync/profile regression。
- `cotest`：以 profile 为单位输出 pass/fail 与 coverage。
