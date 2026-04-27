# 兼容性与实现 Profile

## 1. 目标

Contrix 是模块化协议。为了避免“实现了 Contrix”变成不可验证的模糊声明，规范 MUST 定义可测试的实现 profile。

每个实现 MUST 声明自己支持的 profile、协议版本和 feature 集合。  
Conformance 测试 SHOULD 以 profile 为单位执行。

## 2. Profile 命名

Profile 名称使用：

```text
cx.profile.<name>.v<major>
```

示例：

- `cx.profile.minimal_client.v1`
- `cx.profile.repo_node.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`

## 3. 通用强制要求（所有 Profile 必须遵守）

以下要求不依赖具体角色，必须作为可互操作实现的基础：

- 事件名必须符合 `cx.` 命名规则，且必须在 `schema-registry.md` 注册，或在 migration profile 下有明确兼容映射。
- 事件/关系/实体/View 的 `type`、`created_at`、`space_id`、`space_version`、`proof`、`hlc`、`actor_seq`、`prev_refs` / `auth_refs` 在 reducer 与验证逻辑中不能被跳过。
- `space_version` 与 `auth` 约束必须执行，不得通过客户端配置豁免。
- 兼容别名（如 `space.create`）仅允许在 migration profile 中出现，不允许作为新增标准互操作行为。
- 实现 MUST 对 `causal` 关系、`revoked` 与 `proof` 失效状态进行一致性拒绝（fail-closed），不能“静默接受”。

## 4. Minimal Client

`cx.profile.minimal_client.v1` 适用于只读或轻量写入客户端。

MUST 支持：

- DID / handle 解析
- service discovery
- repo commit / operation 拉取
- index 查询
- 基础 Entity / Relation / Event 解码
- capability 检查结果处理
- cursor 分页
- 标准错误响应

MAY 支持：

- 本地 reducer
- E2EE 解密
- 离线写入
- push notification

## 4. Full Client

`cx.profile.full_client.v1` 适用于桌面、Web 和移动主客户端。

MUST 支持 Minimal Client 的全部能力，并额外支持：

- 本地 repo cache
- 本地 reducer
- 离线 operation 队列
- 幂等重放
- Space bootstrap
- invite accept / reject
- read marker
- notification rule
- profile / presence / typing
- blob upload / download
- conflict UX

SHOULD 支持：

- local full-text search
- private account state
- multi-device sync
- export / backup

## 5. E2EE Client

`cx.profile.e2ee_client.v1` 适用于加密 Space。

MUST 支持 Full Client 的相关能力，并额外支持：

- MLS RFC 9420 group state
- KeyPackage publish / fetch / verify
- Welcome / Commit / Proposal event
- epoch mismatch recovery
- encrypted payload envelope
- encrypted attachment envelope
- device revocation handling
- lost-device response
- local plaintext search for encrypted content

MUST NOT：

- 把明文消息发送给 sync service / index
- 把解密密钥上传给不受信服务
- 在未验证 KeyPackage 所属 DID 的情况下加密给对方

## 6. Repo Node

`cx.profile.repo_node.v1` 适用于 actor repo 或 Space repo 服务。

MUST 支持：

- submit commit / operation
- idempotent write
- commit fetch
- operation fetch
- cursor-based history
- signature verification
- schema validation
- capability precheck
- conflict reporting
- content-addressed blob reference validation

SHOULD 支持：

- snapshot generation
- witness receipt
- rate limiting
- quota accounting

## 7. Principal Server

`cx.profile.principal_server.v1` 适用于用户、组织或 agent principal 控制/委托的服务入口。

MUST 支持：

- subscribe / sync stream
- backfill
- client sync (`POST /sync`)
- cursor stability
- duplicate suppression
- encrypted payload forwarding
- authorization-aware routing metadata
- service describe
- service binding verification for federation destinations
- plaintext-visible service enforcement

SHOULD 支持：

- multi-upstream Principal Server federation
- quarantine queue
- witness receipt
- snapshot pointer distribution

Principal Server MUST NOT become the canonical truth source for Space state.
Principal Server MUST NOT forward non-E2EE private content or reversible derived plaintext to services absent from the relevant DID delegation or Space policy `plaintext_visible_services`.

## 8. Index Node

`cx.profile.index_node.v1` 适用于查询和物化节点。

MUST 支持：

- reducer profile declaration
- entity current-state query
- relation query
- structured query
- notification / inbox materialization
- authorization filtering
- stale frontier reporting
- `X-Contrix-Wait-For` 或等价 sync token
- plaintext-visible declaration and policy enforcement when indexing private plaintext

SHOULD 支持：

- full-text search for plaintext Space
- local-only search coordination for encrypted Space
- explain / debug endpoint for reducer state

Index Node MUST NOT be treated as an authority unless its output can be traced to signed ops and declared reducer profile.

## 9. Identity Registry Node

`cx.profile.identity_registry.v1` 适用于 DID 文档与 key log 服务。

MUST 支持：

- DID resolve
- DID log fetch
- DID operation submit
- `inception_key` verification
- `key_log` validation
- receipt publication
- method adapter metadata

SHOULD 支持：

- witness-only mode
- read replica mode
- raw DID document preservation
- normalized principal view

## 10. Blob Node

`cx.profile.blob_node.v1` 适用于内容寻址存储。

MUST 支持：

- upload
- download
- HEAD metadata
- SHA-256 digest verification
- size limit
- MIME metadata
- authorization-aware access

SHOULD 支持：

- encrypted attachment metadata
- thumbnail / preview derivation
- GC grace period
- legal hold
- unsafe media flag

## 11. Enterprise Client

`cx.profile.enterprise_client.v1` 适用于企业受控客户端。

MUST 支持 Full Client，并根据 policy 支持：

- OIDC / SSO gateway session grant
- device inventory
- admin-triggered device revocation
- auditable E2EE warning UI
- compliance audit event display
- managed update policy

MUST NOT 在不显示 policy 的情况下静默加入 auditable encrypted Space。

## 11.5 Sovereign Deployment

`cx.profile.sovereign_deployment.v1` 适用于军方、关键基础设施、金融核心、情报或其他高安全组织的自建/专属部署。

MUST support:

- Organization DID controlled service delegation
- service DID allowlist
- closed federation default
- private directory default
- controlled collaboration Space
- restricted or invite-only external join
- policy server `closed` or `quarantine` fail mode
- E2EE default for controlled collaboration
- MLS Welcome only to approved external devices
- external Applet / Agent / transport allowlist
- cross-domain event audit
- grant / invite / membership revocation
- MLS epoch rotation after external removal

MUST NOT:

- expose internal Space directory to external members
- treat external Principal Server / Index as authority
- allow public federation by default
- allow external Applet or Agent handoff without explicit capability and policy

SHOULD support:

- isolated collaboration enclave
- import/export review metadata
- data classification labels
- hardware-backed service keys
- offline witness receipts
- break-glass workflow with signed audit

## 11.6 Sovereign Client

`cx.profile.sovereign_client.v1` 适用于接入 sovereign deployment 的受控客户端。

MUST support:

- managed configuration signed by organization DID or governance service DID
- resolver trust domain pinning
- internal `did:uuid` resolution through approved registry / witness only
- service DID allowlist enforcement
- rejection of public registry / public directory for internal principals
- device posture check
- remote session and device revocation
- E2EE default
- classification and external member policy display
- local export controls
- audit log generation

MUST NOT:

- let users add arbitrary Principal Server / Index / Directory / Blob endpoints
- resolve internal `did:uuid` through public registry by default
- silently join Space with external members or auditable E2EE
- expose private organization directory to public search
- enable public social feed, Applet or Agent handoff unless policy allows

SHOULD support:

- hardware-backed device keys
- offline resolver bundles
- smart card / platform authenticator
- policy-controlled copy, screenshot and bulk export restrictions
- emergency wipe

## 12. Agent Runtime

`cx.profile.agent_runtime.v1` 适用于 AI agent、bot、automation。

MUST 支持：

- DID 或 delegated actor identity
- explicit capability grant
- scoped action execution
- run log
- memory write policy
- accountability metadata
- kill switch / revocation check

SHOULD 支持：

- proposal mode for high-risk actions
- approval constraint
- deterministic replay metadata
- tool call audit envelope

## 13. Applet Bridge

`cx.profile.applet_bridge.v1` 适用于桥接外部系统和运行 Applet 集成服务。

MUST 支持：

- signed `applet_registration`
- namespace declaration and matching
- ping / describe endpoint
- transaction push endpoint
- transaction idempotency
- query actor endpoint
- query space endpoint
- protocol metadata endpoint
- ghost actor accountability metadata
- portal Space metadata
- capability enforcement
- HTTP message signature verification
- event signature verification
- external event deduplication

MUST NOT：

- 把 namespace 命中当作写权限
- 静默 impersonate native user
- 在无授权时接收全网 sync stream
- 在未提示边界的情况下把 E2EE 内容桥接到非 E2EE 网络

SHOULD 支持：

- third-party user / location lookup
- bridge error event
- admin revoke / pause
- per-Space bridge policy
- Applet health and lag metrics

## 14. Conformance 测试要求

每个 profile SHOULD 提供：

- schema validation tests
- signature verification tests
- idempotency tests
- reducer convergence tests（含 state resolution 向量）
- state resolution state vectors（见 `state-resolution-conformance-vectors.md`）
- redaction vectors（见 `redaction-conformance-vectors.md`）
- capability vectors（见 `capability-conformance-vectors.md`）
- authorization tests
- privacy regression tests
- error response tests
- downgrade / unsupported feature tests

所有 profile MUST 能按 `data-structures.md` 解码和验证其声明支持的核心对象字段。实现 MAY 保留未知字段，但 MUST reject 类型错误、必填字段缺失、非法 enum、非法 ID/hash/timestamp/cursor pattern，以及违反条件必填规则的对象。

所有 profile MUST 按 `encoding-conformance-vectors.md` 覆盖 canonical JSON、hash、signature binding、HLC 和 cursor 的基础向量。Repo、Index、Full Client 与 E2EE Client MUST 额外覆盖 event digest；Repo Node MUST 覆盖 commit digest；E2EE Client 和 Principal Server MUST 覆盖 encrypted envelope digest。

E2EE profile MUST 额外提供：

- KeyPackage verification vector
- MLS epoch transition vector
- encrypted payload vector
- removed member cannot decrypt vector

Client Sync 相关 profile MUST/SHOULD 按 `sync-conformance-vectors.md` 执行对应向量：

- Minimal Client MUST 覆盖基础排序、tie break、pagination gap、backfill order 和 token expiry recovery。
- Full Client MUST 额外覆盖 snapshot frontier、state_after 与 decryption_pending 的 UI / cache 恢复行为。
- E2EE Client MUST 覆盖 MLS epoch backfill、decryption_pending recovery 和 removed member fail closed。
- Index Node MUST 覆盖 deterministic timeline order、causal barrier 和 stale frontier reporting。
- Principal Server SHOULD 覆盖 duplicate suppression、backfill order、encrypted payload forwarding 和不能转发解密材料。

Identity profile MUST 额外提供：

- `did:uuid` bit layout vector
- `inception_key` hash vector
- key rotation vector
- recovery vector
- pairwise DID unlinkability checks

Applet Bridge profile MUST 额外提供：

- registration signature vector
- namespace conflict vector
- duplicate transaction vector
- ghost actor mapping vector
- portal Space mapping vector
- unauthorized write rejection vector

## 15. Feature Discovery 示例

```json
{
  "service_did": "did:web:index.example.com",
  "service_type": "ContrixIndex",
  "protocol_version": "0.2-draft",
  "supported_profiles": [
    "cx.profile.index_node.v1"
  ],
  "supported_features": [
    "structured_query",
    "notification_index",
    "wait_for_sync_token"
  ],
  "reducer_profiles": [
    "cx.reducer.v1"
  ],
  "schema_profiles": [
    "cx.schema.core.v1"
  ]
}
```

## 16. 初版决定

首个互操作目标 SHOULD 是：

- `minimal_client`
- `repo_node`
- `principal_server`
- `index_node`
- `identity_registry`
- `blob_node`
- `applet_bridge`

`full_client` 和 `e2ee_client` 是产品可用性的目标 profile。  
`enterprise_client` 和 `agent_runtime` 是高价值扩展 profile，但不应阻塞基础互操作。
