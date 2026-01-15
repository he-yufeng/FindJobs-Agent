@echo off
setlocal ENABLEDELAYEDEXPANSION

echo [NLP Project] One-click start (Windows)
echo.

REM ---- Locate project root (this script should be under scripts/) ----
pushd %~dp0
cd ..
set ROOT=%CD%

REM ---- 1) Start backend (no env management, just run) ----
echo [*] Starting backend server...
start "" cmd /k "cd /d %ROOT% && python api_server.py"

REM ---- 2) Ensure npm is available; if not, try to install Node.js LTS ----
where npm >nul 2>nul
if errorlevel 1 (
  echo [!] npm not found. Attempting to install Node.js LTS...

  REM Try winget first
  where winget >nul 2>nul
  if not errorlevel 1 (
    echo [*] Using winget to install Node.js LTS...
    winget install --id OpenJS.NodeJS.LTS -e --accept-source-agreements --accept-package-agreements
  ) else (
    REM Try chocolatey
    where choco >nul 2>nul
    if not errorlevel 1 (
      echo [*] Using chocolatey to install nodejs-lts...
      choco install nodejs-lts -y
    ) else (
      echo [!] Could not find winget or choco to auto-install Node.js.
      echo     Please install Node.js from https://nodejs.org and re-run this script.
      goto end
    )
  )
)

REM ---- 3) Start frontend: install deps then run dev server ----
pushd "%ROOT%\\FrontEnd"
if not exist node_modules (
  echo [*] node_modules not found, installing frontend dependencies...
  call npm install
) else (
  echo [*] Frontend dependencies already installed, skipping npm install.
)
echo [*] Starting frontend dev server...
start "" cmd /k "cd /d %ROOT%\\FrontEnd && npm run dev"
popd

echo.
echo [✓] Backend: http://localhost:5000
echo [✓] Frontend: http://localhost:5173 (dev server will appear in a new window)

:end
popd
endlocal
