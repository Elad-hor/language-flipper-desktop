; Language Flipper — Windows Installer
; Produces: Language-Flipper-Setup.exe
; No admin rights required (installs per-user to AppData\Local\Programs)

[Setup]
AppName=Language Flipper
AppVersion=0.1.57
AppPublisher=Elad Horenstine
AppPublisherURL=https://github.com/Elad-hor/language-flipper-desktop
DefaultDirName={localappdata}\Programs\Language Flipper
DefaultGroupName=Language Flipper
OutputDir=dist
OutputBaseFilename=Language-Flipper-Setup
SetupIconFile=assets\icon.ico
Compression=lzma
SolidCompression=yes
PrivilegesRequired=lowest
WizardStyle=modern
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\Language Flipper.exe
UninstallDisplayName=Language Flipper
CloseApplications=yes
RestartApplications=yes

[Files]
Source: "dist\Language Flipper.exe"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\Language Flipper"; Filename: "{app}\Language Flipper.exe"
Name: "{group}\Uninstall Language Flipper"; Filename: "{uninstallexe}"

[Tasks]
Name: "startup"; Description: "Start Language Flipper automatically when Windows starts"; GroupDescription: "Startup options:"

[Registry]
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "LanguageFlipper"; ValueData: """{app}\Language Flipper.exe"""; Tasks: startup; Flags: uninsdeletevalue

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM ""Language Flipper.exe"""; Flags: runhidden waituntilterminated

[Run]
Filename: "{app}\Language Flipper.exe"; Description: "Launch Language Flipper now"; Flags: nowait postinstall skipifsilent
