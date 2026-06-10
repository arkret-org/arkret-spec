---
title: Call State and Recording
status: candidate
normative: true
stability: v1
updated: 2026-06-10
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
    "ended_at": null
  }
}
```

`state`（通话生命周期，完整枚举、合法转换与终态见 §4.2）：

- `scheduled`
- `ringing`
- `connecting`
- `active`
- `ended`
- `missed`
- `failed`
- `cancelled`

> 录制**不是**通话生命周期的一部分，走**独立字段** `recording_state`（`{ recording, stopped, ready, failed }`，缺省=未录制），与 `state` 正交，见 §4.2 / §5。

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

### 4.2 `state` 状态机（normative）

`call_state_payload.state` 是通话生命周期的受控枚举。合法转换、终态与并发仲裁如下：

| `state` | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `scheduled` | 已排期，未开始 | `ringing`、`connecting`、`cancelled`、`missed` | 否 |
| `ringing` | 呼叫已发起，待应答 | `connecting`、`active`、`missed`、`cancelled`、`failed` | 否 |
| `connecting` | 应答后媒体协商中 | `active`、`failed`、`ended` | 否 |
| `active` | 通话进行中 | `ended`、`failed` | 否 |
| `ended` | 正常结束 | —（终态） | **是** |
| `missed` | 未应答 | —（终态） | **是** |
| `failed` | 出错失败 | —（终态） | **是** |
| `cancelled` | 连接前取消 | —（终态） | **是** |

- **终态集合**：`{ ended, missed, failed, cancelled }`。reducer MUST 拒绝从任一终态转出（单调推进），违反用 `failed_precondition` `reason="call_state_terminal"`。
- **并发仲裁**：多个并发 `ck.call.state` head 时，按 canonical order 取最终态；一旦达终态即吸收，不得回退。

**`recording_state`（录制维度，与 `state` 正交，normative）**：`{ recording, stopped, ready, failed }`，缺省=未录制。录制随 `ck.call.recording.start` 进入 `recording`；人工停止时通过 `ck.call.state` 写 `recording_state="stopped"`；artifact 入 Cokret blob pipeline 后转 `ready`，失败转 `failed`。录制态**独立于** `state`——通话可在 `active` 期间为 `recording_state="recording"`，通话 `ended` 之后再写 `recording_state="ready"`。`recording_state ∈ { ready, failed, stopped }` 时 SHOULD 携带 `recording_result.recording_start_event_id` 绑定本段录制的 start event；`ready` / `failed` 还 SHOULD 携带 content digest / duration / media type / retention policy。v1 不为录制注册独立 result/stop event，录制态变化通过 `ck.call.state` 写入（见 §5）。

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
- `payload.recording_id` MUST 是该录制 artifact lifecycle 的稳定 opaque string，并进入 recording key exporter Context；缺失时 recording start event MUST `schema_violation` reject。它不是 `ck:*` typed ID；最终持久化产物仍通过 Cokret blob / Morph / artifact 引用暴露。由于 `recording_id` 是跨实现密钥派生输入（进入 §5 第 3 步的 `Context`），其 canonical 形态 MUST 由 `ck.call.state` recording start event 一次性固定并逐字节保留：取值 MUST 为 ASCII 子集 `[A-Za-z0-9._-]`、长度 1–128 字节；发送方写入后该字符串即为 canonical，**接收方 MUST NOT 做任何 normalize**（大小写折叠、Unicode NFC/NFKC、trim、re-encode 等），并 MUST 在所有引用该录制的 event / key 派生中逐字节复用 start event 的原值。任何对 `recording_id` 的本地规范化都会令派生出的 recording key 与发送方分裂、导致解密失败。
- 手动停止录制不注册独立 `ck.call.recording.stop` event；holder of `ck.call.record` 通过 `ck.call.state` 写 `recording_state="stopped"`，并在 `recording_result.recording_start_event_id` 指向被停止的 `ck.call.recording.start`。`stopped` 是该录制段的终态，不要求产生 artifact；若 backend 已经产出可用 artifact，后续 MAY 以同一 `recording_start_event_id` 写 `ready`，否则保持 `stopped`。
- 同一通话允许多段录制。`ready` / `failed` / `stopped` 之后再次进入 `recording` 时，MUST 先接受新的 `ck.call.recording.start`，且新的 `recording_id` MUST 不同于该 call 任何既有 recording start 的 `recording_id`。物化投影 MAY 只展示最新 `recording_state`，但历史段以各自 `ck.call.recording.start` 与后续 `ck.call.state` event 保持可审计。
- 录制 artifact MUST 作为 encrypted Blob 或受控 media object 存储。
- **Backend-generated recording 必经 Cokret blob pipeline**（参见 [`media-service-binding.md` §8.1](./media-service-binding.md)）：backend 可能自带录制能力（LiveKit Egress、Janus recording plugin 等），但生成的 artifact MUST：
  1. 作为加密 blob 上传到 Cokret media service（通过 [`media-and-blob.md`](./media-and-blob.md) 的 authenticated upload 端点），不得 backend 自行托管。
  2. 上传请求携带 `recording_initiator_capability_ref`，证明该 recording 由具备 `ck.call.record` 的 actor 发起。
  3. 加密 key MUST 由 Cokret 协议层提供（与 [`media-service-binding.md` §8.1](./media-service-binding.md) 同源，从 MLS exporter 派生），backend 不持久化明文。Recording artifact key label 固定为 `"ck-rtc-recording-key/v1"`，`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id})`，输出 32 bytes；不得复用 SFrame label `"ck-rtc-frame-key/v1"` 或空 Context。
  4. 入库后通过 `ck.call.state` 发布 lifecycle state，引用 content digest、duration、media type、retention policy 与 `recording_start_event_id`。
  绕过该 pipeline（如 backend 直接对外暴露 recording URL）MUST 被客户端拒绝并报 `recording_artifact_pipeline_bypassed`。这保证 backend 是 "录制执行单元" 而非 "录制档案库"。
- 录制结果 MUST 通过已注册的 `ck.call.state` 写入**独立的 `recording_state` 字段**（`recording_state="ready"` / `recording_state="failed"` / `recording_state="stopped"`，与通话 `state` 正交，见 §4.2），并在 `recording_result` 中引用 `recording_start_event_id`；ready/failed 结果还应引用 content digest、duration、media type 和 retention policy。v1 不注册独立的 `ck.call.recording.result` 或 `ck.call.recording.stop` event kind；实现不得把这些裸名写入 Event Envelope。
- 转写需要 `ck.call.transcribe`，转写文本应作为 Morph 或 Artifact，并遵守同一 Realm policy。
