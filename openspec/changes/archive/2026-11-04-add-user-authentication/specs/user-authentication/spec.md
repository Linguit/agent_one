## Purpose

提供安全的用户注册、登录、登出、认证恢复和当前用户查询能力。

## Requirements

## ADDED Requirements

### Requirement: 用户注册与密码安全
系统 SHALL 接受规范化邮箱和密码注册，邮箱唯一，密码 SHALL 使用 Argon2 哈希保存且不得保存或记录明文。

#### Scenario: 注册成功
- **WHEN** 客户端提交未使用的邮箱和合规密码
- **THEN** 系统创建用户并返回统一成功 envelope，响应不包含密码或 password_hash

#### Scenario: 重复邮箱
- **WHEN** 客户端提交已存在邮箱的任意大小写或空白变体
- **THEN** 系统返回统一业务错误且不创建第二个用户

### Requirement: 登录与 bearer 会话
系统 SHALL 对正确凭据生成高熵 opaque bearer token；数据库仅保存 64 位 SHA-256 token hash 及 createdAt、lastSeenAt、revokedAt。

#### Scenario: 正确登录
- **WHEN** 已注册用户提交正确邮箱和密码
- **THEN** 系统返回 raw token 与用户 DTO，数据库不出现 raw token

#### Scenario: 错误或未知凭据
- **WHEN** 密码错误或邮箱不存在
- **THEN** 系统执行 dummy Argon2 校验并返回相同 AUTH_INVALID_CREDENTIALS 错误

#### Scenario: 当前会话访问
- **WHEN** 请求携带有效 Bearer token 调用 /auth/me
- **THEN** 系统返回当前用户并更新 lastSeenAt

### Requirement: 登出与认证依赖
系统 SHALL 支持撤销当前会话；无效、缺失或已撤销 token 的受保护请求 SHALL 返回统一 401 错误。

#### Scenario: 登出
- **WHEN** 已认证客户端调用 /auth/logout
- **THEN** 当前会话写入 revokedAt，后续 /auth/me 不再接受该 token

#### Scenario: 认证恢复与清理
- **WHEN** 前端初始化或 token 失效
- **THEN** 前端调用 /auth/me 恢复用户，失败或 logout 时清除本地 token 和内存用户状态

### Requirement: 统一 API 与 contracts
认证端点 SHALL 提供 POST /auth/register、POST /auth/login、POST /auth/logout、GET /auth/me，均使用统一 envelope/error/requestId；contracts SHALL 声明 DTO、Bearer security scheme、401 错误和本机前端 CORS。

#### Scenario: 认证错误格式
- **WHEN** 请求缺少或携带无效认证
- **THEN** 响应状态为 401 且包含统一 error code、message、requestId
