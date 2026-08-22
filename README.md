<p align="center">
  <img src="./site/public/brand/arkret-logo.svg" alt="Arkret logo" width="160" />
</p>

# Arkret Spec

Arkret v1 去中心化协作协议规范。仓库同时承载 **规范本体** 和 **协议站源码**。

## Realm vs Space

- **Realm:** security boundary — membership, capability, E2EE, and federation
  are governed at this level.
- **Space:** navigation container — board, list, section, calendar bucket.
  Lives inside a Realm.

The normative tables under `spec/v1/zh/` and the machine-readable artifacts
under `spec/v1/artifacts/` are the source of truth for current v1 wire names.

- 规范本体：[`spec/v1/`](./spec/v1/)
  - 中文 normative 正文：[`spec/v1/zh/index.md`](./spec/v1/zh/index.md)
  - 英文入口：[`spec/v1/en/index.md`](./spec/v1/en/index.md) 仅供说明；不存在完整英文版，且不承诺提供英文版
  - 机器构件：[`spec/v1/artifacts/`](./spec/v1/artifacts/)
  - **提案（非 normative）**：[`spec/v1/proposals/`](./spec/v1/proposals/) — Arkret Proposal (AKP) 草案，未 accepted 前不构成 wire contract
- 协议站源码：[`site/`](./site/) — Astro Starlight + Scalar(OpenAPI) + 自定义 JSON Schema 渲染器
- 工具：[`tools/`](./tools/) — registry 生成 / lint 流水线

## Layout

```
spec/v1/
├── zh/   en/                      # zh 为 normative prose；en 仅为说明性入口，不是英文版承诺
├── proposals/                     # Arkret Proposals (AKP) — 非 normative
└── artifacts/
    ├── registry/                  # contract-registry (canonical) + 派生 view
    ├── profiles/                  # conformance-profiles.json
    ├── schemas/                   # JSON Schema *.schema.json
    ├── openapi/                   # arkret-service-api.openapi.yaml
    ├── bindings/                  # 非 HTTP transport binding
    └── fixtures/                  # conformance fixtures
site/
└── ...                            # 协议站（pnpm 项目）
tools/
├── artifact_pipeline.py           # registry 生成 / drift check
└── artifact_lint/                  # 分域的跨构件 + Markdown 一致性 lint 包
```

### 手动 fixture 再生成器

以下脚本不在 CI 流水线内，只在对应 fixture 的输入变化时手动运行；它们是各自 fixture
唯一的再生成路径，**不得**按“无调用者”删除：

| 脚本 | 产出 |
| --- | --- |
| `tools/regenerate_crypto_signature_fixture.py` | `spec/v1/artifacts/fixtures/crypto-signature-fixture.json` 的 canonical bytes、digest 与真实 Ed25519 / ES256 / ML-DSA-65 签名，并同步 `websocket-binding-fixture.json` 内嵌的 event frame。需要 `cryptography` 与支持 ML-DSA-65 的 `openssl`（3.5+）。 |

其余 `generate_*` / `regenerate_*` 脚本在其产出 fixture 的 `generated_by` 字段中自行登记。

## 规范权威层级

- `spec/v1/artifacts/registry/contract-registry.json` 是 event/schema/id/operation contract 的 canonical catalog。
- `spec/v1/artifacts/registry/event-kind-registry.json`、`schema-registry.json`、`id-kind-registry.json`、`operation-registry.json` 是从 canonical catalog 生成的机器视图；实现、SDK、lint 应消费这些生成物，不要手抄 Markdown。
- `spec/v1/artifacts/registry/error-code-registry.json` 是标准 service error 的 canonical registry。
- `spec/v1/artifacts/openapi/arkret-service-api.openapi.yaml` 是 HTTP/OpenAPI binding shape。
- `spec/v1/artifacts/profiles/conformance-profiles.json` 是实现 profile 的机器矩阵。
- `spec/v1/zh/**/*.md` 主要承担解释、边界说明和阅读路径；除明确标注"生成视图"外，不再手工维护穷尽清单——这部分由协议站组件运行时从 catalog 渲染。

任何 `spec/v1/zh/` 与 canonical artifact 的漂移都是规范 bug。对 event / schema / id / operation / error / profile wire contract，实现 MUST 跟随 active 机器 registry / schema；对 reducer、authorization、privacy、security、deployment 语义，实现 MUST 跟随中文 normative 文本。

## Public v1 artifact

`spec/v1/artifacts/registry/contract-registry.json` 是当前工作树的 canonical catalog。
`site/public/v1/contract-registry-1.0.0-candidate.json` 是当前 `v1.0.0-candidate` release tag
对应且唯一受版本控制的 public catalog snapshot。
仓库不同时维护 rc / stable 两套 public catalog；`tools/artifact_pipeline.py generate`
只刷新这个当前 v1 snapshot，`check` 用 count/hash gate 证明它与 canonical catalog 一致。

## Maintenance pipeline

```
python tools/artifact_pipeline.py generate   # 重新生成派生 registry view
python tools/artifact_pipeline.py check      # drift 检查 + lint
```

CI: [`.github/workflows/artifact-lint.yml`](./.github/workflows/artifact-lint.yml)

## 站点

```
cd site
pnpm install
pnpm run dev       # http://localhost:4321
pnpm run build     # 静态产物 site/dist/
```

详见 [`site/README.md`](./site/README.md)。
