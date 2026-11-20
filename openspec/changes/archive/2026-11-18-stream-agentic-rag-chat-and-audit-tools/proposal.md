## Why

已有会话和知识检索工具需要接入可持久化的流式对话，让模型按用户意图决定是否检索。

## What Changes

- 提供会话消息 SSE 接口及工具审计查询。
- 接入知识检索和当前时间工具，MCP 由 P18 扩展。

## Capabilities

### New Capabilities

- `agentic-chat-stream`：模型自主选工具、消息持久化和工具审计。

### Modified Capabilities

## Impact

依赖 P06 模型、P12 检索、P14 会话与 P09 可观测性基础，涉及后端、SQLite、共享契约及前端流客户端。
