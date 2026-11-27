# 诊断失败脱敏日志

## Why
诊断和后台任务异常被转换为通用错误，无法定位失败阶段。

## What Changes
记录阶段、异常类型、白名单错误码与栈帧位置，禁止记录异常正文、局部变量、参数、返回值和凭据。保持 API 与任务重试行为不变。

## Capabilities
### Modified Capabilities
- `aiops-diagnosis`: 增加服务端脱敏失败诊断。

## Impact
仅影响诊断运行器、后台任务异常日志和回归测试。
