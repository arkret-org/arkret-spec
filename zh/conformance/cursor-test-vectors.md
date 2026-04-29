# Cursor Test Vectors

本文件为 `cursor-encoding.md` 的中文结构对齐入口。  
可执行官方向量位于：

- [`artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)
- [`zh/conformance/fixtures/encoding-fixture.json`](./fixtures/encoding-fixture.json)

## 覆盖点

- cursor 版本字段与过期时间
- per-space frontier 编码
- device message 位置
- 过期 token 回退
- 非法额外字段拒绝

## 规范要求

- 实现 MUST 将 cursor 视为 opaque token。
- 服务端 MUST 校验 `v`、`t`、`s`、`x` 与每个 Space frontier 的结构。
- 非 HTTP binding 也 MUST 复用同一 cursor 语义，而不是把 offset 当作 canonical cursor。
