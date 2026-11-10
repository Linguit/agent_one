## Context

P01 已提供通用本地 JSON 加载器。Repository 与共享契约已具备，模型调用使用独立的后端 Protocol。

## Goals / Non-Goals

在显式创建时校验合并后的模型配置，提供对话、嵌入、重排和就绪探测。业务路由和远端验收由使用方按需执行。

## Decisions

- 对话和嵌入使用 langchain-openai，嵌入通过 OpenAIEmbeddings 按最多十条原始字符串分批。
- 百炼原生 HTTP 重排支持独立注入客户端，超时、限流和服务端暂时错误可重试。
- 创建者管理 HTTP 客户端生命周期。注入客户端可用于 MockTransport 测试。
- 外部错误在边界转换为安全错误，响应正文和原始异常链不向调用方传播。

## Risks / Trade-offs

模型可用性与地域和账号有关。模板提供北京端点，真实服务通过手动探测验证。
