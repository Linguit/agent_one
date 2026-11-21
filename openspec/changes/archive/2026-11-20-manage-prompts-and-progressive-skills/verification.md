# P16 验证报告

日期：2026-11-20。变更：`manage-prompts-and-progressive-skills`，流程：spec-driven。

## 核对结果

| 维度 | 结果 |
| --- | --- |
| 完整性 | 8/8 任务完成；5/5 要求、7/7 场景已有实现与测试；主规范已同步，change 已归档 |
| 正确性 | Prompt 单选、Skill 多选、owner 隔离、删除回退、严格上传及模型按需加载均验证通过 |
| 一致性 | 遵循 SQLite 显式事务、生命周期注入、统一认证/envelope、LangChain 工具审计及前端账户切换模式 |

未发现 CRITICAL、WARNING 或需要修复的 SUGGESTION。未跳过要求或场景核对。

## 要求与证据

| 要求 | 实现 | 场景验证 |
| --- | --- | --- |
| 用户资产与配置持久化 | `0008_user_chat_configuration.py`；`memory/sqlite/configuration.py`；`configuration_api.py` | 从 0007 升级、空库升级、降级再升级、旧用户保留、CRUD、跨用户拒绝、非法选择不变、应用重启持久化、删除失败事务回滚、Prompt 删除回退 null 并保留其他资产 |
| 标准 Skill 上传 | `skill_format.py`；上传路由对原始 Content-Disposition 与解析后 filename 双重验证 | 严格 SKILL.md、目录路径、Windows 绝对路径及 UNC 拒绝；UTF-8/大小/空正文/YAML/重复键/锚点/类型/name/description 校验；用户内规范化去重、跨用户允许同名；原始内容与 JSON metadata 持久化 |
| 渐进装配与权限 | `progressive_skills.py`；`agent_chat.py` | 初始 catalog 仅 name/description；metadata 与正文不预注入；实际 LangChain Agent 模型工具往返及审计；未选择、其他用户、撤销、删除拒绝；多选与请求快照不能扩大到后来新选 Skill；当前 Prompt 更新后下一次装配使用最新内容 |
| contracts 与 store | `configuration.ts`；`configurationClient.ts`；`configurationStore.ts` | 资产编辑及选择契约；multipart 文件；路由编码；服务端删除回退协调；切换用户丢弃旧结果、阻止旧排队写入、退出清空、失败恢复 |
| 标准示例 | `examples/skills/<name>/SKILL.md` | 五个指定示例用同一上传解析器验证，name 匹配目录，description 与正文非空；不会自动注册或注入 |

平台规则明确优先级；真实工具仍使用可信 OwnerScope，用户 Prompt/Skill 无法扩展权限。reasoning 提取与 SSE 透传保持现有实现，工具加载事件不伪装成 reasoning。模型往返测试验证真实模型响应字段的透传。

## 门禁

所有正式后端命令在 `apps/backend` 执行，pytest 加载本地 pyproject.toml，asyncio_mode=auto。

| 命令 | 结果 |
| --- | --- |
| `uv run ruff check .` | 通过 |
| `uv run pyright` | 0 errors、0 warnings |
| `uv run pytest` | 99 passed，包含 P16 新增 30 项 |
| `npm run contracts:typecheck` / `npm run contracts:test` | 通过；4 项测试 |
| `npm run frontend:typecheck` / `npm run frontend:test` | 通过；22 项测试 |
| `npm run frontend:build` / `npm run frontend:security` | 通过；公开与非公开 analytics 两组，7 个私密哨兵均未泄漏 |
| `npm run frontend:desktop` | 实际 Edge 浏览器 1440×900 验证通过；接口夹具覆盖认证、导航、知识库操作、标题、布局、无横向溢出、无控制台错误及配置访问拒绝 |
| `npm run foundation:test` | 6 项通过，包含未跟踪文件空白规则和 Compose 边界 |
| `npm run docs:build` / `npm run docs:security` | 通过；首页 200，两份本机配置请求 403 |
| `openspec validate --all` | 归档前同步后 20 项通过；归档后 19 项主规范通过 |
| `git diff --check` | 通过 |

开发中发现并修复了测试 provider 参数、LangChain 延迟导入和严格输入消息类型、原始 Windows 文件名校验；曾从仓库根目录误启动 pytest，未加载后端异步配置，已在正确目录完成正式全量重验。

## 真实模型验收

使用现有本机模型配置，独立临时 SQLite 数据库和一次性测试用户执行真实 ChatAgent 请求，未修改本机业务数据库或配置，未输出凭据。

- 模型请求次数：2。
- `load_skill` 工具审计：completed。
- 每次请求的初始 system prompt 均不含验收正文。
- 正文只通过工具结果进入后续模型上下文。
- SSE 正常 complete，最终答案返回仅存在于 Skill 正文的验收标记。

真实验收脚本保留于 ignored `.cache/progressive_skill_smoke.py`，没有加入项目源代码或自动化测试。

## 交付边界

新增 Alembic 0008，部署时需显式升级至 head。本次仅迁移隔离测试数据库；P19 最终侧栏不在 P16 范围。
本次未自动提交或推送。主规范新增 `openspec/specs/user-chat-configuration/spec.md`，逐字核对所有要求与场景和 delta 一致后，使用 `openspec archive manage-prompts-and-progressive-skills --yes --skip-specs` 归档；此处 skip-specs 仅避免重复同步，主规范已完成同步。

归档目录：`openspec/changes/archive/2026-11-20-manage-prompts-and-progressive-skills/`。
