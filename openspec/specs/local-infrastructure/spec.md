## Purpose

定义本地基础设施服务、镜像与运行边界。

## Requirements

### Requirement: 本地基础设施运行边界

Compose MUST 仅托管 etcd v3.5.18、MinIO RELEASE.2024-12-18T13-15-44Z、Milvus v3.0-beta、Attu v2.5.12 和 Alertmanager v0.28.1，并作为镜像版本唯一来源。后端、前端和官方 CLS MCP Server MUST 在主机运行。MinIO 仅供 Milvus 使用。

#### Scenario: 校验服务配置

- **WHEN** 解析 Compose
- **THEN** 仅有上述五项服务、健康检查及所需持久卷，Milvus standalone 等待 etcd 和 MinIO 健康，Attu 等待 Milvus 健康，Alertmanager 只读挂载配置并暴露 9093
- **AND** 无应用容器、应用镜像、应用 Dockerfile、环境文件、变量插值、日志上传或 SOP seed，模板无遗留 docker 配置段
