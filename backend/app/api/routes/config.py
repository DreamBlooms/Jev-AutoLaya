from __future__ import annotations

from fastapi import APIRouter

from app.api.serializers import config_out
from app.schemas.config import DeviceUpdate
from app.services.runtime import set_device_preference

router = APIRouter(tags=["config"])


@router.get("/config")
def get_config() -> dict:
    return {"data": config_out()}


@router.post("/config/device")
def update_device(payload: DeviceUpdate) -> dict:
    set_device_preference(payload.device)
    return {"data": config_out()}
