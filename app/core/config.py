# App/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from pathlib import Path

class Settings(BaseSettings):
    app_name: str = Field(default="AirHealth Data API", alias="APP_NAME")
    app_env: str = Field(default="dev", alias="APP_ENV")

    # Keys
    earthdata_username: str | None = Field(default=None, alias="EARTHDATA_USERNAME")
    earthdata_password: str | None = Field(default=None, alias="EARTHDATA_PASSWORD")
    openaq_api_key:   str | None = Field(default=None, alias="OPENAQ_API_KEY")
    airnow_api_key:   str | None = Field(default=None, alias="AIRNOW_API_KEY")

    # Bases
    worldview_base: str = Field(default="https://wvs.earthdata.nasa.gov/api/v1/snapshot", alias="WORLDVIEW_BASE")
    gesdisc_base:   str = Field(default="https://disc.gsfc.nasa.gov", alias="GESDISC_BASE")
    podaac_base:    str = Field(default="https://podaac.earthdata.nasa.gov", alias="PO.DAAC_BASE")

    # ✅ pydantic-settings v2: usa model_config, NO class Config
    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[1] / ".env"),  # App/.env
        env_file_encoding="utf-8",
        extra="ignore",
        protected_namespaces=("settings_",)  # quita el warning de "model_"
    )

settings = Settings()
