import secrets
from hashlib import sha256
from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from pwdlib import PasswordHash
from sqlalchemy import Column, DateTime, ForeignKey, String, Table, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from super_ai.memory.base import Base, utc_now

users = Table(
    "users",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("email", String(320), nullable=False, unique=True),
    Column("password_hash", String(512), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
)
auth_sessions = Table(
    "auth_sessions",
    Base.metadata,
    Column("id", String(36), primary_key=True),
    Column("user_id", String(36), ForeignKey("users.id"), nullable=False),
    Column("token_hash", String(64), unique=True, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), nullable=False),
    Column("revoked_at", DateTime(timezone=True)),
)

passwords = PasswordHash.recommended()
DUMMY_HASH = passwords.hash("dummy-auth-password")


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def token_digest(token: str) -> str:
    return sha256(token.encode()).hexdigest()


class AuthService:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.factory = session_factory

    async def register(self, email: str, password: str) -> dict[str, str]:
        normalized, now, uid = normalize_email(email), utc_now(), str(uuid4())
        async with self.factory() as s:
            try:
                await s.execute(
                    users.insert().values(
                        id=uid,
                        email=normalized,
                        password_hash=passwords.hash(password),
                        created_at=now,
                    )
                )
                await s.commit()
            except IntegrityError:
                await s.rollback()
                raise HTTPException(409, "邮箱已注册") from None
        return {"id": uid, "email": normalized}

    async def login(self, email: str, password: str) -> tuple[str, dict[str, str]]:
        async with self.factory() as s:
            row = (
                (await s.execute(select(users).where(users.c.email == normalize_email(email))))
                .mappings()
                .first()
            )
            valid = passwords.verify(password, row["password_hash"] if row else DUMMY_HASH)
            if not row or not valid:
                raise HTTPException(401, "AUTH_INVALID_CREDENTIALS")
            token, now = secrets.token_urlsafe(48), utc_now()
            await s.execute(
                auth_sessions.insert().values(
                    id=str(uuid4()),
                    user_id=row["id"],
                    token_hash=token_digest(token),
                    created_at=now,
                    last_seen_at=now,
                )
            )
            await s.commit()
            return token, {"id": row["id"], "email": row["email"]}

    async def current(self, token: str) -> dict[str, str] | None:
        async with self.factory() as s:
            row = (
                (
                    await s.execute(
                        select(users, auth_sessions.c.id.label("sid"))
                        .join(auth_sessions, users.c.id == auth_sessions.c.user_id)
                        .where(
                            auth_sessions.c.token_hash == token_digest(token),
                            auth_sessions.c.revoked_at.is_(None),
                        )
                    )
                )
                .mappings()
                .first()
            )
            if not row:
                return None
            await s.execute(
                update(auth_sessions)
                .where(auth_sessions.c.id == row["sid"])
                .values(last_seen_at=utc_now())
            )
            await s.commit()
            return {"id": row["id"], "email": row["email"]}

    async def logout(self, token: str) -> None:
        async with self.factory() as s:
            await s.execute(
                update(auth_sessions)
                .where(auth_sessions.c.token_hash == token_digest(token))
                .values(revoked_at=utc_now())
            )
            await s.commit()


def get_auth_service(request: Request) -> AuthService:
    return AuthService(request.app.state.db_session_factory)


async def current_user(
    request: Request, service: AuthService = Depends(get_auth_service)
) -> dict[str, str]:
    header = request.headers.get("Authorization", "")
    user = await service.current(header[7:]) if header.startswith("Bearer ") else None
    if not user:
        raise HTTPException(401, "需要认证")
    return user
