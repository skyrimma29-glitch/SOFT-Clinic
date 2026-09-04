param(
    [switch]$Clean
)

$ErrorActionPreference = 'Stop'
if ($Clean -and (Test-Path dist)) { Remove-Item dist -Recurse -Force }

python -m pip install -r requirements.txt
if (-not (Test-Path assets\clinicsoft.ico)) { throw 'No se encontró assets\clinicsoft.ico.' }
python -m PyInstaller --noconfirm --clean --onedir --name ClinicSoft-IPS `
    --icon "assets\clinicsoft.ico" `
    --add-data "core;core" `
    --add-data "facturacion;facturacion" `
    --add-data "facturacion/static;facturacion/static" `
    --add-data "static;static" `
    --add-data "manage.py;." `
    clinicsoft_desktop.py

Write-Host 'Build terminado en dist\ClinicSoft-IPS.'
Write-Host 'Para generar el instalador, abra installer\ClinicSoft.iss con Inno Setup.'
