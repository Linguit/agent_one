# 最终桌面聊天工作区

## Purpose

将已有会话、流式聊天、Prompt、Skill、记忆、MCP 与检索能力组合为安全、一致且引用可追溯的桌面聊天体验。

## Requirements

### Requirement: 固定桌面聊天工作区
系统 MUST 仅在 /chat 的全局 Workspace 左栏显示会话新建、切换和删除，主区不得嵌套历史侧栏。消息区域局部滚动且 composer 可见，Prompt 与 Skill 使用独立右栏 disclosure，记忆模式及占用率邻近 composer；空 transcript 保持空白。

#### Scenario: 桌面切换会话
- **WHEN** 用户在 1440×900 桌面创建、切换或删除会话
- **THEN** 左栏和服务端状态一致，正文适应宽度，页面无溢出且 composer 保持可见

### Requirement: 安全输入与正文
系统 MUST 支持 Enter 发送、Shift+Enter 换行和 IME composing 不发送；textarea 不可 resize。正文必须经 marked 和 DOMPurify 渲染并禁用不可信 raw HTML。

#### Scenario: 输入法和恶意正文
- **WHEN** 用户处于输入法组词或消息包含 raw HTML 与危险链接
- **THEN** 组词 Enter 不发送，正文不执行 HTML 或脚本，普通 Markdown 正常显示

### Requirement: 顺序流与历史对账
系统 MUST 使用 Pinia 保存会话、当前消息、配置、工具审计、实时工具及引用，领域状态不进 localStorage；共享 SSE 支持断帧。for-await 按序处理，正文每个字符更新后等待约 28 ms，complete 后从服务端历史对账。

#### Scenario: 正文后到达完成事件
- **WHEN** 正文、工具和 complete 连续到达
- **THEN** 逐字符等待结束后继续后续事件，最终消息以服务端历史为准

### Requirement: 每轮引用与检索证据
系统 MUST 在新回合清空实时引用，重载从对应 assistant metadata 恢复引用。引用最多五条，按 rerankRank 和 score 排序，显示来源、excerpt、文档与知识库及 vector/BM25/RRF/rerank 排名分数；缺失阶段显示“未命中”。详情展示 metadata、阶段轨迹并可导航 owner 文档。

#### Scenario: 两轮引用隔离
- **WHEN** 第一轮检索有引用，第二轮普通问答无引用并重载
- **THEN** 第一轮保留自己的引用，第二轮不显示上一轮引用

### Requirement: 可操作配置和生命周期
系统 MUST 提供 Prompt 单选与 CRUD、Skill 多选上传删除、memory mode 和 manual compact。推理与工具生命周期可折叠，工具输出默认折叠，仅展示安全摘要且不渲染 raw JSON。失败后可重试操作。

#### Scenario: 配置或压缩失败后重试
- **WHEN** 接口失败后用户修正输入或重试
- **THEN** 显示错误并保留操作上下文，后续成功时与服务器状态一致

### Requirement: 真实服务验收
系统 MUST 通过前端与契约全门禁、相关后端测试、OpenSpec 校验和 diff 检查，并在桌面使用真实模型执行普通问答和自主知识或 MCP 工具问答后方可同步规范及归档。

#### Scenario: 真实模型 smoke
- **WHEN** 在实际桌面页面发送普通问题与工具问题
- **THEN** 实际 API/SSE 完成，工具问答具有真实调用证据，检查布局及控制台无错误
