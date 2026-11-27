## Context

已有告警、持久诊断/后台 job、SSE、证据链、结构化案例和 owner 知识文档 API。现有 /aiops 仍为占位页面。

## Goals / Non-Goals

目标：中文三栏桌面控制台，以持久 API 为事实来源，呈现安全报告与 provenance。
非目标：新增 context 合同、自动重新订阅、自动修复、伪造真实 MCP 验收。

## Decisions

- 复用 Vue/Pinia、认证 request/stream 与安全 Markdown；typed aiopsClient 隔离路径。
- store 管理 history、activeAlerts、cases、activeTask、liveEvents、evidenceChain；选择或断流后读取 detail、history、chain、cases。SSE 只追加 timeline，不推断任务成功。
- generation 与 AbortController 防止跨 owner、切换任务和卸载后的旧响应污染；断流不重订阅，提供显式持久状态刷新。
- 三栏使用 minmax(0,1fr)、min-height:0 与独立 overflow；报告与 timeline 在中栏分区内滚。
- 对开放对象只提取已知可读字段，禁止 JSON.stringify 产品展示；工具详情默认折叠。报告移除原始 JSON 块，保留证据 ID 与安全 Markdown。
- 案例通过 owner 知识库列表解析并打开 document 深链接，不信任客户端 owner。
- 不新增依赖、配置或导入副作用，不改变基础设施及凭据边界。

## Risks / Trade-offs

- 真实依赖不可用 → 展示错误并记录 smoke 未执行；替身仅用于自动化交互测试。
- 断流期间任务继续 → 显式刷新持久记录，不虚构自动恢复 SSE。
- 开放证据对象 → 仅呈现白名单摘要与来源/审计/关联 ID，保留服务端原始数据。
