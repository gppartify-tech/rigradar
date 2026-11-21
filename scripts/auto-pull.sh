#!/usr/bin/env bash
# Keeps this folder in sync with GitHub: every N seconds (default 15), if the `main` branch
# has new commits, pull them. Used together with `docker compose up --watch`, which then
# applies the changed files to the running website (see scripts/live.sh).
#
#     bash scripts/auto-pull.sh        # check every 15 s
#     bash scripts/auto-pull.sh 60     # check every minute
set -u
INTERVAL="${1:-15}"
cd "$(dirname "$0")/.." || exit 1

echo "Watching GitHub for new commits on main every ${INTERVAL}s (Ctrl+C to stop)"
while true; do
  if git fetch -q origin main 2>/dev/null; then
    if [ "$(git rev-parse HEAD)" != "$(git rev-parse origin/main)" ]; then
      echo "$(date +%T) new changes on GitHub - pulling..."
      if git pull --ff-only -q origin main; then
        echo "$(date +%T) updated to: $(git log -1 --format='%h %s')"
      else
        echo "$(date +%T) pull failed - you probably edited files in this folder. Run 'git status'."
      fi
    fi
  else
    echo "$(date +%T) could not reach GitHub (offline?) - will retry"
  fi
  sleep "$INTERVAL"
done
