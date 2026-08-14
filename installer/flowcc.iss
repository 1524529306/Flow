; FlowCC 安装包脚本（Inno Setup 6）
; 编译：ISCC.exe installer\flowcc.iss
; 产物：release\FlowCC-Setup-2.2.6.exe（下一步式安装向导，免管理员权限）

[Setup]
AppName=FlowCC
AppVersion=2.2.6
AppVerName=FlowCC 2.2.6
AppPublisher=FlowCC
VersionInfoVersion=2.2.6.0
DefaultDirName={autopf}\FlowCC
DefaultGroupName=FlowCC
OutputDir=..\release
OutputBaseFilename=FlowCC-Setup-2.2.6
SetupIconFile=..\flowcc.ico
UninstallDisplayIcon={app}\flowcc.ico
UninstallDisplayName=FlowCC
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=lowest
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

[Languages]
Name: "zh"; MessagesFile: "compiler:Default.isl,zh_cn.isl"

[Tasks]
Name: "desktopicon"; Description: "创建桌面快捷方式"

[Files]
Source: "..\dist\FlowCC.exe"; DestDir: "{app}"; Flags: ignoreversion
Source: "..\flowcc.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\FlowCC"; Filename: "{app}\FlowCC.exe"; IconFilename: "{app}\flowcc.ico"
Name: "{group}\卸载 FlowCC"; Filename: "{uninstallexe}"
Name: "{autodesktop}\FlowCC"; Filename: "{app}\FlowCC.exe"; IconFilename: "{app}\flowcc.ico"; Tasks: desktopicon

[Run]
Filename: "{app}\FlowCC.exe"; Description: "立即启动 FlowCC"; Flags: nowait postinstall skipifsilent
