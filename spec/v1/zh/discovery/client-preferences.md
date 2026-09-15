---
title: "Client Preferences & Account Data"
status: candidate
normative: true
stability: v1
updated: 2026-07-02
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

在 Arkret 网络中，绝大部分数据是跨节点共享的协作对象（Realm、Space、Strand、Message、Morph、Relation、View）。但每个用户（Actor）也有大量的**私有状态**需要在其各个设备之间同步，但不应该对网络中的其他人可见。

本规范定义了这些**客户端偏好与账户数据 (Account Data)** 的存储、同步与标准 Schema。

## 2. 存储模型

Account Data 的存储、namespace key、`derive_account_data_key`、value encryption、HKDF/AAD transcript 与轮换规则的单一真相源是 [`../models/account-data.md`](../models/account-data.md)。本文只定义客户端偏好 data type 与服务端 policy projection 协商，不重复基础原语。

```json
{
  "kind": "ak.account_data.set",
  "key": "ak.client.ui_state",
  "body": {
    "mode": "dark",
    "accent_color": "#FF5733"
  }
}
```

### 2.1 服务端 policy projection 能力协商（normative）

account data 默认是 holder-private 加密数据，Station sync surface 只存不透明密文（[`../models/account-data.md` §1](../models/account-data.md)）。presence / typing 的精确 kind、target 与 visibility policy 不交给服务端读取；发送端按 [`profiles-presence.md` §3.4](./profiles-presence.md) 选择可安全加密的 scope。服务端仅可读取其它明确声明、确有服务端执行需要的最小 policy projection（例如单独授权的 blocklist data class）。"account data 加密"与"服务端执行 policy"之间的边界必须显式协商：

- 服务端 MUST 在 `ak.server.read.describe.v1`（`ServiceDescribe`）中声明它能否读取每个最小 policy projection（例如通过 `plaintext_visible_services.data_classes` 或等价 `policy_projection_readable[]` 声明）。`presence_visibility` 不得声明为服务端可读；未声明的其它 data class 视为不能读取。
- Presence / typing 的 policy gate **固定在发送客户端**：客户端只向符合本端 membership、contact 与 visibility 判断的整个加密 scope 发送；无法安全选择 scope 时 MUST 抑制发送。Station sync surface 只按外层已签名 `scope_ref` 做成员级 fanout，不读取或推断 `ak.presence.visibility`，也不得因无法读取该 key 而把整个 opaque Signal rail 判为不可转发。
- 单独声明且 holder 明确授权的其它最小 projection（例如 blocklist data class）可由服务端执行；其过滤结果 MUST NOT 让发送方、被查询方或 federation peer 区分"被屏蔽"与"无权限 / 不存在 / 离线"（§3.5）。

## 3. 标准账户数据类型

为了保证不同客户端间的互操作性，本规范定义了以下标准 Key 命名空间：
这些 key/pattern 的机器索引位于 [`account-data-key-registry.json`](../../artifacts/registry/account-data-key-registry.json)；新增标准 Account Data key 时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 校验 source refs 与写入 Event.kind。

### 3.1 空间标签与分类 (Realm Tags)

用户可以给加入的 Realm 打上私有标签（例如“收藏”、“低优先级”、“公司项目”）。

**Key:** `ak.tags.realm.<realm_id>`

```json
{
  "tags": {
    "ak.favorite": { "order": "m" },
    "ak.low_priority": {},
    "org.example.work": {}
  }
}
```

客户端 SHOULD 根据这些标签将 Realm 在 UI 上分组或排序。`order` 是用于自定义排序的稳定 rank string（跨端确定性见 §6；客户端 MAY 在 UI 内用 float 计算临时位置，但写回 account data 时 MUST 归一为规范 rank string）。

**Tag 命名保留规则（normative）**：`ak.*` tag 命名空间保留给本规范；客户端扩展 tag MUST 使用 `<vendor>.*` 反向域名风格前缀（例如 `org.example.work`）。§3.6 / §3.7 的私有 `tags` 字段沿用同一命名规则。

**标准 tag 词表（normative）**：

| tag | 语义 | 客户端行为 |
| --- | --- | --- |
| `ak.favorite` | 收藏 | 客户端 SHOULD 在分组 / 排序中置顶展示。 |
| `ak.low_priority` | 低优先级 | 客户端 SHOULD 降权展示（折叠、置底或降低通知突出度）。 |

未识别的 `ak.*` tag MUST 原样保留（存储与回写），客户端 MAY 不渲染；新增标准 tag MUST 登记到本词表。

### 3.2 勿扰与通知设置 (Notification Settings)

控制各个 Realm 或全局的通知覆盖行为（详见 `push-notifications.md`）。

**Key:** `ak.push_rules` 和 `ak.dnd_schedule`

`ak.dnd_schedule` 解密后的 plaintext 使用闭合 schema `ak.schema.dnd_schedule.v1`；时间段边界、
canonical IANA timezone、固定 tzdb 及异常值恢复规则见
[`push-notifications.md` §7](./push-notifications.md#7-静默时段-do-not-disturb)。

Notification projection 的 `dismissed` / `archived` 跨设备状态使用
`ak.notifications.inbox.<notification_id>`。加密 value MUST 绑定同一 `notification_id`、
`state ∈ {dismissed, archived}`、HLC 与 device tie-break 材料，并按 account-data CAS
重试循环合并；`read` / `unread` 仍由 read cursor 派生，不得写入该 key。

`<notification_id>` MUST 与 account subscribe `notifications.items[].id` 逐字节相等：普通源 Event 通知用
`ak:notification_projection:<44 字符 token>`。该 key 是 inbox 处置的唯一真源，账号同步通道不携带 `state`，
服务端也不得代写或代删该 key；同步通道的 `remove` 只删除本地当前行，是否清理对应 key 由持有者客户端自行决定
（见 [`../sync/client-sync.md` §3.1.2](../sync/client-sync.md)）。Agent runtime approval 分支只做 local dismiss，
不写该 durable key。

Actor-private View 使用 `ak.views.private.<view_id>`；加密 value MUST validate 为
`ak.schema.view.v1` 且 `visibility="private"`。共享 View 仍只能使用 `ak.view.*` Event。

以上两个 key 的可执行覆盖见
[`../conformance/conformance-vectors.md` §5.11](../conformance/conformance-vectors.md) 的
`ak.vector.account_data.private_view_inbox_binding.v1`。

### 3.3 自定义 Emoji 与 Sticker (Custom Emojis)

用户个人收藏的表情包或贴纸集。

**Key:** `ak.collections.stickers`

```json
{
  "images": {
    "party_parrot": {
      "blob_ref": "ak:blob:sha256:abcd...",
      "mime_type": "image/gif"
    }
  }
}
```

### 3.4 客户端 UI 偏好 (UI State)

用于保存用户的视图偏好，以便在新设备登录时恢复熟悉的界面。

**Key:** `ak.client.ui_state`

```json
{
  "sidebar_collapsed": false,
  "recent_realms": [
    "ak:realm:AdHing2meouJofkXXyApJTyFCo7SNoZHrSjQHaitT3D8",
    "ak:realm:AbFCxTyW_gTLgSNJVZge-vUGLGIA_xSq6UixRuoPDk-W"
  ],
  "language": "zh-CN"
}
```

> **字段命名（normative）**：该数组承载的是 `ak:realm:` ID，canonical 字段名为 `recent_realms`。客户端 MUST 写入并读取 `recent_realms`；`recent_spaces` 不是 v1 字段名。

### 3.5 个人屏蔽与过滤 (Personal Blocklist)

用户可以在私有 account data 中保存个人 blocklist。该数据只影响用户自己的客户端、本地搜索/投影、通知规则和联系请求处理，不改变 Realm 的共享事实。

**Key:** `ak.account.blocklist`

```json schema=schemas/event-payload.schema.json#/$defs/account_blocklist_payload
{
  "version": 1,
  "entries": [
    {
      "entry_id": "ak:block:019640b3-cc00-7000-8000-000000000000",
      "target": {
        "kind": "actor",
        "actor_id": {
          "kind": "account",
          "account_id": {
            "principal_id": "ak:did_core:webvh:zGMfBAbnRTYqW4943CVr9Dcii",
            "station_id": "ak:did_core:webvh:z6mkfixturestationexample"
          }
        }
      },
      "mode": "block",
      "applies_to": [
        "messages",
        "mentions",
        "dm",
        "calls",
        "contacts",
        "applets",
        "presence",
        "notifications",
        "directory"
      ],
      "reason_code": "harassment",
      "created_at": "2026-04-26T10:00:00.000Z",
      "expires_at": null
    }
  ]
}
```

`target.kind` 取值：

- `actor`
- `device`
- `handle`
- `domain`
- `applet`
- `keyword`

规则：

- blocklist holder 只取自已验 Event envelope 的完整 account `actor_id`，payload 不复制 holder 坐标。`version` 是该 exact AccountId blocklist 的单调 CAS revision；第一版为 `1`，后续写入必须精确为当前值 `+ 1`，跳号、回滚或并发旧版本均 `cas_conflict`。`ak.account.blocklist` 与同一 account author 的 `ak.account_data.set{key="ak.account.blocklist"}` 共享同一个 revision counter，不能形成两条独立 winner 链；同 principal core 异 Station 的账号绝不共享 counter 或规则。
- 每个 payload 是**全量替换**，不是 entry patch：加入屏蔽对象是在下一 revision 中加入新 `entry_id`；修改同一规则时保留 `entry_id`；移除屏蔽对象是在下一 revision 中省略对应 entry；`entries=[]` 清空全部规则。服务端或客户端不得把“移除”解释为删除共享消息、撤销 capability 或通知被屏蔽方。`expires_at` 到期只令该 entry 在 holder projection 中失效；同步写者 SHOULD 在下一 revision 中清除它，receiver 不得用本地计时器改写 durable payload。
- `target` 是闭合 discriminated union：`actor` 必须且只能携带完整 `actor_id`；`applet` 必须且只能携带 canonical `ak:applet:` `object_ref`；`handle | domain | keyword` 必须且只能携带 `value`；`device` 携带 canonical `ak:device:` `object_ref`，或在无法取得 device id 时携带 verification-method DID URL `value`。仅有裸 display name、W3C DID 或 `did_core_id` 不得成为 actor target；device 与 applet 的 typed-id 前缀必须由 schema 校验，不能把其它 `object_ref` 塞入对应分支。
- `actor` target 只按被过滤 Event / request 已验证的完整发送者 `actor_id` 逐字匹配：Station 承载的 user、organization、team、Agent、Bot 或 integration 账号均使用 `ActorId.account{account_id:{principal_id,station_id}}`，service 以自身身份实际作为发送者时使用 `ActorId.service{service_id}`。不得按 `actor_kind`、Organization DID / claim、`ak.realm.organization`、托管 Station、转发 service 或其它 affiliation 把一条 actor rule 扩张到关联主体；service 仅作为 transport / relay 时也不得命中。
- v1 不定义 `organization` 或 `realm` blocklist target。Organization 官方账号发出的内容按其 exact account ActorId 过滤；service 自身发出的内容按其 service ActorId 过滤。整个 Realm 的通知或默认视图偏好属于独立 per-Realm 客户端偏好；退出、拒绝新写入或撤销共享权限必须使用 membership / Contact / capability 的既有协议路径，不得由个人 blocklist 合成。
- 同一 revision 内最多 4096 个 entry；规范化后的 `(target, applies_to)` 不得被多个 entry 重复覆盖；需要不同 mode 时必须使用互不重叠的 `applies_to`。`applies_to` 至少一个值并决定规则作用面，其中 `contacts` 覆盖 contact request/relationship surface，`applets` 覆盖 applet-mediated request；不得用 `dm` 或 `notifications` 猜测替代这两个独立 surface。
- `mode="block"`：在所选 holder-facing surface 上拒绝新的 contact / DM / call / applet request 或隐藏来自 target 的内容；但共享 Realm Event 仍按下文“收取与过滤边界”处理。`mode="mute"`：内容仍可见、可搜索和正常同步，只抑制铃声、push、mention badge 等 attention surface。`mode="hide"`：内容仍同步、验证和保留，但从默认 holder view / search 中排除；它不拒绝新的协议请求。
- 通过非可信服务同步时，account blocklist MUST 仅为 holder 自己的设备加密。
- 客户端 SHOULD 抑制来自被屏蔽对象的通知、联系人请求、通话邀请与 DM 请求。
- 客户端 MAY 在共享 Realm 视图中隐藏或折叠被屏蔽内容。
- 客户端 MUST NOT 把 blocklist 发布到公共 Realm 状态或目录服务。
- 对被屏蔽方的可观察行为 MUST 与普通不可达 / 不可枚举场景一致：客户端和受托服务不得返回 `blocked_by_user`、不得发送 read receipt / typing / presence 的差异信号、不得因为 block 命中改变公开错误码、延迟模式或 directory 结果形态。需要本地诊断时只能在 holder 自己的加密 account data 或本地日志中记录。
- `ak.account.blocklist` 是 actor-private/account-private durable cell：它可以在 holder 的设备间同步，但不进入共享 Realm Seal coverage、membership state、Directory ingest 或 federation payload。
- 若服务端代表用户执行 blocklist 过滤（例如通知、DM invite、call invite 或 directory preview），该服务 MUST 被 holder 显式授权读取对应 blocklist 明文，或声明自身进入 `plaintext_visible_services.data_classes=["blocklist"]` / 等价 holder-private confidential service；否则只能转发给客户端本地过滤。服务端执行模式不得让发送方、被查询方或 federation peer 区分"被屏蔽"与"无权限 / 不存在 / 用户离线"。
- `handle` target 只与发送者已验证 handle claim 中的 canonical `handle`逐字比较；`domain` target 只与该已验证 handle claim 的 domain 分量，或按 [`../identity/did-usage-and-verification.md`](../identity/did-usage-and-verification.md) 已验证的 DID 域名绑定比较。display name、未验证 handle / DID 字符串或裸字符串后缀均不得命中这两类 target；`keyword` 才是纯内容字符串过滤。三者命中都只在 holder-private projection 生效，不证明也不得推断任何 actor、service、Organization 或 Realm 的控制关系。

#### 3.5.1 收取与过滤边界（normative）

- **共享 Realm 消息**：必须先按正常 federation / sync 路径收取、验签、准入、存储并推进 canonical Event / Seal 状态，因为同一 Event 对其他成员、引用链和 state root 仍然有效；随后才在 holder-private projection 应用 `block` / `hide`。不得在网络层丢弃该 Operation，也不得从共享 history、Seal coverage 或其它成员视图删除它。被过滤内容不生成 holder notification、mention attention、自动 read receipt，且不得触发 typing / presence 等可让发送方推断 block 命中的差异信号。
- **现有 Direct Conversation**：个人 blocklist 自身只是私有过滤器，不撤销 membership、Contact authority 或 participant authority。若产品的“拉黑用户”承诺阻止后续 DM 写入，客户端 MUST 把 blocklist 更新与 `ak.self.contact.command.tombstone.v1{block_peer=true}` 作为同一持久化 saga 执行并重试至闭合；Contact tombstone使稳定 conversation 投影为 `suspended` 并禁止新 application message，Consent revoke不得作为替代或附加门槛。只写 blocklist 时，对端仍可能成功提交 shared DM Event，本端必须同步后私下过滤。
- **新的 holder-private 请求**：contact request、首次 DM invite、call invite 或 applet-mediated request 在受托服务有权读取 blocklist 时可于 holder surface 前 drop；否则服务必须以不可区分形态转发加密材料，由客户端本地过滤。两种模式都不得向发送方返回 `blocked_by_user`，也不得产生可区分的错误、时延或 delivery receipt。
- **解除屏蔽**：下一 revision 移除 entry 后，未来 projection 立即停止过滤。此前已经正常收取并按 retention 保留的共享 Realm / DM 历史会重新出现在 holder view；若产品希望解除后仍不显示旧内容，必须另存 holder-private hide/tombstone 或执行已有 erasure 流程，不能把 blocklist removal 偷换成历史删除。Block 期间被 Contact tombstone真正拒绝、从未 accepted 的新请求或消息不会因解除屏蔽而补写。
- **离线与多设备**：设备只能依据其已同步到的最高 accepted blocklist revision 过滤。尚未取得新 revision 的设备必须把 blocklist freshness 视为 unknown，禁止发送 read receipt / presence 等可能泄漏差异的信号，待 actor-private account-data catch-up 后重算 holder projection。

上述 CAS、receive-before-filter、解除后 projection rebuild、DM Contact authority与Consent完全隔离及不可枚举行为由 conformance vector `ak.vector.account.blocklist_projection.v1` 闭合。

### 3.6 联系人备注 (Contact Remarks)

用户可以为 `ak.self.contact.read.list.v1` 中 `peer.kind="human"` 且状态为 `accepted` 的联系人保存只对自己可见的全局备注名（wire 字段 `petname`）、笔记和私有标签。逻辑记录由 `(holder principal_id, peer.principal_id)` 唯一确定；同一 holder 对同一联系人至多存在一条 live value，并在所有 Realm 共用。用户不得设置 per-Realm 联系人备注名，也不得创建 `ak.contacts.realm_actor.*`、`ak.contacts.actor.<principal_key>.<realm_id>` 或等价分叉载体。

该数据是 principal-private 的渲染覆盖层，**不**修改对方公开 profile，**不**写入 Realm history、mention、sender attribution 或任何协议主体字段。`peer.principal_id` 是 human Contact 的用户 `did_core_id`；`peer_id` 只是托管对端的 Station service DID，不是联系人身份键。Realm `actor_id`、Realm-scoped pairwise DID、MemberIdentity row、`realm_id`、handle、display name 与 `ak.profile.realm_override` 均不得成为联系人备注的逻辑键。

`ak.contacts.*` account-data key 只表达 holder-private 备注、标签、置顶、别名和本地排序。它不通知对方，不证明对方接受，也不打开 `direct_message` / `invite` / `call` / `presence` gate。联系人关系状态与 Contact-based action gate MUST 只从 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md) 定义的 `ak.contact.*` directional fact log 投影；Consent不得参与。客户端 MAY 把本地备注与 `ak.self.contact.read.list.v1` 结果合并展示，但不得把 account-data note 当作 accepted contact。

**Key:** `ak.contacts.actor.<principal_key>`，其中：

```text
principal_key = derive_account_data_key(
    RFC8785_JCS(["ak.contacts.actor", peer.principal_id])
)
storage_key = "ak.contacts.actor." || principal_key
```

`derive_account_data_key` 与 holder 的 `account_data_namespace_key` 定义见 [`../models/account-data.md` §2](../models/account-data.md)。`principal_key` 必须是 32-byte HMAC 输出的无 padding base64url（43 个 ASCII 字符）；服务端只能看到不透明尾段。

```json schema=schemas/contact-remark.schema.json
{
  "version": 1,
  "subject": {
    "kind": "human",
    "principal_id": "ak:did_core:webvh:z5Z2tUHXdembzXVX7EE5SJp5g"
  },
  "petname": "老王（前同事）",
  "note": "2024 年 ArkretCon 认识",
  "tags": ["org.example.work", "ak.favorite"],
  "pinned": true,
  "verified_handle_at_save": "wang:example.com",
  "confirmed_display_name": "Wang Wei",
  "saved_at": "2026-05-08T10:00:00.000Z",
  "updated_at": "2026-05-08T10:00:00.000Z"
}
```

字段（顺序与 [`contact-remark.schema.json`](../../artifacts/schemas/contact-remark.schema.json) 的属性顺序一致，
由正文字段表门禁机械比对）：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `version` | `int` | yes | 值格式版本，v1 恒为 `1`。取别的值是被拒绝的值，不是可协商的变体。 |
| `subject` | `object` | yes | 封闭对象，展开见下表。principal 级作用域是刻意的：备注是 holder 私有展示数据，不参与授权或主体相等，因此不带 Station / actor role。 |
| `petname` | `display_text_128` | no | holder 为该稳定联系人主体保存的全局备注名，最大 128 个 Unicode code point；UI 中文称“备注名”。跨所有 Realm 生效。缺省表示没有备注名；**不得**用空串清除（display profile 会拒绝空串）。 |
| `note` | `string` | no | 自由文本笔记，最大 4096 个 Unicode code point。可以为空，也可以跨行，因此不复用单行 display profile。 |
| `tags` | `string[]` | no | 私有分组标签，命名规则同 §3.1 Realm tags（`ak.*` 保留给本规范，`<vendor>.*` 用于客户端扩展）。schema 只校验 array-of-string；命名空间由客户端按 §3.1 作为领域规则校验，schema 通过**不**等于命名空间合法。 |
| `pinned` | `bool` | no | 是否置顶。 |
| `verified_handle_at_save` | `canonical_handle` | no | 保存或最近一次更新时该 DID 的 verified handle 快照，用于反冒充比对。存 wire canonical form（`<localpart>:<domain>`），不含输入用的前缀标记。 |
| `confirmed_display_name` | `display_text_128` | no | holder 最近一次显式确认联系人身份时所见的 verified PCR `actor_profile.display_name`；与 Profile **共用同一个** `display_text_128`（最大 128 个 Unicode code point），两侧不可能漂移到不同上限。不得写入 Realm override、MemberIdentity display、Directory 裸结果、OIDC `name` 或其它 fallback。 |
| `saved_at` | `timestamp` | yes | 首次保存时间。 |
| `updated_at` | `timestamp` | no | 最近修改时间。 |

`subject` 的两个成员（封闭对象，`additionalProperties:false`）：

- `kind`：`const("human")`，与 Contact human branch 对齐；Organization、设备、service 或 Realm actor 不得复用该记录。
- `principal_id`：`did_core_id`，取 `ak.self.contact.read.list.v1` human row 的 `peer.principal_id`；
  解密后 MUST 用它与 holder namespace key 重算 `<principal_key>` 并精确匹配当前 storage key。

`optional` 表示成员**缺失**，不是 `null`。裸 `{}` 不能冒充删除（`version` / `subject` / `saved_at` 是必需的），
物理删除的 tombstone 也不按本 schema 校验。petname 与 `confirmed_display_name` 同时缺失是合法值：
没有 Profile evidence 不阻断 Contact accept。

跨实现向量是 `ak.vector.contacts.remark_value.v1`（fixture `contact-remark-fixture.json`），
结构半与领域半必须都过，见 [`../conformance/conformance-vectors.md` §5.13](../conformance/conformance-vectors.md)。

**校验点（normative）**：producer 在**加密与签名之前**校验最终待写明文（含 CAS 重试时合并出的那一版），
consumer 在 **AEAD 解密之后、应用之前**校验。承载该 key 的 Station 没有密钥，
MUST NOT 因此要求明文、明文镜像或服务端 validator。结构校验只证明形状：
storage key 绑定、显式确认证据与 tag 命名空间是同一客户端另行执行的领域规则。

规则：

- 只有 accepted human Contact 可以新建或编辑 `petname`。Contact tombstone / suspended 后记录 MAY 保留，但非 accepted 期间不得将它作为实时身份面的主标签；同一 `peer.principal_id` 后续重新成为 accepted Contact 时继续使用原记录，不得重键或自动覆盖。
- 该 key 是 principal-private，MUST 与 §3.5 blocklist 一样以加密 account data 形式同步，Station sync surface 不得读取明文。客户端解密后 MUST 验证 `subject.kind="human"`，并用完整 `subject.principal_id` 和 holder 的 namespace key 重算 storage key；不匹配时 MUST fail closed，且不得覆盖本地已验证记录。
- `petname` 与 `note` MUST NOT 通过 mention、quote、forward、profile、Realm state、directory 或 Realm export 泄露给备注对象本人或其他成员。客户端构造引用、转发或导出时 MUST 使用对方公开的 display name / handle，不得替换为备注名。
- 本地备注 MUST NOT 参与 ACL、grant subject、policy condition、audit attribution、sender verification 或 MLS credential 判定，约束与 [`identity/identity-handles.md`](../identity/identity-handles.md) §2.3 中 display name 一致。
- roster、消息 sender、联系人 / DM 列表、mention autocomplete、邀请 / 请求确认等实时 holder-facing 身份面，只有在 verified evidence 能把可见主体唯一归约到 accepted Contact 的 `peer.principal_id` 时才可 join 备注；映射缺失、不唯一或仅有 display name / handle 时 MUST 按“无备注”处理，不得按字符串猜测关联。非空 `petname` MUST 作为主标签并带可识别的“备注”角标，当前 verified PCR Profile display 作为次要上下文；没有 `petname` 时主标签使用当前 verified PCR Profile display，不可达时才按既有 verified handle / protocol ID 降级。`confirmed_display_name` 是确认基准，不得充当实时名称缓存。
- 历史 replay、audit 与 export 中，当前 `petname` MAY 作为明确标注的 holder-private name 并列，但 MUST NOT 取代事件的 `subject_id`、as-of handle、`display_name_at_time` 或 audit attribution。安全敏感 UI MUST 能直接显示完整 `peer.principal_id`；若显示 `peer_id`，必须标记为托管服务而不是联系人身份。
- 当对方当前 verified handle 与 `verified_handle_at_save` 不一致时，客户端 SHOULD 在该联系人的渲染处显示 handle changed / transferred 标记，并提示用户复核备注，与 [`identity/identity-handles.md`](../identity/identity-handles.md) §6.1 的缓存失效语义一致。
- 当前可验证的 PCR `actor_profile.display_name` 与 `confirmed_display_name` 不一致时，普通实时身份面 SHOULD、安全敏感面 MUST 显示“全局显示名已变更”并同时提供旧确认值。profile 不可达、候选不唯一或只有 Realm override 时状态是 unknown，不得伪报 changed；只有 holder 的显式身份确认动作才可刷新已有值。普通 petname / note / tags / pin 编辑与 account-data CAS merge MUST 原样保留该字段。
- 客户端 MUST 在本地构造 accepted human Contact 的 confusable comparison set（confusable 比较基准集）：每个非空 `petname` 及已保存的 `confirmed_display_name`。渲染主体 S 的当前 surface public display 时，MUST 以 [`conformance/encoding.md` §2.2](../conformance/encoding.md) 的 `arkret_display_confusable_v1` 与其它 Contact 的比较基准值比较，并排除 S 自己的基准值。碰撞主体不是 Contact 时必须显示“非联系人”及 verified handle / DID；是另一 Contact 时使用其自己的 `petname`（若有）并加 handle / DID 消歧，且不得继承被碰撞联系人的头像信任环、verified-contact badge 或颜色。roster、请求、mention autocomplete、邀请确认与不可逆操作面必须使用同一判据。
- Contact accept 生效后，客户端仅可在该 key 从未存在、并且接受界面当场持有并展示了经 `ak.self.actor_profile.read.resolve.v1` 取得并自行验签的 exact signed Profile Event 时，把接受动作作为首次身份确认，初始化 `confirmed_display_name`；此动作 MUST NOT 自动创建或覆盖 `petname`。当时没有可验证 Profile 时保持两字段缺失，Contact accept 仍成功；稍后的静默后台读取不得冒充用户确认。不得以 Realm override、Directory 裸结果、handle、DID、MemberIdentity display 或 OIDC `name` 代替 verified PCR Profile。已有记录的 `petname`、note、tags、pin、`saved_at` 与确认值必须保留；并发初始化必须按 account-data whole-value CAS 做 read/decrypt → domain merge → encrypt/write，且保持幂等。
- 备注初始化或同步失败 MUST NOT 回滚、拒绝或伪装成 Contact accept 失败；客户端 SHOULD 持久重试并可显示“备注尚未跨设备同步”。手工输入备注和备注写入成功都不得成为 request / respond / glare accepted 的协议前置，也不得成为 typing / presence 等可被对端观察的差异信号。
- 客户端 MUST NOT 在未加密的本地缓存、日志、push payload 或崩溃报告中泄露 `petname` 与 `note`。服务端仍可能观察不透明 key 的数量、大小与更新时间；实现不得声称消除了这些流量 metadata。
- 删除联系人备注 MUST 使用 `ak.self.account_data.resource.delete.v1` 写入 [`../models/account-data.md` §5.3](../models/account-data.md) 定义的有版本 physical-delete tombstone，不依赖客户端本地清理，也不得用无法通过本节字段验证的空对象冒充删除。

不透明 key transcript、raw principal / Realm / service DID 负例与解密后 slot-binding 校验由 `ak.vector.account_data.contact_petname_binding.v1` 闭合；成对名称碰撞由 `ak.vector.encoding.confusable_check.v1` 闭合。

### 3.7 Realm 备注 (Realm Remarks)

用户可以为已加入或已收藏的 Realm 保存只对自己可见的本地备注名、笔记和私有标签。该数据是 actor-private 的渲染覆盖层，**不**修改 Realm 公开的 `title` / `summary`，**不**写入 Realm history、invite 文案、directory 投影或任何协议主体字段。

典型场景：用户加入多个 `title` 相同的 Realm（例如多个 "Engineering"、多家客户都用 "项目 A"），需要在本地侧栏稳定区分而无需向其他成员暴露区分依据。

**Key:** `ak.contacts.realm.<realm_id>`

```json
{
  "version": 1,
  "subject": {
    "kind": "realm",
    "id": "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5"
  },
  "local_name": "Acme 内部 · 工程",
  "note": "和外包侧 Engineering Realm 同名，注意区分",
  "tags": ["work", "high_signal"],
  "pinned": true,
  "verified_title_at_save": "Engineering",
  "verified_owning_organization_ids_at_save": ["ak:did_core:webvh:zGUwpRSnyVCLzU7upsm9iSwEv"],
  "saved_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `version` | `int` | yes | schema 版本，当前为 `1`。 |
| `subject.kind` | `enum(realm)` | yes | 固定 `realm`，与 §3.6 仅以 human Contact `peer.principal_id` 为主体的全局联系人备注正交。 |
| `subject.id` | `id:realm` | yes | 备注对象 Realm ID；MUST 与 key 中 `<realm_id>` 完全一致。 |
| `local_name` | `string` | no | Realm 本地备注名，最大 128 字符；字符串验证与 §3.6 `petname` 一致，成对 confusable 比较见 [`conformance/encoding.md`](../conformance/encoding.md) §2.2。 |
| `note` | `string` | no | 自由文本笔记，最大 4096 字符。 |
| `tags` | `string[]` | no | 私有分组标签，命名空间与 §3.1 `ak.tags.realm.<realm_id>.tags` 互通（同名 tag 视为同一分组）；`ak.*` 保留给本规范，`<vendor>.*` 用于客户端扩展。 |
| `pinned` | `bool` | no | 是否置顶。 |
| `verified_title_at_save` | `string` | no | 保存或最近一次更新时 Realm 公开 `title` 的快照，用于反"改名混淆"。 |
| `verified_owning_organization_ids_at_save` | `did_core_id[]` | no | 保存时 `owning_organization_ids` 快照，用于在组织漂移 / takeover 时给出复核提示。 |
| `saved_at` | `timestamp` | yes | 首次保存时间。 |
| `updated_at` | `timestamp` | no | 最近修改时间。 |

规则：

- 该 key 是 actor-private，MUST 与 §3.5、§3.6 一样以加密 account data 形式同步，Station sync surface 不得读取明文。
- `local_name` 与 `note` MUST NOT 通过 invite 文案、mention、quote、forward、directory 投影、shared link preview 或任何 Realm state 字段泄露给其他 Realm 成员；客户端构造邀请、跨端 share sheet、跨 Realm 引用或导出时 MUST 使用 Realm 公开 `title`，不得替换为本地备注。
- 本地备注 MUST NOT 参与 ACL、capability subject、policy condition、audit attribution、MLS credential 或 federation routing 判定，约束与 §3.6 中本地联系人备注一致。
- UI 显示本地备注时 SHOULD 同时呈现 Realm 公开 `title` 或 `ak:realm:` token 短摘要（44-character suffix 的前 8 字符），使用户可识别"备注相同但 Realm 不同"的误判；安全敏感 UI（删除 / archive / tombstone Realm、跨 Realm 邀请确认、转账类 applet 调用）MUST 能直接显示完整 `realm_id` 与 `owning_organization_ids`。
- 当 Realm 公开 `title` 与 `verified_title_at_save` 不一致，或 `owning_organization_ids` 与 `verified_owning_organization_ids_at_save` 不一致时，客户端 SHOULD 在该 Realm 渲染处显示 title changed / organization changed 标记，并提示用户复核备注；该机制与 §3.6 `verified_handle_at_save` 对称。
- 当用户已加入的多个 Realm 的公开 `title` 字符串经 `arkret_display_confusable_v1` 判为碰撞时，UI MUST 优先按 `local_name` 区分；缺少 `local_name` 时 MUST 退化到 `owning_organization_ids` / source Realm / `ak:realm:` 短摘要等附加上下文，不得在仅显示 `title` 的情况下让用户做破坏性或不可逆操作。
- 客户端 MUST NOT 在未加密的本地缓存、日志、push payload 或崩溃报告中泄露 `local_name` 与 `note`。
- 删除 Realm 备注 MUST 使用 `ak.self.account_data.resource.delete.v1` 写入 [`../models/account-data.md` §5.3](../models/account-data.md) 定义的有版本 physical-delete tombstone（与 §3.6 联系人备注同一机制），不依赖客户端本地清理，也不得用空对象冒充删除——空对象会被 `ak.self.account_data.resource.replace.v1` 的 closed schema 当作普通值写入，删不掉任何东西。用户离开或被踢出 Realm MAY 触发自动 tombstone（客户端策略，规范不强制）。
- `ak.contacts.realm.<realm_id>` 与 §3.1 `ak.tags.realm.<realm_id>` 并存：前者负责命名与笔记，后者负责分组与 `order` 排序；客户端 SHOULD 在本地 projection 中按 `realm_id` join 二者，规范上互不替代。

### 3.8 已读回执偏好 (Read Receipt Preferences)

控制是否向其他成员发送 `ak.receipt.read`（详见 [`discovery/read-receipts.md`](./read-receipts.md)）。MAY 设全局默认，并对特定 Realm 或 Strand / discussion track 单独重写。

**Key:** `ak.read_receipt.preferences`

```json
{
  "default": {
    "send": true,
    "display": true
  },
  "realms": {
    "ak:realm:Ac1aCK8aQdnkYImvdH3DFjq4jDCP198pXYWCGzGuVyj5": {
      "send": false
    }
  },
  "strands": {
    "ak:strand:AaalePlTK6W4ZKrbKyKzlmmcdhXVx-InxeWY4ul69tiN": {
      "send": true
    }
  }
}
```

字段：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `default.send` | `bool` | `true` | 全局是否发送 `ak.receipt.read`。 |
| `default.display` | `bool` | `true` | 全局是否在本地 UI 显示他人的 `ak.receipt.read`。只影响本地渲染，不改变订阅、fanout 或 unread 计算。 |
| `realms.<realm_id>.send` | `bool` |  | 针对单个 Realm 的覆盖，优先于 `default`。 |
| `realms.<realm_id>.display` | `bool` |  | 针对单个 Realm 的本地显示覆盖，优先于 `default`。 |
| `strands.<strand_id>.send` | `bool` |  | 针对单个 Strand / discussion track 的覆盖，优先于 `realms.<realm_id>`。 |
| `strands.<strand_id>.display` | `bool` |  | 针对单个 Strand / discussion track 的本地显示覆盖，优先于 `realms.<realm_id>`。 |

规则：

- 该 key 是 actor-private，加密存储于 account data；其他成员或 Station sync surface 不得读取明文。
- 客户端在生成 `ak.receipt.read` 前 MUST 按 (strand, realm, default) 顺序解析有效 `send`，最先命中的非空值生效。
- 客户端在渲染他人的 `ak.receipt.read` 前 SHOULD 按相同顺序解析有效 `display`；`display=false` 只隐藏本地 UI，不得要求 Station sync surface 停止投递，也不得改变 read cursor、unread count 或 push suppression 的协议状态。
- 该偏好 MUST NOT 影响 §3 中 actor-private 的 Read Cursor（`ak.read_cursor.advance`）发送或多端同步。
- 当目标 Realm / Strand 声明 `ak.realm.read_receipt_policy.disclosure="required"`（详见 [`discovery/read-receipts.md`](./read-receipts.md) §2.5）时，合规客户端 MUST NOT 允许该 scope 设置为 `send=false`，并 SHOULD 在 UI 标注该开关被 Realm / Strand 策略锁定；声明为 `disabled` 时同样无视用户的 `send=true` 不发送。
- 客户端 MAY 在 UI 上将常用过滤维度（按 Realm 标签、按 Organization）做成批量编辑入口，但实际 canonical state 仍以本 key 中的逐 ID 覆盖为准。

## 4. 与本地投影的交互

虽然 account data 对外不公开，但用户自己的客户端或可信端侧节点会拉取并解密这些数据，并合并到本地查询结果中。

例如：当客户端以 `object_kinds=["realm"]` 查询加入的 Realm 列表时，本地 projection 可以按 `realm_id` 同时 join `ak.tags.realm.*`（私有标签与排序）与 `ak.contacts.realm.*`（本地备注名、笔记、置顶），得到带 `local_name` 与 tag 的 Realm 列表，并在 `title` 重复时优先按 `local_name` 区分。

## 5. 安全与隐私

- 涉及用户敏感信息的 Account Data（例如访问第三方服务的私钥、密码管理器的 Vault），MUST 另外进行客户端加密（Client-Side Encryption），使用类似 Matrix 4S (Secret Storage) 的机制，通过单独的 Recovery Key 保护。
- 普通的 UI 偏好和标签可以直接由用户的 Device Key 签名写入加密 account data。

## 6. v1 规则

- 4S / Secret Storage 与 Key Backup 的存储格式必须使用客户端加密 envelope，绑定 principal DID、device / recovery key、algorithm、KDF parameters、created_at、version 和 payload hash。服务端不得获得解锁材料。
- 跨端排序字段 MUST 使用稳定 rank string 或 HLC + tie-break 组合，不得使用非确定性 float 作为唯一排序真相。客户端可在 UI 内使用 float 计算临时位置，但写回必须归一为规范 rank。
