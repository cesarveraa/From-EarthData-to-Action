# App/utils/http.py
import httpx
from typing import Optional

async def get_json(url: str, headers: Optional[dict] = None, auth: Optional[tuple] = None, timeout: float = 30.0):
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers=headers, auth=auth)
        r.raise_for_status()
        return r.json()

async def get_text(url: str, headers: Optional[dict] = None, auth: Optional[tuple] = None, timeout: float = 30.0):
    async with httpx.AsyncClient(timeout=timeout) as client:
        r = await client.get(url, headers=headers, auth=auth)
        r.raise_for_status()
        return r.text

async def head(url: str, headers: Optional[dict] = None, auth: Optional[tuple] = None, timeout: float = 30.0):
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        r = await client.head(url, headers=headers, auth=auth)
        return {"status_code": r.status_code, "headers": dict(r.headers)}
