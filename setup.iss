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
Filename: "{app}\PDFAura.exe"; Description: "PDF Aura'yı başlat"; Flags: nowait postinstall skipifsilent

[CustomMessages]
WebView2Title=Microsoft Edge WebView2
WebView2Body=PDF Aura'nın penceresini çizen WebView2 çalışma zamanı indirilip kuruluyor...
WebView2Failed=Microsoft Edge WebView2 çalışma zamanı kurulamadı. PDF Aura onsuz açılmaz; daha sonra https://go.microsoft.com/fwlink/p/?LinkId=2124703 adresinden kurabilirsiniz.%n%nKuruluma yine de devam edilsin mi?

[Code]
// PDF Aura's window is drawn by the Edge WebView2 runtime. Windows 11 and
// an up-to-date Windows 10 already have it; elsewhere Microsoft's
// Evergreen bootstrapper (~2 MB) is downloaded and run, so the installer
// itself stays small and never ships an outdated runtime.
const
  WebView2Client = 'SOFTWARE\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}';
  WebView2Bootstrapper = 'https://go.microsoft.com/fwlink/p/?LinkId=2124703';

var
  DownloadPage: TDownloadWizardPage;

function HasVersion(RootKey: Integer; SubKey: String): Boolean;
var
  Version: String;
begin
  Result := RegQueryStringValue(RootKey, SubKey, 'pv', Version) and (Version <> '') and (Version <> '0.0.0.0');
end;

// The places Microsoft documents: per machine (32-bit view), per user.
function WebView2Installed: Boolean;
begin
  Result := HasVersion(HKLM32, WebView2Client) or (IsWin64 and HasVersion(HKLM64, WebView2Client))
    or HasVersion(HKCU, WebView2Client);
end;

procedure InitializeWizard;
begin
  DownloadPage := CreateDownloadPage(CustomMessage('WebView2Title'), CustomMessage('WebView2Body'), nil);
end;

function InstallWebView2: Boolean;
var
  ResultCode: Integer;
begin
  DownloadPage.Clear;
  DownloadPage.Add(WebView2Bootstrapper, 'MicrosoftEdgeWebview2Setup.exe', '');
  DownloadPage.Show;
  try
    try
      DownloadPage.Download;
      Exec(ExpandConstant('{tmp}\MicrosoftEdgeWebview2Setup.exe'), '/silent /install', '', SW_HIDE,
           ewWaitUntilTerminated, ResultCode);
    except
      Log(GetExceptionMessage);
    end;
  finally
    DownloadPage.Hide;
  end;
  Result := WebView2Installed;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = wpReady) and not WebView2Installed and not InstallWebView2 then
    Result := MsgBox(CustomMessage('WebView2Failed'), mbConfirmation, MB_YESNO) = IDYES;
end;
