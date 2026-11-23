"""使用本机提供方和隔离 SQLite/Milvus 集合启动真实聊天验收服务。"""

import argparse
from pathlib import Path
from uuid import uuid4

import uvicorn

from super_ai.main import create_app
from super_ai.memory.migrations import upgrade_head
from super_ai.project_config import load_project_config


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--milvus-endpoint")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    cache = root / ".cache"
    cache.mkdir(exist_ok=True)
    run_id = uuid4().hex
    config = load_project_config(root / "config")
    url = f"sqlite+aiosqlite:///{(cache / f'chat-smoke-{run_id}.db').as_posix()}"
    config["database"] = {"url": url}
    settings = config.get("vectorStore")
    if not isinstance(settings, dict):
        raise RuntimeError("真实验收需要 vectorStore 配置")
    settings["collectionName"] = f"p19_smoke_{run_id}"
    if args.milvus_endpoint:
        settings["endpoint"] = args.milvus_endpoint
    upgrade_head(url, root / "apps/backend")
    uvicorn.run(create_app(config=config), host="127.0.0.1", port=18019)


if __name__ == "__main__":
    main()
