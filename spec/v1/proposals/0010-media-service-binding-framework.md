---
ckp: CKP-0010
title: Media Service Binding Framework（媒体服务 Backend 绑定框架）
status: accepted
created: 2026-05-27
accepted: 2026-05-27
merged_to:
  - spec/v1/zh/crypto-media/media-service-binding.md
  - spec/v1/zh/crypto-media/call-state.md
  - spec/v1/zh/crypto-media/bindings/livekit.md
  - spec/v1/zh/crypto-media/bindings/cokret-native.md
  - spec/v1/artifacts/registry/event-kind-registry.json
  - spec/v1/artifacts/registry/error-code-registry.json
  - spec/v1/artifacts/registry/operation-registry.json
  - spec/v1/artifacts/registry/vector-registry.json
  - spec/v1/artifacts/profiles/conformance-profiles.json
historical_only: true
normative_source: spec/v1/zh/crypto-media/media-service-binding.md
authors:
  - chris@acroidea.com
depends_on: []
discussion: <pending>
---

> **Status: accepted (merged 2026-05-27).** 本提案已合入 normative spec;`merged_to` 列出主要落地文件。
>
> This proposal file is retained as historical design rationale. Future updates to media service binding framework MUST land directly on `zh/crypto-media/media-service-binding.md`, `zh/crypto-media/call-state.md` and the `bindings/` directory, not here.
>
> 本提案不替代 [`spec/v1/zh/crypto-media/webrtc-signaling.md`](../zh/crypto-media/webrtc-signaling.md)，而是在其上方补一层 **transport-agnostic 的媒体服务发现、凭证交换与 focus 选择**抽象，让 LiveKit / mediasoup / Janus / 未来的 MoQ-relay 都可以作为可替换 backend，而不污染 Cokret 核心信令模型。

## 1. Summary

定义 `ck.profile.media_service_binding.v1`：把"媒体服务实例"从 Realm policy 中的单一 `sfu_endpoint` 字段升级为 **multi-focus 列表 + 抽象 backend 描述符**；定义统一的 **token exchange 端点契约**（Matrix MSC4195 `lk-jwt-service` 的等价物）；定义 **session focus 选择与持久化规则**（`oldest_membership` 模式）；并规定 **具体 backend binding 附录** 的写法（v1 给出 LiveKit binding 作为参考）。

设计目标是：**协议层永不规定 SFU 内部协议**；backend 替换不破坏 wire；MoQ 等未来 transport 通过新增 `type` 值接入而不破坏现有客户端。

## 2. Motivation

### 2.1 现状缺口

[`webrtc-signaling.md` §6.1](../zh/crypto-media/webrtc-signaling.md) 的 `ck.realm.media_service` 把 SFU 视为单实例 endpoint：

```json
{ "service_id": "did:webvh:z8MediaTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:media.example.com",
  "sfu_endpoint": "https://sfu.example.com",
  ... }
```

§10.1 的 SFU join request/response 假设客户端**已经知道**该 endpoint 的 wire 协议（Cokret 自定义信令）。这导致三个问题：

1. **无法直接复用主流 SFU 实现**。LiveKit、mediasoup、Janus 都有自己的客户端 SDK 与私有信令；强行让它们说 Cokret-native 信令意味着必须 fork 或写适配器。Matrix 的教训（[Waterfall](https://github.com/matrix-org/waterfall) 项目）说明自研 SFU 不可持续。
2. **缺多 focus 发现**。Realm 只能声明一个 SFU；跨区域、容灾、负载分担都无法表达。
3. **缺 focus 选择规则**。`focus_join`/`focus_leave` signal type 在 §7.2 已注册但语义未定，多 focus 场景下两个客户端可能选到不同 SFU，会议直接分裂。

### 2.2 借鉴对象

Matrix 走过的弯路给出明确答案（详见 [MSC4143 MatrixRTC](https://github.com/matrix-org/matrix-spec-proposals/pull/4143) + [MSC4195 LiveKit binding](https://github.com/matrix-org/matrix-spec-proposals/pull/4195)）：

- **不规定 SFU 内部协议** — 协议只规定 *发现 + 鉴权 token 交换 + 成员协调*，SFU 自己的信令是黑盒。
- **transport-agnostic** — MSC4143 不绑定 LiveKit；MSC4195 是它的第一个 binding 实例。
- **focus 选择用 `oldest_membership`** — 不发明选举协议，最早加入者的 preferred 列表首项胜出。
- **E2EE 密钥不走 backend 通道** — Matrix 用 `m.rtc.encryption_key`（Megolm 分发），Cokret 已经有等价物（governance binding + MLS exporter）。

### 2.3 为什么不直接采用 LiveKit binding

直接写 "Cokret-LiveKit binding" 会重复 Matrix 的耦合错误。LiveKit 现在是工程最优解，但：

- 2027+ MoQ（Media over QUIC，IETF moq-transport）成熟后，会议的 fan-out 层可能向其迁移。
- mediasoup、Janus 在特定部署形态（如自托管最小化、PSTN 桥接）下仍是合理选择。
- 协议层暴露 backend 私有细节会让未来替换变成 wire-breaking change。

正确做法：**协议层定义抽象（本提案），具体 binding 走附录**。

## 3. 设计不变量

1. **协议核心不感知 backend 协议** — Cokret 客户端**可以**完全不用 LiveKit SDK；某些 backend binding（如 LiveKit）允许实现方携带其官方 SDK，但 wire 协议层只看到 token 与 connect URL。
2. **Backend 不能获得 Realm 权限** — backend 是媒体路由黑盒，绝不参与 capability 决策；token issuer 是 Cokret-side 授权组件，必须按 Realm policy 执行校验。若 issuer 与 backend 同部署，也必须以 service DID 委托和最小授权边界隔离。
3. **E2EE 密钥分发与 backend 解耦** — 密钥继续走 [`webrtc-signaling.md` §10.3](../zh/crypto-media/webrtc-signaling.md) + governance binding；backend 即使支持自身 E2EE（如 LiveKit SFrame），密钥源 MUST 是 Cokret 协议层（MLS exporter 派生），不得使用 backend 自己的密钥分发机制。
4. **Multi-focus 但 session 内单一 backend** — 一个 call session 全局只用一个已持久化的 `session_focus`，避免媒体路径分裂；跨 focus 的 cascading 推给 backend 自身的 mesh 能力（如 LiveKit Cloud SFU mesh），不在协议层规范。
5. **Focus 选举无投票协议** — 用 `oldest_membership` 规则（最早加入者的 preferred 列表首项胜出），避免分布式共识复杂度。
6. **Backend 替换不破坏现有 wire** — 新 backend 通过新增 `type` 值接入；旧客户端遇到未知 `type` MUST 优雅降级（拒绝加入而非崩溃）。

## 4. 规格草案（outline）

### 4.1 升级 `ck.realm.media_service`

把现行单 endpoint 形态扩展为 multi-focus 列表（保持向后兼容：单 focus 是 N=1 的特例）：

```json
{
  "kind": "ck.realm.media_service",
  "payload": {
    "service_id": "did:webvh:z8MediaTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:media.example.com",
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
        "capabilities": ["audio", "video", "screen", "e2ee_sframe"]
      }
    ],
    "default_call_mode": "sfu",
    "allowed_call_modes": ["p2p", "sfu"],
    "recording_supported": false
  }
}
```

**关键字段语义**：

- `foci[].type` — backend binding 标识。v1 规范登记表：`livekit` | `mediasoup` | `janus` | `cokret-native` | `moq-relay`（保留位，experimental，v1 周期内不提供 normative binding；预留以避免未来 schema breakage）。`cokret-native` 是当前 §10.1 自定义 SFU 信令的形态，保留作 reference impl。
- `foci[].token_endpoint` — token 兑换端点（见 §4.2）。**所有 backend 共用同一抽象**，差异只在返回 payload 形态。
- `foci[].connect_url` — backend 连接入口（具体协议见 type-specific 附录）。
- `foci[].capabilities` — 该 focus 支持的能力子集，用于客户端能力协商。
- `foci[].health_endpoint` (optional) — 客户端预检 endpoint。返回 `200` + `{"status":"ok","load":<0..1>}` 表示可用。该 endpoint 只用于**尚未 commit `session_focus` 前**排序本地 `foci_preferred`；一旦 `ck.call.state.session_focus` 已存在，connect 失败 MUST 暴露为 focus 不可用，不得静默切到另一 focus 造成 split-brain。

### 4.2 Token Exchange 端点（normative，所有 backend 通用）

```http
POST {token_endpoint}
Authorization: <device proof | bearer>
Content-Type: application/json

{
  "realm_id": "ck:realm:...",
  "call_id": "ck:call:...",
  "actor_id": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example.com",
  "device_id": "ck:device:...",
  "focus_id": "fra-1",
  "capability_refs": ["ck:grant:..."],
  "desired_media": { "audio": true, "video": true, "screen": false }
}
```

响应：

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
    "actor_id": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example.com",
    "device_id": "ck:device:...",
    "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
    "issued_at": "2026-05-27T12:29:56Z",
    "expires_at": "2026-05-27T12:34:56Z",
    "issuer_kid": "did:webvh:z8MediaTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:media.example#key-1",
    "sig": "..."
  },
  "expires_at": "2026-05-27T12:34:56Z",
  "service_signature": { "kid": "did:webvh:z8MediaTnL4rP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:media.example#key-1", "sig": "..." }
}
```

**核心约束**：
- `backend_token` 对协议层不透明，由 backend SDK 解析。
- Token issuer MUST 在签发前完成 §4.4 的权限校验。
- TTL 短期化：**MUST ≤ 600s**（10 分钟），SHOULD ≤ 300s。过期前客户端 MUST 重新兑换。
- `participant_identity` 在 backend 中作为 SFU-local handle，MUST 不携带可关联到长期 actor 身份的可识别信息（与 [`webrtc-signaling.md` §6.6 pairwise pseudonym](../zh/crypto-media/webrtc-signaling.md) 规则对齐），且 MUST 至少绑定 `(realm_id, call_id, focus_id, device_id, issuer_service_did, issued_at_bucket)` 派生。
- `participant_binding` 是 token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺；客户端 MUST 先验证该 binding，再把它写入 / 对照 `ck.call.state` membership。backend 只需要看到 `participant_identity` 与 `backend_token`，不应获得长期 actor 身份。
- **Token issuer DID 锚定**：响应中的 `service_signature.kid` 与 `participant_binding.issuer_kid` MUST 对应一个出现在当前 epoch `ck.realm.media_service.service_id` 的 service DID（即该 service 在 Realm policy 中已被 `ck.realm.media_service` 或 `ck.policy.manage` 显式授权）；客户端 MUST 拒绝来自未授权 DID 的 token。这把 token 签发权与 Realm policy 锁定，防止任意 service 凭空铸造 join token。

### 4.3 Focus 选择规则（normative）

`m.rtc.member` 的 Cokret 等价物（沿用现有 `ck.call.state` membership facet）新增 call-level `session_focus` 与 participant-level binding 字段：

```json
{
  "kind": "ck.call.state",
  "payload": {
    "call_id": "ck:call:...",
    "state": "active",
    "mode": "sfu",
    "session_focus": "fra-1",
    "participants": [
      {
        "actor_id": "did:webvh:z2dmjZ8r7L4nP2vXkBqM9wTyHfJgRdN3sV6cKuYi5oXtAeB1Z:alice.example.com",
        "device_id": "ck:device:...",
        "foci_preferred": ["fra-1", "us-east-1"],
        "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
        "participant_binding": { "scheme": "ck.media.participant_binding.v1", "...": "..." },
        "joined_at": "2026-05-27T10:00:00.123Z"
      }
    ]
  }
}
```

**选举规则**（确定性，无投票）：

1. 若 `ck.call.state.session_focus` 已存在，它就是唯一 authoritative focus；客户端和 token issuer MUST 使用它。
2. 若 `session_focus` 尚不存在，收集所有当前 active member 的 `(joined_at, actor_id, device_id, foci_preferred)` 元组；按 `(joined_at, actor_id, device_id)` 升序，**oldest_membership 的 `foci_preferred[0]` 被写入 `session_focus`**。
3. 后加入者 MUST 使用同一 `session_focus`，无论自己的偏好；如果该 focus 在自己的 preferred 列表中不存在，客户端 MAY 拒绝加入（fail closed）。
4. Token issuer MUST 拒绝任何 `focus_id != session_focus` 的 token exchange；这条规则优先于 health check、region preference 和 load balancing。
5. 当 oldest member 离开，focus **不自动迁移**（避免媒体路径中断）；session 持续到所有人离开后才重置。

**Open question**（见 §6）：是否需要 "focus migration"（在线切换 focus）能力？v1 倾向不提供。

### 4.4 Token Issuer 必须校验的权限

Token 端点扮演的角色等价于 [MSC4195 `lk-jwt-service`](https://github.com/element-hq/lk-jwt-service)。Issuer MUST 校验：

- 调用者 device proof / bearer 有效，未 revoked。
- Actor 在 `realm_id` 拥有 `call.join` capability。
- 请求的 `desired_media` 不超过授权（`call.screen_share` 等子 capability 检查）。
- Realm policy 允许该 `focus_id`（即 focus 出现在当前 `ck.realm.media_service.foci[]` 中）。
- 如果 `ck.call.state.session_focus` 已存在，请求的 `focus_id` 与其完全一致；不一致 MUST 返回 `focus_mismatch` / `sfu_not_allowed` 的等价错误并拒绝签发。
- call state 允许新 participant，且该 `(actor_id, device_id)` 未被 revoked、未被 ban / suspended。
- MLS governance binding `policy_root` 与 `ck.realm.media_service` 当前 epoch 一致（防 stale policy）。
- 如果 backend 将解密媒体（`media_service_decrypts=true`），完整执行 [`webrtc-signaling.md` §10.3.1](../zh/crypto-media/webrtc-signaling.md) 的三层校验。

### 4.5 Backend Binding 附录格式（normative meta-rule）

每个具体 `type` 值在 `spec/v1/zh/crypto-media/bindings/<type>.md` 下有专属附录文件，必须覆盖：

| 章节 | 内容 |
| --- | --- |
| Token claims | `backend_token` payload 的具体字段（如 LiveKit JWT 的 `video.room` / `video.roomJoin` / `video.canPublish`） |
| Connect handshake | 客户端如何用 `connect_url` + token 建立媒体通道 |
| E2EE key injection | 如何把 Cokret MLS exporter 派生的 frame key 喂给 backend 加密层（见 §4.5.1） |
| Capability mapping | `desired_media` 字段如何映射到 backend 内部权限 |
| Cascading 行为 | backend 是否支持 mesh / cascading，及如何配置 |
| Failure modes | 错误码到 [`webrtc-signaling.md` §16](../zh/crypto-media/webrtc-signaling.md) 错误表的映射 |
| Participant identity validation | backend "X 加入"通知与 `ck.call.state` membership 的交叉校验路径 |

v1 提案随附 LiveKit binding 草案（`bindings/livekit.md`）作为示例与 conformance baseline。

#### 4.5.1 E2EE Key Injection 通用契约（normative）

无论 backend 自身有无 E2EE 支持，所有 binding 附录的 E2EE 章节 MUST 规定一个最小契约，使得**客户端侧 binding adapter / media SDK** 能从 Cokret 协议层接收 key，而不从 backend 自带密钥分发机制取。最小契约：

```text
inject_frame_key(key_bytes: 32-byte secret,
                 epoch_id: u64,
                 rotation_trigger: enum{member_join,member_leave,manual,scheduled})
```

- `key_bytes` MUST 由 Cokret MLS exporter 派生，**label 固定为 ASCII 字符串 `"ck-rtc-frame-key/v1"`**（length=19 bytes，无 trailing newline；RFC 9420 §8 `MLS-Exporter` 的 `Label`，`Context = ""`，`KDF.Nh` 长度 32 bytes）。该 label 不在 conformance 阶段再议——任何变更属于 wire-breaking 改动，必须开新 profile。
- `epoch_id` 与 Realm MLS epoch 一一对应。
- backend SDK / adapter 内部如何把该 key 映射到 SFrame / 私有帧加密格式由附录指定，但 **MUST NOT** 接受任何非该接口的 key 源（如 backend 自带 KMS、自生成 random key）。除非 Realm policy 明确允许 `media_service_decrypts=true` 且完成 [`webrtc-signaling.md` §10.3.1](../zh/crypto-media/webrtc-signaling.md) 三层校验，`key_bytes` MUST NOT 被发送给远端 SFU / MCU。
- Conformance negative vector：backend 用自家密钥 → 客户端 MUST 拒绝并报 `e2ee_key_source_unauthorised`。

#### 4.5.2 Participant Identity 交叉校验（normative）

Backend 通知"X 加入会议"时，客户端 MUST：

1. 从 backend 通知中提取 `participant_identity`。
2. 在当前 `ck.call.state.participants[]` 中查找同一 `participant_identity`。
3. 验证该 participant entry 内的 `participant_binding` 签名，确认它覆盖同一 `(realm_id, call_id, session_focus, actor_id, device_id, participant_identity)`。
4. 不匹配或签名无效 → 拒绝建立该 participant 的媒体流，报 `participant_identity_unrecognised`。

这防止 backend 单方面"塞入"未经 Realm 授权的参与者（包括 backend 运营方误配置或被入侵的场景）。

### 4.6 Cascading：协议层的表态

**v1 协议不规范 SFU-to-SFU cascading 协议**。理由：

- 每个 backend 有自己的 mesh 实现（LiveKit Cloud SFU mesh、mediasoup 自托管 cluster、Janus federation）。
- Matrix 自己写 Waterfall 的失败先例。

但协议层 MUST 暴露 cascading 状态：

- `ck.realm.media_service.foci[].cascade_group` 字段（optional），声明属于同一 backend cluster 的 focus 集合。
- 客户端可以读出该字段并向用户提示"跨区域会议由 backend 内部级联，媒体延迟取决于 backend 配置"。

### 4.7 Recording Artifact 流转（normative）

Backend 可能自带录制能力（LiveKit Egress、Janus recording plugin 等）。**v1 不禁止 backend 生成录制**，但生成的 artifact MUST 经 Cokret-side blob pipeline 入库：

1. Backend recording component 把录制结果作为加密 blob **上传到 Cokret media service**（通过 [`media-and-blob.md`](../zh/crypto-media/media-and-blob.md) 的 authenticated upload 端点），不得自行托管。
2. 上传请求 MUST 携带 `recording_initiator_capability_ref`，证明该 recording 由具备 `call.record` 的 actor 发起。
3. 录制 artifact 加密 key MUST 由 Cokret 协议层提供（与 §4.5.1 同源），backend 不持久化明文。Artifact encryption key MUST come from MLS exporter label `"ck-rtc-recording-key/v1"` with `Context=canonical_json({realm_id, call_id, focus_id, recording_id, media_service_did, recording_start_event_id})`; it MUST NOT reuse SFrame label `"ck-rtc-frame-key/v1"` or an empty Context。
4. 入库后通过已注册的 `ck.call.state` 写入 call lifecycle state（例如 `state="recording_ready"` / `state="recording_failed"`），并在 payload 中引用 blob hash、duration、media type、retention policy 和 `recording_start_event_id`。v1 不新增 `ck.call.recording.artifact` event kind。

这保证 backend 是"录制执行单元"而非"录制档案库"，audit 链与生命周期管控不被 backend 实现细节绕过。

### 4.8 Conformance Vectors（historical list; merged）

以下向量已合入 [`zh/conformance/conformance-vectors.md`](../zh/conformance/conformance-vectors.md) 与 `artifacts/registry/vector-registry.json`；本节只保留历史设计清单：

- `ck.vector.media_binding.focus_selection_oldest_membership.v1` — 多人不同 preferred 时 oldest member 偏好胜出。
- `ck.vector.media_binding.session_focus_no_split_brain.v1` — `session_focus` 一旦写入，token issuer 拒绝其他 focus；connect 失败不得静默切换。
- `ck.vector.media_binding.token_exchange_minimal.v1` — token 端点最小字段集与 TTL ≤ 600s。
- `ck.vector.media_binding.token_issuer_unauthorised.v1` — token issuer DID 不在 `ck.realm.media_service.service_id` 列表时客户端 MUST 拒绝。
- `ck.vector.media_binding.participant_binding_required.v1` — 缺失或签名无效的 participant binding 必须拒绝。
- `ck.vector.media_binding.unknown_type_fail_closed.v1` — 未知 `type` 值客户端 MUST 拒绝加入。
- `ck.vector.media_binding.e2ee_key_source.v1` — backend 即使支持自家 E2EE，密钥源 MUST 来自 Cokret MLS exporter；backend 自生成 key 时客户端拒绝。
- `ck.vector.media_binding.participant_identity_unrecognised.v1` — backend 通知 join 的 participant 不在 `ck.call.state` 时客户端拒绝该流。
- `ck.vector.media_binding.recording_artifact_via_cokret_blob.v1` — backend-generated recording 必须通过 Cokret blob pipeline 入库，并用 `ck.call.state` 发布结果；绕过路径拒绝。
- `ck.vector.media_binding.recording_exporter_label.v1` — recording key 必须使用 `"ck-rtc-recording-key/v1"` 与 recording transcript Context；复用 SFrame label 或空 Context 必须拒绝。

## 5. Interactions with normative spec

| 文件 | 影响 |
| --- | --- |
| [`zh/crypto-media/webrtc-signaling.md`](../zh/crypto-media/webrtc-signaling.md) | §6.1 schema 扩展（`sfu_endpoint` → `foci[]`，无兼容退化）；§7.2 `focus_join`/`focus_leave` 语义补全；§10.1 SFU join request/response 重新框架化为 type-specific 附录；§11 `ck.call.state` 增加 `session_focus`、`participant_identity`、`participant_binding`；§13 录制结果继续使用 `ck.call.state` |
| `zh/crypto-media/bindings/livekit.md` | **新文件** — LiveKit binding |
| `zh/crypto-media/bindings/cokret-native.md` | **新文件** — 把现行 §10.1 自定义 SFU 信令搬入此处作为 reference impl |
| [`zh/sync/service-http-binding.md`](../zh/sync/service-http-binding.md)、[`zh/sync/service-surface.md`](../zh/sync/service-surface.md) | 登记 token exchange canonical operation 与默认 HTTP binding（建议 `POST /_cokret/self/rtc/token`），并在 media service describe 中暴露 |
| [`zh/authz/capabilities.md`](../zh/authz/capabilities.md) | 已有 `ck.realm.media_service` 不变；`call.join` / `call.screen_share` / `call.record` 等现行裸名在 accepted 迁移时必须注册或收敛到 `ck.call.*` action，不得只停留在 narrative |
| `artifacts/registry/operation-registry.json`、`artifacts/openapi/cokret-service-api.openapi.yaml` | 新增 token exchange operation / schema / error response；health endpoint 若保留也要登记 discovery 语义 |
| `artifacts/registry/event-kind-registry.json` | `ck.realm.media_service` payload schema 更新；不新增 recording artifact event kind |
| `artifacts/registry/error-code-registry.json` | 新增 `focus_mismatch`、`e2ee_key_source_unauthorised`、`participant_identity_unrecognised` 等错误码，或映射到既有 canonical code |
| `artifacts/profiles/conformance-profiles.json` | 新增 `ck.profile.media_service_binding.v1`；具体 backend binding 作为可选 sub-profile |
| `artifacts/registry/vector-registry.json` | 新增 §4.8 列出的向量 |

**Schema compatibility**：`ck.realm.media_service` 单 endpoint 形态在本提案 accepted 后的 **v1 cycle 全程** MUST 被拒绝，不做 reducer / projection 入口自动迁移。`foci[].type` MUST 有 registry source of truth；客户端遇到未知 `type` 或已知但 unsupported / experimental 的 `type` MUST fail closed，而不是尝试把 token 交给任意 SDK。

## 6. Rationale & alternatives

- **为什么不直接写 LiveKit binding 作为 v1 normative？** 见 §2.3，避免 backend 锁定。
- **为什么不允许 focus migration？** 在线迁移需要媒体平面 graceful handover，工程复杂度高；Matrix MatrixRTC 也未规范。v1 范围外。
- **为什么 token TTL 短期化？** Backend token 一旦泄漏在 TTL 内不可吊销（除非 backend 支持 token revocation list，多数不支持）。短 TTL + 频繁兑换是普遍工程实践。
- **为什么不抽象到 MoQ？** MoQ（[draft-ietf-moq-transport](https://datatracker.ietf.org/wg/moq/)）2026 仍在 last call 阶段；对 interactive conferencing 还无生产实现。MSC4143 transport-agnostic 模型为未来 MoQ binding 留好了扩展位，本提案沿用同样思路。
- **为什么不引入 SFU 选举协议？** `oldest_membership` 是 Matrix 验证过的"足够好"方案。代价是缺地理/负载感知，但避免了选举协议的 split-brain 风险。地理感知可通过 backend cluster 自身的 mesh 处理。

## 7. Resolved / Deferred Questions（historical）

以下问题在 accepted 迁移时已 resolved 或 deferred；读者应以 `merged_to` 中的 normative 文件为准。

| Question | Status | Normative outcome |
| --- | --- | --- |
| 是否包含 LiveKit binding | resolved | `bindings/livekit.md` 已作为 optional sub-profile 合入，不进入 v1 mandatory core。 |
| Cascading 节点级可观测性 | deferred-to-profile | core 只要求 `session_focus` 与 participant binding；节点 / region 诊断由 backend binding profile 声明。 |
| `cokret-native` reference impl 命运 | resolved | 保留为 `bindings/cokret-native.md` reference binding。 |
| call capability 命名收敛 | resolved | capability registry 使用 `ck.call.join` / `ck.call.record` / `ck.realm.media_service`。 |

## 8. Resolved Decisions（记录已定取舍）

为避免后续重新争论：

- **Token TTL**：MUST ≤ 600s，SHOULD ≤ 300s（§4.2）。
- **Token issuer DID 锚定**：必须等于 Realm-configured `ck.realm.media_service.service_id`（§4.2）。
- **Focus health check**：可选 `health_endpoint` 只参与 pre-commit 排序；`session_focus` 写入后不得静默 fallback（§4.1 / §4.3）。
- **Backend-native E2EE 密钥来源**：MUST 来自 Cokret MLS exporter，固定客户端侧接口 `inject_frame_key(key_bytes, epoch_id, rotation_trigger)`，MLS-Exporter label 固定为 `"ck-rtc-frame-key/v1"`、context 空、`KDF.Nh=32`（§4.5.1）。
- **单 endpoint 形态**：v1 cycle 内 MUST 拒绝，不做自动 normalize（§5）。
- **Participant identity 交叉校验**：客户端 MUST 校验 backend 通知的 participant 与 `ck.call.state` 中的 signed `participant_binding` 一致（§4.5.2）。
- **MoQ 保留位**：v1 schema 接受 `type: "moq-relay"`，但 v1 周期内不提供 normative binding（§4.1）。
- **Recording artifact**：backend 可执行录制，但 artifact MUST 经 Cokret blob pipeline 入库，加密 key 来自协议层 MLS exporter label `"ck-rtc-recording-key/v1"`，结果通过 `ck.call.state` 发布，不新增 `ck.call.recording.artifact` event（§4.7）。
- **Focus migration**：v1 不提供在线 focus 切换；session 持续到所有人离开（§4.3）。

## 9. Migration plan（historical; completed）

- Phase 1：webrtc-signaling.md §6.1 扩展为 multi-focus（无兼容退化）；§10.1 文本搬入 `bindings/cokret-native.md` 作为 reference impl，不改 wire。
- Phase 2：补 `ck.call.state.session_focus` / `participant_binding` schema、token exchange operation、OpenAPI、error registry 与 backend type registry。
- Phase 3：新增 `bindings/livekit.md`，给出完整 LiveKit binding，conformance profile 标 optional。
- Phase 4：vector-registry 落 §4.8 向量。
- Phase 5：observation period 后，决定是否把 LiveKit binding 升 candidate normative。

---

**References**：
- [MSC4143 — MatrixRTC](https://github.com/matrix-org/matrix-spec-proposals/pull/4143)
- [MSC4195 — MatrixRTC LiveKit Backend](https://github.com/matrix-org/matrix-spec-proposals/pull/4195)
- [Matrix 2.0 blog](https://matrix.org/blog/2023/09/matrix-2-0/)
- [Element Call Beta 3 — switch to LiveKit](https://element.io/blog/element-call-beta-3/)
- [RFC 9605 — SFrame](https://www.rfc-editor.org/rfc/rfc9605.html)
- [lk-jwt-service](https://github.com/element-hq/lk-jwt-service)
