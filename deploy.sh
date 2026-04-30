#!/bin/bash
set -euo pipefail
cd /Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard

VERSION="v$(TZ=Asia/Tokyo date '+%Y%m%d.%H%M')"
JST_NOW="$(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST')"

# Stamp build version into index.html (BSD sed compatible)
sed -i.bak -E "s|(<span class=\"live-version\" id=\"liveVersion\">)[^<]*(</span>)|\1${VERSION}\2|" index.html
rm -f index.html.bak

git add data.js data.json index.html
git commit -m "update: ${JST_NOW} [${VERSION}]" --allow-empty
git push origin main
