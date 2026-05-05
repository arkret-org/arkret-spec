# Matrix 与 Contrix 的核心区别

## 1. 目标

本文旨在说明 Contrix 与 Matrix 的核心设计差异，阐明 Contrix 为何不是 Matrix 的直接变体，更非对其 room / homeserver / appservice 等概念的简单换名或重写。

## 2. 总体结论

Matrix 的核心抽象是 **room + event graph + homeserver federation**，重点服务实时通信、群聊、桥接和开放联邦。

Contrix 的核心抽象是 **signed Event + per-actor event chain + Space + Flow + Message + Morph + Relation + View + capability**，其中工作流容器通过 `Space (kind=board)` / `Space (kind=list)` 表达，重点服务可审计的协作对象、任务、看板、agent 协作和多视图投影。

因此二者可以互联或桥接，但协议根不同。

## 3. 核心差异表

| 维度 | Matrix | Contrix |
| --- | --- | --- |
| 数据根 | Room 内事件流与 room state。 | Space 内授权 Event 集合，归约为 Space、Flow、Message、Morph、Relation、View；看板与列容器通过 `Space.kind` 区分。 |
| 主要用途 | 即时通信、群聊、VoIP 信令、桥接通信网络。 | 协作对象、任务/看板、聊天/话题、agent 协作、审计工作流。 |
| 服务器模型 | Homeserver 是用户账号、room 参与和联邦传播的核心服务。 | Principal Server 是 principal 控制或显式委托的服务边界；Events、Sync、Blob、Policy 分层。 |
| 真相源 | Room event graph 与状态解析。 | Actor/device/service 签名 Event Envelope，加上 Space reducer；搜索和 View projection 都是派生层。 |
| 身份 | Matrix user ID 绑定 homeserver 域，如 `@alice:example.org`。 | Principal 使用 DID 作为协议主键；`@alice:example.org` 这类标识可作为 handle、登录入口或 bridge alias，但不能作为权限主体。 |
| 服务迁移 | 账号和 room 与 homeserver 域耦合较强。 | 身份、Event 发布链与服务 endpoint 分离，DID / handle / service delegation 支持迁移。 |
| 授权模型 | Room auth rules、membership、power levels。 | Capability grant、constraint、claim、policy、deterministic authorization。 |
| 扩展集成 | Application Service 主要由 homeserver 注册，按 user / room alias namespace 和 transaction 工作。 | Applet 是可签名、可授权、可审计的 service DID，可按 Space、Actor、对象范围、用户授权和 capability 细分。 |
| AI agent | Bot 可作为用户或 appservice 接入，但不是协议根对象。 | Agent 是一等 principal / Actor，可签名 Event，并拥有 capability 和 protocol session。 |
| 外部 agent 协议 | 无原生 A2A / ACP handoff 语义。 | A2A / ACP / MCP bridge / custom agent API 可作为受控 agent protocol session。 |
| E2EE | 当前 Matrix E2EE 基于 Olm / Megolm。 | Contrix 推荐 MLS RFC 9420 作为群组 E2EE 基础。 |
| 查询与视图 | 客户端主要从 sync、state、relations、聚合 API 还原体验。 | View 是一等投影定义；搜索和 projection 默认由客户端本地派生，不能成为真相源。 |
| 明文服务边界 | Homeserver 和 appservice 的明文可见性依赖部署、加密和桥接配置。 | 非 E2EE 私有内容必须只进入 principal 或 Space policy 明确委托的服务；明文可见服务用 `plaintext_visible_services` 声明。 |

## 4. 核心概念对比深化

### 4.1 Applet 与 Appservice

Matrix Application Service 是成熟的桥接机制，适合让 homeserver 与外部系统或 bot 服务通信。它的核心是 homeserver 侧注册、namespace、transaction、query 和 ping。

Contrix Applet 的差异不是简单“更强”，而是粒度不同：

- Applet registration 是签名声明，可由 Space owner、Organization、registry 或 authz service 接受。
- Applet 不因 namespace 自动获得权限；每次写入仍需 capability。
- 同一个 Applet 可以被不同 Space 用不同 capability、不同可见性、不同对象范围启用。
- 不同用户或组织可以在自己控制的 Space 中启用不同 Applet，但必须受 Space policy 和授权约束。
- Applet 可作为 bot、bridge、ghost actor controller、portal Space manager、delegated agent / device 参与审计链。

因此 Contrix 的优势是 **Space / principal / capability 级别的可组合授权与审计**，不是无条件允许任何用户随意给任何 Space 安装 Applet。

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

- atprotocol 主要面向公开 record 与 PDS；Contrix 面向多方协作 Space、授权状态、私有内容、E2EE 和企业治理。
- Contrix v1 core 默认普通用户身份方法是 `did:web`，同时支持 `did:key`（bootstrap / 设备）；高可审计部署可升级为 `did:webvh`（high-trust profile）。`did:pkh`（钱包）、`did:plc`（AT Protocol interop）、KERI 等 method 作为 v1.1+ extension interop profile 提供，不属于 v1 core 互操作必需。
- Contrix 的 Event 记录协作事实，不是公开内容分发 record。
- Contrix 把 Space policy、capability、Applet、Agent、MLS 和受托明文服务边界都纳入同一协作协议边界。

### 4.4 E2EE 架构选择

Matrix 的 Olm / Megolm 生态成熟、部署广泛、客户端实现经验丰富。Contrix 选择 MLS RFC 9420，是因为它更适合作为新的群组 E2EE 基础：

- MLS 是 IETF 标准。
- MLS 原生建模 group state、epoch、commit、proposal、member add/remove。
- Contrix 可以把 MLS epoch 与 Space membership、history visibility、device authorization、auditable E2EE 直接绑定。
- 被移除成员必须在新 epoch 上 fail closed。

因此，Contrix 选择了 **更现代、标准化、适合动态群组协作治理的 MLS 基础**，而不是沿用 Matrix 的 Olm / Megolm。

## 5. 其他关键区别

### 5.1 Room-first 与 object-first

Matrix 可以承载很多非聊天数据，但它的协议根仍是 room event。

Contrix 从一开始把 Flow、Space、Message、Morph 和 Relation 都作为协作对象处理；看板与列容器通过 `Space.kind` 表达。聊天只是讨论 projection 的一种常见场景，不是所有业务状态的唯一载体。

### 5.2 Power level 与 capability

Matrix power level 适合 room 内角色治理。

Contrix capability 更适合细粒度协作系统：

- 可以限定 Space、Flow、Message、Morph、Relation，以及 `space.kind`、字段、时间、设备、速率、审批条件。
- 可以委托给 agent、Applet、设备、组织角色或外部服务。
- 可撤销、可审计，并与 policy server 风险决策分离。

### 5.3 Homeserver 与 Principal Server

Matrix homeserver 是用户与 room federation 的核心承载点。

Contrix Principal Server 是受 principal 或 Space policy 控制的服务边界，不是身份本身，也不是真相源。它可以承载 Events API、Sync、Blob、Push、Policy，但协议仍保持分层。

这也是 Contrix 去掉独立第三方分发服务器后的核心边界：未加密私有内容不应进入不受用户、组织或 Space policy 控制的第三方服务。

### 5.4 Query / Projection 是客户端派生层

Matrix 客户端通常从 sync、state、relations 和聚合接口构建体验。

Contrix 明确把搜索、通知、inbox、board、table、graph 等作为派生体验。默认由客户端本地完成；可选受托服务不能成为真相源，输出必须可追溯到签名 Event、reducer profile 和授权状态。

### 5.5 协作图比通信图更大

Matrix 的强项是通信网络。

Contrix 的目标是协作图：任务依赖、对象引用、结构化 mention、agent action、审计记录、审批和视图投影都属于同一个协议图。

## 6. Matrix 仍然更强的地方

Contrix 不应忽略 Matrix 的成熟度：

- Matrix 有更成熟的实时通信和客户端生态。
- Matrix room federation、state resolution、E2EE 客户端实现、bridge 生态有多年生产经验。
- Matrix 对聊天、公开房间、桥接传统 IM 网络仍是强参考。

因此 Contrix 应继续吸收 Matrix 的稳定经验，尤其是 room version / auth rules / state resolution、device trust、client sync、policy server、appservice transaction、authenticated media 等，但不继承 Matrix 的抽象根。

## 7. 相关文档

- `extensions/applet-integration.md`
- `extensions/agent-protocol-interop.md`
- `identity/identity-did.md`
- `crypto-media/encryption-and-audit.md`
- `authz/capabilities.md`
- `sync/service-surface.md`

## 8. 外部参考

- Matrix Specification: https://spec.matrix.org/latest/
- Matrix Application Service API: https://spec.matrix.org/unstable/application-service-api/
- Matrix E2EE guide: https://matrix.org/docs/matrix-concepts/end-to-end-encryption/
- Matrix Megolm specification: https://spec.matrix.org/unstable/olm-megolm/megolm/
- AT Protocol DID specification: https://atproto.com/specs/did
- AT Protocol repository specification: https://atproto.com/specs/repository
- MLS RFC 9420: https://www.ietf.org/rfc/rfc9420
