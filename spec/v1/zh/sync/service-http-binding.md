---
title: Service HTTP Binding
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - authority-commit-log.md
  - service-api-schema.mdx
  - ../conformance/normative-language.md
---

# Service HTTP 绑定

规范关键字按[规范语言](../conformance/normative-language.md)解释。HTTP path、method、operation ID、request/response schema
和错误映射的唯一机器真相源是 `operation-registry.json`、`arkret-service-api.openapi.yaml` 和
`operations-error-mapping.json`。本页只规定 authority-commit 切换后的绑定边界，不维护一份并行端点全表。

## 1. Surface 分层

- `/_arkret/gate/*` 是无 Realm 会话前置流程；它不能接纳 Realm Event。
- `/_arkret/self/*` 由已认证账号调用自己的 Account Station。
- `/_arkret/peer/*` 只用于验证过的 Station-to-Station 转发、复制和计划 handoff。
- `/_arkret/open/*` 只返回明确登记的公开对象；返回 locator 不等于证明 authority。

所有非 `open` 端点必须在解析大型 body 之前执行身份、audience、重放窗口和字节上限检查。
未授权的 hidden Realm/Circle/Sidecar 必须使用不可枚举的统一失败形态。

## 2. Event 提交

### 2.1 Self 提交

`POST /_arkret/self/events` 接受 `authority-commit-operations.schema.json#/$defs/submit_request`。Account
Station 必须先耐久保存 exact producer-signed Event，再解析 current authority bundle 并转发。
它只能返回 `queued`、`forwarding`、`committed`、`rejected` 或 `temporarily_unavailable` 的 schema 登记分支。
没有验证到 RealmCommit 时不得返回 `committed`或对其它成员 fanout。

### 2.2 Peer 转发

`POST /_arkret/peer/events` 只把 exact Event 转发给已验证的 current governance Station。请求必须使用
service-to-service authentication 绑定 source/destination service identity、operation、body digest 与有界时间窗。
非当前 authority 的接收方只能重定位或转发，不能签发 RealmCommit。

### 2.3 幂等与不确定结果

exact Event retry 必须返回同一 committed outcome；同 Event ID 但 canonical bytes 不同必须
`duplicate_conflict` 且零写入。请求者在 response 丢失后重放原字节，不得重签或生成新幂等身份。

## 3. 读取与同步

### 3.1 Stream scan

`POST /_arkret/self/streams/scan` 一次只扫描一条 caller 获准的 Realm、Circle 或 Sidecar stream。
request 明确指定 `stream_ref`、起始 position、limit 和方向；response 返回连续 RealmCommit
及其可见 Event。页内和跨页都必须检查 position 严格递增和 `previous_commit_ref` 连续。

`POST /_arkret/peer/streams/scan` 使用相同 schema，但要求调用 Station 对该具体 stream 具有复制权。

`POST /_arkret/peer/streams/resolve` 只接受 canonical sorted/unique 的 exact committed refs；每项
必须同时给出 `event_id`、`commit_id`、`stream_ref` 与 `stream_position`。响应返回匹配的
`RealmCommit + Event`。调用方必须对缺项、任一字段不匹配、Commit 签名失败或 authority chain
不成立 fail closed。该操作用于 Directory 首次 ingest 等精确依赖验证，不得退化为按 Event ID
返回未提交 Event，也不得通过扫描另一条 stream 补齐。
获准 Realm stream 不自动授权 Circle 或 Sidecar stream。

#### 3.1.4 Typed current 读取

Typed current operation 只接受封闭 selector union。响应中的 revision 是最后影响该 typed row 的 Commit ID
与 stream position；不接受 caller 提供的通用 state key，也不暴露其它 stream head。

### 3.2 Snapshot + tail

首次 join、新设备和缓存修复使用 authority-signed typed snapshot，再从 snapshot 内每条获准
stream head 的下一 position 拉取 tail。Snapshot 不包含 typed current result chunk、通用 state root 或隐藏 stream
的 position。历史可见性仍由 join/history/retention policy 决定，不默认拉全历史。

#### 3.3.1.1 Discovery 投影

Directory、Invite 和分享链接只能提供 `realm_id`、authority locator candidate 和必要的 bootstrap hint。
客户端必须向 candidate 请求 nonce-bound authority bundle，从 Realm genesis 连续验证 old→new handoff chain，
然后才接受 current authority 的 snapshot/tail。

### 3.3.3 Peer 权威复制

Peer 复制只交付已签 RealmCommit、exact Event、typed snapshot 和获准的当前投影。消费 Station
验证 authority chain 和逐 stream 连续性，不重做一份可导出不同 accepted 结果的本地治理判决。

## 4. Authority discovery 与更换

### 4.1 Nonce-bound bundle

`POST /_arkret/open/realm-authority/bundle` 返回 `realm-authority-bundle.schema.json`。响应必须绑定
request nonce、Realm genesis、连续 handoff records、current generation/service identity 和公开 Realm stream head。
locator、TLS endpoint 或 DID route 只用来找到候选服务，不作为治理权证明。

### 4.2 Planned handoff

`POST /_arkret/peer/realm-authority/handoff` 只安装 old/new Station 对同一 transition body 的双签 handoff。
transition body 绑定完整 typed snapshot digest 和所有 Realm/Circle/Sidecar stream heads 的私有 manifest
digest。旧方在精确 cut 后永久拒写；新方未完整导入时不得启动任何 stream。

旧 authority 丢失且没有已完成 handoff 时，HTTP 层不定义 takeover、管理员自封或备份恢复写权。

## 5. MLS

MLS Genesis 与 Commit 仍是 producer-signed Event，由 current governance Station 接纳。Add Commit 使用
`mls-commit-submission.schema.json`，将 exact Commit Event 和所有 producer-signed Welcome delivery 作为一个原子请求；
任一 delivery 缺失、超限、claim 不匹配或 proof 无效时整体零写入。

Commit 成功后立即成为 winning epoch，Welcome 由治理 Station 的 recipient queue 耐久重试；不等待接收者
ACK 才提交。Station 只验证 RFC 9420 公开 transition、roster、sender 和 `key_access_revision`，
不持有 MLS private group state。

## 6. 错误与缓存

- `schema_violation`：closed schema、canonical encoding 或 typed ID 失败。
- `authority_mismatch`：目标不是验证后的 current authority。
- `stream_conflict`：expected position/predecessor 与当前 stream head 不符。
- `cas_conflict`：typed payload 的领域 `expected_revision` 不符。
- `epoch_mismatch`：MLS epoch/group-state/key-access revision 不符。
- `duplicate_conflict`：相同幂等身份或内容 ID 对应不同 canonical bytes。
- `temporarily_unavailable`：可安全 exact retry，且未产生 Commit。

包含授权结果、authority bundle、snapshot、Commit 或 Welcome 的响应默认 `Cache-Control: no-store`。
缓存的 public locator 必须遵循短 TTL，并在每次写入前重新验证 authority chain。

## 7. 非 HTTP 绑定

gRPC、WebSocket 和 MQ 可以复用同一 operation 和 schema，但不得创造 HTTP 不具有的 accepted 状态、
跨 stream 总序或更弱的 proof 验证。所有 transport 的幂等、字节上限、错误语义和权限必须等价。

## 8. 稳定引用锚点

下列章节号供其他领域规范稳定引用；具体 operation 始终以 machine registry 为准。

### 2.1 REST API 命名空间组织

`gate/self/peer/open/root/edge/find/server` 前缀只表达认证与网络边界，不改变同一 operation 的 typed schema 和 authority-commit 语义。

#### 2.1.2 Account authentication

Account 认证和 session grant 在 gate/self 边界完成，不因其成功而绕过 Realm Event 的 authority commit。

#### 2.2.2 Service authentication

Station-to-Station 请求必须绑定 exact source/destination service identity、operation ID、body digest 和重放窗口。

#### 2.2.3 Deployment-internal channel

部署内通道可使用独立认证 profile，但必须在 operation registry 逐项登记，不得作为通用 peer 降级路径。

### 2.2 端点契约规则

每个端点必须绑定唯一 operation ID、request/response schema、auth profile、body class 和错误集。

### 2.4 上传与二进制传输

Blob 和其它 binary operation 使用各自登记的 streaming/binary body contract，不与 Event submit 共用 JSON 上限。

#### 2.4.1 Content digest

带 body 的服务请求按登记 profile 绑定 Content-Digest；无 body 请求不得伪造 digest member。

### 2.4 字段级 Schema 索引

下表是 operation registry 的生成索引，只用于确保每个 operation 的 schema ref 在正文可检索；规范字段仍以被引用 schema 为准。

#### 2.4.1 Binding completeness index

<!-- BEGIN GENERATED OPERATION FIELD TABLE -->
| Operation | HTTP | Required | Optional | Constraints |
| --- | --- | --- | --- | --- |
| `ak.edge.applet.actor.read.resolve.v1` | `GET /_arkret/edge/applet/actors/{actor_id}` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_actor_view |
| `ak.edge.applet.command.transaction.v1` | `POST /_arkret/edge/applet/transactions` | - | - | request_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_request_body; response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_transaction_outcome |
| `ak.edge.applet.managed_actor.command.author.v1` | `POST /_arkret/edge/applet/managed-actors/author` | - | - | request_schema_ref=schemas/applet-install-authoring.schema.json#/$defs/author_request_body; response_schema_ref=schemas/applet-install-authoring.schema.json#/$defs/author_outcome |
| `ak.edge.applet.read.describe.v1` | `GET /_arkret/edge/applet/describe` | - | - | response_schema_ref=schemas/service-describe.schema.json |
| `ak.edge.applet.read.ping.v1` | `GET /_arkret/edge/applet/ping` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_ping_outcome |
| `ak.edge.applet.read.protocol_metadata.v1` | `GET /_arkret/edge/applet/protocols/{protocol}` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_protocol_metadata |
| `ak.edge.applet.realm.read.resolve.v1` | `GET /_arkret/edge/applet/realms/{realm_id_or_alias}` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_realm_view |
| `ak.edge.applet.third_party_locations.read.list.v1` | `GET /_arkret/edge/applet/third_party/locations` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_location_list |
| `ak.edge.applet.third_party_users.read.list.v1` | `GET /_arkret/edge/applet/third_party/users` | - | - | response_schema_ref=schemas/applet-edge-operations.schema.json#/$defs/applet_third_party_user_list |
| `ak.edge.push.command.apply_registration.v1` | `POST /_arkret/edge/push/registrations:apply` | - | - | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_registration_handoff_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_registration_handoff_outcome |
| `ak.edge.push.command.notify.v1` | `POST /_arkret/edge/push/notify` | - | - | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_notify_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_notify_outcome |
| `ak.edge.push.command.register_device.v1` | `POST /_arkret/edge/push/register-device` | - | - | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_register_device_request_body; response_schema_ref=schemas/push-operations.schema.json#/$defs/push_register_device_outcome |
| `ak.edge.push.command.unregister_device.v1` | `POST /_arkret/edge/push/unregister-device` | - | - | request_schema_ref=schemas/push-operations.schema.json#/$defs/push_unregister_device_request_body |
| `ak.find.directory.command.announce.v1` | `POST /_arkret/find/directory/announce` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryAnnounceOutcome |
| `ak.find.directory.command.withdraw.v1` | `POST /_arkret/find/directory/withdraw` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DirectoryWithdrawOutcome |
| `ak.find.directory.read.describe.v1` | `GET /_arkret/find/directory/describe` | - | - | response_schema_ref=schemas/service-describe.schema.json |
| `ak.find.directory.read.list_handles_for_subject.v1` | `POST /_arkret/find/directory/list-handles-for-subject` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_list_handles_for_subject_request_body; response_schema_ref=schemas/list-handles-for-subject-response.schema.json |
| `ak.find.directory.read.private_contact_discovery.v1` | `POST /_arkret/find/directory/private-contact-discovery` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_private_contact_discovery_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_private_contact_discovery_outcome |
| `ak.find.directory.read.resolve_agent_selector.v1` | `POST /_arkret/find/directory/resolve-agent-selector` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_agent_selector_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_agent_selector_resolution_outcome |
| `ak.find.directory.read.resolve_handle.v1` | `POST /_arkret/find/directory/resolve-handle` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_handle_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_handle_resolution_outcome |
| `ak.find.directory.read.resolve_organization.v1` | `POST /_arkret/find/directory/resolve-organization` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_organization_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_organization_resolution_outcome |
| `ak.find.directory.read.resolve_realm.v1` | `POST /_arkret/find/directory/resolve-realm` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_realm_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_realm_resolution_outcome |
| `ak.find.directory.read.resolve_target.v1` | `POST /_arkret/find/directory/resolve-target` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_resolve_target_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_target_resolution_outcome |
| `ak.find.directory.read.search_actors.v1` | `POST /_arkret/find/directory/search-actors` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_actors_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_actor_search_outcome |
| `ak.find.directory.read.search_organizations.v1` | `POST /_arkret/find/directory/search-organizations` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_organizations_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_organization_search_outcome |
| `ak.find.directory.read.search_realms.v1` | `POST /_arkret/find/directory/search-realms` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_realms_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_realm_search_outcome |
| `ak.find.directory.read.search_users.v1` | `POST /_arkret/find/directory/search-users` | - | - | request_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_search_users_request_body; response_schema_ref=schemas/directory-operations.schema.json#/$defs/directory_user_search_outcome |
| `ak.gate.account.command.abandon_identity_creation.v1` | `POST /_arkret/gate/account/identity-abandonments` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/identity_abandonment_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/identity_abandonment_outcome |
| `ak.gate.account.command.finalize_device_pairing.v1` | `POST /_arkret/gate/account/device-pairing/finalizations` | - | - | request_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_finalize_request_body; response_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_finalize_outcome |
| `ak.gate.account.command.introspect_session_grant.v1` | `POST /_arkret/gate/account/session-grants/introspect` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantIntrospectRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantIntrospectOutcome |
| `ak.gate.account.command.issue_controller_gate_attestation.v1` | `POST /_arkret/gate/account/controller-gate-attestations` | - | - | request_schema_ref=schemas/agent-authority-evidence.schema.json#/$defs/controller_account_gate_attestation_issue_request_body; response_schema_ref=schemas/agent-authority-evidence.schema.json#/$defs/controller_account_gate_attestation_issue_outcome |
| `ak.gate.account.command.issue_did_binding_challenge.v1` | `POST /_arkret/gate/account/did-binding-challenges` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/did_binding_challenge_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/did_binding_challenge_outcome |
| `ak.gate.account.command.issue_identity_binding_challenge.v1` | `POST /_arkret/gate/account/identity-binding-challenges` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/identity_binding_challenge_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/identity_binding_challenge_outcome |
| `ak.gate.account.command.issue_recovery_completion_grant.v1` | `POST /_arkret/gate/account/recovery-session-grants/issue` | - | - | request_schema_ref=schemas/recovery-authority.schema.json#/$defs/issue_recovery_completion_grant_request; response_schema_ref=schemas/recovery-authority.schema.json#/$defs/issue_recovery_completion_grant_outcome |
| `ak.gate.account.command.issue_session_grant.v1` | `POST /_arkret/gate/account/session-grants` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantOutcome |
| `ak.gate.account.command.logout.v1` | `POST /_arkret/gate/account/logout` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountLogoutRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountLogoutOutcome |
| `ak.gate.account.command.logout_auth_session.v1` | `POST /_arkret/gate/account/auth-sessions/logout` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthSessionLogoutRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthSessionLogoutOutcome |
| `ak.gate.account.command.pair_agent_key.v1` | `POST /_arkret/gate/account/agent-key-pair` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_key_pair_outcome |
| `ak.gate.account.command.pair_device.v1` | `POST /_arkret/gate/account/device-pair` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_pair_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/account_device_pair_outcome |
| `ak.gate.account.command.refresh_session_grant.v1` | `POST /_arkret/gate/account/session-grants/refresh` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantRefreshRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SessionGrantOutcome |
| `ak.gate.account.command.register.v1` | `POST /_arkret/gate/account/register` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_register_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_register_outcome |
| `ak.gate.account.command.request_erasure.v1` | `POST /_arkret/gate/account/erasure-requests` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_request_erasure_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_request_erasure_outcome |
| `ak.gate.account.command.revoke_session.v1` | `POST /_arkret/gate/account/session-grants/revoke` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/session_revoke_outcome |
| `ak.gate.account.exchange.create_handoff.v1` | `POST /_arkret/gate/account/authentication-handoffs` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_handoff_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_handoff_outcome |
| `ak.gate.account.read.claim_device_pairing_code.v1` | `POST /_arkret/gate/account/device-pairing/code-claims` | - | - | request_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_code_claim_request_body; response_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_code_claim_outcome |
| `ak.gate.account.read.onboarding.v1` | `GET /_arkret/gate/account/onboarding` | - | - | response_schema_ref=schemas/account-operations.schema.json#/$defs/account_onboarding_state |
| `ak.open.agent_pairing.command.submit_runtime_key_request.v1` | `POST /_arkret/open/agent-pairing/runtime-key-requests` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_outcome |
| `ak.open.agent_pairing.read.resolve.v1` | `POST /_arkret/open/agent-pairing/resolve` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pairing_resolve_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pairing_bootstrap |
| `ak.open.agent_pairing.read.runtime_key_request_status.v1` | `POST /_arkret/open/agent-pairing/runtime-key-requests/status` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_runtime_approval_status_outcome |
| `ak.open.device_pairing.command.stage.v1` | `POST /_arkret/open/device-pairing/requests` | - | - | request_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_stage_request_body; response_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_stage_outcome |
| `ak.open.device_pairing.read.resolve.v1` | `POST /_arkret/open/device-pairing/resolve` | - | - | request_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_resolve_request_body; response_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_bootstrap |
| `ak.open.device_pairing.read.status.v1` | `POST /_arkret/open/device-pairing/requests/status` | - | - | request_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_status_request_body; response_schema_ref=schemas/device-pairing.schema.json#/$defs/device_pairing_status_outcome |
| `ak.open.identity.read.resolution.v1` | `GET /_arkret/open/principals/{principal_id}/resolution` | - | - | response_schema_ref=schemas/identity-resolution.schema.json#/$defs/public_principal_resolution |
| `ak.open.invite_locator.read.resolve.v1` | `POST /_arkret/open/invite-locators/resolve` | - | - | request_schema_ref=schemas/principal-locator.schema.json#/$defs/principal_locator_resolve_request_body; response_schema_ref=schemas/principal-locator.schema.json |
| `ak.open.mimi.command.notify.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/notify` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_notify_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_notify_outcome |
| `ak.open.mimi.command.proxy_download.v1` | `POST /_arkret/open/mimi/proxy-download` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_proxy_download_outcome |
| `ak.open.mimi.command.report_abuse.v1` | `POST /_arkret/open/mimi/report-abuse` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_report_abuse_outcome |
| `ak.open.mimi.command.request_consent.v1` | `POST /_arkret/open/mimi/consent/request` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_request_consent_outcome |
| `ak.open.mimi.command.submit_message.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/messages` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_submit_message_outcome |
| `ak.open.mimi.command.update_consent.v1` | `POST /_arkret/open/mimi/consent/update` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_update_consent_outcome |
| `ak.open.mimi.command.update_room.v1` | `POST /_arkret/open/mimi/strands/{strand_id}/update` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_room_update_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_room_update_outcome |
| `ak.open.mimi.exchange.request_key_material.v1` | `POST /_arkret/open/mimi/key-material` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_key_material_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_key_material_outcome |
| `ak.open.mimi.read.identifiers.v1` | `POST /_arkret/open/mimi/identifiers/query` | - | - | request_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_request_body; response_schema_ref=schemas/mimi-operations.schema.json#/$defs/mimi_identifier_query_outcome |
| `ak.open.mimi.read.provider_directory.v1` | `GET /_arkret/open/mimi/provider-directory` | - | - | response_schema_ref=schemas/mimi-interop.schema.json |
| `ak.open.realm_authority.read.bundle.v1` | `POST /_arkret/open/realm-authority/bundle` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/authority_bundle_request; response_schema_ref=schemas/realm-authority-bundle.schema.json |
| `ak.open.service.read.resolution.v1` | `GET /_arkret/open/services/{service_id}/resolution` | - | - | response_schema_ref=schemas/identity-resolution.schema.json#/$defs/authenticated_service_resolution |
| `ak.open.third_party_invite.command.activate.v1` | `POST /_arkret/open/third-party-invites/activate` | - | - | request_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_activation_request_body; response_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_activation_outcome |
| `ak.open.third_party_invite.command.present_token.v1` | `POST /_arkret/open/third-party-invites/present` | - | - | request_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_present_request_body; response_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_present_outcome |
| `ak.open.third_party_invite.command.provision.v1` | `POST /_arkret/open/third-party-invites/provision` | - | - | request_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_provision_request_body; response_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_provision_outcome |
| `ak.open.third_party_invite.read.provisioning_status.v1` | `POST /_arkret/open/third-party-invites/status` | - | - | request_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_provisioning_status_request_body; response_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_provisioning_status_outcome |
| `ak.peer.account_status.command.submit.v1` | `POST /_arkret/peer/account-status` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_status_publication_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_status_publication_outcome |
| `ak.peer.account_status.read.resolve.v1` | `POST /_arkret/peer/account-status/resolve` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_status_resolve_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_status_resolve_outcome |
| `ak.peer.contacts.command.submit.v1` | `POST /_arkret/peer/contacts` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/peer_contact_submit_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/peer_contact_submit_outcome |
| `ak.peer.device_revocations.command.check.v1` | `POST /_arkret/peer/device-revocations/check` | - | - | request_schema_ref=schemas/device-revocation-state.schema.json#/$defs/device_revocation_gate_check_request_body; response_schema_ref=schemas/device-revocation-state.schema.json#/$defs/device_revocation_gate_check_outcome |
| `ak.peer.erasure_receipt.command.submit.v1` | `POST /_arkret/peer/erasure-receipts` | - | - | request_schema_ref=schemas/erasure-receipt-operations.schema.json#/$defs/erasure_receipt_submit_request_body; response_schema_ref=schemas/erasure-receipt-operations.schema.json#/$defs/erasure_receipt_submit_outcome |
| `ak.peer.erasure_receipt.resource.get.v1` | `GET /_arkret/peer/erasure-receipts/{receipt_id}` | - | - | response_schema_ref=schemas/erasure-receipt-operations.schema.json#/$defs/erasure_receipt_resource |
| `ak.peer.events.command.submit.v1` | `POST /_arkret/peer/events` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request; response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome |
| `ak.peer.events.read.resolve_committed.v1` | `POST /_arkret/peer/streams/resolve` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_request; response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/committed_event_resolve_outcome |
| `ak.peer.events.read.scan.v1` | `POST /_arkret/peer/streams/scan` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request; response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome |
| `ak.peer.invites.command.submit.v1` | `POST /_arkret/peer/invites` | - | - | request_schema_ref=schemas/invite-delivery-request.schema.json; response_schema_ref=schemas/invite-delivery-request.schema.json#/$defs/invite_delivery_outcome |
| `ak.peer.keys.keypackages.command.claim.v1` | `POST /_arkret/peer/keys/keypackages/claim` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_claim_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/peer_keypackages_claim_command_outcome |
| `ak.peer.keys.keypackages.read.claim.v1` | `POST /_arkret/peer/keys/keypackages/claims/query` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/peer_keypackages_claim_query_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/peer_keypackages_claim_query_outcome |
| `ak.peer.keys.read.lookup.v1` | `POST /_arkret/peer/keys/query` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/peer_keys_query_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/peer_keys_query_outcome |
| `ak.peer.mls.read.group_state_material.v1` | `POST /_arkret/peer/mls/group-state-material` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/MlsGroupStateMaterialRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/MlsGroupStateMaterialOutcome |
| `ak.peer.principal_genesis.command.submit.v1` | `POST /_arkret/peer/principal-genesis` | - | - | request_schema_ref=schemas/principal-operations.schema.json#/$defs/pcr_genesis_submit_request; response_schema_ref=schemas/principal-operations.schema.json#/$defs/pcr_genesis_submit_outcome |
| `ak.peer.realm_authority.command.handoff.v1` | `POST /_arkret/peer/realm-authority/handoff` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/handoff_request; response_schema_ref=schemas/realm-authority-handoff.schema.json |
| `ak.peer.realm_join.read.application_status.v1` | `POST /_arkret/peer/realm-joins/application-status` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_application_status_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_application_status_outcome |
| `ak.peer.realm_join.read.bootstrap.v1` | `POST /_arkret/peer/realm-joins/bootstrap` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_bootstrap_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_bootstrap_outcome |
| `ak.peer.realm_join.read.preview.v1` | `POST /_arkret/peer/realm-joins/preview` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_preview_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/peer_preview_outcome |
| `ak.peer.signal.command.relay.v1` | `POST /_arkret/peer/signal` | - | - | request_schema_ref=schemas/signal-relay.schema.json |
| `ak.root.identity.command.submit_did_operation.v1` | `POST /_arkret/root/identity/submit-did-operation` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DidOperationSubmitOutcome |
| `ak.root.identity.document.resource.get.v1` | `GET /_arkret/root/identity/document` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityDocumentView |
| `ak.root.identity.log.read.list.v1` | `GET /_arkret/root/identity/log` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityLogListOutcome |
| `ak.root.identity.organization_registration.command.ensure.v1` | `POST /_arkret/root/identity/organization-registrations:ensure` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationEnsureRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationOutcome |
| `ak.root.identity.organization_registration.command.prepare.v1` | `POST /_arkret/root/identity/organization-registrations:prepare` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationChallengeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationChallenge |
| `ak.root.identity.organization_registration.command.refresh.v1` | `POST /_arkret/root/identity/organization-registrations:refresh` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationRefreshRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationOutcome |
| `ak.root.identity.organization_registration.command.revoke.v1` | `POST /_arkret/root/identity/organization-registrations:revoke` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationRevokeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationOutcome |
| `ak.root.identity.organization_registration.resource.get.v1` | `GET /_arkret/root/identity/organization-registrations` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/OrganizationRegistrationOutcome |
| `ak.root.identity.read.resolve.v1` | `POST /_arkret/root/identity/resolve` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityResolveOutcome |
| `ak.root.identity.receipts.read.list.v1` | `GET /_arkret/root/identity/receipts` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/IdentityReceiptListOutcome |
| `ak.root.identity.recovery_policy.command.publish.v1` | `POST /_arkret/root/identity/recovery-policy` | - | - | request_schema_ref=schemas/recovery-policy.schema.json#/$defs/recovery_policy_publish_request; response_schema_ref=schemas/recovery-policy.schema.json#/$defs/recovery_policy_publish_outcome |
| `ak.root.identity.recovery_policy.resource.get.v1` | `GET /_arkret/root/identity/recovery-policy` | - | - | response_schema_ref=schemas/recovery-policy.schema.json#/$defs/recovery_policy_active_outcome |
| `ak.root.identity.recovery_session.command.create.v1` | `POST /_arkret/root/identity/recovery-sessions` | - | - | request_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_create_request_body; response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_state |
| `ak.root.identity.recovery_session.command.submit_proof.v1` | `POST /_arkret/root/identity/recovery-sessions/{recovery_session_id}/proofs` | - | - | request_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_proof_submit_request_body; response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_proof_submit_outcome |
| `ak.root.identity.recovery_session.resource.get.v1` | `GET /_arkret/root/identity/recovery-sessions/{recovery_session_id}` | - | - | response_schema_ref=schemas/recovery-session.schema.json#/$defs/recovery_session_state |
| `ak.root.identity.registry.read.describe.v1` | `GET /_arkret/root/identity/describe` | - | - | response_schema_ref=schemas/service-describe.schema.json |
| `ak.root.identity.service_registration.command.ensure.v1` | `POST /_arkret/root/identity/service-registrations:ensure` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationEnsureRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationOutcome |
| `ak.root.identity.service_registration.resource.get.v1` | `GET /_arkret/root/identity/service-registrations` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ServiceRegistrationOutcome |
| `ak.self.account.command.revoke_cursor.v1` | `POST /_arkret/self/account/cursor/revoke` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AccountCursorRevokeOutcome |
| `ak.self.account.command.update_profile.v1` | `POST /_arkret/self/account/profile` | - | - | request_schema_ref=schemas/account-operations.schema.json#/$defs/account_update_profile_request_body; response_schema_ref=schemas/account-operations.schema.json#/$defs/account_update_profile_outcome |
| `ak.self.account.read.describe.v1` | `GET /_arkret/self/account/describe` | - | - | response_schema_ref=schemas/service-describe.schema.json |
| `ak.self.account.read.viewer.v1` | `GET /_arkret/self/account/viewer` | - | - | response_schema_ref=schemas/account-operations.schema.json#/$defs/account_view |
| `ak.self.account.stream.subscribe.v1` | `GET /_arkret/self/account/subscribe` | - | - | response_schema_ref=schemas/account-subscribe-frame.schema.json |
| `ak.self.account_data.read.list.v1` | `GET /_arkret/self/account_data` | - | - | response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_list |
| `ak.self.account_data.resource.delete.v1` | `DELETE /_arkret/self/account_data/{account_data_key}` | - | - | request_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_delete_request_body; response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_delete_outcome |
| `ak.self.account_data.resource.get.v1` | `GET /_arkret/self/account_data/{account_data_key}` | - | - | response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_entry |
| `ak.self.account_data.resource.replace.v1` | `PUT /_arkret/self/account_data/{account_data_key}` | - | - | request_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_replace_request_body; response_schema_ref=schemas/account-data-operations.schema.json#/$defs/account_data_entry |
| `ak.self.actor_profile.read.resolve.v1` | `POST /_arkret/self/actor-profiles/query` | - | - | request_schema_ref=schemas/actor-profile-operations.schema.json#/$defs/resolve_request; response_schema_ref=schemas/actor-profile-operations.schema.json#/$defs/resolve_outcome |
| `ak.self.agent.command.deactivate.v1` | `POST /_arkret/self/agents/{agent_id}/deactivate` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_deactivate_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state |
| `ak.self.agent.command.pause.v1` | `POST /_arkret/self/agents/{agent_id}/pause` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_pause_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state |
| `ak.self.agent.command.provision.v1` | `POST /_arkret/self/agents` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_provision_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_provision_outcome |
| `ak.self.agent.command.renew_pairing.v1` | `POST /_arkret/self/agents/{agent_id}/renew-pairing` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_renew_pairing_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_renew_pairing_outcome |
| `ak.self.agent.command.resume.v1` | `POST /_arkret/self/agents/{agent_id}/resume` | - | - | request_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_resume_request_body; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_lifecycle_state |
| `ak.self.agent.participation.resource.get.v1` | `GET /_arkret/self/agents/{agent_id}/participation` | - | - | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_participation_outcome |
| `ak.self.agent.participation.resource.replace.v1` | `PUT /_arkret/self/agents/{agent_id}/participation` | - | - | request_schema_ref=schemas/principal-operations.schema.json#/$defs/participation_replace_request; response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_participation_outcome |
| `ak.self.agent.read.list.v1` | `GET /_arkret/self/agents` | - | - | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_list |
| `ak.self.agent.resource.get.v1` | `GET /_arkret/self/agents/{agent_id}` | - | - | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_view |
| `ak.self.agent.sidecar.command.ensure.v1` | `POST /_arkret/self/agent-sidecars:ensure` | - | - | request_schema_ref=schemas/principal-operations.schema.json#/$defs/sidecar_ensure_request; response_schema_ref=schemas/principal-operations.schema.json#/$defs/sidecar_ensure_outcome |
| `ak.self.agent.sidecar.read.list.v1` | `GET /_arkret/self/agent-sidecars` | - | - | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_sidecar_list |
| `ak.self.agent.sidecar.resource.get.v1` | `GET /_arkret/self/agent-sidecars/{sidecar_id}` | - | - | response_schema_ref=schemas/agent-operations.schema.json#/$defs/agent_sidecar_view |
| `ak.self.applet.command.install.v1` | `POST /_arkret/self/applets/install` | - | - | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_request_body; response_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_outcome |
| `ak.self.applet.command.revoke.v1` | `POST /_arkret/self/applets/{applet_id}/revoke` | - | - | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_request_body; response_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_outcome |
| `ak.self.applet.ghost.command.preview.v1` | `POST /_arkret/self/applets/{applet_id}/ghosts/provision/preview` | - | - | request_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_preview_request_body; response_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_preview_outcome |
| `ak.self.applet.ghost.command.provision.v1` | `POST /_arkret/self/applets/{applet_id}/ghosts/provision` | - | - | request_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_actor_provision_request_body; response_schema_ref=schemas/applet-ghost-operations.schema.json#/$defs/ghost_actor_provision_outcome |
| `ak.self.applet.install.command.preview.v1` | `POST /_arkret/self/applets/install/preview` | - | - | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_install_preview_request_body; response_schema_ref=schemas/applet-install-authoring.schema.json#/$defs/install_preview_outcome |
| `ak.self.applet.revoke.command.preview.v1` | `POST /_arkret/self/applets/{applet_id}/revoke/preview` | - | - | request_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_preview_request_body; response_schema_ref=schemas/applet-install-operations.schema.json#/$defs/applet_revoke_preview_outcome |
| `ak.self.authz.grants.read.effective.v1` | `GET /_arkret/self/authz/effective-grants` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/GrantList |
| `ak.self.authz.invites.read.list.v1` | `GET /_arkret/self/authz/invites` | - | - | response_schema_ref=schemas/authz-operations.schema.json#/$defs/authz_invite_list |
| `ak.self.authz.read.check.v1` | `POST /_arkret/self/authz/check` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/AuthzCheckOutcome |
| `ak.self.blob.command.presign.v1` | `POST /_arkret/self/blob/presign` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/BlobPresignRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/BlobPresignOutcome |
| `ak.self.blob.resource.get.v1` | `GET /_arkret/self/blob/get` | - | - | registry-declared non-JSON or shared binding |
| `ak.self.blob.resource.head.v1` | `HEAD /_arkret/self/blob/get` | - | - | registry-declared non-JSON or shared binding |
| `ak.self.blob.upload.create.v1` | `POST /_arkret/self/blob/upload` | - | - | request_schema_ref=schemas/blob-operations.schema.json#/$defs/blob_upload_request_body; response_schema_ref=schemas/blob-operations.schema.json#/$defs/blob_upload_outcome |
| `ak.self.call.media.exchange.issue_token.v1` | `POST /_arkret/self/rtc/token` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/CallMediaTokenExchangeOutcome |
| `ak.self.circle.command.create.v1` | `POST /_arkret/self/circles` | - | - | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_create_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view |
| `ak.self.circle.command.rotate_scope.v1` | `POST /_arkret/self/circles/{circle_id}/scope-rotate` | - | - | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_scope_rotate_outcome |
| `ak.self.circle.member.command.add.v1` | `POST /_arkret/self/circles/{circle_id}/members` | - | - | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_member_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_membership_outcome |
| `ak.self.circle.member.resource.delete.v1` | `DELETE /_arkret/self/circles/{circle_id}/members/{actor_id}` | - | - | request_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_member_delete_request_body; response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_membership_outcome |
| `ak.self.circle.read.list.v1` | `GET /_arkret/self/circles` | - | - | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_list |
| `ak.self.circle.resource.get.v1` | `GET /_arkret/self/circles/{circle_id}` | - | - | response_schema_ref=schemas/circle-operations.schema.json#/$defs/circle_view |
| `ak.self.consent.command.grant.v1` | `POST /_arkret/self/consent/results/grant` | - | - | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_grant_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_view |
| `ak.self.consent.command.request.v1` | `POST /_arkret/self/consent/request` | - | - | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_request_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_request_outcome |
| `ak.self.consent.command.revoke.v1` | `POST /_arkret/self/consent/results/revoke` | - | - | request_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_revoke_request_body; response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_view |
| `ak.self.consent.read.list.v1` | `GET /_arkret/self/consent/results` | - | - | response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_list |
| `ak.self.consent.resource.get.v1` | `GET /_arkret/self/consent/result` | - | - | response_schema_ref=schemas/consent-operations.schema.json#/$defs/consent_view |
| `ak.self.contact.command.checkpoint.v1` | `POST /_arkret/self/contacts/continuity-checkpoint` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_continuity_checkpoint_request_body; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_continuity_checkpoint_outcome |
| `ak.self.contact.command.reject.v1` | `POST /_arkret/self/contacts/reject` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_reject_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_reject_outcome |
| `ak.self.contact.command.request.v1` | `POST /_arkret/self/contacts/request` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_operation_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_request_outcome |
| `ak.self.contact.command.respond.v1` | `POST /_arkret/self/contacts/respond` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_respond_outcome |
| `ak.self.contact.command.scope_update.v1` | `POST /_arkret/self/contacts/scope-update` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_scope_update_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_scope_update_outcome |
| `ak.self.contact.command.tombstone.v1` | `POST /_arkret/self/contacts/tombstone` | - | - | request_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone_request; response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_tombstone_outcome |
| `ak.self.contact.read.list.v1` | `GET /_arkret/self/contacts` | - | - | response_schema_ref=schemas/contact-operations.schema.json#/$defs/contact_list |
| `ak.self.current_principal.read.resolve.v1` | `POST /_arkret/self/account/current-principal` | - | - | request_schema_ref=schemas/identity-resolution.schema.json#/$defs/current_principal_request_body; response_schema_ref=schemas/identity-resolution.schema.json#/$defs/current_principal_outcome |
| `ak.self.device_messages.command.ack.v1` | `POST /_arkret/self/device_messages/ack` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesAckRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesAckOutcome |
| `ak.self.device_messages.command.send.v1` | `POST /_arkret/self/device_messages` | - | - | request_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesSendRequestBody; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesSendOutcome |
| `ak.self.device_messages.read.list.v1` | `GET /_arkret/self/device_messages` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/DeviceMessagesGetOutcome |
| `ak.self.direct_conversation.read.resolve.v1` | `POST /_arkret/self/direct-conversations/resolve` | - | - | request_schema_ref=schemas/direct-conversation-operations.schema.json#/$defs/direct_conversation_resolve_request; response_schema_ref=schemas/direct-conversation-operations.schema.json#/$defs/direct_conversation_resolve_outcome |
| `ak.self.events.command.submit.v1` | `POST /_arkret/self/events` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_request; response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/submit_outcome |
| `ak.self.events.read.scan.v1` | `POST /_arkret/self/streams/scan` | - | - | request_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_request; response_schema_ref=schemas/authority-commit-operations.schema.json#/$defs/stream_scan_outcome |
| `ak.self.events.resource.get.v1` | `GET /_arkret/self/events/{event_id}` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/EventView |
| `ak.self.events.stream.subscribe.v1` | `GET /_arkret/self/events/subscribe` | - | - | response_schema_ref=schemas/events-subscribe-frame.schema.json |
| `ak.self.identity.read.resolution_audit.v1` | `POST /_arkret/self/identity/resolution-audit/query` | - | - | request_schema_ref=schemas/identity-resolution.schema.json#/$defs/principal_resolution_audit_request; response_schema_ref=schemas/identity-resolution.schema.json#/$defs/principal_resolution_audit_evidence |
| `ak.self.invite_locator.command.issue.v1` | `POST /_arkret/self/invite-locators` | - | - | request_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_issue_request_body; response_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_issue_outcome |
| `ak.self.invite_locator.command.revoke.v1` | `POST /_arkret/self/invite-locators/revoke` | - | - | request_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_revoke_request_body; response_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_revoke_outcome |
| `ak.self.invite_locator.command.rotate.v1` | `POST /_arkret/self/invite-locators/rotate` | - | - | request_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_rotate_request_body; response_schema_ref=schemas/principal-locator.schema.json#/$defs/invite_locator_issue_outcome |
| `ak.self.invite_receive_policy.resource.get.v1` | `GET /_arkret/self/invite-receive-policy` | - | - | response_schema_ref=schemas/invite-receive-policy.schema.json |
| `ak.self.invite_receive_policy.resource.replace.v1` | `PUT /_arkret/self/invite-receive-policy` | - | - | request_schema_ref=schemas/invite-receive-policy.schema.json; response_schema_ref=schemas/invite-receive-policy.schema.json |
| `ak.self.invites.command.dispatch.v1` | `POST /_arkret/self/invites/dispatch` | - | - | request_schema_ref=schemas/invite-delivery-request.schema.json#/$defs/self_invite_dispatch_request_body; response_schema_ref=schemas/invite-delivery-request.schema.json#/$defs/invite_delivery_outcome |
| `ak.self.keys.backup_series.command.erase.v1` | `POST /_arkret/self/keys/backup-series/erase` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/backup_series_erase_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/backup_series_erase_outcome |
| `ak.self.keys.backups.command.issue_delete_challenge.v1` | `POST /_arkret/self/keys/backups/{backup_id}/delete-challenge` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_issue_delete_challenge_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_delete_challenge |
| `ak.self.keys.backups.command.issue_unlock_challenge.v1` | `POST /_arkret/self/keys/backups/{backup_id}/unlock-challenge` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_issue_unlock_challenge_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_unlock_challenge |
| `ak.self.keys.backups.command.unlock.v1` | `POST /_arkret/self/keys/backups/{backup_id}/unlock` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_unlock_request_body; response_schema_ref=schemas/key-backup.schema.json |
| `ak.self.keys.backups.read.list.v1` | `GET /_arkret/self/keys/backups` | - | - | response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_list |
| `ak.self.keys.backups.resource.delete.v1` | `DELETE /_arkret/self/keys/backups/{backup_id}` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_delete_request_body |
| `ak.self.keys.backups.resource.replace.v1` | `PUT /_arkret/self/keys/backups/{backup_id}` | - | - | request_schema_ref=schemas/key-backup.schema.json; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_backups_replace_outcome |
| `ak.self.keys.command.claim.v1` | `POST /_arkret/self/keys/claim` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_claim_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_claim_outcome |
| `ak.self.keys.keypackages.command.claim.v1` | `POST /_arkret/self/keys/keypackages/claim` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_claim_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_claim_outcome |
| `ak.self.keys.keypackages.command.consume.v1` | `POST /_arkret/self/keys/keypackages/consume` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_consume_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_consume_outcome |
| `ak.self.keys.keypackages.command.revoke.v1` | `POST /_arkret/self/keys/keypackages/revoke` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_revoke_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_revoke_outcome |
| `ak.self.keys.keypackages.upload.create.v1` | `POST /_arkret/self/keys/keypackages/upload` | - | - | request_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_upload_request_body; response_schema_ref=schemas/keypackage-operations.schema.json#/$defs/keypackages_upload_outcome |
| `ak.self.keys.read.lookup.v1` | `POST /_arkret/self/keys/query` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_query_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_query_outcome |
| `ak.self.keys.upload.create.v1` | `POST /_arkret/self/keys/upload` | - | - | request_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_upload_request_body; response_schema_ref=schemas/keys-operations.schema.json#/$defs/keys_upload_outcome |
| `ak.self.media.read.ice_config.v1` | `POST /_arkret/self/rtc/ice-config` | - | - | request_schema_ref=schemas/media-operations.schema.json#/$defs/media_ice_config_request_body; response_schema_ref=schemas/ice-config-response.schema.json |
| `ak.self.media_service_binding.read.resolve.v1` | `POST /_arkret/self/media-service-bindings/query` | - | - | request_schema_ref=schemas/media-service-binding-result.schema.json#/$defs/media_service_binding_request_body; response_schema_ref=schemas/media-service-binding-result.schema.json#/$defs/media_service_binding_outcome |
| `ak.self.messages.command.prepare.v1` | `POST /_arkret/self/messages/prepare` | - | - | request_schema_ref=schemas/message-authoring.schema.json#/$defs/message_prepare_request_body; response_schema_ref=schemas/message-authoring.schema.json#/$defs/message_prepare_outcome |
| `ak.self.moderation.command.report.v1` | `POST /_arkret/self/moderation/report` | - | - | request_schema_ref=schemas/moderation-report.schema.json#/$defs/moderation_report_request_body; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ModerationReportOutcome |
| `ak.self.morph.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/morphs` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionMorphList |
| `ak.self.morph.resource.get.v1` | `GET /_arkret/self/realms/{realm_id}/morphs/{morph_id}` | - | - | response_schema_ref=schemas/view.schema.json#/$defs/document_morph_projection_outcome |
| `ak.self.read_cursor.command.advance.v1` | `POST /_arkret/self/read-cursors` | - | - | request_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_cursor_advance_request_body; response_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_marker_outcome |
| `ak.self.read_cursor.read.list.v1` | `GET /_arkret/self/read-cursors` | - | - | response_schema_ref=schemas/read-cursor-operations.schema.json#/$defs/read_cursor_list |
| `ak.self.realm.read.export.v1` | `GET /_arkret/self/realms/{realm_id}/export` | - | - | response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_export |
| `ak.self.realm.resource.get.v1` | `GET /_arkret/self/realms/{realm_id}` | - | - | response_schema_ref=schemas/realm-read-operations.schema.json#/$defs/realm_lifecycle_view |
| `ak.self.realm_join.command.prepare.v1` | `POST /_arkret/self/realm-joins/prepare` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_prepare_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_prepare_outcome |
| `ak.self.realm_join.read.application_status.v1` | `POST /_arkret/self/realm-joins/application-status` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_application_status_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_application_status_outcome |
| `ak.self.realm_join.read.preview.v1` | `POST /_arkret/self/realm-joins/preview` | - | - | request_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_preview_request_body; response_schema_ref=schemas/realm-join-intake.schema.json#/$defs/self_preview_outcome |
| `ak.self.realm_link.read.effective_policy.v1` | `GET /_arkret/self/realms/{realm_id}/effective-policy` | - | - | response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_effective_policy_outcome |
| `ak.self.realm_link.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/links` | - | - | response_schema_ref=schemas/realm-link-operations.schema.json#/$defs/realm_link_list |
| `ak.self.realm_organization.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/organizations` | - | - | response_schema_ref=schemas/realm-organization-operations.schema.json#/$defs/realm_organization_relationship_list |
| `ak.self.realm_state_snapshot.read.manifest_head.v1` | `GET /_arkret/self/realm-state-snapshot/head` | - | - | response_schema_ref=schemas/realm-state-snapshot.schema.json |
| `ak.self.relation_conflicts.read.candidates.v1` | `QUERY /_arkret/self/relation-conflicts/candidates` | - | - | request_schema_ref=schemas/relation.schema.json#/$defs/relation_conflict_candidates_request_body; response_schema_ref=schemas/relation.schema.json#/$defs/relation_conflict_candidates_outcome |
| `ak.self.security_transaction.command.continue.v1` | `POST /_arkret/self/security-transactions/{transaction_id}/continue` | - | - | request_schema_ref=schemas/security-transaction.schema.json#/$defs/continue_request; response_schema_ref=schemas/security-transaction.schema.json |
| `ak.self.security_transaction.command.create.v1` | `POST /_arkret/self/security-transactions` | - | - | request_schema_ref=schemas/security-transaction.schema.json#/$defs/create_request; response_schema_ref=schemas/security-transaction.schema.json |
| `ak.self.security_transaction.resource.get.v1` | `GET /_arkret/self/security-transactions/{transaction_id}` | - | - | response_schema_ref=schemas/security-transaction.schema.json |
| `ak.self.signal.command.send.v1` | `POST /_arkret/self/signal` | - | - | request_schema_ref=schemas/signal-envelope.schema.json; response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/SignalSubmitOutcome |
| `ak.self.signal.stream.subscribe.v1` | `GET /_arkret/self/signal/subscribe` | - | - | response_schema_ref=schemas/signal-stream-frame.schema.json |
| `ak.self.signer_keys.read.resolve.v1` | `POST /_arkret/self/signer-keys/query` | - | - | request_schema_ref=schemas/signer-key-operations.schema.json#/$defs/query_request_body; response_schema_ref=schemas/signer-key-operations.schema.json#/$defs/query_outcome |
| `ak.self.space.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/spaces` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionSpaceList |
| `ak.self.strand.read.list.v1` | `GET /_arkret/self/realms/{realm_id}/strands` | - | - | response_schema_ref=schemas/service-operation-dtos.schema.json#/$defs/ProjectionStrandList |
| `ak.self.third_party_invite.read.acceptance_attestation.v1` | `POST /_arkret/self/third-party-invites/acceptance-attestation` | - | - | request_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_acceptance_attestation_request_body; response_schema_ref=schemas/invite.schema.json#/$defs/third_party_invite_acceptance_attestation_outcome |
| `ak.server.read.describe.v1` | `GET /_arkret/describe` | - | - | response_schema_ref=schemas/service-describe.schema.json |
<!-- END GENERATED OPERATION FIELD TABLE -->

### 普通消息的完整 authoring 准备

普通消息必须在客户端形成 immutable producer-signed Event，再使用统一 Event submit 进入 current authority；准备接口不保留位置也不产生 accepted 结果。

**本地明文意图与加密 wire 请求是两件事（normative）**：`ak.self.messages.command.prepare.v1` 的
`intent.content` 是一个封闭 `oneOf`——`kind="plaintext"` 承载**本地**明文意图，`kind="mls"` 承载已经加密好的
wire 请求（`encrypted_content` 与 `encryption_context`）。两者 MUST NOT 混用或互相回退。在已由 accepted
`ak.mls.genesis` 激活的 effective scope 中，`kind="plaintext"` 的 prepare 请求 MUST 被拒绝
（[`../crypto-media/encryption-and-audit.md` §2.3](../crypto-media/encryption-and-audit.md)）；准备接口
MUST NOT 代替客户端加密，Station 在该 scope 中 MUST NOT 取得明文。

**加密与校验都在客户端（normative）**：客户端 MUST 先按 §2.3 冻结该条消息的 AAD 输入并在本地完成加密，
再发出 prepare 请求。收到 `draft` 后，客户端 MUST 把 draft 中的 ciphertext、加密 metadata 与全部绑定
（effective scope、Event kind、`encryption_context`、引用的 public group revision）与自己冻结、送出的那份
**逐字节**比对，任一不符 MUST 丢弃该 draft 并 fail closed，MUST NOT 就地改写 draft 后签名。

**精确重试不消耗第二个 sender counter（normative）**：prepare 结果不明确时，客户端 MUST 重放 byte-identical
的同一请求。该重试 MUST NOT 重新加密，因此 MUST NOT 推进 RFC 9420 sender ratchet 的 generation，也 MUST NOT
产生第二份 ciphertext。为同一条消息生成第二份 ciphertext 会使已冻结的 AAD 与已送出的那份不再唯一对应。

**两请求路径假定发送就绪与本地 MLS state（normative）**：prepare + submit 这条两请求路径**假定**调用方已经
send-ready 且已持有目标 epoch 的本地 MLS state。prepare MUST NOT 授予权限、MUST NOT 预留 sequence、
MUST NOT 推进任何 stream 的 `RealmCommit.stream_position`，也 MUST NOT 建立、修复或代替本地 MLS state；
缺少这些前提时失败发生在客户端加密阶段，而不是由准备接口补齐。

### 2.5 HTTP Message Signature

所有 peer 写入和高风险读取使用绑定 operation 与 canonical body digest 的服务签名。

#### 2.5.1 Peer signature

接收方先验证 transport signature、DID freshness 和 trust relationship，再验证内层 Event/Commit/handoff proof。

#### 2.5.2 Replay window

重放 cache 与有界 signature window 必须同时执行；cache eviction 不得使过期签名重新有效。

### 3.3 站间操作

站间操作只包含 registry 已登记的 Event 转发、逐 stream 复制、authority bundle 与计划 handoff。

### 5.1 MLS 运输

MLS private bytes 保持端到端加密；Station 只处理公开 transition 和 recipient-addressed Welcome ciphertext。
`ak.peer.events.read.resolve_committed.v1` 是 Directory ingest 的专用 exact-resolve，不是通用 peer
读取入口。其 body 必须包含 `realm_id`、`source_ref_access` 和 `refs[]`。服务在读任何 Event 前
MUST 验证 authenticated caller 等于 carrier `directory_id`，carrier 的 source/Realm/proof/expiry 与
当前 announce 有效，并确认每个 `{event_id, commit_id, stream_ref, stream_position}` 都逐字属于
carrier `source_refs`。它只返回 exact match；任何缺失或越界必须 fail closed，且不得退化为 scan。
