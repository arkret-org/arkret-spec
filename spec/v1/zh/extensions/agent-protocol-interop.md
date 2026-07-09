---
title: Agent Protocol Interop and Upgrade
status: candidate
normative: true
stability: v1
updated: 2026-07-02
sidebar:
  label: Agent Protocol Interop
---

> **状态：extension profile（非 v1 core 互操作必需）**。本文档涉及的外部 agent 协议（A2A / ACP /
> MCP bridge 等）目前都未标准化（IBM Research 已宣布 ACP 并入 Linux Foundation 旗下的
> A2A）。Arkret v1 core 互操作 **不要求** 实现 agent-protocol upgrade；core v1 中 agent
> 仅作为 actor + capability 出现，外协议升级在标准成熟前由 `ak.profile.agent_runtime.v1`
> 单独承载，且视为可选 interop extension profile（见 `artifacts/profiles/conformance-profiles.json`
> 的 `profile_tiers.extension_profile_implementation`）。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

Arkret 原生支持 AI agent 作为 Actor 参与协作，但不应假设所有 agent 通信都必须长期停留在 Arkret Event / Realm 模型内。

当两个 agent 都支持专用 agent-to-agent 协议，例如 A2A 或 ACP endpoint，且任务适合高频、流式、长运行或跨框架直接协作时，Arkret MAY 将一次协作从 canonical 协作层升级为外部 agent protocol session。

这里的“升级”不是替代 Arkret，而是：

- Arkret 负责身份、授权、任务登记、审计、状态回流和结果归档。
- A2A / ACP / 其他 agent protocol 负责高效的实时 agent-to-agent 执行通道。

## 2. 当前外部协议状态

截至本规范撰写时：

- ACP 原由 IBM BeeAI 推动，定位为轻量 HTTP-native agent 通信协议。
- IBM Research 页面已声明 ACP 正在并入 Linux Foundation 旗下的 A2A。
- BeeAI Framework 仍提供 ACP adapter，可连接 ACP-compliant service。
- A2A 使用 AgentCard / Task / Message / Artifact 等概念，面向 agent discovery、长任务协作、streaming、async 和跨框架互操作。

因此 Arkret 不应硬编码“ACP-only”路径。实现 MUST 使用 protocol adapter registry，并允许 A2A、ACP、MCP bridge、私有企业 agent protocol 并存。

## 3. 什么时候留在 Arkret

以下场景 SHOULD 留在 Arkret 原生协议：

- 需要强审计和长期可验证协作历史。
- 需要 Realm membership / capability / policy 逐事件判定。
- 需要 Strand / Morph / Relation / View 与人类 UI 紧密联动。
- 任务结果需要被人类审阅、批准、撤回或归档。
- 对端 agent 不可信、不可发现或没有受支持协议。
- E2EE / 合规 / Policy Server 要求所有步骤进入 Realm 账本。

Arkret 原生模式更适合作为“协作事实层”和“治理层”。

## 4. 什么时候升级到外部 Agent Protocol

以下场景 MAY 升级到 A2A / ACP / 其他 agent protocol：

- 两个 agent 需要高频 token streaming 或事件 streaming。
- 任务是长运行、分阶段、可暂停/恢复的 agent task。
- 对端 agent 已经以 A2A AgentCard 或 ACP metadata 暴露能力。
- 任务执行过程主要是 agent 内部推理、工具调用或跨框架编排，只有最终状态需要回写 Arkret。
- 多 agent 团队跨 LangChain、AutoGen、CrewAI、BeeAI、ADK 等框架协作。
- 需要临时直连或服务到服务通道，避免把每个 token / tool step 写成 durable Event。

升级 MUST 是显式、可授权、可审计的行为，不得由客户端静默发生。

## 5. 协议对象

### 5.1 Agent Endpoint

Agent 可在 profile 或 DID service endpoint 中声明外部协议能力：

```json
{
  "kind": "ak.agent.endpoint",
  "agent_id": "did:webvh:z7JFwDcjH8CMYDmNUkUBhGpNN:agent.example.com",
  "endpoints": [
    {
      "protocol": "a2a",
      "version": "1.x",
      "agent_card_url": "https://agent.example/.well-known/agent-card.json",
      "transport": ["https", "sse"],
      "auth": ["oauth2", "did-http-signature"],
      "content_types": ["text/plain", "application/json", "application/octet-stream"]
    },
    {
      "protocol": "acp",
      "version": "0.x",
      "metadata_url": "https://agent.example/info",
      "transport": ["https", "sse"],
      "auth": ["bearer", "did-http-signature"]
    }
  ]
}
```

`ak.agent.endpoint` 的机读 schema 真源为 [`schemas/event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 中 `$defs/agent_endpoint_payload`（`agent.schema.json` 仅描述 agent session metadata snapshot，不含本 endpoint payload 字段）。

> **`version` 语义(normative)**:endpoint 的 `version` 是 **human-readable hint**,仅供展示与粗粒度兼容判断;`1.x` / `0.x` 通配形式不是有效 semver 也不是 draft id,**MUST NOT** 用于精确 pinning 或版本协商。精确兼容与重放防护以 §5.2 / §5.5 的 `endpoint_digest`(= DID Document canonical hash + service endpoint digest 等 epoch 证据，见 §5.5)为唯一权威 pin;实现 SHOULD 在可行时同时给出精确版本 / 范围，但 reducer 与 session pinning MUST 以 `endpoint_digest` 为准，而非 `version` 字符串。

### 5.2 Protocol Session

升级会话由 Arkret 事件登记：

```json
{
  "kind": "ak.agent.interop_session.start",
  "realm_id": "ak:realm:...",
  "actor_id": "did:webvh:zJ9BR1Wso7TdHzifQDHtN8HTd:requesting-agent.example.com",
  "payload": {
    "session_id": "ak:agent_interop_session:019643c0-0000-7000-8000-000000000000",
    "task_strand_id": "ak:strand:4accc010-0000-7000-8000-000000000000",
    "counterparty_agent": "did:webvh:zB54CCsfUsS7ywusJTQVGBWVd:remote-agent.example.com",
    "protocol": "a2a",
    "external_protocol_version": "1.x",
    "endpoint_ref": "https://agent.example/.well-known/agent-card.json",
    "capability_grant": "ak:grant:...",
    "allowed_artifact_types": [
      "text",
      "file",
      "json"
    ],
    "max_duration_seconds": 3600,
    "audit_mode": "summary_and_artifacts"
  }
}
```

`ak.agent.interop_session.start` 事件的提交 MUST 通过常规的 Realm 授权（capability action `ak.agent.interop_session.start`）与 policy 校验。

**Native agent counterparty 参与门(normative)**：当 `counterparty_agent`(或本地登记执行 agent)解析为本部署 native personal agent，且 start 发起者 ≠ 该 agent 的 controller 时，reducer MUST 套用 [`../models/strand-and-message.md` §9.4.5](../models/strand-and-message.md) 的第三方参与判定:仅当该 agent 对发起方的 effective `accept_third_party_mention`(effective ceiling ∩ controller selection)为 true 时才接受 session start;否则 MUST 拒绝，reason=`agent_participation_denied`。这把第三方 mention 投递 gate 的 controller 意愿语义从 mention fanout 扩展到 interop_session counterparty 选择，避免 `accept_third_party_mention=false` 的 native agent 被第三方经 interop 路径拉入协作。对端为外部(非本部署)agent 时本门不适用，仍以 endpoint policy + DID epoch pin 为准。

Session start MUST pin counterparty DID epoch，规则见 [§5.5 DID Epoch Pinning (normative)](#55-did-epoch-pinning-normative)。

Endpoint 退役也是协议状态，不只是外部连接关闭。Agent owner、Realm admin 或持有等价 endpoint-management capability 的 actor 撤销 / 替换 endpoint 时，MUST 通过新的 `ak.agent.endpoint` 状态或等价 profile-declared endpoint record 把旧 `endpoint_digest`（定义见 [§5.5](#55-did-epoch-pinning-normative)）标记为 retired / revoked；reducer 随后 MUST 拒绝以该 digest 发起的新 `ak.agent.interop_session.start`，并把仍引用该 digest 的 active session 转为 `blocked` 或 `cancelled`，`reason_code=agent_endpoint_retired`。实现不得在旧 endpoint 仍能响应 HTTP 的情况下继续建立新 session，也不得自动把 session 迁移到新 endpoint；迁移必须重新 start 并重新 pin DID epoch（见 §5.5）。

### 5.3 Status 回流

外部协议执行过程中的状态 MUST 回流为 Arkret event：

```json
{
  "kind": "ak.agent.interop_session.status",
  "realm_id": "ak:realm:...",
  "payload": {
    "session_id": "ak:agent_interop_session:019643c0-0000-7000-8000-000000000000",
    "external_task_id": "a2a-task-123",
    "status": "working",
    "progress_basis_points": 4200,
    "last_update_at": "2026-04-26T00:00:00Z",
    "summary": "Remote agent is generating implementation plan."
  }
}
```

`progress_basis_points` 是可选的整数进度提示，取值域为 `0..10000` basis points（即 0% 到 100.00%，每 1 basis point = 0.01%）。它只表达外部任务的近似进度，不具授权或 canonical 状态语义；reducer MUST NOT 依据 `progress_basis_points` 改变 canonical task 状态（canonical 状态只由 `status` 与 `result` 决定）。超出 `0..10000` 的值 MUST 导致整个 status 被拒绝，reason=`agent_protocol_malformed_response`（固定单一行为，确保跨实现确定性；实现 MUST NOT 改为 clamp 后接受）。

标准状态：

- `negotiating`
- `accepted`
- `working`
- `input_required`
- `blocked`
- `completed`
- `failed`
- `cancelled`
- `expired`

合法状态转移（normative）：

| 当前状态 | 合法后继 | 终态 |
| --- | --- | --- |
| `negotiating` | `accepted` / `blocked` / `failed` / `cancelled` / `expired` | no |
| `accepted` | `working` / `input_required` / `blocked` / `completed` / `failed` / `cancelled` / `expired` | no |
| `working` | `input_required` / `blocked` / `completed` / `failed` / `cancelled` / `expired` | no |
| `input_required` | `working` / `blocked` / `failed` / `cancelled` / `expired` | no |
| `blocked` | `working` / `input_required` / `failed` / `cancelled` / `expired` | no |
| `completed` | 无 | yes |
| `failed` | 无 | yes |
| `cancelled` | 无 | yes |
| `expired` | 无 | yes |

`ak.agent.interop_session.start` 被 accepted 后，同一 `session_id` 的 canonical 初始状态固定为 `negotiating`。第一条 `ak.agent.interop_session.status` 或 `ak.agent.interop_session.result` 必须是上表中 `negotiating` 的合法后继；若第一条 result 写入终态，其 `status` 也必须是 `negotiating` 的合法终态后继。**禁跳步（normative，消歧）**：`negotiating` 的合法后继**不含** `working` / `completed`，因此正常完成路径 MUST 经 `negotiating → accepted → working → completed` 逐态推进；reducer MUST 拒绝从 `negotiating` 直达 `working` / `completed` 的事件（`agent_protocol_malformed_response`）。§5.4 result 示例与 §6 时序图为简洁省略了中间态，**不**表示允许跳步。

Reducer MUST 对同一 `session_id` 的 accepted `ak.agent.interop_session.status` / `.result` 事件按 Seal application order 回放；同一 Seal 内无法由因果关系区分的候选 MUST 按 [`encoding.md` §4.2](../conformance/encoding.md) 的并发候选最终 tie-break 规则处理，即使用 canonical Event bytes 计算出的 `event_digest`，选择 bytewise greatest digest 作为该排序位置的 canonical candidate。`created_at` 与 `event_id` MUST NOT 作为最终 tie-break 或 winner selection 输入。每个候选状态 MUST 符合上表；从终态转出、跳过合法后继或对同一终态写入冲突 result 的事件 MUST fail closed，reason=`agent_protocol_malformed_response`。`ak.agent.interop_session.result` 是终态写入；当同一 canonical candidate 同时表达 status 与 result 语义时，result 的 `status` 作为 canonical terminal status。

**提交者-session 绑定(normative)**：`ak.agent.interop_session.status` / `.result` 事件的提交 actor MUST 等于该 `session_id` 对应 `ak.agent.interop_session.start` 事件的提交 actor，或持有显式绑定该 `session_id` 的 session-scoped 委托(capability constraint 携带 `allowed_session_ids` 且命中本 `session_id`)。`ak.agent.interop_session.cancel` 是 capability action，不是 durable Event kind；取消必须通过 `.status` 或 `.result` 落地为 `status="cancelled"`。reducer MUST 拒绝不满足该绑定的回流事件，reason=`interop_session_writer_unauthorized`。由于 v1 resource selector 不提供 session 维度,Realm 级 `ak.agent.interop_session.stream_status` / `cancel` capability 本身不足以授权对任意 `session_id` 写回；该绑定校验是防止持 Realm 级能力的成员伪造他人会话终态/结果的唯一闸门。

**超时自动终态(normative)**：`ak.agent.interop_session.start` accepted 的 `created_at` 是 `max_duration_seconds` 的计时锚。当前状态仍为非终态且 `now >= start.created_at + max_duration_seconds` 时，reducer / 受托 session service MUST 物化 `status="expired"` 终态；该自动写入豁免上段提交者-session 绑定，但 MUST 绑定原 `session_id`、`start_event_id`、`expired_at`、`reason_code="timeout"` 与触发它的 service / reducer identity。若迟到的 `.status` / `.result` 与自动 `expired` 并发，按 §5.3 的 canonical candidate 规则选择同一排序位置的唯一候选；一旦 `expired` 成为 canonical 终态，后续非 recovery 写入 MUST fail closed，reason=`agent_protocol_malformed_response`。实现 MAY 以后台扫描、读时 materialization 或 Seal/reducer hook 执行该自动转换，但对相同 accepted history 的投影结果 MUST 等价。

Cancellation 是协议状态，不是只关本地 socket。持有 `ak.agent.interop_session.cancel` capability 的 actor 或授权管理员取消会话时，MUST 通过 `ak.agent.interop_session.status{status="cancelled"}` 或终态 `ak.agent.interop_session.result{status="cancelled"}` 写入同一 `session_id`；payload MUST 携带 `cancelled_by`、`cancelled_at`、`reason_code`、`external_cancel_ref?` 和 `cleanup_required[]`。外部协议若无法确认 cancel，session MUST 先进入 `blocked`，直到 result 标记 `cancelled` / `failed` / `expired`。

`status="cancelled"` 完整示例(MUST 字段齐全):

```json
{
  "kind": "ak.agent.interop_session.status",
  "realm_id": "ak:realm:...",
  "payload": {
    "session_id": "ak:agent_interop_session:019643c0-0000-7000-8000-000000000000",
    "external_task_id": "a2a-task-123",
    "status": "cancelled",
    "cancelled_by": "did:webvh:zJ9BR1Wso7TdHzifQDHtN8HTd:requesting-agent.example.com",
    "cancelled_at": "2026-04-26T00:05:00Z",
    "reason_code": "user_cancelled",
    "external_cancel_ref": "a2a-cancel-789",
    "cleanup_required": [
      "remote_task_handle",
      "external_transcript"
    ],
    "last_update_at": "2026-04-26T00:05:00Z"
  }
}
```

`cancelled_by`(取消发起 actor DID)、`cancelled_at`(timestamp)、`reason_code`(取消原因码)与 `cleanup_required[]`(待清理外部 artifact 标识列表)在 `status="cancelled"` / `result{status="cancelled"}` 下 MUST 提供;`external_cancel_ref` 在外部协议返回 cancel 确认 id 时 MUST 携带，否则 MAY 省略。这些字段属 `ak.agent.interop_session.status` / `.result` 的 payload。其机读 schema 真源为 [`schemas/event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) 中 `$defs/agent_interop_session_status_payload`（`.status` 事件）与 `$defs/agent_interop_session_result_payload`（`.result` 事件）(`agent.schema.json` 仅描述 agent session metadata snapshot,不含这些 wire payload 字段)。

### 5.4 Result 回流

最终结果 MUST 回写 Arkret：

```json
{
  "kind": "ak.agent.interop_session.result",
  "realm_id": "ak:realm:...",
  "payload": {
    "session_id": "ak:agent_interop_session:019643c0-0000-7000-8000-000000000000",
    "status": "completed",
    "result_objects": [
      {
        "object_type": "strand",
        "object_ref": "ak:strand:4accc010-0000-7000-8000-000000000000",
        "track": "synthesis",
        "role": "primary_result"
      }
    ],
    "artifacts": [
      {
        "artifact_type": "text",
        "object_ref": "ak:morph:0ecec3a6-8180-7000-8000-000000000000",
        "artifact_digest": "sha256:..."
      }
    ],
    "external_transcript_digest": "sha256:...",
    "artifact_retention": "retain_by_policy",
    "external_artifact_stub": {
      "artifact_digest": "sha256:...",
      "remote_id_digest": "sha256:...",
      "retention_reason": "realm_policy",
      "cleanup_retry_policy": "not_applicable"
    },
    "completed_at": "2026-04-26T00:10:00Z"
  }
}
```

`ak.agent.interop_session.result` 的 payload MUST 至少包含 `result_objects`、`artifacts` 或失败信息之一。`result_objects` 用于声明协议层可引用的持久化成果；v1 标准对象类型为 `strand`、`message`、`morph` 和 `blob` 引用。

**结果对象 Realm 绑定（normative）**：`result_objects[].object_ref`、`artifacts[].object_ref` 以及任何 profile-defined Arkret object reference MUST 解析到与本 `ak.agent.interop_session.result.realm_id` 相同的 Realm，且 MUST 属于该 session start 时声明的任务 / artifact 允许范围。Reducer 在 accept result 前 MUST 对每个引用执行同 Realm 归属校验、对象可见性校验和 capability / egress policy 校验；跨 Realm 对象不得作为本 Realm session 的直接 `result_objects` 回流。需要记录外部系统或其它 Realm 的输出时，必须使用 `external_artifact_stub`、digest、Relation/reference 事件或显式 profile 注册的跨 Realm 引用机制，并分别通过对应 Realm 的授权路径。

外部 artifact 清理职责：若 start / status / result 暴露了外部 transcript、临时文件、tool output 或 remote task handle，result 终态 MUST 明确 `artifact_retention`（`retain_by_policy` / `delete_requested` / `deleted` / `unknown`）以及 `artifact_digest` / deletion receipt。`cancelled`、`failed`、`expired` 终态若未能删除外部 artifact，必须保留最小 `external_artifact_stub`（`artifact_digest`、`remote_id_digest`、retention reason、cleanup retry policy），不得把未验证的外部删除当成已完成。

Agent 产出的长期工作载体 SHOULD 优先落到 Strand：例如通过 Realm schema/profile、`metadata.fields.workflow_type`、Relation 或 labels 标记执行、决策、方案或研究类 Strand。需要聊天沉淀时，结果 MAY 同时附带 discussion Message 引用；二进制、代码包、长报告或外部 transcript 则 SHOULD 存为 Morph / Blob / Artifact，并在 result event 中引用 hash。

### 5.5 DID Epoch Pinning (normative)

本小节集中定义外部 agent DID 的 epoch pinning 规则。§5.2、§5.3、§5.4、§6 中所有提及 "pin DID epoch" / "DID epoch mismatch" 的位置均引用本小节，不再各自重复定义。

`ak.agent.interop_session.start` MUST pin counterparty DID epoch。payload 或 `refs[]` evidence MUST 记录：

- counterparty DID Document canonical hash；
- method-specific version / log entry id（若 DID method 支持版本化）；
- matched service entry id；
- service endpoint digest（本小节单点定义 `endpoint_digest ≝ service endpoint digest`；§5.2 等其它位置的 `endpoint_digest` 均指此处定义）；
- verification method。

reducer normative：

- 外部协议握手时 MUST 携带并签名同一组 pin digest。
- `ak.agent.interop_session.status` / `result` 回流时 reducer MUST 校验这些 pin 仍与 session start 一致。
- 若外部 DID 在会话期间轮换到不同 service endpoint 或 verification method，现有 session MUST 进入 `blocked` 或 `cancelled`，reason `session_pinned_did_epoch_mismatch`，MUST NOT 静默迁移到新 endpoint；迁移必须重新 start 并重新 pin。

> 对无版本化 DID method（如部分 `did:web` 部署），canonical hash + service endpoint digest 即构成该 method 可用的 epoch 证据；reducer MUST 以 fetch-time digest 不匹配作为 mismatch，不得因为 method 不提供显式版本号而跳过校验。

## 6. 协商流程

下图把一次升级到外部 agent protocol 的握手画成时序图。**Arkret 始终持有身份 / capability / 任务登记 / 审计**，外部协议只承担高频实时执行通道。

```mermaid
sequenceDiagram
    autonumber
    participant LocalAg as Local Agent
    participant Cx as Arkret Realm<br>(capability + Seal)
    participant Pol as Policy Server
    participant Remote as Remote Agent<br>(A2A / ACP endpoint)

    LocalAg->>Cx: 创建或选择任务 Strand
    LocalAg->>Cx: 检查 ak.agent.interop_session.start capability
    Cx->>Pol: endpoint validation<br>(目标 DID Document service binding<br> + TLS / HTTP Sig pinning)
    Pol-->>Cx: 通过 / 拒绝 (拒绝则中止)
    LocalAg->>Cx: ak.agent.interop_session.start<br>(session_id / counterparty / protocol /<br> capability_grant / allowed_artifact_types /<br> max_duration_seconds / audit_mode)
    note over Cx: sealed 后 session 生效

    LocalAg->>Remote: 通过外部协议建立 session
    Remote-->>LocalAg: streaming status / tool call / artifact (高频)
    LocalAg->>Cx: 节流回写 ak.agent.interop_session.status<br>(working / input_required / blocked / ...)

    Remote-->>LocalAg: 终态 (completed / failed / cancelled)
    LocalAg->>Cx: ak.agent.interop_session.result<br>(result_objects / artifacts /<br> external_transcript_digest)
    note over Cx: reducer 更新 Strand / Morph / Relation<br>外部状态在 result 被 accepted 前不改变 canonical task
```

读图要点：

- 步骤 3-4 的 endpoint validation 是 normative 校验（规范 MUST 条款单点定义于下方编号步骤 4，本概览不重复其 normative 文本）：把 endpoint URL 与目标 agent DID Document 的 `service` entry 完全匹配，并校验 TLS / HTTP Message Signature 与 verificationMethod 绑定。
- 节流回写 `status` 不要求每个 token 都进 durable Event；具体频率由 `audit_mode` 决定（`status_only` / `summary_and_artifacts` / `full_transcript_digest` / `full_transcript`）。
- Arkret 不信任外部 task status：只有 `ak.agent.interop_session.result` event 被 reducer accept 后才改变 canonical task 状态。


1. Requesting agent 查询目标 agent profile、DID service endpoint、A2A AgentCard 或 ACP metadata。
2. Requesting agent 在 Arkret 中创建或选择任务 Strand，或选择可承载任务语义的 Morph。
3. Requesting agent 检查自己是否拥有 `ak.agent.interop_session.start` capability。
4. **Endpoint validation（normative MUST）**：Policy Server MUST 验证目标 endpoint 与目标 agent DID 的 service binding 一致性，至少完成以下检查（任一失败 MUST 拒绝 session start）：
   - 解析目标 agent DID Document，确认其 `service` entry 的 `serviceEndpoint` URL 与 session start 中声明的 endpoint **完全匹配**（包括 scheme / host / port / 路径前缀）。
   - 验证目标 endpoint 的 TLS 证书 / mutual TLS / HTTP Message Signature 与 DID Document 中声明的 verificationMethod 绑定（与 [`../sync/federation.md` §3.1-§3.2](../sync/federation.md) destination host pinning 同等强度）。
   - 按 [§5.5 DID Epoch Pinning (normative)](#55-did-epoch-pinning-normative) 把 DID epoch pin（canonical document hash、method-specific version / log entry id（若 method 支持）、matched service entry id、service endpoint digest、verification method）写入 session start 的 audit binding 或 policy decision evidence，并在外部协议握手与 `status` / `result` 回流时按 §5.5 校验。
   - **`allowed_endpoints` 只作 constraint 预筛，不替代精确匹配**：capability constraint 中的 `allowed_endpoints` 通配（如 `https://*.trusted.example`）只用于在 session start 之前粗粒度收敛候选 endpoint 集合；最终 session start MUST 仍满足上文的精确 DID-service-binding 匹配（`serviceEndpoint` URL 与 DID Document 的 `service` entry **完全匹配**）。通配命中本身 MUST NOT 被当作授权通过。实现 SHOULD 警告通配子域（`*.example`）会扩大 handoff 攻击面，并 SHOULD 把 `allowed_endpoints` 限为 host suffix 精确集合或显式 host 列表，而不是开放通配。
   - **出站网络目标策略（normative，SSRF 防护）**：对解析出的 endpoint（及 redirect / Alt-Svc 后的实际目标）MUST 执行 [`../sync/api-conventions.md` §11.2](../sync/api-conventions.md) 出站网络目标策略；命中云 metadata / 内网 / 回环等禁止地址类别时 MUST 拒绝 session start。此检查覆盖本步骤的 `serviceEndpoint` 以及 §5.1 的 `agent_card_url` / `metadata_url`、§5.2 的 `endpoint_ref`；上述 URL 的 scheme MUST 限 `https`。精确 DID-service-binding 匹配只证明"是这个 agent"，不证明"网络目标合法"，二者 MUST 同时满足。
   - **Egress policy（normative 失败条件）**：当目标是外发 E2EE Realm 明文或其派生明文时，session start MUST 命中显式 egress grant 并通过数据分类（`allowed_data_classes`）校验；任一不满足 MUST 拒绝 session start，reason=`egress_policy_denied`。详见 [§8 安全边界](#8-安全边界)。
   宽松的 MAY 路径会留下漏洞窗口——恶意中间人可在不被任何节点验证的情况下劫持 A2A handoff，因此本规范统一为 MUST。
5. Requesting agent 提交 `ak.agent.interop_session.start`。
6. 双方通过选定外部协议建立 session。
7. 执行过程按节流策略回写 `status`。
8. 结果、artifact、transcript hash、错误或取消原因回写 Arkret。
9. Reducer 将 Strand、Morph、Relation 或 notification 更新为最终状态。

## 7. Capability

新增标准动作（capability actions；对应 event kind 使用 `ak.agent.interop_session.*` 前缀，与 capability action 命名空间一致）：

- `ak.agent.protocol.discover`
- `ak.agent.interop_session.start`（authorize submitting `ak.agent.interop_session.start`）
- `ak.agent.interop_session.cancel`（authorize cancellation strand that writes `ak.agent.interop_session.status{status="cancelled"}` / `result`）
- `ak.agent.interop_session.stream_status`（authorize streaming `ak.agent.interop_session.status`）
- `ak.agent.interop_session.attach_artifact`（authorize artifact attachment that strands through `ak.agent.interop_session.status` / `result`）
- `ak.agent.interop_session.read_transcript`（authorize transcript read; no event kind side-effect）

Capability constraint SHOULD 支持：

```json
{
  "allowed_protocols": ["a2a", "acp"],
  "allowed_endpoints": ["https://*.trusted.example"],
  "max_duration_seconds": 3600,
  "max_artifact_bytes": 10485760,
  "allowed_data_classes": ["public", "internal"],
  "requires_human_approval": true,
  "egress_policy": "metadata_only"
}
```

## 7.1 与 Personal Agent Runtime Session 的边界

本文档定义的是与 **外部 A2A / ACP / MCP agent protocol** 互操作的 session 模型(`ak.agent.interop_session.start/status/result`)。它与 [`../identity/key-management.md` §3.6.1](../identity/key-management.md) 定义的 **personal agent runtime authentication session**(`/_arkret/gate/account/session-grants` + `proof.proof_kind="agent_key_proof"`)是**两个不同的 session 概念**:

| 维度 | Personal agent runtime session | External agent protocol session(本文档) |
| --- | --- | --- |
| 用途 | Arkret 内部 native agent runtime 认证 Auth Server 与 Events API | 与外部 A2A / ACP / MCP endpoint 协商执行 task |
| Endpoint | `/_arkret/gate/account/session-grants` | `ak.agent.interop_session.start` Event + 外部 protocol endpoint |
| Proof | `agent_key_proof`(短期 `ak.session.grant`) | 由 `ak.agent.endpoint` policy / external protocol auth 决定 |
| 是否数据外发 | 否——session 只用于在 Arkret 内签发后续 wire write | 是——外发到 external agent network |
| Realm policy 闸口 | `ak.profile.personal_agent_provisioning.v1` / `ak.profile.agent_auth.v1` | `ak.profile.agent_runtime.v1` + `audit_mode` |

Agent runtime 拥有 `ak.profile.agent_auth.v1` session grant **不**自动授权其启动外部 agent protocol session;后者仍需独立的 `ak.agent.interop_session.start` 写入、`ak.agent.endpoint` policy 校验、以及 §8 的外发行为约束。实现 MUST 把二者作为独立 capability 与独立 audit 流处理。

## 8. 安全边界

外部 agent protocol session 是数据外发行为。实现 MUST：

- 在启动前做 capability 检查。
- 记录 endpoint、protocol、counterparty、task、grant 和数据分类。
- 外发 E2EE Realm 明文或其派生明文 / 摘要时，session start MUST 命中显式 egress grant（如 capability constraint 中的 `egress_policy` 配合具体 grant）并通过数据分类（`allowed_data_classes`）校验；任一不满足，实现 MUST 拒绝 session start，reason=`egress_policy_denied`，MUST NOT 退回到 SHOULD 形态或静默外发。
- 对敏感 Realm 默认要求 human approval。
- 对返回 artifact 做 hash、MIME、size、malware scan 和 policy check。
- 不信任外部 task status；只有 Arkret result event accepted 后才改变 canonical task 状态。
- 支持 cancellation 和 timeout。

## 9. 审计模式

`audit_mode`：

- `status_only`：只记录 start/status/result。
- `summary_and_artifacts`：记录摘要、artifact hash 和关键状态。
- `full_transcript_digest`：不保存全部明文 transcript，但保存外部 transcript 的 hash / Merkle root。
- `full_transcript`：完整回写 transcript。仅在 policy 允许且用户知情时使用。

默认 SHOULD 使用 `summary_and_artifacts`。

## 10. 与 MCP 的关系

MCP 主要是 agent 到 tool/data 的协议，不是 Arkret 的 agent-to-agent 升级目标。但外部 A2A / ACP agent 在执行内部 MAY 使用 MCP 调用工具。

Arkret 只要求最终状态、artifact、审计证明和授权边界回流，不要求记录远端 agent 内部每次 MCP tool call，除非 Realm policy 要求 full transcript 或 regulated audit。


## 11. Adapter Registry

实现 SHOULD 提供 adapter registry：

| Adapter | 用途 |
| --- | --- |
| `a2a` | 首选 agent-to-agent 外部协议。 |
| `acp` | 连接使用 ACP metadata / endpoint 的 BeeAI 或 ACP-compliant service。 |
| `mcp_bridge` | 将 Arkret task 包装为 MCP tool/resource 调用，适合 agent-to-tool。 |
| `http_custom` | 企业内部私有 agent API，需要显式 allowlist。 |

Adapter MUST 声明：

- discovery mechanism
- auth mechanism
- streaming support
- task id mapping
- message/artifact mapping
- cancellation mapping
- error mapping
- transcript hash format

## 12. 失败处理

失败 MUST 回写为 `ak.agent.interop_session.status` 或 `result`：

| 错误 | 语义 |
| --- | --- |
| `discovery_failed` | 找不到或无法验证对端 metadata / AgentCard。 |
| `protocol_not_supported` | 双方没有共同协议。 |
| `auth_failed` | 外部协议认证失败。 |
| `policy_denied` | Arkret Policy Server 或 capability constraint 拒绝。 |
| `egress_policy_denied` | 外发 E2EE Realm 明文 / 派生明文未命中显式 egress grant 或未通过数据分类校验；MUST 拒绝 session start（见 §6 步骤 4 与 §8）。 |
| `remote_rejected` | 对端 agent 拒绝任务。 |
| `timeout` | 超过最大执行时间。 |
| `cancelled` | 主体或管理员取消。 |
| `artifact_rejected` | 返回 artifact 未通过安全或 schema 检查。 |
| `agent_endpoint_retired` | pinned endpoint 已被 owner/admin 标记退役或撤销；现有 session 必须 blocked/cancelled，新 session 必须重新 pin。 |
| `agent_protocol_malformed_response` | 外部协议返回无法按声明 schema / transcript hash / artifact binding 验证的响应；必须写回 status/result，而不是静默丢弃。 |

失败不得删除 `start` event；审计链必须保留。

## 13. 设计结论

Arkret SHOULD 支持 agent protocol upgrade，但它必须是受控 handoff：

- Arkret 是 durable coordination / authorization / audit layer。
- A2A / ACP 是 optional execution transport。
- 所有外部执行的输入边界、状态、结果和审计证明必须回到 Arkret。

这样 Arkret 可以连接外部 agent 生态，同时不牺牲 DID、capability、Realm policy、E2EE 和审计模型。
