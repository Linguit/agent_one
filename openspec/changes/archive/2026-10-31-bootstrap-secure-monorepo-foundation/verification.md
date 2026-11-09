# P01 验证报告

变更：bootstrap-secure-monorepo-foundation。日期：2026-10-31。流程：spec-driven。
依次使用 openspec-propose、openspec-apply-change、openspec-verify-change；本报告完成后同步正式规范，再使用 openspec-archive-change。

## 总体结论

| 维度 | 结果 |
| --- | --- |
| 完整性 | 实施及验证任务完成，8 项规范要求、11 个场景均有实现或明确边界证据；正式规范同步属于下一生命周期步骤 |
| 正确性 | 后端 9、契约 1、前端 5、工程 4 项自动化测试通过；两轮构建扫描与两组真实浏览器安全验收通过 |
| 一致性 | 实现符合技术栈、目录、配置、导入安全、tenant 和基础设施边界；未实现产品能力 |

源码阻塞问题为 0。独立只读审查提出的两项问题均已修复并回归，复核确认无剩余阻塞。已知开发依赖审计告警不等于源码问题已消除，详见下文限制。

## 要求与证据

| 规范要求 | 实现及验证证据 |
| --- | --- |
| 最终目录和包边界 | apps/backend/src/super_ai、hatchling 配置；test_all_modules_import_without_io 从临时工作目录导入；scripts/foundation.test.mjs 检查路径与禁止 src.super_ai |
| 最小应用与技术栈 | pyproject.toml、package.json、两份锁文件、AGENTS.md；create_app 和 /health 测试；Vue 三张基础卡片及范围说明 |
| 基础设施与后续边界 | infra/README.md、AGENTS.md；无应用 Dockerfile 或 Compose；tenant 与真实 MCP 只定义约束 |
| 本地 JSON 递归合并 | project_config.py 与前端构建辅助代码；对象递归、数组/null 替换、输入不变、缺省覆盖、无效 JSON、环境变量不参与等测试 |
| 前端公开白名单 | build/project-config.ts 逐项投影，config.ts 只接收公开对象；未知 frontend/LLM/CLS/MCP/MinIO 私密字段构建扫描；analytics 开关测试 |
| 凭据模板和导入安全 | 两份模板凭据为空；git check-ignore 验证真实配置和生成物；子进程禁止文件读取、socket、SQLite/SQLAlchemy 建连后导入全部模块 |
| 可重复质量命令 | 根 npm workspaces 与各包 scripts；pytest auto、Ruff 100/py310/B/E/F/I/UP、strict Pyright、TS 严格开关全部配置并实际运行 |
| 测试覆盖与归档证据 | tests、foundation 脚本、sentinel 脚本、Edge 1440x900 截图及本报告；归档后另记录同步和验证结果 |

## 最终门禁执行结果

环境：Windows、Python 3.12.4、Node 24.20.0。Python 3.10 为最低兼容目标，Pyright 按 3.10 检查；未宣称已执行所有 Python 小版本运行测试。

| 命令 | 结果 |
| --- | --- |
| 根 npm install / backend uv sync | 通过，按要求在生成清单后先执行，生成 package-lock.json 与 uv.lock |
| uv run ruff check . | 通过 |
| uv run pyright | 0 errors、0 warnings |
| uv run pytest | 9 passed |
| npm run contracts:typecheck | 通过 |
| npm run contracts:test | 1 passed |
| npm run frontend:typecheck | 通过，含 Vue 源码和 Node 构建配置 |
| npm run frontend:test | 5 passed |
| npm run frontend:build | 通过，Vite 6.4.5 |
| npm run frontend:security | 两轮各 3 个构建产物，7 个私密哨兵均未出现；公开标题、基址及 analytics 开关符合预期 |
| npm run foundation:test | 4 passed，覆盖目录/scripts/ignore/包边界及未跟踪文件空白 |
| npm run docs:build | 通过，VitePress 1.6.4 |
| npm run frontend:desktop | Edge 1440x900：标题、三张卡片、范围说明、无横向溢出、控制台无错误；临时两份配置请求均 403 |
| npm run docs:security | 临时文档首页 200，两份临时 JSON 请求均 403 |
| openspec validate --all | 归档前变更验证 1 passed、0 failed；正式规范同步后另行复验 |
| git diff --check | 通过；另以 foundation 检查所有未跟踪文件，避免父级空 diff 掩盖新增文件空白问题 |

真实本机配置只为显式启动/build 从模板复制，保持 ignored，未暂存。单元、安全构建、桌面及文档测试均使用临时 JSON，未读取开发者真实值。

## 发现问题、修复和重新验证

1. 预期失败阶段：后端缺少 super_ai.main，前端缺少公开配置模块，工程检查缺少指南/模板；实现后通过对应测试。
2. Vitest 2 引入 Vite 5，与应用 Vite 6 插件类型冲突。根 overrides 统一到 Vite 6.4.5，重新解析锁文件后 typecheck、test、build、文档和浏览器验证通过，未用类型断言掩盖版本冲突。
3. 桌面浏览器发现 favicon 404，增加显式空 favicon，重验控制台无错误。
4. 独立复核发现桌面测试读取本机配置，改用 temporary-project.mjs 创建临时源码及配置，重新运行通过。
5. 独立复核发现文档服务器可通过 /@fs/ 读取配置。使用临时配置复现 HTTP 200，增加 fs deny 后重验两份 JSON 均 403。浏览器完整加载后关闭服务，避免仅请求 HTML 造成依赖预构建尚未结束时关闭挂起。

## 已知限制与工程裁定

- 完整 npm audit 仍有 10 项开发工具链告警（8 moderate、2 critical），包括指定 Vitest 2 及其依赖；生产依赖 npm audit --omit=dev 为 0。未强制跨大版本升级，未宣称依赖零漏洞。只使用本地 vitest run，不启用测试 UI/API；后续依赖升级提案需评估修复。记录见 docs/dependency-notes.md。
- Agent/AI 依赖选型已写入设计和指南，业务接入由后续提案负责；P01 不建立 SQLite 表、Milvus、LLM 或 MCP 连接。
- 内置浏览器工具初始化失败，改用现有 Edge 与 Playwright 验收，没有以单元测试替代真实桌面浏览器。截图位于 ignored 的 .cache/desktop-foundation.png，已人工查看布局。
- 当前 Git 根为父级 F:/agent；只修改 agent_again。没有提交、推送或历史清理。归档任务只核对前置条件，归档作为其后的生命周期动作执行。

## 规范同步与归档

三份 delta specs 已同步至 openspec/specs，对应新增 8 项要求及 11 个场景，无修改、删除或重命名既有要求。同步后 openspec validate --all 为 4 passed、0 failed，foundation 4 项检查及 git diff --check 再次通过。10/10 任务完成。

已执行 openspec archive bootstrap-secure-monorepo-foundation --yes --skip-specs，退出码 0；skip-specs 仅避免对已同步且比对一致的正式规范重复应用，并未跳过规范同步或验证。归档目录为 openspec/changes/archive/2026-10-31-bootstrap-secure-monorepo-foundation，保留 .openspec.yaml、提案、设计、任务、delta specs 与本报告。

CLI 对提案的简体中文“为什么/变更内容”标题产生非阻塞提示，其检查器只识别英文 Why/What Changes；对应内容均已提供，按用户要求保留中文标题。规范解析所需 Requirement/Scenario 等标记使用 CLI 格式。该提示不代表缺少需求或验证失败。

归档后复验：openspec validate --all 为 3 passed、0 failed；openspec list 无活动变更；foundation 4 项检查及 git diff --check 通过；归档文件齐全，三份正式规范与归档 delta 内容一致；两份真实配置不在暂存区。完整生命周期已完成。
