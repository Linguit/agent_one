## Purpose

统一 HTTP、OpenAPI 与 SSE 合同，作为前后端单一事实来源。

## Requirements



### Requirement: HTTP envelope and error catalog
共享合同 SHALL 定义成功 envelope `{ok:true,data,meta:{requestId}}` 与失败 envelope `{ok:false,error:{code,category,httpStatus,message,details?},meta:{requestId}}`。错误目录 MUST 覆盖 `AUTH_*`、`BUSINESS_*`、`VALIDATION_*`、`SYSTEM_*` 前缀，每项包含 category、HTTP status 和安全默认消息，并允许后续追加业务错误。

#### Scenario: 成功响应
- **WHEN** foundation/health 返回成功
- **THEN** JSON 包含 ok=true、data 和带 requestId 的 meta，且不含 error。

#### Scenario: 失败响应
- **WHEN** 请求触发已登记错误
- **THEN** JSON 包含 ok=false、完整 error 字段和同一 requestId，默认 message 不泄露内部细节。

#### Scenario: 验证错误字段路径
- **WHEN** 请求体验证失败
- **THEN** error.category=VALIDATION、httpStatus=422，details 包含可定位的字段路径。

### Requirement: Request ID and FastAPI integration
后端 SHALL 提供统一 success/error helper、验证/未处理异常 handler，并优先透传合法 `X-Request-ID`；缺失或非法时生成 UUID。响应 header 与 envelope.meta.requestId MUST 使用同一值。

#### Scenario: 透传 request id
- **WHEN** 请求带合法 X-Request-ID
- **THEN**响应 header 和 envelope meta 原样使用该 ID。

#### Scenario: 生成 request id
- **WHEN** 请求缺少或带非法 X-Request-ID
- **THEN**后端生成新的 UUID 并写入 header 与 envelope meta。

### Requirement: OpenAPI contract registry
合同 MUST 以机器可读方式登记 OpenAPI path，当前至少覆盖 foundation/health；新增 endpoint 前 MUST 先补充合同与合同测试。

#### Scenario: health path registered
- **WHEN** 生成应用 OpenAPI 文档
- **THEN** foundation/health path、响应 envelope 和错误响应可被机器读取并与合同快照一致。

#### Scenario: unregistered endpoint rejected
- **WHEN** 新增 endpoint 未登记合同
- **THEN** contracts test 或 lint 门禁失败。

### Requirement: SSE discriminated union
合同 SHALL 定义公共字段 id、type、channel（chat|aiops）、timestamp 的判别联合事件：content.delta、reasoning.delta、tool.call、reference.source、task.status、report、complete、error。tool.call MUST 支持 started、delta、completed、failed，SSE error MUST 复用 HTTP error 结构。

#### Scenario: 全事件目录可解析
- **WHEN** parser 接收任一登记 type 的合法 data
- **THEN**返回对应的 typed union，公共字段和专属字段均可访问。

#### Scenario: tool lifecycle
- **WHEN** 接收 started、delta、completed、failed 的 tool.call
- **THEN** parser 保留生命周期状态、tool 标识和增量数据，不把事件降级为私有结构。

#### Scenario: SSE error reuse
- **WHEN** 服务发送 error 事件
- **THEN** data.error 与 HTTP 失败 envelope 的 error 字段同形，且包含 requestId 元数据。

### Requirement: Typed clients and chunk-safe parser
前端 SHALL 提供 typed apiClient 与 sseClient，支持 bearer/request-id 注入扩展点、解码 HTTP envelope，并按跨 chunk 的空行 frame 边界解析 SSE。前端 MUST 复用共享 event union，禁止私有临时 event union 或 payload。

#### Scenario: 跨 chunk frame
- **WHEN** 一个 SSE frame 被拆分到多个网络 chunk
- **THEN** parser 缓冲不完整内容，拼接后只发出一次完整 typed event。

#### Scenario: transport extension points
- **WHEN** 调用 apiClient/sseClient
- **THEN** caller 可注入 request id 和 bearer，而 secret 不进入合同或浏览器 bundle。

#### Scenario: 禁止临时结构
- **WHEN** 合同测试扫描前后端 transport 类型
- **THEN** 未登记的 SSE type 或 response payload 使测试失败。


