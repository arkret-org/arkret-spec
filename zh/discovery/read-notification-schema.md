# Read Marker, Inbox, Notification Schema

## 1. Read Marker

Read marker 是 actor-private 状态。

```json
{
  "type": "read_marker",
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "scope": {
    "kind": "room",
    "ref": "cx:room:01JS0ROOM000000000000000"
  },
  "position": {
    "event_id": "cx:event:01JS0EV000000000000000000",
    "hlc": "01970e589d21-0004-a13f9c2e"
  },
  "updated_at": "2026-04-26T00:00:00Z"
}
```

## 2. Receipt

Receipt MAY be public or private depending on Space policy。

```json
{
  "type": "receipt",
  "receipt_type": "read",
  "actor_id": "did:web:alice.example",
  "target_event_id": "cx:event:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 3. Notification

Notification 是派生 projection。

```json
{
  "notification_id": "cx:notif:01JS0NF000000000000000000",
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:...",
  "source_event_id": "cx:event:...",
  "source_ref": "cx:message:...",
  "kind": "mention",
  "state": "unread",
  "priority": "normal",
  "created_at": "2026-04-26T00:00:00Z"
}
```

## 4. Query

```text
GET /api/v1/index/notifications?state=unread&cursor=<cursor>
```

请求字段：

| 字段 | 位置 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- | --- |
| `state` | query | `string` | optional | 通知状态过滤，例如 `unread`。 |
| `cursor` | query | `cursor` | optional | 分页 cursor。 |
| `limit` | query | `int` | optional | 返回数量上限；服务端 MUST enforce 最大值。 |

响应字段：

| 字段 | 类型 | 必填 | 说明与约束 |
| --- | --- | --- | --- |
| `notifications` | `object[]` | required | 当前 principal/device 可见通知。 |
| `counts` | `object` | optional | 未读数等聚合计数。 |
| `next_cursor` | `cursor` | optional | 下一页 cursor。 |

响应示例（非完整 schema）：

```json
{
  "notifications": [],
  "next_cursor": null,
  "counts": {}
}
```

## 5. Merge

多设备 read marker 合并规则：

- 同一 scope 取 causally latest marker
- 并发 marker 取 HLC 最大
- HLC 相同按 device id tie-break

Notification state SHOULD be derived from read marker + notification rule。
