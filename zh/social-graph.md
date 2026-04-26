# Social Graph and Feed Draft

## 1. 目标

Contrix 可以支持个人或组织的社交发布、关注、时间线、朋友圈和组织公告，但这些能力应作为对象图与视图扩展，而不是把协议根模型改成社交 feed。

本文定义：

- public feed，类似 Twitter / Bluesky 的公开广播模型
- circle feed，类似朋友圈的受众受限模型
- organization feed，组织公告、成员动态和官方发布
- follow / contact / circle 关系
- audience policy、转发、回复、搜索、删除和 E2EE 边界

## 2. 核心原则

社交能力必须遵守以下边界：

- DID / Principal 仍然是身份根。
- Post / Feed / Circle / Profile 仍然是 Entity / Relation / View，不是新的协议根。
- 公开可发现不等于可互动；可读不等于可回复、转发或索引。
- 朋友圈式内容必须按 audience policy 授权，不能靠客户端 UI 隐藏实现。
- 组织 feed 的官方性必须由 Organization DID 或 `cx.space.organization` 背书证明。

## 3. 标准 Entity 类型

### 3.1 `social_post`

`social_post` 表示可被时间线投影的发布内容。

```json
{
  "entity_type": "social_post",
  "author": "did:uuid:alice",
  "content": {
    "format": "contrix.richtext.v1",
    "body": "Ship notes for today"
  },
  "attachments": [],
  "audience_ref": "cx:audience:public",
  "reply_policy": "followers",
  "reshare_policy": "public_allowed",
  "created_at": "2026-04-26T00:00:00Z"
}
```

### 3.2 `social_feed`

`social_feed` 是发布入口或时间线源，例如个人主页、组织公告、项目动态。

```json
{
  "entity_type": "social_feed",
  "owner": "did:web:acme.example",
  "feed_kind": "organization_announcement",
  "discoverability": "public",
  "default_audience": "public"
}
```

### 3.3 `social_circle`

`social_circle` 是发布者维护的受众集合，用于朋友圈、亲友圈、团队动态等。

```json
{
  "entity_type": "social_circle",
  "owner": "did:uuid:alice",
  "circle_id": "cx:circle:close-friends",
  "visibility": "private",
  "membership_policy": "owner_managed",
  "member_refs": [
    "did:uuid:bob",
    "did:uuid:carol"
  ]
}
```

Circle membership SHOULD be holder-private or minimally disclosed. 公开列出“谁在我的朋友圈里”会泄露社交图，默认 MUST NOT 公开。

## 4. 标准 Relation 类型

| Relation | 含义 |
| --- | --- |
| `follows` | A 订阅 B 的公开或允许订阅 feed。 |
| `contact` | A 与 B 有联系人关系，可用于 presence、DM、朋友圈候选受众。 |
| `circle_member` | 某 actor 属于某 circle。默认私有或受限可见。 |
| `blocks_social` | 社交层屏蔽关系，通常映射到 personal blocklist。 |
| `reposts` | A 转发 B 的 post。 |
| `quotes` | A 引用 B 的 post 并附加内容。 |
| `likes` | A 对 post 表达轻量反馈。 |
| `replies_to` | post 回复另一个 post。 |

Follow 可以是单向；Contact 通常需要双向确认或至少本地确认。朋友圈受众不等于 follow graph。

## 5. Audience Policy

`cx.social.audience_policy` 定义一条 post 或 feed 的可见、可互动、可索引边界：

```json
{
  "type": "cx.social.audience_policy",
  "audience_id": "cx:audience:close-friends",
  "owner": "did:uuid:alice",
  "mode": "circle",
  "readers": {
    "circle_refs": ["cx:circle:close-friends"],
    "actor_refs": [],
    "claim_selectors": []
  },
  "interaction": {
    "reply": "readers_only",
    "react": "readers_only",
    "reshare": "disabled",
    "quote": "disabled"
  },
  "indexing": {
    "public_search": false,
    "directory_preview": false,
    "external_crawlers": false
  },
  "snapshot_at_publish": true
}
```

`mode` 取值：

- `public`：任何人可读，可进入公共搜索和公开 feed。
- `followers`：已被发布者允许的 follower 可读。
- `contacts`：联系人可读。
- `circle`：指定 circle 成员可读。
- `organization`：满足组织 claim 或组织 Space membership 的主体可读。
- `space_members`：指定 Space 当前成员可读。
- `direct`：显式 actor 列表可读。
- `private`：仅作者设备可读。

`snapshot_at_publish=true` 表示发布时冻结受众集合。后续从 circle 移除某人不应让其继续获取新内容，但是否撤销其已获得的旧内容取决于加密和 retention policy。高隐私朋友圈 SHOULD 使用 publish-time audience snapshot。

## 6. Twitter / Bluesky 式公开广播

公开广播 profile 使用：

- `social_feed.discoverability=public`
- `audience_policy.mode=public`
- `indexing.public_search=true`
- `reshare_policy` 可允许 repost / quote
- follow graph 可公开或半公开，取决于 holder policy

公共 feed 的分发可以由 Directory / Index / Relay / AppView 派生。推荐时间线类型：

- author timeline：某主体发布的公开 post
- following timeline：我关注的人发布的 post
- organization timeline：某组织官方 post
- topic / tag timeline：按 tag、schema 或 relation 聚合

公共 feed 中的 post 删除仍使用 redaction / tombstone 语义，不承诺全网物理删除。

## 7. 朋友圈式受众模型

朋友圈不是“公开 feed + 客户端隐藏”。它需要协议级 audience policy。

朋友圈 post SHOULD 使用：

- `audience_policy.mode=circle` 或 `contacts`
- `snapshot_at_publish=true`
- `indexing.public_search=false`
- `reshare=disabled`
- `quote=disabled`
- `reply=readers_only`

可见性规则：

- 未在受众快照内的主体 MUST NOT 从 Directory / Index / Relay preview 得知 post 内容。
- 如果实现支持 E2EE，post payload SHOULD 加密给受众快照对应设备或 MLS group。
- 服务端 Index MAY 只索引密文 metadata，不得公开正文、附件、评论或反应列表。
- 评论和 reaction 默认继承原 post audience，不得扩大受众。

朋友圈的关系图隐私：

- circle 名称、成员列表、移入/移出记录默认 holder-private。
- 被加入 circle 的人不一定需要知道 circle 名称。
- 用户 MAY 提供“可见范围提示”，但客户端不得泄露完整成员列表，除非 owner 明确允许。

## 8. Organization Social Feed

组织可以拥有官方 feed，例如公告、招聘、发布日志、成员动态。

组织官方 feed MUST satisfy:

1. Feed owner 是 Organization DID，或由 Organization DID 委派的 service/actor DID。
2. Feed 与 Space 或 profile 的官方性由 Organization DID 签名证明。
3. 如果 feed 声称属于某 official Space，必须验证 `cx.space.organization`。
4. Directory 显示官方标记前必须验证 Organization DID 和 endorsement。

组织 feed 的 audience 可为：

- `public`：公开公告。
- `organization`：仅当前组织成员。
- `space_members`：仅某官方 Space 成员。
- `claim_selectors`：满足角色或资格 claim 的主体。

组织内部动态不应默认公开到公共搜索。组织成员列表和阅读回执也不应默认公开。

## 9. Feed Space

实现 MAY 为社交功能创建专用 Space：

- personal public Space：个人公开发布日志。
- personal circle Space：朋友圈 E2EE group。
- organization announcement Space：组织公告。
- community Space：类似论坛/社区时间线。

但 feed 不要求每个 follower 都加入同一个 Space。公共广播可从作者 Principal Repo 直接发布，再由 Index/AppView 物化成 feed。朋友圈和组织内部 feed 更适合使用 Space membership、MLS 或 audience snapshot 管理加密与回填。

## 10. Moderation and Blocking

社交层必须复用 moderation 和 personal blocklist：

- 作者 MAY block actor，使其无法回复、引用、DM 或出现在个人 feed 互动中。
- Space / Organization moderation policy MAY quarantine、hide、deny interaction 或 remove from feed。
- Directory / public feed index MUST apply discoverability、audience policy 和 moderation policy。
- 被 block 的 actor 的历史 repost / reply 是否隐藏，由 viewer blocklist、author policy 和 Space policy 共同决定。

## 11. Federation and Portability

公共社交内容 SHOULD be portable:

- post 存在作者 Principal Repo 中
- feed projection 可由任意授权 Index 重建
- follow graph 可导出/导入
- handle 变更不改变历史 author DID

受限朋友圈内容 MUST prioritize privacy over portability:

- 导出必须保留 audience policy 和加密状态。
- 不得把 circle membership 明文导出给未授权接收方。
- 跨服务迁移时，旧服务不得继续获得新 post 的密钥。

## 12. Security Requirements

实现 MUST prevent:

- 通过搜索结果、推荐排序或错误信息泄露朋友圈 post 存在。
- 通过 reaction/reply count 泄露受众规模。
- 通过公共 feed index 暴露 private DID、pairwise DID 或 private handle。
- 将组织内部 feed 误标为 public。
- 将 follower 关系误当作 friend/contact/circle 关系。
- 转发或 quote 扩大原 post audience。

## 13. Conformance

`cx.profile.social.v1` MUST test:

- public post indexing
- follower timeline projection
- circle audience snapshot
- unauthorized circle post invisibility
- reply/reaction audience inheritance
- repost disabled enforcement
- organization official feed verification
- personal blocklist interaction filtering
- redaction/tombstone projection
