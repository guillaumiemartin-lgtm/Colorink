@echo off
rem ColorInk - lanceur Windows (double-clic)
rem Copyright (c) 2026 Martin Guillaumie - licence MIT
rem Au premier lancement : installe "uv", qui telecharge ensuite Python et les
rem bibliotheques (quelques minutes). Ensuite, l application demarre directement.
setlocal
cd /d "%~dp0"

set "UV="
where uv >nul 2>nul && set "UV=uv"
if not defined UV if exist "%USERPROFILE%\.local\bin\uv.exe" set "UV=%USERPROFILE%\.local\bin\uv.exe"
if not defined UV (
    echo Premiere utilisation : installation de uv...  /  First run: installing uv...
    powershell -NoProfile -ExecutionPolicy ByPass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "UV=%USERPROFILE%\.local\bin\uv.exe"
)
if not exist "%USERPROFILE%\.local\bin\uv.exe" if not "%UV%"=="uv" (
    echo Echec de l installation de uv.  /  uv installation failed.
    pause
    exit /b 1
)

rem Raccourci sur le Bureau, avec l icone (mis a jour a chaque lancement)
powershell -NoProfile -Command "$d=[Environment]::GetFolderPath('Desktop'); $l=Join-Path $d 'ColorInk.lnk'; $n=-not (Test-Path $l); $s=(New-Object -ComObject WScript.Shell).CreateShortcut($l); $s.TargetPath='%~dp0lancer.bat'; $s.WorkingDirectory='%~dp0'; $s.IconLocation='%~dp0images\icone.ico'; $s.Save(); if ($n) { Write-Host 'Raccourci ColorInk ajoute sur le Bureau.' }"

echo Demarrage de ColorInk...  /  Starting ColorInk...
"%UV%" run --project "%~dp0." python "%~dp0interface.py"
if errorlevel 1 pause
