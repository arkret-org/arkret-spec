# Service API Schema（统一 OpenAPI）

## 1. 目标

`service-api-schema.md` 是 Contrix **canonical operation** 的统一服务清单。  
HTTP/JSON 是参考绑定；同一操作必须可以无语义损失映射到其它 transport（gRPC、WebSocket、SSE、MQ、libp2p、IPC）。

本文件同时承担：

- operation id 稳定性定义
- 各服务角色最小能力边界
- OpenAPI 与 transport 映射的一致性锚点

请求/响应形状、错误、分页、幂等、同步语义由 `api-conventions.md`、`service-surface.md`、`client-sync.md`、`service-http-binding.md` 共同约束。

## 2. 统一约定

- 所有 canonical operation 均使用 `encoding.md` 的 canonical JSON 与签名输入规则。
- 关键行为不由路径决定，而由 operation id 与数据语义决定。
- 服务发现应返回至少：
  - `protocol_version`
  - `supported_profiles`
  - `supported_features`
  - `supported_reducer_profiles`
  - `supported_schema_profiles`

## 3. OpenAPI 参考快照（简化版）

```yaml
openapi: 3.1.0
info:
  title: Contrix Service API
  version: 0.2.0
  x-conformance-profile: cx.profile.conformance.v1
servers:
  - url: https://{host}/api/v1
    variables:
      host: { default: localhost }

components:
  parameters:
    SyncToken:
      name: next_batch
      in: query
      schema: { type: string }
    CXCursor:
      name: cursor
      in: query
      schema: { type: string }

paths:
  /server/describe:
    get:
      operationId: cx.describeService
      responses:
        '200': { description: service profile }

  /identity/resolve:
    post:
      operationId: cx.resolveIdentity
  /identity/document:
    get:
      operationId: cx.getIdentityDocument
  /identity/log:
    get:
      operationId: cx.getIdentityLog
  /identity/submit-did-op:
    post:
      operationId: cx.submitDidOp

  /repo/submit-commit:
    post:
      operationId: cx.submitCommit
  /repo/ops:
    post:
      operationId: cx.getOps
  /repo/sync:
    post:
      operationId: cx.syncRepo

  /relay/subscribe:
    get:
      operationId: cx.subscribeRelay

  /index/query:
    post:
      operationId: cx.indexQuery
  /index/sync:
    post:
      operationId: cx.indexSync

  /directory/search-spaces:
    post:
      operationId: cx.directorySearchSpaces
  /directory/resolve-space:
    post:
      operationId: cx.directoryResolveSpace
  /directory/search-organizations:
    post:
      operationId: cx.directorySearchOrganizations
  /directory/resolve-organization:
    post:
      operationId: cx.directoryResolveOrganization
  /directory/search-actors:
    post:
      operationId: cx.directorySearchActors
  /directory/resolve-handle:
    post:
      operationId: cx.directoryResolveHandle

  /blob/upload:
    post:
      operationId: cx.uploadBlob
  /blob/get:
    get:
      operationId: cx.getBlob

  /device_messages/{txn_id}:
    put:
      operationId: cx.putToDeviceMessage
  /keys/upload:
    post:
      operationId: cx.uploadKeys
  /keys/query:
    post:
      operationId: cx.queryKeys
  /keys/claim:
    post:
      operationId: cx.claimKeys

  /authz/check:
    post:
      operationId: cx.checkAuthorization
  /contrix/v1/check:
    post:
      operationId: cx.policyServerCheck

  /sync:
    post:
      operationId: cx.clientSync
```

## 4. Canonical 操作与 transport 映射

| Canonical Operation | HTTP 参考绑定 | 其他 transport 映射 |
| --- | --- | --- |
| `cx.resolveIdentity` | `POST /identity/resolve` | gRPC `ResolveIdentity` / MQ `identity.resolve` |
| `cx.submitDidOp` | `POST /identity/submit-did-op` | gRPC `SubmitDidOperation` / libp2p stream |
| `cx.submitCommit` / `cx.syncRepo` | `POST /repo/*` | gRPC `SubmitCommit` / 队列 `repo.commit` |
| `cx.clientSync` | `POST /sync` | WebSocket/SSE / `/sync?since...` |
| `cx.subscribeRelay` | `GET /relay/subscribe` | WebSocket firehose / pubsub |
| `cx.indexQuery` / `cx.indexSync` | `POST /index/*` | gRPC `IndexQuery` / SSE 查询流 |
| `cx.directorySearch*` | `POST /directory/*` | gRPC Discovery Service |
| `cx.putToDeviceMessage` | `PUT /device_messages/{txn_id}` | MQ device topic / 本地 IPC |
| `cx.checkAuthorization` | `POST /authz/check` | gRPC / policy 插件回调 |
| `cx.policyServerCheck` | `POST /contrix/v1/check` | policy 本地调用 |

## 5. 落地要求

- 任何节点都应能发布一份可下载的 OpenAPI 文档（建议路径 `/.well-known/contrix/openapi.yaml`），并在 service DID metadata 中声明版本和 hash。
- 实现必须保持 operation id 在演进中稳定；若请求字段名变更，必须保留兼容版本或通过 profile 明确协商。
- OpenAPI 只定义形态，不定义核心语义。核心语义仍由本协议对象模型、授权状态、签名、同步与加密规范给出。

