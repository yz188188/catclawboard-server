# ========================================
# CatClawBoard Windows Task Scheduler 一键注册脚本
# 需要以管理员权限运行
#
# 使用 scheduler 常驻模式：单进程登录 THS，按时间表自动执行所有采集任务
# 避免多进程同时 thslogin() 导致互相踢下线
# ========================================

# Check admin privileges
$isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Not running as admin, re-launching with elevation..." -ForegroundColor Yellow
    $scriptPath = $MyInvocation.MyCommand.Path
    Start-Process powershell.exe -Verb RunAs -ArgumentList "-ExecutionPolicy Bypass -File `"$scriptPath`"" -Wait
    exit
}

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TaskFolder = "\CatClawBoard\"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host " CatClawBoard 定时任务注册" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "脚本目录: $ScriptDir"

# ---- 第1步: 删除旧的独立任务 ----
$oldTasks = @(
    "CatClaw_bidding", "CatClaw_mighty", "CatClaw_lianban", "CatClaw_jjmighty",
    "CatClaw_stat", "CatClaw_thsdata",
    "CatClaw_mighty_close", "CatClaw_lianban_close", "CatClaw_jjmighty_close"
)

Write-Host ""
Write-Host "清理旧的独立任务..." -ForegroundColor Yellow
foreach ($name in $oldTasks) {
    $existing = Get-ScheduledTask -TaskName $name -TaskPath $TaskFolder -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $name -TaskPath $TaskFolder -Confirm:$false
        Write-Host "  已删除: $name" -ForegroundColor DarkGray
    }
}

# ---- 第2步: 注册 scheduler 常驻任务 + cleanup_logs ----
$tasks = @(
    @{
        Name        = "CatClaw_scheduler"
        Hour        = 9
        Minute      = 15
        Script      = "task_scheduler.bat"
        Description = "采集调度器常驻模式 (9:15 启动，自动执行全天所有采集任务)"
        TimeLimit   = 480
    },
    @{
        Name        = "CatClaw_cleanup_logs"
        Hour        = 23
        Minute      = 0
        Script      = "cleanup_logs.bat"
        Description = "清理30天前日志 (23:00)"
        TimeLimit   = 5
    }
)

foreach ($task in $tasks) {
    $taskName = $task.Name
    $batPath = Join-Path $ScriptDir $task.Script
    $timeLimitMinutes = $task.TimeLimit

    Write-Host ""
    Write-Host "注册任务: $taskName" -ForegroundColor Yellow
    Write-Host "  脚本: $batPath"
    Write-Host "  时间: $($task.Hour):$($task.Minute.ToString('D2'))"
    Write-Host "  说明: $($task.Description)"

    # 检查 bat 脚本是否存在
    if (-not (Test-Path $batPath)) {
        Write-Host "  错误: 脚本不存在，跳过!" -ForegroundColor Red
        continue
    }

    # 删除已有的同名任务（静默）
    $existing = Get-ScheduledTask -TaskName $taskName -TaskPath $TaskFolder -ErrorAction SilentlyContinue
    if ($existing) {
        Unregister-ScheduledTask -TaskName $taskName -TaskPath $TaskFolder -Confirm:$false
        Write-Host "  已删除旧任务" -ForegroundColor DarkGray
    }

    # 创建触发器: 每天指定时间
    $trigger = New-ScheduledTaskTrigger -Daily -At "$($task.Hour):$($task.Minute.ToString('D2'))"

    # 创建操作: 运行 bat 脚本
    $action = New-ScheduledTaskAction -Execute $batPath

    # 创建设置
    $settings = New-ScheduledTaskSettingsSet `
        -StartWhenAvailable `
        -RestartCount 2 `
        -RestartInterval (New-TimeSpan -Minutes 5) `
        -ExecutionTimeLimit (New-TimeSpan -Minutes $timeLimitMinutes) `
        -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries

    # 注册任务（以当前用户身份运行）
    Register-ScheduledTask `
        -TaskName $taskName `
        -TaskPath $TaskFolder `
        -Trigger $trigger `
        -Action $action `
        -Settings $settings `
        -Description $task.Description `
        | Out-Null

    Write-Host "  注册成功" -ForegroundColor Green
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host " 注册完成! 已注册的任务:" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Get-ScheduledTask -TaskPath $TaskFolder | Format-Table TaskName, State, @{
    Label      = "NextRunTime"
    Expression = { (Get-ScheduledTaskInfo -TaskName $_.TaskName -TaskPath $_.TaskPath).NextRunTime }
} -AutoSize

Write-Host ""
Write-Host "手动启动: .\scripts\task_scheduler.bat" -ForegroundColor DarkGray
Write-Host "查看日志: type logs\scheduler_$(Get-Date -Format 'yyyyMMdd').log" -ForegroundColor DarkGray
Write-Host "删除所有: Get-ScheduledTask -TaskPath '$TaskFolder' | Unregister-ScheduledTask -Confirm:`$false" -ForegroundColor DarkGray
