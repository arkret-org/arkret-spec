# Redaction Conformance Vectors

## 1. 目标

本文件定义 redaction 的执行顺序、保留字段与可见性收敛规则。  
所有实现必须将 redaction 视为“可验证的内容裁剪”，而非删除事件。

向量命名：

```text
cx.vector.redaction.<scenario>.v1
```

## 2. Vector: 字段保留规则

向量名称：

```text
cx.vector.redaction.preserve_fields.v1
```

输入：

```json
{
  "target_event": {
    "event_id": "cx:event:01js0mrc000000000000000000",
    "kind": "cx.message.create",
    "space_id": "cx:space:01js0ms0000000000000000000",
    "space_version": "1",
    "actor_id": "did:uuid:alice",
    "created_at": "2026-04-26T00:00:00Z",
    "hlc": "01970e589d24-0001-aaaaaaaa",
    "prev_refs": [],
    "auth_refs": [],
    "content": {
      "body": "private notes",
      "mentions": ["@bob"],
      "attachments": ["hash:img1", "hash:img2"],
      "fields": {
        "rank": 10
      }
    },
    "client_generated": {
      "draft_id": "d-001",
      "ui_last_seen": "2026-04-26T00:00:01Z"
    }
  },
  "redaction_event": {
    "event_id": "cx:event:01js0rm0v00000000000000000",
    "kind": "cx.redaction",
    "space_id": "cx:space:01js0ms0000000000000000000",
    "space_version": "1",
    "actor_id": "did:uuid:alice",
    "created_at": "2026-04-26T00:00:02Z",
    "hlc": "01970e589d24-0002-bbbbbbbb",
    "prev_refs": ["cx:event:01js0mrc000000000000000000"],
    "auth_refs": ["cx:event:01js0cap000000000000000000"],
    "content": {
      "redacts": "cx:event:01js0mrc000000000000000000",
      "reason_code": "policy_recall"
    }
  }
}
```

期望结果：

```json
{
  "event_id": "cx:event:01js0mrc000000000000000000",
  "state": "redacted",
  "kept_envelope_fields": [
    "event_id",
    "kind",
    "space_id",
    "space_version",
    "actor_id",
    "created_at",
    "hlc",
    "prev_refs",
    "auth_refs",
    "proofs",
    "hashes",
    "redacted_by",
    "redaction_reason_code"
  ],
  "removed_fields": [
    "content",
    "client_generated",
    "mentions",
    "attachments"
  ]
}
```

判定要求：

- `redacts` 目标事件必须在 reducer 可见集合中存在。
- 重放前后事件必须保留 event_id/hash 的验证可追踪性。
- 目标事件的 `content`、`mentions`、`attachments`、`client_generated` 不得再对外展示。

失败判定：

- 把事件当作 tombstone 并抹去事件本体。
- 保留 `client_generated` 等不可验证字段。
- 修改 `event_id` 或 `hlc`。

## 3. Vector: redaction 与 policy scope

向量名称：

```text
cx.vector.redaction.policy_scope.v1
```

输入序列（先后顺序如下）：

1) 正常消息事件（可见策略允许）
2) policy 屏蔽事件（mark quarantined）
3) redaction（撤回）
4) redaction 之后查询 / 回放

```json
{
  "timeline": [
    {
      "event_id": "cx:event:01js0qv1000000000000000000",
      "kind": "cx.message.create",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "space_version": "1",
      "created_at": "2026-04-26T00:00:00Z",
      "hlc": "01970e589d25-0001-11111111",
      "state_key": "tx1",
      "content": { "body": "bad link: spam.example/phish" }
    },
    {
      "event_id": "cx:event:01js0qv2c00000000000000000",
      "kind": "cx.policy.action",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "space_version": "1",
      "created_at": "2026-04-26T00:00:01Z",
      "hlc": "01970e589d25-0001-22222222",
      "actor_id": "did:uuid:policy_bot",
      "content": {
        "target_id": "cx:event:01js0qv1000000000000000000",
        "scope": "public",
        "decision": "quarantine"
      }
    },
    {
      "event_id": "cx:event:01js0qv3r00000000000000000",
      "kind": "cx.redaction",
      "space_id": "cx:space:01js0ms0000000000000000000",
      "space_version": "1",
      "actor_id": "did:web:policy-admin.example",
      "content": {
        "redacts": "cx:event:01js0qv1000000000000000000",
        "reason_code": "policy_recall"
      }
    }
  ]
}
```

期望：

- Projection 不得展示已 redacted 的 `content`，但应保留 stripped 证据用于审计。
- 历史可见性为 `world_readable` 时，外部审计仍应看到 redaction 事实而不是原文。
- 冻结空间（frozen space）与历史归档（archived event）场景下，timeline 位置必须保留，不能物理删除。
- policy 的 `quarantine` 仍需要保留 redaction 后事件的 `event_id` 指纹映射。

失败判定：

- 在 redaction 后把事件从 timeline 移除。
- 使用完整明文替代 redaction 保留字段。
- 将 `quarantine` 解释为“删除”而非显示约束。

## 4. Vector: hard erasure receipt

向量名称：

```text
cx.vector.redaction.hard_erasure_receipt.v1
```

期望：

- hard erasure 在被测存储边界内删除 payload bytes 与派生明文。
- 实现保留 verification stub：原始 event id、验证事件图所需的 Event envelope digest / proof `payload_hash`、redaction event id、erasure reason、执行服务 DID、执行时间和签名 receipt。
- stub 不得额外保留已擦除明文字段的 standalone content hash、payload-only digest 或未加盐搜索 fingerprint；若审计必须保留内容承诺，必须使用每事件 salt 或 HMAC/pepper commitment，并把 secret 留在 legal-hold 边界或按 erasure policy 销毁。
- backfill 返回 redacted / erased stub，不伪造替代事件，也不静默造成历史缺口。
- legal hold 存在时阻止 hard erasure，但默认展示仍应用 redaction。
