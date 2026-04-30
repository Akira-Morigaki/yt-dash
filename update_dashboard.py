#!/usr/bin/env python3
"""
Update YouTube dashboard data files (data.js and data.json).
Hybrid approach:
- Subscriber count: subscriber-history.json (DOM 真値) + Analytics API 差分累積
- Video stats: Data API (基本情報、累計views) + Analytics API (24h views)
"""
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from datetime import datetime, timezone, timedelta

CHANNEL_ID     = "UCXDnQrp8Sao7ZmpL9Ws-SLA"
BASE_DATA      = "https://www.googleapis.com/youtube/v3"
BASE_ANALYTICS = "https://youtubeanalytics.googleapis.com/v2/reports"
GET_TOKEN_PY   = "/Users/akira.ai/.claude/scheduled-tasks/youtube-oauth/get_token.py"
DASH_DIR       = "/Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard"
HISTORY_JSON   = "/Users/akira.ai/.claude/scheduled-tasks/youtube-subscriber-tracker/subscriber-history.json"
VIDEO_VIEWS_HISTORY = "/Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard-updater/video-views-history.json"
DATA_JSON      = os.path.join(DASH_DIR, "data.json")
DATA_JS        = os.path.join(DASH_DIR, "data.js")


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
    """True if the video is a YouTube Short (≤180s かつ #shorts または60秒未満)."""
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


def get_subscriber_count(now, token):
    """
    Returns (current_count, base_at_iso).

    current_count = base (subscriber-history.json, DOM 真値)
                  + Analytics API 差分累積 since (base_date + 1 day)

    Analytics API は最大72時間遅延あり。DOM 取得日翌日以降の確定差分を加算。
    Analytics 失敗時は base 値をそのまま返す。
    """
    with open(HISTORY_JSON, encoding="utf-8") as f:
        sub_history = json.load(f)
    base_count = int(sub_history["last_count"])
    base_at    = sub_history["last_updated"]
    base_dt    = datetime.fromisoformat(base_at)

    delta = 0
    start_date = (base_dt.date() + timedelta(days=1)).isoformat()
    end_date   = now.date().isoformat()

    if start_date <= end_date:
        try:
            resp = api_get(
                f"{BASE_ANALYTICS}?ids=channel==MINE"
                f"&startDate={start_date}&endDate={end_date}"
                f"&metrics=subscribersGained,subscribersLost",
                token,
            )
            rows = resp.get("rows", [])
            if rows:
                delta = int(rows[0][0]) - int(rows[0][1])
        except Exception as e:
            print(f"Analytics subscriber delta failed: {e}", file=sys.stderr)
            delta = 0

    return base_count + delta, base_at


def get_videos(now, jst, token):
    """
    Latest 3 long-form videos.
    - Data API: 基本情報 + 累計views
    - 24h views: 累計views を毎回スナップショットして 24h 前との差分を計算
      (Analytics API は72h遅延で当日/昨日値が取れないため自前で計算)
    """
    search = api_get(
        f"{BASE_DATA}/search?part=snippet&channelId={CHANNEL_ID}"
        f"&type=video&order=date&maxResults=30",
        token,
    )
    video_ids = [item["id"]["videoId"] for item in search.get("items", [])]
    if not video_ids:
        return []

    vids = api_get(
        f"{BASE_DATA}/videos?part=snippet,contentDetails,statistics&id={','.join(video_ids)}",
        token,
    )
    order = {vid_id: i for i, vid_id in enumerate(video_ids)}
    items = sorted(vids.get("items", []), key=lambda x: order.get(x["id"], 999))
    long_items = [it for it in items if not is_short(it)][:3]
    if not long_items:
        return []

    # Load per-video view snapshot history for 24h delta
    snapshots = {}
    if os.path.exists(VIDEO_VIEWS_HISTORY):
        try:
            with open(VIDEO_VIEWS_HISTORY, encoding="utf-8") as f:
                snapshots = json.load(f)
        except Exception:
            snapshots = {}

    videos = []
    new_snapshots = {}
    target = now - timedelta(hours=24)
    cutoff = now - timedelta(hours=23)
    prune_cutoff = now - timedelta(hours=25)

    for item in long_items:
        vid_id        = item["id"]
        pub           = datetime.fromisoformat(item["snippet"]["publishedAt"].replace("Z", "+00:00"))
        current_views = int(item["statistics"].get("viewCount", 0))

        # 24h delta: pick the snapshot closest to 24h ago, but only ≥23h old
        prev_snaps = snapshots.get(vid_id, [])
        eligible = [s for s in prev_snaps if datetime.fromisoformat(s["t"]) <= cutoff]
        if eligible:
            best = min(eligible, key=lambda s: abs((datetime.fromisoformat(s["t"]) - target).total_seconds()))
            views_24h = current_views - int(best["views"])
        else:
            views_24h = None

        # Prune older than 25h, append current
        kept = [s for s in prev_snaps if datetime.fromisoformat(s["t"]) > prune_cutoff]
        kept.append({"t": now.isoformat(), "views": current_views})
        new_snapshots[vid_id] = kept

        videos.append({
            "id":           vid_id,
            "title":        item["snippet"]["title"],
            "views":        current_views,
            "views_24h":    views_24h,  # None if no eligible snapshot yet
            "published_at": pub.astimezone(jst).isoformat(),
            "thumbnail":    f"https://i.ytimg.com/vi/{vid_id}/maxresdefault.jpg",
        })

    os.makedirs(os.path.dirname(VIDEO_VIEWS_HISTORY), exist_ok=True)
    atomic_write(VIDEO_VIEWS_HISTORY, json.dumps(new_snapshots, ensure_ascii=False, indent=2) + "\n")

    return videos


HISTORY_MAX_DAYS = 365


def update_history(now, sub_count, old_data):
    """One JST-day point in history. Missing days are filled with the previous
    value (= 0 growth). Keeps the last HISTORY_MAX_DAYS entries."""
    history = list((old_data or {}).get("history", []))
    today = now.date()
    jst   = now.tzinfo

    if not history:
        return [{"t": now.isoformat(), "n": sub_count}]

    last_dt = datetime.fromisoformat(history[-1]["t"])
    last_d  = last_dt.date()
    last_n  = history[-1]["n"]

    if last_d == today:
        history[-1] = {"t": now.isoformat(), "n": sub_count}
    else:
        d = last_d + timedelta(days=1)
        while d < today:
            history.append({
                "t": datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=jst).isoformat(),
                "n": last_n,
            })
            d += timedelta(days=1)
        history.append({"t": now.isoformat(), "n": sub_count})

    return history[-HISTORY_MAX_DAYS:]


def main():
    jst   = timezone(timedelta(hours=9))
    now   = datetime.now(jst)
    token = get_token()

    old_data = None
    if os.path.exists(DATA_JSON):
        try:
            with open(DATA_JSON, encoding="utf-8") as f:
                old_data = json.load(f)
        except Exception:
            pass

    current, base_at = get_subscriber_count(now, token)
    previous = (old_data or {}).get("subscribers", {}).get("current", current)
    videos   = get_videos(now, jst, token)
    history  = update_history(now, current, old_data)

    data = {
        "subscribers": {
            "current":    current,
            "previous":   previous,
            "updated_at": now.isoformat(),
            "base_at":    base_at,
        },
        "history": history,
        "videos":  videos,
    }

    json_str = json.dumps(data, ensure_ascii=False, indent=2)
    atomic_write(DATA_JSON, json_str + "\n")
    atomic_write(DATA_JS,  f"window.__YT_DATA__ = {json_str};\n")

    print(f"Dashboard updated: {current:,} subs (base {base_at}), {len(videos)} videos",
          file=sys.stderr)


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"Dashboard update error: {e}", file=sys.stderr)
        sys.exit(1)
