# Contrix v1 规范与一致性文档索引

## 概述

本目录包含 Contrix v1 协议的完整规范文档、一致性测试向量和实现指南。

## 文档结构

```
conformance/
├── schemas/                    # JSON Schema 定义
│   ├── cursor-schema.json     # Cursor 结构验证
│   ├── event-schema.json      # Event 信封验证
│   ├── grant-schema.json      # Capability Grant 验证
│   └── encrypted-envelope-schema.json  # 加密信封验证
│
├── 新增技术规范
│   ├── cursor-encoding.md     # Cursor 编码规范
│   ├── hlc-specification.md   # HLC 格式规范
│   ├── hlc-test-vectors.md    # HLC 测试向量
│   └── cursor-test-vectors.md # Cursor 测试向量
│
├── 实现指南
│   └── reference-implementation-guide.md  # 参考实现指南
│
└── 已有文档
    ├── encoding.md                    # 编码规范
    ├── encoding-conformance-vectors.md # 编码测试向量
    ├── snapshot-schema.md             # 快照 Schema
    ├── state-resolution-conformance-vectors.md  # 状态解析测试
    ├── redaction-conformance-vectors.md        # 编辑测试向量
    ├── conformance-profiles.md        # 一致性配置
    ├── conformance-suite.md           # 测试套件
    └── schema-registry.md             # Schema 注册表
```

## 规范文档

### 核心规范

| 文档 | 描述 | 状态 |
|------|------|------|
| cursor-encoding.md | Cursor 编码格式、验证规则、安全考虑 | ✅ 完成 |
| hlc-specification.md | HLC 文本格式、比较算法、时钟处理 | ✅ 完成 |
| encoding.md | Canonical JSON 编码规范 | 已存在 |
| snapshot-schema.md | 快照结构和验证规范 | 已存在 |

### 授权规范

| 文档 | 描述 | 状态 |
|------|------|------|
| resource-selector-grammar.md | 资源选择器 EBNF 语法、匹配算法 | ✅ 完成 |
| constraint-schema.md | 约束类型定义、评估顺序 | ✅ 完成 |
| grant-constraint-schema.md | Grant 约束规范（原已存在） | 已存在 |

### 加密规范

| 文档 | 描述 | 状态 |
|------|------|------|
| encrypted-envelope-schema.md | 加密信封结构、AAD 处理、MLS 集成 | ✅ 完成 |

## 测试向量

### 新增测试向量

| 文档 | 覆盖范围 | 测试数量 |
|------|----------|----------|
| hlc-test-vectors.md | HLC 格式验证、比较、生成 | 30+ |
| cursor-test-vectors.md | Cursor 编码/解码、验证、过期 | 25+ |

### 已有测试向量

| 文档 | 覆盖范围 |
|------|----------|
| encoding-conformance-vectors.md | Canonical JSON 编码 |
| state-resolution-conformance-vectors.md | 状态解析和冲突解决 |
| redaction-conformance-vectors.md | 消息编辑和撤回 |
| capability-conformance-vectors.md | 授权匹配 |

## JSON Schema 文件

所有 Schema 文件使用 JSON Schema Draft 7 格式：

| Schema | 用途 | 验证内容 |
|--------|------|----------|
| cursor-schema.json | Cursor 验证 | 结构、字段类型、格式约束 |
| event-schema.json | Event 信封验证 | 签名、引用、内容格式 |
| grant-schema.json | Grant 验证 | 授权、约束、证明 |
| encrypted-envelope-schema.json | 加密信封验证 | 加密结构、AAD、digest |

## 实现指南

| 文档 | 目标读者 | 内容 |
|------|----------|------|
| reference-implementation-guide.md | 实现者 | 架构建议、代码组织、关键实现 |

## 一致性要求

### 必须满足的要求

声明支持 Contrix v1 的实现必须：

1. **核心协议**
   - ✅ 支持所有 v1 事件类型
   - ✅ 实现正确的 HLC 生成和比较
   - ✅ 实现正确的 cursor 编码
   - ✅ 支持所有 v1 约束类型

2. **同步协议**
   - ✅ 支持增量同步
   - ✅ 支持选择性同步
   - ✅ 实现正确的状态收敛
   - ✅ 支持回填机制

3. **授权模型**
   - ✅ 实现基于 capability 的授权
   - ✅ 支持所有 v1 约束类型
   - ✅ 实现正确的评估顺序
   - ✅ 支持 delegation 限制

4. **加密**（可选）
   - 支持 MLS (RFC 9420)
   - 正确实现加密信封
   - 支持 E2EE 场景

5. **联邦**（可选）
   - 支持服务间认证
   - 实现重放防护
   - 支持快照辅助引导

### 测试要求

实现必须通过以下测试：

1. **编码测试**
   - Canonical JSON 编码
   - HLC 生成和比较
   - Cursor 编码和解码

2. **状态解析测试**
   - 冲突解决
   - 状态收敛
   - 因果关系处理

3. **授权测试**
   - Capability 匹配
   - 约束评估
   - Delegation 追踪

4. **加密测试**（如支持）
   - 信封加密和解密
   - AAD 验证
   - MLS 集成

## 使用指南

### 对于实现者

1. 从 `reference-implementation-guide.md` 开始
2. 查阅相关规范文档了解详细要求
3. 使用 JSON Schema 文件验证数据结构
4. 运行测试向量验证实现正确性

### 对于协议研究者

1. 阅读核心规范文档了解协议设计
2. 查看测试向量理解边界情况
3. 参考 JSON Schema 了解数据结构

### 对于测试工具开发者

1. 使用 JSON Schema 文件自动验证
2. 实现测试向量自动化测试
3. 参考一致性配置文件

## 版本历史

### v1.0 (2026-04-28)

初始完整规范版本，包含：
- 所有核心技术规范
- 完整的 JSON Schema 定义
- 全面的测试向量
- 参考实现指南

## 贡献指南

### 提交新规范

1. 遵循现有文档格式
2. 提供完整的 JSON Schema
3. 包含测试向量
4. 更新本索引文件

### 提交测试向量

1. 使用标准格式（参考现有测试向量）
2. 包含预期结果
3. 覆盖边界情况
4. 提供验证工具（如适用）

## 相关资源

### 协议文档

- [对象模型核心](../models/object-model-core.md)
- [操作与同步](../sync/operations-sync.md)
- [授权模型](../authz/capabilities.md)
- [加密与审计](../crypto-media/encryption-and-audit.md)

### 工具和库

- JSON Schema 验证库：`ajv` (JavaScript), `jsonschema` (Python)
- Canonical JSON：`canonical-json` (npm)
- DID 解析：`did-resolver`

## 联系方式

- 规范问题：提交 GitHub Issue
- 实现问题：在 Discussions 中讨论
- 安全问题：参考安全报告流程
