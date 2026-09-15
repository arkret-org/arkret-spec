---
title: Service Surface And Bootstrap
status: candidate
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - service-http-binding.md
  - authority-commit-log.md
  - federation.md
  - current-results.md
  - ../conformance/normative-language.md
---

## 0. 规范语言

本文中的规范关键字按 [normative-language.md](../conformance/normative-language.md) 解释。字段级请求、响应、认证和错误合同以 [service-http-binding.md](./service-http-binding.md) 与 canonical operation registry 为准；本文只定义服务角色和跨 surface 不变量。

## 1. 目标（Goals）

Arkret v1 定义可互操作的 identity、authority commit、account sync、snapshot、Directory、Blob 与 invite surface。producer-signed Event 只有在其所属 Realm/Circle/Sidecar stream 的**当前治理 Station**签发 `RealmCommit` 后才成为共享 accepted 事实。

Realm、每个 Circle、每个 Sidecar 各有独立 stream；不存在 Realm 总链或跨 stream position。Account-private 数据、DeviceMessage、Signal 和 Blob bytes 不进入这些 stream。

## 2. 基本原则

### 2.1 DID Document 只做发现，不直接承载全部状态

DID method state 用于解析稳定 `did_core_id`、service identity、verification method 与 HTTPS endpoint。Realm current state、member、capability、MLS epoch、通知或 inbox 不写入 DID Document。

### 2.2 治理 Station 是每条 Realm stream 的唯一提交权威

- producer Event 是内容与用户意图的真实性来源；
- 当前治理 Station 是 admission、顺序、finality、复制和 current projection 的唯一权威；
- `RealmCommit` 绑定 exact Event、stream、position 和同 stream predecessor；
- 消费 Station验证 producer proof、authority chain、commit signature 与逐 stream 连续性；
- Directory、invite、cache 和 mirror 只提供 locator，不能产生或替代 authority。

治理 Station可能审查、扣留或停止写入，因此 v1 明确接受单权威的可用性与治理信任代价。协议不再要求客户端交叉验证 CBS、Seal、Cell root、actor chain 或 reducer profile。

### 2.3 接口必须天然支持幂等重试

同一 Event canonical bytes 以 `event_id` 幂等；同一 committed 结果以 `commit_id` 幂等。相同 Event ID 对应不同 bytes、相同 stream position 对应不同有效 Commit，均为安全故障并 fail closed。网络失败后 caller 重放 exact request，不重新签 Event。

### 2.4 服务必须公布自己的实现 profile

`ServiceDescribe` 公布 `protocol_version`、supported operation bundles、features、schema profiles、limits 与 transport。固定 v1 reducer/digest 语义不是 Realm 可选择 profile；服务不得继续广告退役的 Seal/Cell/CBS/history-key/MLS-governance-proof operation。

### 2.5 核心角色、Station capability 与可选服务

| 角色 | 职责 |
| --- | --- |
| Account Station | 认证本地账号，保存 signed draft，转发到 current authority，向自己的客户端提供 trusted current/sync。 |
| Realm governance Station | 对 Realm、每个 Circle、每个 Sidecar 的独立 stream 分配 position、签 RealmCommit、执行 typed reducer、生成 snapshot 与复制 outbox。 |
| Consumer Station | 验证 authority chain/Commit 连续性并向本地成员提供获准结果。 |
| Directory | 返回 discovery projection 与 authority locator；不执行 join，不选择 authority。 |
| Blob/Media/Push 等 | 仅在各自委托边界工作，不取得 Realm commit authority。 |

一个 Station 可以同时承担多个角色，但每个请求的 service identity、Realm authority generation 和 operation contract必须明确。

#### 2.5.1 Account Authority 与认证方法发现

Account Authority 是 Station 的账号准入逻辑入口，不是独立 Realm authority。Passkey、OIDC、SSO 等 provider 只提供认证输入；它们不能签 RealmCommit。账号恢复、session、device 与本地 draft queue 不改变 Realm 的 current governance Station。

### 2.6 Service DID 权威入口与路由解析（normative）

服务调用方 MUST 验证 `did_core_id` 对应的 method-native 当前状态、唯一 `ArkretService` entry、`serviceKind` 和 canonical HTTPS endpoint。缓存、邀请和 Directory 行都是 locator。

Realm authority 还必须验证 genesis 的 generation-0 service、连续 old→new handoff chain、已观察最高 generation 的防回滚约束，以及目标 service 对 caller nonce 的短期 `current_assertion`。只有这一 bundle 验证成功后，endpoint 才可作为 current governance Station。

## 3. 通用服务描述接口

所有可发现服务提供 `GET /_arkret/describe`。响应只广告 registry 中存在且本部署真实实现的 operation bundle。HTTP/JSON 是 v1 core binding；其它 transport 必须逐 operation 等价映射认证、授权、幂等、分页、错误和流控。

### 3.0 Describe response claim levels

描述信息分为协议固定能力、部署声明能力和运行时可用性。Describe 不能证明某服务是某 Realm 的 current authority；authority 身份只能由 `RealmAuthorityBundle` 证明。

#### 3.0.1 Bundle 展开与 transport 求交

实现先展开 canonical operation bundle，再与调用方和服务共同支持的 transport 求交。求交为空即不支持，不得静默替换另一个 operation。

### 3.1 Identity Resolution Surface

Identity surface 处理 method-native DID 状态，不处理 Realm Event finality。

#### 3.1.1 描述 registry

返回 method、proof suite、历史能力与大小限制。

#### 3.1.2 获取当前 DID Document

必须返回可独立验证的当前 method state；携带的旧文档或 TLS 可达性不构成 freshness。

#### 3.1.3 获取 DID 日志

有历史的方法返回从已知 head 到目标 head 的连续原生日志；无历史的方法必须显式声明其信任限制。

#### 3.1.4 提交 DID 更新

DID operation 的 admission、receipt 和 witness 语义属于 DID method，不产生 RealmCommit。

#### 3.1.5 获取 receipt / witness 证明

Receipt 仅证明 identity registry/witness 对 method operation 的观察，不证明 Realm admission。

#### 3.1.6 写入确认建议

高保证部署可以要求 method 自身的多 witness 策略；这不恢复 Realm 的分布式共识。

## 4. Events API

Events API 接收 producer-signed Event，并返回 authority commit 状态。`queued` / `forwarding` 只是本地队列状态；只有有效 `RealmCommit` 才是共享 `committed`。

### 4.1 描述 Events API

Describe 至少声明 self submit/read/subscribe 能力；承担 federation 的 Station另声明 peer submit、per-stream scan 和 committed exact resolve。每个 stream selector 都是 closed `stream_ref`，Circle/Sidecar position 不得通过 Realm stream 暴露。

### 4.2 提交 Event

`ak.self.events.command.submit.v1` 接收单个 `EventInitialSubmission {event}`。Account Station验证本地 session 与 producer proof，随后把 exact bytes 转发给已验证 current authority；它不能自行报告 accepted。

`ak.peer.events.command.submit.v1` 只允许目标 Realm 的 current governance Station执行 admission。结果为 `committed`、`duplicate`、`rejected` 或 retryable unavailable状态。成功返回 Event 与 `RealmCommit`；拒绝不写共享 pending 对象。

### 4.3 获取单个 Event

`ak.self.events.resource.get.v1` 返回调用方可见的 committed Event 及其 Commit 坐标。不可见与不存在保持不可区分。

### 4.4 批量获取 Event

跨 Station 精确取证统一使用 `ak.peer.events.read.resolve_committed.v1`。selector 是 `{event_id, commit_id, stream_ref, stream_position}`；响应必须让调用方逐项核对，不接受 caller-supplied Event、裸 Event ID 或 scan cursor 作为完整性证明。

### 4.5 列出 / 回填 Event

`ak.self.events.read.scan.v1` 与 `ak.peer.events.read.scan.v1` 按**单个获准 stream**的连续 position 分页。每页不得把多个 Circle/Sidecar 拼成 Realm 总序，也不得用隐藏 stream 的 position gap 暗示其活动。历史可见性、membership join floor 和 retention 可以裁剪可读起点。

### 4.6 获取 Event frontier

frontier 是每条已获准 stream 的 `{head_commit_ref, next_position}` 集合，不是 actor frontier，也不是全 Realm 总 head。公开 authority bundle只披露 Realm stream head；私有 Circle/Sidecar heads 只进入获权 snapshot 或 handoff manifest。

## 5. Account Aggregate / Snapshot Surface

Account aggregate 是自己的 Station提供的受信投影。它可以聚合多个 Realm，但必须保留每条 Realm/Circle/Sidecar stream 的独立 cursor/position；聚合 cursor 只是 Station-local resume token，不是 RealmCommit predecessor。

### 5.1 Account 自服务与描述

viewer、profile、account subscribe 与 cursor revoke 只作用于已认证账号。Profile Event若属于 PCR Realm，同样必须由其 current authority commit；Account-private preference 则继续使用自身的 Station-local合同。

### 5.2 snapshot 入口

`ak.self.realm_state_snapshot.read.manifest_head.v1` 返回 current governance Station签署的 typed snapshot manifest。Snapshot 包含 typed sections、每条获准 stream head、history floor 和 chunk digests，不包含 Cell、state root 或 reducer replay program。客户端从当前 authority取得 snapshot，再从各自 head 继续拉获准 tail。

### 5.3 Event / Seal 状态与确定性 current

Seal 已退役。本节锚点保留供旧引用跳转；现行规则如下：Event 状态只区分本地 queued/forwarding 与 authority 的 committed/rejected。Typed current result由治理 Station按 commit 顺序执行领域 reducer产生，并带来源 `commit_id`、`stream_ref`、`stream_position` 和领域 revision。客户端不得从 timeline 最后一个同 kind Event猜 current。

### 5.4 明文与服务信任

MLS 未激活的 scope 是明文 scope，治理 Station可见内容；这必须向用户披露。MLS 激活后治理 Station仍可见 sender、scope、时间、大小、routing 和 group churn，但不持有 group secret。Directory、Push 与未授权投影服务不得接收正文。

## 6. Search / Projection Semantics

搜索、inbox、notification 与 View 默认是 own-Station 或客户端派生结果。任何远端投影都必须标明其来源 committed refs 与可见性边界，且不能成为 authority。

### 6.1 结构化查询形状

查询复用 registry 的 closed request/response schema；服务不得增加 caller-controlled state key、reducer 或 authority selector。

### 6.2 Strand Discussion / Context Projection

Discussion 投影按 typed Strand/Message current 生成；跨 stream 引用不产生跨 stream 顺序。

### 6.3 Inbox / Notification Projection

通知是提示。客户端收到后仍从 own Station读取对应 Commit/current result。

### 6.4 全文搜索

搜索范围不得超过 caller 当前可见的 committed plaintext或本地已解密内容。

### 6.5 明文搜索边界

第三方索引明文需要显式 policy 委托；MLS ciphertext 不得通过搜索 surface 解密。

## 7. Blob Surface

Blob surface 管理 bytes，不判断 Realm Event accepted。

### 7.1 上传 blob

上传返回内容摘要引用；引用进入 Event 后仍需 authority commit。

### 7.2 查询 blob 头信息

metadata 查询遵守引用 Event 的当前访问控制。

### 7.3 下载 blob

下载授权不授予其它 Event、stream 或历史读取权。

## 8. Directory Surface

Directory 只提供可验证投影与 locator。其 `DirectorySourceRefAccess.source_refs` 是 `CommittedEventRef[]`，每项绑定 Event、Commit、stream、position，并只通过 `ak.peer.events.read.resolve_committed.v1` 验证。

### 8.1 描述 directory

Describe 公布查询、ingest、anti-enumeration 和 TTL 限制。

### 8.2 搜索 Realm

搜索结果不是 authority assertion。

### 8.3 精确解析 Realm

解析可以返回 authority locator；caller 仍必须验证 nonce-bound authority bundle。

### 8.4 搜索与解析 Organization

Organization 投影不能授权 Realm join 或治理写入。

### 8.5 搜索 Actor / Handle

结果遵守 visibility 和 anti-enumeration；handle 不替代 AccountId/ActorId。

### 8.6 私密联系人发现

PSI/OPRF 输出不得泄露未匹配集合或 Realm membership。

## 9. MIMI Provider Facade Surface（extension profile）

MIMI facade 只映射已注册互操作 operation，不取得 Arkret authority。

## 10. Capability / Invite Surface

Invite 与 capability 是 typed Event或专用 delivery object。Invite携带的 service 是 locator；join 必须提交给 current authority。无已完成 handoff时，旧 authority永久丢失不会触发自动 takeover。

## 10.1 Agent Surface

Agent 继续使用自身 producer key、controller authorization 和 Account Station认证。治理 Station不能代签 Agent Event。

## 11. Realm Bootstrap Strand

新加入者自己的 Station从当前治理 Station取得 nonce-bound authority bundle、签名 typed snapshot 与获准 stream tails。默认不从邀请人 Station、genesis Station或任意 member Station拉全历史。`since_join`、private Circle 与 retention floor 必须在 snapshot/history floor 中体现。

## 12. 新鲜度与多服务并存

多个 locator可以并存，但一个 Realm generation 只有一个 current governance Station。看到更高 generation 后不得回滚；互斥 handoff、相同 generation 不同 cut 或 authority equivocation 必须冻结相关 Realm/stream。

## 13. 传输安全与密文

所有 service-to-service 请求验证 service identity、TLS、HTTP Message Signature、audience、nonce/expiry 和 replay。Transport protection 不替代 producer proof、RealmCommit 或 MLS。

## 14. 防滥用与配额机制 (Anti-Spam & Quota)

限速和配额可以拒绝新请求，但不能改写已 committed history。

### 14.1 存储责任与 Blob Quota

配额按 Station/Realm policy执行；Blob bytes 与 Realm log分别核算。

### 14.2 写频率控制 (Rate Limiting)

retryable throttle 不产生 pending Realm state；重试必须复用 exact Event。

## 15. 设计决定

v1 选择单治理 Station、逐 Realm/Circle/Sidecar 独立 authority stream，以实现简单、可判定的顺序、撤销、bootstrap 与 handoff。代价是 authority 的审查权与写可用性单点；Base v1 不提供自动选主或 Byzantine 共识。

## 16. HTTP/JSON Binding

全部 canonical path、method、schema 与 error mapping 见 [service-http-binding.md](./service-http-binding.md)。

## 17. 线级互操作要求

实现 MUST 验证 Event/Commit/authority chain；逐 stream 检查 position/predecessor；拒绝跨 stream predecessor；不暴露隐藏 stream gap；不广告退役 operation；并在 snapshot、scan、resolve、handoff 与 MLS transaction 上保持同一 committed 坐标。
