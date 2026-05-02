# Read Marker, Inbox, Notification Schema

## 1. Read Marker

Read marker 是 actor-private 状态。

```json
{
  "type": "read_marker",
  "actor_id": "did:web:alice.example",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "scope": {
    "kind": "room",
    "ref": "cx:flow:01js0r00m00000000000000000"
  },
  "position": {
    "event_id": "cx:event:01js0ev0000000000000000000",
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
  "notification_id": "cx:notif:01js0nf0000000000000000000",
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
客户端本地 notification query: state=unread, cursor=<cursor>
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

## 6. Cross-device Sync Semantics

`cx.read.marker` 是 actor-private event，默认进入 principal 的 encrypted account data / actor-private stream，不进入共享 Space timeline，也不推进 Space reducer frontier。它仍然必须由当前 actor 或授权 device/session 签名，并绑定 `actor_id`、`space_id`、scope、position、HLC 和 device id。

跨设备已读同步流程：

1. 设备本地读到某个 scope 的位置后，提交或更新 actor-private `cx.read.marker`。
2. Principal Server / Sync Service 只向同一 principal 的授权设备返回该 marker，可通过 `account_data` 或 `receipts` stream 增量同步。
3. 每个设备按第 5 节规则合并同一 scope 的 marker，重新派生本地 notification state、unread count 和 push suppression state。
4. 派生 notification 的 `state=read/unread` 不得作为共享 Space 事实写回；需要公开已读回执时，必须使用 Space policy 允许的 `cx.receipt.read` ephemeral / receipt stream，并与 private read marker 分开授权。
5. 当 marker 指向的 target event 对某设备不可见、缺失或被 redacted，客户端 MUST 保留 marker 但把对应 projection 标记为 `target_missing` / `redacted`，不得回退到较旧 marker 造成未读计数反弹。

Notification projection MUST 绑定 read marker frontier、notification rule frontier 和 source event frontier。服务端返回 unread count 时 SHOULD 附带这些 frontier 或 sync token；客户端发现 frontier 陈旧时必须重新派生或请求增量，而不是把 push provider 的角标当作协议真相。
