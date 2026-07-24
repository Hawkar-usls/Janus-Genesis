$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$pythonExe = $null
$pythonArgs = @()
$candidates = @(
    @{ Exe = "py"; Args = @("-3") },
    @{ Exe = "python"; Args = @() },
    @{ Exe = "python3"; Args = @() }
)

foreach ($candidate in $candidates) {
    try {
        $versionText = (& $candidate.Exe @($candidate.Args) --version 2>&1 | Out-String).Trim()
        if ($LASTEXITCODE -ne 0) { continue }
        if ($versionText -match "Python\s+(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if (($major -gt 3) -or (($major -eq 3) -and ($minor -ge 11))) {
                $pythonExe = $candidate.Exe
                $pythonArgs = @($candidate.Args)
                break
            }
        }
    } catch {}
}
if (-not $pythonExe) { throw "Python 3.11+ not found." }

& $pythonExe @pythonArgs "$root\janus_genesis.py"
if ($LASTEXITCODE -ne 0) {
    throw "Janus Genesis stopped with exit code $LASTEXITCODE."
}
