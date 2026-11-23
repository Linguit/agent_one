# 桌面聊天工作区

在 `/chat` 的全局左栏新建、选择和删除会话。消息区域独立滚动，输入框始终保留在主区域底部；空会话不显示占位图标。Enter 发送，Shift+Enter 换行，输入法组词时 Enter 不发送。

右侧“Prompt 与 Skill”按钮可收起配置栏。Prompt 支持单选、新建、编辑和删除；Skill 支持上传 SKILL.md、多选与删除。错误保留编辑输入，可修正后重试。记忆模式和上下文占用率位于输入框旁，满足服务端压缩条件时可手动压缩。

回答使用安全 Markdown，原始 HTML 不执行。推理和工具调用可展开查看；工具输出默认折叠，仅展示服务端摘要，不展示参数或原始 JSON。引用卡最多五条，展示摘录和各检索阶段证据；缺失阶段显示“未命中”。展开详情可查看元数据，并跳转到有权限访问的来源文档。

实时引用每轮清空，历史引用按各助手消息元数据恢复。Pinia 保存领域状态，不写入 localStorage。正文流按 for-await 顺序处理：每更新一个 Unicode 字符后等待约 28 ms，随后继续读取后续事件；完成后从服务端历史对账。

当前会话 ID 保存在 URL 的 session 查询参数中，刷新页面后重新请求该会话和每条助手消息的引用。

自动桌面夹具：`npm run frontend:desktop`。真实 smoke：在 apps/backend 用 `uv run python ../../scripts/serve_chat_smoke.py --milvus-endpoint http://127.0.0.1:19530` 启动当前后端，然后根目录执行 `node scripts/check-chat-real.mjs`。启动器复用本机提供方配置，通过应用工厂注入独立 SQLite 和 Milvus 集合；省略端口参数则使用本机 JSON 的地址。后者使用真实本机模型、嵌入、Milvus、重排和 `http://127.0.0.1:3000/sse` 官方 CLS MCP 服务，创建独立验收账号及资源，调用只读地域查询工具。截图和不含凭据的检查结果写入 ignored 的 `.cache`。

使用正常本机配置复验时，按常规命令启动后端 8000 和前端 5173，再执行 `node scripts/check-chat-real.mjs --normal`。此模式直接访问正常页面，不启动临时 Vite、不覆盖 API 地址、数据库或 Milvus 集合。它在正常数据库中创建独立验收账号、文档和 MCP 连接；结果与截图分别保存至 `.cache/chat-normal-smoke.json` 和 `.cache/chat-normal-smoke.png`。
