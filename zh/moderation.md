# Moderation Draft

## 1. 目标

去中心化协作协议不能仅依赖"好人不会来捣乱"的假设。协议必须提供标准化的**内容审核与用户管理**机制，包括：

- 用户举报不当内容
- 忽略/屏蔽其他用户
- Space 级别的审核策略
- 组织级别的准入黑名单、允许列表和风险策略
- 服务器级别的访问控制

## 2. 设计原则

### 2.1 审核权由 Space Owner 行使

去中心化环境中没有"全网管理员"。内容审核的权限由 Space 的 Capability 体系决定。只有拥有 `space.moderate` 权限的 Actor 才能执行审核操作。

### 2.2 屏蔽是本地行为

用户屏蔽另一个用户是纯本地的客户端行为，不需要广播到网络。协议不应强制"告诉全世界我屏蔽了谁"。

### 2.3 举报留痕但不公开

举报记录应被安全送达 Space 管理员，但不应暴露给被举报人或其他普通成员。

### 2.4 黑名单不是 capability grant

Contrix 的授权核心仍然是 allow-grant + explicit revoke。黑名单、过滤器和风险策略是额外的 deny/quarantine 层：

- 没有 capability 时，黑名单不能创建权限。
- 有 capability 时，Space / Organization / Service policy MAY deny、quarantine 或 require review。
- 个人 block 只影响个人客户端体验，不能替 Space 删除其他成员可见的事实。

## 3. 内容举报 (Report)

### 3.1 举报操作

用户可以举报 Space 中的任何 Entity（消息、任务、评论等）：

```
POST /api/v1/moderation/report
```

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "target_ref": "cx:message:01JS1000000000000000000002",
  "reason": "harassment",
  "description": "This message contains targeted personal attacks.",
  "reporter": "did:web:alice.example.com"
}
```

### 3.2 举报原因枚举

| Reason | 说明 |
|--------|------|
| `spam` | 垃圾信息 / 广告 |
| `harassment` | 骚扰 / 人身攻击 |
| `hate_speech` | 仇恨言论 |
| `nsfw` | 不适当的成人内容 |
| `illegal` | 违法内容 |
| `misinformation` | 虚假信息 |
| `other` | 其他原因（需要 `description` 补充说明） |

### 3.3 举报的处理

- 举报会生成一个 `event.moderation.report` 事件，写入 Space Repo
- 该事件仅对拥有 `space.moderate` 权限的 Actor 可见
- 被举报人不会收到通知
- 管理员可以基于举报决定后续行动（警告、删除内容、封禁用户等）

## 4. 用户屏蔽 (Ignore/Block)

### 4.1 屏蔽是 Actor-Private 状态

用户可以屏蔽任意 Actor，屏蔽列表存储在本地或用户的私有 Repo 中：

```json
{
  "type": "cx.account.blocklist",
  "owner": "did:uuid:alice",
  "entries": [
    {
      "target": {
        "kind": "actor",
        "did": "did:web:spammer.example.com"
      },
      "mode": "block",
      "created_at": "2026-04-26T10:00:00Z",
      "reason_code": "harassment",
      "expires_at": null
    }
  ]
}
```

### 4.2 屏蔽行为

客户端在渲染时：

- SHOULD 隐藏被屏蔽用户的消息
- SHOULD 不显示被屏蔽用户的 Typing 和 Presence 状态
- SHOULD 不为被屏蔽用户的消息生成通知
- SHOULD 默认拒绝被屏蔽用户发起的 DM、call invite、contact request 和 applet-mediated request
- MAY 在共同 Space 中显示折叠占位符，避免破坏上下文
- MUST NOT 从网络层面丢弃被屏蔽用户的 Op（这些 Op 对其他成员仍然有效）

### 4.3 个人过滤对象

个人 blocklist MAY 包含：

- actor DID
- device DID / device id
- service DID
- handle
- domain
- organization DID
- Applet id
- keyword / mention pattern

对 handle、domain、organization DID 的屏蔽 MUST 在本地解析成可验证 DID / claim 后应用。客户端 MUST NOT 因裸字符串后缀误伤无关主体。

### 4.4 隐私要求

个人 blocklist 是 holder-private account data。实现 MUST NOT 默认上传明文 blocklist 到公共 Relay、Space、Directory 或被屏蔽方可见的位置。

跨设备同步 SHOULD 使用 Account Repo + 客户端加密。服务端只应看到不透明密文。

## 5. Space 审核工具

### 5.1 内容删除

管理员可以通过 `cx.message.redact` 操作撤回任意成员的消息：
- 需要 `space.moderate` 权限
- 撤回会产生 tombstone，不可逆
- 审计视图中仍可看到撤回记录

### 5.2 用户封禁

管理员通过 `cx.membership.ban` 操作封禁用户（详见 `object-model-core.md` 的成员与 policy 语义）。封禁后：

- 被封禁用户无法重新加入该 Space
- 其未来的 Op 提交将被 Relay 拒绝
- 是否隐藏其历史内容由 Space Policy 决定

### 5.3 Space Blocklist / Filter Policy

Space MAY 使用 `cx.space.moderation_policy` state event 声明黑名单、允许列表、内容过滤和风险处理策略。

```json
{
  "type": "cx.space.moderation_policy",
  "state_key": "default",
  "content": {
    "version": 1,
    "targets": [
      {
        "target": {
          "kind": "actor",
          "did": "did:web:spammer.example.com"
        },
        "action": "deny_join",
        "reason_code": "spam",
        "created_by": "did:web:acme.example#mod",
        "created_at": "2026-04-26T00:00:00Z",
        "expires_at": null
      },
      {
        "target": {
          "kind": "domain",
          "domain": "malicious.example"
        },
        "action": "quarantine_message",
        "reason_code": "abuse_cluster"
      }
    ],
    "content_filters": [
      {
        "filter_id": "cx:filter:spam-links",
        "match": {
          "kind": "url_domain",
          "pattern_hash": "sha256:..."
        },
        "action": "require_review"
      }
    ],
    "appeal": {
      "enabled": true,
      "endpoint": "cx:entity:appeal-topic"
    }
  }
}
```

`action` 取值：

- `deny_join`
- `deny_invite`
- `deny_write`
- `quarantine_message`
- `require_review`
- `redact_on_accept`
- `shadow_collapse`

规则：

- 修改 `cx.space.moderation_policy` MUST require `space.moderate` or `space.policy.manage` capability。
- Space blocklist MUST be evaluated after basic signature/DID validation and before event enters user-visible reducer state。
- `deny_join` / `deny_write` SHOULD produce a signed moderation decision or audit record。
- `quarantine_message` MUST keep the event out of normal user-visible views until moderator approval。
- Content filters SHOULD use hashes, labels or local classification where possible; E2EE Space MUST NOT require plaintext upload to a server-side filter。
- Space blocklist MUST NOT silently override cryptographic history. Existing accepted events require redaction/tombstone/quarantine event to change presentation.

### 5.4 消息审核队列

Space SHOULD 支持审核队列 (Moderation Queue) 视图，汇集所有举报记录。建议使用标准 View 机制：

```json
{
  "kind": "moderation_queue",
  "query": {
    "entity_types": ["moderation_report"],
    "filters": [
      { "field": "fields.status", "op": "eq", "value": "pending" }
    ]
  }
}
```

## 6. 服务器级访问控制

### 6.1 Server ACL

Relay 和 Index 节点可以配置服务器级别的 ACL，控制哪些域的联邦请求被接受或拒绝：

```json
{
  "server_acl": {
    "allow": ["*"],
    "deny": [
      "spam-node.example.com",
      "*.malicious.example.net"
    ]
  }
}
```

规则评估顺序：先检查 `deny` 列表，再检查 `allow` 列表。支持 glob 通配符。

### 6.2 与联邦协议的关系

Server ACL 在联邦层（参见 `federation.md`）起作用。当 Relay 收到来自被 deny 的域的 `push-ops` 请求时，SHOULD 立即返回 `403 CapabilityDenied`。

## 7. Organization-level Moderation

Organization MAY publish organization-level moderation policy for Spaces and services it controls or endorses. This policy applies through explicit references, not by global magic.

Recommended object:

```json
{
  "type": "cx.organization.moderation_policy",
  "organization_did": "did:web:acme.example",
  "policy_id": "cx:org-policy:abuse-v1",
  "scope": {
    "space_ids": ["cx:space:01JS0SP..."],
    "service_dids": [
      "did:web:relay.acme.example",
      "did:web:policy.acme.example"
    ],
    "applies_to_official_spaces": true
  },
  "rules": [
    {
      "target": {
        "kind": "organization",
        "did": "did:web:known-abuse.example"
      },
      "action": "deny_federation",
      "reason_code": "abuse_network"
    },
    {
      "target": {
        "kind": "claim_selector",
        "claim_type": "org_membership",
        "issuer": "did:web:untrusted.example"
      },
      "action": "deny_restricted_join"
    }
  ],
  "valid_from": "2026-04-26T00:00:00Z",
  "valid_until": null,
  "proof": {
    "type": "detached_jws",
    "verification_method": "did:web:acme.example#governance-key-1",
    "jws": "..."
  }
}
```

Rules:

- Organization policy is authoritative only for Spaces/services that explicitly reference it, or for official Spaces whose `cx.space.organization` endorsement states that the organization policy applies.
- A Space MAY override organization defaults only if its policy says override is allowed.
- Organization-level deny SHOULD be enforced by Policy Server, Relay Server ACL, Directory filtering and Space moderation policy together.
- Organization policy MUST be signed by Organization DID or delegated governance service DID.
- Organization policy MUST NOT reveal private user blocklists, private handles or undisclosed organization memberships.

## 8. Policy Server Integration

Space and Organization moderation policies SHOULD be evaluated through Policy Server for dynamic checks:

- invite / join request
- knock request
- message create / edit
- media upload
- Applet transaction
- federation transaction
- directory listing
- call invite

Policy Server MAY return `hard_deny`, `quarantine`, `require_review` or `soft_deny`, but it MUST NOT grant capability by itself.

## 9. 服务端威胁借鉴

在“去中心化服务治理”场景中，服务端常见风险的抗滥用经验如下：

- **入口源身份强制**：任何外部服务联邦请求都先验 `service DID`。未签名或未被 allowlist 的源服务不得参与写路径（至少转入 `soft_deny` / `quarantine`）。
- **多级限速**：Relay / Index / Policy Server 应至少按以下维度限速：`source DID`、`source IP`（或其哈希）、`service token`、`space id`、`endpoint`。超阈值 MUST 返回 `rate_limited`。
- **批量事件反滥用**：对短周期内的 `invite`、`join`、`message`、`media.upload` 进行突发抑制；出现异常突发可触发 `quarantine`。
- **最小可观察性差异**：对未通过鉴权的目录/加入枚举请求，返回统一错误，不泄露对象可见性差异。
- **可疑媒体隔离**：媒体 hash、MIME、扫描标签先入审计与审核，不应默认解密给 relay/index；必要时按 `snapshot`/`preview` 再二次放行。
- **可追溯审计**：每次风控拦截、隔离、降级决策都要记录结构化审计事件，且不得仅依赖联邦来源的本地口头说明。

上述规则至少部分对应 `server-threat-model.md` 中的映射结果。  
`policy-server.md` 与 `federation.md` 也应同步落地。

## 10. 后续待细化

- 自动化审核（基于 AI 的内容分类与标记）
- 上诉流程（被封禁用户的申诉机制）
- 跨 Space 的共享封禁列表与信任/误伤处理
- 审核操作的不可抵赖性日志
