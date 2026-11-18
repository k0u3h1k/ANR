<#
.SYNOPSIS
    Game Auto-Detector & ANR / OptiScaler Installer for Windows.
.EXAMPLE
    .\tools\game_installer.ps1 -Scan
    .\tools\game_installer.ps1 -Install 1 -Upscaler xess
    .\tools\game_installer.ps1 -Install "C:\Games\Cyberpunk 2077"
#>

[CmdletBinding()]
param (
    [switch]$Scan,
    [string]$Install,
    [string]$Uninstall,
    [ValidateSet("anr", "anr-sr", "anr-rr", "xess", "dlss", "fsr21", "fsr22", "fsr31")]
    [string]$Upscaler,
    [string]$Path
)

$Python = Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1

if ($Python) {
    $ScriptArgs = @("$PSScriptRoot\game_installer.py")
    if ($Scan -or (-not $Install -and -not $Uninstall)) { $ScriptArgs += "--scan" }
    if ($Install) { $ScriptArgs += @("--install", $Install) }
    if ($Uninstall) { $ScriptArgs += @("--uninstall", $Uninstall) }
    if ($Upscaler) { $ScriptArgs += @("--upscaler", $Upscaler) }
    if ($Path) { $ScriptArgs += @("--path", $Path) }

    & $Python @ScriptArgs
    exit $LASTEXITCODE
} else {
    Write-Error "Python 3 is required to run the game installer scanner."
}
