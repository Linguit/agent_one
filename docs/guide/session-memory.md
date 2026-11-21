# 会话记忆模式

P17 为每个会话独立保存记忆策略与摘要。压缩仅改变提供给模型的上下文，完整消息仍可通过会话详情查看。

| 模式 | 自动触发条件 |
| --- | --- |
| `every_30_turns`（默认） | 下次发送前已有 30 个未压缩完整 user/assistant turn |
| `context_70_percent` | 候选上下文达到所选模型窗口的 70% |
| `manual` | 不自动压缩，通过 API 显式执行 |

`PUT /chat/sessions/{id}/memory` 接受 `{"memoryMode":"manual"}`；`POST /chat/sessions/{id}/memory:compact` 执行压缩。两者返回刷新后的 session。全部操作由登录用户的 owner scope 限制。前端 client/store 已支持更新与压缩，composer 入口由 P19 提供。

session 返回 `memoryMode`、`memorySummary`、`contextTokens`、`contextWindowTokens`、`contextUsagePercent`、`compactedMessageCount`、`lastCompactedAt` 和 `canCompact`。用量按当前 Prompt/Skill catalog、摘要和未压缩消息重新估算，不包含已经压缩的原始消息。Skill 正文仍按需加载；加载后调用模型前再次检查预算。

自动压缩在新用户消息写入前完成。边界停在最后一个完整配对的 assistant，末尾未回答消息保留；失败问题不计 turn，也不会永久阻断后续压缩。摘要标注消息范围和来源 ID，生成失败、空摘要或无缩减时回滚。

候选预算达到 95% 时返回 `CHAT_CONTEXT_LIMIT_REACHED`，提示手动压缩，且不保存候选 user 消息。自动压缩后仍达到上限也会回滚。流内模型调用达到上限时使用相同错误码发送 SSE error。token 是 LangChain 的近似估算值，5% 余量不代表精确 tokenizer 保证。

项目配置必须在 `modelCapabilities` 为所选对话模型提供正整数 `contextWindowTokens`。缺失或无效返回 `CHAT_MODEL_CAPABILITY_INVALID`，不使用猜测窗口。升级部署前在后端执行 `uv run alembic upgrade head`；0009 为既有会话填入默认状态。降级移除记忆字段而保留完整消息。

SQLite 写事务覆盖预算检查、摘要更新和消息写入，保证失败回滚；压缩期间会持有写锁，受现有模型 timeout 限制。
