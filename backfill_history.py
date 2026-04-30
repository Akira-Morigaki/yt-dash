#!/usr/bin/env python3
"""One-shot backfill: fill subscriber history with one point per day for the last
180 days. For each day we walk backwards from the current count using
Analytics API daily subscribersGained/Lost. Days with no API row are treated
as zero growth (= flat line, same as previous day)."""
import json
import os
import subprocess
import sys
import urllib.request
from datetime import datetime, timezone, timedelta

CHANNEL_ID     = "UCXDnQrp8Sao7ZmpL9Ws-SLA"
BASE_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
GET_TOKEN_PY   = "/Users/akira.ai/.claude/scheduled-tasks/youtube-oauth/get_token.py"
HISTORY_JSON   = "/Users/akira.ai/.claude/scheduled-tasks/youtube-subscriber-tracker/subscriber-history.json"
DASH_DIR       = "/Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard"
DATA_JSON      = os.path.join(DASH_DIR, "data.json")
DATA_JS        = os.path.join(DASH_DIR, "data.js")
DAYS           = 365


def get_token():
    r = subprocess.run(["python3", GET_TOKEN_PY], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def main():
    jst   = timezone(timedelta(hours=9))
    now   = datetime.now(jst)
    today = now.date()
    start = (today - timedelta(days=DAYS - 1)).isoformat()
    end   = today.isoformat()

    token = get_token()
    url = (
        f"{BASE_ANALYTICS}?ids=channel==MINE"
        f"&startDate={start}&endDate={end}"
        f"&metrics=subscribersGained,subscribersLost"
        f"&dimensions=day&sort=day"
    )
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        body = json.loads(resp.read())

    # rows: [["YYYY-MM-DD", gained, lost], ...]
    deltas = {row[0]: int(row[1]) - int(row[2]) for row in body.get("rows", [])}

    with open(HISTORY_JSON, encoding="utf-8") as f:
        sub_history = json.load(f)
    current = int(sub_history["last_count"])

    # Walk backward: today carries `current`. Yesterday = today - delta(today).
    history = []
    val = current
    d   = today
    for _ in range(DAYS):
        history.append({
            "t": datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=jst).isoformat(),
            "n": val,
        })
        delta = deltas.get(d.isoformat(), 0)
        val   = val - delta
        d     = d - timedelta(days=1)

    history.reverse()

    with open(DATA_JSON, encoding="utf-8") as f:
        data = json.load(f)
    data["history"] = history
    data["subscribers"]["updated_at"] = now.isoformat()

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    with open(DATA_JSON, "w", encoding="utf-8") as f:
        f.write(json_str + "\n")
    with open(DATA_JS, "w", encoding="utf-8") as f:
        f.write(f"window.__YT_DATA__ = {json_str};\n")

    print(
        f"Backfilled {len(history)} days "
        f"({history[0]['t'][:10]} -> {history[-1]['t'][:10]}, "
        f"{history[0]['n']} -> {history[-1]['n']})",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
