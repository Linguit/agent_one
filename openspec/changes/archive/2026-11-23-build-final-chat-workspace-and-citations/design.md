## Context

路由尚使用占位组件。chatStore、configurationStore、认证传输和共享 SSE 已存在；后端检索输出含排序证据，但聊天 reference.source 和持久化元数据目前只保留 title/uri，需要同时补齐。

## Goals / Non-Goals

目标：接入现有服务，完成 1440×900 桌面聊天与可追溯引用。非目标：新增模型、认证机制或基础设施；不覆盖既有未提交变更。

## Decisions

- 在 WorkspaceLayout 左栏挂载会话管理，ChatView 只包含会话正文、composer 和配置右栏。Grid 限定高度，消息区域独立滚动。
- 继续使用 Pinia 与现有认证客户端；领域状态不写 localStorage。配置维持独立配置 store，并由聊天工作区组合使用。
- 当前会话 ID 写入 URL 的 session 查询参数；刷新时重新读取对应会话及其工具审计，保持刷新恢复且不缓存领域数据。
- for-await 顺序消费共享 SSE，按 Unicode 字符更新正文后 await setTimeout(28)，然后才读取后续事件；不用 requestAnimationFrame 或独立队列。complete 后重新读取服务端历史及工具审计。
- 新回合初始化空引用与工具状态；历史按各 assistant metadata 渲染。引用最多五条，按 rerankRank、score 排序；缺失阶段显示“未命中”。
- marked 自定义 renderer 禁用 raw HTML，DOMPurify 再过滤生成 HTML。工具参数及 raw JSON 不渲染，只展示工具名、状态和服务端安全摘要。
- 配置与记忆操作保留输入并显示可恢复错误；会话切换、删除及新建均走真实接口。

## Risks / Trade-offs

- 顺序延迟会推迟工具与完成事件 → 明确该时序为本次契约，并用 fake timer 验证。
- 真实模型、知识索引或 MCP 服务不可用 → 如实记录阻塞，不用测试替身冒充 smoke，不提前归档。
- 引用 metadata 可能含复杂对象 → 用文本逐字段展示，不执行 HTML，不展示工具 raw JSON。

## Migration Plan

无数据库迁移。发布前后端现有契约兼容；回退前端路由即可回滚。
