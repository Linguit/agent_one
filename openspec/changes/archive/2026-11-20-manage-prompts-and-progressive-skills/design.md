## Context

现有 ChatAgent 在应用生命周期注入模型、知识工具、会话仓储与审计。认证上下文提供 owner；SQLite 已迁移至 0007。

## Goals / Non-Goals

目标：用户资产持久化、严格标准文件上传、每请求读取选择、渐进加载与跨用户隔离。
非目标：P19 侧栏、执行上传代码、文件系统资源包与静态项目 catalog。

## Decisions

- 新增 user_chat_configurations、user_chat_prompts、user_chat_skills 三表。配置以 owner 为主键，选项在 SQLite 写事务内验证并更新；资产查询、修改、删除均带 owner 条件。删除选中 Prompt 原子设为 null，删除 Skill 原子移除选择。
- 使用现有认证与 envelope；GET/PUT /chat/configuration 返回 prompts、skills、selectedPromptId、selectedSkillIds，写入仅接受两个选择字段。Prompt 保存 label/content，Skill 保存原始 filename/content、完整 JSON 元数据和 description 摘要。
- multipart 文件名必须逐字等于 SKILL.md，不接受目录、绝对路径、大小写变体。UTF-8 限制 256 KiB；安全解析 YAML，拒绝重复键、复杂类型和无效 name/description；name 去除首尾空白并转小写后校验 1–64 位小写字母数字与单连字符，owner 内唯一。
- 初始 system prompt 包含平台规则、自定义 Prompt 和 JSON 编码 name/description catalog。请求快照只保存当前 owner 已选 Skill，load_skill 使用闭包白名单并在加载时再次查 owner 与当前选择；撤销、删除后拒绝加载。正文仅通过工具结果返回，不回填 system prompt 或持久历史。
- 用户 Prompt 与 Skill 是不可信指导，不能改变服务端工具、tenant 或 owner。知识工具继续使用可信 scope。reasoning 只走现有模型内容透传。工具审计只存状态和摘要。
- configuration store 使用认证请求与串行操作，切换用户时清空且丢弃旧请求结果。最终编辑侧栏由 P19 接入。

## Risks / Trade-offs

- 提示注入风险 → 平台明确优先级，权限由工具闭包和仓储条件强制执行，用户文本不能授权工具。
- 上传文件膨胀或恶意 YAML → 字节、字段长度限制，拒绝别名与重复键，安全加载且仅保存 JSON 元数据。
- 配置并发更新 → BEGIN IMMEDIATE 串行化配置及删除事务；请求 catalog 为启动时快照，后续撤销在工具加载时生效。

## Migration Plan

Alembic 0008 创建三表，空用户默认 null/[]，不自动导入示例。回滚先删除配置再删除资产表；部署显式执行迁移，不在导入时建表或连接服务。

## Open Questions

无。真实模型验证仅在配置可用时执行，并单独记录结果，不用替身冒充。
