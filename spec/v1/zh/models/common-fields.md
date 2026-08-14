---
title: Common Fields
status: candidate
normative: true
stability: v1
updated: 2026-07-13
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

本文定义 Arkret 协作图所有 canonical object 共享的字段、lifecycle 状态机、主体引用语义与 reducer 总则。每个对象自己的字段表（Realm / Strand / Message / ...）放在该对象的专属文件中；本文只承载"所有对象都遵循"的内容。

## 2. 类型记法

| 记法 | 含义 |
| --- | --- |
| `string` | JSON string。 |
| `boolean` | JSON boolean。 |
| `integer` | JSON integer，不能是 float。 |
| `number` | JSON number，必须满足 `encoding.md` 的 number profile。 |
| `object` | JSON object，字段名必须 snake_case。 |
| `array<T>` | JSON array，元素类型为 `T`。 |
| `map<T>` | JSON object，value 类型为 `T`。 |
| `enum(...)` | 枚举字符串。 |
| `timestamp` | RFC 3339 UTC string，必须以 `Z` 结尾。 |
| `did` | DID URI string。 |
| `id:<kind>` | `ak:<kind>:<payload>` typed ID；payload 由该 kind 在 `id-kind-registry.json` 声明的 `id_form` 唯一决定。 |
| `ref:<kind>` | 指向 `<kind>` 的 typed reference material；wire form 同样由 `id-kind-registry.json` 或对应 profile 声明，但字段语义是因果 / proof / content-addressed / profile-scoped reference，而不是普通对象主键。 |
| `digest` | 自描述 `<digest-suite>:<lowercase_hex_digest>`（suite 取 `digest-suite-registry.json` 的 active 套件，如 `sha256:` / `blake3:`；实际套件由 Realm `digest_algorithm` 决定）。 |
| `cursor` | `ak:cursor:<base64url>` opaque string。 |
| `patch` | `ak.schema.patch.v1` 形态的 JSON patch 片段，具体路径与 op 规则见 [`event-and-patch.md`](./event-and-patch.md)。 |

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `ak:device:<uuid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `ak:<kind>:<uuid>` 格式。这些标识符的编码规则由各自所在章节定义。`recording_id` 是 [`crypto-media/call-state.md` §5](../crypto-media/call-state.md) 定义的 opaque 领域标识（示例形态 `rtc-recording-<uuid>`）：它是 backend 媒体服务（如 LiveKit Egress）生成的 opaque 录制 lifecycle 句柄，进入 recording key exporter Context，**不是** `ak:*` typed ID。

Arkret 命名空间与分隔符约定（normative）：`.` 与 `:` 表达不同层级，MUST NOT 互换，也不得把其中一种拼写当作另一种的 alias。

| 形态 | 语义 | 示例 |
| --- | --- | --- |
| `ak.<symbol-path>` | **符号名称 / 注册表词汇**。`.` 只表达命名空间与分类层级；值命名一种 event、operation、schema、profile、capability action、content kind、Cell Family 或 namespaced key，不直接充当某个协议对象实例的 typed reference。 | `ak.message.create`、`ak.self.events.command.submit`、`ak.schema.event.v1`、`ak.component.strand.discussion.timeline.v1` |
| `ak:<kind>:<payload>` | **具体实例或引用**。第一个 `:` 把 Arkret namespace 与 ref kind 分开，第二个 `:` 开始该 kind 的实例载荷；载荷由 `id-kind-registry.json` 对应 kind 的 wire form 决定。 | `ak:message:<44-char-event-token>`、`ak:strand:<44-char-event-token>`、`ak:seal:sha256:<digest>`、`ak:trust_domain:<scope>` |
| `ak:cell:<cell-family>:<subject>` | **复合 typed reference**。外层 `ak:cell:` 表示 CellRef；`<cell-family>` MUST 原样嵌入完整的点分 `ak.component.<family-path>.v<n>` 符号名称；`<subject>` MAY 自身是一个带 `:` 的 typed reference。 | `ak:cell:ak.component.strand.discussion.timeline.v1:ak:strand:<44-char-event-token>` |

因此，看到 `ak:` 先按“typed ref / special-form ref”解析，看到 `ak.` 先按“registry symbol / namespaced key”解析。CellRef 中同时出现两者是有意的类型组合，不是可选拼写：省略内层 family 的 `ak.` 限定、把外层 CellRef 写成点分名称，或将 `ak.component.*` family 改写为冒号分隔，均不是 canonical wire。完整 typed-ref special forms 以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 和 [`encoding.md` §4](../conformance/encoding.md) 为准；各点分 symbol 的合法 segment、版本后缀及登记边界以对应 registry/schema 为准。任何缺席于当前 registry/schema 的前缀或拼写都不是 alias，parser MUST fail closed。

需要安全域分离的固定字符串 label 也使用 registry 明确登记的 `ak.*` 值。MLS GroupContext extension 的当前 wire 名是 `mls_governance_binding`（codepoint 0xF1C0，不使用品牌前缀），实现 MUST 用 `mls_governance_binding`、MUST NOT 接受其它拼写。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- Event Envelope 顶层未知字段 MUST 被 schema validation 拒绝；非关键扩展只能放入 `payload.x_*`，且仅当该 payload kind 的 schema 显式声明 `x_*` patternProperties 扩展槽时才可使用——未声明扩展槽的 payload kind 不接受任何未知字段（payload schema 的 `additionalProperties: false` 即权威判定）。实现 MUST 在 canonical bytes、存储、转发和 backfill 中保留 schema 允许的 `x_*` 字段，但 MUST NOT 让 `x_*` 字段绕过 capability、schema、policy 或加密约束。需要扩展槽的 payload kind SHOULD 先在对应 schema 登记 `x_*` patternProperties 槽再使用；当前已声明扩展槽的 payload kind 以 schema 为准（Invite 的六个逐 Event payload schema 各自声明该槽）。未知 critical extension MUST fail closed。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `ak:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 前缀由字段的**语义类型**决定，不由承载介质决定。配置、环境变量、数据库、HTTP header 或签名 transcript 不会把裸字符串自动升级成协议 ID；一旦一个值被声明为 `id:<kind>`，它在进入领域模型时就 MUST 已是完整 canonical typed ID，签名与 hash 层 MUST 原样承诺该值，MUST NOT 在签名前后补前缀、去前缀、大小写折叠或接受裸 payload alias。
- 外部标准拥有的标识符保留该标准的 canonical namespace：完整 DID / DID URL 分别使用 `did:<method>:...` / `did:<method>:...#<fragment>`，MUST NOT为完整 DID 另加 Arkret typed-ID 前缀。Arkret 从 DID 投影出的稳定身份核是另一个已登记类型 `ak:did_core:<method>:<core>`；字段要求 `did_full_id`、`did_url` 或 `did_core_id` 中的哪一种，完全由 schema 决定，不得因它进入签名或数据库而互换。
- 配置字段若会进入 wire、canonical object、签名、hash、联邦或审计语义，MUST 接受并保存完整 canonical 值。例如 `trust_domain` 配置使用 `ak:trust_domain:<scope>`。若实现希望提供只填写 `<scope>` 的运营便利入口，必须使用语义不同且显式命名为 `trust_domain_scope`（或等价的 `*_scope`）的输入，在配置解析边界一次性构造并验证 `trust_domain`；同一个配置键 MUST NOT 同时接受裸 scope 与完整 typed ID 两种 alias。
- 数据库压缩表示必须在 schema 与类型名上显式。名为 `realm_id`、`trust_domain`、`principal_id` 等 canonical identity 列 SHOULD 保存完整 wire value；若只保存载荷，列 / 类型 MUST 命名为 `realm_token`、`trust_domain_scope`、`did_core_payload` 等非 canonical 名称，并由唯一 storage adapter 无损恢复。恢复之前的内部值 MUST NOT越过 storage adapter，也不得参与签名、hash、日志、错误响应或跨服务比较。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `ak:device:<uuid>`，MUST NOT 写成局部别名如 `dev_a` 或 `a`。
- `summary` / `description` 命名约定：canonical object 或 projection row 的短摘要、列表预览、聚合摘要使用 `summary`；Strand 的用户可读短摘要放在 `metadata.summary` 或 `encrypted_metadata`，不得作为顶层 `summary`。原因说明、补充说明、长说明或 schema / registry 元数据说明使用 `description`。OpenAPI 自身标准关键字 `summary` / `description` 按 OpenAPI 语义使用。若字段承载人类可读名称，canonical object 默认使用 `title`；Strand 使用 `metadata.title` 或 `encrypted_metadata`，Actor / user-facing identity profile 使用 `display_name`；`name` 只用于外部协议、加密算法、service surface 或 registry 内部 label，不作为 Realm / Space / Strand 等 canonical object 的显示名。
- Projection row 若表达 canonical object 的同一概念，MUST 沿用 canonical 字段名（例如 `title`、`summary`、`avatar_blob_ref`、`owning_organizations`），MUST NOT 另起 `name`、`avatar`、`official_organizations` 等别名。若服务需要返回渲染友好的派生对象，字段名 MUST 明确带 projection 语义并有 schema；v1 默认不定义通用 `avatar` projection，头像引用使用 `avatar_blob_ref`。
- `_id` / `_ref` / `_did` 后缀约定见 §2.1。简要规则：单一具体 protocol object kind 与 service identity 使用 `_id`；因果 / proof / schema-profile / content-addressed / polymorphic reference 使用 `_ref` / `_refs`；其它必须保留 DID ecosystem 术语的原始 material 使用 `_did`。字段后缀表达协议语义角色，不单独决定 wire value 类型，也不表达授权、同步、保留或加密是否级联；这些语义 MUST 由 role prefix、schema description 与对象专属章节定义。
- 分类字段使用以下四条互斥命名轴；机器许可与精确上下文以 [`classification-field-registry.json`](../../artifacts/registry/classification-field-registry.json) 为准：

  | 轴 | 规范语义 | 命名要求 |
  | --- | --- | --- |
  | `kind` | Arkret 自有 discriminator、routing 维度、registry family、互斥 shape 选择与 reducer/lattice 分派。开放或闭合 value set 均可；是否开放由 schema/registry 另行声明。 | 裸 `kind` 或 `*_kind` / `*_kinds`。Arkret 自有分类默认使用此轴。 |
  | `type` | 仅用于直接继承 IANA/HTTP、W3C DID/VC/Data Integrity、MLS、WebRTC 等外部标准的字段名、值集和分派语义。Arkret 不得添加私有值、改写含义或把它变为 Arkret 主分派轴。 | 裸 `type` 或 `*_type` / `*_types`；每个使用点必须在 classification registry 以精确 schema/doc path 登记外部锚点。 |
  | `class` | 有限、无序、闭合，且不选择互不兼容对象 shape 的分类。 | `*_class` / `*_classes`；必须可解析到 finite enum/const，不能表示自由标签或开放 registry。 |
  | `tier` | 有限且存在严格全序，比较结果会改变协议判定的等级。 | `*_tier`；必须登记完整顺序与比较语义。v1 当前仅保留 `risk_tier`，顺序为 `low < medium < high`。 |

  四条硬判据（normative）：

  1. **Selector 判据**：任何 wire 字段若被可执行 artifact 的 `{"kind":"select","selector":"<path>"}` 引用，作为主 cell subject 分类维度，或在 discriminated schema 分支中选择互斥 Arkret shape，其字段名 MUST 为 `kind` / `*_kind` / `*_kinds`。
  2. **闭集判据**：`*_class` / `*_classes` MUST 直接或经 `$ref` 解析到有限 enum/const；registry/fixture-only context MUST 在 classification registry 明列 `allowed_values`。自由字符串、开放 registry 或 `additionalProperties` taxonomy 不得使用 class 轴。
  3. **外部锚点判据**：wire、normative canonical JSON 与 Arkret 可执行 artifact DSL 中的 `type` 轴字段 MUST 有逐路径外部锚点，且 `dispatch_authority="external_standard"`、`arkret_extensions_allowed=false`。真正的 JSON Schema `type` vocabulary keyword 由 parser 上下文排除；Arkret mini-schema 的值形状声明使用 `value_shape`。
  4. **同轴与顺序判据**：同一概念不得并存不同后缀轴；无法从 stem 判断的正交概念必须用 `semantic_axis` / `distinct_from` 显式声明。任何 tier 字段必须有有限值、严格全序和比较语义。

  因而 Event Envelope 的唯一事件 discriminator 是 `kind`；`morph_kind`、`service_kind`、`claim_kind` 与 `notary.kind` 均为 Arkret 自有分派。MLS `proposal_type`、WebRTC session description `type`、W3C DID/Data Integrity raw object `type` 与 IANA/HTTP `media_type` / `content_type` 只在 registry 登记的精确路径保留，不形成全局例外。
- 时间边界命名约定：有效期下界统一使用 `not_before`，有效期上界统一使用 `expires_at`；缓存或派生结果的失效时间使用带领域前缀的 `cache_expires_at`。新增 wire 字段不得使用 `valid_from`、`valid_until` 或 `not_after` 作为同义别名。**已登记外部标准命名例外**：[`calendar-event.md` §4.2](./calendar-event.md) 的 recurrence 终止字段名为 `until`，不是 `expires_at`。它不是绝对 instant，也不是对象级有效期上界，而是 RFC 8984 `RecurrenceRule.until` 的 snake_case 映射——按事件 `timezone` + `tzdb_version` 解释的 local 终止界，与 occurrence 的 local start 做 `<=` 比较。沿用外部标准名是有意取舍，MUST NOT 改名为 `expires_at`；反之，新增的对象级有效期上界字段仍 MUST 使用 `expires_at`，MUST NOT 借用 `until`。**已登记 interop 命名例外**：设备验证 to-device 消息族 `ak.key.verification.*`（schema [`device-message.schema.json`](../../artifacts/schemas/device-message.schema.json) 的 `key_verification_content`）沿用 Matrix `m.key.verification` interop 的裸字段名 `timestamp` 表示请求签发 instant，是对齐外部验证协议 transcript 的有意例外，不改名为 `issued_at`；新增的非 interop date-time wire 字段仍 MUST 使用 `_at` 形态。
- `state` / `status` / `stage` 命名约定：`state` 表示 canonical object 的物理生命周期；`stage` 表示 Strand / Morph 等业务进度轴；`status` 只用于账号、session、delivery、外部过程或 registry 条目状态，不用于表达 object lifecycle 目标值。对象 lifecycle payload 若需要携带目标状态，字段名使用 `target_state`。
- `created_by` / `creator_*` 命名约定：materialized object metadata 使用 `created_by` / `updated_by`，由 reducer 从 Event `actor_id` 派生。`creator_*` 只用于外部协议或加密 transcript 自身的创建者 tuple（例如 MLS group creator），不得作为 object 创建主体字段的别名。
- 哈希字段命名三词词汇表：算法/函数族选择器使用 `<noun>_algorithm`（枚举字符串，例如 `digest_algorithm: "sha256"`）；任意字节的不透明哈希输出使用 `<noun>_digest`（wire 形态必须是自描述 `<alg>:<hex>`）；树状 / Merkle / 累加器的根使用 `<noun>_root`（同样是 `<alg>:<hex>`，区别在于单独验证还需配套包含证明）。**wire 字段名 MUST NOT 以"hash"结尾（不论是 `_hash` 后缀还是 `hash_profile`、`hash_algorithm` 等同义形态）**；算法选择器只能使用 `<noun>_algorithm`，字节输出只能使用 `<noun>_digest`。复合 commitment 对象（例如 `event_set_commitment`）的外层名描述语义，内部以 `algorithm` + `root` 或 `digest` 表达字节材料；外层 MUST NOT 再追加 `_digest` 后缀。Event proof 绑定 canonical Event bytes 的字段名是 `event_digest`；非 Event 通用 detached proof 使用 `payload_digest`，其说明必须写明被 digest 覆盖的 canonical payload。
- 签名 proof 中表示签名 key DID URL 的字段统一为 `verification_method`，不得使用 `signed_by`。协议级密钥标识使用 `key_id`；JOSE/JWK 结构可保留标准 `kid` / `alg`。若 schema 显式定义紧凑 detached signature tuple `{alg,kid,sig}`，短字段 `sig` 只允许出现在该 tuple 内；协议对象的普通签名字段使用 `signature` 或带角色的 `<role>_signature`。若需要表达消息或通知中的发送主体，使用带角色的 `sender_actor_id`；展示名称使用 `sender_actor_display_name`，不得用裸 `sender` 承载 DID。
- `recipient_service_id` 与 `audience` 不可互换：前者是物理路由目标 service DID，后者是密码学 transcript / proof 的受众绑定。即使 `audience` 只有一个 DID，也不得替代 `recipient_service_id`；反之亦然。
- `scope` 命名约定：当 scope 是该对象自身的边界字段时，wire schema 使用裸 `scope`（与对象自身 `id` 的命名规则相同），例如 `ak.schema.erasure_receipt.v1.scope`、`ak.schema.erasure_verification_stub.v1.scope`、`ak.schema.event_batch_receipt.v1.scope`。当字段引用外部对象、表达子结构中的特定作用域，或同一 payload 同时出现多个 scope 语义时，必须用领域前缀说明形态与用途，例如 `read_scope`、`event_range`、`match_scope`、`claim_scope`、`agent_key_scope`、`consent_scope`、`realm_key_scope`、`extension_scope`、`constraint_scope`、`policy_scope`、`search_scope`、`relation_scope`。Registry 元数据若表示条目适用范围，可继续使用 `scope`。
- 诊断命名约定：机器可枚举的失败 / 恢复 / reset 原因使用 `reason_code` 或带领域前缀的 `*_reason_code`；人类可读自由文本使用 `reason` 或 `description`。受控枚举不得命名为 `reason`。
- ID kind 与 wire prefix 必须使用完整 snake_case 名称，不得使用缩写前缀（例如使用 `ak:notification:`、`ak:device_message:`、`ak:key_event:`、`ak:moderation_queue_item:`、`ak:request:`、`ak:transaction:`、`ak:franking_proof:`）。
- CRDT lattice 字段使用 `lattice`，枚举值使用 snake_case（如 `or_set`、`mv_register`、`cas_register`、`ordered_log`）。新增 lattice 枚举不得使用 kebab-case，且必须先完成 join、op schema、profile gate 与 conformance vector 闭包。
- Event kind 动词使用动词原形表达 reducer 动作（如 `authorize`、`revoke`、`rotate`、`tombstone`）；只有纯状态通告或外部标准名有明确理由时才可使用过去分词。**过去分词形态 MUST 逐条登记**（`event-kind-registry.json` 的 `verb_form: "past_participle"` 加理由），不得凭"读起来像通告"自行选用。v1 已登记的过去分词 kind 与其理由：

  | kind | 理由 |
  | --- | --- |
  | `ak.audit.accessed` | 纯审计通告：记录"已被访问"这一既成事实，无 reducer 动作语义。 |
  | `ak.capability.derived` | 纯派生通告：记录 grant 派生结果，派生动作本身由 `ak.capability.grant` 承担。 |
  | `ak.mls.commit_failed` | 外部结果通告：MLS commit 失败是 RFC 9420 处理结果，不是 Arkret reducer 动作。 |
  | `ak.contact.requested` / `.accepted` / `.rejected` | contact round 的三个终态通告；round 推进由 source service 的 slot CAS 承担，Event 只广播既成状态。 |
  | `ak.direct_conversation.bound` | founding unit 完成后的绑定事实通告。 |

- **Facet 值设置事件的命名形态（normative）**：写入单个 Realm 配置切面的 event kind 使用**裸名词形态** `ak.<scope>.<facet>`（如 `ak.realm.join_rule`、`ak.realm.history_visibility`、`ak.member.state`、`ak.call.state`），不追加 `.set`。`.set` 后缀**只保留**给两种情形：(a) 需要与同名 patch 路径区分（`ak.<kind>.stage.set` 对应 `stage` 字段，而 `ak.<kind>.update` 的 patch 路径 MUST NOT 触及 `stage`）；(b) 需要独立 capability 切分（`ak.strand.watch.set` / `ak.policy.set` / `ak.account_data.set` / `ak.rsvp.set`）。两种形态都是 canonical，选择依据 MUST 是上述判据而非作者偏好；新增 facet event 默认取裸名词形态。
- Capability action 命名约定：
  - **`ak.<entity>.<verb>` 是默认形态**，对应 `target_event_kinds` 中的一个或多个 reducer-input event kind。新增 action 默认 MUST 与被授权 event kind 同名；只有 [`authz/capabilities.md` §5.0](../authz/capabilities.md#50-action--event-kind-偏离类别normative-reference) 登记的偏离类别允许不同名。授权、IAM 工具、SDK 生成和 audit 解析 MUST 读取 capability-action-registry 的 `target_event_kinds`，不得从 action 字符串拆解推断 event kind。
  - **通用 `ak.object.<verb>`**（如 `ak.object.read` / `ak.object.archive` / `ak.object.restore` / `ak.object.stage.set`) 只允许在 Realm-wide admin 或跨实体审计 grant 中使用 (`match_scope` 不限定单一实体 ID); 对单一实体的常规授权 MUST 使用专属 `ak.<entity>.<verb>` (例如 `ak.strand.archive`)。这是为了让 grant author 在最小作用域内表达意图, 同时保留 admin 路径使用通用 action 的能力。
  - **后缀 `.own` / `.others`**: 不带后缀的 action 默认作用域不限定 "creator = grantee"; 加 `.own` 表示 "仅 actor 自己创建的对象" (例如 `ak.message.revise.own`, `ak.message.redact.own`); 加 `.others` 表示 "允许操作他人创建的对象", 通常 risk_tier=high。三种形态 MUST 在 capability-action-registry 中分别登记, 不得当作通配等价。历史命名 `manage_others` 已收敛为 `.others` 后缀（例如 `ak.strand.watch.set.others`）。

#### 2.0.1 全域命名判据（normative）

- <!-- rule_id: NC-BOOL-001 --> **R1 布尔许可与义务**：许可字段 MUST 使用 `<axis>_allowed`，强制义务 MUST 使用 `<axis>_required`；wire boolean MUST NOT 使用 `allow_*`、`require_*`、`requires_*`、`deny_*`、`force_*` 或负极性 `no_*` / `disallow_*`。`include_*` 只用于请求侧投影开关；`*_present` 只用于 fixture/诊断，或逐路径登记的不回显原材料审计摘要。
- <!-- rule_id: NC-COUNT-001 --> **R2 计数与长度**：元素个数 MUST 使用 `_count`，字节数 MUST 使用 `_bytes`，字符/码位数 MUST 使用 `_chars` / `_code_points`；Arkret wire、registry 语义字段与 fixture 断言 MUST NOT 使用 `_len`、`_length` 或 `_size`。`cardinality` 只用于 registry 的关系基数元数据。
- <!-- rule_id: NC-ENUM-001 --> **R3 符号枚举值**：Arkret 自有符号型枚举 MUST 使用 snake_case。只有外部规范定义了该字面值且 Arkret 必须逐字节往返时才可例外，并须登记外部章节/codepoint；数值区间、URI 与 media type 按各自词法。
- <!-- rule_id: NC-TYPE-001 --> **R4 类型名**：JSON Schema `$defs` 键 MUST 使用 snake_case；OpenAPI schema component 与规范自有的概念类型名 MUST 使用 PascalCase。PascalCase 中的缩写 MUST 按普通单词折叠大小写（例如 `CbaProofBundle`、`MlsGovernanceProofBundle`、`DidOperationSubmitOutcome`），不得写成连续全大写片段（例如 `CBA` + `ProofBundle`、`MLS…`、`DID…`）；外部标准要求逐字引用的类型名不在此改写。承担结构包装角色的末词只能是 `RequestBody`、`Outcome`、`View`、`Row`、`List`、`Envelope`、`Ref`、`Problem`；领域主语不受包装词封闭表约束。`service-operation-dtos.schema.json` 作为 OpenAPI DTO 镜像是已登记结构例外。
- <!-- rule_id: NC-CODE-001 --> **R5 机器原因码**：机器可枚举原因 MUST 使用 `reason_code` / `<domain>_reason_code`，协议标准错误码 MUST 使用 `error_code`；`failure_code` / `rejection_code` 等中间形态禁止。
- <!-- rule_id: NC-EVIDENCE-001 --> **R6 证据材料名词**：`proof` 是可独立验证的密码学命题材料；`attestation` 是第三方对范围/状态的签发断言；`receipt` 是请求状态回执；`witness` 是背书角色；`commitment` 是集合/树承诺；`transcript` 是签名/KDF 的规范输入。`evidence` 仅用于可容纳至少两类上述材料的多态容器。
- <!-- rule_id: NC-ARTIFACT-001 --> **R7 artifact 文件与 provenance**：artifact 文件名 MUST 为 kebab-case。类别词按数据形态使用：`registry`、`table`、`graph`、`report`、`index`、`digests`、`fixture`、`manifest`、`probes`；provenance 由真实数据流决定，canonical artifact 使用 `source_of_truth: true`，派生 artifact 使用 `source_of_truth: false` 且声明非空 `generated_from` / `generated_by`。
- <!-- rule_id: NC-SET-001 --> **R8 集合前缀**：allowlist/denylist array/set 的唯一反义词对是 `allowed_` / `denied_`；`permitted_` / `forbidden_` / `blocked_` / `banned_` 禁止用于这类集合。scope 差异 MUST 进入 role prefix；`supported_`、`accepted_`、`advertised_`、`declared_` 分别表示实现能力、运行时接受、对外通告、profile 声明，不得同域混用。
- <!-- rule_id: NC-HASH-001 --> **既有 hash 词汇判据**：`_hash` / `_hashes`、`hash_profile`、`hash_algorithm` 在 Arkret wire 中禁止。本判据同时适用于 **Arkret 自有类型名**（JSON Schema `$defs` 键与规范概念类型名）：承载自描述摘要的 canonical 类型名是 `digest`，MUST NOT 命名为 `hash`——否则规则会在同一份文档里既禁止又使用同一个词。RFC 9420 / did:webvh / Matrix `m.key.verification` 等逐字面外部字段只按登记的精确路径 + JSON Pointer 保留，不得使用按名全局白名单。
- <!-- rule_id: NC-CLASSIFICATION-001 --> **四轴分类后缀**：`kind` / `type` / `class` / `tier` 的逐字段许可、闭集与异轴声明由 [`classification-field-registry.json`](../../artifacts/registry/classification-field-registry.json) 唯一登记，轴级判据表只引用该 registry，不复制条目。

### 2.1 Identifier 字段命名约定（normative）

本节适用所有持有 protocol identifier、DID material 或 reference material 的 wire 字段。字段名只表达 **value category**，不表达"硬归属 vs 软导航"、权限传播、同步传播、retention 级联或 E2EE key 级联。后者 MUST 由 role prefix、JSON Schema `description` 和对象专属章节共同定义。

#### 2.1.1 `_id`

`_id` 用于单一、具体、已在 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 登记的 protocol kind，或本协议把 DID 当作责任主体 ID 使用的字段。

形式：

```text
id
<kind>_id
<role>_<kind>_id
expected_<role>_<kind>_id
```

规则：

- canonical materialized object 自身 primary identity 字段 MUST 使用 `id`，不得写成 `strand_id` / `message_id` / `actor_profile_id` 等带对象名前缀的字段。Actor / user-facing identity 在 v1 中由 Actor Profile 表达：Profile 对象自身仍使用 `id`，其授权主体 DID 另用 `principal_id`。
- Snapshot manifest 自身也使用 `id`；`snapshot_ref` 只在其他对象、chunk payload、challenge 或 API hint 指向该 manifest 时使用。
- Event Envelope、Receipt、Attestation、Key Backup、Applet 等协议 artifact 或非通用 materialized object MAY 使用 `<artifact>_id` 作为自身标识（例如 `event_id`、`receipt_id`、`attestation_id`、`backup_id`、`applet_id`），因为这些对象经常与 `realm_id`、`actor_id`、`policy_id`、`device_id` 等并列并进入签名 transcript，需要在混合上下文中消歧。该例外不得反向用于 Realm / Space / Strand / Message / Morph / Relation / View / Policy / Actor Profile 等普通 canonical object。
- 单一具体 kind MUST 在字段名中出现 kind slug，例如 `space_id`、`parent_space_id`、`default_realm_id`、`scope_circle_id`、`policy_id`、`retention_policy_id`。
- protocol responsibility subject 使用 `_id`，即使 wire value 是 DID，例如 `actor_id`、`principal_id`、`subject_id`、`agent_id`、`controller_id`、`watcher_actor_id`。角色词是限定词时不得再插入额外的 `principal` 限定词；`principal_id` 本身以 principal 为中心词，继续保留。
- 上述稳定 principal / service identity 字段在 v1 承载 `did_core_id`：`ak:did_core:<method>:<core>`。需要实际解析 DID 时另用 `full_id`；不得因字段以 `_id` 结尾而把当前完整 DID 存入业务主键。
- Event payload 若写入某个 materialized object / projection 字段的值，payload 字段名 MUST 与该物化字段同名。操作目标、CAS expected head、audit target、selector target 等事件操作角色 MAY 加 role prefix，例如 `space_id` 与 `expected_parent_space_id`。

#### 2.1.2 `_ref` / `_refs`

`_ref` / `_refs` 只用于 reference material，而不是单一具体 object kind 字段。允许类别：

- Event / Seal / Cell / Snapshot / Receipt 等因果、finality、state 或证明引用：`prev_refs`、`seal_ref`、`cell_ref`、`snapshot_ref`。
- Blob 或 content-addressed 引用：`blob_ref`、`avatar_blob_ref`、`thumbnail_blob_ref`。
- Schema / Profile / Feature 引用：`schema_refs`、`profile_ref`、`feature_ref`。
- Proof / evidence / transcript 引用：`evidence_ref`、`proof_ref`、`service_acceptance_ref`、`policy_event_ref`。
- Profile-scoped typed reference 或 profile-defined 非 UUID form：例如 `mls_group_ref` 使用 `ak:mls:<profile>:<profile_id>`，由 E2EE profile 校验。它故意不同于 MLS 标准 payload 内的原始 `mls_group_id`。
- Polymorphic reference：字段允许多个 protocol kind、DID、content-addressed value 或 hash 形态时使用 `_ref`，例如 `target_ref`、`object_ref`、Relation 的 `from_ref` / `to_ref`。

新增字段若只允许一个具体 canonical materialized object kind，且不是上述因果、proof、schema/profile、content-addressed 或 profile-scoped reference，MUST 使用 `_id` 而不是 `_ref`。

#### 2.1.3 Service identity 与 `_did`

Service identity 字段统一使用 `service_id` / `<role>_service_id`；例如 `service_id`、`recipient_service_id`、`source_service_id`、`destination_service_id`、`verification_service_id`。这些稳定引用承载 service `did_core_id`，并与 `actor_id`、`principal_id`、`controller_id` 等责任主体命名保持一致。schema description MUST 明确其承载 `ak:did_core:<method>:<core>`，不得描述成可直接解析 endpoint 的完整 DID。

`_did` 仅保留给不属于 service identity 字段族、且必须强调 DID ecosystem 原始术语的 material，例如 pairwise DID 或 operator DID。例：`pairwise_did`、`operator_principal_id`、`push_gateway_service_id`。v1 不再为跨 DID continuity 定义专用 `_did` 字段。`principal_server_service_id` 是既有 Principal Server 专名，不作为 `service_id` 的别名，也不受 service identity 字段族规则影响。

普通协议责任主体不得使用 `_did`；使用 `actor_id`、`principal_id`、`subject_id`、`recipient_principal_id`、`agent_id`、`audit_service_actor_id` 等 `_id` 字段。

`verification_method` 保留 W3C DID 规范字段名，承载 DID URL，不改名为 `_id` 或 `_did`。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。公共字段的 canonical 排列顺序以 §3.2 为单一真源（content → lifecycle → audit）：即 `state`、`state_changed_at`、`stage`、`stage_changed_at` 等 lifecycle 簇 MUST 排在 `created_by`、`created_at`、`updated_by`、`updated_at` 等 audit 簇之前（与全部已实现 schema 一致）。对象专属字段 MAY 插入在 scope / lifecycle / body 分组中，但同名公共字段的相对顺序 MUST 与 §3.2 和 `tools/field-order-rules.json` 保持一致。本节字段表（§3.1）仅为概念性字段清单，不作为顺序真源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`ak:strand:` 即 strand 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `schema` | yes | `string` | SHOULD 是 `ak.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `realm_id` | conditional | `id:realm` | Realm 外对象可省略。 | 所属 Realm。 |
| `created_by` | conditional | `did_core_id` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `did_core_id` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST be no earlier than `created_at`。 | 最近更新时间。 |
| `state_changed_at` | R when state≠active | `timestamp` | **Reducer-derived,actor 不可信:** 所有具有 `state` 字段的对象（Circle / Space / Strand / Message / Morph / Relation / View）当 `state != active` 时 MUST 写入（逐对象必填性矩阵见 §3.1，统一标记 `R when state≠active`）;reducer **MUST** 忽略任何 wire payload 中 actor-supplied 的 `state_changed_at` 值。权威值为 `max(Event.created_at, first_covering_sealed_at)`；`first_covering_sealed_at` 是覆盖该 Move 的全部 accepted Seal 中 `sealed_at` 的最小值，data-plane Event 或尚未被 Seal 覆盖时只取 `created_at`。MUST be no earlier than `created_at`,MUST ≤ `updated_at`(当后者存在时)。 | 最近一次 state 转换时间。 |
| `stage` | conditional | `enum` | 适用对象自己的 schema 声明本字段时可用（v1 适用对象 = Strand / Morph，详见 §5.3）；二者在通用 schema 中均可省略，具体 profile MAY 收紧为必填。取值为 §5.3 的协议级 8 值枚举。**禁止与 `state` 混用**：`stage` 表达业务进度，`state` 表达物理生命周期，两者正交。Strand 的 `metadata.fields.stage` / `metadata.fields.lifecycle` / `metadata.fields.progress_state` / `metadata.fields.stage_reason`，以及 Morph 的 `fields.stage` / `fields.lifecycle` / `fields.progress_state` / `fields.stage_reason` 等同名/近名 wire 路径 MUST 被拒绝。stage 变更的"为什么"解释通过 discussion track Message 表达，不在对象字段中携带。 | 业务进度阶段。 |
| `stage_changed_at` | conditional | `timestamp` | **Reducer-derived，actor 不可信：** 适用对象 `stage` 字段每次实际变更时 MUST 写入；Strand 缺少 `stage` 时 MUST NOT 单独出现。reducer **MUST** 忽略 wire payload 的 actor-supplied 值，以触发该 transition 的 `ak.<kind>.stage.set` event 的 `created_at` 覆盖写入。MUST be no earlier than `created_at`。same-value self-transition（stage 值未变）reducer MUST NOT 更新本字段。 | 最近一次 stage 转换时间。 |
| `labels` | no | `array<string>` | SHOULD 小写短标签。 | 用户或系统标签。 |
| `fields` | no | `object` | 字段 schema 由对象类型自身的 `schema_refs` 决定。 | 扩展字段；v1 唯一标准扩展容器。 |

对象种类由 `id` 的 typed prefix（`ak:strand:` / `ak:realm:` / ...）唯一决定；扩展字段统一走 `fields`，由对象 `schema_refs` 约束。Event Envelope 不是 Materialized Object，事件类型由顶层 `kind` 表达。

### 3.0.1 Size 字段命名

表示字节数的字段 MUST 使用 `_bytes` 后缀，例如 `size_bytes`、`max_total_blob_bytes`、`canonical_payload_bytes`。不得新增裸 `size` 表示字节数；Blob metadata、Media metadata、Content Block descriptor 与 Snapshot chunk descriptor 均使用 `size_bytes`。

### 3.0.2 Duration 字段命名

表示机器处理时长的新增 wire 字段 SHOULD 使用整数加显式单位后缀，优先选择 `_ms` 或 `_seconds`，例如 `retry_after_ms`、`ttl_seconds`、`refresh_lead_seconds`。字段名不得只靠 description 表达单位。

需要 profile author 直接书写的人类可读策略时长 MUST 使用 ISO 8601 duration 字符串（如 `PT24H`、`P30D`、`P1Y`），并以统一 pattern `^P(?:[0-9]+Y)?(?:[0-9]+M)?(?:[0-9]+W)?(?:[0-9]+D)?(?:T(?:[0-9]+H)?(?:[0-9]+M)?(?:[0-9]+S)?)?$` 约束。v1 内**只有这一种 duration 字符串格式**：自造的 compact duration mini-DSL（如 `^[0-9]+(ms|s|m|h|d)$`）与无 pattern 的裸 duration string MUST NOT 出现在 wire 字段中。

时长名词按语义区分：`ttl` 表示对象或凭据存活期；`timeout` 表示等待无响应后的放弃；`window` 表示允许动作发生的相对窗口；`period` 表示周期性轮换/复发；`cooldown` 表示拒绝或关闭后的最短重试间隔；`age` / `staleness` 表示已存在材料相对当前时间的新鲜度上限。

**同一时长名词的单位选择（normative）**：整数时长字段的单位由**时间尺度**唯一决定，不由作者偏好决定，同一名词 MUST NOT 在同一尺度内并存两种单位。

| 尺度 | 单位后缀 | 适用 | v1 实例 |
| --- | --- | --- | --- |
| 亚分钟瞬时信号（presence / typing / 交互式配对等 ephemeral rail 计时器） | `_ms` | 需要毫秒级精度或与前端定时器直接对应 | `ttl_ms`（signal-presence / signal-typing，上限 30000）、`pairing_ttl_ms` |
| 策略、凭据、缓存与批次有效期（分钟以上） | `_seconds` | 人类可读、以秒为最小有意义粒度 | `ttl_seconds`、`max_ttl_seconds`、`cache_ttl_seconds`、`default_ttl_seconds`、`batch_completion_ttl_seconds`、`blob_presign_max_ttl_seconds`、`effective_ttl_seconds` |

因此 `ttl_ms` 与 `ttl_seconds` 并存不是漂移，而是尺度分工；新增 TTL 字段 MUST 先按本表定位尺度再选后缀，
MUST NOT 在同一尺度内引入第二种单位。需要 profile author 直接书写的策略时长仍按本节上文使用 ISO 8601
duration 字符串（例如 join policy 的 `application_ttl`），不受本表的整数单位约束。

### 3.0.3 Slug 字段命名

对象自身的 canonical slug 字段 MUST 使用裸名 `slug`；创建、更新或投影该对象且只存在一个 slug 语义的 DTO MUST 与物化字段同名。其它对象、claim、mention metadata、selector 参数或混合上下文引用该对象的 slug 时，MUST 使用 `<entity>_slug` 或带 role / time qualifier 的名称，例如 `agent_slug`、`agent_slug_at_time`。该规则与 §2.1 中对象自身 `id`、外部引用 `<entity>_id` 的区分一致；不得因为外部 selector claim 使用 `agent_slug`，就把 Agent 自身字段改名为 `agent_slug`。

### 3.1 字段 × 对象适用性矩阵（normative reference）

下表把 §3 列出的公共字段按对象 kind 标注必填 / 可选 / 不适用。SDK / projection / fixture 生成器 MUST 严格按此表验证，不得给"不适用"格写值；新增对象 kind 时 MUST 先在本表落表再发布 schema。术语：`Y` = 必填；`O` = 可选；`R` = reducer-derived（actor MUST NOT 写）；`—` = 不适用（schema MUST 拒绝该字段）。

字段按用途分四组：

- **Universal**：所有 durable canonical object 都用。
- **Authorship**：协作图对象记录创建 / 更新主体；与 reducer 派生关系紧密。
- **Lifecycle**：物理生命周期（active / archived / tombstoned / ...），与 `ak.<kind>.archive` / `restore` / `tombstone` 系列 event 配对。
- **Progress**：业务进度（v1 仅 Strand / Morph），与 `ak.<kind>.stage.set` event 配对。

| 字段 | 组 | Realm | Circle | Space | Strand | Message | Morph | Relation | View | Policy | Blob meta | Capability Grant | Invite | Read Cursor | Notification | Actor Profile | Sidecar |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `id` | Universal | Y | Y | Y | Y | Y | Y | Y | Y | Y | —（见 `blob_ref`，§3.2 第 2 类） | Y | Y | Y | Y | Y | Y |
| `schema` | Universal | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y |
| `realm_id` | Universal | —（Realm 自身即边界，无 `realm_id` 字段，schema 拒绝） | Y | Y | Y | Y | Y | Y | Y | O | O | O | Y | Y | O | O | Y |
| `created_by` | Authorship | Y | Y | Y | Y | Y (reducer-derived from Event `actor_id`) | Y | Y | Y | Y | Y | — (see `issuer`) | — (see `inviter`) | — (see `actor_id`) | — (see `actor_id`) | — (see `principal_id`) | — (see `controller_id`，见附注) |
| `created_at` | Authorship | Y | Y | Y | Y | Y | Y | Y | Y | Y | Y | —（见 `issued_at`，§3.2） | Y | —（仅 `updated_at`，见 §3.2） | Y | Y | Y |
| `updated_by` | Authorship | O | O | O | O | O | O | O | O | O | O | O | O | — | — | O | — |
| `updated_at` | Authorship | O | O | O | O | O | O | O | O | O | O | O | O | Y | O | O | O |
| `state` | Lifecycle | —（Realm 终态由 lifecycle facet 表达，schema 拒绝） | Y | O | O | Y | O | O | O | — | — | — | Y（流程状态轴，见附注） | — | Y（actor-private 处理轴，见附注） | — (see `status`，mirrors account status) | Y（reducer 派生轴，含 `suspended`，见附注） |
| `state_changed_at` | Lifecycle | —（Realm 终态由 lifecycle facet 表达，schema 拒绝） | R when state≠active | R when state≠active | R when state≠active | R when state≠active | R when state≠active | R when state≠active | R when state≠active | — | — | — | — | — | — | — | R when state≠active |
| `stage` | Progress | — | — | — | O | — | O | — | — | — | — | — | — | — | — | — | — |
| `stage_changed_at` | Progress | — | — | — | R per `ak.strand.stage.set` | — | R per `ak.morph.stage.set` | — | — | — | — | — | — | — | — | — | — |
| `labels` | Universal | — | — | O | — | — | — | — | — | — | — | — | — | — | — | — | — |
| `fields` / `metadata.fields` | Universal | O | — | O | O (`metadata.fields`) | O (`metadata.fields`) | O (主要载荷) | O | — | — | — | — | — | — | — | — (see `profile_fields`) | — |

附注：

- Realm 使用通用 `created_by` 字段；其额外语义是 Realm create event 的 authorizing principal，并作为 genesis member bootstrap 主体（见 §4.1 / §4.2 与 [`realm-and-space.md` §2.5](./realm-and-space.md#25-akrealmcreate-reducer-bootstrapnormative)）。
- Capability Grant / Invite / Read Cursor / Notification / Actor Profile 用领域特有的 authorship 字段（`issuer` / `inviter` / `actor_id` / `principal_id`），各对象 schema 内部独立约束；本表对应格写"—"是因为它们不使用通用 `created_by`，并不表示没有创建主体记录。
- Read Cursor / Notification 是 actor-private 状态：`realm_id` 在 Read Cursor 上必填（`read-cursor.schema.json` 列入 `required[]`），在 Notification 上可选（允许 actor-scoped 视图省略）；`updated_by` 均不适用——这些对象由系统派生或 actor 本人推进。
- **`state_changed_at` reducer-derived 总括 MUST（单一真源）**：任何承载物理 lifecycle `state` 轴的对象（Circle / Space / Strand / Message / Morph / Relation / View）在 `state != active` 时 MUST 写入 `state_changed_at`；该字段一律 **reducer-derived，actor MUST NOT 携带**，reducer 强制使用 §3 定义的 `max(Event.created_at, min(covering Seal.sealed_at))`，actor wire 值 MUST 被忽略（详见 §5.1）。各对象专属文件的 `state_changed_at` 行不必重复声明该 reducer-derived 约束，以本条为权威。本条不适用于 Notification / Invite 的 `state` 轴——它们由 Arkret 推进但不属于 §5.1 通用 lifecycle 状态机（见下条）。
- **`state` 必填性差异（Circle=Y vs Space/Strand/Morph=O）**：Circle 的 `state` 为必填（`circle.schema.json` 列入 `required[]`），而 Space / Strand / Morph 为可选（缺省语义 `active`）。理由：Circle 是独立的 scoped event boundary，其 lifecycle（`active` / `archived` / `tombstoned`）直接决定该 scope 内对象能否继续写入与投递裁剪（见 [`circle.md` §9.2](./circle.md)），故 reducer / projection 必须能从 Circle 对象直接读出确定 state，不容许 "缺省即 active" 的隐式解释带来 scope 可写性歧义；Space / Strand / Morph 的缺省 `active` 不影响其它对象的 scope 边界，省略时按 `active` 解释是安全且省 wire 的取舍。两类对象的 `state` 转换真源仍统一为 §5.1 的 reducer-input lifecycle event，必填性差异只影响 wire 上是否允许省略该字段。
- Notification 的 `state` 是 schema required 字段（enum `unread / read / dismissed / archived`）：它承载 actor-private 的通知处理轴；按 §5 的所有权判据这是 `state` 的正确用法（轴由 Arkret 推进），**不是命名例外**，但它不落入 §5.1 的通用 lifecycle 状态机，且 Notification 无 `state_changed_at`。Invite 的 `state` 同为 schema required，承载邀请流程状态轴（见 [`governance-objects.md` §5](./governance-objects.md)），同理不落入 §5.1 状态机。
- `stage_changed_at` 仅 Strand / Morph 适用，且仅当 `stage` 存在并真正发生 stage 变更时写入；同值 self-transition reducer MUST NOT 更新（详见 §3 与 §5.3）。
- `labels` 仅适用于 Space。Realm / Circle / Strand / Message / Morph / Relation / View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification / Actor Profile 的标签语义由各自的 schema-specific 字段（如 `tags`、`reason`、`category`）或扩展容器承担，避免与 Space labels 投影冲突。
- `fields` 是协作对象的扩展容器；Strand / Message 的用户可读扩展放入 `metadata.fields` 或 `encrypted_metadata`，不得作为顶层 `fields`；View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification 不暴露开放扩展容器。
- **View 终态复用 update**：共享 View 通过 `ak.view.update` patch `state="tombstoned"` 进入 durable terminal state；不另注册平行的 `ak.view.tombstone` event kind。Reducer 派生 `state_changed_at`，终态后的 update / reconcile 用 `view_already_terminal` 拒绝；见 [`views.md` §3.1](./views.md)。
- **Realm 无 materialized `state` 字段**：Realm 的 `archived` / `frozen` / `tombstoned` / `destroyed` 由 `ak.component.realm.*` lifecycle facet 表达，`realm.schema.json` 拒绝 `state` / `state_changed_at`。Projection MAY 把 `ak.realm.tombstone` 与 `ak.realm.destroy` 均显示为 `realm_terminal_state`，并用 `terminal_kind=tombstone|destroy` 或同等字段区分 successor 迁移与永久退役；不得把该 projection 状态写回 Realm 对象。
- **Agent Sidecar（`ak:sidecar:`）authorship 与 state 特例**：Sidecar 不使用通用 `created_by` / `updated_by`；其 authorship 是 controller（`controller_id`，create-locked、必为父 Realm active member），create / update 主体由 reducer 从 controller account / Realm membership / lifecycle frontier 派生（`agent-sidecar.schema.json` 无 `created_by` / `updated_by`）。本表对应格写"—"与 Capability Grant / Invite 同理——不表示没有创建主体记录。Sidecar 的 `state`（`active` / `suspended` / `tombstoned`）是**reducer-derived 特例生命周期轴**：`suspended` 不属于 §5 通用物理 lifecycle 枚举（见 §5 附注），无 actor-authored `ak.sidecar.update/archive/restore`；`state_changed_at` 取触发派生转换的已接受 Event timestamp。合法 / 非法迁移封闭表见 [`sidecar.md` §7](./sidecar.md)。Sidecar 无 `labels` / `stage` / `stage_changed_at` / 顶层 `fields` 扩展容器。

### 3.2 字段声明 / 展示顺序约定（normative reference）

本表是 §3 / §3.1 之外的**顺序**约定：它不改变任何字段的必填性，只规定 schema `properties` 的声明顺序与 SDK / 文档生成器的展示顺序，使不同对象族呈现统一字段簇。本表为各 schema 的 canonical property ordering 真源；§3.1 的概念性字段表不应被当作顺序真源。

按结构角色把对象分三类，各自的顺序如下：

1. **canonical materialized object**（Realm / Circle / Space / Strand / Message / Morph / Relation / View / Policy / Actor Profile 等）字段簇顺序 SHOULD 为：
   1. identity：`id`、`schema`
   2. scope / container：`realm_id`、`space_id`、`strand_id`、其它 parent refs（如 `parent_space_id`、`scope_circle_id`）
   3. object discriminator / 引用：`kind`、`rank`、`schema_refs`
   4. content / config：`title`、`metadata`、`fields`、policy / config 字段
   5. lifecycle：`state`、`state_changed_at`、`stage`、`stage_changed_at`
   6. audit：`created_by`、`created_at`、`updated_by`、`updated_at`
   7. extension / profile 容器（若未在第 4 组出现）
2. **protocol artifact / proof**（Blob meta、attestation、receipt 等）：`schema`、`<artifact>_id`、scope refs、issuer / subject、artifact body、validity（`not_before`、`expires_at`）、签发 / 审计字段。这类对象 MAY 不含顶层 `id`（使用 `<artifact>_id`），不视为遗漏。
3. **private projection / process artifact**（Read Cursor、Capability Grant、Notification 等）：projection id / scope、grant / body、validity、lifecycle update（`updated_by`、`updated_at`）、revocation（`revoked_by`、`revoked_at`）。

排序硬规则（对全部三类生效，可被 lint 机器校验）：

- `created_at` MUST 排在 `updated_at` 之前；`created_by` MUST 排在 `created_at` 之前；`updated_by` MUST 排在 `updated_at` 之前。
- `state_changed_at` MUST 紧跟 `state`；`stage_changed_at` MUST 紧跟 `stage`。
- 任何同时承载 validity 字段簇（`not_before` / `issued_at` / `effective_at` / `expires_at`）与 audit 字段簇（`created_by` / `created_at` / `updated_*`）的对象，validity 簇 MUST 整体排在 audit 簇之前（即 `expires_at` 等有效期字段 MUST 排在 `created_by` / `created_at` 之前）。validity 簇内部 MUST 满足：`not_before` MUST 排在 `expires_at` 之前、`issued_at` MUST 排在 `expires_at` 之前（签发 / 生效下界先于有效期上界）；`not_before` 与 `issued_at` 同时存在时二者相对顺序不强制，按对象语义择一在前。以上由 `tools/field-order-rules.json` 的 `cluster_precedence` + `ordered_groups.validity` 经 `check_field_order` 强制。
- 开放扩展容器（`fields` / `metadata`）MUST 落在 content / config 区，紧邻对象内容字段，MUST NOT 混入 audit 字段簇。对 Realm 这类把 `fields` 置于审计字段之前的配置根对象，按本节"对象族例外"声明即可。

对象族例外 MUST 在对应 schema description 或本节列明。Realm 是配置根对象：`title` / `summary` / `security_class` 可在 `trust_domain` / `schema_refs` 之前展示，以便管理端先呈现人类可读身份和安全等级；`trust_domain` 仍是 create-locked replay boundary，`schema_refs` 仍是字段验证引用，不改变其语义。

**role ordering guidance（说明性，非强制改 schema）**：identity / scope / subject role 字段（`realm_id` / `actor_id` / `event_id` 等）的相对顺序按对象语义选择，并 MUST 在对应 schema description 或本节显式化例外——event 主体对象 MAY 采用 event-first（`event_id` 先，如 `event-envelope.schema.json` 的 `event_id` → `realm_id` → `actor_id`）；receipt / projection 类 MAY 采用 scope-first（`realm_id` 先，如 `read-receipt.schema.json` 的 `realm_id` → `actor_id` → `event_id`）；actor 私有 / actor 维度对象 MAY 采用 actor-first（`actor_id` 先，如 `notification.schema.json` 的 `actor_id` → `realm_id`）。这三种排列是依对象语义的有意例外、非漂移；审查与 lint MUST NOT 据单一全局 role 顺序判错。本节的硬排序规则（`created_*` / `updated_*`、`state_changed_at` / `stage_changed_at` 紧邻、validity 字段簇顺序）仍对全部三类生效，不受本 guidance 影响。

**过程型 / private object 例外**：第 3 类对象（见本节上方 private projection / process artifact 分类）不套用 canonical materialized object 的 audit 字段簇规则——

- **Read Cursor** 是仅更新态 projection，必填 `updated_at` 而**无** `created_at`；这是有意设计，不是字段遗漏。读者 / 生成器 MUST NOT 据 §3.1 推断它缺 `created_at`。
- **Capability Grant** 使用 grant 语义字段（签发 / 撤销相关）表达生命周期；其"创建时间"语义由 `issued_at`（而非通用 `created_at`）承载，retention / audit / 排序查询 MUST 使用 grant 自身的 `issued_at` / `expires_at` / `revoked_at`，不要回退到通用 `created_at`。
- **Notification** 同属 actor-private projection，不暴露开放扩展容器（见 §3.1 附注）。

> 说明：§3.2 排序硬规则已由 `tools/lint_artifacts.py` 的 `check_field_order` 自动校验——递归全部 `artifacts/schemas/*.schema.json` 的每个 `properties` 对象，强制 `created_by < created_at < updated_at`、`updated_by < updated_at`，以及 `state_changed_at` / `stage_changed_at` 紧邻 `state` / `stage`。规则按字段存在性条件触发，故 Read Cursor（无 `created_at`）、Capability Grant（用 `issued_at`）等有意例外天然不触发，无需白名单。

## 4. 主体引用字段交叉对照

### 4.1 DID 适用边界

主体标识分为两种强类型：

| 类型 | wire 形态 | 用途 |
| --- | --- | --- |
| `did_core_id` | `ak:did_core:<method>:<core>` | Event、principal / service reference、membership、capability、业务数据库关联与相等判断。 |
| `full_id` | 标准 bare DID，例如 `did:webvh:<scid>:<host>` | 注册、DID resolution、method-native operation、DID Document / history 验证。 |

`full_id ≅ did_core_id + method-specific resolution` 只是 adapter 语义，不是字符串拼接格式。只有已登记 DID method adapter 可以从 `full_id` 投影 `did_core_id`；普通业务代码 MUST NOT 自行拆解或反向构造。一个 `full_id` 投影到的 `did_core_id` 必须唯一。DID URL 不属于 `full_id`：`verification_method` 等 DID URL 必须在验证 `full_id` 后由相同 adapter 处理，禁止把 fragment 直接拼到 `did_core_id`。

`did_core_id` 是 Arkret 的稳定主体标识，`full_id` 是其当前 DID resolution material；二者都不是普通协作对象 ID。标准协作对象（Realm / Circle / Space /
Strand / Message / Morph / Relation / View / Policy / Grant / Invite / Blob 等）MUST 使用
`ak:<kind>:` typed ID 作为对象 ID；设备也不是 actor 主体，其标识是
`device_id`（`ak:device:<uuidv7>`），没有设备 DID。

DID / DID URL 字段总表、条件性 polymorphic ref、明确不是 DID 的 `*_id`，以及“普通业务只把
DID 当作身份锚点、仅在封闭触发条件下验证 DID 控制权”的规则，统一见
[`../identity/did-usage-and-verification.md`](../identity/did-usage-and-verification.md)。
本节不复制总表，避免字段新增后出现两份不一致清单。

仅作为内容、容器、投影或关系事实存在的对象，不需要也不得发明独立 DID；它们通过 typed ID
被引用，通过 `created_by` / `updated_by` 等字段关联到主体 `did_core_id`。字段里出现完整 DID 只声明
value category，不会自动触发 DID Document 解析或在线验证。

### 4.2 主体引用字段

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、Read Cursor、Notification | 直接执行该 Event / 拥有该私有状态的 actor `did_core_id`（`actor_kind` 决定它是 user / agent / service 等）；普通业务按身份锚点使用，验证边界见 §4.1 的引用。 |
| `watcher_actor_id` / `target_actor_id` / `writer_actor_id` | Event payload、Audit payload | 带角色限定的 actor `did_core_id`；字段名必须说明角色，避免回退到模糊的 `actor_did`。 |
| `principal_id` | Actor Profile | Profile 对应的 principal `did_core_id`；稳定权限主体引用。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的 Event 的 `actor_id`，由 reducer 派生。Realm 的 `created_by` 还承担 genesis member bootstrap 的 authorizing principal 语义。 |
| `issuer` | Capability Grant、Identity Receipt、Handle Claim、Agent Selector Claim | 签发授权、receipt 或 claim 的主体 `did_core_id`；必须持有签发权限。 |
| `subject` | Capability Grant、Handle Claim、Agent Selector Claim | 被授权 principal `did_core_id`、selector condition，或 claim 绑定的目标 `did_core_id`。claim 层 raw subject 使用 `subject`；进入具体协议 transcript / mention / delivery candidate 后才使用 `subject_id`。 |
| `controller_subject` | Agent Selector Claim | 拥有 controller-scoped agent selector namespace 的 controller principal `did_core_id`；因处于 claim 层使用 `subject` 词汇，不使用 `controller_subject_id`。事件 mention metadata 快照才使用 `controller_subject_id`。 |
| `subject_id` | Mention reference、Handle / invite / delivery binding candidate | 当 subject 必须是具体 principal `did_core_id` 且进入可验证 transcript 时使用；generic / raw handle claim 和 agent selector claim subject 仍使用 `subject`。`MemberDeliveryBindingCandidate.subject_id` MUST equal 上游 handle claim 的 `subject`。 |
| `inviter` / `invitee` | Invite | 邀请方 / 被邀请方 `did_core_id`。 |
| `accountable_principal_ids` | Actor Profile | 该 Actor Profile 声明可问责到的一组 principal `did_core_id`（每个条目须有对应 active `ak.identity.accountability_grant` 背书）。array 形态使用 `_ids` 复数，与 agent key payload 的 scalar `accountable_principal_id` 共用同一 accountability 主体词汇；责任主体一律走 `_id` / `_ids`，不使用 `_to` 介词后缀或裸关系短语。 |
| `agent_id` / `audit_service_actor_id` | Agent key payload、Audit release evidence | agent / audit release service 作为协议责任主体时使用 `did_core_id`；承载运行或托管服务身份时另用 `service_id`。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

主体字段新增策略：

- 既定 crypto / governance 角色名词（如 `issuer`、`inviter`、`holder`、`notary`）可保留并应在 §4.3 角色名词登记索引登记（其权威定义仍在对应对象 schema / glossary / 专属章节）。新增的普通作者 / 操作者归属字段默认使用 `<verb>_by`（例如 `approved_by`、`revoked_by`），时间点使用 `<verb>_at`。
- 过程结果词汇按对象族固定（**封闭四词**，normative）：

  | 词 | 语义 | 典型载体 |
  | --- | --- | --- |
  | `outcome` | 请求 / 提交 / receipt 的完成结果，配 `outcome_reason_code` | 全部 `*_outcome` DTO、receipt 的结果字段 |
  | `result` | 执行体或 session 自身算出的运行结果 | call recording / transcript 的 `result`、SDK conformance claim |
  | `decision` | 人为或治理裁决 | moderation、appeal、join review、consent |
  | `resolution` | 名称 / 选择器 / 冲突的**解析**结果，不是过程结局 | `service_resolution`、agent selector、applet namespace conflict |

  新增相邻对象 MUST 从上表取词，不得随机换用近义词。已收敛的历史别名：
  receipt 上的 `disposition` 已并入 `outcome`；moderation / appeal 的 `verdict` 已并入 `decision`
  ——后者是为了让字段名与既有符号 `ak.moderation.decision`、`ak.moderation.appeal.decision`
  及 `moderation_decision_payload` 三层一致，而不是反过来把三个符号面改去迁就一个字段名。
  `response` / `ack` 不是独立结果词：HTTP 响应体统一走 `*_outcome`，确认类载荷按其真实语义归入上表。

### 4.3 角色名词登记索引

下表收敛 v1 已确立的 crypto / governance 角色名词，供读 spec / 评审命名时一次定位。本表是 **informative 索引**：每个角色的字段形态、约束与 normative 语义以「权威定义」列指向的 schema / glossary / 专属章节为单一真相源，本表不重复承载约束，也不得与权威定义冲突。新增 normative 文本引入主体 / 操作者归属字段时，先查本表确认是否已有既定角色名词，再按上文「主体字段新增策略」决定复用或使用 `<verb>_by`。

| 角色名词 | 类别 | 权威定义 | 角色语义 |
| --- | --- | --- | --- |
| `issuer` | id 字段（§4.2） | §4.1 / §4.2；[glossary `Capability Grant` / `Control Move`](../overview/glossary.md) | 签发 Capability Grant / Identity Receipt 或签署 DataEvent / Control Move 的主体 DID；必须持有对应签发权限。 |
| `subject` / `subject_id` | id 字段（§4.2） | §4.1 / §4.2；[glossary `Subject`](../overview/glossary.md) | Capability grant 的授予对象：`subject` 为 principal `did_core_id` 或 condition selector，`subject_id` 用于必须是具体 principal `did_core_id` 且进入可验证 transcript 的场景。 |
| `inviter` / `invitee` | id 字段（§4.2） | §4.1 / §4.2；[`governance-objects.md` §5 Invite](./governance-objects.md)；[`invite.schema.json`](../../artifacts/schemas/invite.schema.json) | 邀请方 DID / 被邀请方 DID；3PID 邀请可暂无 `invitee`，认领后必须绑定可验证主体。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。 |
| `holder` | 叙述性角色名词 | [`consent-model.md` §2.1](../identity/consent-model.md)；[`client-preferences.md`](../discovery/client-preferences.md)；[glossary `Consent`](../overview/glossary.md) | consent / blocklist / recovery share / pairwise 假名等 holder-private 状态的归属主体；只有 holder 本人或其显式授权的 controller / agent 可写。 |
| `notary` | 叙述性角色名词 | [`event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)；[glossary `Seal` / `Notary Cell`](../overview/glossary.md)；[`capabilities.md`](../authz/capabilities.md) | Seal ordering authority：对 Move frontier 签名承诺的主体；由 `notary_cell`（`cas_register + bottom=reject`）授权，冲突时触发 Realm-wide Seal pause。 |
| `witness` | 叙述性角色名词 | [glossary `Witness`](../overview/glossary.md)；[`federation.md`](../sync/federation.md)；[`operations-sync.md`](../sync/operations-sync.md)；[`identity-did.md`](../identity/identity-did.md) | 对 frontier、range completeness、DID key-log 头部或 handover frontier 签发 attestation / receipt 的受信背书主体；不替代 Event 自身签名、Seal finality 或 reducer 验证。 |
| `controller` | 叙述性角色名词 | [`identity-did.md`](../identity/identity-did.md)（DID controller proof）；[`actor.md` §3.3](./actor.md)（Native Personal Agent controller） | DID 控制主体（method history 中以 controller proof 证明控制权），或受 holder / principal 显式授权代为写入 / provision 的控制方。 |
| `publisher_id` | id 字段（§4.2） | [`extension-manifest.md`](../extensions/extension-manifest.md)；[`extension-manifest.schema.json`](../../artifacts/schemas/extension-manifest.schema.json) | 对 Extension Manifest 的 canonical digest 与完整声明负责并签发 publisher proof 的主体 DID；不得用裸 `publisher` 或 transport service identity 替代。 |

### 4.4 `agent_participation` wire 形态（normative）

Realm、Circle、Strand 的 `agent_participation` policy component 使用
`{native_agent:{reply_message,reaction_add,reaction_remove,accept_third_party_mention,act_on_behalf}}`；
controller-private selection 直接使用同一个五位 inner object。五个 boolean 全部 required，两个 object 都 closed；
任一位缺失或出现未知位均 `schema_violation`，不得默认补齐。外层 axis 为其它 actor family 保留，不同
family 使用独立 sibling key。

某层policy component整体省略时表示本层不另作声明并继承已验证父级current ceiling；一旦出现则五位必须完整。
Reducer逐层AND，同名位内层true必须蕴含父层true，放宽返回
`agent_participation_ceiling_widen`。任一required layer在本次admission应存在却missing/unknown/stale/fork时按
全deny，不按“无声明=放宽”。实际动作的 participation gate 为 target deployment safety、
Realm/Circle/Strand governance 与 Account Authority 当前 controller selection 的逐位交集；普通 capability、
session scope、membership 和 lifecycle 是并列的独立 admission 条件，不复制进 participation record；详见
[`../authz/capabilities.md` §5.4](../authz/capabilities.md)。

### 4.5 参数化 membership FSM（normative）

Realm 与 Circle membership 共用本节唯一的状态图。`initial_state=leave`，wire 枚举固定为 `invite / join / knock / leave / ban`；不存在 `none`。实例参数 `delivery_binding_rebind` 仅控制 `join -> join`：Realm 为 `true`，Circle 为 `false`。除该参数化边外，任何未列边与任何 same-state transition 均非法，MUST `failed_precondition`（`reason=invalid_membership_transition`）。

下表的 **wire event kind** 列给出承载该边的 Event kind（Realm scope）。每条边都 MUST 由已登记 kind 的 canonical reducer contract 明确派生；未登记的“reducer 隐式推进”不是合法边。

| from | to | wire event kind（Realm） | Realm guard / writer | Circle guard / writer |
| --- | --- | --- | --- | --- |
| `leave` | `invite` | `ak.invite.create`（directed 分支，条件性 `member.state` projection） | `ak.realm.join.review` 或 `ak.realm.admin` | `ak.circle.member.manage` |
| `leave` | `knock` | `ak.member.state` | target actor，且 Join Rule / Join Policy 允许 | target actor，且 `join_rule=knock` |
| `leave` | `join` | `ak.member.state`（Realm bootstrap 的 creator slot 同样走本 kind，见 [`realm-and-space.md` §2.7](realm-and-space.md)；`ak.realm.create` 自身不承载 membership 边） | target actor 通过 public/restricted gate，或 `ak.realm.admin`；Native Personal Agent carve-out 见 Realm 文档 | target actor 仅当 `join_rule=public`，否则 `ak.circle.member.manage` |
| `invite` | `join` | `ak.invite.accept` | target actor 或 `ak.realm.admin` | target actor（`ak.circle.member.add`）或 `ak.circle.member.manage` |
| `invite` | `leave` | `ak.invite.cancel` / `ak.invite.revoke`（条件性 `member.state` projection） | target actor、inviter 或 `ak.realm.admin` | target actor 或 `ak.circle.member.manage` |
| `knock` | `invite` | `ak.invite.create`（reviewer 批准后签发定向 invite） | `ak.realm.join.review` 或 `ak.realm.admin` | `ak.circle.member.manage` |
| `knock` | `join` | `ak.member.state` | `ak.realm.join.review` 或 `ak.realm.admin` | `ak.circle.member.manage` |
| `knock` | `leave` | `ak.member.state` | target actor、reviewer 或 `ak.realm.admin` | target actor 或 `ak.circle.member.manage` |
| `join` | `join` | `ak.member.state` | 仅当 `delivery_binding_rebind=true`：target actor 或 rebind-authorized service，且只更新 delivery binding / membership metadata | 不可用（`delivery_binding_rebind=false`） |
| `join` | `leave` | `ak.member.state` | target actor 或 `ak.realm.admin` | target actor 或 `ak.circle.member.manage` |
| `leave` / `invite` / `knock` / `join` | `ban` | `ak.member.state` | `ak.realm.admin` | `ak.circle.member.manage` |
| `ban` | `leave` / `invite` | `ak.member.state`（→`leave`）/ `ak.invite.create`（→`invite`） | `ak.realm.admin` | `ak.circle.member.manage`；self-service fail closed |

实现 MUST 以 `(scope_kind, delivery_binding_rebind)` 选择 FSM 实例，再按上表对应 scope 列求值 writer/guard，不得分别硬编码两套 transition graph。Bare knock / invite 的本地计时器不产生隐式边；任何过期清理仍须由该 scope 对应列授权的 writer 显式提交 `leave`。

**`default_join_rule=closed` 下的可用分支（normative）**：Realm scope 下 `default_join_rule=closed` 只关闭 **applicant-initiated 入口**——`leave -> knock` 与 applicant 自助的 `leave -> join` MUST 被拒绝。上表 `leave -> join` / `invite -> join` / `knock -> join` 三行的 **authorized-writer 分支仍然可用**（`ak.realm.admin`、`ak.realm.join.review`、Native Personal Agent controller carve-out、Realm bootstrap batch 内 creator 写入的初始成员）；封闭豁免列表见 [`../governance/join-policy.md` §4](../governance/join-policy.md)。所有分支仍 MUST 通过 Join Policy 的 A 轴 `principal_admission` 与 B 轴 `cooldown`。

**Realm `invite` 态与 Invite 对象的原子绑定（normative）**：Realm scope 下 `member.state=invite` 与一条 live 定向 Invite 对象（[`governance-objects.md` §5](governance-objects.md)）**一一对应**，二者的转换 MUST 在同一 Control Move 内原子完成：

- 进入 `invite` 只能由 `ak.invite.create` 的定向分支承担（它同时写 `ak.component.invite.lifecycle.v1` 与 `ak.component.member.state.v1`）；
- 离开 `invite` 到 `leave` 只能由把该 Invite 推进到终态的 `ak.invite.cancel` / `ak.invite.revoke` 承担；离开到 `join` 只能由 `ak.invite.accept` 承担。**MUST NOT** 用裸 `ak.member.state` 单独改写处于 `invite` 的 Realm member cell——那会留下 invite 对象与成员态不一致的悬挂状态。
- 因此 Realm scope 的 `invite -> ban` MUST 先（或在同一 batch 内）由 `ak.invite.revoke` 把该 Invite 推进终态，使 ban 边实际以 `leave -> ban` 求值。对处于 `invite` 的 Realm member cell 直接提交 `ak.member.state{ban}` MUST `failed_precondition`（`reason=invalid_membership_transition`）。Circle scope 无 Invite 对象，`invite -> ban` 照常由 `ak.circle.member.state` 承担。

## 5. State 枚举对齐

`state`、`stage`、`status`、`runtime_status` 和 `binding_state` 分属不同状态轴，不是同一字段的别名：

判据（normative，**无例外**）：区分 `state` 与 `status` 的是**谁拥有并推进这条状态轴**，不是"物理 vs 流程"。

- **`state`** —— 该轴由本协议**拥有并推进**：轴上每次转换都由已登记的 Arkret Event 或 reducer 派生产生，转换表在本规范内封闭。
- **`status`** —— 该轴由本协议**观察但不拥有**：真值在外部系统或传输过程中（账号系统、agent session、delivery 尝试、外部 registry 条目），Arkret 只镜像其当前值。
- **`stage`** 回答“这件事在业务推进上走到哪里”，用于跨 Realm / 跨产品聚合；与 `state` 正交，MUST NOT 互相 implicate。
- Jira-style workflow status、Trello 自定义列表名、审核节点名等细粒度业务状态 MUST 由 Realm workflow profile 或 schema 字段声明，并映射到 `stage`；不得把它们当作 `state` 或新的协议级 `stage` 枚举。

按该判据，Notification（`unread`/`read`/`dismissed`/`archived`）、Invite（邀请流程态）与 Agent Sidecar
（`active`/`suspended`/`tombstoned`）使用 `state` 是**正确的**，不是命名例外——三者的轴都由 Arkret Event
或 reducer 派生封闭推进。此前把它们记为"特例"源自旧判据以"物理生命周期"划线，而"物理"从来不是
可判定的界线；改用所有权判据后三条例外全部消失。反之 Actor Profile 的 `status` 镜像账号系统状态、
delivery `status` 镜像投递过程，仍 MUST 用 `status`。

上表"物理生命周期"一列因此读作"该对象自身的主状态轴"；各对象的具体枚举与转换表仍以 §5.1、§5.2
及对象专属章节为准。

| 字段 | 使用场景 | 语义轴 |
| --- | --- | --- |
| `state` | Realm / Circle / Space / Strand / Message / Morph / Relation 等 canonical object | 物理生命周期：active、archived、redacted、tombstoned / deleted 等。 |
| `stage` | Strand / Morph | 业务进度，与物理生命周期正交；完整枚举为 8 值（draft、proposed、planned、in_progress、blocked、done、cancelled、superseded），权威定义见 §5.3.2。 |
| `status` | Account、agent session、delivery、moderation workflow、registry entry 等过程型对象 | 外部过程或会话状态；不得替代 object lifecycle。 |
| `runtime_status` | Applet bridge / runtime metadata | 跨协议 runtime 可用性或执行态，避免与 canonical object `status` / `state` 混淆。 |
| `binding_state` | Handle claim / identity binding | claim 绑定验证状态：pending、verified、revoked、expired；不是 materialized object lifecycle。 |

各对象的 `state` 字段值不完全相同（部分名字承载了已稳定的 `ak.*.tombstone` event 命名约定），但在 reducer / projection 语义层等价于以下规范状态机：

| 规范状态 | 语义 | Strand | Circle | Space | Message | Morph | Relation | Realm |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `active` | 当前可用 | `active` | `active` | `active` | `active` | `active` | `active` | `active` |
| `archived` | 软隐藏，UI 默认不展示，可撤销 | `archived` | `archived` | `archived` | — | `archived` | — | `archived` |
| `redacted` | 内容已根据 redaction policy 清除，envelope 与审计元数据保留 | `redacted` | — | — | `redacted` | `redacted` | `tombstoned`（合并 deleted+redacted） | — |
| `deleted` | 不可逆删除：content / encrypted_content / encrypted_payload 清空，仅保留 envelope 用于审计 | — | `tombstoned` | `tombstoned` | — | — | `tombstoned` | `realm_terminal_state`（projection；Realm 对象无 `state` 字段，`ak.realm.tombstone` / `ak.realm.destroy` 均映射到此终态类别） |

约定：

- 写入路径 MUST 来自对应 reducer-input event（`ak.<kind>.archive` / `ak.<kind>.restore` / `ak.<kind>.tombstone` / `ak.<kind>.redact` 或等价命名）；不得直接 PATCH 对象顶层 state。`archived -> active` 是显式的可逆转换，由 `ak.<kind>.restore`（Strand、Circle、Space、Morph 均已注册对应 restore event）承担；`tombstoned` / `deleted` / `redacted` 是不可逆终态，MUST NOT 被 restore。
- `state != active` 时 MUST 写入 `state_changed_at`（§3 / §3.1 统一标记为 `R when state≠active`：reducer-derived、actor MUST NOT 携带）。
- **Agent Sidecar（`ak:sidecar:`）reducer 派生 state 轴**：Sidecar 的 `state` 为 `active` / `suspended` / `tombstoned`。它**不**由 §5.1 的 `ak.<kind>.archive/restore/tombstone` 事件驱动，而是由已接受的 controller account / Realm membership / lifecycle frontier **reducer-derived** 的 canonical projection（无 actor-authored lifecycle event）。`suspended`（controller 暂时失去 Realm access / account 临时冻结 / 密钥恢复未 ready）是本轴独有的可逆中间态，不属于上表通用 `archived` 语义；`tombstoned` 为不可逆终态。合法 / 非法迁移封闭表与派生条件见 [`sidecar.md` §7](./sidecar.md)。与 Notification / Invite 的 `state` 轴（§3.1 附注）并列：三者都是 Arkret 拥有并推进的主状态轴（§5 判据），但都不落入本节通用协作对象 lifecycle 状态机。

#### 5.1 Canonical state-transition table

每个 reducer-input lifecycle event 都 MUST 校验**当前 state**(reducer 视角下的 pre-state)落在下表"合法源"集合内，否则 MUST 返回 `failed_precondition`,`reason` 取下表 `reason_code` 列。

| event family | 允许的源 state | 目标 state | `failed_precondition` reason_code |
| --- | --- | --- | --- |
| `ak.<kind>.archive` | `active` | `archived` | `<kind>_not_active` |
| `ak.<kind>.restore` | `archived` | `active` | `<kind>_not_archived` |
| `ak.<kind>.tombstone` | `active`、`archived` | `tombstoned` / `deleted`(各对象 schema 自命名) | `<kind>_already_terminal` |
| `ak.<kind>.redact` 或 cross-object `ak.redaction` 指向该对象 | `active`、`archived` | `redacted`(如对象支持),或合并到 `tombstoned` | `<kind>_already_terminal` |

> **Strand / Morph 豁免**:上表 `ak.<kind>.tombstone` 行是通用模板;Strand 与 Morph **没有** `tombstone` 终态(也不用 `deleted`),其不可逆终态经指向该对象的 `ak.redaction` 进入 `redacted`(见 §5.2 模板槽与 [strand-and-message.md §9.1](./strand-and-message.md))。对 Strand / Morph 提交 `ak.<kind>.tombstone` 不适用。

`<kind>` 是 schema 类型短名(`strand`、`circle`、`space`、`morph`、`message`、`relation`),所有 reducer 实现 MUST 用相同 reason_code,使跨实现错误诊断一致。具体值如:`strand_not_active` / `strand_not_archived` / `strand_already_terminal`,`circle_not_active` / `circle_not_archived` / `circle_already_terminal`,`space_not_active` / `space_not_archived` / `space_already_terminal`,`morph_not_active` / `morph_not_archived` / `morph_already_terminal`,以及无 archived 态对象的 `message_already_terminal` / `relation_already_terminal`(见本节末段)。

附加规则:

- **未知对象 pending / replay**：reducer 若收到的 lifecycle event 指向尚未在本地物化的对象（create event 尚未通过 causal / backfill 到达），MUST NOT 把该事件当作成功 no-op 丢弃，也 MUST NOT 返回普通 `failed_precondition`。接收方 MUST 把该 lifecycle event 保留为 `pending_causal_apply`（或等价可重放状态），按目标对象 id / digest 建索引，并在目标 create/backfill、可验证 snapshot 或 target visibility 证明到达后重新执行同一 state transition 校验。若后续证明目标永久不可见、未授权或已被 retention 剪裁，实现 MAY 分别暴露已登记的 `dependency_missing`、`capability_denied` 或 `history_not_visible` 诊断，但不得把签名 lifecycle event 记为 accepted-and-applied。该规则与“对已知对象的 state 校验”互补：已知对象走上表 pre-state 校验；未知对象进入 pending/replay，从而保证相同事件集合在不同交付顺序下仍收敛。
- **终态等价**:`tombstoned` / `deleted` 在 state-machine 中等价，都属于"不可逆终态";`redacted` 单独占一格但对 archive / restore / tombstone 而言同样是"不可逆终态"(MUST NOT 被这些 event 修改)。
- **不允许 same-state self-transition**:`ak.<kind>.archive` 在 `state == "archived"` 时 MUST 返回 `<kind>_not_active`,**MUST NOT** 当作 idempotent no-op。这保证 reducer 路径上每个 state transition 都对应一次 audit-able 状态变化；客户端如果想"重新 archive"应当先 restore 再 archive,或确认目标对象 state 后跳过事件提交。
- **`state_changed_at` reducer-derived(normative)**:reducer **MUST** 忽略 wire payload 中任何 actor-supplied 的 `state_changed_at` 值。该字段的权威值是 `max(Event.created_at, first_covering_sealed_at)`，其中 `first_covering_sealed_at = min({S.sealed_at | accepted Seal S covers Event})`；覆盖集合为空时只取 `created_at`。同一 Move 被多个 `open_set` 并发 Seal 覆盖时仍由该集合纯函数得到唯一值。客户端不得依赖 wire 上的 `state_changed_at` 做时序判断；若 wire 值与 reducer 派生值不一致,SDK SHOULD 报警并以 reducer 派生值为准。该规则防止 actor 通过填错时间戳干扰 retention、audit timeline、conflict tie-break(虽然 §6 已禁止 HLC / event id / actor_seq 作为 cell winner 选边，但 retention 与 audit query 仍可能 group by `state_changed_at`)。

`*.create` 与 `*.update` 永远 set state 为 `active`(或保持当前 active);对一个非 active 对象提交 update MUST 失败(`failed_precondition`,reason 同 `<kind>_not_active` 家族),否则编辑会隐式复活已 archive/tombstone 的对象——这与 `*.restore` 的语义冲突。Conformance 实现 MUST 把"update on non-active object"视为 invariant 违反。

Message 与 Relation 没有 `archived` 态(见 §5.2 模板使用约束):它们的非 `active` state 一律是不可逆终态。因此对非 active 的 Message / Relation 提交 update(如 `ak.message.revise`)MUST 返回 `failed_precondition`,`reason_code` 取 `<kind>_already_terminal`(即 `message_already_terminal` / `relation_already_terminal`),不使用 `_not_active` 家族。

#### 5.2 Unified lifecycle event template（doc-only canonical）

任何 durable canonical object 的 lifecycle event 家族 SHOULD 按以下模板派生(实际 wire kind 仍按对象自身命名，不强制重命名；本节统一描述以便新对象注册时直接对齐，无需在 event-kind-registry 重新讨论一次):

| 模板槽 | 含义 | 已有实例 |
| --- | --- | --- |
| `ak.<kind>.create` | 创建对象，落 state=`active`,写入 `created_by` / `created_at`。 | `ak.strand.create`、`ak.circle.create`、`ak.space.create`、`ak.morph.create`、`ak.message.create` |
| `ak.<kind>.update` | 增量更新 active 对象字段;reducer 拒绝非 active 源。**新对象 SHOULD 沿用 `ak.schema.patch.v1` 统一 patch 表达，不应再造单字段 update event。** | `ak.strand.update`、`ak.morph.update`、`ak.schema.patch.v1`(unified) |
| `ak.<kind>.archive` | active → archived;写入 `state_changed_at`。 | `ak.strand.archive`、`ak.circle.archive`、`ak.space.archive`、`ak.morph.archive` |
| `ak.<kind>.restore` | archived → active;写入 `state_changed_at`。 | `ak.strand.restore`、`ak.circle.restore`、`ak.space.restore`、`ak.morph.restore` |
| `ak.<kind>.tombstone` 或 cross-object `ak.redaction` | active/archived → terminal(`tombstoned`/`deleted`/`redacted`);不可逆。Strand 与 Morph 的终态仅通过指向该对象的 `ak.redaction` 表达。 | `ak.circle.tombstone`、`ak.space.tombstone`、`ak.relation.tombstone`、`ak.redaction`(指向 strand / space / morph / message) |
| `ak.<kind>.redact` 或 cross-object `ak.redaction` | active/archived → `redacted`(若对象支持);envelope 保留,content 清空。v1 wire 实际注册形态请以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 为准:Message 走 `ak.message.redact`;Strand / Morph / Space / Relation 等未单独注册 `ak.<kind>.redact` 的对象走 cross-object `ak.redaction`。两种 wire 形态都是 canonical (`active` status),按对象选择;reducer 不得自行折叠或互换。 | `ak.message.redact`、`ak.redaction`(用于 strand / morph / space / relation 等未单独注册的对象) |

模板使用约束:

- **不是命名 mandate**,但 **MUST 与 registry 对齐**:模板槽列出的"已有实例"必须存在于 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 中;`ak.message.create` 是 v1 标准 wire kind。新对象在注册时按模板选择需要的槽，但**不得**列出 registry 中不存在的 wire kind 当作示例。
- **不创造新槽**:新增 lifecycle 行为(例如"软隔离 / 待审 / 撤回审核")MUST 先在本节扩展模板；否则不得作为标准 lifecycle event 入 registry。
- **patch 优先**:新对象 lifecycle 中的"字段更新"槽 SHOULD 由 `ak.schema.patch.v1` 承载(参见 [`strand-and-message.md` §4.8](./strand-and-message.md) 的 `ak.strand.tracks.update` 实例);避免出现 `ak.<kind>.set_<field>` / `ak.<kind>.toggle_<field>` 这类单点 event 膨胀。**stage 是该原则的明确例外**:`ak.<kind>.stage.set` 走专用 event 是为了 capability 切分与审计过滤(见 §5.3),而非字段膨胀。
- **stage 模板槽**:适配 §5.3 的对象 MUST 注册一条 `ak.<kind>.stage.set` event,并在 event kind registry 显式绑定该对象类型的专用 stage-set payload schema（现有绑定为 `strand_stage_set_payload` 与 `morph_stage_set_payload`;详见 [`event-payload.schema.json`](../../artifacts/schemas/event-payload.schema.json));`ak.<kind>.update` patch 路径 MUST NOT 修改 `stage` / `stage_changed_at`(违者 `schema_violation`,单源约束)。**stage 变更不携带 reason 字段**:事件本身已经 durable 且 `created_by` / `created_at` 即审计归属；需要解释"为什么 cancel / block / supersede"时,actor SHOULD 在该对象的 discussion track 发一条 Message(`ak.message.create`),通过 `references` Relation 指向本次 `ak.<kind>.stage.set` event,而不是把 reason 藏在对象字段里。
- **可逆 lifecycle facet 的两种合规形态**:`ak.<kind>.archive` / `ak.<kind>.restore` 模板槽描述的是**独立 archive event + 独立 restore event** 成对形态（Strand / Space / Morph 即此形态）。但可逆 lifecycle 也允许第二种形态：**单一 reversible boolean facet event**（同一 `ak.<kind>.archive` 写 `true` / `false` 在 active ↔ archived 间切换，不发布独立 `ak.<kind>.restore`）。Realm 的 `ak.realm.archive` / `ak.realm.freeze` 即此形态（见 [`realm-and-space.md` §2.6.0](./realm-and-space.md#260-realm-可逆-lifecycle-facetakrealmarchive--akrealmfreeze)）。某 Event 是否属于本模板，不按 kind 名称或是否写 `fsm` 猜测：只有其目标 family 在 canonical `fsm_contracts` 中声明 `axis="object_lifecycle"` 时，event-kind 行才 MUST 登记 `lifecycle_modality`（`reversible` 或 `terminal`）。workflow、membership、status、audit、key-material FSM 以及 OR-Set 撤销均不适用。具体对象采用哪种形态，以 [`event-kind-registry.json`](../../artifacts/registry/event-kind-registry.json) 的该字段为准；`reversible` boolean facet 不要求也不应存在配套 `ak.<kind>.restore`。
- **state 校验来源唯一**:本节所有模板事件的状态机校验入口都是 §5.1 表，不在各对象文档重复说明转换矩阵。
- "Space 没有 redacted"：Space 不承载用户 content（仅承载结构容器元数据），无需独立 redaction 状态；title / summary 的内容清理通过 `ak.space.tombstone` 或 `ak.redaction` 一并完成。
- "Message / Relation 没有 archived"：Message timeline 是有时序流，Relation 是边——两者都不需要"软隐藏可撤销"语义；要隐藏 Message 用 redaction，要解除 Relation 用删除即可。
- "Relation 用 `tombstoned` 单一终态"：删除与 redaction 在边语义上不可区分（边只有"存在"或"不存在"），故物化 state 合并为单一 `tombstoned`；具体 reason 在对应 `ak.relation.tombstone` / `ak.redaction` event 中保留。
- Reducer 与 projection MUST 把 `tombstoned` 视为不可逆删除状态；Strand / Morph 不使用 `deleted`，其不可逆内容清除状态是 `redacted`。UI 展示策略（隐藏 vs 显示 tombstone 占位符）由 client 根据对象类型决定。

### 5.3 Stage 轴（业务进度，与 state 正交）

`state` 表达**物理生命周期**（对象是否存在 / 是否可写 / 是否已被 redact）；`stage` 表达**业务进度**（一件事从想法走到完成的过程）。两个字段在不同 reducer 路径上独立维护，**MUST NOT 互相 implicate**：archive 不会把 `stage` 推到 cancelled，`stage=done` 不会自动 archive 对象。

#### 5.3.1 适用对象（v1）

| 对象 | 是否声明 `stage` | 必填语义 | 触发 event |
| --- | --- | --- | --- |
| `Strand` | yes | 可选；`ak.strand.create` MAY 省略，普通业务 Strand SHOULD 填写，DM 主 Strand MAY 省略或选填合法值 | `ak.strand.stage.set` |
| `Morph` | yes | 可选；generic mirror/data Morph MAY 省略，需要进度轴的 morph_kind profile MAY 收紧为 create 必填 | `ak.morph.stage.set` |
| Realm / Space / Message / Relation / View / Policy / ... | no | — | — |

适用对象自己的 schema MUST 显式枚举允许值；`strand.schema.json` 与 `morph.schema.json` MUST 把 `stage` 声明为可选字段，且 `stage_changed_at` MUST NOT 在缺少 `stage` 时单独出现。Morph 缺失 stage 时，首条 `ak.morph.stage.set` 是初始化而非从某个隐含默认值迁移；可取任一注册值，之后才应用普通转换规则。不适用对象 MUST NOT 暴露 `stage` 顶层字段。**未来如有新对象需要 stage 轴**,扩展时 MUST 同步在本节登记。

#### 5.3.2 协议级枚举（8 值，固定）

| 值 | bucket | 含义 |
| --- | --- | --- |
| `draft` | `todo` | 起草 / scoping,未对外承诺。 |
| `proposed` | `todo` | 待评审 / 决策(accept or reject)。 |
| `planned` | `todo` | 已接受，排期中，未启动。 |
| `in_progress` | `doing` | 当前正在被推进。 |
| `blocked` | `doing` | 在做但被外部依赖卡住。 |
| `done` | `closed` | 成功完成。 |
| `cancelled` | `closed` | 主动放弃，未完成，无替代品。 |
| `superseded` | `closed` | 被另一个对象取代;SHOULD 配套写 Relation `superseded_by` 指向继任。 |

`bucket`(`todo / doing / closed`)是**派生**分类，不入 wire / canonical bytes / 签名输入;projection 自行映射用于 dashboard / filter。bucket 命名刻意避开 `active`,防止与 `state=active` 撞名。

枚举值在 v1 内**固定**,profile MUST NOT 新增 stage value;细粒度业务状态(`needs_review` / `qa` / `signed_off` 等)走 per-Realm workflow profile 或 `fields.<custom_status>`,**不**在协议级 stage 表达。

#### 5.3.3 转换规则（reducer-enforced 硬约束)

`stage` 的细粒度 transition matrix 由 per-Realm workflow profile(profile-level)声明;**核心 reducer 不强制 stage 之间的方向**(`done → in_progress` 回炉、`cancelled → planned` 复活均合法)。但以下硬约束 MUST 由 core reducer 强制:

1. **物理终态优先**:对象 `state ∈ {redacted, tombstoned, deleted}` 时,`ak.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_already_terminal"`。
2. **non-active 拒写**:对象 `state=archived` 时,`ak.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_not_active"`(与 §5.1 update on non-active 同语义);想推进 stage 必须先 `ak.<kind>.restore`。
3. **`stage_changed_at` reducer-derived**:reducer **MUST** 忽略 wire payload 中 actor-supplied 的 `stage_changed_at`,以触发 event 的 `created_at` 覆盖。
4. **same-value self-transition no-op**:`ak.<kind>.stage.set` 把 `stage` 设为与当前相同值时,reducer **不更新** `stage_changed_at`,且不计入审计变更(与 §5.1 `ak.<kind>.archive` 在 same-state 时 fail 的规则**不同** —— stage 是软进度字段，允许 idempotent no-op)。
5. **stage 变更不携带 reason 字段**:`ak.<kind>.stage.set` payload **不**定义 reason / note / explanation 字段。需要解释时 SHOULD 在该对象的 discussion track 发 Message 并通过 Relation `references` 指向本次 stage event;事件日志本身的 `created_by` / `created_at` 已经是审计归属真源。reserved-name guard:对象顶层与 `fields.*` 上 `stage_reason` / `stage_note` / `stage_explanation` / `stage_comment` MUST 被 forbidden-wire-fields 拒绝。
6. **`ak.<kind>.update` 禁写 stage**:patch path `stage` / `stage_changed_at` MUST 被 forbidden-wire-fields 拒绝(单源:stage 变更只能走 `ak.<kind>.stage.set`)。

#### 5.3.4 与 workflow profile 的关系

未启用 workflow profile 的 Realm:actor 通过 `ak.<kind>.stage.set` 直接推进 stage,reducer 只走 §5.3.3 硬约束。

启用 workflow profile 的 Realm(profile-level,non-core):

- 每个 workflow state SHOULD 声明 `stage_category`(取上面 8 值之一);
- workflow 推进 event 在变更 `workflow_state_ref` 时,reducer SHOULD 派生写入对应 `stage`;
- 客户端直接发 `ak.<kind>.stage.set` 仍合法，但 profile MAY 收紧为只允许 workflow event 路径(profile-defined,非 core)。

携带 `stage` 的对象使用该字段作为 workflow 的协议级粗投影，跨 Realm dashboard 可聚合(同一个 `stage=in_progress` bucket 涵盖各 Realm 自定义的"In Dev / Reviewing / QA"等 fine-grained state)。

## 6. 通用对象 ID 约定

### 6.0 create-once 对象 ID 由 create Event 派生（normative）

对象 ID 不由调用方选取。对每个在 [`contract-registry.json`](../../artifacts/registry/contract-registry.json) 中声明 `id_source="event_derived"` 的 create Event kind：

```text
object_id ≡ retype(create_event.event_id, object_kind)
```

即被创建对象的 ID 与创建它的 Event 的 `event_id` 共享同一个 33-octet token，只更换 typed 前缀（`ak:event:<T>` → `ak:<object_kind>:<T>`）。`T` 是 suite wire code 与完整 32-octet Event digest 的 canonical Base64URL 编码，按 [`../conformance/encoding.md` §4.0](../conformance/encoding.md) 由 Event 内容绑定；它不是 UUID，也不得存入 native UUID 列。

规则：

- **create payload MUST NOT 携带该 ID 字段。**携带即 `schema_violation`，`reason_code=object_id_not_event_derived`。reducer 在物化对象时派生它。
- **一条 create Event 对同一 typed kind 最多派生一个 create-once 对象 ID。**同一 Event MAY 按
  registry 的封闭 `id_kind` / `id_kinds[]` 声明，把相同 33-octet token 重类型到多个不同 typed
  namespace；例如一个 Event 可同时派生 `ak:report:<T>` 与 `ak:moderation_queue_item:<T>`，二者不是同一
  完整 typed ID。未在 registry 登记的额外派生、同一 kind 的多个对象或 caller 自选 ID 一律禁止。
- **`event_id` 是完整密码学身份。**canonical Event store 必须保存完整 33-octet raw token 或等价 typed string；重算验证通过前不得物化对象。
- `ak.realm.create` 的 wire envelope 与 payload 都省略 `realm_id`，receiver 对所有 `purpose` 一律按 `retype(event_id)` 派生；见 [`realm-and-space.md` §2.5](./realm-and-space.md)。

若两个不同 canonical create Event 在同一 suite 下发生完整 256-bit hash collision，它们会得到同一 Event ID，重类型后也争用同一对象 ID。此时必须按 [`../sync/operations-sync.md` §12](../sync/operations-sync.md) 隔离两条 Event、其派生对象与未 final writes，在协议外裁决前不得物化任一对象。

本节的 conformance 入口是 `ak.vector.object_identity.event_derived.v1`（机读 fixture 见 [`content-bound-event-id-fixture.json`](../../artifacts/fixtures/content-bound-event-id-fixture.json)）：它固定 `retype(event_id)` 的 KAT、`realm_id` 的自证校验，以及 `object_id_not_event_derived` / `realm_id_not_event_derived` 两条拒绝路径。

`id_source` 的其它取值：`reference` 表示该 kind 引用一个别处创建的对象；`not_an_object_id` 表示该字段不是 typed 对象 ID（DID、命名空间字符串、profile-scoped form）。**每个 active kind MUST 声明其一**，registry lint 在缺声明时失败——覆盖面由机器保证，不依赖人工枚举。

Protocol typed identifier / reference 的 wire value MUST 使用带类型前缀的稳定字符串：

```text
ak:realm:<44-char-event-token>
ak:space:<event-token>
ak:strand:<event-token>
ak:message:<event-token>
ak:morph:<event-token>
ak:relation:<event-token>
ak:actor_profile:<event-token>
ak:event:<event-token>
ak:view:<event-token>
ak:policy:<uuid>
ak:capability:<uuid>     # abstract capability definition reference（非签名 grant；签名 grant 用 ak:grant:）；真源 artifacts/registry/id-kind-registry.json `capability` 条目
ak:grant:<44-char-event-token>
ak:invite:<44-char-event-token>
ak:applet:<uuid>
ak:blob:<uuid>                 # blob metadata row id
ak:blob:sha256:...             # content-addressed special form（sha256:<hex>，digest-suite 见 digest-suite-registry.json）
ak:receipt:<uuid>
ak:trust_domain:<trust_domain_label>   # 非 UUID 形态，见下方说明
```

typed ID 的 token 构造 MUST 由
[`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 中该 kind 的 `id_form`
唯一固定：`producer_allocated` 使用 UUIDv7（time-ordered），`event_derived` 使用
[`../conformance/encoding.md` §4.0](../conformance/encoding.md) 定义的 33-octet suite-tagged 完整 digest token；
`suite_tagged_full_digest` 同样使用 §4.0 的完整 uint8 digest-suite code 加 32-octet digest，但其 preimage 与
authority 由 kind-specific registry contract 固定。Realm ID 属 `event_derived`：它使用
[`../conformance/encoding.md` §4.1](../conformance/encoding.md) 的 33-octet token，高 nibble 永久保留为零、
低 nibble 固定 digest suite，与其 `ak.realm.create` Event token 逐字节相同。调用点 MUST NOT 自行选择
id_form，也不得把 Event、Realm 或 Event-derived typed ID 降级为 UUIDv7。content-addressed form
使用对应 digest。

所有 typed ID 的总表是 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)；它同时列出
`id_form`、`identity_authority`，并在适用行列出 `genesis_event_kinds` 或 kind-specific derivation contract，
实现 MUST NOT 在各 schema / reducer 中另建一份手写分类。其中 `ak:audit_binding:`、`ak:call:` 与
`ak:grant:` 是 `event_derived`，分别从 `ak.audit.applet_binding.create`、`ak.call.create` 与
`ak.capability.grant` 的 Event ID 重类型化为相同 33-octet token。`ak:session_grant:` 则是
`identity_authority="issuer_record"` 的 `suite_tagged_full_digest`：从 closed
`ak.session_grant.issuance.v1` preimage 派生，并以 `(issuer_did, typed_id)` 作为 storage identity key；它
不是 Event ID。其首字节是完整 digest-suite wire code，不得按 Realm 的“保留零 nibble + 低 4 位
suite”解释；具体合同见 [`../identity/key-management.md` §6.1](../identity/key-management.md)。

`producer_allocated` UUIDv7 只提供时间排序与随机冲突概率，**不证明谁有权分配该 ID**。其协议身份键 MUST 是 `(mint_authority, typed_id)`，`mint_authority` 是该 ID 首次持久出现时通过接收校验的 genesis proof signer DID。存储与索引 MUST 原子保留这个二元组：同 authority + 同 ID + 同内容是幂等重放；同 authority + 同 ID + 不同内容 MUST 拒绝并隔离；不同 authority 即使 UUID 相同也是不同身份。裸 typed-ID 查找、跨 authority 去重、last-writer-wins 修复以及未绑定签名的预占位都 MUST fail closed。该规则由 ID registry 顶层 `producer_allocated_identity_contract` 机读定义，所有 `identity_authority="producer_signature"` 行统一继承。

并非所有 ID kind 都是 producer-allocated `ak:<kind>:<uuidv7>`。Event-derived kind 使用上述
suite-tagged 完整 digest token，此外 `ak:trust_domain:` 是 deployment-scoped replay boundary 标识：其 wire form 为
`ak:trust_domain:<trust_domain_label>`，`<trust_domain_label>` 是稳定的部署信任域标签（例如
`ak:trust_domain:did.webvh.acme.example`），不是 UUID。它 create-locked 在 Realm `trust_domain`
字段上，MUST 匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context（见
[`realm-and-space.md` §2.3](./realm-and-space.md)）。

`ak:cell:` / `ak:cursor:` / `ak:seal:` 等同步 / 状态原语的 wire form 见各自章节与 `artifacts/registry/id-kind-registry.json`，不在本协作图对象 ID 约定表内。上表只是常见 wire value 形态摘要，完整 ID kind 注册表及唯一真源见 `artifacts/registry/id-kind-registry.json`。本节不决定字段名：普通 canonical object 主键仍是 `id`，Event / Receipt / Backup 等 artifact 可用 `<artifact>_id`，Blob / Snapshot / MLS 等 reference 形态按 §2.1 使用 `_ref`。

### 6.1 Policy 对象 vs 内联配置的字段命名约定（normative）

实现者经常困惑：同一个对象上既有 `<axis>_profile` / `<axis>_policy` 这样的内联枚举字段（如 `encryption_profile`、`federation_policy`、`notary_profile`、`digest_algorithm`），又有 `<axis>_policy_id` 这样指向独立 Policy 对象的字段（如 `policy_id`、`retention_policy_id`、`disclosure_policy_id`、`rate_limit_policy_id`）。这是有意区分，规则如下：

- **`<axis>_profile`**：v1 协议级**固定选项**（create-locked 或 reducer-enforced 收敛），值是封闭 enum 字符串（`"mls_rfc9420"` / `"single_did"` / `"sha256"` / ...）。schema 内联约束，无需引用独立对象。变更需要新 event kind（如 hash-transition Seal）或新 Realm。
- **`<axis>_policy`**：v1 协议级**软策略字段**，值仍是 enum 字符串（`"open"` / `"restricted"` / `"closed"` / `"quarantine"` 等），但描述运行时执行策略，与其他 cell state 有交互。同样内联，不通过引用对象。
- **`<axis>_policy_id`**：指向独立 Policy 对象（`ak:policy:<uuid>`）的 ID，pattern `^ak:policy:[0-9a-f]{8}-...`。Policy 对象自身有 schema 与版本，可以被多个对象共享、被 governance event 修订。独立对象用于：(a) 跨对象复用、(b) 大体积或频繁变更、(c) 需要独立审计 / 签名链。
- **`<axis>_floor`**：某条加密 / 隐私轴上的**下限**字段，值与对应 `<axis>_profile` 取同一封闭 enum，但语义是"只能向上收紧、MUST NOT 放宽继承到的上游基线"。它用于真实子作用域（Circle）声明比父 Realm 更严格的下限；authorization-transparent 的 Space 只表达 placement 谓词，不承载 floor 值。effective 值取上游 `_profile` 与各 scope `_floor` 的更严格者（见 [`circle.md` §7](./circle.md)）。

判定流程：写新字段时若是**封闭 enum**（值集已知、协议级固定）用 `_profile` 或 `_policy`；若是**指向 Policy 对象**用 `_policy_id`；不得在同一对象上同时定义 `xxx_policy` 与 `xxx_policy_id` 表示同一个轴。若字段引用的是"授权该决策的 policy revision Event"，使用带 event 语义的 `_ref` 名称，例如 `policy_event_ref`，不得与 `policy_id` 混用。

公共字段示例：

```json
{
  "id": "ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa",
  "schema": "ak.schema.strand.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "created_by": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": "ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH",
  "updated_at": "2026-04-26T00:00:00Z"
}
```

## 7. Reducer 总则

Reducer 总则的 normative 表述以 [`event-and-patch.md` §6](./event-and-patch.md) 为唯一权威；本节不再重复列出验证步骤，避免两份独立维护的清单漂移。

§5 state-transition 表与 §5.1 `failed_precondition` reason-code 族属于本节关注的"对象 lifecycle 层 reducer 行为"; 它们与 §6 (Event-level reducer 总则) 形成"对象层 ↔ 事件层"两个互补侧面，均受 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 统一约束。

## 8. 规范性引用

- 完整 ID kind registry：`artifacts/registry/id-kind-registry.json`。
- Schema registry：`artifacts/registry/schema-registry.json` 与 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Canonical JSON、hash、签名、cursor、HLC、rank 编码：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Reducer conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
