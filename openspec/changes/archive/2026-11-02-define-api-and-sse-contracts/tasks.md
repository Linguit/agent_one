## 1. 共享合同

- [x] 1.1 建立 `packages/api-contracts` 的 TypeScript 类型、错误目录、HTTP envelope 与 SSE 判别联合
- [x] 1.2 生成/维护 OpenAPI 合同注册与 foundation/health 快照
- [x] 1.3 为合同增加 typecheck、序列化一致性和禁止临时结构测试

## 2. 后端 transport

- [x] 2.1 增加 Pydantic envelope、错误目录映射和统一 success/error helper
- [x] 2.2 增加 request-id 中间件及验证/异常 handler，并接入 foundation/health
- [x] 2.3 增加后端合同测试：四类 envelope、字段路径、request-id、OpenAPI 和 SSE 事件目录

## 3. 前端 transport

- [x] 3.1 建立 typed apiClient，支持 envelope 解码及 bearer/request-id 注入扩展点
- [x] 3.2 建立跨 chunk 安全的 sseClient/parser，复用共享 event union 和错误结构
- [x] 3.3 增加前端 typecheck、parser、全事件目录和禁止临时 payload 测试

## 4. 验证与收尾

- [x] 4.1 运行 contracts、backend、frontend、OpenSpec 和 git diff 门禁并修复失败项
- [x] 4.2 完成桌面 Web 1440x900 检查并记录结果
- [x] 4.3 同步 delta specs 到主规格并归档 change
