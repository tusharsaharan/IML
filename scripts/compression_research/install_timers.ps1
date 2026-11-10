param([Parameter(Mandatory=$true)][string]$State)
$ErrorActionPreference = 'Stop'
$config = Get-Content -LiteralPath $State -Raw | ConvertFrom-Json
if ($config.interval_seconds -ne 1800 -or $config.check_times.Count -ne 20) {
    throw 'Expected exactly 20 timer slots, 30 minutes apart.'
}
$name = 'IML-Compression-' + (Get-Date -Format 'yyyyMMdd-HHmmss')
$worker = Join-Path $PSScriptRoot 'timer_check.ps1'
$powershell = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
$arguments = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -File "' + $worker + '" -State "' + $State + '"'
try {
    $triggers = @($config.check_times | ForEach-Object {
        New-ScheduledTaskTrigger -Once -At ([datetimeoffset]::Parse($_).LocalDateTime)
    })
    $action = New-ScheduledTaskAction -Execute $powershell -Argument $arguments
    $settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 25)
    $principal = New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().Name) -LogonType Interactive -RunLevel Limited
    $task = Register-ScheduledTask -TaskName $name -Action $action -Trigger $triggers -Settings $settings -Principal $principal
    $info = Get-ScheduledTaskInfo -TaskName $name
    $registration = @{mode='windows_task_scheduler';task_name=$name;trigger_count=$task.Triggers.Count;next_run=$info.NextRunTime.ToString('o');state=$State}
} catch {
    # No elevation request or system power change. A detached, finite user-owned
    # worker is a fallback, requiring this login and computer to remain awake.
    $arguments += ' -Mode run'
    $folder = Split-Path -Parent $State
    $process = Start-Process -FilePath $powershell -ArgumentList $arguments -WindowStyle Hidden -PassThru `
        -RedirectStandardOutput (Join-Path $folder 'timer-worker.log') `
        -RedirectStandardError (Join-Path $folder 'timer-worker-error.log')
    $registration = @{mode='detached_windows_worker';pid=$process.Id;trigger_count=20;state=$State;task_scheduler='unavailable'}
}
$registration | ConvertTo-Json | Set-Content -LiteralPath (Join-Path (Split-Path -Parent $State) 'timer-registration.json')
$registration | ConvertTo-Json
