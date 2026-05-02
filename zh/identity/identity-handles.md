# Handle 与 Claim 证明

## 1. 目标

Handle 是人类可读入口，不是权限主键。  
Contrix 使用 DID 作为稳定主体，用可验证 claim / attestation 表达 handle、组织成员、邮箱控制权和其他动态属性。

本文定义：

- handle 格式
- handle 到 DID 的解析
- 双向绑定验证
- pairwise DID 隐私模型
- 选择性披露 / 不可链接 presentation

## 2. Handle 原则

### 2.1 Handle 不是主键

协议层 MUST NOT 把以下内容作为 grant subject 或 Event actor：

- handle
- 邮箱
- 域名用户名
- 组织命名空间字符串，例如 `alice:google.com`

正确模型：

```text
grant subject = DID
authorization condition = verified claim / attestation
```

### 2.2 Handle 可以迁移

Handle MAY 变更、冻结、迁移或重新绑定。  
历史 Event 仍然保留原 DID 作为 actor，因此 handle 被回收不会改变历史责任主体。

### 2.3 Connection Identifier 与显示名分离

实现 MUST 区分以下标识层：

| 层 | 示例 | 用途 | 是否可作为协议主体 |
| --- | --- | --- | --- |
| Connection Identifier | `alice@example.com`、手机号、通讯录用户名、外部账号 ID | 发现联系人、请求 consent、发送邀请或建立初始关系 | 否 |
| Administrative Identifier | 组织账号、计费账号、客服账号、受管员工编号 | 组织本地管理、合规和账号恢复 | 否 |
| Handle | `alice.example.com`、`@alice:example.org` | 人类可读入口和公开/半公开别名 | 否 |
| Display Name | `Alice Zhang` | UI 展示 | 否 |
| Principal DID | `did:plc:...`、`did:web:...` | 签名、授权、事件责任主体 | 是 |

规则：

- Connection Identifier 只用于发现、consent、邀请或一次性绑定证明。它不得自动写入 DID Document、Space history、membership event、grant subject 或 MLS credential。
- Provider、Directory 或 Auth Server 证明某个 connection identifier 可达时，输出仍 MUST 归约为 DID 或 pending invite proof，并带有 purpose、audience、expiry 和 issuer proof。
- 同一个 principal 可以为不同 provider、组织或 Space 使用不同 connection identifier 和 pairwise DID。实现不得要求全局唯一 connection identifier。
- Connection identifier 与 DID 的绑定默认是关系私有状态。除非 holder 明确发布为 handle 或 VC claim，其他 Space 成员和 federation peer 不得获得该映射。
- Display name 是可变 metadata，不得被用于 ACL、grant、audit attribution 或 sender verification。

## 3. Handle 格式

初版推荐 DNS 风格 handle：

- `alice.example.com`
- `ops.example.com`
- `agent.release.example.com`

组织内部 MAY 使用命名空间 handle，但它仍然只是属性：

- `alice@google.com`
- `alice:google.com`
- `google.example/users/alice`
- `@alice:example.org`

这些字符串本身不证明组织成员资格。

Matrix-style identifier（如 `@alice:example.org`）MAY 作为用户可见 handle、登录名、联系人搜索项或 bridge alias。实现 MUST 保留其外部体系、localpart、domain / origin server 与大小写规范化规则；不得把它直接当作 DID、grant subject、Event actor 或未验证的组织成员证明。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json
{
  "alsoKnownAs": [
    "contrix://alice.example.com"
  ]
}
```

Pairwise DID、临时 DID、设备 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。

## 5. Handle 解析

推荐双通道解析：

1. DNS TXT：`_contrix.<handle>`
2. HTTPS well-known：`https://<handle>/.well-known/contrix-did`

DNS / HTTPS well-known 适用于 DNS 风格 handle。对于 `@alice:example.org`、`alice@google.com` 或其他非 DNS handle，解析 MAY 通过组织 Directory、Auth / Account Server、bridge registry 或受信 issuer claim 完成，但解析结果仍然 MUST 归约到 DID 和可验证绑定证据。

Well-known 示例：

```json
{
  "did": "did:plc:ewvi7nxzyoun6zhxrhs64oiz"
}
```

## 6. 双向验证

客户端解析 handle 得到 DID 后，MUST 继续解析 DID Document，并验证：

```text
did_document.alsoKnownAs contains contrix://<handle>
```

若双向验证失败，客户端 MUST NOT 把该 handle 当作可信绑定。

DNS TXT 只能作为发现通道。若使用 DNS TXT 直接声明 handle 绑定，客户端 MUST 满足以下至少一项才可显示为 verified：

- DNSSEC validation 成功，且 TXT 内容绑定 handle、DID、service DID、created_at、expires_at 和 signature / hash commitment。
- TXT 记录内的绑定声明由目标 DID、Organization DID 或受信 issuer 签名，客户端能通过 DID resolver / VC 验证该签名。
- HTTPS well-known 或 Directory / VC presentation 提供等价的签名绑定证据。

未启用 DNSSEC 且没有可验证签名的 DNS 结果只能作为 unverified discovery hint，MUST NOT 作为 grant subject、Organization membership、official Space 或 verified handle 的依据。

### 6.1 缓存与失效

Handle 解析结果是带时间边界的绑定，不是永久身份事实。

缓存规则：

- verified handle cache MUST 绑定 `handle`、`did`、解析通道、DID Document version / digest、alsoKnownAs proof、issuer proof（如有）、verified_at、expires_at 和 resolver policy。
- DNS / HTTPS 解析结果的 TTL MUST 不超过底层 DNS TTL、HTTPS response cache headers、签名绑定 `expires_at`、DID Document cache TTL 和本地 resolver policy 上限中的最小值。未提供 TTL 时，verified cache SHOULD 不超过 24 小时；高风险授权或组织背书 SHOULD 使用更短 TTL 或实时 status check。
- 当 DID Document 移除对应 `alsoKnownAs`、issuer claim 被 revoke / expired、well-known 绑定变更、DNSSEC validation 失败、handle 被解析到不同 DID、或 resolver policy 更新时，缓存 MUST 失效或降级为 unverified。
- Handle 转让不改变历史 Event 的 actor DID、签名责任或 audit attribution。历史 `@mention`、profile snapshot 或 message text MAY 保留当时显示字符串，但安全敏感 UI 必须能显示事件实际 DID，并在当前 handle 解析与历史 sender DID 不一致时标记为 handle changed / transferred。
- 授权、grant subject、membership、MLS credential 和 audit attribution MUST 使用 DID / verified claim，而不是缓存中的 handle 字符串。缓存失效不得自动撤销 DID 已签名的历史事件；只影响后续显示、发现和基于 handle claim 的条件化授权。

## 7. Verified Claim

Handle、组织成员、邮箱控制权和角色 SHOULD 通过 credential / attestation 表达。

授权判断 MUST 检查：

- issuer 是否被目标 Space / Policy 信任
- subject DID 是否匹配当前 actor
- claim 是否在有效期内
- claim 是否未撤销
- claim 内容是否满足 grant constraint
- presentation 是否绑定当前 verifier challenge / domain

## 8. 隐私保护型 Handle 证明

DID Document MUST NOT 被用作跨组织身份画像。公开或半公开 DID Document MUST NOT 直接列出以下信息，除非主体明确希望这些信息被关联：

- `alice@google.com`
- `alice@facebook.com`
- 第三方 profile URL
- 跨组织账号名
- 可关联多个 persona 的相同 service endpoint
- 可关联多个 persona 的相同 verification method

## 9. 标准依据

本设计与以下 W3C 文档一致：

- DID Core 隐私章节要求公开 DID Document 避免个人数据，并提醒 service endpoint、verification method 复用会带来关联风险。
- DID Core 建议使用 pairwise DID 降低跨关系关联。
- VC Data Model v2.0 定义 selective disclosure、unlinkable disclosure，并说明 zero-knowledge proof mechanism 可用于证明而不披露全部属性。
- VC DI BBS Cryptosuites 定义 `bbs-2023` base proof、derived proof、selective pointers 和 unlinkable proof 机制。

## 10. 推荐方案：Google 与 Facebook Handle

对 `alice@google.com` 和 `alice@facebook.com`：

1. Alice 为 Google 关系使用 `did:key:z6Mkgpairwise...`
2. Alice 为 Facebook 关系使用 `did:key:z6Mkfpairwise...`
3. 两个 DID MUST NOT 复用相同 verification method、专用 service endpoint、endpoint 用户名、`alsoKnownAs` 或公开 profile URL
4. Google 或受信 issuer 给 `did:key:z6Mkgpairwise...` 签发 `ContrixOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:key:z6Mkfpairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "contrix_org_membership_credential"],
  "issuer": "did:web:google.example",
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "org": "did:web:google.example",
    "member": true,
    "handle_verified": true
  },
  "validFrom": "2026-04-26T00:00:00Z",
  "validUntil": "2026-07-26T00:00:00Z",
  "credentialStatus": {
    "type": "privacy_preserving_status_list"
  }
}
```

如果确实需要显示 Google handle，presentation MAY 披露：

```json
{
  "credentialSubject": {
    "id": "did:key:z6Mkgpairwise...",
    "handle": "alice@google.com",
    "handle_verified": true
  }
}
```

该 disclosure MUST 绑定单一 verifier challenge / domain，并且 MUST NOT 自动披露其他组织 handle。

## 12. Presentation Request

Verifier MUST 使用最小披露请求，不得请求“所有 alias”或“所有账号”。

```json
{
  "type": "contrix_presentation_request",
  "audience": "did:web:google.example",
  "domain": "google.example",
  "challenge": "cx_chal_01J...",
  "accepted_issuers": [
    "did:web:google.example",
    "did:web:trusted-hr.example"
  ],
  "required_claims": [
    {
      "type": "contrix_org_membership_credential",
      "constraints": {
        "org": "did:web:google.example",
        "member": true
      },
      "disclosure": "abstract"
    }
  ],
  "forbidden_claims": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier"
  ]
}
```

Wallet MUST 展示将要披露的 claim。  
Wallet SHOULD 拒绝或警告请求无关 handle、global subject identifier、credential id 或不必要人口属性的 presentation request。

## 13. Proof Profile

Contrix SHOULD 支持：

- `sd_jwt_vc`：适合广泛 JOSE 互操作和 claim 级选择性披露
- `vc_di_bbs_2023`：适合需要不可链接 derived proof 的高隐私场景

需要不可链接 presentation 时，MUST 使用实际支持 unlinkability 的 proof mechanism。实现不得仅因为使用 VC 就宣称零知识或不可链接。

使用 `vc_di_bbs_2023` 时：

- issuer 创建 base proof 并只交给 holder
- holder 使用 selected claim pointers 创建 derived proof
- verifier 验证 derived proof、issuer key、challenge、domain 和 audience
- verifier MUST NOT 收到未披露 claim、base proof 或无关 credential identifier

## 14. Status 与撤销

Credential status check MUST 避免 verifier 驱动的关联追踪。

实现 SHOULD 使用：

- privacy-preserving status list
- cached status material
- verifier-independent revocation proof

实现 SHOULD NOT 要求 verifier 在每次 presentation 时把唯一 credential id、subject DID 或 handle 提交给中心化 status endpoint。

## 15. 授权语义

Capability policy MAY 依赖 verified claim，但 grant subject 仍然是 DID。

正确：

```text
grant subject = did:key:z6Mkgpairwise...
condition = has valid contrix_org_membership_credential where org = did:web:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. 定向披露策略与存储

TSP 可以帮助把 presentation 发送给正确的 VID，并通过 nested/routed message 降低元数据关联风险；但“对谁披露哪个 handle、披露条件是什么、披露记录存在哪里”属于 Contrix identity / wallet / private state 语义，MUST 明确定义。

完整端到端实现规则见 `progressive-disclosure.md`。本节保留核心身份语义和对象摘要。

### 16.1 组织如何确定

“特定组织”MUST 由可验证组织主体标识，而不是显示名、邮箱域名或普通字符串决定。

组织标识符 SHOULD 是：

- 组织 DID，例如 `did:web:google.example`
- 组织 service DID，例如 `did:web:google.example#hr`
- 受 trust registry / governance registry 认可的 VID
- Space policy 中列出的 trusted issuer DID

Verifier 声称自己代表某组织时，MUST 提供：

```json
{
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "authority_chain": [
    {
      "issuer": "did:web:google.example",
      "subject": "did:web:login.google.example",
      "claim_type": "org_service_authorization",
      "service": "contrix_verifier",
      "valid_until": "2026-07-26T00:00:00Z"
    }
  ],
  "challenge": "cx_chal_01J...",
  "domain": "google.example"
}
```

Wallet MUST verify：

1. `verifier_did` 可解析。
2. `represented_org` 与用户预期组织一致。
3. `authority_chain` 由 represented org 或受信 governance issuer 签发。
4. challenge / domain / audience 与本次 presentation request 匹配。
5. Space policy 或用户本地 disclosure policy 允许向该 verifier 披露对应 claim。

仅凭 `google.com` 域名、TLS 证书、邮箱后缀或 UI 文案，MUST NOT 视为组织身份已经确定。

### 16.2 披露策略对象

用户的 wallet 或 private account data MAY 保存 `cx.identity.disclosure_policy`：

```json
{
  "type": "cx.identity.disclosure_policy",
  "policy_id": "cx:policy:d1sc01j0000000000000000000",
  "holder_did": "did:web:holder.example.com",
  "audience": {
    "org_did": "did:web:google.example",
    "verifier_dids": ["did:web:login.google.example"],
    "tsp_vids": ["did:webs:google.example:verifier"]
  },
  "allowed_claims": [
    {
      "claim_type": "contrix_org_membership_credential",
      "issuer": "did:web:google.example",
      "subject_did": "did:key:z6Mkgpairwise...",
      "disclosure": "abstract",
      "fields": ["org", "member", "handle_verified"]
    },
    {
      "claim_type": "verified_handle",
      "issuer": "did:web:google.example",
      "subject_did": "did:key:z6Mkgpairwise...",
      "disclosure": "explicit",
      "fields": ["handle"],
      "value_constraints": {
        "handle": "alice@google.com"
      }
    }
  ],
  "forbidden_fields": [
    "other_handles",
    "external_accounts",
    "global_flow_identifier",
    "credential_id"
  ],
  "requires_user_consent": true,
  "expires_at": "2026-07-26T00:00:00Z"
}
```

该 policy 是 holder-private state，默认不得写入公共 Space。

### 16.3 存储位置

私密身份披露相关数据分层存储：

| 数据 | 推荐位置 | 可见性 |
| --- | --- | --- |
| 原始 credential / base proof | wallet 本地加密库或 holder private account data | 仅 holder 设备 |
| pairwise DID key material | wallet / device secret storage | 仅 holder 设备 |
| disclosure policy | holder private account data，端到端加密 | holder 自己的设备 |
| presentation request | 临时 inbox 或 encrypted private account data | holder 与 verifier 可见 |
| derived proof / presentation | 只发送给目标 verifier；可在本地加密留存副本 | holder 与 verifier |
| disclosure receipt | holder private account data，可选写入审计摘要 | 默认仅 holder |
| revocation/status material cache | holder private account data 或 wallet cache | holder 自己的设备 |

Holder private account data MUST 使用设备或 recovery key 加密。服务端、Sync Service 或受托服务不应能读取原始 credential、base proof、完整 disclosure policy 或跨组织 handle 列表。

### 16.4 披露记录

Wallet SHOULD 在 holder private account data 中保存 disclosure receipt：

```json
{
  "type": "cx.identity.disclosure_receipt",
  "receipt_id": "cx:receipt:d1sc01j0000000000000000000",
  "holder_did": "did:key:z6Mkgpairwise...",
  "verifier_did": "did:web:login.google.example",
  "represented_org": "did:web:google.example",
  "presentation_hash": "sha256:...",
  "disclosed_fields": [
    "credentialSubject.org",
    "credentialSubject.member",
    "credentialSubject.handle_verified"
  ],
  "withheld_fields": [
    "credentialSubject.handle",
    "other_handles",
    "external_accounts"
  ],
  "proof_profile": "vc_di_bbs_2023",
  "tsp_relationship_id": "tsp:rel:...",
  "created_at": "2026-04-26T00:00:00Z"
}
```

Receipt MUST NOT contain undisclosed handle values or other organization identifiers.

### 16.5 TSP 在定向披露中的作用

若 verifier 支持 TSP，wallet MAY 使用 TSP：

- 用 verifier VID 建立 directional TSP relationship。
- 在 outer TSP relationship 中发送 presentation request / response。
- 使用 nested TSP message 隐藏 holder 的内层 pairwise DID。
- 使用 routed mode 降低网络层对 holder/verifier 关系的关联。

但 TSP 只保护传输和 VID 关系：

- TSP 不决定哪些 claim 可以披露。
- TSP 不验证组织成员资格语义。
- TSP 不替代 VC/BBS/SD-JWT proof。
- TSP 不替代 holder 本地 disclosure policy。

### 16.6 端到端流程

1. Verifier 发送 presentation request，声明 `verifier_did`、`represented_org`、challenge、domain 和 required claims。
2. Wallet 解析 verifier DID / VID，验证 authority chain。
3. Wallet 查找本地 disclosure policy，匹配 represented org。
4. Wallet 选择对应 pairwise DID 和 credential。
5. Wallet 生成 SD-JWT VC disclosure 或 BBS derived proof。
6. 如启用 TSP，Wallet 通过 direct/routed/nested TSP message 发送 presentation。
7. Verifier 验证 proof、issuer、challenge、domain、audience 和 status。
8. Wallet 写入私有 disclosure receipt。

## 17. v1 互操作要求

- Handle ABNF 必须限制为可规范化、大小写明确、禁止控制字符和混淆分隔符的字符串；DNS 风格 handle 使用 IDNA 处理后再验证，显示层必须防同形混淆。
- DNS TXT record 格式 MUST 绑定 handle、DID、service DID、created_at、expires_at 和 signature / hash commitment；过期或不匹配时不得显示 verified。
- Well-known response schema MUST 返回 subject DID、handle、issuer、proof、validity、service binding 和 optional challenge；客户端必须做双向验证。
- Credential schema、presentation request、disclosure policy 和 disclosure receipt 必须绑定 holder DID、verifier DID、audience、challenge、domain、disclosed fields、withheld fields 和 proof profile。
- Status list profile MUST 支持凭证撤销和暂停。授权依赖的 credential 无法确认状态时 MUST fail closed。
- BBS / SD-JWT VC conformance vectors MUST 覆盖选择性披露、challenge/domain 绑定、错误 issuer、过期凭证、撤销凭证和 pairwise DID unlinkability。
