# Sync Conformance Vectors

## 1. 目标

本文定义 Client Sync、timeline ordering、pagination、snapshot、backfill 与 E2EE / MLS 同步的跨实现测试向量。当前向量已按标准对象 / Morph 模型重置，不包含旧 `Entity` 兼容性要求。

实现声称支持以下 profile 时 SHOULD 运行本文对应向量：

- `cx.profile.minimal_client.v1`
- `cx.profile.chat_only_client.v1`
- `cx.profile.kanban_only_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_events_api.v1`
- `cx.profile.principal_server.v1`

## 2. 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "cx:event:01js0ev0000000000000000000",
  "actor_id": "did:web:actor-a.example.com",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a0000000",
  "prev_refs": [],
  "auth_refs": [],
  "kind": "cx.flow.update",
  "target_ref": "cx:flow:01js0ca0000000000000000000",
  "content_hash": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor 的单条因果路径上严格递增；并发 sibling fork 可出现相同高度。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `target_ref` MUST 指向标准对象、Morph、Relation、View 或 Space。

## 3. Vector: Board Collection Projection

输入：

```json
{
  "space_id": "cx:space:01js0sp0000000000000000000",
  "events": [
    {
      "kind": "cx.space.create",
      "target_ref": "cx:space:01js0bd0000000000000000000",
      "content": { "kind": "board", "board_kind": "kanban" }
    },
    {
      "kind": "cx.space.create",
      "target_ref": "cx:space:01js0111000000000000000000",
      "content": {
        "kind": "list",
        "rank": "U"
      }
    },
    {
      "kind": "cx.flow.create",
      "target_ref": "cx:flow:01js0ca1000000000000000000",
      "content": {
        "board_id": "cx:space:01js0bd0000000000000000000",
        "list_id": "cx:space:01js0111000000000000000000",
        "rank": "U"
      }
    }
  ]
}
```

期望：

- Collection projection MUST 返回 `object.id = cx:flow:01js0ca1000000000000000000`。
- 返回项 MUST 位于 `cx:space:01js0111000000000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

## 4. Vector: Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "cx.flow.move",
    "target_ref": "cx:flow:01js0ca1000000000000000000",
    "content": {
      "board_id": "cx:space:01js0bd0000000000000000000",
      "card_id": "cx:flow:01js0ca1000000000000000000",
      "from_list_id": "cx:space:01js0111000000000000000000",
      "to_list_id": "cx:space:01js0112000000000000000000",
      "rank": "U"
    }
  },
  "query": {
    "object_types": ["card"],
    "consistency": {
      "wait_for": "sync_token_from_write"
    }
  }
}
```

期望：

- Projection executor 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Card 的 `list_id` MUST 为 `cx:space:01js0112000000000000000000`。

## 5. Vector: Linked Room Visibility

输入：

```json
{
  "card_id": "cx:flow:01js0ca1000000000000000000",
  "linked_room_id": "cx:room:01js0r01000000000000000000",
  "viewer": "did:web:viewer.example.com",
  "viewer_can_read_card": true,
  "viewer_is_room_member": false
}
```

期望：

- Card projection MAY show a lazy linked Room reference.
- Flow discussion timeline MUST NOT be expanded.
- Notification/search results MUST NOT reveal hidden discussion messages.

## 5.1 Vector: Subject Surface Visibility

输入：

```json
{
  "subject_id": "cx:subject:01js0sb1000000000000000000",
  "surface_room_id": "cx:room:01js0r02000000000000000000",
  "viewer_grants": ["cx.subject.read"],
  "viewer_room_membership": "none"
}
```

期望：

- Subject projection MAY show a lazy/locked Room surface reference if Room discoverability permits.
- Subject activity MUST NOT include hidden Room messages.
- Subject context MUST NOT leak hidden Room message bodies through previews, summaries, notifications, search snippets, embeddings, or decision summaries.

## 6. Vector: Room Timeline

输入：

```json
{
  "room_id": "cx:room:01js0r01000000000000000000",
  "events": [
    {
      "kind": "cx.message.create",
      "target_ref": "cx:message:01js0me1000000000000000000",
      "content": {
        "room_id": "cx:room:01js0r01000000000000000000"
      }
    }
  ]
}
```

期望：

- `room-timeline` MUST return the message when viewer is a Room member.
- `card-discussions` MUST only include this message if the Room is linked to the Card and viewer can read the Room.
