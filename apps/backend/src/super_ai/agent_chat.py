from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, aclosing, suppress
from datetime import datetime, timezone
from time import perf_counter
from typing import TYPE_CHECKING, Any, Literal, cast
from urllib.parse import quote

from anyio import CancelScope
from pydantic import BaseModel, JsonValue, TypeAdapter

from super_ai.contracts import ERROR_CATALOG
from super_ai.mcp_provider import McpFailure, McpProvider
from super_ai.memory.sqlite.chat import ChatRepository, MessageRecord
from super_ai.memory.sqlite.configuration import ConfigurationRepository
from super_ai.memory.sqlite.tool_audits import ToolAuditRepository
from super_ai.progressive_skills import assemble_configuration
from super_ai.session_memory import MemoryFailure, SessionMemory, context_messages
from super_ai.tenant import OwnerScope

if TYPE_CHECKING:
    from langchain.agents.middleware import AgentState, ToolCallRequest
    from langchain.agents.middleware.types import InputAgentState
    from langchain_core.language_models import BaseChatModel
    from langchain_core.messages import AIMessage, AnyMessage, ToolMessage
    from langchain_core.tools import BaseTool
    from langgraph.runtime import Runtime
    from langgraph.types import Command

logger = logging.getLogger(__name__)
ChatModelFactory = Callable[[], AbstractAsyncContextManager["BaseChatModel"]]
EventType = Literal[
    "content.delta", "reasoning.delta", "tool.call", "reference.source", "complete", "error"
]
EventData = dict[str, JsonValue]
ToolHandler = Callable[["ToolCallRequest"], Awaitable["ToolMessage | Command[Any]"]]


class Citation(BaseModel):
    chunkId: str
    source: str
    knowledgeBaseId: str
    documentId: str
    excerpt: str
    metadata: dict[str, JsonValue]
    vectorRank: int | None
    vectorScore: float | None
    bm25Rank: int | None
    bm25Score: float | None
    rrfRank: int | None = None
    rrfScore: float
    rerankRank: int
    rerankScore: float
    score: float


class RetrievalResult(BaseModel):
    results: list[Citation]


def get_current_time() -> str:
    """获取当前 UTC 时间（ISO 8601），用于回答需要当前时间的问题。"""
    return datetime.now(timezone.utc).isoformat()


def _reasoning(message: AIMessage) -> str:
    value = message.additional_kwargs.get("reasoning_content")
    if isinstance(value, str) and value:
        return value
    blocks = cast(list[dict[str, object]], message.content_blocks)
    return "\n".join(
        text
        for block in blocks
        if block["type"] == "reasoning" and isinstance(text := block.get("reasoning"), str)
    )


class ChatAgent:
    def __init__(
        self,
        model: ChatModelFactory,
        knowledge_tool: Callable[[OwnerScope], BaseTool],
        chat: ChatRepository,
        audits: ToolAuditRepository,
        configuration: ConfigurationRepository,
        memory: SessionMemory,
        mcp: McpProvider | None = None,
    ) -> None:
        self._model = model
        self._knowledge_tool = knowledge_tool
        self._chat = chat
        self._audits = audits
        self._configuration = configuration
        self._memory = memory
        self._mcp = mcp

    async def stream(
        self, scope: OwnerScope, user: MessageRecord, request_id: str
    ) -> AsyncGenerator[str]:
        queue: asyncio.Queue[tuple[EventType, EventData]] = asyncio.Queue()
        producer = asyncio.create_task(self._run(scope, user, request_id, queue))
        sequence = 0

        def frame(kind: EventType, data: EventData) -> str:
            nonlocal sequence
            sequence += 1
            event_id = f"{user.id}:{sequence}"
            event = {
                "id": event_id,
                "sequence": sequence,
                "type": kind,
                "channel": "chat",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": data,
            }
            payload = json.dumps(event, ensure_ascii=False)
            return f"id: {event_id}\nevent: {kind}\ndata: {payload}\n\n"

        try:
            while True:
                kind, data = await queue.get()
                if kind == "content.delta":
                    for character in cast(str, data["text"]):
                        yield frame(kind, {"text": character})
                else:
                    yield frame(kind, data)
                if kind in ("error", "complete"):
                    break
        finally:
            if not producer.done():
                producer.cancel()
            with CancelScope(shield=True), suppress(asyncio.CancelledError):
                await producer

    async def _run(
        self,
        scope: OwnerScope,
        user: MessageRecord,
        request_id: str,
        queue: asyncio.Queue[tuple[EventType, EventData]],
    ) -> None:
        from langchain.agents import create_agent  # pyright: ignore[reportUnknownVariableType]
        from langchain.agents.middleware import before_model, wrap_tool_call
        from langchain_core.messages import AIMessage, SystemMessage, ToolMessage
        from langchain_core.tools import tool
        from langsmith import tracing_context  # pyright: ignore[reportUnknownVariableType]

        session_id = user.session_id
        references: dict[str, EventData] = {}
        call_ids: list[JsonValue] = []
        tool_failed = False
        tool_error_code: str | None = None

        def emit(kind: EventType, data: EventData) -> None:
            queue.put_nowait((kind, data))

        @before_model
        async def require_successful_tools(state: AgentState[Any], runtime: Runtime[None]) -> None:
            if tool_failed:
                if tool_error_code is not None:
                    raise McpFailure(tool_error_code)
                raise RuntimeError("工具执行失败")
            self._memory.check_limit(
                [
                    SystemMessage(content=configuration.system_prompt),
                    *cast(list["AnyMessage"], state["messages"]),
                ]
            )

        @wrap_tool_call
        async def audit_tool(
            request: ToolCallRequest, handler: ToolHandler
        ) -> ToolMessage | Command[Any]:
            nonlocal tool_failed, tool_error_code
            name = request.tool_call["name"]
            arguments = TypeAdapter(dict[str, JsonValue]).validate_python(request.tool_call["args"])
            audit_id = await self._audits.start(scope, name, arguments, chat_session_id=session_id)
            call_ids.append(audit_id)
            start = perf_counter()
            sources: list[Citation] = []

            def report(status: Literal["started", "completed", "failed"]) -> None:
                logger.info(
                    "Agent 工具生命周期",
                    extra={
                        "requestId": request_id,
                        "toolCallId": audit_id,
                        "toolName": name if request.tool is not None else "unknown",
                        "argumentKeys": sorted(arguments),
                        "status": status,
                    },
                )
                emit("tool.call", {"toolId": audit_id, "toolName": name, "status": status})

            report("started")
            try:
                result = await handler(request)
                if not isinstance(result, ToolMessage) or result.status != "success":
                    raise RuntimeError("工具执行失败")
                if name == "knowledge_retrieval":
                    sources = RetrievalResult.model_validate_json(result.text).results
            except (Exception, asyncio.CancelledError) as exc:
                with CancelScope(shield=True):
                    await self._audits.finish(
                        scope,
                        audit_id,
                        int((perf_counter() - start) * 1000),
                        error_message="工具执行失败或已取消。",
                    )
                report("failed")
                if isinstance(exc, asyncio.CancelledError):
                    raise
                # Let parallel tools finish their audits before stopping the graph.
                tool_failed = True
                if isinstance(exc, McpFailure):
                    tool_error_code = exc.code
                return ToolMessage(
                    content="工具执行失败。",
                    tool_call_id=request.tool_call["id"],
                    status="error",
                    name=name,
                )
            await self._audits.finish(
                scope,
                audit_id,
                int((perf_counter() - start) * 1000),
                result_summary=f"返回 {len(sources)} 条检索结果。"
                if name == "knowledge_retrieval"
                else ("已按需加载 Skill。" if name == "load_skill" else "工具执行成功。"),
            )
            report("completed")
            for source in sources:
                kb = quote(source.knowledgeBaseId, safe="")
                document = quote(source.documentId, safe="")
                uri = f"/knowledge-bases/{kb}/documents/{document}"
                if source.chunkId not in references:
                    reference: EventData = {
                        **source.model_dump(mode="json"), "title": source.source, "uri": uri
                    }
                    references[source.chunkId] = reference
                    emit("reference.source", reference)
            return result

        try:
            session, history = await self._chat.detail(scope, session_id)
            if not any(record.id == user.id for record in history):
                raise RuntimeError("会话消息已清空")
            final: AIMessage | None = None
            configuration = await assemble_configuration(self._configuration, scope)
            mcp_tools = await self._mcp.tools(scope) if self._mcp is not None else []
            with tracing_context(enabled=False):
                async with self._model() as model:
                    agent = create_agent(
                        model,
                        tools=[
                            self._knowledge_tool(scope),
                            tool(get_current_time),
                            configuration.skill_tool,
                            *mcp_tools,
                        ],
                        middleware=[require_successful_tools, audit_tool],
                        system_prompt=configuration.system_prompt,
                    )
                    # system_prompt 由 create_agent 注入，历史摘要保留在消息上下文中。
                    context = context_messages(
                        session,
                        [row for row in history if row.sequence <= user.sequence],
                        configuration.system_prompt,
                    )
                    input_state: InputAgentState = {"messages": context[1:]}
                    updates = cast(
                        AsyncGenerator[dict[str, Any]],
                        agent.astream(  # pyright: ignore[reportUnknownMemberType]
                            input_state,
                            stream_mode="updates",
                            config={"recursion_limit": 24},
                        ),
                    )
                    async with aclosing(updates):
                        async for update in updates:
                            model_update = update.get("model")
                            if not model_update:
                                continue
                            message = model_update["messages"][-1]
                            if isinstance(message, AIMessage):
                                final = message
                                if reasoning := _reasoning(message):
                                    emit("reasoning.delta", {"text": reasoning})
            if (
                final is None
                or final.tool_calls
                or final.invalid_tool_calls
                or final.response_metadata.get("finish_reason") in ("length", "content_filter")
                or not final.text.strip()
            ):
                raise RuntimeError("模型未返回完整回答")
            _, assistant = await self._chat.append(
                scope,
                session_id,
                role="assistant",
                content=final.text,
                metadata={"references": list(references.values()), "toolCallIds": call_ids},
                after_user_message_id=user.id,
            )
            emit("content.delta", {"text": final.text})
            emit("complete", {"result": {"messageId": assistant.id}})
        except Exception as exc:
            logger.warning("Agent 对话失败", extra={"requestId": request_id})
            code = (
                exc.code
                if isinstance(exc, (MemoryFailure, McpFailure))
                else "SYSTEM_INTERNAL_ERROR"
            )
            category, status, message = ERROR_CATALOG[code]
            emit(
                "error",
                {
                    "error": {
                        "code": code,
                        "category": category,
                        "httpStatus": status,
                        "message": message,
                    },
                    "meta": {"requestId": request_id},
                },
            )
