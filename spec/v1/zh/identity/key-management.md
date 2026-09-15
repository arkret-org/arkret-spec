---
title: Key Management
status: candidate
normative: true
stability: v1
updated: 2026-09-12
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

身份层定义“谁是主体”，加密层定义“如何保护内容”，但真正能让系统安全运行的是密钥管理。

本文定义 Arkret 的密钥生命周期：

- identity root key
- principal 高权限签署规则（v1 不新增独立 key）
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
- root 的 Event 签名权限是封闭白名单：仅允许签自体 principal 的 PCR genesis `ak.realm.create`；包括 `ak.device.reanchor` 在内的其它 Event，即使携带 DID entry ref 也不得启用 root-anchor 验签路径；
- root 还可签合规 DID log controller proof，或在 accepted PCR recovery policy 显式启用 `did_root` factor 时签该 factor 的 recovery-session transcript。后者只满足 policy 条件，不成为 Event signer；恢复 unit 的两条 Event 均由 session 冻结的 replacement device identity key 签署（`crypto-media/device-lifecycle.md` §14）；
- 每个后继 root 公钥 MUST 不同于全部已激活 root；一代 root 被后继 entry 取代后即 spent，MUST NOT 再出现在任何后继 `updateKeys` 或 `nextKeyHashes` 中。

### 3.2 Principal High-Privilege Signing

Arkret v1 不定义独立的账户级设备签名层级。高权限 PCR Event 由当前 generation 的 accepted device 签署；全设备丢失时只允许 §14 的 replacement-device-signed recovery unit 特例。recovery policy 的 quorum/signer 验证 session factor，不能代签该 unit。identity root 仅承担 §3.1 的封闭用途。任何实现都不得从 DID Document 的普通 verification method 推导设备授权。

`principal_signing` 不是 v1 的密钥类型、proof kind 或兼容别名。需要当前设备持有证明的普通操作使用明确的 current-device 分支；需要恢复权威的操作使用 `did_root`、`recovery_unlock`、`device_quorum` 或 `trusted_recovery_service` 中实际被 recovery policy 接受的分支。实现不得把其中任一分支重命名为“principal signing”，也不得让一把日常 device key 因名称含混而取得恢复或高风险销毁权限。

### 3.3 Recovery Secret 与域分隔子键

recovery secret 是派生源，不是可跨用途复用的一把 recovery private key。Arkret v1 的派生合同隔离代际 DID update root、稳定 recovery-session proof key 与稳定 backup HPKE key。客户端 MAY 在首次配置时由同一 secret 派生这些角色，但 accepted PCR recovery policy MAY 独立登记由另一 secret 派生的 recovery-session proof key；后者不得被要求等于或控制注册 DID 的 root。客户端恢复 UI MAY 把 secret 呈现为 24 词 BIP-39 助记词，但 MUST NOT 上传助记词、BIP-39 seed、PRK 或任何派生 private key；本地 MAY 仅保留不可逆指纹用于输入校验。恢复 policy key 不授予 DID update authority；备份解锁仍须满足该备份自身的 key binding。

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

普通 root 轮换只推进 `root/<i>`。root index 是该 DID canonical history 的**全局**单调计数，不因 recovery secret handoff 归零。recovery secret 疑似泄露时：若没有预先存在且能拒绝“旧 secret 单签”的独立 guardian/witness/组织策略，原 DID MUST 视为不可逆 compromised，停止建立新信任并用新 secret 重铸 DID；旧 DID deactivation 只能 best-effort，不能作为安全迁移前提。若存在独立策略，MUST 走可续跑的两-entry handoff：设当前 entry 激活 `root_i` 且已承诺旧 secret 的 `root_{i+1}`；先确认新 secret 保管；entry i+1 在独立策略批准下激活旧 `root_{i+1}`，并承诺由新 secret 以**全局索引 i+2**派生的 `root'_{i+2}`；entry i+2 激活 `root'_{i+2}`、承诺 `root'_{i+3}`；随后独立按 accepted PCR policy 执行 §5.0.3 recovery unit（不得把 entry i+2 当作恢复授权）、发布新 recovery-proof policy、为所有引用旧 backup-HPKE recipient 的 active envelope 建新 series 并推进 signed active-series pointer，验证后再撤销旧 policy key。不得把新 secret 的局部 `root'_0` 填入既有 DID history；恢复者从 canonical entry 数重建同一全局 index。每一步 MUST 有 durable checkpoint 并支持幂等续跑。

### 3.4 Device Key

每台设备 SHOULD 本地生成独立 device key。

device key 用于：

- 日常 Operation 签名
- Events API / sync 认证
- device-to-device pairing
- MLS KeyPackage 身份绑定

device key MUST 通过 device authorization event 或 capability grant 绑定到 principal DID。

普通 human endpoint 不另建 principal signing key 或 ordinary MLS leaf signer。相同 device Ed25519 key material MAY 用于上述签名职责，但每个 operation 必须使用其登记的不可互换 context/transcript，并独立校验完整 AccountId、device generation、capability、audience、scope、freshness 与撤销状态。设备的 HPKE/X25519 密封 key 是不同算法与权能，MUST NOT 与该签名 key 转换或复用。

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

v1 不定义独立的 agent key rotate 事件。Controller-signed `ak.agent.key.authorize.payload.supersedes[]` MUST 精确列出 `seal_basis` 与首次接受前完整 active authorization 集合的 `{key_id, authorized_event_ref}`，最多 256 项，按该二元组 UTF-8 字节序排序。active 集合为空时 MUST 省略，包括先 revoke 后重新 attach；同 key re-authorization 也必须列出旧 dot。Event 原子移除所有旧 key cell 的 observed authorization dots 并 add 新 authorize dot。stale、遗漏或多余条目 MUST conflict / fail closed，不得按 key_id 或本地 map overwrite 替换。Event 的 `seal_basis` 与激活 fence 同时钉住批准快照，不能把集合相等误当成可检测空→非空→空 ABA。服务端不得伪造 controller-authored revoke Event。

**同 key re-authorization（normative）**：controller MAY 为同一 `(agent_id,key_id)` 签发新的 `ak.agent.key.authorize`。该 Cell 是 `sequenced_state` 安全集合；首次授权写入一个 authorize dot，续期命令按已签 basis 枚举全部活跃 authorize dots，在同一确认事务移除它们并加入一个 replacement dot。执行位置必须校验确切相关 revision；两个基于同一旧 revision 的替换最多一个成功，另一个拒绝后重新取得状态并签署，不合并成并发权限 heads。不得按 HLC、到达时间或最小 digest 选授权。该路径不换 key material、不需要 pairing 仪式，但必须由 controller 或其授权设备签署，runtime 不能用旧 key 自行续期。renew-pairing（§3.6.1）用于 key 丢失、疑似泄露或更换 runtime。

高风险 agent key（能写入、调用外部工具、管理 capability、读取审计材料或代表用户发起 service-call）的 grant MUST 同时有 resource selector、accountable actor、approval/proposal evidence 和 revocation freshness check；`expires_at` 是可选的附加约束，授权失效控制以撤销链与 lifecycle 级联为权威。只声明 API token 或本地环境变量而没有上述事件链的 agent key 不得用于 v1 standard operation。

#### 3.6.1 Agent runtime pairing 与 session(normative)

`ak.profile.agent_provisioning.v1` 定义了一条面向普通用户的 Agent 流程，以现有 agent key 原语为基础:

PCR create admission 必须从 durable provisioning 状态读取 prepare 锁定的 exact `initial_resolution`，再与 genesis 携带值逐字段比较；只校验请求自带值格式正确或 `project(did)==agent_id` 不足以建立 create-locked 绑定。普通 Event policy admission 与 delegated Agent envelope admission 两条路径都必须使用同一份保存值。

- **Provisioning** (`POST /_arkret/self/agents`, operation `ak.self.agent.command.provision.v1`) 是闭合的 prepare/commit operation，其外围由 controller 先发布 PCR-independent DID entry 0、后发布 PCR binding entry 1。controller MUST 先按 §3.6.3 可恢复地持久化 WebVH 更新密钥，并发布不含 PCR binding 的 Agent inception。`phase=prepare` 只校验 controller recovery、caller-supplied `did` 的 accepted entry 0 与 controller delegation等先决条件，并返回 exact `initial_resolution`、controller PCR 与 delegation ref；它 MUST NOT 生成 Agent DID 或私钥，也 MUST NOT 分配 `principal_control_realm_id`（该值只能由 controller 从本地冻结的 genesis create 派生），也 MUST NOT 发布 durable Agent/PCR、accountability、selector、pairing、grant 或其它可观察副作用。controller 必须逐字核对 `initial_resolution`，并以 `(agent_id, controller_principal_id, requested_scope)` 重算返回的域分离 `requested_scope_digest`，不匹配时停止。随后 controller MUST 调用 `arkret-rust-sdk` 的统一 authoring API 生成恰好一个 controller-owned `ak.agent.provision` `EventInitialSubmission`；其闭合 payload 同时绑定 allocation、controller delegation、`accountability_scope=agent_operator`、selector、`requested_scope_digest` 与前向声明的 `principal_control_realm_id`（§3.6.3），不含内层 proof。Event `actor_id` MUST 是 authenticated controller、`realm_id` MUST 是返回的 controller PCR；Event proof 是唯一签名。`phase=commit` 原样携带服务端 allocation、完整 private `requested_scope` 与该 submission；Station 必须通过普通 Event schema/proof/authz/frontier/reducer admission 接受它，不得用 service key 代签、接受 `dev-proof`，或绕过 admission 直接写 canonical store。一次 accepted reducer transaction MUST 原子写入 provision、accountability、selector 与 realm-id claim 四个 cell；不得暴露部分完成状态。该 Event durable accepted 只把 outcome 推进到 `status=awaiting_pcr_genesis`；genesis accepted 后推进到 `status=awaiting_did_binding`；只有 controller 使用 inception 预承诺 key 发布的连续 entry 1 也 accepted、且其唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 精确匹配 create-locked 四元组，才创建 pairing handle 并返回 `status=complete`。完整 `requested_scope` 始终保持 controller-private，不得进入公开 DID history 或 durable Event。精确 commit 重试以 allocation 与 submission 的 Event id/canonical bytes/publication evidence bytes 为身份，MUST 返回该身份**当前**的 durable outcome（依次为 `awaiting_pcr_genesis`、`awaiting_did_binding` 或同一 complete outcome）；同 Event id 不同 bytes 或不同 evidence MUST conflict。恢复 MUST 重放同一 submission 与已持久化的 exact DID operation，并依靠各自 admission 幂等完成，MUST NOT 另造 Event id、proof、lease、receipt 或重复 fact。
  `requested_scope` 是该 Agent key/session 的**全局硬上限而不是授权**：`actions[]` 中的内容 action 只表示以后在某 Realm 中可被单独 grant 的最大 action 集；省略的内容 action 不能由 Realm / Circle / Strand grant、session 或 participation gate 补回。operation/service resource 约束服务面；显式内容 resource selector 只进一步收窄以后允许附加的 Realm 内容资源。Provisioning MUST NOT 从 `requested_scope` 物化 `ak.capability.grant`；后续 grant 必须满足 `grant.actions ⊆ requested_scope.actions` 并继续按 AND 收窄。Participation selection 是独立的动作时 deny gate，不属于 provision commitment。complete 返回 Agent PCR binding、`requested_scope_digest` 与一次性 `pairing_request_id` + `pairing_code`；`pairing_code` MUST 由 CSPRNG 生成且熵不少于 128 bit。controller E2EE client 在提交 §3.6.3 的 genesis 时按 §4.1 本地生成 Agent PCR MLS state 并提交 Agent profile Event，但不得把该 active state 上传为 backup。Fresh endpoint 随后只能通过标准 KeyPackage/Add/Welcome 进入 group；`mls_history` 仅可恢复合法 history-secret ranges（§7.5.6）。服务端、Account Authority 与 Station MUST NOT 生成或短暂持有 Agent PCR MLS private state。流程不写入独立 `ak.self.agent.command.provision.v1` Event，也不得在首次 runtime pairing 前伪造或预写 `ak.agent.key.authorize`。
- `requested_scope` 在 v1 provision request 中 MUST 存在，且 Agent principal 创建后 immutable；实现不得把省略解释为 unconstrained 或 deny-all，也不得通过 renew-pairing、同 key re-authorization、Realm 加入或 policy 更新修改它。需要改变（包括扩大）该全局 ceiling 时必须 provision 新 Agent principal。后续 `ak.agent.key.authorize.payload.agent_key_scope` MAY 比它更窄，但 MUST 满足 actions/resources/constraints 的 selector-narrowing 子集规则；不得要求两者完全相等。Receiver 不得信任 service-local row 声称的 ceiling：必须按 authorizing object 的 accepted-at 解析 Agent DID history，验证 §4.1 的公开 digest commitment，并取得有效的 `ak.schema.agent_requested_scope_disclosure.v1` 私有披露，重算 digest 后再求子集。具体 digest、资源覆盖和 mandatory constraint 规则以 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 为准。
- **Runtime key pairing** (`POST /_arkret/gate/account/agent-key-pair`, operation `ak.gate.account.command.pair_agent_key.v1`):runtime 先经 open submit 登记一份已验 PoP 的 frozen candidate。controller 只提交 `{pairing_request_id, approval_request_id, requested_scope_disclosure, authorize_event}`；raw key、method、scope、audience、expiry 与 exact supersedes 由唯一 controller-signed authorize Event 绑定。Station 从持久 candidate 取 PoP/attestation 原材料并验证 current handle、controller/Agent parent authority、DID binding、private scope ceiling 与 Event proof。首次接纳耐久保存 exact 命令和激活 fence，返回 `awaiting_accepted_frontier`；覆盖该 Event 的 successor Seal accepted 后，后台 reconciler MUST 自动推进，无需第二次 pair command。Seal 必须仍由实际授权 controller/notary 签名，不能由 Station 代签。首次激活事务重新检查 handle/candidate identity、expiry、fence、exact旧授权集合和当前 parent authority，再消费 handle并记录 active outcome；renew、expiry、cancel、deactivate 或授权基准变化使待激活命令 cancelled，迟到 Seal 不得复活它。paused Agent 可保留有效 key但不得签发session；active outcome也不替代 runtime 的fresh agent_key_proof。精确重试只读取/恢复同一 durable command，同 Event id 不同 bytes 必须 conflict。

  Account Authority 与该 Station 处于同一部署内已登记的认证关系，但其签发职责与 Station 的业务准入职责不合并。内部职责按**唯一 owner** 划分：事实 owner MUST 对冻结输入做完整验证；内部消费者通过认证且完整性受保护的 exact 结果承接同一事实，MUST NOT 为同一材料另取原材料重复验签，也 MUST NOT 从客户端或任意服务的 `verified=true` 布尔值推断该事实成立。消费者仍 MUST 检查本次 account、audience、operation、intent、状态版本、有效期与自身业务权限；状态变化后的 current gate 不是重复验签，继续执行。该划分不能检测整个 Station 的合谋谎报，本节不声称覆盖该情形。

  当 Account Authority 与保存 Agent pairing/PCR 的 Station 分离时，**Station 是 pairing 原材料与业务准入的唯一 owner**：它 MUST 保存并完整验证 candidate PoP、current handle/expiry、controller/Agent parent authority、DID binding、private scope ceiling、requested scope disclosure、exact supersedes 与 controller-signed Event proof，并在 activation fence 与 accepted Seal 下执行激活事务；MUST NOT 从客户端或任意服务的 `verified=true` 推断 PoP 已验。Authority 以完全相同的最小 `AgentKeyPairRequestBody`、部署内认证和 `Idempotency-Key=authorize_event.event.event_id` 委托到 Station 同一 canonical pair operation；禁止私有端点或自定义队列信封。Authority 对该已认证结果 MUST 核对 request / Event / Agent / controller / 授权对象的绑定，MUST NOT 为同一冻结材料另行取得 verifier-only 原材料并独立重建 stable binding、PoP transcript 或重复验签。Authority 以该 exact Event ref 对齐 durable outcome；Seal 自动推进后通过既有读取/幂等恢复观察 active，只有确认 durable activation 才建立本地授权投影。激活时由 **Station** 从同一冻结 authorization/lifecycle/notary/account-authority closure 使用 SDK `build_agent_signer_evidence` 构建**恰好一份** `CurrentSignerEvidence::Agent`，并用唯一 `signer_evidence_ref` helper 计算 content ref；Authority 只消费该 exact outcome，MUST NOT 另起一轮构建后比较，也 MUST NOT 以新时间戳或新签名替换已冻结结果。消费前 Authority 仍 MUST 核对 response 的 ref 与对象关联、身份、时态与授权 intent。Runtime 与外部 Station 对 portable closure 的既有完整验证不变。

  **状态真源与耐久协调（normative）**：Agent pairing 的业务 command 与 activation 真源只有 Station 一份；Account Authority 侧保留 issuer ledger 与必要的协调/派生读取，协议 MUST NOT 要求第二份独立的业务激活裁决。Authority 若保留本地授权投影，该投影 MUST 能从同一 durable outcome 恢复并受 current gate 约束，MUST NOT 被当作 Station 已激活的替代证据。v1 不采用 at-most-once 网络投递：Authority 若在 Station 接纳前就向调用方承诺命令耐久，MUST 保存 exact pending intent 并可重试；若改为纯同步中继，客户端成功边界 MUST 在 Station durable accept 之后，未成功的 exact request 由原请求 owner 保管并重试。已接纳的 `awaiting_accepted_frontier` MUST 由 Station 后台 reconciler 继续推进，MUST NOT 再依赖第二次用户批准。

  Runtime 通过既有 `ak.open.agent_pairing.read.runtime_key_request_status.v1` 的 active outcome 一次取得 `current_signer_evidence` 与 `signer_resolution_evidence_ref`，不得新增 evidence endpoint。它必须验证完整递归闭包、重算 ref、逐字匹配自己的 method/raw-key，然后原子持久化完整 evidence 与 ref；以后普通 Event 直接引用本地 ref，并可向 receiver 提供本地持有的 evidence closure，不联系 controller、Account Authority 或 origin Station。`authorized_event_ref` 只标识授权 provenance，绝不能冒充 signer evidence ref。`ak.self.agent.resource.get.v1` 的 `key_state` 在存在 active authorization 时携带同一 pair，供已授权 controller/Authority 审计和恢复；两字段必须同现。
- **Lifecycle、readiness 与 presence 正交（normative）**：通用 Agent view 只暴露三轴，`key_state` 不重复状态。poll 的 operation-local `runtime_state` 仅从 current active authorization set 与所查 handle 派生：无key/open handle→pending_runtime_key；无key/已过期handle→pairing_expired；有key/open handle→replacing；有key/无open handle→ready。不得持久化该诊断或使用历史 `authorized_event_ref` 推断当前授权。无key映射runtime_key_missing，open handle映射pairing_open；paused与key ready并存时不得虚报session_missing。
- **Pairing 失败清理**：任意 handle 过期只关闭open fields、取消该handle未激活命令并更新readiness，不改变lifecycle、key或grant。无current key时维持runtime_key_missing，有key时原授权继续受其current gates约束。unknown、过期和被renew替代的handle在匿名接口统一防枚举；合法runtime的终态结果只在secret绑定的有限结果保留窗口内可读取。
- **Pairing 续期** (`ak.self.agent.command.renew_pairing.v1`):controller 可对任何 active/paused Agent 重开同一 attach/replace 流程；deactivated拒绝。每个Agent最多一个open handle。服务 MUST 返回新的 `pairing_request_id`、必填 `pairing_code` 与 expiry；secret由CSPRNG产生至少128 bit，不得用短十进制显示码替代。所有旧handle与未激活批准永久失效。续期不修改principal、slug、lifecycle、key、grant或历史，不得检查sibling slug可用性。当前active授权集为空即attach，否则由同一Event exact supersede；不存在独立持久或wire分支判别字段。
  新 runtime MUST 生成未用于该 Agent 的新raw Ed25519 signing key。服务须保留历史raw-key指纹并拒绝pairing重用，不论旧授权已撤销、当前集合为空、换key_id/handle/Event或endpoint。same-key续权仅走保有durable Signal序号allocator的独立re-authorization路径；丢allocator不得重置序号，必须换新raw key。服务不得在该路径要求 `mls_history` active-state快照。怀疑失陷时controller SHOULD先pause；完成替换保留原lifecycle意图和principal-bound grants。
- **Agent runtime authentication**:复用 `POST /_arkret/gate/account/session-grants`(operation `ak.gate.account.command.issue_session_grant.v1`),通过 `proof.proof_kind="agent_key_proof"` 分支区分。Auth Server MUST 维护独立 schema branch、独立 proof validator;不得让 `agent_key_proof` 走 password / OIDC / passkey 的 validator fallback。请求侧 `agent_scope_request` 是 `ak.profile.agent_auth.v1` overlay,签发后的 scope MUST 物化为 capabilities.md 已注册的 `allowed_tracks` / `allowed_strand_ids` / `allowed_data_labels` / `allowed_endpoints` 等 typed constraints。Auth Server 求交前 MUST 取得已验证、与自身 verifier/audience 及当前 accepted-at DID digest 匹配的私有 `requested_scope_disclosure`；它 MAY 使用 pairing 时建立或经 authenticated confidential S2S 转移的 verifier-private evidence，请求也 MAY 在该 agent 分支携带新 disclosure。仅有 service-local Agent row、公开 digest 或由 agent runtime 自报的完整 scope 时 MUST fail closed。
- **Agent runtime capability 选择与最小服务面（normative）**：唯一机读规则见 `../../artifacts/registry/agent-runtime-scope-registry.json`。实现 MUST 仅从 accepted immutable provision `requested_scope.actions[]` 按 exact operation token 选择 capability：某 capability 的任一 `activation_operations` 出现即按 registry 的 `selection_rule=any_activation_operation_present_in_immutable_provision_actions` 选择它。不得使用 prefix/subsumption、内容 action、endpoint path、runtime attestation、Realm/grant/participation、产品 preset，或 key/session scope 重新选择或取消 capability；lower layer 出现 provision 未含的 activation operation 仍按既有 subset 规则拒绝，不能升级 immutable intent。`interactive_chat.activation_operations` 是 subscribe、scan、Event frontier、Seal frontier、submit 五项完整 atomic floor；任一项出现，provision、accepted key authorization 与 requested/current session 三层都 MUST 覆盖全部 `interactive_chat.mandatory_operations`。`e2ee.activation_operations` 是 Agent KeyPackage upload/consume/revoke；任一项出现，三层都 MUST 覆盖 `e2ee.mandatory_operations` 的 KeyPackage upload。Server 只诊断并拒绝缺项，MUST NOT 自动补 operation；controller authoring 可在签署 provision 前用同一 registry 规则展开 floor。Event frontier 只提供 actor causal frontier，Seal frontier 提供安全 head discovery；普通 ordinary Event 可复用已验证缓存 `auth_context.authority_refs`，安全命令使用确切 `seal_basis`，两者不得替代。内容层仍须独立覆盖 `ak.event.read`、`ak.message.create` 并取得目标 Realm / Strand 的有效 grant；submit service ceiling 本身不授予内容写权限。在线 presence 与延迟/离线发布分别按 registry 的 feature additions 增加 operation。在线 Event 直接在 submit transaction 读取当前 admission state，不需要前置 lease；显式离线 lease 只延长已验证 authority basis 的有限窗口，不提升内容权限。

三层缺项 MUST 使用从 authoritative provision scope 导出的同一 selected capability 集，按最高缺失层 fail closed，且不得静默扩权：provision prepare/commit 在创建或推进 reservation 前只评估 provision 层，缺项返回 `failed_precondition` / `agent_provision_scope_migration_required` 并 provision 新 Agent；key pairing 先评估 provision、再评估 proposed `agent_key_scope`，分别返回 migration 或 `failed_precondition` / `agent_key_scope_reauthorization_required`，Account Authority 不得先持久化 queued authorization 再丢失下游精确 reason；session issuance/refresh 依次评估 provision、accepted key、requested/current session，前两层均允许而 session 缺项时返回 `failed_precondition` / `agent_session_scope_refresh_required`。key 只可在 provision ceiling 内重新授权或轮换，session 只可在两层 ceiling 内重签；两者均不得扩大上层 ceiling，session 也不能通过少报 activation operation 使 capability 消失。
- **Agent MLS runtime endpoint 与持久化**：pairing accepted 后，runtime MUST 以 `(agent_id, exact agent_verification_method, current agent_key_authorize_event_id)` 创建或恢复 Agent MLS endpoint，并在发布任何 KeyPackage 前持久化 identity/private KeyPackage state。Agent branch 不创建、不携带也不从 session/token 派生 synthetic `device_id`；它与 human-device branch 在 KeyPackage、claim、Welcome、durable receipt 与 consume 中严格 XOR。runtime MUST 使用 current authorization 对应的同一 Ed25519 private signing capability 构造 MLS identity；该 private key MAY 位于不可导出的硬件或进程外 signer 中，协议不得要求导出 seed。MLS LeafNode signature key、§9 upload publish signature与 `ak.agent.key.authorize.verification_method` 必须是同一 key。authorization replacement 完成时，旧 session 必须失效，旧 authorization 下 published/claimed 未消费 pool 必须 revoke，旧 Welcome/claim 必须拒绝；runtime 以新 verification method/key/current authorize Event 重建 identity/pool。Welcome routing与 consume只保留上述 Agent authority 三元组，不得 fallback 到 controller device、普通 device authorization 或假 Device endpoint。canonical signing bytes以 [`device-lifecycle.md` §9.0](../crypto-media/device-lifecycle.md) 为唯一合同。
- **Session TTL**:Agent session grant 默认最大 TTL SHOULD 为 15 分钟；若 deployment profile 显式声明更长，不应超过 60 分钟。Controller 进入 `deactivated` / `suspended` 后，其 accountable agent 的 active sessions MUST 通过 account lifecycle / revocation 链失效。单次 `agent_key_proof` / refresh proof 的接收窗口 MUST 与已签发 session TTL 分离：proof 的 `expires_at-issued_at` MUST `<=300s`，用于限制一次性证明的重放窗口；Account Authority 不得因此把成功签发的 Agent session TTL 静默收窄到该 proof 剩余窗口。runtime SHOULD 在 grant 到期前自动轮换；正常轮换不得要求 controller 在线或人工批准。
- **Key authorization lifetime 与 session TTL 分离(longevity-safe)**:`ak.agent.key.authorize` 是可供多次 session 签发复用的 durable key authorization。其 `expires_at` 可选:缺省表示不设时间过期，有效性完全由撤销链治理(`ak.agent.key.revoke`、pause / deactivate、controller lifecycle 级联);声明 `expires_at` 是部署或 controller 的附加策略选择。Account Authority MUST NOT 把上述单次 Agent session grant 的 15 分钟默认 TTL 或 60 分钟上限复用为 `ak.agent.key.authorize` 的有效期上限；每次 session 签发仍 MUST 独立检查 authorization 未撤销、未过期(若声明了 `expires_at`)且 scope / audience 匹配，并把签发出的 session TTL 限制在上一条的边界内。
- **授权链无静默悬崖(normative)**:配对完成后,agent 的持续在线不得依赖任何需要人工续期的定时器。默认配置下，使 agent 失去授权的路径只有:显式 kill switch(pause / deactivate / `ak.agent.key.revoke` / `ak.capability.revoke`)、controller lifecycle 或 Realm membership 级联、以及部署 / controller 显式声明的可选 `expires_at`。Session 由 runtime 持 authorized key 自动重签，不构成失效面。session 签发因授权链异常被拒时,Auth Server MUST 使用统一错误信封返回机器可读 reason,使 runtime 能提示 controller 介入；其中 key authorization 已过期导致的拒签 MUST 使用 reason=`agent_key_authorization_expired`,MUST NOT 混入 `proof_invalid`——runtime 必须能区分"proof 构造错误"与"需要 controller 续期"。对任何非 terminal 的 agent,controller 始终可通过 renew-pairing + grant 重授权恢复，恢复路径本身 MUST NOT 过期。**异步续期与提前提醒**:声明了 `expires_at` 的 key authorization,runtime SHOULD 在到期临近时主动发起续期请求（见 §3.6 同 key re-authorization）;controller 无需保持在线——到期前任意时刻、任一已授权设备签发一次新 authorize 即可完成续期。不接受此运维依赖的部署 SHOULD 不声明 `expires_at`(缺省即无此依赖);协议不定义无人批准的自动续期。
- **High-risk approval**:Auth Server MUST NOT 给 agent runtime 展示 CAPTCHA / OTP 页面；需要人类批准时返回统一错误信封 `error.code=claim_required`，并令 `error.details` 严格匹配 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`：`reason_code=human_approval_required`、`approval_request_id=<opaque>`。Controller 在带外 UI 完成批准，产生 capability / delegation / approval event,agent retry 时引用该 event。该分支由 `ak.vector.agent_auth.human_approval_required.v1` 固化。
- **E2EE access**（conformance vector `ak.vector.agent.mls_keypackage_authorization.v1`）:Agent MUST 作为独立 MLS member 参与，不得伪装成 controller 的 delegated device。Agent MLS KeyPackage MUST 由其当前 active accepted `ak.agent.key.authorize.verification_method` 对应的同一 Ed25519 key 生成 MLS LeafNode signature key并签署发布 transcript；claim / Welcome 的 claimed-endpoint trust binding MUST 使用 `agent_key_authorize_event_id` 引用该 authorize Event，并携 exact Agent method，且与普通设备使用的 `device_id + device_authorize_event_id` 精确互斥。Agent 分支禁止 `device_id`。authorize 被 revoke、supersede、过期或 key 不匹配时必须使未消费 claim fail closed，从而使 key authorization、session proof 与 MLS membership 落在同一审计链。

##### Agent 初次 session proof、holder 出示与重试（normative）

`AgentSessionGrantRequest.proof` 是闭合对象，字段按顺序为
`proof_kind`、`challenge`、`request_canonical_digest`、`audience_id`、`issued_at`、
`expires_at`、`verification_method`、`signature`，全部 required。`proof_kind` 固定为
`agent_key_proof`；不携额外 `nonce`。runtime 为每次新申请生成至少 128 bit 密码学随机
challenge，编码为无 padding 的 canonical Base64URL；同一申请的重传保留原值。
challenge 不是服务端预发凭证，不需要新增 challenge endpoint，也不得复用 pairing handle/code。
`audience_id` 是已验证的目标 resource service 身份，不得由 HTTP Host 或 caller 自选 verifier 替代。

首次验证必须满足 `0 < expires_at-issued_at <=300s`、`issued_at <= now+30s`、
`now < expires_at`。30 秒仅容忍签发时间领先，不延长 expiry 或 proof lifetime。
时间使用 canonical timestamp；缺失值不得补写。该时窗不改变上述独立 session TTL。

令 `R` 为完整 typed 请求 JSON：`request_canonical_digest` 固定为
`sha256:hex(SHA-256(JCS(R 删除 proof.signature 与 proof.request_canonical_digest)))`。
所有其它实际存在成员，包括两个时间、challenge、scope、authorization ref、可选 disclosure 与
body `dpop_binding_proof`，都进入摘要；缺席 optional 不补 `null`。runtime 使用当前 accepted
Agent key 对 `JCS(proof 删除 signature)` 直接作 Ed25519 签名，signature 使用无 padding 的
canonical Base64URL 编码的 64-byte raw signature。proof_kind 与 request digest 都在签名内；
不得套用 Event JWS transcript 或添加私有前缀。接收方从收到的完整 typed 请求独立重算两段 bytes。

body `dpop_binding_proof.proof_jwt` 是冻结申请中的原始 holder proof；HTTP `DPoP` header 是
每次请求的新鲜 transport proof。首次签发必须分别验证两者签名、method/target、时效及适用的
DPoP nonce，且两者 public JWK 的 thumbprint 必须相同；同一 HTTP attempt 使用同一个 JWT 时
只消费一次 JTI。重试必须保留完整 body，不替换 body JWT；header 使用同一 holder key 生成新鲜
JWT/JTI。两者不要求 JWT 字符串相等。命中 §6.2 已完成 issuance record 后，仅复用原 body proof
与 runtime one-shot proof 的耐久验证结果，仍重验当前 header 与原 holder JKT、method/target、
issuer/audience、canonical request digest 及 exact intent。不得把原 body proof 再作为本次 transport
proof 消费，也不得因原 one-shot proof 已过期而否定尚有效的 exact ledger replay。

Agent 初次签发的 request identity 由完整
`(principal_id, agent_key_authorization_ref, verification_method, challenge)` 确定，并由 §6.2
的 issuer/operation namespace 隔离。immutable intent 绑定完整冻结请求和已验证 holder JKT，
不包含可轮换的 HTTP header JWT。同 identity + 同 intent 只能恢复原结果；不同 intent 必须
`duplicate_conflict`。初次 proof 消费与 issuance 的事务/恢复必须保证失败或崩溃不会留下无法
恢复的 burnt challenge；有 pending record 但尚无已验证结果时，不得视作已完成或跳过首次验证。
已完成结果的 expired/revoked/superseded/indeterminate 处理遵循 §6.2，不重新签发。

##### Agent signing-key binding 与 portable signer evidence（normative）

本节 portable evidence 的消费、attestation 直接查询窗口和治理验证规则适用于 Station/peer 验证者。普通客户端使用
[server-trusted-results §5.6](../sync/server-trusted-results.md#56-按次-current-与精确历史签名公钥)
的 self key 结果，current 每次查询且不跨未来 Signal/操作复用，historical 精确绑定原 Event/receiver；
不缓存或 hydrate 本节完整 authority 闭包。controller签署完整authorize Event与客户端真实内容验签不变。

每次 pairing 或 same-key re-authorization 都只用一个 controller-signed `ak.agent.key.authorize` 认证完整公开 key：payload的 `public_key` 使用唯一 closed Ed25519 PublicKey profile（`kty`、`kid`、`algorithm`、`key`），`kid` MUST 等于 `verification_method`，method经注册DID adapter投影为 `agent_id`，raw key恰为32 bytes。Event同时认证accountable controller、scope、audience、issued_at、expiry和批准实例；不另发公开key-binding对象、第二份controller签名或binding-core摘要。portable verifier从完整accepted Event、原producer proof、producer signer evidence 与已确认 Seal/state witness验证同一事实；不得改删已签Event字段再复用签名。私有 `requested_scope_disclosure`、PoP、pairing secret和session material不进入公开Event。

raw-key索引与显示只允许 SDK唯一 `agent_signing_public_key_digest` 对decoded 32-byte Ed25519 bytes计算SHA-256，不hash PublicKey DTO/JWK/multibase/hex文本。稳定candidate binding也使用该raw-key helper；固定profile与完整method/kid约束在schema/admission独立校验，不保留第二套DTO digest。普通自己Station的self key结果继续遵循server-trusted-results；它们不要求客户端携完整portable evidence。

`ak.component.agent.key.v1` 的 registered reducer projection 是 portable state witness 的唯一状态来源，不能只把 key Event 写入历史。cell subject MUST 使用 SDK `composite_subject([agent_id, key_id])`，不得用字符串拼接或 diagnostic subject。每个 `ak.agent.key.authorize` 的 reducer MUST 先对 `payload.supersedes[]` 逐项在对应旧 key cell 投影 `remove(tag=authorized_event_ref 对应的 observed canonical Event dot)`，再在当前 key cell 投影 `add(tag=canonical_event_dot(event_id, write_index), value=完整 authorize payload)`；authorization 元素的稳定 tag 是 [`event-and-patch.md` §2.4.2](../models/event-and-patch.md) 定义的 `<event_id>:<write_index>`，绝不是裸 `event_id`。`ak.agent.key.revoke` MUST 在 `seal_basis` 观察到的对应 key cell 中移除全部 active authorize dot，并加入 `add(tag=canonical_event_dot(event_id, write_index), value=完整 revoke payload)` 的 transition marker；marker 只保留可见证的撤销边界，不是 active authorization。Station MUST 在接受前从 `kind + payload` 重建并逐项校验这些 canonical writes；write 缺失、多余、cell/tag/value/顺序不一致均须 `reducer_projection_failed`。这样 authorize、same-key re-authorization、replacement supersede 与 explicit revoke 都能从签名 Seal 的 resolved cell 独立证明，不依赖服务端私有投影。

`ak.schema.agent_signer_evidence.v1` 是 structural XOR：顶层只能是 `verification_mode=current_admission` 或
`verification_mode=historical_event` 两种 closed object 之一，二者字段集合不同，不能通过改 tag 或增删一个
frontier 互换。共享 `admission_evidence` 只含 `agent_authority_state_evidence`、隐私最小化的
`controller_account_gate_attestation` 及无自引用的 `admission_evidence_digest`。raw public key不是秘密；Agent/controller
private key、MLS private state、服务本地 `account_id` 与 raw account cell 永不进入 portable evidence。

`agent_authority_state_evidence.state` 在 Agent Principal Control Realm 的一个 exact confirmed Seal state 中同时承载完整
pcr_genesis_event、key_authorization_event、key authorization、key state witness 和 Agent lifecycle witness。`state_digest` 只对 state
做 RFC 8785/JCS SHA-256；`attestation` 由该 PCR 的权威 service DID 在独立 domain
`ak.agent_authority_state_evidence.v1` 下签名并逐字绑定 authority、verification method、state digest 与时窗。
state 的 `seal_lineages[]` 必须是把 key/status witness Seal 连接到 `frontier_seal_id` 的完整、无重复
predecessor closure；unknown、fork、跨 Realm、缺 predecessor 或签名无效均拒绝。

authorization.accepted_at 是 key authorization 经 accepted_seal_id 生效的时点，MUST 等于 key_state_witness.seal.sealed_at；accepted_seal_id、key_state_witness.seal_id 与 Seal.id 必须相等。原 Event 的 producer proof 独立验证其 signer evidence；接收服务的存储时间不创造 runtime key 权限，covering Seal 前不得把 key 当作已生效。

key `cell_ref` MUST 精确等于 SDK 从 `(agent_id, agent_key_id)` 派生的 `ak.component.agent.key.v1` composite
subject；`cell_value` 是 closed、canonical sorted active tagged-set entry array，每项 tag 必须解析为 accepted Event 的 canonical
`<event_id>:<write_index>` dot，value 必须是 schema-valid authorize/revoke payload。Agent lifecycle `cell_ref` MUST
由 `agent_id` 派生，`cell_value` 是 closed lifecycle 值；`accepted_status_event`、provenance、registered reducer write、
Seal delta/lineage 和 state leaf 必须互相重算一致。首次 active 的唯一 provenance 是 Agent delegated PCR
genesis `ak.realm.create` 在 `payload.object.purpose == "agent_control"` 上的条件写（subject 取
`envelope.actor_id`，`uninitialized -> active`，见 §3.6.3）；服务私有 row、FSM 默认值或
organization-governed PCR 都不能合成首次 active witness。

Portable lifecycle provenance 的每个 closed 分支只携对应的 accepted 状态 Event ID：genesis 的
`realm_create_event_id`、pause 的 `pause_event_id`、resume 的 `resume_event_id`、deactivate 的
`deactivate_event_id`。不得携 `agent_provision_event_id` 或 `predecessor_*_event_id` 等无独立证明载体的
历史引用；`prev_refs` 是 actor 因果前沿，不是上一条 lifecycle Event 的专用指针。§3.6.3 的唯一 accepted
provision 反查仍是 genesis admission 的强制条件。Receiver MUST 验证状态 Event 的 原始 producer proof 与可携带授权
绑定与签名，并使用其中冻结的 `producer_signing_key_did` 验 controller producer proof；不得重新用当前
controller device 状态解析历史签名。随后 MUST 按 registry 从签名 Event 重算 lifecycle cell 与 transition，
绑定完整 ActorId、cell head/value，以及包含该 Event 的 signed Seal 到目标 frontier 的 ancestry。


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

Account Authority 是同一 owning Station 下的独立签名职责，可以使用专用 verification method，但没有独立 service DID（见 overview/architecture.md 与 sync/service-surface.md）。消费者从实际 Agent 完整 AccountId 独立取得 Station：gate.authority_id MUST 等于该 Station；controller 的完整 AccountId 从 key_authorization_event 的已验证原始 producer proof 与可携带授权 与 producer 身份取得，MUST 等于 {principal_id: binding.controller_principal_id, station_id: Agent AccountId.station_id}。同 principal 在另一 Station 的 Account 或 gate 自报 authority 均不能替代。controller binding 使用该 Event 冻结的 producer method/key 验签；设备 method 不要求出现在 Principal DID assertionMethod 中，不再携带独立 controller signer evidence ref。

Agent authority **不能自行合成 Account Authority evidence**。当签发或直接消费需要 current-query 语义的结果且缺少未过期、匹配 controller principal 的 gate 时，
它 MUST 使用部署内已登记的 `ak.gate.account.command.issue_controller_gate_attestation.v1`，提交 closed
`{request_id, principal_id, agent_authority_id}`。该请求走**部署内认证合同**：认证 MUST 绑定已配置的调用方、目标
Station、trust domain 与允许的 operation，Account Authority MUST 只从该已认证调用关系取得调用方身份。请求体不携带、
也不得重新引入任何 service resolution carrier；`Source-Service-ID`、客户端自报的 `internal` 字段、裸 DID、URL、bearer
或自报 public key 都不是身份来源。已认证 source、`agent_authority_id` 与 controller exact AccountId 的 Station 必须
相同，且 MUST 等于该 principal 当前 binding 指定的 authority；Account Authority 从自己的权威 account status/binding
取值，不接受 caller 自报的 account active 值。未知 principal、错误 authority 或无权 caller 返回不可枚举的
`not_found`。gate **响应**侧不随请求侧改为内部认证而削弱：attestation 签名、其 verification method 的公开 DID
assertion 授权、TTL 与 exact replay 全部保留，因为该响应进入外部 Agent 证据链，由 SDK 与外部 Station 独立验证。
gate 的正有效期 MUST 不超过 300 秒；相同 request id 与 canonical intent 的 replay 返回原字节，
不同 intent 为 `duplicate_conflict` 且零签发。有效 gate 可以跨 current 状态查询与同一适用关系的设备复用；直接 current 消费只在
缺失、到期或已观察状态变化时刷新，不增加 controller 审批。普通 Event 携带并验证的是原 observation 事实，gate 到期本身不要求 producer 刷新，也不要求 Account Authority 在线。

#### 可复用当前授权

`current_admission` 表示该材料在签发时来自 current basis，只包含 tagged `admission_evidence` 与可选 transparency；该名称不赋予普通 Event 周期租约语义。Agent Authority 的唯一状态签名为
`agent_authority_state_evidence.attestation`，它绑定 exact authority、method、state digest 和观察时窗；独立的 controller
proof、Account Authority gate 和 Seal 签名各自保留。不再定义 current observation、Agent outer 或 query response
签名。attestation `issued_at` MUST 是读取权威状态的真实时刻，`0 < expires_at-issued_at <= 300s`；转发、重新包装、重连、
磁盘恢复或重复签旧观察 MUST NOT 重新计时。直接 current-query 消费的有效截止为 attestation、gate、binding 与 key authorization 的所有已声明 expiry 最小值；有效开始为 attestation.issued_at、gate.issued_at、binding.issued_at、authorization.accepted_at 与 not_before 的最大值，共同窗口必须非空。普通 Event 将该时窗作为已签原始观察验证，不按接收时墙钟重新要求 current；其后由显式业务期限与已知撤销 fence 决定 live 接纳。

直接 current-query 消费与普通 Event 首次验证都 MUST 从可信来源核对完整 Agent AccountId、Agent PCR authority、controller exact AccountId、runtime
method/key、accepted authorize Event/dot 与 scope disclosure。state 中 controller binding 和独立 gate 的 principal
必须一致，authority routing 必须匹配完整 AccountId。裸摘要、同 principal 的另一 Station、同 owner 标记和另一端
的 verified 标志都不是授权。新操作仍从实际请求核对 operation/scope、Realm、当前 membership/generation 与授权
subset；有界缓存的 key、Agent lifecycle、controller account 均须 active。已观察 revoke/supersede、pause/deactivate、
account inactive 或相关冲突立即使当前 Agent 签名授权缓存失效，不等租约到期。membership ending/generation 变化立即使对应操作不再适用，由每消息的 membership/MLS 检查拒绝；它不改变 Agent 签名事实，不要求刷新同一 PCR state attestation。

自有关系在 accepted pairing/首次入组时验证并保留完整材料。稳态多条 Signal MUST 复用仍有效的本地验证结果，
每条独立验证 producer signature、actor/endpoint、scope/group/epoch、TTL、AAD/AEAD 与 replay。普通重连、重新订阅、
恢复未过期可信状态不触发重新配对、完整取证或状态重签。到期只刷新状态；绑定变化或缺材料才验证相应新增材料。
刷新失败暂停需要当前授权的操作，历史验证不受影响。上下文只是派生验证结果：不得新增 context id、服务端登记表、
建立/确认握手或独立撤销链。多端共享同一已签事实，各端仍自行验证 session、设备授权、MLS 成员资格和消息。

Agent authority MUST 由完整 Agent ActorId 的 AccountId.station_id 独立确定；state.authority_id 必须与其相等，不得用响应自报 authority 作为 expected authority。Service signer leaf 验证完整 method-native history：resolution 来源按自身签发时刻验证，各个 Station proof 和 attestation/gate 按其实际签发/接纳时刻选择历史 method。历史方法不必仍存在于 current head；新 resolution 不得让旧签名追溯失效。

Signal current-signer query 的 `known_agent_state_digests` 只声明本地已完整验证的 state；相同摘要可在专用 compact
transport root 中省略 `state`。接收端 MUST 先按摘要补回完整 state，再重算 admission/root digest 和验证签名；
compact bytes 不是 canonical signer-evidence 对象，也不能存入 canonical CAS。变更 state 必须完整交付。
`known_signer_evidence_refs` 允许省略已知依赖，消费者按已验证缓存与收到材料组成完整闭包；缺项仍 unresolved。
稳定材料不重复验签，authority 观察更新只验证新 attestation/gate；冷缓存不声明 known，返回完整材料。不新增取回端点。

稳定 state MUST 始终携带原始 pcr_genesis_event 与 exact key_authorization_event，二者均为已有完整 accepted Event，不是新 proof。前者必须是本 Agent 完整 Account actor 的唯一 ak.realm.create，event-derived Realm 必须等于 principal_control_realm_id，并按 §3.6.3 验证 create-locked controller、delegation 与 notary。即使当前 lifecycle provenance 已是 resume/pause，仍须携带原 genesis，不能把后续状态 Event 当作 genesis。后者的 Event ID、完整 Agent actor、executed_by 的完整 controller Account、Agent/key、binding core digest 与授权 witness 必须逐字匹配；executed_by/authorization_ref 必须与原 genesis 的 controller/delegation 一致。两者都独立验证唯一 producer proof 及其精确 signer evidence，再验证所属安全序列的确认；controller binding 的签名方法必须精确等于授权 Event 的 producer method，并使用同一已接纳 key 验证。不得改查当前设备或 Principal DID assertionMethod。

闭包的必需边是 ASRE 的 authority 与 Account Authority refs，以及 genesis、key authorization、lifecycle 和历史接纳 Event 各自 producer proof 的 signer_resolution_evidence_ref。相同 ref 仅保留一次。PCR Seal 的 Agent root 签名从已验证 genesis 的 frozen notary descriptor 验证；controller delegated notary 仍须满足 §3.6.3 的精确授权规则，Station 或 Account Authority service key 不得替代。缺少原 Event、历史签名 method、真实 notary 授权或签名均为不完整闭包；不得以额外在线 DID 查询补足。未被实际 proof/ref 使用的材料仍为 surplus，全部唯一内容摘要仍受 64 项上限限制。

state 的 accepted_delegated_notary_signers 是既有 NotarySignerDescriptor 的必需数组，按 verification_method 的 UTF-8 字节序排列、去重；只含本 state 所携 Seal 签名实际使用的 delegated controller key，只有 Agent root 签名时为空。每项 actor_id 必须逐字等于已验证 genesis.executed_by 的完整 controller Account，且符合 create-locked delegation；verification_method、key kind、JOSE algorithm、frozen public key 与 digest 按既有 descriptor 规则逐项验证，并精确匹配目标 Seal 签名。未使用项、同 method 冲突 key、另一 controller/Station 或 service actor 均拒绝。

这些 descriptor 是 authority 在原 Seal admission 时独立核验并持久保留的接纳事实，由唯一 state attestation 连同该 state 的确切 Seal 集合一并签名；不另造公证 receipt、签名或通用 device evidence。producer MUST 在原接纳事务保留来源，之后即使设备撤销、轮换或不在线也只能重用原记录，不能从当前设备状态重构历史 key。consumer 只能用该映射验证本 state 的已接纳 Seal，不得用它验证普通 Event、Signal、controller binding 或扩张 genesis notary/delegation。不同合法 controller 设备可封存其他设备已提交的 Event，不要求重签 genesis 或重新授权 Agent runtime key。

#### 历史接纳

`historical_event` 保存完整冻结 `admission_evidence`、`authorization_closure_refs` 和可选 transparency。Event 的唯一 producer proof 指向原 signer evidence；receiver receipt 和接收时间均不授予作者权限。历史 wrapper 不需要另签消息准入证明，也不能改写冻结内容。

Agent Authority attestation 与 Account Authority gate 的签名按其 observation 依据验证；短缓存 TTL 不要求普通消息在线刷新。真实 key/delegation 的授权期限、Agent lifecycle、controller lifecycle 及适用关闭集合分别验证并取交集。后来发现撤销可使此前暂时接纳的普通 Event 隔离，不能声称所有已接纳历史永远有效。

原 genesis、key authorization 和 lifecycle Event 的 producer proof 必须独立验证，所需递归 refs 去重保留。设备签名 key 由原授权 evidence 解析，notary 签名按唯一确认配置的 frozen descriptor 验证；两者不得互换。缺必要依赖 unresolved，确定无权则拒绝/隔离。当前 DID head 和新服务签名均不能补造历史权限。

同一不可变 selector tuple 与完整内容摘要原子存储 root 和递归依赖；相同内容重试 no-op，异内容冲突拒绝。普通聊天沿已验证缓存继续，真正需要当前结果的会话、管理和安全操作执行各自 current gate。`ak.vector.agent.signer_evidence_binding.v1` 与 `ak.vector.agent.historical_evidence_materialization.v1` 覆盖上述区别。

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

`POST /_arkret/open/agent-pairing/resolve` 的新响应 MUST 在六个基础字段之外返回
`runtime_identity = {controller_account_id, verification_method}`。controller AccountId
MUST 来自该 Agent 已接受的完整 controller 账号绑定，不得由 principal 或服务端域名猜测
Station。完整 DID URL MUST 使用已接受的 Agent DID（例如 controller delegation 中的 DID），
其 controller 经 DID method adapter 投影后 MUST 等于 bootstrap `agent_id`；不得从
`ak:did_core:*` 反推 locator。服务端 SHOULD 为同一 pairing handle 返回稳定的 key fragment；
该 fragment 是运行时密钥标签，MUST NOT 要求其为 `ak:device:*` 或将其当作 human-device 身份。
客户端 MUST 自动消费此对象，无需用户手填这两个内部字段。旧存储 bootstrap MAY 缺省
`runtime_identity`，但新链接配对遇到缺失 MUST 明确提示更新配对服务，不得合成身份或静默挂起。
此对象仅是配对上下文，不是授权；local key PoP、controller 审批、完整 authorize Event
及既有 scope 校验仍 MUST 执行。

Conformance vector：`ak.vector.agent.runtime_key_binding.v1`。

每个 open `pairing_request_id` 最多一份 frozen runtime candidate。稳定binding的唯一canonical对象为 `{kind, agent_id, pairing_request_id, verification_method, public_key_digest, attestation_digest}`，kind=`ak.agent.runtime_key_binding.v1`；public_key_digest使用上述唯一raw-key helper，attestation_digest是可选runtime_attestation（缺省null）的JCS SHA-256 typed digest，外层对象也做JCS SHA-256。pairing secret、expiry和PoP freshness不进入稳定candidate identity。首个合法candidate冻结key/method/attestation；同binding可刷新PoP但不得换candidate，变更必须renew新handle。

`proof_of_possession` MUST 验证 `agent-operations.schema.json#/$defs/agent_runtime_key_possession_proof`，不得接受开放 JSON、实现私有字段或算法 fallback。v1 runtime key profile 固定为 Ed25519：`public_key.kty="OKP"`、`public_key.algorithm="Ed25519"`，`public_key.key` 解码后恰为 32 bytes；`public_key.kid`、request `verification_method` 与 proof `verification_method` MUST byte-identical，且该 DID URL 的 controller MUST 经注册 DID method adapter 投影为 request `agent_id`。proof `kind` 固定为 `agent_runtime_key_possession`，proof `signature_algorithm` 固定为 `Ed25519`（Arkret 自有对象不使用 JOSE 短名 `alg`，见 `signature-alg-registry.json`；`alg` 只保留给 JWS protected header 与 JWK），`signature` 是 64-byte raw Ed25519 signature 的无 padding base64url 表达。`Ed25519`也是 RFC 9864 fully-specified JOSE algorithm identifier；任何不能仅凭该算法标识唯一确定曲线和签名算法的多态别名都不属于本协议词表并 MUST fail closed。key 与 signature 解码后还 MUST 以 canonical unpadded base64url 重编码并与 wire byte-identical；非零 unused bits、padding 或其它别名表达必须拒绝。

构造方先计算上述稳定 `runtime_key_binding_digest`，再对以下闭合对象的 JCS bytes 签名；`context` 只存在于签名输入，不是 wire 字段：

```json
{
  "context": "ak.agent_runtime_key_possession_proof.v1",
  "kind": "agent_runtime_key_possession",
  "verification_method": "<request.verification_method>",
  "challenge": "<pairing_request_id>",
  "audience_id": "<pairing record service_id>",
  "created_at": "<proof.created_at>",
  "expires_at": "<proof.expires_at>",
  "pairing_code": "<pairing record pairing_code>",
  "runtime_key_binding_digest": "<stable binding digest>",
  "signature_algorithm": "Ed25519"
}
```

proof `challenge` MUST byte-identical 于权威 pairing record 的 `pairing_request_id`，不得由 caller 另造；`audience_id` MUST byte-identical 于 bootstrap 与 record 的 service DID `service_id`，不得使用 URL、HTTP Host 或请求体自选 verifier；签名输入中的 `pairing_code` MUST byte-identical 于 runtime body 与 record 中的 ≥128-bit secret，但不得复制到 proof 或 controller projection。`transcript_digest` MUST 等于上述 JCS bytes 的 SHA-256 typed digest；接收方必须先独立重建并比较 digest，再用 request `public_key` 验 Ed25519 signature。任一 equality、长度、digest 或 signature 不符都在创建/更新 pending request 前 fail closed。

`created_at`、proof `expires_at` 和pairing expiry使用固定UTC毫秒profile。首次接纳每份PoP须满足created_at≤now+60s、created_at<expires_at≤created_at+300s、expires_at≤pairing expiry且now<expires_at。Station耐久记录验证材料与接纳时间；后续批准有效期由handle/candidate/fence和批准scope/time约束，不因原PoP自然过期或same-binding fresh PoP替换而失效。split Authority独立复验签名与记录接纳时freshness；首次激活仍要求handle未过期，runtime session另需新的agent_key_proof，不能把曾验PoP当永久在线证明。

Runtime MUST 在首次提交前持久化本地 key seed/private key，并在同一 open `pairing_request_id` 的整个生命周期内跨进程重启、配置重载和同名 channel 删除/重建复用同一 key binding；发现已有合法 key 时不得用新 seed 覆盖。若原 key 已丢失、损坏或无法访问，runtime MUST 停止重试并要求 controller 执行 `renew-pairing`，取得新 handle 后才能生成新 key。Runtime 不得把服务端的 `agent_runtime_request_conflict` 当成“以新 key 覆盖旧 pending request”的许可。

controller `approval_evidence.request_canonical_digest` 的唯一canonical对象为 `{kind, operation_id, controller_principal_id, agent_id, pairing_request_id, approval_request_id, expires_at, audience_id, runtime_key_binding_digest}`：kind=`ak.agent.key_pairing_request_binding.v1`，operation_id=`ak.gate.account.command.pair_agent_key.v1`，expires_at逐字等于pairing expiry，audience_id等于authority service DID。该对象只绑定冻结candidate/批准实例，不含pairing secret或PoP digest；Event自身另行签署scope、audience、expiry和exact supersedes，不重复造签名对象。

最终 pair operation 从当前持久candidate/record重算stable binding与批准digest，核对body的pairing_request_id/approval_request_id、Event内联key/method与私有scope disclosure。服务检查PoP已按上文接纳并可独立复验，不接收caller回声key/PoP/attestation。同candidate刷新PoP保留批准；candidate、handle或授权意图变化必须使旧批准fail closed。base v1信任自己Station如实投影candidate；有效PoP不证明是用户想配的runtime，也不防恶意自己Station替换为其自有key。需要独立发现替换时，产品须让用户在runtime可信显示与controller批准页带外比对raw-key fingerprint，不得把同Station多发proof宣称为此保障。

`ak.agent.key_pairing_request_binding.v1.expires_at` 与权威 `pairing_expires_at`、PoP `created_at` / `expires_at` 都使用统一 UTC 毫秒 profile `YYYY-MM-DDTHH:mm:ss.SSSZ`。构造方 MUST 先把 typed instant 按 Unix 时间向负无穷方向 floor 到毫秒，再以恰好三位小数和大写 `Z` 序列化；投影、transcript 和摘要绑定使用逐字相同的 canonical string，不得从宽松 RFC 3339 输入临时正规化，也不得另派生 epoch 字段。非法或非 canonical wire 输入必须在摘要验证前 fail closed。

首次合法请求生成一个稳定 `approval_request_id` 和 `ak:notification:*` id，并在创建 pairing record 的 account context 中物化 `action=upsert` 的 Agent runtime approval notification delta。相同 stable binding 的重试是幂等的：允许刷新 PoP 和完整 request，但保留两项 id，并重新物化同一 `action=upsert` 投影。已有 pending 时，不同 stable binding MUST 返回 HTTP 409 `agent_runtime_request_conflict`，不得替换 controller 当前看到的请求。

Runtime提交、controller视图和最终批准体是不同closed DTO。open submit含secret与PoP；普通controller投影只含handle、approval_request_id、Agent、method、raw key、stable digest和可选attestation，不含PoP或secret回声。客户端从authenticated key_state同时取得exact current active授权集和private ceiling，核对已展示Agent、raw-key fingerprint、scope/expiry、exact supersedes与完整待签Event bytes后，只附加controller producer proof并提交最小pair command；private scope disclosure仍按既有verifier/audience/challenge合同签发。split verifier原材料只经前述S2S限制字段读取。notification仅作发现，读取authenticated view后才能批准。

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
   `initial_resolution`、allocation 与 authorization ref。`requested_scope_digest` 由 controller 按 §9.1 的既有域分隔算法对自己冻结的 exact requested_scope 重算，outcome 不回显。controller MUST 把返回的
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
为 subject 写一个 `sequenced_state` 的 cell；两条 provision 声明同一 realm id 时第二条 MUST 被
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
的完整 Agent account ActorId：先把 RFC 8785 JCS 文本作为唯一 composite 分量，再按 §9.5 的 canonical
composite 规则派生 subject；transition 为 `uninitialized -> active`。`ak.self.agent.pause` / `resume` /
`deactivate` MUST 使用完全相同的 subject。Agent principal 只由 `envelope.actor_id` 派生，controller 只由
`executed_by` 派生；lifecycle payload 不携 `agent_id` / `controller_principal_id`。非 `agent_control` 的 create MUST NOT 触发
该写入。服务私有 row、FSM 默认值或 organization-governed PCR 都不能合成首次 active witness。

Portable lifecycle provenance 的每个 closed 分支只携对应的 accepted 状态 Event ID：genesis 的
`realm_create_event_id`、pause 的 `pause_event_id`、resume 的 `resume_event_id`、deactivate 的
`deactivate_event_id`。不得携 `agent_provision_event_id` 或 `predecessor_*_event_id` 等无独立证明载体的
历史引用；`prev_refs` 是 actor 因果前沿，不是上一条 lifecycle Event 的专用指针。§3.6.3 的唯一 accepted
provision 反查仍是 genesis admission 的强制条件。Receiver MUST 验证状态 Event 的 原始 producer proof 与可携带授权
绑定与签名，并使用其中冻结的 `producer_signing_key_did` 验 controller producer proof；不得重新用当前
controller device 状态解析历史签名。随后 MUST 按 registry 从签名 Event 重算 lifecycle cell 与 transition，
绑定完整 ActorId、cell head/value，以及包含该 Event 的 signed Seal 到目标 frontier 的 ancestry。


**未完成 provision 不可撤销（normative）**：`ak.agent.provision` 一旦 accepted 就是 controller PCR 中不可删除、
不可重写的历史事实，其 `agent_slug` 与 `principal_control_realm_id` claim 也不得通过服务私有清理、超时或垃圾回收
释放。controller 必须持久化并恢复冻结的 genesis bytes，继续完成同一 provisioning；协议不提供第二条 HTTP
放弃通道。客户端若在 provision accepted 前放弃，只需丢弃尚未提交的本地 intent。

### 3.7 MLS KeyPackage Key

MLS KeyPackage 携带 MLS leaf/init 等群组加入材料，但 Arkret 不为它新增一把账户级授权 key。endpoint signer 使用 [`../crypto-media/encryption-and-audit.md` §2.6](../crypto-media/encryption-and-audit.md) 的封闭三分支：ordinary human 使用 current accepted device key，Agent 使用 exact current agent key，minimal-metadata endpoint 使用 exact pairwise `did:key`。

要求：

- MUST 绑定到对应分支的完整 Actor/endpoint identity；只有 ordinary human 分支携 device id
- MUST 由该分支 current accepted endpoint key 签名，不存在 principal signing key 或独立 ordinary MLS leaf signer fallback
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

跨账号 `ak.self.keys.read.lookup.v1` 的 device row **不承载** `principal_genesis_receipt` 或任何 PCR chain/Seal；其设备投影由自己的 Station 按 [`device-lifecycle.md` §8.2/§8.3](../crypto-media/device-lifecycle.md) 验证 origin Station signed `device_projection_attestation` 后，以 closed `device_projection` 投影交付；attestation 与其 proof 只存在于 Station↔Station 的 peer row，不进入客户端 row。跨账号查询由自己的 Station 以该合同验证当前 device/generation/key，客户端消费 exact account/selector 绑定的结果，不取得或重放对方 PCR；这与内部设备投影的 §5.5 PCR authority 要求是不同角色，不能互相替代或扩大披露。

public projection 本身仍 MUST 可验证：它由 Station 的 `projection_attestation` 覆盖，用于确认 `(principal_id, station_id)` 的 current `did` 与 method history 位置。首次接触（Contact request、invite、member add）只需要该 public projection 与可验证 service route，MUST NOT 以取得对方 PCR genesis、Seal 或 history 为前置条件。

Organization principal 的 control stream 遵守同一 PCR 规则，但它没有共享 human password account。组织 PCR 的 genesis / recovery / delegated write MUST 由组织 DID inception/controller proof、满足组织 governance threshold 的 proof、或组织 DID Document / governance profile 明确委派的 Account Authority / `ArkretGovernanceService` 授权。委派路径的 purpose MUST 覆盖对应动作（例如 `principal_control_realm_bootstrap`、`device_enrollment`、`session_issuer` 或 `ak.realm.organization`），且事件必须保留实际执行主体（`executed_by`、governance decision id 或等价审计 ref）。普通企业 SSO/OIDC/passkey 登录只认证某个管理员 principal；它不能单独创建、登录或控制组织 PCR，除非该 Account Authority 同时出示上述组织侧 delegation / governance proof。

Agent 是独立 DID principal，不继承 controller 的 PCR 或 home/Collaboration Realm。Agent DID accepted inception entry 0 MUST 只含 Station 与唯一 `ArkretManagedPrincipalController` delegation，MUST NOT 含 PCR id 或 `ArkretPrincipalControlRealm`。Agent PCR genesis accepted 后，controller MUST 使用 entry 0 预承诺的 update key 发布连续 entry 1，并新增唯一 service entry：`id=<agent DID>#arkret-principal-control-realm`、`type="ArkretPrincipalControlRealm"`，`serviceEndpoint` 为闭合对象 `{realm_id, controller_did, authorization_ref, requested_scope_digest}`。`realm_id` 是该 Agent PCR genesis `ak.realm.create` 的 event-derived `ak:realm:*`（按 [`../models/realm-and-space.md` §2.5.0](../models/realm-and-space.md) 的通则 `retype(event_id)` 派生，服务端不得自选）；该 service entry 是他人**发现**该 realm id 的已发布指针，不是其派生权威；`controller_did` 是获授权的 managed-principal controller；`authorization_ref` 是 entry 0 中覆盖 `principal_control_realm_bootstrap`、agent-control authoring 与 `principal_control_realm_recovery` 的 delegation DID URL；`requested_scope_digest` 必须按 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 的域分离 canonical input 重算匹配。entry 1 的四元组 create-locked；后续 DID update 删除或改变任一字段时，该 Agent binding 对新授权失效，不能把更新后的值视为扩权。公开 DID Document 与其历史 MUST NOT 包含 `requested_scope`、具体 resource selector 或 constraint。Receiver 必须按 authorizing Event / grant 的 accepted-at 解析 Agent DID history，逐字验证此 entry，并从 controller 经 [`../identity/identity-handles.md` §16](./identity-handles.md) 的认证私有 presentation 路径取得符合 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 的完整 scope 披露。Receiver MUST 校验 `request_id`/`challenge` 单次使用、`verifier_id`/`audience` 精确匹配、`expires_at-issued_at <= 300s`、controller 当前 proof 与 disclosure digest，再以披露 scope 重算 DID 中 commitment；任一环节失败均 fail closed。成功接收后 MAY 把披露作为加密的 verifier-private evidence 保存，但缓存键 MUST 至少包含 `(agent_id, requested_scope_digest, verifier_id, audience)`，不得把 service-local Agent row 单独当成协议绑定，也不得把披露写回公开 DID、Realm plaintext、durable Event、pairing code 或通知。

[Contact §2](./contact-and-direct-conversation.md#2-contact-写链回执与-contact-round) 五类历史 carrier 是已登记的
exact-Event source projection 消费：源 Station 仍在其 command 确认路径履行上述完整 Agent/controller/key/grant
与私有 scope 校验，接收方验证公开 create-locked Agent DID 绑定、完整 Account/Station、source 历史签名及
`producer_signer` 所绑定原 Event 的实际 producer 签名。该接收方不执行新的 Agent 控制命令，不因此取得私有
requested_scope 或 PCR history；不得把此窄投影复用于 generic Control admission、其它 Event、runtime session、
DID 更新或 notary。其它 Agent signer-evidence 与 scope disclosure 消费继续按原适用操作验证。


该边界的 conformance vector 为 `ak.vector.agent.pcr_separation.v1`。

Agent PCR genesis MUST 使用 `purpose="agent_control"`，MUST NOT 携带 human-only `founding_device_descriptor`（`genesis_salt` 与其它 Realm 一样必填），并遵守共享 PCR profile、`history_access=since_join`、`encryption_profile=mls_rfc9420` 与两条 `e2ee_required` floor；`created_by` 与 notary 都绑定同一完整 Agent account ActorId。Controller 受托创建或写入 Agent PCR 时，Event `actor_id` 是控制事实所属 Agent 的完整 account ActorId，`executed_by` 是 controller 的完整 account ActorId，`authorization_ref` 是上述 DID delegation 或其可验证 materialized grant；proof verification method 必须属于 controller，不得由服务端伪造 Agent 签名。Agent actor 使用 `service` variant、`executed_by` 或配对 `authorization_ref` 缺失，或缺少 exact Station binding 时，receiver MUST fail closed；对 agent-control genesis 与 `ak.self.agent.pause/resume/deactivate`，该 executor pair 的存在由 event-kind admission 规则（`event-kind-registry.json` 的 admission_variants 及其 Event Envelope schema 锁）强制，不依赖通用 envelope 的可选 `executed_by`。Agent 与 controller 的 principal 分量只从 `actor_id` / `executed_by` 取得，payload 不再携 `agent_id` / `controller_principal_id` 镜像。同一 `principal_id` 在不同 `station_id` 下是不同 Account ActorId，MUST 派生不同 lifecycle cell subject，禁止退化为裸 DidCoreId 或 `composite(DidCoreId)`。Agent PCR 的 MLS group state MUST 由 controller E2EE client 本地生成；服务端只能保存 ciphertext、公开 envelope metadata 与 reducer 所需的承诺/证明，不得生成、托管或解密该 private state。Agent profile、`ak.agent.key.authorize/revoke` 与 `ak.self.agent.pause/resume/deactivate` 写入 Agent PCR。Controller-owned `ak.agent.provision` 保持在 controller PCR，并原子投影 Agent provisioning、accountability、selector 与 `principal_control_realm_id` claim 事实；后续独立变更仍可使用通用 accountability/selector Event。该 provision MUST 先于 Agent PCR genesis 成型并在另一次提交中被接受，genesis 的准入由 §3.6.3 的反查绑定，二者 MUST 由同一 Station 承载。Realm-specific capability grant 仍写入所治理 action 所属 Realm。Pairing request 与 approval notification 永远不写入任一 PCR。

Agent PCR 的 Seal 由 `POST /_arkret/self/seals`（`ak.self.seals.command.submit.v1`）直接提交；Seal 不是 Event，也不经 EventInitialSubmission。若 accepted Agent DID delegation 的 purpose 覆盖 `principal_control_realm_recovery`，该 delegation 同时授权当前 controller device 为此 Agent PCR 的 delegated notary signer；receiver MUST 从唯一 signed Agent PCR create Event 精确验证 `(Agent account ActorId, controller account ActorId, realm_id, authorization_ref)`。Agent PCR Event 必须由 producer 签名 Realm `scope_ref`，reducer 独立复核。首个非空 Seal MUST 无 predecessor 并原子覆盖 Agent PCR founding anchor unit；Station、Account Authority 或其他 service 不得用 service key 代替 Agent/controller 签署。

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

**执行放弃（normative）**：仅调用 `ak.gate.account.command.abandon_identity_creation.v1`，携带稳定 request_id、principal_id、did_version_id、lease id/fence 和为此次显式确认新取得的 holder-bound handoff。字段顺序、固定后果、当前 checkpoint 重验、PCR 竞态、单 tombstone 与 exact replay 由 [account-lifecycle §2.1.2](./account-lifecycle.md) 唯一规定。不存在前置 abandonment challenge；该删除不降低 fresh handoff、明确用户动作或零写入原子边界。身份已经 accepted 必须拒绝放弃并走其既有生命周期，不能通过 lease expiry、fence takeover 或垃圾回收模拟显式放弃。

#### 5.0.3 PCR-Policy Re-anchor Unit（normative）

全设备丢失时，基础恢复直接使用丢失前已进入 accepted Seal/control state 的 PCR recovery policy。客户端
建立 recovery session，提交满足 policy 的 recovery secret、device quorum、trusted recovery service 或
threshold proof；验证通过后原子提交：

1. 由 session 冻结的 replacement device identity key 签署的、policy-authorized `ak.device.reanchor`，携带 `recovery_authority_kind="pcr_policy"`、policy/session ref、
   `previous_device_generation`、严格递增的 `new_device_generation` 与 replacement authorize payload digest；
2. 同一 replacement device identity key 自签 `ak.device.authorize`，`authorization_binding_kind="pcr_recovery"`，`prev_refs`
   只含 re-anchor Event id。

这两个预授权槽位的 producer proof 均 MUST 省略 `signer_resolution_evidence_ref`；否则实现会要求 replacement device 在被该 unit 授权前已经拥有 accepted device signer evidence，形成循环。专用 recovery unit verifier 只能使用 session 冻结的 candidate identity key、create-time possession proof、accepted recovery policy/session 与 unit-local overlay 验两条签名，并在完整验证后原子建立新 generation。任一 Event 脱离完整 recovery unit/receipt closure 都不可进入普通 submit、federation、backfill 或 shared read；其它 device Event 省略 ref 必须 fail closed。

`new_device_generation` 是 PCR-local monotonic generation ref，MUST NOT 等于或派生自 DID `versionId`。
generation revision/CAS 在唯一合法 PCR Seal 序列的 unit 执行位置校验，只有完整 unit 的 committed 结果才 fence 全部旧 generation device；pending/rejected 候选不推进或冲突化 generation，resolution cell 不变。承载该 committed 结果的首个新 generation Seal 由同一 replacement device 签署，其 unsigned body 在 RecoveryTransaction create 的专用 prepare 中冻结，并只能与两条 Event 一起经 `commit_recovery_unit` 的唯一原子提交被接受（[`security-transactions.md` §2](./security-transactions.md)）。两条 Event 共享 session 冻结的
`requesting_device_public_key_did` 与 unit-local candidate overlay；create-time PoP、factor transcript、
设备 method 和原子消费规则全部按 `crypto-media/device-lifecycle.md` §14，不能以 root Event proof 替代。唯一确认与 rival 无执行效力由 `ak.vector.identity.device_reanchor.v1` 验证。

DID-root recovery 是 accepted policy 可显式启用、可撤销的一种 proof factor。只有 adapter 同时满足
`verifiable_control_history` 与 `pre_rotation_commitment` 时，re-anchor 才可携带
`recovery_authority_kind="did_root"` 与 recovery-session 已冻结的 current-root evidence。未启用、已撤销或
method 不支持时 MUST `unsupported_feature`/`recovery_policy_mismatch`。它不在 RecoveryTransaction 中发布
DID operation，也不推进 resolution；用户另行执行 method successor 时走独立 DID operation 发布流程。

#### 5.0.4 Recovery-material gate（normative）

Genesis/re-anchor accepted 只建立可认证设备，不等于 recovery ready。在首个 accepted Seal 与由该设备签署的 genesis recovery policy 都完成前，PCR 必须保持 `recovery_material_pending`。此 gate 不回滚已 accepted identity/device state；失败后客户端 exact resume。

**客户端续接边界（normative）**：注册返回有效 Standard grant 且 current-principal 已核对完整 Account、Station、holder/device 与唯一 PCR 后，客户端 MAY 建立该已接纳账号的本地存储上下文。需要缓存 frontier 或 recovery evidence 的客户端 MUST 在对应写入前建立该上下文并耐久保存续接 checkpoint；不得要求先完成 recovery 才能建立其自身所需的账号存储。存储上下文存在不构成 recovery ready、普通 E2EE 授权或 setup complete；客户端 MUST 保留未完成 gate 和 exact replay 状态，完成后才发布相应产品就绪状态。协议不规定客户端内部类型名或要求新增临时账号／SessionGrant。

gate 的作用范围是：**发起任何 post-bootstrap E2EE Realm 创建/加入前 MUST 完成**（与 §7.11 一致）；gate 未完成时允许读取与非 E2EE 的本地/账号级操作。gate 期间允许的封闭写入集合恰为：该 PCR 的首个 Seal、genesis recovery policy、使该 policy 生效所必需且不包含其它控制写入的设备签名 successor Seal、以及 genesis unit 自身产生的 device projection 更新（`ak.device.list_update`）；其余 Realm 写入 MUST fail closed。policy Event 接纳不等于 policy 已生效；完成 gate 必须观察到已生效的该 policy，不能仅凭接纳回执解除 gate。

### 5.1 新设备加入（首台设备已存在）

推荐流程：

1. 新设备本地生成 device key。
2. 新设备没有 accepted-device signer 时不得调用 `issue_session_grant`，也不会得到任何 restricted SessionGrant；它通过匿名 `ak.open.device_pairing.command.stage.v1` 取得二维码/手动码，并把同一 pairing payload 通过二维码、手动复制或等价带外通道交给一台由用户选择的旧设备。匿名 stage/resolve/status 在授权前始终 account-less，不得绑定或返回 principal、sibling device 集合，也不得允许新设备调用任何 `/_arkret/self/*` surface。只有 step 5 的 authorize Event 已 durable accepted、新设备出现在 current durable device list，且重新认证取得 AccountHandoff 后，才能用 accepted-device proof 换取 Standard grant。在此之前 MUST NOT 读取 E2EE history、解锁 key backup、发送或接收 `ak.secret.request/send`。带外 pairing 确认只允许进入授权确认，不构成 secret-transfer 例外。
3. 已授权设备扫描或打开带外 pairing payload，按 [`device-lifecycle.md` §2.1.1](../crypto-media/device-lifecycle.md) 调用匿名 body-only resolve，独立重算并验证 唯一 `device_pairing_target_proof`，然后显示 requesting-device metadata、key fingerprint、完整 pairing code 与 `gate_audience`。用户必须把 code 与新设备屏幕逐位比较并显式确认。新设备在本步骤不得发送任何 to-device 消息；已授权设备的选择由带外交付动作完成，不存在 fresh-device sibling target discovery。
4. push 或 to-device 通知不是本 bootstrap 的一部分，也不得承载 token、pairing code、target proof 或 sibling device 列表。部署若在已认证账号边界内提供额外的脱敏唤醒，只能作为可选 UI 提示，不能替代步骤 3 的带外交付、验签和人工确认，也不能给予新设备任何账号能力。
5. 用户在已授权设备上逐位核对 pairing code 并批准后，该设备先验签 `device_pairing_target_proof`、从中取出 `hpke_key` 与 `algorithms`（MUST NOT 从服务端响应或 UI 输入取），据此对完整 `ak.device.authorize` payload 签署 Event Initial Submission，再调用 `POST /_arkret/gate/account/device-pair`，提交 transcript 绑定的 `pairing_code`、`new_device_pubkey`、payload 内 exact `hpke_key`、exact `device_signature`、完整 `authorize_event` 与当前设备 fresh proof；challenge digest 的重建规则见 [`device-lifecycle.md` §2.1.2](../crypto-media/device-lifecycle.md)，target `device_signature` 的 `accepted_device` possession domain 与签名对象见 [`device-lifecycle.md` §5.2](../crypto-media/device-lifecycle.md) §5.2.2。服务端必须按普通 Event admission 接受该 exact submission，不得自行 mint Event 或直接写 device projection。`/_arkret/self/devices/pairing-requests*` 不是 v1 core approval surface。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->
6. Events API / identity registry durable 接受并传播 `ak.device.authorize` 与 `ak.device.list_update`；gate 返回 `authorized_event_ref` 或等价引用。新设备可通过 [`device-lifecycle.md` §2.1.1](../crypto-media/device-lifecycle.md) 的匿名 status、重新签发/升级后的 session grant、或后续 account subscribe/device list baseline 观察结果，但 MUST 以 durable device list 为准；只有观察到该 exact authorize Event 已进入 current durable device list 后，才可发送 `ak.secret.request`、开始同步 Event history、Realm membership 和必要的 MLS Welcome / key share。

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
    "authorization_event_id": "ak:event:AUTTW11VHiB1CyE9I304vg0i43r0udn-PTMgwXCFGYrG",
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
`holder_binding.kind="agent_runtime"` 与 `holder_binding.kind="minimal_metadata_pairwise"` 时
`device_binding` 禁带，这两类 holder 的完整 endpoint 身份只落在各自分支内（pairwise 分支见 §6.5）。
current-v1 不存在缺 `device_binding` 的
fresh-device human grant。恢复完成在核验 replacement device 后直接签发同一种 Standard grant，不存在临时
恢复凭据类。因而修改任一 binding 必须改变 canonical preimage、digest、grant ID 与 `jti`；verifier 不得把
binding 当作不参与 ID 的附加 metadata。

`session_public_key` MUST 先解析为受支持且不含 private member 的 public JWK，再编码为 RFC 8785 JCS
UTF-8 字符串；JWT claim 自身必须携带该 canonical 字符串。接收方重新解析并序列化后若不能逐字节得到
相同字符串，MUST 拒绝。`audience_id` 的 canonical 形态是目标 resource service 的稳定 `did_core_id`，
与 `SessionGrantRequestProof.audience_id`、issue/refresh outcome 的 typed `DidCoreId` 相同；HTTP origin / endpoint URL
由 DPoP `htu` 单独绑定，MUST NOT 写入 SessionGrant `audience_id`。该选择与 SDK 的 `DidCoreId` wire type及 Account
Authority 对 non-DID audience 的 fail-closed 校验一致。preimage 不含独立顶层 `device_id`：human device
绑定由 required `holder_binding={kind="human_device",device_binding}` 表达；Agent runtime 与
minimal-metadata pairwise endpoint 绑定由各自对应的
`holder_binding` 分支表达。operation `scopes[]` 只承载授权求交后的服务操作，不得再编码设备身份或旧
`session.bind` 哨兵 scope。

除固定 `schema`、固定 credential `kind` 与派生结果 `jti` 外，preimage 的每个字段都 MUST 是 JWT 的
signed claim。**issuer 侧**在签发与 refresh 时 MUST 自建该 canonical immutable preimage、`issuance_nonce`、
digest 与 typed ID，并把完整凭据与 grant 状态原子写入 issuer ledger（§6.2）；exact issue/refresh replay 合同不变。
**资源服务（Station）侧**不重建该派生：它 MUST 在预先绑定的 Account Authority 通道上提交**完整 token** 与目标
`audience_id` 做内省，由 issuer ledger 以 exact credential 命中并返回权威元数据，再据此判定授权。资源服务
MUST NOT 把本地 JWT 验签、issuer DID 历史回放或 preimage/digest/`jti` 重算当作授权依据，也 MUST NOT 以 `jti`
或任何 ID 命中替代 exact token 绑定；依赖不可达或响应不完整 MUST fail closed，不得解释为 active。仅验证
`ak:session_grant:` 外形同样不构成有效验证。客户端始终把该 JWT 当作不透明凭据，本条不改变 SessionGrant
的凭据格式。该 ID 的 `id_form=suite_tagged_full_digest`，是 33-octet `uint8 digest-suite wire code ||
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

### 6.5 Minimal-metadata pairwise endpoint 会话绑定（normative）

[`../crypto-media/encryption-and-audit.md` §2.7](../crypto-media/encryption-and-audit.md) 的 Realm-local
pairwise endpoint 不建立 account、Device 或 Agent，因此它没有自己的 account↔principal binding，也不能取得
独立 SessionGrant。当该 endpoint 需要在其 hosting Station 上执行 endpoint-scoped 的认证读取（v1 唯一消费者是
[`../sync/server-trusted-results.md` §5.2.1](../sync/server-trusted-results.md) 的 Welcome 引用发现）时，
MUST 使用本节的第三个 Standard holder 分支：同一个 Account/Station 会话在签发时额外证明它当前持有该 exact
pairwise endpoint 私钥，issuer 把该绑定冻结进 signed grant。仅持有普通账号 session、Realm current membership
或 controller 身份都不能证明该控制权，服务端也不得由 transport session actor 推断。

请求分支为 `PairwiseEndpointSessionGrantRequest`，body 固定
`{request_id,principal_id,device_id,audience_id,accepted_device_possession_proof,pairwise_endpoint_possession_proof}`；
账号侧授权载体与 returning human 完全相同：`Authorization: DPoP <account_handoff_grant>` 加匹配 DPoP 与
`ak.session_grant_accepted_device_possession_proof.v1`，origin current-device gate 必须返回 `allow`，
`authority_mismatch | revocation_pending | revoked | generation_mismatch` 一律零 grant。账号侧 gate 不因
pairwise 分支放松，pairwise 侧证明也不替代它。

`pairwise_endpoint_possession_proof` 使用 `ak.session_grant_pairwise_endpoint_possession_proof.v1`，canonical
签名输入为 `utf8("ak.session_grant_pairwise_endpoint_possession_proof.v1\n")` 加该对象删除 `signature` 后的
RFC 8785 JCS bytes，由 `verification_method` 所指 `did:key` 私钥签名，signature 是 64-byte raw Ed25519 的
canonical unpadded base64url。它绑定 `request_id`、完整 `account_id`、`realm_id`、完整 pairwise `actor_id`、
`audience_id`、holder JKT、canonical immutable session intent 与最多 300 秒时窗。Account Authority MUST 校验：
`request_id`、`account_id`、`audience_id`、`holder_jkt` 与 `session_intent_digest` 与本次请求逐字一致；
`actor_id` 是 `kind="account"` 分支且其 `account_id.principal_id` 为 `ak:did_core:key:` 形态；
`actor_id.account_id.station_id` 逐字等于 `audience_id`，即该 endpoint 的 hosting Station；
`verification_method` 是 exact `did:key:<multibase>#<same multibase>` DID URL，其 controller 经已登记 adapter
投影后精确等于该 principal 分量，投影不符 MUST 返回 `verification_method_principal_mismatch`；签名以同一
multibase 展开的 Ed25519 公钥验证，失败 MUST 返回 `proof_invalid`。Account Authority MUST NOT 为此查询 Realm
成员、目录或 MLS 状态：它只判定"当前持有"，不判定 Realm affinity 的当前有效性。

签发结果的 `credential_class` 仍为 `standard`，`proof_kind` 为 `pairwise_endpoint_proof`，`holder_binding`
恰为 `{kind="minimal_metadata_pairwise",realm_id,actor_id,verification_method}`，顶层 `device_binding` 禁带。
`account_id` 仍是发起会话的真实 Account/Station，MUST NOT 被替换成 pairwise principal，Account Authority 也
MUST NOT 为 pairwise principal 铸造账号。该 grant 不可 refresh：`SessionGrantRefreshRequestBody` 的两个分支
分别要求 predecessor 的 human `device_binding` 与 Agent runtime lifecycle，本 holder 两者都不满足；过期后必须
以新的 possession proof 重新 issue，这也是"当前持有"判定的新鲜度上界。

Station 在每个受保护请求的 admission 中 MUST 重新判定当前持有与撤销，任一项失败即 `unauthenticated` 且
fail closed：grant 经 issuer ledger 内省仍为 `active`；`holder_binding.realm_id` 所指 Realm 在本 Station 上
当前可见；由完整 `actor_id` 定址的 `ak.component.member.state.v1` 当前为 active join；该 actor 在当前 winning
epoch 恰有一条 active LeafNode，其 BasicCredential identity 逐字等于 `actor_id.account_id.principal_id` 的
UTF-8 bytes，signature key 逐字等于 `verification_method` 展开的 raw key。leaf 被移除或替换、零匹配或多匹配、
membership incarnation 变化、method 变更与 Realm 不可见都使该 grant 对该 endpoint 立即失效；Realm membership
本身、controller、默认设备或 transport session actor 都不得补足这项证明。

该 pairwise holder binding 只在 issuer 与 hosting Station 之间承担认证职责。它 MUST NOT 被投影进 Realm state、
roster、目录、federation 载荷、push payload 或任何 peer 可见面，也 MUST NOT 被用来聚合同一账号的多个 pairwise
endpoint；§2.7 对 Realm 及其它成员的不可关联性照旧成立。消费该 holder 的封闭 endpoint-scoped 读取请求 MUST NOT
因此新增 proof 字段，也 MUST NOT 由 controller 或其它设备代领该 endpoint 的读取窗口。

## 7. 密钥备份

### 7.1 备份内容

`backup_kind=mls_history` 的一个 object MUST 只属于一个
`content_scheme=mls_exporter_aead_v1` effective scope。Public `contents` 只包含一个
`history_secret_ranges` index（exact scope 与 ranges）；解密后的
[`key-backup-plaintext.schema.json`](../../artifacts/schemas/key-backup-plaintext.schema.json) items 只包含 packed
`HistorySecretRange {from_epoch,to_epoch,secrets_b64u}`。Decoded bytes 严格等于按 epoch 升序拼接的 secrets，总长
`(to-from+1)*KDF.Nh`；suite 必须从 receipt-bound 认证的 exact winning transition 解析（治理结果消费 Station按 cbs-profiles §9，不重放完整控制历史），不得在 backup 自报。
每个被写入的 secret 必须是本 endpoint 从已完整验证并实际应用的 MLS state 直接导出的 `local_authoritative` 项。History response、
RHRK open 或其它外部 carrier 收到的 candidate 即使已成功解密某个 Event，也不得写入 portable backup；它只能留在 device-bound
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
2. 用户输入 Recovery Key（24 词助记词，§3.3），或按 recovery policy 完成 `device_quorum` / `trusted_recovery_service` / `did_root` 授权；仅当目标是 `passphrase_kdf` envelope 时才输入对应口令（§7.5.1）。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `ak.device.authorize`。
6. 若涉及 E2EE Realm，客户端拉取 MLS state 并处理 epoch 缺口。

恢复 device key 时 MUST 生成新的 device key，不得把备份中的旧设备身份克隆到新设备。fresh device 的 active MLS membership 只能由该设备自己的 accepted authorization、新 KeyPackage 与 accepted Welcome/Commit 建立；portable history material 只能进入 history-only decrypt lane，不能提供 Commit/application signer。恢复出的账户级非身份 secret 只能恢复其声明用途；不得用于克隆旧设备身份或绕过 pairing/re-anchor。

same-endpoint crash resume MAY 使用**设备本地 MLS 检查点**（device-bound、不可移植的 active MLS state；类型词根 `mls_local_checkpoint`），但 record principal/device 必须与当前 endpoint 完全相同、PCR device 仍 current、scope/group/epoch/ref 不回滚。该检查点不得上传进 human `mls_history` backup，也不构成任何可被他方验证的证明——它与 Realm 状态快照、Agent 权威状态证明是三个不同对象，MUST NOT 因共用「快照」一词而互相代入。foreign-device 的 active install/send MUST 拒绝。

### 7.3.1 Account MLS root 与 durable recovery unit（normative）

只有经验证的账号首次 enrollment 显式 API MAY create account MLS root。root 必须先 durable commit，或与首个依赖 snapshot 原子提交，之后才能生成任何依赖密文。其它 account-data、saved content、file transfer、MLS bootstrap/join 与普通 feature API 只能 load existing root；缺失时返回 `recovery_required` 并走既有 recovery/pairing，MUST NOT 隐式 mint replacement。

wrapping root、加密 snapshot、`group_state_refs` 与 genesis/commit emitted marker 构成一个 durable recovery unit：必须同一事务提交，或使用 durable-first + 启动交叉验证达到等价原子性。marker 声称材料存在而 root/snapshot/ref 缺失、epoch/ref 回滚或材料解不开时必须进入 `recovery_required`；不得在相同 derived group id 下重铸另一棵 tree。account-data、设备本地 MLS 检查点与 history backup 继续使用独立 HKDF subdomain。

设备授权、账户 root 恢复、该设备的 MLS 入群与旧历史恢复是不同阶段。配对授权成功或签发 SessionGrant MUST NOT 被解释为账户 root 已转移；客户端不得以重复配对代替缺失的密钥恢复。已有合法 session 可以继续使用不依赖缺失 root 的功能；若允许用户推迟恢复，UI MUST 明确指出缺失 root 也会阻止依赖它的新加密写入与本地 MLS 状态持久化，不能仅宣称旧历史不可读。账户 root 恢复成功也不授予 MLS 成员资格，仍须验证该设备自己的 accepted Welcome/Commit 后才能发送。

### 7.4 所有权证明与解密证明

DID 控制权证明 SHOULD 优先使用签名挑战，而不是“能解开某段历史密文”：

- 当前控制密钥、已授权 device key 或 recovery key 对服务端 fresh challenge 签名。
- 新设备生成 device key 后，由当前有效设备或 recovery policy 签发 `ak.device.authorize`。
- recovery service 在 DID Document、organization policy 或 recovery policy 中被明确声明，并签发可验证 recovery event。

“能解密用某个公钥加密的数据”MAY 作为恢复流程中的一个密码学因子，但不得单独等同于账号所有权。允许的形式是：服务端生成短期随机 challenge，按当前 key-log / recovery policy 指定的 recovery public key 加密，客户端在本地解密后对 challenge transcript 签名或返回 proof。该流程 MUST 绑定：

- `challenge`
- `audience` / `origin`
- `service_id`
- `account_id`（完整 AccountId；method adapter 仅把 verification method 投影到其 `principal_id` 分量，Station 分量由已接受授权独立绑定）
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

`auth_data.verification_method` 必须是 DID URL：其 bare `did` 经已登记 method adapter 投影必须等于
`actor_id.signing_principal_id()`，fragment 必须等于 `device_id`；不得把完整 `actor_id` 或其 principal
分量直接拼接 fragment。完整 Account/Station 身份 MUST 独立取自已接受 authorization 并与 envelope
`actor_id` 逐字绑定；仅凭 DidUrl 不得定位账号。`device_authorize_event_id` 必须解析为该 device 在 envelope
frontier 的 accepted authorization。Verifier
KeyPackage 对外 claim 不携带 PCR/device history sidecar。账号当前所在的 source Station 在本地检查 registration、generation 与 revocation 后签发承载该 KeyPackage 的 claim；普通 Event federation receiver 独立验证 Event 的唯一 producer proof、其 `signer_resolution_evidence_ref` 闭包与签名时携带的 `auth_context.authority_refs`，不依赖 source 或账号原站在线。

### 7.5 Recipient Method Profiles

`ak.schema.key_backup.v1.encryption.recipient_method` 枚举 3 种 envelope 解锁方式。每种方式 MUST 按下列 normative 约束实现；服务端遇到本节未定义的 `recipient_method` MUST fail closed。

#### 7.5.0 `backup_kind` × `recipient_method` 合法组合矩阵（normative）

`backup_kind`（仅 `secret_storage` / `mls_history` 两类，§7.1）与 `recipient_method` 的组合不是自由叉乘。下表是合法组合的**集中**声明；producer MUST NOT 写入标 `forbidden` 的组合，receiver / 服务端遇到 `forbidden` 组合或本表未列出的组合 MUST fail closed（reason 见各格），即作为兜底也不允许：

| `backup_kind` ＼ `recipient_method` | `passphrase_kdf` | `recovery_public_key` | `secret_storage_key` |
| --- | --- | --- | --- |
| `secret_storage` | allowed（见 §7.5.1）: §7.2 / §7.5.1 Argon2id 或显式 degraded PBKDF2；新创建 envelope 满足 §7.2 机器下限 | allowed（新写入 SHOULD 优先，见 §7.5.1） | allowed: 仅现有持有 root key 的设备本地缓存/同步，新设备 MUST NOT 直接 bootstrap，否则循环依赖 |
| `mls_history` | forbidden: `mls_history_passphrase_forbidden` | allowed：MUST 带签名覆盖的 `recovery_policy_ref` | allowed：释放仍以 active-series record / frontier_ref / Realm-MLS 授权 / 设备状态为准 |

集中要点（与下列 §7.5.1–§7.5.5 的分散规则一致，本表为 normative summary）：

- **`passphrase_kdf` 仅 `secret_storage`**：`mls_history` MUST NOT 使用 `passphrase_kdf`，即便作为 fallback 也不允许（单一口令不得直接解锁 MLS 历史）。需要口令参与时，口令只能先解锁 `secret_storage` root、recovery private key 或 hardware wrapper 的本地保护层，再由 `recovery_public_key` / `secret_storage_key` 完成对应 `backup_kind` 的释放。
- **recovery 私钥释放强度（normative 澄清）**：本矩阵在 envelope 层禁止 `mls_history` 用低熵口令派生（`passphrase_kdf`），确保 E2EE 历史不被单一**低熵**口令直接控制。recovery **私钥本身**的释放强度由 §8 recovery policy 的 `methods[]` 决定：当 policy 仅配置单个 `recovery_unlock`（单把高熵 24 词助记词签名）时，恢复强度即等同于该单一高熵助记词——这是 v1 default profile **有意接受**的取舍（高熵单因子 ≠ 低熵口令）。高价值 / 组织账号 SHOULD 改用 `device_quorum`（多设备门限）或 `trusted_recovery_service`（产品完成自己的身份核验后签发受限恢复授权），并 MAY 设置 §8.1 的 `cooldown_seconds`；新增独立 OR method 不提高其它方法的门限，不得将多个可替代方法误当作多因素叠加。
- **`secret_storage_key` 不可 bootstrap**：新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap，必须先用 `passphrase_kdf` 或经 recovery policy 释放的 `recovery_public_key` 解出 root secret storage key（消除"新设备能解 wire envelope"的循环依赖）。
- **恢复授权属于 recovery policy 层**：`device_quorum`、`trusted_recovery_service` 与 `did_root` 可以保护 recovery private key 或 secret storage root 的释放，但不得作为 `ak.schema.key_backup.v1.encryption.recipient_method`。v1 没有 share、holder 或 hardware-module 分支；相关 proof transcript 由 §8 recovery policy 与 `ak.schema.recovery_session.v1` 约束。
- 所有 fail-closed 判定 MUST 在解密尝试之前完成；服务端 / receiver 不得对 `forbidden` 组合"先解密再检查"。

#### 7.5.1 `passphrase_kdf`

参考 §7.2：Argon2id（或显式 degraded PBKDF2）派生 root key，HKDF 派生 `commitment_key` 与 `nonce_key`，AEAD AAD 覆盖全部 envelope metadata。`passphrase_kdf` 仅用于 `secret_storage` envelope；`mls_history` envelope MUST NOT 使用 `passphrase_kdf`，即使作为 fallback 也不允许。需要用户口令参与 MLS 历史恢复的实现 MUST 让口令先解锁 `secret_storage` root、recovery key 或 hardware wrapper 的本地保护层，而不是在 wire 上发布 `backup_kind="mls_history", recipient_method="passphrase_kdf"` 的 envelope。

**与 recovery secret 的关系（normative）**：内容恢复的标准用户凭证是 §3.3 recovery secret；它经固定域派生 backup-HPKE key。实现 SHOULD NOT 引入独立 vault 口令作为标准凭证。

- 新写入的 `secret_storage` envelope SHOULD 使用 `recipient_method="recovery_public_key"`（加密给 §3.3 backup-HPKE public key）；`passphrase_kdf` envelope MAY 用于实现自选的口令派生场景。
- `passphrase_kdf` 是合法 wire `recipient_method`：服务端 key-backup 端点（§7.8、[`../crypto-media/device-lifecycle.md` §12.1](../crypto-media/device-lifecycle.md)）不区分凭证来源，`passphrase_kdf` envelope MUST 可被列出、读取与删除，本节与 §7.2 的 KDF / nonce / commitment 约束对其适用。

#### 7.5.2 `recovery_public_key`

DEK 通过 HPKE（base mode）加密给 `recovery_public_key`：

- `recipient_key_ref` MUST 是 envelope 的 `recovery_policy_ref` 所指 accepted recovery policy（§8）中 `methods[kind=recovery_unlock].keys[].backup_hpke.key_agreement_ref`。DID Document-only `recoveryKeyAgreement` 不是授权源，MUST reject。该 ref MUST NOT 指向 method signing entry 的 `verification_method`：后者只标识 recovery-proof 签名 key。receiver 必须从同一 policy entry 取得 X25519 `public_key_multibase`，并确认 `encryption.hpke_suite` 在该 entry 的 `hpke_suites` 中。
- HPKE suite MUST 是 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active 行，由 `encryption.hpke_suite` 选定；该字段缺省时 MUST 解释为 default-MUST 行 `ak.hpke_x25519_aead_chacha20poly1305.v1`。`aead.name` MUST 等于所选 suite 的 AEAD。遇到未登记、非 active 或 reserved-未激活的 suite id，receiver MUST fail closed（`unsupported_hpke_suite`），MUST NOT 自由组合未登记的 KEM/KDF/AEAD，也 MUST NOT 仅凭 `aead.name` 推断 suite 参数。P-256 KEM 互操作经 profile-gated 行 `ak.hpke_p256_aead_aes256gcm.v1`（`ak.profile.hpke.p256.v1`）提供。HPKE 单发 base-mode 由 key schedule 内部派生 AEAD nonce，故 `recovery_public_key` envelope 不携带 wire `nonce`。
- HPKE `info` MUST 包含 `canonical_json({backup_id, series_id, series_seq, actor_id, backup_kind, backup_version, created_at})`；HPKE `aad` MUST 等于 envelope 的 AEAD AAD。
- 普通 DID root generation 轮换不改变 backup-HPKE key。只有 recovery secret handoff 才改变 recipient key；handoff 后所有 active backup class MUST 按 §3.3 建新 series/重封装并推进 signed active-series pointer。
- 任何 `recipient_method="recovery_public_key"` envelope 都 MUST 携带 `recovery_policy_ref{policy_id, policy_version}`；它作为实际存在的顶层成员自动进入 §7.2 的完整 envelope 签名转录。`recipient_key_ref` 只在该 accepted policy 的 method 内联 `backup_hpke` 中解析。各 backup class 在读取/恢复时 MUST 验证 referenced policy 仍属于该 principal 的 accepted policy history，并按 active-series 与轮换规则拒绝回滚。不匹配 MUST `recovery_policy_mismatch`。这项 policy 绑定不替代 MLS 历史或 secret-storage 的独立授权判断。
- **备份接收 key 的角色隔离（normative）**：wire 名称 `recovery_public_key` 指 §3.3 派生的 X25519 backup-HPKE public key。它与 Ed25519 recovery-proof key、任一代 identity root 是不同 key，但三者来自同一用户 recovery secret。实现 MUST NOT 在 `secret_storage` 中再制造第四把长期 backup keypair，也不得把 Ed25519 key 转换成 X25519 key。

recovery policy 的 signing entry MUST 内联独立 `backup_hpke` entry：`recovery_unlock.keys[]` 是 v1 唯一携带 backup-HPKE recipient 的 method entry，recipient ref 唯一解析到其中的 `backup_hpke.key_agreement_ref`，不得跨 method 猜选。HPKE entry 的 use 固定为 `backup_hpke`，只能接收备份，不能验 recovery proof 或授权 DID/Event。向量 `ak.vector.identity.recovery_key_role_separation.v1` 验证这些独立角色。所有内联材料进入完整 policy 签名；悬空/重复 ref、同一 signing/HPKE material、suite 不匹配、已撤销/过期或 DID Document-only 旁路均 fail closed。

#### 7.5.3 `secret_storage_key`

仅用于已经持有 `secret_storage` root key 的现有设备本地缓存/同步（不是 bootstrap）。

- `recipient_key_ref` MUST 命名一个已经在该设备 device-local secret storage（参见 `crypto-media/device-lifecycle.md` §11 `ak.secret_storage.v1`）中存在的 key id（例如 `mls_group_secrets_backup_key`）。
- 当 `backup_kind="mls_history"` 使用 `secret_storage_key` 时，envelope MAY 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 作为恢复流程 hint；若出现，它自动进入 §7.2 的完整 envelope 签名转录，receiver MUST 验证它与当前 accepted recovery policy 一致。MLS 历史材料的释放仍以 active-series record、frontier_ref、Realm/MLS 授权与设备状态校验为准。
- 新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap：它必须先经 recovery policy 接受 recovery proof，再由用户 recovery secret 派生 backup-HPKE private key以打开 `recovery_public_key` envelope，之后才能拉取 `secret_storage_key` envelope。
- 这是为了消除"新设备能解 wire envelope"的循环依赖。
- **AEAD nonce 唯一性（normative）**：`secret_storage_key` 是长期复用的对称 wrap key，因此 `aead.nonce` MUST 在该 `recipient_key_ref` key 的整个生命周期内对每条 envelope 唯一——producer MUST 为每条新 envelope 生成至少 96-bit 的随机 nonce（或在该 key 下严格单调不回绕的 counter），且 MUST NOT 用同一 (`recipient_key_ref` key, `aead.nonce`) 对写第二条 envelope；需要更新内容时 MUST 生成新 `backup_id` 与新 `nonce`，并 SHOULD 轮换底层 wrap key。`nonce` 作为 `encryption.aead` 成员自动进入 §7.2 的完整 envelope 签名转录，并进入 AEAD AAD。该约束与 `passphrase_kdf` 的 `nonce_salt` deterministic derivation（§7.5.1）、`recovery_public_key` 的 HPKE 内部 nonce 派生共同关闭三种 `recipient_method` 的 nonce-reuse 面。

#### 7.5.4 恢复授权因子不是 recipient method

`ak.schema.key_backup.v1.encryption.recipient_method` 的封闭枚举只有 §7.5.1–§7.5.3 三项。recovery policy 的 `methods[]`（`did_root` / `recovery_unlock` / `device_quorum` / `trusted_recovery_service`）是 policy 层的解锁因子，MUST NOT 出现在 `recipient_method` 位置；`threshold_recovery`、`hardware_wrapped_key`、`device_snapshot_secret` 既不是 v1 recovery method 也不是 v1 recipient method，receiver / validator MUST fail closed。

- 恢复授权在 policy 层完成后才释放 recovery private key 或 secret-storage root，客户端随后用 `recovery_public_key` 或 `secret_storage_key` 解开 envelope；授权本身不解密任何 envelope。
- 释放出的 recovery secret、PRK 或任一派生 private key MUST NOT 写入在线持久化存储；上下文在用途结束后立即清除。
- v1 不定义份额、持有者释放、可验证秘密共享或再分享编排。产品若在自己内部使用多方审批或份额保护，最终 MUST 以 §8.2 的单一恢复授权进入协议；协议不接收也不校验这些内部材料。

#### 7.5.5 硬件本地保护层

v1 core 不把 `hardware_wrapped_key` 作为 `ak.schema.key_backup.v1.encryption.recipient_method`，也没有独立 hardware recovery method。HSM、TPM 或 Secure Enclave MAY 在本地保护既有方法使用的 recovery secret、backup-HPKE key 或 secret-storage root；该本地保护不产生新的 policy authority，也不改变 `methods[]`、门限或签名验证规则。

- closed recovery policy 不接受自定义 hardware profile、wrap key id、hardware holder 或 attestation 字段；不得以这些字段、任意 `did:key` 或“硬件已解锁”的本地标记满足恢复授权。v1 没有 `attestation_required` 之类的可配置外观，实现 MUST NOT 复活它。
- `recipient_method=hardware_wrapped_key` MUST 被 schema/receiver 拒绝为未知枚举值。未来若引入可互操作的硬件证明，必须先定义签名原像、session/challenge 绑定、受信 profile、key identity、验证与失败合同，再登记对应能力；v1 不承诺可配置该能力。

#### 7.5.6 Agent PCR history-only backup（normative）

Conformance vector：`ak.vector.agent.pcr_history_backup.v1`。

`mls_history` wire 是 history-only exporter secret backup；无论 ordinary human、Agent 或 Agent PCR，均不得携带
`mls_group_state`、`mls_epoch_secret`、`pending_welcome`、leaf signer、ratchet、proposal、sender counter 或设备本地 MLS 检查点。
Controller-owned backup 不能成为跨 principal 的 active-state exception，也不能把 Agent PCR active MLS private state 混入 controller
自己的 series。`managed_principal_binding`、`managed_frontier_ref` 与 `agent_pcr` backup subdomain 不属于 v1 wire。

Agent 或其 controller fresh endpoint 恢复时，只能安装 schema 允许的 history-secret ranges；这不会恢复 active leaf、runtime
signer、counter 或 current group state。Fresh endpoint 必须按当前 authorization 重新生成 runtime key，并经标准 KeyPackage/
Welcome/Add 进入唯一 derived group；同 endpoint crash-resume 若使用**设备本地 MLS 检查点**，只属于 §7.3 的本地不可移植状态，
不得上传。Pairing admission 只验证当前 controller/Agent authority、proof-of-possession 与 accepted control frontier，不得要求一个 wire
上无法承载的 `pcr_recovery.status=ready` active-snapshot gate。

### 7.6 Backup Series & Freshness

每个 `(actor_id, backup_kind)` 的 series 使用严格递增 `series_seq` 与 digest-bound `supersedes_id` 链。Active-series record 必须由当前 accepted device 签名，签名输入固定为 `RFC8785_JCS(record 删除 auth_data.signature)`；闭合 record 的全部实际存在成员自动受认证，不携字段名清单。record 携带其 `device_authorize_event_id`，并以整数 `frontier_ref.device_generation_ref` 绑定 current generation。服务器在 accepted PCR 状态中验证 pointer 的单调性、签名、generation 与分支，拒绝回滚、fork 和链缺口；普通客户端使用下述自己 Station 的当前指针结果，不验证 PCR 历史或要求列表携 completeness/witness evidence。

#### 7.6.1 自己 Station 的 active series 与有界列表

`ak.self.keys.backups.read.list.v1` 的 `KeysBackupsList` 按 `backups, active_series, next_cursor?, has_more` 排列。
`active_series` 是必填 `BackupActiveSeriesState`，按 `account_id, control_realm_id, seal_basis, secret_storage, mls_history`
排列，绑定本次已认证完整 AccountId、其 PCR 和完成当前指针判断的 已确认 basis（每 Realm 恰一个 head）。两个 backup class 始终全部返回，
不受 series_id/backup_kind 过滤、当前页有无 envelope 或 envelope 的过期/删除影响。

每个 class 的 `BackupActiveSeriesPointer` 为 closed 分支：`{state:"absent"}` 或
`{state:"active", active_series_id, series_pointer_version}`。active 来自该 basis 已接受的
exact `ak.key_backup.active_series` cell，pointer version >=1；basis 和 class 足以定位结果，不额外携带历史证明或 Event 清单。absent 只表示服务器已完成该 basis 的求值且没有指针；
未验证、缺依赖、安全确认故障、PCR 不可用必须使请求返回 frontier_unavailable，不得以 absent、空列表、字段省略或 null 掩盖。

普通客户端 MUST 信任本次自己 Station 的结果，检查账号、PCR 与结果形状；不得下载 PCR 闭包、历史 DID、签名清单或独立
witness 来重建 active 指针。不得把唯一可见 series 猜成 active，也不得由列表到达次序、最大 seq 或 created_at 选出 active。
首次初始化仅在对应 class 为 absent 时准备 version=1 的已签 CAS；并发指针出现后必须重新读取，不能改写已签 intent。
active series 不在当前页不表示它不存在。旧设备上传的“验证标记”不是本结果的来源。

list 默认 limit=50，允许 1..200；完整响应 canonical bytes 上限 1 MiB。服务端按 backup_kind、series_id 的 canonical
UTF-8 字节序，随后 series_seq 数值、backup_id canonical 字节序升序分页。范围、排序和 limit 必须下推到有界存储读取，
不能先读取全部 envelope 再截断。has_more=true 必须给 next_cursor，false 禁止给 next_cursor；超过单项字节上限返回
limit_exceeded，不返回不完整 metadata。客户端只在分页完成后声明目标范围完整，不以部分页缺项删除本地状态。

cursor 是自己 Station 签发的 opaque 列表位置，绑定 operation、完整账号、过滤条件、排序和服务端列表修订及 active 指针
状态。跨账号/operation/过滤条件、篡改、已失效修订必须拒绝为 cursor_invalid；不能退化成从头页并报告 continuation 成功。
列表内容或 active 指针改变可使旧 cursor 失效；客户端重新读取目标过滤范围。每页仍执行当前设备/账号读取授权，缓存命中
不豁免撤销。分页不要求持有所有历史治理状态，也不使账号导航等待所有备份页。

恢复只读取所需 active series 的 metadata 页与确切 envelope；备份链、signed envelope 用户/recipient 绑定、HPKE/AEAD
和密文 digest 认证仍在端到端客户端完成。服务器确认治理可用性不表示它读取或认证了加密明文。

### 7.7 Recovery UI Requirements（normative）

恢复 UI 是用户唯一能识别"我在恢复一个真实的自己 vs 我在被钓鱼"的界面。实现 MUST：

- 密钥备份解密凭证 MUST 是 Recovery Key（24 词 BIP-39 助记词，§3.3）：由其派生 / 解锁 recovery private key 后按 §7.5.2 HPKE-open `recovery_public_key` envelope；硬件只能作为 §7.5.5 的本地保护层。恢复 UI MUST NOT 要求用户设置独立 vault passphrase 作为标准凭证；仅当目标 envelope 是 `passphrase_kdf`（§7.5.1）时，MAY 提示输入对应口令完成解密，并 SHOULD 在恢复成功后引导写入加密给 recovery key 的新 envelope（§7.5.2，按 §7.6 series 规则开新链或追加）。
- 在尝试解密任何备份 envelope 之前，向用户展示：`backup_kind`、`series_id`、`series_seq`、`backup_version`、`encryption.recipient_method`、`encryption.aead.aead_profile?`（缺省时显示 `aead.name`）、`principal_id`、`device_id`（当前请求恢复的新设备）与 `frontier_ref.device_generation_ref`。
- 在使用 `passphrase_kdf` 时，明确展示 KDF（Argon2id / PBKDF2）与参数；用 PBKDF2 的 envelope MUST 在 UI 中显示 `degraded_profile_reason`，且不得自动选用 PBKDF2 envelope 当 Argon2id envelope 同时存在。
- 在 envelope 携带 `mixed_secret_storage=true` 时 MUST 显著警告"该备份同时保护身份签名与 E2EE 历史，单一口令被攻破将同时丢失两者"；非 `personal_node` profile 下 MUST 直接拒绝展示此类 envelope 作为 primary recovery source。
- envelope 携带 `recovery_policy_ref` 时 MUST 展示当前 envelope 的 `policy_id` / `policy_version` 与当前 accepted recovery policy 的一致性并验证。不一致时 MUST `recovery_policy_mismatch`，并指向"更新 recovery policy"流程而不是默默继续。
- 不得从本地缓存读取用户先前确认的 fingerprint / passphrase / OOB token 跳过当次显式确认。本地缓存 MAY 用于自动补全，但用户 MUST 显式提交本次输入。
- 在 §7.4 列出的禁用证明类型（历史明文、邮箱验证码、撤销设备等）被用户尝试时 MUST 给出可读的拒绝原因。
- **无恢复路径（SPOF）账号的 fresh-device 登录警示**：`active_policy=null` 时 fresh-device recovery MUST fail closed，并提示只能由旧设备确认。存在 policy 时，UI 只展示其已接受 proof kinds；`did_root` 未启用时不得因用户持有当前 DID control 就提供重锚，启用时必须显著披露其接管风险。

### 7.7.1 Backup Unlock Proof 与 Plaintext Keybag（normative）

每次读取并尝试解密 key backup 都 MUST 产出一条 unlock proof，明文 keybag 也 MUST 有固定 schema，避免“能下载密文”被误当作“有权使用解密结果”：

- unlock proof MUST validate as `ak.schema.key_backup_unlock_proof.v1`；签名输入为 `RFC8785_JCS(proof 删除 auth_data.signature)`，闭合分支全部实际存在字段均被认证。公共字段为 `kind/account_id/requesting_device_id/backup_id/backup_kind/series_id/ciphertext_digest/challenge/audience/service_id/issued_at/expires_at/auth_data`。`kind="current_device"` 另携 `challenge_id/nonce`，MUST NOT 携 session id，由 exact AccountId 当前 accepted、active、未撤销且 generation 匹配的设备 identity key 签署。`kind="recovery_session"` 仅另携 `recovery_session_id`，由 session 创建时冻结的 `requesting_device_public_key_did` 对应 replacement identity key 签署，MUST NOT 使用恢复因子 key。恢复分支的 challenge、audience/service、有效期与完整 AccountId/device 必须精确匹配该 verified、未过期、未完成、未撤销 session；实际恢复方法只读取其 durable proof_summary，不由 object proof 重报。grant/JKT 必须与冻结 session 相同，不能降级为 bearer 或任意 DID resolver fallback。Completed 后的新设备读取必须走 current_device。
- 取回完整 ciphertext 的协议操作是 `ak.self.keys.backups.command.unlock.v1`（`POST /_arkret/self/keys/backups/{backup_id}/unlock`）：unlock proof MUST 作为 request body 的 `proof` 字段提交（`keys-operations.schema.json#/$defs/keys_backups_unlock_request_body`），path `backup_id` 与 `proof.backup_id` MUST 一致；实现 MUST NOT 用 header、query string 或私有载体承载该 proof。服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed（`recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `signature_invalid`）。
- AEAD/HPKE open 后得到的明文 MUST validate as `ak.schema.key_backup_plaintext.v1`，且其中 `backup_id`、`backup_kind`、`series_id`、`series_seq` MUST byte-for-byte 等于外层 envelope。`items[].secret_id` / `item_kind` 是 keybag 内部路由字段，不得替代外层 envelope 的授权判断。
- 实现 MUST 把 plaintext keybag 限定为本地瞬时处理材料；除非它被重新加密进本地 secret storage，否则不得持久化明文。日志、crash dump、telemetry MUST NOT 记录 `secret_b64u`。

### 7.8 Server-Side Hardening for Backup Access

加密备份的密文虽然不暴露明文，但下载即"投喂 KDF 爆破弹药"。Station device/key surface MUST 对 `ak.keys.backups.*` 接口实施：

- **普通每 principal 每 24h 下载上限**：参数唯一来源是 [`history-recovery-scalability-registry.json#backup_access`](../../artifacts/registry/history-recovery-scalability-registry.json)；默认 `64`，deployment 只可在闭合区间 `[16,64]` 内选择或进一步收紧。该普通桶只覆盖不在 verified RecoverySession 下的下载，不能把一个多 scope 恢复拆成跨日或跨 session 的同一次恢复。
- **普通每 IP 限速**：同一 registry 固定默认 `per_ip_unlock_burst=8`、`per_ip_unlock_sustained_per_minute=4`；deployment MAY 收紧。逾限响应 MUST 是 `429 Too Many Requests`，并 SHOULD 在 `Retry-After` 中给出建议。
- **RecoverySession frozen unlock manifest**：session 原子转为 `verified` 时，Station MUST 以该时点全部 active 且可恢复的 backup object 建立 server-side immutable manifest；每个 exact `backup_id` 与其 series_id/ciphertext_digest 与 canonical response-byte charge 各冻结一次，形成一次独立 allowance，完整 manifest 的 checked-u64 byte budget 等于这些 charge 之和。manifest entry 不计普通 24h 个数桶；manifest 外对象、verified 后才 active 的对象 MUST 拒绝该恢复授权。消费 allowance、扣减 byte budget、保存 canonical request digest/holder 与 immutable result ref MUST 在同一 shared-durable 事务提交，提交后发送 ciphertext。同一仍合法 holder 的 exact replay 返回原对象且不重复扣费；异请求不能复用已消费 entry。失败 proof 不消费 allowance，但计入 session rate/异常审计。双实例、重启和提交后断连不得改变这一规则；历史成功不授予设备或 session 撤销后的读取权。
- **900 秒内可完成性**：RecoverySession 的默认和最长 TTL 为 `900` 秒。verified 后的 recovery 专用速率按 registry 的 `rate_formula` 从 frozen entry 数、实际 `verified_at`、`expires_at` 与 completion reserve 唯一计算，并按 `recovery_session_id` 而非按单次 unlock 或 IP 计；Station 至少提供该速率，且只有在 byte budget、并发和服务能力能于 reserve 前交付完整 manifest 时才可进入 `verified`。此例外不放宽 fresh device proof、逐 object unlock proof、一次性 allowance、byte budget、并发或审计要求。
- **认证降级阻断**：`POST /_arkret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof（与 §7.4 fresh challenge 相同绑定：challenge / audience / service_id / 完整 account_id / key_id / nonce / 过期时间）。bearer token 单独到达 MUST 被拒绝。
- **审计记录**：超出阈值或在异常时间窗内的下载 MUST 写入 `ak.audit.accessed`，`access_kind="key_backup_read"`，并按 `ak.profile.attested_audit.e2ee.v1`（若声明）配对 audit pair。
- **跨 actor 拒绝**：服务端 MUST 在 envelope `actor_id` 与请求 caller 不一致时返回 `forbidden`，并不得通过 metadata 暴露 envelope 是否存在。v1 不定义 controller-owned Agent active-state backup，因此不存在以 `managed_principal_binding` 绕过本规则的例外。
- **删除验证**：active series 内的非尾部 envelope MUST NOT 被单独删除。`DELETE` 尾部 envelope MUST 携带 [`high-risk-authority-proof.schema.json`](../../artifacts/schemas/high-risk-authority-proof.schema.json) 的三分支之一（`recovery_unlock` / `device_quorum` / `trusted_recovery_service`），按 §7.8.1 绑定服务端签发的单次 challenge 并签署 canonical delete-intent transcript，然后写入 `access_kind="key_backup_delete"` 审计。普通 `current_device` proof **不是**该 family 的第四分支：仅持普通 device proof 的 caller 只能删除 `expired_at < now` 且不属于 active series 的旧 envelope，或对已被 active-series record 移出 primary source 的旧 series 发起整组 erasure/retention 删除。设备revoke轮换的整组删除必须使用[`security-transactions.md` §3](./security-transactions.md)登记的transaction-bound operation；普通DELETE outcome不得作为`erase_confirmation_digest`来源。

本轮维持单对象授权边界：有限 exact manifest 的一次身份签名方案尚未闭合 holder、expiry、总预算、逐对象 replay 与客户端意图验证，不能作为部署私有扩权。v1 **不定义 batch unlock**：唯一操作仍是逐 object 的 `ak.self.keys.backups.command.unlock.v1`，每个请求只接受 path 中一个 `backup_id` 及其完整独立 proof。不得发明 collection-level `unlock_batch`、跨对象 proof、partial outcome 或私有批量载体；未来若需要批量协议，必须单独走 AKP。实现 MAY 在 deployment policy 中收紧 registry 允许收紧的阈值；MUST NOT 放宽普通下载上限超过 `64`，也 MUST NOT 把收紧配置用于破坏已进入 verified 的 manifest 在 session 过期前的可完成性。

#### 7.8.1 高风险删除的 challenge 与 canonical delete-intent transcript

freshness MUST 由服务端发放，不得接受 caller 自造 nonce：

1. **challenge 签发**。`ak.self.keys.backups.command.issue_delete_challenge.v1`
   （`POST /_arkret/self/keys/backups/{backup_id}/delete-challenge`，request body 为闭合
   `{request_id}`）返回 durable、单次使用、TTL 不超过 300 秒的 challenge
   （[`keys-operations.schema.json#/$defs/keys_backups_delete_challenge`](../../artifacts/schemas/keys-operations.schema.json)），
   至少绑定 `{challenge_id, challenge, nonce, operation, account_id, backup_id, audience,
   service_id, request_id, issued_at, expires_at}`。同一 `(account_id, backup_id,
   request_id)` 在 challenge 尚有效时 MUST 返回同一 challenge；不同 `request_id` 签发新
   challenge。
2. **唯一 canonical delete-intent transcript**。所有 proof 分支（含 device quorum 中的每一份
   签名）MUST 覆盖同一 canonical bytes：

   ```text
   {
     "context": "ak.key_backup_delete_proof.v1",
     "operation": "ak.self.keys.backups.resource.delete.v1",
     "request_id": <DELETE body request_id>,
     "account_id": <authenticated AccountId>,
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
   audience / service 不同一律 fail closed），再验证 proof 分支的授权（`recovery_unlock`
   必须携带 exact `recovery_session_id`，该 session 必须属于同一 Account、处于 verified 且未完成/撤销状态、
   未过期，其 proof summary 必须为 `recovery_unlock` 并绑定同一 verification method；签名 key 必须从该 session
   冻结的 accepted recovery policy 解析，不能从当前 DID Document 或请求自报 key 取得；`device_quorum` 去重后有效签名数不小于当前 recovery policy 的 `k` 且请求
   `threshold` 等于该 `k`；`trusted_recovery_service` 的 session 必须未过期、未消费且由
   recovery unlock / device quorum 建立），最后在成功删除的同一事务中
   原子消费 challenge。
4. **幂等**。服务端以 `(account_id, backup_id, request_id)` 保存 canonical request digest 与
   terminal outcome：完全相同的网络重试返回已存 outcome，不重新验收已消费 challenge；同
   `request_id` 不同 digest 返回 duplicate conflict。"单次 challenge"与 registry 声明的
   DELETE retry-safe 由此并存。
5. **conformance**。`ak.vector.key_backup.delete_authority.v1` MUST 覆盖：三个 high-risk
   分支的正例、普通 device proof 删除 active tail 被拒、非尾部单独删除被拒、quorum 去重 /
   低于 policy `k` 被拒、`recovery_unlock` 的 session/method/policy 错绑被拒、session 过期或已消费被拒、challenge 重放 / 过期被拒，以及篡改
   `backup_id` / `reason` / `audience` / `nonce` / `context` 任一 transcript 字段后验签必然失败。

#### 7.8.2 普通设备 unlock challenge 与耐久重试

`ak.self.keys.backups.command.issue_unlock_challenge.v1`（`POST /_arkret/self/keys/backups/{backup_id}/unlock-challenge`）使用 closed `{request_id}`；返回 `keys-operations.schema.json#/$defs/keys_backups_unlock_challenge`。服务端从当前 caller 与 immutable 备份记录填入完整 AccountId、requesting device、backup/series/ciphertext、audience/service、challenge_id、challenge、nonce、operation、issued_at/expires_at；TTL ≤ 300 秒，challenge 为 32-byte CSPRNG。不得接受 caller 自造 nonce。相同 `(AccountId,device_id,backup_id,request_id)` 的有效未消费 issuance 返回同一对象；challenge 存储、限额、消费与 exact result ledger MUST 跨实例耐久。

current_device proof 的 challenge_id、challenge、nonce、audience、service、account/device、backup/series/digest 逐字匹配服务端记录，`issued_at` 位于签发窗口，`expires_at` 等于签发截止时间；首次消费必须仍在窗口内。恢复分支复用 session.challenge 与 session.expires_at，不额外调用本接口。两分支均只授权一个 exact object，首次消费与结果引用原子提交；exact replay 仍校验当前 holder authority、对象未被撤销/删除、session 未完成且未过期。服务端不能以只发送 HTTP 成功作为耐久边界。

### 7.9 Algorithm Agility & Forward Compatibility

v1 的备份枚举数量有限，但 envelope 结构需要支持未来 PQ / hybrid 迁移：

- method signing entry 的 `signature_algorithm` MUST 取自 active [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) row 的非空 `raw_signature_algorithm`；v1 机读集合为 `Ed25519`、`ML-DSA-65`。`Ed25519` 是默认 MUST，`ML-DSA-65` 仅在实现声明相应 PQ 签名能力时可签发。`ES256` 只有 JOSE mapping，没有 Arkret raw-signature mapping，因此不得出现在该字段。receiver 不支持 entry 声明的 active algorithm 时 MUST fail closed `unsupported_signature_alg`，不得回退为 Ed25519 或忽略该 recovery key。

- Receiver MUST 对未知 `encryption.kdf.name`、`encryption.aead.name`、`encryption.aead.aead_profile`、`encryption.recipient_method` fail closed（不得回退到默认）。未知或未激活 `aead_profile`（含 reserved 但未发布的 `ak.aead.hybrid_kem.*`）的 reason code 为 `unsupported_aead_profile`；禁止仅凭 `aead.name` 推断参数。
- PQ / hybrid KEM agility MUST 通过 `encryption.hpke_suite` 选择子 + [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 声明，不得塞进 AEAD profile。PQ hybrid（X25519+ML-KEM-768）已在该 registry 预留 `ak.hpke_xwing_aead_chacha20poly1305.v1`（status=reserved，profile `ak.profile.kem.hybrid_xwing.v1`），与 `ak.aead.hybrid_kem.*` 预留 namespace 对齐；只有该 registry row 的 activation requirements 全部满足并翻为 active 后才可出现在 wire 上。`ak.aead.*` 只描述 AEAD 算法、nonce/tag/key 长度和 AAD 构造；receiver 收到把 KEM 语义编码进 `encryption.aead.aead_profile` 的 envelope MUST fail closed。
- 当 `frontier_ref` 携带 `seal_ref` 时，client 可以用 Seal inclusion proof 来证明 envelope 创建时刻不晚于 Seal commit；receiver MAY 在 sovereign / high_security_organization profile 中要求该证明。
- 实现 MUST 在 envelope metadata 中保留 `additionalProperties` 与 `x_*` 前缀作为 forward-compat 扩展槽；MUST NOT 在 wire 上接受未知顶层字段（已由 schema `additionalProperties: false` 强制）。

### 7.10 自动持续备份

账户级非身份 secret、允许恢复的 MLS history 与 encrypted private account-data cache 新增或轮换时，客户端 SHOULD 自动上传相应 envelope并推进 active series。identity root/recovery secret 与 device private key始终禁止自动备份。PCR genesis/re-anchor 后必须立即生成由新 accepted device 签名、绑定 current device generation 的新 series tail。

### 7.11 加密 Realm 创建 / 加入前的 Recovery 前置门（normative）

E2EE Realm（effective `content_encryption_floor` 或 `metadata_encryption_floor` 为 `e2ee_required`，含 PCR 与任何加密协作 Realm）的创建或加入会产生该用户独有的 MLS group secret；若此时账号尚无可用恢复路径，丢失唯一设备即永久丢失这些内容。因此：

- 客户端在 `recovery_state` 未配置（`active_policy=null`）时，发起任何 post-bootstrap E2EE Realm 创建/加入前 MUST 完成 recovery-material gate；PCR bootstrap 是唯一豁免。
- `ak.profile.personal_node.v1` MAY 允许用户在明确告知"丢失本设备将永久丢失该 Realm 内容"后**显式跳过**，并维持 / 标记 `single_point_of_failure=true`、持续提醒；`small_team` 及以上 deployment profile SHOULD 阻断创建 / 加入，直至 recovery policy 配置完成。
- `ak.profile.agent_provisioning.v1` 对 Agent 收紧上一条例外：即使部署同时声明 `ak.profile.personal_node.v1`，controller 没有 accepted **account recovery policy** 时 `ak.self.agent.command.provision.v1` MUST 在产生 Agent DID / PCR / grant 副作用前 fail closed。该门只确认 controller 账户恢复材料已配置，不要求 Agent PCR 的设备本地 MLS 检查点或 `mls_history` ready 状态；runtime pairing 按 current controller/Agent authority 与 proof-of-possession 判定。不得以服务端托管 MLS secret 或为 Agent 生成另一套助记词绕过。
- **加入路径的判定输入（normative）**：invitee 在加入前读不到 membership 门控的 Realm policy 投影，因此加入侧 gate 判定 MUST 只以 `ak.schema.realm_join_candidate.v1` 的 effective `encryption_profile` 为输入（见 [`../discovery/discovery-directory.md`](../discovery/discovery-directory.md) §9.1.1 第 9 条）：`mls_rfc9420` 时 gate MUST 生效。该输入相对本节按 floor 给出的范围是 fail-closed 的超集——MLS-backed Realm 的 effective `metadata_encryption_floor` 缺省即 `e2ee_required`；而 `encryption_profile` 为 `none` / `external` 的 Realm 即使 floor 为 `e2ee_required`，Realm join 本身也不产生 Realm MLS group secret，其加密材料在加入后的 Circle 路径上由已可读状态按同一 gate 判定。客户端 MUST NOT 为该判定读取 membership 门控的 Realm Event 历史。
- 该前置门是客户端编排义务，不替代服务端的 floor ratchet 与 PCR 校验；它针对的是"加密材料先于恢复路径产生"的时间窗，而非加密本身是否启用。

## 8. Recovery Policy

Recovery policy 是 PCR control state。Genesis policy 只能由 founding accepted device 签发；后续 policy 更新由 current generation accepted device 或满足旧 policy 的 quorum 签发，并必须受 version ratchet、accepted Seal 与 generation fence 约束。DID Document 中任意 verification method、账号登录或服务端 transport identity都不能单独授权 policy 更新。

### 8.1 Policy 生命周期

**账号边界（normative）**：recovery policy、proof、session 与 device re-anchor 只恢复其绑定的 exact
AccountId，MUST 遵守 [`common-fields.md` §4.2](../models/common-fields.md#42-主体引用字段)。另一 Station
上相同 principal 的账号、设备授权、PCR 或 session 没有替代效力；持有相同 DID control key 也不产生
跨账号恢复权。显式启用的 DID-root proof 仍须完整满足目标 Account 自己的已接受 policy 与 transcript，
MUST NOT 将其解释为另一账号的权限继承或跨 Station 迁移。原 Station 永久停止服务不提供跨 Station
re-anchor 出口。

Recovery policy 的所有发布、轮换和撤销均进入 PCR control stream。签名设备必须满足 `device_generation_status="active"`、`authorized_generation_ref == current_device_generation_ref` 与未撤销状态；quorum 更新还必须满足旧 policy 的门限和 ratchet：

Policy 签名输入固定为 `UTF8("ak.identity.recovery_policy.signature.v1\n") || RFC8785_JCS(policy 的全部实际存在顶层成员，排除 auth_data)`。schema 允许的 optional 成员出现时自动进入投影，缺席时省略；只有 schema 明确允许 `null` 的位置才能保留 `null`。wire 上不携字段名清单，receiver 不得按调用方自报清单缩小投影。

- **publish**：首次发布或后续无中断更新。新 envelope 的 `version` MUST 严格大于当前 accepted policy 的 `version`，`supersedes` MUST 引用前一份 `policy_id`（首版为 `null`）。
- **rotate**：用于更换 `methods[]` 中的 key、成员设备或恢复授权方；出现的成员自动进入上述完整 policy 投影。轮换期内的 in-flight recovery session（参见 `crypto-media/device-lifecycle.md` §14）MUST 使用其 `issued_at` 时点的 policy；服务端 MUST 拒绝跨 policy 版本拼接材料。
- **revoke key**：当某把 `recovery_unlock` key 被怀疑泄露时，policy holder 发布只更新该 entry `revoked_at` 的 rotate envelope。receiver MUST 拒绝任何 `revoked_at != null` 的 entry，即便签名本身有效；该拒绝 MUST NOT 影响同一 policy 中未被撤销的其它独立 OR 方法。
- **revoke policy**：唯一显式形式是发布下一版本 `methods=[]`；它使未完成 session、尚有效 publication lease 和尚未 accepted reanchor 全部失效。后续只有发布新的 active policy 才能恢复。`expires_at` 表达自然过期：到期不得创建或推进恢复 session，也不得新接受恢复 publication；它不是另一种撤销编码。普通 rotate 允许未被显式撤销且未过期的 in-flight session 继续使用创建时 frozen policy；不得跨版本拼接材料。 session 授权消费 MUST 重查该完整 AccountId 的 accepted policy 历史；一次明确 revoke 不能被后续重新启用 policy 消除。session verified 转换、backup unlock/delete、恢复 transaction step 与首次 reanchor 接纳必须把该检查和相应写入置于同一共享耐久事务边界，使用与 policy 发布一致的账户锁序；仅 HTTP 预检查不足以阻止并发撤销。`recovery_unlock` key 的显式 `revoked_at` 必须对尚未 accepted 的恢复及时生效，不能借 frozen snapshot 绕过泄露撤销。已接受的 reanchor 不因事后 policy revoke 回滚。

**唯一方法来源**：signed policy 只有 `methods[]`，tag 每种最多一条，v1 的封闭四项是 `did_root {}`、`recovery_unlock {keys[]}`、`device_quorum {k,member_ids[]}`、`trusted_recovery_service {services[]}`。每个 entry 是独立 OR 恢复方法。device_quorum 必须按不同有效设备去重并满足 2 ≤ k ≤ n。trusted_recovery_service 的 `services[]` 之间也是 OR：恰好一条 entry 的 `service_id`、`authorization_verification_method` 与 `audience` MUST 与提交的授权逐字相等，没有跨 entry 门限，也不存在部署级恢复签发方；不能用 DID Document membership 或任意字段“提及”替代。did_root 只声明 opt-in，由 DID history/pre-rotation 验证当前 root，不钉一把跨代静态 root，也不接受设备 key 代替。一个方法的证明不得拼给另一个方法凑门限。

publication authority、UI 与 session verifier MUST 从该 entry 同源派生：rule id = kind，role 固定 identity_recovery，action 固定 ak.device.reanchor；recovery_unlock 的 issuer = active keys、门限 1；device_quorum issuer 来自该 accepted basis 上 member_ids 对应 active device methods、门限 k；trusted service issuer 为 `services[]` 的 exact `authorization_verification_method` 集合、门限 1；did_root 从 accepted DID history 取 root authority。排序去重与有效期检查在计算 authority_set_digest 前完成。衍生 rule 不是 policy 中第二份可编辑配置。

**可执行性与失败合同**：v1 没有通用 approval AND 层、announcement 等待或部署级支持矩阵；`min_approvals`、`announcement_required`、`attestation_required` 与服务 k-of-n 都不是 v1 wire 字段，实现 MUST NOT 复活它们。
policy 的唯一附加约束是顶层 `cooldown_seconds`：出现即 MUST 执行，接收方 MUST 拒绝在恢复会话 `created_at` 起未满该秒数时提交的 proof。

发布（publish / rotate）时接收方 MUST 拒绝自身不可执行的 policy，而不是接受后在真正恢复时才暴露：`device_quorum.k` 大于去重后的有效成员数、`recovery_unlock` entry 的有效期或 `backup_hpke` ref 自相矛盾、`trusted_recovery_service` entry 的 `authorization_verification_method` 的 controller 投影不等于同 entry 的 `service_id`，都 MUST reject，且这一类**发布期**拒绝 MUST 使用 `failed_precondition`——它判定的是这份 policy 自身不可执行，不是某次恢复证明与 policy 不匹配，MUST NOT 复用下文的 `recovery_policy_mismatch`。**恢复执行期**的四类失败必须稳定可分且只使用 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json) 已登记的 code：不支持用 `recovery_proof_kind_unimplemented`（501），policy 不允许该 kind 用 `recovery_proof_kind_not_allowed`（409），授权条件未满足（冷却未到、门限不足、逐字匹配失败、设备未授权）用 `recovery_policy_mismatch` / `recovery_policy_device_unauthorized`（409），签名不验证用 `signature_invalid`（401），失效或撤销用 `recovery_policy_revoked`（409）与 `auth_expired`（401）。已签的约束 MUST NOT 被静默忽略：无法执行时 fail closed，不得把多因素授权降级成单因素。部署能力仍复用既有 ServiceDescribe 能力声明与协商，MUST NOT 另建第二套恢复策略来源或方法支持矩阵。

恢复权限只授权受限 reanchor/unlock，MUST NOT 自动授予历史内容解密、active backup 删除或任意内容发布；高风险删除仍执行 §7.8.1 的独立 intent 与权限条件，历史内容解密仍以 MLS 与 backup envelope 自身的授权与密钥要求为准。恢复通过不等于备份或历史消息已恢复。

任何允许的恢复方式（did_root / recovery_unlock / device_quorum / trusted_recovery_service）的 create request、session state 与 proof transcript MUST 绑定 exact closed `account_id: AccountId {principal_id, station_id}`，以及 `(policy_id, version, recovery_session_id)`；create wire 不接受旧顶层 `principal_id`。接收方 MUST 要求 `account_id.station_id` 等于自身 authenticated service DID，并以完整 pair 选择唯一 lifetime PCR lineage，unknown/wrong-service/mismatch fail closed。不绑定的 proof MUST `recovery_evidence_unbound`。Device recovery 场景还 MUST 使用 `crypto-media/device-lifecycle.md` §14 定义的 canonical transcript，其字段集同时绑定 create `request_id`、认证该 create 的 `recovery_session` SessionGrant id、该 grant 的 `cnf.jkt`、`requesting_device_id`、`requesting_device_public_key_did`、`trust_domain`、`identity_model="pcr_policy"`、`model_generation_ref`、session `challenge`、session `created_at` 与 `expires_at`；`model_generation_ref` 必须等于 PCR current device generation，且不得由 DID `versionId` 推导。get、proof submit、backup unlock 与 RecoveryTransaction MUST 出示同一 grant/JKT；transport grant、session state 或 proof transcript 任一 binding 不同都必须 `recovery_evidence_unbound`。`did_root` 仅在冻结 policy 显式启用时成立。

`recovery-session.schema.json#/$defs/publication_authority_context` 的 schema identity 固定
`pcr_policy` authority model，因此该内嵌 context 不携 `identity_model`；session state 与 proof transcript
中进入签名/绑定原像的 `identity_model` 仍保留，consumer 不得用前者的省略删除后者。

### 8.2 恢复授权方与精确授权（normative）

产品自行完成人脸、身份证明、人工审核、企业审批、通知等待等身份核验；这些流程、材料与证据 MUST NOT 进入协议，接收方也 MUST NOT 接收或校验它们。协议只回答三件事：账号是否**事先**授权了这位恢复授权方，该授权方是否为**本次**账号控制权变更签发了有效且精确绑定的授权，以及这次执行**现在**是否仍被允许。

**事先授权**：恢复授权方只能由账号自己经既有合法授权路径写入 accepted recovery policy 的 `methods[kind=trusted_recovery_service].services[]`。产品、部署管理员或 Station MUST NOT 因完成了身份审核而对任意账号取得恢复权；不在该账号 accepted policy 中逐字登记的签发方一律 fail closed。产品内的登录找回与整个账号控制权恢复是两件事，产品授权界面 MUST 明确区分；多个产品共享同一账号时，MUST NOT 默认每个产品都持有整账号恢复权。

**精确授权**：授权 MUST 由 `services[]` 中某一条 entry 的 `authorization_verification_method` 签名，且该 entry 的 `service_id` 与 `audience` MUST 与提交值逐字相等。授权进入签名的 transcript MUST 同时绑定完整 `account_id: AccountId {principal_id, station_id}`、目标新控制密钥（`requesting_device_id` 与冻结的 `requesting_device_public_key_did`）、具体动作（`ak.device.reanchor`）、接收方（`trust_domain` 与 `account_id.station_id`）、本次会话与 challenge（`recovery_session_id`、`policy_id`、`policy_version`、`challenge`、`session_grant_id`、`session_grant_cnf_jkt`）以及明确有效期（`created_at` / `expires_at`）。字段集与字节序按 §8.1 与 [`../crypto-media/device-lifecycle.md` §14](../crypto-media/device-lifecycle.md) 的 canonical transcript。任一绑定不同都 MUST `recovery_evidence_unbound`；该授权 MUST NOT 被挪用到另一账号、另一目标密钥、另一动作、另一部署或另一会话。

**请求方设备绑定**：`recovery_session_id` MUST 来自接收方为本次会话签发的 challenge，MUST NOT 接受调用方自造的 session id。

- `device_quorum`：每个签名设备 MUST 是该 accepted basis 上未撤销的 accepted device，并按不同设备去重后满足 `k`。
- `recovery_unlock` / `trusted_recovery_service` / `did_root`：请求方设备 MAY 是尚未授权的新设备。接收方 MUST 验证 `recovery_session_id`、当前 policy/version、identity model 与 model generation、请求方设备 key 的 proof-of-possession、session challenge、`requesting_device_id` 与冻结的 `requesting_device_public_key_did` 全部一致，MUST NOT 要求该新设备预先存在于 control stream。
- 没有 accepted device 时，恢复完成出口 MUST 按 [`../crypto-media/device-lifecycle.md` §14](../crypto-media/device-lifecycle.md) 提交由同一 replacement device identity key 签署两条 Event 的原子 unit；不得追加 DID-root Event 签名条件。

**执行仍被允许**：签名验证通过不足以放行。接收方 MUST 在同一共享耐久事务边界内按 §8.1 重查 bound policy 是否自然到期、后续任一 accepted 版本是否显式撤销、本次所用 key 是否 `revoked_at`，并原子消费该授权以防重放。冻结 session MUST NOT 绕过自然到期与显式撤销；撤销后重新启用 policy MUST NOT 复活旧 session；已完成动作的精确只读回执不构成重新授权。

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
- `ak.device.authorize` 与 `ak.device.revoke` MUST 进入 schema registry，并按 event auth 规则验证。`ak.device.revoke` 的控制面位置由其 Control Move 信封 `seal_basis`（授权基准，签名覆盖）、首次原子持久化的 Ack + `ak.schema.device_revocation_state.v1` pending record，以及覆盖它的 accepted Seal（永久生效切点）表达，payload 不携带 frontier / generation 字段；已知 pending 起接收方不得为该设备提供新的 session grant、KeyPackage claim、to-device / Event write 或 可携带 producer signer evidence，只有 exact 已确认 rejected command result 可清该 proposal 的 pending；committed command result 才永久撤销。
- Session grant MUST 绑定 principal `did_core_id`、device id、service `did_core_id` / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖：加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定、服务端不可解密要求、`series_seq` 严格单调、`supersedes_id` / `supersedes_digest` 链完整、`mixed_secret_storage=true` 在 non-personal_node profile 下被拒绝、`mls_history` 域使用 `passphrase_kdf` 的 envelope 被拒绝、§7.8 服务端限速与跨 actor 拒绝。
- MLS KeyPackage binding MUST 覆盖 principal `did_core_id`、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝无法由当前 `did` / resolution evidence 验证到该 `did_core_id` 与 device trust chain 的 KeyPackage。
- Recovery policy grammar 由 `ak.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）规范化；publish / rotate 与 `recovery_unlock` key revoke 的 wire 形态由 §8.1 描述。grammar MUST 表达封闭的 `methods`（`did_root`、`recovery_unlock`、`device_quorum`、`trusted_recovery_service` 四项）、每个 `recovery_unlock` key 的 `not_before` / `expires_at` / `revoked_at`、顶层 `cooldown_seconds` 与恢复 receipt。v1 不存在 threshold、share holder、`n` 镜像或 signed approval requirement，grammar MUST NOT 恢复它们。恢复只改变控制链，不自动授予内容读取、历史内容解密或业务 capability。
- Recovery policy publication 的 `ak.vector.identity.recovery_policy_publication.v1` MUST 由至少两个独立 runner 覆盖 canonical `EventInitialSubmission`、PCR allowlist/reducer/Seal admission、threshold recovery signing/HPKE key 闭包、issuer projection、跨字段不一致、未 Seal retry 与特殊写路径绕过拒绝。
- Recovery receipt 由 `ak.schema.recovery_receipt.v1`（`artifacts/schemas/recovery-receipt.schema.json`）规范化；签名输入固定为 `UTF8("ak.identity.recovery_receipt.signature.v1\n") || RFC8785_JCS(receipt 的全部实际存在顶层成员，排除 auth_data)`，不携字段名清单。`crypto-media/device-lifecycle.md` §14 finalize 写入的 receipt MUST 通过该 schema 校验，并绑定 `recovery_session_id` / `policy_id` / `policy_version` / `new_device_id` / `identity_model` / `previous_model_generation_ref` / `result_model_generation_ref` / authorization path refs / `proof_summary` / `unlocked_backups` / `welcome_count` / `outcome`。
- Backup series MUST 满足 §7.6：客户端检查自己 Station 列表结果的 exact AccountId、PCR 与当前 active pointer，按 immutable envelope 的 `supersedes_id` 链选择对应尾部并解密；不得以下载或重放 PCR/control stream 历史作为普通备份读取的前置条件。


PCR 治理事实的非投票消费按 [cbs-profiles §9](../authz/cbs-profiles.md#9-治理结果证明normative)：
key authorization/lifecycle/generation 的确认性可由合法 PCR 治理结果证明证明，不重放整条 PCR 控制流。
本章原始 genesis/controller delegation、实际 producer 历史公钥与签名、method-native 身份根、独立 Account gate
和 Agent authority attestation 仍各自验证；目标 Realm notary 或普通 Station service key 不因此取得 PCR 签名资格。
稳定材料耐久共享，只验证新增事实；已知撤销立即失效相应当前资格，历史签名事实不由 current resolver 重建。
