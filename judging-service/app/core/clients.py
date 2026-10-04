"""Calls to the other services, forwarding the caller's token."""
import httpx
from fastapi import HTTPException, status


def get_json(url: str, token: str) -> dict | None:
    """Return the JSON body, None on 404, and raise 503 if the service is unreachable."""
    try:
        resp = httpx.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=5.0)
    except httpx.HTTPError as exc:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, f"Upstream unavailable: {url}") from exc
    if resp.status_code == 404:
        return None
    if resp.status_code in (401, 403):
        raise HTTPException(resp.status_code, resp.json().get("detail", "Not allowed"))
    if resp.status_code >= 400:
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, f"Upstream error {resp.status_code}: {url}")
    return resp.json()
