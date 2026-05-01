# contrix-spec Active TODO

> 更新日期: 2026-04-30
> 范围: Contrix v1 协议规范、机器可执行工件和跨实现一致性材料。中文规范为主规范文本，英文规范保持结构对齐。

## 0. 当前边界

- `contrix-spec` 是协议事实源，不承载具体服务端、客户端或 SDK 实现。
- 规范已覆盖 DID/handle、Space/Room/Board/List/Card/Message/Morph/Relation/Event/View、capability、repo/operation/sync、federation、blob/media、push、E2EE、applet、agent、WebRTC 和 conformance profile。
- 当前主要风险不是继续扩展概念面，而是缺少机器可执行 schema、OpenAPI/binding、fixture 和可自动认证的 conformance suite。

## P0: 机器可执行规范工件

目标: 让实现方可以从规范生成或校验相同的 wire contract。

- [x] 生成 JSON Schema 工件:
  - [x] `cx.space.*`。
  - [x] `cx.room.*`、`cx.board.*`、`cx.list.*`、`cx.card.*`、`cx.message.*`、`cx.morph.*`、`cx.relation.*`、`cx.view.*`。
  - [x] `cx.event.*`、`cx.operation.*`、`cx.commit.*`。
  - [x] `cx.capability.*`、grant constraint、resource selector。
  - [x] `cx.sync.*` cursor、snapshot、client sync response。
  - [x] `cx.blob.*`、encrypted envelope、media metadata。
  - [x] `cx.push.*`、notification、read marker、receipt。
  - [x] `cx.identity.*`、DID key-log、receipt、handle claim。
- [x] 生成 OpenAPI 3.1:
  - [x] Principal Server / repo / sync / index / blob / authz / device / federation endpoints。
  - [x] Identity Registry endpoints。
  - [x] Push Gateway `cx.push.notify` endpoint。
  - [x] coauth admin/account/OIDC integration endpoints。
  - [x] Sodmin admin API 依赖的 server/admin endpoints。
- [x] 固定非 HTTP binding 映射:
  - [x] WebSocket / SSE frame schema。
  - [x] gRPC service mapping。
  - [x] message queue envelope。
  - [x] libp2p / P2P envelope。
- [x] 统一错误与 header components:
  - [x] `not_found` 对不可见与不存在不可区分。
  - [x] `method_not_allowed`。
  - [x] `rate_limited` + `Retry-After`。
  - [x] `temporarily_unavailable`。
  - [x] 禁止 query string 认证。
  - [x] `X-Contrix-Request-Id`、`Idempotency-Key`、`X-Contrix-Wait-For`。

并行性: schema、OpenAPI、非 HTTP binding、错误 envelope 可由不同负责人并行推进，但必须共用同一 schema id / operation id registry。

## P0: Conformance Fixture

目标: `cotest`、SDK、服务端和客户端都能消费同一组官方向量。

- [x] Encoding fixture:
  - [x] canonical JSON。
  - [x] hash / digest。
  - [x] proof payload。
  - [x] HLC。
  - [x] cursor。
  - [x] fractional rank。
- [x] State resolution fixture:
  - [x] membership 并发。
  - [x] capability grant/revoke/delegate race。
  - [x] schema/policy update race。
  - [x] deterministic tie-breaker。
- [x] Redaction fixture:
  - [x] preserved fields。
  - [x] dangling redaction。
  - [x] late target event。
  - [x] audit visibility。
- [x] Capability fixture:
  - [x] resource selector grammar。
  - [x] constraint fail-closed。
  - [x] approval/proposal。
  - [x] claim/attestation revocation。
  - [x] delegation cycle and scope narrowing。
- [x] Sync fixture:
  - [x] initial / incremental sync。
  - [x] `state_after`。
  - [x] limited timeline + backfill。
  - [x] expired cursor。
  - [x] filter mismatch。
  - [x] to-device ack。
  - [x] snapshot manifest/chunk/frontier。
- [x] Federation fixture:
  - [x] HTTP Message Signature canonical request hash。
  - [x] origin/destination service DID mismatch。
  - [x] replay protection。
  - [x] fork quarantine。
  - [x] pull authorization。
- [x] Privacy/security fixture:
  - [x] private blob HEAD/Range anti-enumeration。
  - [x] push blind wakeup payload。
  - [x] pairwise DID resolve proof。
  - [x] encrypted payload forwarding without plaintext。

并行性: 每组 fixture 独立编写；统一由 `cotest` 接入并输出 profile coverage。

## P1: 规范一致性和发布剖面

- [x] 中英文结构一致性检查:
  - [x] 文件列表一致。
  - [x] section id / profile id / operation id 一致。
  - [x] 中文主规范新增 MUST/SHOULD 后，英文摘要及时同步。
- [x] Profile 收敛:
  - [x] minimal client。
  - [x] full client。
  - [x] e2ee client。
  - [x] enterprise client。
  - [x] principal server。
  - [x] identity registry。
  - [x] push gateway。
  - [x] applet service。
  - [x] agent runtime。
- [x] Production deployment profiles:
  - [x] personal node。
  - [x] small team。
  - [x] organization。
  - [x] high-security organization。
  - [x] isolated / sovereign network。
- [x] Federation hardening:
  - [x] service DID authentication。
  - [x] cross-domain Space join。
  - [x] policy decision exchange。
  - [x] quarantine / appeal / audit。
- [x] Directory/search/preview:
  - [x] exact resolve vs search semantics。
  - [x] encrypted Space search boundary。
  - [x] preview minimum disclosure。
  - [x] hierarchy query semantics。
- [x] Moderation/abuse:
  - [x] report schema。
  - [x] moderation queue schema。
  - [x] block/mute/hide/quarantine。
  - [x] server ACL。
  - [x] appeal and audit trail。

## P1: MIMI 草案借鉴落地

目标: 吸收 MIMI 最新草案中对 E2EE 联邦聊天有普适价值的机制，同时保持 Contrix 的 repo-first、Space-first 和 DID/capability 模型。

- [x] MLS-bound state root:
  - [x] `cx.mls.commit` 绑定 membership frontier、policy root、capability root、metadata hash 和 reducer profile。
  - [x] 接收端在 MLS transcript 与 Contrix accepted state 不一致时 fail closed。
- [x] KeyPackage claim lifecycle:
  - [x] KeyPackage 从“可公开拉取材料”收敛为 single-use `published -> claimed -> consumed | expired | revoked` 状态机。
  - [x] Claim 绑定 intended Space、requester、RequiredCapabilities、device trust 和 Welcome 路由引用。
- [x] Minimal-metadata encrypted Space:
  - [x] 增加 room-scoped pseudonymous MLS credential 和 E2EE identity link 规则。
  - [x] 服务端只看到 routing pseudonym，不默认获得真实 principal DID 映射。
- [x] E2EE moderation franking:
  - [x] 增加服务端不可读正文时的 message frank / delivery receipt 证明。
  - [x] 举报方可提交 plaintext + frank，审核方可验证内容曾被对应服务接收但不要求服务端保留明文。
- [x] Asset download privacy policy:
  - [x] Space policy 声明 direct、provider proxy、OHTTP/relay proxy 等下载路径。
  - [x] 私有附件下载不得因 direct fetch 泄露 IP、在线时间或 provider 关系，除非 policy 明确允许。
- [x] Policy components and history sharing:
  - [x] 将 role、preauth、asset、logging、bot、expiration、operational、history sharing 等策略组件化。
  - [x] 明确 history sharing 会削弱 forward secrecy，并绑定可分享角色、窗口和审计。
- [x] Connection identifier and private discovery:
  - [x] 区分 connection identifier、administrative identifier、display name 和 DID。
  - [x] 增加私密联系人发现 profile，避免目录服务同时看到 requester DID 与原始邮箱/手机号/用户名。
- [x] Message ID AAD visibility:
  - [x] 允许 Space policy 选择是否在 MLS AAD 暴露 opaque message/event id 以换取投递诊断能力。
  - [x] 隐私 Space 默认不暴露可跨服务关联的 message id。

## P1: MIMI 互操作支持落地

目标: 在不改变 Contrix core truth model 的前提下，提供可实现、可测试的 MIMI provider facade，使 Contrix Space / Room 能与 MIMI provider 互通。

- [x] 定义 `cx.profile.mimi_interop.v1`:
  - [x] 固定目标草案版本: `draft-ietf-mimi-protocol-06`、`draft-ietf-mimi-content-08`、`draft-ietf-mimi-room-policy-03`、`draft-kohbrok-mimi-identifiers-01`。
  - [x] 草案版本漂移时通过 profile version / draft pinning 处理，核心 Space version 不变。
- [x] 定义 MIMI Provider Facade:
  - [x] provider directory / describe 语义。
  - [x] hub / follower provider 与 Contrix Principal Server / Space Host 的映射。
  - [x] HTTP Message Signature、service DID、destination binding 和 Space policy 授权规则。
- [x] 定义 Room Binding:
  - [x] `cx.mimi.room_binding` 将 Contrix Space / Room 绑定到 MIMI room URI。
  - [x] 明确 canonical truth 仍是 Contrix signed Event / Reducer，MIMI room state 是互操作投影。
  - [x] 规定 MIMI participant / role / policy 与 Contrix membership / capability / policy components 的双向映射。
- [x] 定义 MIMI endpoint surface:
  - [x] `key-material`、`update`、`notify`、`submit-message`、`group-info`。
  - [x] `request-consent`、`update-consent`、`identifier-query`。
  - [x] `report-abuse`、`proxy-download`。
- [x] 定义内容转码:
  - [x] `cx.content.*` 与 `application/mimi-content`、`text/plain;charset=utf-8`、`text/markdown;variant=GFM-MIMI` 映射。
  - [x] reply、reaction、edit、delete、expiration、attachment、thread/card discussion 映射。
  - [x] 未能无损映射的 Contrix 内容以 proprietary alternative part 保留。
- [x] 定义身份、发现和 consent:
  - [x] MIMI URI / connection identifier / provider identifier 到 DID / handle / pairwise DID 的映射。
  - [x] consent state 与 Contrix private discovery / invite / presentation 兼容。
- [x] 定义 conformance 与机器工件:
  - [x] 新增 MIMI interop schema、fixture、profile manifest。
  - [x] 更新 operation registry、OpenAPI、non-HTTP binding。
  - [x] 中英文 spec map 与 extension 文档结构对齐。

## Cross-Project Contract Output

- `contrix-rust-sdk`: 消费 schema、operation registry、fixture，并提供 typed builders/validators。
- `soland`: 对照 Principal Server、repo、sync、index、blob、federation profile。
- `starid`: 对照 identity registry、DID key-log、receipt、resolver profile。
- `coauth`: 对照 auth/account server、session grant、claim/attestation、admin API profile。
- `floria`: 对照 push gateway notify profile。
- `chime`: 对照 push registration client helper profile。
- `chask`: 对照 client、E2EE、sync、identity、push UX profile。
- `sodmin`: 对照 admin OpenAPI 和 operational audit profile。
- `cotest`: 消费所有 fixture 并输出实现 coverage。

## 产出位置

- `artifacts/schemas/`：canonical JSON Schema registry。
- `artifacts/openapi/contrix-service-api.openapi.yaml`：统一 OpenAPI 3.1。
- `artifacts/bindings/non-http-bindings.yaml`：WebSocket / SSE / gRPC / MQ / libp2p 映射。
- `artifacts/fixtures/*.json`：encoding、state resolution、redaction、capability、sync、federation、privacy/security fixture。
- `artifacts/profiles/conformance-profiles.json`：实现与部署 profile manifest。
- `zh/en/conformance/schemas/`、`zh/en/conformance/fixtures/`、`zh/en/sync/*.yaml`：镜像输出。

## Definition of Done

- [ ] 每个新增 MUST/SHOULD 都有 schema、fixture 或明确不可测试原因。
- [x] 每个 endpoint 都有 operation id、request/response schema、错误 envelope 和安全要求。
- [ ] 每个 profile 都能被 `cotest` 或 SDK conformance runner 声明 pass/fail。
- [ ] 规范变更能同步到对应项目 `_todos.md` 的责任边界。
