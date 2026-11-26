import json
from contextlib import nullcontext
from hashlib import sha256
from typing import cast
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession

from super_ai.alert_inputs import redact
from super_ai.diagnostic_case_contracts import DiagnosticCase
from super_ai.diagnostic_case_source import case_fields, source_metadata, successful_source
from super_ai.document_api import default_knowledge_base_id
from super_ai.document_contracts import FixedCharacterConfig
from super_ai.memory.sqlite.diagnostic_cases import DiagnosticCaseRepository, cases
from super_ai.memory.sqlite.documents import DocumentRepository
from super_ai.memory.sqlite.index_tasks import IndexTasks
from super_ai.memory.sqlite.jobs import JobRepository, job_utc_now
from super_ai.project_config import JsonObject
from super_ai.tenant import OwnerScope


class DiagnosisCasePersistor:
    """Automatic source-task idempotency; the legacy API deliberately does not use this service."""

    def __init__(
        self,
        jobs: JobRepository,
        documents: DocumentRepository,
        secrets: tuple[str, ...] = (),
    ) -> None:
        self.jobs, self.documents, self.secrets = jobs, documents, secrets
        self.indexing = IndexTasks(jobs)

    async def on_succeeded(self, db: AsyncSession, job: RowMapping) -> None:
        if job["status"] != "succeeded" or job["resource_type"] != "diagnostic_task":
            return
        owner = str(job["owner_user_id"])
        await self.persist(OwnerScope(owner, owner), str(job["resource_id"]), transaction=db)

    async def persist(
        self,
        scope: OwnerScope,
        task_id: str,
        *,
        transaction: AsyncSession | None = None,
    ) -> DiagnosticCase | None:
        async with (
            self.jobs.factory.begin() if transaction is None else nullcontext(transaction)
        ) as db:
            if transaction is None:
                await db.execute(text("BEGIN IMMEDIATE"))
            source = await successful_source(db, scope, task_id)
            if source is None:
                return None
            existing = await DiagnosticCaseRepository.for_task(db, scope, task_id)
            if existing is not None:
                return DiagnosticCase.model_validate(existing)
            fields = cast(JsonObject, redact(case_fields(source), self.secrets))
            metadata = source_metadata(source, "diagnostic-case")
            body = "\n".join(
                [
                    "# 诊断故障案例",
                    "",
                    "## 来源",
                    "```json",
                    json.dumps(metadata, ensure_ascii=False, indent=2),
                    "```",
                    "",
                    "## 告警与服务",
                    f"告警：{fields['alert_name'] or '未提供匹配告警'}",
                    f"服务：{fields['service'] or '未提供服务'}",
                    "",
                    "## 关键词",
                    json.dumps(fields["keywords"], ensure_ascii=False),
                    "",
                    "## 摘要",
                    str(fields["summary"]),
                    "",
                    "## 根因结论",
                    str(fields["root_cause"]),
                    "",
                    "## 处理建议（不表示已执行）",
                    str(fields["remediation"]),
                    "",
                    "## 证据快照",
                    json.dumps(metadata["sourceEvidenceIds"], ensure_ascii=False),
                    "未关联证据时不能据此确认根因。",
                    "",
                    "## 原始诊断报告",
                    str(source.report["content"]),
                ]
            )
            body = cast(str, redact(body, self.secrets))
            kb = default_knowledge_base_id(scope)
            document = await self.documents.add(
                scope,
                kb,
                filename=f"diagnostic-case-{task_id}.md",
                size=len(body.encode("utf-8")),
                mime_type="text/markdown",
                sha256=sha256(body.encode("utf-8")).hexdigest(),
                chunking=FixedCharacterConfig(),
                body=body,
                overwrite=False,
                metadata=metadata,
                transaction=db,
            )
            index_task = await self.indexing.create(scope, kb, str(document["id"]), transaction=db)
            if index_task is None:
                raise LookupError("案例文档无法调度索引")
            row = (
                (
                    await db.execute(
                        cases.insert()
                        .values(
                            id=str(uuid4()),
                            owner_user_id=scope.owner_user_id,
                            task_id=task_id,
                            report_id=str(source.report["id"]),
                            document_id=str(document["id"]),
                            index_task_id=str(index_task["id"]),
                            created_at=job_utc_now(),
                            **fields,
                        )
                        .returning(*cases.c)
                    )
                )
                .mappings()
                .one()
            )
            return DiagnosticCase.model_validate(row)
