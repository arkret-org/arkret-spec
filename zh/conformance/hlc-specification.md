# 混合逻辑时钟 (HLC) 规范

## 1. 概述

Contrix v1 使用混合逻辑时钟 (HLC) 进行分布式事件排序。本规范定义了 Contrix 中 HLC 值的精确格式、编码和比较规则。

## 2. 动机

纯物理时钟存在时钟漂移问题，而纯逻辑时钟不关联物理时间。HLC 结合两者优势：

- 在分布式系统中单调递增
- 紧密跟踪物理时间
- 无需全局协调即可排序

## 3. HLC 格式

### 3.1 结构

HLC 是 (physical_time, logical_counter, node_id) 三元组：

- **physical_time**: 48 位 Unix 毫秒时间戳（约 8,925 年后溢出）
- **logical_counter**: 16 位单调计数器（每毫秒最多 65,535 个事件）
- **node_id**: 节点标识符的 32 位哈希（用于平局消除）

### 3.2 文本编码

HLC 值编码为以下格式的字符串：

```
<physical_hex>-<logical_hex>-<node_hex>
```

其中：

- `physical_hex`: 12 字符小写十六进制（零填充至 12 字符）
- `logical_hex`: 4 字符小写十六进制（零填充至 4 字符）
- `node_hex`: 8 字符小写十六进制（SHA256(node_id) 的前 32 位）

### 3.3 示例

合法 HLC 值：

- `01970e589d21-0004-a13f9c2e`
- `000000000001-ffff-12345678`
- `ffffffffffff-0000-abcdef12`

非法 HLC 值：

- `1970e589d21-1-a13f9c2e`（未零填充）
- `01970e589d21-0004`（缺少 node 部分）
- `xyz-0004-a13f9c2e`（非法十六进制）

## 4. HLC 操作

### 4.1 初始化

节点启动时，初始化其 HLC：

```
hlc = max(current_physical_ms, 0)
```

### 4.2 发送事件

发送事件时：

```
hlc = max(current_hlc, current_physical_ms)
if hlc.physical == current_physical_ms:
    hlc.logical += 1
else:
    hlc.physical = current_physical_ms
    hlc.logical = 0
```

### 4.3 接收事件

接收带有 HLC `hlc_remote` 的事件时：

```
hlc = max(current_hlc, current_physical_ms, hlc_remote)
if hlc.physical == current_physical_ms or hlc.physical == hlc_remote.physical:
    hlc.logical += 1
else:
    hlc.logical = 0
```

### 4.4 Node ID 计算

```
node_hex = SHA256(node_identifier)[0:8]
```

其中 `node_identifier` 是 principal DID 或 service DID。

## 5. 比较规则

HLC 比较基于编码字符串的字典序：

1. 首先比较 physical_hex（数值比较）
2. 若相等，比较 logical_hex（数值比较）
3. 若相等，比较 node_hex（字典序比较）

由于固定宽度十六进制编码保证了正确的排序。

### 5.1 伪代码

```
function compare_hlc(hlc1, hlc2):
    p1 = parse_hex(hlc1.physical_hex)
    p2 = parse_hex(hlc2.physical_hex)
    if p1 != p2:
        return p1 - p2

    l1 = parse_hex(hlc1.logical_hex)
    l2 = parse_hex(hlc2.logical_hex)
    if l1 != l2:
        return l1 - l2

    return strcmp(hlc1.node_hex, hlc2.node_hex)
```

## 6. 在 Contrix 中的使用

### 6.1 Timeline 事件排序

客户端 timeline、backfill page 和展示层的默认事件排序按以下规则递增：

```
causal_depth ASC, hlc ASC, actor_id ASC, actor_seq ASC, event_id ASC
```

HLC 在因果依赖之后提供第二级展示排序。该顺序不表示授权状态或对象字段冲突的 winner 选择，也不得覆盖 `prev_refs` / `auth_refs` 已经表达的因果关系。

### 6.2 State / Reducer 冲突解决

当两个并发操作冲突（无因果关系）时：

1. 按该 reducer 或 auth-state profile 的授权权重 / domain-specific priority 比较（若定义）
2. 按 HLC 比较（较大的已验证 HLC 胜出）
3. 若 HLC 相等（极少见），按 actor_id 比较（字典序）
4. 若仍相等，按 event_id 或 event hash 比较（字典序，按对应 profile 固定）

冲突 winner 顺序与 6.1 的 timeline 展示顺序是两个不同投影：前者选状态，后者排历史。实现 MUST 在 profile 中明确使用哪一个，不得把 timeline 中最后出现的 Event 直接当作状态 winner。

### 6.3 游标位置

同步游标包含 HLC 以跟踪时间线位置：

```json
{
  "s": {
    "cx:space:...": {
      "o": "01970e589d21-0004-a13f9c2e"
    }
  }
}
```

## 7. 验证规则

实现 MUST：

- 使用正则表达式验证 HLC 格式：`^[0-9a-f]{12}-[0-9a-f]{4}-[0-9a-f]{8}$`
- 拒绝或隔离物理时间超过 hard future-skew 上限的 HLC 值；v1 默认 hard 上限为 5 分钟
- 对高风险 state event 应使用 profile 声明或本地策略中的更小 expected drift 窗口；5 分钟不得被解释为排序信任窗口
- 在本地维护单调性
- 使用一致的 node_id 计算方式

该文本格式对 Event envelope、cursor、snapshot frontier、暴露 HLC 位置的 sync token 和 conformance fixture 都是规范格式。profile 不得把 logical counter 替换为 8 字符或可变宽度编码；若确需改变，必须声明新的 HLC version 和 schema profile。

## 8. 安全考虑

1. **时钟漂移攻击**：验证物理时间在 hard 上限内，并对高风险 state event 使用更小 expected drift / observed drift 检查
2. **Node ID 碰撞**：使用完整 SHA256 空间使碰撞可忽略
3. **重放检测**：结合 HLC 与其他因果追踪机制

## 9. 实现指南

### 9.1 时钟漂移处理

节点应跟踪观察到的最大漂移：

- 若本地时钟落后于远端，则推进到远端时间
- 若本地时钟超前，限制推进速率
- 漂移超过 1 秒时记录日志
- 漂移超过 profile expected drift 但未超过 hard 上限时，对普通事件可 soft-fail / backfill；对 capability、membership、policy、MLS epoch、service binding 和 Space upgrade 等高风险事件应 quarantine 或人工审查

### 9.2 溢出处理

物理时间溢出在数千年内不会发生，但实现应：

- 拒绝 `physical_hex > ffffffffffff` 的 HLC 值
- 若需要，优雅过渡到版本 2

### 9.3 测试

测试套件应包含：

- 高并发下的单调性
- hard future-skew 边界、profile expected drift 和 observed drift 超限时的 soft-fail / quarantine 行为
- 字典序排序与数值比较的一致性
- Node ID 计算一致性

## 10. 一致性

声称支持 Contrix v1 的实现 MUST：

- 接受指定格式的 HLC 值
- 生成指定格式的 HLC 值
- 实现正确的比较和排序
- 维护本地单调性
- 验证传入的 HLC 值

## 11. 从时间戳迁移

从纯时间戳过渡的实现应：

- 将现有时间戳映射为 HLC：`physical = timestamp_ms, logical = 0`
- 对所有迁移事件使用一致的 node_id
- 在快照元数据中记录迁移截止点
