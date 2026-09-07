# Build the Windows executable

This source package includes build tooling, not a prebuilt EXE. Windows builds
must run on Windows; [PyInstaller does not cross-compile](https://www.pyinstaller.org/).
No Windows runner is available in the authoring environment. The workflow below
has been prepared but has not been run or published automatically.

## On your Windows PC

1. Extract this repository with all files together.
2. With Python installed, double-click `BUILD-WINDOWS.bat`.
3. The script creates an isolated build environment, installs the pinned
   PyInstaller build tool, runs tests, builds the app, and runs its HTTP self-test.
4. On success, it opens the `release` folder containing `PokemonTeam.exe`.
5. Share that EXE with the README and third-party notices. Recipients can
   double-click the EXE without installing Python. Keep its terminal open.

The EXE saves `pokemon-team-data.json` beside itself, outside its extraction
folder, so progress survives restarts. Put it in a writable folder. A console
window is intentionally retained for the OBS URL, diagnostics, and Ctrl+C.
The build is unsigned; no publisher certificate is bundled.

## On GitHub

Upload all repository files at the top level, including
`.github/workflows/windows-build.yml`. Do not nest them inside another project
folder. The workflow runs on pushes to main that change relevant files, or can
be started manually from **Actions → Build Windows app → Run workflow**.

When it succeeds, download the `PokemonTeam-Windows` artifact from the workflow
run and extract `PokemonTeam.exe`. You can attach the executable to a GitHub
Release for public downloads. Creating a Release is a separate publishing step;
the workflow does not publish one or change your repository permissions.

Before announcing the executable, run it on your PC, add a Pokémon, verify a
live OBS update, close/reopen it, and check that the team persists.
