from typing import Annotated, cast

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer
from starlette.responses import Response

from super_ai.alert_inputs import ActiveAlerts, AlertAggregator, AlertsUnavailable
from super_ai.auth import current_user
from super_ai.chat_contracts import ChatEnvelope
from super_ai.contracts import FailureEnvelope, failure, success
from super_ai.project_config import JsonObject

router = APIRouter(
    prefix="/aiops/alerts",
    dependencies=[Depends(HTTPBearer(auto_error=False))],
    responses={status: {"model": FailureEnvelope} for status in (401, 403, 503)},
)


def get_alert_aggregator(request: Request) -> AlertAggregator:
    return AlertAggregator(cast(JsonObject, request.app.state.project_config))


@router.get("/active", response_model=ChatEnvelope[ActiveAlerts])
async def active_alerts(
    request: Request,
    user: Annotated[dict[str, str], Depends(current_user)],
    aggregator: Annotated[AlertAggregator, Depends(get_alert_aggregator)],
) -> Response:
    del user  # 源是 deployment-global；本接口不持久化用户业务数据。
    try:
        result = await aggregator.active()
    except AlertsUnavailable:
        return failure("AIOPS_ALERTS_UNAVAILABLE", request)
    return success(result.model_dump(mode="json"), request)
