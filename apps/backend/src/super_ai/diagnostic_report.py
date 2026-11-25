from __future__ import annotations

import json
from typing import TYPE_CHECKING, cast

from super_ai.diagnostic_contracts import Finding, ReportDraft
from super_ai.job_runtime import JobContext
from super_ai.memory.sqlite.diagnostic_schema import checkpoints, links, reports
from super_ai.project_config import JsonObject

if TYPE_CHECKING:
    from super_ai.diagnostic_runtime import DiagnosticRunner


async def build_report(runner: DiagnosticRunner, context: JobContext, state: JsonObject) -> None:
    repo = runner.repo
    chain = await repo.chain(context.scope, str(context.job["resource_id"]))
    items = cast(list[JsonObject], chain["evidence"])
    allowed = {str(item["id"]) for item in items}
    alert_ids = {str(item["id"]) for item in items if item["kind"] == "alert"}
    mode = "model"
    try:
        if not any(item["kind"] == "log" for item in items):
            raise ValueError("没有日志证据，使用保守 fallback")
        draft = cast(
            ReportDraft,
            await runner.ask(
                ReportDraft,
                "根据 alert、SOP、plan 和真实 evidence 生成中文诊断分析。每条关键发现必须引用"
                "对应 evidenceIds；逐条覆盖告警，alertEvidenceId 必须是对应告警证据 ID。"
                "区分相关性与因果、明确不确定性；没有实际日志不得确认根因。"
                "建议是待执行事项，不得声称已修复。",
                {"plan": state.get("plan"), "evidence": chain["evidence"], "steps": chain["steps"]},
            ),
        )
        if any(not set(f.evidenceIds) <= allowed for f in draft.findings):
            raise ValueError("无效证据引用")
        if alert_ids and ({f.alertEvidenceId for f in draft.findings} != alert_ids):
            raise ValueError("告警与结论映射不完整")
        if any(
            f.alertEvidenceId is not None
            and (f.alertEvidenceId not in alert_ids or f.alertEvidenceId not in f.evidenceIds)
            for f in draft.findings
        ):
            raise ValueError("告警结论缺少对应告警引用")
        draft = ReportDraft.model_validate(runner.clean(draft))
    except Exception:
        mode = "fallback"
        draft = (
            ReportDraft(
                findings=[
                    Finding(
                        text="已保存真实输入与工具返回；证据不足，无法确认根因，需人工核验。",
                        evidenceIds=([alert_id] if alert_id else [])
                        + [id for id in sorted(allowed) if id != alert_id][:29],
                        alertEvidenceId=alert_id,
                    )
                    for alert_id in (sorted(alert_ids) if alert_ids else [None])
                ]
                if allowed
                else [],
                recommendation="补充时间范围、日志及监控数据，由运维人员核验后再处理。",
            )
            if allowed
            else None
        )
    alerts = [item for item in items if item["kind"] == "alert"]
    logs = [item for item in items if item["kind"] == "log"]
    step_rows = cast(list[JsonObject], chain["steps"])
    completed = [row for row in step_rows if row["status"] == "completed"]
    findings = draft.findings if draft else []
    finding_text = (
        "\n".join(
            f"- {finding.text}（证据：{', '.join(finding.evidenceIds)}）" for finding in findings
        )
        or "证据不足，无法确认根因。"
    )
    recommendation = draft.recommendation if draft else "补充真实日志并人工核验。"
    lines = ["# 告警分析报告", "", "## 📋 活跃告警清单", ""]
    for alert in alerts:
        data = cast(JsonObject, alert["content"])
        lines.append(f"- {data.get('alertname')}（证据：{alert['id']}）")
    if not alerts:
        lines.append("当前真实告警快照未包含匹配告警；按查询诊断，不能据此推断系统正常。")
    for i, alert in enumerate(alerts or [None], 1):
        data = cast(JsonObject, alert["content"]) if alert else {}
        alert_findings = [
            finding
            for finding in findings
            if (finding.alertEvidenceId == (str(alert["id"]) if alert else None))
        ]
        root_text = (
            "\n".join(
                f"- {finding.text}（证据：{', '.join(finding.evidenceIds)}）"
                for finding in alert_findings
            )
            or "证据不足，无法确认该告警根因。"
        )
        annotations = data.get("annotations", {})
        symptoms = (
            json.dumps(annotations, ensure_ascii=False)
            if annotations
            else ("没有额外告警症状描述，未核实项保持不确定。")
        )
        lines.extend(
            [
                "",
                f"## 🔍 告警根因分析{i}",
                "",
                f"### 详情\n{data.get('alertname', '查询诊断（无匹配活跃告警）')}\n"
                f"服务：{data.get('service')}；级别：{data.get('severity')}；"
                f"状态：{data.get('status')}；起始时间：{data.get('startsAt')}。",
                "### 症状\n" + symptoms,
                "### 日志证据\n"
                + (
                    "\n".join(
                        f"- {row['source']}：证据 {row['id']}（真实返回，因果未确认）\n"
                        + "```json\n"
                        + json.dumps(row["content"], ensure_ascii=False)[:1000].replace(
                            "```", "'''"
                        )
                        + "\n```"
                        for row in logs[:10]
                    )
                    or "没有可用日志证据。"
                ),
                "### 根因结论\n" + root_text,
                f"\n## 🛠️ 处理方案执行{i}\n",
                "### 已执行步骤\n"
                + (
                    "\n".join(
                        f"- 诊断读取：{row['tool_name']}（审计 {row['audit_id']}）"
                        for row in completed
                    )
                    or "没有已完成的工具步骤。"
                ),
                "### 建议\n" + recommendation,
                "### 预期效果\n待建议执行并复测后评估；当前未执行自动修复。",
            ]
        )
    lines.extend(
        [
            "",
            "## 📊 结论",
            "",
            "### 整体评估\n诊断基于已存证据，根因仍需核验。",
            "### 关键发现\n" + finding_text,
            "### 后续建议\n" + recommendation,
            "### 风险评估\n证据覆盖、时间窗口与工具失败可能影响判断，不能将未发现视为不存在。",
        ]
    )
    content = cast(str, runner.clean("\n".join(lines)))
    async with repo.fenced(context) as db:
        report_id = await repo.insert(
            db,
            context,
            reports,
            {
                "job_id": context.id,
                "content": content,
                "mode": mode,
            },
        )
        for finding in findings:
            for evidence_id in finding.evidenceIds:
                await repo.insert(
                    db,
                    context,
                    links,
                    {
                        "report_id": report_id,
                        "evidence_id": evidence_id,
                        "claim": finding.text,
                    },
                )
        await repo.event(db, context, "report", {"content": content, "reportId": report_id})
        state["next"] = "end"
        await repo.insert(
            db,
            context,
            checkpoints,
            {
                "job_id": context.id,
                "state": state,
                "next_node": "end",
                "plan_version": state["version"],
            },
        )
