# contrix-spec TODO

> 整理日期: 2026-05-07
> 范围: Contrix v1 normative spec、machine-readable artifacts、协议站。
> 当前事实源: `spec/v1/zh/` + `spec/v1/artifacts/` + `tools/artifact_pipeline.py`。

## 当前状态摘要

- `python tools/artifact_pipeline.py check` 当前通过: 110 event kinds、34 schemas、36 typed ID kinds、83 operations、48 profiles。
- `v1.0.0` 已作为稳定基线写入 `CHANGELOG.md`，active wire contract 以 `spec/v1/artifacts/registry/contract-catalog.json` 和派生 registry 为准。
- 规范文本已迁到 `spec/v1/zh/`；根目录和下游仓库中的协议源引用已经同步到当前路径。
- 协议侧开放项以后统一写入本文件。

## 标记说明

- `[ ]` 未完成
- `[~]` 部分完成 / 等下游或外部决策
- `[x]` 已完成，保留为短 changelog
- `🅿` parallel-safe: 单文档 / 单 artifact / 单 site 页面
- `🔒` sequential: 改 canonical registry/schema/profile，会触发下游同步
- `⚠` high-risk: wire contract / conformance profile / 发布边界变更

## P0 · 规范源一致性（2026-05-07 复审）

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| R1 🔒 | `[x]` | 修复 registry 中残留的 `../zh/sync/contrix-service-api.openapi.yaml` 路径 | `spec/v1/artifacts/registry/contract-catalog.json#operation_registry.generated_views`、生成视图 `operation-registry.json` | OpenAPI 已迁到 `artifacts/openapi/`，但 `operation_registry.generated_views[1].file` 仍指向旧的 `../zh/sync/contrix-service-api.openapi.yaml`（已不存在）。改为 `openapi/contrix-service-api.openapi.yaml`，再 `python tools/artifact_pipeline.py generate` 同步派生视图。 |
| R2 🔒 | `[x]` | 修正 `service-api-schema` 文件扩展名 | `spec/v1/artifacts/registry/contract-catalog.json`、`spec/v1/zh/sync/service-api-schema.mdx` 自指、`spec/v1/zh/sync/transport-bindings.md`、`spec/v1/zh/sync/service-http-binding.md`、`spec/v1/zh/spec-map.md`、`spec/v1/zh/conformance/conformance-suite.md` | 实际文件是 `service-api-schema.mdx`（含 `<OperationTable />` 组件），但 catalog `generated_views[2].file`、prose 和 spec-map 仍写 `service-api-schema.md`。统一改为 `.mdx`，让 GitHub 链接、`lint_artifacts.py` 链接检查与 spec-map 一致。 |
| R3 🅿 | `[x]` | 删除 `service-http-binding.md` 表格中重复的 `federation.md` | `spec/v1/zh/sync/service-http-binding.md` §2.1 命名空间表 `/federation/*` 行 | `规范文件` 列写成 `` `federation.md`、`federation.md` ``，是 `federation-wire.md` 合并到 `federation.md` 后未去重的残留。改为单一 `federation.md`。 |
| R4 🅿 | `[x]` | 清理 `conformance-profiles.md` 末尾的"中文镜像"措辞 | `spec/v1/zh/conformance/conformance-profiles.md` §20 | 文中两处 `(见 .../*.json 与中文镜像)` 是当 fixture 同时存在 `artifacts/` 与 `zh/conformance/fixtures/` 时的引用。`zh/conformance/fixtures/` 已删除，`artifacts/fixtures/` 是唯一来源；保留"中文镜像"会误导读者去找已不存在的镜像。直接改为 `(见 artifacts/fixtures/*.json)`。 |
| R5 🅿 | `[x]` | 重写 `spec/v1/zh/conformance/README.md` | `spec/v1/zh/conformance/README.md` | 该 README 仍声称"本目录中的 `schemas/` 与 `fixtures/` 是根目录 `artifacts/` 的镜像副本…镜像路径清单由 `artifacts/registry/mirror-manifest.json` 统一声明"。事实上 `zh/conformance/` 下没有 `schemas/`、`fixtures/` 子目录，`artifacts/registry/mirror-manifest.json` 已不存在，`artifact_pipeline.py` 也没有 `sync` 子命令。改写为：本目录只承载 normative prose；canonical machine artifact 在 `spec/v1/artifacts/`；管线只有 `generate` / `check`。 |
| R6 🅿 | `[x]` | 校正 `spec/v1/artifacts/README.md` 的管线与 mirror 描述 | `spec/v1/artifacts/README.md` | §1.1 列出 `artifacts/registry/mirror-manifest.json` 与"`zh/` 与工件文件镜像关系"——文件不存在。§2 依然写 `python tools/artifact_pipeline.py sync`，pipeline 只剩 `generate` / `check`。§2 描述 `check` 三层校验时提到"镜像漂移"，已废弃。改写为当前真实 layout（canonical / generated 二分；pipeline 只有两个子命令；lint 校验注册表交叉引用 + Markdown 链接 + 选定完整对象示例的 schema required-field drift）。 |
| R7 🅿 | `[x]` | 修正 `release-readiness.md` "mirror lint" 表述 | `spec/v1/zh/overview/release-readiness.md` §2 | 第二段"`zh/` 与 `artifacts/` 的 registry / schema / mirror lint 必须通过"中的 `mirror lint` 已经不存在；当前 lint 是 registry / schema / Markdown 引用 / OpenAPI shape lint。改为现行表述。 |
| R8 🅿 | `[x]` | 刷新 CHANGELOG 模板对 `pipeline sync` 的引用 | `CHANGELOG.md` v1.1+ 变更登记模板 | 模板中"派生 artifact 同步"列写 `tools/artifact_pipeline.py sync`，但 pipeline 只剩 `generate`。改为 `tools/artifact_pipeline.py generate` 并明确 lint 漂移由 `check` 检测。 |
| R9 🅿 | `[x]` | 校正 `artifact_pipeline.py` docstring 中关于 `service-api-schema.md` 的描述 | `tools/artifact_pipeline.py` 文件头 docstring | 文件头注释提到"rewrite generated markdown tables inside zh/sync/service-api-schema.md"——文件实际是 `.mdx`，且 markdown 表格生成逻辑已删除。把后一句改成准确描述（"site renders machine artifacts directly via MDX components"）。 |

## P1 · 协议站（site）改进（2026-05-07 复审）

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| W1 🅿 | `[x]` | 修复 `astro check` 6 个 TS 报错 | `site/src/components/Header.astro`、`site/src/components/SiteNav.astro` | `Cannot find module 'virtual:starlight/...'` × 4 个：在 `site/src/env.d.ts` 中新增 Starlight 虚拟模块的 type reference。`SiteNav.astro:54` 的 `aria-current={isActive(item.href) ...}` 在 `item.soon` 分支下 `item.href` 是 `undefined`：把签名收紧或在 nav 项 narrow `href` 类型。 |
| W2 🅿 | `[x]` | 替换占位仓库 URL `your-org` | `site/src/pages/openapi.astro:9`、`site/src/pages/catalog/event-kinds/[kind].astro:31` | 两处都是 `https://github.com/your-org/contrix-spec/...` 占位链接，正式 GitHub URL 在 `MarketingLayout.astro` 已写为 `https://github.com/contrix-dev/contrix-spec`。统一抽到 `site/src/lib/site-meta.ts`（或 lib/artifacts.ts）做单一来源，让所有 catalog 详情页的 "view canonical row on GitHub" 链接共用同一 base。 |
| W3 🅿 | `[x]` | catalog 详情页补全 "back to index" 与 source link | `site/src/pages/catalog/{event-kinds,errors,operations,profiles,schemas}/[*].astro` | 现状各详情页只有标题 + 数据，没有"返回 catalog 列表"导航。统一加面包屑或顶部 `← Event kinds` 链接；同时把 `Source` 段（catalog row / generated view）抽成共用 `<CatalogSource>` 组件，复用 W2 的 GitHub base URL。schemas / operations / profiles / errors 详情页也补 source 段（目前 errors 页只有一段最小 "canonical row" 文字，没有 GitHub deep link；profiles 页没有 source 段）。 |
| W4 🅿 | `[x]` | 首页 stats `48 profiles` 与实际 implementation+deployment+vector+hardening 之和不一致排查 | `site/src/pages/index.astro` `stats` 数组 | profile 总数算的是 `implementation_profiles.length + deployment_profiles.length + hardening_profiles.length + vector_profiles.length`（17+6+10+3=36），但 release-readiness、artifact_pipeline check 都说"48 profiles"。差额是 `profile_requirements` block 数 + extension profiles。`crossref-check` 报 36，`artifact_pipeline.py profile_summary_text` 报 17/6/10/3 + 38 requirement blocks，`lint_artifacts.py` 显示 48 profiles。统一首页 stats 计数方式与 readiness 表对齐。 |
| W5 🅿 | `[x]` | OpenAPI 视图主题与站点主题对齐 | `site/src/components/OpenAPIRef.astro` | `OpenAPIRef` config 写死 `darkMode: false`，与站点 dark/light 切换不联动；用户在 dark 主题下进 `/openapi/` 看到亮色 Scalar 面板，体验割裂。改为根据 `document.documentElement.dataset.theme` 动态设置 Scalar `darkMode`（监听 `storage` 与 `data-theme` 变化）。 |
| W6 🅿 | `[x]` | 站点 SEO / OG meta 用英文双开关 | `site/src/layouts/MarketingLayout.astro` | 默认 title `"Contrix · 去中心化协作协议"`、description 全是中文。SEO / 社交分享在英文场景下表现差。增加 i18n title/description（中文 + 英文 fallback）。 |
| W7 🅿 | `[x]` | 首页 "v1.0.0 stable baseline" eyebrow 与 catalog version 同源 | `site/src/pages/index.astro` 的 hero eyebrow | hero eyebrow 把 "v1.0.0 stable baseline" 字符串硬编码；catalog version 已经从 `contractCatalog.version` 读。 把 v1.0.0 也抽到 `lib/site-meta.ts`（与 W2 共用），后续升 v1.0.1 / v1.1 时只改一处。 |
| W9 🅿 | `[x]` | catalog operations index 加 surface group 速跳 | `site/src/pages/catalog/operations/index.astro` | 当前 `OperationTable` 整页输出（83 个 operation 分 13 个 surface group），没有页内导航。加一个 sticky 侧边或顶端的 surface tag list（每个 surface group `<a href="#surface-name">`）或 jump-to-surface 下拉。 |
| W10 🅿 | `[x]` | 首页 hero CTA 与 docs 入口对齐 | `site/src/pages/index.astro` | 当前 CTA "阅读规范" 指向 `/zh/v1/`（spec/v1/zh/index.md），不是真正的总目录。改 "阅读规范" 指向 `/zh/v1/spec-map/`，更适合"开始阅读"。 |
| W11 🅿 | `[x]` | catalog event-kinds index 加分类筛选 | `site/src/pages/catalog/event-kinds/index.astro` + `EventKindTable.astro` | 110 个 event kind 全列在一张表里，缺乏 category / wire_scope filter。增加按 category（space / flow / message / member / capability / ...）的 anchor link 或 client-side filter，提高可浏览性。 |

## P2 · v1.1+ profile 与扩展面（沿用上一轮）

| # | 状态 | 任务 | 文件 | 并行性 |
|---|---|---|---|---|
| P1 🅿 | `[x]` | `did:webvh` high-trust profile 文本化 | `spec/v1/zh/identity/identity-did.md` §3.3、`conformance-profiles.json` `cx.profile.org_high_assurance_identity.v1` | profile 已注册为 `identity_extension_profiles`，`did:webvh_witness` / `did:webvh_watcher` 列入 optional_extensions，`history_bearing_did_method` 是必需 feature；prose §3.3 描述 SCID / entry hash chain / controller proof 验证要求。 |
| P2 🅿 | `[x]` | non-HTTP binding profile 发布边界 | `spec/v1/zh/sync/transport-bindings.md`、`spec/v1/artifacts/bindings/non-http-bindings.yaml` | core 锁定 HTTP/JSON 为 normative；gRPC / WS / SSE / MQ / libp2p 全部声明为 v1.1+ extension binding；`non-http-bindings.yaml` 顶部声明 v1.1+ extension reference 状态。 |
| P3 🅿 | `[x]` | Applet / Agent / MIMI extension conformance profile 明确化 | `conformance-profiles.json` `profile_tiers.v1_1_extension_implementation` | `cx.profile.applet_service.v1` / `cx.profile.agent_runtime.v1` / `cx.profile.mimi_interop.v1` 已列入 v1.1+ extension tier，并在 `tier_rules` 中说明可选性与外部标准成熟后替换路径。 |
| P4 🅿 | `[x]` | CBOR deterministic encoding extension profile | `spec/v1/zh/conformance/encoding.md` §2.1、`conformance-profiles.json` `encoding_extension_profiles` | `cx.profile.encoding.cbor.v1` 已注册为 encoding extension profile；core v1 仍以 canonical JSON 为唯一 normative encoding。 |
| P5 🔒 | `[x]` | constraint family 下游迁移注记 | `spec/v1/zh/authz/constraint-schema.md` §3 | §3 包含完整 v0→v1 family 命名映射（`approval_workflow` → `claim_based{subtype=approval}` 等）以及 14→8 收敛说明；下游 SDK / cotest 用此段翻译既有 grant。 |

## P3 · 协议站与发布质量（沿用上一轮）

| # | 状态 | 任务 | 文件 | 说明 |
|---|---|---|---|---|
| Q1 🅿 | `[~]` | 英文 normative 发布策略 | `spec/v1/en/index.md`、site | 现状: `spec/v1/en/index.md` 声明英文 normative "not yet published"，请读者回退到中文 + artifacts。仍需正式决定: 隐藏 `/en/` 路由、保留 placeholder + preview 标签，或安排 v1.0 英文版翻译。决定后再更新本条。 |
| Q2 🅿 | `[x]` | site crossref / schema rendering gate | `.github/workflows/site.yml` | PR gate 已固定 `npm run check` + `npm run crossref` + `npm run build`，并把 `site/dist` 上传为 artifact；任一步失败会阻塞合并。 |
| Q3 🅿 | `[x]` | release-readiness 页面同步 artifact 计数 | `spec/v1/zh/overview/release-readiness.md` §2 | 新增 registry 计数表（110 event kinds / 34 schemas / 36 typed ID / 83 operations / 48 profiles）并要求与 `tools/artifact_pipeline.py check` 输出一致；新增/退役 registry 项 MUST 同步本表。 |

## P0 · 历史已完成（短 changelog）

- `[x]` v1.0.0 registry / schema / fixture artifact lint 当前通过。
- `[x]` active wire contract 已迁到 `spec/v1/artifacts/`，root `artifacts/` 仅为历史目录/兼容残留。
- `[x]` 2026-05-07 整批: S1-S4、P1-P5、Q2-Q3 全部完成；CHANGELOG 增加 v1.1+ 变更登记模板与 actor_profile + gatekeeper 收尾段；release-readiness 增加 registry 计数表；spec-map / release-readiness 修复失效路径。Q1 仍待英文发布策略决策。
- `[x]` 2026-05-07 复审批次（R/W 系列）: contract-catalog 中残留的 `../zh/sync/...` 派生视图路径修正为 `openapi/`、`service-api-schema.mdx`，并通过 `python tools/artifact_pipeline.py generate` 同步派生视图；prose / spec-map / conformance-suite 中 `service-api-schema.md` 全部改为 `.mdx`；`service-http-binding.md` `/federation/*` 行去重 `federation.md`；`conformance-profiles.md` §20 移除"中文镜像"措辞；`spec/v1/zh/conformance/README.md` + `spec/v1/artifacts/README.md` 重写为当前 layout（不再提 `mirror-manifest.json` 或 `pipeline sync`）；`release-readiness.md` "mirror lint" 表述改为 `artifact_pipeline.py check`；CHANGELOG 模板把 `pipeline sync` 改为 `pipeline generate`；`artifact_pipeline.py` docstring 校正。site 侧: 新增 `lib/site-meta.ts` 集中托管 GitHub URL 与发布 tag、新增 `Header` `Props` 类型 + `env.d.ts` 让 `astro check` 0 error；catalog 详情页加面包屑 + `<CatalogSource>`；首页 stats Profiles 改用 `totalProfileCount` 与 readiness 48 对齐；hero CTA "阅读规范" 改指向 `/zh/v1/spec-map/`；OpenAPI Scalar 主题改为跟随 `data-theme` 同步；marketing layout title/description 增加英文 fallback；operations index 加 surface 跳转导航；event-kinds index 按 category 分块。最终验证: `python tools/artifact_pipeline.py check`、`npm run check`、`npm run crossref`、`npm run build` 全部通过（431 页）。

## 跨项目登记

跨项目执行项不在本文件展开，统一放根 [`../_todos.md`](../_todos.md)。本文件只保留协议源自身需要完成的工作。
