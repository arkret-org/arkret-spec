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

本文件限制 parser、authority admission、逐 stream复制、snapshot、projection 与 MLS transaction 的最坏成本。Seal、Cell、CBS、actor-chain 与 history-key 的旧预算不再是 v1 合同。

## 2. 通用 Wire 上限

| 项 | v1 硬上限 | 规则 |
| --- | ---: | --- |
| canonical Event | 1 MiB | 超限 `payload_too_large`；大正文/附件走 Blob。 |
| canonical RealmCommit | 256 KiB | Commit 不复制 Event payload、state root或 reducer effects。 |
| 非流式 JSON request/response | 8 MiB | operation registry 标为 non-streaming JSON 时适用。 |
| 非流式 HTTP message content | 16 MiB | 完整解析/JCS 前停止读取。 |
| 单 header value / aggregate | 8 KiB / 32 KiB | 专用字段可更小。 |
| path + query | 8 KiB | 大 selector 使用注册的 POST body。 |
| Event `refs[]` | 128 | typed business refs；不存在 predecessor/actor-chain refs。 |
| 一次 authority submit | 1 Event | v1 不定义通用 Event batch原子提交。 |
| stream scan page | 1,000 Commits | 一次仅一个 `stream_ref`。 |
| committed exact-resolve refs | 100 | 必须是 `DirectorySourceRefAccess.source_refs` 的逐字子集。 |
| authority generation | unsigned 64-bit | 严格单调；不能回滚。 |
| stream position | unsigned 64-bit | 每条 Realm/Circle/Sidecar stream各自从 0 连续递增。 |
| canonical JSON/CBOR嵌套深度 | 64 | 超限 `structure_depth_exceeded`。 |
| deterministic CBOR单 map/array项数 | 65,536 | 解码器在分配前检查。 |
| cursor decoded payload | 64 KiB | cursor 还同时受 transport上限。 |

### 2.1 三层大小边界（normative）

Event canonical bytes、operation canonical body、HTTP wire bytes 是三个独立测量对象，三项上限同时成立。

#### 2.1.1 Event（1 MiB）

测量完整 producer-signed Event canonical JSON。Event没有 `unsigned`、`actor_seq`、`prev_refs`、`causal_refs`、`auth_context`、`preconditions`、`seal_basis` 或 `requirements`。

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

## 3. 授权与 Capability 上限

| 项 | 上限 | 规则 |
| --- | ---: | --- |
| Event `refs[role=authorized_by]` | 64 | 只携带业务所需 exact refs；current authority仍在 commit位置求值。 |
| capability constraints | schema定义，默认≤64 | 未知 critical constraint fail closed。 |
| join policy gates | 16 | gate id唯一。 |
| authority handoff chain item | 每代 1 | generation严格+1；同代互斥项为安全故障。 |

授权缓存必须绑定 current authority generation与领域 revision。相关 committed state变化后立即失效。

## 4. CBS / Lattice 上限

CBS/Lattice 已退役；本节锚点保留供旧引用跳转。现行 authority-commit预算如下：

| 项 | 上限 | 规则 |
| --- | ---: | --- |
| 单 stream并发 head CAS | 1 winner | 相同 predecessor并发提交只有一个成功。 |
| 单 position有效 Commit | 1 | 两个不同有效签名为 authority equivocation，冻结该 Realm/stream。 |
| Realm active Circle数 | 1,000 | Circle各有独立 stream。 |
| Realm active Sidecar数 | 10,000 | Sidecar各有独立 stream；部署可收紧。 |
| snapshot chunk | 8 MiB | chunk hash必须匹配 manifest。 |
| snapshot manifest streams | 11,001 | Realm + 上述 Circle/Sidecar理论上限；只返回 caller获准的 streams。 |
| handoff manifest streams | 同上 | 私有传输覆盖全部 stream heads，不公开隐藏 stream。 |

### 4.1 Progressive CBS Backfill Profile

旧 profile 已退役；现行渐进恢复固定为：验证 current authority bundle → 验证 typed snapshot → 对每条获准 stream从 snapshot head逐 position补 tail。单条 stream失败不允许从其它 stream猜测缺失 Commit，也不阻塞无关 stream。

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
| epoch gap直接恢复 | 32 | 更大 gap用 snapshot/public-state+range读取，不用 history-key。 |
| active push routes / device | 16 | Account-private delivery限制。 |

### 6.1 身份、邀请与推送隐私窗口

Invite/Directory只返回有界 authority locator。Push payload不携成员表、hidden stream head、消息正文或MLS secret。Locator/notification过期后重新从 own Station解析。

## 7. Retention、Snapshot Pruning 与 Tombstone 上限

治理 Station可以按 policy裁剪 raw payload，但必须保留可验证的 Commit连续性、typed tombstone/stub、snapshot history floor和必要审计 ID。裁剪范围之前不可读取不等于 position gap。

Snapshot SHOULD 至少保留当前和一个前代有效 manifest。Planned handoff snapshot必须覆盖全部 stream heads、current typed state、Event/Commit/stub幂等索引、replication outbox和MLS public/Welcome queue；不得包含 member private keys。

### 7.1 内建 cell plane 的 v1 限制

Cell plane 已退役；本节锚点保留。实现内部数据库表与索引不是 wire Cell，不得向 Event、snapshot、query或proof暴露 `CellRef`、state model、dot、root或通用 lattice operation。

## 8. 错误语义

结构性超限永久拒绝；authority暂时不可用返回 retryable状态；expected revision/head竞争返回 conflict并要求调用方基于新 current重签或重试。拒绝和 retryable都不产生共享 pending Commit。

### Welcome 收件人发现窗口

Welcome通过 recipient-scoped `MlsWelcomeDelivery` queue读取，默认 page 20、最大 100，按 `welcome_id`幂等并显式ACK。它不再是 Realm Event，也不通过 Seal或history-key索引发现。

### 8.1 self operation 预算与通用错误

own Station必须在 service describe公布更小的 rate/page预算。`rate_limited`、`payload_too_large`、`conflict`、`not_found`与 retryable unavailable状态不得被客户端解释为 committed；只有返回并验证有效 RealmCommit才可推进共享状态。
