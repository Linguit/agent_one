## Why

P01、P05、P06 建立了配置、租户边界和模型供应方基础。P07 为后续向量检索提供本地基础设施与租户隔离适配器。

## What Changes

- 固定五项基础设施服务及其版本，应用进程在主机运行。
- 以合并后的 `vectorStore` 配置显式连接 Milvus，并验证检索和删除的租户边界。
- 移除模板中遗留的 `docker` 配置段。

## Capabilities

### New Capabilities

- `local-infrastructure`：本地服务及运行边界。
- `milvus-vector-store`：向量集合、生命周期和租户过滤。

### Modified Capabilities

## Impact

涉及基础设施、配置模板、后端依赖和测试。知识库检索编排留待后续变更。
