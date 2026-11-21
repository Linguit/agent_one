## Why

长会话持续传入全部消息会耗尽模型窗口。P17 在保留完整历史的同时，让每个会话独立控制压缩策略并在写入前检查预算。

## What Changes

- 保存三种记忆模式、可追溯摘要、压缩边界与上下文用量。
- 新增 owner scoped 记忆配置和手动压缩 API；复用 Prompt/Skill catalog 与 Qwen capability。
- 自动压缩完整 turn；候选上下文达到 95% 时拒绝且不保存新消息。
- 前端契约、client 和 store 支持读取、更新与压缩；composer 入口留给 P19。

## Capabilities

### New Capabilities
- `session-memory`: 会话记忆策略、摘要、预算防护与管理 API。

### Modified Capabilities

无；在已有会话和 streaming 基础上增加独立记忆能力。

## Impact

影响 SQLite migration、ChatRepository、ChatAgent、会话 API、共享契约及前端 store。复用 LangChain token 估算与现有模型工厂，不新增外部服务。
