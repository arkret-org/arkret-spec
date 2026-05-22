---
title: MIMI Interoperability
---

> **状态：interop extension profile（非 v1 core 互操作必需）**。本文档描述的 MIMI Provider Facade 跟踪的
> 是仍在演进的 IETF MIMI Internet-Draft。Contrix v1 core 互操作 **不要求** 实现 MIMI
> facade；声称 `cx.profile.principal_server.v1` 或 `cx.profile.full_client.v1` 的实现
> 可以完全不实现本 profile。当 MIMI 升级为 RFC 后，将以新的 `cx.profile.mimi_interop_<rfc>.v1`
> 引入稳定 profile；当前 `cx.profile.mimi_interop.v1` 视为实验性 interop extension profile。

## 1. 目标

本文定义 Contrix 对 MIMI 的互操作 profile。目标不是把 Contrix core 改成 room-first 协议，而是在 Contrix 的 Realm / Event / DID / capability 模型外提供一个可测试的 **MIMI Provider Facade**，让支持 MLS 的 Contrix Realm 或 Flow discussion track 可以与 MIMI provider 互通。

`cx.profile.mimi_interop.v1` 固定参考以下草案版本：

- `draft-ietf-mimi-protocol-06`
- `draft-ietf-mimi-content-08`
- `draft-ietf-mimi-room-policy-03`
- `draft-kohbrok-mimi-identifiers-01`

这些草案仍是 Internet-Draft。实现 MUST 在 `server/describe` 和 MIMI provider directory 中声明实际支持的 draft version。草案更新导致 wire 语义变化时，Contrix MUST 通过新的 interop profile 版本处理，不得改变 v1 核心状态语义。

## 2. 角色

| MIMI 角色 | Contrix 映射 |
| --- | --- |
| Provider | `mimi_provider_facade` service DID，通常由 Principal Server、anchorer service 或受托 bridge 暴露。 |
| Hub provider | 对外拥有 MIMI room URI 的 provider service；在 Contrix 侧通常映射为 Principal Server 或 anchorer service，负责 MIMI room fanout 和 groupInfo。 |
| Follower provider | 参与 MIMI room 的远端 provider；在 Contrix 中表现为 federation peer 或 Applet bridge peer。 |
| User / client | Contrix principal DID + device id，可按 Realm policy 使用 pairwise DID 或 room-scoped pseudonym。 |
| Room | Contrix Flow discussion track 的 MIMI room 投影，可附带所在 Realm 的最小上下文。 |

MIMI facade 不是新的真相源。Contrix native 侧的 canonical truth 是 signed Move、Anchor frontier、Lattice cell state、capability refs 与 MLS Governance Binding（`governance_binding` + `covered_frontier_cell`）。MIMI room state 是对这些状态的互操作投影。

## 3. Provider Discovery

支持 MIMI 的服务 MUST 在 DID Document service entry 和 `GET /api/v1/server/describe` 中声明：

```json
{
  "service_type": "mimi_provider_facade",
  "supported_profiles": ["cx.profile.mimi_interop.v1"],
  "mimi": {
    "protocol_draft": "draft-ietf-mimi-protocol-06",
    "content_draft": "draft-ietf-mimi-content-08",
    "room_policy_draft": "draft-ietf-mimi-room-policy-03",
    "identifier_draft": "draft-kohbrok-mimi-identifiers-01",
    "base_url": "https://chat.example/api/v1/mimi",
    "provider_id": "mimi://example.com",
    "features": [
      "key_material",
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
GET /api/v1/mimi/provider-directory
```

目录响应 MUST 绑定 service DID、provider id、base URL、支持草案版本、endpoint 列表、MLS cipher suites、内容 profile、room policy components 和签名 proof。客户端和远端 provider MUST 验证 service DID、HTTP Message Signature、TLS endpoint、DID service endpoint 和 Realm policy 委托一致。

## 4. Room Binding

允许被导出为 MIMI room 的 Contrix 对象 MUST 有写入 `cx.component.mimi.room_binding.v1` cell 的 Move effect。兼容 Event kind 为 `cx.mimi.room_binding`；cell subject 是 `payload.mimi_room_uri`：

```json
{
  "kind": "cx.mimi.room_binding",
  "payload": {
    "profile": "cx.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
      "flow_id": "cx:flow:01964137-0000-7000-8000-000000000000"
    },
    "hub_provider": "did:web:mimi.example.com",
    "local_provider_role": "hub",
    "follower_providers": [
      "did:web:remote.example"
    ],
    "mls_group_id": "base64url...",
    "content_profile": "application/mimi-content",
    "policy_component_root": "sha256:...",
    "created_at": "2026-04-30T00:00:00Z"
  }
}
```

规则：

- `binding_scope.realm_id` MUST 指向一个 accepted Realm。`flow_id` MUST 指向该 Realm 内启用 discussion track 的 accepted Flow；MIMI room timeline 只投影该 Flow discussion track 的消息。
- `hub_provider` MUST 是 Realm policy、Organization DID 或 participant DID 明确委托的 service DID。
- `local_provider_role` 取值为 `hub`、`follower` 或 `bridge_only`。
- `cx.mimi.room_binding` 的创建、更新和撤销 MUST require `cx.policy.manage`、`cx.realm.admin` 或等价 interop capability。
- E2EE MIMI room MUST 绑定 `mls_group_id`，并按 `encryption-and-audit.md §2.5`（MLS Governance Binding）的 `covered_frontier_cell` precondition 校验 membership、policy 和 capability。
- 撤销 binding 后，facade MUST 停止接受新的 MIMI writes，只允许 backfill、tombstone、report、legal hold 或 migration proof 等维护操作。

## 5. Endpoint Surface

MIMI facade 至少定义以下 canonical operation：

| operation_id | HTTP binding | 语义 |
| --- | --- | --- |
| `cx.mimi.provider_directory` | `GET /mimi/provider-directory` | 返回 MIMI provider feature profile。 |
| `cx.mimi.key_material` | `POST /mimi/key-material` | 领取 MLS KeyPackage，映射到 Contrix KeyPackage claim lifecycle。 |
| `cx.mimi.room_update` | `PUT /mimi/rooms/{flow_id}/update` | 提交或转发 room state / MLS update。 |
| `cx.mimi.notify` | `POST /mimi/rooms/{flow_id}/notify` | provider 间投递通知、fanout 或 delivery event。 |
| `cx.mimi.submit_message` | `POST /mimi/rooms/{flow_id}/messages` | 提交 MIMI encrypted application message。 |
| `cx.mimi.group_info` | `GET /mimi/rooms/{flow_id}/group-info` | 获取 MLS groupInfo / room projection。 |
| `cx.mimi.request_consent` | `POST /mimi/consent/request` | 请求建立跨 provider 联系或 room invite consent。 |
| `cx.mimi.update_consent` | `POST /mimi/consent/update` | 更新 consent state。 |
| `cx.mimi.identifier_query` | `POST /mimi/identifiers/query` | 查询 connection identifier / MIMI URI 的可达性。 |
| `cx.mimi.report_abuse` | `POST /mimi/report-abuse` | 提交跨 provider abuse report，支持 E2EE frank。 |
| `cx.mimi.proxy_download` | `POST /mimi/proxy-download` | 代理或 oblivious 下载资产。 |

所有写入型 endpoint MUST 使用 HTTP Message Signatures 或等价 service proof，并绑定：

- source service DID
- destination service DID
- provider id
- MIMI room URI 或 target identifier
- request canonical hash
- created / expires
- body digest

Facade 接收请求后 MUST 先验证 MIMI envelope，再映射为 Contrix Move / compatible Event 或 to-device message。MIMI 传输签名只证明 provider 来源，不替代 Actor DID / device 签名、MLS transcript、capability 或 Realm policy。

## 6. Key Material

`cx.mimi.key_material` MUST 使用 `device-lifecycle.md` 的 KeyPackage claim API。请求必须包含：

- target MIMI identifier 或 DID / pairwise DID。
- intended MIMI room URI 和 Contrix `realm_id`。
- required content profile、MLS capabilities 和 cipher suites。
- requester provider DID 和 proof。
- 是否允许 minimal-metadata pseudonymous credential。

响应 MUST 返回 claimed KeyPackage、`claim_id`、`keypackage_ref`、device binding、expiry 和 supported capabilities。KeyPackage 被 Welcome 成功使用后 MUST 进入 `consumed`。不可见用户、无可用设备、policy denied 和不存在目标 SHOULD 使用统一失败形态，避免枚举。

## 7. Message Submission

`cx.mimi.submit_message` 接收 MIMI encrypted application message 后，facade MUST：

1. 验证 provider signature、room binding、destination、body digest 和重放窗口。
2. 验证 MLS epoch 与 `cx.mimi.room_binding.mls_group_id` 匹配。
3. 按 MLS Governance Binding 验证：commit 携带的 `governance_binding` 解析到的 Contrix Anchor view 与 state_root，且 `covered_frontier_cell` 覆盖该消息所需 governance frontier。
4. 将 MIMI content container 映射为 `cx.message.create`、`cx.message.revise`、`cx.message.redact`、`cx.reaction.add`、`cx.reaction.remove` 或 `cx.relation.*`。
5. 保留原始 MIMI envelope hash、provider id、message id 和 accepted timestamp 作为 interop metadata。
6. 对无法确认授权、epoch、content 或 policy 的消息返回 `temporarily_unavailable`、`dependency_missing`、`capability_denied` 或 `quarantine`。

Contrix native 客户端发送到 MIMI room 时，facade MUST 将 signed Contrix event 转换为 MIMI message，并把 MIMI provider accepted timestamp / message id 写回可验证 receipt 或 interop metadata。不得把 MIMI provider accepted timestamp 当作 Contrix event 的 creation truth；timeline 排序仍以 Contrix HLC / reducer 规则为准。

## 8. Content Mapping

MIMI facade MUST 支持接收：

- `application/mimi-content`
- `text/plain;charset=utf-8`
- `text/markdown;variant=GFM-MIMI`

推荐映射：

| Contrix | MIMI |
| --- | --- |
| `cx.content.text` plain | `text/plain;charset=utf-8` body part |
| `cx.content.text` markdown | `text/markdown;variant=GFM-MIMI` body part |
| `cx.content.composite` | MIMI multipart / multiple body parts |
| `reply_context` + `replies_to` Relation | MIMI reply behavior field |
| `cx.reaction.add/remove` | MIMI reaction / unlike behavior |
| `cx.message.revise` | MIMI edit behavior |
| `cx.message.redact` | MIMI delete behavior |
| `message_expiration` policy | MIMI expiring message field |
| attachment `blob_ref` | MIMI external content / asset reference |
| Room thread / Message relation | MIMI topic / threading field |

规则：

- 发送到 MIMI 时，facade SHOULD 生成 MIMI required / recommended media type，同时 MAY 附带 `application/vnd.contrix.content+json` proprietary alternative 以保留无损 Contrix 内容。
- 从 MIMI 接收未知 extension field 时，facade MUST 保留原始 CBOR bytes 或 canonical hash，至少保证未来支持时可回放或审计。
- 任何正文 fallback 进入 E2EE Realm 时必须仍在密文中；不得为了 MIMI 预览把 `body` 明文复制到 routing metadata。
- Link preview、attachment thumbnail 和 asset metadata MUST 遵守 `asset_privacy_policy` 与 `plaintext_visible_services`。

## 9. Room Policy Mapping

Contrix v1 把 Realm-level policy 映射为 Move effects on cell families。Facade 在 MIMI room policy 与 Contrix state 之间转换时，读取 registry 中的 `cell_family`、`lattice` 与 `bottom`。

### 9.1 Cell Family 互译

| Contrix cell_family | Contrix effect kind | MIMI policy component（draft-ietf-mimi-room-policy） |
| --- | --- | --- |
| `cx.component.realm.policy.v1` | `cx.realm.policy` | （Contrix 专属；映射时合并入 `operational`） |
| `cx.component.realm.join_rule.v1` | `cx.realm.join_rule` | `participation` 中 `join_policy` 子字段（粗粒度入口枚举） |
| `cx.component.realm.join_policy.v1` | `realm.join_policy`（candidate workflow concept/action 名称，不是 v1 wire `Event.kind`；见 [`../conformance/schema-registry.md` §4.1](../conformance/schema-registry.md)） | `participation.join_policy` 子字段（结构化 gates / reviewer / TTL）；MIMI 侧未覆盖部分以 `application/vnd.contrix.component+json` 私有扩展承载 |
| `cx.component.realm.history_visibility.v1` | `cx.realm.history_visibility` | `history_sharing` 的 visibility 子字段 |
| `cx.component.realm.discovery.v1` | `cx.realm.discovery` | `participation` 中 `discoverability` 子字段 |
| `cx.component.realm.policy_server.v1` | `cx.realm.policy_server` | （Contrix 专属，与 MIMI hub provider 概念解耦） |
| `cx.component.realm.policy_components.v1` | `cx.realm.policy_components` | MIMI policy component 集合声明（root + active list） |
| `cx.component.realm.history_sharing_policy.v1` | `cx.realm.history_sharing_policy` | `history_sharing` |
| `cx.component.realm.asset_privacy_policy.v1` | `cx.realm.asset_privacy_policy` | `asset` |
| `cx.component.realm.moderation_policy.v1` | `cx.realm.moderation_policy` | `logging` 的 abuse-report 子字段 + 自定义 `moderation` extension |
| `cx.component.realm.plaintext_visible_services.v1` | `cx.realm.plaintext_visible_services` | （Contrix 专属隐私透明度机制；MIMI 侧无对应） |
| `cx.component.realm.media_service.v1` | `cx.realm.media_service` | （Contrix 专属，与 MIMI 的 hub provider 解耦） |
| `cx.component.realm.schema.v1` | `cx.realm.schema` | （Contrix 专属，schema_refs 声明） |
| `cx.component.realm.inheritance_policy.v1` | `cx.realm.inheritance_policy` | （Contrix 专属，per-parent 继承） |
| `cx.component.realm.archive.v1` | `cx.realm.archive` | （部分等价于 MIMI lifecycle hint，目前 MIMI 草案未规范） |
| `cx.component.realm.freeze.v1` | `cx.realm.freeze` | 同上 |
| `cx.component.realm.tombstone.v1` | `cx.realm.tombstone` | 同上 |
| `cx.component.realm.destroy.v1` | `cx.realm.destroy` | 同上 |
| `cx.component.member.state.v1` | `cx.member.state` | MLS GroupContext 的 leaf node + roster；Contrix membership 不进入 MIMI policy components |

> 历史的 MIMI components（`roles`、`preauth`、`bot`、`message_expiration`、`operational`）在 Contrix 中是 `cx.realm.policy_components` cell 的子字段，而不是独立 kind。Facade 接收 MIMI policy update 时 MUST 把这些 components 归约为 `cx.realm.policy_components` Move effect。
>
> MIMI room policy 投影 MUST 落在有效 Realm（source Realm 或 `Flow.discussion_realm_ref` 指向的 linked Realm）的 `cx.realm.policy_components` cell；不存在 track-scoped policy projection——track 不携带独立 access。

### 9.2 Unknown Handling

Contrix 的 unknown handling 来自 Lattice bottom：

| Contrix | MIMI |
| --- | --- |
| `bottom=reject` 或 unknown core lattice | `must-understand` |
| `bottom=expose` | `should-understand` / exposed conflict |
| 非授权 projection extension | `silently-drop`，但必须保留 raw bytes 或 canonical hash |

**Facade 责任**：

- 接收 MIMI policy update 时 MUST 验证目标 `cell_family` 已注册（或被部署的 profile 显式 opt-in），并归约为对应 Move effect；未注册 MIMI component MUST 按其 MIMI unknown-handling 处理。
- 发送 Contrix state 到 MIMI 时 MUST 按 §9.1 表生成 MIMI component。Contrix 专属 component（无 MIMI 对应）在 facade 输出中标记为 `application/vnd.contrix.component+json` 私有扩展。

MIMI role 只能作为 interop projection。Contrix 授权仍以 capability Move / grant cell 为准。Facade 在接收 MIMI role/policy update 时 MUST 归约为 `cx.capability.*` 或具体 `cx.realm.<facet>` Move effect，并经过 Contrix Move refs 授权验证后才能生效。

## 10. Identifiers And Consent

MIMI identifier MUST NOT 被直接作为 Contrix actor。映射规则：

- MIMI provider identifier 映射到 service DID。
- MIMI user identifier 映射到 principal DID、pairwise DID 或 pending invite proof。
- connection identifier 仅用于 discovery / consent，不进入 Realm history，除非 holder 明确作为 handle / claim 披露。
- display name 只用于 UI，不参与授权。

`cx.mimi.identifier_query` SHOULD 调用 `cx.private_contact_discovery.v1`，按 [`discovery/discovery-directory.md` §6](../discovery/discovery-directory.md) 的 PSI 流程返回 set-membership 命中位图与 invite handoff stub；MUST NOT 返回任何形式的 "reachability proof"——该机制在 v1 已被移除（见 `discovery-directory.md` §6 的 PSI-only 边界），facade 实现 MUST NOT 复活它。`cx.mimi.request_consent` / `cx.mimi.update_consent` MUST 映射为 Contrix 的 holder-private consent state（`cx.consent.grant` / `cx.consent.revoke`，详见 [`identity/consent-model.md`](../identity/consent-model.md)）。Consent 不授予 Realm read/write 权限；加入和发消息仍需 membership、capability 和 policy checks。Facade 在两侧 round-trip 时 MUST 保留 `consent_id` 作为 inter-protocol correlation。

## 11. Abuse Report And Proxy Download

`cx.mimi.report_abuse` MUST 映射到 `cx.moderation.report`。E2EE report SHOULD 携带 message frank、encrypted evidence package、reporter signature、MIMI room id、provider id 和 target event hash。Facade MUST NOT 要求 reporter 向普通 provider 上传未加密明文；只有被 Realm policy 授权的 moderation recipient 可以解密 evidence。

`cx.mimi.proxy_download` MUST 遵守 `cx.realm.asset_privacy_policy`。当 policy 要求 `provider_proxy` 或 `ohttp_relay` 时，facade 不得返回 direct object-store URL。下载成功不证明内容可信，客户端仍 MUST 验证 content hash、ciphertext digest 和 attachment metadata。

## 12. Conformance

`cx.profile.mimi_interop.v1` MUST 测试：

- provider directory draft pinning 与 service DID 签名。
- `cx.mimi.room_binding` 创建、更新、撤销和 policy root 校验。
- KeyPackage single-use claim / Welcome consume。
- Contrix message 到 MIMI content roundtrip。
- MIMI text / markdown / reply / reaction / edit / delete / attachment 接收映射。
- MIMI policy update 归约为 Contrix capability / policy state。
- identifier query 不泄露 raw connection identifier。
- consent 不自动授予 membership / write capability。
- E2EE report franking 验证。
- proxy download 遵守 asset privacy policy。
- unsupported draft version fail closed。

## 13. 设计决定

Contrix v1 的 MIMI 支持固定为 facade profile：

- 不把 MIMI hub 变成 Contrix 的唯一 truth source。
- 不用 MIMI room id 替代 `realm_id`。
- 不用 MIMI user identifier 替代 DID。
- 不绕过 Contrix capability Move refs / policy server。
- 不把 MIMI provider accepted timestamp 替代 Contrix HLC / event hash。
- 支持 MIMI 草案版本 pinning，并允许未来 profile 处理草案变化。
