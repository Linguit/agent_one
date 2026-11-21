from email.message import Message
from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request, UploadFile
from fastapi.security import HTTPBearer
from starlette.responses import Response

from super_ai.chat_api import Owner
from super_ai.chat_contracts import ChatDeleted, ChatEnvelope
from super_ai.configuration_contracts import (
    ChatConfiguration,
    ConfigurationInput,
    PromptInput,
    UserPrompt,
    UserSkill,
)
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.memory.sqlite.chat import ChatAccessDenied
from super_ai.memory.sqlite.configuration import ConfigurationRepository
from super_ai.skill_format import MAX_SKILL_BYTES, SkillFormatError


def _repository(request: Request) -> ConfigurationRepository:
    return cast(ConfigurationRepository, request.app.state.chat_configuration)


Repository = Annotated[ConfigurationRepository, Depends(_repository)]
router = APIRouter(
    prefix="/chat",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={status: {"model": FailureEnvelope} for status in (401, 403, 422, 500)},
)


@router.get("/configuration", response_model=ChatEnvelope[ChatConfiguration])
async def get_configuration(request: Request, scope: Owner, repo: Repository) -> Response:
    return success((await repo.get(scope)).model_dump(mode="json"), request)


@router.put("/configuration", response_model=ChatEnvelope[ChatConfiguration])
async def put_configuration(
    body: ConfigurationInput, request: Request, scope: Owner, repo: Repository
) -> Response:
    try:
        config = await repo.put(scope, body)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(config.model_dump(mode="json"), request)


@router.post("/prompts", response_model=ChatEnvelope[UserPrompt])
async def create_prompt(
    body: PromptInput, request: Request, scope: Owner, repo: Repository
) -> Response:
    return success((await repo.save_prompt(scope, body)).model_dump(mode="json"), request)


@router.put("/prompts/{id}", response_model=ChatEnvelope[UserPrompt])
async def update_prompt(
    id: str, body: PromptInput, request: Request, scope: Owner, repo: Repository
) -> Response:
    try:
        prompt = await repo.save_prompt(scope, body, id)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(prompt.model_dump(mode="json"), request)


@router.post("/skills", response_model=ChatEnvelope[UserSkill])
async def upload_skill(
    file: UploadFile, request: Request, scope: Owner, repo: Repository
) -> Response:
    try:
        # Multipart parsers strip Windows paths for legacy browsers; validate the raw header too.
        disposition = Message()
        disposition["Content-Disposition"] = file.headers.get("content-disposition", "")
        parameters = disposition.get_params(header="content-disposition", failobj=[])
        if (
            disposition.get_filename() != "SKILL.md"
            or sum(key == "filename" for key, _ in parameters) != 1
        ):
            raise SkillFormatError("文件名必须严格为 SKILL.md")
        data = await file.read(MAX_SKILL_BYTES + 1)
        skill = await repo.upload(scope, file.filename, data)
    except SkillFormatError:
        return failure("VALIDATION_INVALID_REQUEST", request)
    finally:
        await file.close()
    return success(skill.model_dump(mode="json"), request)


@router.delete("/prompts/{id}", response_model=ChatEnvelope[ChatDeleted])
async def delete_prompt(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    return await _delete(id, request, scope, repo, skill=False)


@router.delete("/skills/{id}", response_model=ChatEnvelope[ChatDeleted])
async def delete_skill(id: str, request: Request, scope: Owner, repo: Repository) -> Response:
    return await _delete(id, request, scope, repo, skill=True)


async def _delete(
    id: str, request: Request, scope: Owner, repo: Repository, *, skill: bool
) -> Response:
    try:
        await repo.delete(scope, id, skill=skill)
    except ChatAccessDenied:
        return failure("AUTH_FORBIDDEN", request)
    return success(ChatDeleted().model_dump(mode="json"), request)
