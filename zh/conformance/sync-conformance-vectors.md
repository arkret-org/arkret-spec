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
- `cx.profile.index_node.v1`

## 2. 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "cx:event:01js0ev000000000000000000",
  "actor_id": "did:uuid:actor_a",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a0000000",
  "prev_refs": [],
  "auth_refs": [],
  "kind": "cx.card.update",
  "target_ref": "cx:card:01js0ca000000000000000000",
  "content_hash": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor event chain 内严格单调。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `target_ref` MUST 指向标准对象、Morph、Relation、View 或 Space。

## 3. Vector: Board Collection Projection

输入：

```json
{
  "space_id": "cx:space:01js0sp000000000000000000",
  "events": [
    {
      "kind": "cx.board.create",
      "target_ref": "cx:board:01js0bd000000000000000000"
    },
    {
      "kind": "cx.list.create",
      "target_ref": "cx:list:01js0li100000000000000000",
      "content": {
        "board_id": "cx:board:01js0bd000000000000000000",
        "rank": "U"
      }
    },
    {
      "kind": "cx.card.create",
      "target_ref": "cx:card:01js0ca100000000000000000",
      "content": {
        "board_id": "cx:board:01js0bd000000000000000000",
        "list_id": "cx:list:01js0li100000000000000000",
        "rank": "U"
      }
    }
  ]
}
```

期望：

- Collection projection MUST 返回 `object.id = cx:card:01js0ca100000000000000000`。
- 返回项 MUST 位于 `cx:list:01js0li100000000000000000`。
- View cursor MUST 绑定 projection、view、frontier 与权限上下文。

## 4. Vector: Card Move Read-Your-Writes

输入：

```json
{
  "write": {
    "kind": "cx.card.move",
    "target_ref": "cx:card:01js0ca100000000000000000",
    "content": {
      "card_id": "cx:card:01js0ca100000000000000000",
      "from_list_id": "cx:list:01js0li100000000000000000",
      "to_list_id": "cx:list:01js0li200000000000000000",
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

- Index 在返回前 MUST 等待本地 frontier 覆盖写入 token，或返回可恢复超时。
- 查询结果中该 Card 的 `list_id` MUST 为 `cx:list:01js0li200000000000000000`。

## 5. Vector: Linked Room Visibility

输入：

```json
{
  "card_id": "cx:card:01js0ca100000000000000000",
  "linked_room_id": "cx:room:01js0ro100000000000000000",
  "viewer": "did:uuid:viewer",
  "viewer_can_read_card": true,
  "viewer_is_room_member": false
}
```

期望：

- Card projection MAY show a lazy linked Room reference.
- Room timeline MUST NOT be expanded.
- Notification/search results MUST NOT reveal hidden Room messages.

## 6. Vector: Room Timeline

输入：

```json
{
  "room_id": "cx:room:01js0ro100000000000000000",
  "events": [
    {
      "kind": "cx.message.create",
      "target_ref": "cx:message:01js0me100000000000000000",
      "content": {
        "room_id": "cx:room:01js0ro100000000000000000"
      }
    }
  ]
}
```

期望：

- `room-timeline` MUST return the message when viewer is a Room member.
- `card-discussions` MUST only include this message if the Room is linked to the Card and viewer can read the Room.
