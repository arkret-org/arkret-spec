# Matrix / MSC 功能差距与 Contrix 决策

## 1. 范围

本文件对照本地参考仓库：

- `E:\Works\palpo-im\matrix-spec`
- `E:\Works\palpo-im\matrix-spec-proposals`

目标不是把 Matrix 的 room / homeserver / power level 模型搬进 Contrix，而是识别 Matrix 已经用多年实现经验证明必须明确的协议层能力，并把这些能力映射到 Contrix 的 DID、Space、Entity、Relation、Event、View、repo、capability 与 Applet 模型。

## 2. 总体结论

当前 Contrix 已经覆盖身份、对象模型、基础同步、能力授权、媒体、Applet、推送、回执、VoIP、3PID 邀请等大方向；相对 Matrix 仍缺少以下落地关键层：

| Matrix 能力区 | Matrix 参考 | Contrix 缺口 | 处理决策 |
| --- | --- | --- | --- |
| room version / auth rules / state resolution | `content/rooms/v*.md`, `content/server-server-api.md` | Space 版本、事件授权、状态冲突归约规则不够形式化 | 新增 `event-auth-state-resolution.md`，作为 P0 |
| cross-signing / to-device / key backup / verification | `end_to_end_encryption.md`, `keys.yaml`, `to_device.yaml`, MSC1756, MSC1946, MSC4312 | 多设备信任链、设备间消息、密钥备份和验证流程不够可实现 | 新增 `device-crypto-verification.md`，作为 P0 |
| sync / account data / ephemeral / device lists | `sync.yaml`, `account_data.md`, `send_to_device.md` | 现有同步文档偏 repo 层，缺客户端稳定增量同步面 | 新增 `client-sync.md`，作为 P0 |
| policy server / moderation policy rooms | `policy_servers.md`, `policy_server.yaml`, MSC4284, MSC2313 | 审核策略有对象，但缺预提交策略服务签名与失败语义 | 新增 `policy-server.md`，作为 P1 |
| appservice bridge evolution | `application-service-api.md`, MSC2659, MSC2778, MSC3905, MSC4190, MSC4326 | Applet 已补，但仍需强调设备代理、ping、命名空间和局部用户范围 | 合并到 `applet-integration.md` / `applet-schema.md` |
| authenticated media | `authed-content-repo.yaml`, MSC3916, MSC3860 | 当前已有 blob 认证下载，需要明确与同步 token、缓存和重定向的关系 | 后续扩展 `media-and-blob.md` |
| room upgrades / tombstone | `room_upgrades.yaml`, `m.room.tombstone` | Space schema / auth 规则升级流程不够明确 | 纳入 `event-auth-state-resolution.md` |
| guest / knock / restricted join / history visibility | `joining.yaml`, `knocking.yaml`, `history_visibility.md` | Space 加入模式、预览状态、历史可见性边界不够细 | 纳入 `event-auth-state-resolution.md` |
| account lifecycle / soft logout / admin lock | `account_deactivation.yaml`, `logout.yaml`, MSC4323 | DID 账户与服务账户生命周期未拆清 | 新增 `account-lifecycle.md` |

## 3. 不继承 Matrix 抽象根

Contrix 不继承以下设计作为协议根：

- `room_id` 不作为唯一状态容器，改为 `space_id` 与 Entity / Relation 图。
- `m.room.power_levels` 不作为核心权限模型，改为 capability grant、policy 与 deterministic authorization。
- Matrix 的 homeserver 在 Contrix 中不被视为用户唯一权威入口；Contrix 用 principal repo、service DID、relay、index、blob 与 authz 分层替代。
- Matrix event type 不直接成为 Contrix 类型空间，Contrix 使用 `cx.*` 注册表。
- handle / user ID 不作为权限主键，权限主体必须是 DID principal、device 或受约束 selector。

## 4. 必须吸收的稳定经验

### 4.1 版本化状态规则

Matrix room version 的最大价值不是版本号本身，而是把事件格式、授权规则、状态解析、redaction、event id/hash 绑定在同一个不可变 profile 下。Contrix 必须采用同样思想：每个 Space 都有 `space_version`，它决定：

- canonical event envelope
- accepted event type set
- auth input selection
- authorization algorithm
- state reducer and conflict ordering
- redaction preserved fields
- join / invite / knock / restricted membership semantics
- schema upgrade rules

### 4.2 授权失败与 soft fail

联邦系统不能只支持 accept / reject。节点在缺上下文、收到未来状态或遇到策略服务暂时不可用时，需要 soft fail / quarantine 状态，避免错误事件污染本地可见状态，也避免永久断联。

Contrix 的 reducer 必须输出四种结果：

- `accepted`
- `soft_failed`
- `rejected`
- `quarantined`

### 4.3 设备不是会话字符串

Matrix 的 cross-signing、device list、to-device、key backup 说明：E2EE 系统里 device 是有长期信任语义的协议主体。Contrix 的 device 必须有签名身份、轮换、撤销、验证、密钥备份、设备间秘密共享与联邦同步规则。

### 4.4 同步是客户端协议，不只是 repo 复制

Repo commit / operation log 解决真相复制；客户端还需要低延迟、可分页、可过滤、可恢复的 sync API，包括 timeline、state、private state、ephemeral、to-device、receipt、notification、presence 与 device list delta。

### 4.5 策略服务只能增强，不能替代授权

Matrix MSC4284 类 policy server 的经验是：策略服务适合做内容、邀请、加入、媒体、滥用预判，但不能成为唯一授权真相。Contrix 采用 signed decision + deterministic fallback；策略服务结果进入审计，但基础 capability/auth 仍由本地可验证规则决定。

## 5. MSC 提案带来的 Contrix 设计约束

以下 MSC 方向应在 Contrix 中直接体现：

- MSC3861 / MSC2964 / MSC2965 / MSC2966：认证与授权服务器解耦，Contrix 服务发现必须公布 OAuth/OIDC metadata，但 DID principal 不等于 OAuth subject。
- MSC4326 / MSC4190：Applet / bridge 需要设备代理能力，否则无法桥接 E2EE 和 device-centric 功能。
- MSC2659：Applet 必须支持 homeserver/service 到 applet 的 ping 与健康状态。
- MSC3905：Applet 只能声明本服务范围内的 ghost actor / local namespace，不能全网抢占。
- MSC3916 / MSC3860：媒体下载应默认 authenticated，可支持受控 redirect。
- MSC1756 / MSC1946 / MSC2874 / MSC4312：cross-signing、secret storage 与 reset 是必需协议，不是客户端私有实现。
- MSC4222：sync 响应必须能表达 state-after timeline，避免客户端用错误状态解释事件。
- MSC3440 / MSC2674 / MSC2675 / MSC3715 / MSC3981：relation / aggregation / threading 需要服务端一致聚合，但 canonical truth 仍是关系事件。
- MSC3952：mention 必须结构化，不能依赖正文扫描。
- MSC4284 / MSC2313：policy server 与 policy list 需要互相补充，且决策要可签名、可缓存、可审计。

## 6. 当前补充文件

本轮补齐以下文档：

- `event-auth-state-resolution.md`：Space 版本、事件授权、状态归约、redaction 与升级。
- `device-crypto-verification.md`：设备信任、cross-signing、to-device、验证、密钥备份。
- `client-sync.md`：客户端增量同步 API 与 stream 语义。
- `policy-server.md`：策略服务请求、签名决策、缓存、失败语义。
- `account-lifecycle.md`：账户锁定、暂停、注销、软登出、服务账号与 DID 身份边界。

这些文件是 Contrix 进入稳定实现前的 P0/P1 规范补丁。
