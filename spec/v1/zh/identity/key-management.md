---
title: Key Management
status: candidate
normative: true
stability: v1
updated: 2026-08-11
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

身份层定义“谁是主体”，加密层定义“如何保护内容”，但真正能让系统安全运行的是密钥管理。

本文定义 Arkret 的密钥生命周期：

- identity root key
- principal signing key
- recovery secret 与域分隔子键
- device key
- session key
- agent key
- MLS KeyPackage
- backup / restore key

## 2. 基本原则

### 2.1 主体不等于设备

一个 DID principal MAY 拥有多个设备。
设备可以签名、同步和解密，但设备不是协议层主身份。

协议层主体仍然是 DID。设备权力来自：

- DID Document 当前控制密钥
- DID method history / key log / operation log
- device authorization event
- capability grant
- recovery policy

### 2.2 长期密钥与日常密钥分离

实现 MUST 区分：

- 长期身份锚点
- 日常签名密钥
- 设备密钥
- 会话密钥
- 加密群组密钥
- 恢复密钥

长期身份锚点不得用于日常签名。human DID control 只直接参与注册锚、method successor、current external claim，以及 policy 显式启用的可选 DID-root recovery factor；普通授权、recovery policy、capability 与业务 Event 必须由当前 PCR generation 的 accepted device、policy quorum 或短期 session/device key 路径完成。

### 2.3 所有授权都必须可撤销

设备、agent、session 和企业网关颁发的权限 MUST 有明确失效条件：

- `expires_at`
- revoke event、status event 或 profile 注册的 credential status mechanism
- `agent_key_scope`
- `audience`
- `not_before`

无限期、无 scope 的委托只允许用于极少数离线恢复场景，并且 SHOULD 有多签或门限保护。

## 3. 密钥类型

### 3.1 Identity Root Key

identity root key 表示 DID method 的初始与后继更新控制材料。对 Arkret v1 默认的 `did:webvh` principal，entry i 的 `updateKeys[0]` 是 `root_i` 公钥，`nextKeyHashes[0]` 是 `root_{i+1}` 公钥的哈希；它们不是同一把 key 的两个表示位置。pre-rotation 启用时，entry i+1 的 controller proof MUST 由 entry i+1 中当前 active 的 `root_{i+1}` 签发，并验证其公钥命中 entry i 的 `nextKeyHashes` 承诺。

要求：

- root private key MUST 从生成起冷持有，不得由服务端生成或持有，也不得在任何设备上长期驻留；
- root public key MUST NOT 出现在 principal DID Document 的 `verificationMethod` 中，root private key MUST NOT 充当 device key、MLS leaf key、KeyPackage key、session key 或入册权威 key；
- root 的 Event 签名权限是封闭白名单：仅允许签自体 principal 的 PCR genesis `ak.realm.create` 与恢复 `ak.device.reanchor`；其他 Event 即使携带 DID entry ref 也不得启用 root-anchor 验签路径；
- root 还可签合规 DID log controller proof；除此之外不得签普通 Arkret 操作。因此 root 的签名用途恰为三项：PCR genesis `ak.realm.create`、恢复 `ak.device.reanchor`、DID log controller proof；
- 每个后继 root 公钥 MUST 不同于全部已激活 root；一代 root 被后继 entry 取代后即 spent，MUST NOT 再出现在任何后继 `updateKeys` 或 `nextKeyHashes` 中。

### 3.2 Principal High-Privilege Signing

Arkret v1 不定义独立的账户级设备签名层级。高权限 PCR 操作由当前 generation 的 accepted device，或 recovery policy 明确登记的 quorum/signer 签发；identity root 仅承担 §3.1 的封闭 genesis/re-anchor 白名单。任何实现都不得从 DID Document 的普通 verification method 推导设备授权。

### 3.3 Recovery Secret 与域分隔子键

用户只保管一个 recovery secret；它是派生源，不是可跨用途复用的一把 recovery private key。Arkret v1 从它派生三个相互隔离的角色：代际 DID update root、稳定 recovery-session proof key、稳定 backup HPKE key。客户端恢复 UI MAY 把 recovery secret 呈现为 24 词 BIP-39 助记词，但 MUST NOT 上传助记词、BIP-39 seed、PRK 或任何派生 private key；本地 MAY 仅保留不可逆指纹用于输入校验。

24 词助记词与“至少 32-byte 均匀随机 secret”是两条互斥的**本地输入表示路径**，不是两种 wire recovery key。若产品把 raw secret 显示为 Crockford/Base32 等可抄录文本，其 codec MUST 无损往返全部 secret bits，KDF 输入 MUST 是解码后的原始 bytes，MUST NOT 是编码文本的 UTF-8 bytes。`ak.schema.key_backup.v1` 的 `recipient_method="passphrase_kdf"` 所用产品自选 backup passphrase 是另一类本地凭证；实现 MUST NOT 把它命名或解释为本节 identity recovery secret，也 MUST NOT 将其送入本节 identity recovery KDF。标准内容恢复凭证与 backup-HPKE 关系仍以 §7.5.2 为准。

24 词路径 MUST 严格按 BIP-39 对 mnemonic 与 passphrase 做 NFKD/UTF-8 处理并得到 64-byte seed；未提供附加 passphrase 时 passphrase 是空字符串。非助记词路径 MUST 输入至少 32-byte 均匀随机 secret。所得原始 bytes 直接作为 `recovery_secret_bytes`，不得先转成 hex/Base64 文本。byte-exact KDF 为：

```text
PRK = HKDF-Extract(
  hash = SHA-256,
  salt = utf8("arkret-identity-recovery-kdf-v1"),
  IKM  = recovery_secret_bytes
)

root_seed_i = HKDF-Expand(PRK,
  info = utf8("arkret/did-update/root/v1") || u64be(i), L = 32)

recovery_proof_seed = HKDF-Expand(PRK,
  info = utf8("arkret/recovery-proof/v1"), L = 32)

backup_hpke_ikm = HKDF-Expand(PRK,
  info = utf8("arkret/backup-hpke/v1"), L = 32)
```

`root_seed_i` 与 `recovery_proof_seed` 分别是独立 Ed25519 seed。`backup_hpke_ikm` MUST 作为 v1 default HPKE suite `DHKEM(X25519, HKDF-SHA256).DeriveKeyPair` 的 IKM，不得把任一 Ed25519 seed 转换或复用成 X25519 private key。对 X25519，KAT 必须区分 RFC 9180 §7.1.3 `DeriveKeyPair` 中 `LabeledExpand(..., "sk", ..., 32)` 的原始 32-byte `derived_sk`，与 §7.1.2 `SerializePrivateKey(derived_sk)` 按 RFC 7748 clamp 后的 32-byte serialized private key；不得把两种表示混为一个字段。`i` 是从 0 开始、不回绕的 unsigned 64-bit big-endian root generation；它 MUST 从已验证 canonical DID history 重建，不能信任设备本地可变计数器。Ed25519 root 公钥的 DID wire 表示 MUST 是 Ed25519 multicodec 前缀 `0xed01` 加 32-byte raw public key 后的 Base58BTC multikey。did:webvh `nextKeyHashes` 值 MUST 是 `Base58BTC(multihash(sha2-256, UTF8(multikey))))`；不得对 raw public key 直接求哈希，也不得添加 `sha256:` 前缀。实现 MUST 通过规范 KAT 逐字节验证 PRK、`root_seed_0`、`root_seed_1`、`recovery_proof_seed`、`backup_hpke_ikm`、HPKE raw/serialized private-key 表示、对应 raw public key、multikey 与 canonical `nextKeyHash(root_1)`。

本节密码学闭包由 `ak.vector.identity.recovery_kdf.v1` 执行验证；recovery secret 换代的全局 index 与崩溃续跑由 `ak.vector.identity.recovery_secret_handoff.v1` 验证。

普通 root 轮换只推进 `root/<i>`。root index 是该 DID canonical history 的**全局**单调计数，不因 recovery secret handoff 归零。recovery secret 疑似泄露时：若没有预先存在且能拒绝“旧 secret 单签”的独立 guardian/witness/组织策略，原 DID MUST 视为不可逆 compromised，停止建立新信任并用新 secret 重铸 DID；旧 DID deactivation 只能 best-effort，不能作为安全迁移前提。若存在独立策略，MUST 走可续跑的两-entry handoff：设当前 entry 激活 `root_i` 且已承诺旧 secret 的 `root_{i+1}`；先确认新 secret 保管；entry i+1 在独立策略批准下激活旧 `root_{i+1}`，并承诺由新 secret 以**全局索引 i+2**派生的 `root'_{i+2}`；entry i+2 激活 `root'_{i+2}`、承诺 `root'_{i+3}`；随后对 entry i+2 执行 §5.0.3 re-anchor、发布新 recovery-proof policy、为所有引用旧 backup-HPKE recipient 的 active envelope 建新 series 并推进 signed active-series pointer，验证后再撤销旧 policy key。不得把新 secret 的局部 `root'_0` 填入既有 DID history；恢复者从 canonical entry 数重建同一全局 index。每一步 MUST 有 durable checkpoint 并支持幂等续跑。

### 3.4 Device Key

每台设备 SHOULD 本地生成独立 device key。

device key 用于：

- 日常 Operation 签名
- Events API / sync 认证
- device-to-device pairing
- MLS KeyPackage 身份绑定

device key MUST 通过 device authorization event 或 capability grant 绑定到 principal DID。

### 3.5 Session Key

session key 是短期在线密钥，常用于 Web、SSO、临时容器或远程执行环境。

要求：

- MUST 有短失效时间
- MUST 绑定 audience / origin / service
- SHOULD 绑定 device id 或 browser instance
- MUST NOT 被用于恢复 DID 或签发长期 grant

### 3.6 Agent Key

agent key 用于 AI agent、bot、CI 或 automation。

要求：

- MUST 有明确 agent_key_scope
- MUST 有 `expires_at` 或 revocation check
- MUST 绑定 accountable actor
- SHOULD 使用 proposal / approval 约束执行高风险动作

agent key 的授权、轮换和撤销 MUST 进入可审计状态，而不能只存在于服务端配置。标准事件为：

| 事件 | 用途 | 必要授权 |
| --- | --- | --- |
| `ak.agent.key.authorize` | Payload MUST validate as `event-payload.schema.json#/$defs/agent_key_authorize_payload`，绑定 `agent_id` / `key_id` / `verification_method` / `accountable_principal_id` / `agent_key_scope` / `audience` / `issued_at` / `approval_evidence`，以及可选 `expires_at`（缺省表示不设时间过期，授权有效性由撤销链治理）。 | `ak.agent.key.authorize` |
| `ak.agent.key.revoke` | Payload MUST validate as `agent_key_revoke_payload`，绑定 `agent_id` / `key_id` / `revoked_at` / `revoked_by`；撤销的控制面基准由 Control Move 信封 `seal_basis` 表达，自被 accepted Seal 覆盖起使后续 session / protocol action proof fail closed。 | `ak.agent.key.revoke` |

v1 不定义独立的 agent key rotate 事件：key 替换统一通过 §3.6.1 的 runtime replacement re-pairing 表达。Controller-signed `ak.agent.key.authorize.payload.supersedes[]` MUST 逐项携带被替换 active authorization 的 `{key_id, authorized_event_ref}`，并与权威 reducer 接受该 Event 前的完整 active 集合 set-equal；接受同一 Event 时 reducer 原子 remove 这些 authorization dots（审计 reason=`superseded_by_repairing`）并 add 新 authorize dot。只有首次配对（接受前 active 集合为空）MUST 省略 `supersedes`；同 `key_id` re-authorization 仍是旧 authorization dot 到新 dot 的 replacement，必须携带旧 dot，不能靠 map overwrite 隐式替换。stale、遗漏或多余条目 MUST conflict / fail closed。服务端不得为满足替换语义而伪造 controller-authored `ak.agent.key.revoke` Event；`ak.agent.key.revoke` 保留给 controller 显式撤销。

**同 key re-authorization（续期路径，续期 ≠ 重配对，normative）**：controller MAY 随时对同一 `(agent_id, key_id)` 签发新的 `ak.agent.key.authorize`。`ak.component.agent.key.v1` 是 observed-remove OR-Set；首次授权写一个 authorize add dot，重新授权的同一 Control Move MUST 在其 `seal_basis` view 下 observe-remove 该 cell 的**全部 active authorize dots**，并原子加入一个 replacement authorize dot。实现 MUST NOT 按本地到达时间或 HLC 选择所谓“最新”授权。若两个 replacement Move 基于同一旧 view 并发，join 后存活多个 authorize dots，effective authorization MUST 做确定性最严格 fold：`agent_key_scope` 与 `audience` 分别取交集，`expires_at` 取最早的有限值（缺省按 `+infinity`），`accountable_principal_id` 或 `verification_method` 不一致则 fail closed。controller 可再提交一次观察全部并发 dots 的 re-authorization 收敛为单一授权。该路径不需要 pairing 仪式、不触发 supersede、不更换 key material；authorize MUST 由 controller（或其授权设备）签发，MUST NOT 由 agent runtime 持旧 key 单方面完成。renew-pairing（§3.6.1）只用于 key 丢失、疑似泄露或更换 runtime 的场景。

高风险 agent key（能写入、调用外部工具、管理 capability、读取审计材料或代表用户发起 service-call）的 grant MUST 同时有 resource selector、accountable actor、approval/proposal evidence 和 revocation freshness check；`expires_at` 是可选的附加约束，授权失效控制以撤销链与 lifecycle 级联为权威。只声明 API token 或本地环境变量而没有上述事件链的 agent key 不得用于 v1 standard operation。

#### 3.6.1 Agent runtime pairing 与 session(normative)

`ak.profile.agent_provisioning.v1` 定义了一条面向普通用户的 Agent 流程，以现有 agent key 原语为基础:

PCR create admission 必须从 durable provisioning 状态读取 prepare 锁定的 exact `initial_resolution`，再与 genesis 携带值逐字段比较；只校验请求自带值格式正确或 `project(did)==agent_id` 不足以建立 create-locked 绑定。普通 Event policy admission 与 delegated Agent envelope admission 两条路径都必须使用同一份保存值。

- **Provisioning** (`POST /_arkret/self/agents`, operation `ak.self.agent.command.provision.v1`) 是闭合的 prepare/commit operation，其外围由 controller 先发布 PCR-independent DID entry 0、后发布 PCR binding entry 1。controller MUST 先按 §3.6.3 可恢复地持久化 WebVH 更新密钥，并发布不含 PCR binding 的 Agent inception。`phase=prepare` 只校验 controller recovery、caller-supplied `did` 的 accepted entry 0 与 controller delegation等先决条件，并返回 exact `initial_resolution`、controller PCR 与 delegation ref；它 MUST NOT 生成 Agent DID 或私钥，也 MUST NOT 分配 `principal_control_realm_id`（该值只能由 controller 从本地冻结的 genesis create 派生），也 MUST NOT 发布 durable Agent/PCR、accountability、selector、pairing、grant 或其它可观察副作用。controller 必须逐字核对 `initial_resolution`，并以 `(agent_id, controller_id, requested_scope)` 重算返回的域分离 `requested_scope_digest`，不匹配时停止。随后 controller MUST 调用 `arkret-rust-sdk` 的统一 authoring API 生成恰好一个 controller-owned `ak.agent.provision` `EventInitialSubmission`；其闭合 payload 同时绑定 allocation、controller delegation、`accountability_scope=agent_operator`、selector、`requested_scope_digest` 与前向声明的 `principal_control_realm_id`（§3.6.3），不含内层 proof。Event `actor_id` MUST 是 authenticated controller、`realm_id` MUST 是返回的 controller PCR；Event proof 是唯一签名。`phase=commit` 原样携带服务端 allocation、完整 private `requested_scope` 与该 submission；Station 必须通过普通 Event schema/proof/authz/frontier/reducer admission 接受它，不得用 service key 代签、接受 `dev-proof`，或绕过 admission 直接写 canonical store。一次 accepted reducer transaction MUST 原子写入 provision、accountability、selector 与 realm-id claim 四个 cell；不得暴露部分完成状态。该 Event durable accepted 只把 outcome 推进到 `status=awaiting_pcr_genesis`；genesis accepted 后推进到 `status=awaiting_did_binding`；只有 controller 使用 inception 预承诺 key 发布的连续 entry 1 也 accepted、且其唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 精确匹配 create-locked 四元组，才创建 pairing handle 并返回 `status=complete`。完整 `requested_scope` 始终保持 controller-private，不得进入公开 DID history 或 durable Event。精确 commit 重试以 allocation 与 submission 的 Event id/canonical bytes/publication evidence bytes 为身份，MUST 返回该身份**当前**的 durable outcome（依次为 `awaiting_pcr_genesis`、`awaiting_did_binding` 或同一 complete outcome）；同 Event id 不同 bytes 或不同 evidence MUST conflict。恢复 MUST 重放同一 submission 与已持久化的 exact DID operation，并依靠各自 admission 幂等完成，MUST NOT 另造 Event id、proof、lease、receipt 或重复 fact。
  `requested_scope` 是该 Agent key/session 的**全局硬上限而不是授权**：`actions[]` 中的内容 action 只表示以后在某 Realm 中可被单独 grant 的最大 action 集；省略的内容 action 不能由 Realm / Circle / Strand grant、session 或 participation gate 补回。operation/service resource 约束服务面；显式内容 resource selector 只进一步收窄以后允许附加的 Realm 内容资源。Provisioning MUST NOT 从 `requested_scope` 物化 `ak.capability.grant`；后续 grant 必须满足 `grant.actions ⊆ requested_scope.actions` 并继续按 AND 收窄。Participation selection 是独立的动作时 deny gate，不属于 provision commitment。complete 返回 Agent PCR binding、`requested_scope_digest` 与一次性 `pairing_request_id` + `pairing_code`；`pairing_code` MUST 由 CSPRNG 生成且熵不少于 128 bit。controller E2EE client 在提交 §3.6.3 的 genesis 时按 §4.1 本地生成 Agent PCR MLS state 并提交 Agent profile Event，但不得把该 active state 上传为 backup。Fresh endpoint 随后只能通过标准 KeyPackage/Add/Welcome 进入 group；`mls_history` 仅可恢复合法 history-secret ranges（§7.5.6）。服务端、Account Authority 与 Station MUST NOT 生成或短暂持有 Agent PCR MLS private state。流程不写入独立 `ak.self.agent.command.provision.v1` Event，也不得在首次 runtime pairing 前伪造或预写 `ak.agent.key.authorize`。
- `requested_scope` 在 v1 provision request 中 MUST 存在，且 Agent principal 创建后 immutable；实现不得把省略解释为 unconstrained 或 deny-all，也不得通过 renew-pairing、同 key re-authorization、Realm 加入或 policy 更新修改它。需要改变（包括扩大）该全局 ceiling 时必须 provision 新 Agent principal。后续 `ak.agent.key.authorize.payload.agent_key_scope` MAY 比它更窄，但 MUST 满足 actions/resources/constraints 的 selector-narrowing 子集规则；不得要求两者完全相等。Receiver 不得信任 service-local row 声称的 ceiling：必须按 authorizing object 的 accepted-at 解析 Agent DID history，验证 §4.1 的公开 digest commitment，并取得有效的 `ak.schema.agent_requested_scope_disclosure.v1` 私有披露，重算 digest 后再求子集。具体 digest、资源覆盖和 mandatory constraint 规则以 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 为准。
- **Runtime key pairing** (`POST /_arkret/gate/account/agent-key-pair`, operation `ak.gate.account.command.pair_agent_key.v1`):agent runtime 本地生成 key pair、提交 public key + proof-of-possession + 可选 `runtime_attestation`。请求还 MUST 携带 controller 签名的 `requested_scope_disclosure` 与 ordinary `EventInitialSubmission` 形态的 `authorize_event`。服务在 accepted-at current frontier 验证 controller/Agent authority、pairing handle、DID binding、scope disclosure、proof-of-possession、replacement exact set 与 Event proof；不得要求 `mls_history` 中不存在的 Agent PCR active snapshot，也不得以 `pcr_recovery.status` 作为 pairing gate。首次调用只把 authorize Event durable 入库并返回 `awaiting_accepted_frontier`；覆盖该 Event 的 Agent-PCR successor Seal accepted 后，以 byte-identical request 重试才可原子激活、消费 handle 并签发 session。Replacement 必须在同一 Event 中 exact supersede 全部旧 authorization，旧 session 在 freshness window 内失效。

  当 `gate_account_base_url` 的 Account Authority 与保存 Agent pairing record / Agent PCR 的 Station 分离时，Account Authority MUST 以完全相同的 `AgentKeyPairRequestBody` 将同一 `ak.gate.account.command.pair_agent_key.v1` 委托到该 Station 的 canonical `POST /_arkret/gate/account/agent-key-pair`，使用部署内 S2S bearer 或 §3 HTTP Message Signature 认证，并携带 `Idempotency-Key=authorize_event.event.event_id`。下游 MUST 独立重做 current pairing、runtime PoP、controller Event proof、在线 typed request context、Agent PCR / delegation、scope 与 replacement 校验；不得信任上游“已验证”布尔值。该委托是同一标准 operation 的部署内执行，不是新的 fan-out operation；实现 MUST NOT 用任何非注册端点或自定义 queue envelope 承载这项协议职责。Account Authority MUST 透明转发下游的两阶段 outcome；只有下游返回与 `authorize_event.event.event_id` 一致的 `authorize_event_ref`、`activation_state="active"` 且 activation 已 durable 后，才能把本地 authorization 标为 active。`awaiting_accepted_frontier`、本地入库或入队均不构成激活成功。
- **Lifecycle、readiness 与 presence 正交（normative）**：通用 Agent list/get view 只暴露 [`../models/actor.md` §3.3](../models/actor.md) 的三轴；`key_state` 不重复 lifecycle/readiness/presence，也不包含 `runtime_state`。后者只允许作为 pairing poll 的 operation-specific 诊断，从被轮询 handle 与 key facts 机械派生：无 active accepted key 且存在未过期 bootstrap handle → `pending_runtime_key`；无 active key 且 bootstrap handle 已过期 → `pairing_expired`；有 active key 且无未消费 replacement handle → `ready`；有 active key 且存在未过期 replacement handle → `replacing`。它 MUST NOT 被直接写入或提升成产品状态，并必须映射进 generic readiness blocker（无 key → `runtime_key_missing`，open handle → `pairing_open`）。session 签发仍由 lifecycle 与授权链治理；poll 的 `replacing` 不改变旧 key 的 session 语义，真正安全边界是 pair commit 的原子 supersede。
- **Pairing 失败清理**:仅适用于从未完成首次 key 授权的 Agent。`pairing.expires_at` 到达且未完成 pairing 时，服务关闭并省略 open-handle fields；generic readiness 保持 `not_ready` + `runtime_key_missing`，对过期 handle 的 pairing poll 报 `runtime_state=pairing_expired`。服务不得因此创建、撤销或改写任何 Realm grant，也不得改变 lifecycle 意图。已持有 authorized key 的 Agent 的 replacement handle 过期没有任何副作用：lifecycle、既有 key 与 grant 均不变，open fields 消失，readiness 移除 `pairing_open`；其 poll 不得报 `pairing_expired`。
- **Pairing 续期** (`POST /_arkret/self/agents/{agent_id}/renew-pairing`, operation `ak.self.agent.command.renew_pairing.v1`):controller MAY 对无 active accepted runtime key 的 bootstrap Agent或已持有 active authorized key 的 Agent(lifecycle `active` 或 `paused`)原地重开 pairing；`deactivated` MUST 拒绝。每个 Agent 同一时刻至多一个 open pairing handle。
  - 服务 MUST 签发全新的一次性 `pairing_request_id` + `pairing_code` + `pairing.expires_at`，并 MUST 使该 agent 此前签发的所有 pairing handle 永久不可解析(与过期 handle 一致的 anti-enumeration 语义:handle 是一次性的，principal 不是)。
  - 响应以 `pairing_mode="bootstrap"|"replacement"` 固化本次分支；不得返回或依赖从 `mls_history` 推断的 `pcr_recovery` active-snapshot 投影。后续 pair commit 以 current authority、PoP、accepted frontier 与 replacement exact-set 为闭合 gate。
  - **Bootstrap 重开**(无 active accepted runtime key):续期后返回 `pairing_mode=bootstrap`，通用 readiness 含 `runtime_key_missing` 与 `pairing_open`；不得创建、撤销或重发 Realm grant。
  - **Runtime replacement**(已持有 active authorized key,lifecycle `active` 或 `paused`):用于 runtime 迁移、key 丢失恢复与例行换钥。重开 pairing 返回 `pairing_mode=replacement` 并使通用 readiness 含 `pairing_open`，MUST NOT 改变 lifecycle 意图；既有 key 与 grant 保留。新 pairing 完成时按上文 supersede 语义原子替换全部旧 key，lifecycle 意图原样保留。怀疑旧 key 失陷时 controller SHOULD 先显式 pause。capability grants 绑定 Agent principal 而非 key，不受替换影响。approval UI MUST 明示 replacement 后果。replacement handle 过期只清除 open fields / `pairing_open` blocker，lifecycle、既有 key、grant 均不变。
  - 若该 agent 的 slug 已被同一 controller 的其他 active / open agent 占用，续期 MUST 以 `failed_precondition` 拒绝。
- **Agent runtime authentication**:复用 `POST /_arkret/gate/account/session-grants`(operation `ak.gate.account.command.issue_session_grant.v1`),通过 `proof.proof_kind="agent_key_proof"` 分支区分。Auth Server MUST 维护独立 schema branch、独立 proof validator;不得让 `agent_key_proof` 走 password / OIDC / passkey 的 validator fallback。请求侧 `agent_scope_request` 是 `ak.profile.agent_auth.v1` overlay,签发后的 scope MUST 物化为 capabilities.md 已注册的 `allowed_tracks` / `allowed_strand_ids` / `allowed_data_labels` / `allowed_endpoints` 等 typed constraints。Auth Server 求交前 MUST 取得已验证、与自身 verifier/audience 及当前 accepted-at DID digest 匹配的私有 `requested_scope_disclosure`；它 MAY 使用 pairing 时建立或经 authenticated confidential S2S 转移的 verifier-private evidence，请求也 MAY 在该 agent 分支携带新 disclosure。仅有 service-local Agent row、公开 digest 或由 agent runtime 自报的完整 scope 时 MUST fail closed。
- **Agent runtime capability 选择与最小服务面（normative）**：唯一机读规则见 `../../artifacts/registry/agent-runtime-scope-registry.json`。实现 MUST 仅从 accepted immutable provision `requested_scope.actions[]` 按 exact operation token 选择 capability：某 capability 的任一 `activation_operations` 出现即按 registry 的 `selection_rule=any_activation_operation_present_in_immutable_provision_actions` 选择它。不得使用 prefix/subsumption、内容 action、endpoint path、runtime attestation、Realm/grant/participation、产品 preset，或 key/session scope 重新选择或取消 capability；lower layer 出现 provision 未含的 activation operation 仍按既有 subset 规则拒绝，不能升级 immutable intent。`interactive_chat.activation_operations` 是 subscribe、scan、Event frontier、Seal frontier、submit 五项完整 atomic floor；任一项出现，provision、accepted key authorization 与 requested/current session 三层都 MUST 覆盖全部 `interactive_chat.mandatory_operations`。`e2ee.activation_operations` 是 Agent KeyPackage upload/consume/revoke；任一项出现，三层都 MUST 覆盖 `e2ee.mandatory_operations` 的 KeyPackage upload。Server 只诊断并拒绝缺项，MUST NOT 自动补 operation；controller authoring 可在签署 provision 前用同一 registry 规则展开 floor。Event frontier 只提供 actor causal frontier，Seal frontier 是构造每条 DataEvent `seal_ref` 与 Control Move `seal_basis` 的唯一来源，两者不得替代。内容层仍须独立覆盖 `ak.event.read`、`ak.message.create` 并取得目标 Realm / Strand 的有效 grant；submit service ceiling 本身不授予内容写权限。在线 presence 与延迟/离线发布分别按 registry 的 feature additions 增加 operation。在线 Event 直接在 submit transaction 读取当前 admission state，不需要前置 lease；显式离线 lease 只延长已验证 authority basis 的有限窗口，不提升内容权限。

三层缺项 MUST 使用从 authoritative provision scope 导出的同一 selected capability 集，按最高缺失层 fail closed，且不得静默扩权：provision prepare/commit 在创建或推进 reservation 前只评估 provision 层，缺项返回 `failed_precondition` / `agent_provision_scope_migration_required` 并 provision 新 Agent；key pairing 先评估 provision、再评估 proposed `agent_key_scope`，分别返回 migration 或 `failed_precondition` / `agent_key_scope_reauthorization_required`，Account Authority 不得先持久化 queued authorization 再丢失下游精确 reason；session issuance/refresh 依次评估 provision、accepted key、requested/current session，前两层均允许而 session 缺项时返回 `failed_precondition` / `agent_session_scope_refresh_required`。key 只可在 provision ceiling 内重新授权或轮换，session 只可在两层 ceiling 内重签；两者均不得扩大上层 ceiling，session 也不能通过少报 activation operation 使 capability 消失。
- **Agent MLS runtime endpoint 与持久化**：pairing accepted 后，runtime MUST 以 `(agent_id, exact agent_verification_method, current agent_key_authorize_event_id)` 创建或恢复 Agent MLS endpoint，并在发布任何 KeyPackage 前持久化 identity/private KeyPackage state。Agent branch 不创建、不携带也不从 session/token 派生 synthetic `device_id`；它与 human-device branch 在 KeyPackage、claim、Welcome、durable receipt 与 consume 中严格 XOR。runtime MUST 使用 current authorization 对应的同一 Ed25519 private signing capability 构造 MLS identity；该 private key MAY 位于不可导出的硬件或进程外 signer 中，协议不得要求导出 seed。MLS LeafNode signature key、§9 upload publish signature与 `ak.agent.key.authorize.verification_method` 必须是同一 key。authorization replacement 完成时，旧 session 必须失效，旧 authorization 下 published/claimed 未消费 pool 必须 revoke，旧 Welcome/claim 必须拒绝；runtime 以新 verification method/key/current authorize Event 重建 identity/pool。Welcome routing与 consume只保留上述 Agent authority 三元组，不得 fallback 到 controller device、普通 device authorization 或假 Device endpoint。canonical signing bytes以 [`device-lifecycle.md` §9.0](../crypto-media/device-lifecycle.md) 为唯一合同。
- **Session TTL**:Agent session grant 默认最大 TTL SHOULD 为 15 分钟；若 deployment profile 显式声明更长，不应超过 60 分钟。Controller 进入 `deactivated` / `suspended` 后，其 accountable agent 的 active sessions MUST 通过 account lifecycle / revocation 链失效。单次 `agent_key_proof` / refresh proof 的接收窗口 MUST 与已签发 session TTL 分离：proof 的 `expires_at-issued_at` MUST `<=300s`，用于限制一次性证明的重放窗口；Account Authority 不得因此把成功签发的 Agent session TTL 静默收窄到该 proof 剩余窗口。runtime SHOULD 在 grant 到期前自动轮换；正常轮换不得要求 controller 在线或人工批准。
- **Key authorization lifetime 与 session TTL 分离(longevity-safe)**:`ak.agent.key.authorize` 是可供多次 session 签发复用的 durable key authorization。其 `expires_at` 可选:缺省表示不设时间过期，有效性完全由撤销链治理(`ak.agent.key.revoke`、pause / deactivate、controller lifecycle 级联);声明 `expires_at` 是部署或 controller 的附加策略选择。Account Authority MUST NOT 把上述单次 Agent session grant 的 15 分钟默认 TTL 或 60 分钟上限复用为 `ak.agent.key.authorize` 的有效期上限；每次 session 签发仍 MUST 独立检查 authorization 未撤销、未过期(若声明了 `expires_at`)且 scope / audience 匹配，并把签发出的 session TTL 限制在上一条的边界内。
- **授权链无静默悬崖(normative)**:配对完成后,agent 的持续在线不得依赖任何需要人工续期的定时器。默认配置下，使 agent 失去授权的路径只有:显式 kill switch(pause / deactivate / `ak.agent.key.revoke` / `ak.capability.revoke`)、controller lifecycle 或 Realm membership 级联、以及部署 / controller 显式声明的可选 `expires_at`。Session 由 runtime 持 authorized key 自动重签，不构成失效面。session 签发因授权链异常被拒时,Auth Server MUST 使用统一错误信封返回机器可读 reason,使 runtime 能提示 controller 介入；其中 key authorization 已过期导致的拒签 MUST 使用 reason=`agent_key_authorization_expired`,MUST NOT 混入 `proof_invalid`——runtime 必须能区分"proof 构造错误"与"需要 controller 续期"。对任何非 terminal 的 agent,controller 始终可通过 renew-pairing + grant 重授权恢复，恢复路径本身 MUST NOT 过期。**异步续期与提前提醒**:声明了 `expires_at` 的 key authorization,runtime SHOULD 在到期临近时主动发起续期请求（见 §3.6 同 key re-authorization）;controller 无需保持在线——到期前任意时刻、任一已授权设备签发一次新 authorize 即可完成续期。不接受此运维依赖的部署 SHOULD 不声明 `expires_at`(缺省即无此依赖);协议不定义无人批准的自动续期。
- **High-risk approval**:Auth Server MUST NOT 给 agent runtime 展示 CAPTCHA / OTP 页面；需要人类批准时返回统一错误信封 `error.code=claim_required`，并令 `error.details` 严格匹配 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`：`reason_code=human_approval_required`、`approval_request_id=<opaque>`。Controller 在带外 UI 完成批准，产生 capability / delegation / approval event,agent retry 时引用该 event。该分支由 `ak.vector.agent_auth.human_approval_required.v1` 固化。
- **E2EE access**（conformance vector `ak.vector.agent.mls_keypackage_authorization.v1`）:Agent MUST 作为独立 MLS member 参与，不得伪装成 controller 的 delegated device。Agent MLS KeyPackage MUST 由其当前 active accepted `ak.agent.key.authorize.verification_method` 对应的同一 Ed25519 key 生成 MLS LeafNode signature key并签署发布 transcript；claim / Welcome 的 claimed-endpoint trust binding MUST 使用 `agent_key_authorize_event_id` 引用该 authorize Event，并携 exact Agent method，且与普通设备使用的 `device_id + device_authorize_event_id` 精确互斥。Agent 分支禁止 `device_id`。authorize 被 revoke、supersede、过期或 key 不匹配时必须使未消费 claim fail closed，从而使 key authorization、session proof 与 MLS membership 落在同一审计链。

##### Agent signing-key binding 与 portable signer evidence（normative）

每次首次 pairing、replacement pairing 或 same-key re-authorization 接受时，controller MUST 在同一批准动作中签发 `ak.schema.agent_signing_key_binding.v1`。其公开字段只允许 `agent_id`、与 authorize payload byte-identical 的 `agent_key_id`、完整 `verification_method`、raw Ed25519 `public_key`、`public_key_digest`、`agent_key_authorize_event_id`（完整 Event ID）、`issued_at`、仅在授权实际有期限时出现的 `expires_at`、`controller_id` 与 `controller_proof`。authorize Event 的 payload 只承诺排除 `agent_key_authorize_event_id` 与 `controller_proof` 的 binding core digest；receiver 接受并得到完整 Event identity 后才 materialize 这两个字段，禁止在 Event authoring 前预铸本 Event ID。requested scope、`agent_key_scope`、audience selector、pairing code/request、runtime PoP、attestation、session 与 capability material 不得进入公开 binding。

controller proof 的 signing input 固定为：

```text
UTF8("ak.agent_signing_key_binding.v1\n")
||
JCS(binding object with controller_proof.jws omitted)
```

`controller_proof` MUST 按 `issued_at` 时点的 controller DID/delegation 与 device authorization 验证。binding 的
`issued_at`、`expires_at`、agent/key/method/controller必须与 authorize payload逐字相等。`agent_key_id` MUST 等于
authorize payload 的 `key_id`；`verification_method` 去除 fragment/query 后 MUST 与 `agent_id` byte-identical；
raw key必须解码为恰好32 bytes。authorize payload、公开 binding 与 runtime 审批状态中的
`public_key_digest` MUST 只对这32-byte raw Ed25519 key调用 SDK唯一
`agent_signing_public_key_digest` helper计算，不得hash PublicKey DTO、JWK、multibase或hex文本。`signing_key_binding_digest`只对**排除 `agent_key_authorize_event_id` 与 `controller_proof` 的 binding core**做RFC8785/JCS后SHA-256；controller proof签名transcript则使用上文
独立domain tag并省略`controller_proof.jws`。两种digest与proof transcript是三个互斥domain，不得交换、二次
hash或形成自引用。对应authorize payload必须分别承诺两digest；Event/key/method/controller/time/expiry或任一
digest不一致必须拒绝，service不得替换disclosure或代controller补签。

上述公开授权 digest 与 runtime request binding 中的私有请求 digest 是两个不同 domain。后者只在
`ak.agent.runtime_key_binding.v1` 内使用 `agent_runtime_public_key_digest` 对完整
`agent_runtime_approval_request_body.public_key` DTO 做RFC8785/JCS SHA-256，因此覆盖`kty`、`kid`、`alg`与`key`；
它不得写入 authorize payload、公开 signing-key binding或审批状态，也不得与 raw-key digest直接比较。pairing
接收方必须解码两边raw key逐字匹配（或调用SDK显式的runtime-request转换helper），再分别验证两个digest domain。

`ak.component.agent.key.v1` 的 registered reducer projection 是 portable state witness 的唯一状态来源，不能只把 key Event 写入历史。cell subject MUST 使用 SDK `composite_subject([agent_id, key_id])`，不得用字符串拼接或 diagnostic subject。每个 `ak.agent.key.authorize` 的 reducer MUST 先对 `payload.supersedes[]` 逐项在对应旧 key cell 投影 `remove(tag=authorized_event_ref 对应的 observed canonical Event dot)`，再在当前 key cell 投影 `add(tag=canonical_event_dot(event_id, write_index), value=完整 authorize payload)`；authorization 元素的稳定 tag 是 [`event-and-patch.md` §2.4.2](../models/event-and-patch.md) 定义的 `<event_id>:<write_index>`，绝不是裸 `event_id`。`ak.agent.key.revoke` MUST 在 `seal_basis` 观察到的对应 key cell 中移除全部 active authorize dot，并加入 `add(tag=canonical_event_dot(event_id, write_index), value=完整 revoke payload)` 的 transition marker；marker 只保留可见证的撤销边界，不是 active authorization。Station MUST 在接受前从 `kind + payload` 重建并逐项校验这些 canonical writes；write 缺失、多余、cell/tag/value/顺序不一致均须 `reducer_projection_failed`。这样 authorize、same-key re-authorization、replacement supersede 与 explicit revoke 都能从签名 Seal 的 resolved cell 独立证明，不依赖服务端私有投影。

`ak.schema.agent_signer_evidence.v1` 是 structural XOR：顶层只能是 `verification_mode=current_admission` 或
`verification_mode=historical_event` 两种 closed object 之一，二者字段集合不同，不能通过改 tag 或增删一个
frontier 互换。共享 `admission_evidence` 只含 `agent_authority_snapshot`、隐私最小化的
`controller_account_gate_attestation` 及无自引用的 `admission_evidence_digest`。raw public key不是秘密；Agent/controller
private key、MLS private state、服务本地 `account_id` 与 raw account cell 永不进入 portable evidence。

`agent_authority_snapshot.core` 在 Agent Principal Control Realm 的一个 exact signed Seal view 中同时承载完整
`signing_key_binding`、key authorization、key state witness 和 Agent lifecycle witness。`snapshot_digest` 只对 core
做 RFC 8785/JCS SHA-256；`lease` 由该 PCR 的权威 service DID 在独立 domain
`ak.agent_authority_snapshot.v1` 下签名并逐字绑定 authority、verification method、snapshot digest 与时窗。
snapshot core 的 `seal_lineage[]` 必须是把 key/status witness Seal 连接到 `frontier_seal_id` 的完整、无重复
predecessor closure；unknown、fork、跨 Realm、缺 predecessor 或签名无效均拒绝。

key `cell_ref` MUST 精确等于 SDK 从 `(agent_id, agent_key_id)` 派生的 `ak.component.agent.key.v1` composite
subject；`cell_value` 是 closed、canonical sorted OR-set entry array，每项 tag 必须解析为 accepted Event 的 canonical
`<event_id>:<write_index>` dot，value 必须是 schema-valid authorize/revoke payload。Agent lifecycle `cell_ref` MUST
由 `agent_id` 派生，`cell_value` 是 closed lifecycle 值；`accepted_status_event`、provenance、registered reducer write、
Seal delta/lineage 和 state leaf 必须互相重算一致。首次 active 的唯一 provenance 是 Agent delegated PCR
genesis `ak.realm.create` 在 `payload.object.purpose == "agent_control"` 上的条件写（subject 取
`envelope.actor_id`，`uninitialized -> active`，见 §3.6.3）；服务私有 row、FSM 默认值或
organization-governed PCR 都不能合成首次 active witness。

每个 state witness 都必须携带完整 signed Seal、closed `cell_value`、leaf digest/index/count 与 inclusion proof。
receiver 验证 Seal id/notary signature/Realm/lineage，以 canonical
`{"cell":cell_ref,"state":{"value":cell_value}}` 重算 leaf，再按 §6.2.2 odd-tail promotion 重建 `state_root`。
缺 signed Seal/value、cell/subject/actor/controller/event dot 错配、proof 剩余/不足或 root 不等均 fail closed。

`controller_account_gate_attestation` 由 Account Authority 在 domain `ak.controller_account_gate.v1` 下签名，只公开
controller principal `did_core_id`、closed active/inactive eligibility、六值 account status、`basis.kind` 对应的最小
binding/status digest 与时窗。`account_binding_default` 表示权威私有 binding 上尚无更严格 accepted status head；
`account_status_event` 绑定真实 status Event/frontier digest。`status=active` 当且仅当 `eligibility=active`；其它状态
全部 inactive。由于 portable evidence 不公开 service-local account identity，任何 `account_id`、raw account cell 或
caller 自报 active 布尔值都是 schema violation。

Agent authority **不能自行合成这一层 evidence**。组装 current admission evidence 或签发 historical admission receipt
之前，它 MUST 以 authenticated S2S 身份调用
`ak.gate.account.command.issue_controller_gate_attestation.v1`，提交 closed
`{request_id, principal_id, agent_authority_id, agent_authority_resolution}`。后者携 current signed
`ServiceResolutionRecord`、adapter-discriminated method evidence 与其认证的 normalized DID Document；Account Authority
MUST 独立重做 method evidence、document digest、record proof/currentness、`project(did)` 与 active assertion key 校验，
然后才可用同一 keyid 验 RFC 9421。签名 MUST 覆盖 method、target URI/path、Content-Digest、
Source/Destination-Service-ID、operation id 与 request id。DidCoreId、URL、bearer 或 caller 自报 public key 均不是验签钥匙来源；
bearer 只能作为附加部署门。`agent_authority_id` MUST 与请求的 verified source
service identity 逐字相等。Account Authority 还 MUST 要求 `agent_authority_id` 等于 controller account authority pair 的 `station_id`。随后只从本地 authoritative account/device state 选择 basis；未知 principal、source/service 不一致与无权 caller 统一返回不可枚举的 `not_found`，不得泄露 account status。attestation 时窗 MUST 不超过 300 秒；producer 不得用
service-local cache row、session introspection、controller 自报状态或过期 attestation替代。该 attestation 只是短 TTL
controller-lifecycle snapshot，可在其时窗内被同一 producer复用，故不携 operation/request digest/audience/challenge；
每个 `current_observation` 与 outer attestation 必须把它的 digest 重新绑定到 exact request context，裸 gate 单独跨请求
重放不构成有效 signer evidence。exact issuance request replay 在保留期内
返回 byte-identical outcome；同 request id 异 canonical intent 为 `duplicate_conflict` 且零签发。该 S2S carrier 只补齐
Account Authority-owned gate，不验证或替代 Agent PCR snapshot、key/lifecycle witness 与 outer attestation。

current 分支必须携带 `current_observation`，逐字绑定 operation/request/verifier/audience/challenge、Agent snapshot
digest、key/status Seal 与 controller gate digest。validator MUST 要求 `operation_id`、`request_digest`、`challenge`
与当前实际请求完全相同，`verifier_id` 与实际执行验证的 authenticated service DID 相同，`audience` 与目标 operation
的实际 audience 相同；任一字段不得由 evidence 自报后直接采信。observation 的 snapshot digest、key Seal、status Seal
与 controller gate attestation digest MUST 分别逐字等于同一 `admission_evidence` 中被验证对象的实际值。
outer attestation 的 source service MUST 是该 Agent PCR 的预期 authority service，并且其 proof 必须覆盖整个 tagged
evidence。verifier-now 必须同时位于 outer attestation、Agent snapshot lease、
controller gate attestation 和 current observation 的时窗内，且 key、Agent lifecycle、controller account 三层均
active；pause/deactivate/revoke/supersede/expire/conflict或任一 stale/mismatch 均拒绝新操作。current object 在
historical API 或 Event 历史验签路径结构性非法，也不得跨 verifier、audience、operation、request 或 challenge 重放。

historical 分支必须携带由实际接收 Station 在 Event accepted 时签发的
`ak.schema.agent_signer_admission_receipt.v1`。receipt 在 domain
`ak.agent_signer_admission_receipt.v1` 下闭合绑定 suite-bearing Event ID/Realm、origin `station_admission.accepted_at`、
receiver `accepted_at`、Agent/key method、origin 冻结的
`producer_signer_resolution_evidence_ref/digest` 与 receiver。Event digest 从 ID 解码，并覆盖 Event 自身的 `seal_ref`、
`seal_basis` 或 anchor 形态，因此 receipt 不重复携带一个对 Data Event、Control Move 和 anchor 含义不一致的
`event_admitted_seal_id`。
receipt 的 `receiver_id` MUST 与实际接收并承诺该Event的destination service相同，receipt proof必须由该
destination 在 `accepted_at` 有效的 registered verification method验证；查询方不得用source service或 current head
document 中的 method 替代。v1 不新增 historical service-resolution endpoint：既有 current signed
ServiceResolutionRecord 的 WebVH method-history evidence 已携带完整 log，materializer 与 verifier 必须先验证该完整
carrier，再从 log 选择 `accepted_at` 的 exact normalized document；did:key 直接按不可变 identifier 展开，mutable
did:web 继续 fail closed。current record URL 只是取得完整已签 carrier 的 transport locator，不使 head document 成为
历史 key 的权威来源。历史 verifier
必须从原 Event admission proof 取得并逐字复核 producer evidence pair，按其 digest 从 CAS 读取 byte-exact
`CurrentAdmission` root，只复用其中冻结的 `admission_evidence`；不得由 receipt 自报 snapshot，也不得读取当前状态
重建。verifier 在 `producer_accepted_at` 检查当时 snapshot lease和account attestation有效，且被冻结的三层 basis
均 active；不要求这些短期证明在 verifier-now 仍有效。删除 receipt、替换任一 basis、拿 later paused/deactivated
witness 冒充 admission witness、或把 historical object用于新 admission均拒绝。

key interval、Agent lifecycle 与 controller account lifecycle 是三个正交 AND gate。key revoke/supersede 只由真实
`ak.agent.key.*` transition witness表达；parent pause/resume/deactivate或account状态变化不得伪造 key transition、
不得改写 key authorization。Agent PCR 与 account authority 属于不同 DAG，frontier 不可跨 Realm 排序，协议明确
否决“取最早 terminal frontier写入单一 valid_until”的做法。历史有效性只取决于 destination-signed receipt 固定的
三项 admission-time basis；后来任一 gate 变化只阻止新 admission，不追溯抹除此前合法签名。

outer attestation 在 domain `ak.agent_signer_evidence.v1` 下签整个 tagged evidence（只省略 outer_attestation 自身）
的 JCS digest，防止 mode/context/snapshot/receipt拼接；它不替代底层 controller proof、Seal、snapshot lease、Account
Authority proof或receipt proof。直接 evidence query 与 federation transport另用 RFC 9421 HTTP Message Signature
覆盖完整 content digest、operation id与双方 service/session binding，不把 HTTP Signature header 嵌回 body形成环。
current branch 的 outer 使用 `issued_at/expires_at` 短时窗；historical branch 使用 closed
`attested_at` 且没有 verifier-now TTL。`attested_at` MUST 是 Agent Authority 实际签署 historical outer 的时刻，
不得回填为 receipt `accepted_at` 或从 selector 派生。历史 verifier 必须从同一完整 ServiceResolutionRecord carrier
的 method-history evidence 选择 `attested_at` 时 Authority 的 exact document 与 outer method；该 carrier 也必须能够在
原 snapshot/lease 的签发时刻解析其内层 Authority method，不要求两次 method 相同。之后 key rotation、Agent key
revoke、Agent pause/deactivate 或 controller account terminal 不得使已经合法组装的 historical root 追溯失效。

Historical root 的 content digest 是该次首次物化的内容地址，不是 selector tuple 的确定性函数；真实
`attested_at`、签名随机性或并发首次尝试可以产生候选 digest。协议唯一性与幂等只由已登记 selector tuple 承担：第一份
成功发布的完整 root 胜出；同 tuple + byte-identical receipt 的任何重试 MUST 在签名前返回已存 root/no-op，不得重新签署；
同 tuple 异 receipt 或试图覆盖已存 root仍为 `duplicate_conflict`。因此无需伪造确定时间，也无需 outer renewal、root
replacement 或第二套 generation 协议。

`revoked`、`superseded`、`expired`、`conflicted`或 admission-time 任一 parent inactive 是确定性拒绝；evidence/receipt
缺失、时窗不满足或网络失败是 `Unresolved/Stale`，绝不得提升为 Verified。启用
`ak.profile.key_transparency.v1` 时还必须验证 inclusion/consistency/witness proof。完整 transcript 与正负矩阵由
`ak.vector.agent.signer_evidence_binding.v1` 固化；historical materialization 的 selector tuple exact replay /
`duplicate_conflict`、`attested_at` 长期验证与 receiver key rotation 由
`ak.vector.agent.historical_evidence_materialization.v1` 固化。

任何缺少 `signing_key_binding_digest` 证据的 authorization 都是 unresolved，服务端不得从 session row 合成证书，也不得提升为 Verified。客户端 MUST 显示 `verification_pending`；controller MUST 通过 same-key re-authorization 产生 replacement authorize Event 与完整 v1 binding，runtime key MAY 保持不变。
- **Sidecar exposure 披露**：pairing approval UI 必须说明，建立 Agent ownership 本身不会把 Agent 加入任何
  Sidecar。只有该 Agent 后来成为某个 exact Realm 的 active member 时，才会自动进入该 Realm 对应 Sidecar
  的派生 `desired_agent_ids`，并在该 Sidecar 自己的 MLS reconciliation 完成后进入 `effective_agent_ids`
  和取得 future epoch 内容；这不会影响 controller 在其它 Realm 的 Sidecar。该变化来自 accepted ownership、
  lifecycle 与 Realm membership frontier，不依赖 UI 确认，也不存在需要调用方维护的 Sidecar roster 字段（见
  [`../models/sidecar.md` §5](../models/sidecar.md#5-参与者与有效访问)）。
- **Lifecycle**: ak.self.agent.command.pause.v1 / resume / deactivate 写入唯一 lifecycle 轴。pause/resume/deactivate 都是写入 ak.component.agent.status.v1 的 Control Move，authoring frontiers 只由 envelope seal_basis 表达。Pause 保留 durable state 但拒绝新 session；Auth Server MUST 在 ≤60 秒的独立 freshness window 内对已签 session fail closed。Deactivate 是 terminal，只提交一个 controller-authorized lifecycle Event；accepted 后 lifecycle=active 成为所有 runtime key、session、open pairing handle、capability grant、KeyPackage、presence 与未来 Event submission 的不可绕过 AND gate。历史 child Event 保留审计，显式 ak.agent.key.revoke / ak.capability.revoke 仅用于 parent 非 terminal 时的定点撤销。服务可异步 cleanup，但不得以 cleanup 成败阻塞 deactivated。所有 open pairing handle 永久不可解析；replacement pairing 与 terminal status 并发时，以 accepted status frontier 为写屏障，terminal 后 pair/renew 均拒绝。portable signer evidence 可用 lifecycle state witness 证明“因 parent terminal 而 ineffective”，无需伪造逐 key transition Event。

Agent projection MUST 分离三轴：`lifecycle=active|paused|deactivated` 是durable controller intent；generic
`readiness=ready|not_ready` 的 closed blockers 只含主体级 durable `runtime_key_missing|pairing_open`，
不得含session、KeyPackage、target grant/membership/reply或MLS blocker；`presence=online|offline|unknown`只表示
短期可达性。target-specific blockers只能出现在对应operation/SDK local plan。presence响应必须携
`expires_at`与`refresh_after`并由客户端jitter刷新；offline不等于deactivated、unpaired或conversation不存在。
#### 3.6.2 Runtime request binding、审批竞态与账号通知（normative）

Conformance vector：`ak.vector.agent.runtime_key_binding.v1`。

每个 open `pairing_request_id` 同时最多一个 pending runtime key binding。服务端 MUST 以 canonical JSON 对象计算稳定 digest，kind 固定为 `ak.agent.runtime_key_binding.v1`，对象字段为 `{kind, agent_id, pairing_request_id, verification_method, public_key_digest, attestation_digest}`；此处的`public_key_digest`是私有runtime-request digest，MUST调用`agent_runtime_public_key_digest`对`agent_runtime_approval_request_body.public_key`完整DTO的canonical JSON bytes计算SHA-256 typed digest；它与上节公开授权所用raw-key digest不同且不得互换。`attestation_digest`对`runtime_attestation`（缺省时为 JSON `null`）的 canonical JSON bytes 计算 SHA-256 typed digest。外层 binding 对象再按同一规则计算 SHA-256 typed digest。pairing code、过期时间、PoP challenge/signature 等 freshness proof 不得进入这份稳定身份。canonical helper 只能由 arkret-rust-sdk 定义并供实现复用。

`proof_of_possession` MUST 验证 `agent-operations.schema.json#/$defs/agent_runtime_key_possession_proof`，不得接受开放 JSON、实现私有字段或算法 fallback。v1 runtime key profile 固定为 Ed25519：`public_key.kty="OKP"`、`public_key.alg="Ed25519"`，`public_key.key` 解码后恰为 32 bytes；`public_key.kid`、request `verification_method` 与 proof `verification_method` MUST byte-identical，且该 DID URL 的 controller MUST 等于 request `agent_id`。proof `kind` 固定为 `agent_runtime_key_possession`，proof `signature_algorithm` 固定为 `Ed25519`（Arkret 自有对象不使用 JOSE 短名 `alg`，见 `signature-alg-registry.json`；`alg` 只保留给 JWS protected header 与 JWK），`signature` 是 64-byte raw Ed25519 signature 的无 padding base64url 表达。`Ed25519`也是 RFC 9864 fully-specified JOSE algorithm identifier；任何不能仅凭该算法标识唯一确定曲线和签名算法的多态别名都不属于本协议词表并 MUST fail closed。controller proof 的 detached JWS protected header 同样 MUST 使用 `alg="Ed25519"`。key 与 signature 解码后还 MUST 以 canonical unpadded base64url 重编码并与 wire byte-identical；非零 unused bits、padding 或其它别名表达必须拒绝。

构造方先计算上述稳定 `runtime_key_binding_digest`，再对以下闭合对象的 JCS bytes 签名；`context` 只存在于签名输入，不是 wire 字段：

```json
{
  "context": "ak.agent_runtime_key_possession_proof.v1",
  "kind": "agent_runtime_key_possession",
  "verification_method": "<request.verification_method>",
  "challenge": "<pairing_request_id>",
  "audience": "<pairing record service_id>",
  "created_at": "<proof.created_at>",
  "expires_at": "<proof.expires_at>",
  "pairing_code": "<pairing record pairing_code>",
  "runtime_key_binding_digest": "<stable binding digest>",
  "signature_algorithm": "Ed25519"
}
```

proof `challenge` MUST byte-identical 于权威 pairing record 的 `pairing_request_id`，不得由 caller 另造；`audience` MUST byte-identical 于 bootstrap 与 record 的 service DID `service_id`，不得使用 URL、HTTP Host 或请求体自选 verifier；签名输入中的 `pairing_code` MUST byte-identical 于 runtime body 与 record 中的 ≥128-bit secret，但不得复制到 proof 或 controller projection。`transcript_digest` MUST 等于上述 JCS bytes 的 SHA-256 typed digest；接收方必须先独立重建并比较 digest，再用 request `public_key` 验 Ed25519 signature。任一 equality、长度、digest 或 signature 不符都在创建/更新 pending request 前 fail closed。

`created_at`、proof `expires_at` 和 pairing record `pairing_expires_at` 均使用固定毫秒 UTC profile。proof MUST 满足 `created_at <= verifier_now + 60s`、`created_at < expires_at <= created_at + 300s` 且 `expires_at <= pairing_expires_at`。首次 runtime submit 与首次 final pairing 状态变更都必须在 `verifier_now < expires_at` 且 pairing record 未过期时复验；已经 accepted 的完全相同 Event-id 幂等重放只返回原 outcome，不重新执行状态变更。`pairing_request_id` 与 secret 是服务端发放的权威 challenge，故本流程不新增 caller-controlled challenge endpoint；同 stable binding retry 可提交新的短窗 proof，服务端用它原子替换当前完整 request。

Runtime MUST 在首次提交前持久化本地 key seed/private key，并在同一 open `pairing_request_id` 的整个生命周期内跨进程重启、配置重载和同名 channel 删除/重建复用同一 key binding；发现已有合法 key 时不得用新 seed 覆盖。若原 key 已丢失、损坏或无法访问，runtime MUST 停止重试并要求 controller 执行 `renew-pairing`，取得新 handle 后才能生成新 key。Runtime 不得把服务端的 `agent_runtime_request_conflict` 当成“以新 key 覆盖旧 pending request”的许可。

该 digest 与 controller `ak.agent.key.authorize.payload.approval_evidence.request_canonical_digest` 使用的 `ak.agent.key_pairing_request_binding.v1` 不同：后者是 controller 对当前 runtime request 与 pairing record 的批准证据。其唯一 canonical 对象为 `{kind, operation_id, controller_id, agent_id, pairing_request_id, pairing_code, expires_at, audience, runtime_key_binding_digest, proof_of_possession_digest}`：`kind="ak.agent.key_pairing_request_binding.v1"`，`operation_id="ak.gate.account.command.pair_agent_key.v1"`，`expires_at` byte-identical 于权威 `pairing_expires_at`，`audience` byte-identical 于 record `service_id`，`proof_of_possession_digest` 是当前闭合 proof wire object 的 JCS SHA-256 typed digest；不得加入或省略字段。runtime public key、verification method 与 optional attestation 已由 `runtime_key_binding_digest` 闭合绑定，不重复铺开，也不得用只绑定 public-key digest 的旧 helper。

最终 `ak.gate.account.command.pair_agent_key.v1` MUST 从数据库当前持久化的 runtime request 与 pairing record 重新计算 stable binding、PoP transcript/digest/signature 和 pairing-request binding，并与 controller 签名 `approval_evidence.request_canonical_digest`、提交 body、`signing_key_binding`、`authorize_event` payload 及当前 stable binding 比较；final body 的 `proof_of_possession` MUST byte-identical 于当前持久化 proof。不得只比较提交 body 与 pairing handle。same-binding retry 刷新 proof 后，任何绑定旧 `proof_of_possession_digest` 的 controller prompt/approval 自动失效；过期 prompt 或任一不一致必须 fail closed，客户端重新读取。

`ak.agent.key_pairing_request_binding.v1.expires_at` 与权威 `pairing_expires_at`、PoP `created_at` / `expires_at` 都使用统一 UTC 毫秒 profile `YYYY-MM-DDTHH:mm:ss.SSSZ`。构造方 MUST 先把 typed instant 按 Unix 时间向负无穷方向 floor 到毫秒，再以恰好三位小数和大写 `Z` 序列化；投影、transcript 和摘要绑定使用逐字相同的 canonical string，不得从宽松 RFC 3339 输入临时正规化，也不得另派生 epoch 字段。非法或非 canonical wire 输入必须在摘要验证前 fail closed。

首次合法请求生成一个稳定 `approval_request_id` 和 `ak:notification:*` id，并在创建 pairing record 的 account context 中物化 `action=upsert` 的 Agent runtime approval notification delta。相同 stable binding 的重试是幂等的：允许刷新 PoP 和完整 request，但保留两项 id，并重新物化同一 `action=upsert` 投影。已有 pending 时，不同 stable binding MUST 返回 HTTP 409 `agent_runtime_request_conflict`，不得替换 controller 当前看到的请求。

Runtime 提交体、controller 投影与最终批准体是三个不同的闭合 DTO，不得互相反序列化替代：runtime 向 open endpoint 提交 `agent_runtime_approval_request_body`（含 `pairing_code`，不含 controller disclosure/Event）；authenticated `key_state.pending_runtime_key_request` MUST 精确匹配 `agent_runtime_approval_controller_projection`，只含 `{pairing_request_id, agent_id, verification_method, public_key, proof_of_possession, runtime_attestation?}`，不得含 `pairing_code`、`requested_scope_disclosure`、`authorize_event` 或额外字段；controller 核对 sibling `key_state.pairing_code` 后，MUST 使用当前 controller signer、权威 verifier/audience/challenge 与不超过 5 分钟的 freshness window 新建 `requested_scope_disclosure` 和 `ak.agent.key.authorize`，再组装 `agent_key_pair_request_body`。Account notification 仅携 [`../sync/client-sync.md` §3.1](../sync/client-sync.md) 的最小发现字段；客户端收到通知后读取一次 authenticated Agent projection，不得假定 notification 自身包含完整审批请求。

Pairing record 与 account notification projection 的 upsert/remove MUST 同一数据库事务提交。只有 `ak.agent.key.authorize` 已被 controller-signed Agent PCR Seal 覆盖、且可构造 active portable signer evidence 后，才能消费 pairing handle并发 `remove(reason=approved)`；仅 durable 入库的 pending control Event 不满足该条件。expiry、renew-pairing、deactivate 与 supersede 也必须发对应 remove。Authorization witness/activation projection 与该消费必须共享事务，或者以 `authorize_event_ref` 为键提供启动时和请求时均可幂等执行的 reconciler；reconciler MUST 重验 accepted Seal witness，不得从 Event row 存在性推断授权。崩溃不得使已见证 authorization 永久显示 pending。Notification 只负责 controller 发现，不是 durable 审批事实。

最终 pairing commit 以 `authorize_event.event.event_id` 为幂等身份。相同 `pairing_request_id`、相同 stable runtime binding、相同完整 request digest 与相同 EventInitialSubmission bytes 的重试 MUST 返回当前权威阶段：Seal witness 尚未 accepted 时为同一 `awaiting_accepted_frontier`，witness accepted 且 activation durable 后为同一 `active`；不得再次插入 authorization 或因数据库唯一约束返回 500。online publication authority 由每次请求的 sender-constrained controller session typed context 重验，不是 submission bytes 的一部分。相同 Event ID 携带不同 canonical Event bytes，或相同 runtime key id 绑定不同 Agent / pairing / public key时 MUST 返回 conflict 并 fail closed。网络超时后的调用方 MAY 安全重试完全相同的请求，也 MAY 通过 `ak.self.agent.resource.get.v1` / list 确认 active `authorized_event_ref`；服务端后台重试同样 MUST 重放原始 controller-signed submission，不得生成替代 Event 或代签 receipt。

Controller 通过 `ak.self.account.stream.subscribe.v1.notifications.items[]` 发现请求；声明支持的服务 MUST 在 `ServiceDescribe.supported_features` 列出 `ak.feature.agent_runtime_approval_notifications.v1`。只有 describe 已成功解析且缺少该 token 时，controller 客户端才能启用 30 秒起、带 jitter、最大 60 秒的 list/get fallback；describe 未解析、应用隐藏或离线时不得轮询。未配对 runtime 仍通过 `ak.open.agent_pairing.read.runtime_key_request_status.v1` 有界轮询；HTTP response MUST 携带 `Retry-After`，客户端采用 1s/2s/5s/10s 后最大 30s，并遵守更长的服务端值，在 pairing 过期后停止。

#### 3.6.3 Agent PCR genesis 的构造顺序（normative）

Agent PCR 的 `realm_id` 按 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md) 只能等于其 genesis
`ak.realm.create` 的 `retype(event_id)`。该 create 又必须提交 Agent DID accepted inception 的闭合
`initial_resolution={did,method_history_head,version_id}`。因此 Agent inception **不得**预先包含尚未存在的
PCR id；PCR service binding 必须是 create accepted 后的连续 DID update。实现 MUST 精确按此执行：

1. **controller 创建并发布 PCR-independent inception**。controller client 先生成 Agent `did:webvh` root、
   预轮换 binding update key 与其下一代 key，并在任何网络副作用前可恢复地持久化至少后两者。entry 0 只含
   `type="ArkretService", serviceKind="station"` 与唯一 `ArkretManagedPrincipalController` delegation，MUST NOT 含
   `ArkretPrincipalControlRealm`。controller 签名并提交 exact entry 0；Station 不生成、不持有、
   不代签 Agent DID 私钥。只有 entry 0 已 accepted 才进入下一步。
2. **prepare 钉死 accepted inception 与 controller account pair**。controller 以该 `did` 和当前 `controller_station_id` 调用 `phase=prepare`；服务端将它与 session principal 组成的 pair 逐字匹配 authenticated session 的 `(principal_id, station_id)`，并只从该 pair 的本地唯一 PCR lineage 取得后续材料。随后服务端
   独立解析并验证 entry 0、`project(did)=agent_id`、controller delegation 与“尚无 PCR binding”，返回 exact
   `initial_resolution`、allocation、authorization ref 与 `requested_scope_digest`。controller MUST 把返回的
   history head/version 与自己提交的 entry 0 逐字比较。
3. **controller 本地冻结 genesis 信封**。controller 把该 exact `initial_resolution` 连同
   `purpose="agent_control"`、`genesis_salt`、`executed_by`、`authorization_ref` 等一次写入完整
   `ak.realm.create` canonical bytes，自算 `event_id`，再取 `realm_id = retype(event_id, "realm")`。该 create
   **此刻不提交**。
4. **提交 `ak.agent.provision`**。payload 保留 `principal_control_realm_id`，其值就是上一步算出的 id；它是
   对一条**尚未提交**的 Event 的**前向声明**。这是 [`../conformance/encoding.md` §6.0.1](../conformance/encoding.md)
   的具名 C 类例外 `ak.exemption.preimage_identity.agent_provision_principal_control_realm_id.v1`：
   inception 不依赖 PCR；genesis 只依赖 accepted inception；provision 依赖已冻结 genesis 的派生 id，依赖
   方向严格单向，每个对象都可构造。
5. **另一次提交 genesis create**。该 create MUST 在一次**独立的提交**中送出，MUST NOT 与 provision 同属
   一个原子 unit 或同一 ordered submit batch——那正是 §6.0.1 B 类禁令，会让两条 Event 互为原像而不可构造。
   Genesis admission MUST 反查：controller PCR 中是否存在一条**已 accepted** 的 `ak.agent.provision`，其
   `payload.principal_control_realm_id` 逐字等于 `retype(本 create 的 event_id)`。无匹配 MUST 零写入拒绝。
6. **发布 DID binding update**。genesis accepted 后 outcome 进入 `status=awaiting_did_binding`。controller 使用
   entry 0 `nextKeyHashes[0]` 预承诺的 update key 签发连续 entry 1，保留 controller delegation，并新增唯一
   `ArkretPrincipalControlRealm.serviceEndpoint={realm_id,controller_did,authorization_ref,requested_scope_digest}`。
   服务端必须验证完整 history、预轮换连续性和四元组与 accepted create/provision 逐字相等；只有 update
   accepted 后 outcome 才进入 `complete`，才能发布 Agent list/get、pairing handle 与 lifecycle projection。

该 create **不再携带** `refs[] role=agent_provision`：provision 先于 create 成型，create 若引用它会在 create
被组装之前就要求知道一个不在冻结范围内的值，且反查已经提供同等且更强的绑定（ref 只声明"我指向某条
provision"，反查证明"某条 accepted provision 恰好声明了我"）。`delegated_pcr_genesis` 因此改由
`payload.object.purpose` 判别。

**声明唯一性（normative）**：同一 controller PCR 内，`ak.agent.provision` 以 `payload.principal_control_realm_id`
为 subject 写一个 `cas_register`、`bottom=reject` 的 cell；两条 provision 声明同一 realm id 时第二条 MUST 被
拒绝且零写入。该 cell 只覆盖同一 controller PCR。跨 controller 的重复声明由 Station 的**本地唯一
索引**兜底：同一部署内任意两条 accepted provision MUST NOT 声明同一 `principal_control_realm_id`，冲突
MUST 零写入拒绝。两层合起来使"一个 realm id 至多一条 provision 声明"成立。

**同 Station 承载（normative）**：Agent PCR 与其 controller PCR MUST 由**同一个 Principal
Server** 承载。genesis admission 的反查是一次本地投影查询，跨服务器时它既没有可信的查询面，也没有可
线性化的唯一性判定点；上面的本地唯一索引同样是部署内事实。这不改变 PCR 的既有作用域语义——PCR 的
作用域本来就是 `(DID, Station)`。

**中间态不外显（normative）**：provision 被接受但 genesis 或 DID binding update 尚未接受的窗口内，该 Agent 对外**不存在**。
`ak.self.agent.command.provision.v1` 的 outcome 停在 `status=awaiting_pcr_genesis`；Agent DID 的
`ArkretPrincipalControlRealm` service entry、pairing handle 与 `ak.self.agent.read.list.v1` /
`ak.self.agent.resource.get.v1` 的可见性**全部推迟到 binding update 被接受之后**。genesis accepted 后状态改为
`status=awaiting_did_binding`，但仍没有可见 Agent 对象。因此不存在"lifecycle 取什么值"、
"能否 pause/deactivate"、"readiness 该报哪个 blocker"这三个问题：没有可投影的 Agent 对象。genesis 被接受时
只确认 PCR；binding update 被接受时才一次性创建 pairing handle、把 lifecycle 写入 `active`（见 §3.6.3
下一段与 [`../models/actor.md` §3.3](../models/actor.md)），并把 outcome 推进到 `status=complete`。

**genesis 是唯一的首次 active 写入（normative）**：`ak.component.agent.status.v1` 的 FSM 只有
`uninitialized -> active` 一条离开初始态的边，而 `ak.self.agent.pause` / `resume` / `deactivate` 都要求非
`uninitialized` 的前驱。因此 Agent PCR genesis `ak.realm.create` 在
`payload.object.purpose == "agent_control"` 时 MUST 条件写入该 cell，subject 取 `envelope.actor_id`
（即 Agent DID），transition 为 `uninitialized -> active`。非 `agent_control` 的 create MUST NOT 触发
该写入。服务私有 row、FSM 默认值或 organization-governed PCR 都不能合成首次 active witness。

**未完成 provision 不可撤销（normative）**：`ak.agent.provision` 一旦 accepted 就是 controller PCR 中不可删除、
不可重写的历史事实，其 `agent_slug` 与 `principal_control_realm_id` claim 也不得通过服务私有清理、超时或垃圾回收
释放。controller 必须持久化并恢复冻结的 genesis bytes，继续完成同一 provisioning；协议不提供第二条 HTTP
放弃通道。客户端若在 provision accepted 前放弃，只需丢弃尚未提交的本地 intent。

### 3.7 MLS KeyPackage Key

MLS KeyPackage key 用于加入加密 Realm。

要求：

- MUST 绑定到 Actor DID 和 device id
- MUST 由有效 device key 或 principal signing key 签名
- MUST 有发布时间与过期时间
- SHOULD 单次或短期使用
- 被撤销设备的 KeyPackage MUST NOT 用于新加密

## 4. Device Record

建议 device record 是 actor-private signed Event 或 identity sidecar 中的 signed state。

示例：

```json
{
  "id": "ak:device:01964137-0000-7000-8000-000000000000",
  "actor_id": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "display_name": "Alice MacBook Pro",
  "device_public_key_did": "z6Mks...",
  "device_key_format": "Multikey",
  "created_at": "2026-04-26T00:00:00Z",
  "authorized_by": "ak:device:01964136-8000-7000-8000-000000000000",
  "authorization_ref": "ak:event:AeIDJcHD1Li18FoX3Nti6o-PayZ07cEjUQhzn6cyY6Z_",
  "status": "active",
  "last_seen_at": "2026-04-26T08:00:00Z",
  "revocation_ref": null
}
```

### 4.1 Principal Control Event Stream

设备、recovery 和 KeyPackage 有效性属于 principal 级状态，不属于任意 Collaboration Realm。Arkret v1 使用 **Principal Control Event Stream** 承载这些 durable identity state（其归属的 Realm 即 [Principal Control Realm](../models/realm-and-space.md#28-realm-角色分类normative)，与 Collaboration Realm 在 `models/realm-and-space.md` §2.8 中正式分类）。SessionGrant 是 Account Authority 的 issuer-ledger credential，其签发与 lifecycle 不写入 Principal Control Event Stream，见 §6。

当 `ak.device.authorize`、`ak.device.revoke` 或 `ak.device.list_update` 以 `ak.schema.event.v1` Event Envelope 传播时：

- `realm_id` MUST 是该 principal 的专用 `principal_control_realm_id`，不得使用任意 Collaboration Realm 的 `realm_id`。
- `actor_id` MUST 是签发该控制事件的 principal、已授权 device 或受信 recovery service。
- `payload.principal_id` MUST 与该 control Realm 绑定的 principal `did_core_id` 一致；不一致时 MUST reject。
- control Realm 的 `ak.realm.create` 或等价 genesis record MUST 绑定 principal `did_core_id`、`initial_resolution={did,method_history_head,version_id?}`、control stream policy 和可发现的 service endpoint。Station MUST 用 method adapter 独立验证 `project(did) == principal_id`，并以 genesis 初始化 `ak.component.identity.resolution.v1`。该 Realm 使用标准 `ak.schema.realm.v1`；human / organization PCR 通过 `fields.purpose="principal_control"` 标记，Agent PCR 通过 `fields.purpose="agent_control"` 标记；两者的 `schema_refs` 都包含 `ak.profile.principal_control_realm.v1`（详见 §5.0.1 步骤 3）。control realm **不**使用单独的 Realm kind——所有 Realm-level 验证（schema、boundary、E2EE、federation）走标准 Realm 路径。
- 普通 Collaboration Realm 的业务事件 MAY 通过 `refs[role=authorized_by]` 引用不可变 grant record，并通过 role=`did_inception` 等专门 role、verified snapshot reference 或 device-state seal 引用 principal control state；`authorized_by` 不得使用 Event id alias，也不得把另一个 principal 的 device/session 事件直接写入该 Collaboration Realm history 来改变身份状态。

**`principal_control_realm_id` 不在公开面上（normative）**：`ak.open.identity.read.resolution.v1` 的 public projection MUST NOT 携带它（见 [`./identity-did.md` §4.2](./identity-did.md)）。实际需要使用该 principal PCR 控制事实的一方，MUST 从与自身角色相符的授权来源取得并独立验证 canonical `principal_control_realm_id`：holder 与 recovery actor 用 `ak.self.identity.read.resolution_audit.v1`；关系对端只使用其特定 operation 已登记且获授权的 carrier（`ak.peer.contacts.command.submit.v1` 逐字投递的 signed Event envelope、`ak.peer.account_status.*` 的 authority evidence）；Agent 用其 DID Document 的唯一 `ArkretPrincipalControlRealm` service entry；本地账号还可用自己的 account binding。normalized principal view 只在其输入本身来自上述已验证来源时可用。外部 verifier 对敏感操作 MUST 获取最新 evidence 并独立验证；它不必长期持久化其他 principal 的 resolution，短 TTL cache 也不得代替 freshness。需要 PCR authority 的操作无法验证 control Realm 与 principal `did_core_id` / `did` projection 的绑定时，MUST fail closed。

跨账号 `ak.self.keys.read.lookup.v1` 的 device row **不承载** `principal_genesis_receipt` 或任何 PCR chain/Seal；其唯一设备投影验证载体是 [`device-lifecycle.md` §8.2/§8.3](../crypto-media/device-lifecycle.md) 的 origin Station signed `device_projection_attestation`。跨账号客户端以该既有合同验证当前 device/generation/key，不要求取得或重放对方 PCR；这与内部设备投影的 §5.5 PCR authority 要求是不同角色，不能互相替代或扩大披露。

public projection 本身仍 MUST 可验证：它由 Station 的 `projection_attestation` 覆盖，用于确认 `(principal_id, station_id)` 的 current `did` 与 method history 位置。首次接触（Contact request、invite、member add）只需要该 public projection 与可验证 service route，MUST NOT 以取得对方 PCR genesis、Seal 或 history 为前置条件。

Organization principal 的 control stream 遵守同一 PCR 规则，但它没有共享 human password account。组织 PCR 的 genesis / recovery / delegated write MUST 由组织 DID inception/controller proof、满足组织 governance threshold 的 proof、或组织 DID Document / governance profile 明确委派的 Account Authority / `ArkretGovernanceService` 授权。委派路径的 purpose MUST 覆盖对应动作（例如 `principal_control_realm_bootstrap`、`device_enrollment`、`session_issuer` 或 `ak.realm.organization`），且事件必须保留实际执行主体（`executed_by`、governance decision id 或等价审计 ref）。普通企业 SSO/OIDC/passkey 登录只认证某个管理员 principal；它不能单独创建、登录或控制组织 PCR，除非该 Account Authority 同时出示上述组织侧 delegation / governance proof。

Agent 是独立 DID principal，不继承 controller 的 PCR 或 home/Collaboration Realm。Agent DID accepted inception entry 0 MUST 只含 Station 与唯一 `ArkretManagedPrincipalController` delegation，MUST NOT 含 PCR id 或 `ArkretPrincipalControlRealm`。Agent PCR genesis accepted 后，controller MUST 使用 entry 0 预承诺的 update key 发布连续 entry 1，并新增唯一 service entry：`id=<agent DID>#arkret-principal-control-realm`、`type="ArkretPrincipalControlRealm"`，`serviceEndpoint` 为闭合对象 `{realm_id, controller_did, authorization_ref, requested_scope_digest}`。`realm_id` 是该 Agent PCR genesis `ak.realm.create` 的 event-derived `ak:realm:*`（按 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md) 的通则 `retype(event_id)` 派生，服务端不得自选）；该 service entry 是他人**发现**该 realm id 的已发布指针，不是其派生权威；`controller_did` 是获授权的 managed-principal controller；`authorization_ref` 是 entry 0 中覆盖 `principal_control_realm_bootstrap`、agent-control authoring 与 `principal_control_realm_recovery` 的 delegation DID URL；`requested_scope_digest` 必须按 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 的域分离 canonical input 重算匹配。entry 1 的四元组 create-locked；后续 DID update 删除或改变任一字段时，该 Agent binding 对新授权失效，不能把更新后的值视为扩权。公开 DID Document 与其历史 MUST NOT 包含 `requested_scope`、具体 resource selector 或 constraint。Receiver 必须按 authorizing Event / grant 的 accepted-at 解析 Agent DID history，逐字验证此 entry，并从 controller 经 [`../identity/identity-handles.md` §16](./identity-handles.md) 的认证私有 presentation 路径取得符合 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 的完整 scope 披露。Receiver MUST 校验 `request_id`/`challenge` 单次使用、`verifier_id`/`audience` 精确匹配、`expires_at-issued_at <= 300s`、controller 当前 proof 与 disclosure digest，再以披露 scope 重算 DID 中 commitment；任一环节失败均 fail closed。成功接收后 MAY 把披露作为加密的 verifier-private evidence 保存，但缓存键 MUST 至少包含 `(agent_id, requested_scope_digest, verifier_id, audience)`，不得把 service-local Agent row 单独当成协议绑定，也不得把披露写回公开 DID、Realm plaintext、durable Event、pairing code 或通知。

该边界的 conformance vector 为 `ak.vector.agent.pcr_separation.v1`。

Agent PCR genesis MUST 使用 `purpose="agent_control"`，MUST NOT 携带 human-only `founding_device_descriptor`（`genesis_salt` 与其它 Realm 一样必填），并遵守共享 PCR profile、`history_access=since_join`、`encryption_profile=mls_rfc9420` 与两条 `e2ee_required` floor；`created_by` 与 notary 都是 Agent DID。Controller 受托创建或写入 Agent PCR 时，Event `actor_id` 是 Agent DID（控制事实所属 principal），`executed_by` 是 controller DID，`authorization_ref` 是上述 DID delegation 或其可验证 materialized grant；proof verification method 必须属于 controller，不得由服务端伪造 Agent 签名。Agent PCR 的 MLS group state MUST 由 controller E2EE client 本地生成；服务端只能保存 ciphertext、公开 envelope metadata 与 reducer 所需的承诺/证明，不得生成、托管或解密该 private state。Agent profile、`ak.agent.key.authorize/revoke` 与 `ak.self.agent.pause/resume/deactivate` 写入 Agent PCR。Controller-owned `ak.agent.provision` 保持在 controller PCR，并原子投影 Agent provisioning、accountability、selector 与 `principal_control_realm_id` claim 事实；后续独立变更仍可使用通用 accountability/selector Event。该 provision MUST 先于 Agent PCR genesis 成型并在另一次提交中被接受，genesis 的准入由 §3.6.3 的反查绑定，二者 MUST 由同一 Station 承载。Realm-specific capability grant 仍写入所治理 action 所属 Realm。Pairing request 与 approval notification 永远不写入任一 PCR。

Agent PCR 的 Seal 由 `POST /_arkret/self/seals`（`ak.self.seals.command.submit.v1`）直接提交；Seal 不是 Event，也不经 EventInitialSubmission。若 accepted Agent DID delegation 的 purpose 覆盖 `principal_control_realm_recovery`，该 delegation 同时授权当前 controller device 为此 Agent PCR 的 delegated notary signer；receiver MUST 从唯一 signed Agent PCR create Event 精确验证 `(Agent DID, controller DID, realm_id, authorization_ref)`。Agent PCR Event 必须由 producer 签名 Realm `scope_ref`，reducer 独立复核。首个非空 Seal MUST 无 predecessor 并原子覆盖 Agent PCR founding anchor unit；Station、Account Authority 或其他 service 不得用 service key 代替 Agent/controller 签署。

Agent PCR 的单条 create 虽无 `seal_basis`，仍是 closed-anchor Control Move。Controller
client MUST 从该候选 create 重算完整 founding notary authority，并由 accepted delegation 下的
当前 controller device 为 exact create digest 签 Control Proposal Ack；Station MUST 在同一
事务提交 receipt、canonical create 与 pending Control index。首 Seal 的原子提交再把同一 digest
标记 sealed，并同时提交 Seal lineage 与 registered cell effects；不得出现“Event log 已有 create，
但 pending store 无该 digest”或以 service key/无 Control Proposal Ack 绕过 proposal 轨道的中间状态。

Agent 不建立独立的面向用户 Recovery Key，也不得要求用户为每个 Agent 保存另一套 24 词。Agent DID / PCR 管理连续性来自当前 controller delegation；可移植 backup 只保存该 actor 合法持有的 history-secret ranges，不保存或恢复 Agent PCR active MLS state。解开历史密钥不授予 Agent DID 控制、agent-control authoring 或业务 capability；fresh endpoint 仍必须用 current delegation 经标准 KeyPackage/Add/Welcome 重新加入，任何恢复后的写入仍验证当前 Agent DID delegation、controller 状态与目标 Event authorization。

实现 MAY 用 identity sidecar、device registry 或 DID/key-log operation 存储同一状态，但它们必须提供等价的签名、digest、auth dependency 和撤销语义；桥接到 Event Envelope 时仍必须遵守上述 `realm_id` 规则。

## 5. 设备授权流程

### 5.0 PCR Genesis 与首设备

首次设备授权不是账号服务签发的临时 credential，也不是在 PCR 创建后的第二个审批流程。客户端在任何外部副作用前必须 durable 保存 recovery material、method control material（若有）、device identity、HPKE、DPoP keys 与完整 registration draft，然后一次构造：

- method-specific registration artifact：did:webvh inception/current entry、did:web HTTPS Document，或 did:key local expansion；active adapter 从 canonical `did` 投影稳定 `principal_id=did_core_id`，并冻结 bootstrap trust 与 control evidence；
- `identity_creation_control_proof`，由注册时 current control key 签名并承诺 principal/PCR id、`did`、method evidence digest、create/authorize payload digest、首个 Standard session request digest、lease fence、DPoP/audience/origin/trust-domain 与 expiry；
- ordered `pcr_genesis_unit=[ak.realm.create, ak.device.authorize]`。create 由 registration control key 签名；authorize 由 founding device 自签，`authorization_binding_kind="registration_anchor"`。

create 的 `initial_resolution` MUST 携带 `{did,method_history_head,version_id?}`。Station 验证通过后把它作为 PCR current resolution 持久化；不得只存在 Account Authority 的 registration saga 中。

Account Authority 将 exact draft 持久化为单调 saga：

```text
reserved -> did_published -> pcr_accepted -> account_bound -> completed
```

它发布 exact client-signed DID operation，再通过 `ak.peer.principal_genesis.command.submit.v1` 透明 relay exact genesis unit。Station 独立验证所有内容 proof，并原子接受两条 Event，返回 `scope.kind="pcr_genesis_unit"` 的 batch receipt。Account Authority 只有在 receipt 与 frozen registration 逐字一致后才能提交一账号一 principal binding，并从 durable issuer ledger 签发首个 `credential_class="standard"` grant。

#### 5.0.1 Root commitment 与无环约束（normative）

`FoundingDeviceDescriptor` 位于 principal-control realm genesis fields，承诺 device/HPKE keys、算法及 founding authorize **payload** digest。identity creation transcript 也只承诺两条 payload digest。任何 Event id 或 envelope digest 都不得进入 root commitment：第二条 authorize 的 `prev_refs` 必须引用第一条 create Event id，若 root 再承诺 authorize Event id 会形成双向原像循环。

第二条 authorize 的 `proof.verification_method` 必须是 method adapter 基于已验证 `initial_resolution.did` 构造的 device DID URL，其 fragment 绑定 `device_id`。验签方 MUST 解析该 DID URL、确认其 base `did` 投影为 `principal_id`，再用 unit-local candidate overlay 把 fragment 映射到 descriptor/payload key；不得把 fragment 直接拼到 `did_core_id`，不得使用 `did:key` 作为 Event method，也不得假定设备目录已经落地。两条 Event、receipt、resolution/device projection 必须在同一原子提交中成功或全部不可见。

#### 5.0.2 注册中设备丢失（normative）

PCR accepted 前，账号只有 provisional reservation。新设备通过同一账号强认证并持有同一 registration control 时，可以取得递增 lease fence，继承 principal/DID reservation，以新 device descriptor 重签 fresh transcript 并 exact resume。两个 unit 并发时**账号维度**的 PCR create-once 只允许一个 winner；若旧设备 unit 已先 accepted，新设备必须按 §5.0.3 走已接受 recovery policy，不能再次 genesis。

PCR 尚未 accepted 且 identity root 也丢失时，可以显式放弃 provisional identity，以全新 root/DID/PCR 开始。放弃 provisional identity MUST 是显式用户动作，MUST NOT 由普通账号登录、session 恢复、lease fence 递增或任何自动流程触发；MUST 在执行前向用户明示后果——旧 entry 0 将永久不可用且**无法注销**，其上不存在可延续的业务状态。重认证强度、风险检查项与冷却期时长属**部署治理**，实现 SHOULD 施加与账号敏感操作同级的重认证与冷却，具体由部署自定，本规范不规定也不强制。放弃后：已发布 entry 0 作为 orphan anchor，不得复用或声称连续性，registry 必须保留 tombstone/audit reservation。显式放弃处置的是同一账号/audience 下已冻结、可能已发布的那一份 reservation；它不承担清理由并发实现错误额外制造的第二份 DID 的职责——registry 唯一性由 [`account-lifecycle.md` §2.1.2](./account-lifecycle.md) 的 frozen-reservation barrier 保证。

**执行放弃的唯一 operation 对（normative）**：显式放弃由封闭的两步 operation 承载，
`ak.gate.account.command.issue_identity_abandonment_challenge.v1` 取 challenge，
`ak.gate.account.command.abandon_identity_creation.v1` 确认；形状对位既有的
`issue_identity_binding_challenge` + `register`。实现 MUST NOT 另造 abandon 入口，也 MUST NOT
用 lease expiry、fence takeover 或垃圾回收模拟显式放弃。

- **凭据被逼定**：PCR 从未被 accepted ⇒ 用户没有 principal ⇒ 不存在绑定 principal 的 `ak.session.grant`。
  两个 operation 因此都只能由 account handoff grant 授权，并已加入
  `ak.gate.account.exchange.create_handoff.v1` 的封闭 operation 白名单。
- **"显式"由 challenge 结构保证**：根已丢失，用户签不了确认书，客户端自报的"我已阅读"可伪造。
  challenge 单次使用、≤300 秒、保存在 shared durable state（不是进程内存），并钉死 `account_subject`、
  holder `cnf.jkt`、本次要放弃的 `principal_id` 与 `did_version_id`、当前 lease id 与 fence、必须向用户
  展示的封闭后果集合 `consequence_disclosure`、audience、origin、trust domain、purpose 与 expiry；
  重复同一 `request_id` 返回同一未消费 challenge，expiry 与已消费是不同终态。上一段"MUST NOT 由
  登录 / session 恢复 / fence 递增 / 任何自动流程触发"正落在这里：自动流程不会先取 challenge，
  因此结构上做不到。
- **确认必须新鲜**：确认调用 MUST 出示一份新鲜的 handoff grant，MUST NOT 复用签发 challenge 时那一份。
  "要不要重认证"是协议保证；**重认证强度、风险检查项与冷却期时长仍属部署治理，本规范不规定**。
- **并发**：challenge 签发与确认之间 PCR 被 accepted 时，确认 MUST 以 `identity_creation_already_accepted`
  失败且 MUST NOT 执行放弃——身份既已成立，该走的是账号删除流程。判定依据是 challenge 钉死的
  `did_version_id` 与 lease fence，不是本地推断。
- **原子边界**：消费 challenge、写 orphan anchor tombstone/audit reservation、从**所有** holder 可读面
  抑制 `reserved_identity_creation` checkpoint、释放 identity-creation lease，MUST 在一个事务内完成，
  任一步失败零写入。同 `request_id` 重放 MUST 返回同一终态，MUST NOT 产生第二条 tombstone。

放弃后该 reservation 的 `reserved_identity_creation` checkpoint **MUST NOT** 继续作为"某账号曾尝试创建身份"
的可读痕迹对外提供——包括后续 handoff 的 `identity_creation_lease.reserved_identity`——只保留 tombstone/audit
所需的最小记录。这是安全性质，不是清理策略。

**orphan anchor 的后续处置属部署治理，不由本规范定义（normative 边界）**：该 entry 0 的 root 已丢失，
而 did:webvh 的 deactivation 需要 controller 签名，因此它**永久不可注销且公开可解析**。
托管方 MUST NOT 代签任何 log entry 来标记它（[`identity-did.md` §3.7](./identity-did.md) I-1：
hosting 不等于 control）。是否在部署自有的发现面上标注、handle 与 namespace 何时释放、
保留多久，都由该部署的运营方按自身治理策略决定，本规范不规定，也**不要求**实现具备该能力。

**但有一条协议层约束必须保持**：某个 Station 上没有该 `did_core_id` 的 accepted PCR
**只是本地事实**。PCR 的作用域是 (`did_core_id`, Station)，同一主体在别的 Station 上
可能完全正常。解析方与联邦对端 MUST NOT 把"某个部署报告无账号"推断为"该主体已失效"
或据此拒绝其在其它 Station 上的有效证据。PCR 已 accepted 时账号认证绝不能替代 recovery proof。

#### 5.0.3 PCR-Policy Re-anchor Unit（normative）

全设备丢失时，基础恢复直接使用丢失前已进入 accepted Seal/control state 的 PCR recovery policy。客户端
建立 recovery session，提交满足 policy 的 recovery secret、device quorum、trusted recovery service 或
threshold proof；验证通过后原子提交：

1. policy-authorized `ak.device.reanchor`，携带 `recovery_authority_kind="pcr_policy"`、policy/session ref、
   `previous_device_generation`、严格递增的 `new_device_generation` 与 replacement authorize payload digest；
2. replacement device 自签 `ak.device.authorize`，`authorization_binding_kind="pcr_recovery"`，`prev_refs`
   只含 re-anchor Event id。

`new_device_generation` 是 PCR-local monotonic generation ref，MUST NOT 等于或派生自 DID `versionId`。
generation CAS 接受后 fence 全部旧 generation device；resolution cell 不变。

DID-root recovery 是 accepted policy 可显式启用、可撤销的一种 proof factor。只有 adapter 同时满足
`verifiable_control_history` 与 `pre_rotation_commitment` 时，re-anchor 才可携带
`recovery_authority_kind="did_root"` 与 recovery-session 已冻结的 current-root evidence。未启用、已撤销或
method 不支持时 MUST `unsupported_feature`/`recovery_policy_mismatch`。它不在 RecoveryTransaction 中发布
DID operation，也不推进 resolution；用户另行执行 method successor 时走独立 DID operation 发布流程。

#### 5.0.4 Recovery-material gate（normative）

Genesis/re-anchor accepted 只建立可认证设备，不等于 recovery ready。在首个 accepted Seal 与由该设备签署的 genesis recovery policy 都完成前，PCR 必须保持 `recovery_material_pending`。此 gate 不回滚已 accepted identity/device state；失败后客户端 exact resume。

gate 的作用范围是：**发起任何 post-bootstrap E2EE Realm 创建/加入前 MUST 完成**（与 §7.11 一致）；gate 未完成时允许读取与非 E2EE 的本地/账号级操作。gate 期间允许的封闭写入集合恰为：该 PCR 的首个 Seal、genesis recovery policy、以及 genesis unit 自身产生的 device projection 更新（`ak.device.list_update`）；其余 Realm 写入 MUST fail closed。

### 5.1 新设备加入（首台设备已存在）

推荐流程：

1. 新设备本地生成 device key。
2. 新设备没有 accepted-device signer 时不得调用 `issue_session_grant`，也不会得到任何 restricted SessionGrant；它通过匿名 `ak.open.device_pairing.command.stage.v1` 取得二维码/手动码，并把同一 pairing payload 交给旧设备。只有 step 5 的 authorize Event 已 durable accepted、新设备出现在 current durable device list，且重新认证取得 AccountHandoff 后，才能用 accepted-device proof 换取 Standard grant。在此之前 MUST NOT 读取 E2EE history、解锁 key backup、发送或接收 `ak.secret.request/send`。SAS/QR 成功只允许进入授权确认，不构成 secret-transfer 例外。
3. 新设备通过 `POST /_arkret/self/device_messages` 向同 principal 的已授权设备发送 `ak.key.verification.request`。content MUST 至少包含 `transaction_id`、`from_device`、`methods`、`timestamp`、`expires_at`；用于设备授权时 SHOULD 带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`（canonical `PublicKey`）、`challenge_proof`、`target_attestation`（`accepted_device` possession attestation，本路径下 `hpke_key` / `algorithms` 的唯一权威来源，见 [`device-lifecycle.md` §5.2](../crypto-media/device-lifecycle.md) §5.2.2）、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`（wire 示例见 [`device-lifecycle.md` §7](../crypto-media/device-lifecycle.md)）。
4. 已授权设备的主接收路径是 `GET /_arkret/self/account/subscribe` 的 `delta.to_device.messages[]`；push 只能作为唤醒提示。若 `delta.to_device.limited=true`、本地 dispatcher 需要补洞，或旧设备当前没有完整 account subscribe，才使用 `GET /_arkret/self/device_messages?after=<cursor>&limit=n` 补拉。UI MUST 显示 requesting device metadata 与 pairing code，要求用户和新设备屏幕上的 code 比对。
5. 用户在已授权设备上批准并完成 SAS/QR transcript 后，该设备先验签 `target_attestation`、从中取出 `hpke_key` 与 `algorithms`（MUST NOT 从服务端响应或 UI 输入取），据此对完整 `ak.device.authorize` payload 签署 Event Initial Submission，再调用 `POST /_arkret/gate/account/device-pair`，提交 transcript 绑定的 `pairing_code`、`new_device_pubkey`、`challenge_proof`、payload 内 exact `hpke_key`、exact `device_signature`、完整 `authorize_event` 与当前设备 fresh proof；`challenge_proof` 的 transcript 与验签规则见 [`device-lifecycle.md` §2.1.2](../crypto-media/device-lifecycle.md)，target `device_signature` 的 `accepted_device` possession domain 与签名对象见 [`device-lifecycle.md` §5.2](../crypto-media/device-lifecycle.md) §5.2.2。服务端必须按普通 Event admission 接受该 exact submission，不得自行 mint Event 或直接写 device projection。`/_arkret/self/devices/pairing-requests*` 不是 v1 core approval surface。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->
6. Events API / identity registry durable 接受并传播 `ak.device.authorize` 与 `ak.device.list_update`；gate 返回 `authorized_event_ref` 或等价引用。新设备可通过 `ak.key.verification.done` 中的 hint、重新签发/升级后的 session grant、或后续 account subscribe/device list baseline 观察结果，但 MUST 以 durable device list 为准；只有观察到该 exact authorize Event 已进入 current durable device list 后，才可发送 `ak.secret.request`、开始同步 Event history、Realm membership 和必要的 MLS Welcome / key share。

如果用户没有任何可用的已授权设备，UI SHOULD 明确优先提示"在已有设备确认"；确认不可用后，才进入恢复密钥 / social recovery 路径。新设备仅凭登录 session grant MUST NOT 获得 E2EE history key。

`ak.device.authorize.payload` 示例：

```json
{
  "principal_id": "ak:did_core:webvh:zQ3shExampleScid",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "device_public_key_did": "did:key:z6Mks...",
  "hpke_key": "z6LS...",
  "algorithms": ["ak.mls.v1"],
  "device_key_algorithm": "Ed25519",
  "authorized_by": "ak:device:01964136-8000-7000-8000-000000000000",
  "authorization_binding_kind": "accepted_device",
  "not_before": "2026-04-26T00:00:00.000Z",
  "device_signature": "base64url..."
}
```

`authorization_binding_kind="accepted_device"` 下 `authorized_by` 是**批准设备自己的 `device_id`**，不是它所属 principal 的 `did_core_id`；`registration_anchor` 与 `pcr_recovery` 才使用目标 account authority pair 的 principal `did_core_id`。批准方 accepted device 以 authorize Event proof 对完整 payload 签名；`verification_method` 必须由该 Event accepted-at 的 `did` 与 method evidence 验证，解析后的 base 必须投影为 `principal_id`，不得要求 current DID resolution。该 proof 也是 `principal_id` / `authorized_by` / `not_before` / `expires_at` / `scopes` 的唯一签名承载；新设备的 `device_signature` 只在 `accepted_device` possession transcript 上证明持有 candidate key 与自己的 `hpke_key` / `algorithms`。candidate overlay 只用于 registration genesis 与 PCR recovery unit，普通 pairing 不允许目标设备自我授权。

### 5.2 设备吊销

设备丢失、出售、被恶意控制或员工离职时，MUST 发布 `ak.device.revoke`。

吊销后：

- Events API MUST 拒绝该设备的新签名写入
- authz MUST 视相关 session grant 失效
- 加密 Realm SHOULD 通过 MLS Remove 推进 epoch；Commit 的 `governance_binding.security_frontier_digest` MUST 从已经包含该 `ak.device.revoke` 或已导入该撤销的 Realm leaf-remove Move 的 accepted state 重算，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖
- 客户端和受托 projection executor SHOULD 标记已撤销设备产生的未确认 Operation 为高风险

## 6. Session Grant

Session grant 用于 OIDC / SSO、浏览器短会话与远程执行环境。Arkret v1 的
`kind="ak.session.grant"` 是 Account Authority / Auth Server 对自身授权决定签发的短期 credential
kind，**不是** Event kind。它的唯一 durable lifecycle 权威是 issuer 自己维护的 ledger；Principal
Control Realm 不保存 grant genesis、grant state cell 或其任何投影。

`SignedSessionGrantClaims` 示例（`session_public_key` 的值是 canonical public-JWK JCS 字符串）：

```json
{
  "kind": "ak.session.grant",
  "jti": "ak:session_grant:AZ0oygQqi49PKjNV8SXyFW3rediuQPhSh-cimdK5R62n",
  "issuer_id": "ak:did_core:webvh:z6mkfixtureauthaexample",
  "issuance_nonce": "AAECAwQFBgcICQoLDA0ODxAREhMUFRYXGBkaGxwdHh8",
  "subject_id": "ak:did_core:webvh:z6mkfixture",
  "session_public_key": "{\"crv\":\"Ed25519\",\"kty\":\"OKP\",\"x\":\"11qYAYdk9Jc1iP4Z9Qv7XKpM6Jw8LmN0RsTuVwXyZaB\"}",
  "audience_id": "ak:did_core:webvh:z6mkfixtureserviceexample",
  "scopes": [
    "ak.self.account.read.describe.v1",
    "ak.self.events.read.scan.v1"
  ],
  "not_before": "2026-08-08T12:00:00.000Z",
  "expires_at": "2026-08-08T13:00:00.000Z",
  "session_id": "session-chain-fixture-001",
  "credential_class": "standard",
  "holder_binding": {
    "kind": "human_device",
    "device_binding": "ak:device:019a0000-0000-7000-8000-000000000001"
  },
  "device_binding": {
    "device_id": "ak:device:019a0000-0000-7000-8000-000000000001",
    "authorization_event_id": "ak:event:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    "model_generation_ref": 1
  },
  "proof_kind": "account_handoff"
}
```

该示例逐字段复用
[`session-grant-issuance-fixture.json`](../../artifacts/fixtures/session-grant-issuance-fixture.json) 的
`issuer_a_closed_preimage` KAT；其 canonical preimage、digest 与 `jti` 必须可机械复算一致。

### 6.1 Issuance record 与 ID（normative）

issuer 必须从下面的 closed immutable preimage 派生 SessionGrant ID：

```text
issuance_preimage = JCS({
  schema: "ak.session_grant.issuance.v1",
  issuer_id,
  issuance_nonce,
  subject_id,
  session_public_key,
  audience_id,
  scopes,
  not_before,
  expires_at,
  session_id,
  cnf,
  credential_class,
  device_binding?,
  holder_binding,
  proof_kind?,
  scope_details?
})

grant_digest = SHA-256(issuance_preimage)
grant_id = "ak:session_grant:" ||
  base64url_no_pad(sha256_digest_suite_wire_code || grant_digest)
JWT jti = grant_id
```

`sha256_digest_suite_wire_code` MUST 取自
[`digest-suite-registry.json`](../../artifacts/registry/digest-suite-registry.json)，不得复制 Event token 的私有
常量。它在当前 profile 中是完整 `0x01` byte；v1 只接受高 nibble 为零的 active suite code，但不得把该
零 nibble 解释成 Realm 的保留高 nibble。`issuance_nonce` MUST 是 issuer 为本次逻辑签发生成的 256-bit CSPRNG nonce，并以恰好 32 octets
的无 padding Base64URL 作为 signed claim。`scopes` MUST 在授权求交后按协议 byte-wise 排序去重；时间
MUST 使用 UTC canonical millisecond；optional 字段无值时 MUST 省略而非写 `null`。

credential class、holder binding 与 human device authorization binding 都是 preimage 的身份材料：Arkret v1
的 `credential_class` 固定为 `standard`，并且 MUST 携带 `holder_binding`。`holder_binding.kind="human_device"`
时完整 `device_binding` 必填且只能逐字取自 origin current-device gate 的 `allow` receipt；
`holder_binding.kind="agent_runtime"` 时 `device_binding` 禁带。current-v1 不存在缺 `device_binding` 的
fresh-device human grant。恢复完成在核验 replacement device 后直接签发同一种 Standard grant，不存在临时
恢复凭据类。因而修改任一 binding 必须改变 canonical preimage、digest、grant ID 与 `jti`；verifier 不得把
binding 当作不参与 ID 的附加 metadata。

`session_public_key` MUST 先解析为受支持且不含 private member 的 public JWK，再编码为 RFC 8785 JCS
UTF-8 字符串；JWT claim 自身必须携带该 canonical 字符串。接收方重新解析并序列化后若不能逐字节得到
相同字符串，MUST 拒绝。`audience_id` 的 canonical 形态是目标 resource service 的稳定 `did_core_id`，
与 `SessionGrantRequestProof.audience_id`、issue/refresh outcome 的 typed `DidCoreId` 相同；HTTP origin / endpoint URL
由 DPoP `htu` 单独绑定，MUST NOT 写入 SessionGrant `audience_id`。该选择与 SDK 的 `DidCoreId` wire type及 Account
Authority 对 non-DID audience 的 fail-closed 校验一致。preimage 不含独立顶层 `device_id`：human device
绑定由 required `holder_binding={kind="human_device",device_binding}` 表达；Agent runtime 绑定由对应的
`holder_binding` 分支表达。operation `scopes[]` 只承载授权求交后的服务操作，不得再编码设备身份或旧
`session.bind` 哨兵 scope。

除固定 `schema`、固定 credential `kind` 与派生结果 `jti` 外，preimage 的每个字段都 MUST 是 JWT 的
signed claim。verifier MUST 验证 JWT signature、issuer key 的 accepted-at 历史，并从 signed claims
重算 preimage、digest 与 typed ID，要求结果与 `jti` 逐字节相等。仅验证 `ak:session_grant:` 外形不构成
有效验证。该 ID 的 `id_form=suite_tagged_full_digest`，是 33-octet `uint8 digest-suite wire code ||
32-octet digest` token；它不是 Realm / Event 的 `reserved-zero nibble || 4-bit suite` header，不是 Event
ID，也不是 `ak:grant:` Capability
GrantId；不得提供 Event retype、`from_event_id` 或 accepted-Event marker 路径。跨 issuer 的 durable
identity/replay key MUST 使用 `(issuer_id, typed_id)`。

`session_id` MUST 在首次签发前由 issuer 独立分配，作为稳定的 rotation-chain ID；refresh 继承它。
`session_id` MUST NOT 等于或派生自 `grant_id`，否则 ID derivation 形成自引用。

### 6.2 签发、签名边界与 durable exact replay（normative）

Account Authority MUST 先验证 account↔principal binding、登录或恢复 proof、当前 holder DPoP、`audience_id`
与 scope ceiling，再建立 issuer-owned issuance operation。issuer 必须在响应前原子持久化 canonical
intent、request identity、preimage bytes、nonce、digest、grant ID、完整 JWT、signing key id、状态与时间；
JWT 是该 immutable issuance record 的签名投影。Coauth/Account Authority 只签自己的 JWT 与 issuer
status，MUST NOT 获取或使用 principal/root/device/notary 私钥，MUST NOT 为 SessionGrant 构造或提交
`/_arkret/self/events` Event，也 MUST NOT 等待 PCR frontier、Seal 或 `accepted[]`。

每个 production proof 分支 MUST 提供稳定 request identity；ledger key 至少包含
`(issuer_id, operation_or_proof_kind, request_identity)`。同 key + byte-identical canonical intent MUST 在
进程重启、并发重试及 commit 后响应丢失时返回首次持久化的同一 nonce、grant ID 与 byte-identical JWT；
同 key + 不同 intent MUST `duplicate_conflict` 且零新 grant、零状态变化。replay lookup 仍 MUST 重新验证
本次 holder/DPoP、HTTP method/target、`issuer_id` / `audience_id` 与 canonical request digest；它只复用已持久化的
one-shot proof 验证结果，不允许仅知道 request identity 的第三方取回 JWT。

若 replay 命中的记录已经 expired，MUST 返回 `session_grant_replay_expired`；若已 `revoked` 或
`superseded`，MUST 返回 `session_grant_replay_terminal`。两种响应的 closed details 都 MUST 携带原
`grant_id` 与 exact state，MUST NOT 返回成功或在同一 request identity 下补发 credential。replay record
保留期 MUST 不短于相应 one-shot proof 的最大可重试窗口；保留期后无法判定旧请求是否提交时 MUST
`session_grant_replay_indeterminate`，不得把它当首次签发。客户端收到这三类结果后必须取得新的 one-shot
proof 与 request identity，重新走完整认证。

### 6.3 Lifecycle、refresh、revoke 与 introspection（normative）

issuer ledger 的 durable state 是 `active | revoked | superseded`；`expired` 只从 immutable
`expires_at` 判定，不写状态 Event。refresh MUST 以
`(predecessor_grant_id, refresh_request_digest)` 作为稳定 request identity，在同一 issuer transaction
中创建 active successor、继承独立 `session_id`，并把 predecessor 原子转为 `superseded`、记录
`successor_session_grant_id`；commit 后才可返回 successor JWT。exact refresh replay 返回同一 successor，
不得创建第二个 successor。revoke/logout MUST 幂等地把 active record 转为 `revoked`；revoke mutation
还必须以 issuer、operation kind、authenticated session/principal、canonical selector 与 request digest
构造稳定 request identity，durable 保存首次 exact outcome。同 identity + 同 intent 在重验当前调用方授权后
返回 byte-identical outcome；同 identity + 异 intent 返回 `duplicate_conflict` 且不得再次改变状态。
account、device 与 Agent-key lifecycle cascade 也必须更新同一 ledger，不得声称生成 principal Event。

introspection MUST 从该 ledger 返回当前状态，绑定 issuer proof/key 与 exact authenticated request。
跨服务可转交的 status MUST 带 issuer/service signature；同一部署的直接响应至少必须经过 authenticated
channel 并绑定 exact request。Resource server 的本地 session/cache 只是有 freshness 上限的投影，不能
覆盖 ledger；issuer key rotation 必须保留 signing key id，并按 accepted-at key history 验证既有 JWT，
不得用当前 key 重签历史 exact-replay outcome。

### 6.4 客户端 Event signer 边界（normative）

SessionGrant request/DPoP 由当前客户端的 grant-binding key 签，credential 由 issuer key 签；两者都不
替代 principal Event proof。若其它 Account Authority operation 确实需要 principal Event，服务只能返回
closed canonical draft/basis/material，由持有当前有效 principal/device/notary key 的客户端签 exact Event
并提交，receiver 必须独立验签。relay 或 S2S HTTP Message Signature 只认证 transport，MUST NOT 代签或
替代内层 Event actor proof。首次 onboarding 的 Recovery root 继续只承担登记的冷根职责，MUST NOT 因
SessionGrant 签发而扩张为日常 Event signer。

规则：

- session grant MUST 由可信 issuer 签名，且 session key MUST NOT 超过 grant 的有效期；
- session grant MUST 绑定 `audience_id`；
- 在条件允许时，session grant SHOULD 在 WebCrypto / 平台 keystore 中以不可导出方式存储；
- canonical 撤销真相只能来自 issuer ledger、immutable `expires_at` 或触发 ledger cascade 的 current
  account/device/Agent lifecycle；不得另建 Event cell、未注册 revocation-list ID 或第二套状态源。

## 7. 密钥备份

### 7.1 备份内容

`backup_kind=mls_history` 的一个 object MUST 只属于一个
`content_scheme=mls_exporter_aead_v1` effective scope。Public `contents` 只包含一个
`history_secret_ranges` index（exact scope 与 ranges）；解密后的
[`key-backup-plaintext.schema.json`](../../artifacts/schemas/key-backup-plaintext.schema.json) items 只包含 packed
`HistorySecretRange {from_epoch,to_epoch,secrets_b64u}`。Decoded bytes 严格等于按 epoch 升序拼接的 secrets，总长
`(to-from+1)*KDF.Nh`；suite 必须从 receipt-bound direct Seal replay 得到的 exact winning transition 解析，不得在 backup 自报。
每个被写入的 secret 必须是本 endpoint 从已完整验证并实际应用的 MLS state 直接导出的 `local_authoritative` 项。History response、
RRK open 或其它外部 carrier 收到的 candidate 即使已成功解密某个 Event，也不得写入 portable backup；它只能留在 device-bound
multi-candidate store。

多 scope 或超预算历史拆成可列举的多个 object，由 series sequence/supersedes 提供 anti-rollback。History backup
不得含 secret_id/version、policy/membership digest、group-state ref、active group state、epoch secret-tree state、
pending Welcome、leaf signing key、ratchet、proposal 或 sender counter；restore 只能写 history-only decrypt store。
新设备的 authoring state 只能由新 KeyPackage/Welcome 建立。Standard MLS、plaintext 与 Sidecar 不得创建
`mls_history` object。


### 7.2 Backup Envelope

`ak.schema.key_backup.v1` 是 encrypted, signed, append-only series envelope。上传设备必须用当前 accepted device key 签署完整 metadata 与 ciphertext digest，并携带 `device_authorize_event_id`。`frontier_ref` 只有 `device_generation_ref` 分支；该字段是最小值为 1 的 PCR-local monotonic integer，绝不是 DID `versionId` 或其字符串编码。该值、`frontier_digest` 与可选 `seal_ref` 必须指向创建时可验证的 PCR frontier。Receiver 从 PCR authorization chain 解析签名 key，拒绝 revoked/fenced/conflicted device、错误 authorize ref、stale frontier、破损 supersedes chain 或 digest mismatch。

`domain_separation` 只携带 producer 选择的 `subdomain` 与可选 `aead_aad_extensions`；不得携带 `hkdf_info` 或固定 AAD 成员的 wire 镜像。`hkdf_info` 的唯一派生式是 `arkret-key-backup/<backup_kind>/<subdomain>/v1`。AEAD/HPKE AAD 的唯一构造过程如下，sealer 与 opener MUST 使用同一过程，任一输入缺失、扩展名非法或扩展与固定字段冲突时 MUST 在解密前 fail closed：

1. 从 `contents[].item_kind` 取 UTF-8 字节串，按 unsigned UTF-8 bytewise lexicographic order 排序，并按逐字 byte equality 去重，得到唯一的 `item_kinds` 数组；content 原始顺序和重复 item 不得改变 AAD。
2. 构造固定 base object：`{schema:"ak.schema.key_backup.v1",actor_id,device_id,backup_kind,backup_version,created_at,item_kinds,recipient_method}`。`device_id` 缺失时 base 中该 key 的值固定为 JSON `null`；`recipient_method` 从 `encryption.recipient_method` 派生。仅当 `encryption.recipient_key_ref` 实际存在时，向 base 加入 `recipient_key_ref`。
3. 将 `domain_separation.aead_aad_extensions` 的每个 `x_*` 成员逐字合并进 base；extension map 不得包含非 `x_*` 名称，也不得覆盖任何固定成员。
4. `aead_aad_bytes = RFC8785_JCS(merged_base)`。该字节串同时用于对称 AEAD AAD 与 §7.5.2 HPKE `aad`；无扩展时对空 map 不增加任何成员。

Envelope 的签名输入固定为 `RFC8785_JCS(envelope 删除 auth_data.signature)`。因此顶层所有实际存在的 required、optional 与 `x_*` 成员，以及 `auth_data` 中除 `signature` 外的成员，都自动进入同一转录；缺席的 optional 成员不进入对象，producer 不得改写为 `null`。wire 上不携字段名清单，receiver 也不得按调用方提供的清单选择投影。

server 只存 ciphertext、索引和 signed metadata，不能解密、重签或选择 primary recovery series。closed plaintext keybag 的 item kind 由 schema allowlist 决定，不包含 identity-root 或 device private key。

### 7.3 恢复流程

恢复流程：

1. 新设备生成 device key。
2. 用户输入 Recovery Key（24 词助记词，§3.3），或按 recovery policy 收集 recovery shares / 完成硬件解锁；仅当目标是 `passphrase_kdf` envelope 时才输入对应口令（§7.5.1）。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `ak.device.authorize`。
6. 若涉及 E2EE Realm，客户端拉取 MLS state 并处理 epoch 缺口。

恢复 device key 时 MUST 生成新的 device key，不得把备份中的旧设备身份克隆到新设备。fresh device 的 active MLS membership 只能由该设备自己的 accepted authorization、新 KeyPackage 与 accepted Welcome/Commit 建立；portable history material 只能进入 history-only decrypt lane，不能提供 Commit/application signer。恢复出的账户级非身份 secret 只能恢复其声明用途；不得用于克隆旧设备身份或绕过 pairing/re-anchor。

same-endpoint crash resume MAY 使用本地、device-bound、不可移植的 active MLS state，但 record principal/device 必须与当前 endpoint 完全相同、PCR device 仍 current、scope/group/epoch/ref 不回滚。该本地 state 不得上传进 human `mls_history` backup。foreign-device full snapshot 的 active install/send MUST 拒绝。

### 7.3.1 Account MLS root 与 durable recovery unit（normative）

只有经验证的账号首次 enrollment 显式 API MAY create account MLS root。root 必须先 durable commit，或与首个依赖 snapshot 原子提交，之后才能生成任何依赖密文。其它 account-data、saved content、file transfer、MLS bootstrap/join 与普通 feature API 只能 load existing root；缺失时返回 `recovery_required` 并走既有 recovery/pairing，MUST NOT 隐式 mint replacement。

wrapping root、加密 snapshot、`group_state_refs` 与 genesis/commit emitted marker 构成一个 durable recovery unit：必须同一事务提交，或使用 durable-first + 启动交叉验证达到等价原子性。marker 声称材料存在而 root/snapshot/ref 缺失、epoch/ref 回滚或材料解不开时必须进入 `recovery_required`；不得在相同 derived group id 下重铸另一棵 tree。account-data、MLS active snapshot 与 history backup 继续使用独立 HKDF subdomain。

### 7.4 所有权证明与解密证明

DID 控制权证明 SHOULD 优先使用签名挑战，而不是“能解开某段历史密文”：

- 当前控制密钥、已授权 device key 或 recovery key 对服务端 fresh challenge 签名。
- 新设备生成 device key 后，由当前有效设备或 recovery policy 签发 `ak.device.authorize`。
- recovery service 在 DID Document、organization policy 或 recovery policy 中被明确声明，并签发可验证 recovery event。

“能解密用某个公钥加密的数据”MAY 作为恢复流程中的一个密码学因子，但不得单独等同于账号所有权。允许的形式是：服务端生成短期随机 challenge，按当前 key-log / recovery policy 指定的 recovery public key 加密，客户端在本地解密后对 challenge transcript 签名或返回 proof。该流程 MUST 绑定：

- `challenge`
- `audience` / `origin`
- `service_id`
- `principal_id`
- `key_id`
- 过期时间
- 防重放 nonce

实现 MUST NOT 把以下情况当作独立恢复依据：

- 用户能解密某条历史消息、历史 Blob、先前 MLS epoch 或先前备份。
- 用户能提供某段历史明文。
- 用户知道 service account 密码或邮箱验证码，但没有 DID / recovery proof。
- 用户持有已经撤销、过期或不在当前 recovery policy 中的设备密钥。

安全风险：

- **密钥用途混淆**：内容解密密钥、MLS epoch key、backup key 和 DID 控制密钥不是同一种权力。
- **失效密钥复活**：被移除成员或已撤销设备可能仍能解密既有内容，但不应重新获得账号控制权。
- **弱口令备份被盗**：攻击者获得云端备份密文后可以离线爆破 passphrase。
- **解密 oracle**：服务端若允许任意密文挑战，可能被滥用为私钥 oracle；challenge 必须是固定格式、短期、限速且只针对声明的 recovery key。
- **钓鱼与中继**：攻击者可能诱导用户解密 challenge；proof 必须绑定 domain / service DID / audience，并在 UI 中展示高风险恢复意图。
- **隐私泄露**：用历史内容证明所有权会向恢复服务暴露用户拥有或可读哪些私有内容。

因此，解密能力最多是 recovery factor；真正改变 DID 控制状态必须落成 DID method history、key log、`recover`、`rotate`、`ak.device.authorize` 或等价 signed event。

#### 7.4.1 备份签名的设备信任根锚定（normative）

`auth_data.verification_method` 必须是 DID URL：其 bare `did` 经 method adapter 投影必须等于
`actor_id`，fragment 必须等于 `device_id`；不得把 core `actor_id` 直接拼接 fragment。
`device_authorize_event_id` 必须解析为该 device 在 envelope frontier 的 accepted authorization。Verifier
KeyPackage 对外 claim 不携带 PCR/device history sidecar。origin Station 在本地检查 registration、generation 与 revocation后签发承载该 KeyPackage 的 admission/claim；普通 Event federation receiver 只验证 Event 内嵌 admission proof。

### 7.5 Recipient Method Profiles

`ak.schema.key_backup.v1.encryption.recipient_method` 枚举 3 种 envelope 解锁方式。每种方式 MUST 按下列 normative 约束实现；服务端遇到本节未定义的 `recipient_method` MUST fail closed。

#### 7.5.0 `backup_kind` × `recipient_method` 合法组合矩阵（normative）

`backup_kind`（仅 `secret_storage` / `mls_history` 两类，§7.1）与 `recipient_method` 的组合不是自由叉乘。下表是合法组合的**集中**声明；producer MUST NOT 写入标 `forbidden` 的组合，receiver / 服务端遇到 `forbidden` 组合或本表未列出的组合 MUST fail closed（reason 见各格），即作为兜底也不允许：

| `backup_kind` ＼ `recipient_method` | `passphrase_kdf` | `recovery_public_key` | `secret_storage_key` |
| --- | --- | --- | --- |
| `secret_storage` | allowed（见 §7.5.1）: §7.2 / §7.5.1 Argon2id 或显式 degraded PBKDF2；新创建 envelope 满足 §7.2 机器下限 | allowed（新写入 SHOULD 优先，见 §7.5.1） | allowed: 仅现有持有 root key 的设备本地缓存/同步，新设备 MUST NOT 直接 bootstrap，否则循环依赖 |
| `mls_history` | forbidden: `mls_history_passphrase_forbidden` | allowed：MUST 带签名覆盖的 `recovery_policy_ref` | allowed：释放仍以 active-series record / frontier_ref / Realm-MLS 授权 / 设备状态为准 |

集中要点（与下列 §7.5.1–§7.5.5 的分散规则一致，本表为 normative summary）：

- **`passphrase_kdf` 仅 `secret_storage`**：`mls_history` MUST NOT 使用 `passphrase_kdf`，即便作为 fallback 也不允许（单一口令不得直接解锁 MLS 历史）。需要口令参与时，口令只能先解锁 `secret_storage` root、recovery private key、threshold share 或 hardware wrapper 的本地保护层，再由 `recovery_public_key` / `secret_storage_key` 完成对应 `backup_kind` 的释放。
- **recovery 私钥释放强度（normative 澄清）**：本矩阵在 envelope 层禁止 `mls_history` 用低熵口令派生（`passphrase_kdf`），确保 E2EE 历史不被单一**低熵**口令直接控制。recovery **私钥本身**的释放强度由 §8 recovery policy 的 `allowed_proof_kinds` 决定：当 policy 仅配置单个 `recovery_unlock`（单把高熵 24 词助记词签名）时，恢复强度即等同于该单一高熵助记词——这是 v1 default profile **有意接受**的取舍（高熵单因子 ≠ 低熵口令）。高价值 / 组织账号 SHOULD 按 §7.11（"高价值账号 SHOULD 支持门限恢复"）叠加门限（`threshold_recovery`）或多 `proof_kind`，不依赖单一可窃取秘密。
- **`secret_storage_key` 不可 bootstrap**：新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap，必须先用 `passphrase_kdf` 或经 recovery policy 释放的 `recovery_public_key` 解出 root secret storage key（消除"新设备能解 wire envelope"的循环依赖）。
- **门限/硬件属于 recovery policy 层**：threshold、hardware module、trusted recovery service 可以保护 recovery private key 或 secret storage root 的释放，但不得作为 `ak.schema.key_backup.v1.encryption.recipient_method`。相关 proof transcript 由 §8 recovery policy 与 `ak.schema.recovery_session.v1` 约束。
- 所有 fail-closed 判定 MUST 在解密尝试之前完成；服务端 / receiver 不得对 `forbidden` 组合"先解密再检查"。

#### 7.5.1 `passphrase_kdf`

参考 §7.2：Argon2id（或显式 degraded PBKDF2）派生 root key，HKDF 派生 `commitment_key` 与 `nonce_key`，AEAD AAD 覆盖全部 envelope metadata。`passphrase_kdf` 仅用于 `secret_storage` envelope；`mls_history` envelope MUST NOT 使用 `passphrase_kdf`，即使作为 fallback 也不允许。需要用户口令参与 MLS 历史恢复的实现 MUST 让口令先解锁 `secret_storage` root、recovery key、threshold share 或 hardware wrapper 的本地保护层，而不是在 wire 上发布 `backup_kind="mls_history", recipient_method="passphrase_kdf"` 的 envelope。

**与 recovery secret 的关系（normative）**：内容恢复的标准用户凭证是 §3.3 recovery secret；它经固定域派生 backup-HPKE key。实现 SHOULD NOT 引入独立 vault 口令作为标准凭证。

- 新写入的 `secret_storage` envelope SHOULD 使用 `recipient_method="recovery_public_key"`（加密给 §3.3 backup-HPKE public key）；`passphrase_kdf` envelope MAY 用于实现自选的口令派生场景。
- `passphrase_kdf` 是合法 wire `recipient_method`：服务端 key-backup 端点（§7.8、[`../crypto-media/device-lifecycle.md` §12.1](../crypto-media/device-lifecycle.md)）不区分凭证来源，`passphrase_kdf` envelope MUST 可被列出、读取与删除，本节与 §7.2 的 KDF / nonce / commitment 约束对其适用。

#### 7.5.2 `recovery_public_key`

DEK 通过 HPKE（base mode）加密给 `recovery_public_key`：

- `recipient_key_ref` MUST 是 envelope 的 `recovery_policy_ref` 所指 accepted recovery policy（§8）中 `recovery_key_agreements[].key_agreement_ref`。DID Document-only `recoveryKeyAgreement` 不是授权源，MUST reject。该 ref MUST NOT 指向 `recovery_keys[].verification_method`：后者只标识 recovery-proof 签名 key。receiver 必须从同一 policy entry 取得 X25519 `public_key_multibase`，并确认 `encryption.hpke_suite` 在该 entry 的 `hpke_suites` 中。
- HPKE suite MUST 是 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active 行，由 `encryption.hpke_suite` 选定；该字段缺省时 MUST 解释为 default-MUST 行 `ak.hpke_x25519_aead_chacha20poly1305.v1`。`aead.name` MUST 等于所选 suite 的 AEAD。遇到未登记、非 active 或 reserved-未激活的 suite id，receiver MUST fail closed（`unsupported_hpke_suite`），MUST NOT 自由组合未登记的 KEM/KDF/AEAD，也 MUST NOT 仅凭 `aead.name` 推断 suite 参数。P-256 KEM 互操作经 profile-gated 行 `ak.hpke_p256_aead_aes256gcm.v1`（`ak.profile.hpke.p256.v1`）提供。HPKE 单发 base-mode 由 key schedule 内部派生 AEAD nonce，故 `recovery_public_key` envelope 不携带 wire `nonce`。
- HPKE `info` MUST 包含 `canonical_json({backup_id, series_id, series_seq, actor_id, backup_kind, backup_version, created_at})`；HPKE `aad` MUST 等于 envelope 的 AEAD AAD。
- 普通 DID root generation 轮换不改变 backup-HPKE key。只有 recovery secret handoff 才改变 recipient key；handoff 后所有 active backup class MUST 按 §3.3 建新 series/重封装并推进 signed active-series pointer。
- 任何 `recipient_method="recovery_public_key"` envelope 都 MUST 携带 `recovery_policy_ref{policy_id, policy_version}`；它作为实际存在的顶层成员自动进入 §7.2 的完整 envelope 签名转录。`recipient_key_ref` 只在该 accepted policy 的 `recovery_key_agreements[]` 中解析。各 backup class 在读取/恢复时 MUST 验证 referenced policy 仍属于该 principal 的 accepted policy history，并按 active-series 与轮换规则拒绝回滚。不匹配 MUST `recovery_policy_mismatch`。这项 policy 绑定不替代 MLS 历史或 secret-storage 的独立授权判断。
- **备份接收 key 的角色隔离（normative）**：wire 名称 `recovery_public_key` 指 §3.3 派生的 X25519 backup-HPKE public key。它与 Ed25519 recovery-proof key、任一代 identity root 是不同 key，但三者来自同一用户 recovery secret。实现 MUST NOT 在 `secret_storage` 中再制造第四把长期 backup keypair，也不得把 Ed25519 key 转换成 X25519 key。

recovery policy 中两类 key 必须显式配对：`recovery_keys[]` 每项携带 recovery-proof 签名 `public_key_multibase` 与独立 `key_agreement_ref`；该 ref 必须唯一解析到同一 policy 的 `recovery_key_agreements[]`。后者 `use="backup_hpke"`，只能接收备份，不能验 recovery proof 或授权 DID/Event。两数组与配对 ref 作为实际存在的 policy 顶层成员自动进入 §8.1 的闭合 policy 签名投影；缺项、悬空或重复 ref、同一 key material、suite 不匹配、已撤销/过期、DID Document-only 旁路均 fail closed，并由 `ak.vector.identity.recovery_key_role_separation.v1` 执行验证。

#### 7.5.3 `secret_storage_key`

仅用于已经持有 `secret_storage` root key 的现有设备本地缓存/同步（不是 bootstrap）。

- `recipient_key_ref` MUST 命名一个已经在该设备 device-local secret storage（参见 `crypto-media/device-lifecycle.md` §11 `ak.secret_storage.v1`）中存在的 key id（例如 `mls_group_secrets_backup_key`）。
- 当 `backup_kind="mls_history"` 使用 `secret_storage_key` 时，envelope MAY 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 作为恢复流程 hint；若出现，它自动进入 §7.2 的完整 envelope 签名转录，receiver MUST 验证它与当前 accepted recovery policy 一致。MLS 历史材料的释放仍以 active-series record、frontier_ref、Realm/MLS 授权与设备状态校验为准。
- 新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap：它必须先经 recovery policy 接受 recovery proof，再由用户 recovery secret 派生 backup-HPKE private key以打开 `recovery_public_key` envelope，之后才能拉取 `secret_storage_key` envelope。
- 这是为了消除"新设备能解 wire envelope"的循环依赖。
- **AEAD nonce 唯一性（normative）**：`secret_storage_key` 是长期复用的对称 wrap key，因此 `aead.nonce` MUST 在该 `recipient_key_ref` key 的整个生命周期内对每条 envelope 唯一——producer MUST 为每条新 envelope 生成至少 96-bit 的随机 nonce（或在该 key 下严格单调不回绕的 counter），且 MUST NOT 用同一 (`recipient_key_ref` key, `aead.nonce`) 对写第二条 envelope；需要更新内容时 MUST 生成新 `backup_id` 与新 `nonce`，并 SHOULD 轮换底层 wrap key。`nonce` 作为 `encryption.aead` 成员自动进入 §7.2 的完整 envelope 签名转录，并进入 AEAD AAD。该约束与 `passphrase_kdf` 的 `nonce_salt` deterministic derivation（§7.5.1）、`recovery_public_key` 的 HPKE 内部 nonce 派生共同关闭三种 `recipient_method` 的 nonce-reuse 面。

#### 7.5.4 门限恢复作为 recovery policy 层

v1 core 不把 `threshold_recovery` 作为 `ak.schema.key_backup.v1.encryption.recipient_method`。门限恢复在 policy 层重建/释放 recovery secret 或明确的 backup-HPKE key material；客户端随后用 `recovery_public_key` 或 `secret_storage_key` 解开 envelope。

- 每份 share 的取回 MUST 绑定当前 recovery 流程的 `recovery_session_id`（见 [`../crypto-media/device-lifecycle.md` §14](../crypto-media/device-lifecycle.md)）；holder 服务 MUST NOT 把同一 share 多次释放给不同 session 而不经显式授权。
- reconstruction 完成的 recovery secret、PRK 或任一派生 private key MUST NOT 写入在线持久化存储；上下文在用途结束后立即清除。
- share commitment 校验：reconstruction 前 client / recovery coordinator MUST 验证每份 share 与 `recovery_policy.threshold.shares[].share_commitment` 一致；失败时 MUST `share_commitment_mismatch` 并通知用户特定 holder 提交了 invalid share。

#### 7.5.5 硬件包装作为 recovery policy 层

v1 core 不把 `hardware_wrapped_key` 作为 `ak.schema.key_backup.v1.encryption.recipient_method`。硬件模块、HSM、TPM 或 Secure Enclave 只能作为 recovery policy unlock factor：它们释放 recovery secret、threshold share、backup-HPKE key 或 secret-storage root 的本地保护层。

- recovery policy MUST 记录被信任的 hardware / service profile、wrap key 稳定标识与 attestation 要求；proof transcript MUST 绑定 `recovery_session_id` 与当前 challenge。
- receiver MUST 验证当前的 hardware attestation evidence 仍声明同一 key id（即设备未在静默状态下被替换），并且该 profile 属于当前 accepted recovery policy。
- 任何 envelope 单纯展示 `recipient_method=hardware_wrapped_key` MUST 被 schema/receiver 拒绝为未知枚举值；缺少 attestation chain 的 recovery proof MUST `attestation_missing`。

#### 7.5.6 Agent PCR history-only backup（normative）

Conformance vector：`ak.vector.agent.pcr_history_backup.v1`。

`mls_history` wire 是 history-only exporter secret backup；无论 ordinary human、Agent 或 Agent PCR，均不得携带
`mls_group_state`、`mls_epoch_secret`、`pending_welcome`、leaf signer、ratchet、proposal、sender counter 或 active snapshot。
Controller-owned backup 不能成为跨 principal 的 active-state exception，也不能把 Agent PCR active MLS private state 混入 controller
自己的 series。`managed_principal_binding`、`managed_frontier_ref` 与 `agent_pcr` backup subdomain 不属于 v1 wire。

Agent 或其 controller fresh endpoint 恢复时，只能安装 schema 允许的 history-secret ranges；这不会恢复 active leaf、runtime
signer、counter 或 current group state。Fresh endpoint 必须按当前 authorization 重新生成 runtime key，并经标准 KeyPackage/
Welcome/Add 进入唯一 derived group；同 endpoint crash-resume 若使用 device-bound local snapshot，只属于 §7.3 的本地不可移植状态，
不得上传。Pairing admission 只验证当前 controller/Agent authority、proof-of-possession 与 accepted control frontier，不得要求一个 wire
上无法承载的 `pcr_recovery.status=ready` active-snapshot gate。

### 7.6 Backup Series & Freshness

每个 `(actor_id, backup_kind)` 的 series 使用严格递增 `series_seq` 与 digest-bound `supersedes` 链。Active-series record 必须由当前 accepted device 签名，签名输入固定为 `RFC8785_JCS(record 删除 auth_data.signature)`；闭合 record 的全部实际存在成员自动受认证，不携字段名清单。record 携带其 `device_authorize_event_id`，并以整数 `frontier_ref.device_generation_ref` 绑定 current generation。Receiver 选择已验证的最高 pointer version，拒绝回滚、fork、链缺口、旧 generation 或缺少 completeness/witness evidence 的服务端列表。

### 7.7 Recovery UI Requirements（normative）

恢复 UI 是用户唯一能识别"我在恢复一个真实的自己 vs 我在被钓鱼"的界面。实现 MUST：

- 密钥备份解密凭证 MUST 是 Recovery Key（24 词 BIP-39 助记词，§3.3）：由其派生 / 解锁 recovery private key 后按 §7.5.2 HPKE-open `recovery_public_key` envelope，或按 recovery policy（§8）以 threshold / hardware 因子释放同一 recovery private key。恢复 UI MUST NOT 要求用户设置独立 vault passphrase 作为标准凭证；仅当目标 envelope 是 `passphrase_kdf`（§7.5.1）时，MAY 提示输入对应口令完成解密，并 SHOULD 在恢复成功后引导写入加密给 recovery key 的新 envelope（§7.5.2，按 §7.6 series 规则开新链或追加）。
- 在尝试解密任何备份 envelope 之前，向用户展示：`backup_kind`、`series_id`、`series_seq`、`backup_version`、`encryption.recipient_method`、`encryption.aead.aead_profile?`（缺省时显示 `aead.name`）、`principal_id`、`device_id`（当前请求恢复的新设备）与 `frontier_ref.device_generation_ref`。
- 在使用 `passphrase_kdf` 时，明确展示 KDF（Argon2id / PBKDF2）与参数；用 PBKDF2 的 envelope MUST 在 UI 中显示 `degraded_profile_reason`，且不得自动选用 PBKDF2 envelope 当 Argon2id envelope 同时存在。
- 在 envelope 携带 `mixed_secret_storage=true` 时 MUST 显著警告"该备份同时保护身份签名与 E2EE 历史，单一口令被攻破将同时丢失两者"；非 `personal_node` profile 下 MUST 直接拒绝展示此类 envelope 作为 primary recovery source。
- envelope 携带 `recovery_policy_ref` 时 MUST 展示当前 envelope 的 `policy_id` / `policy_version` 与当前 accepted recovery policy 的一致性并验证。不一致时 MUST `recovery_policy_mismatch`，并指向"更新 recovery policy"流程而不是默默继续。
- 不得从本地缓存读取用户先前确认的 fingerprint / passphrase / OOB token 跳过当次显式确认。本地缓存 MAY 用于自动补全，但用户 MUST 显式提交本次输入。
- 在 §7.4 列出的禁用证明类型（历史明文、邮箱验证码、撤销设备等）被用户尝试时 MUST 给出可读的拒绝原因。
- **无恢复路径（SPOF）账号的 fresh-device 登录警示**：`active_policy=null` 时 fresh-device recovery MUST fail closed，并提示只能由旧设备确认。存在 policy 时，UI 只展示其已接受 proof kinds；`did_root` 未启用时不得因用户持有当前 DID control 就提供重锚，启用时必须显著披露其接管风险。

### 7.7.1 Backup Unlock Proof 与 Plaintext Keybag（normative）

每次读取并尝试解密 key backup 都 MUST 产出一条 unlock proof，明文 keybag 也 MUST 有固定 schema，避免“能下载密文”被误当作“有权使用解密结果”：

- backup decrypt proof payload MUST validate as `ak.schema.key_backup_unlock_proof.v1`，其签名输入固定为 `RFC8785_JCS(unlock proof 删除 auth_data.signature)`；闭合 proof 的全部实际存在成员自动受认证，包括出现时的 `challenge`，不携字段名清单。它绑定 `recovery_session_id`、`principal_id`、`requesting_device_id`、`backup_id`、`backup_kind`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest` 与 `issued_at`。`proof_digest` 是已接受 recovery proof transcript 的 digest；receiver MUST 用当前 session state 重建 transcript 后比对，不得采信客户端自报的 policy/session metadata。
- 取回完整 ciphertext 的协议操作是 `ak.self.keys.backups.command.unlock.v1`（`POST /_arkret/self/keys/backups/{backup_id}/unlock`）：unlock proof MUST 作为 request body 的 `proof` 字段提交（`keys-operations.schema.json#/$defs/keys_backups_unlock_request_body`），path `backup_id` 与 `proof.backup_id` MUST 一致；实现 MUST NOT 用 header、query string 或私有载体承载该 proof。服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed（`recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `signature_invalid`）。
- AEAD/HPKE open 后得到的明文 MUST validate as `ak.schema.key_backup_plaintext.v1`，且其中 `backup_id`、`backup_kind`、`series_id`、`series_seq` MUST byte-for-byte 等于外层 envelope。`items[].secret_id` / `item_kind` 是 keybag 内部路由字段，不得替代外层 envelope 的授权判断。
- 实现 MUST 把 plaintext keybag 限定为本地瞬时处理材料；除非它被重新加密进本地 secret storage，否则不得持久化明文。日志、crash dump、telemetry MUST NOT 记录 `secret_b64u`。

### 7.8 Server-Side Hardening for Backup Access

加密备份的密文虽然不暴露明文，但下载即"投喂 KDF 爆破弹药"。Station device/key surface MUST 对 `ak.keys.backups.*` 接口实施：

- **每 principal 每 24h 下载上限**：默认 `daily_principal_download_limit = 64`（覆盖单一 series 下大量历史 epoch 备份的合理使用，又能拦截批量 dump）。`ak.profile.key_backup.memory_hard.v1` 实现 MUST 公布所采用的实际上限，并接受 deployment 配置在 `[16, 256]` 范围内调整。
- **每 IP / 每 session 限速**：默认 `per_ip_unlock_burst = 8`，`per_ip_unlock_sustained_per_minute = 4`；逾限响应 MUST 是 `429 Too Many Requests`，并 SHOULD 在 `Retry-After` 中给出建议。
- **认证降级阻断**：`POST /_arkret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof（与 §7.4 fresh challenge 相同绑定：challenge / audience / service_id / principal_id / key_id / nonce / 过期时间）。bearer token 单独到达 MUST 被拒绝。
- **审计记录**：超出阈值或在异常时间窗内的下载 MUST 写入 `ak.audit.accessed`，`access_kind="key_backup_read"`，并按 `ak.profile.attested_audit.e2ee.v1`（若声明）配对 audit pair。
- **跨 actor 拒绝**：服务端 MUST 在 envelope `actor_id` 与请求 caller 不一致时返回 `forbidden`，并不得通过 metadata 暴露 envelope 是否存在。v1 不定义 controller-owned Agent active-state backup，因此不存在以 `managed_principal_binding` 绕过本规则的例外。
- **删除验证**：active series 内的非尾部 envelope MUST NOT 被单独删除。`DELETE` 尾部 envelope MUST 携带 [`high-risk-authority-proof.schema.json`](../../artifacts/schemas/high-risk-authority-proof.schema.json) 的三分支之一（`principal_signing` / `device_quorum` / `trusted_recovery_service`），按 §7.8.1 绑定服务端签发的单次 challenge 并签署 canonical delete-intent transcript，然后写入 `access_kind="key_backup_delete"` 审计。普通 current device proof **不是**该 family 的第四分支：仅持普通 device proof 的 caller 只能删除 `expired_at < now` 且不属于 active series 的旧 envelope，或对已被 active-series record 移出 primary source 的旧 series 发起整组 erasure/retention 删除。设备revoke轮换的整组删除必须使用[`security-transactions.md` §3](./security-transactions.md)登记的transaction-bound operation；普通DELETE outcome不得作为`erase_confirmation_digest`来源。

实现 MAY 在 deployment policy 中收紧上述阈值；MUST NOT 放宽超过本节默认。

#### 7.8.1 高风险删除的 challenge 与 canonical delete-intent transcript

freshness MUST 由服务端发放，不得接受 caller 自造 nonce：

1. **challenge 签发**。`ak.self.keys.backups.command.issue_delete_challenge.v1`
   （`POST /_arkret/self/keys/backups/{backup_id}/delete-challenge`，request body 为闭合
   `{request_id}`）返回 durable、单次使用、TTL 不超过 300 秒的 challenge
   （[`keys-operations.schema.json#/$defs/keys_backups_delete_challenge`](../../artifacts/schemas/keys-operations.schema.json)），
   至少绑定 `{challenge_id, challenge, nonce, operation, principal_id, backup_id, audience,
   service_id, request_id, issued_at, expires_at}`。同一 `(principal_id, backup_id,
   request_id)` 在 challenge 尚有效时 MUST 返回同一 challenge；不同 `request_id` 签发新
   challenge。
2. **唯一 canonical delete-intent transcript**。所有 proof 分支（含 device quorum 中的每一份
   签名）MUST 覆盖同一 canonical bytes：

   ```text
   {
     "context": "ak.key_backup_delete_proof.v1",
     "operation": "ak.self.keys.backups.resource.delete.v1",
     "request_id": <DELETE body request_id>,
     "principal_id": <authenticated principal>,
     "backup_id": <path value, byte-identical>,
     "reason": <request value or JSON null>,
     "challenge_id": <server-issued id>,
     "challenge": <server-issued bytes>,
     "nonce": <server-issued nonce>,
     "audience": <server-issued audience>,
     "service_id": <server DID>,
     "issued_at": <server-issued timestamp>,
     "expires_at": <server-issued timestamp>
   }
   ```

   `payload_digest = "sha256:" + lowercase_hex(SHA-256(RFC8785_JCS(transcript)))`。`reason`
   缺省 MUST 固定编码为 JSON `null`，不得省略该键；proof 的 `created_at` MUST 落在
   challenge window（`issued_at`..`expires_at`）内。

   `context` 是本 consumer 在 [`proof-context-registry.json`](../../artifacts/registry/proof-context-registry.json)
   登记的唯一对象族 context `ak.key_backup_delete_proof.v1`，其 registry row 以
   `consumer_operation = "ak.self.keys.backups.resource.delete.v1"` 声明归属。
   [`high-risk-authority-proof.schema.json`](../../artifacts/schemas/high-risk-authority-proof.schema.json)
   是**一套 wire leaf、多 consumer context**：leaf 自身不拥有 context，schema 根的
   `x-arkret-proof-contexts` 逐字枚举全部已登记 consumer context。后续把该 family 复用到别的
   高风险 operation 时，MUST 先登记该 operation 自己的 context row（带自己的
   `consumer_operation`）并同步该注解，MUST NOT 复用本 context；用另一 consumer 的 context
   生成的签名即使密码学验签通过也 MUST 拒绝。
3. **验证与消费**。`DELETE` body 为闭合 `{request_id, challenge_id, proof, reason?}`。服务端
   MUST 先按当前 caller / path / audience / service 校验 challenge（重放、过期、path 不同、
   audience / service 不同一律 fail closed），再验证 proof 分支的授权（`principal_signing`
   的 controller 必须逐字节等于 `principal_id` 且该 key 在 `created_at` 是当前 principal
   control key；`device_quorum` 去重后有效签名数不小于当前 recovery policy 的 `k` 且请求
   `threshold` 等于该 `k`；`trusted_recovery_service` 的 session 必须未过期、未消费且由
   principal signing / recovery unlock / device quorum 建立），最后在成功删除的同一事务中
   原子消费 challenge。
4. **幂等**。服务端以 `(principal_id, backup_id, request_id)` 保存 canonical request digest 与
   terminal outcome：完全相同的网络重试返回已存 outcome，不重新验收已消费 challenge；同
   `request_id` 不同 digest 返回 duplicate conflict。"单次 challenge"与 registry 声明的
   DELETE retry-safe 由此并存。
5. **conformance**。`ak.vector.key_backup.delete_authority.v1` MUST 覆盖：三个 high-risk
   分支的正例、普通 device proof 删除 active tail 被拒、非尾部单独删除被拒、quorum 去重 /
   低于 policy `k` 被拒、session 过期或已消费被拒、challenge 重放 / 过期被拒，以及篡改
   `backup_id` / `reason` / `audience` / `nonce` / `context` 任一 transcript 字段后验签必然失败。

### 7.9 Algorithm Agility & Forward Compatibility

v1 的备份枚举数量有限，但 envelope 结构需要支持未来 PQ / hybrid 迁移：

- `recovery_policy.recovery_keys[].signature_algorithm` MUST 取自 active [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) row 的非空 `raw_signature_algorithm`；v1 机读集合为 `Ed25519`、`ML-DSA-65`。`Ed25519` 是默认 MUST，`ML-DSA-65` 仅在实现声明相应 PQ 签名能力时可签发。`ES256` 只有 JOSE mapping，没有 Arkret raw-signature mapping，因此不得出现在该字段。receiver 不支持 entry 声明的 active algorithm 时 MUST fail closed `unsupported_signature_alg`，不得回退为 Ed25519 或忽略该 recovery key。

- Receiver MUST 对未知 `encryption.kdf.name`、`encryption.aead.name`、`encryption.aead.aead_profile`、`encryption.recipient_method` fail closed（不得回退到默认）。
- PQ / hybrid KEM agility MUST 通过 `encryption.hpke_suite` 选择子 + [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 声明，不得塞进 AEAD profile。PQ hybrid（X25519+ML-KEM-768）已在该 registry 预留 `ak.hpke_xwing_aead_chacha20poly1305.v1`（status=reserved，profile `ak.profile.kem.hybrid_xwing.v1`），与 `ak.aead.hybrid_kem.*` 预留 namespace 对齐；只有该 registry row 的 activation requirements 全部满足并翻为 active 后才可出现在 wire 上。`ak.aead.*` 只描述 AEAD 算法、nonce/tag/key 长度和 AAD 构造；receiver 收到把 KEM 语义编码进 `encryption.aead.aead_profile` 的 envelope MUST fail closed。
- 当 `frontier_ref` 携带 `seal_ref` 时，client 可以用 Seal inclusion proof 来证明 envelope 创建时刻不晚于 Seal commit；receiver MAY 在 sovereign / high_security_organization profile 中要求该证明。
- 实现 MUST 在 envelope metadata 中保留 `additionalProperties` 与 `x_*` 前缀作为 forward-compat 扩展槽；MUST NOT 在 wire 上接受未知顶层字段（已由 schema `additionalProperties: false` 强制）。

### 7.10 自动持续备份

账户级非身份 secret、允许恢复的 MLS history 与 encrypted private account-data cache 新增或轮换时，客户端 SHOULD 自动上传相应 envelope并推进 active series。identity root/recovery secret 与 device private key始终禁止自动备份。PCR genesis/re-anchor 后必须立即生成由新 accepted device 签名、绑定 current device generation 的新 series tail。

### 7.11 加密 Realm 创建 / 加入前的 Recovery 前置门（normative）

E2EE Realm（effective `content_encryption_floor` 或 `metadata_encryption_floor` 为 `e2ee_required`，含 PCR 与任何加密协作 Realm）的创建或加入会产生该用户独有的 MLS group secret；若此时账号尚无可用恢复路径，丢失唯一设备即永久丢失这些内容。因此：

- 客户端在 `recovery_state` 未配置（`active_policy=null`）时，发起任何 post-bootstrap E2EE Realm 创建/加入前 MUST 完成 recovery-material gate；PCR bootstrap 是唯一豁免。
- `ak.profile.personal_node.v1` MAY 允许用户在明确告知"丢失本设备将永久丢失该 Realm 内容"后**显式跳过**，并维持 / 标记 `single_point_of_failure=true`、持续提醒；`small_team` 及以上 deployment profile SHOULD 阻断创建 / 加入，直至 recovery policy 配置完成。
- `ak.profile.agent_provisioning.v1` 对 Agent 收紧上一条例外：即使部署同时声明 `ak.profile.personal_node.v1`，controller 没有 accepted **account recovery policy** 时 `ak.self.agent.command.provision.v1` MUST 在产生 Agent DID / PCR / grant 副作用前 fail closed。该门只确认 controller 账户恢复材料已配置，不要求 Agent PCR active MLS snapshot 或 `mls_history` ready 状态；runtime pairing 按 current controller/Agent authority 与 proof-of-possession 判定。不得以服务端托管 MLS secret 或为 Agent 生成另一套助记词绕过。
- **加入路径的判定输入（normative）**：invitee 在加入前读不到 membership 门控的 Realm policy 投影，因此加入侧 gate 判定 MUST 只以 `ak.schema.realm_join_candidate.v1` 的 effective `encryption_profile` 为输入（见 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) §9.1.1 第 9 条）：`mls_rfc9420` 时 gate MUST 生效。该输入相对本节按 floor 给出的范围是 fail-closed 的超集——MLS-backed Realm 的 effective `metadata_encryption_floor` 缺省即 `e2ee_required`；而 `encryption_profile` 为 `none` / `external` 的 Realm 即使 floor 为 `e2ee_required`，Realm join 本身也不产生 Realm MLS group secret，其加密材料在加入后的 Circle 路径上由已可读状态按同一 gate 判定。客户端 MUST NOT 为该判定读取 membership 门控的 Realm Event 历史。
- 该前置门是客户端编排义务，不替代服务端的 floor ratchet 与 PCR 校验；它针对的是"加密材料先于恢复路径产生"的时间窗，而非加密本身是否启用。

## 8. Recovery Policy

Recovery policy 是 PCR control state。Genesis policy 只能由 founding accepted device 签发；后续 policy 更新由 current generation accepted device 或满足旧 policy 的 quorum 签发，并必须受 version ratchet、accepted Seal 与 generation fence 约束。DID Document 中任意 verification method、账号登录或服务端 transport identity都不能单独授权 policy 更新。

### 8.1 Policy 生命周期

Recovery policy 的所有发布、轮换和撤销均进入 PCR control stream。签名设备必须满足 `device_generation_status="active"`、`authorized_generation_ref == current_device_generation_ref` 与未撤销状态；quorum 更新还必须满足旧 policy 的门限和 ratchet：

Policy 签名输入固定为 `UTF8("ak.identity.recovery_policy.signature.v1\n") || RFC8785_JCS(policy 的全部实际存在顶层成员，排除 auth_data)`。schema 允许的 optional 成员出现时自动进入投影，缺席时省略；只有 schema 明确允许 `null` 的位置才能保留 `null`。wire 上不携字段名清单，receiver 不得按调用方自报清单缩小投影。

- **publish**：首次发布或后续无中断更新。新 envelope 的 `version` MUST 严格大于当前 accepted policy 的 `version`，`supersedes` MUST 引用前一份 `policy_id`（首版为 `null`）。
- **rotate**：用于 `reshare_policy` 触发的 proactive secret sharing 或更换 holder 集合；出现的 `threshold`、`device_quorum` 与 share commitment 自动进入上述完整 policy 投影。轮换期内的 in-flight recovery session（参见 `crypto-media/device-lifecycle.md` §14）MUST 使用其 `issued_at` 时点的 policy；服务端 / coordinator MUST 拒绝跨 policy 版本拼接 share。
- **revoke share**：当某个 share holder 被怀疑泄露时，policy holder 可发布只更新 `threshold.shares[i].revoked_at` 与 `revocation_reason_code` 的 rotate envelope。recovery coordinator MUST 拒绝任何 `revoked_at != null` 的 share，即便 commitment 仍能通过。`reshare_policy.max_share_age_seconds` 到期后未 reshare 的 share 在 coordinator 侧 MUST 被视为 stale，UI MUST 提醒用户。
- **revoke policy**：用 `expires_at = now`、`allowed_proof_kinds = []`、或专门的 `policy_id` revoke 进入 principal control stream；revoke 之后只有写入新 policy 才能恢复账号——这是高代价动作，必须配 §7.7 UI 警告。

任何允许的恢复方式（did_root / device_quorum / trusted_recovery_service / threshold_recovery / recovery_unlock）的 create request、session state 与 proof transcript MUST 绑定 exact closed `account_id: AccountId {principal_id, station_id}`，以及 `(policy_id, version, recovery_session_id)`；create wire 不接受旧顶层 `principal_id`。接收方 MUST 要求 `account_id.station_id` 等于自身 authenticated service DID，并以完整 pair 选择唯一 lifetime PCR lineage，unknown/wrong-service/mismatch fail closed。不绑定的 proof MUST `recovery_evidence_unbound`。Device recovery 场景还 MUST 使用 `crypto-media/device-lifecycle.md` §14 定义的 canonical transcript，其字段集同时绑定 create `request_id`、认证该 create 的 `recovery_session` SessionGrant id、该 grant 的 `cnf.jkt`、`requesting_device_id`、`trust_domain`、`identity_model="pcr_policy"`、`model_generation_ref`、session `challenge`、session `created_at` 与 `expires_at`；`model_generation_ref` 必须等于 PCR current device generation，且不得由 DID `versionId` 推导。get、proof submit、backup unlock 与 RecoveryTransaction MUST 出示同一 grant/JKT；transport grant、session state 或 proof transcript 任一 binding 不同都必须 `recovery_evidence_unbound`。`did_root` 仅在冻结 policy 显式启用时成立。

### 8.2 Holder 取回与防滥用

share holder（无论是个人 DID、托管服务 DID，还是 hardware module）在向恢复请求方释放 share 时 MUST：

- 验证 `recovery_session_id` 来源——session id MUST 来自当前 accepted recovery policy 中的 announcement event 或 trusted_recovery_service 签发的 challenge；不得接受任何 client 直接构造的 session id。
- 在签发 share release 之前 MUST 验证 holder 自己未被 §8.1 revoke，且当前时间在该 share 的 `not_before` / `expires_at` 范围内。
- share release 的请求方绑定按 `proof_kind` 分流：
  - `device_quorum`：请求方设备的 device key MUST 已绑定到目标 principal control stream 中某个尚未 revoke 的 device record；不满足则拒绝 release。
  - `threshold_recovery` / `recovery_unlock`：请求方设备 MAY 是尚未授权的新设备。holder MUST 验证 `recovery_session_id`、当前 policy/version、identity model/model generation、requesting device key proof-of-possession、session challenge、`requesting_device_id` 与 share request transcript 一致，并按 policy 要求完成 holder 侧 OOB / announcement / approval 检查；MUST NOT 要求该新设备预先存在于 control stream。若没有 accepted device，恢复完成出口必须按 `crypto-media/device-lifecycle.md` §14 提交 root-signed re-anchor + replacement-device-signed authorize 原子 unit。
  - 其它 future `proof_kind` 未在 policy 中 active 登记前 MUST fail closed；不得把 `threshold_recovery` 当作 `device_quorum` 的弱化别名。
- share release transcript MUST 绑定 `(share_id, holder, recovery_session_id, requesting_device_id, audience, issued_at)`，并由 holder 签名；coordinator 在 reconstruction 之前 MUST 重放该 transcript 比对，并 MUST NOT 把同一 transcript 用于两次 reconstruction。
- holder MAY 引入额外 OOB confirmation（电话回拨、共享密语）；该层不在 protocol normative 之内，但被纳入 holder 自身的安全 surface。

## 9. 泄露响应

当怀疑密钥泄露时，客户端 SHOULD：

1. 立即发布 device revocation 或 key rotation。
2. 停止接受已撤销设备/session 的新写入。
3. 对 E2EE Realm 触发 MLS Remove / Update。
4. 标记泄露窗口内的高风险 Operation。
5. 提醒用户检查未知设备、session 和 agent grant。

单代 identity root 瞬态泄露但 recovery secret 安全时，必须用已预承诺下一 root 推进 DID，并处理可能的同高度 sibling；不得把 pre-rotation 宣称为无 witness 的唯一性保证。
recovery secret 疑似泄露时 MUST 按 §3.3 分流：有独立权威才允许两-entry handoff；没有独立权威则原 DID 不可逆 compromised，必须重铸并重新建立外部信任。

### 9.1 备份子系统泄露的组合恢复流程（normative）

设备/身份泄露的步骤(上)与备份子系统的轮换/删除/PCS 之前是分散定义的。当怀疑**备份接收密钥（recovery key / `mls_group_secrets_backup_key`）或某个 backup envelope 的解锁材料泄露**时，实现 MUST 把以下三件事作为**一个组合流程**执行，而不是各自孤立：

1. **轮换 backup series**：按 §7.6 为受影响 `backup_kind` 开启**新 `series_id`**（不是在旧 series 上追加），用轮换后的接收密钥重新加密当前需要保留的内容并上传新 series。新设备发现 canonical series 的方式见下方“active series 指针”。
2. **推进受影响 MLS 群组 epoch（PCS）**：轮换备份密钥本身**不**提供 post-compromise security——它只更换“备份包装”。要使后续消息密钥与被泄状态解耦，MUST 对受影响 Realm 触发 MLS Remove / Update 推进 epoch（与 §9 step 3 同一动作），并按 `crypto-media/encryption-and-audit.md` 绑定 governance frontier。
3. **删除旧 series**：在新 series 确认可恢复**之后**，按 `crypto-media/device-lifecycle.md` §12.2 retention 流程删除旧 `series` 的服务端密文。删除 MUST 在确认新备份可用之后进行，且 MUST 整组迁移而非删除链中间节点。若触发源是设备revoke，`secret_storage`与`mls_history`必须由同一`SecurityRotationTransaction`预留并通过`ak.self.keys.backup_series.command.erase.v1`返回逐series durable progress；只有complete typed confirmation的canonical digest可推进事务。

**不可挽回边界（MUST 在 UI 明示）**：上述流程只缩小**后续**暴露面；攻击者在泄露窗口内**已经下载**的旧密文用旧密钥永远可解，轮换/删除无法撤销。

**Active series 指针**：当一个 `(actor_id, backup_kind)` 存在多个 `series_id`（轮换后新旧并存的过渡期）时，恢复方 MUST 通过 §7.6 的 signed active-series record 确定当前 canonical series。`frontier_ref` 是 envelope / record 的 control-stream 锚，不是 series 选择器；服务端返回顺序、最大 `series_seq`、最新 `created_at` 或单个 envelope 的 `frontier_ref` 都不能单独决定 active series。旧 series 仅在 retention 删除前用于读取既有内容，MUST NOT 作为 primary recovery source。

## 10. 实现要求

实现 MUST：

- 使用系统安全存储保存私钥
- 对可导出密钥做用户确认
- 对恢复操作做高风险 UI，且 §7.7 的 UI 字段展示要求 MUST 被遵守
- 对设备列表显示最近活动和授权来源
- 对吊销操作做不可抵赖记录
- 在发布 entry 0 前执行 custody-confirmation gate，并在 PCR bootstrap 后按 §5.0.4 的范围阻塞 E2EE Realm 创建/加入直至 recovery-material gate 完成

实现 SHOULD：

- 支持硬件安全模块或平台 keystore
- 支持 biometric unlock 但不把 biometric 当作 cryptographic secret
- 支持 passkey / WebAuthn 作为本地解锁与网关认证材料
- 支持企业设备管理和远程吊销

## 11. 一致性要求

Arkret v1 对设备、会话和恢复要求如下：

- Device record JSON Schema 由 `../models/common-fields.md`（`id:device` 类型与 typed-id 规则）与 `../crypto-media/device-lifecycle.md` 共同固定。设备记录 MUST 绑定 principal `did_core_id`、device id、verification method、算法、创建时间、撤销状态和签名链；verification method 的 base `did` 必须经 adapter 投影回该 `did_core_id`。
- `ak.device.authorize` 与 `ak.device.revoke` MUST 进入 schema registry，并按 event auth 规则验证。`ak.device.revoke` 的控制面位置由其 Control Move 信封 `seal_basis`（授权基准，签名覆盖）、首次原子持久化的 Ack + `ak.schema.device_revocation_state.v1` pending record，以及覆盖它的 accepted Seal（永久生效切点）表达，payload 不携带 frontier / generation 字段；pending 起设备不得取得新的 session grant、KeyPackage claim、to-device / Event write 或 Station admission proof，只有 exact signed reject 可恢复，Seal 后永久撤销。
- Session grant MUST 绑定 principal `did_core_id`、device id、service `did_core_id` / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖：加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定、服务端不可解密要求、`series_seq` 严格单调、`supersedes` / `supersedes_digest` 链完整、`mixed_secret_storage=true` 在 non-personal_node profile 下被拒绝、`mls_history` 域使用 `passphrase_kdf` 的 envelope 被拒绝、§7.8 服务端限速与跨 actor 拒绝。
- MLS KeyPackage binding MUST 覆盖 principal `did_core_id`、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝无法由当前 `did` / resolution evidence 验证到该 `did_core_id` 与 device trust chain 的 KeyPackage。
- Recovery policy grammar 由 `ak.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）规范化；publish / rotate / share-revoke 的 wire 形态由 §8.1 描述。grammar MUST 表达 threshold、share holder、not_before、expires_at、allowed_proof_kinds、approval requirement 与 audit event；threshold 的总 share 数唯一由 `shares.length` 派生，wire 不携带 `n` 镜像。恢复只改变控制链，不自动授予内容读取或业务 capability。
- Recovery policy publication 的 `ak.vector.identity.recovery_policy_publication.v1` MUST 由至少两个独立 runner 覆盖 canonical `EventInitialSubmission`、PCR allowlist/reducer/Seal admission、threshold recovery signing/HPKE key 闭包、issuer projection、跨字段不一致、未 Seal retry 与特殊写路径绕过拒绝。
- Recovery receipt 由 `ak.schema.recovery_receipt.v1`（`artifacts/schemas/recovery-receipt.schema.json`）规范化；签名输入固定为 `UTF8("ak.identity.recovery_receipt.signature.v1\n") || RFC8785_JCS(receipt 的全部实际存在顶层成员，排除 auth_data)`，不携字段名清单。`crypto-media/device-lifecycle.md` §14 finalize 写入的 receipt MUST 通过该 schema 校验，并绑定 `recovery_session_id` / `policy_id` / `policy_version` / `new_device_id` / `identity_model` / `previous_model_generation_ref` / `result_model_generation_ref` / authorization path refs / `proof_summary` / `unlocked_backups` / `welcome_count` / `outcome`。
- Backup series MUST 满足 §7.6：客户端 `LIST` 后重建链 → 验证 `supersedes_digest` → 用尾部 envelope 解密；当 `frontier_ref` 存在时 MUST 用 control stream snapshot 验证 `frontier_digest` 与 `device_generation_ref`。
