---
title: Audited End-to-End Encryption (Profile)
status: candidate
normative: true
stability: v1
updated: 2026-05-25
sidebar:
  label: Audited E2EE
---

> **状态：可选 hardening profile**。本文档定义 `cx.profile.attested_audit.e2ee.v1` 与
> `cx.profile.disclosed_audit.e2ee.v1` 两类受审计 E2EE profile 的 normative 行为。v1 core
> 互操作 **不要求** 实现本 profile；只有在 Realm policy 显式声明 `audit_disclosure` 时启用。
> 基础 MLS / E2EE 架构见 [`encryption-and-audit.md`](./encryption-and-audit.md)。

## 0. 规范语言

本文中的规范关键字（**MUST** / **SHOULD** / **MAY** 等）按 [conformance/normative-language.md](../conformance/normative-language.md) 解释；仅大写形式具规范约束力。

## 1. 目标

在很多去中心化产品中，如果存在审查，往往是通过向客户端下发"旁路后门"或者弱化密钥机制实现的，这引起了极大的隐私恐慌。

Contrix 引入 **"透明留痕审计 (Transparent Audit Trail)"** 机制：既满足组织的强制合规要求，又向所有参与者提供可验证的审计记录。该机制划分为两类正交保证：

- **`attested` 类**（`cx.profile.attested_audit.e2ee.v1`）：通过 TEE / HSM / 等价硬件隔离把 key release 或明文输出**密码学绑定**到先写审计记录。
- **`disclosed` 类**（`cx.profile.disclosed_audit.e2ee.v1`）：仅在 Realm policy 中**公开声明**审计代理在场并约定流程，**不提供密码学/硬件强制**——协议层不能阻止恶意持钥客户端绕过日志。

`disclosed` 与 `attested` **不是强弱不同的同一保证**，而是不同 family 的保证。任何把两者混称为 "Auditable E2EE" 或暗示二者等价的措辞都不符合本规范（见 §6）。

## 2. Audit Policy 声明

要启用此机制，Realm 的 `schema/policy` 必须显式声明 **两个正交字段**：`audit_disclosure`（透明度承诺，两类共用）+ `audit_assurance`（保证类型，决定使用哪个 profile）。

```json
{
  "encryption_profile": "mls_rfc9420",
  "audit_disclosure": {
    "audit_actors": ["did:web:compliance.acme.corp"],
    "purpose_classes": ["legal_compliance"],
    "retention_days": 365,
    "ryw_receipt_required": true
  },
  "audit_assurance": "attested_hardware"
}
```

`audit_assurance` 是封闭 enum，且与 profile id 一一映射；schema 通过 `if/then` 强约束二者一致。

| `audit_assurance` 值 | 对应 profile | 含义 |
| --- | --- | --- |
| `attested_hardware` | `cx.profile.attested_audit.e2ee.v1` | Audit Agent MUST 在声明的 TEE / enclave / 等价硬件隔离环境中运行；remote attestation evidence MUST 走 [`attestation-evidence.schema.json`](../../artifacts/schemas/attestation-evidence.schema.json)（schema id `cx.schema.attestation_evidence.v1`），结构化绑定 `realm_id`、enclave measurement、attestation chain、attestation key（与 `cx.audit.epoch_key_destruction.proofs[*].verification_method` 共享 root of trust）、verification_method、validity 窗口、revocation 检查、operator DID、audit_purpose、`audit_policy_version_digest`（canonical JSON 规则见 [`conformance/encoding.md` §2](../conformance/encoding.md)）。Verifier MUST 拒绝 `realm_id` 与实际 Welcome / Event Realm 不一致的 evidence；相同 policy hash 不使 evidence 可跨 Realm 复用。Key material 与明文输出 MUST 在受控边界内处理。 |
| `disclosed_policy` | `cx.profile.disclosed_audit.e2ee.v1` | 不要求 TEE。Audit Agent 仍然 MUST 执行 `cx.audit.accessed` 先写后解密流程并等待 RYW receipt，但**保证类别仅是合规与流程承诺，不是密码学强制**。Realm policy MUST 在加入前可见确认该降级。 |

客户端在加入声明 `audit_disclosure` 的 Realm 前 MUST 读取 `audit_assurance`，并按 §2.1 显示**正确分类**的 join warning；MUST NOT 用同一段笼统文案覆盖两种保证。

### 2.1 Join Warning（normative MUST，必须分两套）

实现 MUST 按 `audit_assurance` 显示如下两套文案之一（也可本地化，但必须保留区分）。MUST NOT 把两套文案合并成一段或省略关键限定词。

- 当 `audit_assurance = "attested_hardware"`（profile = `cx.profile.attested_audit.e2ee.v1`）：

  <!-- lint-ignore: ST002 — normative end-user-facing UI string, second person intentional -->
  > 这是一个**硬件强制审计的加密空间**。审查由声明的 TEE / 飞地强制执行先写后解密：合规员的访问会在你看到之前先公开留痕，群内可验证。被移除的合规员仍可解密其成员期间的历史。

- 当 `audit_assurance = "disclosed_policy"`（profile = `cx.profile.disclosed_audit.e2ee.v1`）：

  <!-- lint-ignore: ST002 — normative end-user-facing UI string, second person intentional -->
  > 这是一个**仅依赖流程承诺的审计加密空间**。合规员能解密内容；空间公开声明会留痕，但**协议层不能阻止恶意合规客户端在不留痕的情况下解密内容**——是否信任取决于你对该组织和该客户端实现的信任，而不是密码学强制。被移除的合规员仍可解密其成员期间的历史。

`disclosed_policy` 文案中"协议层不能阻止恶意合规客户端…"一段 MUST 完整呈现，不得作为可折叠的次要说明被默认收起。

## 3. 审计节点的入群

`did:web:compliance.acme.corp` 对应的合规客户端（Audit Agent）会作为一个合法的、只读的成员，由创建者通过正常的 `cx.mls.commit` 邀请加入 MLS 群组。这意味着：

- Audit Agent 从密码学上获得了当前 Epoch 的解密能力。
- 群组内所有的普通成员都可以通过检查 MLS 树，清晰地知晓 Audit Agent 的存在。

### 3.1 审计节点最小权限与前向安全边界

Audited E2EE 必须明确承认其安全边界：Audit Agent 是真实 MLS 成员，因此它被移除后仍可解密其成员期间已经收到且按 retention policy 保留的历史消息；Audit Agent key 泄露会影响其可访问 epoch 的机密性。Contrix 不得把这种模式描述为"审计方不可见内容"或"对审计方仍保持完整 forward secrecy"。

Audit Agent profile MUST 满足：

- 只授予 `cx.audit.accessed`、必要的 key receive / decrypt capability 和 policy 明确声明的 audit query capability；不得授予普通发消息、编辑内容、管理 membership、签发 capability、推进 MLS epoch 或更改 Realm policy 的权限。
- MLS leaf credential、service DID、attestation evidence、operator DID、保留策略、允许的 audit purpose 和有效期 MUST 对成员可见，并被 Realm policy / `governance_binding.policy_root` 覆盖。
- `audit_assurance = "attested_hardware"` 下，MLS key material、exporter secret、历史 epoch secret 和明文输出 MUST 在 HSM、TEE、enclave 或等价硬件隔离边界内处理；remote attestation 必须绑定代码 measurement、service DID、policy version、audit purpose、created_at 和 expiry。
- `audit_assurance = "disclosed_policy"` 下，客户端必须按 §2.1 disclosed 文案向成员显示这是**流程性披露**，不是硬件强制保证；MUST NOT 复用 `attested_hardware` 文案。
- Audit Agent 的本地 key retention MUST 有上限，并能被成员验证为 policy 声明的一部分；legal hold 或监管保留需要单独声明，不能由 Agent 私下延长。

#### 3.1.1 Audit Agent 移除后 epoch key destruction attestation(`attested_hardware` 专属)

> **不实现本节即不得使用 `audit_assurance="attested_hardware"` 措辞。** 仅声明 attested 文案而不发布 destruction attestation 时,Audit Agent 与软件审计在 forward secrecy 行为上**完全等价**;Contrix 把这种部署视为 spec violation,group MUST 在下一轮 MLS commit 中把 `audit_assurance` 强制降级为 `disclosed_policy` 或更弱形态，并按 §2.1 重新展示降级文案。

> **非 retroactive revocation**：`cx.audit.epoch_key_destruction` 只能证明声明的 enclave / HSM 在某时刻销毁了其受控边界内仍持有的 epoch key material，从而限制未来继续访问；它不能密码学证明历史 epoch key、历史明文或导出副本从未泄漏。已交付给 Audit Agent 或其运行环境的历史 epoch 必须按“可能已被永久解密”建模。UI、合规说明和市场文案 MUST NOT 把本机制宣传为“可撤销历史审计访问”或“移除 Audit Agent 后历史内容密码学不可解”。

> **命名注意**：本节涉及的两个 event kind 名 `cx.audit.epoch_key_destruction` 和 `cx.realm.audit_policy_downgrade` 在 v1 registry 中**不携带** `.v<n>` suffix。Wire 形态版本化通过 Event envelope 的 `requirements.features[]` 表达，与 kind name 严格分离 —— 这与所有其他 `cx.*` event kind 的约定一致，见 [`../conformance/encoding.md`](../conformance/encoding.md) "Event kind / requirements 分层" 一节。

##### 3.1.1.1 触发条件

任一 `cx.mls.commit` 把 Audit Agent 从 MLS group 中 `Remove` 时(自愿离开 / 被踢 / device revoke 级联 / membership policy revoke 等任何原因) — 该 Audit Agent **MUST**:

1. 在对应 enclave / HSM 内部对**其在群成员期间持有的所有历史 epoch secret 与 exporter secret**(从其 join epoch 到 remove epoch 之间所有 epoch)执行密码学销毁(zeroize + secure erase 或等价硬件操作)。
2. 由 enclave / HSM 签发一条 **`cx.audit.epoch_key_destruction`** attestation event,内容覆盖被销毁的 epoch 范围、销毁完成 timestamp、enclave measurement、Audit Agent DID、remove commit ref。该 event 作为 reducer-input Event 提交给该 Realm,actor 是 Audit Agent service DID,proof 由 enclave / HSM 的 attestation key 签发(不接受普通 service signing key — 必须是被远程 attestation 绑定的 enclave-internal key)。
3. attestation event 与 Audit Agent 被 Remove 的 `cx.mls.commit` **MUST 同一 anchor batch** 提交;reducer 拒绝单独 anchor 的 remove(reason `audit_agent_remove_requires_paired_destruction_attestation`)。
4. attestation effect MUST 写入 `cx.component.audit.epoch_key_destruction.v1` audit state cell，cell subject 为 `(mls_group_id, audit_agent_principal_id, epoch_range)`；后续 `cx.mls.commit` 的 `governance_binding.policy_root` / `capability_root` MUST 覆盖该 audit state，证明新 epoch 已见到销毁事实。

##### 3.1.1.2 `cx.audit.epoch_key_destruction` 必填字段

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `audit_agent_principal_id` | did | 被移除的 Audit Agent service DID。 |
| `mls_group_id` | string | 该 Audit Agent 服务的 MLS group。 |
| `epoch_range` | object | `{first_epoch, last_epoch}`,两端 inclusive,覆盖该 Agent 持有 epoch secret 的全部 epoch。 |
| `destroyed_at` | timestamp | enclave 内时钟标记的销毁完成时刻。 |
| `enclave_measurement` | object | `{platform, code_digest, policy_version}` — 与 Audit Agent 入群时 attestation 中相同的 measurement;不一致 → reject `audit_agent_attestation_mismatch`。 |
| `remove_commit_ref` | id:event | 把该 Audit Agent 移除的 `cx.mls.commit` event id。reducer 校验该 event 在同一 anchor batch 中存在。 |
| `proof` | array | 至少一条 enclave-attested signature,`verification_method` MUST 指向 enclave attestation key(以 Audit Agent service DID 控制根追溯，与入群 attestation 共享 attestation chain)。 |

##### 3.1.1.3 Reducer 拒绝规则

| 失败模式 | reducer 拒绝 reason |
| --- | --- |
| `cx.mls.commit(remove Audit Agent)` 提交但同 anchor batch 内无配套 `cx.audit.epoch_key_destruction` | `audit_agent_key_destruction_attestation_missing` |
| destruction attestation 的 `enclave_measurement` 与入群 attestation 不同(暗示 attacker 替换了 enclave 镜像后再销毁) | `audit_agent_attestation_mismatch` |
| `epoch_range` 不完整(缺少该 Agent 已知持有的某些 epoch) | `audit_agent_epoch_range_incomplete` |
| destruction attestation proof 不是 enclave attestation chain 签发的(普通 service signing key 签发) | `audit_agent_destruction_proof_not_enclave_signed` |
| destruction attestation 的 `remove_commit_ref` 指向的 commit 不在同一 anchor batch | `audit_agent_destruction_not_paired_with_remove` |
| 后续 commit 未覆盖已 accepted destruction audit state | `audit_agent_destruction_not_covered_by_commit` |

##### 3.1.1.4 文案与降级义务

- 因 §3.1.1.1 step 3 强制 attestation 与 remove commit 同一 anchor batch，语义上 "remove 已生效但 attestation 缺失" 的中间态在 reducer 层不可达——任何缺失配套 attestation 的 remove commit 在 reducer 入口即被 §3.1.1.3 拒绝，不会落入 frontier。因此 §3.1.1.4 不再描述 grace window 路径。`cx.realm.audit_policy_downgrade` 仍是 active event kind，但只表示管理员 / policy server 在后续操作前显式把 Realm 从 `attested_hardware` 降级到 `disclosed_policy`；它 **MUST NOT** 被当作"remove 已接受但 attestation 超时"的补救事件，也不得 retroactively 使一个缺失 destruction attestation 的 remove batch 生效。
- destruction attestation 落盘后,UI MAY 显示"已由 enclave 完成受控边界内 epoch 密钥销毁 — 该 Agent 不应再通过该 enclave 继续访问对应历史"; UI MUST 同时避免暗示已经泄漏或导出的历史 key / 明文可被 retroactively 撤销。
- `audit_assurance = "disclosed_policy"` 部署**不要求**本节(disclosed 文案本就声明不提供密码学强制);只有 `attested_hardware` profile 必须实现。
- Fraud detection：attestation 落盘后，若同一 Audit Agent / enclave measurement 后续又签发对已销毁 epoch 的 `cx.audit.accessed`、RYW receipt 或外部 export proof，verifier MUST 标记 `audit_agent_destroyed_epoch_accessed`，quarantine 该访问链，并触发 Realm `audit_assurance` 降级或 operator incident。该检测使用 `cx.component.audit.epoch_key_destruction.v1` state，不依赖 UI 记忆。

##### 3.1.1.5 安全代价登记

- 优势:Audit Agent 一旦被移除，其历史 epoch decryption capability 在密码学层面被销毁。Audit Agent 即便保留 TEE image / HSM backup,因密钥已 zeroize 也不可恢复。
- 代价:enclave / HSM 必须支持 attestation-signed zeroization 操作(主流 TEE 如 Intel TDX / AMD SEV-SNP / AWS Nitro Enclave / SGX 均已具备此类原语);依赖纯软件审计 agent 的部署 MUST 改用 `disclosed_policy` profile,**不得使用** `attested_hardware` 措辞。
- 与 §1 disclosed 文案的区分:disclosed 部署移除 Audit Agent 后历史密钥**仍然存在**(只是 Realm policy 不再认可它);attested 部署移除时 enclave 内部已经销毁，这是两种 profile 的关键区别。

不需要常驻审计解密能力的 Realm SHOULD 使用 franking / moderation proof profile（例如 `cx.moderation.franking_proof` 或 profile 注册的等价 token）来证明消息可审计性，并在真正审计时由发送方、持钥成员或受控服务按 policy 解密；不得把 standing Audit Agent 作为唯一合规模式。

## 4. 强制留痕机制 (Audit Record Mandatory)

获得密钥并不意味着可以合规地随意查看。协议要求 Audit Agent 按声明的 audit profile 执行以下工作流；`cx.profile.attested_audit.e2ee.v1` 下该实现必须依托 TEE / enclave 或等价硬件隔离环境，并保证 MLS key、exporter secret 或解密明文不会在审计确认前离开受控边界：

1. **收到审查请求**：组织内部触发对某条涉嫌违规的 Message 的审查（如 `message_id: cx:message:99804430-0000-7000-8000-000000000000`）。
2. **强制上链/入库声明**：Audit Agent 在进行解密之前，MUST 生成一条 `kind="cx.audit.accessed"` 的不可撤销 Event，并提交给该 Realm：
   ```json
   {
     "kind": "cx.audit.accessed",
     "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
     "actor_id": "did:web:compliance.acme.corp",
     "payload": {
       "access_kind": "e2ee_plaintext_release",
       "writer_actor_id": "did:web:compliance.acme.corp",
       "target_ref": "cx:message:99804430-0000-7000-8000-000000000000",
       "purpose": "Internal legal compliance request #8801",
       "accessed_at": "2026-04-30T00:00:00Z",
       "ryw_required": true
     }
   }
   ```
3. **基于 RYW (Read-Your-Writes) 的因果确权回执等待**：为防止网络抖动或同步节点恶意丢包导致的"假动作死锁"（即记录没发出去但明文已吐出），合规飞地 MUST 等待因果确权回执，确认该 `cx.audit.accessed` 已经成功跨越本地局域网并在协作图中落盘。回执 MUST 携带 `audit_assurance_class` 字段，且其值 MUST 与 Realm policy 声明的 `audit_assurance` 一致；不一致时接收方 MUST fail closed。
   - **回执数量与 witness attestation**：`cx.profile.attested_audit.e2ee.v1` MUST 在解密前获得 ≥2 个 witness 联合 attested 的 RYW receipt（聚合规则见 §4.1.1）。`cx.profile.disclosed_audit.e2ee.v1` 在单签发者部署下 MAY 使用单源回执，但 receipt 的 `witness_attestation.kind` MUST 写为 `single_source`，且 `witness_attestation.witnesses[]` MUST 仅包含该唯一签发方；部署声明也 MUST 公开承认此降级。
   - **失效处理**：若后续 backfill / witness / state verification 证明该 `cx.audit.accessed` 未进入 accepted history、canonical bytes 与回执不匹配、`audit_assurance_class` 与 Realm `audit_assurance` 不一致、或确权来源无权签发该回执，Audit Agent MUST 将对应解密会话标记为 `audit_receipt_invalidated`，并在重新输出明文前重新发布审计事件并等待新的确权回执。普通 redaction 不会抹除已发生访问的 verification stub，但客户端应在审计视图中显示 redaction 状态。
4. **完成解密**：只有在接收到确权回执后，硬件飞地、HSM 或受控合规服务才被允许利用持有的 MLS 密钥将对应明文输出给合规人员。`cx.profile.disclosed_audit.e2ee.v1` MUST 按同一顺序执行并记录证明，但**对恶意持钥客户端不提供密码学阻断**——这是该 profile 的本质局限，不是实现缺陷。

### 4.1 RYW Receipt Schema

`cx.audit.ryw_receipt` 是 receipt 对象，用于满足 §4 步骤 3 的"因果确权回执"要求。它由 Events API、witness 或独立验证节点签发，证明特定 `cx.audit.accessed` 已经进入接收方 accepted history（或至少其 actor frontier 已经覆盖该 event）。

> **Object 与 durable Event 两种形态**（normative）：`cx.audit.ryw_receipt` 这个名字同时承担两种角色——
>
> 1. **Receipt object** — schema id `cx.schema.audit_ryw_receipt.v1`，作为 §4 步骤 3 的因果确权对象。所有 audit profile 都使用这种形态。
> 2. **Durable Event** — `event-kind-registry.json` 中 `cx.audit.ryw_receipt` 为 `status="active"`、`wire_scope="durable_event"`、`reducer_input=false`；仅在 `cx.profile.attested_audit.e2ee.v1` 下，receipt 同时作为 `Event.kind="cx.audit.ryw_receipt"` 提交到 Events API，把 receipt 永久写入 audit log。`cx.profile.disclosed_audit.e2ee.v1` 等其它 profile 下只产出 object form，不要把 receipt 当 durable Event 提交。
>
> 这两种形态共享同一 canonical payload；只是分发路径不同。下游 SDK / cotest scanner 在判断 `cx.audit.ryw_receipt` 是不是 Event kind 时 MUST 按当前 profile 判定，不要假定它"总是" Event kind 或"从不是" Event kind。与 `cx.event_batch_receipt`（receipt object only，不是 event kind）形成对照——后者在任何 profile 下都不会作为 `Event.kind` 出现。

Schema id：`cx.schema.audit_ryw_receipt.v1`

```json
{
  "receipt_id": "cx:receipt:0196418f-0000-7000-8000-000000000000",
  "schema": "cx.schema.audit_ryw_receipt.v1",
  "issuer": "did:web:witness.example.com",
  "issuer_role": "witness",
  "audit_event_id": "cx:event:019640a5-0000-7000-8000-000000000000",
  "audit_event_digest": "sha256:...",
  "realm_id": "cx:realm:0196419b-0000-7000-8000-000000000000",
  "trust_domain": "cx:trust_domain:did.webvh.example",
  "audit_actor_id": "did:web:audit-agent.example.com",
  "frontier": {
    "realm_frontier": ["cx:event:..."],
    "actor_frontier": {
      "did:web:audit-agent.example.com": {
        "actor_seq": 17,
        "event_id": "cx:event:019640a5-0000-7000-8000-000000000000"
      }
    }
  },
  "observed_at": "2026-04-26T00:00:00.123Z",
  "witness_attestation": {
    "kind": "federation_witness_attested",
    "witnesses": [
      {
        "issuer": "did:web:witness.example.com",
        "verification_method": "did:web:witness.example.com#receipt-key-1",
        "controlling_organization": "did:webvh:identity.foundation:org:witness-coop",
        "attested_at": "2026-04-26T00:00:00.123Z"
      },
      {
        "issuer": "did:web:witness2.acme.example",
        "verification_method": "did:web:witness2.acme.example#receipt-key-3",
        "controlling_organization": "did:webvh:z2dmjQyDxVnosYTzHAMbzYDRZkVrD32ea9Sr2XNs8NkgMB5mn:acme.example",
        "attested_at": "2026-04-26T00:00:00.456Z"
      }
    ]
  },
  "audit_assurance_class": "attested_hardware",
  "audit_policy_version_digest": "sha256:aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "proofs": [
    {
      "kind": "detached_jws",
      "alg": "EdDSA",
      "verification_method": "did:web:witness.example.com#receipt-key-1",
      "payload_digest": "sha256:...",
      "created_at": "2026-04-26T00:00:00.123Z",
      "jws": "..."
    }
  ]
}
```

字段语义：

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| `receipt_id` | yes | `cx:receipt:<uuid>`。 |
| `schema` | yes | 固定 `cx.schema.audit_ryw_receipt.v1`。该字段同时充当类型鉴别器，与 `cx.schema.flow.v1` / `cx.schema.message.v1` 等其它标准对象保持同一约定，receipt 不再额外携带 `type` 字段。 |
| `issuer` | yes | 签发方 service / witness DID。MUST 与 proof `verification_method` 同 DID。 |
| `issuer_role` | yes | `events_api` / `witness` / `peer_node` 之一，标记 receipt 来源类型。 |
| `audit_event_id` | yes | 对应的 `cx.audit.accessed` event 的 typed ID。 |
| `audit_event_digest` | yes | `cx.audit.accessed` envelope 的 canonical digest（与该 envelope `proofs[].event_digest` 一致）。 |
| `realm_id` | yes | `cx.audit.accessed` 所在 Realm。 |
| `trust_domain` | yes | 签发 receipt 时该 Realm 所属 deployment trust domain；MUST 与当前接收上下文和 enclosing audit envelope 的 Realm context 一致。 |
| `audit_actor_id` | yes | 发起 audit 的 Audit Agent DID。 |
| `frontier.realm_frontier` | yes | 签发时 issuer 已 accepted 的 Realm frontier。MUST 因果上 ≥ `audit_event_id`。 |
| `frontier.actor_frontier` | conditional | 至少包含 `audit_actor_id` 的 frontier。其它 actor frontier 由 issuer 选择性透出。 |
| `observed_at` | yes | issuer 观测到 `cx.audit.accessed` accepted 的时间。 |
| `witness_attestation` | yes | Witness attestation block。`witness_attestation.kind` 取值 `federation_witness_attested` / `single_source`；`witness_attestation.witnesses[]` 列出所有 attesting witnesses 的 `(issuer, verification_method, controlling_organization, attested_at)`。`kind` 取值 MUST 由 `witnesses[]` 的基数与独立性外部可验证地推导（`federation_witness_attested` 必须 `witnesses.length >= 2` 且 issuer / controlling_organization / verification_method 两两 distinct 且每个 issuer 出现在 Realm `audit.ryw_witnesses[]`；`single_source` 必须 `witnesses.length == 1`）；不一致 MUST 拒绝并 `audit_receipt_invalidated`。独立性由可外部验证的 witness 列表表达，而不是单点自报。详细聚合规则见 §4.1.1。 |
| `audit_assurance_class` | yes | `attested_hardware` / `disclosed_policy`。MUST 与 Realm `audit_assurance` 在该 receipt 的 frontier 处一致；不一致时接收方 fail closed。该字段是协议层向接收方透出的保证级别 hint，**不是**实现声称硬件 attestation 的依据；硬件 attestation 由 Audit Agent profile（`cx.profile.attested_audit.e2ee.v1`）的 attestation evidence 单独证明。 |
| `audit_policy_version_digest` | yes | Realm-bound policy hash（`sha256` over canonical JSON `{realm_id: <id>, trust_domain: <trust_domain>, audit_disclosure: <object>, audit_assurance: <string>}`）。让接收方 O(1) 校验"receipt 声明的 policy class 与 frontier 处实际 policy 一致"，无需重放事件，同时防止相同 policy 文本跨 Realm 复用。MUST 与 receipt frontier 处的 policy state 一致；不一致 fail closed (`audit_receipt_invalidated`)。 |
| `proofs` | yes | 至少一个 detached JWS，覆盖 receipt 全部字段（除 proofs 自身）。 |

规则：

`audit_policy_version_digest` 在 v1 中固定为 `sha256:<64 lowercase hex>`，不使用 hash agility。若未来需要迁移到其它算法，必须通过新的 schema/profile 明确升级，而不是让同一字段接受多算法值。

- Audit Agent MUST 在解密前等待至少一个有效 RYW receipt；`cx.profile.attested_audit.e2ee.v1` MUST 等待 `witness_attestation.kind="federation_witness_attested"` 的 receipt（即 `witness_attestation.witnesses[]` 同时包含 ≥2 个独立 witness）。
- Issuer 不得伪造未观测到的 receipt；任何客户端 / 审计客户端 MUST 拒绝 `audit_event_digest` 与 envelope 实际 digest 不符的 receipt，并按 `audit_receipt_invalidated`（参见 `error-code-registry.json`）处理。
- Verifier MUST 同时校验 `receipt.realm_id == enclosing audit envelope.realm_id`，且 `receipt.trust_domain == current receive context.trust_domain`。仅凭 `audit_policy_version_digest` 相等不得把 receipt 复用于其它 Realm 或其它 trust domain。
- RYW receipt 默认是 actor-private / ephemeral 在 `cx.profile.disclosed_audit.e2ee.v1` 下；在 `cx.profile.attested_audit.e2ee.v1` 下 receipt 可以同时作为 durable Event（`cx.audit.ryw_receipt`）进入 audit log，便于事后调查。
- Receipt 可被 redaction 覆盖，但 redaction 只清除 cleartext metadata；`audit_event_id`、`audit_event_digest` 与 `audit_assurance_class` 仍保留，以便审计链可还原。

### 4.1.1 `witness_attestation.kind="federation_witness_attested"` 的密码学聚合规则（normative）

`witness_attestation` 不是审计代理的"自报"声明，而是**接收方可独立验证的属性**。`kind="federation_witness_attested"` 等价于接收方在 receipt 的 `witness_attestation.witnesses[]` 上重新执行下列检查并全部通过；任一不成立 MUST 触发 `audit_receipt_invalidated` 并降级为 `single_source` 处理：

1. **多 witness 覆盖**：`witness_attestation.witnesses[]` MUST `length >= 2`；所有 witnesses entries 对应的 RYW receipt（每条 `cx.audit.ryw_receipt` 对象有自己的 `proofs[]`）覆盖**同一** `audit_event_id` + `audit_event_digest`。Audit Agent 在解密前 MUST 同时持有这两条 receipt 并以聚合形式提交给接收方校验。
2. **witness 独立性**：`witnesses[]` 中任意两个 entry 的 `(issuer, controlling_organization, verification_method)` 三元组 MUST 两两 distinct：
   - 不同 service DID（`issuer` 字段字符串不相等）；
   - 不同 controlling organization（`controlling_organization` 字段必须能从 witness issuer DID Document 的 `controller` / service ownership 链或 Realm policy 声明验证，不接受 witness 自报；且运营方不得与 audit actor 的 controlling organization 相同）；
   - 不同 `verification_method` 控制密钥（不能是同一私钥不同 `kid`）。
3. **frontier 一致性**：所有 witnesses entries 对应 receipt 的 `frontier.realm_frontier` 在 `audit_event_id` 上 MUST 因果一致；frontier 不一致时 receipts 不能聚合为 `federation_witness_attested`，每条只能各自以 `single_source` 形态处理。
4. **签发方授权**：每个 `witnesses[].issuer` MUST 都被 Realm policy 声明为合法 RYW witness（`cx.realm.policy_components` 下 `audit.ryw_witnesses[]`）。Policy 未列出的 issuer 即使签出有效 receipt 也不计入聚合。

`kind` 取值与 `witnesses[]` 不匹配（例如 `kind="federation_witness_attested"` 但 `witnesses.length == 1`，或 `kind="single_source"` 但 `witnesses.length >= 2`）MUST 直接 `audit_receipt_invalidated`。本规则不依赖任何 receipt 内部字段的"自报值"，只看 `witnesses[]` 列表与签发证据；单签发者跨多 receipt 持续声称 `federation_witness_attested` 是误用，接收方 MUST 把这种情况视为 `single_source`。

## 5. 审查透明公示

因为 `cx.audit.accessed` 是一条公开写入的协作事件，所有参与者的客户端都能通过 sync 实时同步到该事件。

- **用户端 UI**：客户端检测到自己发送的消息被附加了 `cx.audit.accessed` 后，应在界面上（如气泡旁边）显示明显的标识（例如一个带警告色的"合规审查"眼睛图标），并允许用户点击查看审查事由、时间与 `audit_assurance_class`。
- **不可抵赖性范围**：在 `cx.profile.attested_audit.e2ee.v1` 下，合规输出必须绑定到 `cx.audit.accessed` 的确权回执；在 `cx.profile.disclosed_audit.e2ee.v1` 下，成员可审计合规客户端是否按流程记录访问，但协议不能阻止恶意持钥实现绕过日志。

## 6. 保证类别与对外描述（governance hand-off）

`cx.profile.disclosed_audit.e2ee.v1` 是**流程性披露**，`cx.profile.attested_audit.e2ee.v1` 是**硬件强制审计**——两者不是同一保证的强弱级别，是不同 family 的保证。本规范的 normative 责任到 §2.1 join warning 与 §4 工作流为止：客户端 MUST 区分文案，receipt MUST 透出 `audit_assurance_class`，接收方 MUST 在两者不一致时 fail closed。

产品文档、UI 标签、营销材料、合规说明等"对外描述"是否准确反映保证类别，属于实现方/部署方的 governance、合规与品牌职责，不在本协议规范的 normative 范围内。审计员、监管方与采购方 SHOULD 直接核验 §2 / §2.1 / §4 / §4.1 的 normative 行为以及 attestation evidence 是否当前有效，而不是依赖措辞自查。
