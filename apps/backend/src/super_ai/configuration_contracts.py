from pydantic import BaseModel, ConfigDict, Field, JsonValue, field_validator


class PromptInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    label: str = Field(min_length=1, max_length=100)
    content: str = Field(min_length=1, max_length=65536)

    @field_validator("label", "content")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("内容不能为空白")
        return value


class UserPrompt(PromptInput):
    id: str


class UserSkill(BaseModel):
    id: str
    filename: str
    name: str
    description: str
    summary: str
    content: str
    metadata: dict[str, JsonValue]


class ConfigurationInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selectedPromptId: str | None
    selectedSkillIds: list[str] = Field(max_length=100)

    @field_validator("selectedSkillIds")
    @classmethod
    def unique_ids(cls, value: list[str]) -> list[str]:
        if len(value) != len(set(value)):
            raise ValueError("Skill 选择不能重复")
        return value


class ChatConfiguration(ConfigurationInput):
    prompts: list[UserPrompt]
    skills: list[UserSkill]
