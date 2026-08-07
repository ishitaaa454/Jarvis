"""HTTP API for Phase 6 system monitoring."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, HTTPException, Query, Request
from pydantic import BaseModel, Field

from app.models.system_metrics import SystemMonitorStatusResponse
from app.services.system_monitor.metric_history_store import ALLOWED_METRICS
from app.services.system_monitor.system_monitor_service import SystemMonitorService

router = APIRouter(prefix="/api/system-monitor", tags=["system-monitor"])

ALLOWED_SORT = {"cpu", "memory", "name", "pid"}
ALLOWED_ORDER = {"asc", "desc"}
ALLOWED_RETRY = {"gpu", "temperatures", "battery", "network", "disk"}


def _service(request: Request) -> SystemMonitorService:
    return request.app.state.system_monitor_service


@router.get("/status", response_model=SystemMonitorStatusResponse)
async def get_status(request: Request) -> SystemMonitorStatusResponse:
    return _service(request).get_status()


@router.get("/snapshot")
async def get_snapshot(request: Request) -> dict:
    return _service(request).get_snapshot().model_dump(mode="json")


@router.get("/history")
async def get_history(
    request: Request,
    metric: str = Query(...),
    points: int | None = Query(default=None, ge=1, le=5000),
) -> dict:
    if metric not in ALLOWED_METRICS and not metric.startswith("cpu.core."):
        raise HTTPException(status_code=400, detail="Unknown metric name")
    service = _service(request)
    try:
        series = service.get_history(metric, points=points)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"metric": metric, "points": series}


@router.get("/processes")
async def get_processes(
    request: Request,
    sort: str = Query(default="cpu"),
    order: str = Query(default="desc"),
    limit: int = Query(default=25, ge=1, le=100),
    search: str = Query(default=""),
) -> dict:
    if sort.lower() not in ALLOWED_SORT:
        raise HTTPException(status_code=400, detail="Invalid sort field")
    if order.lower() not in ALLOWED_ORDER:
        raise HTTPException(status_code=400, detail="Invalid order")
    service = _service(request)
    # Prefer cached snapshot; re-sort/filter locally for query params.
    snapshot = service.get_processes()
    records = list(snapshot.processes)
    needle = search.strip().lower()
    if needle:
        records = [r for r in records if needle in r.name.lower()]
    reverse = order.lower() != "asc"
    key_map = {
        "cpu": lambda r: r.cpu_percent if r.cpu_percent is not None else -1.0,
        "memory": lambda r: r.memory_percent if r.memory_percent is not None else -1.0,
        "name": lambda r: r.name.lower(),
        "pid": lambda r: r.pid,
    }
    records.sort(key=key_map[sort.lower()], reverse=reverse)
    clipped = records[:limit]
    payload = snapshot.model_dump(mode="json")
    payload["processes"] = [r.model_dump(mode="json") for r in clipped]
    payload["returned"] = len(clipped)
    return payload


@router.get("/capabilities")
async def get_capabilities(request: Request) -> dict:
    caps = _service(request).get_capabilities()
    if caps is None:
        return {}
    return caps.model_dump(mode="json")


@router.get("/disks")
async def get_disks(request: Request) -> dict:
    snap = _service(request).get_snapshot()
    return snap.disks.model_dump(mode="json")


@router.get("/network-adapters")
async def get_network_adapters(request: Request) -> dict:
    snap = _service(request).get_snapshot()
    return {
        "adapters": [a.model_dump(mode="json") for a in snap.network.adapters],
        "active_adapter_count": snap.network.active_adapter_count,
        "collected_at": snap.network.collected_at.isoformat()
        if snap.network.collected_at
        else None,
    }


class RefreshResponse(BaseModel):
    accepted: bool = True
    status: SystemMonitorStatusResponse


@router.post("/refresh", response_model=RefreshResponse)
async def refresh(request: Request) -> RefreshResponse:
    status = await _service(request).request_refresh()
    return RefreshResponse(accepted=True, status=status)


@router.post("/retry-provider/{provider_name}", response_model=RefreshResponse)
async def retry_provider(provider_name: str, request: Request) -> RefreshResponse:
    if provider_name not in ALLOWED_RETRY:
        raise HTTPException(status_code=400, detail="Unknown provider")
    try:
        status = await _service(request).retry_provider(provider_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return RefreshResponse(accepted=True, status=status)
