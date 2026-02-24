"""Bridge between Telnyx media stream and OpenAI Realtime API.

Handles:
- Forwarding inbound audio (agent) → OpenAI Realtime input
- Forwarding Realtime output audio → Telnyx outbound (patient voice)
- Capturing transcripts from both sides
"""

import asyncio
import json
from datetime import datetime

import websockets
from config import OPENAI_API_KEY, REALTIME_MODEL

REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

PATIENT_WRAPPER = (
    "You are role-playing as a patient calling a medical/dental office phone line. "
    "You are speaking on the phone with the office's AI receptionist.\n\n"
    "RULES:\n"
    "- Stay in character at all times\n"
    "- Respond naturally and conversationally, like a real phone call\n"
    "- Keep responses to 1-3 sentences — don't monologue\n"
    "- Do not narrate actions or use stage directions\n"
    "- If the receptionist asks for info you have, provide it naturally\n"
    "- When the conversation reaches a natural end, say goodbye and wait for them to end the call\n\n"
    "PATIENT PERSONA:\n{scenario_prompt}\n\n"
    "When the receptionist greets you, respond with something like: \"{opening_line}\""
)


class RealtimeBridge:
    """Manages one OpenAI Realtime session bridged to a Telnyx media stream."""

    def __init__(self, scenario: dict, telnyx_ws, call_control_id: str):
        self.scenario = scenario
        self.telnyx_ws = telnyx_ws  # FastAPI WebSocket
        self.call_control_id = call_control_id
        self.openai_ws = None
        self.transcript: list[dict] = []
        self.started_at = datetime.utcnow().isoformat()
        self._listener_task = None
        self._connected = False

    async def connect(self):
        """Open WebSocket to OpenAI Realtime API and configure the session."""
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        }
        self.openai_ws = await websockets.connect(
            REALTIME_URL,
            additional_headers=headers,
            max_size=None,  # no limit on message size for audio chunks
        )
        self._connected = True

        # Configure session — use g711_ulaw to match Telnyx audio format directly
        await self._send_openai({
            "type": "session.update",
            "session": {
                "modalities": ["text", "audio"],
                "instructions": PATIENT_WRAPPER.format(
                    scenario_prompt=self.scenario["system_prompt"],
                    opening_line=self.scenario["opening_line"],
                ),
                "voice": "alloy",
                "input_audio_format": "g711_ulaw",
                "output_audio_format": "g711_ulaw",
                "input_audio_transcription": {
                    "model": "whisper-1",
                },
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 700,
                },
            },
        })

        # Start background listener for OpenAI → Telnyx direction
        self._listener_task = asyncio.create_task(self._listen_openai())

        print(f"  ✓ Realtime bridge connected for {self.scenario['name']}")

    # Telnyx → OpenAI (inbound agent audio)
    async def forward_audio_to_openai(self, audio_base64: str):
        """Send a chunk of inbound audio (agent's voice) to OpenAI."""
        if self._connected and self.openai_ws:
            await self._send_openai({
                "type": "input_audio_buffer.append",
                "audio": audio_base64,
            })

    # OpenAI → Telnyx (patient audio + transcript capture)
    async def _listen_openai(self):
        """Background task: read events from OpenAI and forward audio to Telnyx."""
        try:
            async for raw in self.openai_ws:
                event = json.loads(raw)
                etype = event.get("type", "")

                # Audio output: patient speaking → play on call
                if etype == "response.audio.delta":
                    audio = event.get("delta", "")
                    if audio:
                        await self.telnyx_ws.send_text(json.dumps({
                            "event": "media",
                            "media": {"payload": audio},
                        }))

                # Transcript: patient finished a response 
                elif etype == "response.audio_transcript.done":
                    text = event.get("transcript", "").strip()
                    if text:
                        self.transcript.append({"role": "bot", "text": text})
                        print(f"  PATIENT: {text}")

                # Transcript: agent utterance transcribed
                elif etype == "conversation.item.input_audio_transcription.completed":
                    text = event.get("transcript", "").strip()
                    if text:
                        self.transcript.append({"role": "agent", "text": text})
                        print(f"  AGENT:   {text}")

                # Session lifecycle
                elif etype == "session.created":
                    print(f"  ✓ Realtime session created")

                elif etype == "session.updated":
                    print(f"  ✓ Realtime session configured")

                elif etype == "error":
                    err = event.get("error", {})
                    print(f"  Realtime error: {err.get('message', err)}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"  → Realtime WebSocket closed: {e}")
        except Exception as e:
            print(f"  Realtime listener error: {e}")

    # Helpers
    async def _send_openai(self, msg: dict):
        if self.openai_ws:
            await self.openai_ws.send(json.dumps(msg))

    async def close(self):
        """Clean up the Realtime connection."""
        self._connected = False
        if self._listener_task:
            self._listener_task.cancel()
        if self.openai_ws:
            try:
                await self.openai_ws.close()
            except Exception:
                pass
        print(f"  Realtime bridge closed")