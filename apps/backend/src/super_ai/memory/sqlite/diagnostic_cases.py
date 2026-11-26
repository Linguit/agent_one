from sqlalchemy import JSON, DateTime, String, column, select, table
from sqlalchemy.engine import RowMapping
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.diagnostic_case_contracts import DiagnosticCase
from super_ai.tenant import OwnerScope

cases = table(
    "aiops_diagnostic_cases",
    *[
        column(name, String)
        for name in (
            "id",
            "owner_user_id",
            "task_id",
            "report_id",
            "document_id",
            "index_task_id",
            "alert_name",
            "service",
            "root_cause",
            "remediation",
            "summary",
        )
    ],
    column("keywords", JSON),
    column("evidence_ids", JSON),
    column("created_at", DateTime),
)


class DiagnosticCaseRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self.factory = factory

    async def list_cases(self, scope: OwnerScope) -> list[DiagnosticCase]:
        async with self.factory() as db:
            rows = (
                await db.execute(
                    select(cases)
                    .where(
                        cases.c.owner_user_id == scope.owner_user_id,
                    )
                    .order_by(cases.c.created_at.desc(), cases.c.id)
                )
            ).mappings()
            return [DiagnosticCase.model_validate(row) for row in rows]

    async def get(self, scope: OwnerScope, id: str) -> DiagnosticCase | None:
        async with self.factory() as db:
            row = (
                (
                    await db.execute(
                        select(cases).where(
                            cases.c.owner_user_id == scope.owner_user_id,
                            cases.c.id == id,
                        )
                    )
                )
                .mappings()
                .first()
            )
            return DiagnosticCase.model_validate(row) if row is not None else None

    @staticmethod
    async def for_task(db: AsyncSession, scope: OwnerScope, task_id: str) -> RowMapping | None:
        return (
            (
                await db.execute(
                    select(cases).where(
                        cases.c.owner_user_id == scope.owner_user_id,
                        cases.c.task_id == task_id,
                    )
                )
            )
            .mappings()
            .first()
        )
