[Setup]
; App Information
AppName=PDF Aura
AppVersion=2.1
AppPublisher=PDF Aura Team
VersionInfoVersion=2.1.0.0

; Architecture
ArchitecturesInstallIn64BitMode=x64
DefaultDirName={autopf}\PDF Aura
DefaultGroupName=PDF Aura
DisableProgramGroupPage=yes

; Look and Feel
WizardStyle=modern
SetupIconFile=assets\app_icon.ico
WizardImageFile=assets\wizard_large.bmp
WizardSmallImageFile=assets\wizard_small.bmp
UninstallDisplayIcon={app}\PDFAura.exe

; Output
OutputDir=dist
OutputBaseFilename=PDFAura-Setup
Compression=lzma2/ultra64
SolidCompression=yes

; Behavior
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Files]
Source: "dist\PDFAura\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PDF Aura"; Filename: "{app}\PDFAura.exe"
Name: "{autodesktop}\PDF Aura"; Filename: "{app}\PDFAura.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"

[Run]
Filename: "{app}\PDFAura.exe"; Description: "PDF Aura'yi baslat"; Flags: nowait postinstall skipifsilent
