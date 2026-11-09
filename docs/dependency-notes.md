# 依赖检查记录

P01 使用指定的 Vue 3.5、Vite 6、TypeScript 5.6、Vitest 2。锁文件记录实际解析版本。

2026-10-31 检查结果：生产依赖 `npm audit --omit=dev` 为 0 项；完整审计为 10 项（8 moderate、2 critical），位于开发测试工具链，包括 Vitest 2、tinypool、@vitest/mocker、vue-tsc 等依赖链。

这些告警没有被消除，不能将本项目称为“依赖零漏洞”。本提案保留用户指定的 Vitest 2；部分修复需要升级其大版本，留待专门依赖升级提案评估。开发脚本只运行本地 `vitest run`，不启动 Vitest UI/API 服务器；Vite 与文档服务只监听 127.0.0.1，拒绝配置目录访问。限制暴露面不能代替升级修复，不要对不可信测试或代码运行工具链。

本次将 Vitest/VitePress 内嵌 Vite 5 通过根 overrides 统一到 Vite 6.4.5，解决插件类型冲突并减少旧版本告警；契约、前端、文档及真实浏览器回归均需验证该组合。
未执行 `npm audit fix --force`，未擅自改变技术栈大版本。具体依赖审计随公告变化，后续应重新运行命令，不能依赖本记录判断未来状态。
