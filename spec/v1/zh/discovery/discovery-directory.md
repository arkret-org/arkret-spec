---
title: Discovery and Directory
status: candidate
normative: true
stability: v1
updated: 2026-05-25
see_also:
  - ../governance/history-visibility.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Contrix 需要明确区分三件事：

- 资源是否可被发现。
- 资源是否可被预览。
- 主体是否可加入、读取或写入资源。

发现不等于读取，读取不等于加入，加入不等于写入。实现 MUST NOT 用 `join_rule` 或 `history_visibility` 代替 discoverability policy。

本文定义 Realm、Organization、Actor 和 Applet 的发现模型、目录服务和防枚举要求。

## 2. 发现级别

`discoverability` 取值：

| 值 | 含义 |
| --- | --- |
| `public` | 可被公共目录索引和搜索。 |
| `listed` | 可在指定目录、组织页、源 Realm 或受信目录中列出，但不一定进入全网公共搜索。 |
| `restricted` | 只有满足可验证条件的请求方可发现，例如组织成员、受邀者、共同 Realm 成员或持有特定 claim 的主体。 |
| `unlisted` | 不进入目录搜索；知道精确 id、alias、邀请链接或 source Realm edge 的主体 MAY 尝试解析。 |
| `invite_only` | 未被邀请或未持有 invite proof 的主体不得得知其存在；查询应返回与不存在相同的错误。 |
| `secret` | 仅本地或端到端加密上下文中可见；目录、Sync Service 和受托 search / projection 服务不应公开可枚举 metadata。 |

默认值：

- 新 Realm 默认 `invite_only`。
- 新 Organization profile 默认 `listed`，但 MAY 设置为 `restricted` 或 `unlisted`。
- Pairwise / private DID 默认 `secret`。
- Public Persona DID 默认 `public` 或 `listed`，由 holder policy 决定。

## 3. Realm Discoverability

Realm discovery policy SHOULD 由 `cx.realm.discovery` state event 表达：

```json
{
  "kind": "cx.realm.discovery",
  "payload": {
    "discoverability": "listed",
    "directory_visibility": {
      "public_directory": false,
      "organization_directory": true,
      "source_realm_directory": true
    },
    "preview": {
      "mode": "stripped_state",
      "fields": [
        "title",
        "avatar_blob_ref",
        "summary",
        "owning_organizations",
        "join_rule",
        "member_count_bucket"
      ]
    },
    "allowed_discoverers": [
      {
        "type": "claim",
        "claim_type": "org_membership",
        "organization": "did:web:acme.example",
        "issuer": "did:web:acme.example"
      }
    ],
    "directory_services": [
      "did:web:directory.acme.example"
    ],
    "anti_enumeration": {
      "require_exact_alias_for_unlisted": true,
      "member_count_mode": "bucketed",
      "not_found_blinding": true
    }
  }
}
```

规则：

- `discoverability=public` 的 Realm MAY 被公共目录服务索引。
- `listed` Realm MUST 仅出现在 `directory_visibility` 或 `directory_services` 明确允许的目录中。
- `restricted` Realm MUST 在返回搜索结果前要求目录查询授权。
- `unlisted` Realm MUST NOT 出现在关键字搜索，但在 policy 允许时 MAY 通过精确 id / alias / 签名 invite / source Realm edge 解析。
- 未授权 subject 对 `invite_only` 与 `secret` Realm 的查询 MUST 返回 `not_found` 或与其不可区分的响应。
- 在未单独授权时，目录结果 MUST NOT 包含事件历史、成员列表、policy 原文、MLS 状态、隐藏 parent/child edge 或完整组织治理链。

`anti_enumeration.member_count_mode` 取值 normative：

| 模式 | 行为 |
| --- | --- |
| `exact` | 返回精确成员数；仅在 `discoverability ∈ {public, listed}` 时允许。 |
| `bucketed` | 返回**封闭 bucket** 之一：`1-10` / `11-50` / `51-100` / `101-500` / `501-2000` / `2000+`。Directory 实现 MUST 使用本 bucket grid，不得自定义粒度（防止粒度差异成为枚举侧信道）。请求方收到不在此枚举的 bucket 字符串 MUST 视作 `invalid_response` 并丢弃。 |
| `omit` | 不返回成员数；任何隐含的 hint（如返回组员数组的 length）也 MUST 被裁剪。 |

`unlisted` / `invite_only` / `secret` Realm 的 `member_count_mode` 默认 `omit`；显式声明 `bucketed` 时必须遵守上述 bucket grid。

`join_rule` 只控制加入流程。公开可发现的 Realm MAY 仍要求 invite、knock 或 restricted join。不可发现的 Realm MAY 对持有私有链接的成员保持 `join_rule=public`，但除非配套强反垃圾策略，否则不推荐。

`history_visibility` 只控制历史读取范围。`discoverability=public` MUST NOT 隐含 `history_visibility=world_readable`。五个 history level 的 reader class、invite / join 时点、removal 后 backfill 和 E2EE key share 语义以
[`../governance/history-visibility.md`](../governance/history-visibility.md) 为准；本文件只定义 discovery / join / history 三 gate 的组合关系。

### 3.0 三个独立 Gate（先于矩阵理解）

`discoverability`、`join_rule`、`history_visibility` 是三条**独立判定**的 gate，作用面互不替代：

```mermaid
flowchart TB
    subgraph Q ["三个独立 gate（实现 MUST 分开判断）"]
        direction LR
        D["1. Discoverability<br>能不能发现?<br>public / listed / restricted<br>unlisted / invite_only / secret"]
        J["2. Join Rule<br>能不能加入?<br>public / invite / knock<br>restricted / knock_restricted / closed"]
        H["3. History Visibility<br>加入后能看多少历史?<br>world_readable / shared<br>invited / joined / restricted"]
    end

    Search["Directory / 搜索 / preview<br>受 Discoverability 决定"]
    Join["加入 / knock / invite<br>受 Join Rule 决定"]
    Read["历史读取范围<br>受 History Visibility 决定"]

    D --> Search
    J --> Join
    H --> Read

    R1["不可发现 ≠ 不可加入<br>unlisted + 已知 invite link → 仍可加入"]
    R2["可加入 ≠ 可见全部历史<br>history_visibility 独立收窄"]
    R3["可发现 ≠ 全网可读<br>discoverability=public 不隐含 world_readable"]

    D -. 与 J 独立 .-> R1
    J -. 与 H 独立 .-> R2
    D -. 与 H 独立 .-> R3
```

读图要点：

- **Discoverability** 只控制资源是否能在搜索 / Directory / preview 里出现；不决定加入资格，也不决定历史读取范围。
- **Join Rule** 只控制加入流程；不可发现的 Realm 也可以是 `join_rule=public`（持有私链接即可加入），公开 Realm 也可以是 `join_rule=invite`。
- **History Visibility** 只控制 reader 对历史 Event range 的读取资格；与前两者完全正交。E2EE Realm 中它不自动授予旧 epoch key。
- 任何把 `discoverability` 当作 `join_rule` 或 `history_visibility` 简写的实现都是错误——下表 §3.1 锁定了允许的组合。

### 3.1 `discoverability × join_rule × history_visibility` 兼容矩阵（normative）

下表声明 v1 在三组维度上**允许 / 禁止 / 不推荐**的组合。`✓` = 允许；`!` = 允许但 SHOULD 在 Realm create 时显示警告；`✗` = MUST 拒绝（reducer 在 `cx.realm.policy_components` accept 时返回 `policy_combination_invalid`）。本表不替代 §3 与上方各 enum 的语义；当某条规则与本表冲突时，更严格者（拒绝/警告）优先。

| discoverability ↓ \ join_rule → | `public` | `invite` | `knock` | `restricted` | `knock_restricted` | `closed` |
| --- | --- | --- | --- | --- | --- | --- |
| `public` | ✓ | ✓ | ✓ | ✓ | ✓ | ! |
| `listed` | ! | ✓ | ✓ | ✓ | ✓ | ! |
| `restricted` | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ |
| `unlisted` | ✗ | ✓ | ! | ✓ | ✓ | ✓ |
| `invite_only` | ✗ | ✓ | ✗ | ✓ | ✗ | ✓ |
| `secret` | ✗ | ✓ | ✗ | ✗ | ✗ | ✓ |

`history_visibility` 与上述任一组合搭配时的额外约束：

- `world_readable` MUST NOT 与 `discoverability ∈ {invite_only, secret}` 同时声明（拒绝）。
- `world_readable` 与 `discoverability ∈ {unlisted, restricted}` 同时声明 MUST 在 join warning 显式告知（"任何持有 link 的方都可读取全部历史"）。
- `shared` / `invited` / `joined` 与所有 discoverability 组合兼容。
- `restricted` 历史可见性 MUST 与有效 `cx.realm.history_sharing_policy` 一致；缺少该 policy 时 reducer MUST 拒绝该 effective state。与 `discoverability=public` 组合时仍 SHOULD 限制 lazy member preview 防止枚举。

实现 MUST 在 `cx.realm.policy_components` reducer 接受前用本表校验当前 effective 状态；变更任一字段使组合落入 `✗` 时 MUST 返回 `policy_combination_invalid` 并保留旧值。本表是 v1 wire 互操作的最小集，profile 可以**收紧**但不得放宽。

### 3.2 Preview / Peek 与 History Visibility 的关系

Directory preview 不是历史读取的快捷方式。`cx.realm.discovery.preview` 只声明目录结果或 exact resolve 可以返回哪些最小 metadata（例如 `title`、`summary`、`join_rule`、bucketed member count、`stripped_state`），不得单独授权正文历史、成员列表、policy 原文、隐藏 edge 或 E2EE 明文。

当实现要支持 Matrix-style "peek before join"、invitee 进入前历史片段、或带 token 的 object preview 时，Realm MUST 同时声明有效 `cx.realm.preview_policy`，并按
[`../governance/history-visibility.md`](../governance/history-visibility.md) §4 执行 preview audience、字段、历史范围、E2EE 和 anti-enumeration 规则。没有 `cx.realm.preview_policy` 时：

- Directory MAY 返回 directory card / stripped state，但 MUST NOT 返回 history stub 或 history snippet。
- `resolve_realm` / `resolve_target` 对未授权 preview MUST 返回与不存在不可区分的 `not_found`。
- `history_visibility=world_readable` 仍不允许 Directory 自动扩展 preview 字段；完整历史读取必须走 Events / backfill surface，并继续执行 capability、retention、redaction 和 plaintext-visible service 检查。

## 4. Organization 可发现性

Organization discovery policy SHOULD 通过组织 profile 状态或 governance registry 记录表达：

```json
{
  "kind": "cx.organization.discovery",
  "organization_did": "did:web:acme.example",
  "discoverability": "public",
  "profile_visibility": {
    "display_name": "public",
    "logo_blob_ref": "public",
    "summary": "public",
    "owned_realms": "listed",
    "members": "restricted",
    "services": "listed"
  },
  "directory_services": [
    "did:web:directory.acme.example"
  ],
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:web:acme.example#governance-key-1",
    "jws": "..."
  }
}
```

Organization 可以是公开的、受限的或不可列举的。实现 MUST NOT 因为组织 DID 可解析，就公开组织成员列表、官方 Realm 列表、服务拓扑或治理策略全文。

客户端展示组织搜索结果时 SHOULD verify：

1. Organization DID 可解析。
2. discovery policy 或 profile 由组织 DID / governance service 签名。
3. 如果结果声称包含 official Realm，仍需验证每个 Realm 的 `cx.realm.organization` 背书。
4. 目录服务 DID 被组织 DID 声明或被本地 trust policy 接受。

### 4.1 Actor / Applet / Handle Discovery State

`cx.actor.discovery`、`cx.applet.discovery` 与 `cx.handle.discovery` 是 v1 active discovery state event kind。它们与 `cx.organization.discovery` 使用同一组目录 ingest 规则：resource 自签名声明可发现性，Directory 只索引被 `directory_services[]` 明确列出的资源，且不得替 resource 重新签名或扩展披露范围。

这些 payload 至少包含：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `resource_kind` | `enum(actor,applet,handle)` | required | 必须与 Event kind 后缀一致。 |
| `resource_id` | `did` / canonical handle / applet id | required | 被发现资源的稳定标识。 |
| `discoverability` | §2 enum | required | `public` / `listed` / `restricted` / `unlisted` / `invite_only` / `secret`。 |
| `directory_services` | `did[]` | required | 被允许索引该资源的 Directory service DID 列表。 |
| `profile_visibility` | `object` | optional | 每个预览字段的可见性；未列字段默认不披露。 |
| `proof` | detached proof | required | 由 resource controller / governance key 签名，覆盖 canonical payload（不含 proof 本身）。 |

Actor discovery MUST NOT 暴露 pairwise/private DID、未披露组织账号或仅因共同 Realm 推断出的关系。Applet discovery MUST 只披露 registration 允许的 public metadata，不得暴露 private namespace、token、webhook secret 或租户内 endpoint。Handle discovery MUST 绑定 handle issuer、subject claim、audience 与过期时间；受限 handle 未满足 presentation / policy gate 时不得返回 subject DID 或 `member_delivery_binding`。

## 5. Actor 与 Handle 可发现性

Actor / Principal 发现 MUST 尊重 holder 隐私：

- 公开 persona MAY 出现在公共用户目录中。
- Pairwise DID、私有 DID、设备 DID 与隐私敏感的 agent DID 默认 MUST NOT 出现在公共目录中。
- Handle 搜索 MUST 仅返回绑定公开或 holder 已显式授权披露的 handle。
- Handle 搜索 / 解析若会暴露 `subject` DID 或 `member_delivery_binding`，MUST 额外满足 requester proof、intent、audience / challenge 和 issuer policy；共同 Realm 或同组织排序信号不得单独授权披露。
- Presence、common Realm、组织成员与联系人图谱 MUST NOT 通过搜索排序或自动补全泄露。

在共享 Realm 中查询未知 actor profile，仅允许在渲染已授权内容（如显示名、头像）所必需的范围内进行；MUST NOT 借此泄露无关 handle 或组织账号。

## 6. Private Contact Discovery

通讯录式发现比普通目录搜索更敏感。实现 MAY 支持 `cx.private_contact_discovery.v1`，用于在不上传明文通讯录、不让目录服务同时获得 requester DID 与目标 connection identifier 的前提下发现可联系主体。

### 6.1 Profile 目标

- Discovery Provider 不应同时获得 requester 的稳定 DID 和原始邮箱/手机号/用户名。
- 请求应使用 batch、padding、rate limit 和 time-bound proof，避免逐个枚举。
- 发现结果应返回最小可联系材料，而不是完整 profile 或关系图谱。
- 协议 MUST 定义"private discovery 能回答什么"——并显式声明不能回答什么——避免实现私自扩展导致隐私退化。

### 6.2 v1 core 形态：Set-Membership PSI（双轮 OPRF）

v1 core `cx.private_contact_discovery.v1` profile 明确限定为 **set-membership PSI**：客户端只能问"我已知的 connection identifier 集合中，哪些在 provider 的可联系集合内？"，回答严格是布尔位图，不附带任何额外 reachability claim、profile 或 metadata。

实现 MUST 使用基于 OPRF（Oblivious Pseudorandom Function）的两轮协议（推荐 RFC 9497 VOPRF 或 Signal CDSI 风格）：

1. **Round 1 — Blind**：客户端按 RFC 9497 OPRF 流程对每个本地 connection identifier 计算 `blind = OPRF.Blind(identifier_canonical_bytes)`；提交 `{batch_id, blinded[]}` 给 provider。Provider 对每个 `blinded[i]` 用其 OPRF secret key 计算 `evaluation[i] = OPRF.BlindEvaluate(sk, blinded[i])` 并返回。Provider 看不到 raw identifier；客户端 unblind 后得到 `derived[i]`。`batch_size`、dummy padding 与失败延迟由 Provider policy 强制，不由客户端自报决定。
2. **Round 2 — Match**：客户端在第二个独立请求中提交 `{batch_id, derived_digest_prefix[]}`（每条发送 derived digest 的固定前缀，长度由 provider 在第一轮响应中声明）。Provider 仅在自己的 OPRF-evaluated 可联系集合中按前缀比较，返回固定基数（dummy padding 到 batch size）的命中位图；无论命中数为 0、部分命中还是全部命中，response frame 数量、字段集合、排序和 padding 形态 MUST 相同。
3. **披露**：客户端只在 user 在 UI 中显式确认联系或发起邀请时，才向目标 principal 的 provider 披露自己的 DID、pairwise DID、presentation 或 connection identifier 原文。该披露走 §6 / consent-model 的 invite + consent 流程，不在 PSI 协议范围内。

OPRF 选择：

- v1 core 强制要求 RFC 9497 VOPRF（验证 OPRF），ciphersuite 至少包含 `OPRF(ristretto255, SHA-512)`。
- Provider OPRF secret key MUST 周期轮换（默认 ≥ 7 天 / ≤ 90 天）；轮换后客户端持有的 derived 缓存自动失效，避免长期跨域关联。
- Provider MUST 在 `server/describe.discovery` 暴露当前 ciphersuite、key epoch、batch size / padding 上限。

### 6.3 请求形态（非完整 schema）

第一轮（blind）：

```json
{
  "profile": "cx.private_contact_discovery.v1",
  "phase": "blind",
  "batch_id": "cx:batch:0196429a-0000-7000-8000-000000000000",
  "ciphersuite": "OPRF-ristretto255-SHA512",
  "key_epoch": 14,
  "blinded_elements": ["base64url...", "base64url..."]
}
```

第二轮（match）：

```json
{
  "profile": "cx.private_contact_discovery.v1",
  "phase": "match",
  "batch_id": "cx:batch:0196429a-0000-7000-8000-000000000000",
  "key_epoch": 14,
  "derived_prefixes": ["base64url-16bytes...", "base64url-16bytes..."]
}
```

### 6.4 规则

- Raw email、phone number、address-book label、local contact name 和未加盐低熵 hash MUST NOT 被发送给公共 Directory，包括第一轮的 OPRF input（OPRF Blind 已经做了 unlinkable 化，但实现仍 MUST 在客户端先做 normalization + canonical encoding，杜绝把明文写入 audit log）。
- Provider MUST 对 batch 大小、dummy padding、失败响应、计时和 result cardinality 做反枚举处理；不存在、不可发现、policy-denied 和 OPRF mismatch 在 wire 上 MUST 保持相同响应形态与延迟分布。客户端提交的 padding hint（若 profile 扩展保留该字段）只能作为上限内的偏好，Provider MUST 按自身 policy 重写为固定 `batch_size`。
- Provider MUST NOT 在第二轮返回 reachability proof、handle verified claim、组织成员资格、Realm membership 或读取权限。这些声明只能通过后续 invite + consent 流程获得。
- Private discovery 结果**仅** 证明"在 provider 当前可联系集合中存在 OPRF derived 与某项匹配的条目"——不证明该条目对应的真实身份、handle、活跃度或意愿。客户端 UI MUST 把它表述为"可能可联系"而不是"已确认存在"。
- 高隐私客户端 SHOULD 为每个 provider 或关系使用 pairwise DID，并在 consent 完成前避免披露全局 public persona DID。
- 实现 MUST NOT 在同一 quota window 内允许同一 authenticable principal / device credential 提交超过 `max_psi_queries_per_window`（默认 1）次 batch；默认 quota window 为 24h，且 MUST 与 OPRF key epoch 解耦。超过后 provider 返回与其它 policy-denied 情况等形态的 `psi_quota_exhausted`。IP 只能作为辅助限速维度，不能作为唯一 quota key。新 OPRF key epoch 不得单独重置 quota；只有 quota window 滚动或 operator 明确的反滥用解封才能重置。

## 7. Directory Service Role

Directory Service 是 Contrix 的**发现入口层**：让任意 subject 在不预先知道精确 id / alias / invite 的前提下，从其 trust 范围内**已 opt-in 暴露**的资源中找到目标，并取得**足以独立发起下一步 action（resolve / preview / knock / join / invite / verify / contact）的最小可验证元数据**。

它的职责面 normative 限定为三件事，超出以下范围的能力 MUST NOT 被实现为 Directory 的内置职责：

1. **Ingest**：按 §8 接入资源（Realm / Organization / Actor / Applet / Handle）的签名 discovery state，建立**可重建、可替换、可撤销**的索引。
2. **Query**：向 subject 提供 search / resolve（§9），返回最小可验证元数据 + `source_refs`，让客户端能独立回真相源验签。
3. **Filter & 防枚举**：执行 §3 / §11 的 discoverability 过滤、bucket 聚合、blinded `not_found`，杜绝侧信道。

### 7.1 索引内容

Directory MAY index：

- public / listed Realm preview metadata
- organization public profile
- public persona profile
- applet protocol metadata
- verified handle records that are intended to be public

Directory MUST NOT 索引任何**未通过 §8 ingest protocol opt-in 的**资源；MUST NOT 通过爬取 DID 命名空间、扫描 well-known endpoint、或被动嗅探 federation traffic 自行发现资源。

### 7.2 Directory 不是

| 不是 | 真正责任方 |
| --- | --- |
| 真相源 | 资源各自的 Principal Server 上的签名 state event |
| 授权决策点 | Realm policy / Organization governance / capability evaluator |
| Join 执行点 | `join_candidates[]` 中的 Realm ingress service 按 `join_rule` + Realm policy 接收 / 转发；最终由 reducer 收敛 |
| 身份解析器 | DID resolver / identity registry / witness |
| 消息或历史镜像 | Events API / Sync stream |
| Service topology 权威 | DID Document `service` entry + `cx.organization.service_binding` |
| 全网爬虫 | 不存在；ingest 仅按 §8 双向 opt-in |

特别地：**Directory 不执行 join、不签发 invite token、不签发 capability grant**。Directory 的 join-side 责任到"产出 `realm_id + join_candidates[]` 让客户端能选择合格的 Realm ingress service 发起 join / invite-accept / knock"为止。能否实际加入由 Realm 的 `join_rule` 与 policy 决定（见 §3.0 三个独立 gate）。

### 7.3 不变量（normative）

任何符合 v1 的 Directory 实现 MUST 满足：

1. **Rebuildable**：丢失全部本地索引后，Directory 必须能仅凭 `directory_services` 列出本 DID 的资源 + ingest protocol 重建索引内容。Directory 不得持有任何不可从真相源恢复的"权威"数据。
2. **Pluralizable**：同一资源 opt-in 多家 Directory 时，针对同一 `(resource_id, source_refs frontier, policy_revision)` 的查询结果 MUST 在 §9.1 normative 字段上一致；不一致 MUST 标记为 `stale=true` 或 `divergent=true`。
3. **Freshness-tagged**：每条返回结果 MUST 携带 `as_of`、`source_refs`、`policy_revision`；TTL 过期未续约的 entry MUST 标记 `stale=true` 或被移除（见 §8.6）。
4. **Withdrawable**：资源 governance 通过 §8.7 撤销 opt-in 后，Directory MUST 在 ≤ 1h 内停止披露该资源。
5. **Plaintext-free**：Directory MUST NOT 持有或转发 Realm 内 plaintext content、E2EE 密文 payload、私 persona DID、pairwise DID 或 governance 密钥材料。
6. **No-shadow-grant**：Directory MUST NOT 签发 invite token、capability grant、session credential 或任何能绕过 Realm / Organization policy 的认证材料。

### 7.4 行为契约

Directory Service MUST：

- expose its service DID and feature profile（`cx.directory.describe`，含 §8.9 ingest 字段）
- accept ingest only via §8 with verified governance signature and bidirectional opt-in
- apply authorization filtering before returning each result
- return stable pagination cursors
- indicate result freshness（§9.1 字段）
- avoid leaking existence through distinct errors for hidden resources

Directory Service MUST NOT：

- list `invite_only` or `secret` resources to unauthorized subjects
- expose full member lists unless explicitly allowed
- expose private handles, pairwise DID, disclosure policy or credential contents
- rank hidden resources in a way that reveals their existence
- ingest resources whose signed discovery state does not list this Directory's DID
- alter, re-sign, or substitute discovery state on behalf of resources
- accept indexed content forwarded from another Directory as authoritative

## 8. Discovery Ingest Protocol

Directory 不是真相源（§7）。Directory 持有的索引内容 MUST 来自资源自身签名的 discovery state，并通过本节定义的 ingest protocol 接入。本节是 v1 公共发现互操作的契约层；任何符合 v1 的 Directory MUST 至少实现 §8.2 中的一种 ingest 模式。

### 8.1 双向 opt-in

ingest 是**双向 opt-in**，缺一不可：

| 方向 | 资源端表达 | Directory 端表达 |
| --- | --- | --- |
| 资源 → Directory | 在 `cx.{realm,organization,actor,applet,handle}.discovery.directory_services` 列出本 Directory 的 service DID + governance key 签名整份 payload | — |
| Directory → 资源 | — | 在 `cx.directory.describe.accept_policy_kind` 中声明可接受的资源类别、trust root、配额（§8.9） |

Directory 接受 ingest 的前置条件：

- 资源签名声明中**未列出**本 Directory DID → MUST 拒绝并返回 `directory_not_authorized`。
- 资源不在 Directory `accept_policy` 范围内 → MUST 拒绝并返回 `accept_policy_denied`。
- 资源端 governance key 在 ingest 时刻不在 DID document 当前 epoch → MUST 拒绝并返回 `governance_key_invalid`。

### 8.2 两种 ingest 模式

Directory MUST 支持 **push (announce)** 与 **pull (refresh)** 两种 ingest 模式之一，且 MUST 在 `cx.directory.describe.ingest_modes` 中显式声明本实例支持的模式。

| 模式 | 触发方 | 适用场景 |
| --- | --- | --- |
| push（announce） | 资源 Principal Server 主动提交签名 discovery state | 公开 / 社区 directory；资源希望尽快上线或撤销 |
| pull（refresh） | Directory 按已知资源 DID 周期性拉取最新签名 discovery state | 高安全部署、白名单 directory、与 federation 复用 |

资源端 MAY 任选支持的一种使用；Directory MAY 同时支持两种以提高可用性。两模式产生的索引条目 normative 等价。

### 8.3 Push 模式：`cx.directory.announce`

**Endpoint**：`POST /api/v1/directory/announce`

**认证**：

- Transport 层：HTTP Message Signature（RFC 9421）由资源所在 Principal Server 的 service DID 签发，绑定 `Source-Service-DID` header。
- Payload 层：`discovery_state.proof.detached_jws` 由资源 governance key（按资源 DID document 解析）签发，与 `cx.organization.discovery` / `cx.realm.discovery` 的 effective signer 一致。

**请求字段**：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `resource_kind` | `enum(realm, organization, actor, applet, handle)` | required | 资源类别。 |
| `resource_id` | `id \| did \| handle` | required | 资源主键：Realm 用 `cx:realm:...`；Organization / Actor / Applet 用 DID；handle 用 canonical handle string。 |
| `discovery_state` | `object` | required | 完整签名 `cx.{kind}.discovery` payload（含 `proof`）。MUST 与真相源 byte-for-byte 一致。 |
| `source_refs` | `id[]` | required | 真相源 event id 列表，至少包含产生当前 effective discovery state 的 anchor / state event id。 |
| `as_of` | `timestamp` | required | 资源端声明的 effective 时间；与服务端时间偏差 > 5 min MUST 拒绝（`signature_stale`）。 |
| `principal_server_did` | `did` | required | 当前资源真相源所在的 Principal Server service DID（用于 Directory 在需要时 pull 验证）。 |
| `ttl_seconds` | `int` | optional | 期望保留时长；缺省采用 `default_ttl_seconds`。MUST ≤ `max_ttl_seconds`（§8.6）。 |
| `supersedes_announce_id` | `cx:announce:<uuidv7>` | optional | 上一次 announce id；用于幂等替换与 audit 链接。该 id 只在签发它的 Directory 内有权威含义。 |

**响应**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `announce_id` | `cx:announce:<uuidv7>` | 本次 ingest 记录 id，例如 `cx:announce:0196419b-0000-7000-8000-000000000000`。这是 Directory 本地 ingest 记录；typed 形态只用于统一 validator / SDK 处理，不赋予跨 Directory 的全局对象权威。 |
| `indexed_at` | `timestamp` | Directory 完成索引的服务器时间。 |
| `effective_ttl_seconds` | `int` | Directory 实际授予的 TTL。 |
| `next_revalidation_after` | `timestamp` | 下一次 re-announce 或 pull-refresh 的最早时间。 |
| `warnings` | `string[]?` | 非阻塞警告，例如 `truncated_member_count`、`policy_revision_drift`。 |

**典型错误码**：`directory_not_authorized`、`accept_policy_denied`、`invalid_signature`、`signature_stale`、`source_refs_unverifiable`、`governance_key_invalid`、`ttl_out_of_range`、`rate_limited`、`takedown_in_force`。

请求示例（非完整 schema）：

```json
{
  "resource_kind": "organization",
  "resource_id": "did:web:acme.example",
  "principal_server_did": "did:web:principal.acme.example",
  "as_of": "2026-05-10T08:00:00Z",
  "ttl_seconds": 86400,
  "source_refs": [
    "cx:event:0196419b-0000-7000-8000-000000000000"
  ],
  "discovery_state": {
    "kind": "cx.organization.discovery",
    "organization_did": "did:web:acme.example",
    "discoverability": "public",
    "directory_services": [
      "did:web:directory.example",
      "did:web:directory.acme.example"
    ],
    "profile_visibility": { "...": "..." },
    "proof": {
      "kind": "detached_jws",
      "verification_method": "did:web:acme.example#governance-key-1",
      "jws": "..."
    }
  }
}
```

### 8.4 Pull 模式与 push webhook 注册：`cx.directory.push.register`

Pull 模式复用资源 Principal Server 既有的 `cx.events.query`：

```
GET /api/v1/events
  ?subject={resource_id}
  &kind=cx.{realm,organization,actor,applet}.discovery
  &state_only=true
  &after_revision={last_known_revision}
```

Directory 拉取流程：

1. 按本地 trust root / 已配对资源列表，定期向资源 Principal Server 发 state-only query。
2. Principal Server 返回最新 effective discovery state（含 `proof`）。
3. Directory 按 §8.5 验签后写入或更新本地索引。

可选的 webhook 辅助：Directory MAY 调用 `cx.directory.push.register`（§9）让资源 Principal Server 在 discovery state 变更时主动 webhook 通知（fan-out 优化），但**协议级 freshness 仍以 §8.6 为准**——通知缺失或迟到不得使 stale 条目复活。

### 8.5 验签与接受规则

Directory 接受 ingest（无论 push 或 pull）前 MUST 顺序完成：

1. **Transport layer**：验证 HTTP Message Signature（push）或 service binding + TLS（pull）。
2. **Discovery proof**：验证 `discovery_state.proof.detached_jws` 由资源 governance key 有效签发，签发时间在 key 当前 epoch 内（按 DID document key history）。
3. **Directory authorization**：确认 `discovery_state.directory_services` 数组包含本 Directory 的 service DID。
4. **Source refs sanity**：MAY 通过 pull 抽查 `source_refs` 中至少一个 anchor 在资源 Principal Server 上可解析、frontier 一致。Directory MUST 对**首次 ingest** 的资源至少抽查一次。
5. **Accept policy**：对照本地 `accept_policy` 检查资源 DID method、trust root、配额、abuse 黑名单。

任一步失败 MUST 拒绝并返回对应错误码；Directory MUST NOT 部分接受或"先索引后审核"。

### 8.6 Freshness、TTL 与续约

| 参数 | 默认 | 上限 | 说明 |
| --- | --- | --- | --- |
| `default_ttl_seconds` | `86400`（24h） | — | Directory describe 中声明 |
| `max_ttl_seconds` | `604800`（7d） | `2592000`（30d） | TTL 不得超过此值 |
| `revalidation_grace_seconds` | `3600`（1h） | — | TTL 到期后允许的宽限期 |

规则：

- 资源 MUST 在 `next_revalidation_after` 之前发起 re-announce 或允许 Directory pull-refresh。
- TTL + grace 过期后未续约的 entry MUST 在查询结果中标记 `stale=true`；Directory MAY 在再延迟 24h 后从索引中移除。
- 资源 governance key 在 ingest 期间发生 rotation：MUST 在下一次 announce 中携带新 key 的签名；Directory MUST 在验证 DID document key history 后接受。
- Discovery state 内容未变但需要续约时，资源 MAY 重新提交相同 `discovery_state` + 新 `as_of`，Directory MUST 视为有效续约（按 `(resource_id, as_of)` 幂等）。
- Directory MUST 拒绝 `as_of` 早于已存 entry `as_of` 的 announce（`policy_revision_rollback`）。

### 8.7 撤销

撤销 opt-in 有三条等价路径，Directory MUST 全部支持：

1. **资源端发布新 state**：`cx.{kind}.discovery` 中将 `directory_services` 移除本 Directory DID，或将 `discoverability` 改为 `secret` / `unlisted`。Directory 在下一次 ingest 周期内 MUST 移除条目；push-only 部署中资源 SHOULD 同时调用路径 2 加速生效。
2. **资源端主动 withdraw**：`POST /api/v1/directory/withdraw`，body 含 `resource_id`、`reason`、governance key 签名（与 announce 同等强度）。Directory MUST 在 ≤ 1h 内停止披露。
3. **Directory operator takedown**：单方面下架（policy 违规、abuse、法律）。Directory MUST：
   - 在内部 audit log 记录 `takedown_id`、operator、reason、生效时间；
   - 通过 `cx.directory.describe.takedown_contact` 暴露的入口或 DID document `service` entry 中声明的 governance contact 通知资源端；
   - 不得伪装为"资源主动撤销"——audit log 与资源端通知 MUST 标记为 `operator_takedown`。

Operator takedown 的申诉 / 恢复 MUST 形成可验证闭环：

1. takedown notice MUST 向资源 governance contact 提供 `takedown_id`、resource id、policy reason code、evidence digest、effective_at、appeal endpoint / contact 和 Directory service DID signature；
2. 资源端提交 appeal 时，appeal packet MUST 绑定 `takedown_id`、resource id、appellant DID、argument / evidence digest、requested_outcome 和 created_at，并由资源 governance key 或授权 advocate 签名；
3. Directory 审核结果 MUST 写入内部 audit log，并返回 signed decision receipt；若 overturned，Directory MUST 在下一次 ingest 或 ≤1h 内解除 `takedown_in_force`，并接受资源端最新 signed discovery state；
4. 若该资源同时处于 Realm moderation / organization policy 管辖范围，Directory SHOULD 引用 `cx.moderation.appeal.*` 的 appeal id / decision receipt，避免发现层与协作层出现两个互相矛盾的申诉结果。

撤销后，Directory MUST 对该 `resource_id` 的精确 resolve 返回与 `unlisted` / `not_found` 不可区分的响应（参见 §3 防枚举）；对正在分页的 search 响应，MUST 在下一次 cursor 推进时停止披露。

### 8.8 Cross-Directory Replication（out of scope）

v1 core **不**定义 Directory 之间的 replication / federation 协议。每个 Directory 独立 ingest；同一资源 opt-in 多家 Directory 时分别 announce。

跨 directory mirror、ranking 共享、reputation 交换属于未来 extension profile（工作名 `directory_mesh.v1`），不在 v1 互操作 floor。Directory MUST NOT 接受其他 directory 转发的索引内容作为权威；MAY 把其他 directory 的存在性作为 hint，但仍 MUST 通过 §8.2 模式独立 ingest。

### 8.9 `cx.directory.describe` 扩展

**Schema overlay 关系（normative）**：`cx.directory.describe` 响应是通用 `cx.schema.service_describe.v1` 的 **superset overlay**。Directory describe MUST 在通用 `service_describe` 基础上 extend 以下字段集，作为 directory-specific 字段权威列表：(a) `resource_types[]` 与 `discovery_profiles[]`（资源类别与索引 profile）；(b) `restricted_query_proof`（是否需要 holder-approved proof）；(c) 本节下表列出的 9 个 ingest 字段。`../sync/service-http-binding.md` 中所有 `cx.directory.describe` operation row 引用本节作为字段 superset 的权威定义，不另列重复表；任何 directory-specific 字段调整 MUST 先在本节落地。

Directory MUST 在 `describe` 响应中暴露 ingest 能力：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ingest_modes` | `array<push \| pull>` | 本 directory 支持的模式，至少一个。 |
| `accept_policy_kind` | `enum(open, allowlist, trust_root_signed, operator_review)` | `open` = 任意签名资源；`allowlist` = 资源 DID 在显式白名单；`trust_root_signed` = 需要 trust anchor 背书；`operator_review` = 人工审核。 |
| `accept_policy_ref` | `object?` | 描述如何获得接入资格的可读 ref（URL / DID / governance contact）。 |
| `default_ttl_seconds` | `int` | 默认 TTL。 |
| `max_ttl_seconds` | `int` | TTL 上限，MUST ≤ 2,592,000。 |
| `revalidation_grace_seconds` | `int` | TTL 到期宽限。 |
| `accepted_resource_kinds` | `enum[]` | 本 directory 接受的资源类别子集。 |
| `accepted_did_methods` | `string[]` | 接受的 principal/governance DID method。 |
| `takedown_contact` | `did \| url?` | operator takedown 时的通知 / 申诉入口。 |
| `rate_limits` | `object?` | per-DID / per-org / per-IP 配额上限的可读描述。 |

### 8.10 Anti-abuse

ingest 通道 MUST 防御：

- **Replay**：同一 `(resource_id, as_of)` 重复 announce MUST 幂等（返回原 `announce_id`）；过期 timestamp 的 announce MUST 拒绝（`signature_stale`，`as_of` 与服务端时间偏差 > 5 min）。
- **DID 抢占**：首次 ingest 某 DID 时 MUST 全量验证 DID document + governance key history；不允许仅凭 `did:web` 域名解析跳过 webvh history / witness 校验。
- **Quota burning**：Directory MUST 对 per-resource、per-Principal Server、per-IP 限流；超限返回 `rate_limited`。
- **Source-ref 伪造**：Directory MUST 拒绝 `source_refs` 中包含本 Directory 不能从声明的 Principal Server 解析得到的 event id 的 announce。
- **撤销规避**：Directory MUST NOT 接受 `as_of` 早于已记录 withdraw 时间的 announce（`takedown_in_force`）。
- **Policy rollback**：Directory MUST 拒绝 `discovery_state` 的 `policy_revision` 严格小于当前已索引版本的 announce（`policy_revision_rollback`）。

Directory operator MAY 维护资源黑名单（abuse、垃圾、法律）；命中黑名单时 MUST 直接返回 `accept_policy_denied`，不得进入 ingest 流程后再静默丢弃。

## 9. Service Surface

Recommended operations：

```text
GET  /api/v1/directory/describe
POST /api/v1/directory/search-realms
POST /api/v1/directory/resolve-realm
POST /api/v1/directory/search-organizations
POST /api/v1/directory/resolve-organization
POST /api/v1/directory/search-actors
POST /api/v1/directory/search-users
POST /api/v1/directory/resolve-handle
POST /api/v1/directory/list-handles-for-subject
POST /api/v1/directory/private-contact-discovery
POST /api/v1/directory/announce
POST /api/v1/directory/withdraw
POST /api/v1/directory/push/register
```

字段级定义：

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `cx.directory.describe` | 无 | 无 | `service_did: did`; `resource_types: string[]`; `discovery_profiles: string[]`; `restricted_query_proof: boolean?`；以及 §8.9 全部 ingest 字段 | `public_metadata`；可限流。 |
| `cx.directory.search_realms` | 无 | `query: string`; `organization_did: did`; `source_realm_id: id`; `requester: did`; `proofs: proof[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 每条 result MUST 含 §9.1 normative 字段；其余按 §3 / §11 过滤；隐藏资源不得泄露存在性。 |
| `cx.directory.resolve_realm` | 至少一个：`realm_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proofs: proof[]` | `realm_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `join_candidates?: cx.schema.realm_join_candidate.v1[]` | `join_candidates[]` 是 v1 join 路由的规范字段；当 resolver 支持结构化 candidate 且调用方有权得到 join 路由时 MUST 给出调用方可用且经过 policy 过滤的候选 ingress service。若隐私策略不能披露 candidate，响应 MUST 省略 `join_candidates[]`；客户端在取得候选列表前不得提交 join material。invite / restricted / secret Realm 对未授权请求使用统一 `not_found`。 |
| `cx.directory.resolve_target` | `address: string`（object-addressing grammar） | `requester: did`; `proofs: proof[]`; `token: string` | `target_kind: enum(realm,flow,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; §9.1 全部通用字段 | `resolve_realm` 的对象级泛化（分享 Flow / Message / Realm 的深链解析）；realm 解析 MUST 委托同一 `resolve_realm` 路径，并继承 `join_candidates[]` 语义；携带 `token` 时 MUST 按 target descriptor 逐级校验再走 join-policy；未授权统一 `not_found`。完整 grammar / token 绑定 / 隐私规则见 [`object-addressing.md`](./object-addressing.md)。 |
| `cx.directory.search_organizations` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 仅返回公开或授权可发现组织。 |
| `cx.directory.resolve_organization` | 至少一个：`organization_did: did` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员、Realm 列表或服务拓扑。 |
| `cx.directory.search_actors` | 无 | `query: string`; `realm_id: id`; `organization_did: did`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 不得泄露 pairwise/private DID 或未披露组织账号。 |
| `cx.directory.search_users` | `body.query: string` | `body.realm_id: id`; `body.limit: int`; `body.intent: enum(mention,invite,member_add)` | `results: object[]` | mention autocomplete；受共同 Realm / directory policy 限制。结果 MAY 含 handle preview，但不得在未授权时披露 `subject` DID 或 `member_delivery_binding`。`query` 不得进入 URL、Referer 或未脱敏 access log。 |
| `cx.directory.resolve_handle` | `handle: string` | `expected_did: did`; `proof_challenge: string`; `intent: enum(lookup,mention,invite,member_add)`; `realm_id: id`; `requester: did`; `proofs: proof[]` | `did: did`; `subject: did`; `handle: string`; `verified: boolean`; `claims: object[]?`; `member_delivery_binding: object?`; `source_refs: id[]?`; `expires_at: timestamp?` | 受限 / 组织 handle 需要 presentation；响应 `handle` 是 canonical `user:domain`；投递服务 DID 只通过 `member_delivery_binding.recipient_service_did` 返回。 |
| `cx.directory.list_handles_for_subject` | `subject: did` | `realm_id: id`; `intent: enum(lookup,mention,invite,member_add)`; `requester: did`; `proof_challenge: string`; `proofs: proof[]`; `as_of: datetime`; `cursor: cursor`; `limit: int` | `subject: did`; `claims: object[]`; `primary_handle: string?`; `as_of: datetime`; `next_cursor: cursor?`; `has_more: boolean` | 已知 holder / principal DID 时列出当前 context 可见 signed handle claims；响应符合 `cx.schema.list_handles_for_subject_response.v1`，且 `claims[].subject` MUST 等于响应 `subject`。`subject` 不是 Realm `actor_id`。必须按 disclosure policy、issuer trust、audience 和 Realm intent 过滤。 |
| `cx.directory.private_contact_discovery` | 见 §6.3 | 见 §6.3 | 见 §6.3 | 见 §6；MUST 使用 blinded / padded identifier batch；不得返回原始 connection identifier、完整 profile、成员列表或关系图谱。 |
| `cx.directory.announce` | 见 §8.3 | 见 §8.3 | 见 §8.3 | 见 §8。 |
| `cx.directory.withdraw` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdrawal_ref: string`; `acked_at: timestamp` | `withdrawal_ref` 是 Directory-local audit reference，不是注册 typed ID；见 §8.7。 |
| `cx.directory.push.register` | `subscriber_did: did`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | 仅作为 pull 模式优化；不替代 §8.6 freshness 协议。 |

### 9.0 Handle 解析（normative）

Directory MAY 解析 `@alice:acme.example`、`alice@acme.example`、`alice:acme.example` 或 `acct:alice@acme.example` 这类 handle 输入。解析结果是**寻址证据**，不是成员资格、grant 或投递授权本身。已知 `subject` DID 但不知道当前 handle 时，调用方使用 `list-handles-for-subject`；该接口返回的是当前 context 可见 handle claim set，不是 profile 或 MemberIdentity event。

当 `intent ∈ {invite, member_add}` 且 Directory 返回 `member_delivery_binding` 时，响应 MUST 满足：

1. `subject` / `did` 是被寻址主体的 principal DID；两者同时出现时 MUST byte-for-byte 相同。
2. `handle` 是 canonical handle（`<localpart>:<domain>` 主形态）；UI 字符串不得作为验签输入。
3. `member_delivery_binding.recipient_service_did` 是 Principal Server service DID，且 claim issuer 对该 service DID 的使用有可验证授权。
4. `claims[]` 至少包含一个可验证 handle claim、VC presentation 或 signed directory claim，绑定 `handle`、`subject`、`member_delivery_binding.recipient_service_did`、issuer、`audience`、`created_at`、`expires_at`。
5. claim `audience` MUST 等于请求中 `realm_id` 或邀请方 service DID 之一；不一致 MUST 返回与"无可披露 claim"不可区分的统一拒绝。
6. `member_delivery_binding` 只能作为构造 `cx.member.state{membership="join"}.delivery_binding` 的输入；`member_delivery_binding.binding_source` 不得是 `did_document_default`；接收方 reducer 仍 MUST 按 Join Policy 独立验证。

Directory MUST NOT：

- 因为某个 Principal Server 本地存在账号就直接披露 `member_delivery_binding.recipient_service_did`。
- 向无权请求方泄露组织内部 handle 与 DID / service DID 的映射。
- 把 handle 解析结果缓存为全局 actor routing；缓存必须绑定 `handle`、claim digest、audience / scope、requester policy 与 expiry。
- 执行 join、签发 invite token 或授予 Realm capability；Directory 只返回可验证寻址证据。

### 9.1 通用结果字段（normative）

每条 search / resolve 结果 MUST 包含：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `as_of` | `timestamp` | Directory 上次刷新该条目的时间。 |
| `source_refs` | `id[]` | 真相源 event id；客户端可据此回 Principal Server 验签。 |
| `policy_revision` | `string?` | discovery state 的 effective revision；便于跨 Directory 对账。 |
| `stale` | `boolean?` | TTL 过期且未续约时为 `true`，客户端 SHOULD 仅作参考。 |
| `divergent` | `boolean?` | 与同一资源的另一 Directory 视图不一致时为 `true`（实现可选检测）。 |
| `join_candidates` | `cx.schema.realm_join_candidate.v1[]?` | Realm join / invite-accept / knock 的候选 ingress service 列表。`resolve_realm` 与 realm-target `resolve_target` 在 resolver 支持结构化 candidate 且调用方有权得到 join 路由时 MUST 给出；search 结果 MAY 省略，客户端 join 前再 resolve。没有 `join_candidates[]` 的响应不能直接用于提交 join material。 |

#### 9.1.1 Realm Join Candidate（normative）

`join_candidates[]` 是 Contrix 对 Matrix `via` / candidate resident servers 模式的 Realm 级对应物：它是路由提示，不是授权证明。客户端 MAY 通过列表中任一合格候选提交 `cx.invite.accept`、`cx.member.state{membership="join"}`、`cx.member.state{membership="knock"}` 或 profile 声明的 application receipt；协议不要求必须经邀请者所在 Principal Server 加入。

每个 candidate MUST 符合 [`cx.schema.realm_join_candidate.v1`](../../artifacts/schemas/realm-join-candidate.schema.json)，并满足：

1. `realm_id` MUST 等于解析结果的 canonical Realm ID。
2. `service_did` MUST 是 service DID，不是用户 / 成员 principal DID；调用方在传输前 MUST 重新解析 DID Document，并确认 endpoint 支持 candidate 声明的 `operations`。
3. `operations` MUST 包含 `cx.events.submit`；缺失时不得用于 join-side submit。
4. `expires_at` 过期、`stale=true`、或 `policy_revision` / `source_refs` 与真相源不一致时，客户端 MUST 重新 `resolve_realm`，不得继续使用缓存 candidate。
5. Candidate 只决定"把 join material 交给哪一个服务"；最终是否接受仍由 Realm auth state、Join Policy、capability、invite / review 链、event signature 和 reducer 校验决定。
6. `member_delivery_binding.recipient_service_did` 与 `join_candidates[].service_did` 是两个不同方向：前者是成员加入后自己的投递服务，后者是本次加入 Realm 的 ingress service。实现 MUST NOT 从一个字段推导另一个字段。
7. Directory / invite link MAY 按 requester、join_rule、discoverability、anti-enumeration policy 裁剪 candidate 数量；不得因 candidate 列表泄露完整成员 Principal Server 拓扑。

客户端选择算法 SHOULD 按 `priority` 升序，再按本地可达性与 `service_did` 稳定排序。候选不可达、返回 `not_found`、`policy_denied`、过期 / stale 诊断或等价 fail-closed 错误时，客户端 MAY 尝试下一个未过期候选；收到新的 `join_candidates[]` 诊断时 MUST 用新列表替换旧列表。所有重试 MUST 使用同一 canonical `realm_id`，不得把失败重试重定向到另一个 Realm。

客户端在以下情况 MUST 回真相源验签后再 act：

- 准备执行 join、capability 请求或 invite 接受
- 跨 Directory 看到 `policy_revision` 不一致或 `divergent=true`
- 收到 `stale=true` 的关键条目（policy / membership / endorsement）

### 9.2 Search / Resolve 示例

`search-realms` 请求（非完整 schema）：

```json
{
  "query": "release",
  "search_scope": {
    "organization_did": "did:web:acme.example",
    "source_realm_id": null
  },
  "requester": "did:web:alice.example.com",
  "proofs": [
    "cx:presentation:..."
  ],
  "limit": 20,
  "cursor": null
}
```

Result：

```json
{
  "results": [
    {
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "title": "Release Coordination",
      "summary": "Public release coordination",
      "discoverability": "listed",
      "join_rule": "knock_restricted",
      "history_visibility": "joined",
      "owning_organizations": [
        "did:web:acme.example"
      ],
      "preview_ref": "cx:event:<uuid>",
      "join_candidates": [
        {
          "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
          "service_did": "did:web:principal.acme.example",
          "service_type": "principal_server",
          "role": "primary",
          "endpoint": "https://principal.acme.example/api/v1",
          "operations": [
            "cx.events.submit",
            "cx.events.query"
          ],
          "join_methods": [
            "knock",
            "restricted_join"
          ],
          "priority": 0,
          "source": "directory_ingest",
          "source_refs": [
            "cx:event:36531ccc-395a-7455-9880-000000000000"
          ],
          "as_of": "2026-05-10T07:55:12Z",
          "expires_at": "2026-05-10T08:05:12Z"
        }
      ],
      "as_of": "2026-05-10T07:55:12Z",
      "policy_revision": "01JTV0KQ7K5ZP4VN6C9WEZK2X1",
      "source_refs": [
        "cx:event:36531ccc-395a-7455-9880-000000000000",
        "cx:event:36531cd0-e580-7bb1-a8ab-310000000000",
        "cx:event:36531c0c-4155-7fd5-a082-b15662000000"
      ]
    }
  ],
  "next_cursor": null
}
```

未授权对隐藏资源的精确 resolve SHOULD 返回：

```json
{
  "ok": false,
  "error": {
    "code": "not_found",
    "message": "not found"
  }
}
```

实现 SHOULD 对"不存在"与"未授权访问的隐藏资源"使用相同的 status、相同时延等级与相同响应结构。

## 10. Parent Realm 与 Organization Directory

Realm 层级 MAY 协助发现，但 parent 成员资格不授予 child 成员资格或 child 读权限。

规则：

- Space hierarchy MAY 列出跨 Realm child Space 预览，但每个 child Space 仍按自身 `realm_id` 的 discoverability 与 caller authorization 独立裁剪。Realm link graph 不提供通用 parent/child directory expansion。
- Organization 目录 MAY 列出 Realm 预览，仅当 Realm discovery policy 允许组织目录列出且组织背书有效时成立。
- 把 Realm 从组织目录中移除不会撤销成员资格或删除数据。
- 撤销 `cx.realm.organization` 背书 MUST 使官方目录徽章在目录刷新后被移除。

## 11. 安全要求

目录与发现实现 MUST 防御：

- Realm id enumeration
- alias guessing
- member count probing
- hidden organization probing
- private handle correlation
- pairwise DID correlation
- raw connection identifier leakage
- private contact graph reconstruction
- timing side channels that reveal hidden existence
- stale official badge after organization endorsement revocation
- announce replay 与 timestamp skew（§8.10）
- DID hijack via announce（首次 ingest 必须全量验证 DID method history / governance key）
- takedown spoofing（仅 Directory operator 与 governance key 持有方有撤销权；audit log 必须区分两者）
- policy revision rollback（拒绝 `as_of` / `policy_revision` 早于已索引值的 announce）
- cross-directory poisoning（每个 Directory 独立验签；不接受其他 directory 转发的索引内容作为权威）
- shadow grant（Directory MUST NOT 签发 invite / capability / session credential）

在高隐私部署中，客户端 SHOULD 优先使用 invite 链接或加密的带外邀请，而不是目录搜索。

## 12. Conformance

Directory-capable implementations MUST test：

**Query 面**

- `cx.vector.directory.public_realm_search.v1`：public Realm search。
- `cx.vector.directory.organization_search.v1`：listed organization directory search。
- `cx.vector.directory.restricted_claim_presentation.v1`：restricted search with valid and invalid claim presentation。
- `cx.vector.directory.unlisted_exact_resolve.v1`：unlisted exact resolve。
- `cx.vector.directory.invite_not_found_blinding.v1`：invite-only indistinguishable not_found。
- `cx.vector.directory.resolve_target_blinding.v1`：`cx.directory.resolve_target` unauthorized / nonexistent / undiscoverable targets return byte-identical `not_found` and do not reveal target kind, Realm id, object id, timing class or preview metadata。
- `cx.vector.directory.organization_badge_verification.v1`：official Realm verification through `cx.realm.organization`。
- `cx.vector.directory.pairwise_did_exclusion.v1`：hidden pairwise DID exclusion。
- `cx.vector.directory.stale_result_rejection.v1`：stale result rejection after discovery policy update。
- `cx.vector.psi.no_reachability_metadata.v1`：private contact discovery does not disclose raw connection identifiers、reachability proof、profile、成员列表或关系图谱。
- `cx.vector.directory.result_common_fields.v1`：search / resolve result MUST carry §9.1 normative 字段（`as_of`、`source_refs`、`policy_revision`；支持结构化 candidate 且可披露 join 路由的 resolve 必含 `join_candidates[]`）。

**Ingest 面**

- `cx.vector.directory.announce_bidirectional_opt_in.v1`：announce accepted when directory DID listed in `directory_services` and signature valid。
- `cx.vector.directory.announce_directory_not_authorized.v1`：announce rejected with `directory_not_authorized` when directory DID NOT listed。
- `cx.vector.directory.announce_bad_signature.v1`：announce rejected with `invalid_signature` on bad `discovery_state.proof`。
- `cx.vector.directory.announce_signature_stale.v1`：announce rejected with `signature_stale` when `as_of` skew > 5 min。
- `cx.vector.directory.policy_revision_rollback.v1`：announce rejected with `policy_revision_rollback` when `as_of` earlier than indexed entry。
- `cx.vector.directory.accept_policy_denied.v1`：announce rejected with `accept_policy_denied` when resource outside policy。
- `cx.vector.directory.reannounce_idempotent_ttl.v1`：re-announce idempotent on `(resource_id, as_of)`，TTL 正确续约。
- `cx.vector.directory.pull_mode_refresh_verification.v1`：pull-mode ingest verifies signed discovery state on every refresh。
- `cx.vector.directory.ttl_expiry_removal.v1`：TTL expiry marks entries `stale=true`，after grace + 24h removed。
- `cx.vector.directory.withdraw_blinded_not_found.v1`：withdraw stops disclosure within ≤ 1h，subsequent resolve returns indistinguishable `not_found`。
- `cx.vector.directory.operator_takedown_audit.v1`：operator takedown writes audit log with `operator_takedown` marker and notifies governance contact。
- `cx.vector.directory.takedown_reannounce_rejected.v1`：subsequent announce after takedown rejected with `takedown_in_force`。

**PSI 面**

- `cx.vector.psi.oprf_two_round_shape.v1`：private contact discovery MUST use the §6.2 two-round OPRF set-membership flow。
- `cx.vector.psi.padding_and_cardinality.v1`：batch size、dummy padding、result cardinality、failure response shape and timing do not reveal match count。
- `cx.vector.psi.quota_blinded_denial.v1`：`max_psi_queries_per_window` denial has the same wire shape / delay class as policy-denied or no-match cases。
