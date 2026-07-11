---
title: TSP Integration
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

> **状态：interop extension profile（非 v1 core 互操作必需）**。Arkret v1 core 默认使用
> HTTPS JWE / MLS DM 进行跨主体可信传输。Trust over IP 框架的 Trust Spanning Protocol
>（TSP）是可选的 metadata-privacy 增强 transport；v1 core 实现 **不要求** 实现本文档。
> 当 TSP 实现成熟后将以独立 interop profile 承载稳定 wire 形态。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret MAY 集成 TSP，用于跨 DID、KERI AID、`did:webs`、`did:x509`、`did:peer`、X.509/URN 等 Verifiable Identifier (VID) 体系建立可信消息关系。

TSP 在 Arkret 中是可选 transport / trust binding，不是 Realm 状态、capability、reducer 或 MLS 的替代品。

## 2. TSP 适用位置

TSP 适合用于：

- identity registry / witness / replica 之间的可信消息交换。
- DID / VID support system 之间的验证和信任评估。
- 跨组织 service DID 的 federation bootstrap。
- Applet、Policy Server、media service、agent runtime 的服务间认证通道。
- pairwise / private DID 场景下的低关联消息路由。
- 3PID 邀请、VC presentation、handle claim 等身份相关控制消息。
- agent protocol handoff 前的对端 VID 验证和信任建立。
- holder 向特定 verifier / 组织定向发送选择性披露 presentation。

TSP 不适合直接承担：

- Realm 多成员群组 E2EE 状态机。
- MLS epoch / group membership 变更。
- Object / Morph / Relation / Event reducer。
- capability 授权本身。
- 高吞吐媒体 RTP 转发。

## 3. 与 Arkret 身份模型的映射

TSP 的 VID 可映射到 Arkret：

| TSP | Arkret |
| --- | --- |
| VID | principal DID / service DID / pairwise DID / 受支持的外部 identifier |
| TSP Endpoint | actor 设备、service 节点、Applet、Policy Server、agent runtime |
| TSP Relationship | 两个 principal / service 之间的 pairwise 可信通道 |
| TSP Support System | identity registry、DID method adapter、witness、governance registry |
| TSP Intermediary | Sync Service、privacy router、store-and-forward 服务 |
| TSP Message | 承载 Arkret operation 或控制 payload 的已签名 / 加密 transport envelope |

Arkret DID method adapter SHOULD 暴露某个 principal 或服务是否支持 TSP。

## 4. TSP Binding Discovery

服务可在 DID Document 或 normalized principal view 中声明：

```json
{
  "type": "ak.service.tsp",
  "id": "did:webvh:z5CVGhWHEfRe1HhKLRueCrxfD:server.example#tsp",
  "serviceEndpoint": "https://server.example/tsp",
  "supported_vid_schemes": ["did", "urn"],
  "supported_modes": ["direct", "routed", "nested"],
  "supported_payloads": [
    "ak.self.events.command.submit",
    "ak.self.events.query.scan",
    "ak.identity.presentation_request",
    "ak.identity.presentation_response"
  ],
  "metadata_privacy": {
    "nested_messages": true,
    "routed_messages": true
  }
}
```

在可用时，feature discovery SHOULD 把 `tsp` 列为支持的 transport binding。

### 4.1 Endpoint 反向绑定校验（normative）

DID Document 或 normalized principal view 中出现 `ak.service.tsp` 只是一侧声明。Verifier 在把该 endpoint 作为可信 TSP 通道前，MUST 完成反向绑定校验，二选一：

1. 调用 TSP endpoint 的等价 `/.well-known`、`/holder?did=<holder_did>` 或 profile 声明的 discovery API，取得由 endpoint service key 签名的声明，确认该 endpoint 确实服务该 holder / service DID、支持相同 VID scheme 与 payload set。
2. 通过 OOBI / trust registry / support system 取得同一 endpoint 与 holder DID 的双向 binding proof，并验证 proof digest 与 DID Document service entry 一致。

仅有 DID Document 单向声明不足以授权高风险 service-to-service 操作。反向绑定失败时，TSP transport MUST fail closed；实现 MAY 回退到 v1 core HTTP Message Signature / MLS DM 路径。

### 4.1.1 高风险 protocol surface 清单（normative）

下列 protocol surface 在通过 TSP transport 触发时 MUST 在 transport 层完成 §4.1 反向绑定校验，校验失败 MUST fail closed，不得回退到任何不带反向绑定的传输路径承载该次调用。本节故意把 surface 分成三类；实现不得把 Event kind 或 capability action 误登记为 operation id。

**Operation id**（取自 `operation-registry.json`）：

- 跨 `trust_domain` 的 `ak.self.events.command.submit`
- `ak.root.identity.command.submit_did_operation`

**Durable Event kind carried inside `ak.self.events.command.submit`**：

- `ak.cross_signing.publish`
- `ak.cross_signing.reset`
- `ak.device.authorize`
- `ak.device.revoke`
- `ak.session.grant`
- 跨 `trust_domain` 的 `ak.member.state`
- 跨 `trust_domain` 的 `ak.invite.create`

**Capability action**：

- 所有在 [`artifacts/registry/capability-action-registry.json`](../../artifacts/registry/capability-action-registry.json) 中标记 `risk_tier=high` 的 capability action 通过 TSP 远程触发时。

实现 MAY 通过引用 capability action registry 的 `risk_tier=high` 子集自动扩展第三类清单；新增的 `risk_tier=high` action 默认进入该清单，不需要在本节单独再列。本节列出的 operation/event kind 与 registry 子集冲突时，本节为准（registry 是 capability action 的 superset，不是 operation registry 的替代品）。

## 5. Arkret over TSP

Arkret operation 可作为 TSP application payload：

```json
{
  "operation": "ak.self.events.command.submit",
  "content_type": "application/arkret+json",
  "realm_id": "ak:realm:...",
  "payload_digest": "sha256:...",
  "payload": {}
}
```

示例中的 `operation` 字段 MUST 取自 [`artifacts/registry/operation-registry.json`](../../artifacts/registry/operation-registry.json)；
TSP transport 不引入平行 operation namespace。若 TSP adapter 需要 transport-private 控制消息（例如握手 / heartbeat），SHOULD 用 `tsp.adapter.*` 命名空间并显式声明为 TSP-private，不得进入 Arkret operation registry 或 conformance claim。

规则：

- TSP authenticity 不替代 Arkret event signature / operation proof。任何通过 TSP 承载的 Arkret operation（包括非持久 operation、控制消息、Event 提交、capability 驱动动作）在进入 Arkret operation layer 前，receiver MUST 验证对应的 Arkret 签名、payload proof 或 capability-bound proof；仅凭 TSP relationship / channel authentication MUST NOT 放行。没有 Arkret operation 语义的 TSP-private 控制消息必须留在 `tsp.adapter.*` namespace，不得伪装成 Arkret operation。
- TSP confidentiality 不替代 Realm E2EE；它只保护 transport message payload。
- TSP relationship 不自动授予 Realm membership 或 capability。
- TSP routed mode 中 intermediary MUST NOT 被视为可信授权方，也 MUST NOT 获得、记录或向下游暴露内层 VID、内层 relationship id 或可逆的外层 VID → 内层 VID 映射；实现 MUST 对长度使用协商的 padding bucket，并对可合并投递使用批处理，避免把精确大小与时序作为稳定关联键。
- 若使用 nested TSP message 隐藏内层 VID，外层 endpoint 仍必须满足 Arkret routing 和 policy 要求。发送方在发送前 MUST 验证 endpoint 的反向绑定声明同时包含 `metadata_privacy.nested_messages=true`；routed mode 还 MUST 验证 `metadata_privacy.routed_messages=true`。声明缺失、过期或与实际握手能力不一致时 MUST fail closed，不得把隐私模式静默降级为 direct/public VID。

## 6. 与 MLS 的差异

| 维度 | TSP | MLS |
| --- | --- | --- |
| 核心目标 | 跨 VID 端点的可信消息交换 | 群组端到端加密和成员状态演进 |
| 通信形态 | 方向性异步 message，可 direct 或 routed | group session，有 epoch、commit、proposal、welcome |
| 身份模型 | VID 抽象，支持 DID/URN/X.509 等 | 依赖外部 credential 绑定成员 identity |
| 加密对象 | 单条 message payload，可选 confidentiality | 群组消息和 epoch secret |
| 元数据隐私 | nested message、routed message 等机制 | 主要保护内容；成员/epoch/发送关系需要额外设计 |
| 成员管理 | TSP relationship table，不是群组 membership | 明确 Add/Update/Remove、epoch 变更 |
| 适合场景 | 服务间、跨身份体系、pairwise 控制消息 | Realm/会议/群聊的多成员 E2EE |
| 是否替代对方 | 不替代 MLS | 不替代 TSP 的跨 VID trust binding |

## 7. 推荐组合

Arkret SHOULD 采用以下组合：

- Pairwise 服务 / 身份控制消息：MAY 使用 TSP。
- Federation bootstrap：MAY 使用 TSP 验证 service VID 并建立安全通道。
- Realm 持久事件：MUST 仍使用 Arkret event signature / hash / reducer。
- 加密 Realm 内容：SHOULD 使用 MLS。
- Agent handoff：MAY 使用 TSP 认证 endpoint，再按协商使用 A2A / ACP / 自定义 transport。
- WebRTC 媒体：MUST NOT 用 TSP 加密 RTP 媒体；按需使用 WebRTC SRTP 与 SFrame / Insertable Streams。

### 7.1 渐进披露中的 TSP

TSP 可以作为选择性披露 presentation 的私密传输层。推荐模式：

- Verifier 使用 organization-authorized VID / DID 发起 presentation request。
- Holder wallet 验证 verifier VID 与 represented organization 的 authority chain。
- Holder 使用本地 disclosure policy 选择对应 pairwise DID 和 credential。
- Presentation payload 使用 SD-JWT VC 或 BBS derived proof。
- Presentation message MAY 通过 TSP nested / routed mode 发送，以降低 holder 与 verifier、不同 pairwise DID 之间的元数据关联。

TSP 不能单独解决“披露什么”的问题。披露决策仍由 holder wallet、Arkret disclosure policy、VC proof profile、credential status 和 verifier request 共同决定。

## 8. Security Requirements

实现使用 TSP 时 MUST：

- 验证 remote VID，记录使用的 support system 和 trust assessment result。
- 将 TSP relationship 与 Arkret principal/service DID 显式绑定。
- 防止把 TSP channel authentication 当作 Realm authorization。
- 对 metadata privacy mode 做显式声明，尤其是 public VID、nested VID、routed mode。
- 对 routed intermediary 做最小信任假设：中继可见面 MUST 限于下一跳 routing handle、padding bucket、粗粒度 delivery window 和 opaque ciphertext；它 MUST NOT 看见内层 VID、Arkret actor / principal DID、operation payload、relationship id 或跨 relationship 稳定 tag。中继日志 MUST 按最短投递诊断窗口保留，且 MUST NOT 跨 relationship、租户或时间窗关联外层 routing handle。
- sender MUST 通过 §4.1 反向绑定签名验证对端 `metadata_privacy` 能力；仅有 DID Document 自声明不足以启用 nested / routed privacy mode。
- 在 audit log 中记录 TSP binding、remote VID、relationship id、payload hash 和 verification result。

## 9. Conformance

支持 TSP 的实现 SHOULD 提供：

- DID/VID discovery vector。
- TSP direct message carrying Arkret payload vector。
- TSP routed/nested privacy vector。
- TSP relationship to Arkret service DID binding vector。
- 负向测试：合法的 TSP 消息在缺少 Arkret capability 时 MUST 在 operation 层被拒绝。
