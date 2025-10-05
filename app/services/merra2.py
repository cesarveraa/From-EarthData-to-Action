# app/services/merra2.py
from datetime import datetime, timezone
import math
import re
from typing import Tuple, List, Optional

from ..utils.time import parse_date
from ..core.config import settings
from ..utils.http import get_text
from ..schemas.common import DataSource

# -----------------------------------------------------------------------------
# 1) MODO RAW: URLs plantilla para MERRA-2 (OPeNDAP)
# -----------------------------------------------------------------------------
def merra2_urls(variables: list[str], date_iso: str | None):
    """
    Devuelve plantillas OPeNDAP para MERRA-2 (producto horario M2T1NXSLV).
    Se usa en los endpoints /data/* cuando están en modo RAW.
    """
    collection = "M2T1NXSLV.5.12.4"
    base = "https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2"
    return [
        DataSource(
            name="MERRA-2 (OPeNDAP 1h single-level)",
            url=f"{base}/{collection}/<YYYY>/<MM>/MERRA2_<stream>.<YYYYMMDD>.nc4",
            note=f"Vars: {', '.join(variables)} | Usa subsetting lat/lon/time | Earthdata requerido.",
            auth_required=True,
        )
    ]


# -----------------------------------------------------------------------------
# 2) MODO PREDICT: Fetch real con OPeNDAP (.ascii) para variables puntuales
# -----------------------------------------------------------------------------

# --- Grilla de MERRA-2 (M2T1NXSLV) ---
# latitud: paso 0.5° de -90..90  -> 361 puntos  (index 0..360)
# longitud: paso 0.625° de -180..180 -> 576 puntos (index 0..575)
def _m2_idx_lat(lat: float) -> int:
    return int(round((lat + 90.0) / 0.5))

def _m2_idx_lon(lon: float) -> int:
    return int(round((lon + 180.0) / 0.625))

def _m2_time_idx(dt: datetime) -> int:
    # producto horario -> índice = hora UTC (0..23)
    return dt.hour

def _m2_stream_for_year(year: int) -> str:
    """
    Selección simple del 'stream' para el año dado.
    Para años recientes (p. ej. 1992+), típicamente '400'.
    Ajusta si necesitas años antiguos.
    """
    return "400"

def _merra2_ascii_url(dt: datetime) -> str:
    """
    Construye la URL base OPeNDAP .ascii para el día dado (producto horario).
    """
    stream = _m2_stream_for_year(dt.year)
    # Ej: .../MERRA2_400.tavg1_2d_slv_Nx.YYYYMMDD.nc4.ascii
    return (
        "https://goldsmr4.gesdisc.eosdis.nasa.gov/opendap/MERRA2/"
        "M2T1NXSLV.5.12.4/"
        f"{dt:%Y}/{dt:%m}/MERRA2_{stream}.tavg1_2d_slv_Nx.{dt:%Y%m%d}.nc4.ascii"
    )

async def _fetch_m2_scalar(var: str, lat: float, lon: float, when_iso: str | None) -> Tuple[Optional[float], DataSource]:
    """
    Obtiene un escalar puntual de MERRA-2 (p. ej. T2M, RH2M, U10M, V10M, TS) vía OPeNDAP .ascii.
    Devuelve (valor, DataSource usado). Requiere Earthdata (basic auth).
    """
    dt = parse_date(when_iso).astimezone(timezone.utc)
    url_base = _merra2_ascii_url(dt)
    t = _m2_time_idx(dt)
    j = _m2_idx_lat(lat)
    i = _m2_idx_lon(lon)

    # Asegura rangos válidos
    j = max(0, min(360, j))
    i = max(0, min(575, i))

    url = f"{url_base}?{var}[{t}:{t}][{j}:{j}][{i}:{i}]"

    auth = None
    if settings.earthdata_username and settings.earthdata_password:
        auth = (settings.earthdata_username, settings.earthdata_password)

    try:
        txt = await get_text(url, auth=auth, timeout=40.0)
        # Busca línea tipo: var[0][0][0] = VALUE
        m = re.search(rf"{var}\[\d+\]\[\d+\]\[\d+\]\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", txt)
        if not m:
            return None, DataSource(
                name=f"MERRA-2 {var} (ascii subset)",
                url=url,
                note="Sin valor (subsetting vació o índice fuera de rango)",
                auth_required=True,
            )
        val = float(m.group(1))
        return val, DataSource(
            name=f"MERRA-2 {var}",
            url=url,
            note="OPeNDAP subset .ascii",
            auth_required=True,
        )
    except Exception:
        return None, DataSource(
            name=f"MERRA-2 {var} (error)",
            url=url,
            note="Fallo OPeNDAP/credenciales",
            auth_required=True,
        )

# ----------------- Wrappers de variables útiles -----------------
async def fetch_t2m_c(lat: float, lon: float, when_iso: str | None):
    """
    Temperatura a 2 m (K) → °C.
    """
    v, src = await _fetch_m2_scalar("T2M", lat, lon, when_iso)
    if v is None:
        return None, src
    return v - 273.15, src

async def fetch_rh2m(lat: float, lon: float, when_iso: str | None):
    """
    Humedad relativa a 2 m (%).
    """
    return await _fetch_m2_scalar("RH2M", lat, lon, when_iso)

async def fetch_ts_c(lat: float, lon: float, when_iso: str | None):
    """
    Skin temperature (K) → °C.
    """
    v, src = await _fetch_m2_scalar("TS", lat, lon, when_iso)
    if v is None:
        return None, src
    return v - 273.15, src

async def fetch_wind10m(lat: float, lon: float, when_iso: str | None):
    """
    Viento a 10 m: magnitud (m/s) a partir de U10M y V10M.
    Devuelve (speed_mps, [src_u, src_v])
    """
    u, src_u = await _fetch_m2_scalar("U10M", lat, lon, when_iso)
    v, src_v = await _fetch_m2_scalar("V10M", lat, lon, when_iso)
    if u is None or v is None:
        return None, [src_u, src_v]
    speed = math.sqrt(u * u + v * v)  # m/s
    return speed, [src_u, src_v]
