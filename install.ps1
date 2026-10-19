# Installation des outils du depot (aucune manipulation manuelle).
# - Python 3.11+ (deja present) ;
# - PyBoy (simulateur Game Boy), SkoolKit (simulateur Z80), Pillow, numpy ;
# - RGBDS (rgbasm/rgblink/rgbfix) pour reassembler le listing GB.
$ErrorActionPreference = 'Stop'
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
python -m pip install --disable-pip-version-check --upgrade pyboy skoolkit pillow numpy
if ($LASTEXITCODE -ne 0) { throw 'pip a echoue' }

$rgb = Join-Path $env:LOCALAPPDATA 'rgbds'
if (-not (Test-Path (Join-Path $rgb 'rgbasm.exe'))) {
    Write-Output 'RGBDS absent : telechargement de la version Windows...'
    $zip = Join-Path $env:TEMP 'rgbds-win64.zip'
    Invoke-WebRequest -Uri 'https://github.com/gbdev/rgbds/releases/latest/download/rgbds-win64.zip' -OutFile $zip
    New-Item -ItemType Directory -Force -Path $rgb | Out-Null
    Expand-Archive -LiteralPath $zip -DestinationPath $rgb -Force
    Remove-Item $zip
}
foreach ($t in 'rgbasm','rgblink','rgbfix') {
    $p = Join-Path $rgb ($t + '.exe')
    if (-not (Test-Path $p)) { throw "$t introuvable dans $rgb" }
}
Write-Output "Outils OK : PyBoy, SkoolKit, RGBDS ($rgb)"
