from pydantic import BaseModel, Field
from typing import Any

class Location(BaseModel):
    lat: float = Field(..., ge=-90, le=90)
    lon: float = Field(..., ge=-180, le=180)

class DataSource(BaseModel):
    name: str
    url: str
    note: str | None = None
    auth_required: bool = False

class DataBundle(BaseModel):
    location: Location
    timestamp: str
    sources: list[DataSource]
    artifacts: dict[str, Any] = {}
