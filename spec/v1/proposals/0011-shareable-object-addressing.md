---
ckp: CKP-0011
title: Shareable Object Addressing — web+cokret URI scheme & deep-link resolution
normative: false
stability: v1
updated: 2026-05-28
status: accepted
created: 2026-05-28
authors:
  - chris@acroidea.com
depends_on: [CKP-0007]
merged_into: spec/v1/zh/discovery/object-addressing.md
---

> **Status: accepted, merged into v1 normative spec on 2026-05-28.**
>
> Normative entry point: [`spec/v1/zh/discovery/object-addressing.md`](../zh/discovery/object-addressing.md)。Operation 注册见 [`contract-catalog.json`](../artifacts/registry/contract-catalog.json#operation_registry) 的 `ck.find.directory.query.resolve_target`(`POST /directory/resolve-target`),OpenAPI binding 与 `operations-error-mapping.json` 已同步。CHANGELOG 条目在 2026-05-28 下。
>
> 合入时对 §6 open questions 的最终决议见 §6（已逐条标注 RESOLVED）。本文件保留为历史设计 rationale；Object Addressing 的后续变更 MUST 落到 normative 文件,不在此处。

## 1. Summary

定义一套**客户端无关的可分享对象地址**,让用户可以把一个 Strand(或 Strand 内某条 Message、或 Realm)通过一串链接分享出去,接收方任意 Cokret 客户端都能解析并在自己 UI 里打开。

核心是把三件被混淆的东西分层:

- **逻辑地址 grammar**(已存在的 `ck:strand:<uuid>` 等不透明 id,不动);
- **可注册 URI scheme `web+cokret:`**(app-to-app / "在 App 打开");
- **HTTPS 落地链接**(matrix.to 模型,用户真正复制粘贴的那串,fragment-based)。

地址层**纯寻址**;授权永远是挂在纯地址上的、可吊销、有 expiry 的签名 token,分 `reference` / `preview` / `invite` 三型。寻址 ≠ 授权:裸地址解析仍受 [`discovery-directory.md`](../zh/discovery/discovery-directory.md) 三 gate 约束,看不见的资源解析成 `not_found`。

非目标:本提案**不**引入新对象、新 event、新 capability,也**不**改变任何 wire / reducer 行为。它是 client-facing 寻址契约 + 一个新 directory resolve operation。

## 2. Motivation

### 2.1 现状只到 Realm 级,没有对象级深链

[`discovery-directory.md` §9](../zh/discovery/discovery-directory.md) 已有 `ck.find.directory.resolve_realm`,接受 `realm_id | alias | invite_token | signed_link`,并返回 `via_services`(host Principal Server service DID)——这正是 Matrix `matrix.to` 里 `?via=` 路由提示的等价物。**但它只解析到 Realm**:没有"分享某个具体 Strand / Message"的对象级入口。

`ck:strand:<uuid>` 是全局唯一 UUIDv7,但**不可路由**:光有 strand_id 不知道它属于哪个 Realm、由哪台 server 托管。用户要分享一个 Strand,目前只能复制各自客户端的私有 URL(`app.foo.com/strand/…`、`bar://strand/…`),换个客户端就打不开。

### 2.2 外部对照

Matrix 用**三件套**解决同一问题,值得直接借形:

- 逻辑 id:`!room:server` / `$event`(↔ Cokret `ck:strand:` / `ck:message:`);
- 注册 URI scheme:`matrix:roomid/<id>/e/<event>?via=`(↔ 本提案 `web+cokret:`);
- HTTPS 分享页:`https://matrix.to/#/!room:server/$event?via=`(↔ 本提案 HTTPS 落地)。

三者职责不同、不可合并;早期把它们压成一个 scheme 是 Matrix 踩过的坑。

## 3. Specification

### 3.1 地址 grammar(path 表身份,query 表提示)

canonical 形态(`web+cokret:` envelope):

```
web+cokret:realm/<realm>/strand/<strand>/m/<msg>?via=<service_did>&via=<service_did>&action=view
```

| 部分 | 承载 | 规则 |
| --- | --- | --- |
| **path** | containment 链 = 身份 + 解析顺序 | keyword 带类型,值是**裸 uuid**(剥掉 `ck:strand:` sigil)。层级:`realm/<r>` ⊃ `strand/<f>` ⊃ `m/<msg>`。 |
| **query** | 非身份提示 + 授权组件 | `via`(多值,物理路由)、`action`(UI 意图:`view`(默认)/`join`/`reply`)、`lt`(link_type,见 §3.4)、`tok`(授权 token,见 §3.4)。语法上都在 query-suffix,但只有 `via`/`action` 是"删掉不改变目标"的纯提示;`lt`/`tok` 携带授权类别。 |
| **fragment** | 隐私敏感位(仅 HTTPS 形态) | 见 §3.3。 |

层级合法前缀(短到长均可单独成址):

```
web+cokret:realm/<realm>                              # Realm(退化回 resolve_realm)
web+cokret:realm/<realm>/strand/<strand>                  # Strand(reference,无 token)
web+cokret:realm/<realm>/strand/<strand>/m/<msg>          # Strand discussion track 内某条 Message
web+cokret:realm/<realm>/strand/<strand>?via=<did>&lt=invite&tok=<token>   # invite link
```

规则:

- **realm 是身份,进 path;via 是路由,进 query。** realm 脱离 path 则 strand 无法定位(authz/解析以 Realm 为根,见 [CKP-0007](./0007-circle-primitive.md));via 是"此刻哪台 server 托管该 Realm",可增删过期、不影响身份。
- `<realm>` 接受 `realm_id`(裸 uuid)或 **alias**(域名样式)。消歧:含 `.` 且非 UUIDv7 shape → alias;UUIDv7 shape → id。`<strand>` / `<msg>` 只接受裸 uuid。path 内裸 uuid 只是 URI 压缩形态;进入 token target descriptor 前,解析方 **MUST** 按 path keyword 重建 typed canonical ID(`ck:realm:<uuid>` / `ck:strand:<uuid>` / `ck:message:<uuid>`)。alias 只作为解析输入形态;带 token 的地址在验 token 前 **MUST** 先按常规 Realm 解析路径(必要时使用 `via`)解析出 canonical `realm_id`,后续 target digest 一律绑定 `realm_id` 而不是 alias 字符串。
- Strand / Message 地址 **MUST** 携带 `realm/<realm>` + 至少一个 `via`;两者缺一,解析方 fail-closed(不做全网 strand_id 猜测)。
- **未知 path keyword fail-closed**:v1 合法 keyword 只有 `realm` / `strand` / `m`,且层级顺序必须是 `realm` ⊃ `strand` ⊃ `m`。解析方遇到未注册 keyword、顺序错乱或缺中间层级时 **MUST** 返回 `not_found`,不得猜测。未来扩展对象类型(`morph` / `space` / `circle` 等)**MUST** 显式扩 keyword 表;旧客户端遇到新 keyword 一律按 fail-closed 处理,保证 forward-compat 下不分叉。
- **Token wire syntax(normative)**:授权组件**统一**用两个参数,**禁止** `invite_token=` / `signed_link=` 等分叉参数名(消除客户端生成互不互通链接):
  - `lt=<reference|preview|invite>`,省略等价 `reference`;
  - `tok=<opaque-token>`,**当且仅当** `lt ∈ {preview, invite}` 出现;直接映射到 `resolve_target.token`。
  - token 的内部类别(preview grant / invite / signed_link 风格)由签名 payload 内的 `link_type` 承载(§3.4),不靠参数名区分。
  - `tok` 位于 query-suffix,因此在 HTTPS envelope 下随整串落进 fragment(§3.3),自动满足"token MUST 在 fragment";`web+cokret:` 原生 handler 形态同样把它留在 query-suffix。
  - token 存在时**权威 link_type 取自 token 签名 payload**;URL `lt` 仅是解析前展示 hint,**MUST NOT** 用于放大权限,与 token 内 `link_type` 矛盾时以 token 为准。
- Circle-scoped Strand(`Strand.scope_circle_id != null`)的地址形态**不**额外暴露 circle id:scope 由解析后的访问判定决定,地址层不泄露 Circle 存在性(见 §3.4)。

### 3.2 三个 envelope,一套 grammar

| Envelope | 形态 | 用途 |
| --- | --- | --- |
| **逻辑 id** | `ck:strand:<uuid>`(不变) | 协议内部 / `resolve_*` 输入;不是 URI,不塞 `?via=`。 |
| **`web+cokret:`** | `web+cokret:realm/…/strand/…?via=…` | "在 App 打开"。原生 app 经 OS 级 handler 直接接收(真·本地,不经任何 web server)。web 客户端经 `navigator.registerProtocolHandler('web+cokret', <https-template>)` 登记——注意 handler 模板的隐私约束见 §3.3。 |
| **HTTPS 落地** | `https://<landing>/#realm/…/strand/…?via=…` | 用户复制粘贴的默认形态;`#` 后整体 = 上面同一 grammar。 |

`web+cokret:` 与 HTTPS 落地共用同一 grammar parser,只是外壳不同(裸接 scheme vs 接在 `#` 后)。

### 3.3 隐私:target 与 token 放 fragment

HTTPS 落地链接中,`strand` / `m` / `via` / 尤其授权 token **MUST** 放在 URL **fragment(`#`)**,不进 path/query。理由:fragment 不发往落地页服务器,服务器日志学不到"谁在打开哪个 Strand",与 [`discovery-directory.md` §11](../zh/discovery/discovery-directory.md) anti-enumeration 立场一致(matrix.to 同款)。

**`web+cokret:` 的隐私边界按 handler 类型分两支(不可笼统说"不经 web server"):**

- **原生 OS 级 handler**:URI 由操作系统直接派发给本地 app,确实不经任何第三方 web server,via / token 留在 query 无泄露风险。
- **web `registerProtocolHandler` handler**:浏览器会**导航到注册的 HTTPS handler 模板 URL**,并把原始 `web+cokret:` URI 作为替换值(`%s`)填入。**若模板把 `%s` 放在 path/query,则 target 乃至 token 会进入 handler 服务端的请求与日志**——这与 §3.3 的隐私目标直接冲突。因此 normative 约束:
  - web handler 模板 **MUST** 把 `%s` 放进**自身 fragment**(例如 `https://app.example/open#%s`),使被替换的 URI 永远落在 fragment、不进服务端;**或**
  - web 客户端干脆**只走 HTTPS fragment 落地页**,把 `web+cokret:` 留给原生/本地 handler,不自行注册 web protocol handler。

### 3.4 Link 类型(寻址 ≠ 授权)

授权**不做成独立 scheme**,而是同一地址 + 一个清晰分型的签名 token 组件(复刻 `resolve_realm` 已有的 `realm_id`(纯) vs `invite_token`/`signed_link`(带授权)输入形状):

| 类型 | 携带 | 解析后效果 |
| --- | --- | --- |
| `reference`(默认) | 纯地址 | 走正常 discovery + access gate;**不授予任何权限**,看不见即 `not_found`。 |
| `preview` | 地址 + preview 授权 token | 可取 stripped preview(title/summary),不能读正文 / join。映射 discovery `preview`。 |
| `invite` | 地址 + `invite_token` / `signed_link` | 兑换后经 [`join-policy.md`](../zh/governance/join-policy.md) 授予 membership/访问;有 expiry、audience-bound、可吊销。 |

**Token 必须绑定 canonical target(normative)**:`preview` / `invite` token 仅有 expiry / audience / 可吊销**不够**——其签名 payload **MUST** 覆盖它授权的具体对象,否则 `resolve_target` 把 `address` 与 `token` 当独立输入时,A 对象的有效 token 会被重放到 B 地址(scope confusion)。具体要求:

- token 签名 payload **MUST** 包含 **target descriptor** + 生命周期字段:
  - **target descriptor** = normalize 后的身份元组 `{realm_id, strand_id?, message_id?}` + `link_type`;等价地可表示为 `target_digest = "sha256:" || hex(sha256(JCS(target_descriptor)))`。`realm_id` / `strand_id` / `message_id` 字段值 **MUST** 使用 typed canonical ID wire form(`ck:realm:<uuid>` / `ck:strand:<uuid>` / `ck:message:<uuid>`),不得使用 path 中的裸 uuid 或 alias 原文。`realm_id` 必须是 Directory 解析后的 canonical Realm ID;若地址 path 中 `<realm>` 是 alias,`resolve_target` 必须先按常规 Realm 解析路径(必要时使用 `via`)完成 alias → `realm_id` 规范化,再计算/比对 digest。alias 解析失败、alias 与 token 绑定的 `realm_id` 不一致、或无法取得 canonical `realm_id` 时,均返回统一 `not_found`。
  - **descriptor canonical shape(确定性,normative)**:`target_descriptor` 是**恰好**如下字段的对象,缺省的层级字段 **MUST 整键省略**(不得写 `null`——避免 JCS 因 `null` vs 省略产生不同 digest):

    ```json
    {
      "realm_id": "ck:realm:<uuid>",
      "strand_id": "ck:strand:<uuid>",        // 仅 strand / message 目标出现
      "message_id": "ck:message:<uuid>",  // 仅 message 目标出现
      "link_type": "preview"              // "preview" | "invite"
    }
    ```

    JCS(RFC 8785)对该对象规范化后取 sha256;白名单外字段 **MUST NOT** 进 digest(与 `claim_digest` 同纪律)。签发端与 `resolve_target` 端 MUST 用同一 shape 与省略规则,否则 digest 不可比对。
  - **target_digest 只覆盖身份 path(`realm` / `strand` / `m`)与 `link_type`**,**MUST NOT** 纳入 `via` / `action` / `tok` / `lt` 或任何其它 query hint(它们按 §3.1 是非身份提示)。后果是确定的:**路由提示刷新或 UI action 改变不使 token 失效**;而换一个 Strand/Message 必然换 digest、token 不可挪用——消除"一端纳入 via、另一端不纳入"导致的两端验签规则分叉。digest 的 JCS + 字段白名单纪律与 [`identity-handles.md` §3.2.1](../zh/identity/identity-handles.md) `claim_digest` 同源。
  - 生命周期字段 `aud` / `exp` / `nonce` 在 token payload 内,但**不属于** target descriptor(它们是 token 自身的有效性边界,不是被寻址对象的身份)。
- `resolve_target` **MUST** 校验 token 的 target descriptor 与请求 `address` 解析出的 canonical 身份 `{realm_id, strand_id?, message_id?}` + 生效 link_type **逐级一致**(等价:重算 `target_digest` 比对);不一致时返回与"无 token / 不存在"**不可区分**的统一 `not_found`,不得只校验 token 自身有效性。

这样 Circle-scoped Strand 自然成立:`reference` link 对非 Circle 成员解析成 `not_found`(不泄露存在性);要让人看见就配 Circle-scoped `invite`,且该 invite token 只对它签发时绑定的那个 Strand/Circle 生效。

### 3.5 解析 operation(草案)

新增 `ck.find.directory.query.resolve_target`,是 `resolve_realm` 的对象级泛化:

| operation_id | 必填 | 可选 | 响应 | 约束 |
| --- | --- | --- | --- | --- |
| `ck.find.directory.query.resolve_target` | `address: string`(canonical grammar) | `requester: did`; `proofs: proof[]`; `token: string`(preview/invite) | `target_kind: enum(realm,strand,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; **以及 §9.1 全部通用字段** | 响应 **MUST** 含 [`discovery-directory.md` §9.1](../zh/discovery/discovery-directory.md) 通用字段(`as_of`、`source_refs`、`via_services`、可选 `policy_revision` / `stale` / `divergent`),让客户端能回真相源验签并判断 stale/divergent;`via_services` v1 normative;复用 `resolve_realm` 的统一 `not_found` blinding;invite/restricted/secret 对未授权请求与不存在不可区分;token 校验见 §3.4。 |

客户端流程:解析 `address` → 取 path 末段 target_kind → 用 `via` + realm path 段解析 Realm 并取得 canonical `realm_id`(沿用 resolve_realm)→ 若有 token,按 §3.4 校验 token target descriptor → 在 Realm 内按 access gate 定位 strand/message → 渲染成本地 UI URL。

## 4. Interactions with normative spec

- **新增 normative 文件**(accepted 后):`spec/v1/zh/discovery/object-addressing.md`(grammar + 三 envelope + 解析契约)。
- **改动** [`discovery-directory.md` §9](../zh/discovery/discovery-directory.md):operation-registry 增 `ck.find.directory.query.resolve_target`;§9.1 `via_services` 语义复用。
- **artifact**:source of truth 是 `contract-catalog.json`(`source_of_truth: true`)——`resolve_target` operation_id 先在此新增;`operation-registry.json` 等 `generated_registries` 由 `tools/artifact_pipeline.py generate` 派生,**不得手工改**。`openapi/cokret-service-api.openapi.yaml`(`POST /_cokret/find/directory/resolve-target`)与 HTTP binding / prose 表是对齐 artifact,需要在同一 accepted patch 中同步更新,再由 `tools/artifact_pipeline.py check` 校验它们与 catalog/registry 一致。`id-kind-registry.json` 若需"address grammar"附注,也应通过 `contract-catalog.json` 的 id-kind source 更新后生成(非新 id kind)。
- **Invite token 生命周期复用**:`invite` token 的签发 / 过期 / 吊销复用 [`join-policy.md`](../zh/governance/join-policy.md) 既有 `invite_token` / `signed_link` 生命周期,本提案**不另发明** revocation 机制;`resolve_target` 在 §3.4 target descriptor 校验通过后,仍 **MUST** 走 join-policy 的 token 有效性 / 吊销检查。`preview` token 的授权与吊销归属属于未决设计点,见 §6。
- **不触碰** event-kind / capability / schema 的 wire 约束;**不需要** forbidden-wire 守卫(没有新 on-wire 字段进对象 / payload)。
- **隐私**:地址 grammar 与 anti-enumeration、Circle 存在性隐私([CKP-0007](./0007-circle-primitive.md))、handle 可迁移原则([`identity-handles.md` §3.8](../zh/identity/identity-handles.md))一致——realm alias 是可迁移 label,历史链接靠 realm_id + via 仍可解析。

## 5. Rationale & alternatives

- **扁平 query(`?realm=&strand=&m=`)被否**:丢失解析顺序信号;跨对象类型扩展需每类型一个 param 名且有歧义;把身份(`strand=`)和提示(`via=`)压到同一句法层,抹掉 §3.4 想要的 identity/hint 边界。层级 path 把 containment 与解析顺序写进语法。
- **裸 `ck:` 作 URI scheme 被否**:浏览器 `registerProtocolHandler` 只允许 `web+` 前缀(或内置安全名单),裸 `ck:` 永远注册不了——而多客户端(含 web PWA)正是本提案前提;且 `ck:strand:019…` 与 id 字面量完全相同会产生歧义;2 字母 scheme IANA 注册基本不可行。`web+cokret:` 丑但几乎不直接露给用户(用户分享 HTTPS 落地链接)。
- **纯路径(via 也进 path)被否**:`via` 真·多值、真·非身份,`/via/<did>/via/<did>` 既丑又混淆物理路由与逻辑身份。
- **只做原生 scheme(`ck://`)被否**:把 web 客户端排除在链接处理之外,违背"客户端无关"目标。原生 app 仍可私下额外认领,但 spec 祝福的互通 scheme 是 `web+cokret:`。

## 6. Open questions（合入决议）

合入 normative 时全部 RESOLVED：

- [x] **Message 锚点 keyword** → **`m/`**(对齐协议层 Message 对象,而非底层 event envelope)。
- [x] **裸 strand link** → **不允许**:Strand / Message 地址强制 `realm/<realm>` + ≥1 `via`,缺则 fail-closed `not_found`。
- [x] **`preview` token** → **v1 不实现,`preview` 保留为 reserved 值**。token 授予 preview 会在 discovery 三 gate 之外新开授权旁路(属新授权原语),超出寻址职责;若未来需要由独立提案定义其与三 gate 的关系。v1 link 类型只有 `reference` + `invite`;`reference` 在 discoverability 已允许时返回 preview,不引入新原语。
- [x] **`resolve_target` vs `resolve_realm`** → **共存**:`resolve_realm` 保留为 realm-only 入口且**不** deprecate;`resolve_target` 解析 realm 目标时 MUST 委托同一 Realm 解析路径,避免语义漂移。
- [x] **HTTPS 落地域名** → **部署方自选**,协议只规范 fragment grammar,不指定中心化落地域名(联邦化原则)。
- [x] **alias-vs-uuid 消歧** → **normative 固化**:`<realm>` 段匹配 UUIDv7 文本形态即 `realm_id`,否则 alias;`<strand>`/`<msg>` 只接受裸 uuid。

## 7. Migration plan

合入步骤(已执行,2026-05-28):

1. 新增 normative `spec/v1/zh/discovery/object-addressing.md`。
2. `contract-catalog.json` 增 `ck.find.directory.query.resolve_target`,`artifact_pipeline.py generate` 生成 `operation-registry.json` 等视图。
3. 同步 `openapi/cokret-service-api.openapi.yaml`、`non-http-bindings.yaml`、`operations-error-mapping.json`,`artifact_pipeline.py check` 验证对齐。
4. `discovery-directory.md` §9 / `service-http-binding.md` §2.3 / `release-readiness.md` / `spec-map.md` 同步行与计数(100 → 101)。
5. CHANGELOG + STATUS_METRICS + 本目录 README 索引更新。

1. 落 `spec/v1/zh/discovery/object-addressing.md` normative。
2. 在 `contract-catalog.json`(source of truth)增 `resolve_target`,再跑 `tools/artifact_pipeline.py generate` 生成 `operation-registry.json` 等 generated registry view。
3. 同步补 `openapi/cokret-service-api.openapi.yaml`、HTTP binding/prose 表与必要 conformance profile 引用,再跑 `tools/artifact_pipeline.py check` 验证 catalog / registry / OpenAPI 对齐。
4. 在 `discovery-directory.md` 交叉引用新文件。
5. CHANGELOG + STATUS_METRICS 更新。

## 8. References

- [CKP-0007](./0007-circle-primitive.md) — Circle scope / 存在性隐私(本提案 `depends_on`)。
- [`discovery-directory.md` §9](../zh/discovery/discovery-directory.md) — `resolve_realm` / `via_services` / anti-enumeration。
- [`identity-handles.md` §3.8](../zh/identity/identity-handles.md) — handle/alias 可迁移、DID-sealed 寻址原则。
- Matrix `matrix:` URI scheme(MSC2312)与 matrix.to 三件套设计。
- WHATWG HTML `registerProtocolHandler` `web+` scheme 安全名单。
