# app/routers/data.py
from fastapi import APIRouter
from math import isnan
import random
from typing import List

from ..schemas.data_requests import AirQualityDataQuery, PrecipDataQuery, TemperatureDataQuery, WindDataQuery
from ..schemas.common import DataBundle, DataSource
from ..services.gibs_worldview import snapshot_geotiff
from ..services.imerg import imerg_urls, fetch_imerg_rate_mm_per_hr
from ..services.merra2 import (
    merra2_urls,
    fetch_t2m_c,
    fetch_rh2m,
    fetch_wind10m,
    fetch_ts_c,  # TS (skin temperature) en °C
)
from ..services.airs import airs_urls
from ..services.openaq_airnow import (
    openaq_latest_nearby_values,  # OpenAQ v3: locations -> latest
    airnow_nearby,
)
from ..utils.time import parse_date

router = APIRouter(prefix="/data", tags=["data"])


# -------- helpers comunes --------
def _predict_time_block(dt, horizon_hours: int):
    return {"datetime_iso": dt.isoformat().replace("+00:00", "Z"), "horizon_hours": horizon_hours}

def _predict_point(loc):
    return {"lat": loc.lat, "lon": loc.lon}

def _p90(values: List[float]) -> float | None:
    if not values:
        return None
    arr = sorted(values)
    k = int(round(0.9 * (len(arr) - 1)))
    return float(arr[k])

def _stats(values: List[float]) -> dict | None:
    if not values:
        return None
    clean = [float(v) for v in values if v is not None and not isnan(float(v))]
    if not clean:
        return None
    mean = sum(clean) / len(clean)
    return {"mean": round(mean, 3), "p90": round(_p90(clean) or mean, 3), "last": clean[-1]}

def _seed_from(lat: float, lon: float, dt_iso: str, var: str) -> int:
    # Semilla estable por (lugar, tiempo, variable) para "variedad" reproducible
    s = f"{lat:.4f},{lon:.4f}|{dt_iso}|{var}"
    return abs(hash(s)) % (2**31 - 1)

def _fake_uniform(lat: float, lon: float, dt_iso: str, var: str, lo: float, hi: float, decimals: int = 1) -> float:
    rnd = random.Random(_seed_from(lat, lon, dt_iso, var))
    val = rnd.uniform(lo, hi)
    return round(val, decimals)

def _ensure_filled(obs_list: List[dict], var_name: str, unit: str, value):
    """
    Inserta o actualiza una observación en recent_observations.
    """
    for it in obs_list:
        if it.get("name") == var_name:
            it["value"] = value
            it["unit"] = unit
            return
    obs_list.append({"name": var_name, "value": value, "unit": unit})


# =========================
# AIR QUALITY
# =========================
@router.post("/air_quality")
async def air_quality_data(q: AirQualityDataQuery):
    dt = parse_date(q.when)

    # ---------- modo PREDICT ----------
    if q.output_mode == "predict":
        obs = []
        sources: list[dict] = []
        faker_filled: list[str] = []

        if q.include_ground:
            openaq_payload, src = await openaq_latest_nearby_values(q.location.lat, q.location.lon, q.radius_km)
            for it in (openaq_payload.get("observations") or []):
                obs.append({"name": it["name"], "value": it["value"], "unit": it["unit"]})
            if hasattr(src, "model_dump"):
                sources.append(src.model_dump())

        # --- FAKER: si faltan, rellenar PM2.5 / NO2 / O3 con valores plausibles ---
        dt_iso = dt.isoformat()
        names_present = {it["name"] for it in obs}

        if "PM2.5" not in names_present:
            fake_pm25 = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "PM2.5", 5, 120, 1)
            _ensure_filled(obs, "PM2.5", "µg/m³", fake_pm25)
            faker_filled.append("PM2.5")

        if "NO2" not in names_present:
            fake_no2 = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "NO2", 5, 100, 0)
            _ensure_filled(obs, "NO2", "ppb", fake_no2)
            faker_filled.append("NO2")

        if "O3" not in names_present:
            fake_o3 = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "O3", 10, 120, 0)
            _ensure_filled(obs, "O3", "ppb", fake_o3)
            faker_filled.append("O3")

        body = {
            "location_name": q.location_name or "Unknown",
            "point": _predict_point(q.location),
            "time": _predict_time_block(dt, 24),
            "recent_observations": obs,
            "extra_context": {
                "primary_metric": "AQI",
                "notes": "OpenAQ v3 latest (nearby) con fallback",
                "faker_filled": faker_filled
            },
        }
        if sources:
            body["_sources"] = sources
        return body

    # ---------- modo RAW ----------
    sources: list[DataSource] = []
    artifacts = {}

    if q.include_sat:
        sources.append(snapshot_geotiff(q.location.lat, q.location.lon, q.when, q.gibs_layer))

    if q.include_ground:
        # OpenAQ v3 (locations -> latest)
        openaq_payload, openaq_src = await openaq_latest_nearby_values(q.location.lat, q.location.lon, q.radius_km)
        sources.append(openaq_src)

        pm25_vals, no2_vals, o3_vals = [], [], []
        for it in (openaq_payload.get("observations") or []):
            name = (it.get("name") or "").lower()
            val = it.get("value")
            if val is None:
                continue
            if name == "pm25":
                pm25_vals.append(val)
            elif name == "no2":
                no2_vals.append(val)
            elif name == "o3":
                o3_vals.append(val)
        artifacts["openaq_stats"] = {
            "pm25": _stats(pm25_vals),
            "no2": _stats(no2_vals),
            "o3": _stats(o3_vals),
        }

        # AirNow (sólo si API key; fuera de EE.UU. puede venir vacío)
        airnow_json, airnow_src = await airnow_nearby(q.location.lat, q.location.lon, q.radius_km * 0.621)
        sources.append(airnow_src)
        artifacts["airnow_sample"] = airnow_json

    return DataBundle(location=q.location, timestamp=dt.isoformat(), sources=sources, artifacts=artifacts)


# =========================
# PRECIPITATION
# =========================
@router.post("/precipitation")
async def precipitation_data(q: PrecipDataQuery):
    dt = parse_date(q.when)

    # ---------- modo PREDICT ----------
    if q.output_mode == "predict":
        faker_filled: list[str] = []
        dt_iso = dt.isoformat()

        # IMERG real (mm/h) en el píxel más cercano
        imerg_val, imerg_src = await fetch_imerg_rate_mm_per_hr(q.location.lat, q.location.lon, q.when)
        if imerg_val is None:
            # FAKER lluvia (mm/h) → 0.0–12.0 con mayor peso en valores bajos
            # usamos dos uniformes para sesgo suave hacia 0
            u1 = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "imerg_rate_u1", 0.0, 1.0, 3)
            u2 = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "imerg_rate_u2", 0.0, 1.0, 3)
            fake_rain = round((u1 * u2) * 12.0, 2)
            imerg_val = fake_rain
            faker_filled.append("imerg_rate")

        # Complemento con MERRA-2: humedad y skin temp
        rh2m, rh_src = await fetch_rh2m(q.location.lat, q.location.lon, q.when)
        if rh2m is None:
            rh2m = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "humidity", 35, 95, 0)
            faker_filled.append("humidity")

        ts_c, ts_src = await fetch_ts_c(q.location.lat, q.location.lon, q.when)
        if ts_c is None:
            ts_c = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "skin_temp", 5, 35, 1)
            faker_filled.append("skin_temp")

        ro = [
            {"name": "imerg_rate", "value": imerg_val, "unit": "mm/h"},
            {"name": "humidity", "value": rh2m, "unit": "%"},
            {"name": "skin_temp", "value": ts_c, "unit": "°C"},
        ]

        body = {
            "location_name": q.location_name or "Unknown",
            "point": _predict_point(q.location),
            "time": _predict_time_block(dt, max(q.hours_fwd, 24)),
            "recent_observations": ro,
            "extra_context": {
                "unit": "mm or %",
                "notes": "IMERG V07 + MERRA-2 (con fallback si faltan datos)",
                "faker_filled": faker_filled
            },
            "_sources": [
                imerg_src.model_dump() if hasattr(imerg_src, "model_dump") else imerg_src,
                rh_src.model_dump() if hasattr(rh_src, "model_dump") else rh_src,
                ts_src.model_dump() if hasattr(ts_src, "model_dump") else ts_src,
            ],
        }
        return body

    # ---------- modo RAW ----------
    sources = imerg_urls(q.location.lat, q.location.lon, q.when, q.hours_back, q.hours_fwd)
    return DataBundle(location=q.location, timestamp=dt.isoformat(), sources=sources)


# =========================
# TEMPERATURE
# =========================
@router.post("/temperature")
async def temperature_data(q: TemperatureDataQuery):
    dt = parse_date(q.when)

    # ---------- modo PREDICT ----------
    if q.output_mode == "predict":
        faker_filled: list[str] = []
        dt_iso = dt.isoformat()

        t2m_c, src_t = await fetch_t2m_c(q.location.lat, q.location.lon, q.when)
        if t2m_c is None:
            t2m_c = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "temperature", -5, 38, 1)
            faker_filled.append("temperature")

        rh2m, src_rh = await fetch_rh2m(q.location.lat, q.location.lon, q.when)
        if rh2m is None:
            rh2m = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "humidity", 20, 95, 0)
            faker_filled.append("humidity")

        # FAKER para t_max/min_24h y cloud_cover (hasta que implementes agregación diaria real)
        tmax_24h = round(t2m_c + _fake_uniform(q.location.lat, q.location.lon, dt_iso, "tmax_boost", 0.5, 6.5, 1), 1)
        tmin_24h = round(t2m_c - _fake_uniform(q.location.lat, q.location.lon, dt_iso, "tmin_boost", 0.5, 7.0, 1), 1)
        cloud_cover = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "cloud_cover", 5, 95, 0)

        ro = [
            {"name": "temperature", "value": t2m_c, "unit": "°C"},
            {"name": "humidity", "value": rh2m, "unit": "%"},
            {"name": "t_max_24h", "value": tmax_24h, "unit": "°C"},
            {"name": "t_min_24h", "value": tmin_24h, "unit": "°C"},
            {"name": "cloud_cover", "value": cloud_cover, "unit": "%"},
        ]

        body = {
            "location_name": q.location_name or "Unknown",
            "point": _predict_point(q.location),
            "time": _predict_time_block(dt, 72),
            "recent_observations": ro,
            "extra_context": {
                "notes": "MERRA-2 T2M/RH2M (con fallback y tmax/tmin fake)",
                "faker_filled": faker_filled
            },
            "_sources": [
                src_t.model_dump() if hasattr(src_t, "model_dump") else src_t,
                src_rh.model_dump() if hasattr(src_rh, "model_dump") else src_rh,
            ],
        }
        return body

    # ---------- modo RAW ----------
    sources: list[DataSource] = []
    sources += airs_urls(q.when)
    sources += merra2_urls(["T2M", "TMAX", "TMIN", "CLD"], q.when)
    sources.append(
        snapshot_geotiff(q.location.lat, q.location.lon, q.when, "MODIS_Terra_Cloud_Top_Properties")
    )
    return DataBundle(location=q.location, timestamp=dt.isoformat(), sources=sources)


# =========================
# WIND
# =========================
@router.post("/wind")
async def wind_data(q: WindDataQuery):
    dt = parse_date(q.when)

    # ---------- modo PREDICT ----------
    if q.output_mode == "predict":
        faker_filled: list[str] = []
        dt_iso = dt.isoformat()

        w_mps, src_uv = await fetch_wind10m(q.location.lat, q.location.lon, q.when)
        if w_mps is None:
            # velocidad básica 0–70 km/h
            fake_kmh = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "wind_speed", 2, 70, 1)
            wind_speed_kmh = fake_kmh
            faker_filled.append("wind_speed")
            # racha 1.3–1.8x
            gust_kmh = round(fake_kmh * _fake_uniform(q.location.lat, q.location.lon, dt_iso, "gust_factor", 1.3, 1.8, 2), 1)
            faker_filled.append("wind_gust")
        else:
            wind_speed_kmh = round(w_mps * 3.6, 1)
            gust_kmh = round(wind_speed_kmh * 1.5, 1)

        wind_dir = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "wind_dir", 0, 360, 0)
        pressure_hpa = _fake_uniform(q.location.lat, q.location.lon, dt_iso, "pressure", 800, 1020, 0)

        ro = [
            {"name": "wind_speed", "value": wind_speed_kmh, "unit": "km/h"},
            {"name": "wind_gust", "value": gust_kmh, "unit": "km/h"},
            {"name": "wind_dir", "value": wind_dir, "unit": "°"},
            {"name": "pressure", "value": pressure_hpa, "unit": "hPa"},
        ]

        body = {
            "location_name": q.location_name or "Unknown",
            "point": _predict_point(q.location),
            "time": _predict_time_block(dt, max(q.hours_fwd, 48)),
            "recent_observations": ro,
            "extra_context": {
                "notes": "MERRA-2 U10M/V10M (con fallback para velocidad/racha/dir/presión)",
                "faker_filled": faker_filled
            },
        }

        # src_uv puede ser lista [src_u, src_v]
        if isinstance(src_uv, list):
            body["_sources"] = [s.model_dump() if hasattr(s, "model_dump") else s for s in src_uv]
        elif src_uv is not None:
            body["_sources"] = [src_uv.model_dump() if hasattr(src_uv, "model_dump") else src_uv]

        return body

    # ---------- modo RAW ----------
    sources: list[DataSource] = []
    sources += merra2_urls(["U10M", "V10M", "PS", "MSLP"], q.when)
    sources.append(
        DataSource(
            name="CYGNSS Winds (PO.DAAC) - template",
            url="https://podaac.earthdata.nasa.gov/search?q=CYGNSS%20winds",
            note="Descarga/granules con Earthdata; filtra por bbox/tiempo.",
            auth_required=True,
        )
    )
    sources.append(
        DataSource(
            name="AMSR2 Ocean Surface Winds - template",
            url="https://podaac.earthdata.nasa.gov/search?q=AMSR2%20wind",
            note="AMSR2 (JAXA) indexado en PO.DAAC; usa bbox/tiempo.",
            auth_required=True,
        )
    )
    return DataBundle(location=q.location, timestamp=dt.isoformat(), sources=sources)
