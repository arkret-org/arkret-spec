---
title: 可恢复内容加密与历史交付
status: candidate
normative: true
stability: v1
updated: 2026-11-13
---

# 可恢复内容加密与历史交付

本章MUST／MUST NOT等关键词依[规范语言](../conformance/normative-language.md)解释。

## 1. 两个独立选择器

本章是应用正文、可恢复内容根、授权历史及PCR恢复的规范合同。机器真源为
`content-encryption-registry.json`、`content-encryption.schema.json`和canonical catalog的
`content_encryption_contract`。它替代“应用只能PrivateMessage／历史秘密永久禁止”的旧限制；
MLS仍用于群成员、epoch、Commit／Welcome，Signal／RTC仍使用自身已登记的用途。

encrypted envelope必带`encryption_scheme`；`content_type`只标识解密后的业务内容。
当前唯一active方案为`ak.encryption.epoch_content_aead.v1`：ciphertext是应用AEAD的
`ciphertext || tag`，**不是**RFC 9420 PrivateMessage。信封版本保持`1.0`，不得猜测旧格式或回退明文。

Realm genesis必带`initial_encryption_backup_strategy`，参与原Event ID preimage；Realm query的
`encryption_backup_strategy`从该原签值投影。当前唯一active策略为
`ak.encryption_backup.epoch_content_roots.v1`，create-locked。该字段不自动激活MLS。
Circle／Sidecar独立群在accepted MLS Genesis时冻结其所属Realm的注册策略为自身策略；其
`backup_strategy_ref`仍精确指向该策略的原签声明，不继承父群secret／epoch／history权限。

未知、reserved、未实现的scheme／strategy及其不匹配组合MUST拒绝，不得忽略字段或静默降级。
未来策略／格式用新的稳定v1 ID登记closed schema、KDF、能力、授权／耐久语义及正反向向量后激活，
不需发明v2／任意options字典。当前不允许原地切换；将来若登记迁移，必须保留原scope／身份与全部
历史的原scheme／basis及解密路径，不能按最新策略重新解释旧密文。原始MLS PrivateMessage不作为兼容分支保留。

## 2. 精确KDF与原件绑定

`C_root`为`content-encryption.schema.json#/$defs/root_context`的RFC8785 JCS字节。
effective_scope、immutable genesis、epoch、group_state_ref和cipher_suite必须从同一已接纳MLS
结果核对；strategy及backup_strategy_ref必须来自原签genesis。裸epoch、当前投影或同名其它群都不能替代。

```text
R = MLS-Exporter("ak.epoch-content-root-v1", JCS(C_root), 32)
root_ref = "sha256:" || hex(SHA256(UTF8("ak.content.root_ref.v1\n") || JCS(C_root) || R))
C_item = content_context 的封闭对象
K = ExpandWithLabel(R, "ak.content-v1", SHA256(JCS(C_item)), AEAD.Nk)
key_commitment = "sha256:" || hex(SHA256(UTF8("ak.content.key_commitment.v1\n") || JCS(C_item) || K))
```

`C_item`的producer取原accepted授权事实绑定的完整Actor、endpoint、authorization Event和Ed25519
leaf签名公钥。Human不能只用Actor／counter／leaf index；Agent必须绑定其current method及授权实例，
不能伪造DeviceId。正文C_item的purpose固定为`event_body`、算法固定为`aes128_gcm`；
附件使用media-and-blob §3.0独立的blob context与label，不能套用正文KDF；
当前正文用AES-128-GCM、16-byte K，root为32bytes。新内容各取32-byte CSPRNG salt。

信封context携epoch、group_state_ref、content_key_salt、root_ref、key_commitment、protection及可选登记routing；
其余C_item成员从原签外层、历史MLS及原producer事实重建，不相信随包复制的事实。
令`E`为冻结Event删除`event_id,payload,producer_proof,unsigned`后实际存在的成员，`M`为信封删除ciphertext后
的成员；正文AAD精确为`JCS({outer_event:E,envelope:M,content_context:C_item})`。
本地消息起草carrier必须保留实际producer和完整E的SHA-256摘要，按service-http-binding §2.8的
`message_encryption_context`合同在最终authoring逐字核对。Direct／委托／semantic refs与实际endpoint
必须先于seal固定，不得在密文产生后另取时间或补授权；这些本地字段不替代原native来源或当前发送资格。
同一本地消息的正文和metadata须绑定同一原群结果、root_ref和producer，并逐槽使用不同content_key_salt；
最终authoring必须拒绝跨槽复用salt，不因MIME或AAD不同而放行。
K仅使用一次，nonce固定12个零byte。原producer proof按既有Event规则覆盖完整原件及密文；
key_commitment必须先核对再AEAD解密，不能把GCM当作key-committing构造。

构造顺序为accepted群结果→root备份→冻结salt／意图→K／commitment→AEAD→Event ID及签名。
任何自身ciphertext digest／Event ID不得进入KDF，root_ref不得反向写入生成R的MLS GroupContext。
exact retry重发完全相同原件；改变正文、epoch、scope、endpoint或basis必须另取salt并创建新Event。
接纳终局未知时先对账，不重新加密覆盖已接纳原件。历史验证使用原cut，当前授权用于新的发送／交付。
同一root_ref／已验证producer／purpose／salt只能对应一份不可变内容意图；不同原件复用该域必须拒绝，
不能认为更换AAD或MIME类型就能安全复用K／nonce。已接纳原件索引承担该唯一性核对，exact重放除外。

## 3. 备份与耐久覆盖

不保管原始exporter_secret、secret tree、已消费消息key、旧leaf signer或可克隆endpoint状态。
现有`backup_kind=secret_storage`增加closed `content_epoch_root` item，含C_root、R与root_ref；
沿用既有KeyBackup签名、series、AAD／HPKE、current policy及active-series规则，不建立第二套备份API。
公开contents列item_kind／secret_id，根条目还列root_context／root_ref；解密后必须与完整条目逐项对应。

多个R可以批量封装在不可变块中；每个新块必须fresh独立AEAD key；HPKE块以fresh CSPRNG ephemeral通过key schedule派生。含新R的压实块不得复用旧端掌握的
块key／account secret，所有recipient分支都不得再向旧设备开放。recipient公钥只从accepted policy
取，日常设备／runtime不持久保管backup私钥或助记词。普通DID root轮换不改变backup key。

新epoch first-use前根块须耐久。原Event／Commit、密文blob、根包及coverage必须在同一接纳边界绑定；
可先prepare对象，但任一必需对象缺失时不得提交成功，禁止best-effort窗口。
coverage按256项以内不可变页串联，从genesis至独立验证的cut逐位置核对原Event／Commit、root及blob，
页摘要为`sha256(JCS(页删除page_digest))`。不能只计条数；缺条、重复顶替、缺root、分叉、旧前缀或
未完成页均不能宣称完整。可复算的旧清单不证明最新；current／nonce／authority资格必须独立验证。

coverage是既有committed Event scan／get及其原签protection的可重建派生索引，不是第二个历史权威或
未登记的上传／读取API。服务在原接纳事务保存该索引；恢复端按独立验证的cut扫描全部原件重建并核对
相同覆盖关系。缓存页可丢弃重建，原件／blob／根及其来源证明不可缺失；不能以缓存清单代替原件验证。

### 3.1 跨Station的根保管来源（normative）

`content_epoch_root`从首次原生PUT成功起即承担归档保管义务，不以某条Event已经接纳为前提。
保管单位是完整备份主体、C_root及root_ref；没有成功业务原件、first-use失败、CAS loser、来源过期或
终局未知均不解除该义务。包可依§8.3充分替换／压实，但最后充分根材料不得普通删除。
这不是逐Event可过期租约、共享prepare阶段或第二套备份API；同epoch的重试不产生新的R。

Account／Agent跨站`authority_forward`须按原提交顺序，在`content_backup_sources`中为每个含登记
Epoch Content AEAD槽的Event携恰好一个closed `backup_source`；普通单Event最多一个，审计配对最多两个。
无此槽的Event不携来源；遗漏、重复、额外或乱序均零接纳。来源不能用于committed_replication或
registered_atomic_unit代替其原生依赖检查；其它合法首次接纳载体仍须证明本地完整依赖，不能略过缺失来源。

`backup_source`由`attestation,origin_resolution`组成。attestation按canonical schema顺序携
`event_ref,event_original_digest,producer,effective_scope,destination_service_id,protections_digest,
verification_method,attested_at,expires_at,signature`。
`event_original_digest = "sha256:" || lower_hex(SHA256(JCS(完整原Event)))`，包括实际producer_proof及
所有实际出现的成员，不用E摘要、Event ID或删proof的摘要代替。`producer`须等于独立原生核验的实际
ContentEndpoint，其Actor取executed_by存在时的值，否则取actor_id；跨站来源只由该完整Account的
原Station保管服务签发，不能改为controller、目标governor、Account Authority或其它服务。

令P为从该Event已登记schema槽逐项投影的`[{content_path,protection}]`，以RFC6901 JSON pointer的
UTF-8字节序排序；每槽的protection保留原数组顺序，必须完整且path唯一。不得搜索任意extension中的
envelope形状、忽略metadata或把正文嵌套附件的公开保护依赖丢掉。
`protections_digest = "sha256:" || lower_hex(SHA256(JCS(P)))`，P为空时禁止来源。
signature使用标准Ed25519 service签名形状，kid等于verification_method，签名字节精确为
`UTF8("ak.content.backup_source.v1\n") || JCS(attestation删除signature)`。
origin_resolution须在attested_at冻结完整method-native Service历史，独立验证该Station保管服务的
实际签名method／公钥；不是调用方公钥、当前DID捷径或仅有签名者授权的证明。
attested_at不得晚于首次准入now，`0 < expires_at-attested_at <= 300秒`且now早于expires_at；
来源过期只要求重新核验签发，不允许删除根。已accepted exact retry仍先返回原结果，不重跑当前门。

origin在自己的同一原生锁定cut核原Event／proof、原群结果、根包首次接纳索引、精确Root／backup引用、
充分当前recipient及必要替代映射；根包、索引与既有§10原件来源日记共同耐久后才签发来源。
先冻结此来源，再签Device／Agent／审计配对producer evidence；既有完整forward_body_digest投影
包含content_backup_sources，不删除该字段或另试预像，因此没有循环签名依赖。
仅复制备份密文、signer evidence或caller自报durable均不构成来源。

governor独立核原签Event、实际producer当前准入、已验证来源、actual destination及P摘要，并验证其
实际密文Blob／内容地址等依赖，在自己的同一事务保存原Event、winning Commit、coverage与完整来源私有审计。
来源不授当前写入、membership、历史披露或原件accepted资格，不随普通成员复制公开PCR／custody信息。
同Station路径直接执行相同原生根保管检查；不得伪造peer来源代替本地事实。
不同服务不共享DB、配置、私钥或后端函数，只沿已登记网络接口取得所需原件及终局。
origin暂时断连不等于根已丢失；已有未过期且独立验真的保管来源可支持接纳，恢复读取仍重试原Station。
没有充分来源、根缺损或终局未知均不能猜测成功，也不能通过超时释放最后根。
合法Realm治理交接须移交上述私有接纳来源及保管者引用，根仍由原Account Station保管；
新destination的来源可沿已验证权威重新签发，不重签或重加密原Event。
Human／用户管理Agent不因此取得更换逻辑Station的能力；同Station的hosting搬迁仍按原身份验证。
独立字节向量`ak.vector.crypto.content_backup_source.v1`覆盖原件／service签名、完整槽绑定及拒绝分支；
它不证明根包原生PUT、Service当前资格或故障后的物理耐久，后者须独立真实服务验收。

### 3.2 Realm Bot／Ghost 的原生根备份（normative）

本节是完整 Realm Actor 的独立首次根发布合同，不要求先存在 Human 的备份、业务 Event 或其它主体的 seed。
沿用 `secret_storage`／`content_epoch_root`、既有 KeyBackup 操作与 v1，不创建 Account、PCR、SessionGrant、
第二套备份服务或公共 raw-R 交付接口。完整主体始终是带 kind 的 Realm Actor；本节不改变普通 Account／Agent 分支。
本节的规范参考转录登记为 `ak.vector.realm_actor.content_backup.v1`，见 [vector registry](../../artifacts/registry/vector-registry.json)
及 [native backup fixture](../../artifacts/fixtures/realm-actor-content-backup-fixture.json)。这些协议字节／真实签名／
HPKE／AAD／digest 与拒绝分支参考不证明 PostgreSQL 并发、真实网络、冷重启或物理保管；后者仍须本节真实联合验收。

#### 3.2.1 原生 recipient 与密钥职责

`realm_actor_recovery.content_backup_recipient` 是 closed descriptor，按 `key_agreement_ref,hpke_suite,public_key_base64url`
排列。`key_agreement_ref` 为该主体原声明中已验证的 DID `keyAgreement` 方法，suite 固定为已登记 X25519／
ChaCha20Poly1305 HPKE suite，公钥为 canonical base64url 编码的有效、非低阶 32-byte X25519 公钥。
接纳时 MUST 核该原生声明、原 DID method history 与实际 raw key；不能查询今日 DID 文档代替原声明。
`content_backup_recipient_ref` 为安装该 descriptor 的 create／reset／manager.change 原件的完整
CommittedEventRef，由接受事务派生，不进入自身 Event preimage。普通控制轮换、Device reset、status 或
recovery.set MUST 保留该 descriptor/ref；control.reset 无 replacement 时亦保留原两值，不能只因 reset 更新来源 ref。
`recovery.enabled` 继续只控制身份 reset，不是合法业务 Device PUT 的 gate。

recipient 私钥 MUST 在 manager-only archive vault 中独立随机生成并先耐久保存，不能复用 Device Welcome HPKE、
日常 control、DID update／next seed 或通用 authoring KEK。日常 Device、其 DeviceRecord／RootStore 及通用
key-material decrypt 对象不得持有该私钥或解锁 vault 的能力。治理 Station 只保管密文、原件、索引和原生结果，
不得持有该私钥。创建／恢复及转交的具体原签来源依 [Realm actors §10.9](../extensions/realm-actors.md#109-原生内容根-recipient-与归档保管normative)。

#### 3.2.2 Scope-specific series 与首次发布

原生 active series 的独立 current family 为 realm_actor_key_backup_active_series，唯一键是
`(完整 Realm Actor,effective_scope,backup_kind)`；不复用旧 Account／Agent current-key helper 的固定 arity。effective_scope 只可为
该主体所属 Realm 或其获准的一个 Circle；Realm 与各 Circle 独立，不继承隐藏 Circle、不使用 Sidecar／PCR／
realm_control 作为根的业务 scope。Device／普通业务调用者不得跨同 Actor 的其它 Circle 读取 pointer、counter、
predecessor 或 metadata；只有§3.2.5明确的 current Manager 私密 custody 库存例外，不授业务历史权限。

当前 manager Service 通过既有 `ak.key_backup.active_series` 的原生 realm_control 分支选择每个 scope 的 series；
外层 Event 的 actor 是真实 Service，record.actor_id 是完整目标 Realm Actor。record 必带 effective_scope、
manager_ref、recovery_ref、recipient_ref；原签绑定实际 current manager／recovery／recipient 原写入，禁止虚构
Account、Device、PCR source_commit_ref 或 executed_by。真实 Service record signature 与外层 producer proof
均须验证。Service Event 沿既有 ak.edge.applet.command.transaction.v1 的 events[] 封闭 standing-manager 入口，
核 current registration／manager、已登记 exact known scope、原 recipient／refs、CAS、pending=null；不依赖业务
active install／grant。owner／governance 任一 retired 或 Realm terminal 均拒，owner／governance paused 与 identity
recovery.enabled=false 本身不阻断维护。不新增 Service self/events Session／Bearer 权，不扩其它 Service 写入或
Device PUT；后者仍执行完整 current install／consent／业务状态／scope／MLS epoch gate。Device 只能追加，不能
设置 pointer、选择 recipient 或借普通 grant 替代 manager-maintenance 权威。
首次 pointer version 为 1，后继只在同一 scope 做严格 version/CAS 和 previous_series_ids 校验。

record.recovery_ref 冻结为该 series 被选择时的真实 Recovery 来源；接纳新 selection 时 MUST 等于锁内
current Recovery 来源，接受后不随 Recovery current revision 改写。普通 recovery.set 的 enabled 切换，
以及未替换 manager／recipient 的 Recovery 来源推进，MUST NOT 隐式要求重选 series。Station MUST 独立
验证历史 series 原件、原签和选择时资格，并在当前锁内核同一 manager_ref、recipient_ref、exact scope、
未退休的 selected series 及 pending=null；不能仅凭不等的 recovery_ref 拒绝仍有效的历史 selection。
新 PUT 的 auth_binding.recovery_ref MUST 取本次 current Recovery 来源，而非复制历史 series.recovery_ref。
同一 current cut 指本次一起核验各对象的当前有效性，不要求不同对象的历史写入 ref 相同；manager／
recipient 真正替换后的 fresh-series 要求、当前 Device／generation／业务／MLS 等全部门保持不变。

manager 可以先签选尚无 envelope 的新 series，故初次 PUT 不依赖一张尚不存在的备份回执。Device 必须读取本次
exact scope 已接受的 pointer 与公共 recipient；未选、旧 manager／recipient 或缺少已验原件时保持不可用，不能从
唯一可见 series、最大 sequence、到达顺序或默认配置猜测。首包 series_sequence=0；后继精确绑定同 scope 的直接
predecessor 与 supersedes digest，不能用另一个 Circle 的包补 predecessor。

原生 KeyBackup 的 `actor_id.kind=realm` 必须与 `encryption.recipient_method=realm_actor_recovery` 同时成立。
只允许一个 content_epoch_root item，包含真实 C_root／root_ref；禁止混入其它 secret class。
原生 root envelope 禁止 expires_at，显式 null 同样非法；原生 metadata 也不携 expiry。首次 PUT 后的原包／
完整来源／root 索引／固定结果／coverage 是持久 custody，普通 expiry SQL 过滤、查询层隐藏或后台 TTL 清理均
不得令其失踪或删除；只按本节正式 root 保管／充分替代合同处理，旧 Account／Agent expiry 规则不改变。
`auth_binding` 精确为 `{kind:"realm_device",manager_ref,recovery_ref,recipient_ref,device_generation}`，
其中前三个 ref 是原接受来源的完整 CommittedEventRef，device_generation 是正整数 Realm-native 代次。
它不是 PCR device_generation_ref；原生分支禁止 recovery_policy_ref、source_commit_ref、Agent custody 字段与
Agent signature 分支。实际 Device Ed 签名覆盖完整 envelope；签名 proof 的 DeviceId、原 authorize Event 与 method
必须匹配真实主体及当前原生授权。原生 AAD 在既有固定 base 中另纳入完整 auth_binding，不能塞入 x_* 或改变
普通 Account／Agent 的 AAD；精确转录见 [key-management §7.5.6](../identity/key-management.md#756-realm_actor_recovery)。

首次 PUT 必须在同一原生锁定 cut 重查当前治理任期、manager／登记、双业务 gate、无冲突 recovery pending、
Device 原授权／代次／窗口／撤销、exact scope/action、当前安装与适用 Policy、获准成员状态、已接受 MLS
Genesis／epoch／group_state_ref／cipher suite、当前 recipient 以及该 scope 的 active pointer。
`recovery.enabled=false` 不得单独阻断其它 gate 均有效的 PUT。服务 MUST 独立验证实际 Device 签名及原件引用；
body、DID URL 拼写、HTTP 成功、本地 frozen packet 或 claimed durable flag 均不产生写权。
Device 的四个 native backup 操作按 [device-lifecycle §16.2](./device-lifecycle.md#162-已登记-operation-的配对消费normative)
使用 Controller 原签 DeviceAuthorize exact scope/action 上界与真实 Device proof，属于 subject-only non-Event；
不要求也不得为它们造 Service parent／terminal child 业务 grant。所有上述实际当前 gate 仍执行，真正业务 Event
的 grant／审批／quota 另验，不能继承本分支或拿此例外授权其它操作。

根值、最终签名密文及稳定 PUT 意图必须在发网前耐久；重试使用同一 backup_id、完整字节和幂等键。
只有真实已认证 PUT 对 exact backup_id／ciphertext_digest 的成功结果，才可写入 accepted-publication journal 并供
后续业务加密引用。ciphertext、完整 signed envelope、原 first-admission signer／policy 来源、根索引、series CAS
与 exact outcome MUST 同事务耐久，成功响应不得早于该提交。原生 receipt 的 envelope_digest 精确为
SHA256(JCS(完整原 signed KeyBackup))，包括完整 signature；它与既有 supersedes_digest 的删签名投影是两个
独立轴，不能互换。相同 backup_id 的完整 canonical body／signature 任一差异必须零效果冲突，不能重签当重试。

已 accepted 的 exact retry 在本次仍合法、且确为原 requester 的真实认证后，应先返回原 ACK／admission；
不得重新执行首次 PUT 的新 epoch／recipient／业务 gate 来否定已经固定的原结果，也不改变 archive_revision。
这不恢复已失效 Credential、已撤销／fenced 的原 Device 或过期原授权：真正当前认证／原 generation 失效仍拒，
新 manager 应从完整私密库存对账该原结果。未知意图只有未发现原 fixed outcome 时，才按首次 PUT 语义继续。
超时或崩溃保持未知并对账原意图，不能重新加密成另一成功意图或伪造 ACK。
实际业务 Event 接纳仍独立核物理根包和当前 recipient／writer；journal 不授当前写权。

#### 3.2.3 密文读取与历史恢复

既有 list、unlock-challenge 与 unlock 使用独立 closed 原生角色。Device 的 `series_predecessor` 仅允许本完整
Actor、exact scope、当前 selected series 的当前 head；空 series 返回空，禁止 cursor、任意 series_id、previous
series 或旧包枚举；Device list 还禁止 limit／backup_kind。list 只返回该 head 的 metadata，逐对象 unlock
只交付同一当前 head 的完整签名密文及原生
准入回执，用于验证当前 root／严格续链。同 Actor 的 sibling Device 可为合法原作者；own Station 必须独立
保管并验证其完整原 first-PUT 授权来源，再在本次受验 bound response 交付最小 signed admission。
Device 以该回执绑定的原公钥验证完整包的真实 Ed 签名，不能比对今日公钥或从 signer 发起新的 DID／治理发现。realm_actor_backup_series_head_response_body 的 closed 字段为 purpose、realm_actor_id、effective_scope、active_series、items，
items 最多一项 closed `{metadata,admission}`，metadata 为 realm_actor_backup_metadata 的原生 typed 投影，
不携 ciphertext；没有 cursor／has_more 或历史系列页。Device exact unlock 的 closed 响应为 `{backup,admission}`，
backup 是完整原 KeyBackup；不能用原 Account／Agent 单独 KeyBackup 响应或 Manager full-source 分支满足请求。
Device 的首次 PUT ACK 同样只携最小 admission，不下发完整 native_source。
metadata 不能冒充完整可验签包：native envelope 签名、envelope_digest、ciphertext_digest 和 AAD 验证仍针对
exact unlock 交付的完整原 KeyBackup。challenge 必须绑定本次 current requester 的原 Device／generation、完整
Actor、exact scope、当前 head 及 packet digest，发放和消费均重查该 cut；并发 head 改变后不得交付旧 head。
它不提供 archive key、明文 R、旧 Event 读取资格或另一个 scope 的链。manager 的
`archive_recovery` 只按完整目标主体、一个 exact scope
与真实 current manager Service 身份读取归档密文；仅§3.2.5的 manager-only archive_inventory 允许
完整本主体库存枚举，不授业务／明文读取。两者均绑定 manager_ref／recovery_ref／recipient_ref、
备份／series／ciphertext、服务端单次 challenge、nonce、audience／service 与时间窗口；不得套 Account、
recovery session 或 Agent custody 字段。unlock proof 的 manager_ref／recovery_ref 与 requester Device／generation
是本次真实 current cut 的请求资格；recipient_ref 则必须精确指向目标原包历史 accepted recipient 声明，按该原
声明独立历史验真并与完整 signed envelope_digest 绑定，不得强逼等于当前 recipient。目标原包 auth_binding
及 admission 内全部原始 refs 保持冻结，不因本次 requester／recipient／manager 变化而改写。
不能用历史包原权威给当前 requester 授权，也不能因旧作者撤销或原 refs 与当前不同而否定真实旧签名。
没有新增 backup resource GET 或明文根 RPC；除§3.2.5明确登记的
manager-only 完整库存外，不存在 broad actor 枚举。

公共 recipient／pointer 仅沿既有 material `purpose=current` 的本 actor recovery 与 exact scope series 两种 selector
取得；series 的公共 current value 仅含 active_series_id、series_pointer_version、manager_ref、recovery_ref、
recipient_ref 五字段；完整 Actor／exact Scope／class 在 selector，source／revision 保留原 accepted ref。它不下发
完整已签 record、previous_series_ids 或 inner proof。Device 仍须 current，且 pending 必须为 null。`purpose=event` 保持原有权限，仅允许本 Device 自己的
exact authorize 原件；本次不开放 recipient 声明、create／reset／manager.change、series 或 begin 的控制 Event 原件。
Station 必须独立完整验证原声明／DID／series、current reset→exact accepted begin 与同一 current cut，再供给公共
current 投影与 typed 输入；不得把 create 原件中的 creation_scope／external_ref 或其它有限 scope 外资料下发 Device。
Device 不自行回放 control／Actor DID／governance 历史，也不能从 metadata 或嵌套值推导 Event 坐标。
只有两个 selector 在同一 cut 完整且 Device／代次／current series 均有效时，响应才可携非 null 的
next_prepare_input={auth_binding,content_backup_recipient,active_series_id}；Device 逐字 echo，不自行拼装引用。
公共 metadata／next_prepare_input 是本次 own-Station bound 供给，不冒充嵌套 Event 历史来源，不附加读取原控制
Event 或按 signer 新发现网络的权利；Manager 的完整归档原件与私密验证闭包保持独立角色来源。
这些来源不含 archive 私钥，不授业务权限。Device 的最小 admission 只含正式回执登记的 exact Actor／Scope、
原作者公钥／Device／authorize ref／generation、manager／recovery／recipient refs、packet digests、原 issuer／
time／signature；不携 sibling DeviceAuthorize 原件、其其它 Circle scopes、完整 producer fact、governance history
或 method-native history。Station 对完整原始授权／治理闭包的真实独立验证及耐久保管仍是交付前置门；
Device 在本次已认证、current、exact actor/scope 的 bound response 验证后以回执原公钥验包，不能用调用者给定
key、当前 Device directory 或独立从 receipt signer 发现网络代替。metadata／receipt 不冒充完整包 Ed 验证。
manager 的 inventory／archive_recovery 只按本 Actor 目的取得完整 native_source，且受当前管理资格核验；
Device 不得以 fullSource 参数、Manager purpose、缓存或其它 mode 获得该私密闭包。

manager vault 只在已验证完整 Actor、目标 Device 原授权／代次、当前 scope membership 与 history floor、确切
历史原件及 recipient 来源后，通过受限本地 capability 恢复专用根。恢复值只能进入 history-only lane；不能安装
活跃 MLS checkpoint／leaf／ratchet、克隆旧 endpoint、授 membership 或绕过新 Device 的 KeyPackage／Welcome。
不能从日常对象的共享 KEK 解开 archive vault，亦不能用一个 transferable verified 布尔绕过上述来源检查。

#### 3.2.4 完整保管、管理转交与治理交接

从首次真实 PUT 起，全部根索引均承担 §3.1／§8.3 保管义务，包括尚无业务 Event、CAS loser、失败 first-use、
未返回 ACK 和终局未知的根。普通删除、retention、recipient／series 轮换都不得删除最后充分包；删除资格必须在
与 policy／series 同一互斥边界检查完整索引及已耐久、可由当前合法 archive vault 解开的替代包。

manager.change 之前，新 manager MUST 实际私密导入所有必要旧 recipient 私钥、原声明、完整 root custody
索引、包／series／coverage、固定结果及未决意图；其完整 manifest 摘要作为 content_backup_handover_digest
进入真实新 Service acceptance，另以 content_backup_inventory_digest 绑定治理方已验证的完整原生库存。只有签名、摘要相等或数据目录存在不足以证明导入。缺任一必要旧 key／来源或根
材料就保持 paused／未就绪，不以新 recipient 掩盖历史丢失；不新增 staging 或提前伪接受的 PUT。

接受 manager.change 时原子切换 manager、Device generation 与 fresh future recipient，旧 manager 立即丧失
current 权。旧 recipient 仅用于已验旧包的历史解封，MUST NOT 授新 PUT；新 manager 保留 owner paused，按 scope
选择绑定新 recipient 的 fresh series，确认全部必要 scope 库存／覆盖就绪后才可显式 resume。其它 Actor 的授权、
AppletId、Realm 身份、membership 与 MLS group 不因转交改变。

所属 Realm 的合法 governance handoff 必须实际导入上述全部服务端密文、原始准入来源、首次 PUT 索引、
scoped pointers、challenge／nonce／去重／固定结果及保管义务，不能仅导出已有业务 Event 引用的包。
这些全部原生私态 MUST 在 handoff 的同一冻结 cut 纳入既有 management_private_state 的完整 canonical 私有导出，
由其 state_digest 及既有 management_private_state_digest／双签 handoff 承诺，见
[authority-commit-log §10](../sync/authority-commit-log.md#10-applet-管理私态的既有交接)。必须逐完整 Actor／exact
scope 保留 archive_revision、全部 first-PUT 原包和原 author／治理／recipient 来源、所有 scope-series／原声明、
root／last-sufficient coverage、fixed outcome／幂等／challenge／nonce 及未知结果意图；无业务 Event、CAS loser、
丢 ACK 和失败 first-use 均包括在内，不能把它们过滤出导出域。旧站冻结写入，新站实际完整物理导入后，必须从
导入的真实存储重导出并比较同 cut 的 canonical state_digest；只复制 manifest／摘要、当前 rows、已引用包或
本地 ACK journal 不构成完整导入。缺项、额外冲突、不同 revision／cut 或无法重导出均不可激活新任期。
本条只复用既有私有 handoff carrier、salted commitment 和真实网络路径，不新增 HTTP／raw-root 公共读取面，
manager-only archive 私钥／解锁能力及成员 MLS 私态均不属于 Station 私态导出。
旧治理方冻结 native 写入，新方完成验证和物理导入才可激活；Applet 的 archive 私钥与成员 MLS 私态不进入
治理数据库。Account／Agent 仍固定其原 Account Station；Realm Actor 原生 custody 不得冒充该固定账号规则，
也不允许借备份创建新的 PCR／Station 迁移权。跨独立服务只用已登记认证网络操作，不共享业务数据库或私钥。

#### 3.2.5 Manager-only 完整库存与转交 cut

仅当前真实 manager Service 可在既有 GET /_arkret/self/keys/backups 使用 purpose=archive_inventory，
按完整 realm_actor_id 读取该主体跨 scopes 的完整原生归档库存。Account、Agent、Device 及旧 manager 均禁止；
此分支与 Device exact-scope head 及 Account／Agent metadata 分支严格互斥，不允许 circle_id、series_id、backup_kind 等子集过滤伪装成全量。
它不返回私钥、明文 R、成员私有 MLS state 或其它主体资料，也不授任何 Circle 的业务／历史读取权。

库存必须包含全部首次 PUT 永久准入索引及完整原包、保管替代来源、每个 scope 的 series／指针、历史
recipient 原声明与必要原始签署来源；无业务 Event、CAS loser、丢 ACK、失败 first-use 和未决结果均不能遗漏。
不得只扫描 content_originals、当前可见业务流、客户端本地 journal 或当前单一 series。
私有 first-PUT row 使用自己的原生库存标识／revision，MUST NOT 伪造 EventId／RealmCommit 或 stream position。
每个 first-PUT 的原作者证据必须保管实际原 DeviceAuthorize／原接受 cut、原 generation、manager／recovery／
recipient 声明和真实签署 key／原验签来源。旧 Device 撤销、换代或日常 key 移除后仍以该原始来源验原包 Ed 签名，
不得用今日 key 或 accepted=true 重构。该 closed durable source 与真实 ACK／包 id／完整 envelope digest／
ciphertext digest 在同一首次 PUT 事务固定；它是原生保管结果，不是新共享 Event、RealmCommit 或可转移写权。
完整私密 `realm_actor_content_backup_source` 为 closed `{admission,device_authorization,origin_resolution,governance_history}`，
只供治理方保管／验证和获准 current Manager 的归档用途，绝不因 Device predecessor 读取而披露；
`admission` 是治理方在首次 PUT 同事务固定的真实 detached Service 回执，
不是 Event／Commit。其字段绑定 backup_id、完整 canonical signed envelope 的 envelope_digest、ciphertext_digest、
完整 realm_actor_id／effective_scope、原 device_id／device_authorize_ref／device_generation／公钥、manager_ref、
recovery_ref、recipient_ref、accepted_at、真实 service_id／governance_generation／authority_ref。
context 固定为 `ak.realm_actor_content_backup_admission_signature.v1`；按 proof registry 的 unsigned projection
及 detached-signature 转录验证，receipt.signature.created_at 与原 admission.accepted_at 一致；包的 created_at 仍是原 producer 签署值，不得改写。
admission.accepted_at 必须取真实 first-PUT 耐久接受时钟，不由包 created_at／客户端声称时间或重试时钟代替。
服务签名必须由独立验证的原始治理任期及
原 Service method-native history 支持；origin_resolution 只证明方法 key，不单独证明谁是原治理方。
governance_history 必含真实 Genesis Event＋Commit＋依原 digest 约束携带的 producer fact，以及到原接受任期的
真实治理转移／handoff／原 Service resolution；不得把当日 key、当前 nonce 包装或无依据的治理声明当原任期。
governance_generation 按既有 uint64_decimal 字符串真源编码，不是 JSON number。
device_authorization 必须是实际原 DeviceAuthorize Event＋Commit＋必要原 fact，精确匹配回执坐标、key、代次、
主体及 scope；同时对原包执行真实 Device Ed 验签。新 nonce-bound material 包装、今日 Device projection 或
accepted=true 都不能替代这个原始闭包。首次 native PUT 的 Device 响应必须选携最小 admission 的独立分支，
不能拿结构上合法的 Account 响应代替，也不能披露完整 source；完整 source 在原事务保管，幂等成功重放返回
同一原 admission／accepted_at，不推进库存 revision。Manager 库存及已知单包 archive unlock 才交付完整 source。

完整 manifest 的 closed 字段为 realm_actor_id、manager_ref、archive_revision、entries；entries 是互斥的
backup／series／recipient 原件分支。backup 携完整 signed KeyBackup 与 native_source；series 携 exact scope、
已签 record、原 source_ref 和完整 source:event_material，source 坐标 MUST 与 source_ref 精确相等；recipient
携原声明 Event＋Commit＋必要原 fact，reset 安装的
replacement 还必须含该 reset 精确引用的 accepted begin 原件，其它声明禁止多带 recovery_begin。
条目身份键分别为 `["backup",backup_id]`、`["series",effective_scope,record.active_series_id,record.series_pointer_version]`、
`["recipient",recipient_ref]`。对这些 typed keys 作 RFC8785 JCS，按所得无符号 UTF-8 字节序排序，拒绝相同身份键
的重复条目，即使其余内容不同。inventory_digest 精确为 SHA256(JCS(完整 manifest))，不得按页、到达顺序、
时间或新响应包装排序／求摘要。所有该 digest 的转录均使用此唯一投影。

返回 typed、有界、确定排序的分页以及 inventory_digest，所有页绑定同一完整 Actor、current manager、真实
请求 role 与冻结 inventory cut。recipient／series 原件必须是不可变 Event＋Commit（及原 fact），
不能把有新 nonce／audience／expires_at 的 material response wrapper 纳入库存摘要。原生 archive revision
只因真实库存变更推进；幂等重试、读取或刷新响应包装不递增，合法 governance handoff 保留它。
inventory page 精确携 purpose、realm_actor_id、manager_ref、archive_revision、inventory_digest、entries、
has_more 与适用的 next_cursor；每页最多200条、完整 canonical body 上限4 MiB，limit 默认50且为1..200。
单项无法完整放入该预算时拒绝，不能省略 source／原包或只给摘要。has_more=true 必有 next_cursor，false 禁止
该成员；opaque cursor 的词法、失效与跨 role／cut 纪律沿既有列表合同。完整性只能在同 cut
全部页结束并逐项重算摘要后宣称。原生库存、scope pointer、recipient 声明、保管替代或固定结果变化必须使旧
continuation 失效或继续该真正冻结 cut，不能无声换到新 cut。HTTP success、has_more=false 或摘要值单独不证明
实际包／私钥已被新 manager 导入。

owner paused 后的 manager.change 接受事务必须锁同一完整 Actor 的 root namespace；首次 PUT、series／
recipient／替代／删除及库存状态写入使用同一互斥边界。治理方在锁内以持久全库存重算摘要，逐字比较
content_backup_inventory_digest，且其范围必须为此 actor 的全部必要 scopes，而非调用者可筛选的子集。
new-Service acceptance 还绑定 content_backup_handover_digest，覆盖其真实耐久导入的旧 recipient 私钥、
原声明、完整库存与该 inventory_digest。
私密交付只沿既有 manager offer／transfer 渠道，并先核
[Realm actors §7／§10.6](../extensions/realm-actors.md#106-更换管理-service-必须交接原生更新权) 的真实转交资格及目标 Service 原签 offer。
私有 archive 必须独立域 HPKE 封装到该 offer 绑定的 fresh next archive public key；新 Service 实际 open 后，
逐旧 private key 重算公钥并核对原声明、逐原包及完整库存 cut，再把导入结果耐久后签 acceptance。
该私有过程使用 keys-operations.schema.json 中五个 closed DTO，不另造外部 HTTP：

- `realm_actor_content_backup_handover_offer` 为 new Service 原签 offer，精确绑定 realm_actor_id、manager_ref、
  new_service_id、fresh next_content_backup_recipient、inventory_digest、archive_revision、expires_at、nonce 和 signature。
  验真实目标 Service 原 method、有效期、完整主体与原 manager／冻结库存 cut，不把自报 offer 当转交资格。
- `realm_actor_content_backup_handover_plaintext` 精确含 offer_digest、完整 inventory_manifest、recipient_keys、
  challenge_base64url。每个 private-recipient-key 项为原 recipient_ref、content_backup_recipient 与 private_key_base64url；
  拒绝缺项、额外／重复 recipient 身份、私钥重算公钥与原声明不符。challenge 为独立新生成的32-byte CSPRNG秘密。
- `realm_actor_content_backup_sealed_handover` 精确携完整 offer、固定 hpke_suite、enc、ciphertext_base64url，
  使用 RFC9180 HPKE base mode 和该 offer 中 fresh next recipient。`offer_digest=SHA256(JCS(完整已签 offer))`；
  `info=UTF8("ak.realm_actor_content_backup_handover.v1\n") || JCS({realm_actor_id,manager_ref,new_service_id,offer_digest,inventory_digest})`，
  `aad=JCS(完整已签 offer)`；plaintext 即上项完整 closed 对象，不复用普通 KeyBackup info／AAD。
- 新 Service 实际 open 后核 offer_digest、manifest 完整性／digest／revision／主体／manager、所有原件／包／历史签名，
  并在独立 manager vault 耐久导入全部所需旧 key 与库存。`handover_digest=SHA256(JCS(完整 plaintext))`，包括秘密 challenge，
  不对页、本地 ACK 子集或自报数量求值。只有完成这一步才可签 `realm_actor_content_backup_handover_confirmation`。
- confirmation 精确携 offer_digest、inventory_digest、handover_digest、challenge_response_base64url、signature。
  response 为 unpadded base64url 的 `HMAC-SHA256(key=decoded challenge,data=UTF8("ak.realm_actor_content_backup_handover_confirmation.v1\n") || JCS({offer_digest,inventory_digest,handover_digest}))`。
  旧 manager 必须用原秘密 challenge 验 response、new Service 原签及 exact offer／cut；随后 public manager acceptance
  与 manager.change 才可签相同 inventory／handover 摘要及 fresh recipient。offer／confirmation 签名各用 proof registry
  登记的独立 context，不能改用日常 Device／control key 或未登记的通用签名标签。

这个秘密 challenge roundtrip 强制实现经过真实 HPKE open；签名、摘要或 roundtrip 自身都不是物理耐久的数学
证明，实际导入与崩溃／缺 key／缺包／错 cut 回归仍不可省略。尚未 accepted 的 next key 只用于该私有交接，不能
提前普通 PUT。私钥与 challenge 不得裸放共享 Event、KeyBackup root 包、一般 DeviceStore、日常 authoring KEK
或一般日志；私有 DTO 只由 SDK 唯一定义，secret 字段必须使用 zeroizing SecretBytes 并以 redacted Debug 处理。
治理方只取得公开摘要／原 source refs／接纳结果，不取得私钥或秘密 challenge。
任何缺项、cut／role／manager 变化或摘要不符均零接受并保持 paused；
不能以新 manager 的自报导入 flag、摘要相等或原包 ciphertext 的复制代替真正恢复能力。

验收 MUST 使用真实服务与耐久存储覆盖：首次 PUT 与 scoped-head CAS／manager change 的 PostgreSQL 并发、
成功响应丢失后的原字节重试、已 fixed outcome 之后 epoch／recipient／业务 gate 变化、原认证真正失效、
进程冷重启后的 exact receipt／库存／root 恢复，以及未产生业务 Event／CAS loser／失败 first-use 的 last-root 保管。
Device sibling head 正例必须核独立原签且拒完整授权／其它 Circle scopes 泄漏；manager 转交必须实际 HPKE open、
完整私钥／包／原件导入并冷重启后解封，缺任一材料、错库存 cut 或普通 Device KEK 都不得成功。多 Station 验收
只走已登记真实认证网络，不能共享数据库／私钥；参考模型、fixture 布尔、静态 SHA 相等或 HTTP200 均不替代这些证据。

## 4. 获授权后加入者

`history_access=all_history_for_current_members`必须有实际可读路径，不能只返回密文。
`since_join`是显式披露策略，其floor按完整Actor的合法join实例求值；同Account换Device或同Agent换runtime
不得改用新leaf的Add时间。普通Realm仍受当前membership、exact scope、policy与retention约束。
个人24词的强制全历史保证仅适用于§5的PCR恢复集；本章不承诺普通群聊永久无损保管或仅凭24词恢复全部群聊历史。
全scope安全收尾是旧endpoint隔离义务，不扩大任何业务scope的历史读取权限，也不改变普通retention。

recipient先提交原签durable `ak.mls.history_request`，payload为closed history_request，
以自身current native endpoint的Event key签署recipient／fresh X25519公钥／history_cut／expires_at。
主体只需该scope的current read资格，可为只读成员；request和recovery检查点采用self_authored_proof，
禁止executed_by／authorization_ref代签；必须由payload绑定的exact当前endpoint自己签署，请求不授membership或披露key，
不得套用issuer的管理员权限门。新公钥私钥仅在recipient端加密保存至请求消费／过期。

端点授权唯一由`recipient.authorization_event_ref`绑定，request与grant均没有顶层
`authorization_event_ref`；不得从一个opaque引用推导scope读取或issuer披露权限。
接受request的原RealmCommit确定其接纳cut；原件及原生资格来源仍须按各自既有合同核验，
不能把RealmCommit签名或request本身当成读取授权。
资源读取资格、完整Actor的合法join实例／history floor及issuer披露权限，分别沿既有原生规则求值，
不能以endpoint授权、当前MLS membership或原请求曾被接纳替代。合法读取授权可以晚于history_cut，
不得因此拒绝获授权后加入者的旧历史。

原Event signer必须与recipient完整Actor／endpoint及其原生授权实例匹配；
`recipient.signature_key_base64url`绑定其已验证MLS leaf。Event设备签名key可以与leaf signer不同，
但须由独立原生creator／Add／recovery绑定证明为同一exact端点，不能直接比等两把key，
也不能接受调用者自报的leaf归属。新的request及grant交付均核exact当前端点；
端点授权或leaf绑定失效时须创建新的request。§8的current-device历史根领取不依赖先发history_request，
因此全设备丢失时不会因尚未恢复MLS leaf而阻塞24词归档恢复。

唯一共享历史key载体是原签durable Event `ak.mls.history_grant`，复用现有Events提交／scan／get，
其payload由`history_grant`定义。recipient_key_event_ref必须指向上述accepted request原件；
核原request producer原签与原生端点绑定；grant的完整recipient、HPKE公钥、history_cut及expires_at
必须与该request逐字段相等，不能换key、换授权实例或扩大cut。recipient_key_event_ref绑定原request Event。
请求TTL最多900秒、expires_at大于created_at，过期请求不能签发或领取新的grant；
issuer与recipient在交付时均重查current资格，不能以请求原来有效绕过撤销。
issuer须有当前披露资格和对应材料；recipient须有当前读取资格，
并与Actor／endpoint／HPKE key／原请求及有效期逐字段绑定。该kind不授予membership、不修改MLS私态。
其payload是metadata及HPKE密文，不再套进依赖待交付root的应用信封。原签覆盖全部成员。

每entry的HPKE info与AAD均为schema所列closed header的JCS；default active HPKE suite，单发base mode，
sealed_key_base64url的解码字节唯一为enc[32] || ciphertext || tag[16]，无TLS／JSON／length包装。
16-byte DEK的总长恰为64bytes，32-byte DEK／R恰为80bytes；必须canonical unpadded base64url，
Open前拒绝错长、截断、非canonical、X25519低阶／全零shared secret；每entry使用fresh CSPRNG ephemeral，seq=0，
不携wire nonce，不复用enc。HPKE header另包含recipient_key_event_ref，info与AAD逐字相同。
plaintext仅为选定16／32-byte DEK或32-byte R。除完整且封闭epoch的全部内容均获授权外，只能发DEK，
不得用“当前页全部允许”代替完整epoch证明。epoch_root须核closed_epoch_cut，开放epoch禁止整根交付。
接收者核原作者、source Event／Commit、key承诺／root_ref及AEAD；共享者重签明文不是原历史。

`content_key` selector 的 `content_path` 是以 `source_event_ref` 的已认证不可变原Event为根的RFC6901 JSON pointer，不是物化Message、当前编辑结果或Blob metadata的路径。仅允许选中已登记的完整encrypted envelope（正文／metadata等，16-byte DEK）或已认证ContentBlock内符合encrypted_attachment schema的完整descriptor（32-byte DEK）；对象容器、任意扩展字段或标量不得自行视为key槽。逐token解析；数组下标必须为canonical十进制（`0`或非零首位的数字，不接受`-`、负数或前导零）。缺路径、错误目标类型或未知profile MUST fail closed，不猜同名槽、不回退至整Event。

若pointer终止于encrypted envelope，即选择该信封；若仍有后续token，MUST 先用另一项独立获授权的key验证该信封的原Context、key_commitment及AEAD，并按其已登记content_type解析明文，再在该位置继续解析后续token。例如 `/payload/encrypted_content` 选择正文DEK，`/payload/encrypted_metadata` 选择metadata DEK，`/payload/encrypted_content/attachments/0` 选择该正文解密后第一个附件的DEK；嵌套ContentBlock沿原 `parts`／数组位置继续。此解密视图仅用于定位，不改写原Event、EventId、producer proof、Context或AAD；重复JSON成员、不能按登记schema解释的明文或未认证父节点不得进入视图。

所选附件DEK的接收流程以media-and-blob §3.0为准，不要求接收者同时持有R。正文／metadata单项DEK也直接验证原C_item的key_commitment并按§2解密，不以DEK充当R。所需父信封key可来自已合法持有的材料；若需新交付，每项仍必须独立满足原accepted request、exact recipient、scope／cut、TTL及当前读取／披露资格，不能混换请求。一个附件selector不隐含父正文或其它key的授权。缺依赖则保持未完成，不得扩大披露或另造未登记的独立descriptor载体。原Event／Commit、历史producer与公开group provenance验证始终独立必需，交付key不成为这些原件的替代权威。

history-ready要求获准全部source的原件与grant已耐久且接收方逐件验证成功。只有membership、
当前snapshot或“去找旧设备”不算完成。有权端可预备密封材料，授权生效前不得向目标披露；
授权生效后的delivery仍核current gate。已经合法给出的key不能远程收回，撤权限制后续交付及新epoch。
允许all-history的scope必须维护可用的授权custodian及恢复来源，材料不足时保持未完成，不能伪报成功。

## 5. PCR24词恢复与旧端失效

个人PCR从accepted genesis到恢复cut的全部原件、必要blob、根和producer证据必须持续保管，
不受普通Realm有损retention／按epoch GC裁剪。当前有效24词为充分本地凭证：BIP39额外passphrase为空，
按既有隔离KDF重建recovery-proof和backup-HPKE；不需旧设备、旧端account secret、另存文件／口令或在线批准者。
首次启用必须确认两种公钥来自该24词并登记充分的accepted policy路径；未完成不得表示账号恢复配置完成。
初始公共控制原件也须完整保管，首条加密PCR写入前必须完成recipient登记及根耐久。
PCR 私有 Profile 的唯一 typed 槽与精确原件路径见 profiles-presence.md §2.3.1；其 C_item.purpose 固定为 event_body，
原公开控制字段不伪装为密文，PCR allowlist 不因历史恢复增加业务 Message。

复用既有policy-authorized RecoveryTransaction两Event原子unit，先推进generation、只授权replacement，
与session消费及current目录同事务提交，随后旧设备／session／队列／KeyPackage立即按旧代次拒绝。
基础policy恢复不要求current DID publication／updateKeys，不借unsupported first-device active-series分支。
下载历史只还原读视图，不能将旧snapshot／device authorize重新安装为current。

完整安全库存必须覆盖所有相关PCR／Realm／Circle／Sidecar／Direct的旧endpoint，包括无内容空群，
不等于非空root库。Join／Add／consume账本的登记及安全收尾须耐久；枚举与新membership／pairing有并发fence。
仍有当前参与资格的目标根据已验证的RFC roster实际Remove旧leaf，更新epoch／新根备份，保留其它Actor及合法成员。
已经失去资格或scope已不可逆终止的目标按§10.1取得removed／terminated窄证明，不重新入群、不领取新根。
各治理方收到收尾义务后保持全发送者业务屏障；未确认／不可达目标保持pending，不能以过期缓存跳过。
跨站rekeyed沿已登记participant／signer材料和Events authority-forward；失权／终止目标沿§10.1登记的self／peer命令取得窄证明与当前交付确认。两条路径均不公开PCR历史、不给服务端私钥。
最终成功必须同时具有PCR全历史精确读取及完整库存每个scope经独立验证的收尾结果；身份unit completed本身不足。
密码隔离保证从全scope收尾ready之后成立，不能谎称网络尚未确认的群已即时完成Remove。

恢复沿原group External Commit接入：仅在`mls_commit_payload.recovery_binding`有效、原Actor当前仍joined、
replacement授权已接纳、exact current base／epoch及库存digest匹配时允许new_member_commit／ExternalInit。
§6.1 的 controller endpoint 以其独立原生控制角色及原 accepted leaf 参与事实替代普通 joined 行，
仅限原 Agent PCR；不能据此建立业务 membership。
Human授权ref必须来自已accepted的policy-authorized RecoveryTransaction两Event unit，核reanchor／authorize／generation关系；
Agent必须来自当前controller批准且完整supersedes的实际pairing授权。普通DeviceAuthorize、普通Add或仅当前membership
不能授予此恢复例外。新replacement签名pub必须不等于该Actor任何被替换端的旧pub，并有独立fresh PoP。
未授权外部加入继续拒绝；握手不创造membership。External Commit仍是RFC PublicMessage，后续Remove不可省略，
中间epoch禁止业务。所有winning Commit必须耐久签入新GroupInfo／tree refs，existing group-state-material读取
可以请求对应accepted Commit的公开材料，不再只限epoch0；仍按当前／target cut及恢复policy私有授权披露。
可恢复群的GroupInfo必须包含RFC 9420 external_pub扩展，并与同一accepted tree／epoch核对，不能只保留缺少ExternalInit所需公钥的普通GroupInfo。
同base仅一个CAS winner；恢复fence、原件、reserved材料及step结果耐久，崩溃后对账续跑，不清空义务。

**External Commit治理绑定（normative）**：RFC 9420 §12.2不允许External Commit包含
GroupContextExtensions Proposal，因此此唯一恢复分支不更新GroupContext中的`0xF1C0`。
它必须逐字继承exact accepted base的全部GroupContext extensions，禁止借恢复修改policy或扩展；
旧extension只证明继承的base，不得与新payload的next epoch强行比较。
本次`MlsGroupBinding`仍使用encryption-and-audit §2.5.1的同一closed字段表和deterministic CBOR，
其精确编码必须完整放入RFC `FramedContent.authenticated_data`，不得添加前缀、JCS包装或trailing bytes。
该CBOR binding须与原Event的`governance_binding`及current scope／base／previous_epoch／next_epoch／
key_access_revision逐字段相等，并验证RFC原Commit签名、path及transcript。
`recovery_binding`仍由原Event producer proof和origin source逐项绑定；authenticated_data本身不授予恢复资格。
Genesis及Member Commit继续按通常`0xF1C0`合同验证；后续首笔Member清理Commit必须更新该extension
至自己的新binding。读取刚恢复epoch的公开物料或恢复本地checkpoint时，必须连同原External Commit
验证上述AAD binding及继承关系，不能把继承extension的旧epoch误当当前epoch，也不能跳过exact accepted base。
参考固定字节与负例见`content-history-fixture.json.external_recovery_binding`；真实RFC验证仍属实现验收。

恢复准入及后续清理使用同一current恢复授权门，不要求普通成员额外取得Realm管理员能力。
每个清理Commit仍带按其新base／epoch更新的recovery_binding；producer必须是已批准replacement，
Remove集合必须精确覆盖库存中该Actor尚存的旧endpoint，禁止删除其它Actor、普通Add／扩权或借机改变policy。
该窄例外仅允许完成已验证安全收尾，不等于给replacement通用ak.mls.commit管理权。
不同Actor的普通Commit、Add及非恢复写入继续原有capability准入，不能用恢复字段绕过。

## 6. 用户管理Agent与保密边界

Agent DID、完整Account、PCR、Station／controller pair和group ID不变。Agent备份主体始终是Agent。
Controller-signed `ak.agent.provision.history_custody`显式绑定Agent PCR至controller完整Account的
accepted初始恢复policy／backup key。该批准属于Agent账号的immutable provision，
不是runtime key授权；后续runtime supersedes不撤销它，key-authorize不再携该字段。
初始ref固定原批准basis，后续同custodian的连续accepted policy可按§8重封装／轮换，
不能仅换runtime就换custodian或复活已撤销key。当前runtime授权只说明运行权限，缺该明确批准不得推定可解历史。
provision／配对完成前须安排完整PCR的保管；新runtime丢失后不能倒补不存在的备份。

跨主体KeyBackup携`custodian_actor_id`和`custody_authorization_ref`，后者核上述accepted current授权，
recovery_policy_ref／recipient_key_ref在该custodian的accepted policy中解析；不得仅信DID Document。
原provision在Agent PCR创世前已accepted；首个根由controller可信端生成和HPKE密封，
按该原签批准上传，随后才接受首个依赖加密内容／profile，最后执行真正runtime pairing。
不预写runtime key授权，不让服务端持有R；任何准备失败不得接受依赖内容。
Controller可信客户端用自己的24词解Agent备份，仅将获准Agent根密封给经pairing批准的新runtime。
24词、backup私钥、Human其它scope及DID root不进入runtime。新runtime使用该同一fresh签名key接续原group。
旧runtime授权以完整supersedes／activation fence替换，不能套Human Device generation或创建新Agent。

### 6.1 Controller 的独立 PCR MLS endpoint

Agent PCR 的原件仍以 Agent 为资源 Actor，controller 代表其写入时维持既有
`actor_id=Agent`、`executed_by=controller` 与原生 `authorization_ref`，不增加 Human
self-authored 写入 Agent PCR 的例外。仅在独立验证 accepted immutable provision、原 Agent PCR／
完整 Account／同 Station、当前 controller binding／lifecycle、实际 Human 设备授权及该具体
MLS 动作的 control delegation 后，才可使用本窄角色。history_custody 批准本身不是写权限；
普通 Realm／Circle／Sidecar／Direct 不适用此例外。

此角色的 MLS BasicCredential、Genesis 唯一 leaf、Member sender、External path leaf、
creator_leaf_authority.endpoint／authorization_event_ref 和内容 C_item.producer 均绑定
`actual_signer`，即 controller 自己的完整 Human Actor／真实 Device 授权。Event key 与其 MLS
leaf key仍可独立，但须原签绑定；外层 Agent control authorization_ref 与 controller 的 Device
authorize ref 职责独立。不得构造 Agent credential、预写 runtime key、克隆 runtime MLS 私态、
把 controller key 当 Agent runtime key，或仅因 executed_by 存在就放宽普通 scope 的 sender 验证。

合法顺序是：controller PCR 接受 provision／history_custody；创建同 Station 原 Agent PCR；
controller 以自己的 endpoint 创建其 epoch-0 group，提交 Agent＋executed_by 的 Genesis，
再将导出的首根按 Agent subject／当前 custodian policy 密封上传；充分根包耐久后才接纳首个
encrypted_private_fields 原件。最后用真实 pairing 授权、KeyPackage、Add／Welcome 接入独立
runtime。各步保存 exact intent／原件，失败续接原步骤，不重新 provision、换 PCR 或要求 runtime
预先存在。非依赖控制 metadata 可先提交；服务端从不持有 R 或任一 endpoint 私态。

名册和全 scope 库存必须按原 Genesis／Add／recovery 事实中的实际 endpoint Actor 归属，
不能按资源 Event.actor_id 推断。Human 全设备丢失时，库存包含该 Human 在所有受托 Agent PCR
内的 controller leaves（含空群），用其原生 Human RecoveryTransaction replacement 恢复；
治理方另核当前 Agent control delegation 与上述窄角色，允许原 group 的 External／Remove 收尾，
不要求不存在的普通 Realm member 行。只移除被替换 Human endpoints，保留独立有效 runtime；
Agent runtime supersedes 则只清理相应 Agent endpoints，保留合法 controller leaves。
两类恢复的原件来源、fresh PoP、库存／exact base CAS、全发送者屏障及新根隔离规则均不减少。
recovery_source、producer fact 和 roster 公钥绑定实际签名者，并通过完整原 Event／Commit
保留 Agent 资源 Actor 与 executed_by 的原签关系，不添加另一种身份或把 Human fact 伪装为 Agent。
Agent 自己的 history_recovery 检查点仍由对应 replacement runtime 自签，controller 不能冒签。


保留R意味着该epoch可恢复，不能同时声称逐条key密码销毁或MLS原生逐消息FS。
旧端已缓存的旧历史无法远程擦除；新R及新备份对仅持旧日常私态的端隔离。
24词本身泄露按key-management §3.3独立策略处理；无预先独立策略不能保证原DID安全恢复。
服务必须履行完整加密恢复集保管；暂时不可用就重试，缺材料是故障而非合格部分成功。
所有存储副本均毁损时seed不能重造字节；这不允许正常PCR写入留备份缺口。

## 7. 验收与实现声明

正式shape／KDF／签名／AEAD向量和mutation gate见`content-history-fixture.json`及
`tools/test_content_history_contract.py`。这些验证协议字节和负例，不替代独立Station、真实PCR全原件、
存储故障、generation／跨scope屏障和客户端重启恢复E2E。实现未完成不得宣称产品支持。

消息context的protection以原签认证root_refs、blob_refs、backup_refs；接纳前核对所有依赖耐久，root索引须在KeyBackup公开contents中与解密条目一致。缺依赖零提交。附件按media-and-blob §3.0从同一R派生；grant以source_event_ref＋content_path精确选择正文或附件。

向量：`ak.vector.crypto.content_history.v1`。

### 7.1 恢复leaf的原件来源

External Commit的path leaf不是KeyPackage Add，不得伪造claim receipt／consumed Add ordinal。
roster_record增加closed recovery分支：保留原始公开Commit Event、covering RealmCommit及exact minimal
historical producer signer fact。核原Event ID、Commit event_ref／stream／position、producer_signer_fact_digest及
原producer签名，binding、Actor、current替换授权和RFC path leaf／BasicCredential／signature key必须逐字段一致。
recovery Event不得含无关semantic_refs／external_ref；此窄披露仅提供群安装所需公开握手和最小fact，
不开放PCR历史或业务plaintext，也不改普通history floor。缺原件／fact保持revision_unavailable，不用current key补齐。

own Station按§9.1验证原origin service的完整method-native历史、exact recovery_source、fact承诺及原producer proof，self roster响应对每个recovery
record按原顺序给一个record_digest绑定的recovery_signing_keys公钥；没有recovery record不得返回额外key。
客户端必须再核该key与replacement／RFC path key相等并验证原签，不以manifest或一个verified布尔替代。
历史Actor／授权资格按原接受cut验证，当前披露资格仍按原有self／peer roster读取门；source事实不授予新membership。
该补充不修改Add记录的双issuer签名、method-native冻结closure及分页2MiB／1..8记录约束，
新记录与self公钥投影必须一起计入原预算；恢复之后的普通Add继续原合同。

Agent恢复记录使用authority-commit-operations的agent_runtime_historical_signer_fact最小原事实，源于原接纳时已完成的native Agent authority校验，须匹配原Commit的producer_signer_fact_digest；该事实本身不证明授权，own Station必须验证§9.1原始冻结来源，缺失就失败。不得公开controller私有requested scope／PCR历史，不以当前DID key代替旧key，也不将Agent伪装成account_device或Service。

## 8. 历史根领取、policy轮换与Agent备份主体（normative）

### 8.1 原创建资格与当前领取资格分离

新增内容根envelope写入、active-series更新仍严格检查current writer／generation／policy。
历史读取有一个窄例外：在现有逐object unlock中，新的current_device proof可携content_history，
其source是目标主体PCR中已accepted的原CommittedEventRef，root_refs是该原件原签protection的非空子集。
服务按原cut核Event／RealmCommit、scope及backup_refs，核所选envelope公开root索引确实覆盖这些root，
并确认原件／根仍属于完整PCR恢复集。原始backup ref可以定位原包，
受保管的同root_ref／root_context经当前series原签登记的充分recipient替代包也可领取，
不得为重封装改写原Event；原包删除前替代映射和包必须已耐久且经客户端核原root_ref。不得把调用者自报ref或任意旧series当成依据。

该分支按envelope创建时的原签者、原generation／policy／recipient验证，不因之后generation推进、
普通policy版本更新、原writer正常撤销、active pointer切换而抹除已经accepted的历史事实。
当前reader必须是目标Account当前accepted device，或§8.2明确的当前controller device；
其当前授权、generation、policy、custody及原件可读权每次均重查。原24词能打开保留的根，
不等于拥有当前API权限；旧设备、旧recovery session、过期／已消费challenge继续拒绝。

issue_unlock_challenge请求、响应和unlock proof必须逐字段绑定相同content_history及可选subject_actor_id／
custody_authorization_ref；不可删除、补默认或在普通分支重放。相同request_id只允许完整canonical请求的exact重放；
subject／custody／content_history变化必须幂等冲突，不返回或重绑旧challenge。每次用fresh challenge／nonce、TTL<=300秒，
消费与返回immutable对象结果同事务。此读取不消费或重开已完成的identity RecoverySession，
因此identity unit完成、900秒session到期、进程崩溃后，新current device可继续用新challenge逐对象恢复。
本分支不计普通64对象／24h桶，受正常authenticated read速率／并发／字节预算和审计约束；
不得通过额外永久restore lease、无限batch或session TTL使合法全PCR恢复不可完成。

只允许将选中的content_epoch_root导入history-only lane。envelope内其它旧items不能据此成为current
signer、policy、设备目录或active MLS state。查询PCR原件及其保护依赖复用现有scan／get／Blob读取；
正常active数据读取仍适用§7.6 freshness，不泛化此例外。

policy轮换不得使当前24词丢失全部旧根。若更换backup HPKE key／24词，先发布含旧新recipient的
accepted重叠policy，再逐块重封装所有仍受保护PCR根并核完整coverage，最后才发布撤销旧recipient的后继policy。
最终当前24词切换与充分恢复状态只在该覆盖核对完成后生效；不能先宣称新词充分再best-effort补材。
若只更新policy版本且backup key不变，历史包按原policy验签解封即可，无需重写旧密文。
怀疑24词泄露的紧急撤销仍依key-management §3.3独立安全策略；未完成的重封装保持明确pending，
新epoch根／新内容不得再向失陷recipient封装，不能用旧根保留推导新根访问权。

### 8.2 同一组标准API中的Agent subject／controller caller

Agent完整Account和PCR从accepted immutable provision及原Station绑定派生。
list可选agent_id只能选择本调用者当前管理、同Station且有有效history_custody的那个Agent；
不能把DID裸值当授权，也不能选择foreign Station。省略时只读caller自身，Agent session仅可选自身。
返回active_series.account_id／control_realm_id属于选定subject，不属于controller；cursor额外绑定caller、
subject、custody ref、current controller generation和原过滤条件，撤权后不得继续分页。

跨主体challenge／unlock的account_id、requesting_device_id与签名key始终属于authenticated controller，
subject_actor_id与custody_authorization_ref必须成对存在且精确等于目标Agent和原provision Event。
仅current_device分支允许它们；recovery_session分支禁止。controller换设备先完成自身正常身份恢复，
再按其新的current device资格领取Agent原件／根；不把Human助记词或私钥交runtime。
同一current custody允许现有self scan／get／Blob路径读取该Agent PCR的保护原件及必要来源，
不授予controller其它业务Realm、其它Agent或Human scope读取权。未知、异主、撤销、无custody目标统一not_found。
此跨主体读取逐kind登记于pcr-exposure-registry的
`ak.pcr_exposure_policy.current_agent_history_custodian.v1`；只适用accepted agent_control provenance，
PCR共享allowlist不构成其它主体的读取许可，返回保留原Event及covering RealmCommit签名。

Agent根envelope必须有custodian_actor_id／custody_authorization_ref：
controller上传以其current accepted Device签完整Agent-subject envelope，device_authorize及可选source_commit_ref
均在custodian PCR验证；runtime上传以signature_proof.agent_authorization_event_ref绑定其当前原生Agent授权和
verification_method，禁止device_id／device_authorize／source_commit_ref冒充Human generation。
二者都验证原provision、当前Agent lifecycle／controller binding、所选recipient的current custodian policy，
runtime还须有明确备份操作scope且仅能追加Agent自己的密封根。
本custody的每个根块只允许该Agent PCR的root_context，不得混入其它业务Realm、其它Agent或Human根；
不能靠请求只选择一个获权root就把同块其它scope根泄露给controller。其它scope必须另有其自身显式披露依据。服务不取得解密key。

Agent active-series只由当前custodian Device签署，记录同一custodian pair；
其ak.key_backup.active_series Event落Agent PCR：actor_id为完整Agent Account，executed_by为custodian，
authorization_ref核原生Agent control delegation且与provision/controller一致。该条件分支按现有capability_gated
验证受托PCR control权，不要求runtime授权或通用Realm管理员权；Human自身分支仍self_authored_proof，错配零接受。source_commit_ref是custodian PCR
的真实Device generation锚，不能伪造Agent generation。runtime不能改active pointer或recipient；
在已选series中追加只检查其native current authorization与predecessor CAS，无需controller持续在线。
原writer在创建时的授权用于历史验签；当前runtime supersedes／Human device fence只阻断新的写入。
controller policy本身撤销则当前领取仍拒绝；解除日常runtime授权不撤销immutable account custody。

### 8.3 root索引及保管不可被普通删除旁路

普通item公开索引精确为item_kind／secret_id；content_epoch_root另必带root_context／root_ref，
解封后按完整索引投影逐项核对，重复secret_id、额外／遗漏root、错context／root_ref都失败。
完整envelope签名覆盖所有索引；保留既有AAD构造，根值及索引的正确性须再以root_ref／原protection核对。
每个首次原生PUT已接纳的content_epoch_root必须有可用的充分recipient包，不以已有accepted PCR引用为条件。
普通DELETE／retention／series轮换、待决失败或来源过期不得删除最后一份必要包；同root_ref替代包必须先耐久且可由当前24词解开。
recipient轮换及根包删除与该完整根索引使用同一原生互斥边界，覆盖从首次PUT起的全部根，不能只查已成功Event的引用。
旧包可在充分替代后删除密文，但首次索引／原签引用到充分替代包的绑定须继续可验证，不新增查找API。
账号正式终止／擦除是独立生命周期，
不能把主动清空恢复集描述为仍可完整恢复的正常账号。

## 9. 恢复名册的唯一收集／排序合同（normative）

完整records数组首先是唯一accepted MLS Genesis，然后按accepted Commit stream_position递增处理：
普通Commit按原Proposal ordinal追加其历史Add记录；恢复External Commit先追加唯一recovery记录，
它不得混入普通Add（RFC握手要求之外的其他成员／policy变更拒绝）。同一Actor的后续清理Commit
若仍是Member sender，不重复追加recovery记录，也不伪造Add记录。
recovery记录的原Commit、covering RealmCommit和source fact必须独立核原签、exact base／epoch、
已接纳replacement及RFC PublicMessage UpdatePath leaf／BasicCredential／signature key，不能只凭manifest。

为使后加入客户端能验证原RFC恢复握手，recovery记录另必带`base_group_info_ref`与
`base_ratchet_tree_ref`，逐字取自`commit_event.payload.base_group_state_ref`所指exact accepted
Genesis／Commit原payload。治理方签发前及own Station投影前均须独立核对该原base、epoch和refs；
不得用恢复后的GroupInfo／tree、当前tree或调用者自报值替代。两refs在完整record_digest及manifest摘要内。
客户端从已验证record的base ref／previous_epoch／这两refs与原manifest的caller／target cut构造既有
self group-state-material请求，取得digest-bound原base GroupInfo／tree并验证原RFC External Commit
signature、path、BasicCredential、replacement key、AAD binding和继承的extensions；不要求在业务history
floor之前另行公开base Event或PCR历史。该窄公开握手物料仍受相同current／target cut披露门，缺原件则
revision_unavailable；不能仅解析path字段就宣称独立RFC验签成功。两refs及self投影均计入原分页预算。

records_digest=sha256(JCS(完整有序records))，record_digest=sha256(JCS(该完整记录))。
self wrapper唯一字段顺序为roster、manifest_signing_key、add_signing_keys、可选recovery_signing_keys。
Add rows按页内Add顺序一对一保留双签key；recovery rows按页内recovery顺序一对一返回原producer raw key；
没有recovery则禁止该字段，有则必带非空数组。任何额外、缺项、重复、错digest／key拒绝整个安装。
每页仍取同时满足peer和完整self编码<=2MiB的最长1..8条连续前缀，预算包括两类key投影及全部wrapper／cursor。
客户端收齐同一manifest所有页，重算records_digest，核每条原来源与RFC leaf后才能安装。
Member PublicMessage按RFC核membership MAC；恢复NewMemberCommit没有Member MAC，不能伪造或要求不存在的MAC。
这些规则替代仅收集Genesis／Add的旧算法，Add原双签与native authority责任不减少。

### 9.1 独立origin来源，禁止公开Agent私有权威闭包

恢复握手的MlsCommitSubmission在origin Account Station完成current native replacement校验后，由该Station生成
recovery_source，包含exact recovery_source_attestation及在attested_at冻结的完整authenticated_service_resolution。
原客户端self提交禁止自报该字段；origin同事务保留它与outgoing intent，然后以既有peer MLS submission转发。
本地治理时同一Station仍须生成并保留同样的原件。peer缺它、来源Station与Actor.account.station_id不符即零接纳。
原Actor Event先冻结ID；source仅在submission wrapper，不进入该Event preimage，不形成自引用。

attestation按UTF8("ak.mls.recovery_source.v1\n") || JCS(attestation删除signature)签署，复用标准Ed25519 service签名形状。
必须逐字绑定Event ref、完整replacement、scope、base、previous_epoch、inventory_digest与原verification_method；
origin签署时原Event ID、endpoint、授权实例和公钥均已冻结，不预签尚未由governor确定的committed_at或最终fact摘要。binding.authorization_event_ref必须等于replacement.authorization_event_ref，
binding.base_group_state_ref及expected_epoch必须逐项等于原payload的base_group_state_ref及previous_epoch；scope/current membership仍由governor独立核验。原接纳时TTL<=300秒，attested_at <= committed_at < expires_at且expires_at-attested_at在(0,300秒]内，
签名method在attested_at须属于该Actor owning Station且获assertionMethod／Station服务角色授权。
重试保留完全相同source；终局未知先对账，不能重绑到新Event或新base。

roster recovery记录保留完整recovery_source，origin_resolution不是当前路由。own Station独立验证该原origin角色、
同core、已登记方法版本、完整历史及原签，核source与原Event／binding逐项一致；
另核covering RealmCommit的producer_signer_fact_digest等于SHA256(JCS完整原fact))。
原fact的Event、完整Actor、实际method、公钥和authorization Event必须分别等于source／replacement，
Human还须核DeviceId；fact.accepted_at等于该Commit.committed_at，原授权在source时有效。
再验原endpoint producer签名及RFC path leaf。
这不是接受governor manifest代替原作者或origin来源，也不把最小Agent fact单独当作授权。
Agent私有requested_scope和PCR闭包只在owning Account Station按原native门验证，不向其它成员Station公开；
其它成员Station核上述独立origin原签来源，不能用当前DID key或向controller重新取私密scope补历史。

Agent恢复采用authority-commit-operations的agent_runtime_historical_signer_fact闭合分支，原接纳后入
RealmCommit.producer_signer_fact_digest；该联合新增第六分支而不把Agent伪装成Device或Service。
历史安装使用该原fact、origin source及原签；没有这组来源就revision_unavailable，绝不TOFU。
若原Commit用commit_message_ref，按当前／target cut授权的roster可经既有Blob读取得该精确公开Commit Blob，
先核typed ref的digest suite和原bytes，再解析；此窄读取仅允许已授权原roster引用的公开握手，不开放历史业务Blob。
无需在record复制另一份wire，也不能从缺证据的当前tree猜原path。所有source／resolution及self key均计入2MiB预算。

## 10. 安全库存、收尾结果与私密Blob（normative）

recovery_inventory是closed canonical preimage，inventory_digest等于
sha256(UTF8("ak.content.recovery_inventory.v1\n") || JCS(inventory))。
entries按JCS({effective_scope,genesis_event_ref})的unsigned UTF8字节升序、同pair唯一；old_leaves按leaf_index升序唯一，
endpoint必须与冻结原RFC roster的Actor／原授权实例／签名key完全相符。每个目标scope即使无内容或旧leaf已不存在，
也必须保留entry（可为空old_leaves）；禁止只由非空root库或本机缓存枚举。

完整性来自own Station从首次Genesis／Add／External Commit开始的durable admission／claim／consume／
outgoing-intent与accepted结果账本。origin在转发或发claim前先耐久登记exact目标，governor只接纳有该来源的入群；
claim原意图按device-lifecycle §9.0.1同时保存原签effective_scope、intended_realm_id与mls_group_id，
两端校验其同一目标绑定。尚无Welcome／consume的意图仍有完整scope定位；定位不证明已激活或已无旧leaf，
不能从单向group ID反解scope、默认Realm或以claim终态替代原件／winning结果对账。
结果沿既有committed replication／outcome对账冻结确认。恢复fence和该账本枚举在同一actor锁序下，
此前pending admission须先对账或阻断接受，之后旧授权不得新增scope。不得以新建版本或旧数据兼容豁免漏记空群。
服务不能把无法确认的遗漏报告为完整；这不是开放unsupported first-device PCR全历史验证分支。

rekeyed／removed首次结算据同锁cut已验证RFC tree重对库存中的原endpoint provenance，再清理所有匹配旧leaf；历史续读按§10.1验证原cut，不重套当前成员资格。
不能盲用曾经的leaf index删除已换成其它Actor的新leaf。base变化重新CAS／生成新binding，原库存承诺不改，
已不存在的旧leaf以真实原生结果（含§10.1原签removed证明）确认，不伪造Remove。cleanup_inventory.scope_cleanups与库存entry一对一同序，
每项为closed `scope_cleanup`：`rekeyed`携实际winning Commit、remaining_old_leaf_count=0、新根及充分备份引用；
`removed`或`terminated`仅携§10.1的原签retirement_proof。前者证明全部被替换endpoint已移除，后者证明原scope不可逆终止，
不伪造剩余leaf计数。不能因失去membership删掉entry，亦不能为补齐根引用向失权主体交付新根。
cleanup_inventory_digest=sha256(UTF8("ak.content.cleanup_inventory.v1\n") || JCS(cleanup_inventory))；
missing／重复／错序／scope错配、rekeyed／removed中任何旧leaf残留或无效终止证明都不允许ready。

inventory与cleanup preimage分别以原JCS字节存私密content-addressed Blob；history_recovery的inventory_blob_ref／
cleanup_blob_ref指向它们，ready时二者必带。只用既有Blob读写及Range，不新增未登记endpoint；
原RecoveryReceipt是身份unit之前签署的终局意图，不携content_recovery，也不得事后修改。
替代endpoint以自身current native key在自己的PCR提交原签ak.mls.history_recovery检查点，payload为history_recovery，
原签key必须等于inventory.replacement签名key，Human和Agent都不允许其它设备替它声明ready。
该subject-only私密控制metadata不依赖待清理的应用加密状态，不授业务明文写入权。
coordinator按已完成的identity／pairing原件及当前exact replacement资格，耐久固定Blob引用、摘要和subject；
既有Blob读取门仅允许该subject当前holder
或有效Agent custodian按相同current-device门取这些原签检查点引用，禁止匿名／peer公开或仅凭Blob ref读取。
该授权只涵盖库存材料，不继承其中其它scope的内容读取权。客户端核检查点的原producer proof／accepted RealmCommit／exact subject、Blob digest及
带域摘要，再按结果分支从现有原件／roster／winning Commit、§10.1原签终态证明和账本来源核全量结果；
失权者仅消费窄证明，不为验证收尾读取完整roster。bool和digest本身都不是完整性证明。
preimage可流式解析／散列，不截断账户的scope总数，也不为缩小receipt把未确认scope丢弃。

### 10.1 失去参与资格的scope收尾（normative）

本节仅处理已prepared原生episode的完整固定inventory，不产生membership、管理员权、历史权限或新episode。
scope_cleanup保持rekeyed／removed／terminated三态；仍有参与资格的目标首次收尾走§5的rekeyed。
资格包括§6.1原Agent PCR controller窄角色，不能仅因无普通Member行误判退群。
本节先检查当前reader，再区分首次签发与已有终局续读；不能把当前群成员资格当历史证明的读取门。

**终态与保密边界**：removed证明在其首次终局cut全部被替换endpoint已实际移除；terminated证明原scope依据登记生命周期
不可逆终止。terminated允许保留旧leaf，但原group从该终态起永远不得再接纳业务密文、新epoch内容或新R，不得restore、
重铸同group或由successor复活原group。archive／freeze／暂停／断连／无在线成员／治理站失联／缺树均不是终止证明；
不激活禁止提交的ak.realm.destroy。Circle／Sidecar派生终态须核真实上游accepted来源，不能伪造子scope tombstone。
既有历史根保管与充分重封装仍按§8执行；后两种终态不交付root、backup、完整roster、其它成员详情或业务原件。
无法核实实际移除或合法不可逆终态保持pending／明确不可用，不猜测完成。

**当前reader与正式入口**：self命令`ak.self.mls.command.reconcile_recovery_scope.v1`
（`POST /_arkret/self/mls/recovery-scope-cleanup`）的closed body字段顺序为authorization_event_ref、inventory_digest、
effective_scope、genesis_event_ref、nonce_base64url、delivery_challenge_base64url。前四项只选择原生episode及其exact entry；
不能上传inventory或选择另一replacement。只允许该subject当前native holder，或§8.2当前明确Agent custodian。
每次调用重核当前endpoint／generation或Agent授权、episode、subject及custody；候选、旧端、旧episode、异主与未知目标统一not_found。
未prepared为failed_precondition。该门与历史cut的群资格独立，曾在群内或持有旧proof不授当前API权限。
两个base64url字段都是canonical unpadded的32-byte CSPRNG值：nonce_base64url是本业务意图的稳定身份，
delivery_challenge_base64url是每次新观察／交付的fresh challenge。首次请求前耐久保存它们及完整body，不另携Idempotency-Key。

**两层幂等与稳定I**：两个self／peer命令均登记canonical_hash／full_body／retry_safe=true，完整请求SHA256、
principal／operation作用域、24小时下限及同identity异body冲突严格遵守api-conventions §6，不以nonce标签代替内容哈希。
内层另按完整subject、replacement.authorization_event_ref和nonce_base64url唯一结算原生意图；这是恢复安全账本，
独立于外层请求缓存，须随episode／原证明与fence持续保管，不能在24小时后丢掉终局或重新执行已完成收尾。
I唯一为closed对象`{replacement,inventory_digest,inventory_entry,nonce_base64url}`，
request_digest=`sha256(UTF8("ak.mls.recovery_scope_cleanup_request.v1\n") || JCS(I))`。
同内层身份对应不同I须duplicate_conflict、零新效果；不同scope、entry、replacement或inventory不能借重试换绑。
最小意图预留与scope业务效果分开：own Station在当前reader、prepared exact inventory与请求结构均合法后，
须先在subject／episode／nonce锁序原子耐久固定完整I，再派生／签发任何peer来源；该表跨全部目标governor唯一，
不得用每个governor各自的局部表代替。governor在当前来源与原生目标资格核实后也保管同I绑定，先于首次参与资格判定。
首次领域failed_precondition仍保留该最小预留；预留本身不安装endpoint fence、scope义务或业务屏障，也不是cleanup终局。
原外层body／challenge的拒绝观察保持不变；fresh challenge仅可继续同I，不同合法业务意图必须生成新nonce。
当前认证、来源窗口、exact inventory或原生目标来源未通过时不得创建该层意图；暂不可用不伪造业务终局，
但已合法耐久的最小预留不能因后续临时失败、超时、崩溃、24小时缓存到期或合法handoff被遗忘。
目的governor、交付challenge、method／有效期／签名和origin_resolution均不进入I，但始终受完整外层body哈希及各自来源签名认证。
刷新这些字段形成新的外层请求，内层仍对账同一I；不得静默删除通用幂等的完整body比较。

**当前原生来源**：own Station由prepared episode和完整账本取replacement／exact entry，先核当前reader再解析当前合法governor，
以peer命令`ak.peer.mls.command.reconcile_recovery_scope.v1`（`POST /_arkret/peer/mls/recovery-scope-cleanup`）
发送closed recovery_scope_cleanup_source：仅attestation及完整冻结origin_resolution。客户端禁止自报来源。
own Station在首次peer发送前，须将派生的完整peer body及其self请求／内层身份／challenge绑定原子耐久；
崩溃重启或self exact retry复用原签来源，不重新签发同challenge。未发送的过期来源也不能原地改签，须明确失败后由fresh challenge发起新观察。
attestation字段顺序为replacement、inventory_digest、inventory_entry、destination_service_id、predecessor_authorization_event_refs、nonce_base64url、
delivery_challenge_base64url、verification_method、attested_at、expires_at、signature。
来源由replacement.actor_id.account_id.station_id的原生保管Station签发；§6.1绑定实际Human replacement，不按资源Agent猜Actor。
predecessor_authorization_event_refs为本Actor在该exact scope／genesis关联的未完成前序恢复授权Event ref集合，按canonical字符串UTF8升序唯一；
完整原生census没有关联时必带空数组，不能省略或截断。own Station在最小I预留时同时冻结该关联；它不进入四字段I摘要，
但由完整source签名及外层body绑定，同I的fresh来源也不得改此集合，换绑为duplicate_conflict。原生义务后来已满足不重写该冻结集合。
签发该source即由原生授权唯一保管origin明确证明：逐项前序授权已被本replacement的合法完整generation／supersedes链替代；
完整私密身份原件、因果链及其验证留在origin，不要求governor另取Human／Agent私密PCR。governor验证完整Service历史和该原签声明，
再与自己保管的同Actor／scope／genesis前序source与义务逐项关联、核全本地安全覆盖；未知引用、来源缺损或遗漏本地未满足义务不回落为无前序。
这些引用只在受认证的own Station与该目标governor间流转，不进入普通roster、self终态证明或公开日志。
即使Actor仍有参与资格、窄retirement命令返回failed_precondition，已验证的该source与最小绑定也须保管；
后继正常rekeyed在发布完成前使用它核前序关联。没有这份具名签名来源时不得用裸bool或新时间替代跨站因果资格。

核原Human recovery unit或Agent完整supersedes／activation、原scope参与账本及当前请求资格；只携本entry，不携其它scope库存、
PCR cut／原件或Agent私有requested scope。signature为标准Ed25519 service形状，kid等于verification_method，
签名字节唯一为`UTF8("ak.mls.recovery_scope_cleanup_authorization.v1\n") || JCS(attestation删除signature)`。
origin_resolution按attested_at验证method-native Station服务角色、原签及同core；不能以当前DID、公钥自报或一个verified布尔替代。
在原生准入cut要求attested_at<=now<expires_at且有效期在(0,300秒]内；writer等待后也重核当前资格与有效期。
peer还须通过Service HTTP认证，实际caller／来源Station／replacement.actor_id.account_id.station_id相符，destination为当前governor；
治理方独立核原group／scope／genesis、accepted entry basis及自己账本中的原endpoint参与事实。无此原生参与来源不得受理。
同Station也执行相同门；各服务仅经登记网络接口调用，数据库、配置、私钥和后端函数继续隔离。

**首次签发与内层CAS**：当前认证／来源／reader及原生目标门通过后，在同一原生scope／Actor锁序先保管／核对最小I预留，再查询业务终局。
同锁先核本challenge已绑定的来源及观察：异来源为duplicate_conflict且零新增效果；已有观察按后述缓存规则返回，
即使内层已完成，也不得把旧pending改为终局。以下结算只适用于尚无观察的新challenge，不能先执行效果再发现challenge冲突。
已有终局则取原proof，绝不重新执行首次成员资格、Remove、换根或临时业务屏障；原Actor后来合法重新入群仍可续读。向外完成交付仍须通过下述关联前序义务满足门。
没有终局时才检查本次首次签发的有效参与资格：仍有资格为failed_precondition，零新增收尾效果；该Actor应走§5。
失权者登记episode对被替换endpoint的单调fence和待决义务，完整对账已签发／claim／consume／outgoing admission及winning结果。
集合来自原生恢复资格和完整账本，不能只看entry.old_leaves、旧index或裸pub；fence拦截包括尚未过期来源在内的旧授权再次Add。
核当前RFC tree的原endpoint provenance，保留其它Actor及未被supersede的合法endpoint。旧leaf仍在或相关准入未确认时仅返回
`{state:"pending"}`；合法MLS endpoint沿原权限提交repair Remove，命令不能替成员生成Commit或给replacement扩权。
全部旧endpoint实际移除、所有复活路径终结／fenced后才签removed；terminated同锁核不可逆终态及永久禁止原group新内容／新R。
原事实、首次exact来源和完整历史method、单调fence、原proof及签署意图在同一原生事务耐久后才形成唯一终局；
proof.attested_at须落在首次终局实际使用的来源窗口内，不得先签证明再异步补fence。

**原证明与三态结算**：scope_retirement_proof的字段顺序保持schema：state、replacement、inventory_digest、inventory_entry_digest、
request_digest、effective_scope、genesis_event_ref、governance_station_id、governance_generation、scope_cut、group_state_ref、epoch、
nonce_base64url、attested_at、verification_method，随后仅removed携remaining_old_leaf_count=0，仅terminated携terminal_source_digest，最后signature。
原governor／generation、scope_cut和MLS结果按首次终局cut验证；后续current head、method轮换、成员重入或handoff不改写它们。
inventory_entry_digest=`sha256(JCS(完整原entry))`；proof签名字节为`UTF8("ak.mls.scope_retirement.v1\n") || JCS(proof删除signature)`。
外层scope_cleanup的state／scope／genesis与proof和entry逐字相符，removed／terminated禁止winning_commit、root_refs、backup_refs。
terminated仅公开terminal_source_digest，不公开上游PCR坐标。令T为closed对象
`{effective_scope,genesis_event_ref,terminal_event_ref,nonce_base64url}`，terminal_event_ref为原生私密保管的真实不可逆来源CommittedEventRef，
其余值取I；摘要为`sha256(UTF8("ak.mls.scope_terminal_source.v1\n") || JCS(T))`。T、原件和完整级联来源仅留原生私有审计，
不向ordinary／peer／self披露T或外scope引用，也不跨stream比较position。
proof.scope_cut始终属于目标scope；terminal_event_ref则为真实直接或已登记级联的上游终态来源，二者不要求同stream。
例如Sidecar的controller principal终态可来自其PCR，父Realm终态可使Circle／Sidecar派生终止；治理方须独立核accepted原件、
精确目标及完整原生级联关系，不能仅凭一个跨stream引用或合法签名推导终止，也不能伪造Sidecar tombstone Event。

**当前交付确认**：terminal peer响应固定为`{cleanup,delivery_attestation}`，cleanup为原scope_cleanup逐字不变；
即使两次交付由同一governor完成，也须有独立的fresh交付确认。它只在当前governor持同锁核原proof、原生来源与单调fence
确已保管／依法导入后签署，不以“旧签名有效”或公开handoff链本身代替实际native import。
delivery_attestation字段顺序为request_digest、authorization_digest、proof_digest、recipient_service_id、governance_station_id、
governance_generation、nonce_base64url、delivery_challenge_base64url、attested_at、expires_at、verification_method、signature。
authorization_digest=`sha256(JCS(本次完整来源attestation，包括signature))`；proof_digest=`sha256(JCS(完整原proof))`。
request_digest与nonce取同I，challenge逐字取本次请求，recipient_service_id为经认证的owning Station；gov／generation为本次合法当前任期。
标准Ed25519签名的kid等于verification_method，字节为`UTF8("ak.mls.scope_retirement_delivery.v1\n") || JCS(delivery_attestation删除signature)`。
本次source.attested_at<=delivery.attested_at<delivery.expires_at<=source.expires_at，交付窗口在(0,300秒]内；
receiver首次验收时要求delivery.attested_at<=now<delivery.expires_at。错challenge、来源摘要、audience、任期、proof或未导入fence均拒绝。
原证明历史资格与本次交付current资格分开核验；旧method正常轮换不撤销原签事实，当前非法governor却不能因持旧proof签新交付。

**交接、缓存及重试**：只在authority-commit-log §8.1／§8.2允许的原Realm发生合法治理handoff；Human／用户管理Agent PCR、
Direct及其它禁止类别不因本节新增迁移能力。新governor激活前必须实际导入本scope全部内层预留（含首次拒绝）、pending／终局、exact I、
首次来源／proof／历史methods、单调endpoint fence、前序义务／满足记录、未完成业务屏障及交付去重账本，继续原身份和原group。
handoff只改变新的签名路由和当前交付任期，不改变稳定nonce／I／原proof。新current governor用fresh来源及fresh challenge
签当前交付确认；原proof继续用首次任期的原key验证。未导入或来源缺损为revision_unavailable，不以cache补造确认。
own Station可缓存原证明及已验证历史来源以避免重取原件，但新的网络交付始终要求当前governor的fresh确认，不能只回裸cache。
当前governor不可达时新交付保持明确不可用；先前已合法接收并耐久验证的结果不因临时断连或交付TTL到期而自动倒退。
交付观察另按内层身份／delivery_challenge_base64url持锁固定本次authorization_digest及原观察；同challenge异来源attestation为duplicate_conflict。
即使内层后来完成，旧challenge的pending观察也不改写。任何非逐字节外层重试的后继观察若更改来源签名／有效期／路由，须fresh challenge；
仅更新同一原签source的等价历史resolution仍须独立native验真、形成新完整body身份，但不改变challenge已绑定的authorization_digest。
同完整外层请求的合法exact retry只返回原still-valid响应、原pending观察或确定性failed_precondition，不改写已缓存响应字节；
当前认证／授权及本次来源窗口先于cache命中。首次资格核验所得确定性failed_precondition也须原子固定为该完整body／challenge的原outcome，
不能在资格变化后用同body／challenge重算为成功；fresh challenge可在同I下形成新观察。revision_unavailable等暂不可核实原生来源的
失败不被当作首次领域终局，也不得笼统缓存全部异常。pending只表示尚未完成观察，不冻结内层终局；后续轮询使用fresh challenge形成新外层请求，
同I再次结算，已完成则返回同proof及新交付确认。响应／source过期后也使用fresh challenge与来源，新body不伪装成旧外层exact retry。
终局未知先对账同I，不能改nonce创建第二意图；不存在以超时删除native obligation／永久fence的路径。

**self消费与耐久进度**：self响应为delivery（原peer响应逐字不变）及terminal必带的attestor_signing_key、delivery_signing_key；
pending禁止两项key。前者为`{proof_digest,verification_method,public_key_base64url}`，绑定原proof历史签名key；
后者为`{delivery_digest,verification_method,public_key_base64url}`，delivery_digest=`sha256(JCS(完整delivery_attestation))`，绑定当前交付签名key。
own Station独立验证两种method各自时点的完整Service历史、合法current治理链／generation、源授权、原终局事实与本次原生交付，
再按exact digest投影两把公钥；不让普通客户端执行Service／PCR原生verifier或信任调用者key。
客户端从已绑定own Station消费，独立核原请求／episode／entry、I、challenge、两个摘要和两份原签；只有成功后才将cleanup导入私密cleanup Blob。
短效delivery不写入不可变cleanup preimage；它用于本次交付验收。成功验收的exact请求／响应、key投影、episode绑定、当时验收时间及已核来源／路由依据须耐久保存，
使重启可验证当时的合法交付，不用当前时钟否决历史验收；验证记录缺失时重新取得fresh确认，不能信本地自报verified布尔。
原证明持续依靠不可逆fence；ready前仍核当前episode和全部scope各自结果。不能要求任意多scope的所有交付都在同一300秒窗口内。
本窄native结果不是新的共享Event finality、membership或历史权限，消费分工与隐私例外见server-trusted-results §2。

**屏障及最终完成**：临时业务屏障以完整subject／effective_scope／genesis／replacement.authorization_event_ref逐episode登记，
它与永久endpoint fence、普通membership／policy／key-access门和terminal生命周期分别维护。pending时本scope全部业务发送者阻断。
同effective_scope／genesis／replacement.authorization_event_ref的原生收尾终局在rekeyed／removed／terminated之间互斥，
由同一scope／episode锁序与耐久结果账本协调。失权scope收尾命令pending后若Actor重新获参与资格，必须沿§5正常rekeyed路径，
仅在真实accepted RFC、零旧leaf及充分新根备份全部核实后，原子登记rekeyed终局并使该episode的pending retirement义务按此结果收敛；
保留原I／来源及旧body／challenge观察，不改写旧pending，也不伪造retirement proof或经窄命令返回Root。
已有rekeyed终局的episode不得再首次签发retirement，新的该类命令返回failed_precondition；后来再次失权也不覆盖已完成结果。
rekeyed／removed的原生终局事务直接解除本episode临时阻断，不等待客户端下载或全账号ready；其它episode仅可按下述逐项义务满足规则收敛，普通门继续。
removed不要求给失权者新根，实际Remove仍满足RFC的新epoch隔离。terminated永久禁止原group写入，不能通过清除临时阻断恢复。
endpoint fence始终保留，以上变化不推进key_access_revision，不增加其唯一写者。历史终局重读不重新安装已完成的临时屏障。

**连续恢复与前序义务满足**：已受理的安全义务属于原生scope账本，不以旧replacement继续在线、当前API读取资格、
来源TTL或恢复session存活为执行租约。新恢复E2可在E1尚pending时合法发生；旧episode继续拒绝读取，不以E2冒签E1、
重开旧授权、改写旧I、原观察或首次proof完成前序义务。原生worker仅维护已受理的安全义务，不借此新增Remove／Commit作者权限。
它可用依法已接纳的正常rekeyed结果或原生removed／terminated终局满足前序义务；没有安全结果仍保持pending／明确不可用。

治理方须在同一scope／Actor锁序逐项核验并原子耐久私有“义务满足记录”与对应屏障释放：

- 前序确有已受理未完成义务；完整Actor／Account、effective_scope与genesis精确一致，且保管origin按上述签名集合证明的E1→E2
  supersedes／generation因果关联（可跨多次恢复，完整私密身份链仍由origin原生验证），不能只凭较新时间、Event ref不同、同用户或同scope推导承接。
- 源终局属于该合法后继授权，已经按自身分支独立完成全部原生验证。rekeyed须真实accepted RFC、新epoch、充分新Root备份；
  removed须全部相关旧endpoint实际不在tree；terminated须真实不可逆终态及永久禁止原group新内容／新R。
- 覆盖前序完整原生endpoint集合及所有issued／claim／consume／outgoing admission和竞争准入路径，不只entry.old_leaves或当前leaf。
  rekeyed／removed须这些端全部实际移除且相关复活路径结束／fenced；terminated须所有路径均被不可逆生命周期门封死。
  全部前序永久endpoint fence继续保管，不能用后继自己的零旧leaf计数替代前序覆盖。覆盖事实须在源终局的exact cut成立；
  rekeyed绑定实际winning Commit，removed／terminated绑定原proof.scope_cut及真实终态来源，不能用后来current cut的安全事实补称旧cut已覆盖。
- 记录逐字绑定前序episode／I及义务集合、后继授权／因果链、源终局的exact摘要与实际accepted来源及覆盖依据；
  exact重复只读同记录，冲突为duplicate_conflict且零新增效果，缺原件或覆盖不足不释放。对多个前序逐项结算，未覆盖者继续阻断。
  若前序自身合法终局已在竞争锁序中先完成，则保留该原终局并视其义务已完成，不另造满足记录；两条路径不得互相覆盖。
  若前序已被另一合法episode的满足记录完成，也必须核验并复用原记录，不能为本后继重建一份不同来源／cut的记录。
  冻结关联仍列出该前序，既有完成事实使它不再需要新的满足写入；不能为避免冲突删除冻结引用或生成新nonce。

**已有满足记录的复用与写入分离**：完成协调和ready检查在同锁下逐项选择“原自身终局”“原已验证满足记录”或“尚待满足”路径。
复用须逐字核原前序I／义务集合及Actor／scope／genesis，原满足来源的后继授权、origin原签因果声明和当时完整Service方法来源，
原安全终局／exact cut、端点／准入覆盖及永久fence。原授权声明按原合法接纳时点和原key验证，不对旧episode重新开放API或要求其source现在仍有效。
记录与其原签来源、完整原生验证依据、accepted原件／引用须同事务保管；仅保存摘要、record key、verified bool或重算另一来源不足以复用。
当前治理方每次复用还须核真实current authority、记录／原件实际保管或依法完整导入、所有相关永久fence及准入关闭状态；
历史验证快照不能代替本次原生保管检查。缺损／未知／未导入为revision_unavailable并保持屏障，不以“已有记录”跳过。该门用于新的原生收尾／完成验收及交付，
不回溯推翻已合法耐久验收的历史结果，也不把离线重启续用变成新的completion lease。
核验成功仅消费原完成事实，原记录和旧观察逐字不变，不写成当前episode的新满足记录。显式尝试写入另一候选记录仍为duplicate_conflict；
“合法原记录复用”与“不同候选覆盖写入”是不同的原生操作，不能用后者的CAS冲突规则阻断前者。
当前后继自己的安全终局仍须在其exact cut核全关联集合覆盖；复用旧记录不豁免当前accepted RFC、隔离、充分备份和普通门。
一个后继满足多个前序时逐项选择并验证，任一不充分则不发布后继完成或释放未核实义务。ready与完成协调使用相同复用判定。
若原自身终局或原满足来源为terminated，原group的不可逆生命周期继续，不得支持终止后的新rekeyed／新epoch／新Root。
合法早于终止的rekeyed／removed历史结果不回溯改写；目标scope的旧winning cut可以等于派生终止证明的最后目标cut，
因为真实终态来源可能在另一个stream且没有子scope tombstone。只在同stream核目标cut顺序，不跨stream比较position；
当前terminal写禁独立保持，历史结果的验收不授现在写权。每笔新原生接受都在其实际接受cut核生命周期，不能用旧snapshot签发新写入。

所有winning／scope cut的exact committed ref均按authority-commit-log §3／§5的不可变Commit与exact四元组核原件：同commit_id不得更换Event、stream或position，
同Event／同stream position也不得被另一成功Commit替代。候选引用与native局部镜像相同不够，必须与独立核实的原生原件索引逐字段相符；
真实原件仍须重算ID、验签并核接受资格，schema形状、opaque测试ID或native已验证输入本身不替代这一步。

该记录仅是私有原生安全账本，**不是第四种scope_cleanup、旧episode的rekeyed／retirement proof或可移植读取许可**。
不将E2的Root、证明或授权替换进E1 cleanup Blob，不使旧episode重新ready；原历史proof／观察持续不可变，永久fence不删除。
满足记录及其原生来源与义务同寿命保管，崩溃重启及允许类别handoff必须实际导入；历史签名或内存bool不代表已导入。
治理方从已保管的accepted来源完成本地结算，经既有登记复制／对账合同协调，不访问其它服务数据库、私钥或新增私有接口。
后继库存prepare须从完整原生账本纳入前序尚未满足义务的所有精确scope（即使当前无leaf／已失权）；保留前序集合关联，
不能只枚举最新replacement的tree／root库。原先已经prepared的库存不改字节，前序义务通过独立原生账本关联并在ready门复核。
后继本scope终局的安全语义包含上述关联前序集合：治理方在相关满足记录耐久前，不得将该scope对外报告为本次恢复已完成。
本episode终局形成前就须核全关联前序集合在其exact cut的安全覆盖；不充分时不得登记该终局。满足记录可在该安全终局之后对账耐久，
但对外完成交付／own Station的完整cleanup验收须等待所有关联前序记录耐久；否则维持pending／明确不可用。不得复用早先覆盖不足的终局并以后来cut补证。
own Station按既有本episode三态结果及其分支原生来源完成验收，内部满足记录不增加wire字段、不公开前序私态，也不以未登记的跨站布尔回执补洞。
当前episode每项仍须自身合法三态结果及全部相关前序义务已满足，不能以满足记录代替其cleanup结果；原生来源未知时不得ready。
只有所有临时义务均已解除、普通门通过且非terminal，业务发送才恢复；不相关Actor、scope／genesis、无因果链或覆盖不足的episode不得随之清除。

ready仍要求PCR全部原件实际恢复且完整库存各项有有效rekeyed／removed／terminated结果；原缓存历史不可远程抹除。
该安全收尾不承诺24词恢复普通群全部历史；原retention与读取权限不变。声明支持本内容恢复策略的owning Station／governor
须实现上述登记命令与合同；schema／签名KAT／reference模型不证明native RFC、物理import、事务耐久或生产支持。


## 11. Coverage的确定性重建（normative）

coverage.genesis_event_ref是该PCR stream的原Realm create Event，区别于root_context中独立MLS Genesis。
输入必须是同一stream从position0至独立可信cut（含）的完整连续原件，source.EventId唯一，最后source精确等于cut；
不得跨stream比较位置。entries按position顺序，逐项从原件protection重建root／blob／backup集合，
每个集合按canonical wire字符串UTF8升序去重；公共控制原件可为空集合。
按全局ordinal精确每256项切页，只有末页可不足256；所有页用同一个cut／genesis／scope，
首previous_page_digest=null，其余为前页page_digest。每页backup_refs为本页原件backup引用并集的排序去重结果，
不是全历史并集或当前active series猜测值。页摘要仍为sha256(JCS(页删除page_digest))，head是末页摘要。
不得以另一种合法长度分组接受不同head；缓存可按上述唯一算法从原件完全重建，不建立第二套API。

### 11.1 内容根备份的唯一HPKE块格式

本节 Account／Agent PCR 的 content_epoch_root KeyBackup 必须仅含这种 item，recipient_method 固定 recovery_public_key；
Realm Actor 的独立 recipient method 及 AAD 由§3.2规定，不适用本节的 Account 24词凭证。此处
只使用default X25519/HKDF-SHA256/ChaCha20Poly1305；不得另有旧SSK／passphrase／日常device可解的recipient分支。
closed plaintext keybag整体作为单次HPKE plaintext，沿既有KeyBackup布局：
encryption.aead.enc是32-byte KEM enc，ciphertext是HPKE ciphertext || tag[16]，二者各用canonical unpadded base64url；
不能把grant的enc拼接格式写入KeyBackup ciphertext重复携enc；keybag元数据／索引必须与外层逐项一致。没有另一个未登记的DEK包装层。
info采用key-management §7.5.2完整metadata JCS，AAD采用§7.2唯一构造，nonce仅为RFC内部seq=0。
fresh ephemeral产生fresh AEAD key，旧端持有旧R／旧SSK也不能打开含新R的新块；相同当前24词backup key
只在可信controller／恢复端持有，不向日常端泄露。每个新块重新HPKE seal，禁止复用上下文或ephemeral。

### 11.2 进度原件与私密物料的读取

检查点pending必须cleanup_completed=false，带inventory_blob_ref、replacement、固定pcr_cut和实际coverage摘要，不得带cleanup_blob_ref或
cleanup_inventory_digest；ready则必须cleanup_completed=true、带完整cleanup引用与摘要，并且所有原历史实际解密验证完成。
允许多个后继检查点，但同一恢复episode的replacement／inventory／pcr_cut不变；只接受同current授权实例的连续进度，
不以较新时间戳、别的设备或旧episode的ready覆盖当前pending。Episode由replacement authorization Event唯一绑定，
不添加第二版本／profile。current holder经既有PCR scan/get找自己的该实例原件；Agent的current controller可依§8.2读取，
这只提供Agent runtime原签进度，不允许controller冒签为该runtime。group及业务仍须客户端实际验证后才可展示ready。

物料prepare时即在own Station按同一subject／episode设置私密Blob ACL，并绑定原identity/pairing授权来源；
不是先公开Blob再等检查点引用。Inventory从coordinator冻结账本产生，当前replacement可经普通私密Blob接口领取，
用其真实hash提交pending；其它Actor、旧端或未完成替换的候选无权领取。检查点不是新的远程历史权限oracle。

### 11.3 原生episode与首次物料发现

首次恢复端只需原identity／pairing结果中已有的replacement authorization Event引用，
经`ak.self.mls.content_recovery.resource.get.v1`读取自己Station的私密preparation资源。
HTTP为`GET /_arkret/self/mls/content-recoveries/{authorization_event_ref}`，没有request body；
不要求预先存在history_recovery检查点、另交Blob hash、选另一把leaf key或执行第二个公开prepare命令。
该GET只观察已经耐久的原生episode，不创建episode、推进generation或接受客户端自报库存。

Human的已接纳RecoveryTransaction terminal unit在同一PCR权威事务内保留episode／fence意图；
固定`pcr_cut`为该unit最后一条authorize Event的CommittedEventRef。Agent从实际supersedes pairing的
原authorize及原生activation结果保留同类意图，固定cut为该Agent PCR的原授权Commit；跨服务终局只经
已登记网络接口耐久对账，不把两个服务数据库当作一个事务。缺实际pairing／activation来源保持不可用。
在后台完整库存尚未准备好时，意图和并发fence已经生效；恢复后新membership／pairing及旧授权的
来源签发不得越过该fence造成漏项。符合本恢复episode的控制metadata、对账和安全收尾沿其窄授权继续。

replacement唯一取原生授权的完整Actor、Device或runtime endpoint、authorization Event及Ed25519公钥：
Human取原device authorize的device_public_key_did，Agent取原key authorize的public_key与verification_method，
不能把controller签署Agent authorize时的Human producer key当成runtime key。
这与§9.1原recovery producer fact公钥相等、§10检查点同key的合同一致；普通非恢复MLS leaf仍可使用独立key。
原生授权PoP与RFC External Commit的fresh path／signature PoP分别验证。
接纳replacement之前还须核完整旧日常授权及MLS签名pub排除集，包括已发布／已claim而尚未进入当前tree的
真实KeyPackage、Genesis／Add／Update和已移除端的原生来源；仅比较旧Device公钥或当前leaf不充分。
公钥来源须核实际Actor／原授权实例及原PoP，不能用未验证的声明值任意污染该集合；缺完整来源不能假称fresh。

资源使用`content-encryption.schema.json#/$defs/recovery_preparation`，字段依次为：

| 字段 | 合同 |
| --- | --- |
| `state` | `pending`或`prepared`，只表示库存物料的准备阶段 |
| `replacement` | 上述固定的原生endpoint；其authorization_event_ref逐字等于路径引用 |
| `pcr_cut` | episode固定的原PCR cut，不能在重试／后台进度时换head |
| `inventory_blob_ref` | 仅prepared必带；pending禁止该字段，不能发布部分库存 |

读取者须为该subject当前native holder或当前明确获准的Agent history custodian；Human使用Standard
Device绑定，Agent runtime须核当前原key授权，custodian仍核§8.2完整来源。候选、旧设备／runtime、
另一Actor、旧episode、匿名或peer请求均不得取得该资源，unknown／未授权统一not_found；
合法资源的必要原件缺损或不一致为revision_unavailable。远端义务未确认时返回pending并继续对账，
不以缺失目标、超时、过期缓存或空数组冒充prepared。该查询不授予库存所列其它scope的内容读取权。

后台coordinator只从§10完整原生账本准备一次canonical inventory；prepared后原Blob引用、
replacement及pcr_cut不可重绑，prepared不得退回pending。重复GET返回该episode的当前物料阶段；
新原生恢复授权开启新episode，旧实例结果不能覆盖它；前序未完成安全义务的库存完整性、关联及满足按§10.1继续，旧读取权不恢复。物料prepare时即绑定subject／episode私密ACL；
内容去重也不得复用公开Blob或其它主体的普通上传授权。资源及每次Blob／Range交付都重验current资格，
不能把已知Blob ref或曾持旧会话当作读许可。原签检查点仍由replacement自己提交，coordinator／controller不能冒签。

`prepared`不表示历史已解密、External／Remove已完成或客户端history-ready。客户端取得并核原JCS Blob、
带域inventory摘要与当前episode绑定后，即可按§11.2提交自己的pending进度；pending不以全部历史已到齐为前提。
ready须按分支逐项验证：rekeyed核相应原件／名册、accepted RFC与充分Root备份；removed／terminated仅核§10.1
窄原生证明及合法交付，不要求已失权scope的完整名册，也不由该证明获得业务历史。个人原PCR全部历史／coverage
恢复及全库存终局仍是ready的必要条件，原RecoveryReceipt不变。
若完整原生census证明从未激活任何MLS scope，inventory.entries和对应cleanup.scope_cleanups可都为空；
仍须保存真实私密preimage并完成PCR全历史／coverage核验。已激活但无内容或无旧leaf的群必须保留真实entry，
不得为凑非空数组伪造Genesis、leaf、External或winning Remove，也不得以schema／摘要能接受空数组证明库存完整。
