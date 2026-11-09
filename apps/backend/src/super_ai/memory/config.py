from dataclasses import dataclass
from typing import cast

from super_ai.project_config import JsonObject


@dataclass(frozen=True)
class DatabaseSettings:
    url: str


def database_settings(config: JsonObject) -> DatabaseSettings:
    raw = config.get("database")
    if not isinstance(raw, dict) or not isinstance(raw.get("url"), str):
        raise ValueError("database.url 配置缺失")
    return DatabaseSettings(url=cast(str, raw["url"]))
