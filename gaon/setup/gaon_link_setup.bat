@echo off
REM ============================================================
REM GAON NEXUS - Symbolic Link Setup Launcher
REM RULE: ZERO Korean chars - all Korean path ops via Python
REM REQUIREMENT: Run as Administrator (right-click -> Run as Admin)
REM ============================================================

set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ============================================================
echo  GAON NEXUS Symbolic Link Setup
echo  Run as Administrator required
echo ============================================================
echo.

REM ── Administrator check ──────────────────────────────────────
net session >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Please run this script as Administrator.
    echo         Right-click the BAT file and select "Run as administrator"
    pause
    exit /b 1
)
echo [OK] Administrator confirmed.
echo.

REM ── All Korean path operations delegated to Python ───────────
echo [RUN] Executing link setup via Python...
echo.

python -X utf8 "C:\gaon\setup\create_symlinks.py"
if errorlevel 1 (
    echo.
    echo [ERROR] Link setup failed. Check output above.
    pause
    exit /b 1
)

echo.
echo ============================================================
echo  Setup Complete.
echo  Next steps:
echo    1. python C:\gaon\ops\daily_health_check.py
echo    2. python C:\gaon\utils\discord_notify.py --test
echo ============================================================
pause
