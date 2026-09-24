$ErrorActionPreference = "Stop"

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $projectDir

$env:OPENBLAS_NUM_THREADS = "1"
py -3 -m PyInstaller --noconfirm --clean .\fixatools.spec
if ($LASTEXITCODE -ne 0) {
    throw "O PyInstaller falhou com código $LASTEXITCODE."
}

if (-not (Test-Path -LiteralPath .\config.ini)) {
    throw "config.ini não encontrado. Configure os acessos antes de distribuir o executável."
}

Copy-Item -LiteralPath .\config.ini -Destination .\dist\config.ini -Force
Write-Host "Executável gerado em .\dist\FIXATOOLS.exe"
Write-Host "Configuração copiada para .\dist\config.ini"
