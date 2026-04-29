# Sync Conformance Vectors

## 1. 目标

本文定义 Client Sync、timeline ordering、pagination、snapshot、backfill 与 E2EE / MLS 同步的跨实现测试向量。

这些向量不是新的协议能力；它们把 `client-sync.md`、`operations-sync.md`、`snapshot-schema.md`、`encryption-and-audit.md` 中的规则转化为可执行的一致性测试。

实现声称支持以下 profile 时 SHOULD 运行本文对应向量：

- `cx.profile.minimal_client.v1`
- `cx.profile.full_client.v1`
- `cx.profile.e2ee_client.v1`
- `cx.profile.principal_server_repo_api.v1`
- `cx.profile.principal_server.v1`
- `cx.profile.index_node.v1`

## 2. 通用约定

测试向量使用以下简化字段：

```json
{
  "event_id": "evt_a",
  "actor_id": "did:uuid:actor_a",
  "actor_seq": 1,
  "hlc": "019b76daa800-0000-a0000000",
  "causal_depth": 1,
  "prev_refs": [],
  "auth_refs": [],
  "type": "cx.message.create",
  "content_hash": "sha256:..."
}
```

实现 MAY 使用真实 canonical JSON、CID、签名和 hash 替换示例值，但 MUST 保持以下语义：

- `event_id` 是内容寻址或签名绑定后的稳定 ID。
- `actor_seq` 在同一 actor repo 内严格单调。
- `hlc` 是 Hybrid Logical Clock，不能单独决定因果顺序。
- `causal_depth` 是 reducer 可计算的因果深度。
- `prev_refs` 描述 actor repo 发布前序。
- `auth_refs` 描述权限和状态依赖。

Timeline 默认排序键为：

```text
causal_depth ASC,
hlc ASC,
actor_id ASC,
actor_seq ASC,
event_id ASC
```

实现 MUST NOT 使用 Sync Service 到达顺序、数据库自增 ID、HTTP 接收顺序或本地写入时间替代上述排序。

## 3. Vector: Basic Timeline Order

向量名称：

```text
cx.vector.sync.order.basic.v1
```

输入事件：

```json
[
  {
    "event_id": "evt_b",
    "actor_id": "did:uuid:b",
    "actor_seq": 1,
    "hlc": "019b76daafd0-0000-00000000",
    "causal_depth": 1,
    "prev_refs": [],
    "auth_refs": []
  },
  {
    "event_id": "evt_a",
    "actor_id": "did:uuid:a",
    "actor_seq": 1,
    "hlc": "019b76daabe8-0000-00000000",
    "causal_depth": 1,
    "prev_refs": [],
    "auth_refs": []
  },
  {
    "event_id": "evt_c",
    "actor_id": "did:uuid:c",
    "actor_seq": 1,
    "hlc": "019b76daa9f4-0000-00000000",
    "causal_depth": 2,
    "prev_refs": [],
    "auth_refs": ["evt_a"]
  }
]
```

期望 timeline order：

```json
["evt_a", "evt_b", "evt_c"]
```

判定规则：

- `evt_c` 虽然 HLC 早于 `evt_a` 和 `evt_b`，但因果深度更大，MUST 排在因果前序之后。
- `evt_a` 和 `evt_b` 因果深度相同，按 HLC 排序。

失败条件：

- 输出 `["evt_c", "evt_a", "evt_b"]`。
- 输出与 Sync Service 输入数组顺序相同。

## 4. Vector: Deterministic Tie Break

向量名称：

```text
cx.vector.sync.order.tie_break.v1
```

输入事件：

```json
[
  {
    "event_id": "evt_z",
    "actor_id": "did:uuid:z",
    "actor_seq": 1,
    "hlc": "019b76daabe8-0000-00000000",
    "causal_depth": 1
  },
  {
    "event_id": "evt_a",
    "actor_id": "did:uuid:a",
    "actor_seq": 9,
    "hlc": "019b76daabe8-0000-00000000",
    "causal_depth": 1
  },
  {
    "event_id": "evt_a_2",
    "actor_id": "did:uuid:a",
    "actor_seq": 10,
    "hlc": "019b76daabe8-0000-00000000",
    "causal_depth": 1
  }
]
```

期望 timeline order：

```json
["evt_a", "evt_a_2", "evt_z"]
```

判定规则：

- `actor_id` 是跨 actor 的稳定 tie breaker。
- 同一 `actor_id` 下 `actor_seq` MUST 保持 repo 内顺序。
- `event_id` 只在前述字段全部相同的异常场景中作为最终稳定 tie breaker。

## 5. Vector: Limited Pagination Gap

向量名称：

```text
cx.vector.sync.pagination_gap.v1
```

服务端持有完整 timeline：

```json
["evt_1", "evt_2", "evt_3", "evt_4", "evt_5", "evt_6", "evt_7"]
```

客户端 initial sync 请求：

```json
{
  "filter": {
    "spaces": ["space_a"],
    "timeline_limit": 2
  }
}
```

允许响应：

```json
{
  "rooms": {
    "space_a": {
      "timeline": {
        "events": ["evt_6", "evt_7"],
        "limited": true,
        "prev_batch": "backfill_before_evt_6"
      }
    }
  },
  "next_batch": "sync_after_evt_7"
}
```

期望客户端行为：

- MUST 显示 `evt_6`, `evt_7` 的相对顺序。
- MUST 标记 `evt_1` 到 `evt_5` 尚未完成本地 backfill。
- MUST NOT 假设 `prev_batch` 前方没有历史。
- MUST NOT 把缺口解释为 redaction、删除或授权拒绝。
- 客户端向上滚动或恢复本地搜索时 SHOULD 使用 `prev_batch` backfill。

失败条件：

- 客户端把本地 timeline 视为完整。
- 客户端用本地插入时间重新排序 backfill 后事件。

## 6. Vector: Snapshot Frontier

向量名称：

```text
cx.vector.sync.snapshot_frontier.v1
```

Snapshot manifest：

```json
{
  "snapshot_id": "snap_a",
  "space_id": "space_a",
  "covers": {
    "timeline_before_or_equal": "evt_3",
    "frontier": ["evt_3"],
    "state_hash": "sha256:state_after_evt_3"
  },
  "chunks": [
    {
      "chunk_id": "chunk_1",
      "content_hash": "sha256:chunk_1"
    }
  ],
  "signature": "sig_of_snapshot_manifest"
}
```

增量事件：

```json
["evt_4", "evt_5"]
```

期望行为：

- 客户端 MUST 验证 manifest 签名和 chunk hash。
- 客户端 MUST 验证 snapshot 的 `state_hash` 与声明 reducer profile 匹配。
- 客户端 MUST 将 `frontier` 作为增量同步起点，而不是把 snapshot 当作无前序的新 genesis。
- `evt_4` / `evt_5` MUST 在 snapshot frontier 之后继续按 timeline order 应用。

失败条件：

- snapshot `state_hash` 不匹配时仍接受。
- 无法证明 `evt_4` 与 `frontier` 可连接时仍静默合并。

## 7. Vector: 联邦 pull 时的 Snapshot Bootstrap（新增）

向量名称：

```text
cx.vector.sync.snapshot_bootstrap.v1
```

联邦 pull 响应（跨域恢复场景）：

```json
{
  "operations": [
    "evt_4",
    "evt_5"
  ],
  "snapshot_bootstrap": {
    "snapshot_ref": "snap_a",
    "state_hash": "sha256:state_after_evt_3",
    "snapshot_frontier": ["evt_3"],
    "state_signature": {
      "issuer": "did:web:index.example",
      "alg": "ed25519",
      "sig": "sig_of_snapshot_assist"
    }
  },
  "next_cursor": "fed_after_evt_5"
}
```

期望行为：

- 客户端在处理 `operations` 之前先验证：
  - `snapshot_bootstrap.state_signature` 的签名；
  - `state_hash` 与声明的 reducer profile 一致；
  - `snapshot_frontier` 为非空且可与 `operations` 的因果源衔接。
- 验证通过后，以 `snapshot_frontier` 为增量起点继续应用 `evt_4` / `evt_5`。
- 验证失败时，不得直接使用 snapshot；应退回到 operation-only 回放或触发同源回源校验。
- `snapshot_bootstrap` 缺失时，节点 MAY 使用纯回放路径，不得将失败计为同步异常。

失败条件：

- 验证失败仍沿用 snapshot，并改变 frontier 判定。
- 将 `evt_4` / `evt_5` 当作无前序事件直接重放到空状态。

## 8. Vector: State After Timeline Item

向量名称：

```text
cx.vector.sync.state_after.v1
```

Timeline item：

```json
{
  "event_id": "evt_message_1",
  "state_after": {
    "membership_epoch": "m_10",
    "auth_state_hash": "sha256:auth_after_evt_message_1",
    "mls_epoch": 41
  }
}
```

后续状态变更：

```json
{
  "event_id": "evt_remove_bob",
  "state_after": {
    "membership_epoch": "m_11",
    "auth_state_hash": "sha256:auth_after_evt_remove_bob",
    "mls_epoch": 42
  }
}
```

期望行为：

- 客户端展示 `evt_message_1` 时 MUST 使用该事件对应的 `state_after` 或可验证等价状态。
- 客户端 MUST NOT 用当前最新 membership 状态重写历史消息当时的授权语义。
- 搜索、导出和审计界面 SHOULD 能区分事件发生时状态与当前状态。

## 9. Vector: Causal Barrier / Read Your Writes

向量名称：

```text
cx.vector.sync.causal_barrier.v1
```

客户端提交事件后收到：

```json
{
  "event_id": "evt_write_1",
  "sync_token": "sync_after_evt_write_1"
}
```

随后查询：

```http
POST /api/v1/index/query
X-Contrix-Wait-For: sync_after_evt_write_1
Content-Type: application/json
```

```json
{
  "space_ids": ["space_a"],
  "entity_types": ["message"],
  "limit": 20
}
```

期望行为：

- Index Node 支持该 profile 时 MUST 等待本地 materialized frontier 覆盖 `sync_after_evt_write_1`，或返回明确 stale / timeout 错误。
- 实现 MUST NOT 返回看似成功但不包含该写入的陈旧结果，除非响应显式声明 stale frontier。
- Principal Server MAY 只提供传播确权，不得伪装为 reducer 查询确权。

失败条件：

- 查询成功但缺少 `evt_write_1`，且没有 stale frontier 标记。

## 10. Vector: MLS Epoch Backfill

向量名称：

```text
cx.vector.sync.mls_epoch_backfill.v1
```

同步返回：

```json
{
  "timeline": [
    {
      "event_id": "evt_enc_1",
      "encryption": {
        "scheme": "mls-rfc9420",
        "group_id": "mls_group_a",
        "epoch": 41
      }
    },
    {
      "event_id": "evt_enc_2",
      "encryption": {
        "scheme": "mls-rfc9420",
        "group_id": "mls_group_a",
        "epoch": 42
      }
    }
  ],
  "mls_epochs": [
    {
      "group_id": "mls_group_a",
      "epoch": 41,
      "commit_event_id": "evt_mls_commit_41"
    }
  ]
}
```

期望行为：

- 客户端 MAY 解密 `evt_enc_1`，前提是本地有 epoch 41 secret。
- 客户端 MUST 接受并缓存 `evt_enc_2` 的密文 envelope。
- 客户端缺少 epoch 42 state 或 secret 时 MUST 将 `evt_enc_2` 标记为 `decryption_pending`。
- 客户端 SHOULD 使用 MLS epoch backfill 取回 `evt_mls_commit_42`、Welcome 或 key backup 恢复材料。
- 客户端 MUST NOT 因为暂时无法解密就丢弃 `evt_enc_2` 或改变其 timeline position。

失败条件：

- 把 `evt_enc_2` 当作损坏事件删除。
- 请求密钥时没有验证 epoch 42 的 membership 和设备授权。

## 11. Vector: Decryption Pending Recovery

向量名称：

```text
cx.vector.sync.decryption_pending_recovery.v1
```

初始状态：

```json
{
  "event_id": "evt_enc_pending",
  "timeline_position": 42,
  "decryption_state": "decryption_pending",
  "mls_epoch": 55
}
```

随后到达：

```json
{
  "event_id": "evt_mls_commit_55",
  "type": "cx.mls.commit",
  "group_id": "mls_group_a",
  "epoch": 55
}
```

期望行为：

- 客户端验证 `evt_mls_commit_55` 的签名、auth refs、membership transition 和 MLS transcript hash。
- 验证通过后 MAY 解密 `evt_enc_pending`。
- 解密成功后 MUST 保持原 timeline position。
- 本地搜索索引 MAY 增量更新，但 MUST 不把 plaintext 上传给 sync service / index。

失败条件：

- 解密恢复后把事件移动到 key arrival 时间。
- 在验证 MLS commit 前尝试使用外部提供的 secret。

## 12. Vector: Removed Member Fail Closed

向量名称：

```text
cx.vector.sync.removed_member_fail_closed.v1
```

状态序列：

```json
[
  {
    "event_id": "evt_remove_bob",
    "type": "cx.space.member.remove",
    "target": "did:uuid:bob",
    "mls_epoch_after": 44
  },
  {
    "event_id": "evt_enc_after_remove",
    "encryption": {
      "scheme": "mls-rfc9420",
      "group_id": "mls_group_a",
      "epoch": 44
    }
  }
]
```

期望行为：

- Bob 的客户端 MAY 继续保存无法解密的密文 envelope，前提是 history visibility 允许看见事件存在。
- Bob 的客户端 MUST NOT 获得 epoch 44 secret。
- Key backup、to-device、Welcome、external sender 任何路径都 MUST 对 Bob fail closed。
- 服务端或 Sync Service 若不能判断授权，MUST 只转发密文，不得转发解密材料。

失败条件：

- Bob 能通过 backfill、key backup 或旧设备同步拿到 epoch 44 secret。

## 13. Vector: Backfill Preserves Order Across Pages

向量名称：

```text
cx.vector.sync.backfill_order.v1
```

第一页：

```json
{
  "events": ["evt_4", "evt_5"],
  "limited": true,
  "prev_batch": "before_evt_4"
}
```

backfill 页：

```json
{
  "events": ["evt_2", "evt_3"],
  "limited": true,
  "prev_batch": "before_evt_2",
  "next_batch": "after_evt_3"
}
```

期望合并结果：

```json
["evt_2", "evt_3", "evt_4", "evt_5"]
```

判定规则：

- 合并 MUST 由 timeline order 和 cursor 边界共同验证。
- 客户端 MUST 去重重复事件。
- 客户端 MUST 保留 `evt_1` 仍缺失的 gap 标记。

## 14. Vector: Token Expiry Recovery

向量名称：

```text
cx.vector.sync.token_expiry_recovery.v1
```

输入：

```json
{
  "since": "expired_sync_token"
}
```

允许响应：

```json
{
  "ok": false,
  "error": {
    "code": "sync_token_expired",
    "message": "sync token expired",
    "details": {
      "retry_from": "initial_sync"
    }
  }
}
```

期望行为：

- 客户端 MUST 回退到 initial sync 或 snapshot-assisted initial sync。
- 客户端 MUST 保留本地未确认离线写入队列。
- 客户端 MUST NOT 清空已验证 repo cache，除非 cache hash 与新 snapshot 明确冲突。

## 15. Vector: Kanban Projection Column Pagination

向量名称：

```text
cx.vector.sync.kanban_projection_column_pagination.v1
```

初始请求：

```json
{
  "projection": "kanban",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "entity_types": ["task"],
  "limit": 2
}
```

输入响应：

```json
{
  "projection": "kanban",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "space_id": "cx:space:01js0sp0000000000000000000",
  "frontier": {
    "state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111",
    "operation_ids": ["cx:operation:01js0qp0000000000000000000"]
  },
  "columns": [
    {
      "key": "todo",
      "title": "Todo",
      "rank": "F",
      "source": {
        "model": "field_value",
        "field": "fields.status",
        "value": "todo"
      },
      "cards": [
        {
          "entity": {
            "id": "cx:entity:01js0ta0000000000000000000",
            "entity_type": "task",
            "title": "Task A"
          },
          "position": {
            "model": "field_value",
            "container_id": "todo",
            "rank": "F"
          }
        },
        {
          "entity": {
            "id": "cx:entity:01js0tb0000000000000000000",
            "entity_type": "task",
            "title": "Task B"
          },
          "position": {
            "model": "field_value",
            "container_id": "todo",
            "rank": "V"
          }
        }
      ],
      "next_cursor": "cx:cursor:kanban_todo_after_task_b",
      "limited": true
    },
    {
      "key": "done",
      "title": "Done",
      "rank": "V",
      "source": {
        "model": "field_value",
        "field": "fields.status",
        "value": "done"
      },
      "cards": [
        {
          "entity": {
            "id": "cx:entity:01js0tz0000000000000000000",
            "entity_type": "task",
            "title": "Task Z"
          },
          "position": {
            "model": "field_value",
            "container_id": "done",
            "rank": "V"
          }
        }
      ],
      "next_cursor": null,
      "limited": false
    }
  ]
}
```

后续请求：

```json
{
  "projection": "kanban",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "cursor": "cx:cursor:kanban_todo_after_task_b",
  "limit": 2
}
```

期望后续响应：

```json
{
  "projection": "kanban",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "frontier": {
    "state_hash": "sha256:1111111111111111111111111111111111111111111111111111111111111111"
  },
  "columns": [
    {
      "key": "todo",
      "title": "Todo",
      "source": {
        "model": "field_value",
        "field": "fields.status",
        "value": "todo"
      },
      "cards": [
        {
          "entity": {
            "id": "cx:entity:01js0tc0000000000000000000",
            "entity_type": "task",
            "title": "Task C"
          },
          "position": {
            "model": "field_value",
            "container_id": "todo",
            "rank": "k"
          }
        }
      ],
      "next_cursor": null,
      "limited": false
    }
  ]
}
```

期望行为：

- 客户端 MUST 只把 `todo` 列标记为未完整窗口。
- `cx:cursor:kanban_todo_after_task_b` 只能用于继续拉取 `todo` 列，不得作为整个 View 的全局 cursor。
- `done.limited=false` 不得让客户端推断其他列完整。
- 上述请求与响应 MUST 通过 `contrix-service-api.openapi.yaml` 中的 `QueryRequest` 与 `KanbanProjectionResponse` 校验。

## 16. Vector: Kanban Projection Hidden Counts

向量名称：

```text
cx.vector.sync.kanban_projection_hidden_counts.v1
```

输入状态：

```json
{
  "view": {
    "id": "cx:view:01js0vw0000000000000000000",
    "type": "view",
    "space_id": "cx:space:01js0sp0000000000000000000",
    "kind": "kanban",
    "query": {
      "entity_types": ["task"]
    },
    "kanban": {
      "column_model": "field_value",
      "group_by": "fields.status",
      "columns": [
        { "key": "review", "title": "Review", "rank": "F" }
      ],
      "card_order_by": [{ "field": "fields.rank", "direction": "asc" }],
      "hidden_count_policy": "omit"
    },
    "created_by": "did:web:alice.example",
    "created_at": "2026-04-29T00:00:00Z"
  },
  "actor_visibility": {
    "visible_entities": ["cx:entity:01js0tv0000000000000000000"],
    "hidden_entities": ["cx:entity:01js0th0000000000000000000"]
  },
  "canonical_column_membership": {
    "review": [
      "cx:entity:01js0tv0000000000000000000",
      "cx:entity:01js0th0000000000000000000"
    ]
  }
}
```

允许响应：

```json
{
  "projection": "kanban",
  "view_id": "cx:view:01js0vw0000000000000000000",
  "frontier": {
    "state_hash": "sha256:2222222222222222222222222222222222222222222222222222222222222222"
  },
  "columns": [
    {
      "key": "review",
      "title": "Review",
      "source": {
        "model": "field_value",
        "field": "fields.status",
        "value": "review"
      },
      "cards": [
        {
          "entity": {
            "id": "cx:entity:01js0tv0000000000000000000",
            "entity_type": "task",
            "title": "Visible task"
          },
          "position": {
            "model": "field_value",
            "container_id": "review",
            "rank": "F"
          }
        }
      ],
      "next_cursor": null,
      "limited": false
    }
  ]
}
```

判定要点：

- 本向量 MUST 至少执行 `omit`、`authorized_estimate`、`authorized_exact` 三组 policy case。
- `hidden_count_policy=omit` 时，Index MUST NOT 返回任何 `total_estimate`。
- `hidden_count_policy=authorized_estimate` 时，Index MAY 返回权限裁剪后的估计计数；在上述输入中允许 `total_estimate=1`，返回 `total_estimate=2` 为失败。
- `hidden_count_policy=authorized_exact` 时，Index MAY 返回权限裁剪后的精确计数；在上述输入中允许 `total_estimate=1`，返回 `total_estimate=2` 为失败，除非另有独立列级聚合授权。
- 不可见卡片不得通过空列、错误码、计数差异或 cursor 形态泄露存在性。
- 在上述输入中，返回 `total_estimate: 2` 或任何可推断隐藏卡片数量的 cursor / warning 均为失败。

## 17. 覆盖矩阵

| 向量 | Minimal Client | Full Client | E2EE Client | Repo Node | Principal Server | Index Node |
| --- | --- | --- | --- | --- | --- | --- |
| `cx.vector.sync.order.basic.v1` | MUST | MUST | MUST | SHOULD | SHOULD | MUST |
| `cx.vector.sync.order.tie_break.v1` | MUST | MUST | MUST | SHOULD | SHOULD | MUST |
| `cx.vector.sync.pagination_gap.v1` | MUST | MUST | MUST | MAY | SHOULD | SHOULD |
| `cx.vector.sync.snapshot_frontier.v1` | SHOULD | MUST | MUST | SHOULD | SHOULD | SHOULD |
| `cx.vector.sync.snapshot_bootstrap.v1` | SHOULD | SHOULD | MUST | SHOULD | MUST | SHOULD |
| `cx.vector.sync.state_after.v1` | SHOULD | MUST | MUST | SHOULD | MAY | MUST |
| `cx.vector.sync.causal_barrier.v1` | MAY | SHOULD | SHOULD | MAY | MAY | MUST |
| `cx.vector.sync.mls_epoch_backfill.v1` | N/A | MAY | MUST | MAY | SHOULD | MAY |
| `cx.vector.sync.decryption_pending_recovery.v1` | N/A | MAY | MUST | N/A | MAY | N/A |
| `cx.vector.sync.removed_member_fail_closed.v1` | N/A | MAY | MUST | SHOULD | SHOULD | SHOULD |
| `cx.vector.sync.backfill_order.v1` | MUST | MUST | MUST | MAY | SHOULD | SHOULD |
| `cx.vector.sync.token_expiry_recovery.v1` | MUST | MUST | MUST | MAY | MAY | SHOULD |
| `cx.vector.sync.kanban_projection_column_pagination.v1` | SHOULD | MUST | SHOULD | N/A | MAY | MUST |
| `cx.vector.sync.kanban_projection_hidden_counts.v1` | SHOULD | MUST | MUST | N/A | SHOULD | MUST |

## 18. 实现报告要求

Conformance runner SHOULD 为每个向量输出：

```json
{
  "vector": "cx.vector.sync.order.basic.v1",
  "implementation": "example-client 0.1.0",
  "profile": "cx.profile.full_client.v1",
  "result": "pass",
  "evidence": {
    "input_hash": "sha256:...",
    "output_hash": "sha256:...",
    "transcript_hash": "sha256:..."
  }
}
```

失败结果 MUST 包含：

- vector 名称
- profile 名称
- 输入版本
- 实际输出摘要
- 失败规则编号或描述

实现 MAY 隐藏密钥、明文和用户私有数据，但 MUST 保留足以复现协议行为的 hash、事件 ID、epoch、cursor 和状态 frontier。
