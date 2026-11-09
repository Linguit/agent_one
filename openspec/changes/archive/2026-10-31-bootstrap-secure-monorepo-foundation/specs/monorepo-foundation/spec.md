## ADDED Requirements

### Requirement: 最终目录和包边界
项目 MUST 建立 apps/backend、apps/frontend、packages/api-contracts、config、infra、scripts、openspec、docs；后端包 MUST 位于 apps/backend/src/super_ai，只允许 super_ai 包导入，禁止 src.super_ai。

#### Scenario: 安装后导入
- **WHEN** 完成 uv sync 并从仓库外目录导入 super_ai
- **THEN** 包可以从已安装的 src layout 解析，代码不依赖工作目录或 src.super_ai

### Requirement: 最小应用与工程技术栈
项目 MUST 按设计锁定后端、Agent/AI、前端和仓库技术栈，提交 uv.lock 和 package-lock.json，提供 FastAPI create_app、GET /health、Vue 桌面骨架和最小共享类型入口；MUST 不实现产品功能。

#### Scenario: 健康接口与桌面骨架
- **WHEN** 使用临时配置创建应用并访问 /health，构建桌面前端
- **THEN** 接口返回 200 和 status=ok，桌面页面展示标题及骨架范围，无认证或聊天功能

### Requirement: 基础设施与后续能力边界
项目指南 MUST 明确 Compose 仅托管 etcd、MinIO、Milvus、Attu、Alertmanager；后端、前端和官方 CLS MCP Server 在主机运行。P01 MUST 仅创建说明，不创建应用 Dockerfile 或应用 Compose。指南 MUST 记录 tenant 可信上下文隔离与真实 MCP 验收约束。

#### Scenario: 检查基础设施目录
- **WHEN** 检查 infra 和项目指南
- **THEN** 存在边界说明且不存在 app.Dockerfile、project.compose.json 或应用 Compose 服务
