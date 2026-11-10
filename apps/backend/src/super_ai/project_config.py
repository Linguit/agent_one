"""只读取本地 JSON，不使用环境变量或创建外部资源。"""

import json
from copy import deepcopy
from pathlib import Path
from typing import TypeAlias, cast

JsonValue: TypeAlias = "str | int | float | bool | None | list[JsonValue] | dict[str, JsonValue]"
JsonObject: TypeAlias = dict[str, JsonValue]


class ConfigError(ValueError):
    """不携带配置值的加载错误。"""


def deep_merge(base: JsonObject, override: JsonObject) -> JsonObject:
    result = deepcopy(base)
    for key, value in override.items():
        previous = result.get(key)
        if isinstance(previous, dict) and isinstance(value, dict):
            result[key] = deep_merge(previous, value)
        else:
            result[key] = deepcopy(value)
    return result


def _read_object(path: Path, *, optional: bool = False) -> JsonObject:
    try:
        value: object = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        if optional:
            return {}
        raise ConfigError(f"缺少基础配置文件：{path.name}") from None
    except (OSError, UnicodeError, json.JSONDecodeError):
        raise ConfigError(f"无法读取合法 JSON 配置：{path.name}") from None
    if not isinstance(value, dict):
        raise ConfigError(f"配置根节点必须为对象：{path.name}")
    return cast(JsonObject, value)


def default_config_dir() -> Path:
    return Path(__file__).resolve().parents[4] / "config"


def load_project_config(config_dir: Path | None = None) -> JsonObject:
    directory = config_dir if config_dir is not None else default_config_dir()
    base = _read_object(directory / "project.json")
    user_path = directory / "user.project.json"
    override = _read_object(user_path, optional=True)
    return deep_merge(base, override)
