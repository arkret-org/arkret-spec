# Scalability Constraints

## 1. 目标

Contrix v1 的一致性不仅要求语义正确，也要求实现不会被合法但过大的输入拖垮。本文定义 v1 默认规模上限。实现 MAY 在私有部署中使用更低或更高限制，但对外声明互操作 profile 时 MUST：

- 在 `server/describe.limits` 暴露实际限制。
- 对超过限制的输入返回标准错误、`rejected[]` 或 `quarantine[]`，不得无界处理。
- 不得因为本地上限不同而接受会导致其他 v1 节点无法验证的 wire object。

本文的数值是 v1 wire interoperability bounds，不是产品体验目标。

## 2. 通用 Wire 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 canonical Event / Operation envelope | 1 MiB | 超过时 MUST reject 为 `payload_too_large` 或 `schema_violation`。正文、附件和大对象必须使用 Blob。 |
| 单个 Repo commit 引用的 operation 数 | 1,000 | 超过时 MUST 拆分 commit。 |
| 单个 federation transaction 的 operation 数 | 500 | 超过时 MUST 拆分 transaction；接收方 MAY 返回 `rate_limited` 或 `payload_too_large`。 |
| 单次 sync / backfill / index page 返回项 | 1,000 | 服务端 MUST enforce；客户端不得假设更大 page 可用。 |
| 单个 operation 的 `prev_refs` 数量 | 128 | 超过时 MUST reject 或要求提交 snapshot / checkpoint 引用。 |
| 单个 operation 的 `auth_refs` 数量 | 64 | 超过时 MUST reject；auth refs 必须是最小授权状态集合。 |
| 单个 Relation / View / Morph `fields` canonical size | 256 KiB | 更大内容必须放入 Blob 或加密 payload。 |
| 关系展开深度 | 32 | Index / graph query MUST enforce，跨 Space 引用必须按 Lazy Link 截断。 |

## 3. 授权与 Capability 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| delegation chain 深度 | 4 | 超过时 MUST deny；profile MAY 声明更低上限。 |
| 单次授权判定展开 grant 数 | 1,024 | 超过时 MUST fail closed、使用已验证 snapshot，或返回 `soft_fail` / `temporarily_unavailable`。 |
| 单个 grant 的 constraint 数 | 64 | 超过时 MUST reject。 |
| 单个 resource selector AST 深度 | 16 | 超过时 MUST reject。 |
| 高频路径 authz snapshot 最大重建延迟 | 5 秒 | `chat_only_client`、`kanban_only_client`、`full_client`、`principal_server` 和 `index_node` 相关服务 MUST 满足。 |

当 grant / revoke / claim status / policy component / membership frontier 变化时，受影响的 capability snapshot MUST 立即标记 stale。stale snapshot 不得继续用于新的写入 allow 决策。

## 4. State Resolution 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 state key 的 conflict candidate 数 | 256 | 超过时 MUST 使用最近可验证 snapshot 作为 base，并把超阈值候选进入 review / quarantine。 |
| `auth_chain` 闭包深度 | 64 | 超过时 MUST soft-fail 依赖事件或 fail closed。 |
| `auth_difference` 事件数 | 4,096 | 超过时 MUST fallback to verified snapshot-assisted resolution。 |
| 单次 resolution 内存预算 | 实现声明 | 服务 MUST 在 `server/describe.limits` 暴露，超出时返回可恢复错误而不是 OOM。 |

State resolution fallback 不得选择本地接收顺序或数据库 ID。fallback snapshot 必须有签名、frontier、state hash 和 chunk digest。

## 5. Board / Relation / View 上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单个 Board active List 数 | 500 | 超过时 Board projection MUST paginate 或 require filtered View。 |
| 单个 List active Card 数 | 10,000 | Projection MUST paginate；drag / reorder 仍按 rank + deterministic tie-break。 |
| 单个对象 active Relation 数 | 10,000 | Index query MUST paginate，不能要求客户端一次性拉全。 |
| 单个 View projection page | 1,000 items | View cursor MUST 绑定 authorization context 和 frontier。 |
| rank 长度 | 128 chars | 超过时 MUST reject，见 `encoding.md`。 |

Board position edge 的 canonical key 是 `(board_id, card_id)`。同一 key 下多个 active edge 只允许 reducer 选择一个 winner，并记录 losers；Index MAY 暴露 loser conflict records，但不得把同一 Card 渲染成多个主位置。

## 6. E2EE 与设备上限

| 项 | v1 默认上限 | 规则 |
| --- | ---: | --- |
| 单 principal active device 数 | 100 | 超过时 Device / Key Server MAY require admin approval or device cleanup。 |
| 单 MLS commit 绑定的 `membership_frontier` refs | 128 | 超过时 MUST 使用签名 state root / snapshot reference。 |
| KeyPackage 有效期 | 30 days | 更长有效期必须由 profile 明确声明。 |
| 单次 to-device page | 1,000 | 服务端 MUST enforce。 |

## 7. 错误语义

超过规模上限时：

- 确定不可接受的结构输入 MUST reject。
- 缺依赖或可通过 backfill / snapshot 恢复的输入 SHOULD `soft_fail` 或返回 `dependency_missing`。
- 可能是滥用、fork 或异常来源的输入 MAY 进入 `quarantine`。
- 所有可恢复错误 SHOULD 带 `retry_after_ms`、`next_retry_at`、backfill 起点或 snapshot frontier。

实现不得把超限输入静默截断后当作 accepted state。
