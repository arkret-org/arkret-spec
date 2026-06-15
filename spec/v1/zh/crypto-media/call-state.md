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
- `participants[]`：单条 `ck.call.state` 事件的 `participants[]` MUST ≤ 1,000 项（v1 wire 上限，见 [`../conformance/scalability-constraints.md` §5](../conformance/scalability-constraints.md)；schema 声明 `maxItems: 1000`）；超过时 MUST reject 或改用采样 / 摘要写入。
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

`call_state_payload.state` 是通话生命周期的受控枚举。它写入 `ck.component.call.state.v1` cell，`cell_subject = payload.call_id`，lattice 为 `fsm`、`bottom=reject`。合法转换、终态与并发语义如下：

| `state` | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| `scheduled` | 已排期，未开始 | `ringing`、`connecting`、`cancelled`、`missed`、`failed`（排期通话自动启动失败） | 否 |
| `ringing` | 呼叫已发起，待应答 | `connecting`、`active`、`missed`、`cancelled`、`failed` | 否 |
| `connecting` | 应答后媒体协商中 | `active`、`failed`、`ended` | 否 |
| `active` | 通话进行中 | `ended`、`failed` | 否 |
| `ended` | 正常结束 | —（终态） | **是** |
| `missed` | 未应答 | —（终态） | **是** |
| `failed` | 出错失败 | —（终态） | **是** |
| `cancelled` | 连接前取消 | —（终态） | **是** |

- **初始 state 集合**：某 `call_id` 的**首条** `ck.call.state` 事件，其 `state` MUST ∈ `{ scheduled, ringing, connecting }`——`scheduled` 对应预先排期，`ringing` 对应即时呼叫发起，`connecting` 对应无振铃阶段的直接加入（如会议直连）。首条事件携带其它取值（`active` 或任一终态）MUST `failed_precondition`，`reason_code="call_state_transition_invalid"`。
- **终态集合**：`{ ended, missed, failed, cancelled }`。reducer MUST 拒绝从任一终态转出（单调推进），违反用 `failed_precondition` `reason="call_state_terminal"`。
- **非法转换通用规则**：源 state 为非终态时，任何不在上表"合法后继"列内的 `state` 转换 MUST `failed_precondition`，`reason_code="call_state_transition_invalid"`（见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；源为终态时用 `call_state_terminal`，二者不混用。
- **同状态重放**：同一 basis 上重复提交相同 `from -> to` 转换是幂等 no-op；reducer MUST 不产生新的分叉 head，也不得把同值重放当成非法转换。
- **并发冲突**：同一 `call_id`、同一 CBA basis 下出现两个 sibling `ck.call.state` 转换，且二者的 `to` state 不同，`fsm` join MUST 返回 `Bottom{kind="conflict"}` 并按 `bottom=reject` 暴露 `failed_bottom` / diagnostic。实现 MUST NOT 用 HLC、`created_at`、`event_id`、actor id、event digest、数据库插入顺序或本地接收顺序选择 winner。冲突恢复必须由后续显式 recovery / operator action 在新的 accepted basis 上提交，不能静默回退。
- **终态吸收**：一旦某 accepted head 进入终态，任何后续转出都按 `call_state_terminal` 拒绝；终态不能被并发 winner 规则覆盖，因为本状态机没有 winner 规则。

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

- 需要 `ck.call.record` capability。`ck.call.recording.start` 通过 `capture_kind`(`recording` / `transcript`,缺省 `recording`)区分录制与转写两条平行生命周期(转写见 §5.1)。
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

### 5.1 转写生命周期（normative）

转写与录制平行：默认关闭，MUST 由 Realm policy 与 `ck.call.transcribe` capability 显式允许。转写态走 `ck.call.state` 的**独立字段** `transcript_state`（`{ transcribing, stopped, ready, failed }`，缺省=未转写），与 `state` 及 `recording_state` 三者正交。

- 启动转写复用 `ck.call.recording.start` event kind，但 `capture_kind="transcript"`（缺省 `recording` 用于向后兼容）；其 `recording_id` 同样是稳定 opaque 句柄，约束与 §5 录制 `recording_id` 完全一致（ASCII 子集 `[A-Za-z0-9._-]`、1–128 字节、逐字节 canonical、接收方 MUST NOT normalize），并进入 transcript key exporter Context。缺少 `ck.call.transcribe` 时 MUST 拒绝，`reason_code="transcription_denied"`。
- 客户端 MUST 对所有参会者显示转写进行中提示（与录制提示同等级别）。
- 转写文本 MUST 作为 **encrypted Blob / 受控 media object** 存储，绝不明文落 backend。转写 artifact 的加密 key MUST 由 Cokret MLS exporter 派生，**label 固定为 ASCII 字符串 `"ck-rtc-transcript-key/v1"`**（与 SFrame `"ck-rtc-frame-key/v1"`、录制 `"ck-rtc-recording-key/v1"` 区分），`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, transcript_start_event_id})`，输出 32 bytes；canonical 登记见 [`../../artifacts/registry/exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)。复用其它 label、空 Context，或接受 backend / KMS 自生成的 transcript key MUST fail closed `transcription_artifact_pipeline_bypassed`。
- 转写结果通过 `ck.call.state` 写入 `transcript_state`，并在 `transcript_result` 中引用 `transcript_start_event_id`；`ready` / `failed` 还 SHOULD 携带 content digest、media type、language 与 retention policy。手动停止时写 `transcript_state="stopped"`，不要求产生 artifact。
- v1 不为转写注册独立的 result / stop event kind；转写态变化一律通过 `ck.call.state` 写入。

### 5.2 录制 / 转写 retention policy（normative）

录制与转写 artifact 的保留期、删除触发、审计锁定与二次确认走 `recording_result.retention` / `transcript_result.retention`（schema 见 `call_recording_retention`）。规则：

- **保留期**：`retention.retention_expires_at` 是协议固定的**最早**可删除时间；缺省时由 `retention_policy_id` 指向的 Realm retention policy 决定。写入时 MUST NOT 为过去时刻。
- **删除触发**：`retention.deletion_trigger ∈ { retention_expiry, manual, realm_policy, participant_erasure }`。`participant_erasure` 对应某参与者发起 erasure 时对其媒体片段的级联删除（见 account erasure 流程）。
- **审计锁定**：`retention.audit_lock=true` 时该 artifact 处于 legal / audit hold，**任何**删除（含 retention 到期、manual）MUST 被拒绝 `legal_hold_active`，直到 audit 级 action 解除锁定；audit_lock 优先于 `retention_expires_at` 与 capability。
- **客户端二次确认**:录制 / 转写从未捕获进入捕获态（`recording_state="recording"` / `transcript_state="transcribing"`）前 MUST 取得用户的第二次显式同意，并将事实记入 `retention.consent_confirmed=true`。reducer 见到捕获态而对应 `retention.consent_confirmed` 不为 true 时 MUST `failed_precondition` `reason_code="recording_consent_required"`。
- retention 字段是 `recording_result` / `transcript_result` 的子对象，与 §4.2 录制态机正交；它只约束 artifact 生命周期，不改变通话 `state`。

## 6. P2P→SFU 升级（normative）

通话可以 P2P 起步（`mode="p2p"`），但当并发参与者人数 **> 2** 时 MUST 从 P2P 收敛到 SFU。触发与协商规则:

1. **触发条件**:任一参与设备观察到当前 active 参与者(已 accepted answer 的 leg)将达到 3 人时,MUST 发起升级，不得继续以 P2P / full-mesh 承载 3 人以上(`mesh` 仅 SHOULD 用于 3–4 人且不作为默认，见 §2)。
2. **focus 协商**:升级 MUST 复用 [`media-service-binding.md` §5](./media-service-binding.md) 的 deterministic, no-vote focus 选举——由 oldest_membership 的 `foci_preferred[0]` 选出 `session_focus` 并写入首个携带 `session_focus` 的 `ck.call.state`。升级**不**引入新的投票或 leader 选举路径。
3. **加入信令**:各设备通过 `ck.call.signal{signal_type=focus_join}`(见 [`webrtc-signaling.md` §5](./webrtc-signaling.md))向选定 focus 迁移媒体；原 P2P leg 在所有参与者完成 `focus_join` 后 MUST 优雅拆除，迁移期间不得丢媒体(参照 §4.2 credential refresh 的"保留旧 allocation 直到迁移完成"原则)。
4. **`mode` 写入**:升级落定后，下一条 `ck.call.state` 的 `mode` MUST 写 `sfu`,且一旦 `session_focus` committed 即不可在本生命周期内回退到 `p2p`(回退 P2P 需新 call)。
5. **单调性**:`session_focus` 一经 committed 即 write-once(改写 MUST `session_focus_already_committed`,见 §4.1);升级到 SFU 后人数回落到 2 人 MUST NOT 自动降级回 P2P。

## 7. 通话摘要（normative）

通话到达终态(`state ∈ { ended, missed, failed, cancelled }`)后,SHOULD 写入一条 durable `ck.call.summary` event,作为无需重放 ephemeral 信令即可呈现的持久通话记录:

```json
{
  "kind": "ck.call.summary",
  "realm_id": "ck:realm:...",
  "payload": {
    "call_id": "ck:call:0196441c-0000-7000-8000-000000000000",
    "final_state": "ended",
    "mode": "sfu",
    "started_at": "2026-04-26T00:00:00Z",
    "ended_at": "2026-04-26T00:42:00Z",
    "duration_ms": 2520000,
    "peak_participant_count": 7,
    "distinct_participant_count": 9,
    "recording_state": "ready",
    "transcript_state": "ready"
  }
}
```

- `ck.call.summary` 写入 `ck.component.call.summary.v1` cell,`cell_subject = payload.call_id`,lattice 为 `cas_register`、`bottom=reject`(write-once;divergent 重写 MUST `call_summary_invalid`)。
- `final_state` MUST 是某终态，且该 `call_id` MUST 已存在终态 `ck.call.state` head;否则 reducer MUST `failed_precondition` `reason_code="call_summary_invalid"`。
- `recording_state` / `transcript_state` 是终态时刻从 `ck.call.state` 镜像的捕获态；缺省表示未录制 / 未转写。
- 写入 `ck.call.summary` 需要 `ck.call.join`(参见 [`../../artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json));它不替代 `ck.call.state` 终态，而是其上的 durable 摘要投影。
