"""从已合并的项目配置提取百炼模型设置。"""

from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    HttpUrl,
    SecretStr,
    ValidationError,
    field_validator,
)

from super_ai.project_config import ConfigError, JsonObject


class ModelCapability(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True)
    contextWindowTokens: int = Field(gt=0)


class QwenConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    provider: Literal["qwen"] = "qwen"
    apiKey: SecretStr
    baseUrl: HttpUrl
    rerankUrl: HttpUrl
    chatModel: str = Field(default="qwen3.7-max", min_length=1)
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout: float = Field(default=120, gt=0, allow_inf_nan=False)
    retries: int = Field(default=2, ge=0)

    @field_validator("apiKey")
    @classmethod
    def require_api_key(cls, value: SecretStr) -> SecretStr:
        if not value.get_secret_value().strip():
            raise ValueError("缺少 API key")
        return value

    @field_validator("baseUrl", "rerankUrl")
    @classmethod
    def require_plain_endpoint(cls, value: HttpUrl) -> HttpUrl:
        if value.username or value.password or value.query or value.fragment:
            raise ValueError("端点不能包含凭据、查询或片段")
        return value


class ModelConfig(BaseModel):
    model_config = ConfigDict(strict=True, hide_input_in_errors=True)
    llm: QwenConfig
    modelCapabilities: dict[str, ModelCapability]

    @classmethod
    def from_project(cls, config: JsonObject) -> "ModelConfig":
        try:
            settings = cls.model_validate(config)
        except ValidationError as exc:
            # 只报告已知字段，避免回显用户控制的键或值。
            known = {"llm", "modelCapabilities", *QwenConfig.model_fields}
            fields = {
                ".".join(str(part) for part in error["loc"][:2] if part in known)
                for error in exc.errors(include_input=False, include_context=False)
            }
            message = "模型配置缺失或无效：" + "、".join(sorted(fields))
        else:
            if settings.llm.chatModel in settings.modelCapabilities:
                return settings
            message = "modelCapabilities 缺少所选对话模型的 contextWindowTokens"
        raise ConfigError(message)
