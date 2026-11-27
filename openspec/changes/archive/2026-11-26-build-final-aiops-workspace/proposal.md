## Why

持久诊断、证据报告与案例服务需要统一的中文桌面入口，使运维人员可以从真实告警追踪诊断过程、结论及来源。

## What Changes

- 新增 /aiops 三栏控制台，独立内滚报告、实时过程和证据来源。
- typed client 与 Pinia 消费真实告警、诊断、持久 SSE、后台任务取消及案例 API。
- 断流读取持久状态恢复，区分诊断与后台任务状态，不自动重订阅。
- 安全 Markdown 与结构化证据/案例展示，不使用假数据或原始 JSON 产品界面。

## Capabilities

### New Capabilities
- `final-aiops-workspace`: 中文桌面诊断工作区及持久状态交互。

### Modified Capabilities

无。

## Impact

影响 apps/frontend、相关合同呈现及诊断报告的可读输出；复用既有身份、持久诊断、告警、MCP 和知识文档 API。不增加 context 输入，不实现自动修复，不提交或推送。
