from datetime import datetime, timezone

from pydantic import BaseModel, ConfigDict, field_validator
from pydantic.alias_generators import to_camel


class DiagnosticCase(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)

    id: str
    owner_user_id: str
    task_id: str
    report_id: str
    document_id: str
    index_task_id: str
    alert_name: str
    service: str
    keywords: list[str]
    root_cause: str
    remediation: str
    summary: str
    evidence_ids: list[str]
    created_at: datetime

    @field_validator("created_at")
    @classmethod
    def utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc)


class SavedDiagnosisKnowledge(BaseModel):
    documentId: str
    indexTaskId: str
    knowledgeBaseId: str
