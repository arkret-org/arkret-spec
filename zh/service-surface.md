# Service Surface And Bootstrap Draft

## 1. 目标

如果只有对象模型、同步原则和 capability，而没有最小线级服务面，协议仍然很难真正互操作。

因此 Contrix 初版需要定义：

- repo 如何收发 commit / op
- relay 如何做 workspace firehose 与 backfill
- index 如何做查询与 inbox / notification 物化
- blob 如何上传与校验
- invite / grant 如何参与首次加入工作区

本文给出一个 **最小可互操作服务面** 草案。  
实现可以不是 HTTP，也可以不是 XRPC，但必须提供语义等价的接口。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

DID Document SHOULD 只负责：

- 声明 repo / relay / index / blob / capability 服务入口
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
GET /xrpc/cx.server.describe
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

## 4. Repo Surface

repo 至少应提供以下语义：

### 4.1 描述 repo

```text
GET /xrpc/cx.repo.describe
```

返回：

- `repo_did`
- 当前 head commit
- 支持的签名算法
- 是否支持批量取 op

### 4.2 列出 commit

```text
GET /xrpc/cx.repo.listCommits?cursor=<cursor>&limit=<n>
```

用于：

- actor 历史恢复
- 审计回放
- 补齐缺失 commit

### 4.3 获取单个 commit

```text
GET /xrpc/cx.repo.getCommit?commit_id=<id>
```

### 4.4 批量获取 op

```text
POST /xrpc/cx.repo.getOps
```

请求体可携带一组 `op_id`。

### 4.5 提交 commit

```text
POST /xrpc/cx.repo.submitCommit
```

要求：

- 同一个 `commit_id` 重复提交相同字节内容 MUST 幂等成功
- 同一个 `commit_id` 若内容不同 MUST 拒绝
- repo SHOULD 返回新的 head 与已接受 op 列表

## 5. Relay Surface

relay 至少应提供以下语义：

### 5.1 描述 relay

```text
GET /xrpc/cx.relay.describe
```

### 5.2 workspace firehose 订阅

```text
GET /xrpc/cx.relay.subscribe?workspace_id=<id>&cursor=<cursor>
```

实现可用：

- SSE
- WebSocket
- 长轮询

但必须提供稳定 cursor 语义。

### 5.3 增量回补

```text
GET /xrpc/cx.relay.backfill?workspace_id=<id>&cursor=<cursor>&limit=<n>
```

### 5.4 snapshot 入口

```text
GET /xrpc/cx.relay.getSnapshotHead?workspace_id=<id>
```

用于拿到当前推荐 snapshot manifest。

## 6. Index Surface

index 至少应提供以下语义：

### 6.1 描述 index

```text
GET /xrpc/cx.index.describe
```

### 6.2 获取对象当前态

```text
GET /xrpc/cx.index.getObject?ref=<stable-ref>
```

### 6.3 结构化查询

```text
POST /xrpc/cx.index.query
```

其请求体 SHOULD 接受：

- `kind`
- 过滤条件
- 排序
- cursor
- limit

### 6.4 thread / topic 查询

```text
GET /xrpc/cx.index.getThread?topic_id=<id>&cursor=<cursor>
```

### 6.5 inbox / notification 查询

```text
GET /xrpc/cx.index.getNotifications?cursor=<cursor>&state=unread
```

```text
GET /xrpc/cx.index.getInbox?scope=<scope>&cursor=<cursor>
```

## 7. Blob Surface

blob 服务至少应提供：

### 7.1 上传 blob

```text
POST /xrpc/cx.blob.upload
```

返回：

- `blob_cid`
- `sha256`
- `size`

### 7.2 查询 blob 头信息

```text
HEAD /xrpc/cx.blob.get?blob_cid=<cid>
```

### 7.3 下载 blob

```text
GET /xrpc/cx.blob.get?blob_cid=<cid>
```

blob 校验 MUST 基于内容哈希，而不是单一 URL。

## 8. Capability / Invite Surface

虽然 grant / revoke / invite 本身也是对象或 op，但服务层仍需要可查询面。

至少建议提供：

```text
GET /xrpc/cx.authz.getEffectiveGrants?workspace_id=<id>&subject=<did>
```

```text
GET /xrpc/cx.authz.getInvites?workspace_id=<id>&subject=<did-or-handle>
```

```text
POST /xrpc/cx.authz.check
```

`check` 接口适合：

- repo 接收写入前预检查
- relay 分发前快速过滤
- client 发送前本地 UX 提示

## 9. Workspace Bootstrap Flow

初版推荐的首次加入流程：

1. 用户输入 handle、DID 或 workspace link
2. 客户端解析 DID，并完成 handle 双向校验
3. 从 DID Document 发现 repo / relay / index / blob / authz 服务
4. 拉取与该 principal 相关的 invite / grant 视图
5. 获取 workspace metadata 与 snapshot head
6. 下载 snapshot manifest 与 chunk
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

## 11. 传输安全与密文

服务面 SHOULD 区分：

- 路由所需元数据
- 可选端到端密文内容

如果 payload 已按 `policy.encryption_profile` 加密，则：

- repo / relay / index MAY 不解密正文
- 但仍 SHOULD 保留 hash、cursor、causal 与目标引用

## 12. 初版设计决定

当前草案建议固定：

- 定义最小 repo / relay / index / blob / authz 服务面
- `xrpc` 风格路径只是建议，语义等价最重要
- 写接口必须幂等
- bootstrap 必须覆盖 invite / grant / snapshot / backfill
- 服务必须公开 reducer / schema / feature profile

## 13. 后续待细化

下一轮仍需继续补：

- 每个接口的正式请求/响应 schema
- cursor 编码
- firehose 帧格式
- 错误码与重试语义
- auth token 或签名请求格式
