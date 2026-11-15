import re
from collections.abc import Iterator
from dataclasses import dataclass
from io import BytesIO
from pathlib import PurePath

from pypdf import PdfReader

from super_ai.document_contracts import (
    DEFAULT_MAX_CHARACTERS,
    DEFAULT_OVERLAP,
    MAX_UPLOAD_BYTES,
    UPLOAD_MIME_TYPES,
    ChunkingConfig,
    FixedCharacterConfig,
    NaturalChunkingConfig,
    Strategy,
)

_HEADING = re.compile(r"^ {0,3}#{1,6}(?=[ \t]|$)", re.MULTILINE)
_FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
_PARAGRAPH = re.compile(r"\r?\n(?:[^\S\r\n]*\r?\n)+")
_SURROGATE = re.compile(r"[\ud800-\udfff]")


@dataclass(frozen=True)
class DocumentChunk:
    index: int
    start: int
    end: int
    text: str


def resolve_chunking(
    strategy: Strategy, max_characters: int | None, overlap: int | None
) -> ChunkingConfig:
    if strategy != "fixed-character":
        if max_characters is not None or overlap is not None:
            raise ValueError("只有 fixed-character 接受长度和重叠参数")
        return NaturalChunkingConfig(strategy=strategy)
    maximum = DEFAULT_MAX_CHARACTERS if max_characters is None else max_characters
    shared = DEFAULT_OVERLAP if overlap is None else overlap
    if not 0 <= shared < maximum:
        raise ValueError("overlap 必须大于等于零且小于 maxCharacters")
    return FixedCharacterConfig(maxCharacters=maximum, overlap=shared)


def extract_document_text(filename: str, mime_type: str, content: bytes) -> str:
    suffix = PurePath(filename).suffix.lower()
    if not 0 < len(content) <= MAX_UPLOAD_BYTES:
        raise ValueError("文件大小必须在 1 字节到 10 MiB 之间")
    if mime_type not in UPLOAD_MIME_TYPES.get(suffix, ()):
        raise ValueError("文件扩展名与 MIME 必须符合上传政策")
    if suffix == ".md":
        text = content.decode("utf-8-sig")
    else:
        if not content.startswith(b"%PDF-"):
            raise ValueError("PDF 文件头无效")
        try:
            reader = PdfReader(BytesIO(content))
            if reader.is_encrypted:
                raise ValueError("PDF 已加密")
            text = "\n\n".join(page.extract_text() for page in reader.pages)
        except Exception:
            raise ValueError("无法提取 PDF 正文") from None
        text = _SURROGATE.sub("\ufffd", text)
    if not text.strip() or "\x00" in text:
        raise ValueError("文件必须包含可索引正文")
    return text


def _heading_starts(text: str) -> Iterator[int]:
    fence: str | None = None
    offset = 0
    for line in re.finditer(r"[^\n]*(?:\n|$)", text):
        body = line.group().rstrip("\r\n")
        match = _FENCE.match(body)
        if match:
            marker, rest = match.groups()
            if fence is None:
                fence = marker
            elif marker.startswith(fence) and not rest.strip():
                fence = None
        elif fence is None and offset and _HEADING.match(body):
            yield offset
        offset = line.end()


def _chunk_spans(text: str, config: ChunkingConfig) -> Iterator[tuple[int, int]]:
    if isinstance(config, FixedCharacterConfig):
        if config.overlap >= config.maxCharacters:
            raise ValueError("overlap 必须小于 maxCharacters")
        step = config.maxCharacters - config.overlap
        for start in range(0, len(text), step):
            end = min(start + config.maxCharacters, len(text))
            yield start, end
            if end == len(text):
                break
    elif config.strategy == "markdown-heading":
        start = 0
        for end in _heading_starts(text):
            yield start, end
            start = end
        yield start, len(text)
    else:
        start = 0
        for separator in _PARAGRAPH.finditer(text):
            yield start, separator.start()
            start = separator.end()
        yield start, len(text)

geiw
def chunk_document_text(text: str, config: ChunkingConfig) -> Iterator[DocumentChunk]:
    """按持久化配置切分正文，字符区间为零基、左闭右开。"""
    index = 0
    for start, end in _chunk_spans(text, config):
        chunk = text[start:end]
        if chunk.strip():
            yield DocumentChunk(index, start, end, chunk)
            index += 1
