# 验证脚本

- npm run foundation:test：检查目录、入口、脚本、Git 忽略与工程边界。
- npm run frontend:desktop：使用本机 Microsoft Edge 无头桌面浏览器验收 1440x900 页面、控制台及开发服务器配置访问拒绝；截图保存于 ignored 的 .cache/desktop-foundation.png。本机需已安装 Edge。
- npm run docs:security：使用临时文档副本和临时 JSON，验证首页可访问且两份配置均被拒绝。桌面和文档测试不读取开发者本机 JSON。
- npm run frontend:security：在本项目 .cache 内构建临时前端，以七个私密哨兵检查所有 dist 产物；分别验证公开 analytics 开关，不读取或覆盖开发者配置，结束后清理临时目录。

应用配置只使用本地 JSON，不依赖环境变量。所有门禁详见根 README 和 AGENTS.md。
