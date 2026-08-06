---
title: Key Management
status: candidate
normative: true
stability: v1
updated: 2026-07-30
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

长期身份锚点不得用于日常签名。identity root 的 Arkret Event 白名单仅为 §3.1 的 PCR genesis 与 B 模型 re-anchor；设备授权、recovery policy、capability 与普通 Event 必须由对应 enrollment authority、当前 generation 设备/SSK、policy quorum 或短期 session/device key 路径完成。

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
- root 的 Event 签名权限是封闭白名单：仅允许签自体 principal 的 PCR genesis `ak.realm.create` 与 B 模型恢复 `ak.device.reanchor`；其他 Event 即使携带 DID entry ref 也不得启用 root-anchor 验签路径；
- root 还可签合规 DID log controller proof，以及 recovery-material gate 的离线 sealed receipt；除此之外不得签普通 Arkret 操作；
- 每个后继 root 公钥 MUST 不同于全部已激活 root；一代 root 被后继 entry 取代后即 spent，MUST NOT 再出现在任何后继 `updateKeys` 或 `nextKeyHashes` 中。

### 3.2 Principal Signing Key

principal signing key 用于：

- 高权限 capability 签发
- A 模型的 device authorization 与 recovery policy 更新
- principal control state 中其它明确要求 principal-level proof 的操作

它 MAY 轮换。轮换 MUST 进入 principal control stream 或等价 signed event。DID 文档更新只由 §3.1 identity root / guardian update authority 完成；B 模型 enrollment authority 与设备 key 不得被称为 principal signing key，也不得伪造 SSK。

### 3.3 Recovery Secret 与域分隔子键

用户只保管一个 recovery secret；它是派生源，不是可跨用途复用的一把 recovery private key。Arkret v1 从它派生三个相互隔离的角色：代际 DID update root、稳定 recovery-session proof key、稳定 backup HPKE key。客户端恢复 UI MAY 把 recovery secret 呈现为 24 词 BIP-39 助记词，但 MUST NOT 上传助记词、BIP-39 seed、PRK 或任何派生 private key；本地 MAY 仅保留不可逆指纹用于输入校验。

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

普通 root 轮换只推进 `root/<i>`。root index 是该 DID canonical history 的**全局**单调计数，不因 recovery secret handoff 归零。recovery secret 疑似泄露时：若没有预先存在且能拒绝“旧 secret 单签”的独立 guardian/witness/组织策略，原 DID MUST 视为不可逆 compromised，停止建立新信任并用新 secret 重铸 DID；旧 DID deactivation 只能 best-effort，不能作为安全迁移前提。若存在独立策略，MUST 走可续跑的两-entry handoff：设当前 entry 激活 `root_i` 且已承诺旧 secret 的 `root_{i+1}`；先确认新 secret 保管；entry i+1 在独立策略批准下激活旧 `root_{i+1}`，并承诺由新 secret 以**全局索引 i+2**派生的 `root'_{i+2}`；entry i+2 激活 `root'_{i+2}`、承诺 `root'_{i+3}`；随后对 entry i+2 执行 §5.0.7 re-anchor、发布新 recovery-proof policy、为所有引用旧 backup-HPKE recipient 的 active envelope 建新 series 并推进 signed active-series pointer，验证后再撤销旧 policy key。不得把新 secret 的局部 `root'_0` 填入既有 DID history；恢复者从 canonical entry 数重建同一全局 index。每一步 MUST 有 durable checkpoint 并支持幂等续跑。

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

#### 3.6.1 Personal agent runtime pairing 与 session(normative)

`ak.profile.personal_agent_provisioning.v1` 定义了一条面向普通用户的 personal native agent 流程，以现有 agent key 原语为基础:

- **Provisioning** (`POST /_arkret/self/agents`, operation `ak.self.agent.command.provision`) 是闭合的两阶段 operation。`phase=prepare` 只校验 controller recovery 等先决条件并保留 managed Agent DID、专用 `principal_control_realm_id`、controller PCR 与 delegation ref；它 MUST NOT 发布 durable Agent/DID/PCR、accountability、selector、pairing、grant 或其它可观察副作用。controller 必须以 `(agent_id, controller_id, requested_scope)` 重算返回的域分离 `requested_scope_digest`，不匹配时停止。随后 controller MUST 调用 `arkret-rust-sdk` 的统一 authoring API 生成恰好一个 controller-owned `ak.agent.provision` `EventInitialSubmission`；其闭合 payload 同时绑定 allocation、controller delegation、`accountability_scope=agent_operator`、selector 与 `requested_scope_digest`，不含内层 proof。Event `actor_id` MUST 是 authenticated controller、`realm_id` MUST 是返回的 controller PCR；Event proof 是唯一签名。`phase=commit` 原样携带服务端 allocation、完整 private `requested_scope` 与该 submission；Principal Server 必须通过普通 Event schema/proof/authz/frontier/reducer admission 接受它，不得用 service key 代签、接受 `dev-proof`，或绕过 admission 直接写 canonical store。一次 accepted reducer transaction MUST 原子写入 provision、accountability 与 selector 三个 cell；不得暴露部分完成状态。只有该 Event durable accepted 后才能在 Agent DID accepted inception history 的唯一 `ArkretPrincipalControlRealm.serviceEndpoint` 写入闭合四字段 controller delegation + `requested_scope_digest` commitment、创建 pairing handle 并返回 `status=complete`。完整 `requested_scope` 始终保持 controller-private，不得进入公开 DID history 或 durable Event。精确 commit 重试以 allocation 与 submission 的 Event id/canonical bytes/publication evidence bytes 为身份，MUST 返回首次 complete outcome；同 Event id 不同 bytes 或不同 evidence MUST conflict。恢复 MUST 重放同一 submission 并依靠 Event admission 幂等完成，MUST NOT 另造 Event id、proof、lease、receipt 或重复 fact。
  `requested_scope` 是该 Agent key/session 的**全局硬上限而不是授权**：`actions[]` 中的内容 action 只表示以后在某 Realm 中可被单独 grant 的最大 action 集；省略的内容 action 不能由 Realm / Circle / Strand grant、session 或 participation gate 补回。operation/service resource 约束服务面；显式内容 resource selector 只进一步收窄以后允许附加的 Realm 内容资源。Provisioning MUST NOT 从 `requested_scope` 物化 `ak.capability.grant`；后续 grant 必须满足 `grant.actions ⊆ requested_scope.actions` 并继续按 AND 收窄。Participation selection 是独立的动作时 deny gate，不属于 provision commitment。complete 返回 Agent PCR binding、`requested_scope_digest` 与一次性 `pairing_request_id` + `pairing_code`；`pairing_code` MUST 由 CSPRNG 生成且熵不少于 128 bit。此时 Agent PCR bootstrap/recovery state 是 `pending`；controller E2EE client 随后按 §4.1 本地生成 Agent PCR MLS state、提交 Agent PCR genesis 与 Agent profile Event，并按 §7.5.6 上传 controller-owned managed-PCR recovery backup。服务端、Account Authority 与 Principal Server MUST NOT 生成或短暂持有 Agent PCR MLS private state。流程不写入独立 `ak.self.agent.command.provision` Event，也不得在首次 runtime pairing 前伪造或预写 `ak.agent.key.authorize`。
- `requested_scope` 在 v1 provision request 中 MUST 存在，且 Agent principal 创建后 immutable；实现不得把省略解释为 unconstrained 或 deny-all，也不得通过 renew-pairing、同 key re-authorization、Realm 加入或 policy 更新修改它。需要改变（包括扩大）该全局 ceiling 时必须 provision 新 Agent principal。后续 `ak.agent.key.authorize.payload.agent_key_scope` MAY 比它更窄，但 MUST 满足 actions/resources/constraints 的 selector-narrowing 子集规则；不得要求两者完全相等。Receiver 不得信任 service-local row 声称的 ceiling：必须按 authorizing object 的 accepted-at 解析 Agent DID history，验证 §4.1 的公开 digest commitment，并取得有效的 `ak.schema.agent_requested_scope_disclosure.v1` 私有披露，重算 digest 后再求子集。具体 digest、资源覆盖和 mandatory constraint 规则以 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 为准。
- **Runtime key pairing** (`POST /_arkret/gate/account/agent-key-pair`, operation `ak.gate.account.command.pair_agent_key`):agent runtime 本地生成 key pair、提交 public key + proof-of-possession + 可选 `runtime_attestation`(v1 baseline `kind="self_asserted"`)。请求还 MUST 携带 controller 签名的 `requested_scope_disclosure`，其 request/challenge 来自权威 pairing verifier。Controller 签发的 `ak.agent.key.authorize.payload.approval_evidence` MUST 使用 `kind="pairing_request"`，带 `pairing_request_id` 且与请求体 bit-identical，并以 `request_canonical_digest` 绑定本次 pairing request、以 `approved_by` 绑定 controller；该分支 MUST NOT 带 `evidence_ref`，因为短期 `pairing_request_id` 不是 durable object ref，也不存在需要伪造自引用的独立 approval Event。其他 evidence kind 继续以 `evidence_ref` 引用可在 Event frontier 重放的 durable grant / approval / proposal / policy object。首次配对与 replacement re-pairing commit 前，endpoint MUST 针对 **authorize Event 被接受前的 current frontier** 验证 `pcr_recovery.status="ready"`：controller 的当前 active `mls_history` series 尾部必须含 §7.5.6 的 Agent PCR `mls_group_state`，其 controller recovery policy、managed-principal binding 与 Agent PCR accepted frontier/MLS epoch 均为当前值；`pending`、`stale`、缺失或无法验证时 MUST fail closed(`agent_pcr_recovery_not_ready`)且不得消费 pairing handle。`authorize_event` MUST 是普通 `EventInitialSubmission`，其 `event` 写入 Agent PCR：`realm_id` MUST 等于 Agent DID Document 的 `ArkretPrincipalControlRealm.serviceEndpoint.realm_id`，`actor_id` MUST 等于 `agent_id`，`executed_by` MUST 等于 controller DID，`authorization_ref` MUST 等于该 service binding 的 controller delegation DID URL；proof verification method MUST 属于 controller 或其当前授权设备；submission 必须携带普通 publication authority evidence，服务端不得代签 receipt。写入 controller PCR、令 `actor_id=controller`，或由 Account Authority / Principal Server 重新签名均 MUST 拒绝。Pairing endpoint MUST 按 authorize Event accepted-at 验证同一 DID service entry 的 digest commitment，校验私有披露的 controller/verifier/audience/challenge/freshness/proof，重算 `requested_scope_digest`，再校验 `agent_key_scope` 是披露 scope 的收窄子集；还 MUST 校验 `verification_method` 逐字等于 `` `{agent_id}#{device_id}` ``，其中 `device_id` 是同一请求 / session grant 绑定的稳定 Native Agent endpoint。不匹配 fail closed(`reason="verification_method_principal_mismatch"`)。该相等只把 runtime key 与 Signal / MLS endpoint 绑定，MUST NOT 产生 `ak.device.authorize` 或把 Agent 降级为普通 device identity。披露不得复制进 `authorize_event`、通知或任何 durable/public history。首次调用只可把 `ak.agent.key.authorize` 作为 pending control Event durable 入库，并 MUST 返回 `activation_state="awaiting_accepted_frontier"`；durable Event 本身不是 accepted authorization witness，服务端此时不得消费 pairing handle、移除审批通知、写 active key projection 或签发 Agent session。Controller E2EE client MUST 随后以当前 Controller 设备签发覆盖该 Event 的 managed Agent-PCR successor Seal，再以完全相同的 body 与 `Idempotency-Key` 重试。只有服务端能从该 accepted Seal 构造 `status=active` 的完整 portable Agent signer evidence 后，才能原子激活 runtime、消费 handle、终止通知并返回 `activation_state="active"`；缺少 witness 的任何 reconciler 或重试都必须继续保持 awaiting。该 Seal 推进 Agent PCR frontier 后，`pcr_recovery` MUST 暂时投影为 `stale`，直到 producer 追加覆盖新 frontier 的 active-series 尾部；这不回滚已完成的 key activation，但会阻断下一次 pairing commit。若该 agent 此前已存在 active authorized key(runtime replacement re-pairing,见「Pairing 续期」),controller-signed payload 的 `supersedes[]` MUST 精确列出全部既有 active authorization，reducer 在接受该单一 Event 的同一事务中原子替换；被替换 key 已签发的 active session MUST 在 revocation freshness window 内 fail closed,MUST NOT 自然存活到原 TTL。

  当 `gate_account_base` 的 Account Authority 与保存 Agent pairing record / Agent PCR 的 Principal Server 分离时，Account Authority MUST 以完全相同的 `AgentKeyPairRequestBody` 将同一 `ak.gate.account.command.pair_agent_key` 委托到该 Principal Server 的 canonical `POST /_arkret/gate/account/agent-key-pair`，使用部署内 S2S bearer 或 §3 HTTP Message Signature 认证，并携带 `Idempotency-Key=authorize_event.event.event_id`。下游 MUST 独立重做 current pairing、runtime PoP、controller Event proof、publication authority evidence、Agent PCR / delegation、scope 与 replacement 校验；不得信任上游“已验证”布尔值。该委托是同一标准 operation 的部署内执行，不是新的 fan-out operation；实现 MUST NOT 用任何非注册端点或自定义 queue envelope 承载这项协议职责。Account Authority MUST 透明转发下游的两阶段 outcome；只有下游返回与 `authorize_event.event.event_id` 一致的 `authorize_event_ref`、`activation_state="active"` 且 activation 已 durable 后，才能把本地 authorization 标为 active。`awaiting_accepted_frontier`、本地入库或入队均不构成激活成功。
- **Lifecycle、readiness 与 presence 正交（normative）**：通用 Agent list/get view 只暴露 §3.6.3 的三轴；`key_state` 不重复 lifecycle/readiness/presence，也不包含 `runtime_state`。后者只允许作为 pairing poll 的 operation-specific 诊断，从被轮询 handle 与 key facts 机械派生：无 active accepted key 且存在未过期 bootstrap handle → `pending_runtime_key`；无 active key 且 bootstrap handle 已过期 → `pairing_expired`；有 active key 且无未消费 replacement handle → `ready`；有 active key 且存在未过期 replacement handle → `replacing`。它 MUST NOT 被直接写入或提升成产品状态，并必须映射进 generic readiness blocker（无 key → `runtime_key_missing`，open handle → `pairing_open`）。session 签发仍由 lifecycle 与授权链治理；poll 的 `replacing` 不改变旧 key 的 session 语义，真正安全边界是 pair commit 的原子 supersede。
- **Pairing 失败清理**:仅适用于从未完成首次 key 授权的 Agent。`pairing.expires_at` 到达且未完成 pairing 时，服务关闭并省略 open-handle fields；generic readiness 保持 `not_ready` + `runtime_key_missing`，对过期 handle 的 pairing poll 报 `runtime_state=pairing_expired`。服务不得因此创建、撤销或改写任何 Realm grant，也不得改变 lifecycle 意图。已持有 authorized key 的 Agent 的 replacement handle 过期没有任何副作用：lifecycle、既有 key 与 grant 均不变，open fields 消失，readiness 移除 `pairing_open`；其 poll 不得报 `pairing_expired`。
- **Pairing 续期** (`POST /_arkret/self/agents/{agent_id}/renew-pairing`, operation `ak.self.agent.command.renew_pairing`):controller MAY 对无 active accepted runtime key 的 bootstrap Agent或已持有 active authorized key 的 Agent(lifecycle `active` 或 `paused`)原地重开 pairing；`deactivated` MUST 拒绝。每个 Agent 同一时刻至多一个 open pairing handle。
  - 服务 MUST 签发全新的一次性 `pairing_request_id` + `pairing_code` + `pairing.expires_at`，并 MUST 使该 agent 此前签发的所有 pairing handle 永久不可解析(与过期 handle 一致的 anti-enumeration 语义:handle 是一次性的，principal 不是)。
  - 响应 MUST 返回当前 `pcr_recovery` 投影，并以 `pairing_mode="bootstrap"|"replacement"` 固化本次分支；`renew-pairing` 本身不把恢复状态改写为 `pending`。后续 pair commit 无论分支仍只接受 `pcr_recovery.status="ready"`。
  - **Bootstrap 重开**(无 active accepted runtime key):续期后返回 `pairing_mode=bootstrap`，通用 readiness 含 `runtime_key_missing` 与 `pairing_open`；不得创建、撤销或重发 Realm grant。
  - **Runtime replacement**(已持有 active authorized key,lifecycle `active` 或 `paused`):用于 runtime 迁移、key 丢失恢复与例行换钥。重开 pairing 返回 `pairing_mode=replacement` 并使通用 readiness 含 `pairing_open`，MUST NOT 改变 lifecycle 意图；既有 key 与 grant 保留。新 pairing 完成时按上文 supersede 语义原子替换全部旧 key，lifecycle 意图原样保留。怀疑旧 key 失陷时 controller SHOULD 先显式 pause。capability grants 绑定 Agent principal 而非 key，不受替换影响。approval UI MUST 明示 replacement 后果。replacement handle 过期只清除 open fields / `pairing_open` blocker，lifecycle、既有 key、grant 均不变。
  - 若该 agent 的 slug 已被同一 controller 的其他 active / open agent 占用，续期 MUST 以 `failed_precondition` 拒绝。
- **Agent runtime authentication**:复用 `POST /_arkret/gate/account/session-grants`(operation `ak.gate.account.command.issue_session_grant`),通过 `proof.proof_kind="agent_key_proof"` 分支区分。Auth Server MUST 维护独立 schema branch、独立 proof validator;不得让 `agent_key_proof` 走 password / OIDC / passkey 的 validator fallback。请求侧 `agent_scope_request` 是 `ak.profile.agent_auth.v1` overlay,签发后的 scope MUST 物化为 capabilities.md 已注册的 `allowed_tracks` / `allowed_strand_ids` / `allowed_data_labels` / `allowed_endpoints` 等 typed constraints。Auth Server 求交前 MUST 取得已验证、与自身 verifier/audience 及当前 accepted-at DID digest 匹配的私有 `requested_scope_disclosure`；它 MAY 使用 pairing 时建立或经 authenticated confidential S2S 转移的 verifier-private evidence，请求也 MAY 在该 agent 分支携带新 disclosure。仅有 service-local Agent row、公开 digest 或由 agent runtime 自报的完整 scope 时 MUST fail closed。
- **可交互聊天 runtime 的最小服务面（normative）**：若一个 personal Agent runtime 声明能够接收并回复 Realm / Direct Conversation Message，immutable provision `requested_scope`、accepted `agent_key_scope` 与每次 requested session scope MUST 同时覆盖 `ak.self.events.stream.subscribe`、`ak.self.events.read.scan`、`ak.self.events.read.frontier` 与 `ak.self.events.command.submit`；内容层仍须独立覆盖 `ak.event.read`、`ak.message.create` 并取得目标 Realm / Strand 的有效 grant。若该 runtime 还显示在线状态，三层 scope 还 MUST 覆盖 `ak.self.signal.command.send`；只有声明延迟/离线发布时才额外要求 `ak.self.authorization_leases.command.issue`。在线 Event 直接在 submit transaction 读取当前 admission state，不需要前置 lease；显式离线 lease 只延长已验证 authority basis 的有限窗口，不提升内容权限。任一必需 operation 未进入 immutable provision ceiling 时，runtime MUST 在启动时 fail closed 并报告需要 provision 新 Agent principal；不得通过 renew-pairing、扩大 key authorization 或把 Signal 伪装成 Event 修补 immutable ceiling。
- **Agent MLS runtime endpoint 与持久化**：pairing accepted 后，runtime MUST 为 current authorization 创建或恢复一个稳定的协议 `device_id`（wire form `ak:device:<uuid>`），并以该 id 作为 MLS endpoint、KeyPackage owner、Welcome recipient和 consume/revoke session binding。`agent_key_proof` 的 `SessionGrantRequestBody.device_id` MUST 携带该 id，并由 `request_canonical_digest` 与 runtime proof 签名覆盖；Account Authority MUST 将相同 id 持久化到 session grant/introspection metadata 并在 `SessionGrantOutcome.device_id` 返回，Principal Server 若收到缺失该绑定的 Agent grant MUST fail closed。同一 authorization下的 session grant刷新、DPoP key轮换或进程重启不得改变该 id，也不得从 session id/token派生它。runtime MUST 使用 current authorization 对应的同一 Ed25519 private signing capability构造 MLS identity，并在发布任何 KeyPackage前持久化 identity/private KeyPackage state；该 private key MAY 位于不可导出的硬件或进程外 signer 中，协议不得要求导出 seed。MLS LeafNode signature key、§9 upload publish signature与 `ak.agent.key.authorize.verification_method` 必须是同一 key。authorization replacement完成时，旧 session必须失效，旧 authorization下 published/claimed未消费 pool必须 revoke，旧 Welcome/claim必须拒绝；runtime以新 verification method/key和新的 endpoint binding重建 identity/pool，不得把旧 `device_id` 静默重绑到新 key。Welcome routing与 consume必须保留 `(agent_id, device_id, agent_key_authorize_event_id)` 三元组；不得 fallback到 controller device、`ssk_generation` 或 `device_authorize_event_id`。canonical signing bytes以 [`device-lifecycle.md` §9.0](../crypto-media/device-lifecycle.md) 为唯一合同。
- **Session TTL**:Agent session grant 默认最大 TTL SHOULD 为 15 分钟；若 deployment profile 显式声明更长，不应超过 60 分钟。Controller 进入 `deactivated` / `suspended` 后，其 accountable agent 的 active sessions MUST 通过 account lifecycle / revocation 链失效。单次 `agent_key_proof` / refresh proof 的接收窗口 MUST 与已签发 session TTL 分离：proof 的 `expires_at-issued_at` MUST `<=300s`，用于限制一次性证明的重放窗口；Account Authority 不得因此把成功签发的 Agent session TTL 静默收窄到该 proof 剩余窗口。runtime SHOULD 在 grant 到期前自动轮换；正常轮换不得要求 controller 在线或人工批准。
- **Key authorization lifetime 与 session TTL 分离(longevity-safe)**:`ak.agent.key.authorize` 是可供多次 session 签发复用的 durable key authorization。其 `expires_at` 可选:缺省表示不设时间过期，有效性完全由撤销链治理(`ak.agent.key.revoke`、pause / deactivate、controller lifecycle 级联);声明 `expires_at` 是部署或 controller 的附加策略选择。Account Authority MUST NOT 把上述单次 Agent session grant 的 15 分钟默认 TTL 或 60 分钟上限复用为 `ak.agent.key.authorize` 的有效期上限；每次 session 签发仍 MUST 独立检查 authorization 未撤销、未过期(若声明了 `expires_at`)且 scope / audience 匹配，并把签发出的 session TTL 限制在上一条的边界内。
- **授权链无静默悬崖(normative)**:配对完成后,agent 的持续在线不得依赖任何需要人工续期的定时器。默认配置下，使 agent 失去授权的路径只有:显式 kill switch(pause / deactivate / `ak.agent.key.revoke` / `ak.capability.revoke`)、controller lifecycle 或 Realm membership 级联、以及部署 / controller 显式声明的可选 `expires_at`。Session 由 runtime 持 authorized key 自动重签，不构成失效面。session 签发因授权链异常被拒时,Auth Server MUST 使用统一错误信封返回机器可读 reason,使 runtime 能提示 controller 介入；其中 key authorization 已过期导致的拒签 MUST 使用 reason=`agent_key_authorization_expired`,MUST NOT 混入 `proof_invalid`——runtime 必须能区分"proof 构造错误"与"需要 controller 续期"。对任何非 terminal 的 agent,controller 始终可通过 renew-pairing + grant 重授权恢复，恢复路径本身 MUST NOT 过期。**异步续期与提前提醒**:声明了 `expires_at` 的 key authorization,runtime SHOULD 在到期临近时主动发起续期请求（见 §3.6 同 key re-authorization）;controller 无需保持在线——到期前任意时刻、任一已授权设备签发一次新 authorize 即可完成续期。不接受此运维依赖的部署 SHOULD 不声明 `expires_at`(缺省即无此依赖);协议不定义无人批准的自动续期。
- **High-risk approval**:Auth Server MUST NOT 给 agent runtime 展示 CAPTCHA / OTP 页面；需要人类批准时返回统一错误信封 `error.code=claim_required`，并令 `error.details` 严格匹配 `agent-operations.schema.json#/$defs/agent_human_approval_error_details`：`reason_code=human_approval_required`、`approval_request_id=<opaque>`。Controller 在带外 UI 完成批准，产生 capability / delegation / approval event,agent retry 时引用该 event。该分支由 `ak.vector.agent_auth.human_approval_required.v1` 固化。
- **E2EE access**（conformance vector `ak.vector.agent.mls_keypackage_authorization.v1`）:Agent MUST 作为独立 MLS member 参与，不得伪装成 controller 的 delegated device。Native Agent MLS KeyPackage MUST 由其当前 active accepted `ak.agent.key.authorize.verification_method` 对应的同一 Ed25519 key 生成 MLS LeafNode signature key 并签署发布 transcript；claim / Welcome 的 claimed-endpoint trust binding MUST 使用 `agent_key_authorize_event_id` 引用该 authorize Event，且与设备使用的 `ssk_generation` / `device_authorize_event_id` 精确互斥。`device_id` 在该分支只标识 Agent runtime 的 MLS endpoint / Welcome 投递实例，不产生 `ak.device.authorize`、不把 Agent 变成 controller delegated device。authorize 被 revoke、supersede、过期或 key 不匹配时必须使未消费 claim fail closed，从而使 key authorization、session proof 与 MLS membership 落在同一审计链。

##### Agent signing-key binding 与 portable signer evidence（normative）

每次首次 pairing、replacement pairing 或 same-key re-authorization 接受时，controller MUST 在同一批准动作中签发 `ak.schema.agent_signing_key_binding.v1`。其公开字段只允许 `agent_id`、与 authorize payload byte-identical 的 `agent_key_id`、完整 `verification_method`、raw Ed25519 `public_key`、`public_key_digest`、`agent_key_authorize_event_id`、`issued_at`、仅在授权实际有期限时出现的 `expires_at`、`controller_id` 与 `controller_proof`。requested scope、`agent_key_scope`、audience selector、pairing code/request、runtime PoP、attestation、session 与 capability material 不得进入公开 binding。

controller proof 的 signing input 固定为：

```text
UTF8("ak.agent-signing-key-binding-v1\n")
||
JCS(binding object with controller_proof.jws omitted)
```

`controller_proof` MUST 按 `issued_at` 时点的 controller DID/delegation 与 device authorization 验证。binding 的
`issued_at`、`expires_at`、agent/key/method/controller必须与 authorize payload逐字相等。`agent_key_id` MUST 等于
authorize payload 的 `key_id`；`verification_method` 去除 fragment/query 后 MUST 与 `agent_id` byte-identical；
raw key必须解码为恰好32 bytes。authorize payload、公开 binding 与 runtime 审批状态中的
`public_key_digest` MUST 只对这32-byte raw Ed25519 key调用 SDK唯一
`agent_signing_public_key_digest` helper计算，不得hash PublicKey DTO、JWK、multibase或hex文本。`signing_key_binding_digest`只对**包含
完整 controller proof 的整个 binding object**做RFC8785/JCS后SHA-256；controller proof签名transcript则使用上文
独立domain tag并省略`controller_proof.jws`。两种digest与proof transcript是三个互斥domain，不得交换、二次
hash或形成自引用。对应authorize payload必须分别承诺两digest；Event/key/method/controller/time/expiry或任一
digest不一致必须拒绝，service不得替换disclosure或代controller补签。

上述公开授权 digest 与 runtime request binding 中的私有请求 digest 是两个不同 domain。后者只在
`ak.agent.runtime_key_binding.v1` 内使用 `agent_runtime_public_key_digest` 对完整
`agent_runtime_approval_request_body.public_key` DTO 做RFC8785/JCS SHA-256，因此覆盖`kty`、`kid`、`alg`与`key`；
它不得写入 authorize payload、公开 signing-key binding或审批状态，也不得与 raw-key digest直接比较。pairing
接收方必须解码两边raw key逐字匹配（或调用SDK显式的runtime-request转换helper），再分别验证两个digest domain。

`ak.component.agent.key.v1` 的 registered reducer projection 是 portable state witness 的唯一状态来源，不能只把 key Event 写入历史。cell subject MUST 使用 SDK `composite_subject([agent_id, key_id])`，不得用字符串拼接或 diagnostic subject。每个 `ak.agent.key.authorize` 的 reducer MUST 先对 `payload.supersedes[]` 逐项在对应旧 key cell 投影 `remove(tag=authorized_event_ref 对应的 observed canonical Event dot)`，再在当前 key cell 投影 `add(tag=canonical_event_dot(event_id, write_index), value=完整 authorize payload)`；authorization 元素的稳定 tag 是 [`event-and-patch.md` §2.4.2](../models/event-and-patch.md) 定义的 `<event_id>:<write_index>`，绝不是裸 `event_id`。`ak.agent.key.revoke` MUST 在 `seal_basis` 观察到的对应 key cell 中移除全部 active authorize dot，并加入 `add(tag=canonical_event_dot(event_id, write_index), value=完整 revoke payload)` 的 transition marker；marker 只保留可见证的撤销边界，不是 active authorization。Principal Server MUST 在接受前从 `kind + payload` 重建并逐项校验这些 canonical writes；write 缺失、多余、cell/tag/value/顺序不一致均须 `reducer_projection_failed`。这样 authorize、same-key re-authorization、replacement supersede 与 explicit revoke 都能从签名 Seal 的 resolved cell 独立证明，不依赖服务端私有投影。

`ak.schema.agent_signer_evidence.v1` 是 structural XOR：顶层只能是 `verification_mode=current_admission` 或
`verification_mode=historical_event` 两种 closed object 之一，二者字段集合不同，不能通过改 tag 或增删一个
frontier 互换。共享 `admission_evidence` 只含 `agent_authority_snapshot`、隐私最小化的
`controller_account_gate_attestation` 及无自引用的 `admission_evidence_digest`。raw public key不是秘密；Agent/controller
private key、MLS private state、服务本地 `account_id` 与 raw account cell 永不进入 portable evidence。

`agent_authority_snapshot.core` 在 Agent Principal Control Realm 的一个 exact signed Seal view 中同时承载完整
`signing_key_binding`、key authorization、key state witness 和 Agent lifecycle witness。`snapshot_digest` 只对 core
做 RFC 8785/JCS SHA-256；`lease` 由该 PCR 的权威 service DID 在独立 domain
`ak.agent-authority-snapshot-v1` 下签名并逐字绑定 authority、verification method、snapshot digest 与时窗。
snapshot core 的 `seal_lineage[]` 必须是把 key/status witness Seal 连接到 `frontier_seal_id` 的完整、无重复
predecessor closure；unknown、fork、跨 Realm、缺 predecessor 或签名无效均拒绝。

key `cell_ref` MUST 精确等于 SDK 从 `(agent_id, agent_key_id)` 派生的 `ak.component.agent.key.v1` composite
subject；`cell_value` 是 closed、canonical sorted OR-set entry array，每项 tag 必须解析为 accepted Event 的 canonical
`<event_id>:<write_index>` dot，value 必须是 schema-valid authorize/revoke payload。Agent lifecycle `cell_ref` MUST
由 `agent_id` 派生，`cell_value` 是 closed lifecycle 值；`accepted_status_event`、provenance、registered reducer write、
Seal delta/lineage 和 state leaf 必须互相重算一致。首次 active 的唯一 provenance 是 managed Agent delegated PCR
genesis `ak.realm.create` 对恰好一个 critical `refs[] role=agent_provision` 的条件写；服务私有 row、FSM 默认值或
organization-governed PCR 都不能合成首次 active witness。

每个 state witness 都必须携带完整 signed Seal、closed `cell_value`、leaf digest/index/count 与 inclusion proof。
receiver 验证 Seal id/notary signature/Realm/lineage，以 canonical
`{"cell":cell_ref,"state":{"value":cell_value}}` 重算 leaf，再按 §6.2.2 odd-tail promotion 重建 `state_root`。
缺 signed Seal/value、cell/subject/actor/controller/event dot 错配、proof 剩余/不足或 root 不等均 fail closed。

`controller_account_gate_attestation` 由 Account Authority 在 domain `ak.controller-account-gate-v1` 下签名，只公开
controller principal DID、closed active/inactive eligibility、六值 account status、`basis.kind` 对应的最小
binding/status digest 与时窗。`account_binding_default` 表示权威私有 binding 上尚无更严格 accepted status head；
`account_status_event` 绑定真实 status Event/frontier digest。`status=active` 当且仅当 `eligibility=active`；其它状态
全部 inactive。由于 portable evidence 不公开 service-local account identity，任何 `account_id`、raw account cell 或
caller 自报 active 布尔值都是 schema violation。

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

historical 分支必须携带由实际接收 Principal Server 在 Event accepted 时签发的
`ak.schema.agent_signer_admission_receipt.v1`。receipt 在 domain
`ak.agent-signer-admission-receipt-v1` 下闭合绑定 Event id/digest/Realm/admitted Seal/accepted_at、Agent/key method、
authorize Event、完整 admission evidence digest、Agent snapshot/key/status basis、controller gate digest 与 receiver。
receipt 的 `receiver_service_id` MUST 与实际接收并承诺该Event的destination service相同，receipt proof必须由该
destination的registered verification method验证；查询方不得用source service或current authority替代。历史 verifier
在 receipt `accepted_at` 检查当时 snapshot lease和account attestation有效，且 receipt 固定的三层 basis
均 active；不要求这些短期证明在 verifier-now 仍有效。删除 receipt、替换任一 basis、拿 later paused/deactivated
witness 冒充 admission witness、或把 historical object用于新 admission均拒绝。

key interval、Agent lifecycle 与 controller account lifecycle 是三个正交 AND gate。key revoke/supersede 只由真实
`ak.agent.key.*` transition witness表达；parent pause/resume/deactivate或account状态变化不得伪造 key transition、
不得改写 key authorization。Agent PCR 与 account authority 属于不同 DAG，frontier 不可跨 Realm 排序，协议明确
否决“取最早 terminal frontier写入单一 valid_until”的做法。历史有效性只取决于 destination-signed receipt 固定的
三项 admission-time basis；后来任一 gate 变化只阻止新 admission，不追溯抹除此前合法签名。

outer attestation 在 domain `ak.agent-signer-evidence.v1` 下签整个 tagged evidence（只省略 outer_attestation 自身）
的 JCS digest，防止 mode/context/snapshot/receipt拼接；它不替代底层 controller proof、Seal、snapshot lease、Account
Authority proof或receipt proof。直接 evidence query 与 federation transport另用 RFC 9421 HTTP Message Signature
覆盖完整 content digest、operation id与双方 service/session binding，不把 HTTP Signature header 嵌回 body形成环。

`revoked`、`superseded`、`expired`、`conflicted`或 admission-time 任一 parent inactive 是确定性拒绝；evidence/receipt
缺失、时窗不满足或网络失败是 `Unresolved/Stale`，绝不得提升为 Verified。启用
`ak.profile.key_transparency.v1` 时还必须验证 inclusion/consistency/witness proof。完整 transcript 与正负矩阵由
`ak.vector.agent.signer_evidence_binding.v1` 固化。

任何缺少 `signing_key_binding_digest` 证据的 authorization 都是 unresolved，服务端不得从 session row 合成证书，也不得提升为 Verified。客户端 MUST 显示 `verification_pending`；controller MUST 通过 same-key re-authorization 产生 replacement authorize Event 与完整 v1 binding，runtime key MAY 保持不变。
- **Sidecar exposure 披露**：pairing approval UI 上，若该 controller 在新 agent 将要 active 的任一 Realm 中已存在独立 Agent Sidecar 对象，实现 MUST 显式披露“该 agent 激活并完成 access/MLS reconciliation 后，将获得这些 Realm 中现有私人 AI 工作区未来内容的访问权”（见 [`../models/sidecar.md` §4](../models/sidecar.md)）。
- **Lifecycle**: ak.self.agent.command.pause / resume / deactivate 写入唯一 lifecycle 轴。pause/resume/deactivate 都是写入 ak.component.agent.status.v1 的 Control Move，authoring basis 只由 envelope seal_basis 表达。Pause 保留 durable state 但拒绝新 session；Auth Server MUST 在 ≤60 秒的独立 freshness window 内对已签 session fail closed。Deactivate 是 terminal，只提交一个 controller-authorized lifecycle Event；accepted 后 lifecycle=active 成为所有 runtime key、session、open pairing handle、capability grant、KeyPackage、presence 与未来 Event submission 的不可绕过 AND gate。历史 child Event 保留审计，显式 ak.agent.key.revoke / ak.capability.revoke 仅用于 parent 非 terminal 时的定点撤销。服务可异步 cleanup，但不得以 cleanup 成败阻塞 deactivated。所有 open pairing handle 永久不可解析；replacement pairing 与 terminal status 并发时，以 accepted status frontier 为写屏障，terminal 后 pair/renew 均拒绝。portable signer evidence 可用 lifecycle state witness 证明“因 parent terminal 而 ineffective”，无需伪造逐 key transition Event。

Agent projection MUST 分离三轴：`lifecycle=active|paused|deactivated` 是durable controller intent；generic
`readiness=ready|not_ready`的closed blockers只含主体级durable `runtime_key_missing|pairing_open|recovery_stale`，
不得含session、KeyPackage、target grant/membership/reply或MLS blocker；`presence=online|offline|unknown`只表示
短期可达性。target-specific blockers只能出现在对应operation/SDK local plan。presence响应必须携
`expires_at`与`refresh_after`并由客户端jitter刷新；offline不等于deactivated、unpaired或conversation不存在。
- **Resume 时 Sidecar exposure 重新披露（normative）**：`ak.self.agent.command.resume` 提交前，实现 MUST 重新执行上一条流程，列出 agent 在 pause 期间因 controller 新建/ensure 或新加入 Realm 而新增的 Sidecar desired-access exposure；若集合非空，resume MUST 在 controller 显式再次同意之前拒绝执行（不得 silent resume），并把确认作为 audit 事件留底。仅当 pause 期间无新增 Sidecar exposure 时可不重复披露。恢复 active 只改变 desired access；实际读取仍须等待 backing scope/MLS reconciliation 完成。

#### 3.6.2 Runtime request binding、审批竞态与账号通知（normative）

Conformance vector：`ak.vector.agent.runtime_key_binding.v1`。

每个 open `pairing_request_id` 同时最多一个 pending runtime key binding。服务端 MUST 以 canonical JSON 对象计算稳定 digest，kind 固定为 `ak.agent.runtime_key_binding.v1`，对象字段为 `{kind, agent_id, pairing_request_id, verification_method, public_key_digest, attestation_digest}`；此处的`public_key_digest`是私有runtime-request digest，MUST调用`agent_runtime_public_key_digest`对`agent_runtime_approval_request_body.public_key`完整DTO的canonical JSON bytes计算SHA-256 typed digest；它与上节公开授权所用raw-key digest不同且不得互换。`attestation_digest`对`runtime_attestation`（缺省时为 JSON `null`）的 canonical JSON bytes 计算 SHA-256 typed digest。外层 binding 对象再按同一规则计算 SHA-256 typed digest。pairing code、过期时间、PoP challenge/signature 等 freshness proof 不得进入这份稳定身份。canonical helper 只能由 arkret-rust-sdk 定义并供实现复用。

`proof_of_possession` MUST 验证 `agent-operations.schema.json#/$defs/agent_runtime_key_possession_proof`，不得接受开放 JSON、实现私有字段或算法 fallback。v1 runtime key profile 固定为 Ed25519：`public_key.kty="OKP"`、`public_key.alg="Ed25519"`，`public_key.key` 解码后恰为 32 bytes；`public_key.kid`、request `verification_method` 与 proof `verification_method` MUST byte-identical，且该 DID URL 的 controller MUST 等于 request `agent_id`。proof `kind` 固定为 `agent_runtime_key_possession`，proof `alg` 固定为 `Ed25519`，`signature` 是 64-byte raw Ed25519 signature 的无 padding base64url 表达。`Ed25519`也是 RFC 9864 fully-specified JOSE algorithm identifier；任何不能仅凭 `alg` 唯一确定曲线和签名算法的多态别名都不属于本协议词表并 MUST fail closed。controller proof 的 detached JWS protected header 同样 MUST 使用 `alg="Ed25519"`。key 与 signature 解码后还 MUST 以 canonical unpadded base64url 重编码并与 wire byte-identical；非零 unused bits、padding 或其它别名表达必须拒绝。

构造方先计算上述稳定 `runtime_key_binding_digest`，再对以下闭合对象的 JCS bytes 签名；`context` 只存在于签名输入，不是 wire 字段：

```json
{
  "context": "ak.agent-runtime-key-possession-proof-v1",
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

该 digest 与 controller `ak.agent.key.authorize.payload.approval_evidence.request_canonical_digest` 使用的 `ak.agent.key_pairing_request_binding.v1` 不同：后者是 controller 对当前 runtime request 与 pairing record 的批准证据。其唯一 canonical 对象为 `{kind, operation_id, controller_id, agent_id, pairing_request_id, pairing_code, expires_at, audience, runtime_key_binding_digest, proof_of_possession_digest}`：`kind="ak.agent.key_pairing_request_binding.v1"`，`operation_id="ak.gate.account.command.pair_agent_key"`，`expires_at` byte-identical 于权威 `pairing_expires_at`，`audience` byte-identical 于 record `service_id`，`proof_of_possession_digest` 是当前闭合 proof wire object 的 JCS SHA-256 typed digest；不得加入或省略字段。runtime public key、verification method 与 optional attestation 已由 `runtime_key_binding_digest` 闭合绑定，不重复铺开，也不得用只绑定 public-key digest 的旧 helper。

最终 `ak.gate.account.command.pair_agent_key` MUST 从数据库当前持久化的 runtime request 与 pairing record 重新计算 stable binding、PoP transcript/digest/signature 和 pairing-request binding，并与 controller 签名 `approval_evidence.request_canonical_digest`、提交 body、`signing_key_binding`、`authorize_event` payload 及当前 stable binding 比较；final body 的 `proof_of_possession` MUST byte-identical 于当前持久化 proof。不得只比较提交 body 与 pairing handle。same-binding retry 刷新 proof 后，任何绑定旧 `proof_of_possession_digest` 的 controller prompt/approval 自动失效；过期 prompt 或任一不一致必须 fail closed，客户端重新读取。

`ak.agent.key_pairing_request_binding.v1.expires_at` 与权威 `pairing_expires_at`、PoP `created_at` / `expires_at` 都使用统一 UTC 毫秒 profile `YYYY-MM-DDTHH:mm:ss.SSSZ`。构造方 MUST 先把 typed instant 按 Unix 时间向负无穷方向 floor 到毫秒，再以恰好三位小数和大写 `Z` 序列化；投影、transcript 和摘要绑定使用逐字相同的 canonical string，不得从宽松 RFC 3339 输入临时正规化，也不得另派生 epoch 字段。非法或非 canonical wire 输入必须在摘要验证前 fail closed。

首次合法请求生成一个稳定 `approval_request_id` 和 `ak:notification:*` id，并在创建 pairing record 的 account context 中物化 `agent_runtime_approval action=add`。相同 stable binding 的重试是幂等的：允许刷新 PoP 和完整 request，但保留两项 id，并物化 `action=update`。已有 pending 时，不同 stable binding MUST 返回 HTTP 409 `agent_runtime_request_conflict`，不得替换 controller 当前看到的请求。

Runtime 提交体、controller 投影与最终批准体是三个不同的闭合 DTO，不得互相反序列化替代：runtime 向 open endpoint 提交 `agent_runtime_approval_request_body`（含 `pairing_code`，不含 controller disclosure/Event）；authenticated `key_state.pending_runtime_key_request` MUST 精确匹配 `agent_runtime_approval_controller_projection`，只含 `{pairing_request_id, agent_id, verification_method, public_key, proof_of_possession, runtime_attestation?}`，不得含 `pairing_code`、`requested_scope_disclosure`、`authorize_event` 或额外字段；controller 核对 sibling `key_state.pairing_code` 后，MUST 使用当前 controller signer、权威 verifier/audience/challenge 与不超过 5 分钟的 freshness window 新建 `requested_scope_disclosure` 和 `ak.agent.key.authorize`，再组装 `agent_key_pair_request_body`。Account notification 仅携 [`../sync/client-sync.md` §3.1](../sync/client-sync.md) 的最小发现字段；客户端收到通知后读取一次 authenticated Agent projection，不得假定 notification 自身包含完整审批请求。

Pairing record 与 account notification projection 的 add/update/remove MUST 同一数据库事务提交。只有 `ak.agent.key.authorize` 已被 controller-signed managed PCR Seal 覆盖、且可构造 active portable signer evidence 后，才能消费 pairing handle并发 `remove(reason=approved)`；仅 durable 入库的 pending control Event 不满足该条件。expiry、renew-pairing、deactivate 与 supersede 也必须发对应 remove。Authorization witness/activation projection 与该消费必须共享事务，或者以 `authorize_event_ref` 为键提供启动时和请求时均可幂等执行的 reconciler；reconciler MUST 重验 accepted Seal witness，不得从 Event row 存在性推断授权。崩溃不得使已见证 authorization 永久显示 pending。Notification 只负责 controller 发现，不是 durable 审批事实。

最终 pairing commit 以 `authorize_event.event.event_id` 为幂等身份。相同 `pairing_request_id`、相同 stable runtime binding、相同完整 request digest 与相同 EventInitialSubmission bytes（含 publication authority evidence）的重试 MUST 返回当前权威阶段：Seal witness 尚未 accepted 时为同一 `awaiting_accepted_frontier`，witness accepted 且 activation durable 后为同一 `active`；不得再次插入 authorization 或因数据库唯一约束返回 500。相同 Event ID 携带不同 canonical Event bytes 或 publication authority evidence，或相同 runtime key id 绑定不同 Agent / pairing / public key时 MUST 返回 conflict 并 fail closed。网络超时后的调用方 MAY 安全重试完全相同的请求，也 MAY 通过 `ak.self.agent.resource.get` / list 确认 active `authorized_event_ref`；服务端后台重试同样 MUST 重放原始 controller-signed submission，不得生成替代 Event 或代签 receipt。

Controller 通过 `ak.self.account.stream.subscribe.notifications.items[]` 发现请求；声明支持的服务 MUST 在 `ServiceDescribe.supported_features` 列出 `ak.feature.agent_runtime_approval_notifications.v1`。只有 describe 已成功解析且缺少该 token 时，controller 客户端才能启用 30 秒起、带 jitter、最大 60 秒的 list/get fallback；describe 未解析、应用隐藏或离线时不得轮询。未配对 runtime 仍通过 `ak.open.agent_pairing.query.runtime_key_request_status` 有界轮询；HTTP response MUST 携带 `Retry-After`，客户端采用 1s/2s/5s/10s 后最大 30s，并遵守更长的服务端值，在 pairing 过期后停止。

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
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "display_name": "Alice MacBook Pro",
  "device_public_key": "z6Mks...",
  "device_key_format": "Multikey",
  "created_at": "2026-04-26T00:00:00Z",
  "authorized_by": "ak:device:01964136-8000-7000-8000-000000000000",
  "authorization_ref": "ak:event:01964137-8000-8000-8000-000000000000",
  "status": "active",
  "last_seen_at": "2026-04-26T08:00:00Z",
  "revocation_ref": null
}
```

### 4.1 Principal Control Event Stream

设备、session、recovery 和 KeyPackage 有效性属于 principal 级状态，不属于任意 Collaboration Realm。Arkret v1 使用 **Principal Control Event Stream** 承载这些 durable identity state（其归属的 Realm 即 [Principal Control Realm](../models/realm-and-space.md#28-realm-角色分类normative)，与 Collaboration Realm 在 `models/realm-and-space.md` §2.8 中正式分类）。

当 `ak.device.authorize`、`ak.device.revoke`、`ak.device.list_update` 或 `ak.session.grant` 以 `ak.schema.event.v1` Event Envelope 传播时：

- `realm_id` MUST 是该 principal 的专用 `principal_control_realm_id`，不得使用任意 Collaboration Realm 的 `realm_id`。
- `actor_id` MUST 是签发该控制事件的 principal、已授权 device、受信 recovery service 或组织声明的 session issuer。
- `payload.principal_id` / `payload.subject` MUST 与该 control Realm 绑定的 principal DID 一致；不一致时 MUST reject。
- control Realm 的 `ak.realm.create` 或等价 genesis record MUST 绑定 principal DID、DID method / key-log history、control stream policy 和可发现的 service endpoint。该 Realm 使用标准 `ak.schema.realm.v1`；通过 `fields.purpose="principal_control"` + `schema_refs` 包含 `ak.profile.principal_control_realm.v1` 标记其 control stream 角色（详见 §5.0.1 步骤 3）。control realm **不**使用单独的 Realm kind——所有 Realm-level 验证（schema、boundary、E2EE、federation）走标准 Realm 路径。
- 普通 Collaboration Realm 的业务事件 MAY 通过 `refs[role=authorized_by]` 引用不可变 grant record，并通过 role=`did_inception` 等专门 role、verified snapshot reference、Policy Server proof 或 device-state seal 引用 principal control state；`authorized_by` 不得使用 Event id alias，也不得把另一个 principal 的 device/session 事件直接写入该 Collaboration Realm history 来改变身份状态。

`principal_control_realm_id` MUST 可通过 DID Document service、normalized principal view、device/key server describe endpoint 或本地 account binding 验证。客户端无法验证 control Realm 与 principal DID 的绑定时，MUST fail closed：不得接受该 principal 的新 device grant、session grant、KeyPackage 或 device revocation 状态。

Organization principal 的 control stream 遵守同一 PCR 规则，但它没有共享 human password account。组织 PCR 的 genesis / recovery / delegated write MUST 由组织 DID inception/controller proof、满足组织 governance threshold 的 proof、或组织 DID Document / governance profile 明确委派的 Account Authority / `ArkretGovernanceService` 授权。委派路径的 purpose MUST 覆盖对应动作（例如 `principal_control_realm_bootstrap`、`device_enrollment`、`session_issuer` 或 `ak.realm.organization`），且事件必须保留实际执行主体（`executed_by`、governance decision id 或等价审计 ref）。普通企业 SSO/OIDC/passkey 登录只认证某个管理员 principal；它不能单独创建、登录或控制组织 PCR，除非该 Account Authority 同时出示上述组织侧 delegation / governance proof。

Native Personal Agent 是独立 DID principal，不继承 controller 的 PCR 或 home/Collaboration Realm。Managed-agent DID bootstrap MUST 在 Agent DID Document accepted inception history 中包含唯一 service entry：`id=<agent DID>#arkret-principal-control-realm`、`type="ArkretPrincipalControlRealm"`，`serviceEndpoint` 为闭合对象 `{realm_id, controller_did, authorization_ref, requested_scope_digest}`。`realm_id` 是服务端分配的 `ak:realm:*`（本规范不规定算法派生）；`controller_did` 是获授权的 managed-principal controller；`authorization_ref` 是 DID Document 中覆盖 `principal_control_realm_bootstrap`、agent-control authoring 与 `principal_control_realm_recovery` 的 delegation DID URL；`requested_scope_digest` 必须按 [`../authz/capabilities.md` §9.1](../authz/capabilities.md) 的域分离 canonical input 重算匹配。首次 accepted entry 的四元组 create-locked；后续 DID update 删除或改变任一字段时，该 managed-Agent binding 对新授权失效，不能把更新后的值视为扩权。公开 DID Document 与其历史 MUST NOT 包含 `requested_scope`、具体 resource selector 或 constraint。Receiver 必须按 authorizing Event / grant 的 accepted-at 解析 Agent DID history，逐字验证此 entry，并从 controller 经 [`../identity/identity-handles.md` §16](./identity-handles.md) 的认证私有 presentation 路径取得符合 [`agent-requested-scope-disclosure.schema.json`](../../artifacts/schemas/agent-requested-scope-disclosure.schema.json) 的完整 scope 披露。Receiver MUST 校验 `request_id`/`challenge` 单次使用、`verifier_did`/`audience` 精确匹配、`expires_at-issued_at <= 300s`、controller 当前 proof 与 disclosure digest，再以披露 scope 重算 DID 中 commitment；任一环节失败均 fail closed。成功接收后 MAY 把披露作为加密的 verifier-private evidence 保存，但缓存键 MUST 至少包含 `(agent_id, requested_scope_digest, verifier_did, audience)`，不得把 service-local Agent row 单独当成协议绑定，也不得把披露写回公开 DID、Realm plaintext、durable Event、pairing code 或通知。

该边界的 conformance vector 为 `ak.vector.agent.managed_pcr_separation.v1`。

Agent PCR genesis 必须遵守普通 PCR marker、`history_visibility=restricted`、`encryption_profile=mls_rfc9420` 与两条 `e2ee_required` floor；`created_by` 与 notary 都是 Agent DID。Controller 受托创建或写入 Agent PCR 时，Event `actor_id` 是 Agent DID（控制事实所属 principal），`executed_by` 是 controller DID，`authorization_ref` 是上述 DID delegation 或其可验证 materialized grant；proof verification method 必须属于 controller，不得由服务端伪造 Agent 签名。Agent PCR 的 MLS group state MUST 由 controller E2EE client 本地生成；服务端只能保存 ciphertext、公开 envelope metadata 与 reducer 所需的承诺/证明，不得生成、托管或解密该 private state。Agent profile、`ak.agent.key.authorize/revoke` 与 `ak.self.agent.pause/resume/deactivate` 写入 Agent PCR。Controller-owned `ak.agent.provision` 保持在 controller PCR，并原子投影 Agent provisioning、accountability 与 selector 事实；后续独立变更仍可使用通用 accountability/selector Event。Realm-specific capability grant 仍写入所治理 action 所属 Realm。Pairing request 与 approval notification永远不写入任一 PCR。

Agent PCR 的 Event Seal 仍由 `POST /_arkret/self/events/seals` 提交。若 accepted Agent DID delegation 的 purpose 覆盖 `principal_control_realm_recovery`，该 delegation 同时授权当前 controller device 为此 managed PCR 的 delegated notary signer；receiver MUST 从唯一 signed managed-PCR create Event 精确验证 `(Agent DID, controller DID, realm_id, authorization_ref)`。Managed PCR Event 必须由 producer 签名 Realm `scope_ref`，reducer 独立复核。首个非空 Seal MUST 无 predecessor 并原子覆盖 managed PCR founding anchor unit；Principal Server、Account Authority 或其他 service 不得用 service key 代替 Agent/controller 签署。

Managed Agent PCR 的单条 create 虽无 `seal_basis`，仍是 closed-anchor Control Move。Controller
client MUST 从该候选 create 重算完整 founding notary authority，并由 accepted delegation 下的
当前 controller device 为 exact create digest 签 proposal receipt；Principal Server MUST 在同一
事务提交 receipt、canonical create 与 pending Control index。首 Seal 的原子提交再把同一 digest
标记 sealed，并同时提交 Seal lineage 与 registered cell effects；不得出现“Event log 已有 create，
但 pending store 无该 digest”或以 service key/无 receipt 绕过 proposal 轨道的中间状态。

Native Personal Agent 不建立独立的面向用户 Recovery Key，也不得要求用户为每个 Agent 保存另一套 24 词。Agent DID / PCR 管理连续性来自当前 controller delegation；Agent PCR 内容可恢复性来自 §7.5.6 的 controller-owned `mls_history` backup。二者是不同权力：解开 Agent PCR 历史密钥不授予 Agent DID 控制、agent-control authoring 或业务 capability；任何恢复后的写入仍必须验证当前 Agent DID delegation、controller 状态与目标 Event authorization。

实现 MAY 用 identity sidecar、device registry 或 DID/key-log operation 存储同一状态，但它们必须提供等价的签名、digest、auth dependency 和撤销语义；桥接到 Event Envelope 时仍必须遵守上述 `realm_id` 规则。

## 5. 设备授权流程

### 5.0 First-Device Delegated Bootstrap

§5.1 假设已有授权者。principal 首次激活没有已授权 peer，但该死锁不要求把 DID root 与首台 device key 合并：entry 0 的 controller proof 已覆盖 DID Document，文档可以用窄关系把设备入册权委派给独立 enrollment authority。验证者据此验证“这个 DID 授权该权威入册设备”；绑定来自被 root 签名的 delegation，不来自两把 key 相同。

#### 5.0.0 `device_bootstrap` credential 与 transaction（normative）

首设备与 sibling pairing 共用一个 closed credential class `device_bootstrap`，但其 `mode` 是互斥分支，
allowed operations 不得合并：

- `founding` 恰好允许 `ak.gate.account.command.enroll_device`、
  `ak.gate.account.command.cancel_device_bootstrap`、`ak.self.events.command.submit`、
  `ak.self.events.read.resolve`。submit 只可重放同 transaction 的原 `founding_batch_digest`、原 Event IDs 与
  byte-identical Event bytes；resolve 只可查询这些原 Event IDs。不得增加通用 account/bootstrap status、
  Realm write、history、backup、普通 sync或 KeyPackage claim。
- `sibling_pairing` 恰好允许 `ak.gate.account.command.cancel_device_bootstrap`、
  `ak.self.device_messages.command.send`、`ak.self.device_messages.query.list`、
  `ak.self.device_messages.command.ack`。三项 device-message 操作必须绑定同一 transaction、source/target
  device与已登记 `ak.key.verification.*` content kind；list按 transaction过滤且不得返回 secret或普通 message。
  bootstrap sibling不得 enroll。最终 pair只能由 active sibling持 `standard` credential调用
  `ak.gate.account.command.pair_device`。

credential 两分支都签入 principal、device key digest、transaction ID、holder JKT、closed allowlist与
`credential_expires_at`，每次请求都执行 DPoP。transaction另有独立
`bootstrap_transaction_expires_at`，状态仅为 `pending | accepted | cancelled | expired`。bearer过期只令 token
失效：transaction仍 pending且 current holder/device proof通过时，issuer可为同 transaction、同 canonical request
digest续发；不得创建新 transaction、改写 request或替换 Event。只有 founding batch accepted，或 standard
sibling调用 `pair_device` accepted，才可在再次验证 current proof后另签 `standard` credential。

只有显式 accepted cancel进入 `cancelled`，只有 transaction deadline进入 `expired`；其它失败保持
`pending/retryable`，不得写第四状态或 failed terminal。`cancelled|expired`只能 exact replay，禁止续 bootstrap和
standard。

`ak.gate.account.command.cancel_device_bootstrap` 的 closed request固定为
`{transaction_id,mode,canonical_request_digest,idempotency_key}`，并同时要求 bootstrap bearer + DPoP。
cancel ledger key仅为 `(transaction_id,idempotency_key)`，row分别保存原 bootstrap request digest与
`cancel_request_digest`；后者固定为删除任何 derived digest字段后的 exact closed request body做 RFC 8785/JCS，
再对 UTF-8 bytes计算 SHA-256。same key + same full request bytes回放首次 outcome，different bytes返回
`bootstrap_idempotency_conflict`。response必须是 closed discriminated union；
`outcome_digest=SHA-256(RFC8785/JCS(response_without_outcome_digest))`。HTTP/gRPC/MQ逐字段等值，transport不得
把 retryable failure改写成 cancelled/accepted。

`ak.gate.account.command.enroll_device` 以 `(principal_id,device_id,bootstrap transaction)`与 canonical request
digest保存 durable outcome。相同 key/body永远回放原 `ak.device.authorize` Event bytes、ID与 outcome；不同 body
conflict。credential/publication authority过期只允许对原 transaction/outcome/Event签发 fresh外层 evidence，
不得生成“等价”replacement Event。原 Event按当前固定合同不可接受时必须确定性失败。

#### 5.0.1 标准 delegated 路径（v1 core 默认 `did:webvh` principal）

1. **发布前 custody-confirmation gate**：客户端先生成 recovery secret 与完整 inception draft，按 §3.3 派生 `root_0`/`root_1`，并以完整回填、随机抽词、硬件确认或 guardian acknowledgement 验证用户已取得保管能力。客户端可按设备形态选择其中一种，不得把具体助记词序号、协议阶段名或内部 key 名称当作必须暴露的用户界面。在 gate 成功前 MUST NOT 发布 entry 0 或提交 PCR bootstrap。崩溃恢复 MUST 复用同一 draft 与 canonical operation idempotency key，不得重新生成一个身份后静默继续。`personal_node + single_point_of_failure=true` MAY 以设备本地持久化成功替代人工抄录确认，但 MUST 明示身份随设备而失。
2. **`did:webvh` entry 0**：`parameters.method` MUST 为 `did:webvh:1.0`；缺失或未知版本 MUST `unsupported_did_method`。`updateKeys[0]=root_0`，`nextKeyHashes[0]` 按 did:webvh v1.0 对 `root_1` multikey 文本计算 sha2-256 multihash/Base58BTC。DID Document MUST 恰好选择一种 enrollment delegation：B 模型只使用 `ArkretDeviceEnrollmentAuthority` service，`serviceEndpoint` 指向外部 authority DID；A 模型只使用 `capabilityDelegation` 指向 principal 自持的专用 enrollment key。A 模型还 MUST 在 `verificationMethod` + `assertionMethod` 中声明独立 PSK，供 §5.1 首发 `ak.cross_signing.publish`；PSK、enrollment key、identity root 与 device key 必须四者材料不同，且 `capabilityDelegation` 只能指 enrollment key。B 模型 MAY 只有 `id` + service，不要求 `verificationMethod`，且 MUST NOT 声明 A 模型 PSK/capabilityDelegation。两种 delegation 同时出现、悬空 DID URL、指向 root/device key 或 authority 归属含混均 fail closed。root MUST NOT 写入 `verificationMethod`。entry 0 controller proof 由 `root_0` 签发。
3. **PCR bootstrap unit**：客户端 MUST 在一个 `ak.self.events.command.submit` batch 中按顺序提交且原子接受两条 Event；拆批、缺项、重排或只接受一条均 MUST reject。
   1. 第一条是 `ak.realm.create`，创建 principal control Realm。其 `actor_id`/`created_by` 等于 principal DID；`fields.purpose="principal_control"`；`schema_refs` 含 `ak.profile.principal_control_realm.v1`；`encryption_profile="mls_rfc9420"`；两条 encryption floor 均为 `e2ee_required`；`history_visibility="restricted"`；`notary_profile="single_did"`；`notary=<principal DID>`；`security_class="high_assurance"`。Event proof 由 `root_0` 签发，并恰有一个 critical `refs[role="did_inception"]` 指向 entry 0。该 root-anchor 权限只适用于此自体 principal 的第一条 PCR genesis；同一 principal 的第二条 PCR genesis、非 PCR create、actor/realm/DID 不一致、缺失或非 critical ref 均 MUST reject。
   2. 第二条是首个 `ak.device.authorize`，只使用 `service_attested` + `enrollment_authority_binding`。托管路径 `authority_did` 是 entry 0 service 指向的 authority DID；自主权路径 `authority_did` 是 principal DID 且由 entry 0 的 `capabilityDelegation` 专用 enrollment key 签发。`authorization_ref` MUST 精确指向 entry 0 中对应 delegation/service 条目的 DID URL。该 Event 不由 root 签名。PCR bootstrap 的第二槽位就是这条首个 delegated `ak.device.authorize`，它免 `seal_basis`，且是 PCR 分支独有的必需槽位；普通 Realm bootstrap **没有**第二个必需槽位（v1 已删除 founding `ak.capability.grant`，见 [`../models/realm-and-space.md` §2.5](../models/realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)）。两条分支的 authority 各由自己的 root anchor 提供：PCR 用 entry 0 的 critical `did_inception` root anchor，普通 Realm 用 create reducer 注册写入的 `ak.component.realm.authority_root.v1` cell。二者 MUST NOT 互相替代——不得用 Realm authority-root cell 顶替 PCR 的 root anchor，也不得把 device authority 当作 Realm authority root。其他 Realm 不得使用此豁免。
4. **bootstrap 状态**：B 模型接受 unit 时，reducer MUST 初始化 `current_device_generation_ref=entry0.versionId`、`device_generation_status="active"`，并把首设备的 reducer-managed `authorized_generation_ref` 设为同一 versionId。A 模型只使用 SSK generation，不建立这些字段；同一 control stream 混用两套 generation 状态机 MUST fail closed。bootstrap 后首个 Seal 由已授权的设备 #1 代 principal 签出，此后 Control Move 恢复普通 `seal_basis` 规则。
5. **recovery-material gate**：PCR bootstrap accepted 后进入 `recovery_material_pending`。此状态只允许完成 gate 所必需的封闭写入集合：覆盖 bootstrap unit 的首个 Seal、由首设备签名的 genesis `ak.schema.recovery_policy.v1` 发布，以及紧随其后的 genesis `did_recovery` backup put；这些写入不得承载业务 payload、第二设备入册或其它 policy/capability。除该封闭集合外，任何 post-bootstrap 持久 Event、MLS application write 或第二设备入册都必须在 gate 完成前拒绝。客户端 MUST 先发布并接受 genesis recovery policy，再完成以下之一：
   - 发布 `backup_kind="did_recovery"`、`series_seq=0`、`recipient_method="recovery_public_key"` 的 `ak.schema.key_backup.v1` envelope，携带且签名覆盖当前 `recovery_policy_ref`；该 envelope 加密给 §3.3 的 backup-HPKE public key，MUST NOT 使用 `passphrase_kdf`、`secret_storage_key`、`threshold_recovery` 或 `hardware_wrapped_key`；或
   - 保存由 identity root 签名的 offline-sealed receipt，记录 fingerprint、`sealed_at` 与 allowed recovery method，并要求用户二次确认已离线持有。

genesis recovery policy 的 `auth_data` MUST 由 bootstrap unit 已接受的首设备 key 签名，并绑定该设备的当前 A/B generation；它是“尚无既有 policy/SSK”时唯一的 device-signed policy 入口。后续 A 模型 policy 由当前 accepted SSK 或旧 policy quorum 签发；后续 B 模型 policy 由 `device_generation_status="active"` 且 `authorized_generation_ref == current_device_generation_ref` 的当前设备，或旧 policy quorum 签发。两道 gate 分别防止“公开一个用户无法恢复的 DID”和“开始持久使用却没有 accepted 恢复材料”。实现不得把注册面、Events、备份服务伪装成一个分布式原子事务。普通 branch 任一 gate 失败都必须停止；`personal_node` 显式降级只能维持 `single_point_of_failure=true` 并持续警示。

**PCR history key share 释放授权（normative）**：释放方 MUST 校验接收设备存在 accepted `ak.device.authorize`。A 模型要求其 SSK generation 等于当前 accepted generation；B 模型要求 `device_generation_status="active"` 且设备 `authorized_generation_ref` 等于 `current_device_generation_ref`。释放区间以该 authorize 的 accepted frontier 为 baseline，不得释放 baseline 之外的更早或并发分支 epoch key；敏感 recovery interval SHOULD 额外要求 SAS/QR 验证或 enrollment authority 背书。

#### 5.0.2 `personal_node` Profile 降级路径（principal_method=`did:web`）

`personal_node` 使用 `did:web` 时没有可验证历史 log。客户端仍 MUST 先完成 custody-confirmation gate，并在 DID Document 中表达与 §5.0.1 相同的 `capabilityDelegation` 或 `ArkretDeviceEnrollmentAuthority` service；root 不进入 `verificationMethod`，device key 也不在创世文档中伪造占位。continuity evidence MUST 把冷 root 的 `did:key` 公钥、目标 `did:web` 文档 canonical digest 与 delegation 绑定；PCR genesis 的唯一 critical `did_inception` ref 指向该 evidence。PCR bootstrap unit、首设备 enrollment-authority binding 与 recovery-material gate 与 §5.0.1 相同。

`did:web` 只能证明 hosting domain 的当前内容，没有 history resolution 或独立 witness；UI MUST 将其标为低于 witnessed `did:webvh`。升级到 `small_team` 或更高 profile 时 MUST 走 §5.0.5，历史 Event 保留原 `did:web` actor_id。

#### 5.0.3 验证规则

Receiver 接受 PCR bootstrap unit 时 MUST：

`ak.vector.identity.root_anchor_exclusivity.v1` 是本节 root 白名单、delegated bootstrap 原子性与负向边界的规范执行向量。

- 按 method 验证唯一 critical `did_inception` ref、SCID/entry hash/controller proof 或等价 continuity evidence；
- 确认 PCR genesis proof 使用该 evidence 的 active identity root，且 `actor_id`、`created_by`、PCR realm 与 evidence principal 全部一致；
- 确认第二条 `ak.device.authorize` 的 enrollment authority 与 entry 0/document 中窄 delegation 一致，并校验 authority proof、device possession proof、`device_public_key`、`hpke_key` 与 canonical algorithms；
- 原子建立 PCR 与首设备状态，不得让外部观察者看到只有 create 或只有 authorize 的中间态；
- root-anchor Event 验签仅允许本节 PCR genesis 与 §5.0.7 `ak.device.reanchor`。任何其他 kind 携带 `did_inception`/`did_recovery_anchor`，或 root 签任意普通 Event，MUST fail closed。

后续 `ak.device.authorize` 还 MUST 验证 enclosing Realm 已 accepted 且 `fields.purpose="principal_control"`、包含 PCR profile、`created_by` 等于 principal；否则 `device_authorized_principal_control_realm_mismatch`。普通 Event proof MUST 从当前 principal-control frontier 的设备集投影取 key；不得把 DID root、静态 DID Document 的占位 VM 或单 key fallback 当作 device key。

#### 5.0.4 攻击模型

- root 从出生即冷，避免了“先把高权 root 当热 device key、再与时间窗口赛跑”的攻击面；协议不定义 inception online window，也不信任 entry `versionTime` 来决定 root 权限。
- `did:webvh` 的 SCID/hash chain/controller proof 提供可验证连续性；witness/registry 用于发现并裁决 equivocation。pre-rotation 防止泄露的当前 root 直接签下一高度，但不能在无 witness 条件下阻止它制造同高度 sibling。
- `did:web` 仅提供当前 hosting 内容，因此只能用于 `personal_node` 降级 profile。控制 DNS/TLS 的攻击者可替换当前文档；delegation 不提升 method 自身的历史保证。
- `did:key` MUST NOT 直接作为长期 principal。它只可承载本节 method evidence 或迁移证据。

#### 5.0.5 `personal_node`(`did:web`) → `small_team`(`did:webvh`) 跨 method 安全升级

**问题**：`personal_node` 阶段的 `did:web` root evidence 只受 hosting domain DNS/TLS 保护；若注册期间 DNS 被劫持，攻击者可写入伪造文档与 delegation。一旦直接“无审”升级到 `small_team` 的 `did:webvh`，被劫持历史会被当作正常延续。

> **`purpose` 取值边界**（与 [`identity-did.md` §4.2.2](./identity-did.md) 互引）：本节描述同一物理身份从 `did:web` 升级到 `did:webvh`，continuity proof 的 `purpose` MUST 为 `principal_method_upgrade`，且走本节 OOB + 双签硬条件。`principal_migration` 不得用于绕过本节对弱 method root fingerprint 的独立确认。

为此，跨 method 升级 MUST 满足以下硬条件，否则 receiver MUST reject，reason=`inception_upgrade_evidence_insufficient`：

##### 5.0.5.1 OOB root fingerprint 验证

用户 MUST 在升级前通过至少一条独立信任通道确认 `did:web` 阶段 cold root public key fingerprint：

| 信任通道 | 形态 | UI 强度 |
| --- | --- | --- |
| 离线纸质 / 硬件钱包记录 | 用户在 `personal_node` 注册成功后导出 `SHA-256(root pubkey)` fingerprint 并离线记录 | 强 |
| 物理面对面 | 邮票号 / QR 在物理设备间扫描 | 强 |
| 已知可信第二信道 | 邮箱(非托管在同一 hosting domain)、Signal、电话回拨 | 中 — UI MUST 警告"通道需独立于注册时的 DNS/TLS 链" |
| 同一 hosting domain 内的 HTTPS 凭证 | — | **不接受**(同源已被假设劫持) |

UI 在升级流程中 MUST 强制要求用户**重新输入或扫描** fingerprint,而不是从本地缓存读取——否则攻击者把首次注册期间植入的 fingerprint 缓存也算作"用户确认"。

##### 5.0.5.2 Cold root 双签 transfer proof

升级 transition Event(`ak.did.proof.continuity`,`old_did=did:web:<host>`,`new_did=did:webvh:<scid>:<host>`)**MUST** 满足 `ak.schema.did_continuity_proof.v1` transfer envelope 结构；reducer 与 receiver 直接消费下列字段集合，并按 schema 与签名链验证：

```json
{
  "schema": "ak.schema.did_continuity_proof.v1",
  "old_did": "did:web:<host>",
  "new_did": "did:webvh:<scid>:<host>",
  "purpose": "principal_method_upgrade",
  "trust_domain": "ak:trust_domain:<deployment-or-realm>",
  "audience": ["did:webvh:z2Cxbwy2o7AmBLzdfDbix8WAP:registry.example"],
  "issued_at": "2026-05-19T00:00:00Z",
  "transfer_proof": {
    "old_did_document_canonical_digest": "sha256:<64-hex>",
    "old_did_document_fetched_at": "<RFC 3339 UTC>",
    "inception_public_key_fingerprint": "sha256:<64-hex>",
    "user_oob_confirmation_id": "<opaque user-side confirmation token>",
    "user_oob_confirmation_method": "offline_paper|physical_meet|independent_channel"
  },
  "signature_chain": [
    {
      "principal_id": "did:web:<host>",
      "verification_method": "did:key:<old-cold-root-multikey>#<old-cold-root-multikey>",
      "algorithm": "Ed25519",
      "payload_digest": "sha256:<64-hex>",
      "signature": "<base64url-signature>"
    },
    {
      "principal_id": "did:webvh:<scid>:<host>",
      "verification_method": "did:key:<new-cold-root-multikey>#<new-cold-root-multikey>",
      "algorithm": "Ed25519",
      "payload_digest": "sha256:<64-hex>",
      "signature": "<base64url-signature>"
    }
  ]
}
```

关键 normative 规则:
- `signature_chain` MUST 同时含两段签名：原 `did:web` continuity evidence 绑定的 cold root + 新 `did:webvh` entry-0 active cold root。两段 `verification_method` 都标识实际签名 root 的 `did:key` VM；不得回退到 DID Document-only inception/verification VM。任一缺失或失效即 `inception_upgrade_signature_chain_invalid`。
- 为保持既有 wire 名称，`inception_public_key_fingerprint` 字段继续存在，但其值是 §5.0.2 continuity evidence 中 cold root public key 的 fingerprint，不要求该 key 出现在 DID Document `verificationMethod`。
- `user_oob_confirmation_id` 是 user-side 不透明 token——客户端 SHOULD 把 OOB 确认结果写入 user-private secret storage,服务端 / receiver 不 trust 该字段为真实人类确认证据，但**保留**以便审计回放与 UI 重现。`user_oob_confirmation_method` 是枚举 hint,receiver MAY 用它把"通过弱通道(independent_channel)确认的迁移"打上额外的低信任标记。
- 整个 transfer envelope MUST 在签名 transcript 中包含 `old_did_document_canonical_digest`——这一字段 freezes 攻击者对 hosting domain 在升级时刻**之后**继续替换 DID Document 的可能性(任何替换都会让 hash 不再匹配 receiver 拉取的新 document)。
- **Replay 域绑定(`trust_domain` / `audience`)**:升级 transition envelope MUST 在签名 transcript 中包含当前接收语境的 `trust_domain` 与至少一个 `audience`。Receiver MUST 校验 `trust_domain == current_receive_context.trust_domain`，且自身 service DID、Realm registry DID 或明确配置的 verifier id 位于 `audience` 中；任一不匹配 MUST reject `inception_upgrade_evidence_insufficient`。该绑定与 `signature_chain` 双签、`transfer_proof` 一起构成升级证明，防止合法升级 envelope 被跨 verifier / 跨 trust domain 重放。
- **反向 acceptance**:本节的双签 `signature_chain` 已在**同一 envelope 内**承载新 DID 侧的接受证明——`signature_chain[1]` 由 `did:webvh` entry-0 controller key(新 method 主体)签署，即等价于 [identity-did.md §4.2](./identity-did.md) 要求的反向 `ArkretContinuityAccepted`,无需新 DID 侧再发独立 acceptance Event。即:跨 method 升级以"单 envelope 双签"满足双向 continuity,而 §4.2 的"`ArkretContinuityProof` + 反向 `ArkretContinuityAccepted` 两个 service entry"模式适用于原 DID 仍持续可解析的同 method / 一般迁移场景。

##### 5.0.5.3 Receiver 验证规则

任何接收升级 transition Event 的 receiver(Principal Server、其他 federation peer、新设备 join 时)**MUST**:

1. 拉取 `old_did` 的当前 DID Document,canonicalize 后 hash 比对 `transfer_proof.old_did_document_canonical_digest`;不一致 → reject `inception_upgrade_old_document_hash_mismatch`。
2. 校验 `transfer_proof.old_did_document_fetched_at` 是 RFC 3339 UTC，且 receiver 当前时间与该值的差值不得超过升级 evidence 新鲜度上限常量 `inception_upgrade_evidence_max_age = 168h`（7 天）；超过窗口 → reject `inception_upgrade_evidence_stale`。Receiver MAY 使用更短 deployment policy，但 MUST NOT 接受超过 `inception_upgrade_evidence_max_age` 的 transfer evidence。

   > 说明：`inception_upgrade_evidence_max_age` 是**在线升级 transfer evidence 新鲜度**的独立常量，与 [`identity-did.md` §3.4](./identity-did.md) `did:webvh` outage 期 per-entry cache age 7 天上限**语义域不同**（前者约束升级证据的拉取时效，后者约束 outage cache entry 的可用性）。两者当前**取值恰好相同（168h / 7 天）但不绑定**：调整任一处不应自动推导改动另一处，引用方 MUST 各自独立解读。
3. 校验 `signature_chain` 两段签名：旧段公钥必须等于 §5.0.2 continuity evidence 绑定的 cold root，且该 evidence 覆盖被 hash 的旧文档与 delegation；新段公钥必须是 `did:webvh` entry 0 active root。任一失败即 `inception_upgrade_signature_chain_invalid`。
4. 校验 `inception_public_key_fingerprint` 等于步骤 3 命中的旧 cold root fingerprint；失败即 `inception_upgrade_fingerprint_mismatch`。
5. 校验 `trust_domain` 与 `audience` 域绑定；失败 → reject `inception_upgrade_evidence_insufficient`。
6. 校验 `did:webvh` `entry 0` 的 SCID / entry hash / controller proof(标准 `did:webvh` inception 验证)——这一段独立于 `did:web` 阶段。
7. 写入“该 principal 已通过 §5.0.5 跨 method 升级”标记；历史 Event 可保留 `did:web` actor_id，升级后新 Event 使用 `did:webvh` actor_id。旧 `did:web` root 在升级 accepted 后 retired，不得签任何新 Event 或被放入新 DID 的 device/enrollment key 位置。

##### 5.0.5.4 不允许的简化

- Forbidden: "用户点 OK 即升级"(无 OOB confirmation_method / 无 inception_public_key_fingerprint 二次确认) — receiver MUST reject `inception_upgrade_evidence_insufficient`。
- Forbidden：旧 root 单签升级；缺新 `did:webvh` entry-0 root 签名必须 `inception_upgrade_signature_chain_invalid`。
- Forbidden: DNS / hosting domain 内嵌"确认页"作为 OOB(同源攻击窗口未脱离)。
- Forbidden：升级后继续接受旧 `did:web` root 签发的新 Event；升级 accepted 后立即标记 retired，已 sealed 历史保留。

##### 5.0.5.5 安全代价登记

- 该流程把 personal_node 阶段被 DNS 劫持的损害限制在 personal_node Realm 内部；升级后 attacker 无法通过升级路径继承新 method 的根。
- 代价:升级流程对用户**强制**至少一次离线 / 独立通道确认,UI 不能"自动一键升级"。这是明确取舍:为防止注册期 DNS 劫持继承，引入一次性 OOB 友好度成本。
- 对从未通过 personal_node 阶段(直接以 `did:webvh` 走 §5.0.1)的 principal,本节不适用。

#### 5.0.6 外部入册权威(account-authority enrollment)

[`account-lifecycle.md` §2.1.1](./account-lifecycle.md) 允许 account-first onboarding 使用 auth service 提供的 hosting 与 enrollment authority。"托管"只表示 DID log / hosting 与账号入册服务受托运行；identity root 仍由客户端生成并冷持有，服务端 MUST NOT 生成、取得或持久保存 root private key。设备授权的信任根是 DID 文档指派的入册权威，而非 identity root 或 SSK。规则:

1. **入册权威指派(in-document,可自证)**：客户端签发 principal DID entry 时 MUST 在 DID 文档中以**窄关系**指派入册权威——一条 `ArkretDeviceEnrollmentAuthority` service 条目（`serviceEndpoint` 指向权威 DID，见 [`identity-did.md`](./identity-did.md)），或一条 `capabilityDelegation` verification method。identity registry / account authority 可托管日志和提供 enrollment 服务，但不得生成或持有 principal identity root。指派 **MUST NOT** 复用 `controller`（后者是改写身份根的强权，入册权威只应能入册）。文档锚定的指派是地面真值；deployment 信任策略 MAY 收紧（交集）或在文档无法表达时补空（回退，标记低 assurance），**MUST NOT** 并集扩权。
2. **持久入册密钥（≠ identity root）**：入册权威持有一把持久签名密钥，只用于签发 `ak.device.authorize`。该 key 可轮换且不使既有授权失效；identity root 从出生即冷，二者 MUST NOT 复用。
3. **设备授权走 `service_attested`**：设备入册按 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md) 的 `enrollment_authority_binding` / `service_attested` 形态，account authority **MUST NOT** 持有或伪造本 principal 的 SSK。客户端经 canonical gate 操作 `ak.gate.account.command.enroll_device`（`POST /_arkret/gate/account/device-enroll`）请求该签名；首台设备由 §5.0.1 原子 bootstrap unit 绑定，后续无兄弟设备可审批的恢复由 §5.0.7 绑定。
4. **按时点解析，轮换不失效**：receiver 复验历史 `ak.device.authorize` 时，对**具备 history-resolution method 的入册权威 DID**（如 `did:webvh`），MUST 按 Event accepted-at 做按时点解析（`did:webvh` 历史 `versionTime`），用当时有效的入册密钥验签——轮换不使既有授权失效。

   **无 history-resolution method 的入册权威(normative，inline 快照 + controller proof)**:当入册权威 DID 是**无可验证历史 method**(典型 `did:web`——它只反映"当前 DID Document",一旦入册密钥轮换或 hosting domain 被劫持回填，旧 `ak.device.authorize` 既无法按时点解析当时的 verification method、也可被替换后的当前文档伪造复验)时，按时点解析不可用。此时设备授权事件 MUST 在 `enrollment_authority_binding` 中 **inline 携带签发时刻的 verification method 快照**(签名公钥 multibase / JWK + 其在入册权威 DID 文档中的 method id)以及**该 key 的 controller proof**(由入册权威 DID 当时的 controller key 对"该 verification method 属于本 DID 且获授签发设备授权"的签名)，使历史复验**只依赖事件内自带的快照 + controller proof**、不依赖对 `did:web` 当前文档的在线解析。receiver 复验时 MUST：(a) 用 inline 快照中的公钥验 `proofs[]`;(b) 验 controller proof 把该快照公钥链接到入册权威 DID 的 controller 集；(c) 校验 binding 的 `authority_did` / `authorization_ref` 与快照一致。缺失 inline 快照或 controller proof 的、由无 history-resolution method 入册权威签发的 `ak.device.authorize` MUST `reject`(reason `device_enrollment_authority_snapshot_missing`)。

   作为该 inline-快照要求的替代，deployment policy MAY 直接**禁止 `did:web` 等无历史 method 作入册权威轮换**——要求入册权威在轮换前先按 [`identity-did.md` §4.2.2](./identity-did.md) 与本文 §5.0.5 升级到 `did:webvh`,使按时点解析重新可用。v1 推荐前者(inline 快照 + controller proof)，因为它不强制所有托管 DID 部署升级 method。

   > **schema 落地状态**：上述 inline 快照 + controller proof 已在 `device_enrollment_authority_binding`（[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `$defs/device_enrollment_authority_binding`）落地为可选字段 `authority_verification_method_snapshot {method_id, public_key_multibase|public_key_jwk, alg}` 与 `authority_controller_proof {controller_method_id, signature, signed_at}`；对应 fail-closed reason_code `device_enrollment_authority_snapshot_missing` 已登记于 [`error-code-registry.json`](../../artifacts/registry/error-code-registry.json)。正文语义与 schema / error-code 均已同步。
5. **provenance**:每条设备授权记录 MUST 记录其入册权威与来源(文档锚定 / 仅策略);联邦只采信文档锚定者。

自主权路径（客户端用 `capabilityDelegation` 指向自有专用 enrollment method）与本节对称，采用同一 `service_attested` 信封，仅 `authority_did` 等于 principal DID。模型互斥 MUST 按权威归属判断：外部 account authority 出现时，该 control stream MUST NOT 出现 `ak.cross_signing.publish`；`authority_did == principal_id` 时允许 A 模型 SSK/USK 共存。不得仅因存在 `enrollment_authority_binding` 就把自主权 A 模型误判成 B 模型。

#### 5.0.7 B 模型 Recovery Re-anchor Unit

> 本节的 re-anchor unit 是 B 模型 `RecoveryTransaction` 的 `submit_reanchor_unit` 步骤，不是独立流程：create 先固定 typed prepared plan 与 ticket/DID/Event reserved ids；coordinator 依次执行 `issue_authority_ticket → authorize_recovery_device → publish_did_entry → submit_reanchor_unit`。unit 原子覆盖 `reanchor_event_id` 与 `authorize_event_id`，MUST NOT 拆成两个可独立重试、会产生不同 Event id 的步骤。WebVH entry 已接受但 re-anchor response 丢失时，transaction 保持 `running` 并从相同 prepared bytes、reserved ids 与 authority accepted output续跑，不得创建第二 entry。见 [`./security-transactions.md` §2](./security-transactions.md)。

`ak.vector.identity.device_reanchor.v1` 覆盖本节原子 unit、frontier CAS、generation fence、receipt、幂等与冲突 quarantine 的规范执行闭包。

本节仅适用于外部 enrollment authority 的 B 模型。A 模型 fresh-device recovery 继续使用 [`../crypto-media/device-lifecycle.md` §15](../crypto-media/device-lifecycle.md) 的 SSK path；同一 control stream 混用 `ak.device.reanchor` 与 SSK generation MUST fail closed。

恢复客户端 MUST 在 transaction create 前准备 `did:webvh` entry N 的 canonical bytes，但不得自行先发布。entry N 的 `updateKeys[0]` 是当前 active `root_{i+1}`，其哈希命中 entry N-1 的 `nextKeyHashes`；entry N controller proof 必须由 entry N 当前 active authority 签发，而不是 previous root。entry N 同时承诺下一 root，并可替换 enrollment delegation。guardian 替代 authority 必须表现为一把 generation-specific threshold multikey；DID 层仍是 any-of，不得把多个普通 `updateKeys` 宣称为 threshold。已经激活的 root/guardian key 均为 spent，不得复用。Principal Server 必须先为 durable transaction 签发 audience 精确的 recovery authority ticket，Account Authority 通过 `ak.gate.account.command.authorize_recovery_device` 返回 byte-stable authorize Event；只有该 accepted output 与 prepared plan逐项一致后，coordinator 才发布 entry N。authorization preimage 必须向 Account Authority 提供与 prepared publication byte-identical 的 candidate entry canonical bytes；Account Authority 必须在内存中把它接到独立验证的 entry N-1 history，验证 WebVH chain/controller proof并从 candidate document 解析本次 `authorization_ref`，不得用旧 delegation 或 ticket 摘要代替，也不得提前发布 entry。

随后客户端 MUST 在一个 `ak.self.events.command.submit` batch 中按顺序原子提交：

1. `ak.device.reanchor`：payload 严格按 `principal_id`、`did_version_id`、`previous_device_generation`、`new_device_generation`、`pre_fence_basis`、`replacement_authorize_event_id`、`replacement_authorize_digest` 排列并 closed；`new_device_generation == did_version_id`。Event 由 entry N controller proof 实际使用的 active update authority 签发，恰有一个 critical `refs[role="did_recovery_anchor"]` 指向 entry N。
2. `ak.device.authorize#R`：由 entry N delegation 指派的 enrollment authority 签发，使用 `service_attested` + `enrollment_authority_binding`。其 id/digest 必须逐字等于 re-anchor payload 的 replacement fields，`prev_refs` 只含 re-anchor event id。设备行 `authorized_generation_ref` 由 reducer 写成 entry N versionId，producer payload 不得自报。

构造顺序固定为：先为两条 Event 分配独立 typed UUIDv7 id；authorize 的 `prev_refs` 写 re-anchor id，填完 actor sequence/payload 后计算不含 proofs 的 authorize digest；将 id/digest 写入 re-anchor payload并由 active update authority 签名；最后由 enrollment authority 对 authorize digest 签 proof。authorize 不引用 re-anchor digest，因此不存在 digest cycle。

`pre_fence_basis` 是 live admission 的完整 accepted Seal frontier：

- 仅当 canonical joined view 尚无 accepted Seal 时可为 null，此时仅保留 immutable genesis anchor set；
- 非 null 时 `leaves[]` 必须精确等于受理时完整、已验证、非 quarantine frontier，`control_event_set_root`/`state_root` 必须可从同一 view 重建；producer 不得选择更老或不完整 frontier；
- admission 必须与 Seal admission 串行化，或在同一事务对 frontier digest 做 CAS；快照后改变则整个 unit 以 `device_reanchor_frontier_mismatch` 拒绝；
- re-anchor `prev_refs` 等于 preserved closure 加 genesis anchor set 中该 actor 的 canonical heads，`actor_seq=1+max(preserved actor_seq)`；authorize sequence 紧随其后。未保留 pending/unsealed siblings 不得阻塞恢复。

live admission 时 entry N 必须是 registry head，否则 `device_reanchor_entry_not_head`。受理必须在同一数据库事务写入 batch receipt、两条 Event、generation state 与 device projection；receipt 必须绑定 accepted-at registry head、DID version、re-anchor digest 与 authorize digest。完全相同 unit 的重试返回原 outcome，不重复 projected writes。历史 replay 使用 receipt 固定的 accepted-at snapshot；后来的普通 entry 不使既有 unit 失效。

unit 验证完成时授权 fence 立即生效，不等待旧设备签 Seal。reducer 将 `current_device_generation_ref` 推进到 entry N、状态置 `active`。首个新-generation Seal 的 predecessors 必须精确等于 basis leaves（null 时为空），delta 必须覆盖 re-anchor 与 authorize。basis closure 内旧 Event/Seal 保留；closure 外仅由旧 generation device 签发的 Event/Seal 保留原 bytes 但进入 `fork_quarantine`。此后普通 Event/Seal 的 signer device 必须满足 `authorized_generation_ref == current_device_generation_ref`，否则 `device_generation_fenced`。

冲突槽位是 `(principal_id, did_version_number)`，version number 从已验证 versionId 解析。只有 did_version_id、re-anchor digest、authorize digest 全相同才是幂等；同一槽位出现任一不同，所有候选 unit 及其后继 generation Seal MUST 全部 quarantine，reason=`device_reanchor_conflict`，MUST NOT 选 first-seen winner。状态保留最后未冲突 generation ref 并置 `device_generation_status="conflicted"`；此时关闭全部普通 Event/Seal admission。解除冲突只能使用更高 version number、由下一把已预承诺 authority 签发且按 registry/witness policy 成为 canonical head 的后继 entry，再提交 re-anchor；其 `previous_device_generation` 仍指最后未冲突 ref。不能由独立 policy 排除的 sibling 继续 quarantine。

### 5.1 新设备加入（首台设备已存在）

推荐流程：

1. 新设备本地生成 device key。
2. 新设备先通过 `ak.gate.account.command.issue_session_grant` 获得 fresh-device restricted session grant，或通过二维码/手动码把同等 pairing payload 交给旧设备。该 grant 只能用于同 principal 的 `ak.key.verification.*` bootstrap；在完成 step 5 的 SAS/QR transcript 验证之前，MUST NOT 读取 E2EE history、解锁 key backup 或请求 `ak.secret.*`。**SAS 验证成功后例外**（normative）：该 fresh-device grant MAY 仅向同一 SAS transcript 绑定的已授权设备发送 `ak.secret.request`，用于无口令 secret 直传（[`device-lifecycle.md` §10.7](../crypto-media/device-lifecycle.md)）；该例外仅限 transcript 绑定的设备对，不放宽 E2EE history 读取或 key backup 解锁。
3. 新设备通过 `POST /_arkret/self/device_messages` 向同 principal 的已授权设备发送 `ak.key.verification.request`。content MUST 至少包含 `transaction_id`、`from_device`、`methods`、`timestamp`、`expires_at`；用于设备授权时 SHOULD 带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`（canonical `PublicKey`）、`challenge_proof`、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`（wire 示例见 [`device-lifecycle.md` §7](../crypto-media/device-lifecycle.md)）。
4. 已授权设备的主接收路径是 `GET /_arkret/self/account/subscribe` 的 `delta.to_device.messages[]`；push 只能作为唤醒提示。若 `delta.to_device.limited=true`、本地 dispatcher 需要补洞，或旧设备当前没有完整 account subscribe，才使用 `GET /_arkret/self/device_messages?after=<cursor>&limit=n` 补拉。UI MUST 显示 requesting device metadata 与 pairing code，要求用户和新设备屏幕上的 code 比对。
5. 用户在已授权设备上批准并完成 SAS/QR transcript 后，该设备调用 `POST /_arkret/gate/account/device-pair`，提交 transcript 绑定的 `pairing_code`、`new_device_pubkey`、`challenge_proof` 与当前设备 fresh proof；`challenge_proof` 的 transcript 与验签规则见 [`device-lifecycle.md` §2.1.2](../crypto-media/device-lifecycle.md)。`/_arkret/self/devices/pairing-requests*` 不是 v1 core approval surface。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->
6. Events API / identity registry 接受并传播 `ak.device.authorize` 与 `ak.device.list_update`；gate 返回 `authorized_event_ref` 或等价引用。新设备可通过 `ak.key.verification.done` 中的 hint、重新签发/升级后的 session grant、或后续 account subscribe/device list baseline 观察结果，但 MUST 以 durable device list 为准，之后才开始同步 Event history、Realm membership 和必要的 MLS Welcome / key share。

如果用户没有任何可用的已授权设备，UI SHOULD 明确优先提示"在已有设备确认"；确认不可用后，才进入恢复密钥 / social recovery 路径。新设备仅凭登录 session grant MUST NOT 获得 E2EE history key。

`ak.device.authorize.payload` 示例：

```json
{
  "principal_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "device_public_key": "z6Mks...",
  "scopes": [
    "ak.self.events.read.describe",
    "ak.self.events.command.submit",
    "ak.self.account.stream.subscribe",
    "ak.self.keys.keypackages.upload.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "authorized_by": "ak:device:01964136-8000-7000-8000-000000000000",
  "cross_signing_binding": {
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ak_self_signing_v1",
    "ssk_generation": 1,
    "signature": "base64url...",
    "signature_algorithm": "Ed25519"
  },
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#device-old",
    "jws": "..."
  }
}
```

### 5.2 设备吊销

设备丢失、出售、被恶意控制或员工离职时，MUST 发布 `ak.device.revoke`。

吊销后：

- Events API MUST 拒绝该设备的新签名写入
- authz MUST 视相关 session grant 失效
- 加密 Realm SHOULD 通过 MLS Remove 推进 epoch；Commit 的 `governance_binding.security_frontier_digest` MUST 从已经包含该 `ak.device.revoke` 或已导入该撤销的 Realm leaf-remove Move 的 accepted state 重算，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖
- 客户端和受托 projection executor SHOULD 标记已撤销设备产生的未确认 Operation 为高风险

## 6. Session Grant

Session grant 用于 OIDC / SSO、浏览器短会话、远程执行环境。
Arkret v1 使用 `ak.session.grant` 作为 principal control stream 中的标准 durable control event 类型。

`ak.session.grant.payload` 示例：

```json
{
  "grant_id": "ak:grant:01964198-0000-7000-8000-000000000000",
  "realm_id": "ak:realm:01964198-7000-8000-8000-000000000000",
  "issuer": "did:webvh:z99jGJ9cd12QASVtC6r35kV5q:auth-gateway.example.com",
  "subject": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "session_public_key": "z6Mss...",
  "audience": "https://app.example.com",
  "scopes": [
    "ak.self.events.command.submit",
    "ak.realm.discover",
    "ak.object.read",
    "ak.strand.update",
    "ak.message.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-27T00:00:00Z"
}
```

> 注：`ak.session.grant` 是 principal control stream 事件，`realm_id` MUST 等于 subject 的
> principal control realm（§4.1）。本字段是 control event 必填项；省略 MUST 被 reducer
> 以 `schema_violation` 拒绝。

规则：

- session grant MUST 由可信 issuer 签名
- session key MUST NOT 超过 grant 的有效期
- session grant SHOULD 绑定 audience
- 在条件允许时，session grant SHOULD 在 WebCrypto / 平台 keystore 中以不可导出方式存储
- session grant 撤销 MUST 由下列 **canonical 撤销机制** 之一表达：accepted `ak.session.grant` 状态更新（含 supersede / expiry），或 device / account revoke（[`account-lifecycle.md` §9](./account-lifecycle.md) Session Revocation、§7.1 Deactivation Fanout 的 `ak.session.grant` 撤销链）。除上述 canonical 机制外，仅当某 extension / deployment profile **显式注册并声明** 了一个 credential status mechanism（profile MUST 给出该 mechanism 的 canonical event / 字段定义，对照 agent key 撤销的具体 `ak.agent.key.revoke`）时，方可使用该 profile 注册的机制表达撤销；未注册、无明确 canonical event / 字段定义的机制 MUST NOT 用于 session 撤销，且任何情况下 MUST NOT 使用未注册的 `ak:revocation-list:*` typed ID。

## 7. 密钥备份

### 7.1 备份内容

Arkret v1 将密钥备份分为三个不同密钥域。实现 MUST 在 metadata 中声明备份域，且不得把一个域的解锁材料当作另一个域的授权证明：

- `did_recovery`：恢复 DID 控制链所需的 root-generation metadata、guardian share metadata 或受信恢复服务证明。它只能用于 policy 允许的 DID update、`ak.device.reanchor` 与 recovery-policy handoff，不得直接签普通 `ak.device.authorize`。
- `secret_storage`：保存 `self_signing_key`、`user_signing_key`、MLS group secrets backup key、`account_data_namespace_key`、account-data value encryption 的 account secret、applet delegated device secret 和 encrypted private account data cache。`account_data_namespace_key` 属于 `secret_storage/account_data_namespace/v1` 子域，只用于 [`../models/account-data.md` §2](../models/account-data.md) 的 account-data key 派生，不得暴露给服务端或跨 principal 复用；account-data value key 则从可恢复的 32-byte account secret 按同文 §3 规定的 HKDF transcript 派生，两者用途不得互换。其中 A 模型**承载 SSK 的恢复定向副本**（`recipient_method="recovery_public_key"`）属于 fresh-device recovery-bootstrap unlock set，可在新设备授权之前由 backup-HPKE key 解锁（见 [`../crypto-media/device-lifecycle.md` §15](../crypto-media/device-lifecycle.md)）。B 模型没有 SSK，不得生成该副本；这不破坏域隔离——SSK 不解密 MLS 历史，攻破该副本不等于攻破 `mls_history` 或 `did_recovery`。
- `mls_history`：保存用户已有权读取的 Realm / MLS-backed Circle 的 MLS group state、历史 epoch key material、pending Welcome 和必要的 epoch 缺口恢复 metadata。

域隔离规则：

- 每个 `backup_kind` MUST 使用独立 salt、KDF context、HKDF info 和 AEAD associated data；一个域的 derived key、commitment key 或 wrap key 不得直接用于另一个域。
- AEAD AAD MUST 绑定 `actor_id`、`device_id`、`backup_kind`、`backup_version`、item type、created_at 和 schema/profile id，防止把 ciphertext 从一个域重放到另一个域。
- 即使用户选择同一个 passphrase，客户端也必须先用 KDF 得到 root unlock key，再用 `HKDF(root, info="arkret-key-backup/<backup_kind>/<subdomain>/v1")` 派生域内子密钥；不得复用裸 KDF 输出。
- `did_recovery` 域不得和 `mls_history` 域共享 wrap key、recovery share 或 key commitment。攻破 `mls_history` backup key 不得允许 DID rotate / recover；攻破 DID recovery share 也不得直接解密 MLS 历史。
- **组织 / Realm Recovery Key（RRK）属 history-recovery 域**：Realm `durability_policy` 引用的 RRK（[`identity-did.md` §8.3](./identity-did.md)、[`../models/realm-and-space.md` §2.3.1](../models/realm-and-space.md)）是 principal（通常为 Organization）持有的、用于解 Realm 历史的 HPKE 接收钥匙，与本域 `mls_history` 同性质而作用域为 Realm。它 MUST 独立于该 principal 的 `did_recovery` 钥匙：同一把 key MUST NOT 既作 `did_recovery` 又作 `ArkretRealmHistoryRecoveryKey`。RRK 私钥的离线保管 / 门限 / 硬件释放复用 §8 recovery policy（subject = 该 principal、域 = history-recovery）。
- `self_signing_key` / `user_signing_key` 与 MLS group secrets backup key MUST 分成不同 backup envelope 或不同 subdomain key，并 SHOULD 要求不同 passphrase、硬件保护或门限恢复策略。**单一 passphrase 同时控制身份签名和 E2EE 历史**的失败模式在任何部署上都不可接受。只有 `ak.profile.personal_node.v1` MAY 接受 `mixed_secret_storage=true` 的本地备份 envelope；`small_team`、`organization`、`high_security_organization`、`sovereign_deployment` 等 profile MUST 拒绝该 flag。mixed 模式若使用 `passphrase_kdf`，MUST 使用 Argon2id 且 `memory_kib >= 262144`、`iterations >= 4`、`parallelism >= 1`。

以下材料 MAY 进入客户端加密备份，但 MUST 只以密文形式保存：

- recovery key share 或门限 share。
- `self_signing_key` 与 `user_signing_key`。
- MLS group secrets backup key。
- MLS group state、历史 epoch key material、pending Welcome。
- encrypted private account data cache 和 private account state。

以下材料 MUST NOT 进入普通在线密钥备份：

- 当前设备的 device private key。新设备 MUST 本地生成新 device key，再由有效设备或 recovery policy 授权。
- Native Personal Agent 的 runtime private key。新 runtime MUST 本地生成新 key pair，再由 controller 通过 §3.6.1 `renew-pairing` / `pair_agent_key` 授权并原子替换旧 authorization；实现 MUST NOT 导出、克隆或把旧 runtime private key 包装进 `secret_storage`、`mls_history`、`did_recovery` 或产品自定义备份。
- session key、refresh token 或浏览器临时会话材料。
- 已发布或已领取的 MLS KeyPackage private key；设备 SHOULD 重新生成 KeyPackage。
- 明文 identity root seed、recovery secret、HKDF PRK 或完整派生 private key。高权限材料只能离线保存、硬件保护或门限封装；服务端不得解密。

备份 MUST NOT 以明文保存私钥。

### 7.2 Backup Envelope

标准备份对象使用 `ak.schema.key_backup.v1`。服务端只校验 envelope metadata、访问控制和签名，不得要求上传解锁口令、recovery private key、硬件解锁材料或任何可直接解密 ciphertext 的 secret。

示例：

```json
{
  "backup_id": "ak:backup:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
  "backup_kind": "secret_storage",
  "backup_version": "kb_1",
  "series_id": "ak:backup_series:01964137-1000-7000-8000-000000000000",
  "series_seq": 0,
  "created_at": "2026-04-26T00:00:00Z",
  "encryption": {
    "recipient_method": "passphrase_kdf",
    "kdf": {
      "name": "argon2id",
      "salt": "base64url...",
      "params": {
        "memory_kib": 65536,
        "iterations": 3,
        "parallelism": 1
      }
    },
    "aead": {
      "name": "xchacha20_poly1305",
      "aead_profile": "ak.aead.xchacha20_poly1305.v1",
      "nonce_salt": "b64uRandom128Bits",
      "nonce": "base64url..."
    },
    "key_commitment": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "domain_separation": {
    "hkdf_info": "arkret-key-backup/secret_storage/account_keys/v1",
    "subdomain": "account_keys",
    "aead_aad": {
      "schema": "ak.schema.key_backup.v1",
      "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
      "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
      "backup_kind": "secret_storage",
      "backup_version": "kb_1",
      "created_at": "2026-05-30T00:00:00Z",
      "item_kinds": ["self_signing_key", "user_signing_key"]
    }
  },
  "contents": [
    {"item_kind": "self_signing_key", "secret_id": "self_signing_key"},
    {"item_kind": "user_signing_key", "secret_id": "user_signing_key"}
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:2108421084217842908421084210842121084210842178429084210842108421",
  "auth_data": {
    "device_id": "ak:device:01964137-0000-7000-8000-000000000000",
    "signature": "base64url..."
  }
}
```

实现 SHOULD 使用现代 KDF，例如 Argon2id。新创建的 `recipient_method="passphrase_kdf"` envelope MUST 满足以下机器下限（base v1 无条件要求，`ak.schema.key_backup.v1` 同步编码）：Argon2id `memory_kib >= 65536`、`iterations >= 3`、`parallelism >= 1`；salt MUST 随 envelope 独立生成并进入 KDF 输入。
如果平台限制只能使用 PBKDF2，新创建的 PBKDF2 envelope MUST 满足 `iterations >= 600000` 且 `digest_algorithm ∈ {sha256, sha384, sha512}`，并 MUST 在 backup metadata 中声明 `degraded_profile_reason`、迭代次数、salt、KDF 参数和 profile id。`params.digest_algorithm` 是唯一合法的 digest 算法选择器；任何其它字段名均因 schema closed-world 校验而被 current parser 拒绝。新创建的 `passphrase_kdf` envelope（§7.5.1）不得默认使用 PBKDF2：Argon2id 可用时 MUST 优先。声明 `ak.profile.key_backup.memory_hard.v1` 是在上述 base 下限之上的更强承诺：该 profile 下 `passphrase_kdf` envelope 的 KDF MUST 是 Argon2id；PBKDF2 只允许出现在显式 degraded profile（见下）中，不满足 memory-hard 要求。

FIPS-only 部署若不能批准 Argon2id，MUST 使用显式降级 profile（例如 `fips_pbkdf2` key backup profile），并声明其安全级别低于默认 memory-hard backup profile。该 profile 至少要求 FIPS 批准的 KDF、强口令策略、在线恢复限速、失败审计和备份 metadata 中的 `degraded_profile_reason`；它不得作为公共网络默认 key backup profile。

每个 `ak.schema.key_backup.v1` envelope MUST 携带顶层 `domain_separation`，并在 `auth_data.signed_fields` 中覆盖该字段。`domain_separation.hkdf_info` MUST 等于 `arkret-key-backup/<backup_kind>/<subdomain>/v1`，`domain_separation.aead_aad` MUST 绑定 `schema`、`actor_id`、`device_id`、`backup_kind`、`backup_version`、`created_at` 与 `contents[].item_kind`；存在 §7.5.6 managed Agent PCR item 时还 MUST 绑定全部 `managed_principal_binding` canonical set。顶层 `device_id` 是可选字段：envelope 若无发起设备，`aead_aad.device_id` MUST 绑定 `null`，MUST NOT 省略该键，也 MUST NOT 代之以空字符串——AAD transcript 的字段集恒定，sealer 与 opener 才能逐字节重建同一个对象（KAT 见 `artifacts/fixtures/key-backup-hardening-fixture.json` 的 `secret_storage_no_device` 用例）。接收方 MUST 用该对象的 canonical JSON 作为 AEAD/HPKE AAD，并验证它与外层 envelope 及解密后 keybag 字段逐字节一致；服务端不得生成、修改或补全该对象。该对象即本 domain 在 [`../conformance/encoding.md` §10.2](../conformance/encoding.md) 意义上的 **pre-encryption immutable header**：其全部字段在 AEAD/HPKE seal 前已确定。`ciphertext_digest` 与 `key_commitment` 是 post-encryption commitment，MUST NOT 出现在 `domain_separation.aead_aad` 中；它们的真实性由 `auth_data.signed_fields` 覆盖的设备签名承担（§7.4）。

`key_commitment` 的推荐构造（`commitment` 是 §7.1 `arkret-key-backup/<backup_kind>/<subdomain>/v1` 体系下的一个 subdomain，因此 commitment 天然按 `backup_kind` 域隔离，不会跨域复用）：

```
derived_key = KDF(passphrase, salt, kdf_params)
commitment_key = HKDF(derived_key, info="arkret-key-backup/<backup_kind>/commitment/v1")
key_commitment = SHA256(commitment_key)
```

`recipient_method="passphrase_kdf"` 的 AEAD nonce MUST deterministic derive，但 derivation transcript MUST 包含 producer-generated `aead.nonce_salt`。`nonce_salt` 是随 envelope 新生成的至少 128-bit 随机值，不是 secret，必须进入 signed metadata / AAD；服务端不得生成、覆盖或由用户输入提供该值。

```text
nonce_key = HKDF(derived_key, info="arkret-key-backup-aead-nonce-v1")
nonce = HMAC-SHA256(
  key  = nonce_key,
  data = canonical_json({
    "backup_id": backup_id,
    "actor_id": actor_id,
    "device_id": device_id,
    "backup_kind": backup_kind,
    "backup_version": backup_version,
    "created_at": created_at,
    "aead": aead.name,
    "aead_profile": aead.aead_profile,
    "nonce_salt": aead.nonce_salt
  })
)[0:N_AEAD]
```

**澄清（防误读）**：`nonce_key` 的 info 为固定值不构成 §7.1 的跨域密钥复用——§7.1 禁止跨域的是 derived key、commitment key 和 wrap key；`nonce_key` 只用于 nonce 推导，且推导 transcript 已绑定 `backup_kind`，nonce 输出本身按域隔离。该 info 在 interop 关键路径上（接收方 MUST 重算 nonce），不得变更。

`aead_profile` 是可选但推荐的协商标识，绑定 AEAD 算法版本、nonce 长度、tag 长度、key 长度和 AAD 构造。接收方看到不支持的 `aead_profile` MUST fail closed；不得只凭 `aead.name` 推断可接受的参数组合。未携带 `aead_profile` 的 envelope 按 `aead.name` 的 v1 默认 profile 解释，但新写入 envelope SHOULD 显式携带 profile id。

Producer MUST reject attempts to write two backup envelopes with the same nonce derivation tuple, including `nonce_salt`。`backup_id` 仍应按单写不可变处理；若需要更新备份内容，producer MUST 生成新的 `backup_id` 或至少新的 `nonce_salt` 并重新签名 envelope。Receiver MUST recompute the nonce for `passphrase_kdf` envelopes before decryption and reject mismatches or missing `nonce_salt` as `schema_violation`.

客户端 MAY 在尝试解密 `ciphertext` 前用用户输入的 passphrase 派生 key，计算 commitment 并与 envelope 中的 `key_commitment` 比对。不匹配时 MUST 拒绝解密并提示用户 passphrase 错误。`key_commitment` 只是本地快速拒绝错误口令和防止密文替换的辅助值，不是服务端认证材料；服务端不得要求用户上传 passphrase、derived key、commitment key 或使用 `key_commitment` 做在线口令检查。**澄清（防误读）**：该禁令针对的是"服务端获得可离线验证口令的材料"；它**不禁止** aPAKE 形态的协议（如 OPAQUE，RFC 9807）——aPAKE 的设计不变量恰是服务端永不见口令也无法预计算字典，与本条约束相容。离线攻击者仍可对备份执行 KDF 级别的口令猜测，因此实现必须执行强口令策略、Argon2id 参数下限和速率受控的恢复 UI。

> **路线图注记（informative，2026-06 评审采纳）**：对低熵口令的已声明残余风险（离线无限猜测），已识别的增量缓解方向是 **OPAQUE（RFC 9807）/ HSM·TEE 限速恢复服务**（Signal SVR、WhatsApp HSM vault 形态）：把暴露面从"离线无限猜"压缩为"在线限速猜"，且服务端攻破不可预计算。引入形态为与 `passphrase_kdf` **并存**的新 recipient_method（schema 枚举加法，不替代离线兜底），recovery service 的 attestation 要求可复用既有 audit-release attestation 框架。本注记不预注册 method 名或 profile id；待实现计划成立时按加法引入。

域隔离 profile 的 conformance proof MUST 至少证明：不同 `backup_kind` / subdomain 的 HKDF info 不同、AEAD AAD 覆盖域和 item type、key commitment 不能跨域复用、恢复流程不会把一个域的解锁成功当作另一个域的授权证明。

`ciphertext_digest` 覆盖密文字节，`plaintext_commitment` 若存在只用于本地完整性或跨设备一致性检查；服务端不得要求知道明文 hash 才能存储或返回备份。

### 7.3 恢复流程

恢复流程：

1. 新设备生成 device key。
2. 用户输入 Recovery Key（24 词助记词，§3.3），或按 recovery policy 收集 recovery shares / 完成硬件解锁；仅当目标是 `passphrase_kdf` envelope 时才输入对应口令（§7.5.1）。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `ak.device.authorize`。
6. 若涉及 E2EE Realm，客户端拉取 MLS state 并处理 epoch 缺口。

恢复 device key 时 MUST 生成新的 device key，不得把备份中的旧设备身份克隆到新设备。恢复出的 `self_signing_key` / `user_signing_key` 可用于重建 cross-signing 状态，但 Cross-Signing Reset 仍必须满足 `device-lifecycle.md` 的高风险证明要求。

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

`auth_data.signature` 由上传设备的 device signing key 产生（`auth_data.verification_method` 指向该 device key）。仅设备签名只能证明“某个持有该 device key 的实体写了它”，无法独立抵御**恶意服务器联合一个被攻破 / 已撤销的旧 device key 注入或替换备份 envelope**。因此 receiver 在信任并使用一条 backup envelope（恢复或读取）前 MUST 把该签名锚定到 actor 当前 accepted 设备信任根：

- receiver MUST 验证 `auth_data.verification_method` 指向的 device key 属于该 actor 当前 accepted、未撤销的设备投影，并且该 device key 验证 `auth_data.signature` 覆盖的 canonical envelope；
- cross-signing 设备路径：envelope MUST 携带对签发该设备授权的 self-signing key 代际的绑定（`auth_data.ssk_generation`）。这里的 `ssk_generation` 与 `ak.device.authorize.payload.cross_signing_binding.ssk_generation`、`ak.cross_signing.publish.generation` 是同一 cross-signing 代际计数（reset 时 `generation += 1`），其权威定义与单调性规则见 [`../crypto-media/device-lifecycle.md` §5](../crypto-media/device-lifecycle.md)（cross-signing publish）与 [`§14`](../crypto-media/device-lifecycle.md)（cross-signing reset / generation 推进）。receiver MUST 拒绝代际早于当前 published generation 且超出 rotation grace window 的 envelope（`stale_backup_trust_generation`）；
- service-attested / enrollment-authority 设备路径（见 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md)）：envelope MUST 携带 `auth_data.device_authorize_event_id`，且该值 MUST 等于该 `auth_data.device_id` 当前 accepted 的 `ak.device.authorize` event id。receiver MUST 使用该设备投影中的 `payload.device_public_key` 验证 `auth_data.signature`；`auth_data.ssk_generation` 在此路径 MUST 缺失，因为 account authority 不持有、不得伪造本 principal 的 SSK；
- `auth_data.ssk_generation` 与 `auth_data.device_authorize_event_id` MUST 精确二选一。二者同时存在、同时缺失、设备未授权、设备已撤销、代际不符、授权事件不符或签名验不过的 envelope MUST 被视为 `untrusted_backup_signature`（代际过旧时可用 `stale_backup_trust_generation`）并拒绝用于恢复，即使其 series 链与 `ciphertext_digest` 自洽。
- **高敏 backup_kind 的信任锚强制存在（normative）**：对 `backup_kind ∈ {secret_storage, did_recovery}` 这两类高敏备份，receiver MUST fail closed，MUST NOT 退回到"device key 在 `created_at` 时点是否有效"的较弱判定接受它用于恢复或读取。即：core 档下 `secret_storage` / `did_recovery` envelope 必须携带上述两个合法信任锚之一，使恶意服务端联合旧 / 已撤销 device key 注入的高敏备份无法绕过信任根比对。`mls_history` 类也必须满足本节签名锚定；其 freshness / frontier 强化仍按各档 hardening profile 策略处置。

这样 envelope 的真实性锚定在 actor 当前设备信任根，而不是“碰巧持有某个 device key”，与 series 链（§7.6，防回滚 / 扣留）正交：前者保证 authenticity，后者保证 freshness / 单调性。

> **Schema 影响**：`ak.schema.key_backup.v1.auth_data.ssk_generation` 绑定 [`ak.cross_signing.publish`](../crypto-media/device-lifecycle.md) 的 `generation`（见 [`../crypto-media/device-lifecycle.md` §5](../crypto-media/device-lifecycle.md)）；`ak.schema.key_backup.v1.auth_data.device_authorize_event_id` 绑定 [`ak.device.authorize`](../crypto-media/device-lifecycle.md) 的 accepted event id（见 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md)）。二者 MUST 精确二选一；任何未声明的 `auth_data` 字段 MUST 因 closed-world schema 校验以 `schema_violation` 拒绝。

### 7.5 Recipient Method Profiles

`ak.schema.key_backup.v1.encryption.recipient_method` 枚举 3 种 envelope 解锁方式。每种方式 MUST 按下列 normative 约束实现；服务端遇到本节未定义的 `recipient_method` MUST fail closed。

#### 7.5.0 `backup_kind` × `recipient_method` 合法组合矩阵（normative）

`backup_kind`（仅 `did_recovery` / `secret_storage` / `mls_history` 三类，§7.1）与 `recipient_method` 的组合不是自由叉乘。下表是合法组合的**集中**声明；producer MUST NOT 写入标 `forbidden` 的组合，receiver / 服务端遇到 `forbidden` 组合或本表未列出的组合 MUST fail closed（reason 见各格），即作为兜底也不允许：

| `backup_kind` ＼ `recipient_method` | `passphrase_kdf` | `recovery_public_key` | `secret_storage_key` |
| --- | --- | --- | --- |
| `did_recovery` | forbidden: `did_recovery_passphrase_forbidden` | allowed: MUST 带顶层 `recovery_policy_ref{policy_id, policy_version}` == 当前 accepted recovery policy，否则 `recovery_policy_mismatch` | forbidden: `did_recovery_secret_storage_key_forbidden`（DID recovery 不得依赖 device-local secret storage root） |
| `secret_storage` | allowed（见 §7.5.1）: §7.2 / §7.5.1 Argon2id 或显式 degraded PBKDF2；新创建 envelope 满足 §7.2 机器下限 | allowed（新写入 SHOULD 优先，见 §7.5.1） | allowed: 仅现有持有 root key 的设备本地缓存/同步，新设备 MUST NOT 直接 bootstrap，否则循环依赖 |
| `mls_history` | forbidden: `mls_history_passphrase_forbidden` | allowed：MUST 带签名覆盖的 `recovery_policy_ref` | allowed：释放仍以 active-series record / frontier_ref / Realm-MLS 授权 / 设备状态为准 |

集中要点（与下列 §7.5.1–§7.5.5 的分散规则一致，本表为 normative summary）：

- **`passphrase_kdf` 仅 `secret_storage`**：`did_recovery` 与 `mls_history` MUST NOT 使用 `passphrase_kdf`，即便作为 fallback 也不允许（单一口令不得直接控制 DID recovery 或解锁 MLS 历史）。需要口令参与时，口令只能先解锁 `secret_storage` root、recovery private key、threshold share 或 hardware wrapper 的本地保护层，再由 `recovery_public_key` / `secret_storage_key` 完成对应 `backup_kind` 的释放。
- **`did_recovery` 只能用 `recovery_public_key`**：`did_recovery` 的唯一合法 `recipient_method` 是 `recovery_public_key`。envelope 顶层 `recovery_policy_ref{policy_id, policy_version}` MUST 等于当前 accepted `ak.schema.recovery_policy.v1`，并进入 `auth_data.signed_fields`；不一致 MUST `recovery_policy_mismatch`（fail closed）。
  - **recovery 私钥释放强度（normative 澄清）**：本矩阵在 envelope 层禁止 `did_recovery` 用低熵口令派生（`passphrase_kdf` / `secret_storage_key`），确保 DID recovery 不被单一**低熵**口令直接控制。recovery **私钥本身**的释放强度由 §8 recovery policy 的 `allowed_proof_kinds` 决定：当 policy 仅配置单个 `recovery_unlock`（单把高熵 24 词助记词签名）时，恢复强度即等同于该单一高熵助记词——这是 v1 default profile **有意接受**的取舍（高熵单因子 ≠ 低熵口令）。高价值 / 组织账号 SHOULD 按 §7.11（"高价值账号 SHOULD 支持门限恢复"）对 `did_recovery` 释放叠加门限（`threshold_recovery`）或多 `proof_kind`，不依赖单一可窃取秘密。
- **`secret_storage_key` 不可 bootstrap**：新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap，必须先用 `passphrase_kdf` 或经 recovery policy 释放的 `recovery_public_key` 解出 root secret storage key（消除"新设备能解 wire envelope"的循环依赖）。
- **门限/硬件属于 recovery policy 层**：threshold、hardware module、trusted recovery service 可以保护 recovery private key 或 secret storage root 的释放，但不得作为 `ak.schema.key_backup.v1.encryption.recipient_method`。相关 proof transcript 由 §8 recovery policy 与 `ak.schema.recovery_session.v1` 约束。
- 所有 fail-closed 判定 MUST 在解密尝试之前完成；服务端 / receiver 不得对 `forbidden` 组合"先解密再检查"。

#### 7.5.1 `passphrase_kdf`

参考 §7.2：Argon2id（或显式 degraded PBKDF2）派生 root key，HKDF 派生 `commitment_key` 与 `nonce_key`，AEAD AAD 覆盖全部 envelope metadata。`passphrase_kdf` 仅用于 `secret_storage` envelope；`mls_history` 与 `did_recovery` envelope MUST NOT 使用 `passphrase_kdf`，即使作为 fallback 也不允许。需要用户口令参与 DID recovery 或 MLS 历史恢复的实现 MUST 让口令先解锁 `secret_storage` root、recovery key、threshold share 或 hardware wrapper 的本地保护层，而不是在 wire 上发布 `backup_kind="mls_history"` / `backup_kind="did_recovery", recipient_method="passphrase_kdf"` 的 envelope。

**与 recovery secret 的关系（normative）**：内容恢复的标准用户凭证是 §3.3 recovery secret；它经固定域派生 backup-HPKE key。实现 SHOULD NOT 引入独立 vault 口令作为标准凭证。

- 新写入的 `secret_storage` envelope SHOULD 使用 `recipient_method="recovery_public_key"`（加密给 §3.3 backup-HPKE public key）；`passphrase_kdf` envelope MAY 用于实现自选的口令派生场景。
- `passphrase_kdf` 是合法 wire `recipient_method`：服务端 key-backup 端点（§7.8、[`../crypto-media/device-lifecycle.md` §12.1](../crypto-media/device-lifecycle.md)）不区分凭证来源，`passphrase_kdf` envelope MUST 可被列出、读取与删除，本节与 §7.2 的 KDF / nonce / commitment 约束对其适用。

#### 7.5.2 `recovery_public_key`

DEK 通过 HPKE（base mode）加密给 `recovery_public_key`：

- `recipient_key_ref` MUST 是 envelope 的 `recovery_policy_ref` 所指 accepted recovery policy（§8）中 `recovery_key_agreements[].key_agreement_ref`。DID Document-only `recoveryKeyAgreement` 不是授权源，MUST reject。该 ref MUST NOT 指向 `recovery_keys[].verification_method`：后者只标识 recovery-proof 签名 key。receiver 必须从同一 policy entry 取得 X25519 `public_key_multibase`，并确认 `encryption.hpke_suite` 在该 entry 的 `hpke_suites` 中。
- HPKE suite MUST 是 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active 行，由 `encryption.hpke_suite` 选定；该字段缺省时 MUST 解释为 default-MUST 行 `ak.hpke_x25519_aead_chacha20poly1305.v1`。`aead.name` MUST 等于所选 suite 的 AEAD。遇到未登记、非 active 或 reserved-未激活的 suite id，receiver MUST fail closed（`unsupported_hpke_suite`），MUST NOT 自由组合未登记的 KEM/KDF/AEAD，也 MUST NOT 仅凭 `aead.name` 推断 suite 参数。P-256 KEM 互操作经 profile-gated 行 `ak.hpke_p256_aead_aes256gcm.v1`（`ak.profile.hpke.p256.v1`）提供。HPKE 单发 base-mode 由 key schedule 内部派生 AEAD nonce，故 `recovery_public_key` envelope 不携带 wire `nonce`。
- HPKE `info` MUST 包含 `canonical_json({backup_id, series_id, series_seq, actor_id, backup_kind, backup_version, created_at})`；HPKE `aad` MUST 等于 envelope 的 AEAD AAD。
- 普通 DID root generation 轮换不改变 backup-HPKE key。只有 recovery secret handoff 才改变 recipient key；handoff 后所有 active backup class MUST 按 §3.3 建新 series/重封装并推进 signed active-series pointer。
- 任何 `recipient_method="recovery_public_key"` envelope 都 MUST 携带 `recovery_policy_ref{policy_id, policy_version}` 并由 `auth_data.signed_fields` 覆盖；`recipient_key_ref` 只在该 accepted policy 的 `recovery_key_agreements[]` 中解析。`backup_kind="did_recovery"` 时该 ref 还 MUST 等于当前 active policy；其它 backup class 在读取/恢复时也必须验证 referenced policy 仍属于该 principal 的 accepted policy history，并按 active-series 与轮换规则拒绝回滚。不匹配 MUST `recovery_policy_mismatch`。这项 policy 绑定不替代 MLS 历史或 secret-storage 的独立授权判断。
- **备份接收 key 的角色隔离（normative）**：wire 名称 `recovery_public_key` 指 §3.3 派生的 X25519 backup-HPKE public key。它与 Ed25519 recovery-proof key、任一代 identity root 是不同 key，但三者来自同一用户 recovery secret。实现 MUST NOT 在 `secret_storage` 中再制造第四把长期 backup keypair，也不得把 Ed25519 key 转换成 X25519 key。

recovery policy 中两类 key 必须显式配对：`recovery_keys[]` 每项携带 recovery-proof 签名 `public_key_multibase` 与独立 `key_agreement_ref`；该 ref 必须唯一解析到同一 policy 的 `recovery_key_agreements[]`。后者 `use="backup_hpke"`，只能接收备份，不能验 recovery proof 或授权 DID/Event。两数组与配对 ref 均进入 `auth_data.signed_fields`；缺项、悬空或重复 ref、同一 key material、suite 不匹配、已撤销/过期、DID Document-only 旁路均 fail closed，并由 `ak.vector.identity.recovery_key_role_separation.v1` 执行验证。

#### 7.5.3 `secret_storage_key`

仅用于已经持有 `secret_storage` root key 的现有设备本地缓存/同步（不是 bootstrap）。

- `recipient_key_ref` MUST 命名一个已经在该设备 device-local secret storage（参见 `crypto-media/device-lifecycle.md` §11 `ak.secret_storage.v1`）中存在的 key id（例如 `mls_group_secrets_backup_key`）。
- 当 `backup_kind="mls_history"` 使用 `secret_storage_key` 时，envelope MAY 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 作为恢复流程 hint；若出现，`auth_data.signed_fields` MUST 覆盖它，receiver MUST 验证它与当前 accepted recovery policy 一致。MLS 历史材料的释放仍以 active-series record、frontier_ref、Realm/MLS 授权与设备状态校验为准。
- 新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap：它必须先经 recovery policy 接受 recovery proof，再由用户 recovery secret 派生 backup-HPKE private key以打开 `recovery_public_key` envelope，之后才能拉取 `secret_storage_key` envelope。
- 这是为了消除"新设备能解 wire envelope"的循环依赖。
- **AEAD nonce 唯一性（normative）**：`secret_storage_key` 是长期复用的对称 wrap key，因此 `aead.nonce` MUST 在该 `recipient_key_ref` key 的整个生命周期内对每条 envelope 唯一——producer MUST 为每条新 envelope 生成至少 96-bit 的随机 nonce（或在该 key 下严格单调不回绕的 counter），且 MUST NOT 用同一 (`recipient_key_ref` key, `aead.nonce`) 对写第二条 envelope；需要更新内容时 MUST 生成新 `backup_id` 与新 `nonce`，并 SHOULD 轮换底层 wrap key。`nonce` 进入 `auth_data.signed_fields` 覆盖的 AEAD AAD（§7.4）。该约束与 `passphrase_kdf` 的 `nonce_salt` deterministic derivation（§7.5.1）、`recovery_public_key` 的 HPKE 内部 nonce 派生共同关闭三种 `recipient_method` 的 nonce-reuse 面。

#### 7.5.4 门限恢复作为 recovery policy 层

v1 core 不把 `threshold_recovery` 作为 `ak.schema.key_backup.v1.encryption.recipient_method`。门限恢复在 policy 层重建/释放 recovery secret 或明确的 backup-HPKE key material；客户端随后用 `recovery_public_key` 或 `secret_storage_key` 解开 envelope。

- 每份 share 的取回 MUST 绑定当前 recovery 流程的 `recovery_session_id`（见 [`../crypto-media/device-lifecycle.md` §15](../crypto-media/device-lifecycle.md)）；holder 服务 MUST NOT 把同一 share 多次释放给不同 session 而不经显式授权。
- reconstruction 完成的 recovery secret、PRK 或任一派生 private key MUST NOT 写入在线持久化存储；上下文在用途结束后立即清除。
- share commitment 校验：reconstruction 前 client / recovery coordinator MUST 验证每份 share 与 `recovery_policy.threshold.shares[].share_commitment` 一致；失败时 MUST `share_commitment_mismatch` 并通知用户特定 holder 提交了 invalid share。

#### 7.5.5 硬件包装作为 recovery policy 层

v1 core 不把 `hardware_wrapped_key` 作为 `ak.schema.key_backup.v1.encryption.recipient_method`。硬件模块、HSM、TPM 或 Secure Enclave 只能作为 recovery policy unlock factor：它们释放 recovery secret、threshold share、backup-HPKE key 或 secret-storage root 的本地保护层。

- recovery policy MUST 记录被信任的 hardware / service profile、wrap key 稳定标识与 attestation 要求；proof transcript MUST 绑定 `recovery_session_id` 与当前 challenge。
- receiver MUST 验证当前的 hardware attestation evidence 仍声明同一 key id（即设备未在静默状态下被替换），并且该 profile 属于当前 accepted recovery policy。
- 任何 envelope 单纯展示 `recipient_method=hardware_wrapped_key` MUST 被 schema/receiver 拒绝为未知枚举值；缺少 attestation chain 的 recovery proof MUST `attestation_missing`。

#### 7.5.6 Managed Agent PCR recovery（normative）

Conformance vector：`ak.vector.agent.managed_pcr_recovery.v1`。

`ak.profile.personal_agent_provisioning.v1` 下的 Native Personal Agent 没有独立人类用户，因此不得复制普通用户的“每 principal 一套 24 词”交互。Agent PCR 的 MLS 可恢复状态 MUST 由 controller 以自己的 `actor_id` 写入 controller-owned `backup_kind="mls_history"` series；这不是 controller 跨 actor 读取 Agent backup，§7.8 的跨 actor 拒绝保持不变。controller 的 Recovery Key（24 词、门限或硬件释放）只解锁该 controller 自己的 envelope，envelope 内被授权托管的 Agent PCR item 通过 `managed_principal_binding` 标明来源。

每个承载 Agent PCR `mls_group_state` / `mls_epoch_secret` / `pending_welcome` 的 public `contents[]` item 与解密后的 plaintext item MUST 携带逐字一致的 `managed_principal_binding`：

- `managed_principal_id` MUST 等于 Agent DID；`principal_control_realm_id` MUST 等于该 Agent DID accepted-at `ArkretPrincipalControlRealm.serviceEndpoint.realm_id`。
- `controller_id` MUST 等于外层 backup `actor_id`；`authorization_ref` MUST 等于同一 service binding 的 delegation DID URL，且该 delegation 在 envelope `created_at` 时覆盖 `principal_control_realm_recovery`。
- `managed_frontier_ref{frontier_digest, seal_ref, mls_epoch}` MUST 指向该 Agent PCR 已 accepted 且被 Seal 覆盖的 frontier；item 的 `realm_id` / `epoch` MUST 分别与 binding 的 PCR / MLS epoch 一致。未被 accepted Seal 覆盖的本地 tentative state 不得标为可恢复。
- `domain_separation.hkdf_info` / `subdomain` MUST 分别为 `arkret-key-backup/mls_history/managed_agent_pcr/v1` / `managed_agent_pcr`；`domain_separation.aead_aad.managed_principal_bindings[]` MUST 是 envelope `contents[]` 中全部 distinct binding 的 canonical set（按 canonical JSON bytes 升序、无重复），并与解密后 keybag 中出现的 binding set 完全一致。遗漏、多余、顺序错误、外层/明文不一致或跨 Agent/PCR transplant MUST fail closed。
- envelope MUST 使用 `recipient_method="recovery_public_key"`，`recipient_key_ref` MUST 逐字等于 controller 当前 accepted recovery policy 中一个 current、未撤销、`use="backup_hpke"` 且允许所选 HPKE suite 的 `recovery_key_agreements[].key_agreement_ref`；该 entry 的 X25519 public key 必须与本地 Recovery Key 派生的 recipient key 逐字一致。producer MUST 从 signed policy body 选择该 ref，不得合成 `<controller>#recovery` 或把 recovery-proof signing ref 当 recipient。envelope 还必须携带等于 controller 当前 accepted policy 的 `recovery_policy_ref`。不得把 Agent runtime key、Agent 独立 mnemonic、服务端可解密 wrapper 或 `secret_storage_key`-only 副本作为此恢复路径。active-series Event 的 `issued_at` 与 backup `created_at` 都 MUST 使用统一 canonical UTC 毫秒 profile `YYYY-MM-DDTHH:MM:SS.sssZ`；业务若只需整秒，先截断值再以 `.000Z` 序列化，不得引入无小数 grammar。

一个 controller 的 `mls_history` series MAY 同时承载其自身 Realm state 与多个 managed Agent PCR item；每个 managed item 独立携带 binding，AAD 列表覆盖全部 binding。producer MUST 在签名上传前本地解密回读并验证 plaintext keybag 与 public `contents[]` / AAD binding set 一致；签名上传即是该 producer 对这项自检的声明，服务端仍不得索取明文或解密密钥。服务端只依据已接受 envelope 的签名、公开 metadata、active-series 尾部、current recovery policy / delegation 与可验证 Seal/MLS frontier 投影状态：仅当目标 Agent PCR 当前 `mls_group_state` 及上述条件全部通过时为 `pcr_recovery.status="ready"`；无备份为 `pending`，policy、delegation、PCR Seal 或 MLS epoch 前进后尚未产生新尾部 envelope 为 `stale`。解密恢复时 receiver MUST 再独立执行 plaintext 一致性校验，失败不得导入。首次及 replacement runtime pairing 均以 §3.6.1 的 ready gate 为准。

controller fresh-device recovery 仍先完成自己的普通 §7.3 / `device-lifecycle.md` §15 流程，再解开 controller-owned `mls_history` active series，恢复 Agent PCR group state，最后按当前 delegation 重发 MLS Welcome 或提交新的 controller-authored Agent PCR Event。恢复不得复活 superseded Agent runtime key；runtime 丢钥只走本地新生 key + re-pairing。controller recovery policy 轮换时 MUST 按 §9.1 为包含 managed Agent PCR item 的 `mls_history` 开新 series 并重新加密所有仍 active 的 binding。Agent deactivation 或 controller delegation 终止后，producer MUST 在新 series 中排除对应 item，确认新 series 可恢复后按 retention 删除旧 series；这不能撤回旧 controller 已经合法下载的历史 plaintext，UI / audit MUST 明示该不可挽回边界。

### 7.6 Backup Series & Freshness

服务端是不可信存储；攻击者控制服务端时，可以静默返回**旧**版本 envelope 让恢复设备解出已经 retired 的密钥。`ak.schema.key_backup.v1` 通过 `series_id` / `series_seq` / `supersedes` / `supersedes_digest` / `frontier_ref` 链堵塞这一点。

要求：

- `series_id` 是 `ak:backup_series:<uuid>` typed-id。每个 `series_id` MUST 只属于一个 `(actor_id, backup_kind)`，但同一 `(actor_id, backup_kind)` MAY 在密钥泄露轮换或迁移过渡期拥有多个 series。常规状态下只能有一个 active series；当前 active series MUST 由下方 `ak.schema.key_backup_active_series.v1` signed active-series record 选择，不得由服务端返回顺序推断。
- 新 envelope MUST 满足 `series_seq == prev.series_seq + 1`；`supersedes` MUST 是同 `series_id` 中上一条 envelope 的 `backup_id`，且 `supersedes_digest` MUST 等于上一条 envelope 排除 `auth_data.signature` 后 canonical_json 的哈希。
- genesis envelope MUST `series_seq == 0`，且 MUST NOT 携带 `supersedes` 或 `supersedes_digest`。
- `auth_data.signed_fields` MUST 覆盖 `series_id` / `series_seq`；非 genesis envelope 还 MUST 覆盖 `supersedes` 与 `supersedes_digest`，携带 `frontier_ref` 时还 MUST 覆盖 `frontier_ref`（schema 已在 `signed_fields.allOf.contains` / 条件分支中强制）；服务端 MUST NOT 替换这些字段。
- `frontier_ref` 是 RECOMMENDED 字段；当声明 `ak.profile.key_backup.memory_hard.v1` 或更高 hardening profile 时，`secret_storage` 与 `did_recovery` 类备份的新 envelope MUST 携带 `frontier_ref.frontier_digest`，并 SHOULD 携带 `frontier_ref.seal_ref`。generation 字段精确二选一：A 模型为 `frontier_ref.ssk_generation`，B 模型为 `frontier_ref.device_generation_ref`。
- **`mls_history` 释放的 frontier 校验为 MUST（normative，非 `personal_node` profile）**：除 `personal_node` profile 外，`mls_history` 类备份的释放 MUST 校验 active-series record，并验证 envelope 的 `frontier_ref`（`frontier_digest`，可达时连同 `seal_ref` 与对应 A/B generation）与当前 accepted control-stream frontier 一致。B 模型还必须要求 `device_generation_status="active"` 且 `device_generation_ref == current_device_generation_ref`；缺失 active-series record 或 frontier/generation 校验不通过时 MUST fail closed。
- **Active-series record**：当某 `(actor_id, backup_kind)` 存在多个 series，或实现需要向新设备声明 canonical series 时，principal control stream MUST 发布 event kind `ak.key_backup.active_series`，payload MUST validate as `ak.schema.key_backup_active_series.v1`。该 record MUST 至少绑定 `schema`、`actor_id`、`backup_kind`、`active_series_id`、`series_pointer_version`、`issued_at`、`previous_series_ids[]`、`frontier_ref{frontier_digest, seal_ref?, ssk_generation|device_generation_ref}` 与签名 `auth_data`。A 模型 `auth_data.ssk_generation` 必须等于当前 SSK generation；B 模型 `auth_data.device_authorize_event_id` 必须解析到 current device generation 中的签名设备，且 `frontier_ref.device_generation_ref` 等于 `current_device_generation_ref`。两类字段不得混用。`series_pointer_version` 按 `(actor_id,backup_kind)` 从 1 开始严格单调，每条 successor MUST 等于前值 + 1；同版本不同内容为 fork，版本跳跃为链缺口，均 fail closed。`active_series_id` MUST 指向同 `(actor_id, backup_kind)` 下的 genesis 或 successor series；`previous_series_ids[]` 只用于 retention / read-old-data 过渡，不得作为 primary recovery source。Receiver MUST 取已验证的最高 pointer version；设备/恢复材料 MUST 持久化自己已见最高版本，服务端返回更低版本时拒绝 `backup_frontier_stale`。首次恢复且本地无最高版本时，receiver MUST 通过 control-stream completeness proof / witness 验证该 record 是当前最高版本，不能只信列表顺序。Envelope 自身的 `frontier_ref` 只证明该 envelope 创建时的 control-stream 位置，不能替代 active-series record。
- 客户端发起恢复（device-lifecycle.md §15）时 MUST：
  1. 若恢复方未持有已验证的 `series_id`，先从 principal control stream 解析并验证 active-series record，取得 `active_series_id`；然后 `LIST /_arkret/self/keys/backups?series_id=<active_series_id>` 取回**全部** envelope metadata；
  2. 按 `series_seq` 重建链，验证每条 `supersedes` / `supersedes_digest` 正确；任一 envelope 缺失或 hash 不匹配 → MUST `series_chain_broken`；
  3. 用链的**最尾**条进行解密；任何中间条目 MUST NOT 被用作主恢复源；
  4. 当存在 `frontier_ref` 时 MUST 用 control stream snapshot 验证 `frontier_digest` 落入当前 principal control stream，并验证 A 模型 `ssk_generation` 等于当前 accepted generation，或 B 模型 `device_generation_ref` 等于 active `current_device_generation_ref`；否则 MUST `backup_frontier_stale`。
- 服务端 MUST 把同一 series 内的删除视为高风险动作（参见 `crypto-media/device-lifecycle.md` §12.1）：active series 内的非尾部 envelope MUST NOT 被单独删除；删除尾部 envelope 等同于让 series 失效，MUST 在 audit 中可见。旧 series 只能按 retention / erasure 规则整组迁移或整组删除，不能留下断链作为可恢复来源。

### 7.7 Recovery UI Requirements（normative）

恢复 UI 是用户唯一能识别"我在恢复一个真实的自己 vs 我在被钓鱼"的界面。实现 MUST：

- 密钥备份解密凭证 MUST 是 Recovery Key（24 词 BIP-39 助记词，§3.3）：由其派生 / 解锁 recovery private key 后按 §7.5.2 HPKE-open `recovery_public_key` envelope，或按 recovery policy（§8）以 threshold / hardware 因子释放同一 recovery private key。恢复 UI MUST NOT 要求用户设置独立 vault passphrase 作为标准凭证；仅当目标 envelope 是 `passphrase_kdf`（§7.5.1）时，MAY 提示输入对应口令完成解密，并 SHOULD 在恢复成功后引导写入加密给 recovery key 的新 envelope（§7.5.2，按 §7.6 series 规则开新链或追加）。
- 在尝试解密任何备份 envelope 之前，向用户展示：`backup_kind`、`series_id`、`series_seq`、`backup_version`、`encryption.recipient_method`、`encryption.aead.aead_profile?`（缺省时显示 `aead.name`）、`principal_id`、`device_id`（当前请求恢复的新设备）、以及 A 的 `frontier_ref.ssk_generation` 或 B 的 `frontier_ref.device_generation_ref`。
- 在使用 `passphrase_kdf` 时，明确展示 KDF（Argon2id / PBKDF2）与参数；用 PBKDF2 的 envelope MUST 在 UI 中显示 `degraded_profile_reason`，且不得自动选用 PBKDF2 envelope 当 Argon2id envelope 同时存在。
- 在 envelope 携带 `mixed_secret_storage=true` 时 MUST 显著警告"该备份同时保护身份签名与 E2EE 历史，单一口令被攻破将同时丢失两者"；非 `personal_node` profile 下 MUST 直接拒绝展示此类 envelope 作为 primary recovery source。
- 在 `did_recovery` 域使用 `passphrase_kdf` 单独路径时 MUST 拒绝继续（参见 §7.5.1）。
- 对 `did_recovery` envelope，展示当前 envelope 的 `recovery_policy_ref.policy_id` / `policy_version` 与当前 accepted recovery policy 的一致性；其它 envelope 携带 `recovery_policy_ref` 时也 MUST 展示并验证。不一致时 MUST `recovery_policy_mismatch`，并指向"更新 recovery policy"流程而不是默默继续。
- 不得从本地缓存读取用户先前确认的 fingerprint / passphrase / OOB token 跳过当次显式确认。本地缓存 MAY 用于自动补全，但用户 MUST 显式提交本次输入。
- 在 §7.4 列出的禁用证明类型（历史明文、邮箱验证码、撤销设备等）被用户尝试时 MUST 给出可读的拒绝原因。
- **无恢复路径（SPOF）账号的 fresh-device 登录警示**：当新设备登录的目标 principal 的 `active_policy=null`（无 accepted recovery policy）时，fresh-device DID recovery 与 `did_recovery` backup unlock MUST fail closed（§8）。此时 UI MUST 在进入任何恢复尝试之前明示"该账号没有已配置的恢复路径，唯一的换机方式是在一台已授权的旧设备上确认"，并把入口优先导向同 principal 旧设备确认流程（[`../crypto-media/device-lifecycle.md` §10](../crypto-media/device-lifecycle.md)）；不得让用户在无恢复材料的前提下反复尝试 recovery proof。

### 7.7.1 Backup Unlock Proof 与 Plaintext Keybag（normative）

每次读取并尝试解密 key backup 都 MUST 产出一条 unlock proof，明文 keybag 也 MUST 有固定 schema，避免“能下载密文”被误当作“有权使用解密结果”：

- backup decrypt proof payload MUST validate as `ak.schema.key_backup_unlock_proof.v1`，并绑定 `recovery_session_id`、`principal_id`、`requesting_device_id`、`backup_id`、`backup_kind`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest` 与 `issued_at`。`proof_digest` 是已接受 recovery proof transcript 的 digest；receiver MUST 用当前 session state 重建 transcript 后比对，不得采信客户端自报的 policy/session metadata。
- 取回完整 ciphertext 的协议操作是 `ak.self.keys.backups.command.unlock`（`POST /_arkret/self/keys/backups/{backup_id}/unlock`）：unlock proof MUST 作为 request body 的 `proof` 字段提交（`keys-operations.schema.json#/$defs/keys_backups_unlock_request_body`），path `backup_id` 与 `proof.backup_id` MUST 一致；实现 MUST NOT 用 header、query string 或私有载体承载该 proof。服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed（`recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `invalid_signature`）。
- AEAD/HPKE open 后得到的明文 MUST validate as `ak.schema.key_backup_plaintext.v1`，且其中 `backup_id`、`backup_kind`、`series_id`、`series_seq` MUST byte-for-byte 等于外层 envelope。`items[].secret_id` / `item_kind` 是 keybag 内部路由字段，不得替代外层 envelope 的授权判断。
- 实现 MUST 把 plaintext keybag 限定为本地瞬时处理材料；除非它被重新加密进本地 secret storage，否则不得持久化明文。日志、crash dump、telemetry MUST NOT 记录 `secret_b64u`。

### 7.8 Server-Side Hardening for Backup Access

加密备份的密文虽然不暴露明文，但下载即"投喂 KDF 爆破弹药"。Device / Key Server MUST 对 `ak.keys.backups.*` 接口实施：

- **每 principal 每 24h 下载上限**：默认 `daily_principal_download_limit = 64`（覆盖单一 series 下大量历史 epoch 备份的合理使用，又能拦截批量 dump）。`ak.profile.key_backup.memory_hard.v1` 实现 MUST 公布所采用的实际上限，并接受 deployment 配置在 `[16, 256]` 范围内调整。
- **每 IP / 每 session 限速**：默认 `per_ip_unlock_burst = 8`，`per_ip_unlock_sustained_per_minute = 4`；逾限响应 MUST 是 `429 Too Many Requests`，并 SHOULD 在 `Retry-After` 中给出建议。
- **认证降级阻断**：`POST /_arkret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof（与 §7.4 fresh challenge 相同绑定：challenge / audience / service_id / principal_id / key_id / nonce / 过期时间）。bearer token 单独到达 MUST 被拒绝。
- **审计记录**：超出阈值或在异常时间窗内的下载 MUST 写入 `ak.audit.accessed`，`access_kind="key_backup_read"`，并按 `ak.profile.attested_audit.e2ee.v1`（若声明）配对 audit pair。
- **跨 actor 拒绝**：服务端 MUST 在 envelope `actor_id` 与请求 caller 不一致时返回 `forbidden`，并不得通过 metadata 暴露 envelope 是否存在。§7.5.6 managed Agent PCR backup 的 envelope `actor_id` 是 controller，上传/列出/解锁 caller 也始终是该 controller；`contents[].managed_principal_binding.managed_principal_id` 不把 Agent 变成 backup owner，不构成跨 actor 例外。
- **删除验证**：active series 内的非尾部 envelope MUST NOT 被单独删除。`DELETE` 尾部 envelope MUST 携带 [`high-risk-authority-proof.schema.json`](../../artifacts/schemas/high-risk-authority-proof.schema.json) 的三分支之一（`principal_signing` / `device_quorum` / `trusted_recovery_service`），按 §7.8.1 绑定服务端签发的单次 challenge 并签署 canonical delete-intent transcript，然后写入 `access_kind="key_backup_delete"` 审计。普通 current device proof **不是**该 family 的第四分支：仅持普通 device proof 的 caller 只能删除 `expired_at < now` 且不属于 active series 的旧 envelope，或对已被 active-series record 移出 primary source 的旧 series 发起整组 erasure/retention 删除。设备revoke轮换的整组删除必须使用[`security-transactions.md` §3](./security-transactions.md)登记的transaction-bound operation；普通DELETE outcome不得作为`erase_confirmation_digest`来源。

实现 MAY 在 deployment policy 中收紧上述阈值；MUST NOT 放宽超过本节默认。

#### 7.8.1 高风险删除的 challenge 与 canonical delete-intent transcript

freshness MUST 由服务端发放，不得接受 caller 自造 nonce：

1. **challenge 签发**。`ak.self.keys.backups.command.issue_delete_challenge`
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
     "context": "ak.keys.backup_delete.v1",
     "operation": "ak.self.keys.backups.resource.delete",
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
   `backup_id` / `reason` / `audience` / `nonce` 任一 transcript 字段后验签必然失败。

### 7.9 Algorithm Agility & Forward Compatibility

v1 的备份枚举数量有限，但 envelope 结构需要支持未来 PQ / hybrid 迁移：

- `recovery_policy.recovery_keys[].signature_algorithm` MUST 取自 active [`signature-alg-registry.json`](../../artifacts/registry/signature-alg-registry.json) row 的非空 `raw_signature_algorithm`；v1 机读集合为 `Ed25519`、`ML-DSA-65`。`Ed25519` 是默认 MUST，`ML-DSA-65` 仅在实现声明相应 PQ 签名能力时可签发。`ES256` 只有 JOSE mapping，没有 Arkret raw-signature mapping，因此不得出现在该字段。receiver 不支持 entry 声明的 active algorithm 时 MUST fail closed `unsupported_signature_alg`，不得回退为 Ed25519 或忽略该 recovery key。

- Receiver MUST 对未知 `encryption.kdf.name`、`encryption.aead.name`、`encryption.aead.aead_profile`、`encryption.recipient_method` fail closed（不得回退到默认）。
- PQ / hybrid KEM agility MUST 通过 `encryption.hpke_suite` 选择子 + [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 声明，不得塞进 AEAD profile。PQ hybrid（X25519+ML-KEM-768）已在该 registry 预留 `ak.hpke_xwing_aead_chacha20poly1305.v1`（status=reserved，profile `ak.profile.kem.hybrid_xwing.v1`），与 `ak.aead.hybrid_kem.*` 预留 namespace 对齐；只有该 registry row 的 activation requirements 全部满足并翻为 active 后才可出现在 wire 上。`ak.aead.*` 只描述 AEAD 算法、nonce/tag/key 长度和 AAD 构造；receiver 收到把 KEM 语义编码进 `encryption.aead.aead_profile` 的 envelope MUST fail closed。
- 当 `frontier_ref` 携带 `seal_ref` 时，client 可以用 Seal inclusion proof 来证明 envelope 创建时刻不晚于 Seal commit；receiver MAY 在 sovereign / high_security_organization profile 中要求该证明。
- 实现 MUST 在 envelope metadata 中保留 `additionalProperties` 与 `x_*` 前缀作为 forward-compat 扩展槽；MUST NOT 在 wire 上接受未知顶层字段（已由 schema `additionalProperties: false` 强制）。

### 7.10 自动持续备份

§5.0.1 recovery-material gate 完成后，客户端 SHOULD 自动、持续地维护密钥备份，而不是把备份当作一次性手动动作：

- account secret（`self_signing_key` / `user_signing_key`、`account_data_namespace_key` 等 `secret_storage` 域材料）、历史密钥材料（MLS group state / epoch key material 等 `mls_history` 域材料）与 encrypted private account data cache 发生新增或轮换时，客户端 SHOULD 自动上传对应 `ak.schema.key_backup.v1` envelope，遵守 §7.6 series 链规则。recovery secret、identity root seed、HKDF PRK 与任何完整派生 private key 始终受 §7.1 禁止项约束，不得上传或自动备份。
- controller 创建 Agent PCR、Agent PCR accepted Seal/frontier 或 MLS epoch 前进（包括 pairing 接受新的 key-authorization Event）、controller recovery policy 轮换、Agent deactivation 或 delegation 变更时，客户端 MUST 立即重算 §7.5.6 managed binding 与 controller `mls_history` active series；在新尾部 envelope accepted 前，对应 Agent `pcr_recovery` MUST 为 `pending` / `stale`，不得完成下一次 runtime pairing。
- 自动备份 SHOULD NOT 要求用户手动触发或重复输入凭证；envelope 加密给 recovery public key（§7.5.2）只使用公钥，不需要用户在场。客户端 MAY 额外提供手动"立即备份"入口。
- 自动备份失败（网络、§7.8 限速、series 冲突）时，客户端 SHOULD 退避重试，并在持续失败超过实现定义的窗口时向用户显式提示备份落后；SHOULD NOT 静默丢弃待备份材料。
- 本节不放宽 §7.1 的禁止项：device private key、session key、已发布的 KeyPackage private key 等仍 MUST NOT 进入自动备份。
- **A 模型首份 `secret_storage` 备份**：SSK/USK 在 `ak.cross_signing.publish` 后产生；客户端 SHOULD 立即发布其 `recipient_method="recovery_public_key"` envelope 并纳入 onboarding 完成判据。B 模型没有 SSK/USK，不得伪造这类备份。

### 7.11 加密 Realm 创建 / 加入前的 Recovery 前置门（normative）

E2EE Realm（effective `content_encryption_floor` 或 `metadata_encryption_floor` 为 `e2ee_required`，含 PCR 与任何加密协作 Realm）的创建或加入会产生该用户独有的 MLS group secret；若此时账号尚无可用恢复路径，丢失唯一设备即永久丢失这些内容。因此：

- 客户端在 `recovery_state` 未配置（`active_policy=null` 且无 §5.0.1 offline-sealed receipt）时，发起任何 post-bootstrap E2EE Realm 创建/加入前 MUST 完成 recovery-material gate；PCR bootstrap 是唯一豁免。
- `ak.profile.personal_node.v1` MAY 允许用户在明确告知"丢失本设备将永久丢失该 Realm 内容"后**显式跳过**，并维持 / 标记 `single_point_of_failure=true`、持续提醒；`small_team` 及以上 deployment profile SHOULD 阻断创建 / 加入，直至 recovery policy 配置完成。
- `ak.profile.personal_agent_provisioning.v1` 对 Native Personal Agent 收紧上一条例外：即使部署同时声明 `ak.profile.personal_node.v1`，controller 没有 accepted recovery policy 时 `ak.self.agent.command.provision` MUST 在产生 Agent DID / PCR / grant 副作用前 fail closed；Agent PCR bootstrap 后、§7.5.6 首份 controller-owned recovery envelope accepted 前，Agent 只能保持 `pending_runtime_key` 且 pairing commit MUST `agent_pcr_recovery_not_ready`。不得以 `single_point_of_failure=true`、服务端托管 MLS secret 或为 Agent 生成另一套助记词绕过。
- 该前置门是客户端编排义务，不替代服务端的 floor ratchet 与 PCR 校验；它针对的是"加密材料先于恢复路径产生"的时间窗，而非加密本身是否启用。

## 8. Recovery Policy

高价值账号 SHOULD 支持门限恢复。Recovery policy 的规范形态由 `ak.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）固定；本节内联 JSON 仅作示意，wire 实现 MUST 以 schema 为准。

Recovery policy 的标准发布面是 `POST /_arkret/root/identity/recovery-policy`（operation `ak.root.identity.recovery_policy.command.publish`，请求体为 `recovery-policy.schema.json#/$defs/recovery_policy_publish_request`，即携带 `ak.policy.set` Event 的完整 `EventInitialSubmission`，响应 `recovery-policy.schema.json#/$defs/recovery_policy_publish_outcome`）；Event payload 固定为 `{policy_id, value}`，`value` 才是本节定义的完整 `ak.schema.recovery_policy.v1`，两处 policy id 必须一致且不得携带 `state` / `reason`。标准读取面是 `GET /_arkret/root/identity/recovery-policy`（operation `ak.root.identity.recovery_policy.resource.get`，响应 `recovery-policy.schema.json#/$defs/recovery_policy_active_outcome`）。服务端在 Event 首次接受前 MUST 校验 `auth_data.signed_fields`、签名权限、`version` 单调递增和 `supersedes` 链接；只有覆盖该 Event digest 的 control Seal/SealBasis materialize后才能推进 active policy并返回 immutable `acceptance_basis`，此前同 Event 重试返回 `frontier_unavailable`。客户端在校验 `recovery_policy_ref`、创建 `ak.schema.recovery_session.v1`、或向用户展示恢复策略之前，MUST 通过 GET 端点读取当前服务观察到的 active policy，或从本地已验证的 principal control stream 重放到同一 frontier 得到等价结果。新设备尚未持有 control stream 时 MUST 使用该端点；`active_policy=null` 表示当前没有 accepted recovery policy，fresh-device DID recovery 与 `did_recovery` backup unlock MUST fail closed。客户端向 `recovery_session.create` 发送 `expected_recovery_policy_ref` 时 SHOULD 使用该读取结果中的 `active_policy.policy_id` 与 `active_policy.version`，服务端发现不同步 MUST 返回 `recovery_policy_mismatch`。

`ak.policy.set` 进入 Principal Control Realm 时只允许上述 recovery-policy publish 形态成为恢复 authority：payload 必须逐字只含 `{policy_id,value}`，且 `value.schema="ak.schema.recovery_policy.v1"`。普通 Realm 中其它 policy family 的 `ak.policy.set` 合同不会因此获得 PCR 写入权；recovery endpoint 也不得绕过 `ak.profile.principal_control_realm.v1` 的 event-kind allowlist、普通 Event proof/lease admission、reducer 或 Seal 流程。

```json
{
  "schema": "ak.schema.recovery_policy.v1",
  "policy_id": "ak:policy:01964140-0000-7000-8000-000000000000",
  "principal_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "version": 1,
  "supersedes": null,
  "trust_domain": "ak:trust_domain:did.webvh.example",
  "allowed_proof_kinds": [
    "threshold_recovery"
  ],
  "publication_authorization_rules": [
    {
      "rule_id": "threshold_recovery",
      "proof_kind": "threshold_recovery",
      "issuer_role": "identity_recovery",
      "allowed_actions": [
        "ak.device.reanchor"
      ],
      "issuers": [
        {
          "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#recovery-proof-1"
        }
      ],
      "threshold": 1
    }
  ],
  "threshold": {
    "k": 2,
    "n": 2,
    "shares": [
      {
        "share_id": "s1",
        "holder": "did:webvh:zFUHaR4UpA8gSoyk7J4AgYBHa:alice-friend.example",
        "transport": "hpke_x25519",
        "share_commitment": {
          "algorithm": "feldman_vss_sha256",
          "commitment_b64u": "Y29tbWl0bWVudDE"
        },
        "not_before": "2026-04-26T00:00:00.000Z",
        "expires_at": null,
        "revoked_at": null
      },
      {
        "share_id": "s2",
        "holder": "did:webvh:z6mkfixture:bob.example",
        "transport": "hpke_x25519",
        "share_commitment": {
          "algorithm": "feldman_vss_sha256",
          "commitment_b64u": "Y29tbWl0bWVudDI"
        },
        "not_before": "2026-04-26T00:00:00.000Z",
        "expires_at": null,
        "revoked_at": null
      }
    ],
    "reshare_policy": {
      "max_share_age_seconds": 7776000,
      "scheme": "proactive_vss"
    }
  },
  "recovery_keys": [
    {
      "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#recovery-proof-1",
      "public_key_multibase": "z6MkogKw38hXxUkpMWitoBubBGHZzeGrQJ4oHF36iegUbmpA",
      "key_agreement_ref": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#backup-hpke-1",
      "not_before": "2026-04-26T00:00:00.000Z",
      "expires_at": "2036-04-26T00:00:00.000Z",
      "revoked_at": null,
      "signature_algorithm": "Ed25519"
    }
  ],
  "recovery_key_agreements": [
    {
      "key_agreement_ref": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#backup-hpke-1",
      "key_agreement_algorithm": "X25519",
      "public_key_multibase": "z6LSriWhVBzW9Vz2PvqbieSz7Aa2hPLzTKJuDwXTMKFeomeW",
      "hpke_suites": [
        "ak.hpke_x25519_aead_chacha20poly1305.v1"
      ],
      "use": "backup_hpke",
      "not_before": "2026-04-26T00:00:00.000Z",
      "expires_at": "2036-04-26T00:00:00.000Z",
      "revoked_at": null
    }
  ],
  "approval_requirement": {
    "min_approvals": 1,
    "cooldown_seconds": 3600,
    "announcement_required": true
  },
  "issued_at": "2026-04-26T00:00:00.000Z",
  "not_before": "2026-04-26T00:00:00.000Z",
  "expires_at": null,
  "auth_data": {
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ak_principal_signing_v1",
    "signature": "c2lnbmF0dXJl",
    "signed_fields": [
      "schema",
      "policy_id",
      "principal_id",
      "version",
      "supersedes",
      "trust_domain",
      "allowed_proof_kinds",
      "publication_authorization_rules",
      "threshold",
      "recovery_keys",
      "recovery_key_agreements",
      "approval_requirement",
      "issued_at",
      "not_before",
      "expires_at"
    ],
    "signature_algorithm": "Ed25519"
  }
}
```

恢复 share holder 只能帮助恢复控制权，不自动获得读取内容或代表主体操作的 capability。Recovery policy MUST 为每个门限 share 记录 `share_commitment{algorithm, commitment_b64u}`（如 Feldman VSS commitment 或 share hash commitment）；恢复时客户端 / recovery coordinator MUST 校验提交的 share 与 commitment 一致，避免 holder 或中间服务替换 share 后仍通过 policy 语法检查。

### 8.1 Policy 生命周期

Recovery policy 是 principal control state；其签发权按模型封闭解析，不得仅凭任意 DID Document VM 接受：genesis policy 仅可由 §5.0.1 bootstrap 已接受的首设备 key 签发；后续 A 模型由当前 accepted SSK 或满足旧 policy 的 quorum 签发；后续 B 模型由当前 active device generation 中的 accepted device key 或满足旧 policy 的 quorum 签发。B 模型设备签名必须同时验证 `device_generation_status="active"`、`authorized_generation_ref == current_device_generation_ref` 与未撤销状态。所有发布、轮换、撤销均进入 principal control stream：

- **publish**：首次发布或后续无中断更新。新 envelope 的 `version` MUST 严格大于当前 accepted policy 的 `version`，`supersedes` MUST 引用前一份 `policy_id`（首版为 `null`）。
- **rotate**：用于 `reshare_policy` 触发的 proactive secret sharing 或更换 holder 集合；rotate envelope MUST 在 `signed_fields` 中覆盖 `threshold` 与 `device_quorum`，并 SHOULD 同时附带新 share commitment。轮换期内的 in-flight recovery session（参见 `crypto-media/device-lifecycle.md` §15）MUST 使用其 `issued_at` 时点的 policy；服务端 / coordinator MUST 拒绝跨 policy 版本拼接 share。
- **revoke share**：当某个 share holder 被怀疑泄露时，policy holder 可发布只更新 `threshold.shares[i].revoked_at` 与 `revocation_reason_code` 的 rotate envelope。recovery coordinator MUST 拒绝任何 `revoked_at != null` 的 share，即便 commitment 仍能通过。`reshare_policy.max_share_age_seconds` 到期后未 reshare 的 share 在 coordinator 侧 MUST 被视为 stale，UI MUST 提醒用户。
- **revoke policy**：用 `expires_at = now`、`allowed_proof_kinds = []`、或专门的 `policy_id` revoke 进入 principal control stream；revoke 之后只有写入新 policy 才能恢复账号——这是高代价动作，必须配 §7.7 UI 警告。

任何允许的恢复方式（principal_signing / device_quorum / trusted_recovery_service / threshold_recovery / recovery_unlock）的 proof transcript MUST 绑定 `(policy_id, version, recovery_session_id)`；不绑定的 proof MUST `recovery_evidence_unbound`。Device recovery 场景还 MUST 使用 `crypto-media/device-lifecycle.md` §15 定义的 canonical transcript，其字段集同时绑定 `principal_id`、`requesting_device_id`、`trust_domain`、`identity_model`、`model_generation_ref`、session `challenge`、session `created_at` 与 `expires_at`；A 的 generation ref 是 SSK generation，B 是 DID versionId。

### 8.2 Holder 取回与防滥用

share holder（无论是个人 DID、托管服务 DID，还是 hardware module）在向恢复请求方释放 share 时 MUST：

- 验证 `recovery_session_id` 来源——session id MUST 来自当前 accepted recovery policy 中的 announcement event 或 trusted_recovery_service 签发的 challenge；不得接受任何 client 直接构造的 session id。
- 在签发 share release 之前 MUST 验证 holder 自己未被 §8.1 revoke，且当前时间在该 share 的 `not_before` / `expires_at` 范围内。
- share release 的请求方绑定按 `proof_kind` 分流：
  - `device_quorum`：请求方设备的 device key MUST 已绑定到目标 principal control stream 中某个尚未 revoke 的 device record；不满足则拒绝 release。
  - `threshold_recovery` / `recovery_unlock`：请求方设备 MAY 是尚未授权的新设备。holder MUST 验证 `recovery_session_id`、当前 policy/version、identity model/model generation、requesting device key proof-of-possession、session challenge、`requesting_device_id` 与 share request transcript 一致，并按 policy 要求完成 holder 侧 OOB / announcement / approval 检查；MUST NOT 要求该新设备预先存在于 control stream。恢复完成出口必须按 `crypto-media/device-lifecycle.md` §15 分流：A 模型由恢复出的 SSK 签 authorize；B 模型提交 root-signed re-anchor + enrollment-authority-signed authorize 原子 unit。
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
3. **删除旧 series**：在新 series 确认可恢复**之后**，按 `crypto-media/device-lifecycle.md` §12.2 retention 流程删除旧 `series` 的服务端密文。删除 MUST 在确认新备份可用之后进行，且 MUST 整组迁移而非删除链中间节点。若触发源是设备revoke，`secret_storage`与`mls_history`必须由同一`SecurityRotationTransaction`预留并通过`ak.self.keys.backup_series.command.erase`返回逐series durable progress；只有complete typed confirmation的canonical digest可推进事务。

**不可挽回边界（MUST 在 UI 明示）**：上述流程只缩小**后续**暴露面；攻击者在泄露窗口内**已经下载**的旧密文用旧密钥永远可解，轮换/删除无法撤销。

**Active series 指针**：当一个 `(actor_id, backup_kind)` 存在多个 `series_id`（轮换后新旧并存的过渡期）时，恢复方 MUST 通过 §7.6 的 signed active-series record 确定当前 canonical series。`frontier_ref` 是 envelope / record 的 control-stream 锚，不是 series 选择器；服务端返回顺序、最大 `series_seq`、最新 `created_at` 或单个 envelope 的 `frontier_ref` 都不能单独决定 active series。旧 series 仅在 retention 删除前用于读取既有内容，MUST NOT 作为 primary recovery source。

## 10. 实现要求

实现 MUST：

- 使用系统安全存储保存私钥
- 对可导出密钥做用户确认
- 对恢复操作做高风险 UI，且 §7.7 的 UI 字段展示要求 MUST 被遵守
- 对设备列表显示最近活动和授权来源
- 对吊销操作做不可抵赖记录
- 在发布 entry 0 前执行 custody-confirmation gate，并在 PCR bootstrap 后阻塞所有 post-bootstrap 持久写入直至 recovery-material gate 完成

实现 SHOULD：

- 支持硬件安全模块或平台 keystore
- 支持 biometric unlock 但不把 biometric 当作 cryptographic secret
- 支持 passkey / WebAuthn 作为本地解锁与网关认证材料
- 支持企业设备管理和远程吊销

## 11. 一致性要求

Arkret v1 对设备、会话和恢复要求如下：

- Device record JSON Schema 由 `../models/common-fields.md`（`id:device` 类型与 typed-id 规则）与 `../crypto-media/device-lifecycle.md` 共同固定。设备记录 MUST 绑定 principal DID、device id、verification method、算法、创建时间、撤销状态和签名链。
- `ak.device.authorize` 与 `ak.device.revoke` MUST 进入 schema registry，并按 event auth 规则验证。`ak.device.revoke` 的控制面位置由其 Control Move 信封 `seal_basis`（授权基准，签名覆盖）与覆盖它的 accepted Seal（生效切点）表达，payload 不携带 frontier 字段；撤销后设备不得产生新的有效 session grant、KeyPackage 或 to-device write。
- Session grant MUST 绑定 principal DID、device id、service DID / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖：加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定、服务端不可解密要求、`series_seq` 严格单调、`supersedes` / `supersedes_digest` 链完整、`mixed_secret_storage=true` 在 non-personal_node profile 下被拒绝、`did_recovery` 域使用 `passphrase_kdf` 的 envelope 被拒绝(该域只允许 `recovery_public_key`)、§7.8 服务端限速与跨 actor 拒绝。
- MLS KeyPackage binding MUST 覆盖 principal DID、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝未绑定 DID / device trust chain 的 KeyPackage。
- Recovery policy grammar 由 `ak.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）规范化；publish / rotate / share-revoke 的 wire 形态由 §8.1 描述。grammar MUST 表达 threshold、share holder、not_before、expires_at、allowed_proof_kinds、approval requirement 与 audit event；恢复只改变控制链，不自动授予内容读取或业务 capability。
- Recovery policy publication 的 `ak.vector.identity.recovery_policy_publication.v1` MUST 由至少两个独立 runner 覆盖 canonical `EventInitialSubmission`、PCR allowlist/reducer/Seal admission、threshold recovery signing/HPKE key 闭包、issuer projection、跨字段不一致、未 Seal retry 与特殊写路径绕过拒绝。
- Recovery receipt 由 `ak.schema.recovery_receipt.v1`（`artifacts/schemas/recovery-receipt.schema.json`）规范化；`crypto-media/device-lifecycle.md` §15 finalize 写入的 receipt MUST 通过该 schema 校验，并绑定 `recovery_session_id` / `policy_id` / `policy_version` / `new_device_id` / `identity_model` / `previous_model_generation_ref` / `result_model_generation_ref` / authorization path refs / `proof_summary` / `backup_classes_unlocked` / `welcome_count` / `outcome`。
- Backup series MUST 满足 §7.6：客户端 `LIST` 后重建链 → 验证 `supersedes_digest` → 用尾部 envelope 解密；当 `frontier_ref` 存在时 MUST 用 control stream snapshot 验证 `frontier_digest` 以及 A 模型 `ssk_generation` 或 B 模型 `device_generation_ref`。
