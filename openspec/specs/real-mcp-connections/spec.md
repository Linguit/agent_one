# 真实 MCP 连接与工具管理

## Purpose

提供用户隔离的真实 MCP 连接管理、工具发现和调用来源，让 Chat 与后续 AIOps 共用安全、可审计的工具接入。

## Requirements

### Requirement: 用户连接管理
系统 SHALL 提供 GET/POST /mcp/connections、PUT/DELETE /mcp/connections/{id}，持久化 owner、name、transport、url、enabled、timeoutSeconds、retries、lastCheck、lastError、discoveredTools 和时间戳。owner MUST 来自认证上下文。

#### Scenario: CRUD 与 owner 隔离
- **WHEN** 用户创建、编辑、删除或列举连接，另一用户访问该 id
- **THEN** 仅返回和修改自身记录，越权访问失败

#### Scenario: URL 与范围
- **WHEN** 提交非 http/https、无 host、有 userinfo 的 URL，或超出 1..300 的超时、0..5 的重试数
- **THEN** 返回校验失败，完整 URL 不出现在错误中

#### Scenario: 拒绝重复连接
- **WHEN** 同一用户新增或编辑连接，与其另一记录的 transport 和完整 URL 相同
- **THEN** 系统 MUST 返回 HTTP 409，包含并发提交、改名和禁用场景；编辑记录自身不算重复，不同用户可分别保存同一服务

### Requirement: 真实发现与调用
系统 SHALL 使用 langchain-mcp-adapters/MCP client 执行 POST /mcp/connections/{id}:check，返回实际工具列表或安全错误，更新检查状态。系统 MUST 支持 SSE 和 Streamable HTTP，不提供 fake profile/result。

#### Scenario: 检查和实际工具列表
- **WHEN** 检查可访问的真实连接或不可达连接
- **THEN** 保存真实发现列表或固定安全错误，编辑后旧检查失效

#### Scenario: 有界超时重试与调用一次
- **WHEN** 发现超时或失败，或工具调用失败
- **THEN** 发现最多尝试 retries+1 次且每次受 timeoutSeconds 限制；工具调用受超时限制且仅调用一次

### Requirement: 统一用户工具来源
系统 SHALL 按当前 owner 的 enabled connections 聚合真实工具供 Chat 与后续 AIOps 共用。同名工具 MUST 明确报冲突。仅当用户无连接记录时允许 clsMcpServer.url 真实回退。

#### Scenario: 禁用与冲突
- **WHEN** 用户禁用全部记录，或两个启用 server 返回同名工具
- **THEN** 禁用记录不连接且不触发回退；冲突导致明确错误而不随机选择

### Requirement: Chat 注入与安全审计
系统 SHALL 将真实 MCP tools 注入请求级 Agent，复用 tool.call SSE 和统一 audit；审计 MUST 仅记录工具名、参数键、状态、耗时及安全摘要。

#### Scenario: 工具调用与脱敏
- **WHEN** Chat 调用 MCP 工具，参数和结果含凭据
- **THEN** 真实工具执行，SSE 报告生命周期，持久审计和日志不包含参数值、原始结果及异常内容

### Requirement: 桌面管理与真实验收
系统 SHALL 提供 /mcp typed client、Pinia store、连接列表编辑启停、transport 选择、检查状态和实际发现列表，以服务器为事实来源。界面和文档 MUST 明确完整 URL 包括 query 会持久化并返回，禁止 token/secret 放入 query；README 仅说明官方 cls-mcp-server 在主机运行，细节留给 P26。

#### Scenario: 状态同步与用户切换
- **WHEN** 保存、删除、检查完成或用户切换
- **THEN** 重新读取服务器状态，清空旧用户数据并丢弃迟到响应，错误保持可见

#### Scenario: 桌面与真实 CLS smoke
- **WHEN** 执行验收
- **THEN** 以 1440x900 验证页面标题布局溢出和控制台；真实官方 CLS smoke 独立记录，无凭据或服务时明确未执行，单元替身不等于真实验收
