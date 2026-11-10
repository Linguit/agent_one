## Why

后续 Agent 和检索功能需要通过统一边界调用百炼模型，并在配置错误和供应商失败时保护凭据。

## What Changes

- 复用本地 JSON 深合并，扩充模板并新增模型配置校验。
- 提供可注入的对话、嵌入、重排及异步就绪探测。

## Capabilities

### New Capabilities

- `qwen-model-providers` 提供百炼模型调用边界。

### Modified Capabilities

- `secure-project-config` 补充缺失文件错误和配置模板结构。

## Impact

依赖现有配置、SQLite Repository 基础和共享契约。后端增加 langchain-openai 与 HTTPX 运行时依赖。本次范围为后端模型边界。
