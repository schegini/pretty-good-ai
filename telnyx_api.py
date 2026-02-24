"""Telnyx Call Control API wrapper."""

import httpx
from config import TELNYX_API_KEY

BASE = "https://api.telnyx.com/v2"
HEADERS = {
    "Authorization": f"Bearer {TELNYX_API_KEY}",
    "Content-Type": "application/json",
}


async def _post(path: str, json: dict) -> dict:
    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{BASE}{path}", headers=HEADERS, json=json, timeout=30)
        resp.raise_for_status()
        return resp.json()


async def create_call(to: str, from_: str, connection_id: str, webhook_url: str) -> dict:
    """Place an outbound call."""
    data = await _post("/calls", {
        "to": to,
        "from": from_,
        "connection_id": connection_id,
        "webhook_url": webhook_url,
    })
    return data["data"]


async def stream_start(call_control_id: str, stream_url: str) -> dict:
    """Start bidirectional audio streaming on a call."""
    return await _post(f"/calls/{call_control_id}/actions/streaming_start", {
        "stream_url": stream_url,
        "stream_track": "inbound_track",
    })


async def hangup(call_control_id: str) -> dict:
    """Hang up a call."""
    return await _post(f"/calls/{call_control_id}/actions/hangup", {})