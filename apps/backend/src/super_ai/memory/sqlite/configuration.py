from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import uuid4

from sqlalchemy import JSON, String, column, select, table, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.configuration_contracts import (
    ChatConfiguration,
    ConfigurationInput,
    PromptInput,
    UserPrompt,
    UserSkill,
)
from super_ai.memory.sqlite.chat import ChatAccessDenied
from super_ai.skill_format import SkillFormatError, parse_skill
from super_ai.tenant import OwnerScope

prompts = table(
    "user_chat_prompts",
    column("id", String),
    column("owner_user_id", String),
    column("label", String),
    column("content", String),
)
skills = table(
    "user_chat_skills",
    column("id", String),
    column("owner_user_id", String),
    column("filename", String),
    column("name", String),
    column("description", String),
    column("summary", String),
    column("content", String),
    column("metadata", JSON),
)
configurations = table(
    "user_chat_configurations",
    column("owner_user_id", String),
    column("selected_prompt_id", String),
    column("selected_skill_ids", JSON),
)


class ConfigurationRepository:
    def __init__(self, factory: async_sessionmaker[AsyncSession]) -> None:
        self._factory = factory

    @asynccontextmanager
    async def _transaction(self, *, write: bool) -> AsyncGenerator[AsyncSession]:
        async with self._factory.begin() as db:
            await db.execute(text("BEGIN IMMEDIATE" if write else "BEGIN"))
            yield db

    async def _read(self, db: AsyncSession, scope: OwnerScope) -> ChatConfiguration:
        owner = scope.owner_user_id
        row = (
            (
                await db.execute(
                    select(configurations).where(configurations.c.owner_user_id == owner)
                )
            )
            .mappings()
            .one_or_none()
        )
        prompt_rows = (
            (
                await db.execute(
                    select(prompts).where(prompts.c.owner_user_id == owner).order_by(prompts.c.id)
                )
            )
            .mappings()
            .all()
        )
        skill_rows = (
            (
                await db.execute(
                    select(skills).where(skills.c.owner_user_id == owner).order_by(skills.c.name)
                )
            )
            .mappings()
            .all()
        )
        return ChatConfiguration(
            selectedPromptId=row["selected_prompt_id"] if row else None,
            selectedSkillIds=row["selected_skill_ids"] if row else [],
            prompts=[
                UserPrompt(id=item["id"], label=item["label"], content=item["content"])
                for item in prompt_rows
            ],
            skills=[UserSkill.model_validate(dict(item)) for item in skill_rows],
        )

    async def get(self, scope: OwnerScope) -> ChatConfiguration:
        async with self._transaction(write=False) as db:
            return await self._read(db, scope)

    async def _write(
        self, db: AsyncSession, scope: OwnerScope, selection: ConfigurationInput
    ) -> None:
        # Explicit owner predicate for every update; the write transaction serializes deletes.
        await db.execute(
            configurations.delete().where(configurations.c.owner_user_id == scope.owner_user_id)
        )
        await db.execute(
            configurations.insert().values(
                owner_user_id=scope.owner_user_id,
                selected_prompt_id=selection.selectedPromptId,
                selected_skill_ids=selection.selectedSkillIds,
            )
        )

    async def put(self, scope: OwnerScope, selection: ConfigurationInput) -> ChatConfiguration:
        async with self._transaction(write=True) as db:
            config = await self._read(db, scope)
            if (
                selection.selectedPromptId is not None
                and selection.selectedPromptId not in {p.id for p in config.prompts}
            ) or not set(selection.selectedSkillIds) <= {s.id for s in config.skills}:
                raise ChatAccessDenied
            await self._write(db, scope, selection)
            return await self._read(db, scope)

    async def save_prompt(
        self, scope: OwnerScope, body: PromptInput, prompt_id: str | None = None
    ) -> UserPrompt:
        async with self._transaction(write=True) as db:
            values = body.model_dump()
            if prompt_id is None:
                prompt_id = str(uuid4())
                await db.execute(
                    prompts.insert().values(
                        id=prompt_id, owner_user_id=scope.owner_user_id, **values
                    )
                )
            else:
                result = await db.execute(
                    prompts.update()
                    .where(
                        prompts.c.id == prompt_id, prompts.c.owner_user_id == scope.owner_user_id
                    )
                    .values(**values)
                    .returning(prompts.c.id)
                )
                if result.scalar_one_or_none() is None:
                    raise ChatAccessDenied
            return UserPrompt(id=prompt_id, **values)

    async def upload(self, scope: OwnerScope, filename: str | None, data: bytes) -> UserSkill:
        name, description, metadata, content = parse_skill(filename, data)
        async with self._transaction(write=True) as db:
            existing = await db.execute(
                select(skills.c.id).where(
                    skills.c.owner_user_id == scope.owner_user_id, skills.c.name == name
                )
            )
            if existing.first() is not None:
                raise SkillFormatError("当前用户已存在同名 Skill")
            skill = UserSkill(
                id=str(uuid4()),
                filename="SKILL.md",
                name=name,
                description=description,
                summary=description,
                content=content,
                metadata=metadata,
            )
            await db.execute(
                skills.insert().values(owner_user_id=scope.owner_user_id, **skill.model_dump())
            )
            return skill

    async def delete(self, scope: OwnerScope, asset_id: str, *, skill: bool) -> None:
        async with self._transaction(write=True) as db:
            config = await self._read(db, scope)
            assets = config.skills if skill else config.prompts
            if asset_id not in {asset.id for asset in assets}:
                raise ChatAccessDenied
            if skill:
                config.selectedSkillIds = [i for i in config.selectedSkillIds if i != asset_id]
            elif config.selectedPromptId == asset_id:
                config.selectedPromptId = None
            await self._write(db, scope, config)
            asset_table = skills if skill else prompts
            await db.execute(
                asset_table.delete().where(
                    asset_table.c.owner_user_id == scope.owner_user_id, asset_table.c.id == asset_id
                )
            )

    async def load(self, scope: OwnerScope, skill_id: str, name: str) -> str:
        config = await self.get(scope)
        for skill in config.skills:
            if skill.id == skill_id and skill.name == name and skill.id in config.selectedSkillIds:
                return skill.content
        raise ChatAccessDenied
