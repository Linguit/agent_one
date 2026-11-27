# 无告警源的日志诊断

## Why
仅使用 CLS 的用户未选择告警时，诊断仍强制读取告警源并失败。

## What Changes
仅在 alertNames 非空时读取和筛选告警；未选择告警时使用知识检索和当前用户启用的日志查询 MCP 继续诊断。保持指定告警时的失败行为。

## Capabilities
### Modified Capabilities
- `aiops-diagnosis`: 告警读取由显式选择触发。

## Impact
仅修改 Planner 条件及回归测试，不改变接口契约、租户范围及工具真实调用要求。
