# WebRTC Signaling Draft

## 1. 目标

实时音视频通话 (VoIP/Video Call) 是现代协作协议的必备能力。与持久化的业务数据不同，通话信令具有高频、短暂、对延迟极度敏感的特征。

本规范定义了如何利用 Contrix 的 **Ephemeral Channel** 来传输 WebRTC 信令，实现端到端的音视频通话。

## 2. 设计原则

### 2.1 信令是 Ephemeral 的
通话信令（Offer, Answer, ICE Candidates）本身不需要永久记录在 Space Repo 的因果图中。它们 MUST 通过 Relay 的 Ephemeral Channel 发送。
通话的“历史记录”（例如“Alice 呼叫了 Bob，通话时长 5 分钟”）MAY 作为普通的 Durable Event 写入 Repo，但这与信令协商过程解耦。

### 2.2 信令必须加密
为了防止中间人窃听通话双方的 IP 地址或注入恶意 SDP，所有的 WebRTC 信令 MUST 被端到端加密（使用该 Space 或 DM 的 MLS 组密钥）。

### 2.3 支持 1对1 与多方通话
- 1对1 呼叫：标准 WebRTC P2P 协商。
- 多方呼叫 (Group Call)：建议采用类似 Matrix 的 Focus/SFU 架构，信令统一发给 SFU Bot，或网状 P2P 协商（仅限小规模群组）。

## 3. 信令事件流

一次标准的 1对1 呼叫涉及以下事件类型：

1. `cx.call.invite` (Offer)
2. `cx.call.candidates` (ICE)
3. `cx.call.answer` (Answer)
4. `cx.call.reject` (拒绝)
5. `cx.call.hangup` (挂断)

所有的信令事件都被包裹在统一的 Ephemeral Envelope 中，通过 Relay 广播给目标 Actor 的在线设备。

## 4. 信令负载格式

### 4.1 呼叫邀请 `cx.call.invite`

发起方向接收方发送包含 SDP Offer 的邀请：

```json
{
  "type": "cx.call.invite",
  "call_id": "call-12345-abcde",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "party_id": "device-alice-1",
  "lifetime_ms": 60000,
  "offer": {
    "type": "offer",
    "sdp": "v=0\r\no=- 25678 753849 IN IP4 127.0.0.1\r\n..."
  },
  "capabilities": {
    "dtmf": true,
    "video": true
  }
}
```

| 字段 | 必需 | 说明 |
|------|------|------|
| `call_id` | MUST | 通话的全局唯一标识符 |
| `space_id` | MUST | 呼叫发生的 Space 上下文 |
| `party_id` | MUST | 发起方当前设备的唯一标识（避免多端冲突） |
| `lifetime_ms` | SHOULD | 邀请的有效期，超时客户端应视为未接通 |
| `offer` | MUST | WebRTC RTCSessionDescriptionInit 对象 |

### 4.2 呼叫应答 `cx.call.answer`

接收方同意接听，并回复 SDP Answer：

```json
{
  "type": "cx.call.answer",
  "call_id": "call-12345-abcde",
  "space_id": "cx:space:01JS0SP000000000000000000",
  "party_id": "device-bob-2",
  "answer": {
    "type": "answer",
    "sdp": "v=0\r\no=- 98765 43210 IN IP4 127.0.0.1\r\n..."
  }
}
```

### 4.3 交换候选者 `cx.call.candidates`

Trickle ICE 机制下的候选者交换，可以在 Invite 之后持续发送：

```json
{
  "type": "cx.call.candidates",
  "call_id": "call-12345-abcde",
  "party_id": "device-alice-1",
  "candidates": [
    {
      "candidate": "candidate:842163049 1 udp 1677729535 1.2.3.4 54321 typ srflx",
      "sdpMid": "video",
      "sdpMLineIndex": 1
    }
  ]
}
```

### 4.4 拒绝呼叫 `cx.call.reject`

```json
{
  "type": "cx.call.reject",
  "call_id": "call-12345-abcde",
  "party_id": "device-bob-2",
  "reason": "busy" // busy, ignored, declined
}
```

### 4.5 挂断呼叫 `cx.call.hangup`

```json
{
  "type": "cx.call.hangup",
  "call_id": "call-12345-abcde",
  "party_id": "device-alice-1",
  "reason": "user_hangup" // user_hangup, ICE_failed, timeout
}
```

## 5. 多设备冲突处理

由于用户的账号可能登录在多个设备上，当 Alice 呼叫 Bob 时，Bob 的所有设备都会收到 `cx.call.invite` 并响铃。

1. **唯一应答**：如果 Bob 在设备 B1 上点击了接听，B1 发出 `cx.call.answer`。
2. **响铃取消**：Bob 的设备 B2 收到信令通道广播的 B1 `cx.call.answer` 后，知道该通话已被本人的其他设备接管，应立即停止响铃。
3. **忽略冗余**：Alice 收到 B1 的 Answer 后建立连接。如果由于网络延迟又收到了 B2 的 Answer，Alice 的客户端 SHOULD 拒绝 B2 的协商。

## 6. 与推送的集成

为了在移动端实现类似系统电话的唤醒（如 iOS CallKit / Android ConnectionService），`cx.call.invite` 事件 MUST 触发具有最高优先级的**VoIP Push Notification**。

Relay 节点在匹配推送规则时，应识别 `cx.call.invite` 并向推送网关发送带有 `voip: true` 标记的脱敏 payload。

## 7. 后续待细化

- 基于 SFU (Selective Forwarding Unit) 的大规模群呼信令路由
- 屏幕共享 (Screen Sharing) 的 SDP 标识符规范
- TURN/STUN 服务器在 Space 级别的动态发现机制
