---
title: 服务器当前结果与有界基线
status: candidate
normative: true
stability: v1
updated: 2026-09-13
sidebar:
  label: 当前结果与基线
---

本文规范用语遵循 [规范性语言](../conformance/normative-language.md)。

## 1. 唯一当前状态来源

普通客户端信任自己的 Account Station 对治理、可见性、ordinary Event 资格、固定因果顺序和 reducer 的判定。
`account-subscribe-frame` 的每 Realm `current {entries}` 是当前状态安装来源，替代并删除 `state`、
`state_after` Event 容器。原始 timeline Event、`state_at_window_start` 展示上下文、MLS 私有 tree 和
当前结果分别保存；不能从 Event kind、HLC、`effects` 或最后到达的 Event 推导当前值。

机器真相源为 [current-result-registry](../../artifacts/registry/current-result-registry.json) 与
[account-current-result schema](../../artifacts/schemas/account-current-result.schema.json)。每个标准非日志
cell family 必须登记明确交付策略；普通 current family 有精确 value schema、lattice 和 target 推导规则；value 是完整结果，不是 patch、reducer op
或任意 JSON。生成器校验与所有已注册非日志 writer 的覆盖，不允许静默漏掉新增 writer。
device.list_update 是历史通知断言，只通过既有 device_lists 通道与设备当前查询交付，不进入普通 current
coverage，也不得把全历史 changed/left payload 数组伪装成设备当前值。
ordered_log 不进入完整当前 cell 集，继续使用 timeline 或专门的服务器当前投影，例如成员 identity roster。
扩展 family 在注册完整当前值类型前不得伪装成标准 value；只能明确 unavailable，不得用空值代替。

## 2. 选择器、类型与唯一字段归属

每条 `CurrentResultEntry` 为 closed `{selector, target, revision, result}`。
`selector {scope_ref, cell_id}` 是唯一安装键；scope 只能是该外层 Realm 自身或它拥有的合法 Circle，
cell_id 是原有完整 CellRef。不同 scope 的同 CellRef 不相等。

`target` 是 closed `realm | strand {strand_id} | member {actor_id} | event {event_id}` 的兴趣归属：

- realm：本 Realm 当前治理、create-locked 属性和没有更细目标的当前对象。
- strand：由 accepted writer 的注册 subject 输入精确绑定的 Strand，包含它的当前对象、位置、生命周期和配置。
- member：由完整注册 membership subject 输入绑定的 ActorId；Circle membership 仍保留 Circle scope。
- event：消息 create Event 的精确 ref，由注册 Message subject 的 event-derived ID 规则反解；只用于
  请求 timeline 窗口中的 revision/reaction 当前结果。object redaction 按 accepted object subject 归属：
  Message 使用 event、Strand 使用 strand、其余对象使用 realm，不从 redaction Event 自身的 ID 推导。

pin 按 accepted pin_scope 推导：strand 使用 strand target，其余使用 realm target，仍保留真实 effective scope。

target 不另建状态键，不是 caller 提供的权限声明。服务器必须在事务索引中保存并验证它与 selector、
accepted source 对象的关联；客户端按 registry 检查可检查的 scope/ID/target 绑定，不重放 source history。
tuple/hash subject 不可逆，服务器必须在接纳 writer 时同事务保存其真实目标关联，不能从 hash 猜测目标。
客户端不为补关联下载 source history；只核对可检查的单 ID、结果内对象 ID 与 scope，信任自己 Station 的已裁决关联。
同 selector 的 target 不能随更新或分页任意改变。Realm target 不扩大 Circle 可见性；即使 cell 属于 realm
目标，Circle 内的内容仍须同时满足冻结窗口与当前 Circle 读取资格。

`result` 的唯一分支：

- `status=value, value, source?`：sequenced_state 的已确认值、OR-set 完整已 join 的元素值集合，或
  causal_register 的确定性唯一当前值。causal_register MUST 同时携带
  `source={event_id,depth}`；`depth` 为同 Cell 已验证因果深度，`event_id` 为该完整值的写入身份。
  其它 state model MUST 省略 source。空集合与显式
  null 依 family 类型表示真实结果，不表示缺响应；不携 dots，不要求客户端 join。
  从未写入的 sequenced_state cell 可由服务器确认 null，OR-set 可确认空数组，不得为补基线伪造 Genesis Event。
- `status=removed`：该 selector 在本次读取视图中已不存在或不再可见的版本化移除。它只删除当前结果，
  不删除 timeline 历史，不自动解释为成员 leave、对象业务 tombstone 或 MLS Remove。
- `status=unavailable, reason`：reason 闭合为 dependency_missing/limit_exceeded。
  不可用不是空值或删除。causal_register rank 依赖缺失时不得安装猜测值；安全状态缺确认材料时同样 fail closed。

Strand/Space/Morph/Relation/Profile/Circle 的当前对象值使用注册的具体对象 schema 派生完整当前值类型，
保留 create-derived id 和本 cell 全部已物化字段；registry 明确排除由独立 lifecycle、stage、parent、
resolution 或 history-access cell 拥有的字段。客户端只在展示层组合不同已安装结果，不能把组合对象
反写为单个 head 或使一个 cell 的替代删除其它 cell。View.state 由 View 自身持有时保留。

Realm genesis 当前值保留原有具体 genesis schema，为 purpose、security_class、encryption_profile 等
create-locked 属性提供完整来源。genesis 中的初始 notary/reducer/digest 坐标只表示创建时配置，当前值
分别由 notary、realm.reducer_profile、realm.digest_suite cell 决定，禁止用旧初始值覆盖它们。
MLS epoch cell 复用唯一 MlsEpochHead；Genesis 仅允许 `(0,0)`，普通推进必须 `n→n+1`，无 nullable 第二类型。

### 2.1 集合领域当前投影

remove_observed/remove_dots 是服务器操作，绝不进入 current 值。某些领域把 remove 作为 add 断言保留在
审计 cell；它们不能作为活跃条目发送给客户端再求领域默认视图。registry 的 domain_current 分支明确为：

- agent.key：服务器执行 key-management 的完整有效授权 fold，active 结果返回精确 method、public-key
  digest、accountability、scope/audience 交集、最早有限 expiry 和全部活跃 authorization Event refs。
  method/accountability 等安全事实缺少可验证确认状态时 unavailable；无授权、已撤销、到期或父 lifecycle
  不活跃或 scope/actions/resources/audience 交集为空使用 closed inactive reason（empty_scope）。revoke transition marker 不是 active authorization，不交客户端 fold。
- pin：pins 为服务器按 pins.md 已完成因果寄存器当前值、remove 和 reorder-note 继承判定的完整 active Pin
  payload；source_event_ids 列出组成此结果的真实 add/reorder 来源，供 encrypted note 的 exact读取与
  E2E。conflicts 仅表达 pins.md 登记的目标级领域冲突，不是通用 `causal_register` 多头，也不发送 remove/reorder patch 要求客户端求值。
- message.reactions：服务器按 strand-and-message §9.8 remove-wins 判定后，按 `(actor_id,key)` 返回当前
  reactions；每组 assertions 只含使其存活的真实 add 的 exact Event ref 与原 typed payload，去重成员
  已由服务器完成。所有 payload key/target 必须匹配分组与 selector。客户端只解密/验证真实 E2E内容，
  不从 remove 断言、dot 或因果边计算成员。未存活的组省略，空 reactions 是完整空结果。

capability/grant/derived、consent 和 invite proposal 的 joined 值只表示已保存事实，不能被解释为有效权限、
当前可行动邀请或成员资格。有效授权复用 self.authz 的 effective/check 当前结果，邀请复用当前邀请 list；
consent revoke 的精确 active dots 继续由 consent authoring 查询提供，本载体不替代这些专门输入。

这些是服务器当前读投影，不改动原核心 lattice、审计 cell 或 signed Event。时间到期、父 lifecycle 和
范围可见性变化同样触发持久 current revision/失效，不能仅等下一条用户 Event 才撤销旧 active 结果。

## 3. 版本与失效

revision 使用与账号 Realm 摘要、`realm_invalidations.revision` 相同的持久账号投影顺序域，范围
0–9007199254740991。同一发布事务的多项结果可以共享 revision；后继事务严格增加。数值不能取自 HLC
或客户端时钟。恢复数据库、重建版本域、切换 Station/账号时必须废止旧 cursor/snapshot，不能重置数字
后继续消费旧窗口。

增量按 `(revision, JCS(selector) 的无符号 UTF-8 字节)` 稳定排序；一个发布事务的同 revision 多 selector
允许跨页，私有继续位置必须同时保存 revision 与最后 selector 排序键。不得只保存最后 revision 再查询
`revision > last`，否则会漏掉同版本尾项；也不得为避免该问题要求整 revision 批一次装入单帧。

客户端按 selector 原子安装完整 result 与 target：较大 revision 替代，较小 revision 忽略；相同 revision
必须是 canonical-byte 相同的 result 和 target。相同版本不同内容或归属属于协议冲突，必须拒绝该帧、
停止推进 cursor 并重新查询 Station，不能任择覆盖。一个 Event 影响多个 cell 时，每个 selector 独立安装。

失效到达时暂停受影响操作，废止该 Realm 旧 baseline generation；旧段和旧 complete 不能清除 pending。
即使 filter 未变化，也必须重新建立目标当前结果基线。新基线 cut_revision 必须不早于已知失效 revision。
成员/范围撤权使用当前可见性规则清理可见缓存和移除记录，不借撤权响应暴露此前未披露的 selector。
当前结果不授予操作权限；每次服务写入仍由 Station gate，实际 MLS 接收/签名/解密/tree 校验仍在客户端。

## 4. 精确覆盖的分段基线

详情 `baseline` 替换为 closed `{snapshot_cursor, cut_revision, coverage, complete}`。
coverage 为 closed `{realm, strand_ids, members, event_ids}`：realm 为布尔值，strand_ids 最多32个，
event_ids 最多100个；members 为 `{mode:all}` 或 `{mode:selected,actor_ids}`，后者最多100个完整 ActorId。
集合无重复；strand_ids 与 event_ids 按解码后的 token 字节排序，ActorId 按 JCS 无符号 UTF-8 排序。
此处不是 SyncFilter 绑定摘要的字符串 lexicographic 排序；producer 从 filter 构造 coverage 时 MUST 按 coverage 规则重新规范化，不能直接复用 filter 数组顺序。

覆盖集只包含本次 filter 实际请求且获准的目标。realm=true 覆盖已选择 Realm 的必要治理与当前 Realm
目标；Strand 集按 filter 的精确选择或其服务器当前 default pointer 确定；event_ids 仅取实际 timeline
窗口；lazy members=true 时 selected 为窗口所需成员，false 才能声明 all。all 仍须有界分页，不得成为
首屏、发送或整个账号加载的前置条件。移除兴趣只停止投递，不产生业务删除。

服务器在一个事务中冻结 cut、精确 coverage、当前权限上下文及保留 reservation，再签发 snapshot_cursor。
不能先读 cut、稍后登记 cursor，中间按旧 cursor 最小 cut GC。窗口存续期间保留需要的历史投影版本；
无法保留时显式 resync，不能漏项。扫描使用 current/version 索引，不扫描全部历史再求最新值。

同 snapshot 的每段重复相同 cut_revision 和 coverage。含 baseline 的 Realm entry 内全部 current 结果
属于这个冻结快照，revision 不大于 cut；该段不夹带同目标新 live 结果。live frame 可穿插在快照段之间，
使用自身较大 revision。每页交付前重查权限，资格变化必须废止受影响窗口并重建，不把新视图重标成旧快照。

客户端以磁盘/事务存储持续记录本快照 seen selectors，不要求把整个集合装入内存。complete=true 只有在
全部此前分段持久安装后才生效；完成时只清理本 coverage 内、未 seen 且本地 revision≤cut 的旧结果。
窗口后新增、更新或移除不能被旧快照清理覆盖。部分页、空中间页、其它目标完成、catchup_complete 均不得
清空集合。snapshot 标识、seen 标记、结果和恢复 cursor 同一耐久边界保存；崩溃重放幂等。

Realm 首个可用基线必须提供当前 genesis/create-locked 安全属性、当前 policy/policy_bundle 的完整结果或
已确认空值、default Strand pointer 及请求默认目标时对应 Strand 当前结果。当前权限通过现有逐操作
authz/current-result 接口取得；不可要求客户端从 grant Events 求权限。必要字段未交付保持该操作 pending，
不能解释为默认值。服务器优先交付这些有界必要目标；不能要求等待 Realm 全对象、all members、所有 Realm
或旧消息才能呈现首屏。MLS authoring/accepted-artifact 查询仍使用各自正式 exact result，不借本基线替代 E2E。

`cell_contracts` 中 `cell_subject: null` 表示单例，不能误读为动态 subject。对于上述尚未写入的单例，
publisher 必须在验证完整 accepted 状态后发布已确认空值；数据库中缺少结果行本身不是空值证明。
派生 publication 标为 ready 但缺少必要基线条目时，读取方必须使其失效并通过既有 accepted frontier
重建路径修复，不能永久重试同一不完整 publication，也不能由客户端补默认值或发出新的治理 Event。

## 5. 预算与失败

每 current.entries 最多100项，受 account frame 8 MiB canonical /16 MiB wire 和 round 16 MiB/16 frames
总预算共同约束。分页只能在完整 selector 之间切分；causal_register 只发送唯一当前值及其 source。
固定 `MAX_ATOMIC_CURRENT_ENTRY_CANONICAL_BYTES = 7 MiB (7,340,032 bytes)`，计数对象为完整
CurrentResultEntry 的 RFC 8785 UTF-8 字节，包括 selector、target、revision 和完整 result/source 封装。
producer、持久索引和 receiver MUST 使用同一固定上限；它不随 coverage、调用方或当前帧余量改变。
能够符合此上限的完整 selector 必须在本帧装不下时延后，不得改成 unavailable。
只有完整 entry 超过此固定上限时，publisher 才以同一 selector/target/revision 持久化
unavailable/limit_exceeded；替换后的 entry 仍 MUST 满足上限。若坐标本身过大，连此固定失败结果也
无法封装，使用 Realm unavailable/limit_exceeded，不能截断坐标、记 seen 或声明 baseline complete。

单 Realm 最小合法详情帧的必需封装预留 `1 MiB (1,048,576 bytes)`，定义为含一个 entry 的帧
JCS 字节数减去该 entry 的 JCS 字节数，包括顶层 kind/cursor、Realm map key、current/entries
容器，以及 baseline 的 snapshot_cursor/cut_revision/coverage/complete。其它可选通道、Realm 和
payload MUST 在需要时拆到其它帧，不能挤占必需封装而改变原子结果。7 MiB + 1 MiB = 8 MiB。

此保留量有 schema 上界证明：两个 cursor 各至多2048个 ASCII 字符；每个 DID core 至多512个
Unicode code point，JCS 每个 code point 保守按最多6 bytes计（包含 JSON 转义），AccountActor
含两个 DID core。覆盖100个完整 ActorId、32个 StrandId、100个 EventId、53字节 Realm key、
安全整数 revision 及全部固定 JSON 键/标点后的必需封装仍小于1 MiB。不得把 code-point 上限
直接当UTF-8字节上限。`tools/test_current_result_budget.py` 的冻结向量验证此上界、临界值与
不同合法 coverage 下相同 entry 字节不变；schema 边界变化 MUST 同时更新并重新证明此预算。

最大合法 Event 的完整当前值连同固定 source 必须能由本预算路径表达；并发候选数不扩大单条 current entry。
单个最大合法值超过预算时使用上述 `limit_exceeded`，不得退回旧式完整 heads 或截断值。暂时读取或服务失败使用
既有 Realm unavailable，不产生、安装或记录 seen 的 selector 结果，也不能声明 baseline complete。
Realm 整体当前权威结果不可计算时使用既有 `realms[id].unavailable`，不能伪造完整空基线。

客户端只对尚缺目标必要当前结果的操作等待；removed、unavailable、成员状态与 E2E pending 分开处理。
服务器不得复活旧 state/state_after、raw-latest、retag 合成对象或客户端 reducer 作为兼容路径。
