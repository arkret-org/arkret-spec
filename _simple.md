# 协议行文优化任务清单

生成日期：2026-06-01

目标：先改善读者理解路径，再收紧容易产生二义性的术语与对象边界；本轮原则上不改 wire schema / registry。

## 任务

- [x] 1. 在入口文档补一张“5 分钟读法”心智模型，先说明 Realm / Space / Flow / Message / Relation / View 各自解决什么问题。
- [x] 2. 补充同类产品概念映射：聊天 / WeChat 群聊、Matrix Room、Trello Kanban、Jira issue/workflow/link/watchers 在 Contrix 中分别落到哪些对象。
- [x] 3. 澄清 `discussion` track、watch、push rule、read receipt 的职责边界，避免把 track 误读成独立 ACL / E2EE 边界。
- [x] 4. 去掉或降级术语表里的重复定义，保留单一 canonical 定义，并把“别名 / 禁用词 / 局部术语”集中说明。
- [x] 5. 明确 `state` / `stage` / `status` / workflow status 的分工，避免把 Jira-style workflow status 与对象生命周期混用。
- [x] 6. 识别 Trello/Jira 常见但 v1 core 不强行固化的能力（checklist、subtask、automation、saved filter），给出 profile / Morph / Relation / account data 的落点。
- [x] 7. 修正文档中容易误导的措辞，例如“discussion 承载成员 / 历史可见性”这类会暗示 track 拥有独立边界的句子。
- [x] 8. 运行 `lint_spec.py`、`lint_artifacts.py` 或 artifact pipeline，确认 Markdown 与构件引用没有被 prose 修改破坏。

## 行业参照点

- Matrix：Room 把 timeline、state、members、receipts、threads 等放进 room 语义；Contrix 拆成 Realm 边界 + Flow/Message 协作对象 + View 投影。
- Trello：Board / List / Card / Custom Fields / Checklist / Automation 映射到 Space(kind=board/list)、Flow、fields / Morph、Relation、profile automation。
- Jira：Issue / Workflow status / Transition / Issue links / Watchers 映射到 Flow、stage + workflow profile、Relation、watch cell。
- WeChat / 通用聊天：联系人、群聊、订阅/服务通知、隐私同意分别映射到 Principal/Handle、Realm + discussion Flow、Notification/Push、Consent / Account Data。
