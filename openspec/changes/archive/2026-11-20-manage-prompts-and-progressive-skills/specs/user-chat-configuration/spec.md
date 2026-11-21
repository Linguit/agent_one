## ADDED Requirements

### Requirement: 用户资产与配置持久化
系统 SHALL 通过三张 user_chat_* 表保存认证用户 Prompt、Skill 和单 Prompt 多 Skill 选择，所有读写 MUST owner scoped。GET/PUT /chat/configuration 返回当前资产与选择；POST /chat/prompts、PUT/DELETE /chat/prompts/{id} 保存 label/content。

#### Scenario: 持久化与非法选择
- **WHEN** 用户保存资产并选择后重新读取或重启应用
- **THEN** 资产与选择保持；不存在或其他用户资产不能被选择、修改或删除；失败写入不改变原配置

#### Scenario: 删除回退
- **WHEN** 用户删除当前 Prompt 或已选 Skill
- **THEN** 同一事务内 Prompt 选择设为 null，Skill 从选择中移除，其他资产与选择保持

### Requirement: 标准 Skill 上传
系统 SHALL 通过 POST /chat/skills multipart 接收严格名为 SKILL.md 的 UTF-8 文件，通过 DELETE /chat/skills/{id} 删除。系统 MUST 校验 YAML frontmatter 的 name、description，规范化 name 且 user 内唯一，保存 filename/content/metadata/摘要，拒绝非法路径、超限和无效元数据。

#### Scenario: 上传校验与用户隔离
- **WHEN** 上传合法文件或包含路径、错误文件名、无效 YAML、缺失字段、规范化后重复 name 的文件
- **THEN** 合法文件可读且隔离；非法文件返回验证错误且不产生资产；相同 name 可属于不同用户

### Requirement: 渐进 Skill 装配与权限
系统 SHALL 在每次请求以平台安全规则、当前 Prompt 和仅含已选 Skill name/description 的 catalog 组装 system prompt。MUST 创建请求级 LangChain load_skill(name) 工具，只有模型调用时返回 Skill 正文。用户文本不得改变服务端 owner/tenant/tool 权限；reasoning MUST 仅透传模型真实内容。

#### Scenario: 摘要与按需加载
- **WHEN** 模型第一次接收请求并随后调用已选 Skill
- **THEN** 初始 system prompt 没有 Skill 正文，工具结果才包含正文，工具调用进入原有审计，后续请求使用最新选择

#### Scenario: 未选择与跨用户拒绝
- **WHEN** 模型请求未选择、其他用户或已撤销、已删除的 Skill
- **THEN** 工具拒绝且不泄漏正文，用户 Prompt 不能解除限制

### Requirement: 共享契约与前端配置状态
系统 SHALL 提供可编辑资产、selectedPromptId/selectedSkillIds 的 contracts 与前端 configuration store，支持配置读取、选择保存和资产管理；切换用户 MUST 清理旧状态并拒绝过期请求覆盖。

#### Scenario: 配置操作与用户切换
- **WHEN** 前端修改资产及选择或切换认证用户
- **THEN** store 反映服务端最新配置，旧用户异步结果不能写入新用户状态，最终侧栏由 P19 实现

### Requirement: 标准示例
系统 SHALL 提供 knowledge-search、log-analysis、incident-report、api-troubleshooting、change-risk-review 五个示例，目录采用 <skill-name>/SKILL.md，具备合法 frontmatter 与可操作正文。

#### Scenario: 样例规范
- **WHEN** 使用同一上传解析器检查全部示例
- **THEN** 五个示例均合法，name 与目录相同，description 非空，正文不会自动导入模型
