# HLC Test Vectors

本文件为 `hlc-specification.md` 的中文结构对齐入口。  
可执行官方向量位于：

- [`artifacts/fixtures/encoding-fixture.json`](../../artifacts/fixtures/encoding-fixture.json)
- [`zh/conformance/fixtures/encoding-fixture.json`](./fixtures/encoding-fixture.json)

## 覆盖点

- 文本编码格式 `<unix_ms_hex>-<logical_hex>-<node_id_hash>`
- 同毫秒下 logical counter 增长
- 字典序与时间/逻辑序一致
- 本地时钟回拨下的单调性
- tie-break 依赖稳定 node id hash

## 规范要求

- 实现 MUST 保证 HLC 单调前进。
- reducer、timeline 和 sync frontier 的比较 MUST 使用同一 HLC 比较规则。
- 仅靠 `created_at` MUST NOT 替代 HLC 做因果排序。
- 5 分钟只作为 hard future-skew 上限；高风险 state event MUST 覆盖更小 expected drift / observed drift 超限时的 soft-fail 或 quarantine 向量。
