---
title: 服务端攻击模型与反制
status: candidate
normative: true
stability: v1
updated: 2026-09-12
sidebar:
  label: 服务端威胁模型
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文件给出服务端可直接落地的威胁与防护。
所有条目均按 Arkret 的 Events API / Station sync surface / Directory / Identity 平面映射到协议规则。客户端侧的单一攻击面索引见 [architecture §6.7](../overview/architecture.md#67-客户端攻击面索引)。

## 2. 服务端攻击面

### 2.1 当前协议可直接防御的攻击手段

1. **开放联邦入口滥用（Open Federation Abuse）**
   攻击者将未认证来源注入联邦传播路径，试图批量推送内容或索取状态资源。

2. **认证与凭证滥用（Credential Abuse / Brute-force / Session Token Replay）**
   对认证入口进行高频尝试，或利用泄露/重放的 session token、service token、gateway token 发起越权写入与批量操作。

3. **写入泛滥（Write Flood）**
   大量 `self.events.command.submit`（含联邦 service-to-service 形态）、`media.upload`、`call` 事务造成 CPU/IO/队列压垮。

4. **放大与重试风暴（Amplification / Retry Storm）**
   利用短周期失败、重试、回执链路放大或抖动，触发队列/重试池快速增长。

5. **来源身份伪造（Source Spoofing）**
   伪造 `origin` / `service DID` / transport 绑定签名，绕过来源约束。

6. **钓鱼与品牌仿冒（Phishing / Social Engineering）**
   通过目录、邀请、授权提示、签名展示链条进行误导，引导用户执行高风险动作。
   **Realm alias 同形 / 抢注细分（与 [`discovery/object-addressing.md` §3.3](../discovery/object-addressing.md) 交叉引用）**:攻击者注册与目标 Realm alias 视觉同形（homograph / confusable）或抢注的 `<localpart>:<domain>` realm alias，借 `web+arkret:` 短地址 / `#alias` 分享链接诱导用户进入冒名 Realm。防护以 object-addressing §3.3「混淆防护」为权威——canonical equality 只比较 prepared localpart + lowercase A-label domain；registration authority 在自己的 realm-alias namespace 内使用固定版本 UTS #39 restriction-level / skeleton collision index，碰撞返回 `failed_precondition` `reason="realm_alias_homograph_forbidden"`，但 skeleton 不进入 wire equality。landing / handler 域名不是信任锚（object-addressing §5.1），客户端 MUST 以解析后的 canonical `realm_id` 为唯一信任锚。

7. **恶意附件与链接传播（Malware / Unsafe Media）**
   上传/分享高风险附件、链接、可疑 blob，诱导后续执行或传播。

8. **目录与枚举探测（Enumeration / Membership Probe）**
   利用返回时序、状态码差异推断隐私资源可见性、成员关系或组织结构。
   **Consent / PSI oracle 细分**：PSI 命中位翻转时刻可泄露 grant/revoke 时序，跨 requester 稳定的裸 consent-state hash 可被离线枚举并关联 holder。防护以 [`identity/consent-model.md` §6.1.1 / §6.2.2](../identity/consent-model.md) 为权威：per-`(requester, holder)` 限速与 bucket 化、holder 可审计访问记录，以及 audience-bound opaque response。

9. **队列与存储耗尽（Queue / Storage Exhaustion）**
   借助大对象、分页滑动、深分页、历史清单拉取导致资源占用失控。

10. **中间人与重放（MITM / Replay）**
    传输层或协议层重放、顺序篡改、跨服务幂等键重用导致重复落库或越权生效。

11. **配置与权限误用（Policy Misconfiguration / Privilege Abuse）**
    allowlist/blacklist/secret 管理缺失，导致高敏入口被过度放开。

12. **服务拓扑污染（Topology / Service Discovery Poisoning）**
    篡改目录、member ActorId、service resolution、`plaintext_visible_services`、官方组织/Realm 背书引用，影响账号选择、传播路径与明文可见边界。

13. **身份解析污染（DID Resolver / Registry Tampering）**
    污染 DID resolver、registry、witness 可信链，或 `did:web` / `did:webvh` 的域绑定与 `did.jsonl` 托管，错误承认身份控制权。**默认 method 是 `did:webvh`**，其 hosting 方 split-view 与历史截断只被部分缓解，见 §2.1a。

14. **历史冲突与 fork 影响（Fork / Duplicate Conflict）**
    利用伪造的 `event_id` / canonical bytes 不匹配、完整 hash collision evidence、actor over-fork 或竞争确认凭证制造普通状态错误、错误 authority-commit query basis 或安全域停摆。合法的普通并发写由 Station 在该 stream 上串行化为单值，被取代不等于 quarantine；仍获权的作者可以靠高频重写反复抢占当前值，这是需限速、审计和最终撤权的数据完整性/资源残余风险。两个互不可达 confirmed RealmCommit 是共识安全故障，不能作为普通可合并冲突；接收方必须按安全域故障停摆。

15. **快照与快照块投毒（Snapshot / Snapshot Chunk Poisoning）**
    通过伪造 snapshot manifest、chunk/索引入口、签名链错误，劫持 bootstrap 或跳过一致性回放。

16. **跨域边界绕过（Cross-domain/Scope Confusion）**
    混淆 `realm_id` / `service scope` / `destination` / `organization` 的绑定域，触发越权写入或错误可见性。

17. **邀请令牌与第三方身份绑定滥用（Third-Party Invite Abuse）**
    针对 `ak.invite.third_party` / `ak.invite.claim` 的 token 泄露、重放、并发认领进行滥用。

18. **会话成员与设备凭证滥用（Session/Device Credential Abuse）**
    复用未及时撤销的 device/session/gateway token 继续提交高敏操作、join、invite 或读取。
    **授权 revoke proposer 的 pending DoS**：持有 `ak.device.revoke` authority 的主体可提交一条合法 revoke Event，使 exact device generation 在 authority transaction 完成前进入 `revocation_pending`，统一阻断 session grant、KeyPackage claim、to-device write、Event write 与普通 live 提交。该可用性影响是 revoke authority 的显式组成部分。缓解边界是：(a) 未获 authority 的 caller 在读取 device-private state 前即不可区分地拒绝且零写入；(b) accepted Event、exact authority/device/generation 与 pending index 原子持久化；(c) 只有该 transaction 的 terminal rejected result 可解除 pending；(d) 多个 transaction 独立计数，reject 一条不清另一条；(e) governance health / recovery 告警暴露长期积压。部署必须用独立恢复授权、审计与 signer rotation 管理该残余风险。

19. **加密状态回退与伪造（MLS Epoch Abuse）**
    通过 epoch 回退、非法 commit 顺序、已移除成员持有先前密钥继续参与解密相关流程。
    **Last-resort KeyPackage 残余暴露**：复用 init/encryption key 会削弱 Welcome 阶段前向保密；私钥在轮换前泄露可解开此前由该包封装的 Welcome。边界与缓解以 [`crypto-media/encryption-and-audit.md` §2.6.2](../crypto-media/encryption-and-audit.md) 为权威：强制轮换、上线后对相关 group self-update、`expires_at` ≤ 30d，且 high-security / sovereign profile 禁用。

20. **推送网关与通知元数据滥用（Push/Gateway Abuse）**
    攻击者利用未鉴权的 gateway 注册、metadata 推送接口、超频或伪造事件触发隐私侧信道或 DoS。
    **推送侧信道细分（与 [`discovery/push-notifications.md` §2.2 / §2.4 / §5.1](../discovery/push-notifications.md) 交叉引用）**:具体威胁向量包括——(a) **collapse / dedup key 跨 window 关联**:provider 可见的 collapse / dedup key 若跨 delivery window 稳定，可关联同一目标的连续 wakeup，还原活动模式；防护见 push-notifications §2.4「Provider 侧 collapse / dedup key 约束」(跨 window 不可链接随机值，MUST NOT 直接用 `source_event_digest` / event id / Realm id 等稳定派生)。(b) **push timing oracle**:在用户刚上线 / 离线瞬间发出可被 provider 观察的 per-event push burst，使 presence 成为精确 timing oracle；防护见 push-notifications §2.4(按 Realm policy bucket 粒度，默认 ≥ 60s 批处理 / 延迟)。(c) **`push_target_id` 可链接性**:伪名若可跨 Realm / Station 关联即成行为追踪点；防护见 push-notifications §2.2(per-(account_id, device_id, push_route) pairwise pseudonym，keyed salt 派生，跨上下文不可复用)。(d) **counts 活动侧信道**:明文绝对未读数让 provider 重建累计活跃度画像；防护见 push-notifications §5.1(blind_wakeup 下 counts MUST NOT 携带明文绝对未读数，改用布尔 / 增量 / bucket)。(e) **`is_direct_message` / `member_count` DM 关系图重建**:push rule 的 server-side 条件 `is_direct_message` 与 `member_count` 要求 Station sync surface 读取精确成员数与"是否双人私聊"，在 E2EE Realm 中构成成员数与私聊存在性侧信道；叠加 push timing 可近似重建"谁在和谁私聊"的 DM 关系图。防护见 push-notifications §4.3「`is_direct_message` / `member_count` 在 E2EE / 高隐私 Realm 的侧信道收口」为权威(`member_count` 仅暴露 bucket 化值、口径同 discovery §3；`is_direct_message` 受 Realm policy gate，`minimal-metadata` Realm MUST 关闭并降级为 §4.5 client-side 评估)。

21. **URL 凭证泄露（URL Credential Leakage）**
    将 session token、API key 或签名材料放入 query string，导致浏览器历史、代理日志、崩溃日志、复制链接或 referrer 泄露。

    *受控例外：`ak.self.blob.command.presign.v1`* — 为兼容浏览器原生标签（`<img src>` / `<video src>` 等无法附 Authorization header）允许由 blob service DID 签发的 pre-signed URL 通过 `?presign=<envelope>` 携带认证。该例外受 §5.4 [`crypto-media/media-and-blob.md`](../crypto-media/media-and-blob.md) 严格收紧：TTL ≤ 1h、单 blob、只读、可撤销、不得用于 E2EE 附件；envelope 内不得包含可重用 credential；服务端用 audit log 追踪签发。**除此一个明确登记的例外外，本威胁项规则不变**：session token / refresh token / capability grant / device key 等任何长期或可重用凭证仍 MUST NOT 进入 URL。

22. **媒体侧信道探测（Media Header / Range Probe）**
    通过 `HEAD`、`Range`、`Content-Length`、`Content-Type`、`Content-Disposition` 或 redirect 差异推断私有 blob 是否存在、大小、类型或文件名。

23. **联邦流量模式旁观（Federation Traffic-Pattern Observer）** —— *conditional：base v1 不直接防御，仅在声明 `ak.profile.traffic_metadata_hardened.v1` 时缓解（见 §2.1a）。*
    即使 Event body、MLS payload 与 service signatures 都正确，联邦 peer、网络运营方或受托 relay 仍可能通过 fanout 时间、batch 大小、重试节奏、provider 组合和跨 Realm burst 关联组织活动。base v1 不提供针对该侧信道的直接防御。高隐私部署 SHOULD 声明 `ak.profile.traffic_metadata_hardened.v1`（profile 定义见 [`conformance/conformance-profiles.md` §11.1](../conformance/conformance-profiles.md)）；一旦声明，该部署 MUST 使用 OHTTP / relay indirection / decoy traffic 之一，并对批处理 padding、发送延迟抖动、固定大小 federation batch、retry cadence padding 和 blind / batch wakeup 执行该 profile 的可测试参数。未声明该 profile 时，不得把 E2EE 误表述为隐藏 federation traffic metadata。

24. **出站 URL / SSRF（Server-Side Request Forgery）**
    攻击者通过 DID Document serviceEndpoint、媒体 URL、snapshot chunk、Webhook、Applet/Agent endpoint 或联邦 peer discovery 引导服务访问 loopback、私网、link-local、metadata endpoint 或内部控制面。

25. **Directory ingest 写路径滥用（Directory Ingest Abuse）**
    攻击者污染 Directory 的发现 / 投影 ingest 写路径（与 [`discovery/discovery-directory.md` §8.10 / §11](../discovery/discovery-directory.md) 交叉引用）。具体向量:**announce replay**(重放过期 announce 让陈旧条目复活)、**`as_of` skew**(伪造 `as_of` 时间使旧状态看似最新)、**policy_revision rollback**(回退 policy_revision 绕过更严策略)、**DID hijack**(劫持 announce 来源 DID 冒名注入条目)、**source-ref 伪造**(伪造来源引用让未授权条目进入 directory)、**takedown spoofing**(伪造下架 / takedown 让合法条目被移除)。防护以 discovery-directory §8.10 / §11 的来源 DID 验签、`as_of` 单调 / 时间锚校验、policy_revision 单调、announce 一次性 / 过期窗口、source-ref 授权核验与 takedown 授权链为权威。

26. **实时活动信号去匿名追踪（Real-time Activity-Signal Deanonymization）**
    攻击者（外部 world-readable 观察者、受托 Station sync surface 或共谋成员）订阅并关联实时活动信号——read receipt（`ak.receipt.read`）已读位置、typing（`ak.typing`）逐键活动、presence（`ak.presence` 的 `dnd` / `idle` / bucket 化 `last_active_at`）、push wakeup timing，以及 reaction routing tag 在同一 `routing_window` 内的频率分布与等值聚类——以重建特定 actor 的活动时间序列、作息画像，甚至去匿名其阅读 / 输入 / 反应行为。这些信号单独看是产品功能，关联后成为去匿名 timing / equality oracle。防护以各自正文为权威：read receipt 的 world-readable / forced-public 组合 fail-closed 与 fanout 收口见 [`discovery/read-receipts.md` §2.5.1](../discovery/read-receipts.md)；typing 的 world_readable scope fail-closed 与 presence `dnd`/`idle` 对未授权观察者 MUST 降级见 [`discovery/profiles-presence.md` §3.4 / §3.5](../discovery/profiles-presence.md)；push wakeup bucket 化见 [`discovery/push-notifications.md` §2.4](../discovery/push-notifications.md)；reaction tag 按 Event 已签 `created_at` 派生一小时 `routing_window`，但绝不要求每小时 MLS Commit，见 [`crypto-media/encryption-and-audit.md` §2.9](../crypto-media/encryption-and-audit.md)。Mention recipient/token/sidecar 不属于 v1，mention 保持在 ciphertext 中并走 blind/batch wakeup。

27. **实时媒体 / SFU 信任边界滥用（Media-Plane Abuse）**
    恶意或被攻陷的 token issuer、SFU/MCU、TURN 服务或 recording/transcription backend 可能注入未授权 participant、伪造 `participant_id` / frame-key 来源、静默把 `media_service_decrypts` 从 false 降级为 true、滥用短期 TURN credential、把 backend 明文产物绕过 Arkret blob pipeline，或通过 room join/leave timing 与包大小重建会议参与图谱。防护以 [`crypto-media/media-service-binding.md` §3/§7/§8](../crypto-media/media-service-binding.md)、[`crypto-media/webrtc-signaling.md` §3a/§5/§10](../crypto-media/webrtc-signaling.md) 与 [`crypto-media/call-state.md` §4/§5](../crypto-media/call-state.md) 为权威：participant admission 必须同时验证 membership/account/device/capability 与 signed binding；远端 SFU 默认不得获得 exporter key；任何 backend 明文访问必须通过三层 governance gate；TURN credential 必须短期、audience/focus/call 绑定；录制/转写只经 Arkret authenticated encrypted-blob pipeline。任一校验不可得 MUST fail closed。即使内容 E2EE，SFU/relay 仍可观察 room timing/size；实现 MUST 在 UI/policy 披露该残余元数据面，minimal-metadata profile SHOULD 做 bucket/padding/短留存。

28. **生成式正文预览滥用（Streaming Preview Abuse）**
    恶意 sender 可用 `ak.message.stream` 高频大帧消耗 recipient 内存/渲染资源、用不同
    `stream_id` 制造同 attempt 分叉、发送危险 markdown，或展示诱导性 preview 后提交不同
    final。Signal 强制密文只隐藏精确 kind/target，不隐藏外层 sender、scope、时间与大小模式。
    防护以 [`sync/signal.md` §7](../sync/signal.md#7-message-正文流式预览-payload-profile) 为权威：
    producer/receiver 执行 16 KiB、5 fps、8 streams、10 min 上限；分叉冻结；markdown 按不可信
    富文本消毒；final 始终覆盖 preview，UI MUST NOT 把 preview 标成已提交内容。service 只执行
    64 KiB envelope、外层 byte/rate/backpressure 和 scope admission，不得通过解密建立产品级
    stream 状态。

### 2.1a 需 profile 才能缓解的攻击项（base v1 不直接防御）

§2.1 中以 *conditional* 标注的条目不属于 base v1 可直接防御范围，只有在显式声明对应 hardening profile 时才能缓解。本节是 conditional 项的索引，缓解手段与 normative 约束（含「未声明 profile 时 MUST NOT 把 E2EE 误表述为隐藏 federation traffic metadata」）以被索引条目正文为权威，不在此重述：

- **#23 联邦流量模式旁观** —— 详见 §2.1 #23 正文；profile 定义见 [`conformance/conformance-profiles.md` §11.1](../conformance/conformance-profiles.md)（`ak.profile.traffic_metadata_hardened.v1`）。
- **Sender 元数据对承载服务可见（acknowledged residual exposure，informative）** —— v1 baseline 接受 Event Envelope 顶层 `actor_id` 对承载它的 Station / Station sync surface **始终明文可见**（见 [`sync/operations-sync.md` §14](../sync/operations-sync.md) 字段可见性分级把 `actor_id` 列为路由 / 签名归属元数据）。即"谁在何时给谁发"对受托承载服务可观测，base v1 不提供 sender-anonymity 通道。这是 acknowledged residual exposure，与 #23 联邦流量旁观同属"承载服务可见的元数据面"；未来加固方向（committed-sender 风格的对中转服务隐藏 `actor_id` 通道、OHTTP / oblivious relay 提升为 event-submit / push / directory 的可选元数据隐私基线）列为未来 profile，不在 v1 core。实现 MUST NOT 把 E2EE 正文加密误表述为隐藏 sender 元数据。

- **Last-resort 私钥事后泄露** —— 已捕获 Welcome 在包到期后仍可被匹配私钥解密；expires_at 只限制新分发，不能撤销历史密文。未来 epoch 的恢复依赖攻击者未知的新秘密和 MLS 恢复条件；更新不恢复旧明文保密性。高安全 / sovereign profile 禁用该回退，Realm affinity 保持强制。见 [encryption-and-audit §2.6.2](../crypto-media/encryption-and-audit.md)。

- **认证组件局部失陷** —— Account Authority 是 Station 认证 TCB 内部职责，不是独立 wire role。认证 TCB 内按事实 owner 分责：事实 owner 对冻结输入完成完整验证，内部消费者通过已认证且完整性受保护的通道承接该 exact 结果，并仍逐次检查本次完整 AccountId、audience、operation、intent、状态版本、有效期与自身业务权限；状态变化后的 current gate（撤销、fence、expiry、设备与成员准入）继续执行，它不是对同一冻结输入的重复验签。分析 MUST 明确未失陷方，不能把下列能力合并：
  - IdP 失陷但 Authority/Station 诚实时，攻击者可冒用受该 IdP 管理且映射到本站的 subject；绑定账号只可取得 holder-bound 受限恢复会话及 pre-proof 闭包，不能跳过 accepted-device proof 或恢复 policy。策略可见性限于该账号，不等于枚举任意本站用户；首次抢先绑定只适用于尚未绑定的 service account，不能覆盖既有 principal/PCR。见 [account-lifecycle §2.1.2](../identity/account-lifecycle.md)。
  - 仅 issuer signing key 泄露但 ledger 与认证内省仍诚实时，伪造 JWT 签名不等于创建 active ledger record：唯一权威是 issuer ledger 中与提交 token 绑定的 exact credential record，没有 active 的该 exact record MUST 拒绝。资源服务器消费该 exact 内省结果，不重建 signed claims 或派生 ID，并继续验证 audience、holder DPoP 与 current gate；改写 holder/scope/audience 后重新签名的 token 不是账本内的完整凭据，按 jti 命中或本地验签成功都 MUST NOT 放行。因此「仅 issuer key 泄露」仍被挡在 active 会话之外。若攻击者还控制被接受的 status，则已越过此假设，属于下一项。见 [key-management §6](../identity/key-management.md#6-session-grant)。
  - Authority/ledger/status authority 被控制但 Station 业务准入仍诚实时，会话签发、账号状态和认证新鲜度失去可信性；攻击者可能建立指向其 holder 的账号会话，访问各 operation 与当前业务授权允许的数据或滥用恢复 pre-proof 面。此半径不是所有非 E2EE 数据，也不自动批准 Agent pairing：后者仍须 controller producer 签名、合法 RealmCommit 与 durable activation。恢复 policy 的任一方法必须另获对应授权，服务身份不提供该授权。
  - 以上各项不产生攻击者未持有的用户/root/device 签名或既有 E2EE/backup 解密密钥；也不保证错误认证/治理结果无法诱导未来错误授权。整个 Station 被控制时适用下项，不能继续假设其准入验证诚实。
- **首次接入与认证权威替换** —— 普通客户端按 [server-trusted-results §1.2](../sync/server-trusted-results.md#12-普通客户端的-station-接入normative) 从明确选择/独立预配 origin 接入并持久比较身份和认证配置。选错 origin、预配渠道或受信 WebPKI/origin 失陷是残余暴露；正常证书验证仍防御仅控制网络的主动攻击者。首次 pin 不能追溯证明初始选择正确，describe 自洽不能成为独立身份背书。部署内 Account Authority 的首次接纳同样以明确配置的 exact Station origin 为网络信任起点，但不要求另行预配 service ID：只有 TLS/egress policy 与完整 WebVH history、`AuthenticatedServiceResolution`、role/core/endpoint/freshness 验证全部成立，才能原子耐久 pin 身份与 history floor。public Describe 或 shared secret 单独不能建立身份；并发冲突、不同 core/genesis、history rollback、endpoint continuity 验证失败、`stations[]` 首个元素、redirect 或网络错误都不得替换已有 binding。依赖不可达或返回 503 时业务面 fail closed 并可重试完整验证，不得退化为自报信任或用首个候选顶替目标；身份替换只能走具名、审计的显式高风险恢复操作。
- **治理方、受托恢复方与 runtime 宿主失陷** —— [architecture §6.0](../overview/architecture.md#60-参与方关系矩阵) 分别界定其权限。唯一治理方失陷可产生错误结论，不保证都以可检测分叉表现；合法恢复服务可滥用既有整账号恢复授权，但不自动取得历史密钥；runtime 宿主影响其实际持有的全部 Agent key/秘密，不保证仅单 Agent 受损。
- **运营方/管理员滥权** —— 管理身份仅在已授权 operation 内生效；可用性、元数据及合法可见明文可能受影响。export、retention/hold、quarantine 与恢复分别按领域合同，不附赠 E2EE 密钥或用户签名。运营者控制整站的情形适用下项，不把 MUST NOT 误表述为恶意服务器不可实施的动作。
- **自己 Station / 同源 registry 失陷** —— personal_node 允许 registry 与 Station 同源。普通客户端信任自己的 Station 提供治理与身份授权结果，不承诺独立检测其任意 registry equivocation 或伪造的历史。客户端仍核对自己提交的账号、设备/DID 公钥、inception 和待签字节，保留私钥 possession、内容认证及既有带外设备信任；这些检查不等于重放完整 DID/PCR 历史。服务间接纳外部 DID 的验证与独立 witness/auditor 仍适用；同源运营者失陷属于治理可信边界失陷，不能声称客户端会自动通过 pin 恢复真实历史。见 [服务器信任与结果消费](../sync/server-trusted-results.md)。
- **base v1 不要求 consistency proof** —— 证明 log append-only、历史未被改写的 consistency proof 只在 `high_security_organization` 与 `sovereign_deployment` profile 是 MUST；base v1（含 `small_team` / `organization`）以离散 witness 签名为准，不要求 log-backed transparency。因此"历史未被截断"在默认部署下不可由协议独立证明。

### 2.2 当前协议中不成立的攻击项

- 回退重试链路细节（如不可控网关转发回路）
  该类机制不是本协议服务面的一部分。
- 基于主机级转发队列语义的网关信任模型
  协议仅依赖声明式服务发现与签名绑定，不使用该类网关转发语义。

### 2.3 通用防护手段

- **身份与来源前置验签**：服务来源先做服务 DID 绑定、签名验证、trust policy 检查，再执行业务授权。
- **分层限速与退避**：按来源、source service、realm、keyed IP digest、tenant、endpoint 限速，超过阈值退避或拒绝。

  > **不可链接限速配套方向（informative，路线图注记，2026-06 评审采纳；不落地 v1）**：现状反滥用主要依赖按来源 / IP hash 限速，而协议在多处推动 OHTTP / relay 路由的不可链接化（见 §2.1 #23、`conformance/conformance-profiles.md` §11.1 的 `ak.profile.traffic_metadata_hardened.v1`，以及 push / preview / blob 下载等 relay 化入口）。流量越走 relay，IP 维度限速越失效，运营方被迫在「放松限速」与「破坏不可链接性」之间二选一。作为该张力的配套方向，本注记登记 **Privacy Pass**（RFC 9576 架构 / RFC 9577 HTTP 认证 scheme `PrivateToken` / RFC 9578 token 签发协议；rate-limited issuance 见 draft-ietf-privacypass-rate-limit-tokens）作为 relay 化 pre-auth 面（OHTTP blob 下载、匿名 preview / peek、3PID claim 等）的**不可链接限速**配套路线。客户端可在不暴露稳定 IP / 身份的前提下向 origin 出示匿名 token，使 origin 在保持来源不可链接的同时仍能限速。本注记**不预注册 token type 或 profile id**；落地需先设计 issuer / attester 信任模型（谁签发、谁背书、何种 attestation），故 v1 仅作占位登记、不落地，不引入新 normative 规则。
- **幂等与重放防护**：`request_id`、`Idempotency-Key`、`event_id` 与 canonical hash 绑定；`event_id` 重复但内容不一致 MUST reject。
- **统一错误语义**：未授权、不可见、未索引场景返回一致失败形态，避免侧信道。
- **认证材料不进入 URL**：受保护 endpoint 拒绝 query string / path 中的 token、API key 和签名材料；日志默认脱敏。
- **验证角色分工**：首次接纳外部材料、治理 Station和独立审计者按其领域合同验证 snapshot、resolver、checkpoint、policy 与 DID 状态；治理结果消费 Station按 [authority_commit-profiles §9](../sync/authority-commit-log.md) 认证 exact 治理结果证明，不被要求重放无关历史。普通客户端按 [server-trusted-results §1–§3](../sync/server-trusted-results.md) 核对请求、意图、已知身份与 E2EE，不执行泛化二次治理验证。
- **隔离与缓冲**：异常源先走 `quarantine` 与 `review` 决策，再决定 `allow`、`deny` 或 `reject`。
- **可追溯审计**：拒绝、退避、隔离、降级必须可审计（含 hash / hash chain / 决策签名）。
- **故障收敛策略**：`rate_limited`、`soft_failed`、`temporarily_unavailable` 与 `closed` 的优先级分层，不以单点服务脆弱性扩散给全域。
- **出站网络目标策略**：任何由外部输入导向的 URL、endpoint 或 service discovery 结果都必须在连接前执行 CIDR / 地址类别 / redirect / DNS rebind 检查。

### 2.4 传输层后量子姿态

> **PQ-hybrid TLS 传输层姿态（威胁论据真相源）**：本节给出该姿态的威胁论据；规范义务的 canonical 表述在 [`../sync/transport-bindings.md` §5](../sync/transport-bindings.md)。生产 v1 的 federation / service-to-service / client-service TLS 1.3 连接 SHOULD 支持并优先协商混合后量子 key exchange group `X25519MLKEM768`（`draft-ietf-tls-ecdhe-mlkem-05`；IANA TLS Supported Groups codepoint 已注册，主流浏览器与 OpenSSL 3.5+ 已默认部署）。`ak.profile.high_security_organization.v1`、`ak.profile.sovereign_deployment.v1` 及继承它们的 profile 下，相关连接 MUST 协商 `X25519MLKEM768`，对端不提供时 MUST fail closed。default profile 可回落到经典 TLS 1.3，但必须记录未协商 PQ 的 transport posture，且不得宣称该连接具备 Harvest-Now-Decrypt-Later resistant transport。该姿态把 `crypto-media/encryption-and-audit.md` 既有 PQ 路线图（informative，HNDL / Harvest-Now-Decrypt-Later 优先）对 Harvest-Now-Decrypt-Later 的缓解，扩展到**仅靠 TLS 保护、不进 MLS / E2EE**的传输面——联邦 transaction 元数据、public plaintext Realm 内容、directory / sync 流量。该要求零 wire 字段成本、不触碰任何 wire 字段或 envelope `scheme` / `version`：握手在 TLS 层协商，与请求级 RFC 9421 签名正交，不改 Arkret wire envelope / schema / object model。高安全 / sovereign conformance 验证为 **deployment-profile 握手探针**：握手完成后检查协商出的 TLS named group 是否等于 `X25519MLKEM768`，并验证对端不提供时 fail closed，而非 object-model conformance vector。
> 部署交叉引用：传输绑定 canonical 表述见 [`../sync/transport-bindings.md` §5](../sync/transport-bindings.md)；联邦链路见 [`../sync/federation.md` §3.2](../sync/federation.md)；sovereign / 高安全部署的探针落地见 [`../sync/sovereign-deployment.md` §3 / §11](../sync/sovereign-deployment.md)。

## 3. 对照：协议内映射与处理

| 攻击类型 | 成立性 | 对应改造 |
| --- | --- | --- |
| 开放联邦滥用 | 是 | `federation`/`service-surface` 的 Federation Allow List，`server ACL`，未签名来源走 `soft_deny`/`rate_limited`。 |
| 认证与凭证爆破 | 是 | `account-lifecycle` 与 auth 入口开启失败风控；`session/device token` 撤销与短TTL。 |
| 写入泛滥 | 是 | `rate_limit`，`per-source` 与 `per-realm` 队列保护。 |
| 重试放大 | 是 | 窗口退避、批次阈值、失败率熔断，优先使用 `Retry-After`，并在 body 中提供 `retry_after_ms`。 |
| 来源身份伪造 | 是 | source DID / message-signature / service signature 验签链。 |
| 钓鱼 | 是/部分 | 客户端按 object-addressing 与 architecture §6.7 展示 canonical 身份、目标与用户意图；治理来源由自己 Station 的 scoped 结果确认。展示与带外核对仍是客户端职责，不保证识破所有社会工程。 |
| 恶意载荷 | 是 | blob/mime/hash 扫描、危险标签隔离、`quarantine` 与人工复核。 |
| 枚举探测 | 是 | 目录/join/probe 接口统一 `not_found`/`forbidden` 时序与时延。 |
| 队列耗尽 | 是 | `quota_exceeded`、`rate_limited` 与短时限批量写保护。 |
| 重放 | 是 | `request_id` 与 canonical hash 绑定，异内容复用返回 `duplicate_conflict`；Event 先重算 content-addressed `event_id`，carried ID 不匹配以 `event_id_digest_mismatch` 拒绝，真正 full-hash collision 以 `witness_disagreement` 隔离。 |
| 配置误用 | 是 | 变更审计、最小默认权限、fail-closed。 |
| 拓扑污染 | 是 | 实际接纳/审计角色按 [discovery-directory §8.10 / §11](../discovery/discovery-directory.md) 验来源签名、source-ref 与背书授权，按 service-surface §2.6 验服务路由；普通客户端按已登记 Station 结果消费。不定义通用双签载体。 |
| 解析污染 | **部分** | resolver trust domain pinning、method adapter 证据核验、SCID 自证与 entry hash chain、freshness profile 的同步刷新或 fail closed。**默认 `did:webvh` 部署对 hosting 方 split-view 与历史截断不构成完整缓解**——witness 在 base v1 可选、consistency proof 仅高保障 profile 要求，见 §2.1a 的两条 residual risk。 |
| 冲突/分叉 | **部分** | hash collision 与 actor over-fork 按各自可验证规则 quarantine；普通合法写入保留历史并由该 stream 的接纳次序收敛为单值，不能仅因陈旧或已被取代隔离。已授权恶意作者仍可写恶意内容、延长分支或消耗资源，依靠限速、审计、撤权与数据基准关闭缓解。 |
| 快照投毒 | 是 | snapshot manifest 与 chunk hash 链路签名、checkpoint 一致性双重校验。 |
| 跨域边界绕过 | 是 | source/destination/scope 每一层 must-bind 校验，禁止空域回退。 |
| 邀请令牌滥用 | 是 | token 一次性约束、过期窗口、绑定 proof 重放检测。 |
| 会话凭证滥用 | 是 | `account-lifecycle` 强制撤销链路、推送网关 token 与 service token 的短期有效策略。 |
| MLS epoch 滥用 | 是 | epoch monotonic、移除成员 fail-closed、提交顺序与 commit/proposal 校验。 |
| 推送网关滥用 | 是 | push gateway 注册与签发源鉴权，推送消息按最小必要字段。**推送侧信道**:collapse/dedup key 跨 window 不可链接、presence push timing bucket 化(默认 ≥60s)、`push_target_id` pairwise 不可跨上下文关联、blind_wakeup counts 不携带明文绝对未读数(见 §2.1 #20 与 [`discovery/push-notifications.md` §2.2 / §2.4 / §5.1](../discovery/push-notifications.md))。 |
| Directory ingest 滥用 | 是 | announce 来源 DID 验签、`as_of` 单调 / 时间锚、policy_revision 单调防回退、announce 一次性 + 过期窗口、source-ref 授权核验、takedown 授权链(见 §2.1 #25 与 [`discovery/discovery-directory.md` §8.10 / §11](../discovery/discovery-directory.md))。 |
| URL 凭证泄露 | 是 | 禁止 query string 认证。**单一登记例外**：`ak.self.blob.command.presign.v1` 签发的 pre-signed URL 通过 `?presign=` 携带 server-issued、短时效（≤1h）、单 blob、只读、可撤销的签名 envelope（见 §2.1 #21 与 [`crypto-media/media-and-blob.md` §5.4](../crypto-media/media-and-blob.md)）；E2EE 附件 ciphertext fetch MUST NOT 使用此机制。 |
| 媒体侧信道探测 | 是 | 私有 blob 的 HEAD/Range/redirect 统一授权；不可见资源不返回大小、MIME、文件名或 Range header。 |
| 实时媒体 / SFU 滥用 | 是 | participant binding + membership/account/device/capability 分层 admission；`media_service_decrypts` 三层 governance gate；sender-bound exporter key；TURN credential call/focus/audience 绑定；backend artifact 强制 Arkret encrypted-blob pipeline（§2.1 #27）。 |
| 出站 URL / SSRF | 是 | [`sync/api-conventions.md`](../sync/api-conventions.md) §11.2 的出站网络目标策略；DID、联邦、媒体、snapshot、Webhook、Applet/Agent endpoint 统一做私网/metadata 地址拒绝、DNS rebind 防护和 redirect 复核。 |

## 4. 协议规则完善（落地要求）

### 4.1 入口与服务面

- 所有入口 MUST 按 [service-http-binding §2.2](../sync/service-http-binding.md#22-端点契约规则) 及各 operation 的认证、授权、披露、限流和失败合同执行；namespace、认证机制与业务权限不得混用。匿名或转发来源不因路径/代理身份取得写权，也不得绕过已登记 operation 的失败语义另建通用 quarantine 准入。
- 所有统一错误语义在未认证/未授权/不可见场景保持不可区分。
- `request_id`、`request_canonical_digest`、`Idempotency-Key` 必须参与防重放判定；不同内容不得复用同一签名或请求键。
- 受保护 endpoint 不得接受 URL 中的认证材料；反向代理、应用日志和安全审计日志必须对敏感 query 做脱敏或拒绝记录。

### 4.2 风险与 moderation 求值

- 风险 `reason_code` 的取值以
  [`../../artifacts/registry/error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 为机器真源。
- `quarantine` / `require_review` 事件须保留 `request_id`、`canonical hash` 与决策签名，进入审查队列。
- 对 `push`/`join`/`directory` 的高风险 source 应触发 `rate_limit` + 侧信道统一返回策略。

### 4.3 联邦与传播

- `Idempotency-Key` 与 `canonical hash` 一致后才可幂等接受；单事件级别仍以 `event_id` 去重。
- 连续失败率升高的来源逐层下调优先级并退避；HTTP response 优先用 `Retry-After`，body 可附带 `retry_after_ms`。
- fork / checkpoint 异常进入 `quarantine` 并执行本地再校验，不直接进入主 reducer。
- 解析 federation peer endpoint、DID Document service entry 或 backfill/snapshot URL 前，必须先执行出站网络目标策略；命中私网、loopback、link-local 或 metadata 地址时 fail closed，不得进入重试风暴。

### 4.4 Blob / Media

- 私有 blob 下载、HEAD、Range 和 redirect 必须使用同一授权上下文。
- 不可见 blob 应返回与不存在资源一致的失败语义，不得通过 `Content-Length`、`Content-Type`、`Content-Disposition`、`Accept-Ranges` 或 redirect URL 暴露信息。
- 上传 MIME 与 filename 均为不可信 metadata；下载时 `Content-Disposition` 必须使用安全清理后的文件名，并对危险类型默认 `attachment`。
- SFU/MCU/token issuer 在每次 join、token refresh 与 participant notification 上必须重验 signed participant binding、membership/account/device/capability；不得只信 backend 自报 identity。
- 默认 E2EE binding 不得把 exporter key 发送给远端媒体服务。只有 `media_service_decrypts=true` 经 policy component、`plaintext_visible_services` 与 MLS governance binding 三层同时授权后才可发送，且该事实必须成员可见。
- TURN credential 必须短期、单 call/focus/audience 绑定并限速；backend-generated recording/transcript 必须经 Arkret authenticated encrypted-blob pipeline，禁止直出 URL 或云存储旁路。

### 4.5 目录与发现

- 搜索 / 解析均先做最小可见性授权过滤后再返回结果；结果分页必须具备节流参数。
- `invite_only` / `secret` 不得因返回差异泄露存在性；未授权请求返回统一错误形态。

### 4.6 加密状态与通知

- `ak.mls` 提交需保留 `epoch`、`commit`、proposal 关系；移除成员不得解密后续事件。
- 推送网关仅接收最小唤醒元数据，禁止推送明文内容。

## 5. 相关文档

- `../governance/content-moderation.md`（blocklist / allowlist / quarantine）
- `../sync/federation.md`（联邦放行与签名验证）
- `../sync/api-conventions.md`（统一错误码、重放控制与出站网络目标策略）
- `../discovery/discovery-directory.md`（发现防枚举）
- `../identity/identity-did.md`（resolver trust）
- `../conformance/realm-state-snapshot-schema.md`（snapshot integrity）
- `../sync/third-party-invites.md`（邀请令牌生命周期）
- `../identity/account-lifecycle.md`（设备与会话撤销）
- `../crypto-media/encryption-and-audit.md`（MLS epoch 与移除成员控制）
- `../sync/sovereign-deployment.md`（高安全部署收敛项）
