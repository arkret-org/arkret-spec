# Identity Layer Draft

## 1. 目标

Contrix New 的身份层采用 **DID 作为稳定身份根**，并参考 atprotocol 的“Handle 入口 + DID 根锚 + 文档服务发现”模式，但在 DID 生成与迁移规则上做出自己的定义。

这一层必须解决：

- 稳定标识人类、组织、agent、服务
- 绑定身份锚定公钥与服务入口
- 允许 handle 迁移而不破坏历史引用
- 支持设备委托、agent 委托、密钥恢复与身份迁移
- 在身份锚定公钥变更时，生成新的 DID，并把新旧身份通过文档链起来

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

- repo endpoint
- relay endpoints
- index endpoints
- blob endpoint
- capability endpoint
- notification endpoint

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

## 3.3 DID 与锚定公钥的关系

Contrix DID 不是随机号。  
它 MUST 由以下两部分共同决定：

1. 生成时间戳
2. 身份锚定公钥的哈希片段

这意味着：

- 不能只改变时间戳而保持公钥哈希片段不变来制造一个“新身份”
- 如果身份锚定公钥改变，则 DID 也必须改变
- 如果只是重新签发证书，但锚定公钥未变，则 DID MUST NOT 改变

## 4. UUID v8 位布局

Contrix 默认 DID 的 `<uuid-v8>` 使用 128 位 UUID v8，自定义位布局如下。

### 4.1 位段定义

- 前 48 位：Unix 毫秒时间戳
- 接下来的 4 位：Version，固定为 `0x8`
- 接下来的 4 位：Algorithm ID
- 接下来的 8 位：公钥哈希起始片段
- 接下来的 2 位：Variant，固定为 `0b10`
- 最后的 62 位：公钥哈希后续片段

换言之：

- 时间戳占 48 位
- 算法标识占 4 位
- 公钥哈希总共占 70 位

## 4.2 大端序要求

在处理整个 128 位 UUID 时，Contrix MUST 使用 **大端序** 进行位填充与比对。

这条规则是强制性的。  
否则不同语言在把 128 位 UUID 与字节数组互转时，可能出现顺序不一致，导致 DID 生成或验证失败。

具体要求：

- 时间戳按 48 位大端序写入高位
- Algorithm ID 与哈希位段也按从高位到低位的顺序连续填充
- Version 和 Variant 位必须被明确跳过，不能被哈希填充覆盖

## 4.3 位编号

建议把 UUID 128 位按从高位到低位编号为 `bit 0 .. bit 127`。

位映射如下：

- `bit 0 .. bit 47`：Unix 毫秒时间戳
- `bit 48 .. bit 51`：Version = `1000`
- `bit 52 .. bit 55`：Algorithm ID
- `bit 56 .. bit 63`：公钥哈希 `hash[0..7]`
- `bit 64 .. bit 65`：Variant = `10`
- `bit 66 .. bit 127`：公钥哈希 `hash[8..69]`

## 5. Algorithm ID 与哈希输入

## 5.1 初版 Algorithm ID 注册表

初版建议定义如下：

- `0x0`：保留
- `0x1`：Ed25519
- `0x2`：secp256k1
- `0x3`：P-256
- `0x4 .. 0xE`：保留给后续规范
- `0xF`：实验/私有实现

## 5.2 身份锚定公钥

每个 `did:uuid` DID Document MUST 指定一个唯一的 **身份锚定公钥**。

建议字段名：

- `anchor_key`

它的值应指向 `verificationMethod` 中的某个 key id。

该锚定公钥用于：

- 生成 DID 中的公钥哈希片段
- 作为身份迁移与验证的根锚

## 5.3 哈希输入规则

Contrix DID 里的哈希片段 MUST 来源于 **身份锚定公钥的 canonical 字节表示**，而不是整张证书的完整字节流。

这样做的原因是：

- 证书的非公钥元数据变化不应无意义地改变 DID
- 只有锚定公钥变化才应触发 DID 变化

初版建议 canonical 字节表示如下：

- Ed25519：32 字节原始公钥
- secp256k1：33 字节压缩 SEC1 公钥
- P-256：33 字节压缩 SEC1 公钥

## 5.4 哈希函数与截断规则

初版建议：

- 使用 `SHA-256(anchor_key_bytes)`
- 从结果中按位截取前 70 位

然后按大端序写入 UUID 的两个哈希位段：

- 先写入 `bit 56 .. bit 63`
- 再跳过 Variant
- 再写入 `bit 66 .. bit 127`

实现 MUST 避开：

- Version 位
- Variant 位

## 5.5 生成约束

生成新的 `did:uuid` DID 时：

- 时间戳 MUST 反映生成时的 Unix 毫秒时间
- Algorithm ID MUST 与锚定公钥算法匹配
- 70 位哈希片段 MUST 来自该锚定公钥

以下情况 MUST 被视为无效：

- 只改变时间戳，不改变 Algorithm ID 与 70 位公钥哈希片段
- Algorithm ID 与实际锚定公钥算法不一致
- 使用小端方式填充导致位序错误

## 6. DID Document 模型

## 6.1 最小字段

Contrix DID Document 至少应包含：

- `id`
- `alsoKnownAs`
- `anchor_key`
- `verificationMethod`
- `authentication`
- `assertionMethod`
- `service`

## 6.2 建议的 service type

初版建议定义以下服务类型：

- `ContrixRepo`
- `ContrixRelay`
- `ContrixIndex`
- `ContrixBlob`
- `ContrixCapabilities`
- `ContrixNotifications`

## 6.3 身份迁移字段

为支持因锚定公钥变化而产生的新 DID，本文档定义两个字段：

- `superseded_by`
- `supersedes`

语义如下：

- `superseded_by`：写在旧 DID 文档中，表示该身份已经被新的 DID 取代
- `supersedes`：写在新 DID 文档中，表示该身份来源于之前的 DID

### 6.3.1 为什么不用 `transfer`

这里不使用 `transfer` 作为正式字段名，是因为它容易被理解成“所有权转让”。  
实际上这里表达的是：

- 密钥泄露后的迁移
- 恢复后的替代身份
- 锚定公钥轮换导致的新 DID

因此 `superseded_by / supersedes` 更准确。

## 6.4 锁死规则

一旦某个 DID 文档设置了 `superseded_by`，该文档就进入 **locked** 状态。

locked 状态下：

- 不允许后续任何字段再发生变化
- 不允许再改 handle
- 不允许再改 service endpoints
- 不允许再改 verificationMethod
- 不允许再改其他扩展字段

实现 SHOULD 在 locked 后返回逻辑上完全相同的文档内容。  
从协议语义上看，locked 文档已经冻结。

## 6.5 新旧 DID 的合法关系

当一个新 DID 文档声称 `supersedes = <old_did>` 时，以下条件 SHOULD 成立：

1. 新 DID 的锚定公钥与旧 DID 不同
2. 新 DID 的 70 位公钥哈希片段与旧 DID 不同
3. 新 DID 的时间戳不早于旧 DID
4. 旧 DID 文档最终应设置 `superseded_by = <new_did>`

也就是说：

- 新 DID 不能只是旧 DID 加一个新时间戳
- 新 DID 必须体现新的锚定公钥身份

## 6.6 DID Document 示例

```json
{
  "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "anchor_key": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#anchor-1",
  "supersedes": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110",
  "verificationMethod": [
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#anchor-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mki..."
    },
    {
      "id": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1",
      "type": "Multikey",
      "controller": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
      "publicKeyMultibase": "z6Mks..."
    }
  ],
  "authentication": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
  ],
  "assertionMethod": [
    "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992#signing-1"
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

旧文档冻结后的示例：

```json
{
  "id": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110",
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ],
  "anchor_key": "did:uuid:0196fd30-70ab-8121-8b12-8f0d7c882110#anchor-1",
  "superseded_by": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992",
  "locked": true
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

## 9. 密钥模型

主体身份不等于某一台设备或某一个执行进程。

初版建议区分：

- identity anchor key
- principal signing key
- device key
- delegated agent key
- ephemeral execution key

### 9.1 Identity Anchor Key

用于：

- 生成 `did:uuid`
- 作为身份迁移的锚点
- 证明新旧 DID 的继承关系

若该 key 改变，则 DID 也必须改变。

### 9.2 Principal Signing Key

用于：

- 发布正式身份文档
- 签发高权限 capability
- 签发设备或 agent 委托

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

### 9.5 Ephemeral Execution Key

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
4. Algorithm ID 与 `anchor_key` 算法一致
5. 文档中的 `anchor_key` 重新哈希后，70 位片段与 DID 中的一致
6. 若文档有 `superseded_by`，则该文档已锁死，不允许再有新变化
7. 若文档有 `supersedes`，则新 DID 不得只是旧 DID 的时间戳变化版本
8. 若通过 device / agent / execution key 进行签名，则委托链完整

## 12. 初版设计决定

当前草案建议固定：

- 默认 DID 方法为 `did:uuid`
- `did:uuid` 基于自定义 UUID v8
- UUID 中包含 48 位毫秒时间戳、4 位 Algorithm ID、70 位锚定公钥哈希片段
- 哈希填充与验证 MUST 使用大端序
- 旧身份文档使用 `superseded_by`
- 新身份文档使用 `supersedes`
- 一旦 `superseded_by` 被设置，旧文档锁死不可再变
- handle 模型参考 atprotocol，使用 `alsoKnownAs + primary_handle`

## 13. 后续待细化

下一轮仍需补充：

- `did:uuid` 解析与分发的线级协议
- `anchor_key` 与文档签名链的正式 schema
- `supersedes/superseded_by` 的互验证流程
- Handle ABNF
