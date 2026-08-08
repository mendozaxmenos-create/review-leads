@echo off
REM Tunel gratis Cloudflare → demo local (PC encendida). Preferí Render prod:
REM   https://review-leads.onrender.com/demo
REM Uso: scripts\run_demo_tunnel.bat
cd /d "%~dp0.."
if not exist tools\cloudflared.exe (
  echo Falta tools\cloudflared.exe
  exit /b 1
)
echo Abriendo tunel publico a http://127.0.0.1:8000 ...
echo Deja esta ventana abierta mientras los leads prueban la demo.
echo.
tools\cloudflared.exe tunnel --url http://127.0.0.1:8000
