## 背景

项目尚无应用代码。P01 建立最终目录、技术栈与安全配置边界，后续提案在这些边界内扩展。

## 目标与非目标

目标：最小应用可启动，配置行为可测试，依赖可复现，所有质量门禁可运行。
非目标：认证、聊天、知识库、AIOps、MCP 集成、数据库业务模型、基础设施部署。

## 技术栈

- 后端：Python >=3.10、FastAPI、Pydantic v2、uv、hatchling、src layout、SQLAlchemy 2 async、aiosqlite、Alembic、pytest、pytest-asyncio、Ruff、strict Pyright。pytest asyncio_mode=auto；Ruff line-length=100、target py310、B/E/F/I/UP。
- Agent/AI：LangChain 1.x create_agent、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters、httpx。除基础测试所需 httpx 外，业务集成与依赖安装由后续提案负责；P01 不宣称这些能力已实现。
- 前端：Vue 3.5、Vite 6、TypeScript 5.6 strict，开启 exactOptionalPropertyTypes、noUncheckedIndexedAccess、isolatedModules，ES2022/Bundler resolution；Pinia 3、Vue Router 4、Vitest 2、marked、DOMPurify、lucide-vue-next。
- 仓库：npm workspaces、OpenSpec spec-driven workflow、VitePress 文档、Conventional Commits。

## 决策

### 目录与包

最终目录为 apps/backend、apps/frontend、packages/api-contracts、config、infra、scripts、openspec、docs。后端只从 super_ai 导入，包位于 apps/backend/src/super_ai；hatchling 安装包，禁止 src.super_ai。共享包只导出 HealthResponse 等 foundation 类型。

### 最小应用与依赖注入

FastAPI 暴露 create_app 工厂及 GET /health，返回 {"status":"ok"}。工厂接受可选配置对象，通过应用状态及依赖函数提供配置；模块导入不读配置、不创建数据库引擎、不访问网络、不连接 SQLite、Milvus、LLM、MCP。P01 不创建数据库会话或迁移业务。

### 配置与安全

只提交 config/project.template.json 和 config/user.project.template.json；所有 key/secret/password 值为空。默认读取仓库 config/project.json，然后以可缺省的 user.project.json 覆盖：对象递归合并，标量、数组、null 整体替换；不修改原对象。缺少基础配置、非法 JSON 或非对象根节点均给出明确错误，不回退环境变量。配置目录可显式传入测试，应用不读取 OS 环境变量作为项目配置。

前端 Vite 在 Node 构建阶段读取同样的本地 JSON 合并规则，然后逐项构造公开对象，只允许 frontend.title、frontend.apiBaseUrl，以及 analytics.public=true 时的 analytics.key。配置值类型不符则拒绝构建。业务 config.ts 只接收 __PUBLIC_CONFIG__，禁止直接导入完整 JSON。LLM、CLS、MCP、MinIO 和任意未允许字段不会注入，新增 frontend 私密字段也不会因对象展开泄漏。P06 只增加 LLM typed validation/provider，不另建配置读取通道。

测试使用临时配置目录。sentinel 构建测试在临时目录复制前端源码和工具配置，复用已安装依赖，使用临时本地配置和独立输出目录；扫描所有构建产物，确认私密 sentinel 不存在、允许的公开 sentinel 存在，不覆盖开发者配置。

桌面与文档服务器验收也使用临时副本及临时 JSON，不读取开发者真实配置。两个开发服务器均显式拒绝 config 目录访问，并以 /@fs/ 请求回归确认 403。桌面测试使用本机 Edge 与 Playwright，截图不包含开发者配置值。

### 工程边界

tenant 是未来所有租户资源的隔离边界；未来由可信认证上下文提供 tenant_id，禁止由客户端参数直接认定身份，P01 不实现租户或认证。未来 MCP 必须连接真实官方服务，不以 mock 冒充验收成功。官方 CLS MCP Server 与前后端均运行在主机。

Compose 最终只托管 etcd、MinIO、Milvus、Attu、Alertmanager；P01 只建 infra 说明，不创建 app.Dockerfile、project.compose.json 或应用 Compose 服务。

### 方案取舍

采用显式双文件深合并及公开字段投影，满足用户指定边界；不采用环境变量覆盖，不把完整配置传给浏览器。AI 依赖只锁定选型而不提前集成，避免 P01 引入外部服务连接。暂不搭建复杂插件、认证或数据库抽象。

## 质量与验收

生成 package/pyproject 后先执行根 npm install 与 backend uv sync，提交两份锁文件。先为配置、健康接口、导入安全、仓库结构及前端白名单写失败测试，再实现。根 npm scripts 统一调用 contracts/frontend/docs 门禁。桌面 Web 在 1440x900 检查标题、骨架说明、布局和控制台；不以移动端替代。

必须通过 openspec validate --all；backend uv run ruff check .、uv run pyright、uv run pytest；contracts typecheck/test；frontend typecheck/test/build；sentinel 构建扫描；docs build；git diff --check。发现问题先修复重跑，再生成中文验证报告、同步 delta specs 并归档。

## 风险与迁移

这是从零项目，无历史迁移，不设计 filter-repo 或 force push。本机配置从模板复制且保持 ignored；不暂存。父级 Git 仓库中的其他项目不属于本提案。依赖版本兼容性以安装、类型检查和构建结果验证，不以工具已安装替代。
