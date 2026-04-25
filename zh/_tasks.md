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

## 当前轮验收标准

- [x] 协议问题清单被明确列出
- [x] 看板数据模型被明确为 `board + collection + item + view`
- [x] 聊天/话题模型被明确为 `channel + topic + message`
- [x] `@mention` 被明确为结构化 DID/object ref
- [x] 撤回被明确为 redaction/tombstone，而不是隐式物理删除
- [x] board/chat/topic 的同步与冲突规则被写回规范

## 下一轮 Backlog

- [ ] 定义 repo / relay / index / blob 的正式 HTTP 或 XRPC 接口
- [ ] 定义 query JSON schema 的正式语法
- [ ] 定义 grant constraint schema
- [ ] 定义 cursor / HLC / rank / commit hash 编码
- [ ] 定义 snapshot manifest 与 chunk schema
- [ ] 定义 read marker / inbox / notification 的正式 schema
