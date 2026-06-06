---
title: WebRTC Calls and Meetings
status: candidate
normative: true
stability: v1
updated: 2026-06-04
sidebar:
  label: WebRTC Calls
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Cokret 支持音频通话、视频通话、屏幕共享和多人会议。实时媒体本身不进入 Realm Event history；信令、会议状态、邀请、参与者变化、录制引用和通话摘要按不同持久性处理。

本文件定义 **ephemeral 信令与 WebRTC 传输面**：

- 一对一 WebRTC P2P 通话
- TURN / STUN / ICE server 动态发现与 in-call 凭证刷新
- 信令 envelope（offer/answer/candidate/renegotiate 等）、多设备冲突处理
- 屏幕共享、推送集成、信令层安全与隐私

相邻规范：

- 媒体服务发现、token / participant binding 兑换、focus 选举、SFU 权限、媒体 E2EE 帧密钥注入与治理绑定，见 [`media-service-binding.md`](./media-service-binding.md)。
- 通话模型与状态机、durable `ck.call.state` 字段语义、录制 / 转写生命周期，见 [`call-state.md`](./call-state.md)。

## 2. 设计原则

### 2.1 信令是 Ephemeral

Offer、Answer、ICE candidate、renegotiation、speaking update 等高频信令 SHOULD 通过 Sync Service 的 Ephemeral Channel 或等价 streaming transport 发送。

通话摘要、会议实体、录制 artifact、会议权限变化 MAY 作为 Durable Event 写入 Realm Event history。

### 2.2 信令必须认证和加密

WebRTC 信令会暴露设备、网络和媒体能力。所有信令 MUST：

- 绑定 Realm id、call id、device id、actor id。
- 由发送设备签名，或封装在已认证的 encrypted ephemeral channel。
- 对同一 Realm / DM 的授权成员端到端加密。
- 防重放，至少包含 timestamp、sequence 或 frame id。

### 2.3 媒体路径不等于信任路径

媒体可能经过 TURN、SFU 或 MCU。它们可以转发包或混流，但不得因此获得 Realm 权限。媒体服务 MUST 有 service DID，并由 Realm policy 显式允许。

## 3. 权限模型

标准 actions（canonical 命名以 capability registry / `contract-catalog.json` 为唯一真源；正文与实现 MUST 使用带 `ck.` 前缀的形态，MUST NOT 接受裸 `call.*` 名）：

- `ck.call.join` —— 加入并发起 call。v1 不注册独立的 `call.start`：call 的发起由首个具备 `ck.call.join` 的 actor 写入首个 `ck.call.state` 完成。
- `ck.call.signal.send` —— 发送 call signaling frame，含邀请（`ck.call.signal{kind=invite}`）。v1 不注册独立的 `call.invite`，邀请通过该 signaling action 表达。
- `ck.call.screen_share`
- `ck.call.record`
- `ck.call.transcribe`
- `ck.call.moderate` —— 主持 / 管理操作，含对全体结束 call。v1 不注册独立的 `call.end_for_all`，end-for-all 由 `ck.call.moderate` 授权。
- `ck.realm.media_service`

默认规则：

- Realm 成员不自动拥有 `ck.call.record`。
- `ck.call.screen_share` SHOULD 独立授权。
- `ck.realm.media_service` 只应授予管理员或受信服务。
- Actor 加入 call 的资格 MUST 按分层 predicate 校验，不得依赖泛化口语状态（如笼统的「被 ban / suspended」）：(a) 在目标 `realm_id` 的 Realm membership 必须为 `join`；(b) 若 call scoped 到某 Circle，该 actor 还必须是该 Circle 的活跃成员；(c) account lifecycle status MUST NOT 为 `suspended` / `deactivated` / `erasure_pending`；(d) 发起设备的 device grant MUST NOT 被 revoked，且其 `ck.call.join` capability grant 未被 revoke。任一条不满足 MUST NOT 加入。
- 外部 guest 加入必须通过 invite 或 meeting-specific guest grant。

## 4. ICE Server Discovery

客户端通过 Realm policy、service discovery 或 media service 获取 ICE servers。媒体服务本身的 multi-focus 声明（`ck.realm.media_service`）见 [`media-service-binding.md` §2](./media-service-binding.md)。

### 4.1 ICE Config Endpoint

默认 HTTP binding：

```http
POST /_cokret/self/rtc/ice-config
Authorization: Bearer <token>
Content-Type: application/json
```

请求 schema 见 [`media-operations.schema.json#/$defs/ice_config_request`](../../artifacts/schemas/media-operations.schema.json)。字段语义如下：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 调用者认证，MUST 绑定 `actor_id` 与 `device_id`。 |
| `realm_id` | body | `id` | required | 通话所在 Realm。 |
| `call_id` | body | `id` | required | 通话 ID。 |
| `actor_id` | body | `did` | required | 请求 ICE 配置的 Actor。 |
| `device_id` | body | `id` | required | 请求设备。 |
| `mode` | body | `enum(p2p,sfu,turn)` | required | 请求媒体模式。 |

请求示例（非完整 schema）：

```json
{
  "realm_id": "ck:realm:...",
  "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:...",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "mode": "p2p"
}
```

响应字段（schema 见 [`ice-config-response.schema.json`](../../artifacts/schemas/ice-config-response.schema.json)，schema id `ck.schema.ice_config_response.v1`）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `realm_id` | `id` | required | 回显请求 Realm，进入签名 canonical bytes，防止跨 Realm 重放。 |
| `call_id` | `id` | required | 回显请求 call，进入签名 canonical bytes，防止跨通话重放。 |
| `actor_id` | `did` | required | 回显请求 actor，进入签名 canonical bytes。 |
| `device_id` | `id` | required | 回显请求设备，进入签名 canonical bytes。 |
| `ttl_seconds` | `int` | required | ICE 配置有效期（秒）。建议 ≤ 1 小时。 |
| `refresh_lead_seconds` | `int` | required | 客户端在剩余有效期 ≤ 此值时 SHOULD 提前刷新；建议 `ttl_seconds / 4`。schema 合法范围为 `minimum=10`、`maximum=1800`。**服务端 MUST 保证 `refresh_lead_seconds` 严格小于 `ttl_seconds`**（否则客户端在签发瞬间即判定 credential 需刷新，陷入刷新风暴)。推荐 floor 60s 仅在 `60 < ttl_seconds` 时适用，否则 `refresh_lead_seconds < ttl_seconds` 优先于推荐 floor（floor 让位的完整论证与取值规则见 §4.2 服务端规则）。让所有客户端按统一节奏 refresh，server 也据此设计 secret rotation grace 窗口。 |
| `issued_at` | `timestamp` | required | 服务端签发时间，进入签名 canonical bytes。 |
| `issued_at_bucket` | `timestamp` | required | TURN pseudonym 派生的粗粒度 bucket 起点；MUST 等于 `floor(issued_at / bucket_seconds) * bucket_seconds`，进入签名 canonical bytes。 |
| `bucket_seconds` | `int` | required | v1 固定为 `300` 秒；客户端 SHOULD 在跨越下一 bucket 前 refresh。 |
| `expires_at` | `timestamp` | optional | 等于 `issued_at + ttl_seconds`；冗余字段，便于客户端判定。 |
| `ice_servers` | `object[]` | required | STUN/TURN server 配置数组。 |
| `ice_servers[].urls` | `string[]` | required | STUN/TURN URL。 |
| `ice_servers[].username` | `string` | TURN 时 required | TURN 用户名（per-call pairwise pseudonym，REST-style: `<expiry-unix>:<pseudonym>`）。 |
| `ice_servers[].credential` | `string` | TURN 时 required | 短期 TURN credential（HMAC-SHA256 of username）。 |
| `ice_servers[].credential_type` | `string` | optional | credential 类型，例如 `password`。 |
| `force_turn` | `boolean` | optional | 是否强制 TURN（高隐私 Realm）。 |
| `constraints` | `object` | optional | 候选地址与传输策略（`allow_udp` / `allow_tcp` / `allow_ipv6`）。 |
| `next_retry_at` | `timestamp` | optional | 软失败（如 `turn_credential_expired`）时返回；客户端 MUST NOT 在此前重试。 |
| `signature` | `signature` | required | Media Service DID 对 canonical bytes（去除 `signature` 自身）的 detached 签名。 |

响应示例（非完整 schema）：

```json
{
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "call_id": "ck:call:0196419c-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "ttl_seconds": 600,
  "refresh_lead_seconds": 60,
  "issued_at": "2026-04-26T00:00:00Z",
  "issued_at_bucket": "2026-04-26T00:00:00Z",
  "bucket_seconds": 300,
  "ice_servers": [
    {
      "urls": ["stun:stun.example.com:3478"]
    },
    {
      "urls": ["turns:turn.example.com:5349?transport=tcp"],
      "username": "1699999999:ck_pseudonym_call_4f7c3b2a9e1d5a6f",
      "credential": "base64url...",
      "credential_type": "password"
    }
  ],
  "force_turn": false,
  "constraints": {
    "allow_udp": true,
    "allow_tcp": true,
    "allow_ipv6": true
  },
  "signature": {
    "alg": "EdDSA",
    "kid": "did:web:media.example.com#key-1",
    "sig": "base64url..."
  }
}
```

要求：

- TURN credential MUST 短期有效，SHOULD 使用 REST-style ephemeral credential（draft-uberti-rtcweb-turn-rest-00 风格 username = `<expiry-unix>:<pairwise-pseudonym>`，password = `HMAC-SHA256(turn_shared_secret, username)`；实现不得降级为 HMAC-SHA1）。
- TURN `username` 中的"身份段" MUST 是 **per-call pairwise pseudonym**（建议形态 `ck_pseudonym_call_<random>` 或等价 random tag）。它不得是 principal DID、handle、邮箱或可跨呼叫关联的稳定 ID；该不可关联性只针对 TURN 运营方成立，不对铸造 pseudonym 的 Cokret media service 成立。
- Pseudonym 生成 MUST 使用每次通话的新随机种子或 media service 私有密钥派生，且至少绑定 `(realm_id, call_id, actor_id, device_id, issued_at_bucket, media_service_did)`；推荐：

  ```text
  pseudonym = "ck_pseudonym_call_" ||
    base64url(HMAC-SHA256(media_service_pseudonym_secret,
      canonical_json({realm_id, call_id, actor_id, device_id, issued_at_bucket, nonce})
    )[0:16])
  ```

  `nonce` MUST 对每个 `(call_id, actor_id, device_id)` fresh，media service MUST 在签名 ICE config 的内部审计记录中保留 nonce freshness evidence，且不得把 nonce 或其稳定派生值写入 TURN username 之外的可跨 Realm 关联字段。Refresh 时同一 active call leg MAY 复用 pseudonym 以避免 TURN 误判为不同会话，但新 call、new device leg、超过 `ttl_seconds + refresh grace` 的恢复、或 policy 要求匿名重置时 MUST 生成新 pseudonym。Pseudonym 不得仅由稳定 ID 确定性派生。
- ICE config response MUST 由 media service 签名，签名 canonical bytes MUST 覆盖 `realm_id`、`call_id`、`actor_id`、`device_id`、`issued_at`、`issued_at_bucket`、`bucket_seconds`、`ttl_seconds`、`ice_servers[]` 与策略字段；TLS + service DID 绑定只能认证通道，不能替代响应对象签名。
- 客户端 MUST 尊重 `ttl_seconds`，过期后重新获取。
- 高隐私 Realm MAY 设置 `force_turn=true`，禁止 host/srflx candidate 泄露本地或公网 IP。

### 4.2 In-call Credential Refresh

通话进行中 TURN credential 可能在 `ttl_seconds` 之前到期或被 server 主动撤销。客户端 MUST 实现在通话期间的 credential refresh，避免 mid-call 失联：

| 触发条件 | 客户端行为 |
| --- | --- |
| 当前剩余有效期 ≤ `max(ttl_seconds * 0.25, refresh_lead_seconds)`（响应中携带的 `refresh_lead_seconds` 为权威阈值；由于 §4.1 规定 `refresh_lead_seconds < ttl_seconds`，该阈值始终在 TTL 窗口内，不会触发签发即刷新的风暴) | 在不中断通话的情况下重新调用 ICE config endpoint，获取新一组 `ice_servers[]` 与 credential。 |
| ICE agent 报告 TURN allocation refresh 失败、收到 `441 Wrong Credentials`、`438 Stale Nonce` 或等价错误 | 立即调用 ICE config endpoint，并对受影响 candidate 触发 ICE restart（`signaling.payload.signal_type = renegotiate`）。 |
| ICE config endpoint 返回 `turn_credential_expired` | 客户端按服务器返回的 `next_retry_at` / `Retry-After` 退避；超过 30 秒仍无新 credential 时通过 `ck.call.signal` 发出 `error` payload 并以 graceful hangup 收尾。 |

新 credential 应用规则：

- 客户端 MUST 在新 credential 生效后 **保留旧 allocation 直到所有现有 RTP 会话迁移完成**，然后再 `CREATE-PERMISSION` 释放旧通道；不得在 candidate 切换中途让媒体丢包。
- 多对多会议中，客户端 MUST 周期检查 `ttl_seconds`（默认每 30 秒），不得依赖单一 timer。
- Refresh 流程不重放 user-facing UI 提示；通话状态保持 `active`。
- Refresh 请求 MUST 与原 ICE config 请求一致地携带 per-call pairwise pseudonym（同一通话内 pseudonym 可保持不变，避免 TURN 运营方误判为不同呼叫）。

服务端规则：

- ICE config endpoint MUST 在响应中携带 `refresh_lead_seconds`（推荐 60、可调），且 MUST 保证 `refresh_lead_seconds < ttl_seconds`，让客户端按统一节奏 refresh。当 `ttl_seconds` 较小(如 60s 下限)以致无法同时满足推荐 floor 60s 与 `refresh_lead_seconds < ttl_seconds` 时,`refresh_lead_seconds < ttl_seconds` 优先，服务端 MUST 选取更小的 lead 值。
- TURN shared secret MUST 周期轮换（默认 ≤ 24 小时）；轮换时 server MUST 同时接受新旧 secret 一段时间（grace ≥ `ttl_seconds`）以避免 in-call 集体失败。
- `turn_credential_expired` 响应 MUST 包含 `next_retry_at`；不得让客户端进入 tight retry loop。

## 5. Signaling Envelope

所有 call signaling frame 使用 `ck.schema.ephemeral_envelope.v1` 的 broadcast envelope；`ck.call.signal` 分支 MUST 携带 `device_id` 与 `proof`，并在 `payload` 中携带 call 级字段：

```json schema=schemas/ephemeral-envelope.schema.json
{
  "kind": "ck.call.signal",
  "realm_id": "ck:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "sent_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:00:30Z",
  "payload": {
    "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
    "signal_type": "invite",
    "seq": 12,
    "data": {}
  },
  "proof": {}
}
```

Receiver MUST verify `proof` over the canonical envelope bytes (excluding `proof`) before surfacing ringing UI, and MUST reject replay / rollback using monotonically increasing `payload.seq` per `(realm_id, payload.call_id, actor_id, device_id)`.

`payload.signal_type`：

- `invite`
- `answer`
- `candidate`
- `reject`
- `hangup`
- `renegotiate`
- `mute_state`
- `media_state`
- `speaking`
- `focus_join`
- `focus_leave`
- `error`
- `ack`

## 6. 一对一通话

以下示例给出 `ck.call.signal` 信令的 `payload` 对象（外层 ephemeral envelope 形态见 §5；`payload` 的封闭字段为 `call_id` / `signal_type` / `seq` / `data`，信令种类由 `payload.signal_type` 选择，取值见 §5）。

Invite payload:

```json
{
  "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
  "signal_type": "invite",
  "seq": 12,
  "data": {
    "lifetime_ms": 60000,
    "mode": "p2p",
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
  "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
  "signal_type": "answer",
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
  "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
  "signal_type": "candidate",
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

字段名在 Cokret envelope 中使用 snake_case；浏览器原生 `sdpMid` / `sdpMLineIndex` MUST 映射为 `sdp_mid` / `sdp_m_line_index`。

## 7. 多设备冲突处理

同一 actor 的多个设备 MAY 同时收到 invite。

规则：

- 首个 accepted answer 赢得 call leg。
- 其他设备收到同 actor 的 accepted answer 后 MUST 停止响铃。
- 发起端收到同 actor 多个 answer 时，只接受第一个通过签名和 device validity 验证的 answer。
- 被拒绝或超时的设备 SHOULD 发送 `reject`，reason 为 `answered_elsewhere` 或 `timeout`。

## 8. 屏幕共享

屏幕共享是一种独立 media source：

```json
{
  "kind": "ck.call.signal",
  "payload": {
    "call_id": "ck:call:...",
    "signal_type": "media_state",
    "seq": 7,
    "data": {
      "screen": {
        "enabled": true,
        "source_id": "screen_01",
        "with_audio": false
      }
    }
  }
}
```

规则：

- 需要 `ck.call.screen_share` capability。
- 客户端 MUST 在本地展示正在共享状态。
- 会议主持人 MAY 使用 `ck.call.moderate` 请求停止某人的 screen share。

## 9. 推送集成

`ck.call.signal` 中 `signal_type=invite` SHOULD 触发 VoIP push。push 必须遵循 [`crypto-media/device-lifecycle.md` §5a Privacy-Preserving Push](./device-lifecycle.md) 的 pairwise pseudonym 规则；不得在投递给 APNs / FCM / Push Gateway 的 payload 中携带 principal DID、device DID URL、Realm id、call id 或 sender DID。

脱敏 push payload（推送上游可见部分）:

```json
{
  "push_target_id": "ck:pseudonym:push:01js0pu0000000000000000000",
  "wakeup_kind": "call_invite",
  "urgency": "urgent",
  "expires_at": "2026-04-26T00:01:00Z"
}
```

设备本地 OS 收到唤醒后，App 拉起 P2P / Sync 通道，使用本地密钥解密 `ck.call.signal{signal_type=invite}` envelope，从签名 envelope 中获得真实 `realm_id`、`call_id`、`sender_actor_id` 等字段并展示来电 UI。Push 上游永远看不到这些字段。

Push payload MUST NOT 包含 SDP、ICE candidate、TURN credential、principal DID、Realm id、call id 或明文会议标题；只允许 §9 上面 4 个脱敏字段，其它一切信息必须通过本地解密获得。

**Push wakeup 与 invite lifetime（normative）**: VoIP push wakeup 仅传 "incoming call" 信号，不携带 invite envelope；客户端唤醒后 MUST fresh fetch 当前 invite envelope。若本地 invite 已过期（超出 `lifetime_ms` = 60s 默认），客户端 MUST 拒绝复用 envelope，触发新的 `ck.call.signal{signal_type=invite}` 邀请流程。push wakeup 自身的 TTL（默认 24h）与 invite signaling lifetime 是不同语义，不构成死锁。

## 10. 安全与隐私

实现 MUST：

- 验证所有 signaling sender 的 membership 和 device validity。
- 防止 replay、sequence rollback 和 stale invite。
- 对 TURN credential 使用短期凭证。
- 对高隐私 Realm 支持 `force_turn`。
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

媒体服务绑定相关错误码（`unknown_focus_type`、`focus_mismatch`、`token_issuer_unauthorised`、`participant_identity_unrecognised`、`e2ee_key_source_unauthorised`、`media_plaintext_service_not_authorised`、`mls_governance_binding_stale` 等）见 [`media-service-binding.md`](./media-service-binding.md) 与 `error-code-registry.json`。

## 12. 与 Matrix Call 的关系

Cokret 借鉴 Matrix call event、VoIP push、group call / SFU 方向，但采用自己的 Realm、capability、device trust、Policy Server 和 transport binding 模型。

Matrix 风格的 call invite/answer/candidates 可通过 Applet/bridge 映射为 `ck.call.signal`，但 durable meeting state、recording artifact 和 Realm policy 必须遵守 Cokret 规则。
