# 会话记忆策略

## Purpose

为每个会话提供独立的上下文压缩策略、可追溯历史摘要和模型窗口预算防护，在保留完整消息记录的同时保证 owner 隔离与失败回滚。

## Requirements

### Requirement: 独立记忆状态与管理 API
系统 SHALL 按 owner 和会话保存 memory_mode、memory_summary、compacted_message_count、context_tokens、last_compacted_at。模式 SHALL 为 every_30_turns、context_70_percent、manual。session DTO SHALL 返回 memoryMode、memorySummary、contextTokens、contextWindowTokens、contextUsagePercent、compactedMessageCount、lastCompactedAt、canCompact。PUT /chat/sessions/{id}/memory 与 POST /chat/sessions/{id}/memory:compact SHALL 返回刷新状态；前端 store SHALL 支持两项操作。

#### Scenario: 模式与隔离
- **WHEN** owner 更新一个会话模式，其他用户访问该会话
- **THEN** 仅目标会话改变；其他用户收到 AUTH_FORBIDDEN 且无法触发模型调用

### Requirement: 压缩触发与完整边界
系统 SHALL 在下一条用户消息写入前按模式判断触发：every_30_turns 累计 30 个未压缩完整 turn，context_70_percent 候选预算达到 70%，manual 仅显式 API。压缩 SHALL 以最后一个完整配对的 assistant 为边界并保留尾部未完成消息；边界前失败问题 SHALL 作为未决资料进入摘要，不计完整 turn。

#### Scenario: 29 与 30 turn
- **WHEN** every_30_turns 会话分别已有 29 与 30 个完整 turn 并发送新消息
- **THEN** 前者不压缩，后者压缩；不完整 turn 不计数

#### Scenario: 69 与 70 百分比
- **WHEN** context_70_percent 候选预算分别为窗口 69% 与 70%
- **THEN** 前者不压缩，后者尝试压缩；manual 两者都不自动压缩

#### Scenario: 失败 turn 与末尾未回答消息
- **WHEN** 历史中出现失败 user，后面存在完整配对，末尾仍有未回答 user
- **THEN** 失败 user 不计数且不阻断后续完整配对计数，压缩边界不覆盖末尾未回答消息

### Requirement: 可追溯摘要和完整历史
系统 SHALL 使用 LLM 生成带来源范围的摘要，组装摘要、未压缩消息、当前 Prompt/Skill catalog。压缩 SHALL 不删除或改写 chat_messages，失败 SHALL 回滚全部记忆变化。

#### Scenario: 历史与失败回滚
- **WHEN** 压缩成功或模型失败、空输出、无缩减
- **THEN** 成功时仅更新记忆字段并保留全部原消息；失败时记忆和消息均保持原状

#### Scenario: 长历史分块摘要
- **WHEN** 全部待压缩消息无法安全放入一次摘要请求
- **THEN** 系统分块汇总并在每次请求前检查 95% 上限，全部分块成功后才提交摘要与边界

### Requirement: 写入前预算与配置错误
系统 SHALL 通过纯函数 estimate_context_tokens 调用 LangChain count_tokens_approximately；候选预算达到 95% SHALL 返回 CHAT_CONTEXT_LIMIT_REACHED 并提示手动压缩，在新 user message 持久化与对话模型调用之前拒绝。HTTP/SSE SHALL 使用共享错误。模型 capability 缺失 SHALL 明确配置错误而不猜测窗口。

#### Scenario: 95 百分比拒绝
- **WHEN** 自动压缩后或 manual 候选上下文达到 95%
- **THEN** 返回共享错误且不写入候选消息，不调用对话模型

#### Scenario: capability 缺失
- **WHEN** 所选模型缺少有效 contextWindowTokens
- **THEN** 返回明确配置错误，且不保存新消息

#### Scenario: 流内预算增长
- **WHEN** 已建立 SSE 流，在下一次模型调用前预算达到 95%
- **THEN** 不调用该次模型并发送相同 CHAT_CONTEXT_LIMIT_REACHED 错误
