## Why

桌面前端需要接入 P04 会话，为后续业务模块提供统一的导航、请求与反馈基础。

## What Changes

- 提供中文登录、注册和受保护的桌面工作台。
- 复用共享契约，统一 HTTP、SSE 和会话清理。
- 提供可访问的异步状态与全局反馈。四个业务入口预留路由和画布。

## Capabilities

### New Capabilities

- `chinese-vue-app-shell` 提供认证工作台与共享交互组件。

### Modified Capabilities

## Impact

涉及 `apps/frontend`、桌面验收脚本与 OpenSpec，依赖现有认证接口及共享契约。
