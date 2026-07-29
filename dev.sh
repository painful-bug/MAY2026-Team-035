#!/usr/bin/env bash

# Start HomeBandhu's Vite frontend and/or FastAPI backend from any directory.
#
#   ./dev.sh                 # start both services
#   ./dev.sh --frontend      # start only Vite
#   ./dev.sh --backend       # start only FastAPI

set -u

readonly ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

run_backend=0
run_frontend=0

usage() {
  cat <<'EOF'
Usage: ./dev.sh [--backend] [--frontend]

Start HomeBandhu development servers.

With no flags, starts both services:
  frontend  http://localhost:5173
  backend   http://127.0.0.1:8000

Options:
  --backend   Start only the FastAPI backend.
  --frontend  Start only the Vite frontend.
  -h, --help  Show this help message.
EOF
}

for argument in "$@"; do
  case "$argument" in
    --backend)
      run_backend=1
      ;;
    --frontend)
      run_frontend=1
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      printf 'Unknown option: %s\n\n' "$argument" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ "$run_backend" -eq 0 && "$run_frontend" -eq 0 ]]; then
  run_backend=1
  run_frontend=1
fi

if [[ "$run_backend" -eq 1 ]] && ! command -v uv >/dev/null 2>&1; then
  printf 'Backend requires uv. Install it from https://docs.astral.sh/uv/\n' >&2
  exit 1
fi

if [[ "$run_frontend" -eq 1 ]] && ! command -v npm >/dev/null 2>&1; then
  printf 'Frontend requires npm (Node.js).\n' >&2
  exit 1
fi

pids=()

start_backend() {
  printf 'Starting backend at http://127.0.0.1:8000 ...\n'
  (
    cd "$ROOT_DIR/backend"
    exec uv run uvicorn app.main:app --reload
  ) &
  pids+=("$!")
}

start_frontend() {
  printf 'Starting frontend at http://localhost:5173 ...\n'
  (
    cd "$ROOT_DIR"
    exec npm run dev
  ) &
  pids+=("$!")
}

cleanup() {
  local exit_code=$?

  trap - EXIT INT TERM
  for pid in "${pids[@]}"; do
    if kill -0 "$pid" 2>/dev/null; then
      kill "$pid" 2>/dev/null || true
    fi
  done
  for pid in "${pids[@]}"; do
    wait "$pid" 2>/dev/null || true
  done
  exit "$exit_code"
}

# Stop the remaining service if either server exits, or when Ctrl-C is pressed.
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

if [[ "$run_backend" -eq 1 ]]; then
  start_backend
fi

if [[ "$run_frontend" -eq 1 ]]; then
  start_frontend
fi

printf 'Press Ctrl-C to stop the selected development server(s).\n'

# macOS ships Bash 3.2, which lacks `wait -n`. Polling lets the launcher stop
# both processes promptly if either one exits.
while true; do
  for pid in "${pids[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      wait "$pid"
      exit $?
    fi
  done
  sleep 0.2
done
