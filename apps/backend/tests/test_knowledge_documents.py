import asyncio
import subprocess
import sys
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from super_ai.document_chunking import chunk_document_text, extract_document_text, resolve_chunking
from super_ai.document_contracts import MAX_UPLOAD_BYTES
from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head
from super_ai.tenant import OwnerScope


def test_pdf_extraction() -> None:
    writer = PdfWriter()
    page = writer.add_blank_page(200, 200)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {
            NameObject("/Font"): DictionaryObject({NameObject("/F1"): font}),
        }
    )
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 10 10 Td (Extracted PDF) Tj ET")
    page[NameObject("/Contents")] = stream
    buffer = BytesIO()
    writer.write(buffer)
    assert (
        extract_document_text("test.PDF", "application/pdf", buffer.getvalue()) == "Extracted PDF"
    )


@pytest.mark.parametrize(
    ("filename", "mime", "body"),
    [
        ("x.txt", "text/plain", b"hello"),
        ("x.md", "application/pdf", b"hello"),
        ("x.pdf", "text/plain", b"%PDF-1.7"),
        ("x.pdf", "application/pdf", b"invalid"),
        ("x.pdf", "application/pdf", b"%PDF-1.7\ninvalid"),
        ("x.md", "text/markdown", b"\xff"),
        ("x.md", "text/markdown", b""),
        ("x.md", "text/markdown", b"  "),
        ("x.md", "text/markdown", b"a\x00b"),
    ],
)
def test_invalid_upload(filename: str, mime: str, body: bytes) -> None:
    with pytest.raises(ValueError):
        extract_document_text(filename, mime, body)


def test_upload_size_boundary() -> None:
    content = b"a" * MAX_UPLOAD_BYTES
    assert len(extract_document_text("x.md", "text/markdown", content)) == MAX_UPLOAD_BYTES
    with pytest.raises(ValueError):
        extract_document_text("x.md", "text/plain", content + b"a")


def test_chunk_spans_and_configuration() -> None:
    fixed = resolve_chunking("fixed-character", 4, 2)
    chunks = list(chunk_document_text("甲乙丙丁戊己", fixed))
    assert [(c.index, c.start, c.end, c.text) for c in chunks] == [
        (0, 0, 4, "甲乙丙丁"),
        (1, 2, 6, "丙丁戊己"),
    ]
    text = "# 第一节\n```python\n# 注释\n```\n## 第二节\n末尾"
    headings = list(chunk_document_text(text, resolve_chunking("markdown-heading", None, None)))
    assert [c.text for c in headings] == ["# 第一节\n```python\n# 注释\n```\n", "## 第二节\n末尾"]
    paragraphs = list(
        chunk_document_text(
            "第一段\r\n \r\n第二段",
            resolve_chunking(
                "paragraph",
                None,
                None,
            ),
        )
    )
    assert [c.text for c in paragraphs] == ["第一段", "第二段"]
    with pytest.raises(ValueError):
        resolve_chunking("fixed-character", 200, 200)
    with pytest.raises(ValueError):
        resolve_chunking("fixed-character", 200, -1)
    with pytest.raises(ValueError):
        resolve_chunking("paragraph", None, 0)
    with pytest.raises(ValueError):
        resolve_chunking("markdown-heading", 1200, None)


async def register_user(client: httpx.AsyncClient, name: str) -> tuple[str, dict[str, str]]:
    credentials = {"email": f"{name}@example.test", "password": "Local-password-2026"}
    registration = await client.post("/auth/register", json=credentials)
    assert registration.status_code == 200
    login = await client.post("/auth/login", json=credentials)
    return (
        str(registration.json()["data"]["id"]),
        {"Authorization": f"Bearer {login.json()['data']['token']}"},
    )


async def test_document_lifecycle(tmp_path: Path) -> None:
    url = f"sqlite+aiosqlite:///{(tmp_path / 'documents.db').as_posix()}"
    upgrade_head(url, Path(__file__).resolve().parents[1])
    calls: list[tuple[OwnerScope, str, str]] = []
    fail = False

    def delete_vectors(scope: OwnerScope, kb: str, document: str) -> None:
        calls.append((scope, kb, document))
        if fail:
            raise RuntimeError("模拟清理失败")

    app = create_app(config={"database": {"url": url}}, delete_document_vectors=delete_vectors)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app, raise_app_exceptions=False),
            base_url="http://test",
        ) as client,
    ):
        owner_id, owner = await register_user(client, "owner")
        _, other = await register_user(client, "other")
        assert (await client.get("/knowledge-bases")).status_code == 401
        bases = (await client.get("/knowledge-bases", headers=owner)).json()["data"]
        assert len(bases) == 1
        assert (await client.get("/knowledge-bases", headers=owner)).json()["data"] == bases
        kb = str(bases[0]["id"])
        path = f"/knowledge-bases/{kb}/documents"
        other_kb = str(
            (await client.get("/knowledge-bases", headers=other)).json()["data"][0]["id"]
        )
        assert other_kb != kb
        assert (await client.get(path, headers=other)).status_code == 403
        body = "正文" * 7000
        files = {"file": ("notes.md", body.encode(), "text/markdown")}
        invalid = await client.post(
            path,
            headers=owner,
            files=files,
            data={
                "strategy": "paragraph",
                "overlap": "0",
            },
        )
        assert invalid.status_code == 422
        first, second = await asyncio.gather(
            client.post(path, headers=owner, files=files),
            client.post(path, headers=owner, files=files),
        )
        assert sorted([first.status_code, second.status_code]) == [200, 409]
        created, conflict = (first, second) if first.status_code == 200 else (second, first)
        assert conflict.json()["error"]["code"] == "BUSINESS_CONFLICT"
        data = created.json()["data"]
        document = str(data["id"])
        detail = f"{path}/{document}"
        assert data["sha256"] == sha256(body.encode()).hexdigest()
        assert data["size"] == len(body.encode())
        assert data["indexStatus"] == "pending"
        assert data["chunking"] == {
            "strategy": "fixed-character",
            "maxCharacters": 1200,
            "overlap": 200,
        }
        assert (await client.get(detail, headers=owner)).json()["data"] == data
        preview = (await client.get(f"{detail}/chunk-preview", headers=owner)).json()["data"]
        assert len(preview["chunks"]) == 12
        assert all(len(chunk["excerpt"]) == 400 for chunk in preview["chunks"])
        assert preview["chunks"][1]["start"] == 1000
        assert (await client.delete(detail, headers=other)).status_code == 403
        other_path = f"/knowledge-bases/{other_kb}/documents"
        assert (await client.get(f"{other_path}/{document}", headers=other)).status_code == 404
        assert (await client.post(other_path, files=files, headers=other)).status_code == 200
        assert not calls
        fail = True
        assert (await client.delete(detail, headers=owner)).status_code == 500
        assert (await client.get(detail, headers=owner)).status_code == 200
        fail = False
        overwrite = await client.post(
            path,
            headers=owner,
            files=files,
            data={
                "overwrite": "true",
                "strategy": "paragraph",
            },
        )
        assert overwrite.status_code == 200
        new = overwrite.json()["data"]
        assert new["id"] != document
        assert new["chunking"] == {"strategy": "paragraph"}
        assert (await client.get(detail, headers=owner)).status_code == 404
        assert (await client.get(path, headers=owner)).json()["data"] == [new]
        assert (await client.delete(f"{path}/{new['id']}", headers=owner)).status_code == 200
        assert (await client.get(path, headers=owner)).json()["data"] == []
        scope = OwnerScope(owner_id, owner_id)
        assert calls == [(scope, kb, document), (scope, kb, document), (scope, kb, new["id"])]


def test_openapi_contract() -> None:
    schema = create_app(config={}).openapi()
    paths = schema["paths"]
    upload = paths["/knowledge-bases/{kb}/documents"]["post"]
    assert upload["x-upload-policy"]["maxBytes"] == MAX_UPLOAD_BYTES
    assert {"401", "403", "409", "422"} <= upload["responses"].keys()
    multipart = upload["requestBody"]["content"]["multipart/form-data"]["schema"]["$ref"]
    properties = schema["components"]["schemas"][multipart.rsplit("/", 1)[-1]]["properties"]
    assert set(properties) == {"file", "overwrite", "strategy", "maxCharacters", "overlap"}
    assert properties["overwrite"]["default"] is False
    assert paths["/knowledge-bases/{kb}/documents/{document}/chunk-preview"]["get"]["security"]


def test_document_import_safety(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from unittest.mock import patch

with (
    patch('super_ai.project_config.load_project_config', side_effect=AssertionError),
    patch('super_ai.memory.engine.create_engine', side_effect=AssertionError),
    patch('super_ai.vector_store._connect', side_effect=AssertionError),
):
    import super_ai.main
    import super_ai.document_api
""",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
