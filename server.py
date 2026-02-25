"""FastAPI server handling Telnyx webhooks and media streams.

Endpoints:
  POST /webhook          — Telnyx Call Control events
  WS   /media-stream     — Telnyx bidirectional audio stream
  POST /calls/{index}    — Trigger an outbound call with a scenario
  GET  /scenarios         — List available scenarios
"""

import asyncio
import json
import os
from datetime import datetime

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import JSONResponse

import telnyx_api
from bridge import RealtimeBridge
from config import (
    MAX_CALL_DURATION,
    STREAM_URL,
    TARGET_NUMBER,
    TELNYX_CONNECTION_ID,
    TELNYX_FROM_NUMBER,
    WEBHOOK_URL,
)
from scenarios import SCENARIOS

app = FastAPI(title="Voice Bot — Patient Simulator (Realtime)")


@app.on_event("startup")
async def startup_check():
    """Validate config on startup."""
    print()
    print("  Voice Bot — Patient Simulator (Realtime API)")
    print()
    issues = []
    if not TELNYX_FROM_NUMBER or TELNYX_FROM_NUMBER == "+1XXXXXXXXXX":
        issues.append("TELNYX_FROM_NUMBER not set")
    else:
        print(f"  From number:  {TELNYX_FROM_NUMBER}")
    if not TELNYX_CONNECTION_ID or "your_" in (TELNYX_CONNECTION_ID or ""):
        issues.append("TELNYX_CONNECTION_ID not set")
    if not WEBHOOK_URL or "your-domain" in WEBHOOK_URL:
        issues.append("WEBHOOK_BASE_URL not set")
    else:
        print(f"  Webhook URL:  {WEBHOOK_URL}")
        print(f"  Stream URL:   {STREAM_URL}")
    if not OPENAI_API_KEY or "your_" in (OPENAI_API_KEY or ""):
        issues.append("OPENAI_API_KEY not set")
    print(f"  Target:       {TARGET_NUMBER}")
    print(f"  Scenarios:    {len(SCENARIOS)}")
    if issues:
        print(f"\n  CONFIG ISSUES:")
        for i in issues:
            print(f"    - {i}")
    print()

# In-memory state
# call_control_id → {scenario, bridge, ...}
calls: dict[str, dict] = {}

TRANSCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "transcripts")
os.makedirs(TRANSCRIPTS_DIR, exist_ok=True)


# Call trigger endpoint
@app.post("/calls/{scenario_index}")
async def trigger_call(scenario_index: int):
    """Trigger an outbound call using a specific scenario."""
    if scenario_index < 0 or scenario_index >= len(SCENARIOS):
        return JSONResponse({"error": f"Invalid index. Use 0-{len(SCENARIOS)-1}"}, 400)

    scenario = SCENARIOS[scenario_index]
    print(f"\n Placing call — Scenario: {scenario['name']}")

    try:
        result = await telnyx_api.create_call(
            to=TARGET_NUMBER,
            from_=TELNYX_FROM_NUMBER,
            connection_id=TELNYX_CONNECTION_ID,
            webhook_url=WEBHOOK_URL,
        )
    except Exception as e:
        print(f"   Telnyx call failed: {e}")
        return JSONResponse({"error": f"Telnyx API error: {str(e)}"}, 500)

    call_control_id = result["call_control_id"]
    calls[call_control_id] = {
        "scenario": scenario,
        "bridge": None,
        "timeout_task": None,
        "started_at": datetime.utcnow().isoformat(),
    }

    print(f"   Call control ID: {call_control_id[:20]}...")
    return {"status": "calling", "call_control_id": call_control_id, "scenario": scenario["name"]}


@app.get("/scenarios")
async def list_scenarios():
    return [{"index": i, "id": s["id"], "name": s["name"]} for i, s in enumerate(SCENARIOS)]


@app.get("/")
async def health():
    return {"status": "ok", "scenarios": len(SCENARIOS), "active_calls": len(calls)}


# Telnyx webhook (HTTP)
@app.post("/webhook")
async def webhook(request: Request):
    body = await request.json()
    data = body.get("data", {})
    event_type = data.get("event_type", "")
    payload = data.get("payload", {})
    call_control_id = payload.get("call_control_id", "")

    print(f"[EVENT] {event_type}")

    if event_type == "call.initiated":
        print(f"  Call initiated to {payload.get('to')}")

    elif event_type == "call.answered":
        await _on_answered(call_control_id, payload)

    elif event_type == "call.hangup":
        await _on_hangup(call_control_id, payload)

    elif event_type == "streaming.started":
        print(f"  Media streaming started")

    elif event_type == "streaming.stopped":
        print(f"  Media streaming stopped")

    return JSONResponse({"status": "ok"})


async def _on_answered(call_control_id: str, payload: dict):
    """Call answered, start media streaming."""
    state = calls.get(call_control_id)
    if not state:
        print(f"  No state for call {call_control_id[:16]}, skipping")
        return

    print(f"  Call answered; starting media stream to {STREAM_URL}")
    await telnyx_api.stream_start(call_control_id, STREAM_URL)

    # Set a max-duration timer so calls don't run forever
    state["timeout_task"] = asyncio.create_task(
        _call_timeout(call_control_id, MAX_CALL_DURATION)
    )


async def _on_hangup(call_control_id: str, payload: dict):
    """Call ended; save transcript, clean up."""
    state = calls.pop(call_control_id, None)
    if not state:
        return

    if state.get("timeout_task"):
        state["timeout_task"].cancel()

    bridge: RealtimeBridge | None = state.get("bridge")
    if bridge:
        _save_transcript(bridge)
        await bridge.close()

    print(f"  Call ended and cleaned up")


async def _call_timeout(call_control_id: str, seconds: int):
    """Auto-hangup after max duration."""
    await asyncio.sleep(seconds)
    print(f"  Max duration ({seconds}s) reached — hanging up")
    try:
        await telnyx_api.hangup(call_control_id)
    except Exception as e:
        print(f"  Hangup failed: {e}")


# Telnyx media WebSocket
@app.websocket("/media-stream")
async def media_stream(ws: WebSocket):
    """Receives Telnyx audio stream and bridges it to OpenAI Realtime."""
    await ws.accept()
    print("[WS] Telnyx media stream connected")

    bridge: RealtimeBridge | None = None

    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            event = data.get("event")

            if event == "connected":
                print("[WS] Stream connected event received")

            elif event == "start":
                start_info = data.get("start", {})
                call_control_id = start_info.get("call_control_id", "")
                stream_id = start_info.get("stream_id", "")

                print(f"[WS] Stream started — call={call_control_id[:16]}... stream={stream_id[:16]}...")

                state = calls.get(call_control_id)
                if not state:
                    # Fallback: try to find by partial match (Telnyx sometimes sends a slightly different ID format)
                    for cid, s in calls.items():
                        if cid.startswith(call_control_id[:16]) or call_control_id.startswith(cid[:16]):
                            state = s
                            call_control_id = cid
                            break

                if state:
                    bridge = RealtimeBridge(state["scenario"], ws, call_control_id)
                    state["bridge"] = bridge
                    await bridge.connect()
                else:
                    print(f"[WS] No matching call state found!")

            elif event == "media" and bridge:
                # Forward audio from agent → OpenAI Realtime
                payload = data.get("media", {}).get("payload", "")
                if payload:
                    await bridge.forward_audio_to_openai(payload)

            elif event == "stop":
                print("[WS] Stream stop event")
                break

    except WebSocketDisconnect:
        print("[WS] Telnyx media stream disconnected")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        if bridge:
            await bridge.close()
        print("[WS] Media stream handler exited")


# Transcript saving
def _save_transcript(bridge: RealtimeBridge):
    scenario = bridge.scenario
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{scenario['id']}_{timestamp}.txt"
    filepath = os.path.join(TRANSCRIPTS_DIR, filename)

    lines = [
        f"Scenario: {scenario['name']}",
        f"Started:  {bridge.started_at}",
        f"Turns:    {len(bridge.transcript)}"
    ]
    for entry in bridge.transcript:
        role = "PATIENT" if entry["role"] == "bot" else "AGENT"
        lines.append(f"\n[{role}]: {entry['text']}")

    with open(filepath, "w") as f:
        f.write("\n".join(lines))

    print(f"  Transcript saved: {filepath}")
