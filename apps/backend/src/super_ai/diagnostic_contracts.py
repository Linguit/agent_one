from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue

MAX_STEPS = 6
MAX_REPLANS = 3
DIAGNOSTIC_KIND = "aiops_diagnosis"
JobStatus = Literal["queued", "running", "succeeded", "failed", "cancelled"]
DiagnosticStatus = Literal["accepted", "running", "succeeded", "failed", "cancelled"]
STATUS_MAP: dict[str, str] = {"queued": "accepted"}


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", hide_input_in_errors=True)


class DiagnosticInput(StrictModel):
    query: str = Field(min_length=1, max_length=8000, pattern=r"\S")
    alertNames: list[str] = Field(default_factory=list, max_length=20)


class PlanStep(StrictModel):
    tool: str = Field(min_length=1)
    arguments: dict[str, JsonValue]
    purpose: str = Field(min_length=1, max_length=500)


class Plan(StrictModel):
    steps: list[PlanStep] = Field(min_length=1, max_length=MAX_STEPS)


class Replan(StrictModel):
    action: Literal["continue", "adjust", "report"]
    message: str = Field(max_length=500)
    steps: list[PlanStep] = Field(default_factory=lambda: [], max_length=MAX_STEPS)


class Finding(StrictModel):
    text: str = Field(min_length=1, max_length=2000)
    evidenceIds: list[str] = Field(min_length=1, max_length=30)
    alertEvidenceId: str | None = None


class ReportDraft(StrictModel):
    findings: list[Finding] = Field(min_length=1, max_length=20)
    recommendation: str = Field(min_length=1, max_length=2000)


class TaskProgress(StrictModel):
    message: str
    progress: float = Field(ge=0, le=1)


class TaskStatus(StrictModel):
    status: JobStatus
    task: TaskProgress


class StreamInput(StrictModel):
    jobId: str | None = None
    afterSequence: int = Field(default=0, ge=0)
