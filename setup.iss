[Setup]
AppName=PDF Aura
AppVersion=1.0
DefaultDirName={autopf}\PDF Aura
DefaultGroupName=PDF Aura
OutputDir=dist
OutputBaseFilename=PDFAura_TamKurulum
Compression=lzma
SolidCompression=yes
PrivilegesRequired=admin
SetupIconFile=assets\app_icon.ico
WizardImageFile=assets\wizard_large.bmp
WizardSmallImageFile=assets\wizard_small.bmp

[Files]
Source: "build\exe.win-amd64-3.10\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs
Source: "assets\gs10040w64.exe"; DestDir: "{tmp}"; Flags: deleteafterinstall

[Icons]
Name: "{group}\PDF Aura"; Filename: "{app}\PDFAura.exe"
Name: "{autodesktop}\PDF Aura"; Filename: "{app}\PDFAura.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"

[Run]
Filename: "{tmp}\gs10040w64.exe"; StatusMsg: "Gerekli altyapi: Ghostscript kuruluyor (Lutfen cikan pencerede Ileri diyerek kurun)..."; Flags: waituntilterminated
Filename: "{app}\PDFAura.exe"; Description: "PDF Aura'yi baslat"; Flags: nowait postinstall skipifsilent
