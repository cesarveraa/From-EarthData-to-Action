from ..core.config import settings
from ..utils.geo import point_bbox
from ..utils.time import parse_date
from ..schemas.common import DataSource

def snapshot_geotiff(lat: float, lon: float, when: str | None, layer: str, bbox_half_deg: float = 0.2, width: int = 1024, height: int = 1024, crs="EPSG:4326"):
    dt = parse_date(when)
    bbox = point_bbox(lat, lon, bbox_half_deg)
    url = (
        f"{settings.worldview_base}?REQUEST=GetSnapshot"
        f"&TIME={dt.strftime('%Y-%m-%d')}"
        f"&BBOX={bbox.south},{bbox.west},{bbox.north},{bbox.east}"
        f"&CRS={crs}&LAYERS={layer}&FORMAT=image/geotiff&WIDTH={width}&HEIGHT={height}"
    )
    return DataSource(
        name=f"GIBS Worldview {layer}",
        url=url,
        note="GeoTIFF vía Worldview Snapshots; descarga directa sin autenticación.",
        auth_required=False
    )
