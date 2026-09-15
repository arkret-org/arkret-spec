---
title: CBS Profiles (Retired)
status: deprecated
normative: true
stability: v1
updated: 2026-09-16
see_also:
  - ../sync/authority-commit-log.md
  - event-auth-state-resolution.md
  - ../conformance/normative-language.md
---

> CBS、Seal、Control Move双平面、proof bundle、closure与治理结果证明已从 Arkret v1 退役。本文件只保留稳定链接锚点，任何实现不得据此接受旧 wire object、operation或兼容路径。现行合同见 [authority-commit-log.md](../sync/authority-commit-log.md)。

## 1. 安全域与配置

现行 v1 每个 Realm有一个 current governance Station，并分别维护 Realm、每个 Circle、每个 Sidecar的独立 authority stream。

## 2. 提案、执行和确认

不再存在通用 proposal/ack/defer。一个 Event请求只得到 committed、duplicate、rejected或retryable unavailable。

## 3. 单写者耐久确认

`RealmCommit` 是唯一共享 finality；同一 stream position双签是 authority equivocation。

## 4. 授权轮换与顺序迁移

治理 Station更换使用 old→new planned handoff；无已完成handoff时不能自动选主。

## 5. 授权关闭与有限期

授权在实际 commit位置按 current typed state求值，不再冻结 CBS basis。

### 5.1 精确依赖坐标

跨对象取证使用 `{event_id, commit_id, stream_ref, stream_position}`。

### 5.2 来源与关闭边界

Commit signature与逐 stream predecessor提供完整性；不再有 closure proof。

### 5.3 历史集合与有限期

历史可见性由 snapshot history floor、join position、retention与MLS epoch边界决定。

### 5.4 普通数据收录与基准关闭

普通与治理 Event均走同一 authority commit路径。

## 6. 跨 Realm 原子性

v1不提供跨 stream或跨 Realm原子提交；使用 exact committed refs和幂等saga。

## 7. 证明消费

消费 Station验证 authority chain、RealmCommit和producer proof；客户端消费 own Station的typed current result。

## 8. 单次 Agent 批准的发布

Agent批准绑定exact Event ID，随后仍由current authority在commit位置求值。

## 9. 治理结果证明（normative）

旧治理结果证明已删除；本标题只保留链接兼容。

### 9.1 责任与唯一载体

唯一载体是 `RealmCommit` 或 authority-signed typed snapshot/current result。

### 9.2 签名与配置认证

验证 genesis、handoff chain、current assertion和Commit signature。

### 9.3 封闭查询与确定性结果

使用 typed selector/result；没有caller自选Cell key。

### 9.4 披露、传输与失败

只披露caller获准stream；拒绝不返回隐藏scope证据。

### 9.5 业务消费与保留

业务状态按Commit顺序执行typed reducer并保留来源committed ref。
