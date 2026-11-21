## 1. 持久化与核心策略

- [x] 1.1 新增 migration、记忆状态与 owner scoped 原子存储
- [x] 1.2 实现纯 token 估算、完整 turn 边界、三模式压缩和预算回滚

## 2. 接口与集成

- [x] 2.1 记忆 API、刷新 DTO、模型调用前预算与共享 HTTP/SSE 错误
- [x] 2.2 共享契约、前端 client/store 及 owner 切换保护

## 3. 验证与交付

- [x] 3.1 覆盖触发边界、历史保留、回滚、隔离与配置错误，验证 migration 往返
- [x] 3.2 执行全部后端、契约、前端、构建、安全、桌面与文档门禁
- [x] 3.3 核对 artifacts 与实现、生成验证报告，运行 OpenSpec validate 和 diff check
- [x] 3.4 同步规范并归档
