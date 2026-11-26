## 1. 数据与事务边界

- [x] 1.1 新增案例表、文档 metadata 迁移及 owner scoped 模型/仓储。
- [x] 1.2 扩展既有文档与索引仓储以支持显式事务组合，保持原 API 行为。

## 2. 自动与手动路径

- [x] 2.1 实现独立 DiagnosisCasePersistor、确定性字段提取、Markdown 和 source metadata。
- [x] 2.2 接入诊断 succeeded 收尾事务，验证 report/end checkpoint，保证幂等、回滚及证据快照。
- [x] 2.3 实现独立 legacy 保存路由、案例列表/详情及 contracts。
- [x] 2.4 索引与检索传递来源 metadata，让案例进入下一轮 RAG。

## 3. 验证与归档

- [x] 3.1 测试成功/失败/取消/无最终报告、空证据、并发幂等、回滚、legacy、跨用户、Markdown、索引及再检索。
- [x] 3.2 运行 migration、backend/contracts、构建/安全/桌面等项目门禁并记录真实 smoke 条件。
- [x] 3.3 完成 verify 记录，验证所有规范与差异，同步 specs 并归档。
