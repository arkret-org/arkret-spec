# Service Surface And Bootstrap Draft

## 1. 目标

如果只有对象模型、同步原则和 capability，而没有最小线级服务面，协议仍然很难真正互操作。

因此 Contrix 初版需要定义：

- identity registry 如何收发 DID 操作与 receipt
- repo 如何收发 commit / op
- relay 如何做 workspace firehose 与 backfill
- index 如何做查询与 inbox / notification 物化
- blob 如何上传与校验
- invite / grant 如何参与首次加入工作区

本文给出一个 **最小可互操作服务面** 草案。  
默认调用风格采用 RESTful HTTP，但实现也可以兼容 gRPC、GraphQL 等其他风格，只要提供语义等价的接口即可。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

DID Document SHOULD 只负责：

- 声明 identity registry / repo / relay / index / blob / capability 服务入口
- 声明服务 DID 或服务 endpoint

它不应直接塞入：

- 当前 grant 全量状态
- 当前 workspace 当前态
- 大量通知或 inbox 数据

### 2.2 没有任何单一服务是唯一真相源

- repo 是 actor 发布真相源
- relay 是传播层
- index 是查询物化层
- blob 是内容层

客户端应能在这些层之间交叉验证 frontier、hash 与 reducer profile。

### 2.3 接口必须天然支持幂等重试

网络重试、离线回放、多 relay 回流在去中心化系统中是常态。

因此写接口 MUST 支持：

- `commit_id` 幂等
- `op_id` 幂等
- 重复提交不重复生效

### 2.4 服务必须公布自己的兼容 profile

每个服务 SHOULD 能公开：

- `protocol_version`
- `supported_features`
- `supported_reducer_profiles`
- `supported_schema_profiles`

否则客户端无法判断自己能否安全使用该服务。

## 3. 通用服务描述接口

建议所有服务都提供：

```text
GET /api/v1/server/describe
```

示例：

```json
{
  "service_did": "did:web:relay.example.net",
  "service_type": "ContrixRelay",
  "protocol_version": "0.2-draft",
  "supported_features": [
    "firehose",
    "snapshot",
    "notification-index"
  ],
  "supported_reducer_profiles": [
    "cx.reducer.v1"
  ],
  "supported_schema_profiles": [
    "cx.schema.v1"
  ],
  "max_body_bytes": 1048576
}
```

### 3.1 Identity Registry Surface

identity registry 至少应提供以下语义：

#### 3.1.1 描述 registry

```text
GET /api/v1/identity/describe
```

返回：

- `service_did`
- `registry_mode = writer | witness | replica`
- 支持的 receipt 类型
- 当前软件版本与兼容 profile

#### 3.1.2 获取当前 DID Document

```text
GET /api/v1/identity/document?did=<did>
```

返回 SHOULD 包含：

- 当前 materialized DID Document
- 当前 `head_event_hash`
- 当前 `seq`
- 可选 witness receipts

#### 3.1.3 获取 DID 日志

```text
GET /api/v1/identity/log?did=<did>&cursor=<cursor>&limit=<n>
```

用于：

- 审计
- 重建 DID Document
- 验证 `key_log` 与 registry head 一致

#### 3.1.4 提交 DID 更新

```text
POST /api/v1/identity/submit-did-op
```

请求体 SHOULD 包含：

- `did`
- `seq`
- `prev_event_hash`
- `patch`
- `proofs`

要求：

- 相同 `did + seq` + 相同内容的重复提交 MUST 幂等成功
- 相同 `did + seq` 但内容不同 MUST 拒绝
- registry MUST 验证从 `inception_key` 出发的授权链

#### 3.1.5 获取 receipt / witness 证明

```text
GET /api/v1/identity/receipts?did=<did>&head=<event-hash>
```

#### 3.1.6 写入确认建议

初版建议：

- writer 客户端同时向多个 registry / witness 提交 `did_op`
- 至少拿到 `k-of-n` receipt 才视为提交成功
- 读取时可附带 `expected_head` 或 `min_seq`

这让 DID 写入仍然是普通网络请求，而不是全网区块共识。

## 4. Repo Surface

repo 至少应提供以下语义：

### 4.1 描述 repo

```text
GET /api/v1/repo/describe
```

返回：

- `repo_did`
- 当前 head commit
- 支持的签名算法
- 是否支持批量取 op

### 4.2 列出 commit

```text
GET /api/v1/repo/commits?cursor=<cursor>&limit=<n>
```

用于：

- actor 历史恢复
- 审计回放
- 补齐缺失 commit

### 4.3 获取单个 commit

```text
GET /api/v1/repo/commit?commit_id=<id>
```

### 4.4 批量获取 op

```text
POST /api/v1/repo/ops
```

请求体可携带一组 `op_id`。

### 4.5 提交 commit

```text
POST /api/v1/repo/submit-commit
```

要求：

- 同一个 `commit_id` 重复提交相同字节内容 MUST 幂等成功
- 同一个 `commit_id` 若内容不同 MUST 拒绝
- repo SHOULD 返回新的 head、已接受 op 列表，以及一组 **因果同步令牌 (Causal Sync Tokens, e.g., `[commit_hash, hlc]`)**，供客户端后续进行强一致性查询时使用。

## 5. Relay Surface

relay 至少应提供以下语义：

### 5.1 描述 relay

```text
GET /api/v1/relay/describe
```

### 5.2 Space firehose 订阅

```text
GET /api/v1/relay/subscribe?space_id=<id>&cursor=<cursor>
```

实现可用：

- SSE
- WebSocket
- 长轮询

但必须提供稳定 cursor 语义。

### 5.3 增量回补

```text
GET /api/v1/relay/backfill?space_id=<id>&cursor=<cursor>&limit=<n>
```

### 5.4 snapshot 入口

```text
GET /api/v1/relay/snapshot-head?space_id=<id>
```

用于拿到当前推荐 snapshot manifest。

## 6. Index Surface

index 至少应提供以下语义：

### 6.1 描述 index

```text
GET /api/v1/index/describe
```

### 6.2 获取 Entity 当前态

```text
GET /api/v1/index/entity?entity_id=<id>
```

### 6.3 结构化查询

```text
POST /api/v1/index/query
```

其请求头 SHOULD 支持 `X-Contrix-Wait-For: <sync_token>`。
其请求体 SHOULD 接受：

- `entity_types`
- `relation`
- 过滤条件
- 排序
- cursor
- limit
- `sync_token`: 可选。如果提供，Index 节点在响应前 MUST 阻塞等待本地物化进度到达或超过该 token 指示的因果前沿 (如特定的 `commit_hash`)，以保障“读己之所写”体验。超时则返回 408 或 504。

### 6.4 thread / topic 查询

```text
GET /api/v1/index/thread?topic_id=<id>&cursor=<cursor>
```

### 6.5 inbox / notification 查询

```text
GET /api/v1/index/notifications?cursor=<cursor>&state=unread
```

```text
GET /api/v1/index/inbox?scope=<scope>&cursor=<cursor>
```

## 7. Blob Surface

blob 服务至少应提供：

### 7.1 上传 blob

```text
POST /api/v1/blob/upload
```

返回：

- `blob_cid`
- `sha256`
- `size`

### 7.2 查询 blob 头信息

```text
HEAD /api/v1/blob/get?blob_cid=<cid>
```

### 7.3 下载 blob

```text
GET /api/v1/blob/get?blob_cid=<cid>
```

blob 校验 MUST 基于内容哈希，而不是单一 URL。

## 8. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 op，但服务层仍需要可查询面。

至少建议提供：

```text
GET /api/v1/authz/effective-grants?space_id=<id>&subject=<did>
```

```text
GET /api/v1/authz/invites?space_id=<id>&subject=<did-or-handle>
```

```text
POST /api/v1/authz/check
```

`check` 接口适合：

- repo 接收写入前预检查
- relay 分发前快速过滤
- client 发送前本地 UX 提示

## 9. Space Bootstrap Flow

初版推荐的首次加入流程：

1. 用户输入 handle、DID 或 Space link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 DID Document 发现 identity registry / repo / relay / index / blob / authz 服务
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 Space metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk。**防投毒要求 (Snapshot Validation)**：由于 Relay 和 Index 属于不受信节点，快照可能被恶意篡改。客户端 MUST 验证快照 manifest 中包含的 `state_hash` (Merkle Root)，且该哈希 MUST 具备 `Space Owner` 或可信发行者的密码学签名。若校验失败，客户端 MUST 丢弃快照并回退到 Repo 进行原始历史回放。
7. 从 frontier 之后拉取 backfill / firehose 增量
8. 本地执行 reducer
9. 建立 read marker、notification cursor 等个人状态

## 10. 新鲜度与多服务并存

当多个 relay / index 并存时，服务 SHOULD 公开：

- 当前 frontier
- snapshot frontier
- reducer profile
- 最后物化时间

客户端 MAY 比较这些值来判断：

- 哪个服务更新
- 是否需要回退到 repo 重放
- 某个 index 是否只是暂时落后，而不是数据冲突

对于 identity registry，同样 SHOULD 公开：

- DID 当前 head
- `seq`
- receipt 集合摘要

客户端可据此判断某个 registry 是：

- 最新 head
- 落后副本
- 还是可能发生了分叉或作恶

## 11. 传输安全与密文

服务面 SHOULD 区分：

- 路由所需元数据
- 可选端到端密文内容

如果 payload 已按 `policy.encryption_profile` 加密，则：

- repo / relay / index MAY 不解密正文
- 但仍 SHOULD 保留 hash、cursor、causal 与目标引用

## 12. 防滥用与配额机制 (Anti-Spam & Quota)

在去中心化网络中，计算、存储与带宽都是稀缺资源。协议要求所有提供写入或传播服务的节点实现必须具备防御恶意滥用的能力：

### 12.1 存储责任与 Blob Quota
- **成本归属**：Space 的整体数据大小、历史 Op 数量及附属的 Blob 存储成本，逻辑上必须绑定到 Space 的 `owner` 或负责托管的 `responsible_actor_id`。
- **拒绝写入**：当 Blob 服务或 Index 服务评估该 Space 占用的资源已超出预设的 Policy 配额 (Quota) 时，MUST 返回明确的资源超限错误 (如 HTTP 413 或 402)，并拒收新写入的 Op 或大文件 Blob。

### 12.2 写频率控制 (Rate Limiting)
- Relay 和 Repo 节点 SHOULD 基于 `actor_id` 与 `space_id` 实施严格的并发和频率限制。
- 对于来自未验证或低信誉 DID 的恶意刷写（例如短时间内进行海量无效的 `message.create` 或反复触发高并发图重组），节点有权暂时熔断该 DID 的请求。

## 13. 初版设计决定

当前草案建议固定：

- 定义最小 identity registry / repo / relay / index / blob / authz 服务面
- RESTful 风格路径是默认推荐，但语义等价最重要，可兼容其他调用风格
- 写接口必须幂等
- DID 写入采用多 registry / witness receipt，而不是区块链
- bootstrap 必须覆盖 invite / grant / snapshot / backfill
- 服务必须公开 reducer / schema / feature profile
- 明确 Space Owner 的资源记账责任与防滥用熔断标准

## 14. 核心 API 契约与 Schema (REST API)

为了保障客户端与去中心化节点的互操作性，定义以下核心 RESTful 端点。请求采用 Content-Type `application/json`。调用需在 HTTP Header 中附带 `Authorization: Bearer <JWS_Token>` 或使用 HTTP 签名认证。

### 14.1 Repo API: 提交操作
**`POST /api/v1/repo/submit-op`**
- **描述**：客户端向 Repo 提交经过签名的 Event Envelope。
- **请求 (Request)**：
  ```json
  {
    "repo_id": "cx:space:01JS0KP...",
    "op": { /* 完整的 Event Envelope 对象，见 object-model.md 19.1 */ }
  }
  ```
- **响应 (Response)**：
  ```json
  {
    "status": "accepted",
    "commit_id": "cx:op:01JS0KE...",
    "sync_token": "token_str_for_ryw"
  }
  ```
  *注：若 CAS (`expected_state_hash`) 校验失败，返回 409 Conflict。*

### 14.2 Repo API: 同步增量
**`POST /api/v1/repo/sync`**
- **描述**：基于 cursor 从 Repo 拉取缺失的 operations。
- **请求 (Request)**：
  ```json
  {
    "repo_id": "cx:space:01JS0KP...",
    "since": "cursor_string_or_op_id",
    "limit": 500
  }
  ```
- **响应 (Response)**：
  ```json
  {
    "ops": [ { /* Event Envelopes */ } ],
    "next_cursor": "new_cursor_string",
    "has_more": true
  }
  ```

### 14.3 Identity API: 解析 DID
**`POST /api/v1/identity/resolve`**
- **描述**：根据 DID 查询当前的公钥、Service Endpoints 及其合法演化证明。
- **请求 (Request)**：
  ```json
  {
    "did": "did:web:alice.com"
  }
  ```
- **响应 (Response)**：
  ```json
  {
    "did_document": {
      "id": "did:web:alice.com",
      "verificationMethod": [ ... ],
      "service": [
        { "id": "#repo", "type": "ContrixRepo", "serviceEndpoint": "https://repo.alice.com" }
      ]
    },
    "key_log_head": "cx:keyevt:01JS...",
    "seq": 5
  }
  ```

### 14.4 Relay API: 实时流订阅
**`GET /api/v1/relay/firehose?space_id=cx:space:01JS0KP...`**
- **描述**：通过 WebSocket 或 Server-Sent Events (SSE) 建立实时监听。
- **Frame Format (每帧)**：
  ```json
  {
    "type": "event",
    "seq": 106,
    "payload": { /* Event Envelope */ }
  }
  ```

## 15. 标准错误响应 (Error Response Schema)

所有 API 端点在遇到错误时 MUST 返回统一格式的 JSON 错误体，以便客户端 SDK 做统一的重试与 UI 展示：

```json
{
  "error": "CASConflict",
  "message": "expected_state_hash mismatch: current=abc..., expected=def...",
  "retry_after_ms": 2000
}
```

### 15.1 标准错误码枚举

| 错误码 | HTTP Status | 含义 |
|--------|-------------|------|
| `InvalidSignature` | 401 | 签名校验失败 |
| `AuthExpired` | 401 | 认证令牌或 Grant 已过期 |
| `CapabilityDenied` | 403 | 当前 Actor 在目标资源上无所需权限 |
| `SpaceFrozen` | 403 | Space 处于冻结/归档状态，拒绝写入 |
| `NotFound` | 404 | 目标 DID、Space 或 Entity 不存在 |
| `CASConflict` | 409 | `expected_state_hash` 不匹配（并发冲突） |
| `EpochMismatch` | 409 | MLS Epoch 版本过期，需拉取最新状态 |
| `QuotaExceeded` | 413 | Blob 存储或 Space 数据量超出 Policy 配额 |
| `RateLimited` | 429 | 请求频率超限，应遵守 `retry_after_ms` |
| `UnknownDID` | 422 | 提交的 DID 无法在任何 Registry 中解析 |
| `SchemaViolation` | 422 | Op 的 payload 不符合当前 Space 的 Schema 约束 |
| `InternalError` | 500 | 节点内部错误 |

客户端在收到 `429 RateLimited` 时 MUST 遵守 `retry_after_ms` 字段指定的退避间隔。在收到 `409 CASConflict` 或 `409 EpochMismatch` 时 SHOULD 拉取最新状态后使用指数退避重试。

## 16. Blob API

### 16.1 上传接口
**`POST /api/v1/blob/upload`**
- **Content-Type**: `application/octet-stream` 或 `multipart/form-data`
- **描述**：客户端上传二进制文件，服务端计算内容哈希后返回地址。
- **响应 (Response)**：
  ```json
  {
    "blob_ref": "cx:blob:sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "size": 102450,
    "mimetype": "image/png"
  }
  ```

### 16.2 哈希规范
- 算法：**SHA-256**。
- 地址格式：`cx:blob:sha256:<hex_digest>`。
- 校验规则：客户端在下载 Blob 后 MUST 本地计算 SHA-256 并与地址中的摘要比对，若不一致 MUST 丢弃该 Blob。

### 16.3 生命周期与 GC
- Blob 必须被至少一个 Entity 的 `attachments` 或 `content` 字段引用才被视为"活跃"。
- Blob Store MAY 对超过 `retention_policy` 周期且无任何引用的孤儿 Blob 执行垃圾回收 (GC)。
- Blob 删除前 SHOULD 有一个宽限期 (Grace Period)，防止上传与引用之间的网络延迟导致误删。
