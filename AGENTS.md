# 项目指南

## 范围与目录

本项目当前只有 P01 安全工程基础，不得声称认证、聊天、知识库、AIOps 或 MCP 已实现。
最终目录：apps/backend、apps/frontend、packages/api-contracts、config、infra、scripts、openspec、docs。
后端包固定 apps/backend/src/super_ai；前端以桌面 Web 为验收目标；共享包仅存放接口契约。

## 技术栈

- 后端：Python >=3.10、FastAPI、Pydantic v2、uv、hatchling、src layout、SQLAlchemy 2 async、aiosqlite、Alembic、pytest、pytest-asyncio、Ruff、strict Pyright。pytest 使用 asyncio_mode=auto；Ruff line-length=100、target py310、规则 B/E/F/I/UP。
- Agent/AI：LangChain 1.x create_agent、LangGraph、langchain-openai、langchain-mcp-adapters、MCP、pymilvus 3、rank-bm25、pypdf、langchain-text-splitters、httpx；这些能力由后续提案实现。httpx 在 P01 仅用于接口测试。
- 前端：Vue 3.5、Vite 6、TypeScript 5.6 strict，开启 exactOptionalPropertyTypes、noUncheckedIndexedAccess、isolatedModules，target ES2022、moduleResolution Bundler；Pinia 3、Vue Router 4、Vitest 2、marked、DOMPurify、lucide-vue-next。
- 仓库：npm workspaces、OpenSpec spec-driven workflow、VitePress 文档、Conventional Commits。Node >=20.19，npm >=10；锁文件是可复现安装依据。

## 安装、启动与质量命令

根目录执行 npm install（后续复现可 npm ci），apps/backend 执行 uv sync（后续 uv sync --locked）。
启动前将 config 下两份模板复制为对应本机 JSON；不得覆盖已有配置。
后端：在 apps/backend 执行 uv run uvicorn super_ai.main:create_app --factory --host 127.0.0.1 --port 8000。
前端：根目录 npm run frontend:dev；文档 npm run docs:dev。

验收必须执行：

```text
openspec validate --all
cd apps/backend
uv run ruff check .
uv run pyright
uv run pytest
cd ../..
npm run contracts:typecheck
npm run contracts:test
npm run frontend:typecheck
npm run frontend:test
npm run frontend:build
npm run frontend:security
npm run frontend:desktop
npm run foundation:test
npm run docs:build
npm run docs:security
git diff --check
```

## Python 导入和依赖注入

只允许 from super_ai...，禁止 src.super_ai。通过 uv 安装包，不用 sys.path 注入或 PYTHONPATH 绕过安装。
模块导入期间不得读取本机配置或连接 SQLite、Milvus、LLM、MCP，不创建引擎或客户端。
资源在应用生命周期中显式创建/关闭，通过 Depends、应用工厂参数或 provider 注入；测试使用临时配置和显式替身。P01 不创建外部服务资源。

## 配置与凭据

只提交 config/project.template.json 和 config/user.project.template.json，所有 key/secret/password 为空。
真实 project.json、user.project.json 必须 ignored 且不能 stage。禁止提交 .env、凭据、SQLite、日志、缓存、构建物。
通用 project_config.py 读取 project.json 后以 user.project.json 递归深合并；对象递归，其他值整体替换。用户文件可缺省，基础文件必须存在。应用不读取 OS 环境变量作为项目配置。
P06 只能新增 LLM typed validation/provider，不能另起配置读取机制。
前端禁止 import 完整 JSON。Vite 只向 config.ts 注入 frontend.title、frontend.apiBaseUrl 和 analytics.public=true 的 analytics.key；其余值不允许进入 bundle，禁止展开完整配置对象。
LLM、CLS、MCP、MinIO secret 永远不进入浏览器；错误和测试输出不打印配置值。
新增公开字段必须同步白名单、规范与 sentinel 测试。测试不得依赖开发者真实配置。

## tenant 与真实 MCP

后续租户资源必须按可信认证上下文中的 tenant_id 隔离，禁止信任客户端自报 tenant 或跨租户查询。P01 不实现租户、认证。
后续 MCP 验收必须连接真实服务；官方 CLS MCP Server 在主机运行。单元测试替身不能冒充真实 MCP 验收通过，不以模拟能力宣称功能完成。

## 基础设施边界

Compose 最终仅托管 etcd、MinIO、Milvus、Attu、Alertmanager；后端、前端、官方 CLS MCP Server 均在主机运行。
P01 仅建立 infra 目录与说明，不创建 app.Dockerfile、project.compose.json 或应用 Compose 服务。

## OpenSpec、文档与验收

使用 spec-driven，依次提案、实施、验证、同步 delta specs、归档；文档正文使用简体中文，解析所需 Requirement/Scenario/ADDED 等结构标记保留。
发现验证问题先修复重验，全部门禁通过才归档。遵循 Conventional Commits，不自动提交或推送。
桌面前端以 1440x900 检查标题、布局、溢出和控制台错误；测试与构建不能代替桌面浏览器检查。
从零项目不设计 filter-repo/force push；不得修改父级仓库中的其他项目。
