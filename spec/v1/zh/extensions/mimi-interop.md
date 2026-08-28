---
title: MIMI Interoperability
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

> **状态：interop extension profile（非 v1 core 互操作必需）**。本文档描述的 MIMI Provider Facade 跟踪的
> 是仍在演进的 IETF MIMI Internet-Draft。Arkret v1 core 互操作 **不要求** 实现 MIMI
> facade；声称 `ak.profile.principal_server.v1` 或 `ak.profile.full_client.v1` 的实现
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
| Provider | `mimi_provider_facade` service DID，通常由 Principal Server、notary service 或受托 bridge 暴露。 |
| Hub provider | 对外拥有 MIMI room URI 的 provider service；在 Arkret 侧通常映射为 Principal Server 或 notary service，负责 MIMI room fanout 和 groupInfo。 |
| Follower provider | 参与 MIMI room 的远端 provider；在 Arkret 中表现为 federation peer 或 Applet bridge peer。 |
| User / client | Arkret principal DID + device id，可按 Realm policy 使用 pairwise DID 或 room-scoped pseudonym。 |
| Room | Arkret Strand discussion track 的 MIMI room 投影，可附带所在 Realm 的最小上下文。 |

MIMI facade 不是新的真相源。Arkret native 侧的 canonical truth 是 signed DataEvent、Control Move、Seal coverage、Lattice cell state、capability refs 与 MLS Security Frontier Binding（`governance_binding.security_frontier_digest` + current winning group-state projection）。MIMI room state 是对这些状态的互操作投影。

## 3. Provider Discovery

支持 MIMI 的服务 MUST 在 DID Document service entry 和 `GET /_arkret/describe` 中声明：

```json
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
      "group_info",
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

目录响应 MUST 绑定 service DID、provider id、base URL、支持草案版本、endpoint 列表、MLS cipher suites、内容 profile、room policy components 和签名 proof。客户端和远端 provider MUST 验证 service DID、HTTP Message Signature、TLS endpoint、DID service endpoint 和 Realm policy 委托一致。

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

允许被导出为 MIMI room 的 Arkret 对象 MUST 有写入 `ak.component.mimi.room_binding.v1` cell 的 Control Move registered projection。对应 Event kind 为 `ak.mimi.room_binding`；cell subject 是 `payload.mimi_room_uri`，registry 中的 `cell_subject.kind` 为 `uri`。

**`mimi_room_uri` canonical wire form 与 cell subject 编码（normative）**：`mimi_room_uri` 既是 wire 字段又是 `state_root` leaf 的 preimage 与排序键，因此它 MUST 是**封闭 canonical 形态**；receiver MUST NOT 先归一化再接受，非 canonical 输入 MUST 以 `schema_violation` 拒绝。若 `mimi://Example.com/r/1` 与 `mimi://example.com/r/1` 各落一个 cell，同一 room 就能有两个「首个 accepted binding」，§4.2 的初始状态与 `revoked` 终态都能靠换写法绕过。

canonical 形态（机读真源是 [`mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 的 `$defs/mimi_room_uri`）：

- scheme 固定小写 `mimi://`；authority 只允许 `host[:port]`，MUST NOT 出现 userinfo；
- host MUST 是小写 A-label（IDN MUST 已 punycode；MUST NOT 出现大写或 U-label），每个 label 以 ASCII 字母数字起止；
- port 只在非默认端口时出现，MUST NOT 有前导零，且 MUST 在 `1..=65535` 内；默认端口 `443` MUST NOT 显式书写；
- path MUST 至少一个非空 segment，MUST NOT 出现 `.` / `..` segment，MUST NOT 有尾随 `/`；
- MUST NOT 携带 query 或 fragment；
- percent-escape MUST 使用大写 hex，且 MUST NOT 编码 unreserved octet（RFC 3986 §6.2.2.2 的最小编码）；
- 整串长度 MUST ≤ 512 octet。

canonical CellRef subject 由该 canonical URI 的 exact UTF-8 bytes 按 [`../conformance/encoding.md` §4](../conformance/encoding.md) 的 `uri` subject kind **全量** percent 编码得到（`:` `/` `%` 一并编码，`%` → `%25`），例如：

```text
mimi://mimi.example.com/rooms/01JSMIMI
→ ak:cell:ak.component.mimi.room_binding.v1:mimi%3A%2F%2Fmimi.example.com%2Frooms%2F01JSMIMI
```

实现 MUST NOT 改用 hash 化 subject、URI 片段截取，或在 payload 中另立一个 caller 分配的 room 标识符作为 subject——后者会给同一 room URI 制造第二个身份，使 §4 的 1:1 语义无法在 wire 上强制。canonical 形态与 subject 编码的正反例由 [`ak.vector.encoding.cell_subject_uri.v1`](../../artifacts/registry/vector-registry.json) 唯一闭合。

`ak.mimi.room_binding` 的完整 payload 形态（含 `hub_provider`、`follower_providers`、`content_profile`、`policy_root`、`local_provider_role` 等全部字段）以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威机读真源；下文逐字段说明不替代该 schema。

```json
{
  "kind": "ak.mimi.room_binding",
  "payload": {
    "profile": "ak.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
      "strand_id": "ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa"
    },
    "hub_provider": "ak:did_core:webvh:z5dPBhAYJdfYhFqD3peyGJcxj",
    "local_provider_role": "hub",
    "status": "accepted",
    "follower_providers": [
      "ak:did_core:webvh:z2B174DcqrzvV5vkzDBdSwVvy"
    ],
    "mls_group_id": "base64url...",
    "content_profile": "application/mimi-content",
    "policy_root": "sha256:...",
    "created_at": "2026-04-30T00:00:00Z"
  }
}
```

规则：

- `binding_scope.realm_id` MUST 指向一个 accepted Realm。`strand_id` MUST 指向该 Realm 内启用 discussion track 的 accepted Strand；MIMI room timeline 只投影该 Strand discussion track 的消息。
- `hub_provider` MUST 是 Realm policy、Organization principal 或 member principal 明确委托的 service `did_core_id`；委托证据中的 service `did` / VM 必须经 adapter 投影到该值。
- `local_provider_role` 取值为 `hub`、`follower` 或 `observer`（封闭枚举，以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。各值语义:
  - `hub`:本地 facade 即拥有该 MIMI room URI 的 hub provider,负责 room fanout 与 groupInfo,对外承担 room 真相投影责任;
  - `follower`:本地 facade 作为 follower provider 参与远端 hub 拥有的 room,接收 fanout 并向 hub 提交本地 writes;
  - `observer`:本地 facade 只读投影该 room（监听 fanout / groupInfo 用于本地呈现或审计），MUST NOT 代表本地参与方向 MIMI room 提交 writes 或承担 hub fanout 职责。
- `ak.mimi.room_binding` 的创建、更新和撤销 MUST require `ak.policy.manage`、`ak.realm.admin` 或等价 interop capability。
- E2EE MIMI room MUST 绑定 `mls_group_id`，并按 [`../crypto-media/encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md) 校验当前 epoch 的 `security_frontier_digest`；membership、实际 leaf key 与 key-access policy 进入 frontier，普通 capability 仍由 Event admission 独立校验。
- MIMI facade 在无法解析或验证 Arkret MLS Governance Binding 时 MUST fail closed：入站 MIMI room state、groupInfo、key material 或 message 不得直接投影到 Arkret Realm，而是进入 quarantine，reason=`mimi_governance_binding_missing` 或更具体的 binding mismatch 错误。
- 撤销 binding 后，facade MUST 停止接受新的 MIMI writes，只允许 backfill、tombstone、report、legal hold 或 migration proof 等维护操作。`status` 的完整生命周期状态机（初始状态、合法迁移、终态、非法迁移拒绝、`migrating` 窗口与并发收敛）见 §4.2。

**E2EE MIMI 互操作下界（normative）**：凡 MIMI room binding 携带 `mls_group_id`、groupInfo、key material 或加密 application message，并要投影到 Arkret Realm / Strand，facade MUST 把 Arkret `ak.profile.mls_governance_binding.full.v1` 当作最低 E2EE 互操作能力，而不是把 MIMI provider 的 room state 当成等价治理真相。具体要求：

- `ak.mimi.room_binding.mls_group_id`、MIMI groupInfo 中的 group id、Arkret `governance_binding.mls_group_id` 必须一致；
- `governance_binding.binding_profile` 与 `governance_binding.reducer_profile` 必须存在且被本 facade 支持；未知或缺失时不得用 MIMI draft 字段、provider 目录或本地配置补齐；
- current winning MLS group state 的 `security_frontier_digest` 必须等于从当前 accepted key-access state 重算的值；
- MIMI 未知字段仍按 §9.2 安全惰性处理，不得提升 provider role、放宽 `policy_root` 或改变 MLS epoch / group state 判定。

`ak.profile.e2ee_relaxed.v1` 不得被 facade 对外表述为等价 full MLS Governance Binding。若本地 Realm 是 relaxed 降级，facade 只有在双方都显式声明 Arkret relaxed 语义、且满足 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.4.1 的 federation guard 时，才可投影 relaxed 窗口内的消息；否则 MUST reject / quarantine，reason 使用 `mimi_room_state_incompatible`、`mimi_governance_binding_missing` 或 `mimi_governance_binding_mismatch`。

### 4.1 Fail-Closed Reason Taxonomy

MIMI facade 对 Arkret Realm 的入站投影失败时，MUST 使用稳定 reason code，避免不同 provider 把 fail-closed 结果折叠成不可测试的通用错误：

| reason_code | 触发条件 | 外部行为 |
| --- | --- | --- |
| `mimi_governance_binding_missing` | 找不到可验证的 Arkret MLS Governance Binding。 | quarantine 或 reject，不投影到 Realm。 |
| `mimi_governance_binding_mismatch` | binding 存在但 `realm_id` / `strand_id` / `mls_group_id` / provider DID 与当前 MIMI room state 不一致。 | quarantine；需要人工或 backfill 复核。 |
| `mimi_policy_root_mismatch` | MIMI policy component 与 Arkret `policy_root` / `ak.realm.policy_bundle` 不一致。 | reject 当前 update，等待 fresh policy projection。 |
| `mimi_room_state_incompatible` | MIMI room state 使用当前 profile 不支持的 lifecycle、membership、policy 形态，或试图把未被双方显式声明支持的 `ak.profile.e2ee_relaxed.v1` 降级当作 full MLS Governance Binding 投影。 | reject 或要求使用新 interop profile。 |
| `mimi_provider_unreachable` | provider directory、key material 或 groupInfo 依赖暂时不可达。 | `temporarily_unavailable` + bounded retry；不得接受无 binding 的 fallback。 |
| `mimi_draft_unsupported` | 对端声明的 MIMI draft version 不在本 profile 支持集合。 | reject；不得按相近草案猜测解析。 |
| `mimi_room_binding_status_transition_invalid` | `ak.mimi.room_binding.payload.status` 初始值非法、迁移不在 §4.2 表内，或试图修改 `revoked` 终态。 | reject；不得把缺失或未知 status 当作 accepted。 |
| `mimi_observer_write_forbidden` | `local_provider_role=observer` 的 binding 试图代表本地参与方向 MIMI room 提交 write。 | reject；observer 只读投影不得产生 write side effect。 |

### 4.2 `status` 生命周期状态机（normative）

`payload.status` 是 binding 的生命周期判定字段，取值为封闭枚举 `proposed`、`accepted`、`revoked`、`migrating`（以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。状态迁移规则：

- **初始状态**：对某个 `mimi_room_uri` 的首个被接受的 `ak.mimi.room_binding` Control Move MUST 把 `status` 设为 `proposed`（跨 provider 协商中，等待对端确认）或 `accepted`（本地 facade 即 hub 且无需对端确认时可直接激活）。以 `revoked` 或 `migrating` 作为初始状态的写入 MUST 被拒绝。
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
- **`migrating` 窗口语义**：进入 `migrating` 后，facade 对该 binding MUST 停止接受新的 MIMI writes 投影，仅允许 backfill、tombstone、report、legal hold 与 migration 所需的 groupInfo / state 转移及 migration proof 提交；`migrating -> accepted` 的 Control Move MUST 引用已验证的 migration proof 并携带 `payload.migration_outcome ∈ {completed, rolled_back}`（其它转换 MUST NOT 携带该字段），使"迁移完成"与"回滚"在 binding 状态上可区分、可审计；hub / follower 拓扑变更只能随该迁移落地。
- **可写性判定**：仅 `accepted` 状态接受新的 MIMI writes 投影。`proposed` 状态下 facade MUST NOT 把 MIMI room state 投影到 Realm（目录 / 协商类流量除外）；`revoked` 后行为见 §4 撤销规则。
- **并发收敛**：`ak.mimi.room_binding` 是写入 `ak.component.mimi.room_binding.v1` cell 的 Control Move，并发更新由控制面 Seal 串行化仲裁，不存在数据面并发合并；后到的冲突 Move 在其 seal basis 下按本状态机重新校验，非法即拒绝。

## 5. Endpoint Surface

MIMI facade 至少定义以下 canonical operation：

| operation_id | HTTP binding | 语义 |
| --- | --- | --- |
| `ak.open.mimi.read.provider_directory.v1` | `GET /_arkret/open/mimi/provider-directory` | 返回 MIMI provider feature profile。 |
| `ak.open.mimi.exchange.request_key_material.v1` | `POST /_arkret/open/mimi/key-material` | 领取 MLS KeyPackage，映射到 Arkret KeyPackage claim lifecycle。 |
| `ak.open.mimi.command.update_room.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/update` | 提交或转发 room state / MLS update。 |
| `ak.open.mimi.command.notify.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/notify` | provider 间投递通知、fanout 或 delivery event。 |
| `ak.open.mimi.command.submit_message.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/messages` | 提交 MIMI encrypted application message。 |
| `ak.open.mimi.read.group_info.v1` | `GET /_arkret/open/mimi/strands/{strand_id}/group-info` | 获取 MLS groupInfo / room projection。 |
| `ak.open.mimi.command.request_consent.v1` | `POST /_arkret/open/mimi/consent/request` | 请求建立跨 provider 联系或 room invite consent。 |
| `ak.open.mimi.command.update_consent.v1` | `POST /_arkret/open/mimi/consent/update` | 提交调用方已签名的 `ak.consent.grant` / `ak.consent.revoke` Event。 |
| `ak.open.mimi.read.identifiers.v1` | `POST /_arkret/open/mimi/identifiers/query` | 查询 connection identifier / MIMI URI 的可达性。 |
| `ak.open.mimi.command.report_abuse.v1` | `POST /_arkret/open/mimi/report-abuse` | 提交跨 provider abuse report，支持 E2EE franking proof。 |
| `ak.open.mimi.command.proxy_download.v1` | `POST /_arkret/open/mimi/proxy-download` | 代理或 oblivious 下载资产。 |

`update_room` 以请求中的语义判别器 `update.kind` 选择封闭效果分支；`update.kind` MUST 与
decoded opaque payload 内的 `kind` 逐字相同，二者不一致必须在读取 room/binding 私有状态前
以 `mimi_room_binding_event_invalid` 拒绝。普通 MIMI room/MLS update 是 receipt-only facade
operation，不产生 Arkret Event。若 `update.kind == "ak.mimi.room_binding"`，请求 MUST 同时携带完整的
caller-authored、caller-signed `room_binding_event` (`EventInitialSubmission`)。facade MUST
验证该 Event 的 exact payload 与 path room、目标 Realm/Strand、`mls_group_id` 及已认证的
MIMI operation 一致，再将 exact bytes 送入 ordinary Event admission；MUST NOT 合成、
重建、代签或 co-sign actor Event。binding 分支缺少该 Event、非 binding 分支携带该字段、外层与
decoded kind 不一致或 Event 绑定不一致，MUST 对外合并为同一个
`mimi_room_binding_event_invalid`（相同 HTTP status 与 body shape），精确原因只写内部 audit；conformance vector `ak.vector.mimi.room_update_branched_effect.v1` 同时锁定 binding 与 receipt-only 两个分支；该失败
不得依赖 room 是否存在、是否已有 binding 或目标 Realm 私有状态。普通 Event admission 的标准失败码
在 pre-admission 通过后按其已登记合同返回。非 binding update MUST omit `room_binding_event`。

所有写入型 endpoint MUST 使用 HTTP Message Signatures 或等价 service proof，并绑定：

- source service DID
- destination service DID
- provider id
- MIMI room URI 或 target identifier
- request canonical hash
- created / expires
- body digest

HTTP Message Signature profile（适用于 provider-to-provider 写入）：

- 请求 MUST 携带 `Signature`、`Signature-Input`、`Content-Digest`、`Source-Service-ID`、`Destination-Service-ID` 和 `Provider-ID`；room-scoped endpoint 还 MUST 携带 `MIMI-Room-URI`。
- sender MUST 按 [`../sync/service-http-binding.md` §2.5.1](../sync/service-http-binding.md) 把 `canonical_json(request_body)` 的结果逐字节作为 exact HTTP message content，且不得应用 `Content-Encoding`；`Content-Digest` MUST 是 RFC 9530 `sha-256=:base64(SHA-256(exact_http_content_bytes)):`。receiver MUST 先校验 exact content bytes 的 `Content-Digest`，再严格解析并确认 wire 本身就是 canonical JSON，并从这些 bytes 内部计算 Arkret request digest；MUST NOT parse arbitrary JSON 后仅对 canonicalized value 求 digest。
- `Signature-Input` 的 covered components MUST 至少包含 `@method`、`@target-uri`、`@authority`、`content-digest`、`source-service-id`、`destination-service-id`、`provider-id`；room-scoped endpoint MUST additionally cover `mimi-room-uri`。`created`、`expires`、`keyid` 和 `alg="ed25519"` 参数 MUST 存在，且 `expires-created <= 300s`、`created` 在接收方时钟 ±30s 内、`expires` 未过期。
- `keyid` MUST 是 `Source-Service-ID` 所控制的 Ed25519 verification method；接收方 MUST 用已接受的 service key binding 或已配置信任根取得它。只有新 service / key、binding invalidation 或显式 freshness 失效时才做 DID authority resolution，普通请求不得逐次在线解析。HTTP signature 只认证 provider service source，不替代 Actor DID/device 签名、MLS transcript、capability 或 Realm policy 校验。

本 profile 的失败码与 [`applet-integration.md` §7.3.1](./applet-integration.md) 的逐次投递来源签名同源，按
[`../sync/api-conventions.md` §5](../sync/api-conventions.md) 只用 RFC 9457 Problem `type` 分派，MUST NOT
返回通用 code 再用 `reason` / `reason_code` 二次分派：

- 缺 `Signature` / 纯 bearer：`http_signature_required`（401）。
- 签名验证失败、必需 header 缺失、`Content-Digest` 不覆盖 exact HTTP content bytes、wire 不是 canonical JSON，或 `Source-Service-ID` / `Provider-ID` / `MIMI-Room-URI` 与 transcript 不一致：`http_signature_invalid`（401）。
- `created` / `expires` 超出上述时效窗口：`signature_window_invalid`（401）。

这三个 code 已在 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 登记，并在
[`operations-error-mapping.json`](../../artifacts/registry/operations-error-mapping.json) 中逐条挂在要求本
signature profile 的 MIMI 写入 operation 上；未挂载该 profile 的 read operation 不得返回它们。

Facade 接收请求后 MUST 先验证 MIMI envelope，再映射为 Arkret DataEvent、Control Move 或 to-device message。MIMI 传输签名只证明 provider 来源，不替代 Actor DID / device 签名、MLS transcript、capability 或 Realm policy。

### 5.1 MIMI operation actor proof（normative）

MIMI DTO 中名为 `signature` 或 `proofs[]` 的字段是 Actor DID/device 对具体操作的 detached payload proof，不是 Event Envelope proof。它 MUST 使用 `payload_digest`，MUST NOT 使用只适用于 Event Envelope 的 `event_digest`。单值形态由 `mimi-operations.schema.json#/$defs/signature` 定义，数组形态由各对象族自己内联的 `proofs[]`（元素为 `#/$defs/proof`）定义；两者的 `domain` MUST 等于接收部署的 `trust_domain`，`audience` MUST 覆盖接收 Principal Server service DID。

**每个对象族一个 context（normative）**：`mimi-operations.schema.json` 是 DTO 容器而不是一个对象族，因此**不存在**覆盖全文件的 MIMI operation context。持有 detached proof 的对象族逐个登记独立 context，schema 侧以 `x-arkret-proof-context` 逐字投影；对象族、context 与 operation 的对应关系分别以 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json) 和 [`operation-registry.json`](../../artifacts/registry/operation-registry.json) 经 schema ref 连接后的结果为唯一真源，本节不复述派生 join 表。

发送方 MUST 先从 request/outcome body 移除顶层 `signature` 或 `proofs` 成员（删除成员本身，不是置为 `null`），保留所有实际存在的 optional 字段，对剩余完整对象计算 `payload_digest = sha256(canonical_json(unsigned_body))`，再以 canonical JSON 编码并签署下列 transcript：

```json
{
  "context": "<该对象族在 proof-context-registry 中登记的 context>",
  "payload_digest": "sha256:<lowercase-hex>",
  "issuer": "<request.actor_id | request.requester | request.requester_id>",
  "operation_id": "<由 schema ref 在 operation-registry 中连接到的 operation>",
  "verification_method": "<proof.verification_method>",
  "created_at": "<proof.created_at>",
  "domain": "<destination trust_domain>",
  "audience": "<destination Principal Server service DID>"
}
```

transcript 的完整 binding fields 逐族列在 registry 的 `binding_fields`：`issuer` 只在该对象族的 wire 形态定义了发起方字段时出现（`mimi_key_material_request_body.requester`、`mimi_request_consent_request_body.requester_id`、`mimi_update_consent_request_body.actor_id` MUST 出现；`mimi_identifier_query_request_body.requester` 可缺席，缺席时 transcript MUST 同时省略 `issuer`），outcome 族的签发方身份只由 `verification_method` 承载。除公共字段外还 MUST 逐字加入该族的目标标识：`mimi_key_material_request_body` 加 `strand_id` 与 `device_id`；`mimi_request_consent_request_body` 加 `target` 与 `purpose`；`mimi_update_consent_request_body` 加 `consent_id` 与 `decision`；`mimi_group_info_outcome` 在 `room_binding_ref` 存在时加该字段。

字段顺序不影响 canonical JSON；`audience` 也可为至少覆盖目标 service DID 的非空无重复字符串数组。接收方 MUST 重算 unsigned body digest，验证 `issuer` 等于该族的发起方字段、当前 DID Document 授权的 `verification_method`、`kind=detached_jws`、`alg=Ed25519`、精确的 context/operation/domain/audience 绑定和 JWS。**接收方 MUST 拒绝 context 与本 operation 对象族不一致的 proof**：在一个族下有效的签名不得被另一个族接受，跨 operation 与 request/outcome 方向的重放由 context 本身阻断，不依赖 `operation_id` 是否被某个实现纳入 transcript。`created_at` MUST 位于接收方当前时钟前后 300 秒内。proof 失败 MUST 在写 consent state 之前拒绝；同一 proof 只能随其已绑定的完整 body 使用。相同 `consent_event.event.event_id` 与 byte-identical Event 的请求重放是 §10 定义的 retry-safe 例外，MUST 返回原 accepted Event ref；相同 Event ID 携不同 canonical Event bytes MUST `duplicate_conflict`，不得被 proof replay 检查改写成另一种成功或提前泄露 holder state。

Bearer user session 只证明当前调用会话；它 MUST 与 `actor_id` 一致，并且仍 MUST 验证上述 actor proof。跨 provider 调用还 MUST 同时通过本节的 HTTP Message Signature：provider transport proof 与 actor operation proof 缺一不可，任何一层都不得替代另一层。

## 6. Key Material

`ak.open.mimi.exchange.request_key_material.v1` MUST 使用 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) 的 KeyPackage claim API。请求必须包含：

- target MIMI identifier 或 DID / pairwise DID。
- intended MIMI room URI 和 Arkret `realm_id`。
- required content profile、MLS capabilities 和 cipher suites。
- requester provider DID 和 proof。
- 是否允许 minimal-metadata pseudonymous credential。

响应 MUST 返回 claimed KeyPackage、`claim_id`、`keypackage_ref`、device binding、expiry 和 supported capabilities。KeyPackage 被 Welcome 成功使用后 MUST 进入 `consumed`。不可见用户、无可用设备、policy denied 和不存在目标 SHOULD 使用统一失败形态，避免枚举。

## 7. Message Submission

`ak.open.mimi.command.submit_message.v1` 接收 MIMI encrypted application message 后，facade MUST：

1. 验证 provider signature、room binding、destination、body digest 和重放窗口。同时 MUST 校验本 binding 的 `local_provider_role ∈ { hub, follower }`;`local_provider_role=observer` 的 binding 不得代表本地参与方提交 writes(见 §4),facade MUST 拒绝该 submit_message,reason=`mimi_observer_write_forbidden`。
2. 验证 MLS epoch 与 `ak.mimi.room_binding.mls_group_id` 匹配。
3. 按 MLS Security Frontier Binding 验证：Commit 携带的 `governance_binding.security_frontier_digest` 与从 accepted key-access state 重算的值相同，消息 group/epoch 指向该 current winning group state；普通 Event `seal_ref` 另行通过 admission。
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
provider/room/Realm/Strand/MLS group 与 current security frontier、来源 provider proof、
外部 sender 的 consent/membership/action 授权；revise/redact 还必须验证外部 sender 对
目标 Message 的修改/删除权限。HTTP provider signature 只证明来源传输，不能替代 Event
proof，也不能把外部 sender 的 authority 转授给 facade。两种 admission 分支不得同时匹配。

Arkret native 客户端发送到 MIMI room 时，facade MUST 将 signed Arkret event 转换为 MIMI message，并把 MIMI provider accepted timestamp / message id 写回可验证 receipt 或 interop metadata。不得把 MIMI provider accepted timestamp 当作 Arkret event 的 creation truth；timeline 排序仍以 Arkret HLC / reducer 规则为准。

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

Arkret v1 把 Realm-level policy 映射为 Control Move 的 registered cell projections。Facade 在 MIMI room policy 与 Arkret state 之间转换时，读取 registry 中的 `cell_family`、`lattice` 与 `bottom`。

### 9.1 Cell Family 互译

| Arkret cell_family | Arkret Event kind | MIMI policy component（draft-ietf-mimi-room-policy） |
| --- | --- | --- |
| `ak.component.realm.policy.v1` | `ak.realm.policy` | （Arkret 专属；映射时合并入 `operational`） |
| `ak.component.realm.join_rule.v1` | `ak.realm.join_rule` | `participation` 中 `join_policy` 子字段（粗粒度入口枚举） |
| `ak.component.realm.history_access.v1` | `ak.realm.history_access` | MIMI 若能表达等价的 current-member history range 则映射；否则 fail closed，不臆造旧五档 visibility |
| `ak.component.realm.discovery.v1` | `ak.realm.discovery` | `participation` 中 `discoverability` 子字段 |
| `ak.component.realm.alias.v1` | `ak.realm.alias` | （Arkret 专属；MIMI 的 room URI / hub-local name 不是可映射 policy component） |
| `ak.component.realm.policy_server.v1` | `ak.realm.policy_server` | （Arkret 专属，与 MIMI hub provider 概念解耦） |
| `ak.component.realm.policy_bundle.v1` | `ak.realm.policy_bundle` | 没有独立 facet event kind 的 Realm policy 组件集合（`join_policy` / `agent_participation` / `account_deactivation` / `availability_policy` / `audit_policy` / `preauth` / 加密 floor 与 scheme 等）；对应 MIMI 的 `participation.join_policy`、`preauth` 与 `bot` 子字段 |
| `ak.component.realm.asset_privacy_policy.v1` | `ak.realm.asset_privacy_policy` | `asset` |
| `ak.component.realm.moderation_policy.v1` | `ak.realm.moderation_policy` | `logging` 的 abuse-report 子字段 + 自定义 `moderation` extension |
| `ak.component.realm.plaintext_visible_services.v1` | `ak.realm.plaintext_visible_services` | （Arkret 专属隐私透明度机制；MIMI 侧无对应） |
| `ak.component.realm.media_service.v1` | `ak.realm.media_service` | （Arkret 专属，与 MIMI 的 hub provider 解耦） |
| `ak.component.realm.schema.v1` | `ak.realm.schema` | （Arkret 专属，schema_refs 声明） |
| `ak.component.realm.inheritance_policy.v1` | `ak.realm.inheritance_policy` | （Arkret 专属，per-parent 继承） |
| `ak.component.realm.archive.v1` | `ak.realm.archive` | （部分等价于 MIMI lifecycle hint，目前 MIMI 草案未规范） |
| `ak.component.realm.freeze.v1` | `ak.realm.freeze` | 同上 |
| `ak.component.realm.tombstone.v1` | `ak.realm.tombstone` | 同上 |
| `ak.component.realm.destroy.v1` | `ak.realm.destroy` | 同上 |
| `ak.component.member.state.v1` | `ak.member.state` | MLS GroupContext 的 leaf node + roster；Arkret membership 不进入 MIMI policy components |

#### 9.1.1 Candidate-profile-only 行（base profile MUST reject）

下表中的条目**不是** v1 base profile 的 wire `Event.kind`，仅在显式声明对应 candidate profile 的 facade 上可见。**base profile 下 MIMI facade MUST reject / omit 这些条目，而不得把它们写入 shared Realm history。** 把它们与 §9.1 主表的 base-profile Event kind 分开列出，避免误读为 base profile 必须支持。

| Arkret concept/action 名称 | 所属 candidate profile | MIMI policy component | base profile 行为 |
| --- | --- | --- | --- |
| `realm.join_policy`（candidate workflow concept/action 名称，不是 v1 wire `Event.kind`；见 [`../conformance/schema-registry.md` §4.1](../conformance/schema-registry.md)） | `ak.profile.candidate.join_policy.v1` | `participation.join_policy` 子字段（结构化 gates / reviewer / TTL）；MIMI 侧未覆盖部分以 `application/vnd.arkret.component+json` 私有扩展承载 | MIMI facade **MUST reject / omit**，不得写入 shared Realm history |

> 历史的 MIMI components（`roles`、`preauth`、`bot`、`message_expiration`、`operational`）在 Arkret 中都不是独立 Event kind。它们没有统一承载：facade 接收 MIMI policy update 时 MUST 按下表逐项归约到已登记的 Arkret 承载，再按 registry 派生 cell write；无法映射的子字段按 §9.2 unknown handling 处理，MUST NOT 塞进任何 closed payload 的未登记字段。
>
> | MIMI component | Arkret 承载 |
> | --- | --- |
> | `roles` | `ak.capability.grant` / `ak.capability.revoke`（capability 是 allow 的唯一来源，不是 policy 子字段） |
> | `preauth` | `ak.realm.policy_bundle` payload 的 `preauth` 组件（[`../identity/consent-model.md` §6.1](../identity/consent-model.md)） |
> | `bot` | `ak.realm.policy_bundle` payload 的 `agent_participation` 组件（[`../models/realm-and-space.md` §2.2](../models/realm-and-space.md)） |
> | `operational` | `ak.realm.policy` facet event（`ak.component.realm.policy.v1`，见 §9.1 首行） |
>
> MIMI room policy 投影 MUST 落在有效 Realm 的 `ak.realm.policy_bundle` cell；不存在 track-scoped policy projection——track 不携带独立 access。当 MIMI room 映射的 Strand 通过 `scope_circle_id` 落在 Realm 内的 [Circle](../models/circle.md) 时，Circle-local policy 通过 Circle 自身 `policy_root` 表达，与父 Realm policy 取更严格者。

### 9.2 Unknown Handling

Arkret 的 unknown handling 来自 Lattice bottom：

| Arkret | MIMI |
| --- | --- |
| `bottom=reject` 或 unknown core lattice | `must-understand` |
| `bottom=expose` | `should-understand` / exposed conflict |
| 非授权 projection extension | `silently-drop`，但必须保留 raw bytes 或 canonical hash |

**Facade 责任**：

- 接收 MIMI policy update 时 MUST 验证目标 `cell_family` 已注册（或被部署的 profile 显式 opt-in），并归约为对应 Control Move `kind + payload`；未注册 MIMI component MUST 按其 MIMI unknown-handling 处理。
- 发送 Arkret state 到 MIMI 时 MUST 按 §9.1 表生成 MIMI component。Arkret 专属 component（无 MIMI 对应）在 facade 输出中标记为 `application/vnd.arkret.component+json` 私有扩展。

MIMI role 只能作为 interop projection。Arkret 授权仍以 capability Control Move / grant cell 为准。Facade 在接收 MIMI role/policy update 时 MUST 归约为具体 capability event（如 `ak.capability.grant` / `ak.capability.revoke` / `ak.capability.relinquish`）或具体 `ak.realm.<facet>` Control Move effect，并经过 Arkret Control Move refs 授权验证后才能生效。

**未知字段安全惰性（normative）**：interop schema 为前向兼容演进中的 IETF MIMI Internet-Draft，有意在 top-level 与 `mimi` / `binding_scope` / `payload` 子树保留开放 `additionalProperties`。接收方 MUST 把该 surface 上任何未识别字段视为**安全惰性**：MUST 忽略其参与任何安全判定，且 MUST NOT 让它影响 authorization、identity binding、`policy_root`、MLS epoch / group state、routing / hub-follower 关系或任何 signature / digest transcript。已知字段仍以 schema pin 的定义为准；未识别字段只能作为不可信的 draft passthrough 保留（如需保留 raw bytes / canonical hash 见 §9.2 表）。实现 MUST NOT 依据未识别字段提升 provider role、改写 `policy_root` 或放宽 governance binding 校验。

## 10. Identifiers And Consent

MIMI identifier MUST NOT 被直接作为 Arkret actor。映射规则：

- MIMI provider identifier 映射到 service DID。
- MIMI user identifier 映射到 principal DID、pairwise DID 或 pending invite proof。MIMI user → 既有 principal DID 的绑定 MUST 有目标侧 consent proof（如 `ak.consent.grant`、accepted invite proof）或该 principal holder 的显式 claim；facade MUST NOT 仅凭来源 MIMI provider 的断言或 connection identifier 相似性把入站 MIMI user 映射到既有 principal DID。缺少目标侧 consent proof 或 holder claim 时，facade MUST 将该 MIMI user 视为新的 pairwise DID / pending invite proof，而不得冒充既有 principal。
- connection identifier 仅用于 discovery / consent，不进入 Realm history，除非 holder 明确作为 handle / claim 披露。
- display name 只用于 UI，不参与授权。

`ak.open.mimi.read.identifiers.v1` SHOULD 调用 `ak.private_contact_discovery.v1`，按 [`discovery/discovery-directory.md` §6](../discovery/discovery-directory.md) 的 PSI 流程返回 set-membership 命中位图与 invite handoff stub；MUST NOT 返回任何形式的 "reachability proof"——该机制在 v1 已被移除（见 `discovery-directory.md` §6 的 PSI-only 边界），facade 实现 MUST NOT 复活它。`ak.open.mimi.command.request_consent.v1` / `ak.open.mimi.command.update_consent.v1` MUST 映射为 Arkret 的 holder-private consent state（`ak.consent.grant` / `ak.consent.revoke`，详见 [`identity/consent-model.md`](../identity/consent-model.md)）。Consent 不授予 Realm read/write 权限；加入和发消息仍需 membership、capability 和 policy checks。Facade 在两侧 round-trip 时 MUST 保留 `consent_id` 作为 inter-protocol correlation。

`request_consent` 返回 `consent_id` 前 MUST 持久保存仅服务本地可见的 correlation：`(consent_id, requester_id, target, purpose, strand_id?, authenticated source service/session class, created_at, expires_at?)`。该记录不是 Event、cell、授权或可对外查询的 pending consent state。`update_consent` 必须在验证 transport 与 actor proof 后，将 actor、来源、Event 解析得到的 holder/peer/scope 与该 correlation 逐字对账；`target.kind != did` 只有在目标侧 claim/identifier binding 已解析到同一 holder 时才可继续，否则 fail closed。未知、过期、属于其它来源/holder 或调用方不可见的 correlation，以及 revoke/deny 找不到匹配 active observed dots，统一返回相同的 `not_found` 失败形态与披露等级，不得说明记录是否存在、目标是谁或 holder 是否已有 consent cell。

`update_consent` **MUST** 携带完整 `consent_event: EventInitialSubmission`：`decision=accept` 对应 `event.kind=ak.consent.grant`，`decision=deny|revoke` 对应 `event.kind=ak.consent.revoke`。`event.actor_id` 必须等于请求 `actor_id` 与私有 correlation 的 holder，且 Event actor 与认证 holder 必须是该 holder Principal Control Realm 当前 authority-root controller；grant payload 的 `consent_id`、peer 与 scope 必须等于 facade 私有 correlation，revoke payload 的 `consent_id` 与 active `observed_dots` 必须解析到该 correlation 的同一 holder/peer/scope cell。facade 同时验证覆盖完整 unsigned body 的 detached operation signature；`authorization_ref` 必须绑定当前 authority-root 授权。`ak.consent.grant` / `ak.consent.revoke` 是 `root_control_only` action，不支持由不同主体独立 managed-behalf，也不接受 `consent_write` 委派；普通 PCR write、co-owner grant、controller / agent automation 或 payload approval evidence 均不能替代。facade 只能把 exact submission 交给 ordinary Event admission，**MUST NOT** 代签、重建或合成 Event。deny/revoke 没有可枚举的 active observed dots 时必须用不泄露 holder 状态的拒绝结束，不能写“成功但无 Event”的本地状态。成功响应必须返回 `status=accepted` 与唯一 `event_ref`；相同 Event ID 的逐字节重放返回同一结果。

## 11. Abuse Report And Proxy Download

`ak.open.mimi.command.report_abuse.v1` MUST 映射到一条 `ak.self.moderation.report` **Event**，由 facade 以自己的 service DID 作者身份提交到普通 Event admission（`service_attested` variant，见下方「归属与 admission 的分离」）。它 **MUST NOT** 走 `ak.self.moderation.command.report.v1` operation：该 self endpoint 只接受 reporter 本人设备直接签名，并显式禁止 MIMI facade provenance（[`../governance/content-moderation.md` §3.1](../governance/content-moderation.md)），按它走必被拒。E2EE report SHOULD 携带 message franking proof、encrypted evidence package、reporter signature、MIMI room id、provider id 和 target event hash。Facade MUST NOT 要求 reporter 向普通 provider 上传未加密明文；只有被 Realm policy 授权的 moderation recipient 可以解密 evidence。

入站 MIMI report 的 `reporter` MUST 按 [§10 Identifiers And Consent](#10-identifiers-and-consent) 的 consent / holder-claim 规则解析到 Arkret principal,facade MUST NOT 仅凭来源 provider 的断言把 report 归因到既有 principal(防止以他人名义举报)。映射前 facade 还 MUST 校验该 reporter 对 `target_ref` 在对应 Realm / scope 内可见(对齐 [`../governance/content-moderation.md` §3.1/§3.3](../governance/content-moderation.md)),并把 [`../governance/content-moderation.md` §3.1.1](../governance/content-moderation.md) 的 per-reporter 限速至少按 (映射后 reporter principal DID, 来源 provider service DID) 双维度施加；不满足按 pairwise / pending 处理或拒绝。

**归属与 admission 的分离（normative）**：facade 不持有映射后 principal 的任何签名密钥，
MUST NOT 以该 principal 作为 envelope `actor_id` 代签 report。`ak.self.moderation.report`
的 admission 是 conditional（contract-registry `admission_variants`）：

- reporter 自己的设备发出的 report 走 `self_authored_proof`，reducer 验证
  `actor == payload.reporter`；payload 不携带 `provenance` 或取 `"self"`；
- facade 映射的入站 MIMI report 设 `payload.provenance="mimi_facade"`，走
  `service_attested`：envelope `actor_id` 是 facade 的 service DID，
  `payload.reporter` 是按本节规则解析出的 Arkret principal，
  `payload.source_provider` 必填并携带来源 provider 的 service DID；reducer MUST 验证
  actor service 确实为 `payload.realm_id` 运营 MIMI facade。归属（attribution）由
  `payload.reporter` 承载，作者（authorship）由 envelope actor 承载，两者不得混同。

`ak.open.mimi.command.proxy_download.v1` MUST 遵守 `ak.realm.asset_privacy_policy`。当 policy 要求 `provider_proxy` 或 `ohttp_relay` 时，facade 不得返回 direct object-store URL。下载成功不证明内容可信，客户端仍 MUST 验证 content hash、ciphertext digest 和 attachment metadata。

**被代理 URL 的出站网络目标策略（normative，SSRF 防护）**：`proxy_download` 是 facade 代外部资产做 server-side fetch 的高危面。facade 在抓取被代理资产 URL（含 redirect / Alt-Svc 后实际目标）前 MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝代理，不得向内部地址发起请求。被代理 URL 来自对端 provider，恶意 / 被攻陷 provider 可借此诱导 facade SSRF，故该校验 MUST 不可绕过。

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
- proxy download 遵守 asset privacy policy。
- unsupported draft version fail closed。

## 13. 设计决定

Arkret v1 的 MIMI 支持固定为 facade profile：

- 不把 MIMI hub 变成 Arkret 的唯一 truth source。
- 不用 MIMI room id 替代 `realm_id`。
- 不用 MIMI user identifier 替代 DID。
- 不绕过 Arkret capability Control Move refs / Policy Server。
- 不把 MIMI provider accepted timestamp 替代 Arkret HLC / event hash。
- 支持 MIMI 草案版本 pinning，并允许未来 profile 处理草案变化。
