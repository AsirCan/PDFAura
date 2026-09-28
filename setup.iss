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

#define GhostscriptInstaller "assets\gs10040w64.exe"

[Files]
Source: "dist\PDFAura\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
; The Ghostscript installer is not in the repository (it is a third-party
; binary). Bundle it only if it has been placed in assets\, so that
; `iscc setup.iss` works on a clean clone.
#if FileExists(GhostscriptInstaller)
Source: "{#GhostscriptInstaller}"; DestDir: "{tmp}"; Flags: deleteafterinstall
#endif

[Icons]
Name: "{group}\PDF Aura"; Filename: "{app}\PDFAura.exe"
Name: "{autodesktop}\PDF Aura"; Filename: "{app}\PDFAura.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"

[Run]
#if FileExists(GhostscriptInstaller)
Filename: "{tmp}\gs10040w64.exe"; Parameters: "/S"; StatusMsg: "Ghostscript motoru arka planda kuruluyor, lutfen bekleyin..."; Flags: waituntilterminated; Check: NeedsGhostscript
#endif
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
