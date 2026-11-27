# final-aiops-workspace Specification

## Purpose
提供基于真实告警、持久诊断与证据来源的中文桌面 AIOps 控制台，规范任务交互、断流恢复、安全报告和案例追溯。
## Requirements
### Requirement: 中文桌面诊断输入与持久任务
系统 SHALL 在 /aiops 提供手工 query、可选告警、真实告警刷新、诊断历史与创建入口；不得添加独立 context 字段。系统 SHALL 分开呈现诊断状态与后台 job 状态，按 job id 取消 queued/running 任务。

#### Scenario: 告警预填与创建
- **WHEN** 用户选择真实活跃告警并提交
- **THEN** 使用 query 与 alertNames 创建诊断并订阅该持久 job 的 SSE

#### Scenario: 历史与取消
- **WHEN** 用户选择历史或取消活动任务
- **THEN** 读取对应持久 detail 和 evidence chain，使用 background job id 请求取消并刷新持久状态

### Requirement: 实时过程与断流恢复
系统 SHALL 展示 plan、step、tool lifecycle、evidence、replan；Planner/Replanner 仅为 phase。断流后 SHALL 重新读取持久 task、history、chain、cases，不自动重订阅 SSE，不将工具或 provider 失败呈现为成功。

#### Scenario: 断流与失败
- **WHEN** SSE 中断、结束或返回 error
- **THEN** 恢复持久状态，显示连接提示与真实失败状态，保留已取得证据

### Requirement: 报告证据与案例来源
系统 SHALL 以安全 Markdown 展示固定报告结构、证据引用、不确定性和 fallback，工具输出默认折叠且只展示可读摘要，禁止 raw JSON 作为产品 UI。系统 SHALL 展示结构化 case 并打开对应 owner knowledge document。

#### Scenario: 查看来源
- **WHEN** 用户阅读报告、展开工具或案例
- **THEN** 可查看证据来源、步骤审计、引用关联、案例根因及建议，并打开对应文档

### Requirement: 固定高度与独立滚动
系统 SHALL 在 workspace 可用高度内显示左侧输入/告警/历史、中间报告/timeline、右侧证据/执行链/案例；长内容不得撑高页面。

#### Scenario: 长内容
- **WHEN** 报告、过程或证据内容超过可用高度
- **THEN** 对应区域内部滚动且右侧 provenance 保持可访问，无水平页面溢出
