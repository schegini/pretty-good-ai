import os
from dotenv import load_dotenv

# Load .env from project root (one level up from src/)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

TELNYX_API_KEY = os.getenv("TELNYX_API_KEY")
TELNYX_CONNECTION_ID = os.getenv("TELNYX_CONNECTION_ID")
TELNYX_FROM_NUMBER = os.getenv("TELNYX_FROM_NUMBER")
TARGET_NUMBER = os.getenv("TARGET_NUMBER", "+18054398008")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_BASE_URL")  # e.g. https://abc.ngrok-free.app

# Derived URLs
WEBHOOK_URL = f"{WEBHOOK_BASE_URL}/webhook"
# Replace https:// with wss:// for WebSocket URL
STREAM_URL = f"{WEBHOOK_BASE_URL.replace('https://', 'wss://').replace('http://', 'ws://')}/media-stream"

# OpenAI Realtime model
# GA model: "gpt-realtime" | Beta/preview: "gpt-4o-realtime-preview"
REALTIME_MODEL = "gpt-4o-realtime-preview"

# Call settings
MAX_CALL_DURATION = 240  # seconds (4 min)
