## 1. 工程契约与依赖

- [x] 1.1 建立最终目录、根与各 workspace package.json、backend pyproject 和严格质量配置；随即执行根 npm install、backend uv sync 并生成锁文件。
- [x] 1.2 编写目录、导入、scripts、ignore、配置及白名单失败测试，记录预期失败。

## 2. 最小应用与配置

- [x] 2.1 实现 super_ai/project_config.py 深合并与显式注入、create_app 和 /health，通过临时配置及导入安全测试。
- [x] 2.2 实现 contracts typed entrypoint 与 Vue 桌面骨架、Vite 公开字段投影；通过类型检查和单元测试。
- [x] 2.3 建立两份空凭据模板与 ignore；实现临时配置 sentinel 构建扫描，验证私密字段不进入 dist。

## 3. 指南与边界

- [x] 3.1 完成根 AGENTS.md、中文 README、workspace README、VitePress 与 infra/scripts 说明，记录完整技术栈、tenant、真实 MCP 和主机/Compose 边界。
- [x] 3.2 更新 openspec/config.yaml 的技术栈、工程约束和简体中文规则。

## 4. 验证与归档

- [x] 4.1 运行全部静态检查、测试、前端及文档构建、sentinel 扫描、桌面验收与 git diff --check；修复后重新验证。
- [x] 4.2 使用 openspec-verify-change 生成中文完整性、正确性、一致性报告，确认无阻塞问题。
- [x] 4.3 同步三份 delta specs，执行 OpenSpec 验证并确认归档前置条件。

所有任务完成后，使用 openspec-archive-change 归档并复查正式规范与归档状态；归档本身为生命周期动作，避免把自身归档后的动作设为归档前置任务。
