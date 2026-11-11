# P07 验收记录

验收日期为 2026-11-11。

| 维度 | 结果 |
| --- | --- |
| 完整性 | 三项任务完成，覆盖两项能力的三条要求 |
| 正确性 | Compose 解析验证服务边界、依赖、卷与健康检查。向量测试覆盖合并配置、无副作用导入、健康探测、集合与索引、部分失败重试、作用域转义及跨用户检索和删除 |
| 一致性 | 复用项目 JSON 加载器及 P05 的 OwnerScope。调用方从可信身份和已授权知识库派生检索范围 |

## 门禁结果

- 后端 Ruff、strict Pyright 和 pytest 通过，31 项测试通过。Alembic 报告一条现有配置弃用警告。
- `docker compose -f infra/compose.yaml config --quiet` 通过，工程基础测试 6 项通过。
- 契约、前端类型检查与测试、前端构建及安全检查、1440×900 桌面浏览器检查、文档构建及安全检查均通过。
- `openspec validate --all` 和 `git diff --check` 通过。

## 真实服务冒烟

2026-11-11 首次归档时，Docker Desktop Linux Engine 不可达，未执行真实冒烟。Docker Desktop 启动后，同日补验通过。

### 启动实况

- `minio/minio` 拉取返回 `denied`。Compose 改用 `milvusdb/minio`，保留 `RELEASE.2024-12-18T13-15-44Z` 标签。
- 本机已有 `agent-py-milvus-1` 占用 19530，Docker 引擎也未能从工作区绑定配置文件。以 `infra/compose.yaml` 为基础，通过本机临时覆盖将 P07 的 Milvus 绑定到 `127.0.0.1:19531`，并从只读卷挂载 `infra/alertmanager.yaml` 的内容。仓库默认端口与配置文件挂载方式仍按 Compose 定义。
- `docker compose up -d --wait` 返回成功，P07 的 etcd、MinIO、Milvus、Attu、Alertmanager 五个容器均为 `healthy`。实际测试端点为 `http://127.0.0.1:19531`，Milvus RPC 返回版本 `3.0-beta`。

### 实测断言

| 项目 | 结果 |
| --- | --- |
| 健康与初始化 | 健康探测通过且未创建集合。同一实例重复初始化及第二实例加载已有集合均通过 |
| 集合与索引 | 服务端确认 `chunkId` 主键、1024 维 FLOAT_VECTOR、HNSW/COSINE、M=16、efConstruction=200，以及五个可过滤标量索引 |
| 写入 | 两个租户共写入 4 条。检索结果的标量与 metadata 均保留实际租户及所有者，覆盖输入中的伪造值 |
| 检索隔离 | 两个租户复用 KB 与文档 ID，分别只取回各自授权 KB 的数据。空 KB 返回空结果，带引号和反斜杠的作用域值可正常检索 |
| 删除隔离 | 删除目标租户、KB 和文档的向量后，同租户其他 KB、同 KB 其他文档和另一租户的同名文档仍可检索 |
| 清理 | 随机命名的临时集合已删除，并复查不存在 |

首轮脚本已通过初始化和写入，随后因将结果主键读作顶层 `id` 而中断。该临时集合已清理。改从返回实体的 `chunkId` 读取后，使用新集合完整重跑通过。

## 配置核对

基线的两份 JSON 模板已无 `docker` 段，本次增加了模板边界回归断言。已有本机配置可按基础设施说明填写 `vectorStore.endpoint`。
