## Why

后续流式 Agent 需要稳定的服务端会话和消息边界，以便读取历史并保存结果。现阶段先明确会话归属、消息排序和写入事务，让后续流式执行可以复用一致的持久化行为。

## What Changes

- 通过 SQLite 管理会话和消息，复用认证、租户隔离和 API 错误信封。
- 定义非流式增删查接口与前端状态对账。本阶段不发起模型调用。

## Capabilities

### New Capabilities

- `chat-sessions` 管理会话与消息生命周期。

### Modified Capabilities

- `api-contracts` 增补会话 API 的共享契约。

## Impact

涉及后端迁移、SQLite Repository、FastAPI、共享 TypeScript 契约和前端状态。
