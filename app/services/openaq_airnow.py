# app/services/openaq_airnow.py
from typing import Tuple, Optional, Dict, Any, List
import httpx

from ..schemas.common import DataSource
from ..core.config import settings
from ..utils.http import get_json


def _headers() -> Dict[str, str]:
    """Headers para OpenAQ v3 (X-API-Key si está configurado)."""
    return {"X-API-Key": settings.openaq_api_key} if settings.openaq_api_key else {}


async def openaq_latest_nearby_values(
    lat: float,
    lon: float,
    radius_km: float = 25.0,
    wanted: Tuple[str, ...] = ("pm25", "no2", "o3"),
) -> Tuple[Dict[str, Any], DataSource]:
    """
    Flujo recomendado OpenAQ v3:
      1) /v3/locations?coordinates=lat,lon&radius=...
      2) /v3/locations/{id}   -> para mapear sensorsId -> parameter name/units
      3) /v3/locations/{id}/latest -> últimos valores por sensor

    Devuelve: (payload, DataSource)
      payload = {
        "location_id": <int>,
        "observations": [{"name": "PM2.5"|"NO2"|"O3", "value": <float>, "unit": "µg/m³|ppb|..."}]
      }
    """
    meters = int(radius_km * 1000)
    h = _headers()
    note = "OpenAQ v3 locations→latest"

    # 1) estación más cercana
    locs_url = (
        f"https://api.openaq.org/v3/locations?"
        f"coordinates={lat},{lon}&radius={meters}&limit=1&order_by=distance&sort=asc"
    )
    try:
        locs = await get_json(locs_url, headers=h)
    except httpx.HTTPStatusError as e:
        return {"error": f"OpenAQ {e.response.status_code}"}, DataSource(
            name="OpenAQ v3 (error)", url=locs_url, note=note, auth_required=True
        )

    locs_res = (locs or {}).get("results", [])
    if not locs_res:
        return {"warning": "No nearby OpenAQ locations"}, DataSource(
            name="OpenAQ locations", url=locs_url, note=note, auth_required=True
        )

    loc = locs_res[0]
    loc_id = loc.get("id")

    # 2) detalle de la estación para mapear sensores → parámetros
    loc_detail_url = f"https://api.openaq.org/v3/locations/{loc_id}"
    try:
        loc_detail = await get_json(loc_detail_url, headers=h)
    except httpx.HTTPStatusError as e:
        return {"error": f"OpenAQ {e.response.status_code}"}, DataSource(
            name="OpenAQ v3 (error)", url=loc_detail_url, note=note, auth_required=True
        )

    sensor_map: Dict[Any, Dict[str, Optional[str]]] = {}
    loc_detail_res = (loc_detail.get("results") or [{}])[0]
    for s in (loc_detail_res.get("sensors") or []):
        sid = s.get("id")
        p = (s.get("parameter") or {})
        if sid is not None:
            sensor_map[sid] = {
                "name": (p.get("name") or "").lower(),       # pm25, no2, o3, etc.
                "units": p.get("units"),                      # µg/m³, ppb, ppm, ...
                "display": p.get("displayName"),
            }

    # 3) latest
    latest_url = f"https://api.openaq.org/v3/locations/{loc_id}/latest"
    try:
        latest = await get_json(latest_url, headers=h)
    except httpx.HTTPStatusError as e:
        return {"error": f"OpenAQ {e.response.status_code}"}, DataSource(
            name="OpenAQ v3 (error)", url=latest_url, note=note, auth_required=True
        )

    wanted_set = set(wanted)
    observations: List[Dict[str, Any]] = []

    for r in latest.get("results", []):
        sid = r.get("sensorsId")
        if sid not in sensor_map:
            continue
        meta = sensor_map[sid]
        pname = meta.get("name") or ""
        units = meta.get("units")
        val = r.get("value")
        if pname in wanted_set and val is not None:
            # Normaliza gases ppm → ppb si hace falta
            if pname in ("no2", "o3") and units == "ppm":
                val = val * 1000.0
                units = "ppb"
            # Etiquetas de salida bonitas
            out_name = "PM2.5" if pname == "pm25" else pname.upper()
            observations.append({"name": out_name, "value": val, "unit": units})

    payload = {"location_id": loc_id, "observations": observations}
    src = DataSource(name="OpenAQ latest by location (v3)", url=latest_url, note=note, auth_required=True)
    return payload, src


async def airnow_nearby(
    lat: float,
    lon: float,
    distance_miles: float = 25.0
) -> Tuple[Dict[str, Any], DataSource]:
    """
    Observaciones actuales cercanas vía AirNow.
    Requiere AIRNOW_API_KEY (cobertura principalmente EE.UU.).
    """
    if not settings.airnow_api_key:
        return {
            "warning": "AIRNOW_API_KEY not set"
        }, DataSource(
            name="AirNow observations",
            url=(
                "https://www.airnowapi.org/aq/observation/latLong/current/"
                "?format=application/json&latitude=..&longitude=..&distance=..&API_KEY=<REQUIRED>"
            ),
            note="Requiere API key.",
            auth_required=True,
        )

    url = (
        "https://www.airnowapi.org/aq/observation/latLong/current/"
        f"?format=application/json&latitude={lat}&longitude={lon}&distance={distance_miles}"
        f"&API_KEY={settings.airnow_api_key}"
    )
    try:
        data = await get_json(url)
        return data, DataSource(name="AirNow observations", url=url, note="Requiere API key.", auth_required=True)
    except httpx.HTTPStatusError as e:
        return {"error": f"AirNow {e.response.status_code}"}, DataSource(
            name="AirNow (error)", url=url, note="Verifica API key y parámetros.", auth_required=True
        )
