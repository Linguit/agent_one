# 中文桌面工作台

Vue Router 管理登录、注册与受保护路由，Pinia 管理会话和受保护状态。登录、注册、刷新和退出依赖运行中的 P04 后端。
对话、知识库、AIOps 和 MCP 页面提供后续接入用的画布。

根目录执行 npm install 后，可在本目录执行 npm run dev、npm run typecheck、npm run test、npm run build。
dev/build 读取根目录的本机 JSON。按根 README 从模板复制，config.ts 只接收允许的公开字段。
单元测试使用独立配置。根目录的 npm run frontend:security 构建临时副本并检查配置泄漏，npm run frontend:desktop 使用 1440×900 浏览器验收。
