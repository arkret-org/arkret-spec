---
title: WebRTC Calls and Meetings
status: candidate
normative: true
stability: v1
updated: 2026-07-02
sidebar:
  label: WebRTC Calls
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 支持音频通话、视频通话、屏幕共享和多人会议。实时媒体本身不进入 Realm Event history；信令、会议状态、邀请、参与者变化、录制引用和通话摘要按不同持久性处理。

本文件定义 **ephemeral 信令与 WebRTC 传输面**：

- 一对一 WebRTC P2P 通话
- TURN / STUN / ICE server 动态发现与 in-call 凭证刷新
- 信令 envelope（offer/answer/candidate/renegotiate 等）、多设备冲突处理
- 屏幕共享、推送集成、信令层安全与隐私

相邻规范：

- 媒体服务发现、token / participant binding 兑换、focus 选举、SFU 权限、媒体 E2EE 帧密钥注入与治理绑定，见 [`media-service-binding.md`](./media-service-binding.md)。
- 通话模型与状态机、durable `ak.call.state` 字段语义、录制 / 转写生命周期，见 [`call-state.md`](./call-state.md)。

## 2. 设计原则

### 2.1 信令是 Ephemeral

Offer、Answer、ICE candidate、renegotiation、speaking update 等高频信令 SHOULD 通过 Station sync surface 的 Signal Extension 或等价 streaming transport 发送。

通话摘要、会议实体、录制 artifact、会议权限变化 MAY 作为 Durable Event 写入 Realm Event history。

### 2.2 信令必须认证和加密

WebRTC 信令会暴露设备、网络和媒体能力。所有信令 MUST：

- 绑定 Realm id、call id、device id、actor id。
- 由发送设备签名，并封装在已认证的 encrypted Signal rail。
- 对同一 Realm / DM 的授权成员端到端加密。
- 防重放，至少包含 timestamp、sequence 或 frame id。

### 2.3 媒体路径不等于信任路径

媒体可能经过 TURN、SFU 或 MCU。它们可以转发包或混流，但不得因此获得 Realm 权限。媒体服务 MUST 有 service DID，并由 Realm policy 显式允许。

## 3. 权限模型

标准 actions（canonical 命名以 capability registry / `contract-registry.json` 为唯一真源；正文与实现 MUST 使用带 `ak.` 前缀的形态，MUST NOT 接受裸 `call.*` 名）：

- `ak.call.join` —— 创建或加入 call。发起方必须先提交 `ak.call.create`，由其 Event ID 派生 `call_id`；后续所有 `ak.call.state` 与信令只能引用已 accepted 的 create。
- `ak.call.signal.send` —— 发送 call signaling frame，含邀请（`ak.call.signal{kind=invite}`）。v1 不注册独立的 `call.invite`，邀请通过该 signaling action 表达。
- `ak.call.screen_share`
- `ak.call.record`
- `ak.call.transcribe`
- `ak.call.moderate` —— 主持 / 管理操作，含对全体结束 call。v1 不注册独立的 `call.end_for_all`，end-for-all 由 `ak.call.moderate` 授权。
- `ak.realm.media_service`

默认规则：

- offer / answer / candidate / invite / focus_join 发送、push 响铃、ICE/TURN 凭证与媒体 token 签发都 MUST 在服务端解析到同 Realm 的 accepted `ak.call.create` 后才可执行；裸 `call_id` 不能创建会话占位。
- Realm 成员不自动拥有 `ak.call.record`。
- `ak.call.screen_share` SHOULD 独立授权。
- `ak.realm.media_service` 只应授予管理员或受信服务。
- Actor 加入 call 的资格 MUST 按分层 predicate 校验，不得依赖泛化口语状态（如笼统的「被 ban / suspended」）：(a) 在目标 `realm_id` 的 Realm membership 必须为 `join`；(b) 若 call scoped 到某 Circle，该 actor 还必须是该 Circle 的活跃成员；(c) account lifecycle status MUST NOT 为 `suspended` / `deactivated` / `erasure_pending`；(d) 发起设备的 device grant MUST NOT 被 revoked，且其 `ak.call.join` capability grant 未被 revoke。任一条不满足 MUST NOT 加入。
- `signal_kind=invite` 还 MUST 通过 [`identity/consent-model.md` §6.2](../identity/consent-model.md) 的 `voice_call` / `video_call` consent gate；服务端投递、目标客户端响铃 UI 与 media token 签发都不得仅信任发起方 preflight。
- 外部 guest 加入必须通过 invite 或 meeting-specific guest grant。

### 3a. 主持 / 审核（kick / ban / end-for-all / force-mute，normative）

主持操作统一由 `ak.call.moderate` capability 授权(§3)。无该 capability 的 actor 发出任一主持信令 / 写任一主持字段，接收方与 reducer MUST 拒绝，错误码 `call_moderation_unauthorised`。

主持动作通过 `ak.call.signal{signal_kind=moderation}` 或 §6.1 的 `mute_state{by=moderator}` 表达瞬时控制，并在 durable `ak.call.state` 留痕：kick / ban 写入 `moderation_delta`，end-for-all 写入 `state_transition.to="ended"`，force-mute 写入目标 leg 的 `mute_override`。`moderation` payload `data` 形态:

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 60,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "moderation",
  "seq": 30,
  "data": {
    "action": "kick",
    "target_actor_id": "ak:did_core:webvh:zHuXvTbhiRsj2KEPE64TLhzG4",
    "target_device_id": "ak:device:01964137-0000-7000-8000-000000000000",
    "reason": "policy_violation"
  }
}
```

- `action` MUST 为 `kick` / `ban` / `end_for_all` 之一。强制静音走 §6.1 的 `mute_state{by=moderator}`，不复用本信令，但同样 MUST 由 `ak.call.moderate` 授权并落目标 leg 的 `mute_override`。
- `kick`:移除某 `(target_actor_id, target_device_id)` 的当前 call leg。被点名设备收到后 MUST 立即拆除媒体并退出；SFU 部署中 backend 同时按 token issuer 通知断开该 `participant_id`。kick 不阻止该 actor 重新发起 join。
- `ban`:移除某 `target_actor_id`(其全部设备)并在本通话生命周期内禁止其重新加入。被 ban 的 actor 重新兑换 join token 时，token issuer MUST 拒绝 `call_participant_removed`。
- `end_for_all`:对全体结束通话。它由 `ak.call.moderate` 授权(v1 不注册独立的 `call.end_for_all`)，并 MUST 紧随一条携带 `ak.call.state.state_transition.to="ended"` 的 durable event；收到的客户端 MUST 全部挂断。
- kick / ban MUST 以 `ak.call.state.moderation_delta.op="remove_participant"` 留痕(其 `removal` 为 `{ actor_id, device_id?, action, removed_by, removed_at }`;`ban` 省略 `device_id` 表示按 actor 维度)。token issuer 与 SFU 在签发 / 接纳 participant 前 MUST 校验目标不在 `call_moderation` effective authority-ordered keyed set 的 ban 集合内，违反 `call_participant_removed`。
- force-mute MUST 以 `ak.call.state.mute_override` 写入 `(call_id, actor_id, device_id)` 的当前覆盖值；token issuer 与 SFU 在签发 / 刷新 / 接纳 participant send permission 前 MUST 应用该值，禁止被静音 track 继续上行。客户端本地强制静音只是 UX 镜像，MUST NOT 是唯一 enforcement。
- 所有主持信令受 §5 的 `seq` 单调性防回滚；`moderation` 帧 MUST 由具备 `ak.call.moderate` 的 actor 签名。

## 4. ICE Server Discovery

客户端通过 Realm policy、service discovery 或 media service 获取 ICE servers。媒体服务本身的 multi-focus 声明（`ak.realm.media_service`）见 [`media-service-binding.md` §2](./media-service-binding.md)。

### 4.1 ICE Config Endpoint

默认 HTTP binding：

```http
POST /_arkret/self/rtc/ice-config
Authorization: Bearer <token>
Content-Type: application/json
```

请求 schema 见 [`media-operations.schema.json#/$defs/media_ice_config_request_body`](../../artifacts/schemas/media-operations.schema.json)。字段语义如下：

客户端调用 `ice_config_endpoint` 前 MUST 按 [`media-service-binding.md` §2.1](./media-service-binding.md) 消费自己 Station 的已验证媒体服务绑定结果，核对 `ak.realm.media_service` 的该 exact typed current result value 与结果 `route.service_id` 一致，且该 endpoint 的 origin 落在 `route.base_url` 之内。缺失、stale 或不一致时 MUST fail closed(`media_service_binding_uncovered`)，不得向该 endpoint 请求 ICE/TURN credential；ICE config 响应签名的 kid 也 MUST 命中同一结果的 `signing_keys`，否则 `token_issuer_unauthorised`。endpoint 变更不进入 `key_access_revision`，因此这里 **MUST NOT** 额外要求该 event 被当前 epoch MLS governance binding 覆盖，也不得为它强制 rekey。

**凭证缓存与日志脱敏（normative）**：ICE config 响应体携带短期 TURN `credential` / `username`（bearer 性质）。`POST /_arkret/self/rtc/ice-config` 响应 MUST 携带 `Cache-Control: private, no-store`；服务端 MUST NOT 在 access log / metrics / tracing 中记录响应体中的 `credential` 与 `username` 原文，客户端 MUST NOT 把 TURN credential 持久化到普通日志 / 浏览器历史 / analytics。这与 blob presign bearer URL（[`media-and-blob.md` §5.4.3](./media-and-blob.md)）同级:虽然媒体帧另有 SFrame E2EE 且 credential 短时效 per-call，被缓存 / 落日志的 credential 在 TTL 窗口内仍可被取用以滥用 TURN 中继资源。

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 调用者认证，MUST 绑定 `actor_id` 与 `device_id`。 |
| `realm_id` | body | `id` | required | 通话所在 Realm。 |
| `call_id` | body | `id` | required | 通话 ID。 |
| `actor_id` | body | `ActorId` | required | 请求 ICE 配置的 Actor，完整 tagged `ActorId` 对象（`common-ids.schema.json#/$defs/actor_id`）；裸 DID 字符串 MUST `schema_violation`。 |
| `device_id` | body | `id` | required | 请求设备。 |
| `mode` | body | `enum(p2p,sfu,turn)` | required | **传输模式请求**，与 [`call-state.md` §2](./call-state.md) 的会议拓扑 `call_mode`（`{p2p,mesh,sfu,mcu}`）**不是同一枚举、不是同一概念**：本字段表达"客户端希望服务端为本次 ICE 协商返回何种传输面凭证"，`call_mode` 表达"整通会议在 §2 模型下的拓扑形态"。二者同名值（`p2p` / `sfu`）只是巧合，MUST NOT 互相推导或混用。各取值语义：`p2p` = 请求直连 / srflx candidate 优先的对等传输；`sfu` = 请求接入 SFU focus 所需的 ICE/TURN 凭证；`turn` = 请求纯 TURN 中继传输（强制经 TURN server 转发，不暴露 host/srflx candidate，等价于 `force_turn=true` 的传输诉求，用于高隐私 / 受限网络）。本字段不决定也不改写 `ak.call.state.focus.mode`；会议拓扑的权威值始终是 `call-state.md` 的 `call_mode`。**call_mode → 传输 mode 映射（normative）**：`call_mode=mesh` 的各对等腿请求 `mode=p2p`（或受限网络下 `mode=turn`）；`call_mode=mcu` 与 `call_mode=sfu` 均请求 `mode=sfu`（接入 focus 的 ICE/TURN 凭证；纯中继诉求用 `mode=turn`）。即 `mesh` 映射到对等传输、`mcu`/`sfu` 映射到 focus 传输，不存在未覆盖的拓扑→传输空白。 |

请求示例：

```json schema=schemas/media-operations.schema.json#/$defs/media_ice_config_request_body
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6mkfixture",
      "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
    }
  },
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "mode": "p2p"
}
```

响应字段（schema 见 [`ice-config-response.schema.json`](../../artifacts/schemas/ice-config-response.schema.json)，schema id `ak.schema.ice_config_response.v1`）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `realm_id` | `id` | required | 回显请求 Realm，进入签名 canonical bytes，防止跨 Realm 重放。 |
| `call_id` | `id` | required | 回显请求 call，进入签名 canonical bytes，防止跨通话重放。 |
| `actor_id` | `ActorId` | required | 回显请求的完整 tagged `ActorId`（与请求逐字节相等），进入签名 canonical bytes。 |
| `device_id` | `id` | required | 回显请求设备，进入签名 canonical bytes。 |
| `ttl_seconds` | `int` | required | ICE 配置有效期（秒）。建议 ≤ 1 小时。 |
| `refresh_lead_seconds` | `int` | required | 客户端在剩余有效期 ≤ 此值时 SHOULD 提前刷新；建议 `ttl_seconds / 4`。schema 合法范围为 `minimum=10`、`maximum=1800`。**服务端 MUST 保证 `refresh_lead_seconds` 严格小于 `ttl_seconds`**（否则客户端在签发瞬间即判定 credential 需刷新，陷入刷新风暴)。推荐 floor 60s 仅在 `60 < ttl_seconds` 时适用，否则 `refresh_lead_seconds < ttl_seconds` 优先于推荐 floor（floor 让位的完整论证与取值规则见 §4.2 服务端规则）。让所有客户端按统一节奏 refresh，server 也据此设计 secret rotation grace 窗口。 |
| `issued_at` | `timestamp` | required | 服务端签发时间，进入签名 canonical bytes。 |
| `ice_servers` | `object[]` | required | STUN/TURN server 配置数组。 |
| `ice_servers[].urls` | `string[]` | required | STUN/TURN URL。 |
| `ice_servers[].username` | `string` | TURN 时 required | TURN 用户名（per-call pairwise pseudonym，REST-style: `<expiry-unix>:<pseudonym>`）。 |
| `ice_servers[].credential` | `string` | TURN 时 required | 短期 TURN credential（HMAC-SHA256 of username）。 |
| `ice_servers[].credential_type` | `string` | optional | credential 类型，例如 `password`。 |
| `turn_required` | `boolean` | optional | 是否强制 TURN（高隐私 Realm）。 |
| `constraints` | `object` | optional | 候选地址与传输策略（`udp_allowed` / `tcp_allowed` / `ipv6_allowed`）。 |
| `next_retry_at` | `timestamp` | optional | 软失败（如 `turn_credential_expired`）时返回；客户端 MUST NOT 在此前重试。 |
| `signature` | `signature` | required | Media Service DID 对 canonical bytes（去除 `signature` 自身）的 detached 签名。 |

响应示例：

```json schema=schemas/ice-config-response.schema.json
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6mkfixture",
      "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
    }
  },
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "ttl_seconds": 600,
  "refresh_lead_seconds": 60,
  "issued_at": "2026-04-26T00:00:00.000Z",
  "ice_servers": [
    {
      "urls": [
        "stun:stun.example.com:3478"
      ]
    },
    {
      "urls": [
        "turns:turn.example.com:5349?transport=tcp"
      ],
      "username": "1699999999:ak_pseudonym_call_4f7c3b2a9e1d5a6f",
      "credential": "H1qD0S6dbc7Xk3mPZ4Nn2QWQ8o9tQ3vJ5UcxGsq4Xf0",
      "credential_type": "password"
    }
  ],
  "turn_required": false,
  "constraints": {
    "udp_allowed": true,
    "tcp_allowed": true,
    "ipv6_allowed": true
  },
  "signature": {
    "kid": "did:webvh:z7ECJ5c1A1o5Xr1AdPqPCBD7L:media.example.com#key-1",
    "sig": "Yq2wq5mQ3vJ5UcxGsq4Xf0H1qD0S6dbc7Xk3mPZ4Nn2QWQ8o9tQ3vJ5UcxGsq4Xf0H1qD0S6dbc7Xk3mPZ4Nn2Q",
    "signature_algorithm": "Ed25519"
  }
}
```

要求：

- TURN credential MUST 短期有效，SHOULD 使用 REST-style ephemeral credential（draft-uberti-rtcweb-turn-rest-00 风格 username = `<expiry-unix>:<pairwise-pseudonym>`，password = `HMAC-SHA256(turn_shared_secret, username)`；实现不得降级为 HMAC-SHA1）。
- TURN `username` 中的"身份段" MUST 是 **per-call pairwise pseudonym**（建议形态 `ak_pseudonym_call_<random>` 或等价 random tag）。它不得是 principal DID、handle、邮箱或可跨呼叫关联的稳定 ID；该不可关联性只针对 TURN 运营方成立，不对铸造 pseudonym 的 Arkret media service 成立。
- v1 固定 `ice_bucket(t)=UTC_timestamp(floor(unix_seconds(t)/300)*300)`。server 与 client MUST 从签名覆盖的 `issued_at` 计算该值；不得在 response wire 中另传 bucket 常量或 bucket 起点。客户端 SHOULD 在跨越下一 300 秒 bucket 前 refresh。credential expiry 同样只计算为 `issued_at + ttl_seconds`，不得另传 `expires_at`；canonical timestamp 加法溢出 MUST fail closed。
- Pseudonym 生成 MUST 使用每次通话的新随机种子或 media service 私有密钥派生，且至少绑定 `(realm_id, call_id, actor_id, device_id, ice_bucket(issued_at), media_service_id)`；推荐：

  ```text
  pseudonym = "ak_pseudonym_call_" ||
    base64url(HMAC-SHA256(media_service_pseudonym_secret,
      canonical_json({realm_id, call_id, actor_id, device_id, ice_bucket: ice_bucket(issued_at), nonce})
    )[0:16])
  ```

  `nonce` MUST 对每个 `(call_id, actor_id, device_id)` fresh，media service MUST 在签名 ICE config 的内部审计记录中保留 nonce freshness evidence，且不得把 nonce 或其稳定派生值写入 TURN username 之外的可跨 Realm 关联字段。Refresh 时同一 active call leg MAY 复用 pseudonym 以避免 TURN 误判为不同会话，但新 call、new device leg、超过 `ttl_seconds + refresh grace` 的恢复、或 policy 要求匿名重置时 MUST 生成新 pseudonym。Pseudonym 不得仅由稳定 ID 确定性派生。
- ICE config response MUST 由 media service 签名；`signature.signature_algorithm` MUST 是 [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) 中 `status=active` 且 `proof_kinds` 包含 `detached_jws` 的 `raw_signature_algorithm` 值。default v1 部署使用 `Ed25519`；高保证或部署特定 profile MAY 要求 registry 中的其它 active 算法，但签名 canonical bytes 与本节 domain label 不变。签名 canonical bytes MUST 覆盖 response 去除 `signature` 后的完整权威对象，包括 `realm_id`、`call_id`、`actor_id`、`device_id`、`issued_at`、`ttl_seconds`、`ice_servers[]` 与策略字段；derived bucket 与 expiry 由这些已签输入唯一决定，不进入 wire。TLS + service DID 绑定只能认证通道，不能替代响应对象签名。
  - **签名 domain label（normative，跨实现互通契约）**：ICE config response `signature.sig` MUST 是 issuer 私钥（对应 `signature.kid`）按 `signature.signature_algorithm` 指定算法对下列字节串产生的签名；`signature.signature_algorithm="Ed25519"` 时该签名为 Ed25519。`ES256`、`ML-DSA-65` 等其它允许 detached JWS 的 active `signature_algorithm` 值只改变验签算法和 key type，不改变本 signing input、domain label 或 payload digest：

    ```text
    signing_input =
      "ak.media.ice_config.v1" || 0x00 ||
      canonical_json(<ICE config response 去除 `signature` 字段后的权威对象>)
    ```

    第一段是固定 ASCII 域分隔 label（逐字节等于 `ak.media.ice_config.v1`），随后单字节 `0x00` 分隔，再接去掉 `signature` 自身后的响应对象的 canonical JSON（RFC 8785 JCS：键按字母序、无多余空白，故字段书写顺序无关）。该 label MUST 与 [`media-service-binding.md` §3.1](./media-service-binding.md) 媒体签名 domain label 分离表登记的常量逐字节一致，且 MUST 区别于 `ak.media.participant_binding.v1`——这把 ICE config 签名与 participant binding 签名隔离，防止同一 issuer key 的签名被跨用途重解释。任何 media service MUST 按此构造，任何客户端 MUST 按此验签；实现 MUST NOT 引入私有 domain 前缀，也 MUST NOT 复用 participant_binding label。
  - 固定 label 与 payload digest 都是 verifier 的内部确定性输入，不是 `signature` 的 wire 成员。Verifier MUST 固定使用 `ak.media.ice_config.v1`，并从去除顶层 `signature` 后的权威对象重算 canonical JSON 与 SHA-256 诊断摘要；不得接受 caller 提供的 label、digest 回声或用其替代上述签名字节重算。
- 客户端 MUST 尊重 `ttl_seconds`，过期后重新获取。
- 高隐私 Realm MAY 设置 `turn_required=true`，禁止 host/srflx candidate 泄露本地或公网 IP。

### 4.2 In-call Credential Refresh

通话进行中 TURN credential 可能在 `ttl_seconds` 之前到期或被 server 主动撤销。客户端 MUST 实现在通话期间的 credential refresh，避免 mid-call 失联：

| 触发条件 | 客户端行为 |
| --- | --- |
| 当前剩余有效期 ≤ `max(ttl_seconds * 0.25, refresh_lead_seconds)`（响应中携带的 `refresh_lead_seconds` 为权威阈值；由于 §4.1 规定 `refresh_lead_seconds < ttl_seconds`，该阈值始终在 TTL 窗口内，不会触发签发即刷新的风暴) | 在不中断通话的情况下重新调用 ICE config endpoint，获取新一组 `ice_servers[]` 与 credential。 |
| ICE agent 报告 TURN allocation refresh 失败、收到 `441 Wrong Credentials`、`438 Stale Nonce` 或等价错误 | 立即调用 ICE config endpoint，并对受影响 candidate 触发 ICE restart（`signaling.payload.signal_kind = renegotiate`）。 |
| ICE config endpoint 返回 `turn_credential_expired` | 客户端按服务器返回的 `next_retry_at` / `Retry-After` 退避；超过 30 秒仍无新 credential 时通过 `ak.call.signal` 发出 `error` payload 并以 graceful hangup 收尾。 |

新 credential 应用规则：

- 客户端 MUST 在新 credential 生效后 **保留旧 allocation 直到所有现有 RTP 会话迁移完成**，然后再 `CREATE-PERMISSION` 释放旧通道；不得在 candidate 切换中途让媒体丢包。
- 多对多会议中，客户端 MUST 周期检查 `ttl_seconds`（默认每 30 秒），不得依赖单一 timer。
- Refresh 流程不重放 user-facing UI 提示；通话状态保持 `active`。
- Refresh 请求 MUST 与原 ICE config 请求一致地携带 per-call pairwise pseudonym（同一通话内 pseudonym 可保持不变，避免 TURN 运营方误判为不同呼叫）。

服务端规则：

- ICE config endpoint MUST 在响应中携带 `refresh_lead_seconds`（推荐 60、可调），且 MUST 保证 `refresh_lead_seconds < ttl_seconds`，让客户端按统一节奏 refresh。当 `ttl_seconds` 较小(如 60s 下限)以致无法同时满足推荐 floor 60s 与 `refresh_lead_seconds < ttl_seconds` 时，`refresh_lead_seconds < ttl_seconds` 优先，服务端 MUST 选取更小的 lead 值。
- TURN shared secret MUST 周期轮换（默认 ≤ 24 小时）；轮换时 server MUST 同时接受新旧 secret 一段时间（grace ≥ `ttl_seconds`）以避免 in-call 集体失败。
- `turn_credential_expired` 响应 MUST 包含 `next_retry_at`；不得让客户端进入 tight retry loop。

## 5. Signaling Envelope

所有 call signaling frame 使用 [`SignalEnvelope`](../sync/signal.md)，外层只允许
`signal_class` 三值分类。`call_id`、`signal_kind`、sequence、SDP、ICE candidate 与媒体状态
全部位于 `encrypted_payload` 内；服务端不得看见或按它们路由。`invite` 等需要唤醒的 frame
使用 `signal_class=setup`，moderation frame 使用 `moderation`，其余使用 `session`。

接收方 MUST 在 ringing、candidate application 或任何副作用之前验证外层 device proof、
RealmCommit basis、scope/MLS epoch 与 AAD，然后解密并检查 plaintext sequence 在
`(realm_id, call_id, actor_id, device_id)` 上单调递增。失败、过期、重放、未知 signal kind
或被吊销设备的 frame 必须 fail closed。规范外层 schema 是
[`signal-envelope.schema.json`](../../artifacts/schemas/signal-envelope.schema.json)；
proof context 固定为 `ak.signal_proof.v1`。

解密后的 plaintext 顶层必须通过 [`call-signal-plaintext.schema.json`](../../artifacts/schemas/call-signal-plaintext.schema.json)（`ak.schema.call_signal_plaintext.v1`），闭合字段为 `kind=ak.call.signal`、
`payload_sequence`、`call_id`、`signal_kind`、`seq` 与 `data`。`payload_sequence` 是
[`../sync/signal.md` §1.1](../sync/signal.md) 对全部 plaintext profile 强制的通用字段，按
完整 sender Actor、device 与 signed scope 单调，服务于 §2 的 `(sender_actor_id, sender_device_id, canonical scope_ref,
payload_sequence)` 去重；它与本节按 `(realm_id, call_id, actor_id, device_id)` 防回滚的
`seq` 相互独立，任一方 MUST NOT 替代另一方。允许的 `signal_kind` 为 `invite` / `answer` /
`candidate` / `reject` / `hangup` / `renegotiate` / `mute_state` / `media_state` /
`speaking` / `focus_join` / `focus_leave` / `moderation` / `error` / `ack`。

## 6. 一对一通话

以下示例给出解密后的 `ak.call.signal` plaintext 对象；外层加密形态见 §5。

Invite payload:

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 30,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "invite",
  "seq": 12,
  "data": {
    "lifetime_ms": 60000,
    "offer": {
      "type": "offer",
      "sdp": "v=0\r\n..."
    },
    "media": {
      "audio": true,
      "video": true,
      "screen": false
    }
  }
}
```

Answer payload:

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 31,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "answer",
  "seq": 13,
  "data": {
    "answer": {
      "type": "answer",
      "sdp": "v=0\r\n..."
    },
    "accepted_media": {
      "audio": true,
      "video": true
    }
  }
}
```

Candidate payload:

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 32,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "candidate",
  "seq": 14,
  "data": {
    "candidates": [
      {
        "candidate": "candidate:...",
        "sdp_mid": "0",
        "sdp_m_line_index": 0
      }
    ]
  }
}
```

字段名在 Arkret envelope 中使用 snake_case；浏览器原生 `sdpMid` / `sdpMLineIndex` MUST 映射为 `sdp_mid` / `sdp_m_line_index`。

### 6.1 通话内状态信令（renegotiate / mute_state / speaking）

以下信令的 `payload` 外层形态同 §5；`payload.data` 形态如下。它们同时适用于一对一与多方场景；`mute_state` / `speaking` 在多方 SFU 会议中按 §5 的 `seq` 单调性逐 `(realm_id, call_id, actor_id, device_id)` 防回滚。

`renegotiate` payload —— 媒体协商变更（增删轨道、编解码变更、ICE restart）。一帧 MUST 仅携带 `offer` 与 `answer` 之一：发起侧帧带 `offer`，应答侧帧带 `answer`。

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 40,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "renegotiate",
  "seq": 20,
  "data": {
    "reason": "add_track",
    "ice_restart": false,
    "offer": {
      "type": "offer",
      "sdp": "v=0\r\n..."
    },
    "media": {
      "audio": true,
      "video": true,
      "screen": false
    }
  }
}
```

- `reason` MUST 为 `add_track` / `remove_track` / `codec_change` / `ice_restart` 之一。
- `ice_restart=true` 时 MUST 触发 ICE restart（见 §4.2 凭证刷新触发）；此时 `offer` / `answer` 中的 SDP MUST 携带新的 ICE ufrag/pwd。
- `media` optional，反映本帧后发送侧期望的媒体轨道集合。

`mute_state` payload —— 音频/视频静音状态变更。

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 41,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "mute_state",
  "seq": 21,
  "data": {
    "audio_muted": true,
    "video_muted": false,
    "by": "self"
  }
}
```

- `audio_muted` / `video_muted` 为 boolean，required。
- `by` MUST 为 `self` 或 `moderator`。`by=moderator` MUST 由具备 `ak.call.moderate`（§3）的 actor 发出，并 MUST 携带 `target_actor_id` 与 `target_device_id` 指明被静音方；同一主持操作还 MUST 写入 durable `ak.call.state.mute_override`，并由 SFU / token issuer 收紧该 call leg 的 audio/video send permission。被静音客户端收到后 MUST 本地强制静音并向用户显示来源；若客户端拒不配合，服务端媒体权限仍必须阻断其继续推送被静音 track。`by=self` 时 MUST NOT 携带 `target_*` 字段，且不写 `mute_override`。

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 42,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "mute_state",
  "seq": 22,
  "data": {
    "audio_muted": true,
    "video_muted": true,
    "by": "moderator",
    "target_actor_id": "ak:did_core:webvh:zHuXvTbhiRsj2KEPE64TLhzG4",
    "target_device_id": "ak:device:01964137-0000-7000-8000-000000000000"
  }
}
```

`speaking` payload —— voice activity 指示，高频、best-effort。接收方 MAY 丢弃乱序/过期帧而不报错。

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 43,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "speaking",
  "seq": 23,
  "data": {
    "speaking": true,
    "audio_level": 0.42
  }
}
```

- `speaking` 为 boolean，required。
- `audio_level` optional，归一化 RMS（`0.0`–`1.0`）；不得携带原始音频样本或可重建语音内容的数据。
- `speaking` 帧 SHOULD 限频（建议 ≤ 5 帧/秒），且 MUST NOT 触发 push 唤醒。

## 7. 多设备冲突处理

同一 actor 的多个设备 MAY 同时收到 invite。

规则：

- `answer` signaling frame 只是候选应答，不是 winner 真相。winner 必须由接收方的 call admission 接受一条 durable `ak.call.state.roster_delta.op="join"` 后才成立。P2P / mesh 候选不取得 `participant_binding`；SFU / MCU 的每个候选设备 MAY 在提交 join 前兑换短期 `participant_binding` 与 media token，winner 仍由首条 accepted roster join 确立。非 winner 的 binding / token MUST 由 issuer 立即撤销，或在不超过 `ring_timeout_ms`（[`call-state.md` §5](./call-state.md) 的登记常量，默认且最大 60,000 ms）的短 TTL 后失效，不得据此进入 media roster。
- Admission service MUST 按 `(call_id, actor_id)` 串行化 accepted participant entry：若当前 accepted call roster effective authority-ordered keyed set 已存在同一 actor 的 active call leg，后续 answer MUST 拒绝 `call_already_answered`，并要求该设备停止响铃。
- 若同一 actor 的多个设备基于同一 prior call-state basis 并发 answer，reducer / admission service MUST 使用确定性 tiebreak，而不是本地接收顺序：按 `(device_id, proof.event_digest)` 字典序最小的候选成为唯一 winner；其它候选返回 `call_already_answered` 或发送 `reject{reason="call_already_answered"}`。该 tiebreak 只处理真正并发 sibling；非并发场景仍由已 accepted durable participant entry 吸收后续请求。
- 发起端、其它接收端与 SFU MUST 以 accepted `call_roster` effective authority-ordered keyed set 中的 participant entry 为权威，停止同 actor 其它设备的 ringing / offer-answer 流程；它们 MUST NOT 因先收到某个通过签名验证的 answer 就本地承认 winner。
- 被拒绝或超时的设备 SHOULD 发送 `reject`，reason 为 `call_already_answered` 或 `timeout`，但拒绝帧本身不改变 durable winner。

## 8. 屏幕共享

屏幕共享是一种独立 media source：

```json
{
  "kind": "ak.call.signal",
  "payload_sequence": 50,
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "signal_kind": "media_state",
  "seq": 7,
  "data": {
    "screen": {
      "enabled": true,
      "source_id": "screen_01",
      "with_audio": false
    }
  }
}
```

规则：

- 需要 `ak.call.screen_share` capability。
- 客户端 MUST 在本地展示正在共享状态。
- 会议主持人 MAY 使用 `ak.call.moderate` 请求停止某人的 screen share。

## 9. 推送集成

`ak.call.signal` 中 `signal_kind=invite` SHOULD 触发 VoIP push。push 必须遵循 [`crypto-media/device-lifecycle.md` §5.6 Privacy-Preserving Push](./device-lifecycle.md) 的 pairwise pseudonym 规则；不得在投递给 APNs / FCM / Push Gateway 的 payload 中携带 principal DID、device verification-method DID URL、Realm id、call id 或 sender DID。

脱敏 push payload（推送上游可见部分）:

```json
{
  "notification": {
    "push_target_id": "ak:pseudonym:push:lg8aqJ2eJjms1GQpkzloxGn8F802f8RfmfmfsC85eRo",
    "wakeup_kind": "call_invite",
    "push_hint": "incoming_call"
  }
}
```

设备本地 OS 收到唤醒后，App 拉起 P2P / Sync 通道，使用本地密钥解密 `ak.call.signal{signal_kind=invite}` envelope，从签名 envelope 中获得真实 `realm_id`、`call_id`、`sender_actor_id` 等字段并展示来电 UI。Push 上游永远看不到这些字段。

Push payload MUST NOT 包含 SDP、ICE candidate、TURN credential、principal DID、Realm id、call id 或明文会议标题；provider-facing body 的唯一权威形态是 [`discovery/push-notifications.md` §5.1](../discovery/push-notifications.md) 的 blind notification。WebRTC call invite 只允许使用 `notification.push_target_id`、`notification.wakeup_kind`、可选 `notification.push_hint="incoming_call"` 以及该节允许的本地化 / 计数字段；不得携带 `urgency`、`expires_at` 或任何未登记字段。其它一切信息必须通过本地解密获得。

**Push wakeup 与 invite lifetime（normative）**: VoIP push wakeup 仅传 "incoming call" 信号，不携带 invite envelope；客户端唤醒后 MUST fresh fetch 当前 invite envelope。若本地 invite 已过期（超出 `lifetime_ms` = 60s 默认），客户端 MUST 拒绝复用 envelope，触发新的 `ak.call.signal{signal_kind=invite}` 邀请流程。push wakeup 自身的 TTL（默认 24h）与 invite signaling lifetime 是不同语义，不构成死锁。

## 10. 安全与隐私

实现 MUST：

- 验证所有 signaling sender 的 membership 和 device validity。
- 防止 replay、sequence rollback 和 stale invite。
- 对 TURN credential 使用短期凭证。
- 对高隐私 Realm 支持 `turn_required`。
- 不把 SDP / ICE candidate 写入 durable public event。
- 对 SFU/MCU/recording service 使用 service DID 和 policy allowlist。
- 在 E2EE 降级、MCU 混流、录制、外部 PSTN bridge 时显示明确提示。

实现 SHOULD：

- 支持 IP 泄露最小化 profile。
- 支持 bandwidth / resolution policy。
- 对会议服务做 region / data residency 限制。
- 对呼叫滥用做 rate limit 和 block。

## 11. 错误码

| code | 含义 |
| --- | --- |
| `call_not_found` | call id 不存在或不可见。 |
| `call_expired` | invite 或 call 已过期。 |
| `call_already_answered` | 其他设备已经接听。 |
| `media_permission_denied` | 缺少 video/audio/screen/record 权限。 |
| `ice_config_denied` | 无权获取 ICE 配置。 |
| `turn_credential_expired` | TURN credential 已过期。 |
| `sfu_not_allowed` | Realm policy 不允许该 SFU。 |
| `e2ee_required` | Realm 要求 E2EE，但当前媒体路径不满足。 |
| `recording_denied` | 录制未授权或 policy 禁止。 |
| `transcription_denied` | 转写未授权或 policy 禁止(见 [`call-state.md` §5.1](./call-state.md))。 |
| `recording_consent_required` | 进入录制 / 转写捕获态但缺少客户端二次确认(见 [`call-state.md` §5.2](./call-state.md))。 |
| `call_moderation_unauthorised` | 主持动作(kick / ban / end-for-all / force-mute)由不具 `ak.call.moderate` 的 actor 发起(见 §3a)。 |
| `call_participant_removed` | 被 kick / ban 的参与者尝试重新建立 media leg 或重新兑换 join token(见 §3a)。 |
| `call_summary_invalid` | `ak.call.summary` 的 `final_state` 非终态、无终态 `ak.call.state` head，或与已存在摘要分叉(见 [`call-state.md` §7](./call-state.md))。 |
| `session_focus_already_committed` | 已提交的 call `session_focus` 不可在同一生命周期内改写。 |
| `call_state_terminal` | `ak.call.state` 不能从 `ended` / `missed` / `failed` / `cancelled` 终态转出。 |

媒体服务绑定相关错误码（`unknown_focus_type`、`focus_mismatch`、`token_issuer_unauthorised`、`participant_binding_invalid`、`participant_id_unrecognised`、`e2ee_key_source_unauthorised`、`recording_artifact_pipeline_bypassed`、`media_service_foci_required`、`media_service_binding_uncovered`、`focus_unavailable_for_client`、`media_plaintext_service_not_authorised`、`mls_governance_binding_stale` 等）见 [`media-service-binding.md`](./media-service-binding.md) 与 `error-code-registry.json`。

## 12. 与 Matrix Call 的关系

Arkret 借鉴 Matrix call event、VoIP push、group call / SFU 方向，但采用自己的 Realm、capability、device trust 和 transport binding 模型。

Matrix 风格的 call invite/answer/candidates 可通过 Applet/bridge 映射为 `ak.call.signal`，但 durable meeting state、recording artifact 和 Realm policy 必须遵守 Arkret 规则。
