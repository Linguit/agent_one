## ADDED Requirements

### Requirement: 本地配置模板覆盖最终配置分区
基础模板 MUST 包含 app、backend、frontend、llm、modelCapabilities、vectorStore、mcp、clsMcpServer、prometheusAlerts、clsLogUpload 与 aiopsDemo。aiopsDemo MUST 包含 backendBaseUrl、email、displayName、password、pollIntervalSeconds 和 indexWaitSeconds。

#### Scenario: 初始化本地文件
- **WHEN** 从模板初始化缺少的本地文件
- **THEN** 已有本地文件保留，实际凭据仅填入被忽略的用户配置
