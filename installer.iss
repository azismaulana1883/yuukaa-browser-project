[Setup]
AppId={{C7A2E9F2-3B44-4A8E-9801-D36F6D44123A}
AppName=Yuukaa Browser
AppVersion=13.0
AppPublisher=Azis Maulana (Yuukaa)
AppCopyright=Copyright (C) 2026 Azis Maulana (Yuukaa)
LicenseFile=G:\yuukaa-browser\license.txt
DefaultDirName={autopf}\Yuukaa Browser
DefaultGroupName=Yuukaa Browser
OutputDir=G:\yuukaa-browser\installer
OutputBaseFilename=Yuukaa_Browser_V13_Setup
SetupIconFile=G:\yuukaa-browser\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
ArchitecturesAllowed=x64
ArchitecturesInstallIn64BitMode=x64
CloseApplications=yes
RestartApplications=yes

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}";

[Files]
Source: "G:\yuukaa-browser\dist\YuukaaBrowser\YuukaaBrowser.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "G:\yuukaa-browser\dist\YuukaaBrowser\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\Yuukaa Browser"; Filename: "{app}\YuukaaBrowser.exe"
Name: "{autodesktop}\Yuukaa Browser"; Filename: "{app}\YuukaaBrowser.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\YuukaaBrowser.exe"; Description: "{cm:LaunchProgram,Yuukaa Browser}"; Flags: nowait postinstall skipifsilent
