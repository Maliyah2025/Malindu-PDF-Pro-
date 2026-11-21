#define MyAppName "Malindu PDF Pro"
#define MyAppExeName "Malindu_PDF_Pro_Windows_x64.exe"
[Setup]
AppId={{3320D953-7E7D-442D-93EF-6F31426F8F26}
AppName={#MyAppName}
AppVersion=1.4.0
DefaultDirName={localappdata}\Programs\Malindu PDF Pro
DefaultGroupName={#MyAppName}
PrivilegesRequired=lowest
OutputDir=..\dist
OutputBaseFilename=Malindu_PDF_Pro_Setup_x64
Compression=lzma2
SolidCompression=yes
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UninstallDisplayIcon={app}\{#MyAppExeName}
ChangesAssociations=yes
[Files]
Source: "..\dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
[Icons]
Name: "{group}\Malindu PDF Pro"; Filename: "{app}\{#MyAppExeName}"
Name: "{autodesktop}\Malindu PDF Pro"; Filename: "{app}\{#MyAppExeName}"
[Registry]
Root: HKCU; Subkey: "Software\Classes\MalinduPDFPro.Document"; ValueType: string; ValueData: "PDF Document"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\MalinduPDFPro.Document\DefaultIcon"; ValueType: string; ValueData: "{app}\{#MyAppExeName},0"
Root: HKCU; Subkey: "Software\Classes\MalinduPDFPro.Document\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExeName}"" ""%1"""
Root: HKCU; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "MalinduPDFPro.Document"; ValueData: ""; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Malindu\PDFPro\Capabilities"; ValueType: string; ValueName: "ApplicationName"; ValueData: "Malindu PDF Pro"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Malindu\PDFPro\Capabilities"; ValueType: string; ValueName: "ApplicationDescription"; ValueData: "Malindu PDF Pro PDF reader"
Root: HKCU; Subkey: "Software\Malindu\PDFPro\Capabilities\FileAssociations"; ValueType: string; ValueName: ".pdf"; ValueData: "MalinduPDFPro.Document"
Root: HKCU; Subkey: "Software\RegisteredApplications"; ValueType: string; ValueName: "Malindu PDF Pro"; ValueData: "Software\Malindu\PDFPro\Capabilities"; Flags: uninsdeletevalue
[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Launch Malindu PDF Pro"; Flags: nowait postinstall skipifsilent
