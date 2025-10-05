from dataclasses import dataclass

@dataclass
class BBox:
    west: float
    south: float
    east: float
    north: float

def point_bbox(lat: float, lon: float, half_size_deg: float = 0.2) -> BBox:
    return BBox(
        west=lon - half_size_deg,
        south=lat - half_size_deg,
        east=lon + half_size_deg,
        north=lat + half_size_deg
    )
