# Voice Bot: AI Patient Simulator

Automated voice bot that calls the Pivot Point Orthopedics AI receptionist, simulates realistic patient scenarios, and identifies bugs in the agent's responses.

Loom walkthrough: https://www.loom.com/share/0c994429980741b0ae3e603ec8562043

## Architecture

See [docs/architecture.md](docs/architecture.md) for a detailed explanation.

In short: the system bridges Telnyx Call Control with OpenAI's Realtime API over WebSocket. Telnyx streams G.711 u-law audio from the call, the server pipes it directly to the Realtime API (same codec, zero transcoding), and the model generates spoken patient responses that stream back onto the call. Transcripts are captured automatically via built-in Whisper transcription.

## Project Structure

```
.
├── src/
│   ├── server.py          # FastAPI: webhooks, WebSocket media, call triggers
│   ├── bridge.py          # OpenAI Realtime API <-> Telnyx audio bridge
│   ├── telnyx_api.py      # Telnyx Call Control REST wrapper
│   ├── scenarios.py       # 12 patient test scenarios
│   └── config.py          # Environment config loader
├── transcripts/           # Auto-saved call transcripts
├── docs/
│   ├── architecture.md    # System design and key decisions
│   └── bug_report.md      # Bugs found in the AI agent
├── make_call.py           # CLI to trigger calls
├── requirements.txt
├── .env.example
└── .gitignore
```

## Setup

### Prerequisites

- Python 3.10+
- Telnyx account with a purchased phone number assigned to a Call Control connection
- OpenAI API key with Realtime API access
- ngrok installed and authenticated

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
```

Fill in all values. Phone numbers must be in E.164 format with no dashes or spaces (e.g. `+13412226273`).

| Variable | Description |
|----------|-------------|
| TELNYX_API_KEY | Telnyx v2 API key (starts with KEY...) |
| TELNYX_CONNECTION_ID | ID of your Call Control connection |
| TELNYX_FROM_NUMBER | Your Telnyx phone number (E.164) |
| TARGET_NUMBER | Test line to call (default: +18054398008) |
| OPENAI_API_KEY | OpenAI API key with Realtime access |
| WEBHOOK_BASE_URL | Your ngrok public URL, no trailing slash |

### 3. Telnyx configuration

In Telnyx Mission Control:

- Your phone number must be assigned to your Call Control connection.
- If your account is new (trust level D60), add +18054398008 under Numbers > Verified Numbers.

### 4. Start ngrok (Terminal 1)

```bash
ngrok http 80
```

Copy the forwarding URL and set it as WEBHOOK_BASE_URL in your .env file.

### 5. Start the server (Terminal 2)

```bash
cd src
uvicorn server:app --host 0.0.0.0 --port 80
```

The server prints a config summary on startup. Check for warnings about missing variables.

### 6. Make calls (Terminal 3)

```bash
# List scenarios
python make_call.py

# Run one scenario
python make_call.py 0

# Run all 12 scenarios
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
| 4 | General Questions | Hours, insurance, new patients |
| 5 | Sunday Appointment Request | Booking on a closed day |
| 6 | Vague, Rambling Patient | Unclear/confused patient |
| 7 | Mid-Call Topic Switch | Abrupt topic changes |
| 8 | Urgent Injury | Possible fracture, same-day care |
| 9 | Contradictory Information | Inconsistent patient details |
| 10 | Cancel Then Immediately Rebook | State management after cancellation |
| 11 | Wrong Type of Doctor | Dental cleaning at an orthopedic clinic |

## Bug Report

See [docs/bug_report.md](docs/bug_report.md).

## Troubleshooting

**No webhook events in server logs:** ngrok is not forwarding to your server. Verify ngrok is running on the correct port and check the ngrok terminal for incoming requests.

**422 from Telnyx:** Phone numbers are not in E.164 format. Remove all dashes and spaces.

**403 from Telnyx:** Wrong API key, phone number not assigned to the connection, or account trust level blocks calls to unverified numbers.

**Call connects but no bot audio:** Check server logs for "Realtime session created". If missing, verify your OpenAI key has Realtime API access.

**ngrok returns HTML instead of forwarding:** Use `ngrok http 80` from the CLI rather than a cloud endpoint to avoid the free tier browser interstitial.
