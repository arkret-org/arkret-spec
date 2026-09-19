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

Event 没有通用 `producer_revision`、`hlc` 或 `domain_refs`。业务依赖使用registry声明的typed payload字段或`refs[]` role。依赖某个accepted事实时使用exact committed ref；业务引用不产生跨stream总序。

## 4. 授权关闭

授权不再冻结于producer选择的历史basis。治理 Station在分配Commit前读取current membership、capability、policy、device/Agent authorization和typed target revision；任一条件失败则rejected且不产生Commit。

## 5. 有限期与时间证明

期限以authority admission时的受信时钟和proof自身受约束时间求值。Producer `created_at` 只用于审计/展示，不能延长已撤销权限或决定winner。

## 6. Typed 当前值与 compare-and-set

同一 typed target 的当前值由**该 target 所属 stream 上最后一个被接受的写入 Event** 决定。次序只来自治理
Station 在该 stream 上给出的 `stream_position`：位置更大的已接纳写入取代位置更小的。客户端不持有、也不可能
持有可用于排序的因果深度——生产者 Event 不携带前驱、basis 或 frontier，因此 MUST NOT 存在"深度更大者胜"
这类判据，也 MUST NOT 用 HLC、`created_at`、actor id、本地接收顺序或数据库插入顺序选边。

需要防覆盖的 kind 在 payload 定义 `expected_revision`，并按 compare-and-set 收敛：提交者带上它读到的
`CurrentRevision`，Station 在接纳位置比较该值，不匹配即以 `failed_precondition` 拒绝且零写入，客户端重读
当前值后重新签发再试。并发写因此串行化为该 stream 上的一串位置，不产生需要用户合并的多头。

跨 stream 不存在共享次序：Realm、每个 Circle 与每个 Sidecar 各自独立。需要跨 stream 协调的领域使用已提交
引用与显式补偿 Event，MUST NOT 假定两个 stream 的位置可比较。

## 7. 其他普通状态与结构

Membership、policy、Strand、Message、Relation、Circle和capability由各自 typed reducer处理。wire 只暴露 producer-signed Event、RealmCommit 与登记的 typed current result。

## 8. 安全状态与 RealmCommit

`RealmCommit` 是唯一 finality；它只承诺单个 Event 的接纳及同 stream predecessor，不携 state root、effect list 或通用 proof。相同 stream position 出现两个不同有效 Commit 时，消费方冻结该 Realm/stream 并保留 equivocation evidence。

## 9. 跨域与不可逆效果

跨Realm/Circle/Sidecar不提供原子提交。不可逆side effect只能在其前置Event committed后执行，并以exact committed ref作幂等键；失败使用领域saga补偿，不伪造跨stream事务。

## 10. MLS、恢复与快照

MLS只保留shared `ak.mls.genesis`和`ak.mls.commit` Event。治理 Station跟踪public state与`key_access_revision`，不持有secret。Commit与新增recipient Welcome delivery必须在一个authority transaction中全成或全败。恢复使用authority-signed typed snapshot + 每条获准stream tail。

## 11. 安全状态根与序列化

Snapshot 完整性由 manifest signature、typed sections、stream heads、history floors 和 chunk digests 提供；它不授权新写入。

## 12. Governance Station 与领域规则

每个 Realm 以 `governance_station_id` 建立 generation-0 authority，并只通过连续 `RealmAuthorityHandoff` 更换治理 Station。v1 领域规则和 digest 语义由协议版本固定；service key rotation 通过 service DID method history 处理。

## 13. 固定 content-address suite

current v1 的 Event、Event-derived object、Realm 与 RealmCommit ID 固定使用 RFC 8785 JCS + SHA-256，33-octet token 的首字节固定为 `0x01`。Realm schema、policy、header、query 或部署配置都不得选择或切换该 suite；其它已登记 digest suite 只可被其 owning typed domain（例如 Blob ref）显式使用。上述 ID 中出现其它 suite code 必须以 `unsupported_digest_algorithm` fail closed，历史引用不重哈希。

## 14. 提交结果与积压恢复

治理 Station 一次提交返回 committed、duplicate、rejected 或 retryable unavailable；后两者不写共享 pending 状态。

### 14.1 持久恢复与积压终结（normative）

Account Station 可以耐久保存 exact signed Event 并重试。它必须先刷新 current authority；handoff 后只向
new authority 转发。请求结果不确定时按 Event ID 查询或重放 exact bytes，不能重签或生成另一个 Event 冒充重试。

**恢复必须保住的五项持久事实（normative）**：重启、lease 过期、旧 worker 复活或积压重扫之后，实现 MUST
原样保住

1. 同一 stream 的 durable single-writer fence——同一治理 Station 的全部 worker MUST 共用该 fence 与其原子
   接受边界，MUST NOT 各自推进；
2. 已冻结的 exact candidate body——恢复方读取既有字节，MUST NOT 从 UI 状态、默认值或投影重建；
3. 唯一 lineage——一个逻辑命令只有一条谱系，恢复 MUST NOT 派生第二条并行谱系；
4. 原命令结果——已 committed / rejected / duplicate 的请求返回原结果，MUST NOT 被重算成另一个结论；
5. outbox——已建立的投递义务在恢复后继续存在，MUST NOT 因为重扫而丢弃或重复执行副作用。

**竞争的安全命令（normative）**：同时争用同一安全状态的命令 MUST 携带 revision precondition 执行，由
Station 串行化：落后 revision 的命令以 `failed_precondition` 拒绝。被拒绝的命令 MUST NOT 产生任何业务
效果——不写 typed current、不入 outbox、不消耗一次性材料、不推进任何位置。有权 author 可以读取新的 head
后重新签署并重投，但 MUST NOT 把普通竞争制造成一个"已接受的失败态"。

**超时不是权威（normative）**：lease 超时、请求超时与调度超时都只是本地调度条件。它们 MUST NOT 抹除一个
已签名并已接纳的位置，也 MUST NOT 授权一条并行 lineage 接管该位置。崩溃后 MUST 先查原 durable outcome；
结果未知时只能精确重投同一字节或继续查询，MUST NOT 另签一个 Event 冒充重试。

**跨 stream 原子性边界（normative）**：一次原子接受只能推进一个 authority stream。Realm、Circle、Sidecar
以及不同 Realm 的 stream 即使由同一治理 Station、同一进程或同一 serializable store 承载，也仍是独立的
权威边界；共址不得把它们合并成一个原子事务。跨 stream 工作流 MUST 以已提交的精确引用串联为 saga：每一步
分别取得自己的 RealmCommit，重试使用同一请求身份与 exact bytes，后续不可用时不得回滚或改写已提交的前序
事实；需要撤销业务意图时，必须在相应 stream 上提交显式补偿 Event。实现 MUST NOT 暴露或宣称跨 stream
all-or-nothing 接受，也 MUST NOT 用本地数据库事务、无限 defer 或静默部分写入冒充协议原子性。对应的可执行
转录为 `ak.vector.authority_commit.cross_stream_saga.v1`。

暂缺依赖、损坏记录与已验证不合法的请求 MUST 区分处置：隔离单项调度故障、保留安全 gate 与可诊断恢复入口，
MUST NOT 伪造终局拒绝。已证明无依赖的就绪工作与其它 Realm MUST 获得公平处理机会；扫描预算不是队列总量
上限，重复重启或固定读取第一页不得使已准入的义务永久饿死。

## 15. Actor 分叉与内容地址碰撞

相同 Event ID、不同 canonical bytes 是内容地址冲突，全部拒绝并告警；相同 Event 多次提交是幂等。Authority equivocation 按 §8 处理，base v1 不自动选 winner。
