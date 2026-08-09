<#
.SYNOPSIS
  Install ytmp3 shims into ~/bin so the command works from every shell.

.DESCRIPTION
  PowerShell and cmd prefer name.cmd; bash looks for the exact name. Writing
  both side by side means one command works from PowerShell, cmd, Git Bash and
  MSYS2. The repo path is baked in, so no PATH or PYTHONPATH juggling is needed
  at call time.
#>

$ErrorActionPreference = "Stop"

$repo = $PSScriptRoot
$bin = Join-Path $HOME "bin"
$python = (Get-Command python -ErrorAction SilentlyContinue).Source
if (-not $python) { throw "python not found on PATH" }

if (-not (Test-Path $bin)) { New-Item -ItemType Directory -Path $bin | Out-Null }

$repoForward = $repo -replace '\\', '/'

$cmdShim = @"
@echo off
python -X utf8 "$repo\shim.py" %*
"@

$bashShim = @"
#!/usr/bin/env bash
exec python -X utf8 "$repoForward/shim.py" "`$@"
"@

Set-Content -Path (Join-Path $bin "ytmp3.cmd") -Value $cmdShim -Encoding ascii
Set-Content -Path (Join-Path $bin "ytmp3") -Value ($bashShim -replace "`r`n", "`n") -Encoding ascii -NoNewline

Write-Host "installed:"
Write-Host "  $bin\ytmp3.cmd"
Write-Host "  $bin\ytmp3"

$userPath = [Environment]::GetEnvironmentVariable("PATH", "User")
if ($userPath -notlike "*$bin*") {
    Write-Host ""
    Write-Host "warning: $bin is not on the User PATH" -ForegroundColor Yellow
    Write-Host "add it with:"
    Write-Host "  [Environment]::SetEnvironmentVariable('PATH', `"`$env:PATH;$bin`", 'User')"
}
