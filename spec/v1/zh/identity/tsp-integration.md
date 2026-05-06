---
title: TSP Integration
---

> **状态：v1.1+ interop extension（非 core 互操作）**。Contrix v1 core 默认使用
> HTTPS JWE / MLS DM 进行跨主体可信传输。Trust Spanning Protocol 是可选的 metadata-privacy
> 增强 transport；core v1 实现 **不要求** 实现本文档。当 TSP 实现成熟后将以独立 interop
> profile 承载稳定 wire 形态。

## 1. 目标

Contrix MAY 集成 Trust over IP 的 Trust Spanning Protocol (TSP)，用于跨 DID、KERI AID、`did:webs`、`did:x509`、`did:peer`、X.509/URN 等 Verifiable Identifier (VID) 体系建立可信消息关系。

TSP 在 Contrix 中是可选 transport / trust binding，不是 Space 状态、capability、reducer 或 MLS 的替代品。

## 2. TSP 适用位置

TSP 适合用于：

- identity registry / witness / replica 之间的可信消息交换。
- DID / VID support system 之间的验证和信任评估。
- 跨组织 service DID 的 federation bootstrap。
- Applet、policy server、media service、agent runtime 的服务间认证通道。
- pairwise / private DID 场景下的低关联消息路由。
- 3PID 邀请、VC presentation、handle claim 等身份相关控制消息。
- agent protocol handoff 前的对端 VID 验证和信任建立。
- holder 向特定 verifier / 组织定向发送选择性披露 presentation。

TSP 不适合直接承担：

- Space 多成员群组 E2EE 状态机。
- MLS epoch / group membership 变更。
- Object / Morph / Relation / Event reducer。
- capability 授权本身。
- 高吞吐媒体 RTP 转发。

## 3. 与 Contrix 身份模型的映射

TSP 的 VID 可映射到 Contrix：

| TSP | Contrix |
| --- | --- |
| VID | principal DID / service DID / pairwise DID / supported external identifier |
| TSP Endpoint | actor device、service node、Applet、policy server、agent runtime |
| TSP Relationship | pairwise trusted channel between two principals/services |
| TSP Support System | identity registry、DID method adapter、witness、governance registry |
| TSP Intermediary | Sync Service、privacy router、store-and-forward service |
| TSP Message | signed/encrypted transport envelope carrying Contrix operation or control payload |

Contrix DID method adapter SHOULD expose whether a principal or service supports TSP.

## 4. TSP Binding Discovery

服务可在 DID Document 或 normalized principal view 中声明：

```json
{
  "type": "cx.service.tsp",
  "id": "did:web:server.example#tsp",
  "serviceEndpoint": "https://server.example/tsp",
  "supported_vid_schemes": ["did", "urn"],
  "supported_modes": ["direct", "routed", "nested"],
  "supported_payloads": [
    "cx.federation.transaction",
    "cx.identity.presentation",
    "cx.agent.protocol_session.start"
  ],
  "metadata_privacy": {
    "nested_messages": true,
    "routed_messages": true
  }
}
```

Feature discovery SHOULD also list `tsp` as a supported transport binding when available.

## 5. Contrix over TSP

Contrix operation 可作为 TSP application payload：

```json
{
  "operation": "federation.transaction",
  "content_type": "application/contrix+json",
  "space_id": "cx:space:...",
  "payload_hash": "sha256:...",
  "payload": {}
}
```

规则：

- TSP authenticity 不替代 Contrix event signature；两者 SHOULD 都验证。
- TSP confidentiality 不替代 Space E2EE；它只保护 transport message payload。
- TSP relationship 不自动授予 Space membership 或 capability。
- TSP routed mode 中 intermediary 不应被视为可信授权方。
- 若使用 nested TSP message 隐藏内层 VID，外层 endpoint 仍必须满足 Contrix routing 和 policy 要求。

## 6. 与 MLS 的差异

| 维度 | TSP | MLS |
| --- | --- | --- |
| 核心目标 | 跨 VID 端点的可信消息交换 | 群组端到端加密和成员状态演进 |
| 通信形态 | 方向性异步 message，可 direct 或 routed | group session，有 epoch、commit、proposal、welcome |
| 身份模型 | VID 抽象，支持 DID/URN/X.509 等 | 依赖外部 credential 绑定成员 identity |
| 加密对象 | 单条 message payload，可选 confidentiality | 群组消息和 epoch secret |
| 元数据隐私 | nested message、routed message 等机制 | 主要保护内容；成员/epoch/发送关系需要额外设计 |
| 成员管理 | TSP relationship table，不是群组 membership | 明确 Add/Update/Remove、epoch 变更 |
| 适合场景 | 服务间、跨身份体系、pairwise 控制消息 | Space/会议/群聊的多成员 E2EE |
| 是否替代对方 | 不替代 MLS | 不替代 TSP 的跨 VID trust binding |

## 7. 推荐组合

Contrix SHOULD 采用以下组合：

- Pairwise service / identity control messages：MAY use TSP。
- Federation bootstrap：MAY use TSP to verify service VID and establish secure channel。
- Space durable events：MUST still use Contrix event signature / hash / reducer。
- Encrypted Space content：SHOULD use MLS。
- Agent handoff：MAY use TSP to authenticate endpoint, then use A2A / ACP / custom transport as negotiated。
- WebRTC media：MUST NOT use TSP for RTP media encryption; use WebRTC SRTP plus SFrame/Insertable Streams where needed。

### 7.1 渐进披露中的 TSP

TSP 可以作为选择性披露 presentation 的私密传输层。推荐模式：

- Verifier 使用 organization-authorized VID / DID 发起 presentation request。
- Holder wallet 验证 verifier VID 与 represented organization 的 authority chain。
- Holder 使用本地 disclosure policy 选择对应 pairwise DID 和 credential。
- Presentation payload 使用 SD-JWT VC 或 BBS derived proof。
- Presentation message MAY 通过 TSP nested / routed mode 发送，以降低 holder 与 verifier、不同 pairwise DID 之间的元数据关联。

TSP 不能单独解决“披露什么”的问题。披露决策仍由 holder wallet、Contrix disclosure policy、VC proof profile、credential status 和 verifier request 共同决定。

## 8. Security Requirements

实现使用 TSP 时 MUST：

- 验证 remote VID，记录使用的 support system 和 trust assessment result。
- 将 TSP relationship 与 Contrix principal/service DID 显式绑定。
- 防止把 TSP channel authentication 当作 Space authorization。
- 对 metadata privacy mode 做显式声明，尤其是 public VID、nested VID、routed mode。
- 对 routed intermediary 做最小信任假设。
- 在 audit log 中记录 TSP binding、remote VID、relationship id、payload hash 和 verification result。

## 9. Conformance

支持 TSP 的实现 SHOULD 提供：

- DID/VID discovery vector。
- TSP direct message carrying Contrix payload vector。
- TSP routed/nested privacy vector。
- TSP relationship to Contrix service DID binding vector。
- negative tests: valid TSP message without Contrix capability MUST be rejected at operation layer。
