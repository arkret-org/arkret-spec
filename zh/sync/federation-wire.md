# Federation Wire Protocol Draft

## 1. 目标

本文定义跨域服务间交易、跨域加入、backfill authorization 与 fork detection。

## 2. Service Authentication

每个 federation service MUST have DID。请求 MUST 使用 HTTP Message Signatures，并绑定：

- method
- target URI
- date
- content digest
- source service DID
- destination service DID

## 3. Transaction

```text
PUT /api/v1/federation/transactions/{txn_id}
```

```json
{
  "txn_id": "cx:txn:01JS0TX000000000000000000",
  "origin": "did:web:server.a.example",
  "destination": "did:web:server.b.example",
  "service_binding_ref": {
    "space_policy_hash": "sha256:...",
    "membership_frontier": ["cx:evt:..."],
    "destination_service_type": "principal_server"
  },
  "events": [],
  "receipts": [],
  "frontier": {},
  "created_at": "2026-04-26T00:00:00Z"
}
```

`txn_id` MUST be idempotent。

`origin` 与 `destination` MUST 是 service DID。接收方 MUST 验证 `destination` 与请求签名、目标 URL、DID service endpoint、Space policy 和 `service_binding_ref` 一致；不一致时 MUST 拒绝或进入 quarantine。

## 4. Cross-Domain Join

Join flow:

1. remote actor requests invite or join.
2. local authz checks Space policy.
3. local service returns join authorization.
4. remote actor submits membership event.
5. federation transaction distributes membership event.
6. if encrypted, MLS Welcome / Commit follows policy.

## 5. Backfill Authorization

Backfill request:

```json
{
  "space_id": "cx:space:...",
  "from_cursor": "cx:cursor:...",
  "limit": 100,
  "requester": "did:web:server.remote.example"
}
```

Remote service MUST prove it is allowed to receive the requested history. Visibility and capability rules apply to backfill.

Backfill authorization MUST evaluate the requester service DID against the Space policy, membership frontier, service delegation and plaintext visibility rules. If the requested range contains non-E2EE private content, the requester MUST be a participant Principal Server or an explicitly listed `plaintext_visible_services` entry for that range.

## 6. Fork Detection

Services SHOULD exchange frontier:

```json
{
  "space_id": "cx:space:...",
  "heads": ["sha256:..."],
  "max_hlc": "01970e589d21-0004-a13f9c2e",
  "witness_receipts": []
}
```

If two histories contain conflicting commits with same id but different hash, service MUST quarantine and report `duplicate_conflict`。

## 7. Quarantine

Suspicious remote input MAY be stored in quarantine queue until:

- signature verified
- schema verified
- capability verified
- fork resolved
- operator policy accepts source
