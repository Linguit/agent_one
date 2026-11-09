# 基础设施边界

P01 仅锁定职责，不提供 Compose 部署文件或启动基础设施。

最终 Compose 只托管 etcd、MinIO、Milvus、Attu、Alertmanager。后端、前端和官方 CLS MCP Server 必须在主机运行。
不创建 app.Dockerfile、project.compose.json 或应用 Compose 服务；端口、卷、健康检查与真实服务验收由后续提案定义。
