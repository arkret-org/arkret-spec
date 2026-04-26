# Encryption and Auditability Draft

## 1. 目标

去中心化协作协议面临着复杂的隐私与合规矛盾：一方面，商业数据和私密频道必须提供不可被 Relay / Index 窃听的端到端加密 (E2EE)；另一方面，在特定组织边界内，数据流又需要受到法律或合规层面的安全审查。

本规范定义了 Contrix 官方推荐的加密标准，旨在实现：
- 基于 **MLS (RFC 9420)** 的高效大规模协作加密
- 强前向安全 (Forward Secrecy) 与后向安全 (Post-Compromise Security)
- 独创的 **可审查加密 (Auditable E2EE)**，确保合规解密必定留下透明不可抵赖的密码学记录。

## 2. 基础加密架构：MLS 与 Contrix 的融合

Contrix 采用 [RFC 9420 - Message Layer Security (MLS)](https://datatracker.ietf.org/doc/html/rfc9420) 作为官方的群组加密标准。
不推荐使用传统的 Double Ratchet（双棘轮），因为在包含数十到数百名成员的 `board` 或 `channel` 协作空间中，双棘轮会导致巨大的性能开销与并发处理难题。

### 2.1 KeyPackage 与服务发现
在参与 MLS 加密前，用户必须公布自己的 `KeyPackage`。
- **发布位置**：Actor 通过 Repo 发布自己的 `KeyPackage`，或者在其 DID Document 的 `service` 中指定独立的 `MLS Delivery Service` 节点入口。
- **生命周期验证**：其他客户端在拉取 `KeyPackage` 时，MUST 通过 Actor 的 DID Document 与 Repo 历史验证该包的公钥签名，确保未被身份盗用。

### 2.2 握手与组成员管理 (Welcome, Commit)
MLS 维护了一颗成员密钥树 (Ratchet Tree)。在 Contrix 中，群组的密钥状态变动不依赖于独立的中心化分发服务器，而是映射到原生的 `Space` 与 `Repo` 模型中：
- **`event.mls.commit`**：当拥有权限的 Admin 邀请新成员加入或移除成员时，客户端计算 MLS 的 `Commit` 消息。该 `Commit` 必须作为 `event.mls.commit` 类型的 Event 提交至 Space Repo。它作为不可篡改的账本，确保全网节点对群组密钥状态树的演进达成一致。
- **`Welcome` 分发**：新成员会收到由 Admin 构造的 `Welcome` 消息。由于其仅面向特定新成员解密，该消息可通过 Relay 的 Ephemeral Channel 发送，或通过私信 `message` 投递。

### 2.3 载荷加密 (Application Data)
日常的 `message` 或 `task` 的内容负载在写入 Repo 前，必须使用当前 MLS Epoch 的流密钥 (Application Key) 加密为密文信封。
- **可路由元数据分离**：密文信封 `encrypted_payload` 仅包裹实际的业务内容 (`body`, `content`, `attachments`)。
- **明文元数据保留**：用于网络路由和索引查询的 `space_id`, `type`, `causal_links`, `status`, `labels` 必须保持明文。
- Relay 和 Index 节点可以依据明文元数据完成数据的转发、排序、过滤和去重，而完全无法窥探密文信封内的具体正文。

## 3. 可审查的端到端加密 (Auditable E2EE)

在很多去中心化产品中，如果存在审查，往往是通过向客户端下发“旁路后门”或者弱化密钥机制实现的，这引起了极大的隐私恐慌。

Contrix 引入 **“透明留痕审计 (Transparent Audit Trail)”** 机制：既满足组织的强制合规要求，又向所有参与者提供 100% 透明的审计记录。没有隐秘监控，所有的解密审查都被置于阳光之下。

### 3.1 Auditable Policy 声明
要启用此机制，Space 的 `schema/policy` 必须显式声明：
```json
{
  "encryption_profile": "mls-rfc9420",
  "auditable_e2ee": true,
  "audit_actors": [
    "did:web:compliance.acme.corp"
  ]
}
```
客户端在加入此类 Space 前，**UI 必须向人类用户明确警告**：“这是一个受审核的加密空间，内容对合规员可见，但任何审查都会被记录并在群内公示。”

### 3.2 审计节点的入群
`did:web:compliance.acme.corp` 对应的合规客户端（Audit Agent）会作为一个合法的、只读的成员，由创建者通过正常的 `event.mls.commit` 邀请加入 MLS 群组。
这意味着：
- Audit Agent 从密码学上获得了当前 Epoch 的解密能力。
- 群组内所有的普通成员都可以通过检查 MLS 树，清晰地知晓 Audit Agent 的存在。

### 3.3 强制留痕机制 (Audit Record Mandatory)
获得密钥并不意味着可以随意“暗中偷看”。协议要求 Audit Agent 的实现（强烈建议依托于 TEE / SGX enclave 技术）必须执行以下硬性工作流：

1. **收到审查请求**：组织内部触发对某条涉嫌违规的 Message 的审查（如 `message_id: cx:msg:123`）。
2. **强制上链/入库声明**：Audit Agent 在进行解密之前，MUST 生成一条类型为 `event.audit.accessed` 的不可撤销操作，并提交给该 Space 的 Repo：
   ```json
   {
     "type": "event.audit.accessed",
     "target_ref": "cx:msg:123",
     "reason": "Internal legal compliance request #8801",
     "actor": "did:web:compliance.acme.corp"
   }
   ```
3. **基于 RYW (Read-Your-Writes) 的因果确权回执等待**：为防止网络抖动或中继节点恶意丢包导致的“假动作死锁”（即记录没发出去但明文已吐出），合规飞地 MUST 等待来自底层 Repo 或至少一个独立验证节点的 `sync_token`（或因果确权回执），确认该 `event.audit.accessed` 已经成功跨越本地局域网并在协作图中落盘。
4. **完成解密**：只有在接收到确权回执后，硬件飞地（或受控合规服务）才被允许利用持有的 MLS 密钥将对应的明文吐出给合规人员。

### 3.4 审查透明公示
因为 `event.audit.accessed` 是一条公开写入的协作事件，所有参与者的客户端 Index 都能实时同步到该事件。
- **用户端 UI**：客户端检测到自己发送的消息被附加了 `event.audit.accessed` 后，应在界面上（如气泡旁边）显示明显的标识（例如一个带警告色的“合规审查”眼睛图标），并允许用户点击查看审查事由与时间。
- **不可抵赖性**：合规员无法悄无声息地查看信息；一旦查看，全群组所有成员都能看到透明的访问足迹。

## 4. 受控账号的通信穿透 (Master-Agent Control)

协议严格区分“场地方合规审查 (Space Audit)”与“参与方主控权穿透 (Master-Agent Control)”。

当一个受控账户（如 AI Agent，拥有自己独立的 DID）加入了一个私密加密群组，其拥有者（Master）理论上拥有读取该 Agent 所有通信记录的权利。这属于**终端节点数据与密钥管理范畴**，不需要、也不应该触发前文所述的 `event.audit.accessed` 强制公开留痕机制。

协议推荐以下三种原生方式实现 Master 对 Agent 的通信穿透：

### 4.1 方案 A：密钥衍生与影子客户端 (Key Derivation / Ghost Client) —— 首选
如果 Agent 是完全独立的 DID，其初始私钥 MUST 由 Master 的根种子（Root Seed）以分层确定性（HD）方式衍生。
- **机制**：Master 设备在本地计算出 Agent 的 MLS 私钥，并在本地静默运行一个无 UI 的“影子客户端”。
- **效果**：Master 能够直接从 Repo 同步并解密发给 Agent 的所有群组信息。对于群内其他成员而言，消息只是发给了 Agent，这不会破坏群组的加密边界，也不会产生额外的协议开销。

### 4.2 方案 B：记忆提取与私聊同步 (Memory Forwarding)
如果 Agent 运行在受控云端环境中，Master 无需同步全量密文：
- **机制**：Agent 在可信执行环境 (TEE) 中解密所参与的群聊消息，提炼为 `memory` 对象，然后通过 Agent 与 Master 之间单独建立的 **专属 1 对 1 E2EE Space** 转发给 Master。
- **效果**：利用应用层的常规消息传递机制完成上下文汇报，无需污染原始协作空间的加密树。

### 4.3 方案 C：多设备绑定 (Multi-Device KeyPackage)
- **机制**：Agent 作为一个独立的物理/逻辑实体，生成自己的 `KeyPackage`，但在身份层面上挂靠在 Master 的 DID 下，作为 Master 的另一台“设备”。
- **效果**：在 MLS 树中，发送者对同一个主体的多个叶子节点加密。Master 手机与 Agent 服务器同时收到密文副本并各自解密。

## 5. 离线支持与消息延迟到达
- 凭借 MLS 的 Ratchet Tree，即使某成员长时间离线，只要他没有被驱逐出群组，他上线后依然能通过同步全量的 `event.mls.commit` 操作跟上 Epoch 的演进，并解密积压在 Relay 中的加密事件。
- 对于极端网络分区情况，客户端 SHOULD 保存尚未完全确认的前驱 Epoch 密钥状态，直到所有相关的历史 `encrypted_payload` 都已被成功拉取与解密。

## 6. 待细化领域
- 详细的 KeyPackage 格式在 DID Document 中的映射 Schema。
- TEE 环境下 Audit Agent 代码开源验证（Remote Attestation）在 Contrix 协议中的集成校验流程。
- 与现存 Signal/Double Ratchet 私信场景的无缝回退兼容性。
