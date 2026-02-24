# Voice Bot: AI Patient Simulator

Automated voice bot that calls the Pivot Point Orthopedics AI receptionist, simulates realistic patient scenarios, and identifies bugs in the agent's responses. Built for the Pretty Good AI engineering assessment.

## Architecture

The system bridges Telnyx Call Control (telephony) with OpenAI's Realtime API (native speech-to-speech model) to create low-latency, natural-sounding voice conversations.

When a call is placed, Telnyx connects it and streams raw audio (G.711 u-law, 8kHz) to a FastAPI server via WebSocket. The server opens a parallel WebSocket to OpenAI's Realtime API, configured with the same g711_ulaw format, so audio passes through with zero format conversion. The Realtime model hears the agent's voice, processes it natively as audio (not text), and generates a spoken patient response that streams back through Telnyx onto the call. OpenAI's server-side VAD handles turn detection automatically.

Key design choices:

- Realtime API over text-based STT/LLM/TTS for dramatically lower latency and more natural conversation flow. The model reasons about tone and pacing, not just words.
- g711_ulaw end-to-end to avoid audio transcoding overhead. Telnyx streams PCMU natively, and the Realtime API accepts it directly.
- RTP bidirectional streaming mode on Telnyx so raw audio (not MP3) can be sent back to the call.
- Telnyx over Twilio because Telnyx runs on a private IP backbone instead of Twilio's public internet infrastructure. This is better and more secure for dealing with healthcare patients who have sensitive information.
- Transcripts are captured from the Realtime API's built-in Whisper transcription of both audio tracks.

## Setup

### Prerequisites

- Python 3.10+
- A Telnyx account with a purchased phone number assigned to a Call Control connection
- An OpenAI API key with Realtime API access
- ngrok installed and authenticated

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in all values. Phone numbers must be in E.164 format with no dashes or spaces (e.g. `+13412226273`, not `+1-341-222-6273`).

| Variable | Description |
|----------|-------------|
| TELNYX_API_KEY | Telnyx v2 API key (starts with KEY...) |
| TELNYX_CONNECTION_ID | ID of your Call Control connection in Mission Control |
| TELNYX_FROM_NUMBER | Your Telnyx phone number in E.164 format |
| TARGET_NUMBER | Test line to call (default: +18054398008) |
| OPENAI_API_KEY | OpenAI API key with Realtime API access |
| WEBHOOK_BASE_URL | Your ngrok public URL, no trailing slash |

### 3. Telnyx configuration

In Telnyx Mission Control:

- Your phone number must be assigned to your Call Control connection.
- If your account is new (trust level D60), you must transition to a 'Paid' plan in order to be able to make outbound calls to unverified numbers. The transition is free and you still have a pay-as-you-go API.

### 4. Start ngrok (Terminal 1)

```bash
ngrok http 80
```

Copy the forwarding URL (e.g. `https://example.ngrok-free.dev`) and set it as `WEBHOOK_BASE_URL` in your `.env` file.

### 5. Start the server (Terminal 2)

```bash
uvicorn server:app --host 0.0.0.0 --port 80
```

The server prints a startup summary showing your config. Check for any warnings about missing variables.

### 6. Make calls (Terminal 3)

```bash
# List available scenarios
python make_call.py

# Run a single scenario
python make_call.py 0

# Run all 12 scenarios sequentially
python make_call.py all

# Custom delay between calls (default 30s)
python make_call.py all --delay 45
```

## Scenarios

All scenarios target Pivot Point Orthopedics, which supports appointments, insurance updates, and prescription refills.

| # | Name | What It Tests |
|---|------|---------------|
| 0 | New Appointment (Knee Pain) | Basic appointment booking |
| 1 | Reschedule Existing Appointment | Modifying an existing appointment |
| 2 | Prescription Refill (Naproxen) | Refill request handling |
| 3 | Update Insurance Information | Insurance update flow |
| 4 | General Questions | Office hours, insurance acceptance, new patients |
| 5 | Sunday Appointment Request | Booking on a closed day |
| 6 | Vague, Rambling Patient | Unclear/confused patient |
| 7 | Mid-Call Topic Switch | Abrupt topic changes |
| 8 | Urgent Injury | Possible fracture, needs same-day care |
| 9 | Contradictory Information | Patient gives inconsistent details |
| 10 | Cancel Then Immediately Rebook | Tests state management after cancellation |
| 11 | Wrong Type of Doctor | Calling orthopedics for a dental cleaning |

## Project Structure

```
server.py          FastAPI server: webhooks, WebSocket media, call triggers
bridge.py          OpenAI Realtime API <-> Telnyx audio bridge
telnyx_api.py      Telnyx Call Control REST wrapper
scenarios.py       12 patient test scenarios
config.py          Environment config
make_call.py       CLI to trigger calls
transcripts/       Auto-saved call transcripts
requirements.txt
.env.example
```

## How It Works

```
Telnyx           FastAPI           OpenAI Realtime
(phone call)     Server            API (patient)
    |                |                   |
    |-- call.answered -->|               |
    |                |-- stream_start -->|
    |<-- WebSocket audio stream -------->|
    |                |                   |
    |  agent audio ->|-> g711_ulaw ----->|
    |                |                   |
    |                |<-- g711_ulaw -----|  (patient response)
    |<- play audio --|                   |
    |                |                   |
    |  (transcripts captured via Whisper)|
    |                |                   |
    |-- call.hangup ->|                  |
    |                |-- save transcript |
```

## Troubleshooting

**No webhook events in server logs:** ngrok is not forwarding to your server. Make sure ngrok is running and pointing to the correct port. Check the ngrok terminal for incoming POST requests.

**422 from Telnyx:** Phone numbers must be in E.164 format with no dashes or spaces.

**403 from Telnyx:** Either the API key is wrong, the phone number is not assigned to the connection, or the account trust level blocks calls to unverified numbers.

**Call connects but no audio from bot:** Check that the OpenAI Realtime WebSocket connected (look for "Realtime session created" in server logs). Verify your OpenAI key has Realtime API access.

**ngrok returning HTML instead of forwarding:** The free tier browser interstitial can intercept webhook POSTs. Use `ngrok http 80` from the command line rather than a cloud endpoint.
