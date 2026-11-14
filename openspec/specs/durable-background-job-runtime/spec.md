# 持久后台任务运行时

## Purpose

在 SQLite 中保存后台任务和事件，支持进程重启后恢复执行，以及客户端重连后按序读取进度。

## Requirements
### Requirement: 持久任务与租约
系统 SHALL 使用 SQLite 保存任务、尝试次数、调度时间、租约与事件，并原子领取到期任务。

#### Scenario: 并发领取与重启恢复
- **WHEN** 多个执行槽同时竞争任务，或运行进程退出导致租约过期
- **THEN** 每次领取只授予一个租约，过期任务按尝试次数重新调度或结束，旧租约无法覆盖当前状态

### Requirement: 任务生命周期
系统 SHALL 在 FastAPI lifespan 启停按 kind 分发的 worker，并支持续租、指数退避、最大尝试次数、超时和协作式取消。状态包括 queued、running、succeeded、failed 和 cancelled。

#### Scenario: 执行失败或取消
- **WHEN** handler 失败、超时或收到取消
- **THEN** 系统按剩余尝试次数重试失败或超时任务，或记录最终状态；取消优先于重新调度

### Requirement: 按认证身份管理任务
系统 SHALL 按可信 owner scope 隔离查询、取消、重试与事件访问，并通过四个后台任务 HTTP 接口管理任务。共享契约和 OpenAPI SHALL 描述返回结构。

#### Scenario: 跨租户访问
- **WHEN** 调用者使用其他用户的任务标识
- **THEN** 查询、取消、重试与事件读取均不会暴露或修改该任务

### Requirement: 持久事件重放与脱敏
系统 SHALL 在状态事务中追加单调序号事件，支持按 after_sequence 读取后续事件。系统 SHALL 避免在日志与公开错误中输出载荷和原始异常。

#### Scenario: 客户端断开后重放
- **WHEN** 客户端断开后从序号 0 或已有游标重新读取
- **THEN** 任务继续运行，事件按序重放
