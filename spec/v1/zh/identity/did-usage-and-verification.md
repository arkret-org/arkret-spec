---
title: DID 使用与验证边界
status: candidate
normative: true
stability: v1
updated: 2026-07-29
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按
[`../conformance/normative-language.md`](../conformance/normative-language.md)
解释；仅大写形式具规范约束力。

## 1. 目标与总原则

本文集中回答两个问题：

1. Arkret wire 中哪些 identifier 字段承载 DID 或 DID URL；
2. 哪些业务场景真正需要验证 DID 控制权，哪些场景只把 DID 当作稳定身份锚点。

DID 在绝大多数业务路径中只是稳定、可比较、可索引的主体标识。字段承载 DID **不等于**
读取或写入该字段时必须解析 DID Document，更不等于必须发起在线网络请求。实现 MUST 把下列
四件事分开：

1. **语法校验**：确认值是 bare DID、DID URL 或其它已声明 identifier 形态；
2. **标识使用**：比较、索引、去重、路由、授权主体匹配或展示 DID；
3. **签名验证**：使用已经接受并固定到相应 auth-state / key epoch 的公钥验证某个 proof；
4. **DID 权威验证**：按 DID method、resolver policy、history / controller proof 与 trust
   evidence 建立或更新“该 DID 控制哪些 key / service / delegation”的可信绑定。

第 1 项在 wire ingress 执行；第 2 项是普通业务路径；第 3 项按签名对象的协议要求执行；只有
第 4 项属于本文所称的“验证 DID”。前三项不得被实现成“顺便在线解析 DID”。DID 权威验证是
少量、显式的信任边界操作，不能成为普通对象读取、列表渲染或每次 Event 提交的隐式前置条件。

## 2. DID 字段总表

本节按**字段语义族**列出 v1 中承载 DID 的 identifier。对象专属 schema 仍是字段必填性与
精确 shape 的单一真相源；本表是跨 schema 的 value-category 总表。新增 DID 字段 MUST 同步
更新本节，并遵守 [`../models/common-fields.md` §2.1](../models/common-fields.md) 的 `_id` /
`_ref` / `_did` 命名规则。

### 2.1 必为 bare DID 的字段

下表中的值 MUST 是不含 path、query 或 fragment 的 bare DID。复数形态中的每个元素遵守同一
规则。

#### 2.1.1 `*_id` / `*_ids` 中的 DID 封闭判据

看到 `_id` 不能默认判断为 DID。只有下表 semantic stem（可带角色前缀）的字段在对应 schema
声明为 DID 时属于 DID-as-id；未命中者默认按 `id-kind-registry.json` 或对象专属 schema
解释，不得按字符串前缀猜测。

| semantic stem | DID 字段实例 | 反例 / 边界 |
| --- | --- | --- |
| `actor_id` / `actor_ids` | `actor_id`、`sender_actor_id`、`target_actor_id`、`watcher_actor_id`、`writer_actor_id`、`source_actor_id`、`approver_actor_id`、`closer_actor_id`、`approval_actor_ids[]`、`assigned_actor_ids[]` | `actor_profile_id` 是 `ak:actor_profile:` typed ID，不是 DID。 |
| `principal_id` / `principal_ids` | `principal_id`、`creator_principal_id`、`managed_principal_id`、`recipient_principal_id`、`sender_principal_id`、`target_principal_id`、`accountable_principal_id`、`accountable_principal_ids[]` | `account_id` 是 deployment-local account identifier。 |
| `service_id` / `service_ids` | `service_id` 及带角色前缀的 `source_`、`destination_`、`recipient_`、`requester_`、`issuer_`、`provider_`、`peer_`、`principal_server_`、`policy_server_`、`verification_`、`coordinator_`、`log_`、`media_`、`generated_by_`、`via_`、`allowed_`、`trusted_` service id(s) | endpoint URL、`service_kind`、deployment instance id 不是 DID。 |
| Agent / Applet actor stem | `agent_id`、`coordinator_agent_id`、`expected_coordinator_agent_id`、`addressed_agent_ids[]`、`participating_agent_ids[]`、`desired_agent_ids[]`、`effective_agent_ids[]`、`bot_actor_id`、`ghost_actor_id` | `applet_id` 是 §2.3 的多态例外；`device_id` 永远不是 DID。 |
| Organization stem | schema 明确声明的 `organization_id`、`organization_did`、`owning_organizations[]`、`controller_organization`、`controlling_organization`、`realm_operator_organization` | Realm / Circle / Space 的 organization metadata object id 若未来登记 typed kind，必须另用明确字段，不能复用这些 DID stem。 |
| 其它已登记责任 stem | `controller_id`、`subject_id`、`holder_id`、`publisher_id`、`signer_id`、`requester_id`、`auditor_id`、`audit_actor_id`、`audit_service_actor_id`、`account_authority_id` | `realm_id`、`device_id`、`event_id`、`grant_id`、`policy_id`、`invite_id`、`session_id`、`transaction_id` 等不是 DID。 |

带角色前缀不会改变 value category：例如 `recipient_service_id` 仍是 service DID，
`recipient_principal_id` 仍是 principal DID。反之，任意 `_id` 不能仅因出现在 actor 附近就
自动提升为 DID。

#### 2.1.2 bare DID 字段名穷举

下表穷举当前 v1 schema 中“命中时必为 bare DID”的字段名；同名字段的嵌套路径不重复展开，
复数字段的每个元素均为 bare DID。`subject`、`audience`、`applet_id`、普通 `id` 与多态 ref
不在本表，统一见 §2.3。DID method 名称和 `device_signing_key` 也不在本表，见 §2.4。

| 字段族 | 当前字段名（穷举） |
| --- | --- |
| Actor / principal / controller | `actor_id`、`actors`、`sender_actor_id`、`source_actor_id`、`target_actor_id`、`watcher_actor_id`、`writer_actor_id`、`principal_id`、`creator_principal_id`、`managed_principal_id`、`recipient_principal_id`、`sender_principal_id`、`target_principal_id`、`accountable_principal_id`、`accountable_principal_ids`、`allowed_principal_dids`、`denied_principal_dids`、`subject_id`、`target`、`controller`、`controller_id`、`controller_subject`、`controller_subject_id`、`holder`、`holder_did`、`holder_id`、`owner`、`local_admin_subject`、`account_authority_id`。 |
| Agent / Applet actor | `agent_id`、`bot_actor_id`、`coordinator_agent_id`、`expected_agent_did`、`expected_coordinator_agent_id`、`ghost_actor_id`、`recording_agent`、`addressed_agent_ids`、`desired_agent_ids`、`effective_agent_ids`、`participating_agent_ids`、`approved_recipient_audit_actor_id`、`audit_actor_id`、`audit_service_actor_id`、`recipient_audit_actor_id`。 |
| Service / provider / peer | `service_id`、`allowed_service_ids`、`coordinator_service_id`、`destination_service_id`、`generated_by_service_id`、`issuer_service_id`、`log_service_id`、`media_service_id`、`new_recipient_service_id`、`peer_service_id`、`policy_server_id`、`principal_server_id`、`provider_service_id`、`recipient_service_id`、`registry_service_id`、`requester_service_id`、`source_service_id`、`verification_service_id`、`via_service_ids`、`trusted_directory_services`、`trusted_principal_services`、`denied_principal_services`、`follower_providers`、`heroes`、`hub_provider`、`origin_provider`、`relay_provider`、`target_providers`、`peer`。 |
| Organization / authority / witness | `organization`、`organization_did`、`organization_id`、`owning_organizations`、`declared_organization_hints`、`controller_organization`、`controlling_organization`、`realm_operator_organization`、`recovery_controller_organizations`、`range_completeness_witnesses`、`recovery_members`、`authority_did`、`enrollment_authority_did`、`witness_did`。 |
| 审批、邀请、审计与责任角色 | `acknowledged_by`、`appellant`、`appellant_did`、`applicant_did`、`approval_actor_ids`、`approved_by`、`approved_key_issuers`、`approver_actor_id`、`approvers`、`assigned_actor_ids`、`assigned_to`、`auditor_id`、`authorized_by`、`cancelled_by`、`changed`、`changed_by`、`closer`、`closer_actor_id`、`contact`、`created_by`、`delivered_to`、`delegation_path`、`denied_subjects`、`executed_by`、`inheritance_chain`、`invitee`、`inviter`、`iss`、`issuer`、`left`、`members`、`participants_unordered`、`produced_by`、`publisher_id`、`received_by`、`removed_by`、`reporter`、`requested_by`、`requester`、`requester_did`、`requester_id`、`required_endorsers`、`resolved_by`、`restored_by`、`reviewer`、`reviewer_did`、`reviewers`、`revoked_by`、`routed_to`、`signer_id`、`signers`、`trusted_claim_issuers`、`trusted_handle_issuers`、`trusted_issuers`、`updated_by`。 |
| DID 原始材料 | `did`、`old_did`、`new_did`、`pairwise_did`、`operator_did`、`verifier_did`、`expected_did`、`peer_did`、`policy_server_did`、`principal_server_did`、`push_gateway_did`、`subscriber_did`。 |

例如，`handover_proof.actor_id`、`aad.actor_id` 与顶层 `actor_id` 在本表只占一个字段名；
它们仍分别受所在 schema 的 transcript / 必填性约束。字段含义不明确时必须回到对象 schema，
不能仅凭本表把任意同名应用私有字段提升为 DID。

字段名包含 `organization`、`issuer`、`reporter` 等角色词而不带 `_id`，是既有
crypto / governance 角色名词，不是创建新别名的先例。新增普通责任主体字段默认使用
`<role>_id` 或 [`../models/common-fields.md` §4.2](../models/common-fields.md) 规定的
`<verb>_by`。

### 2.2 必为 DID URL 的字段

下列字段指向具体 verification method，MUST 是带 `#fragment` 的 DID URL，不能只给 bare DID：

| 字段族 | 当前字段 |
| --- | --- |
| 通用 proof key | `verification_method`（包括 `proof.`、`auth_data.`、`binding_proof.`、`subject_proof.`、`source_proof.`、`signature_chain[].`、`signatures[].`、`share_releases[].` 等嵌套路径） |
| 带角色的 verification method | `authorization_verification_method`、`authorized_verification_method`、`recipient_verification_method`、`witness_verification_method` |
| DID Document 标准关系 | `verificationMethod`、`verificationMethod[].id`、`authentication`、`assertionMethod`、`keyAgreement` 中按 DID Core 允许的 DID URL reference |
| 封闭签名 / key reference | schema 明确声明为 DID URL 的 `kid`、`issuer_kid`、`recipient_hpke_kid`、`key_ref`、`authorization_ref`、`controller_authorization_ref`、`key_agreement_ref`、`approved_recipient_public_key_ref`、`recipient_public_key_ref` |

JOSE / JWK 的 `kid`、`key_ref` 与 `authorization_ref` 仅在其对象 schema 或 profile 明确要求
DID URL 时才属于本表；这些裸字段名不是 DID URL 的通用别名。`device_signing_key` 的
`did:key` 形态是自描述公钥编码，不会使设备成为 DID 主体。

### 2.3 条件性或多态字段

| 字段 | DID 条件 | 非 DID 形态 |
| --- | --- | --- |
| `subject` | schema 分支要求具体 principal / actor 时是 bare DID。 | Capability condition selector 或其它显式 selector shape。 |
| `applet_id` | 个别 Applet package / install profile 允许 Applet actor DID 时是 bare DID。 | canonical Applet object 使用 `ak:applet:<uuidv7>` typed ID。消费者 MUST 由 schema 分支判定，不能按字段名猜测。 |
| `from_ref` / `to_ref` / `target_ref` / `object_ref` | polymorphic reference 指向 Actor 时可以是 bare DID。 | 指向普通对象时是 `ak:<kind>:` typed ID；也可按所属 schema 使用 content-addressed / profile-scoped ref。 |
| `target_source_ref` | service-targeted to-device 分支中可以是 service DID。 | own-device / member-device 分支中是 `ak:device:` typed ID。 |
| `resource_id` | Directory announce / withdraw / appeal 指向 Actor 时可以是 bare DID。 | Realm / Applet typed ID 或 directory profile 明确允许的 handle。 |
| `id` | DID Document 顶层 `id` 或 conformance issuer object 的 `id` 是 bare DID；verification method / service entry 的 `id` 是 DID URL。 | 普通 canonical object 的 `id` 是 `ak:<kind>:` typed ID，其它局部对象由自己的 schema 定义。 |
| `kid` | 签名 profile 明确要求 controller key 时是带 fragment 的 DID URL；仅表达本地 key label 的 profile 不是 DID。 | JWK / JOSE profile-local key label、device-local `ak:device:` key id 或其它 schema-scoped string。 |
| `audience` | schema 明确把 audience 限定为一个 service / principal 时可以是 bare DID。 | Realm ID、trust domain 或 profile 声明的 audience string / array。 |

多态字段必须先由所在 schema / discriminator 确定分支，再校验值；实现 MUST NOT 用
`starts_with("did:")` 代替 schema 分派或把 DID 自动转换成普通对象 ID。

### 2.4 明确不是 DID 的 `*_id`

| 类别 | 字段 / 形态 | 规则 |
| --- | --- | --- |
| Canonical protocol object | `id` 以及 `realm_id`、`circle_id`、`space_id`、`strand_id`、`message_id`、`morph_id`、`relation_id`、`view_id`、`policy_id`、`grant_id`、`invite_id`、`event_id`、`blob_id` 等 | 使用 [`id-kind-registry.json`](../../artifacts/registry/id-kind-registry.json) 登记的 `ak:<kind>:` typed ID。 |
| Device | `device_id` | `ak:device:<uuidv7>`；设备不是 actor principal，没有设备 DID。 |
| Deployment account / session | `account_id`、`session_id`、`transaction_id`、`operation_id` 等 | 由各自 schema 定义的 deployment-local 或 operation identifier；不得当作 principal DID。 |
| 人类可读与外部标识 | `handle`、邮箱、手机号、OIDC `sub`、external user / tenant / message id | 只能用于发现、登录、claim 或 bridge 映射；不得直接成为 Arkret 授权主键。 |
| DID method / key material | `accepted_did_methods[]`、`accepted_subject_did_methods[]`、`allowed_did_methods[]`、DID method version 的 `method`、`device_signing_key` | 前四者是 `did:<method>` method 名称，不是主体 DID；`device_signing_key=did:key:...` 是 DID 形态的自描述公钥材料，不是设备身份，也不得对其发起网络解析。 |
| Key / digest / cursor / reference | `key_id`、schema 未声明为 DID URL 的 `kid`、`*_digest`、`cursor`、`*_ref` | 分别是 key label、JOSE/JWK key id、摘要、游标或引用材料；仅在 schema 明确声明的多态 ref 分支中才可能承载 DID。 |

## 3. 普通业务路径：只使用身份锚点

已经建立可信绑定后，下列操作只需要把 DID 当作 opaque identity key，不得因此触发 DID
Document 解析、history 验证或网络请求：

- profile、成员、消息、通知、已读状态、列表、搜索结果与审计记录的读取和渲染；
- DID 的 equality、set membership、索引、去重、分组、排序、日志归属与 selector 匹配；
- 使用已接受 auth-state 中的 `actor_id` / `principal_id` / `service_id` 做 capability、
  membership、policy、blocklist 或 routing binding 求值；
- 已认证 session 中由同一 accepted device / agent key epoch 签署的普通 Event 提交；
- replay、backfill、snapshot 重放或历史查询已经携带并命中 pinned auth-state / historical
  verification binding 的材料；
- 使用已物化的 `member_delivery_binding` 路由到已经验证并被 Realm policy 接受的 service DID；
- 展示 verification badge 的缓存状态。UI 可以显示 `verified` / `stale` / `unknown`，但显示路径
  不能升级成 authority path。

普通签名对象仍 MUST 验证签名、canonical transcript、nonce / sequence、scope 与 authorization。
该验证应使用相应 Seal / auth-state / device authorization / agent signer evidence 中已经接受的
公钥绑定。**验证签名不等于重新验证 DID**；实现不得仅因签名对象含 `actor_id` 或
`verification_method` 就对 resolver 发起请求。

## 4. DID 权威验证的封闭触发条件

只有下表情形需要建立、刷新或替换 DID 权威绑定：

| 触发场景 | 必须验证的内容 | 是否允许复用既有验证结果 |
| --- | --- | --- |
| 一个此前未被本 trust domain 接受的 DID 首次跨越信任边界 | method allowlist、DID Document / method history、controller proof、role / purpose、必要 witness evidence | 仅当已有结果绑定相同 DID、trust domain、purpose、policy digest 与可接受 freshness 时可复用。 |
| 账号注册、认领、恢复或 service account 与 principal DID 首次绑定 | 当前控制 proof、session / device、audience、nonce、有效期与 account binding | 不得用邮箱、OIDC `sub`、passkey 登录成功或仅有 DID 字符串替代。 |
| 出现新的 `verification_method`、device generation、agent signer epoch、service signing key 或 controller | 新 key 的 controller / delegation、用途、有效期、前序 history / authorization | 已接受旧 key 不能自动授权新 key。 |
| DID rotation、recovery、deactivation、method continuity 或 service endpoint / delegation 变更 | 精确历史版本、previous head / sequence、recovery / continuity proof、目标 trust domain 与 policy | 必须按事件接受时点或显式 pinned version 验证，不能只看当前文档。 |
| 新 service DID 被加入 federation peer、plaintext-visible service、media / push / audit / directory / policy allowlist | service control、service kind、endpoint delegation、trust domain、policy scope | 已验证的同一 service binding 在有效期内可复用；普通请求不重复解析。 |
| membership / MLS admission 引入此前未接受的 principal、pairwise DID 映射或新的 delivery service binding | principal / pairwise link、KeyPackage / device or agent key binding、service binding | 既有 active member 的普通消息、presence、read receipt 不触发。 |
| 高风险写入显式要求的 freshness 已过期，或收到 rotation / deactivation / witness fork / policy-change invalidation | 与该风险级别对应的最新 method evidence 或指定历史版本 | 低风险读路径不得因后台刷新失败而偷偷 live fallback；高风险操作 fail closed 或等待刷新。 |
| 验证第三方 claim / receipt / attestation 时，本地没有其 issuer key 的已接受绑定 | issuer DID、verification method、claim purpose / audience / status / revocation | 同 issuer、key epoch、purpose 与 policy 下可复用。 |

除上述触发条件外，业务代码 MUST NOT 自行增加“保险起见再 resolve 一次”的路径。若一个业务
动作认为需要 DID 权威验证，它必须能指出本表中的触发场景、所需 purpose 与 freshness policy；
无法指出时应按普通身份锚点处理。

## 5. 验证结果、缓存与失效

DID 权威验证的产物 MUST 是可复用、可审计的 verified binding，而不是一个无上下文的
`verified=true`：

| 字段 | 要求 |
| --- | --- |
| `did` | 被验证的 bare DID。 |
| `trust_domain` / `purpose` | 结果适用的本地信任域与用途（principal、service、issuer、controller 等）。 |
| `method` / `verification_method` | DID method 与被接受的具体 DID URL；不适用具体 key 时可省略后者。 |
| `document_digest` / `history_head` / `version_id` | 固定验证依据；method 不支持的字段可省略，但必须记录该 limited-trust 能力。 |
| `evidence_digest` / `policy_digest` | method evidence 与 resolver / Realm policy 的绑定。 |
| `verified_at` / `refresh_after` / `expires_at` | 验证时间、后台刷新点与硬失效点；具体必填性由 method / risk profile 决定。 |
| `status` | `active`、`stale`、`deactivated`、`quarantined` 或等价封闭状态。 |

实现 SHOULD 先查本地 accepted auth-state、verified binding store 与 resolution cache，再决定是否
需要后台刷新。缓存 TTL 到期本身不得把普通业务请求变成在线 DID resolution；它只会把
authority-grade 结果标为 stale。仅当 §4 的触发场景要求新鲜证据时，调用方才等待刷新或 fail
closed。

rotation、deactivation、witness fork、controller / service delegation 变化、Realm resolver
policy 变化和 explicit revocation MUST 使受影响 binding 失效或进入 stale / quarantined。
失效索引至少能按 DID、verification method、history head、trust domain、purpose 与 policy
digest 定位。后台 watcher / refresh 可以主动更新绑定，但不得在失败时把信任降级到另一个 DID
method。

## 6. 实现分层要求

- Wire / model 层 MUST 用强类型区分 `Did`、`DidUrl` 与 `ak:<kind>:` typed ID；不得把所有
  identifier 长期保留为无类型 `String` 后靠前缀猜测。
- Resolver / verifier 层负责 §4–§5；业务 reducer、projection、query、UI 与 routing 代码只消费
  verified binding 或 accepted auth-state，不直接持有通用网络 resolver。
- Event ingress MUST 对每个签名做密码学验证，但 SHOULD 从 Event 所引用的 Seal / auth-state、
  device authorization、agent signer evidence 或 pinned historical binding 取得 key。只有缺少
  该绑定且 §4 允许建立新信任时才进入 DID 权威验证；否则 fail closed。
- Service endpoint 发现与 DID 控制权验证是两件事。已接受的 `member_delivery_binding` /
  `ServiceDescribe` binding 是普通路由输入；发现到一个新 endpoint 不会自动证明 service DID
  控制权，反过来也不要求每次 HTTP 请求都重新解析 endpoint。
- 测试 MUST 能证明：普通读写命中已接受 binding 时 resolver 网络调用次数为零；新 DID / 新 key
  / rotation / recovery / invalidation 场景才调用 authority resolver；缓存失效不会让低风险读取
  阻塞或 live fallback。

## 7. 复审核对表

新增或修改 identifier 字段时逐项确认：

1. 它是主体 DID、具体 verification method、普通 typed ID，还是 polymorphic ref；
2. 字段名与 §2 总表及 `id-kind-registry.json` 一致；
3. schema 使用 bare DID 与 DID URL 的正确约束；
4. 业务路径只是使用锚点，还是命中 §4 的显式权威验证触发条件；
5. 若需要验证，purpose、trust domain、freshness、历史时点、缓存与失效条件是否完整；
6. 是否错误地给 device、Realm、Message 等非主体对象发明 DID；
7. 是否把签名验证、session 认证、handle 双向验证或 endpoint TLS 误写成 DID 控制权验证。
