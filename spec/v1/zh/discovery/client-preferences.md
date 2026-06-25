---
title: "Client Preferences & Account Data"
status: candidate
normative: true
stability: v1
updated: 2026-06-10
---

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

在 Cokret 网络中，绝大部分数据是跨节点共享的协作对象（Realm、Space、Strand、Message、Morph、Relation、View）。但每个用户（Actor）也有大量的**私有状态**需要在其各个设备之间同步，但不应该对网络中的其他人可见。

本规范定义了这些**客户端偏好与账户数据 (Account Data)** 的存储、同步与标准 Schema。

## 2. 存储模型

### 2.1 存储在私有 Account Data

由于 Cokret 采用 signed Event 和 per-actor event chain 作为信任根，账户私有数据 SHOULD 作为加密 account data 或 actor-private Event 保存。

这些私有数据只有用户本人的受信任设备有权限读写。Sync Service 节点仅负责存储加密或不透明的二进制块，并不解析其中的明文。

### 2.2 数据寻址

所有的偏好数据以 Key-Value 字典的形式组织。每次修改是对某个 Key 的全量覆盖（使用 `ck.account_data.set` 操作）。

```json
{
  "kind": "ck.account_data.set",
  "key": "ck.client.ui_state",
  "body": {
    "mode": "dark",
    "accent_color": "#FF5733"
  }
}
```

### 2.3 服务端 policy projection 能力协商（normative）

account data 默认是 holder-private 加密数据，Sync Service 只存不透明密文（§2.1）。但部分 policy 投影（如 `ck.presence.visibility` 的 `presence_visibility` enum、`ck.account.blocklist` 的最小 data_class）需要服务端在执行 presence / typing fanout gate（[`profiles-presence.md` §3.4`](./profiles-presence.md)）或代表用户做 blocklist 过滤（§3.5）时读取。"account data 加密"与"服务端执行 policy"之间存在张力：若服务端完全无法读取最小 policy projection，它无法在服务端可靠 gate；若它能读，则突破了 holder-private 边界。v1 通过**显式能力协商**消解，而非让实现各自假定：

- 服务端 MUST 在 `ck.server.query.describe`（`ServiceDescribe`）中声明它能否读取最小 policy projection，至少覆盖 `presence_visibility` 与 `blocklist` 两个 data_class（例如通过 `plaintext_visible_services.data_classes` 或等价 `policy_projection_readable[]` 声明）。未声明即视为**不能读取**（fail-closed 默认）。
- 客户端据该声明选择执行位置：
  - 服务端声明可读对应 projection 且 holder 已显式授权 → 客户端 MAY 采用**服务端 gate**（服务端据 projection 执行 presence / typing fanout 与 blocklist 过滤）。
  - 服务端未声明可读、或 holder 未授权 → 客户端 MUST 采用**客户端本地 gate**，并且服务端 MUST 对跨设备 / 跨接收方 fanout fail closed（与 [`profiles-presence.md` §3.4`](./profiles-presence.md) "无法读取最小 policy projection 时 MUST 对 fanout fail closed" 同口径）。
- 无论哪种模式，服务端执行 blocklist / presence 过滤 MUST NOT 让发送方、被查询方或 federation peer 区分"被屏蔽"与"无权限 / 不存在 / 离线"（§3.5）。该协商只决定 gate 在哪一侧执行，不改变对外不可区分要求。

## 3. 标准账户数据类型

为了保证不同客户端间的互操作性，本规范定义了以下标准 Key 命名空间：
这些 key/pattern 的机器索引位于 [`account-data-type-registry.json`](../../artifacts/registry/account-data-type-registry.json)；新增标准 Account Data key 时 MUST 同步更新该 registry，并通过 `tools/artifact_pipeline.py check` 校验 source refs 与写入 Event.kind。

### 3.1 空间标签与分类 (Realm Tags)

用户可以给加入的 Realm 打上私有标签（例如“收藏”、“低优先级”、“公司项目”）。

**Key:** `ck.tags.realm.<realm_id>`

```json
{
  "tags": {
    "ck.favorite": { "order": "m" },
    "ck.low_priority": {},
    "org.example.work": {}
  }
}
```

客户端 SHOULD 根据这些标签将 Realm 在 UI 上分组或排序。`order` 是用于自定义排序的稳定 rank string（跨端确定性见 §6；客户端 MAY 在 UI 内用 float 计算临时位置，但写回 account data 时 MUST 归一为规范 rank string）。

**Tag 命名保留规则（normative）**：`ck.*` tag 命名空间保留给本规范；客户端扩展 tag MUST 使用 `<vendor>.*` 反向域名风格前缀（例如 `org.example.work`）。§3.6 / §3.7 的私有 `tags` 字段沿用同一命名规则。

**标准 tag 词表（normative）**：

| tag | 语义 | 客户端行为 |
| --- | --- | --- |
| `ck.favorite` | 收藏 | 客户端 SHOULD 在分组 / 排序中置顶展示。 |
| `ck.low_priority` | 低优先级 | 客户端 SHOULD 降权展示（折叠、置底或降低通知突出度）。 |

未识别的 `ck.*` tag MUST 原样保留（存储与回写），客户端 MAY 不渲染；新增标准 tag MUST 登记到本词表。

### 3.2 勿扰与通知设置 (Notification Settings)

控制各个 Realm 或全局的通知覆盖行为（详见 `push-notifications.md`）。

**Key:** `ck.push_rules` 和 `ck.dnd_schedule`

### 3.3 自定义 Emoji 与 Sticker (Custom Emojis)

用户个人收藏的表情包或贴纸集。

**Key:** `ck.collections.stickers`

```json
{
  "images": {
    "party_parrot": {
      "blob_ref": "ck:blob:sha256:abcd...",
      "mime_type": "image/gif"
    }
  }
}
```

### 3.4 客户端 UI 偏好 (UI State)

用于保存用户的视图偏好，以便在新设备登录时恢复熟悉的界面。

**Key:** `ck.client.ui_state`

```json
{
  "sidebar_collapsed": false,
  "recent_realms": [
    "ck:realm:01964195-0000-7000-8000-000000000000",
    "ck:realm:01964195-8000-7000-8000-000000000000"
  ],
  "language": "zh-CN"
}
```

> **字段命名（normative）**：该数组承载的是 `ck:realm:` ID，canonical 字段名为 `recent_realms`。客户端 MUST 写入并读取 `recent_realms`；`recent_spaces` 不是 v1 字段名。

### 3.5 个人屏蔽与过滤 (Personal Blocklist)

用户可以在私有 account data 中保存个人 blocklist。该数据只影响用户自己的客户端、本地搜索/投影、通知规则和联系请求处理，不改变 Realm 的共享事实。

**Key:** `ck.account.blocklist`

```json
{
  "version": 1,
  "entries": [
    {
      "entry_id": "ck:block:019640b3-cc00-7000-8000-000000000000",
      "target": {
        "kind": "actor",
        "did": "did:web:spammer.example.com"
      },
      "mode": "block",
      "applies_to": [
        "messages",
        "mentions",
        "dm",
        "calls",
        "presence",
        "notifications",
        "directory"
      ],
      "reason_code": "harassment",
      "created_at": "2026-04-26T10:00:00Z",
      "expires_at": null
    }
  ]
}
```

`target.kind` 取值：

- `actor`
- `device`
- `service`
- `handle`
- `domain`
- `organization`
- `applet`
- `keyword`

规则：

- 通过非可信服务同步时，account blocklist MUST 仅为 holder 自己的设备加密。
- 客户端 SHOULD 抑制来自被屏蔽对象的通知、联系人请求、通话邀请与 DM 请求。
- 客户端 MAY 在共享 Realm 视图中隐藏或折叠被屏蔽内容。
- 客户端 MUST NOT 把 blocklist 发布到公共 Realm 状态或目录服务。
- 对被屏蔽方的可观察行为 MUST 与普通不可达 / 不可枚举场景一致：客户端和受托服务不得返回 `blocked_by_user`、不得发送 read receipt / typing / presence 的差异信号、不得因为 block 命中改变公开错误码、延迟模式或 directory 结果形态。需要本地诊断时只能在 holder 自己的加密 account data 或本地日志中记录。
- `ck.account.blocklist` 是 actor-private/account-private durable cell：它可以在 holder 的设备间同步，但不进入共享 Realm Seal coverage、membership state、Directory ingest 或 federation payload。
- 若服务端代表用户执行 blocklist 过滤（例如通知、DM invite、call invite 或 directory preview），该服务 MUST 被 holder 显式授权读取对应 blocklist 明文，或声明自身进入 `plaintext_visible_services.data_classes=["blocklist"]` / 等价 holder-private confidential service；否则只能转发给客户端本地过滤。服务端执行模式不得让发送方、被查询方或 federation peer 区分"被屏蔽"与"无权限 / 不存在 / 用户离线"。
- 屏蔽组织或域 MUST 在可能时通过已验证的 DID / claim 绑定评估；仅有弱字符串匹配时，客户端 SHOULD 给出警告。

### 3.6 联系人备注 (Contact Remarks)

用户可以为已知联系人（其他 Actor / Organization / 设备）保存只对自己可见的本地备注名、笔记和私有标签。该数据是 actor-private 的渲染覆盖层，**不**修改对方公开 profile，**不**写入 Realm history、mention、sender attribution 或任何协议主体字段。

`ck.contacts.*` account-data key 只表达 holder-private 备注、标签、置顶、别名和本地排序。它不通知对方，不证明对方接受，也不打开 `direct_message` / `invite` / `call` / `presence` gate。联系人关系状态 MUST 从 [`../identity/contact-and-direct-conversation.md`](../identity/contact-and-direct-conversation.md) 定义的 `ck.contact.*` fact log 投影；contact action gate MUST 从 [`../identity/consent-model.md`](../identity/consent-model.md) 定义的 consent cell 投影。客户端 MAY 把本地备注与 `ck.self.contact.query.list` 结果合并展示，但不得把 account-data note 当作 accepted contact。

**Key:** `ck.contacts.actor.<did>`

```json
{
  "version": 1,
  "subject": {
    "kind": "actor",
    "did": "did:web:wang.example.com"
  },
  "local_name": "老王（前同事）",
  "note": "2024 年 CokretCon 认识",
  "tags": ["work", "favorite"],
  "pinned": true,
  "verified_handle_at_save": "wang.example.com",
  "saved_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `version` | `int` | yes | schema 版本，当前为 `1`。 |
| `subject.kind` | `enum(actor, organization, device, service)` | yes | 备注对象类型，命名空间与 §3.5 blocklist `target.kind` 子集一致。 |
| `subject.did` | `did` | yes | 备注对象 DID；MUST 与 key 中 `<did>` 完全一致。 |
| `local_name` | `string` | no | 本地备注名，最大 128 字符；规范化与 confusable 处理与 display name 一致（见 [`conformance/encoding.md`](../conformance/encoding.md) §2）。 |
| `note` | `string` | no | 自由文本笔记，最大 4096 字符。 |
| `tags` | `string[]` | no | 私有分组标签，命名规则同 §3.1 Realm tags（`ck.*` 保留给本规范，`<vendor>.*` 用于客户端扩展）。 |
| `pinned` | `bool` | no | 是否置顶。 |
| `verified_handle_at_save` | `string` | no | 保存或最近一次更新时该 DID 的 verified handle 快照，用于反冒充比对。 |
| `saved_at` | `timestamp` | yes | 首次保存时间。 |
| `updated_at` | `timestamp` | no | 最近修改时间。 |

规则：

- 该 key 是 actor-private，MUST 与 §3.5 blocklist 一样以加密 account data 形式同步，Sync Service 不得读取明文。
- `local_name` 与 `note` MUST NOT 通过 mention、quote、forward、profile、Realm state 或 directory 泄露给备注对象本人或其他成员。客户端构造引用、转发或导出时 MUST 使用对方公开的 display name / handle，不得替换为本地备注。
- 本地备注 MUST NOT 参与 ACL、grant subject、policy condition、audit attribution、sender verification 或 MLS credential 判定，约束与 [`identity/identity-handles.md`](../identity/identity-handles.md) §2.3 中 display name 一致。
- UI 显示本地备注时 SHOULD 同时呈现对方 verified handle 或 DID 短摘要，使用户可识别"备注名相同但 DID 不同"的冒充尝试；安全敏感 UI（DM 邀请、approval、转账类操作）MUST 能直接显示对方 DID。
- 当对方当前 verified handle 与 `verified_handle_at_save` 不一致时，客户端 SHOULD 在该联系人的渲染处显示 handle changed / transferred 标记，并提示用户复核备注，与 [`identity/identity-handles.md`](../identity/identity-handles.md) §6.1 的缓存失效语义一致。
- 当对方公开 display name 与本地 `local_name` 字符串相同或高度 confusable（按 [`conformance/encoding.md`](../conformance/encoding.md) §2.1 规则）时，UI MUST 优先显示本地备注并加可识别的"备注"角标，避免对方通过改名伪装成用户给他取的备注。
- 客户端 MUST NOT 在未加密的本地缓存、日志、push payload 或崩溃报告中泄露 `local_name` 与 `note`。
- 删除联系人备注 MUST 通过 `ck.account_data.set` 写入空对象或显式 `tombstone`，不依赖客户端本地清理。

### 3.7 Realm 备注 (Realm Remarks)

用户可以为已加入或已收藏的 Realm 保存只对自己可见的本地备注名、笔记和私有标签。该数据是 actor-private 的渲染覆盖层，**不**修改 Realm 公开的 `title` / `summary`，**不**写入 Realm history、invite 文案、directory 投影或任何协议主体字段。

典型场景：用户加入多个 `title` 相同的 Realm（例如多个 "Engineering"、多家客户都用 "项目 A"），需要在本地侧栏稳定区分而无需向其他成员暴露区分依据。

**Key:** `ck.contacts.realm.<realm_id>`

```json
{
  "version": 1,
  "subject": {
    "kind": "realm",
    "id": "ck:realm:0196419b-0000-7000-8000-000000000000"
  },
  "local_name": "Acme 内部 · 工程",
  "note": "和外包侧 Engineering Realm 同名，注意区分",
  "tags": ["work", "high_signal"],
  "pinned": true,
  "verified_title_at_save": "Engineering",
  "verified_owning_organizations_at_save": ["did:web:acme.example"],
  "saved_at": "2026-05-08T10:00:00Z",
  "updated_at": "2026-05-08T10:00:00Z"
}
```

字段：

| 字段 | 类型 | 必需 | 说明 |
| --- | --- | --- | --- |
| `version` | `int` | yes | schema 版本，当前为 `1`。 |
| `subject.kind` | `enum(realm)` | yes | 固定 `realm`，与 §3.6 联系人备注（actor/organization/device/service）正交。 |
| `subject.id` | `id:realm` | yes | 备注对象 Realm ID；MUST 与 key 中 `<realm_id>` 完全一致。 |
| `local_name` | `string` | no | 本地备注名，最大 128 字符；规范化与 confusable 处理与 §3.6 `local_name` 一致（见 [`conformance/encoding.md`](../conformance/encoding.md) §2）。 |
| `note` | `string` | no | 自由文本笔记，最大 4096 字符。 |
| `tags` | `string[]` | no | 私有分组标签，命名空间与 §3.1 `ck.tags.realm.<realm_id>.tags` 互通（同名 tag 视为同一分组）；`ck.*` 保留给本规范，`<vendor>.*` 用于客户端扩展。 |
| `pinned` | `bool` | no | 是否置顶。 |
| `verified_title_at_save` | `string` | no | 保存或最近一次更新时 Realm 公开 `title` 的快照，用于反"改名混淆"。 |
| `verified_owning_organizations_at_save` | `did[]` | no | 保存时 `owning_organizations` 快照，用于在组织漂移 / takeover 时给出复核提示。 |
| `saved_at` | `timestamp` | yes | 首次保存时间。 |
| `updated_at` | `timestamp` | no | 最近修改时间。 |

规则：

- 该 key 是 actor-private，MUST 与 §3.5、§3.6 一样以加密 account data 形式同步，Sync Service 不得读取明文。
- `local_name` 与 `note` MUST NOT 通过 invite 文案、mention、quote、forward、directory 投影、shared link preview 或任何 Realm state 字段泄露给其他 Realm 成员；客户端构造邀请、跨端 share sheet、跨 Realm 引用或导出时 MUST 使用 Realm 公开 `title`，不得替换为本地备注。
- 本地备注 MUST NOT 参与 ACL、capability subject、policy condition、audit attribution、MLS credential 或 federation routing 判定，约束与 §3.6 中本地联系人备注一致。
- UI 显示本地备注时 SHOULD 同时呈现 Realm 公开 `title` 或 `ck:realm:` 短摘要（UUID 前 8 位），使用户可识别"备注相同但 Realm 不同"的误判；安全敏感 UI（删除 / archive / tombstone Realm、跨 Realm 邀请确认、转账类 applet 调用）MUST 能直接显示完整 `realm_id` 与 `owning_organizations`。
- 当 Realm 公开 `title` 与 `verified_title_at_save` 不一致，或 `owning_organizations` 与 `verified_owning_organizations_at_save` 不一致时，客户端 SHOULD 在该 Realm 渲染处显示 title changed / org changed 标记，并提示用户复核备注；该机制与 §3.6 `verified_handle_at_save` 对称。
- 当用户已加入的多个 Realm 的公开 `title` 字符串相同或高度 confusable（按 [`conformance/encoding.md`](../conformance/encoding.md) §2.1 规则）时，UI MUST 优先按 `local_name` 区分；缺少 `local_name` 时 MUST 退化到 `owning_organizations` / source Realm / `ck:realm:` 短摘要等附加上下文，不得在仅显示 `title` 的情况下让用户做破坏性或不可逆操作。
- 客户端 MUST NOT 在未加密的本地缓存、日志、push payload 或崩溃报告中泄露 `local_name` 与 `note`。
- 删除 Realm 备注 MUST 通过 `ck.account_data.set` 写入空对象或显式 `tombstone`，不依赖客户端本地清理；用户离开或被踢出 Realm MAY 触发自动 tombstone（客户端策略，规范不强制）。
- `ck.contacts.realm.<realm_id>` 与 §3.1 `ck.tags.realm.<realm_id>` 并存：前者负责命名与笔记，后者负责分组与 `order` 排序；客户端 SHOULD 在本地 projection 中按 `realm_id` join 二者，规范上互不替代。

### 3.8 已读回执偏好 (Read Receipt Preferences)

控制是否向其他成员发送 `ck.receipt.read`（详见 [`discovery/read-receipts.md`](./read-receipts.md)）。MAY 设全局默认，并对特定 Realm 或 Strand / discussion track 单独重写。

**Key:** `ck.read_receipt.preferences`

```json
{
  "default": {
    "send": true,
    "display": true
  },
  "realms": {
    "ck:realm:0196419b-0000-7000-8000-000000000000": {
      "send": false
    }
  },
  "strands": {
    "ck:strand:01964200-0000-7000-8000-000000000001": {
      "send": true
    }
  }
}
```

字段：

| 字段 | 类型 | 默认 | 说明 |
| --- | --- | --- | --- |
| `default.send` | `bool` | `true` | 全局是否发送 `ck.receipt.read`。 |
| `default.display` | `bool` | `true` | 全局是否在本地 UI 显示他人的 `ck.receipt.read`。只影响本地渲染，不改变订阅、fanout 或 unread 计算。 |
| `realms.<realm_id>.send` | `bool` |  | 针对单个 Realm 的覆盖，优先于 `default`。 |
| `realms.<realm_id>.display` | `bool` |  | 针对单个 Realm 的本地显示覆盖，优先于 `default`。 |
| `strands.<strand_id>.send` | `bool` |  | 针对单个 Strand / discussion track 的覆盖，优先于 `realms.<realm_id>`。 |
| `strands.<strand_id>.display` | `bool` |  | 针对单个 Strand / discussion track 的本地显示覆盖，优先于 `realms.<realm_id>`。 |

规则：

- 该 key 是 actor-private，加密存储于 account data；其他成员或 Sync Service 不得读取明文。
- 客户端在生成 `ck.receipt.read` 前 MUST 按 (strand, realm, default) 顺序解析有效 `send`，最先命中的非空值生效。
- 客户端在渲染他人的 `ck.receipt.read` 前 SHOULD 按相同顺序解析有效 `display`；`display=false` 只隐藏本地 UI，不得要求 Sync Service 停止投递，也不得改变 read cursor、unread count 或 push suppression 的协议状态。
- 该偏好 MUST NOT 影响 §3 中 actor-private 的 Read Cursor（`ck.read_cursor.advance`）发送或多端同步。
- 当目标 Realm / Strand 声明 `ck.realm.read_receipt_policy.disclosure="required"`（详见 [`discovery/read-receipts.md`](./read-receipts.md) §2.5）时，合规客户端 MUST NOT 允许该 scope 设置为 `send=false`，并 SHOULD 在 UI 标注该开关被 Realm / Strand 策略锁定；声明为 `disabled` 时同样无视用户的 `send=true` 不发送。
- 客户端 MAY 在 UI 上将常用过滤维度（按 Realm 标签、按 Organization）做成批量编辑入口，但实际 canonical state 仍以本 key 中的逐 ID 覆盖为准。

## 4. 与本地投影的交互

虽然 account data 对外不公开，但用户自己的客户端或可信端侧节点会拉取并解密这些数据，并合并到本地查询结果中。

例如：当客户端以 `object_types=["realm"]` 查询加入的 Realm 列表时，本地 projection 可以按 `realm_id` 同时 join `ck.tags.realm.*`（私有标签与排序）与 `ck.contacts.realm.*`（本地备注名、笔记、置顶），得到带 `local_name` 与 tag 的 Realm 列表，并在 `title` 重复时优先按 `local_name` 区分。

## 5. 安全与隐私

- 涉及用户敏感信息的 Account Data（例如访问第三方服务的私钥、密码管理器的 Vault），MUST 另外进行客户端加密（Client-Side Encryption），使用类似 Matrix 4S (Secret Storage) 的机制，通过单独的 Recovery Key 保护。
- 普通的 UI 偏好和标签可以直接由用户的 Device Key 签名写入加密 account data。

## 6. v1 规则

- 4S / Secret Storage 与 Key Backup 的存储格式必须使用客户端加密 envelope，绑定 principal DID、device / recovery key、algorithm、KDF parameters、created_at、version 和 payload hash。服务端不得获得解锁材料。
- 跨端排序字段 MUST 使用稳定 rank string 或 HLC + tie-break 组合，不得使用非确定性 float 作为唯一排序真相。客户端可在 UI 内使用 float 计算临时位置，但写回必须归一为规范 rank。
