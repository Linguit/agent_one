## Context

P07 复用 P01 的 JSON 深合并、P05 的认证 scope，并承接 P06 的 1024 维向量约定。

## Goals / Non-Goals

提供本地五服务拓扑及可注入的同步 Milvus 适配器。知识库管理与检索工具由后续变更实现。

## Decisions

- 容器只承载基础设施。宿主机端口绑定回环地址，持久数据使用命名卷。
- 构造只保存配置与工厂。连接、健康探测和集合初始化由调用方显式触发。单实例串行初始化，已存在的集合直接加载。
- 复用 OwnerScope。调用方从可信认证和 owner-scoped 仓储派生授权 KB。适配器用 JSON 字符串字面量生成 Milvus 表达式，空授权直接返回。
- 写入从 scope 派生标量和 metadata 的身份字段。文档与 metadata 后过滤由后续检索工具负责。

## Risks / Trade-offs

真实服务探测受 Docker 与 Milvus 可用性影响，记录实际观察结果。同步适配器未来从异步入口使用时需安排线程执行。
