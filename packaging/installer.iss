; Inno Setup script for Cove Narrator (Windows)
; Invoked from build.ps1 via:
;   iscc /DAppVersion=X.Y.Z /DSourceDir=<abs dist\cove-narrator>
;        /DOutputDir=<abs release> /DIconFile=<abs icon.ico> installer.iss

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef SourceDir
  #define SourceDir "..\dist\cove-narrator"
#endif
#ifndef OutputDir
  #define OutputDir "..\release"
#endif
#ifndef IconFile
  #define IconFile "..\build\icon.ico"
#endif

[Setup]
AppId={{A4E7C2D1-9F3B-4A8E-B6D2-1C5E8F0A3B9D}
AppName=Cove Narrator
AppVersion={#AppVersion}
AppPublisher=Cove
AppPublisherURL=https://github.com/Sin213/cove-narrator
AppSupportURL=https://github.com/Sin213/cove-narrator/issues
AppUpdatesURL=https://github.com/Sin213/cove-narrator/releases
DefaultDirName={autopf}\Cove Narrator
DefaultGroupName=Cove Narrator
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\cove-narrator.exe
Compression=lzma2/max
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
ArchitecturesAllowed=x64compatible
OutputDir={#OutputDir}
OutputBaseFilename=cove-narrator-{#AppVersion}-Setup
SetupIconFile={#IconFile}
WizardStyle=modern
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "Create a &desktop shortcut"; GroupDescription: "Additional shortcuts:"

[Files]
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Cove Narrator"; Filename: "{app}\cove-narrator.exe"
Name: "{group}\Uninstall Cove Narrator"; Filename: "{uninstallexe}"
Name: "{autodesktop}\Cove Narrator"; Filename: "{app}\cove-narrator.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\cove-narrator.exe"; Description: "Launch Cove Narrator"; Flags: nowait postinstall skipifsilent
