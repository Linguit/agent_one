from dataclasses import dataclass
from typing import Any, Protocol


class ScopeError(ValueError):
    pass


@dataclass(frozen=True)
class CurrentUser:
    user_id: str
    email: str | None = None

    @property
    def tenant_id(self) -> str:
        return self.user_id


@dataclass(frozen=True)
class OwnerScope:
    owner_user_id: str
    tenant_id: str

    def __post_init__(self):
        if not self.owner_user_id or self.owner_user_id != self.tenant_id:
            raise ScopeError("invalid owner scope")

    @classmethod
    def from_user(cls, user: CurrentUser):
        return cls(user.user_id, user.tenant_id)


class ScopedRepository(Protocol):
    async def get(self, record_id: Any, *, owner_user_id: str) -> Any: ...


def require_owner_user_id(owner_user_id: str) -> str:
    if not owner_user_id:
        raise ScopeError("owner_user_id 不能为空")
    return owner_user_id
