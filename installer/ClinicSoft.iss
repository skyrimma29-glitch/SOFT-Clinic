; Inno Setup script for the single-computer ClinicSoft installation.
; PostgreSQL is intentionally a prerequisite, not silently replaced.
#define AppName "ClinicSoft-IPS"
#define AppVersion "1.1.0"
#define AppExeName "ClinicSoft-IPS.exe"

[Setup]
AppId={{B7B5C2C8-4C8B-4D20-9C71-1A2B3C4D5E6F}
AppName={#AppName}
AppVersion={#AppVersion}
DefaultDirName={autopf}\ClinicSoft-IPS
DefaultGroupName={#AppName}
OutputDir=..\dist\installer
OutputBaseFilename=ClinicSoft-IPS-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=admin

[Files]
Source: "..\dist\ClinicSoft-IPS\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "..\scripts\clinicsoft-db.ps1"; DestDir: "{app}\scripts"; Flags: ignoreversion

[Icons]
Name: "{autodesktop}\ClinicSoft-IPS"; Filename: "{app}\{#AppExeName}"
Name: "{group}\ClinicSoft-IPS"; Filename: "{app}\{#AppExeName}"

[Run]
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -File ""{app}\scripts\clinicsoft-db.ps1"""; Description: "Preparar base de datos de ClinicSoft"; Flags: waituntilterminated postinstall runhidden
Filename: "{app}\{#AppExeName}"; Description: "Iniciar ClinicSoft-IPS"; Flags: nowait postinstall skipifsilent

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
  if not DirExists(ExpandConstant('{pf64}\PostgreSQL')) and
     not DirExists(ExpandConstant('{pf}\PostgreSQL')) then
    MsgBox('PostgreSQL no parece estar instalado. Instálelo y configure la base soft_clinic_db antes de iniciar ClinicSoft. Las migraciones se ejecutarán automáticamente cuando la base esté disponible.', mbInformation, MB_OK);
  if not RegKeyExists(HKLM, 'SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') and
     not RegKeyExists(HKLM, 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}') then
    MsgBox('Microsoft Edge WebView2 Runtime no parece estar instalado. Instálelo para abrir ClinicSoft como ventana de escritorio.', mbInformation, MB_OK);
end;
