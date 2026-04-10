# Create a Windows shortcut to launch Board Generator Studio (Web UI).
# Run from project root: powershell -ExecutionPolicy Bypass -File scripts/create_shortcut.ps1
# Optional: pass a shortcut key, e.g. -ShortcutKey "Ctrl+Alt+G"
# To create a shortcut with no hotkey: -ShortcutKey ""

param(
    [string]$ShortcutKey = "Ctrl+Alt+G"
)

$ErrorActionPreference = "Stop"
$ProjectRoot = $PSScriptRoot | Split-Path -Parent
$BatchPath = Join-Path $ProjectRoot "launch_board_studio.bat"

if (-not (Test-Path $BatchPath)) {
    Write-Error "Not found: $BatchPath. Run this script from the project root."
}

$WshShell = New-Object -ComObject WScript.Shell
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Board Generator Studio.lnk"

$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $BatchPath
$Shortcut.WorkingDirectory = $ProjectRoot
$Shortcut.Description = "Launch Board Generator Studio (Web UI)"
$Shortcut.WindowStyle = 7

if ($ShortcutKey) {
    $Shortcut.Hotkey = $ShortcutKey
}

$Shortcut.Save()
[System.Runtime.Interopservices.Marshal]::ReleaseComObject($WshShell) | Out-Null

Write-Host "Shortcut created: $ShortcutPath"
if ($ShortcutKey) {
    Write-Host "Shortcut key: $ShortcutKey"
}
Write-Host "Right-click the shortcut -> Properties to change or remove the shortcut key."
