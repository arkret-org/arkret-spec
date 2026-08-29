---
title: Discovery and Directory
status: candidate
normative: true
stability: v1
updated: 2026-07-02
see_also:
  - ../governance/history-visibility.md
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 需要明确区分三件事：

- 资源是否可被发现。
- 资源是否可被预览。
- 主体是否可加入、读取或写入资源。

发现不等于读取，读取不等于加入，加入不等于写入。实现 MUST NOT 用 `join_rule` 或 `history_access` 代替 discoverability policy。

本文定义 Realm、Organization、Actor 和 Applet 的发现模型、目录服务和防枚举要求。

## 2. 发现级别

`discoverability` 取值：

| 值 | 含义 |
| --- | --- |
| `public` | 可被公共目录索引和搜索。 |
| `listed` | 可在指定目录、组织页、源 Realm 或受信目录中列出，但不一定进入全网公共搜索。 |
| `restricted` | 只有满足可验证条件的请求方可发现，例如组织成员、受邀者、共同 Realm 成员或持有特定 claim 的主体。 |
| `unlisted` | 不进入目录搜索；知道精确 id、alias、邀请链接或 source Realm edge 的主体 MAY 尝试解析。 |
| `invite_only` | 未被邀请或未持有 invite proof 的主体不得得知其存在；查询 MUST 返回与不存在相同的错误（规范强度见 §3）。 |
| `secret` | 仅本地或端到端加密上下文中可见；目录、Principal Server sync surface 和受托 search / projection 服务 MUST NOT 公开可枚举 metadata（规范强度见 §3）。 |

默认值：

- 新 Realm 默认 `invite_only`。
- 新 Organization profile 默认 `listed`，但 MAY 设置为 `restricted` 或 `unlisted`。
- Pairwise / private DID 默认 `secret`。
- Public Persona DID 默认 `public` 或 `listed`，由 holder policy 决定。

## 3. Realm Discoverability

Realm discovery policy SHOULD 由 `ak.realm.discovery` state event 表达：

```json
{
  "kind": "ak.realm.discovery",
  "payload": {
    "value": {
      "discoverability": "listed",
      "directory_visibility": {
        "public_directory": false,
        "organization_directory": true,
        "source_realm_directory": true
      },
      "allowed_discoverers": [
        {
          "selector_kind": "claim",
          "claim_kind": "organization_membership",
          "organization_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
          "issuer": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example"
        }
      ],
      "directory_services": [
        "ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"
      ],
      "anti_enumeration": {
        "unlisted_exact_alias_required": true,
        "member_count_mode": "bucketed",
        "not_found_blinding": true,
        "member_count_hysteresis": {"ratio": 0.15},
        "member_count_min_residence_ms": 300000
      }
    }
  }
}
```

`ak.realm.discovery` 的 payload class 是 closed `realm_discovery_payload`：策略内容整体位于 whole-value
`value` 内，`state` / `reason` 是可选的诊断成员。**MUST NOT** 把策略字段平铺到 payload 顶层，也 **MUST NOT**
在 payload 内携带 detached `proof`——Event envelope 的 producer proof 已经覆盖同一批 canonical bytes
（§8.3 已明令废除 payload 内含 proof 的形态）。

规则：

- `discoverability=public` 的 Realm MAY 被公共目录服务索引。
- `listed` Realm MUST 仅出现在 `directory_visibility` 或 `directory_services` 明确允许的目录中。
- `restricted` Realm MUST 在返回搜索结果前要求目录查询授权。
- `unlisted` Realm MUST NOT 出现在关键字搜索，但在 policy 允许时 MAY 通过精确 id / alias / 签名 invite / source Realm edge 解析。
- 未授权 subject 对 `invite_only` 与 `secret` Realm 的查询 MUST 返回 `not_found` 或与其不可区分的响应。
- 在未单独授权时，目录结果 MUST NOT 包含事件历史、成员列表、policy 原文、MLS 状态、隐藏 parent/child edge 或完整组织治理链。

`discoverability=restricted` 的 Realm 查询授权使用 `DirectoryRestrictedClaimPresentation`（wire schema：`directory-operations.schema.json#/$defs/directory_restricted_claim_presentation`），由 `search_realms` / `resolve_realm` 请求体的 `claim_presentations[]` 承载；请求体同时 MAY 携带 `proof_challenge`，presentation 的 `nonce` MUST 等于该 challenge。presentation MUST 绑定 `kind="ak.directory.restricted_claim_presentation.v1"`、签发方 `iss`、`verification_method`、目标 Directory service `audience`、防重放 `nonce`、被披露的 `claim`、可选 `expires_at`、`created_at` 与 `jws`。Directory service MUST 验证 issuer key、JWS、audience、nonce、claim subject/requester、过期时间与 resource policy；任一失败 MUST fail closed，且 `resolve_realm` 对未授权 restricted Realm MUST 返回与不存在不可区分的 `not_found`。Realm restricted discovery MUST NOT 把 Event `Proof` 当作 claim presentation 解析。

`anti_enumeration.member_count_mode` 取值 normative：

| 模式 | 行为 |
| --- | --- |
| `exact` | 返回精确成员数；仅在 `discoverability ∈ {public, listed}` 时允许。 |
| `bucketed` | 返回**封闭 bucket** 之一：`1-10` / `11-50` / `51-100` / `101-500` / `501-2000` / `2000+`。Directory 实现 MUST 使用本 bucket grid，不得自定义粒度（防止粒度差异成为枚举侧信道）。请求方收到不在此枚举的 bucket 字符串 MUST 视作 `response_invalid` 并丢弃。**边界振荡侧信道（normative）**：真实成员数在两个 bucket 边界附近抖动时，反复观察 bucket 翻转可被用来逼近精确成员数。因此 bucket 输出 MUST 带迟滞（hysteresis）**且** 最小驻留时间，且两个下界均为 MUST，不得用"声明极小窗口 / 零带宽"架空：bucket 一旦切换，MUST 在 policy 的 `anti_enumeration.member_count_min_residence_ms` 或本段默认的最小驻留窗口内保持稳定，不得在边界两侧逐次 query 即翻转。该最小驻留窗口 MUST ≥ max(当前 directory entry 的刷新 TTL，成员数 query 的可观察刷新间隔)；声明小于此下界的窗口 MUST 被视为不合规，未声明时采用该下界。迟滞带宽由 `anti_enumeration.member_count_hysteresis.absolute` 或 `.ratio` 声明；两者同时出现时取更严格（更大）的有效带宽。实现 MUST 仅在真实计数越过 bucket 边界、并持续超过该 policy 声明或本段默认的迟滞带宽后才切换输出 bucket。默认迟滞带宽 = max(2, ceil(相邻有限 bucket 跨度较小者 × 0.10))；policy MAY 声明更大的绝对值或比例，但不得低于该默认值。**开放上界 bucket(`2000+`)的迟滞参照(normative)**:`2000+` 无有限跨度，故其相邻边界(`501-2000` 与 `2000+` 之间)的迟滞带宽 MUST 取相邻有限 bucket `501-2000` 的跨度(1500)作为参照基数，按上述默认或 policy 值计算。无论哪种，该边界的迟滞带宽 MUST 为正且不得为 0。 |
| `omit` | 不返回成员数；任何隐含的 hint（如返回组员数组的 length）也 MUST 被裁剪。 |

`restricted` / `unlisted` / `invite_only` / `secret` Realm 的 `member_count_mode` 默认 `omit`；显式声明 `bucketed` 时必须遵守上述 bucket grid 与迟滞约束。

**Preview 成员数字段与 `member_count_mode` 的绑定（normative）**：`ak.realm.preview_policy.value.fields` 中的成员数字段（canonical 名 `member_count_bucket`）的存在性与形态 MUST 由 effective `member_count_mode` 决定，二者不得各自独立：

| effective `member_count_mode` | `preview.fields` 中成员数字段的存在性与形态 |
| --- | --- |
| `omit` | preview MUST NOT 含任何成员数字段；即使 `preview.fields` 列出 `member_count_bucket`，directory 在产出 preview 时 MUST 裁剪该字段（与表中 `omit` 行"任何隐含 hint 也 MUST 被裁剪"一致）。 |
| `bucketed` | preview 成员数以 `member_count_bucket` 承载，取值 MUST 是上方 bucket grid 之一，并遵守迟滞 / 最小驻留约束。 |
| `exact` | preview 成员数以 `member_count_bucket` 字段承载精确计数（整数值），仅在 `discoverability ∈ {public, listed}` 时允许；字段名保持 `member_count_bucket` 不变，避免不同 mode 暴露不同 wire 字段名而成为枚举侧信道。 |

字段名在三种 mode 下统一为 `member_count_bucket`；请求方 MUST 按 effective `member_count_mode`（而非字段名）解释其语义。directory MUST NOT 因 `preview.fields` 显式列出该字段而越过 `member_count_mode` 披露上限。

**`member_count_bucket` 的 wire 类型（normative）**：该字段是 `string | int` union——`bucketed` mode 下 MUST 是上方 bucket grid 之一的封闭枚举字符串；`exact` mode 下 MUST 是非负整数（精确成员数）。请求方 MUST 由 effective `member_count_mode` 决定按字符串枚举还是整数解析，不得仅凭值类型推断 mode。两种 mode 下 preview 输出（`realm_preview` / `stripped_state`）中该字段的取值示例：

`bucketed` mode 下为封闭枚举字符串：

```json
{ "title": "Acme", "member_count_bucket": "51-100" }
```

`exact` mode（仅 `discoverability ∈ {public, listed}`）下为精确成员数整数：

```json
{ "title": "Acme Public", "member_count_bucket": 342 }
```

**`member_count_bucket` 属 §9.1 一致性字段，MUST 携带 effective mode（normative）**：`member_count_bucket` 是 union 字段（`bucketed` 下为枚举字符串、`exact` 下为整数），其语义依赖 effective `member_count_mode`。若仅凭值类型推断 mode，则跨 Directory 对账（§7.3 不变量 2 Pluralizable、§9.1 一致性字段）会因 mode 解析歧义而无法判定"两家 Directory 是否一致"。因此：

- `member_count_bucket` 一旦在 preview / 结果中出现，即**属于 §9.1 normative 一致性字段**，纳入同一资源跨 Directory 的一致性比对（针对同一 `(resource_id, source_refs frontier, policy_revision)`）。
- 携带 `member_count_bucket` 的 search / resolve 结果与 preview **MUST 同时携带 effective `member_count_mode`**（取值 `exact` / `bucketed` / `omit` 之一，`omit` 时不出现该字段），使请求方与对账方据带内 mode（而非带外推断或值类型猜测）确定解析路径并比对；缺失 effective mode 的结果 MUST 视作 `response_invalid` 并丢弃。
- 跨 Directory 对账时，`member_count_bucket` 值与其 effective mode 必须一并比对；两家 Directory 对同一资源给出不同 mode 或不同 bucket 时 MUST 标记 `divergent=true`（§7.3 不变量 2）。

`join_rule` 只控制加入流程。公开可发现的 Realm MAY 仍要求 invite、knock 或 restricted join。不可发现的 Realm MAY 对持有私有链接的成员保持 `join_rule=public`，但除非配套强反垃圾策略，否则不推荐。

`history_access` 只控制历史读取范围。`discoverability=public` MUST NOT 隐含 `history_access=all_history_for_current_members`。五个 history level 的 reader class、invite / join 时点、removal 后 backfill 和 E2EE key share 语义以
[`../governance/history-visibility.md`](../governance/history-visibility.md) 为准；本文件只定义 discovery / join / history 三 gate 的组合关系。

### 3.0 三个独立 Gate（先于矩阵理解）

`discoverability`、`join_rule`、`history_access` 是三条**独立判定**的 gate，作用面互不替代：

```mermaid
flowchart TB
    subgraph Q ["三个独立 gate（实现 MUST 分开判断）"]
        direction LR
        D["1. Discoverability<br>能不能发现?<br>public / listed / restricted<br>unlisted / invite_only / secret"]
        J["2. Join Rule<br>能不能加入?<br>public / invite / knock<br>restricted / knock_restricted / closed"]
        H["3. History Access<br>当前成员能否恢复加入前历史?<br>since_join /<br>all_history_for_current_members"]
    end

    Search["Directory / 搜索 / preview<br>受 Discoverability 决定"]
    Join["加入 / knock / invite<br>受 Join Rule 决定"]
    Read["历史读取范围<br>受 History Visibility 决定"]

    D --> Search
    J --> Join
    H --> Read

    R1["不可发现 ≠ 不可加入<br>unlisted + 已知 invite link → 仍可加入"]
    R2["可加入 ≠ 可见全部历史<br>history_access 独立收窄"]
    R3["可发现 ≠ 可恢复全部历史<br>discoverability=public 不改变 history_access"]

    D -. 与 J 独立 .-> R1
    J -. 与 H 独立 .-> R2
    D -. 与 H 独立 .-> R3
```

读图要点：

- **Discoverability** 只控制资源是否能在搜索 / Directory / preview 里出现；不决定加入资格，也不决定历史读取范围。
- **Join Rule** 只控制加入流程；不可发现的 Realm 也可以是 `join_rule=public`（持有私链接即可加入），公开 Realm 也可以是 `join_rule=invite`。
- **History Visibility** 只控制 reader 对历史 Event range 的读取资格；与前两者完全正交。E2EE Realm 中它不自动授予旧 epoch key。
- 任何把 `discoverability` 当作 `join_rule` 或 `history_access` 简写的实现都是错误——下表 §3.1 锁定了允许的组合。

### 3.1 `discoverability × join_rule × history_access` 兼容矩阵（normative）

下表声明 v1 在三组维度上**允许 / 禁止 / 不推荐**的组合。`✓` = 允许；`!` = 允许但 SHOULD 在 Realm create 时显示警告；`✗` = MUST 拒绝（任何写入三轴 cell 的 reducer 在 accept 时返回 `policy_combination_invalid`）。本表不替代 §3 与上方各 enum 的语义；当某条规则与本表冲突时，更严格者（拒绝/警告）优先。

| discoverability ↓ \ join_rule → | `public` | `invite` | `knock` | `restricted` | `knock_restricted` | `closed` |
| --- | --- | --- | --- | --- | --- | --- |
| `public` | ✓ | ✓ | ✓ | ✓ | ✓ | ! |
| `listed` | ! | ✓ | ✓ | ✓ | ✓ | ! |
| `restricted` | ! | ✓ | ✓ | ✓ | ✓ | ✓ |
| `unlisted` | ! | ✓ | ! | ✓ | ✓ | ✓ |
| `invite_only` | ! | ✓ | ✗ | ✓ | ✗ | ✓ |
| `secret` | ! | ✓ | ✗ | ✗ | ✗ | ✓ |

`history_access` 与上述任一组合正交，且始终只有 `since_join | all_history_for_current_members` 两个当前值。它只控制当前成员的私有历史恢复范围；discoverability 不能授予历史读取或 exporter secret。即使 `discoverability=public`，服务仍 MUST 按 exact current membership incarnation 与该 scope 的 history gate 过滤，并限制 lazy member preview 防止枚举。plaintext scope 仍按公开正文读取合同工作；`mls_rfc9420` 只允许 `since_join`，exporter scope 才可使用二态并通过 private history-key surface 交付。

本矩阵是 cell-level 不变量：实现 MUST 在 `ak.realm.policy_bundle`、`ak.realm.discovery`、`ak.realm.join_rule`、`ak.realm.history_access` 或任何其它写入三轴之一的 reducer 接受前，以同一 basis 的 post-write effective 三轴状态执行本表。使组合落入 `✗` 时 MUST 返回 `policy_combination_invalid` 并保留全部旧值；不得因写入只触及一个 cell 而跳过。本表是 v1 wire 互操作的最小集，profile 可以**收紧**但不得放宽。

### 3.2 Preview / Peek 与 History Visibility 的关系

Directory preview 不是历史读取的快捷方式。目录结果或 exact resolve 可以返回的最小 metadata 只由 `ak.realm.preview_policy` 声明；`ak.realm.discovery` 不再包含第二套 `preview` 字段。preview policy 不得单独授权正文历史、成员列表、policy 原文、隐藏 edge 或 E2EE 明文。

当实现要返回 directory card / stripped state、支持 Matrix-style "peek before join"、invitee 进入前历史片段、或带 token 的 object preview 时，Realm MUST 声明有效 `ak.realm.preview_policy`，并按
[`../governance/history-visibility.md`](../governance/history-visibility.md) §4 执行 preview audience、字段、历史范围、E2EE 和 anti-enumeration 规则。没有 `ak.realm.preview_policy` 时：

- Directory MUST NOT 返回 directory card、stripped state、history stub 或 history snippet；只可返回不可区分的最小定位结果。
- `resolve_realm` / `resolve_target` 对未授权 preview MUST 返回与不存在不可区分的 `not_found`。
- `history_access=all_history_for_current_members` 仍不允许 Directory 自动扩展 preview 字段；完整历史读取必须走 Events / backfill surface，并继续执行 capability、retention、redaction 和 plaintext-visible service 检查。

## 4. Organization 可发现性

Organization discovery policy SHOULD 通过组织 profile 状态或 governance registry 记录表达：

```json
{
  "kind": "ak.organization.discovery",
  "payload": {
    "organization_principal_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
    "value": {
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
        "ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"
      ]
    }
  }
}
```

`organization_principal_id` 是 cell subject 且必须是 `did_core_id`；策略内容位于 whole-value `value` 内。
payload **不携带** detached `proof`：治理签名就是该 Event 的 envelope proof（§8.3）。

Organization 可以是公开的、受限的或不可列举的。实现 MUST NOT 因为组织 DID 可解析，就公开组织成员列表、官方 Realm 列表、服务拓扑或治理策略全文。

客户端展示组织搜索结果时 SHOULD verify：

1. Organization DID 可解析。
2. discovery policy 或 profile 由组织 DID / governance service 签名。
3. 如果结果声称包含 official Realm，仍需验证每个 Realm 的 `ak.realm.organization` 背书。
4. 目录服务 DID 被组织 DID 声明或被本地 trust policy 接受。

### 4.1 Actor / Applet / Handle Discovery State

`ak.actor.discovery`、`ak.applet.discovery` 与 `ak.handle.discovery` 是 v1 active discovery state event kind。它们与 `ak.organization.discovery` 使用同一组目录 ingest 规则：resource 自签名声明可发现性，Directory 只索引被 `directory_services[]` 明确列出的资源，且不得替 resource 重新签名或扩展披露范围。

这些 Event 的 payload class 是 closed `resource_discovery_state_payload`：顶层只有 `resource_id`
（cell subject）、whole-value `value` 与可选 `state` / `reason`。下表描述 `value` 内的成员：

| payload 位置 | 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- | --- |
| 顶层 | `resource_id` | `did_core_id` / canonical handle / applet id | required | 被发现资源的稳定标识，同时是 cell subject；actor 分支使用 `did_core_id`，不接受裸 DID。 |
| `value` | `resource_kind` | `enum(actor,applet,handle)` | required | 必须与 Event kind 后缀一致。 |
| `value` | `discoverability` | §2 enum | required | `public` / `listed` / `restricted` / `unlisted` / `invite_only` / `secret`。 |
| `value` | `directory_services` | `did_core_id[]` | required | 被允许索引该资源的稳定 Directory service `did_core_id` 列表。 |
| `value` | `profile_visibility` | `object` | optional | 每个预览字段的可见性；未列字段默认不披露。 |

payload **MUST NOT** 携带 detached `proof`：controller / governance 签名就是该 Event 的 envelope proof
（§8.3 已明令废除 payload 内含 proof 的形态）。

Actor discovery MUST NOT 暴露 pairwise/private DID、未披露组织账号或仅因共同 Realm 推断出的关系。Applet discovery MUST 只披露 registration 允许的 public metadata，不得暴露 private namespace、token、webhook secret 或租户内 endpoint。Handle discovery MUST 绑定 handle issuer、subject claim、audience 与过期时间；受限 handle 未满足 presentation / policy gate 时不得返回 subject `did_core_id` 或 `member_delivery_binding`。

## 5. Actor 与 Handle 可发现性

Actor / Principal 发现 MUST 尊重 holder 隐私：

- 公开 persona MAY 出现在公共用户目录中。
- Pairwise DID、私有 DID、设备 verification method / `device_id` 与隐私敏感的 agent DID 默认 MUST NOT 出现在公共目录中。设备自身没有 DID。
- Handle 搜索 MUST 仅返回绑定公开或 holder 已显式授权披露的 handle。
- Handle 搜索 / 解析若会暴露 `subject` DID 或 `member_delivery_binding`，MUST 额外满足 requester proof、intent、audience / challenge 和 issuer policy；共同 Realm 或同组织排序信号不得单独授权披露。`intent="contact_request"` 只表示调用方希望把 verified handle claim 用作 first-contact `handle_claim` introduction evidence，不构成 contact consent。这些受限 handle 解析的 not_found / unauthorized 分支 MUST 满足 §9.2 的失败不可区分（含**时延等同**）约束，不得因走完整校验失败与早退不存在产生可观测时序差。
- Controller-scoped agent selector（`@<controller-handle>/<agent_slug>`）解析若会暴露 agent DID 或 selector claim，MUST 满足 requester 已与该 agent 共享可见 scope，或 selector claim `visibility="public"` / 当前 `audience` 明确授权该 requester 与当前 `intent`（mention 场景为 `intent="mention"`）。未授权、slug 不存在、controller 不存在、agent 不可见、claim revoked / expired / ambiguous 等结果 MUST 使用不可区分失败（含 §9.2 的**时延等同**约束），避免按时序差分枚举 controller 的 agent 名单。
- Presence、common Realm、组织成员与联系人图谱 MUST NOT 通过搜索排序或自动补全泄露。

在共享 Realm 中查询未知 actor profile，仅允许在渲染已授权内容（如显示名、头像）所必需的范围内进行；MUST NOT 借此泄露无关 handle 或组织账号。

## 6. Private Contact Discovery

通讯录式发现比普通目录搜索更敏感。实现 MAY 支持 `ak.private_contact_discovery.v1`，用于在不上传明文通讯录、不让目录服务同时获得 requester DID 与目标 connection identifier 的前提下发现可联系主体。

### 6.1 Profile 目标

- Discovery Provider 不应同时获得 requester 的稳定 DID 和原始邮箱/手机号/用户名。
- 请求应使用 batch、padding、rate limit 和 time-bound proof，避免逐个枚举。
- 发现结果应返回最小可联系材料，而不是完整 profile 或关系图谱。
- 协议 MUST 定义"private discovery 能回答什么"——并显式声明不能回答什么——避免实现私自扩展导致隐私退化。

### 6.2 v1 core 形态：Set-Membership PSI（双轮 OPRF）

v1 core `ak.private_contact_discovery.v1` profile 明确限定为 **set-membership PSI**：客户端只能问"我已知的 connection identifier 集合中，哪些在 provider 的可联系集合内？"核心回答是命中位图。响应 MAY 在每个命中旁附带最小 invite/consent handoff stub，但该 stub 只能声明 consent state hash、grant/revoke 状态或下一步引导，且必须与未命中 / policy-denied 响应保持同样的 padding 与字段形态。响应 MUST NOT 附带 contact request handoff token、reachability claim、完整 profile、成员资格、Realm membership、读取权限或关系图谱。

实现 MUST 使用 RFC 9497 `modeVOPRF`（0x01）的两轮协议：

1. **配置与本地 padding**：客户端先读取 `ServiceDescribe.private_contact_discovery`，验证 `profile="ak.private_contact_discovery.v1"`、`oprf_mode="VOPRF"`、`ciphersuite="ristretto255-SHA512"`、当前 `public_key` / `key_epoch`、固定 `batch_item_count`、`proof_shape="single_batched_dleq"` 与其它必需字段。任一字段缺失、未知或不支持时 MUST fail closed。客户端把真实 canonical connection identifier 与 CSPRNG 生成的 dummy private input 混合并随机排列到**恰好** `batch_item_count` 项，真实 / dummy 位置映射只保留在本地；不得把真实项数量作为 wire 字段或让数组长度泄露它。
2. **Round 1 — Blind**：客户端对固定 batch 的每项执行 RFC 9497 VOPRF Blind，提交 `{batch_id, blinded_elements[]}`。Provider 对同序数组执行 batched VOPRF BlindEvaluate，返回等长 `evaluated_elements[]` 与覆盖整个数组的**一条** batched DLEQ proof。客户端用 describe 中同 `key_epoch` 的 `public_key` 验证 proof 后才可 unblind；验证失败 MUST 丢弃整批结果。
3. **Round 2 — Match**：客户端在第二个独立请求中按同序提交恰好 `batch_item_count` 项 `derived_prefixes[]`；v1 每项固定为 VOPRF output digest 的前 16 字节。Provider 仅在自己的 VOPRF-evaluated 可联系集合中比较，返回恰好 `batch_item_count` 位 `hit_bitmap`。无论命中数为 0、部分命中还是全部命中，数组 cardinality、排序、响应 body bucket 与延迟分布 MUST 相同。
4. **披露**：客户端只在 user 在 UI 中显式确认联系或发起邀请时，才向目标 principal 的 provider 披露自己的 DID、pairwise DID、presentation 或 connection identifier 原文。该披露走 §6 / consent-model 的 invite + consent 流程，不在 PSI 协议范围内。

OPRF 选择：

- v1 core 强制要求 RFC 9497 `modeVOPRF`（0x01），ciphersuite identifier 固定为 RFC 9497 §4.1 的 `ristretto255-SHA512`。mode 与 ciphersuite 是两个独立参数；实现 MUST 使用 RFC `CreateContextString(modeVOPRF, "ristretto255-SHA512")`，不得把旧的非标准 token `OPRF-ristretto255-SHA512` 当作 context identifier。
- Provider OPRF secret key MUST 周期轮换（默认 ≥ 7 天 / ≤ 90 天）；轮换后客户端持有的 derived 缓存自动失效，避免长期跨域关联。
- Provider MUST 在闭合 schema `ServiceDescribe.private_contact_discovery` 暴露 VOPRF public key、key epoch、固定 batch size、单批 proof shape、handoff shape、允许的 response buckets、预计算的 blind / match phase bucket、batch completion TTL、quota 参数和反枚举延迟分布。`batch_completion_ttl_seconds` 从 blind 成功准入时刻起定义精确的 batch 接纳区间；Provider MUST 在整个区间保留 pinned key epoch、public-key binding 与缓存，达到或超过 `admission_time + TTL` 后统一返回 `psi_batch_unavailable`。客户端也 MUST 把该 public key / epoch 与本地 batch state 一起保留到完成或 TTL 到期。

### 6.3 请求 / 响应形态（非完整 schema）

第一轮（blind）：

```json
{
  "profile": "ak.private_contact_discovery.v1",
  "phase": "blind",
  "batch_id": "ak:batch:0196429a-0000-7000-8000-000000000000",
  "ciphersuite": "ristretto255-SHA512",
  "key_epoch": 14,
  "blinded_elements": ["base64url-32bytes...", "... exactly batch_item_count entries ..."]
}
```

第二轮（match）：

```json
{
  "profile": "ak.private_contact_discovery.v1",
  "phase": "match",
  "batch_id": "ak:batch:0196429a-0000-7000-8000-000000000000",
  "key_epoch": 14,
  "derived_prefixes": ["base64url-16bytes...", "... exactly batch_item_count entries ..."]
}
```

第一轮响应（blind outcome）：

```json
{
  "profile": "ak.private_contact_discovery.v1",
  "phase": "blind",
  "batch_id": "ak:batch:0196429a-0000-7000-8000-000000000000",
  "ciphersuite": "ristretto255-SHA512",
  "key_epoch": 14,
  "evaluated_elements": ["base64url-32bytes...", "... exactly batch_item_count entries ..."],
  "evaluation_proofs": ["base64url-64byte-batched-dleq-proof..."],
  "derived_prefix_bytes": 16,
  "padding": "    "
}
```

- `evaluated_elements` MUST 与请求的 `blinded_elements` 等长且同序。
- `evaluation_proofs` 在 v1 MUST 恰好包含一条 64-byte RFC 9497 batched DLEQ proof；客户端以 describe 中当前 epoch 的 32-byte ristretto255 `public_key` 验证。
- `derived_prefix_bytes` 在 v1 MUST 为 16。
- `padding` 是只含 ASCII SP 的响应填充字段；精确 body bucket 规则见 §6.4。

第二轮响应（match outcome）：

```json
{
  "profile": "ak.private_contact_discovery.v1",
  "phase": "match",
  "batch_id": "ak:batch:0196429a-0000-7000-8000-000000000000",
  "key_epoch": 14,
  "hit_bitmap": [false, true, false, false],
  "handoff_stubs": [
    { "kind": "consent", "state": "unknown", "next_step": "no_action" },
    { "kind": "consent", "state": "no_consent", "next_step": "request_consent" },
    { "kind": "consent", "state": "unknown", "next_step": "no_action" },
    { "kind": "consent", "state": "unknown", "next_step": "no_action" }
  ],
  "padding": "    "
}
```

- `hit_bitmap` MUST 与 blind / match 数组具有相同的 `batch_item_count` cardinality 与位置顺序。
- `handoff_stubs_mode="always"` 时 `handoff_stubs` MUST 在每个响应中出现、与 `hit_bitmap` 等长，且未命中 / 逐目标拒绝位置携带相同 dummy stub；`handoff_stubs_mode="never"` 时每个响应都 MUST 省略该字段。不得按是否命中动态切换字段存在性。

quota denial（blind 阶段，HTTP 429 + `Retry-After` header）：

```json
{
  "type": "https://arkret.org/problems/psi_quota_exhausted",
  "title": "Psi quota exhausted",
  "status": 429,
  "detail": "psi quota exhausted for this device in the current quota window",
  "instance": "ak:request:0196429a-0000-7000-8000-0000000000aa",
  "padding": "    "
}
```

- 这是 §6.4 Class B 失败形态：标准 RFC 9457 Problem Details 的 PSI padding extension + canonical 错误码 `psi_quota_exhausted`；`Retry-After` 与精确 body / delay bucket 规则见 §6.4。
- quota denial 只在 blind 阶段出现；已被接纳的 `batch_id` 的 match 请求 MUST NOT 再因 quota 被拒。

### 6.4 规则

- Raw email、phone number、address-book label、local contact name 和未加盐低熵 hash MUST NOT 被发送给公共 Directory，包括第一轮的 OPRF input（OPRF Blind 已经做了 unlinkable 化，但实现仍 MUST 在客户端先做 normalization + canonical encoding，杜绝把明文写入 audit log）。
- Provider MUST 对 batch 大小、dummy padding、失败响应、计时和 result cardinality 做反枚举处理。**不可区分性分两类界定（normative）**：
  - **Class A（逐目标 outcome）**：目标不存在、不可发现、逐目标 policy-denied 与 OPRF mismatch MUST 统一编码为固定 cardinality 成功 outcome（`hit_bitmap`）中的未命中位，在 HTTP status、字段集合与字节形态上逐目标不可区分；MUST NOT 通过专用错误码、额外字段或逐目标延迟差暴露上述任何一种情形。
  - **Class B（整请求级失败）**：quota 耗尽与 batch 级 `policy_denied`（如 requester 被封禁、profile 未启用）MUST 使用带顶层 `padding` 的标准 RFC 9457 Problem Details；其内容只允许描述 requester / batch 自身状态，MUST NOT 携带逐目标信息。Class B 触发条件 MUST 只依赖 requester / batch 级状态，MUST NOT 依赖目标集合内容。quota 与初始 batch policy 准入发生在 blind 阶段；已接纳 batch 后发生的账号冻结等 requester 状态仍 MAY 在 match 阶段以 Class B 拒绝，但不得重新执行逐目标判断。
  - **固定请求 cardinality**：客户端 MUST 在发送前把 blind batch 填充到 describe 的精确 `batch_item_count`；Provider 对 cardinality 不等于该值的请求 MUST 在目标评估前以 `schema_violation` 拒绝。Provider 不得在收到可变长数组后自行追加 dummy 来声称隐藏了客户端原始 cardinality。
- **PSI HTTP entity-body bucket（normative）**：describe 固定 buckets `[4096, 16384, 65536, 262144]` bytes。对 blind / match 各 phase，Provider 分别构造该 phase 最大合法 200 success，以及每一种允许的 Class B RFC 9457 Problem Details / `PsiPaddedProblem` 最大投影（均令 `padding=""`），取其中 RFC 8785 JCS UTF-8 body 最大者，再选择能容纳它的最小 bucket `B_phase`；计算必须纳入 schema 允许的最大字符串转义长度。若无 bucket 可容纳，MUST NOT advertise 该配置。Provider MUST 分别把结果写入 `blind_response_bucket_bytes` / `match_response_bucket_bytes`，客户端与 runner MUST 重算并拒绝不是最小可容纳 bucket 的 describe。产生实际响应时，先对 `padding=""` 的完整对象执行 RFC 8785 JCS 并取 UTF-8 byte length `N`，再把 `padding` 设为恰好 `B_phase-N` 个 ASCII SP，最后再次执行 JCS 得到 wire body；由于 SP 在 JSON string 中不转义，最终 HTTP entity body 的实际 `Content-Length` MUST **恰好等于** describe 的 phase bucket。该 phase 的每个 200 success 与 Class B RFC 9457 Problem Details 都使用此算法。响应 MUST **省略 `Content-Encoding`**（即不应用任何 content coding）并设置 `Cache-Control: no-store, no-transform`；origin 与受控 gateway MUST NOT 压缩或改写 body。RFC 9110 将 `identity` 保留给 `Accept-Encoding`，因此实现 MUST NOT 发送 `Content-Encoding: identity`。`application/problem+json` 使用闭合的 `PsiPaddedProblem`，`padding` 是唯一 extension member，并满足同一算法；此 PSI surface 的 `type` MUST 为 `https://arkret.org/problems/<canonical_error_code>`，`status` MUST 与 HTTP status line 及 error registry 一致。该 endpoint 不因 content negotiation 旁路 padding 或改变错误语义。
- **反枚举 delay class（normative）**：describe 的 `anti_enumeration_delay={minimum_ms,jitter_ms,distribution="uniform"}` 定义 origin 从完成认证 / schema 校验到开始发送响应前的等待分布：`minimum_ms + UniformInteger(0..jitter_ms)`。同一 phase 的成功与 Class B 路径 MUST 调用同一 sampler；不得按错误原因选择不同 floor / jitter。Conformance runner MUST 检查配置路径一致，并在同机条件下对每类至少采样 30 次；success 与 Class B 的 p95 差异 MUST ≤ `max(50ms, jitter_ms/4)`。
- Provider MUST NOT 在第二轮返回 contact request handoff token、reachability proof、handle verified claim、完整 profile、组织成员资格、Realm membership 或读取权限。这些声明只能通过后续 contact / invite + consent 流程获得。既有最小 invite/consent handoff stub 只可声明 consent state hash、grant/revoke 状态或下一步引导，不得成为可直接创建 contact relation 的凭据。
- Private discovery 结果**仅** 证明"在 provider 当前可联系集合中存在 OPRF derived 与某项匹配的条目"——不证明该条目对应的真实身份、handle、活跃度或意愿。客户端 UI MUST 把它表述为"可能可联系"而不是"已确认存在"。
- 高隐私客户端 SHOULD 为每个 provider 或关系使用 pairwise DID，并在 consent 完成前避免披露全局 public persona DID。
- 实现 MUST NOT 在同一 quota window 内允许同一 quota key 提交超过 `max_psi_queries_per_window`（默认 1）次 batch；默认 quota window 为 24h，且 MUST 与 VOPRF key epoch 解耦。quota 以**已认证 device credential**为主键；provider MAY 额外施加 per-principal 与 IP 反滥用上限，但单一 IP MUST NOT 是唯一 quota key。一次完整 PSI query 的 blind + match 整体计 1 次，quota 只在首次 blind 准入时原子执行；已接纳 batch 的 match 与完全相同重试 MUST NOT 再扣 quota。
- **batch replay / retry binding（normative）**：Provider 以 `(authenticated_device_credential, batch_id)` 为唯一域。首次通过语法、固定 cardinality、ciphersuite / epoch 校验的 blind 请求计算 `blind_digest = SHA-256(JCS(closed blind request body))`，原子完成 quota 准入、计数、digest / epoch 绑定与 outcome 缓存；在 `batch_completion_ttl_seconds` 接纳区间内，同 digest 重试 MUST 返回缓存的同一语义 outcome、不重新计数，并继续使用相同 phase bucket / delay sampler；同一 batch_id 携带不同 blind digest MUST 返回 409 `duplicate_conflict`，不得重新求值。首次合法 match 同样绑定 `match_digest = SHA-256(JCS(closed match request body))` 并缓存 outcome；相同 match 重试返回缓存 outcome，不同 digest 返回 `duplicate_conflict`。batch 未知、属于其它 device，或请求到达时刻大于等于 `admission_time + batch_completion_ttl_seconds`，统一返回 410 `psi_batch_unavailable`，不得区分具体原因。Provider MUST 在接纳区间内保留绑定、pinned epoch 与缓存；不得以 epoch 已轮换为由拒绝合法 match，区间结束后不得接受孤立 match。
- **超额响应（normative）**：超额 blind 返回 HTTP 429 + `psi_quota_exhausted` 的 padded Class B RFC 9457 Problem Details，并携带十进制秒数形式 `Retry-After`；取值为距 quota window 滚动剩余秒数向上量化到 300s 整数倍，最小值 300。Provider MUST NOT 把 quota denial 伪装成 200 no-match：quota 是 requester 自身状态，伪装会产生可缓存假阴性且可被自控 canary 识破。新 VOPRF key epoch 不得单独重置 quota；只有 quota window 滚动或 operator 明确解封可重置。

## 7. Directory Service Role

Directory Service 是 Arkret 的**发现入口层**：让任意 subject 在不预先知道精确 id / alias / invite 的前提下，从其 trust 范围内**已 opt-in 暴露**的资源中找到目标，并取得**足以独立发起下一步 action（resolve / preview / knock / join / invite / verify / contact）的最小可验证元数据**。

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
| Join 执行点 | invitee 自己的 Principal Server 首次准入，再按 signed invite / 当前 joined-member delivery binding 选择 `join_candidates[]` 中的成员 Principal Server 转发；最终由 reducer 收敛 |
| 身份解析器 | DID resolver / identity registry / witness |
| 消息或历史镜像 | Events API / Sync stream |
| Service topology 权威 | DID Document `service` entry |
| 全网爬虫 | 不存在；ingest 仅按 §8 双向 opt-in |

特别地：**Directory 不执行 join、不签发 invite token、不签发 capability grant**。Directory 的 join-side 责任只到“产出 `realm_id + join_candidates[]`，供 invitee 的 Principal Server 选择有界的 joined-member Principal Server 转发目标”为止。客户端始终把 join / invite-accept / knock 提交给自己的 Principal Server；能否实际加入由 Realm 的 `join_rule` 与 policy 决定（见 §3.0 三个独立 gate）。

### 7.3 不变量（normative）

任何符合 v1 的 Directory 实现 MUST 满足：

1. **Rebuildable**：丢失全部本地索引后，Directory 必须能仅凭 `directory_services` 列出本 DID 的资源 + ingest protocol 重建索引内容。Directory 不得持有任何不可从真相源恢复的"权威"数据。
2. **Pluralizable**：同一资源 opt-in 多家 Directory 时，针对同一 `(resource_id, source_refs frontier, policy_revision)` 的查询结果 MUST 在 §9.1 normative 字段上一致；不一致 MUST 标记为 `stale=true` 或 `divergent=true`。缺省的 `source_refs` 在该元组里就是空 frontier，与任何非空 frontier 都不相等——两家 Directory 只有在都不可验证时才算同一 frontier。
3. **Freshness-tagged**：每条返回结果 MUST 携带 `as_of` 与 `policy_revision`。`source_refs` 是**可验证性**字段，不是格式字段：entry 有 Event 来源时 MUST 携带它，让消费者能回真相源自行验签；没有 Event 来源时 MUST 整个省略该成员。实现 MUST NOT 为一条自己从未 author 的 Event 铸造 id，也 MUST NOT 用空数组冒充（schema 保持 `minItems: 1`，所以"存在但为空"不是一种合规形态）。一个伪造的 `source_refs` 比缺省更坏：它看起来可验证，消费者会拿它去解析一个不存在的 Event。消费者 MUST 把缺省的 `source_refs` 当作"该 entry 此刻不可独立验证"，而不是当作已验证。TTL 过期未续约的 entry MUST 标记 `stale=true` 或被移除（见 §8.6）。
4. **Withdrawable**：资源 governance 通过 §8.7 撤销 opt-in 后，Directory MUST 在 ≤ 1h 内停止披露该资源。
5. **Plaintext-free**：Directory MUST NOT 持有或转发 Realm 内 plaintext content、E2EE 密文 payload、私 persona DID、pairwise DID 或 governance 密钥材料。
6. **No-shadow-grant**：Directory MUST NOT 签发 invite token、capability grant、session credential 或任何能绕过 Realm / Organization policy 的认证材料。

### 7.4 行为契约

Directory Service MUST：

- expose its service DID and feature profile（`ak.find.directory.read.describe.v1`，含 §8.9 ingest 字段）
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
| 资源 → Directory | 在 `ak.{realm,organization,actor,applet,handle}.discovery.directory_services` 列出本 Directory 的 service DID + governance key 签名整份 payload | — |
| Directory → 资源 | — | 在 `ak.find.directory.read.describe.v1.accept_policy_kind` 中声明可接受的资源类别、trust root、配额（§8.9） |

Directory 接受 ingest 的前置条件：

- 资源签名声明中**未列出**本 Directory DID → MUST 拒绝并返回 `directory_unauthorized`。
- 资源不在 Directory `accept_policy` 范围内 → MUST 拒绝并返回 `accept_policy_denied`。
- 资源端 governance key 在 ingest 时刻不在 DID document 当前 epoch → MUST 拒绝并返回 `governance_key_invalid`。

### 8.2 两种 ingest 模式

Directory MUST 支持 **push (announce)** 与 **pull (refresh)** 两种 ingest 模式之一，且 MUST 在 `ak.find.directory.read.describe.v1.ingest_modes` 中显式声明本实例支持的模式。

| 模式 | 触发方 | 适用场景 |
| --- | --- | --- |
| push（announce） | 资源 Principal Server 主动提交签名 discovery state | 公开 / 社区 directory；资源希望尽快上线或撤销 |
| pull（refresh） | Directory 按已知资源 DID 周期性拉取最新签名 discovery state | 高安全部署、白名单 directory、与 federation 复用 |

资源端 MAY 任选支持的一种使用；Directory MAY 同时支持两种以提高可用性。两模式产生的索引条目 normative 等价。

### 8.3 Push 模式：`ak.find.directory.command.announce.v1`

**Endpoint**：`POST /_arkret/find/directory/announce`

**认证**：

- Transport 层：HTTP Message Signature（RFC 9421）由资源所在 Principal Server 的 service DID 签发，绑定 `Source-Service-ID` header。
- Payload 层：`discovery_event` 是**已接受的 `ak.{kind}.discovery` Event 原件**，其自身 `proofs[]` 即资源 governance key 的签名（按资源 DID document 解析 effective signer）。规范**不再**定义第二份对同一事实的 detached 签名副本——同一事实两种签名形态必然漂移，且 Event 之外的“payload 内含 proof”形态在本模型中没有可移植的 canonical bytes 定义。

**请求字段**：

| 字段 | 类型 | 必填 | 说明 |
| --- | --- | --- | --- |
| `discovery_event` | `SignedEvent` | required | 已接受的 `ak.{kind}.discovery` Event 原件，逐字节等于真相源（[`event-envelope.schema.json`](../../artifacts/schemas/event-envelope.schema.json)）。资源类别由五个封闭 Event kind 唯一派生；资源主键按 event-kind registry 的 cell subject 派生：Realm 取 envelope `realm_id`，Organization 取 `payload.organization_principal_id`，Actor / Applet / Handle 取 `payload.resource_id`。投递原签名 Event 与 `/_arkret/peer/contacts` 投递原签名 `ak.contact.*` Event 同形。effective discovery state 是闭合 wrapper 的 `payload.value`，不得把 payload wrapper 当作扁平 state。 |
| `source_refs` | `id[]` | required | 真相源 event frontier，至少包含产生当前 effective discovery state 的 state Event；Realm 还 MUST 包含 effective `ak.realm.policy_bundle` Event。Directory 将此已验证、有序去重的 frontier 做 JCS + SHA-256，所得 digest 是结果的 `policy_revision`，请求不得另行回声该值。 |
| `as_of` | `timestamp` | required | 资源端声明的 effective 时间；与服务端时间偏差 > 5 min MUST 拒绝（`signature_stale`）。 |
| `principal_server_id` | `did_core_id` | required | 当前资源真相源所在 Principal Server 的稳定 service `did_core_id`；Directory 必须通过 verified ServiceResolutionRecord 映射当前 `did` / URL 后 pull 验证，不得把该值交给 DID resolver。 |
| `ttl_seconds` | `int` | optional | 期望保留时长；缺省采用 `default_ttl_seconds`。MUST ≤ `max_ttl_seconds`（§8.6）。 |
| `supersedes_announce_id` | `ak:announce:<uuidv7>` | optional | 上一次 announce id；用于幂等替换与 audit 链接。该 id 只在签发它的 Directory 内有权威含义。 |

**响应**：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `announce_id` | `ak:announce:<uuidv7>` | 本次 ingest 记录 id，例如 `ak:announce:0196419b-0000-7000-8000-000000000000`。这是 Directory 本地 ingest 记录；typed 形态只用于统一 validator / SDK 处理，不赋予跨 Directory 的全局对象权威。 |
| `indexed_at` | `timestamp` | Directory 完成索引的服务器时间。 |
| `effective_ttl_seconds` | `int` | Directory 实际授予的 TTL。 |
| `next_revalidation_after` | `timestamp` | 下一次 re-announce 或 pull-refresh 的最早时间。 |
| `warnings` | `string[]?` | 非阻塞警告，例如 `truncated_member_count`、`policy_revision_drift`。 |

**典型错误码**：`directory_unauthorized`、`accept_policy_denied`、`signature_invalid`、`signature_stale`、`source_refs_unverifiable`、`governance_key_invalid`、`ttl_out_of_range`、`rate_limited`、`takedown_in_force`。

请求示例（非完整 schema）：

```json
{
  "principal_server_id": "ak:did_core:webvh:z3omZGak5a5es84Ph2kfPs4UP",
  "as_of": "2026-05-10T08:00:00Z",
  "ttl_seconds": 86400,
  "source_refs": [
    "ak:event:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
  ],
  "discovery_event": {
    "kind": "ak.organization.discovery",
    "payload": {
      "organization_principal_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
      "value": {
        "discoverability": "public",
        "directory_services": [
          "ak:did_core:webvh:zAvx6fqPK7h5rBjBiBRbmLmd6",
          "ak:did_core:webvh:z43vHHHeh32Hnyv6t7X3t33Xs"
        ],
        "profile_visibility": { "...": "..." }
      }
    },
    "proofs": [
      {
        "verification_method": "did:webvh:zGUwpRSnyVCLzU7upsm9iSwEv:acme.example#governance-key-1",
        "...": "..."
      }
    ],
    "...": "..."
  }
}
```

### 8.4 Pull 模式与 push webhook 注册：`ak.find.directory.push.command.register.v1`

Pull 模式不得调用资源 Principal Server 的 `/_arkret/self/events/*`。资源若允许 Directory 主动 refresh discovery state，必须通过 `/_arkret/find/directory/*` ingest / pull profile 暴露 Directory 专用读取面，并在 `supported_operation_bundles` 中声明对应 Directory operation 的精确 carrier/schema 行；Directory 只能读取该资源签名的 effective discovery state，不得把 Events API 当作通用 discovery dump。

Directory 拉取流程：

1. 按本地 trust root / 已配对资源列表，定期向资源 Principal Server 的 Directory 专用读取面发 state-only query。
2. Principal Server 返回最新 effective discovery Event 原件（与 push 模式的 `discovery_event` 是同一对象，不另造 state-only 形态）。
3. Directory 按 §8.5 验签后写入或更新本地索引。

可选的 webhook 辅助：Directory MAY 调用 `ak.find.directory.push.command.register.v1`（§9）让资源 Principal Server 在 discovery state 变更时主动 webhook 通知（fan-out 优化），但**协议级 freshness 仍以 §8.6 为准**——通知缺失或迟到不得使 stale 条目复活。

### 8.5 验签与接受规则

Directory 接受 ingest（无论 push 或 pull）前 MUST 顺序完成：

1. **Transport layer**：验证 HTTP Message Signature（push）或 service binding + TLS（pull）。
2. **Discovery proof**：按 Event proof 既有规则验证 `discovery_event` 的 `proofs[]`（重算 canonical bytes 与 `event_id` 并逐字节比对），确认 effective signer 是资源 governance key 且签发时间在 key 当前 epoch 内（按 DID document key history）；随后按 kind / cell-subject 映射派生资源类别与主键，不存在外层 mismatch 分支。
3. **Directory authorization**：确认 `discovery_event.payload.value.directory_services` 数组包含本 Directory 的 service DID。
4. **Source refs sanity**：MAY 通过 pull 抽查 `source_refs` 中至少一个 seal 在资源 Principal Server 上可解析、frontier 一致。Directory MUST 对**首次 ingest** 的资源至少抽查一次。
5. **Accept policy**：对照本地 `accept_policy` 检查资源 DID method、trust root、配额、abuse 黑名单。

任一步失败 MUST 拒绝并返回对应错误码；Directory MUST NOT 部分接受或"先索引后审核"。

**DID authority call site（normative）**：第 2 步验证的是 service / organization 的**治理签名方**，不是 human principal 的操作，因此它落在 [`../identity/did-usage-and-verification.md` §5.4](../identity/did-usage-and-verification.md) 的 `ongoing_governance` evidence class 内，并已按该文 §4 结尾的硬约束登记为**真实调用点**：`ak.find.directory.command.announce.v1` 与 `ak.find.directory.command.withdraw.v1` 两条 operation 在 `contract-registry.json` 中携带 `did_authority`（`freshness_profile_id = ak.did_freshness.ongoing_governance.v1`），并在 `did-freshness-profile-registry.json` 的 `call_sites[]` 中逐字登记。announce admission 内为解析 principal server endpoint 而发起的 DID 解析属于该 operation 的组成部分，**MUST NOT** 另立 call site。

未登记 `did_authority` 的 Directory operation **MUST NOT** 调用 authority resolver。因此全部 `ak.find.directory.read.*` 查询 / filter 面是**零网络**的：它们只消费已接受 binding，实现 MUST 在类型层把已接受 binding 存储与网络 resolver 隔离，使查询路径结构上无法发起解析。`DirectoryIssuer` 用途的 binding 由 ingest acceptance 镜像得到，**MUST NOT** 自行发起解析。

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
- Discovery state 内容未变但需要续约时，资源 MAY 重新提交相同 `discovery_event` + 新 `as_of`，Directory MUST 视为有效续约（按 `(resource_id, as_of)` 幂等）。
- Directory MUST 拒绝 `as_of` 早于已存 entry `as_of`，或从已验证 `source_refs` frontier 派生出的 `policy_revision` 已出现在当前 revision 之前的 announce（`policy_revision_rollback`）；digest 本身不作字典序大小比较。

### 8.7 撤销

撤销 opt-in 有三条等价路径，Directory MUST 全部支持：

1. **资源端发布新 state**：`ak.{kind}.discovery` 中将 `directory_services` 移除本 Directory DID，或将 `discoverability` 改为 `secret` / `unlisted`。Directory 在下一次 ingest 周期内 MUST 移除条目；push-only 部署中资源 SHOULD 同时调用路径 2 加速生效。
2. **资源端主动 withdraw**：`POST /_arkret/find/directory/withdraw`，body 含 `resource_id`、`reason`、governance key 签名（与 announce 同等强度）。Directory MUST 在 ≤ 1h 内停止披露。
3. **Directory operator takedown**：单方面下架（policy 违规、abuse、法律）。Directory MUST：
   - 在内部 audit log 记录 `takedown_id`、operator、reason、生效时间；
   - 通过 `ak.find.directory.read.describe.v1.takedown_contact` 暴露的入口或 DID document `service` entry 中声明的 governance contact 通知资源端；
   - 不得伪装为"资源主动撤销"——audit log 与资源端通知 MUST 标记为 `operator_takedown`。

v1 core 只规定 operator takedown、不可篡改审计和资源通知，不定义公开的 Directory appeal HTTP operation。takedown notice SHOULD 提供 `takedown_id`、resource id、policy reason code、evidence digest、effective_at、治理联系通道与 Directory service DID signature。部署可通过离线或私有治理通道复核并恢复条目；若未来标准化公开申诉，必须作为包含提交、状态读取、裁决、恢复、签名回执、权限和隐私模型的完整扩展落地，不能只增加一个 submit endpoint。

撤销后，Directory MUST 对该 `resource_id` 的精确 resolve 返回与 `unlisted` / `not_found` 不可区分的响应（参见 §3 防枚举）；对正在分页的 search 响应，MUST 在下一次 cursor 推进时停止披露。

#### 8.7.1 Withdraw governance proof wire 形态与绑定（normative）

`withdraw` 的 `governance_proof` MUST 验证
`service-operation-dtos.schema.json#/$defs/DirectoryGovernanceProof`：复用通用非 Event
detached-JWS proof 叶，并对本对象族封闭三个选择——`proof_purpose` MUST 为
`governance_authorization`，`audience` MUST 为目标 Directory 的 service DID（单值），
`domain` MUST 缺席。proof 对象开放、出现未声明成员、purpose / audience 不符，MUST 在
执行撤销动作前拒绝。

绑定按 `device-lifecycle.md` §9.0.1 同一形态构造：先从闭合 request body 删除顶层
`governance_proof` 成员（不是置为 `null`），保留所有实际存在的 optional 字段，计算
`payload_digest = SHA-256(JCS(request_without_governance_proof))` typed digest；proof
`payload_digest` MUST 与之 byte-identical。detached JWS 的 payload segment MUST 为空，
并对下列唯一 canonical binding object 的 JCS bytes 签名：

```json
{
  "context": "ak.directory_governance_request_proof.v1",
  "payload_digest": "<proof.payload_digest>",
  "operation_id": "ak.find.directory.command.withdraw.v1",
  "resource_id": "<request.resource_id>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "proof_purpose": "governance_authorization",
  "audience": "<目标 Directory 的 service_id>"
}
```

**`audience` 形态（normative）**：这里的"目标 Directory 的 service DID"逐字等于该 Directory
`ak.find.directory.read.describe.v1` 响应中的 `service_id`，即 `did_core_id` 形态
（`ak:did_core:<method>:<msi>`），与 §2 `directory_restricted_claim_presentation.audience` 同形态。
完整 `did:<method>:<msi>` 形、DID URL 与数组形**都不是**可接受的替代形；Directory MUST 以
`service-operation-dtos.schema.json#/$defs/DirectoryGovernanceProof` 的 `audience` 约束拒绝其它形态，
MUST NOT 为兼容而同时接受两种形态。

`operation_id` 进入 binding object，阻断签名跨 operation 重放。签名者授权
沿用既有规则：`verification_method` MUST 解析为该资源当前 DID document epoch 内的
governance key（§8.1 / §8.5，失败返回 `governance_key_invalid`）。**新鲜度**：Directory MUST 拒绝
`proof.created_at` 与接收时刻偏差超过 300 秒的 proof；需要更长窗口的调用方 MUST 重新
签发，部署 MUST NOT 放宽该常量。

### 8.8 Cross-Directory Replication（out of scope）

v1 core **不**定义 Directory 之间的 replication / federation 协议。每个 Directory 独立 ingest；同一资源 opt-in 多家 Directory 时分别 announce。

跨 directory mirror、ranking 共享、reputation 交换属于未来 extension profile（工作名 `directory_mesh.v1`），不在 v1 互操作 floor。Directory MUST NOT 接受其他 directory 转发的索引内容作为权威；MAY 把其他 directory 的存在性作为 hint，但仍 MUST 通过 §8.2 模式独立 ingest。

### 8.9 `ak.find.directory.read.describe.v1` 扩展

**Schema overlay 关系（normative）**：`ak.find.directory.read.describe.v1` 响应是通用 `ak.schema.service_describe.v1` 的 **directory-service overlay**。这些 overlay 字段已作为裸字段登记在 [`service-describe.schema.json`](../../artifacts/schemas/service-describe.schema.json) 中，且仅在 `service_kind=directory_service` 的 describe 响应上成为 required directory contract；实现 MUST NOT 把下列标准字段改写为 vendor-specific `x_*` 顶层字段。Directory describe MUST 在通用 `service_describe` 基础上 extend 以下字段集，作为 directory-specific 字段权威列表：(a) `resource_kinds[]`（资源类别）；(b) `restricted_query_proof`（是否需要 holder-approved proof）；(c) 本节下表列出的 ingest 字段。Conformance profile 只进入 `supported_profiles`，private contact discovery 可用性只由已登记 operation bundle、feature 与 closed `private_contact_discovery` 配置表达；不再另设混合 profile/extension 名称的第二列表。`../sync/service-http-binding.md` 中所有 `ak.find.directory.read.describe.v1` operation row 引用本节作为字段 superset 的权威定义，不另列重复表；任何 directory-specific 字段调整 MUST 先在本节落地。

Directory MUST 在 `describe` 响应中暴露 ingest 能力：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `ingest_modes` | `array<push \| pull>` | 本 directory 支持的模式，至少一个。 |
| `accept_policy_kind` | `enum(open, allowlist, trust_root_signed, operator_review)` | `open` = 任意签名资源；`allowlist` = 资源 DID 在显式白名单；`trust_root_signed` = 需要 trust seal 背书；`operator_review` = 人工审核。 |
| `accept_policy_ref` | `object?` | 描述如何获得接入资格的可读 ref（URL / DID / governance contact）。 |
| `default_ttl_seconds` | `int` | 默认 TTL。 |
| `max_ttl_seconds` | `int` | TTL 上限，MUST ≤ 2,592,000。 |
| `revalidation_grace_seconds` | `int` | TTL 到期宽限。 |
| `accepted_resource_kinds` | `enum[]` | 本 directory 接受的资源类别子集。 |
| `accepted_did_methods` | `string[]` | 接受的 principal/governance DID method token，形如 `did:web`、`did:webvh`。 |
| `takedown_contact` | `did \| url?` | operator takedown 时的通知 / 申诉入口。 |
| `rate_limits` | `object?` | per-DID / per-organization / per-IP 配额上限的可读描述。 |

Directory 若支持 handle lookup 的高敏 intent，SHOULD 在 `ServiceDescribe` 扩展字段中声明粗粒度能力，例如 `x_handle_resolution.contact_request_enabled`、`x_handle_resolution.invite_enabled` 与 `x_handle_resolution.member_add_enabled`。这些开关为 `false` 或缺失时，客户端 MUST 使用 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) 的 invite address + introduction evidence 流程，或使用 `ak.self.contact.command.request.v1` 的 `explicit_address` 低信任路径；不得把 `resolve_handle(intent="contact_request" | "invite" | "member_add")` 当作 base invite / contact 前置条件。

### 8.10 Anti-abuse

ingest 通道 MUST 防御：

- **Replay**：同一 `(resource_id, as_of)` 重复 announce MUST 幂等（返回原 `announce_id`）；过期 timestamp 的 announce MUST 拒绝（`signature_stale`，`as_of` 与服务端时间偏差 > 5 min）。
- **DID 抢占**：首次 ingest 某 DID 时 MUST 全量验证 DID document + governance key history；不允许仅凭 `did:web` 域名解析跳过 webvh history / witness 校验。
- **Quota burning**：Directory MUST 对 per-resource、per-Principal Server、per-IP 限流；超限返回 `rate_limited`。
- **Source-ref 伪造**：Directory MUST 拒绝 `source_refs` 中包含本 Directory 不能从声明的 Principal Server 解析得到的 event id 的 announce。
- **撤销规避**：Directory MUST NOT 接受 `as_of` 早于已记录 withdraw 时间的 announce（`takedown_in_force`）。
- **Policy rollback**：Directory MUST 解析并验证 `source_refs` 对应的 accepted frontier；若其权威 predecessor/successor 关系早于当前已索引 frontier，则拒绝 `policy_revision_rollback`。`policy_revision` 只是该已验证 frontier 的 JCS/SHA-256 结果，不从 `discovery_event.payload` 读取，也不按摘要字典序比较。

Directory operator MAY 维护资源黑名单（abuse、垃圾、法律）；命中黑名单时 MUST 直接返回 `accept_policy_denied`，不得进入 ingest 流程后再静默丢弃。

## 9. Service Surface

Recommended operations：

```text
GET  /_arkret/find/directory/describe
POST /_arkret/find/directory/search-realms
POST /_arkret/find/directory/resolve-realm
POST /_arkret/find/directory/resolve-target
POST /_arkret/find/directory/search-organizations
POST /_arkret/find/directory/resolve-organization
POST /_arkret/find/directory/search-actors
POST /_arkret/find/directory/search-users
POST /_arkret/find/directory/resolve-handle
POST /_arkret/find/directory/resolve-agent-selector
POST /_arkret/find/directory/list-handles-for-subject
POST /_arkret/find/directory/private-contact-discovery
POST /_arkret/find/directory/announce
POST /_arkret/find/directory/withdraw
POST /_arkret/find/directory/push/register
```

字段级定义：

`organization_preview` 的基础字段为 `organization_principal_id`、`handle?`、`display_name?`、`avatar_blob_ref?`、`as_of`、`source_refs`、`policy_revision`。当组织目录 policy 允许公开治理预览时，preview MAY 额外携带 `verified_badge`、`member_count`、`realms`、`realm_count`；这些字段仅表示公开/授权可发现的组织和 Realm fan-out，不授权披露非公开成员、完整组织拓扑或私有 Realm。

| operation_id | 必填字段 | 可选字段 | 响应字段 | 约束 |
| --- | --- | --- | --- | --- |
| `ak.find.directory.read.describe.v1` | 无 | 无 | `service_id: did_core_id`; `resource_kinds: string[]`; `restricted_query_proof: boolean?`；以及 §8.9 全部 ingest 字段 | `public_metadata`；可限流。 |
| `ak.find.directory.read.search_realms.v1` | 无 | `query: string`; `organization_principal_id: did_core_id`; `source_realm_id: id`; `requester: did`; `proof_challenge: string`; `claim_presentations: DirectoryRestrictedClaimPresentation[]`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 每条 result MUST 含 §9.1 normative 字段；其余按 §3 / §11 过滤；restricted Realm 的 claim presentation 形态见 §2；隐藏资源不得泄露存在性。 |
| `ak.find.directory.read.resolve_realm.v1` | 至少一个：`realm_id: id`、`alias: string`、`invite_token: string`、`signed_link: string` | `requester: did`; `proof_challenge: string`; `claim_presentations: DirectoryRestrictedClaimPresentation[]` | `realm_preview: object`; `stripped_state: object[]?`; `join_rule: string?`; `join_candidates?: ak.schema.realm_join_candidate.v1[]` | `alias` 输入 MUST 解析自 effective `ak.component.realm.alias.v1`（唯一 wire 承载是 `ak.realm.alias`，tombstone 视为不存在；见 [`object-addressing.md` §3.3](./object-addressing.md)），Directory 行只是该 cell 的投影而非独立真相源。`join_candidates[]` 只向 invitee 的 Principal Server 提供从 signed invite / 当前 joined-member delivery binding 裁剪的转发提示，不是客户端可直投列表。若隐私策略不能披露 candidate，响应 MUST 省略；客户端仍只向自己的 Principal Server 提交 join material。invite / restricted / secret Realm 对未授权请求使用统一 `not_found`。 |
| `ak.find.directory.read.resolve_target.v1` | `address: string`（object-addressing grammar） | `requester: did`; `proofs: proof[]`; `token: string` | `target_kind: enum(realm,strand,message)`; `realm_preview: object?`; `object_preview: object?`; `join_rule: string?`; §9.1 全部通用字段 | `resolve_realm` 的对象级泛化（分享 Strand / Message / Realm 的深链解析）；realm 解析 MUST 委托同一 `resolve_realm` 路径，并继承 `join_candidates[]` 语义；`token` 仅在 `lt ∈ {invite, preview}` 的 link 类型下允许携带，reference 类型 MUST NOT 带 token（见 [`object-addressing.md` §4.1](./object-addressing.md)）；携带 `token` 时 MUST 按 target descriptor 逐级校验再走 join-policy；未授权统一 `not_found`。完整 grammar / token 绑定 / 隐私规则见 [`object-addressing.md`](./object-addressing.md)。 |
| `ak.find.directory.read.search_organizations.v1` | 无 | `query: string`; `claims: object`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 仅返回公开或授权可发现组织。 |
| `ak.find.directory.read.resolve_organization.v1` | 至少一个：`organization_principal_id: did_core_id` 或 `handle: string` | `proofs: proof[]` | `organization_preview: object`; `did_document_ref: string?`; `endorsements: object[]?` | 解析组织不等于公开成员、Realm 列表或服务拓扑。 |
| `ak.find.directory.read.search_actors.v1` | 无 | `query: string`; `realm_id: id`; `organization_principal_id: did_core_id`; `cursor: cursor`; `limit: int` | `results: object[]`; `next_cursor: cursor?`; `has_more: boolean` | 不得泄露 pairwise/private DID 或未披露组织账号。 |
| `ak.find.directory.read.search_users.v1` | `body.query: string` | `body.realm_id: id`; `body.limit: int`; `body.intent: enum(mention,contact_request,invite,member_add)`; `body.cursor: cursor` | `users: object[]`（每条 user：`handle: string?`、`principal_id: did_core_id?`(conditional)、`display_name: string?`、`avatar_blob_ref: id:blob?`、`membership: string?`、`verified: boolean?`、`member_delivery_binding: object?`(conditional)）； `next_cursor: cursor?`; `has_more: boolean?` | Directory-side user search / candidate discovery；受共同 Realm / directory policy 限制。Realm message mention MUST 先走 roster-local 解析，不得自动外呼本接口。分页字段（`has_more` / `next_cursor`）与本表其它 `search_*` op 一致，是 `search-users` 响应的唯一规范分页约定（[`profiles-presence.md` §4.1](./profiles-presence.md) 引用本行，不另定义 `limited`）。user 主体 DID 字段名统一为 `principal_id`（字段集以 [`directory-operations.schema.json`](../../artifacts/schemas/directory-operations.schema.json) 的 `user_search_outcome` 为准）。`users[].principal_id` 是 **conditional**：仅当请求方已通过 `resolve_handle` 所需的 claim / presentation / audience / intent 验证，或结果来自调用方本地持有的联系人索引时才可返回；共同 Realm membership 不得单独授权披露它。未授权时结果 MAY 只含 handle / display preview，不返回 `principal_id` 或 `member_delivery_binding`。`query` 不得进入 URL、Referer 或未脱敏 access log。 |
| `ak.find.directory.read.resolve_handle.v1` | `handle: string` | `expected_principal_id: did_core_id`; `proof_challenge: string`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `realm_id: id`; `requester: did_core_id`; `proofs: proof[]` | `principal_id: did_core_id`; `subject: did_core_id`; `handle: string`; `verified: boolean`; `claims: object[]?`; `member_delivery_binding: object?`; `source_refs: id[]?`; `expires_at: timestamp?` | 可选 Directory/profile 能力；base invite/member-add/contact request 不依赖该接口。受限 / 组织 handle 需要 presentation；响应 `handle` 是 canonical `user:domain`；投递服务 DID 只通过 `member_delivery_binding.recipient_id` 返回，且只能作为 builder evidence 或 `handle_claim` introduction evidence，不能替代 invite address / contact_address + introduction evidence，也不能越过接收方 Principal Server `receive_policy_constraints`。 |
| `ak.find.directory.read.resolve_agent_selector.v1` | `controller_handle: string`; `agent_slug: string`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `requester: did` | `expected_actor_id: did_core_id`; `proof_challenge: string`; `realm_id: id`; `proofs: proof[]` | `controller_subject: did`; `subject: did`; `agent_slug: string`; `verified: true`; `selector_claim: object`; `source_refs: id[]?`; `expires_at: timestamp?` | 可选的精确 native personal agent selector 解析，不属于 `ak.profile.directory_service.v1` 基线。只有直接拥有同一 accepted Event store、能在本地 joined basis 下验证 selector claim、agent Actor Profile 与 accountability grant 的 role-local 部署，才能广告独立 `ak.operation_bundle.directory_service.resolve_agent_selector.v1`；current-v1 不新增 Directory evidence ingest carrier，独立 Directory 因而 MUST 省略该 bundle。广告后，Directory MUST 先按 handle claim 解析 `controller_handle` 为 controller DID，再验证当前可见 `ak.schema.agent_selector_claim.v1` 的 `(controller_subject, agent_slug) -> subject`、`binding_state="verified"`、visibility / audience / claim_scope、proof、agent Actor Profile 与 accountability grant。成功响应中的 `subject` 是 agent DID；失败、未授权、不可见、revoked / expired / ambiguous、controller 不存在或 agent 不可见 MUST 使用与不存在不可区分的失败。该接口不是搜索 / 列表接口，不得支持 slug prefix、模糊匹配或返回候选。 |
| `ak.find.directory.read.list_handles_for_subject.v1` | `subject: did` | `realm_id: id`; `intent: enum(lookup,mention,contact_request,invite,member_add)`; `requester: did`; `proof_challenge: string`; `proofs: proof[]`; `as_of: datetime`; `cursor: cursor`; `limit: int` | `subject: did`; `claims: object[]`; `primary_handle: string?`; `as_of: datetime`; `next_cursor: cursor?`; `has_more: boolean` | 已知 holder / principal DID 时列出当前 context 可见 signed handle claims；响应符合 `ak.schema.list_handles_for_subject_response.v1`，且 `claims[].subject` MUST 等于响应 `subject`。`subject` 不是 Realm `actor_id`。必须按 disclosure policy、issuer trust、audience 和 intent 过滤。 |
| `ak.find.directory.read.private_contact_discovery.v1` | 见 §6.3 | 见 §6.3 | 见 §6.3 | 见 §6；MUST 使用 blinded / padded identifier batch；不得返回原始 connection identifier、完整 profile、成员列表或关系图谱。 |
| `ak.find.directory.command.announce.v1` | 见 §8.3 | 见 §8.3 | 见 §8.3 | 见 §8。 |
| `ak.find.directory.command.withdraw.v1` | `resource_id: id\|did\|handle`; `governance_proof: object`; `reason: string` | `effective_at: timestamp` | `withdrawal_ref: string`; `acked_at: timestamp` | `withdrawal_ref` 是 Directory-local audit reference，不是注册 typed ID；见 §8.7。 |
| `ak.find.directory.push.command.register.v1` | `subscriber_principal_id: did_core_id`; `resource_filter: object`; `webhook_endpoint: url` | `secret: string`; `expires_at: timestamp` | `subscription_id: id`; `effective_at: timestamp` | 仅作为 pull 模式优化；不替代 §8.6 freshness 协议。 |

**Plaintext query 跨请求关联（normative）**：上表 `query` 脱敏约束（不进入 URL / Referer / 未脱敏 access log）只堵旁路面；受托 Directory（半受信第三方）还 MUST NOT 在应用层把 `(requester_actor_id, query_term, realm_id, timestamp)` 跨请求持久关联用于重建 requester 画像（"谁在找谁、对哪些 Realm 成员感兴趣"）。`search_users` / `search_actors` / `search_realms` 的 plaintext `query` 留存 MUST 有界并 SHOULD 脱敏 / 仅保留聚合反滥用指标；高隐私部署 SHOULD 走客户端本地索引或 §6 PSI / blind index 路径而非把 raw query 交给 Directory。口径对齐 §6 对 raw identifier 的保护与 [`../sync/privacy-preserving-search.md`](../sync/privacy-preserving-search.md) 对 access pattern 的风险登记。

### 9.0 Handle 解析（normative）

Directory MAY 解析 `@alice:acme.example`、`alice@acme.example`、`alice:acme.example` 或 `acct:alice@acme.example` 这类 handle 输入。解析结果是**寻址证据**，不是成员资格、grant、contact consent、invite delivery 授权或投递授权本身。base v1 invite/member-add 使用 [`../sync/invite-addressing.md`](../sync/invite-addressing.md) 的显式 `invite_address + introduction_evidence`；base contact request 使用 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md) 的 `contact_address + introduction_evidence`。`resolve_handle(intent="contact_request" | "invite" | "member_add")` 仅是可选 Directory/profile 输出。已知 `subject` DID 但不知道当前 handle 时，调用方使用 `list-handles-for-subject`；该接口返回的是当前 context 可见 handle claim set，不是 profile 或 MemberIdentity event。

当 `intent ∈ {contact_request, invite, member_add}` 时，能够评价 `subject` 的 `invite_receive_policy` 或等价接收策略的 Directory / Principal Server MUST 在披露 `subject` DID、`claims[]` 或 `member_delivery_binding` 前先按 `handle_claim` introduction evidence 执行接收策略；若策略结果为 `drop`，或部署要求的 receive-policy 证据不可验证，响应 MUST 使用与不存在不可区分的统一拒绝。无法评价接收策略的受托 Directory MUST 不得把解析成功解释为投递授权，且返回的证据 MUST 仍强制接收方 Principal Server / reducer 按 `receive_policy_constraints` 与 Join Policy 复核。

当 `intent ∈ {contact_request, invite, member_add}` 且 Directory 返回 `member_delivery_binding` 时，响应 MUST 满足：

1. `subject` / `principal_id` 是被寻址主体的稳定 principal `did_core_id`，不是裸 DID；两者同时出现时 MUST byte-for-byte 相同。
2. `handle` 是 canonical handle（`<localpart>:<domain>` 主形态）；UI 字符串不得作为验签输入。
3. `member_delivery_binding.recipient_id` 是 Principal Server service `did_core_id`，且 claim issuer 对该 service identity 的使用有可验证授权。
4. `claims[]` 至少包含一个可验证 handle claim、VC presentation 或 signed directory claim，绑定 `handle`、`subject`、`member_delivery_binding.recipient_id`、issuer、`audience`、`created_at`、`expires_at`。
5. claim `audience` MUST 等于请求中 `realm_id`、requester service DID 或调用 profile 声明的 audience 之一；不一致 MUST 返回与"无可披露 claim"不可区分的统一拒绝。
6. 当 intent 为 `invite` 或 `member_add` 时，`member_delivery_binding` 只能作为构造 `ak.member.state{membership="join"}.delivery_binding` 的输入；`member_delivery_binding.binding_source` 不得是 `did_document_default`；接收方 reducer 仍 MUST 按 Join Policy 独立验证。当 intent 为 `contact_request` 时，`member_delivery_binding` 只能作为构造 `contact_address.recipient_id` 与 `handle_claim` introduction evidence 的输入；接收方仍 MUST 按 subject receive policy 与 `receive_policy_constraints` 独立判定 drop / quarantine / notify。

Directory MUST NOT：

- 因为某个 Principal Server 本地存在账号就直接披露 `member_delivery_binding.recipient_id`。
- 因为调用方猜中某个 handle 字符串就合成 `invite_address` / `contact_address`，或替调用方发起 invite delivery / contact request。
- 向无权请求方泄露组织内部 handle 与 DID / service DID 的映射。
- 把 handle 解析结果缓存为全局 actor routing；缓存必须绑定 `handle`、claim digest、audience / scope、requester policy 与 expiry。
- 执行 join、签发 invite token 或授予 Realm capability；Directory 只返回可验证寻址证据。

#### 9.0.1 Requester proof wire 形态与绑定（normative）

`resolve_target`、`resolve_organization`、`resolve_handle`、`resolve_agent_selector` 与
`list_handles_for_subject` 的 `proofs[]` 复用通用非 Event detached-JWS proof 叶
（`event-envelope.schema.json#/$defs/proof`），但**每个 request 对象族各自持有一个内联的
`proofs[]` 节点与一个独立 context**。`directory-operations.schema.json` 是 DTO 容器而不是一个
对象族，因此**不存在**覆盖全文件的 directory operation context；schema 侧以
`x-arkret-proof-context` 逐字投影，
[`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json) 是唯一真源：

| 对象族 | operation | context |
| --- | --- | --- |
| `directory_resolve_target_request_body` | `ak.find.directory.read.resolve_target.v1` | `ak.directory_resolve_target_request_proof.v1` |
| `directory_resolve_organization_request_body` | `ak.find.directory.read.resolve_organization.v1` | `ak.directory_resolve_organization_request_proof.v1` |
| `directory_resolve_handle_request_body` | `ak.find.directory.read.resolve_handle.v1` | `ak.directory_resolve_handle_request_proof.v1` |
| `directory_resolve_agent_selector_request_body` | `ak.find.directory.read.resolve_agent_selector.v1` | `ak.directory_resolve_agent_selector_request_proof.v1` |
| `directory_list_handles_for_subject_request_body` | `ak.find.directory.read.list_handles_for_subject.v1` | `ak.directory_list_handles_for_subject_request_proof.v1` |

绑定按 §8.7.1 同一形态构造：先从闭合 request body 删除顶层 `proofs` 成员（不是置为 `null`），
保留所有实际存在的 optional 字段，计算
`payload_digest = SHA-256(JCS(request_without_proofs))` typed digest；每条 proof 的
`payload_digest` MUST 与之 byte-identical。detached JWS 的 payload segment MUST 为空，并对下列
唯一 canonical binding object 的 JCS bytes 签名：

```json
{
  "context": "<上表中该对象族的 context>",
  "payload_digest": "<proof.payload_digest>",
  "issuer": "<request.requester>",
  "operation_id": "<上表中该对象族的 operation>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "audience": "<目标 Directory 的 service_id>"
}
```

`audience` MUST 为目标 Directory 的 service DID（单值），`domain` MUST 缺席，`proof_purpose`
MUST 缺席（`governance_authorization` 只属于 §8.7.1 的写入面）。

**`audience` 形态（normative）**：这里的"目标 Directory 的 service DID"逐字等于该 Directory
`ak.find.directory.read.describe.v1` 响应中的 `service_id`，即 `did_core_id` 形态
（`ak:did_core:<method>:<msi>`），与 §2 `directory_restricted_claim_presentation.audience` 及 §8.7.1
governance proof 的 `audience` 同形态。完整 `did:<method>:<msi>` 形、DID URL 与数组形**都不是**可接受的
替代形；Directory MUST 以 `directory-operations.schema.json#/$defs/proof` 的 `audience` 约束拒绝其它
形态，MUST NOT 为兼容而同时接受两种形态。签名方与验证方 MUST 用同一 `service_id` 逐字节构造 binding
object，形态不一致时签名必然不成立，且失败按本节末段走 §9.2 的不可区分拒绝，现场不会给出可归因信号。
本条只约束 proof 叶与 binding object 的 `audience`；`resolve_handle` 请求体自身的顶层 `audience`
字段是 handle claim 的披露 audience 选择器（见本节上文），不是 proof audience，不受本条约束。

binding object 各字段的取值形态如下（本表与 registry 的 `binding_fields` 逐族列表配套，registry 只登记
字段名，形态以本表为准）：

| binding 字段 | 形态 | 取值来源 |
| --- | --- | --- |
| `context` | 上表中该对象族的 context 字面量 | `proof-context-registry.json` |
| `payload_digest` | typed digest string | `proof.payload_digest` |
| `issuer` | `did_core_id` | `request.requester`（`resolve_organization` 省略该字段） |
| `operation_id` | operation id 字面量 | 上表中该对象族的 operation |
| `verification_method` | DID URL | `proof.verification_method` |
| `created_at` | RFC 3339 timestamp | `proof.created_at` |
| `audience` | `did_core_id`（单值） | 目标 Directory `describe.service_id` |
| `address` | 非空 address string | `request.address`（`resolve_target`） |
| `handle` | canonical handle | `request.handle`（`resolve_handle`） |
| `controller_handle` | canonical handle | `request.controller_handle`（`resolve_agent_selector`） |
| `agent_slug` | agent slug | `request.agent_slug`（`resolve_agent_selector`） |
| `subject` | `did_core_id` | `request.subject`（`list_handles_for_subject`） |

携带 `proofs` 的请求 MUST 同时携带本对象族定义的发起方字段，且 `issuer` MUST 与之 byte-for-byte 相同：`resolve_target` /
`resolve_handle` / `list_handles_for_subject` 为 `requester`，`resolve_agent_selector` 为
`requester`。`directory_resolve_organization_request_body` 没有发起方 wire 字段，其 binding
object MUST 省略 `issuer`，签名者身份只由 `verification_method` 承载。

除公共字段外，binding object 还 MUST 逐字加入该族的解析目标：`resolve_target` 加 `address`；
`resolve_handle` 加 `handle`；`resolve_agent_selector` 加 `controller_handle` 与 `agent_slug`；
`list_handles_for_subject` 加 `subject`；`resolve_organization` 的目标已完全落在
`payload_digest` 内，不另加字段。完整逐族 binding fields **字段名**以 registry 的 `binding_fields`
为准，字段**取值形态**以上面的形态表为准；registry 不登记形态，实现 MUST NOT 从字段名推断形态。

**Directory MUST 拒绝 context 与本 operation 对象族不一致的 proof**：在一个族下有效的签名不得
被另一个族接受。`proof_challenge` 出现时，它随 `payload_digest` 一并被绑定，不另作签名域。
**新鲜度**：Directory MUST 拒绝 `proof.created_at` 与接收时刻偏差超过 300 秒的 proof；需要更长
窗口的调用方 MUST 重新签发，部署 MUST NOT 放宽该常量。proof 校验失败的受限解析 MUST 按 §9.2
使用与不存在不可区分的统一拒绝，不得回传 proof 层的精确原因。

### 9.1 通用结果字段（normative）

每条 search / resolve 结果 MUST 包含下表中标为必填的字段；`source_refs` 是 conditional，其余可选字段按各自条件出现：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `as_of` | `timestamp` | Directory 上次刷新该条目的时间。 |
| `source_refs` | `id[]?` | 真相源 event id；客户端可据此回 Principal Server 验签。**conditional**：entry 有 Event 来源时 MUST 携带（`minItems: 1`）；没有 Event 来源时 MUST 整个省略，MUST NOT 用空数组冒充（判据见 §7.3 不变量 3）。 |
| `policy_revision` | `string` | discovery state 的 effective revision；便于跨 Directory 对账。每条 search / resolve 结果 MUST 携带（与 §7.3 不变量 3 一致），不得省略；`ak.find.directory.read.resolve_target.v1` 等泛化解析继承同一 MUST。 |
| `stale` | `boolean?` | TTL 过期且未续约时为 `true`，客户端 SHOULD 仅作参考。 |
| `divergent` | `boolean?` | 与同一资源的另一 Directory 视图不一致时为 `true`（实现可选检测）。 |
| `join_candidates` | `ak.schema.realm_join_candidate.v1[]?` | invitee Principal Server 可用于转发 Realm join / invite-accept / knock 的有界 joined-member Principal Server 提示。来源只允许 signed invite 与当前 joined-member delivery binding；search 结果 MAY 省略。该字段不授权客户端绕过自己的 Principal Server 直接提交。 |

#### 9.1.1 Realm Join Candidate（normative）

`join_candidates[]` 是 invitee Principal Server 的有界转发提示，不是 Realm 级 ingress 权威或授权证明。客户端 MUST 把 `ak.invite.accept`、`ak.member.state{membership="join"}`、`ak.member.state{membership="knock"}` 或 profile 声明的 application receipt 先提交给自己的 Principal Server；该 Principal Server 完成本地 admission 后，才可按 signed invite / 当前 joined-member delivery binding 选择已有 Realm 成员的 Principal Server 转发。

每个 candidate MUST 符合 [`ak.schema.realm_join_candidate.v1`](../../artifacts/schemas/realm-join-candidate.schema.json)，并满足：

1. `realm_id` MUST 等于解析结果的 canonical Realm ID。
2. `service_id` MUST 是稳定 service `did_core_id`，不是裸 DID，也不是用户 / 成员 principal `did_core_id`；调用方首次接受新 candidate、candidate binding / policy revision 变化或其 authority freshness 失效时 MUST 验证该 core 与当前 service DID binding，并确认 endpoint 支持 candidate 声明的 `operations`。同一未过期 candidate 命中已接受 binding 时直接复用，不得在每次传输前重新在线解析 DID Document。
3. `operations` MUST 包含 `ak.peer.events.command.submit.v1`；缺失时 invitee Principal Server 不得将其用于 join-side federation forwarding。客户端不得调用该 candidate。
4. `expires_at` 过期、`stale=true`、或 `policy_revision` / `source_refs` 与真相源不一致时，客户端 MUST 重新 `resolve_realm`，不得继续使用缓存 candidate。
5. Candidate 只决定 invitee Principal Server 可将 join material 转交给哪个已有成员 Principal Server；最终是否接受仍由 Realm auth state、Join Policy、capability、invite / review 链、Event proof 和 reducer 校验决定。
6. `join_candidates[].service_id` MUST 来自 signed invite 或当前 effective joined-member `delivery_binding.recipient_id`，但 candidate 仍不授权投递，也不得被复制为 invitee 加入后的 `delivery_binding`。后者必须由 invitee 自己签署。
7. Directory / invite link MAY 按 requester、join_rule、discoverability、anti-enumeration policy 裁剪 candidate 数量；不得泄露完整成员 Principal Server 拓扑。对 `restricted` / `unlisted` / `invite_only` / `secret` 的 Realm，MUST 只给出 signed invite 或最小 current member binding 所需的有界集合；部署已知 peer、mirror、notary、search projection 或 URL hint 不得凭自身进入列表。
8. `seal_basis` 是 candidate `service_id` 在 `as_of` observation coordinate 下该 Realm 的**完整当前已接受 Seal frontier**：`single_signer`/`threshold` authority 恰一 leaf，`open_set` authority 是 canonical sorted、duplicate-free 的完整 non-quarantined leaf antichain；不得把 open_set 压成 single head。roots 由客户端与接收方从全部所引 Seal 的 joined view 重算，不复制到 Event。resolver 只有在 signed invite 或 current member binding 已授权该有界披露时才可返回 basis；客户端 MUST 在向自己的 Principal Server 首次提交前验证并 stamp Control Move。`seal_basis` 进入 Event digest 且被 proof 绑定，任何服务都不得补填。candidate 不持有完整 Realm Seal frontier 时 MUST NOT 返回。**pre-join 活跃度侧信道收口（normative）**：对非成员 basis 解析 MUST 按 `(realm_id, requester)` 限速并使用固定 timing bucket，且 SHOULD 对 frontier 推进迟滞/分桶。
9. `encryption_profile` 是签发方在 `as_of` 时**已接受 Realm projection** 的 effective 值，与 `seal_basis` 同样进入 candidate payload digest 并被 candidate proof 绑定。pre-join client MUST 只用该字段判定 [`../identity/key-management.md`](../identity/key-management.md) §7.11 的加入前 recovery-material gate：`mls_rfc9420` 表示该 join 会为 invitee 产生 Realm MLS group secret，gate MUST 生效；`none` / `external` 表示 Realm join 本身不产生 Realm 级 MLS 材料，gate 由后续 Circle 加入等已可读状态各自判定。客户端 MUST NOT 为判定该 gate 绕过 membership gate 或读取 membership 门控的 Realm Event 历史（服务端按本节对非成员统一返回 `not_found`，这条读路径不存在）。签发方在该 Realm 的已接受 projection 缺失或不可验证时 MUST NOT 猜测默认值，MUST 省略该 candidate；任何服务都不得补填该字段。
10. `digest_algorithm` 是签发方在 `as_of` 对完整 `seal_basis` 的 accepted joined projection 验证得到的 current live `DigestSuite`，与 `encryption_profile`、`seal_basis` 一并进入 candidate payload digest 并被 candidate proof 绑定。缺失、为 `Bottom`、各 leaf join 后不唯一或任一 leaf / predecessor closure 不可验证时，签发方 MUST 省略整个 candidate。pre-join client 只能使用这个已签值 author `ak.invite.accept`；MUST NOT 从 `SealId`、`state_root` 或其他待验证 digest 前缀推断 suite。接收 Realm service 仍须按真实 predecessor joined suite 重验 Event，candidate 值不一致时拒绝，因此恶意 candidate issuer 只能造成拒绝服务，不能扩张权限。

invitee Principal Server 的转发算法 SHOULD 按 `priority` 升序，再按本地可达性与 `service_id` 稳定排序。候选不可达、过期或 fail closed 时 MAY 尝试下一个；客户端只重试自己的 Principal Server。所有重试 MUST 使用同一 canonical `realm_id`，不得跨 Realm 重定向。

客户端在以下情况 MUST 回真相源验签后再 act：

- 准备执行 join、capability 请求或 invite 接受
- 跨 Directory 看到 `policy_revision` 不一致或 `divergent=true`
- 收到 `stale=true` 的关键条目（policy / membership / endorsement）

### 9.2 Search / Resolve 示例

`search-realms` 请求（非完整 schema）：

```json schema=schemas/directory-operations.schema.json#/$defs/directory_search_realms_request_body
{
  "query": "release",
  "organization_principal_id": "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv",
  "requester_id": "ak:did_core:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR",
  "proof_challenge": "ak.chal_01JTV0KQ7K5ZP4VN6C9WEZK2X1",
  "limit": 20
}
```

请求体是 closed `directory_search_realms_request_body`：字段**平铺**，没有 `search_scope` 包装，
`proofs[]` 的登记形态是 `claim_presentations`（`DirectoryRestrictedClaimPresentation[]`）。
optional 字段省略即可，MUST NOT 写成 `null`。

Result：

```json
{
  "realms": [
    {
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "title": "Release Coordination",
      "summary": "Public release coordination",
      "discoverability": "listed",
      "join_rule": "knock_restricted",
      "history_access": "since_join",
      "owning_organization_ids": [
        "ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv"
      ],
      "preview_ref": "ak:event:AYemPz_ISC7Yf4ytl7vB21-c37l_4W9dmtZFF_yWUcq9",
      "join_candidates": [
        {
          "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
          "service_id": "ak:did_core:webvh:z3omZGak5a5es84Ph2kfPs4UP",
          "service_kind": "principal_server",
          "role": "joined_member_principal_server",
          "endpoint": "https://principal.acme.example",
          "operations": [
            "ak.peer.events.command.submit.v1",
            "ak.self.events.read.scan.v1"
          ],
          "join_methods": [
            "knock",
            "restricted_join"
          ],
          "priority": 0,
          "source": "member_delivery_binding",
          "source_refs": [
            "ak:event:AYemPz_ISC7Yf4ytl7vB21-c37l_4W9dmtZFF_yWUcq9"
          ],
          "as_of": "2026-05-10T07:55:12Z",
          "expires_at": "2026-05-10T08:05:12Z"
        }
      ],
      "as_of": "2026-05-10T07:55:12Z",
      "policy_revision": "01JTV0KQ7K5ZP4VN6C9WEZK2X1",
      "source_refs": [
        "ak:event:AYemPz_ISC7Yf4ytl7vB21-c37l_4W9dmtZFF_yWUcq9",
        "ak:event:AVZRcfmbNkWDnY7vFRBfT5-0GKc1emMtu7zh2LD9WziK",
        "ak:event:AcmUk3Vf28NeA_10d3lhwc2_Ojm518lWJl2oGUshkHp5"
      ]
    }
  ],
  "has_more": false
}
```

响应体是 closed `directory_realm_search_outcome`：数组字段名是 `realms`（不是 `results`），
`has_more` 必填，`next_cursor` optional 且省略即表示末尾，MUST NOT 写成 `null`。

未授权对隐藏资源的精确 resolve SHOULD 返回：

```json
{
  "type": "https://arkret.org/problems/not_found",
  "title": "Not found",
  "status": 404,
  "detail": "not found"
}
```

**失败不可区分（含时延等同，normative）**：对"不存在"与"未授权访问的隐藏资源"，实现 MUST 使用相同的 status、相同响应结构与**相同时延等级**（constant-time 或固定时延桶，避免按是否走完整 presentation / claim / audience 校验产生可观测时序差）。该要求适用于 `resolve_realm`、`resolve_target`、`resolve_handle`、`resolve_agent_selector`、`list_handles_for_subject`、`search_users` / `search_actors` / `search_realms` 的所有 `not_found` / `unauthorized` 分支。否则攻击者可用时序差分逐个探测 handle / selector / 成员是否存在，即便响应体一致也能去匿名化组织成员名单与关系图。pre-join resolve 若返回 `seal_basis` / head snapshot，服务端还 MUST 对返回给同一 requester 的 head 推进使用固定迟滞 / 分桶：每 `(realm_id, requester)` 在部署声明窗口内最多暴露一次新的 head snapshot，窗口不得随 Realm 实时写入速率变化；未到窗口边界时返回上一可见 snapshot 或不可区分失败，而不是实时 head。实现也可用严格限速替代，但必须声明可测上限（默认 SHOULD ≤ 1 次 / 5 分钟），并在 conformance / ServiceDescribe 中暴露该上限。timing 侧信道收口对齐 [`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md) 的目录 resolve 反枚举 / blinding 条款；`resolve_target`、`resolve_handle` 与 `resolve_agent_selector` 分别由 `ak.vector.directory.resolve_target_blinding.v1`、`ak.vector.directory.resolve_handle_failure_blinding.v1`、`ak.vector.directory.resolve_agent_selector_failure_blinding.v1` 固定。

## 10. Parent Realm 与 Organization Directory

Realm 层级 MAY 协助发现，但 parent 成员资格不授予 child 成员资格或 child 读权限。

规则：

- Space hierarchy MAY 列出跨 Realm child Space 预览，但每个 child Space 仍按自身 `realm_id` 的 discoverability 与 caller authorization 独立裁剪。Realm link graph 不提供通用 parent/child directory expansion。
- Organization 目录 MAY 列出 Realm 预览，仅当 Realm discovery policy 允许组织目录列出且组织背书有效时成立。
- 把 Realm 从组织目录中移除不会撤销成员资格或删除数据。
- 撤销 `ak.realm.organization` 背书 MUST 使官方目录徽章在目录刷新后被移除。

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

- `ak.vector.directory.public_realm_search.v1`：public Realm search。
- `ak.vector.directory.organization_search.v1`：listed organization directory search。
- `ak.vector.directory.restricted_claim_presentation.v1`：restricted search with valid and invalid claim presentation。
- `ak.vector.directory.unlisted_exact_resolve.v1`：unlisted exact resolve。
- `ak.vector.directory.invite_not_found_blinding.v1`：invite-only indistinguishable not_found。
- `ak.vector.directory.resolve_target_blinding.v1`：`ak.find.directory.read.resolve_target.v1` unauthorized / nonexistent / undiscoverable targets return byte-identical `not_found` and do not reveal target kind, Realm id, object id, timing class or preview metadata。
- `ak.vector.directory.organization_badge_verification.v1`：official Realm verification through `ak.realm.organization`。
- `ak.vector.directory.pairwise_did_exclusion.v1`：hidden pairwise DID exclusion。
- `ak.vector.directory.stale_result_rejection.v1`：stale result rejection after discovery policy update。
- `ak.vector.psi.no_reachability_metadata.v1`：private contact discovery does not disclose raw connection identifiers、reachability proof、profile、成员列表或关系图谱。
- `ak.vector.directory.result_common_fields.v1`：search / resolve result MUST carry §9.1 normative 字段（`as_of`、`source_refs`、`policy_revision`；支持结构化 candidate 且可披露 join 路由的 resolve 必含 `join_candidates[]`）。

**Ingest 面**

- `ak.vector.directory.announce_bidirectional_opt_in.v1`：announce accepted when directory DID listed in `directory_services` and signature valid。
- `ak.vector.directory.announce_directory_not_authorized.v1`：announce rejected with `directory_unauthorized` when directory DID NOT listed。
- `ak.vector.directory.announce_bad_signature.v1`：announce rejected with `signature_invalid` on a bad `discovery_event` proof。
- `ak.vector.directory.announce_signature_stale.v1`：announce rejected with `signature_stale` when `as_of` skew > 5 min。
- `ak.vector.directory.policy_revision_rollback.v1`：announce rejected with `policy_revision_rollback` when `as_of` earlier than indexed entry。
- `ak.vector.directory.accept_policy_denied.v1`：announce rejected with `accept_policy_denied` when resource outside policy。
- `ak.vector.directory.reannounce_idempotent_ttl.v1`：re-announce idempotent on `(resource_id, as_of)`，TTL 正确续约。
- `ak.vector.directory.pull_mode_refresh_verification.v1`：pull-mode ingest verifies signed discovery state on every refresh。
- `ak.vector.directory.ttl_expiry_removal.v1`：TTL expiry marks entries `stale=true`，after grace + 24h removed。
- `ak.vector.directory.withdraw_blinded_not_found.v1`：withdraw stops disclosure within ≤ 1h，subsequent resolve returns indistinguishable `not_found`。
- `ak.vector.directory.operator_takedown_audit.v1`：operator takedown writes audit log with `operator_takedown` marker and notifies governance contact。
- `ak.vector.directory.takedown_reannounce_rejected.v1`：subsequent announce after takedown rejected with `takedown_in_force`。

**PSI 面**

- `ak.vector.psi.oprf_two_round_shape.v1`：private contact discovery MUST use the §6.2 two-round OPRF set-membership strand。
- `ak.vector.psi.padding_and_cardinality.v1`：batch size、dummy padding、result cardinality、failure response shape and timing do not reveal match count。
- `ak.vector.psi.quota_blinded_denial.v1`：首次 blind quota denial 返回 padded HTTP 429 `psi_quota_exhausted` + 300s 量化 `Retry-After`；UTF-8 entity body 必须精确命中 blind phase bucket，并使用 describe 的同一 delay sampler。向量同时覆盖 exact blind / match replay 不重扣 quota、同 batch_id 异 body 返回 `duplicate_conflict`、未知 / wrong-device / expired batch 合并为 `psi_batch_unavailable`，以及 pinned epoch 在完整 completion TTL 内保留；不得伪装成 200 no-match。逐目标 outcome 继续在固定 cardinality `hit_bitmap` 内字节级不可区分（§6.4 Class A）。
