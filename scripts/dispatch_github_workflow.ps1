param(
    [string]$Owner = "youngj-kim",
    [string]$Repo = "safetyzone_automation",
    [string]$Workflow = "daily-monitor.yml",
    [string]$Ref = "main",
    [string]$TokenFile = ".secrets\github_dispatch_token.txt",
    [ValidateSet("true", "false")]
    [string]$NotificationTest = "false"
)

$ErrorActionPreference = "Stop"

Set-Location (Resolve-Path (Join-Path $PSScriptRoot ".."))

$token = $env:GITHUB_DISPATCH_TOKEN
if ([string]::IsNullOrWhiteSpace($token) -and (Test-Path $TokenFile)) {
    $token = (Get-Content $TokenFile -Raw).Trim()
}

if ([string]::IsNullOrWhiteSpace($token)) {
    throw "Missing GitHub token. Set GITHUB_DISPATCH_TOKEN or create $TokenFile."
}

$headers = @{
    Authorization = "Bearer $token"
    Accept = "application/vnd.github+json"
    "X-GitHub-Api-Version" = "2022-11-28"
}

$body = @{
    ref = $Ref
    inputs = @{
        notification_test = $NotificationTest
    }
} | ConvertTo-Json -Depth 5

$uri = "https://api.github.com/repos/$Owner/$Repo/actions/workflows/$Workflow/dispatches"

Invoke-RestMethod `
    -Method Post `
    -Uri $uri `
    -Headers $headers `
    -Body $body `
    -ContentType "application/json"

Write-Host "Dispatched GitHub Actions workflow '$Workflow' on '$Owner/$Repo' ref '$Ref'."
