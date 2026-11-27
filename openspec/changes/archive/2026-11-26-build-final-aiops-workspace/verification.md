# P23 验证记录

日期：2026-11-26。Change：build-final-aiops-workspace，schema：spec-driven。

| 维度 | 结论 |
| --- | --- |
| 完整性 | 7/7 任务；4 项 Requirement 均有实现与验证证据 |
| 正确性 | 5 个 Scenario 已映射到交互测试或桌面浏览器检查 |
| 一致性 | typed client/Pinia、可信 owner 请求、持久状态对账、三栏内滚与安全摘要符合设计 |

## 需求与实现映射

- 输入/持久任务：apps/frontend/src/aiopsClient.ts；aiopsStore.ts 的 create/select/cancel/recover；AiopsView.vue 的输入、告警、历史与双状态显示。
- 实时/恢复：aiopsStore.ts 的 SSE 循环、事件去重、实时证据读取及 finally 持久状态恢复。仅创建后订阅一次，断流不重订阅；切换历史/owner/卸载清理旧响应。timeline 由事件与持久 checkpoints/steps 提供，Planner/Replanner 不进入状态枚举。
- 报告/证据/案例：aiopsPresentation.ts 复用安全 Markdown，隐藏原始 JSON 块；AiopsView.vue 显示 fallback、不确定性、证据来源、步骤审计、报告关联和结构化 case；inspectCase 通过当前 owner 知识库文档定位深链接。
- 固定高度：style.css 的 aiops-workspace、aiops-center、aiops-column、aiops-report、aiops-timeline；scripts/check-aiops-desktop.mjs 验证左右栏、报告与 timeline 超长内容内滚、页面高度与宽度、默认折叠、安全摘要及控制台。

## 自动门禁

- openspec validate --all：通过（归档前 27 项）。
- 后端 uv run ruff check .、uv run pyright：通过；uv run pytest：204 passed，2 条既有 MCP adapter 弃用提醒。
- contracts:typecheck、contracts:test：通过，8 tests。
- frontend:typecheck、frontend:test：通过，46 tests（新增 AIOps 7 tests）。
- frontend:build、frontend:security：通过；public=false/true 的 7 个私密哨兵均未进入产物。
- frontend:desktop：原有壳/MCP/聊天/知识库检查与新增 AIOps 1440×900 检查通过。
- foundation:test：6 passed。
- docs:build、docs:security：通过；首页 200，两份私密 JSON 403。
- git diff --check：通过。

旧桌面夹具原先期待 AIOps 占位页，已增加真实路径对应的空接口夹具并更新页面断言；新增长历史脚本曾有字符串转义错误，已修正并重跑通过。以上夹具只用于自动化交互及布局，不代表真实服务验收。

## 桌面人工复核与真实 smoke 限制

已查看 .cache/desktop-aiops-long.png，1440×900 三栏布局清晰，报告在中栏内部截断滚动，右侧来源与审计保持可访问，页面无溢出。

真实告警→诊断→报告→证据→案例 smoke **未执行**：本次检查 http://127.0.0.1:8000/health、http://127.0.0.1:5173/aiops、http://127.0.0.1:9093/-/ready 均不可达。没有创建虚构告警、日志或成功证据，没有用替身冒充真实 MCP/模型验收。根据用户允许的环境不可用分支记录此限制后归档。

## 最终评估

无未解决的 CRITICAL 实现问题。已执行门禁通过；真实集成 smoke 为已披露的环境限制。既有三处 vector_scope/vector_store/test_vector_store 未提交改动保持不动；本次不提交、不推送。
