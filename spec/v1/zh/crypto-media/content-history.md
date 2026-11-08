---
title: 可恢复内容加密与历史交付
status: candidate
normative: true
stability: v1
updated: 2026-11-08
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

多个R可以批量封装在不可变块中；每个新块必须fresh随机块key。含新R的压实块不得复用旧端掌握的
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

## 4. 获授权后加入者

`history_access=all_history_for_current_members`必须有实际可读路径，不能只返回密文。
`since_join`是显式披露策略，其floor按完整Actor的合法join实例求值；同Account换Device或同Agent换runtime
不得改用新leaf的Add时间。普通Realm仍受当前membership、exact scope、policy与retention约束。

唯一共享历史key载体是原签durable Event `ak.mls.history_grant`，复用现有Events提交／scan／get，
其payload由`history_grant`定义。issuer须有当前披露资格和对应材料；recipient须有当前读取资格，
并与Actor／endpoint／HPKE key／授权cut／有效期逐字段绑定。该kind不授予membership、不修改MLS私态。
其payload是metadata及HPKE密文，不再套进依赖待交付root的应用信封。原签覆盖全部成员。

每entry的HPKE info与AAD均为schema所列closed header的JCS；default active HPKE suite，单发base mode，
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

复用既有policy-authorized RecoveryTransaction两Event原子unit，先推进generation、只授权replacement，
与session消费及current目录同事务提交，随后旧设备／session／队列／KeyPackage立即按旧代次拒绝。
基础policy恢复不要求current DID publication／updateKeys，不借unsupported first-device active-series分支。
下载历史只还原读视图，不能将旧snapshot／device authorize重新安装为current。

完整安全库存必须覆盖所有相关PCR／Realm／Circle／Sidecar／Direct的旧endpoint，包括无内容空群，
不等于非空root库。Join／Add／consume账本的登记及安全收尾须耐久；枚举与新membership／pairing有并发fence。
每个目标根据已验证的RFC roster实际Remove旧leaf，更新epoch／新根备份，保留其它Actor及合法成员。
各治理方收到收尾义务后保持全发送者业务屏障；未确认／不可达目标保持pending，不能以过期缓存跳过。
跨站收尾仅用已登记的participant／signer材料和Events authority-forward路径，不公开PCR历史、不给服务端私钥。
最终成功必须同时具有PCR全历史精确读取及完整库存每个scope的winning收尾结果；身份unit completed本身不足。
密码隔离保证从全scope收尾ready之后成立，不能谎称网络尚未确认的群已即时完成Remove。

恢复沿原group External Commit接入：仅在`mls_commit_payload.recovery_binding`有效、原Actor当前仍joined、
replacement授权已接纳、exact current base／epoch及库存digest匹配时允许new_member_commit／ExternalInit。
未授权外部加入继续拒绝；握手不创造membership。External Commit仍是RFC PublicMessage，后续Remove不可省略，
中间epoch禁止业务。所有winning Commit必须耐久签入新GroupInfo／tree refs，existing group-state-material读取
可以请求对应accepted Commit的公开材料，不再只限epoch0；仍按当前／target cut及恢复policy私有授权披露。
可恢复群的GroupInfo必须包含RFC 9420 external_pub扩展，并与同一accepted tree／epoch核对，不能只保留缺少ExternalInit所需公钥的普通GroupInfo。
同base仅一个CAS winner；恢复fence、原件、reserved材料及step结果耐久，崩溃后对账续跑，不清空义务。

恢复准入及后续清理使用同一current恢复授权门，不要求普通成员额外取得Realm管理员能力。
每个清理Commit仍带按其新base／epoch更新的recovery_binding；producer必须是已批准replacement，
Remove集合必须精确覆盖库存中该Actor尚存的旧endpoint，禁止删除其它Actor、普通Add／扩权或借机改变policy。
该窄例外仅允许完成已验证安全收尾，不等于给replacement通用ak.mls.commit管理权。
不同Actor的普通Commit、Add及非恢复写入继续原有capability准入，不能用恢复字段绕过。

## 6. 用户管理Agent与保密边界

Agent DID、完整Account、PCR、Station／controller pair和group ID不变。Agent备份主体始终是Agent。
Controller-signed `ak.agent.key.authorize.history_custody`显式绑定Agent PCR至controller完整Account的
accepted恢复policy／backup key。当前runtime授权只说明运行权限，缺该明确批准不得推定可解历史。
provision／配对完成前须安排完整PCR的保管；新runtime丢失后不能倒补不存在的备份。

跨主体KeyBackup携`custodian_actor_id`和`custody_authorization_ref`，后者核上述accepted current授权，
recovery_policy_ref／recipient_key_ref在该custodian的accepted policy中解析；不得仅信DID Document。
Controller可信客户端用自己的24词解Agent备份，仅将获准Agent根密封给经pairing批准的新runtime。
24词、backup私钥、Human其它scope及DID root不进入runtime。新runtime使用该同一fresh签名key接续原group。
旧runtime授权以完整supersedes／activation fence替换，不能套Human Device generation或创建新Agent。

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
historical producer signer fact。核原Event ID、Commit event_ref／stream／position、producer_fact_digest及
原producer签名，binding、Actor、current替换授权和RFC path leaf／BasicCredential／signature key必须逐字段一致。
recovery Event不得含无关semantic_refs／external_ref；此窄披露仅提供群安装所需公开握手和最小fact，
不开放PCR历史或业务plaintext，也不改普通history floor。缺原件／fact保持revision_unavailable，不用current key补齐。

own Station通过既有原件历史验证职责独立验证该记录的native producer证据，self roster响应对每个recovery
record按原顺序给一个record_digest绑定的recovery_signing_keys公钥；没有recovery record不得返回额外key。
客户端必须再核该key与replacement／RFC path key相等并验证原签，不以manifest或一个verified布尔替代。
历史Actor／授权资格按原接受cut验证，当前披露资格仍按原有self／peer roster读取门；source事实不授予新membership。
该补充不修改Add记录的双issuer签名、method-native冻结closure及分页2MiB／1..8记录约束，
新记录与self公钥投影必须一起计入原预算；恢复之后的普通Add继续原合同。

Agent恢复记录使用roster_agent_signer_fact的exact-target最小投影，源于原接纳时已完成的native Agent authority校验，须匹配原Commit的producer-fact摘要；该投影本身不证明授权，own Station必须验证原始冻结来源，缺失就失败。不得公开controller私有requested scope／PCR历史，不以当前DID key代替旧key，也不将Agent伪装成account_device或Service。
