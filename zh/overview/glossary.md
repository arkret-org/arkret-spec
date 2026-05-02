# 术语表

## 1. 目标

本文集中定义 Contrix 规范中的核心术语。若其他文档使用同一术语，除非所在章节明确覆盖，否则应以本文定义为准。

本文中的英文术语保留为规范关键字；中文解释用于帮助阅读，不改变字段名、事件名或协议对象名。

## 2. 核心对象

| 术语 | 中文说明 | 定义 |
| --- | --- | --- |
| Contrix | 协议名称 | 面向去中心化协作对象、会话、任务、看板和 agent 协作的协议族。 |
| Principal | 主体 | 协议中的稳定身份主体，通常由 DID 表示。人、组织、agent、Applet 都可以是 principal。 |
| Organization | 组织 | 一类 principal，通常由组织 DID 表示，可签发成员资格/角色 credential、控制服务 DID、托管 Principal Server / Applet、发布 policy 或拥有 Space。Organization 不是 Space；它是治理与身份主体。 |
| Organization Governance | 组织治理 | Organization DID 的控制策略，包括治理密钥、阈值、多签、服务委派、恢复和所有权转移规则。 |
| Actor | 行为者 | 在 Space 中执行动作、产生 Event、拥有 profile 和 membership 的主体视图。Actor 通常映射到 principal，但可包含 ghost actor、bot actor 或 accountable actor。 |
| Space | 协作空间 | 复制、授权、schema、policy、membership 和 history visibility 的边界。它替代 Matrix room 作为 Contrix 的协作边界，但不是唯一数据模型。 |
| Official Space | 官方空间 | 由 Organization DID 直接创建，或被 active `cx.space.organization` state event 背书且 `scope.official=true` 的 Space。名称、域名、服务器托管方或成员列表不能单独证明官方性。 |
| Space Hierarchy | 空间层级 | Space 之间的 parent/child 组织关系，用于导航、发现和受控继承；不默认级联权限、成员、历史或加密。 |
| Discoverability | 可发现性 | 资源是否可被目录、搜索、父 Space、组织页、精确链接或邀请发现的策略；不等于 join rule、read permission 或 history visibility。 |
| Flow | 协作流 | Space 内统一的协作载体，用于同时承载正式表达、结构化字段和可选 discussion。`kind` 表达默认主模式，`semantic_kind` 表达业务语义。 |