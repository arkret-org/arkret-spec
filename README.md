# Contrix Spec

Contrix v1 去中心化协作协议规范。仓库同时承载 **规范本体** 和 **协议站源码**。

## Realm vs Space

- **Realm:** security boundary — membership, capability, E2EE, and federation
  are governed at this level.
- **Space:** navigation container — board, list, section, calendar bucket.
  Lives inside a Realm.

The normative tables under `spec/v1/zh/` are the source of truth for wire
names. Historical / pre-inversion model names and their replacements are
recorded in `CHANGELOG.md` and the machine-readable drift artifacts under
`spec/v1/artifacts/registry/` (`renames.json`, `removed-event-kinds.json`,
`forbidden-model-terms.json`, `forbidden-wire-fields.json`).

- 规范本体：[`spec/v1/`](./spec/v1/)
  - 中文 normative 正文：[`spec/v1/zh/index.md`](./spec/v1/zh/index.md)
  - 英文 normative：占位（未发布）
  - 机器构件：[`spec/v1/artifacts/`](./spec/v1/artifacts/)
  - **提案（非 normative）**：[`spec/v1/proposals/`](./spec/v1/proposals/) — Contrix Proposal (CXP) 草案，未 accepted 前不构成 wire contract
- 协议站源码：[`site/`](./site/) — Astro Starlight + Scalar(OpenAPI) + 自定义 JSON Schema 渲染器
- 工具：[`tools/`](./tools/) — registry 生成 / lint 流水线

## Layout

```
spec/v1/
├── zh/   en/                      # 规范正文（normative prose）
├── proposals/                     # Contrix Proposals (CXP) — 非 normative
└── artifacts/
    ├── registry/                  # contract-catalog (canonical) + 派生 view
    ├── profiles/                  # conformance-profiles.json
    ├── schemas/                   # JSON Schema *.schema.json
    ├── openapi/                   # contrix-service-api.openapi.yaml
    ├── bindings/                  # 非 HTTP transport binding
    └── fixtures/                  # conformance fixtures
site/
└── ...                            # 协议站（npm 项目）
tools/
├── artifact_pipeline.py           # registry 生成 / drift check
└── lint_artifacts.py              # 跨构件 + markdown 引用一致性 lint
```

## 规范权威层级

- `spec/v1/artifacts/registry/contract-catalog.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `spec/v1/artifacts/registry/event-kind-registry.json`、`schema-registry.json`、`id-kind-registry.json`、`operation-registry.json` 是从 canonical catalog 生成的机器视图；实现、SDK、lint 应消费这些生成物，不要手抄 Markdown。
- `spec/v1/artifacts/registry/error-code-registry.json` 是标准 service error 的 canonical registry。
- `spec/v1/artifacts/openapi/contrix-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape。
- `spec/v1/artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵。
- `spec/v1/zh/**/*.md` 主要承担解释、边界说明和阅读路径；除明确标注"生成视图"外，不再手工维护穷尽清单——这部分由协议站组件运行时从 catalog 渲染。

任何 `spec/v1/zh/` 与 canonical artifact 的漂移都是规范 bug。对 event / schema / id / operation / error / profile wire contract，实现 MUST 跟随 active 机器 registry / schema；对 reducer、authorization、privacy、security、deployment 语义，实现 MUST 跟随中文 normative 文本。

## Maintenance pipeline

```
python tools/artifact_pipeline.py generate   # 重新生成派生 registry view
python tools/artifact_pipeline.py check      # drift 检查 + lint
```

CI: [`.github/workflows/artifact-lint.yml`](./.github/workflows/artifact-lint.yml)

## 站点

```
cd site
npm install
npm run dev          # http://localhost:4321
npm run build        # 静态产物 site/dist/
```

详见 [`site/README.md`](./site/README.md)。
