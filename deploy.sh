#!/bin/bash
set -euo pipefail
cd /Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard
git add data.js data.json
git commit -m "update: $(TZ=Asia/Tokyo date '+%Y-%m-%d %H:%M:%S JST')" --allow-empty
git push origin main
