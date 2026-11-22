import logging
from collections.abc import Generator
from contextlib import contextmanager
from contextvars import ContextVar

_active: ContextVar[bool] = ContextVar("mcp_private_operation", default=False)


class _PrivateTransportFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        # SDK debug/exception logs can contain messages, arguments, results and URLs.
        # Lifecycle diagnostics are emitted separately by the application audit layer.
        return not _active.get()


_filter = _PrivateTransportFilter()


@contextmanager
def private_transport_logs() -> Generator[None]:
    names = ["httpx", "mcp.client.sse", "mcp.client.streamable_http", "mcp.shared.session"]
    names.extend(
        name
        for name in list(logging.Logger.manager.loggerDict)
        if name.startswith(("mcp.", "httpcore.", "langchain_mcp_adapters."))
    )
    for name in names:
        logger = logging.getLogger(name)
        if _filter not in logger.filters:
            logger.addFilter(_filter)
    token = _active.set(True)
    try:
        yield
    finally:
        _active.reset(token)
