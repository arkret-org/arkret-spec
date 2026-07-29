---
title: Object Addressing & Shareable Links
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 的**客户端无关可分享对象地址**：用户把一个 Strand（或 Strand 内某条 Message、或 Realm）通过一串链接分享出去，接收方的任意 Arkret 客户端都能解析并在自己 UI 里打开。

它解决的具体问题：`ak:strand:<uuid>` 是全局唯一 UUIDv7，但**不可路由**——光有 strand_id 不知道它属于哪个 Realm、由哪台 server 托管，因此各客户端只能各自拼私有 URL，换个客户端就打不开。

地址层**只负责寻址**。授权不是地址的一部分，而是挂在地址上的、有 expiry、audience-bound、可吊销的签名 token。**寻址 ≠ 授权**：裸地址解析仍受 [`discovery-directory.md` §2/§3](./discovery-directory.md) 的 discoverability / join / history 三 gate 约束，请求方看不见的资源 MUST 解析为与不存在不可区分的 `not_found`。

本文定义一套地址 grammar、三种 envelope，以及解析 operation `ak.find.directory.query.resolve_target`。v1 的 preview link type 依赖 Realm 侧 `ak.realm.preview_policy`，但地址层本身仍不授予 membership 或写权限。

## 2. 三个 envelope，一套 grammar

| Envelope | 形态 | 用途 |
| --- | --- | --- |
| **逻辑 ID** | `ak:strand:<uuid>`（不变） | 协议内部 / `resolve_*` 输入。它是不透明 ID，不是 URI，**MUST NOT** 携带 `action` / token。 |
| **`web+arkret:` URI scheme** | `web+arkret:realm/…/strand/…?action=view` | "在 App 打开"。原生 app 经 OS 级 handler 直接接收；web 客户端经 `navigator.registerProtocolHandler('web+arkret', <https-template>)` 登记（约束见 §5）。 |
| **HTTPS 落地链接** | `https://<landing>/#realm/…/strand/…?action=view` | 用户复制粘贴的默认形态；`#` 之后整体 = 同一 grammar。`<landing>` 域名由部署方选定，本协议**不**指定中心化落地域名。 |

`web+arkret:` 与 HTTPS 落地形态共用同一 §3 grammar parser，只是外壳不同（裸接 scheme vs 接在 `#` 后）。逻辑 ID grammar（`ak:<kind>:<uuid>`）见 [`artifacts/registry/id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)，本文不重复定义。

## 3. 地址 grammar

canonical 形态（以 `web+arkret:` envelope 表示）：

```
web+arkret:realm/<realm>/strand/<strand>/m/<msg>?action=view
```

| 部分 | 承载 | 规则 |
| --- | --- | --- |
| **path** | containment 链 = 身份 + 解析顺序 | path keyword 携带对象类型，值是**裸 UUID**（剥掉 `ak:<kind>:` sigil）。层级固定 `realm/<r>` ⊃ `strand/<f>` ⊃ `m/<msg>`。 |
| **query** | 非身份提示 + 授权组件 | `action`、`lt`、`tok`（见 §3.2 / §4）。 |
| **fragment** | 隐私敏感位（仅 HTTPS 形态） | 见 §5。 |

合法前缀（短到长均可单独成址）：

```
web+arkret:realm/<realm>                              # Realm（解析委托给 resolve_realm）
web+arkret:realm/<realm>/strand/<strand>                  # Strand
web+arkret:realm/<realm>/strand/<strand>/m/<msg>          # Strand discussion track 内某条 Message
web+arkret:realm/<realm>/strand/<strand>?lt=invite&tok=<token>   # invite link
```

### 3.1 Path 规则（normative）

- **realm 是身份，进 path；join routing 不进 URL query。** realm 脱离 path 则 strand 无法定位（授权 / 解析以 Realm 为根，见 [`models/circle.md`](../models/circle.md)）；加入时可用的 Realm ingress service 由 `resolve_realm` / `resolve_target` 返回的 `join_candidates[]` 给出，不写入地址本体。
- **Strand / Message 地址 MUST 携带 `realm/<realm>`**；缺少 Realm 根时解析方 MUST fail closed（返回 `not_found`），不得做全网 strand_id 猜测。
- **`<realm>` 段消歧（normative）**：该段匹配 UUIDv7 文本形态时解释为 `realm_id`；否则解释为 **realm alias**（canonical grammar `<localpart>:<domain>`，见 §3.3）。判据等价：裸 UUID → `realm_id`，含 `:` 而非 UUIDv7 文本 → alias。`<strand>` / `<msg>` 段**只**接受裸 UUID。path 内裸 UUID 是 URI 压缩形态；进入 token target descriptor（§4）或下游比对前，解析方 MUST 按 path keyword 重建 typed canonical ID（`ak:realm:<uuid>` / `ak:strand:<uuid>` / `ak:message:<uuid>`）。alias 仅作为解析输入形态，MUST 先经常规 Realm 解析路径规范化为 canonical `realm_id`，后续身份比对一律绑定 `realm_id` 而非 alias 字符串。
- **未知 path keyword fail-closed**：v1 合法 keyword 只有 `realm` / `strand` / `m`，且层级顺序 MUST 为 `realm` ⊃ `strand` ⊃ `m`。解析方遇到未注册 keyword、顺序错乱或缺中间层级时 MUST 返回 `not_found`，不得猜测。未来扩展对象类型（如 `morph` / `space` / `circle`）MUST 显式扩 keyword 表；旧客户端遇到未知 keyword 一律按 fail-closed 处理，保证 forward-compat 下不分叉。
- Message 锚点 keyword 固定为 `m/`（对齐协议层 [Message 对象](../models/strand-and-message.md#9-message)，而非底层 event envelope）。在 v1 中，`m/<msg>` 只寻址 Strand discussion track 内的 `ak:message:` 对象；synthesis track 的结构化内容应通过 Strand / Morph / Relation 等对象地址或 profile 显式注册的未来 keyword 寻址，不得把 `m/` 解释为任意 track-local item。
- **Circle-scoped Strand**（`Strand.scope_circle_id != null`）的地址形态**不**额外暴露 circle id：scope 由解析后的访问判定决定，地址层不泄露 Circle 存在性（见 §6）。

### 3.2 Query 规则（normative）

- `action=<view|join|reply>`：纯 UI 意图 hint，默认 `view`；解析方 MAY 忽略，**MUST NOT** 据此放大权限。
- `lt` / `tok`：授权组件，见 §4。
- `action` 是"删掉不改变指向什么"的纯提示；`lt` / `tok` 携带授权类别，删除 `tok` 把链接降级为 `reference`。

### 3.3 Realm alias 与人类短地址（normative）

`<realm>` 段的 alias 与用户 handle 共享同一套人类地址形态，二者只在 sigil 与命名空间上区分。

**Realm alias canonical grammar**：realm alias 的 canonical 形态是 `<localpart>:<domain>`，与 [`identity/identity-handles.md` §3.1/§17](../identity/identity-handles.md) 定义的 handle canonical 形态**同语法**：

- `<localpart>`：与 handle localpart 相同的 `arkret_human_identifier`，即 RFC 8265 `UsernameCaseMapped` enforcement 后的 Unicode canonical value；它不是 domain label，MUST NOT 使用 IDNA。长度 1..128 Unicode code points 且不超过 512 UTF-8 octets。
- `<domain>`：运营该 alias 的部署 / 组织（realm alias issuer）的权威域，至少两个 label；用户输入 MAY 是 U-label，canonical wire MUST 是按 [`conformance/encoding.md` §2.2.1](../conformance/encoding.md) 得到的小写 A-label。
- canonical alias **不含** sigil。`#general:acme.example`、`general@acme.example`、裸 `general` 等形态 MUST NOT 作为 canonical alias 出现在 `web+arkret:` path 段、缓存键或 `resolve_*` 规范化结果中（带 sigil 形态仅可作为 §下文「输入路由」的解析输入）。

**人类短地址与 sigil（display + 输入路由）**：面向人的短地址用前导 sigil 标注目标类型：

| 短地址形态 | 目标类型 | 解析 operation |
| --- | --- | --- |
| `@<localpart>:<domain>` | 用户 handle | `resolve_handle`（见 [identity-handles §3](../identity/identity-handles.md)） |
| `#<localpart>:<domain>` | realm alias | `resolve_realm`（见 [discovery-directory §9](./discovery-directory.md)） |

sigil 承担两个 normative 职责：

- **输出（display / share）**：客户端渲染、@mention、可分享短文本、二维码 SHOULD 以带 sigil 形态呈现 realm alias（`#`）与 handle（`@`），使人一眼区分「频道 / realm」与「人」。
- **输入路由（parse）**：客户端接受带 sigil 输入时，MUST 用 sigil 选择解析命名空间（`#` → `resolve_realm`，`@` → `resolve_handle`），并在解析前 strip sigil 还原 canonical `<localpart>:<domain>`。

sigil 是展示与输入层 affordance，**不是 wire 的一部分**：strip 后的 canonical 才进 `resolve_*` 输入、`web+arkret:` path、§4.2 target descriptor、签名 transcript、Directory 缓存键、`handle` / alias 字段。这与 handle 的 `@` 纪律（identity-handles §3.1）一致。

**无 sigil 裸输入的 default（normative）**：通用输入框 / 搜索框收到无 sigil 的裸 `<localpart>:<domain>` 时，客户端 MUST NOT 静默猜测单一类型，而是：

- MUST 同时对 handle 与 realm alias 两个命名空间发起解析；
- 命中**唯一**命名空间时直接采用该结果；
- 命中**多个**命名空间时 MUST 向用户呈现消歧选择（`@…` vs `#…`），不得擅自取其一。

**命名空间不相交，无全局唯一约束（normative）**：handle 与 realm alias 占据**两个不相交的命名空间**，分别由 `resolve_handle` 解析为 holder / principal DID、由 `resolve_realm` 解析为 `ak:realm:<uuid>`。协议 **MUST NOT** 要求两命名空间间全局唯一：同一 `<localpart>:<domain>` MAY 同时是一个 handle 与一个 realm alias，由 sigil 在显示 / 输入期区分，线上字段（自带类型上下文）无歧义。同一 `<domain>` 的 issuer **MAY** 选择在两命名空间间保留 / 对齐同名（本地治理策略），但这不是协议强制约束，实现 MUST NOT 因此在两命名空间间引入跨注册表唯一性检查。

**混淆防护（normative）**：realm alias 的 canonical equality 是 prepared localpart + lowercase A-label domain 的精确相等。registrar MAY 按 handle §17 在同一 authority 的 **realm-alias namespace** 内建立 UTS #39 skeleton collision index并要求 `Highly Restrictive`；碰撞返回 `failed_precondition` `reason="realm_alias_homograph_forbidden"`。skeleton 不得进入 wire equality。handle 与 realm alias namespace 不相交，跨 namespace skeleton 相同不构成冲突，由 sigil 与类型上下文消歧。

**Native personal Agent selector slug（normative）**：`@<controller-handle>/<agent_slug>` 的 `agent_slug` 复用 `arkret_human_identifier` preparation，长度 1..64 Unicode code points且不超过 256 UTF-8 octets；`/`、`@`、`:`、`#`、`?`、`\\`、空白与控制字符均禁止。`总结助手` 是合法 canonical slug。slug 只在 controller namespace 内唯一，是可变、可撤销、非授权的用户标签；若实现需要 URL path / machine-only ASCII token，必须定义独立字段，不能收窄 `agent_slug`。

## 4. Link 类型与授权 token

授权**不做成独立 scheme**，而是同一地址 + 一个分型签名 token 组件（与 [`discovery-directory.md` §9](./discovery-directory.md) `resolve_realm` 已有的 `realm_id`（纯）vs `invite_token` / `signed_link`（带授权）输入形状同构）。

v1 定义三种 link 类型：

| 类型 | 携带 | 解析后效果 |
| --- | --- | --- |
| `reference`（默认） | 纯地址 | 走正常 discovery + access gate；**不授予任何权限**。请求方本就能发现/读取时返回对应 preview / 内容，否则 `not_found`。 |
| `invite` | 地址 + `tok`（`invite_token` / `signed_link`） | 兑换后经 [`governance/join-policy.md`](../governance/join-policy.md) 授予 membership / 访问；有 expiry、audience-bound、可吊销。 |
| `preview` | 地址 + `tok`（signed preview token），或 requester proof 满足 `ak.realm.preview_policy` | 只授予 policy 限定的 stripped preview / history stub / plaintext Realm snippet；**不授予 membership、write、join routing 或完整历史读取**。 |

`preview` link type 的授权语义由 [`../governance/history-visibility.md`](../governance/history-visibility.md) §4 与 Realm 的 effective `ak.realm.preview_policy` 定义。解析方遇到 preview token 但 Realm 未声明有效 preview policy 时 MUST 按未授权处理并返回统一 `not_found`。Preview token 只扩大到 policy 指定的 preview projection，不得被解释成 invite、membership、`ak.event.read` 或 E2EE key share grant。

### 4.1 Token wire syntax（normative）

授权组件**统一**用两个 query 参数，**禁止** `invite_token=` / `signed_link=` 等分叉参数名（否则不同客户端生成互不互通的链接）：

- `lt=<reference|invite|preview>`，省略等价 `reference`。解析方遇到其它值时 MUST 按最严格的 `reference` 语义处理（不授予任何权限）。
- `tok=<opaque-token>`，**当且仅当** `lt ∈ {invite, preview}` 出现；直接映射到 `ak.find.directory.query.resolve_target` 的 `token` 输入。
- token 的内部类别（`invite_token` 风格 vs `signed_link` 风格）由签名 payload 自身表达，**不**靠 URL 参数名区分。
- token 存在时，**权威 address_link_kind 取自 token 签名 payload**；URL `lt` 仅是解析前的展示 hint，**MUST NOT** 用于放大权限，与 token 内声明矛盾时以 token 为准。

### 4.2 Token 必须绑定 canonical target（normative）

`invite` / `preview` token 仅有 expiry / audience / 可吊销**不够**——其签名 payload **MUST** 覆盖它授权的具体对象，否则 `resolve_target` 把 `address` 与 `token` 当独立输入时，A 对象的有效 token 可被重放到 B 地址（scope confusion）。

token 签名 payload **MUST** 包含 **target descriptor** + 生命周期字段。

**Target descriptor canonical shape（确定性）**：`target_descriptor` 由 [`object-addressing.schema.json#/$defs/address_link_target_descriptor`](../../artifacts/schemas/object-addressing.schema.json) 定义，是**恰好**如下字段的对象；签名 token 公共 claims 使用同一 schema 的 `$defs/signed_address_link_token_claims`。缺省的层级字段 **MUST 整键省略**（不得写 `null`——避免 JCS 因 `null` vs 省略产生不同 digest）：

```json
{
  "realm_id": "ak:realm:<uuid>",
  "strand_id": "ak:strand:<uuid>",
  "message_id": "ak:message:<uuid>",
  "address_link_kind": "invite"
}
```

字段出现规则：`realm_id` 与 `address_link_kind` 必含；`address_link_kind` MUST 是 token 签名 payload 声明的 effective type（`invite` 或 `preview`）；`strand_id` 仅 strand / message 目标出现；`message_id` 仅 message 目标出现。

`target_digest = "sha256:" || hex(sha256(JCS(target_descriptor)))`，其中 `JCS` 是 [RFC 8785](https://www.rfc-editor.org/rfc/rfc8785) JSON Canonicalization Scheme。

- `realm_id` / `strand_id` / `message_id` 字段值 MUST 使用 typed canonical ID（`ak:realm:<uuid>` 等），不得使用 path 中的裸 UUID 或 alias 原文；`realm_id` 必须是 alias 规范化（§3.1）后的 canonical Realm ID。
- **`target_digest` 只覆盖身份元组（`realm` / `strand` / `m`）与 `address_link_kind`**，**MUST NOT** 纳入 `action` / `tok` / `lt` 或任何其它 query hint。后果是确定的：路由提示刷新或 UI action 改变**不**使 token 失效；而换一个 Strand / Message、或把 `preview` token 当 `invite` token 使用，必然换 digest、token 不可挪用。白名单外字段 MUST NOT 进 digest——与 [`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md) `claim_digest` 同纪律。
- 生命周期字段 `aud` / `exp` / `nonce` 在 token payload 内，但**不属于** target descriptor（它们是 token 自身有效性边界，不是被寻址对象的身份）。
- 签发端与 `resolve_target` 端 MUST 用同一 shape 与省略规则，否则 digest 不可比对。

### 4.3 Token 生命周期

`invite` token 的签发 / 过期 / 吊销复用 [`governance/join-policy.md`](../governance/join-policy.md) 既有 `invite_token` / `signed_link` 生命周期，本文**不另发明** revocation 机制。`resolve_target` 在 §4.2 target descriptor 校验通过后，仍 MUST 走 join-policy 的 token 有效性 / 吊销检查。

`preview` token 使用同一 target descriptor discipline，但生命周期由 `ak.realm.preview_policy` 约束。签名 payload MUST 至少包含 `aud`、`exp`、`nonce`、`target_digest`、`address_link_kind="preview"`、`preview_policy_digest`，并 SHOULD 包含允许的 preview mode / max events 摘要。解析方 MUST 校验 `preview_policy_digest` 指向当前 effective preview policy，或指向 effective policy **显式枚举**的、仍接受的 previous digest；否则返回统一 `not_found`。

**`preview_policy_digest` allowlist 边界（normative）**：为避免 "still-valid previous" 含义不清形成 policy downgrade 窗口（旧、已收紧前的 preview policy 被无限期接受），其边界 MUST 由 policy 自身显式声明，不得由解析方自行推断版本数 / 时间窗口：

- effective `ak.realm.preview_policy` MUST 显式枚举它仍接受的 previous `preview_policy_digest` 集合（`accepted_previous_policy_digests[]`），每个条目 MUST 携带各自的过期时间（`expires_at`）。
- 解析方 MUST 仅接受 `preview_policy_digest` 等于当前 effective digest、或命中该 allowlist 且 `now < expires_at` 的 previous digest；不在 allowlist 内、或已过期者一律按未授权返回统一 `not_found`。
- 解析方 MUST NOT 用"最近 N 个版本""固定时间窗口"等隐式规则代替 allowlist。
- policy 收紧时，签发端 MUST 能即时清空 / 重写 `accepted_previous_policy_digests[]`（例如置空数组），使被收紧前签发的 preview token 立即失效，不依赖各条目自然过期。

## 5. 隐私：target 与 token 放 fragment

HTTPS 落地链接中，`strand` / `m` / 尤其 `tok` **MUST** 放在 URL **fragment（`#`）**，不进 path / query。理由：fragment 不发往落地页服务器，服务器日志学不到"谁在打开哪个 Strand / 持有哪个 token"，与 [`discovery-directory.md` §11](./discovery-directory.md) anti-enumeration 立场一致。

`web+arkret:` 的隐私边界按 handler 类型分两支（不可笼统说"不经 web server"）：

- **原生 OS 级 handler**：URI 由操作系统直接派发给本地 app，不经任何第三方 web server，`tok` 留在 query 无泄露风险。
- **web `registerProtocolHandler` handler**：浏览器会**导航到注册的 HTTPS handler 模板 URL**，并把原始 `web+arkret:` URI 作为替换值（`%s`）填入。若模板把 `%s` 放在 path / query，则 target 乃至 token 会进入 handler 服务端的请求与日志。因此：
  - web handler 模板 **MUST** 把 `%s` 放进**自身 fragment**（例如 `https://app.example/open#%s`），使被替换的 URI 永远落在 fragment、不进服务端；**或**
  - web 客户端**只**走 HTTPS fragment 落地页，把 `web+arkret:` 留给原生 / 本地 handler，不自行注册 web protocol handler。

### 5.1 Landing / handler 域名不是信任锚（normative）

`<landing>` 域名与 web `registerProtocolHandler` handler 模板域名由部署方任意选定，本协议**不**赋予它们任何权威。客户端解析链接时：

- 客户端 **MUST** 把**解析后**的 canonical 身份（`realm_id` 及 §4.2 target descriptor 中的 `strand_id` / `message_id`，经 §3.1 alias 规范化）作为唯一信任锚，所有后续 access gate / 身份比对一律绑定该 canonical target。
- 客户端 **MUST NOT** 因 landing 域名、handler 模板域名、或链接外壳与某个已信任部署"看起来相同 / 不同"而授予任何额外权限、放大 token scope、跳过 §6 的 `resolve_target` 校验，或自动向该域名提交 `tok` / 任何授权 material。token 的兑换目标仍由其签名 payload 内的 target descriptor 决定，与承载它的 landing 域无关。
- 对**未知 / 不在本地信任集合内**的 landing 域名，客户端 **SHOULD** 在解析或兑换前提示用户确认，避免任意域名借 Arkret 链接外壳诱导用户提交 token。

## 6. 解析 operation：`ak.find.directory.query.resolve_target`

`ak.find.directory.query.resolve_target` 是 [`discovery-directory.md` §9](./discovery-directory.md) `resolve_realm` 的对象级泛化。两者**共存**：`resolve_realm` 保留为 realm-only 入口；`resolve_target` 解析 realm 目标时 MUST 委托给同一 Realm 解析路径（不另发明 realm 解析语义，避免漂移）。

| operation_id | 必填 | 可选 | 响应 | 约束 |
| --- | --- | --- | --- | --- |
| `ak.find.directory.query.resolve_target` | `address: string`（§3 canonical grammar） | `requester: did`; `proofs: proof[]`; `token: string`（`lt ∈ {invite, preview}` 时） | `target_kind: enum(realm,strand,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; 以及 [§9.1](./discovery-directory.md) 全部通用字段 | 见下。 |

响应约束（normative）：

- 响应 **MUST** 含 [`discovery-directory.md` §9.1](./discovery-directory.md) 全部通用字段，按该节定义直接继承——本节不重述或弱化各字段的强度。其中 `as_of`、`source_refs`、`policy_revision` 在所有 search / resolve 结果上均为 **MUST**（与 [`discovery-directory.md` §7.3](./discovery-directory.md) 不变量 3 一致）；`stale` / `divergent` 为可选诊断标记。realm target 在调用方有权得到 join 路由时 MUST 同时返回 `join_candidates[]`。
- invite / restricted / secret 资源对未授权请求使用与不存在不可区分的统一 `not_found`（复用 `resolve_realm` 的 blinding）。
- 携带 `token` 时，`resolve_target` MUST 按 §4.2 校验 token 的 target descriptor 与 `address` 解析出的 canonical 身份 `{realm_id, strand_id?, message_id?}` + 生效 address_link_kind **逐级一致**（等价：重算 `target_digest` 比对），再按 §4.3 走 invite 或 preview 的有效性 / 吊销检查；任一不一致返回统一 `not_found`，不得只校验 token 自身有效性。
- `preview` token 校验通过时，响应 MUST 只包含 effective `ak.realm.preview_policy` 允许的 `realm_preview` / `object_preview` / stripped `history_preview` 字段。除非 caller 另行满足 join routing disclosure gate，响应 MUST 省略 `join_candidates[]`。
- alias 解析失败、alias 与 token 绑定的 `realm_id` 不一致、或无法取得 canonical `realm_id` 时，均返回统一 `not_found`。

客户端解析流程：解析 `address` → 取 path 末段确定 `target_kind` → 用 realm path 段解析 Realm 并取得 canonical `realm_id` 与可披露的 `join_candidates[]`（委托 `resolve_realm`）→ 若有 `token`，按 §4.2 校验 target descriptor → 在 Realm 内按 access gate 定位 strand / message → 渲染成本地 UI URL。若随后要 join / invite-accept / knock，客户端从 `join_candidates[]` 选择一个未过期候选，而不是假定邀请者服务就是唯一入口。

## 7. 规范性引用

- 发现 / 目录 / 三 gate / anti-enumeration / `resolve_realm` / `join_candidates`：[`discovery/discovery-directory.md`](./discovery-directory.md)。
- Realm 为根的授权 / Circle scope / 存在性隐私：[`models/circle.md`](../models/circle.md)、[`models/strand-and-message.md`](../models/strand-and-message.md)。
- Invite token / signed_link 生命周期：[`governance/join-policy.md`](../governance/join-policy.md)。
- Digest 纪律（JCS + 字段白名单）：[`identity/identity-handles.md` §3.2.1](../identity/identity-handles.md)。
- 逻辑 ID grammar：[`artifacts/registry/id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)。
- Operation 注册 / HTTP binding：[`artifacts/registry/contract-registry.json`](../../artifacts/registry/contract-registry.json)、[`sync/service-http-binding.md` §2.3](../sync/service-http-binding.md)。
