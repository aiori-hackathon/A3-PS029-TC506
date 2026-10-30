@echo off
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel%==0 (
  py -3 qoo_x_app.py
) else (
  python qoo_x_app.py
)
if errorlevel 1 pause
