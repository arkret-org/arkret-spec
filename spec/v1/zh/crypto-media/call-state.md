---
title: Call State and Recording
status: candidate
normative: true
stability: v1
updated: 2026-07-13
sidebar:
  label: Call State
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与范围

本文件定义通话 / 会议的 **durable 真源**：通话模型与状态机、`ak.call.state` payload 字段语义与 reducer 校验规则、participant 绑定的落地校验，以及录制 / 转写的生命周期。实时媒体本身不进入 Realm Event history；高频信令走 ephemeral 通道。

边界：

- ephemeral 信令（offer/answer/candidate、ICE/TURN、一对一通话、推送、`ak.call.*` 权限模型）见 [`webrtc-signaling.md`](./webrtc-signaling.md)。
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
  "morph_kind": "call",
  "realm_id": "ak:realm:...",
  "title": "Design review",
  "fields": {
    "call_id": "ak:call:0196441c-0000-7000-8000-000000000000",
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

> 录制**不是**通话生命周期的一部分，走独立 `recording_transition` delta，与 `state_transition` 正交，见 §4.2 / §5。

## 4. 会议状态事件

会议状态可作为 durable event 记录：

```json
{
  "kind": "ak.call.state",
  "realm_id": "ak:realm:...",
  "payload": {
    "call_id": "ak:call:0196441c-0000-7000-8000-000000000000",
    "state_transition": {
      "from": "connecting",
      "to": "active"
    },
    "focus": {
      "mode": "sfu",
      "session_focus": "fra-1"
    },
    "roster_delta": {
      "op": "join",
      "participant": {
        "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
        "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
        "joined_at": "2026-04-26T00:00:00Z",
        "foci_preferred": ["fra-1", "us-east-1"],
        "participant_identity": "ak:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
        "participant_binding": {
          "scheme": "ak.media.participant_binding.v1",
          "realm_id": "ak:realm:...",
          "call_id": "ak:call:0196441c-0000-7000-8000-000000000000",
          "focus_id": "fra-1",
          "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
          "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
          "participant_identity": "ak:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
          "issued_at": "2026-04-26T00:00:00Z",
          "expires_at": "2026-04-26T00:05:00Z",
          "issuer_kid": "did:webvh:zCxjAemtszNh7bTFGWFS4m8gv:media.example#key-1",
          "sig": "base64url..."
        },
        "media": {
          "audio": true,
          "video": true,
          "screen": false
        }
      }
    }
  }
}
```

### 4.1 字段语义（normative）

**Cell 归属（normative）**：`ak.call.state` 的各个正交轴分别写入**各自独立、各自单 lattice 的 cell**，登记在 canonical [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 的 `ak.call.state` `cell_writes[]` 中。一个 cell family 只有一个 `lattice` 与一个 cell 级 `bottom`（[`../authz/event-auth-state-resolution.md` §9 / §9.1.1](../authz/event-auth-state-resolution.md)），因此 v1 **不存在**"同一 cell 内 per-field 判定"或"per-field bottom"的语义：

| 承载字段 | cell family | cell_subject | lattice | bottom |
| --- | --- | --- | --- | --- |
| `state_transition` | `ak.component.call.state.v1` | `payload.call_id` | `fsm` | `reject` |
| `focus` | `ak.component.call.focus.v1` | `payload.call_id` | `cas_register` | `reject` |
| `recording_transition` | `ak.component.call.recording.v1` | composite `[payload.call_id, payload.recording_transition.recording_id]` | `fsm` | `reject` |
| `recording_transition.result` | `ak.component.call.recording_result.v1` | 同上 | `cas_register` | `reject` |
| `transcript_transition` | `ak.component.call.transcript.v1` | composite `[payload.call_id, payload.transcript_transition.recording_id]` | `fsm` | `reject` |
| `transcript_transition.result` | `ak.component.call.transcript_result.v1` | 同上 | `cas_register` | `reject` |
| `moderation_delta` | `ak.component.call.moderation.v1` | `payload.call_id` | `or_set` | `inert` |
| `roster_delta` | `ak.component.call.roster.v1` | `payload.call_id` | `or_set` | `inert` |
| `mute_override` | `ak.component.call.mute_override.v1` | composite `[payload.call_id, payload.mute_override.actor_id, payload.mute_override.device_id]` | `cas_register` | `reject` |

**未变更的轴 MUST NOT 产生 projected write（normative）**：`payload.call_id` 之外的每个 delta 字段都是可选的，单条 `ak.call.state` MUST 只携带本次实际变更的轴，并且至少携带一个 delta（schema `anyOf`）。上表每条 `cell_writes[]` 都是**条件性**目标；字段存在则对应 write 必需，字段缺席则对应 write MUST NOT 产生。`recording_transition.result` / `transcript_transition.result` 各自额外产生 result cell write。完整 op 由 registry `effect_projection` 派生，producer 不得自选 `from` / `to` / `tag` / `value`。

**捕获态按段切分**：录制 / 转写 cell 的 subject 是 `(call_id, recording_id)` composite，因此同一通话的多段捕获天然落在不同 cell，互不冲突。段键选用 `payload.recording_id` 而不是 start Event 的 `event_id`：v1 的封闭 envelope subject 来源白名单只登记 `envelope.actor_id`，不登记 `envelope.event_id`；而 `recording_id` 已经是 `ak.call.recording.start` 的 required 字段、已按 §5 要求在同一通话内逐段唯一、且已是录制 / 转写 key exporter Context 的 member，因此是两侧都能派生的同一个键。`ak.call.recording.start` 按 `payload.capture_kind` 写入 `ak.component.call.recording.v1` 或 `ak.component.call.transcript.v1`，subject 为 `[payload.call_id, payload.recording_id]`；后续 `ak.call.state` 用 `recording_transition.recording_id` / `transcript_transition.recording_id` 指向同一段，其值 MUST 与该段 start event 的 `recording_id` 逐字节相同。`capture_kind` 是 required 字段，MUST NOT 由 missing-field default 推断——它决定目标 cell family。

**捕获 transition 与 result 分离（normative）**：`recording_transition` / `transcript_transition` 自身 MUST 携带 `recording_id`、`from`、`to`，FSM cell 只保存生命周期 state。可选 `result` 写入独立 result CAS cell；不得把 artifact/result 私自塞进 transition op，因为 FSM join 不保存 `op.value`。`recording_start_event_id` / `transcript_start_event_id` 只作 provenance 引用。

- `focus`：是 `ak.component.call.focus.v1` 的**完整目标值**，`mode` required、`session_focus` optional。首个 committed `session_focus` 后，任何后继 `focus` 写入都 MUST 原样携带它；省略或改写均以 `session_focus_already_committed` 拒绝。`mode` 只允许按 §6 单向升级。
- `roster_delta`：`op=join` 时 effect 固定为 `add(tag=dot,value=participant)`（`dot` 为本 write 的 canonical OR-Set dot，定义见 [`../models/event-and-patch.md`](../models/event-and-patch.md) §2.4.2）；`op=leave` 时固定为 `remove(tag=observed_dot)`，并携带与 observed add value 一致的 `actor_id/device_id`。未知、跨 call 或身份不匹配的 tag MUST 拒绝。每 Event 只允许一个 roster delta；effective roster 上限为 1,000。
- `roster_delta.participant` 的 durable 身份最小化：除 Realm policy 明确要求实名审计且已披露外，`actor_id` MUST 使用 call-scoped pairwise DID，`device_id` MUST 使用仅在该 call 内稳定的 typed device alias。`joined_at` 若写入 durable event MUST 向下取整到 5 分钟 bucket。
- `roster_delta.participant.foci_preferred`：客户端本地 focus 偏好列表；后加入者不得改变已 committed `session_focus`。
- `roster_delta.participant.participant_identity`：来自 token exchange 响应的 SFU-local handle，scope 限 `(call_id, focus_id, sfu_did)`。
- `roster_delta.participant.participant_binding`：token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺。reducer **MUST** 验证：
  1. `issuer_kid` 解析到的 service DID 出现在当前 epoch `ak.realm.media_service.service_id`；
  2. binding `realm_id` / `call_id` / `focus_id` / `actor_id` / `device_id` / `participant_identity` 与 participant entry 一致；
  3. `expires_at` > event `created_at`（不接受已过期 binding）；
  4. `sig` 通过签名验证。
  任一失败 → `failed_precondition` `reason="participant_binding_invalid"`。
- **P2P / mesh roster 分支**：当当前 `focus.mode ∈ {p2p, mesh}` 且尚无
  `session_focus` 时，roster join MUST 省略 `participant_identity` 与
  `participant_binding`；participant identity 由 signed answer proof 中的
  `(call_id, actor_id, device_id)` 组成，admission service 验证 answer 后接受 durable join。
  当 `focus.mode ∈ {sfu, mcu}` 或已 committed `session_focus` 时，上述两个字段反而都 MUST
  出现并按本节四项校验。模式分支由包含 roster delta 的同一 accepted call-state basis
  决定，producer 不得自行声明第三个判据。
- `mute_override`：每个 call leg 独立写入 `ak.component.call.mute_override.v1` CAS cell。`status=active` 时必须携带 `audio_muted/video_muted`；`status=cleared` 时二者必须省略。不同 leg 并发互不冲突，同一 leg 并发改写 fail closed。写入者 MUST 持有 `ak.call.moderate`。
- `moderation_delta.op=remove_participant`：projected write 固定为 `add(tag=dot,value=removal)`。`kick` MUST 含 `device_id`；`ban` MUST 省略它。`moderation_delta.op=restore_participant` 固定移除 `observed_dot`，且只能移除已观察到、actor 一致的 ban，不能恢复 kick。

高频 speaking、自主 mute/video 状态 SHOULD 走 encrypted Signal Extension；主持人强制静音 MUST 通过 durable `mute_override` 驱动服务端媒体权限。

### 4.2 `state` 状态机（normative）

`call_state_payload.state_transition` 是通话生命周期 delta，显式携带 `from` / `to`。它写入 `ak.component.call.state.v1`，且**只承载这一条轴**。合法转换、终态与并发语义如下：

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

- **初始 state 集合**：某 `call_id` 的**首条** `ak.call.state` 事件 MUST 携带 `state`（其余轴可选，但首条不得只写别的轴而让 `state` 轴 cell 保持未初始化），且其 `state` MUST ∈ `{ scheduled, ringing, connecting }`——`scheduled` 对应预先排期，`ringing` 对应即时呼叫发起，`connecting` 对应无振铃阶段的直接加入（如会议直连）。首条事件携带其它取值（`active` 或任一终态）MUST `failed_precondition`，`reason_code="call_state_transition_invalid"`。
- **终态集合**：`{ ended, missed, failed, cancelled }`。reducer MUST 拒绝从任一终态转出（单调推进），违反用 `failed_precondition` `reason="call_state_terminal"`。
- **非法转换通用规则**：源 state 为非终态时，任何不在上表"合法后继"列内的 `state` 转换 MUST `failed_precondition`，`reason_code="call_state_transition_invalid"`（见 [`artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json)）；源为终态时用 `call_state_terminal`，二者不混用。
- **同状态重放**：同一 basis 上重复提交相同 `from -> to` 转换是幂等 no-op；reducer MUST 不产生新的分叉 head，也不得把同值重放当成非法转换。
- **并发冲突**：同一 `call_id`、同一 CBA basis 下出现两个 sibling `ak.call.state` 转换，且二者的 `to` state 不同，`fsm` join MUST 返回 `Bottom{kind="conflict"}` 并按 `bottom=reject` 暴露 `failed_bottom` / diagnostic。实现 MUST NOT 用 HLC、`created_at`、`event_id`、actor id、event digest、数据库插入顺序或本地接收顺序选择 winner。冲突恢复必须由后续显式 recovery / operator action 在新的 accepted basis 上提交，不能静默回退。
- **终态吸收**：一旦某 accepted head 进入终态，任何后续转出都按 `call_state_terminal` 拒绝；终态不能被并发 winner 规则覆盖，因为本状态机没有 winner 规则。

**超时推进（normative）**：`ring_timeout_ms` 默认且最大为 `60,000`；`scheduled_start_grace_ms` 默认且最大为 `300,000`；`connecting_timeout_ms` 默认且最大为 `120,000`。计时锚分别为进入 `ringing` 的 accepted event `created_at`、排期开始时间、进入 `connecting` 的 accepted event `created_at`。focus / token issuer（无 focus 时为 Principal Server）MUST 在窗口到达后以当前 accepted head 为 CAS basis 提交显式状态事件：`ringing → missed`、未在 grace 内开始的 `scheduled → missed`、`connecting → failed`（`failure_reason_code="media_negotiation_timeout"`）。计时器本身不得直接改写 reducer state。若迟到的 `active` 与超时终态竞争，仍按上文 sibling conflict / `bottom=reject` 规则处理；提交方 MUST NOT 用本地到达顺序选择 winner。
- **空 roster 终态推进**：当 focus / token issuer 观察到 active media roster 为空时，最后离开的、仍持有 `ak.call.join` 的成员 SHOULD 立即提交 `state_transition={from:"active",to:"ended"}`；focus / token issuer MUST 启动 `call_empty_timeout_ms`（默认且最大 120,000 ms），超时前 roster 仍为空时 MUST 代表该 call 提交同一显式 transition。若没有 focus（纯 P2P），承载该 Realm 的 Principal Server MUST 以相同窗口根据 authenticated ephemeral leave / leg expiry 证据推进终态。任何新 leg 在该窗口内重新加入会取消计时；终态 accepted 后不得复活，重新加入必须创建新 `call_id`。

**录制维度（与通话 state 正交，normative）**：录制只随 `ak.call.recording.start` 从空值进入 `recording`；后续 `recording_transition.to ∈ { stopped, ready, failed }`，人工停止、artifact ready 或失败通过显式 transition 推进。start event 与后续 transition 的 `result` 都写独立 result cell；`to=ready` MUST 携带有效 artifact。

#### `recording_transition` / `transcript_transition` 受控转换（normative）

`recording_transition` 与 `transcript_transition` 各自绑定单段捕获，与主 `state_transition` 及彼此正交。两者同构，单段转换表如下：

| 捕获态 | 语义 | 合法后继 | 终态? |
| --- | --- | --- | --- |
| （缺省=未录制） | 该 `call_id` 尚无录制段 | `recording`（接受 `ak.call.recording.start` 后） | — |
| `recording` | 捕获进行中 | `stopped`、`ready`、`failed` | 否 |
| `stopped` | 人工停止，可能无 artifact | `ready`（backend 事后产出 artifact） | **是**（除非升级为 `ready`） |
| `ready` | artifact 已入库 | —（本段终态） | **是** |
| `failed` | 捕获 / 入库失败 | —（本段终态） | **是** |

- **终态集合**：`{ ready, failed }` 为硬终态；`stopped` 是软终态——只能向 `ready` 升级（同一 `recording_start_event_id`，backend 事后产出可用 artifact），不得转 `failed` 或回 `recording`。`ready` / `failed` 之后对同一捕获段的任何转出 MUST `failed_precondition`，`reason_code="recording_state_transition_invalid"`。
- **非法转换**：源态为非终态时，任何不在"合法后继"列内的 `recording_transition.from -> recording_transition.to` / `transcript_transition.from -> transcript_transition.to` 转换 MUST `failed_precondition`，`reason_code="recording_state_transition_invalid"`（转写用同一 reason_code）。新一段捕获 MUST 先接受新的 `ak.call.recording.start`（新 `recording_id`，见 §5），不得在终态上原地翻回 `recording`。
- **正交轴之间互不影响（normative）**：state、focus、每段 capture lifecycle、每段 result、moderation、roster 与每个 leg 的 mute override 分别落在不同 cell；某个 cell 的冲突不得冻结其它轴。
- **同一轴的并发冲突**：两个并发 sibling `ak.call.state` 对**同一** cell 写入不同 `to` 值时，该 cell 的 fsm join MUST 返回 `Bottom{kind="conflict"}` 并按 `bottom=reject` 暴露 `failed_bottom`；恢复走 §9.5 conflict-recovery。实现 MUST NOT 用 HLC、`created_at`、`event_id`、actor id、event digest 或接收顺序选择 winner。
- **moderation / roster 并发 join**：每个 add 使用 Event id 作为唯一 dot，remove 只引用已观察 dot。不同目标的并发 add 自然并集；remove 不能删除未观察到的并发新 dot。重复 Event id 的 add value 必须逐字节相同，否则拒绝。

## 5. 录制与转写

录制和转写默认关闭，必须由 Realm policy 和 call capability 显式允许。

启动录制：

```json
{
  "kind": "ak.call.recording.start",
  "realm_id": "ak:realm:...",
  "payload": {
    "call_id": "ak:call:0196441c-0000-7000-8000-000000000000",
    "recording_id": "rtc-recording-0196441d-0000-7000-8000-000000000000",
    "recording_agent": "did:webvh:zCYG7PrN3Yt1TdX4X8gfYFA4R:recorder.example",
    "capture_kind": "recording",
    "mode": "audio_video",
    "visible_notice": true
  }
}
```

要求：

- 需要 `ak.call.record` capability。`ak.call.recording.start` 通过 **required** `capture_kind`(`recording` / `transcript`)区分录制与转写两条平行生命周期(转写见 §5.1)；它选择目标 cell family(`ak.component.call.recording.v1` / `ak.component.call.transcript.v1`)，因此 MUST 显式携带，缺失 MUST `schema_violation`，MUST NOT 由 missing-field default 推断。
- `payload.mode` MUST 显式携带，封闭为 `audio` / `audio_video`；无缺省值，缺失 MUST `schema_violation`。
- `payload.visible_notice` MUST 显式为 `true`；客户端 MUST 对所有参会者显示录制中。
- `payload.result` MUST 携带与 `capture_kind` 对应的 `recording_start_event_id` 或 `transcript_start_event_id`，且该值 MUST 逐字节等于本 Event 的 `event_id`；另一种 start ref MUST 缺省。`result.retention.consent_confirmed` MUST 为 `true`，否则 reducer 在创建 capture FSM cell 前拒绝 `recording_consent_required`。start event 原子写入 capture FSM 与独立 result cell，不能先进入捕获态再补交同意事实。
- `payload.recording_id` MUST 是该录制 artifact lifecycle 的稳定 opaque string，并进入 recording key exporter Context；缺失时 recording start event MUST `schema_violation` reject。它不是 `ak:*` typed ID；最终持久化产物仍通过 Arkret blob / Morph / artifact 引用暴露。由于 `recording_id` 是跨实现密钥派生输入（进入 §5 第 3 步的 `Context`），其 canonical 形态 MUST 由 `ak.call.state` recording start event 一次性固定并逐字节保留：取值 MUST 为 ASCII 子集 `[A-Za-z0-9._-]`、长度 1–128 字节；发送方写入后该字符串即为 canonical，**接收方 MUST NOT 做任何 normalize**（大小写折叠、Unicode NFC/NFKC、trim、re-encode 等），并 MUST 在所有引用该录制的 event / key 派生中逐字节复用 start event 的原值。任何对 `recording_id` 的本地规范化都会令派生出的 recording key 与发送方分裂、导致解密失败。
- 手动停止录制不注册独立 `ak.call.recording.stop` event；holder of `ak.call.record` 通过 `ak.call.state` 写 `recording_transition={recording_id,from:"recording",to:"stopped"}`。若同时携带 `recording_transition.result`，其中的 `recording_start_event_id` 继续指向该段的 `ak.call.recording.start` 作为 provenance；该 result 写入独立 result cell，不进入 FSM transition op。`stopped` 是该录制段的终态，不要求产生 artifact；若 backend 已经产出可用 artifact，后续 MAY 以同一 `recording_start_event_id` 写 `to="ready"`，否则保持 `stopped`。
- 同一通话允许多段录制。`ready` / `failed` / `stopped` 之后再次进入 `recording` 时，MUST 先接受新的 `ak.call.recording.start`，且新的 `recording_id` MUST 不同于该 call 任何既有 recording start 的 `recording_id`。物化投影 MAY 只展示最新捕获态，但历史段以各自 `ak.call.recording.start` 与后续 `ak.call.state` event 保持可审计。
- 录制 artifact MUST 作为 encrypted Blob 或受控 media object 存储。
- **Backend-generated recording 必经 Arkret blob pipeline**（参见 [`media-service-binding.md` §8.1](./media-service-binding.md)）：backend 可能自带录制能力（LiveKit Egress、Janus recording plugin 等），但生成的 artifact MUST：
  1. 作为加密 blob 上传到 Arkret media service（通过 [`media-and-blob.md`](./media-and-blob.md) 的 authenticated upload 端点），不得 backend 自行托管。
  2. 上传请求携带 `recording_initiator_capability_ref`，证明该 recording 由具备 `ak.call.record` 的 actor 发起。
  3. 加密 key MUST 由 Arkret 协议层提供（与 [`media-service-binding.md` §8.1](./media-service-binding.md) 同源，从 MLS exporter 派生），backend 不持久化明文。Recording artifact key label 固定为 `"ak.rtc-recording-key/v1"`，`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_id, recording_start_event_id})`，输出 32 bytes；不得复用 SFrame label `"ak.rtc-frame-key/v1"` 或空 Context。
  4. 入库后通过 `ak.call.state` 的 `recording_transition` 发布 lifecycle state，并在 `recording_transition.result` 引用 content digest、duration、media type、retention policy、`recording_start_event_id` 与 artifact。
  绕过该 pipeline（如 backend 直接对外暴露 recording URL）MUST 被客户端拒绝并报 `recording_artifact_pipeline_bypassed`。这保证 backend 是 "录制执行单元" 而非 "录制档案库"。
- 录制结果 MUST 通过已注册的 `ak.call.state` 写入 `recording_transition`：`to` 为 `ready` / `failed` / `stopped`，与通话 `state_transition` 正交（见 §4.2）；需要结果事实时在 `recording_transition.result` 中引用 `recording_start_event_id`。`to="ready"` 时，`recording_transition.result.artifact` MUST 符合 [`call-recording-artifact.schema.json`](../../artifacts/schemas/call-recording-artifact.schema.json)，其 `schema` MUST 为 `ak.schema.call_recording_artifact.v1`，且 MUST 绑定同一 `realm_id` / `call_id` / `recording_id` / `recording_start_event_id`、`blob_ref`、`content_digest`、`ciphertext_digest`、`duration_ms`、`media_type`、`encryption.exporter_label="ak.rtc-recording-key/v1"`、`encryption.context`、`retention`、`produced_by` 与 `recording_initiator_capability_ref`。result 中的 `content_digest` / `duration_ms` / `media_type` / `retention_policy_id` / `retention` 是便于投影和查询的镜像字段；若与 artifact 同名事实不一致，reducer / consumer MUST fail closed `schema_violation`。`to="failed"` 时 SHOULD 携带 `failure_reason_code`，MUST NOT 携带 backend 直出 URL、明文路径或明文片段。v1 不注册独立的 `ak.call.recording.result` 或 `ak.call.recording.stop` event kind；实现不得把这些裸名写入 Event Envelope。
录制与转写的 `failure_reason_code` 共用封闭 core 集：`media_negotiation_timeout` / `permission_denied` / `backend_unavailable` / `media_source_unavailable` / `storage_failed` / `policy_revoked` / `consent_withdrawn` / `integrity_failed`。扩展值 MUST 使用 `x_` 前缀并匹配 `^x_[a-z0-9_]{1,62}$`；其它值 MUST `schema_violation`。

- 转写需要 `ak.call.transcribe`，转写文本应作为 Morph 或 Artifact，并遵守同一 Realm policy。

### 5.1 转写生命周期（normative）

转写与录制平行：默认关闭，MUST 由 Realm policy 与 `ak.call.transcribe` capability 显式允许。转写态走 `ak.call.state` 的独立 `transcript_transition`（`to ∈ { stopped, ready, failed }`，缺省=未转写；进入 `transcribing` 只能由下述 `ak.call.recording.start` 派生），与 `state_transition` 及 `recording_transition` 三者正交。

- 启动转写复用 `ak.call.recording.start` event kind，但 `capture_kind="transcript"`（该字段 required，无 missing-field default）；其 `recording_id` 同样是稳定 opaque 句柄，约束与 §5 录制 `recording_id` 完全一致（ASCII 子集 `[A-Za-z0-9._-]`、1–128 字节、逐字节 canonical、接收方 MUST NOT normalize），并进入 transcript key exporter Context。缺少 `ak.call.transcribe` 时 MUST 拒绝，`reason_code="transcription_denied"`。
- 客户端 MUST 对所有参会者显示转写进行中提示（与录制提示同等级别）。
- 转写文本 MUST 作为 **encrypted Blob / 受控 media object** 存储，绝不明文落 backend。转写 artifact 的加密 key MUST 由 Arkret MLS exporter 派生，**label 固定为 ASCII 字符串 `"ak.rtc-transcript-key/v1"`**（与 SFrame `"ak.rtc-frame-key/v1"`、录制 `"ak.rtc-recording-key/v1"` 区分），`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_id, transcript_start_event_id})`，输出 32 bytes；canonical 登记见 [`../../artifacts/registry/exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)。复用其它 label、空 Context，或接受 backend / KMS 自生成的 transcript key MUST fail closed `transcription_artifact_pipeline_bypassed`。
- 转写结果通过 `ak.call.state` 写入 `transcript_transition`，并在 `transcript_transition.result` 中引用 `transcript_start_event_id`；`to="ready"` / `to="failed"` 时还 SHOULD 携带 content digest、media type、language 与 retention policy。手动停止时写 `to="stopped"`，不要求产生 artifact。
- v1 不为转写注册独立的 result / stop event kind；转写态变化一律通过 `ak.call.state` 写入。

### 5.2 录制 / 转写 retention policy（normative）

录制与转写 artifact 的保留期、删除触发、审计锁定与二次确认走对应 capture transition 的 `result.retention`（schema 见 `call_recording_retention`）。规则：

- **保留期**：`retention.retention_expires_at` 是协议固定的**最早**可删除时间；缺省时由 `retention_policy_id` 指向的 Realm retention policy 决定。写入时 MUST NOT 为过去时刻。
- **删除触发**：`retention.deletion_trigger ∈ { retention_expiry, manual, realm_policy, participant_erasure }`。`participant_erasure` 对应某参与者发起 erasure 时对其媒体片段的级联删除（见 account erasure 流程）。实际删除尝试的触发事实写入 result artifact 的 `deletion_audit.trigger`（或转写后续定义的等价 artifact 字段）；该值 MUST 与 retention 的 `deletion_trigger` 一致，不得由 Blob 服务或媒体 backend 自行改写。
- **审计锁定**：`retention.audit_lock=true` 时该 artifact 处于 legal / audit hold，**任何**删除（含 retention 到期、manual）MUST 被拒绝 `legal_hold_active`，直到 audit 级 action 解除锁定；audit_lock 优先于 `retention_expires_at` 与 capability。**解除后删除（normative）**：audit_lock 被 audit 级 action 解除后，删除按**原本适用的** `deletion_trigger` 继续（`retention_expiry` 若已到期、否则按触发来源取 `manual` / `realm_policy` / `participant_erasure`），**不**新增独立 trigger 枚举值；该次删除的 deletion audit MUST 记录解锁来源（`legal_hold_ref` + 对应 `trigger_event_id`），使"曾被 legal hold 阻塞、解锁后按原 trigger 删除"在审计上可追溯。
- **删除审计**：每次删除尝试 MUST 至少在服务审计日志中记录 `trigger`、`outcome`、`requested_by?`、`trigger_event_id?`、`requested_at`、`completed_at?`、`erasure_receipt_ref?`、`legal_hold_ref?` 与 `failure_reason_code?`，其 wire 形态见 `call-recording-artifact.schema.json#/$defs/call_recording_deletion_audit`。删除完成时 MUST 产出或引用 `ak.schema.erasure_receipt.v1`（可作为 `ak.audit.erasure_receipt` durable event），并把 `erasure_receipt_ref` 绑定到 deletion audit；因 legal hold 阻塞时 MUST 记录 `outcome="blocked_by_legal_hold"` 与 `legal_hold_ref`，不得伪造成已删除。
- **客户端二次确认**:录制 / 转写进入捕获态只能由 `ak.call.recording.start` 完成；接受该 Event 前 MUST 取得用户的第二次显式同意，并将事实记入 `payload.result.retention.consent_confirmed=true`。reducer MUST 原子验证该事实并写入独立 result cell，缺失或不为 true 时 MUST `failed_precondition` `reason_code="recording_consent_required"`；`ak.call.state` 不得提交 `to="recording"` / `to="transcribing"` 绕过 start gate。
- **`consent_confirmed` 的保证类别（normative，诚实标注）**：`consent_confirmed=true` 是**流程性约束**，**不是**密码学同意证明——它由发起方客户端单方面置真，协议层无法强制其真实性（与 audited-e2ee `disclosed_policy` 同类：声明 / 留痕但不提供硬强制）。实现、UI、采购或合规文案 MUST NOT 把 `consent_confirmed=true` 表述为"已获得（被录制方的）密码学同意"或等价措辞，避免 false-positive 合规声明；该字段只表示"发起方声明已在本端取得用户二次确认"。
- **per-participant consent acknowledgment（更强合规 profile，normative）**：每个被录制方设备签名的 consent acknowledgment，其 signing input MUST 覆盖 `(call_id, recording_artifact_ref 或 capture epoch, consenting_actor_id, consenting_device_id, consented_at)`，签名身份按 [`device-lifecycle.md` §8.2/§8.3](../crypto-media/device-lifecycle.md) 的设备验签公钥目录解析并 fail-closed 验证。`security_class=high-confidentiality`、minimal-metadata Realm、或启用 attested / disclosed audit profile 的 Realm MUST 启用该门禁；其它 Realm MAY 启用。启用时，reducer MUST 对缺少任一当前被录制方有效 acknowledgment 的捕获态 `failed_precondition` `reason_code="recording_consent_required"`，且成员加入、设备切换或 capture epoch 改变后 MUST 重新取得 ack 后才能继续捕获。该签名集合是 `disclosed_policy` 之上的 `attested`-类强保证，可作为可审计同意证据。未启用该 profile 的部署仍只具备上一条的流程性保证，不得声称等价。
- retention 字段是对应 `recording_transition.result` / `transcript_transition.result` 的子对象，与 §4.2 捕获态机正交；它只约束 artifact 生命周期，不改变通话主状态。

## 6. P2P→SFU 升级（normative）

通话可以 P2P 起步（`mode="p2p"`），但当并发参与者人数 **> 2** 时 MUST 从 P2P 收敛到 SFU。

**并发升级收敛性（normative）**：分布式下各设备对"将达 3 人"的本地观测可能不同步，因而多台设备可能并发发起升级。这**不**产生 split-brain：升级 MUST 复用 [`media-service-binding.md` §5](./media-service-binding.md) 的 deterministic, no-vote focus 选举（由 oldest_membership 的 `foci_preferred[0]` 确定性选出 `session_focus`），且 `session_focus` 为 write-once（本文 §6 第 5 条 / §4.1，由 `ak.component.call.focus.v1` 的 `cas_register` CAS precondition 表达），任意子集设备并发发起的升级最终都被同一 `session_focus` 值吸收——首个被接受的 CAS 写入定锚，其余并发 CAS 收敛到同值或以 `session_focus_already_committed` 失败。因此并发升级收敛到同一 SFU focus，不依赖各设备观测同步，也不引入投票或 leader 选举。

触发与协商规则:

1. **触发条件**:任一参与设备观察到当前 active 参与者(已 accepted answer 的 leg)将达到 3 人时,MUST 发起升级，不得继续以 P2P / full-mesh 承载 3 人以上(`mesh` 仅 SHOULD 用于 3–4 人且不作为默认，见 §2)。
2. **focus 协商**:升级 MUST 复用 [`media-service-binding.md` §5](./media-service-binding.md) 的 deterministic, no-vote focus 选举——由 oldest_membership 的 `foci_preferred[0]` 选出 `session_focus` 并写入首个携带 `focus={mode:"sfu",session_focus}` 的 `ak.call.state`。升级**不**引入新的投票或 leader 选举路径。
3. **加入信令**:各设备通过 `ak.call.signal{signal_kind=focus_join}`(见 [`webrtc-signaling.md` §5](./webrtc-signaling.md))向选定 focus 迁移媒体；原 P2P leg 在所有参与者完成 `focus_join` 后 MUST 优雅拆除，迁移期间不得丢媒体(参照 §4.2 credential refresh 的"保留旧 allocation 直到迁移完成"原则)。
4. **`mode` 写入**:升级落定后，下一条 `ak.call.state` 的 `focus.mode` MUST 写 `sfu`,且一旦 `session_focus` committed 即不可在本生命周期内回退到 `p2p`(回退 P2P 需新 call)。
5. **单调性**:`session_focus` 一经 committed 即 write-once——由 `ak.component.call.focus.v1` 的 CAS precondition 强制，改写 MUST 以 `session_focus_already_committed` 失败(见 §4.1);升级到 SFU 后人数回落到 2 人 MUST NOT 自动降级回 P2P。
6. **升级失败 / 迁移中断（normative）**:升级编排可能在三处失败——focus 不可达(选举出的 `session_focus` 无法建立媒体)、某设备 `focus_join` 中途失败、原 P2P leg 已拆除但 SFU leg 未建成的部分迁移态。处置规则:
   - **focus 不可达且无可选 focus**:发起方 MUST 保留旧 P2P/mesh leg(尚未拆除时)继续承载已有媒体，并 SHOULD 在新的 accepted basis 上以下一候选 focus 重试 [`media-service-binding.md` §5.1](./media-service-binding.md) 的选举(基于剩余 `foci_preferred`)；候选耗尽后，通话整体 MUST 提交 `state_transition={from:"active",to:"failed"}`(`reason_code="call_state_transition_invalid"` 不适用——这是终态推进，按 §4.2 `active → failed` 合法转换)，不得停留在"已拆 P2P 又无 SFU"的不可解释悬挂态。
   - **单设备 `focus_join` 失败**:不影响其它已迁移设备；该设备 SHOULD 重试 `focus_join`，持续失败则按本地策略以 `ak.call.signal{signal_kind=leave}` 退出本通话，通话 `state` 不因单设备迁移失败而回退。
   - **迁移期间不得丢媒体**:在所有参与者完成 `focus_join` **之前**,原 leg MUST NOT 被拆除(§6 第 3 条);若实现因故已提前拆除且 SFU 未建成,MUST 视为升级失败并按上面第一条处置(重试 focus 或转 `failed`),MUST NOT 静默丢弃通话状态。
   - `session_focus` 一旦 committed 即 write-once:升级失败重试只能在 `session_focus` 尚未 committed 时切换候选 focus;已 committed 后 focus 不可达只能转 `failed` 并由用户新建通话(§6 第 4 条回退 P2P 需新 call 同理)。

## 7. 通话摘要（normative）

通话到达终态(`state ∈ { ended, missed, failed, cancelled }`)后,SHOULD 写入一条 durable `ak.call.summary` event,作为无需重放 ephemeral 信令即可呈现的持久通话记录:

```json
{
  "kind": "ak.call.summary",
  "realm_id": "ak:realm:...",
  "payload": {
    "call_id": "ak:call:0196441c-0000-7000-8000-000000000000",
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

- `ak.call.summary` 写入 `ak.component.call.summary.v1` cell,`cell_subject = payload.call_id`,lattice 为 `cas_register`、`bottom=reject`(write-once;divergent 重写 MUST `call_summary_invalid`)。
- `final_state` MUST 是某终态，且该 `call_id` 的 `ak:cell:ak.component.call.state.v1:<call_id>` MUST 已存在终态 head;否则 reducer MUST `failed_precondition` `reason_code="call_summary_invalid"`。该前置只看 `state` 轴 cell——某段捕获 cell 处于 `⊥` 或未终结 MUST NOT 阻止 summary 写入。
- `recording_state` / `transcript_state` 是终态时刻从各捕获段 cell（`ak.component.call.recording.v1` / `ak.component.call.transcript.v1`）镜像的**投影字段**；缺省表示未录制 / 未转写。通话可有多段捕获，因此这两个字段只是给 UI 的摘要投影，MUST NOT 被用作授权判据或任何状态派生输入——需要逐段真相时 MUST 读对应段的 capture cell。多段并存时该投影取哪一段由实现选择且 MUST NOT 进入 conformance 断言。

**字段必填 / nullable 语义（normative）**:`ak.call.summary` payload 字段约束如下，reducer / consumer MUST 按此校验，不一致 `schema_violation`:

| 字段 | 必填 | nullable | 说明 |
| --- | --- | --- | --- |
| `call_id` | 是 | 否 | 引用对应 `ak.call.state` 的 call。 |
| `final_state` | 是 | 否 | MUST ∈ 终态集合且与现存终态 head 一致(见上)。 |
| `mode` | 是 | 否 | 通话最终 `mode`。 |
| `started_at` | 否 | 是 | 通话从未进入 `active`(如 `final_state ∈ { missed, cancelled }`)时 MUST 为 `null`;曾 `active` 时 SHOULD 填实际开始时刻。 |
| `ended_at` | 否 | 是 | `final_state="ended"` 时 SHOULD 填结束时刻;`missed` / `cancelled` / `failed` 等非正常结束态 MUST 为 `null`(无明确"结束"时刻)。 |
| `duration_ms` | 否 | 是 | 仅当 `started_at` 与 `ended_at` 均非 `null` 时 MUST 等于二者之差；否则 MUST 为 `null`。 |
| `peak_participant_count` | 否 | 否 | 整数，缺省 `0`；上限同 §4.1 effective roster（≤ 1000）。 |
| `distinct_participant_count` | 否 | 否 | 整数，缺省 `0`，MUST ≥ `peak_participant_count`。 |
| `recording_state` | 否 | 否 | 缺省=未录制(见上)。 |
| `transcript_state` | 否 | 否 | 缺省=未转写(见上)。 |
- 写入 `ak.call.summary` 需要 `ak.call.join`(参见 [`../../artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json));它不替代 `ak.call.state` 终态，而是其上的 durable 摘要投影。
