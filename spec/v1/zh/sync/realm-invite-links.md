---
title: Realm Invite Links
status: candidate
normative: true
stability: v1
updated: 2026-10-28
---

## 0. 规范语言

本文的 MUST / MUST NOT / SHOULD / MAY 按 [规范语言](../conformance/normative-language.md)解释。本文定义用户自行分享的Realm邀请授权，不定义邮箱、手机号或第三方标识验证。个人PrincipalLocator只提供账号引介；普通定向Invite仍按[治理对象 §5](../models/governance-objects.md#5-invite)工作。

## 1. 身份、角色与信任边界

RealmInviteLink是一个Realm范围的独立授权对象；其 `realm_invite_link_id` 从已接纳 `ak.realm_invite_link.create` Event派生，使用 `ak:realm_invite_link:<44-char-event-token>`，MUST NOT 当作InviteId。目标只包含Realm，MUST NOT 授予Strand、Circle、Sidecar、消息、历史、管理或MLS私态权限。

创建者与接受者 MUST 是完整account Actor；AccountId的principal_id和station_id均不可省略。同principal在不同Station的两个账号是不同接受者。接受者自己的Station验证其普通会话／producer proof，通过正式peer网络面将原签Event交给当前Realm治理Station；不得访问别的服务的数据库、配置、KeyStore或实现函数。账号服务只承担普通登录会话职责，不承担链接秘密托管、计次或成员权威。

当前治理方 MUST 按[authority-commit-log §8.1／§8.2](./authority-commit-log.md#81-pcr-治理归属与交接资格normative)验证既有Realm主体与交接资格。本能力不增加PCR或其它对象的迁移资格。链接状态只随原已允许的Realm治理交接延续，原始身份、公钥、使用事实与额度不重置。

## 2. 客户端秘密与链接外壳

创建者客户端 MUST 使用CSPRNG生成全新32-byte Ed25519链接专用seed，并只将对应公钥、expires_at和max_uses写入创建Event。seed不是用户身份密钥或Station私钥，不授予除该链接接受证明以外的权限；MUST NOT 写入任何Event、Realm current、HTTP请求／响应、服务日志、遥测、普通浏览器持久化存储或账号服务。SDK中的secret类型 MUST 清零并脱敏Debug／错误显示。

HTTPS分享外壳复用[对象地址](../discovery/object-addressing.md)：

```text
https://<landing>/#realm/<realm-token>?action=join&lt=invite&tok=<credential>
```

`credential` 是无padding base64url编码的RFC8785 canonical JSON，closed成员依次为schema、realm_id、realm_invite_link_id、secret_seed、authority_locator_hints。schema恒为 `ak.schema.realm_invite_link_token.v1`。secret_seed是32-byte seed的无padding base64url；locator hints复用[RealmJoinCandidate](../../artifacts/schemas/realm-join-candidate.schema.json)的1..8项、严格按service_id排序的现有合同，只是未授权发现线索。客户端 MUST 检查URL规范化Realm等于token的realm_id。

tok MUST 只在HTTPS fragment内；客户端读取后 MUST 清理地址栏。landing、hints、URL的lt／action及token自述均不授予权限。最终授权只能来自当前治理方验证的已接纳创建Event、current和本次原签接受Event。客户端不得将seed发给landing、Directory、账号服务或自己的Station；网络请求只带目的隔离的链接持有证明。用户自行选择复制、二维码或其它分享渠道，协议不执行或确认外部投递。

尚未登录时 MUST 先登录／注册并明确选择账号；不得把秘密放进OAuth参数或return URL。只有能够按既有客户端私密存储合同安全保存时才可跨登录恢复；否则要求登录后重新打开链接。GET、扫描、链接预取、打开、登录、预览与账号切换 MUST NOT 接受邀请或占次数。

## 3. 创建与生成限制

`ak.realm_invite_link.create` 是正常producer-signed Realm Event。创建权是独立登记的管理权限；普通定向邀请权不自动产生多次可转发链接创建权。payload中的public_key、expires_at、max_uses均必填、接纳后不可修改；expires_at使用canonical UTC timestamp，max_uses为正整数，不允许null／0／缺省表示无限。

产品默认选择7天、1次，并在签名前明确显示。Realm policy bundle中的 `invite_link_limits` 是生成限制：max_lifetime_seconds默认2592000且不得小于60，max_uses_per_link默认1000且必须为正整数；创建寿命不得短于60秒，也不得超过该cut上的最大寿命。客户端使用既有Event可信时间窗口；治理方必须在接纳时确认尚未过期，且expires_at相对创建Event.created_at的寿命满足限制。超限拒绝，不修改已签payload。限制只约束新创建，不悄悄延长、缩短或增减已接纳链接；当前加入策略仍逐次生效。

创建Event、冻结定义与active生命周期 MUST 在同一个RealmCommit事务中持久化。得到真实accepted Commit前客户端 MUST NOT 将链接显示为可用。精确重试保留原Event与seed，不重新发钥。服务端只能读取公钥及授权定义，不能恢复链接秘密；丢失秘密后由有权管理者撤销旧链接、创建新链接。替换不另定义rotate alias，旧撤销必须先获得终局确认。

## 4. 持有证明与账号确认

public_key是原创建Event冻结的32-byte Ed25519公钥；不是DID verification method，也不得代替账号producer key。链接持有证明使用既有Ed25519／SHA256／RFC8785密码原语；closed proof携signature_algorithm、transcript_digest、signature，不虚构verification_method。

接受transcript是 `utf8("ak.realm_invite_link.accept_proof.v1\n") || canonical_json({realm_id,realm_invite_link_id,subject_account_id,request_id,audience:"arkret.realm_invite_link.accept"})`。preview／prepare使用独立 `ak.realm_invite_link.preview_proof.v1` context及 `arkret.realm_invite_link.preview` audience，绑定相同完整目标与请求身份；它不能成为接受证明。只有对应current链接定义的公钥可以验证证明。

`ak.realm_invite_link.accept` payload必须携realm_invite_link_id、subject_account_id、request_id、link_proof。subject_account_id MUST 逐字等于envelope.actor_id的完整account分量，普通账号producer proof覆盖包含link_proof的完整Event。持有证明不能转移至另一账号、另一Station、另一链接、另一Realm或另一用途。仅持有账号签名或仅持有链接证明都不足。

客户端只向自己的Station调用正式Realm preview／prepare／Event submit。既有RealmJoinIntent和目标合同增加闭合、互斥的链接来源分支；MUST NOT 用InviteId、裸URL、未登记resolve_target或x_*承载新授权。自己的Station独立验证nonce-bound RealmAuthorityBundle及当前治理身份，peer请求使用普通服务间认证，不转发用户bearer。

## 5. 接受、计次与成员原子性

链接持有者显式确认后才签署接受Event。治理方在同一Realm授权锁定cut核对：创建原件／公钥、active且未撤销、接受线性化时点严格早于expires_at、创建者当前仍具适用Realm邀请权限、全部现行join_rule／join_policy／ban及主体资格门、同账号未使用、已用集合基数小于max_uses。会话退出和密钥轮换不追溯撤销创建事实，新的接受仍遵守当前Realm授权。

接受者必须尚未join；已经是成员的打开或重复尝试不产生新Commit、使用记录或成员写入。`realm_invite_link_use` 的身份是(link ID,canonical_json(完整subject_account_id))，create-locked、不可删除或复用，记录必须引用本次真实接受Event／Commit。同一账号每链接至多一次；退出后不得再凭同链接入组，同principal在另一Station是另一个账号。次数以完整账号而非自然人为单位。

使用记录、成员leave→join、原Event、RealmCommit、必要outbox与索引 MUST 同事务提交。max_uses前态在该事务内求值，MUST NOT 让producer签某个head或旧计数来模拟排序。最后一次额度并发只能一个成功；全部拒绝零共享写入。计数规范来源为已接纳使用事实的唯一集合基数；物化counter只是可重建索引，MUST NOT 独立修改、因退群返还、因GC或交接清零。集合完整性与基数约束必须登记为security admission合同。

精确Event重试先恢复原accepted结果，不重复扣次或重新入组；创建、撤销、过期、耗尽和后续退群均不改写历史Commit。新Event不得凭旧成功回复重新入组。旧事件在到期后首次送达，或仅把created_at回填到到期前，MUST 拒绝。历史验证使用原Commit的接纳时点与冻结前态，不用backfill墙钟。

加入仍只授予既有成员边界；消息写入、历史floor、MLS Add／Welcome及其它capability继续走原合同。链接不能把ban、closed或其它硬门降级为预览或普通加入。

## 6. 撤销、状态与读取

`ak.realm_invite_link.revoke` 引用精确链接ID，由当前有相应权限的创建者或Realm管理者签署。撤销在同Realm stream提交active→revoked后永久生效；不能恢复或通过重写URL／seed绕过。原撤销Event精确重试返回原终局，不追加新状态改变。撤销先提交则后接受拒绝；接受先提交则保留已加入成员，踢人使用独立成员管理Event。

存储生命周期只保存active／revoked。管理 `RealmInviteLinkView` 从原件及current派生期限、max_uses、use_count和显示status；显示优先级revoked、expired、exhausted、active，不把显示状态当独立授权。读取与分页复用正式Realm current／history面与其披露权限，不返回秘密或把Replica旧View当当前接纳权威。预览只披露现行政策允许的入组前摘要，不泄露成员列表、消息或MLS secrets。

未知、撤销、过期、耗尽、错账号和无权认领对外统一not_found；管理员自身有权读取的状态可显示原因。schema、认证及已登记运行错误保留其原分类，不能以404掩盖内部错误。失败审计不得记录秘密。

## 7. 合同闭合与能力广告

唯一公共类型由SDK实现：RealmInviteLinkId、RealmInviteLinkView、RealmInviteLinkUseRecord及三类payload／私密token／证明。View用于读取组合，Record只表示明确身份且必须保留的接受事实，不另造Result／Row或同形Body alias。

正文、schema、ID／Event／action／proof-context／current／生成限制／时间／error与vector registry、OpenAPI、SDK、Coland真实事务、浏览器和native/WASM消费者必须同步。个人locator、普通账号Invite与本能力各自独立；不得重用或恢复第三方验证角色、邮箱材料和旧claim路径。

只有真实闭环完成且生成、撤销、期限、次数、完整账号接受及跨站路径全部具名验收后才能广告本能力。URL roundtrip、mock成功、空响应、入口存在或响应前拒绝均不代表覆盖。并发最后名额、撤销竞争、过期边界、相同principal异Station、错误证明用途、网络重试／崩溃、合法交接和所有失败零写入均必须验证。
