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

$appDir = Join-Path $projectDir "dist\FIXATOOLS"
if (-not (Test-Path -LiteralPath $appDir)) {
    throw "A pasta do executável não foi gerada: $appDir"
}
Copy-Item -LiteralPath .\config.ini -Destination (Join-Path $appDir "config.ini") -Force
$zipPath = Join-Path $projectDir "dist\FIXATOOLS_MPCE.zip"
Compress-Archive -Path (Join-Path $appDir "*") -DestinationPath $zipPath -Force
Write-Host "Executável gerado em .\dist\FIXATOOLS\FIXATOOLS.exe"
Write-Host "Configuração copiada para .\dist\FIXATOOLS\config.ini"
Write-Host "Pacote gerado em .\dist\FIXATOOLS_MPCE.zip"
