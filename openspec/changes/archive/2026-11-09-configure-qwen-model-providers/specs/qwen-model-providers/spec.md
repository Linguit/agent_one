## ADDED Requirements

### Requirement: 配置与可注入对话
后端 MUST 基于合并后的本地 JSON 校验 llm 和 modelCapabilities，并提供 LlmProvider 与 QwenOpenAIProvider。对话 MUST 使用 ChatOpenAI，默认模型为 qwen3.7-max，temperature 为 0.2、timeout 为 120 秒、retries 为 2，模型画像提供 contextWindowTokens。

#### Scenario: 显式创建提供者
- **WHEN** 使用有效模型配置创建提供者
- **THEN** 对话请求采用已校验的参数和相应模型画像，导入阶段无外部资源初始化

#### Scenario: 配置缺少必要字段
- **WHEN** 模型配置缺少凭据、端点或所选模型画像
- **THEN** 安全报错且不显示配置值

### Requirement: 原始字符串嵌入和顺序
嵌入 MUST 使用 OpenAIEmbeddings、text-embedding-v4、1024 维、关闭上下文长度检查，每批最多十条。

#### Scenario: 嵌入超过十条文本
- **WHEN** 嵌入超过十条文本
- **THEN** 依次提交原始字符串批次，向量顺序与输入一致

### Requirement: 独立重排与安全探测
重排 MUST 通过可注入的 HTTP 客户端访问 qwen3-vl-rerank，返回真实索引与分数。异步就绪探测 MUST 发出最小请求并返回 provider、model、baseUrl、latency。错误 MUST 保护所有 API key。

#### Scenario: 三种能力的最小探测
- **WHEN** 探测指定能力
- **THEN** 发出该能力的最小请求，成功时返回测量结果，失败时报告脱敏错误

#### Scenario: 重排服务出现临时或永久故障
- **WHEN** 重排服务超时、限流或拒绝请求
- **THEN** 按配置重试临时故障，永久故障或重试耗尽时安全失败
