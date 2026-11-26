import re
from dataclasses import dataclass
from typing import cast

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.diagnostic_contracts import DIAGNOSTIC_KIND
from super_ai.memory.sqlite.diagnostic_schema import checkpoints, evidence, reports, tasks
from super_ai.memory.sqlite.job_schema import jobs
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope


@dataclass(frozen=True)
class DiagnosisSource:
    task: RowMapping
    report: RowMapping
    evidence: list[RowMapping]


async def successful_source(
    db: AsyncSession,
    scope: OwnerScope,
    task_id: str,
) -> DiagnosisSource | None:
    task = (
        (
            await db.execute(
                select(tasks).where(
                    tasks.c.owner_user_id == scope.owner_user_id,
                    tasks.c.id == task_id,
                )
            )
        )
        .mappings()
        .first()
    )
    if task is None:
        return None
    job = (
        (
            await db.execute(
                select(jobs)
                .where(
                    jobs.c.owner_user_id == scope.owner_user_id,
                    jobs.c.resource_id == task_id,
                    jobs.c.resource_type == "diagnostic_task",
                    jobs.c.kind == DIAGNOSTIC_KIND,
                )
                .order_by(jobs.c.created_at.desc(), jobs.c.id.desc())
                .limit(1)
            )
        )
        .mappings()
        .first()
    )
    if job is None or job["status"] != "succeeded":
        return None
    report = (
        (
            await db.execute(
                select(reports)
                .where(
                    reports.c.owner_user_id == scope.owner_user_id,
                    reports.c.task_id == task_id,
                )
                .order_by(reports.c.created_at.desc(), reports.c.id.desc())
                .limit(1)
            )
        )
        .mappings()
        .first()
    )
    if report is None or not str(report["content"]).strip():
        return None
    final = await db.scalar(
        select(checkpoints.c.id)
        .where(
            checkpoints.c.owner_user_id == scope.owner_user_id,
            checkpoints.c.task_id == task_id,
            checkpoints.c.job_id == report["job_id"],
            checkpoints.c.next_node == "end",
        )
        .limit(1)
    )
    if final is None:
        return None
    rows = list(
        (
            await db.execute(
                select(evidence)
                .where(
                    evidence.c.owner_user_id == scope.owner_user_id,
                    evidence.c.task_id == task_id,
                )
                .order_by(evidence.c.created_at, evidence.c.id)
            )
        ).mappings()
    )
    return DiagnosisSource(task, report, rows)


def source_metadata(source: DiagnosisSource, knowledge_type: str) -> JsonObject:
    return {
        "knowledgeType": knowledge_type,
        "sourceDiagnosticTaskId": str(source.task["id"]),
        "sourceReportId": str(source.report["id"]),
        "sourceEvidenceIds": [str(row["id"]) for row in source.evidence],
    }


def report_section(markdown: str, title: str) -> str:
    pieces = re.findall(
        r"^###\s+" + re.escape(title) + r"\s*\n(.*?)(?=^#{1,3}\s|\Z)",
        markdown,
        re.M | re.S,
    )
    return "\n\n".join(dict.fromkeys(piece.strip() for piece in pieces if piece.strip()))


def case_fields(source: DiagnosisSource) -> JsonObject:
    report = str(source.report["content"])
    alerts = [
        cast(JsonObject, row["content"])
        for row in source.evidence
        if row["kind"] == "alert" and isinstance(row["content"], dict)
    ]
    names = list(
        dict.fromkeys(str(alert["alertname"]) for alert in alerts if alert.get("alertname"))
    )
    services = list(
        dict.fromkeys(str(alert["service"]) for alert in alerts if alert.get("service"))
    )
    query = str(cast(JsonObject, source.task["safe_input"]).get("query", ""))
    root = report_section(report, "根因结论") or "报告未提供可确认根因。"
    remediation = report_section(report, "建议") or "报告未提供处理建议。"
    summary = (
        report_section(report, "整体评估") or report_section(report, "关键发现") or report[:2000]
    )
    keywords = list(
        dict.fromkeys(
            re.findall(
                r"[A-Za-z][\w.-]*|[\u3400-\u9fff]{2,12}",
                " ".join([*names, *services, query]),
            )
        )
    )[:30]
    return {
        "alert_name": "、".join(names),
        "service": "、".join(services),
        "keywords": keywords,
        "root_cause": root,
        "remediation": remediation,
        "summary": summary,
        "evidence_ids": [str(row["id"]) for row in source.evidence],
    }
