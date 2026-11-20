# 流式 Agent 聊天与工具审计

## Purpose

支持会话所有者与自主选用工具的模型进行持久化流式对话，并查询每次工具调用的审计记录。

## Requirements

### Requirement: 会话流与自主工具选择

系统 MUST 在 `POST /chat/sessions/{sessionId}/messages:stream` 接收 `content` 和可选 `metadata`，先校验会话归属并按会话消息规则持久化用户消息，随后调用绑定 `knowledge_retrieval` 和 `get_current_time` 的 Agent，由模型选择工具。

#### Scenario: 模型直接应答

- **WHEN** 模型直接生成回答
- **THEN** 系统不调用知识检索

#### Scenario: 模型选择工具

- **WHEN** 模型选择知识检索
- **THEN** 工具仅能访问认证租户范围内的知识资源

### Requirement: 流契约与消息持久化

系统 MUST 通过共享 SSE 契约发送 `content.delta`、可选的 `reasoning.delta`、`tool.call`、`reference.source` 以及 `complete` 或 `error`，并提供稳定事件 ID 与从 1 开始的递增序号。最终正文按 Unicode 码点输出，其他事件保持完整。推理事件仅来自真实模型输出。

#### Scenario: 成功完成

- **WHEN** Agent 成功返回最终答案
- **THEN** 系统一次性保存助手消息和本轮引用及审计 ID，并发送一次完成事件

#### Scenario: 本轮失败

- **WHEN** 工具或模型失败
- **THEN** 发送错误事件并保留用户消息，助手消息不落库

#### Scenario: 多轮与重载

- **WHEN** 开始下一轮或重载会话
- **THEN** 实时引用从空状态开始，历史引用来自各助手消息的元数据

### Requirement: 通用工具审计

系统 MUST 记录 owner、会话或诊断任务二选一的父资源、工具名、参数、状态、结果摘要或脱敏错误、开始和结束时间及耗时。`GET /chat/sessions/{id}/tool-call-audits` 仅向会话所属用户返回审计。

#### Scenario: 生命周期与归属

- **WHEN** 工具开始、成功或失败
- **THEN** 每次调用的 `started` 与其 `completed` 或 `failed` 事件使用同一持久审计 ID，所属用户方可读取会话审计

#### Scenario: 日志脱敏

- **WHEN** 记录工具结构化运行日志
- **THEN** 参数只记录键，且日志排除提示词、查询、参数值、工具输出和令牌
