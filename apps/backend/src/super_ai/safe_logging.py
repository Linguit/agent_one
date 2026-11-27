"""Exception diagnostics without messages, source lines, locals or payloads."""

import logging
import traceback
from typing import cast

_SAFE_CODES = frozenset({
    "MCP_DISCOVERY_FAILED", "MCP_TIMEOUT", "MCP_CALL_FAILED",
    "MCP_TOOL_NAME_CONFLICT", "MCP_CONFIG_INVALID", "SYSTEM_UNAVAILABLE",
    "DIAGNOSTIC_EXECUTION_FAILED", "DIAGNOSTIC_KNOWLEDGE_FAILED",
    "DIAGNOSTIC_TOOL_FAILED", "DIAGNOSTIC_INVALID_PLAN", "DIAGNOSTIC_MODEL_FAILED",
})


def log_failure(logger: logging.Logger, stage: str, exc: BaseException) -> None:
    """Log only structural exception data; never format the exception itself."""
    pending = [exc]
    seen: set[int] = set()
    while pending and len(seen) < 16:
        current = pending.pop(0)
        if id(current) in seen:
            continue
        seen.add(id(current))
        code = current.args[0] if current.args else None
        safe_code = code if isinstance(code, str) and code in _SAFE_CODES else "REDACTED"
        frames = traceback.extract_tb(current.__traceback__)
        locations = " > ".join(
            f"{frame.filename.replace(chr(92), '/').rsplit('/', 1)[-1]}:"
            f"{frame.lineno}:{frame.name}" for frame in frames
        )
        logger.error(
            "执行异常 stage=%s exception_type=%s code=%s frames=%s",
            stage, type(current).__name__, safe_code, locations,
        )
        if current.__cause__ is not None:
            pending.append(current.__cause__)
        elif current.__context__ is not None:
            pending.append(current.__context__)
        nested = getattr(current, "exceptions", ())
        if isinstance(nested, tuple):
            pending.extend(item for item in cast(tuple[object, ...], nested)
                           if isinstance(item, BaseException))
