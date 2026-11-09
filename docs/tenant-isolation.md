# 架构边界

所有未来资源必须在 Repository 查询入口执行 owner scope。tenantId 与当前 user id 等价，向量 metadata 同时保留 tenantId 和 ownerUserId。登出只撤销认证并清理客户端状态，不删除持久数据。

适用范围包括 chat、knowledge、index jobs、vector、MCP、AIOps、evidence、reports、cases、feedback、audit、background jobs。
