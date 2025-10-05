# app/services/imerg.py
from datetime import datetime, timezone, timedelta
import re, math
from ..utils.time import parse_date
from ..schemas.common import DataSource
from ..core.config import settings
from ..utils.http import get_text

# -------- utilidades de grid ----------
def _imerg_idx_lat(lat: float) -> int:
    # IMERG 0.1° grilla [-90..90], 1800 puntos
    return int(round((lat + 90.0) * 10.0))

def _imerg_idx_lon(lon: float) -> int:
    # IMERG 0.1° grilla [-180..180], 3600 puntos
    return int(round((lon + 180.0) * 10.0))

def _half_hour_window(dt: datetime):
    minute = 0 if dt.minute < 30 else 30
    start = dt.replace(minute=minute, second=0, microsecond=0)
    end = start + timedelta(minutes=29, seconds=59)
    return start, end

def _imerg_granule_name(dt: datetime) -> str:
    s,e = _half_hour_window(dt)
    # 3B-HHR-L.MS.MRG.3IMERG.YYYYMMDD-SHHMMSS-EHHMMSS.V07B.HDF5
    return f"3B-HHR-L.MS.MRG.3IMERG.{dt:%Y%m%d}-S{s:%H%M%S}-E{e:%H%M%S}.V07B.HDF5"

def build_imerg_ascii_url(dt: datetime) -> str:
    coll = "GPM_3IMERGHH.07"
    fname = _imerg_granule_name(dt)
    return (f"https://gpm1.gesdisc.eosdis.nasa.gov/opendap/GPM_L3/{coll}/"
            f"{dt:%Y}/{dt:%m}/{dt:%d}/{fname}.ascii")

# ✅ NUEVO: provee el símbolo que tu router intenta importar
def imerg_urls(when_iso: str) -> list[str]:
    """
    Devuelve una lista de URLs relevantes para IMERG en el timestamp dado (UTC).
    Por ahora solo el endpoint .ascii con OPeNDAP subset (la lista permite crecer a futuro).
    """
    dt = parse_date(when_iso).astimezone(timezone.utc)
    return [build_imerg_ascii_url(dt)]

async def fetch_imerg_rate_mm_per_hr(lat: float, lon: float, when_iso: str | None, radius_cells: int = 0):
    """
    Devuelve precipitación (mm/h) de IMERG V07 (precipitationCal) para el píxel más cercano.
    Requiere Earthdata (basic auth). Usa OPeNDAP .ascii con subsetting por índice.
    """
    dt = parse_date(when_iso).astimezone(timezone.utc)
    url_base = build_imerg_ascii_url(dt)
    iy = _imerg_idx_lat(lat)
    ix = _imerg_idx_lon(lon)

    # extrae 1 píxel (o pequeño vecindario si radius_cells>0)
    y0, y1 = max(0, iy - radius_cells), min(1799, iy + radius_cells)
    x0, x1 = max(0, ix - radius_cells), min(3599, ix + radius_cells)
    q = f"?precipitationCal[{y0}:{y1}][{x0}:{x1}]"
    url = url_base + q

    auth = None
    if settings.earthdata_username and settings.earthdata_password:
        auth = (settings.earthdata_username, settings.earthdata_password)

    try:
        txt = await get_text(url, auth=auth, timeout=40.0)

        # Corrige el regex: un solo grupo de captura (no-capturing group para el exponente)
        matches = re.findall(r"precipitationCal\[\d+\]\[\d+\]\s*=\s*([-+]?\d*\.?\d+(?:[eE][-+]?\d+)?)", txt)
        vals = [float(m) for m in matches]

        if not vals:
            # Parser alterno en la sección Data:
            body = txt.split("Data:")[-1] if "Data:" in txt else txt
            nums = re.findall(r"[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?", body)
            vals = [float(n) for n in nums] if nums else []

        if not vals:
            return None, DataSource(name="IMERG (ascii subset)", url=url, note="Sin datos en píxel", auth_required=True)

        avg = sum(vals) / len(vals)
        return float(avg), DataSource(name="IMERG precipitationCal (mm/h)", url=url, note="OPeNDAP subset .ascii", auth_required=True)

    except Exception as ex:
        return None, DataSource(name="IMERG (error)", url=url, note=f"Fallo OPeNDAP/credenciales: {ex}", auth_required=True)
