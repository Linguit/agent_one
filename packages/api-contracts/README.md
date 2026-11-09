# 基础接口契约

当前 typed entrypoint 只导出 HealthResponse，不预先创建认证、聊天或知识库类型。前后端仍需各自运行时校验，TypeScript 类型不会自动验证 HTTP 数据。
根 npm install 后，在本目录执行 npm run typecheck、npm run test。
通过 `import type { HealthResponse } from '@super-ai/api-contracts'` 导入。
