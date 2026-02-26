"""Bridge between Telnyx media stream and OpenAI Realtime API.

Handles:
- Forwarding inbound audio (agent) → OpenAI Realtime input
- Forwarding Realtime output audio → Telnyx outbound (patient voice)
- Capturing transcripts from both sides

Uses the beta/preview Realtime API format (gpt-4o-realtime-preview).
To switch to GA (gpt-realtime), remove the OpenAI-Beta header and
restructure session.update to use the nested audio config format.
"""

import asyncio
import json
from datetime import datetime

import websockets
from config import OPENAI_API_KEY, REALTIME_MODEL

REALTIME_URL = f"wss://api.openai.com/v1/realtime?model={REALTIME_MODEL}"

PATIENT_WRAPPER = (
    "You are role-playing as a patient calling an orthopedic clinic (Pivot Point "
    "Orthopedics) on the phone. You are speaking with the clinic's AI receptionist.\n\n"
    "RULES:\n"
    "- Stay in character at all times as the patient described below\n"
    "- Respond naturally and conversationally, like a real phone call\n"
    "- Keep responses to 1-3 sentences — don't monologue\n"
    "- Do not narrate actions or use stage directions\n"
    "- If the receptionist asks for info your character has, provide it naturally\n"
    "- When the conversation reaches a natural end, say goodbye politely\n\n"
    "PATIENT PERSONA:\n{scenario_prompt}\n\n"
    "Start the conversation with something like: \"{opening_line}\""
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
        self._audio_chunks_received = 0  # from Telnyx (agent audio)
        self._audio_chunks_sent = 0      # to Telnyx (bot audio)

    async def connect(self):
        """Open WebSocket to OpenAI Realtime API and configure the session."""
        headers = {
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "OpenAI-Beta": "realtime=v1",
        }

        try:
            self.openai_ws = await websockets.connect(
                REALTIME_URL,
                additional_headers=headers,
                max_size=None,
            )
        except Exception as e:
            print(f"  Failed to connect to OpenAI Realtime: {e}")
            return

        self._connected = True

        # Wait for session.created before sending session.update
        raw = await self.openai_ws.recv()
        created = json.loads(raw)
        if created.get("type") == "session.created":
            print(f"  Realtime session created: {created['session'].get('id', 'n/a')}")
        else:
            print(f"  Unexpected first event: {created.get('type')}")

        # Configure session for telephony audio (g711_ulaw)
        await self._send({
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
                "temperature": 0.8,
            },
        })

        # Start background listener for OpenAI → Telnyx direction
        self._listener_task = asyncio.create_task(self._listen_openai())

        # Kick off the conversation, inject the opening line so the bot speaks first.
        # We add it as a user message (pretending the agent greeted us) and then
        # create a response so the model speaks the opening line aloud.
        await self._send({
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            "The receptionist just answered the phone and greeted you. "
                            "Introduce yourself and state your reason for calling."
                        ),
                    }
                ],
            },
        })
        await self._send({"type": "response.create"})

        print(f"  Realtime bridge ready — Scenario: {self.scenario['name']}")

    # Telnyx → OpenAI (inbound agent audio)
    async def forward_audio_to_openai(self, audio_base64: str):
        """Send a chunk of inbound audio (agent's voice) to OpenAI."""
        if self._connected and self.openai_ws:
            self._audio_chunks_received += 1
            if self._audio_chunks_received in (1, 10, 50, 100, 500):
                print(f"  Audio chunks received from Telnyx: {self._audio_chunks_received}")
            await self._send({
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

                # Audio output: patient voice → play on the call
                if etype == "response.audio.delta":
                    audio = event.get("delta", "")
                    if audio:
                        await self._send_telnyx_audio(audio)

                # Transcript: patient (bot) finished a response
                elif etype == "response.audio_transcript.done":
                    text = event.get("transcript", "").strip()
                    if text:
                        self.transcript.append({"role": "bot", "text": text})
                        print(f"  PATIENT: {text}")

                # Transcript: agent (inbound) utterance transcribed
                elif etype == "conversation.item.input_audio_transcription.completed":
                    text = event.get("transcript", "").strip()
                    if text:
                        self.transcript.append({"role": "agent", "text": text})
                        print(f"  AGENT:   {text}")

                # Session confirmed updated
                elif etype == "session.updated":
                    print(f"  Session config applied")

                # Errors
                elif etype == "error":
                    err = event.get("error", {})
                    print(f"  Realtime error: {err.get('message', err)}")

                # Response lifecycle (useful for debugging)
                elif etype == "response.done":
                    pass  # response complete, transcript already captured above

                elif etype == "response.created":
                    print(f"  OpenAI: Response generation started")

                elif etype in (
                    "response.output_item.added",
                    "response.content_part.added",
                    "response.audio.done",
                    "response.content_part.done",
                    "response.output_item.done",
                    "input_audio_buffer.speech_started",
                    "input_audio_buffer.committed",
                ):
                    # Known events we can safely ignore in logs
                    pass

                elif etype == "input_audio_buffer.speech_started":
                    print(f"  OpenAI: Speech detected in input")

                elif etype == "input_audio_buffer.speech_stopped":
                    print(f"  OpenAI: Speech ended in input")

                else:
                    # Log any unhandled events for debugging
                    print(f"  OpenAI event: {etype}")

        except websockets.exceptions.ConnectionClosed as e:
            print(f"  Realtime WebSocket closed: {e}")
        except Exception as e:
            print(f"  Realtime listener error: {type(e).__name__}: {e}")

    # Send audio back to Telnyx
    async def _send_telnyx_audio(self, audio_base64: str):
        """Send audio payload back to Telnyx media stream."""
        try:
            self._audio_chunks_sent += 1
            if self._audio_chunks_sent in (1, 10, 50, 100, 500):
                print(f"  Audio chunks sent to Telnyx: {self._audio_chunks_sent}")
            await self.telnyx_ws.send_text(json.dumps({
                "event": "media",
                "media": {"payload": audio_base64},
            }))
        except Exception as e:
            print(f"  Failed to send audio to Telnyx: {e}")

    # Helpers
    async def _send(self, msg: dict):
        """Send a JSON message to OpenAI."""
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
        print(f"  Bridge closed ({len(self.transcript)} transcript entries)")

