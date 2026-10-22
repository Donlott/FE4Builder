# Regenerate the Launcher shortcut if FE4Builder is moved to another folder.
$ErrorActionPreference = 'Stop'
$builderDirectory = Split-Path -Parent $PSScriptRoot
$shellObject = New-Object -ComObject WScript.Shell
$shortcut = $shellObject.CreateShortcut((Join-Path $builderDirectory 'Launcher.lnk'))
$shortcut.TargetPath = Join-Path $PSScriptRoot 'Launcher.cmd'
$shortcut.WorkingDirectory = $builderDirectory
$shortcut.IconLocation = (Join-Path $builderDirectory 'assets\sigurd.ico') + ',0'
$shortcut.Description = 'Launch FE4Builder'
$shortcut.WindowStyle = 1
$shortcut.Save()
