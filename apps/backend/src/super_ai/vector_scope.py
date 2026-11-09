from collections.abc import Iterable

from .tenant import require_owner_user_id


def milvus_search_filter(*, tenant_id: str, allowed_knowledge_base_ids: Iterable[str]) -> str:
    require_owner_user_id(tenant_id)
    ids = [x for x in allowed_knowledge_base_ids if x]
    return (
        ""
        if not ids
        else f"tenantId == {tenant_id!r} and knowledgeBaseId in [{', '.join(repr(x) for x in ids)}]"
    )


def milvus_delete_filter(*, tenant_id: str, knowledge_base_id: str, document_id: str) -> str:
    require_owner_user_id(tenant_id)
    if not knowledge_base_id or not document_id:
        raise ValueError("删除 scope 不能为空")
    return (
        f"tenantId == {tenant_id!r} and knowledgeBaseId == {knowledge_base_id!r} "
        f"and documentId == {document_id!r}"
    )


def vector_metadata(*, tenant_id: str, owner_user_id: str, **extra: object) -> dict[str, object]:
    require_owner_user_id(tenant_id)
    require_owner_user_id(owner_user_id)
    if tenant_id != owner_user_id:
        raise ValueError("tenant 与 owner 必须一致")
    return {"tenantId": tenant_id, "ownerUserId": owner_user_id, **extra}
