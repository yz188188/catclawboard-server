# ========================================
# CatClawBoard Windows Task Scheduler 一键注册脚本
# 需要以管理员权限运行
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

# 检查脚本目录
Write-Host "脚本目录: $ScriptDir"

# 任务定义: 名称, 触发时间(时:分), bat 脚本, 说明, 最大执行时长(分钟)
$tasks = @(
    @{
        Name        = "CatClaw_bidding"
        Hour        = 9
        Minute      = 26
        Script      = "task_bidding.bat"
        Description = "竞价数据采集 (9:26)"
        TimeLimit   = 10
    },
    @{
        Name        = "CatClaw_mighty"
        Hour        = 9
        Minute      = 30
        Script      = "task_mighty.bat"
        Description = "强势反包实时监控 (9:30，内含16分钟循环)"
        TimeLimit   = 30
    },
    @{
        Name        = "CatClaw_lianban"
        Hour        = 9
        Minute      = 30
        Script      = "task_lianban.bat"
        Description = "连板反包实时监控 (9:30，内含16分钟循环)"
        TimeLimit   = 30
    },
    @{
        Name        = "CatClaw_jjmighty"
        Hour        = 9
        Minute      = 30
        Script      = "task_jjmighty.bat"
        Description = "竞价强势实时监控 (9:30，内含16分钟循环)"
        TimeLimit   = 30
    },
    @{
        Name        = "CatClaw_stat"
        Hour        = 15
        Minute      = 5
        Script      = "task_stat.bat"
        Description = "涨停统计 (15:05)"
        TimeLimit   = 15
    },
    @{
        Name        = "CatClaw_thsdata"
        Hour        = 15
        Minute      = 8
        Script      = "task_thsdata.bat"
        Description = "涨停反包+大额成交，收盘后全天数据 (15:08)"
        TimeLimit   = 15
    },
    @{
        Name        = "CatClaw_mighty_close"
        Hour        = 15
        Minute      = 15
        Script      = "task_mighty_close.bat"
        Description = "更新强势反包收盘涨幅 (15:15)"
        TimeLimit   = 10
    },
    @{
        Name        = "CatClaw_lianban_close"
        Hour        = 15
        Minute      = 15
        Script      = "task_lianban_close.bat"
        Description = "更新连板反包收盘涨幅 (15:15)"
        TimeLimit   = 10
    },
    @{
        Name        = "CatClaw_jjmighty_close"
        Hour        = 15
        Minute      = 15
        Script      = "task_jjmighty_close.bat"
        Description = "更新竞价强势收盘涨幅 (15:15)"
        TimeLimit   = 10
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
Write-Host "手动测试: .\scripts\run_task.bat stat" -ForegroundColor DarkGray
Write-Host "查看日志: type logs\stat_$(Get-Date -Format 'yyyyMMdd').log" -ForegroundColor DarkGray
Write-Host "删除所有: Get-ScheduledTask -TaskPath '$TaskFolder' | Unregister-ScheduledTask -Confirm:`$false" -ForegroundColor DarkGray
