import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import timedelta
from typing import TYPE_CHECKING, Any, cast

from pydantic import BaseModel, TypeAdapter

from super_ai.mcp_contracts import ConnectionInput, DiscoveredTool, McpConnection
from super_ai.mcp_logging import private_transport_logs
from super_ai.memory.sqlite.mcp import McpRepository
from super_ai.project_config import JsonObject
from super_ai.safe_logging import log_failure
from super_ai.tenant import OwnerScope

if TYPE_CHECKING:
    from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

Discover = Callable[[ConnectionInput], Awaitable[list["BaseTool"]]]


class McpFailure(RuntimeError):
    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


async def discover_real(body: ConnectionInput) -> list["BaseTool"]:
    from langchain_mcp_adapters.client import MultiServerMCPClient
    from langchain_mcp_adapters.sessions import Connection

    connection: Connection
    if body.transport == "sse":
        connection = {
            "transport": "sse",
            "url": body.url,
            "timeout": float(body.timeoutSeconds),
            "sse_read_timeout": float(body.timeoutSeconds),
        }
    else:
        connection = {
            "transport": "streamable_http",
            "url": body.url,
            "timeout": timedelta(seconds=body.timeoutSeconds),
            "sse_read_timeout": timedelta(seconds=body.timeoutSeconds),
        }
    with private_transport_logs():
        return await MultiServerMCPClient({"server": connection}).get_tools()


def bounded_tool(source: "BaseTool", timeout: int) -> "BaseTool":
    from langchain_core.runnables import RunnableConfig
    from langchain_core.tools import StructuredTool

    async def invoke(config: RunnableConfig, **arguments: Any) -> Any:
        try:
            with private_transport_logs():
                return await asyncio.wait_for(source.ainvoke(arguments, config=config), timeout)
        except asyncio.TimeoutError:
            raise McpFailure("MCP_TIMEOUT") from None
        except Exception:
            raise McpFailure("MCP_CALL_FAILED") from None

    return StructuredTool(
        name=source.name,
        description=source.description,
        args_schema=source.args_schema or {},
        coroutine=invoke,
    )


def tool_descriptions(tools: list["BaseTool"]) -> list[DiscoveredTool]:
    return [
        DiscoveredTool(
            name=tool.name,
            description=tool.description,
            inputSchema=TypeAdapter(dict[str, Any]).validate_python(
                tool.args_schema
                if isinstance(tool.args_schema, dict)
                else cast(type[BaseModel], tool.get_input_schema()).model_json_schema()
            ),
        )
        for tool in tools
    ]


class McpProvider:
    """Shared owner-scoped source for Chat and future AIOps; never uses cached tools."""

    def __init__(
        self,
        repository: McpRepository,
        config: JsonObject,
        discover: Discover = discover_real,
    ) -> None:
        self.repository = repository
        self._config = config
        self._discover = discover

    async def discover(self, body: ConnectionInput) -> list["BaseTool"]:
        code = "MCP_DISCOVERY_FAILED"
        for _ in range(body.retries + 1):
            try:
                return await asyncio.wait_for(self._discover(body), body.timeoutSeconds)
            except asyncio.TimeoutError as exc:
                log_failure(logger, "mcp_discovery_timeout", exc)
                code = "MCP_TIMEOUT"
            except Exception as exc:
                log_failure(logger, "mcp_discovery_transport", exc)
                code = "MCP_DISCOVERY_FAILED"
        raise McpFailure(code) from None

    async def check(self, scope: OwnerScope, id: str) -> McpConnection:
        record = await self.repository.get(scope, id)
        try:
            tools = tool_descriptions(await self.discover(record))
            error = None
        except McpFailure as exc:
            tools, error = [], exc.code
        return await self.repository.checked(scope, record, tools, error)

    async def tools(self, scope: OwnerScope, *, allow_fallback: bool = True) -> list["BaseTool"]:
        records = await self.repository.list(scope)
        sources: list[ConnectionInput] = [row for row in records if row.enabled]
        if not records and allow_fallback:
            fallback = self._config.get("clsMcpServer")
            if isinstance(fallback, dict) and fallback.get("url"):
                try:
                    sources = [
                        ConnectionInput(name="官方 CLS", transport="sse", url=str(fallback["url"]))
                    ]
                except ValueError:
                    raise McpFailure("MCP_CONFIG_INVALID") from None
        result: list[BaseTool] = []
        names = {"knowledge_retrieval", "get_current_time", "load_skill"}
        for source in sources:
            for tool in await self.discover(source):
                if tool.name in names:
                    raise McpFailure("MCP_TOOL_NAME_CONFLICT")
                names.add(tool.name)
                result.append(bounded_tool(tool, source.timeoutSeconds))
        return result
