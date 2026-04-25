# Identity Layer Draft

## 1. 目标

Contrix New 的身份层采用 **DID 作为稳定身份根**，并参考 atprotocol 的“Handle 入口 + DID 根锚 + 文档服务发现”模式，但在 DID 生成、密钥轮换与恢复规则上做出自己的定义。

这一层必须解决：

- 稳定标识人类、组织、agent、服务
- 把 DID 的“出生锚点”与后续控制密钥区分开
- 允许 handle 迁移而不破坏历史引用
- 支持设备委托、agent 委托、密钥恢复与密钥轮换
- 在公钥丢失、泄露、例行轮换时，尽量保持 DID 不变

## 2. 基本原则

### 2.1 所有稳定主体引用 MUST 使用 DID

协议中的主体引用 MUST 使用 DID，而不是 Handle。

包括：

- 对象创建者
- 对象修改者
- grant issuer
- grant subject
- run actor
- memory author
- 服务节点主体

### 2.2 Handle 只是人类入口，不是主键

Handle 可以变更、迁移、冻结、重新绑定，因此：

- 历史 op 不得以 Handle 作为身份依据
- ACL / capability 不得绑定到 Handle
- 对象 `created_by` / `updated_by` 必须记录 DID

### 2.3 DID Document 是服务发现根入口

Contrix 客户端在拿到 DID 后，SHOULD 从 DID Document 发现：

- identity registry endpoints
- repo endpoint
- relay endpoints
- index endpoints
- blob endpoint
- capability endpoint
- notification endpoint

### 2.4 DID 应持久，密钥可以轮换

Contrix 对 `did:uuid` 的核心立场是：

- 普通密钥轮换 MUST NOT 导致 DID 变化
- DID 中嵌入的哈希锚定的是 **初始锚点公钥**，不是当前正在使用的控制公钥
- 当前控制公钥是否可信，取决于从初始锚点出发的可验证历史链，而不是“当前公钥必须和 DID 里的哈希直接相等”

也就是说，Contrix 采用：

- **初始匹配**
- **过程授权**

的身份验证模型。

## 3. Contrix 原生 DID 方法

## 3.1 默认 DID 方法

Contrix 的默认原生 DID 方法定义为：

- `did:uuid:<uuid-v8>`

其中：

- `did:uuid` 是方法名
- `<uuid-v8>` 是按 Contrix 规则生成的 UUID v8 文本表示

初版建议：

- MUST 支持 `did:uuid`
- SHOULD 支持 `did:web` 作为组织/服务互操作方法
- MAY 支持 `did:plc`
- MAY 支持 `did:key` 用于测试或临时主体

## 3.2 文本格式

`<uuid-v8>` 的 canonical 文本格式 SHOULD 使用：

- 小写十六进制
- 标准 UUID 连字符格式 `8-4-4-4-12`

示例：

```text
did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992
```

## 3.3 DID 与初始锚点公钥的关系

Contrix DID 不是随机号。  
它 MUST 由以下三部分共同决定：

1. 生成时间戳
2. 哈希算法标识
3. **初始锚点公钥** 的哈希片段

这意味着：

- 不能只改变时间戳而保持哈希算法标识和初始锚点哈希片段不变来制造“新身份”
- DID 的 74 位哈希片段记录的是身份诞生时刻的锚点指纹
- 后续控制公钥可以变化，只要变化过程有完整的授权证据链
- 只有在 **没有有效恢复路径且决定重建身份** 时，才 MAY 生成新的 DID

## 4. UUID v8 位布局

Contrix 默认 DID 的 `<uuid-v8>` 使用 128 位 UUID v8，自定义位布局如下。

### 4.1 位段定义

- 前 44 位：Unix 毫秒时间戳
- 接下来的 4 位：Hash Algorithm ID
- 接下来的 4 位：Version，固定为 `0x8`
- 接下来的 12 位：初始锚点公钥哈希起始片段
- 接下来的 2 位：Variant，固定为 `0b10`
- 最后的 62 位：初始锚点公钥哈希后续片段

换言之：

- 时间戳占 44 位
- 哈希算法标识占 4 位
- 除去 UUID 标准要求的 Version 与 Variant 位后，其余可用位全部用于承载公钥哈希
- 公钥哈希总共占 74 位

## 4.2 大端序要求

在处理整个 128 位 UUID 时，Contrix MUST 使用 **大端序** 进行位填充、解析与比对。

这条规则是强制性的。  
否则不同语言在把 128 位 UUID 与字节数组互转时，可能出现顺序不一致，导致 DID 生成或验证失败。

具体要求：

- 时间戳按 44 位大端序写入最高位
- Hash Algorithm ID 紧跟时间戳写入
- 公钥哈希位段按从高位到低位顺序连续填充
- Version 和 Variant 位必须被明确跳过，不能被哈希填充覆盖

## 4.3 位编号

建议把 UUID 128 位按从高位到低位编号为 `bit 0 .. bit 127`。

位映射如下：

- `bit 0 .. bit 43`：Unix 毫秒时间戳
- `bit 44 .. bit 47`：Hash Algorithm ID
- `bit 48 .. bit 51`：Version = `1000`
- `bit 52 .. bit 63`：公钥哈希 `hash[0..11]`
- `bit 64 .. bit 65`：Variant = `10`
- `bit 66 .. bit 127`：公钥哈希 `hash[12..73]`

## 5. Hash Algorithm ID 与哈希输入

## 5.1 初版 Hash Algorithm ID 注册表

初版建议定义如下：

- `0x0`：保留
- `0x1`：SHA-256
- `0x2`：SHA-512/256
- `0x3`：SHA3-256
- `0x4`：BLAKE3-256
- `0x5 .. 0xE`：保留给后续规范
- `0xF`：实验/私有实现

## 5.2 初始锚点公钥

每个 `did:uuid` DID Document MUST 指定一个唯一且不可变的 **初始锚点公钥**。

建议字段名：

- `inception_key`

它的值应指向 `verificationMethod` 中的某个 key id。

该初始锚点公钥用于：

- 生成 DID 中的公钥哈希片段
- 作为身份历史的永久锚点
- 为后续控制密钥链提供最初的可信起点

为了兼容早期草案，实现 MAY 暂时接受：

- `anchor_key`

作为 `inception_key` 的过渡别名，但规范字段名应是 `inception_key`。

## 5.3 哈希输入规则

Contrix DID 里的哈希片段 MUST 来源于 **初始锚点公钥的 canonical 字节表示**，而不是：

- 当前控制公钥
- 整张证书的完整字节流
- 恢复密钥

这样做的原因是：

- DID 需要一个稳定的“出生证指纹”
- 证书的非公钥元数据变化不应无意义地改变 DID
- 后续公钥轮换不应破坏历史身份引用

初版建议 canonical 字节表示如下：

- Ed25519：32 字节原始公钥
- secp256k1：33 字节压缩 SEC1 公钥
- P-256：33 字节压缩 SEC1 公钥

## 5.4 哈希函数与截断规则

初版建议：

- `Hash Algorithm ID = 0x1`
- 使用 `SHA-256(inception_key_bytes)`
- 从结果中按位截取前 74 位

然后按大端序写入 UUID 的两个哈希位段：

- 先写入 `bit 52 .. bit 63`
- 再跳过 Variant
- 再写入 `bit 66 .. bit 127`

实现 MUST 避开：

- Version 位
- Variant 位

## 5.5 生成约束

生成新的 `did:uuid` DID 时：

- 时间戳 MUST 反映生成时的 Unix 毫秒时间，并被截断到 44 位
- Hash Algorithm ID MUST 与实际采用的哈希函数匹配
- 74 位哈希片段 MUST 来自该初始锚点公钥的 canonical 字节表示

以下情况 MUST 被视为无效：

- 只改变时间戳，不改变 Hash Algorithm ID 与 74 位初始锚点哈希片段
- Hash Algorithm ID 与实际采用的哈希函数不一致
- 使用小端方式填充导致位序错误

普通密钥轮换 MUST NOT 重新生成 DID。  
只有在身份不可恢复且决定重建时，才 MAY 生成新的 DID。

## 6. DID Document 模型

## 6.1 最小字段

Contrix DID Document 至少应包含：

- `id`
- `alsoKnownAs`
- `inception_key`
- `verificationMethod`
- `authentication`
- `assertionMethod`
- `service`
- `key_log`

## 6.2 建议的 service type

初版建议定义以下服务类型：

- `ContrixIdentityRegistry`
- `ContrixRepo`
- `ContrixRelay`
- `ContrixIndex`
- `ContrixBlob`
- `ContrixCapabilities`
- `ContrixNotifications`

### 6.2.1 身份文档由谁负责存储

Contrix 不要求把 DID 文档直接写进区块链。  
初版建议采用：

- **principal 自己保留签名过的身份状态副本**
- **开放的 `ContrixIdentityRegistry` 节点网络保存可解析副本**
- **任意第三方可运行 read replica / audit replica**

也就是说：

- principal 自己的 repo SHOULD 保留身份相关操作与 checkpoint，便于审计与恢复
- 面向全网解析的当前 DID 文档 SHOULD 由多个 `ContrixIdentityRegistry` 节点共同托管
- 客户端 MAY 从 registry、replica、本地 cache、导出的 checkpoint 中读取，但都必须重新验证签名链

这使“存储责任”被拆成三层：

1. actor 自己保留原始签名状态
2. registry 提供在线解析与写入入口
3. replica 提供高可用读取与外部审计

### 6.2.2 如何防止被随意乱写入

不上链不等于谁都能改。

Contrix 对 DID 文档更新的保护依赖：

- DID 自描述锚点：DID 必须能验证到 `inception_key`
- append-only 身份日志：`key_log` 不可回写
- 当前控制权证明：更新必须由当时有效的控制密钥或恢复策略授权
- 顺序约束：每次 DID 更新 SHOULD 带 `prev_event_hash` 与单调递增 `seq`
- 多副本校验：registry 和 replica 都必须独立验证事件

建议每次身份更新都封装为 `did_op`：

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "seq": 12,
  "prev_event_hash": "bafy...",
  "patch": {
    "add_authentication": [
      "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-4"
    ]
  },
  "proofs": [
    {
      "verificationMethod": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "jws": "..."
    }
  ]
}
```

Registry MUST 拒绝：

- 签名不成立的更新
- `seq` 回退或重复但内容不一致的更新
- `prev_event_hash` 不匹配当前 head 的更新
- 不能从 `inception_key` 推导出授权链的更新

因此，单个恶意 registry 可以：

- 拒绝服务
- 延迟服务
- 谎报旧状态

但不能让一个**无效更新**在正确实现的客户端里变成有效身份状态。

### 6.2.3 如何在不引入区块链的情况下做到快速写入和读取

Contrix 不追求“全网全局共识链”，只追求：

- **每个 DID 自己的 append-only 日志有序**
- **日志可被多个 registry / replica 快速复制**

因此它的性能模型更接近：

- 目录服务
- 透明日志
- witness quorum

而不是区块链。

建议：

- 写入走普通 HTTPS / XRPC 请求
- writer 同时提交给 `n` 个 registry / witness 节点
- 当获得至少 `k-of-n` 个有效 receipt 后，视为该 DID 更新已提交
- 读取可以来自任意 registry、read replica、本地 cache 或 CDN

这样做的好处是：

- 写入延迟接近普通多副本数据库，而不是区块出块时间
- 读取可以本地化、缓存化、CDN 化
- 不需要让全网所有 DID 共享一个全局排序器

如果客户端需要强 read-after-write，一种简单规则是：

- 优先查询刚返回 receipt 的 registry
- 或在读取时带上自己期望的 `min_seq` / `expected_head`

### 6.2.4 Registry、Witness 与 Replica 的建议角色

为避免重走单目录中心化的老路，Contrix SHOULD 区分：

- `registry writer`
- `witness`
- `read replica`

其中：

- `registry writer`：接收 DID 更新，做主验证与分发
- `witness`：不一定承担读接口，但会为某个 head 出具 receipt
- `read replica`：主打可读性、缓存、审计，不一定参与写入确认

初版最稳妥的方向是：

- 写确认至少要求多个独立 operator 的 receipt
- 读解析允许只读 replica 横向扩展

这比“单一主目录 + 被动镜像”的模式更去中心化。

## 6.3 当前控制密钥与 `key_log`

Contrix SHOULD 把 DID Document 拆成两类信息：

1. **不随轮换改变的锚点信息**
2. **会随轮换改变的当前控制信息**

其中：

- `inception_key` 是不可变锚点
- `authentication` / `assertionMethod` 表示当前有效控制密钥集合
- `key_log` 是 append-only 的密钥事件日志，用于证明“当前控制密钥是如何从初始锚点合法演化而来”

这意味着：

- 当前控制密钥不需要直接与 DID 中的哈希片段相等
- 但它 MUST 能通过 `key_log` 被追溯到 `inception_key`

## 6.4 `key_log` 事件模型

初版建议 `key_log` 支持以下事件类型：

- `inception`
- `rotate`
- `recover`
- `deactivate`

建议字段：

```json
{
  "event_id": "cx:keyevt:01JS0KE000000000000000000",
  "seq": 2,
  "type": "rotate",
  "performed_at": "2026-04-25T08:00:00Z",
  "prev_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "next_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
  ],
  "authorized_by": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "reason": "routine_rotation",
  "proof": {
    "type": "JCSDetachedJWS",
    "verificationMethod": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
    "jws": "..."
  }
}
```

规则：

- `seq` MUST 单调递增
- 旧事件 MUST NOT 被重写
- 每个 `rotate` / `recover` 事件 MUST 由当时有效的控制密钥集合或恢复策略授权
- `deactivate` 事件表示该 DID 不再接受新的控制写入

## 6.5 恢复模型

为处理“当前私钥丢失但 DID 仍需保留”的场景，Contrix SHOULD 支持恢复机制。

建议字段：

- `recovery_keys`
- 或 `recovery_policy`

恢复语义：

- 若当前控制密钥丢失，但恢复密钥仍可用，则 DID MUST 保持不变
- 新控制密钥通过 `key_log.type = recover` 事件写入
- 该 `recover` 事件必须能被恢复策略验证

若既没有当前控制密钥，也没有有效恢复路径，则该 DID SHOULD 被视为：

- `unrecoverable`
- 或 `deactivated`

## 6.6 例外性的身份重建

`did:uuid` 的常规规则是：

- **换公钥，不换 DID**

但在以下例外情况下，新的 DID MAY 被创建：

- 旧 DID 已不可恢复
- 操作方明确决定放弃旧 DID 并重建身份
- 需要在产品或社交层声明“新身份承接旧身份”

只有在这种 **身份重建** 场景下，才建议使用：

- `superseded_by`
- `supersedes`

它们不应用于日常密钥轮换。

如果旧 DID 文档还能被合法更新，并设置了 `superseded_by`，则该文档 SHOULD 进入 locked 状态。  
但对不可恢复 DID，客户端 MUST 不假设一定能获得双向链接。

## 6.7 DID Document 示例

```json
{
  "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "inception_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
  "verificationMethod": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mki..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mks..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mkr..."
    }
  ],
  "authentication": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
  ],
  "assertionMethod": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
  ],
  "recovery_keys": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1"
  ],
  "key_log": [
    {
      "event_id": "cx:keyevt:01JS0KE000000000000000000",
      "seq": 0,
      "type": "inception",
      "performed_at": "2026-04-25T08:00:00Z",
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ]
    },
    {
      "event_id": "cx:keyevt:01JS0KF000000000000000000",
      "seq": 1,
      "type": "rotate",
      "performed_at": "2026-05-01T09:00:00Z",
      "prev_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ],
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
      ],
      "authorized_by": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#inception-1"
      ],
      "reason": "routine_rotation"
    },
    {
      "event_id": "cx:keyevt:01JS0KG000000000000000000",
      "seq": 2,
      "type": "recover",
      "performed_at": "2026-05-10T11:00:00Z",
      "prev_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-2"
      ],
      "next_keys": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-3"
      ],
      "authorized_by": [
        "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#recovery-1"
      ],
      "reason": "key_loss"
    }
  ],
  "service": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#repo",
      "type": "ContrixRepo",
      "serviceEndpoint": "https://alice.example.com/cx/repo"
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#relay",
      "type": "ContrixRelay",
      "serviceEndpoint": "https://relay.example.net/cx"
    }
  ]
}
```

## 7. Handle 设计

## 7.1 与 atprotocol 的关系

Contrix 在 handle 模型上大致借鉴 atprotocol：

1. handle 与 DID 分离
2. handle 是用户可见标识
3. DID 文档中显式声明 handle 绑定
4. 解析时必须做双向验证

## 7.2 Handle 形式

初版建议 handle 采用 DNS 风格主机名：

- `alice.example.com`
- `ops.example.com`
- `agent.release.example.com`

## 7.3 DID Document 中的 handle 绑定

建议使用：

- `alsoKnownAs: ["contrix://alice.example.com"]`

其中：

- `contrix://<handle>` 是 handle 的 canonical URI 形式

一个 DID 文档 SHOULD 至少有一个主 handle。  
如需保留历史别名，可以在 `alsoKnownAs` 中保留多个 handle URI。

## 7.4 Identity Profile 中的显示字段

为了让 UI 更方便使用，Contrix SHOULD 允许 identity profile 包含：

- `primary_handle`
- `display_name`
- `previous_handles`

其中：

- `primary_handle` 是当前默认展示给用户的 handle
- `previous_handles` 用于可选展示历史迁移信息

## 7.5 Handle 解析

Handle 解析建议采用与 atprotocol 接近的双通道机制：

1. DNS TXT
2. HTTPS well-known

推荐优先顺序：

1. 查询 `_contrix.<handle>` TXT
2. 若不存在，再读取 `https://<handle>/.well-known/contrix-did`

Well-known 示例：

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992"
}
```

## 7.6 双向验证

Handle 解析成功后，客户端 MUST 继续验证 DID 文档中的 `alsoKnownAs` 是否包含：

- `contrix://<handle>`

若未完成双向验证，客户端 MUST 不把该 handle 当作可信绑定。

## 8. Identity Profile

为避免把协作细节全部压进 DID Document，Contrix SHOULD 允许一个扩展 identity profile。

建议入口：

```text
GET /.well-known/contrix-identity.json
```

示例：

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "kind": "user",
  "primary_handle": "alice.example.com",
  "display_name": "Alice",
  "previous_handles": [
    "alice-old.example.com"
  ],
  "repo_endpoint": "https://alice.example.com/cx/repo",
  "relay_endpoints": [
    "https://relay.example.net/cx"
  ],
  "index_endpoints": [
    "https://index.example.net/cx"
  ],
  "blob_endpoint": "https://blob.example.net/cx",
  "capability_endpoint": "https://authz.example.net/cx",
  "updated_at": "2026-04-25T08:00:00Z"
}
```

## 9. 密钥与恢复模型

主体身份不等于某一台设备或某一个执行进程。

初版建议区分：

- inception key
- principal signing key
- device key
- delegated agent key
- recovery key
- ephemeral execution key

### 9.1 Inception Key

用于：

- 生成 `did:uuid`
- 作为身份历史的永久锚点
- 为后续 `key_log` 提供起点

该 key 的公开部分 MUST 永久可验证。  
它 MAY 不再作为当前活跃控制密钥使用。

### 9.2 Principal Signing Key

用于：

- 发布正式身份文档
- 执行正常的控制密钥轮换
- 签发高权限 capability

### 9.3 Device Key

用于：

- 日常 commit / op 签名
- 客户端同步认证

### 9.4 Delegated Agent Key

用于：

- 长生命周期 agent
- 服务机器人
- CI / automation

它 MUST 携带作用域与失效时间。

### 9.5 Recovery Key

用于：

- 当前控制密钥丢失后的恢复
- 高风险泄露后的强制切换
- 执行 `key_log.type = recover`

恢复密钥 SHOULD 与日常控制密钥隔离存储。

### 9.6 Ephemeral Execution Key

用于：

- 某次 run
- 某次自动化任务
- 某个短时容器或沙箱执行实例

## 10. 设备与 agent 委托

设备和 agent 委托至少需要表达：

- `issuer`
- `subject_key`
- `subject_did` 或执行主体
- `scope`
- `not_before`
- `expires_at`
- `revocation_ref`

## 11. 验证规则

任何接收写入的 Contrix 节点，至少应校验：

1. actor 是合法 DID
2. DID 文档可成功解析
3. `did:uuid` 的 UUID v8 位布局合法
4. DID 中嵌入的 Hash Algorithm ID 是已知且受支持的
5. 按该 Hash Algorithm ID 指定的哈希函数，对文档中的 `inception_key` 重新哈希后，得到的前 74 位片段与 DID 中的一致
6. `key_log` 是 append-only、`seq` 单调、旧事件未被重写
7. 当前 `authentication` / `assertionMethod` 中的控制密钥，能够通过有效的 `key_log` 从 `inception_key` 推导出来
8. 每个 `rotate` / `recover` 事件都由当时有效的控制密钥集合或恢复策略授权
9. 若存在 `deactivate` 事件，则后续新的控制写入 MUST 被拒绝
10. 若通过 device / agent / execution key 进行签名，则委托链完整
11. 若 DID 状态来自 registry / replica，则其 `head_event_hash` 与 receipt 集合摘要没有自相矛盾

注意：

- DID 中的哈希片段只要求与 `inception_key` 一致
- 它不要求与“当前活跃控制密钥”直接一致

## 12. 初版设计决定

当前草案建议固定：

- 默认 DID 方法为 `did:uuid`
- `did:uuid` 基于自定义 UUID v8
- UUID 中包含 44 位毫秒时间戳、4 位 Hash Algorithm ID、74 位 **初始锚点公钥** 哈希片段
- 哈希填充与验证 MUST 使用大端序
- 普通密钥轮换 MUST NOT 改变 DID
- 当前控制密钥可以与 DID 中的哈希片段不直接匹配，但必须能通过 `key_log` 从 `inception_key` 被验证出来
- `key_log` 是密钥轮换与恢复的标准证明链
- `superseded_by / supersedes` 只用于不可恢复后的例外性身份重建，不用于日常轮换
- handle 模型参考 atprotocol，使用 `alsoKnownAs + primary_handle`

## 13. 后续待细化

下一轮仍需补充：

- `did:uuid` 解析与分发的线级协议
- `key_log` 事件与 proof envelope 的正式 schema
- `recovery_policy` 的正式语法
- 大型实现中的日志压缩 / checkpoint 规则
- Handle ABNF
