## Why

用户需要持久管理个人 Prompt 和标准 Agent Skill，并在每次对话中使用当前选择。Skill 正文应由模型按需加载，减少初始上下文并保持服务端权限边界。

## What Changes

- 新增 owner scoped Prompt、Skill 和选择配置的 SQLite 持久化与认证 API。
- 严格接收 SKILL.md，校验 YAML 元数据，保存正文与摘要；增加请求级 load_skill 工具。
- 服务端组合平台规则、当前 Prompt 和仅含 name/description 的已选 Skill catalog。
- 增加共享契约、前端 configuration store 和五个标准示例；最终侧栏留给 P19。

## Capabilities

### New Capabilities
- `user-chat-configuration`: 个人 Prompt、Skill、选择配置及按需加载的安全装配。

### Modified Capabilities

无。现有 Chat Agent 的真实 reasoning、持久会话与工具权限边界保持原有要求。

## Impact

影响后端 Alembic、认证路由、ChatAgent、contracts、前端 store、示例与测试。使用现有 SQLite 与 LangChain 生命周期，不引入静态项目 catalog 或正文预注入。非目标是 P19 侧栏、执行上传代码以及改变租户权限。
