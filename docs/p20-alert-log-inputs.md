# P20 告警与 CLS 输入

本 change 只提供输入，不生成诊断。GET `/aiops/alerts/active` 需要既有 Bearer 认证；返回标准 envelope，data 仅含 items。每条包含 source、原生 status、alertname、service、severity、startsAt、labels、annotations、脱敏 raw。所有认证用户共享项目部署配置的源；本接口不创建用户拥有的源或诊断数据。

在 ignored `config/project.json` 或 `config/user.project.json` 中设置（不要提交凭据）：

```json
{
  "prometheusAlerts": {
    "sources": [
      {"name": "prometheus", "type": "prometheus-v1", "url": "http://127.0.0.1:9090/api/v1/alerts", "timeout": 10},
      {"name": "alertmanager", "type": "alertmanager-v2", "url": "http://127.0.0.1:9093/api/v2/alerts", "timeout": 10, "basicAuth": {"username": "", "password": ""}}
    ]
  }
}
```

URL 是完整 API 地址，不支持内嵌凭据或 query。认证可省略；生产 Basic Auth 应使用 HTTPS。Prometheus 保留 firing/pending，Alertmanager 保留 active/suppressed/unprocessed；已解决记录排除。单源失败仍返回成功源 items（可能为空），全失败/无配置返回 `AIOPS_ALERTS_UNAVAILABLE` 503。没有 provider 状态集合、默认告警或诊断。错误不包含上游 body 或 URL。监控标签仍应遵守部署数据治理，不应把凭据写入自由文本。

## 独立 CLS 工具

官方 SDK 1.0.9 要求 protobuf<4，与 backend pymilvus 的 protobuf>=5 不兼容。因此使用独立环境，通过 uv 安装 backend 包（不安装其依赖）复用同一 JSON 加载器；不设置 PYTHONPATH 或注入 sys.path。在仓库根目录执行：

```powershell
uv venv scripts/.cls-venv
uv pip install --python scripts/.cls-venv/Scripts/python.exe -r scripts/cls-requirements.txt
uv pip install --python scripts/.cls-venv/Scripts/python.exe --no-deps -e apps/backend
```

在 ignored JSON 配置 `cls.secretId`、`cls.secretKey` 与 `clsLogUpload.endpoint/region/topicId/logsetId`。endpoint 必须是 `https://ap-guangzhou.cls.tencentcs.com` 形式的官方上传域名，无路径/端口/query；topicId 为 UUID。region 是日志字段，不决定客户端路由；logsetId 仅人工关联，不传给 SDK。模板凭据保持为空。日志固定为不含用户数据的 sample-service 样例，count 范围 1..1000。

```powershell
# 默认只预览，不导入 SDK，不创建客户端，不上传
scripts/.cls-venv/Scripts/python.exe scripts/generate_and_upload_cls_logs.py --count 10
# 只有操作者提供自己的凭据并确认目标后，才手动执行以下命令
scripts/.cls-venv/Scripts/python.exe scripts/generate_and_upload_cls_logs.py --count 10 --confirm-endpoint https://ap-guangzhou.cls.tencentcs.com --confirm-topic <自己的topic-UUID>
```

工具调用官方 `LogClient(endpoint, secretId, secretKey)` 和 `put_log_raw(topicId, groups)`，protobuf 时间单位为微秒。不打印 secret 或 SDK 异常。应用导入、启动、普通测试不上传。上传可能计费；不要把命令加入启动流程。官方接口依据：[腾讯 CLS SDK](https://github.com/TencentCloud/tencentcloud-cls-sdk-python)、[Alertmanager v2](https://github.com/prometheus/alertmanager/blob/main/api/v2/openapi.yaml)、[Prometheus API](https://prometheus.io/docs/prometheus/latest/querying/api/#alerts)。

## 真实 smoke 记录

本次未执行真实 Prometheus/Alertmanager API smoke 或 CLS 上传：用户尚未确认真实 API 目标，也未为本轮上传提供凭据和目标确认。单测仅使用 fake HTTP/SDK 边界，不代表真实服务验收。后续需先确认目标，再读取认证 API；CLS 写入必须单独确认并记录上传数量与结果，禁止记录凭据。
