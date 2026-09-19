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

本文件定义 Arkret 多人会议的 **transport-agnostic 媒体服务 backend 绑定**：媒体服务发现（`ak.realm.media_service` 的 multi-focus 描述符）、token / participant binding 兑换、focus 选举与 session 持久化、SFU 权限与 participant identity 交叉校验，以及媒体 E2EE 帧密钥注入与治理绑定。LiveKit / mediasoup / Janus / arkret_native / MoQ-relay 都作为可替换 backend 通过 `foci[].focus_kind` 区分，具体 wire 见 [`bindings/<focus_kind>.md`](./bindings/) 附录。

边界：

- ephemeral 信令（offer/answer/candidate、ICE/TURN 发现与刷新、一对一通话、推送）见 [`webrtc-signaling.md`](./webrtc-signaling.md)。
- durable 会议状态（`ak.call.state` payload、状态机、participant 与录制生命周期）见 [`call-state.md`](./call-state.md)。

## 2. Realtime Media Services

`ak.realm.media_service` 把媒体服务声明为 **multi-focus 列表 + transport-agnostic backend 描述符**。协议层永不规定 SFU 内部协议；LiveKit / mediasoup / Janus / arkret_native / MoQ-relay 都作为可替换 backend 通过 `foci[].focus_kind` 区分，具体 wire 见 [`bindings/<focus_kind>.md`](./bindings/) 附录。

```json fragment
{
  "kind": "ak.realm.media_service",
  "payload": {
    "value": {
      "service_id": "ak:did_core:webvh:z7ECJ5c1A1o5Xr1AdPqPCBD7L",
      "modes": [
        "turn",
        "sfu"
      ],
      "ice_config_endpoint": "https://media.example.com/_arkret/self/rtc/ice-config",
      "foci": [
        {
          "focus_id": "fra-1",
          "focus_kind": "livekit",
          "region": "eu-fra",
          "token_endpoint": "https://media.example.com/_arkret/self/rtc/token",
          "connect_url": "wss://livekit-fra.example.com",
          "capabilities": ["audio", "video", "screen", "e2ee_sframe"],
          "health_endpoint": "https://media.example.com/_arkret/self/rtc/health/fra-1"
        },
        {
          "focus_id": "us-east-1",
          "focus_kind": "livekit",
          "region": "us-east",
          "token_endpoint": "https://media.example.com/_arkret/self/rtc/token",
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
}
```
字段语义（normative）：

- `foci[].focus_id`：focus 在该 Realm media service 内的稳定 ID；进入签名 canonical bytes 与 `session_focus` 选举（见 [`call-state.md` §4.1](./call-state.md)）。
- `foci[].focus_kind`：backend binding 标识。字段名用 `kind` 轴而不是 `type`：这是 Arkret 自有的封闭 registry，而 `type` 轴按 [`classification-field-registry.json`](../../artifacts/registry/classification-field-registry.json) 只留给逐字沿用外部标准的字段。v1 注册值：`livekit`、`mediasoup`、`janus`、`arkret_native`、`moq_relay`（实验保留位，v1 周期内不提供 normative binding）。`moq_relay` 在激活前必须由独立 binding 精确钉定 `draft-ietf-moq-transport` revision、Arkret participant/session/track 到 MOQT namespace/track/object 的映射、relay authorization、SFrame / secure-object 绑定、resume 与错误语义；草案 revision 变化按新 binding profile release 处理，不得原地漂移。客户端遇到未知或 unsupported `focus_kind` MUST fail closed（错误码 `unknown_focus_type`），不得尝试把 token 交给任意 SDK。
- `foci[].token_endpoint`：token 兑换端点；所有 backend 共用同一抽象（见 §3），差异只在 `backend_token` 形态。
- `foci[].connect_url`：backend 连接入口；具体协议由 backend binding 附录定义。
- `foci[].capabilities[]`：该 focus 支持的能力子集，用于客户端能力协商。
- `foci[].health_endpoint`（optional）：客户端预检 endpoint，返回 `200` + `{"status":"ok","load":<0..1>}`。**只用于尚未 commit `session_focus` 前**排序本地 `foci_preferred`；一旦 `call_focus` 已存在 `session_focus`，connect 失败 MUST 暴露为 focus 不可用，不得静默切到另一 focus（`session_focus_no_split_brain`）。
- `foci[].cascade_group`（optional）：声明属于同一 backend cluster 的 focus 集合；客户端可据此向用户披露"跨区域会议由 backend 内部级联"。协议层不规范 SFU-to-SFU cascading 协议；每个 backend 自行实现 mesh，正式 Arkret wire 只公开 `foci[].cascade_group` 与用户可见披露语义。

`ak.realm.media_service` 的媒体描述符位于 `payload.value`；`payload.value.foci[]` MUST 非空。只提供单个 `sfu_endpoint`、把媒体描述符扁平放在 `payload` 下，或缺少 `payload.value.foci[]` MUST fail closed，返回 `schema_violation` 或 `failed_precondition`，原因码 `media_service_foci_required`；服务端不得在实时路径中自动补写、normalize 或推断 focus。

**字段集合是封闭的（normative）**：`payload.value` 与 `foci[]` 的完整字段集以 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 的 `$defs/realm_media_service_payload` 为权威机读真源，二者都 `additionalProperties: false`；`foci[].focus_id`、`focus_kind`、`token_endpoint` 与 `connect_url` 是 required。**token issuer 的部署配置 MUST NOT 出现在本 typed current result 中**——签名 key id、token audience、TTL 与 backend API 凭据都是 `foci[].token_endpoint` 所指服务自己的配置，把它们写进本 typed current result 会有两个后果：轮换一次 issuer key 就需要一条持有 `ak.realm.media_service` / `ak.policy.manage` capability 的 Realm policy Event，且 issuer 内部配置对全体 Realm 成员外露。客户端与 token issuer MUST 都按同一 schema 消费该 typed current result；任何一侧私自读写未登记字段，都会让另一侧对同一条已签名 typed current result 解析出不同结果，而这种错配不会被任何东西报错。

修改该 state event 需要 `ak.realm.media_service` 或 `ak.policy.manage` capability。

### 2.1 完整性绑定（normative）

`ak.realm.media_service` 的 `service_id`、`ice_config_endpoint` 与 `foci[].token_endpoint` 是媒体 token / TURN credential 签发权与 issuer DID 锚定的**信任根**(见 §3 / §7 与 [`call-state.md` §4.1](./call-state.md))。为保证"谁担保该 `service_id` / endpoint 列表未被篡改",本节固定:

- `ak.realm.media_service` state Event（含 `service_id`、`ice_config_endpoint` 与全部 `foci[].token_endpoint`）MUST 通过普通 Event proof、authority-commit admission 与 accepted RealmCommit state 物化；客户端不得接受未进入当前 accepted policy projection 的本地/OOB endpoint。
- 普通已登录客户端在把这些字段锚定为 credential issuer DID 前，MUST 通过 [`../sync/server-trusted-results.md` §5.9](../sync/server-trusted-results.md) 的 `ak.self.media_service_binding.read.resolve.v1` 取得自己 Station 在其 exact accepted basis 下给出的已验证 `route` 与 `signing_keys`，并把 `route.service_id` 与本地已安装的该 typed current result 当前值逐字比较，再核对 `ice_config_endpoint` 与每个 `foci[].token_endpoint` 的 origin 落在 `route.base_url` 之内；不相等、缺失、stale 或结果窗口已过期时 fail closed（`media_service_binding_uncovered`）。客户端 MUST NOT 自行解析该 service DID 的 method history、witness 记录或 describe，也 MUST NOT 把任意候选 origin 的自报当作 route。服务器、联邦接收方与独立审计者按各自角色继续执行 DID 权威验证。普通 endpoint 变更不改变 MLS key 持有人，因此不得仅为它强制 rekey。
- 只有 `media_service_decrypts` 或 `plaintext_visible_services` 的 accepted effect 改变媒体明文/密钥接收者时，才按 [`encryption-and-audit.md` §2.5](./encryption-and-audit.md) 进入 `key_access_revision` 并等待新 Commit。

## 3. Token Exchange (normative)

会议加入前，客户端 MUST 先向 `foci[].token_endpoint` 兑换 backend 凭证；issuer 是 Arkret-side 授权组件。`backend_token` 是由同级 `backend_kind` 判别的 closed union：`arkret_native` 必须携带 [`bindings/arkret-native.md` §2](./bindings/arkret-native.md) 的 typed object；`livekit`、`mediasoup`、`janus`、`moq_relay` 必须携带非空 opaque string，并由对应 backend SDK 继续解析。客户端 MUST 拒绝 branch 不匹配、未知 backend 或把 object 再编码成 JSON string 的响应。Token endpoint 等价于 [MSC4195 `lk-jwt-service`](https://github.com/element-hq/lk-jwt-service)，但绑定到 Arkret 的 capability、当前 accepted Realm policy；服务实际取得媒体明文时还必须绑定当前 `key_access_revision`。

请求：

```http
POST {token_endpoint}
Authorization: <device proof | bearer>
Content-Type: application/json
```

请求 body（与 `CallMediaTokenExchangeRequestBody` 共用同一机读合同）：

```json schema=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeRequestBody
{
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6mkfixture",
      "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
    }
  },
  "device_id": "ak:device:0198c2f4-0000-7000-8000-000000000001",
  "focus_id": "fra-1",
  "capability_refs": [
    "ak:grant:AUFBzmnhUmJ_VzOH2YJX1xVzwAsxVk_-5MZ_5wu41zCA"
  ],
  "desired_media": { "audio": true, "video": true, "screen": false }
}
```

响应（binding scheme 由本 operation 固定为 `ak.media.participant_binding.v1`，不重复携带）：

```json schema=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeOutcome
{
  "focus_id": "fra-1",
  "backend_kind": "livekit",
  "connect_url": "wss://livekit-fra.example.com",
  "backend_token": "<opaque to Arkret protocol — backend-specific>",
  "participant_id": "ak:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
  "participant_binding": {
    "expires_at": "2026-05-27T12:34:56.000Z",
    "issuer_kid": "did:webvh:z6mkfixture:media.example#key-1",
    "sig": "AA"
  },
  "expires_at": "2026-05-27T12:34:56.000Z",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "actor_id": {
    "kind": "account",
    "account_id": {
      "principal_id": "ak:did_core:webvh:z6mkfixture",
      "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
    }
  },
  "device_id": "ak:device:0198c2f4-0000-7000-8000-000000000001"
}
```

核心约束（normative）：

- **Backend token branch**：`backend_kind` 与 `backend_token` 形状 MUST 逐项匹配。`arkret_native` branch 是 closed `{kid,payload,sig,signature_algorithm:"Ed25519"}` object，其中 `payload` 也是 closed typed object；其余 v1 branch 是非空 string。实现不得使用 `Value`、object-as-JSON-string、先尝试 string 再尝试 object，或任何未登记 fallback。
- **TTL 短期化**：`backend_token` / `participant_binding` `expires_at` 的硬上限 MUST ≤ 600s（10 分钟）；推荐上限 SHOULD ≤ 300s。过期前客户端 MUST 重新兑换；backend token 一旦泄漏在 TTL 内通常不可吊销（除非 backend 提供 revocation list），短 TTL 是工程兜底。
- **Token issuer DID 锚定**：`ak.realm.media_service` 是 `commit-ordered projection` 单值 typed current result；`participant_binding.issuer_kid` 的 controller bare DID MUST 逐字等于当前 epoch 唯一 settled `ak.realm.media_service.service_id`，具体 key MUST 命中 §2.1 同一 service 结果 `signing_keys` 中的某个 `verification_method`。typed current result 缺失、必要证明未就绪、安全确认故障或结果 service 不等时均不可用，不存在多 service 列表或“之一”分支；验签不要求逐 token 在线解析 DID。出现新 service / key epoch、binding invalidation 或该结果窗口过期时重新取得 §2.1 的结果，普通客户端不因此获得 DID 权威验证职责。客户端 MUST 拒绝来自未授权 DID 的 token，错误码 `token_issuer_unauthorised`。该规则把 token 签发权与 Realm policy 锁定，防止任意 service 凭空铸造 join token。
  - **命名与类型（normative）**：`issuer_kid` 是 issuer **key identifier**，不是 issuer service identifier，因此该字段名不得改成 `issuer_id`。其值 MUST 是带 verification-method fragment 的 DID URL（例如 `did:web:media.example#key-1`）；去掉 `#fragment` 后得到的 service DID 才与当前 epoch 的 `service_id` 做锚定。`service_id` 标识服务主体，`issuer_kid` 标识该主体用于本次签名的具体密钥，二者不可互换。
  - **轮换语义（normative）**：`participant_binding` 只承诺六元组 + `expires_at`，**不**绑定签发时的 media_service epoch。issuer 锚定按**写入 `ak.call.state` 时的当前 epoch** `service_id` 判定（[`call-state.md` §4.1](./call-state.md)），因此一次 media_service 轮换（旧 `service_id` 被移出当前 epoch）即时作废由被移出 service 签发、尚在 TTL 内的在途 binding：reducer MUST 以 `token_issuer_unauthorised` 拒绝其落账，客户端 MUST 重新向当前 epoch service 兑换。这是已知的 ≤600s 活性窗口（与 TTL 上限一致），不引入跨 epoch binding 复用；实现 MUST NOT 为旧 epoch binding 增设 grace 接受。
- **`participant_id` 形态**：作为 SFU-local 短期随机 handle，scope 限 `(call_id, focus_id, sfu_did)`；MUST NOT 携带可关联到长期 actor 身份的可识别信息（与 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md) pairwise pseudonym 规则对齐），也不得由可公开重算的主体元组确定性派生。六元组绑定职责由下方 `participant_binding` 的签名承诺承担。
- **`participant_id` 传播边界**：因为它本身不携带 actor 链接信息，客户端 **MUST** 把它写入 `ak.call.state.roster_delta.op="join"` 的 participant value（用于 §7 cross-check）——这条安全集合 value 是 Realm-encrypted control state，不构成 actor-身份外泄。但 `participant_id` MUST NOT 进入下列三类 surface：(a) 任何 plaintext audit log / 服务方 access log（包括 backend SFU 自身的日志）；(b) 任何 unencrypted ephemeral / push / telemetry 通道；(c) backend 一侧对外的 metrics、tracing 标签或 cross-tenant 数据导出。Backend 内部允许保留它作为 SFU-local routing handle，但不应跨 call leg / 跨 tenant 复用。
- **唯一载体与重建**：`participant_binding` 恰为 `{expires_at, issuer_kid, sig}`。token outcome 同时携带 realm_id、call_id、focus_id、actor_id、device_id、participant_id；与 exact request 对应坐标必须一致。durable roster entry 保存 actor_id/device_id/participant_id/focus_id 与该 binding，realm_id 和 call_id 从 enclosing Call 身份取得。写入时 focus_id 必须等于已接受的 selected focus；以后轮换 focus 不改旧 entry 的签名输入。p2p/mesh 不携带这组三字段。无完整七元组的 carrier MUST 拒绝，不能查询不相关状态补齐、使用空值或保留另一种完整 binding 形状。issued_at 没有签名或消费者，删除；签名七元组与域分隔 bytes 保持不变。
- **`participant_binding` 是 token issuer 对 `(realm_id, call_id, focus_id, actor_id, device_id, participant_id, expires_at)` 的签名承诺**。客户端 MUST 先验证该 binding，再把它写入 / 对照 `call_roster` 已确认活跃集合（见 [`call-state.md` §4](./call-state.md)）。backend 只看到 `participant_id` 与 `backend_token`，不应获得长期 actor 身份。
- **落账时序**：客户端在获得 token exchange response 后，MUST 先提交包含本端 `participant_id` 与 `participant_binding` 的单项 `ak.call.state.roster_delta` join，并等待该 event 被服务端接受，之后才可把该 identity 视为 durable roster 成员并向用户暴露/订阅对应 SFU media stream。`ak.call.signal` 中的 `invite` / `answer` 只表示实时协商意图，MUST NOT 作为 participant authorization 或 cross-check 真源。
  - **签名输入（normative，跨实现互通契约）**：`participant_binding.sig` MUST 是 issuer 私钥（对应 `issuer_kid`）对下列字节串的 Ed25519 签名：

    ```text
    signing_input =
      "ak.media.participant_binding.v1" || 0x00 ||
      canonical_json({ actor_id, call_id, device_id, expires_at,
                       focus_id, participant_id, realm_id })
    ```

    第一段是固定 ASCII 域分隔 label（逐字节等于 `scheme` 值），随后单字节 `0x00` 分隔，再接 7 字段对象的 canonical JSON（RFC 8785 JCS：键按字母序、无多余空白，故字段书写顺序无关）。**签名仅覆盖这 7 个权威字段**；binding 对象另带的 `scheme` / `issuer_kid` / `issued_at` 是**未签名元数据**，MUST NOT 进入 `signing_input`。接收方据 wire 上的 7 个权威字段值重建 `signing_input` 再验签——故篡改任一权威字段都会令验签失败。任何 media service（arkret_native / LiveKit / 第三方）MUST 按此构造，任何客户端 / reducer MUST 按此验签；实现 MUST NOT 引入私有 domain 前缀，也 MUST NOT 把元数据字段并入签名输入，否则破坏跨 service 互通。
- 调用者 device proof / bearer 有效，未 revoked。
- Actor 在 `realm_id` 拥有 `ak.call.join` capability；`desired_media` 不超过授权（`ak.call.screen_share` 等子 capability 检查）。
- Realm policy 允许该 `focus_id`（即 focus 出现在当前 `ak.realm.media_service.foci[]` 中）。
- 如果 `call_focus` 已存在 `session_focus`，请求的 `focus_id` 必须与其完全一致；不一致 MUST 返回 `focus_mismatch`。
- call state 允许新 participant；且按分层 predicate 校验该 `(actor_id, device_id)`：actor 在 `realm_id` 的 Realm membership 为 `join`（若 scoped 到 Circle 则同时为该 Circle 活跃成员）、account status 不为 `suspended` / `deactivated` / `erasure_pending`、`device_id` 的 device grant 未 revoked。
- `ak.realm.media_service` 与 token request 使用同一 current accepted policy projection；stale endpoint 返回 `media_service_binding_uncovered`。若服务将解密媒体，另要求 active MLS `key_access_revision` 覆盖当前 key-access policy；不一致返回 `mls_governance_binding_stale`。
- 如果 backend 将解密媒体（`media_service_decrypts=true`），完整执行 §8.2 的三层校验。

### 3.1 签名 domain label 分离（normative）

媒体路径上的每一类 **Ed25519 签名** MUST 以一个**独立的 ASCII domain 分隔 label** 前缀其 `signing_input`，再接单字节 `0x00` 分隔与该签名覆盖的 canonical bytes。该 label 是签名的安全域分离参数：它把"同一 issuer key 在不同用途上产生的签名"彼此隔离，使任一签名 MUST NOT 被验证方在另一用途下重新解释（cross-protocol / cross-purpose signature confusion）。任何 media service（arkret_native / LiveKit / 第三方）MUST 按本表构造签名，任何客户端 / reducer MUST 按对应 label 重建 `signing_input` 再验签；验证方 MUST 在重建时使用其**期望用途**对应的 label，签名方使用了不匹配 label 即视为验签失败。

v1 Ed25519 媒体签名点与其 label 常量（逐字节 ASCII）：

| 签名点 | domain label 常量 | signing_input 覆盖 | 定义处 |
| --- | --- | --- | --- |
| `participant_binding.sig` | `ak.media.participant_binding.v1` | `label \|\| 0x00 \|\| canonical_json({actor_id, call_id, device_id, expires_at, focus_id, participant_id, realm_id})`（7 元组，见 §3） | §3（已字节锁，本节仅引用，不改） |
| ICE config response `signature` | `ak.media.ice_config.v1` | `label \|\| 0x00 \|\| canonical_json(ICE config response 去除 `signature` 字段后的完整权威对象)`；300 秒 bucket 与 expiry 由已签 `issued_at, ttl_seconds` 计算，不进入 wire | [`webrtc-signaling.md` §4.1](./webrtc-signaling.md) |
| `backend_token.sig`（`backend_kind="arkret_native"`） | `ak.media.backend_token.v1` | `label \|\| 0x00 \|\| canonical_json(backend_token.payload)` | [`bindings/arkret-native.md` §2](./bindings/arkret-native.md) |
| `sfu_signature.sig`（`backend_kind="arkret_native"`） | `ak.media.sfu_answer.v1` | `label \|\| 0x00 \|\| canonical_json({call_id, focus_id, participant_id, realm_id, sdp})` | [`bindings/arkret-native.md` §3](./bindings/arkret-native.md) |

约束细则：

- **ICE config response 签名 MUST 用 distinct label `ak.media.ice_config.v1`（normative）**：ICE config 响应签名覆盖的完整权威对象（包括 `realm_id` / `call_id` / `actor_id` / `device_id` / `issued_at` / `ttl_seconds` / `ice_servers[]` 与策略字段）与 participant_binding 的 7 元组**不同用途、部分字段重叠**；若两者复用同一 label，则一个 issuer key 对 ICE config 的签名可能被在 participant_binding 验证路径下重解释（反之亦然）。因此 ICE config 签名 MUST 以 `ak.media.ice_config.v1` 前缀其 signing_input。canonical 定义见 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md)。
- **不在本 label 体系内的媒体凭证**（据实说明各自的域，MUST NOT 强加 Ed25519 label）：
  - `backend_token`（LiveKit 部署）是 **LiveKit JWT**，自带 `alg` / `iss` 等 JOSE header 与 issuer 标识，其签名域由 JWT 标准与 LiveKit API Key/Secret 决定（见 [`bindings/livekit.md` §2](./bindings/livekit.md)），不进入本节 Ed25519 label 体系。
  - TURN REST 凭证不是 Ed25519 签名而是 **HMAC**：`credential = HMAC-SHA256(turn_shared_secret, username)`，其中 `username = "<expiry-unix>:<per-call-pairwise-pseudonym>"`（见 [`webrtc-signaling.md` §4.1](./webrtc-signaling.md)）；pseudonym 本身亦由 HMAC 派生。HMAC 的域由其 `turn_shared_secret` 与 username 输入构造决定，不属于 Ed25519 签名 domain label 范畴。
- 本节**只规定 Ed25519 签名类**（`participant_binding` / ICE config / arkret_native backend token 与 SFU answer）的 domain label 分离；MUST NOT 借此更改任何媒体密钥本身、MUST NOT 更改客户端对 issuer / service DID 公钥的锚定路径（§2.1 / §3 / §6 的公钥锚定保持不变）。新增 label 仅约束签名输入前缀，不引入新密钥派生。

## 4. SFU Service

SFU 在 v1 通过 [§2](#2-realtime-media-services) 的 `foci[]` 声明，每个 focus 通过 `focus_kind` 选择具体 backend binding：

- `focus_kind="livekit"`：见 [`bindings/livekit.md`](./bindings/livekit.md)。
- `focus_kind="arkret_native"`：见 [`bindings/arkret-native.md`](./bindings/arkret-native.md)（reference / conformance binding，不作为生产媒体后端）。
- `focus_kind="mediasoup"` / `focus_kind="janus"` / `focus_kind="moq_relay"`：保留位，v1 周期内不提供 normative binding；客户端遇到 unsupported `focus_kind` MUST fail closed，错误码 `unknown_focus_type`。

不论 backend 类型，client→backend 媒体协商前 MUST 先完成 [§3 Token Exchange](#3-token-exchange-normative)；具体 `backend_token` 形态、connect handshake、SDP 协商由 backend binding 附录定义。下面的 §5 / §6 / §7 是跨 backend 通用约束。

## 5. Focus Selection 与 Session 持久化（normative）

会议第一次 join 时由客户端排序 `foci_preferred[]` 写入 `ak.call.state.roster_delta.participant.foci_preferred`；之后用 **deterministic, no-vote** 规则收敛为单一 `session_focus`：

1. 若 `call_focus` 已存在 `session_focus`，它就是唯一 authoritative focus；客户端和 token issuer MUST 使用它。
2. 若 `session_focus` 尚不存在，收集所有当前 active member 的 `(joined_at, actor_id, device_id, foci_preferred)` 元组；按 `(joined_at, actor_id, device_id)` 升序，**oldest_membership 的 `foci_preferred[0]` 被写入 `session_focus`**。
3. 后加入者 MUST 使用同一 `session_focus`，无论自己的偏好；如果该 focus 在自己的 preferred 列表中不存在，客户端 MAY 拒绝加入（fail closed），错误码 `focus_unavailable_for_client`。
4. Token issuer MUST 拒绝任何 `focus_id != session_focus` 的 token exchange，错误码 `focus_mismatch`；该规则优先于 health check、region preference 和 load balancing。
5. 当 oldest member 离开，focus **不自动迁移**（避免媒体路径中断）；session 持续到所有人离开后才重置。v1 不提供 in-session focus migration。

### 5.1 P2P→SFU 升级复用本节选举（normative）

P2P 起步的通话在并发参与者 > 2 时 MUST 收敛到 SFU（normative 触发、信令与 `mode` 写入规则见 [`call-state.md` §6](./call-state.md)）。升级 MUST 直接复用本节的 deterministic, no-vote `session_focus` 选举：由 oldest_membership 的 `foci_preferred[0]` 选出 `session_focus`，各设备经 `ak.call.signal{signal_kind=focus_join}`（见 [`webrtc-signaling.md` §5](./webrtc-signaling.md)）迁移媒体，原 P2P leg 在迁移完成后优雅拆除。升级不引入任何新的投票 / leader 选举路径，也不为升级新增 focus migration 例外——一旦 `session_focus` committed 即遵守第 1–5 条的 write-once 与 no-split-brain 规则。

## 6. SFU 权限

SFU MUST verify:

- Realm media service policy allows this `(focus_id, service_id)` 组合（即 focus 出现在当前 `ak.realm.media_service.foci[]`）。
- actor has `ak.call.join`（capability registry canonical 命名，参见 [`../authz/capabilities.md`](../authz/capabilities.md) §5）。
- actor/device is not revoked。
- call state accepts new participants。
- media request does not exceed grants, e.g. screen share requires `ak.call.screen_share`。

客户端 MUST 校验：

- token issuer service DID 出现在当前 `ak.realm.media_service.service_id` / `foci[].token_endpoint` 锚定的 service DID 列表；
- token exchange 响应的 `participant_binding.sig` 通过；
- backend 通知 "X 加入会议" 时携带的 `participant_id` 与 call roster 已确认活跃集合 中的 participant value 一致（见 §7 cross-check）。

## 7. Participant Identity 交叉校验（normative）

backend "X 加入会议" 通知到达客户端时，客户端 MUST：

1. 从 backend 通知中提取 `participant_id`。
2. 在当前 `call_roster` 已确认活跃集合 中查找同一 `participant_id`。
3. 验证该 participant entry 内的 `participant_binding` 签名（[§3](#3-token-exchange-normative)），确认它覆盖与 §3 签发侧完全相同的权威元组 `(realm_id, call_id, focus_id, actor_id, device_id, participant_id, expires_at)`（此处使用该 roster entry 冻结的 `focus_id`，不得以后来变更的 session_focus 替代；签名输入字段集合与名称以 §3 为准，不得省略 `expires_at`）。
4. 不匹配或签名无效 → 拒绝为该 participant 建立媒体流（不收音、不订阅 video），错误码 `participant_id_unrecognised`。

这道闸门防止 backend 单方面 "塞入" 未经 Realm 授权的参与者——backend 运营方误配置、被入侵或恶意 inject 都无法绕过 Arkret-side `call_roster` 真源。

## 8. E2EE with SFU

SFU 模式 SHOULD 使用 WebRTC Insertable Streams / SFrame 或等价机制实现端到端媒体加密。SFU 可转发 RTP 包和处理转发层 metadata，但不应获得明文媒体。

若 SFU 或 MCU 会解密媒体，客户端 MUST 显示明确安全边界，并且 Realm policy MUST 允许 `media_service_decrypts=true`。

### 8.1 E2EE Key Injection 通用契约（normative）

无论 backend 自身是否支持 E2EE，所有 binding 附录的 E2EE 章节 MUST 规定一个最小契约，使得 **客户端侧 binding adapter / media SDK** 能从 Arkret 协议层接收 frame key，而不从 backend 自带密钥分发机制取。最小契约：

```text
inject_frame_key(key_bytes: 32-byte secret,
                 epoch_id: u64,
                 sender_binding: canonical_json{
                   realm_id, call_id, focus_id,
                   participant_id, device_id
                 },
                 rotation_trigger: enum{member_join, member_leave, manual, scheduled})
```

约束：

- `key_bytes` MUST 由 Arkret MLS exporter 派生，**label 固定为 ASCII 字符串 `"ak.rtc-frame-key/v1"`**（length=19 bytes，无 trailing newline；RFC 9420 §8 `MLS-Exporter` 的 `Label`，`KDF.Nh` 长度 32 bytes）。`Context` MUST 是 canonical JSON bytes of exactly `{realm_id, call_id, focus_id, epoch_id, participant_id, device_id}`，其中 `participant_id` / `device_id` 来自已验证的 call roster participant value 与 `participant_binding`。`Context = ""`、缺少 sender 字段或只绑定 epoch 的派生 MUST fail closed(`e2ee_key_source_unauthorised`)。`ak.rtc-frame-key/v1` / `ak.rtc-recording-key/v1` / `ak.rtc-transcript-key/v1` 是**固定的 canonical wire label**（密钥派生的安全域分离参数，canonical 登记见 [`exporter-label-registry.json`](../../artifacts/registry/exporter-label-registry.json)）；实现 MUST 逐字节使用登记的 label 字符串，MUST NOT 与其它 label 混用。该 label 的任何变更属于 wire-breaking，必须开新 profile。
- `epoch_id` 与 Realm MLS epoch 一一对应。
- `rotation_trigger` 不得被 adapter 当作不透明枚举透传:`rotation_trigger=member_leave`（成员离开 / 被踢 / 被 ban）**MUST** 对应一次 MLS commit（Remove）并推进 `epoch_id`，使新 `key_bytes` 从离开成员不掌握的新 group secret 派生；adapter **MUST NOT** 在 `member_leave` 时仅更换 SFrame KID / keyIndex 而复用旧 epoch 的 group secret，否则离开成员仍能解密后续帧（E2EE 媒体前向保密失效）。`member_join` 同样 MUST 绑定推进后的 `epoch_id`。`manual` / `scheduled` 触发亦 MUST 携带推进后的 `epoch_id`；任何 `rotation_trigger` 下若 `epoch_id` 未相对前一帧密钥推进，客户端 MUST fail closed（`e2ee_key_source_unauthorised`）。
- backend SDK / adapter 内部如何把该 sender-bound key 映射到 SFrame / 私有帧加密格式由附录指定，但 **MUST NOT** 接受任何非该接口的 key 源（如 backend 自带 KMS、自生成 random key）。SFrame KID / key slot MUST 区分同一 epoch 内的不同 sender；若 adapter 无法为 active sender 集合提供无冲突映射，客户端 MUST 拒绝启用该 binding。除非 Realm policy 明确允许 `media_service_decrypts=true` 且完成 §8.2 三层校验，`key_bytes` MUST NOT 被发送给远端 SFU / MCU。
- Conformance negative vector `ak.vector.media_binding.e2ee_key_source.v1`：backend 用自家密钥 → 客户端 MUST 拒绝并报 `e2ee_key_source_unauthorised`。

Conformance vectors for the full media binding framework：

- `ak.vector.media_binding.focus_selection_oldest_membership.v1` — §5 oldest_membership 选举正确性。
- `ak.vector.media_binding.session_focus_no_split_brain.v1` — `session_focus` 写入后 connect 失败 MUST 暴露为不可用，不静默切 focus。
- `ak.vector.media_binding.token_exchange_minimal.v1` — §3 token exchange 最小字段集 + TTL ≤ 600s。
- `ak.vector.media_binding.token_issuer_unauthorised.v1` — issuer DID 不在 service_id 锚定列表时拒绝。
- `ak.vector.media_binding.participant_binding_required.v1` — 缺失或签名无效的 `participant_binding` 必须拒绝。
- `ak.vector.media_binding.unknown_type_fail_closed.v1` — §2 未知 `foci[].focus_kind` MUST fail closed。
- `ak.vector.media_binding.participant_id_unrecognised.v1` — §7 backend 通知的 participant 不在 `call_roster` 已确认活跃集合 时拒绝该流。
- `ak.vector.media_binding.recording_artifact_via_arkret_blob.v1` — [`call-state.md` §5](./call-state.md) backend-generated recording 必须经 Arkret blob pipeline。
- `ak.vector.media_binding.recording_exporter_label.v1` — backend-generated recording 必须使用 `"ak.rtc-recording-key/v1"` 与绑定 recording transcript 的 Context，不得复用 SFrame key label。

### 8.2 治理绑定（normative）

**三层关系**: `ak.realm.media_service` declares SFU existence; `plaintext_visible_services` grants decryption authority; Event kind `ak.realm.policy_bundle` 的 payload path `media_service_decrypts=true` carries the boolean toggle — 三者 MUST 同时成立才能让 media service 解密。

`media_service_decrypts=true` **不**是一个可单独由 SFU 服务自报或客户端配置的开关。它 MUST 同时满足下列约束，否则客户端 MUST 拒绝加入会议、SFU MUST 拒绝媒体协商：

1. **进入 `ak.realm.policy_bundle`**：`media_service_decrypts=true` MUST 由一条 `ak.realm.policy_bundle` 显式写入，受 capability `ak.policy.manage` 控制；当前 accepted bundle 未包含该开关时 MUST 视为未开启。
2. **进入 `plaintext_visible_services`**：解密媒体的 SFU / MCU service DID MUST 在 Realm policy 的 `plaintext_visible_services[]`（或等价 media plaintext service policy）中显式列出，且该条目的机器可判定 `data_classes[]` MUST 包含 `media_plaintext`。自由文本 `purposes` 只作解释，MUST NOT 单独授权明文。仅出现在 `media_services[]`、仅在 `purposes` 中声称媒体处理用途，或未获 `media_plaintext` data class 的服务 MUST 被视为禁止解密媒体的 SFU；其试图协商解密角色时 MUST 返回 `media_plaintext_service_not_authorised`。
3. **MLS key-access revision 覆盖**：成员在 join 前 MUST 核对自己 Station 从当前 accepted policy 求出的 key-access checkpoint 与实际 MLS GroupContext 的绑定，确认它覆盖前两条规则产生的实际 key-access value；policy typed current result 自动进入该闭合 checkpoint 的注册规则保留；不一致时 MUST 触发 `mls_governance_binding_stale` 并拒绝媒体协商（不能依赖 SFU 单方面声明）。
4. **Downgrade 攻击拒绝**：从 `media_service_decrypts=false` 切换到 `true`（或反向）MUST 走 `ak.realm.policy_bundle` 正常路径并伴随客户端 UI 显著二次确认；UI 未展示警示或用户未完成二次确认时 MUST 在发放 join token / media key 前拒绝（`media_plaintext_warning_required`）。不允许 SFU 直接以 OOB 控制信号宣告自己已"获得解密权"。由于该事实改变谁可取得媒体密钥，它必须改变 media scope 的 `key_access_revision`；新 Commit accepted 前客户端沿用旧视图并禁止按 OOB 字段提前授权。
**Conformance negative vector** `ak.vector.webrtc.media_plaintext_downgrade.v1` 必须覆盖：(a) 当前 `key_access_revision` 未授权 `media_service_decrypts` ⇒ 拒绝加入；(b) SFU 未列入 `plaintext_visible_services` 而协商解密 ⇒ 拒绝媒体；(c) UI 未显示警示 ⇒ 拒绝加入。

实际效果：SFU / MCU 不能在 MLS transcript 之外单独变更为可解密媒体的一方。任何看起来“切换成功”但未被当前 `key_access_revision` 授权的状态都是 attack，必须 fail closed。
