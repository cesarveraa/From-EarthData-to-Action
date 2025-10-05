from datetime import datetime, timedelta, timezone

def parse_date(s: str | None) -> datetime:
    if not s:
        return datetime.now(timezone.utc)
    return datetime.fromisoformat(s.replace("Z","+00:00")).astimezone(timezone.utc)

def time_range(center: datetime, hours_back: int = 24, hours_fwd: int = 0):
    return center - timedelta(hours=hours_back), center + timedelta(hours=hours_fwd)
