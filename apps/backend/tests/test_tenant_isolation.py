import pytest

from super_ai.tenant import ScopeError, require_owner_user_id
from super_ai.vector_scope import milvus_delete_filter, milvus_search_filter, vector_metadata


class Repo:
    def __init__(self):
        self.rows = {"a": {"owner": "u1", "value": 1}}

    def read(self, rid: str, *, owner_user_id: str) -> dict[str, str | int] | None:
        require_owner_user_id(owner_user_id)
        row = self.rows.get(rid)
        return row if row and row["owner"] == owner_user_id else None

    def update(self, rid: str, *, owner_user_id: str, value: int) -> dict[str, str | int] | None:
        row = self.read(rid, owner_user_id=owner_user_id)
        if row is None:
            return None
        row["value"] = value
        return row

    def delete(self, rid: str, *, owner_user_id: str) -> bool:
        row = self.read(rid, owner_user_id=owner_user_id)
        if row is None:
            return False
        del self.rows[rid]
        return True


def test_cross_user_read_update_delete_are_non_enumerable():
    repo = Repo()
    assert repo.read("a", owner_user_id="u2") is None
    assert repo.update("a", owner_user_id="u2", value=9) is None
    assert repo.delete("a", owner_user_id="u2") is False
    row = repo.read("a", owner_user_id="u1")
    assert row is not None
    assert row["value"] == 1


def test_empty_scope_and_vector_filters_fail_closed():
    with pytest.raises(ScopeError):
        require_owner_user_id("")
    assert milvus_search_filter(tenant_id="u1", allowed_knowledge_base_ids=[]) == ""
    assert "tenantId" in milvus_delete_filter(
        tenant_id="u1", knowledge_base_id="kb", document_id="doc"
    )
    assert vector_metadata(tenant_id="u1", owner_user_id="u1")["ownerUserId"] == "u1"
