#!/usr/bin/env bash
# One command to run the website AND keep it up to date with GitHub:
#
#     bash scripts/live.sh
#
# 1. scripts/auto-pull.sh runs in the background and pulls new commits from GitHub.
# 2. `docker compose up --build --watch` runs the website and applies every changed file:
#      - Python code      -> copied into the containers, which restart (a few seconds)
#      - React code       -> the frontend image is rebuilt (about 30 seconds)
#      - requirements.txt -> the backend image is rebuilt
# Press Ctrl+C to stop everything.
cd "$(dirname "$0")/.." || exit 1

[ -f .env ] || cp .env.example .env

bash scripts/auto-pull.sh "${1:-15}" &
PULL_PID=$!
trap 'kill "$PULL_PID" 2>/dev/null' EXIT INT TERM

docker compose up --build --watch
