# Agent Protocol Interop and Upgrade

## 1. 目标

Contrix 原生支持 AI agent 作为 Actor 参与协作，但不应假设所有 agent 通信都必须长期停留在 Contrix Event / Space 模型内。

当两个 agent 都支持专用 agent-to-agent 协议，例如 A2A 或 ACP 兼容 endpoint，且任务适合高频、流式、长运行或跨框架直接协作时，Contrix MAY 将一次协作从 canonical 协作层升级为外部 agent protocol session。

这里的“升级”不是替代 Contrix，而是：

- Contrix 负责身份、授权、任务登记、审计、状态回流和结果归档。
- A2A / ACP / 其他 agent protocol 负责高效的实时 agent-to-agent 执行通道。

## 2. 当前外部协议状态

截至本规范撰写时：

- ACP 原由 IBM BeeAI 推动，定位为轻量 HTTP-native agent 通信协议。
- IBM Research 页面已声明 ACP 正在并入 Linux Foundation 旗下的 A2A。
- BeeAI Framework 仍提供 ACP adapter，可连接 ACP-compliant service。
- A2A 使用 AgentCard / Task / Message / Artifact 等概念，面向 agent discovery、长任务协作、streaming、async 和跨框架互操作。

因此 Contrix 不应硬编码“ACP-only”路径。实现 MUST 使用 protocol adapter registry，并允许 A2A、ACP、MCP bridge、私有企业 agent protocol 并存。

## 3. 什么时候留在 Contrix

以下场景 SHOULD 留在 Contrix 原生协议：

- 需要强审计和长期可验证协作历史。
- 需要 Space membership / capability / policy 逐事件判定。
- 需要 Flow / Morph / Relation / View 与人类 UI 紧密联动。
- 任务结果需要被人类审阅、批准、撤回或归档。
- 对端 agent 不可信、不可发现或没有受支持协议。
- E2EE / 合规 / policy server 要求所有步骤进入 Space 账本。

Contrix 原生模式更适合作为“协作事实层”和“治理层”。

## 4. 什么时候升级到外部 Agent Protocol

以下场景 MAY 升级到 A2A / ACP / 其他 agent protocol：

- 两个 agent 需要高频 token streaming 或事件 streaming。
- 任务是长运行、分阶段、可暂停/恢复的 agent task。
- 对端 agent 已经以 A2A AgentCard 或 ACP metadata 暴露能力。
- 任务执行过程主要是 agent 内部推理、工具调用或跨框架编排，只有最终状态需要回写 Contrix。
- 多 agent 团队跨 LangChain、AutoGen、CrewAI、BeeAI、ADK 等框架协作。
- 需要临时直连或服务到服务通道，避免把每个 token / tool step 写成 durable Event。

升级 MUST 是显式、可授权、可审计的行为，不得由客户端静默发生。

## 5. 协议对象

### 5.1 Agent Endpoint

Agent 可在 profile 或 DID service endpoint 中声明外部协议能力：

```json
{
  "type": "cx.agent.endpoint",
  "agent_id": "did:web:agent.example.com",
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

### 5.2 Protocol Session

升级会话由 Contrix 事件登记：

```json
{
  "type": "cx.agent.protocol_session.start",
  "space_id": "cx:space:...",
  "actor_id": "did:web:requesting-agent.example.com",
  "content": {
    "session_id": "cx:agent_session:01J...",
    "task_flow_id": "cx:flow:task0100000000000000000000",
    "counterparty_agent": "did:web:remote-agent.example.com",
    "protocol": "a2a",
    "protocol_version": "1.x",
    "endpoint_ref": "https://agent.example/.well-known/agent-card.json",
    "capability_grant": "cx:grant:...",
    "allowed_artifact_types": ["text", "file", "json"],
    "max_duration_seconds": 3600,
    "audit_mode": "summary_and_artifacts"
  }
}
```

`cx.agent.protocol_session.start` MUST pass normal Space authorization and policy checks.

### 5.3 Status 回流

外部协议执行过程中的状态 MUST 回流为 Contrix event：

```json
{
  "type": "cx.agent.protocol_session.status",
  "space_id": "cx:space:...",
  "content": {
    "session_id": "cx:agent_session:01J...",
    "external_task_id": "a2a-task-123",
    "status": "working",
    "progress": 0.42,
    "last_update_at": "2026-04-26T00:00:00Z",
    "summary": "Remote agent is generating implementation plan."
  }
}
```

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

### 5.4 Result 回流

最终结果 MUST 回写 Contrix：

```json
{
  "type": "cx.agent.protocol_session.result",
  "space_id": "cx:space:...",
  "content": {
    "session_id": "cx:agent_session:01J...",
    "status": "completed",
    "result_objects": [
      {
        "object_type": "flow",
        "object_ref": "cx:flow:task0100000000000000000000",
        "branch": "synthesis",
        "role": "primary_result"
      }
    ],
    "artifacts": [
      {
        "artifact_type": "text",
        "object_ref": "cx:morph:resv1td0c00000000000000000",
        "hash": "sha256:..."
      }
    ],
    "external_transcript_hash": "sha256:...",
    "completed_at": "2026-04-26T00:10:00Z"
  }
}
```

`cx.agent.protocol_session.result` 的 `content` MUST 至少包含 `result_objects`、`artifacts` 或失败信息之一。`result_objects` 用于声明协议层可引用的持久化成果；v1 标准对象类型为 `flow`、`message`、`morph` 和 `blob` 引用。

Agent 产出的长期工作载体 SHOULD 优先落到 Flow：例如 `semantic_kind="task_cluster"` 的执行 Flow、`semantic_kind="decision"` 的决策 Flow、`semantic_kind="proposal"` 的方案 Flow 或 `semantic_kind="research"` 的分析 Flow。需要聊天沉淀时，结果 MAY 同时附带 discussion Message 引用；二进制、代码包、长报告或外部 transcript 则 SHOULD 存为 Morph / Blob / Artifact，并在 result event 中引用 hash。

## 6. 协商流程

1. Requesting agent 查询目标 agent profile、DID service endpoint、A2A AgentCard 或 ACP metadata。
2. Requesting agent 在 Contrix 中创建或选择任务 Flow，或选择可承载任务语义的 Morph。
3. Requesting agent 检查自己是否拥有 `cx.agent.protocol_session.start` capability。
4. Policy server MAY 检查目标 endpoint、数据分类、跨域、E2EE 边界和外发风险。
5. Requesting agent 提交 `cx.agent.protocol_session.start`。
6. 双方通过选定外部协议建立 session。
7. 执行过程按节流策略回写 `status`。
8. 结果、artifact、transcript hash、错误或取消原因回写 Contrix。
9. Reducer 将 Flow、Morph、Relation 或 notification 更新为最终状态。

## 7. Capability

新增标准动作：

- `cx.agent.protocol.discover`
- `cx.agent.protocol_session.start`
- `cx.agent.protocol_session.cancel`
- `cx.agent.protocol_session.stream_status`
- `cx.agent.protocol_session.attach_artifact`
- `cx.agent.protocol_session.read_transcript`

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

## 8. 安全边界

外部 agent protocol session 是数据外发行为。实现 MUST：

- 在启动前做 capability 检查。
- 记录 endpoint、protocol、counterparty、task、grant 和数据分类。
- 对 E2EE Space 默认只外发用户明确授权的明文或派生摘要。
- 对敏感 Space 默认要求 human approval。
- 对返回 artifact 做 hash、MIME、size、malware scan 和 policy check。
- 不信任外部 task status；只有 Contrix result event accepted 后才改变 canonical task 状态。
- 支持 cancellation 和 timeout。

## 9. 审计模式

`audit_mode`：

- `status_only`：只记录 start/status/result。
- `summary_and_artifacts`：记录摘要、artifact hash 和关键状态。
- `full_transcript_hash`：不保存全部明文 transcript，但保存外部 transcript 的 hash / Merkle root。
- `full_transcript`：完整回写 transcript。仅在 policy 允许且用户知情时使用。

默认 SHOULD 使用 `summary_and_artifacts`。

## 10. 与 MCP 的关系

MCP 主要是 agent 到 tool/data 的协议，不是 Contrix 的 agent-to-agent 升级目标。但外部 A2A / ACP agent 在执行内部 MAY 使用 MCP 调用工具。

Contrix 只要求最终状态、artifact、审计证明和授权边界回流，不要求记录远端 agent 内部每次 MCP tool call，除非 Space policy 要求 full transcript 或 regulated audit。

## 11. Adapter Registry

实现 SHOULD 提供 adapter registry：

| Adapter | 用途 |
| --- | --- |
| `a2a` | 首选 agent-to-agent 外部协议。 |
| `acp` | 连接使用 ACP metadata / endpoint 的 BeeAI 或 ACP-compliant service。 |
| `mcp_bridge` | 将 Contrix task 包装为 MCP tool/resource 调用，适合 agent-to-tool。 |
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

失败 MUST 回写为 `cx.agent.protocol_session.status` 或 `result`：

| 错误 | 语义 |
| --- | --- |
| `discovery_failed` | 找不到或无法验证对端 metadata / AgentCard。 |
| `protocol_not_supported` | 双方没有共同协议。 |
| `auth_failed` | 外部协议认证失败。 |
| `policy_denied` | Contrix policy server 或 capability constraint 拒绝。 |
| `remote_rejected` | 对端 agent 拒绝任务。 |
| `timeout` | 超过最大执行时间。 |
| `cancelled` | 主体或管理员取消。 |
| `artifact_rejected` | 返回 artifact 未通过安全或 schema 检查。 |

失败不得删除 `start` event；审计链必须保留。

## 13. 设计结论

Contrix SHOULD 支持 agent protocol upgrade，但它必须是受控 handoff：

- Contrix 是 durable coordination / authorization / audit layer。
- A2A / ACP 是 optional execution transport。
- 所有外部执行的输入边界、状态、结果和审计证明必须回到 Contrix。

这样 Contrix 可以连接外部 agent 生态，同时不牺牲 DID、capability、Space policy、E2EE 和审计模型。
