---
title: MIMI Interoperability
---

> **状态：v1.1+ extension（非 core 互操作）**。本文档描述的 MIMI Provider Facade 跟踪的
> 是仍在演进的 IETF MIMI Internet-Draft。Contrix v1 core 互操作 **不要求** 实现 MIMI
> facade；声称 `cx.profile.principal_server.v1` 或 `cx.profile.full_client.v1` 的实现
> 可以完全不实现本 profile。当 MIMI 升级为 RFC 后，将以新的 `cx.profile.mimi_interop_<rfc>.v1`
> 引入稳定 profile；当前 `cx.profile.mimi_interop.v1` 视为实验性 / interop staging。

## 1. 目标

本文定义 Contrix 对 MIMI 的互操作 profile。目标不是把 Contrix core 改成 room-first 协议，而是在 Contrix 的 Space / Event / DID / capability 模型外提供一个可测试的 **MIMI Provider Facade**，让支持 MLS 的 Contrix Space 或 Flow discussion branch 可以与 MIMI provider 互通。

`cx.profile.mimi_interop.v1` 固定参考以下草案版本：

- `draft-ietf-mimi-protocol-06`
- `draft-ietf-mimi-content-08`
- `draft-ietf-mimi-room-policy-03`
- `draft-kohbrok-mimi-identifiers-01`

这些草案仍是 Internet-Draft。实现 MUST 在 `server/describe` 和 MIMI provider directory 中声明实际支持的 draft version。草案更新导致 wire 语义变化时，Contrix MUST 通过新的 interop profile 版本处理，不得改变 v1 核心状态语义。

## 2. 角色

| MIMI 角色 | Contrix 映射 |
| --- | --- |
| Provider | `mimi_provider_facade` service DID，通常由 Principal Server 或受托 Space Host 暴露。 |
| Hub provider | 对外拥有 MIMI room URI 的 Space Host / Principal Server；负责 MIMI room fanout 和 groupInfo。 |
| Follower provider | 参与 MIMI room 的远端 provider；在 Contrix 中表现为 federation peer 或 Applet bridge peer。 |
| User / client | Contrix principal DID + device id，可按 Space policy 使用 pairwise DID 或 room-scoped pseudonym。 |
| Room | Contrix Flow discussion branch 的 MIMI room 投影，可附带所在 Space 的最小上下文。 |

MIMI facade 不是新的真相源。Contrix native 侧的 canonical truth 仍然是 signed Event、auth refs、state resolution、MLS-bound state root 和 reducer 输出。MIMI room state 是对这些状态的互操作投影。

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

目录响应 MUST 绑定 service DID、provider id、base URL、支持草案版本、endpoint 列表、MLS cipher suites、内容 profile、room policy components 和签名 proof。客户端和远端 provider MUST 验证 service DID、HTTP Message Signature、TLS endpoint、DID service endpoint 和 Space policy 委托一致。

## 4. Room Binding

允许被导出为 MIMI room 的 Contrix 对象 MUST 有 `cx.mimi.room_binding` state event：

```json
{
  "kind": "cx.mimi.room_binding",
  "state_key": "mimi://example.com/rooms/01JSMIMI...",
  "payload": {
    "profile": "cx.profile.mimi_interop.v1",
    "mimi_room_uri": "mimi://example.com/rooms/01JSMIMI...",
    "binding_scope": {
      "space_id": "cx:space:01js0sp0000000000000000000",
      "flow_id": "cx:flow:01JS..."
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

- `binding_scope.space_id` MUST 指向一个 accepted Space。`flow_id` MUST 指向该 Space 内启用 discussion branch 的 accepted Flow；MIMI room timeline 只投影该 Flow discussion branch 的消息。
- `hub_provider` MUST 是 Space policy、Organization DID 或 participant DID 明确委托的 service DID。
- `local_provider_role` 取值为 `hub`、`follower` 或 `bridge_only`。
- `cx.mimi.room_binding` 的创建、更新和撤销 MUST require `cx.policy.manage`、`cx.space.admin` 或等价 interop capability。
- E2EE MIMI room MUST 绑定 `mls_group_id`，并按 `encryption-and-audit.md` 的 MLS-bound application state root 校验 membership、policy 和 capability。
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

Facade 接收请求后 MUST 先验证 MIMI envelope，再映射为 Contrix Event 或 to-device message。MIMI 传输签名只证明 provider 来源，不替代 Actor DID / device 签名、MLS transcript、capability 或 Space policy。

## 6. Key Material

`cx.mimi.key_material` MUST 使用 `device-lifecycle.md` 的 KeyPackage claim API。请求必须包含：

- target MIMI identifier 或 DID / pairwise DID。
- intended MIMI room URI 和 Contrix `space_id`。
- required content profile、MLS capabilities 和 cipher suites。
- requester provider DID 和 proof。
- 是否允许 minimal-metadata pseudonymous credential。

响应 MUST 返回 claimed KeyPackage、`claim_id`、`keypackage_ref`、device binding、expiry 和 supported capabilities。KeyPackage 被 Welcome 成功使用后 MUST 进入 `consumed`。不可见用户、无可用设备、policy denied 和不存在目标 SHOULD 使用统一失败形态，避免枚举。

## 7. Message Submission

`cx.mimi.submit_message` 接收 MIMI encrypted application message 后，facade MUST：

1. 验证 provider signature、room binding、destination、body digest 和重放窗口。
2. 验证 MLS epoch 与 `cx.mimi.room_binding.mls_group_id` 匹配。
3. 验证 MLS-bound `application_state_ref` 对应 Contrix accepted state。
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
- 任何正文 fallback 进入 E2EE Space 时必须仍在密文中；不得为了 MIMI 预览把 `body` 明文复制到 routing metadata。
- Link preview、attachment thumbnail 和 asset metadata MUST 遵守 `asset_privacy_policy` 与 `plaintext_visible_services`。

## 9. Room Policy Mapping

Contrix `cx.space.policy.set` (state_key=`policy_components`) 与 MIMI room policy 组件按以下方式映射：

| Contrix policy component | MIMI policy 语义 |
| --- | --- |
| `roles` | MIMI room roles / capabilities。 |
| `preauth` | pre-authorized joins、join links、invite token。 |
| `history_sharing` | chat history / history sharing policy。 |
| `asset` | upload domain、asset privacy、proxy download。 |
| `logging` | logging、retention、auditable E2EE disclosure。 |
| `bot` | bot / bridge / automated actor policy。 |
| `message_expiration` | message expiration。 |
| `operational` | provider fanout、limits、rate limits、failure behavior。 |

MIMI role 只能作为 interop projection。Contrix 授权仍以 capability 为准。Facade 在接收 MIMI role/policy update 时 MUST 归约为 `cx.capability.*`、`cx.space.policy.set` (state_key=`policy_components`) 或具体 policy state event，并经过 Contrix auth refs 验证后才能生效。

## 10. Identifiers And Consent

MIMI identifier MUST NOT 被直接作为 Contrix actor。映射规则：

- MIMI provider identifier 映射到 service DID。
- MIMI user identifier 映射到 principal DID、pairwise DID 或 pending invite proof。
- connection identifier 仅用于 discovery / consent，不进入 Space history，除非 holder 明确作为 handle / claim 披露。
- display name 只用于 UI，不参与授权。

`cx.mimi.identifier_query` SHOULD 调用 `cx.private_contact_discovery.v1`，并返回 time-bound reachability proof。`cx.mimi.request_consent` / `cx.mimi.update_consent` MUST 映射为 holder-private consent state、invite、presentation request 或 claim proof。Consent 不授予 Space read/write 权限；加入和发消息仍需 membership、capability 和 policy checks。

## 11. Abuse Report And Proxy Download

`cx.mimi.report_abuse` MUST 映射到 `cx.moderation.report`。E2EE report SHOULD 携带 message frank、encrypted evidence package、reporter signature、MIMI room id、provider id 和 target event hash。Facade MUST NOT 要求 reporter 向普通 provider 上传未加密明文；只有被 Space policy 授权的 moderation recipient 可以解密 evidence。

`cx.mimi.proxy_download` MUST 遵守 `cx.space.policy.set` (state_key=`asset_privacy`)。当 policy 要求 `provider_proxy` 或 `ohttp_relay` 时，facade 不得返回 direct object-store URL。下载成功不证明内容可信，客户端仍 MUST 验证 content hash、ciphertext digest 和 attachment metadata。

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
- 不用 MIMI room id 替代 `space_id`。
- 不用 MIMI user identifier 替代 DID。
- 不绕过 Contrix capability / auth refs / policy server。
- 不把 MIMI provider accepted timestamp 替代 Contrix HLC / event hash。
- 支持 MIMI 草案版本 pinning，并允许未来 profile 处理草案变化。
