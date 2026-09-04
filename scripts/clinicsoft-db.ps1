param(
    [string]$Database = 'soft_clinic_db',
    [string]$User = 'postgres',
    [string]$HostName = '127.0.0.1',
    [int]$Port = 5432
)

$ErrorActionPreference = 'Stop'
$manage = Join-Path $PSScriptRoot '..\manage.py'

Write-Host "Verificando PostgreSQL en $HostName`:$Port..."
$connection = Test-NetConnection -ComputerName $HostName -Port $Port -InformationLevel Quiet
if (-not $connection) {
    throw 'PostgreSQL no está disponible. Instálelo o inicie el servicio antes de continuar.'
}

Write-Host "Verificando si existe la base $Database..."
$psqlExe = Get-Command psql -ErrorAction SilentlyContinue
if (-not $psqlExe) {
    throw 'No se encontró psql en PATH. PostgreSQL no está disponible en la ruta del sistema.'
}

$exists = & psql -h $HostName -p $Port -U $User -d postgres -Atqc "SELECT 1 FROM pg_database WHERE datname = '$Database';"
if (-not $exists) {
    Write-Host "Creando la base de datos $Database..."
    & createdb -h $HostName -p $Port -U $User $Database
}

Write-Host "Aplicando migraciones de ClinicSoft..."
python $manage migrate --noinput
Write-Host "Base de datos lista: $Database"
