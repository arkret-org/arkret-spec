# Architecture Draft

## 1. 目标

Contrix New 的顶层架构要同时满足四件事：

- 去中心化身份与发布
- 多主体协作对象共享
- 对人类友好的工作界面
- 对 AI agent 友好的执行与记忆模型

这要求协议在一开始就把“身份、写入、传播、查询、展示、记忆”拆成不同平面，而不是把所有能力都塞进一个服务角色里。

## 2. 总体模型

Contrix New 采用 **principal repo + identity registry + workspace relay + query index** 的分层模型。

### 2.1 Principal Repo

每个 principal 都有自己的 repo，用于发布自己签名的 commit 和 operation。

它承担：

- actor 侧可验证发布
- 历史追溯
- 设备离线后重传
- 审计基线

这点借鉴 atproto 的 repo 思路，但 Contrix 的 repo 记录的是 **协作操作**，而不是面向社交 feed 的 record 集。

### 2.2 Workspace Relay

Relay 负责把多个 principal repo 中与某个 workspace 相关的授权操作聚合、去重、转发与订阅。

它承担：

- Space 范围传播
- cursor/firehose 订阅
- 快速 fanout
- 初级权限过滤

Relay 不是唯一真相源，也不应拥有篡改 actor 历史的权力。

### 2.3 Query Index / AppView

Index 负责把授权操作物化成便于查询的当前态和投影。

它承担：

- 当前态归约
- 复杂查询
- 全文搜索
- 视图渲染输入
- 统计和报表
- 可选 embedding / vector index

Index 是派生层，不是真相源。

### 2.4 Blob Store

Blob Store 提供附件、大对象和可选 snapshot chunk 的内容存储。

Blob 地址可以多源，校验应基于内容哈希而不是单一 URL。

### 2.5 Capability Authority

Capability Authority 是一个逻辑角色，不要求独立部署。

它负责：

- 发布授权策略
- 响应 grant / revoke / delegate 相关查询
- 为 repo / relay / index 提供可缓存的授权依据

### 2.6 Client / Agent

Contrix 的 client 不只包括 GUI 应用，也包括：

- CLI
- webhook worker
- CI agent
- autonomous agent
- background automation

协议必须把 agent 当作一等参与者，而不是 UI 里的“插件”。

## 3. 架构平面

### 3.1 Identity Plane

负责：

- DID 解析
- Handle 解析
- 服务发现
- key rotation / recovery
- DID 日志写入与复制
- registry / witness / replica 协调

### 3.2 Write Plane

负责：

- 生成 op
- 生成 repo commit
- 签名
- 发布到 repo

### 3.3 Distribution Plane

负责：

- relay firehose
- workspace 增量同步
- 去重与 cursor

### 3.4 Query Plane

负责：

- 当前态查询
- 视图查询
- 搜索
- memory 检索

### 3.5 Presentation Plane

负责：

- kanban/list/table/calendar/timeline/graph/activity
- 人类审阅队列
- agent run timeline

### 3.6 Memory Plane

负责：

- run 轨迹沉淀
- episodic memory
- semantic memory
- memory promotion / supersession / forgetting

### 3.7 Confidentiality Plane

负责：

- 可见性与密文负载区分
- 内容加密 envelope
- key distribution / rotation
- 让 relay 在不解密正文时也能继续转发

### 3.8 Portability Plane

负责：

- export / import
- snapshot + op replay
- service replacement
- 多 repo / 多 relay / 多 index 迁移

## 4. 部署拓扑

Contrix 不要求所有角色分离部署。

### 4.1 单人/小团队拓扑

同一个部署可同时承载：

- identity registry
- repo
- relay
- index
- blob

适合：

- 小团队
- 私有实验环境
- 单组织内部部署

### 4.2 多组织协作拓扑

常见模式是：

- 每个组织维护自己的 principal repo
- 一个或多个共享 workspace relay
- 多个 query index 为不同参与方提供视图

这种模式更接近跨企业交付与供应链协作。

### 4.3 Agent 优先拓扑

在 agent 密集场景中，常见模式是：

- user/org DID 作为 authority
- agent DID 拥有受限 capability
- run log 写入 agent repo
- workspace relay 聚合到协作空间
- index 生成 human review queue

## 5. 旧协议与新协议的核心差异

### 5.1 旧模型

旧 `contrix-spec` 基本延续的是：

- room-first
- event-first
- homeserver-first
- communication-first

### 5.2 新模型

新 `contrix-spec-new` 明确改成：

- workspace-first
- object-first
- repo-first
- collaboration-first

这意味着：

- 房间不是唯一世界模型
- 消息也不是唯一原子单元
- UI 不需要从聊天历史里推业务状态
- 协议直接允许“任务、决策、记忆、运行记录、关系”成为一等对象

## 6. 信任边界

### 6.1 Repo 可证明 actor 发过什么

repo 能证明：

- 哪个 principal 发布了哪些 commit
- commit 内有哪些 op
- 顺序与签名是否成立

repo 不能单方面定义共享 workspace 的最终当前态。

### 6.2 Relay 可加速传播，但不应重写历史

relay 可以：

- 缓存
- 排序
- 去重
- 按 cursor 订阅输出

relay 不可以：

- 伪造 actor op
- 静默删除仍然有效的历史 op

### 6.3 Index 可解释状态，但不应替代原始审计链

index 可以：

- 给出当前态
- 提供搜索
- 给出看板/列表/图投影

index 不能作为唯一可验证来源。

### 6.4 Capability 是共享状态合法性的裁判，不是 UI 假设

是否允许某个写入，必须由有效 grant 集决定，而不是：

- 某客户端里当前看起来像管理员
- 某个服务器本地的隐式角色表

## 7. AI 与人类共用同一协议

Contrix New 不打算做“两套系统”：

- 一套给人类看板
- 一套给 AI memory

相反，协议应该保证：

- AI 写入的对象能被人类审阅
- 人类创建的对象能被 AI 理解和引用
- 任务、评论、关系、运行记录、记忆可以互相链接
- 所有沉淀都能投影成可操作界面

## 8. 初版架构决定

当前草案建议固定以下方向：

- principal repo 是 actor 发布基线
- identity registry / witness 是 DID 文档的解析与写入层
- workspace relay 是传播层
- index/appview 是物化查询层
- blob 是独立内容层
- capability 是独立决策层
- run 与 memory 是一等协议对象
- 同一数据既服务人类 UI，也服务 agent 记忆
- confidentiality 与 portability 也是明确协议平面，而不是部署细节

## 9. 后续待细化

下一轮仍需继续明确：

- repo commit 的精确编码
- relay firehose 的订阅协议
- index query surface
- capability cache 的一致性策略
- 多 relay / 多 index 并存时的互操作要求
- 加密 envelope 与 key 分发接口
- export/import 的一致性边界
