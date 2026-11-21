import json
import re
from collections.abc import Hashable
from typing import Any

import yaml
from pydantic import JsonValue, TypeAdapter
from yaml.nodes import MappingNode
from yaml.tokens import AliasToken, AnchorToken

MAX_SKILL_BYTES = 256 * 1024


class SkillFormatError(ValueError):
    pass


class _UniqueLoader(yaml.SafeLoader):
    def construct_mapping(self, node: MappingNode, deep: bool = False) -> dict[Hashable, Any]:
        if any(key.tag != "tag:yaml.org,2002:str" for key, _ in node.value):
            raise SkillFormatError("YAML 对象字段名必须是字符串")
        keys = [key.value for key, _ in node.value]
        if len(keys) != len(set(keys)):
            raise SkillFormatError("YAML 字段不能重复")
        return super().construct_mapping(node, deep)


def parse_skill(filename: str | None, data: bytes) -> tuple[str, str, dict[str, JsonValue], str]:
    if filename != "SKILL.md" or len(data) > MAX_SKILL_BYTES:
        raise SkillFormatError("仅接受不超过 256 KiB、文件名严格为 SKILL.md 的文件")
    try:
        content = data.decode("utf-8")
        if "\x00" in content:
            raise SkillFormatError("文件包含非法字符")
        lines = content.splitlines()
        if not lines or lines[0] != "---":
            raise SkillFormatError("缺少 YAML frontmatter")
        end = lines.index("---", 1)
        header = "\n".join(lines[1:end])
        if not "\n".join(lines[end + 1 :]).strip():
            raise SkillFormatError("Skill 正文不能为空")
        if any(isinstance(token, (AliasToken, AnchorToken)) for token in yaml.scan(header)):
            raise SkillFormatError("不接受 YAML 别名或锚点")
        loaded: object = yaml.load(header, Loader=_UniqueLoader)
        # Reject non-JSON YAML objects and non-string keys before Pydantic coercion.
        serialized = json.dumps(loaded, ensure_ascii=False, allow_nan=False)
        metadata = TypeAdapter(dict[str, JsonValue]).validate_json(serialized, strict=True)
        name, description = metadata.get("name"), metadata.get("description")
        if not isinstance(name, str) or not isinstance(description, str):
            raise SkillFormatError("name 和 description 必须是字符串")
        name, description = name.strip().lower(), description.strip()
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64:
            raise SkillFormatError("name 必须为 1–64 位小写字母数字和单连字符")
        if not description or len(description) > 1024:
            raise SkillFormatError("description 必须为 1–1024 个字符")
        metadata.update(name=name, description=description)
        return name, description, metadata, content
    except (ValueError, TypeError, yaml.YAMLError, RecursionError) as exc:
        raise SkillFormatError("无效的 SKILL.md 或 YAML frontmatter") from exc
