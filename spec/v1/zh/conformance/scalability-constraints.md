---
title: Scalability Constraints
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../sync/authority-commit-log.md
  - ../sync/service-http-binding.md
  - encoding.md
---

## 0. 规范语言

本文关键字按 [normative-language.md](./normative-language.md) 解释。具体 schema 中更小的上限优先；实现不得放宽本文硬上限。

## 1. 目标

本文件限制 parser、authority admission、逐 stream 复制、snapshot、projection 与 MLS transaction 的最坏成本。

## 2. 通用 Wire 上限

| 项 | v1 硬上限 | 规则 |
| --- | ---: | --- |
| canonical Event | 1 MiB | 超限 `payload_too_large`；大正文/附件走 Blob。 |
| canonical RealmCommit | 256 KiB | Commit 不复制 Event payload、state root或 reducer effects。 |
| 非流式 JSON request/response | 8 MiB | operation registry 标为 non-streaming JSON 时适用。 |
| 非流式 HTTP message content | 16 MiB | 完整解析/JCS 前停止读取。 |
| 单 header value / aggregate | 8 KiB / 32 KiB | 专用字段可更小。 |
| path + query | 8 KiB | 大 selector 使用注册的 POST body。 |
| Event `semantic_refs[]` | 128 | typed business refs；不存在 predecessor/actor-chain refs。 |
| 一次 authority submit | 1 Event | v1 不定义通用 Event batch原子提交。 |
| stream scan page | 1,000 Commits | 一次仅一个 `stream_ref`。 |
| authority generation | unsigned 64-bit | 严格单调；不能回滚。 |
| stream position | unsigned 64-bit | 每条 Realm/Circle/Sidecar stream各自从 0 连续递增。 |
| canonical JSON/CBOR嵌套深度 | 64 | 超限 `structure_depth_exceeded`。 |
| deterministic CBOR单 map/array项数 | 65,536 | 解码器在分配前检查。 |
| cursor decoded payload | 64 KiB | cursor 还同时受 transport上限。 |

### 2.1 三层大小边界（normative）

Event canonical bytes、operation canonical body、HTTP wire bytes 是三个独立测量对象，三项上限同时成立。

#### 2.1.1 Event（1 MiB）

测量完整 producer-signed Event canonical JSON。Event没有 `unsigned`、`producer_revision`、`hlc`、`domain_refs`、`commit_authorization_state`、`commit_base`、`preconditions`、`expected_revision` 或 `requirements`。

#### 2.1.2 JSON operation canonical body（8 MiB）

在 schema validation 前执行有界 parse，在需要 transcript/JCS时再测 canonical body。更小 operation上限优先。

#### 2.1.3 HTTP wire message content（16 MiB）

按 transfer/content decoding后的 message content计；达到上限立即停止读取。

#### 2.1.4 Content-Encoding（normative）

压缩前后均设上限，禁止压缩炸弹、递归编码和未声明算法。

#### 2.1.5 二维 batch 与 pagination（normative）

同时限制 item count 与 bytes。达到任一上限即分页或拒绝，不得截断单个原子 item。

#### 2.1.6 固定值与 Describe（normative）

协议硬上限不能由 Describe放宽；部署可以声明更小值。

#### 2.1.7 Streaming 与 binary 例外（normative）

流与 Blob使用各自 frame/chunk上限；例外不改变单 Event/Commit限制。

#### 2.1.8 实现顺序（normative）

先限 transport bytes，再有界解析，随后 schema、canonical ID、producer proof、authority admission。

#### 2.1.9 错误语义（normative）

确定超限返回 `payload_too_large` 或 schema定义的 `limit_exceeded`；暂时资源不足使用 retryable错误，不创建 Realm pending state。

#### 2.1.10 明确否决

不得通过截断 refs、拆分一个 RealmCommit、把多个 stream合成总 position或接受部分 MLS Commit+Welcome事务来规避上限。

### 2.2 Protocol-level time tolerances（normative）

协议级时钟容差的唯一机器真源是
[`contract-registry.json#protocol_time_tolerance_registry`](../../artifacts/registry/contract-registry.json)。
实现 MUST 按场景标识读取容差，不得从本页、某份 schema description 或 fixture 私自复制数值。
容差条目只定义量值；方向由场景单独定义：

- `ak.time_tolerance.approval_approved_at.v1` 是单侧 future guard，只拒绝超过未来上界的
  `approved_at`，不得据此给过去时刻增加宽限；
- `ak.time_tolerance.temporal_constraint.v1` 对未来的 `not_before` 与过去的 `expires_at`
  使用同一量值，边界包含在可接受区间内；
- `ak.time_tolerance.blob_presign_ttl.v1` 对未来的 `issued_at` 与过去的 `expires_at`
  使用其独立的短窗口量值，边界包含在可接受区间内。

部署参数（例如 `revocation_index_propagation_max_ms`）不是协议时钟容差，MUST 显式声明，
不得把上述任一量值当作未声明部署参数的隐式缺省值。

## 3. 授权与 Capability 上限

| 项 | 上限 | 规则 |
| --- | ---: | --- |
| Event `semantic_refs[role=authorized_by]` | 64 | 只携带业务所需 exact refs；current authority仍在 commit位置求值。 |
| capability constraints | schema定义，默认≤64 | 未知 critical constraint fail closed。 |
| join policy gates | 16 | gate id唯一。 |
| authority handoff chain item | 每代 1 | generation严格+1；同代互斥项为安全故障。 |

授权缓存必须绑定 current authority generation与领域 revision。相关 committed state变化后立即失效。

## 4. Authority commit 上限

Authority commit 预算如下：

| 项 | 上限 | 规则 |
| --- | ---: | --- |
| 单 stream并发 head CAS | 1 winner | 相同 predecessor并发提交只有一个成功。 |
| 单 position有效 Commit | 1 | 两个不同有效签名为 authority equivocation，冻结该 Realm/stream。 |
| Realm active Circle数 | 1,000 | Circle各有独立 stream。 |
| Realm active Sidecar数 | 10,000 | Sidecar各有独立 stream；部署可收紧。 |
| Realm State Snapshot inline response | 8 MiB | `ak.self.realm_state_snapshot.read.manifest_head.v1` 属于 non-streaming JSON；超限必须 fail closed，不得截断 `current_state_entries[]`、visible heads 或 floors；v1 未登记 chunk/paging fallback。治理 Station 必须把可向任一 caller 披露的最大 closed signed snapshot 的 RFC 8785 canonical bytes 作为 Realm 硬容量预算。 |
| snapshot manifest streams | 11,001 | Realm + 上述 Circle/Sidecar理论上限；只返回 caller获准的 streams。 |
| handoff manifest streams | 同上 | 私有传输覆盖全部 stream heads，不公开隐藏 stream。 |

### 4.1 Realm Snapshot 硬容量预算

v1 选择内联硬上限，不增加分页、chunk、continuation cursor 或第二套 snapshot identity。治理 Station 在接纳任何会改变
visible stream head、typed current row 或 history floor 的 RealmCommit 前，必须以该事务的候选 durable cut 构造
「最大披露投影」：包含该 cut 下全部可能对任一合法 caller 披露的 streams、rows 与 floors，加入完整固定长度 Ed25519
signature 字段后按 RFC 8785 序列化。结果不得超过 8,388,608 bytes。超限时整个写入以
`failed_precondition`／`snapshot_capacity_exceeded` 拒绝，Realm 状态零变化；不得先提交再让 snapshot read 失败。

任一实际 caller 的返回只能是该最大披露投影按权限删除元素后的 closed 同-cut 子投影，因此不得比已验收的最大投影更大。
实现不得依赖元素计数或平均大小估算，必须测量最终 canonical bytes。并发写入必须在同一 durable admission serialization/CAS
边界内计算，不能让两个分别未超限的候选共同越界。读取仍须复测最终 body；若旧数据、损坏或迁移造成超限，读取整份
`payload_too_large` fail closed。该 Realm 随后只允许能在同一事务中使最大披露投影回到上限内的治理缩减写入，其他写入拒绝；
不得截断、返回 partial success 或恢复旧 unsigned chunk。

### 4.2 Progressive authority-commit Backfill Profile

渐进恢复固定为：验证 current authority bundle → 验证 typed snapshot → 对每条获准 stream 从 snapshot head 逐 position 补 tail。单条 stream 失败不允许从其它 stream 推测缺失 Commit，也不阻塞无关 stream。

## 5. Space / Relation / View 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| active Space / Realm | 5,000 | 超限分页或拒绝创建。 |
| active Circle / Realm | 1,000 | 每个 Circle独立 stream。 |
| active MLS-backed Circle / Actor | 256 | 控制 epoch churn与 fanout。 |
| active Relation / object | 10,000 | projection必须分页。 |
| View page | 1,000 | cursor绑定 selector与 current revision。 |
| Message attachments | 32 | 大内容走 Blob。 |
| inline text | 256 KiB UTF-8 | 超限使用 long-text Blob。 |
| Space nesting | 8 | typed reducer在 commit admission时拒绝成环/超深。 |

## 6. E2EE 与设备上限

| 项 | 上限 | 规则 |
| --- | ---: | --- |
| KeyPackage claim batch | 100 | 每个 claim一次消费。 |
| MLS Welcome deliveries / submission | 1,000 | 与 `ak.mls.commit`原子全成或全败。 |
| Welcome ciphertext | 1 MiB | 每 recipient独立测量。 |
| MLS public tree material | 8 MiB | 更大材料走内容寻址 Blob。 |
| epoch gap 恢复 | 32 | 更大 gap 使用 snapshot/public-state 与已持有的本地 MLS state；服务器不交付 epoch secret。 |
| active push routes / device | 16 | Account-private delivery限制。 |

### 6.1 身份、邀请与推送隐私窗口

Invite/Directory只返回有界 authority locator。Push payload不携成员表、hidden stream head、消息正文或MLS secret。Locator/notification过期后重新从 own Station解析。

## 7. Retention、Snapshot Pruning 与 Tombstone 上限

治理 Station可以按 policy裁剪 raw payload，但必须保留可验证的 Commit连续性、typed tombstone/stub、snapshot history floor和必要审计 ID。裁剪范围之前不可读取不等于 position gap。

Snapshot SHOULD 至少保留当前和一个前代有效 manifest。Planned handoff snapshot必须覆盖全部 stream heads、current typed state、Event/Commit/stub幂等索引、replication outbox和MLS public/Welcome queue；不得包含 member private keys。

### 7.1 Current result 的边界

实现内部数据库表与索引不是 wire contract。Event、snapshot、query 与 proof 只暴露各领域 schema 明确定义的 typed result，不暴露通用 state model、dot、root 或 projection operation。

## 8. 错误语义

结构性超限永久拒绝；authority暂时不可用返回 retryable状态；expected revision/head竞争返回 conflict并要求调用方基于新 current重签或重试。拒绝和 retryable都不产生共享 pending Commit。

### Welcome 收件人发现窗口

Welcome 通过 recipient-scoped `MlsWelcomeDelivery` queue 读取，默认 page 20、最大 100，按 `welcome_id` 幂等并显式 ACK。

### 8.1 self operation 预算与通用错误

own Station必须在 service describe公布更小的 rate/page预算。`rate_limited`、`payload_too_large`、`conflict`、`not_found`与 retryable unavailable状态不得被客户端解释为 committed；只有返回并验证有效 RealmCommit才可推进共享状态。
