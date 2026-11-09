---
title: 可恢复内容加密与历史交付
status: candidate
normative: true
stability: v1
updated: 2026-11-09
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
目的governor、交付challenge、method／有效期／签名和origin_resolution均不进入I，但始终受完整外层body哈希及各自来源签名认证。
刷新这些字段形成新的外层请求，内层仍对账同一I；不得静默删除通用幂等的完整body比较。

**当前原生来源**：own Station由prepared episode和完整账本取replacement／exact entry，先核当前reader再解析当前合法governor，
以peer命令`ak.peer.mls.command.reconcile_recovery_scope.v1`（`POST /_arkret/peer/mls/recovery-scope-cleanup`）
发送closed recovery_scope_cleanup_source：仅attestation及完整冻结origin_resolution。客户端禁止自报来源。
own Station在首次peer发送前，须将派生的完整peer body及其self请求／内层身份／challenge绑定原子耐久；
崩溃重启或self exact retry复用原签来源，不重新签发同challenge。未发送的过期来源也不能原地改签，须明确失败后由fresh challenge发起新观察。
attestation字段顺序为replacement、inventory_digest、inventory_entry、destination_service_id、nonce_base64url、
delivery_challenge_base64url、verification_method、attested_at、expires_at、signature。
来源由replacement.actor_id.account_id.station_id的原生保管Station签发；§6.1绑定实际Human replacement，不按资源Agent猜Actor。
核原Human recovery unit或Agent完整supersedes／activation、原scope参与账本及当前请求资格；只携本entry，不携其它scope库存、
PCR cut／原件或Agent私有requested scope。signature为标准Ed25519 service形状，kid等于verification_method，
签名字节唯一为`UTF8("ak.mls.recovery_scope_cleanup_authorization.v1\n") || JCS(attestation删除signature)`。
origin_resolution按attested_at验证method-native Station服务角色、原签及同core；不能以当前DID、公钥自报或一个verified布尔替代。
在原生准入cut要求attested_at<=now<expires_at且有效期在(0,300秒]内；writer等待后也重核当前资格与有效期。
peer还须通过Service HTTP认证，实际caller／来源Station／replacement.actor_id.account_id.station_id相符，destination为当前governor；
治理方独立核原group／scope／genesis、accepted entry basis及自己账本中的原endpoint参与事实。无此原生参与来源不得受理。
同Station也执行相同门；各服务仅经登记网络接口调用，数据库、配置、私钥和后端函数继续隔离。

**首次签发与内层CAS**：当前认证／来源／reader门通过后，在同一原生scope／Actor锁序查询内层身份并核I。
同锁先核本challenge已绑定的来源及观察：异来源为duplicate_conflict且零新增效果；已有观察按后述缓存规则返回，
即使内层已完成，也不得把旧pending改为终局。以下结算只适用于尚无观察的新challenge，不能先执行效果再发现challenge冲突。
已有终局则取原proof，绝不重新执行首次成员资格、Remove、换根或临时业务屏障；原Actor后来合法重新入群仍可续读。
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
Direct及其它禁止类别不因本节新增迁移能力。新governor激活前必须实际导入本scope全部内层pending／终局、exact I、
首次来源／proof／历史methods、单调endpoint fence、未完成业务屏障及交付去重账本，继续原身份和原group。
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

**屏障及最终完成**：临时业务屏障以effective_scope／genesis／replacement.authorization_event_ref逐episode登记，
它与永久endpoint fence、普通membership／policy／key-access门和terminal生命周期分别维护。pending时本scope全部业务发送者阻断。
同effective_scope／genesis／replacement.authorization_event_ref的原生收尾终局在rekeyed／removed／terminated之间互斥，
由同一scope／episode锁序与耐久结果账本协调。失权scope收尾命令pending后若Actor重新获参与资格，必须沿§5正常rekeyed路径，
仅在真实accepted RFC、零旧leaf及充分新根备份全部核实后，原子登记rekeyed终局并使该episode的pending retirement义务按此结果收敛；
保留原I／来源及旧body／challenge观察，不改写旧pending，也不伪造retirement proof或经窄命令返回Root。
已有rekeyed终局的episode不得再首次签发retirement，新的该类命令返回failed_precondition；后来再次失权也不覆盖已完成结果。
rekeyed／removed的原生终局事务仅解除该episode的临时阻断，不等待客户端下载或全账号ready；其它并行episode阻断和普通门继续。
removed不要求给失权者新根，实际Remove仍满足RFC的新epoch隔离。terminated永久禁止原group写入，不能通过清除临时阻断恢复。
endpoint fence始终保留，以上变化不推进key_access_revision，不增加其唯一写者。历史终局重读不重新安装已完成的临时屏障。
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

含content_epoch_root的KeyBackup必须仅含这种item，recipient_method固定recovery_public_key，
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
新原生恢复授权开启新episode，旧实例结果不能覆盖它。物料prepare时即绑定subject／episode私密ACL；
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
