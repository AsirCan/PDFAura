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

; Silent install/uninstall (Inno's standard switches, no extra work needed):
;   PDFAura-Setup.exe /VERYSILENT /SUPPRESSMSGBOXES /NORESTART
;   /TASKS="desktopicon,contextmenu,fileassoc" picks the integrations; leave a
;   name out to skip it, e.g. /TASKS="desktopicon". Silent installs never open
;   the app and never wait for the WebView2 failure question.
;   Uninstall: unins000.exe /VERYSILENT /SUPPRESSMSGBOXES
;   Add /REMOVESETTINGS=1 to that command to delete %APPDATA%\PDFAura too.

[Files]
Source: "dist\PDFAura\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\PDF Aura"; Filename: "{app}\PDFAura.exe"
Name: "{autodesktop}\PDF Aura"; Filename: "{app}\PDFAura.exe"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Masaüstü kısayolu oluştur"; Flags: checkedonce
Name: "contextmenu"; Description: "PDF dosyalarına sağ tık menüsü ekle (Sıkıştır, Kes, Birleştir)"; Flags: checkedonce
Name: "fileassoc"; Description: "PDF Aura'yı PDF dosyaları için ""Birlikte aç"" listesine ekle"; Flags: checkedonce

[Registry]
; Per-user entries: no administrator rights are needed and uninstalling the
; app removes them again (uninsdeletekey). The Python module that shows the
; same entries from Settings writes exactly this layout.
; "Sıkıştır" and "Kes" receive the clicked file as %1; "Birleştir" receives
; every selected file as %* and is offered for multi-selections.
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Compress"; ValueType: string; ValueName: ""; ValueData: "PDF Aura ile Sıkıştır"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Compress"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\PDFAura.exe,0"; Flags: uninsdeletevalue; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Compress\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFAura.exe"" compress ""%1"" -q ebook"; Flags: uninsdeletekey; Tasks: contextmenu

Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Split"; ValueType: string; ValueName: ""; ValueData: "PDF Aura ile Kes"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Split"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\PDFAura.exe,0"; Flags: uninsdeletevalue; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Split\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFAura.exe"" split ""%1"" --pages 1-1"; Flags: uninsdeletekey; Tasks: contextmenu

Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Merge"; ValueType: string; ValueName: ""; ValueData: "PDF Aura ile Birleştir"; Flags: uninsdeletekey; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Merge"; ValueType: string; ValueName: "Icon"; ValueData: "{app}\PDFAura.exe,0"; Flags: uninsdeletevalue; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Merge"; ValueType: string; ValueName: "MultiSelectModel"; ValueData: "Player"; Flags: uninsdeletevalue; Tasks: contextmenu
Root: HKA; Subkey: "Software\Classes\SystemFileAssociations\.pdf\shell\PDFAura.Merge\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFAura.exe"" merge %*"; Flags: uninsdeletekey; Tasks: contextmenu

; "Birlikte aç" only: the default .pdf handler is left alone. OpenWithProgids
; is shared, so only our value is removed on uninstall.
Root: HKA; Subkey: "Software\Classes\.pdf\OpenWithProgids"; ValueType: string; ValueName: "PDFAura.Document"; ValueData: ""; Flags: uninsdeletevalue; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDFAura.Document"; ValueType: string; ValueName: ""; ValueData: "PDF Belgesi"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDFAura.Document\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\PDFAura.exe,0"; Flags: uninsdeletekey; Tasks: fileassoc
Root: HKA; Subkey: "Software\Classes\PDFAura.Document\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PDFAura.exe"" ""%1"""; Flags: uninsdeletekey; Tasks: fileassoc

[Run]
Filename: "{app}\PDFAura.exe"; Description: "PDF Aura'yı başlat"; Flags: nowait postinstall skipifsilent

[CustomMessages]
WebView2Title=Microsoft Edge WebView2
WebView2Body=PDF Aura'nın penceresini çizen WebView2 çalışma zamanı indirilip kuruluyor...
WebView2Failed=Microsoft Edge WebView2 çalışma zamanı kurulamadı. PDF Aura onsuz açılmaz; daha sonra https://go.microsoft.com/fwlink/p/?LinkId=2124703 adresinden kurabilirsiniz.%n%nKuruluma yine de devam edilsin mi?
RemoveSettingsPrompt=PDF Aura'nın kullanıcı ayarları ve son açılan dosya listesi de silinsin mi?%n%nAyarları saklamak için Hayır'ı seçin.

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
    // A silent install has nobody to answer this question; keep going and
    // let the app explain the missing runtime if it cannot start.
    Result := WizardSilent or
      (MsgBox(CustomMessage('WebView2Failed'), mbConfirmation, MB_YESNO) = IDYES);
end;

// Uninstall keeps %APPDATA%\PDFAura (preferences, recent files, logs) by
// default, so reinstalling does not lose the user's setup. The question is
// skipped in silent mode; pass /REMOVESETTINGS=1 there to clear it too.
procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep <> usPostUninstall then
    Exit;

  if UninstallSilent then
  begin
    if ExpandConstant('{param:REMOVESETTINGS|0}') = '1' then
      DelTree(ExpandConstant('{userappdata}\PDFAura'), True, True, True);
    Exit;
  end;

  if MsgBox(CustomMessage('RemoveSettingsPrompt'), mbConfirmation, MB_YESNO) = IDYES then
    DelTree(ExpandConstant('{userappdata}\PDFAura'), True, True, True);
end;
