## 1. 后端连接与工具来源

- [x] 1.1 添加 migration、输入输出模型、owner CRUD 和真实检查 API
- [x] 1.2 添加真实 adapter、超时重试、禁用过滤、冲突检测和 CLS 回退
- [x] 1.3 注入请求级 Chat Agent 并统一审计脱敏

## 2. 桌面管理

- [x] 2.1 添加 typed contracts/client、Pinia store 与 /mcp 页面
- [x] 2.2 补充 URL 安全说明和 P26 文档边界

## 3. 测试与验证

- [x] 3.1 覆盖 CRUD/owner、校验、发现、超时重试、调用一次、禁用、冲突、Chat 与审计
- [x] 3.2 覆盖 UI store 并在 1440x900 检查页面和控制台
- [x] 3.3 独立运行或明确记录真实官方 CLS smoke 未执行的原因
- [x] 3.4 运行完整门禁、OpenSpec 验证与 git diff --check，生成验证报告

## 4. 同步与归档

- [x] 4.1 同步 delta specs 并在所有门禁通过后归档
