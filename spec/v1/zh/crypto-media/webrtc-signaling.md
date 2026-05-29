---
title: WebRTC Calls and Meetings
status: candidate
normative: true
stability: v1
updated: 2026-05-25
sidebar:
  label: WebRTC Calls
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Contrix 支持音频通话、视频通话、屏幕共享和多人会议。实时媒体本身不进入 Realm Event history；信令、会议状态、邀请、参与者变化、录制引用和通话摘要按不同持久性处理。

本文件定义：

- 一对一 WebRTC P2P 通话
- 多方会议的 Mesh / SFU / MCU 模式
- TURN / STUN / ICE server 动态发现
- 会议 membership、权限、E2EE、push、recording 和审计边界
- 信令事件、会议状态事件和服务发现

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
  "realm_id": "cx:realm:...",
  "title": "Design review",
  "fields": {
    "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
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

- Realm 成员不自动拥有 `call.record`。
- `call.screen_share` SHOULD 独立授权。
- `cx.call.configure_media_service` 只应授予管理员或受信服务。
- 被 ban / suspended 的 actor MUST NOT 加入 call。
- 外部 guest 加入必须通过 invite 或 meeting-specific guest grant。

## 6. ICE Server Discovery

客户端通过 Realm policy、service discovery 或 media service 获取 ICE servers。

### 6.1 Realm Media Service

`cx.realm.media_service` 把媒体服务声明为 **multi-focus 列表 + transport-agnostic backend 描述符**（参考 [CXP-0010](../../proposals/0010-media-service-binding-framework.md)）。协议层永不规定 SFU 内部协议；LiveKit / mediasoup / Janus / contrix-native / MoQ-relay 都作为可替换 backend 通过 `foci[].type` 区分，具体 wire 见 [`bindings/<type>.md`](./bindings/) 附录。

```json
{
  "kind": "cx.realm.media_service",
  "payload": {
    "service_id": "did:web:media.example.com",
    "modes": [
      "turn",
      "sfu"
    ],
    "ice_config_endpoint": "https://media.example.com/contrix/v1/ice-config",
    "foci": [
      {
        "focus_id": "fra-1",
        "type": "livekit",
        "region": "eu-fra",
        "token_endpoint": "https://media.example.com/contrix/v1/rtc/token",
        "connect_url": "wss://livekit-fra.example.com",
        "capabilities": ["audio", "video", "screen", "e2ee_sframe"],
        "health_endpoint": "https://media.example.com/contrix/v1/rtc/health/fra-1"
      },
      {
        "focus_id": "us-east-1",
        "type": "livekit",
        "region": "us-east",
        "token_endpoint": "https://media.example.com/contrix/v1/rtc/token",
        "connect_url": "wss://livekit-use.example.com",
        "capabilities": ["audio", "video", "screen", "e2ee_sframe"],
        "cascade_group": "livekit-cloud-mesh-a"
      }
    ],
    "default_call_mode": "sfu",
    "allowed_call_modes": [
      "p2p",
      "sfu"
    ],
    "recording_supported": false
  }
}
```

字段语义（normative）：

- `foci[].focus_id`：focus 在该 Realm media service 内的稳定 ID；进入签名 canonical bytes 与 `session_focus` 选举（见 §11.1）。
- `foci[].type`：backend binding 标识。v1 注册值：`livekit`、`mediasoup`、`janus`、`contrix-native`、`moq-relay`（实验保留位，v1 周期内不提供 normative binding）。客户端遇到未知或 unsupported `type` MUST fail closed（错误码 `unknown_focus_type`），不得尝试把 token 交给任意 SDK。
- `foci[].token_endpoint`：token 兑换端点；所有 backend 共用同一抽象（见 §6.4），差异只在 `backend_token` 形态。
- `foci[].connect_url`：backend 连接入口；具体协议由 type-specific 附录定义。
- `foci[].capabilities[]`：该 focus 支持的能力子集，用于客户端能力协商。
- `foci[].health_endpoint`（optional）：客户端预检 endpoint，返回 `200` + `{"status":"ok","load":<0..1>}`。**只用于尚未 commit `session_focus` 前**排序本地 `foci_preferred`；一旦 `cx.call.state.session_focus` 已存在，connect 失败 MUST 暴露为 focus 不可用，不得静默切到另一 focus（`session_focus_no_split_brain`）。
- `foci[].cascade_group`（optional）：声明属于同一 backend cluster 的 focus 集合；客户端可据此向用户披露"跨区域会议由 backend 内部级联"。协议层不规范 SFU-to-SFU cascading 协议——每个 backend 自行实现 mesh，详见 [CXP-0010 §4.6](../../proposals/0010-media-service-binding-framework.md)。

兼容性：v1 cycle 内服务端 SHOULD 接受遗留单 `sfu_endpoint` 形态并 normalize 为 `foci=[{focus_id:"legacy", type:"contrix-native", connect_url:<sfu_endpoint>, ...}]`，同时打 audit log；v1.1 起单 endpoint 形态升级为 `failed_precondition` `reason="legacy_single_endpoint_media_service"`。

修改该 state event 需要 `cx.call.configure_media_service` 或 `cx.policy.manage` capability。

### 6.4 Token Exchange (normative)

会议加入前，客户端 MUST 先向 `foci[].token_endpoint` 兑换 backend 凭证；issuer 是 Contrix-side 授权组件，对协议层不透明的 `backend_token` 由 backend SDK 解析。Token endpoint 等价于 [MSC4195 `lk-jwt-service`](https://github.com/element-hq/lk-jwt-service)，但绑定到 Contrix 的 capability / Realm policy / MLS governance binding。

请求：

```http
POST {token_endpoint}
Authorization: <device proof | bearer>
Content-Type: application/json

{
  "realm_id": "cx:realm:...",
  "call_id": "cx:call:...",
  "actor_id": "did:web:alice.example.com",
  "device_id": "cx:device:...",
  "focus_id": "fra-1",
  "capability_refs": ["cx:grant:..."],
  "desired_media": { "audio": true, "video": true, "screen": false }
}
```

响应（`scheme="cx.media.participant_binding.v1"` 是 v1 唯一 participant binding scheme）：

```json
{
  "focus_id": "fra-1",
  "type": "livekit",
  "connect_url": "wss://livekit-fra.example.com",
  "backend_token": "<opaque to Contrix protocol — type-specific>",
  "participant_identity": "cx:rtcpart:0198c2f4-0000-7000-8000-000000000000",
  "participant_binding": {
    "scheme": "cx.media.participant_binding.v1",
    "realm_id": "cx:realm:...",
    "call_id": "cx:call:...",
    "focus_id": "fra-1",
    "actor_id": "did:web:alice.example.com",
    "device_id": "cx:device:...",
    "participant_identity": "cx:rtcpart:0198c2f4-0000-7000-8000-000000000000",
    "issued_at": "2026-05-27T12:29:56Z",
    "expires_at": "2026-05-27T12:34:56Z",
    "issuer_kid": "did:web:media.example#key-1",
    "sig": "base64url..."
  },
  "expires_at": "2026-05-27T12:34:56Z",
  "service_signature": { "kid": "did:web:media.example#key-1", "sig": "base64url..." }
}
```

核心约束（normative）：

- **TTL 短期化**：`backend_token` / `participant_binding` `expires_at` MUST ≤ 600s（10 分钟），SHOULD ≤ 300s。过期前客户端 MUST 重新兑换；backend token 一旦泄漏在 TTL 内通常不可吊销（除非 backend 提供 revocation list），短 TTL 是工程兜底。
- **Token issuer DID 锚定**：`service_signature.kid` 与 `participant_binding.issuer_kid` MUST 解析到一个出现在当前 epoch `cx.realm.media_service.service_id` 的 service DID；客户端 MUST 拒绝来自未授权 DID 的 token，错误码 `token_issuer_unauthorised`。该规则把 token 签发权与 Realm policy 锁定，防止任意 service 凭空铸造 join token。
- **`participant_identity` 形态**：作为 SFU-local 短期 handle，scope 限 `(call_id, focus_id, sfu_did)`；MUST NOT 携带可关联到长期 actor 身份的可识别信息（与 §6.2 pairwise pseudonym 规则对齐），且 MUST 至少绑定 `(realm_id, call_id, focus_id, device_id, issuer_service_did, issued_at_bucket)` 派生。
- **`participant_identity` 传播边界**：因为它本身不携带 actor 链接信息，客户端 **MUST** 把它写入 `cx.call.state.participants[].participant_identity`（用于 §10.4 cross-check）——这条嵌入是 Realm-encrypted control state，不构成 actor-身份外泄。但 `participant_identity` MUST NOT 进入下列三类 surface：(a) 任何 plaintext audit log / 服务方 access log（包括 backend SFU 自身的日志）；(b) 任何 unencrypted ephemeral / push / telemetry 通道；(c) backend 一侧对外的 metrics、tracing 标签或 cross-tenant 数据导出。Backend 内部允许保留它作为 SFU-local routing handle，但不应跨 call leg / 跨 tenant 复用。
- **`participant_binding` 是 token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺**。客户端 MUST 先验证该 binding，再把它写入 / 对照 `cx.call.state` membership（见 §11）。backend 只看到 `participant_identity` 与 `backend_token`，不应获得长期 actor 身份。

Token issuer MUST 在签发前校验：

- 调用者 device proof / bearer 有效，未 revoked。
- Actor 在 `realm_id` 拥有 `cx.call.join` capability；`desired_media` 不超过授权（`cx.call.screen_share` 等子 capability 检查）。
- Realm policy 允许该 `focus_id`（即 focus 出现在当前 `cx.realm.media_service.foci[]` 中）。
- 如果 `cx.call.state.session_focus` 已存在，请求的 `focus_id` 与其完全一致；不一致 MUST 返回 `focus_mismatch`。
- call state 允许新 participant，且该 `(actor_id, device_id)` 未被 revoked / banned / suspended。
- MLS governance binding `policy_root` 与 `cx.realm.media_service` 当前 epoch 一致（防 stale policy）；不一致返回 `mls_governance_binding_stale`。
- 如果 backend 将解密媒体（`media_service_decrypts=true`），完整执行 §10.5.1 的三层校验。

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
| `realm_id` | body | `id` | required | 通话所在 Realm。 |
| `call_id` | body | `id` | required | 通话 ID。 |
| `actor_id` | body | `did` | required | 请求 ICE 配置的 Actor。 |
| `device_id` | body | `id` | required | 请求设备。 |
| `mode` | body | `enum(p2p,sfu,turn)` | required | 请求媒体模式。 |

请求示例（非完整 schema）：

```json
{
  "realm_id": "cx:realm:...",
  "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:...",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
  "mode": "p2p"
}
```

响应字段（schema 见 [`ice-config-response.schema.json`](../../artifacts/schemas/ice-config-response.schema.json)，schema id `cx.schema.ice_config_response.v1`）：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `realm_id` | `id` | required | 回显请求 Realm，进入签名 canonical bytes，防止跨 Realm 重放。 |
| `call_id` | `id` | required | 回显请求 call，进入签名 canonical bytes，防止跨通话重放。 |
| `actor_id` | `did` | required | 回显请求 actor，进入签名 canonical bytes。 |
| `device_id` | `id` | required | 回显请求设备，进入签名 canonical bytes。 |
| `ttl_seconds` | `int` | required | ICE 配置有效期（秒）。建议 ≤ 1 小时。 |
| `refresh_lead_seconds` | `int` | required | 客户端在剩余有效期 ≤ 此值时 SHOULD 提前刷新；建议 `ttl_seconds / 4`，下限 60s 上限 1800s。让所有客户端按统一节奏 refresh，server 也据此设计 secret rotation grace 窗口。 |
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
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "call_id": "cx:call:0196419c-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
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

- TURN credential MUST 短期有效，SHOULD 使用 REST-style ephemeral credential（draft-uberti-rtcweb-turn-rest-00 风格 username = `<expiry-unix>:<pairwise-pseudonym>`，password = `HMAC-SHA256(turn_shared_secret, username)`；实现不得降级为 HMAC-SHA1）。
- TURN `username` 中的"身份段" MUST 是 **per-call pairwise pseudonym**（建议形态 `cx_pseudonym_call_<random>` 或等价 random tag）。它不得是 principal DID、handle、邮箱或可跨呼叫关联的稳定 ID；该不可关联性只针对 TURN 运营方成立，不对铸造 pseudonym 的 Contrix media service 成立。
- Pseudonym 生成 MUST 使用每次通话的新随机种子或 media service 私有密钥派生，且至少绑定 `(realm_id, call_id, actor_id, device_id, issued_at_bucket, media_service_did)`；推荐：

  ```text
  pseudonym = "cx_pseudonym_call_" ||
    base64url(HMAC-SHA256(media_service_pseudonym_secret,
      canonical_json({realm_id, call_id, actor_id, device_id, issued_at_bucket, nonce})
    )[0:16])
  ```

  `nonce` MUST 对每个 `(call_id, actor_id, device_id)` fresh，media service MUST 在签名 ICE config 的内部审计记录中保留 nonce freshness evidence，且不得把 nonce 或其稳定派生值写入 TURN username 之外的可跨 Realm 关联字段。Refresh 时同一 active call leg MAY 复用 pseudonym 以避免 TURN 误判为不同会话，但新 call、new device leg、超过 `ttl_seconds + refresh grace` 的恢复、或 policy 要求匿名重置时 MUST 生成新 pseudonym。Pseudonym 不得仅由稳定 ID 确定性派生。
- ICE config response MUST 由 media service 签名，签名 canonical bytes MUST 覆盖 `realm_id`、`call_id`、`actor_id`、`device_id`、`issued_at`、`issued_at_bucket`、`bucket_seconds`、`ttl_seconds`、`ice_servers[]` 与策略字段；TLS + service DID 绑定只能认证通道，不能替代响应对象签名。
- 客户端 MUST 尊重 `ttl_seconds`，过期后重新获取。
- 高隐私 Realm MAY 设置 `force_turn=true`，禁止 host/srflx candidate 泄露本地或公网 IP。

### 6.3 In-call Credential Refresh

通话进行中 TURN credential 可能在 `ttl_seconds` 之前到期或被 server 主动撤销。客户端 MUST 实现在通话期间的 credential refresh，避免 mid-call 失联：

| 触发条件 | 客户端行为 |
| --- | --- |
| 当前剩余有效期 ≤ `ttl_seconds * 0.25`（推荐阈值 `refresh_lead_seconds=60`，可被服务在响应中覆写） | 在不中断通话的情况下重新调用 ICE config endpoint，获取新一组 `ice_servers[]` 与 credential。 |
| ICE agent 报告 TURN allocation refresh 失败、收到 `441 Wrong Credentials`、`438 Stale Nonce` 或等价错误 | 立即调用 ICE config endpoint，并对受影响 candidate 触发 ICE restart（`signaling.payload.signal_type = renegotiate`）。 |
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

所有 call signaling frame 使用 `cx.schema.ephemeral_envelope.v1` 的 broadcast envelope；`cx.call.signal` 分支 MUST 携带 `device_id` 与 `proof`，并在 `payload` 中携带 call 级字段：

```json schema=schemas/ephemeral-envelope.schema.json
{
  "kind": "cx.call.signal",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "actor_id": "did:web:alice.example.com",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
  "sent_at": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-26T00:00:30Z",
  "payload": {
    "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
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

SFU 在 v1 通过 [§6.1](#61-realm-media-service) 的 `foci[]` 声明，每个 focus 通过 `type` 选择具体 backend binding：

- `type="livekit"`：见 [`bindings/livekit.md`](./bindings/livekit.md)。
- `type="contrix-native"`：见 [`bindings/contrix-native.md`](./bindings/contrix-native.md)（reference impl，不推荐生产使用）。
- `type="mediasoup"` / `type="janus"` / `type="moq-relay"`：保留位，v1 周期内不提供 normative binding；客户端遇到 unsupported `type` MUST fail closed，错误码 `unknown_focus_type`。

不论 backend 类型，client→backend 媒体协商前 MUST 先完成 [§6.4 Token Exchange](#64-token-exchange-normative)；具体 `backend_token` 形态、connect handshake、SDP 协商由 type-specific 附录定义。下面的 §10.2 / §10.3 / §10.4 是跨 backend 通用约束。

### 10.2 Focus Selection 与 Session 持久化（normative）

会议第一次 join 时由客户端排序 `foci_preferred[]` 写入 `cx.call.state.participants[].foci_preferred`；之后用 **deterministic, no-vote** 规则收敛为单一 `session_focus`：

1. 若 `cx.call.state.session_focus` 已存在，它就是唯一 authoritative focus；客户端和 token issuer MUST 使用它。
2. 若 `session_focus` 尚不存在，收集所有当前 active member 的 `(joined_at, actor_id, device_id, foci_preferred)` 元组；按 `(joined_at, actor_id, device_id)` 升序，**oldest_membership 的 `foci_preferred[0]` 被写入 `session_focus`**。
3. 后加入者 MUST 使用同一 `session_focus`，无论自己的偏好；如果该 focus 在自己的 preferred 列表中不存在，客户端 MAY 拒绝加入（fail closed），错误码 `focus_unavailable_for_client`。
4. Token issuer MUST 拒绝任何 `focus_id != session_focus` 的 token exchange，错误码 `focus_mismatch`；该规则优先于 health check、region preference 和 load balancing。
5. 当 oldest member 离开，focus **不自动迁移**（避免媒体路径中断）；session 持续到所有人离开后才重置。v1 不提供 in-session focus migration。

### 10.3 SFU 权限

SFU MUST verify:

- Realm media service policy allows this `(focus_id, service_id)` 组合（即 focus 出现在当前 `cx.realm.media_service.foci[]`）。
- actor has `cx.call.join`（capability registry canonical 命名，参见 [`../authz/capabilities.md`](../authz/capabilities.md) §5）。
- actor/device is not revoked。
- call state accepts new participants。
- media request does not exceed grants, e.g. screen share requires `cx.call.screen_share`。

客户端 MUST 校验：

- token issuer service DID 出现在当前 `cx.realm.media_service.service_id` / `foci[].token_endpoint` 锚定的 service DID 列表；
- token exchange 响应的 `service_signature` 与 `participant_binding.sig` 通过；
- backend 通知 "X 加入会议" 时携带的 `participant_identity` 与 `cx.call.state.participants[].participant_identity` 一致（见 §10.4 cross-check）。

### 10.4 Participant Identity 交叉校验（normative）

backend "X 加入会议" 通知到达客户端时，客户端 MUST：

1. 从 backend 通知中提取 `participant_identity`。
2. 在当前 `cx.call.state.participants[]` 中查找同一 `participant_identity`。
3. 验证该 participant entry 内的 `participant_binding` 签名（[§6.4](#64-token-exchange-normative)），确认它覆盖同一 `(realm_id, call_id, session_focus, actor_id, device_id, participant_identity)`。
4. 不匹配或签名无效 → 拒绝为该 participant 建立媒体流（不收音、不订阅 video），错误码 `participant_identity_unrecognised`。

这道闸门防止 backend 单方面 "塞入" 未经 Realm 授权的参与者——backend 运营方误配置、被入侵或恶意 inject 都无法绕过 Contrix-side `cx.call.state` 真源。

### 10.5 E2EE with SFU

SFU 模式 SHOULD 使用 WebRTC Insertable Streams / SFrame 或等价机制实现端到端媒体加密。SFU 可转发 RTP 包和处理转发层 metadata，但不应获得明文媒体。

若 SFU 或 MCU 会解密媒体，客户端 MUST 显示明确安全边界，并且 Realm policy MUST 允许 `media_service_decrypts=true`。

#### 10.5.0 E2EE Key Injection 通用契约（normative）

无论 backend 自身是否支持 E2EE，所有 binding 附录的 E2EE 章节 MUST 规定一个最小契约，使得 **客户端侧 binding adapter / media SDK** 能从 Contrix 协议层接收 frame key，而不从 backend 自带密钥分发机制取。最小契约：

```text
inject_frame_key(key_bytes: 32-byte secret,
                 epoch_id: u64,
                 rotation_trigger: enum{member_join, member_leave, manual, scheduled})
```

约束：

- `key_bytes` MUST 由 Contrix MLS exporter 派生，**label 固定为 ASCII 字符串 `"cx-rtc-frame-key/v1"`**（length=19 bytes，无 trailing newline；RFC 9420 §8 `MLS-Exporter` 的 `Label`，`Context = ""`，`KDF.Nh` 长度 32 bytes）。该 label 不在 conformance 阶段再议——任何变更属于 wire-breaking，必须开新 profile。
- `epoch_id` 与 Realm MLS epoch 一一对应。
- backend SDK / adapter 内部如何把该 key 映射到 SFrame / 私有帧加密格式由附录指定，但 **MUST NOT** 接受任何非该接口的 key 源（如 backend 自带 KMS、自生成 random key）。除非 Realm policy 明确允许 `media_service_decrypts=true` 且完成 §10.5.1 三层校验，`key_bytes` MUST NOT 被发送给远端 SFU / MCU。
- Conformance negative vector `cx.vector.media_binding.e2ee_key_source.v1`：backend 用自家密钥 → 客户端 MUST 拒绝并报 `e2ee_key_source_unauthorised`。

Conformance vectors for the full media binding framework：

- `cx.vector.media_binding.focus_selection_oldest_membership.v1` — §10.2 oldest_membership 选举正确性。
- `cx.vector.media_binding.session_focus_no_split_brain.v1` — `session_focus` 写入后 connect 失败 MUST 暴露为不可用，不静默切 focus。
- `cx.vector.media_binding.token_exchange_minimal.v1` — §6.4 token exchange 最小字段集 + TTL ≤ 600s。
- `cx.vector.media_binding.token_issuer_unauthorised.v1` — issuer DID 不在 service_id 锚定列表时拒绝。
- `cx.vector.media_binding.participant_binding_required.v1` — 缺失或签名无效的 `participant_binding` 必须拒绝。
- `cx.vector.media_binding.unknown_type_fail_closed.v1` — §6.1 未知 `foci[].type` MUST fail closed。
- `cx.vector.media_binding.participant_identity_unrecognised.v1` — §10.4 backend 通知的 participant 不在 `cx.call.state` 时拒绝该流。
- `cx.vector.media_binding.recording_artifact_via_contrix_blob.v1` — §13 backend-generated recording 必须经 Contrix blob pipeline。

#### 10.5.1 治理绑定（normative）

**三层关系**: `cx.realm.media_service` declares SFU existence; `plaintext_visible_services` grants decryption authority; `cx.realm.policy_components.media_service_decrypts=true` carries the boolean toggle — 三者 MUST 同时成立才能让 media service 解密。

`media_service_decrypts=true` **不**是一个可单独由 SFU 服务自报或客户端配置的开关。它 MUST 同时满足下列约束，否则客户端 MUST 拒绝加入会议、SFU MUST 拒绝媒体协商：

1. **进入 `cx.realm.policy_components`**：`media_service_decrypts=true` MUST 由一条 `cx.realm.policy_components`（或对应 Realm policy facet event）显式写入，受 capability `cx.realm.policy.manage` 控制，并随 Realm policy `policy_root` 一同被 [`encryption-and-audit.md` §2.5](./encryption-and-audit.md) 的 MLS governance binding 覆盖。policy_root 未包含该开关时 MUST 视为未开启。
2. **进入 `plaintext_visible_services`**：解密媒体的 SFU / MCU service DID MUST 在 Realm policy 的 `plaintext_visible_services[]`（或等价 media plaintext service policy）中显式列出，并标 `purpose=media_plaintext`。仅出现在 `media_services[]` 而未列入 `plaintext_visible_services[]` 的服务 MUST 被视为禁止解密媒体的 SFU；其试图协商解密角色时 MUST 返回 `media_plaintext_service_not_authorised`。
3. **MLS Governance Binding 覆盖**：成员在 join 前 MUST 校验当前 epoch 的 governance binding `policy_root` 涵盖前两条规则的 cell value；不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商（不能依赖 SFU 单方面声明）。
4. **Downgrade 攻击拒绝**：从 `media_service_decrypts=false` 切换到 `true`（或反向）MUST 走 `cx.realm.policy_components` 正常路径并伴随客户端 UI 显著二次确认；不允许 SFU 直接以 OOB 控制信号宣告自己已"获得解密权"。在 governance binding 尚未 commit 新 policy_root 的窗口内，客户端 MUST 沿用旧 policy 视图判定，禁止根据 OOB 字段提前授权。
5. **Conformance negative vector** `cx.vector.webrtc.media_plaintext_downgrade.v1` 必须覆盖：(a) policy_root 未覆盖 `media_service_decrypts` ⇒ 拒绝加入；(b) SFU 未列入 `plaintext_visible_services` 而协商解密 ⇒ 拒绝媒体；(c) UI 未显示警示 ⇒ 拒绝加入。

实际效果：SFU / MCU 不能在 MLS transcript 之外单独变更为可解密媒体的一方。任何看起来"切换成功"但未被 governance binding 覆盖的状态都是 attack，必须 fail closed。

## 11. 会议状态事件

会议状态可作为 durable event 记录：

```json
{
  "kind": "cx.call.state",
  "realm_id": "cx:realm:...",
  "payload": {
    "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
    "state": "active",
    "mode": "sfu",
    "session_focus": "fra-1",
    "participants": [
      {
        "actor_id": "did:web:alice.example.com",
        "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
        "joined_at": "2026-04-26T00:00:00Z",
        "foci_preferred": ["fra-1", "us-east-1"],
        "participant_identity": "cx:rtcpart:0198c2f4-0000-7000-8000-000000000000",
        "participant_binding": {
          "scheme": "cx.media.participant_binding.v1",
          "realm_id": "cx:realm:...",
          "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
          "focus_id": "fra-1",
          "actor_id": "did:web:alice.example.com",
          "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
          "participant_identity": "cx:rtcpart:0198c2f4-0000-7000-8000-000000000000",
          "issued_at": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:05:00Z",
          "issuer_kid": "did:web:media.example#key-1",
          "sig": "base64url..."
        },
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

### 11.1 字段语义（normative）

- `session_focus`：本 call 唯一 authoritative `focus_id`。**reducer 写入规则**：第一个 `cx.call.state` 事件根据 §10.2 选举规则把 oldest member 的 `foci_preferred[0]` 写入；后续 `cx.call.state` MUST 保持同值，任何改写 MUST `failed_precondition` `reason="session_focus_already_committed"`。session 结束（所有 participants 离开）后才重置。
- `participants[].foci_preferred`：客户端本地排序的 focus 偏好列表，用于 §10.2 选举。后加入者写入的 `foci_preferred` 不影响已 committed 的 `session_focus`。
- `participants[].participant_identity`：来自 token exchange 响应的 SFU-local handle（见 §6.4）；scope 限 `(call_id, focus_id, sfu_did)`。
- `participants[].participant_binding`：token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺。reducer **MUST** 验证：
  1. `issuer_kid` 解析到的 service DID 出现在当前 epoch `cx.realm.media_service.service_id`；
  2. binding `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_identity` 与 participant entry 一致；
  3. `expires_at` > event `created_at`（不接受已过期 binding）；
  4. `sig` 通过签名验证。
  任一失败 → `failed_precondition` `reason="participant_binding_invalid"`。

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

录制和转写默认关闭，必须由 Realm policy 和 call capability 显式允许。

启动录制：

```json
{
  "kind": "cx.call.recording.start",
  "realm_id": "cx:realm:...",
  "payload": {
    "call_id": "cx:call:0196441c-0000-7000-8000-000000000000",
    "recording_agent": "did:web:recorder.example",
    "mode": "audio_video",
    "visible_notice": true
  }
}
```

要求：

- 需要 `cx.call.record` capability。
- 客户端 MUST 对所有参会者显示录制中。
- 录制 artifact MUST 作为 encrypted Blob 或受控 media object 存储。
- **Backend-generated recording 必经 Contrix blob pipeline**（参见 [CXP-0010 §4.7](../../proposals/0010-media-service-binding-framework.md)）：backend 可能自带录制能力（LiveKit Egress、Janus recording plugin 等），但生成的 artifact MUST：
  1. 作为加密 blob 上传到 Contrix media service（通过 [`media-and-blob.md`](./media-and-blob.md) 的 authenticated upload 端点），不得 backend 自行托管。
  2. 上传请求携带 `recording_initiator_capability_ref`，证明该 recording 由具备 `cx.call.record` 的 actor 发起。
  3. 加密 key MUST 由 Contrix 协议层提供（与 §10.5.0 同源，从 MLS exporter 派生），backend 不持久化明文。
  4. 入库后通过 `cx.call.state` 发布 lifecycle state，引用 blob hash、duration、media type、retention policy 与 `recording_start_event_id`。
  绕过该 pipeline（如 backend 直接对外暴露 recording URL）MUST 被客户端拒绝并报 `recording_artifact_pipeline_bypassed`。这保证 backend 是 "录制执行单元" 而非 "录制档案库"。
- 录制结果 MUST 通过已注册的 `cx.call.state` 写入 call lifecycle state（例如 `state="recording_ready"` / `state="recording_failed"`），并在 payload 中引用 blob hash、duration、media type、retention policy 和 `recording_start_event_id`。v1 不注册独立的 `cx.call.recording.result` event kind；实现不得把该裸名写入 Event Envelope。
- 转写需要 `cx.call.transcribe`，转写文本应作为 Morph 或 Artifact，并遵守同一 Realm policy。

## 14. 推送集成

`cx.call.signal` 中 `kind=invite` SHOULD 触发 VoIP push。push 必须遵循 [`crypto-media/device-lifecycle.md` §5a Privacy-Preserving Push](./device-lifecycle.md) 的 pairwise pseudonym 规则；不得在投递给 APNs / FCM / Push Gateway 的 payload 中携带 principal DID、device DID URL、Realm id、call id 或 sender DID。

脱敏 push payload（推送上游可见部分）:

```json
{
  "push_target_id": "cx:pseudonym:push:01js0pu0000000000000000000",
  "wakeup_kind": "incoming_call",
  "urgency": "urgent",
  "expires_at": "2026-04-26T00:01:00Z"
}
```

设备本地 OS 收到唤醒后，App 拉起 P2P / Sync 通道，使用本地密钥解密 `cx.call.signal{kind=invite}` envelope，从签名 envelope 中获得真实 `realm_id`、`call_id`、`sender_actor_id` 等字段并展示来电 UI。Push 上游永远看不到这些字段。

Push payload MUST NOT 包含 SDP、ICE candidate、TURN credential、principal DID、Realm id、call id 或明文会议标题；只允许 §14 上面 4 个脱敏字段，其它一切信息必须通过本地解密获得。

**Push wakeup 与 invite lifetime（normative）**: VoIP push wakeup 仅传 "incoming call" 信号，不携带 invite envelope；客户端唤醒后 MUST fresh fetch 当前 invite envelope。若本地 invite 已过期（超出 `lifetime_ms` = 60s 默认），客户端 MUST 拒绝复用 envelope，触发新 `call_invite` 流程。push wakeup 自身的 TTL（默认 24h）与 invite signaling lifetime 是不同语义，不构成死锁。

## 15. 安全与隐私

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

## 16. 错误码

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

## 17. 与 Matrix Call 的关系

Contrix 借鉴 Matrix call event、VoIP push、group call / SFU 方向，但采用自己的 Realm、capability、device trust、policy server 和 transport binding 模型。

Matrix 风格的 call invite/answer/candidates 可通过 Applet/bridge 映射为 `cx.call.signal`，但 durable meeting state、recording artifact 和 Realm policy 必须遵守 Contrix 规则。
