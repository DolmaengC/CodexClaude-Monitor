$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$SettingsDir = Join-Path $HOME ".claude"
$SettingsPath = Join-Path $SettingsDir "settings.json"
$SnapshotPath = Join-Path $RepoRoot "data\claude_statusline_snapshot.json"
$CaptureScript = Join-Path $RepoRoot "tools\claude_statusline_capture.py"
$PythonCommand = "python `"$CaptureScript`" --snapshot `"$SnapshotPath`""

New-Item -ItemType Directory -Force $SettingsDir | Out-Null

$settings = @{}
if (Test-Path $SettingsPath) {
    $raw = Get-Content $SettingsPath -Raw -Encoding UTF8
    if ($raw.Trim()) {
        $settings = $raw | ConvertFrom-Json -AsHashtable
    }
}

$backupPath = Join-Path $SettingsDir ("settings.backup-{0}.json" -f (Get-Date -Format "yyyyMMddHHmmss"))
if (Test-Path $SettingsPath) {
    Copy-Item $SettingsPath $backupPath
}

$settings["statusLine"] = @{
    type = "command"
    command = $PythonCommand
}

$json = $settings | ConvertTo-Json -Depth 100
[System.IO.File]::WriteAllText($SettingsPath, $json, [System.Text.Encoding]::UTF8)

Write-Host "Claude statusLine helper installed."
Write-Host "Settings: $SettingsPath"
if (Test-Path $backupPath) {
    Write-Host "Backup:   $backupPath"
}
Write-Host "Snapshot: $SnapshotPath"
Write-Host ""
Write-Host "Interact with Claude once more and the dashboard will pick up 5h/7d limits."
