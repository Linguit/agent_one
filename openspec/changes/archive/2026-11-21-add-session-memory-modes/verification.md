# P17 验证报告

验证日期：2026-11-21。检查 proposal、design、delta spec、tasks 与全部实现差异，没有跳过完整性、正确性或一致性检查。

| 维度 | 结果 |
| --- | --- |
| 完整性 | 4 项需求均已实现，8/8 项任务完成，主规范已同步，归档作为最终交付动作执行 |
| 正确性 | 9 个规范场景均有代码及测试覆盖；确定性估算验证 29/30 turn、69/70/94.9/95% |
| 一致性 | 采用既有 owner scope、模型工厂、配置组装和错误目录；摘要与 append 同事务 |

## 需求与证据

| 需求 | 实现 | 验证 |
| --- | --- | --- |
| 独立记忆状态与 API | 0009_session_memory.py、memory/sqlite/chat.py、chat_contracts.py、chat_api.py | test_owner_and_session_isolation、test_capability_error_no_write、前端 chatStore 与契约测试 |
| 三模式与完整边界 | session_memory.py 的 prepare_append、complete_prefix | test_trigger_boundaries、test_failed_user_does_not_count_or_block_future_turns、test_manual_boundary_history_and_current_catalog |
| 可追溯摘要与保留历史 | session_memory.py 的 _compact、context_messages | test_compaction_failure_rolls_back、test_automatic_failure_has_no_partial_write、test_chunked_summary_calls_stay_below_hard_limit、test_stream_uses_summary_and_keeps_full_history |
| 写入前预算与共享错误 | estimate_context_tokens、ChatRepository.prepare_append、Agent before_model、共享 ERROR_CATALOG | test_pure_estimator_delegates、test_rejection_atomic_and_http_sse_same_error、test_auto_compaction_then_limit_rolls_back、capability 测试 |

## 门禁结果

- migration：临时库 0008 → head → 0008 → head；既有消息与字段默认值验证通过。未操作开发者真实数据库。
- 后端：Ruff 通过；strict Pyright 0 errors；pytest 123 passed。
- 契约：typecheck 通过；5 项测试通过。
- 前端：typecheck、24 项测试、build、security 全部通过。
- 桌面：1440×900 浏览器接口夹具检查通过，包含布局、溢出和控制台；P17 不新增 composer UI。
- foundation：6 项测试通过。docs build 与 security 通过。
- OpenSpec validate --all：同步主规范前 20/20、同步后 21/21 通过；git diff --check 通过。

## 设计修订与结论

复核发现“只允许连续配对前缀”会让失败问题永久阻断后续压缩，已同步修改 design、spec 和实现：失败问题不计 turn，以最后完整 assistant 为边界，保留尾部未回答消息。长历史分块策略也已补入设计和规范。

无 CRITICAL、WARNING 或待修复建议。模型交互使用注入 HTTP transport 验证，没有将替身测试描述为真实在线 Qwen 验收。已知设计取舍：token 为近似估算；压缩期间持有 SQLite 写锁。满足归档条件。
