---
title: Media Service Binding
status: candidate
normative: true
stability: v1
updated: 2026-07-02
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
    "service_id": "did:webvh:z7ECJ5c1A1o5Xr1AdPqPCBD7L:media.example.com",
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

修改该 state event 需要 `ck.realm.media_service` 或 `ck.policy.manage` capability。

### 2.1 完整性绑定（normative）

`ck.realm.media_service` 的 `service_id`、`ice_config_endpoint` 与 `foci[].token_endpoint` 是媒体 token / TURN credential 签发权与 issuer DID 锚定的**信任根**(见 §3 / §7 与 [`call-state.md` §4.1](./call-state.md))。为保证"谁担保该 `service_id` / endpoint 列表未被篡改",本节固定:

- `ck.realm.media_service` state event(含其 `service_id`、`ice_config_endpoint` 与全部 `foci[].token_endpoint`)MUST 被纳入该 Realm policy 的 `policy_root`,并被**当前 epoch 的 MLS governance binding**(见 [`encryption-and-audit.md` §2.5](./encryption-and-audit.md))覆盖;`policy_root` 物化时 MUST 把该 event 的 canonical digest 作为输入之一。
- 客户端在把 `service_id` / `ice_config_endpoint` / `foci[].token_endpoint` 锚定为 credential issuer DID **之前**,MUST 校验该 event 处于当前 epoch governance binding 覆盖之下(即其 digest 可由当前 `policy_root` / governance binding 重建);覆盖校验失败 MUST fail closed(`media_service_binding_uncovered`),不得向未被治理绑定覆盖的 endpoint 兑换 token 或 ICE/TURN credential。
- 服务端 MUST NOT 在实时路径中接受或回填未被当前 epoch governance binding 覆盖的 `ck.realm.media_service`;epoch 推进后，旧 epoch 覆盖的媒体服务声明 MUST 重新经新 epoch governance binding 覆盖才继续作为 issuer 信任根。

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
  "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
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
    "actor_id": "did:webvh:zBfFLx7gUhQB7dPEQCj3qeHZR:alice.example.com",
    "device_id": "ck:device:...",
    "participant_identity": "ck:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
    "issued_at": "2026-05-27T12:29:56Z",
    "expires_at": "2026-05-27T12:34:56Z",
    "issuer_kid": "did:webvh:zCxjAemtszNh7bTFGWFS4m8gv:media.example#key-1",
    "sig": "base64url..."
  },
  "expires_at": "2026-05-27T12:34:56Z",
  "service_signature": { "kid": "did:webvh:zCxjAemtszNh7bTFGWFS4m8gv:media.example#key-1", "sig": "base64url..." }
}
```

核心约束（normative）：

- **TTL 短期化**：`backend_token` / `participant_binding` `expires_at` 的硬上限 MUST ≤ 600s（10 分钟）；推荐上限 SHOULD ≤ 300s。过期前客户端 MUST 重新兑换；backend token 一旦泄漏在 TTL 内通常不可吊销（除非 backend 提供 revocation list），短 TTL 是工程兜底。
- **Token issuer DID 锚定**：`service_signature.kid` 与 `participant_binding.issuer_kid` MUST 解析到一个出现在当前 epoch `ck.realm.media_service.service_id` 的 service DID；客户端 MUST 拒绝来自未授权 DID 的 token，错误码 `token_issuer_unauthorised`。该规则把 token 签发权与 Realm policy 锁定，防止任意 service 凭空铸造 join token。
  - **轮换语义（normative）**：`participant_binding` 只承诺六元组 + `expires_at`，**不**绑定签发时的 media_service epoch。issuer 锚定按**写入 `ck.call.state` 时的当前 epoch** `service_id` 判定（[`call-state.md` §4.1](./call-state.md)），因此一次 media_service 轮换（旧 `service_id` 被移出当前 epoch）即时作废由被移出 service 签发、尚在 TTL 内的在途 binding：reducer MUST 以 `token_issuer_unauthorised` 拒绝其落账，客户端 MUST 重新向当前 epoch service 兑换。这是已知的 ≤600s 活性窗口（与 TTL 上限一致），不引入跨 epoch binding 复用；实现 MUST NOT 为旧 epoch binding 增设 grace 接受。
- **`participant_identity` 形态**：作为 SFU-local 短期随机 handle，scope 限 `(call_id, focus_id, sfu_did)`；MUST NOT 携带可关联到长期 actor 身份的可识别信息（与 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md) pairwise pseudonym 规则对齐），也不得由可公开重算的主体元组确定性派生。六元组绑定职责由下方 `participant_binding` 的签名承诺承担。
- **`participant_identity` 传播边界**：因为它本身不携带 actor 链接信息，客户端 **MUST** 把它写入 `ck.call.state.participants[].participant_identity`（用于 §7 cross-check）——这条嵌入是 Realm-encrypted control state，不构成 actor-身份外泄。但 `participant_identity` MUST NOT 进入下列三类 surface：(a) 任何 plaintext audit log / 服务方 access log（包括 backend SFU 自身的日志）；(b) 任何 unencrypted ephemeral / push / telemetry 通道；(c) backend 一侧对外的 metrics、tracing 标签或 cross-tenant 数据导出。Backend 内部允许保留它作为 SFU-local routing handle，但不应跨 call leg / 跨 tenant 复用。
- **`participant_binding` 是 token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)` 的签名承诺**。客户端 MUST 先验证该 binding，再把它写入 / 对照 `ck.call.state` membership（见 [`call-state.md` §4](./call-state.md)）。backend 只看到 `participant_identity` 与 `backend_token`，不应获得长期 actor 身份。
- **落账时序**：客户端在获得 token exchange response 后，MUST 先提交包含本端 `participant_identity` 与 `participant_binding` 的 `ck.call.state.participants[]`，并等待该 event 被服务端接受，之后才可把该 identity 视为 durable roster 成员并向用户暴露/订阅对应 SFU media stream。`ck.call.signal` 中的 `invite` / `answer` 只表示实时协商意图，MUST NOT 作为 participant authorization 或 cross-check 真源。
  - **签名输入（normative，跨实现互通契约）**：`participant_binding.sig` MUST 是 issuer 私钥（对应 `issuer_kid`）对下列字节串的 EdDSA(Ed25519) 签名：

    ```text
    signing_input =
      "ck.media.participant_binding.v1" || 0x00 ||
      canonical_json({ actor_id, call_id, device_id, expires_at,
                       focus_id, participant_identity, realm_id })
    ```

    第一段是固定 ASCII 域分隔 label（逐字节等于 `scheme` 值），随后单字节 `0x00` 分隔，再接 7 字段对象的 canonical JSON（RFC 8785 JCS：键按字母序、无多余空白，故字段书写顺序无关）。**签名仅覆盖这 7 个权威字段**；binding 对象另带的 `scheme` / `issuer_kid` / `issued_at` 是**未签名元数据**，MUST NOT 进入 `signing_input`。接收方据 wire 上的 7 个权威字段值重建 `signing_input` 再验签——故篡改任一权威字段都会令验签失败。任何 media service（cokret-native / LiveKit / 第三方）MUST 按此构造，任何客户端 / reducer MUST 按此验签；实现 MUST NOT 引入私有 domain 前缀，也 MUST NOT 把元数据字段并入签名输入，否则破坏跨 service 互通。
  - **`service_signature`**：`service_signature.sig` 是 issuer 对**同一 `signing_input`**（label 与 7 元组与上完全一致）的 EdDSA 签名，承诺该次 token exchange 响应整体的 issuer 身份；`service_signature.kid` 与 `participant_binding.issuer_kid` 都 MUST 锚定当前 epoch `service_id`（见上「Token issuer DID 锚定」）。客户端在默认验证路径中 **MUST** 同时验 `service_signature.sig` 与 `participant_binding.sig` 通过后才使用该 token——二者任一验签失败即 `token_issuer_unauthorised` 拒绝，MUST NOT 把签名校验降级为可选的 SHOULD。

Token issuer MUST 在签发前校验：

- 调用者 device proof / bearer 有效，未 revoked。
- Actor 在 `realm_id` 拥有 `ck.call.join` capability；`desired_media` 不超过授权（`ck.call.screen_share` 等子 capability 检查）。
- Realm policy 允许该 `focus_id`（即 focus 出现在当前 `ck.realm.media_service.foci[]` 中）。
- 如果 `ck.call.state.session_focus` 已存在，请求的 `focus_id` 与其完全一致；不一致 MUST 返回 `focus_mismatch`。
- call state 允许新 participant；且按分层 predicate 校验该 `(actor_id, device_id)`：actor 在 `realm_id` 的 Realm membership 为 `join`（若 scoped 到 Circle 则同时为该 Circle 活跃成员）、account status 不为 `suspended` / `deactivated` / `erasure_pending`、`device_id` 的 device grant 未 revoked。
- MLS governance binding `policy_root` 与 `ck.realm.media_service` 当前 epoch 一致（防 stale policy）；不一致返回 `mls_governance_binding_stale`。
- 如果 backend 将解密媒体（`media_service_decrypts=true`），完整执行 §8.2 的三层校验。

### 3.1 签名 domain label 分离（normative）

媒体路径上的每一类 **Ed25519 签名** MUST 以一个**独立的 ASCII domain 分隔 label** 前缀其 `signing_input`，再接单字节 `0x00` 分隔与该签名覆盖的 canonical bytes。该 label 是签名的安全域分离参数：它把"同一 issuer key 在不同用途上产生的签名"彼此隔离，使任一签名 MUST NOT 被验证方在另一用途下重新解释（cross-protocol / cross-purpose signature confusion）。任何 media service（cokret-native / LiveKit / 第三方）MUST 按本表构造签名，任何客户端 / reducer MUST 按对应 label 重建 `signing_input` 再验签；验证方 MUST 在重建时使用其**期望用途**对应的 label，签名方使用了不匹配 label 即视为验签失败。

v1 Ed25519 媒体签名点与其 label 常量（逐字节 ASCII）：

| 签名点 | domain label 常量 | signing_input 覆盖 | 定义处 |
| --- | --- | --- | --- |
| `participant_binding.sig` | `ck.media.participant_binding.v1` | `label \|\| 0x00 \|\| canonical_json({actor_id, call_id, device_id, expires_at, focus_id, participant_identity, realm_id})`（7 元组，见 §3） | §3（已字节锁，本节仅引用，不改） |
| `service_signature.sig` | `ck.media.participant_binding.v1`（**复用** participant_binding label 与同一 7 元组 signing_input） | 同上 | §3 |
| ICE config response `signature` | `ck.media.ice_config.v1` | `label \|\| 0x00 \|\| canonical_json(ICE config response 去除 `signature` 字段后的权威字段：`realm_id, call_id, actor_id, device_id, issued_at, issued_at_bucket, bucket_seconds, ttl_seconds, ice_servers, 及策略字段`) | [`webrtc-signaling.md` §4.1](./webrtc-signaling.md) |

约束细则：

- **`participant_binding` / `service_signature` 刻意共用同一 label 与 signing_input，且 v1 不赋予 `service_signature` 独立语义（normative，显式裁决）**：§3 已字节锁 `participant_binding.sig` 与 `service_signature.sig` 对**同一** `signing_input`（label = `ck.media.participant_binding.v1`、同一 7 元组）签名。这看似与本节"用途隔离"立论冲突，但 v1 的显式裁决是：二者**不是两个不同用途的签名**，而是**同一断言的冗余**——`service_signature` 与 `participant_binding` 承诺的是同一 7 元组 token-exchange 响应，前者表达"issuer 对该响应负责"、后者表达"该 participant 绑定有效"，二者覆盖完全相同的 canonical bytes，因此共用 label 不构成 cross-purpose confusion（不存在"另一种用途"可被混淆解释）。v1 **刻意保持复用**，**不为 `service_signature` 引入独立 label，也不赋予 `service_signature` 任何独立于 `participant_binding` 的语义**；该 label 常量已在 §3 字节锁并被 fixture / 向量固定，改 label 属 wire-breaking，故 v1 选择"明确声明冗余"而非拆分。任何把 `service_signature` 当作独立用途签名、或期望它覆盖与 `participant_binding` 不同 bytes 的实现，均违反本裁决。
- **ICE config response 签名 MUST 用 distinct label `ck.media.ice_config.v1`（normative）**：ICE config 响应签名覆盖的字段集合（`realm_id` / `call_id` / `actor_id` / `device_id` / `issued_at` / `issued_at_bucket` / `bucket_seconds` / `ttl_seconds` / `ice_servers[]` 与策略字段）与 participant_binding 的 7 元组**不同用途、部分字段重叠**；若两者复用同一 label，则一个 issuer key 对 ICE config 的签名可能被在 participant_binding 验证路径下重解释（反之亦然）。因此 ICE config 签名 MUST 以 `ck.media.ice_config.v1` 前缀其 signing_input。canonical 定义见 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md)。
- **不在本 label 体系内的媒体凭证**（据实说明各自的域，MUST NOT 强加 Ed25519 label）：
  - `backend_token`（LiveKit 部署）是 **LiveKit JWT**，自带 `alg` / `iss` 等 JOSE header 与 issuer 标识，其签名域由 JWT 标准与 LiveKit API Key/Secret 决定（见 [`bindings/livekit.md` §2](./bindings/livekit.md)），不进入本节 Ed25519 label 体系。
  - TURN REST 凭证不是 Ed25519 签名而是 **HMAC**：`credential = HMAC-SHA256(turn_shared_secret, username)`，其中 `username = "<expiry-unix>:<per-call-pairwise-pseudonym>"`（见 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md)）；pseudonym 本身亦由 HMAC 派生。HMAC 的域由其 `turn_shared_secret` 与 username 输入构造决定，不属于 Ed25519 签名 domain label 范畴。
- 本节**只规定 Ed25519 签名类**（`participant_binding` / `service_signature` / ICE config）的 domain label 分离；MUST NOT 借此更改任何媒体密钥本身、MUST NOT 更改客户端对 issuer / service DID 公钥的锚定路径（§2.1 / §3 / §6 的公钥锚定保持不变）。新增 label 仅约束签名输入前缀，不引入新密钥派生。

## 4. SFU Service

SFU 在 v1 通过 [§2](#2-realtime-media-server) 的 `foci[]` 声明，每个 focus 通过 `type` 选择具体 backend binding：

- `type="livekit"`：见 [`bindings/livekit.md`](./bindings/livekit.md)。
- `type="cokret-native"`：见 [`bindings/cokret-native.md`](./bindings/cokret-native.md)（reference / conformance binding，不作为生产媒体后端）。
- `type="mediasoup"` / `type="janus"` / `type="moq-relay"`：保留位，v1 周期内不提供 normative binding；客户端遇到 unsupported `type` MUST fail closed，错误码 `unknown_focus_type`。

不论 backend 类型，client→backend 媒体协商前 MUST 先完成 [§3 Token Exchange](#3-token-exchange-normative)；具体 `backend_token` 形态、connect handshake、SDP 协商由 type-specific 附录定义。下面的 §5 / §6 / §7 是跨 backend 通用约束。

## 5. Focus Selection 与 Session 持久化（normative）

会议第一次 join 时由客户端排序 `foci_preferred[]` 写入 `ck.call.state.participants[].foci_preferred`；之后用 **deterministic, no-vote** 规则收敛为单一 `session_focus`：

1. 若 `ck.call.state.session_focus` 已存在，它就是唯一 authoritative focus；客户端和 token issuer MUST 使用它。
2. 若 `session_focus` 尚不存在，收集所有当前 active member 的 `(joined_at, actor_id, device_id, foci_preferred)` 元组；按 `(joined_at, actor_id, device_id)` 升序，**oldest_membership 的 `foci_preferred[0]` 被写入 `session_focus`**。
3. 后加入者 MUST 使用同一 `session_focus`，无论自己的偏好；如果该 focus 在自己的 preferred 列表中不存在，客户端 MAY 拒绝加入（fail closed），错误码 `focus_unavailable_for_client`。
4. Token issuer MUST 拒绝任何 `focus_id != session_focus` 的 token exchange，错误码 `focus_mismatch`；该规则优先于 health check、region preference 和 load balancing。
5. 当 oldest member 离开，focus **不自动迁移**（避免媒体路径中断）；session 持续到所有人离开后才重置。v1 不提供 in-session focus migration。

### 5.1 P2P→SFU 升级复用本节选举（normative）

P2P 起步的通话在并发参与者 > 2 时 MUST 收敛到 SFU（normative 触发、信令与 `mode` 写入规则见 [`call-state.md` §6](./call-state.md)）。升级 MUST 直接复用本节的 deterministic, no-vote `session_focus` 选举：由 oldest_membership 的 `foci_preferred[0]` 选出 `session_focus`，各设备经 `ck.call.signal{signal_type=focus_join}`（见 [`webrtc-signaling.md` §5](./webrtc-signaling.md)）迁移媒体，原 P2P leg 在迁移完成后优雅拆除。升级不引入任何新的投票 / leader 选举路径，也不为升级新增 focus migration 例外——一旦 `session_focus` committed 即遵守第 1–5 条的 write-once 与 no-split-brain 规则。

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
3. 验证该 participant entry 内的 `participant_binding` 签名（[§3](#3-token-exchange-normative)），确认它覆盖与 §3 签发侧完全相同的权威元组 `(realm_id, call_id, focus_id, actor_id, device_id, participant_identity, expires_at)`（此处当前 `session_focus` 即 §3 元组中的 `focus_id`；签名输入字段集合与名称以 §3 为准，不得省略 `expires_at`）。
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

- `key_bytes` MUST 由 Cokret MLS exporter 派生，**label 固定为 ASCII 字符串 `"ck-rtc-frame-key/v1"`**（length=19 bytes，无 trailing newline；RFC 9420 §8 `MLS-Exporter` 的 `Label`，`KDF.Nh` 长度 32 bytes）。`Context` MUST 是 canonical JSON bytes of exactly `{realm_id, call_id, focus_id, epoch_id, participant_identity, device_id}`，其中 `participant_identity` / `device_id` 来自已验证的 `ck.call.state.participants[]` 与 `participant_binding`。`Context = ""`、缺少 sender 字段或只绑定 epoch 的派生 MUST fail closed(`e2ee_key_source_unauthorised`)。`ck-rtc-frame-key/v1` / `ck-rtc-recording-key/v1` 是**固定的 canonical wire label**（密钥派生的安全域分离参数，canonical 登记见 [`exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)）；实现 MUST 逐字节使用登记的 label 字符串，MUST NOT 与其它 label 混用。该 label 的任何变更属于 wire-breaking，必须开新 profile。
- `epoch_id` 与 Realm MLS epoch 一一对应。
- `rotation_trigger` 不得被 adapter 当作不透明枚举透传:`rotation_trigger=member_leave`（成员离开 / 被踢 / 被 ban）**MUST** 对应一次 MLS commit（Remove）并推进 `epoch_id`，使新 `key_bytes` 从离开成员不掌握的新 group secret 派生；adapter **MUST NOT** 在 `member_leave` 时仅更换 SFrame KID / keyIndex 而复用旧 epoch 的 group secret，否则离开成员仍能解密后续帧（E2EE 媒体前向保密失效）。`member_join` 同样 MUST 绑定推进后的 `epoch_id`。`manual` / `scheduled` 触发亦 MUST 携带推进后的 `epoch_id`；任何 `rotation_trigger` 下若 `epoch_id` 未相对前一帧密钥推进，客户端 MUST fail closed（`e2ee_key_source_unauthorised`）。
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
- `ck.vector.media_binding.recording_exporter_label.v1` — backend-generated recording 必须使用 `"ck-rtc-recording-key/v1"` 与绑定 recording transcript 的 Context，不得复用 SFrame key label。

### 8.2 治理绑定（normative）

**三层关系**: `ck.realm.media_service` declares SFU existence; `plaintext_visible_services` grants decryption authority; `ck.realm.policy_components.media_service_decrypts=true` carries the boolean toggle — 三者 MUST 同时成立才能让 media service 解密。

`media_service_decrypts=true` **不**是一个可单独由 SFU 服务自报或客户端配置的开关。它 MUST 同时满足下列约束，否则客户端 MUST 拒绝加入会议、SFU MUST 拒绝媒体协商：

1. **进入 `ck.realm.policy_components`**：`media_service_decrypts=true` MUST 由一条 `ck.realm.policy_components`（或对应 Realm policy facet event）显式写入，受 capability `ck.policy.manage` 控制，并随 Realm policy `policy_root` 一同被 [`encryption-and-audit.md` §2.5](./encryption-and-audit.md) 的 MLS governance binding 覆盖。policy_root 未包含该开关时 MUST 视为未开启。
2. **进入 `plaintext_visible_services`**：解密媒体的 SFU / MCU service DID MUST 在 Realm policy 的 `plaintext_visible_services[]`（或等价 media plaintext service policy）中显式列出，并标 `purpose=media_plaintext`。仅出现在 `media_services[]` 而未列入 `plaintext_visible_services[]` 的服务 MUST 被视为禁止解密媒体的 SFU；其试图协商解密角色时 MUST 返回 `media_plaintext_service_not_authorised`。
3. **MLS Governance Binding 覆盖**：成员在 join 前 MUST 校验当前 epoch 的 governance binding `policy_root` 涵盖前两条规则的 cell value；不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商（不能依赖 SFU 单方面声明）。
4. **Downgrade 攻击拒绝**：从 `media_service_decrypts=false` 切换到 `true`（或反向）MUST 走 `ck.realm.policy_components` 正常路径并伴随客户端 UI 显著二次确认；不允许 SFU 直接以 OOB 控制信号宣告自己已"获得解密权"。在 governance binding 尚未 commit 新 policy_root 的窗口内，客户端 MUST 沿用旧 policy 视图判定，禁止根据 OOB 字段提前授权。
5. **进入成员可见 metadata**：`media_service_decrypts=true` 这一"该 Realm 媒体可被服务解密"的事实 MUST 进入 governance binding 覆盖的成员可见 metadata（如 `discussion_metadata_digest`），使任意成员无需依赖客户端 UI 即可从 MLS transcript 独立复算该事实。该 digest MUST 由前 1–3 条所覆盖的 policy cell value 确定性派生；成员本地复算结果与 governance binding 覆盖值不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商。
6. **Conformance negative vector** `ck.vector.webrtc.media_plaintext_downgrade.v1` 必须覆盖：(a) policy_root 未覆盖 `media_service_decrypts` ⇒ 拒绝加入；(b) SFU 未列入 `plaintext_visible_services` 而协商解密 ⇒ 拒绝媒体；(c) UI 未显示警示 ⇒ 拒绝加入；(d) 成员从 MLS transcript 独立复算的 `media_service_decrypts` 事实与 governance binding 覆盖的成员可见 metadata 不一致 ⇒ 拒绝媒体协商。

实际效果：SFU / MCU 不能在 MLS transcript 之外单独变更为可解密媒体的一方。任何看起来"切换成功"但未被 governance binding 覆盖的状态都是 attack，必须 fail closed。
