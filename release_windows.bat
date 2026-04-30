@echo off
:: Usage: release_windows.bat 0.1.68

set VERSION=%~1

if "%VERSION%"=="" (
    echo Usage: release_windows.bat ^<version^> "^<release notes^>"
    exit /b 1
)

echo pulling latest code...
git pull

echo updating version to %VERSION%...
echo VERSION = "%VERSION%" > flipper_daemon\version.py
powershell -Command "(Get-Content language_flipper_setup.iss) -replace 'AppVersion=.*', 'AppVersion=%VERSION%' | Set-Content language_flipper_setup.iss"

echo building exe...
pyinstaller --noconfirm language_flipper_windows.spec

echo packaging installer...
if exist "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" (
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" language_flipper_setup.iss
) else if exist "C:\Program Files\Inno Setup 6\ISCC.exe" (
    "C:\Program Files\Inno Setup 6\ISCC.exe" language_flipper_setup.iss
) else (
    echo ERROR: Inno Setup 6 not found. Please install it from https://jrsoftware.org/isdl.php
    exit /b 1
)

echo committing version bump...
git add flipper_daemon\version.py language_flipper_setup.iss
git commit -m "bump version to %VERSION% (windows)"
git push

echo releasing to GitHub...
gh release create "v%VERSION%-windows" "dist\Language-Flipper-Setup.exe" --title "Language Flipper %VERSION% - Windows" --generate-notes

echo.
echo Done! Released v%VERSION%-windows
