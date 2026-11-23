# 第 19 个变更验证报告

日期：2026-11-23。变更：build-final-chat-workspace-and-citations；schema：spec-driven。

## 验证结果

| 维度 | 结果 |
| --- | --- |
| 完整性 | 9/9 任务已完成；6 项功能与验收要求均有实现，主规范已同步且变更已归档 |
| 正确性 | 6/6 要求覆盖；前端 39 项、契约 5 项、后端全量 150 项测试通过 |
| 一致性 | 复用现有认证、API 与共享 SSE；Pinia 领域状态、顺序 28ms 延迟和服务端对账符合设计 |

未发现待修复的功能 CRITICAL、WARNING 或 SUGGESTION。所有功能验证通过；主规范 openspec/specs/final-chat-workspace/spec.md 已同步，变更已归档至 2026-11-23-build-final-chat-workspace-and-citations。

## 需求与证据

| 要求 | 实现 | 验证 |
| --- | --- | --- |
| 固定桌面工作区 | apps/frontend/src/WorkspaceLayout.vue:59；ChatView.vue；style.css | scripts/check-desktop.mjs：空白 transcript、全局左栏、长会话局部滚动、固定 composer、跨页面返回与刷新；1440×900 截图已查看 |
| 输入与安全正文 | ChatView.vue 的 keydown/composition；chatPresentation.ts 的 marked renderer 和 DOMPurify | chatWorkspace.test.ts：Enter、Shift+Enter、IME、恶意 HTML/链接；桌面 textarea resize=none |
| 顺序流与对账 | chatStore.ts:102 的 for-await；110 的 setTimeout(28)；130 的工具审计加载 | chatWorkspace.test.ts 的 Unicode fake timer；chatStore.test.ts 的对账、账号隔离；transport.test.ts 的逐字节 UTF-8/SSE 断帧 |
| 每轮引用与证据 | agent_chat.py 的 Citation、chunkId 去重及助手 metadata；knowledge_retrieval.py 的真实 rrfRank；ChatReferences.vue | 后端 test_chat_sessions.py 验证完整引用和下一轮空引用；前端排序最多 5 条、未命中、文档导航与历史隔离测试；真实检索引用和刷新检查 |
| 配置与生命周期 | ChatConfiguration.vue、configurationStore.ts、ChatView.vue 的 memory/工具摘要 | Prompt CRUD、Skill 上传/选择/删除及失败恢复测试；记忆模式、压缩错误重试测试；推理折叠和工具参数不渲染测试 |
| 真实服务验收 | scripts/serve_chat_smoke.py、scripts/check-chat-real.mjs | 真实模型、嵌入、Milvus、重排、官方 CLS MCP；四轮实际 API/SSE 全部 complete，浏览器 errors=[] |

## 全部门禁

- openspec validate --all：同步前 22/22、同步后 23/23 通过；归档后再次校验主规范。
- 后端 uv run ruff check .、uv run pyright：通过；uv run pytest：150 passed。另有两个既有 MCP SDK 弃用提示，不影响功能。
- contracts:typecheck、contracts:test：通过，5 tests。
- frontend:typecheck、frontend:test、frontend:build：通过，39 tests。
- frontend:security：两种 analytics 模式的 7 个私密哨兵均未出现。
- frontend:desktop：Edge 1440×900 通过，已覆盖空白和长对话、记忆控件、跨页面返回与刷新。
- foundation:test：6/6 通过；docs:build、docs:security、git diff --check：通过。
- 新增 Python 验收启动器 Ruff：通过。

## 真实桌面 smoke

使用真实本机模型及提供方配置，通过应用工厂注入独立 SQLite 和 Milvus 集合，未用接口或模型替身。Milvus 实际连接 19530；官方 CLS MCP 连接用户提供的 http://127.0.0.1:3000/sse。

1. 普通问答：一句话解释 HTTP；真实 SSE reasoning/content/complete。
2. 上传验收 Markdown 并完成真实嵌入和索引；模型自主调用 knowledge_retrieval，返回摘录及 vector/BM25/RRF/rerank 证据。
3. 下一轮普通回答不检索，无新引用；刷新后上一条助手引用保留，当前助手无上一轮引用。
4. 通过 MCP 页面保存与检查官方连接，模型自主调用 GetRegionCodeByName 并完成；工具输出仅显示安全摘要。
5. 操作记忆模式，检查 1440×900 固定输入区、无页面溢出及浏览器无错误。

本机 ignored 的 .cache/chat-real-smoke.json 中 ordinary、knowledge、mcp、referenceIsolation、layout 均为 true，errors 为空；.cache/chat-real-smoke.png 已目视检查。截图与运行数据不进入版本库。

## 验证期间修复

- 后端原先只保存 title/uri，已补齐原始检索证据，并保留真实 RRF 候选排名。
- 修复长对话撑高外层网格、composer 离开视口的问题，并补充浏览器回归。
- 修复从知识库返回聊天后 URL 未同步、刷新丢失当前会话的问题，并补充回归。
- 清空现有模板中的非空凭据，保留有效本机配置；基础安全断言改为不回显凭据值。
- 本机 Milvus 配置指向未监听的 19531，验收通过显式连接实际 19530 和独立集合解决；未改动其他项目或既有集合。

## 交付边界

没有自动提交或推送。初始存在的向量隔离与向量适配器改动保持原样。真实 smoke 使用独立数据库与集合；常规应用仍使用其本机 JSON，部署时应确认实际 Milvus 地址与 MCP 连接。
