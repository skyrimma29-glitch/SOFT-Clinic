# ClinicSoft-IPS como aplicación de escritorio

ClinicSoft se distribuye como una ventana nativa de Windows. Internamente sigue usando Django y PostgreSQL, pero el usuario no necesita abrir el navegador manualmente.

## Arquitectura

- `ClinicSoft-IPS.exe` inicia el servidor Django en `127.0.0.1`.
- `pywebview` muestra el sistema en una ventana WebView2.
- PostgreSQL se ejecuta como servicio local de Windows.
- La base existente se conserva; el instalador solo ejecuta migraciones.

## Preparación del equipo destino

1. Instalar PostgreSQL 14 o superior.
2. Crear la base `soft_clinic_db` y configurar el usuario de aplicación.
3. Ejecutar `scripts\clinicsoft-db.ps1` como administrador.
4. Verificar que Microsoft Edge WebView2 Runtime esté instalado.

## Generar el ejecutable

Desde PowerShell en la raíz del proyecto:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\build_desktop.ps1 -Clean
```

El resultado queda en `dist\ClinicSoft-IPS`.

## Generar el instalador

Abrir `installer\ClinicSoft.iss` con Inno Setup y compilarlo. El instalador crea el acceso directo y ofrece iniciar ClinicSoft al terminar.

## Nota sobre PostgreSQL

Esta primera versión no instala PostgreSQL silenciosamente ni distribuye contraseñas. Es deliberado: evita sobrescribir una base existente. La automatización completa de PostgreSQL se puede añadir después cuando se defina la política de respaldos y credenciales.
