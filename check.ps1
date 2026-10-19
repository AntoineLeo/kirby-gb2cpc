# Lance check.sh avec le shell POSIX de Git (sh n'est pas dans le PATH Windows).
param([string]$Mode = 'rapide')
$sh = Join-Path $env:ProgramFiles 'Git\bin\sh.exe'
if (-not (Test-Path $sh)) { throw "Git Bash introuvable : $sh" }
& $sh (Join-Path $PSScriptRoot 'check.sh') $Mode
exit $LASTEXITCODE
