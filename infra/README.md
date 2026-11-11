# 基础设施边界

Compose 托管 etcd、MinIO、Milvus、Attu 和 Alertmanager，镜像版本以 `compose.yaml` 为准。后端、前端和官方 CLS MCP Server 在主机运行。MinIO 仅用于 Milvus 内部存储。

在仓库根目录运行：

```powershell
docker compose -f infra/compose.yaml config --quiet
docker compose -f infra/compose.yaml up -d --wait
docker compose -f infra/compose.yaml ps
```

主机通过 `http://127.0.0.1:19530` 连接 Milvus，通过 3000 和 9093 端口访问 Attu 和 Alertmanager。用本机合并 JSON 的 `vectorStore.endpoint`、`token` 和可选 `collectionName` 配置适配器。默认集合为 `knowledge_chunks`。

`docker compose -f infra/compose.yaml down` 停止服务并保留命名卷。

## Windows 本机启动覆盖

如果主机的 19530 已被占用，或 Docker Desktop 无法绑定挂载工作区中的配置文件，可在仓库根目录运行下面的 PowerShell。需要支持 `!override` 的 Docker Compose。覆盖通过标准输入传入 Compose，可以重复执行。

```powershell
$alertConfigVolume = 'infra_p07_local_alertmanager_config'

docker volume create $alertConfigVolume
if ($LASTEXITCODE -ne 0) { throw '创建 Alertmanager 配置卷失败' }

# 从主机读取仓库配置，通过 stdin 写入 Docker 卷，绕开文件共享。
$seedConfig = 'cat > /config/alertmanager.yml.tmp && chmod 444 /config/alertmanager.yml.tmp && mv -f /config/alertmanager.yml.tmp /config/alertmanager.yml'
Get-Content -Raw -Encoding utf8 -LiteralPath infra/alertmanager.yaml |
  docker run --rm -i --mount "type=volume,source=$alertConfigVolume,target=/config" busybox:latest sh -c $seedConfig
if ($LASTEXITCODE -ne 0) { throw '写入 Alertmanager 配置卷失败' }

$override = @"
services:
  milvus:
    ports: !override
      - "127.0.0.1:19531:19530"
  alertmanager:
    volumes: !override
      - p07-local-alert-config:/etc/alertmanager:ro
      - alertmanager-data:/alertmanager
volumes:
  p07-local-alert-config:
    external: true
    name: $alertConfigVolume
"@

$override | docker compose -f infra/compose.yaml -f - config --quiet
if ($LASTEXITCODE -ne 0) { throw 'Compose 覆盖配置无效' }

$override | docker compose -f infra/compose.yaml -f - up -d --wait --wait-timeout 180
if ($LASTEXITCODE -ne 0) { throw 'Compose 服务未全部就绪' }

docker compose -f infra/compose.yaml ps
```

将本机 JSON 的 `vectorStore.endpoint` 设为 `http://127.0.0.1:19531`。Attu 在容器网络内使用 `milvus:19530`，Alertmanager 对主机开放 9093。

更新 `infra/alertmanager.yaml` 后，重新运行上面的命令写入配置卷。如果 Alertmanager 容器已经在运行，在同一 PowerShell 会话中发送重载信号：

```powershell
$override | docker compose -f infra/compose.yaml -f - kill -s SIGHUP alertmanager
```

停止服务时可运行 `docker compose -f infra/compose.yaml down`，配置卷和数据卷会保留。再次启动时重用上面的覆盖命令。
