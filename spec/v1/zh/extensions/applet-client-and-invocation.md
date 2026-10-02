---
title: Applet 单主体、主动领取与按调用披露
status: candidate
normative: true
stability: v1
updated: 2026-10-03
---

## 0. 范围与唯一载体

本合同属于可选 `ak.profile.applet_service.v1`，替代 Applet 独立 Bot principal、必须有入站
URL 和“原群 MLS 成员即可严格仅 @ 可读”的假设。关键字按
[规范语言](../conformance/normative-language.md) 解释。
个人 Agent、外部人类 Ghost、Widget、普通 Account/Device 和单权威 RealmCommit 合同不改变。
不存在 Applet SessionGrant、Agent pairing、私有 bearer、第三种 MLS recipient endpoint 或私有加密算法。

身份与 epoch 使用 `applet-package.schema.json`、`applet-managed-actor.schema.json` 和
`applet-registration-epoch-transcript.schema.json`；主动连接使用
[`applet-client-operations.schema.json`](../../artifacts/schemas/applet-client-operations.schema.json)；
调用明文 Content Block 使用
[`content-block-applet.schema.json`](../../artifacts/schemas/content-block-applet.schema.json)。
正文不得被解释为绕过这些 closed schema 的第二种 wire。

## 1. 一个 Applet 身份，两种用途

### 1.1 创建与归因

Applet MUST 使用一个通过完整方法历史验证的 `did:webvh`。
`service_id` 是其 adapter projection；`applet_actor_id` MUST 为完整 account ActorId，
其中 `account_id.principal_id == service_id`，`station_id` 为该 Account 的 hosting Station。
`applet_id` 标识应用/安装，不替代这两个身份坐标。controller MUST 为另一个已验证的人或组织。
此绑定只属于本合同，不产生任意 `ActorId.service == ActorId.account` 等价关系。
同 principal 在两个 Station 的 Account/PCR、grant、设备与安装 MUST 保持独立。

`bot_actor_id`、`initial_package_bot_actor_id`、`bot_actor_provision_ref`、
`bot_principal_control_realm_id` 和 `purpose=install_bot` 都不是合法 wire。
其新的中性坐标分别为 `applet_actor_id`、`initial_package_applet_actor_id`、
`applet_actor_provision_ref`、`applet_principal_control_realm_id` 和 `purpose=install_applet`。
managed provision 的 `actor_role` 只允许 `applet|ghost`：`applet` 绑定上述同 core 的 Account，
`ghost` 仍必须有独立 SCID、external tuple 和 namespace/provision 证据。
不得只重命名字段后继续生成第二个自动化 DID。

首次安装仍接受 registration/grants 与四条由 Applet Service 实际自签的 creation Events。
provision、PCR genesis、accountability 和 Profile 的固定集合、不可变 anchors、同事务及 exact
retry 保留。Applet 初始 Profile 的 `actor_kind` MUST 为 `service`；它是展示分类，不授予权限。
外部 Bot 镜像仍可用 Ghost 的 `actor_kind=bot`，外部 MIMI 的 bot 词汇不因此改变。
同一主体的 Service 传输/creation proof、Principal 的 PCR/native control proof 和 delegated Device
的普通 Event/MLS proof MUST 分别验证，不因 core 相等省略任意 root。
代表真人执行时仍保留真人 `actor_id`、实际 Applet `executed_by` 与确切授权；不交付真人私钥。

### 1.2 原生轮换与 exact Account 对齐

WebVH 原生 history 是唯一身份控制来源；registration epoch 是 Service 的安全版本载体，
每个 exact Account 的 PCR resolution typed current 是该 Account 的控制版本载体。
两者 MUST 逐字绑定相同的 native version、DID document digest 及被批准 key material，才可开始
新的 live 业务写入、内容领取或 disclosure。相同 DID 不允许不同 current basis 混签。
这里的 key material 指同一已批准 DID document 中按 verification relationship 和用途解析的
密钥集合；不要求 native updateKey、Service assertion key 与 delegated Device key 为同一把密钥。
历史 Event 使用原已冻结 Service/Principal/Device evidence，不以 current 网上 head 重写。

完整轮换顺序是：

1. runtime 先耐久保存 successor 私钥、完整 native history 与 witness；再发布已预承诺的 native
   successor。不得从 Station 响应重造私钥或生成平行身份。
2. 经 [applet-integration §7.3.2.1](./applet-integration.md) 的唯一 native PCR update branch，
   向每个 installing Station 分别提交原 current old updateKey 自签的 exact resolution successor。
   标准 previous-resolution CAS、同 Account/PCR、native chain/witness 与原安装 fence 全部保留。
   该维护请求的 RFC 9421 来源可使用原已接受 epoch 的 key；它只更新自己的 PCR，不授权业务内容。
3. Station 在同一 UoW 接纳 PCR successor、保存新 Principal root/attester/closure/outbox。
   若原 Service epoch 尚未与新 PCR 对齐，该 Account 进入业务暂停状态。
   只允许原件恢复、轮换维护、安装续订/撤销及不含业务内容的 own completion。
4. 管理员按既有 preview/install 的 Reuse 分支批准新 package/registration epoch 与新 grants。
   commit MUST 在首个副作用前核该 Station 的已 accepted PCR version 与新 epoch 一致；
   再同事务替换 exact install 的 registration/grants，冻结新 Service root 及同版本 Principal root，
   交付该续订的 own completion。旧 grants 不自动改绑到新 epoch。

Service-first：新 epoch 只能停在 pending preview，PCR 未更新时 install commit 返回
`failed_precondition` 且零 accepted registration/grant/root/outbox；不得先暴露新 Service authority。
PCR-first：允许第 2、3 步成立，但第 4 步完成前不得使用新 Principal 与旧 epoch 做业务。
多个 scope 安装也分别完成续订；一侧完成不能开启另一侧。
同 DID 两 Station 只完成一侧时，另一侧不得接纳新 method/key。其原已接受且未关闭的 aligned
basis 不因别站更新自动改写；一旦本 Station 验证到已知关闭/deactivation 或不一致 successor，
新的 live 业务失败关闭，仍可按上述维护路径恢复。不要求跨 Station 原子提交，也不要求每消息
在线重新解析 DID。新的 epoch 不会恢复已 committed revoke 或重新打开旧安装实例。
迟到 completion 只能保留历史原件，不能倒退 current、覆盖新私钥或恢复 live 资格。

## 2. HTTPS 推送与主动领取

### 2.1 封闭选择与来源认证

Package、registration 和 epoch transcript 的 `transport.kind` MUST 是以下之一：

- `https_push`：`base_url` 必填且为 HTTPS，`endpoint_policy.endpoints` 非空；保留现有
  DID endpoint 绑定、SSRF/地址准入与所有 edge operation 来源认证。
- `client_pull`：禁止 `base_url`，`endpoint_policy.endpoints` 必须为空，`receive_signals=false`。
  runtime 主动连接目标 Station 的标准 HTTPS JSON exchange；本版本不通过耐久队列模拟瞬态 Signal。

DID 的 WebVH 发布/历史地址不属于 runtime 的入站 API。无入站 URL 不免除该发布职责。
`webhook_auth` 在两支均保留，用于绑定 Applet 主动提交的 Service key/algorithm 与 epoch。
transport 改变是安全 transcript 改变，必须新 epoch、管理员批准和 exact install 续订。

唯一新客户端操作是 `ak.edge.applet.client.command.exchange.v1`，
`POST /_arkret/edge/applet/client/exchange`，承载于目标 **Station**。
它的逐次 RFC 9421 签名 MUST 解析
`ak.http_signature.scenario.applet_client.v1`；covered components、参数和 freshness
只取 canonical signature registry，不在本页复制数字或清单。

<!-- BEGIN ak-http-signature-covered-set ak.http_signature.scenario.applet_client.v1 -->
必须覆盖 `@method`、`@authority`、`@target-uri`、`arkret-operation`、`source-service-id`、`destination-service-id`、`content-digest`、`idempotency-key`、`source-trust-domain`、`destination-trust-domain`；trust-domain 两项仅在跨 trust-domain 时适用。
<!-- END ak-http-signature-covered-set -->

Source/Destination 分别等于 Applet Service 和 exact Station；verification method/public key
由对应阶段的已验证 epoch 解析，不接受 caller 自报 key。没有 session 或 bearer fallback。

每个 claim 在收到确定响应后使用新的 `Idempotency-Key` 取得最新状态；丢响应只重试原 key/body。
缓存身份绑定 operation、完整 Source/Destination、key、canonical body 与 security basis。
同 key 异 body/binding 返回 `duplicate_conflict`。更新 RFC 签名时间但同 key material/body 的
合法重投不会重新执行；每次仍验 freshness、当前 fence 和披露资格，然后才能返回缓存内容。

### 2.2 首次安装阶段：消除 active-install 循环

管理员先经既有 preview 保存自己签署的 registration/grants，取得目标 Station 自签的 exact
`authoring_request`。管理员将 **目标 Station、Applet id、epoch、完整 signed request 的 digest**
交给 runtime；digest 是精确选择器，不是 bearer secret，也不授予读取。

`bootstrap_claim` MUST 只命中这份请求。Station 核 original administrator、signed basis、
package controller proof、method/epoch evidence、exact service/audience/target/scope、pending generation
与 expiry，并以该 epoch key 的 RFC 9421 持钥证明确认领取者。此阶段不要求 active install；
但 MUST NOT 提前接受 staged registration/grants 或允许 Realm/Strand scan、Ghost 查询、Blob、
Signal、业务 Event、业务 task。错误 service/Station/key/epoch/digest 返回 `permission_denied`；
未知与未授权请求不得用于枚举别人的 pending 记录。

runtime 按原 authoring 算法自签并耐久保存 exact 四 Event bundle，以 `bootstrap_submit` 回传。
Station 验完整 request/bundle/proofs/交叉绑定后只保存 authored ledger，不产生安装事实。
同 request/digest 的同 bundle 返回原结果；异 bundle 为 `duplicate_conflict`，零替换。
管理员再次以相同 preview basis 读取原 request 与可选 `managed_actor_bundle`，随后显式调用
原 install commit。runtime 不能用 submit 自行批准安装。

pending 请求的 closed 状态是 pending、authored、committed、expired、cancelled、superseded。
preview 对同 subject 异 payload 的 supersede、原 expiry、commit、submit 和取消 MUST 共用一个
耐久 subject/request CAS。取消唯一操作为
`ak.self.applet.install.command.cancel.v1`，`POST /_arkret/self/applets/install/cancel`：
仅原 authenticated installing administrator 且仍有相应管理资格可取消 exact request。
取消、expiry 或 supersede 后零新 bundle/commit；已 committed 不能 cancel，必须原 revoke。
取消重试保持同 terminal 结果。expiry 后不能新 commit；既有 committed exact retry 不受 preview
expiry 影响。`bootstrap_claim` 可向同一已验证接收者返回 own `bootstrap_committed` completion，
即使没有业务读取 grant；known revoke 时只提供同一历史结果，绝不使其 live。

bootstrap 只披露该请求的管理员已批准安装材料、该 bundle 和该 exact installation 的结果；
completion 持久化/验签/CAS 安装仍服从 §7.3.2。重启从同 ledger 取原件，零重复创建。
同一个 Applet 在别的 scope 已安装，也不把这份 bootstrap 请求变成 installed content authorization。

### 2.3 已安装阶段：队列、结果与撤销

`installed_claim` / `installed_ack` 只选择 complete `registration_ref`、epoch、Applet 与 exact
effective scope。Station MUST 在同事务 snapshot 核 current active install、aligned roots、每项
action/resource grant、membership、内容可见范围与 revoke fence。
唯一轮换恢复例外是 §1.2 已验证自身 PCR successor 的 own `authoring_context` completion：
可在旧 accepted epoch 与新 PCR 尚未对齐时领取原件，但必须核同 Applet Account/PCR、原维护请求、
本 Station 的真实 accepted Commit 及 ledger；队列项不得混入业务 Event、Signal、query 或其它主体。
该例外不授予历史内容读取，也不重新打开 revoked install；仅已有 exact completion 可作为历史恢复。
strict invocation 的披露只来自 §3 的独立 invocation Circle；源群 read/scan/history/blob 权限不会
因其安装、@、receive_events 或 namespace 增加。

队列 item 是 Station 自签的 closed `{applet_id,registration_epoch,registration_ref,
effective_scope,issued_at,expires_at?,task,proof}`；签名覆盖不含 proof 的完整对象，audience
等于 Applet service。runtime 必须验预期 Station 的 Service history/key、proof、当前绑定与
task 原 producer proofs。`item_digest=SHA256(JCS(完整 signed item))` 是准确 ack 身份，不是 EventId
或权限。推送和领取共用同一 original task/body 与一次执行 ledger；改变输送方式不重建身份或 Event。

task 的 operation enum/参数/body/outcome 按 client schema 分支闭合，覆盖既有 describe、ping、
managed author、transaction、Actor/Realm resolve、protocol metadata 与 third-party lookup；不得
用 opaque JSON 增加其它操作。所有业务 query 仍须 current install/grant/scope，结果不证明 Ghost 归属。
管理 authoring/completion 只披露原 exact subject 的安装/PCR 最小材料。

每条 lane 的未确认首项重复领取原 signed bytes；同 Realm stream 的 committed Event 按实际
Commit position 排序，PCR completion 按本 PCR successor 顺序，不能比较不同 stream position。
其它 query lane 采用本地 durable FIFO，不创造协议全局 frontier。跨 lane 无全局顺序；消费者缺
predecessor 时保持 pending。query 必须有 expires_at，过期后不执行；accepted completion 无
年龄租约，不能因 request preview 到期重建它。

runtime 在副作用前保存 exact task，执行结果与 ack outcome 耐久提交后才能 ack。
Station 对同 item 同 outcome 精确重放确认；异 outcome 返回 `duplicate_conflict`；未知 item 不推进。
ack 不等于 Event accepted：transaction 的 committed refs 与 completion 仍按自身合同验证。
领取后崩溃从同 ledger 重放，不新签 Event；外部系统不支持幂等时只能报告不明结果，不能宣称 exactly-once。
队列饱和沿 `queue_full` / `retry_after_ms`，claim 不消费未 ack 项；无新项返回空 items，可退避重领。
撤销/关闭/epoch replacement 与 claim 读取共用同一安装 fence：**返回字节前**重新检查，缓存和旧连接
都不得继续披露。未确认旧业务项停止交付/执行；已获准交付的明文不能远程收回。

## 3. 严格按调用的最小披露

### 3.1 调用的授权与独立 Circle

结构化 @ 只表达意图，不是 consent 或 capability。严格调用 MUST 由有权读取**且有权披露**
所选来源的用户明确确认目标 Applet、exact install/epoch、来源消息、逐项上下文/附件、允许
动作/回复位置和 expires_at。目标 Realm/Circle policy 必须允许披露。
新增 non-event action `ak.applet.invoke` 授予 exact Applet **接收所选披露**的资格；
`disclosure_grant_refs` 必须绑定该 Applet 的 full subject authority pair、registration/epoch 与
所选每项源 Message/Event、引用和 Blob resource。调用者仍必须独立具有当前 read 权限、目标
policy 明确允许向这个 Applet 披露、并签署本次 consent；Applet 的 receiving grant 不替调用者授权。
该 action 不授予 Applet 原群 read/scan/history、写入、MLS 或下一次调用。
该 action 的首发由本 profile 登记的同 scope current `ak.realm.admin` authority 签发，不能从
requested_scopes、membership 或包签名推导；UI 不能自动替用户批准全部历史。

最小加密通道是一个**独立 private Circle**及其 standard RFC 9420 MLS group，只含调用者和
exact Applet Account 的已接受 delegated device。Circle 必须按既有 creation/membership/grant/
MLS Genesis/Add/Welcome 合同建立；调用者缺创建/披露/成员权限时停止调用，不降级明文。
可以复用同一调用者、Applet Account、install 实例/epoch 的已获准 Circle；更换任一绑定必须
重新授权，不能沿旧 key/pending invocation 接收新内容。Applet 不获得原 Realm/来源 Circle 的
MLS private state。原群中可 mention 的成员资格不等于其原群 MLS 加入。

严格调用须有覆盖源位置和独立 invocation Circle 的 Realm 级 effective install；实际 grants
仍只授权所选源 resource 与该独立 Circle，不因此产生 Realm-wide read。原 Circle-only install
不足时必须由管理员明确续订 scope，不能静默扩大，也不能在原 Circle 中建立通道来交付群密钥。
Realm effective install 是其 resources 的上界，不要求实际 read grant 必须 Realm-wide；
MUST 允许 grant 用现有 exact Circle/Message/Event/Blob selector 缩小范围。每个 selector仍须位于
install ceiling 内，Circle install 不能越到 Realm 或其它 Circle。invocation Circle 的 read/write
grants 只覆盖这个 Circle，源群与其它 Circle 的 scan/subscribe/history/blob 全部保持普通拒绝门。
持续同步模式独立、明确地批准所需 read resources 与原群 MLS join；UI 必须说明它能解密获准
MLS epochs 的群内容，不能称其“密码学上仅 @ 可读”。

### 3.2 可验证的披露内容与附件

调用者提交普通 encrypted `ak.message.create`，解密后的 `kind=ak.content.applet.invocation`
必须通过 closed content schema。其 accepted `CommittedEventRef` 是 invocation 唯一身份，
不另 mint invocation id；完整 signed plaintext 的 `SHA256(JCS(...))` 是内容绑定。
Applet 验外层 Event/Commit/原 Device evidence、Circle MLS leaf，再验明文中的 invoker、target
Applet Account、registration ref/epoch、原消息/逐项 source refs、grant refs 与期限。
不能把 body/fallback、mention AST 或未签对象作为执行依据。

每项 `provenance` 固定 `invoker_disclosure`：原作者只为原 Event/密文负责，调用者为选择、披露
或转述负责。引用 original Event/Commit 或 Station 背书不能证明转述是原作者签名的原文。
本 profile 不提供这种原文明文一致性证明，也不允许 UI 作这种归因。
上下文默认只有调用消息；引用链、summary、历史窗口须逐项确认，不递归展开。

为使跨群转交仍能验证**调用者确实签署该披露**，invocation 内必带原 AccountDeviceSignerEvidence
和 `ak.applet_disclosure_signature.v1` detached signature。签名者必须等于外层 invocation Event 的
exact invoker Device；在原 covering Commit 时间独立验证其授权/generation/window、Service
attestation/native history 与签名。该 signature 的 host projection 是完整 Content Block 去掉
`signature`，并按 `detached-object-signature.schema.json` 算法签署；不替代外层 Event proof。

附件采用 closed `disclosed_attachment={source_blob_ref,attachment}`。调用者先对批准的原
Blob 完成原 AEAD/内容验证，再仅把选择的文件按现有 `blob.schema.json#/$defs/encrypted_attachment`
算法重新加密到 invocation Circle，上传新的 ciphertext Blob；attachment 的 `key_ref.group_state_ref`
必须是该 Circle 的已验证 MLS state。标准 whole-file/streaming AEAD、AAD、nonce/段数与 digest
规则完全复用，不新定义算法或密钥封装。原 Blob 引用只作披露来源，禁止交付原群 exporter、
epoch secret、其它文件 key、raw group private state 或泛化 credential；不能复制原群 key_ref
让 Applet去索取原群密钥。调用者若无新 Blob 上传/披露权限，停止该附件交付。

新附件 Blob 的 read grant 仅覆盖该 invocation Circle 的具体 Blob；源 Blob 的披露 grant 不
授予它或其它 Blob 的 GET/presign。嵌套 Content Block 的 attachment/reply_context/composite
parts 必须递归以已确认的内容和新 Circle descriptor 构造，禁止把未确认 extension、原群 key
descriptor 或跨 scope引用自动展开进快照。已有 attachment descriptor 必须逐字列入所选
attachments，重复或超集拒绝。附件 descriptor 与 sources 同受 invocation signature/MLS 保护。

### 3.3 执行、签名结果与原群转交

Applet 必须先取得覆盖本次具体动作/resources 的 independent capability grant；其现有
`authority_control.applet_authority` constraint 可带完整 `invocation_ref`，由该引用冻结到本次
调用，不能由另一安装、另一次调用或 generic Realm read grant 代替。grant 必须有不晚于
invocation expires_at 的实际期限；issuer 仍按所授 action 的普通 authority 规则验，不因是 Applet
加通用 subject-kind 门槛。接收端须验证该 invocation 的已 accepted Event/Commit 与完整目标绑定。
客户端/runtimes 在新披露、执行和提交前重验 current install、grant、membership、policy、期限；
服务端准入仍独立按原 action/resource/grant 条件检查，不依赖服务器解密 mention 或内容。

Applet 在独立 Circle 自己发送 ordinary encrypted result Message。
其 `ak.content.applet.result` 包含完整 invocation_ref、signed invocation 的 digest、Applet Account、
exact install/epoch、原调用者 Account 和所选 result Content Block。
结果签名的 created_at 必须在 invocation 已 accepted 之后、期限之前，并不晚于 result
covering Commit；relay 验证这些时间和本次完整绑定，不能用历史合法 key 签一个没有期限的结果。
同时携 `Principal` signer evidence 与 `ak.applet_result_signature.v1` detached signature；
其 host projection 是完整 result Block 去掉 signature。必须重算原 Principal root、实际 native
history/Station attester 绑定并验证该 Account 在签署时的 aligned authority；不能从裸 key/JWK
或当前网上 DID head推断。外层 result 的 Device/MLS authoring 与内层 Principal 内容证明分别验证。
因此原群读者可验证 Applet 自签的结果明文；原 result Event 的密文签名或 ref 本身不替代这份证明。

只有当前仍获权的**原调用者持钥客户端**可把结果加密回原群，提交自身签署的 ordinary Message。
`ak.content.applet.relay` 冻结原 invocation/result Events、covering Commits 与两个完整 signed
Content Blocks；recipient 检查两份独立 plaintext signatures、invocation digest/ref、Applet
Account/install/epoch、result audience 和转交 scope/resource。`verification_scope=relay_disclosure`
明确只证明这两份独立签署内容，不能宣称证明它们与原 MLS ciphertext 的解密一致性。
UI 必须分开展示“Applet 签署的结果”和“调用者转交”；消息 actual producer 是调用者，
不得伪造 Applet 的原群 Event、`executed_by` 或原作者明文来源。

调用者离线时结果保持待转交，runtime/Station 不凭空生成原群加密回复。恢复后先核当时的
source membership/grant、install/epoch/期限和 MLS current，再允许新 relay。被撤销/到期的调用
不产生新披露、执行或转交；已合法交付的内容和签名历史仍可审计，不能远程收回。
本合同不授权另一个后台持钥转交者；需要无人在线自动转交的产品必须另行明确授权其生命周期。

## 4. 准入与实现声明

新 wire 不支持时 MUST 以现有 `unsupported_feature` / `schema_violation` 零副作用拒绝；
不得把仅有 HTTPS push、旧独立 Bot、全量 read 或原群 MLS member 的实现声明为本合同支持。
规范 fixture 的通过只证明合同/验证器，不能冒充独立 runtime、浏览器、数据库或跨进程生命周期验收。
对应 implementer 必须验证两种 transport 首装/重启、Service/PCR 轮换中间态、多 Station 隔离、
撤销队列、最小披露/附件、调用重放/结果替换/身份冒用、离线转交和 read/scan/history/blob 绕过。

合同／算法专项向量：`ak.vector.applet.self_actor_contract.v1`。独立运行时生命周期验收
`ak.vector.applet.self_actor_live_lifecycle.v1` 保持 reserved，满足 §4 后才可激活；不得以模型测试替代。
