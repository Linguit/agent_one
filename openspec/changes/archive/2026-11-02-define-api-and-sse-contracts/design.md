## Context

P01 已有 monorepo、FastAPI foundation/health 与 Vue 桌面前端，但没有共享接口契约。该 change 横跨共享包、后端 transport、前端 transport 和测试，必须保持模块导入无外部资源副作用。

## Goals / Non-Goals

**Goals:**
- 以 `packages/api-contracts` 维护可生成/可校验的 envelope、错误目录、OpenAPI path 元数据和 SSE 联合类型。
- 后端和前端分别以本地语言类型实现同一序列化形状，并用合同测试证明一致。
- 让 health 成为当前唯一登记的 OpenAPI path，并为后续 endpoint 设立先补合同的门禁。

**Non-Goals:**
- 不实现认证、聊天、AIOps、知识库、MCP、LLM 或租户隔离。
- 不新增外部服务、数据库资源或应用 Compose 服务。

## Decisions

1. **共享合同采用 TypeScript 源码 + JSON Schema/OpenAPI 快照**：前端直接导入类型，后端以 Pydantic 模型复刻序列化形状；合同测试比较字段和枚举，避免后端导入 TypeScript。
2. **错误目录集中注册**：错误码使用稳定前缀和默认安全消息，helper 只接受目录中的 code，未知 code 走 SYSTEM_INTERNAL_ERROR。
3. **SSE parser 以增量 buffer 处理**：按空行切 frame，保留末尾不完整内容，解析 `event`/`data` 后交给共享判别联合；`error` 的 data 复用 HTTP error 对象。
4. **request-id 由后端中间件负责**：优先透传合法 `X-Request-ID`，缺失时生成 UUID，并写入 response header 与 envelope meta；前端 client 暴露 bearer/request-id 注入扩展点但不读取 secret 配置。
5. **合同测试作为扩展门禁**：OpenAPI snapshot 只允许 foundation/health；新增 path 或 SSE type 必须先修改合同与测试，禁止私有临时 payload。

## Risks / Trade-offs

- [Risk] TS 与 Pydantic 可能出现可选字段差异 → 通过 JSON fixture 和字段路径测试锁定序列化结果。
- [Risk] SSE 网络分块边界复杂 → 覆盖任意 chunk 切分、空行和多事件 frame 的 parser 测试。
- [Risk] 错误信息泄露内部细节 → 默认消息来自安全目录，异常 handler 仅在 details 明确允许时输出结构化非敏感信息。

## Migration Plan

先新增合同和测试，再切换 health 与基础异常处理，最后接入前端 typed clients。回滚时保留原 health 路径并移除 transport 接入；不涉及数据迁移。

## Open Questions

无；后续提案可在不破坏既有字段的前提下扩展错误码、SSE type 和 OpenAPI path。
