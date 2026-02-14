#ifndef MyAppVersion
  #define MyAppVersion "0.0.0-dev"
#endif

#ifndef StageRoot
  #error "Missing StageRoot define. Pass /DStageRoot=<path to full-stage>."
#endif

#ifndef OutputDir
  #define OutputDir AddBackslash(StageRoot) + "..\installer-output"
#endif

#ifndef MyAppIconFile
  #define MyAppIconFile AddBackslash(SourcePath) + "assets\zotero-pdf2zh-server.ico"
#endif

#define MyAppName "Zotero-PDF2ZH Server"
#define MyAppPublisher "guaguastandup"
#define MyAppExeName "pdf2zh-server.exe"
#define MyAppDataDirName "PDF2ZH Server"

[Setup]
AppId={{C119F5DB-E8E7-4D3B-B35D-9D26F74EEB62}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir={#OutputDir}
OutputBaseFilename=zotero-pdf2zh-server-full-setup-x64-v{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
SetupIconFile={#MyAppIconFile}
CloseApplications=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Dirs]
Name: "{commonappdata}\{#MyAppDataDirName}"
Name: "{commonappdata}\{#MyAppDataDirName}\config"
Name: "{commonappdata}\{#MyAppDataDirName}\translated"
Name: "{commonappdata}\{#MyAppDataDirName}\logs"

[Files]
Source: "{#StageRoot}\app\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Uninstall {#MyAppName}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Run]
Filename: "{app}\prerequisites\vc_redist15.x64.exe"; Parameters: "/quiet /norestart"; Flags: runhidden waituntilterminated skipifdoesntexist
Filename: "{app}\prerequisites\vc_redist17.x64.exe"; Parameters: "/quiet /norestart"; Flags: runhidden waituntilterminated skipifdoesntexist
Filename: "{app}\{#MyAppExeName}"; Description: "Launch {#MyAppName}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{commonappdata}\{#MyAppDataDirName}"
Type: filesandordirs; Name: "{app}"

[Code]
procedure KillServerProcesses();
var
  ResultCode: Integer;
begin
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM pdf2zh-server.exe',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
  Exec(
    ExpandConstant('{sys}\taskkill.exe'),
    '/F /T /IM pdf2zh-server-core.exe',
    '',
    SW_HIDE,
    ewWaitUntilTerminated,
    ResultCode
  );
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    KillServerProcesses();
end;
