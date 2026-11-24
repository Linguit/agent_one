# P20 实现验证记录

## 验证结论

实现与 proposal、design、两份 delta specs 一致，未发现 CRITICAL、WARNING 或待修复 SUGGESTION。两份主规范已同步且逐条比对一致，归档前状态检查通过。

| 维度 | 结果 |
|---|---|
| 完整性 | 7/7 任务完成，3/3 要求覆盖，规范同步及归档前检查通过 |
| 正确性 | 3/3 Requirement、9/9 Scenario 有实现与测试证据 |
| 一致性 | 复用项目配置/认证/envelope；源为 deployment-global；无诊断和 provider 状态集合 |

## 需求与场景映射

| 要求/场景 | 实现 | 验证 |
|---|---|---|
| 全局真实告警聚合、两类响应标准化及脱敏 | apps/backend/src/super_ai/alert_inputs.py:15、:36、:93、:155 | tests/test_alert_inputs.py:68 |
| 部分失败、全失败及成功空列表 | alert_inputs.py:155；alert_api.py:25 | test_alert_inputs.py:89、:116、:155 |
| 认证、DTO、401/403、全局源授权 | alert_api.py:25；main.py；packages/api-contracts/src/index.ts | test_alert_inputs.py:155；packages/api-contracts/tests/alerts.test.ts |
| 普通启动/导入不访问告警或 CLS | 仅路由请求调用 aggregator；脚本 main guard 与延迟 SDK import | test_alert_inputs.py:155、:318；backend 环境未安装 CLS SDK，启动测试正常通过 |
| 独立安全 CLS、默认预览 | scripts/generate_and_upload_cls_logs.py:18、:68 | test_alert_inputs.py:231 |
| 显式确认、endpoint 路由、region 日志字段、logsetId 人工关联 | generate_and_upload_cls_logs.py:36、:54、:68 | test_alert_inputs.py:231、:298 |
| 非法 endpoint/count、不泄漏异常或配置 | generate_and_upload_cls_logs.py:18、:36、:104 | test_alert_inputs.py:275、:291、:298 |

测试文件完整路径为 apps/backend/tests/test_alert_inputs.py。HTTP/SDK 为 fake 边界；未将这些结果描述为真实 API smoke。

## 门禁结果

- `uv run ruff check .`：通过。
- `uv run pyright`：0 errors、0 warnings。
- `uv run pytest`：176 passed；仅两条既有 MCP streamable HTTP 弃用警告。
- P20 新增后端测试：26 passed。
- `npm run contracts:typecheck`、`npm run contracts:test`：通过，6 tests。
- frontend:typecheck/test/build/security/desktop：通过，39 tests；1440×900 浏览器夹具验收通过，无页面控制台错误；真实配置请求被拒绝为预期行为。
- foundation:test：6 passed。
- docs:build/security：通过，临时首页 200，两份本地 JSON 均为 403。
- `openspec validate --all`：同步前 23 passed，同步后 25 passed。
- `git diff --check`：通过；foundation:test 同时扫描未跟踪新文件空白。
- 官方 SDK 1.0.9 离线 protobuf 构造/序列化：通过；未创建 LogClient，未执行网络请求。

## 依赖与安全边界

官方 SDK 要求 protobuf<4，与 backend pymilvus 要求 protobuf>=5 冲突。采用 scripts/cls-requirements.txt 锁定的独立环境，通过 uv --no-deps 安装 backend 包以复用统一 JSON 加载器，无 sys.path/PYTHONPATH 注入。应用依赖和运行时没有引入上传任务。SDK 官方参考：https://github.com/TencentCloud/tencentcloud-cls-sdk-python 。

只修改空凭据模板，不读取、覆盖或 stage 真实配置；保留已有 vector 相关修改。未提交、推送。

## 真实服务验收边界

未执行真实 Prometheus/Alertmanager API smoke，也未执行 CLS 上传。原因：用户未确认本轮真实 API 目标，未提供本轮自己的 CLS 凭据和目标确认。真实写入需要操作者在独立脚本显式确认 endpoint/topic 后执行；普通启动、单测和本次门禁均没有触发上传。

## 归档结果

已同步两份主规范，并逐条确认 requirement/scenario 与 delta 一致。7/7 任务完成，CLI state=all_done。已归档至 `openspec/changes/archive/2026-11-23-integrate-active-alerts-and-cls-log-inputs`；归档后 `openspec validate --all` 为 24 passed、0 failed，active changes 为空，`git diff --check` 通过。真实 API smoke 和 CLS 写入仍未执行。
