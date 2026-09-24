<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="./site/public/brand/arkret-logo-dark.svg" />
    <img src="./site/public/brand/arkret-logo.svg" alt="Arkret logo" width="160" />
  </picture>
</p>

# Arkret Spec

Arkret v1 是面向个人、组织与 AI Agent 的去中心化协作协议：各方可以自托管服务并跨域联邦协作，
以 Realm / Circle / Agent Sidecar 划分访问与 MLS 端到端加密边界，同时把聊天、任务、文档、日历和通话
统一为可由不同客户端投影的开放协作模型。仓库同时承载 **规范本体** 和 **协议站源码**。

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
- 协议站源码：[`site/`](./site/) — Astro Starlight + Scalar(OpenAPI) + 自定义 JSON Schema 渲染器
- 工具：[`tools/`](./tools/) — registry 生成 / lint 流水线

## Layout

```
spec/v1/
├── zh/   en/                      # zh 为 normative prose；en 仅为说明性入口，不是英文版承诺
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
| `tools/regenerate_crypto_signature_fixture.py` | 从各 KAT 的 `binding_object` 重算 `spec/v1/artifacts/fixtures/crypto-signature-fixture.json` 的 canonical binding bytes、digest、JWS signing input 与确定性 Ed25519 / ES256 / ML-DSA-65 签名，并刷新九个算法负例。需要 `cryptography` 与支持 ML-DSA-65 的 `openssl`（3.5+）。支持 `--check`。 |
| `tools/generate_hash_transition_fixture.py` | `spec/v1/artifacts/fixtures/hash-transition-fixture.json` 的 SHA-256/BLAKE3 Event、state、control、completeness 与 Seal digest。需要 Python `blake3` 包。 |
| `tools/regenerate_sdk_conformance_claim.py` | 从完整 `sdk_conformance_contract` 重算 `sdk-conformance-claim-fixture.json` 正例的 `contract_digest`，并用 `franking-proof-transcript-fixture.json` 已发布的 conformance Ed25519 seed 重签；负例保持不变。支持 `--check`。 |

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

`tools/release-tool-manifest.json` 是 artifact/release gate 唯一可执行清单；runner 代码只实现其中已登记的
`check_id`，漏 runner、未登记 runner、重复或不存在的 owner script 都会 fail closed。普通与 strict release
模式也由该 manifest 选择，CI 不另存第二份步骤表。

CI: [`.github/workflows/artifact-lint.yml`](./.github/workflows/artifact-lint.yml)

## 变更说明义务

删除或替换 canonical 机器契约、fixture，或摘除 `tools/artifact_lint/runner.py`
阶段调用表里的任何一道门禁时，提交正文 MUST 逐项列出：

1. **被撤掉的对象**：契约 / fixture / 门禁的具体名字，不能只写"清理"或只宣传同一提交里的新增物；
2. **原因**：为什么这个对象不再成立；
3. **验收继任者**：这条义务此后由哪个门禁、fixture 或 vector 承担；
   若该义务本身正式作废，说明依据，并确认没有 registry 条目仍指着它。

触发条件是**契约影响**，不是删除行数：摘掉阶段调用表里的两行也会移除一道完整门禁，
而机械生成物的大量删行按契约类别概括即可。这是贡献流程约定，不新增协议 MUST，
也不追改历史提交。

背景：`c473e3c4` 一次提交删掉两份 fixture（6308 行）并摘掉两行阶段注册，
提交说明只讲同批新增的三个脚本；两个 `check_*` 函数留在 `fixtures.py` 里无人调用，
其中一个守护的十项安全证据义务随之静默消失，而测试全绿。
`tools/test_lint_check_reachability.py` 现在会让"摘线但留函数"直接变红，
但它证明不了删除**是否被说明过**——那由本节负责。

## 站点

```
cd site
pnpm install
pnpm run dev       # http://localhost:4321
pnpm run build     # 静态产物 site/dist/
```

详见 [`site/README.md`](./site/README.md)。
