# Build dist\HackerCam\ and the installer dist\HackerCam-<version>-windows-x64-setup.exe.
# Usage (PowerShell): packaging\build_windows.ps1   (uses .venv\Scripts\python.exe unless $env:PYTHON is set)
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")

$py = if ($env:PYTHON) { $env:PYTHON } else { ".venv\Scripts\python.exe" }
$version = (Select-String -Path app.py -Pattern '^__version__ = "(.+)"').Matches[0].Groups[1].Value

Write-Host "==> Icons"
& $py packaging/make_icons.py
if ($LASTEXITCODE) { throw "make_icons failed" }

Write-Host "==> PyInstaller"
& $py -m PyInstaller --noconfirm --clean --distpath dist --workpath build packaging/hacker_cam.spec
if ($LASTEXITCODE) { throw "PyInstaller failed" }

Write-Host "==> Self-test"
# GUI-subsystem exe: Start-Process -Wait is needed to get its exit code. It has
# no console, so the self-test writes its report to %TEMP%\hackercam-selftest.txt.
$log = Join-Path $env:TEMP "hackercam-selftest.txt"
Remove-Item $log -ErrorAction SilentlyContinue
$p = Start-Process -FilePath "dist\HackerCam\HackerCam.exe" -ArgumentList "--self-test" -Wait -PassThru
if (Test-Path $log) { Get-Content $log }
if ($p.ExitCode -ne 0) { throw "Self-test failed (exit $($p.ExitCode))" }

Write-Host "==> Installer"
$iscc = (Get-Command iscc.exe -ErrorAction SilentlyContinue).Source
if (-not $iscc) {
    $iscc = @("${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe", "$env:ProgramFiles\Inno Setup 6\ISCC.exe") |
            Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $iscc) { throw "Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup" }
& $iscc "/DAppVersion=$version" packaging\windows\installer.iss
if ($LASTEXITCODE) { throw "Inno Setup failed" }

Write-Host "==> Done"
Get-ChildItem dist\*.exe | Format-Table Name, @{n="MB"; e={[math]::Round($_.Length / 1MB)}}
