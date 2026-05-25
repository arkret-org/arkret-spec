---
title: 从 Matrix 迁移到 Contrix
status: candidate
normative: false
stability: v1
updated: 2026-05-25
---

> 本文档原位于 `overview/matrix-core-differences.md`，于 2026-05-24 迁移到 `guides/` 并改名为 `migrating-from-matrix.md`。读者群从"协议概览读者"调整为"已熟悉 Matrix 并计划迁移或对接的实现者"，定位更准确。

## 1. 目标

本文旨在说明 Contrix 与 Matrix 的核心设计差异，阐明 Contrix 为何不是 Matrix 的直接变体，更非对其 room / homeserver / appservice 等概念的简单换名或重写。

## 2. 总体结论

Matrix 的核心抽象是 **room + event graph + homeserver federation**，重点服务实时通信、群聊、桥接和开放联邦。

Contrix 的核心抽象是 **signed Event + per-actor event chain + Realm + Space + Flow + Message + Morph + Relation + View + capability**，其中 Realm 是 security boundary、Space 是结构容器（Board / List / 等），重点服务可审计的协作对象、任务、看板、agent 协作和多视图投影。

因此二者可以互联或桥接，但协议根不同。

## 3. 核心差异表

| 维度 | Matrix | Contrix |
| --- | --- | --- |
| 数据根 | Room 内事件流与 room state。 | Realm 内授权 Event 集合，归约为 Realm、Flow、Message、Morph、Relation、View；看板与列容器是独立的 Space 对象（`cx:space:`），永远住在某 Realm 内。 |
| 主要用途 | 即时通信、群聊、VoIP 信令、桥接通信网络。 | 协作对象、任务/看板、聊天/话题、agent 协作、审计工作流。 |
| 服务器模型 | Homeserver 是用户账号、room 参与和联邦传播的核心服务。 | Principal Server 是 principal 控制或显式委托的服务边界；Events、Sync、Blob、Policy 分层。 |
| 真相源 | Room event graph 与状态解析。 | Actor/device/service 签名 Event Envelope，加上 Realm reducer；搜索和 View projection 都是派生层。 |
| 身份 | Matrix user ID 绑定 homeserver 域，如 `@alice:example.org`。 | Principal 使用 DID 作为协议主键；`@alice:example.org` 这类标识可作为 handle、登录入口或 bridge alias，但不能作为权限主体。 |
| 服务迁移 | 账号和 room 与 homeserver 域耦合较强。 | 身份、Event 发布链与服务 endpoint 分离，DID / handle / service delegation 支持迁移。 |
| 授权模型 | Room auth rules、membership、power levels。 | Capability grant、constraint、claim、policy、deterministic authorization。 |
| 扩展集成 | Application Service 主要由 homeserver 注册，按 user / room alias namespace 和 transaction 工作。 | Applet 是可签名、可授权、可审计的 service DID，可按 Realm、Actor、对象范围、用户授权和 capability 细分。 |
| AI agent | Bot 可作为用户或 appservice 接入，但不是协议根对象。 | Agent 是一等 principal / Actor，可签名 Event，并拥有 capability 和 protocol session。 |
| 外部 agent 协议 | 无原生 A2A / ACP handoff 语义。 | A2A / ACP / MCP bridge / custom agent API 可作为受控 agent protocol session。 |
| E2EE | 当前 Matrix E2EE 基于 Olm / Megolm。 | Contrix 推荐 MLS RFC 9420 作为群组 E2EE 基础。 |
| 查询与视图 | 客户端主要从 sync、state、relations、聚合 API 还原体验。 | View 是一等投影定义；搜索和 projection 默认由客户端本地派生，不能成为真相源。 |
| 明文服务边界 | Homeserver 和 appservice 的明文可见性依赖部署、加密和桥接配置。 | 非 E2EE 私有内容必须只进入 principal 或 Realm policy 明确委托的服务；明文可见服务用 `plaintext_visible_services` 声明。 |

## 4. 核心概念对比深化

### 4.1 Applet 与 Appservice

Matrix Application Service 是成熟的桥接机制，适合让 homeserver 与外部系统或 bot 服务通信。它的核心是 homeserver 侧注册、namespace、transaction、query 和 ping。

Contrix Applet 的差异不是简单“更强”，而是粒度不同：

- Applet registration 是签名声明，可由 Realm owner、Organization、registry 或 authz service 接受。
- Applet 不因 namespace 自动获得权限；每次写入仍需 capability。
- 同一个 Applet 可以被不同 Realm 用不同 capability、不同可见性、不同对象范围启用。
- 不同用户或组织可以在自己控制的 Realm 中启用不同 Applet，但必须受 Realm policy 和授权约束。
- Applet 可作为 bot、bridge、ghost actor controller、portal Realm manager、delegated agent / device 参与审计链。

因此 Contrix 的优势是 **Realm / principal / capability 级别的可组合授权与审计**，不是无条件允许任何用户随意给任何 Realm 安装 Applet。

### 4.2 AI 与 agent 支持

Matrix 可以通过 bot、appservice 或 bridge 接入 AI，但 AI 不是 Matrix 的协议根对象。Contrix 从对象模型开始就把 agent 纳入：

- agent 可以是 principal、Actor、capability subject。
- agent 输出可以写入 Message、Flow、Morph 或 Relation。
- agent 权限必须窄范围、短时效、可撤销、可审计。
- agent-to-agent 场景可以显式升级到 A2A / ACP / MCP bridge / 企业私有 agent API，并将 session、status、artifact、result 回写 Contrix。
- Contrix 只要求协作事实、授权边界、审计摘要和最终结果进入协议账本，不要求把每个 token 或 tool call 都强制写成 durable Event。

### 4.3 身份系统的演进

Contrix 的身份与发布模型借鉴 atprotocol 的几个方向：

- DID 是稳定身份根，handle 是可变入口。
- handle 需要双向验证。
- DID Document 用于服务发现和 key discovery。
- 每个 actor 通过 `actor_id`、`actor_seq` 和 `prev_refs` 形成可验证 event chain。
- signed Event Envelope 是发布单元，服务器不能伪造 principal 写入。

这不要求普通用户直接看见或管理 DID。客户端和服务端 MAY 提供类似 Matrix 的 `@user:domain` 体验，把它作为联系人搜索、登录名、组织 handle 或桥接 alias；在提交持久 Event、grant 或 MLS membership 前，必须解析或绑定到 principal DID。

但 Contrix 不等同于 atprotocol：

- atprotocol 主要面向公开 record 与 PDS；Contrix 面向多方协作 Realm、授权状态、私有内容、E2EE 和企业治理。
- Contrix v1 core 默认普通用户身份方法是 `did:webvh`（提供可审计 DID 控制历史，抵御 DNS / TLS 单点失陷），同时支持 `did:web`（service DID / `personal_node` profile）和 `did:key`（bootstrap / 设备）。`did:pkh`（钱包）、`did:plc`（AT Protocol interop）、KERI 等 method 作为 interop extension profile 提供，不属于 v1 core 互操作必需。
- Contrix 的 Event 记录协作事实，不是公开内容分发 record。
- Contrix 把 Realm policy、capability、Applet、Agent、MLS 和受托明文服务边界都纳入同一协作协议边界。

### 4.4 E2EE 架构选择

Matrix 的 Olm / Megolm 生态成熟、部署广泛、客户端实现经验丰富。Contrix 选择 MLS RFC 9420，是因为它更适合作为新的群组 E2EE 基础：

- MLS 是 IETF 标准。
- MLS 原生建模 group state、epoch、commit、proposal、member add/remove。
- Contrix 可以把 MLS epoch 与 Realm membership、history visibility、device authorization、auditable E2EE 直接绑定。
- 被移除成员必须在新 epoch 上 fail closed。

因此，Contrix 选择了 **更现代、标准化、适合动态群组协作治理的 MLS 基础**，而不是沿用 Matrix 的 Olm / Megolm。

### 4.5 Device 密钥层级与生命周期

§4.4 只覆盖了群组 E2EE 算法的选择。但 device-key 是一整套包含身份密钥、prekey、群组密钥、cross-signing、备份、推送、验证状态机的体系。Matrix 在这套体系上有成熟实践（参见 [Matrix E2EE guide](https://matrix.org/docs/matrix-concepts/end-to-end-encryption/) 与 [Megolm spec](https://spec.matrix.org/unstable/olm-megolm/megolm/)），Contrix 在保留多数原语形状的同时，把身份根换到 DID method、把 E2EE 换到 MLS、并把若干在 Matrix 中相对耦合的语义拆开规范化。本节按原语逐项对照。

#### 4.5.1 设备级身份密钥与信任根

| Matrix | Contrix | 说明 |
| --- | --- | --- |
| Device Ed25519 fingerprint key | `cx:device:` 记录里的 `verify_key` (Ed25519) | Contrix 把 device 公钥写进 `cx:device:` 记录（详见 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §4），并由 `cx.device.authorize` Event 锚定到 principal DID，而非 homeserver 账号。 |
| Device Curve25519 identity key | `cx:device:` 记录里的 `hpke_key` (X25519) | 用于 HPKE-based to-device 通道、KeyPackage init key 来源、加密 backup envelope 接收。Matrix Curve25519 用于 Olm 长期 DH，语义对等但用途窄一些。 |
| (homeserver 账号绑定) | DID method controller / inception key | Contrix 在 master 密钥之上多一层：DID method 的初始控制材料（`did:webvh` entry-0 controller、`did:plc` rotation key、KERI inception 等）是身份根。principal signing key 必须进入 DID method history / key log，而不是 homeserver 内部状态。详见 [`identity/key-management.md`](../identity/key-management.md) §5.0。 |

#### 4.5.2 Prekey 与会话引导

| Matrix | Contrix | 说明 |
| --- | --- | --- |
| `/keys/upload` Curve25519 OTK | `POST /api/v1/keys/upload` 的 `one_time_keys` | 语义一致，用于非 MLS 加密或 MLS 引导。`claim` MUST 原子消费一次性 key。 |
| Fallback key | `fallback_keys` 字段，`fallback=true` 标记 | Contrix 规范要求成功建立会话后尽快轮换；Matrix 行为类似但描述较弱。 |
| (Olm OTK 同时承担群组成员引导) | MLS KeyPackage 独立 claim API | Contrix 把 MLS KeyPackage 从 OTK 池里拆出来：`/api/v1/keys/keypackages/{upload, claim, consume, revoke}`，新增 **`required_capabilities` ⊆ KeyPackage `capabilities` normative subset rule**，并对 claim 失败做反枚举（统一返回 `claim_failed`）。Matrix 无对应概念。 |

#### 4.5.3 群组消息密钥

| Matrix | Contrix | 说明 |
| --- | --- | --- |
| Megolm outbound session（per-sender ratchet） | MLS exporter / application key per epoch | Contrix 没有 per-sender Megolm session；群组密钥状态由 MLS group state、epoch、KeyPackage 演进。 |
| Megolm inbound session 缓存 | MLS group state + epoch material 写入 `mls_epoch_cell`、`key_schedule_cell`、`covered_frontier_cell` | epoch 被 lattice cell 显式承载，governance 状态通过 §6.5 的 MLS Governance Binding 与 MLS transcript 哈希绑定。 |
| Megolm Ed25519 签名（per-message） | MLS application message 内嵌签名 + MLS transcript | 完整性来自 MLS 标准；不再额外维护 per-message Megolm 签名链。 |

#### 4.5.4 Cross-Signing 与信任视图

Contrix 沿用 Matrix 的三层 cross-signing 结构（[`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5）：

| 角色 | Matrix | Contrix |
| --- | --- | --- |
| 用户身份根 | Master key | `principal_signing_key`，轮换 MUST 进入 DID method history / key log |
| 签名本账号所有设备 | Self-signing key | `self_signing_key`（存 secret storage，跨设备共享） |
| 签名其他用户身份 key | User-signing key | `user_signing_key`（同上） |

差异：Contrix `principal_signing_key` 的演进绑定到 DID method 链（`did:webvh` entry、`did:plc` operation 等），不是 homeserver 内部状态；`self_signing_key` / `user_signing_key` 在 cross-signing reset 时整条信任链置为 `needs_reverification`，并需要 DID 控制证明、recovery 解锁、设备 quorum 签名或受信账户恢复服务签名之一。

线级形态：SSK / USK 公钥与 PSK 绑定通过 `cx.cross_signing.publish`（[`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5.1）公布到 principal control stream；每条 `cx.device.authorize` 在 `content.cross_signing_binding` 中携带 SSK 对设备 `verify_key` 的签名（§5.2），并显式声明 `ssk_generation`。Reset 写 `cx.cross_signing.reset`（§14.1），`new_generation = previous_generation + 1`，并必须在 `cx.profile.cross_signing.reset.v1` 的 `parameters.publish_recovery_window_seconds` 窗口内发布对应 publish，否则接收方对该 `new_generation` 的 device authorization MUST 拒绝。验证 transaction 检测到 reset 时以 `code=cross_signing_reset` 取消，对应 §10.6 / §14.3 cancel code。

#### 4.5.5 Secret Storage 与 Key Backup

| Matrix | Contrix | 说明 |
| --- | --- | --- |
| Secure Secret Storage（SSSS）统一保管 cross-signing / megolm backup 等 | `cx.secret_storage.v1`（**client-local only**）+ wire 上传走 `cx.schema.key_backup.v1` | Contrix v1 不再把 secret storage envelope 作为 wire 格式；服务端只接受 `cx.schema.key_backup.v1`，每条 backup MUST 声明 `backup_class`。 |
| 一把 backup key 覆盖所有 secret 类别 | **域隔离**：`did_recovery` / `secret_storage` / `mls_history` / `external` 四类 `backup_class`，各自独立 KDF info、HKDF 子密钥、AEAD AAD、wrap key | 防止"一把口令同时控制身份签名和 E2EE 历史"。`self_signing_key` / `user_signing_key` 与 MLS group secrets backup key 必须分到不同 envelope 或不同 subdomain key。详见 [`identity/key-management.md`](../identity/key-management.md) §7。 |
| 一把 recovery key 解锁 SSSS | recovery key + 门限 / 社交恢复 share | Contrix 把 recovery 表达为 `recovery_policy`，可声明 threshold、share holder、有效期、approval 条件；share holder 不自动获得读取内容能力。 |
| (Matrix 未明确约束) | "能解密某段历史" MUST NOT 单独作为账号所有权证明 | Contrix 显式禁止把解密 oracle 当成 DID 控制证明，并定义了固定格式、限速、绑定 audience / service DID 的 challenge 流程。 |

#### 4.5.6 Push 通道密钥

Matrix pusher 把 (user, device, push token) 映射作为 push gateway 可见标识符，没有跨设备 / 跨通道 / 跨 Realm 的不可链接性规范。Contrix 在 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5a 引入 `push_target_id`：

- per `(recipient_service_did, principal, device, push_route)` 伪名；至少 128 bit 熵，推荐 256 bit。
- MUST NOT 由公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码推导。
- 同一 principal 在不同 `recipient_service_did`、两台设备或同一 device 的两条 push_route 上的 `push_target_id`，对 push gateway / vendor / 第三方 transport MUST 不可关联。
- gateway / vendor 不得保留可逆映射；被 member delivery binding 授权的 Sync Service 仅可在本服务上下文内持有运行时索引，轮换或失效后旧伪名不得被服务端链接回当前 `(recipient_service_did, principal, device)`。
- 推送 payload 必须是 `encrypted-envelope.schema.json` 形态或等价 ephemeral encrypted blob；gateway / vendor 不得解密。

#### 4.5.7 Contrix 新增的密钥类别

以下密钥类别在 Matrix 中没有显式协议层定义（属于实现侧或 appservice 侧约定），Contrix 在 [`identity/key-management.md`](../identity/key-management.md) §3 中作为一等协议原语：

- **Session key（`cx.session.grant`）**：浏览器、OIDC、SSO、远程执行环境的短期会话密钥。MUST 绑定 audience / origin / service / scope / 过期时间；不得签发长期 device grant、不得访问 E2EE 历史密钥。资源服务器仍 MUST 重新验证 DID control state，而不是把 OIDC 成功视为 DID 控制证明。
- **Agent key**：AI agent / bot / CI / automation 的一等密钥类型，MUST 有 scope、`expires_at`、accountable actor 绑定，SHOULD 用 proposal / approval 约束高风险动作。Matrix bot 复用 user / appservice token，没有这一层 scope/审计要求。
- **Applet delegated device key**：Applet 代表 ghost actor 或桥接用户参与 E2EE 时，使用受限的 delegated device 密钥；`device_id` MUST 标记 `applet_id`，capability MUST 限定 Realm / 协议 / 动作 / 有效期，**且 delegated device 不得签发新的人类 device**。to-device 权限只覆盖其 namespace 内 actor。Matrix appservice 的 ghost user 没有 device-level 委托语义。
- **Inception key**：DID method 层的初始控制密钥，是 principal control realm genesis 与首台 `cx.device.authorize` 的信任根。使用后 SHOULD 立即写入 DID method 轮换链中并从首台设备销毁，或作为 recovery share 存入 secret storage；MUST NOT 长期作为日常 device signing key。

#### 4.5.8 验证 / 登录 / 设备授权的语义解耦

Matrix to-device 验证（SAS / QR）成功后，客户端实现常常顺势把设备视为"已信任、已授权"，登录与设备授权也较多耦合在 homeserver 的 `/login` 路径上。Contrix MUST 严格分开三件事（[`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §1.2）：

| 操作 | Contrix 允许产出 | Contrix MUST NOT 自动产出 |
| --- | --- | --- |
| 登录因子验证（密码 / passkey / OIDC / SSO） | 短期 `cx.session.grant`、触发 recovery、请求已授权设备授权 | 长期 device、`cx.device.authorize`、E2EE 历史密钥访问 |
| 设备授权 | `cx.device.authorize`、DID key-log operation、`cx.device.list_update`、MLS Welcome 资格 | 仅凭密码 / SSO 通过即视作设备授权 |
| 设备密钥验证（SAS / QR） | `user_signing_key` 签名（跨 principal）、本地信任标记 | 长期 device grant、Realm capability、登录态 |

验证消息形状（`cx.key.verification.{request, ready, start, accept, key, mac, done, cancel}`）与 Matrix 一致，但 Contrix 进一步规范化：

- `request.expires_at` MUST 不晚于 `timestamp + 10m`；用户 2 分钟未交互 SHOULD 本地取消。
- SAS transcript MUST 绑定双方 principal id、device id、verify key、transaction id、method、算法选择、双方 ephemeral key 与待验证 key id。
- QR payload MUST 至少绑定 transaction id、展示端 principal/device、intended verifier、一次性 secret 或 commitment、`expires_at`、supported method；MUST NOT 包含长期私钥、secret storage key、recovery secret 或 MLS group secret。
- 跨 principal 验证只表达人工信任；本端 `user_signing_key` 签名对方 identity key，不改变对方设备授权状态。
- cancel code 由 §10.6 给出固定 registry（`user_cancelled` / `timeout` / `mismatched_commitment` / `mismatched_mac` / `device_revoked` / `untrusted_device` / `policy_denied` / `accepted_by_other_device` / …）。

#### 4.5.9 完整性评估

按 Matrix device-key 模型逐项比对，Contrix v1 已经覆盖：

- ✅ device identity key（Ed25519 / X25519）
- ✅ OTK / fallback key
- ✅ cross-signing 三层
- ✅ to-device 验证状态机 + cancel code
- ✅ server-side key backup（并增加域隔离）
- ✅ device list sync + 撤销
- ✅ secret storage（降为 client-local，wire 走 backup envelope）
- ✅ 群组加密（以 MLS 取代 Megolm，绑定 governance lattice）

Contrix 比 Matrix 多覆盖的：DID-rooted inception、principal control event stream、`cx.session.grant`、agent key、applet delegated device、push 伪名（`push_target_id`）、KeyPackage capability-subset rule、域隔离 backup、解密能力 ≠ 所有权证明的明确禁令。

因此本节认为 Contrix 在 device 密钥这一层已经完善，且与 Matrix 在关键点上的差异都已在协议中规范化定义。未来若出现新的 attack model 或 Matrix 引入新原语（如 MSC 中的 MLS / Olm hybrid），应在本节继续追加对比。

## 5. 其他关键区别

### 5.1 Room-first 与 object-first

Matrix 可以承载很多非聊天数据，但它的协议根仍是 room event。

Contrix 从一开始把 Flow、Realm、Space、Message、Morph 和 Relation 都作为协作对象处理；看板与列容器是 Space（`cx:space:`），住在 Realm 内但本身不是安全边界。聊天只是讨论 projection 的一种常见场景，不是所有业务状态的唯一载体。

### 5.2 Power level 与 capability

Matrix power level 适合 room 内角色治理。

Contrix capability 更适合细粒度协作系统：

- 可以限定 Realm、Space、Flow、Message、Morph、Relation，以及 `space.kind`、字段、时间、设备、速率、审批条件。
- 可以委托给 agent、Applet、设备、组织角色或外部服务。
- 可撤销、可审计，并与 policy server 风险决策分离。

### 5.3 Homeserver 与 Principal Server

Matrix homeserver 是用户与 room federation 的核心承载点。

Contrix Principal Server 是受 principal 或 Realm policy 控制的服务边界，不是身份本身，也不是真相源。它可以承载 Events API、Sync、Blob、Push、Policy，但协议仍保持分层。

这也是 Contrix 去掉独立第三方分发服务器后的核心边界：未加密私有内容不应进入不受用户、组织或 Realm policy 控制的第三方服务。

### 5.4 Query / Projection 是客户端派生层

Matrix 客户端通常从 sync、state、relations 和聚合接口构建体验。

Contrix 明确把搜索、通知、inbox、board、table、graph 等作为派生体验。默认由客户端本地完成；可选受托服务不能成为真相源，输出必须可追溯到签名 Event、reducer profile 和授权状态。

### 5.5 协作图比通信图更大

Matrix 的强项是通信网络。

Contrix 的目标是协作图：任务依赖、对象引用、结构化 mention、agent action、审计记录、审批和视图投影都属于同一个协议图。

## 6. State Model 与 Writer Model 的明确偏离

Matrix v1/v11 room state model 与 Contrix 的 **Move · Anchor · Lattice** 模型有若干关键偏离。本节列出这些偏离，使实现者在概念映射时不被相似命名误导。

### 6.1 没有 `state_key` 字段

Matrix event envelope 顶层有 `state_key` 字段，state event 用 `(type, state_key)` 作为 state slot 主键。Contrix v1 **不**继承这个字段——在 Contrix wire 上根本不存在 `state_key`。

替代设计：

- 协议状态写入由 Move 的 `effects[(cell_id, lattice_op)]` 表达。
- `cell_id` 是显式 canonical cell，例如 `cx:cell:cx.component.member.state.v1:<actor-did>`。
- 每个 cell family 在 registry / Realm schema 中声明 `lattice` 与 `bottom`。
- Subject 信息仍存在于 payload 或 Move effect value 中，并由 explicit cell id 承载。

**理由**：Matrix `state_key` 在实际使用中过载了多种语义。Contrix 把这些语义移动到 cell id 与 lattice schema，使多 cell 原子写、冲突 bottom、Anchor finality 和轻客户端 state_root 验证可以共用同一模型。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §3–§5。

### 6.2 没有 `cx.realm.policy.set` 这种聚合 kind

Matrix 把所有 room 配置塞进 `m.room.*` 一组同 type、不同 state_key 的事件（power_levels、join_rules、history_visibility 等共享同一 prefix）。Contrix v1 把每个配置 facet 拆成独立 kind：`cx.realm.policy`、`cx.realm.join_rule`、`cx.realm.history_visibility`、`cx.realm.discovery`、`cx.realm.media_service`、`cx.realm.archive`、`cx.realm.tombstone`、...

**理由**：聚合 kind 没有真实共享：每个 facet 有不同的 capability tier、auth refs、payload schema、reducer 行为。把它们绑成一个 kind 只是 Matrix wire 字段限制的产物，不反映任何模型上的共性。Contrix 的 per-facet kind 让 schema 路由更直、capability 矩阵更清楚、未来 facet 演进可独立版本化。

### 6.3 没有 Matrix 式 Winner Reconstruction

Matrix room state v2/v11 会在每个 `(type, state_key)` 上重建 auth chain difference 并自动选出 winner。Contrix v1 不再有全局 winner 算法：

- Move 是多 cell 原子 CAS，precondition 不成立则整个 Move 失败。
- Anchor 是 ordering authority 对 Move frontier 的承诺，Hub、threshold、peer mesh 都只是 anchorer cell 的不同 value。
- Lattice `join()` 对每个 cell 返回 value 或 `⊥`；安全关键 cell 使用 `bottom=reject` fail closed，不自动猜 winner。
- 冲突修复是普通 Move（例如 `head_in [A,B]` + recovery capability），不是特殊裁决路径。

### 6.4 Component Lattice

Matrix state event 没有显式的 cell 代数。Contrix v1 的 registry / Realm schema 为 reducer-input kind 声明：

- `cell_family`（稳定 `cx.component.*.v<n>` URI）
- `cell_subject`（null、payload field 或 composite descriptor）
- `lattice`（`or_set` / `mv_register` / `cas_register` / `fsm` / `counter` / `ordered_log`）
- `bottom`（`reject` / `expose`）

Receiver 不识别核心 lattice type MUST fail closed；扩展 cell family 必须通过 schema/profile 显式 opt-in。

### 6.5 E2EE Realm 的 MLS Governance Binding

Matrix 的 E2EE（Olm/Megolm）和 room state 是两条并行轨。Contrix v1 引入 **MLS Governance Binding**（profile `cx.profile.mls_governance_binding.full.v1`，定义见 `crypto-media/encryption-and-audit.md §2.5`），把 MLS epoch 强绑定到 governance state，由两层 wire-level artifact 协同工作：

- **Commit 侧** —— 每个 `cx.mls.commit` 携带 `governance_binding`（GroupContext extension `cx_governance_binding`），把 membership / policy / capability / discussion-metadata roots 哈希进 MLS transcript。
- **Lattice 侧** —— MLS commit 是 Move，写入 `mls_epoch_cell`、`key_schedule_cell` 与 `covered_frontier_cell`（or_set）。E2EE message Move 用 `contains` precondition 证明 `covered_frontier_cell` 覆盖自身 `anchor_ref` 所需 governance frontier。

**理由**：撤销、ban、device revoke 和 policy 收紧不能只在应用层 accepted；它们必须被 MLS epoch / key schedule 覆盖后才能影响新消息解密能力。`covered_frontier_cell` 让这条 "governance state 已被 commit attest 覆盖" 的事实变成可被 reducer 确定性查询的 lattice cell，而不是隐含在 transcript hash 里的 ad-hoc 检查。governance / recovery Move 不引用 `covered_frontier_cell`，因此 MLS 卡住不会阻止冲突修复。

### 6.6 Holder-Private Consent

Matrix 没有显式的 consent state——是否接受 invite / DM 由 client UI 处理，不进入协议账本。Contrix v1 引入独立的 [`identity/consent-model.md`](../identity/consent-model.md)：`cx.consent.grant` / `cx.consent.revoke` 是 holder principal control Realm 中的 Move，写入 `cx:cell:cx.component.consent.grant.v1:<consent_id>` cell（or_set, bottom=reject；or_set 本身不产生 ⊥，该 bottom 值与 registry 保持一致），作为 invite / contact 路径的前置 gate。MIMI `request_consent` / `update_consent` 直接映射到这套机制。

**理由**：去中心化协作中 consent 是合规与隐私的核心机制（GDPR、各种联系人骚扰防护、组织间合作授权）。把它建模为签名 Move on consent cell 而非 client-side 偏好，使其可审计、可签名、可跨 deployment 同步。

## 7. Matrix 仍然更强的地方

Contrix 不应忽略 Matrix 的成熟度：

- Matrix 有更成熟的实时通信和客户端生态。
- Matrix room federation、state resolution、E2EE 客户端实现、bridge 生态有多年生产经验。
- Matrix 对聊天、公开房间、桥接传统 IM 网络仍是强参考。

因此 Contrix 应继续吸收 Matrix 的稳定经验，尤其是 room version / auth rules、device trust、client sync、policy server、appservice transaction、authenticated media 等，但不继承 Matrix 的抽象根或 state winner 算法。

## 8. 相关文档

- [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) — Move、Anchor、Lattice、bottom diagnostics、E2EE MLS Move
- [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) — MLS Governance Binding：`governance_binding` 与 `covered_frontier_cell`
- [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) — device 密钥记录、prekey / fallback / KeyPackage claim、to-device 验证状态机、`push_target_id`、key backup envelope
- [`identity/key-management.md`](../identity/key-management.md) — inception / principal / recovery / device / session / agent / KeyPackage 密钥层级，`backup_class` 域隔离，社交恢复
- [`identity/consent-model.md`](../identity/consent-model.md) — holder-private consent on consent cell（or_set lattice）
- [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) — MIMI policy component / consent 互译
- [`extensions/applet-integration.md`](../extensions/applet-integration.md)
- [`extensions/agent-protocol-interop.md`](../extensions/agent-protocol-interop.md)
- [`identity/identity-did.md`](../identity/identity-did.md)
- [`sync/service-surface.md`](../sync/service-surface.md)

## 9. 外部参考

本节链接均为 informative reference；`unstable` 路径仅用于 Matrix 互操作背景说明，不构成 Contrix v1 normative dependency。

- Matrix Specification: https://spec.matrix.org/latest/
- Matrix Application Service API: https://spec.matrix.org/unstable/application-service-api/
- Matrix E2EE guide: https://matrix.org/docs/matrix-concepts/end-to-end-encryption/
- Matrix Megolm specification: https://spec.matrix.org/unstable/olm-megolm/megolm/
- AT Protocol DID specification: https://atproto.com/specs/did
- AT Protocol repository specification: https://atproto.com/specs/repository
- MLS RFC 9420: https://www.ietf.org/rfc/rfc9420
