[Setup]
; App Information
AppName=PDF Aura
AppVersion=1.0
AppPublisher=PDF Aura Team
VersionInfoVersion=1.0.0.0

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
OutputBaseFilename=PDFAura
Compression=lzma2/ultra64
SolidCompression=yes

; Behavior
PrivilegesRequired=admin
CloseApplications=yes
RestartApplications=no

[Files]
Source: "dist\PDFAura\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\gs10040w64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\PDF Aura"; Filename: "{app}\PDFAura.exe"
Name: "{autodesktop}\PDF Aura"; Filename: "{app}\PDFAura.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"

[Run]
Filename: "{tmp}\gs10040w64.exe"; Parameters: "/S"; StatusMsg: "Ghostscript motoru arka planda kuruluyor, lutfen bekleyin..."; Flags: waituntilterminated; Check: NeedsGhostscript
Filename: "{app}\PDFAura.exe"; Description: "PDF Aura'yi baslat"; Flags: nowait postinstall skipifsilent

[Code]
function IsGhostscriptInstalled: Boolean;
begin
  Result := RegKeyExists(HKLM, 'SOFTWARE\GPL Ghostscript') or RegKeyExists(HKLM64, 'SOFTWARE\GPL Ghostscript') or RegKeyExists(HKCU, 'SOFTWARE\GPL Ghostscript');
end;

function NeedsGhostscript: Boolean;
begin
  Result := not IsGhostscriptInstalled;
end;
