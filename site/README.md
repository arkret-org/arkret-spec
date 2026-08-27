# Arkret Spec Site

Astro Starlight 站点，把 `spec/v1/` 渲染成可浏览的协议规范网站。

## 设计要点

- 内容源直接读 `../spec/v1/{zh,en}/` 与 `../spec/v1/artifacts/`，**不复制、不镜像**。
  内容路径由 `src/content.config.ts` 通过 `docsLoader({ generateId })` 重写：
  `spec/v1/zh/sync/client-sync.md` → 路由 `/zh/v1/sync/client-sync/`。
- Markdown / MDX 内容通过 Astro Starlight content loader 读取；页面标题以已有
  frontmatter 或内容元数据为准。当前自定义 remark 插件只负责 Mermaid block 与相对
  Markdown 链接归一化。
- 机器构件（registry / schema / openapi / fixtures）通过 `src/lib/artifacts.ts`
  在构建期由 `import.meta.glob` 全部 eager-import，全静态 bundle，无运行时 fetch。
- 自定义 MDX 组件使每个 spec 页面都能引用 catalog 条目，构建期校验 prop 必须命中
  registry，否则直接构建失败：

  ```mdx
  <EventKind name="ak.message.create" />
  <EventKindTable category="message" />
  <ErrorCode code="schema_violation" />
  <ErrorCodeTable scope="both" />
  <OperationRef id="ak.events.submit" />
  <OperationTable tier="core" />
  <ProfileMatrix kind="implementation" />
  <SchemaViewer schema="ak.schema.event_envelope.v1" expand={2} />
  <Fixture name="encoding-fixture" path="vectors[0]" />
  <OpenAPIRef />
  ```

- OpenAPI 在 `/openapi/` 用 [Scalar](https://github.com/scalar/scalar) 渲染。
  内文 `<OperationRef>` 链接 deep-link 到 `/openapi/#operation/<operationId>`。

## 路由

| URL | 内容 |
| --- | --- |
| `/` | 首页 + catalog 概览 |
| `/zh/v1/...` | 中文 normative 全文（`spec/v1/zh/...`） |
| `/en/v1/...` | 英文说明性入口（非 normative）；目前只有 `en/index.md` 是英文页面，不存在完整英文版，且不承诺提供英文版 |
| `/openapi/` | Scalar OpenAPI 视图 |
| `/catalog/event-kinds/` 与 `/[kind]/` | event_kind 目录 + 详情 |
| `/catalog/errors/` 与 `/[code]/` | 错误码目录 + 详情 |
| `/catalog/operations/` 与 `/[id]/` | operation 目录 + 详情 |
| `/catalog/profiles/` 与 `/[id]/` | conformance profile 目录 + 详情 |
| `/catalog/schemas/` 与 `/[id]/` | JSON Schema 目录 + viewer |

## 本地开发

```
cd site
pnpm install
pnpm run dev          # http://localhost:4321
pnpm run build        # 静态产物 -> site/dist
pnpm run check        # astro + ts type check
pnpm run crossref     # 校验 spec/ 中所有 <EventKind/> <ErrorCode/> 等 prop 命中 registry
```

## 关键文件

```
site/
├── astro.config.mjs                 # Starlight + remark plugin + i18n
├── plugins/
│   ├── remark-mermaid.mjs
│   └── remark-rel-md-links.mjs
├── scripts/
│   ├── crossref-check.mjs           # 预构建校验
│   └── gen-public-catalog.mjs       # prebuild/predev 生成对外发布的 registry 快照
├── src/
│   ├── content.config.ts            # docsLoader 指向 ../spec/
│   ├── lib/
│   │   ├── artifacts.ts             # 全局构件加载器（typed）
│   │   ├── site-meta.ts             # release tag / 仓库 URL 等站点元数据适配
│   │   └── schema/
│   │       ├── types.ts             # JSON Schema 子集
│   │       ├── deref.ts             # $ref / JSON pointer 解析
│   │       └── walk.ts              # schema -> SchemaRow 树
│   ├── components/                  # MDX / catalog 组件
│   ├── pages/
│   │   ├── index.astro
│   │   ├── 404.astro
│   │   ├── ecosystem.astro
│   │   ├── openapi.astro            # Scalar
│   │   ├── artifacts/               # 构建期暴露的构件 JSON 路由
│   │   └── catalog/                 # 5 个动态路由集
│   └── styles/
│       ├── spec.css
│       └── marketing.css            # 首页 / ecosystem 等营销页样式
└── tsconfig.json
```

## 演进

- 多版本：将来加 `spec/v1.1/zh/`，`docsLoader` 自动收录为 `/zh/v1.1/...`。
- 英文：`spec/v1/en/index.md` 仅用于说明性入口；除非未来另行接受新的语言政策提案，否则不得把 `/en/v1/...` 页面当作英文 normative mirror 或完整英文版发布。
- 新构件类型：在 `src/lib/artifacts.ts` 加 typed 入口 + 在 `src/components/` 加组件 +
  在 `src/pages/catalog/` 加 index/[param] 路由。crossref 脚本只需在 `checks` 数组里加一行。
