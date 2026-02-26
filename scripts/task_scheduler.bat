@echo off
REM ========================================
REM CatClawBoard - Scheduler (常驻模式)
REM 单进程登录 THS，按时间表自动执行所有采集任务
REM ========================================

call "%~dp0env.bat"
cd /d "%PROJECT_DIR%"
"%PYTHON_EXE%" -m app.collectors.scheduler
exit /b %ERRORLEVEL%
