---
title: LiveKit Backend Binding
status: candidate
normative: true
stability: v1
profile: ck.profile.media_service_binding.livekit.v1
updated: 2026-06-10
sidebar:
  label: LiveKit Binding
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`conformance/normative-language.md`](../../../zh/conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 范围

本附录定义 `ck.realm.media_service.foci[].type = "livekit"` 的 backend binding 细节。它 **不替代** [`../media-service-binding.md`](../media-service-binding.md) 与 [`../call-state.md`](../call-state.md)——参见 media-service-binding §2（multi-focus schema）、§3（token exchange 通用契约）、§5（focus selection）、§7（participant identity 校验）、§8.1（E2EE key injection 通用契约），及 call-state §4（ck.call.state 字段）。

声明 `ck.profile.media_service_binding.livekit.v1` 的部署 MUST 同时声明上游 `ck.profile.media_service_binding.v1`。本 binding 在 v1 周期内为 **optional** sub-profile；core conformance 不强制实现 LiveKit binding。

## 2. Token Claims

`backend_token` 是 LiveKit JWT（[LiveKit Authentication](https://docs.livekit.io/home/get-started/authentication/)），由 Cokret-side token issuer 用 LiveKit API Key/Secret 派生。Issuer MUST 注入下列 LiveKit standard claims：

| LiveKit claim | Cokret 字段映射 | 约束 |
| --- | --- | --- |
| `iss` | LiveKit API Key | issuer 标识；MUST 与 Realm 声明的 LiveKit deployment 一致 |
| `sub` | `participant_identity` | LiveKit participant identity；MUST 与响应顶层 `participant_identity` 一致 |
| `nbf` / `iat` | token 签发时刻 | — |
| `exp` | `expires_at` Unix epoch | MUST ≤ 600s after `iat`（media-service-binding §3 TTL 上限） |
| `name` | optional display label | MUST NOT 携带可关联 actor 身份信息（与 [`../media-service-binding.md` §3](../media-service-binding.md) pairwise pseudonym 对齐）；推荐留空或使用 `participant_identity` |
| `video.room` | `call_id` | MUST 等于请求的 `call_id`；LiveKit room name 由 issuer 派生（建议 `ck_call_<call_id_short_hash>`，不暴露 raw Realm/call id 到 LiveKit logs） |
| `video.roomJoin` | `true` | join 权限 |
| `video.canPublish` | `desired_media.audio ∨ video ∨ screen` | issuer 按 capability 派生 |
| `video.canPublishSources[]` | `["microphone","camera","screen_share"]` 子集 | 与 `ck.call.screen_share` 等子 capability 对齐 |
| `video.canSubscribe` | `true` | 接收者权限 |
| `video.hidden` | `false` | Cokret 不使用 LiveKit hidden participant |
| `video.recorder` | `false` | recording 走 Cokret blob pipeline（§5），不通过 LiveKit recorder claim |

Issuer MUST NOT 注入：

- `metadata`：LiveKit 允许任意 JSON 字符串，但携带 `metadata` 会绕过 Cokret `participant_binding` 真源。Cokret participant metadata MUST 通过 `ck.call.state` 写入。
- `video.canUpdateOwnMetadata`：禁止 client 改写 LiveKit metadata。

## 3. Connect Handshake

客户端用 `connect_url`（典型 `wss://livekit-<region>.example.com`）与 `backend_token` 建立 WebSocket。LiveKit SDK 处理 SDP 协商、ICE、SFrame 协商等内部协议；Cokret 协议层不规定具体 wire 形态。

约束：

- 客户端 SDK 接到 LiveKit `ParticipantConnected` 事件时，MUST 按 [`../media-service-binding.md` §7](../media-service-binding.md) 做 participant identity 交叉校验：以 LiveKit `participant.identity` 为索引在 `ck.call.state.participants[]` 找匹配项，验证 `participant_binding` 签名。未匹配或签名失败 → 拒绝建立媒体流，错误码 `participant_identity_unrecognised`。
- 客户端 MUST NOT 信任 LiveKit SDK 透传的 `participant.name`、`metadata` 或其它字段作为 actor 身份判定来源；唯一权威来源是 `ck.call.state` + `participant_binding`。

## 4. E2EE Key Injection

LiveKit 通过 [SFrame](https://www.rfc-editor.org/rfc/rfc9605.html) 实现 frame-level E2EE。Cokret-LiveKit binding 的 key 注入按 [`../media-service-binding.md` §8.1](../media-service-binding.md) 通用契约：

1. 客户端 binding adapter 从 Cokret MLS exporter 为每个 sender 派生 `key_bytes`（label `"ck-rtc-frame-key/v1"`，`Context=canonical_json({realm_id, call_id, focus_id, epoch_id, participant_identity, device_id})`，`KDF.Nh=32`）。
2. 调 LiveKit SDK 的 `Room.setE2EEEnabled(true)` 并通过 `keyProvider` 注入 `key_bytes`。
3. MLS epoch 或 participant set 变化 → 调 `keyProvider.setKey(keyBytes, keyIndex=<sender-bound-key-index>)` 触发 LiveKit SFrame ratchet。`keyIndex` MUST 是当前 active `(epoch_id, participant_identity)` 集合内无冲突的 adapter-local 映射；MUST NOT 仅用 `epoch_id % 256`。
4. backend SDK 若试图通过 LiveKit Cloud 的 internal key distribution（如 LiveKit Cloud E2EE Token Service）注入 key，客户端 MUST 拒绝，错误码 `e2ee_key_source_unauthorised`。

`media_service_decrypts=true` 时（少数合规部署）：客户端按 [`../media-service-binding.md` §8.2](../media-service-binding.md) 完成三层校验，且 MUST 通过 Cokret-controlled keying path 把 `key_bytes` 提交给 LiveKit decryption oracle；不得使用 LiveKit Cloud 自动 key escrow。

## 5. Capability Mapping

| Cokret `desired_media` | LiveKit claim |
| --- | --- |
| `audio: true` | `video.canPublishSources` 含 `microphone` |
| `video: true` | `video.canPublishSources` 含 `camera` |
| `screen: true` + `ck.call.screen_share` | `video.canPublishSources` 含 `screen_share` |
| `ck.call.record` | recording 走 §6 不签 LiveKit recorder claim |
| `ck.call.moderate` | issuer MAY 派生 `video.roomAdmin=true`，但生效仅限 LiveKit-level moderation（mute remote、disconnect），不替代 Cokret `ck.call.signal` moderation |

## 6. Recording

Cokret-LiveKit 部署 MAY 使用 LiveKit Egress 触发录制，但 Egress endpoint MUST 是 Cokret-side proxy；录制 artifact 流向严格按 [`../call-state.md` §5](../call-state.md) 与 [`../media-service-binding.md` §8.1](../media-service-binding.md)：

- Egress destination MUST 是 Cokret media service 的 authenticated upload endpoint；不得 LiveKit Cloud 直传 S3 / GCS。
- 录制加密 key 来自 MLS exporter，label 固定为 ASCII 字符串 `"ck-rtc-recording-key/v1"`（与 SFrame `"ck-rtc-frame-key/v1"` 区分；`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id})`，`KDF.Nh=32`）。实现若复用 SFrame label、空 Context，或接受 LiveKit/KMS 自行生成的 recording key，MUST fail closed；LiveKit 不持久化明文。
- 录制完成后通过 `ck.call.state` 发布 `recording_state="ready"` + content digest。
- 客户端检测到 LiveKit Egress 配置指向非 Cokret endpoint → fail closed `recording_artifact_pipeline_bypassed`。
- 转写(`capture_kind="transcript"`)走同一 Egress / Cokret blob 路径，但加密 key label 固定为 `"ck-rtc-transcript-key/v1"`(`Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, transcript_start_event_id})`,`KDF.Nh=32`),与录制 / SFrame label 区分；复用其它 label、空 Context 或 backend 自生成 transcript key MUST fail closed `transcription_artifact_pipeline_bypassed`。转写完成后通过 `ck.call.state` 发布 `transcript_state="ready"`。见 [`../call-state.md` §5.1](../call-state.md)。

## 7. Cascading

LiveKit Cloud SFU mesh 是 backend-internal 概念；Cokret 通过 `foci[].cascade_group` 仅向用户披露 "跨区域会议由 backend 内部级联，媒体延迟取决于 backend 配置"。协议层不规范 cascading wire 形态，也不暴露 LiveKit internal node 路由信息。

## 8. Failure Mode 映射

| LiveKit 失败 | Cokret 错误码 |
| --- | --- |
| LiveKit JWT signature invalid / expired | `proof_invalid`（token exchange 阶段）/ `token_expired` |
| `video.room` mismatch | `focus_mismatch`（如果 issuer 在 mismatch 时返回；否则客户端在 connect 阶段 fail closed） |
| LiveKit `ConnectionState.Disconnected` (auth) | 客户端 MUST 重新走 media-service-binding §3 token exchange，不得复用旧 token |
| LiveKit SFU not reachable | 按 [`../media-service-binding.md` §5](../media-service-binding.md) `session_focus` 持久化规则，**不静默切 focus**；暴露为 `focus_unavailable_for_client` |

## 9. Participant Identity 验证

按 §3 / [`../media-service-binding.md` §7](../media-service-binding.md)。LiveKit `Participant.identity` 即 Cokret `participant_identity`，由 token issuer 在 media-service-binding §3 响应里给出，并已被 `participant_binding` 签名覆盖。客户端 MUST 在 connect / track-published 事件上完整校验该 binding；MUST NOT 信任 LiveKit `Participant.metadata` 字段中可能携带的任何身份字符串。

## 10. Conformance Vectors

实现声明 `ck.profile.media_service_binding.livekit.v1` 时，至少通过 [`../../../zh/conformance/conformance-vectors.md`](../../../zh/conformance/conformance-vectors.md) 中的：

- `ck.vector.media_binding.focus_selection_oldest_membership.v1`
- `ck.vector.media_binding.session_focus_no_split_brain.v1`
- `ck.vector.media_binding.token_exchange_minimal.v1`
- `ck.vector.media_binding.token_issuer_unauthorised.v1`
- `ck.vector.media_binding.participant_binding_required.v1`
- `ck.vector.media_binding.unknown_type_fail_closed.v1`
- `ck.vector.media_binding.e2ee_key_source.v1`
- `ck.vector.media_binding.participant_identity_unrecognised.v1`
- `ck.vector.media_binding.recording_artifact_via_cokret_blob.v1`
- `ck.vector.media_binding.recording_exporter_label.v1`

LiveKit-specific vectors (JWT claim shape conformance、SFrame key injection cross-check) 在 v1 cycle 内非 normative；录制 exporter label 已由 `ck.vector.media_binding.recording_exporter_label.v1` 固定，任何 label/context 变更都必须开新 profile。

具体向量 fixture 与脚本由 [`../../../artifacts/registry/vector-registry.json`](../../../artifacts/registry/vector-registry.json) 编排。
