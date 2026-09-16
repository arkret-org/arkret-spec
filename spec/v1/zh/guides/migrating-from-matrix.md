---
title: 从 Matrix 迁移到 Arkret
status: candidate
normative: false
stability: v1
updated: 2026-07-13
---

> 本文件为面向 Matrix 实现者的 informative 设计取舍对照，不是协议真相源；任何协议约束以被引用的具体规范章节为准。

## 1. 目标

本文旨在说明 Arkret 与 Matrix 的核心设计差异，阐明 Arkret 为何不是 Matrix 的直接变体，更非对其 room / homeserver / appservice 等概念的简单换名或重写。

## 2. 总体结论

Matrix 的核心抽象是 **room + event graph + homeserver federation**，重点服务实时通信、群聊、桥接和开放联邦。

Arkret 的核心抽象是 **signed Event + per-actor event chain + Realm + Circle + Space + Strand + Message + Morph + Relation + View + capability**（canonical 对象清单以 [`index.md` §1](../index.md) 为准），其中 Realm 是 security boundary、Circle 是 Realm 内的子事件边界、Space 是结构容器（Board / List / 等），重点服务可审计的协作对象、任务、看板、agent 协作和多视图投影。

因此二者可以互联或桥接，但协议根不同。

## 3. 核心差异表

| 维度 | Matrix | Arkret |
| --- | --- | --- |
| 数据根 | Room 内事件流与 room state。 | Realm 内授权 Event 集合，归约为 Realm、Strand、Message、Morph、Relation、View；看板与列容器是独立的 Space 对象（`ak:space:`），永远住在某 Realm 内。 |
| 主要用途 | 即时通信、群聊、VoIP 信令、桥接通信网络。 | 协作对象、任务/看板、聊天/话题、agent 协作、审计工作流。 |
| 服务器模型 | Homeserver 是用户账号、room 参与和联邦传播的核心服务。 | Station 是 principal 控制或显式委托的服务边界；Events、Sync、Blob、Policy 分层。 |
| 真相源 | Room event graph 与状态解析。 | Actor/device/service 签名 Event Envelope，加上 Realm reducer；搜索和 View projection 都是派生层。 |
| 身份 | Matrix user ID 绑定 homeserver 域，如 `@alice:example.org`。 | Principal 使用 DID 作为协议主键；`@alice:example.org` 这类标识可作为 handle、登录入口或 bridge alias，但不作为权限主体。 |
| 服务迁移 | 账号和 room 与 homeserver 域耦合较强。 | 身份、Event 发布链与服务 endpoint 分离，DID / handle / service delegation 支持迁移。 |
| 授权模型 | Room auth rules、membership、power levels。 | Capability grant、constraint、claim、policy、deterministic authorization。 |
| 扩展集成 | Application Service 主要由 homeserver 注册，按 user / room alias namespace 和 transaction 工作。 | Applet 是可签名、可授权、可审计的 service DID，可按 Realm、Actor、对象范围、用户授权和 capability 细分。 |
| AI agent | Bot 可作为用户或 appservice 接入，但不是协议根对象。 | Agent 是一等 principal / Actor，可签名 Event，并拥有 capability 和 protocol session。 |
| 外部 agent 协议 | 无原生 agent handoff 语义。 | 外部 agent 协议桥接与自定义 agent API 可作为受控 agent protocol session。 |
| E2EE | 当前 Matrix E2EE 基于 Olm / Megolm。 | Arkret 推荐 MLS RFC 9420 作为群组 E2EE 基础。 |
| 查询与视图 | 客户端主要从 sync、state、relations、聚合 API 还原体验。 | View 是一等投影定义；搜索和 projection 默认由客户端本地派生，不充当真相源。 |
| 明文服务边界 | Homeserver 和 appservice 的明文可见性依赖部署、加密和桥接配置。 | 非 E2EE 私有内容由 principal 或 Realm policy 明确委托的服务处理；明文可见服务用 `plaintext_visible_services` 声明。 |

## 4. 核心概念对比深化

### 4.1 Applet 与 Appservice

Matrix Application Service 是成熟的桥接机制，适合让 homeserver 与外部系统或 bot 服务通信。它的核心是 homeserver 侧注册、namespace、transaction、query 和 ping。

Arkret Applet 的差异不是简单“更强”，而是粒度不同：

- Applet registration 是签名声明，注册材料可由 Realm owner、Organization 或 registry 验证；正式 Realm Event 的准入与 capability 判定由 Station 负责。
- Applet 不因 namespace 自动获得权限；写入授权仍由 capability 表达。
- 同一个 Applet 可以被不同 Realm 用不同 capability、不同可见性、不同对象范围启用。
- 不同用户或组织可以在自己控制的 Realm 中启用不同 Applet，并受 Realm policy 和授权约束（规范见 [`extensions/applet-integration.md`](../extensions/applet-integration.md)）。
- Applet 可作为 bot、bridge、Ghost Actor controller、portal Realm manager、delegated agent / device 参与审计链。

因此 Arkret 的优势是 **Realm / principal / capability 级别的可组合授权与审计**，不是无条件允许任何用户随意给任何 Realm 安装 Applet。

### 4.2 AI 与 agent 支持

Matrix 可以通过 bot、appservice 或 bridge 接入 AI，但 AI 不是 Matrix 的协议根对象。Arkret 从对象模型开始就把 agent 纳入：

- agent 可以是 principal、Actor、capability subject。
- agent 输出可以写入 Message、Strand、Morph 或 Relation。
- agent 权限采用窄范围、短时效、可撤销、可审计（规范见 [`identity/key-management.md`](../identity/key-management.md) §3 agent key）。
- agent 间协作场景可以显式升级到外部 agent 协议桥接或企业私有 agent API，并将 session、status、artifact、result 回写 Arkret。
- Arkret 把协作事实、授权边界、审计摘要和最终结果放入协议账本，不把每个 token 或 tool call 都建模为 durable Event。

### 4.3 身份系统的演进

Arkret 的身份与发布模型借鉴 atprotocol 的几个方向：

- DID 是稳定身份根，handle 是可变入口。
- handle 采用双向验证模型。
- DID Document 用于服务发现和 key discovery。
- 每个 actor 通过 `actor_id`、`producer_revision` 和 `domain_refs` 形成可验证 event chain。
- signed Event Envelope 是发布单元，服务器无法伪造 principal 写入。

这不要求普通用户直接看见或管理 DID。客户端和服务端可以提供类似 Matrix 的 `@user:domain` 体验，把它作为联系人搜索、登录名、组织 handle 或桥接 alias；持久 Event、grant 或 MLS membership 的权威主体仍是 principal DID。

但 Arkret 不等同于 atprotocol：

- atprotocol 主要面向公开 record 与 PDS；Arkret 面向多方协作 Realm、授权状态、私有内容、E2EE 和企业治理。
- Arkret v1 唯一可注册长期用户身份方法是 `did:webvh`（提供可审计 DID 控制历史，抵御 DNS / TLS 单点失陷）；`did:web` 只用于显式 no-history service，`did:key` 只用于声明 `ak.profile.ephemeral_pairwise_principal.v1`、且由 exact accepted MLS LeafNode 约束的 Realm-local 临时 actor。后者不创建账号/PCR/设备目录。设备自身没有 DID；设备公钥可以使用 `did:key` 作自描述 key material。`did:pkh`（钱包）、`did:plc`（AT Protocol interop）、KERI 等 method 只作为外部 interop claim，不属于 v1 principal 创建面。
- Arkret 的 Event 记录协作事实，不是公开内容分发 record。
- Arkret 把 Realm policy、capability、Applet、Agent、MLS 和受托明文服务边界都纳入同一协作协议边界。

### 4.4 E2EE 架构选择

Matrix 的 Olm / Megolm 生态成熟、部署广泛、客户端实现经验丰富。Arkret 选择 MLS RFC 9420，是因为它更适合作为新的群组 E2EE 基础：

- MLS 是 IETF 标准。
- MLS 原生建模 group state、epoch、commit、proposal、member add/remove。
- Arkret 可以把 MLS epoch 与 Realm membership、history visibility、device authorization、auditable E2EE 直接绑定。
- 被移除成员在新 epoch 上 fail closed（规范见 [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) §2.5 MLS Governance Binding）。

因此，Arkret 选择了 **更现代、标准化、适合动态群组协作治理的 MLS 基础**，而不是沿用 Matrix 的 Olm / Megolm。

### 4.5 Device 密钥层级与生命周期

§4.4 只覆盖了群组 E2EE 算法的选择。但 device-key 是一整套包含身份密钥、prekey、群组密钥、账户级设备信任、备份、推送、验证状态机的体系。Matrix 在这套体系上有成熟实践（参见 [Matrix E2EE guide](https://matrix.org/docs/matrix-concepts/end-to-end-encryption/) 与 [Megolm spec](https://spec.matrix.org/unstable/olm-megolm/megolm/)），Arkret 在保留多数原语形状的同时，把身份根换到 DID method、把 E2EE 换到 MLS、并把若干在 Matrix 中相对耦合的语义拆开规范化。本节按原语逐项对照。

#### 4.5.1 设备级身份密钥与信任根

| Matrix | Arkret | 说明 |
| --- | --- | --- |
| Device Ed25519 fingerprint key | `ak:device:` 记录里的 `verify_key` (Ed25519) | Arkret 把 device 公钥写进 `ak:device:` 记录（详见 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §4），并由 `ak.device.authorize` Event 锚定到 principal DID，而非 homeserver 账号。 |
| Device Curve25519 identity key | `ak:device:` 记录里的 `hpke_key` (X25519) | 用于 HPKE-based to-device 通道、KeyPackage init key 来源、加密 backup envelope 接收。Matrix Curve25519 用于 Olm 长期 DH，语义对等但用途窄一些。 |
| (homeserver 账号绑定) | DID method cold identity root | Arkret 在日常设备签名层之外另有一层冷身份根：例如 `did:webvh` 的逐代 `updateKeys`。它只做 DID method 管理、签自体 PCR genesis，并在 accepted recovery policy 显式启用时充当 recovery-session factor；它不签 `ak.device.reanchor`，也不成为 device key、MLS leaf key 或日常 Event key。恢复 unit 由 session 冻结的 replacement device identity key 签署。根代际归属由 DID method history / key log 表达，而不是 homeserver 内部状态。详见 [`identity/key-management.md`](../identity/key-management.md) §3.1、§5.0。 |

#### 4.5.2 Prekey 与会话引导

| Matrix | Arkret | 说明 |
| --- | --- | --- |
| `/_matrix/client/v3/keys/upload` Curve25519 OTK | `POST /_arkret/self/keys/upload` 的 `one_time_keys` | 语义一致，用于非 MLS 加密或 MLS 引导。一次性 key 的原子消费规则由 key operation 章节定义。 |
| Fallback key | `fallback_keys` 字段，`fallback=true` 标记 | Arkret 在会话建立后倾向更快轮换；Matrix 行为类似但描述较弱。 |
| (Olm OTK 同时承担群组成员引导) | MLS KeyPackage 独立 claim API | Arkret 把 MLS KeyPackage 从 OTK 池里拆出来：`/_arkret/self/keys/keypackages/upload`、`/_arkret/self/keys/keypackages/claim`、`/_arkret/self/keys/keypackages/consume`、`/_arkret/self/keys/keypackages/revoke`，并把 capability 子集校验与反枚举失败形态放在 KeyPackage 规范中。Matrix 无对应概念。 |

#### 4.5.3 群组消息密钥

| Matrix | Arkret | 说明 |
| --- | --- | --- |
| Megolm outbound session（per-sender ratchet） | MLS exporter / application key per epoch | Arkret 没有 per-sender Megolm session；群组密钥状态由 MLS group state、epoch、KeyPackage 演进。 |
| Megolm inbound session 缓存 | MLS group state + epoch material 写入 `mls_epoch_result`、`key_schedule_result` 与 active key-access-revision projection | epoch 与 key-access checkpoint 由 MLS transcript 和 reducer projection 共同绑定。 |
| Megolm Ed25519 签名（per-message） | MLS application message 内嵌签名 + MLS transcript | 完整性来自 MLS 标准；不再额外维护 per-message Megolm 签名链。 |

#### 4.5.4 设备授权与信任视图

Arkret v1 不移植 Matrix 的账户级设备信任密钥层级。设备 authority 以 root-committed PCR genesis 为起点；首设备同时提供私钥持有证明，后续设备由当前 generation 中已 accepted 的设备批准，全设备丢失使用 identity-root re-anchor。DID 只锚定 identity root key log，不承载设备目录或业务委派。

Matrix 导入只能生成显式迁移 evidence，不能把旧的跨设备信任断言直接变成 active PCR authorization。迁移客户端必须让用户在 Arkret 侧完成一次明确的 genesis、pairing 或 re-anchor ceremony。

#### 4.5.5 Secret Storage 与 Key Backup

| Matrix | Arkret | 说明 |
| --- | --- | --- |
| Secure Secret Storage（SSSS）统一保管账户密钥 / megolm backup 等 | `ak.secret_storage.v1`（**client-local only**）+ wire 上传走 `ak.schema.key_backup.v1` | Arkret v1 不再把 secret storage envelope 作为 wire 格式；服务端 wire backup 使用 `ak.schema.key_backup.v1` 与 `backup_kind` 分类。 |
| 一把 recovery key 解锁 SSSS | `recovery_policy` 的封闭四方法 | Arkret 把 recovery 表达为 `recovery_policy`，`methods` 封闭为 `did_root`、`recovery_unlock`、`device_quorum`、`trusted_recovery_service`，可声明每个 key 的有效期与顶层冷却。身份核验与人工审核由产品承担，协议只验证账号事先授权的签发方与本次受限授权；v1 没有 threshold、share holder 或 approval 条件。恢复控制权不自动授予读取内容或解密历史的能力。 |
| (Matrix 未明确约束) | "能解密某段历史" 不单独作为账号所有权证明 | Arkret 把 DID 控制证明与解密能力分开，并定义了固定格式、限速、绑定 audience / service DID 的 challenge 流程。 |

#### 4.5.6 Push 通道密钥

Matrix pusher 把 (user, device, push token) 映射作为 push gateway 可见标识符，没有跨设备 / 跨通道 / 跨 Realm 的不可链接性规范。Arkret 在 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §5.6 引入 `push_target_id`：

- per `(account_id, device_id, push_route)` 伪名；熵下限和高安全部署参数见 `device-lifecycle.md` §5.6.1。
- 伪名派生不使用公开 DID、`device_id`、平台 push token、handle、邮箱或电话号码作为可观察输入。
- 同一 principal 在不同 Station、两台设备或同一 device 的两条 push_route 上得到不可链接的 `push_target_id`。
- gateway / vendor 不保存可逆映射；被 joined-member ActorId routing projection 授权的 Station sync surface 在本服务上下文内持有运行时索引。
- 推送 payload 以加密 envelope 或等价 ephemeral encrypted blob 表达，gateway / vendor 不持有解密语义。

#### 4.5.7 Arkret 新增的密钥类别

以下密钥类别在 Matrix 中没有显式协议层定义（属于实现侧或 appservice 侧约定），Arkret 在 [`identity/key-management.md`](../identity/key-management.md) §3 中作为一等协议原语：

- **Session key（`ak.session.grant`）**：浏览器、OIDC、SSO、远程执行环境的短期会话密钥。其 audience / origin / service / scope / 过期时间绑定和 DID control state 复验由 key-management 与 account lifecycle 章节定义。
- **Agent key**：AI agent / bot / CI / automation 的一等密钥类型，带 scope、`expires_at`、accountable actor 绑定；高风险动作可由 proposal / approval 约束。Matrix bot 复用 user / appservice token，没有这一层 scope/审计结构。
- **Applet delegated device key**：Applet 代表 Ghost Actor 或桥接用户参与 E2EE 时，使用受限的 delegated device 密钥；`device_id` 标记 `applet_id`，capability 限定 Realm / 协议 / 动作 / 有效期，delegated device 不签发新的人类 device。to-device 权限只覆盖其 namespace 内 actor。Matrix appservice 的 ghost user 没有 device-level 委托语义。
- **冷 Identity Root 代际**：DID method 层的逐代控制密钥。`root_0` 只签客户端构造的 DID entry 0 controller proof、PCR genesis 与全设备丢失时的 re-anchor。root、device key 与 DPoP key 材料必须分离，recovery secret / root seed 不上传、不进入 `secret_storage` wire backup；日常 Event 只由已授权 device key 签名。

#### 4.5.8 验证 / 登录 / 设备授权的语义解耦

Matrix to-device 验证（SAS / QR）成功后，客户端实现常常顺势把设备视为"已信任、已授权"，登录与设备授权也较多耦合在 homeserver 的 `/login` 路径上。Arkret 把三件事分开建模（[`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §1.2），并且**不移植 Matrix 的 device-level SAS / verification-QR 协议**：

| 操作 | Arkret 允许产出 | Arkret 不自动产出 |
| --- | --- | --- |
| 登录因子验证（密码 / passkey / OIDC / SSO） | 短期 `ak.session.grant`、触发 recovery、请求已授权设备授权 | 长期 device、`ak.device.authorize`、E2EE 历史密钥访问 |
| 设备授权 | `ak.device.authorize`、DID key-log operation、`ak.device.list_update`、MLS Welcome 资格 | 仅凭密码 / SSO 通过即视作设备授权 |
| 设备信任确认（pairing 短码 / pairing 二维码 / 配对链接） | §10.1 的 verification checkpoint 与一次性 pairing transcript | 长期 device grant、Realm capability、登录态 |

Arkret v1 没有 `m.key.verification` 对应的 to-device 消息族、SAS 算法协商或独立的 verification 二维码。同一 principal 的新设备只走一次 pairing ceremony：新设备同时展示 8 位短码、pairing 二维码与配对链接，已授权设备扫码、输码或粘贴链接后核对短码并批准，绑定规则见 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) §2.1.1 / §2.1.2：

- pairing transcript 覆盖 `pairing_code`、`device_pairing_request_id`、完整 `AccountId`、`gate_audience`、`expires_at`、candidate keys 与 metadata digest。
- 成功的 accepted-device pairing 按 §10.1 建立 `verification_source=pairing_code` 的 verification checkpoint；lifecycle 与 trust evidence 仍是两个正交维度。
- 跨 principal 的联系人验真不在 v1 范围；未来若需要，应绑定双方 stable principal / identity key 的 safety number，而不是逐台确认会轮换的 device key。
- Matrix 客户端迁移时 MUST 把 SAS / verification-QR 界面映射到 pairing ceremony，不能期待 Arkret 提供等价的 device-level 验证消息。

#### 4.5.9 完整性评估

> **informative 自评**：本小节是面向 Matrix 迁移读者的对照性自评，不是 coverage / conformance 的权威真相源。某能力是否构成 v1 一致性要求，以 [`conformance/conformance-profiles.json`](../../artifacts/profiles/conformance-profiles.json)（及 [`conformance/`](../conformance/) 下相关文档）与 [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) 为准；本节列举仅供迁移规划参考。

按 Matrix device-key 模型逐项比对，Arkret v1 已经覆盖：

- covered: device identity key（Ed25519 / X25519）
- covered: OTK / fallback key
- covered: PCR-rooted device authorization、pairing、revoke 与 root re-anchor
- covered: to-device 验证状态机 + cancel code
- covered: server-side key backup（并增加域隔离）
- covered: device list sync + 撤销
- covered: secret storage（降为 client-local，wire 走 backup envelope）
- covered: 群组加密（以 MLS 取代 Megolm，绑定 governance projection）

Arkret 比 Matrix 多覆盖的：DID-rooted inception、principal control event stream、`ak.session.grant`、agent key、applet delegated device、push 伪名（`push_target_id`）、KeyPackage capability-subset rule、域隔离 backup、解密能力 ≠ 所有权证明的明确禁令。

因此本节认为 Arkret 在 device 密钥这一层已经完善，且与 Matrix 在关键点上的差异都已在协议中规范化定义。未来若出现新的 attack model 或 Matrix 引入新原语（如 MSC 中的 MLS / Olm hybrid），应在本节继续追加对比。

## 5. 其他关键区别

### 5.1 Room-first 与 object-first

Matrix 可以承载很多非聊天数据，但它的协议根仍是 room event。

Arkret 从一开始把 Strand、Realm、Space、Message、Morph 和 Relation 都作为协作对象处理；看板与列容器是 Space（`ak:space:`），住在 Realm 内但本身不是安全边界。聊天只是讨论 projection 的一种常见场景，不是所有业务状态的唯一载体。

### 5.2 Power level 与 capability

Matrix power level 适合 room 内角色治理。

Arkret capability 更适合细粒度协作系统：

- 可以限定 Realm、Space、Strand、Message、Morph、Relation，以及 `space.kind`、字段、时间、设备、速率、审批条件。
- 可以委托给 agent、Applet、设备、组织角色或外部服务。
- 可撤销、可审计，并与持久治理策略分离。

### 5.3 Homeserver 与 Station

Matrix homeserver 是用户与 room federation 的核心承载点。

Arkret Station 是受 principal 或 Realm policy 控制的服务边界，不是身份本身，也不是真相源。它可以承载 Events API、Sync、Blob、Push、Policy，但协议仍保持分层。

这也是 Arkret 去掉独立第三方分发服务器后的核心边界：未加密私有内容停留在用户、组织或 Realm policy 控制的服务边界内。

### 5.4 Query / Projection 是客户端派生层

Matrix 客户端通常从 sync、state、relations 和聚合接口构建体验。

Arkret 明确把搜索、通知、inbox、board、table、graph 等作为派生体验。默认由客户端本地完成；可选受托服务不充当真相源，输出可追溯到签名 Event、fixed reducer semantics 和授权状态（规范见 [`overview/architecture.md`](../overview/architecture.md) §3）。

### 5.5 协作图比通信图更大

Matrix 的强项是通信网络。

Arkret 的目标是协作图：任务依赖、对象引用、结构化 mention、agent action、审计记录、审批和视图投影都属于同一个协议图。

## 6. State Model 与 Writer Model 的明确偏离

Matrix v1/v11 room state model 与 Arkret 的 **authority-commit projection** 模型有若干关键偏离。本节列出这些偏离，使实现者在概念映射时不被相似命名误导。

### 6.1 没有 `state_key` 字段

Matrix event envelope 顶层有 `state_key` 字段，state event 用 `(type, state_key)` 作为 state slot 主键。Arkret v1 **不**继承这个字段——在 Arkret wire 上根本不存在 `state_key`。

替代设计：

- 协议事实由普通 Event 或 state-changing Event 的 `kind + payload` 表达；typed current result target 与状态操作由注册 reducer contract 确定性派生，不是 wire 字段。
- `result_id` 是显式 canonical typed current result，例如 `member_state:<actor-did>`。
- 每个 typed current result family 在 registry 中声明 `execution`、`domain reducer` 与 `value_shape`；普通 `current-value projection` 以固定 `(depth,EventId)` 产生唯一 winner，安全写入使用 RealmCommit 的唯一确认顺序。
- Subject 信息存在于 payload；receiver 按 registry 从具名 payload 路径派生 explicit typed current result id 与 projected value。

**理由**：Matrix `state_key` 在实际使用中过载了多种语义。Arkret 把这些语义移动到 typed current result id 与注册状态合同；普通数据按声明的 CRDT 模型收敛，安全状态由 RealmCommit 确认序列推进，轻客户端按各自承诺验证。详见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) §3–§5。

### 6.2 没有 `ak.realm.policy.set` 这种聚合 kind

Matrix 把所有 room 配置塞进 `m.room.*` 一组同 type、不同 state_key 的事件（power_levels、join_rules、history_access 等共享同一 prefix）。Arkret v1 把每个配置 facet 拆成独立 kind：`ak.realm.policy`、`ak.realm.join_rule`、`ak.realm.history_access`、`ak.realm.discovery`、`ak.realm.media_service`、`ak.realm.archive`、`ak.realm.tombstone` 等；完整 active kind 集合以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为权威源。

**理由**：聚合 kind 没有真实共享：每个 facet 有不同的 capability tier、auth refs、payload schema、reducer 行为。把它们绑成一个 kind 只是 Matrix wire 字段限制的产物，不反映任何模型上的共性。Arkret 的 per-facet kind 让 schema 路由更直、capability 矩阵更清楚、未来 facet 演进可独立版本化。

### 6.3 没有 Matrix 式 Winner Reconstruction

Matrix room state v2/v11 会在每个 `(type, state_key)` 上重建 auth chain difference 并自动选出 winner。Arkret v1 不再有全局 winner 算法：

- 普通数据采用因果寄存器、OR-set、日志或分片计数器；接收站独立验证，未知撤销允许传播窗口。
- 安全命令在每 Realm 唯一确认序列中执行，实际读取/写入 revision 与授权必须重验，竞争 CAS 至多一个成功。
- RealmCommit 只确认安全状态，不覆盖普通消息。每个 Realm 同阶段仅一个治理 Station 和唯一冻结 signer；不提供多节点容错。
- 普通寄存器按固定因果全序选择唯一 current，有权因果后继可继续编辑；安全状态不做无序 join，也不存在任意 typed current result reset。

### 6.4 领域 current result

Matrix state event 没有显式的领域 current result。Arkret v1 为每个可查询领域声明：

- closed `selector.kind` 与稳定领域身份字段；
- 完整 typed value schema；
- 最后修改它的 `{commit_id, stream_position}` revision；
- 写入需要并发保护时使用的 typed `expected_revision`。

Receiver 不识别 selector kind 或 value branch 时 fail closed。扩展领域必须通过 schema/profile 显式 opt-in，不得退化为通用状态键或客户端自定义求值（规范见 [`sync/current-results.md`](../sync/current-results.md) 与 [`models/common-fields.md`](../models/common-fields.md) §3）。

### 6.5 E2EE Realm 的 MLS Governance Binding

Matrix 的 E2EE（Olm/Megolm）和 room state 是两条并行轨。Arkret v1 引入 **MLS Governance Binding**（固定 GroupContext extension，定义见 `crypto-media/encryption-and-audit.md §2.5`），把 MLS epoch 强绑定到 governance state，由两层 wire-level artifact 协同工作：

- **Commit 侧** —— 每个 `ak.mls.commit` 携带 `governance_binding`（GroupContext extension `mls_governance_binding`），把唯一 `key_access_revision` 哈希进 MLS transcript；digest 只覆盖会改变密钥访问资格的 closed state。
- **deterministic projection 侧** —— MLS Commit 是 state-changing Event，写入 `mls_epoch_result`、`key_schedule_result` 与 active key-access-revision projection。E2EE message Event 的普通 `commit_authorization_state.authority_refs` 只用于 Event admission；MLS gate 独立检查消息 group/epoch 对应的 digest 是否仍等于当前 key-access checkpoint。

**理由**：member/leaf remove、device revoke 和 key-access policy 收紧被新 MLS epoch 覆盖后才限制新消息密钥；普通 capability、metadata 或 moderation 变化没有改变谁持有 epoch key，不应机械阻塞发送。active projection 使 Commit 所覆盖的精确 digest 可确定性查询，governance / recovery Event 不依赖它，因此 MLS 卡住不会阻止冲突修复。

### 6.6 Holder-Private Consent

Matrix 没有显式的 consent state——是否接受 invite / DM 由 client UI 处理，不进入协议账本。Arkret v1 引入独立的 [`identity/consent-model.md`](../identity/consent-model.md)：`ak.consent.grant` / `ak.consent.revoke` 是 holder principal control Realm 中的 Event，写入 `consent_grant:<consent_id>` typed current result（commit-ordered projection，value_shape=set），作为 invite 与明确登记的非 Contact action 前置 gate；Contact/Personal DM只读取双方方向性 Contact heads，绝不读取 Consent。MIMI `request_consent` / `update_consent` 直接映射到这套独立机制。

**理由**：去中心化协作中 consent 是合规与隐私的核心机制（GDPR、各种联系人骚扰防护、组织间合作授权）。把它建模为签名 Event on consent typed current result 而非 client-side 偏好，使其可审计、可签名、可跨 deployment 同步。

## 7. Matrix 仍然更强的地方

Arkret 可以继续吸收 Matrix 的成熟经验：

- Matrix 有更成熟的实时通信和客户端生态。
- Matrix room federation、state resolution、E2EE 客户端实现、bridge 生态有多年生产经验。
- Matrix 对聊天、公开房间、桥接传统 IM 网络仍是强参考。

因此 Arkret 应继续吸收 Matrix 的稳定经验，尤其是 room version / auth rules、device trust、client sync、appservice transaction、authenticated media 等，但不继承 Matrix 的抽象根或 state winner 算法。

## 8. 相关文档

- [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) — Event、state-changing Event、RealmCommit、state model、ordinary causal conflict、E2EE MLS Event
- [`crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) — MLS key-access revision binding：`governance_binding.key_access_revision` 与 current winning group-state projection
- [`crypto-media/device-lifecycle.md`](../crypto-media/device-lifecycle.md) — device 密钥记录、prekey / fallback / KeyPackage claim、to-device 验证状态机、`push_target_id`、key backup envelope
- [`identity/key-management.md`](../identity/key-management.md) — inception / principal / recovery / device / session / agent / KeyPackage 密钥层级，`backup_kind` 域隔离，社交恢复
- [`identity/consent-model.md`](../identity/consent-model.md) — holder-private consent on consent typed current result（commit-ordered projection 安全集合）
- [`extensions/mimi-interop.md`](../extensions/mimi-interop.md) — MIMI policy component / consent 互译
- [`extensions/applet-integration.md`](../extensions/applet-integration.md)
- [`identity/identity-did.md`](../identity/identity-did.md)
- [`sync/service-surface.md`](../sync/service-surface.md)

## 9. 外部参考

本节链接均为 informative reference；`unstable` 路径仅用于 Matrix 互操作背景说明，不构成 Arkret v1 normative dependency。

- Matrix Specification: https://spec.matrix.org/latest/
- Matrix Application Service API: https://spec.matrix.org/unstable/application-service-api/
- Matrix E2EE guide: https://matrix.org/docs/matrix-concepts/end-to-end-encryption/
- Matrix Megolm specification: https://spec.matrix.org/unstable/olm-megolm/megolm/
- AT Protocol DID specification: https://atproto.com/specs/did
- AT Protocol repository specification: https://atproto.com/specs/repository
- MLS RFC 9420: https://www.ietf.org/rfc/rfc9420
