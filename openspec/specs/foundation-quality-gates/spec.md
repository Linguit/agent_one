# foundation-quality-gates 规范

## Purpose

本规范定义安全单仓库第一阶段的工程契约，固定目录、技术栈、配置读取与公开投影、安全测试和质量门禁，确保后续产品功能在明确边界内演进，并通过可重复执行的验证防止凭据泄漏、导入副作用及规范漂移。

## Requirements

### Requirement: 可重复执行的质量命令
项目 MUST 提供 backend pytest/Ruff/strict Pyright、contracts typecheck/test、frontend dev/typecheck/test/build、docs 命令和根工作区脚本。pytest MUST 使用 asyncio_mode=auto；Ruff MUST 使用 100、py310、B/E/F/I/UP；TypeScript MUST 使用设计指定的严格配置。

#### Scenario: 执行质量门禁
- **WHEN** 安装根 npm 依赖和 backend uv 依赖后运行验收命令
- **THEN** 静态检查、测试、前端构建、文档构建和 git diff --check 全部通过

### Requirement: 测试覆盖与归档证据
项目 MUST 测试目录、导入、scripts、ignore、import-safety、配置合并及公开白名单，并执行 sentinel 构建扫描和桌面前端验收。所有门禁通过后 MUST 同步 delta specs 并归档，文档正文 MUST 使用简体中文，规范解析结构标记保留 CLI 要求格式。

#### Scenario: 验证后归档
- **WHEN** 任务已完成且中文验证报告记录所有门禁通过
- **THEN** 正式规范包含本次新增要求，变更归档，未实现的产品能力不被宣称已完成
