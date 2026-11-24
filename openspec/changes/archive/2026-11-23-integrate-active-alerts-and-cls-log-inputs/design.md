## Context

复用本地 JSON 深合并、认证与 httpx。配置为 deployment-global，用户不能提交源地址或凭据；诊断持久数据留给 P21 按 owner 隔离。

## Goals / Non-Goals

目标：真实告警读取及安全独立日志上传。非目标：诊断、用户拥有的告警源、provider 状态集合、自动上传、基础设施扩容。

## Decisions

- sources 每项配置 name/type/url/basicAuth/timeout，url 为完整 API URL。使用异步 httpx 并发隔离每源失败，成功空集合仍为成功；没有可用源返回 503。
- DTO 保留源名称、原生状态、时间、标签、注释和脱敏 raw。Prometheus firing/pending 与 Alertmanager active/suppressed/unprocessed 保持原始语义，排除已解决记录。
- 仅认证 GET 请求触发读取；应用导入和启动不访问告警 API，不上传日志。资源通过显式调用上下文创建关闭。
- 官方 SDK 1.0.9 要求 protobuf<4，与 backend pymilvus 的 protobuf>=5 冲突。脚本采用独立 uv 环境及锁定 requirements，通过 uv --no-deps 安装 backend 包复用同一 JSON 加载器，不注入 sys.path/PYTHONPATH，不修改应用依赖。
- CLS 使用官方 SDK 的 LogClient(endpoint, secretId, secretKey) 和 put_log_raw(topicId, groups)。endpoint 决定路由，region 写入每条日志，logsetId 仅人工关联。默认仅预览计数；上传必须显式指定 endpoint/topic 确认参数，count 上限 1000。
- 模板所有凭据为空。错误使用固定文本，凭据及敏感键值在 raw/labels/annotations 中脱敏。前端公开配置白名单不变。

## Risks / Trade-offs

- 部分源失败不能显示来源状态集合：保留真实 items，按需求不扩展响应。
- 上游文本可能包含敏感信息：递归敏感键与凭据值过滤；调用者仍应对监控标签执行数据治理。
- 真实 API 与 CLS 上传需用户确认，隔离单测不能代替真实 smoke；记录未执行原因。

## Migration Plan

在 ignored JSON 配置 sources 与 CLS 目标。无数据库迁移，回滚移除路由和脚本即可。基础设施仍遵循现有 Compose 边界。
