# App/schemas/data_requests.py
from pydantic import BaseModel, Field
from typing import Literal, Optional
from .common import Location

class BaseDataQuery(BaseModel):
    location: Location
    when: str | None = Field(None, description="ISO datetime; default now (UTC)")
    radius_km: float | None = 25
    # NUEVO:
    location_name: Optional[str] = None
    output_mode: Literal["raw", "predict"] = "raw"

class AirQualityDataQuery(BaseDataQuery):
    include_ground: bool = True
    include_sat: bool = True
    gibs_layer: str = "MODIS_Terra_Aerosol"

class PrecipDataQuery(BaseDataQuery):
    hours_back: int = 24
    hours_fwd: int = 24

class TemperatureDataQuery(BaseDataQuery):
    days_back: int = 2
    days_fwd: int = 2

class WindDataQuery(BaseDataQuery):
    hours_back: int = 24
    hours_fwd: int = 48
