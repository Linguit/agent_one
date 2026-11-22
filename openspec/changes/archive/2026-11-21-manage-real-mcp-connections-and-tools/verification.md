# P18 验证报告

日期：2026-11-21。变更：manage-real-mcp-connections-and-tools。工作流：spec-driven。

## 核对结果

| 维度 | 结果 |
| --- | --- |
| 完整性 | 10/10 任务完成；5 项需求、8 个场景均有实现和验证证据 |
| 正确性 | owner 隔离、真实 adapter、连接校验、发现重试、调用一次、冲突和 Chat 注入符合规范 |
| 一致性 | 使用现有项目配置、可信 owner、请求级 Agent、统一 audit、typed client 和 Vue 工作台 |

未发现需修复的关键问题或规范偏离。真实官方 CLS 验收的限制单独记录如下，不能将单元和浏览器替身等同于真实服务验收。

## 需求与场景证据

| 需求 | 实现 | 场景验证 |
| --- | --- | --- |
| 用户连接管理 | `0010_mcp_connections.py`、`mcp_contracts.py`、`memory/sqlite/mcp.py`、`mcp_api.py` | `test_crud_owner_discovery_and_stale_check` 覆盖 CRUD、401/403、owner、过期检查；`test_validation` 和 `test_url_preserved` 覆盖 URL、query 保留和范围 |
| 真实发现与调用 | `mcp_provider.py` 的 `discover_real`、`discover`、`bounded_tool` | `test_retry_timeout_cancel_call_once_and_adapter` 覆盖重试次数、超时、取消和两种 transport；`test_real_adapter_protocol_with_fake_http_transport` 使用真实 SDK 完成 initialize/list/call 且只调用一次 |
| 统一用户工具来源 | `McpProvider.tools` | `test_conflict_disabled_and_fallback` 覆盖 CLS 真实 URL 回退、禁用、不回退、服务器同名及内置工具冲突；Chat 冲突返回明确 SSE 错误且不调用工具 |
| Chat 注入与安全审计 | `main.py`、`agent_chat.py`、`tool_audits.py`、`mcp_logging.py` | `test_chat_injection_audit_and_error` 验证工具注入、成功/失败 tool.call、审计键占位符、固定摘要、耗时及异常脱敏；`test_sdk_log_privacy_is_context_scoped` 验证 SDK 原始消息不泄露且不影响其他操作日志 |
| 桌面管理与真实验收 | `mcp.ts`、`mcpClient.ts`、`mcpStore.ts`、`McpView.vue`、说明文档 | 4 项 store/client 测试覆盖服务器对账、CRUD/检查/启停、换用户、迟到响应、失败恢复和 ID 编码；1440x900 Edge 检查标题、CRUD、编辑、启停、发现展示、水平溢出及控制台 |

发现缓存只用于展示，每次 Chat 请求重新发现启用连接。检查禁用记录属于用户明确触发的排障操作，Chat 不连接禁用记录。PUT 清空旧检查结果，版本条件避免在并发编辑后写入旧检查结果。

## 已执行门禁

- `uv run ruff check .`、`uv run pyright` 通过。
- `uv run pytest -q`：148 通过；最终新增冲突断言后重跑 MCP 专项：25 通过。
- `npm run contracts:typecheck`、`npm run contracts:test`：通过，5 项契约测试。
- `npm run frontend:typecheck`、`npm run frontend:test`、`npm run frontend:build`：通过，28 项前端测试。
- `npm run frontend:security`：analytics 公开开/关两种构建均通过，7 个私密 sentinel 未进入产物。
- `npm run frontend:desktop`：1440x900 Edge 通过；截图 `.cache/desktop-mcp.png` 已人工查看。使用浏览器接口夹具，不代表真实 MCP 验收。
- `npm run foundation:test`：6 项通过。
- `npm run docs:build`、`npm run docs:security`：通过；临时文档首页 200，两份真实配置访问均 403。
- `openspec validate --all`、`git diff --check`：通过；同步和归档后再次执行。

兼容性记录：adapter 0.2.2 与 MCP 2.x 存在导入不兼容，已在 pyproject 和 uv.lock 中限定 `langchain-mcp-adapters>=0.2,<0.3`、`mcp>=1.26,<2`，锁定 MCP 1.30.0。SDK 的 Streamable HTTP 兼容入口产生 2 条弃用警告，协议测试实际通过；未忽略或伪造测试结果。

## 真实官方 CLS smoke

独立执行 `uv run python ../../scripts/check_mcp_cls.py`，结果为：**未执行：未配置真实官方 CLS MCP 服务 URL；未使用 mock 替代。**

因此本次没有官方 CLS 服务连接或实际 CLS 工具调用成功的证据。后续配置主机官方服务后需独立重跑 smoke；P26 负责启动与凭据说明。运行时真实 MCP provider 没有 mock profile、假列表或假结果。

## 部署与边界

新增 migration 仅在临时测试数据库中执行验证，未修改开发者数据库；部署时需 `uv run alembic upgrade head`。无自定义 headers；完整 URL 包括 query 会持久化并返回，界面和文档明确禁止其中放入 token/secret。

保留会话开始前的 4 个向量检索相关未提交改动，未自动提交或推送。未修改父级仓库其他项目。

## 规范同步与归档

已将 5 项新增需求、8 个场景同步至 `openspec/specs/real-mcp-connections/spec.md`，保留完整内容。2026-11-21 已归档至 `openspec/changes/archive/2026-11-21-manage-real-mcp-connections-and-tools`，`.openspec.yaml` 完整保留。
