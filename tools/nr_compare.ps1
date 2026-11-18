<#
.SYNOPSIS
    Runs comparison between two frame generation / upscaling generators on Windows.
.EXAMPLE
    .\tools\nr_compare.ps1 -Record "$env:LOCALAPPDATA\nr-record\capture" -Generator provider -Dll "C:\anr\nvngx_dlssg.dll" -Label "ANR FG" -BGenerator nvidia -BDll "C:\game\nvngx_dlssg.dll" -BLabel "DLSS-G" -View
#>

[CmdletBinding()]
param (
    [Parameter(Mandatory=$true)]
    [string]$Record,
    [string]$Out = "out\cmp",
    [Parameter(Mandatory=$true)]
    [ValidateSet("provider", "nvidia", "dlss", "dlssd", "ngx", "fsr", "ffx", "xess", "anr", "anr-sr", "anr-rr", "recorded")]
    [string]$Generator,
    [string]$Dll,
    [string]$Label = "A",
    [ValidateSet("provider", "nvidia", "dlss", "dlssd", "ngx", "fsr", "ffx", "xess", "anr", "anr-sr", "anr-rr", "recorded")]
    [string]$BGenerator,
    [string]$BDll,
    [string]$BLabel = "B",
    [string]$Frames,
    [int]$Multiplier,
    [ValidateSet("interleaved", "generated")]
    [string]$Mode,
    [string]$Preset,
    [switch]$View,
    [string]$ReplayBin,
    [string]$VideoBin,
    [string]$RendererBin
)

$Python = Get-Command python, python3 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty Source -First 1

if ($Python) {
    $ScriptArgs = @(
        "$PSScriptRoot\nr_compare.py",
        "--record", $Record,
        "--out", $Out,
        "--generator", $Generator,
        "--label", $Label
    )
    if ($Dll) { $ScriptArgs += @("--dll", $Dll) }
    if ($BGenerator) {
        $ScriptArgs += @("--b-generator", $BGenerator, "--b-label", $BLabel)
        if ($BDll) { $ScriptArgs += @("--b-dll", $BDll) }
    }
    if ($Frames) { $ScriptArgs += @("--frames", $Frames) }
    if ($Multiplier) { $ScriptArgs += @("--multiplier", $Multiplier) }
    if ($Mode) { $ScriptArgs += @("--mode", $Mode) }
    if ($Preset) { $ScriptArgs += @("--preset", $Preset) }
    if ($View) { $ScriptArgs += @("--view") }
    if ($ReplayBin) { $ScriptArgs += @("--replay-bin", $ReplayBin) }
    if ($VideoBin) { $ScriptArgs += @("--video-bin", $VideoBin) }
    if ($RendererBin) { $ScriptArgs += @("--renderer-bin", $RendererBin) }

    & $Python @ScriptArgs
    exit $LASTEXITCODE
} else {
    Write-Error "Python 3 is required to run nr_compare. Please install Python or run nr-replay and nr-video manually."
}
