# Federation Draft

## 1. 目标

Contrix 是去中心化协议，不同用户或组织各自运行受控 Principal Server。当来自不同域的 Actor 需要在同一个 Space 中协作时，Principal Server 之间需要一套**跨域联邦协议 (Federation Protocol)**，定义：

- 节点之间如何互相发现与认证
- 如何安全交换签名操作 (Op) 与 Commit
- 如何处理跨域加入 Space 的请求
- 如何在异构网络中维持因果一致性

## 2. 设计原则

### 2.1 Repo 是信任锚点

跨域协作的信任不来自"服务器管理员彼此认识"，而来自**每个 Actor 的 Repo 都是密码学可验证的**。任何节点在接收到来自外部域的 Op 时，可以独立验证签名、DID、因果链，不需要信任对方服务器。

### 2.2 Principal Server 是受控同步边界，不是全局权威

联邦场景中没有独立第三方分发服务器角色。Space 范围传播由参与方 Principal Server 之间的 federation transaction 完成。Principal Server 不能伪造、篡改或选择性隐藏已签名的 Op；任何参与者都可以通过直接查询源 Repo 或其他受信 Principal Server 交叉验证历史。

### 2.3 最终一致性优于强一致性

跨域网络延迟不可预测。联邦协议不追求全局共识或全局排序，而是依赖已有的因果排序 (`deps` + `hlc`) 和确定性 Reducer 实现**最终一致性收敛**。

## 3. 节点间认证

### 3.1 基于 DID 的服务器身份

每个 Principal Server / Repo / Index 节点 MUST 拥有自己的 DID（通常是 `did:web`），并在其 DID Document 中声明 Service Endpoints：

```json
{
  "id": "did:web:server.acme.example.com",
  "service": [
    {
      "id": "#contrix-principal-server",
      "type": "ContrixPrincipalServer",
      "service_endpoint": "https://server.acme.example.com/api/v1"
    }
  ],
  "verification_method": [
    {
      "id": "#server-key-1",
      "type": "Ed25519VerificationKey2020",
      "public_key_multibase": "z6Mkf..."
    }
  ]
}
```

### 3.2 请求签名

节点间的 HTTP 请求 MUST 使用 [HTTP Message Signatures (RFC 9421)](https://datatracker.ietf.org/doc/html/rfc9421) 进行签名。接收方通过发送方 DID Document 中的公钥验证请求的真实性。

签名 MUST 覆盖以下 HTTP 组件：
- `@method`
- `@target-uri`
- `content-digest`（针对有 body 的请求）
- `@authority`

### 3.3 域信任模型

Contrix 不要求全局信任列表。每个节点维护自己的**联邦许可列表 (Federation Allow List)**：

- **开放联邦 (Open)**：接受来自任何域的合法签名请求。适合公共协作场景。
- **受限联邦 (Restricted)**：仅接受来自预配置域列表的请求。适合企业内部或联盟场景。
- **封闭 (Closed)**：不接受任何外部联邦请求。适合纯内部部署。

## 4. Op 交换协议

### 4.1 推送模式 (Push)

当 Actor A（托管在 `server-alpha.com`）向 Space S 提交了新 Op，而 Space S 的另一参与方 Principal Server `server-beta.com` 也服务同一个 Space 时：

1. `server-alpha.com` 检测到新 Op 属于跨域 Space
2. `server-alpha.com` 从 Space policy / membership / service delegation 中解析应接收该 Op 的对端 Principal Server
3. `server-alpha.com` 向 `server-beta.com` 发送推送请求：

```
POST /api/v1/federation/push-ops
Host: server-beta.com
Signature-Input: sig1=("@method" "@target-uri" "content-digest")
Signature: sig1=:base64...:
```

```json
{
  "origin": "did:web:server-alpha.com",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "ops": [
    { /* 完整的 Event Envelope，含签名 */ }
  ]
}
```

4. `server-beta.com` 独立验证每个 Op 的 Actor 签名、Space policy、服务委托和因果链，然后决定是否接受

### 4.2 拉取模式 (Pull / Backfill)

当节点发现自己的因果图中存在缺失（`deps` 引用了本地没有的 Op）时，可以主动向源 Principal Server 或源 Repo 拉取：

```
GET /api/v1/federation/pull-ops?space_id=cx:space:...&after_cursor=...&limit=100
Host: server-alpha.com
```

### 4.3 重复与幂等

- 同一个 `op_id` 的 Op MAY 被多个 Principal Server 推送多次
- 接收方 MUST 以 `op_id` 去重
- 内容相同的重复推送 MUST 幂等接受
- `op_id` 相同但内容不同的推送 MUST 拒绝

## 5. 跨域加入 Space

### 5.1 邀请流程

当 Space S 的管理员邀请外部用户 Bob（Repo / Principal Server 在 `server-beta.com`）时：

1. 管理员提交 `cx.invite.create` Op，`subject_did` 指向 Bob 的 DID
2. 该 Op 通过联邦推送到达 Bob 的 Principal Server / Repo
3. Bob 的客户端发现 Invite，决定接受
4. Bob 的客户端提交 `cx.invite.accept` Op 到自己的 Repo
5. Bob 的 Principal Server 将该 Op 推送给 Space S 的其他参与方 Principal Server
6. 各参与方按 reducer 验证 Invite 有效性并收敛成员状态
7. 若 Space 启用了 E2EE，管理员的客户端构造 MLS `Welcome` 消息发给 Bob

### 5.2 Knock 流程

Bob 也可以主动申请加入：

1. Bob 发现 Space S 的元数据（通过公开的 Space Directory 或链接）
2. Bob 提交 `cx.membership.knock` Op，推送给 Space S 的 shared Space Host 或管理员 Principal Server
3. 接收方验证 knock 的签名有效后，转发给 Space 管理员
4. 管理员审批后提交 `cx.invite.create` + Bob 提交 `cx.invite.accept`

## 6. 联邦级服务发现

### 6.1 Space Host / Sync Endpoint 列表

每个 Space 的 metadata MAY 包含一个 `sync_endpoints` 列表，用于列出被 Space policy 明确委托的 shared Space Host 或组织 Principal Server：

```json
{
  "space_id": "cx:space:01JS0SP000000000000000000",
  "sync_endpoints": [
    {
      "did": "did:web:server-alpha.com",
      "endpoint": "https://server-alpha.com/api/v1",
      "role": "primary"
    },
    {
      "did": "did:web:server-beta.com",
      "endpoint": "https://server-beta.com/api/v1",
      "role": "mirror"
    }
  ]
}
```

### 6.2 Actor Repo 发现

给定一个 Actor 的 DID，其他节点通过解析 DID Document 中的 `#contrix-repo` 服务端点来定位其 Repo：

```
DID Document -> service[type=ContrixRepo] -> service_endpoint
```

## 7. 联邦 API 端点

### 7.1 推送 Op

```
POST /api/v1/federation/push-ops
```

### 7.2 拉取 Op

```
GET /api/v1/federation/pull-ops?space_id=<id>&after_cursor=<cursor>&limit=<n>
```

### 7.3 查询 Space 成员

```
GET /api/v1/federation/space-members?space_id=<id>
```

### 7.4 验证 Actor

```
POST /api/v1/federation/verify-actor
```

请求体包含 Actor DID 和待验证的签名，用于在没有本地 DID 缓存时请求对端帮忙校验。

## 8. 安全考量

### 8.1 反洪泛 (Anti-Flooding)

联邦端点 MUST 实施严格的速率限制。恶意节点可能通过大量推送无效 Op 来消耗对端资源。建议：
- 按 `origin` DID、来源 IP hash、endpoint 和 Space id 做独立限速
- 对来自未知域的首次请求做降级处理（先验证后全速）
- 限制单次请求体积和批次大小，超阈值先进入 `rate_limited`

### 8.2 选择性拒绝

节点有权选择性拒绝来自特定域的联邦请求（参见 3.3 节的域信任模型），这不违反协议。被拒绝的域可以通过其他途径（如用户直接下载 Repo 数据）获取信息。

### 8.3 元数据与身份校验

联邦请求在鉴权前应执行签名与服务源一致性检查：

- `origin`/`destination` service DID 必须与请求签名与 `target-uri` 一致；
- 对签名失败、签名域缺失、`origin` 不在可接受集合的来源进入 `quarantine` 或 `hard_deny`；
- 未通过身份校验的错误响应 MUST 不泄露可验证/不可验证来源的差异。

### 8.4 元数据泄露防护

在联邦推送 E2EE Space 的 Op 时，密文信封 `encrypted_payload` 对联邦中间节点同样不可见。联邦协议传输的只有明文路由元数据和不透明的密文块。

### 8.5 重放与异常模式防护

节点 MUST 将 `txn_id` 与请求 canonical hash 绑定后执行幂等和重放检查：

- `txn_id` 相同但 hash 不同 MUST 拒绝；
- `txn_id` 相同且 hash 相同 MAY 幂等接受；
- 同源短时重复失败、失败率异常上升时 MUST 暂停该源并返回 `rate_limited`/`temporarily_unavailable`。

### 8.6 威胁映射落地

本协议在服务器端应默认支持 [server-threat-model.md](../security/server-threat-model.md) 中“可借鉴项”，特别是：

- 开放联邦入口阻断；
- 攻击来源限流与排队；
- 重放检测与 quarantine；
- 统一回执和拒绝语义避免枚举泄漏。

## 9. 后续待细化

- 联邦级 Snapshot 同步与校验
- 多 Principal Server 之间的 Gossip / batch sync 优化
- 跨域 Space 的权限委托与级联
- 联邦节点的声誉系统（可选）
