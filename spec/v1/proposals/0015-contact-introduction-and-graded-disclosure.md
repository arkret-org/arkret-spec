---
akp: AKP-0015
title: Contact introduction evidence & graded invite-outcome disclosure — 让已互授 consent 的联系人无需 locator 即可拉群,并按引入信任分档回送邀请结果
normative: false
stability: v1
updated: 2026-06-08
status: draft
created: 2026-06-08
authors:
  - chris@acroidea.com
---

# AKP-0015: Contact introduction evidence & graded invite-outcome disclosure

> **Status: draft.** 本提案在 [`contact-and-direct-conversation.md`](../zh/identity/contact-and-direct-conversation.md) 的 contact / consent / invite 基础上,补齐"联系人拉群"的引入证据与回包披露语义。在被接受并合入 normative spec 之前,实现 MUST NOT 依赖本文新增的 `consent_grant` 高信任引入路径或 `disclosed_outcome` 回包字段。

## 1. Summary

现行 contact model 把"加联系人 → 找他聊天"定义在 contact fact / consent gate / direct conversation binding 之上,但把"联系人拉进 Realm/Strand 群聊"这一步留在了较弱的引入证据模型里:已经互授 `consent_scope=invite` 的两个人,邀请仍只能退化为 `same_principal_server` 或 `explicit_address` 这类低信任 evidence,接收方据此普遍按陌生人对待。

本提案在既有 invite 引入证据与 receive policy 之上做四处收敛,均为既有 schema 上的加字段 / 加枚举值,不新增 event kind、operation、error code 或 schema id:

1. **`consent_grant` 引入证据。** 被邀请方主动签发给邀请者的 `ak.consent.grant`(scope `invite` 或 `any`)可作为高信任引入证据,信任来源与 `locator_ref` 同构。已互授 invite consent 的联系人拉群无需 locator URL。
2. **分级披露(graded disclosure)。** `invite_delivery_outcome` 在受控前提下可回送真实处理结果(`delivered` / `blocked` / `quarantined`),粒度由 `invite_receive_policy.disclosure` 按引入信任分档决定:高信任档默认可披露,低信任档默认 opaque。
3. **per-subject 拉黑。** `invite_receive_policy.blocked_subjects` 是按 peer subject DID 的黑名单,命中即 `drop` 且强制 opaque,避免黑名单经回包侧信道泄露。
4. **request 附言与 tombstone 拉黑联动。** contact request body 增加可选 `message`;contact tombstone body 增加可选 `block_peer`,把 peer 写入 holder 的 `blocked_subjects`。

## 2. Motivation

### 2.1 G1:联系人拉群退化成弱信任

现行 contact accept 会让 Alice 与 Bob 互写 consent grant(`invite` 或更广 scope)。但当 Alice 要把 Bob 拉进一个 Realm/Strand 群聊时,invite delivery 携带的引入证据只能是 `locator_ref`(需要 Bob 主动给出的 locator URL)、`shared_realm`(需要已同在某 Realm)、`same_principal_server` 或 `explicit_address`。对"已经是联系人、已互授 invite consent"的这对人,既没有现成 locator,也未必同在 Realm,于是 invite 退化为低信任档,接收方按陌生人策略处理,容易被 quarantine 或 drop。这与"他们已经显式互相授权过 invite"的事实矛盾。

### 2.2 G2:没有分级披露

`invite_delivery_outcome.status` 目前只有 `accepted` / `duplicate` / `deferred` 三个 generic 值,且 normative 要求它不得泄露 subject 是否存在、是否被 quarantine/drop。这条反枚举约束对陌生人是正确的,但对"已建立信任的来源"过于一刀切:联系人之间一次失败的邀请,邀请者得不到任何可解释反馈,产生"联系人加不进却不知为何"的 UX 黑洞。缺少的是按信任分档区分披露粒度的机制。

### 2.3 G3:没有 per-subject 拉黑

policy 已有 `blocked_principal_services`(按服务 DID 粒度),但没有按 peer subject DID 的黑名单。用户"拉黑某个具体的人"无法表达,只能粗粒度地屏蔽其整个 Principal Server,会误伤同服务的其他人。

### 2.4 G4:contact request 缺附言

contact request 没有任何随请求传达的人类可读上下文。真实社交产品里"加好友附言"是基本能力;缺少它会迫使实现把附言塞进带外通道或私有字段。

## 3. Specification

四处改动落在三个既有 schema 与三份 normative 正文上,均不新增 schema id / event kind / operation / error code。

### 3.1 D1:`consent_grant` 引入证据

`schemas/invite-delivery-request.schema.json` 的 `introduction_evidence` oneOf 在 `locator_ref_evidence` 之后新增 `consent_grant_evidence`;`schemas/invite-receive-policy.schema.json` 的 `$defs/introduction_kind` enum 在 `locator_ref` 之后新增 `consent_grant`。

```json
{
  "kind": "consent_grant",
  "consent_grant_ref": "ak:event:0190a9c2-1f3e-7a2b-9c4d-1122334455aa",
  "consent_id": "holder-consent-cell-7f3a"
}
```

- `consent_grant_ref`(必填,`event_ref`)指向被邀请方(`invite_address.subject_id`)主动签发给邀请者的 `ak.consent.grant`,scope MUST 是 `invite` 或 `any`。
- `consent_id`(可选,string)定位 holder consent cell,加速接收方校验 active grant dot。
- 接收方验证:`consent_grant_ref` 所指 grant 在被邀请方 consent cell 中仍是 active grant dot,且 `peer == inviter`、`consent_scope ∈ {invite, any}`、未过期未撤销。通过即按高信任处理。
- 校验失败时,接收方 MUST 降级按 `explicit_address`(低信任)处理,MUST NOT 因为携带了 evidence 字段就放行。

引入信任分档(normative):高信任档 = `{locator_ref, consent_grant, shared_realm}`;低信任档 = `{same_principal_server, explicit_address, 无 / 非法 evidence}`。

### 3.2 D2:分级披露 disclosure

`schemas/invite-delivery-request.schema.json` 的 `invite_delivery_outcome` 新增可选 `disclosed_outcome` enum `[delivered, blocked, quarantined]`;`schemas/invite-receive-policy.schema.json` 新增 `$defs/disclosure_level` enum `[opaque, outcome]` 与 `$defs/disclosure_policy { high_trust, low_trust }`,并在根属性新增 `disclosure`。

```json
{
  "disclosure": {
    "high_trust": "outcome",
    "low_trust": "opaque"
  }
}
```

回包:

```json
{
  "status": "accepted",
  "disclosed_outcome": "blocked",
  "received_at": "2026-06-08T03:21:00Z"
}
```

- `opaque`:`invite_delivery_outcome` 只返回 generic `status`,MUST NOT 携带 `disclosed_outcome`,对 exists / not-exists / quarantine / drop 各情形不可区分。这是反枚举 / 反侧信道的默认。
- `outcome`:`invite_delivery_outcome` MAY 携带 `disclosed_outcome`,把真实处理结果告知邀请者。
- `disclosure` 整体省略时按默认 `high_trust=outcome / low_trust=opaque`。
- 披露档由 §3.1 引入信任分档选择:高信任档用 `disclosure.high_trust`,低信任档用 `disclosure.low_trust`。

### 3.3 D3:per-subject 拉黑 blocked_subjects

`schemas/invite-receive-policy.schema.json` 根属性新增 `blocked_subjects`(`did` 数组,`uniqueItems`)。

```json
{
  "blocked_subjects": [
    "did:webvh:example.com:alice"
  ]
}
```

- inviter 命中 `blocked_subjects` 时,delivery MUST `drop`。
- 命中者无论 `disclosure` 设置如何,披露 MUST 强制为 `opaque`,以免黑名单经回包侧信道泄露。
- `blocked_subjects` 是 subject DID 粒度,与既有 `blocked_principal_services`(服务 DID 粒度)正交并存,语义不重叠。

### 3.4 D4:request message 与 tombstone block_peer

`schemas/contact-operations.schema.json`:

- `contact_request_request_body` 新增可选 `message`(string,1..2000),携带进 `contact_requested_payload.message`,按 canonical encoding 做 NFC 归一化。
- `contact_tombstone_request_body` 新增可选 `block_peer`(boolean,default false);为 true 时额外把 peer DID 写入 holder `invite_receive_policy.blocked_subjects`,在 contact tombstone 之上叠加一次硬拉黑。

```json
{
  "target": "did:webvh:example.com:bob",
  "requested_scopes": ["direct_message", "invite"],
  "message": "Hi Bob, 我们在上周的活动认识的。"
}
```

```json
{
  "contact": "did:webvh:example.com:bob",
  "block_peer": true
}
```

## 4. Interactions with normative spec

本次改动文件清单:

- `spec/v1/artifacts/schemas/invite-delivery-request.schema.json`:`introduction_evidence` oneOf 加 `consent_grant_evidence`;新增 `$defs/consent_grant_evidence`;`invite_delivery_outcome` 加 `disclosed_outcome`。
- `spec/v1/artifacts/schemas/invite-receive-policy.schema.json`:`$defs/introduction_kind` 加 `consent_grant`;根属性加 `blocked_subjects` 与 `disclosure`;新增 `$defs/disclosure_level` 与 `$defs/disclosure_policy`。
- `spec/v1/artifacts/schemas/contact-operations.schema.json`:`contact_request_request_body` 加 `message`;`contact_tombstone_request_body` 加 `block_peer`。
- `spec/v1/zh/sync/invite-addressing.md`:§2 证据表加 `consent_grant` 高信任行、信任分档与验证规则;§5 policy 加 `blocked_subjects`;§5.1 分级披露;§7 step6/7/8;§8 `supported_introduction_kinds`。
- `spec/v1/zh/identity/contact-and-direct-conversation.md`:§4 表加 request `message` 与 tombstone `block_peer`。
- `spec/v1/zh/identity/consent-model.md`:§4 后加 `consent_grant` 引入证据交叉引用。
- `spec/v1/artifacts/reports/operation-schema-index.json`:派生 DTO 字段索引随 schema 重生成(`tools/artifact_pipeline.py generate`)。

就 D1–D4 的核心 schema 与 prose 改动本身而言,`contract-catalog.json` 及其派生 registry(event-kind / schema / id-kind / operation / capability-action)无需改动:这部分不新增 schema id / event kind / operation,且 catalog 只在 schema_id / file / description 粒度登记,不做字段级或枚举级登记。

### 4.1 后续配套改动(随本提案落地补全)

D1–D4 设计不变,以下为本轮在实现对齐过程中新增/补登的配套项,一并记录在册:

- `spec/v1/artifacts/schemas/peer-contact-delivery-request.schema.json`(新增)+ operation `ak.peer.contacts.submit`(`POST /_arkret/peer/contacts`):Principal Server 间私有 contact fact 投递面,承载 `ak.contact.requested/accepted/rejected/tombstoned` envelope;响应默认 opaque,沿用 D2 分级披露边界。新增 schema id 与 operation 已登记进 `contract-catalog.json` 及派生 registry。
- `spec/v1/artifacts/schemas/contact-operations.schema.json`:`contact_request_request_body` 加可选 `recipient_service_did`、`contact_respond_request_body` 加可选 `requester_service_did`(均为 `$ref` did),用于 closed DTO 显式携带对端投递服务 DID。
- `spec/v1/artifacts/schemas/contact-operations.schema.json`:`contact_list_row` 加 `invite_consent_grant_ref` 与 `peer_service_did`,把 D1 的 consent_grant 引入证据引用与对端投递服务 DID surface 到 holder 联系人投影。
- operation `ak.self.invite_receive_policy.get`(`GET /_arkret/self/invite-receive-policy`)与 `ak.self.invite_receive_policy.set`(`POST`):读取/替换 subject 私有 invite-receive policy(D2/D3 的 `disclosure` 与 `blocked_subjects` 即在此 policy 上配置)。两条 operation 已补登 `contract-catalog.json`、`openapi/arkret-service-api.openapi.yaml`、`bindings/non-http-bindings.yaml`、`zh/sync/service-http-binding.md` 操作字段表,并随之更新 `overview/release-readiness.md` operation 计数(123→125)。
- `ak.self.direct_conversation.resolve`:DM Realm 解析改为事件化(resolve/create 经 durable 事件而非纯投影),与 D1 accepted-contact + direct_message consent 双 gate 衔接。

## 5. Rationale & alternatives

- **为何 `consent_grant` 等同 `locator_ref` 高信任。** 二者信任来源同构:都是被邀请方主动交付给邀请者的授权材料。locator 是被邀请方给出的可达性凭证,consent grant 是被邀请方给出的、更强的 action 授权(它显式声明"允许此 peer 给我发 invite")。把 consent grant 放进低信任档,等于无视被邀请方已经做出的显式授权,反而不合理。
- **为何按引入信任分档,而不是一个全局披露开关。** 全局"开/关披露"要么对陌生人泄露 exists/not-exists(反枚举失效),要么对联系人也一律 opaque(UX 黑洞)。按引入信任分档是唯一能同时满足"对信任来源可解释、对陌生人不可区分"的粒度。`blocked_subjects` 命中强制 opaque 是这条原则的安全收口:拉黑必须对被拉黑者不可观测。
- **否决:把 `consent_grant_ref` 直接写进 durable invite 事件。** 引入证据是私有 service-to-service 材料,raw 引用不入 durable Realm 事件,与既有 `introduction_evidence_digest` 模型一致;本提案沿用该边界。
- **否决:per-subject 拉黑复用 `blocked_principal_services`。** 服务粒度会误伤同服务其他人;subject 粒度是必要的新维度。
- **否决:把 `message` 塞进既有 `idempotency_key` 或带外通道。** 附言是面向人的内容,需独立字段并参与 canonical encoding 与长度约束。

## 6. Open questions

- **OQ1 consent grant 过期与 invite gate cache 一致性。** `consent-model.md` §4.1.2 的 invite gate cache 在 grant 撤销后失效;`consent_grant` evidence 在被邀请方侧的校验需要读到最新 grant dot 状态。跨 Principal Server 的撤销传播延迟窗口内,evidence 可能短暂仍被判高信任。窗口内的 fail-closed/fail-open 选择需在 normative 合入时钉死(倾向 fail-closed 降级为低信任)。
- **OQ2 `disclosed_outcome` 与既有 `status` 的组合约束。** 是否需要 normative 约束某些 `status` 与 `disclosed_outcome` 的组合(例如 `status=duplicate` 时 `disclosed_outcome` 的允许取值),当前 schema 仅做枚举,未做组合约束。
- **OQ3 `blocked_subjects` 与 pairwise DID。** 拉黑基于 subject DID;pairwise DID 场景下同一人可能呈现多个 DID,blocked_subjects 是否需要映射回稳定 subject,与现行 contact pair key canonical encoding 的未决项耦合。
- **OQ4 是否登记 conformance vector。** 本提案未引入新 conformance vector;`consent_grant` 高信任降级、`blocked_subjects` 强制 opaque、分档披露这几条是否需要补 vector,留待 normative 合入时决定。

## 7. References

- normative:[`zh/sync/invite-addressing.md`](../zh/sync/invite-addressing.md)、[`zh/identity/contact-and-direct-conversation.md`](../zh/identity/contact-and-direct-conversation.md)、[`zh/identity/consent-model.md`](../zh/identity/consent-model.md)。
- schemas:[`invite-delivery-request.schema.json`](../artifacts/schemas/invite-delivery-request.schema.json)、[`invite-receive-policy.schema.json`](../artifacts/schemas/invite-receive-policy.schema.json)、[`contact-operations.schema.json`](../artifacts/schemas/contact-operations.schema.json)。
