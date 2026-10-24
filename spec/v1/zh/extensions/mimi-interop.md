---
title: MIMI Interoperability
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

> **状态：interop extension profile（非 v1 core 互操作必需）**。本文档描述的 MIMI Provider Facade 跟踪的
> 是仍在演进的 IETF MIMI Internet-Draft。Arkret v1 core 互操作 **不要求** 实现 MIMI
> facade；声称 `ak.profile.station.v1` 或 `ak.profile.full_client.v1` 的实现
> 可以完全不实现本 profile。当 MIMI 升级为 RFC 后，将以新的 `ak.profile.mimi_interop_<rfc>.v1`
> 引入稳定 profile；当前 `ak.profile.mimi_interop.v1` 视为实验性 interop extension profile。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 对 MIMI 的互操作 profile。目标不是把 Arkret core 改成 room-first 协议，而是在 Arkret 的 Realm / Event / DID / capability 模型外提供一个可测试的 **MIMI Provider Facade**，让支持 MLS 的 Arkret Realm 或 Strand discussion track 可以与 MIMI provider 互通。

`ak.profile.mimi_interop.v1` 固定参考以下草案版本：

- `draft-ietf-mimi-protocol-06`
- `draft-ietf-mimi-content-08`
- `draft-ietf-mimi-room-policy-03`
- `draft-kohbrok-mimi-identifiers-01`

本 profile 的 active conformance vector 集合以
[`vector-registry.json`](../../artifacts/registry/vector-registry.json) 的 `ak.vector.mimi.*` 行为准
（该 registry 是唯一权威；本文不复述清单或计数）。

这些草案仍是 Internet-Draft。实现 MUST 在 `server/describe` 和 MIMI provider directory 中声明实际支持的 draft version。草案更新导致 wire 语义变化时，Arkret MUST 通过新的 interop profile 版本处理，不得改变 v1 核心状态语义。

## 2. 角色

| MIMI 角色 | Arkret 映射 |
| --- | --- |
| Provider | `mimi_provider_facade` service DID，通常由 Station 或受托 bridge 暴露。 |
| Hub provider | 对外拥有 MIMI room URI 的 provider service；在 Arkret 侧通常映射为 Station，负责 MIMI room fanout 和 groupInfo。 |
| Follower provider | 参与 MIMI room 的远端 provider；在 Arkret 中表现为 federation peer 或 Applet bridge peer。 |
| User / client | Arkret principal DID + device id，可按 Realm policy 使用 pairwise DID 或 room-scoped pseudonym。 |
| Room | Arkret Strand discussion track 的 MIMI room 投影，可附带所在 Realm 的最小上下文。 |

MIMI facade 不是新的真相源。Arkret native 侧的 canonical truth 是 producer-signed Event、state-changing Event、唯一确认的 RealmCommit 安全序列、按已登记状态模型投影的 current state state、capability refs 与 MLS key-access revision binding（`governance_binding.key_access_revision` + current confirmed group-state projection）。MIMI room state 是对这些状态的互操作投影。

## 3. Provider Discovery

支持 MIMI 的服务 MUST 在 DID Document service entry 和 `GET /_arkret/describe` 中声明：

```json fragment
{
  "service_kind": "mimi_provider_facade",
  "supported_profiles": ["ak.profile.mimi_interop.v1"],
  "mimi": {
    "protocol_draft": "draft-ietf-mimi-protocol-06",
    "content_draft": "draft-ietf-mimi-content-08",
    "room_policy_draft": "draft-ietf-mimi-room-policy-03",
    "identifier_draft": "draft-kohbrok-mimi-identifiers-01",
    "base_url": "https://chat.example/mimi",
    "provider_id": "mimi://example.com",
    "features": [
      "key_material",
      "room_update",
      "notify",
      "submit_message",
      "consent",
      "identifier_query",
      "report_abuse",
      "proxy_download"
    ]
  }
}
```
实现 SHOULD 同时暴露 MIMI provider directory 互操作入口：

```text
GET /.well-known/mimi-protocol-directory
GET /_arkret/open/mimi/provider-directory
```

目录响应 MUST 绑定 service DID、provider id、base URL、支持草案版本、endpoint 列表、MLS cipher suites、内容 profile、room policy components 和签名 proof。自己 Station 和远端 provider MUST 验证 service DID、HTTP Message Signature、TLS endpoint、DID service endpoint 和 Realm policy 委托一致。客户端从自己的 Station 取得结果并绑定所请求 provider/Realm；不回取 DID 或治理历史。

**出站网络目标策略（normative，SSRF 防护）**：facade 在向对端 provider 声明的 `base_url`（及其派生 endpoint）发起任何 server-side 请求前，MUST 对该 URL（含 redirect 后实际目标）执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝，`base_url` scheme MUST 限 `https`。签名 proof 只证明"是这个 provider"，不证明"网络目标合法"。

### 3.1 Provider directory 的签名 projection 与验证算法（normative）

directory 文档由 [`mimi-interop.schema.json#/$defs/provider_directory`](../../artifacts/schemas/mimi-interop.schema.json)
定义：安全核心（`schema`、`service_id`、`proof`）与完整能力声明（`endpoints` /
`features` / `mls_cipher_suites` / `content_profiles` / `room_policy_components`，均
`minItems: 1`、排序去重）全部必备。`proof` 是共享闭合 detached-JWS
（[`event-envelope.schema.json#/$defs/proof`](../../artifacts/schemas/event-envelope.schema.json)），
签名主体是 `service_id` 控制的 verification method；dev 摘要或任何可由公开输入复算的值不是签名。

**精确（非"至少"）unsigned projection**。`proof.payload_digest` 是下列闭合对象的
canonical JSON（[`../conformance/encoding.md` §2](../conformance/encoding.md)，JCS）
SHA-256 typed digest；proof 自身与任何未登记扩展字段都不进入 projection。projection
首个成员是本对象族在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)
登记的唯一 context `ak.mimi_provider_directory_proof.v1`（schema 侧投影为
`mimi-interop.schema.json#/$defs/provider_directory` 的 `x-arkret-proof-context`，两处 MUST
逐字一致）；用其它对象族 context 生成的签名即使密码学验签通过也 MUST 拒绝：

```text
{
  "context": "ak.mimi_provider_directory_proof.v1",
  "schema": ...,
  "service_id": ...,
  "service_kind": ...,
  "supported_profiles": <sorted unique>,
  "mimi": {
    "protocol_draft": ..., "content_draft": ...,
    "room_policy_draft": ..., "identifier_draft": ...,
    "base_url": ..., "provider_id": ...,
    "endpoints": <sorted by endpoint_id>,
    "features": <sorted unique>,
    "mls_cipher_suites": <sorted unique>,
    "content_profiles": <sorted unique>,
    "room_policy_components": <sorted unique>
  }
}
```

draft extension 的开放性保留在 wire 层，但未知字段 MUST NOT 改变 endpoint 派生、能力
协商、授权、路由或验签结果，也不得进入 v1 transcript；新增安全语义必须先登记进 profile
schema 与本 projection，不能靠未签名 extension 暗中生效。

**endpoint 行**。`endpoints[]` 的每行是闭合 `{endpoint_id, relative_path}`；`endpoint_id`
取值集合与 `features` 同一封闭枚举且每个 id 至多出现一次。`relative_path` MUST 是以 `/`
开头、不含 scheme、authority、query、fragment、空白与反斜杠的规范化相对路径；
percent-decoding 后出现 `.` / `..` 段、编码的 `/` 或 `\` 一律拒绝。effective URL 只能通过
标准 URL parser 在已验证的 HTTPS `base_url` 下解析，解析后 MUST 再次同 origin，并执行本节
出站网络目标策略——签过名的 endpoint 列表不豁免 SSRF 检查。

**接收方验证算法**。除按共享 proof 定义重算 `payload_digest`、验证 JWS 与 `created_at`
freshness 外，接收方 MUST：

1. 从 `proof.verification_method` DID URL 取得无 path/query/fragment 的 controller `did`，
   用已登记 method adapter 验证并要求 `project(did) == service_id`（稳定 service `did_core_id`），
   再确认该 key 在对应当前 service DID Document 中被授权用于 service assertion；禁止把DID
   与 `service_id` 直接作字符串相等比较，DID URL 可解析本身也不构成接受理由；
2. 随后独立验证 HTTP Message Signature、TLS、DID service endpoint、Realm policy 委托与
   SSRF policy——directory proof 不替代其中任何一项；
3. 任一 required 能力缺失、能力数组为空、endpoint 行非法或 projection 重算不符时整体拒绝。

conformance：`ak.vector.mimi.provider_directory_signature.v1` MUST 覆盖正向签名向量，以及
缺失任一 required 能力、篡改 endpoint / cipher suite / content profile / room policy、proof
controller 与 `service_id` 不同、unknown extension 试图改变路由、过期 `created_at`、projection
`context` 被替换为其它已登记对象族 context、HTTP signature 合法但 directory JWS 无效（及反向）
等负向量。

## 4. Room Binding

`CurrentMimiRoomBinding` 是 `current-state.schema.json#/$defs/current_mimi_room_binding` 的完整强类型：依次包含闭合 `selector: {kind: "mimi_room_binding", mimi_room_uri}`、`source_stream_ref`、`revision`、`value`。`source_stream_ref` MUST 来自精确覆盖该绑定 source Event 的已接受 RealmCommit，并与该 Commit 的 `realm_id`、`commit_id`、`stream_position` 一致；其 stream 的 Realm MUST 等于 `value.binding_scope.realm_id`；stream kind 沿用已接受 Commit 的真实值，不能从“控制面”术语推导为 Realm Actor 专用的 `realm_control` stream。selector URI MUST 等于 payload URI。缺失 covering Commit 或不匹配的坐标 MUST 拒绝，不能由 room URI、缓存或当前 head 猜测来源。facade 的 payload 投影不是完整 Current，也不得另保留三字段同名兼容类型。

允许被导出为 MIMI room 的 Arkret 对象 MUST 有写入 `mimi_room_binding` current state 的 state-changing Event registered projection。对应 Event kind 为 `ak.mimi.room_binding`；current state subject 是 `payload.mimi_room_uri`，registry 中的 `state_selector.kind` 为 `uri`。

**`mimi_room_uri` canonical wire form 与 current state subject 编码（normative）**：`mimi_room_uri` 既是 wire 字段又是 current state selector 的 preimage 与排序键，因此它 MUST 是**封闭 canonical 形态**；receiver MUST NOT 先归一化再接受，非 canonical 输入 MUST 以 `schema_violation` 拒绝。若 `mimi://Example.com/r/1` 与 `mimi://example.com/r/1` 各落一个 current state，同一 room 就能有两个「首个 accepted binding」，§4.2 的初始状态与 `revoked` 终态都能靠换写法绕过。

canonical 形态（机读真源是 [`mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 的 `$defs/mimi_room_uri`）：

- scheme 固定小写 `mimi://`；authority 只允许 `host[:port]`，MUST NOT 出现 userinfo；
- host MUST 是小写 A-label（IDN MUST 已 punycode；MUST NOT 出现大写或 U-label），每个 label 以 ASCII 字母数字起止；
- port 只在非默认端口时出现，MUST NOT 有前导零，且 MUST 在 `1..=65535` 内；默认端口 `443` MUST NOT 显式书写；
- path MUST 至少一个非空 segment，MUST NOT 出现 `.` / `..` segment，MUST NOT 有尾随 `/`；
- MUST NOT 携带 query 或 fragment；
- percent-escape MUST 使用大写 hex，且 MUST NOT 编码 unreserved octet（RFC 3986 §6.2.2.2 的最小编码）；
- 整串长度 MUST ≤ 512 octet。

canonical TypedStateSelector subject 由该 canonical URI 的 exact UTF-8 bytes 按 [`../conformance/encoding.md` §4](../conformance/encoding.md) 的 `uri` subject kind **全量** percent 编码得到（`:` `/` `%` 一并编码，`%` → `%25`），例如：

```text
mimi://mimi.example.com/rooms/01JSMIMI
→ mimi_room_binding:mimi%3A%2F%2Fmimi.example.com%2Frooms%2F01JSMIMI
```

实现 MUST NOT 改用 hash 化 subject、URI 片段截取，或在 payload 中另立一个 caller 分配的 room 标识符作为 subject——后者会给同一 room URI 制造第二个身份，使 §4 的 1:1 语义无法在 wire 上强制。canonical 形态与 subject 编码的正反例由 [`ak.vector.encoding.state_selector_uri.v1`](../../artifacts/registry/vector-registry.json) 唯一闭合。

`ak.mimi.room_binding` 的完整 payload 形态（含 `hub_provider_id`、`follower_provider_ids`、`content_profile`、`policy_revision`、`local_provider_role` 等全部字段）以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威机读真源；下文逐字段说明不替代该 schema。

```json fragment
{
  "kind": "ak.mimi.room_binding",
  "payload": {
    "profile": "ak.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "strand_id": "ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa"
    },
    "hub_provider_id": "ak:did_core:webvh:z5dPBhAYJdfYhFqD3peyGJcxj",
    "local_provider_role": "hub",
    "status": "accepted",
    "follower_provider_ids": [
      "ak:did_core:webvh:z2B174DcqrzvV5vkzDBdSwVvy"
    ],
    "mls_group_id": "base64url...",
    "content_profile": "application/mimi-content",
    "policy_revision": 7,
    "created_at": "2026-04-30T00:00:00Z"
  }
}
```
规则：

- `binding_scope.realm_id` MUST 指向一个 accepted Realm。`strand_id` MUST 指向该 Realm 内启用 discussion track 的 accepted Strand；MIMI room timeline 只投影该 Strand discussion track 的消息。
- `hub_provider_id` MUST 是 Realm policy、Organization principal 或 member principal 明确委托的 service `did_core_id`；委托证据中的 service `did` / VM 必须经 adapter 投影到该值。
- `local_provider_role` 取值为 `hub`、`follower` 或 `observer`（封闭枚举，以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。各值语义:
  - `hub`:本地 facade 即拥有该 MIMI room URI 的 hub provider,负责 room fanout 与 groupInfo,对外承担 room 真相投影责任;
  - `follower`:本地 facade 作为 follower provider 参与远端 hub 拥有的 room,接收 fanout 并向 hub 提交本地 writes;
  - `observer`:本地 facade 只读投影该 room（监听 fanout / groupInfo 用于本地呈现或审计），MUST NOT 代表本地参与方向 MIMI room 提交 writes 或承担 hub fanout 职责。
- `ak.mimi.room_binding` 的创建、更新和撤销 MUST require `ak.policy.manage`、`ak.realm.admin` 或等价 interop capability。
- E2EE MIMI room MUST 绑定 `mls_group_id`，并按 [`../crypto-media/encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md) 校验当前 epoch 的 `key_access_revision`；只有 current membership 推进该 revision（§2.4.1），实际 leaf key 的撤销由治理 Station send gate 同 cut 拒绝，普通 capability 仍由 Event admission 独立校验。
- MIMI facade 在无法解析或验证 Arkret MLS Governance Binding 时 MUST fail closed：入站 MIMI room state、groupInfo、key material 或 message 不得直接投影到 Arkret Realm，而是进入 quarantine，reason=`mimi_governance_binding_missing` 或更具体的 binding mismatch 错误。
- 撤销 binding 后，facade MUST 停止接受新的 MIMI writes，只允许 backfill、tombstone、report、legal hold 或 migration proof 等维护操作。`status` 的完整生命周期状态机（初始状态、合法迁移、终态、非法迁移拒绝、`migrating` 窗口与并发收敛）见 §4.2。

**E2EE MIMI 互操作下界（normative）**：凡 MIMI room binding 携带 `mls_group_id`、groupInfo、key material 或加密 application message，并要投影到 Arkret Realm / Strand，facade MUST 把 §2.5.1 固定 GroupContext binding 当作最低 E2EE 互操作能力，而不是把 MIMI provider 的 room state 当成等价治理真相。具体要求：

- `ak.mimi.room_binding.mls_group_id`、经 RFC 9420 验证的 MIMI GroupInfo／GroupContext group id，以及从同一 scope 的当前 accepted `MlsGroupValue.effective_scope` 按 [`../models/realm-and-space.md` §2.2](../models/realm-and-space.md) 唯一公式推导的 Arkret group id MUST 相等。facade MUST 先验证该 current public state 的 source RealmCommit 和固定五字段 `governance_binding`，再作比较；GroupInfo、provider room state 或请求自报值均不能单独充当 Arkret 当前治理事实。固定 binding 不含 `mls_group_id`，MUST NOT 为此增加第六字段、接受第二套推导公式或以本地缓存补缺；
- 固定 binding 的 `effective_scope`、`base_group_state_ref`、`previous_epoch`、`next_epoch` 与 `key_access_revision` 必须全部存在且逐字段可验证；未知或缺失时不得用 MIMI draft 字段、provider 目录或本地配置补齐；
- current winning MLS group state 的 `key_access_revision` 必须等于从当前 accepted key-access state 重算的值；
- MIMI 未知字段仍按 §9.2 安全惰性处理，不得提升 provider role、放宽 `policy_revision` 或改变 MLS epoch / group state 判定。

### 4.1 Fail-Closed Reason Taxonomy

MIMI facade 对 Arkret Realm 的入站投影失败时，MUST 使用稳定 reason code，避免不同 provider 把 fail-closed 结果折叠成不可测试的通用错误：

| reason_code | 触发条件 | 外部行为 |
| --- | --- | --- |
| `mimi_governance_binding_missing` | 找不到可验证的 Arkret MLS Governance Binding。 | quarantine 或 reject，不投影到 Realm。 |
| `mimi_governance_binding_mismatch` | binding 存在，但其 scope／epoch／revision、已验证 GroupInfo group id、从当前 accepted `MlsGroupValue.effective_scope` 推导的 group id、room binding、provider DID 或目标 Realm／Strand 不一致。 | quarantine；需要人工或 backfill 复核，零投影写入。 |
| `mimi_policy_revision_mismatch` | MIMI policy component 与 accepted `ak.realm.policy_bundle` revision 不一致。 | reject 当前 update，等待 fresh policy projection。 |
| `mimi_room_state_incompatible` | MIMI room state 使用本 profile 不支持的 lifecycle、membership 或 policy 形态。 | reject 或要求使用新 interop profile。 |
| `mimi_provider_unreachable` | provider directory、key material 或 groupInfo 依赖暂时不可达。 | `temporarily_unavailable` + bounded retry；不得接受无 binding 的 fallback。 |
| `mimi_draft_unsupported` | 对端声明的 MIMI draft version 不在本 profile 支持集合。 | reject；不得按相近草案猜测解析。 |
| `mimi_room_binding_status_transition_invalid` | `ak.mimi.room_binding.payload.status` 初始值非法、迁移不在 §4.2 表内，或试图修改 `revoked` 终态。 | reject；不得把缺失或未知 status 当作 accepted。 |
| `mimi_room_binding_migration_proof_invalid` | 结构合法的 `migrating -> accepted` 引用的 Event/RealmCommit 不是同一 room 的相邻 accepted→migrating 权威状态，outcome 与提交拓扑不符，目标 MLS current 状态不符，或其它转换误带成对迁移字段。 | reject；零 Event、RealmCommit 或 typed current 写入。 |
| `mimi_observer_write_forbidden` | `local_provider_role=observer` 的 binding 试图代表本地参与方向 MIMI room 提交 write。 | reject；observer 只读投影不得产生 write side effect。 |

### 4.2 `status` 生命周期状态机（normative）

`payload.status` 是 binding 的生命周期判定字段，取值为封闭枚举 `proposed`、`accepted`、`revoked`、`migrating`（以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。状态迁移规则：

- **初始状态**：对某个 `mimi_room_uri` 的首个被接受的 `ak.mimi.room_binding` state-changing Event MUST 把 `status` 设为 `proposed`（跨 provider 协商中，等待对端确认）或 `accepted`（本地 facade 即 hub 且无需对端确认时可直接激活）。以 `revoked` 或 `migrating` 作为初始状态的写入 MUST 被拒绝。
- **迁移表**：

  | 当前状态 | 允许出边 | 触发条件 |
  | --- | --- | --- |
  | `proposed` | `accepted` | 协商完成：对端 provider 确认，或本地 hub 接受。 |
  | `proposed` | `revoked` | 协商被拒绝、超时或发起方撤回。 |
  | `accepted` | `migrating` | hub 迁移 / provider 拓扑替换开始。 |
  | `accepted` | `revoked` | 持有 §4 要求 capability 的管理操作撤销 binding。 |
  | `migrating` | `accepted` | migration proof 验证通过；MUST 携带 `payload.migration_outcome` 区分 `completed`（新拓扑生效）或 `rolled_back`（恢复原拓扑）。 |
  | `migrating` | `revoked` | 迁移失败且不回滚，或管理操作撤销。 |

- **终态**：`revoked` 是唯一终态；对 `revoked` binding 的任何 `status` 变更 MUST 被拒绝。同一对象若需重新导出为 MIMI room，MUST 以新的 `mimi_room_uri` 建立新 binding 并重新通过 §4 的 capability 校验，不得复活已撤销 binding。
- **非法迁移**：不在上表中的迁移（含初始状态违例与 `revoked` 后写入）MUST 被 reducer 以 `mimi_room_binding_status_transition_invalid` 拒绝。
- **`migrating` 窗口语义**：进入 `migrating` 后，facade 对该 binding MUST 停止接受新的 MIMI writes 投影，仅允许 backfill、tombstone、report、legal hold 与 migration 所需的 groupInfo / state 转移及 migration proof 提交；`migrating -> accepted` 的 state-changing Event MUST 引用已验证的 migration proof 并携带 `payload.migration_outcome ∈ {completed, rolled_back}`（其它转换 MUST NOT 携带该字段），使"迁移完成"与"回滚"在 binding 状态上可区分、可审计；hub / follower 拓扑变更只能随该迁移落地。
- **迁移证据载体与校验**：`migrating -> accepted` 的 caller-signed Event payload MUST 同时携带 `migration_outcome` 和闭合 `migration_proof`；其它初始写入及状态转换 MUST 省略两者。`migration_proof` 的四项必填成员依次为 `previous_accepted_event_id`、`previous_accepted_commit_id`、`migrating_event_id`、`migrating_commit_id`，均是已经 accepted 的 Event 与其 covering RealmCommit 的精确 ID；不得用 pending Event、provider 自报状态、receipt 或未认证缓存代替。接纳方在拟提交的 RealmCommit basis 上验证四个引用均属于同一 Realm、同一 canonical `mimi_room_uri`，各 Commit 覆盖所指 Event，前一对是进入迁移前的最终 accepted binding source，后一对是当前 `migrating` current state 的 source，且两者按该 room 的权威提交顺序相邻（中间没有另一条 accepted binding Event）。本次 Event 的 `binding_scope`、`mimi_room_uri`、`profile` 必须与两项来源一致。`completed` 时本次 `hub_provider_id`、`follower_provider_ids`、`local_provider_role`、`mls_group_id` 必须逐项等于 `migrating` 候选 payload；`rolled_back` 时必须逐项等于迁移前 accepted payload；缺失的 optional 字段与存在的字段不得视为等价。本次 `mls_group_id` 还必须通过 §4 的当前 accepted `MlsGroupValue.effective_scope` 唯一推导与已验证 GroupInfo／GroupContext 三者比较；迁移候选或回滚原值与当前 MLS public state 不一致时不得接纳，直到相应 MLS 状态已获权威提交。proof 是可重放验证的 committed lineage 加本次 Event 签名断言，不声称单靠 provider transport 或 receipt 证明远端动作完成；hub 委托和其它 admission gate 仍须分别通过 §4。闭合 schema 中只带一个迁移字段或 proof 内缺字段先以 `schema_violation` 拒绝；两个迁移字段都缺失却试图从 `migrating` 转到 `accepted`，以及结构合法但状态、引用、拓扑或 MLS 当前性验证失败，MUST 以 `mimi_room_binding_migration_proof_invalid` 拒绝，且不得产生 Event、RealmCommit 或 current state 写入。
- **可写性判定**：仅 `accepted` 状态接受新的 MIMI writes 投影。`proposed` 状态下 facade MUST NOT 把 MIMI room state 投影到 Realm（目录 / 协商类流量除外）；`revoked` 后行为见 §4 撤销规则。
- **并发收敛**：`ak.mimi.room_binding` 是写入 `mimi_room_binding` current state 的 state-changing Event，并发更新由控制面 RealmCommit 串行化仲裁，不存在数据面并发合并；后到的冲突 Event 在其 authority commit basis 下按本状态机重新校验，非法即拒绝。

## 5. Endpoint Surface

MIMI facade 至少定义以下 canonical operation：

| operation_id | HTTP binding | 语义 |
| --- | --- | --- |
| `ak.open.mimi.read.provider_directory.v1` | `GET /_arkret/open/mimi/provider-directory` | 返回 MIMI provider feature profile。 |
| `ak.open.mimi.exchange.request_key_material.v1` | `POST /_arkret/open/mimi/key-material` | 现有 KeyPackage claim 的 MIMI 适配入口，复用原生请求、领取账本和带状态结果（§6）。 |
| `ak.open.mimi.command.update_room.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/update` | 提交或转发 room state / MLS update。 |
| `ak.open.mimi.command.notify.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/notify` | provider 间投递通知、fanout 或 delivery event。 |
| `ak.open.mimi.command.submit_message.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/messages` | 提交 MIMI encrypted application message。 |
| `ak.open.mimi.command.request_consent.v1` | `POST /_arkret/open/mimi/consent/request` | 请求建立跨 provider 联系或 room invite consent。 |
| `ak.open.mimi.command.update_consent.v1` | `POST /_arkret/open/mimi/consent/update` | 提交调用方已签名的 `ak.consent.replace` Event。 |
| `ak.open.mimi.read.identifiers.v1` | `POST /_arkret/open/mimi/identifiers/query` | 查询 connection identifier / MIMI URI 的可达性。 |
| `ak.open.mimi.command.report_abuse.v1` | `POST /_arkret/open/mimi/report-abuse` | 提交跨 provider abuse report，支持 E2EE franking proof。 |
| `ak.open.mimi.command.proxy_download.v1` | `POST /_arkret/open/mimi/proxy-download` | 代理或 oblivious 下载资产。 |

`update_room` 以请求中的语义判别器 `update.kind` 选择封闭效果分支；`update.kind` MUST 与
decoded opaque payload 内的 `kind` 逐字相同，二者不一致必须在读取 room/binding 私有状态前
以 `mimi_room_binding_event_invalid` 拒绝。普通 MIMI room/MLS update 是 receipt-only facade
operation，不产生 Arkret Event。若 `update.kind == "ak.mimi.room_binding"`，请求 MUST 同时携带完整的
caller-authored、caller-signed `room_binding_event` (`EventAdmissionSubmission`)。facade MUST
验证该 Event 的 exact payload 与 path room、目标 Realm/Strand、`mls_group_id` 及已认证的
MIMI operation 一致，再将 exact bytes 送入 Event admission；MUST NOT 合成、
重建、代签或 co-sign actor Event。binding 分支缺少该 Event、非 binding 分支携带该字段、外层与
decoded kind 不一致或 Event 绑定不一致，MUST 对外合并为同一个
`mimi_room_binding_event_invalid`（相同 HTTP status 与 body shape），精确原因只写内部 audit；conformance vector `ak.vector.mimi.room_update_branched_effect.v1` 同时锁定 binding 与 receipt-only 两个分支；该失败
不得依赖 room 是否存在、是否已有 binding 或目标 Realm 私有状态。普通 Event admission 的标准失败码
在 pre-admission 通过后按其已登记合同返回。非 binding update MUST omit `room_binding_event`。

逐次 RFC 9421 来源签名的适用面由 operation id 封闭，不由 HTTP method 或 `read` / `command` 名称推导。
下列 operation **MUST** 使用 HTTP Message Signatures；其它 MIMI operation 不继承该要求：

- `ak.open.mimi.command.notify.v1`
- `ak.open.mimi.command.proxy_download.v1`
- `ak.open.mimi.command.report_abuse.v1`
- `ak.open.mimi.command.request_consent.v1`
- `ak.open.mimi.command.submit_message.v1`
- `ak.open.mimi.command.update_consent.v1`
- `ak.open.mimi.command.update_room.v1`
- `ak.open.mimi.exchange.request_key_material.v1`
- `ak.open.mimi.read.identifiers.v1`

上述来源签名要求对每次调用都适用，包括同部署调用、携带 Bearer user session 或 AgentRuntime session 的请求。会话认证不豁免 HTTP Message Signature；缺来源签名 MUST 在 actor proof、PSI、consent state 或 Event 处理之前以 `http_signature_required` 拒绝并零写入。发送方须使用本 operation 登记的 provider / service 身份，不得以用户或 Agent runtime key 冒充 provider transport key。

其中 identifiers query 虽分类为 read，仍必须逐次认证 provider 来源；认证后按 §10 返回无匹配，不执行 PSI。
`ak.open.mimi.read.provider_directory.v1` 明确不要求本 profile，也不得返回本 profile 的三个错误码。
要求签名的请求绑定：

- source service DID
- destination service DID
- provider id
- MIMI room URI 或 target identifier
- request canonical hash
- created / expires
- body digest

HTTP Message Signature profile（仅适用于上述逐条登记的 provider-to-provider operation）：

- 请求 MUST 携带 `Signature`、`Signature-Input`、`Content-Digest`、`Source-Service-ID`、`Destination-Service-ID` 和 `Provider-ID`；room-scoped endpoint 还 MUST 携带 `MIMI-Room-URI`。
- sender MUST 按 [`../sync/service-http-binding.md` §8.2](../sync/service-http-binding.md) 把 `canonical_json(request_body)` 的结果逐字节作为 exact HTTP message content，且不得应用 `Content-Encoding`；`Content-Digest` MUST 是 RFC 9530 `sha-256=:base64(SHA-256(exact_http_content_bytes)):`。receiver MUST 先校验 exact content bytes 的 `Content-Digest`，再严格解析并确认 wire 本身就是 canonical JSON，并从这些 bytes 内部计算 Arkret request digest；MUST NOT parse arbitrary JSON 后仅对 canonicalized value 求 digest。
- 本场景是 [`../sync/service-http-binding.md` §8](../sync/service-http-binding.md) 的
  `ak.http_signature.scenario.mimi_provider.v1`。`Signature-Input` 适用的必需覆盖项：

  <!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.mimi_provider.v1 -->
  - `@method`、`@target-uri`、`@authority`
  - `arkret-operation`
  - `content-digest`
  - `source-service-id`、`destination-service-id`、`provider-id`
  - `mimi-room-uri`（条件项：room-scoped endpoint 必需）
  - `idempotency-key`（条件项：`request_key_material` 必需）
  - `source-trust-domain`、`destination-trust-domain`（条件项：`request_key_material` 跨 trust domain 时必需）
  <!-- END ak-http-signature-covered-set -->

  `created`、`expires`、`keyid` 与 `alg="ed25519"` 参数 MUST 存在；时效窗口判据是
  [`../sync/service-http-binding.md` §8.3](../sync/service-http-binding.md) 的共享窗口，本节不复制其数值。
- `keyid` MUST 是 `Source-Service-ID` 所控制的 Ed25519 verification method；接收方 MUST 用已接受的 service key binding 或已配置信任根取得它。只有新 service / key、binding invalidation 或显式 freshness 失效时才做 DID authority resolution，普通请求不得逐次在线解析。HTTP signature 只认证 provider service source，不替代 Actor DID/device 签名、MLS transcript、capability 或 Realm policy 校验。

本 profile 的失败码与 [`applet-integration.md` §7.3.1](./applet-integration.md) 的逐次投递来源签名同源，按
[`../sync/api-conventions.md` §5](../sync/api-conventions.md) 只用 RFC 9457 Problem `type` 分派，MUST NOT
返回通用 code 再用 `reason` / `reason_code` 二次分派：

- 缺 `Signature` / 纯 bearer：`http_signature_required`（401）。
- 签名验证失败、必需 header 缺失、`Content-Digest` 不覆盖 exact HTTP content bytes、wire 不是 canonical JSON，或 `Source-Service-ID` / `Provider-ID` / `MIMI-Room-URI` 与 transcript 不一致：`http_signature_invalid`（401）。
- `created` / `expires` 超出上述时效窗口：`signature_window_invalid`（401）。

这三个 code 已在 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 登记，并在
[`operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 中逐条挂在要求本
signature profile 的 MIMI operation 上；`read.identifiers` 必须挂载，`read.provider_directory` 必须不挂载。
operation id 与 error mapping 的双向闭包是机器判据。
负向 conformance vector 为 `ak.vector.mimi.identifier_query_source_signature.v1`：缺失/无效来源签名
必须在 PSI 求值前拒绝，并断言 `ak.open.mimi.read.provider_directory.v1` 不继承该 profile。

Facade 接收请求后 MUST 先验证 MIMI envelope，再映射为 Arkret Event、state-changing Event 或 to-device message。MIMI 传输签名只证明 provider 来源，不替代 Actor DID / device 签名、MLS transcript、capability 或 Realm policy。

### 5.1 MIMI operation actor proof（normative）

MIMI DTO 中名为 `signature` 或 `proofs[]` 的字段是 Actor DID/device 对具体操作的 detached payload proof，不是 Event Envelope proof。它 MUST 使用 `payload_digest`，MUST NOT 使用只适用于 Event Envelope 的 `event_digest`。单值形态由 `mimi-operations.schema.json#/$defs/signature` 定义，数组形态由各对象族自己内联的 `proofs[]`（元素为 `#/$defs/proof`）定义；两者的 `domain` MUST 等于接收部署的 `trust_domain`，`audience` MUST 覆盖接收 Station service DID。

`request_key_material` 的请求与结果直接复用 §6 的原生 claim 载体，不属于本节的 detached payload proof 对象族；其 participant authorization、claim receipt 和 transport signature 各自沿现有合同验证，不另加 MIMI request/outcome proof。

**每个对象族一个 context（normative）**：`mimi-operations.schema.json` 是 DTO 容器而不是一个对象族，因此**不存在**覆盖全文件的 MIMI operation context。持有 detached proof 的对象族逐个登记独立 context，schema 侧以 `x-arkret-proof-context` 逐字投影；对象族、context 与 operation 的对应关系分别以 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json) 和 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 经 schema ref 连接后的结果为唯一真源，本节不复述派生 join 表。

发送方 MUST 先从 request/outcome body 移除顶层 `signature` 或 `proofs` 成员（删除成员本身，不是置为 `null`），保留所有实际存在的 optional 字段，对剩余完整对象计算 `payload_digest = sha256(canonical_json(unsigned_body))`，再以 canonical JSON 编码并签署下列 transcript：

```json fragment
{
  "context": "<该对象族在 proof-context-registry 中登记的 context>",
  "payload_digest": "sha256:<lowercase-hex>",
  "issuer": "<request.actor_id | request.requester | request.requester_actor_id>",
  "operation_id": "<由 schema ref 在 operation-registry 中连接到的 operation>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<destination trust_domain>",
  "audience": "<destination Station service DID>"
}
```
transcript 的完整 binding fields 逐族列在 registry 的 `binding_fields`：`issuer` 只在该对象族的 wire 形态定义了发起方字段时出现（`mimi_request_consent_request_body.requester_actor_id`、`mimi_update_consent_request_body.actor_id` MUST 出现；`mimi_identifier_query_request_body.requester` 可缺席，缺席时 transcript MUST 同时省略 `issuer`），outcome 族的签发方身份只由 `verification_method` 承载。除公共字段外还 MUST 逐字加入该族的目标标识：`mimi_request_consent_request_body` 加 `holder_account_id` 与 `purpose`；`mimi_update_consent_request_body` 加 `consent_id` 与 `decision`。

字段顺序不影响 canonical JSON；`audience` 也可为至少覆盖目标 service DID 的非空无重复字符串数组。接收方 MUST 重算 unsigned body digest，验证 `issuer` 等于该族的发起方字段、下述当前权威来源授权的 `verification_method`、`kind=detached_jws`、`alg=Ed25519`、精确的 context/operation/domain/audience 绑定和 JWS。**接收方 MUST 拒绝 context 与本 operation 对象族不一致的 proof**：在一个族下有效的签名不得被另一个族接受，跨 operation 与 request/outcome 方向的重放由 context 本身阻断，不依赖 `operation_id` 是否被某个实现纳入 transcript。`created_at` MUST 位于接收方当前时钟前后 300 秒内。proof 失败 MUST 在写 consent state 之前拒绝；同一 proof 只能随其已绑定的完整 body 使用。相同 `consent_event.event.event_id` 与 byte-identical Event 的请求重放是 §10 定义的 retry-safe 例外，MUST 返回原 accepted Event ref；若 carried Event ID 不等于当前 canonical Event bytes 的重算值，MUST 以 `event_id_digest_mismatch` 拒绝且不得提前泄露 holder state；只有不同 canonical preimage 各自重算为同一个完整 EventId 时才按 `witness_disagreement` 隔离。

**密钥权威来源（normative）**：完整身份参与 transcript 与 authority lookup，两者缺一不可。

- Account 发起的 `request_consent` 与 holder 的 `update_consent` MUST 按 exact AccountId（principal、Station）解析当前 accepted PCR generation 内的设备授权，并验证 method、设备状态、撤销与 generation；DID Document 只用于已登记的身份解析，不是普通设备签名的授权目录。MUST NOT 要求把设备 key 加入 DID Document，也 MUST NOT 用 root/update/recovery key 签普通 MIMI 操作。`update_consent` 仍须满足 §10 的 authority-root controller 和 Event admission；operation proof 不另授 consent 写权限。
- Agent requester 使用其 exact Actor 的当前 accepted runtime key，MUST 验证 lifecycle、controller/accountability、当前 key authorization、immutable provision ceiling、key scope 与本 operation 的 session scope。Agent key 不是 controller device。接收 Station 已持有这些当前私有权威事实时，可结合其已验证的 AgentRuntime session grant；grant 必须绑定同一 Actor、verification method 与当前 authorization。仅有 runtime 自报 key、公开 DID key 或 service transport signature 均不足以准入。
- provider 发起的 identifier request 的 `requester_id` 是 service principal；无 requester 的 identifier proof 绑定已认证 source service。服务 proof 与服务 outcome 从相应 service 的 accepted key binding／受信 DID authority 取得 key，不得将这种 service 验签规则用于 Account 或 Agent。key-material 的实际 requester 与 source Station 必须满足 §6 的原生 claim 授权，provider 服务身份不能替代 participant authorization。
- 远端 Account／Agent 必须通过该 operation 获准使用的当前、保密 authority evidence 验证，证据须绑定 exact identity 与签名 method；实际请求、目标 verifier 和范围由请求自身签名及授权检查绑定。`request_consent` 当前没有通用远端 PCR 披露 carrier；裸 ActorId、provider assertion、同 principal 的本机账号、历史 Event 或其它 operation 的 signer evidence 均不补足这个缺口。没有合法证据来源时 MUST 在创建 correlation 或读取 holder 私有状态前 fail closed（`proof_invalid`），MUST NOT 推导并查询远端私有 PCR。此限制不影响接收 Station 本地可验证的 requester 向任意 exact holder 地址发起 opaque request。

Bearer user session 只证明当前调用会话；它 MUST 与 `actor_id` 一致，并且仍 MUST 验证上述 actor proof。§5 封闭清单内的 operation 还 MUST 同时通过 §5 的 HTTP Message Signature，与是否跨 provider 或携带有效会话无关：provider transport proof 与适用的 participant authorization / actor operation proof 缺一不可，任何一层都不得替代另一层。

## 6. Key Material

`ak.open.mimi.exchange.request_key_material.v1` 是 [`../crypto-media/device-lifecycle.md` §9.0.1／§9.2](../crypto-media/device-lifecycle.md) 现有 claim 的适配入口。请求 MUST 直接符合 `keypackage-operations.schema.json#/$defs/keypackages_claim_request_body`，结果 MUST 直接符合同文件的 `peer_keypackages_claim_command_response_body`，不另包一层 MIMI DTO，不裁剪或复制 claim 字段，也不提供 GroupInfo-only 成功分支。

**适用资格与目标绑定**：调用 provider MUST 同时是该原生 claim 获准的 source Station；HTTP `Provider-ID`、`Source-Service-ID` 和 request 的 `service_binding.source_id` MUST 逐字相等，`Destination-Service-ID` MUST 等于 `service_binding.destination_id` 及实际接收 authority。source Station MUST 先按原生合同验证 exact requester 的 current device／Agent／已登记 Realm Device authorization，再转发其原签 canonical request。只有外部 provider 身份、目标 holder 同意或有效服务签名，均不能替代原生 participant authorization 与业务范围资格；不满足时 MUST fail closed，不得新增 provider-only requester 分支或由 facade 代签。

目标只由标准 claim 的 closed selector 确定，不从 provider 身份、自由 DID、MIMI identifier 或相似标识猜测。请求 MUST 通过原生 current membership／policy／endpoint gates，`required_capabilities` MUST 包含 `mimi.content.v1`，`last_resort_allowed` MUST 缺省或为 `false`，返回包 MUST 为 single-use。能力与 cipher suite 验证沿用原生 KeyPackage／LeafNode 和 MLS group 规则，不另设能力镜像。请求 MUST 携带 §5 已签覆盖的 `MIMI-Room-URI`；接收 authority MUST 在 claim CAS 的同一接受边界核对该 URI 的 current accepted room binding、`intended_realm_id`、`mls_group_id` 与实际 effective scope，错 room／Realm／group 或失效 binding 均不得领取。room URI 只定位既存 binding，不授予权限，也不加入第二套 participant transcript。

**唯一账本与结果恢复**：适配入口 MUST 使用原生 destination authority 的同一 `(source_id, claim_request_id)` ledger 与 canonical request digest；MIMI／原生接口不得按 URL 或 operation id 分出第二个领取域。`Idempotency-Key` MUST 等于 `claim_request_id`，HTTP signature 除 §5 的 provider 覆盖项外还 MUST 覆盖该 header，以及跨 trust domain 时原生 service-to-service 合同要求的两个 trust-domain header。首次成功与 exact replay 均返回原生带状态结果及原签 `claim_outcome`；其中 `claims[]` 已含 `claim_id`、KeyPackage bytes／ref、endpoint binding、expiry 与 capabilities，`claim_receipt` 负责原生签名归责。不得另外要求 MIMI outcome `signature` 或重新签发领取收据。响应丢失后只能按原生规则重放同一 canonical request，或以原 source 身份使用既有 `ak.peer.keys.keypackages.read.claim.v1` 查询；不得换领取身份、改请求或另领替代包。

**Welcome 与核销**：沿用原生 `MlsWelcomeDelivery.keypackage_claim_ref`，逐字引用上述 `claim_id`；Welcome 入队与单次绑定、recipient 查询原 claim、成功处理后 durable 保存群状态，再调用既有 `ak.self.keys.keypackages.command.consume.v1` 的完整规则均由 device-lifecycle §9 规定。发送或返回 KeyPackage 不等于 consumed；同一 claim 不得绑定第二份 Welcome，到期／撤权不得重新成为可用包。到期、重放、错 scope、撤权与 consume 响应丢失均复用原生拒绝／恢复规则，不新增 MIMI consume、查询端点或生命周期。

通过 transport 认证后的目标不存在、不可见、无材料、能力不满足、授权／policy 拒绝 MUST 使用原生不透明 `claim_failed` 外观，不返回目标设备列表、库存数或逐设备失败原因。transport 失败仍按 §5 在读取目标状态前拒绝。该最小 profile 不提供仅凭外部 provider 身份代领的通用互通能力；实现声明仍须满足已登记 profile 的全部要求，不能因本节收敛而豁免验收。

## 7. Message Submission

`ak.open.mimi.command.submit_message.v1` 接收 MIMI encrypted application message 后，facade MUST：

1. 验证 provider signature、room binding、destination、body digest 和重放窗口。在任何 Event 构造、提交、持久化 replay/delivery 状态或 fanout 前，MUST 从当前 accepted room binding 检查 `local_provider_role ∈ { hub, follower }`；若为 `observer`，整项 submit_message MUST 以 `mimi_observer_write_forbidden` 拒绝，且 Event、RealmCommit、current state、outbox、receipt、fanout 均为零。该 reason 的唯一生产路径是 `ak.open.mimi.command.submit_message.v1` 的 `mimi.submit_message.observer_role_guard`，由 operation registry 登记。
2. 验证 MLS epoch、已认证 GroupInfo／GroupContext group id、`ak.mimi.room_binding.mls_group_id` 与当前 accepted `MlsGroupValue.effective_scope` 的唯一派生 group id 均匹配；任一不符按 §4.1 fail closed。
3. 按 MLS key-access revision binding 验证：Commit 携带的 `governance_binding.key_access_revision` 与从 accepted key-access state 重算的值相同，消息 group/epoch 指向该 current winning group state；普通 Event 独立验证 producer proof，并验证 current governance Station 在接纳时解析授权实例后为它签发的 covering RealmCommit。Event 不把 Commit 或授权 basis 塞回 producer-signed bytes。
4. 将 MIMI content container 映射为 `ak.message.create`、`ak.message.revise`、`ak.message.redact`、`ak.reaction.add`、`ak.reaction.remove` 或 `ak.relation.*`。
5. 保留原始 MIMI envelope hash、provider id、message id 和 accepted timestamp 作为 interop metadata。
6. 对无法确认授权、epoch、content 或 policy 的消息返回 `temporarily_unavailable`、`dependency_missing`、`capability_denied` 或 `quarantine`。

**作者与外部归属（normative）**：入站映射生成的
`ak.message.create` / `ak.message.revise` / `ak.message.redact` Event 必须由 facade
自己的 service DID 签名，envelope `actor_id` 不得伪装成外部发送者。这三个 kind 的
admission 是 conditional：payload 省略 `mimi_provenance` 时走普通
`capability_gated`；携带 `mimi_provenance.provenance="mimi_facade"` 时走
`service_attested`。`mimi_provenance` 必须同时绑定来源 provider service DID、经 §10
consent / holder-claim 规则解析出的外部 sender actor、sender device、完整原始 submit
envelope 的 canonical SHA-256，以及当前 accepted `ak.mimi.room_binding` Event ref。
Reducer 必须验证 facade service 对目标 Realm/binding 的运营权限、binding 的
provider/room/Realm/Strand/MLS group 与 current key-access revision、来源 provider proof、
外部 sender 的 consent/membership/action 授权；revise/redact 还必须验证外部 sender 对
目标 Message 的修改/删除权限。HTTP provider signature 只证明来源传输，不能替代 Event
proof，也不能把外部 sender 的 authority 转授给 facade。两种 admission 分支不得同时匹配。

Arkret native 客户端发送到 MIMI room 时，facade MUST 将 signed Arkret Event 转换为 MIMI message，并把 MIMI provider accepted timestamp / message id 写回可验证 receipt 或 interop metadata。不得把 MIMI provider accepted timestamp 当作 Arkret Event 的 creation truth 或排序权：同一 Arkret stream 的事实顺序只由已验证 RealmCommit 的 `stream_position` 与 `previous_commit_ref` 决定；跨 stream 没有协议总序，只能使用已登记的 caller-scoped 展示排序规则。

## 8. Content Mapping

MIMI facade MUST 支持接收：

- `application/mimi-content`
- `text/plain;charset=utf-8`
- `text/markdown;variant=GFM-MIMI`

推荐映射：

| Arkret | MIMI |
| --- | --- |
| `ak.content.text` plain | `text/plain;charset=utf-8` body part |
| `ak.content.text` markdown | `text/markdown;variant=GFM-MIMI` body part |
| `ak.content.composite` | MIMI multipart / multiple body parts |
| `reply_context` + `replies_to` Relation | MIMI reply behavior field |
| `ak.reaction.add/remove` | MIMI reaction / unlike behavior |
| `ak.message.revise` | MIMI edit behavior |
| `ak.message.redact` | MIMI delete behavior |
| `message_expiration` policy | MIMI expiring message field |
| attachment `blob_ref` | MIMI external content / asset reference |
| Room thread / Message relation | MIMI topic / threading field |

规则：

- 发送到 MIMI 时，facade SHOULD 生成 MIMI required / recommended media type，同时 MAY 附带 `application/vnd.arkret.content+json` proprietary alternative 以保留无损 Arkret 内容。
- 从 MIMI 接收未知 extension field 时，facade MUST 保留原始 CBOR bytes 或 canonical hash，至少保证未来支持时可回放或审计。
- 任何正文 fallback 进入 E2EE Realm 时必须仍在密文中；不得为了 MIMI 预览把 `body` 明文复制到 routing metadata。
- Link preview、attachment thumbnail 和 asset metadata MUST 遵守 `asset_privacy_policy` 与 `plaintext_visible_services`。

### 8.1 Content Mapping Receipt

facade 在 Arkret ↔ MIMI 之间转换一条内容时，SHOULD 生成 **Content Mapping Receipt**（`receipt_kind="content_mapping_receipt"`，schema `ak.schema.mimi_interop.v1`，见 [`mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json)），作为该次格式映射的可审计证据。它记录 `mimi_room_uri`、`source_format` → `target_format`、被映射源信封摘要 `original_envelope_digest` 与目标 `mapped_operation_id`（可选携带 `mimi_message_id` / `arkret_event_id` / `accepted_at`），使双向投递的内容转换可被追溯与对账。该回执是 facade 本地或受控 interop-audit store 中的 signed metadata，**不是 Event Envelope、`receipt_kind` 不是 event kind、不得以裸 `kind` 写入 Realm history，也不在 event-kind-registry 登记**。需要把回执锚定到 durable history 时，facade MUST 另发已注册的 audit Event，并只引用 receipt digest；回执本体仍留在受控审计存储。该回执是 EXTENSION 范围对象，不进入 v1 core 互操作必需集。

**生成强度（normative）**：Content Mapping Receipt 是跨协议内容映射的唯一可审计证据。在 E2EE Realm、regulated-audit Realm（Realm policy 声明合规审计要求），或本地 binding `local_provider_role="hub"`（本地 facade 即拥有该 room URI、对外承担 room 真相投影责任）时，facade 在每次 Arkret ↔ MIMI 内容转换时 MUST 生成 Content Mapping Receipt；这些场景下缺失 receipt 的映射 MUST 被视为不可审计而拒绝或 quarantine。其余普通场景仍为 SHOULD。

## 9. Policy Mapping

Arkret v1 把 Realm-level policy 映射为 state-changing Event 的 registered current state projections。Facade 在 MIMI room policy 与 Arkret state 之间转换时，读取 registry 中的 `state_family`、`execution`、`domain reducer` 与 `value_shape`；安全状态只消费唯一确认的 RealmCommit 顺序。

### 9.1 current state Family 互译

| Arkret state_family | Arkret Event kind | MIMI policy component（draft-ietf-mimi-room-policy） |
| --- | --- | --- |
| `realm_join_rule` | `ak.realm.join_rule` | `participation` 中 `join_policy` 子字段（粗粒度入口枚举） |
| `realm_history_access` | `ak.realm.history_access` | MIMI 若能表达等价的 current-member history range 则映射；否则 fail closed，不臆造旧五档 visibility |
| `realm_discovery` | `ak.realm.discovery` | `participation` 中 `discoverability` 子字段 |
| `realm_alias` | `ak.realm.alias` | （Arkret 专属；MIMI 的 room URI / hub-local name 不是可映射 policy component） |
| `realm_policy_bundle` | `ak.realm.policy_bundle` | 没有独立 facet event kind 的 Realm policy 组件集合（`join_policy` / `agent_participation` / `account_deactivation` / `preauth` / 加密 floor 与 scheme 等）；对应 MIMI 的 `participation.join_policy`、`preauth` 与 `bot` 子字段 |
| `realm_asset_privacy_policy` | `ak.realm.asset_privacy_policy` | `asset` |
| `realm_plaintext_visible_services` | `ak.realm.plaintext_visible_services` | （Arkret 专属隐私透明度机制；MIMI 侧无对应） |
| `realm_media_service` | `ak.realm.media_service` | （Arkret 专属，与 MIMI 的 hub provider 解耦） |
| `realm_schema` | `ak.realm.schema` | （Arkret 专属，schema_refs 声明） |
| `realm_archive` | `ak.realm.archive` | （部分等价于 MIMI lifecycle hint，目前 MIMI 草案未规范） |
| `realm_freeze` | `ak.realm.freeze` | 同上 |
| `realm_tombstone` | `ak.realm.tombstone` | 同上 |
| `realm_destroy` | `ak.realm.destroy` | 同上 |
| `member_state` | `ak.member.state` | MLS GroupContext 的 leaf node + roster；Arkret membership 不进入 MIMI policy components |

#### 9.1.1 Candidate-profile-only 行（base profile MUST reject）

下表中的条目**不是** v1 base profile 的 wire `Event.kind`，仅在显式声明对应 candidate profile 的 facade 上可见。**base profile 下 MIMI facade MUST reject / omit 这些条目，而不得把它们写入 shared Realm history。** 把它们与 §9.1 主表的 base-profile Event kind 分开列出，避免误读为 base profile 必须支持。

| Arkret concept/action 名称 | 所属 candidate profile | MIMI policy component | base profile 行为 |
| --- | --- | --- | --- |

> 历史的 MIMI components（`roles`、`preauth`、`bot`、`message_expiration`、`operational`）在 Arkret 中都不是独立 Event kind。它们没有统一承载：facade 接收 MIMI policy update 时 MUST 按下表逐项归约到已登记的 Arkret 承载，再按 registry 派生 current state write；无法映射的子字段按 §9.2 unknown handling 处理，MUST NOT 塞进任何 closed payload 的未登记字段。
>
> | MIMI component | Arkret 承载 |
> | --- | --- |
> | `roles` | `ak.capability.grant` / `ak.capability.revoke`（capability 是 allow 的唯一来源，不是 policy 子字段） |
> | `preauth` | `ak.realm.policy_bundle` payload 的 `preauth` 组件（[`../identity/consent-model.md` §6.1](../identity/consent-model.md)） |
> | `bot` | `ak.realm.policy_bundle` payload 的 `agent_participation` 组件（[`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)） |
> | `operational` | 无 Arkret 承载；按 §9.2 unknown handling 处理 |
>
> MIMI room policy 投影 MUST 落在有效 Realm 的 `ak.realm.policy_bundle` current state；不存在 track-scoped policy projection——track 不携带独立 access。当 MIMI room 映射的 Strand 通过 `scope_circle_id` 落在 Realm 内的 [Circle](../models/circle.md) 时，Circle-local policy 通过 Circle 自身 accepted policy 投影表达，与父 Realm policy 取更严格者。 本段不适用于 read receipt policy：已读披露只按消息所属 scope 的独立 `ak.scope.read_receipt_policy` 执行，不做父子继承或取更严（见 [read-receipts §2.5](../discovery/read-receipts.md)）。

### 9.2 Unknown Handling

Arkret 的 unknown handling 来自登记的 state model 与 criticality：

| Arkret | MIMI |
| --- | --- |
| `commit-ordered projection` 安全语义或未知核心状态模型 | `must-understand` |
| `current-value projection` deterministic winner | `should-understand` / single current value with retained history |
| 非授权 projection extension | `silently-drop`，但必须保留 raw bytes 或 canonical hash |

**Facade 责任**：

- 接收 MIMI policy update 时 MUST 验证目标 `state_family` 已注册（或被部署的 profile 显式 opt-in），并归约为对应 state-changing Event `kind + payload`；未注册 MIMI component MUST 按其 MIMI unknown-handling 处理。
- 发送 Arkret state 到 MIMI 时 MUST 按 §9.1 表生成 MIMI component。Arkret 专属 component（无 MIMI 对应）在 facade 输出中标记为 `application/vnd.arkret.component+json` 私有扩展。

MIMI role 只能作为 interop projection。Arkret 授权仍以 capability state-changing Event / grant current state 为准。Facade 在接收 MIMI role/policy update 时 MUST 归约为具体 capability event（如 `ak.capability.grant` / `ak.capability.revoke` / `ak.capability.relinquish`）或具体 `ak.realm.<facet>` state-changing Event effect，并经过 Arkret state-changing Event refs 授权验证后才能生效。

**未知字段安全惰性（normative）**：interop schema 为前向兼容演进中的 IETF MIMI Internet-Draft，有意在 top-level 与 `mimi` / `binding_scope` / `payload` 子树保留开放 `additionalProperties`。接收方 MUST 把该 surface 上任何未识别字段视为**安全惰性**：MUST 忽略其参与任何安全判定，且 MUST NOT 让它影响 authorization、identity binding、`policy_revision`、MLS epoch / group state、routing / hub-follower 关系或任何 signature / digest transcript。已知字段仍以 schema pin 的定义为准；未识别字段只能作为不可信的 draft passthrough 保留（如需保留 raw bytes / canonical hash 见 §9.2 表）。实现 MUST NOT 依据未识别字段提升 provider role、改写 `policy_revision` 或放宽 governance binding 校验。

## 10. Identifiers And Consent

MIMI identifier MUST NOT 被直接作为 Arkret actor。映射规则：

- MIMI provider identifier 映射到 service DID。
- MIMI user identifier 映射到 principal DID、pairwise DID 或 pending invite proof。MIMI user → 既有 principal DID 的绑定 MUST 有目标侧 consent proof（如含相应 concrete scope 的原 accepted `ak.consent.replace`（仍核 current）、accepted invite proof）或该 principal holder 的显式 claim；facade MUST NOT 仅凭来源 MIMI provider 的断言或 connection identifier 相似性把入站 MIMI user 映射到既有 principal DID。缺少目标侧 consent proof 或 holder claim 时，facade MUST 将该 MIMI user 视为新的 pairwise DID / pending invite proof，而不得冒充既有 principal。
- connection identifier 仅用于 discovery / consent，不进入 Realm history，除非 holder 明确作为 handle / claim 披露。
- display name 只用于 UI，不参与授权。

current-v1 不提供 private-contact discovery／PSI（见 [`discovery/discovery-directory.md` §1／§6](../discovery/discovery-directory.md)）。`ak.open.mimi.read.identifiers.v1` 保留已登记的闭合 facade DTO，但没有可产生匹配的发现来源：认证与 proof 校验后必须对每个 commitment 返回 `matched=false`，不得返回 `mimi_uri`、`subject_id`、invite handoff 或 reachability proof；MUST NOT 调用未登记 operation、索引或轮转，也不得用 Consent 或 provider assertion 推导命中。`ak.open.mimi.command.request_consent.v1` / `ak.open.mimi.command.update_consent.v1` MUST 映射为 Arkret 的 holder-private consent state（`ak.consent.replace`，详见 [`identity/consent-model.md`](../identity/consent-model.md)）。Consent 不授予 Realm read/write 权限；加入和发消息仍需 membership、capability 和 policy checks。Facade 在两侧 round-trip 时 MUST 保留 `consent_id` 作为 inter-protocol correlation。

**`request_consent` 的不确定结果不可自动重放（normative）**：它仍是 `idempotency_mechanism=none`、
`retry_safe=false`，不因 correlation 精确化就获得重试幂等性。尚未写 Event 的私有 correlation **不在**
`ak.self.consent.read.list.v1` 里，因此不能用该列表恢复丢失的 `consent_id`；恢复策略是
`manual_confirmation`。**不新增** correlation 查询端点或可枚举 pending 状态：既有请求保持结果未知，
再发一次是**新的** correlation，不得被说成原请求的安全自动重放。

`holder_account_id` 是 requester 签名选择的收件对象，**不是** holder 已同意、存在或可见的证明。
创建 correlation 不查询也不公开 holder consent current state：对语法合法且 requester 已认证的请求，
MUST NOT 因 holder 不存在 / 不可见 / 未同意而产生可区分结果，一律回同一 opaque `consent_id`。
correlation 可以冻结一个最终无人能合法接受的目标——它没有授权效力。

`request_consent` 的请求体**直接写完整身份**：`requester_actor_id` 是 exact ActorId（含 Station 与 role），
`holder_account_id` 是 exact AccountId，`proofs` 必填。返回 `consent_id` 前 MUST 持久保存仅服务本地可见的
correlation：`(consent_id, requester_actor_id, holder_account_id, purpose, strand_id?, authenticated source
service/session class, created_at, expires_at?)`。该记录不是 Event、current state、授权或可对外查询的 pending consent state。

**为什么不再存裸 requester 与 `target`（normative）**：[`identity/consent-model.md` §6.1](../identity/consent-model.md)
的查询步骤 1 要求普通 peer 按**完整 ActorId** 比较并禁止降维到裸 principal，§6.1.1.2 的 holder 维度同样是完整
AccountId。correlation 若只冻结 principal core，`update_consent` 的「逐字对账」在 v1 里就没有可实施口径：
facade 要么降维比较（违反 §6.1），要么自己补一个 Station——那个 Station 不是任何一方声明的事实，
只是本 facade 当次的身份，换一个 facade 就换一个答案。因此本 operation 收窄为
**对已明确选定的 Arkret 身份请求同意**，不兼任别名解析：外部 identifier 到既有身份的映射仍按本节
目标侧 consent proof / holder claim 规则在**调用本 operation 之前**完成，映射不出来的外部用户维持 pending
handoff，MUST NOT 冒充既有账号。`target` 在其它 MIMI identifier / 发现操作里的用途不受影响。

`update_consent` 必须在验证 transport 与 actor proof 后，把 Event 解析得到的 holder/peer/scope 与该
correlation **按结构逐字相等**比较，不重新解析原目标：

```text
body.consent_id == correlation.consent_id
body.actor_id == event.actor_id == AccountActor(correlation.holder_account_id)
event.payload.peer == {kind:"actor",actor_id:correlation.requester_actor_id}
```

`consent_id` 只作私有 request correlation，原生许可 payload／selector 不携该 ID；多个请求 ID 可指同一 exact holder／peer current。purpose 仅为 concrete scope，删除 any，不隐式展开请求。correlation 继续冻结 exact requester／holder／purpose、来源 service/session class、有效期与原 optional strand；来源、holder、设备／root authority gates 与 operation proof 不变，provider transport 不授权 Actor 或完整读取。

所有 decision 只接纳调用方原签 `consent_event: EventAdmissionSubmission`，kind 必为 `ak.consent.replace`；Event 的 PCR 必须确属 exact holder，authorization_ref 绑定当前 root controller，独立 managed-behalf／consent_write delegation／co-owner／automation 不替代。客户端从 [Consent §6.3.1](../identity/consent-model.md#631-holder-private-完整-current-读取) 的获准 self 路径取得完整前态并签完整目标；facade 不以 correlation 读取或披露整份集合，不能补字段、翻译单项旧 Event、重建或代签。

- accept 只能新增／替换 correlation 的一个 scope；目标必须含该项，窗口／约束按普通规则验证，不表示接受后立即有效。
- deny／revoke 的签名前态必须已有该项（可以已过期），目标仅移除该项，删除最后一项形成 empty；从未写入或该项缺失时零写入拒绝，不合成“拒绝成功”Event。
- 其它 scope 的完整条目、窗口、约束及 optional 成员存在性必须保持。比较使用 Event 签入的 exact 前态；facade 只比较已认证的完整 exact 前态；最终 current authority 必须在同一 PCR 接受事务验证该 exact revision／never_written 谓词并执行完整替换。仅历史差异比较不能代替最终 current CAS。已验证非 Human 分离 governor 时，hosting facade 经原获准完整读取验证前态后转交同一原签 Event；authority 的 exact CAS 保证接受的前态仍是那一份，不新增 correlation 跨站披露载体或假定分布式事务。跨 scope 修改走原生显式完整替换。

无效／过期／错来源／错身份／不可见 correlation、decision 差异不符或新的 stale CAS 都沿原同形 not_found 隐私边界拒绝，不披露 holder／current 是否存在；通用 schema／签名失败保留原分类。exact 已接纳 Event 重试保留原 correlation／decision／Event 绑定，重验当前重试披露权后返回原 outcome／event_ref，不以之后 current 重算旧差异、不重复写入或回滚其它 scope。不同 correlation 不得拿同一 accepted Event 冒充另一操作。首次提交前 facade 必须耐久冻结该 correlation／decision／exact Event 绑定；unknown 保持这同一绑定并沿原 Event 终局恢复，不构造新替换。成功返回原 closed mimi_update_consent_response_body，不添加 status 或其它未登记字段。

## 11. Abuse Report And Proxy Download

`ak.open.mimi.command.report_abuse.v1` 的 durable effect 是一条由接收 facade service 自己签发、以 `service_attested` 接纳的 `ak.self.moderation.report` Event，不桥接 `ak.self.moderation.command.report.v1`。外部 Provider 或举报人均不得提交这条 Event 的 producer proof；facade 也不得将举报人的 Actor 冒写成 Event actor。E2EE 举报 claim SHOULD 携带 message franking proof 与 encrypted evidence package。facade MUST NOT 要求 reporter 向普通 provider 上传未加密明文；只有被 Realm policy 授权的 moderation recipient 可以解密 evidence。

入站 request 是 closed `{reporter_authority, report_claim}`。`report_claim` 携带 Realm、scope、target、reason、description 与可选加密 evidence/franking；它不携带 reporter、provider、provenance 或 Event actor 的镜像。`reporter_authority` 携带完整 `actor_id`、exact current accepted `membership_ref` 与 `room_binding_ref`（均为四坐标 `CommittedEventRef`）、短期 `expires_at` 与 holder detached JWS `proof`。source provider 唯一来自 RFC 9421 authenticated Provider-ID/source service；body 自报身份不授权。

本地 detached-signature domain `ak.mimi_reporter_authority_proof.v1` 的唯一 transcript 覆盖完整 request，只删除 `reporter_authority.proof`：`payload_digest` 由 `{reporter_authority（不含 proof）, report_claim}` 的 RFC 8785 canonical bytes 计算；binding 还包含由 `reporter_authority.actor_id` 注入的 `issuer`、固定 `operation_id=ak.open.mimi.command.report_abuse.v1`、两个完整 `CommittedEventRef`、`expires_at` 与 proof `verification_method` / `created_at` / `domain` / `audience`。`domain` MUST 是该本地签名域，`audience` MUST 是接收 facade service。facade 必须从 exact Actor 当前 accepted device/agent proxy authority state 解析 verification method 与授权链；carrier 自报 key、Provider assertion、同 principal 本机账号、consent、holder claim 或 opaque evidence 都不能替代。proof 过期、设备/代理撤销、claim 中 room/target 被替换，均在读 target 私有状态或写 Event 前拒绝。

facade 必须逐项验证两个 ref 的 Event、RealmCommit、stream 与 position，并确认它们在同一 current accepted checkpoint 下仍分别是：(a) `actor_id` 在 exact Realm 的 joined participation；(b) 该 canonical room 对 exact Realm/Strand/provider 的唯一 accepted binding。相同 principal 的其它 Station membership 不匹配；零个或多个 current binding、ref 已被 successor/revoke 覆盖、room/provider/realm/strand 任一不一致都按 `mimi_reporter_resolution_required` 统一拒绝且零副作用。随后 restricted Realm/Circle visibility 与 per-reporter 限速使用完整 `actor_id`；attribution Event payload 中 `reporter_id` 只保存 principal，并至少按 `(actor_id, authenticated Provider-ID)` 双维度限速。consent-only、opaque 非空与 pairwise/pending reporter 一律不能产生 Arkret moderation Event。

**服务作者与原子幂等（normative）**：全部校验通过后，facade 以自己的 service Actor 与当前服务签名 key 创建 Event；其 Realm、scope、target、reason、description、evidence/franking 唯一取自已验证 `report_claim`，payload `reporter_id` 唯一取自 `reporter_authority.actor_id.signing_principal_id`，`provenance` 固定为 `mimi_facade`，`source_provider_id` 唯一取自 transport 已认证 Provider-ID。Event actor MUST 是被 Realm 授权的 facade service DID，不能是 reporter Actor。接纳时重新核对同一 current cut 的所有引用、服务权限与安全策略，签 Event／RealmCommit、写报告 current state 和以 authenticated Provider-ID 分区的 canonical full-body hash 幂等映射必须原子提交；失败零写入，同一请求逐字节重放返回同一已接纳结果和 report ID，异内容重用 reporter proof 拒绝。facade 不得先写私有 report 再尝试 Event admission，也不得把该 operation 降级为只返回本地排队状态。

`ak.open.mimi.command.proxy_download.v1` MUST 遵守 `ak.realm.asset_privacy_policy`。当 policy 要求 `provider_proxy` 或 `ohttp_relay` 时，facade 不得返回 direct object-store URL。下载成功不证明内容可信，客户端仍 MUST 验证 content hash、ciphertext digest 和 attachment metadata。

**被代理 URL 的出站网络目标策略（normative，SSRF 防护）**：`proxy_download` 是 facade 代外部资产做 server-side fetch 的高危面。facade 在抓取被代理资产 URL（含 redirect / Alt-Svc 后实际目标）前 MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝代理（reason code `egress_policy_denied`），不得向内部地址发起请求。被代理 URL 来自对端 provider，恶意 / 被攻陷 provider 可借此诱导 facade SSRF，故该校验 MUST 不可绕过。

## 12. Conformance

`ak.profile.mimi_interop.v1` MUST 测试：

- provider directory draft pinning 与 service DID 签名。
- `ak.mimi.room_binding` 创建、更新、撤销和 policy root 校验。
- KeyPackage single-use claim / Welcome consume。
- Arkret message 到 MIMI content roundtrip。
- MIMI text / markdown / reply / reaction / edit / delete / attachment 接收映射。
- MIMI policy update 归约为 Arkret capability / policy state。
- E2EE MIMI projection 必须满足 full MLS Governance Binding 下界；未声明 relaxed 降级不得按 full binding 接受。
- identifier query 不泄露 raw connection identifier。
- identifier query MUST NOT 返回任何形式的 "reachability proof"（§10 的强禁令负向可测项；facade MUST NOT 复活已被移除的 reachability proof 机制）。
- consent 不自动授予 membership / write capability。
- E2EE report franking 验证。
- report authority exact-binding：合法 holder proof 可提交；同 principal 异 Station、provider/room/target swap、撤销/过期、consent-only、opaque 非空、多个 current binding 歧义均零副作用。
- proxy download 遵守 asset privacy policy。
- unsupported draft version fail closed。

## 13. 设计决定

Arkret v1 的 MIMI 支持固定为 facade profile：

- 不把 MIMI hub 变成 Arkret 的唯一 truth source。
- 不用 MIMI room id 替代 `realm_id`。
- 不用 MIMI user identifier 替代 DID。
- 不绕过 Arkret capability state-changing Event refs 与本地授权检查。
- 不把 MIMI provider accepted timestamp 当作 Arkret Event ID、RealmCommit 顺序、授权、接纳或 finality 的替代物。
- 支持 MIMI 草案版本 pinning，并允许未来 profile 处理草案变化。
