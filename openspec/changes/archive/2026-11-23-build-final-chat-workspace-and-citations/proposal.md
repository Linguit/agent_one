## Why

已有会话、流、配置、记忆、MCP 和检索接口尚未组合为可用的聊天页面。第 19 个变更将这些依赖接入统一桌面工作区，并提供逐轮可追溯的引用体验。

## What Changes

- 全局左栏管理会话；主区固定 composer、局部滚动 transcript，右栏独立管理 Prompt 与 Skill。
- 接入真实 API 与共享 SSE，正文按字符等待约 28 ms，完成后对账历史。
- 安全 Markdown、可折叠推理与工具摘要、逐消息引用卡和检索轨迹。
- 提供 Prompt CRUD、Skill 上传与多选、记忆模式和手动压缩及错误恢复。
- 覆盖键盘、IME、流、引用隔离、安全与桌面布局，并进行真实模型和工具 smoke。

## Capabilities

### New Capabilities
- `final-chat-workspace`: 最终桌面聊天工作区、流状态、配置操作与引用交互。

### Modified Capabilities

无。复用已有后端能力，不改变其业务权限与服务配置机制。

## Impact

影响 apps/frontend、共享引用事件类型及相关契约测试、桌面验证脚本和文档。复用认证及服务端持久化；领域状态只保存在 Pinia，不新增 localStorage。真实模型、检索与 MCP 可用性是归档验收依赖。
