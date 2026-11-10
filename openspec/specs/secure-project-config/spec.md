# secure-project-config 规范

## Purpose

本规范定义安全单仓库第一阶段的工程契约，固定目录、技术栈、配置读取与公开投影、安全测试和质量门禁，确保后续产品功能在明确边界内演进，并通过可重复执行的验证防止凭据泄漏、导入副作用及规范漂移。

## Requirements

### Requirement: 本地 JSON 配置递归合并
应用 MUST 只读取本地 project.json 并以 user.project.json 递归覆盖，对象递归合并，数组、标量、null 整体替换，不修改输入；MUST 不以 OS 环境变量覆盖项目配置。缺少基础文件、非法 JSON 或非对象根节点 MUST 明确报错；缺少用户文件 MUST 视为空覆盖。测试 MUST 显式注入临时配置。

#### Scenario: 嵌套覆盖和环境变量隔离
- **WHEN** 基础配置有嵌套字段，用户配置只覆盖其中一个字段，环境变量含同名设置
- **THEN** 用户字段覆盖，其他基础字段保留，环境变量不参与结果

#### Scenario: 无效或缺少配置
- **WHEN** 基础文件缺失或任一文件不是合法 JSON 对象
- **THEN** 加载失败并提供不包含配置值的明确错误

### Requirement: 前端公开配置白名单
前端 MUST 不导入完整本地 JSON；Vite MUST 仅注入 frontend.title、frontend.apiBaseUrl 和 analytics.public=true 时的 analytics.key。LLM、CLS、MCP、MinIO 和其他字段 MUST 不进入浏览器 bundle。

#### Scenario: 私密哨兵构建
- **WHEN** 临时配置包含各类私密 sentinel、未知 frontend 字段和允许的公开 analytics key
- **THEN** 构建产物中不存在私密 sentinel，存在允许的公开字段，关闭 public 后 analytics key 不暴露

#### Scenario: 开发服务器拒绝配置读取
- **WHEN** 在临时副本中启动前端或文档开发服务器并请求两份本地配置
- **THEN** 请求返回 403，桌面与文档测试均不读取开发者真实配置

### Requirement: 凭据模板与导入安全
版本控制 MUST 只允许提交两份配置模板且其 key/secret/password 为空；MUST 忽略真实配置、环境文件、IDE 文件、虚拟环境、依赖、构建物、缓存、SQLite 和日志。导入模块期间 MUST 不读取本地配置或连接 SQLite、Milvus、LLM、MCP。

#### Scenario: 无服务导入
- **WHEN** 禁止文件配置读取和外部连接后导入全部后端模块
- **THEN** 导入成功且未创建数据库文件或客户端连接

#### Scenario: Git 忽略本地文件
- **WHEN** 检查本地配置和生成目录的忽略规则
- **THEN** git check-ignore 命中，本地配置不被暂存，模板仍可跟踪

### Requirement: 本地配置模板覆盖最终配置分区
基础模板 MUST 包含 app、backend、frontend、llm、modelCapabilities、vectorStore、mcp、clsMcpServer、prometheusAlerts、clsLogUpload 与 aiopsDemo。aiopsDemo MUST 包含 backendBaseUrl、email、displayName、password、pollIntervalSeconds 和 indexWaitSeconds。

#### Scenario: 初始化本地文件
- **WHEN** 从模板初始化缺少的本地文件
- **THEN** 已有本地文件保留，实际凭据仅填入被忽略的用户配置
