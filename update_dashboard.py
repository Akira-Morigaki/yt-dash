#!/usr/bin/env python3
"""
Update YouTube dashboard data files (data.js and data.json).
Self-contained: fetches subscriber count + latest 3 long-form videos via Data API.
Called from youtube-subscriber-tracker SKILL.md after Discord send.
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta

CHANNEL_ID    = "UCXDnQrp8Sao7ZmpL9Ws-SLA"
BASE_DATA     = "https://www.googleapis.com/youtube/v3"
BASE_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
GET_TOKEN_PY  = "/Users/akira.ai/.claude/scheduled-tasks/youtube-oauth/get_token.py"
DASH_DIR      = "/Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard"
HISTORY_JSON  = "/Users/akira.ai/.claude/scheduled-tasks/youtube-subscriber-tracker/subscriber-history.json"
VIDEO_VIEWS_HISTORY = "/Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard-updater/video-views-history.json"
DATA_JSON     = os.path.join(DASH_DIR, "data.json")
DATA_JS       = os.path.join(DASH_DIR, "data.js")


def get_token():
    r = subprocess.run(["python3", GET_TOKEN_PY], capture_output=True, text=True, check=True)
    return r.stdout.strip()


def api_get(url, token):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        return json.loads(resp.read())


def parse_duration(iso):
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso or "")
    if not m:
        return 0
    return int(m.group(1) or 0) * 3600 + int(m.group(2) or 0) * 60 + int(m.group(3) or 0)


def is_short(item):
    """True if the video is a YouTube Short (duration ≤ 180s AND #shorts tag)."""
    duration = parse_duration(item["contentDetails"]["duration"])
    if duration > 180:
        return False
    snippet = item["snippet"]
    text = (snippet.get("title", "") + " " + snippet.get("description", "")).lower()
    return "#short" in text or duration < 60


def atomic_write(path, content):
    dir_ = os.path.dirname(path)
    with tempfile.NamedTemporaryFile("w", dir=dir_, delete=False, suffix=".tmp", encoding="utf-8") as f:
        f.write(content)
        tmp = f.name
    os.replace(tmp, path)


def main():
    jst = timezone(timedelta(hours=9))
    now = datetime.now(jst)
    token = get_token()

    # Subscriber count — read from subscriber-tracker history (single source of truth)
    with open(HISTORY_JSON, encoding="utf-8") as f:
        sub_history = json.load(f)
    sub_count = int(sub_history["last_count"])

    # Latest non-Short videos — fetch up to 30 candidates to find 3 long-form
    search = api_get(
        f"{BASE_DATA}/search?part=snippet&channelId={CHANNEL_ID}"
        f"&type=video&order=date&maxResults=30",
        token,
    )
    video_ids = [item["id"]["videoId"] for item in search.get("items", [])]

    if video_ids:
        vids = api_get(
            f"{BASE_DATA}/videos?part=snippet,contentDetails,statistics&id={','.join(video_ids)}",
            token,
        )
        # Preserve publish-date order from search results
        order = {vid_id: i for i, vid_id in enumerate(video_ids)}
        items = sorted(vids.get("items", []), key=lambda x: order.get(x["id"], 999))
    else:
        items = []

    # Load per-video view snapshot history (for 24h delta calculation)
    snapshots = {}
    if os.path.exists(VIDEO_VIEWS_HISTORY):
        try:
            with open(VIDEO_VIEWS_HISTORY, encoding="utf-8") as f:
                snapshots = json.load(f)
        except Exception:
            snapshots = {}

    videos = []
    new_snapshots = {}
    for item in items:
        if is_short(item):
            continue  # Skip Shorts (duration ≤ 180s かつ #shorts タグ、または60秒未満)
        pub = datetime.fromisoformat(item["snippet"]["publishedAt"].replace("Z", "+00:00"))
        vid_id = item["id"]
        current_views = int(item["statistics"].get("viewCount", 0))

        # 24h delta — find snapshot closest to 24h ago, but only if ≥23h old
        prev_snaps = snapshots.get(vid_id, [])
        target = now - timedelta(hours=24)
        cutoff = now - timedelta(hours=23)
        eligible = [s for s in prev_snaps if datetime.fromisoformat(s["t"]) <= cutoff]
        if eligible:
            best = min(eligible, key=lambda s: abs((datetime.fromisoformat(s["t"]) - target).total_seconds()))
            views_24h = current_views - int(best["views"])
        else:
            views_24h = None

        # Append current snapshot, prune entries older than 25h
        prune_cutoff = now - timedelta(hours=25)
        kept = [s for s in prev_snaps if datetime.fromisoformat(s["t"]) > prune_cutoff]
        kept.append({"t": now.isoformat(), "views": current_views})
        new_snapshots[vid_id] = kept

        videos.append({
            "id": vid_id,
            "title": item["snippet"]["title"],
            "views": current_views,
            "views_24h": views_24h,
            "published_at": pub.astimezone(jst).isoformat(),
            "thumbnail": f"https://i.ytimg.com/vi/{vid_id}/maxresdefault.jpg",
        })
        if len(videos) >= 3:
            break

    # Save updated snapshots
    os.makedirs(os.path.dirname(VIDEO_VIEWS_HISTORY), exist_ok=True)
    atomic_write(VIDEO_VIEWS_HISTORY, json.dumps(new_snapshots, ensure_ascii=False, indent=2) + "\n")

    # Read previous data for delta and history
    prev_count = sub_count
    history = []
    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, encoding="utf-8") as f:
                old = json.load(f)
            prev_count = old.get("subscribers", {}).get("current", sub_count)
            history = old.get("history", [])
        except Exception:
            pass

    # Append current reading to history (max 30 points)
    history.append({"t": now.isoformat(), "n": sub_count})
    history = history[-30:]

    data = {
        "subscribers": {
            "current": sub_count,
            "previous": prev_count,
            "updated_at": now.isoformat(),
        },
        "history": history,
        "videos": videos,
    }

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write(DATA_JSON, json_str + "\n")
    atomic_write(DATA_JS, f"window.__YT_DATA__ = {json_str};\n")

    print(f"Dashboard updated: {sub_count:,} subscribers, {len(videos)} videos", file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Dashboard update error: {e}", file=sys.stderr)
        sys.exit(1)
