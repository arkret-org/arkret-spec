# Handle 与 Claim 证明 Draft

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

## 3. Handle 格式

初版推荐 DNS 风格 handle：

- `alice.example.com`
- `ops.example.com`
- `agent.release.example.com`

组织内部 MAY 使用命名空间 handle，但它仍然只是属性：

- `alice@google.com`
- `alice:google.com`
- `google.example/users/alice`

这些字符串本身不证明组织成员资格。

## 4. Handle 绑定

公开 persona DID MAY 使用：

```json
{
  "also_known_as": [
    "contrix://alice.example.com"
  ]
}
```

Pairwise DID、临时 DID、设备 DID、agent 执行 DID 和隐私敏感关系 DID SHOULD NOT 强制绑定公开 handle。

## 5. Handle 解析

推荐双通道解析：

1. DNS TXT：`_contrix.<handle>`
2. HTTPS well-known：`https://<handle>/.well-known/contrix-did`

Well-known 示例：

```json
{
  "did": "did:uuid:01970e58-9d21-8123-8b7c-0d8f7a31c992"
}
```

## 6. 双向验证

客户端解析 handle 得到 DID 后，MUST 继续解析 DID Document，并验证：

```text
did_document.also_known_as contains contrix://<handle>
```

若双向验证失败，客户端 MUST NOT 把该 handle 当作可信绑定。

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

1. Alice 为 Google 关系使用 `did:uuid:g_pairwise...`
2. Alice 为 Facebook 关系使用 `did:uuid:f_pairwise...`
3. 两个 DID MUST NOT 复用相同 verification method、专用 service endpoint、endpoint 用户名、`also_known_as` 或公开 profile URL
4. Google 或受信 issuer 给 `did:uuid:g_pairwise...` 签发 `ContrixOrgMembershipCredential`
5. Facebook 或受信 issuer 给 `did:uuid:f_pairwise...` 签发独立 credential
6. 面向 Google verifier 时，wallet 只生成 Google 相关 presentation
7. Google verifier MUST NOT 要求披露 Facebook credential、Facebook DID 或跨域 subject identifier

## 11. Credential 示例

如果 verifier 只需要知道“该主体拥有 Google 组织内有效账号”，presentation SHOULD 披露抽象 claim：

```json
{
  "type": ["verifiable_credential", "contrix_org_membership_credential"],
  "issuer": "did:web:google.example",
  "credential_subject": {
    "id": "did:uuid:g_pairwise...",
    "org": "did:web:google.example",
    "member": true,
    "handle_verified": true
  },
  "valid_from": "2026-04-26T00:00:00Z",
  "valid_until": "2026-07-26T00:00:00Z",
  "credential_status": {
    "type": "privacy_preserving_status_list"
  }
}
```

如果确实需要显示 Google handle，presentation MAY 披露：

```json
{
  "credential_subject": {
    "id": "did:uuid:g_pairwise...",
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
    "global_subject_identifier"
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
grant subject = did:uuid:g_pairwise...
condition = has valid contrix_org_membership_credential where org = did:web:google.example
```

错误：

```text
grant subject = alice@google.com
```

如果 holder 后续为另一个组织出示不同 pairwise DID，除非 holder 显式提供 linking proof，否则 verifier MUST 将其视为独立隐私上下文。

## 16. 待细化

- Handle ABNF
- DNS TXT record 格式
- well-known response schema
- credential schema
- presentation request schema
- status list profile
- BBS / SD-JWT VC conformance vectors
