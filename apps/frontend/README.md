# 桌面前端基础骨架

Vue 3.5/Vite 6/TypeScript 5.6 严格模式。当前只显示 P01 范围，没有认证、聊天或其他产品功能。
Pinia、Vue Router 已接入启动；marked、DOMPurify 等依赖保留供后续提案使用，当前不解析外部内容。

根 npm install 后，在本目录执行 npm run dev、npm run typecheck、npm run test、npm run build。
dev/build 读取根 ignored JSON；先按根 README 从模板复制。不导入完整配置，config.ts 只接收允许的公开字段。
单元测试使用独立配置；根 npm run frontend:security 构建临时副本并检查秘密泄漏。桌面以 1440x900 验收。
