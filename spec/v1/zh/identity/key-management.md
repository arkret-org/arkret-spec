---
title: Key Management
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

身份层定义“谁是主体”，加密层定义“如何保护内容”，但真正能让系统安全运行的是密钥管理。

本文定义 Cokret 的密钥生命周期：

- inception key
- principal signing key
- recovery key
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

长期身份锚点密钥 SHOULD NOT 用于日常签名；除 key rotation、recovery、device authorization 等明确生命周期事件外，MUST 由设备密钥或短期 session key 代替执行签名。

### 2.3 所有授权都必须可撤销

设备、agent、session 和企业网关颁发的权限 MUST 有明确失效条件：

- `expires_at`
- revoke event、status event 或 profile 注册的 credential status mechanism
- `agent_key_scope`
- `audience`
- `not_before`

无限期、无 scope 的委托只允许用于极少数离线恢复场景，并且 SHOULD 有多签或门限保护。

## 3. 密钥类型

### 3.1 Inception Key

`inception_key` 表示 DID method 的初始控制材料或等价 genesis authority。不同 DID method 可能使用不同名称，例如 `did:plc` genesis operation / rotation keys、`did:webvh` SCID 与首个 DID log entry、KERI inception event，或其他 method-specific root。

要求：

- 初始控制材料或其 method-specific 证明 MUST 可验证
- 若 method 支持离线 genesis / recovery material，私钥 SHOULD 在 DID 创建后离线保存或销毁
- 普通操作 MUST NOT 依赖高权限 inception / recovery private key 在线存在

### 3.2 Principal Signing Key

principal signing key 用于：

- DID 文档更新
- 高权限 capability 签发
- device authorization
- recovery policy 更新

它 MAY 轮换。轮换 MUST 进入 DID method history、key log 或等价 signed event。

### 3.3 Recovery Key

recovery key 用于当前控制密钥丢失或泄露后的恢复。

recovery key 同时是**内容恢复**（解密 `secret_storage` / `mls_history` 备份）的标准面向用户凭证：备份接收密钥即恢复密钥（§7.5.2），客户端恢复 UI 的密钥备份解密凭证 MUST 是 Recovery Key（§7.7）。实现 SHOULD NOT 在 recovery key 之外引入独立的 "vault passphrase" 用户凭证层（§7.5.1）。

要求：

- SHOULD 与日常设备隔离
- SHOULD 支持多份或门限方案
- MUST 只能执行 recovery policy 允许的操作
- recovery event MUST 写入 DID method history、key log 或等价 signed event
- 面向最终用户的呈现 SHOULD 是 24 词 BIP-39 助记词（编码 recovery private key 的种子）；客户端 MUST NOT 把助记词明文或由其派生的 recovery private key 上传服务端，本地 MAY 仅保存指纹用于输入校验

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
| `ck.agent.key.authorize` | Payload MUST validate as `event-payload.schema.json#/$defs/agent_key_authorize_payload`，绑定 `agent_principal_id` / `key_id` / `verification_method` / `accountable_principal_id` / `agent_key_scope` / `audience` / `issued_at` / `expires_at` / `approval_evidence`。 | `ck.agent.key.authorize` |
| `ck.agent.key.rotate` | Payload MUST validate as `agent_key_rotate_payload`；`key_id` 是被替换 key，`replacement_key_id` 是新 key，二者必须在同一 accountable actor 下，agent_key_scope 不得扩大，TTL 不得长于被替换 key。被替换 `key_id` 已签发的 active agent session MUST 在 ≤ 该部署 agent session 最大 TTL 的 revocation freshness window 内失效（等同 §3.6.1 pause 的 fail-closed 处置）：rotate 只把日常签名权转移到 `replacement_key_id`，MUST NOT 让旧 key 的既有 session 自然存活到原过期窗口。 | `ck.agent.key.rotate` |
| `ck.agent.key.revoke` | Payload MUST validate as `agent_key_revoke_payload`，绑定 `agent_principal_id` / `key_id` / `revoked_at` / `revoked_by`；撤销的控制面基准由 Control Move 信封 `seal_basis` 表达，自被 accepted Seal 覆盖起使后续 session / protocol action proof fail closed。 | `ck.agent.key.revoke` |

高风险 agent key（能写入、调用外部工具、管理 capability、读取审计材料或代表用户发起 service-call）的 grant MUST 同时有 `expires_at`、resource selector、accountable actor、approval/proposal evidence 和 revocation freshness check。只声明 API token 或本地环境变量而没有上述事件链的 agent key 不得用于 v1 standard operation。

#### 3.6.1 Personal agent runtime pairing 与 session(normative)

`ck.profile.personal_agent_provisioning.v1` 定义了一条面向普通用户的 personal native agent 流程，以现有 agent key 原语为基础:

- **Provisioning** (`POST /_cokret/self/agents`, operation `ck.self.agent.command.provision`):service operation 编排 Actor Profile 创建、`ck.identity.accountability_grant`、初始 `ck.capability.grant`(标 `effective_after_first_authorized_key=true`),并返回一次性 `pairing_request_id` + `pairing_code`。不写入独立 `ck.self.agent.command.provision` event。
- **Runtime key pairing** (`POST /_cokret/gate/account/agent-key-pair`, operation `ck.gate.account.command.pair_agent_key`):agent runtime 本地生成 key pair、提交 public key + proof-of-possession + 可选 `runtime_attestation`(v1 baseline `kind="self_asserted"`)。Pairing endpoint MUST 校验 `verification_method` 的 DID 部分(strip fragment/query 后)与请求体中 `agent_principal_id` bit-identical;不匹配 fail closed(`reason="verification_method_principal_mismatch"`)。批准后写入 `ck.agent.key.authorize`,reducer 清除该 agent principal 名下所有 `effective_after_first_authorized_key=true` flag。
- **Pairing 失败清理**:`pairing.expires_at` 到达且未完成 pairing 时，服务 MUST 自动 `ck.capability.revoke` 撤销 pending grant,agent status → `pairing_expired`。
- **Agent runtime authentication**:复用 `POST /_cokret/gate/account/session-grants`(operation `ck.gate.account.command.issue_session_grant`),通过 `proof.proof_kind="agent_key_proof"` 分支区分。Auth Server MUST 维护独立 schema branch、独立 proof validator;不得让 `agent_key_proof` 走 password / OIDC / passkey 的 validator fallback。请求侧 `agent_scope_request` 是 `ck.profile.agent_auth.v1` overlay,签发后的 scope MUST 物化为 capabilities.md 已注册的 `allowed_tracks` / `allowed_strand_ids` / `allowed_data_classes` / `allowed_endpoints` 等 typed constraints。
- **Session TTL**:Agent session grant 默认最大 TTL SHOULD 为 15 分钟；若 deployment profile 显式声明更长，不应超过 60 分钟。Controller 进入 `deactivated` / `suspended` 后，其 accountable agent 的 active sessions MUST 通过 account lifecycle / revocation 链失效。
- **High-risk approval**:Auth Server MUST NOT 给 agent runtime 展示 CAPTCHA / OTP 页面；需要人类批准时返回 structured error `code=claim_required`、`reason_code=human_approval_required`、`approval_request_id=<opaque>`。Controller 在带外 UI 完成批准，产生 capability / delegation / approval event,agent retry 时引用该 event。
- **E2EE access**:Agent MUST 作为独立 MLS member 参与，不得伪装成 controller 的 delegated device;agent MLS KeyPackage SHOULD 由 active `ck.agent.key.authorize.verification_method` 签发或绑定，使 key authorization、session proof 与 MLS membership 落在同一审计链。
- **Sidecar exposure 披露**:pairing approval UI 上，若该 controller 在新 agent 将要 active 的任一 Realm 中已存在 `ck.profile.agent_sidecar_thread.v1` sidecar Circle,实现 MUST 显式披露 "该 agent 激活后将自动获得这些 Realm 中现有 AI sidecar 私聊的访问权"(见 [`../models/circle.md` §11.1](../models/circle.md))。
- **Lifecycle**:`ck.self.agent.command.pause` / `ck.self.agent.command.resume` / `ck.self.agent.command.deactivate` 是 agent lifecycle 写入。Pause 保留 durable state 但拒绝新 session;Auth Server MUST 在 revocation freshness window(≤ session 最大 TTL)内对已签发 session token fail closed。实现 MAY 通过同步 token revocation、introspection fail-closed、资源访问时强制 agent status freshness check 或等价机制达成，但 MUST NOT 仅等待 token 自然过期。Revoke 是 terminal,fan-out `ck.agent.key.revoke` / `ck.capability.revoke` / runtime endpoint revocation。
- **Resume 时 sidecar exposure 重新披露(normative)**:`ck.self.agent.command.resume` 提交前，实现 MUST 重新执行上一条 "Sidecar exposure 披露" 流程，把 agent 在 pause 期间 controller 在 eligible Realm 中**新建或新加入**的 `ck.profile.agent_sidecar_thread.v1` sidecar Circle 列出；若该集合非空,resume MUST 在 controller 显式再次同意之前拒绝执行(不得 silent resume),并把该确认作为 audit 事件留底。仅当 pause 期间无新 sidecar 进入 agent 的 eligibility 集合时,resume 可不重复披露。该规则关闭"pairing 期完成一次披露后,pause 期新建 sidecar 在 resume 时被 agent 静默继承访问权"的暴露面。

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
  "id": "ck:device:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "display_name": "Alice MacBook Pro",
  "device_public_key": "z6Mks...",
  "device_key_type": "Multikey",
  "created_at": "2026-04-26T00:00:00Z",
  "authorized_by": "ck:device:01964136-8000-7000-8000-000000000000",
  "authorization_ref": "ck:event:01964137-8000-7000-8000-000000000000",
  "status": "active",
  "last_seen_at": "2026-04-26T08:00:00Z",
  "revocation_ref": null
}
```

### 4.1 Principal Control Event Stream

设备、session、recovery 和 KeyPackage 有效性属于 principal 级状态，不属于任意 Collaboration Realm。Cokret v1 使用 **Principal Control Event Stream** 承载这些 durable identity state（其归属的 Realm 即 [Principal Control Realm](../models/realm-and-space.md#28-realm-角色分类normative)，与 Collaboration Realm 在 `models/realm-and-space.md` §2.8 中正式分类）。

当 `ck.device.authorize`、`ck.device.revoke`、`ck.device.list_update` 或 `ck.session.grant` 以 `ck.schema.event.v1` Event Envelope 传播时：

- `realm_id` MUST 是该 principal 的专用 `principal_control_realm_id`，不得使用任意 Collaboration Realm 的 `realm_id`。
- `actor_id` MUST 是签发该控制事件的 principal、已授权 device、受信 recovery service 或组织声明的 session issuer。
- `payload.principal_id` / `payload.subject` MUST 与该 control Realm 绑定的 principal DID 一致；不一致时 MUST reject。
- control Realm 的 `ck.realm.create` 或等价 genesis record MUST 绑定 principal DID、DID method / key-log history、control stream policy 和可发现的 service endpoint。该 Realm 使用标准 `ck.schema.realm.v1`；通过 `fields.purpose="principal_control"` + `schema_refs` 包含 `ck.profile.principal_control_realm.v1` 标记其 control stream 角色（详见 §5.0.1 步骤 3）。control realm **不**使用单独的 Realm kind——所有 Realm-level 验证（schema、boundary、E2EE、federation）走标准 Realm 路径。
- 普通 Collaboration Realm 的业务事件 MAY 通过 `refs[role=authorized_by]`（或 role=`did_inception` 等专门 role）、verified snapshot reference、Policy Server proof 或 device-state seal 引用 principal control state；不得把另一个 principal 的 device/session 事件直接写入该 Collaboration Realm history 来改变身份状态。

`principal_control_realm_id` MUST 可通过 DID Document service、normalized principal view、device/key server describe endpoint 或本地 account binding 验证。客户端无法验证 control Realm 与 principal DID 的绑定时，MUST fail closed：不得接受该 principal 的新 device grant、session grant、KeyPackage 或 device revocation 状态。

Organization principal 的 control stream 遵守同一 PCR 规则，但它没有共享 human password account。组织 PCR 的 genesis / recovery / delegated write MUST 由组织 DID inception/controller proof、满足组织 governance threshold 的 proof、或组织 DID Document / governance profile 明确委派的 Account Authority / `CokretGovernanceService` 授权。委派路径的 purpose MUST 覆盖对应动作（例如 `principal_control_realm_bootstrap`、`device_enrollment`、`session_issuer` 或 `ck.realm.organization`），且事件必须保留实际执行主体（`executed_by`、governance decision id 或等价审计 ref）。普通企业 SSO/OIDC/passkey 登录只认证某个管理员 principal；它不能单独创建、登录或控制组织 PCR，除非该 Account Authority 同时出示上述组织侧 delegation / governance proof。

实现 MAY 用 identity sidecar、device registry 或 DID/key-log operation 存储同一状态，但它们必须提供等价的签名、digest、auth dependency 和撤销语义；桥接到 Event Envelope 时仍必须遵守上述 `realm_id` 规则。

## 5. 设备授权流程

### 5.0 First-Device Inception Bootstrap

§5.1 假设新设备由"已授权设备"签发 `ck.device.authorize` 才能加入。但 principal 第一次激活时只有一台设备，没有任何已授权 peer 可以扮演这个角色。如果不为这种"无 peer 设备"的初始情形定义协议路径，§5.1 的链条永远无法启动，§4.1 的 control stream 也无法获得 genesis record。

Inception bootstrap MUST 使用 DID method 自身的初始控制密钥作为信任根，把"第一台设备的 device key"和"DID 的 inception controller key"建立可验证绑定。Cokret 不发明新的 DID inception 操作；它把已有 DID method 的 inception 证据**重用**为 principal control stream 的 genesis record 授权依据。

#### 5.0.1 标准 Inception 路径（v1 core 默认 `did:webvh` principal）

1. **Inception key 生成**：客户端在用户首次注册或自主权恢复时本地生成一个 `inception_keypair`（Ed25519 / ECDSA-P256）。该密钥既是 `did:webvh` 第 0 条 `did.jsonl` entry 的 `updateKeys[0]` / `nextKeyHashes[0]`，也是首台设备的 device key 之一。
2. **`did:webvh` genesis 写入**：客户端按 `did:webvh` specification 计算 SCID，将 `did.jsonl` entry 0 写入 hosting domain（自有 / Auth Server 托管子域）。Entry 0 的 `versionId`、SCID、controller proof MUST 由 inception key 签发。可选 witness MAY 在 entry 0 之后补签，不阻塞 bootstrap。
3. **Principal control realm genesis**：客户端构造 `ck.realm.create` Event 创建 principal control realm（`realm_id` 即 `principal_control_realm_id`，绑定到 principal DID）。该对象是标准 `ck.schema.realm.v1` Realm（不引入新的 Realm kind），并通过以下 Realm 字段把它标记为 control stream：
   - `fields.purpose = "principal_control"`（产品语义；reducer/authz 通过此字段识别 control stream）。
   - `schema_refs` 包含 `ck.profile.principal_control_realm.v1`（profile id；该 profile 收紧 control realm 的允许 event kinds、capability action、E2EE/federation 默认值）。
   - `ck.profile.principal_control_realm.v1` 的机器化要求见 `artifacts/profiles/conformance-profiles.json#profile_requirements`：control Realm MUST 使用 allowlist-only event kind policy；普通 Strand / Message / Space / Relation / View / Morph / Call 协作事件在该 Realm 内 MUST `principal_control_event_kind_forbidden`。
   - `encryption_profile = "mls_rfc9420"`，`content_encryption_floor = "e2ee_required"`，`metadata_encryption_floor = "e2ee_required"`，`history_visibility = "restricted"`，`notary_profile = "single_did"`，`notary = <principal DID>`。Principal Control Realm 的 `encryption_profile` 在 v1 中被 `ck.profile.principal_control_realm.v1` 固定为 `mls_rfc9420`，两条加密 floor 被固定为 `e2ee_required`（v1 不存在明文地板的 PCR）；producer MUST NOT 使用 `none` 或 `external`，也 MUST NOT 把任一 floor 声明为低于 `e2ee_required`。`history_visibility = "restricted"`：新授权的同 principal 设备读取 join 前控制历史走 durable device-list / normalized principal view baseline 与 policy 受控的 MLS history key share，PCR MUST NOT 使用 `joined`。

   **PCR history key share 释放授权（normative）**：PCR 的 MLS history key share 释放判定 MUST NOT 退化为"只要 device 在 device-list 即给全部历史 epoch key"。释放方 MUST：(a) 校验接收设备持有一条 accepted、链接到当前 published 交叉签名代际的 `ck.device.authorize`（`generation` 定义见 [`../crypto-media/device-lifecycle.md` §5](../crypto-media/device-lifecycle.md)）；代际早于当前 accepted generation 的设备 MUST NOT 释放历史 key share；(b) 以该设备权威 `ck.device.authorize` 在 control stream 中的因果位置（其 accepted frontier）为 baseline 判定可释放的 epoch 区间，绝不释放该 baseline 之外、与该设备无关的更早或并发分支 epoch key。此外，对承载历史 recovery secret 副本的最敏感 epoch 区间，释放方 SHOULD 额外要求该设备已完成 SAS/QR 设备密钥验证或由入册权威（§5.4）背书后才释放；未满足时 MUST fail closed（不释放该敏感区间的 history key share），与 [`../crypto-media/encryption-and-audit.md`](../crypto-media/encryption-and-audit.md) 对协作 Realm 成员 key share 校验的 fail-closed 纪律对齐。该约束是 PCR 单成员语境下对 history key share 的专用 restricted 规则，独立于协作 Realm 的 membership 校验路径。
   - `created_by = <principal DID>`，`security_class = "high_assurance"`（强制 federation_policy ∈ {closed, restricted, quarantine}）。

   Event 的 `actor_id` 是 principal DID，`proofs[]` 由 inception key 签发，`refs[]` 引用 `did:webvh` entry 0 的 `versionId` 和 SCID 作为身份证据 ref（`role="did_inception"`，`critical=true`）。Receiver 验证 control realm genesis 时 MUST 同时校验 `fields.purpose=principal_control`、`schema_refs` 包含 `ck.profile.principal_control_realm.v1`、`encryption_profile="mls_rfc9420"` 与 `content_encryption_floor=metadata_encryption_floor="e2ee_required"`；前三项缺一即按普通非 PCR Realm 处理（不再具备 control stream 的特殊语义），若已声明 PCR profile 但 `encryption_profile` 或任一加密 floor 不匹配则 MUST reject。
4. **首台设备自授权**：客户端构造 `ck.device.authorize` Event，`device_id` 是新生成的 device public key 派生的 `ck:device:<uuid>` typed ID（非 DID——设备不是独立主体；inception key 属于 principal，恰好复用为首台设备 key，该 device key 作为 principal DID 的 verification method 由本 Event 登记），`authorized_by` 直接引用 inception key 的 `verification_method`（即 entry 0 的 controller key）。该 Event 的 `proofs[]` 由 inception key 签发；`refs[]` 引用 control realm 的 genesis Event（`role="authorized_by"`）与 `did:webvh` entry 0 的 `versionId`（`role="did_inception"`，`critical=true`）。
5. **Inception key 的归宿**：完成步骤 4 后，inception key 的在线签名角色 MUST 在 `inception_key_max_online_window` 内退出。推荐窗口为 ≤1h；24h 只是协议硬上限，deployment policy MUST NOT 配置更长窗口。`personal_node` / `small_team` profile 在首台 `ck.device.authorize` accepted 后 SHOULD 立即触发 `did:webvh` entry 1 写入或封存流程，不应等待硬上限。退出方式只能是：（a）写入 `did:webvh` entry 1 或等价 DID method operation，把日常 update / device authorization 权限轮换到新的 controller / device key，并从首台设备销毁 inception private key；或（b）把 inception key 封存为 recovery-only key，放入 secret storage / threshold recovery，记录 `sealed_at`、`expires_at?`、allowed recovery method，并禁止在线日常签名。窗口过期后，receiver / Auth Server MUST 拒绝 inception key 继续签发 `ck.device.authorize`、`ck.session.grant`、长期 capability 或 ordinary DID update，并写入安全审计；它只能按已声明 recovery policy 进入恢复流程。它 MUST NOT 长期作为日常 device signing key——暴露面应被限制到 inception bootstrap 与 recovery。

   **接收端独立 enforce（normative，与 [`../crypto-media/encryption-and-audit.md` §2.4.1](../crypto-media/encryption-and-audit.md) 的 `relaxed_window` 接收端独立检查纪律对齐）**：receiver / Auth Server MUST NOT 静默采信 deployment 自报的更长 `inception_key_max_online_window`。它 MUST 以 inception bootstrap 证据中可验证的时间戳为锚，按本地时钟**独立计算** inception key age；当该 age 超过 24h 协议硬上限时，无论 deployment policy 声明的窗口为何，MUST 拒绝该 inception key 签发的 `ck.device.authorize` / `ck.session.grant` / 长期 capability / ordinary DID update，并为该拒绝分配专用 reason_code `inception_key_window_exceeded`。deployment policy 配置的更长窗口对接收端 24h 硬上限无效，receiver 不得据此放行。

   **age 锚点的可信时间源（normative，防 versionTime 回填）**：entry-0 自报的 `did:webvh` `versionTime` **不是**可信时间源——它由 hosting domain 写入，被劫持的 hosting domain 可把 entry-0 的 `versionTime` 回填到过去（或保持在窗口内），从而把一份实际已超 24h 的 inception key 伪装成仍在窗口内，绕过本节硬上限。这与 [`event-auth-state-resolution.md` §4.3](../authz/event-auth-state-resolution.md) 中 distance 只采信"进入 Seal 签名 transcript 的 notary 提交时间"、不采信 producer 自报墙钟的纪律同源。因此：
   - inception key age 的锚点 **SHOULD** 取 **witness / watcher 对 entry-0 的签名背书时间**（witness 是独立于 hosting domain 的第三方，其签名 transcript 覆盖 entry hash 与背书时间，hosting domain 无法单方面回填）。receiver 持有该 witness 背书时间时 MUST 以它（而非 entry 自报 `versionTime`）为锚计算 age。
   - 仅当 **witness 缺失**（例如 §5.0.1 step2 witness 尚未补签，或 `personal_node` profile 单 witness / 无 witness）时，receiver 才退回以 entry-0 自报 `versionTime` 为锚，但此时 MUST 采用**更短的窗口**并配合**更强 UI 警示**：把该 inception 视为 `degraded_no_witness`（见 [`identity-did.md` §4.2.1](./identity-did.md)），其 inception 窗口上界 SHOULD 显著短于 24h（推荐 ≤1h，与 step5 推荐窗口一致），并向用户展示"inception 时间锚不可独立验证、仅凭 hosting domain 自报"的明确警示，MUST NOT 把它与 witness-背书的 inception 展示为等强度（与 §5.0.4 UI 强度要求一致）。
   - `personal_node`(`did:web`) 路径同理：其 continuity proof 由 inception key 单签（§5.0.2），无独立第三方时间背书，receiver MUST 按上一条 witness 缺失的更短窗口 + 更强警示处理，不得以 DID Document 自报时间为可信锚放行长窗口。
6. **Genesis recovery policy**：first-backup gate 之前，客户端 MUST 先把 genesis `ck.schema.recovery_policy.v1` 发布到 principal control stream，形成当前 accepted recovery policy。该 policy MAY 声明 threshold、hardware module 或 trusted recovery service 作为释放 recovery private key 的方式，但这些因素属于 recovery policy / proof 层，不是 key-backup envelope 的 `recipient_method`。
7. **First-backup gate（normative）**：inception key 退场（步骤 5）之前，客户端 MUST 完成以下二者之一，作为 inception 窗口关闭的硬前置条件：
   - 发布一条 `backup_class="did_recovery"` 的 `ck.schema.key_backup.v1` envelope，`series_seq=0`，`recipient_method="recovery_public_key"`，加密给 genesis recovery policy 或当前 DID Document 声明的 recovery key agreement 公钥，并携带顶层 `recovery_policy_ref{policy_id, policy_version}` 绑定当前 accepted recovery policy（`auth_data.signed_fields` MUST 覆盖该字段）。`did_recovery` envelope **不得**使用 `passphrase_kdf`、`secret_storage_key`、`threshold_recovery` 或 `hardware_wrapped_key`；门限/硬件只用于释放 recovery private key，单一口令不得控制 DID recovery。或
   - 写入一份带签名的 offline-sealed receipt（纸质 / 硬件钱包 / 物理离线 module），由 inception key 签发并记录 fingerprint、`sealed_at`、allowed recovery method；UI MUST 要求用户二次确认已离线持有该 receipt。

   实现 MUST 在该 gate 失败时阻止 inception 退场，并向用户展示明确的"当前为单点失效"警告；实现 MUST NOT 把 inception key 在未完成 gate 的情况下静默销毁。当 `personal_node` profile 用户拒绝完成 gate 时，实现 MAY 允许继续，但 MUST 把账号标记为 `single_point_of_failure=true`，并在后续每次启动时提醒用户。
8. **后续设备**：第二台及以后设备走 §5.1 标准流程，由首台已授权设备签发 `ck.device.authorize`。

#### 5.0.2 `personal_node` Profile 降级路径（principal_method=`did:web`）

`personal_node` deployment profile 选择 `did:web` 作为 principal method 时，没有 entry-0 controller proof 可供引用。降级路径：

1. 客户端本地生成 `inception_keypair`，并以它构造一个临时 `did:key:<inception_pub>`。
2. 客户端把 `did:key:<inception_pub>` 作为 `ck.did.proof.continuity` 的 `old_did` 签发 continuity proof，绑定到目标 `did:web:<host>` 作为 `new_did`。该 continuity proof 由 inception key 单方签署即生效（personal_node profile 接受这种"自我升级"，因为 stake 低）。
3. 客户端将 `did:web` DID Document（含 inception public key 作为 `verificationMethod` / `assertionMethod`）写入 hosting domain，并发布该 continuity proof。
4. Principal control realm genesis、首台设备自授权按 §5.0.1 步骤 3-5 执行；`refs[]` 携带 `role="did_inception"` 条目引用 continuity proof + DID Document hash，而不是 `did:webvh` entry 0。
5. `personal_node` profile 升级到 `small_team` 或更高 profile 时,MUST 走 **§5.0.5** 的跨 method 迁移路径切换到 `did:webvh`,期间历史 Event 保留 `did:web` `actor_id`。

#### 5.0.3 验证规则

Receiver 接受 principal 的首批 control stream Event 时，MUST：

- 解析 control realm genesis Event 的 `refs[]`，找到 `role="did_inception"` 条目。
- 按 DID method 验证该引用：
  - `did:webvh`：拉取 `did.jsonl` entry 0，校验 SCID、entry hash、controller proof，确认 inception key 与 genesis Event `proofs[].verification_method` 一致。
  - `did:web` (personal_node)：拉取当前 DID Document，校验 inception public key 出现在 `verificationMethod` 中，并校验 continuity proof 由 `did:key:<inception_pub>` 签发。
  - 其他 method：按对应 method evidence 验证 inception 控制权。
- 校验首台 `ck.device.authorize` Event 的 `authorized_by` 引用与 inception key 一致；不接受 `authorized_by` 引用任何尚未 sealed 的 device。
- Inception bootstrap 成功后，receiver MUST 标记该 control realm 已通过 inception；后续 §5.1 的 `ck.device.authorize` Event MUST `authorized_by` 一台已 sealed 的 device，不得再次自授权。

**后续 device authorization 的 control Realm 归属校验（normative）**：reducer 接收非 inception-bootstrap 的 `ck.device.authorize` 时，不能只验证 device signature 与 `authorized_by` 链。它还 MUST 校验 enclosing `realm_id` 指向的 Realm 已 accepted 且满足全部 control-stream 绑定：(a) `fields.purpose == "principal_control"`；(b) `schema_refs` 包含 `ck.profile.principal_control_realm.v1`；(c) `created_by` 等于被授权 device 所属 principal DID，且该 DID 与签发 `authorized_by` device 的 principal 一致。任一不满足时 MUST `failed_precondition`，`reason_code=device_authorized_principal_control_realm_mismatch`；实现不得把该 event 当作普通非 PCR Realm 中的业务事件继续处理，也不得把另一个 principal 的 control Realm 状态复用于当前 principal。

#### 5.0.4 攻击模型

Inception bootstrap 的密钥学根**仅强于** DID method 自身的 inception 证据：

- `did:webvh` 提供 SCID + entry hash + controller proof，并可叠加 witness——攻击者需要同时控制 hosting domain 和 ≥1 trusted witness 才能伪造 inception。
- `did:web` 仅提供"hosting domain 当前内容"——攻击者控制 DNS/TLS 即可静默替换 inception。这正是 `personal_node` profile 之外不允许 `did:web` 作为 principal method 的根本原因（见 [`identity-did.md` §3](./identity-did.md) 与 [`server-threat-model.md` §2](../security/server-threat-model.md)）。
- `did:key` inception **MUST NOT** 直接作为长期 principal——它必须在 §5.0.1 / §5.0.2 中升级为 `did:webvh` 或 `did:web`。

实现 MUST 在 UI 中向用户清楚展示 inception 路径的密钥学强度（"已 witness 的 did:webvh 链" vs "仅 hosting domain"），不得在 onboarding 中把两者展示为等强度。

#### 5.0.5 `personal_node`(`did:web`) → `small_team`(`did:webvh`) 跨 method 安全升级

**问题**: `personal_node` 阶段的 `did:web` inception 只受 hosting domain DNS/TLS 保护；若用户在注册期间 DNS 被劫持，攻击者可写入伪造 inception(并控制 inception key)。一旦该 principal 直接"无审"升级到 `small_team` 的 `did:webvh`,被劫持的 inception 历史会被当作正常历史延续，所有后续 capability / device authorization / state 都建立在攻击者根之上。

> **`purpose` 取值边界**(与 [`identity-did.md` §4.2.2](./identity-did.md) 互引):本节描述的是**同一物理身份从 `did:web` method 升级到 `did:webvh` method** 的场景,continuity proof 的 `purpose` MUST 为 `principal_method_upgrade`,且 MUST 走本节 §5.0.5.1–§5.0.5.4 的 OOB + 双签硬条件。这与 `principal_migration`(同 / 跨 method 的一般账户迁移，如更换 hosting / 组织迁移，见 §4.2.2 第 1–5 步常规流程)语义不同:`principal_method_upgrade` 专指"弱 method inception 根升级到强 method 根"这一受 DNS 劫持威胁的特例，因而附加本节的强制 OOB 与 inception fingerprint 二次确认;`principal_migration` 在原 DID 仍可解析时只需常规 continuity proof + 反向 acceptance。实现 MUST NOT 用 `principal_migration` 绕过本节针对 `personal_node` 升级的 OOB 硬条件。

为此，跨 method 升级 **MUST** 满足以下硬条件，否则 receiver MUST `reject` 升级 transition Event(reason `inception_upgrade_evidence_insufficient`):

##### 5.0.5.1 OOB inception fingerprint 验证

用户 MUST 在升级前通过**至少一条独立信任通道**确认 `did:web` 阶段的 inception public key fingerprint:

| 信任通道 | 形态 | UI 强度 |
| --- | --- | --- |
| 离线纸质 / 硬件钱包记录 | 用户在 `personal_node` 注册成功后立即在 UI 中导出 fingerprint(SHA-256(inception pubkey) 前 32 bytes hex) 并由用户离线记录 | 强 |
| 物理面对面 | 邮票号 / QR 在物理设备间扫描 | 强 |
| 已知可信第二信道 | 邮箱(非托管在同一 hosting domain)、Signal、电话回拨 | 中 — UI MUST 警告"通道需独立于注册时的 DNS/TLS 链" |
| 同一 hosting domain 内的 HTTPS 凭证 | — | **不接受**(同源已被假设劫持) |

UI 在升级流程中 MUST 强制要求用户**重新输入或扫描** fingerprint,而不是从本地缓存读取——否则攻击者把首次注册期间植入的 fingerprint 缓存也算作"用户确认"。

##### 5.0.5.2 Inception key 重签 transfer proof

升级 transition Event(`ck.did.proof.continuity`,`old_did=did:web:<host>`,`new_did=did:webvh:<scid>:<host>`)**MUST** 满足 `ck.schema.did_continuity_proof.v1` transfer envelope 结构；reducer 与 receiver 直接消费下列字段集合，并按 schema 与签名链验证：

```json
{
  "schema": "ck.schema.did_continuity_proof.v1",
  "old_did": "did:web:<host>",
  "new_did": "did:webvh:<scid>:<host>",
  "purpose": "principal_method_upgrade",
  "trust_domain": "ck:trust_domain:<deployment-or-realm>",
  "audience": ["did:webvh:z2Cxbwy2o7AmBLzdfDbix8WAP:registry.example"],
  "issued_at": "2026-05-19T00:00:00Z",
  "transfer_evidence": {
    "old_did_document_canonical_digest": "sha256:<64-hex>",
    "old_did_document_fetched_at": "<RFC 3339 UTC>",
    "inception_public_key_fingerprint": "sha256:<64-hex>",
    "user_oob_confirmation_id": "<opaque user-side confirmation token>",
    "user_oob_confirmation_method": "offline_paper|physical_meet|independent_channel"
  },
  "signature_chain": [
    {
      "principal_id": "did:web:<host>",
      "verification_method": "did:web:<host>#<inception-key>",
      "algorithm": "Ed25519",
      "payload_digest": "sha256:<64-hex>",
      "signature": "<base64url-signature>"
    },
    {
      "principal_id": "did:webvh:<scid>:<host>",
      "verification_method": "did:webvh:<scid>:<host>#<entry-0-controller-key>",
      "algorithm": "Ed25519",
      "payload_digest": "sha256:<64-hex>",
      "signature": "<base64url-signature>"
    }
  ]
}
```

关键 normative 规则:
- `signature_chain` **必须**同时含两段签名:**inception key**(原 `did:web` 主体)+ `did:webvh` entry-0 controller key(新 method 主体)。任一缺失或签名失效 → reject `inception_upgrade_signature_chain_invalid`。
- `inception_public_key_fingerprint` 必须 byte-for-byte 等于 `did:web` DID Document 中 inception key 对应的那条 `verificationMethod[]` 条目（即 §5.0.5.3 step 3 中签名验证命中的条目；§5.0.2 只要求 inception key **出现在** `verificationMethod` 中，不固定其下标）的派生 fingerprint;同时必须在 `transfer_evidence` 中以 user-readable 形式呈现给 receiver(便于 receiver 二次校验)。
- `user_oob_confirmation_id` 是 user-side 不透明 token——客户端 SHOULD 把 OOB 确认结果写入 user-private secret storage,服务端 / receiver 不 trust 该字段为真实人类确认证据，但**保留**以便审计回放与 UI 重现。`user_oob_confirmation_method` 是枚举 hint,receiver MAY 用它把"通过弱通道(independent_channel)确认的迁移"打上额外的低信任标记。
- 整个 transfer envelope MUST 在签名 transcript 中包含 `old_did_document_canonical_digest`——这一字段 freezes 攻击者对 hosting domain 在升级时刻**之后**继续替换 DID Document 的可能性(任何替换都会让 hash 不再匹配 receiver 拉取的新 document)。
- **Replay 域绑定(`trust_domain` / `audience`)**:升级 transition envelope MUST 在签名 transcript 中包含当前接收语境的 `trust_domain` 与至少一个 `audience`。Receiver MUST 校验 `trust_domain == current_receive_context.trust_domain`，且自身 service DID、Realm registry DID 或明确配置的 verifier id 位于 `audience` 中；任一不匹配 MUST reject `inception_upgrade_evidence_insufficient`。该绑定与 `signature_chain` 双签、`transfer_evidence` 一起构成升级证明，防止合法升级 envelope 被跨 verifier / 跨 trust domain 重放。
- **反向 acceptance**:本节的双签 `signature_chain` 已在**同一 envelope 内**承载新 DID 侧的接受证明——`signature_chain[1]` 由 `did:webvh` entry-0 controller key(新 method 主体)签署，即等价于 [identity-did.md §4.2](./identity-did.md) 要求的反向 `CokretContinuityAccepted`,无需新 DID 侧再发独立 acceptance Event。即:跨 method 升级以"单 envelope 双签"满足双向 continuity,而 §4.2 的"`CokretContinuityProof` + 反向 `CokretContinuityAccepted` 两个 service entry"模式适用于原 DID 仍持续可解析的同 method / 一般迁移场景。

##### 5.0.5.3 Receiver 验证规则

任何接收升级 transition Event 的 receiver(Principal Server、其他 federation peer、新设备 join 时)**MUST**:

1. 拉取 `old_did` 的当前 DID Document,canonicalize 后 hash 比对 `transfer_evidence.old_did_document_canonical_digest`;不一致 → reject `inception_upgrade_old_document_hash_mismatch`。
2. 校验 `transfer_evidence.old_did_document_fetched_at` 是 RFC 3339 UTC，且 receiver 当前时间与该值的差值不得超过升级 evidence 新鲜度上限常量 `inception_upgrade_evidence_max_age = 168h`（7 天）；超过窗口 → reject `inception_upgrade_evidence_stale`。Receiver MAY 使用更短 deployment policy，但 MUST NOT 接受超过 `inception_upgrade_evidence_max_age` 的 transfer evidence。

   > 说明：`inception_upgrade_evidence_max_age` 是**在线升级 transfer evidence 新鲜度**的独立常量，与 [`identity-did.md` §3.4](./identity-did.md) `did:webvh` outage 期 per-entry cache age 7 天上限**语义域不同**（前者约束升级证据的拉取时效，后者约束 outage cache entry 的可用性）。两者当前**取值恰好相同（168h / 7 天）但不绑定**：调整任一处不应自动推导改动另一处，引用方 MUST 各自独立解读。
3. 校验 `signature_chain` 两段签名:inception key 签名(`verification_method` 必须出现在被 hash 的 old document `verificationMethod[]` 内)+ `did:webvh` entry-0 controller key 签名(必须能在 `did:webvh` `did.jsonl` entry 0 找到)。任一失败 → reject `inception_upgrade_signature_chain_invalid`。
4. 校验 `inception_public_key_fingerprint`,确认它等于步骤 3 中签名验证命中的那条 `verificationMethod[]` 条目的派生 fingerprint(不要求该条目位于 index 0);失败 → reject `inception_upgrade_fingerprint_mismatch`。
5. 校验 `trust_domain` 与 `audience` 域绑定；失败 → reject `inception_upgrade_evidence_insufficient`。
6. 校验 `did:webvh` `entry 0` 的 SCID / entry hash / controller proof(标准 `did:webvh` inception 验证)——这一段独立于 `did:web` 阶段。
7. 写入"该 principal 已通过 §5.0.5 跨 method 升级"标记；后续 Event 的 `actor_id` MAY 是 `did:web:...`(历史 Event)或 `did:webvh:...`(升级后 Event);receiver MUST 把两者视作同一 principal,但**不接受**任何新签名的 Event 仍引用 `did:web` inception key——升级后 inception key MUST 进入 `did:webvh` rotation 链或销毁(§5.0.1 步骤 5)。

##### 5.0.5.4 不允许的简化

- Forbidden: "用户点 OK 即升级"(无 OOB confirmation_method / 无 inception_public_key_fingerprint 二次确认) — receiver MUST reject `inception_upgrade_evidence_insufficient`。
- Forbidden: inception key 单签升级(仅 inception key 签 transfer envelope) — receiver MUST reject `inception_upgrade_signature_chain_invalid`(缺 entry-0 controller key 那一段)。
- Forbidden: DNS / hosting domain 内嵌"确认页"作为 OOB(同源攻击窗口未脱离)。
- Forbidden: 升级后继续接受用 `did:web` inception key 签发的新 Event(必须在升级落盘后立即把该 key 标 retired / archived;之前已签发并 sealed 的历史 Event 保留)。

##### 5.0.5.5 安全代价登记

- 该流程把 personal_node 阶段被 DNS 劫持的损害限制在 personal_node Realm 内部；升级后 attacker 无法通过升级路径继承新 method 的根。
- 代价:升级流程对用户**强制**至少一次离线 / 独立通道确认,UI 不能"自动一键升级"。这是明确取舍:为防止注册期 DNS 劫持继承，引入一次性 OOB 友好度成本。
- 对从未通过 personal_node 阶段(直接以 `did:webvh` 走 §5.0.1)的 principal,本节不适用。

#### 5.0.6 托管 DID 的入册权威(account-authority enrollment)

[`account-lifecycle.md` §2.1.1](./account-lifecycle.md) 允许 account-first onboarding 由 auth service 为用户代铸**托管 DID**。该模型下，设备授权的信任根是 **DID 文档指派的入册权威**,而非客户端自持的 inception key 或 SSK。规则:

1. **入册权威指派(in-document,可自证)**:代铸 DID 时,account authority MUST 在 principal DID 文档中以**窄关系**指派入册权威 —— 一条 `CokretDeviceEnrollmentAuthority` service 条目(`serviceEndpoint` 指向权威 DID,见 [`identity-did.md`](./identity-did.md)),或一条 `capabilityDelegation` verification method。**MUST NOT** 复用 `controller`(那是改写身份根的强权，入册权威只应能入册)。文档锚定的指派是地面真值;deployment 信任策略 MAY 收紧(交集)或在文档无法表达时补空(回退，标记低 assurance),**MUST NOT** 并集扩权(本地单方面新增文档未指派的权威 = 越权 + 联邦 split-brain)。
2. **持久入册密钥(≠ inception key)**:入册权威持有一把**持久**签名密钥用于签发 `ck.device.authorize`。它与 §5.0.1 step5 必须退场的 inception key 是不同密钥:inception key 仍按 step5 在 `inception_key_max_online_window` 内退场；入册密钥作为常设服务密钥长期持有合规，并可轮换(轮换不影响既有授权，见下)。
3. **设备授权走 `service_attested`**:设备入册按 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md) 的 `enrollment_authority_binding` / `service_attested` 形态，而非 §5.0.1 inception 自授权或 §5.1 的 SSK cross-signing。account authority **MUST NOT** 持有或伪造本 principal 的 SSK。客户端经 canonical gate 操作 `ck.gate.account.command.enroll_device`（`POST /_cokret/gate/account/device-enroll`，见 [`../sync/service-http-binding.md`](../sync/service-http-binding.md) 与 §5.4）向入册权威请求该签名；它与本节 step5 `pair_device`（已授权设备 SAS/QR 审批）互补，用于无兄弟设备可审批的 bootstrap / 首台设备。
4. **按时点解析，轮换不失效**：receiver 复验历史 `ck.device.authorize` 时，对**具备 history-resolution method 的入册权威 DID**（如 `did:webvh`），MUST 按 Event accepted-at 做按时点解析（`did:webvh` 历史 `versionTime`），用当时有效的入册密钥验签——轮换不使既有授权失效。

   **无 history-resolution method 的入册权威(normative，inline 快照 + controller proof)**:当入册权威 DID 是**无可验证历史 method**(典型 `did:web`——它只反映"当前 DID Document",一旦入册密钥轮换或 hosting domain 被劫持回填，旧 `ck.device.authorize` 既无法按时点解析当时的 verification method、也可被替换后的当前文档伪造复验)时，按时点解析不可用。此时设备授权事件 MUST 在 `enrollment_authority_binding` 中 **inline 携带签发时刻的 verification method 快照**(签名公钥 multibase / JWK + 其在入册权威 DID 文档中的 method id)以及**该 key 的 controller proof**(由入册权威 DID 当时的 controller key 对"该 verification method 属于本 DID 且获授签发设备授权"的签名)，使历史复验**只依赖事件内自带的快照 + controller proof**、不依赖对 `did:web` 当前文档的在线解析。receiver 复验时 MUST：(a) 用 inline 快照中的公钥验 `proofs[]`;(b) 验 controller proof 把该快照公钥链接到入册权威 DID 的 controller 集；(c) 校验 binding 的 `authority_did` / `authorization_ref` 与快照一致。缺失 inline 快照或 controller proof 的、由无 history-resolution method 入册权威签发的 `ck.device.authorize` MUST `reject`(reason `device_enrollment_authority_snapshot_missing`)。

   作为该 inline-快照要求的替代，deployment policy MAY 直接**禁止 `did:web` 等无历史 method 作入册权威轮换**——要求入册权威在轮换前先按 [`identity-did.md` §4.2.2 / §5.0.5](./identity-did.md) 升级到 `did:webvh`,使按时点解析重新可用。v1 推荐前者(inline 快照 + controller proof)，因为它不强制所有托管 DID 部署升级 method。

   > **schema 协调（留协调者）**：上述 inline 快照 + controller proof 需要在 `device_enrollment_authority_binding`（[`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json) `$defs/device_enrollment_authority_binding`，当前 `additionalProperties:false` 且仅含 `kind`/`authority_did`/`authorization_ref`）新增可选字段（建议 `authority_verification_method_snapshot {method_id, public_key_multibase|public_key_jwk, alg}` 与 `authority_controller_proof {controller_method_id, signature, signed_at}`），并新增 reason_code `device_enrollment_authority_snapshot_missing`。正文已定义语义；schema / error-code-registry 字段新增留协调者。
5. **provenance**:每条设备授权记录 MUST 记录其入册权威与来源(文档锚定 / 仅策略);联邦只采信文档锚定者。

自主权路径(客户端自持控制密钥、用 `capabilityDelegation` 指向自有 verification method 作入册权威)与本节对称，采用同一 `service_attested` 信封，仅 `authority_did` 指向用户自有控制密钥所属 DID;实现 MAY 暂不启用该分支，但 schema 与校验 MUST 为其保留扩展位，不得静默放行未指派的权威。

### 5.1 新设备加入（首台设备已存在）

推荐流程：

1. 新设备本地生成 device key。
2. 新设备先通过 `ck.gate.account.command.issue_session_grant` 获得 fresh-device restricted session grant，或通过二维码/手动码把同等 pairing payload 交给旧设备。该 grant 只能用于同 principal 的 `ck.key.verification.*` bootstrap；在完成 step 5 的 SAS/QR transcript 验证之前，MUST NOT 读取 E2EE history、解锁 key backup 或请求 `ck.secret.*`。**SAS 验证成功后例外**（normative）：该 fresh-device grant MAY 仅向同一 SAS transcript 绑定的已授权设备发送 `ck.secret.request`，用于无口令 secret 直传（[`device-lifecycle.md` §10.7](../crypto-media/device-lifecycle.md)）；该例外仅限 transcript 绑定的设备对，不放宽 E2EE history 读取或 key backup 解锁。
3. 新设备通过 `POST /_cokret/self/device_messages` 向同 principal 的已授权设备发送 `ck.key.verification.request`。content MUST 至少包含 `transaction_id`、`from_device`、`methods`、`timestamp`、`expires_at`；用于设备授权时 SHOULD 带 `purpose="same_principal_device_authorization"`、`pairing_code`、`new_device_pubkey`、`challenge_signature`、`gate_audience`、`request_canonical_digest` 与 `device_metadata?`（wire 示例见 [`device-lifecycle.md` §7](../crypto-media/device-lifecycle.md)）。
4. 已授权设备的主接收路径是 `GET /_cokret/self/account/subscribe` 的 `delta.to_device.messages[]`；push 只能作为唤醒提示。若 `delta.to_device.limited=true`、本地 dispatcher 需要补洞，或旧设备当前没有完整 account subscribe，才使用 `GET /_cokret/self/device_messages?from=<cursor>&limit=n` 补拉。UI MUST 显示 requesting device metadata 与 pairing code，要求用户和新设备屏幕上的 code 比对。
5. 用户在已授权设备上批准并完成 SAS/QR transcript 后，该设备调用 `POST /_cokret/gate/account/device-pair`，提交 transcript 绑定的 `pairing_code`、`new_device_pubkey`、`challenge_signature` 与当前设备 fresh proof。`/_cokret/self/devices/pairing-requests*` 不是 v1 core approval surface。 <!-- lint-ignore: CW001 - forbidden historical path named only as a negative example. -->
6. Events API / identity registry 接受并传播 `ck.device.authorize` 与 `ck.device.list_update`；gate 返回 `authorized_event_ref` 或等价引用。新设备可通过 `ck.key.verification.done` 中的 hint、重新签发/升级后的 session grant、或后续 account subscribe/device list baseline 观察结果，但 MUST 以 durable device list 为准，之后才开始同步 Event history、Realm membership 和必要的 MLS Welcome / key share。

如果用户没有任何可用的已授权设备，UI SHOULD 明确优先提示"在已有设备确认"；确认不可用后，才进入恢复密钥 / social recovery 路径。新设备仅凭登录 session grant MUST NOT 获得 E2EE history key。

`ck.device.authorize.payload` 示例：

```json
{
  "principal_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "device_public_key": "z6Mks...",
  "scopes": [
    "ck.self.events.query.describe",
    "ck.self.events.command.submit",
    "ck.self.account.stream.subscribe",
    "ck.self.keys.keypackages.upload.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "authorized_by": "ck:device:01964136-8000-7000-8000-000000000000",
  "cross_signing_binding": {
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ck_self_signing_v1",
    "alg": "EdDSA",
    "ssk_generation": 1,
    "signature": "base64url..."
  },
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#device-old",
    "jws": "..."
  }
}
```

### 5.2 设备吊销

设备丢失、出售、被恶意控制或员工离职时，MUST 发布 `ck.device.revoke`。

吊销后：

- Events API MUST 拒绝该设备的新签名写入
- authz MUST 视相关 session grant 失效
- 加密 Realm SHOULD 通过 MLS Remove 推进 epoch；Remove 的 `governance_binding.membership_frontier` MUST 覆盖该 `ck.device.revoke` 事件本身或覆盖已导入该撤销的 Realm governance Move，且该撤销 MUST 已被 principal control stream 的 accepted Seal 覆盖
- 客户端和受托 projection executor SHOULD 标记已撤销设备产生的未确认 Operation 为高风险

## 6. Session Grant

Session grant 用于 OIDC / SSO、浏览器短会话、远程执行环境。  
Cokret v1 使用 `ck.session.grant` 作为 principal control stream 中的标准 durable control event 类型。

`ck.session.grant.payload` 示例：

```json
{
  "grant_id": "ck:grant:01964198-0000-7000-8000-000000000000",
  "realm_id": "ck:realm:01964198-7000-7000-8000-000000000000",
  "issuer": "did:webvh:z99jGJ9cd12QASVtC6r35kV5q:auth-gateway.example.com",
  "subject": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "session_public_key": "z6Mss...",
  "audience": "https://app.example.com",
  "scopes": [
    "ck.self.events.command.submit",
    "ck.realm.discover",
    "ck.object.read",
    "ck.strand.update",
    "ck.message.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-27T00:00:00Z"
}
```

> 注：`ck.session.grant` 是 principal control stream 事件，`realm_id` MUST 等于 subject 的
> principal control realm（§4.1）。本字段是 control event 必填项；省略 MUST 被 reducer
> 以 `schema_violation` 拒绝。

规则：

- session grant MUST 由可信 issuer 签名
- session key MUST NOT 超过 grant 的有效期
- session grant SHOULD 绑定 audience
- 在条件允许时，session grant SHOULD 在 WebCrypto / 平台 keystore 中以不可导出方式存储
- session grant 撤销 MUST 由下列 **canonical 撤销机制** 之一表达：accepted `ck.session.grant` 状态更新（含 supersede / expiry），或 device / account revoke（[`account-lifecycle.md` §9](./account-lifecycle.md) Session Revocation、§7.1 Deactivation Fanout 的 `ck.session.grant` 撤销链）。除上述 canonical 机制外，仅当某 extension / deployment profile **显式注册并声明** 了一个 credential status mechanism（profile MUST 给出该 mechanism 的 canonical event / 字段定义，对照 agent key 撤销的具体 `ck.agent.key.revoke`）时，方可使用该 profile 注册的机制表达撤销；未注册、无明确 canonical event / 字段定义的机制 MUST NOT 用于 session 撤销，且任何情况下 MUST NOT 使用未注册的 `ck:revocation-list:*` typed ID。

## 7. 密钥备份

### 7.1 备份内容

Cokret v1 将密钥备份分为三个不同密钥域。实现 MUST 在 metadata 中声明备份域，且不得把一个域的解锁材料当作另一个域的授权证明：

- `did_recovery`：恢复 DID 控制链所需的 recovery key share、门限恢复 share metadata 或受信恢复服务证明。它只能用于 `recovery_policy` 允许的 `recover` / `rotate` / `ck.device.authorize` 等操作。
- `secret_storage`：保存 `self_signing_key`、`user_signing_key`、recovery secret、MLS group secrets backup key、`account_data_namespace_key`、applet delegated device secret 和 encrypted private account data cache。`account_data_namespace_key` 属于 `secret_storage/account_data_namespace/v1` 子域，只用于 [`../discovery/client-preferences.md` §2.2](../discovery/client-preferences.md) 的 account-data key 派生，不得暴露给服务端或跨 principal 复用。其中**承载 SSK 的恢复定向副本**（`recipient_method="recovery_public_key"`）属于 fresh-device 恢复的 recovery-bootstrap unlock set：它的域仍是 `secret_storage`，但因为只用 recovery 公钥加密，可在设备授权之前仅凭 recovery 私钥解锁（见 [`../crypto-media/device-lifecycle.md` §15 step 4](../crypto-media/device-lifecycle.md)）。这不破坏域隔离——SSK 不解密 MLS 历史，攻破该副本不等于攻破 `mls_history` 或 `did_recovery`。
- `mls_history`：保存用户已有权读取的 Realm / MLS-backed Circle 的 MLS group state、历史 epoch key material、pending Welcome 和必要的 epoch 缺口恢复 metadata。

域隔离规则：

- 每个 `backup_class` MUST 使用独立 salt、KDF context、HKDF info 和 AEAD associated data；一个域的 derived key、commitment key 或 wrap key 不得直接用于另一个域。
- AEAD AAD MUST 绑定 `actor_id`、`device_id`、`backup_class`、`backup_version`、item type、created_at 和 schema/profile id，防止把 ciphertext 从一个域重放到另一个域。
- 即使用户选择同一个 passphrase，客户端也必须先用 KDF 得到 root unlock key，再用 `HKDF(root, info="cokret-key-backup/<backup_class>/<subdomain>/v1")` 派生域内子密钥；不得复用裸 KDF 输出。
- `did_recovery` 域不得和 `mls_history` 域共享 wrap key、recovery share 或 key commitment。攻破 `mls_history` backup key 不得允许 DID rotate / recover；攻破 DID recovery share 也不得直接解密 MLS 历史。
- **组织 / Realm Recovery Key（RRK）属 history-recovery 域**：Realm `durability_policy` 引用的 RRK（[`identity-did.md` §8.3](./identity-did.md)、[`../models/realm-and-space.md` §2.3.1](../models/realm-and-space.md)）是 principal（通常为 Organization）持有的、用于解 Realm 历史的 HPKE 接收钥匙，与本域 `mls_history` 同性质而作用域为 Realm。它 MUST 独立于该 principal 的 `did_recovery` 钥匙：同一把 key MUST NOT 既作 `did_recovery` 又作 `CokretRealmHistoryRecoveryKey`。RRK 私钥的离线保管 / 门限 / 硬件释放复用 §8 recovery policy（subject = 该 principal、域 = history-recovery）。
- `self_signing_key` / `user_signing_key` 与 MLS group secrets backup key MUST 分成不同 backup envelope 或不同 subdomain key，并 SHOULD 要求不同 passphrase、硬件保护或门限恢复策略。**单一 passphrase 同时控制身份签名和 E2EE 历史**的失败模式在任何部署上都不可接受。只有 `ck.profile.personal_node.v1` MAY 接受 `mixed_secret_storage=true` 的本地备份 envelope；`small_team`、`organization`、`high_security_organization`、`sovereign_deployment` 等 profile MUST 拒绝该 flag。mixed 模式若使用 `passphrase_kdf`，MUST 使用 Argon2id 且 `memory_kib >= 262144`、`iterations >= 4`、`parallelism >= 1`。

以下材料 MAY 进入客户端加密备份，但 MUST 只以密文形式保存：

- recovery key share 或门限 share。
- `self_signing_key`、`user_signing_key` 和 recovery secret。
- MLS group secrets backup key。
- MLS group state、历史 epoch key material、pending Welcome。
- encrypted private account data cache 和 private account state。

以下材料 MUST NOT 进入普通在线密钥备份：

- 当前设备的 device private key。新设备 MUST 本地生成新 device key，再由有效设备或 recovery policy 授权。
- session key、refresh token 或浏览器临时会话材料。
- 已发布或已领取的 MLS KeyPackage private key；设备 SHOULD 重新生成 KeyPackage。
- 明文 principal signing key、inception key 或完整 recovery private key。高权限根材料只能离线保存、硬件保护或门限封装；若以备份形式存在，也必须拆分或封装为 `did_recovery` 域，且不能被服务端解密。

备份 MUST NOT 以明文保存私钥。

### 7.2 Backup Envelope

标准备份对象使用 `ck.schema.key_backup.v1`。服务端只校验 envelope metadata、访问控制和签名，不得要求上传解锁口令、recovery private key、硬件解锁材料或任何可直接解密 ciphertext 的 secret。

示例：

```json
{
  "backup_id": "ck:backup:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
  "backup_class": "secret_storage",
  "backup_version": "kb_1",
  "series_id": "ck:backup_series:01964137-1000-7000-8000-000000000000",
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
      "aead_profile": "ck.aead.xchacha20_poly1305.v1",
      "nonce_salt": "b64uRandom128Bits",
      "nonce": "base64url..."
    },
    "key_commitment": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "domain_separation": {
    "hkdf_info": "cokret-key-backup/secret_storage/account_keys/v1",
    "subdomain": "account_keys",
    "aead_aad": {
      "schema": "ck.schema.key_backup.v1",
      "actor_id": "did:webvh:z2gNJAM6eKtNKMnbxHuqHCnaw:alice.example",
      "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
      "backup_class": "secret_storage",
      "backup_version": "kb_1",
      "created_at": "2026-05-30T00:00:00Z",
      "item_types": ["self_signing_key", "user_signing_key"]
    }
  },
  "contents": [
    {"item_type": "self_signing_key", "secret_id": "self_signing_key"},
    {"item_type": "user_signing_key", "secret_id": "user_signing_key"}
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:2108421084217842908421084210842121084210842178429084210842108421",
  "auth_data": {
    "device_id": "ck:device:01964137-0000-7000-8000-000000000000",
    "signature": "base64url..."
  }
}
```

实现 SHOULD 使用现代 KDF，例如 Argon2id。新创建的 `recipient_method="passphrase_kdf"` envelope MUST 满足以下机器下限（base v1 无条件要求，`ck.schema.key_backup.v1` 同步编码）：Argon2id `memory_kib >= 65536`、`iterations >= 3`、`parallelism >= 1`；salt MUST 随 envelope 独立生成并进入 KDF 输入。
如果平台限制只能使用 PBKDF2，新创建的 PBKDF2 envelope MUST 满足 `iterations >= 600000` 且 `digest_algorithm ∈ {sha256, sha384, sha512}`，并 MUST 在 backup metadata 中声明 `degraded_profile_reason`、迭代次数、salt、KDF 参数和 profile id。`params.digest_algorithm` 是 digest 算法选择器；`params.hash` 不是合法字段，current parser MUST reject（登记于 `artifacts/migration/renames.json`）。新创建的 `passphrase_kdf` envelope（§7.5.1）不得默认使用 PBKDF2：Argon2id 可用时 MUST 优先。声明 `ck.profile.key_backup.memory_hard.v1` 是在上述 base 下限之上的更强承诺：该 profile 下 `passphrase_kdf` envelope 的 KDF MUST 是 Argon2id；PBKDF2 只允许出现在显式 degraded profile（见下）中，不满足 memory-hard 要求。

FIPS-only 部署若不能批准 Argon2id，MUST 使用显式降级 profile（例如 `fips_pbkdf2` key backup profile），并声明其安全级别低于默认 memory-hard backup profile。该 profile 至少要求 FIPS 批准的 KDF、强口令策略、在线恢复限速、失败审计和备份 metadata 中的 `degraded_profile_reason`；它不得作为公共网络默认 key backup profile。

每个 `ck.schema.key_backup.v1` envelope MUST 携带顶层 `domain_separation`，并在 `auth_data.signed_fields` 中覆盖该字段。`domain_separation.hkdf_info` MUST 等于 `cokret-key-backup/<backup_class>/<subdomain>/v1`，`domain_separation.aead_aad` MUST 绑定 `schema`、`actor_id`、`device_id`、`backup_class`、`backup_version`、`created_at` 与 `contents[].item_type`。接收方 MUST 用该对象的 canonical JSON 作为 AEAD/HPKE AAD，并验证它与外层 envelope 字段逐字节一致；服务端不得生成、修改或补全该对象。

`key_commitment` 的推荐构造（`commitment` 是 §7.1 `cokret-key-backup/<backup_class>/<subdomain>/v1` 体系下的一个 subdomain，因此 commitment 天然按 `backup_class` 域隔离，不会跨域复用）：

```
derived_key = KDF(passphrase, salt, kdf_params)
commitment_key = HKDF(derived_key, info="cokret-key-backup/<backup_class>/commitment/v1")
key_commitment = SHA256(commitment_key)
```

`recipient_method="passphrase_kdf"` 的 AEAD nonce MUST deterministic derive，但 derivation transcript MUST 包含 producer-generated `aead.nonce_salt`。`nonce_salt` 是随 envelope 新生成的至少 128-bit 随机值，不是 secret，必须进入 signed metadata / AAD；服务端不得生成、覆盖或由用户输入提供该值。

```text
nonce_key = HKDF(derived_key, info="cokret-key-backup-aead-nonce-v1")
nonce = HMAC-SHA256(
  key  = nonce_key,
  data = canonical_json({
    "backup_id": backup_id,
    "actor_id": actor_id,
    "device_id": device_id,
    "backup_class": backup_class,
    "backup_version": backup_version,
    "created_at": created_at,
    "aead": aead.name,
    "aead_profile": aead.aead_profile,
    "nonce_salt": aead.nonce_salt
  })
)[0:N_AEAD]
```

**澄清（防误读）**：`nonce_key` 的 info 为固定值不构成 §7.1 的跨域密钥复用——§7.1 禁止跨域的是 derived key、commitment key 和 wrap key；`nonce_key` 只用于 nonce 推导，且推导 transcript 已绑定 `backup_class`，nonce 输出本身按域隔离。该 info 在 interop 关键路径上（接收方 MUST 重算 nonce），不得变更。

`aead_profile` 是可选但推荐的协商标识，绑定 AEAD 算法版本、nonce 长度、tag 长度、key 长度和 AAD 构造。接收方看到不支持的 `aead_profile` MUST fail closed；不得只凭 `aead.name` 推断可接受的参数组合。未携带 `aead_profile` 的 envelope 按 `aead.name` 的 v1 默认 profile 解释，但新写入 envelope SHOULD 显式携带 profile id。

Producer MUST reject attempts to write two backup envelopes with the same nonce derivation tuple, including `nonce_salt`。`backup_id` 仍应按单写不可变处理；若需要更新备份内容，producer MUST 生成新的 `backup_id` 或至少新的 `nonce_salt` 并重新签名 envelope。Receiver MUST recompute the nonce for `passphrase_kdf` envelopes before decryption and reject mismatches or missing `nonce_salt` as `schema_violation`.

客户端 MAY 在尝试解密 `ciphertext` 前用用户输入的 passphrase 派生 key，计算 commitment 并与 envelope 中的 `key_commitment` 比对。不匹配时 MUST 拒绝解密并提示用户 passphrase 错误。`key_commitment` 只是本地快速拒绝错误口令和防止密文替换的辅助值，不是服务端认证材料；服务端不得要求用户上传 passphrase、derived key、commitment key 或使用 `key_commitment` 做在线口令检查。**澄清（防误读）**：该禁令针对的是"服务端获得可离线验证口令的材料"；它**不禁止** aPAKE 形态的协议（如 OPAQUE，RFC 9807）——aPAKE 的设计不变量恰是服务端永不见口令也无法预计算字典，与本条约束相容。离线攻击者仍可对备份执行 KDF 级别的口令猜测，因此实现必须执行强口令策略、Argon2id 参数下限和速率受控的恢复 UI。

> **路线图注记（informative，2026-06 评审采纳）**：对低熵口令的已声明残余风险（离线无限猜测），已识别的增量缓解方向是 **OPAQUE（RFC 9807）/ HSM·TEE 限速恢复服务**（Signal SVR、WhatsApp HSM vault 形态）：把暴露面从"离线无限猜"压缩为"在线限速猜"，且服务端攻破不可预计算。引入形态为与 `passphrase_kdf` **并存**的新 recipient_method（schema 枚举加法，不替代离线兜底），recovery service 的 attestation 要求可复用既有 attestation-evidence 框架。本注记不预注册 method 名或 profile id；待实现计划成立时按加法引入。

域隔离 profile 的 conformance proof MUST 至少证明：不同 `backup_class` / subdomain 的 HKDF info 不同、AEAD AAD 覆盖域和 item type、key commitment 不能跨域复用、恢复流程不会把一个域的解锁成功当作另一个域的授权证明。

`ciphertext_digest` 覆盖密文字节，`plaintext_commitment` 若存在只用于本地完整性或跨设备一致性检查；服务端不得要求知道明文 hash 才能存储或返回备份。

### 7.3 恢复流程

恢复流程：

1. 新设备生成 device key。
2. 用户输入 Recovery Key（24 词助记词，§3.3），或按 recovery policy 收集 recovery shares / 完成硬件解锁；仅当目标是 `passphrase_kdf` envelope 时才输入对应口令（§7.5.1）。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `ck.device.authorize`。
6. 若涉及 E2EE Realm，客户端拉取 MLS state 并处理 epoch 缺口。

恢复 device key 时 MUST 生成新的 device key，不得把备份中的旧设备身份克隆到新设备。恢复出的 `self_signing_key` / `user_signing_key` 可用于重建 cross-signing 状态，但 Cross-Signing Reset 仍必须满足 `device-lifecycle.md` 的高风险证明要求。

### 7.4 所有权证明与解密证明

DID 控制权证明 SHOULD 优先使用签名挑战，而不是“能解开某段历史密文”：

- 当前控制密钥、已授权 device key 或 recovery key 对服务端 fresh challenge 签名。
- 新设备生成 device key 后，由当前有效设备或 recovery policy 签发 `ck.device.authorize`。
- recovery service 在 DID Document、organization policy 或 recovery policy 中被明确声明，并签发可验证 recovery event。

“能解密用某个公钥加密的数据”MAY 作为恢复流程中的一个密码学因子，但不得单独等同于账号所有权。允许的形式是：服务端生成短期随机 challenge，按当前 key-log / recovery policy 指定的 recovery public key 加密，客户端在本地解密后对 challenge transcript 签名或返回 proof。该流程 MUST 绑定：

- `challenge`
- `audience` / `origin`
- `service_did`
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

因此，解密能力最多是 recovery factor；真正改变 DID 控制状态必须落成 DID method history、key log、`recover`、`rotate`、`ck.device.authorize` 或等价 signed event。

#### 7.4.1 备份签名的设备信任根锚定（normative）

`auth_data.signature` 由上传设备的 device signing key 产生（`auth_data.verification_method` 指向该 device key）。仅设备签名只能证明“某个持有该 device key 的实体写了它”，无法独立抵御**恶意服务器联合一个被攻破 / 已撤销的旧 device key 注入或替换备份 envelope**。因此 receiver 在信任并使用一条 backup envelope（恢复或读取）前 MUST 把该签名锚定到 actor 当前 accepted 设备信任根：

- receiver MUST 验证 `auth_data.verification_method` 指向的 device key 属于该 actor 当前 accepted、未撤销的设备投影，并且该 device key 验证 `auth_data.signature` 覆盖的 canonical envelope；
- cross-signing 设备路径：envelope MUST 携带对签发该设备授权的 self-signing key 代际的绑定（`auth_data.ssk_generation`）。这里的 `ssk_generation` 与 `ck.device.authorize.payload.cross_signing_binding.ssk_generation`、`ck.cross_signing.publish.generation` 是同一 cross-signing 代际计数（reset 时 `generation += 1`），其权威定义与单调性规则见 [`../crypto-media/device-lifecycle.md` §5](../crypto-media/device-lifecycle.md)（cross-signing publish）与 [`§14`](../crypto-media/device-lifecycle.md)（cross-signing reset / generation 推进）。receiver MUST 拒绝代际早于当前 published generation 且超出 rotation grace window 的 envelope（`stale_backup_trust_generation`）；
- service-attested / enrollment-authority 设备路径（见 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md)）：envelope MUST 携带 `auth_data.device_authorize_event_id`，且该值 MUST 等于该 `auth_data.device_id` 当前 accepted 的 `ck.device.authorize` event id。receiver MUST 使用该设备投影中的 `payload.device_public_key` 验证 `auth_data.signature`；`auth_data.ssk_generation` 在此路径 MUST 缺失，因为 account authority 不持有、不得伪造本 principal 的 SSK；
- `auth_data.ssk_generation` 与 `auth_data.device_authorize_event_id` MUST 精确二选一。二者同时存在、同时缺失、设备未授权、设备已撤销、代际不符、授权事件不符或签名验不过的 envelope MUST 被视为 `untrusted_backup_signature`（代际过旧时可用 `stale_backup_trust_generation`）并拒绝用于恢复，即使其 series 链与 `ciphertext_digest` 自洽。
- **高敏 backup_class 的信任锚强制存在（normative）**：对 `backup_class ∈ {secret_storage, did_recovery}` 这两类高敏备份，receiver MUST fail closed，MUST NOT 退回到"device key 在 `created_at` 时点是否有效"的较弱判定接受它用于恢复或读取。即：core 档下 `secret_storage` / `did_recovery` envelope 必须携带上述两个合法信任锚之一，使恶意服务端联合旧 / 已撤销 device key 注入的高敏备份无法绕过信任根比对。`mls_history` 类也必须满足本节签名锚定；其 freshness / frontier 强化仍按各档 hardening profile 策略处置。

这样 envelope 的真实性锚定在 actor 当前设备信任根，而不是“碰巧持有某个 device key”，与 series 链（§7.6，防回滚 / 扣留）正交：前者保证 authenticity，后者保证 freshness / 单调性。

> **Schema 影响**：`ck.schema.key_backup.v1.auth_data.ssk_generation` 绑定 [`ck.cross_signing.publish`](../crypto-media/device-lifecycle.md) 的 `generation`（见 [`../crypto-media/device-lifecycle.md` §5](../crypto-media/device-lifecycle.md)）；`ck.schema.key_backup.v1.auth_data.device_authorize_event_id` 绑定 [`ck.device.authorize`](../crypto-media/device-lifecycle.md) 的 accepted event id（见 [`../crypto-media/device-lifecycle.md` §5.4](../crypto-media/device-lifecycle.md)）。二者 MUST 精确二选一；携带 `auth_data.x_ssk_generation` 或 `auth_data.x_device_authorize_event_id` 的 envelope MUST reject（`schema_violation`，登记于 `artifacts/migration/renames.json`）。

### 7.5 Recipient Method Profiles

`ck.schema.key_backup.v1.encryption.recipient_method` 枚举 3 种 envelope 解锁方式。每种方式 MUST 按下列 normative 约束实现；服务端遇到本节未定义的 `recipient_method` MUST fail closed。

#### 7.5.0 `backup_class` × `recipient_method` 合法组合矩阵（normative）

`backup_class`（仅 `did_recovery` / `secret_storage` / `mls_history` 三类，§7.1）与 `recipient_method` 的组合不是自由叉乘。下表是合法组合的**集中**声明；producer MUST NOT 写入标 `forbidden` 的组合，receiver / 服务端遇到 `forbidden` 组合或本表未列出的组合 MUST fail closed（reason 见各格），即作为兜底也不允许：

| `backup_class` ＼ `recipient_method` | `passphrase_kdf` | `recovery_public_key` | `secret_storage_key` |
| --- | --- | --- | --- |
| `did_recovery` | forbidden: `did_recovery_passphrase_forbidden` | allowed: MUST 带顶层 `recovery_policy_ref{policy_id, policy_version}` == 当前 accepted recovery policy，否则 `recovery_policy_mismatch` | forbidden: `did_recovery_secret_storage_key_forbidden`（DID recovery 不得依赖 device-local secret storage root） |
| `secret_storage` | allowed（见 §7.5.1）: §7.2 / §7.5.1 Argon2id 或显式 degraded PBKDF2；新创建 envelope 满足 §7.2 机器下限 | allowed（新写入 SHOULD 优先，见 §7.5.1） | allowed: 仅现有持有 root key 的设备本地缓存/同步，新设备 MUST NOT 直接 bootstrap，否则循环依赖 |
| `mls_history` | forbidden: `mls_history_passphrase_forbidden` | allowed | allowed: MAY 带 `recovery_policy_ref` hint；释放仍以 active-series record / frontier_ref / Realm-MLS 授权 / 设备状态为准 |

集中要点（与下列 §7.5.1–§7.5.5 的分散规则一致，本表为 normative summary）：

- **`passphrase_kdf` 仅 `secret_storage`**：`did_recovery` 与 `mls_history` MUST NOT 使用 `passphrase_kdf`，即便作为 fallback 也不允许（单一口令不得直接控制 DID recovery 或解锁 MLS 历史）。需要口令参与时，口令只能先解锁 `secret_storage` root、recovery private key、threshold share 或 hardware wrapper 的本地保护层，再由 `recovery_public_key` / `secret_storage_key` 完成对应 `backup_class` 的释放。
- **`did_recovery` 只能用 `recovery_public_key`**：`did_recovery` 的唯一合法 `recipient_method` 是 `recovery_public_key`。envelope 顶层 `recovery_policy_ref{policy_id, policy_version}` MUST 等于当前 accepted `ck.schema.recovery_policy.v1`，并进入 `auth_data.signed_fields`；不一致 MUST `recovery_policy_mismatch`（fail closed）。
  - **recovery 私钥释放强度（normative 澄清）**：本矩阵在 envelope 层禁止 `did_recovery` 用低熵口令派生（`passphrase_kdf` / `secret_storage_key`），确保 DID recovery 不被单一**低熵**口令直接控制。recovery **私钥本身**的释放强度由 §8 recovery policy 的 `allowed_proof_kinds` 决定：当 policy 仅配置单个 `recovery_unlock`（单把高熵 24 词助记词签名）时，恢复强度即等同于该单一高熵助记词——这是 v1 default profile **有意接受**的取舍（高熵单因子 ≠ 低熵口令）。高价值 / 组织账号 SHOULD 按 §7.11（"高价值账号 SHOULD 支持门限恢复"）对 `did_recovery` 释放叠加门限（`threshold_recovery`）或多 `proof_kind`，不依赖单一可窃取秘密。
- **`secret_storage_key` 不可 bootstrap**：新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap，必须先用 `passphrase_kdf` 或经 recovery policy 释放的 `recovery_public_key` 解出 root secret storage key（消除"新设备能解 wire envelope"的循环依赖）。
- **门限/硬件属于 recovery policy 层**：threshold、hardware module、trusted recovery service 可以保护 recovery private key 或 secret storage root 的释放，但不得作为 `ck.schema.key_backup.v1.encryption.recipient_method`。相关 proof transcript 由 §8 recovery policy 与 `ck.schema.recovery_session.v1` 约束。
- 所有 fail-closed 判定 MUST 在解密尝试之前完成；服务端 / receiver 不得对 `forbidden` 组合"先解密再检查"。

#### 7.5.1 `passphrase_kdf`

参考 §7.2：Argon2id（或显式 degraded PBKDF2）派生 root key，HKDF 派生 `commitment_key` 与 `nonce_key`，AEAD AAD 覆盖全部 envelope metadata。`passphrase_kdf` 仅用于 `secret_storage` envelope；`mls_history` 与 `did_recovery` envelope MUST NOT 使用 `passphrase_kdf`，即使作为 fallback 也不允许。需要用户口令参与 DID recovery 或 MLS 历史恢复的实现 MUST 让口令先解锁 `secret_storage` root、recovery key、threshold share 或 hardware wrapper 的本地保护层，而不是在 wire 上发布 `backup_class="mls_history"` / `backup_class="did_recovery", recipient_method="passphrase_kdf"` 的 envelope。

**与 Recovery Key 的关系（normative）**：内容恢复的标准用户凭证是 Recovery Key（§3.3 / §7.7）；实现 SHOULD NOT 引入独立 vault 口令作为密钥备份的面向用户凭证。

- 新写入的 `secret_storage` envelope SHOULD 使用 `recipient_method="recovery_public_key"`（加密给 recovery key，§7.5.2）；`passphrase_kdf` envelope MAY 用于实现自选的口令派生场景。
- `passphrase_kdf` 是合法 wire `recipient_method`：服务端 key-backup 端点（§7.8、[`../crypto-media/device-lifecycle.md` §12.1](../crypto-media/device-lifecycle.md)）不区分凭证来源，`passphrase_kdf` envelope MUST 可被列出、读取与删除，本节与 §7.2 的 KDF / nonce / commitment 约束对其适用。

#### 7.5.2 `recovery_public_key`

DEK 通过 HPKE（base mode）加密给 `recovery_public_key`：

- `recipient_key_ref` MUST 是当前 accepted recovery policy（§8）中声明的 verification_method，或当前 DID Document 中声明的 `recoveryKeyAgreement`。
- HPKE suite MUST 是 [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 中的 active 行，由 `encryption.hpke_suite` 选定；该字段缺省时 MUST 解释为 default-MUST 行 `ck.hpke_x25519_aead_xchacha20poly1305.v1`。`aead.name` MUST 等于所选 suite 的 AEAD。遇到未登记、非 active 或 reserved-未激活的 suite id，receiver MUST fail closed（`unsupported_hpke_suite`），MUST NOT 自由组合未登记的 KEM/KDF/AEAD，也 MUST NOT 仅凭 `aead.name` 推断 suite 参数。P-256 KEM 互操作经 profile-gated 行 `ck.hpke_p256_aead_aes256gcm.v1`（`ck.profile.hpke.p256.v1`）提供。HPKE 单发 base-mode 由 key schedule 内部派生 AEAD nonce，故 `recovery_public_key` envelope 不携带 wire `nonce`。
- HPKE `info` MUST 包含 `canonical_json({backup_id, series_id, series_seq, actor_id, backup_class, backup_version, created_at})`；HPKE `aad` MUST 等于 envelope 的 AEAD AAD。
- 受 DID 轮换影响：recovery key 轮换后产生的新 envelope MUST 引用新 verification_method；旧 envelope 在轮换 grace window 之后 receiver MUST 拒绝用旧 key 完成的解锁证明。
- 当 `backup_class="did_recovery"` 时，envelope 顶层 `recovery_policy_ref{policy_id, policy_version}` MUST 等于当前 accepted recovery policy；`recipient_key_ref` 必须解析到该 policy 或当前 DID Document recovery key agreement 声明中的接收 key。不匹配 MUST `recovery_policy_mismatch`。其它 `backup_class` 使用 `recovery_public_key` 时，`recovery_policy_ref` 只是可签名 hint；若出现，receiver MUST 验证它与当前 accepted recovery policy 一致，但不得把它作为 MLS 历史或 secret storage 授权的替代。
- **备份接收密钥即恢复密钥（normative）**：v1 MUST NOT 引入独立于 recovery key 之外的"专用 backup keypair"。`recovery_public_key` 的 HPKE 接收方就是 recovery policy / DID Document 声明的 recovery 公钥；其私钥经 §8 recovery policy 解锁（passphrase / threshold / hardware）。实现 MUST NOT 假定存在一个单独存储在 `secret_storage` 中的 backup 私钥项；跨设备的 fresh-device 恢复统一通过解锁 recovery 私钥后 HPKE-open 完成。

#### 7.5.3 `secret_storage_key`

仅用于已经持有 `secret_storage` root key 的现有设备本地缓存/同步（不是 bootstrap）。

- `recipient_key_ref` MUST 命名一个已经在该设备 device-local secret storage（参见 `crypto-media/device-lifecycle.md` §11 `ck.secret_storage.v1`）中存在的 key id（例如 `mls_group_secrets_backup_key`）。
- 当 `backup_class="mls_history"` 使用 `secret_storage_key` 时，envelope MAY 携带顶层 `recovery_policy_ref{policy_id, policy_version}` 作为恢复流程 hint；若出现，`auth_data.signed_fields` MUST 覆盖它，receiver MUST 验证它与当前 accepted recovery policy 一致。MLS 历史材料的释放仍以 active-series record、frontier_ref、Realm/MLS 授权与设备状态校验为准。
- 新设备 MUST NOT 通过 `secret_storage_key` envelope 直接 bootstrap：新设备必须先经由 `passphrase_kdf`，或先经 recovery policy 释放 recovery private key 后通过 `recovery_public_key` 解出 root `secret_storage` key，然后才能拉取 `secret_storage_key` envelope。
- 这是为了消除"新设备能解 wire envelope"的循环依赖。
- **AEAD nonce 唯一性（normative）**：`secret_storage_key` 是长期复用的对称 wrap key，因此 `aead.nonce` MUST 在该 `recipient_key_ref` key 的整个生命周期内对每条 envelope 唯一——producer MUST 为每条新 envelope 生成至少 96-bit 的随机 nonce（或在该 key 下严格单调不回绕的 counter），且 MUST NOT 用同一 (`recipient_key_ref` key, `aead.nonce`) 对写第二条 envelope；需要更新内容时 MUST 生成新 `backup_id` 与新 `nonce`，并 SHOULD 轮换底层 wrap key。`nonce` 进入 `auth_data.signed_fields` 覆盖的 AEAD AAD（§7.4）。该约束与 `passphrase_kdf` 的 `nonce_salt` deterministic derivation（§7.5.1）、`recovery_public_key` 的 HPKE 内部 nonce 派生共同关闭三种 `recipient_method` 的 nonce-reuse 面。

#### 7.5.4 门限恢复作为 recovery policy 层

v1 core 不把 `threshold_recovery` 作为 `ck.schema.key_backup.v1.encryption.recipient_method`。门限恢复用于按 §8 recovery policy 释放 recovery private key 或 secret storage root；释放成功后，客户端再用 `recovery_public_key` 或 `secret_storage_key` 解开对应 backup envelope。这样可以把门限交互、share holder 审计和 envelope 加密算法分层，避免把门限协议细节塞进每个备份对象。

- 每份 share 的取回 MUST 绑定当前 recovery 流程的 `recovery_session_id`（见 [`../crypto-media/device-lifecycle.md` §15](../crypto-media/device-lifecycle.md)）；holder 服务 MUST NOT 把同一 share 多次释放给不同 session 而不经显式授权。
- reconstruction 完成的 recovery private key / root key MUST NOT 写入持久化存储；reconstruction 上下文 MUST 在解密 envelope 后立即销毁。
- share commitment 校验：reconstruction 前 client / recovery coordinator MUST 验证每份 share 与 `recovery_policy.threshold.shares[].share_commitment` 一致；失败时 MUST `share_commitment_mismatch` 并通知用户特定 holder 提交了 invalid share。

#### 7.5.5 硬件包装作为 recovery policy 层

v1 core 不把 `hardware_wrapped_key` 作为 `ck.schema.key_backup.v1.encryption.recipient_method`。硬件模块、HSM、TPM 或 Secure Enclave 只能作为 recovery policy 中的 unlock factor：它们释放 recovery private key、threshold share 或 secret storage root 的本地保护层，然后客户端仍用 `recovery_public_key` / `secret_storage_key` 解开 backup envelope。

- recovery policy MUST 记录被信任的 hardware / service profile、wrap key 稳定标识与 attestation 要求；proof transcript MUST 绑定 `recovery_session_id` 与当前 challenge。
- receiver MUST 验证当前的 hardware attestation evidence 仍声明同一 key id（即设备未在静默状态下被替换），并且该 profile 属于当前 accepted recovery policy。
- 任何 envelope 单纯展示 `recipient_method=hardware_wrapped_key` MUST 被 schema/receiver 拒绝为未知枚举值；缺少 attestation chain 的 recovery proof MUST `attestation_missing`。

### 7.6 Backup Series & Freshness

服务端是不可信存储；攻击者控制服务端时，可以静默返回**旧**版本 envelope 让恢复设备解出已经 retired 的密钥。`ck.schema.key_backup.v1` 通过 `series_id` / `series_seq` / `supersedes` / `supersedes_digest` / `frontier_ref` 链堵塞这一点。

要求：

- `series_id` 是 `ck:backup_series:<uuid>` typed-id。每个 `series_id` MUST 只属于一个 `(actor_id, backup_class)`，但同一 `(actor_id, backup_class)` MAY 在密钥泄露轮换或迁移过渡期拥有多个 series。常规状态下只能有一个 active series；当前 active series MUST 由下方 `ck.schema.key_backup_active_series.v1` signed active-series record 选择，不得由服务端返回顺序推断。
- 新 envelope MUST 满足 `series_seq == prev.series_seq + 1`；`supersedes` MUST 是同 `series_id` 中上一条 envelope 的 `backup_id`，且 `supersedes_digest` MUST 等于上一条 envelope 排除 `auth_data.signature` 后 canonical_json 的哈希。
- genesis envelope MUST `series_seq == 0`，且 MUST NOT 携带 `supersedes` 或 `supersedes_digest`。
- `auth_data.signed_fields` MUST 覆盖 `series_id` / `series_seq`；非 genesis envelope 还 MUST 覆盖 `supersedes` 与 `supersedes_digest`，携带 `frontier_ref` 时还 MUST 覆盖 `frontier_ref`（schema 已在 `signed_fields.allOf.contains` / 条件分支中强制）；服务端 MUST NOT 替换这些字段。
- `frontier_ref` 是 RECOMMENDED 字段；当声明 `ck.profile.key_backup.memory_hard.v1` 或更高 hardening profile 时，`secret_storage` 与 `did_recovery` 类备份的新 envelope MUST 携带 `frontier_ref.frontier_digest`，并 SHOULD 携带 `frontier_ref.seal_ref` 与 `frontier_ref.ssk_generation`。
- **`mls_history` 释放的 frontier 校验为 MUST（normative，非 `personal_node` profile）**：除 `personal_node` profile 外，`mls_history` 类备份的释放（恢复设备解出 MLS 历史材料）MUST 校验 active-series record（§7.6 `ck.schema.key_backup_active_series.v1`）并验证 envelope 的 `frontier_ref`（`frontier_digest`，可达时连同 `seal_ref` / `ssk_generation`）与当前 accepted control-stream frontier 一致；缺失 active-series record 或 frontier 校验不通过时 MUST fail closed，不得释放。否则服务端可静默回放旧 series，让恢复设备解出已 retired 的 MLS 历史密钥（正是本节要堵塞的回滚释放攻击）。该 MUST 取代上方矩阵 `mls_history × secret_storage_key` 单元格"释放仍以…为准"散文表述中可被读成可选的部分。
- **Active-series record**：当某 `(actor_id, backup_class)` 存在多个 series，或实现需要向新设备声明 canonical series 时，principal control stream MUST 发布 event kind `ck.key_backup.active_series`，payload MUST validate as `ck.schema.key_backup_active_series.v1`。该 record MUST 至少绑定 `schema`、`actor_id`、`backup_class`、`active_series_id`、`issued_at`、`previous_series_ids[]`、`frontier_ref{frontier_digest, seal_ref?, ssk_generation}` 与签名 `auth_data`；`auth_data.signed_fields` MUST 覆盖这些字段，`auth_data.ssk_generation` MUST 等于当前 accepted self-signing generation。`active_series_id` MUST 指向同 `(actor_id, backup_class)` 下的 genesis 或 successor series；`previous_series_ids[]` 只用于 retention / read-old-data 过渡，不得作为 primary recovery source。Receiver MUST 先验证该 record 链接到当前 principal control stream 与当前 accepted self-signing generation，再使用其 `active_series_id` 拉取备份链。Envelope 自身的 `frontier_ref` 只证明该 envelope 创建时的 control-stream 位置，不能替代 active-series record。
- 客户端发起恢复（device-lifecycle.md §15）时 MUST：
  1. 若恢复方未持有已验证的 `series_id`，先从 principal control stream 解析并验证 active-series record，取得 `active_series_id`；然后 `LIST /_cokret/self/keys/backups?series_id=<active_series_id>` 取回**全部** envelope metadata；
  2. 按 `series_seq` 重建链，验证每条 `supersedes` / `supersedes_digest` 正确；任一 envelope 缺失或 hash 不匹配 → MUST `series_chain_broken`；
  3. 用链的**最尾**条进行解密；任何中间条目 MUST NOT 被用作主恢复源；
  4. 当存在 `frontier_ref` 时 MUST 用 control stream snapshot 验证 frontier_digest 落入当前 principal control stream，且 `ssk_generation` 不低于当前 accepted generation；否则 MUST `backup_frontier_stale`。
- 服务端 MUST 把同一 series 内的删除视为高风险动作（参见 `crypto-media/device-lifecycle.md` §12.1）：active series 内的非尾部 envelope MUST NOT 被单独删除；删除尾部 envelope 等同于让 series 失效，MUST 在 audit 中可见。旧 series 只能按 retention / erasure 规则整组迁移或整组删除，不能留下断链作为可恢复来源。

### 7.7 Recovery UI Requirements（normative）

恢复 UI 是用户唯一能识别"我在恢复一个真实的自己 vs 我在被钓鱼"的界面。实现 MUST：

- 密钥备份解密凭证 MUST 是 Recovery Key（24 词 BIP-39 助记词，§3.3）：由其派生 / 解锁 recovery private key 后按 §7.5.2 HPKE-open `recovery_public_key` envelope，或按 recovery policy（§8）以 threshold / hardware 因子释放同一 recovery private key。恢复 UI MUST NOT 要求用户设置独立 vault passphrase 作为标准凭证；仅当目标 envelope 是 `passphrase_kdf`（§7.5.1）时，MAY 提示输入对应口令完成解密，并 SHOULD 在恢复成功后引导写入加密给 recovery key 的新 envelope（§7.5.2，按 §7.6 series 规则开新链或追加）。
- 在尝试解密任何备份 envelope 之前，向用户展示：`backup_class`、`series_id`、`series_seq`、`backup_version`、`encryption.recipient_method`、`encryption.aead.aead_profile?`（缺省时显示 `aead.name`）、`principal_id`、`device_id`（当前请求恢复的新设备）、`frontier_ref.ssk_generation?`。
- 在使用 `passphrase_kdf` 时，明确展示 KDF（Argon2id / PBKDF2）与参数；用 PBKDF2 的 envelope MUST 在 UI 中显示 `degraded_profile_reason`，且不得自动选用 PBKDF2 envelope 当 Argon2id envelope 同时存在。
- 在 envelope 携带 `mixed_secret_storage=true` 时 MUST 显著警告"该备份同时保护身份签名与 E2EE 历史，单一口令被攻破将同时丢失两者"；非 `personal_node` profile 下 MUST 直接拒绝展示此类 envelope 作为 primary recovery source。
- 在 `did_recovery` 域使用 `passphrase_kdf` 单独路径时 MUST 拒绝继续（参见 §7.5.1）。
- 对 `did_recovery` envelope，展示当前 envelope 的 `recovery_policy_ref.policy_id` / `policy_version` 与当前 accepted recovery policy 的一致性；其它 envelope 携带 `recovery_policy_ref` 时也 MUST 展示并验证。不一致时 MUST `recovery_policy_mismatch`，并指向"更新 recovery policy"流程而不是默默继续。
- 不得从本地缓存读取用户先前确认的 fingerprint / passphrase / OOB token 跳过当次显式确认。本地缓存 MAY 用于自动补全，但用户 MUST 显式提交本次输入。
- 在 §7.4 列出的禁用证明类型（历史明文、邮箱验证码、撤销设备等）被用户尝试时 MUST 给出可读的拒绝原因。
- **无恢复路径（SPOF）账号的 fresh-device 登录警示**：当新设备登录的目标 principal 的 `active_policy=null`（无 accepted recovery policy）时，fresh-device DID recovery 与 `did_recovery` backup unlock MUST fail closed（§8）。此时 UI MUST 在进入任何恢复尝试之前明示"该账号没有已配置的恢复路径，唯一的换机方式是在一台已授权的旧设备上确认"，并把入口优先导向同 principal 旧设备确认流程（[`../crypto-media/device-lifecycle.md` §10](../crypto-media/device-lifecycle.md)）；不得让用户在无恢复材料的前提下反复尝试 recovery proof。

### 7.7.1 Backup Unlock Proof 与 Plaintext Keybag（normative）

每次读取并尝试解密 key backup 都 MUST 产出一条 unlock proof，明文 keybag 也 MUST 有固定 schema，避免“能下载密文”被误当作“有权使用解密结果”：

- backup decrypt proof payload MUST validate as `ck.schema.key_backup_unlock_proof.v1`，并绑定 `recovery_session_id`、`principal_id`、`requesting_device_id`、`backup_id`、`backup_class`、`series_id`、`ciphertext_digest`、`proof_kind`、`proof_digest` 与 `issued_at`。`proof_digest` 是已接受 recovery proof transcript 的 digest；receiver MUST 用当前 session state 重建 transcript 后比对，不得采信客户端自报的 policy/session metadata。
- 取回完整 ciphertext 的协议操作是 `ck.self.keys.backups.command.unlock`（`POST /_cokret/self/keys/backups/{backup_id}/unlock`）：unlock proof MUST 作为 request body 的 `proof` 字段提交（`keys-operations.schema.json#/$defs/keys_backups_unlock_request_body`），path `backup_id` 与 `proof.backup_id` MUST 一致；实现 MUST NOT 用 header、query string 或私有载体承载该 proof。服务端在返回完整 ciphertext 之前，MUST 校验该 unlock proof 与请求 session、caller、新设备 key、active-series record 和目标 envelope 一致；任一不符 MUST fail closed（`recovery_evidence_unbound` / `backup_frontier_stale` / `series_chain_broken` / `invalid_signature`）。
- AEAD/HPKE open 后得到的明文 MUST validate as `ck.schema.key_backup_plaintext.v1`，且其中 `backup_id`、`backup_class`、`series_id`、`series_seq` MUST byte-for-byte 等于外层 envelope。`items[].secret_id` / `item_type` 是 keybag 内部路由字段，不得替代外层 envelope 的授权判断。
- 实现 MUST 把 plaintext keybag 限定为本地瞬时处理材料；除非它被重新加密进本地 secret storage，否则不得持久化明文。日志、crash dump、telemetry MUST NOT 记录 `secret_b64u`。

### 7.8 Server-Side Hardening for Backup Access

加密备份的密文虽然不暴露明文，但下载即"投喂 KDF 爆破弹药"。Device / Key Server MUST 对 `ck.keys.backups.*` 接口实施：

- **每 principal 每 24h 下载上限**：默认 `daily_principal_download_limit = 64`（覆盖单一 series 下大量历史 epoch 备份的合理使用，又能拦截批量 dump）。`ck.profile.key_backup.memory_hard.v1` 实现 MUST 公布所采用的实际上限，并接受 deployment 配置在 `[16, 256]` 范围内调整。
- **每 IP / 每 session 限速**：默认 `per_ip_unlock_burst = 8`，`per_ip_unlock_sustained_per_minute = 4`；逾限响应 MUST 是 `429 Too Many Requests`，并 SHOULD 在 `Retry-After` 中给出建议。
- **认证降级阻断**：`POST /_cokret/self/keys/backups/{backup_id}/unlock` 即便对自己的备份也 MUST 要求 fresh device proof（与 §7.4 fresh challenge 相同绑定：challenge / audience / service_did / principal_id / key_id / nonce / 过期时间）。bearer token 单独到达 MUST 被拒绝。
- **审计记录**：超出阈值或在异常时间窗内的下载 MUST 写入 `ck.audit.accessed`，`access_kind="key_backup_read"`，并按 `ck.profile.attested_audit.e2ee.v1`（若声明）配对 audit pair。
- **跨 actor 拒绝**：服务端 MUST 在 envelope `actor_id` 与请求 caller 不一致时返回 `forbidden`，并不得通过 metadata 暴露 envelope 是否存在。
- **删除验证**：active series 内的非尾部 envelope MUST NOT 被单独删除。`DELETE` 尾部 envelope MUST 额外要求 `crypto-media/device-lifecycle.md` §15 风格的 high-risk proof（principal_signing / device_quorum / trusted_recovery_service）并写入 `access_kind="key_backup_delete"` 审计。仅持普通 device proof 的 caller 只能删除 `expired_at < now` 且不属于 active series 的旧 envelope，或对已被 active-series record 移出 primary source 的旧 series 发起整组 erasure/retention 删除。

实现 MAY 在 deployment policy 中收紧上述阈值；MUST NOT 放宽超过本节默认。

### 7.9 Algorithm Agility & Forward Compatibility

v1 的备份枚举数量有限，但 envelope 结构需要支持未来 PQ / hybrid 迁移：

- Receiver MUST 对未知 `encryption.kdf.name`、`encryption.aead.name`、`encryption.aead.aead_profile`、`encryption.recipient_method` fail closed（不得回退到默认）。
- PQ / hybrid KEM agility MUST 通过 `encryption.hpke_suite` 选择子 + [`hpke-suite-registry.json`](../../artifacts/registry/hpke-suite-registry.json) 声明，不得塞进 AEAD profile。PQ hybrid（X25519+ML-KEM-768）已在该 registry 预留 `ck.hpke_xwing_aead_xchacha20poly1305.v1`（status=reserved，profile `ck.profile.kem.hybrid_xwing.v1`），与 `ck.aead.hybrid_kem.*` 预留 namespace 对齐；只有该 registry row 的 activation requirements 全部满足并翻为 active 后才可出现在 wire 上。`ck.aead.*` 只描述 AEAD 算法、nonce/tag/key 长度和 AAD 构造；receiver 收到把 KEM 语义编码进 `encryption.aead.aead_profile` 的 envelope MUST fail closed。
- 当 `frontier_ref` 携带 `seal_ref` 时，client 可以用 Seal inclusion proof 来证明 envelope 创建时刻不晚于 Seal commit；receiver MAY 在 sovereign / high_security_organization profile 中要求该证明。
- 实现 MUST 在 envelope metadata 中保留 `additionalProperties` 与 `x_*` 前缀作为 forward-compat 扩展槽；MUST NOT 在 wire 上接受未知顶层字段（已由 schema `additionalProperties: false` 强制）。

### 7.10 自动持续备份

Recovery Key 配置完成（genesis recovery policy accepted 且 §5.0.1 first-backup gate 通过）后，客户端 SHOULD 自动、持续地维护密钥备份，而不是把备份当作一次性手动动作：

- account secret（`self_signing_key` / `user_signing_key`、recovery secret、`account_data_namespace_key` 等 `secret_storage` 域材料）、历史密钥材料（MLS group state / epoch key material 等 `mls_history` 域材料）与 encrypted private account data cache 发生新增或轮换时，客户端 SHOULD 自动上传对应 `ck.schema.key_backup.v1` envelope，遵守 §7.6 series 链规则。
- 自动备份 SHOULD NOT 要求用户手动触发或重复输入凭证；envelope 加密给 recovery public key（§7.5.2）只使用公钥，不需要用户在场。客户端 MAY 额外提供手动"立即备份"入口。
- 自动备份失败（网络、§7.8 限速、series 冲突）时，客户端 SHOULD 退避重试，并在持续失败超过实现定义的窗口时向用户显式提示备份落后；SHOULD NOT 静默丢弃待备份材料。
- 本节不放宽 §7.1 的禁止项：device private key、session key、已发布的 KeyPackage private key 等仍 MUST NOT 进入自动备份。
- **首份 `secret_storage` 备份的及时性**：first-backup gate（§5.0.1 step 7）只强制 `did_recovery` 域 `series_seq=0`；SSK / USK 在 `ck.cross_signing.publish` 之后才产生。客户端 SHOULD 在首次 `ck.cross_signing.publish` accepted 后**立即**发布承载 SSK（及 USK）的首份 `secret_storage` envelope（`recipient_method="recovery_public_key"`，进入 §7.6 series 链），并把它纳入 onboarding 完成判据。否则在 gate 通过、首份 `secret_storage` 落地之前的窗口内丢失唯一设备，用户即便持有 24 词也只能恢复 DID 控制链，cross-signing 树丢失而被迫走 [`../crypto-media/device-lifecycle.md` §14](../crypto-media/device-lifecycle.md) reset（全网 `needs_reverification` 扩散）。

### 7.11 加密 Realm 创建 / 加入前的 Recovery 前置门（normative）

E2EE Realm（effective `content_encryption_floor` 或 `metadata_encryption_floor` 为 `e2ee_required`，含 PCR 与任何加密协作 Realm）的创建或加入会产生该用户独有的 MLS group secret；若此时账号尚无可用恢复路径，丢失唯一设备即永久丢失这些内容。因此：

- 客户端在 `recovery_state` **未配置**（`GET /_cokret/root/identity/recovery-policy` 返回 `active_policy=null`，且无 §5.0.1 step 7 的 offline-sealed receipt）的账号上，发起创建或加入 effective floor 为 `e2ee_required` 的 Realm 之前，MUST 先提示用户完成 Recovery Key 设置与首份备份（§7.10 首份 `secret_storage` envelope）。
- `ck.profile.personal_node.v1` MAY 允许用户在明确告知"丢失本设备将永久丢失该 Realm 内容"后**显式跳过**，并维持 / 标记 `single_point_of_failure=true`、持续提醒；`small_team` 及以上 deployment profile SHOULD 阻断创建 / 加入，直至 recovery policy 配置完成。
- 该前置门是客户端编排义务，不替代服务端的 floor ratchet 与 PCR 校验；它针对的是"加密材料先于恢复路径产生"的时间窗，而非加密本身是否启用。

高价值账号 SHOULD 支持门限恢复。Recovery policy 的规范形态由 `ck.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）固定；本节内联 JSON 仅作示意，wire 实现 MUST 以 schema 为准。

Recovery policy 的标准发布面是 `POST /_cokret/root/identity/recovery-policy`（operation `ck.root.identity.recovery_policy.command.publish`，请求体为 `ck.schema.recovery_policy.v1`，响应 `recovery-policy.schema.json#/$defs/recovery_policy_publish_outcome`）；标准读取面是 `GET /_cokret/root/identity/recovery-policy`（operation `ck.root.identity.recovery_policy.resource.get`，响应 `recovery-policy.schema.json#/$defs/recovery_policy_active_outcome`）。服务端在接受 publish / rotate 前 MUST 校验 `auth_data.signed_fields`、签名权限、`version` 单调递增和 `supersedes` 链接。客户端在校验 `recovery_policy_ref`、创建 `ck.schema.recovery_session.v1`、或向用户展示恢复策略之前，MUST 通过 GET 端点读取当前服务观察到的 active policy，或从本地已验证的 principal control stream 重放到同一 frontier 得到等价结果。新设备尚未持有 control stream 时 MUST 使用该端点；`active_policy=null` 表示当前没有 accepted recovery policy，fresh-device DID recovery 与 `did_recovery` backup unlock MUST fail closed。客户端向 `recovery_session.create` 发送 `expected_recovery_policy_ref` 时 SHOULD 使用该读取结果中的 `active_policy.policy_id` 与 `active_policy.version`，服务端发现不同步 MUST 返回 `recovery_policy_mismatch`。

```json
{
  "schema": "ck.schema.recovery_policy.v1",
  "policy_id": "ck:policy:01964140-0000-7000-8000-000000000000",
  "principal_id": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "version": 1,
  "supersedes": null,
  "trust_domain": "ck:trust_domain:did.webvh.example",
  "allowed_proof_kinds": ["threshold_recovery", "device_quorum"],
  "threshold": {
    "k": 3,
    "n": 5,
    "shares": [
      {
        "share_id": "s1",
        "holder": "did:webvh:zFUHaR4UpA8gSoyk7J4AgYBHa:alice-friend.example",
        "transport": "hpke_x25519",
        "share_commitment": {
          "algorithm": "feldman-vss-sha256",
          "commitment_b64u": "base64url..."
        },
        "not_before": "2026-04-26T00:00:00Z",
        "expires_at": null,
        "revoked_at": null
      }
    ],
    "reshare_policy": {
      "max_share_age_seconds": 7776000,
      "scheme": "proactive_vss"
    }
  },
  "device_quorum": {
    "k": 2,
    "members": [
      "ck:device:01964137-0000-7000-8000-000000000000",
      "ck:device:01964138-0000-7000-8000-000000000000"
    ]
  },
  "approval_requirement": {
    "min_approvals": 1,
    "cooldown_seconds": 3600,
    "announcement_required": true
  },
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "issued_at": "2026-04-26T00:00:00Z",
  "auth_data": {
    "verification_method": "did:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#ck_principal_signing_v1",
    "signature_algorithm": "Ed25519",
    "signature": "base64url...",
    "signed_fields": [
      "schema",
      "policy_id", "principal_id", "version", "trust_domain",
      "supersedes", "allowed_proof_kinds", "threshold", "device_quorum",
      "approval_requirement", "not_before", "expires_at", "issued_at"
    ]
  }
}
```

恢复 share holder 只能帮助恢复控制权，不自动获得读取内容或代表主体操作的 capability。Recovery policy MUST 为每个门限 share 记录 `share_commitment{algorithm, commitment_b64u}`（如 Feldman VSS commitment 或 share hash commitment）；恢复时客户端 / recovery coordinator MUST 校验提交的 share 与 commitment 一致，避免 holder 或中间服务替换 share 后仍通过 policy 语法检查。

### 8.1 Policy 生命周期

Recovery policy 是 principal control state；它的发布、轮换、撤销 MUST 通过当前 accepted principal signing key（或满足旧 policy 的 quorum）签名进入 principal control stream：

- **publish**：首次发布或后续无中断更新。新 envelope 的 `version` MUST 严格大于当前 accepted policy 的 `version`，`supersedes` MUST 引用前一份 `policy_id`（首版为 `null`）。
- **rotate**：用于 `reshare_policy` 触发的 proactive secret sharing 或更换 holder 集合；rotate envelope MUST 在 `signed_fields` 中覆盖 `threshold` 与 `device_quorum`，并 SHOULD 同时附带新 share commitment。轮换期内的 in-flight recovery session（参见 `crypto-media/device-lifecycle.md` §15）MUST 使用其 `issued_at` 时点的 policy；服务端 / coordinator MUST 拒绝跨 policy 版本拼接 share。
- **revoke share**：当某个 share holder 被怀疑泄露时，policy holder 可发布只更新 `threshold.shares[i].revoked_at` 与 `revocation_reason_code` 的 rotate envelope。recovery coordinator MUST 拒绝任何 `revoked_at != null` 的 share，即便 commitment 仍能通过。`reshare_policy.max_share_age_seconds` 到期后未 reshare 的 share 在 coordinator 侧 MUST 被视为 stale，UI MUST 提醒用户。
- **revoke policy**：用 `expires_at = now`、`allowed_proof_kinds = []`、或专门的 `policy_id` revoke 进入 principal control stream；revoke 之后只有写入新 policy 才能恢复账号——这是高代价动作，必须配 §7.7 UI 警告。

任何允许的恢复方式（principal_signing / device_quorum / trusted_recovery_service / threshold_recovery / recovery_unlock）的 proof transcript MUST 绑定 `(policy_id, version, recovery_session_id)`；不绑定的 proof MUST `recovery_evidence_unbound`。Device recovery 场景中的 `principal_signing` proof 还 MUST 使用 `crypto-media/device-lifecycle.md` §15 定义的 canonical transcript,其字段集同时绑定 `principal_id`、`requesting_device_id`、`trust_domain`、`ssk_generation`、session `challenge`、session `created_at` 与 `expires_at`。

### 8.2 Holder 取回与防滥用

share holder（无论是个人 DID、托管服务 DID，还是 hardware module）在向恢复请求方释放 share 时 MUST：

- 验证 `recovery_session_id` 来源——session id MUST 来自当前 accepted recovery policy 中的 announcement event 或 trusted_recovery_service 签发的 challenge；不得接受任何 client 直接构造的 session id。
- 在签发 share release 之前 MUST 验证 holder 自己未被 §8.1 revoke，且当前时间在该 share 的 `not_before` / `expires_at` 范围内。
- share release 的请求方绑定按 `proof_kind` 分流：
  - `device_quorum`：请求方设备的 device key MUST 已绑定到目标 principal control stream 中某个尚未 revoke 的 device record；不满足则拒绝 release。
  - `threshold_recovery` / `recovery_unlock`：请求方设备 MAY 是尚未授权的新设备。holder MUST 验证 `recovery_session_id`、当前 policy/version、requesting device key proof-of-possession、session challenge、`requesting_device_id` 与 share request transcript 一致，并按 policy 要求完成 holder 侧 OOB / announcement / approval 检查；MUST NOT 要求该新设备预先存在于 control stream。恢复完成后的 `ck.device.authorize` 仍必须按 `crypto-media/device-lifecycle.md` §15 由恢复出的 SSK 或被 policy 授权路径签发。
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

如果 principal signing key 泄露但 recovery key 安全，MUST 通过 recovery policy 重建当前控制密钥。  
如果 recovery key 也泄露，SHOULD deactivate 原 DID 并执行身份重建。

### 9.1 备份子系统泄露的组合恢复流程（normative）

设备/身份泄露的步骤(上)与备份子系统的轮换/删除/PCS 之前是分散定义的。当怀疑**备份接收密钥（recovery key / `mls_group_secrets_backup_key`）或某个 backup envelope 的解锁材料泄露**时，实现 MUST 把以下三件事作为**一个组合流程**执行，而不是各自孤立：

1. **轮换 backup series**：按 §7.6 为受影响 `backup_class` 开启**新 `series_id`**（不是在旧 series 上追加），用轮换后的接收密钥重新加密当前需要保留的内容并上传新 series。新设备发现 canonical series 的方式见下方“active series 指针”。
2. **推进受影响 MLS 群组 epoch（PCS）**：轮换备份密钥本身**不**提供 post-compromise security——它只更换“备份包装”。要使后续消息密钥与被泄状态解耦，MUST 对受影响 Realm 触发 MLS Remove / Update 推进 epoch（与 §9 step 3 同一动作），并按 `crypto-media/encryption-and-audit.md` 绑定 governance frontier。
3. **删除旧 series**：在新 series 确认可恢复**之后**，按 `crypto-media/device-lifecycle.md` §12.2 retention 流程删除旧 `series` 的服务端密文。删除 MUST 在确认新备份可用之后进行，且 MUST 整组迁移而非删除链中间节点。

**不可挽回边界（MUST 在 UI 明示）**：上述流程只缩小**后续**暴露面；攻击者在泄露窗口内**已经下载**的旧密文用旧密钥永远可解，轮换/删除无法撤销。

**Active series 指针**：当一个 `(actor_id, backup_class)` 存在多个 `series_id`（轮换后新旧并存的过渡期）时，恢复方 MUST 通过 §7.6 的 signed active-series record 确定当前 canonical series。`frontier_ref` 是 envelope / record 的 control-stream 锚，不是 series 选择器；服务端返回顺序、最大 `series_seq`、最新 `created_at` 或单个 envelope 的 `frontier_ref` 都不能单独决定 active series。旧 series 仅在 retention 删除前用于读取既有内容，MUST NOT 作为 primary recovery source。

## 10. 实现要求

实现 MUST：

- 使用系统安全存储保存私钥
- 对可导出密钥做用户确认
- 对恢复操作做高风险 UI，且 §7.7 的 UI 字段展示要求 MUST 被遵守
- 对设备列表显示最近活动和授权来源
- 对吊销操作做不可抵赖记录
- 在 first-device inception bootstrap 中按 §5.0.1 step 6（first-backup gate）阻塞 inception key 退场

实现 SHOULD：

- 支持硬件安全模块或平台 keystore
- 支持 biometric unlock 但不把 biometric 当作 cryptographic secret
- 支持 passkey / WebAuthn 作为本地解锁与网关认证材料
- 支持企业设备管理和远程吊销

## 11. 一致性要求

Cokret v1 对设备、会话和恢复要求如下：

- Device record JSON Schema 由 `../models/common-fields.md`（`id:device` 类型与 typed-id 规则）与 `../crypto-media/device-lifecycle.md` 共同固定。设备记录 MUST 绑定 principal DID、device id、verification method、算法、创建时间、撤销状态和签名链。
- `ck.device.authorize` 与 `ck.device.revoke` MUST 进入 schema registry，并按 event auth 规则验证。`ck.device.revoke` 的控制面位置由其 Control Move 信封 `seal_basis`（授权基准，签名覆盖）与覆盖它的 accepted Seal（生效切点）表达，payload 不携带 frontier 字段；撤销后设备不得产生新的有效 session grant、KeyPackage 或 to-device write。
- Session grant MUST 绑定 principal DID、device id、service DID / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖：加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定、服务端不可解密要求、`series_seq` 严格单调、`supersedes` / `supersedes_digest` 链完整、`mixed_secret_storage=true` 在 non-personal_node profile 下被拒绝、`did_recovery` 域使用 `passphrase_kdf` 的 envelope 被拒绝(该域只允许 `recovery_public_key`)、§7.8 服务端限速与跨 actor 拒绝。
- MLS KeyPackage binding MUST 覆盖 principal DID、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝未绑定 DID / device trust chain 的 KeyPackage。
- Recovery policy grammar 由 `ck.schema.recovery_policy.v1`（`artifacts/schemas/recovery-policy.schema.json`）规范化；publish / rotate / share-revoke 的 wire 形态由 §8.1 描述。grammar MUST 表达 threshold、share holder、not_before、expires_at、allowed_proof_kinds、approval requirement 与 audit event；恢复只改变控制链，不自动授予内容读取或业务 capability。
- Recovery receipt 由 `ck.schema.recovery_receipt.v1`（`artifacts/schemas/recovery-receipt.schema.json`）规范化；`crypto-media/device-lifecycle.md` §15 step 7 写入的 receipt MUST 通过该 schema 校验，并绑定 `recovery_session_id` / `policy_id` / `policy_version` / `new_device_id` / `proof_summary` / `backup_classes_unlocked` / `welcome_count` / `outcome`。
- Backup series MUST 满足 §7.6：客户端 `LIST` 后重建链 → 验证 `supersedes_digest` → 用尾部 envelope 解密；当 `frontier_ref` 存在时 MUST 用 control stream snapshot 验证 frontier_digest 与 `ssk_generation`。
