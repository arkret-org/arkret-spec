---
title: Media Service Binding
status: candidate
normative: true
stability: v1
updated: 2026-06-04
sidebar:
  label: Media Service Binding
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标与范围

本文件定义 Cokret 多人会议的 **transport-agnostic 媒体服务 backend 绑定**：媒体服务发现（`ck.realm.media_service` 的 multi-focus 描述符）、token / participant binding 兑换、focus 选举与 session 持久化、SFU 权限与 participant identity 交叉校验，以及媒体 E2EE 帧密钥注入与治理绑定。LiveKit / mediasoup / Janus / cokret-native / MoQ-relay 都作为可替换 backend 通过 `foci[].type` 区分，具体 wire 见 [`bindings/<type>.md`](./bindings/) 附录。

边界：

- ephemeral 信令（offer/answer/candidate、ICE/TURN 发现与刷新、一对一通话、推送）见 [`webrtc-signaling.md`](./webrtc-signaling.md)。
- durable 会议状态（`ck.call.state` payload、状态机、participant 与录制生命周期）见 [`call-state.md`](./call-state.md)。

## 2. Realtime Media Server

`ck.realm.media_service` 把媒体服务声明为 **multi-focus 列表 + transport-agnostic backend 描述符**。协议层永不规定 SFU 内部协议；LiveKit / mediasoup / Janus / cokret-native / MoQ-relay 都作为可替换 backend 通过 `foci[].type` 区分，具体 wire 见 [`bindings/<type>.md`](./bindings/) 附录。

```json
{
  "kind": "ck.realm.media_service",
  "payload": {
    "service_id": "did:web:media.example.com",
    "modes": [
      "turn",
      "sfu"
    ],
    "ice_config_endpoint": "https://media.example.com/_cokret/self/rtc/ice-config",
    "foci": [
      {
        "focus_id": "fra-1",
        "type": "livekit",
        "region": "eu-fra",
        "token_endpoint": "https://media.example.com/_cokret/self/rtc/token",
        "connect_url": "wss://livekit-fra.example.com",
        "capabilities": ["audio", "video", "screen", "e2ee_sframe"],
        "health_endpoint": "https://media.example.com/_cokret/self/rtc/health/fra-1"
      },
      {
        "focus_id": "us-east-1",
        "type": "livekit",
        "region": "us-east",
        "token_endpoint": "https://media.example.com/_cokret/self/rtc/token",
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

- `foci[].focus_id`：focus 在该 Realm media service 内的稳定 ID；进入签名 canonical bytes 与 `session_focus` 选举（见 [`call-state.md` §4.1](./call-state.md)）。
- `foci[].type`：backend binding 标识。v1 注册值：`livekit`、`mediasoup`、`janus`、`cokret-native`、`moq-relay`（实验保留位，v1 周期内不提供 normative binding）。客户端遇到未知或 unsupported `type` MUST fail closed（错误码 `unknown_focus_type`），不得尝试把 token 交给任意 SDK。
- `foci[].token_endpoint`：token 兑换端点；所有 backend 共用同一抽象（见 §3），差异只在 `backend_token` 形态。
- `foci[].connect_url`：backend 连接入口；具体协议由 type-specific 附录定义。
- `foci[].capabilities[]`：该 focus 支持的能力子集，用于客户端能力协商。
- `foci[].health_endpoint`（optional）：客户端预检 endpoint，返回 `200` + `{"status":"ok","load":<0..1>}`。**只用于尚未 commit `session_focus` 前**排序本地 `foci_preferred`；一旦 `ck.call.state.session_focus` 已存在，connect 失败 MUST 暴露为 focus 不可用，不得静默切到另一 focus（`session_focus_no_split_brain`）。
- `foci[].cascade_group`（optional）：声明属于同一 backend cluster 的 focus 集合；客户端可据此向用户披露"跨区域会议由 backend 内部级联"。协议层不规范 SFU-to-SFU cascading 协议；每个 backend 自行实现 mesh，正式 Cokret wire 只公开 `foci[].cascade_group` 与用户可见披露语义。

`ck.realm.media_service` MUST 声明非空 `foci[]`。只提供单个 `sfu_endpoint` 或缺少 `foci[]` 的 payload MUST fail closed，返回 `schema_violation` 或 `failed_precondition`，原因码 `media_service_foci_required`；服务端不得在实时路径中自动补写、normalize 或推断 focus。

修改该 state event 需要 `ck.call.configure_media_service` 或 `ck.policy.manage` capability。

## 3. Token Exchange (normative)

会议加入前，客户端 MUST 先向 `foci[].token_endpoint` 兑换 backend 凭证；issuer 是 Cokret-side 授权组件，对协议层不透明的 `backend_token` 由 backend SDK 解析。Token endpoint 等价于 [MSC4195 `lk-jwt-service`](https://github.com/element-hq/lk-jwt-service)，但绑定到 Cokret 的 capability / Realm policy / MLS governance binding。

请求：

```http
POST {token_endpoint}
Authorization: <device proof | bearer>
Content-Type: application/json

{
  "realm_id": "ck:realm:...",
  "call_id": "ck:call:...",
  "actor_id": "did:web:alice.example.com",
  "device_id": "ck:device:...",
  "focus_id": "fra-1",
  "capability_refs": ["ck:grant:..."],
  "desired_media": { "audio": true, "video": true, "screen": false }
}
```

响应（`scheme="ck.media.participant_binding.v1"` 是 v1 唯一 participant binding scheme）：

```json
{
  "focus_id": "fra-1",
  "type": "livekit",
  "connect_url": "wss://livekit-fra.example.com",
  "backend_token": "<opaque to Cokret protocol — type-specific>",
  "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
  "participant_binding": {
    "scheme": "ck.media.participant_binding.v1",
    "realm_id": "ck:realm:...",
    "call_id": "ck:call:...",
    "focus_id": "fra-1",
    "actor_id": "did:web:alice.example.com",
    "device_id": "ck:device:...",
    "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
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

- **TTL 短期化**：`backend_token` / `participant_binding` `expires_at` 的硬上限 MUST ≤ 600s（10 分钟）；推荐上限 SHOULD ≤ 300s。过期前客户端 MUST 重新兑换；backend token 一旦泄漏在 TTL 内通常不可吊销（除非 backend 提供 revocation list），短 TTL 是工程兜底。
- **Token issuer DID 锚定**：`service_signature.kid` 与 `participant_binding.issuer_kid` MUST 解析到一个出现在当前 epoch `ck.realm.media_service.service_id` 的 service DID；客户端 MUST 拒绝来自未授权 DID 的 token，错误码 `token_issuer_unauthorised`。该规则把 token 签发权与 Realm policy 锁定，防止任意 service 凭空铸造 join token。
- **`participant_identity` 形态**：作为 SFU-local 短期 handle，scope 限 `(call_id, focus_id, sfu_did)`；MUST NOT 携带可关联到长期 actor 身份的可识别信息（与 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md) pairwise pseudonym 规则对齐），且 MUST 至少绑定 `(realm_id, call_id, focus_id, device_id, issuer_service_did, issued_at_bucket)` 派生。
- **`participant_identity` 传播边界**：因为它本身不携带 actor 链接信息，客户端 **MUST** 把它写入 `ck.call.state.participants[].participant_identity`（用于 §7 cross-check）——这条嵌入是 Realm-encrypted control state，不构成 actor-身份外泄。但 `participant_identity` MUST NOT 进入下列三类 surface：(a) 任何 plaintext audit log / 服务方 access log（包括 backend SFU 自身的日志）；(b) 任何 unencrypted ephemeral / push / telemetry 通道；(c) backend 一侧对外的 metrics、tracing 标签或 cross-tenant 数据导出。Backend 内部允许保留它作为 SFU-local routing handle，但不应跨 call leg / 跨 tenant 复用。
- **`participant_binding` 是 token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺**。客户端 MUST 先验证该 binding，再把它写入 / 对照 `ck.call.state` membership（见 [`call-state.md` §4](./call-state.md)）。backend 只看到 `participant_identity` 与 `backend_token`，不应获得长期 actor 身份。

Token issuer MUST 在签发前校验：

- 调用者 device proof / bearer 有效，未 revoked。
- Actor 在 `realm_id` 拥有 `ck.call.join` capability；`desired_media` 不超过授权（`ck.call.screen_share` 等子 capability 检查）。
- Realm policy 允许该 `focus_id`（即 focus 出现在当前 `ck.realm.media_service.foci[]` 中）。
- 如果 `ck.call.state.session_focus` 已存在，请求的 `focus_id` 与其完全一致；不一致 MUST 返回 `focus_mismatch`。
- call state 允许新 participant；且按分层 predicate 校验该 `(actor_id, device_id)`：actor 在 `realm_id` 的 Realm membership 为 `join`（若 scoped 到 Circle 则同时为该 Circle 活跃成员）、account status 不为 `suspended` / `deactivated` / `erasure_pending`、`device_id` 的 device grant 未 revoked。
- MLS governance binding `policy_root` 与 `ck.realm.media_service` 当前 epoch 一致（防 stale policy）；不一致返回 `mls_governance_binding_stale`。
- 如果 backend 将解密媒体（`media_service_decrypts=true`），完整执行 §8.2 的三层校验。

## 4. SFU Service

SFU 在 v1 通过 [§2](#2-realtime-media-server) 的 `foci[]` 声明，每个 focus 通过 `type` 选择具体 backend binding：

- `type="livekit"`：见 [`bindings/livekit.md`](./bindings/livekit.md)。
- `type="cokret-native"`：见 [`bindings/cokret-native.md`](./bindings/cokret-native.md)（reference impl，不推荐生产使用）。
- `type="mediasoup"` / `type="janus"` / `type="moq-relay"`：保留位，v1 周期内不提供 normative binding；客户端遇到 unsupported `type` MUST fail closed，错误码 `unknown_focus_type`。

不论 backend 类型，client→backend 媒体协商前 MUST 先完成 [§3 Token Exchange](#3-token-exchange-normative)；具体 `backend_token` 形态、connect handshake、SDP 协商由 type-specific 附录定义。下面的 §5 / §6 / §7 是跨 backend 通用约束。

## 5. Focus Selection 与 Session 持久化（normative）

会议第一次 join 时由客户端排序 `foci_preferred[]` 写入 `ck.call.state.participants[].foci_preferred`；之后用 **deterministic, no-vote** 规则收敛为单一 `session_focus`：

1. 若 `ck.call.state.session_focus` 已存在，它就是唯一 authoritative focus；客户端和 token issuer MUST 使用它。
2. 若 `session_focus` 尚不存在，收集所有当前 active member 的 `(joined_at, actor_id, device_id, foci_preferred)` 元组；按 `(joined_at, actor_id, device_id)` 升序，**oldest_membership 的 `foci_preferred[0]` 被写入 `session_focus`**。
3. 后加入者 MUST 使用同一 `session_focus`，无论自己的偏好；如果该 focus 在自己的 preferred 列表中不存在，客户端 MAY 拒绝加入（fail closed），错误码 `focus_unavailable_for_client`。
4. Token issuer MUST 拒绝任何 `focus_id != session_focus` 的 token exchange，错误码 `focus_mismatch`；该规则优先于 health check、region preference 和 load balancing。
5. 当 oldest member 离开，focus **不自动迁移**（避免媒体路径中断）；session 持续到所有人离开后才重置。v1 不提供 in-session focus migration。

## 6. SFU 权限

SFU MUST verify:

- Realm media service policy allows this `(focus_id, service_id)` 组合（即 focus 出现在当前 `ck.realm.media_service.foci[]`）。
- actor has `ck.call.join`（capability registry canonical 命名，参见 [`../authz/capabilities.md`](../authz/capabilities.md) §5）。
- actor/device is not revoked。
- call state accepts new participants。
- media request does not exceed grants, e.g. screen share requires `ck.call.screen_share`。

客户端 MUST 校验：

- token issuer service DID 出现在当前 `ck.realm.media_service.service_id` / `foci[].token_endpoint` 锚定的 service DID 列表；
- token exchange 响应的 `service_signature` 与 `participant_binding.sig` 通过；
- backend 通知 "X 加入会议" 时携带的 `participant_identity` 与 `ck.call.state.participants[].participant_identity` 一致（见 §7 cross-check）。

## 7. Participant Identity 交叉校验（normative）

backend "X 加入会议" 通知到达客户端时，客户端 MUST：

1. 从 backend 通知中提取 `participant_identity`。
2. 在当前 `ck.call.state.participants[]` 中查找同一 `participant_identity`。
3. 验证该 participant entry 内的 `participant_binding` 签名（[§3](#3-token-exchange-normative)），确认它覆盖同一 `(realm_id, call_id, session_focus, actor_id, device_id, participant_identity)`。
4. 不匹配或签名无效 → 拒绝为该 participant 建立媒体流（不收音、不订阅 video），错误码 `participant_identity_unrecognised`。

这道闸门防止 backend 单方面 "塞入" 未经 Realm 授权的参与者——backend 运营方误配置、被入侵或恶意 inject 都无法绕过 Cokret-side `ck.call.state` 真源。

## 8. E2EE with SFU

SFU 模式 SHOULD 使用 WebRTC Insertable Streams / SFrame 或等价机制实现端到端媒体加密。SFU 可转发 RTP 包和处理转发层 metadata，但不应获得明文媒体。

若 SFU 或 MCU 会解密媒体，客户端 MUST 显示明确安全边界，并且 Realm policy MUST 允许 `media_service_decrypts=true`。

### 8.1 E2EE Key Injection 通用契约（normative）

无论 backend 自身是否支持 E2EE，所有 binding 附录的 E2EE 章节 MUST 规定一个最小契约，使得 **客户端侧 binding adapter / media SDK** 能从 Cokret 协议层接收 frame key，而不从 backend 自带密钥分发机制取。最小契约：

```text
inject_frame_key(key_bytes: 32-byte secret,
                 epoch_id: u64,
                 sender_binding: canonical_json{
                   realm_id, call_id, focus_id,
                   participant_identity, device_id
                 },
                 rotation_trigger: enum{member_join, member_leave, manual, scheduled})
```

约束：

- `key_bytes` MUST 由 Cokret MLS exporter 派生，**label 固定为 ASCII 字符串 `"cx-rtc-frame-key/v1"`**（length=19 bytes，无 trailing newline；RFC 9420 §8 `MLS-Exporter` 的 `Label`，`KDF.Nh` 长度 32 bytes）。`Context` MUST 是 canonical JSON bytes of exactly `{realm_id, call_id, focus_id, epoch_id, participant_identity, device_id}`，其中 `participant_identity` / `device_id` 来自已验证的 `ck.call.state.participants[]` 与 `participant_binding`。`Context = ""`、缺少 sender 字段或只绑定 epoch 的派生 MUST fail closed(`e2ee_key_source_unauthorised`)。`cx-rtc-frame-key/v1` / `cx-rtc-recording-key/v1` 的 `cx-` 前缀是**有意保留的 grandfathered 稳定 wire label**(媒体绑定早期遗留命名，作为密钥派生的安全域分离参数),并非待清理的命名残留；实现 MUST NOT 私自将其迁移为 `ck-` 形态或与其它 label 混用。该 label 不在 conformance 阶段再议——任何变更属于 wire-breaking，必须开新 profile。
- `epoch_id` 与 Realm MLS epoch 一一对应。
- backend SDK / adapter 内部如何把该 sender-bound key 映射到 SFrame / 私有帧加密格式由附录指定，但 **MUST NOT** 接受任何非该接口的 key 源（如 backend 自带 KMS、自生成 random key）。SFrame KID / key slot MUST 区分同一 epoch 内的不同 sender；若 adapter 无法为 active sender 集合提供无冲突映射，客户端 MUST 拒绝启用该 binding。除非 Realm policy 明确允许 `media_service_decrypts=true` 且完成 §8.2 三层校验，`key_bytes` MUST NOT 被发送给远端 SFU / MCU。
- Conformance negative vector `ck.vector.media_binding.e2ee_key_source.v1`：backend 用自家密钥 → 客户端 MUST 拒绝并报 `e2ee_key_source_unauthorised`。

Conformance vectors for the full media binding framework：

- `ck.vector.media_binding.focus_selection_oldest_membership.v1` — §5 oldest_membership 选举正确性。
- `ck.vector.media_binding.session_focus_no_split_brain.v1` — `session_focus` 写入后 connect 失败 MUST 暴露为不可用，不静默切 focus。
- `ck.vector.media_binding.token_exchange_minimal.v1` — §3 token exchange 最小字段集 + TTL ≤ 600s。
- `ck.vector.media_binding.token_issuer_unauthorised.v1` — issuer DID 不在 service_id 锚定列表时拒绝。
- `ck.vector.media_binding.participant_binding_required.v1` — 缺失或签名无效的 `participant_binding` 必须拒绝。
- `ck.vector.media_binding.unknown_type_fail_closed.v1` — §2 未知 `foci[].type` MUST fail closed。
- `ck.vector.media_binding.participant_identity_unrecognised.v1` — §7 backend 通知的 participant 不在 `ck.call.state` 时拒绝该流。
- `ck.vector.media_binding.recording_artifact_via_cokret_blob.v1` — [`call-state.md` §5](./call-state.md) backend-generated recording 必须经 Cokret blob pipeline。
- `ck.vector.media_binding.recording_exporter_label.v1` — backend-generated recording 必须使用 `"cx-rtc-recording-key/v1"` 与绑定 recording transcript 的 Context，不得复用 SFrame key label。

### 8.2 治理绑定（normative）

**三层关系**: `ck.realm.media_service` declares SFU existence; `plaintext_visible_services` grants decryption authority; `ck.realm.policy_components.media_service_decrypts=true` carries the boolean toggle — 三者 MUST 同时成立才能让 media service 解密。

`media_service_decrypts=true` **不**是一个可单独由 SFU 服务自报或客户端配置的开关。它 MUST 同时满足下列约束，否则客户端 MUST 拒绝加入会议、SFU MUST 拒绝媒体协商：

1. **进入 `ck.realm.policy_components`**：`media_service_decrypts=true` MUST 由一条 `ck.realm.policy_components`（或对应 Realm policy facet event）显式写入，受 capability `ck.realm.policy.manage` 控制，并随 Realm policy `policy_root` 一同被 [`encryption-and-audit.md` §2.5](./encryption-and-audit.md) 的 MLS governance binding 覆盖。policy_root 未包含该开关时 MUST 视为未开启。
2. **进入 `plaintext_visible_services`**：解密媒体的 SFU / MCU service DID MUST 在 Realm policy 的 `plaintext_visible_services[]`（或等价 media plaintext service policy）中显式列出，并标 `purpose=media_plaintext`。仅出现在 `media_services[]` 而未列入 `plaintext_visible_services[]` 的服务 MUST 被视为禁止解密媒体的 SFU；其试图协商解密角色时 MUST 返回 `media_plaintext_service_not_authorised`。
3. **MLS Governance Binding 覆盖**：成员在 join 前 MUST 校验当前 epoch 的 governance binding `policy_root` 涵盖前两条规则的 cell value；不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商（不能依赖 SFU 单方面声明）。
4. **Downgrade 攻击拒绝**：从 `media_service_decrypts=false` 切换到 `true`（或反向）MUST 走 `ck.realm.policy_components` 正常路径并伴随客户端 UI 显著二次确认；不允许 SFU 直接以 OOB 控制信号宣告自己已"获得解密权"。在 governance binding 尚未 commit 新 policy_root 的窗口内，客户端 MUST 沿用旧 policy 视图判定，禁止根据 OOB 字段提前授权。
5. **进入成员可见 metadata**：`media_service_decrypts=true` 这一"该 Realm 媒体可被服务解密"的事实 MUST 进入 governance binding 覆盖的成员可见 metadata（如 `discussion_metadata_digest`），使任意成员无需依赖客户端 UI 即可从 MLS transcript 独立复算该事实。该 digest MUST 由前 1–3 条所覆盖的 policy cell value 确定性派生；成员本地复算结果与 governance binding 覆盖值不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商。
6. **Conformance negative vector** `ck.vector.webrtc.media_plaintext_downgrade.v1` 必须覆盖：(a) policy_root 未覆盖 `media_service_decrypts` ⇒ 拒绝加入；(b) SFU 未列入 `plaintext_visible_services` 而协商解密 ⇒ 拒绝媒体；(c) UI 未显示警示 ⇒ 拒绝加入；(d) 成员从 MLS transcript 独立复算的 `media_service_decrypts` 事实与 governance binding 覆盖的成员可见 metadata 不一致 ⇒ 拒绝媒体协商。

实际效果：SFU / MCU 不能在 MLS transcript 之外单独变更为可解密媒体的一方。任何看起来"切换成功"但未被 governance binding 覆盖的状态都是 attack，必须 fail closed。
