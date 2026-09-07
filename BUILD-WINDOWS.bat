@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>nul
if %errorlevel% equ 0 (
  py -3 -m venv .venv-build
) else (
  python -m venv .venv-build
)
if errorlevel 1 goto failed
.venv-build\Scripts\python.exe -m pip install -r requirements-build.txt
if errorlevel 1 goto failed
.venv-build\Scripts\python.exe -m unittest -q
if errorlevel 1 goto failed
.venv-build\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --console --name PokemonTeam --distpath release pokemon_team.py
if errorlevel 1 goto failed
release\PokemonTeam.exe --self-test
if errorlevel 1 goto failed
echo Built release\PokemonTeam.exe. People running this EXE do not need Python.
start "" release
pause
exit /b 0
:failed
echo Build failed. Read the error above; no successful build is claimed.
pause
exit /b 1
