import json
from collections.abc import Iterable

from super_ai.tenant import require_owner_user_id


def _literal(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def milvus_search_filter(*, tenant_id: str, allowed_knowledge_base_ids: Iterable[str]) -> str:
    require_owner_user_id(tenant_id.strip())
    ids = [_literal(value) for value in allowed_knowledge_base_ids if value.strip()]
    if not ids:
        return ""
    return f"tenantId == {_literal(tenant_id)} and knowledgeBaseId in [{', '.join(ids)}]"


def milvus_delete_filter(*, tenant_id: str, knowledge_base_id: str, document_id: str) -> str:
    require_owner_user_id(tenant_id.strip())
    if not knowledge_base_id.strip() or not document_id.strip():
        raise ValueError("删除 scope 不能为空")
    return (
        f"tenantId == {_literal(tenant_id)} and knowledgeBaseId == {_literal(knowledge_base_id)} "
        f"and documentId == {_literal(document_id)}"
    )


def vector_metadata(*, tenant_id: str, owner_user_id: str, **extra: object) -> dict[str, object]:
    require_owner_user_id(tenant_id)
    require_owner_user_id(owner_user_id)
    if tenant_id != owner_user_id:
        raise ValueError("tenant 与 owner 必须一致")
    return {"tenantId": tenant_id, "ownerUserId": owner_user_id, **extra}
