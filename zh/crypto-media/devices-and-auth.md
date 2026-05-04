# 设备、认证与通知规范

## 1. 目标

去中心化协议摒弃了传统的“账号+密码”中心化认证模式，身份的本质是“持有私钥”。为了让普通用户和企业用户获得不输于 Web2 产品的体验，本规范定义了在无密码环境下的：
- 多设备协同与授权配对 (Device Pairing)
- 企业级单点登录网关 (SSO / OIDC Integration)
- 密钥的安全备份与恢复 (Key Backup & Recovery)
- 隐私保护的移动端推送通知 (Privacy-Preserving Push Notifications)

## 1.1 认证服务器验证什么

Contrix 可以部署 Auth Service / Auth Gateway，但它不是协议身份根。它验证的是“某个登录会话是否可以被绑定到某个 DID principal / device”，而不是用用户名、密码、邮箱或 OIDC subject 直接定义主体所有权。

实现 MAY 支持以下登录因子：

- 用户名 + 密码，用于传统 service account 登录。
- Passkey / WebAuthn，用于强认证或无密码登录。
- OIDC / SSO，用于企业或组织管理账号。
- 已授权设备配对，用于普通多设备加入。
- Recovery key、门限恢复或受信恢复服务，用于全部设备丢失后的恢复。

认证成功后，Auth Service MUST 产出以下至少一种可验证绑定：

- `cx.session.grant`：把短期 `session_public_key` 委托给 DID principal / device。
- `cx.device.authorized`：把新设备公钥加入当前设备集合。
- 满足 `recovery_policy` 的 `recover` / key-log event。

资源服务器验证的是 session grant、device authorization、DID proof、capability 和 Space policy，而不是“用户刚刚输入了正确密码”。密码、SSO session 和 service account id 都不能直接作为 `actor_id`、event sender 或 capability subject。

服务账号密码重置只改变服务账号登录凭据；除非同时存在有效 DID 控制证明或 recovery policy 事件，否则不得自动授予 DID 控制权、不得签发长期 device grant、不得访问 E2EE 密钥备份。

## 1.2 登录、设备授权与设备验证的边界

Contrix v1 把三件事分开处理：

- **登录因子验证**：Auth Service 验证 password、passkey、OIDC、SSO 或 recovery factor，只能产出短期 `cx.session.grant`、触发恢复流程，或请求已有设备授权。
- **设备授权**：新设备成为长期有效设备，MUST 落成 `cx.device.authorized`、DID/key-log operation 或等价 signed event。只有这一步改变设备集合。
- **设备密钥验证**：SAS/QR 只确认 device key / identity key 的人工信任。验证成功不得自动创建登录态、长期 device grant 或 Space capability。

因此“新设备登录”的推荐实现是：新设备先本地生成 device key，使用登录因子或已授权设备完成交互验证，再由当前有效授权方签发 `cx.device.authorized` 或短期 `cx.session.grant`。短期 Web/OIDC 登录可以只使用 `cx.session.grant`；需要 E2EE 历史、secret storage 或长期离线能力时，仍必须走设备授权和设备密钥验证。

## 2. 多设备配对 (Device Pairing)

在 Contrix 中，用户的每个物理/逻辑设备都应该拥有本地独立生成的设备级密钥对 (Device Key)。
多设备登录的过程，本质上是“已授权设备将新设备加入身份控制网”的密码学授权过程。

### 2.1 配对流程 (无密码登录)
1. **新设备初始化**：用户在新手机或新电脑上打开应用，本地生成一组全新的 ECDSA/Ed25519 密钥对。屏幕上显示包含公钥与临时连接信息的二维码 (QR Code)。
2. **主设备扫码**：用户使用已登录的主设备（如已通过面容 ID 解锁的手机）扫描该二维码。
3. **密码学授权**：
   - 主设备验证 pairing challenge 后，签发 `cx.device.authorized`、符合 DID method 的 key-log operation，或触发 recovery policy 允许的设备授权流程。
   - DID Document SHOULD 只承载身份控制密钥和服务发现入口。普通设备列表、设备信任状态、吊销状态和算法更新 SHOULD 由 `cx.device.*` 事件、device key log 或受控 device registry 表达；只有 DID method 本身要求时，才把设备 verification method 写入 DID Document。
   - 短期浏览器或临时执行环境 MAY 只拿到 `cx.session.grant`，但它不改变长期设备集合，也不得访问 E2EE 历史密钥，除非另有有效设备授权和密钥共享流程。
4. **状态下发**：主设备通过点对点信道或安全的 Sync Service，将必要的工作区快照、加密会话历史（通过 MLS Welcome / Commit 把新设备加入合适的 group）同步给新设备。
5. **事件广播**：主设备向 principal control stream 广播 `cx.device.authorized` 事件；若封装为 Event Envelope，其 `space_id` 是目标 principal 的 `principal_control_space_id`。新设备获得的能力由该事件、session grant、Space capability 和 policy 共同限制，不是自动获得 principal 的全部权限。

### 2.2 设备吊销
当设备丢失时，用户可从任何其他已授权设备、DID 控制密钥或 recovery policy 允许的恢复服务发起吊销操作：发布 `cx.device.revoked`，停止接受该设备的新签名写入，并对受影响的 MLS 群组触发 `Remove` 与 Epoch 更新。若该设备曾被写入 DID Document，撤销流程还必须按 DID method 规则移除或失效对应 verification method。

## 3. 企业单点登录 (SSO / OIDC Gateway)

企业通常强制要求使用 Okta、Google Workspace 等中心化身份提供商 (IdP) 进行认证。在不破坏去中心化端到端加密前提下，本协议引入 **Auth Gateway (认证网关)** 模式。

### 3.1 架构角色
- **Auth Gateway**：部署在企业内网或受控云端的高安全级别服务器。它通常是组织 DID 明确声明的 session grant issuer 或设备授权服务。只有在企业托管账号场景中，它才 MAY 托管员工 DID 的高权限签发材料；对普通个人 DID，网关 SHOULD 只签发短期 session grant，不应托管用户 principal signing key 或 recovery key。

### 3.2 登录时序
1. **浏览器会话初始化**：员工在浏览器打开 Web 端应用，本地生成临时会话密钥 `session_key`。
2. **OIDC 重定向**：浏览器跳转至企业 Okta 完成标准的 OAuth2 / OIDC 身份认证。
3. **网关授权 (Gateway Delegation)**：Okta 认证成功后回调 Auth Gateway。Gateway 验证员工身份无误后，签发短期、受众绑定、scope 受限的 `cx.session.grant`，把 `session_key_pub` 绑定到目标 DID principal、设备、origin、audience、过期时间和允许的 operation 集合。
4. **会话生效**：浏览器操作必须同时附带 session grant、device proof 或等价绑定证明。资源服务器仍 MUST 重新验证 DID control state、capability、Space policy、grant scope、audience、origin 和重放状态；不得因为 OIDC 成功就把请求视为 DID 控制证明。
5. **平滑过期**：session grant SHOULD 使用分钟到小时级 TTL，并支持即时撤销。续期需要重新验证 OIDC session，并重新检查组织 policy、设备状态和风险信号。

此模式只把 Web2 SSO 作为登录因子和会话授权输入。它不授予 E2EE 密钥访问权，不自动创建长期设备，不替代 `cx.device.authorized`、DID/key-log operation 或 recovery policy。

## 4. 密钥备份与恢复 (Key Backup & Recovery)

为了防止“设备全部丢失导致永远失去账号”，协议提供以下备份标准。

### 4.1 加密云保险箱 (Encrypted Cloud Vault)
- **机制**：客户端将核心主钥、恢复密钥与尚未备份的 MLS 会话状态，使用用户设置的 **强口令 (Passphrase)** 或 PIN 码通过 Argon2id 推导备份密钥，并使用认证加密 envelope 保护（默认 `xchacha20poly1305`；FIPS profile MAY 使用 AES-GCM，但 KDF 仍 MUST 是 Argon2id 或等价 memory-hard KDF）。
- **存储**：加密后的密文 `Ciphertext Blob` 可以安全地存储在公共 Sync Service、用户的私有云网盘或 Contrix Identity Registry 中。
- **恢复**：用户在新设备上输入相同的强口令，拉取 Blob，本地解密还原出完整身份状态。因为存储的是强加密密文，即使云存储服务商被黑客攻破也无法盗取用户身份。

PBKDF2 只允许作为 fallback / constrained-platform 降级 profile；服务和客户端 MUST 在 backup metadata 中声明降级原因、迭代次数、salt、KDF 参数和 profile id。新创建的云保险箱不得默认使用 PBKDF2。

### 4.2 门限社交恢复 (Social Recovery)
高级别账号 MAY 支持通过 Shamir's Secret Sharing (SSS) 将恢复密钥分割为多份碎片（如 3-of-5），分别分发给值得信任的联系人或企业管理员保管。恢复时需集齐指定数量的碎片即可重构私钥。

## 5. 隐私保护的移动端推送 (Privacy-Preserving Push)

在 iOS/Android 上，应用被杀后台时必须依靠苹果 (APNs) 或谷歌 (FCM) 发送推送才能唤醒。去中心化节点直接将明文内容推给苹果/谷歌会导致严重的隐私泄漏。

### 5.1 Push Gateway 角色
协议中引入一个 `Push Gateway` 角色（通常由开发该客户端 App 的厂商运行，以持有苹果/谷歌的推送证书）。

### 5.2 脱敏投递工作流
1. **Token 注册**：客户端向 `Push Gateway` 注册自己的设备 `Push Token`，并将其与自己的 DID 建立匿名映射。
2. **事件触发**：当 Sync Service 或受托 notification service 侦测到该用户的 `@mention` 或紧急任务分配时，它无法也无权解密内容。
3. **脱敏唤醒 (Blind Wakeup)**：该服务向 `Push Gateway` 发出一个极其简略的脱敏触发信号，例如：
   ```json
   {
     "target_did": "did:web:alice.com",
     "event_type": "background_sync_needed",
     "urgency": "high"
   }
   ```
4. **静默拉取**：苹果/谷歌服务器将此唤醒信号推送到用户的手机。手机操作系统在后台短暂唤醒 App。
5. **本地解密展示**：App 被唤醒后，直接使用本地密钥连接 P2P 网络或 Sync Service 拉取最新的加密 Payload。App 在本地完成解密，并调用本地系统的弹窗接口显示明文通知（如：“Bob 提到了你：项目已上线”）。

**结果**：苹果、谷歌和 Push Gateway 默认只看到脱敏唤醒信号。实现仍 MUST 避免在推送 payload、collapse key、topic、analytics tag 或第三方日志中写入正文、附件名、稳定 Space 名称、sender handle 或可长期关联的敏感标识。
