#!/usr/bin/env bash
set -euo pipefail

echo "[NLP Project] One-click start (Linux)"
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$ROOT_DIR"

have() { command -v "$1" >/dev/null 2>&1; }

echo "[*] Checking Python..."
if ! have python3 && ! have python ; then
  echo "[!] Python 3 not found. Please install Python 3.9+ (apt/yum/brew) and retry."
  exit 1
fi

PYBIN="python3"
if ! have python3 ; then PYBIN="python"; fi

echo "[*] Creating venv (if missing)..."
if [ ! -d ".venv" ]; then
  "$PYBIN" -m venv .venv
fi
source .venv/bin/activate

echo "[*] Installing backend dependencies..."
python -m pip install --upgrade pip >/dev/null
pip install -r requirements.txt

echo "[*] Starting backend server..."
nohup python api_server.py > backend.log 2>&1 &
BACK_PID=$!
echo "    Backend PID: $BACK_PID (logs: backend.log)"

echo "[*] Checking npm..."
if ! have npm ; then
  echo "[!] npm not found. Please install Node.js LTS (https://nodejs.org) or via nvm, then re-run this script."
  echo "    Example with nvm:"
  echo "      curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash"
  echo "      source ~/.nvm/nvm.sh && nvm install --lts && nvm use --lts"
  exit 0
fi

echo "[*] Installing frontend dependencies..."
pushd "$ROOT_DIR/FrontEnd" >/dev/null
if [ -f "package-lock.json" ]; then
  npm ci
else
  npm install
fi

echo "[*] Starting frontend dev server..."
echo "    Visit http://localhost:5173"
npm run dev
popd >/dev/null



