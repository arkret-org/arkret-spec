---
title: Sovereign Deployment and Controlled Collaboration
sidebar:
  label: Sovereign Deployment
---

## 1. 目标

高安全组织可以运行独立的 Contrix 网络，同时在必要时为外部人员或外部组织开启受控协作 Space。

本文定义：

- sovereign deployment 的边界
- isolated federation domain
- controlled collaboration Space
- 外部主体进入高安全网络的验证、授权、加密、审计和退出规则
- sovereign client 与 DID resolver policy

## 2. 部署模型

Sovereign deployment 是由单一组织或联盟控制的 Contrix 服务域。它通常包含：

- Organization DID / governance registry / witness
- Identity Registry
- Principal Server / Sync Service
- Directory
- Blob Store
- Policy Server
- Push Gateway
- TURN / SFU / Media Service
- Applet / Agent Runtime allowlist

这些服务 SHOULD 使用 service DID，并由 Organization DID 或联盟治理 DID 明确委派。

### 2.1 网络拓扑图

域内结构（简化视图）：

```mermaid
flowchart TB
    subgraph "Sovereign Main Domain"
        ORG["Organization DID /<br/>Governance"]
        TRUST["Identity / Witness<br/>Services"]
        CORE["Internal Sync Plane<br/>(Principal / Event / Policy)"]
        SUPPORT["Private Support Services<br/>(Directory / Blob / Media)"]
        INTCLIENT["Managed Internal<br/>Clients"]

        ORG --> TRUST
        ORG --> CORE
        ORG --> SUPPORT
        INTCLIENT --> CORE
    end

    subgraph "Controlled Collaboration Enclave"
        ESPACE["Controlled Collaboration<br/>Space"]
        ESVC["Enclave Service Plane<br/>(Principal / Directory / Blob / Policy)"]

        ESPACE --> ESVC
    end

    ORG -->|"creates / endorses"| ESPACE
    INTCLIENT -->|"approved membership"| ESPACE
    CORE -. "no default bridge" .- ESVC
    SUPPORT -. "not exposed" .- ESVC
```

为保持可读性，域内图将 `Directory` / `Blob` / `Media` / `Policy` 等次级组件折叠为 service plane；细项仍以上文服务清单与后续章节为准。

跨域协作路径：

```mermaid
flowchart TB
    subgraph "External Organization Domain"
        EXTORG["External Organization<br/>DID"]
        EXTCLIENT["External Managed<br/>Client"]
        EXTAPI["External Principal Server /<br/>Events API"]
        EXTSYNC["External Principal Server /<br/>Sync Service"]
    end

    subgraph "Controlled Collaboration Enclave"
        ESPACE["Controlled Collaboration<br/>Space"]
        EPOL["Enclave Policy<br/>Server"]
        ESYNC["Enclave Principal Server /<br/>Sync Service"]
    end

    EXTCLIENT -->|"invite + restricted join"| ESPACE
    EXTORG -->|"authority chain / VC"| EPOL
    EXTCLIENT --> EXTAPI
    EXTAPI -->|"signed Events"| ESYNC
    EXTSYNC -. "optional allowlisted federation" .-> ESYNC
    EPOL -->|"allow / deny / quarantine"| ESYNC
```

拓扑含义：

- 主网络保持 closed federation，不向外部主体暴露内部 Directory 或服务拓扑。
- Controlled Collaboration Enclave 是独立协作边界，只承载被批准的 Space。
- 外部主体通过 DID / VC / authority chain / invite / restricted join 进入 enclave Space。
- 外部组织可以保留自己的 Principal Server / Events API，但写入必须经过 enclave Principal Server / Sync Service、Policy Server 和本地授权验证。
- 主网络与 enclave 之间没有默认桥接；资料进出必须经过 export / import review。

## 2.2 Sovereign Client

高安全部署不一定要求从零开发专用客户端，但 MUST 使用受管控客户端 profile。普通公共网络客户端只有在被锁定配置、审计、签名发布和策略管理后才可进入 sovereign deployment。

Sovereign client MUST:

- pin organization trust anchors：Organization DID、governance DID、registry DID、witness DID、service DID allowlist。
- 使用组织配置的 DID resolver policy，不得默认查询公共 registry / public directory。
- 验证服务 DID 委派、证书、HTTP message signature 和 feature profile。
- 禁止用户手动添加未批准 Sync Service / Directory / Blob / Applet endpoint。
- 默认关闭公共 federation、公共搜索、外部 Applet 和外部 Agent handoff。
- 对每个 Space 显示 classification、E2EE、auditable E2EE、export、external member policy。
- 支持远程撤销 session、device、grant、Applet delegation 和 cached secret。
- 支持本地日志、审计导出和密钥擦除策略。

Sovereign client SHOULD:

- 使用硬件密钥、平台安全模块或智能卡。
- 支持离线/内网 resolver bundle。
- 支持 policy-signed configuration update。
- 对截屏、复制、批量导出、水印、外部分享实施本地 policy enforcement。

## 3. 默认安全姿态

高安全部署 SHOULD 默认：

- 禁止公共 federation。
- 禁止公共 directory listing。
- Space 默认 `discoverability=secret` 或 `invite_only`。
- Space 默认 `join_rule=invite` 或 `restricted`。
- Policy Server 默认 `closed` 或 `quarantine` fail mode。
- Sync Service / Directory 只接受 allowlist service DID。
- Blob、snapshot、backup、audit log 存储在组织控制基础设施内。
- 外部 Applet、Agent handoff、TSP/A2A/ACP transport 默认关闭，按 Space 明确开启。
- E2EE 默认开启；需要合规审查时使用 auditable E2EE，且必须向成员显示。

## 3.1 DID Policy

Sovereign 部署 MUST 在内部使用既有 DID 方法。组织与服务主体 SHOULD 使用私有或 allowlist 范围内的 `did:webvh` / `did:web`；仅当 policy 明确允许时，MAY 为外部协作方接受 `did:plc`。

部署 MUST 定义 DID resolver policy：

```json
{
  "kind": "cx.sovereign.did_policy",
  "trust_domain": "did:web:defense.example#contrix-domain",
  "default_principal_method": "did:webvh",
  "allowed_methods": ["did:webvh", "did:web", "did:plc", "did:key"],
  "trust_roots": [
    "did:web:registry.defense.example",
    "did:web:witness-1.defense.example",
    "did:web:witness-2.defense.example"
  ],
  "public_resolver_allowed": false,
  "method_policy": {
    "did:webvh": "allowlist",
    "did:web": "allowlist",
    "did:plc": "external_collaborator_only",
    "did:key": "ephemeral_only"
  }
}
```

规则：

- 除非 policy 明确允许该 method 与 trust root，否则客户端 MUST NOT 通过公共 resolver 端点解析内部主体。
- 内部 DID Document 与 method 历史 MUST 从受批准的 resolver / witness / watcher / 离线 bundle 获取。
- 仅当 policy 允许且权限链已验证时，MAY 为外部协作方接受公共 DID 方法。
- 涉及关联风险的外部协作 SHOULD 使用 pairwise DID。
- 指向公共 Sync Service / Directory 的 DID Document service endpoint 在未 allowlist 时 MUST 被忽略。

## 4. 受控协作 Space

组织 MAY 创建受控协作 Space，允许外部网络的人员或组织加入特定协作范围。

该 Space 是隔离边界，不应让外部主体直接进入组织主网络。

Controlled Collaboration Space SHOULD 使用：

```json
{
  "kind": "cx.space.create",
  "payload": {
    "object": {
      "id": "cx:space:019640ea-8000-7000-8000-000000000000",
      "schema": "cx.schema.space.v1",
      "security_class": "high_assurance",
      "title": "Controlled Collaboration",
      "created_by_principal": "did:web:defense.example",
      "owning_organizations": [
        "did:web:defense.example"
      ],
      "schema_refs": [
        "cx.schema.space.v1"
      ],
      "default_discoverability": "unlisted",
      "default_join_rule": "restricted",
      "history_visibility": "joined",
      "encryption_profile": "mls_rfc9420",
      "federation_policy": "closed",
      "anchor_profile": "single_did",
      "anchorer": {
        "type": "single_did",
        "did": "did:web:server.defense.example"
      },
      "max_anchor_staleness_ms": 86400000,
      "created_at": "2026-04-26T00:00:00Z"
    }
  }
}
```

Sovereign 部署默认采用 **single_did Anchor profile**：每个 Space 由组织自己的 Principal Server（service DID）作为 genesis anchorer，所有 Move 只有进入该 anchorer 签发的 Anchor frontier 后才 effective（参见 [`authz/event-auth-state-resolution.md`](../authz/event-auth-state-resolution.md)）。这与 sovereign 部署"组织拥有自己的服务器，且服务器是 Space 的真相源"的事实结构一致。组织间共享 Space（多个 `owning_organizations`）可以使用 `threshold` 或 `mixed` anchor profile；anchorer 变更是普通 Move，由旧 anchorer finalization，fallback recovery 由 Space create 固定。需要开放联邦协作时，create event 显式声明 `federation_policy="open"` 与 `anchor_profile="open_set"`。

推荐 policy：

- `discoverability=unlisted` 或 `invite_only`
- `join_rule=restricted` 或 `knock_restricted`
- `history_visibility=joined`
- `encryption_required=true`
- `external_federation=allowlist`
- `directory_visibility.public_directory=false`
- 默认禁用 reshare / export
- 默认禁用 applet / agent，需显式授权方可使用

## 5. 外部主体进入流程

外部人员或组织进入受控 Space MUST 经过受控流程：

1. 外部主体提供 DID、Organization DID、service DID 或 verifiable credential。
2. 主组织验证 DID control、handle binding、organization authority chain。
3. Policy Server 检查 allowlist、risk score、clearance claim、contract claim、device posture。
4. Space admin 或 delegated approval actor 发出 invite。
5. 外部主体接受 invite，并提交 `cx.member.state` join event。
6. 对 E2EE Space，管理员客户端或 key service 只向该主体授权设备发 MLS Welcome。
7. Directory 和客户端本地 projection 只暴露该 Space 允许的 stripped preview 和加入后历史。

外部主体 MUST NOT 获得：

- 主网络 directory 全量搜索能力
- 其他 Space 列表
- 组织成员列表
- 不相关 service topology
- 加入前历史密钥，除非 policy 明确允许

## 6. 外部组织协作

当外部组织加入时，建议使用组织级 trust chain：

```json
{
  "claim_type": "external_org_authorization",
  "issuer": "did:web:defense.example",
  "subject": "did:web:contractor.example",
  "scope": {
    "space_id": "cx:space:400d7400-0000-7000-8000-000000000000",
    "roles": ["contractor_reviewer"],
    "max_members": 20
  },
  "valid_until": "2026-07-26T00:00:00Z"
}
```

外部组织 MAY 运营自己的 Principal Server / Events API，但受控 Space SHOULD 要求：

- 外部 service DID 已通过审批
- federation 事务签名
- server ACL allowlist
- 逐事件签名验证
- 本地策略再次校验
- 每次跨域写入留存 audit record

## 7. Gateway / Enclave 模式

高安全组织 SHOULD NOT 将整个内部域桥接到外部网络。

推荐模式：

- 主网络保持 closed federation。
- 创建独立的 collaboration enclave。
- 外部主体只被邀请到 enclave Space。
- enclave Space 使用独立 Principal Server / Blob / Policy Server。
- 从主网络复制到 enclave 的资料必须经 redaction / export review / declassification policy。
- 从 enclave 回流主网络的资料必须经 import review / malware scan / policy approval。

## 8. Applet 与 Agent 控制

受控协作 Space SHOULD 默认：

- 禁用 Applet。
- 禁用 Agent protocol handoff。
- 禁用外部工具访问。
- 禁用媒体录制。

任何例外 MUST 通过 capability 与 policy 授权：

- `via_applet_id`
- `allowed_protocols`
- `allowed_data_classes`
- `human_approval_required`
- `audit_mode`
- `egress_policy`

## 9. 数据出域与导出

外部成员 MAY 只在被授予的范围内读取或写入。

导出控制 SHOULD 包括：

- 默认禁用批量导出
- 对导出包加水印或留存审计
- 附件与 snapshot 导出需审批
- 保留 audience / classification 标签
- 阻止公共目录索引
- 阻止跨服务的未授权再分发

若内容已加密，导出 MUST NOT 在预期接收者集合之外附带密钥。

## 10. 退出、撤销与事件响应

外部访问结束时：

- 撤销 invite / grant / delegation
- 把成员状态设为 `leave` 或 `ban`
- 从 MLS group 中移除外部设备
- 轮换 MLS epoch
- 撤销 Applet / Agent 会话
- 停止其在 directory 中的可见性
- 标记外部 service DID 为不再允许
- 按 retention policy 保留 audit 记录

如怀疑遭受入侵：

- 冻结 Space 或受影响对象集合
- 隔离跨域事件
- 轮换 service key
- 要求所有外部成员重新认证
- 基于源 Events API 运行 backfill 完整性审计

## 11. 一致性 Profile

`cx.profile.sovereign_deployment.v1` SHOULD 测试：

- 默认 closed federation
- service DID allowlist
- 受控协作 Space 的创建流程
- restricted 外部加入流程
- policy server 的 closed fail 模式
- 仅向受批准的外部设备发送 MLS welcome
- 目录对非成员的不可见性
- 跨域事件审计
- 外部 grant 撤销与 epoch 轮换
- enclave 的 import / export review 元数据
