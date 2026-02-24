"""CLI to trigger outbound calls via the running server.

Usage:
    python make_call.py                 — list scenarios
    python make_call.py 0               — run scenario 0
    python make_call.py all             — run all scenarios
    python make_call.py all --delay 45  — run all with 45s between calls
"""

import argparse
import sys
import time

import httpx

SERVER = "http://localhost:80"


def list_scenarios():
    resp = httpx.get(f"{SERVER}/scenarios", timeout=10)
    scenarios = resp.json()
    print("\nAvailable scenarios:")
    for s in scenarios:
        print(f"  {s['index']:>2}: {s['name']}")
    print()


def make_call(index: int):
    print(f"\n Triggering scenario {index}...")
    resp = httpx.post(f"{SERVER}/calls/{index}", timeout=30)
    if resp.status_code == 200:
        data = resp.json()
        print(f"   Call placed — {data['scenario']}")
        print(f"   Call ID: {data['call_control_id'][:24]}...")
    else:
        print(f"   Error: {resp.text}")


def run_all(delay: int = 30):
    resp = httpx.get(f"{SERVER}/scenarios", timeout=10)
    scenarios = resp.json()

    for i, s in enumerate(scenarios):
        print(f"\n{'='*60}")
        print(f"  [{i+1}/{len(scenarios)}] {s['name']}")
        print(f"{'='*60}")
        make_call(s["index"])

        if i < len(scenarios) - 1:
            print(f"\n  Waiting {delay}s before next call...")
            time.sleep(delay)

    print(f"\n All {len(scenarios)} calls placed!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Trigger voice bot calls")
    parser.add_argument("scenario", nargs="?", default=None,
                        help="Scenario index (0-9) or 'all'")
    parser.add_argument("--delay", type=int, default=30,
                        help="Seconds between calls when running all (default: 30)")
    args = parser.parse_args()

    if args.scenario is None:
        list_scenarios()
        print("Usage:")
        print("  python make_call.py <number>         — run one scenario")
        print("  python make_call.py all              — run all scenarios")
        print("  python make_call.py all --delay 45   — custom delay between calls")
        sys.exit(0)

    # Check server is running
    try:
        httpx.get(f"{SERVER}/scenarios", timeout=5)
    except httpx.ConnectError:
        print(" Server not running. Start it first:")
        print("   uvicorn server:app --host 0.0.0.0 --port 8000")
        sys.exit(1)

    if args.scenario == "all":
        run_all(args.delay)
    else:
        try:
            idx = int(args.scenario)
            make_call(idx)
        except ValueError:
            print(f"Unknown argument: {args.scenario}")
            sys.exit(1)
