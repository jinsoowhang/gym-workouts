@echo off
cd /d "%~dp0"
start "Gym Workouts server" wsl.exe --cd "%~dp0." bash -lc "bash scripts/start.sh"
powershell.exe -NoProfile -Command "$gymUrl = 'http://127.0.0.1:8010'; for ($gymAttempt = 0; $gymAttempt -lt 30; $gymAttempt++) { try { $gymHealth = Invoke-RestMethod -Uri ($gymUrl + '/health') -TimeoutSec 1; if ($gymHealth.application -eq 'gym-workouts') { Start-Process $gymUrl; exit 0 } } catch {}; Start-Sleep -Milliseconds 500 }; Write-Host 'The server did not start. Check the Gym Workouts server window.'; exit 1"
if errorlevel 1 pause
