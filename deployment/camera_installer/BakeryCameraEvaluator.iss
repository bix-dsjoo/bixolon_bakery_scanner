#ifndef AppVersion
  #error AppVersion must be defined by the build wrapper
#endif
#ifndef PayloadRoot
  #error PayloadRoot must be defined by the build wrapper
#endif

[Setup]
AppId={{E6B7A8D8-CE4D-4B3D-9B48-7A27279140B2}
AppName=BIXOLON Bakery AI Evaluator
AppVersion={#AppVersion}
AppPublisher=BIXOLON
DefaultDirName={localappdata}\Programs\BIXOLON Bakery AI Evaluator
DefaultGroupName=BIXOLON Bakery AI Evaluator
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
#ifdef ValidateOnly
Output=no
Compression=none
SolidCompression=no
#elif defined(FastCompile)
Compression=none
SolidCompression=no
#else
Compression=lzma2/ultra64
SolidCompression=yes
#endif
OutputBaseFilename=BixolonBakeryEvaluator-{#AppVersion}-win-x64-setup
UninstallDisplayIcon={app}\bakery_camera_prototype.exe
WizardStyle=modern
CloseApplications=yes
RestartApplications=no
SetupLogging=yes
VersionInfoVersion={#AppVersion}
VersionInfoCompany=BIXOLON
VersionInfoDescription=BIXOLON Bakery AI Evaluator Setup
VersionInfoProductName=BIXOLON Bakery AI Evaluator
VersionInfoProductVersion={#AppVersion}

[Tasks]
Name: "desktopicon"; Description: "바탕 화면 바로 가기 만들기"; GroupDescription: "추가 바로 가기:"; Flags: unchecked

[Files]
Source: "{#PayloadRoot}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\BIXOLON Bakery AI Evaluator"; Filename: "{app}\bakery_camera_prototype.exe"; WorkingDir: "{app}"
Name: "{autodesktop}\BIXOLON Bakery AI Evaluator"; Filename: "{app}\bakery_camera_prototype.exe"; WorkingDir: "{app}"; Tasks: desktopicon

[Run]
Filename: "{app}\bakery_camera_prototype.exe"; Description: "BIXOLON Bakery AI Evaluator 실행"; WorkingDir: "{app}"; Flags: nowait postinstall skipifsilent
