---
cxp: CXP-0008
title: 个人 AI Agent 创建与运行时认证
normative: false
stability: v1
updated: 2026-05-26
status: accepted
created: 2026-05-26
authors:
  - chris@acroidea.com
discussion: internal (no public URL)
merged_into:
  - spec/v1/zh/identity/key-management.md
  - spec/v1/zh/identity/account-lifecycle.md
  - spec/v1/zh/models/actor.md
  - spec/v1/zh/models/event-and-patch.md
  - spec/v1/zh/models/private-objects.md
  - spec/v1/zh/authz/capabilities.md
  - spec/v1/zh/sync/service-surface.md
  - spec/v1/zh/conformance/conformance-profiles.md
  - spec/v1/zh/conformance/conformance-vectors.md
  - spec/v1/zh/extensions/applet-integration.md
  - spec/v1/zh/extensions/agent-protocol-interop.md
---

> **Status: accepted, merged into v1 normative spec on 2026-05-26.**
>
> Normative entry points:
>
> - [`spec/v1/zh/identity/key-management.md`](../zh/identity/key-management.md) §3.6.1 — runtime pairing 与 agent session grant 规则。
> - [`spec/v1/zh/identity/account-lifecycle.md`](../zh/identity/account-lifecycle.md) §9.1 — agent pause/resume/deactivate 语义与 controller lifecycle 传播。
> - [`spec/v1/zh/models/event-and-patch.md`](../zh/models/event-and-patch.md) §2.2 / §2.4 — Event Envelope `executed_by` / `authorization_ref` / `actor_kind` projection。
> - [`spec/v1/zh/models/actor.md`](../zh/models/actor.md) §3.3 — native personal agent vs Ghost Actor 边界。
> - [`spec/v1/zh/models/private-objects.md`](../zh/models/private-objects.md) §4.1 / §4.2 — draft account-data 与隐私边界。
> - [`spec/v1/zh/authz/capabilities.md`](../zh/authz/capabilities.md) §5.4 — agent / draft capability actions。
> - [`spec/v1/zh/sync/service-surface.md`](../zh/sync/service-surface.md) §10.1 — personal agent operations。
> - [`spec/v1/zh/conformance/conformance-profiles.md`](../zh/conformance/conformance-profiles.md) §18.1–18.3。
> - [`spec/v1/zh/conformance/conformance-vectors.md`](../zh/conformance/conformance-vectors.md) §11.1–11.5。
>
> Schema / registry artifacts: `event-envelope.schema.json`、`event-payload.schema.json`、`event-kind-registry.json`、`operation-registry.json`、`capability-action-registry.json`、`account-data-type-registry.json`、`profiles/conformance-profiles.json`。CHANGELOG entry under 2026-05-26 "Personal AI Agent provisioning & sidecar threads"。
>
> Accepted 阶段所有 review-stage 决议均已闭合(见 §7.1);§7.2 当前为空。`cx.agent.pause` / `cx.agent.resume` / `cx.agent.deactivate` 三独立 event kind 已注册为 v1 形态;如果未来引入通用 `cx.principal.status.set` lifecycle event,会通过 `renames.json` migration_group 收敛,而不会回到本文件再讨论。
>
> This proposal file is retained as historical design rationale. Future updates to personal agent provisioning MUST land directly on normative files, not here.

## 1. 概要

本提案定义一条面向普通用户的、可审计的 AI Agent 创建与运行路径。

提案引入三个可选 profile:

- `cx.profile.personal_agent_provisioning.v1`: controller 创建 native agent principal、Actor Profile、accountability 绑定、初始 agent key 授权和受限 capability grant。
- `cx.profile.agent_auth.v1`: agent runtime 复用 `/auth/account/session-grants`,使用 `proof.proof_kind="agent_key_proof"` 换取短期 `cx.session.grant`,不重复走人类 coauth。
- `cx.profile.agent_delegation_policy.v1`: Realm policy 与 capability constraint 定义 agent 可读、可写、可整理、可代用户执行的范围。

非目标:本提案不取代 Applet + Ghost Actor。管理员安装的桥接服务、外部系统托管的 actor 池和 Applet 管理的虚拟身份仍应使用 Applet + Ghost Actor。本提案只处理 native personal / workspace AI agent。

非目标:本提案不定义"在某个 Flow / Message 上下文中,controller 与自己的 agent 开启私有持续对话"的 sidecar thread。该能力由 CXP-0009 单独处理。

## 2. 动机

当前 Contrix 已经有表达 AI Agent 所需的基础构件:

- Actor Profile 支持 `actor_kind="agent"`。
- `cx.identity.accountability_grant` 可表达 agent 对谁负责。
- `cx.agent.key.authorize` / rotate / revoke 可管理 agent signing key。
- `cx.capability.grant` / delegate / revoke 可授权 agent 的具体能力。
- `cx.session.grant` 可承载短期运行时访问。

但是协议尚未定义一个顺滑的端到端流程来回答以下实际问题:

1. 普通用户如何创建"我的 AI 助手",而不是手工组装 DID、Actor Profile、accountability、key authorization 和 grants?
2. 创建后用户得到哪些管理信息?哪些 bootstrap material 应该交给 AI runtime?
3. AI runtime 之后如何认证?是否必须打开人类 coauth / CAPTCHA / OTP UI?
4. 用户如何授予窄权限,例如只读、以 agent 身份回复、代表用户执行、把概要写入某个 Flow track、创建新 Flow?
5. 如何保证 agent 不自动继承用户在 Realm 内的最大权限(最小权限原则)?

目标产品体验接近 workspace UI 中的 "Create Agent"。但协议结果必须仍然是 DID-rooted、capability-scoped、auditable、short-lived、revocable。

## 3. 设计不变量

1. **人类 coauth 只属于控制面**:创建 agent、批准 key、扩权、恢复和高风险操作需要 controller 的人类认证或设备证明。Agent 日常运行不应被要求完成 CAPTCHA、OTP、SSO redirect 或 WebAuthn user presence。
2. **Agent runtime 使用 key proof 换短期 session**:runtime 持有 agent key 或 workload credential,通过 `proof_kind="agent_key_proof"` 获取短期 `cx.session.grant`。
3. **不返回长期私钥**:`cx.agent.provision` 响应 MUST NOT 包含长期 private key。默认由 runtime 本地生成 key pair,再由 controller 批准 public key。
4. **不继承 controller 最大权限**:agent effective permission 是多重约束交集,不是 controller 权限的自动拷贝。
5. **高风险操作转成人类 approval request**:需要人类批准时,服务端返回 structured approval request,而不是把 agent runtime 重定向到人类登录页面。
6. **Agent 与 Ghost Actor 边界清晰**:native personal agent 是一等 DID principal;Ghost Actor 是 Applet 管辖 namespace 下的外部/集成 actor 镜像。

## 4. 规格草案

### 4.1 角色

| 角色 | 含义 |
| --- | --- |
| Controller principal | 创建 agent 并对 agent 负责的人类、组织或团队 principal。 |
| Agent principal | 表示 AI agent 的 native DID principal,通常拥有 `actor_kind="agent"`。 |
| Agent runtime | 持有 agent private key、硬件凭据或 workload credential 并执行任务的进程或托管服务。 |
| Auth Server | 验证 agent key proof 与撤销状态后签发短期 `cx.session.grant`。 |
| Realm policy | 决定该 Realm 是否允许 personal agent、委托执行、track 写入、tool / data-class 访问。 |

### 4.2 Native personal agent

Native personal agent 由现有 Contrix primitive 组合表达:

1. Agent DID principal。
2. `actor_kind="agent"` 的 Actor Profile。
3. controller 给 agent 签发的 `cx.identity.accountability_grant`。
4. `cx.agent.key.authorize`,把一个具体 agent key 绑定到 agent DID、accountable actor、`agent_key_scope`、audience 和过期时间。
5. 一个或多个带 scope 的 `cx.capability.grant` / `cx.capability.delegate` event。
6. 可选 runtime endpoint / metadata,用于 agent discovery 或运维展示。

Agent principal 不是 Ghost Actor。它可以按 DID 与 account policy 独立被 mention、assign、grant、revoke、suspend 或 migrate。

`did:webvh` 部署 SHOULD 为 personal agent 分配独立 SCID,并 MAY 在 `did:webvh:<scid>:<host-and-path>` 的 `<host-and-path>` 部分使用 `agents/<slug>` 这类可读路径约定,例如 `did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant`。该路径只是 DID history 托管位置的可读约定,规范性硬性要求只有两条:

1. Agent DID MUST 有独立 DID document、独立 verification method 与独立 key rotation 日志;不得只是 controller DID 的虚拟子身份或路径别名。
2. `accountable_principal_ids[]` 对应的 `cx.identity.accountability_grant` MUST 由 controller 的 primary DID 显式签发,不能从 DID path 形态推导信任。

其它 DID method 的 agent DID 形态由 method-specific deployment policy 决定,但同样必须满足"独立 DID document + 显式 accountability grant"。

### 4.3 Agent 创建操作

新增 profile operation:

```text
POST /api/v1/agents
operation_id: cx.agent.provision
profile: cx.profile.personal_agent_provisioning.v1
```

该 operation 是一个编排入口,不是 durable event kind。最小形态 SHOULD 由服务写入或返回一组现有事件引用:Actor Profile、`cx.identity.accountability_grant`、pending pairing record、初始 capability grant。Provisioning 的可审计状态来自这些子事件;不得再增加一个 `cx.agent.provision` aggregate event 造成 audit 双源。

请求:

```json
{
  "controller_principal_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice",
  "display_name": "Summary Assistant",
  "description": "Reads selected Flows and posts summaries.",
  "agent_did_method": "did:webvh",
  "runtime": {
    "kind": "custom_endpoint",
    "endpoint": "https://agent.example/runtime",
    "public_key_mode": "runtime_generated"
  },
  "requested_capabilities": [
    {
      "actions": ["cx.events.subscribe"],
      "resources": [
        {
          "kind": "object",
          "object_type": "flow",
          "match_scope": "object_refs",
          "allowed_object_refs": ["cx:flow:01970000-0000-7000-8000-000000000001"]
        }
      ],
      "constraints": [
        {
          "constraint_type": "scope_limitation",
          "allowed_data_classes": ["message_content", "flow_content"]
        }
      ],
      "expires_at": "2026-06-26T00:00:00Z"
    },
    {
      "actions": ["cx.message.create"],
      "resources": [
        {
          "kind": "object",
          "object_type": "flow",
          "match_scope": "object_refs",
          "allowed_object_refs": ["cx:flow:01970000-0000-7000-8000-000000000001"]
        }
      ],
      "constraints": [
        {
          "constraint_type": "scope_limitation",
          "allowed_tracks": ["synthesis", "summary"]
        },
        {
          "constraint_type": "quota",
          "subtype": "rate",
          "max_operations": 20,
          "period": "PT1H"
        }
      ],
      "expires_at": "2026-06-26T00:00:00Z"
    }
  ],
  "approval_policy": {
    "default_for_unlisted_actions": "deny",
    "act_on_behalf": "disabled_by_default",
    "require_controller_approval_for": ["cx.flow.create", "cx.capability.delegate"]
  }
}
```

`approval_policy` 是 request-side DSL,不进入 canonical grant wire。服务端 MUST 把它展开为 §4.9 vocabulary 中的 registered constraints:

- `default_for_unlisted_actions: "deny"` → 未列入 `requested_capabilities[].actions[]` 的 action 不签发 grant(不是 wildcard `allow`)。
- `act_on_behalf: "disabled_by_default"` → 不签发任何 `executed_by = agent_principal_id` 形态的 grant,除非 caller 在 `requested_capabilities[]` 中显式声明 `act_on_behalf` mode 并满足 §4.10 的 fresh approval 要求。
- `require_controller_approval_for: [actions...]` → 对列出的每个 action,在对应 `requested_capabilities[].constraints[]` 中加入 `claim_based.approval`(`approval_required=true`, `approval_actor_refs=[<controller_principal_id>]`)与 `claim_based.accountability`(`controller_approval_required=true`)。

`approval_policy` 不引入"high risk" 这类未注册分类。如果实现需要按 risk tier 自动应用 approval,该 tier 表必须由 deployment profile 显式定义并文档化,不得依赖隐含的服务端 hardcoding。

请求字段 enum:

- `agent_did_method`: 接受 `zh/identity/identity-did.md` 注册的 DID method 列表(典型为 `did:webvh`、`did:plc`、`did:keri`)。Method 不在该列表时 fail closed。
- `runtime.kind`: v1 枚举 `{custom_endpoint, custodial}`。`custom_endpoint` = controller 提供 runtime URL 自托管;`custodial` = deployment 提供 hosted runtime,并按 §4.5 规则向 controller 披露 custodial-key 风险。未来 attestation profile 可扩展该枚举。未知值 fail closed。

`requested_capabilities` 示例使用 canonical grant shape。产品 UI / SDK MAY 接受 §4.7 表中的预设名(`read_only`、`draft_only`、`reply_as_agent`、`act_on_behalf`、`organizer`),但服务端写入的 capability grant MUST 展开为 `actions[]`、resource selectors、registered constraints 与 TTL;预设名本身不进入 canonical wire,且实现不得引入未注册的预设名(例如 `write_summary` 等任意字符串)而不在 §4.7 表中登记。

响应:

```json
{
  "agent_principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "agent_profile_event_id": "cx:event:01970000-0000-7000-8000-000000000010",
  "accountability_grant_event_id": "cx:event:01970000-0000-7000-8000-000000000011",
  "initial_capability_grant_ids": ["cx:grant:01970000-0000-7000-8000-000000000012"],
  "pairing": {
    "pairing_request_id": "01970000-0000-7000-8000-000000000020",
    "pairing_code": "R7K9-2M4P",
    "expires_at": "2026-05-26T12:00:00Z"
  },
  "status": "pending_runtime_key"
}
```

`pairing_request_id` 是 account/auth profile-local artifact ID,不是 `cx:<kind>:<uuid>` protocol object id。Accepted schema MUST 显式声明其 opaque UUIDv7 wire form、TTL 与单次消费规则;其它 durable Event 或 object 若引用 pairing approval 结果,应引用 accepted event (`*_event_id` / `authorization_ref`),而不是把 pairing request 当作可长期解析的 `_ref`。

响应 MUST NOT 包含长期 private key、refresh token 或可直接长期调用 Events API 的 bearer token。也 MUST NOT 引入 custom URI scheme(例如 `contrix://`)承载 pairing / management / approval 入口。客户端跳转链接由客户端自己用 deployment 已知的 `contrix_base_url` 拼接 HTTPS URL,例如 `https://<contrix_base_url>/auth/account/agent-pair?request=<pairing_request_id>`;移动端依赖 OS Universal Links / App Links 把 HTTPS URL 路由到原生 app。这样 spec 不背 URI scheme 注册债,联邦多实例下 host 也不会丢失。

#### 4.3.1 Provisioning `status` 枚举

`status` 字段是 provisioning operation 的 lifecycle 投影,枚举闭合为:

| 值 | 含义 | 退出条件 |
| --- | --- | --- |
| `pending_runtime_key` | agent principal 已创建,初始 grant 已签发但 `effective_after_first_authorized_key=true`(见 §4.3.2),等待 pairing 完成 | pairing 成功 → `active`;`pairing.expires_at` 到达 → `pairing_expired` |
| `active` | agent 已有 accepted `cx.agent.key.authorize`,grants 已生效,runtime 可签发 `agent_key_proof` | controller pause → `paused`;controller revoke 或 controller deactivate → `deactivated` |
| `paused` | agent identity 与历史保留,但 Auth Server 拒绝新 session grant(见 §4.11) | controller resume + 重新校验通过 → `active`;controller revoke → `deactivated` |
| `pairing_expired` | pairing 窗口过期且未完成 | controller 重新发起 pairing → 新 `pending_runtime_key`;controller 显式 revoke → `deactivated` |
| `deactivated` | agent terminal state,所有 active sessions / keys / grants / runtime bindings 已失效 | terminal,不再转换 |

该枚举与 [`zh/models/actor.md` §3.2](spec/v1/zh/models/actor.md) 的 actor profile `status` 字段对齐,但 `pending_runtime_key` 与 `pairing_expired` 是 provisioning-specific 投影,不直接出现在 actor profile 上(actor profile 在这些过渡状态下表现为 `active` 或 `suspended`,具体由 account lifecycle 文档定义)。

#### 4.3.2 Pairing 失败时的 grant 清理

`initial_capability_grant_ids` 在 `pending_runtime_key` 阶段已写入 durable storage,但此时 agent 无可用 key,grant 无法被执行。为避免遗留无法激活的孤儿 grant,实现 MUST 遵守:

- `pending_runtime_key` 阶段写入的 grant payload SHOULD 携带 `effective_after_first_authorized_key=true` 标志(profile 字段,reducer 接受为 inactive-but-durable 状态)。Auth Server / capability evaluator 在该 flag 为 true 且对应 agent principal 还没有 accepted `cx.agent.key.authorize` 时 MUST fail closed。
- pairing 完成(§4.5 写入 `cx.agent.key.authorize`)后,reducer MUST 把同 agent principal 名下所有 `effective_after_first_authorized_key=true` grant 的该 flag 清除,转入正常 effective window 评估。
- `pairing.expires_at` 到达且未完成 pairing 时,服务 MUST 自动写入 `cx.capability.revoke` 撤销 `pending_runtime_key` 阶段签发的 grant,并把 agent status 转入 `pairing_expired`。
- controller 也 MAY 在 `pending_runtime_key` 阶段显式 revoke,效果等价于上一条。

实现不得让 pending grant 永远停留在 durable storage 而无可执行路径。

### 4.4 用户与 runtime 分别拿到什么

Provisioning 完成后,controller 侧应看到管理信息:

```json
{
  "agent_principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "display_name": "Summary Assistant",
  "status": "pending_runtime_key",
  "accountable_principal_ids": ["did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice"],
  "grants": [
    {
      "grant_id": "cx:grant:01970000-0000-7000-8000-000000000012",
      "summary": "Read selected Flow and write summary track until 2026-06-26"
    }
  ]
}
```

Agent runtime 只需要 bootstrap material:

```json
{
  "contrix_base_url": "https://contrix.example",
  "service_did": "did:web:contrix.example",
  "agent_principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "pairing_request_id": "01970000-0000-7000-8000-000000000020",
  "pairing_code": "R7K9-2M4P",
  "pairing_expires_at": "2026-05-26T12:00:00Z"
}
```

Bootstrap material 是一次性、短期、可撤销的 pairing 输入。它不能被当作 session grant、capability grant 或长期 secret。

### 4.5 Runtime key pairing

推荐 bootstrap 分两阶段(第 1 步是 §4.3 provisioning 调用的延续):

1. (§4.3) controller 通过 coauth / passkey / device proof 完成 provisioning,得到 `pending_runtime_key` agent 与一次性 `pairing_request_id` / `pairing_code`。
2. (§4.5) agent runtime 在本地生成自己的 key pair。
3. runtime 把 public key 与 proof-of-possession 提交给 pairing endpoint。
4. controller 或 policy engine 批准该 key 绑定。
5. 服务写入 `cx.agent.key.authorize`。
6. runtime 在本地安全保存 private key,后续用它生成 `agent_key_proof`。

新增 account/auth profile operation:

```text
POST /auth/account/agent-key-pair
operation_id: cx.account.agent_key_pair
profile: cx.profile.personal_agent_provisioning.v1
```

请求:

```json
{
  "pairing_request_id": "01970000-0000-7000-8000-000000000020",
  "agent_principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "verification_method": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant#runtime-key-1",
  "public_key": {
    "key_type": "Ed25519",
    "public_key_multibase": "z..."
  },
  "proof_of_possession": {
    "challenge": "base64url...",
    "audience": "https://contrix.example",
    "request_canonical_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "expires_at": "2026-05-26T12:00:00Z",
    "signature": "base64url..."
  },
  "runtime_attestation": {
    "kind": "self_asserted",
    "software": "savfox-agent",
    "version": "0.1.0"
  }
}
```

规则:

- SHOULD 优先使用 runtime-generated private key。
- 除非 deployment profile 明确声明 custodial-key 语义并向用户披露风险,生产托管 agent MUST NOT 使用服务端生成的 private key。
- Pairing token MUST 短期、单次、audience-bound、request-digest-bound、可撤销。
- Pairing endpoint MUST 校验 `verification_method` 的 DID 部分(strip fragment 与 query 后)与请求体中 `agent_principal_id` bit-identical;不匹配 MUST fail closed(`reason="verification_method_principal_mismatch"`),不得自动选用任一为准。
- Pairing approval MUST 写入可审计的 `cx.agent.key.authorize` event。
- 写入的 `agent_key_scope` MUST 不宽于 controller 已批准的初始 capability 与 Realm policy。
- `approval_evidence` SHOULD 引用 pairing request 或 controller approval event。
- v1 `runtime_attestation.kind` 的最低 baseline 是 `self_asserted`。Accepted profile SHOULD 把批准后的 runtime attestation 摘要写入 `cx.agent.key.authorize` payload 或可验证 refs,使 grant validator 能执行 attestation constraint。实现遇到无法解析的 attestation kind MUST fail closed。后续 TEE / SLSA / hosted workload attestation 可以作为更高级 profile 进入同一 slot,不需要再改 agent key authorization 的主线 wire。
- **Sidecar exposure 披露(与 CXP-0009 §3 invariant 10 联动)**:在写入 `cx.agent.key.authorize` 之前的 controller approval UI 上,如果该 controller 在新 agent 将要 active 的任一 Realm 中已存在 `cx.profile.agent_sidecar_thread.v1` sidecar Circle,实现 MUST 向 controller 显式披露 "该 agent 激活后将自动获得这些 Realm 中现有 AI sidecar 私聊的访问权"(以及涉及的 Realm 列表与 sidecar 数量)。该披露是 pairing approval 的必备信息项,不能折叠进通用 capability 列表。Controller 必须能在不批准 pairing 的前提下取消该流程。

### 4.6 Agent runtime 认证

Agent runtime 在日常运行时 MUST NOT 被要求完成人类 coauth UI。CAPTCHA、OTP、WebAuthn user presence、SSO redirect 等人类因子属于 provisioning、approval、recovery 或 high-risk escalation,不属于常规后台执行。

本 profile 复用现有 account/auth session grant 入口,通过扩展 `SessionGrantRequest.proof.proof_kind` 新增 `agent_key_proof` 分支区分 agent runtime 认证:

```text
POST /auth/account/session-grants
operation_id: cx.account.issue_session_grant
profile: cx.profile.agent_auth.v1
```

该选择保留单一 session grant 签发面,便于统一 TTL、audience、revocation、soft logout、risk policy、audit 和 conformance。实现 MUST 通过 request schema、`proof_kind`、proof validator 和 response scope 明确区分 human account login 与 machine runtime authentication,不得把 agent key proof 当作 password / OIDC / passkey 登录因子处理。

请求示例:

```json
{
  "principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "requested_scope": ["cx.events.subscribe", "cx.message.create"],
  "agent_key_authorization_ref": "cx:event:01970000-0000-7000-8000-000000000021",
  "agent_scope_request": {
    "realm_ids": ["cx:realm:01970000-0000-7000-8000-000000000000"],
    "flow_ids": ["cx:flow:01970000-0000-7000-8000-000000000001"],
    "track_names": ["summary"]
  },
  "proof": {
    "proof_kind": "agent_key_proof",
    "verification_method": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant#runtime-key-1",
    "challenge": "base64url...",
    "request_canonical_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
    "audience": "https://contrix.example/api/v1",
    "expires_at": "2026-05-26T10:05:00Z",
    "signature": "base64url..."
  }
}
```

`agent_key_authorization_ref`、`agent_scope_request` 和 `proof.verification_method` 是 `cx.profile.agent_auth.v1` 对现有 `SessionGrantRequest` 的 schema overlay。`verification_method` 承载 DID URL,遵循 [`common-fields.md` §2.1.3](../zh/models/common-fields.md#213-_did)。Accepted 后应扩展 OpenAPI typed schema;在 proposal 阶段不改 artifact。

Wire 影响:本提案不新增 sibling endpoint,也不引入顶层 `grant_type` discriminator。Accepted 后需要把现有 `SessionGrantRequest.proof.proof_kind` 枚举扩展为包含 `agent_key_proof`,并为该分支定义独立 required fields、proof canonicalization 与 validator。实现不得让 `agent_key_proof` 走 password / OIDC / passkey 的 validator fallback。

`agent_scope_request` 是 `cx.profile.agent_auth.v1` overlay,不进入通用 human `SessionGrantRequest` schema。`agent_scope_request.track_names` 是请求侧窄化字段;签发后的 capability / session scope MUST 物化为现有 capability vocabulary 中的 `allowed_tracks` 等 registered constraints,不得把 `track_names` 当作新的 grant constraint。

响应示例:

```json
{
  "principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "session_grant": "opaque-short-lived-token",
  "expires_at": "2026-05-26T10:30:00Z",
  "granted_scope": ["cx.events.subscribe", "cx.message.create"],
  "scope_details": {
    "realm_ids": ["cx:realm:01970000-0000-7000-8000-000000000000"],
    "flow_ids": ["cx:flow:01970000-0000-7000-8000-000000000001"],
    "track_names": ["summary"]
  }
}
```

`scope_details` 是 profile overlay;核心 `SessionGrantResponse` 仍以 `principal_id`、`session_grant`、`expires_at` 和 `granted_scope` 为基础。

校验规则:

- key MUST 被一个 accepted、未过期、未撤销的 `cx.agent.key.authorize` 授权。
- key proof MUST 绑定 challenge、audience、request canonical digest、agent principal、`verification_method`、nonce 和 expiry。
- `request_canonical_digest` MUST 覆盖整个 session grant request 的 canonical bytes,但不包含 `proof.signature` 自身。
- Auth Server MUST 维护 challenge / nonce replay table 或等价一次性校验状态,至少覆盖 proof `expires_at` 后的 replay grace window。已使用或过期 challenge MUST 拒绝。
- requested scope MUST 不宽于 `agent_key_scope`、effective capability grants 与 policy constraints。
- accountable actor、controller principal 与 agent principal MUST 未 deactivated、未 suspended,且未被 policy 阻断。Controller 进入 `deactivated` / `suspended` 后,其 accountable agent 的 active sessions MUST 通过 account lifecycle / revocation 链失效,后续 session grant MUST fail closed。
- 签发的 session MUST short-lived、audience-bound、scope-bound、可撤销。
- Agent session grant 默认最大 TTL SHOULD 为 15 分钟。Deployment MAY 声明更短 TTL;若声明更长 TTL,必须通过 profile 暴露上限、风险理由和额外 revocation freshness 要求,且不应超过 60 分钟。
- 对 high-risk action,撤销状态 unknown 或 stale 时 MUST fail closed。
- Session grant 不授予 E2EE history key、secret storage 或长期 device 权限,除非另一个 E2EE / device profile 显式授权。

Agent 的 E2EE access MUST 作为独立 MLS member 表达,不得把 agent 伪装成 controller 的 delegated device。默认情况下 agent 没有任何 Realm / Circle history key;只有被显式加入对应 MLS group 后,才获得该 scope 的 future epoch access。Agent MLS KeyPackage SHOULD 由 active `cx.agent.key.authorize` 中的 `verification_method` 签发或绑定,使 key authorization、session proof 与 MLS membership 可审计地收敛。

当需要人类批准时,Auth Server MUST NOT 给 agent runtime 展示 CAPTCHA / OTP 页面。它 SHOULD 返回结构化错误:

```json
{
  "ok": false,
  "error": {
    "code": "claim_required",
    "reason_code": "human_approval_required",
    "approval_request_id": "01970000-0000-7000-8000-000000000099"
  }
}
```

`approval_request_id` 是 account/auth profile-local opaque artifact ID,不是 target Flow / Event / Grant 的 reference。Agent runtime 不要解释成 URL,也不要尝试打开 UI。Controller 客户端在自己的 session 中查询该 id 对应的 approval request 详情(端点由 deployment 文档定义,典型路径 `GET https://<contrix_base_url>/auth/account/approvals/<approval_request_id>`),并在人类 UI 中带外批准。本 profile 不引入 custom URI scheme 来承载 approval 跳转——理由同 §4.3 末尾。

controller 通过人类 UI 在带外批准。批准会产生新的 capability / delegation / approval event,agent retry 时引用该 event。

### 4.7 权限模式

实现 MAY 暴露产品预设,但 wire-level grant MUST 收敛为具体 action、selector、constraint 与 TTL。

| 模式 | Actor identity | 典型动作 | 主要风险 |
| --- | --- | --- | --- |
| `read_only` | agent | `cx.events.subscribe`, `cx.event.read`, object read actions | 低到中,取决于 data class |
| `draft_only` | agent -> controller-private control surface | 候选 `cx.agent.draft.propose` / `cx.agent.action_request`;由 Principal Server materialize controller-owned `cx.agent.draft.v1` account data | 发布/共享写入风险低;机密性风险取决于 read scope,可高 |
| `reply_as_agent` | agent | `cx.message.create`, `cx.reaction.add` | 中 |
| `act_on_behalf` | controller 作为 `actor_id`,agent 作为 `executed_by` | `cx.message.create`,选定 workflow actions | 高 |
| `organizer` | agent | `cx.flow.create`, `cx.flow.update`, `cx.relation.create`,受限 `cx.message.create` | 中到高 |

上述模式只用于 UI / SDK 预设。Server 接收和持久化的是 §4.9 中的 capability actions、resource selectors、constraints 与 TTL;模式名本身不进入 canonical wire。

Draft-only 只表示"agent 提出候选内容,等待 controller 批准"。它本身不是"在当前 Flow 内开一个隐形私聊"。若产品需要 controller 与 agent 围绕某个 Flow / Message 位置持续对话,见 CXP-0009 `Agent Sidecar Thread`。

本 profile 标准化 draft-only 的最小互操作面。它们必须是 private/account-data 语义,不应被命名或实现成共享 message event。候选方向:

- `cx.agent.draft.propose`
- `cx.agent.action_request`
- `cx.agent.action_approve`
- `cx.agent.action_reject`

### 4.8 Draft-only 私有存储

`draft_only` 的核心语义是:agent 可以提出候选内容,但不能把候选内容提交到目标 Realm / Flow 的共享历史。Draft MUST NOT 作为 `cx.message.create`、`cx.flow.create` 或任何目标 Realm 的 `wire_scope=durable_event` 写入。

Draft-only 至少有两类私有状态:

| 类型 | owner | 可见性 | 典型用途 |
| --- | --- | --- | --- |
| approval draft | controller principal | controller 的授权设备,以及被显式授予访问该 draft 的 agent runtime | agent 生成待用户确认的消息、摘要、Flow 创建请求。 |
| agent scratchpad | agent principal | agent runtime,以及 policy 显式允许的 controller / operator | agent 的内部计划、缓存、中间推理或工具结果。 |

Approval draft SHOULD 存在 controller 的 encrypted account data 或 controller actor-private stream 中。Agent-facing action 不应是对 controller account data 的通用 `cx.account_data.set`;更合理的 wire 是受限的 `cx.agent.draft.propose` / `cx.agent.action_request`,由 controller 的 Principal Server 在通过 capability、policy、accountability 与 risk check 后 materialize 成 controller-owned account data。

候选 account-data payload:

```json
{
  "type": "cx.agent.draft.v1",
  "draft_id": "01970000-0000-7000-8000-000000000070",
  "owner_principal_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice",
  "agent_principal_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "target": {
    "realm_id": "cx:realm:01970000-0000-7000-8000-000000000000",
    "flow_id": "cx:flow:01970000-0000-7000-8000-000000000001",
    "track_name": "summary"
  },
  "proposed_action": "cx.message.create",
  "content": {
    "body": "Draft text that is not yet visible to the Realm."
  },
  "expires_at": "2026-05-26T11:00:00Z"
}
```

Accepted 后 draft-only MUST 注册 controller-owned account-data type `cx.agent.draft.v1`。建议 key pattern 为 `cx.agent.draft.v1:<agent_principal_id>:<draft_id>`,并标注 `encrypted_at_rest=true`、payload schema、tombstone 规则和 retention policy。Agent-facing `cx.agent.draft.propose` / `cx.agent.action_request` 通过 Principal Server 的 capability、policy、accountability 与 risk check 后,才 materialize 为该 controller-owned account-data。

`draft_id` 是 `cx.agent.draft.v1` account-data artifact ID,不是 canonical Flow / Message / Event id。Accepted schema MUST 定义其 opaque UUIDv7 wire form;shared events 需要审计关联时使用 digest 或 accepted approval / publish event reference,不得把 private draft account-data key 当作 target Flow 内的 `_ref`。

隐私边界:

- Draft storage MUST 使用 `wire_scope=actor_private_event` 的通道,例如 encrypted account data 或 actor-private stream;不得进入 shared Realm Move / Anchor history。
- Target Realm 的 `cx.events.subscribe`、`cx.events.query`、shared reducer、Realm search index、notification fanout 和 push preview MUST NOT 返回 draft content。
- `cx.account.subscribe` 只能把 controller-owned approval draft 返回给 controller principal 的授权 session,以及 scope 明确包含该 draft / account-data 访问权的 agent runtime。
- 若服务端存储 draft 明文,该部署 MUST 把明文可见服务写入 profile / policy 并向 controller 披露;默认语义 SHOULD 是服务端只保存 encrypted account data。
- Draft 可以引用目标 `realm_id`、`flow_id`、`track_name`、`message_id` 或 cursor,但这些引用不授予目标 Realm 成员读取 draft 内容的权利。

发布时,controller approval 或 fresh authorization 会生成真正的 shared event,例如 `cx.message.create`。Shared event MAY 通过 `refs[].role="draft_source"` 携带 opaque digest 便于审计,但明文 draft id、private metadata、scratchpad 或历史版本 MUST NOT 泄露到共享历史。发布后的可见内容只以最终 approved payload 为准。

#### 4.8.1 Draft approval / publish lifecycle

Draft approval MUST 建模为 controller-private lifecycle,而不是对 target Flow 的 mutation。最小状态机:

```text
proposed -> approved -> published
proposed -> rejected
proposed -> expired
approved -> expired
```

规则:

- `cx.agent.draft.propose` / `cx.agent.action_request` 只创建或更新 controller-owned `cx.agent.draft.v1` account data,状态为 `proposed`。
- `cx.agent.action_approve` MUST 由 controller principal 或 fresh controller approval 产生,并绑定 `draft_id`、draft content digest、target descriptor、`proposed_action`、approved payload digest、approval expiry 和 single-use nonce。Controller 可以在批准前编辑内容;此时 approved payload digest 以编辑后的最终 payload 为准,原 draft content 只作为 private 审计输入。
- `cx.agent.action_reject` 把 draft 标记为 `rejected`;agent runtime MUST NOT 继续尝试发布该 draft。
- `approved` draft 仍不是 shared content。它只是一份 controller-private authorization artifact。
- 真正进入目标 Realm / Flow 的步骤是生成新的 shared event。若由 controller 客户端发布,shared event 的 `actor_id` 是 controller。若由 agent runtime 发布,则必须按 §4.10 使用 reply-as-agent 或 act-on-behalf attribution,并通过 `authorization_ref` / approval reference 证明该 publish 覆盖目标 action 与 resource。
- Publish executor MUST 对 approval nonce 做 atomic consume / compare-and-set。成功发布后,对应 draft 状态变为 `published`,并记录 shared event digest / opaque reference;重复提交同一 approval MUST fail closed(`reason="approval_already_consumed"` 或等价错误)。
- Draft 过期、被拒绝或已发布后,MUST NOT 再生成新的 shared event;如需重新发布,agent 必须创建新的 draft / action request。
- Shared event MAY 携带 `refs[].role="draft_source"` 的 opaque digest 或 approval reference,但不得携带明文 `draft_id`、account-data key、`private_flow_id`、scratchpad、private prompt 或历史版本。

因此,"草稿成为正式信息"不是对象搬迁,而是 controller 批准后产生一条新的 shared event;draft 本身始终留在 private/account-data 语义内。

### 4.9 Effective permission rule

Agent 的 effective permission 是以下条件的交集:

```text
controller-approved grant
AND controller's own delegable authority
AND Realm policy
AND resource selector / constraints
AND agent key scope
AND requested session scope
AND current revocation / freshness state
```

Agent MUST NOT 自动继承 controller 在 Realm 内的最大权限。即便 controller 是 Realm admin、owner 或拥有广泛 membership,agent 也只获得显式授予的、受限的、短期的能力。

本 profile 不新增并行 constraint vocabulary。它复用 `capabilities.md` 已注册的 resource selector 与 typed constraints:

| 需求 | Canonical 表达 |
| --- | --- |
| 限定 Realm | resource selector `kind="realm"` 或对象 selector 的 `realm` / `match_scope`,不是 constraint。 |
| 限定 Flow | resource selector `kind="object"`, `object_type="flow"`, `match_scope="object_refs"` + `allowed_object_refs[]`;或已注册 `allowed_flow_refs` constraint。 |
| 限定输出 track | `constraint_type="scope_limitation"` + `allowed_tracks[]`。它只限制输出位置,不创建 per-track security boundary。 |
| 限定明文类别 | `allowed_data_classes[]`。 |
| 限定动作 | grant 顶层 `actions[]`,不是 constraint。 |
| 限速 / 配额 | `constraint_type="quota"`, `subtype="rate"`, `max_operations` + `period`。 |
| 人类批准 | `constraint_type="claim_based"`, `subtype="approval"`, `approval_required`, `approval_mode`, `approval_actor_refs`。 |
| controller accountability approval | `constraint_type="claim_based"`, `subtype="accountability"`, `controller_approval_required`。 |
| 允许外部工具 / service endpoint | `allowed_endpoints[]`。 |
| summary / decision 输出位置 | `allowed_tracks[]`,不另设 `output_track_policy`。 |

例如"只允许把 summary 写入 synthesis track"的 canonical grant:

```json
{
  "actions": ["cx.message.create"],
  "resources": [
    {
      "kind": "object",
      "object_type": "flow",
      "match_scope": "object_refs",
      "allowed_object_refs": ["cx:flow:01970000-0000-7000-8000-000000000001"]
    }
  ],
  "constraints": [
    {
      "constraint_type": "scope_limitation",
      "allowed_tracks": ["synthesis"]
    }
  ],
  "expires_at": "2026-06-26T00:00:00Z"
}
```

`act_on_behalf` 不是一个 constraint。它由 event attribution (`actor_id` = controller, `executed_by` = agent, `authorization_ref` = grant / approval)、capability grant、Realm policy、accountability constraint 与 fresh approval 共同校验。

如果接收方无法执行某个 constraint,它 MUST fail closed 或拒绝该 grant;不得忽略 constraint 后放行。

Realm policy MUST 至少能分别控制 native personal agent 与 Applet / Ghost Actor。部署可以禁止普通用户创建或使用 personal agents,同时允许管理员安装的 Applet + Ghost Actor,也可以反向配置;二者不得被合并为一个不可区分的 "automation allowed" 开关。

### 4.10 Reply-as-agent 与 act-on-behalf

Reply-as-agent:

```json
{
  "actor_id": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "kind": "cx.message.create"
}
```

客户端把它渲染为 agent,并展示 accountability:

```text
Summary Assistant
accountable to Alice
```

Act-on-behalf:

```json
{
  "actor_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:users.example:alice",
  "executed_by": "did:webvh:QmQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:users.example:agents:summary-assistant",
  "authorization_ref": "cx:grant:01970000-0000-7000-8000-000000000030",
  "kind": "cx.message.create"
}
```

客户端 MUST 展示双重署名:

```text
Alice via Summary Assistant
```

Act-on-behalf grant 是 high risk。规则:

- **默认禁止**:除非 controller 与 Realm policy 显式允许,grant MUST 不签发。
- **窄范围**:grant MUST 有限期、限定 action / resource、可审计、可撤销。
- **Receiver 校验**:Receiver MUST 校验 `executed_by` 与实际 signing key / agent proof 一致,并校验 `authorization_ref` 覆盖目标 action 与 resource。
- **Fresh approval 粒度**:默认 SHOULD 是 `(action, target_flow)` + 短期 temporal window;批量 window 必须由 Realm policy 显式开启。
- **Wire 表达**:全部通过现有 `approval_required` / `approval_mode` / `approval_actor_refs` / `controller_approval_required` 组合,不新增 `act_on_behalf_allowed` constraint。

Schema impact:该形态要求 Event Envelope 增加 signed `executed_by` 与 `authorization_ref` 字段,并把二者纳入 event canonical bytes、event digest、E2EE AAD 与 Anchor/sub-anchor leaf 输入。它们不能只作为 UI-only unsigned extension。Accepted migration 必须同时更新 `event-envelope.schema.json`、canonicalization 规则、`event-and-patch.md` 与 schema-registry / service-surface 相关说明,并定义它们与 `proof.verification_method` / active `cx.agent.key.authorize` 的校验关系。

### 4.11 管理与撤销

新增 profile operations:

```text
GET  /api/v1/agents
GET  /api/v1/agents/{agent_principal_id}
POST /api/v1/agents/{agent_principal_id}/pause
POST /api/v1/agents/{agent_principal_id}/resume
POST /api/v1/agents/{agent_principal_id}/deactivate
POST /api/v1/agents/{agent_principal_id}/rotate-key
POST /api/v1/agents/{agent_principal_id}/grants
DELETE /api/v1/agents/{agent_principal_id}/grants/{grant_id}
```

Revocation MUST 使以下材料失效:

- active agent sessions;
- active agent keys,除非只撤销某个具体 key;
- 相关 capability grants / delegations;
- push / webhook / runtime endpoint bindings,如果存在;
- pending action requests,除非 controller 显式保留。

Pause 的精确语义:

- 保留 agent identity、历史记录、accountability_grant、agent_key_authorize 与 capability grants 的 durable state。
- Auth Server MUST 拒绝**新**的 agent session grant 请求(返回 §4.6 同款 structured error,reason_code 建议为 `agent_paused`)。
- 已签发但未过期的 session token:Auth Server SHOULD 在 revocation freshness window(默认与 session 最大 TTL 对齐,即 ≤ 15 分钟)内令其 fail closed。实现路径有两种,profile MUST 在二者中选其一并声明:
  - 同步 revocation:把现有 session token id 推入 revocation list,资源服务器在校验时拒绝(对 high-risk action MUST fail closed when revocation state stale)。
  - 自然过期:不主动撤销现有 token,但 freshness window 内 high-risk action MUST 重新查询 agent status 并 fail closed。
- 与 pause 并行的 pending action requests SHOULD 标记为 `awaiting_resume`,不自动失败也不继续执行,直到 resume 或 revoke。

Resume 前 MUST 重新校验 controller、agent、key、capability、Realm policy 与 accountability_grant freshness;任一不通过则拒绝 resume,agent 保持 `paused`。

Agent key rotation SHOULD 复用 `cx.agent.key.rotate`,并要求 replacement key 的 `agent_key_scope` 等于或窄于旧 key。

这些 management operation MUST 产生可审计的 durable state,不得只修改服务端内存或私有配置。候选 durable event 落点(运行时行为已在前文给出,本处只列审计材料形态):

- `pause`: `cx.agent.pause` 或等价 signed agent status event / principal-control state。
- `resume`: `cx.agent.resume` 或等价 signed status transition。
- `deactivate`: `cx.agent.deactivate` terminal state,并 fan-out `cx.agent.key.revoke`、`cx.capability.revoke` / delegation revoke、runtime endpoint revoke。canonical op id 为 `cx.agent.deactivate`,URL `/api/v1/agents/{agent_principal_id}/deactivate`。
- `rotate-key`: `cx.agent.key.rotate`,记录 replacement key proof 与 approval evidence。

`cx.agent.pause` / `cx.agent.resume` / `cx.agent.deactivate` 已在 accepted artifact 中作为 active event kinds 注册;此处保留枚举以便 audit material 实现者快速查找。

## 5. 与 normative spec 的交互

### 5.1 可能影响的 normative 文档

- `zh/models/actor.md`: 澄清 personal native agent、accountability UI,以及与 Ghost Actor 的区别。
- `zh/identity/key-management.md`: 增加 runtime key pairing 与 agent session grant 规则。
- `zh/identity/account-lifecycle.md`: 定义 agent principal 的 pause / deactivate 行为。
- `zh/authz/capabilities.md`: 增加 agent provisioning / management actions,并明确 personal agent 复用现有 `allowed_tracks`、`allowed_flow_refs`、`allowed_data_classes`、`allowed_endpoints`、`rate_limit` 与 approval/accountability constraints。
- `zh/models/private-objects.md`、`zh/sync/client-sync.md` 与 `zh/sync/operations-sync.md`: 澄清 draft-only 使用 encrypted account data / actor-private stream,不得进入 shared Realm history。
- `zh/models/event-and-patch.md` 或 Event Envelope 相关章节:为 act-on-behalf 增加 signed `executed_by` 与 `authorization_ref` 字段、canonicalization、Anchor 输入与校验规则。同时 SHOULD 在 Event Envelope 上 cache 一个 `actor_kind` projection(由 reducer 在写入时从 Actor Profile 解析),让审计 / 取证 / offline reader 不必反向解析 Actor Profile 即可判断 event 是 agent 行为或 controller 行为。该 projection 是 reducer-stamped immutable 字段,不进入 actor-supplied submit payload。
- `zh/extensions/applet-integration.md`: 澄清管理员管理的 Ghost AI agents 是 Applet-managed external/integration actors,而本 CXP 覆盖 native personal agents。
- `zh/extensions/agent-protocol-interop.md`: 确保 agent runtime session 不暗示支持外部 A2A / ACP session。
- `zh/sync/service-surface.md` 与 `service-http-binding.md`: 增加 profile operations。本 CXP 不引入 custom URI scheme;客户端 deep-link 由 OS Universal Links / App Links 拦截标准 HTTPS URL(host 来自 deployment 已知的 `contrix_base_url`)。
- `zh/conformance/conformance-profiles.md`: 增加三个新 profile 与测试期望。

### 5.2 Accepted 后可能需要的 artifact 改动

- `operation-registry.json`: 增加 `cx.agent.provision`、`cx.account.agent_key_pair`、list/get/pause/resume/deactivate/rotate_key/grant management operations(canonical op id `cx.agent.deactivate`, URL `/api/v1/agents/{agent_principal_id}/deactivate`,旧 `/revoke` 形态不再 normative)。Agent runtime session 复用现有 `cx.account.issue_session_grant` operation,不注册单独的 agent-session 签发 operation。
- `event-kind-registry.json`: 不增加 `cx.agent.provision` aggregate event;provisioning operation fan-out 到 `cx.profile.create`、`cx.identity.accountability_grant`、`cx.agent.key.authorize`、`cx.capability.grant` 等既有 durable events。增加 `cx.agent.pause`、`cx.agent.resume`、`cx.agent.deactivate` 或等价 lifecycle state events,并增加 `cx.agent.draft.propose`、`cx.agent.action_request`、`cx.agent.action_approve`、`cx.agent.action_reject` draft/action-request family。
- `account-data-type-registry.json`: 增加 `cx.agent.draft.v1`,key pattern 建议为 `cx.agent.draft.v1:<agent_principal_id>:<draft_id>`,并声明 `encrypted_at_rest=true`、tombstone 与 retention 规则。
- `capability-action-registry.json`: 增加 `cx.agent.provision` 作为 aggregate admin action,其 `target_event_kinds` MUST 显式列出 fan-out 子事件,例如 `cx.profile.create`、`cx.identity.accountability_grant`、`cx.agent.key.authorize`、`cx.capability.grant`,并标注 migration group。Agent management actions 同样必须声明 target event kinds,不得从 action 字符串推断。
- `event-payload.schema.json`: 若现有 `agent_key_authorize_payload` 尚未包含 runtime attestation,增加 `runtime_attestation` 或 attestation digest/ref 字段;v1 enum 至少包含 `self_asserted`,未知 kind fail closed。
- `event-envelope.schema.json` / `event-payload.schema.json`: 为 accepted 新 event 增加 payload defs;为 act-on-behalf 增加 signed `executed_by` 与 `authorization_ref` 字段,并同步 canonicalization / Anchor vectors。同时增加 reducer-stamped `actor_kind` projection 字段(由 reducer 从 Actor Profile 解析,immutable,不接受 actor-supplied 输入),供审计与离线读取使用。
- `conformance-profiles.json`: 注册 `cx.profile.personal_agent_provisioning.v1`、`cx.profile.agent_auth.v1`、`cx.profile.agent_delegation_policy.v1`。
- OpenAPI: 增加 agent provisioning、pairing typed schemas,并扩展现有 `SessionGrantRequest` / `SessionGrantResponse` 以支持 `proof.proof_kind="agent_key_proof"`、独立 proof schema branch、独立 validator 与 `scope_details` profile overlay。

本提案仍为 `draft` / `review` 时不得改 artifact。

## 6. 设计理由与替代方案

### 6.1 为什么不让 agent 每次登录都走人类 coauth

人类 coauth 因子不适合后台自动化。CAPTCHA、OTP、WebAuthn user presence 与 SSO redirect 会让自动化脆弱,并诱导实现存储人类 refresh token 等不安全 workaround。

更安全的拆分是:

- 人类 coauth 用于 provisioning、approval、recovery 和 high-risk escalation。
- agent key proof 用于常规 runtime session。
- policy 需要人类判断时返回 structured approval request。

### 6.2 为什么不让所有 AI Agent 都使用 Ghost Actor

Ghost Actor 适合 Applet-managed bridge actors 和外部托管 actor 池。但"我的 native AI assistant"需要可被 mention、grant、revoke、管理的一等 Contrix actor principal,因此更适合 native agent principal。

### 6.3 为什么不让 agent 继承用户权限

完整继承违背最小权限原则,并显著扩大事故影响面。即便 controller 是 Realm admin,agent 也应只得到显式委托的、scoped、short-lived capability。

### 6.4 为什么不签发长期 agent bearer token

Bearer token 泄露后更难约束和追溯。Agent runtime SHOULD 使用 private signing key 或 workload credential 换取短期、audience-bound session。

### 6.5 为什么复用 `/auth/account/session-grants`

Session grant 是 account/auth surface 的统一产物。复用 `/auth/account/session-grants` 可以避免出现两套 token 签发、撤销、TTL、audience 和审计路径,也让客户端与资源服务器只需要理解一种 `cx.session.grant` 生命周期。

风险是 human login 与 machine runtime auth 被实现混淆。因此本 profile 要求三道闸:独立 schema 分支、独立 proof validator、返回 scope 只能来自 agent key authorization / capability grant / Realm policy / requested scope 的交集。任何实现若无法区分该分支,必须拒绝 `agent_key_proof`,不得降级到其它 proof kind。

### 6.6 为什么 pairing 放在 account/auth namespace

Runtime key pairing 与 device pairing 类似:它不是普通协作对象写入,而是把一个运行时 credential 绑定到某个 principal / account control context。放在 `/auth/account/*` 下可复用 account auth 的 challenge、risk、approval、replay protection 与审计路径。

## 7. 开放问题

### 7.1 已决记录

- [x] Agent runtime session 复用 `/auth/account/session-grants`,通过 `proof.proof_kind="agent_key_proof"` 与独立 schema/proof validator 区分。
- [x] Runtime key pairing 放在 account/auth namespace,候选 path 为 `POST /auth/account/agent-key-pair`。
- [x] Agent session grant 默认最大 TTL 收敛为 15 分钟;更长 TTL 必须 profile 声明额外风险控制,且不应超过 60 分钟。
- [x] Realm policy 必须能分别控制 native personal agent 与 Applet / Ghost Actor。
- [x] Flow-context private agent chat 不放入本提案;拆分到 CXP-0009 `Agent Sidecar Thread`。
- [x] `cx.agent.provision` 只作 service operation;durable audit 由 `cx.profile.create`、`cx.identity.accountability_grant`、`cx.agent.key.authorize`、`cx.capability.grant` 等 fan-out 子事件承载。
- [x] Draft-only 标准化为 `cx.agent.draft.propose` / `cx.agent.action_request` family + controller-owned `cx.agent.draft.v1` encrypted account data。
- [x] Track-level grant 复用现有 `allowed_tracks`;不引入 `allowed_track_names` 或其它并行 vocabulary。
- [x] `agent_scope_request` 保持 `cx.profile.agent_auth.v1` overlay,不进入通用 human `SessionGrantRequest` schema。
- [x] Agent E2EE access 表达为独立 MLS member,默认无 E2EE access;不得作为 controller delegated device 继承 history keys。
- [x] `act_on_behalf` 默认 fresh approval 粒度为 `(action, target_flow)` + 短期 window,通过现有 approval/accountability constraints 表达。
- [x] `did:webvh` deployment SHOULD 为 personal agent 分配独立 SCID,并 MAY 在 `did:webvh:<scid>:<host-and-path>` 的 `<host-and-path>` 中采用 `agents/<slug>` 可读路径约定;规范信任来源是独立 DID document 与显式 accountability grant,不是路径继承。
- [x] Lifecycle event kinds 注册为 `cx.agent.pause` / `cx.agent.resume` / `cx.agent.deactivate`(已在 accepted artifact 中作为 active event kinds,FSM lattice / `bottom=reject`,payload schema 已 wire 在 `event-payload.schema.json`)。不复用未来可能的通用 `cx.principal.status.set`——principal type 之间的 status 字段语义差异(agent freshness frontier vs human soft_logged_out vs service endpoint revoke)足以让单一 lifecycle event 反而增加 reducer 复杂度。该决议关闭后任何统一 lifecycle event 提案需要独立 CXP。

### 7.2 仍需讨论

本节当前为空——所有 accepted 阶段必需的决议已迁入 §7.1。后续 review feedback 若出现新的待议事项,会重新列入本节。

## 8. 迁移计划

草案占位。若 accepted,按阶段迁入:

1. 增加 conformance profile declarations。
2. 增加 service operations 与 OpenAPI typed schemas。
3. 扩展 `SessionGrantRequest.proof.proof_kind` 枚举,新增 `agent_key_proof` 分支。
4. 增加 capability actions,并把 agent grant 示例全部映射到现有 constraint vocabulary。
5. 增加 draft-only account-data type / draft event family。
6. 增加 pause / resume / deactivate 等 accepted durable lifecycle event kinds。
7. 增加 pairing、agent session grant、draft privacy、revocation、act-on-behalf attribution 和 permission intersection 的 conformance vectors。

## 9. 引用

- 现有 Agent Key 规则: `spec/v1/zh/identity/key-management.md`。
- Actor Profile 与 accountability: `spec/v1/zh/models/actor.md`。
- Capability grants 与 delegation: `spec/v1/zh/authz/capabilities.md`。
- Actor-private / account-data state: `spec/v1/zh/models/private-objects.md`、`spec/v1/zh/sync/client-sync.md`。
- Agent sidecar thread follow-up: `spec/v1/proposals/0009-agent-sidecar-thread.md`。
- Applet / Ghost Actor 边界: `spec/v1/zh/extensions/applet-integration.md`。
- Agent protocol interop extension: `spec/v1/zh/extensions/agent-protocol-interop.md`。
