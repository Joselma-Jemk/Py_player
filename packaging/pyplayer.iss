; Installateur Windows de PyPlayer (Inno Setup 6).
; Construit par le CI :  iscc /DAppVersion=0.2.0 /DExeSource=dist\pyplayer-0.2.0-windows-AMD64.exe packaging\pyplayer.iss
; Sans droits administrateur par défaut (installation pour l'utilisateur courant), droits admin proposés au choix.

#ifndef AppVersion
  #define AppVersion "0.0.0"
#endif
#ifndef ExeSource
  #define ExeSource "..\dist\pyplayer.exe"
#endif

[Setup]
AppId={{6D3C1A52-8F0B-4E7A-9B21-5C4E7F1A93D8}
AppName=PyPlayer
AppVersion={#AppVersion}
AppVerName=PyPlayer {#AppVersion}
AppPublisher=PyPlayer
DefaultDirName={autopf}\PyPlayer
DefaultGroupName=PyPlayer
DisableProgramGroupPage=yes
UninstallDisplayIcon={app}\PyPlayer.exe
UninstallDisplayName=PyPlayer {#AppVersion}
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
ChangesAssociations=yes
ChangesEnvironment=yes
LicenseFile=..\LICENSE
OutputDir=..\dist
OutputBaseFilename=pyplayer-{#AppVersion}-windows-setup
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=yes

[Languages]
Name: "french"; MessagesFile: "compiler:Languages\French.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked
Name: "addtopath"; Description: "Ajouter la commande « pyplayer » au PATH (pyplayer download <lien> dans un terminal)"; GroupDescription: "Ligne de commande :"

[Files]
Source: "{#ExeSource}"; DestDir: "{app}"; DestName: "PyPlayer.exe"; Flags: ignoreversion
Source: "pyplayer.cmd"; DestDir: "{app}\bin"; Flags: ignoreversion; Tasks: addtopath

[Icons]
Name: "{autoprograms}\PyPlayer"; Filename: "{app}\PyPlayer.exe"
Name: "{autodesktop}\PyPlayer"; Filename: "{app}\PyPlayer.exe"; Tasks: desktopicon

[Registry]
; PATH : dossier « bin » (qui ne contient que pyplayer.cmd). Utilisateur seul ou système selon le mode d'installation.
Root: HKCU; Subkey: "Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:PathWith|{app}\bin}"; Tasks: addtopath; Check: (not IsAdminInstallMode) and NeedsAddPath(ExpandConstant('{app}\bin'))
Root: HKLM; Subkey: "SYSTEM\CurrentControlSet\Control\Session Manager\Environment"; ValueType: expandsz; ValueName: "Path"; ValueData: "{code:PathWith|{app}\bin}"; Tasks: addtopath; Check: IsAdminInstallMode and NeedsAddPath(ExpandConstant('{app}\bin'))
; Programme déclaré : apparaît dans « Ouvrir avec… » pour les formats listés (sans prendre la main sur le lecteur par défaut).
Root: HKA; Subkey: "Software\Classes\PyPlayer.media"; ValueType: string; ValueName: ""; ValueData: "Média PyPlayer"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\PyPlayer.media\DefaultIcon"; ValueType: string; ValueName: ""; ValueData: "{app}\PyPlayer.exe,0"
Root: HKA; Subkey: "Software\Classes\PyPlayer.media\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PyPlayer.exe"" ""%1"""
Root: HKA; Subkey: "Software\Classes\Applications\PyPlayer.exe"; ValueType: string; ValueName: "FriendlyAppName"; ValueData: "PyPlayer"; Flags: uninsdeletekey
Root: HKA; Subkey: "Software\Classes\Applications\PyPlayer.exe\shell\open\command"; ValueType: string; ValueName: ""; ValueData: """{app}\PyPlayer.exe"" ""%1"""
; Vidéo
Root: HKA; Subkey: "Software\Classes\.mp4\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.m4v\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mkv\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.avi\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mov\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.webm\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.wmv\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.flv\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mpeg\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mpg\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mpe\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.ts\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.m2ts\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.mts\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.3gp\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.ogv\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.vob\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.asf\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.divx\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
; Audio
Root: HKA; Subkey: "Software\Classes\.mp3\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.wav\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.flac\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.aac\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.ogg\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.oga\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.opus\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.m4a\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue
Root: HKA; Subkey: "Software\Classes\.wma\OpenWithProgids"; ValueType: string; ValueName: "PyPlayer.media"; ValueData: ""; Flags: uninsdeletevalue

[Run]
Filename: "{app}\PyPlayer.exe"; Description: "{cm:LaunchProgram,PyPlayer}"; Flags: nowait postinstall skipifsilent

[Code]
const
  UserEnvKey = 'Environment';
  SystemEnvKey = 'SYSTEM\CurrentControlSet\Control\Session Manager\Environment';

function EnvRoot: Integer;
begin
  if IsAdminInstallMode then
    Result := HKEY_LOCAL_MACHINE
  else
    Result := HKEY_CURRENT_USER;
end;

function EnvSubkey: String;
begin
  if IsAdminInstallMode then
    Result := SystemEnvKey
  else
    Result := UserEnvKey;
end;

{ Vrai si le dossier n'est pas déjà dans le PATH (comparaison sans tenir compte de la casse). }
function NeedsAddPath(Dir: String): Boolean;
var
  Current: String;
begin
  if not RegQueryStringValue(EnvRoot, EnvSubkey, 'Path', Current) then
  begin
    Result := True;
    Exit;
  end;
  Result := Pos(';' + Uppercase(Dir) + ';', ';' + Uppercase(Current) + ';') = 0;
end;

{ Nouvelle valeur du PATH : l'ancienne + le dossier (sans « ; » superflu si le PATH était vide). }
function PathWith(Dir: String): String;
var
  Current: String;
begin
  if not RegQueryStringValue(EnvRoot, EnvSubkey, 'Path', Current) then
    Current := '';
  if Current = '' then
    Result := Dir
  else if Copy(Current, Length(Current), 1) = ';' then
    Result := Current + Dir
  else
    Result := Current + ';' + Dir;
end;

{ À la désinstallation : retire seulement notre dossier du PATH, le reste est conservé. }
procedure RemoveFromPath(Dir: String);
var
  Current: String;
begin
  if not RegQueryStringValue(EnvRoot, EnvSubkey, 'Path', Current) then
    Exit;
  Current := ';' + Current + ';';
  StringChangeEx(Current, ';' + Dir + ';', ';', True);
  if (Length(Current) > 0) and (Current[1] = ';') then
    Delete(Current, 1, 1);
  if (Length(Current) > 0) and (Current[Length(Current)] = ';') then
    Delete(Current, Length(Current), 1);
  RegWriteExpandStringValue(EnvRoot, EnvSubkey, 'Path', Current);
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usPostUninstall then
    RemoveFromPath(ExpandConstant('{app}\bin'));
end;
