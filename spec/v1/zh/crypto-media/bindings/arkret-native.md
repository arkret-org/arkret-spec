---
title: Arkret-Native SFU Binding (reference impl)
status: candidate
normative: true
stability: v1
profile: ak.profile.media_service_binding.arkret_native.v1
updated: 2026-07-02
sidebar:
  label: Arkret-native Binding
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [`conformance/normative-language.md`](../../../zh/conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 范围与定位

本附录定义 `ak.realm.media_service.foci[].focus_kind = "arkret_native"` 的 backend binding，承载 Arkret 自定义信令，作为：

1. **Reference impl**：协议自洽性测试与教学用途；
2. **Conformance baseline**：不依赖任何外部 backend SDK 即可跑完 binding-framework 全套 vector。

本 binding 仅作 reference / conformance 用途，**MUST NOT** 作为生产媒体后端被 claim；生产部署 **MUST** 使用 production-grade 的 `media_service_binding` 子 profile（如 `ak.profile.media_service_binding.livekit.v1`）。

声明 `ak.profile.media_service_binding.arkret_native.v1` 的部署 MUST 同时声明 `ak.profile.media_service_binding.v1`。

## 2. Token Exchange

按 [`../media-service-binding.md` §3](../media-service-binding.md) 通用契约。`backend_token` 形态：

```json fragment
{
  "kid": "did:webvh:zCxjAemtszNh7bTFGWFS4m8gv:media.example#key-1",
  "payload": {
    "call_id": "ak:call:...",
    "focus_id": "fra-1",
    "participant_id": "ak:rtc_participant:...",
    "issued_at": "2026-05-27T12:29:56Z",
    "expires_at": "2026-05-27T12:34:56Z",
    "media": {
      "audio": true,
      "video": true,
      "screen": false
    }
  },
  "sig": "base64url...",
  "signature_algorithm": "Ed25519"
}
```
`sig` 是 base64url（无 padding）编码的 Ed25519 签名，由 token issuer 用 `kid` 指向的 service DID
`assertionMethod` key 生成。**signing_input（normative）**：

```text
"ak.media.backend_token.v1" || 0x00 || canonical_json(payload)
```

`canonical_json` 按 [`../../conformance/encoding.md` §2](../../conformance/encoding.md) 的 JCS 规则序列化
上面的 `payload` 对象本身（不含 `kid` / `sig` / `signature_algorithm`）。domain label 与
[`../media-service-binding.md` §3.1](../media-service-binding.md) 表中其它媒体签名点互不相同，防止一把
issuer key 的签名在另一条验证路径下被重解释。SFU 在每次 SDP 协商前 MUST 用该 signing_input 校验签名，
并继续校验：

该对象直接作为 token-exchange response 的 `backend_token`；不得先 JSON 编码成 string。它与同级 `backend_kind="arkret_native"` 构成一个 closed branch，任意未知 member、缺字段或 string 形态均须在进入 backend 前拒绝。

- `kid` 出现在当前 `ak.realm.media_service.service_id` 锚定的 DID 列表中（与 [`../media-service-binding.md` §3](../media-service-binding.md) issuer DID 锚定一致）；
- `call_id` / `focus_id` 与 SFU 当前 session 一致；
- `expires_at` 未过期；
- `participant_id` 唯一性（同 call、同 focus 内不复用）。

## 3. Connect Handshake

`connect_url` 是 HTTPS endpoint（典型 `https://sfu.example.com`）。客户端发送 SFU join request：

```json fragment
{
  "call_id": "ak:call:ARzVic5s2NUShp82C8GPo-shbkm7isUWyvILLThc3aNL",
  "realm_id": "ak:realm:...",
  "focus_id": "fra-1",
  "participant_binding": {},
  "backend_token": "<token from §2>",
  "capability_refs": [
    "ak:grant:..."
  ],
  "desired_media": {
    "audio": true,
    "video": true,
    "screen": false
  }
}
```
SFU response：

```json fragment
{
  "participant_id": "ak:rtc_participant:0198c2f4-0000-7000-8000-000000000000",
  "transport": "webrtc",
  "offer": {
    "type": "offer",
    "sdp": "v=0\r\n..."
  },
  "sfu_signature": {
    "kid": "did:webvh:zCxjAemtszNh7bTFGWFS4m8gv:media.example#key-1",
    "sig": "base64url..."
  }
}
```
`sfu_signature.sig` 同样是 base64url（无 padding）Ed25519 签名，由 SFU 用 `kid` 指向的 service DID
`assertionMethod` key 生成。**signing_input（normative）**：

```text
"ak.media.sfu_answer.v1" || 0x00 || canonical_json({call_id, focus_id, participant_id, realm_id, sdp})
```

`sdp` 取该响应 `offer.sdp`（或 `answer.sdp`，取决于该轮协商方向）的逐字节原值；其余四项取该轮
handshake 的对应值。客户端 MUST 用同一 signing_input 验签，并 MUST 确认 `kid` 落在当前
`ak.realm.media_service.service_id` 锚定的 DID 列表内。

SFU MUST 在 response 中回显 token exchange 阶段已 issued 的同一 `participant_id`；如果 SFU 派生了新的 internal participant id（如 RTP SSRC 或 LiveKit-style 短 ID），它 MUST 自己内部映射，不出 SFU API 边界。

客户端 MUST：

1. 验证 `sfu_signature` 的 `kid` 与 token issuer 同 DID 集合（不必同 key，但同 service）；
2. 验证 `participant_id` 与 §2 token 响应中的值一致；不一致 → `participant_id_unrecognised` 并断连。

## 4. SDP 协商

Arkret-native SFU 接受标准 WebRTC offer/answer。协议层不约束具体 codec / extension 集合，但：

- SFrame ([RFC 9605](https://www.rfc-editor.org/rfc/rfc9605.html)) MUST 在 SDP 中协商；客户端 MUST 拒绝缺 SFrame extension 的 answer，除非 `media_service_decrypts=true` 经 [`../media-service-binding.md` §8.2](../media-service-binding.md) 三层校验通过。
- SDP `a=fingerprint` MUST 与 token exchange 中绑定的 device cert 一致。

## 5. E2EE Key Injection

按 [`../media-service-binding.md` §8.1](../media-service-binding.md) 通用契约。Arkret-native SFU 的 reference adapter 直接调 WebRTC Insertable Streams API，把 `key_bytes` 装载到 RTP frame encryptor。

`media_service_decrypts=false`（默认）：`key_bytes` 不离开客户端，SFU 只看到密文 RTP payload。

`media_service_decrypts=true`（需 [`../media-service-binding.md` §8.2](../media-service-binding.md) 三层校验）：客户端把 `key_bytes` 通过 Arkret-controlled keying path 提交给 SFU；SFU 在受控边界内解密，不得 forward key 到 backend cluster 外。

## 6. Capability Mapping

| Arkret capability | Arkret-native SFU 行为 |
| --- | --- |
| `ak.call.join` | 接受 SDP offer |
| `ak.call.screen_share` | 接受 `screen` track 协商；否则拒绝并报 `capability_denied` |
| `ak.call.record` | 录制由 Arkret-side recorder 触发；SFU 不直接产 artifact |
| `ak.call.moderate` | SFU 接受 `mute_remote` / `kick_participant` 控制指令，但 MUST 校验 actor 持有该 capability |

## 7. Cascading

Arkret-native reference impl **不实现** SFU-to-SFU cascading；同一 `cascade_group` 内的 focus 仅做 client-side region preference 排序，不做媒体路径桥接。需要 cascading 的部署 MUST 使用支持 mesh 的 production-grade backend binding。

## 8. Failure Mode

| 失败 | 错误码 |
| --- | --- |
| token signature invalid / expired | `proof_invalid` / `token_expired` |
| `focus_id` mismatch | `focus_mismatch` |
| SDP 协商失败 | `media_negotiation_failed` |
| SFU 不在 `plaintext_visible_services` 但收到解密请求 | `media_plaintext_service_not_authorised` |
| backend 试图用非 §5 key 源 | `e2ee_key_source_unauthorised` |

## 9. Conformance Vectors

实现声明 `ak.profile.media_service_binding.arkret_native.v1` 时，至少通过：

- 上游 `ak.profile.media_service_binding.v1` 的全部 `ak.vector.media_binding.*` vector（focus_selection / session_focus / token_exchange / token_issuer_unauthorised / participant_binding / unknown_type / e2ee_key_source / participant_id / recording_artifact / recording_exporter_label）。数量与命名以 [`../../../artifacts/registry/vector-registry.json`](../../../artifacts/registry/vector-registry.json) 为准，本节不复述计数。
- arkret_native-specific：实现自由附加，但 wire 不得引入 v1 周期内 unregistered 字段。

具体向量编排见 [`../../../artifacts/registry/vector-registry.json`](../../../artifacts/registry/vector-registry.json)。
