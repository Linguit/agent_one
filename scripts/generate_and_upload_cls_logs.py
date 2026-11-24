"""独立 CLS 工具；默认只预览。需先安装脚本专用 SDK 环境，见 docs。"""

import argparse
import importlib
import logging
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any
from uuid import UUID

from super_ai.project_config import ConfigError, JsonObject, load_project_config

MAX_COUNT = 1000


def generate_logs(count: int, region: str) -> list[dict[str, str]]:
    if type(count) is not int or not 1 <= count <= MAX_COUNT:
        raise ValueError("count 必须在 1..1000 内")
    if not re.fullmatch(r"[a-z]{2}-[a-z]+(?:-[a-z]+)?", region):
        raise ValueError("region 无效")
    return [
        {
            "event": "aiops_input_sample",
            "service": "sample-service",
            "severity": "info" if i % 3 else "warning",
            "region": region,
            "sequence": str(i),
            "message": "synthetic bounded operational sample",
        }
        for i in range(count)
    ]


def upload_settings(config: JsonObject) -> dict[str, str]:
    section, credentials = config.get("clsLogUpload"), config.get("cls")
    if not isinstance(section, dict) or not isinstance(credentials, dict):
        raise ValueError("缺少 CLS 配置")
    values = {key: section.get(key) for key in ("endpoint", "topicId", "region")}
    values.update({key: credentials.get(key) for key in ("secretId", "secretKey")})
    if not all(isinstance(value, str) and value for value in values.values()):
        raise ValueError("CLS 配置不完整")
    result = {key: str(value) for key, value in values.items()}
    # 固定 HTTPS 官方 CLS 上传域名，禁止 userinfo、端口、路径、查询参数与自定义主机。
    if not re.fullmatch(
        r"https://[a-z0-9]+(?:-[a-z0-9]+)*\.cls\.tencentcs\.com", result["endpoint"]
    ):
        raise ValueError("CLS endpoint 必须为官方 HTTPS 上传域名")
    UUID(result["topicId"])
    return result


def build_groups(logs: list[dict[str, str]], group_factory: Callable[[], Any]) -> Any:
    groups = group_factory()
    group = groups.logGroupList.add()
    group.filename, group.source = "aiops-input-sample.log", "explicit-generator"
    now = time.time_ns() // 1000
    for i, fields in enumerate(logs):
        log = group.logs.add()
        log.time = now + i
        for key, value in fields.items():
            content = log.contents.add()
            content.key, content.value = key, value
    return groups


def run(
    config: JsonObject,
    count: int,
    confirm_endpoint: str | None = None,
    confirm_topic: str | None = None,
    client_factory: Callable[..., Any] | None = None,
    group_factory: Callable[[], Any] | None = None,
) -> int:
    settings = upload_settings(config)
    logs = generate_logs(count, settings["region"])
    if confirm_endpoint is None and confirm_topic is None:
        print(f"已生成 {len(logs)} 条日志；仅预览，未上传。")
        return 0
    if confirm_endpoint != settings["endpoint"] or confirm_topic != settings["topicId"]:
        raise ValueError("上传确认目标与本地配置不一致")
    # SDK 仅在显式上传路径导入；禁止其错误或调试日志泄漏凭据。
    if client_factory is None:
        client_factory = importlib.import_module("tencentcloud.log.logclient").LogClient
    if group_factory is None:
        group_factory = importlib.import_module("tencentcloud.log.cls_pb2").LogGroupList
    groups = build_groups(logs, group_factory)
    previous = logging.root.manager.disable
    logging.disable(logging.CRITICAL)
    try:
        client = client_factory(
            settings["endpoint"], settings["secretId"], settings["secretKey"]
        )
        client.put_log_raw(settings["topicId"], groups)
    except Exception:
        raise ValueError("CLS 上传失败，请检查目标与权限") from None
    finally:
        logging.disable(previous)
    print(f"已上传 {len(logs)} 条日志。")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="有界 CLS 样例日志；默认不上传")
    parser.add_argument("--config-dir", type=Path)
    parser.add_argument("--count", type=int, default=10)
    parser.add_argument("--confirm-endpoint")
    parser.add_argument("--confirm-topic")
    args = parser.parse_args()
    try:
        return run(
            load_project_config(args.config_dir),
            args.count,
            args.confirm_endpoint,
            args.confirm_topic,
        )
    except (ValueError, ConfigError, ImportError):
        print("未完成：配置、参数、SDK 或上传失败；详细配置及凭据不会输出。")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
