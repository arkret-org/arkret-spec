---
title: MIMI Interoperability
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

> **状态：interop extension profile（非 v1 core 互操作必需）**。本文档描述的 MIMI Provider Facade 跟踪的
> 是仍在演进的 IETF MIMI Internet-Draft。Cokret v1 core 互操作 **不要求** 实现 MIMI
> facade；声称 `ck.profile.principal_server.v1` 或 `ck.profile.full_client.v1` 的实现
> 可以完全不实现本 profile。当 MIMI 升级为 RFC 后，将以新的 `ck.profile.mimi_interop_<rfc>.v1`
> 引入稳定 profile；当前 `ck.profile.mimi_interop.v1` 视为实验性 interop extension profile。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Cokret 对 MIMI 的互操作 profile。目标不是把 Cokret core 改成 room-first 协议，而是在 Cokret 的 Realm / Event / DID / capability 模型外提供一个可测试的 **MIMI Provider Facade**，让支持 MLS 的 Cokret Realm 或 Strand discussion track 可以与 MIMI provider 互通。

`ck.profile.mimi_interop.v1` 固定参考以下草案版本：

- `draft-ietf-mimi-protocol-06`
- `draft-ietf-mimi-content-08`
- `draft-ietf-mimi-room-policy-03`
- `draft-kohbrok-mimi-identifiers-01`

这些草案仍是 Internet-Draft。实现 MUST 在 `server/describe` 和 MIMI provider directory 中声明实际支持的 draft version。草案更新导致 wire 语义变化时，Cokret MUST 通过新的 interop profile 版本处理，不得改变 v1 核心状态语义。

## 2. 角色

| MIMI 角色 | Cokret 映射 |
| --- | --- |
| Provider | `mimi_provider_facade` service DID，通常由 Principal Server、notary service 或受托 bridge 暴露。 |
| Hub provider | 对外拥有 MIMI room URI 的 provider service；在 Cokret 侧通常映射为 Principal Server 或 notary service，负责 MIMI room fanout 和 groupInfo。 |
| Follower provider | 参与 MIMI room 的远端 provider；在 Cokret 中表现为 federation peer 或 Applet bridge peer。 |
| User / client | Cokret principal DID + device id，可按 Realm policy 使用 pairwise DID 或 room-scoped pseudonym。 |
| Room | Cokret Strand discussion track 的 MIMI room 投影，可附带所在 Realm 的最小上下文。 |

MIMI facade 不是新的真相源。Cokret native 侧的 canonical truth 是 signed DataEvent、Control Move、Seal coverage、Lattice cell state、capability refs 与 MLS Governance Binding（`governance_binding` + `covered_seals_cell`）。MIMI room state 是对这些状态的互操作投影。

## 3. Provider Discovery

支持 MIMI 的服务 MUST 在 DID Document service entry 和 `GET /_cokret/describe` 中声明：

```json
{
  "service_type": "mimi_provider_facade",
  "supported_profiles": ["ck.profile.mimi_interop.v1"],
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
GET /_cokret/open/mimi/provider-directory
```

目录响应 MUST 绑定 service DID、provider id、base URL、支持草案版本、endpoint 列表、MLS cipher suites、内容 profile、room policy components 和签名 proof。客户端和远端 provider MUST 验证 service DID、HTTP Message Signature、TLS endpoint、DID service endpoint 和 Realm policy 委托一致。

**出站网络目标策略（normative，SSRF 防护）**：facade 在向对端 provider 声明的 `base_url`（及其派生 endpoint）发起任何 server-side 请求前，MUST 对该 URL（含 redirect 后实际目标）执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝，`base_url` scheme MUST 限 `https`。签名 proof 只证明"是这个 provider"，不证明"网络目标合法"。

## 4. Room Binding

允许被导出为 MIMI room 的 Cokret 对象 MUST 有写入 `ck.component.mimi.room_binding.v1` cell 的 Control Move effect。对应 Event kind 为 `ck.mimi.room_binding`；cell subject 是 `payload.mimi_room_uri`。

`ck.mimi.room_binding` 的完整 payload 形态（含 `hub_provider`、`follower_providers`、`content_profile`、`policy_root`、`local_provider_role` 等全部字段）以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威机读真源；下文逐字段说明不替代该 schema。

```json
{
  "kind": "ck.mimi.room_binding",
  "payload": {
    "profile": "ck.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
      "strand_id": "ck:strand:01964137-0000-7000-8000-000000000000"
    },
    "hub_provider": "did:web:mimi.example.com",
    "local_provider_role": "hub",
    "follower_providers": [
      "did:web:remote.example"
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
- `hub_provider` MUST 是 Realm policy、Organization DID 或 member DID 明确委托的 service DID。
- `local_provider_role` 取值为 `hub`、`follower` 或 `observer`（封闭枚举，以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。各值语义:
  - `hub`:本地 facade 即拥有该 MIMI room URI 的 hub provider,负责 room fanout 与 groupInfo,对外承担 room 真相投影责任;
  - `follower`:本地 facade 作为 follower provider 参与远端 hub 拥有的 room,接收 fanout 并向 hub 提交本地 writes;
  - `observer`:本地 facade 只读投影该 room（监听 fanout / groupInfo 用于本地呈现或审计），MUST NOT 代表本地参与方向 MIMI room 提交 writes 或承担 hub fanout 职责。
- `ck.mimi.room_binding` 的创建、更新和撤销 MUST require `ck.policy.manage`、`ck.realm.admin` 或等价 interop capability。
- E2EE MIMI room MUST 绑定 `mls_group_id`，并按 [`../crypto-media/encryption-and-audit.md` §2.5](../crypto-media/encryption-and-audit.md)（MLS Governance Binding）的 `covered_seals_cell` precondition 校验 membership、policy 和 capability。
- MIMI facade 在无法解析或验证 Cokret MLS Governance Binding 时 MUST fail closed：入站 MIMI room state、groupInfo、key material 或 message 不得直接投影到 Cokret Realm，而是进入 quarantine，reason=`mimi_governance_binding_missing` 或更具体的 binding mismatch 错误。
- 撤销 binding 后，facade MUST 停止接受新的 MIMI writes，只允许 backfill、tombstone、report、legal hold 或 migration proof 等维护操作。`status` 的完整生命周期状态机（初始状态、合法迁移、终态、非法迁移拒绝、`migrating` 窗口与并发收敛）见 §4.2。

**E2EE MIMI 互操作下界（normative）**：凡 MIMI room binding 携带 `mls_group_id`、groupInfo、key material 或加密 application message，并要投影到 Cokret Realm / Strand，facade MUST 把 Cokret `ck.profile.mls_governance_binding.full.v1` 当作最低 E2EE 互操作能力，而不是把 MIMI provider 的 room state 当成等价治理真相。具体要求：

- `ck.mimi.room_binding.mls_group_id`、MIMI groupInfo 中的 group id、Cokret `governance_binding.mls_group_id` 必须一致；
- `governance_binding.binding_profile` 与 `governance_binding.reducer_profile` 必须存在且被本 facade 支持；未知或缺失时不得用 MIMI draft 字段、provider 目录或本地配置补齐；
- `covered_seals_cell` 必须覆盖要投影消息依赖的 Cokret governance frontier；
- MIMI 未知字段仍按 §9.2 安全惰性处理，不得提升 provider role、放宽 `policy_root` 或改变 MLS epoch / group state 判定。

`ck.profile.e2ee_relaxed.v1` 不得被 facade 对外表述为等价 full MLS Governance Binding。若本地 Realm 是 relaxed 降级，facade 只有在双方都显式声明 Cokret relaxed 语义、且满足 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.4.1 的 federation guard 时，才可投影 relaxed 窗口内的消息；否则 MUST reject / quarantine，reason 使用 `mimi_room_state_incompatible`、`mimi_governance_binding_missing` 或 `mimi_governance_binding_mismatch`。

### 4.1 Fail-Closed Reason Taxonomy

MIMI facade 对 Cokret Realm 的入站投影失败时，MUST 使用稳定 reason code，避免不同 provider 把 fail-closed 结果折叠成不可测试的通用错误：

| reason_code | 触发条件 | 外部行为 |
| --- | --- | --- |
| `mimi_governance_binding_missing` | 找不到可验证的 Cokret MLS Governance Binding。 | quarantine 或 reject，不投影到 Realm。 |
| `mimi_governance_binding_mismatch` | binding 存在但 `realm_id` / `strand_id` / `mls_group_id` / provider DID 与当前 MIMI room state 不一致。 | quarantine；需要人工或 backfill 复核。 |
| `mimi_policy_root_mismatch` | MIMI policy component 与 Cokret `policy_root` / `ck.realm.policy_components` 不一致。 | reject 当前 update，等待 fresh policy projection。 |
| `mimi_room_state_incompatible` | MIMI room state 使用当前 profile 不支持的 lifecycle、membership、policy 形态，或试图把未被双方显式声明支持的 `ck.profile.e2ee_relaxed.v1` 降级当作 full MLS Governance Binding 投影。 | reject 或要求使用新 interop profile。 |
| `mimi_provider_unreachable` | provider directory、key material 或 groupInfo 依赖暂时不可达。 | `temporarily_unavailable` + bounded retry；不得接受无 binding 的 fallback。 |
| `mimi_draft_unsupported` | 对端声明的 MIMI draft version 不在本 profile 支持集合。 | reject；不得按相近草案猜测解析。 |

### 4.2 `status` 生命周期状态机（normative）

`payload.status` 是 binding 的生命周期判定字段，取值为封闭枚举 `proposed`、`accepted`、`revoked`、`migrating`（以 [`../../artifacts/schemas/mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json) 为权威源）。状态迁移规则：

- **初始状态**：对某个 `mimi_room_uri` 的首个被接受的 `ck.mimi.room_binding` Control Move MUST 把 `status` 设为 `proposed`（跨 provider 协商中，等待对端确认）或 `accepted`（本地 facade 即 hub 且无需对端确认时可直接激活）。以 `revoked` 或 `migrating` 作为初始状态的写入 MUST 被拒绝。
- **迁移表**：

  | 当前状态 | 允许出边 | 触发条件 |
  | --- | --- | --- |
  | `proposed` | `accepted` | 协商完成：对端 provider 确认，或本地 hub 接受。 |
  | `proposed` | `revoked` | 协商被拒绝、超时或发起方撤回。 |
  | `accepted` | `migrating` | hub 迁移 / provider 拓扑替换开始。 |
  | `accepted` | `revoked` | 持有 §4 要求 capability 的管理操作撤销 binding。 |
  | `migrating` | `accepted` | migration proof 验证通过：迁移完成（新拓扑生效）或回滚（恢复原拓扑）。 |
  | `migrating` | `revoked` | 迁移失败且不回滚，或管理操作撤销。 |

- **终态**：`revoked` 是唯一终态；对 `revoked` binding 的任何 `status` 变更 MUST 被拒绝。同一对象若需重新导出为 MIMI room，MUST 以新的 `mimi_room_uri` 建立新 binding 并重新通过 §4 的 capability 校验，不得复活已撤销 binding。
- **非法迁移**：不在上表中的迁移（含初始状态违例与 `revoked` 后写入）MUST 被 reducer 以 `mimi_room_binding_status_transition_invalid` 拒绝。
- **`migrating` 窗口语义**：进入 `migrating` 后，facade 对该 binding MUST 停止接受新的 MIMI writes 投影，仅允许 backfill、tombstone、report、legal hold 与 migration 所需的 groupInfo / state 转移及 migration proof 提交；`migrating -> accepted` 的 Control Move MUST 引用已验证的 migration proof，hub / follower 拓扑变更只能随该迁移落地。
- **可写性判定**：仅 `accepted` 状态接受新的 MIMI writes 投影。`proposed` 状态下 facade MUST NOT 把 MIMI room state 投影到 Realm（目录 / 协商类流量除外）；`revoked` 后行为见 §4 撤销规则。
- **并发收敛**：`ck.mimi.room_binding` 是写入 `ck.component.mimi.room_binding.v1` cell 的 Control Move，并发更新由控制面 Seal 串行化仲裁，不存在数据面并发合并；后到的冲突 Move 在其 seal basis 下按本状态机重新校验，非法即拒绝。

## 5. Endpoint Surface

MIMI facade 至少定义以下 canonical operation：

| operation_id | HTTP binding | 语义 |
| --- | --- | --- |
| `ck.open.mimi.query.provider_directory` | `GET /_cokret/open/mimi/provider-directory` | 返回 MIMI provider feature profile。 |
| `ck.open.mimi.exchange.request_key_material` | `POST /_cokret/open/mimi/key-material` | 领取 MLS KeyPackage，映射到 Cokret KeyPackage claim lifecycle。 |
| `ck.open.mimi.command.update_room` | `POST /_cokret/open/mimi/strands/{strand_id}/update` | 提交或转发 room state / MLS update。 |
| `ck.open.mimi.command.notify` | `POST /_cokret/open/mimi/strands/{strand_id}/notify` | provider 间投递通知、fanout 或 delivery event。 |
| `ck.open.mimi.command.submit_message` | `POST /_cokret/open/mimi/strands/{strand_id}/messages` | 提交 MIMI encrypted application message。 |
| `ck.open.mimi.query.group_info` | `GET /_cokret/open/mimi/strands/{strand_id}/group-info` | 获取 MLS groupInfo / room projection。 |
| `ck.open.mimi.command.request_consent` | `POST /_cokret/open/mimi/consent/request` | 请求建立跨 provider 联系或 room invite consent。 |
| `ck.open.mimi.command.update_consent` | `POST /_cokret/open/mimi/consent/update` | 更新 consent state。 |
| `ck.open.mimi.query.identifiers` | `POST /_cokret/open/mimi/identifiers/query` | 查询 connection identifier / MIMI URI 的可达性。 |
| `ck.open.mimi.command.report_abuse` | `POST /_cokret/open/mimi/report-abuse` | 提交跨 provider abuse report，支持 E2EE franking proof。 |
| `ck.open.mimi.command.proxy_download` | `POST /_cokret/open/mimi/proxy-download` | 代理或 oblivious 下载资产。 |

所有写入型 endpoint MUST 使用 HTTP Message Signatures 或等价 service proof，并绑定：

- source service DID
- destination service DID
- provider id
- MIMI room URI 或 target identifier
- request canonical hash
- created / expires
- body digest

Facade 接收请求后 MUST 先验证 MIMI envelope，再映射为 Cokret DataEvent、Control Move 或 to-device message。MIMI 传输签名只证明 provider 来源，不替代 Actor DID / device 签名、MLS transcript、capability 或 Realm policy。

## 6. Key Material

`ck.open.mimi.exchange.request_key_material` MUST 使用 [`../crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) 的 KeyPackage claim API。请求必须包含：

- target MIMI identifier 或 DID / pairwise DID。
- intended MIMI room URI 和 Cokret `realm_id`。
- required content profile、MLS capabilities 和 cipher suites。
- requester provider DID 和 proof。
- 是否允许 minimal-metadata pseudonymous credential。

响应 MUST 返回 claimed KeyPackage、`claim_id`、`keypackage_ref`、device binding、expiry 和 supported capabilities。KeyPackage 被 Welcome 成功使用后 MUST 进入 `consumed`。不可见用户、无可用设备、policy denied 和不存在目标 SHOULD 使用统一失败形态，避免枚举。

## 7. Message Submission

`ck.open.mimi.command.submit_message` 接收 MIMI encrypted application message 后，facade MUST：

1. 验证 provider signature、room binding、destination、body digest 和重放窗口。同时 MUST 校验本 binding 的 `local_provider_role ∈ { hub, follower }`;`local_provider_role=observer` 的 binding 不得代表本地参与方提交 writes(见 §4),facade MUST 拒绝该 submit_message,reason=`mimi_observer_write_forbidden`。
2. 验证 MLS epoch 与 `ck.mimi.room_binding.mls_group_id` 匹配。
3. 按 MLS Governance Binding 验证：commit 携带的 `governance_binding` 解析到的 Cokret Seal view 与 state_root，且 `covered_seals_cell` 覆盖该消息所需 governance frontier。
4. 将 MIMI content container 映射为 `ck.message.create`、`ck.message.revise`、`ck.message.redact`、`ck.reaction.add`、`ck.reaction.remove` 或 `ck.relation.*`。
5. 保留原始 MIMI envelope hash、provider id、message id 和 accepted timestamp 作为 interop metadata。
6. 对无法确认授权、epoch、content 或 policy 的消息返回 `temporarily_unavailable`、`dependency_missing`、`capability_denied` 或 `quarantine`。

Cokret native 客户端发送到 MIMI room 时，facade MUST 将 signed Cokret event 转换为 MIMI message，并把 MIMI provider accepted timestamp / message id 写回可验证 receipt 或 interop metadata。不得把 MIMI provider accepted timestamp 当作 Cokret event 的 creation truth；timeline 排序仍以 Cokret HLC / reducer 规则为准。

## 8. Content Mapping

MIMI facade MUST 支持接收：

- `application/mimi-content`
- `text/plain;charset=utf-8`
- `text/markdown;variant=GFM-MIMI`

推荐映射：

| Cokret | MIMI |
| --- | --- |
| `ck.content.text` plain | `text/plain;charset=utf-8` body part |
| `ck.content.text` markdown | `text/markdown;variant=GFM-MIMI` body part |
| `ck.content.composite` | MIMI multipart / multiple body parts |
| `reply_context` + `replies_to` Relation | MIMI reply behavior field |
| `ck.reaction.add/remove` | MIMI reaction / unlike behavior |
| `ck.message.revise` | MIMI edit behavior |
| `ck.message.redact` | MIMI delete behavior |
| `message_expiration` policy | MIMI expiring message field |
| attachment `blob_ref` | MIMI external content / asset reference |
| Room thread / Message relation | MIMI topic / threading field |

规则：

- 发送到 MIMI 时，facade SHOULD 生成 MIMI required / recommended media type，同时 MAY 附带 `application/vnd.cokret.content+json` proprietary alternative 以保留无损 Cokret 内容。
- 从 MIMI 接收未知 extension field 时，facade MUST 保留原始 CBOR bytes 或 canonical hash，至少保证未来支持时可回放或审计。
- 任何正文 fallback 进入 E2EE Realm 时必须仍在密文中；不得为了 MIMI 预览把 `body` 明文复制到 routing metadata。
- Link preview、attachment thumbnail 和 asset metadata MUST 遵守 `asset_privacy_policy` 与 `plaintext_visible_services`。

### 8.1 Content Mapping Receipt

facade 在 Cokret ↔ MIMI 之间转换一条内容时，SHOULD 生成 **Content Mapping Receipt**（`content_mapping_receipt`，`kind="ck.mimi.mapping_receipt"`，schema `ck.schema.mimi_interop.v1`，见 [`mimi-interop.schema.json`](../../artifacts/schemas/mimi-interop.schema.json)），作为该次格式映射的可审计证据。它记录 `mimi_room_uri`、`source_format` → `target_format`、被映射源信封摘要 `original_envelope_digest` 与目标 `mapped_operation_id`（可选携带 `mimi_message_id` / `cokret_event_id` / `accepted_at`），使双向投递的内容转换可被追溯与对账。该回执是 EXTENSION 范围对象，不进入 v1 core 互操作必需集。

Cokret v1 把 Realm-level policy 映射为 Control Move effects on cell families。Facade 在 MIMI room policy 与 Cokret state 之间转换时，读取 registry 中的 `cell_family`、`lattice` 与 `bottom`。

### 9.1 Cell Family 互译

| Cokret cell_family | Cokret effect kind | MIMI policy component（draft-ietf-mimi-room-policy） |
| --- | --- | --- |
| `ck.component.realm.policy.v1` | `ck.realm.policy` | （Cokret 专属；映射时合并入 `operational`） |
| `ck.component.realm.join_rule.v1` | `ck.realm.join_rule` | `participation` 中 `join_policy` 子字段（粗粒度入口枚举） |
| `ck.component.realm.history_visibility.v1` | `ck.realm.history_visibility` | `history_sharing` 的 visibility 子字段 |
| `ck.component.realm.discovery.v1` | `ck.realm.discovery` | `participation` 中 `discoverability` 子字段 |
| `ck.component.realm.policy_server.v1` | `ck.realm.policy_server` | （Cokret 专属，与 MIMI hub provider 概念解耦） |
| `ck.component.realm.policy_components.v1` | `ck.realm.policy_components` | MIMI policy component 集合声明（root + active list） |
| `ck.component.realm.history_sharing_policy.v1` | `ck.realm.history_sharing_policy` | `history_sharing` |
| `ck.component.realm.asset_privacy_policy.v1` | `ck.realm.asset_privacy_policy` | `asset` |
| `ck.component.realm.moderation_policy.v1` | `ck.realm.moderation_policy` | `logging` 的 abuse-report 子字段 + 自定义 `moderation` extension |
| `ck.component.realm.plaintext_visible_services.v1` | `ck.realm.plaintext_visible_services` | （Cokret 专属隐私透明度机制；MIMI 侧无对应） |
| `ck.component.realm.media_service.v1` | `ck.realm.media_service` | （Cokret 专属，与 MIMI 的 hub provider 解耦） |
| `ck.component.realm.schema.v1` | `ck.realm.schema` | （Cokret 专属，schema_refs 声明） |
| `ck.component.realm.inheritance_policy.v1` | `ck.realm.inheritance_policy` | （Cokret 专属，per-parent 继承） |
| `ck.component.realm.archive.v1` | `ck.realm.archive` | （部分等价于 MIMI lifecycle hint，目前 MIMI 草案未规范） |
| `ck.component.realm.freeze.v1` | `ck.realm.freeze` | 同上 |
| `ck.component.realm.tombstone.v1` | `ck.realm.tombstone` | 同上 |
| `ck.component.realm.destroy.v1` | `ck.realm.destroy` | 同上 |
| `ck.component.member.state.v1` | `ck.member.state` | MLS GroupContext 的 leaf node + roster；Cokret membership 不进入 MIMI policy components |

#### 9.1.1 Candidate-profile-only 行（base profile MUST reject）

下表中的条目**不是** v1 base profile 的 wire `Event.kind`，仅在显式声明对应 candidate profile 的 facade 上可见。**base profile 下 MIMI facade MUST reject / omit 这些条目，而不得把它们写入 shared Realm history。** 把它们与 §9.1 主表的 base-profile wire effect kind 分开列出，避免误读为 base profile 必须支持。

| Cokret concept/action 名称 | 所属 candidate profile | MIMI policy component | base profile 行为 |
| --- | --- | --- | --- |
| `realm.join_policy`（candidate workflow concept/action 名称，不是 v1 wire `Event.kind`；见 [`../conformance/schema-registry.md` §4.1](../conformance/schema-registry.md)） | `ck.profile.candidate.join_policy.v1` | `participation.join_policy` 子字段（结构化 gates / reviewer / TTL）；MIMI 侧未覆盖部分以 `application/vnd.cokret.component+json` 私有扩展承载 | MIMI facade **MUST reject / omit**，不得写入 shared Realm history |

> 历史的 MIMI components（`roles`、`preauth`、`bot`、`message_expiration`、`operational`）在 Cokret 中是 `ck.realm.policy_components` cell 的子字段，而不是独立 kind。Facade 接收 MIMI policy update 时 MUST 把这些 components 归约为 `ck.realm.policy_components` Control Move effect。
>
> MIMI room policy 投影 MUST 落在有效 Realm 的 `ck.realm.policy_components` cell；不存在 track-scoped policy projection——track 不携带独立 access。当 MIMI room 映射的 Strand 通过 `scope_circle_id` 落在 Realm 内的 [Circle](../models/circle.md) 时，Circle-local policy 通过 Circle 自身 `policy_root` 表达，与父 Realm policy 取更严格者。

### 9.2 Unknown Handling

Cokret 的 unknown handling 来自 Lattice bottom：

| Cokret | MIMI |
| --- | --- |
| `bottom=reject` 或 unknown core lattice | `must-understand` |
| `bottom=expose` | `should-understand` / exposed conflict |
| 非授权 projection extension | `silently-drop`，但必须保留 raw bytes 或 canonical hash |

**Facade 责任**：

- 接收 MIMI policy update 时 MUST 验证目标 `cell_family` 已注册（或被部署的 profile 显式 opt-in），并归约为对应 Control Move effect；未注册 MIMI component MUST 按其 MIMI unknown-handling 处理。
- 发送 Cokret state 到 MIMI 时 MUST 按 §9.1 表生成 MIMI component。Cokret 专属 component（无 MIMI 对应）在 facade 输出中标记为 `application/vnd.cokret.component+json` 私有扩展。

MIMI role 只能作为 interop projection。Cokret 授权仍以 capability Control Move / grant cell 为准。Facade 在接收 MIMI role/policy update 时 MUST 归约为具体 capability event（如 `ck.capability.grant` / `ck.capability.delegate` / `ck.capability.revoke`）或具体 `ck.realm.<facet>` Control Move effect，并经过 Cokret Control Move refs 授权验证后才能生效。

**未知字段安全惰性（normative）**：interop schema 为前向兼容演进中的 IETF MIMI Internet-Draft，有意在 top-level 与 `mimi` / `binding_scope` / `payload` 子树保留开放 `additionalProperties`。接收方 MUST 把该 surface 上任何未识别字段视为**安全惰性**：MUST 忽略其参与任何安全判定，且 MUST NOT 让它影响 authorization、identity binding、`policy_root`、MLS epoch / group state、routing / hub-follower 关系或任何 signature / digest transcript。已知字段仍以 schema pin 的定义为准；未识别字段只能作为不可信的 draft passthrough 保留（如需保留 raw bytes / canonical hash 见 §9.2 表）。实现 MUST NOT 依据未识别字段提升 provider role、改写 `policy_root` 或放宽 governance binding 校验。

## 10. Identifiers And Consent

MIMI identifier MUST NOT 被直接作为 Cokret actor。映射规则：

- MIMI provider identifier 映射到 service DID。
- MIMI user identifier 映射到 principal DID、pairwise DID 或 pending invite proof。MIMI user → 既有 principal DID 的绑定 MUST 有目标侧 consent proof（如 `ck.consent.grant`、accepted invite proof）或该 principal holder 的显式 claim；facade MUST NOT 仅凭来源 MIMI provider 的断言或 connection identifier 相似性把入站 MIMI user 映射到既有 principal DID。缺少目标侧 consent proof 或 holder claim 时，facade MUST 将该 MIMI user 视为新的 pairwise DID / pending invite proof，而不得冒充既有 principal。
- connection identifier 仅用于 discovery / consent，不进入 Realm history，除非 holder 明确作为 handle / claim 披露。
- display name 只用于 UI，不参与授权。

`ck.open.mimi.query.identifiers` SHOULD 调用 `ck.private_contact_discovery.v1`，按 [`discovery/discovery-directory.md` §6](../discovery/discovery-directory.md) 的 PSI 流程返回 set-membership 命中位图与 invite handoff stub；MUST NOT 返回任何形式的 "reachability proof"——该机制在 v1 已被移除（见 `discovery-directory.md` §6 的 PSI-only 边界），facade 实现 MUST NOT 复活它。`ck.open.mimi.command.request_consent` / `ck.open.mimi.command.update_consent` MUST 映射为 Cokret 的 holder-private consent state（`ck.consent.grant` / `ck.consent.revoke`，详见 [`identity/consent-model.md`](../identity/consent-model.md)）。Consent 不授予 Realm read/write 权限；加入和发消息仍需 membership、capability 和 policy checks。Facade 在两侧 round-trip 时 MUST 保留 `consent_id` 作为 inter-protocol correlation。

## 11. Abuse Report And Proxy Download

`ck.open.mimi.command.report_abuse` MUST 映射到 `ck.self.moderation.command.report`。E2EE report SHOULD 携带 message franking proof、encrypted evidence package、reporter signature、MIMI room id、provider id 和 target event hash。Facade MUST NOT 要求 reporter 向普通 provider 上传未加密明文；只有被 Realm policy 授权的 moderation recipient 可以解密 evidence。

入站 MIMI report 的 `reporter` MUST 按 [§10 Identifiers And Consent](#10-identifiers-and-consent) 的 consent / holder-claim 规则解析到 Cokret principal,facade MUST NOT 仅凭来源 provider 的断言把 report 归因到既有 principal(防止以他人名义举报)。映射前 facade 还 MUST 校验该 reporter 对 `target_ref` 在对应 Realm / scope 内可见(对齐 [`../governance/content-moderation.md` §3.1/§3.3](../governance/content-moderation.md)),并把 [`../governance/content-moderation.md` §3.1.1](../governance/content-moderation.md) 的 per-reporter 限速至少按 (映射后 reporter principal DID, 来源 provider service DID) 双维度施加；不满足按 pairwise / pending 处理或拒绝。

`ck.open.mimi.command.proxy_download` MUST 遵守 `ck.realm.asset_privacy_policy`。当 policy 要求 `provider_proxy` 或 `ohttp_relay` 时，facade 不得返回 direct object-store URL。下载成功不证明内容可信，客户端仍 MUST 验证 content hash、ciphertext digest 和 attachment metadata。

**被代理 URL 的出站网络目标策略（normative，SSRF 防护）**：`proxy_download` 是 facade 代外部资产做 server-side fetch 的高危面。facade 在抓取被代理资产 URL（含 redirect / Alt-Svc 后实际目标）前 MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝代理，不得向内部地址发起请求。被代理 URL 来自对端 provider，恶意 / 被攻陷 provider 可借此诱导 facade SSRF，故该校验 MUST 不可绕过。

## 12. Conformance

`ck.profile.mimi_interop.v1` MUST 测试：

- provider directory draft pinning 与 service DID 签名。
- `ck.mimi.room_binding` 创建、更新、撤销和 policy root 校验。
- KeyPackage single-use claim / Welcome consume。
- Cokret message 到 MIMI content roundtrip。
- MIMI text / markdown / reply / reaction / edit / delete / attachment 接收映射。
- MIMI policy update 归约为 Cokret capability / policy state。
- E2EE MIMI projection 必须满足 full MLS Governance Binding 下界；未声明 relaxed 降级不得按 full binding 接受。
- identifier query 不泄露 raw connection identifier。
- identifier query MUST NOT 返回任何形式的 "reachability proof"（§10 的强禁令负向可测项；facade MUST NOT 复活已被移除的 reachability proof 机制）。
- consent 不自动授予 membership / write capability。
- E2EE report franking 验证。
- proxy download 遵守 asset privacy policy。
- unsupported draft version fail closed。

## 13. 设计决定

Cokret v1 的 MIMI 支持固定为 facade profile：

- 不把 MIMI hub 变成 Cokret 的唯一 truth source。
- 不用 MIMI room id 替代 `realm_id`。
- 不用 MIMI user identifier 替代 DID。
- 不绕过 Cokret capability Control Move refs / Policy Server。
- 不把 MIMI provider accepted timestamp 替代 Cokret HLC / event hash。
- 支持 MIMI 草案版本 pinning，并允许未来 profile 处理草案变化。
