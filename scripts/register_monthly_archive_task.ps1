param(
    [string]$TaskName = "SafetyZone Monthly Raw Archive",
    [string]$ArchiveScript = (Join-Path $PSScriptRoot "archive_monthly_snapshot.ps1"),
    [string]$ArchiveMonthArgument = "",
    [int]$DayOfMonth = 28,
    [string]$At = "11:00",
    [switch]$KeepExistingArchiveData
)

$ErrorActionPreference = "Stop"

$scriptPath = Resolve-Path $ArchiveScript
$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")

$arguments = @(
    "-NoProfile",
    "-ExecutionPolicy", "Bypass",
    "-File", "`"$scriptPath`""
)

if ($ArchiveMonthArgument) {
    $arguments += @("-ArchiveMonth", $ArchiveMonthArgument)
}
if (-not $KeepExistingArchiveData) {
    $arguments += "-ReplaceArchiveData"
}

$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument ($arguments -join " ") `
    -WorkingDirectory $repoRoot
$trigger = New-ScheduledTaskTrigger -Monthly -DaysOfMonth $DayOfMonth -At $At
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -ExecutionTimeLimit (New-TimeSpan -Hours 6)

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description "Archive nationwide safety-zone raw API snapshots to local PostgreSQL and pg_dump monthly." `
    -Force | Out-Null

Write-Host "Registered scheduled task: $TaskName"
Write-Host "Schedule: day $DayOfMonth at $At every month"
Write-Host "Script: $scriptPath"
