from pydantic import BaseModel, Field
from typing import Optional

class PredictBase(BaseModel):
    horizon_hours: int = Field(48, ge=1, le=168)
    auto_fetch: bool = False

class PredictAirQuality(PredictBase):
    # features opcionales si NO auto_fetch
    pm25: Optional[float] = None
    no2: Optional[float] = None
    aod: Optional[float] = None
    wind_speed: Optional[float] = None
    temperature: Optional[float] = None

class PredictPrecip(PredictBase):
    imerg_rate: Optional[float] = None
    rh: Optional[float] = None
    skin_temp: Optional[float] = None

class PredictTemperature(PredictBase):
    tmin: Optional[float] = None
    tmax: Optional[float] = None
    cloud_cover: Optional[float] = None

class PredictWind(PredictBase):
    mean_wind: Optional[float] = None
    mslp: Optional[float] = None
    gust: Optional[float] = None
