## Context

依赖已有会话存储、Agent streaming、Qwen modelCapabilities 与渐进式 Prompt/Skill assembly。所有操作使用可信 owner scope；模块导入不创建资源。

## Goals / Non-Goals

目标：每会话独立策略、完整历史保留、确定性预算边界、失败原子回滚。非目标：P19 composer 控件、外部记忆服务、向量记忆。

## Decisions

- 默认 every_30_turns；新用户消息写入前，在未压缩前缀中累计至少 30 个完整 user/assistant 配对时压缩。失败或孤立 user 不算完整 turn；边界为最后一个完整配对的 assistant，保留末尾未完成 turn。此前失败问题作为未决资料进入摘要，避免一次失败永久阻断后续压缩。
- context_70_percent 在候选上下文达到 70% 时先尝试压缩；manual 仅由显式 compact API 触发。自动压缩后重新估算，达到 95% 一律拒绝新消息，不持久化任何候选状态。
- 唯一纯函数 estimate_context_tokens 使用 LangChain count_tokens_approximately。估算包含当前 system Prompt/Skill catalog、旧摘要、未压缩消息和候选用户消息。工具迭代调用模型前再次检查 95%。
- LLM 摘要携带会话消息 sequence 范围与原消息 ID；摘要作为历史资料传入，不改写消息。拒绝空摘要、不完整响应和无缩减摘要。
- 长历史按消息分块，以 70% 为分块目标、95% 为每个摘要请求硬上限；多块累计生成同一摘要，任一块失败都不提交状态。单条消息无法安全放入摘要请求时明确拒绝，不越窗调用。
- SQLite 写事务串行化同会话预算、压缩和 append，失败回滚；DTO 读取时按当前 catalog 与 capability 刷新用量。capability 缺失返回明确配置错误，不猜窗口。
- HTTP 与 SSE 使用共享错误目录。stream 预检失败返回同一 HTTP 错误；已建立流中的预算错误使用同码 SSE error。
- 前端 client/store 复用现有 owner generation 与队列，操作后刷新服务端 session state。

## Risks / Trade-offs

- 近似估算存在误差 → 保留 5% 余量，模型每次调用前检查。
- 摘要 LLM 调用期间持有 SQLite 写事务，可能等待 → 模型既有 timeout 控制，优先保证事务一致性；后续可采用版本校验优化。
- 摘要可能丢失细节 → 完整历史始终可查询，摘要包含来源范围。

## Migration Plan

新增 0009 migration 为既有会话填默认模式、空摘要、零边界和用量；验证升级、降级、再次升级。降级仅删除记忆字段，保留消息。
