"""显式连接的 Milvus 向量适配器。"""

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Protocol, cast

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, ValidationError

from super_ai.project_config import ConfigError, JsonObject, JsonValue, load_project_config
from super_ai.tenant import OwnerScope
from super_ai.vector_scope import milvus_delete_filter, milvus_search_filter

VECTOR_DIMENSION = 1024
_OUTPUT_FIELDS = (
    "chunkId", "documentId", "knowledgeBaseId", "ownerUserId", "tenantId",
    "content", "source", "createdAt", "metadata",
)
_FILTER_FIELDS = ("documentId", "knowledgeBaseId", "ownerUserId", "tenantId", "createdAt")


class VectorStoreConfig(BaseModel):
    model_config = ConfigDict(strict=True, frozen=True, hide_input_in_errors=True)

    endpoint: HttpUrl
    token: SecretStr = SecretStr("")
    collectionName: str = Field(
        default="knowledge_chunks", pattern=r"^[a-zA-Z_][a-zA-Z0-9_]*$", max_length=255
    )

    @classmethod
    def from_project(cls, config: JsonObject) -> "VectorStoreConfig":
        try:
            settings = cls.model_validate(config.get("vectorStore"))
        except ValidationError:
            raise ConfigError("vectorStore 配置缺失或无效") from None
        url = settings.endpoint
        if url.username or url.password or url.query or url.fragment or url.path not in ("", "/"):
            raise ConfigError("vectorStore.endpoint 必须是 HTTP(S) 服务地址")
        return settings


@dataclass(frozen=True)
class VectorChunk:
    chunk_id: str
    document_id: str
    knowledge_base_id: str
    content: str
    source: str
    created_at: int
    metadata: JsonObject
    vector: Sequence[float]

    def to_row(self, scope: OwnerScope) -> dict[str, JsonValue]:
        if not all(value.strip() for value in (
            self.chunk_id, self.document_id, self.knowledge_base_id,
        )):
            raise ValueError("向量块、文档和知识库 ID 不能为空")
        if len(self.vector) != VECTOR_DIMENSION:
            raise ValueError("向量必须为 1024 维")
        return {
            "chunkId": self.chunk_id,
            "documentId": self.document_id,
            "knowledgeBaseId": self.knowledge_base_id,
            "ownerUserId": scope.owner_user_id,
            "tenantId": scope.tenant_id,
            "content": self.content,
            "source": self.source,
            "createdAt": self.created_at,
            "metadata": {
                **self.metadata,
                "ownerUserId": scope.owner_user_id,
                "tenantId": scope.tenant_id,
            },
            "vector": list(self.vector),
        }


class VectorClient(Protocol):
    def has_collection(self, collection_name: str) -> bool: ...
    def create_collection(
        self, collection_name: str, *, schema: object, consistency_level: str
    ) -> object: ...
    def list_indexes(self, collection_name: str) -> list[str]: ...
    def create_index(self, collection_name: str, index_params: object) -> object: ...
    def load_collection(self, collection_name: str) -> object: ...
    def get_server_version(self, *, timeout: float) -> str: ...
    def insert(self, collection_name: str, *, data: list[dict[str, JsonValue]]) -> object: ...
    def search(
        self,
        collection_name: str,
        *,
        data: list[list[float]],
        anns_field: str,
        filter: str,
        limit: int,
        output_fields: list[str],
        search_params: dict[str, JsonValue],
    ) -> Sequence[Sequence[Mapping[str, object]]]: ...
    def delete(self, collection_name: str, *, filter: str) -> object: ...


class _SchemaBuilder(Protocol):
    def add_field(self, field_name: str, datatype: object, **kwargs: object) -> object: ...


class _IndexBuilder(Protocol):
    def add_index(self, field_name: str, **kwargs: object) -> None: ...


class _MilvusBuilders(Protocol):
    def create_schema(self, *, auto_id: bool, enable_dynamic_field: bool) -> _SchemaBuilder: ...
    def prepare_index_params(self) -> _IndexBuilder: ...


def _connect(config: VectorStoreConfig) -> VectorClient:
    from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]

    return cast(VectorClient, MilvusClient(
        uri=str(config.endpoint).rstrip("/"), token=config.token.get_secret_value(), timeout=5
    ))


def _collection_schema() -> object:
    from pymilvus import DataType, MilvusClient  # pyright: ignore[reportMissingTypeStubs]

    builders = cast(_MilvusBuilders, MilvusClient)
    schema = builders.create_schema(auto_id=False, enable_dynamic_field=False)
    schema.add_field("chunkId", DataType.VARCHAR, is_primary=True, max_length=256)
    for name in ("documentId", "knowledgeBaseId", "ownerUserId", "tenantId"):
        schema.add_field(name, DataType.VARCHAR, max_length=256)
    schema.add_field("content", DataType.VARCHAR, max_length=65535)
    schema.add_field("source", DataType.VARCHAR, max_length=4096)
    schema.add_field("createdAt", DataType.INT64)
    schema.add_field("metadata", DataType.JSON)
    schema.add_field("vector", DataType.FLOAT_VECTOR, dim=VECTOR_DIMENSION)
    return schema


def _missing_indexes(existing: set[str]) -> object:
    from pymilvus import MilvusClient  # pyright: ignore[reportMissingTypeStubs]

    indexes = cast(_MilvusBuilders, MilvusClient).prepare_index_params()
    if "vector" not in existing:
        indexes.add_index(
            "vector", index_name="vector", index_type="HNSW", metric_type="COSINE",
            params={"M": 16, "efConstruction": 200},
        )
    for name in _FILTER_FIELDS:
        if name not in existing:
            indexes.add_index(name, index_name=name, index_type="INVERTED")
    return indexes


class MilvusVectorStore:
    def __init__(
        self,
        config: VectorStoreConfig,
        *,
        client_factory: Callable[[VectorStoreConfig], VectorClient] = _connect,
    ) -> None:
        self._config = config
        self._client_factory = client_factory
        self._client: VectorClient | None = None
        self._initialized = False
        self._lock = RLock()

    @classmethod
    def from_local_config(cls, config_dir: Path | None = None) -> "MilvusVectorStore":
        return cls(VectorStoreConfig.from_project(load_project_config(config_dir)))

    def connect(self) -> None:
        """连接服务，集合仍由 initialize 显式准备。"""
        self._connected_client()

    def _connected_client(self) -> VectorClient:
        with self._lock:
            if self._client is None:
                self._client = self._client_factory(self._config)
            return self._client

    def initialize(self) -> None:
        with self._lock:
            if self._initialized:
                return
            client = self._connected_client()
            collection = self._config.collectionName
            if not client.has_collection(collection):
                client.create_collection(
                    collection, schema=_collection_schema(), consistency_level="Strong"
                )
            existing = set(client.list_indexes(collection))
            if not {"vector", *_FILTER_FIELDS}.issubset(existing):
                client.create_index(collection, _missing_indexes(existing))
            client.load_collection(collection)
            self._initialized = True

    def health(self) -> bool:
        """检查服务连通性，不创建或加载集合。"""
        try:
            return bool(self._connected_client().get_server_version(timeout=5))
        except Exception:
            return False

    def _ready_client(self) -> VectorClient:
        with self._lock:
            if self._client is None or not self._initialized:
                raise RuntimeError("请先初始化 Milvus 向量集合")
            return self._client

    def insert(self, scope: OwnerScope, chunks: Sequence[VectorChunk]) -> object:
        rows = [chunk.to_row(scope) for chunk in chunks]
        if not rows:
            return None
        return self._ready_client().insert(self._config.collectionName, data=rows)

    def search(
        self,
        scope: OwnerScope,
        allowed_knowledge_base_ids: Sequence[str],
        vector: Sequence[float],
        *,
        limit: int = 10,
    ) -> list[Mapping[str, object]]:
        expression = milvus_search_filter(
            tenant_id=scope.tenant_id, allowed_knowledge_base_ids=allowed_knowledge_base_ids
        )
        if not expression:
            return []
        if len(vector) != VECTOR_DIMENSION or not 0 < limit <= 64:
            raise ValueError("查询向量必须为 1024 维且 limit 必须在 1 到 64 之间")
        hits = self._ready_client().search(
            self._config.collectionName,
            data=[list(vector)],
            anns_field="vector",
            filter=expression,
            limit=limit,
            output_fields=list(_OUTPUT_FIELDS),
            search_params={"metric_type": "COSINE", "params": {"ef": 64}},
        )
        return list(hits[0]) if hits else []

    def delete_document(
        self, scope: OwnerScope, knowledge_base_id: str, document_id: str
    ) -> object:
        expression = milvus_delete_filter(
            tenant_id=scope.tenant_id, knowledge_base_id=knowledge_base_id, document_id=document_id
        )
        return self._ready_client().delete(self._config.collectionName, filter=expression)
