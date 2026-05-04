# 服务端攻击模型与反制

## 1. 目标

本文件给出服务端可直接落地的威胁与防护。
所有条目均按 Contrix 的 Events API / Sync Service / Directory / Policy Server / Identity 平面映射到协议规则。

## 2. 服务端攻击面

### 2.1 当前协议可直接防御的攻击手段

1. **开放联邦入口滥用（Open Federation Abuse）**
   攻击者将未认证来源注入联邦传播路径，试图批量推送内容或索取状态资源。

2. **认证与凭证滥用（Credential Abuse / Brute-force / Session Token Replay）**
   对认证入口进行高频尝试，或利用泄露/重放的 session token、service token、gateway token 发起越权写入与批量操作。

3. **写入泛滥（Write Flood）**
   大量 `events.submit`、`push-operations`、`media.upload`、`call` 事务造成 CPU/IO/队列压垮。

4. **放大与重试风暴（Amplification / Retry Storm）**
   利用短周期失败、重试、回执链路放大或抖动，触发队列/重试池快速增长。

5. **来源身份伪造（Source Spoofing）**
   伪造 `origin` / `service DID` / transport 绑定签名，绕过来源约束。

6. **钓鱼与品牌仿冒（Phishing / Social Engineering）**
   通过目录、邀请、授权提示、签名展示链条进行误导，引导用户执行高风险动作。

7. **恶意附件与链接传播（Malware / Unsafe Media）**
   上传/分享高风险附件、链接、可疑 blob，诱导后续执行或传播。

8. **目录与枚举探测（Enumeration / Membership Probe）**
   利用返回时序、状态码差异推断隐私资源可见性、成员关系或组织结构。

9. **队列与存储耗尽（Queue / Storage Exhaustion）**
   借助大对象、分页滑动、深分页、历史清单拉取导致资源占用失控。

10. **中间人与重放（MITM / Replay）**
    传输层或协议层重放、顺序篡改、跨服务幂等键重用导致重复落库或越权生效。

11. **配置与权限误用（Policy Misconfiguration / Privilege Abuse）**
    allowlist/blacklist/secret 管理缺失，导致高敏入口被过度放开。

12. **服务拓扑污染（Topology / Service Discovery Poisoning）**
    篡改目录、`sync_endpoints`、`service_did`、`plaintext_visible_services`、官方组织/Space 背书引用，影响服务选择、传播路径与明文可见边界。

13. **身份解析污染（DID Resolver / Registry Tampering）**
    污染 DID resolver、registry、witness 可信链或 `did:web` 域绑定，错误承认身份控制权。

14. **历史冲突与 fork 影响（Fork / Duplicate Conflict）**
    利用重复 `event_id`、同 `event_id` 不同内容、frontier 分叉制造 state resolution 分支偏序。

15. **快照与快照块投毒（Snapshot / Snapshot Chunk Poisoning）**
    通过伪造 snapshot manifest、chunk/索引入口、签名链错误，劫持 bootstrap 或跳过一致性回放。

16. **跨域边界绕过（Cross-domain/Scope Confusion）**
    混淆 `space_id` / `service scope` / `destination` / `organization` 的绑定域，触发越权写入或错误可见性。

17. **邀请令牌与第三方身份绑定滥用（Third-Party Invite Abuse）**
    针对 `cx.invite.third_party` / `cx.invite.claim` 的 token 泄露、重放、并发认领进行滥用。

18. **会话成员与设备凭证滥用（Session/Device Credential Abuse）**
    复用未及时撤销的 device/session/gateway token 继续提交高敏操作、join、invite 或读取。

19. **加密状态回退与伪造（MLS Epoch Abuse）**
    通过 epoch 回退、非法 commit 顺序、已移除成员持有先前密钥继续参与解密相关流程。

20. **推送网关与通知元数据滥用（Push/Gateway Abuse）**
    攻击者利用未鉴权的 gateway 注册、metadata 推送接口、超频或伪造事件触发隐私侧信道或 DoS。

21. **URL 凭证泄露（URL Credential Leakage）**
    将 session token、API key 或签名材料放入 query string，导致浏览器历史、代理日志、崩溃日志、复制链接或 referrer 泄露。

22. **媒体侧信道探测（Media Header / Range Probe）**
    通过 `HEAD`、`Range`、`Content-Length`、`Content-Type`、`Content-Disposition` 或 redirect 差异推断私有 blob 是否存在、大小、类型或文件名。

### 2.2 当前协议中不成立的攻击项

- 回退重试链路细节（如不可控网关转发回路）
  该类机制不是本协议服务面的一部分。
- 基于主机级转发队列语义的网关信任模型
  协议仅依赖声明式服务发现与签名绑定，不使用该类网关转发语义。

### 2.3 通用防护手段

- **身份与来源前置验签**：服务来源先做服务 DID 绑定、签名验证、trust policy 检查，再执行业务授权。
- **分层限速与退避**：按来源、source service、space、IP hash、tenant、endpoint 限速，超过阈值退避或拒绝。
- **幂等与重放防护**：`request_id`、`txn_id`、`event_id` 与 canonical hash 绑定；`event_id` 重复但内容不一致 MUST reject。
- **统一错误语义**：未授权、不可见、未索引场景返回一致失败形态，避免侧信道。
- **认证材料不进入 URL**：受保护 endpoint 拒绝 query string / path 中的 token、API key 和签名材料；日志默认脱敏。
- **多源交叉校验**：snapshot / resolver / frontier / policy decision / DID 头部状态引入二次验证。
- **隔离与缓冲**：异常源先走 `quarantine` 与 `review` 决策，再决定 `allow`、`deny` 或 `reject`。
- **可追溯审计**：拒绝、退避、隔离、降级必须可审计（含 hash / hash chain / 决策签名）。
- **故障收敛策略**：`rate_limited`、`soft_failed`、`temporarily_unavailable` 与 `closed` 的优先级分层，不以单点服务脆弱性扩散给全域。

## 3. 对照：协议内映射与处理

| 攻击类型 | 成立性 | 对应改造 |
| --- | --- | --- |
| 开放联邦滥用 | 是 | `federation`/`service-surface` 的 Federation Allow List，`server ACL`，未签名来源走 `soft_deny`/`rate_limited`。 |
| 认证与凭证爆破 | 是 | `account-lifecycle` 与 auth 入口开启失败风控；`session/device token` 撤销与短TTL。 |
| 写入泛滥 | 是 | `policy-server` 风险码 + `rate_limit`，`per-source` 与 `per-space` 队列保护。 |
| 重试放大 | 是 | 窗口退避、批次阈值、失败率熔断，优先使用 `Retry-After`，并在 body 中提供 `retry_after_ms`。 |
| 来源身份伪造 | 是 | source DID / message-signature / service signature 验签链。 |
| 钓鱼 | 是/部分 | 需要可验证展示（service DID 与 policy 来源）与用户告警策略。 |
| 恶意载荷 | 是 | blob/mime/hash 扫描、危险标签隔离、`quarantine` 与人工复核。 |
| 枚举探测 | 是 | 目录/join/probe 接口统一 `not_found`/`forbidden` 时序与时延。 |
| 队列耗尽 | 是 | `quota_exceeded`、`rate_limited` 与短时限批量写保护。 |
| 重放 | 是 | `request_id` 与 canonical hash 绑定；`event_id` 重复且内容不同 reject；`duplicate_conflict`。 |
| 配置误用 | 是 | 变更审计、最小默认权限、fail-closed。 |
| 拓扑污染 | 是 | service list 与发现结果签名可验证，目录/Space 官方背书需双重签名。 |
| 解析污染 | 是 | resolver trust domain pinning，`did:web` 与 method adapter 证据核验。 |
| 冲突/分叉 | 是 | fork 检测、冲突源 quarantine + backfill re-check。 |
| 快照投毒 | 是 | snapshot manifest 与 chunk hash 链路签名、frontier 一致性双重校验。 |
| 跨域边界绕过 | 是 | source/destination/scope 每一层 must-bind 校验，禁止空域回退。 |
| 邀请令牌滥用 | 是 | token 一次性约束、过期窗口、绑定 proof 重放检测。 |
| 会话凭证滥用 | 是 | `account-lifecycle` 强制撤销链路、推送网关 token 与 service token 的短期有效策略。 |
| MLS epoch 滥用 | 是 | epoch monotonic、移除成员 fail-closed、提交顺序与 commit/proposal 校验。 |
| 推送网关滥用 | 是 | push gateway 注册与签发源鉴权，推送消息按最小必要字段。 |
| URL 凭证泄露 | 是 | 禁止 query string 认证，临时下载 URL 只能使用短时效、单用途、可撤销派生 token。 |
| 媒体侧信道探测 | 是 | 私有 blob 的 HEAD/Range/redirect 统一授权；不可见资源不返回大小、MIME、文件名或 Range header。 |

## 4. 协议规则完善（落地要求）

### 4.1 入口与服务面

- 所有服务入口区分 `authenticated`、`trusted_service`、`anonymous_forwarded`。
- `anonymous_forwarded` 来源不直通写入；默认进入 `rate_limited` 或 `quarantine` 流程。
- 所有统一错误语义在未认证/未授权/不可见场景保持不可区分。
- `request_id`、`request_canonical_hash`、`txn_id` 必须参与防重放判定；不同内容不得复用同一签名或请求键。
- 受保护 endpoint 不得接受 URL 中的认证材料；反向代理、应用日志和安全审计日志必须对敏感 query 做脱敏或拒绝记录。

### 4.2 Policy Server 侧

- `reason_code` 建议覆盖：
  - `spam_flood`
  - `auth_threat`
  - `spoof_like`
  - `malware_media`
  - `replay_suspect`
  - `invite_token_risk`
  - `session_token_risk`
  - `fork_risk`
  - `resolver_risk`
  - `topology_risk`
  - `snapshot_risk`
- `quarantine` / `require_review` 事件须保留 `request_id`、`canonical hash` 与决策签名，进入审查队列。
- 对 `push`/`join`/`directory` 的高风险 source 应触发 `rate_limit` + 侧信道统一返回策略。

### 4.3 联邦与传播

- `txn_id` 与 `canonical hash` 一致后才可幂等接受。
- 连续失败率升高的来源逐层下调优先级并退避；HTTP response 优先用 `Retry-After`，body 可附带 `retry_after_ms`。
- fork / frontier 异常进入 `quarantine` 并执行本地再校验，不直接进入主 reducer。

### 4.4 Blob / Media

- 私有 blob 下载、HEAD、Range 和 redirect 必须使用同一授权上下文。
- 不可见 blob 应返回与不存在资源一致的失败语义，不得通过 `Content-Length`、`Content-Type`、`Content-Disposition`、`Accept-Ranges` 或 redirect URL 暴露信息。
- 上传 MIME 与 filename 均为不可信 metadata；下载时 `Content-Disposition` 必须使用安全清理后的文件名，并对危险类型默认 `attachment`。

### 4.5 目录与发现

- 搜索 / 解析均先做最小可见性授权过滤后再返回结果；结果分页必须具备节流参数。
- `invite_only` / `secret` 不得因返回差异泄露存在性；未授权请求返回统一错误形态。

### 4.6 加密状态与通知

- `cx.mls` 提交需保留 `epoch`、`commit`、proposal 关系；移除成员不得解密后续事件。
- 推送网关仅接收最小唤醒元数据，禁止推送明文内容。

## 5. 相关文档

- `policy-server.md`（风险决策与 `reason_code`）
- `moderation.md`（blocklist / allowlist / quarantine）
- `federation.md` 与 `federation-wire.md`（联邦放行与签名验证）
- `api-conventions.md`（统一错误码与重放控制）
- `discovery-directory.md`（发现防枚举）
- `identity-did.md`（resolver trust）
- `snapshot-schema.md`（snapshot integrity）
- `third-party-invites.md`（邀请令牌生命周期）
- `account-lifecycle.md`（设备与会话撤销）
- `encryption-and-audit.md`（MLS epoch 与移除成员控制）
- `sovereign-deployment.md`（高安全部署收敛项）
