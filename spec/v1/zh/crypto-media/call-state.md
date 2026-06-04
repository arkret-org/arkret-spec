---
title: Call State and Recording
status: candidate
normative: true
stability: v1
updated: 2026-06-04
sidebar:
  label: Call State
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与范围

本文件定义通话 / 会议的 **durable 真源**：通话模型与状态机、`ck.call.state` payload 字段语义与 reducer 校验规则、participant 绑定的落地校验，以及录制 / 转写的生命周期。实时媒体本身不进入 Realm Event history；高频信令走 ephemeral 通道。

边界：

- ephemeral 信令（offer/answer/candidate、ICE/TURN、一对一通话、推送、`ck.call.*` 权限模型）见 [`webrtc-signaling.md`](./webrtc-signaling.md)。
- 媒体服务发现、token / participant binding 兑换、focus 选举、媒体 E2EE 帧密钥注入见 [`media-service-binding.md`](./media-service-binding.md)。

## 2. 通话模型

| 模式 | 适用 | 说明 |
| --- | --- | --- |
| `p2p` | 1 对 1 或极小规模 | 双方直接 WebRTC 连接，必要时经 TURN server。 |
| `mesh` | 3-4 人小会 | 每个客户端与其他客户端建连接，复杂度高，不建议默认。 |
| `sfu` | 多方会议默认 | Selective Forwarding Unit 转发 RTP，不解密 E2EE 内容。 |
| `mcu` | PSTN / 录制 / 低端设备 | Multipoint Control Unit 混流，通常会接触明文或解密后媒体，MUST 强提示和审计。 |

默认多人会议 SHOULD 使用 SFU。

## 3. Call Morph

会议或通话 SHOULD 用标准 Morph 表示：

```json
{
  "morph_type": "call",
  "realm_id": "ck:realm:...",
  "title": "Design review",
  "fields": {
    "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
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

## 4. 会议状态事件

会议状态可作为 durable event 记录：

```json
{
  "kind": "ck.call.state",
  "realm_id": "ck:realm:...",
  "payload": {
    "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
    "state": "active",
    "mode": "sfu",
    "session_focus": "fra-1",
    "participants": [
      {
        "actor_id": "did:web:alice.example.com",
        "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
        "joined_at": "2026-04-26T00:00:00Z",
        "foci_preferred": ["fra-1", "us-east-1"],
        "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
        "participant_binding": {
          "scheme": "ck.media.participant_binding.v1",
          "realm_id": "ck:realm:...",
          "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
          "focus_id": "fra-1",
          "actor_id": "did:web:alice.example.com",
          "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
          "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
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

### 4.1 字段语义（normative）

- `session_focus`：本 call 唯一 authoritative `focus_id`。**reducer 写入规则**：第一个 `ck.call.state` 事件根据 [`media-service-binding.md` §5](./media-service-binding.md) 选举规则把 oldest member 的 `foci_preferred[0]` 写入；后续 `ck.call.state` MUST 保持同值，任何改写 MUST `failed_precondition` `reason="session_focus_already_committed"`。session 结束（所有 participants 离开）后才重置。
- `participants[].foci_preferred`：客户端本地排序的 focus 偏好列表，用于 [`media-service-binding.md` §5](./media-service-binding.md) 选举。后加入者写入的 `foci_preferred` 不影响已 committed 的 `session_focus`。
- `participants[].participant_identity`：来自 token exchange 响应的 SFU-local handle（见 [`media-service-binding.md` §3](./media-service-binding.md)）；scope 限 `(call_id, focus_id, sfu_did)`。
- `participants[].participant_binding`：token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺。reducer **MUST** 验证：
  1. `issuer_kid` 解析到的 service DID 出现在当前 epoch `ck.realm.media_service.service_id`；
  2. binding `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_identity` 与 participant entry 一致；
  3. `expires_at` > event `created_at`（不接受已过期 binding）；
  4. `sig` 通过签名验证。
  任一失败 → `failed_precondition` `reason="participant_binding_invalid"`。

高频 speaking/mute/video 状态 SHOULD 走 ephemeral channel；会议开始、结束、参与者加入/离开 MAY 采样或摘要写入 durable state。

## 5. 录制与转写

录制和转写默认关闭，必须由 Realm policy 和 call capability 显式允许。

启动录制：

```json
{
  "kind": "ck.call.recording.start",
  "realm_id": "ck:realm:...",
  "payload": {
    "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
    "recording_id": "rtc-recording-0196441d-0000-7000-8000-000000000000",
    "recording_agent": "did:web:recorder.example",
    "mode": "audio_video",
    "visible_notice": true
  }
}
```

要求：

- 需要 `ck.call.record` capability。
- 客户端 MUST 对所有参会者显示录制中。
- `payload.recording_id` MUST 是该录制 artifact lifecycle 的稳定 opaque string，并进入 recording key exporter Context；缺失时 recording start event MUST `schema_violation` reject。它不是 `ck:*` typed ID；最终持久化产物仍通过 Cokret blob / Morph / artifact 引用暴露。
- 录制 artifact MUST 作为 encrypted Blob 或受控 media object 存储。
- **Backend-generated recording 必经 Cokret blob pipeline**（参见 [CKP-0010 §4.7](../../proposals/0010-media-service-binding-framework.md)）：backend 可能自带录制能力（LiveKit Egress、Janus recording plugin 等），但生成的 artifact MUST：
  1. 作为加密 blob 上传到 Cokret media service（通过 [`media-and-blob.md`](./media-and-blob.md) 的 authenticated upload 端点），不得 backend 自行托管。
  2. 上传请求携带 `recording_initiator_capability_ref`，证明该 recording 由具备 `ck.call.record` 的 actor 发起。
  3. 加密 key MUST 由 Cokret 协议层提供（与 [`media-service-binding.md` §8.1](./media-service-binding.md) 同源，从 MLS exporter 派生），backend 不持久化明文。Recording artifact key label 固定为 `"cx-rtc-recording-key/v1"`，`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id})`，输出 32 bytes；不得复用 SFrame label `"cx-rtc-frame-key/v1"` 或空 Context。
  4. 入库后通过 `ck.call.state` 发布 lifecycle state，引用 blob hash、duration、media type、retention policy 与 `recording_start_event_id`。
  绕过该 pipeline（如 backend 直接对外暴露 recording URL）MUST 被客户端拒绝并报 `recording_artifact_pipeline_bypassed`。这保证 backend 是 "录制执行单元" 而非 "录制档案库"。
- 录制结果 MUST 通过已注册的 `ck.call.state` 写入 call lifecycle state（例如 `state="recording_ready"` / `state="recording_failed"`），并在 payload 中引用 blob hash、duration、media type、retention policy 和 `recording_start_event_id`。v1 不注册独立的 `ck.call.recording.result` event kind；实现不得把该裸名写入 Event Envelope。
- 转写需要 `ck.call.transcribe`，转写文本应作为 Morph 或 Artifact，并遵守同一 Realm policy。
