# Contrix 收敛前协议审查报告

> 本报告保留为 2026-05-02 收敛前的审查记录。当前闭环状态以 `zh/overview/gap-analysis.md`、`artifacts/` 机器工件和 `zh/conformance/` 为准。

审查日期：2026-05-02

审查范围：以 `zh/` 目录为主规范文本，参考 `artifacts/` 下的 schema、operation registry、OpenAPI 等机器可读输出物。英文目录已在根 README 中标记为 stale，本报告不以英文目录作为判断依据。

## 总体结论

Contrix 的方向是清楚的：它不是 chat-first，而是 space-first、object-first、repo-first 的协作协议。`Space / Room / Board / List / Card / Message / Morph / Relation / Event / View` 的核心分工有价值，尤其是：

- Card 与 Room 权限分离，避免把讨论权限错误继承到任务对象上。
- View 只是投影，不把 UI 状态伪装成协议真相。
- Repo、Sync、Index、Blob、Policy 分层，避免中心服务器成为唯一真相源。
- 对明文可见服务、E2EE、redaction、snapshot 验证、capability revoke 都有明确安全意识。

但当前规范最大问题是：概念已经展开到很大范围，而线级事实模型、命名、最小 profile 和机器 schema 还没有完全收敛。实际实现者会遇到“应该实现哪一个对象、以哪个 envelope 为准、哪些字段是 wire contract、哪些只是内部 canonical object”的问题。建议先冻结一个可实现的 v1 Core，再把 Agent、MIMI、Sovereign、Applet、WebRTC、Social 等放到独立 profile。

优先级判断：

- P0：统一 wire envelope、事件/操作命名、schema registry、operation registry。
- P1：给 `minimal_client`、`chat_only_client`、`kanban_only_client`、`principal_server`、`index_node` 提供最小可运行闭环。
- P2：补齐 security conformance vectors，尤其是 revoke freshness、snapshot trust、directory privacy、plaintext service enforcement。
- P3：为 UI / SDK 定义可直接消费的 projection DTO、error-to-UX 映射和 conflict 展示模型。

## 角色一：实际协议落地开发者

### 结论

协议目标很强，但当前落地成本偏高。实现者不仅要实现对象模型，还要同时理解 DID method、repo commit、canonical operation、operation envelope、event envelope、state event、auth refs、state resolution、snapshot、sync cursor、index projection、capability、policy server、plaintext service boundary、E2EE、directory、blob。若没有官方 reducer / SDK / reference server，很难保证不同实现互操作。

### 主要问题

1. Event / Operation / Canonical Operation 三层边界仍然会让实现者迷惑

`data-structures.md` 定义了 Event Envelope，并把 Canonical Operation Object 声明为 repo / SDK 内部内容寻址对象；`operations-sync.md` 又定义 Operation Envelope 作为 v1 默认 wire format；`federation.md` 表述为完整 Event Envelope 或等价 Operation Envelope。当前机器 schema 中有 `event-schema.json` 和 `operation.schema.json`，但 `operation.schema.json` 是 Canonical Operation，不是 wire Operation Envelope。

实现者会问：

- reducer 的唯一输入到底是 `event_id` 还是 `operation_id`？
- `prev_refs/auth_refs` 与 `causal.deps/authz_ref` 是两套字段还是一套映射？
- federation transaction 里到底传 Event Envelope 还是 Operation Envelope？
- commit 引用的是 canonical operation hash，还是 event envelope hash？

建议：v1 只保留一个 normative wire fact envelope，例如统一叫 `Event Envelope`，字段固定为 `event_id/kind/actor_id/actor_seq/prev_refs/auth_refs/content/proofs`。如果仍保留 `operation_id`，应明确它只是 `event_id` 的别名或派生字段，并给出唯一映射 schema。Canonical Operation 可保留为 SDK builder 内部格式，但不应进入互操作主路径。

2. 命名和枚举存在规范内漂移

已观察到的典型例子：

- Space membership 在 `event-auth-state-resolution.md` 中是 `cx.member.state`，但 `operations-sync.md` 标准 Operation Kind 又列出 `cx.membership.join/leave/kick/ban/unban/knock`。
- `data-structures.md` 中 `default_join_rule` 枚举包含 `invite`、`closed`，而 `event-auth-state-resolution.md` 的 `cx.space.join_rule` 使用 `private`。
- message 编辑在会话模型里是 `cx.message.revise`，capability 动作中出现 `cx.message.update` / `cx.message.update.own`。
- capability 示例使用 `grant_id` 与 `scope`，schema 使用 `id`、`actions`、`resources`。
- 对象 ID 前缀说明偏向 `cx:event`，schema pattern 又允许 `cx:evt`。

这些不是小问题。协议实现会围绕这些字符串做数据库索引、权限判断、schema validation、迁移、SDK 类型生成，一旦早期不统一，后续兼容成本很高。

建议：建立一个 `normative-ids.md` 或直接以 `schema-registry.md + operation-registry.json` 为唯一来源，所有文档示例都从 registry 生成或 lint 校验。

3. 机器可读 artifact 与正文不完全同步

`schema-registry.md` 包含 policy、invite、read marker、notification 等对象 schema，但 `artifacts/registry/schema-registry.json` 没有列出 `cx.schema.policy.v1` 和 `cx.schema.invite.v1`。`operation-registry.json` 只包含一部分服务操作，和 `service-http-binding.md` 的端点清单不一致。

建议：把 registry 反过来作为源文件，由脚本生成 Markdown 表格、OpenAPI 摘要和 conformance checklist。否则实现者无法判断 artifacts 是否可信。

4. 最小实现闭环仍然过大

`conformance-profiles.md` 已经意识到 MVP 分层，但 Core 仍然包含 DID/handle、Repo/Event、Space、Room、Board、List、Card、Message、Morph、Relation、Capability、Index query、Sync cursor、Blob hash、标准错误。对第一个实现来说，这仍然太大。

建议定义三个非常小的可运行闭环：

- `core_event_store`: DID proof + Event Envelope + Repo commit + idempotent submit/fetch。
- `chat_mvp`: Space + Room + Message + Room membership + message redaction + sync/backfill。
- `kanban_mvp`: Space + Board/List/Card + contains relation position + move/reorder + index projection。

每个闭环都必须有 fixtures、expected reduced state、错误响应和最小 HTTP binding。

5. Capability 模型正确但实现压力极大

授权流程包含 DID 解析、签名链、grant 展开、delegation cycle detection、selector、constraints、claim、trusted issuer、approval、revoke、policy server、fast path bitmap。规范还要求 chat/kanban 高频路径必须有 Authz Snapshot Bitmap 或等价缓存。

建议把 authz 引擎做成规范内的参考模块，提供：

- 标准 grant selector AST。
- constraint evaluation order。
- cache key 结构。
- revoke frontier 计算。
- `allow/deny/soft_fail/quarantine/require_review` 的确定性测试向量。

否则每个实现会做出不同的“近似 capability 引擎”。

### 对实现者友好的修订建议

- 先冻结一个 wire envelope，减少 Event / Operation 双轨。
- 为每个 profile 给一张“必须实现的 endpoint + event kind + schema + reducer”矩阵。
- 每个规范章节都明确：这是 canonical truth、derived projection、local/private state，还是 explanatory example。
- 提供 reference reducer 和 reference validator。没有它，state resolution 和 capability conformance 很难独立实现。
- 把所有示例 JSON 纳入 CI，至少校验必填字段、enum、ID pattern 和 schema id。

## 角色二：专业协议专家

### 结论

协议已经覆盖了许多安全边界：明文可见服务、snapshot 验证、DID key log、Room/Card 权限隔离、redaction 与 erasure 区分、MLS history sharing、Directory 隐私、federation destination binding 都有明确意识。主要风险不在“没有安全设计”，而在部分关键规则还不够可执行，容易被实现者解释成不同算法。

### 主要漏洞与风险点

1. Revocation 与离线写入的时间语义需要更硬

`event-auth-state-resolution.md` 说授权计算使用事件 `created_at` 对应的 auth state，而不是接收时间；`operations-sync.md` 又说若业务 operation 在 reducer 顺序上晚于 revoke，则必须无效。这里需要更精确，否则恶意客户端可尝试 backdate `created_at` 或操纵 HLC，让被撤销后的写入看似发生在撤销前。

建议：

- 授权有效性以 causal frontier / actor_seq / HLC monotonicity / commit inclusion time 共同判断，不能只依赖 `created_at`。
- 对 high-risk action 要求 revoke frontier freshness。
- 对离线写入设置最大可接受回溯窗口，或要求 pre-revocation lease / capability snapshot proof。
- 签名 proof 应覆盖 `actor_seq`、HLC、prev refs、auth refs 和 target resource。

2. State resolution 中的 `auth_weight` 需要形式化

当前 state resolution 排序包含 `auth_weight`：creator/admin capability 优先于普通 grant。但如果权重没有精确定义，会导致不同实现选出不同 winner，也可能导致权限膨胀。

建议定义：

- priority class 的完整枚举。
- 每类事件的权重计算函数。
- 当多个 admin / issuer / delegated grant 冲突时的 tie-break。
- 权重是否来自事件创建时 auth state，还是 resolution provisional auth state。

3. Snapshot trust 还需要防“授权签名者作恶”

规范要求 snapshot manifest 验证签名、state hash、frontier、chunk digest、签名者授权。这能防篡改，但不能防授权 snapshot issuer 生成一个“签名合法但 reducer 错误或故意遗漏事件”的 snapshot。

建议至少对高安全 profile 增加：

- snapshot 必须声明 input frontier 中的 event set commitment。
- 支持 challenge replay：客户端可抽样要求 issuer 提供某段 event inclusion proof。
- 多 witness / 多 index state hash 交叉验证。
- 对 conflict_records、soft_failed、quarantined 的摘要进入 snapshot manifest。

4. Unknown field preservation 与 critical extension 机制要落成机器字段

规范要求保留 unknown non-critical 字段，unknown critical feature fail closed。但目前缺少统一字段，例如 `required_features`、`critical_extensions`、`schema_profile_refs` 在 Event Envelope 内的具体位置。

建议：Event / Commit / Snapshot / Grant / Encrypted Envelope 都提供统一的 critical extension 声明方式，并纳入 digest。

5. Directory / private contact discovery 侧信道需要测试而不只是文字规则

文档要求不可见资源与不存在保持同形态，但实际泄露往往来自计时、分页数量、错误码、大小、缓存命中差异。

建议加入隐私回归测试：

- hidden Space resolve：不存在、存在但不可见、存在但 invite_only 三种响应形态一致。
- actor search：共同 Space、presence、组织成员关系不得影响未授权排名。
- private contact discovery：batch cardinality、错误 timing class、result count padding。

6. `did:uuid` 的时间戳对隐私有影响

`did:uuid` 使用 44 位毫秒时间戳。它利于排序和调试，但 pairwise/private DID 会泄露创建时间，可能成为跨服务关联信号。

建议：

- 对 pairwise/private DID profile 允许时间戳 bucket、随机偏移或不公开创建时间的替代方法。
- 明确 public DID 与 private DID 的 resolver / registry visibility 差异。

7. 明文可见服务规则需要强制 schema 和 conformance

`plaintext_visible_services` 是协议非常重要的安全边界，但目前它主要在正文中反复出现。实现时必须能机器判断“这个服务能否接收 message body / attachment preview / embedding / notification summary”。

建议：

- 为 plaintext visibility state event 提供 JSON Schema。
- 在 conformance 中加入“未列入服务拒绝明文请求”的测试。
- 所有 endpoint 的 request DTO 标注 plaintext class。

8. Agent 密钥与主人关系要更加保守

`encryption-and-audit.md` 中提到 Agent 初始私钥可由 Master 根种子 HD 衍生。这个做法会把主人根种子风险扩散到 agent 运行环境，并使 agent compromise 的恢复边界变复杂。

建议：

- Agent 默认使用独立 DID / 独立密钥，主人通过 capability delegation 和 controller approval 管理。
- HD 派生只能作为可选、强警告、高安全受控 profile，不进入基础 E2EE / Agent 规范主路径。

### 协议专家建议的优先修订

- 把 revoke freshness、HLC drift、offline write、actor_seq、commit inclusion 的关系写成确定性算法。
- 为 snapshot 增加 inclusion / omission 防护，至少在 high-assurance profile 中要求。
- 定义 critical extension 字段。
- 为 plaintext visible service、directory privacy、E2EE key sharing 增加 conformance vectors。
- 把 `auth_weight`、policy deny precedence、moderation quarantine 形式化。

## 角色三：最终软件用户

### 结论

如果实现得好，Contrix 对用户会很有吸引力：一个 Space 里可以同时有讨论、任务、看板、文档、Agent 运行记录和长期记忆，而且这些东西能互相引用、可审计、可迁移。用户会感到“同一个协作空间里，聊天不再和任务割裂”。

但用户不会关心 DID、repo、auth refs、state resolution、plaintext-visible services。他们只会感受到：

- 我能不能进来？
- 我为什么看不到这个 Room？
- 我的消息是不是安全？
- 我拖动卡片有没有成功？
- AI 到底代表谁在说话？
- 搜索为什么找不到旧消息？

当前协议若直接暴露底层概念，产品会显得复杂。

### 用户体验风险

1. Card 可见但 Room 不可见会让用户困惑

Card / Room 权限分离是正确的，但用户会看到“卡片上有讨论入口，却点进去无权限”。这需要产品用清晰状态解释：

- 你能看到 Card，但不能读这个 linked Room。
- 你可以请求访问。
- 这个 Room 是外部供应商、私密决策或安全评审 Room。

否则用户会认为软件坏了。

2. Invite、join rule、discoverability、history visibility 概念过多

协议区分 discoverability、join rule、history visibility 是必要的，但 UI 不应直接显示这些词。用户需要的是：

- 是否公开可搜。
- 是否需要邀请。
- 加入后能看到哪些历史。
- 是否端到端加密。

建议给产品层定义简化模板，例如：

- 公开社区。
- 邀请协作。
- 私密项目。
- 外部协作空间。
- 高安全空间。

3. E2EE 搜索和历史可见性会影响预期

用户会期待“我所有设备都能搜到所有消息”。但加密 Space 中全文搜索可能只能本地进行；新成员也不一定能解密加入前历史。产品必须明确显示：

- 本设备尚未建立本地索引。
- 旧历史未共享给你。
- 某些消息等待密钥恢复。
- 管理员是否允许加入前历史共享。

4. AI Agent 的边界必须非常可见

`my.md` 中提到的问题很关键：AI 是否知道主人的状态、是否只在主人不在线时回复、是否能使用主人或组织特有知识、主人不在群里时 AI 能否加入群组。

从用户角度，必须有几个硬规则：

- AI 不能默认知道主人的在线状态；在线状态应是 owner-private account data 或明确授权的 presence signal。
- AI 不能默认代表主人加入 Space；必须有显式 capability、scope、expiry、responsible actor。
- AI 使用个人知识、组织知识、Space 知识时，要显示来源边界。
- AI 产出的 memory 是私有、Space 共享，还是组织可见，必须在写入前可理解。
- 用户需要一个“AI 正在以谁的身份、用什么权限、能看到什么”的面板。

5. 冲突和最终一致性不能变成用户负担

离线写入、拖拽、并发编辑、redaction、revoke 都会产生 pending、soft fail、quarantine、conflict。用户不应看到协议术语，而应看到：

- 正在同步。
- 等待权限确认。
- 已撤回。
- 需要管理员审核。
- 与别人修改冲突，选择保留哪个。

### 用户眼中的优雅点

- Room、Card、Board 分离但能关联，符合真实协作。
- View 只是看法，同一数据能切成看板、表格、日历、图谱。
- Agent 不是外挂机器人，而是一等 Actor，可审计。
- Redaction 不承诺“全网物理删除”，这比虚假承诺更诚实。

### 用户体验建议

- 产品层提供少量 Space 模板，隐藏 discoverability/join/history 的底层枚举。
- 所有 linked object 显示访问状态：可读、仅 metadata、需申请、不可见。
- 所有 Agent 操作显示 responsible actor、grant scope、有效期、最近 run log。
- E2EE 场景明确展示本地搜索、历史共享和 decryption pending 状态。
- 冲突记录转成可操作 UI，不直接展示 reducer 术语。

## 角色四：界面 / App / 桌面 / Web 开发者

### 结论

协议很适合做强协作软件，但 UI 开发不会直接消费 raw Event。前端需要一个强 Index / AppView / SDK 层，把协议对象投影成稳定、分页、带权限解释、带冲突状态的 DTO。否则前端会被迫理解 reducer、auth refs、Room membership、Relation position edge、E2EE epoch、snapshot frontier，开发成本过高。

### 主要挑战

1. 看板位置不是 Card 字段，而是 Relation position edge

这是协议上正确的，但 UI 做拖拽时需要：

- 当前 Board/List/Card 投影。
- Card 当前 position relation id。
- rank。
- expected_position / CAS。
- move/reorder 后的 pending state。
- conflict loser 记录。

建议 `index/query` 的 board projection 返回标准 `CollectionProjectionResponse`，其中每个 item 至少包含：

- `object`
- `derived_position`
- `position_relation_ref`
- `rank`
- `container_ref`
- `permissions`
- `pending_operations`
- `conflict_records`
- `frontier`

2. View 定义很强，但需要 renderer contract

`View.kind=collection/timeline/graph/document/composite` 与 `renderer=board/table/calendar/gantt/chat/...` 的抽象合理，但前端需要知道每种 renderer 必须拿到什么字段。

建议为每种 projection 定义 DTO：

- Board / table / calendar / gantt 的 grouping、lane、item、cursor。
- Chat / thread 的 timeline、state_after、redaction、reaction、decryption state。
- Graph / tree 的 node、edge、lazy link、cross-space cutoff。
- Dashboard 的 widget data contract。

3. linked Room / Card 的权限裁剪会增加 UI 状态

一个 Card 可链接多个 Room，但用户不一定能读。UI 不能只展示房间标题和消息摘要，还要展示访问解释：

- `visible`
- `metadata_only`
- `exists_but_no_access`
- `hidden`
- `requestable`
- `e2ee_key_missing`

这需要 Index API 不仅返回数据，还返回 `visibility_explanation`。

4. Optimistic UI 与 causal wait 需要 SDK 支持

拖动卡片、发送消息、编辑标题都需要先本地乐观更新，再等待 repo commit、sync token、index wait-for。前端不应手写这些流程。

建议 SDK 暴露：

- `submitOperation() -> local_op_id, sync_token`
- `waitForProjection(sync_token, view_id)`
- `pendingStore`
- `conflictStore`
- `retry/backoff`
- `undo if rejected`

5. Timeline 渲染需要历史状态，不只是当前状态

`state_after` 的设计是正确的。消息历史中用户名称、权限、membership、redaction、reaction 都可能需要按事件当时状态解释。但 UI 一般习惯只拿当前 profile。

建议 timeline DTO 直接返回：

- event row。
- sender display snapshot。
- effective visibility。
- redaction state。
- reaction projection。
- state_after。
- missing_dependency / decryption_pending 标记。

6. Morph / facets 给 UI 插件带来灵活性，也带来 renderer 复杂性

未知 Morph type 要降级展示，但用户仍要能看懂标题、摘要、字段和关系。需要标准 fallback card/row/detail renderer。否则扩展对象会在客户端里变成不可读 JSON。

建议基础 UI contract 强制 Morph 至少提供：

- title path。
- summary path。
- primary fields。
- allowed renderers。
- action hints。
- schema-defined validation errors。

7. 错误码多，必须映射成人类动作

`capability_denied`、`stale_frontier`、`soft_fail`、`quarantine`、`schema_violation`、`sync_token_expired`、`epoch_mismatch` 都是合理错误，但 UI 需要统一动作：

- 重试。
- 重新同步。
- 申请权限。
- 进入审核。
- 重新登录。
- 等待密钥。
- 丢弃本地草稿。

建议增加 `user_action_hint` 或 SDK 错误分类，不要求每个 App 自己解释所有错误。

### UI 开发者希望协议简化的地方

- 不让 UI 直接处理 Event / Operation 双轨，统一 SDK 输入。
- Index projection 必须足够完整，前端不应从 raw Relation 自己还原看板。
- 权限解释作为 API 结果的一部分返回。
- 所有 profile 提供 TypeScript 类型和示例数据。
- 对常见应用给官方交互流程：发消息、拖卡片、建 Room、链接 Room、邀请成员、请求访问、处理冲突、AI 审批。

## 跨角色共同认为最应该改的地方

### P0：收敛唯一事实 envelope

必须明确：

- wire 上唯一事实对象叫什么。
- 唯一 ID 是 `event_id` 还是 `operation_id`。
- commit 引用哪个 hash。
- federation 传哪种 envelope。
- reducer 接收哪种 envelope。
- canonical operation 是否只是 SDK 内部格式。

没有这个收敛，互操作无法开始。

### P0：统一注册表和文档示例

需要一个单一 source of truth：

- event kind registry。
- service operation registry。
- object schema registry。
- enum registry。
- relation kind registry。
- capability action registry。

所有 Markdown 示例、OpenAPI、JSON Schema、fixtures 都应由它校验或生成。

### P1：把 MVP 变成可运行路径

建议第一阶段只验收：

1. DID resolve / proof。
2. repo submit/fetch commit。
3. Event validation。
4. Space create / member state。
5. Chat MVP：Room + Message + sync + redaction。
6. Kanban MVP：Board/List/Card + contains relation + move/reorder + projection。
7. Capability grant/revoke 最小集。
8. Blob hash upload/download。
9. Standard error / cursor / pagination。

其他能力作为 extension profile，不阻塞 v1 core interop。

### P1：提供 reference reducer / validator

协议中最难独立实现的是 reducer、authz、state resolution、redaction、snapshot validation。建议官方提供：

- `contrix-core-validator`
- `contrix-reducer-v1`
- `contrix-authz-v1`
- `contrix-test-vectors`
- `contrix-wire-types`

哪怕只是伪代码和测试 harness，也会极大降低实现分叉。

### P2：安全 conformance 补强

重点补：

- revoke freshness / backdated event。
- HLC future drift。
- auth refs 缺失与 backfill。
- snapshot omission。
- plaintext service violation。
- Directory hidden resource side-channel。
- E2EE history sharing。
- unknown critical extension。
- agent capability escalation。

### P3：为产品和 UI 定义友好抽象

协议可以复杂，但 SDK 和 projection 必须简单。建议定义：

- Access explanation object。
- Projection response DTO。
- Pending operation model。
- Conflict record UX model。
- Agent authority panel data。
- E2EE decryption/search state。
- Error-to-action mapping。

## 最终建议

Contrix 当前最有价值的部分是对象边界和安全边界，而不是扩展数量。下一步不建议继续新增能力，应该进入“规范收敛期”：

1. 停止扩大核心对象和服务面。
2. 统一 wire envelope 和命名。
3. 让 artifacts 成为规范机器入口。
4. 建立最小互操作 profile。
5. 用 reference reducer 和 fixtures 锁定行为。

完成这些后，Contrix 会从“设计完整但复杂的协议草案”变成“可以开始实现和互操作的协议”。
