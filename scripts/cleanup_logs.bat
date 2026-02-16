@echo off
REM ========================================
REM CatClawBoard - Cleanup logs older than 30 days
REM ========================================

call "%~dp0env.bat"
forfiles /p "%PROJECT_DIR%\logs" /s /m *.log /d -30 /c "cmd /c del @path" 2>nul

if %ERRORLEVEL% EQU 0 (
    echo Cleaned up log files older than 30 days
) else (
    echo No log files to clean up
)
