# Key Management

## 1. 目标

身份层定义“谁是主体”，加密层定义“如何保护内容”，但真正能让系统安全运行的是密钥管理。

本文定义 Contrix 的密钥生命周期：

- inception key
- principal signing key
- recovery key
- device key
- session key
- agent key
- MLS KeyPackage
- backup / restore key

## 2. 基本原则

### 2.1 主体不等于设备

一个 DID principal MAY 拥有多个设备。  
设备可以签名、同步和解密，但设备不是协议层主身份。

协议层主体仍然是 DID。设备权力来自：

- DID Document 当前控制密钥
- DID method history / key log / operation log
- device authorization event
- capability grant
- recovery policy

### 2.2 长期密钥与日常密钥分离

实现 MUST 区分：

- 长期身份锚点
- 日常签名密钥
- 设备密钥
- 会话密钥
- 加密群组密钥
- 恢复密钥

长期密钥 SHOULD 尽量少在线使用。  
日常操作 SHOULD 由设备密钥或短期 session key 执行。

### 2.3 所有授权都必须可撤销

设备、agent、session 和企业网关颁发的权限 MUST 有明确失效条件：

- `expires_at`
- revoke event、status event 或 profile 注册的 credential status mechanism
- `scope`
- `audience`
- `not_before`

无限期、无 scope 的委托只允许用于极少数离线恢复场景，并且 SHOULD 有多签或门限保护。

## 3. 密钥类型

### 3.1 Inception Key

`inception_key` 表示 DID method 的初始控制材料或等价 genesis authority。不同 DID method 可能使用不同名称，例如 `did:plc` genesis operation / rotation keys、`did:webvh` SCID 与首个 DID log entry、KERI inception event，或其他 method-specific root。

要求：

- 初始控制材料或其 method-specific 证明 MUST 可验证
- 若 method 支持离线 genesis / recovery material，私钥 SHOULD 在 DID 创建后离线保存或销毁
- 普通操作 MUST NOT 依赖高权限 inception / recovery private key 在线存在

### 3.2 Principal Signing Key

principal signing key 用于：

- DID 文档更新
- 高权限 capability 签发
- device authorization
- recovery policy 更新

它 MAY 轮换。轮换 MUST 进入 DID method history、key log 或等价 signed event。

### 3.3 Recovery Key

recovery key 用于当前控制密钥丢失或泄露后的恢复。

要求：

- SHOULD 与日常设备隔离
- SHOULD 支持多份或门限方案
- MUST 只能执行 recovery policy 允许的操作
- recovery event MUST 写入 DID method history、key log 或等价 signed event

### 3.4 Device Key

每台设备 SHOULD 本地生成独立 device key。

device key 用于：

- 日常 Operation 签名
- Events API / sync 认证
- device-to-device pairing
- MLS KeyPackage 身份绑定

device key MUST 通过 device authorization event 或 capability grant 绑定到 principal DID。

### 3.5 Session Key

session key 是短期在线密钥，常用于 Web、SSO、临时容器或远程执行环境。

要求：

- MUST 有短失效时间
- MUST 绑定 audience / origin / service
- SHOULD 绑定 device id 或 browser instance
- MUST NOT 被用于恢复 DID 或签发长期 grant

### 3.6 Agent Key

agent key 用于 AI agent、bot、CI 或 automation。

要求：

- MUST 有明确 scope
- MUST 有 `expires_at` 或 revocation check
- MUST 绑定 accountable actor
- SHOULD 使用 proposal / approval 约束执行高风险动作

### 3.7 MLS KeyPackage Key

MLS KeyPackage key 用于加入加密 Space。

要求：

- MUST 绑定到 Actor DID 和 device id
- MUST 由有效 device key 或 principal signing key 签名
- MUST 有发布时间与过期时间
- SHOULD 单次或短期使用
- 被撤销设备的 KeyPackage MUST 不再用于新加密

## 4. Device Record

建议 device record 是 actor-private signed Event 或 identity sidecar 中的 signed state。

示例：

```json
{
  "id": "cx:device:01js0ke0000000000000000000",
  "actor_id": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "device_label": "Alice MacBook Pro",
  "device_public_key": "z6Mks...",
  "device_key_type": "Multikey",
  "created_at": "2026-04-26T00:00:00Z",
  "authorized_by": "cx:device:01js0kd0000000000000000000",
  "authorization_ref": "cx:event:01js0kf0000000000000000000",
  "status": "active",
  "last_seen_at": "2026-04-26T08:00:00Z",
  "revocation_ref": null
}
```

## 5. 设备授权流程

### 5.1 新设备加入

推荐流程：

1. 新设备本地生成 device key。
2. 新设备展示 pairing code / QR，其中包含 device public key、challenge、过期时间。
3. 已授权设备扫描并验证 challenge。
4. 已授权设备签发 `cx.device.authorized` event。
5. Events API / identity registry 接受并传播该 event。
6. 新设备开始同步 Event history、Space membership 和必要的 MLS Welcome。

`cx.device.authorized` 示例：

```json
{
  "kind": "cx.device.authorized",
  "actor_id": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "device_id": "cx:device:01js0ke0000000000000000000",
  "device_public_key": "z6Mks...",
  "scopes": [
    "cx.events.describe",
    "cx.events.submit",
    "cx.sync.client_sync",
    "cx.keys.keypackages.upload"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null,
  "authorized_by": "cx:device:01js0kd0000000000000000000",
  "proof": {
    "kind": "detached_jws",
    "verification_method": "did:plc:ewvi7nxzyoun6zhxrhs64oiz#device-old",
    "jws": "..."
  }
}
```

### 5.2 设备吊销

设备丢失、出售、被恶意控制或员工离职时，MUST 发布 `cx.device.revoked`。

吊销后：

- Events API MUST 拒绝该设备的新签名写入
- authz MUST 视相关 session grant 失效
- 加密 Space SHOULD 通过 MLS Remove 推进 epoch
- 客户端和受托 projection executor SHOULD 标记旧设备产生的未确认 Operation 为高风险

## 6. Session Grant

Session grant 用于 OIDC / SSO、浏览器短会话、远程执行环境。  
Contrix v1 使用 `cx.session.grant` 作为标准可见事件类型。

示例：

```json
{
  "kind": "cx.session.grant",
  "issuer": "did:web:auth-gateway.example.com",
  "subject": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "session_public_key": "z6Mss...",
  "audience": "https://app.example.com",
  "scopes": [
    "cx.events.submit",
    "cx.space.discover",
    "cx.object.read",
    "cx.flow.update",
    "cx.message.create"
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": "2026-04-27T00:00:00Z"
}
```

规则：

- session grant MUST be signed by trusted issuer
- session key MUST NOT outlive grant
- session grant SHOULD be audience-bound
- session grant SHOULD be non-exportable in WebCrypto / platform keystore where available
- session grant 撤销 MUST 由 accepted `cx.session.grant` 状态更新、device/account revoke、或 profile 注册的 credential status mechanism 表达；不得使用未注册的 `cx:revocation-list:*` typed ID。

## 7. 密钥备份

### 7.1 备份内容

备份 MAY 包含：

- recovery key share
- device state
- encrypted private account data cache
- MLS group state
- pending Welcome
- private account state

备份 MUST NOT 以明文保存私钥。

### 7.2 Backup Envelope

建议格式：

```json
{
  "type": "key_backup",
  "actor_id": "did:plc:ewvi7nxzyoun6zhxrhs64oiz",
  "backup_id": "cx:backup:01js0ke0000000000000000000",
  "created_at": "2026-04-26T00:00:00Z",
  "kdf": {
    "name": "argon2id",
    "params": {
      "memory_kib": 65536,
      "iterations": 3,
      "parallelism": 1
    },
    "salt": "base64url..."
  },
  "aead": {
    "name": "xchacha20_poly1305",
    "nonce": "base64url..."
  },
  "ciphertext": "base64url...",
  "commitment": "sha256:..."
}
```

实现 SHOULD 使用现代 KDF，例如 Argon2id。  
如果平台限制只能使用 PBKDF2，迭代次数 MUST 足够高，并 SHOULD 在 profile 中声明降级。

### 7.3 恢复流程

恢复流程：

1. 新设备生成 device key。
2. 用户输入 passphrase 或收集 recovery shares。
3. 客户端解密 backup envelope。
4. 客户端验证 backup commitment。
5. 客户端用 recovery policy 发布 `recover` 或 `cx.device.authorized`。
6. 若涉及 E2EE Space，客户端拉取 MLS state 并处理 epoch 缺口。

### 7.4 所有权证明与解密证明

DID 控制权证明 SHOULD 优先使用签名挑战，而不是“能解开某段历史密文”：

- 当前控制密钥、已授权 device key 或 recovery key 对服务端 fresh challenge 签名。
- 新设备生成 device key 后，由当前有效设备或 recovery policy 签发 `cx.device.authorized`。
- recovery service 在 DID Document、organization policy 或 recovery policy 中被明确声明，并签发可验证 recovery event。

“能解密用某个公钥加密的数据”MAY 作为恢复流程中的一个密码学因子，但不得单独等同于账号所有权。允许的形式是：服务端生成短期随机 challenge，按当前 key-log / recovery policy 指定的 recovery public key 加密，客户端在本地解密后对 challenge transcript 签名或返回 proof。该流程 MUST 绑定：

- `challenge`
- `audience` / `origin`
- `service_did`
- `principal_did`
- `key_id`
- 过期时间
- 防重放 nonce

实现 MUST NOT 把以下情况当作独立恢复依据：

- 用户能解密某条历史消息、历史 Blob、旧 MLS epoch 或旧备份。
- 用户能提供某段历史明文。
- 用户知道 service account 密码或邮箱验证码，但没有 DID / recovery proof。
- 用户持有已经撤销、过期或不在当前 recovery policy 中的旧设备密钥。

安全风险：

- **密钥用途混淆**：内容解密密钥、MLS epoch key、backup key 和 DID 控制密钥不是同一种权力。
- **旧密钥复活**：被移除成员或旧设备可能仍能解密旧内容，但不应重新获得账号控制权。
- **弱口令备份被盗**：攻击者获得云端备份密文后可以离线爆破 passphrase。
- **解密 oracle**：服务端若允许任意密文挑战，可能被滥用为私钥 oracle；challenge 必须是固定格式、短期、限速且只针对声明的 recovery key。
- **钓鱼与中继**：攻击者可能诱导用户解密 challenge；proof 必须绑定 domain / service DID / audience，并在 UI 中展示高风险恢复意图。
- **隐私泄露**：用历史内容证明所有权会向恢复服务暴露用户拥有或可读哪些私有内容。

因此，解密能力最多是 recovery factor；真正改变 DID 控制状态必须落成 DID method history、key log、`recover`、`rotate`、`cx.device.authorized` 或等价 signed event。

## 8. 社交恢复与门限恢复

高价值账号 SHOULD 支持门限恢复。

Recovery policy 字段：

```json
{
  "type": "recovery_policy",
  "threshold": 3,
  "shares": [
    {
      "holder": "did:web:alice-friend.example",
      "share_id": "s1",
      "transport": "sealed_box"
    }
  ],
  "not_before": "2026-04-26T00:00:00Z",
  "expires_at": null
}
```

恢复 share holder 只能帮助恢复控制权，不自动获得读取内容或代表主体操作的 capability。

## 9. 泄露响应

当怀疑密钥泄露时，客户端 SHOULD：

1. 立即发布 device revocation 或 key rotation。
2. 停止接受旧设备/session 的新写入。
3. 对 E2EE Space 触发 MLS Remove / Update。
4. 标记泄露窗口内的高风险 Operation。
5. 提醒用户检查未知设备、session 和 agent grant。

如果 principal signing key 泄露但 recovery key 安全，MUST 通过 recovery policy 重建当前控制密钥。  
如果 recovery key 也泄露，SHOULD deactivate 旧 DID 并执行身份重建。

## 10. 实现要求

实现 MUST：

- 使用系统安全存储保存私钥
- 对可导出密钥做用户确认
- 对恢复操作做高风险 UI
- 对设备列表显示最近活动和授权来源
- 对吊销操作做不可抵赖记录

实现 SHOULD：

- 支持硬件安全模块或平台 keystore
- 支持 biometric unlock 但不把 biometric 当作 cryptographic secret
- 支持 passkey / WebAuthn 作为本地解锁与网关认证材料
- 支持企业设备管理和远程吊销

## 11. 一致性要求

Contrix v1 对设备、会话和恢复要求如下：

- Device record JSON Schema 由 `data-structures.md`、`devices-and-auth.md` 和 `device-crypto-verification.md` 共同固定。设备记录 MUST 绑定 principal DID、device id、verification method、算法、创建时间、撤销状态和签名链。
- `cx.device.authorized` 与 `cx.device.revoked` MUST 进入 schema registry，并按 event auth 规则验证。撤销后设备不得产生新的有效 session grant、KeyPackage 或 to-device write。
- Session grant MUST 绑定 principal DID、device id、service DID / audience、scope、过期时间、proof 和 revocation reference；服务账户登录不得替代 DID 控制权。
- Backup envelope test vector MUST 覆盖加密备份、错误 recovery key 拒绝、weak passphrase policy、domain / audience 绑定和服务端不可解密要求。
- MLS KeyPackage binding MUST 覆盖 principal DID、device id、KeyPackage hash、签名 verification method、有效期和撤销检查；客户端 MUST 拒绝未绑定 DID / device trust chain 的 KeyPackage。
- Recovery policy grammar MUST 表达 threshold、share holder、not_before、expires_at、allowed recovery methods、approval requirement 和 audit event；恢复只改变控制链，不自动授予内容读取或业务 capability。
