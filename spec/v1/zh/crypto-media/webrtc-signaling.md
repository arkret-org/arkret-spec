---
title: WebRTC Calls and Meetings
sidebar:
  label: WebRTC Calls
---

## 1. 目标

Contrix 支持音频通话、视频通话、屏幕共享和多人会议。实时媒体本身不进入 Space Event history；信令、会议状态、邀请、参与者变化、录制引用和通话摘要按不同持久性处理。

本文件定义：

- 一对一 WebRTC P2P 通话
- 多方会议的 Mesh / SFU / MCU 模式
- TURN / STUN / ICE server 动态发现
- 会议 membership、权限、E2EE、push、recording 和审计边界
- 信令事件、会议状态事件和服务发现

## 2. 设计原则

### 2.1 信令是 Ephemeral

Offer、Answer、ICE candidate、renegotiation、speaking update 等高频信令 SHOULD 通过 Sync Service 的 Ephemeral Channel 或等价 streaming transport 发送。

通话摘要、会议实体、录制 artifact、会议权限变化 MAY 作为 Durable Event 写入 Space Event history。

### 2.2 信令必须认证和加密

WebRTC 信令会暴露设备、网络和媒体能力。所有信令 MUST：

- 绑定 Space id、call id、device id、actor id。
- 由发送设备签名，或封装在已认证的 encrypted ephemeral channel。
- 对同一 Space / DM 的授权成员端到端加密。
- 防重放，至少包含 timestamp、sequence 或 frame id。

### 2.3 媒体路径不等于信任路径

媒体可能经过 TURN、SFU 或 MCU。它们可以转发包或混流，但不得因此获得 Space 权限。媒体服务 MUST 有 service DID，并由 Space policy 显式允许。

## 3. 通话模型

| 模式 | 适用 | 说明 |
| --- | --- | --- |
| `p2p` | 1 对 1 或极小规模 | 双方直接 WebRTC 连接，必要时经 TURN server。 |
| `mesh` | 3-4 人小会 | 每个客户端与其他客户端建连接，复杂度高，不建议默认。 |
| `sfu` | 多方会议默认 | Selective Forwarding Unit 转发 RTP，不解密 E2EE 内容。 |
| `mcu` | PSTN / 录制 / 低端设备 | Mixing Control Unit 混流，通常会接触明文或解密后媒体，必须强提示和审计。 |

默认多人会议 SHOULD 使用 SFU。

## 4. Call Morph

会议或通话 SHOULD 用标准 Morph 表示：

```json
{
  "morph_type": "call",
  "space_id": "cx:space:...",
  "title": "Design review",
  "fields": {
    "call_id": "cx:call:01J...",
    "mode": "sfu",
    "state": "ringing",
    "started_at": null,
    "ended_at": null,
    "recording_policy": "disabled"
  }
}
```

`state`：

- `scheduled`
- `ringing`
- `connecting`
- `active`
- `ended`
- `missed`
- `failed`
- `cancelled`

## 5. 权限模型

标准 actions：

- `call.start`
- `call.join`
- `call.invite`
- `call.moderate`
- `call.screen_share`
- `call.record`
- `call.transcribe`
- `call.end_for_all`
- `cx.call.configure_media_service`

默认规则：

- Space 成员不自动拥有 `call.record`。
- `call.screen_share` SHOULD 独立授权。
- `cx.call.configure_media_service` 只应授予管理员或受信服务。
- 被 ban / suspended 的 actor MUST NOT 加入 call。
- 外部 guest 加入必须通过 invite 或 meeting-specific guest grant。

## 6. ICE Server Discovery

客户端通过 Space policy、service discovery 或 media service 获取 ICE servers。

### 6.1 Space Media Service

```json
{
  "kind": "cx.space.media_service",
  "payload": {
    "service_id": "did:web:media.example.com",
    "modes": [
      "turn",
      "sfu"
    ],
    "ice_config_endpoint": "https://media.example.com/contrix/v1/ice-config",
    "sfu_endpoint": "https://sfu.example.com/contrix/v1",
    "allowed_call_modes": [
      "p2p",
      "sfu"
    ],
    "recording_supported": false
  }
}
```

修改该 state event 需要 `cx.call.configure_media_service` 或 `cx.policy.manage` capability。

### 6.2 ICE Config Endpoint

默认 HTTP binding：

```http
POST /contrix/v1/ice-config
Authorization: Bearer <token>
Content-Type: application/json
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `Authorization` | header | `bearer token` 或 `device proof` | required | 调用者认证，MUST 绑定 `actor_id` 与 `device_id`。 |
| `space_id` | body | `id` | required | 通话所在 Space。 |
| `call_id` | body | `id` | required | 通话 ID。 |
| `actor_id` | body | `did` | required | 请求 ICE 配置的 Actor。 |
| `device_id` | body | `id` | required | 请求设备。 |
| `mode` | body | `enum(p2p,sfu,turn)` | required | 请求媒体模式。 |

请求示例（非完整 schema）：

```json
{
  "space_id": "cx:space:...",
  "call_id": "cx:call:01J...",
  "actor_id": "did:webvh:...",
  "device_id": "cx:device:01js0ke0000000000000000000",
  "mode": "p2p"
}
```

响应字段（schema 见 [`ice-config-response.schema.json`](../../artifacts/schemas/ice-config-response.schema.json)，schema id `cx.schema.ice_config_response.v1`）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `ttl_seconds` | `int` | required | ICE 配置有效期（秒）。建议 ≤ 1 小时。 |
| `refresh_lead_seconds` | `int` | required | 客户端在剩余有效期 ≤ 此值时 SHOULD 提前刷新；建议 `ttl_seconds / 4`，下限 60s 上限 1800s。让所有客户端按统一节奏 refresh，server 也据此设计 secret rotation grace 窗口。 |
| `issued_at` | `timestamp` | required | 服务端签发时间，进入签名 canonical bytes。 |
| `expires_at` | `timestamp` | optional | 等于 `issued_at + ttl_seconds`；冗余字段，便于客户端判定。 |
| `ice_servers` | `object[]` | required | STUN/TURN server 配置数组。 |
| `ice_servers[].urls` | `string[]` | required | STUN/TURN URL。 |
| `ice_servers[].username` | `string` | TURN 时 required | TURN 用户名（per-call pairwise pseudonym，REST-style: `<expiry-unix>:<pseudonym>`）。 |
| `ice_servers[].credential` | `string` | TURN 时 required | 短期 TURN credential（HMAC of username）。 |
| `ice_servers[].credential_type` | `string` | optional | credential 类型，例如 `password`。 |
| `force_turn` | `boolean` | optional | 是否强制 TURN（高隐私 Space）。 |
| `constraints` | `object` | optional | 候选地址与传输策略（`allow_udp` / `allow_tcp` / `allow_ipv6`）。 |
| `next_retry_at` | `timestamp` | optional | 软失败（如 `turn_credential_expired`）时返回；客户端 MUST NOT 在此前重试。 |
| `signature` | `signature` | required | Media Service DID 对 canonical bytes（去除 `signature` 自身）的 detached 签名。 |

响应示例（非完整 schema）：

```json
{
  "ttl_seconds": 600,
  "ice_servers": [
    {
      "urls": ["stun:stun.example.com:3478"]
    },
    {
      "urls": ["turns:turn.example.com:5349?transport=tcp"],
      "username": "1699999999:cx_pseudonym_call_4f7c3b2a9e1d5a6f",
      "credential": "base64url...",
      "credential_type": "password"
    }
  ],
  "policy": {
    "force_turn": false,
    "allow_udp": true,
    "allow_tcp": true,
    "allow_ipv6": true
  },
  "signature": {
    "kid": "did:web:media.example.com#key-1",
    "sig": "base64url..."
  }
}
```

要求：

- TURN credential MUST 短期有效，SHOULD 使用 REST-style ephemeral credential（draft-uberti-rtcweb-turn-rest-00 风格 username = `<expiry-unix>:<pairwise-pseudonym>`，password = `HMAC(turn_shared_secret, username)`）。
- TURN `username` 中的"身份段" MUST 是 **per-call pairwise pseudonym**（建议形态 `cx_pseudonym_call_<random>` 或等价 random tag）。它不得是 principal DID、handle、邮箱或可跨呼叫关联的稳定 ID；TURN 运营方因此只能看到一次性会话标记，无法把同一用户的多次通话或多 Space 活动关联起来。
- ICE config response MUST 由 media service 签名，或通过已认证 TLS + service DID 绑定返回。
- 客户端 MUST 尊重 `ttl_seconds`，过期后重新获取。
- 高隐私 Space MAY 设置 `force_turn=true`，禁止 host/srflx candidate 泄露本地或公网 IP。

### 6.3 In-call Credential Refresh

通话进行中 TURN credential 可能在 `ttl_seconds` 之前到期或被 server 主动撤销。客户端 MUST 实现在通话期间的 credential refresh，避免 mid-call 失联：

| 触发条件 | 客户端行为 |
| --- | --- |
| 当前剩余有效期 ≤ `ttl_seconds * 0.25`（推荐阈值 `refresh_lead_seconds=60`，可被服务在响应中覆写） | 在不中断通话的情况下重新调用 ICE config endpoint，获取新一组 `ice_servers[]` 与 credential。 |
| ICE agent 报告 TURN allocation refresh 失败、收到 `441 Wrong Credentials`、`438 Stale Nonce` 或等价错误 | 立即调用 ICE config endpoint，并对受影响 candidate 触发 ICE restart（`signaling.payload.kind = renegotiate`）。 |
| ICE config endpoint 返回 `turn_credential_expired` | 客户端按服务器返回的 `next_retry_at` / `Retry-After` 退避；超过 30 秒仍无新 credential 时通过 `cx.call.signal` 发出 `error` payload 并以 graceful hangup 收尾。 |

新 credential 应用规则：

- 客户端 MUST 在新 credential 生效后 **保留旧 allocation 直到所有现有 RTP 会话迁移完成**，然后再 `CREATE-PERMISSION` 释放旧通道；不得在 candidate 切换中途让媒体丢包。
- 多对多会议中，客户端 MUST 周期检查 `ttl_seconds`（默认每 30 秒），不得依赖单一 timer。
- Refresh 流程不重放 user-facing UI 提示；通话状态保持 `active`。
- Refresh 请求 MUST 与原 ICE config 请求一致地携带 per-call pairwise pseudonym（同一通话内 pseudonym 可保持不变，避免 TURN 运营方误判为不同呼叫）。

服务端规则：

- ICE config endpoint MUST 在响应中携带 `refresh_lead_seconds`（推荐 60、可调），让客户端按统一节奏 refresh。
- TURN shared secret MUST 周期轮换（默认 ≤ 24 小时）；轮换时 server MUST 同时接受新旧 secret 一段时间（grace ≥ `ttl_seconds`）以避免 in-call 集体失败。
- `turn_credential_expired` 响应 MUST 包含 `next_retry_at`；不得让客户端进入 tight retry loop。

## 7. Signaling Envelope

所有 call signaling frame 使用统一 envelope：

```json
{
  "kind": "cx.call.signal",
  "call_id": "cx:call:01J...",
  "space_id": "cx:space:...",
  "sender": "did:web:alice.example.com",
  "sender_device": "cx:device:01js0ke0000000000000000000",
  "seq": 12,
  "sent_at": "2026-04-26T00:00:00Z",
  "payload": {
    "kind": "invite",
    "data": {}
  },
  "proof": {}
}
```

`payload.kind`：

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

## 8. 一对一通话

Invite payload:

```json
{
  "kind": "invite",
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
  "kind": "answer",
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
  "kind": "candidate",
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

字段名在 Contrix envelope 中使用 snake_case；浏览器原生 `sdpMid` / `sdpMLineIndex` MUST 映射为 `sdp_mid` / `sdp_m_line_index`。

## 9. 多设备冲突处理

同一 actor 的多个设备 MAY 同时收到 invite。

规则：

- 首个 accepted answer 赢得 call leg。
- 其他设备收到同 actor 的 accepted answer 后 MUST 停止响铃。
- 发起端收到同 actor 多个 answer 时，只接受第一个通过签名和 device validity 验证的 answer。
- 被拒绝或超时的设备 SHOULD 发送 `reject`，reason 为 `answered_elsewhere` 或 `timeout`。

## 10. SFU 会议

### 10.1 SFU Service

SFU MUST 有 service DID，并通过 `cx.space.media_service` 或 feature discovery 声明。

SFU join request:

```json
{
  "call_id": "cx:call:01J...",
  "space_id": "cx:space:...",
  "actor_id": "did:web:alice.example.com",
  "device_id": "cx:device:01js0ke0000000000000000000",
  "capability_refs": ["cx:grant:..."],
  "desired_media": {
    "audio": true,
    "video": true,
    "screen": false
  }
}
```

SFU response:

```json
{
  "participant_id": "part_01",
  "transport": "webrtc",
  "offer": {
    "type": "offer",
    "sdp": "v=0\r\n..."
  },
  "sfu_signature": {
    "kid": "did:web:sfu.example#key-1",
    "sig": "base64url..."
  }
}
```

### 10.2 SFU 权限

SFU MUST verify:

- Space media service policy allows this SFU。
- actor has `call.join`。
- actor/device is not revoked。
- call state accepts new participants。
- media request does not exceed grants, e.g. screen share requires `call.screen_share`。

客户端 MUST verify SFU service DID 和 response signature。

### 10.3 E2EE with SFU

SFU 模式 SHOULD 使用 WebRTC Insertable Streams / SFrame 或等价机制实现端到端媒体加密。SFU 可转发 RTP 包和处理转发层 metadata，但不应获得明文媒体。

若 SFU 或 MCU 会解密媒体，客户端 MUST 显示明确安全边界，并且 Space policy MUST 允许 `media_service_decrypts=true`。

## 11. 会议状态事件

会议状态可作为 durable event 记录：

```json
{
  "kind": "cx.call.state",
  "space_id": "cx:space:...",
  "payload": {
    "call_id": "cx:call:01J...",
    "state": "active",
    "mode": "sfu",
    "participants": [
      {
        "actor_id": "did:web:alice.example.com",
        "device_id": "cx:device:01js0ke0000000000000000000",
        "joined_at": "2026-04-26T00:00:00Z",
        "media": {
          "audio": true,
          "video": true,
          "screen": false
        }
      }
    ]
  }
}
```

高频 speaking/mute/video 状态 SHOULD 走 ephemeral channel；会议开始、结束、参与者加入/离开 MAY 采样或摘要写入 durable state。

## 12. 屏幕共享

屏幕共享是一种独立 media source：

```json
{
  "kind": "media_state",
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

- 需要 `call.screen_share` capability。
- 客户端 MUST 在本地展示正在共享状态。
- 会议主持人 MAY 使用 `call.moderate` 请求停止某人的 screen share。

## 13. 录制与转写

录制和转写默认关闭，必须由 Space policy 和 call capability 显式允许。

启动录制：

```json
{
  "kind": "cx.call.recording.start",
  "space_id": "cx:space:...",
  "payload": {
    "call_id": "cx:call:01J...",
    "recording_agent": "did:web:recorder.example",
    "mode": "audio_video",
    "visible_notice": true
  }
}
```

要求：

- 需要 `call.record`。
- 客户端 MUST 对所有参会者显示录制中。
- 录制 artifact MUST 作为 encrypted Blob 或受控 media object 存储。
- 录制结果 MUST 通过 `cx.call.recording.result` 引用 blob hash、duration、media type、retention policy。
- 转写需要 `call.transcribe`，转写文本应作为 Morph 或 Artifact，并遵守同一 Space policy。

## 14. 推送集成

`cx.call.signal` 中 `kind=invite` SHOULD 触发 VoIP push。push 必须遵循 [`crypto-media/device-lifecycle.md` §5a Privacy-Preserving Push](./device-lifecycle.md) 的 pairwise pseudonym 规则；不得在投递给 APNs / FCM / Push Gateway 的 payload 中携带 principal DID、device DID URL、Space id、call id 或 sender DID。

脱敏 push payload（推送上游可见部分）:

```json
{
  "push_target_id": "cx:pseudonym:push:01js0pu0000000000000000000",
  "wakeup_kind": "incoming_call",
  "urgency": "urgent",
  "expires_at": "2026-04-26T00:01:00Z"
}
```

设备本地 OS 收到唤醒后，App 拉起 P2P / Sync 通道，使用本地密钥解密 `cx.call.signal{kind=invite}` envelope，从签名 envelope 中获得真实 `space_id`、`call_id`、`sender` 等字段并展示来电 UI。Push 上游永远看不到这些字段。

Push payload MUST NOT 包含 SDP、ICE candidate、TURN credential、principal DID、Space id、call id 或明文会议标题；只允许 §14 上面 4 个脱敏字段，其它一切信息必须通过本地解密获得。

## 15. 安全与隐私

实现 MUST：

- 验证所有 signaling sender 的 membership 和 device validity。
- 防止 replay、sequence rollback 和 stale invite。
- 对 TURN credential 使用短期凭证。
- 对高隐私 Space 支持 `force_turn`。
- 不把 SDP / ICE candidate 写入 durable public event。
- 对 SFU/MCU/recording service 使用 service DID 和 policy allowlist。
- 在 E2EE 降级、MCU 混流、录制、外部 PSTN bridge 时显示明确提示。

实现 SHOULD：

- 支持 IP 泄露最小化 profile。
- 支持 bandwidth / resolution policy。
- 对会议服务做 region / data residency 限制。
- 对呼叫滥用做 rate limit 和 block。

## 16. 错误码

| code | 含义 |
| --- | --- |
| `call_not_found` | call id 不存在或不可见。 |
| `call_expired` | invite 或 call 已过期。 |
| `call_already_answered` | 其他设备已经接听。 |
| `media_permission_denied` | 缺少 video/audio/screen/record 权限。 |
| `ice_config_denied` | 无权获取 ICE 配置。 |
| `turn_credential_expired` | TURN credential 已过期。 |
| `sfu_not_allowed` | Space policy 不允许该 SFU。 |
| `e2ee_required` | Space 要求 E2EE，但当前媒体路径不满足。 |
| `recording_denied` | 录制未授权或 policy 禁止。 |

## 17. 与 Matrix Call 的关系

Contrix 借鉴 Matrix call event、VoIP push、group call / SFU 方向，但采用自己的 Space、capability、device trust、policy server 和 transport binding 模型。

Matrix 风格的 call invite/answer/candidates 可通过 Applet/bridge 映射为 `cx.call.signal`，但 durable meeting state、recording artifact 和 Space policy 必须遵守 Contrix 规则。
