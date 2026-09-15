---
title: Event Authorization And State Resolution
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../sync/authority-commit-log.md
  - capabilities.md
  - ../sync/current-results.md
  - ../conformance/normative-language.md
---

## 1. 权威来源与执行模型

每个 Realm只有一个 current governance Station。它为 Realm、每个 Circle、每个 Sidecar分别维护一条单写者 authority stream。Producer签 Event；governance Station在实际 commit位置验证 current authorization和领域规则并签 `RealmCommit`。

## 2. 独立接收站准入

Account/consumer Station可以验证、排队、转发和缓存，但不能独立产生accepted状态。只有验证 genesis + handoff chain、current assertion、Commit signature、Event ID/proof和同stream连续性后，才能向客户端报告committed。

## 3. 历史分类与因果依赖

Event没有通用 `actor_seq`、`prev_refs` 或 `causal_refs`。业务依赖使用registry声明的typed payload字段或`refs[]` role。依赖某个accepted事实时使用exact committed ref；业务引用不产生跨stream总序。

## 4. 授权关闭

授权不再冻结于producer选择的历史basis。治理 Station在分配Commit前读取current membership、capability、policy、device/Agent authorization和typed target revision；任一条件失败则rejected且不产生Commit。

## 5. 有限期与时间证明

期限以authority admission时的受信时钟和proof自身受约束时间求值。Producer `created_at` 只用于审计/展示，不能延长已撤销权限或决定winner。

## 6. 因果寄存器

通用causal register已退役。默认同一typed target按Commit顺序更新；需要防覆盖的kind在payload定义`expected_revision`，比较失败则conflict。

## 7. 其他普通状态与结构

Membership、policy、Strand、Message、Relation、Circle和capability由各自typed reducer处理。实现可用内部表/索引，但不得暴露Cell/state-model DSL。

## 8. 安全状态与 Seal

Seal已退役。`RealmCommit`是唯一finality；它不携state root、effect list或通用proof。相同stream position出现两个不同有效Commit时，消费方冻结该Realm/stream并保留equivocation evidence。

## 9. 跨域与不可逆效果

跨Realm/Circle/Sidecar不提供原子提交。不可逆side effect只能在其前置Event committed后执行，并以exact committed ref作幂等键；失败使用领域saga补偿，不伪造跨stream事务。

## 10. MLS、恢复与快照

MLS只保留shared `ak.mls.genesis`和`ak.mls.commit` Event。治理 Station跟踪public state与`key_access_revision`，不持有secret。Commit与新增recipient Welcome delivery必须在一个authority transaction中全成或全败。恢复使用authority-signed typed snapshot + 每条获准stream tail。

## 11. 安全状态根与序列化

通用state root已删除。Snapshot完整性由manifest signature、typed sections、stream heads、history floors和chunk digests提供；它不授权新写入。

## 12. Notary 与 reducer 配置

Realm不再选择notary/reducer profile/digest transition。v1 reducer和digest语义由协议版本固定；service key rotation通过service DID method history处理。

## 13. Hash suite transition

current v1不支持Realm内suite transition。Event/Commit ID使用协议固定suite；未知或错误suite fail closed。

## 14. 控制面 Control Proposal Ack 与 inclusion obligation

Control Proposal Ack、defer window、pending sample和inclusion obligation已退役。治理 Station一次提交返回committed、duplicate、rejected或retryable unavailable；后两者不写共享pending状态。

### 14.1 持久恢复与积压终结（normative）

Account Station可以耐久保存exact signed Event并重试。它必须先刷新current authority；handoff后只向new authority转发。请求结果不确定时按Event ID查询/重放exact bytes，不能重签或生成另一Event冒充重试。

## 15. Actor 分叉与内容地址碰撞

Actor sibling/fork概念已删除。相同Event ID、不同canonical bytes是内容地址冲突，全部拒绝并告警；相同Event多次提交是幂等。Authority equivocation按§8处理，base v1不自动选winner。
