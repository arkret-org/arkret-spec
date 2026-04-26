# Contrix New Tasks

## 当前轮任务

- [x] 增加 `design-questions.md`
- [x] 重写 `README.md`
- [x] 增加 `conversation-model.md`
- [x] 拆分并重写 `object-model-core.md` / `object-model-standard.md`
- [x] 重写 `operations-sync.md`
- [x] 重写 `capabilities.md`
- [x] 重写 `views.md`
- [x] 增加 `service-surface.md`
- [x] 补 `schema / policy / invite / read_marker / notification`
- [x] 补同步与权限细则
- [x] 增加 `gap-analysis.md`
- [x] 增加 `api-conventions.md`
- [x] 增加 `conformance-profiles.md`
- [x] 补 `key-management.md`
- [x] 扩展 `applet-integration.md`

## 当前轮验收标准

- [x] 协议问题清单被明确列出
- [x] 看板数据模型被明确为标准 Entity 类型 + Relation + View
- [x] 聊天/话题模型被明确为 `channel/topic/message` Entity + Relation
- [x] `@mention` 被明确为结构化 DID/entity ref 和 `mentions` Relation
- [x] 撤回被明确为 redaction/tombstone，而不是隐式物理删除
- [x] board/chat/topic 的同步与冲突规则被写回规范
- [x] 最小服务接口与 Space bootstrap 被写回规范
- [x] `schema/policy/invite/read_marker/notification` 被正式定义
- [x] 幂等提交与授权时序规则被写回规范

## 下一轮 Backlog

- [x] 定义 query JSON schema 的正式语法
- [x] 定义 grant constraint schema
- [x] 定义 cursor / HLC / rank / commit hash 编码
- [x] 定义 snapshot manifest 与 chunk schema
- [x] 定义各服务接口的正式 request/response schema
- [x] 定义 snapshot signature / chunk digest / encrypted envelope schema
- [x] 定义 read marker / inbox / notification 的正式 schema 与查询面
- [x] 定义标准 event / object schema registry
- [x] 定义 canonical JSON、hash、id、signature、cursor 编码规范
- [x] 定义 blob/media 的 metadata、thumbnail、authenticated download 与 encrypted attachment envelope
- [x] 定义 federation wire transaction、cross-domain join、backfill authorization 与 fork detection
- [x] 定义 Applet registration / namespace / transaction / protocol metadata 的正式 JSON Schema 与 OpenAPI
- [x] 补齐英文目录，使 `en/` 与 `zh/` 的拆分结构和核心决策一致

## Matrix / MSC 对比补齐

- [x] 对比 `E:\Works\palpo-im\matrix-spec` 的 client-server、server-server、application-service、event schema、room version 模块
- [x] 对比 `E:\Works\palpo-im\matrix-spec-proposals` 中 appservice、sync、policy server、cross-signing、authenticated media、state resolution、OIDC 相关 MSC
- [x] 增加 `matrix-compat-gap.md`，记录哪些 Matrix 能力需要吸收、改造或明确拒绝继承
- [x] 增加 `event-auth-state-resolution.md`，补齐 Space version、auth refs、membership、state resolution、redaction、soft fail、upgrade 规则
- [x] 增加 `device-crypto-verification.md`，补齐设备身份、cross-signing、to-device、verification、secret storage、key backup 与 Applet 设备代理
- [x] 增加 `sync-v2.md`，补齐客户端 timeline/state/account_data/to_device/device_lists/ephemeral 增量同步协议
- [x] 增加 `policy-server.md`，补齐策略服务签名决策、缓存、失败模式、联邦和隐私边界
- [x] 增加 `account-lifecycle.md`，补齐账户锁定、暂停、注销、软登出、擦除与 session/device 撤销
- [x] 更新 README 规范地图与中英文目录结构

## 术语整理

- [x] 增加 `glossary.md`，集中定义协议专业术语
- [x] 覆盖核心对象、标准语义类型、身份、授权、repo/sync/state、服务角色、联邦、Applet、设备加密、媒体通知、API 编码、账户生命周期
- [x] 明确易混术语的边界，例如 DID/Handle、Actor/Principal、Entity/Event、Repo/Index、Capability/Namespace、Redaction/Erasure
- [x] 更新中英文 README 与根目录结构

## Space 层级与级联

- [x] 增加 `space-hierarchy.md`，正式定义 Space parent/child 层级关系
- [x] 明确 Space hierarchy 是有向图，不强制是树，且有效 edge 需要 parent 与 child 双向确认
- [x] 明确 membership、capability、history visibility、E2EE key、schema、policy 默认不级联
- [x] 定义 `cx.space.child`、`cx.space.parent`、`cx.space.inheritance_policy` 与 `cx.capability.derived`
- [x] 定义层级查询、Lazy Link、cycle handling、archive/delete 非默认级联规则
- [x] 更新 object model、event auth/state resolution、README 与英文占位文件

## Agent 外部协议互操作

- [x] 核对 ACP / BeeAI / A2A 当前公开状态，确认 ACP 已并入 Linux Foundation 旗下 A2A，但 BeeAI 仍保留 ACP adapter
- [x] 增加 `agent-protocol-interop.md`，定义 Contrix agent task 到 A2A / ACP legacy / 其他 agent protocol 的受控 handoff
- [x] 明确 Contrix 负责身份、授权、任务登记、审计、状态回流和结果归档，外部协议只作为执行 transport
- [x] 定义 `cx.agent.endpoint`、`cx.agent.protocol_session.start/status/result` 与 adapter registry
- [x] 定义 discovery、capability、policy、E2EE 数据外发、artifact 安全检查、audit mode、failure mapping
- [x] 更新 README、glossary 与英文占位文件
