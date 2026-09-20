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
| `digest` | 自描述 `<digest-suite>:<lowercase_hex_digest>`（suite 取 `digest-suite-registry.json` 中该字段 owning domain 允许的 active 套件，如 Blob 可用 `sha256:` / `blake3:`）。Event、Event-derived object、Realm 与 RealmCommit identity 固定为 current-v1 JCS + SHA-256，不由 Realm 状态选择。 |
| `cursor` | `ak:cursor:<base64url>` opaque string。 |
| `patch` | `ak.schema.patch.v1` 形态的 JSON patch 片段，具体路径与 op 规则见 [`event-and-patch.md`](./event-and-patch.md)。 |

<!-- rule_id: NC-FIELDCASE-001 --> **wire 字段名词法（normative）**：上表 `object` / `map<T>` 记法中的字段名判据是机械判据，不是风格建议：JSON Schema 中声明的每一个 property 名 MUST 为 snake_case。只有两类形态不受该词法约束，且两类都 MUST 在机器可读处声明，不得按字段名或类型名全局豁免：

- **语法保留指令键**：以 `$` 起始的键不是数据字段，而是 schema 语法自身的判别键（v1 中唯一形态是 `ak.schema.patch.v1` 的 `$op`，见 [`event-and-patch.md` §4](./event-and-patch.md)）。正是这个 sigil 使它与数据字段的 snake_case 命名空间不相交；去掉 `$` 之后的剩余部分仍 MUST 为 snake_case。
- **逐字镜像外部规范的对象**：该对象 MUST 在自身 schema 节点上登记 `x-arkret-external-literal-object` 标记，标记 MUST 同时给出外部规范名（`specification`）与带 fragment 的 `https://` 锚点 URL（`anchor`）。该标记只覆盖它**直接声明**的 property 名，MUST NOT 随 `$ref`、类型名或同名字段传播到其它对象；当被标记对象的 property 名全部已是 snake_case 时，标记 MUST 被删除。

注：`device_id` 不是例外字段；它的类型是 `id:device`，wire form MUST 为 `ak:device:<uuid>`。只有部分辅助标识符（如 `transaction_id`、`backup_version`、`stream_id`）使用领域特定前缀（如 `ver_`、`kb_`、`devstream_`），不遵循 `ak:<kind>:<uuid>` 格式。这些标识符的编码规则由各自所在章节定义。`recording_id` 是 [`crypto-media/call-state.md` §5](../crypto-media/call-state.md) 定义的 opaque 领域标识（示例形态 `rtc-recording-<uuid>`）：它是 backend 媒体服务（如 LiveKit Egress）生成的 opaque 录制 lifecycle 句柄，进入 recording key exporter Context，**不是** `ak:*` typed ID。

Arkret 命名空间与分隔符约定（normative）：`.` 与 `:` 表达不同层级，MUST NOT 互换，也不得把其中一种拼写当作另一种的 alias。

| 形态 | 语义 | 示例 |
| --- | --- | --- |
| `ak.<symbol-path>` | **符号名称 / 注册表词汇**。`.` 只表达命名空间与分类层级；值命名一种 event、operation、schema、profile、capability action、content kind 或 namespaced key，不直接充当某个协议对象实例的 typed reference。 | `ak.message.create`、`ak.self.events.command.submit.v1`、`ak.schema.event.v1` |
| `ak:<kind>:<payload>` | **具体实例或引用**。第一个 `:` 把 Arkret namespace 与 ref kind 分开，第二个 `:` 开始该 kind 的实例载荷；载荷由 `id-kind-registry.json` 对应 kind 的 wire form 决定。 | `ak:message:<44-char-event-token>`、`ak:strand:<44-char-event-token>`、`ak:realm_commit:sha256:<digest>`、`ak:trust_domain:<scope>` |
| `{kind, ...identity}` | **领域 current-result selector**。`kind` 与其身份字段由 `typed-current-result.schema.json` 的 closed branch 定义；它是 JSON typed object，不拼接字符串 ID。 | `{ "kind": "strand", "strand_id": "ak:strand:..." }` |

因此，看到 `ak:` 先按“typed ref / special-form ref”解析，看到 `ak.` 先按“registry symbol / namespaced key”解析。领域 current-result selector 始终按其 closed JSON schema 解析，不编码成第三种字符串命名空间。完整 typed-ref special forms 以 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 和 [`encoding.md` §4](../conformance/encoding.md) 为准；缺席于当前 registry/schema 的前缀、selector kind 或拼写都不是 alias，parser MUST fail closed。

需要安全域分离的固定字符串 label 也使用 registry 明确登记的 `ak.*` 值。`proof-context-registry.json` 的 `contexts[].context` 与 `domain_separations[].domain` 统一使用 `ak.<symbol-path>.v1`：`.` 分隔命名层级、层级内复合词使用 snake_case。两类 label 不靠分隔符编码语义，而由其所属数组及 `primitive` 唯一决定；同一 label MUST NOT 同时登记于两类中。历史 `ak.<kebab-case>-proof-v1` 拼写无效且不是 alias；调用点 MUST 逐字使用所属 registry 行。MLS GroupContext extension 的当前 wire 名是 `mls_governance_binding`（codepoint 0xF1C0，不使用品牌前缀），实现 MUST 用 `mls_governance_binding`、MUST NOT 接受其它拼写。它唯一承载 `effective_scope`、`base_group_state_ref`、`previous_epoch`、`next_epoch`、`key_access_revision` 五字段 deterministic-CBOR map；外层 key 的编码字节顺序固定为 `next_epoch`、`previous_epoch`、`effective_scope`、`key_access_revision`、`base_group_state_ref`，三个整数均为 `0..2^64-1`，其中 `key_access_revision` 是单调计数器而非摘要。精确 decoder 上限与拒绝条件见 [`encryption-and-audit.md` §2.5.1](../crypto-media/encryption-and-audit.md)。

字段默认规则：

- 未标记 optional 的字段为 required。
- `null` 只有在类型中明确写出时才允许。
- Event Envelope 顶层未知字段 MUST 被 schema validation 拒绝；非关键扩展只能放入 `payload.x_*`，且仅当该 payload kind 的 schema 显式声明 `x_*` patternProperties 扩展槽时才可使用——未声明扩展槽的 payload kind 不接受任何未知字段（payload schema 的 `additionalProperties: false` 即权威判定）。实现 MUST 在 canonical bytes、存储、转发和 backfill 中保留 schema 允许的 `x_*` 字段，但 MUST NOT 让 `x_*` 字段绕过 capability、schema、policy 或加密约束。需要扩展槽的 payload kind SHOULD 先在对应 schema 登记 `x_*` patternProperties 槽再使用；当前已声明扩展槽的 payload kind 以 schema 为准（Invite 的六个逐 Event payload schema 各自声明该槽）。current-v1 不提供通用 critical-extension carrier；需要 critical 新语义时必须新增或升级具体 kind/schema 并同步登记生产 consumer 与向量。
- 签名和 hash 输入 MUST 使用 canonical JSON。
- `id:<kind>` 在 wire、canonical object、fixture、签名和跨服务引用中 MUST 使用完整 typed ID。数据库内部 MAY 只存 raw id，但在序列化、签名、hash、联邦、sync cursor 和审计回放前必须恢复 `ak:<kind>:` 前缀；不得把数据库主键或表名当作协议 ID 的替代品。
- 前缀由字段的**语义类型**决定，不由承载介质决定。配置、环境变量、数据库、HTTP header 或签名 transcript 不会把裸字符串自动升级成协议 ID；一旦一个值被声明为 `id:<kind>`，它在进入领域模型时就 MUST 已是完整 canonical typed ID，签名与 hash 层 MUST 原样承诺该值，MUST NOT 在签名前后补前缀、去前缀、大小写折叠或接受裸 payload alias。
- 外部标准拥有的标识符保留该标准的 canonical namespace：DID / DID URL 分别使用 `did:<method>:...` / `did:<method>:...#<fragment>`，MUST NOT 为 DID 另加 Arkret typed-ID 前缀。Arkret 从 DID 投影出的稳定身份核是另一个已登记类型 `ak:did_core:<method>:<core>`；字段要求 `did`、`did_url` 或 `did_core_id` 中的哪一种，完全由 schema 决定，不得因它进入签名或数据库而互换。
- 配置字段若会进入 wire、canonical object、签名、hash、联邦或审计语义，MUST 接受并保存完整 canonical 值。例如 `trust_domain` 配置使用 `ak:trust_domain:<scope>`。若实现希望提供只填写 `<scope>` 的运营便利入口，必须使用语义不同且显式命名为 `trust_domain_scope`（或等价的 `*_scope`）的输入，在配置解析边界一次性构造并验证 `trust_domain`；同一个配置键 MUST NOT 同时接受裸 scope 与完整 typed ID 两种 alias。
- 数据库压缩表示必须在 schema 与类型名上显式。名为 `realm_id`、`trust_domain`、`principal_id` 等 canonical identity 列 SHOULD 保存完整 wire value；若只保存载荷，列 / 类型 MUST 命名为 `realm_token`、`trust_domain_scope`、`did_core_payload` 等非 canonical 名称，并由唯一 storage adapter 无损恢复。恢复之前的内部值 MUST NOT越过 storage adapter，也不得参与签名、hash、日志、错误响应或跨服务比较。
- 当 `id:<kind>` 出现在 JSON object key 中时，它仍然属于 wire value；例如 `messages.{principal_id}.{device_id}` 中的 `{device_id}` MUST 使用完整 `ak:device:<uuid>`，MUST NOT 写成局部别名如 `dev_a` 或 `a`。
- `summary` / `description` 命名约定：canonical object 或 projection row 的短摘要、列表预览、聚合摘要使用 `summary`；Strand 的用户可读短摘要放在 `metadata.summary` 或 `encrypted_metadata`，不得作为顶层 `summary`。原因说明、补充说明、长说明或 schema / registry 元数据说明使用 `description`。OpenAPI 自身标准关键字 `summary` / `description` 按 OpenAPI 语义使用。若字段承载人类可读名称，canonical object 默认使用 `title`；Strand 使用 `metadata.title` 或 `encrypted_metadata`，Actor / user-facing identity profile 使用 `display_name`；`name` 只用于外部协议、加密算法、service surface 或 registry 内部 label，不作为 Realm / Space / Strand 等 canonical object 的显示名。
- Projection row 若表达 canonical object 的同一概念，MUST 沿用 canonical 字段名（例如 `title`、`summary`、`avatar_blob_ref`、`owning_organization_ids`），MUST NOT 另起 `name`、`avatar`、`official_organization_ids` 等别名。若服务需要返回渲染友好的派生对象，字段名 MUST 明确带 projection 语义并有 schema；v1 默认不定义通用 `avatar` projection，头像引用使用 `avatar_blob_ref`。
- `_id` / `_ref` / `_did` 后缀约定见 §2.1。简要规则：Arkret-owned identifier 使用“语义角色 + 可验证主体类别 + carrier 后缀”；`DidCoreId` 主体按合同使用 `_principal_id` / `_service_id` / `_station_id` / `_hardware_module_id`，closed `AccountId` / `ActorId` 的 carrier-explicit 形态分别使用 `_account_id` / `_actor_id`，已登记的完整 identity role 可在 terminal 唯一闭合时保留通用 `_id` / `_ids`。W3C DID / generic URI identity / key selector 分别使用 `_did` / `_uri` / `_kid`，HTTP(S)/WS(S) 网络 locator 使用 `_url`。`holder` / `controller` 不得使用省略类别与 carrier 的裸字段。因果 / proof / schema-profile / content-addressed / polymorphic reference 使用 `_ref` / `_refs`。字段名只如实表达 schema/registry 已闭合的类别与 carrier，不能反过来充当分类证据。
- 分类字段使用以下四条互斥命名轴；机器许可与精确上下文以 [`classification-field-registry.json`](../../artifacts/registry/classification-field-registry.json) 为准：

  | 轴 | 规范语义 | 命名要求 |
  | --- | --- | --- |
  | `kind` | Arkret 自有 discriminator、routing 维度、registry family、互斥 shape 选择与 reducer/projection 分派。开放或闭合 value set 均可；是否开放由 schema/registry 另行声明。 | 裸 `kind` 或 `*_kind` / `*_kinds`。Arkret 自有分类默认使用此轴。 |
  | `type` | 仅用于直接继承 IANA/HTTP、W3C DID/VC/Data Integrity、MLS、WebRTC 等外部标准的字段名、值集和分派语义。Arkret 不得添加私有值、改写含义或把它变为 Arkret 主分派轴。 | 裸 `type` 或 `*_type` / `*_types`；每个使用点必须在 classification registry 以精确 schema/doc path 登记外部锚点。 |
  | `class` | 有限、无序、闭合，且不选择互不兼容对象 shape 的分类。 | `*_class` / `*_classes`；必须可解析到 finite enum/const，不能表示自由标签或开放 registry。 |
  | `tier` | 有限且存在严格全序，比较结果会改变协议判定的等级。 | `*_tier`；必须登记完整顺序与比较语义。v1 当前仅保留 `risk_tier`，顺序为 `low < medium < high`。 |

  四条硬判据（normative）：

  1. **Selector 判据**：任何 wire 字段若被可执行 artifact 的 `{"kind":"select","selector":"<path>"}` 引用，作为主 typed current result subject 分类维度，或在 discriminated schema 分支中选择互斥 Arkret shape，其字段名 MUST 为 `kind` / `*_kind` / `*_kinds`。
  2. **闭集判据**：`*_class` / `*_classes` MUST 直接或经 `$ref` 解析到有限 enum/const；registry/fixture-only context MUST 在 classification registry 明列 `allowed_values`。自由字符串、开放 registry 或 `additionalProperties` taxonomy 不得使用 class 轴。
  3. **外部锚点判据**：wire、normative canonical JSON 与 Arkret 可执行 artifact DSL 中的 `type` 轴字段 MUST 有逐路径外部锚点，且 `dispatch_authority="external_standard"`、`arkret_extensions_allowed=false`。真正的 JSON Schema `type` vocabulary keyword 由 parser 上下文排除；Arkret mini-schema 的值形状声明使用 `value_shape`。
  4. **同轴与顺序判据**：同一概念不得并存不同后缀轴；无法从 stem 判断的正交概念必须用 `semantic_axis` / `distinct_from` 显式声明。任何 tier 字段必须有有限值、严格全序和比较语义。

  因而 Event Envelope 的唯一事件 discriminator 是 `kind`；`morph_kind`、`service_kind` 与 `claim_kind` 均为 Arkret 自有分派。MLS `proposal_type`、WebRTC session description `type`、W3C DID/Data Integrity raw object `type` 与 IANA/HTTP `media_type` / `content_type` 只在 registry 登记的精确路径保留，不形成全局例外。
- 时间边界命名约定：有效期下界统一使用 `not_before`，有效期上界统一使用 `expires_at`；缓存或派生结果的失效时间使用带领域前缀的 `cache_expires_at`。新增 wire 字段不得使用 `valid_from`、`valid_until` 或 `not_after` 作为同义别名。**已登记外部标准命名例外**：[`calendar-event.md` §4.2](./calendar-event.md) 的 recurrence 终止字段名为 `until`，不是 `expires_at`。它不是绝对 instant，也不是对象级有效期上界，而是 RFC 8984 `RecurrenceRule.until` 的 snake_case 映射——按事件 `timezone` + `tzdb_version` 解释的 local 终止界，与 occurrence 的 local start 做 `<=` 比较。沿用外部标准名是有意取舍，MUST NOT 改名为 `expires_at`；反之，新增的对象级有效期上界字段仍 MUST 使用 `expires_at`，MUST NOT 借用 `until`。新增的 date-time wire 字段一律 MUST 使用 `_at` 形态；v1 不保留裸 `timestamp` 字段名的 interop 例外。
- `state` / `status` / `stage` 命名约定：`state` 表示 canonical object 的物理生命周期；`stage` 表示 Strand / Morph 等业务进度轴；`status` 只用于账号、session、delivery、外部过程或 registry 条目状态，不用于表达 object lifecycle 目标值。对象 lifecycle payload **MUST NOT** 携带目标 `state`：§5.2 由 event kind 本身确定目标值，reducer 按 `object_lifecycle_state` 产出，payload 只指名目标对象与可选理由。`target_state` 这个字段名保留给 kind 本身**不能**确定终态的 FSM 型 lifecycle（v1 只有 Invite 一例：一条 `ak.invite.revoke` 可落 6 个不同终态），不得用于物理 `state` 轴。
- `created_by` / `creator_*` 命名约定：materialized object metadata 使用 `created_by` / `updated_by`，由 reducer 从 Event `actor_id` 派生。`creator_*` 只保留给外部协议或加密 transcript 自身的创建者 tuple，不得作为 object 创建主体字段的别名；v1 未登记任何 `creator_*` wire 字段，新增字段不得引入该形态。
- 哈希字段命名三词词汇表：算法/函数族选择器使用 `<noun>_algorithm`（枚举字符串，例如 `digest_algorithm: "sha256"`）；任意字节的不透明哈希输出使用 `<noun>_digest`（wire 形态必须是自描述 `<alg>:<hex>`）；树状 / Merkle / 累加器的根使用 `<noun>_root`（同样是 `<alg>:<hex>`，区别在于单独验证还需配套包含证明）。**wire 字段名 MUST NOT 以"hash"结尾（不论是 `_hash` 后缀还是 `hash_profile`、`hash_algorithm` 等同义形态）**；算法选择器只能使用 `<noun>_algorithm`，字节输出只能使用 `<noun>_digest`。复合 commitment 对象使用 `<noun>_commitment`：外层名描述语义，内部以 `algorithm` + `root` 或 `digest` 表达字节材料；外层 MUST NOT 再追加 `_digest` 后缀。Event proof 绑定 canonical Event bytes 的字段名是 `event_digest`；非 Event 通用 detached proof 使用 `payload_digest`，其说明必须写明被 digest 覆盖的 canonical payload。
- 签名 proof 中表示签名 key DID URL 的字段统一为 `verification_method`，不得使用 `signed_by`。协议级密钥标识使用 `key_id`；JOSE/JWK 结构可保留标准 `kid` / `alg`。若 schema 显式定义紧凑 detached signature tuple `{alg,kid,sig}`，短字段 `sig` 只允许出现在该 tuple 内；协议对象的普通签名字段使用 `signature` 或带角色的 `<role>_signature`。若需要表达消息或通知中的发送主体，使用带角色的 `sender_actor_id`；展示名称使用 `sender_actor_display_name`，不得用裸 `sender` 承载 DID。
- `recipient_id` 与 `audience` 不可互换：前者是物理路由目标 service DID，后者是密码学 transcript / proof 的受众绑定。即使 `audience` 只有一个 DID，也不得替代 `recipient_id`；反之亦然。 对于 schema 已闭合为单一稳定责任主体 `DidCoreId` 的受众，使用 `audience_id`（例如 SessionGrant 与 Applet managed-actor request/bundle）；其类别、受众唯一性与身份绑定必须由各对象合同明确，不得因通用 proof 存在 `audience` 就去掉 `_id`。通用 proof 的字符串／数组 `audience` 不构成 typed identity 字段的命名例外。
- `scope` 命名约定：当 scope 是该对象自身的边界字段时，wire schema 使用裸 `scope`（与对象自身 `id` 的命名规则相同），例如 `ak.schema.erasure_receipt.v1.scope`、`ak.schema.erasure_verification_stub.v1.scope`。当字段引用外部对象、表达子结构中的特定作用域，或同一 payload 同时出现多个 scope 语义时，必须用领域前缀说明形态与用途，例如 `read_scope`、`event_range`、`match_scope`、`claim_scope`、`agent_key_scope`、`consent_scope`、`effective_scope`、`extension_scope`、`constraint_scope`、`policy_scope`、`search_scope`、`relation_scope`。Registry 元数据若表示条目适用范围，可继续使用 `scope`。
- 诊断命名约定：机器可枚举的失败 / 恢复 / reset 原因使用 `reason_code` 或带领域前缀的 `*_reason_code`；人类可读自由文本使用 `reason` 或 `description`。受控枚举不得命名为 `reason`。
- ID kind 与 wire prefix 必须使用完整 snake_case 名称，不得使用缩写前缀（例如使用 `ak:notification:`、`ak:device_message:`、`ak:moderation_queue_item:`、`ak:request:`、`ak:transaction:`）。该要求同样适用于 special form：special form 的 wire segment MUST 由其 `wire_form` 唯一解析，且 MUST 与 snake_case `kind` 逐字相同——**不存在拼写例外**。`membership_compensation_delegation` 的 wire form 固定为 `ak:membership_compensation_delegation:`。artifact lint 对 segment ≠ kind 直接失败。
- **schema → registry 封闭（normative）**：任何 schema validation carrier（`pattern`，含分组 / union 分支；`const`；`enum`；以及经本地 `$ref` 复用的同一形状）实际可接受的每一个字面 `ak:<segment>:` 前缀，MUST 唯一命中 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 中某个 `id_kinds` 或 `special_forms` 行由 `wire_form` 解析出的 canonical wire prefix。artifact lint 执行该封闭；未登记前缀是合同缺陷，不是可以留待运行时容忍的写法。反过来，纯关联用途的有界 opaque 字符串（例如 `ServiceRegistrationEnsureRequestBody.idempotency_key`）MUST NOT 借用 `ak:` 命名空间：它不进入 typed-ID parser，也不得成为该 operation 的第二个幂等 authority——注册 identity 是 canonical `(service_kind, public_base_url)` 唯一约束，幂等机制以 operation registry 的 `idempotency_mechanism` 为准。
- typed current result 状态模型字段统一使用 `domain reducer`，封闭取值为 `current-value projection`、`commit-ordered projection`、`keyed-set projection`、`counter`、`append-only projection`；执行域由 `execution=data|security` 明示，物理值形态由 `value_shape=register|set|counter|log` 明示。不得用 CAS、业务状态机或旧的 register 别名扩展状态模型；新增模型必须先完成合并/顺序语义、op schema、profile gate 与 conformance vector 闭包。

  **`keyed-set projection` 的 join（normative，本节是唯一真源）**：该模型的值是一个 **tagged 断言集**。每个元素的稳定 tag 是 [`event-and-patch.md` §2.4.2](./event-and-patch.md) 的 canonical Event dot `<event_id>:<write_index>`，MUST NOT 退化为裸 `event_id`；元素值是产生它的那条已接纳 Event 的完整 payload，投影不拼装、改名或裁剪字段。join 是 **dot 集合并**，因此可交换、可结合、幂等，且与 `RealmCommit` 的执行顺序无关——同一 dot 重复投影是 no-op。**每条参与该 family 的 Event 都只能 `keyed_set_add`**：撤销语义 MUST 表达为「再加一条断言」而不是删除既有 dot，否则并发的 (add, remove) 会丢掉一侧，审计视图无法重建，且 `keyed_set_remove_observed` 只删冻结前态里存活的 dot，会把并发对静默收敛成单侧。`keyed_set_remove_observed` 与 `keyed_set_remove_dots` 只用于由**同一 writer** 显式指名、不承载并发断言语义的集合。**断言者与极性不是元素字段**：reader MUST 从 dot 所指 Event 的签名 envelope（`actor_id` 与 `kind`）读出，因为同一 family 的两个 kind 可能产生逐字节相同的 payload。集合之上的一切——排序 roster、remove-wins 折叠、计数、冲突视图——都是**读侧折叠**，MUST NOT 成为第二份存储状态或新的 `domain reducer` 取值。使用该模型的 family MUST 在自己的正文节里给出这些读侧折叠，并 MUST NOT 重新定义此处的 join。
- Event kind 动词使用动词原形表达 reducer 动作（如 `authorize`、`revoke`、`rotate`、`tombstone`）；只有纯状态通告或外部标准名有明确理由时才可使用过去分词。**每个 active event kind MUST 在 `contract-registry.json#/event_kind_registry.event_kinds[]` 登记终段形态 `verb_form`**，取值为封闭三值 `base`（动词原形）/ `past_participle`（过去分词）/ `not_applicable`（终段是名词化 facet、状态名或外部标准专名，不表达动词）；`event-kind-registry.json` 的同名字段是该登记的生成投影，不是第二个真源。`verb_form: "past_participle"` MUST 同时携带非空 `verb_form_rationale`；`base` 与 `not_applicable` MUST NOT 携带该字段，伪造例外理由与漏登记同样不可接受。判据是语义而非拼写：`bound` 与 `withheld` 都是不规则过去分词，任何 `ed` / `en` 后缀扫描都会漏项，因此英文后缀启发式只能作为 review 提示，MUST NOT 充当 correctness gate。下表是同一登记的可读投影，一 kind 一行，由 artifact lint 与 registry 双向闭合：

  | kind | 过去分词形态的语义理由 |
  | --- | --- |
  | `ak.audit.accessed` | 纯审计通告，记录敏感访问已经发生的事实。 |
  | `ak.capability.derived` | 记录 capability 派生已经完成的结果。 |
  | `ak.contact.accepted` | Contact round 已进入接受终态的通告。 |
  | `ak.contact.rejected` | Contact round 已进入拒绝终态的通告。 |
  | `ak.contact.requested` | Contact round 已进入请求状态的通告。 |
  | `ak.direct_conversation.bound` | 四 Event founding unit 已建立绑定的事实通告。 |

- **Facet 值设置事件的命名形态（normative）**：写入单个 Realm 配置切面的 event kind 使用**裸名词形态** `ak.<scope>.<facet>`（如 `ak.realm.join_rule`、`ak.realm.history_access`、`ak.member.state`、`ak.call.state`），不追加 `.set`。`.set` 后缀**只保留**给两种情形：(a) 需要与同名 patch 路径区分（`ak.<kind>.stage.set` 对应 `stage` 字段，而 `ak.<kind>.update` 的 patch 路径 MUST NOT 触及 `stage`）；(b) 需要独立 capability 切分（`ak.strand.watch.set` / `ak.policy.set` / `ak.account_data.set` / `ak.rsvp.set`）。两种形态都是 canonical，选择依据 MUST 是上述判据而非作者偏好；新增 facet event 默认取裸名词形态。
- Capability action 命名约定：
  - **`ak.<entity>.<verb>` 是默认形态**，对应 `target_event_kinds` 中的一个或多个 reducer-input event kind。新增 action 默认 MUST 与被授权 event kind 同名；只有 [`authz/capabilities.md` §5.0](../authz/capabilities.md#50-action--event-kind-偏离类别normative-reference) 登记的偏离类别允许不同名。授权、IAM 工具、SDK 生成和 audit 解析 MUST 读取 capability-action-registry 的 `target_event_kinds`，不得从 action 字符串拆解推断 event kind。
  - **通用 `ak.object.<verb>`**（如 `ak.object.read` / `ak.object.archive` / `ak.object.restore` / `ak.object.stage.set`) 只允许在 Realm-wide admin 或跨实体审计 grant 中使用 (`match_scope` 不限定单一实体 ID); 对单一实体的常规授权 MUST 使用专属 `ak.<entity>.<verb>` (例如 `ak.strand.archive`)。这是为了让 grant author 在最小作用域内表达意图, 同时保留 admin 路径使用通用 action 的能力。
  - **后缀 `.own` / `.others`**: 不带后缀的 action 默认作用域不限定 "creator = grantee"; 加 `.own` 表示 "仅 actor 自己创建的对象" (例如 `ak.message.revise.own`, `ak.message.redact.own`); 加 `.others` 表示 "允许操作他人创建的对象", 通常 risk_tier=high。三种形态 MUST 在 capability-action-registry 中分别登记, 不得当作通配等价。

#### 2.0.1 全域命名判据（normative）

- <!-- rule_id: NC-BOOL-001 --> **R1 布尔许可与义务**：许可字段 MUST 使用 `<axis>_allowed`，强制义务 MUST 使用 `<axis>_required`；wire boolean MUST NOT 使用 `allow_*`、`require_*`、`requires_*`、`deny_*`、`force_*` 或负极性 `no_*` / `disallow_*`。`include_*` 只用于请求侧投影开关；`*_present` 只用于 fixture/诊断，或逐路径登记的不回显原材料审计摘要。
- <!-- rule_id: NC-COUNT-001 --> **R2 计数与长度**：元素个数 MUST 使用 `_count`，字节数 MUST 使用 `_bytes`，字符/码位数 MUST 使用 `_chars` / `_code_points`；Arkret wire、registry 语义字段与 fixture 断言 MUST NOT 使用 `_len`、`_length` 或 `_size`。`cardinality` 只用于 registry 的关系基数元数据。
- <!-- rule_id: NC-ENUM-001 --> **R3 符号枚举值**：Arkret 自有符号型枚举 MUST 使用 snake_case。只有外部规范定义了该字面值且 Arkret 必须逐字节往返时才可例外，并须登记外部章节/codepoint；数值区间、URI 与 media type 按各自词法。
- <!-- rule_id: NC-TYPE-001 --> **R4 类型名**：JSON Schema `$defs` 键 MUST 使用 snake_case；OpenAPI schema component 与规范自有的概念类型名 MUST 使用 PascalCase。PascalCase 中的缩写 MUST 按普通单词折叠大小写（例如 `MlsCommitSubmission`、`DidOperationSubmitOutcome`），不得写成连续全大写片段（例如 `MLS…`、`DID…`）；外部标准要求逐字引用的类型名不在此改写。承担结构包装角色的末词只能是 `RequestBody`、`Outcome`、`View`、`Row`、`List`、`Envelope`、`Ref`、`Problem`；领域主语不受包装词封闭表约束。`service-operation-dtos.schema.json` 作为 OpenAPI DTO 镜像是已登记结构例外。
- <!-- rule_id: NC-CODE-001 --> **R5 机器原因码**：机器可枚举原因 MUST 使用 `reason_code` / `<domain>_reason_code`，协议标准错误码 MUST 使用 `error_code`；`failure_code` / `rejection_code` 等中间形态禁止。
- <!-- rule_id: NC-EVIDENCE-001 --> **R6 证据材料名词**：`proof` 是可独立验证的密码学命题材料；`attestation` 是第三方对范围/状态的签发断言；`receipt` 是请求状态回执；`witness` 是背书角色；`commitment` 是集合/树承诺；`transcript` 是签名/KDF 的规范输入。`evidence` 仅用于可容纳至少两类上述材料的多态容器。
- <!-- rule_id: NC-ARTIFACT-001 --> **R7 artifact 文件与 provenance**：artifact 文件名 MUST 为 kebab-case。类别词按数据形态使用：`registry`、`table`、`graph`、`report`、`index`、`digests`、`fixture`、`manifest`、`probes`；provenance 由真实数据流决定，canonical artifact 使用 `source_of_truth: true`，派生 artifact 使用 `source_of_truth: false` 且声明非空 `generated_from` / `generated_by`。
- <!-- rule_id: NC-SET-001 --> **R8 集合前缀**：allowlist/denylist array/set 的唯一反义词对是 `allowed_` / `denied_`；`permitted_` / `forbidden_` / `blocked_` / `banned_` 禁止用于这类集合。scope 差异 MUST 进入 role prefix；`supported_`、`accepted_`、`advertised_`、`declared_` 分别表示实现能力、运行时接受、对外通告、profile 声明，不得同域混用。
- <!-- rule_id: NC-LEXEME-001 --> **R9 canonical 领域词、缩写与命名域限定**：Arkret 自有的 wire 字段、JSON Schema `$defs`、OpenAPI / 规范概念类型、符号枚举、registry symbol、profile / operation / event / schema ID、fixture wire specimen、normative JSON 示例与公开 SDK API，MUST 使用完整 canonical 领域词；普通英文单词不得因长度而截短。缩写只有四种 authority：外部标准或算法的 canonical initialism、[`overview/glossary.md`](../overview/glossary.md) 明确定义的 Arkret initialism、已登记结构词（v1 为 `id` / `ref`）以及带精确外部锚点的逐字 literal。具体 canonical word、禁用 alias 与非 contract 边界由 [`canonical-lexeme-registry.json`](../../artifacts/registry/canonical-lexeme-registry.json) 唯一登记；新增 compact token 必须先进入其中一个 authority，MUST NOT 由调用点自行发明。`organization` 是完整领域词，`org` 不是 initialism：Arkret 自有名称 MUST 使用 `organization_membership` / `OrganizationMembershipClaim` / `represented_organization_id`，MUST NOT 使用 `org_membership` / `OrgMembershipClaim` / `represented_org`。Internet `.org` 域名、opaque/external identifier payload、changelog 与明确的 negative case 不属于 Arkret contract name，必须保持原值。字段若承载 Organization DID，还须叠加 §2.1 的 identifier 规则并使用 `organization_id` 或 `<role>_organization_id`；`organization` 只可命名嵌入的 Organization value，不能作为 DID 字段的省略写法。Arkret 是本规范内部名称的默认命名域；Arkret 自有字段、类型、claim kind 与 symbolic value MUST NOT 再加冗余的 `arkret_` / `Arkret` 产品前缀，因此使用 `organization_membership_credential` / `OrganizationMembershipCredential`，不得使用 `arkret_organization_membership_credential` / `ArkretOrganizationMembershipCredential`。只有外部所有者的扩展点、共享全局命名空间、密码学 domain-separation label，或确需区分 provider/backend 的 discriminator 才可带产品/协议限定词，而且精确名称与边界必须先登记；外部语义优先使用其稳定 authority 名（例如 `oidc` / `scim` / `mimi` / `matrix`），不得为了假设的未来冲突先加泛化前缀。`ak.` symbolic namespace 与 `ak:` typed-ID namespace 是全局序列化协议命名空间，不属于冗余产品前缀。`external_organization_authorization` 中的 `external` 描述相对受控 Realm 的协作主体角色，不是来源命名域，因此不受本判据删除；若它将来表示某个外部协议定义的对象，则必须改用该协议的已登记 authority，而不是把 `external` 当作万能 namespace。规范、构件和实现 MUST 只接受 registry 登记的 canonical 名称。
- <!-- rule_id: NC-HASH-001 --> **既有 hash 词汇判据**：`_hash` / `_hashes`、`hash_profile`、`hash_algorithm` 在 Arkret wire 中禁止。本判据同时适用于 **Arkret 自有类型名**（JSON Schema `$defs` 键与规范概念类型名）：承载自描述摘要的 canonical 类型名是 `digest`，MUST NOT 命名为 `hash`——否则规则会在同一份文档里既禁止又使用同一个词。RFC 9420 / did:webvh 等逐字面外部字段只按登记的精确路径 + JSON Pointer 保留，不得使用按名全局白名单。
- <!-- rule_id: NC-CLASSIFICATION-001 --> **四轴分类后缀**：`kind` / `type` / `class` / `tier` 的逐字段许可、闭集与异轴声明由 [`classification-field-registry.json`](../../artifacts/registry/classification-field-registry.json) 唯一登记，轴级判据表只引用该 registry，不复制条目。

### 2.1 Identifier 字段命名约定（normative）

本节适用所有持有 protocol identifier、DID material 或 reference material 的 wire 字段。Arkret-owned identifier 字段名按 §2.1.3 由**语义角色、可验证主体类别与 carrier 后缀**共同确定；字段名必须如实表达已由 schema/registry/admission evidence 闭合的类别，但不能代替这些约束或证据，也不表达"硬归属 vs 软导航"、权限传播、同步传播、retention 级联或 E2EE key 级联。后者 MUST 由 role、JSON Schema `description`、subject-class 约束和对象专属章节共同定义。

**Identifier value category 表（normative，有限且互斥）**：每个 identifier 字段 MUST 恰好属于下表九类之一。类别的真源是 schema 解析后的 terminal 约束（递归展开本地与跨文件 `$ref`、`oneOf` / `anyOf` 分支与 `pattern`）；字段名只负责如实表达该类别，MUST NOT 反过来决定类别，实现也 MUST NOT 仅凭字段名推断值的种类。

| 类别 | 值形态与类型来源 | 允许的字段名形态 | 可否作为 identity / authorization key |
| --- | --- | --- | --- |
| `typed_object_id` <!-- identifier_category: typed_object_id --> | `ak:<kind>:<payload>`，其中 kind 或 special form 已登记于 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json)；schema 以指向 `common-ids.schema.json` 的 `$ref` 或等价 anchored pattern 声明 | 对象自身使用 `id`；引用他者使用 `<kind>_id` / `<role>_<kind>_id` / `expected_<role>_<kind>_id`（详见 §2.1.1） | 是。它是协议对象主键，可直接作为授权主体、去重键与签名 transcript 中的身份 |
| `responsibility_identity_material` <!-- identifier_category: responsibility_identity_material --> | Arkret 的 `did_core_id`、由两个 core 组成的 closed `AccountId`、以 discriminator 封闭的 `ActorId`，或注册、resolution、method evidence 中使用的 W3C DID / DID URL；DID 的具体表示由下方正交 profile 表决定 | 稳定主体使用 `_id`；DID 使用 `did` / `<role>_did(s)`；DID URL key selector 使用 `verification_method` / `<role>_verification_method` | `did_core_id`、AccountId 与 ActorId 可以。DID 必须先经 adapter 投影并绑定 expected core；DID URL 只选择 key |
| `registry_catalog_symbol` <!-- identifier_category: registry_catalog_symbol --> | 命名某个 registry 条目的符号，canonical 形态通常是 `ak.<symbol-path>`；schema 以 anchored `^ak\.` pattern、`const` 或该 registry 的闭合枚举声明 | 保留各 registry 的 canonical 字段名，例如 `operation_id`、`profile_id`、`schema_id`；新增 catalog 字段 SHOULD 使用 registry 自有名或 `*_symbol` | 否。它命名目录条目而不是对象实例，MUST NOT 作为授权主体或对象主键使用 |
| `opaque_correlation` <!-- identifier_category: opaque_correlation --> | 有界 opaque 字符串（MUST 由 `pattern` 或 `maxLength` 限定上界），由某一方铸造用于关联一次请求、挑战、传输、租约或 transcript 位置；MUST NOT 复用 typed-ID 词法空间，即值 MUST NOT 以 `ak:` 开头 | 保留领域既有名，例如 `request_id`、`challenge_id`、`transaction_id`、`<noun>_round_id`、`*_handle` | 否。它只承载关联语义，MUST NOT 单独决定授权、身份归属或 envelope 去重 |
| `transport_idempotency_key` <!-- identifier_category: transport_idempotency_key --> | 传输层重复提交坐标，有界 opaque 字符串；不指向任何协议对象，也不进入对象身份 | MUST 使用 `idempotency_key`，MUST NOT 使用 `_id` 后缀，MUST NOT 复用 typed-ID 词法空间 | 否。只用于同一请求的重复提交判定，MUST NOT 进入身份、授权或因果判定 |
| `external_system_identifier` <!-- identifier_category: external_system_identifier --> | 词法空间由外部标准或外部系统拥有并逐字保留的标识符，例如 RFC 9420 MLS group id、did:webvh `versionId`、OAuth/OIDC `client_id`、MIMI / Matrix 与媒体后端句柄 | 保留外部原名，MUST NOT 改写为 Arkret typed-ID 形态，也 MUST NOT 追加 `ak:` 前缀 | 否。只在该外部绑定内部有效，Arkret MUST NOT 把它解析成 typed ID 或授权主体 |
| `document_local_symbol` <!-- identifier_category: document_local_symbol --> | 只在承载它的对象、策略或 registry 行内可解析的符号；schema 以有界 pattern 或闭合枚举声明；MUST NOT 复用 typed-ID 词法空间，即值 MUST NOT 以 `ak:` 开头 | `rule_id`、`gate_id`、`question_id`、`entry_id`、`widget_id` 等 | 否。离开承载对象即无意义，MUST NOT 作为授权主体或跨对象引用 |
| `unregistered_object_identifier` <!-- identifier_category: unregistered_object_identifier --> | **待收敛类别**：字段确实标识一个持久 Arkret 对象，但该对象 kind 尚未登记于 `id-kind-registry.json`，schema 也未固定 typed pattern；收敛完成前值 MUST NOT 以 `ak:` 开头，其载荷段也 MUST NOT 内嵌 `ak:` | 现状字段名保留；收敛方向 MUST 是登记 kind 并改用 typed 形态，或改判为上述某个已闭合类别 | 否。收敛完成前 MUST NOT 作为授权主体 |
| `non_identifier` <!-- identifier_category: non_identifier --> | **待收敛类别**：字段值根本不是标识符（模式枚举、描述性 object、计数器等），`_id` 后缀是命名缺陷 | 无允许形态；收敛方向 MUST 是改名为如实表达语义的字段名 | 否 |

新增或修改 identifier 字段时：类别 MUST 能由 schema terminal 约束唯一判定；只有类型无法唯一判定的路径才逐条登记到 `tools/identifier-classification-registry.json`，MUST NOT 为已由 `$ref` 明确的字段再复制一份人工登记。`unregistered_object_identifier` 与 `non_identifier` 不能用于新增字段；canonical wire 每个语义只允许一个字段名与一个 schema terminal。

`ak:` 词法空间由 `typed_object_id` 与 `responsibility_identity_material` 两类独占，这是本表"互斥"成立的前提：其余任何类别的 identifier 字段，其 schema terminal 约束 MUST 使值不可能以 `ak:` 开头——只声明了 `pattern` 却允许 `ak:<任意kind>:<载荷>` 的字段等于同时满足两行判据。`description` 散文与 `identifier-classification-registry.json` 的 `reason` MUST NOT 用来替代该 pattern 约束，实现也 MUST NOT 依赖它们判断值的种类。反向亦然：`ak:<kind>:` 前缀只有在 kind 已登记于 `id-kind-registry.json` 时才合法，MUST NOT 引入"kind 已注册即可在非 typed-ID 字段上复用该前缀"这类条件式例外。

**DID representation profile 表（normative，与上表正交）**：

| profile | terminal invariant | 主要用途 | 可否直接作为稳定授权主体 |
| --- | --- | --- | --- |
| `did_core_id` | `^ak:did_core:[a-z0-9]+:[^\s/?#]+$` | 持久主体引用、授权、相等、索引 | 是 |
| `did` | `^did:[a-z0-9]+:[^\s/?#]+$` | 注册、resolution、method evidence | 否；必须投影并与 expected core 绑定 |
| `did_url` | `^did:[a-z0-9]+:[^\s#?]+#[A-Za-z0-9._:-]+$` | verification method / key selection | 否 |

每个 DID-material property MUST 在 semantic category 与 representation profile 两轴上各有且仅有一个判定。外部标准 literal object 可以在第一轴属于 `external_system_identifier`、同时在第二轴属于 `did` 或 `did_url`；两轴不得压成一张互斥表。DID 三类表示由 resolved terminal constraint 决定，实现不得凭字段名推断；URI/URL 的后缀选择还必须结合 locator 与 identifier/reference 语义，不能从 JSON Schema `format: uri` 机械推出 `_uri`。

**词法下界（normative）**：上一段的"MUST 使值不可能以 `ak:` 开头"是一条对 terminal 约束的要求，
不是对散文的要求。每个**不拥有 `ak:` 命名空间**的类别（`registry_catalog_symbol`、
`opaque_correlation`、`transport_idempotency_key`、`external_system_identifier`、
`document_local_symbol`、`unregistered_object_identifier`）的 identifier terminal MUST 提供
`pattern`、`const` 或闭合 `enum`，使"拒绝 `ak:` 前缀"可以**逐 occurrence 机械证明**。
`maxLength` 只限制长度，MUST NOT 单独作为词法下界——它对命名空间不作任何断言。
裸 `type: "string"`（无 pattern / const / enum）判不出类别：按 §2.1 表的判据它同时满足
`opaque_correlation`、`document_local_symbol` 与 `unregistered_object_identifier` 的描述，
也不排除 `typed_object_id` 的值形态，因此本表自称的"有限且互斥"对它不成立。

共享下界是
[`string-profiles.schema.json#/$defs/non_typed_identifier_floor`](../../artifacts/schemas/string-profiles.schema.json)，
其内容恰好是否定前瞻 `^(?!ak:)`：它**只**证明该值不是 `ak:` typed id，不收窄字符集，
因为具体收敛方向（登记 kind 改用 typed 形态，或收紧为更严的 opaque profile）按对象族逐字段裁决，
下界不得替这些字段预先选定最终形态。

门禁 MUST **fail closed**：`check_typed_id_namespace_disjointness` 对既不能证明拒绝、
也不能证明接受的 occurrence 直接失败，MUST NOT 把"未判定"当作"已通过"——后者会让 schema
层继续合法承载 `ak:<任意kind>:<任意载荷>` 而 release gate 一言不发。`_id` 后缀的
`type: "object"` 描述符不是 identifier terminal，本要求对它不适用（其成员各自受本要求约束）。

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
- Snapshot manifest 自身也使用 `id`；`realm_state_snapshot_ref` 只在其他对象、chunk payload、challenge 或 API hint 指向该 manifest 时使用。
- Event Envelope、Receipt、Attestation、Key Backup、Applet 等协议 artifact 或非通用 materialized object MAY 使用 `<artifact>_id` 作为自身标识（例如 `event_id`、`receipt_id`、`attestation_id`、`backup_id`、`applet_id`），因为这些对象经常与 `realm_id`、`actor_id`、`policy_id`、`device_id` 等并列并进入签名 transcript，需要在混合上下文中消歧。该例外不得反向用于 Realm / Space / Strand / Message / Morph / Relation / View / Policy / Actor Profile 等普通 canonical object。
- 单一具体 kind MUST 在字段名中出现 kind slug，例如 `space_id`、`parent_space_id`、`scope_circle_id`、`policy_id`、`retention_policy_id`。
- protocol responsibility subject 的 carrier 与可验证主体类别必须同时反映在字段名：principal/service/Station/hardware module 的 `DidCoreId` 分别使用 `<role>_principal_id` / `<role>_service_id` / `<role>_station_id` / `<role>_hardware_module_id`；完整 account 使用 `<role>_account_id: AccountId`；account-or-service actor 使用 `<role>_actor_id: ActorId`。`actor_id`、`principal_id`、`agent_id` 等主体词本身已闭合 carrier 的既有 canonical 字段继续保留。
- `DidCoreId` 只提供稳定 core carrier，不证明它属于 principal、Station、其它 service 或 hardware module。主体类别必须先由 schema/registry 与 admission evidence 闭合，字段名随后如实表达；需要实际解析 DID 时另用 `<role>_did`。`holder` / `controller` 是高风险责任角色，必须使用上述显式形态，禁止裸名。
- Event payload 若写入某个 materialized object / projection 字段的值，payload 字段名 MUST 与该物化字段同名。操作目标、CAS expected head、audit target、selector target 等事件操作角色 MAY 加 role prefix，例如 `space_id` 与 `expected_parent_space_id`。

#### 2.1.2 `_ref` / `_refs`

`_ref` / `_refs` 只用于 reference material，而不是单一具体 object kind 字段。允许类别：

- Event / RealmCommit / typed current result / Snapshot / Receipt 等 finality、state 或证明引用：`commit_ref`、`result_selector`、`realm_state_snapshot_ref`、`poll_event_ref`。
- Blob 或 content-addressed 引用：`blob_ref`、`avatar_blob_ref`、`thumbnail_blob_ref`。
- Schema / Profile / Feature 引用：`schema_refs`、`profile_ref`、`feature_ref`。
- Proof / evidence / transcript 引用：`evidence_ref`、`proof_ref`、`service_acceptance_ref`、`policy_event_ref`。
- Polymorphic reference：字段允许多个 protocol kind、DID、content-addressed value 或 hash 形态时使用 `_ref`，例如 `target_ref`、`object_ref`、Relation 的 `from_ref` / `to_ref`。

新增字段若只允许一个具体 canonical materialized object kind，且不是上述因果、proof、schema/profile、content-addressed 或 profile-scoped reference，MUST 使用 `_id` 而不是 `_ref`。

#### 2.1.3 角色、表示后缀与主体类别

<!-- rule_id: NC-IDROLE-001 --> **角色 + 主体类别 + carrier 后缀（normative）**：Arkret-owned identifier 字段由三个不可互相替代的轴组成：responsibility role 回答“承担什么职责”，subject class 回答“已验证为何种主体”，carrier 回答“以何种精度标识”。`DidCoreId` 的 principal/service/Station/hardware-module 形态分别为 `<role>_principal_id` / `<role>_service_id` / `<role>_station_id` / `<role>_hardware_module_id`；`AccountId` 与 `ActorId` 是仅有的两个 closed compound carrier，其 carrier-explicit 字段形态分别为 `account_id` / `<role>_account_id` 与 `actor_id` / `<role>_actor_id`。已有完整 identity role（例如 `member_id`、`issuer_id`、`actor_ids`）可保留通用 `_id` / `_ids`，但 schema terminal 必须机器可判定为单一 scalar/array identifier carrier；同名字段在不同上下文使用多个 carrier 时，必须登记精确 carrier 集合及每种 carrier 的语义。W3C DID、generic URI identity/reference、HTTP(S)/WS(S) network locator 与 key selector 分别使用 `<role>_did`、`<role>_uri`、`<role>_url`、`<role>_kid`。carrier 与可验证主体类别共同决定后缀，与对象内是否并列其它形态无关；字段名不得替代 schema/registry/admission evidence 来推断类别。`holder` / `controller` 不适用通用 `_id` 规则，必须使用与合同一致的显式形态，裸 identity 字段在 Arkret-owned v1 中无条件禁用。多主体类别必须使用 discriminator 驱动、branch-specific 字段互斥的 closed union。

唯一的词类级裸名规则是已登记的 provenance/byline 角色：`<past-participle>_by` 整体是完整角色词，而不是“角色 + 被遗漏的 identifier 后缀”。`created_by`、`updated_by`、`executed_by`、`generated_by` 等登记字段永远保持裸名，MUST NOT 改成 `*_by_id`、`*_by_did` 或 `*_by_verification_method`；其值仍须按该字段的真实职责精确登记为 `ActorId`、W3C `did`、DID URL，或其它词法互斥的闭合 identifier union。字段名绝不为了保留裸 byline 而降级为 `string`，类型也绝不为了统一而强制成裸 `did_core_id`。该规则不构成任意裸角色白名单：只有 `tools/identifier-role-suffix-registry.json#registered_provenance_byline_fields` 中登记的精确字段名可使用此形态；新增词必须证明它表达 durable provenance/byline、声明 terminal profile，并通过 mutation gate。查询或索引函数中的 `get_by_id` / `*_by_id` 局部变量不属于 wire 字段命名合同。

URI/URL 与上述 identifier profile **正交**。可通过 HTTP(S) 解引用或通过 WS(S) 连接的网络 locator 使用 `_url`；通用 URI identity/reference、`geo:` / `mimi:` 等非网络 scheme、以及 OAuth/OIDC 等外部标准拥有的精确 URI 词法使用 `_uri`。Web Origin 是完整协议角色，使用裸 `origin`。当前闭合网络 locator 集合为 `arkret_base_url`、`base_url`、`connect_url`、`resolution_url`、`endpoint_url`、`gate_account_base_url`、`inclusion_proof_url`、`openid_configuration_url`、`public_base_url`、`push_gateway_url`、`retrieval_url`、`source_url`、`webhook_url`，以及 `BlobPresignOutcome.url`；当前 URI identity/reference 集合为 `acct_uri`、`gate_audience_uri`、`geo_uri`、`issuer_uri`、`mimi_room_uri`、`mimi_uri`、`provider_uri`、`redirect_uri` 和完整 generic `uri`。DID 专名 `did_url` / `verification_method` 不进入此集合。rate-limit policy 的 `endpoint` 是闭合 selector（absolute service path 或 absolute HTTP(S) URL），不是纯 locator 字段，保持裸名。所有 `_url` schema terminal MUST 明确收紧到登记的 HTTP(S)/WS(S) scheme；`format: uri` 本身既不能证明它是网络 URL，也不能决定字段后缀。

Web Origin 的完整角色名不等于宽松字符串：所有真实 Web Origin occurrence MUST 解析到 `common-ids.schema.json#/$defs/web_origin`。其 wire canonical 形态只允许 lowercase HTTP(S) scheme、host 与可选有效非默认 port；userinfo、任何 path（包括尾 `/`）、query、fragment、显式默认端口和越界端口都 MUST fail closed。`agent-sidecar-exchange-projection.origin` 是 closed provenance enum，不属于此 profile。

`service_id` / `service_ids` 仅在 `service` 本身就是完整语义角色时使用；`allowed_service_ids` 是对这一完整角色的许可集合。`media_service_id` 的 `media_service` 是已登记的复合协议角色，也继续保留。相同正交规则适用于分类后缀：泛化 service 自身使用 `service_kind` / `service_kinds`，已登记复合角色可使用 `media_service_kind`；其它角色必须写作 `<role>_kind(s)`，不得写作 `<role>_service_kind(s)`。除此以外，Arkret-owned 字段 MUST NOT 写成 `<role>_service_id(s)` 或 `<role>_service_kind(s)`。若同一对象同时需要两个责任主体，必须给它们真实且不重叠的角色（例如 claim 的 `issuer_id` 与独立背书方 `vouching_id`），或设计闭合 polymorphic union；不得靠 entity-class 限定词掩盖角色冲突。

外部标准拥有的 literal object 只在登记的精确 owner path 保留原字段名；例外不传播到 Arkret wrapper、projection、registry 或 canonical preimage。artifact lint 必须展开本地与跨文件 `$ref` 到 terminal constraint，并在诊断中同时报告 lexical owner、role stem、terminal category、required subject class、expected suffix 与 exception reason。

Arkret 自有 W3C DID 字段 MUST 使用对象中角色唯一且显然的 `did`，或使用 `<role>_did` / `<role>_dids`。Organization registration / principal-control accepted-evidence 对象同时携带稳定 `organization_id` 与 exact Organization DID 时，二者是同一语义角色的两种表示，MUST 使用逐字配对的 `organization_id` + `organization_did`，不得用裸 `did` 依赖容器类型隐式补全角色。稳定主体引用仍使用 `actor_id`、`principal_id`、`subject_id`、`recipient_principal_id`、`agent_id`、`audit_actor_id` 等已闭合字段。角色本身已是 canonical subject class 的既有名字可保留；`holder` / `controller` 必须显式携带 `principal` / `service` / `station` / `hardware_module` / `account` / `actor` 中由机器合同证明的一项。`sender_account_id`、`recipient_principal_id`、`target_principal_id`、`source_peer_principal_id` 等显式形态不取决于同一对象是否并列其它分支。`did` 与 `_did` 明确表示 W3C DID，绝不表示 `did_core_id`。

公共类型与 schema 定义固定为 `Did` / `did`；不得另定义裸 DID alias。`station_id` 中的 `station` 是已登记协议角色，不是 entity-class 限定词，且是该角色的唯一字段名。

`did` 的存在性由对象职责决定：普通 canonical identity object、Event、membership、grant、profile 与普通主体/service 引用禁止携带 DID；registration / genesis accepted evidence、Identity/Service Resolution Record 与 DID method evidence/control proof 必须把 DID 声明为 required。不得使用通用 optional `did` 充当缓存；缺失、不可见、停用、过期或 stale 必须由对象存在性、closed discriminator/state 与 freshness evidence 表达。

每个 `did_core_id` 的创建路径 MUST 证明它由已登记 adapter 对有效 DID 唯一投影而来；从未具有 DID 的 identity 必须使用其它已登记 ID 类型。可路由 service 必须有有效 resolution record，但普通 service 引用不得内联 DID。

`verification_method` 保留 W3C DID 规范字段名，承载 DID URL，不改名为 `_id` 或 `_did`。

#### 2.1.4 对象集合与分页结构

<!-- rule_id: NC-COLLECTION-001 --> **上下文内最短明确集合名（normative）**：Arkret-owned 对象集合 MUST 使用其 lexical context 内最短且无歧义的复数语义角色；被引用的 item `$ref` 类型名不得机械决定 property 名。`Entry`、`Row`、`View`、`Preview`、`Projection`、`Descriptor` 都是普通语义词，不是类似 `_id` / `_uri` 的 representation suffix：只有元素在协议语义上确实是条目、行、视图、预览、投影或描述符，并且省略该词会造成真实歧义时，字段才使用 `entries`、`rows`、`views`、`previews`、`projections`、`descriptors`；否则使用领域复数，例如 `actors`、`contacts`、`signers`。

非复数 collective / mass noun（例如 `evidence`、`cursor_presence`）、不规则复数和数组型 grammar operator 必须按精确 schema path 登记在 `tools/collection-naming-registry.json`，且登记必须说明该名称为何比普通复数更准确。不得通过复制 item 类型名来替代这项语义审查。

集合与 `limited`、`next_cursor`、`has_more` 等分页 companion 的关联 SHOULD 优先通过有名的嵌套分页对象表达，并在该 owner 内使用最短明确名称；`account-subscribe-frame` 的 `member_roster: { entries, limited, next_cursor }` 是该形态的规范实例。无法嵌套时，MUST 由 `tools/collection-naming-registry.json` 的精确 owner row 明确关联 `collection_field` 与 `companion_fields`；不得依赖或强制 companion 字符串复制完整 collection property 前缀。

## 3. Common Object Fields

所有 durable canonical object SHOULD 使用以下公共字段，除非对象类型另有说明。公共字段的 canonical 排列顺序以 §3.2 为单一真源（content → lifecycle → audit）：即 `state`、`state_changed_at`、`stage`、`stage_changed_at` 等 lifecycle 簇 MUST 排在 `created_by`、`created_at`、`updated_by`、`updated_at` 等 audit 簇之前（与全部已实现 schema 一致）。对象专属字段 MAY 插入在 scope / lifecycle / body 分组中，但同名公共字段的相对顺序 MUST 与 §3.2 和 `tools/field-order-rules.json` 保持一致。本节字段表（§3.1）仅为概念性字段清单，不作为顺序真源。

| 字段 | 必填 | 类型 | 约束 | 说明 |
| --- | --- | --- | --- | --- |
| `id` | yes | `id:*` | typed ID 前缀决定对象种类（`ak:strand:` 即 strand 对象，依此类推）。 | 对象稳定 ID；前缀就是 type，不再单独写 `type` 字段。 |
| `schema` | yes | `string` | SHOULD 是 `ak.schema.*.vN` 或反向域名 schema id。 | 验证 schema id。 |
| `realm_id` | conditional | `id:realm` | Realm 外对象可省略。 | 所属 Realm。 |
| `created_by` | conditional | `ActorId` | 系统派生对象可由 `derived_from` 替代。 | 创建主体（创建该对象的 Event 的完整 `actor_id`）。 |
| `created_at` | yes | `timestamp` | 不能作为因果真相。 | 创建时间。 |
| `updated_by` | no | `ActorId` | 更新时 SHOULD 设置。 | 最近更新主体。 |
| `updated_at` | no | `timestamp` | MUST be no earlier than `created_at`。 | 最近更新时间。 |
| `state_changed_at` | R when state≠active | `timestamp` | **Reducer-derived,actor 不可信:** 所有具有 `state` 字段的对象（Circle / Space / Strand / Message / Morph / Relation / View）当 `state != active` 时 MUST 写入（逐对象必填性矩阵见 §3.1，统一标记 `R when state≠active`）;reducer **MUST** 忽略任何 wire payload 中 actor-supplied 的 `state_changed_at` 值。权威值为 `max(Event.created_at, accepting_committed_at)`，其中 `accepting_committed_at` 来自直接接受该 Event 的确切 RealmCommit；所有 shared durable Event 都有该值。MUST be no earlier than `created_at`,MUST ≤ `updated_at`(当后者存在时)。 | 最近一次 state 转换时间。 |
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
| `created_by` | Authorship | Y | Y | Y | Y | Y (reducer-derived from Event `actor_id`) | Y | Y | Y | Y | Y | — (see `issuer_id`) | — (see `inviter`) | — (see `actor_id`) | — (see `actor_id`) | — (see `principal_id`) | — (see `controller_account_id`，见附注) |
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
- Capability Grant / Invite / Read Cursor / Notification / Actor Profile 用领域特有的 authorship 字段（`issuer_id` / `inviter` / `actor_id` / `principal_id`），各对象 schema 内部独立约束；本表对应格写"—"是因为它们不使用通用 `created_by`，并不表示没有创建主体记录。
- Read Cursor / Notification 是 actor-private 状态：`realm_id` 在 Read Cursor 上必填（`read-cursor.schema.json` 列入 `required[]`），在 Notification 上可选（允许 actor-scoped 视图省略）；`updated_by` 均不适用——这些对象由系统派生或 actor 本人推进。
- **`state_changed_at` reducer-derived 总括 MUST（单一真源）**：任何承载物理 lifecycle `state` 轴的对象（Circle / Space / Strand / Message / Morph / Relation / View）在 `state != active` 时 MUST 写入 `state_changed_at`；该字段一律 **reducer-derived，actor MUST NOT 携带**。安全转换使用 §3 定义的 `max(Event.created_at, accepting RealmCommit.committed_at)`，普通转换只使用 `Event.created_at`；actor wire 值 MUST 被忽略（详见 §5.1）。各对象专属文件的 `state_changed_at` 行不必重复声明该 reducer-derived 约束，以本条为权威。本条不适用于 Notification / Invite 的 `state` 轴——它们由 Arkret 推进但不属于 §5.1 通用 lifecycle 状态机（见下条）。
- **`state` 必填性差异（Circle=Y vs Space/Strand/Morph=O）**：Circle 的 `state` 为必填（`circle.schema.json` 列入 `required[]`），而 Space / Strand / Morph 为可选（缺省语义 `active`）。理由：Circle 是独立的 scoped event boundary，其 lifecycle（`active` / `archived` / `tombstoned`）直接决定该 scope 内对象能否继续写入与投递裁剪（见 [`circle.md` §9.2](./circle.md)），故 reducer / projection 必须能从 Circle 对象直接读出确定 state，不容许 "缺省即 active" 的隐式解释带来 scope 可写性歧义；Space / Strand / Morph 的缺省 `active` 不影响其它对象的 scope 边界，省略时按 `active` 解释是安全且省 wire 的取舍。两类对象的 `state` 转换真源仍统一为 §5.1 的 reducer-input lifecycle event，必填性差异只影响 wire 上是否允许省略该字段。
- Notification 的 `state` 是 schema required 字段（enum `unread / read / dismissed / archived`）：它承载 actor-private 的通知处理轴；按 §5 的所有权判据这是 `state` 的正确用法（轴由 Arkret 推进），**不是命名例外**，但它不落入 §5.1 的通用 lifecycle 状态机，且 Notification 无 `state_changed_at`。Invite 的 `state` 同为 schema required，承载邀请流程状态轴（见 [`governance-objects.md` §5](./governance-objects.md)），同理不落入 §5.1 状态机。
- `stage_changed_at` 仅 Strand / Morph 适用，且仅当 `stage` 存在并真正发生 stage 变更时写入；同值 self-transition reducer MUST NOT 更新（详见 §3 与 §5.3）。
- `labels` 仅适用于 Space。Realm / Circle / Strand / Message / Morph / Relation / View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification / Actor Profile 的标签语义由各自的 schema-specific 字段（如 `tags`、`reason`、`category`）或扩展容器承担，避免与 Space labels 投影冲突。
- `fields` 是协作对象的扩展容器；Strand / Message 的用户可读扩展放入 `metadata.fields` 或 `encrypted_metadata`，不得作为顶层 `fields`；View / Policy / Blob meta / Capability Grant / Invite / Read Cursor / Notification 不暴露开放扩展容器。
- **View 终态复用 update**：共享 View 通过 `ak.view.update` patch `state="tombstoned"` 进入 durable terminal state；不另注册平行的 `ak.view.tombstone` event kind。Reducer 派生 `state_changed_at`，终态后的 update / reconcile 用 `view_already_terminal` 拒绝；见 [`views.md` §3.1](./views.md)。
- **Realm 无 materialized `state` 字段**：Realm 的 `archived` / `frozen` / `tombstoned` / `destroyed` 由各自的领域 Event 与 current result 表达，`realm.schema.json` 拒绝 `state` / `state_changed_at`。读取面 MAY 把 `ak.realm.tombstone` 与 `ak.realm.destroy` 均显示为 `realm_terminal_state`，并用 `terminal_kind=tombstone|destroy` 区分 successor 迁移与永久关闭；不得把该显示状态写回 Realm 对象。
- **Agent Sidecar（`ak:sidecar:`）authorship 与 state 特例**：Sidecar 不使用通用 `created_by` / `updated_by`；其 authorship 是 exact controller account（`controller_account_id`，create-locked、必为父 Realm active member），create / update 主体由 reducer 从 controller account / Realm membership / lifecycle checkpoint 派生（`agent-sidecar.schema.json` 无 `created_by` / `updated_by`）。本表对应格写"—"与 Capability Grant / Invite 同理——不表示没有创建主体记录。Sidecar 的 `state`（`active` / `suspended` / `tombstoned`）是**reducer-derived 特例生命周期轴**：`suspended` 不属于 §5 通用物理 lifecycle 枚举（见 §5 附注），无 actor-authored `ak.sidecar.update/archive/restore`；`state_changed_at` 取触发派生转换的已接受 Event timestamp。合法 / 非法迁移封闭表见 [`sidecar.md` §7](./sidecar.md)。Sidecar 无 `labels` / `stage` / `stage_changed_at` / 顶层 `fields` 扩展容器。

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

> 说明：§3.2 排序硬规则已由 `tools/artifact_lint` 的 `check_field_order` 自动校验——递归全部 `artifacts/schemas/*.schema.json` 的每个 `properties` 对象，强制 `created_by < created_at < updated_at`、`updated_by < updated_at`，以及 `state_changed_at` / `stage_changed_at` 紧邻 `state` / `stage`。规则按字段存在性条件触发，故 Read Cursor（无 `created_at`）、Capability Grant（用 `issued_at`）等有意例外天然不触发，无需白名单。

### 3.3 公共元数据的来源与维护闭包（normative）

物化对象的每个成员都 MUST 有一个已登记来源，且该对象 family 的**每一条**已登记写入都 MUST 对该成员给出明确维护方式。
仅在 schema 里声明一个字段不证明它会被维护：一个从 create 复制进来、此后任何更新都不再触碰的 `updated_by`
既通过 schema 校验，也通过任何只检查"写下的派生名是否登记"的门禁，却在每次更新后指向一个并未作者本次值的 Actor。

来源词表是封闭的，且 MUST NOT 全部压进 reducer 派生白名单：

| 来源 | 含义 | 机器表达 |
| --- | --- | --- |
| 作者输入 | 成员取自签名 Event 的闭合作者载荷 | `apply_patch` 的 `allowed_paths[]`，或 whole-value 投影所读的闭合作者载荷区域的声明属性 |
| reducer 派生 | 成员由本次已接受 Event / RealmCommit 按固定规则算出 | `result_writes[].derived_members[]`，`derivation` 取自封闭派生名集合 |
| 前态保留 | 成员逐字保留冻结前态的值，本次写入不改变它 | `result_writes[].retained_members[]` |
| create-locked | 成员由 create 写入一次性确定，此后只能以前态保留出现 | registry 的 `create_locked[]`：仅 `producer_kinds` 命名的写入以 `derived_members[]` 产出，family 的其它每一条写入都 MUST 在 `retained_members[]` 里列出它 |
| 专属事件维护 | 成员只由某个专属 event kind 写 | 该 kind 的已登记写入；其它写入 MUST NOT 产出它 |

三种角色 MUST 互斥：同一成员在同一条写入上不能既是作者输入又是派生，也不能既是派生又是前态保留。
每条写入声明的名字 MUST 是该 value schema 已声明的成员；value schema 的每个必填成员 MUST 被三者之一恰好覆盖一次。
可选成员 MAY 按合同缺席，但**规范要求出现或要求随写入变化的成员若没有生产／维护规则，门禁 MUST 转红**。

公共元数据的派生规则本身是可复用的，不是某个对象的专用字符串。v1 登记九个公共派生名。

**更新元数据（三个）：**

- `object_update_actor`：`updated_by` = 本次已接受 Event 的 `actor_id`（§3 表）。对象 family 的每一条已登记写入都 MUST 产出它。
- `object_update_time`：`updated_at` = 本次已接受 Event 的 canonical lifecycle timestamp，即 §3 为 `state_changed_at`
  定义的同一公式 `max(Event.created_at, accepting_committed_at)`；shared durable Event 缺 accepting RealmCommit 时不得物化对象状态。
  MUST NOT 使用本地接收时间、任意客户端值或独立墙钟。结果 MUST 满足 §3 的 `created_at` ≤ `updated_at`。对象 family 的每一条已登记写入都 MUST 产出它。
- `object_state_transition_time`：`state_changed_at`，条件性产出——仅当本次写入被接受为一次真实 state 转换时产出，
  公式同上，并 MUST 满足 `state_changed_at` ≤ `updated_at`。只有已登记为该转换承载者的 event kind 可以产出它。

**create-locked 身份与创建元数据（五个）**：这五个成员 MUST NOT 出现在任何写入的作者输入区域里——
包括 create 自己的。一个仍然声明它们的 create 作者载荷等于让签名 Event 自报创建者、自报所属 Realm、
自报初始 state，而后续写入逐字保留该值，伪造因此成为永久的 create-locked 真相；
`state` 之类成员在 `universal_forbidden_patch_paths` 里被 patch 面挡住，却从 create 的 whole-value 快照里整个漏进来，
正是"patch 不能碰的，快照不得伪造"这一条在 v1 之前无人强制的结果。

- `object_schema_identifier`：`schema` = 该对象 kind 在 [`schema-registry.json`](../../artifacts/registry/schema-registry.json)
  中登记的 schema 标识常量，由 event kind 到对象 kind 的登记关系确定，与载荷内容无关。
- `object_realm_binding`：`realm_id` = 接纳本次 Event 的 stream 所属 Realm，取自已验证 Event envelope，
  MUST NOT 取自载荷；跨 Realm 的自报值 MUST 被拒绝。
- `object_create_actor`：`created_by` = 本次已接受 create Event 的 `actor_id`，与 `object_update_actor` 同源，
  差别只在它此后不再改变。
- `object_create_time`：`created_at` = create Event 的 canonical lifecycle timestamp，公式同 `object_update_time`。
  同一条 create 写入产出的 `created_at` 与 `updated_at` MUST 相等。
- `object_initial_state`：`state` = 该对象 kind 登记的初始生命周期状态。create MUST NOT 创建出非初始状态的对象，
  因此也 MUST NOT 产出 `state_changed_at`；离开初始状态只能由已登记的转换承载写入完成。

**生命周期终态（一个）**：

- `object_lifecycle_state`：`state` = §5.2 为本次已接受的专用 lifecycle event kind 登记的目标状态
  （`ak.<kind>.archive` → `archived`，`ak.<kind>.restore` → `active`，`ak.<kind>.tombstone` → `tombstoned`）。
  它只能由该 family 已登记为转换承载者的 lifecycle kind 产出，且只作用于本 Event 指名的那一个目标对象；
  它**不是**作者 patch 权限——`state` 仍在 `universal_forbidden_patch_paths` 里，本派生不改变 patch 面。
  产出它的同一次写入 MUST 同时产出 `object_state_transition_time`。前态 guard 按 §5.2 与各对象正文执行：
  same-state 转换、对已终态对象的任何 lifecycle 写入、以及 `restore` 试图复活 `tombstoned` 对象，
  MUST 以 `failed_precondition` 拒绝，不得静默 no-op。

九个名字与 [`../authz/capabilities.md` §10](../authz/capabilities.md) 登记的 capability / consent / authority-root 派生名同属**一个**封闭集合；
新增任何一个等同新增 normative reducer 规则，MUST 先在正文定义其规范输入、适用写入、条件与确定性输出，再登记到写入行。

以上双向闭包由 [`registry/reducer-managed-path-registry.json`](../../artifacts/registry/reducer-managed-path-registry.json)
的 `value_member_maintenance` 逐 family 表达（`always_maintained` / `conditional_producers` / `create_locked` 三类规则），
并由 `check_result_write_contracts` 与 `check_result_value_member_closure` 强制。
该 registry 同时是"哪些 patch 路径归 reducer 所有"的唯一真源：其有效禁集**逐对象**求解，
`universal_exemptions` 参与相减而不是被当作禁令，某个对象的专属禁令 MUST NOT 污染另一个恰好同名的 family。
未声明 `value_member_maintenance` 的 family 属于已声明的覆盖边界，registry 行内 MUST 指出关闭它的 owner；
这是覆盖边界，不是豁免，不得用来为一条虚假断言背书。

## 4. 主体引用字段交叉对照

### 4.1 DID 适用边界

主体标识分为两种强类型：

| 类型 | wire 形态 | 用途 |
| --- | --- | --- |
| `did_core_id` | `ak:did_core:<method>:<core>` | 密码学 principal / service reference 与 DID-core 相等判断；Event actor、membership、Relation Actor endpoint 与账号级 capability 使用完整 ActorId / AccountId，不得据此丢弃 Station。 |
| `did` | 标准 bare DID，例如 `did:webvh:<scid>:<host>` | 注册、DID resolution、method-native operation、DID Document / history 验证。 |

`did ≅ did_core_id + method-specific resolution` 只是 adapter 语义，不是字符串拼接格式。只有已登记 DID method adapter 可以从 `did` 投影 `did_core_id`；普通业务代码 MUST NOT 自行拆解或反向构造。一个 `did` 投影到的 `did_core_id` 必须唯一。DID URL 不属于 `did`：`verification_method` 等 DID URL 必须在验证 `did` 后由相同 adapter 处理，禁止把 fragment 直接拼到 `did_core_id`。实现 MUST NOT 以字符串前缀判断 DID URL controller；比较前必须由 adapter 解析 DID URL，并验证其 base `did` 到目标 `did_core_id` 的唯一投影关系。

`did_core_id` 是 Arkret 的稳定主体标识，`did` 是其当前 DID resolution material；二者都不是普通协作对象 ID。标准协作对象（Realm / Circle / Space /
Strand / Message / Morph / Relation / View / Policy / Grant / Invite / Blob 等）MUST 使用
`ak:<kind>:` typed ID 作为对象 ID；设备也不是 actor 主体，其标识是
`device_id`（`ak:device:<uuidv7>`），没有设备 DID。

DID / DID URL 字段总表、条件性 polymorphic ref、明确不是 DID 的 `*_id`，以及“普通业务只把
DID 当作身份锚点、仅在封闭触发条件下验证 DID 控制权”的规则，统一见
[`../identity/did-usage-and-verification.md`](../identity/did-usage-and-verification.md)。
本节不复制总表，避免字段新增后出现两份不一致清单。

仅作为内容、容器、投影或关系事实存在的对象，不需要也不得发明独立 DID；它们通过 typed ID
被引用，通过 `created_by` / `updated_by` 等字段关联到完整 ActorId。字段里出现 DID 只声明
value category，不会自动触发 DID Document 解析或在线验证。

### 4.2 主体引用字段

**Account 身份与权限隔离铁律（normative）**：`AccountId={principal_id,station_id}` 是不可拆分的账号身份。
对 `A={principal_id:P,station_id:S1}` 与 `B={principal_id:P,station_id:S2}`，只要 `S1 != S2`，
`A` 与 `B` 就永远是两个独立 Account，account 分支的 ActorId 也永不相等。相同 principal、DID
控制者、公钥、登录用户或组织归属 MUST NOT 建立账号等价、权限关联、继承、合并、代理或恢复关系。
该规则不因任一 Station 离线、永久停止服务、账号恢复、Realm 接管、RealmCommit 冲突或灾难恢复而改变。

账号级 membership、capability、owner/admin/RealmCommit-signing/recovery authority、设备授权、PCR、session 与 MLS
授权 MUST 绑定并验证完整 AccountId；MUST NOT 通过只比较 `principal_id`、替换 `station_id` 或查询
同 principal 的另一账号来补足授权。另一账号如需参与同一 Realm，MUST 以其自身完整 ActorId 独立
满足该操作的授权规则；同 principal 这一事实没有任何授权效力。独立、显式授权不构成账号等价，
也不转移原账号的身份、PCR 或未被该授权授予的权限。

Station 永久停止服务时，其 Account 与 PCR 不提供跨 Station 延续、迁移或复活路径；在另一 Station
注册同 principal 只会建立独立 Account。历史 Event / RealmCommit 的验证与保留不恢复死亡账号的当前行动权。
同一 Station service DID core 的 endpoint 更新不改变 AccountId，不属于跨 Station 账号替换。
生命周期边界见 [`../identity/account-lifecycle.md` §2](../identity/account-lifecycle.md#2-分层)。

| 字段 | 出现对象 | 含义 |
| --- | --- | --- |
| `actor_id` | Event Envelope、membership 与通用 actor-scoped 状态 | 完整 ActorId closed union；account 分支携带 exact AccountId（包括人类、Agent、Ghost 与 integration），service 分支携带 `service_id`。不得用并列 `actor_kind` 或裸 DID 补足语义。 |
| `watcher_actor_id` / `target_actor_id` / `writer_actor_id` | Event payload、Audit payload | 带角色限定的 ActorId；字段名说明角色，值形态仍使用同一个 closed union。若专属 schema 明确只允许某一 DID-core 角色，必须使用该专属角色名而不是泛化 `actor_id`。 |
| `principal_id` | Actor Profile | Profile 对应的密码学 principal `did_core_id`；不是完整账号身份，不产生跨 Station 权限关系。账号授权使用完整 AccountId / ActorId。 |
| `created_by` / `updated_by` | 所有 Materialized Object | 创建 / 最近更新该对象的完整 ActorId，由 reducer 从 Event `actor_id` 原样派生；不得只保存其中的 principal DID。Realm 的 `created_by` 还承担 genesis member bootstrap 的 authorizing actor 语义。 |
| `issuer_id` | Capability Grant、Identity Receipt、Handle Claim、Agent Selector Claim、SessionGrant | 签发授权、receipt、claim 或 credential 的主体 `did_core_id`；必须持有签发权限。 |
| `subject` | Capability Grant | 唯一登记的 closed polymorphic subject：principal `did_core_id` 或带 discriminator 的 condition selector。裸名表示整个闭合 union，不是稳定 ID 的别名。 |
| `subject_account_id` | Handle claim、账号寻址与 mention target | 必须是 exact AccountId；不得降级为裸 principal DID。mention 节点的权威 target 就是本字段（[`../identity/identity-handles.md` §3.8](../identity/identity-handles.md)）。Agent Selector Claim 的 selector **namespace** 是 principal 级的，使用它自己登记的 `controller_subject_id`；但它选中的**目标**是账号级的，就是本字段 `subject_account_id`（[`2026-09-05-1310` 裁决](../identity/identity-handles.md)）。namespace 与目标是两个职责，谁也不从对方派生。 |
| `controller_subject_id` | Agent Selector Claim | 拥有 controller-scoped agent selector namespace 的 controller principal `did_core_id`；它只定 namespace，不定被选中的账号。事件 mention 的 controller audit metadata 另用账号级 `controller_subject_account_id`，两者不可互换。 |
| `inviter_account_id` / `invitee_account_id` | Account-addressed Invite | 邀请方 / 被邀请方 exact AccountId；通用 membership target 使用 ActorId。 |
| `accountable_principal_ids` | Actor Profile | 该 Actor Profile 声明可问责到的一组 principal `did_core_id`（每个条目须有对应 active `ak.identity.accountability_grant` 背书）。array 形态使用 `_ids` 复数，与 agent key payload 的 scalar `accountable_principal_id` 共用同一 accountability 主体词汇；责任主体一律走 `_id` / `_ids`，不使用 `_to` 介词后缀或裸关系短语。 |
| `agent_id` / `audit_actor_id` | Agent key payload、Audit release evidence | agent / audit release service 作为协议责任主体时使用 `did_core_id`；承载运行或托管服务身份时另用 `service_id`。 |

这些不是同一字段的别名，每条都有独立语义角色；该表用于读 spec 时快速建立对应关系。

ActorId 的服务路由投影是封闭且无状态的：account 分支取
`account_id.station_id`，service 分支取
`service_id`。任何需要按托管服务分桶、去重或解析 endpoint 的协议都 MUST 使用这个投影；不得再保存
member-specific route object、route source、fallback 或 rebind 状态。路由刷新只更新对应 service
DID core 的 `AuthenticatedServiceResolution`，不改变 ActorId；service DID core 变化会形成不同 ActorId，必须通过
正常 membership / invitation transition 处理。

主体字段新增策略：

- 既定 crypto / governance 角色名词（如 `issuer`、`inviter`、`holder`、`controller`）登记的是语义 stem，不豁免 §2.1.3 的主体类别与 carrier 后缀；其 identifier 字段按合同使用 `issuer_id`、`inviter_account_id`、`holder_service_id` / `holder_account_id`、`controller_id` 等形态。durable provenance/byline 只有在 registry 精确登记为完整 `<past-participle>_by` 角色后才能使用裸名（例如 `approved_by`、`revoked_by`），并按职责强类型为 `DidCoreId`、`Did`、DID URL 或闭合 union；不得追加 identifier 后缀。时间点独立使用 `<verb>_at`。
- 过程结果词汇按对象族固定（**封闭四词**，normative）：

  | 词 | 语义 | 典型载体 |
  | --- | --- | --- |
  | `outcome` | 请求 / 提交 / receipt 的完成结果，配 `outcome_reason_code` | 全部 `*_outcome` DTO、receipt 的结果字段 |
  | `result` | 执行体或 session 自身算出的运行结果 | call recording / transcript 的 `result`、SDK conformance claim |
  | `decision` | 人为或治理裁决 | moderation、join review、consent |
  | `resolution` | 名称 / 选择器 / 冲突的**解析**结果，不是过程结局 | `service_resolution`、agent selector、applet namespace conflict |

  新增相邻对象 MUST 从上表取词，不得随机换用近义词。receipt 使用 `outcome`，moderation 使用
  `decision`，后者与 `ak.moderation.decision` 及 `moderation_decision_payload` 两层一致。
  `response` / `ack` 不是独立结果词：HTTP 响应体统一走 `*_outcome`，确认类载荷按其真实语义归入上表。

### 4.3 角色名词登记索引

下表收敛 v1 已确立的 crypto / governance 角色名词，供读 spec / 评审命名时一次定位。本表是 **informative 索引**：每个角色的字段形态、约束与 normative 语义以「权威定义」列指向的 schema / glossary / 专属章节为单一真相源，本表不重复承载约束，也不得与权威定义冲突。新增 normative 文本引入主体 / 操作者归属字段时，先查本表确认是否已有既定角色名词，再按上文「主体字段新增策略」决定复用或使用 `<verb>_by`。

| 角色名词 | 类别 | 权威定义 | 角色语义 |
| --- | --- | --- | --- |
| `issuer` → `issuer_id` | role stem / id 字段（§4.2） | §4.1 / §4.2；[glossary `Capability Grant` / `state-changing Event`](../overview/glossary.md) | 签发 Capability Grant / Identity Receipt 或签署 Event / state-changing Event 的主体 DID；wire identifier 必须使用 `issuer_id`。 |
| `subject` → `subject_id` | role stem / id 字段（§4.2） | §4.1 / §4.2；[glossary `Subject`](../overview/glossary.md) | 具体责任主体使用 `subject_id`；只有 CapabilityGrant 的 closed `did_core_id | condition selector` union 使用裸 `subject`。 |
| `inviter` / `invitee` → `inviter_account_id` / `invitee_account_id` | role stem / AccountId 字段（§4.2） | §4.1 / §4.2；[`governance-objects.md` §5 Invite](./governance-objects.md)；[`invite.schema.json`](../../artifacts/schemas/invite.schema.json) | 邀请方 / 被邀请方 exact AccountId；3PID 邀请可暂无 `invitee_account_id`，认领后必须绑定可验证主体。member 引用形态另用 `inviter_member_ref` / `invitee_member_ref`（见 [`invite-delivery-request.schema.json`](../../artifacts/schemas/invite-delivery-request.schema.json)）。 |
| `holder` → `holder_service_id` / `holder_station_id` / `holder_hardware_module_id` / `holder_account_id` | 责任角色 + subject/carrier 字段 | [`consent-model.md` §2](../identity/consent-model.md)；[`client-preferences.md`](../discovery/client-preferences.md)；[glossary `Consent`](../overview/glossary.md) | consent / blocklist / pairwise 假名等 holder-private 状态的归属主体。exact account 使用 `holder_account_id`；archive/availability service 使用 `holder_service_id`；只有机器证明为 Station 或 hardware-backed module 时才允许对应专名。payload 可从 Event actor 派生时不得复制 holder 坐标。 |
| `witness` | 叙述性角色名词 | [glossary `Witness`](../overview/glossary.md)；[`federation.md`](../sync/federation.md)；[`operations-sync.md`](../sync/operations-sync.md)；[`identity-did.md`](../identity/identity-did.md) | 对 checkpoint、DID key-log 头部、handover checkpoint 或已登记对象签发 attestation / receipt 的受信背书主体；不替代 Event 自身签名、RealmCommit finality 或 reducer 验证。 |
| `controller` → `controller_principal_id` / `controller_account_id` / `controller_actor_id` / `method_controller_principal_id` | 责任角色 + subject/carrier 字段 | [`identity-did.md`](../identity/identity-did.md)（DID controller proof）；[`actor.md` §3.3](./actor.md)（Agent controller） | DID method controller principal 使用 `method_controller_principal_id`；稳定 controller principal 使用 `controller_principal_id`；exact account controller 使用 `controller_account_id`；account-or-service authority root 使用 `controller_actor_id`。裸 controller identity 字段禁用。 |
| `owner_id` | id 字段（§4.2） | [`realm-read-operations.schema.json`](../../artifacts/schemas/realm-read-operations.schema.json)（`realm_lifecycle_view`）；[`realm-and-space.md`](./realm-and-space.md)（organization `relationship="owner"`） | Realm lifecycle projection 中该 Realm 归属主体的 `did_core_id`。与 organization statement 的 `relationship="owner"` 同一归属语义，但后者是关系枚举值而不是主体字段。**不得**用 `owner_id` 表达 holder-private 状态的归属主体——那一族使用 `holder`（见本表 `holder` 行）；也不得写成裸 `owner`。 |
| `publisher_id` | id 字段（§4.2） | [`extension-manifest.md`](../extensions/extension-manifest.md)；[`extension-manifest.schema.json`](../../artifacts/schemas/extension-manifest.schema.json) | 对 Extension Manifest 的 canonical digest 与完整声明负责并签发 publisher proof 的主体 DID；不得用裸 `publisher` 或 transport service identity 替代。 |

### 4.4 `agent_participation` wire 形态（normative）

Realm、Circle、Strand 的 `agent_participation` policy component 使用
`{agent:{reply_message,reaction_add,reaction_remove,accept_third_party_mention,act_on_behalf}}`；
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

### 4.5 Membership FSM（normative）

Realm 与 Circle 的 materialized membership 共用唯一状态集 `join / knock / leave / ban`，`initial_state=leave`；
不存在 `none` 或 `invite`。Invite 是独立 pending workflow，只有 exact target ActorId 的有效 acceptance 才把 membership
从 `leave` 推进到 `join`。same-state transition 一律非法；endpoint、transport 或 Station 变化不得伪装成
`join -> join`。

| from | to | wire event kind | guard / writer |
| --- | --- | --- | --- |
| `leave` | `knock` | scope membership state | target ActorId 自著，且 join rule 允许 |
| `leave` | `join` | `ak.member.state` 或 exact invite acceptance | target ActorId 自著 / bootstrap creator，或 exact target invite acceptance |
| `knock` | `join` | scope membership state | 已授权 reviewer/admin |
| `knock` | `leave` | scope membership state | target ActorId 或已授权 reviewer/admin |
| `join` | `leave` | scope membership state | target ActorId 或已授权管理员 |
| `leave` / `knock` / `join` | `ban` | scope membership state | 已授权管理员 |
| `ban` | `leave` | scope membership state | 已授权管理员；self-service fail closed |

任何未列边 MUST `failed_precondition`（`reason=invalid_membership_transition`）。Bare knock/invite 的本地计时器不产生
隐式边；过期清理必须由对应 workflow 或显式 membership Event 完成。账号分支的 target equality 使用完整 AccountId，
其它 Actor 分支使用完整 ActorId；不得回退到裸 DID。
## 5. 状态字段的命名边界

common 只定义 `state` 与 `stage` 两个共享概念。`state` 是所属对象/资源的当前状态，既可以是 FSM 值，也可以是多个已登记事实的确定性投影；同名不表示共享枚举、typed current result 或一个通用 FSM。`stage` 是 Strand/Morph 的业务进度，与 `state` 正交。

`status` 是领域局部字段；closed DTO 内无歧义时可使用，多个领域结果并列时使用 `account_status`、`delivery_status` 等明确名字。这里不按“谁拥有状态”给同名字段分配全局状态机。Agent selector 的绑定与撤销只由 [actor §3.2](./actor.md) 定义。

**whole-value state wrapper MUST NOT 携带 `state` / `reason`（normative）**：形如 `{<subject>?, value}` 的 state-setting payload——整份领域值位于 closed `value`、Event 本身只是把该值置为当前值的那一类——的 wire 形态 MUST 只有 subject 与 `value`；出现 wrapper 级 `state` 或 `reason` 的以 `schema_violation` 拒绝。理由是这两个名字在该形态下都没有真源：wrapper 级 `state` 与本节的对象状态轴不是同一个东西，它没有登记枚举，也没有任何 reducer 读它——这些 kind 的 registry projection 一律只取 `payload.value`，领域值自身的状态（若有）在 `value` 内部由该领域的 schema 定义；wrapper 级 `reason` 与 revoke / tombstone / redact 类 Event 上受 profile 约束的 audit `reason` 也不是同一个字段，它无长度约束、无 reason-code 词表，也不进入任何投影。[governance-objects.md §2.1 / §3.2 / §3.4](./governance-objects.md) 已分别对 `ak.schema.define`、`ak.policy.set`、`ak.policy.action` 写明这一点；本条是该 payload 形态的通则，`ak.realm.policy`、`ak.realm.join_rule`、`ak.realm.discovery`、`ak.realm.asset_privacy_policy`、`ak.realm.schema`、`ak.organization.discovery`、`ak.sovereign.did_policy` 同样适用。需要审计理由的领域用自己的 Event kind 与受约束的 `reason` 表达，不借 wrapper 顺带携带。

### 5.1 对象状态的权威入口

合法操作由对象自己的定义定位到 event-kind registry 的 effect、领域迁移校验与组合规则，不得根据字段名或 Event 拼写推断，也不得把业务状态机复制成 typed current result 状态模型或第二份可逆性标签。Realm 见 [realm-and-space §2.6](./realm-and-space.md)，Strand/Message 见 [strand-and-message](./strand-and-message.md)，其它对象分别见 [circle](./circle.md)、[morph](./morph.md)、[relation](./relation.md)、[views](./views.md)、[sidecar](./sidecar.md)。存在 `state` 不意味着支持 archive/restore。

`state_changed_at` 仍是 reducer-derived：安全转换取 `max(Event.created_at, accepting RealmCommit.committed_at)`，其中 accepting RealmCommit 是唯一确认序列里直接接受该命令的确切位置；普通转换只取 `created_at`。actor 不得通过 payload 改写它。对象缺失不表示 active；缺 create/依赖时按同步规则保留 pending_causal_apply/replay 并按目标建索引，不得成功丢弃操作。依赖、snapshot 或可验证 visibility 材料到达后重新执行同一校验；证明永久不可见时沿 dependency_missing / capability_denied / history_not_visible 报告，不得记为 applied。

### 5.2 操作与组合约束

可归档对象使用独立 archive/restore Event；terminal/redaction 不被 restore 清除。

**kind → 目标 state 映射（normative）**：这三类专用 lifecycle kind 是对象 `state` 轴在 create 之后的**唯一**
承载者，其目标值由 kind 本身确定，不由 payload 携带：

| event kind 形状 | 目标 `state` | 合法前态 | 终态? |
| --- | --- | --- | --- |
| `ak.<kind>.archive` | `archived` | `active` | 否 |
| `ak.<kind>.restore` | `active` | `archived` | 否 |
| `ak.<kind>.tombstone` | `tombstoned` | `active` 或 `archived` | **是** |

reducer 按 §3.3 的 `object_lifecycle_state` 产出该值，同时按 `object_state_transition_time` 产出
`state_changed_at`；两者 MUST 在同一次写入内一起产出。作者 MUST NOT 在 payload 里携带目标 state：
payload 只指名目标对象与可选理由。前态不符（same-state archive、restore 一个 `tombstoned` 对象、
对已 `tombstoned` 对象的任何 lifecycle 写入）MUST 以 `failed_precondition` 拒绝并零写入。
没有专用 lifecycle kind 的对象是例外而不是通则：v1 只有 View 一个，见
[`views.md` §3.1](./views.md) 与 `reducer-managed-path-registry.json` 唯一一条 `universal_exemptions`。
Realm 没有 materialized `state` 字段（§5.1 表末），因此 `ak.realm.archive` / `ak.realm.restore`
不产出本派生，它们按 [`realm-and-space.md` §2](./realm-and-space.md) 的既有合同写 per-Realm 的
`realm_archive` facet。Realm freeze/unfreeze 是独立写 gate，解冻不解除 archive、终止标记或权限限制。每个 effect/FSM 保留其现有 projection、冲突策略与 plane；对象定义负责组合这些事实，不建立通用对象总状态机。

生命周期 payload 不接受 `effective_at` 或 `freeze_expires_at`。状态按正式 state-changing Event/RealmCommit 接受规则推进，时钟自身不产生解冻或恢复 Event。产品调度在实际执行时走普通 author/sign/submit。claim expiry、retention 和既有 revocation fence 仍按各自合同执行。

### 5.3 Stage 轴（业务进度，与 state 正交）

`state` 表达所属对象的当前状态；`stage` 表达**业务进度**（一件事从想法走到完成的过程）。两个字段在不同 reducer 路径上独立维护，**MUST NOT 互相 implicate**：archive 不会把 `stage` 推到 cancelled，`stage=done` 不会自动 archive 对象。

#### 5.3.1 适用对象（v1）

| 对象 | 是否声明 `stage` | 必填语义 | 触发 event |
| --- | --- | --- | --- |
| `Strand` | yes | create payload MUST 省略；需要进度轴时由首条 `ak.strand.stage.set` 初始化。普通业务 Strand SHOULD 在创建后初始化，DM 主 Strand MAY 一直省略 | `ak.strand.stage.set` |
| `Morph` | yes | create payload MUST 省略；generic mirror/data Morph MAY 一直无进度轴。v1 没有任何 carrier 能要求 create payload 携带顶层 `stage`：Realm `morph_kind_profiles` 只收紧 `fields.*` / facets / capability action（[morph.md §4](./morph.md)），`schema_refs[]` 只验业务字段 | `ak.morph.stage.set` |
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

枚举值在 v1 内**固定**，任何 profile MUST NOT 新增 stage value；细粒度业务状态（`needs_review` / `qa` / `signed_off` 等）只能放在 domain-named `fields.<domain>_status`（bare `status` 是 hard-reject 保留名），是本地产品语义，**不**在协议级 stage 表达，也**不**参与 canonical admission（§5.3.4）。

#### 5.3.3 转换规则（reducer-enforced 硬约束)

**v1 没有 per-Realm stage transition matrix 的 carrier**：核心 reducer 不强制 stage 之间的方向（`done → in_progress` 回炉、`cancelled → planned` 复活均合法），这就是 stage 转换的全部方向规则；receiver MUST NOT 依据 Realm 私有配置、`metadata.fields.*` 取值、部署配置或服务端硬编码矩阵收紧 `ak.<kind>.stage.set` 的 admission（§5.3.4）。以下硬约束 MUST 由 core reducer 强制：

1. **物理终态优先**:对象 `state ∈ {redacted, tombstoned, deleted}` 时,`ak.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_already_terminal"`。
2. **non-active 拒写**:对象 `state=archived` 时,`ak.<kind>.stage.set` MUST 返回 `failed_precondition`,`reason="<kind>_not_active"`(与 §5.1 update on non-active 同语义);想推进 stage 必须先 `ak.<kind>.restore`。
3. **`stage_changed_at` reducer-derived**:reducer **MUST** 忽略 wire payload 中 actor-supplied 的 `stage_changed_at`,以触发 event 的 `created_at` 覆盖。
4. **same-value self-transition no-op**:`ak.<kind>.stage.set` 把 `stage` 设为与当前相同值时,reducer **不更新** `stage_changed_at`,且不计入审计变更(与 §5.1 `ak.<kind>.archive` 在 same-state 时 fail 的规则**不同** —— stage 是软进度字段，允许 idempotent no-op)。
5. **stage 变更不携带 reason 字段**:`ak.<kind>.stage.set` payload **不**定义 reason / note / explanation 字段。需要解释时 SHOULD 在该对象的 discussion track 发 Message 并通过 Relation `references` 指向本次 stage event;事件日志本身的 `created_by` / `created_at` 已经是审计归属真源。reserved-name guard:对象顶层与 `fields.*` 上 `stage_reason` / `stage_note` / `stage_explanation` / `stage_comment` MUST 被 forbidden-wire-fields 拒绝。
6. **`ak.<kind>.update` 禁写 stage**:patch path `stage` / `stage_changed_at` MUST 被 forbidden-wire-fields 拒绝(单源:stage 变更只能走 `ak.<kind>.stage.set`)。

#### 5.3.4 与本地 workflow 的关系（normative）

**v1 不提供可互操作的 Realm workflow profile。** 没有 profile object、安装 / 更新 Event、capability、typed current result family 或 `transition_contracts` 条目能声明 workflow state、state 到 stage 的映射或 transition matrix；实现 MUST NOT 把 Realm 私有 metadata key、部署配置文件、数据库表或服务端硬编码 transition matrix 当作这样的 carrier——它们没有 signed authority、authority-commit basis、版本与跨 Station 语义，两个 conforming 实现据此会对同一条 `ak.<kind>.stage.set` 得出不同 admission 结果。

- actor 通过 `ak.<kind>.stage.set` 直接推进 stage，reducer 只执行 §5.3.3 硬约束；本节不给任何实现“按 profile 收紧”的许可。
- 细粒度 workflow state（“In Dev / Reviewing / QA”等）是本地产品关注点：放在 domain-named `metadata.fields.<domain>_status`（bare `status` 是 [`forbidden-wire-fields.json`](../../artifacts/registry/forbidden-wire-fields.json) 的 hard-reject 保留名）或 Morph schema 字段里，不进入 canonical Event admission，跨实现不保证一致解释。
- 跨 Realm / 跨实现只认 8 值 `stage`：维护本地细粒度状态的产品 SHOULD 在本地状态变化时由客户端另发 `ak.<kind>.stage.set` 写入对应粗粒度值；dashboard 只聚合 `stage`（同一个 `stage=in_progress` bucket 涵盖各产品自定义的“In Dev / Reviewing / QA”）。

Rationale（informative）：内建状态模型、领域转移表与写入者在 canonical registry 冻结；Realm policy 不能动态定义新的 typed current result 模型或覆盖内建目标。per-Realm profile 只可按已有注册合同收窄取值和业务约束。

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
实现 MUST NOT 在各 schema / reducer 中另建一份手写分类。其中 `ak:call:` 与
`ak:grant:` 是 `event_derived`，分别从 `ak.call.create` 与
`ak.capability.grant` 的 Event ID 重类型化为相同 33-octet token。`ak:session_grant:` 则是
`identity_authority="issuer_record"` 的 `suite_tagged_full_digest`：从 closed
`ak.session_grant.issuance.v1` preimage 派生，并以 `(issuer_id, typed_id)` 作为 storage identity key；它
不是 Event ID。其首字节是完整 digest-suite wire code，不得按 Realm 的“保留零 nibble + 低 4 位
suite”解释；具体合同见 [`../identity/key-management.md` §6.1](../identity/key-management.md)。

`notification_projection` 使用 `suite_tagged_full_digest` 与 `identity_authority="source_evidence"`，其 closed preimage、域分隔和 SHA-256 算法由 ID registry 的 `notification_projection_identity_contract` 及 [`read-receipts.md` §6.3](../discovery/read-receipts.md#63-notification-派生-projection) 固定。身份键为完整 typed ID；验证责任是校验原始源 Event、接受证据和 recipient context 后重算身份，不要求独立 producer genesis signature。此例外只适用于普通通知投影，不适用于 Agent approval 的 `notification` ID。

`producer_allocated` UUIDv7 只提供时间排序与随机冲突概率，**不证明谁有权分配该 ID**。其协议身份键 MUST 是 `(mint_authority, typed_id)`，`mint_authority` 是该 ID 首次持久出现时通过接收校验的 genesis proof signer DID。存储与索引 MUST 原子保留这个二元组：同 authority + 同 ID + 同内容是幂等重放；同 authority + 同 ID + 不同内容 MUST 拒绝并隔离；不同 authority 即使 UUID 相同也是不同身份。裸 typed-ID 查找、跨 authority 去重、last-writer-wins 修复以及未绑定签名的预占位都 MUST fail closed。该规则由 ID registry 顶层 `producer_allocated_identity_contract` 机读定义，所有 `identity_authority="producer_signature"` 行统一继承。

并非所有 ID kind 都是 producer-allocated `ak:<kind>:<uuidv7>`。Event-derived kind 使用上述
suite-tagged 完整 digest token，此外 `ak:trust_domain:` 是 deployment-scoped replay boundary 标识：其 wire form 为
`ak:trust_domain:<trust_domain_label>`，`<trust_domain_label>` 是稳定的部署信任域标签（例如
`ak:trust_domain:did.webvh.acme.example`），不是 UUID。它 create-locked 在 Realm `trust_domain`
字段上，MUST 匹配部署 `ServiceDescribe.trust_domain` 与 Realm receive context（见
[`realm-and-space.md` §2.3](./realm-and-space.md)）。

`` / `ak:cursor:` / `ak:realm_commit:` 等同步 / 状态原语的 wire form 见各自章节与 `artifacts/registry/id-kind-registry.json`，不在本协作图对象 ID 约定表内。上表只是常见 wire value 形态摘要，完整 ID kind 注册表及唯一真源见 `artifacts/registry/id-kind-registry.json`。本节不决定字段名：普通 canonical object 主键仍是 `id`，Event / Receipt / Backup 等 artifact 可用 `<artifact>_id`，Blob / Snapshot / MLS 等 reference 形态按 §2.1 使用 `_ref`。

### 6.1 Policy 对象 vs 内联配置的字段命名约定（normative）

实现者经常困惑：同一个对象上既有 `<axis>_profile` / `<axis>_policy` 这样的内联枚举字段（如 `federation_policy`），又有 `<axis>_policy_id` 这样指向独立 Policy 对象的字段（如 `policy_id`、`retention_policy_id`、`disclosure_policy_id`、`rate_limit_policy_id`）。这是有意区分，规则如下：

- **`<axis>_profile`**：v1 协议级**固定选项**（create-locked 或 reducer-enforced 收敛），值是封闭 enum 字符串（`"mls_rfc9420"` / `"quorum"` / ...）。schema 内联约束，无需引用独立对象。Event／RealmCommit 的 content-address suite 不是 profile 字段，而是 current-v1 全局固定合同。
- **`<axis>_policy`**：v1 协议级**软策略字段**，值仍是 enum 字符串（`"open"` / `"restricted"` / `"closed"` / `"quarantine"` 等），但描述运行时执行策略，与其他 typed current result state 有交互。同样内联，不通过引用对象。
- **`<axis>_policy_id`**：指向独立 Policy 对象（`ak:policy:<uuid>`）的 ID，pattern `^ak:policy:[0-9a-f]{8}-...`。Policy 对象自身有 schema 与版本，可以被多个对象共享、被 governance event 修订。独立对象用于：(a) 跨对象复用、(b) 大体积或频繁变更、(c) 需要独立审计 / 签名链。
- **`<axis>_floor`**：某条加密 / 隐私轴上的**下限**字段，值与对应 `<axis>_profile` 取同一封闭 enum，但语义是"只能向上收紧、MUST NOT 放宽继承到的上游基线"。它用于真实子作用域（Circle）声明比父 Realm 更严格的下限；authorization-transparent 的 Space 只表达 placement 谓词，不承载 floor 值。effective 值取上游 `_profile` 与各 scope `_floor` 的更严格者（见 [`circle.md` §7](./circle.md)）。

判定流程：写新字段时若是**封闭 enum**（值集已知、协议级固定）用 `_profile` 或 `_policy`；若是**指向 Policy 对象**用 `_policy_id`；不得在同一对象上同时定义 `xxx_policy` 与 `xxx_policy_id` 表示同一个轴。若字段引用的是"授权该决策的 policy revision Event"，使用带 event 语义的 `_ref` 名称，例如 `policy_event_ref`，不得与 `policy_id` 混用。

公共字段示例：

```json fragment
{
  "id": "ak:strand:ATH75ame6bMfYpXtcoLOVb7FKmgpWVniZZqVBz1dUdQa",
  "schema": "ak.schema.strand.v1",
  "realm_id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5",
  "created_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "created_at": "2026-04-26T00:00:00Z",
  "updated_by": {"kind":"account","account_id":{"principal_id":"ak:did_core:webvh:z2dmjZ7p8K3pV4cXbKqL2nMsR9tWfH","station_id":"ak:did_core:webvh:z6mkfixturestationexample"}},
  "updated_at": "2026-04-26T00:00:00Z"
}
```
## 7. Reducer 总则

Reducer 总则的 normative 表述以 [`event-and-patch.md` §3](./event-and-patch.md#3-typed-reducer) 为唯一权威，验证步骤以 [`event-and-patch.md` §4](./event-and-patch.md#4-验证边界) 为唯一权威；本节不再重复列出验证步骤，避免两份独立维护的清单漂移。

§5 state-transition 表与 §5.1 `failed_precondition` reason-code 族属于本节关注的"对象 lifecycle 层 reducer 行为"; 它们与 `event-and-patch.md` §3—§4 (Event-level reducer 总则与验证边界) 形成"对象层 ↔ 事件层"两个互补侧面，均受 [`../authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md) 统一约束。

## 8. 规范性引用

- 完整 ID kind registry：`artifacts/registry/id-kind-registry.json`。
- Schema registry：`artifacts/registry/schema-registry.json` 与 [`../conformance/schema-registry.md`](../conformance/schema-registry.md)。
- Canonical JSON、hash、签名、cursor、HLC、rank 编码：[`../conformance/encoding.md`](../conformance/encoding.md)。
- Reducer conformance vector：[`../conformance/conformance-vectors.md`](../conformance/conformance-vectors.md)。
