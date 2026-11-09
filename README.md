# Super AI 安全工程基础

当前仅提供 P01 骨架：FastAPI `/health`、Vue 桌面页面、共享健康响应类型、本地配置加载及质量命令。
认证、聊天、知识库、AIOps、MCP 尚未实现。完整技术栈及贡献边界见 [项目指南](AGENTS.md)。

## 环境与安装

需要 Git、Python >=3.10、uv、Node >=20.19、npm >=10、OpenSpec CLI 1.5.0。Docker 不参与 P01 应用启动；后续基础设施使用 Docker Engine/Desktop 与 Compose 插件。

```powershell
npm install
cd apps/backend
uv sync
cd ../..
```

复现已有锁文件使用 npm ci、uv sync --locked。后端使用 hatchling 和 src layout，无需设置 PYTHONPATH。

## 本机配置

第一次启动或构建前，在根目录执行（仅在目标不存在时复制）：

```powershell
if (!(Test-Path config/project.json)) { Copy-Item config/project.template.json config/project.json }
if (!(Test-Path config/user.project.json)) { Copy-Item config/user.project.template.json config/user.project.json }
```

两份真实配置均被 Git 忽略，不能暂存。应用先读取 project.json，再递归合并 user.project.json；不以 OS 环境变量覆盖。用户文件可缺省。模板里的凭据均为空。
前端只接收标题、API 基址与显式 public=true 的 analytics key。当前没有 API 调用、analytics 上报或外部服务连接。

## 启动

后端（在 apps/backend）：

```powershell
uv run uvicorn super_ai.main:create_app --factory --host 127.0.0.1 --port 8000
```

访问 `http://127.0.0.1:8000/health` 得到 `{"status":"ok"}`。
另开终端在根目录运行 `npm run frontend:dev`，按终端输出地址访问桌面骨架。文档使用 `npm run docs:dev`。

## 验证

在 apps/backend：

```powershell
uv run ruff check .
uv run pyright
uv run pytest
```

在根目录：

```powershell
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
openspec validate --all
git diff --check
```

测试使用临时配置。安全脚本分别构建公开 analytics 开/关两种情况，扫描所有产物中的私密 sentinel，不覆盖本机配置。
桌面验收以 1440x900 检查标题、三张范围卡片、布局和控制台；页面不展示未实现功能入口。

## 目录与协作

- apps/backend：Python 包与后端测试。
- apps/frontend：桌面 Web 与公开配置构建代码。
- packages/api-contracts：最小共享类型。
- config：空凭据模板和 ignored 本机配置。
- infra：最终基础设施边界说明。
- scripts：工程及构建安全检查。
- openspec：简体中文规范与变更生命周期记录。
- docs：VitePress 文档。

提交信息遵循 Conventional Commits。全部门禁通过后同步规范并归档。基础设施限制见 [infra 说明](infra/README.md)。

固定开发工具链的审计告警和处置边界见 [依赖检查记录](docs/dependency-notes.md)。桌面和文档安全脚本使用临时配置，浏览器验收需要本机 Microsoft Edge。
