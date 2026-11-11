import json
import subprocess
import sys
from pathlib import Path
from typing import Protocol, cast

import pytest

from super_ai.project_config import ConfigError, JsonValue, load_project_config
from super_ai.tenant import OwnerScope, ScopeError
from super_ai.vector_store import MilvusVectorStore, VectorChunk, VectorStoreConfig

Row = dict[str, JsonValue]
VECTOR = [1.0] + [0.0] * 1023


class Serializable(Protocol):
    def to_dict(self) -> dict[str, JsonValue]: ...


class FakeMilvus:
    def __init__(self) -> None:
        self.schema: dict[str, JsonValue] | None = None
        self.indexes: dict[str, dict[str, JsonValue]] = {}
        self.loads = 0
        self.fail_index_once = False
        self.available = True
        self.rows: list[Row] = []
        self.searches: list[str] = []
        self.deletes: list[str] = []

    def has_collection(self, collection_name: str) -> bool:
        assert collection_name == "knowledge_chunks"
        return self.schema is not None

    def create_collection(
        self, collection_name: str, *, schema: object, consistency_level: str
    ) -> None:
        assert not self.has_collection(collection_name)
        assert consistency_level == "Strong"
        self.schema = cast(Serializable, schema).to_dict()

    def list_indexes(self, collection_name: str) -> list[str]:
        assert self.has_collection(collection_name)
        return list(self.indexes)

    def create_index(self, collection_name: str, index_params: object) -> None:
        assert self.has_collection(collection_name)
        for index in cast(list[Serializable], index_params):
            details = index.to_dict()
            name = str(details["index_name"])
            assert name not in self.indexes
            self.indexes[name] = details
            if self.fail_index_once:
                self.fail_index_once = False
                raise RuntimeError("partial index creation")

    def load_collection(self, collection_name: str) -> None:
        assert self.has_collection(collection_name)
        self.loads += 1

    def get_server_version(self, *, timeout: float) -> str:
        assert timeout == 5
        if not self.available:
            raise ConnectionError
        return "3.0-beta"

    def insert(self, collection_name: str, *, data: list[Row]) -> None:
        assert self.has_collection(collection_name)
        self.rows.extend(data)

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
    ) -> list[list[Row]]:
        assert self.has_collection(collection_name)
        assert data == [VECTOR] and anns_field == "vector"
        assert set(output_fields) == {
            "chunkId", "tenantId", "ownerUserId", "knowledgeBaseId", "documentId",
            "content", "source", "metadata", "createdAt",
        }
        assert search_params == {"metric_type": "COSINE", "params": {"ef": 64}}
        self.searches.append(filter)
        tenant, tail = decode_condition(filter, "tenantId == ")
        kb_ids = cast(list[str], json.loads(tail.removeprefix(" and knowledgeBaseId in ")))
        return [[
            row for row in self.rows
            if row["tenantId"] == tenant and row["knowledgeBaseId"] in kb_ids
        ][:limit]]

    def delete(self, collection_name: str, *, filter: str) -> None:
        assert self.has_collection(collection_name)
        self.deletes.append(filter)
        tenant, tail = decode_condition(filter, "tenantId == ")
        kb, tail = decode_condition(tail, " and knowledgeBaseId == ")
        document, tail = decode_condition(tail, " and documentId == ")
        assert tail == ""
        self.rows = [
            row for row in self.rows
            if (row["tenantId"], row["knowledgeBaseId"], row["documentId"])
            != (tenant, kb, document)
        ]


def decode_condition(expression: str, prefix: str) -> tuple[str, str]:
    assert expression.startswith(prefix)
    body = expression[len(prefix):]
    value, end = json.JSONDecoder().raw_decode(body)
    assert isinstance(value, str)
    return value, body[end:]


class Harness:
    def __init__(self) -> None:
        self.client = FakeMilvus()
        self.connects = 0
        config = VectorStoreConfig.from_project({
            "vectorStore": {"endpoint": "http://127.0.0.1:19530"},
        })
        self.store = MilvusVectorStore(config, client_factory=self.connect)

    def connect(self, config: VectorStoreConfig) -> FakeMilvus:
        assert config.endpoint.port == 19530
        self.connects += 1
        return self.client


def test_import_does_not_load_sdk_or_read_project_config() -> None:
    result = subprocess.run(
        [sys.executable, "-c", """
import sys
from pathlib import Path
from unittest.mock import patch

read_text = Path.read_text
def reject_config(self, *args, **kwargs):
    assert self.name not in {'project.json', 'user.project.json'}
    return read_text(self, *args, **kwargs)

def reject_network(event, args):
    assert event not in {'socket.connect', 'socket.getaddrinfo'}

sys.addaudithook(reject_network)
with patch.object(Path, 'read_text', reject_config):
    import super_ai.vector_store
assert 'pymilvus' not in sys.modules
"""],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr


def test_merged_config_ignores_env_and_hides_invalid_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    (tmp_path / "project.json").write_text(
        '{"vectorStore":{"endpoint":"http://127.0.0.1:19530","collectionName":"base"}}',
        encoding="utf-8",
    )
    (tmp_path / "user.project.json").write_text(
        '{"vectorStore":{"collectionName":"override"}}', encoding="utf-8"
    )
    monkeypatch.setenv("MILVUS_URI", "http://example.invalid:1")
    config = VectorStoreConfig.from_project(load_project_config(tmp_path))
    assert config.endpoint.port == 19530
    assert config.collectionName == "override"
    with pytest.raises(ConfigError, match="^vectorStore"):
        VectorStoreConfig.from_project({"vectorStore": {"endpoint": "not-a-url"}})


def test_lazy_lifecycle_health_schema_and_index_retry() -> None:
    harness = Harness()
    store, client = harness.store, harness.client
    assert harness.connects == 0
    with pytest.raises(RuntimeError):
        store.search(OwnerScope("u1", "u1"), ["kb"], VECTOR)
    assert harness.connects == 0
    store.connect()
    store.connect()
    assert harness.connects == 1
    assert store.health()
    client.available = False
    assert not store.health()
    assert client.schema is None
    client.available = True

    client.fail_index_once = True
    with pytest.raises(RuntimeError, match="partial index creation"):
        store.initialize()
    assert client.loads == 0
    store.initialize()
    store.initialize()
    assert client.loads == 1
    assert client.schema is not None
    assert client.schema["enable_dynamic_field"] is False
    fields = {
        field["name"]: field for field in cast(list[Row], client.schema["fields"])
    }
    assert set(fields) == {
        "chunkId", "documentId", "knowledgeBaseId", "ownerUserId", "tenantId",
        "content", "source", "createdAt", "metadata", "vector",
    }
    assert fields["chunkId"]["is_primary"] is True
    assert fields["vector"]["type"] == 101  # PyMilvus FLOAT_VECTOR
    assert fields["vector"]["params"] == {"dim": 1024}
    assert client.indexes["vector"] == {
        "field_name": "vector", "index_name": "vector", "index_type": "HNSW",
        "metric_type": "COSINE", "M": 16, "efConstruction": 200,
    }
    scalars = {
        name for name, index in client.indexes.items() if index["index_type"] == "INVERTED"
    }
    assert scalars == {
        "documentId", "knowledgeBaseId", "ownerUserId", "tenantId", "createdAt",
    }


def test_invalid_or_empty_scopes_never_connect() -> None:
    harness = Harness()
    store = harness.store
    scope = OwnerScope("u1", "u1")
    assert store.search(scope, [], []) == []
    assert store.search(scope, ["", "  "], []) == []
    with pytest.raises(ScopeError):
        OwnerScope("", "")
    with pytest.raises(ScopeError):
        store.search(OwnerScope(" ", " "), [], [])
    with pytest.raises(ScopeError):
        store.delete_document(OwnerScope(" ", " "), "kb", "doc")
    for kb, doc in [("", "doc"), ("kb", " ")]:
        with pytest.raises(ValueError):
            store.delete_document(scope, kb, doc)
    assert harness.connects == 0


def test_cross_user_search_and_delete_escape_and_constrain_scope() -> None:
    harness = Harness()
    store, client = harness.store, harness.client
    store.initialize()
    user_a = '甲" or tenantId != "甲\\'
    kb = '知识库" or true\\'
    doc = "文档\\'\n"
    scope_a = OwnerScope(user_a, user_a)
    scope_b = OwnerScope("user-b", "user-b")
    for scope, chunk_id, kb_id, doc_id in (
        (scope_a, "a", kb, doc),
        (scope_a, "other-kb", "other", doc),
        (scope_a, "other-doc", kb, "other"),
        (scope_b, "b", kb, doc),
    ):
        store.insert(scope, [
            VectorChunk(chunk_id, doc_id, kb_id, "正文", "来源", 123, {
                "ownerUserId": "spoof", "tenantId": "spoof", "page": 1,
            }, VECTOR),
        ])
    assert store.search(scope_a, [kb], VECTOR) == [client.rows[0], client.rows[2]]
    assert store.search(scope_b, [kb], VECTOR) == [client.rows[3]]
    assert "documentId" not in client.searches[0]
    assert "metadata" not in client.searches[0]
    assert "ownerUserId" not in client.searches[0]
    assert client.rows[0]["metadata"] == {
        "ownerUserId": user_a, "tenantId": user_a, "page": 1,
    }
    assert client.rows[0]["ownerUserId"] == user_a
    store.delete_document(scope_a, kb, doc)
    assert {str(row["chunkId"]) for row in client.rows} == {"other-kb", "other-doc", "b"}
    assert "ownerUserId" not in client.deletes[0]
