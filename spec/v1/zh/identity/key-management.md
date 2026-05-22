---
title: Key Management
---

## 1. 目标

身份层定义“谁是主体”，加密层定义“如何保护内容”，但真正能让系统安全运行的是密钥管理。

本文定义 Contrix 的密钥生命周期：

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

长期密钥 SHOULD 尽量少在线使用。  
日常操作 SHOULD 由设备密钥或短期 session key 执行。

### 2.3 所有授权都必须可撤销

设备、agent、session 和企业网关颁发的权限 MUST 有明确失效条件：

- `expires_at`
- revoke event、status event 或 profile 注册的 credential status mechanism
- `scope`
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

要求：

- SHOULD 与日常设备隔离
- SHOULD 支持多份或门限方案
- MUST 只能执行 recovery policy 允许的操作
- recovery event MUST 写入 DID method history、key log 或等价 signed event

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

- MUST 有明确 scope
- MUST 有 `expires_at` 或 revocation check
- MUST 绑定 accountable actor
- SHOULD 使用 proposal / approval 约束执行高风险动作

agent key 的授权、轮换和撤销 MUST 进入可审计状态，而不能只存在于服务端配置。标准事件为：

| 事件 | 用途 | 必要授权 |
| --- | --- | --- |
| `cx.agent.key.authorized` | 绑定 agent DID / key id / scope / audience / `expires_at` / accountable actor 与 approval evidence。 | `cx.agent.key.manage` |
| `cx.agent.key.rotated` | 将旧 key 与新 key 绑定在同一 accountable actor 下，scope 不得扩大，TTL 不得长于被替换 key。 | `cx.agent.key.manage` |
| `cx.agent.key.revoked` | 撤销 agent key，并使后续 session / protocol action proof fail closed。 | `cx.agent.key.manage` |

高风险 agent key（能写入、调用外部工具、管理 capability、读取审计材料或代表用户发起 service-call）的 grant MUST 同时有 `expires_at`、resource selector、accountable actor、approval/proposal evidence 和 revocation freshness check。只声明 API token 或本地环境变量而没有上述事件链的 agent key 不得用于 v1 standard operation。

### 3.7 MLS KeyPackage Key

MLS KeyPackage key 用于加入加密 Realm。

要求：

- MUST 绑定到 Actor DID 和 device id
- MUST 由有效 device key 或 principal signing key 签名
- MUST 有发布时间与过期时间
- SHOULD 单次或短期使用
- 被撤销设备的 KeyPackage MUST 不再用于新加密

## 4. Device Record

建议 device record 是 actor-private signed Event 或 identity sidecar 中的 signed state。

示例：

```json
{
  "id": "cx:device:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_label": "Alice MacBook Pro",
  "device_public_key": "z6Mks...",
  "device_key_type": "Multikey",
  "created_at": "2026-04-26T00:00:00Z",
  "authorized_by": "cx:device:01964136-8000-7000-8000-000000000000",
  "authorization_ref": "cx:event:01964137-8000-7000-8000-000000000000",
  "status": "active",
  "last_seen_at": "2026-04-26T08:00:00Z",
  "revocation_ref": null
}
```

### 4.1 Principal Control Event Stream

设备、session、recovery 和 KeyPackage 有效性属于 principal 级状态，不属于任意协作 Realm。Contrix v1 使用 **Principal Control Event Stream** 承载这些 durable identity state。

当 `cx.device.authorized`、`cx.device.revoked`、`cx.device.list_update` 或 `cx.session.grant` 以 `cx.schema.event.v1` Event Envelope 传播时：

- `realm_id` MUST 是该 principal 的专用 `principal_control_realm_id`，不得使用任意协作 Realm 的 `realm_id`。
- `actor_id` MUST 是签发该控制事件的 principal、已授权 device、受信 recovery service 或组织声明的 session issuer。
- `content.principal_id` / `content.subject` MUST 与该 control Realm 绑定的 principal DID 一致；不一致时 MUST reject。
- control Realm 的 `cx.realm.create` 或等价 genesis record MUST 绑定 principal DID、DID method / key-log history、control stream policy 和可发现的 service endpoint。该 Realm MUST 使用 v1 标准 `kind=collaboration`，并通过 `fields.purpose="principal_control"` + `schema_refs` 包含 `cx.profile.principal_control_realm.v1` 标记其 control stream 角色（详见 §5.0.1 步骤 3）。control realm **不**使用单独的 Realm kind——所有 Realm-level 验证（schema、boundary、E2EE、federation）走 collaboration kind 的标准路径。
- 普通协作 Realm 的业务事件 MAY 通过 `refs[role=authorized_by]`（或 role=`did_inception` 等专门 role）、verified snapshot reference、policy server proof 或 device-state checkpoint 引用 principal control state；不得把另一个 principal 的 device/session 事件直接写入该协作 Realm history 来改变身份状态。

`principal_control_realm_id` MUST 可通过 DID Document service、normalized principal view、device/key server describe endpoint 或本地 account binding 验证。客户端无法验证 control Realm 与 principal DID 的绑定时，MUST fail closed：不得接受该 principal 的新 device grant、session grant、KeyPackage 或 device revocation 状态。

实现 MAY 用 identity sidecar、device registry 或 DID/key-log operation 存储同一状态，但它们必须提供等价的签名、digest、auth dependency 和撤销语义；桥接到 Event Envelope 时仍必须遵守上述 `realm_id` 规则。

## 5. 设备授权流程

### 5.0 First-Device Inception Bootstrap

§5.1 假设新设备由"已授权设备"签发 `cx.device.authorized` 才能加入。但 principal 第一次激活时只有一台设备，没有任何已授权 peer 可以扮演这个角色。如果不为这种"无 peer 设备"的初始情形定义协议路径，§5.1 的链条永远无法启动，§4.1 的 control stream 也无法获得 genesis record。

Inception bootstrap MUST 使用 DID method 自身的初始控制密钥作为信任根，把"第一台设备的 device key"和"DID 的 inception controller key"建立可验证绑定。Contrix 不发明新的 DID inception 操作；它把已有 DID method 的 inception 证据**重用**为 principal control stream 的 genesis record 授权依据。

#### 5.0.1 标准 Inception 路径（v1 core 默认 `did:webvh` principal）

1. **Inception key 生成**：客户端在用户首次注册或自主权恢复时本地生成一个 `inception_keypair`（Ed25519 / ECDSA-P256）。该密钥既是 `did:webvh` 第 0 条 `did.jsonl` entry 的 `updateKeys[0]` / `nextKeyHashes[0]`，也是首台设备的 device key 之一。
2. **`did:webvh` genesis 写入**：客户端按 `did:webvh` specification 计算 SCID，将 `did.jsonl` entry 0 写入 hosting domain（自有 / Auth Server 托管子域）。Entry 0 的 `versionId`、SCID、controller proof MUST 由 inception key 签发。可选 witness MAY 在 entry 0 之后补签，不阻塞 bootstrap。
3. **Principal control realm genesis**：客户端构造 `cx.realm.create` Event 创建 principal control realm（`realm_id` 即 `principal_control_realm_id`，绑定到 principal DID）。该 Realm 是 v1 标准 `kind=collaboration` Realm（不引入新的 Realm kind），并通过以下 Realm 字段把它标记为 control stream：
   - `fields.purpose = "principal_control"`（产品语义；reducer/authz 通过此字段识别 control stream）。
   - `schema_refs` 包含 `cx.profile.principal_control_realm.v1`（profile id；该 profile 收紧 control realm 的允许 event kinds、capability action、E2EE/federation 默认值）。
   - `encryption_profile = "none"`，`history_visibility = "joined"`，`anchor_profile = "single_did"`，`anchorer = <principal DID>`。
   - `created_by_principal = <principal DID>`，`security_class = "high_assurance"`（强制 federation_policy ∈ {closed, restricted, quarantine}）。

   Event 的 `actor_id` 是 principal DID，`proofs[]` 由 inception key 签发，`refs[]` 引用 `did:webvh` entry 0 的 `versionId` 和 SCID 作为身份证据 ref（`role="did_inception"`，`critical=true`）。Receiver 验证 control realm genesis 时 MUST 同时校验 `fields.purpose=principal_control` 与 `schema_refs` 包含 `cx.profile.principal_control_realm.v1`；缺一即按普通 collaboration Realm 处理（不再具备 control stream 的特殊语义）。
4. **首台设备自授权**：客户端构造 `cx.device.authorized` Event，`device_id` 是新生成的 device public key 派生 ID，`authorized_by` 直接引用 inception key 的 `verification_method`（即 entry 0 的 controller key）。该 Event 的 `proofs[]` 由 inception key 签发；`refs[]` 引用 control realm 的 genesis Event（`role="authorized_by"`）与 `did:webvh` entry 0 的 `versionId`（`role="did_inception"`，`critical=true`）。
5. **Inception key 的归宿**：完成步骤 4 后，inception key 的在线签名角色 MUST 在 `inception_key_max_online_window` 内退出，默认窗口为 24h。退出方式只能是：（a）写入 `did:webvh` entry 1 或等价 DID method operation，把日常 update / device authorization 权限轮换到新的 controller / device key，并从首台设备销毁 inception private key；或（b）把 inception key 封存为 recovery-only key，放入 secret storage / threshold recovery，记录 `sealed_at`、`expires_at?`、allowed recovery method，并禁止在线日常签名。窗口过期后，receiver / Auth Server MUST 拒绝 inception key 继续签发 `cx.device.authorized`、`cx.session.grant`、长期 capability 或 ordinary DID update，并写入安全审计；它只能按已声明 recovery policy 进入恢复流程。它 MUST NOT 长期作为日常 device signing key——暴露面应被限制到 inception bootstrap 与 recovery。
6. **后续设备**：第二台及以后设备走 §5.1 标准流程，由首台已授权设备签发 `cx.device.authorized`。

#### 5.0.2 `personal_node` Profile 降级路径（principal_method=`did:web`）

`personal_node` deployment profile 选择 `did:web` 作为 principal method 时，没有 entry-0 controller proof 可供引用。降级路径：

1. 客户端本地生成 `inception_keypair`，并以它构造一个临时 `did:key:<inception_pub>`。
2. 客户端把 `did:key:<inception_pub>` 作为 `cx.did.proof.continuity` 的 `old_did` 签发 continuity proof，绑定到目标 `did:web:<host>` 作为 `new_did`。该 continuity proof 由 inception key 单方签署即生效（personal_node profile 接受这种"自我升级"，因为 stake 低）。
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
- 校验首台 `cx.device.authorized` Event 的 `authorized_by` 引用与 inception key 一致；不接受 `authorized_by` 引用任何尚未 anchored 的 device。
- Inception bootstrap 成功后，receiver MUST 标记该 control realm 已通过 inception；后续 §5.1 的 `cx.device.authorized` Event MUST `authorized_by` 一台已 anchored 的 device，不得再次自授权。

#### 5.0.4 攻击模型

Inception bootstrap 的密钥学根**仅强于** DID method 自身的 inception 证据：

- `did:webvh` 提供 SCID + entry hash + controller proof，并可叠加 witness——攻击者需要同时控制 hosting domain 和 ≥1 trusted witness 才能伪造 inception。
- `did:web` 仅提供"hosting domain 当前内容"——攻击者控制 DNS/TLS 即可静默替换 inception。这正是 `personal_node` profile 之外不允许 `did:web` 作为 principal method 的根本原因（H1 / §3）。
- `did:key` inception **MUST NOT** 直接作为长期 principal——它必须在 §5.0.1 / §5.0.2 中升级为 `did:webvh` 或 `did:web`。

实现 MUST 在 UI 中向用户清楚展示 inception 路径的密钥学强度（"已 witness 的 did:webvh 链" vs "仅 hosting domain"），不得在 onboarding 中把两者展示为等强度。

#### 5.0.5 `personal_node`(`did:web`) → `small_team`(`did:webvh`) 跨 method 安全升级

**问题**: `personal_node` 阶段的 `did:web` inception 只受 hosting domain DNS/TLS 保护;若用户在注册期间 DNS 被劫持,攻击者可写入伪造 inception(并控制 inception key)。一旦该 principal 直接"无审"升级到 `small_team` 的 `did:webvh`,被劫持的 inception 历史会被当作正常历史延续,所有后续 capability / device authorization / state 都建立在攻击者根之上。

为此,跨 method 升级 **MUST** 满足以下硬条件,否则 receiver MUST `reject` 升级 transition Event(reason `inception_upgrade_evidence_insufficient`):

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

升级 transition Event(`cx.did.proof.continuity`,`old_did=did:web:<host>`,`new_did=did:webvh:<scid>:<host>`)**MUST** 满足 `cx.schema.did_continuity_proof.v1` transfer envelope 结构；reducer 与 receiver 直接消费下列字段集合，并按 schema 与签名链验证：

```json
{
  "schema": "cx.schema.did_continuity_proof.v1",
  "old_did": "did:web:<host>",
  "new_did": "did:webvh:<scid>:<host>",
  "purpose": "principal_method_upgrade",
  "issued_at": "2026-05-19T00:00:00Z",
  "transfer_evidence": {
    "old_did_document_canonical_hash": "sha256:<64-hex>",
    "old_did_document_fetched_at": "<RFC 3339 UTC>",
    "inception_pubkey_fingerprint": "sha256:<64-hex>",
    "user_oob_confirmation_id": "<opaque user-side confirmation token>",
    "user_oob_confirmation_method": "offline_paper|physical_meet|independent_channel"
  },
  "signature_chain": [
    { "alg": "...", "by": "<inception key>", "over": "transfer_envelope_canonical" },
    { "alg": "...", "by": "<did:webvh entry-0 controller key>", "over": "transfer_envelope_canonical" }
  ]
}
```

关键 normative 规则:
- `signature_chain` **必须**同时含两段签名:**inception key**(原 `did:web` 主体)+ `did:webvh` entry-0 controller key(新 method 主体)。任一缺失或签名失效 → reject `inception_upgrade_signature_chain_invalid`。
- `inception_pubkey_fingerprint` 必须 byte-for-byte 等于 `did:web` DID Document 当前 `verificationMethod[0]` 的派生 fingerprint;同时必须在 `transfer_evidence` 中以 user-readable 形式呈现给 receiver(便于 receiver 二次校验)。
- `user_oob_confirmation_id` 是 user-side 不透明 token——客户端 SHOULD 把 OOB 确认结果写入 user-private secret storage,服务端 / receiver 不 trust 该字段为真实人类确认证据,但**保留**以便审计回放与 UI 重现。`user_oob_confirmation_method` 是枚举 hint,receiver MAY 用它把"通过弱通道(independent_channel)确认的迁移"打上额外的低信任标记。
- 整个 transfer envelope MUST 在签名 transcript 中包含 `old_did_document_canonical_hash`——这一字段 freezes 攻击者对 hosting domain 在升级时刻**之后**继续替换 DID Document 的可能性(任何替换都会让 hash 不再匹配 receiver 拉取的新 document)。

##### 5.0.5.3 Receiver 验证规则

任何接收升级 transition Event 的 receiver(principal server、其他 federation peer、新设备 join 时)**MUST**:

1. 拉取 `old_did` 的当前 DID Document,canonicalize 后 hash 比对 `transfer_evidence.old_did_document_canonical_hash`;不一致 → reject `inception_upgrade_old_document_hash_mismatch`。
2. 校验 `signature_chain` 两段签名:inception key 签名(`verification_method` 必须出现在被 hash 的 old document `verificationMethod[]` 内)+ `did:webvh` entry-0 controller key 签名(必须能在 `did:webvh` `did.jsonl` entry 0 找到)。任一失败 → reject `inception_upgrade_signature_chain_invalid`。
3. 校验 `inception_pubkey_fingerprint`,确认它等于步骤 1 拉取到的 old document `verificationMethod[0]` 派生 fingerprint;失败 → reject `inception_upgrade_fingerprint_mismatch`。
4. 校验 `did:webvh` `entry 0` 的 SCID / entry hash / controller proof(标准 `did:webvh` inception 验证)——这一段独立于 `did:web` 阶段。
5. 写入"该 principal 已通过 §5.0.5 跨 method 升级"标记;后续 Event 的 `actor_id` MAY 是 `did:web:...`(历史 Event)或 `did:webvh:...`(升级后 Event);receiver MUST 把两者视作同一 principal,但**不接受**任何新签名的 Event 仍引用 `did:web` inception key——升级后 inception key MUST 进入 `did:webvh` rotation 链或销毁(§5.0.1 步骤 5)。

##### 5.0.5.4 不允许的简化

- ❌ "用户点 OK 即升级"(无 OOB confirmation_method / 无 inception_pubkey_fingerprint 二次确认) — receiver MUST reject `inception_upgrade_evidence_insufficient`。
- ❌ inception key 单签升级(仅 inception key 签 transfer envelope) — receiver MUST reject `inception_upgrade_signature_chain_invalid`(缺 entry-0 controller key 那一段)。
- ❌ DNS / hosting domain 内嵌"确认页"作为 OOB(同源攻击窗口未脱离)。
- ❌ 升级后继续接受用 `did:web` inception key 签发的新 Event(必须在升级落盘后立即把该 key 标 retired / archived;之前已签发并 anchored 的历史 Event 保留)。

##### 5.0.5.5 安全代价登记

- 该流程把 personal_node 阶段被 DNS 劫持的损害限制在 personal_node Realm 内部;升级后 attacker 无法通过升级路径继承新 method 的根。
- 代价:升级流程对用户**强制**至少一次离线 / 独立通道确认,UI 不能"自动一键升级"。这是明确取舍:为防止注册期 DNS 劫持继承,引入一次性 OOB 友好度成本。
- 对从未通过 personal_node 阶段(直接以 `did:webvh` 走 §5.0.1)的 principal,本节不适用。

### 5.1 新设备加入（首台设备已存在）

推荐流程：

1. 新设备本地生成 device key。
2. 新设备展示 pairing code / QR，其中包含 device public key、challenge、过期时间。
3. 已授权设备扫描并验证 challenge。
4. 已授权设备签发 `cx.device.authorized` event。
5. Events API / identity registry 接受并传播该 event。
6. 新设备开始同步 Event history、Realm membership 和必要的 MLS Welcome。

`cx.device.authorized.content` 示例：

```json
{
  "principal_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
  "device_public_key": "z6Mks...",
  "scopes": [
    "cx.events.describe",
    "cx.events.submit",
    "cx.account.subscribe",
    "cx.keys.keypackages.upload"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "authorized_by": "cx:device:01964136-8000-7000-8000-000000000000",
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example#device-old",
    "jws": "..."
  }
}
```

### 5.2 设备吊销

设备丢失、出售、被恶意控制或员工离职时，MUST 发布 `cx.device.revoked`。

吊销后：

- Events API MUST 拒绝该设备的新签名写入
- authz MUST 视相关 session grant 失效
- 加密 Realm SHOULD 通过 MLS Remove 推进 epoch
- 客户端和受托 projection executor SHOULD 标记已撤销设备产生的未确认 Operation 为高风险

## 6. Session Grant

Session grant 用于 OIDC / SSO、浏览器短会话、远程执行环境。  
Contrix v1 使用 `cx.session.grant` 作为 principal control stream 中的标准 durable control event 类型。

`cx.session.grant.content` 示例：

```json
{
  "grant_id": "cx:grant:01964198-0000-7000-8000-000000000000",
  "realm_id": "cx:realm:01964198-7000-7000-8000-000000000000",
  "issuer": "did:web:auth-gateway.example.com",
  "subject": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "session_public_key": "z6Mss...",
  "audience": "https://app.example.com",
  "scopes": [
    "cx.events.submit",
    "cx.realm.discover",
    "cx.object.read",
    "cx.flow.update",
    "cx.message.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-27T00:00:00Z"
}
```

> 注：`cx.session.grant` 是 principal control stream 事件，`realm_id` MUST 等于 subject 的
> principal control realm（§4.1）。本字段是 control event 必填项；省略 MUST 被 reducer
> 以 `schema_violation` 拒绝。

规则：

- session grant MUST 由可信 issuer 签名
- session key MUST NOT 超过 grant 的有效期
- session grant SHOULD 绑定 audience
- 在条件允许时，session grant SHOULD 在 WebCrypto / 平台 keystore 中以不可导出方式存储
- session grant 撤销 MUST 由 accepted `cx.session.grant` 状态更新、device/account revoke、或 profile 注册的 credential status mechanism 表达；不得使用未注册的 `cx:revocation-list:*` typed ID。

## 7. 密钥备份

### 7.1 备份内容

Contrix v1 将密钥备份分为三个不同密钥域。实现 MUST 在 metadata 中声明备份域，且不得把一个域的解锁材料当作另一个域的授权证明：

- `did_recovery`：恢复 DID 控制链所需的 recovery key share、门限恢复 share metadata 或受信恢复服务证明。它只能用于 `recovery_policy` 允许的 `recover` / `rotate` / `cx.device.authorized` 等操作。
- `secret_storage`：保存 `self_signing_key`、`user_signing_key`、recovery secret、MLS group secrets backup key、applet delegated device secret 和 encrypted private account data cache。
- `mls_history`：保存用户已有权读取的 Realm / Flow track 的 MLS group state、历史 epoch key material、pending Welcome 和必要的 epoch 缺口恢复 metadata。

域隔离规则：

- 每个 `backup_class` MUST 使用独立 salt、KDF context、HKDF info 和 AEAD associated data；一个域的 derived key、commitment key 或 wrap key 不得直接用于另一个域。
- AEAD AAD MUST 绑定 `actor_id`、`device_id`、`backup_class`、`backup_version`、item type、created_at 和 schema/profile id，防止把 ciphertext 从一个域重放到另一个域。
- 即使用户选择同一个 passphrase，客户端也必须先用 KDF 得到 root unlock key，再用 `HKDF(root, info="contrix-key-backup/<backup_class>/<subdomain>/v1")` 派生域内子密钥；不得复用裸 KDF 输出。
- `did_recovery` 域不得和 `mls_history` 域共享 wrap key、recovery share 或 key commitment。攻破 `mls_history` backup key 不得允许 DID rotate / recover；攻破 DID recovery share 也不得直接解密 MLS 历史。
- `self_signing_key` / `user_signing_key` 与 MLS group secrets backup key MUST 分成不同 backup envelope 或不同 subdomain key，并 SHOULD 要求不同 passphrase、硬件保护或门限恢复策略。**单一 passphrase 同时控制身份签名和 E2EE 历史**的失败模式在任何部署上都不可接受。只有 `cx.profile.personal_node.v1` MAY 接受 `mixed_secret_storage=true` 的本地备份 envelope；`small_team`、`organization`、`high_security_organization`、`sovereign_deployment` 等 profile MUST 拒绝该 flag。mixed 模式若使用 `passphrase_kdf`，MUST 使用 Argon2id 且 `memory_kib >= 262144`、`iterations >= 4`、`parallelism >= 1`。

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

标准备份对象使用 `cx.schema.key_backup.v1`。服务端只校验 envelope metadata、访问控制和签名，不得要求上传解锁口令、recovery private key、硬件解锁材料或任何可直接解密 ciphertext 的 secret。

示例：

```json
{
  "backup_id": "cx:backup:01964137-0000-7000-8000-000000000000",
  "actor_id": "did:webvh:QmZ7p8K3pV4cXbKqL2nMsR9tWfH:alice.example",
  "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
  "backup_class": "secret_storage",
  "backup_version": "kb_1",
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
      "aead_profile": "cx.aead.xchacha20_poly1305.v1",
      "nonce": "base64url..."
    },
    "key_commitment": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "contents": [
    {"item_type": "self_signing_key", "secret_id": "self_signing_key"},
    {"item_type": "user_signing_key", "secret_id": "user_signing_key"}
  ],
  "ciphertext": "base64url...",
  "ciphertext_digest": "sha256:2108421084217842908421084210842121084210842178429084210842108421",
  "auth_data": {
    "device_id": "cx:device:01964137-0000-7000-8000-000000000000",
    "signature": "base64url..."
  }
}
```

实现 SHOULD 使用现代 KDF，例如 Argon2id。声明 `cx.profile.key_backup.memory_hard.v1` 时，`recipient_method="passphrase_kdf"` 的新备份 envelope MUST 满足 `cx.schema.key_backup.v1` 中的机器下限：Argon2id 至少 `memory_kib >= 65536`、`iterations >= 3`、`parallelism >= 1`；salt MUST 随 envelope 独立生成并进入 KDF 输入。
如果平台限制只能使用 PBKDF2，迭代次数 MUST 足够高，并 MUST 在 backup metadata 中声明降级原因、迭代次数、salt、KDF 参数和 profile id。`cx.profile.key_backup.memory_hard.v1` 对 PBKDF2 的最低线是 `iterations >= 600000` 且 `hash ∈ {sha256, sha384, sha512}`，并要求 `degraded_profile_reason`。新创建的云保险箱不得默认使用 PBKDF2。

FIPS-only 部署若不能批准 Argon2id，MUST 使用显式降级 profile（例如 `fips_pbkdf2` key backup profile），并声明其安全级别低于默认 memory-hard backup profile。该 profile 至少要求 FIPS 批准的 KDF、强口令策略、在线恢复限速、失败审计和备份 metadata 中的 `degraded_profile_reason`；它不得作为公共网络默认 key backup profile。

`key_commitment` 的推荐构造：

```
derived_key = KDF(passphrase, salt, kdf_params)
commitment_key = HKDF(derived_key, info="contrix-key-backup-commitment-v1")
key_commitment = SHA256(commitment_key)
```

`recipient_method="passphrase_kdf"` 的 AEAD nonce MUST deterministic derive，不得由服务端随机生成或由用户输入提供：

```text
nonce_key = HKDF(derived_key, info="contrix-key-backup-aead-nonce-v1")
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
    "aead_profile": aead.aead_profile
  })
)[0:N_AEAD]
```

`aead_profile` 是可选但推荐的协商标识，绑定 AEAD 算法版本、nonce 长度、tag 长度、key 长度和 AAD 构造。接收方看到不支持的 `aead_profile` MUST fail closed；不得只凭 `aead.name` 推断可接受的参数组合。未携带 `aead_profile` 的历史 envelope 按 `aead.name` 的 v1 默认 profile 解释，但新写入 envelope SHOULD 显式携带 profile id。

Producer MUST reject attempts to write two backup envelopes with the same nonce derivation tuple. Receiver MUST recompute the nonce for `passphrase_kdf` envelopes before decryption and reject mismatches as `schema_violation`.

客户端 MAY 在尝试解密 `ciphertext` 前用用户输入的 passphrase 派生 key，计算 commitment 并与 envelope 中的 `key_commitment` 比对。不匹配时 MUST 拒绝解密并提示用户 passphrase 错误。`key_commitment` 只是本地快速拒绝错误口令和防止密文替换的辅助值，不是服务端认证材料；服务端不得要求用户上传 passphrase、derived key、commitment key 或使用 `key_commitment` 做在线口令检查。离线攻击者仍可对备份执行 KDF 级别的口令猜测，因此实现必须执行强口令策略、Argon2id 参数下限和速率受控的恢复 UI。

域隔离 profile 的 conformance proof MUST 至少证明：不同 `backup_class` / subdomain 的 HKDF info 不同、AEAD AAD 覆盖域和 item type、key commitment 不能跨域复用、恢复流程不会把一个域的解锁成功当作另一个域的授权证明。

`ciphertext_digest` 覆盖密文字节，`plaintext_commitment` 若存在只用于本地完整性或跨设备一致性检查；服务端不得要求知道明文 hash 才能存储或返回备份。

### 7.3 恢复流程

恢复流程：

1. 新设备生成 device key。
2. 用户输入 passphrase 或收集 recovery shares。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `cx.device.authorized`。
6. 若涉及 E2EE Realm，客户端拉取 MLS state 并处理 epoch 缺口。

恢复 device key 时 MUST 生成新的 device key，不得把备份中的旧设备身份克隆到新设备。恢复出的 `self_signing_key` / `user_signing_key` 可用于重建 cross-signing 状态，但 Cross-Signing Reset 仍必须满足 `device-lifecycle.md` 的高风险证明要求。

### 7.4 所有权证明与解密证明

DID 控制权证明 SHOULD 优先使用签名挑战，而不是“能解开某段历史密文”：

- 当前控制密钥、已授权 device key 或 recovery key 对服务端 fresh challenge 签名。
- 新设备生成 device key 后，由当前有效设备或 recovery policy 签发 `cx.device.authorized`。
- recovery service 在 DID Document、organization policy 或 recovery policy 中被明确声明，并签发可验证 recovery event。

“能解密用某个公钥加密的数据”MAY 作为恢复流程中的一个密码学因子，但不得单独等同于账号所有权。允许的形式是：服务端生成短期随机 challenge，按当前 key-log / recovery policy 指定的 recovery public key 加密，客户端在本地解密后对 challenge transcript 签名或返回 proof。该流程 MUST 绑定：

- `challenge`
- `audience` / `origin`
- `service_did`
- `principal_did`
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

因此，解密能力最多是 recovery factor；真正改变 DID 控制状态必须落成 DID method history、key log、`recover`、`rotate`、`cx.device.authorized` 或等价 signed event。

## 8. 社交恢复与门限恢复

高价值账号 SHOULD 支持门限恢复。

Recovery policy 字段：

```json
{
  "type": "recovery_policy",
  "threshold": 3,
  "shares": [
    {
      "holder": "did:web:alice-friend.example",
      "share_id": "s1",
      "transport": "sealed_box"
    }
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null
}
```

恢复 share holder 只能帮助恢复控制权，不自动获得读取内容或代表主体操作的 capability。

## 9. 泄露响应

当怀疑密钥泄露时，客户端 SHOULD：

1. 立即发布 device revocation 或 key rotation。
2. 停止接受已撤销设备/session 的新写入。
3. 对 E2EE Realm 触发 MLS Remove / Update。
4. 标记泄露窗口内的高风险 Operation。
5. 提醒用户检查未知设备、session 和 agent grant。

如果 principal signing key 泄露但 recovery key 安全，MUST 通过 recovery policy 重建当前控制密钥。  
如果 recovery key 也泄露，SHOULD deactivate 原 DID 并执行身份重建。

## 10. 实现要求

实现 MUST：

- 使用系统安全存储保存私钥
- 对可导出密钥做用户确认
- 对恢复操作做高风险 UI
- 对设备列表显示最近活动和授权来源
- 对吊销操作做不可抵赖记录

实现 SHOULD：

- 支持硬件安全模块或平台 keystore
- 支持 biometric unlock 但不把 biometric 当作 cryptographic secret
- 支持 passkey / WebAuthn 作为本地解锁与网关认证材料
- 支持企业设备管理和远程吊销

## 11. 一致性要求

Contrix v1 对设备、会话和恢复要求如下：

- Device record JSON Schema 由 `../models/common-fields.md`（`id:device` 类型与 typed-id 规则）与 `../crypto-media/device-lifecycle.md` 共同固定。设备记录 MUST 绑定 principal DID、device id、verification method、算法、创建时间、撤销状态和签名链。
- `cx.device.authorized` 与 `cx.device.revoked` MUST 进入 schema registry，并按 event auth 规则验证。撤销后设备不得产生新的有效 session grant、KeyPackage 或 to-device write。
- Session grant MUST 绑定 principal DID、device id、service DID / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定和服务端不可解密要求。
- MLS KeyPackage binding MUST 覆盖 principal DID、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝未绑定 DID / device trust chain 的 KeyPackage。
- Recovery policy grammar MUST 表达 threshold、share holder、not_before、expires_at、allowed recovery methods、approval requirement 和 audit event；恢复只改变控制链，不自动授予内容读取或业务 capability。
