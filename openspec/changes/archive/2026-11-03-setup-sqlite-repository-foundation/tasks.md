## 1. 数据库配置与资源

- [x] 1.1 扩展本地 JSON 配置读取数据库 URL，并定义 database typed settings
- [x] 1.2 建立 `super_ai.memory` Base、UTC/ID/JSON 序列化工具与 async engine/session provider
- [x] 1.3 接入 FastAPI lifespan 或显式依赖 provider，确保 import 无外部副作用

## 2. Alembic schema

- [x] 2.1 建立 Alembic 环境、env.py、script 模板和 migration helper
- [x] 2.2 创建首个基础迁移并验证 fresh upgrade head 与 metadata 一致

## 3. Repository boundary

- [x] 3.1 定义不可变 record、Repository Protocol 和事务接口
- [x] 3.2 增加 SQLite/extended_sqlite 实现骨架，不暴露 ORM model

## 4. 测试与质量

- [x] 4.1 增加临时 SQLite fixture、并发 session、rollback、repository contract 和 import-safety 测试
- [x] 4.2 运行 alembic upgrade head、pytest、Ruff、strict Pyright、OpenSpec validate 和 git diff check
- [x] 4.3 完成验证报告、同步主规格并归档 change



