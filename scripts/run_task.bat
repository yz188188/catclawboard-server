@echo off
REM ========================================
REM CatClawBoard - Task Runner
REM Usage: run_task.bat <task_name>
REM ========================================

if "%~1"=="" (
    echo Usage: run_task.bat ^<task_name^>
    echo Tasks: bidding, mighty, thsdata, stat, mighty_close
    exit /b 1
)

call "%~dp0env.bat"
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" -m app.collectors.scheduler --task %1
exit /b %ERRORLEVEL%
