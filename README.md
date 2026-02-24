# Voice Bot: AI Patient Simulator

An automated voice bot that calls a medical office's AI receptionist, simulates realistic patient scenarios, and identifies bugs in the agent's responses. Built for the Pretty Good AI engineering assessment.

## Architecture

The system bridges **Telnyx Call Control** (telephony) with **OpenAI's Realtime API** (native speech-to-speech model) to create low-latency, natural-sounding voice conversations.

When a call is placed, Telnyx connects it and streams raw audio (G.711 μ-law, 8kHz) to our FastAPI server via WebSocket. The server opens a parallel WebSocket to OpenAI's Realtime API, configured with the same `g711_ulaw` format — so audio passes through with **zero format conversion**. The Realtime model hears the agent's voice, processes it natively as audio (not text), and generates a spoken patient response that streams back through Telnyx onto the call. OpenAI's server-side VAD handles turn detection automatically.

Key design choices: **Realtime API over text-based STT→LLM→TTS** for dramatically lower latency and more natural conversation flow (the model reasons about tone/pacing, not just words). **g711_ulaw end-to-end** to avoid audio transcoding overhead. **Telnyx over Twilio** for lower per-minute costs. Transcripts come free from the Realtime API's built-in Whisper transcription of both sides.

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure environment
```bash
cp .env.example .env
# Fill in: TELNYX_API_KEY, TELNYX_CONNECTION_ID, TELNYX_FROM_NUMBER,
#          OPENAI_API_KEY, WEBHOOK_BASE_URL
```

### 3. Start ngrok (separate terminal)
```bash
ngrok http 8000
```
Update `WEBHOOK_BASE_URL` in `.env` with your ngrok URL.

### 4. Start the server
```bash
uvicorn server:app --host 0.0.0.0 --port 8000
```

### 5. Make calls (separate terminal)
```bash
# List scenarios
python make_call.py

# Run a single scenario
python make_call.py 0

# Run all 10 scenarios
python make_call.py all

# Custom delay between calls (default 30s)
python make_call.py all --delay 45
```

## Scenarios

| # | ID | Name | What It Tests |
|---|-----|------|---------------|
| 0 | simple_scheduling | Simple Scheduling | Basic appointment booking |
| 1 | reschedule | Reschedule | Modifying an existing appointment |
| 2 | medication_refill | Medication Refill | Refill request handling |
| 3 | office_hours_question | Office Hours Q&A | Multi-question informational call |
| 4 | weekend_edge_case | Weekend Edge Case | Booking on a closed day (Sunday) |
| 5 | cancel_appointment | Cancel Appointment | Cancellation flow |
| 6 | vague_symptoms | Vague/Unclear Request | Rambling, confused patient |
| 7 | interruption_test | Interruption Test | Topic switching mid-call |
| 8 | after_hours_call | Emergency Question | Urgent dental issue |
| 9 | multiple_requests | Multiple Requests | Several needs in one call |

## Project Structure

```
├── server.py          # FastAPI — webhooks, WebSocket media, call triggers
├── bridge.py          # OpenAI Realtime API ↔ Telnyx audio bridge
├── telnyx_api.py      # Telnyx Call Control REST wrapper
├── scenarios.py       # 10 patient test scenarios
├── config.py          # Environment config
├── make_call.py       # CLI to trigger calls
├── transcripts/       # Auto-saved call transcripts
├── requirements.txt
└── .env.example
```

## How It Works

```
┌─────────────┐    audio (μ-law)    ┌──────────────┐    audio (μ-law)    ┌─────────────────┐
│  Telnyx     │ ◄────────────────►  │  FastAPI     │ ◄────────────────►  │ OpenAI Realtime │
│ (phone call)│    WebSocket        │  Server      │    WebSocket        │  API (patient)  │
└─────────────┘                     └──────────────┘                     └─────────────────┘
                                          │
                                          ▼
                                    transcripts/
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `TELNYX_API_KEY` | Telnyx API v2 key |
| `TELNYX_CONNECTION_ID` | Telnyx connection/app ID |
| `TELNYX_FROM_NUMBER` | Your Telnyx phone number (E.164) |
| `TARGET_NUMBER` | Test line to call  |
| `OPENAI_API_KEY` | OpenAI API key (needs Realtime API access) |
| `WEBHOOK_BASE_URL` | Public ngrok URL |
