# Contrix New Tasks

## 当前轮任务

- [x] 增加 `design-questions.md`  
  先把协议要回答的问题列出来，再统一收敛决策。
- [x] 重写 `README.md`  
  把规范地图扩展为“问题清单 + 架构 + 对象 + 会话 + 同步 + 权限 + 视图 + memory”。
- [x] 增加 `conversation-model.md`  
  明确 board/chat/topic/mention/edit/recall/reaction 的交互层模型。
- [x] 重写 `object-model.md`  
  把 `channel/topic/message` 纳入一等对象模型。
- [x] 重写 `operations-sync.md`  
  明确 board/chat/topic 的同步 profile、redaction 语义和冲突收敛。
- [x] 重写 `capabilities.md`  
  把消息、话题、频道、撤回、moderation 动作纳入 capability 模型。
- [x] 重写 `views.md`  
  使协议能自然投影为 kanban/chat/forum/thread/inbox 等界面。
- [x] 增加 `service-surface.md`  
  定义最小 repo / relay / index / blob / authz 服务面与 bootstrap 流程。
- [x] 补 `schema / policy / invite / read_marker / notification`  
  把之前只被引用但未正式定义的对象写回协议。
- [x] 补同步与权限细则  
  明确幂等提交、授权时序收敛、密文转发与 invite/read-state 权限。

## 当前轮验收标准

- [x] 协议问题清单被明确列出
- [x] 看板数据模型被明确为 `board + collection + item + view`
- [x] 聊天/话题模型被明确为 `channel + topic + message`
- [x] `@mention` 被明确为结构化 DID/object ref
- [x] 撤回被明确为 redaction/tombstone，而不是隐式物理删除
- [x] board/chat/topic 的同步与冲突规则被写回规范
- [x] 最小服务接口与 workspace bootstrap 被写回规范
- [x] `schema/policy/invite/read_marker/notification` 被正式定义
- [x] 幂等提交与授权时序规则被写回规范

## 下一轮 Backlog

- [ ] 定义 query JSON schema 的正式语法
- [ ] 定义 grant constraint schema
- [ ] 定义 cursor / HLC / rank / commit hash 编码
- [ ] 定义 snapshot manifest 与 chunk schema
- [ ] 定义各服务接口的正式 request/response schema
- [ ] 定义 snapshot signature / chunk digest / encrypted envelope schema
- [ ] 定义 read marker / inbox / notification 的正式 schema 与查询面
