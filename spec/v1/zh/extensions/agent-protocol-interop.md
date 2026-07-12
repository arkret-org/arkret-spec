---
title: Agent Protocol Interop（Reserved）
status: deprecated
normative: true
stability: v1
updated: 2026-07-11
sidebar:
  label: Agent Protocol Interop（Reserved）
---

# Agent Protocol Interop（Reserved）

本扩展面已从 Arkret v1 协议退出。以下名字空间保留但未激活，发送方 **MUST NOT**
在 wire 上产生，接收方 **MUST** 按未知或未激活协议项 fail closed：

- Event kind：`ak.agent.endpoint`、`ak.agent.interop_session.start`、
  `ak.agent.interop_session.status`、`ak.agent.interop_session.result`；
- capability action：`ak.agent.protocol.discover`、
  `ak.agent.interop_session.start`、`ak.agent.interop_session.cancel`、
  `ak.agent.interop_session.stream_status`、`ak.agent.interop_session.attach_artifact`、
  `ak.agent.interop_session.read_transcript`；
- typed ID kind：`ak:agent_interop_session:<uuid>`；
- former agent metadata schema ID `ak.schema.agent&#46;v1`（保留但不再登记 active schema）；
- service operation：`ak.self.agent.protocol.query.discover`。

本文中的规范关键字按
[`normative-language.md`](../conformance/normative-language.md) 解释。

## 退出理由

该面描述的是 agent runtime 向自身部署汇报的外部 A2A / ACP / MCP endpoint 与会话
metadata，不是 Arkret 问责链成立的前提。Agent 写入的问责由 controller 授权的 key、
事件签名、`executed_by` / `authorization_ref` / reducer-stamped `actor_kind` 署名与
accountability grant 闭环承担（见 [`../models/event-and-patch.md`](../models/event-and-patch.md)）。
Runtime 对端配置属于 runtime 本地配置；若需向部署汇报，使用 actor-private Account Data
或部署本地 API，不新增 Arkret 协议对象。

`ak.applet.interop_session.*` 是 applet bridge 的独立机制，不受本次退出影响。

## 重新立项条件

只有当跨部署 agent 直连、委托可见性或入站参与门成为明确产品目标，并且能给出完整的
身份 epoch pinning、capability 与 counterparty 绑定、状态机、隐私边界和 conformance
vectors 时，才可通过新的协议评审重新激活这些保留名字空间。重新激活不得仅恢复旧文本。
