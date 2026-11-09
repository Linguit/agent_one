## Why

当前后端、前端与未来功能缺少共享的 HTTP 和 SSE 合同，容易出现重复 envelope、临时错误码和私有事件结构，导致接口漂移。现在建立单一事实来源，可让 P01 的 health/foundation 接口先具备稳定机器可读合同，并为后续提案提供可扩展基线。

## What Changes

- 在 `packages/api-contracts` 定义成功/失败 response envelope、错误目录、OpenAPI 组织方式与判别联合 SSE 事件。
- 后端增加统一响应 helper、验证/异常处理和 request-id 透传或生成，并让 foundation/health 使用合同形状。
- 前端增加 typed `apiClient`/`sseClient`，共享事件类型并正确解析跨 chunk SSE frame。
- 增加前后端合同一致性、错误字段路径、request-id、SSE 全目录和禁止临时 payload 的测试。
- **BREAKING**：后续接口不得继续使用未登记的 response 或 SSE payload。

## Capabilities

### New Capabilities
- `api-contracts`: HTTP envelope、错误目录、OpenAPI path 和 SSE 事件的共享机器可读合同。

### Modified Capabilities
- 无。

## Impact

影响 `packages/api-contracts`、`apps/backend/src/super_ai`、`apps/frontend`、foundation/health OpenAPI 输出及对应测试；不引入认证、聊天、知识库、AIOps、MCP 或外部服务资源。
