## Purpose

建立可替换、可测试且 import 安全的 SQLite 持久化边界，为后续领域能力提供统一基础。

## Requirements

### Requirement: 异步数据库资源边界
系统 SHALL 使用 SQLAlchemy 2 async 与 aiosqlite，并从本地 JSON merge 配置读取数据库 URL。engine、session factory 和连接资源 MUST 仅在 FastAPI lifespan、依赖 provider 或显式初始化路径创建；导入 `super_ai.memory` MUST 不打开数据库、不运行迁移。

#### Scenario: 配置注入创建数据库
- **WHEN** 测试或应用显式注入包含 database.url 的配置
- **THEN** provider 创建 async engine/session factory，且未读取开发者本机数据库。

#### Scenario: import safety
- **WHEN** 仅导入 `super_ai.memory`
- **THEN** 不创建 engine、不连接 SQLite、不执行 Alembic。

### Requirement: Alembic schema authority
Alembic SHALL 是 schema 迁移唯一权威；系统 MUST 提供声明式 Base、迁移环境和首个基础迁移。fresh database 执行 `upgrade head` 后，metadata 与迁移结果 MUST 一致，应用启动不得隐式 create_all 或自动迁移。

#### Scenario: fresh upgrade
- **WHEN** 对临时 SQLite 数据库执行 `alembic upgrade head`
- **THEN** 迁移成功到 head，且基础 schema 存在。

#### Scenario: metadata consistency
- **WHEN** 比较迁移后的表集合与声明式 metadata
- **THEN** 两者一致，未登记的表或漂移使测试失败。

### Requirement: repository replacement boundary
领域服务 SHALL 依赖 Repository Protocol 和不可变 domain record，不得接收或返回 ORM model。SQLite 实现 MUST 位于 `super_ai.memory.sqlite` 或 `extended_sqlite`，并保留未来 PostgreSQL 替换边界。

#### Scenario: repository contract
- **WHEN** 使用 SQLite repository 实现 protocol
- **THEN** 调用方只处理不可变 record，替换实现无需修改领域服务接口。

#### Scenario: no ORM leakage
- **WHEN** 检查 repository 公共方法签名
- **THEN** 不出现 SQLAlchemy ORM model 类型，业务状态不被隐藏在无结构大 JSON 中。

### Requirement: serialization and transaction conventions
持久化基础 SHALL 统一 JSON 字段序列化、UTC 时间和 ID 生成，并定义显式事务约定：成功提交，异常回滚，session 关闭。具有查询或关联需求的数据 MUST 使用规范化表，而非无结构 JSON。

#### Scenario: rollback
- **WHEN** repository 事务中发生异常
- **THEN** 事务回滚且 session 可安全关闭，不留下部分写入。

#### Scenario: UTC and stable identifiers
- **WHEN** 创建基础记录
- **THEN** 时间带 UTC 语义，ID 使用统一生成策略，JSON 序列化可往返。

### Requirement: test database isolation
系统 SHALL 提供临时 SQLite 数据库和 migration helper。测试 MUST 不依赖开发者本机 `var/memory.sqlite3`，并覆盖并发 async session、fresh upgrade、回滚、repository contract 与 import-safety。

#### Scenario: isolated test database
- **WHEN** 运行 persistence tests
- **THEN** 测试使用临时路径或内存数据库，结束后可清理，不读写项目默认数据库。

#### Scenario: concurrent sessions
- **WHEN** 两个 async session 并发访问测试数据库
- **THEN** session 相互隔离且事务结果可预测。


