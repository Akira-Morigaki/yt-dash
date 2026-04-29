#!/bin/bash
set -euo pipefail
cd /Users/akira.ai/.claude/scheduled-tasks/youtube-dashboard
git add data.js data.json
git commit -m "update: $(date -u +%FT%TZ)" --allow-empty
git push origin main
