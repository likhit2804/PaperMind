@echo off
TITLE PaperMind - Local Launcher

echo ========================================================
echo             PaperMind Launcher
echo  Read less. Understand more.
echo ========================================================
echo.

set "ROOT=%~dp0"

if not exist "%ROOT%backend-node\node_modules" (
    echo [INFO] Installing Backend npm dependencies...
    cd /d "%ROOT%backend-node"
    call npm install
    cd /d "%ROOT%"
)

if not exist "%ROOT%frontend-react\node_modules" (
    echo [INFO] Installing Frontend npm dependencies...
    cd /d "%ROOT%frontend-react"
    call npm install
    cd /d "%ROOT%"
)

echo [1/2] Launching Backend Server (Node.js/Express on Port 8000)...
start "PaperMind Backend" cmd /k cd /d "%ROOT%backend-node" ^&^& npm run dev

echo [2/2] Launching Frontend Interface (React/Vite on Port 5173)...
start "PaperMind Frontend" cmd /k cd /d "%ROOT%frontend-react" ^&^& npm run dev

echo.
echo ========================================================
echo  PaperMind application is starting!
echo  - Backend API:  http://localhost:8000
echo  - Frontend UI:   http://localhost:5173
echo ========================================================
echo.
echo Opening browser in 3 seconds...
ping 127.0.0.1 -n 4 >nul
start http://localhost:5173

echo.
echo Servers are running in separate command windows.
echo Press any key to close this launcher window...
pause >nul
