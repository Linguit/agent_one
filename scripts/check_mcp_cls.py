"""真实官方 CLS MCP 发现 smoke；在 apps/backend 用 uv run python ../../scripts/check_mcp_cls.py。"""
import asyncio

from super_ai.mcp_contracts import ConnectionInput
from super_ai.mcp_provider import discover_real
from super_ai.project_config import load_project_config


async def main() -> None:
    config = load_project_config()
    server = config.get("clsMcpServer")
    if not isinstance(server, dict) or not server.get("url"):
        print("未执行：未配置真实官方 CLS MCP 服务 URL；未使用 mock 替代。")
        return
    try:
        connection = ConnectionInput(name="官方 CLS smoke", transport="sse", url=str(server["url"]))
        tools = await asyncio.wait_for(discover_real(connection), connection.timeoutSeconds)
    except Exception:
        print("真实 CLS smoke 失败：连接或发现失败；请检查官方服务及凭据。")
        raise SystemExit(1) from None
    print(f"真实 CLS smoke：连接并发现 {len(tools)} 个工具，未调用有副作用工具。")


if __name__ == "__main__":
    asyncio.run(main())
